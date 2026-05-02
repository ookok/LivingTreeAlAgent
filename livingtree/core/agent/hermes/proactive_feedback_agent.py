"""
ProactiveFeedbackAgent - 智能体主动反馈

实现智能体主动反馈功能：
1. 智能体可主动报告问题（通过 PyQt6 通知）
2. 智能体可建议改进方案
3. 添加"智能体评论"功能
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import json
import os


class FeedbackType(Enum):
    """反馈类型"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUGGESTION = "suggestion"
    COMMENT = "comment"


class FeedbackPriority(Enum):
    """反馈优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FeedbackItem:
    """反馈项"""
    feedback_id: str
    type: FeedbackType
    priority: FeedbackPriority
    title: str
    message: str
    agent_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    action_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentComment:
    """智能体评论"""
    comment_id: str
    agent_id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    likes: int = 0
    replies: List["AgentComment"] = field(default_factory=list)


class ProactiveFeedbackAgent:
    """
    智能体主动反馈代理
    
    核心功能：
    1. 智能体可主动报告问题
    2. 智能体可建议改进方案
    3. 添加"智能体评论"功能
    4. 通过 PyQt6 通知用户
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._logger = logger.bind(component="ProactiveFeedbackAgent")
        self._feedbacks: List[FeedbackItem] = []
        self._comments: List[AgentComment] = []
        self._notification_callback: Optional[Callable[[dict], None]] = None
        self._load_data()
        self._initialized = True
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _load_data(self):
        """加载反馈数据"""
        try:
            storage_path = self._get_storage_path()
            feedback_file = os.path.join(storage_path, "feedbacks.json")
            comments_file = os.path.join(storage_path, "comments.json")
            
            if os.path.exists(feedback_file):
                with open(feedback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self._feedbacks.append(FeedbackItem(
                            feedback_id=item["feedback_id"],
                            type=FeedbackType(item["type"]),
                            priority=FeedbackPriority(item["priority"]),
                            title=item["title"],
                            message=item["message"],
                            agent_id=item["agent_id"],
                            timestamp=datetime.fromisoformat(item["timestamp"]),
                            resolved=item.get("resolved", False),
                            resolved_at=datetime.fromisoformat(item["resolved_at"]) if item.get("resolved_at") else None,
                            action_url=item.get("action_url"),
                            metadata=item.get("metadata", {})
                        ))
            
            if os.path.exists(comments_file):
                with open(comments_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self._comments.append(AgentComment(
                            comment_id=item["comment_id"],
                            agent_id=item["agent_id"],
                            content=item["content"],
                            timestamp=datetime.fromisoformat(item["timestamp"]),
                            likes=item.get("likes", 0)
                        ))
        except Exception as e:
            self._logger.error(f"加载反馈数据失败: {e}")
    
    def _save_data(self):
        """保存反馈数据"""
        try:
            storage_path = self._get_storage_path()
            
            # 保存反馈
            feedback_data = []
            for feedback in self._feedbacks:
                feedback_data.append({
                    "feedback_id": feedback.feedback_id,
                    "type": feedback.type.value,
                    "priority": feedback.priority.value,
                    "title": feedback.title,
                    "message": feedback.message,
                    "agent_id": feedback.agent_id,
                    "timestamp": feedback.timestamp.isoformat(),
                    "resolved": feedback.resolved,
                    "resolved_at": feedback.resolved_at.isoformat() if feedback.resolved_at else None,
                    "action_url": feedback.action_url,
                    "metadata": feedback.metadata
                })
            
            with open(os.path.join(storage_path, "feedbacks.json"), "w", encoding="utf-8") as f:
                json.dump(feedback_data, f, indent=2, ensure_ascii=False)
            
            # 保存评论
            comment_data = []
            for comment in self._comments:
                comment_data.append({
                    "comment_id": comment.comment_id,
                    "agent_id": comment.agent_id,
                    "content": comment.content,
                    "timestamp": comment.timestamp.isoformat(),
                    "likes": comment.likes
                })
            
            with open(os.path.join(storage_path, "comments.json"), "w", encoding="utf-8") as f:
                json.dump(comment_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._logger.error(f"保存反馈数据失败: {e}")
    
    def _get_storage_path(self) -> str:
        """获取存储路径"""
        path = os.path.join(os.path.expanduser("~"), ".livingtree", "feedback")
        os.makedirs(path, exist_ok=True)
        return path
    
    def set_notification_callback(self, callback: Callable[[dict], None]):
        """
        设置通知回调（用于 PyQt6 通知）
        
        Args:
            callback: 通知回调函数，接收反馈字典作为参数
        """
        self._notification_callback = callback
    
    def report_issue(self, agent_id: str, title: str, message: str,
                    priority: FeedbackPriority = FeedbackPriority.MEDIUM,
                    action_url: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> FeedbackItem:
        """
        报告问题
        
        Args:
            agent_id: 智能体ID
            title: 问题标题
            message: 问题详情
            priority: 优先级
            action_url: 操作链接
            metadata: 附加信息
        
        Returns:
            创建的反馈项
        """
        feedback = FeedbackItem(
            feedback_id=f"feedback_{int(datetime.now().timestamp())}",
            type=FeedbackType.ERROR,
            priority=priority,
            title=title,
            message=message,
            agent_id=agent_id,
            action_url=action_url,
            metadata=metadata or {}
        )
        
        self._feedbacks.append(feedback)
        self._save_data()
        self._send_notification(feedback)
        
        self._logger.warning(f"智能体 {agent_id} 报告问题: {title}")
        
        return feedback
    
    def suggest_improvement(self, agent_id: str, title: str, message: str,
                           priority: FeedbackPriority = FeedbackPriority.LOW,
                           metadata: Optional[Dict[str, Any]] = None) -> FeedbackItem:
        """
        建议改进方案
        
        Args:
            agent_id: 智能体ID
            title: 建议标题
            message: 建议详情
            priority: 优先级
            metadata: 附加信息
        
        Returns:
            创建的反馈项
        """
        feedback = FeedbackItem(
            feedback_id=f"feedback_{int(datetime.now().timestamp())}",
            type=FeedbackType.SUGGESTION,
            priority=priority,
            title=title,
            message=message,
            agent_id=agent_id,
            metadata=metadata or {}
        )
        
        self._feedbacks.append(feedback)
        self._save_data()
        self._send_notification(feedback)
        
        self._logger.info(f"智能体 {agent_id} 提出改进建议: {title}")
        
        return feedback
    
    def send_info(self, agent_id: str, title: str, message: str,
                 metadata: Optional[Dict[str, Any]] = None) -> FeedbackItem:
        """
        发送信息通知
        
        Args:
            agent_id: 智能体ID
            title: 信息标题
            message: 信息内容
            metadata: 附加信息
        
        Returns:
            创建的反馈项
        """
        feedback = FeedbackItem(
            feedback_id=f"feedback_{int(datetime.now().timestamp())}",
            type=FeedbackType.INFO,
            priority=FeedbackPriority.LOW,
            title=title,
            message=message,
            agent_id=agent_id,
            metadata=metadata or {}
        )
        
        self._feedbacks.append(feedback)
        self._save_data()
        self._send_notification(feedback)
        
        return feedback
    
    def add_comment(self, agent_id: str, content: str) -> AgentComment:
        """
        添加智能体评论
        
        Args:
            agent_id: 智能体ID
            content: 评论内容
        
        Returns:
            创建的评论
        """
        comment = AgentComment(
            comment_id=f"comment_{int(datetime.now().timestamp())}",
            agent_id=agent_id,
            content=content
        )
        
        self._comments.append(comment)
        self._save_data()
        
        self._logger.info(f"智能体 {agent_id} 添加评论")
        
        return comment
    
    def _send_notification(self, feedback: FeedbackItem):
        """发送通知"""
        if self._notification_callback:
            notification_data = {
                "id": feedback.feedback_id,
                "type": feedback.type.value,
                "priority": feedback.priority.value,
                "title": feedback.title,
                "message": feedback.message,
                "agent_id": feedback.agent_id,
                "timestamp": feedback.timestamp.isoformat(),
                "action_url": feedback.action_url
            }
            try:
                self._notification_callback(notification_data)
            except Exception as e:
                self._logger.error(f"发送通知失败: {e}")
    
    def resolve_feedback(self, feedback_id: str) -> bool:
        """
        标记反馈为已解决
        
        Args:
            feedback_id: 反馈ID
        
        Returns:
            是否成功
        """
        for feedback in self._feedbacks:
            if feedback.feedback_id == feedback_id:
                feedback.resolved = True
                feedback.resolved_at = datetime.now()
                self._save_data()
                self._logger.info(f"反馈已解决: {feedback_id}")
                return True
        
        return False
    
    def like_comment(self, comment_id: str) -> bool:
        """
        点赞评论
        
        Args:
            comment_id: 评论ID
        
        Returns:
            是否成功
        """
        for comment in self._comments:
            if comment.comment_id == comment_id:
                comment.likes += 1
                self._save_data()
                return True
        
        return False
    
    def get_feedbacks(self, resolved: Optional[bool] = None,
                     feedback_type: Optional[FeedbackType] = None) -> List[FeedbackItem]:
        """
        获取反馈列表
        
        Args:
            resolved: 是否已解决（None表示全部）
            feedback_type: 反馈类型（None表示全部）
        
        Returns:
            反馈列表
        """
        result = self._feedbacks
        
        if resolved is not None:
            result = [f for f in result if f.resolved == resolved]
        
        if feedback_type:
            result = [f for f in result if f.type == feedback_type]
        
        result.sort(key=lambda x: (x.priority.value, x.timestamp), reverse=True)
        
        return result
    
    def get_comments(self) -> List[AgentComment]:
        """获取所有评论"""
        return sorted(self._comments, key=lambda x: x.timestamp, reverse=True)
    
    def get_unresolved_count(self) -> int:
        """获取未解决反馈数量"""
        return sum(1 for f in self._feedbacks if not f.resolved)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        type_counts = {}
        priority_counts = {}
        
        for feedback in self._feedbacks:
            type_counts[feedback.type.value] = type_counts.get(feedback.type.value, 0) + 1
            priority_counts[feedback.priority.value] = priority_counts.get(feedback.priority.value, 0) + 1
        
        return {
            "total_feedbacks": len(self._feedbacks),
            "unresolved_count": self.get_unresolved_count(),
            "resolved_count": len(self._feedbacks) - self.get_unresolved_count(),
            "total_comments": len(self._comments),
            "feedbacks_by_type": type_counts,
            "feedbacks_by_priority": priority_counts
        }