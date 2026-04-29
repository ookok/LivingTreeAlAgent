# -*- coding: utf-8 -*-
"""
Persona Skill 引擎
人格化 AI 调用核心 - 集成 RelayFreeLLM 网关与记忆宫殿
"""

import re
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import asyncio

from .models import PersonaSkill, PersonaSession, PersonaInvokeResult, PersonaCategory, PersonaTier
from .registry import PersonaRegistry


# 尝试导入 L4 执行器（RelayFreeLLM 网关）
try:
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    from core.fusion_rag.l4_executor import L4RelayExecutor
    HAS_L4_EXECUTOR = True
except ImportError:
    HAS_L4_EXECUTOR = False
    L4RelayExecutor = None

# 尝试导入记忆宫殿
try:
    from core.memory_palace.memory_engine import MemoryPalace
    HAS_MEMORY_PALACE = True
except ImportError:
    HAS_MEMORY_PALACE = False
    MemoryPalace = None


class PersonaEngine:
    """
    Persona 引擎 - 人格化 AI 核心

    功能：
    1. 角色Prompt注入与模板化
    2. 集成 RelayFreeLLM 网关调用
    3. 集成记忆宫殿上下文
    4. 变量替换与多轮对话
    5. 自动意图检测与角色推荐
    """

    def __init__(
        self,
        registry: Optional[PersonaRegistry] = None,
        l4_executor: Optional[Any] = None,
        memory_palace: Optional[Any] = None
    ):
        self.registry = registry or PersonaRegistry()
        self.l4_executor = l4_executor
        self.memory_palace = memory_palace
        
        # 当前会话
        self._current_session_id: Optional[str] = None
        self._current_persona_id: Optional[str] = None
        
        # 回调函数
        self._on_token: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

    # ==================== 核心调用 ====================

    async def invoke(
        self,
        task: str,
        persona_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        use_memory: bool = True,
        model_hint: Optional[str] = None,
        **kwargs
    ) -> PersonaInvokeResult:
        """
        调用 Persona 执行任务

        Args:
            task: 用户任务/问题
            persona_id: 指定角色ID，不指定则用当前激活的
            session_id: 会话ID，用于多轮对话
            context: 额外上下文变量
            use_memory: 是否使用记忆宫殿
            model_hint: 指定模型（如 "gpt-4" / "claude-3"）

        Returns:
            PersonaInvokeResult: 调用结果
        """
        start_time = time.time()
        
        # 1. 获取角色
        persona = self._get_persona(persona_id)
        if not persona:
            return PersonaInvokeResult(
                success=False,
                response="",
                persona_id=persona_id or "unknown",
                persona_name="Unknown",
                error=f"Persona not found: {persona_id}"
            )

        # 2. 解析会话
        if session_id:
            self._current_session_id = session_id
        if not self._current_session_id:
            self._current_session_id = self.registry.create_session(persona.id)
        
        session = self.registry.get_session(self._current_session_id)
        if session:
            session.persona_id = persona.id
        
        self._current_persona_id = persona.id

        # 3. 构建消息
        messages = await self._build_messages(persona, task, session, context, use_memory)

        # 4. 调用 LLM
        try:
            if self.l4_executor and HAS_L4_EXECUTOR:
                # 使用 L4 执行器（RelayFreeLLM 网关）
                response = await self._call_l4(messages, model_hint, **kwargs)
            else:
                # 降级方案：使用通用 LLM 调用
                response = await self._call_fallback(messages, **kwargs)

            latency = (time.time() - start_time) * 1000

            # 5. 记录会话
            if session:
                session.add_message("user", task)
                session.add_message("assistant", response)

            # 6. 记录使用
            self.registry.record_usage(persona.id)

            return PersonaInvokeResult(
                success=True,
                response=response,
                persona_id=persona.id,
                persona_name=f"{persona.icon} {persona.name}",
                latency_ms=latency
            )

        except Exception as e:
            return PersonaInvokeResult(
                success=False,
                response="",
                persona_id=persona.id,
                persona_name=f"{persona.icon} {persona.name}",
                error=str(e)
            )

    def _get_persona(self, persona_id: Optional[str]) -> Optional[PersonaSkill]:
        """获取角色"""
        if persona_id:
            return self.registry.get(persona_id)
        
        # 尝试当前激活的
        active = self.registry.get_active()
        if active:
            return active
        
        # 默认返回女娲
        return self.registry.get("nuwa")

    async def _build_messages(
        self,
        persona: PersonaSkill,
        task: str,
        session: Optional[PersonaSession],
        context: Optional[Dict[str, Any]],
        use_memory: bool
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []

        # 1. System Prompt
        system_content = persona.system_prompt

        # 注入记忆上下文
        if use_memory and self.memory_palace and HAS_MEMORY_PALACE:
            try:
                memory_context = await self._get_memory_context(persona.id, task)
                if memory_context:
                    system_content += f"\n\n【记忆上下文】\n{memory_context}"
            except Exception as e:
                print(f"获取记忆上下文失败: {e}")

        # 注入会话历史（最近3轮）
        if session and session.messages:
            history = session.messages[-6:]  # 最近6条（3轮）
            history_str = "\n".join([
                f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
                for m in history
            ])
            system_content += f"\n\n【最近对话】\n{history_str}"

        # 注入上下文变量
        if context:
            ctx_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
            system_content += f"\n\n【当前上下文】\n{ctx_str}"

        messages.append({"role": "system", "content": system_content})

        # 2. User Prompt
        user_content = persona.user_prompt_template.replace("{task}", task)
        messages.append({"role": "user", "content": user_content})

        return messages

    async def _get_memory_context(self, persona_id: str, task: str) -> str:
        """从记忆宫殿获取上下文"""
        if not self.memory_palace:
            return ""

        try:
            # 查询相关记忆
            results = self.memory_palace.search(
                query=f"{persona_id} {task}",
                limit=3
            )
            if results:
                return "\n".join([r.get("content", "")[:200] for r in results])
        except Exception:
            pass
        
        return ""

    async def _call_l4(
        self,
        messages: List[Dict[str, str]],
        model_hint: Optional[str],
        **kwargs
    ) -> str:
        """通过 L4 执行器调用"""
        try:
            result = await self.l4_executor.execute(
                messages=messages,
                model_hint=model_hint,
                **kwargs
            )
            return result.get("content", str(result))
        except Exception as e:
            raise RuntimeError(f"L4执行失败: {e}")

    async def _call_fallback(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """降级方案：简单 LLM 调用"""
        # 这里可以接入任何可用的 LLM
        # 暂时返回模拟响应
        system = messages[0]["content"] if messages else ""
        user = messages[-1]["content"] if len(messages) > 1 else ""
        
        return f"[模拟响应]\n\n收到任务: {user}\n\n请配置 L4 执行器以获取真实响应。"

    # ==================== 快捷方法 ====================

    async def consult(
        self,
        question: str,
        persona_type: str = "colleague_sales",
        **kwargs
    ) -> str:
        """
        快捷咨询方法

        用法示例：
        >>> result = await engine.consult("有个客户价格卡在9折，怎么破？", "colleague_sales")
        """
        result = await self.invoke(
            task=question,
            persona_id=persona_type,
            **kwargs
        )
        return result.response

    async def switch_persona(self, persona_id: str) -> bool:
        """切换当前角色"""
        persona = self.registry.get(persona_id)
        if persona:
            self.registry.activate(persona_id)
            self._current_persona_id = persona_id
            return True
        return False

    def get_current_persona(self) -> Optional[PersonaSkill]:
        """获取当前角色"""
        return self.registry.get(self._current_persona_id)

    # ==================== 意图检测 ====================

    def detect_intent(self, query: str) -> List[Dict[str, Any]]:
        """
        检测用户意图，推荐合适的角色

        Returns:
            推荐的角色列表，按匹配度排序
        """
        query_lower = query.lower()
        recommendations = []

        for persona in self.registry.list_all():
            score = 0
            matched_triggers = []

            # 检查触发词
            for trigger in persona.triggers:
                for kw in trigger.keywords:
                    if kw in query_lower:
                        score += trigger.confidence
                        matched_triggers.append(kw)

            # 关键词命中
            for tag in persona.tags:
                if tag.lower() in query_lower:
                    score += 0.3

            if score > 0:
                recommendations.append({
                    "persona_id": persona.id,
                    "name": persona.name,
                    "icon": persona.icon,
                    "score": score,
                    "matched_keywords": matched_triggers
                })

        # 排序
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:3]  # 返回前3个

    # ==================== 同步调用支持 ====================

    def invoke_sync(self, task: str, **kwargs) -> PersonaInvokeResult:
        """同步调用（用于非异步场景）"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.invoke(task, **kwargs))

    # ==================== 流式调用 ====================

    async def invoke_stream(
        self,
        task: str,
        persona_id: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> PersonaInvokeResult:
        """
        流式调用 - 支持逐字输出

        Args:
            task: 用户任务
            persona_id: 指定角色
            on_token: 每个token的回调
        """
        self._on_token = on_token
        
        # 调用主方法
        result = await self.invoke(task, persona_id, **kwargs)
        
        if result.success and on_token:
            # 模拟流式输出
            for char in result.response:
                on_token(char)
                await asyncio.sleep(0.01)
        
        return result

    # ==================== 蒸馏支持 ====================

    async def distill(
        self,
        source_persona_id: str,
        target_description: str,
        name: str,
        icon: str = "🤖",
        tier: PersonaTier = PersonaTier.CUSTOM
    ) -> Optional[PersonaSkill]:
        """
        蒸馏新角色

        从已有角色蒸馏出符合目标描述的新角色

        Args:
            source_persona_id: 源角色ID
            target_description: 目标角色描述
            name: 新角色名称
            icon: 新角色图标

        Returns:
            蒸馏出的新角色
        """
        from .models import PersonaSkill, PersonaVariable

        # 调用源角色生成新角色配置
        prompt = f"""请根据以下描述，生成一个新角色的完整配置。

目标描述：{target_description}

请生成包含以下内容的JSON：
{{
    "system_prompt": "角色系统提示词",
    "user_prompt_template": "用户输入模板（包含{{task}}占位）",
    "description": "角色描述",
    "tags": ["标签1", "标签2", "标签3"]
}}

只返回JSON，不要其他内容。"""

        result = await self.invoke(prompt, persona_id=source_persona_id)

        if result.success:
            try:
                import json
                # 提取JSON
                json_str = self._extract_json(result.response)
                config = json.loads(json_str)

                # 创建新角色
                new_persona = PersonaSkill(
                    id=f"distilled_{int(time.time())}",
                    name=name,
                    description=config.get("description", target_description),
                    category=category,
                    tier=PersonaTier.CUSTOM,
                    icon=icon,
                    system_prompt=config.get("system_prompt", ""),
                    user_prompt_template=config.get("user_prompt_template", "{task}"),
                    tags=config.get("tags", []),
                    is_builtin=False
                )

                # 注册
                self.registry.register(new_persona)
                return new_persona

            except Exception as e:
                print(f"蒸馏角色解析失败: {e}")

        return None

    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        # 尝试找到 ```json ... ``` 格式
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        
        # 尝试找到 { ... } 格式
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)
        
        return text
