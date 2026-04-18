# relay_server/main.py — FastAPI 中继服务器（精简版）
# =================================================================
# 设计原则：
# 1. 轻量级中继 — 只负责分发参数、收集必要数据
# 2. 客户端完全解耦 — 离线时能独立工作
# 3. 降级友好 — 服务器不可用时客户端不阻塞
# 4. 无外部依赖 — 不依赖 Bot/Forum/Email 等复杂功能
# 5. 多语言支持 — 支持中文/英文
# =================================================================

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from contextlib import asynccontextmanager

# 添加项目根目录到路径
_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_root))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Header
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# i18n 支持
try:
    from core.i18n import _, get_available_locales, set_locale, get_locale
    _HAS_I18N = True
except ImportError:
    _HAS_I18N = False
    def _(s): return s
    def get_available_locales(): return {"en_US": "English"}
    def set_locale(l): pass
    def get_locale(): return "en_US"

# ========== 配置 ==========

def get_data_dir() -> Path:
    """获取数据目录"""
    return Path(os.environ.get(
        "HERMES_RELAY_DATA",
        str(Path.home() / ".hermes-desktop" / "relay_server")
    ))

DATA_DIR = get_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

RAW_DIR = DATA_DIR / "raw"
AGG_DIR = DATA_DIR / "agg"
WEB_DIR = DATA_DIR / "web"
CONFIG_FILE = DATA_DIR / "config.json"
USER_CONFIGS_DIR = DATA_DIR / "user_configs"  # 用户配置存储目录

for d in [RAW_DIR, AGG_DIR, WEB_DIR, USER_CONFIGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ========== 服务器配置 ==========

DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 8766,
        "relay_enabled": True,
        "max_clients": 100,
        "cors_origins": ["*"],
    },
    "relay": {
        "dispatch_params": True,      # 分发中继参数
        "collect_stats": True,         # 收集统计数据
        "offline_fallback": True,      # 离线降级
    },
    "params": {
        # 可分发给客户端的中继参数
        "retry_timeout": 30,
        "max_retry": 3,
        "heartbeat_interval": 60,
        "batch_size": 10,
    }
}

def load_config() -> Dict[str, Any]:
    """加载服务器配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]):
    """保存服务器配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ========== 启动/关闭 ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("Hermes Relay Server 启动中...")
    logger.info(f"数据目录: {DATA_DIR}")
    logger.info(f"中继模式: {load_config().get('relay', {}).get('relay_enabled', True)}")
    yield
    logger.info("Hermes Relay Server 关闭中...")

# ========== FastAPI 应用 ==========

app = FastAPI(
    title="Hermes Relay Server",
    description="轻量级中继服务器 — 分发参数、收集数据、支持离线降级",
    version="2.0.0",
    lifespan=lifespan,
)

# ========== Pydantic 模型 ==========

class CollectRequest(BaseModel):
    """客户端数据收集请求"""
    week_id: str
    client_id: str
    patches: List[Dict[str, Any]] = []
    pain_points: List[Dict[str, Any]] = []
    generated_at: int
    client_version: str = "2.0.0"
    platform: str = "unknown"


class HeartbeatRequest(BaseModel):
    """心跳请求"""
    client_id: str
    timestamp: int
    platform: str = "unknown"
    status: str = "online"


class RelayParamsRequest(BaseModel):
    """请求中继参数"""
    client_id: str
    capabilities: List[str] = []


# ========== 配置同步模型 ==========

class ConfigSyncPushRequest(BaseModel):
    """推送配置到服务器"""
    user_token: str = Field(..., min_length=8, max_length=128)
    config_key: str = Field(..., description="配置键，如 'app', 'ollama', 'model_market', 'search', 'agent'")
    config_data: Dict[str, Any] = Field(..., description="配置数据")
    client_id: str = Field(..., description="客户端ID")
    platform: str = "unknown"
    version: str = "2.0.0"


class ConfigSyncPullRequest(BaseModel):
    """拉取配置"""
    user_token: str = Field(..., min_length=8, max_length=128)


class ConfigSyncResponse(BaseModel):
    """配置同步响应"""
    success: bool
    config_key: str = ""
    config_data: Dict[str, Any] = {}
    server_timestamp: int = Field(default_factory=lambda: int(time.time()))
    message: str = ""


# ========== 工具函数 ==========

def get_week_file(week_id: str) -> Path:
    return RAW_DIR / f"weekly_{week_id}.json"

def load_weekly_data(week_id: str) -> Dict[str, Any]:
    week_file = get_week_file(week_id)
    if week_file.exists():
        try:
            with open(week_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"week_id": week_id, "reports": [], "aggregated": {}}

def save_weekly_data(week_id: str, data: Dict[str, Any]):
    week_file = get_week_file(week_id)
    with open(week_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def aggregate_week(week_id: str) -> Dict[str, Any]:
    """聚合周数据"""
    data = load_weekly_data(week_id)
    reports = data.get("reports", [])

    if not reports:
        return {}

    module_hits: Dict[str, int] = defaultdict(int)
    patch_actions: Dict[str, int] = defaultdict(int)
    pain_types: Dict[str, int] = defaultdict(int)
    clients: set = set()

    for report in reports:
        clients.add(report.get("client_id", ""))
        for patch in report.get("patches", []):
            module = patch.get("module", "unknown")
            action = patch.get("action", "unknown")
            module_hits[module] += 1
            patch_actions[action] += 1
        for pain in report.get("pain_points", []):
            pain_type = pain.get("pain_type", "unknown")
            pain_types[pain_type] += 1

    top_modules = sorted(
        [{"module": k, "count": v} for k, v in module_hits.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return {
        "week_id": week_id,
        "total_patches": sum(module_hits.values()),
        "total_pain_points": sum(pain_types.values()),
        "active_clients": len(clients),
        "top_modules": top_modules,
        "patch_distribution": dict(patch_actions),
        "pain_distribution": dict(pain_types),
        "aggregated_at": int(time.time()),
    }

def run_aggregation(week_id: str):
    """后台聚合任务"""
    try:
        agg = aggregate_week(week_id)
        if agg:
            agg_file = AGG_DIR / f"module_hits_{week_id}.json"
            with open(agg_file, "w", encoding="utf-8") as f:
                json.dump(agg, f, ensure_ascii=False, indent=2)
            logger.info(f"聚合完成: {week_id}, patches={agg.get('total_patches', 0)}")
    except Exception as e:
        logger.error(f"聚合失败: {e}")

# ========== 用户配置存储（配置同步用）============

def _get_user_config_path(user_token: str) -> Path:
    """获取用户配置文件的路径"""
    # 为了安全，对 user_token 做简单哈希处理
    import hashlib
    token_hash = hashlib.sha256(user_token.encode()).hexdigest()[:16]
    return USER_CONFIGS_DIR / f"uc_{token_hash}.json"


def _load_user_configs(user_token: str) -> Dict[str, Any]:
    """加载用户的所有配置"""
    path = _get_user_config_path(user_token)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "user_token": user_token,
        "configs": {},  # config_key -> {data, updated_at, client_id, platform}
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }


def _save_user_configs(user_token: str, data: Dict[str, Any]):
    """保存用户配置"""
    path = _get_user_config_path(user_token)
    data["updated_at"] = int(time.time())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== 核心 API ==========

@app.get("/")
async def root():
    """服务信息 / 项目首页"""
    # 优先返回 HTML 首页（如果已部署）
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    # 否则返回 JSON API 信息
    config = load_config()
    return {
        "service": "Hermes Relay Server",
        "version": "2.0.0",
        "status": "running",
        "relay_enabled": config.get("relay", {}).get("relay_enabled", True),
        "locale": get_locale() if _HAS_I18N else "en_US",
        "available_locales": list(get_available_locales().keys()) if _HAS_I18N else ["en_US"],
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "relay_mode": True,
        "locale": get_locale() if _HAS_I18N else "en_US",
    }


@app.post("/api/i18n/locale")
async def set_language(request: Dict[str, str]):
    """
    设置语言

    请求体: {"locale": "zh_CN"} 或 {"locale": "en_US"}
    """
    locale = request.get("locale", "en_US")
    if _HAS_I18N:
        locales = get_available_locales()
        if locale in locales:
            set_locale(locale)
            return {"success": True, "locale": locale, "message": _("Language updated")}
    return {"success": False, "error": "Invalid locale"}


@app.get("/api/i18n/locale")
async def get_language():
    """获取当前语言"""
    return {
        "locale": get_locale() if _HAS_I18N else "en_US",
        "available_locales": get_available_locales() if _HAS_I18N else {"en_US": "English"},
    }


# ========== 配置同步 API ==========

@app.post("/api/config/sync")
async def sync_config_push(request: ConfigSyncPushRequest):
    """
    推送本地配置到服务器（保存/更新）

    设计：
    - user_token 标识用户身份（所有设备用相同 token 则共享配置）
    - config_key 区分不同配置块（app/ollama/model_market/search/agent 等）
    - 使用 last-write-wins 策略：最新推送的配置覆盖旧配置
    - 服务器记录每个配置的更新时间、来源客户端和平台
    """
    logger.info(f"配置推送: user_token={request.user_token[:8]}..., "
                f"config_key={request.config_key}, client={request.client_id}")

    user_data = _load_user_configs(request.user_token)

    # 更新对应配置块
    config_entry = {
        "data": request.config_data,
        "updated_at": int(time.time()),
        "client_id": request.client_id,
        "platform": request.platform,
        "version": request.version,
    }
    user_data["configs"][request.config_key] = config_entry

    _save_user_configs(request.user_token, user_data)

    return {
        "success": True,
        "config_key": request.config_key,
        "server_timestamp": int(time.time()),
        "message": _("Config synced successfully"),
    }


@app.get("/api/config/sync")
async def sync_config_pull(
    user_token: str = Query(..., min_length=8, max_length=128),
    config_key: Optional[str] = Query(default=None, description="可选：只拉取特定配置块"),
):
    """
    从服务器拉取配置

    - 不带 config_key：拉取用户所有配置
    - 带 config_key：只拉取该配置块
    """
    logger.info(f"配置拉取: user_token={user_token[:8]}..., config_key={config_key}")

    user_data = _load_user_configs(user_token)
    configs = user_data.get("configs", {})

    # 无配置
    if not configs:
        return {
            "success": True,
            "configs": {},
            "server_timestamp": int(time.time()),
            "message": _("No config found"),
        }

    if config_key:
        # 只返回特定配置块
        if config_key in configs:
            return {
                "success": True,
                "config_key": config_key,
                "config_data": configs[config_key].get("data", {}),
                "updated_at": configs[config_key].get("updated_at", 0),
                "client_id": configs[config_key].get("client_id", ""),
                "platform": configs[config_key].get("platform", ""),
                "server_timestamp": int(time.time()),
            }
        else:
            return {
                "success": False,
                "config_key": config_key,
                "error": "Config key not found",
                "server_timestamp": int(time.time()),
            }
    else:
        # 返回所有配置
        return {
            "success": True,
            "configs": {k: v.get("data", {}) for k, v in configs.items()},
            "updated_at": user_data.get("updated_at", 0),
            "server_timestamp": int(time.time()),
            "message": f"Found {len(configs)} config keys",
        }


@app.delete("/api/config/sync")
async def sync_config_clear(
    user_token: str = Query(..., min_length=8, max_length=128),
    config_key: Optional[str] = Query(default=None, description="可选：只删除特定配置块"),
):
    """
    清除服务器上的配置

    - 不带 config_key：清除用户所有配置
    - 带 config_key：只清除该配置块
    """
    user_data = _load_user_configs(user_token)

    if config_key:
        if config_key in user_data.get("configs", {}):
            del user_data["configs"][config_key]
            _save_user_configs(user_token, user_data)
            return {"success": True, "config_key": config_key, "message": _("Config cleared")}
        return {"success": False, "error": "Config key not found"}
    else:
        # 清除所有配置
        user_data["configs"] = {}
        _save_user_configs(user_token, user_data)
        return {"success": True, "message": _("All configs cleared")}


@app.get("/api/config/keys")
async def sync_config_keys(
    user_token: str = Query(..., min_length=8, max_length=128),
):
    """
    查询用户已存储了哪些配置键
    """
    user_data = _load_user_configs(user_token)
    configs = user_data.get("configs", {})

    keys_info = []
    for k, v in configs.items():
        keys_info.append({
            "key": k,
            "updated_at": v.get("updated_at", 0),
            "platform": v.get("platform", ""),
            "client_id": v.get("client_id", ""),
        })

    return {
        "success": True,
        "keys": keys_info,
        "total": len(keys_info),
        "server_timestamp": int(time.time()),
    }


@app.post("/api/collect")
async def collect_data(request: CollectRequest, background_tasks: BackgroundTasks):
    """
    收集客户端周报数据

    设计：服务器不可用时客户端应能正常记录，稍后重试
    """
    logger.info(f"收到周报: week_id={request.week_id}, client={request.client_id}")

    data = load_weekly_data(request.week_id)

    report = {
        "client_id": request.client_id,
        "patches": request.patches,
        "pain_points": request.pain_points,
        "generated_at": request.generated_at,
        "client_version": request.client_version,
        "platform": request.platform,
        "received_at": int(time.time()),
    }

    # 更新或新增
    existing_clients = [r.get("client_id") for r in data.get("reports", [])]
    if request.client_id in existing_clients:
        for i, r in enumerate(data["reports"]):
            if r.get("client_id") == request.client_id:
                data["reports"][i] = report
                break
    else:
        data["reports"].append(report)

    save_weekly_data(request.week_id, data)
    background_tasks.add_task(run_aggregation, request.week_id)

    return {
        "success": True,
        "week_id": request.week_id,
        "client_id": request.client_id,
        "patch_count": len(request.patches),
        "pain_point_count": len(request.pain_points),
    }


@app.post("/api/heartbeat")
async def heartbeat(request: HeartbeatRequest):
    """心跳（轻量）"""
    logger.debug(f"心跳: client={request.client_id}")
    return {
        "success": True,
        "server_time": int(time.time()),
    }


# ========== 中继参数分发 ==========

@app.get("/api/relay/params")
async def get_relay_params():
    """
    获取中继参数

    客户端定期拉取，用于：
    1. 超时重试配置
    2. 批处理大小
    3. 心跳间隔
    """
    config = load_config()
    relay_config = config.get("relay", {})
    params = config.get("params", DEFAULT_CONFIG["params"])

    return {
        "relay_enabled": relay_config.get("relay_enabled", True),
        "offline_fallback": relay_config.get("offline_fallback", True),
        "params": params,
        "server_time": int(time.time()),
    }


@app.post("/api/relay/params")
async def update_relay_params(request: Dict[str, Any]):
    """
    更新中继参数（仅管理员）
    """
    config = load_config()
    if "params" in request:
        config["params"].update(request["params"])
    if "relay" in request:
        config["relay"].update(request["relay"])
    save_config(config)
    return {"success": True}


@app.get("/api/relay/config")
async def get_server_config():
    """获取服务器配置（公开部分）"""
    config = load_config()
    return {
        "relay_enabled": config.get("relay", {}).get("relay_enabled", True),
        "max_clients": config.get("server", {}).get("max_clients", 100),
    }


# ========== 统计数据 ==========

@app.get("/api/stats/overview")
async def get_overview_stats():
    """全局统计概览"""
    total_reports = 0
    total_clients = set()
    total_patches = 0

    for week_file in RAW_DIR.glob("weekly_*.json"):
        try:
            with open(week_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                reports = data.get("reports", [])
                total_reports += len(reports)
                for r in reports:
                    total_clients.add(r.get("client_id", ""))
                    total_patches += len(r.get("patches", []))
        except Exception:
            pass

    return {
        "total_weeks": len(list(RAW_DIR.glob("weekly_*.json"))),
        "total_reports": total_reports,
        "total_clients": len(total_clients),
        "total_patches": total_patches,
        "generated_at": int(time.time()),
    }


@app.get("/api/stats/trends")
async def get_trends(weeks: int = Query(default=4, ge=1, le=12)):
    """进化趋势"""
    trends = []
    now = datetime.now()

    for i in range(weeks):
        target_date = now - timedelta(weeks=i)
        iso_cal = target_date.isocalendar()
        week_id = f"{iso_cal[0]}-W{iso_cal[1]:02d}"

        agg_file = AGG_DIR / f"module_hits_{week_id}.json"

        if agg_file.exists():
            try:
                with open(agg_file, "r", encoding="utf-8") as f:
                    agg = json.load(f)
                    trends.append(agg)
            except Exception:
                trends.append({"week_id": week_id, "total_patches": 0, "active_clients": 0})
        else:
            trends.append({
                "week_id": week_id,
                "total_patches": 0,
                "total_pain_points": 0,
                "active_clients": 0,
            })

    trends.reverse()

    # 环比变化
    for i in range(1, len(trends)):
        prev = trends[i-1].get("total_patches", 0)
        curr = trends[i].get("total_patches", 0)
        if prev > 0:
            trends[i]["wow_change"] = round((curr - prev) / prev * 100, 2)
        else:
            trends[i]["wow_change"] = 0

    return {"trends": trends, "weeks": weeks, "generated_at": int(time.time())}


@app.get("/api/weekly/{week_id}")
async def get_weekly_data(week_id: str):
    """获取周数据"""
    data = load_weekly_data(week_id)
    if not data.get("reports"):
        raise HTTPException(status_code=404, detail="周数据不存在")
    return {
        "week_id": week_id,
        "report_count": len(data["reports"]),
        "reports": data["reports"],
    }


@app.get("/api/weekly/{week_id}/aggregate")
async def get_aggregated_data(week_id: str):
    """获取聚合数据"""
    agg_file = AGG_DIR / f"module_hits_{week_id}.json"
    if agg_file.exists():
        with open(agg_file, "r", encoding="utf-8") as f:
            return json.load(f)
    agg = aggregate_week(week_id)
    if not agg:
        raise HTTPException(status_code=404, detail="聚合数据不存在")
    return agg


@app.get("/api/weekly/{week_id}/raw")
async def download_raw_data(week_id: str):
    """下载原始数据"""
    data = load_weekly_data(week_id)
    if not data.get("reports"):
        raise HTTPException(status_code=404, detail="周数据不存在")
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=weekly_{week_id}.json"}
    )


# ========== Web 管理界面 ==========

@app.get("/")
async def landing_page():
    """项目首页"""
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "service": "Hermes Relay Server",
        "version": "2.0.0",
        "message": "Web界面未部署",
        "hint": "运行 python -m server.relay_server.web_dashboard 生成",
    }


@app.get("/web")
async def web_admin():
    """管理控制台"""
    admin_file = WEB_DIR / "admin.html"
    if admin_file.exists():
        return FileResponse(admin_file)
    return {"message": "管理界面未部署"}


@app.get("/web/{file_path:path}")
async def web_static(file_path: str):
    """Web静态资源"""
    file = WEB_DIR / file_path
    if file.exists() and file.is_file():
        return FileResponse(file)
    raise HTTPException(status_code=404, detail="File not found")


# ========== 管理 API（轻量） ==========

@app.get("/api/admin/stats")
async def admin_stats():
    """管理统计"""
    return await get_overview_stats()


@app.post("/api/admin/config")
async def admin_update_config(request: Dict[str, Any]):
    """更新服务器配置"""
    config = load_config()

    if "server" in request:
        config["server"].update(request["server"])
    if "relay" in request:
        config["relay"].update(request["relay"])
    if "params" in request:
        config["params"].update(request["params"])

    save_config(config)
    logger.info(f"配置已更新: {list(request.keys())}")

    return {"success": True, "updated": list(request.keys())}


@app.delete("/api/admin/data/{week_id}")
async def admin_delete_week_data(week_id: str):
    """删除指定周数据"""
    week_file = get_week_file(week_id)
    agg_file = AGG_DIR / f"module_hits_{week_id}.json"

    deleted = []
    if week_file.exists():
        week_file.unlink()
        deleted.append(str(week_file))
    if agg_file.exists():
        agg_file.unlink()
        deleted.append(str(agg_file))

    if not deleted:
        raise HTTPException(status_code=404, detail="数据不存在")

    return {"success": True, "deleted": deleted}


# ========== 启动 ==========

if __name__ == "__main__":
    import uvicorn

    config = load_config()
    server_config = config.get("server", {})

    uvicorn.run(
        app,
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8766),
        log_level="info",
    )
