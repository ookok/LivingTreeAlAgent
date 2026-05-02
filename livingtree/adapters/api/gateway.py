"""
LivingTree API 网关
===================

统一的API入口，路由前端请求到 LifeEngine。
支持 REST + WebSocket。
"""

from typing import Dict, Any, Optional
from datetime import datetime
import uuid


class APIGateway:
    """
    API 网关 — 前端 API 调用的统一入口

    路由策略：
    - /chat → LifeEngine.handle_request()
    - /health → LifeEngine.get_health()
    - /tools → ToolRegistry.list_all()
    - /skills → SkillRepository.list_all()
    """

    def __init__(self):
        self._life_engine = None
        self._tool_registry = None
        self._skill_repo = None
        self._request_count = 0

    def bind_engine(self, engine):
        self._life_engine = engine

    def bind_tools(self, registry):
        self._tool_registry = registry

    def bind_skills(self, repo):
        self._skill_repo = repo

    # ── API Handlers ──

    def handle_chat(self, message: str, session_id: str = "",
                    stream: bool = False) -> Dict[str, Any]:
        self._request_count += 1
        request_id = str(uuid.uuid4())[:8]

        if not self._life_engine:
            return {
                "id": request_id,
                "type": "chat_response",
                "content": "LifeEngine not initialized",
                "error": "engine_not_bound",
            }

        try:
            from livingtree.core.life_engine import Stimulus
            response = self._life_engine.handle_request(message)
            return {
                "id": request_id,
                "type": "chat_response",
                "content": response.text,
                "trace_id": response.trace_id,
                "metadata": {
                    "tokens_input": response.result.tokens_input,
                    "tokens_output": response.result.tokens_output,
                    "duration_ms": response.result.duration_ms,
                    "learning_score": response.learning.score,
                },
            }
        except Exception as e:
            return {
                "id": request_id,
                "type": "error",
                "content": str(e),
                "error": type(e).__name__,
            }

    async def handle_chat_async(self, message: str, session_id: str = "") -> Dict[str, Any]:
        self._request_count += 1
        request_id = str(uuid.uuid4())[:8]

        if not self._life_engine:
            return {
                "id": request_id,
                "type": "chat_response",
                "content": "LifeEngine not initialized",
                "error": "engine_not_bound",
            }

        try:
            from livingtree.core.life_engine import Stimulus
            stimulus = Stimulus(user_input=message)
            response = await self._life_engine.process(stimulus)
            return {
                "id": request_id,
                "type": "chat_response",
                "content": response.text,
                "trace_id": response.trace_id,
                "metadata": {
                    "tokens_input": response.result.tokens_input,
                    "tokens_output": response.result.tokens_output,
                    "duration_ms": response.result.duration_ms,
                    "learning_score": response.learning.score,
                },
            }
        except Exception as e:
            return {
                "id": request_id,
                "type": "error",
                "content": str(e),
                "error": type(e).__name__,
            }

    def handle_health(self) -> Dict[str, Any]:
        health = {
            "status": "running",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_count": self._request_count,
        }

        if self._life_engine:
            health["engine"] = self._life_engine.get_health()

        if self._tool_registry:
            health["tools_count"] = self._tool_registry.count()

        if self._skill_repo:
            health["skills_count"] = self._skill_repo.count()

        return health

    def handle_tools_list(self) -> Dict[str, Any]:
        if not self._tool_registry:
            return {"tools": [], "error": "ToolRegistry 未绑定"}

        tools = []
        for tool in self._tool_registry.get_all_tools():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "category": getattr(tool, 'category', 'core'),
            })
        return {"tools": tools, "count": len(tools)}

    def handle_skills_list(self) -> Dict[str, Any]:
        if not self._skill_repo:
            return {"skills": [], "error": "SkillRepository 未绑定"}

        skills = []
        for skill in self._skill_repo.list_all():
            skills.append({
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "tags": skill.tags,
            })
        return {"skills": skills, "count": len(skills)}

    def handle_tool_call(self, tool_name: str,
                        params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._tool_registry:
            return {"success": False, "error": "ToolRegistry 未绑定"}

        tool = self._tool_registry.get(tool_name)
        if not tool:
            return {"success": False, "error": f"工具不存在: {tool_name}"}

        if not tool.handler:
            return {"success": False, "error": f"工具无处理器: {tool_name}"}

        try:
            result = tool.handler(params or {})
            return {"success": True, "result": str(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 路由分发 ──

    def register_module(self, module_name: str, module_instance: Any):
        """注册模块到网关"""
        pass

    def dispatch(self, endpoint: str, **params) -> Dict[str, Any]:
        handlers = {
            "chat": lambda: self.handle_chat(
                params.get("message", ""),
                params.get("session_id", ""),
                params.get("stream", False),
            ),
            "health": self.handle_health,
            "tools": self.handle_tools_list,
            "skills": self.handle_skills_list,
        }

        handler = handlers.get(endpoint)
        if handler:
            return handler()
        return {"error": f"Unknown endpoint: {endpoint}"}


_gateway_instance: Optional[APIGateway] = None


def get_api_gateway() -> APIGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = APIGateway()
    return _gateway_instance


__all__ = ["APIGateway", "get_api_gateway"]
