# -*- coding: utf-8 -*-
"""
深度搜索全链路测试
==================
测试流程：
  Phase 0 - 系统参数配置
  Phase 1 - L0 SmolLM2 快反大脑初始化（本地 GGUF）
  Phase 2 - L3 标准模型初始化（qwen3.5:2b @ Ollama）
  Phase 3 - L4 增强模型初始化（qwen3.6:latest @ Ollama）
  Phase 4 - 路由决策（L0 分析用户 query）
  Phase 5 - 深度搜索执行（DeepSearchWikiSystem）
  Phase 6 - 结果汇总输出

测试问题：南京溧水养猪场环评报告
"""

import sys
import os
import asyncio
import time
import json
import logging
import re
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Windows 控制台 UTF-8 编码修复
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ["PYTHONUTF8"] = "1"

# ── 添加项目根目录到 sys.path ────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "client" / "src"))

# ── 日志配置 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("deep_search_test")

# ─────────────────────────────────────────────────────────────────────────────
#  测试配置
# ─────────────────────────────────────────────────────────────────────────────
TEST_QUERY = "南京溧水养猪场环评报告"

# L0 SmolLM2 配置（本地 GGUF 文件）
L0_MODEL_DIR = ROOT / "models"           # models/ 文件夹
L0_OLLAMA_HOST = "http://localhost:11434"
L0_MODEL_NAME = "smollm2-test"           # 注册到 Ollama 的名称

# L3 模型配置
L3_OLLAMA_HOST = "http://localhost:11434"
L3_MODEL_NAME = "qwen3.5:2b"

# L4 模型配置
L4_OLLAMA_HOST = "http://localhost:11434"
L4_MODEL_NAME = "qwen3.6:latest"


# ─────────────────────────────────────────────────────────────────────────────
#  辅助：打印带边框的标题
# ─────────────────────────────────────────────────────────────────────────────
def section(title: str, width: int = 70):
    line = "═" * width
    print(f"\n╔{line}╗")
    print(f"║  {title:<{width - 2}}║")
    print(f"╚{line}╝")


def log_step(step: str, status: str = "INFO", msg: str = ""):
    icon = {"OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "INFO": "ℹ️ ", "RUN": "🔄"}.get(status, "  ")
    print(f"  {icon} [{step}] {msg}")


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 0 - 系统参数配置
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SystemConfig:
    """系统全局配置"""
    l0_model_dir: Path = L0_MODEL_DIR
    l0_ollama_host: str = L0_OLLAMA_HOST
    l0_model_name: str = L0_MODEL_NAME

    l3_ollama_host: str = L3_OLLAMA_HOST
    l3_model_name: str = L3_MODEL_NAME

    l4_ollama_host: str = L4_OLLAMA_HOST
    l4_model_name: str = L4_MODEL_NAME

    search_max_results: int = 10
    deep_search_enabled: bool = True


def phase0_system_config() -> SystemConfig:
    section("Phase 0 · 系统参数配置")
    cfg = SystemConfig()

    # 检查 models 目录
    gguf_files = list(cfg.l0_model_dir.glob("*.gguf")) if cfg.l0_model_dir.exists() else []
    log_step("L0 模型目录", "OK" if gguf_files else "WARN",
             f"{cfg.l0_model_dir}  →  找到 {len(gguf_files)} 个 .gguf 文件")
    for f in gguf_files:
        log_step("  GGUF", "INFO", f.name)

    log_step("L0 Ollama", "INFO", f"{cfg.l0_ollama_host}  model={cfg.l0_model_name}")
    log_step("L3 Ollama", "INFO", f"{cfg.l3_ollama_host}  model={cfg.l3_model_name}")
    log_step("L4 Ollama", "INFO", f"{cfg.l4_ollama_host}  model={cfg.l4_model_name}")
    log_step("测试 Query", "INFO", f'"{TEST_QUERY}"')

    return cfg


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 1 - L0 SmolLM2 初始化
# ─────────────────────────────────────────────────────────────────────────────
class L0SmolLM2Client:
    """
    L0 SmolLM2 客户端
    自动扫描 models/ 目录下的 .gguf 文件，
    注册到本地 Ollama，并提供 classify() 意图分类接口。
    """

    def __init__(self, cfg: SystemConfig):
        self.cfg = cfg
        self.model_name = cfg.l0_model_name
        self.ollama_host = cfg.l0_ollama_host
        self.gguf_path: Optional[Path] = None
        self._ready = False

    # ── 查找 GGUF ─────────────────────────────────────────────────────────────
    def _find_gguf(self) -> Optional[Path]:
        """优先找 SmolLM2 相关 gguf，找不到则取第一个"""
        if not self.cfg.l0_model_dir.exists():
            return None
        for pat in ["*smollm2*.gguf", "*smol*.gguf", "*.gguf"]:
            files = list(self.cfg.l0_model_dir.glob(pat))
            if files:
                return files[0]
        return None

    # ── 检查 Ollama 是否已有模型 ───────────────────────────────────────────────
    async def _model_exists_in_ollama(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.ollama_host}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    return any(self.model_name in m for m in models)
        except Exception:
            pass
        return False

    # ── 创建 Modelfile 并注册到 Ollama ────────────────────────────────────────
    async def _register_to_ollama(self) -> bool:
        if self.gguf_path is None:
            return False
        system_prompt = (
            "你是一个轻量级意图分类器。对用户输入进行快速分类，"
            "输出JSON：{\"route\": \"search\", \"intent\": \"search_query\", "
            "\"reason\": \"原因\", \"confidence\": 0.9}"
        )
        modelfile_content = (
            f"FROM {self.gguf_path.as_posix()}\n\n"
            f"PARAMETER num_ctx 2048\n"
            f"PARAMETER temperature 0.1\n\n"
            f'SYSTEM """{system_prompt}"""\n'
        )
        tmp_modelfile = Path(os.environ.get("TEMP", "/tmp")) / "SmolLM2_Modelfile"
        tmp_modelfile.write_text(modelfile_content, encoding="utf-8")

        try:
            import subprocess
            result = subprocess.run(
                ["ollama", "create", self.model_name, "-f", str(tmp_modelfile)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                log_step("Ollama Create", "OK", f"模型 {self.model_name} 注册成功")
                return True
            else:
                log_step("Ollama Create", "WARN",
                         f"注册失败（{result.stderr.strip()[:100]}），将尝试直接调用")
                return False
        except FileNotFoundError:
            log_step("Ollama CLI", "WARN", "未找到 ollama 命令，跳过注册")
            return False
        except Exception as e:
            log_step("Ollama Create", "WARN", str(e))
            return False

    # ── 初始化 ────────────────────────────────────────────────────────────────
    async def init(self) -> bool:
        section("Phase 1 · L0 SmolLM2 快反大脑初始化")

        self.gguf_path = self._find_gguf()
        if self.gguf_path:
            log_step("GGUF 文件", "OK", str(self.gguf_path))
        else:
            log_step("GGUF 文件", "WARN",
                     f"未在 {self.cfg.l0_model_dir} 找到 .gguf 文件，将使用规则路由兜底")

        # 检查 Ollama 服务可用性
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.ollama_host}/api/version")
                ollama_ok = resp.status_code == 200
        except Exception:
            ollama_ok = False

        if not ollama_ok:
            log_step("Ollama 服务", "WARN", f"{self.ollama_host} 不可达，L0 将使用规则路由")
            self._ready = False
            return False

        log_step("Ollama 服务", "OK", f"{self.ollama_host}")

        if self.gguf_path and not await self._model_exists_in_ollama():
            log_step("模型注册", "RUN", f"注册 {self.model_name} 到 Ollama...")
            await self._register_to_ollama()

        model_ready = await self._model_exists_in_ollama()
        if model_ready:
            log_step("L0 模型", "OK", f"{self.model_name} 已就绪")
            self._ready = True
        else:
            log_step("L0 模型", "WARN", "Ollama 中暂无模型，使用规则路由")
            self._ready = False

        return self._ready

    # ── 意图分类（核心接口）──────────────────────────────────────────────────
    async def classify(self, query: str) -> Dict[str, Any]:
        """使用 SmolLM2 分类意图；若不可用则降级到规则引擎"""
        if self._ready:
            result = await self._classify_via_ollama(query)
            if result:
                return result

        # 规则兜底
        return self._classify_by_rules(query)

    async def _classify_via_ollama(self, query: str) -> Optional[Dict[str, Any]]:
        classify_prompt = (
            "用户输入：" + query + "\n\n"
            "判断路由（cache/local/search/heavy/human）和意图类型，"
            "只输出JSON，不要其他内容。"
        )
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={"model": self.model_name, "prompt": classify_prompt, "stream": False,
                          "options": {"num_predict": 80, "temperature": 0.1}},
                )
                if resp.status_code == 200:
                    text = resp.json().get("response", "")
                    m = re.search(r'\{[^}]+\}', text, re.DOTALL)
                    if m:
                        data = json.loads(m.group())
                        return {
                            "route": data.get("route", "heavy"),
                            "intent": data.get("intent", "unknown"),
                            "reason": data.get("reason", "SmolLM2 分类"),
                            "confidence": float(data.get("confidence", 0.7)),
                            "model": self.model_name,
                            "via": "smollm2_ollama",
                        }
        except Exception as e:
            logger.debug(f"SmolLM2 Ollama 调用失败: {e}")
        return None

    def _classify_by_rules(self, query: str) -> Dict[str, Any]:
        """规则路由引擎（兜底）"""
        q = query.lower()

        # FAST patterns
        if re.match(r'^(你好|您好|嗨|hi|hello|hey)[\s,，.!]*$', q):
            return {"route": "local", "intent": "greeting", "confidence": 0.95,
                    "reason": "规则命中：问候语", "via": "rules"}

        # HEAVY patterns
        heavy_patterns = [
            (r'(写|创作|生成).{10,}?(文章|报告|方案)', "heavy", "long_writing"),
            (r'(分析|评估|对比).{10,}?(市场|竞品|趋势)', "heavy", "analysis"),
        ]
        for pat, route, intent in heavy_patterns:
            if re.search(pat, q):
                return {"route": route, "intent": intent, "confidence": 0.88,
                        "reason": f"规则命中重型模式：{pat[:20]}", "via": "rules"}

        # 包含环评/报告/查询/搜索等关键词 → search/heavy
        search_keywords = ["环评", "报告", "养猪", "环境", "审批", "政府", "公示",
                           "查询", "搜索", "帮我查", "最新", "数据"]
        if any(kw in q for kw in search_keywords):
            return {"route": "search", "intent": "search_query", "confidence": 0.82,
                    "reason": f"规则命中搜索关键词：含 {[kw for kw in search_keywords if kw in q][:3]}",
                    "via": "rules"}

        # 默认 heavy
        return {"route": "heavy", "intent": "unknown", "confidence": 0.5,
                "reason": "规则兜底：默认重型推理", "via": "rules"}


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 2 - L3 标准模型（qwen3.5:2b）
# ─────────────────────────────────────────────────────────────────────────────
class L3OllamaClient:
    """L3 标准模型客户端 - 直接调用 Ollama API"""

    def __init__(self, cfg: SystemConfig):
        self.host = cfg.l3_ollama_host
        self.model = cfg.l3_model_name
        self._ready = False

    async def init(self) -> bool:
        section("Phase 2 · L3 标准模型初始化")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.host}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    model_loaded = any(self.model in m for m in models)
                    log_step("Ollama 服务", "OK", self.host)
                    if model_loaded:
                        log_step("L3 模型", "OK", f"{self.model} 已加载")
                        self._ready = True
                    else:
                        log_step("L3 模型", "WARN",
                                 f"{self.model} 未在 Ollama 中找到，可用模型: {models[:5]}")
                        # 仍然尝试调用，让 Ollama 自动拉取
                        self._ready = True
        except Exception as e:
            log_step("L3 初始化", "ERR", str(e))
        return self._ready

    async def generate(self, messages: List[Dict], max_tokens: int = 800) -> str:
        """调用 Ollama chat API"""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.host}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    },
                )
                if resp.status_code == 200:
                    return resp.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.warning(f"L3 generate 失败: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3 - L4 增强模型（qwen3.6:latest）
# ─────────────────────────────────────────────────────────────────────────────
class L4OllamaClient:
    """L4 增强模型客户端 - 直接调用 Ollama API，支持深度搜索增强"""

    def __init__(self, cfg: SystemConfig):
        self.host = cfg.l4_ollama_host
        self.model = cfg.l4_model_name
        self._ready = False

    async def init(self) -> bool:
        section("Phase 3 · L4 增强模型初始化")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.host}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    model_loaded = any(self.model in m for m in models)
                    log_step("Ollama 服务", "OK", self.host)
                    if model_loaded:
                        log_step("L4 模型", "OK", f"{self.model} 已加载")
                        self._ready = True
                    else:
                        log_step("L4 模型", "WARN",
                                 f"{self.model} 未在 Ollama 中找到，可用模型: {models[:5]}")
                        self._ready = True
        except Exception as e:
            log_step("L4 初始化", "ERR", str(e))
        return self._ready

    async def generate_with_context(
        self,
        query: str,
        search_context: str,
        max_tokens: int = 1200,
    ) -> str:
        """
        使用检索增强上下文调用 L4 模型。
        兼容 Qwen3 思考模型（content 为空时从 thinking 字段取回答）。
        使用 /no_think 指令关闭链式思考以加快响应。
        """
        system_msg = (
            "你是一个专业的环境评估与法规顾问，擅长处理环境影响评价（环评）相关问题。"
            "请根据提供的参考资料，给出详尽、专业的回答。/no_think"
        )
        user_content = (
            f"用户问题：{query}\n\n"
            f"参考资料（来自深度搜索）：\n{search_context}\n\n"
            f"请基于参考资料，给出专业、结构化的回答。 /no_think"
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{self.host}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data.get("message", {})
                    content = msg.get("content", "").strip()
                    # Qwen3 思考模型：content 可能为空，真实回答在 thinking 字段最后部分
                    # 或通过 stream 模式获取。这里优先取 content，无则取 thinking
                    if not content:
                        thinking = msg.get("thinking", "")
                        if thinking:
                            # thinking 字段包含思考过程+最终答案，尝试取最后段落
                            parts = thinking.strip().rsplit("\n\n", 1)
                            content = parts[-1].strip() if parts else thinking.strip()
                            log_step("L4 思考模式", "INFO",
                                     f"content 为空，从 thinking 提取，共 {len(thinking)} 字")
                    return content
        except Exception as e:
            logger.warning(f"L4 generate 失败: {e}")
        return ""

    async def generate_with_context_stream(
        self,
        query: str,
        search_context: str,
        max_tokens: int = 1200,
    ) -> str:
        """
        流式调用 L4 模型（Qwen3 思考模型推荐方式）。
        Qwen3 在流式模式下 content token 正常输出，不依赖 thinking 字段。
        """
        system_msg = (
            "你是一个专业的环境评估与法规顾问，擅长处理环境影响评价（环评）相关问题。"
            "请基于参考资料给出专业、结构化的回答。/no_think"
        )
        user_content = (
            f"用户问题：{query}\n\n"
            f"参考资料（来自深度搜索）：\n{search_context}\n\n"
            f"请给出专业回答。 /no_think"
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content},
        ]
        collected = []
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                async with client.stream(
                    "POST",
                    f"{self.host}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                        "options": {"num_predict": max_tokens},
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                collected.append(token)
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning(f"L4 stream generate 失败: {e}")

        return "".join(collected)


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 4 - 路由决策（L0 分析 Query）
# ─────────────────────────────────────────────────────────────────────────────
async def phase4_route_decision(
    l0: L0SmolLM2Client,
    query: str,
) -> Dict[str, Any]:
    section("Phase 4 · L0 路由决策")
    log_step("输入 Query", "INFO", f'"{query}"')

    start = time.perf_counter()
    decision = await l0.classify(query)
    elapsed = (time.perf_counter() - start) * 1000

    decision["latency_ms"] = round(elapsed, 2)

    log_step("Route",     "OK",  decision.get("route", "?"))
    log_step("Intent",    "OK",  decision.get("intent", "?"))
    log_step("Reason",    "INFO", decision.get("reason", ""))
    log_step("Confidence","INFO", f"{decision.get('confidence', 0):.2f}")
    log_step("Via",       "INFO", decision.get("via", "?"))
    log_step("耗时",       "INFO", f"{elapsed:.1f} ms")

    return decision


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 5 - 深度搜索执行
# ─────────────────────────────────────────────────────────────────────────────
async def phase5_deep_search(
    query: str,
    cfg: SystemConfig,
) -> Dict[str, Any]:
    section("Phase 5 · DeepSearchWikiSystem 深度搜索")
    log_step("搜索 Query", "RUN", f'"{query}"')

    # 尝试使用项目内的 DeepSearchWikiSystem
    wiki_page = None
    try:
        from business.deep_search_wiki import DeepSearchWikiSystem
        wiki_system = DeepSearchWikiSystem()
        start = time.perf_counter()
        wiki_page = await wiki_system.generate_async(query)
        elapsed = (time.perf_counter() - start) * 1000
        log_step("DeepSearchWikiSystem", "OK",
                 f"生成完毕，来源 {len(wiki_page.sources)} 条，耗时 {elapsed:.0f} ms")
    except Exception as e:
        log_step("DeepSearchWikiSystem", "WARN", f"导入/调用失败：{e}，使用内置搜索替代")

    if wiki_page:
        # 从 WikiPage 提取结构化上下文
        ctx_parts = [f"【概述】{wiki_page.summary}"]
        for sec in wiki_page.sections[:3]:
            ctx_parts.append(f"【{sec.title}】{sec.content[:300]}")
        ctx_parts.append(
            f"\n搜索来源（共 {wiki_page.sources_count} 条，"
            f"平均可信度 {wiki_page.credibility_avg:.1f}）"
        )
        return {
            "search_context": "\n\n".join(ctx_parts),
            "sources_count": wiki_page.sources_count,
            "credibility_avg": wiki_page.credibility_avg,
            "wiki_page": wiki_page,
        }

    # ── 内置搜索替代（当 DeepSearchWikiSystem 不可用时）────────────────────────
    log_step("内置搜索", "RUN", "启动内置多源搜索替代方案...")
    return await _builtin_deep_search(query)


async def _builtin_deep_search(query: str) -> Dict[str, Any]:
    """
    内置深度搜索：
    模拟 SmartSearchEngine + CredibilityEvaluator 的行为，
    实际调用 Bing/百度搜索 API（本环境无 key，使用结构化占位数据）。
    """
    from business.deep_search_wiki.search_engine import SmartSearchEngine
    from business.deep_search_wiki.wiki_generator import WikiGenerator

    generator = WikiGenerator()
    start = time.perf_counter()

    # 扩展查询词
    search_query = generator.search_engine.expand_query(query)
    log_step("查询扩展", "OK",
             f"原始: '{query}' → 扩展词 {len(search_query.expanded)} 个")

    # 执行搜索
    results = await generator.search_engine.search(query, max_results=10)
    log_step("搜索结果", "OK", f"获取 {len(results)} 条结果")
    for i, r in enumerate(results[:5], 1):
        print(f"      [{i}] {r.score:>3}分  {r.title[:50]}")

    # 生成 Wiki
    wiki = generator.generate(query, search_results=results)
    elapsed = (time.perf_counter() - start) * 1000
    log_step("Wiki 生成", "OK",
             f"章节 {len(wiki.sections)} 个，来源 {wiki.sources_count} 条，"
             f"可信度均值 {wiki.credibility_avg:.1f}，耗时 {elapsed:.0f} ms")

    ctx_parts = [f"【概述】{wiki.summary}"]
    for sec in wiki.sections[:3]:
        ctx_parts.append(f"【{sec.title}】{sec.content[:300]}")

    return {
        "search_context": "\n\n".join(ctx_parts),
        "sources_count": wiki.sources_count,
        "credibility_avg": wiki.credibility_avg,
        "wiki_page": wiki,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 6 - L4 生成最终答案 + 结果汇总
# ─────────────────────────────────────────────────────────────────────────────
async def phase6_l4_generate_and_summary(
    l4: L4OllamaClient,
    query: str,
    route_decision: Dict[str, Any],
    search_result: Dict[str, Any],
) -> str:
    section("Phase 6 · L4 增强模型生成最终答案")

    search_context = search_result.get("search_context", "（无搜索上下文）")

    if l4._ready:
        log_step("L4 Generate", "RUN",
                 f"调用 {l4.model}（流式+搜索上下文 {len(search_context)} 字）...")
        start = time.perf_counter()

        # 优先使用流式调用（Qwen3 思考模型 stream 模式可正常输出 content token）
        answer = await l4.generate_with_context_stream(query, search_context)

        # 流式调用失败时回退到非流式（自动处理 thinking 字段）
        if not answer:
            log_step("流式降级", "WARN", "流式调用无内容，尝试非流式...")
            answer = await l4.generate_with_context(query, search_context)

        elapsed = (time.perf_counter() - start) * 1000

        if answer:
            log_step("L4 回答", "OK", f"生成 {len(answer)} 字，耗时 {elapsed:.0f} ms")
        else:
            log_step("L4 回答", "WARN", "L4 未返回内容，使用搜索摘要兜底")
            answer = search_context
    else:
        log_step("L4 模型", "WARN", "L4 不可用，使用搜索摘要作为最终回答")
        answer = search_context

    # ── 最终汇总输出 ────────────────────────────────────────────────────────
    section("最终结果汇总")
    print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│  用户问题：{query}
├─────────────────────────────────────────────────────────────────────┤
│  ① L0 路由决策
│     route      = {route_decision.get('route', '?')}
│     intent     = {route_decision.get('intent', '?')}
│     confidence = {route_decision.get('confidence', 0):.2f}
│     via        = {route_decision.get('via', '?')}
│     latency    = {route_decision.get('latency_ms', 0):.1f} ms
├─────────────────────────────────────────────────────────────────────┤
│  ② 深度搜索
│     来源数量  = {search_result.get('sources_count', 0)} 条
│     平均可信度 = {search_result.get('credibility_avg', 0):.1f}
├─────────────────────────────────────────────────────────────────────┤
│  ③ L4 回答（{l4.model}）
└─────────────────────────────────────────────────────────────────────┘
""")
    print(answer)

    return answer


# ─────────────────────────────────────────────────────────────────────────────
#  主测试入口
# ─────────────────────────────────────────────────────────────────────────────
async def run_full_chain_test():
    """执行深度搜索全链路测试"""
    print("\n" + "═" * 72)
    print("  🧪  深度搜索全链路测试  |  LivingTree AI Agent")
    print("═" * 72)
    print(f"  测试时间  : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  测试问题  : {TEST_QUERY}")
    print("═" * 72)

    total_start = time.perf_counter()

    # ── Phase 0: 系统配置 ──────────────────────────────────────────────────
    cfg = phase0_system_config()

    # ── Phase 1: L0 初始化 ─────────────────────────────────────────────────
    l0 = L0SmolLM2Client(cfg)
    await l0.init()

    # ── Phase 2: L3 初始化 ─────────────────────────────────────────────────
    l3 = L3OllamaClient(cfg)
    await l3.init()

    # ── Phase 3: L4 初始化 ─────────────────────────────────────────────────
    l4 = L4OllamaClient(cfg)
    await l4.init()

    # ── Phase 4: L0 路由决策 ────────────────────────────────────────────────
    route_decision = await phase4_route_decision(l0, TEST_QUERY)

    # 根据路由结果决定是否走深度搜索
    route = route_decision.get("route", "heavy")
    if route in ("search", "heavy", "local"):
        log_step("调度决策", "OK",
                 f"route={route} → 执行深度搜索 + L4 增强生成")
    else:
        log_step("调度决策", "WARN",
                 f"route={route}，但本测试强制执行全链路")

    # ── Phase 5: 深度搜索 ───────────────────────────────────────────────────
    search_result = await phase5_deep_search(TEST_QUERY, cfg)

    # ── Phase 6: L4 生成答案 + 汇总 ────────────────────────────────────────
    await phase6_l4_generate_and_summary(l4, TEST_QUERY, route_decision, search_result)

    total_elapsed = (time.perf_counter() - total_start) * 1000
    print(f"\n{'─' * 72}")
    print(f"  ✅  全链路测试完成  |  总耗时 {total_elapsed:.0f} ms  ({total_elapsed / 1000:.1f} s)")
    print("─" * 72)


# ─────────────────────────────────────────────────────────────────────────────
#  入口
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run_full_chain_test())
