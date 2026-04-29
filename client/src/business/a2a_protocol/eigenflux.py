"""
EigenFlux 增强模块
==================
借鉴 EigenFlux 设计理念，增强 A2A 通信层的信号广播与智能匹配能力。

核心理念：
1. 信号广播机制：Agent 广播 KNOWLEDGE / NEED / CAPABILITY
2. 智能信号匹配：网络只传递相关信号，减少信息过载
3. 语义匹配：基于向量嵌入的语义相似度匹配
4. 开放标准：任何 Agent 都可以加入，不同框架可互操作

Author: LivingTree AI Agent
Date: 2026-04-29
"""

import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Generic
from collections import defaultdict
import threading
import json

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ==================== 信号类型定义 ====================

class SignalType(Enum):
    """EigenFlux 信号类型枚举"""
    KNOWLEDGE = "knowledge"      # 知识信号：我知道什么
    NEED = "need"                # 需求信号：我需要什么
    CAPABILITY = "capability"    # 能力信号：我能做什么
    TASK = "task"                # 任务信号：有任务要处理
    BROADCAST = "broadcast"      # 通用广播


class SignalPriority(Enum):
    """信号优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SignalMetadata:
    """信号元数据"""
    signal_id: str
    signal_type: SignalType
    sender_id: str
    timestamp: float = field(default_factory=time.time)
    ttl: int = 300  # 生存时间（秒）
    priority: SignalPriority = SignalPriority.NORMAL
    keywords: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)
    embedding: Optional[List[float]] = None  # 语义向量
    reliability: float = 1.0  # 可靠性 0-1
    audience: Optional[Set[str]] = None  # 指定接收者（None=所有人）
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl
    
    def to_dict(self) -> Dict:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "priority": self.priority.value,
            "keywords": self.keywords,
            "tags": list(self.tags),
            "embedding": self.embedding,
            "reliability": self.reliability,
        }


@dataclass
class Signal:
    """EigenFlux 信号"""
    metadata: SignalMetadata
    payload: Dict[str, Any]
    
    @classmethod
    def create(cls, signal_type: SignalType, sender_id: str, 
                payload: Dict[str, Any], **kwargs) -> "Signal":
        """创建信号的工厂方法"""
        signal_id = hashlib.sha256(
            f"{sender_id}{time.time()}{signal_type.value}".encode()
        ).hexdigest()[:16]
        
        metadata = SignalMetadata(
            signal_id=signal_id,
            signal_type=signal_type,
            sender_id=sender_id,
            **kwargs
        )
        return cls(metadata=metadata, payload=payload)
    
    def to_dict(self) -> Dict:
        return {
            "metadata": self.metadata.to_dict(),
            "payload": self.payload,
        }


# ==================== 订阅者与过滤器 ====================

@dataclass
class Subscriber:
    """信号订阅者"""
    subscriber_id: str
    interests: Set[str] = field(default_factory=set)  # 感兴趣的关键词
    capabilities: Set[str] = field(default_factory=set)  # 自身能力
    signal_types: Set[SignalType] = field(default_factory=set)  # 感兴趣的信号类型
    callback: Callable[[Signal], None] = field(default=None)
    embedding: Optional[List[float]] = None  # 语义向量
    is_active: bool = True
    
    def matches(self, signal: Signal) -> bool:
        """检查订阅者是否匹配某个信号"""
        # 检查信号类型
        if signal.metadata.signal_type not in self.signal_types:
            return False
        
        # 检查指定受众
        if signal.metadata.audience:
            if self.subscriber_id not in signal.metadata.audience:
                return False
        
        # 检查关键词匹配
        if self.interests:
            signal_keywords = set(signal.metadata.keywords) | signal.metadata.tags
            if not signal_keywords & self.interests:  # 无交集
                # 检查语义相似度
                if self.embedding and signal.metadata.embedding and HAS_NUMPY:
                    similarity = self._cosine_similarity(
                        self.embedding, signal.metadata.embedding
                    )
                    return similarity > 0.7
                return False
        
        return True
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if not HAS_NUMPY or not a or not b:
            return 0.0
        a = np.array(a)
        b = np.array(b)
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return dot / norm if norm > 0 else 0.0


# ==================== 信号匹配引擎 ====================

class SignalMatchEngine(ABC):
    """信号匹配引擎抽象基类"""
    
    @abstractmethod
    def match(self, signal: Signal, subscribers: List[Subscriber]) -> List[Subscriber]:
        """匹配信号与订阅者"""
        pass


class SemanticMatcher(SignalMatchEngine):
    """语义匹配器 - 基于向量嵌入"""
    
    def __init__(self, similarity_threshold: float = 0.7):
        self.threshold = similarity_threshold
    
    def match(self, signal: Signal, subscribers: List[Subscriber]) -> List[Subscriber]:
        if not signal.metadata.embedding:
            return subscribers  # 无嵌入向量，返回所有订阅者
        
        results = []
        for sub in subscribers:
            if not sub.is_active:
                continue
            if sub.embedding and HAS_NUMPY:
                similarity = self._cosine_similarity(
                    sub.embedding, signal.metadata.embedding
                )
                if similarity >= self.threshold:
                    results.append(sub)
            else:
                results.append(sub)  # 无嵌入向量，信任其他匹配
        
        return results
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not HAS_NUMPY:
            return 0.0
        a, b = np.array(a), np.array(b)
        dot, norm = np.dot(a, b), np.linalg.norm(a) * np.linalg.norm(b)
        return dot / norm if norm > 0 else 0.0


class KeywordMatcher(SignalMatchEngine):
    """关键词匹配器"""
    
    def match(self, signal: Signal, subscribers: List[Subscriber]) -> List[Subscriber]:
        signal_keywords = set(signal.metadata.keywords) | signal.metadata.tags
        
        if not signal_keywords:
            return subscribers
        
        results = []
        for sub in subscribers:
            if not sub.is_active:
                continue
            # 关键词或兴趣匹配
            if sub.interests & signal_keywords:
                results.append(sub)
        
        return results


class CapabilityMatcher(SignalMatchEngine):
    """能力匹配器 - 用于 NEED -> CAPABILITY 匹配"""
    
    def match(self, signal: Signal, subscribers: List[Subscriber]) -> List[Subscriber]:
        if signal.metadata.signal_type != SignalType.NEED:
            return subscribers
        
        # 从 payload 中提取需要的技能
        needed_skills = set()
        if "required_skills" in signal.payload:
            needed_skills = set(signal.payload["required_skills"])
        if "task_type" in signal.payload:
            needed_skills.add(signal.payload["task_type"])
        
        if not needed_skills:
            return subscribers
        
        results = []
        for sub in subscribers:
            if not sub.is_active:
                continue
            # 检查订阅者能力是否满足需求
            if sub.capabilities & needed_skills:
                results.append(sub)
        
        return results


class InterestMatcher(SignalMatchEngine):
    """兴趣匹配器 - 用于 KNOWLEDGE -> Interest 匹配"""
    
    def match(self, signal: Signal, subscribers: List[Subscriber]) -> List[Subscriber]:
        if signal.metadata.signal_type != SignalType.KNOWLEDGE:
            return subscribers
        
        results = []
        for sub in subscribers:
            if not sub.is_active:
                continue
            # 检查订阅者是否对此知识感兴趣
            signal_domain = signal.payload.get("domain", "")
            if signal_domain in sub.interests:
                results.append(sub)
            elif sub.interests & signal.metadata.keywords:
                results.append(sub)
        
        return results


class CompositeMatcher(SignalMatchEngine):
    """组合匹配器 - 组合多种匹配策略"""
    
    def __init__(self, matchers: List[SignalMatchEngine] = None):
        self.matchers = matchers or [
            KeywordMatcher(),
            SemanticMatcher(),
            CapabilityMatcher(),
            InterestMatcher(),
        ]
    
    def match(self, signal: Signal, subscribers: List[Subscriber]) -> List[Subscriber]:
        results = set()
        for matcher in self.matchers:
            matched = matcher.match(signal, subscribers)
            results.update(matched)
        return list(results)


# ==================== LRU 缓存实现 ====================

from functools import lru_cache
from collections import OrderedDict
from typing import Tuple


class LRUCache(Generic[T]):
    """轻量级 LRU 缓存"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self._cache:
            self._hits += 1
            self._cache.move_to_end(key)
            return self._cache[key]
        self._misses += 1
        return None
    
    def put(self, key: str, value: Any):
        """放入缓存"""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
    
    def invalidate(self, key: str):
        """使缓存失效"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
        }


class SignalCache:
    """
    信号缓存 - 减少重复信号处理
    ==================
    特性：
    1. LRU 淘汰策略
    2. 信号指纹去重
    3. 批量预热
    """
    
    def __init__(self, max_size: int = 5000):
        self._cache: LRUCache = LRUCache(max_size)
        self._signal_fingerprints: Set[str] = set()
        self._lock = threading.Lock()
    
    def _compute_fingerprint(self, signal: Signal) -> str:
        """计算信号指纹（用于去重）"""
        content = json.dumps({
            "type": signal.metadata.signal_type.value,
            "sender": signal.metadata.sender_id,
            "payload": signal.payload,
            "keywords": sorted(signal.metadata.keywords),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def is_duplicate(self, signal: Signal) -> bool:
        """检查是否为重复信号"""
        fp = self._compute_fingerprint(signal)
        with self._lock:
            return fp in self._signal_fingerprints
    
    def add(self, signal: Signal):
        """添加信号到缓存"""
        fp = self._compute_fingerprint(signal)
        with self._lock:
            self._signal_fingerprints.add(fp)
            # 缓存信号内容用于快速检索
            self._cache.put(fp, signal)
    
    def get(self, fingerprint: str) -> Optional[Signal]:
        """获取缓存信号"""
        return self._cache.get(fingerprint)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            return {
                "fingerprints": len(self._signal_fingerprints),
                "cache": self._cache.get_stats(),
            }
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._signal_fingerprints.clear()
            self._cache.clear()


# ==================== 批量处理 ====================

class BatchProcessor:
    """
    批量处理器 - 提升信号处理吞吐量
    ==================
    特性：
    1. 信号批量收集
    2. 批量匹配
    3. 异步批量投递
    """
    
    def __init__(self, bus: "SignalBus", batch_size: int = 50, 
                 batch_interval: float = 0.1):
        self._bus = bus
        self._batch_size = batch_size
        self._batch_interval = batch_interval
        self._pending_signals: List[Signal] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._stats = {
            "batches_processed": 0,
            "signals_batched": 0,
            "signals_flushed": 0,
        }
    
    def add(self, signal: Signal) -> bool:
        """
        添加信号到批处理队列
        返回 True 表示已触发批量处理
        """
        with self._lock:
            self._pending_signals.append(signal)
            self._stats["signals_batched"] += 1
            
            # 检查是否需要触发批量处理
            if (len(self._pending_signals) >= self._batch_size or
                time.time() - self._last_flush >= self._batch_interval):
                self._flush()
                return True
        return False
    
    def _flush(self):
        """执行批量处理"""
        if not self._pending_signals:
            return
        
        signals = self._pending_signals[:]
        self._pending_signals.clear()
        self._last_flush = time.time()
        self._stats["batches_processed"] += 1
        
        # 在锁外执行批量匹配和投递
        total_delivered = 0
        subscribers = self._bus.get_subscribers()
        
        for signal in signals:
            matched = self._bus._match_engine.match(signal, subscribers)
            for sub in matched:
                if sub.callback:
                    try:
                        sub.callback(signal)
                        total_delivered += 1
                    except Exception as e:
                        print(f"[BatchProcessor] Callback error: {e}")
        
        self._stats["signals_flushed"] += total_delivered
    
    def force_flush(self):
        """强制刷新待处理信号"""
        with self._lock:
            self._flush()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批处理统计"""
        with self._lock:
            return {
                **self._stats,
                "pending": len(self._pending_signals),
                "avg_batch_size": (
                    self._stats["signals_batched"] / self._stats["batches_processed"]
                    if self._stats["batches_processed"] > 0 else 0
                ),
            }


# ==================== 信号总线 ====================

class SignalBus:
    """
    EigenFlux 信号总线
    ==================
    核心组件，负责信号的广播与智能路由。
    
    特点：
    1. 广播式发送，无需知道接收者
    2. 智能匹配，只将信号传递给感兴趣的订阅者
    3. 支持多种信号类型和匹配策略
    4. 去中心化，任何 Agent 都可以接入
    """
    
    def __init__(self, name: str = "default",
                 cache_size: int = 5000,
                 batch_size: int = 50,
                 batch_interval: float = 0.1,
                 enable_batch: bool = True,
                 enable_cache: bool = True):
        self.name = name
        self._subscribers: Dict[str, Subscriber] = {}
        self._match_engine = CompositeMatcher()
        self._signal_history: List[Signal] = []
        self._max_history = 1000
        self._lock = threading.RLock()
        
        # 性能优化组件
        self._enable_cache = enable_cache
        self._enable_batch = enable_batch
        self._cache = SignalCache(cache_size) if enable_cache else None
        self._batch_processor = BatchProcessor(
            self, batch_size, batch_interval
        ) if enable_batch else None
        
        self._stats = {
            "signals_sent": 0,
            "signals_delivered": 0,
            "signals_filtered": 0,
            "signals_cached": 0,
            "signals_duplicates": 0,
        }
        
        # 回调钩子
        self._on_signal_broadcast: Optional[Callable[[Signal], None]] = None
        self._on_signal_delivered: Optional[Callable[[Signal, Subscriber], None]] = None
    
    # ==================== 订阅管理 ====================
    
    def subscribe(self, subscriber: Subscriber) -> bool:
        """订阅信号"""
        with self._lock:
            if subscriber.subscriber_id in self._subscribers:
                return False  # 已存在
            self._subscribers[subscriber.subscriber_id] = subscriber
            return True
    
    def unsubscribe(self, subscriber_id: str) -> bool:
        """取消订阅"""
        with self._lock:
            if subscriber_id in self._subscribers:
                del self._subscribers[subscriber_id]
                return True
            return False
    
    def get_subscribers(self) -> List[Subscriber]:
        """获取所有活跃订阅者"""
        with self._lock:
            return [s for s in self._subscribers.values() if s.is_active]
    
    def update_subscriber(self, subscriber_id: str, **kwargs) -> bool:
        """更新订阅者信息"""
        with self._lock:
            if subscriber_id not in self._subscribers:
                return False
            sub = self._subscribers[subscriber_id]
            for key, value in kwargs.items():
                if hasattr(sub, key):
                    setattr(sub, key, value)
            return True
    
    # ==================== 信号广播 ====================
    
    def broadcast(self, signal: Signal, use_cache: bool = True) -> int:
        """
        广播信号到匹配的订阅者
        
        参数：
            signal: 要广播的信号
            use_cache: 是否使用缓存去重（默认 True）
        
        返回：成功传递的订阅者数量
        """
        # 缓存去重检查
        if use_cache and self._cache:
            if self._cache.is_duplicate(signal):
                self._stats["signals_duplicates"] += 1
                return 0  # 重复信号，跳过
            self._cache.add(signal)
            self._stats["signals_cached"] += 1
        
        with self._lock:
            self._stats["signals_sent"] += 1
            self._signal_history.append(signal)
            if len(self._signal_history) > self._max_history:
                self._signal_history.pop(0)
        
        # 触发广播钩子
        if self._on_signal_broadcast:
            self._on_signal_broadcast(signal)
        
        # 使用批处理或直接处理
        if self._batch_processor and self._batch_processor.add(signal):
            # 批处理已触发处理
            return 0  # 由批处理器统计
        
        # 直接处理（无批处理）
        return self._deliver_signal(signal)
    
    def _deliver_signal(self, signal: Signal) -> int:
        """投递信号到匹配的订阅者"""
        subscribers = self.get_subscribers()
        matched = self._match_engine.match(signal, subscribers)
        
        delivered_count = 0
        for sub in matched:
            if sub.callback:
                try:
                    sub.callback(signal)
                    delivered_count += 1
                    self._stats["signals_delivered"] += 1
                    
                    # 触发传递钩子
                    if self._on_signal_delivered:
                        self._on_signal_delivered(signal, sub)
                except Exception as e:
                    print(f"[SignalBus] Callback error for {sub.subscriber_id}: {e}")
        
        with self._lock:
            self._stats["signals_filtered"] += len(subscribers) - delivered_count
        
        return delivered_count
    
    def flush_batch(self):
        """强制刷新批处理队列"""
        if self._batch_processor:
            self._batch_processor.force_flush()
    
    def send_knowledge(self, sender_id: str, knowledge: Dict[str, Any], 
                       domain: str = "", **kwargs) -> int:
        """便捷方法：广播知识信号"""
        payload = {
            "content": knowledge,
            "domain": domain,
        }
        payload.update(knowledge)
        
        signal = Signal.create(
            signal_type=SignalType.KNOWLEDGE,
            sender_id=sender_id,
            payload=payload,
            tags={domain} if domain else set(),
            **kwargs
        )
        return self.broadcast(signal)
    
    def send_need(self, sender_id: str, need: str, 
                  required_skills: List[str] = None, **kwargs) -> int:
        """便捷方法：广播需求信号"""
        payload = {
            "description": need,
            "required_skills": required_skills or [],
        }
        
        signal = Signal.create(
            signal_type=SignalType.NEED,
            sender_id=sender_id,
            payload=payload,
            tags=set(required_skills) if required_skills else set(),
            **kwargs
        )
        return self.broadcast(signal)
    
    def send_capability(self, sender_id: str, capabilities: List[str], 
                        performance: Dict[str, Any] = None, **kwargs) -> int:
        """便捷方法：广播能力信号"""
        payload = {
            "capabilities": capabilities,
            "performance": performance or {},
        }
        
        signal = Signal.create(
            signal_type=SignalType.CAPABILITY,
            sender_id=sender_id,
            payload=payload,
            tags=set(capabilities),
            **kwargs
        )
        return self.broadcast(signal)
    
    def send_task(self, sender_id: str, task: Dict[str, Any], **kwargs) -> int:
        """便捷方法：广播任务信号"""
        payload = {
            "task": task,
        }
        
        # 从任务中提取标签
        tags = set()
        if "task_type" in task:
            tags.add(task["task_type"])
        if "skills_required" in task:
            tags.update(task["skills_required"])
        
        signal = Signal.create(
            signal_type=SignalType.TASK,
            sender_id=sender_id,
            payload=payload,
            tags=tags,
            **kwargs
        )
        return self.broadcast(signal)
    
    # ==================== 统计与调试 ====================
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            stats = {
                **self._stats,
                "active_subscribers": len(self.get_subscribers()),
                "signal_history_size": len(self._signal_history),
                "cache_enabled": self._enable_cache,
                "batch_enabled": self._enable_batch,
            }
            
            # 添加缓存统计
            if self._cache:
                stats["cache"] = self._cache.get_stats()
            
            # 添加批处理统计
            if self._batch_processor:
                stats["batch"] = self._batch_processor.get_stats()
            
            # 计算效率指标
            total = stats["signals_sent"]
            if total > 0:
                stats["delivery_rate"] = round(
                    stats["signals_delivered"] / total, 3
                )
                stats["filter_rate"] = round(
                    stats["signals_filtered"] / total, 3
                )
            
            return stats
    
    def get_recent_signals(self, limit: int = 10) -> List[Signal]:
        """获取最近的信号"""
        with self._lock:
            return self._signal_history[-limit:]
    
    def clear_history(self):
        """清除信号历史"""
        with self._lock:
            self._signal_history.clear()
    
    def clear_cache(self):
        """清除信号缓存"""
        if self._cache:
            self._cache.clear()
    
    def clear_all(self):
        """清除所有缓存和历史"""
        self.clear_history()
        self.clear_cache()
        if self._batch_processor:
            self._batch_processor.force_flush()
    
    # ==================== 钩子设置 ====================
    
    def on_broadcast(self, callback: Callable[[Signal], None]):
        """设置广播回调"""
        self._on_signal_broadcast = callback
    
    def on_delivered(self, callback: Callable[[Signal, Subscriber], None]):
        """设置传递回调"""
        self._on_signal_delivered = callback


# ==================== Agent 信号适配器 ====================

class AgentSignalAdapter:
    """
    Agent 信号适配器
    ==================
    将现有 Agent 接入 EigenFlux 信号总线
    """
    
    def __init__(self, agent_id: str, agent_name: str, 
                 capabilities: List[str], signal_bus: SignalBus):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.capabilities = set(capabilities)
        self.signal_bus = signal_bus
        self.interests: Set[str] = set()
        self._subscriber_id = f"{agent_id}_adapter"
        
        # 创建订阅者
        self._subscriber = Subscriber(
            subscriber_id=self._subscriber_id,
            interests=self.interests,
            capabilities=self.capabilities,
            signal_types={sig.value for sig in SignalType},
            callback=self._on_signal_received,
        )
        
        # 注册订阅
        self.signal_bus.subscribe(self._subscriber)
        
        # 广播自身能力
        self._broadcast_capabilities()
    
    def _broadcast_capabilities(self):
        """广播自身能力"""
        self.signal_bus.send_capability(
            sender_id=self.agent_id,
            capabilities=list(self.capabilities),
            performance={"status": "online"},
        )
    
    def _on_signal_received(self, signal: Signal):
        """收到信号的处理"""
        # 子类可以重写此方法
        pass
    
    def send_knowledge(self, knowledge: Dict[str, Any], domain: str = ""):
        """广播知识"""
        self.signal_bus.send_knowledge(
            sender_id=self.agent_id,
            knowledge=knowledge,
            domain=domain,
        )
    
    def send_need(self, need: str, required_skills: List[str] = None):
        """广播需求"""
        self.signal_bus.send_need(
            sender_id=self.agent_id,
            need=need,
            required_skills=required_skills,
        )
    
    def send_task(self, task: Dict[str, Any]):
        """广播任务"""
        self.signal_bus.send_task(
            sender_id=self.agent_id,
            task=task,
        )
    
    def update_interests(self, interests: Set[str]):
        """更新兴趣"""
        self.interests = interests
        self.signal_bus.update_subscriber(
            self._subscriber_id,
            interests=interests
        )
    
    def update_capabilities(self, capabilities: List[str]):
        """更新能力"""
        self.capabilities = set(capabilities)
        self.signal_bus.update_subscriber(
            self._subscriber_id,
            capabilities=self.capabilities
        )
        # 重新广播能力
        self._broadcast_capabilities()
    
    def disconnect(self):
        """断开连接"""
        self.signal_bus.unsubscribe(self._subscriber_id)


# ==================== 兼容层：与现有 A2A 集成 ====================

class A2AEigenFluxBridge:
    """
    A2A 与 EigenFlux 桥接器
    ========================
    将 EigenFlux 信号机制与现有 A2A 协议无缝集成
    """
    
    def __init__(self, signal_bus: SignalBus, 
                 a2a_protocol: Any = None):
        self.signal_bus = signal_bus
        self.a2a_protocol = a2a_protocol
    
    def agent_registered(self, agent_id: str, capabilities: List[str]):
        """当 Agent 注册时调用 - 广播能力"""
        self.signal_bus.send_capability(
            sender_id=agent_id,
            capabilities=capabilities,
            performance={"status": "online", "event": "registered"},
        )
    
    def agent_unregistered(self, agent_id: str):
        """当 Agent 注销时调用"""
        # 发送离线信号
        signal = Signal.create(
            signal_type=SignalType.CAPABILITY,
            sender_id=agent_id,
            payload={"status": "offline"},
        )
        self.signal_bus.broadcast(signal)
    
    def task_created(self, task_id: str, task_type: str, 
                     skills_required: List[str], sender_id: str):
        """当任务创建时调用 - 广播任务信号"""
        self.signal_bus.send_task(
            sender_id=sender_id,
            task={
                "task_id": task_id,
                "task_type": task_type,
                "skills_required": skills_required,
            },
            priority=SignalPriority.NORMAL,
        )
    
    def knowledge_discovered(self, agent_id: str, knowledge: Dict, domain: str):
        """当发现新知识时调用 - 广播知识信号"""
        self.signal_bus.send_knowledge(
            sender_id=agent_id,
            knowledge=knowledge,
            domain=domain,
        )
    
    def need_identified(self, agent_id: str, need: str, 
                       required_skills: List[str]):
        """当识别到需求时调用 - 广播需求信号"""
        self.signal_bus.send_need(
            sender_id=agent_id,
            need=need,
            required_skills=required_skills,
        )
    
    def find_agents_by_capability(self, capability: str) -> List[Subscriber]:
        """查找具有特定能力的 Agent"""
        subscribers = self.signal_bus.get_subscribers()
        return [s for s in subscribers if capability in s.capabilities]
    
    def find_agents_by_interest(self, interest: str) -> List[Subscriber]:
        """查找对特定主题感兴趣的 Agent"""
        subscribers = self.signal_bus.get_subscribers()
        return [s for s in subscribers if interest in s.interests]


# ==================== 使用示例 ====================

def demo():
    """EigenFlux 使用示例"""
    print("=" * 60)
    print("EigenFlux 增强模块演示")
    print("=" * 60)
    
    # 创建信号总线
    bus = SignalBus("demo")
    
    # 创建订阅者
    hermes = Subscriber(
        subscriber_id="hermes",
        interests={"代码生成", "架构设计", "AI"},
        capabilities={"orchestration", "planning"},
        signal_types={sig.value for sig in SignalType},
    )
    
    ei_agent = Subscriber(
        subscriber_id="ei_agent",
        interests={"自我进化", "机器学习", "优化"},
        capabilities={"self_evolution", "learning", "optimization"},
        signal_types={sig.value for sig in SignalType},
    )
    
    ide_agent = Subscriber(
        subscriber_id="ide_agent",
        interests={"代码生成", "调试", "重构"},
        capabilities={"code_generation", "code_review", "refactoring"},
        signal_types={sig.value for sig in SignalType},
    )
    
    # 注册订阅者
    bus.subscribe(hermes)
    bus.subscribe(ei_agent)
    bus.subscribe(ide_agent)
    
    print(f"\n📡 已注册 {len(bus.get_subscribers())} 个订阅者")
    
    # 广播知识信号
    print("\n🔵 广播知识信号：'Hermes 发现新的架构优化方案'")
    count = bus.send_knowledge(
        sender_id="hermes",
        knowledge={"title": "微服务架构优化", "content": "..."},
        domain="架构设计",
        keywords=["微服务", "优化", "架构"],
    )
    print(f"   → 传递给了 {count} 个订阅者")
    
    # 广播需求信号
    print("\n🟠 广播需求信号：'EI Agent 需要代码审查能力'")
    count = bus.send_need(
        sender_id="ei_agent",
        need="需要代码审查能力来增强自我进化",
        required_skills=["code_review"],
    )
    print(f"   → 传递给了 {count} 个订阅者")
    
    # 广播任务信号
    print("\n🟢 广播任务信号：'新任务需要代码生成'")
    count = bus.send_task(
        sender_id="hermes",
        task={
            "task_id": "task_001",
            "task_type": "code_generation",
            "skills_required": ["code_generation"],
        },
    )
    print(f"   → 传递给了 {count} 个订阅者")
    
    # 打印统计
    print("\n📊 信号总线统计:")
    stats = bus.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo()
