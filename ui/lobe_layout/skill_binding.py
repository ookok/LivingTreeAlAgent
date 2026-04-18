"""
技能开关与后端路由自动绑定逻辑

实现 Lobe 式的"勾选即用"体验
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional
from dataclasses import dataclass

from .lobe_models import SkillCategory, SKILL_PRESETS, SessionType

logger = logging.getLogger(__name__)


@dataclass
class RelayConfig:
    """
    RelayFreeLLM 路由配置

    所有技能开关最终映射到这些配置项
    """
    # 搜索配置
    search_backend: str = "direct"      # direct/agent_reach/p2p
    search_mode: str = "auto"         # auto/direct/p2p

    # 模型配置
    model: str = "auto"               # auto/deepseek/qwen/smollm2
    router: str = "smollm2"           # smollm2/none

    # 技能/人设
    persona: str = ""                  # 当前激活的角色ID
    skills: list[str] = None          # 激活的技能列表

    # 记忆配置
    memory: str = "palace"            # palace/none
    rag: str = "fusion"                # fusion/none

    def __post_init__(self):
        if self.skills is None:
            self.skills = []

    def to_dict(self) -> dict:
        return {
            "search_backend": self.search_backend,
            "search_mode": self.search_mode,
            "model": self.model,
            "router": self.router,
            "persona": self.persona,
            "skills": self.skills,
            "memory": self.memory,
            "rag": self.rag,
        }


class SkillToggleBinding:
    """
    技能开关绑定器

    核心功能：
    1. 监听技能开关变化
    2. 自动更新 RelayConfig
    3. 触发后端路由重新配置
    4. 提供状态回调
    """

    def __init__(self, config: Optional[RelayConfig] = None):
        self.config = config or RelayConfig()
        self._callbacks: list[Callable[[RelayConfig], None]] = []
        self._skill_to_handler: dict[str, Callable[[bool], None]] = {}

        # 注册所有技能的处理器
        self._register_handlers()

    def _register_handlers(self):
        """注册技能处理器"""

        # Agent-Reach 搜索
        def handle_agent_reach(enabled: bool):
            if enabled:
                self.config.search_backend = "agent_reach"
                self.config.search_mode = "direct"
            else:
                if not self.is_skill_active("p2p_proxy"):
                    self.config.search_backend = "direct"

        self._skill_to_handler["agent_reach"] = handle_agent_reach

        # P2P 代理
        def handle_p2p_proxy(enabled: bool):
            if enabled:
                self.config.search_backend = "p2p"
                self.config.search_mode = "p2p"
            else:
                if not self.is_skill_active("agent_reach"):
                    self.config.search_backend = "direct"
                    self.config.search_mode = "auto"

        self._skill_to_handler["p2p_proxy"] = handle_p2p_proxy

        # SmolLM2 路由
        def handle_smollm2(enabled: bool):
            self.config.router = "smollm2" if enabled else "none"

        self._skill_to_handler["smollm2_router"] = handle_smollm2

        # DeepSeek 模型
        def handle_deepseek(enabled: bool):
            if enabled:
                self.config.model = "deepseek"
                self.config.router = "none"  # 深度推理不用轻量路由

        self._skill_to_handler["deepseek"] = handle_deepseek

        # 角色技能
        def make_persona_handler(persona_id: str):
            def handler(enabled: bool):
                if enabled:
                    self.config.persona = persona_id
                    # 取消其他角色的勾选
                    for pid in ["colleague_sales", "colleague_architect", "jobs", "musk", "naval"]:
                        if pid != persona_id:
                            self._notify_skill_change(pid, False)
                else:
                    if self.config.persona == persona_id:
                        self.config.persona = ""
            return handler

        for persona_id in ["colleague_sales", "colleague_architect", "jobs", "musk", "naval"]:
            self._skill_to_handler[persona_id] = make_persona_handler(persona_id)

        # 记忆宫殿
        def handle_memory_palace(enabled: bool):
            self.config.memory = "palace" if enabled else "none"

        self._skill_to_handler["memory_palace"] = handle_memory_palace

        # FusionRAG
        def handle_fusion_rag(enabled: bool):
            self.config.rag = "fusion" if enabled else "none"

        self._skill_to_handler["fusion_rag"] = handle_fusion_rag

        # 角色智库（技能组）
        def handle_persona_skill(enabled: bool):
            if enabled:
                if "persona_skill" not in self.config.skills:
                    self.config.skills.append("persona_skill")
            else:
                if "persona_skill" in self.config.skills:
                    self.config.skills.remove("persona_skill")

        self._skill_to_handler["persona_skill"] = handle_persona_skill

    def _notify_skill_change(self, skill_id: str, enabled: bool):
        """通知技能变化（用于互斥操作）"""
        # 这里会触发 skill_changed 回调
        pass

    def on_skill_changed(self, skill_id: str, enabled: bool):
        """
        技能变化回调

        由 ToolboxDrawerWidget 调用
        """
        logger.info(f"Skill changed: {skill_id} -> {enabled}")

        # 调用处理器
        handler = self._skill_to_handler.get(skill_id)
        if handler:
            handler(enabled)

        # 更新技能列表
        if enabled:
            if skill_id not in self.config.skills:
                self.config.skills.append(skill_id)
        else:
            if skill_id in self.config.skills:
                self.config.skills.remove(skill_id)

        # 通知所有回调
        self._notify_config_change()

    def _notify_config_change(self):
        """通知配置变化"""
        for callback in self._callbacks:
            try:
                callback(self.config)
            except Exception as e:
                logger.error(f"Config callback error: {e}")

    def add_config_callback(self, callback: Callable[[RelayConfig], None]):
        """添加配置变化回调"""
        self._callbacks.append(callback)

    def remove_config_callback(self, callback: Callable[[RelayConfig], None]):
        """移除配置变化回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def apply_session_preset(self, session_type: SessionType):
        """
        应用会话预设

        根据会话类型自动配置技能组合
        """
        presets = {
            SessionType.TRADE: {
                "skills": ["colleague_sales", "memory_palace"],
                "model": "qwen",
                "router": "smollm2",
            },
            SessionType.CODE: {
                "skills": ["colleague_architect", "smollm2_router"],
                "model": "qwen",
                "router": "smollm2",
            },
            SessionType.SEARCH: {
                "skills": ["agent_reach", "p2p_proxy"],
                "model": "deepseek",
                "router": "smollm2",
            },
            SessionType.RAG: {
                "skills": ["fusion_rag", "memory_palace"],
                "model": "qwen",
                "router": "none",
            },
            SessionType.PERSONA: {
                "skills": ["persona_skill"],
                "model": "deepseek",
                "router": "none",
            },
            SessionType.CUSTOM: {
                "skills": [],
                "model": "auto",
                "router": "smollm2",
            },
        }

        preset = presets.get(session_type)
        if preset:
            self.config.skills = preset.get("skills", [])
            self.config.model = preset.get("model", "auto")
            self.config.router = preset.get("router", "smollm2")

            self._notify_config_change()

    def is_skill_active(self, skill_id: str) -> bool:
        """检查技能是否活跃"""
        return skill_id in self.config.skills

    def get_config(self) -> RelayConfig:
        """获取当前配置"""
        return self.config

    def set_config(self, config: RelayConfig):
        """设置配置"""
        self.config = config
        self._notify_config_change()


class LobeMessageProcessor:
    """
    Lobe 风格消息处理器

    负责：
    1. 接收用户消息
    2. 根据当前技能配置选择路由
    3. 调用后端执行
    4. 返回结果和状态流
    """

    def __init__(self, binding: SkillToggleBinding):
        self.binding = binding
        self._handlers: dict[str, Callable] = {}

        # 注册默认处理器
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认处理器"""

        # SmolLM2 意图路由
        async def handle_smollm2_route(prompt: str) -> dict:
            try:
                from core.smolllm2 import L0Router
                router = L0Router()
                decision = await router.route(prompt)

                return {
                    "route": decision.route.value,
                    "intent": decision.intent.value,
                    "confidence": decision.confidence,
                }
            except Exception as e:
                logger.error(f"SmolLM2 route error: {e}")
                return {"route": "heavy", "intent": "unknown"}

        self._handlers["smollm2"] = handle_smollm2_route

        # Agent-Reach 搜索
        async def handle_agent_reach(query: str) -> dict:
            try:
                from core.agent_reach import AgentReachClient
                client = AgentReachClient()
                results = await asyncio.to_thread(
                    client.search, query, "duckduckgo", 5
                )
                return {"status": "success", "results": results}
            except Exception as e:
                logger.error(f"Agent-Reach error: {e}")
                return {"status": "error", "error": str(e)}

        self._handlers["agent_reach"] = handle_agent_reach

        # P2P 代理搜索
        async def handle_p2p_proxy(query: str) -> dict:
            try:
                from core.p2p_search_proxy import P2PSearchProxy, SearchEngineType
                proxy = P2PSearchProxy(node_id="lobe-client")
                task = await proxy.search(query, SearchEngineType.DUCKDUCKGO)
                return {
                    "status": "success" if task.status.value == "success" else "error",
                    "results": task.results,
                    "route": task.route_type,
                }
            except Exception as e:
                logger.error(f"P2P proxy error: {e}")
                return {"status": "error", "error": str(e)}

        self._handlers["p2p_proxy"] = handle_p2p_proxy

        # 角色咨询
        async def handle_persona(prompt: str, persona_id: str) -> dict:
            try:
                from core.persona_skill import PersonaEngine
                engine = PersonaEngine()
                result = await engine.invoke(task=prompt, persona_id=persona_id)
                return {"status": "success", "response": result.response}
            except Exception as e:
                logger.error(f"Persona error: {e}")
                return {"status": "error", "error": str(e)}

        self._handlers["persona"] = handle_persona

    async def process_message(self, prompt: str) -> dict:
        """
        处理消息

        Returns:
            dict: {
                "status": "success"/"error",
                "response": str,  # AI 回复
                "flow": list[str],  # 状态流步骤
                "tokens": int,  # Token 计数
                "model": str,  # 使用的模型
            }
        """
        config = self.binding.get_config()
        flow_steps = []
        tokens = 0

        # 1. 路由决策
        if config.router == "smollm2" and "smollm2_router" in config.skills:
            flow_steps.append("local")
            route_info = await self._handlers["smollm2"](prompt)
        else:
            route_info = {"route": "heavy"}

        # 2. 根据路由执行
        if route_info.get("route") == "local":
            # 本地快速执行
            flow_steps.append("local")
            # ... 执行简单任务

        elif route_info.get("route") in ("search", "p2p"):
            # 搜索任务
            flow_steps.append("search")

            if config.search_backend == "p2p" and "p2p_proxy" in config.skills:
                result = await self._handlers["p2p_proxy"](prompt)
            elif "agent_reach" in config.skills:
                result = await self._handlers["agent_reach"](prompt)
            else:
                result = {"status": "error", "error": "No search backend"}

        else:
            # AI 推理
            flow_steps.append("ai")

            if config.persona and "persona_skill" in config.skills:
                result = await self._handlers["persona"](prompt, config.persona)
            else:
                # 默认 LLM 调用
                flow_steps.append("thinking")
                result = await self._call_default_llm(prompt, config)
                flow_steps.append("writing")

        # 3. 生成响应
        flow_steps.append("done")

        return {
            "status": result.get("status", "success"),
            "response": result.get("response", result.get("results", "")),
            "flow": flow_steps,
            "tokens": tokens,
            "model": config.model,
        }

    async def _call_default_llm(self, prompt: str, config: RelayConfig) -> dict:
        """调用默认 LLM"""
        # 这里应该调用 RelayFreeLLM
        # 简化实现
        return {
            "status": "success",
            "response": f"[{config.model}] 处理: {prompt[:50]}...",
        }
