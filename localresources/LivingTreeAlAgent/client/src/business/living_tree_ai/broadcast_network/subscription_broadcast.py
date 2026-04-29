"""
Subscription Broadcast - 订阅制广播系统
======================================

功能：
- 订阅管理（板块/作者/关键词/类型）
- 智能洪泛传播
- 防环机制
- 分片广播

Author: LivingTreeAI Community
"""

import asyncio
import hashlib
import time
import random
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Set, Dict
from enum import Enum
from collections import defaultdict

from .content_types import Content, ContentType, ContentScope


class SubscriptionType(Enum):
    """订阅类型"""
    BOARD = "board"           # 板块订阅
    AUTHOR = "author"        # 作者关注
    KEYWORD = "keyword"      # 关键词订阅
    CONTENT_TYPE = "content_type"  # 内容类型订阅


@dataclass
class BoardSubscription:
    """板块订阅"""
    board: str
    node_id: str
    subscribed_at: float = field(default_factory=time.time)
    priority: int = 1  # 优先级


@dataclass
class AuthorSubscription:
    """作者订阅（关注）"""
    author: str
    node_id: str
    subscribed_at: float = field(default_factory=time.time)
    notifications_enabled: bool = True


@dataclass
class KeywordSubscription:
    """关键词订阅"""
    keyword: str
    node_id: str
    subscribed_at: float = field(default_factory=time.time)
    min_relevance: float = 0.5  # 最小相关度


class SubscriptionBroadcast:
    """
    订阅制广播系统

    功能：
    1. 多维度订阅（板块/作者/关键词/类型）
    2. 智能洪泛传播
    3. 防洪水攻击（分片广播）
    4. 防环机制
    """

    # 配置
    DEFAULT_TTL = 7  # 最大跳数
    FANOUT_COUNT = 3  # 每轮传播节点数
    MAX_CONTENT_SIZE = 1024 * 1024  # 1MB
    SHARD_SIZE = 64 * 1024  # 64KB 分片

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        sign_func: Optional[Callable[[Content], str]] = None,
    ):
        self.node_id = node_id

        # 订阅存储
        self.board_subscriptions: Dict[str, List[BoardSubscription]] = defaultdict(list)
        self.author_subscriptions: Dict[str, List[AuthorSubscription]] = defaultdict(list)
        self.keyword_subscriptions: List[KeywordSubscription] = []
        self.type_subscriptions: Dict[ContentType, Set[str]] = defaultdict(set)

        # 我的订阅
        self.my_boards: Set[str] = set()
        self.my_authors: Set[str] = set()
        self.my_keywords: List[str] = []

        # 内容缓存
        self.content_cache: Dict[str, Content] = {}
        self.recent_content_ids: Set[str] = set()

        # 已传播记录（防环）
        self.propagated: Set[str] = set()  # (content_id, node_id) 已传播过的

        # 网络函数
        self._send_func = send_func
        self._sign_func = sign_func or self._default_sign

        # 内容处理器
        self._handlers: Dict[str, Callable] = {}

        # 配置
        self.config = {
            "ttl": self.DEFAULT_TTL,
            "fanout_count": self.FANOUT_COUNT,
            "cache_size": 1000,
        }

    # ========== 签名 ==========

    def _default_sign(self, content: Content) -> str:
        """默认签名"""
        data = {
            "author": content.author,
            "title": content.title,
            "body": content.body,
            "timestamp": content.timestamp,
        }
        content_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()[:32]

    def sign_content(self, content: Content) -> str:
        """签名内容"""
        if not content.signature:
            content.signature = self._sign_func(content)
        return content.signature

    def verify_signature(self, content: Content) -> bool:
        """验证签名"""
        if not content.signature:
            return False
        expected = self._sign_func(content)
        return content.signature == expected

    # ========== 发布内容 ==========

    async def publish(
        self,
        content: Content,
        scope: Optional[ContentScope] = None,
    ) -> bool:
        """
        发布内容

        Args:
            content: 内容对象
            scope: 广播范围，为None时自动判断

        Returns:
            是否成功发布
        """
        # 1. 验证内容
        if not content.is_valid():
            return False

        # 2. 签名
        self.sign_content(content)

        # 3. 计算内容ID
        if not content.content_id:
            content.content_id = content.compute_id()

        # 4. 确定广播范围
        if scope is None:
            scope = content.scope

        targets = self._get_targets_for_scope(content, scope)

        # 5. 分片广播
        await self._sharded_broadcast(content, targets)

        # 6. 本地索引
        await self._index_content(content)

        # 7. 本地缓存
        self._cache_content(content)

        return True

    def _get_targets_for_scope(
        self,
        content: Content,
        scope: ContentScope
    ) -> List[str]:
        """获取目标节点列表"""
        if scope == ContentScope.SUBSCRIBERS:
            return self.get_subscribers_for_content(content)
        elif scope == ContentScope.BOARD:
            return self.get_board_subscribers(content.board)
        elif scope == ContentScope.RECIPIENTS:
            return content.recipients or []
        elif scope == ContentScope.PUBLIC:
            return self.get_public_broadcast_targets()
        elif scope == ContentScope.FOLLOWERS:
            return self.get_author_followers(content.author)
        return []

    async def _sharded_broadcast(self, content: Content, targets: List[str]):
        """分片广播（防洪水攻击）"""
        # 去重目标
        targets = list(set(targets) - {self.node_id})

        if not targets:
            return

        # 分片发送
        for i in range(0, len(targets), self.config["fanout_count"]):
            batch = targets[i:i + self.config["fanout_count"]]
            send_tasks = [
                self._send_content(target, content)
                for target in batch
            ]
            asyncio.create_task(asyncio.gather(*send_tasks, return_exceptions=True))

    async def _send_content(self, target: str, content: Content):
        """发送内容到目标节点"""
        if not self._send_func:
            return

        try:
            await self._send_func(target, {
                "type": "content",
                "content": content.to_dict(),
            })
        except Exception:
            pass

    # ========== 洪泛传播 ==========

    async def flood_content(
        self,
        content: Content,
        initial_targets: List[str],
        ttl: Optional[int] = None,
    ):
        """
        智能洪泛传播

        Args:
            content: 内容
            initial_targets: 初始目标节点
            ttl: 最大跳数
        """
        if ttl is None:
            ttl = self.config["ttl"]

        # 防环：已传播节点
        propagated = set(initial_targets)

        # 记录本节点已处理
        propagated.add(self.node_id)

        # 当前轮次目标
        current_targets = set(initial_targets)

        for hop in range(ttl):
            next_targets = set()

            for target in current_targets:
                # 获取邻居
                neighbors = await self._get_node_neighbors(target)

                for neighbor in neighbors:
                    if neighbor in propagated:
                        continue

                    # 检查是否可能感兴趣
                    if await self._might_be_interested(neighbor, content):
                        next_targets.add(neighbor)

            # 发送内容
            send_tasks = [
                self._send_content(target, content)
                for target in next_targets
            ]
            asyncio.create_task(asyncio.gather(*send_tasks, return_exceptions=True))

            propagated.update(next_targets)
            current_targets = next_targets

            # 指数退避
            if hop < ttl - 1:
                await asyncio.sleep(2 ** hop)

    async def _get_node_neighbors(self, node_id: str) -> List[str]:
        """获取节点的邻居节点"""
        # 简化实现：需要外部提供
        # 实际应该查询网络层获取邻居
        return []

    async def _might_be_interested(self, node_id: str, content: Content) -> bool:
        """判断节点是否可能对内容感兴趣"""
        # 检查订阅匹配

        # 板块匹配
        if content.board:
            subs = self.board_subscriptions.get(content.board, [])
            if any(s.node_id == node_id for s in subs):
                return True

        # 作者匹配
        subs = self.author_subscriptions.get(content.author, [])
        if any(s.node_id == node_id for s in subs):
            return True

        # 关键词匹配
        for keyword_sub in self.keyword_subscriptions:
            if keyword_sub.node_id == node_id:
                if keyword_sub.keyword in content.title or keyword_sub.keyword in content.body:
                    return True

        # 类型匹配
        if node_id in self.type_subscriptions.get(content.type, set()):
            return True

        return False

    # ========== 订阅管理 ==========

    def subscribe_board(self, board: str, node_id: Optional[str] = None):
        """订阅板块"""
        if node_id is None:
            node_id = self.node_id

        # 检查是否已订阅
        for sub in self.board_subscriptions[board]:
            if sub.node_id == node_id:
                return

        sub = BoardSubscription(board=board, node_id=node_id)
        self.board_subscriptions[board].append(sub)

        if node_id == self.node_id:
            self.my_boards.add(board)

    def unsubscribe_board(self, board: str, node_id: Optional[str] = None):
        """取消订阅板块"""
        if node_id is None:
            node_id = self.node_id

        self.board_subscriptions[board] = [
            s for s in self.board_subscriptions[board]
            if s.node_id != node_id
        ]

        if node_id == self.node_id:
            self.my_boards.discard(board)

    def subscribe_author(self, author: str, node_id: Optional[str] = None):
        """关注作者"""
        if node_id is None:
            node_id = self.node_id

        for sub in self.author_subscriptions[author]:
            if sub.node_id == node_id:
                return

        sub = AuthorSubscription(author=author, node_id=node_id)
        self.author_subscriptions[author].append(sub)

        if node_id == self.node_id:
            self.my_authors.add(author)

    def unsubscribe_author(self, author: str, node_id: Optional[str] = None):
        """取消关注作者"""
        if node_id is None:
            node_id = self.node_id

        self.author_subscriptions[author] = [
            s for s in self.author_subscriptions[author]
            if s.node_id != node_id
        ]

        if node_id == self.node_id:
            self.my_authors.discard(author)

    def subscribe_keyword(self, keyword: str, node_id: Optional[str] = None):
        """订阅关键词"""
        if node_id is None:
            node_id = self.node_id

        sub = KeywordSubscription(keyword=keyword, node_id=node_id)
        self.keyword_subscriptions.append(sub)

        if node_id == self.node_id:
            self.my_keywords.append(keyword)

    def subscribe_content_type(self, content_type: ContentType, node_id: Optional[str] = None):
        """订阅内容类型"""
        if node_id is None:
            node_id = self.node_id

        self.type_subscriptions[content_type].add(node_id)

    # ========== 查询 ==========

    def get_subscribers_for_content(self, content: Content) -> List[str]:
        """获取对内容感兴趣的订阅者"""
        subscribers = set()

        # 板块订阅者
        if content.board:
            for sub in self.board_subscriptions.get(content.board, []):
                subscribers.add(sub.node_id)

        # 作者关注者
        for sub in self.author_subscriptions.get(content.author, []):
            subscribers.add(sub.node_id)

        # 关键词订阅者
        for keyword_sub in self.keyword_subscriptions:
            if keyword_sub.keyword in content.title or keyword_sub.keyword in content.body:
                subscribers.add(keyword_sub.node_id)

        # 类型订阅者
        subscribers.update(self.type_subscriptions.get(content.type, set()))

        return list(subscribers - {self.node_id})

    def get_board_subscribers(self, board: str) -> List[str]:
        """获取板块订阅者"""
        return [s.node_id for s in self.board_subscriptions.get(board, [])]

    def get_author_followers(self, author: str) -> List[str]:
        """获取作者的关注者"""
        return [s.node_id for s in self.author_subscriptions.get(author, [])]

    def get_keyword_subscribers(self, keyword: str) -> List[str]:
        """获取关键词订阅者"""
        return [
            s.node_id for s in self.keyword_subscriptions
            if s.keyword == keyword
        ]

    def get_public_broadcast_targets(self) -> List[str]:
        """获取公开广播目标"""
        # 返回所有已知节点
        targets = set()
        for subs in self.board_subscriptions.values():
            targets.update(s.node_id for s in subs)
        return list(targets - {self.node_id})

    # ========== 内容处理 ==========

    async def handle_incoming_content(self, content_data: dict):
        """处理收到的内容"""
        content = Content.from_dict(content_data)

        # 检查重复
        if content.content_id in self.recent_content_ids:
            return

        # 验证签名
        if not self.verify_signature(content):
            return

        # 缓存
        self._cache_content(content)

        # 索引
        await self._index_content(content)

        # 调用处理器
        handler_key = f"content_{content.type.value}"
        if handler_key in self._handlers:
            handler = self._handlers[handler_key]
            if asyncio.iscoroutinefunction(handler):
                await handler(content)
            else:
                handler(content)

        # 继续传播
        asyncio.create_task(self._continue_propagation(content))

    async def _continue_propagation(self, content: Content):
        """继续传播内容"""
        # 获取感兴趣的新订阅者
        new_targets = self.get_subscribers_for_content(content)

        # 去除已传播的
        new_targets = [
            t for t in new_targets
            if (content.content_id, t) not in self.propagated
        ]

        if new_targets:
            await self.flood_content(content, new_targets, ttl=content.metadata.get("ttl", 3))

    def register_handler(self, content_type: ContentType, handler: Callable):
        """注册内容处理器"""
        self._handlers[f"content_{content_type.value}"] = handler

    # ========== 索引与缓存 ==========

    async def _index_content(self, content: Content):
        """索引内容（供外部调用）"""
        # 实际索引逻辑在 DistributedInvertedIndex 中
        pass

    def _cache_content(self, content: Content):
        """缓存内容"""
        # 限制缓存大小
        if len(self.content_cache) >= self.config["cache_size"]:
            # 清理最老的
            oldest = sorted(
                self.content_cache.items(),
                key=lambda x: x[1].timestamp
            )[:10]
            for content_id, _ in oldest:
                del self.content_cache[content_id]

        self.content_cache[content.content_id] = content
        self.recent_content_ids.add(content.content_id)

        # 限制最近ID集合大小
        if len(self.recent_content_ids) > self.config["cache_size"] * 2:
            self.recent_content_ids = set(list(self.recent_content_ids)[-self.config["cache_size"]:])

    def get_cached_content(self, content_id: str) -> Optional[Content]:
        """获取缓存内容"""
        return self.content_cache.get(content_id)

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "cached_content": len(self.content_cache),
            "board_subscriptions": {
                board: len(subs)
                for board, subs in self.board_subscriptions.items()
            },
            "author_subscriptions": {
                author: len(subs)
                for author, subs in self.author_subscriptions.items()
            },
            "keyword_subscriptions": len(self.keyword_subscriptions),
            "my_boards": list(self.my_boards),
            "my_authors": list(self.my_authors),
            "my_keywords": self.my_keywords,
        }


# 全局单例
_broadcast_instance: Optional[SubscriptionBroadcast] = None


def get_subscription_broadcast(node_id: str = "local") -> SubscriptionBroadcast:
    """获取订阅广播单例"""
    global _broadcast_instance
    if _broadcast_instance is None:
        _broadcast_instance = SubscriptionBroadcast(node_id)
    return _broadcast_instance