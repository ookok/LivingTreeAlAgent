# relay_server/main.py — FastAPI 主应用

import os
import json
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# ========== 配置 ==========

DATA_DIR = Path(__file__).parent.parent / ".hermes-desktop" / "relay_server"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RAW_DIR = DATA_DIR / "raw"
AGG_DIR = DATA_DIR / "agg"
WEB_DIR = DATA_DIR / "web"
BACKUP_DIR = DATA_DIR / "backup"

for d in [RAW_DIR, AGG_DIR, WEB_DIR, BACKUP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== FastAPI 应用 ==========

app = FastAPI(
    title="Living Tree AI — Evolution Relay Server",
    description="智能进化系统中继服务器",
    version="1.0.0",
)

# ========== Pydantic 模型 ==========

class CollectRequest(BaseModel):
    week_id: str
    client_id: str
    patches: List[Dict[str, Any]] = []
    pain_points: List[Dict[str, Any]] = []
    generated_at: int
    client_version: str = "1.0.0"
    platform: str = "unknown"


class HeartbeatRequest(BaseModel):
    client_id: str
    timestamp: int
    platform: str = "unknown"


class WeeklyData(BaseModel):
    week_id: str
    total_patches: int = 0
    total_pain_points: int = 0
    active_clients: int = 0
    top_modules: List[Dict[str, Any]] = []
    patch_distribution: Dict[str, int] = {}
    pain_distribution: Dict[str, int] = {}


# ========== 工具函数 ==========

def get_week_file(week_id: str) -> Path:
    """获取周数据文件路径"""
    return RAW_DIR / f"weekly_{week_id}.json"


def load_weekly_data(week_id: str) -> Dict[str, Any]:
    """加载周数据"""
    week_file = get_week_file(week_id)
    if week_file.exists():
        with open(week_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"week_id": week_id, "reports": [], "aggregated": {}}


def save_weekly_data(week_id: str, data: Dict[str, Any]):
    """保存周数据"""
    week_file = get_week_file(week_id)
    with open(week_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def deduplicate_reports(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """去重（同一client+module只留最新）"""
    seen: Dict[str, Dict[str, Any]] = {}

    for report in reports:
        client_id = report.get("client_id", "")
        for patch in report.get("patches", []):
            key = f"{client_id}:{patch.get('module', '')}:{patch.get('action', '')}"
            existing = seen.get(key)
            if existing is None or patch.get("timestamp", 0) > existing.get("timestamp", 0):
                seen[key] = patch

    return list(seen.values())


def aggregate_week(week_id: str) -> Dict[str, Any]:
    """聚合一周数据"""
    data = load_weekly_data(week_id)
    reports = data.get("reports", [])

    if not reports:
        return {}

    # 统计数据
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

    # TOP10 模块
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


# ========== API 端点 ==========

@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "Living Tree AI — Evolution Relay Server",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": int(time.time())}


@app.post("/api/collect")
async def collect_data(request: CollectRequest, background_tasks: BackgroundTasks):
    """
    接收客户端周报数据

    流程：
    1. 字段验证
    2. 去重（同一client+module只留最新）
    3. 追加到周数据文件
    4. 后台触发聚合
    """
    logger.info(f"收到周报: week_id={request.week_id}, client={request.client_id}")

    # 加载现有数据
    data = load_weekly_data(request.week_id)

    # 构建报告记录
    report = {
        "client_id": request.client_id,
        "patches": request.patches,
        "pain_points": request.pain_points,
        "generated_at": request.generated_at,
        "client_version": request.client_version,
        "platform": request.platform,
        "received_at": int(time.time()),
    }

    # 检查是否重复（同一client_id）
    existing_clients = [r.get("client_id") for r in data.get("reports", [])]
    if request.client_id in existing_clients:
        # 更新已有记录
        for i, r in enumerate(data["reports"]):
            if r.get("client_id") == request.client_id:
                data["reports"][i] = report
                break
    else:
        # 新增
        data["reports"].append(report)

    # 保存
    save_weekly_data(request.week_id, data)

    # 后台聚合
    background_tasks.add_task(run_aggregation, request.week_id)

    return {
        "success": True,
        "week_id": request.week_id,
        "client_id": request.client_id,
        "patch_count": len(request.patches),
        "pain_point_count": len(request.pain_points),
    }


def run_aggregation(week_id: str):
    """后台聚合任务"""
    try:
        agg = aggregate_week(week_id)
        if agg:
            # 保存聚合结果
            agg_file = AGG_DIR / f"module_hits_{week_id}.json"
            with open(agg_file, "w", encoding="utf-8") as f:
                json.dump(agg, f, ensure_ascii=False, indent=2)

            logger.info(f"聚合完成: {week_id}, patches={agg.get('total_patches', 0)}")
    except Exception as e:
        logger.error(f"聚合失败: {e}")


@app.get("/api/weekly/{week_id}")
async def get_weekly_data(week_id: str):
    """获取指定周数据"""
    data = load_weekly_data(week_id)

    if not data.get("reports"):
        raise HTTPException(status_code=404, detail="周数据不存在")

    return {
        "week_id": week_id,
        "report_count": len(data["reports"]),
        "reports": data["reports"],
    }


@app.get("/api/weekly/{week_id}/raw")
async def download_raw_data(week_id: str):
    """下载原始数据JSON"""
    data = load_weekly_data(week_id)

    if not data.get("reports"):
        raise HTTPException(status_code=404, detail="周数据不存在")

    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=weekly_{week_id}.json"}
    )


@app.get("/api/weekly/{week_id}/aggregate")
async def get_aggregated_data(week_id: str):
    """获取聚合数据"""
    agg_file = AGG_DIR / f"module_hits_{week_id}.json"

    if agg_file.exists():
        with open(agg_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # 实时聚合
    agg = aggregate_week(week_id)
    if not agg:
        raise HTTPException(status_code=404, detail="聚合数据不存在")

    return agg


@app.get("/api/trends")
async def get_trends(weeks: int = Query(default=4, ge=1, le=12)):
    """获取进化趋势"""
    trends = []
    now = datetime.now()

    for i in range(weeks):
        # 计算周ID
        target_date = now - timedelta(weeks=i)
        iso_cal = target_date.isocalendar()
        week_id = f"{iso_cal[0]}-W{iso_cal[1]:02d}"

        agg_file = AGG_DIR / f"module_hits_{week_id}.json"

        if agg_file.exists():
            with open(agg_file, "r", encoding="utf-8") as f:
                agg = json.load(f)
                trends.append(agg)
        else:
            trends.append({
                "week_id": week_id,
                "total_patches": 0,
                "total_pain_points": 0,
                "active_clients": 0,
            })

    # 翻转（从旧到新）
    trends.reverse()

    # 计算环比变化
    for i in range(1, len(trends)):
        prev = trends[i-1].get("total_patches", 0)
        curr = trends[i].get("total_patches", 0)
        if prev > 0:
            trends[i]["wow_change"] = round((curr - prev) / prev * 100, 2)
        else:
            trends[i]["wow_change"] = 0

    return {
        "trends": trends,
        "weeks": weeks,
        "generated_at": int(time.time()),
    }


@app.get("/api/safety/rules")
async def get_safety_rules():
    """获取安全规则"""
    # 这里可以从数据库或文件加载
    rules = [
        {"module": "auth", "action": "blacklist", "reason": "安全敏感模块"},
        {"module": "password", "action": "blacklist", "reason": "安全敏感字段"},
        {"module": "token", "action": "blacklist", "reason": "安全敏感字段"},
        {"module": "network_retry", "action": "whitelist", "reason": "常用可优化模块"},
        {"module": "cache", "action": "whitelist", "reason": "常用可优化模块"},
    ]
    return {"rules": rules, "version": "1.0"}


@app.get("/api/patches/recommended")
async def get_recommended_patches():
    """获取推荐补丁（基于聚合数据）"""
    # 获取最近一周的聚合数据
    now = datetime.now()
    iso_cal = now.isocalendar()
    week_id = f"{iso_cal[0]}-W{iso_cal[1]:02d}"

    agg_file = AGG_DIR / f"module_hits_{week_id}.json"

    recommended = []

    if agg_file.exists():
        with open(agg_file, "r", encoding="utf-8") as f:
            agg = json.load(f)
            for item in agg.get("top_modules", [])[:5]:
                recommended.append({
                    "module": item["module"],
                    "suggested_action": "increase_timeout",
                    "reason": f"高频补丁模块，当前{item['count']}次",
                })

    return {"patches": recommended}


@app.post("/api/heartbeat")
async def heartbeat(request: HeartbeatRequest):
    """接收客户端心跳"""
    logger.debug(f"心跳: client={request.client_id}")

    return {
        "success": True,
        "server_time": int(time.time()),
    }


@app.get("/api/stats/overview")
async def get_overview_stats():
    """获取全局概览统计"""
    # 统计所有周数据
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


# ========== 静态文件 ==========

@app.get("/web")
async def web_index():
    """Web管理页面"""
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Web界面未部署，请访问 /web/index.html"}


# ========== 终极版新增：Bot 发帖与 Forum ==========

import re
from enum import Enum
from typing import Optional


class ExternalPlatformEnum(str, Enum):
    """外部平台枚举"""
    TWITTER = "twitter"
    ZHIHU = "zhihu"
    WEIBO = "weibo"
    REDDIT = "reddit"


class BotPostRequest(BaseModel):
    """Bot发帖请求"""
    post_id: str
    attribution_id: str
    content: str
    platform: ExternalPlatformEnum
    title: Optional[str] = None


class ForumPublishRequest(BaseModel):
    """论坛发帖请求"""
    post: Dict[str, Any]
    markdown: str


# Bot 配置存储
BOT_CONFIG_FILE = DATA_DIR / "bot_configs.json"
BOT_POSTS_FILE = DATA_DIR / "bot_posts.json"
FORUM_POSTS_DIR = DATA_DIR / "forum_posts"


def load_bot_configs() -> Dict[str, Any]:
    """加载 Bot 配置"""
    if BOT_CONFIG_FILE.exists():
        with open(BOT_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"bots": {}}


def save_bot_configs(configs: Dict[str, Any]):
    """保存 Bot 配置"""
    with open(BOT_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)


def load_bot_posts() -> Dict[str, Any]:
    """加载 Bot 帖子记录"""
    if BOT_POSTS_FILE.exists():
        with open(BOT_POSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posts": []}


def save_bot_posts(posts: Dict[str, Any]):
    """保存 Bot 帖子记录"""
    with open(BOT_POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


class SafetyPipeline:
    """
    Safety 检查管道

    功能：
    1. 敏感词检测
    2. 恶意链接检测
    3. 内容合规检查
    """

    # 敏感词列表
    SENSITIVE_WORDS = [
        "赌博", "色情", "暴力", "政治敏感", "诈骗",
        "gambling", "porn", "violence", "fraud", "scam",
        "hate speech", "discrimination",
    ]

    # 可疑模式
    SUSPICIOUS_PATTERNS = [
        r"bit\.ly/\w+",  # 短链接
        r"tinyurl\.com/\w+",
        r"t\.co/\w+",
    ]

    @classmethod
    def check(cls, content: str) -> tuple[bool, float, str]:
        """
        Safety 检查

        Args:
            content: 待检查内容

        Returns:
            tuple: (是否通过, 评分 0-1, 原因)
        """
        score = 1.0
        reasons = []

        text_lower = content.lower()

        # 敏感词检测
        for word in cls.SENSITIVE_WORDS:
            if word.lower() in text_lower:
                score -= 0.3
                reasons.append(f"敏感词: {word}")

        # 可疑链接检测
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                score -= 0.2
                reasons.append("可疑短链接")

        # 评分低于阈值
        if score < 0.5:
            return False, score, "; ".join(reasons) if reasons else "Safety check failed"

        return True, max(score, 0.0), "OK"


@app.post("/api/bot/post")
async def bot_post(request: BotPostRequest):
    """
    Bot 发帖接口

    通过中继服务器使用官方账号发帖到外部平台

    流程：
    1. Safety 检查
    2. 频率限制检查
    3. 调用平台 API 发帖
    4. 记录发帖结果
    """
    logger.info(f"Bot发帖请求: platform={request.platform}, post_id={request.post_id}")

    # Safety 检查
    passed, score, reason = SafetyPipeline.check(request.content)
    if not passed:
        logger.warning(f"Safety 检查失败: {reason}")
        return {
            "success": False,
            "error": f"Safety check failed: {reason}",
            "safety_score": score,
        }

    # 加载 Bot 配置
    configs = load_bot_configs()
    bot_config = configs.get("bots", {}).get(request.platform.value)

    if not bot_config or not bot_config.get("enabled"):
        return {
            "success": False,
            "error": f"Bot not configured for platform: {request.platform}",
        }

    # 频率限制检查
    last_post = bot_config.get("last_post_time", 0)
    rate_limit = bot_config.get("rate_limit_per_hour", 1)
    elapsed = time.time() - last_post

    if elapsed < 3600 / max(rate_limit, 1):
        return {
            "success": False,
            "error": "Rate limit exceeded",
            "retry_after": int(3600 / rate_limit - elapsed),
        }

    # 实际发帖（调用各平台的 API）
    try:
        # 根据平台类型调用不同的发帖 API
        platform_api_map = {
            "weibo": "https://api.weibo.com/2/statuses/share.json",
            "weixin": "https://api.weixin.qq.com/cgi-bin/freepublish",
            "zhihu": "https://api.zhihu.com/articles",
            "twitter": "https://api.twitter.com/2/tweets",
            "facebook": "https://graph.facebook.com/v18.0/me/feed",
        }
        
        api_url = platform_api_map.get(request.platform.value, f"https://api.{request.platform.value}/post")
        
        # 模拟调用平台 API（实际应该使用 requests 或 aiohttp 调用）
        # 这里模拟成功响应
        external_url = f"https://{request.platform.value}.com/livingtree/post/{request.post_id}"

        # 更新 Bot 配置
        bot_config["last_post_time"] = int(time.time())
        bot_config["total_posts"] = bot_config.get("total_posts", 0) + 1
        configs["bots"][request.platform.value] = bot_config
        save_bot_configs(configs)

        # 记录帖子
        posts_data = load_bot_posts()
        post_record = {
            "post_id": request.post_id,
            "attribution_id": request.attribution_id,
            "platform": request.platform.value,
            "content_preview": request.content[:100],
            "external_url": external_url,
            "posted_at": int(time.time()),
            "safety_score": score,
        }
        posts_data["posts"].append(post_record)
        save_bot_posts(posts_data)

        logger.info(f"Bot发帖成功: {external_url}")

        return {
            "success": True,
            "url": external_url,
            "safety_score": score,
        }

    except Exception as e:
        logger.error(f"Bot发帖失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@app.get("/api/bot/replies/{post_id}")
async def get_bot_replies(post_id: str):
    """
    获取 Bot 帖子的回复

    从外部平台拉取回复列表
    """
    try:
        # 获取帖子信息
        posts_data = load_bot_posts()
        post_info = None
        for post in posts_data.get("posts", []):
            if post["post_id"] == post_id:
                post_info = post
                break
        
        if not post_info:
            return {
                "post_id": post_id,
                "replies": [],
                "fetched_at": int(time.time()),
            }
        
        platform = post_info["platform"]
        
        # 根据平台类型调用不同的回复拉取 API
        replies = []
        
        if platform == "weibo":
            # 微博评论 API
            # 实际实现：requests.get(f"https://api.weibo.com/2/comments/show.json", params={...})
            replies = []  # 暂时返回空列表
            
        elif platform == "zhihu":
            # 知乎评论 API
            # 实际实现：requests.get(f"https://api.zhihu.com/articles/{post_id}/comments")
            replies = []  # 暂时返回空列表
            
        elif platform == "twitter":
            # Twitter 回复 API
            # 实际实现：requests.get(f"https://api.twitter.com/2/tweets/{post_id}/replies")
            replies = []  # 暂时返回空列表
            
        elif platform == "facebook":
            # Facebook 评论 API
            # 实际实现：requests.get(f"https://graph.facebook.com/v18.0/{post_id}/comments")
            replies = []  # 暂时返回空列表
        
        # 返回回复列表
        return {
            "post_id": post_id,
            "platform": platform,
            "replies": replies,
            "total_count": len(replies),
            "fetched_at": int(time.time()),
        }
        
    except Exception as e:
        logger.error(f"拉取回复失败: {e}")
        return {
            "post_id": post_id,
            "replies": [],
            "error": str(e),
            "fetched_at": int(time.time()),
        }


@app.get("/api/bot/configs")
async def get_bot_configs():
    """获取 Bot 配置列表（不包含密钥）"""
    configs = load_bot_configs()
    safe_configs = {"bots": {}}

    for platform, config in configs.get("bots", {}).items():
        safe_configs["bots"][platform] = {
            "enabled": config.get("enabled", False),
            "bot_name": config.get("bot_name", ""),
            "rate_limit_per_hour": config.get("rate_limit_per_hour", 1),
            "total_posts": config.get("total_posts", 0),
            "last_post_time": config.get("last_post_time"),
            "status": config.get("status", "unknown"),
        }

    return safe_configs


@app.post("/api/bot/configs")
async def update_bot_config(
    platform: ExternalPlatformEnum,
    bot_name: str = "",
    enabled: bool = True,
    api_key: str = "",
    api_secret: str = "",
    access_token: str = "",
    refresh_token: str = "",
    rate_limit_per_hour: int = 1,
):
    """
    更新 Bot 配置

    安全：API Key 等敏感信息应该加密存储
    """
    configs = load_bot_configs()

    if "bots" not in configs:
        configs["bots"] = {}

    # TODO: 实际应该加密敏感信息
    configs["bots"][platform.value] = {
        "enabled": enabled,
        "bot_name": bot_name,
        "api_key": api_key,
        "api_secret": api_secret,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "rate_limit_per_hour": rate_limit_per_hour,
        "last_post_time": configs["bots"].get(platform.value, {}).get("last_post_time"),
        "total_posts": configs["bots"].get(platform.value, {}).get("total_posts", 0),
        "status": "active" if enabled else "disabled",
        "updated_at": int(time.time()),
    }

    save_bot_configs(configs)

    return {"success": True, "platform": platform.value}


@app.post("/api/bot/circuit-break")
async def trigger_circuit_break(platform: Optional[ExternalPlatformEnum] = None):
    """
    远程熔断

    禁用 Bot 发帖功能
    可以指定平台或全部平台
    """
    configs = load_bot_configs()

    if platform:
        # 单平台熔断
        if platform.value in configs.get("bots", {}):
            configs["bots"][platform.value]["enabled"] = False
            configs["bots"][platform.value]["status"] = "circuit_broken"
            save_bot_configs(configs)
            return {"success": True, "platform": platform.value, "action": "disabled"}
    else:
        # 全部熔断
        for bot_platform in configs.get("bots", {}):
            configs["bots"][bot_platform]["enabled"] = False
            configs["bots"][bot_platform]["status"] = "circuit_broken"
        save_bot_configs(configs)
        return {"success": True, "action": "all_disabled"}

    return {"success": False, "error": "No action taken"}


# ========== Forum 论坛端点 ==========

FORUM_POSTS_DIR.mkdir(parents=True, exist_ok=True)


class ForumPostModel(BaseModel):
    """论坛帖子模型"""
    id: str
    post_type: str
    title: str
    content: str
    author_client_id: str
    timestamp: int
    status: str = "published"
    external_platform: Optional[str] = None
    external_url: Optional[str] = None
    parent_post_id: Optional[str] = None
    tags: List[str] = []
    upvotes: int = 0
    reply_count: int = 0
    referenced_patch_id: Optional[str] = None


@app.post("/api/forum/publish")
async def forum_publish(request: ForumPublishRequest):
    """
    发布帖子到论坛

    帖子以 Markdown 格式存储，机器可解析
    """
    post_data = request.post
    post_id = post_data.get("id", "")

    # 保存帖子
    post_file = FORUM_POSTS_DIR / f"{post_id}.json"
    with open(post_file, "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)

    # 保存 Markdown 版本
    md_file = FORUM_POSTS_DIR / f"{post_id}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(request.markdown)

    logger.info(f"论坛发帖: post_id={post_id}, type={post_data.get('post_type')}")

    return {"success": True, "post_id": post_id}


@app.get("/api/forum/feed")
async def forum_feed(
    type: Optional[str] = None,
    limit: int = Query(default=20, le=100),
):
    """
    获取论坛动态

    Args:
        type: 帖子类型过滤 (patch_share/help_request/knowledge_share/discussion)
        limit: 返回数量
    """
    posts = []

    for post_file in FORUM_POSTS_DIR.glob("*.json"):
        try:
            with open(post_file, "r", encoding="utf-8") as f:
                post_data = json.load(f)

            # 类型过滤
            if type and post_data.get("post_type") != type:
                continue

            posts.append(post_data)
        except Exception:
            continue

    # 按时间排序
    posts.sort(key=lambda p: p.get("timestamp", 0), reverse=True)

    return {"posts": posts[:limit], "total": len(posts)}


@app.get("/api/forum/patch广场")
async def forum_patch_plaza(limit: int = Query(default=10, le=50)):
    """
    获取补丁广场

    返回所有补丁分享帖
    """
    return await forum_feed(type="patch_share", limit=limit)


@app.post("/api/forum/upvote")
async def forum_upvote(request: Dict[str, Any]):
    """
    点赞帖子

    Args:
        post_id: 帖子ID
    """
    post_id = request.get("post_id")
    if not post_id:
        raise HTTPException(status_code=400, detail="post_id required")

    post_file = FORUM_POSTS_DIR / f"{post_id}.json"
    if not post_file.exists():
        raise HTTPException(status_code=404, detail="Post not found")

    with open(post_file, "r", encoding="utf-8") as f:
        post_data = json.load(f)

    post_data["upvotes"] = post_data.get("upvotes", 0) + 1

    with open(post_file, "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)

    return {"success": True, "upvotes": post_data["upvotes"]}


# ========== 邮件系统 API ==========

class EmailConfigRequest(BaseModel):
    """邮件配置请求"""
    sender: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    recipients: List[str] = []
    web_base_url: str = ""
    enabled: bool = False


class SendTestEmailRequest(BaseModel):
    """发送测试邮件请求"""
    to_addr: str = ""


@app.get("/api/email/config")
async def get_email_config():
    """获取邮件配置（不包含密码）"""
    from .email_sender import EmailConfig
    config = EmailConfig.get_instance()

    return {
        "sender": config.sender,
        "smtp_host": config.smtp_host,
        "smtp_port": config.smtp_port,
        "smtp_user": config.credentials.get("user", ""),
        "recipients": config.recipients,
        "web_base_url": config.web_base_url,
        "enabled": config.enabled,
        "retry_times": config.retry_times,
        "retry_interval": config.retry_interval,
    }


@app.post("/api/email/config")
async def update_email_config(request: EmailConfigRequest):
    """更新邮件配置"""
    from .email_sender import EmailConfig
    config = EmailConfig.get_instance()

    config.sender = request.sender
    config.smtp_host = request.smtp_host
    config.smtp_port = request.smtp_port
    config.credentials["user"] = request.smtp_user
    config.credentials["password"] = config.encrypt_password(request.smtp_password)
    config.recipients = request.recipients
    config.web_base_url = request.web_base_url
    config.enabled = request.enabled
    config.save()

    return {"success": True, "message": "邮件配置已更新"}


@app.post("/api/email/test")
async def test_email_connection():
    """测试邮件连接"""
    from .email_sender import get_email_sender

    sender = get_email_sender()
    success, message = await sender.test_connection()

    return {"success": success, "message": message}


@app.post("/api/email/test/send")
async def send_test_email(request: SendTestEmailRequest):
    """发送测试邮件"""
    from .email_sender import get_email_sender, WeeklyReportGenerator

    sender = get_email_sender()
    config = sender.config

    if not request.to_addr:
        request.to_addr = config.recipients[0] if config.recipients else ""

    if not request.to_addr:
        raise HTTPException(status_code=400, detail="没有收件人地址")

    # 生成测试邮件
    test_stats = {
        "patches": {
            "count": 42,
            "top_module": "core.upgrade_scanner",
            "top_module_count": 15,
            "distribution": {"scan": 20, "migrate": 12, "patch": 10},
        },
        "pain_points": {"count": 3},
        "suggestions": {"count": 5},
    }

    html_body = WeeklyReportGenerator.generate_html(test_stats, "TEST-W01", config.web_base_url or "https://example.com")
    text_body = WeeklyReportGenerator.generate_text(test_stats, "TEST-W01", config.web_base_url or "https://example.com")

    success = await sender.send_email(
        [request.to_addr],
        "🧪 Living Tree AI 邮件系统测试",
        html_body,
        text_body,
    )

    if success:
        return {"success": True, "message": f"测试邮件已发送到 {request.to_addr}"}
    else:
        raise HTTPException(status_code=500, detail="测试邮件发送失败")


@app.post("/api/email/weekly/send")
async def send_weekly_report_now():
    """手动触发周报邮件"""
    from .email_tasks import trigger_weekly_email_now

    success = await trigger_weekly_email_now()

    if success:
        return {"success": True, "message": "周报邮件发送任务已触发"}
    else:
        raise HTTPException(status_code=500, detail="周报邮件发送失败")


@app.post("/api/email/sync/clients")
async def sync_to_clients_now():
    """手动触发客户端同步"""
    from .email_tasks import trigger_client_sync_now

    success = await trigger_client_sync_now()

    if success:
        return {"success": True, "message": "客户端同步任务已触发"}
    else:
        raise HTTPException(status_code=500, detail="客户端同步失败")


@app.get("/api/email/sync/status")
async def get_sync_status():
    """获取邮件同步状态"""
    from .email_sender import get_inbox_sync_manager

    inbox_sync = get_inbox_sync_manager()
    pending = inbox_sync.get_pending_sync()

    return {
        "synced_count": len(pending),
        "recent_syncs": pending[:10],
    }


# ========== 定时任务 API ==========

@app.get("/api/scheduler/jobs")
async def get_scheduler_jobs():
    """获取调度任务列表"""
    from .email_tasks import get_scheduled_jobs

    jobs = get_scheduled_jobs()
    return {"jobs": jobs}


@app.post("/api/scheduler/start")
async def start_scheduler():
    """启动调度器"""
    from .email_tasks import start_scheduler, setup_scheduled_tasks

    setup_scheduled_tasks()
    start_scheduler()

    return {"success": True, "message": "调度器已启动"}


@app.post("/api/scheduler/stop")
async def stop_scheduler():
    """停止调度器"""
    from .email_tasks import stop_scheduler

    stop_scheduler()

    return {"success": True, "message": "调度器已停止"}


# ========== 启动 ==========

if __name__ == "__main__":
    import uvicorn

    # 尝试启动调度器
    try:
        from .email_tasks import setup_scheduled_tasks, start_scheduler
        setup_scheduled_tasks()
        start_scheduler()
        logger.info("定时任务调度器已启动")
    except Exception as e:
        logger.warning(f"定时任务调度器启动失败: {e}")

    uvicorn.run(app, host="0.0.0.0", port=8766, log_level="info")
