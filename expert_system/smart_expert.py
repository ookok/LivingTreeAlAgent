"""
个性化专家系统
整合用户画像解析和人格调度，生成个性化回答
"""

import json
import time
import re
import uuid
from typing import Dict, List, Optional, Any, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum

from .user_profile import UserProfileParser, UserProfile
from .persona_dispatcher import PersonaDispatcher, Persona, PersonaLibrary


# ── 数据模型 ─────────────────────────────────────────────────────────

class ResponseStyle(str, Enum):
    """回答风格"""
    STREAMING = "streaming"      # 流式输出
    BATCH = "batch"              # 批量输出
    THINKING = "thinking"        # 带思考过程


@dataclass
class ExpertResponse:
    """专家回答"""
    text: str                    # 回答内容
    persona_id: str              # 使用的人格
    persona_name: str            # 人格名称
    match_score: float           # 匹配度
    reasoning: str = ""           # 选择理由
    processing_time: float = 0    # 处理时间
    confidence: float = 0        # 回答置信度
    sources: List[str] = field(default_factory=list)  # 参考来源
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "persona_id": self.persona_id,
            "persona_name": self.persona_name,
            "match_score": self.match_score,
            "reasoning": self.reasoning,
            "processing_time": self.processing_time,
            "confidence": self.confidence,
            "sources": self.sources,
        }


@dataclass
class InteractionLog:
    """交互日志"""
    id: str
    user_id: str
    question: str
    persona_id: str
    answer: str
    feedback: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


# ── 个性化专家 ───────────────────────────────────────────────────────

class PersonalizedExpert:
    """
    个性化专家系统
    
    整合用户画像解析、人格调度和回答生成
    """
    
    def __init__(
        self,
        hermes_agent=None,
        profile_parser: Optional[UserProfileParser] = None,
        persona_dispatcher: Optional[PersonaDispatcher] = None,
        interaction_log_path: Optional[str] = None,
    ):
        """
        Args:
            hermes_agent: Hermes Agent 实例，用于调用 LLM
            profile_parser: 用户画像解析器
            persona_dispatcher: 人格调度器
            interaction_log_path: 交互日志路径
        """
        self.hermes_agent = hermes_agent
        self.profile_parser = profile_parser or UserProfileParser()
        self.persona_dispatcher = persona_dispatcher or PersonaDispatcher()
        
        # 交互日志
        if interaction_log_path:
            self.interaction_log_path = interaction_log_path
        else:
            from core.config import get_config_dir
            self.interaction_log_path = str(get_config_dir() / "interaction_logs.json")
        
        self._interaction_logs: List[InteractionLog] = []
        self._load_logs()
        
        # 当前会话状态
        self.current_profile: Optional[UserProfile] = None
        self.current_persona: Optional[Persona] = None
        self.conversation_history: List[Dict] = []
    
    def _load_logs(self):
        """加载交互日志"""
        try:
            import os
            if os.path.exists(self.interaction_log_path):
                with open(self.interaction_log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._interaction_logs = [InteractionLog(**log) for log in data]
        except Exception:
            self._interaction_logs = []
    
    def _save_logs(self):
        """保存交互日志"""
        try:
            import os
            os.makedirs(os.path.dirname(self.interaction_log_path), exist_ok=True)
            with open(self.interaction_log_path, "w", encoding="utf-8") as f:
                data = [log.__dict__ for log in self._interaction_logs[-1000:]]
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    async def answer_question(
        self,
        question: str,
        user_id: str = "default",
        system_prompt: Optional[str] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> ExpertResponse:
        """
        处理用户问题并生成个性化回答
        
        Args:
            question: 用户问题
            user_id: 用户ID
            system_prompt: 可选的系统提示（覆盖人格）
            stream_callback: 流式输出的回调函数
            
        Returns:
            ExpertResponse: 个性化回答
        """
        start_time = time.time()
        
        # 1. 获取/更新用户画像
        self.current_profile = self.profile_parser.get_profile(user_id)
        
        # 解析当前消息更新画像
        parsed = self.profile_parser.parse_from_message(
            question, 
            self.conversation_history[-5:]
        )
        self.profile_parser.update_profile(user_id, parsed)
        
        # 刷新当前画像
        self.current_profile = self.profile_parser.get_profile(user_id)
        
        # 2. 分配合适的人格
        profile_dict = self.current_profile.to_dict()
        self.current_persona = self.persona_dispatcher.dispatch(profile_dict, question)
        
        if not self.current_persona:
            self.current_persona = self.persona_dispatcher.library.get("general_expert")
        
        # 3. 构建系统提示
        if system_prompt:
            final_system_prompt = system_prompt
        else:
            final_system_prompt = self._build_system_prompt()
        
        # 4. 生成回答
        answer_text = await self._generate_answer(
            question=question,
            system_prompt=final_system_prompt,
            stream_callback=stream_callback,
        )
        
        # 5. 后处理（根据画像调整回答）
        answer_text = self._polish_answer(answer_text, profile_dict)
        
        # 6. 记录交互
        processing_time = time.time() - start_time
        interaction = InteractionLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            question=question,
            persona_id=self.current_persona.id,
            answer=answer_text,
            timestamp=time.time(),
            metadata={
                "match_score": self._get_match_score(),
                "profile_confidence": self.current_profile.confidence,
            }
        )
        self._interaction_logs.append(interaction)
        self._save_logs()
        
        # 更新对话历史
        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append({"role": "assistant", "content": answer_text})
        
        # 7. 返回结果
        return ExpertResponse(
            text=answer_text,
            persona_id=self.current_persona.id,
            persona_name=self.current_persona.name,
            match_score=self._get_match_score(),
            reasoning=self.persona_dispatcher.explain_selection(profile_dict, question),
            processing_time=processing_time,
            confidence=self.current_profile.confidence,
        )
    
    def _build_system_prompt(self) -> str:
        """构建完整的系统提示"""
        parts = []
        
        # 人格提示
        if self.current_persona and self.current_persona.system_prompt:
            parts.append(self.current_persona.system_prompt)
        
        # 用户画像上下文
        if self.current_profile:
            primary_role = self.current_profile.get_primary_role()
            if primary_role:
                role_name = self._get_role_name(primary_role)
                parts.append(f"\n## 当前用户画像\n")
                parts.append(f"- 主要角色: {role_name}")
                parts.append(f"- 知识水平: {self.current_profile.expertise_level}")
                parts.append(f"- 沟通偏好: {self.current_profile.communication_preference}")
                
                top_concerns = self.current_profile.get_top_concerns(3)
                if top_concerns:
                    parts.append(f"- 核心关切: {', '.join(top_concerns)}")
        
        # 回答调整指示
        parts.append("\n## 回答调整\n")
        parts.append("请根据上述用户画像调整你的回答：")
        
        if self.current_profile:
            if self.current_profile.expertise_level == "beginner":
                parts.append("- 使用通俗易懂的语言，解释专业术语")
            elif self.current_profile.expertise_level == "expert":
                parts.append("- 可以使用专业术语，深入技术细节")
            
            if self.current_profile.communication_preference == "concise":
                parts.append("- 回答要简洁明了，直奔主题")
            elif self.current_profile.communication_preference == "detailed":
                parts.append("- 回答要详细全面，适当展开")
        
        return "\n".join(parts)
    
    async def _generate_answer(
        self,
        question: str,
        system_prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """生成回答"""
        if not self.hermes_agent:
            return self._generate_fallback_answer(question)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        
        full_response = ""
        
        if self.conversation_history:
            history_context = "\n## 最近对话\n"
            for h in self.conversation_history[-6:]:
                role = "用户" if h.get("role") == "user" else "助手"
                history_context += f"{role}: {h.get('content', '')[:200]}...\n"
            messages.insert(1, {"role": "system", "content": history_context})
        
        try:
            for chunk in self.hermes_agent._llm_chat(messages):
                if chunk.delta:
                    full_response += chunk.delta
                    if stream_callback:
                        stream_callback(chunk.delta)
        except Exception as e:
            return f"生成回答时出错: {str(e)}"
        
        return full_response or "抱歉，我暂时无法生成回答。"
    
    def _generate_fallback_answer(self, question: str) -> str:
        """生成后备回答（无 LLM 时）"""
        if self.current_persona:
            return f"【{self.current_persona.name}】\n\n" \
                   f"根据您的问题，我将为您提供专业的分析。\n\n" \
                   f"由于当前未连接大模型，建议启用 Hermes Agent 以获得更精准的回答。"
        return "请先连接大模型以获取个性化回答。"
    
    def _polish_answer(self, answer: str, profile: Dict) -> str:
        """根据用户画像润色回答"""
        comm_pref = profile.get("communication_preference", "detailed")
        
        if comm_pref == "concise":
            sentences = answer.split("。")
            if len(sentences) > 5:
                answer = "。".join(sentences[:5]) + "。"
        
        return answer
    
    def _get_match_score(self) -> float:
        """获取当前匹配度"""
        if not self.current_profile or not self.current_persona:
            return 0.5
        return self.current_persona.matches_profile(self.current_profile.to_dict())
    
    def _get_role_name(self, role_id: str) -> str:
        """获取角色名称"""
        from .user_profile import SOCIAL_ROLES
        return SOCIAL_ROLES.get(role_id, {}).get("name", role_id)
    
    def record_feedback(self, user_id: str, feedback_type: str):
        """记录用户反馈"""
        self.profile_parser.record_feedback(
            user_id, 
            feedback_type,
            self.current_persona.id if self.current_persona else ""
        )
        
        if self._interaction_logs:
            self._interaction_logs[-1].feedback = feedback_type
            self._save_logs()
    
    def get_current_profile(self, user_id: str) -> UserProfile:
        """获取当前用户画像"""
        return self.profile_parser.get_profile(user_id)
    
    def get_persona_suggestions(self, user_profile: Dict, question: str = "") -> List[Dict]:
        """获取人格建议"""
        top_matches = self.persona_dispatcher.dispatch_top_n(user_profile, question, 5)
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "match_score": round(score, 2),
                "domain": p.domain,
            }
            for p, score in top_matches
        ]
    
    def manual_switch_persona(self, persona_id: str) -> bool:
        """手动切换人格"""
        persona = self.persona_dispatcher.library.get(persona_id)
        if persona:
            self.current_persona = persona
            return True
        return False
    
    def get_interaction_history(self, user_id: str, limit: int = 20) -> List[InteractionLog]:
        """获取交互历史"""
        logs = [l for l in self._interaction_logs if l.user_id == user_id]
        return logs[-limit:]
    
    def export_session_summary(self, user_id: str) -> Dict:
        """导出会话摘要"""
        logs = self.get_interaction_history(user_id)
        profile = self.profile_parser.get_profile(user_id)
        
        persona_usage = {}
        for log in logs:
            persona_usage[log.persona_id] = persona_usage.get(log.persona_id, 0) + 1
        
        return {
            "user_id": user_id,
            "profile": profile.to_dict(),
            "total_interactions": len(logs),
            "persona_usage": persona_usage,
            "last_interaction": logs[-1].timestamp if logs else None,
        }
