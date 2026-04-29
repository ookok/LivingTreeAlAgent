"""
LivingTreeAI Knowledge - 知识共享模块
=================================

知识类型：
1. 事实知识 - 可验证的客观信息
2. 推理模式 - 问题解决方法
3. 技能模型 - 特定任务处理能力
4. 元知识 - 如何学习的知识

知识共享协议：
- 自愿贡献
- 署名保护
- 开放授权
- 可验证来源

Author: Hermes Desktop Team
"""

import json
import hashlib
import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


class KnowledgeType(Enum):
    """知识类型"""
    FACT = "fact"                     # 事实知识
    REASONING_PATTERN = "reasoning"   # 推理模式
    SKILL = "skill"                   # 技能
    META = "meta"                     # 元知识


class KnowledgeLicense(Enum):
    """知识许可"""
    OPEN = "open"                     # 完全开放
    ATTRIBUTE = "attribute"           # 需要署名
    NON_COMMERCIAL = "non_commercial" # 非商业
    SHARE_ALIKE = "share_alike"       # 相同方式共享


@dataclass
class KnowledgeEntry:
    """知识条目"""
    knowledge_id: str
    knowledge_type: KnowledgeType
    title: str
    content: Any                      # 内容（可以是文本、模型权重等）
    source_node: str                  # 来源节点
    license: KnowledgeLicense

    # 元数据
    tags: List[str] = field(default_factory=list)
    domain: str = ""                   # 领域
    confidence: float = 1.0           # 可信度
    usage_count: int = 0              # 使用次数

    # 溯源
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = 1

    # 贡献者信息
    contributors: List[str] = field(default_factory=list)
    citation_format: str = ""         # 引用格式

    def to_dict(self) -> Dict:
        return {
            "knowledge_id": self.knowledge_id,
            "knowledge_type": self.knowledge_type.value,
            "title": self.title,
            "content": str(self.content)[:200] + "..." if len(str(self.content)) > 200 else str(self.content),
            "source_node": self.source_node,
            "license": self.license.value,
            "tags": self.tags,
            "domain": self.domain,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "contributors": self.contributors,
        }

    def get_hash(self) -> str:
        """获取内容哈希"""
        content_str = json.dumps(self.content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]


@dataclass
class KnowledgeQuery:
    """知识查询"""
    query_type: KnowledgeType = None  # 知识类型过滤
    domain: str = ""                   # 领域
    tags: List[str] = field(default_factory=list)
    min_confidence: float = 0.0        # 最低可信度
    keywords: List[str] = field(default_factory=list)
    limit: int = 10


@dataclass
class KnowledgeStats:
    """知识统计"""
    total_knowledge: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_domain: Dict[str, int] = field(default_factory=dict)
    total_contributions: int = 0
    network_knowledge_shared: int = 0


class KnowledgeBase:
    """
    本地知识库

    管理本地存储的知识条目
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.entries: Dict[str, KnowledgeEntry] = {}
        self.index_by_type: Dict[KnowledgeType, List[str]] = {kt: [] for kt in KnowledgeType}
        self.index_by_domain: Dict[str, List[str]] = {}

    def add(self, entry: KnowledgeEntry) -> str:
        """添加知识条目"""
        # 生成ID
        if not entry.knowledge_id:
            entry.knowledge_id = str(uuid.uuid4())[:12]

        # 添加到知识库
        self.entries[entry.knowledge_id] = entry

        # 更新索引
        self.index_by_type[entry.knowledge_type].append(entry.knowledge_id)

        if entry.domain:
            if entry.domain not in self.index_by_domain:
                self.index_by_domain[entry.domain] = []
            self.index_by_domain[entry.domain].append(entry.knowledge_id)

        return entry.knowledge_id

    def get(self, knowledge_id: str) -> Optional[KnowledgeEntry]:
        """获取知识条目"""
        return self.entries.get(knowledge_id)

    def query(self, query: KnowledgeQuery) -> List[KnowledgeEntry]:
        """查询知识"""
        results = []

        for entry in self.entries.values():
            # 类型过滤
            if query.query_type and entry.knowledge_type != query.query_type:
                continue

            # 领域过滤
            if query.domain and entry.domain != query.domain:
                continue

            # 可信度过滤
            if entry.confidence < query.min_confidence:
                continue

            # 标签过滤
            if query.tags:
                if not any(tag in entry.tags for tag in query.tags):
                    continue

            # 关键词过滤
            if query.keywords:
                content_str = str(entry.content).lower()
                title_str = entry.title.lower()
                if not any(
                    kw.lower() in content_str or kw.lower() in title_str
                    for kw in query.keywords
                ):
                    continue

            results.append(entry)

        # 按可信度和使用次数排序
        results.sort(
            key=lambda e: (e.confidence, e.usage_count),
            reverse=True
        )

        return results[:query.limit]

    def update(self, knowledge_id: str, content: Any, new_tags: List[str] = None) -> bool:
        """更新知识"""
        if knowledge_id not in self.entries:
            return False

        entry = self.entries[knowledge_id]
        entry.content = content
        entry.updated_at = time.time()
        entry.version += 1

        if new_tags:
            entry.tags = new_tags

        return True

    def delete(self, knowledge_id: str) -> bool:
        """删除知识"""
        if knowledge_id not in self.entries:
            return False

        entry = self.entries[knowledge_id]

        # 从索引移除
        if knowledge_id in self.index_by_type[entry.knowledge_type]:
            self.index_by_type[entry.knowledge_type].remove(knowledge_id)

        if entry.domain and knowledge_id in self.index_by_domain.get(entry.domain, []):
            self.index_by_domain[entry.domain].remove(knowledge_id)

        # 删除条目
        del self.entries[knowledge_id]
        return True

    def increment_usage(self, knowledge_id: str):
        """增加使用计数"""
        if knowledge_id in self.entries:
            self.entries[knowledge_id].usage_count += 1

    def get_stats(self) -> KnowledgeStats:
        """获取统计"""
        stats = KnowledgeStats()
        stats.total_knowledge = len(self.entries)
        stats.total_contributions = sum(e.usage_count for e in self.entries.values())

        for entry in self.entries.values():
            # 按类型统计
            kt = entry.knowledge_type.value
            stats.by_type[kt] = stats.by_type.get(kt, 0) + 1

            # 按领域统计
            if entry.domain:
                stats.by_domain[entry.domain] = stats.by_domain.get(entry.domain, 0) + 1

        return stats

    def export_for_sharing(self, knowledge_id: str) -> Dict:
        """导出知识用于共享"""
        entry = self.entries.get(knowledge_id)
        if not entry:
            return {}

        return {
            "knowledge_id": entry.knowledge_id,
            "knowledge_type": entry.knowledge_type.value,
            "title": entry.title,
            "content": entry.content,
            "source_node": entry.source_node,
            "license": entry.license.value,
            "tags": entry.tags,
            "domain": entry.domain,
            "confidence": entry.confidence,
            "created_at": entry.created_at,
            "version": entry.version,
        }

    def import_from_network(self, data: Dict, contributor_id: str) -> bool:
        """从网络导入知识"""
        try:
            entry = KnowledgeEntry(
                knowledge_id=data.get("knowledge_id", str(uuid.uuid4())[:12]),
                knowledge_type=KnowledgeType(data.get("knowledge_type", "fact")),
                title=data.get("title", ""),
                content=data.get("content", ""),
                source_node=data.get("source_node", "unknown"),
                license=KnowledgeLicense(data.get("license", "open")),
                tags=data.get("tags", []),
                domain=data.get("domain", ""),
                confidence=data.get("confidence", 0.5),
                created_at=data.get("created_at", time.time()),
                version=data.get("version", 1),
            )

            # 添加贡献者
            if contributor_id not in entry.contributors:
                entry.contributors.append(contributor_id)

            self.add(entry)
            return True

        except Exception as e:
            print(f"导入知识失败: {e}")
            return False


class KnowledgeShare:
    """
    知识共享管理器

    功能：
    - 知识发布和订阅
    - 知识同步
    - 冲突解决
    """

    def __init__(self, knowledge_base: KnowledgeBase, node_id: str):
        self.knowledge_base = knowledge_base
        self.node_id = node_id

        # 发布订阅
        self.subscribers: Dict[str, List[str]] = {}  # topic -> [node_id]
        self.subscriptions: List[str] = []           # 我订阅的主题

        # 待同步的知识
        self.pending_push: List[str] = []   # 待推送的知识ID
        self.pending_pull: List[str] = []  # 待拉取的知识ID

    def publish_knowledge(self, entry: KnowledgeEntry) -> str:
        """发布知识到网络"""
        # 确保来源正确
        entry.source_node = self.node_id

        # 添加到本地知识库
        knowledge_id = self.knowledge_base.add(entry)

        # 标记为待推送
        self.pending_push.append(knowledge_id)

        return knowledge_id

    def subscribe_topic(self, topic: str, subscriber_node: str):
        """订阅主题"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        if subscriber_node not in self.subscribers[topic]:
            self.subscribers[topic].append(subscriber_node)

    def unsubscribe_topic(self, topic: str, subscriber_node: str):
        """取消订阅"""
        if topic in self.subscribers:
            if subscriber_node in self.subscribers[topic]:
                self.subscribers[topic].remove(subscriber_node)

    def subscribe(self, topic: str):
        """订阅主题"""
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)

    def get_pending_push(self) -> List[Dict]:
        """获取待推送的知识"""
        result = []
        for kid in self.pending_push[:]:
            data = self.knowledge_base.export_for_sharing(kid)
            if data:
                result.append(data)
                self.pending_push.remove(kid)
        return result

    def get_pending_pull(self) -> List[str]:
        """获取待拉取的知识ID列表"""
        result = self.pending_pull.copy()
        self.pending_pull.clear()
        return result

    def add_pull_request(self, knowledge_id: str):
        """添加拉取请求"""
        if knowledge_id not in self.pending_pull:
            self.pending_pull.append(knowledge_id)

    def resolve_conflict(self, local: KnowledgeEntry, remote: Dict) -> KnowledgeEntry:
        """
        冲突解决策略

        策略：
        1. 版本号优先
        2. 可信度加权
        3. 最新更新优先
        """
        remote_entry = KnowledgeEntry(
            knowledge_id=remote.get("knowledge_id"),
            knowledge_type=KnowledgeType(remote.get("knowledge_type", "fact")),
            title=remote.get("title", ""),
            content=remote.get("content", ""),
            source_node=remote.get("source_node", "unknown"),
            license=KnowledgeLicense(remote.get("license", "open")),
            confidence=remote.get("confidence", 0.5),
            version=remote.get("version", 1),
            updated_at=remote.get("updated_at", 0),
        )

        # 比较版本和可信度
        if remote_entry.version > local.version:
            return remote_entry
        elif remote_entry.version == local.version:
            # 可信度加权
            if remote_entry.confidence > local.confidence:
                return remote_entry

        return local

    def get_share_summary(self) -> Dict:
        """获取共享摘要"""
        stats = self.knowledge_base.get_stats()
        return {
            "node_id": self.node_id,
            "total_knowledge": stats.total_knowledge,
            "pending_push": len(self.pending_push),
            "pending_pull": len(self.pending_pull),
            "subscribers": sum(len(v) for v in self.subscribers.values()),
            "subscriptions": len(self.subscriptions),
            "by_type": stats.by_type,
        }


if __name__ == "__main__":
    # 测试知识库
    kb = KnowledgeBase("test_node")

    # 添加知识
    entry = KnowledgeEntry(
        knowledge_id="fact_001",
        knowledge_type=KnowledgeType.FACT,
        title="水的沸点",
        content="在标准大气压下，水的沸点是100°C",
        source_node="test_node",
        license=KnowledgeLicense.OPEN,
        domain="science",
        tags=["物理", "化学"],
        confidence=0.99,
    )
    kb.add(entry)

    # 查询
    query = KnowledgeQuery(domain="science", limit=10)
    results = kb.query(query)
    print(f"查询结果: {len(results)} 条")

    for r in results:
        print(f"  - {r.title}: {r.content}")

    # 统计
    stats = kb.get_stats()
    print(f"\n统计: {stats.total_knowledge} 条知识")
