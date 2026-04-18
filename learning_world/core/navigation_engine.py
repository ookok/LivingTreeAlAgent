"""
导航引擎
处理标签点击与路径生成
"""

import uuid
import time
from typing import List, Dict, Any, Optional, Callable

from ..models.knowledge_models import (
    KnowledgeTag, LearningResponse, ExplorationPath, LearningSession, TagType
)


class NavigationEngine:
    """
    导航引擎
    
    处理标签点击，生成新的探索路径
    """
    
    def __init__(
        self,
        knowledge_engine,  # KnowledgeEngine 实例
        user_profile_manager=None  # UserProfileManager 实例
    ):
        self.knowledge_engine = knowledge_engine
        self.user_profile_manager = user_profile_manager
        
        # 当前会话
        self._current_session: Optional[LearningSession] = None
        
        # 历史会话
        self._sessions: Dict[str, LearningSession] = {}
    
    @property
    def current_session(self) -> Optional[LearningSession]:
        return self._current_session
    
    def start_new_session(self, initial_query: str) -> LearningSession:
        """开始新的探索会话"""
        session_id = str(uuid.uuid4())[:8]
        path = ExplorationPath(session_id)
        
        session = LearningSession(
            session_id=session_id,
            initial_query=initial_query,
            current_query=initial_query,
            path=path,
        )
        session.record_visit(initial_query)
        
        self._current_session = session
        self._sessions[session_id] = session
        
        return session
    
    async def navigate_by_tag(
        self,
        current_query: str,
        clicked_tag: KnowledgeTag,
        user_profile: Dict[str, Any] = None,
    ) -> LearningResponse:
        """
        根据点击的标签生成新的查询
        
        Args:
            current_query: 当前查询
            clicked_tag: 点击的标签
            user_profile: 用户画像
            
        Returns:
            新的 LearningResponse
        """
        # 获取标签类型
        tag_type = clicked_tag.type.value if hasattr(clicked_tag.type, 'value') else str(clicked_tag.type)
        
        # 1. 构建新查询
        new_query = self._build_query_from_tag(clicked_tag, current_query)
        
        # 2. 记录到路径
        if self._current_session:
            self._current_session.path.add_step(current_query, clicked_tag.text)
            self._current_session.current_query = new_query
            self._current_session.record_visit(new_query)
            self._current_session.record_tag_click(tag_type)
        
        # 3. 更新用户画像
        if self.user_profile_manager:
            # path.steps 是 [(query, tag), ...] 格式
            related_topics = [step[0] for step in (self._current_session.path.steps or []) if step]
            self.user_profile_manager.add_exploration_record(
                topic=new_query,
                tag_type=tag_type,
                related_topics=related_topics,
            )
        
        # 4. 生成新响应
        response = await self.knowledge_engine.generate_response(
            query=new_query,
            user_profile=user_profile,
        )
        
        return response
    
    async def navigate_by_suggestion(
        self,
        suggestion: str,
        user_profile: Dict[str, Any] = None,
    ) -> LearningResponse:
        """根据建议问题导航"""
        if self._current_session:
            self._current_session.path.add_step(
                self._current_session.current_query,
                f"追问: {suggestion}"
            )
            self._current_session.current_query = suggestion
            self._current_session.record_visit(suggestion)
        
        response = await self.knowledge_engine.generate_response(
            query=suggestion,
            user_profile=user_profile,
        )
        
        return response
    
    async def backtrack(self) -> Optional[LearningResponse]:
        """返回上一步"""
        if not self._current_session or not self._current_session.path.steps:
            return None
        
        steps = self._current_session.path.steps
        if len(steps) < 2:
            return None
        
        # 获取上一步的查询
        prev_query = steps[-2][0]
        self._current_session.current_query = prev_query
        
        # 移除最后一步
        self._current_session.path.steps.pop()
        
        # 重新生成响应
        response = await self.knowledge_engine.generate_response(
            query=prev_query,
            user_profile=self._get_user_profile_dict(),
        )
        
        return response
    
    def _build_query_from_tag(
        self,
        tag: KnowledgeTag,
        current_query: str
    ) -> str:
        """基于标签构建新查询"""
        keywords = tag.search_keywords or [tag.text]
        main_keyword = keywords[0]
        
        # 构建查询
        if tag.description:
            return f"{main_keyword}：{tag.description[:50]}"
        else:
            return f"详细了解 {main_keyword}"
    
    def _get_user_profile_dict(self) -> Dict[str, Any]:
        """获取用户画像字典"""
        if self.user_profile_manager:
            return self.user_profile_manager.get_profile().to_dict()
        return {}
    
    def get_breadcrumbs(self) -> List[str]:
        """获取面包屑导航"""
        if self._current_session:
            return self._current_session.path.get_breadcrumbs()
        return []
    
    def get_full_path(self) -> str:
        """获取完整探索路径"""
        if self._current_session:
            return self._current_session.path.get_full_path()
        return ""
    
    def get_session_stats(self) -> Dict[str, Any]:
        """获取当前会话统计"""
        if not self._current_session:
            return {}
        
        session = self._current_session
        return {
            "session_id": session.session_id,
            "initial_query": session.initial_query,
            "current_query": session.current_query,
            "steps_count": len(session.path.steps),
            "visited_topics_count": len(session.visited_topics),
            "preferred_tag_types": session.get_preferred_tag_types(),
            "tag_click_stats": session.tag_click_stats,
        }
    
    def get_current_topic(self) -> str:
        """获取当前主题"""
        if self._current_session:
            return self._current_session.current_query or self._current_session.initial_query
        return ""
    
    def can_go_back(self) -> bool:
        """是否可以返回"""
        if self._current_session and self._current_session.path.steps:
            return len(self._current_session.path.steps) > 1
        return False
    
    def get_tag_type_stats(self) -> Dict[str, int]:
        """获取标签类型统计"""
        if self._current_session:
            return self._current_session.tag_click_stats.copy()
        return {}
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        return [
            {
                "session_id": s.session_id,
                "initial_query": s.initial_query,
                "steps_count": len(s.path.steps),
                "created_at": s.created_at,
            }
            for s in self._sessions.values()
        ]
