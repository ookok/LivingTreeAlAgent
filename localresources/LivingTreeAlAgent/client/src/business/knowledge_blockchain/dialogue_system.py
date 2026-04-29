# -*- coding: utf-8 -*-
"""
去中心化知识区块链系统 - 对话学习系统

实现:
- 对话协议: 知识查询、辩论、协作、教学
- 对话学习机制: 强化学习、迁移学习、联邦学习
- 协同学习: 多节点协作学习
"""

import asyncio
import logging
import json
import hashlib
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from .models import (
    DialogueMessage, DialogueSession, DialogueType,
    KnowledgeUnit
)

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """会话状态"""
    PENDING = "pending"
    ACTIVE = "active"
    WAITING_RESPONSE = "waiting_response"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class MessageRole(Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class DialogueContext:
    """对话上下文"""
    session_id: str
    topic: Optional[str] = None
    knowledge_ids: List[str] = field(default_factory=list)
    learning_goals: List[str] = field(default_factory=list)
    current_depth: int = 0
    max_depth: int = 5
    context_window: int = 10  # 保留的上下文消息数


@dataclass
class LearningInsight:
    """学习洞察"""
    insight_id: str
    content: str
    source_message_id: str
    confidence: float
    extracted_at: datetime
    applied: bool = False


@dataclass
class DialogueStats:
    """对话统计"""
    total_sessions: int = 0
    completed_sessions: int = 0
    total_messages: int = 0
    avg_session_length: float = 0.0
    avg_response_time: float = 0.0
    learning_insights_count: int = 0


class DialogueSystem:
    """对话学习系统"""

    def __init__(
        self,
        node_id: str,
        node_agent: 'NodeAgent',
        knowledge_manager: 'KnowledgeManager'
    ):
        """
        初始化对话系统
        
        Args:
            node_id: 节点ID
            node_agent: 节点智能体
            knowledge_manager: 知识管理器
        """
        self.node_id = node_id
        self.node_agent = node_agent
        self.knowledge_manager = knowledge_manager
        
        # 会话管理
        self.sessions: Dict[str, DialogueSession] = {}
        self.active_sessions: Dict[str, DialogueContext] = {}
        self.session_history: Dict[str, List[DialogueSession]] = defaultdict(list)
        
        # 学习洞察
        self.insights: Dict[str, LearningInsight] = {}
        
        # 对话模板
        self.dialogue_templates: Dict[DialogueType, Dict[str, Any]] = self._init_templates()
        
        # 统计
        self.stats = DialogueStats()
        
        # 事件回调
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        logger.info(f"对话系统初始化: {node_id}")

    async def start(self):
        """启动对话系统"""
        # 启动会话清理任务
        asyncio.create_task(self._cleanup_loop())
        logger.info("✅ 对话系统启动")

    async def stop(self):
        """停止对话系统"""
        # 保存会话历史
        await self._save_sessions()
        logger.info("对话系统已停止")

    # ==================== 会话管理 ====================

    async def create_session(
        self,
        initiator_id: str,
        target_id: str,
        dialogue_type: DialogueType = DialogueType.KNOWLEDGE_QUERY,
        topic: Optional[str] = None
    ) -> Optional[DialogueSession]:
        """
        创建对话会话
        
        Args:
            initiator_id: 发起者ID
            target_id: 目标ID
            dialogue_type: 对话类型
            topic: 话题
            
        Returns:
            创建的会话
        """
        try:
            session_id = self._generate_session_id()
            
            session = DialogueSession(
                session_id=session_id,
                initiator_id=initiator_id,
                target_id=target_id,
                dialogue_type=dialogue_type,
                created_at=datetime.now(),
                status="active"
            )
            
            self.sessions[session_id] = session
            
            # 创建上下文
            context = DialogueContext(
                session_id=session_id,
                topic=topic
            )
            self.active_sessions[session_id] = context
            
            self.stats.total_sessions += 1
            
            logger.info(f"📝 对话会话创建: {session_id} ({dialogue_type.value})")
            
            # 触发事件
            await self._emit("session_created", session)
            
            return session
            
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return None

    async def send_message(
        self,
        session_id: str,
        message: DialogueMessage
    ) -> bool:
        """
        发送消息
        
        Args:
            session_id: 会话ID
            message: 消息
            
        Returns:
            是否成功
        """
        try:
            session = self.sessions.get(session_id)
            if not session or session.status != "active":
                return False
            
            # 添加消息到会话
            session.messages.append(message)
            
            # 更新上下文
            context = self.active_sessions.get(session_id)
            if context:
                context.current_depth += 1
                
                # 提取知识引用
                await self._extract_knowledge_refs(message, context)
                
                # 提取学习洞察
                await self._extract_learning_insights(message, session_id)
            
            self.stats.total_messages += 1
            
            # 触发事件
            await self._emit("message_sent", {
                "session_id": session_id,
                "message": message
            })
            
            logger.info(f"💬 消息发送: {session_id} ({message.message_type})")
            
            return True
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    async def receive_message(
        self,
        session_id: str,
        message: DialogueMessage
    ) -> bool:
        """
        接收消息
        
        Args:
            session_id: 会话ID
            message: 消息
            
        Returns:
            是否成功
        """
        # 接收消息与发送类似，但会触发不同的处理
        return await self.send_message(session_id, message)

    async def end_session(
        self,
        session_id: str,
        reason: str = "completed"
    ) -> bool:
        """
        结束会话
        
        Args:
            session_id: 会话ID
            reason: 结束原因
            
        Returns:
            是否成功
        """
        try:
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            session.status = reason
            session.ended_at = datetime.now()
            
            # 生成学习总结
            summary = await self._generate_learning_summary(session_id)
            session.learning_summary = summary
            
            # 移动到历史
            self.session_history[session_id].append(session)
            
            # 清理活跃上下文
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            self.stats.completed_sessions += 1
            
            logger.info(f"✅ 会话结束: {session_id} ({reason})")
            
            return True
            
        except Exception as e:
            logger.error(f"结束会话失败: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[DialogueSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def get_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[DialogueMessage]:
        """获取历史消息"""
        session = self.sessions.get(session_id)
        if session:
            return session.messages[-limit:]
        return []

    def get_session_count(self) -> int:
        """获取会话数量"""
        return len(self.sessions)

    # ==================== 对话处理 ====================

    async def process_query(
        self,
        session_id: str,
        query: str
    ) -> Optional[DialogueMessage]:
        """
        处理知识查询
        
        Args:
            session_id: 会话ID
            query: 查询内容
            
        Returns:
            响应消息
        """
        try:
            # 搜索相关知识
            results = await self.knowledge_manager.search(
                query=query,
                search_type="semantic",
                limit=5
            )
            
            # 生成响应
            if results:
                response_content = self._format_knowledge_response(results)
            else:
                response_content = "抱歉，我没有找到相关的知识。"
            
            response = DialogueMessage(
                sender_id=self.node_id,
                content=response_content,
                message_type="knowledge_response",
                timestamp=datetime.now()
            )
            
            await self.send_message(session_id, response)
            
            return response
            
        except Exception as e:
            logger.error(f"处理查询失败: {e}")
            return None

    async def process_debate(
        self,
        session_id: str,
        topic: str,
        position: str
    ) -> Optional[DialogueMessage]:
        """
        处理知识辩论
        
        Args:
            session_id: 会话ID
            topic: 辩题
            position: 立场
            
        Returns:
            响应消息
        """
        # 搜索相关知识
        results = await self.knowledge_manager.search(
            query=topic,
            limit=10
        )
        
        # 分析立场
        pro_args = []
        con_args = []
        
        for k in results:
            if position == "support":
                pro_args.append(k.content.content[:200])
            else:
                con_args.append(k.content.content[:200])
        
        response_content = self._format_debate_response(
            topic, position, pro_args, con_args
        )
        
        response = DialogueMessage(
            sender_id=self.node_id,
            content=response_content,
            message_type="debate_response"
        )
        
        await self.send_message(session_id, response)
        
        return response

    async def process_collaboration(
        self,
        session_id: str,
        task: str
    ) -> Optional[DialogueMessage]:
        """
        处理协作创作
        
        Args:
            session_id: 会话ID
            task: 任务描述
            
        Returns:
            响应消息
        """
        # 分析任务
        knowledge_ids = await self._analyze_collaboration_task(task)
        
        # 获取相关知识
        knowledge_pieces = []
        for kid in knowledge_ids:
            k = await self.knowledge_manager.get_knowledge(kid)
            if k:
                knowledge_pieces.append(k.content.to_dict())
        
        response_content = self._format_collaboration_response(
            task, knowledge_pieces
        )
        
        response = DialogueMessage(
            sender_id=self.node_id,
            content=response_content,
            message_type="collaboration_response"
        )
        
        await self.send_message(session_id, response)
        
        return response

    async def process_teaching(
        self,
        session_id: str,
        knowledge_id: str,
        teaching_style: str = "explanation"
    ) -> Optional[DialogueMessage]:
        """
        处理教学
        
        Args:
            session_id: 会话ID
            knowledge_id: 知识ID
            teaching_style: 教学风格
            
        Returns:
            响应消息
        """
        knowledge = await self.knowledge_manager.get_knowledge(knowledge_id)
        if not knowledge:
            return None
        
        # 根据教学风格调整内容
        if teaching_style == "simple":
            content = self._simplify_content(knowledge.content.content)
        elif teaching_style == "detailed":
            content = self._expand_content(knowledge.content.content)
        else:
            content = knowledge.content.content
        
        response = DialogueMessage(
            sender_id=self.node_id,
            content=content,
            message_type="teaching_response",
            learning_highlights=[knowledge_id]
        )
        
        await self.send_message(session_id, response)
        
        return response

    # ==================== 学习洞察 ====================

    async def _extract_knowledge_refs(
        self,
        message: DialogueMessage,
        context: DialogueContext
    ):
        """提取知识引用"""
        # 简化实现：查找 @knowledge_id 格式的引用
        import re
        
        refs = re.findall(r'@([a-zA-Z0-9]{32})', message.content)
        context.knowledge_ids.extend(refs)

    async def _extract_learning_insights(
        self,
        message: DialogueMessage,
        session_id: str
    ):
        """提取学习洞察"""
        # 简化实现：提取关键句子作为洞察
        sentences = message.content.split('。')
        
        for sentence in sentences:
            if len(sentence) > 20 and len(sentence) < 200:
                insight = LearningInsight(
                    insight_id=self._generate_insight_id(sentence),
                    content=sentence,
                    source_message_id=message.message_id,
                    confidence=0.7,
                    extracted_at=datetime.now()
                )
                
                self.insights[insight.insight_id] = insight
                self.stats.learning_insights_count += 1
                
                # 通知智能体
                await self.node_agent.learn_from_dialogue(message)

    async def _generate_learning_summary(self, session_id: str) -> str:
        """生成学习总结"""
        context = self.active_sessions.get(session_id)
        if not context:
            return ""
        
        insights = [
            i for i in self.insights.values()
            if i.source_message_id in [m.message_id for m in self.get_history(session_id)]
        ]
        
        summary_parts = []
        
        if context.topic:
            summary_parts.append(f"话题：{context.topic}")
        
        if context.knowledge_ids:
            summary_parts.append(f"涉及知识：{len(context.knowledge_ids)} 个")
        
        if insights:
            summary_parts.append(f"学习洞察：{len(insights)} 条")
        
        return "；".join(summary_parts) if summary_parts else "无特殊学习成果"

    # ==================== 辅助方法 ====================

    def _generate_session_id(self) -> str:
        """生成会话ID"""
        data = f"{self.node_id}{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:24]

    def _generate_insight_id(self, content: str) -> str:
        """生成洞察ID"""
        data = f"{content}{datetime.now().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:24]

    def _init_templates(self) -> Dict[DialogueType, Dict[str, Any]]:
        """初始化对话模板"""
        return {
            DialogueType.KNOWLEDGE_QUERY: {
                "name": "知识查询",
                "prompt": "回答用户关于知识的问题",
                "steps": ["理解问题", "搜索知识", "组织答案", "返回响应"]
            },
            DialogueType.KNOWLEDGE_DEBATE: {
                "name": "知识辩论",
                "prompt": "对知识进行辩论，支持或反驳",
                "steps": ["分析立场", "收集论据", "组织论证", "返回响应"]
            },
            DialogueType.KNOWLEDGE_COLLABORATE: {
                "name": "协作创作",
                "prompt": "与其他节点协作创作知识",
                "steps": ["分析任务", "分配工作", "整合内容", "生成成果"]
            },
            DialogueType.LEARNING_EXCHANGE: {
                "name": "学习交流",
                "prompt": "分享学习心得和经验",
                "steps": ["分享经验", "讨论心得", "提炼洞察", "更新知识"]
            },
            DialogueType.TEACHING: {
                "name": "教学指导",
                "prompt": "向其他节点传授知识",
                "steps": ["准备内容", "解释概念", "举例说明", "检验理解"]
            }
        }

    def _format_knowledge_response(self, knowledge_list: List[KnowledgeUnit]) -> str:
        """格式化知识响应"""
        lines = ["以下是相关的知识：\n"]
        
        for i, k in enumerate(knowledge_list, 1):
            lines.append(f"{i}. {k.content.title}")
            lines.append(f"   {k.content.summary or k.content.content[:100]}...")
            if k.is_verified:
                lines.append(f"   ✅ 已验证 ({k.verification_info.pass_rate:.0%})")
            lines.append("")
        
        return "\n".join(lines)

    def _format_debate_response(
        self,
        topic: str,
        position: str,
        pro_args: List[str],
        con_args: List[str]
    ) -> str:
        """格式化辩论响应"""
        lines = [f"关于「{topic}」的辩论：\n"]
        
        if position == "support":
            lines.append("支持论点：")
            for i, arg in enumerate(pro_args, 1):
                lines.append(f"  {i}. {arg}")
        else:
            lines.append("反对论点：")
            for i, arg in enumerate(con_args, 1):
                lines.append(f"  {i}. {arg}")
        
        return "\n".join(lines)

    def _format_collaboration_response(
        self,
        task: str,
        knowledge_pieces: List[Dict]
    ) -> str:
        """格式化协作响应"""
        lines = [f"协作任务「{task}」成果：\n"]
        lines.append(f"整合了 {len(knowledge_pieces)} 个知识片段\n")
        
        for kp in knowledge_pieces[:3]:
            lines.append(f"- {kp.get('title', '无标题')}")
        
        return "\n".join(lines)

    def _simplify_content(self, content: str) -> str:
        """简化内容"""
        sentences = content.split('。')
        return '。'.join(sentences[:2]) + '。'

    def _expand_content(self, content: str) -> str:
        """扩展内容"""
        return f"{content}\n\n补充说明：以上内容涉及多个知识点，我将逐一解释..."

    # ==================== 事件处理 ====================

    def on(self, event_name: str, handler: Callable):
        """注册事件处理器"""
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)

    async def _emit(self, event_name: str, data: Any):
        """触发事件"""
        if event_name in self._event_handlers:
            for handler in self._event_handlers[event_name]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"事件处理错误: {e}")

    # ==================== 后台任务 ====================

    async def _cleanup_loop(self):
        """清理循环"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟
                
                # 清理超时会话
                cutoff = datetime.now() - timedelta(hours=24)
                for session_id, session in list(self.sessions.items()):
                    if session.created_at < cutoff and session.status == "active":
                        await self.end_session(session_id, "timeout")
                
                # 清理过期洞察
                insight_cutoff = datetime.now() - timedelta(days=7)
                for iid, insight in list(self.insights.items()):
                    if insight.extracted_at < insight_cutoff and insight.applied:
                        del self.insights[iid]
                        
            except Exception as e:
                logger.error(f"清理循环错误: {e}")

    async def _save_sessions(self):
        """保存会话"""
        try:
            data = {
                sid: session.to_dict()
                for sid, session in self.sessions.items()
            }
            
            logger.info(f"保存 {len(data)} 个会话")
            
        except Exception as e:
            logger.error(f"保存会话失败: {e}")

    def get_stats(self) -> DialogueStats:
        """获取统计"""
        if self.stats.total_sessions > 0:
            self.stats.avg_session_length = (
                self.stats.total_messages / self.stats.total_sessions
            )
        return self.stats
