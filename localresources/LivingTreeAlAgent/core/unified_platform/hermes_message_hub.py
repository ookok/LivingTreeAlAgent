"""
Hermes Message Hub - 统一消息中心
==================================

所有会话消息通过 Hermes Agent 处理的核心模块。

功能：
1. 统一消息路由 - 所有消息经过 Hermes Agent
2. 平台消息适配 - 邮件/博客/论坛消息统一处理
3. 自动思考回复 - 节点对内容自动思考和回复
4. 增量同步 - 节点与中继服务器内容同步

Author: Hermes Desktop Team
"""

import json
import time
import uuid
import asyncio
import logging
import random
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class MessageSource(Enum):
    """消息来源"""
    USER = "user"              # 用户直接输入
    EMAIL = "email"            # 邮件
    BLOG = "blog"              # 博客
    FORUM = "forum"           # 论坛
    RELAY = "relay"           # 中继服务器
    SYSTEM = "system"          # 系统消息
    AUTO_REPLY = "auto_reply"  # 自动回复


class MessageIntent(Enum):
    """消息意图"""
    CHAT = "chat"              # 闲聊
    QUERY = "query"           # 查询
    COMMAND = "command"       # 命令
    REFLECTION = "reflection"  # 思考/反思
    REPLY = "reply"           # 回复
    PUBLISH = "publish"        # 发布


@dataclass
class UnifiedMessage:
    """统一消息格式"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: MessageSource = MessageSource.USER

    # 内容
    content: str = ""
    content_type: str = "text"  # text/html/markdown

    # 作者
    author_id: str = ""
    author_name: str = ""
    author_avatar: str = ""

    # 来源平台
    platform: str = ""        # email/blog/forum/relay
    platform_id: str = ""      # 原平台的消息ID

    # 元数据
    intent: MessageIntent = MessageIntent.CHAT
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 时间
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None  # 回复的消息ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "source": self.source.value,
            "content": self.content,
            "content_type": self.content_type,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "author_avatar": self.author_avatar,
            "platform": self.platform,
            "platform_id": self.platform_id,
            "intent": self.intent.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedMessage":
        data = dict(data)
        data["source"] = MessageSource(data.get("source", "user"))
        data["intent"] = MessageIntent(data.get("intent", "chat"))
        return cls(**data)


@dataclass
class ContentItem:
    """内容项（用于博客/论坛）"""
    content_id: str
    content_type: str  # blog_post / forum_post / forum_reply
    title: str
    content: str
    author_id: str
    author_name: str
    platform: str
    timestamp: float
    url: str = ""

    # 互动数据
    upvotes: int = 0
    downvotes: int = 0
    reply_count: int = 0

    # AI 处理标记
    ai_thought: Optional[str] = None
    ai_reply: Optional[str] = None
    ai_processed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content_id": self.content_id,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "platform": self.platform,
            "timestamp": self.timestamp,
            "url": self.url,
            "upvotes": self.upvotes,
            "downvotes": self.downvotes,
            "reply_count": self.reply_count,
            "ai_thought": self.ai_thought,
            "ai_reply": self.ai_reply,
            "ai_processed": self.ai_processed
        }


class HermesMessageHub:
    """
    Hermes 统一消息中心

    所有消息通过此中心处理，确保：
    1. 所有会话消息经过 Hermes Agent
    2. 统一的消息格式和路由
    3. 平台消息的适配和转换
    4. 自动思考回复功能

    使用示例：
        hub = HermesMessageHub()

        # 处理用户消息
        response = await hub.process_message(
            content="Hello",
            source=MessageSource.USER
        )

        # 处理平台消息
        hub.route_platform_message(
            platform="forum",
            platform_data=forum_post_data
        )
    """

    _instance: Optional['HermesMessageHub'] = None

    def __init__(self):
        self._initialized = False

        # Hermes Agent
        self.agent = None

        # 消息历史
        self.messages: List[UnifiedMessage] = []
        self.max_messages = 1000

        # 内容库（从各平台收集）
        self.content_library: Dict[str, ContentItem] = {}  # content_id -> ContentItem
        self.last_sync: Dict[str, float] = {}  # platform -> last_sync_time

        # 消息处理器
        self._handlers: Dict[MessageSource, Callable] = {}

        # 回调
        self.on_message_processed: Optional[Callable] = None
        self.on_auto_reply: Optional[Callable] = None

        # 自动思考回复配置
        self.auto_reply_enabled = False
        self.auto_reply_probability = 0.3  # 30% 概率自动回复

        # 待处理队列
        self._pending_replies: List[ContentItem] = []

    @classmethod
    def get_instance(cls) -> 'HermesMessageHub':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self, agent=None):
        """初始化"""
        if self._initialized:
            return

        self.agent = agent

        # 注册默认处理器
        self._handlers[MessageSource.USER] = self._handle_user_message
        self._handlers[MessageSource.EMAIL] = self._handle_platform_message
        self._handlers[MessageSource.BLOG] = self._handle_platform_message
        self._handlers[MessageSource.FORUM] = self._handle_platform_message
        self._handlers[MessageSource.RELAY] = self._handle_relay_message

        self._initialized = True
        logger.info("HermesMessageHub initialized")

    def register_handler(self, source: MessageSource, handler: Callable):
        """注册消息处理器"""
        self._handlers[source] = handler

    async def process_message(
        self,
        content: str,
        source: MessageSource = MessageSource.USER,
        author_id: str = "",
        author_name: str = "User",
        platform: str = "",
        metadata: Dict[str, Any] = None,
        **kwargs
    ) -> UnifiedMessage:
        """
        处理消息

        Args:
            content: 消息内容
            source: 消息来源
            author_id: 作者ID
            author_name: 作者名称
            platform: 来源平台
            metadata: 额外元数据

        Returns:
            处理后的消息
        """
        # 创建统一消息
        msg = UnifiedMessage(
            content=content,
            source=source,
            author_id=author_id,
            author_name=author_name,
            platform=platform,
            metadata=metadata or {},
            **kwargs
        )

        # 添加到历史
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

        # 获取处理器
        handler = self._handlers.get(source, self._handle_default)

        # 处理消息
        try:
            result = await handler(msg)
            if asyncio.iscoroutine(result):
                result = await result
        except Exception as e:
            logger.error(f"Message handler error: {e}")
            result = msg

        # 触发回调
        if self.on_message_processed:
            try:
                self.on_message_processed(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return result

    async def _handle_user_message(self, msg: UnifiedMessage) -> UnifiedMessage:
        """处理用户消息"""
        logger.debug(f"Processing user message: {msg.content[:50]}...")

        # 确定意图
        msg.intent = self._classify_intent(msg.content)

        # 如果有 Hermes Agent，调用它
        if self.agent:
            try:
                # 构建提示
                prompt = self._build_prompt(msg)

                # 调用 Agent
                if hasattr(self.agent, 'run_conversation'):
                    response = await self.agent.run_conversation(prompt)
                    msg.metadata["agent_response"] = response
                elif hasattr(self.agent, 'generate'):
                    response = await self.agent.generate(prompt)
                    msg.metadata["agent_response"] = response
            except Exception as e:
                logger.error(f"Agent error: {e}")
                msg.metadata["agent_error"] = str(e)

        return msg

    async def _handle_platform_message(self, msg: UnifiedMessage) -> UnifiedMessage:
        """处理平台消息（邮件/博客/论坛）"""
        logger.debug(f"Processing platform message from {msg.platform}: {msg.content[:50]}...")

        # 将平台消息添加到内容库
        content_item = ContentItem(
            content_id=msg.platform_id or msg.msg_id,
            content_type=f"{msg.platform}_post",
            title=msg.metadata.get("title", ""),
            content=msg.content,
            author_id=msg.author_id,
            author_name=msg.author_name,
            platform=msg.platform,
            timestamp=msg.timestamp
        )
        self.content_library[content_item.content_id] = content_item

        # 标记为需要 AI 处理
        if self.auto_reply_enabled:
            self._pending_replies.append(content_item)

        return msg

    async def _handle_relay_message(self, msg: UnifiedMessage) -> UnifiedMessage:
        """处理中继服务器消息"""
        # 转发到 Hermes Agent
        return await self._handle_user_message(msg)

    async def _handle_default(self, msg: UnifiedMessage) -> UnifiedMessage:
        """默认处理器"""
        return msg

    def _classify_intent(self, content: str) -> MessageIntent:
        """分类消息意图"""
        content_lower = content.lower()

        # 命令
        if content_lower.startswith("/"):
            return MessageIntent.COMMAND

        # 查询
        if any(kw in content_lower for kw in ["查", "找", "什么", "怎么", "如何"]):
            return MessageIntent.QUERY

        # 回复
        if content_lower.startswith("回复", "re:", "回复:"):
            return MessageIntent.REPLY

        # 思考/反思
        if any(kw in content_lower for kw in ["思考", "反思", "想法", "认为"]):
            return MessageIntent.REFLECTION

        # 默认闲聊
        return MessageIntent.CHAT

    def _build_prompt(self, msg: UnifiedMessage) -> str:
        """构建 Agent 提示"""
        prompt_parts = []

        # 上下文
        if msg.author_name:
            prompt_parts.append(f"[{msg.author_name}]: {msg.content}")
        else:
            prompt_parts.append(msg.content)

        # 平台上下文
        if msg.platform:
            platform_names = {
                "email": "邮件",
                "blog": "博客",
                "forum": "论坛"
            }
            prompt_parts.append(f"(来自{platform_names.get(msg.platform, msg.platform)}平台)")

        return "\n".join(prompt_parts)

    # ==================== 平台消息路由 ====================

    async def route_platform_message(
        self,
        platform: str,
        platform_data: Dict[str, Any]
    ) -> UnifiedMessage:
        """
        路由平台消息到统一消息中心

        Args:
            platform: 平台类型 (email/blog/forum)
            platform_data: 平台原始数据

        Returns:
            统一消息
        """
        # 转换平台消息为统一格式
        source_map = {
            "email": MessageSource.EMAIL,
            "blog": MessageSource.BLOG,
            "forum": MessageSource.FORUM
        }

        msg = UnifiedMessage(
            source=source_map.get(platform, MessageSource.USER),
            content=platform_data.get("content", platform_data.get("body", "")),
            content_type=platform_data.get("content_type", "text"),
            author_id=platform_data.get("author_id", platform_data.get("from_id", "")),
            author_name=platform_data.get("author_name", platform_data.get("from_name", "Anonymous")),
            platform=platform,
            platform_id=platform_data.get("id", ""),
            metadata={
                "title": platform_data.get("title", ""),
                "topic": platform_data.get("topic", ""),
                "raw_data": platform_data
            }
        )

        return await self.process_message(
            content=msg.content,
            source=msg.source,
            author_id=msg.author_id,
            author_name=msg.author_name,
            platform=msg.platform,
            metadata=msg.metadata,
            intent=msg.intent,
            platform_id=msg.platform_id
        )

    # ==================== 自动思考回复 ====================

    def enable_auto_reply(self, probability: float = 0.3):
        """启用自动思考回复"""
        self.auto_reply_enabled = True
        self.auto_reply_probability = probability
        logger.info(f"Auto reply enabled (probability: {probability})")

    def disable_auto_reply(self):
        """禁用自动思考回复"""
        self.auto_reply_enabled = False
        logger.info("Auto reply disabled")

    async def trigger_auto_reply(self, content_item: ContentItem = None) -> Optional[str]:
        """
        触发自动思考回复

        Args:
            content_item: 指定的内容项，如不指定则随机选择

        Returns:
            生成的回复内容
        """
        if not self.auto_reply_enabled:
            return None

        # 随机选择或使用指定内容
        if content_item is None:
            pending = [c for c in self._pending_replies if not c.ai_processed]
            if not pending:
                # 从内容库随机选一条未处理的
                unprocessed = [c for c in self.content_library.values() if not c.ai_processed]
                if not unprocessed:
                    return None
                content_item = random.choice(unprocessed)
            else:
                content_item = random.choice(pending)

        # 随机概率决定是否回复
        if random.random() > self.auto_reply_probability:
            logger.debug(f"Skipping auto reply for {content_item.content_id} (probability)")
            return None

        # 生成思考
        thought = await self._generate_thought(content_item)
        content_item.ai_thought = thought

        # 生成回复
        reply = await self._generate_reply(content_item)
        content_item.ai_reply = reply
        content_item.ai_processed = True

        logger.info(f"Auto reply generated for {content_item.content_id}: {reply[:50]}...")

        # 触发回调
        if self.on_auto_reply:
            try:
                self.on_auto_reply(content_item, thought, reply)
            except Exception as e:
                logger.error(f"Auto reply callback error: {e}")

        return reply

    async def _generate_thought(self, content: ContentItem) -> str:
        """生成 AI 思考"""
        if not self.agent:
            return "这是一个值得思考的内容。"

        try:
            prompt = f"""请对以下内容进行深度思考，分析其价值和意义：

标题：{content.title}
内容：{content.content[:500]}

请从以下几个角度进行分析：
1. 内容的核心观点是什么？
2. 有什么独特见解或价值？
3. 可能存在的问题或争议点？

请用简洁的语言表达你的思考。"""

            if hasattr(self.agent, 'run_conversation'):
                thought = await self.agent.run_conversation(prompt)
            elif hasattr(self.agent, 'generate'):
                thought = await self.agent.generate(prompt)
            else:
                thought = "深度思考中..."
        except Exception as e:
            logger.error(f"Thought generation error: {e}")
            thought = "思考中..."

        return thought

    async def _generate_reply(self, content: ContentItem) -> str:
        """生成 AI 回复"""
        if not self.agent:
            return "感谢分享！"

        try:
            prompt = f"""请为以下内容生成一条有价值的回复：

标题：{content.title}
内容：{content.content[:500]}

要求：
1. 回复要有深度，不能只是表面恭维
2. 可以补充观点、提出问题或分享相关经验
3. 语言自然，像真实的人类回复
4. 长度适中（50-200字）

回复："""

            if hasattr(self.agent, 'run_conversation'):
                reply = await self.agent.run_conversation(prompt)
            elif hasattr(self.agent, 'generate'):
                reply = await self.agent.generate(prompt)
            else:
                reply = "感谢分享，受益匪浅！"
        except Exception as e:
            logger.error(f"Reply generation error: {e}")
            reply = "感谢分享！"

        return reply

    # ==================== 增量同步 ====================

    async def sync_from_relay(self, relay_data: Dict[str, Any]) -> List[ContentItem]:
        """
        从中继服务器同步内容

        Args:
            relay_data: 中继服务器返回的数据

        Returns:
            新增的内容列表
        """
        new_items = []
        items = relay_data.get("items", [])

        for item_data in items:
            content_id = item_data.get("content_id")
            if content_id in self.content_library:
                continue

            item = ContentItem(
                content_id=content_id,
                content_type=item_data.get("content_type", ""),
                title=item_data.get("title", ""),
                content=item_data.get("content", ""),
                author_id=item_data.get("author_id", ""),
                author_name=item_data.get("author_name", ""),
                platform=item_data.get("platform", ""),
                timestamp=item_data.get("timestamp", time.time()),
                url=item_data.get("url", ""),
                upvotes=item_data.get("upvotes", 0),
                downvotes=item_data.get("downvotes", 0),
                reply_count=item_data.get("reply_count", 0)
            )

            self.content_library[content_id] = item
            self.last_sync[item.platform] = time.time()
            new_items.append(item)

            # 标记为待自动回复
            if self.auto_reply_enabled:
                self._pending_replies.append(item)

        logger.info(f"Synced {len(new_items)} new items from relay")
        return new_items

    async def publish_to_relay(
        self,
        title: str,
        content: str,
        content_type: str = "forum_post",
        platform: str = "forum",
        author_id: str = "",
        author_name: str = ""
    ) -> Dict[str, Any]:
        """
        发布内容到中继服务器

        Args:
            title: 标题
            content: 内容
            content_type: 内容类型
            platform: 平台
            author_id: 作者ID
            author_name: 作者名称

        Returns:
            发布结果
        """
        content_id = str(uuid.uuid4())

        item = ContentItem(
            content_id=content_id,
            content_type=content_type,
            title=title,
            content=content,
            author_id=author_id,
            author_name=author_name,
            platform=platform,
            timestamp=time.time()
        )

        # 添加到本地库
        self.content_library[content_id] = item

        # 准备发送到中继服务器的数据
        relay_payload = {
            "action": "publish",
            "content_id": content_id,
            "title": title,
            "content": content,
            "content_type": content_type,
            "platform": platform,
            "author_id": author_id,
            "author_name": author_name,
            "timestamp": time.time()
        }

        return {
            "success": True,
            "content_id": content_id,
            "item": item,
            "relay_payload": relay_payload
        }

    def get_pending_count(self) -> int:
        """获取待处理数量"""
        return len([c for c in self._pending_replies if not c.ai_processed])

    def get_content_by_platform(self, platform: str) -> List[ContentItem]:
        """获取指定平台的内容"""
        return [
            c for c in self.content_library.values()
            if c.platform == platform
        ]

    def get_recent_content(self, limit: int = 50) -> List[ContentItem]:
        """获取最近的内容"""
        items = list(self.content_library.values())
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items[:limit]

    def get_unprocessed_content(self) -> List[ContentItem]:
        """获取未处理的内容"""
        return [
            c for c in self.content_library.values()
            if not c.ai_processed
        ]
