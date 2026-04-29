# -*- coding: utf-8 -*-
"""
Phase 3: 多智能体协同分析器
================================

多个专门化 Agent 并行工作，协同完成复杂分析任务。

架构设计:
```
                    ┌─────────────────────────────────────┐
                    │      MultiAgentCoordinator          │
                    │         (多智能体协调器)              │
                    ├─────────────────────────────────────┤
                    │                                     │
    ┌───────────────┼───────────────┐                     │
    │   SummaryAgent              │  ←── 摘要专家           │
    │   (摘要生成)                │                       │
    └─────────────────────────────┘                       │
    ┌───────────────┬───────────────┐                     │
    │   EntityAgent │  RelationAgent │  ←── 并行执行       │
    │   (实体提取)  │  (关系分析)    │                     │
    └───────────────┴───────────────┘                     │
    ┌───────────────┬───────────────┐                     │
    │   InsightAgent│  SynthesisAgent│ ←── 聚合执行      │
    │   (洞察发现)  │  (综合报告)    │                    │
    └───────────────┴───────────────┘                     │
    │              Message Bus              │             │
    └──────────────────────────────────────┘              │
                    │                                     │
                    ▼                                     │
              ┌─────────────┐                             │
              │  最终报告   │                             │
              └─────────────┘                             │
```

设计原则:
1. 每个 Agent 专门化: 单一职责，高效执行
2. 并行 + 串行混合: 根据依赖关系调度
3. 消息传递: Agent 间通过消息总线通信
4. 结果聚合: 协调器整合各 Agent 结果

Author: Hermes Desktop Team
Date: 2026-04-24
from __future__ import annotations
"""


import re
import logging
import time
from typing import (
    List, Dict, Any, Optional, Callable, Iterator,
    TypeVar, Generic, Set, Tuple
)
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from abc import ABC, abstractmethod
import threading

logger = logging.getLogger(__name__)

# ============================================================================
# 枚举定义
# ============================================================================

class AgentType(Enum):
    """Agent 类型枚举"""
    SUMMARY = "summary"           # 摘要生成
    ENTITY = "entity"            # 实体提取
    RELATION = "relation"         # 关系分析
    INSIGHT = "insight"           # 洞察发现
    SYNTHESIS = "synthesis"       # 综合报告

class AgentStatus(Enum):
    """Agent 状态"""
    IDLE = "idle"                # 空闲
    RUNNING = "running"           # 运行中
    WAITING = "waiting"          # 等待中
    COMPLETED = "completed"       # 完成
    FAILED = "failed"            # 失败

class MessageType(Enum):
    """消息类型"""
    TASK = "task"                 # 任务消息
    RESULT = "result"             # 结果消息
    ERROR = "error"              # 错误消息
    SYNC = "sync"               # 同步消息
    REQUEST = "request"          # 请求消息
    RESPONSE = "response"        # 响应消息

# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class AgentMessage:
    """Agent 间消息"""
    msg_id: str
    msg_type: MessageType
    from_agent: str
    to_agent: Optional[str]  # None 表示广播
    content: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None

@dataclass
class AgentConfig:
    """Agent 配置"""
    agent_type: AgentType
    name: str
    description: str
    max_retries: int = 3
    timeout: int = 60
    priority: int = 5  # 1-10, 越高越先执行
    dependencies: Set[AgentType] = field(default_factory=set)
    # LLM 配置
    llm_model: str = "qwen2.5:1.5b"
    llm_temperature: float = 0.3
    # 特殊配置
    extra_config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentResult:
    """Agent 执行结果"""
    agent_type: AgentType
    agent_name: str
    status: AgentStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================================
# 消息总线
# ============================================================================

class MessageBus:
    """Agent 间消息总线"""

    def __init__(self):
        self._subscribers: Dict[str, Set[Callable]] = defaultdict(set)
        self._message_queue: deque = deque(maxlen=1000)
        self._lock = threading.Lock()
        self._message_id = 0

    def subscribe(self, agent_name: str, callback: Callable[[AgentMessage], None]):
        """订阅消息"""
        self._subscribers[agent_name].add(callback)

    def unsubscribe(self, agent_name: str, callback: Callable[[AgentMessage], None]):
        """取消订阅"""
        self._subscribers[agent_name].discard(callback)

    def publish(self, message: AgentMessage):
        """发布消息"""
        with self._lock:
            self._message_queue.append(message)
            self._message_id += 1

        # 分发消息
        if message.to_agent:
            # 点对点消息
            callbacks = self._subscribers.get(message.to_agent, set())
            for callback in callbacks:
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"消息回调失败: {e}")
        else:
            # 广播消息
            for agent_name, callbacks in self._subscribers.items():
                if agent_name != message.from_agent:
                    for callback in callbacks:
                        try:
                            callback(message)
                        except Exception as e:
                            logger.error(f"广播回调失败: {e}")

    def get_messages(self, agent_name: str, msg_type: Optional[MessageType] = None) -> List[AgentMessage]:
        """获取消息"""
        with self._lock:
            messages = list(self._message_queue)
        
        result = [m for m in messages if m.to_agent == agent_name or m.to_agent is None]
        if msg_type:
            result = [m for m in result if m.msg_type == msg_type]
        return result

    def clear(self):
        """清空消息"""
        with self._lock:
            self._message_queue.clear()

# ============================================================================
# 基础 Agent
# ============================================================================

class BaseAgent(ABC):
    """Agent 基类"""

    def __init__(
        self,
        config: AgentConfig,
        message_bus: Optional[MessageBus] = None,
    ):
        self.config = config
        self.message_bus = message_bus or MessageBus()
        self.status = AgentStatus.IDLE
        self._result: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def agent_type(self) -> AgentType:
        return self.config.agent_type

    @property
    def result(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._result

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行分析任务"""
        pass

    def _update_status(self, status: AgentStatus):
        """更新状态"""
        with self._lock:
            self.status = status

    def _set_result(self, result: Dict[str, Any]):
        """设置结果"""
        with self._lock:
            self._result = result

    def _send_message(
        self,
        msg_type: MessageType,
        to_agent: Optional[str],
        content: Dict[str, Any],
    ):
        """发送消息"""
        message = AgentMessage(
            msg_id=f"{self.name}_{int(time.time() * 1000)}",
            msg_type=msg_type,
            from_agent=self.name,
            to_agent=to_agent,
            content=content,
        )
        self.message_bus.publish(message)

    def _receive_messages(
        self,
        msg_type: Optional[MessageType] = None,
    ) -> List[AgentMessage]:
        """接收消息"""
        return self.message_bus.get_messages(self.name, msg_type)

# ============================================================================
# 专门化 Agent 实现
# ============================================================================

class SummaryAgent(BaseAgent):
    """摘要生成 Agent"""

    def __init__(self, config: Optional[AgentConfig] = None, message_bus: Optional[MessageBus] = None):
        if config is None:
            config = AgentConfig(
                agent_type=AgentType.SUMMARY,
                name="SummaryAgent",
                description="专门生成高质量摘要",
                priority=10,
            )
        super().__init__(config, message_bus)

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成摘要"""
        self._update_status(AgentStatus.RUNNING)
        start_time = time.time()

        try:
            text = context.get("text", "")
            task = context.get("task", "")
            chunks = context.get("chunks", [])

            # 多级摘要
            summaries = {}

            # 1. 超级摘要 (<50字)
            summaries["super"] = self._generate_super_summary(text)

            # 2. 简短摘要 (<100字)
            summaries["brief"] = self._generate_brief_summary(text, task)

            # 3. 完整摘要 (<300字)
            summaries["full"] = self._generate_full_summary(text, task, chunks)

            # 4. 关键点列表
            summaries["key_points"] = self._extract_key_points(text, chunks)

            result = {
                "summaries": summaries,
                "word_count": len(text),
                "chunk_count": len(chunks) if chunks else 0,
            }

            self._set_result(result)
            self._update_status(AgentStatus.COMPLETED)

            return result

        except Exception as e:
            self._update_status(AgentStatus.FAILED)
            raise e
        finally:
            result = self.result or {}
            result["execution_time"] = time.time() - start_time

    def _generate_super_summary(self, text: str) -> str:
        """生成超级摘要 (<50字)"""
        # 提取前两句
        sentences = re.split(r'[。！？\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return "内容为空"

        # 取前2句
        super_summary = "".join(sentences[:2])
        if len(super_summary) > 50:
            super_summary = super_summary[:47] + "..."

        return super_summary

    def _generate_brief_summary(self, text: str, task: str) -> str:
        """生成简短摘要 (<100字)"""
        sentences = re.split(r'[。！？\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 3:
            return "".join(sentences)

        # 取前3-5句
        brief_summary = "".join(sentences[:min(5, len(sentences))])
        if len(brief_summary) > 100:
            brief_summary = brief_summary[:97] + "..."

        return brief_summary

    def _generate_full_summary(self, text: str, task: str, chunks: List) -> str:
        """生成完整摘要 (<300字)"""
        if not chunks:
            return self._generate_brief_summary(text, task)

        # 从每个分块提取关键句
        key_sentences = []

        for chunk in chunks[:5]:  # 最多5个分块
            chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
            sentences = re.split(r'[。！？\n]+', chunk_text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

            if sentences:
                key_sentences.append(sentences[0])  # 取每个分块的第一句

        full_summary = "".join(key_sentences[:4])
        if len(full_summary) > 300:
            full_summary = full_summary[:297] + "..."

        return full_summary

    def _extract_key_points(self, text: str, chunks: List) -> List[str]:
        """提取关键点"""
        key_points = []

        # 统计高频词
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        word_freq = defaultdict(int)
        for word in words:
            if len(word) >= 2:
                word_freq[word] += 1

        # 取频率最高的词
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        key_points = [f"核心主题: {word}" for word, _ in top_words[:3] if _ > 1]

        return key_points[:5]


class EntityAgent(BaseAgent):
    """实体提取 Agent"""

    def __init__(self, config: Optional[AgentConfig] = None, message_bus: Optional[MessageBus] = None):
        if config is None:
            config = AgentConfig(
                agent_type=AgentType.ENTITY,
                name="EntityAgent",
                description="专门提取文本中的实体",
                priority=8,
            )
        super().__init__(config, message_bus)

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """提取实体"""
        self._update_status(AgentStatus.RUNNING)
        start_time = time.time()

        try:
            text = context.get("text", "")
            chunks = context.get("chunks", [])

            # 实体类型
            entity_types = {
                "person": r'(?:先生|女士|教授|工程师|博士|CEO|董事长|总经理|总监)',
                "org": r'(?:公司|集团|企业|机构|组织|医院|学校|银行)',
                "location": r'(?:北京|上海|深圳|杭州|广州|成都|武汉|西安|南京)',
                "tech": r'(?:API|SDK|LLM|AI|ML|DL|NLP|CV)',
                "number": r'\d+(?:\.\d+)?%',
            }

            entities = {}

            for entity_type, pattern in entity_types.items():
                matches = re.findall(pattern, text)
                entities[entity_type] = list(set(matches))

            # 合并分块实体
            chunk_entities = []
            for i, chunk in enumerate(chunks):
                chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                chunk_entity_list = []

                for entity_type, pattern in entity_types.items():
                    matches = re.findall(pattern, chunk_text)
                    for match in matches:
                        chunk_entity_list.append({
                            "text": match,
                            "type": entity_type,
                            "chunk_index": i,
                        })

                chunk_entities.append(chunk_entity_list)

            result = {
                "entities": entities,
                "chunk_entities": chunk_entities,
                "total_count": sum(len(v) for v in entities.values()),
            }

            self._set_result(result)
            self._update_status(AgentStatus.COMPLETED)

            return result

        except Exception as e:
            self._update_status(AgentStatus.FAILED)
            raise e
        finally:
            result = self.result or {}
            result["execution_time"] = time.time() - start_time

    def _extract_advanced_entities(self, text: str) -> List[Dict[str, str]]:
        """高级实体提取 (使用模式匹配)"""
        entities = []

        # 人名模式
        person_pattern = r'([A-Za-z·\u4e00-\u9fa5]{2,4})(?:先生|女士|教授)'
        for match in re.finditer(person_pattern, text):
            entities.append({
                "text": match.group(0),
                "type": "person",
                "start": match.start(),
                "end": match.end(),
            })

        # 公司名模式
        org_pattern = r'([A-Za-z\u4e00-\u9fa5]+)(?:公司|集团|企业)'
        for match in re.finditer(org_pattern, text):
            entities.append({
                "text": match.group(0),
                "type": "organization",
                "start": match.start(),
                "end": match.end(),
            })

        return entities


class RelationAgent(BaseAgent):
    """关系分析 Agent"""

    def __init__(self, config: Optional[AgentConfig] = None, message_bus: Optional[MessageBus] = None):
        if config is None:
            config = AgentConfig(
                agent_type=AgentType.RELATION,
                name="RelationAgent",
                description="专门分析实体间关系",
                priority=6,
                dependencies={AgentType.ENTITY},
            )
        super().__init__(config, message_bus)

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析关系"""
        self._update_status(AgentStatus.RUNNING)
        start_time = time.time()

        try:
            text = context.get("text", "")
            chunks = context.get("chunks", [])
            entity_result = context.get("entity_result", {})

            relations = []
            relation_types = {
                "因果": [r'(\w+)导致(\w+)', r'(\w+)引起(\w+)', r'(\w+)造成(\w+)'],
                "对比": [r'(\w+)与(\w+)不同', r'(\w+)优于(\w+)', r'(\w+)vs(\w+)'],
                "包含": [r'(\w+)包含(\w+)', r'(\w+)包括(\w+)', r'(\w+)属于(\w+)'],
                "时序": [r'(\w+)然后(\w+)', r'(\w+)接着(\w+)', r'首先(\w+)然后(\w+)'],
            }

            for rel_type, patterns in relation_types.items():
                for pattern in patterns:
                    for match in re.finditer(pattern, text):
                        if len(match.groups()) >= 2:
                            relations.append({
                                "type": rel_type,
                                "from": match.group(1),
                                "to": match.group(2),
                                "pattern": pattern,
                            })

            # 基于实体的关系
            entities = entity_result.get("entities", {})
            entity_relations = self._analyze_entity_relations(text, entities, chunks)

            result = {
                "relations": relations,
                "entity_relations": entity_relations,
                "relation_count": len(relations) + len(entity_relations),
                "relation_types": list(relation_types.keys()),
            }

            self._set_result(result)
            self._update_status(AgentStatus.COMPLETED)

            return result

        except Exception as e:
            self._update_status(AgentStatus.FAILED)
            raise e
        finally:
            result = self.result or {}
            result["execution_time"] = time.time() - start_time

    def _analyze_entity_relations(
        self,
        text: str,
        entities: Dict[str, List],
        chunks: List,
    ) -> List[Dict[str, Any]]:
        """分析实体间关系"""
        relations = []

        # 检查同一分块中的实体
        if not chunks:
            return relations

        for i, chunk in enumerate(chunks[:3]):
            chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
            chunk_entities = []

            for entity_type, entity_list in entities.items():
                for entity in entity_list:
                    if entity in chunk_text:
                        chunk_entities.append((entity, entity_type))

            # 同一分块中的实体可能相关
            for j, (e1, t1) in enumerate(chunk_entities):
                for e2, t2 in chunk_entities[j+1:]:
                    if e1 != e2:
                        relations.append({
                            "type": "共现",
                            "entity1": e1,
                            "entity1_type": t1,
                            "entity2": e2,
                            "entity2_type": t2,
                            "chunk_index": i,
                        })

        return relations


class InsightAgent(BaseAgent):
    """洞察发现 Agent"""

    def __init__(self, config: Optional[AgentConfig] = None, message_bus: Optional[MessageBus] = None):
        if config is None:
            config = AgentConfig(
                agent_type=AgentType.INSIGHT,
                name="InsightAgent",
                description="专门发现深层洞察",
                priority=4,
                dependencies={AgentType.ENTITY, AgentType.RELATION},
            )
        super().__init__(config, message_bus)

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """发现洞察"""
        self._update_status(AgentStatus.RUNNING)
        start_time = time.time()

        try:
            text = context.get("text", "")
            chunks = context.get("chunks", [])
            summary_result = context.get("summary_result", {})
            entity_result = context.get("entity_result", {})
            relation_result = context.get("relation_result", {})

            insights = {
                "patterns": [],
                "anomalies": [],
                "trends": [],
                "recommendations": [],
            }

            # 1. 模式识别
            insights["patterns"] = self._find_patterns(text, chunks)

            # 2. 异常检测
            insights["anomalies"] = self._find_anomalies(text, chunks)

            # 3. 趋势分析
            insights["trends"] = self._analyze_trends(text, chunks)

            # 4. 基于关系的洞察
            insights["relation_insights"] = self._analyze_relation_insights(
                entity_result, relation_result
            )

            # 5. 建议生成
            insights["recommendations"] = self._generate_recommendations(
                summary_result, entity_result, relation_result
            )

            result = {
                "insights": insights,
                "insight_count": (
                    len(insights["patterns"]) +
                    len(insights["anomalies"]) +
                    len(insights["trends"]) +
                    len(insights["recommendations"])
                ),
            }

            self._set_result(result)
            self._update_status(AgentStatus.COMPLETED)

            return result

        except Exception as e:
            self._update_status(AgentStatus.FAILED)
            raise e
        finally:
            result = self.result or {}
            result["execution_time"] = time.time() - start_time

    def _find_patterns(self, text: str, chunks: List) -> List[str]:
        """发现模式"""
        patterns = []

        # 重复模式
        sentences = re.split(r'[。！？\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        seen = set()
        for sent in sentences:
            if sent in seen:
                patterns.append(f"重复出现: {sent[:30]}...")
            seen.add(sent)

        # 递进模式 (首先...然后...最后)
        if re.search(r'(?:首先|然后|接着|最后)', text):
            patterns.append("包含递进结构")

        # 对比模式
        if re.search(r'(?:然而|但是|不过|然而)', text):
            patterns.append("包含转折对比")

        return patterns[:5]

    def _find_anomalies(self, text: str, chunks: List) -> List[str]:
        """发现异常"""
        anomalies = []

        # 过长段落
        for i, chunk in enumerate(chunks):
            chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if len(chunk_text) > 2000:
                anomalies.append(f"分块 {i} 过长 ({len(chunk_text)} 字)")

        # 缺失内容
        if len(chunks) > 10 and len(text) / len(chunks) < 100:
            anomalies.append("平均分块过短，可能存在内容缺失")

        # 数字不一致
        numbers = re.findall(r'\d+', text[:5000])
        if numbers:
            unique_numbers = len(set(numbers))
            if unique_numbers > 50:
                anomalies.append("存在大量数字数据")

        return anomalies[:3]

    def _analyze_trends(self, text: str, chunks: List) -> List[str]:
        """分析趋势"""
        trends = []

        # 时间趋势
        time_keywords = ['增加', '增长', '上升', '下降', '减少', '提高', '降低']
        for kw in time_keywords:
            if kw in text:
                trends.append(f"包含趋势关键词: {kw}")
                break

        # 阶段划分
        phase_keywords = ['第一阶段', '第二阶段', '第三阶段', '初期', '中期', '后期']
        phases = [kw for kw in phase_keywords if kw in text]
        if phases:
            trends.append(f"包含 {len(set(phases))} 个阶段划分")

        return trends[:3]

    def _analyze_relation_insights(
        self,
        entity_result: Dict,
        relation_result: Dict,
    ) -> List[str]:
        """分析关系洞察"""
        insights = []

        relations = relation_result.get("relations", [])
        if len(relations) > 5:
            insights.append(f"发现 {len(relations)} 个明确关系")

        entity_relations = relation_result.get("entity_relations", [])
        if entity_relations:
            insights.append(f"发现 {len(entity_relations)} 个实体关联")

        return insights[:3]

    def _generate_recommendations(
        self,
        summary_result: Dict,
        entity_result: Dict,
        relation_result: Dict,
    ) -> List[str]:
        """生成建议"""
        recommendations = []

        summaries = summary_result.get("summaries", {})
        if not summaries.get("super"):
            recommendations.append("建议补充摘要信息")

        entities = entity_result.get("entities", {})
        if sum(len(v) for v in entities.values()) < 3:
            recommendations.append("建议深入提取实体")

        relations = relation_result.get("relations", [])
        if len(relations) < 2:
            recommendations.append("建议加强关系分析")

        return recommendations[:3]


class SynthesisAgent(BaseAgent):
    """综合报告 Agent"""

    def __init__(self, config: Optional[AgentConfig] = None, message_bus: Optional[MessageBus] = None):
        if config is None:
            config = AgentConfig(
                agent_type=AgentType.SYNTHESIS,
                name="SynthesisAgent",
                description="专门生成综合分析报告",
                priority=2,
                dependencies={AgentType.SUMMARY, AgentType.ENTITY, AgentType.RELATION, AgentType.INSIGHT},
            )
        super().__init__(config, message_bus)

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成综合报告"""
        self._update_status(AgentStatus.RUNNING)
        start_time = time.time()

        try:
            task = context.get("task", "")
            summary_result = context.get("summary_result", {})
            entity_result = context.get("entity_result", {})
            relation_result = context.get("relation_result", {})
            insight_result = context.get("insight_result", {})
            layer_result = context.get("layer_result", {})

            # 1. 执行摘要
            summaries = self._synthesize_summaries(summary_result, task)

            # 2. 实体关系图
            entity_graph = self._build_entity_graph(entity_result, relation_result)

            # 3. 关键发现
            key_findings = self._extract_key_findings(
                summary_result, entity_result, relation_result, insight_result
            )

            # 4. 结论
            conclusions = self._generate_conclusions(
                summaries, key_findings, insight_result
            )

            # 5. 建议
            suggestions = self._generate_suggestions(
                conclusions, insight_result, task
            )

            # 6. 知识图谱
            knowledge_graph = self._build_knowledge_graph(
                entity_result, relation_result, insight_result
            )

            result = {
                "summaries": summaries,
                "entity_graph": entity_graph,
                "key_findings": key_findings,
                "conclusions": conclusions,
                "suggestions": suggestions,
                "knowledge_graph": knowledge_graph,
                "confidence_score": self._calculate_confidence(
                    summary_result, entity_result, relation_result, insight_result
                ),
            }

            self._set_result(result)
            self._update_status(AgentStatus.COMPLETED)

            return result

        except Exception as e:
            self._update_status(AgentStatus.FAILED)
            raise e
        finally:
            result = self.result or {}
            result["execution_time"] = time.time() - start_time

    def _synthesize_summaries(
        self,
        summary_result: Dict,
        task: str,
    ) -> Dict[str, str]:
        """综合摘要"""
        summaries = summary_result.get("summaries", {})

        # 生成综合摘要
        super_summary = summaries.get("super", "")
        key_points = summaries.get("key_points", [])

        synthesized = {
            "super": super_summary,
            "executive": f"{super_summary}。针对任务「{task}」，关键点包括: {'; '.join(key_points[:3])}",
            "detailed": summaries.get("full", super_summary),
        }

        return synthesized

    def _build_entity_graph(
        self,
        entity_result: Dict,
        relation_result: Dict,
    ) -> Dict[str, Any]:
        """构建实体图"""
        graph = {
            "nodes": [],
            "edges": [],
        }

        # 添加节点
        entities = entity_result.get("entities", {})
        node_id = 0
        for entity_type, entity_list in entities.items():
            for entity in entity_list[:5]:  # 最多5个
                graph["nodes"].append({
                    "id": node_id,
                    "label": entity,
                    "type": entity_type,
                })
                node_id += 1

        # 添加边
        entity_relations = relation_result.get("entity_relations", [])
        for rel in entity_relations[:10]:  # 最多10条边
            graph["edges"].append({
                "from": rel.get("entity1", ""),
                "to": rel.get("entity2", ""),
                "type": rel.get("type", "related"),
            })

        return graph

    def _extract_key_findings(
        self,
        summary_result: Dict,
        entity_result: Dict,
        relation_result: Dict,
        insight_result: Dict,
    ) -> List[str]:
        """提取关键发现"""
        findings = []

        # 从洞察中提取
        insights = insight_result.get("insights", {})
        patterns = insights.get("patterns", [])
        findings.extend([f"模式: {p}" for p in patterns[:2]])

        # 从关系中提取
        relations = relation_result.get("relations", [])
        if relations:
            findings.append(f"发现 {len(relations)} 个关系")

        # 从实体中提取
        entities = entity_result.get("entities", {})
        total_entities = sum(len(v) for v in entities.values())
        if total_entities > 0:
            findings.append(f"提取 {total_entities} 个实体")

        return findings[:5]

    def _generate_conclusions(
        self,
        summaries: Dict[str, str],
        key_findings: List[str],
        insight_result: Dict,
    ) -> List[str]:
        """生成结论"""
        conclusions = []

        # 基于摘要
        if summaries.get("super"):
            conclusions.append(f"核心内容: {summaries['super']}")

        # 基于发现
        if key_findings:
            conclusions.append(f"主要发现: {'; '.join(key_findings[:2])}")

        # 基于洞察
        insights = insight_result.get("insights", {})
        anomalies = insights.get("anomalies", [])
        if anomalies:
            conclusions.append(f"注意异常: {anomalies[0]}")

        return conclusions[:3]

    def _generate_suggestions(
        self,
        conclusions: List[str],
        insight_result: Dict,
        task: str,
    ) -> List[str]:
        """生成建议"""
        suggestions = []

        # 基于任务
        if task:
            suggestions.append(f"针对「{task}」的建议: 请参考以上分析")

        # 基于洞察
        insights = insight_result.get("insights", {})
        recommendations = insights.get("recommendations", [])
        suggestions.extend(recommendations)

        # 通用建议
        if len(insights.get("patterns", [])) > 2:
            suggestions.append("建议深入分析发现模式")

        return suggestions[:5]

    def _build_knowledge_graph(
        self,
        entity_result: Dict,
        relation_result: Dict,
        insight_result: Dict,
    ) -> Dict[str, Any]:
        """构建知识图谱"""
        graph = {
            "concepts": [],
            "relationships": [],
            "attributes": {},
        }

        # 概念
        entities = entity_result.get("entities", {})
        for entity_type, entity_list in entities.items():
            for entity in entity_list[:3]:
                graph["concepts"].append({
                    "name": entity,
                    "type": entity_type,
                })

        # 关系
        relations = relation_result.get("relations", [])
        for rel in relations[:5]:
            graph["relationships"].append({
                "from": rel.get("from", ""),
                "to": rel.get("to", ""),
                "type": rel.get("type", "related"),
            })

        # 属性
        insights = insight_result.get("insights", {})
        graph["attributes"]["pattern_count"] = len(insights.get("patterns", []))
        graph["attributes"]["anomaly_count"] = len(insights.get("anomalies", []))

        return graph

    def _calculate_confidence(
        self,
        summary_result: Dict,
        entity_result: Dict,
        relation_result: Dict,
        insight_result: Dict,
    ) -> float:
        """计算置信度"""
        scores = []

        # 摘要完整性
        summaries = summary_result.get("summaries", {})
        if summaries.get("super"):
            scores.append(0.9)
        else:
            scores.append(0.3)

        # 实体提取
        entities = entity_result.get("entities", {})
        entity_count = sum(len(v) for v in entities.values())
        if entity_count > 10:
            scores.append(0.9)
        elif entity_count > 3:
            scores.append(0.7)
        else:
            scores.append(0.4)

        # 关系分析
        relations = relation_result.get("relations", [])
        if len(relations) > 5:
            scores.append(0.9)
        elif len(relations) > 0:
            scores.append(0.6)
        else:
            scores.append(0.3)

        # 洞察发现
        insights = insight_result.get("insights", {})
        insight_count = (
            len(insights.get("patterns", [])) +
            len(insights.get("anomalies", [])) +
            len(insights.get("trends", []))
        )
        if insight_count > 5:
            scores.append(0.9)
        elif insight_count > 2:
            scores.append(0.7)
        else:
            scores.append(0.5)

        return sum(scores) / len(scores) if scores else 0.5


# ============================================================================
# 多智能体协调器
# ============================================================================

class MultiAgentCoordinator:
    """
    多智能体协调器

    负责:
    1. Agent 注册和管理
    2. 任务调度 (并行/串行)
    3. 结果聚合
    4. 错误处理
    """

    def __init__(
        self,
        max_workers: int = 4,
        message_bus: Optional[MessageBus] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        self.max_workers = max_workers
        self.message_bus = message_bus or MessageBus()
        self.progress_callback = progress_callback

        # 注册的 Agent
        self._agents: Dict[AgentType, BaseAgent] = {}
        self._agent_results: Dict[AgentType, Dict[str, Any]] = {}

        # 调度配置
        self._parallel_agents = {AgentType.SUMMARY, AgentType.ENTITY}
        self._sequential_agents = {
            AgentType.RELATION: {AgentType.ENTITY},
            AgentType.INSIGHT: {AgentType.ENTITY, AgentType.RELATION},
            AgentType.SYNTHESIS: {
                AgentType.SUMMARY, AgentType.ENTITY,
                AgentType.RELATION, AgentType.INSIGHT
            },
        }

        # 初始化默认 Agent
        self._init_default_agents()

    def _init_default_agents(self):
        """初始化默认 Agent"""
        # 摘要 Agent
        self.register_agent(SummaryAgent(message_bus=self.message_bus))

        # 实体 Agent
        self.register_agent(EntityAgent(message_bus=self.message_bus))

        # 关系 Agent
        self.register_agent(RelationAgent(
            config=AgentConfig(
                agent_type=AgentType.RELATION,
                name="RelationAgent",
                description="专门分析实体间关系",
                priority=6,
                dependencies={AgentType.ENTITY},
            ),
            message_bus=self.message_bus,
        ))

        # 洞察 Agent
        self.register_agent(InsightAgent(
            config=AgentConfig(
                agent_type=AgentType.INSIGHT,
                name="InsightAgent",
                description="专门发现深层洞察",
                priority=4,
                dependencies={AgentType.ENTITY, AgentType.RELATION},
            ),
            message_bus=self.message_bus,
        ))

        # 综合 Agent
        self.register_agent(SynthesisAgent(
            config=AgentConfig(
                agent_type=AgentType.SYNTHESIS,
                name="SynthesisAgent",
                description="专门生成综合分析报告",
                priority=2,
                dependencies={
                    AgentType.SUMMARY, AgentType.ENTITY,
                    AgentType.RELATION, AgentType.INSIGHT
                },
            ),
            message_bus=self.message_bus,
        ))

    def register_agent(self, agent: BaseAgent):
        """注册 Agent"""
        self._agents[agent.agent_type] = agent
        logger.info(f"注册 Agent: {agent.name} ({agent.agent_type.value})")

    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """获取 Agent"""
        return self._agents.get(agent_type)

    def analyze(
        self,
        text: str,
        task: str = "",
        chunks: Optional[List] = None,
        agent_types: Optional[Set[AgentType]] = None,
    ) -> Dict[str, Any]:
        """
        执行多智能体分析

        Args:
            text: 待分析文本
            task: 分析任务
            chunks: 分块列表
            agent_types: 指定要使用的 Agent 类型

        Returns:
            分析结果
        """
        if agent_types is None:
            agent_types = set(self._agents.keys())

        start_time = time.time()

        # 构建上下文
        context = {
            "text": text,
            "task": task,
            "chunks": chunks or [],
        }

        # 阶段1: 并行执行独立 Agent
        parallel_types = agent_types & self._parallel_agents
        parallel_results = self._execute_parallel(parallel_types, context)

        # 更新上下文
        context.update(parallel_results)

        # 阶段2: 执行有依赖的 Agent
        sequential_types = agent_types - self._parallel_agents
        sequential_results = self._execute_sequential(sequential_types, context)

        # 合并结果 (处理生成器情况)
        if hasattr(parallel_results, '__iter__') and not isinstance(parallel_results, dict):
            parallel_results = dict(parallel_results) if parallel_results else {}
        if hasattr(sequential_results, '__iter__') and not isinstance(sequential_results, dict):
            sequential_results = dict(sequential_results) if sequential_results else {}
        
        all_results = {**parallel_results, **sequential_results}

        # 生成最终报告
        final_report = self._generate_final_report(all_results, task)

        return {
            "agent_results": all_results,
            "final_report": final_report,
            "execution_time": time.time() - start_time,
            "total_agents": len(agent_types),
        }

    def analyze_streaming(
        self,
        text: str,
        task: str = "",
        chunks: Optional[List] = None,
    ) -> Iterator[Tuple[str, Dict[str, Any], float]]:
        """
        流式多智能体分析

        Yields:
            (agent_name, result, progress)
        """
        context = {
            "text": text,
            "task": task,
            "chunks": chunks or [],
        }

        total_agents = len(self._agents)
        completed = 0

        # 阶段1: 并行执行
        parallel_types = self._parallel_agents & set(self._agents.keys())
        for agent_type, result in self._execute_parallel(parallel_types, context, streaming=True):
            completed += 1
            context.update(result)
            progress = completed / total_agents
            yield (agent_type.value, result, progress)

        # 阶段2: 串行执行
        sequential_types = set(self._agents.keys()) - self._parallel_agents
        for agent_type, result in self._execute_sequential(sequential_types, context, streaming=True):
            completed += 1
            context.update(result)
            progress = completed / total_agents
            yield (agent_type.value, result, progress)

    def _execute_parallel(
        self,
        agent_types: Set[AgentType],
        context: Dict[str, Any],
        streaming: bool = False,
    ) -> Dict[str, Any]:
        """并行执行 Agent"""
        results = {}

        if not agent_types:
            return results

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            for agent_type in agent_types:
                agent = self._agents.get(agent_type)
                if agent:
                    future = executor.submit(agent.execute, context.copy())
                    futures[future] = agent_type

            for future in as_completed(futures):
                agent_type = futures[future]
                try:
                    result = future.result(timeout=120)
                    results[agent_type.value] = result
                    self._agent_results[agent_type] = result

                    if streaming:
                        yield agent_type, result

                    self._report_progress(f"{agent.name} 完成", len(results) / len(agent_types))

                except Exception as e:
                    logger.error(f"Agent {agent_type.value} 执行失败: {e}")
                    results[agent_type.value] = {"error": str(e)}

        return results

    def _execute_sequential(
        self,
        agent_types: Set[AgentType],
        context: Dict[str, Any],
        streaming: bool = False,
    ) -> Dict[str, Any]:
        """串行执行 Agent (按依赖顺序)"""
        results = {}

        if not agent_types:
            return results

        # 按优先级排序
        sorted_types = sorted(
            agent_types,
            key=lambda t: self._agents.get(t, AgentConfig(
                agent_type=t, name="", description=""
            )).config.priority,
            reverse=True,
        )

        for agent_type in sorted_types:
            agent = self._agents.get(agent_type)
            if not agent:
                continue

            # 检查依赖
            dependencies = agent.config.dependencies
            deps_satisfied = all(
                dep in results or dep.value in results
                for dep in dependencies
            )

            if not deps_satisfied:
                logger.warning(f"Agent {agent.name} 依赖未满足，跳过")
                continue

            try:
                result = agent.execute(context.copy())
                results[agent_type.value] = result
                self._agent_results[agent_type] = result

                # 更新上下文
                context[agent_type.value + "_result"] = result

                if streaming:
                    yield agent_type, result

                self._report_progress(f"{agent.name} 完成", len(results) / len(sorted_types))

            except Exception as e:
                logger.error(f"Agent {agent_type.value} 执行失败: {e}")
                results[agent_type.value] = {"error": str(e)}

        return results

    def _generate_final_report(
        self,
        agent_results: Dict[str, Any],
        task: str,
    ) -> Dict[str, Any]:
        """生成最终报告"""
        # 使用 SynthesisAgent 的结果作为最终报告
        synthesis_result = agent_results.get(AgentType.SYNTHESIS.value, {})

        if synthesis_result:
            return {
                "summary": synthesis_result.get("summaries", {}).get("executive", ""),
                "key_findings": synthesis_result.get("key_findings", []),
                "conclusions": synthesis_result.get("conclusions", []),
                "suggestions": synthesis_result.get("suggestions", []),
                "knowledge_graph": synthesis_result.get("knowledge_graph", {}),
                "entity_graph": synthesis_result.get("entity_graph", {}),
                "confidence": synthesis_result.get("confidence_score", 0.5),
            }

        # 降级: 手动生成报告
        return self._generate_fallback_report(agent_results, task)

    def _generate_fallback_report(
        self,
        agent_results: Dict[str, Any],
        task: str,
    ) -> Dict[str, Any]:
        """生成降级报告"""
        summary_result = agent_results.get(AgentType.SUMMARY.value, {})
        entity_result = agent_results.get(AgentType.ENTITY.value, {})
        relation_result = agent_results.get(AgentType.RELATION.value, {})

        summaries = summary_result.get("summaries", {})

        return {
            "summary": summaries.get("super", summaries.get("brief", "")),
            "key_findings": [
                f"提取 {entity_result.get('total_count', 0)} 个实体",
                f"发现 {relation_result.get('relation_count', 0)} 个关系",
            ],
            "conclusions": [summaries.get("executive", "")],
            "suggestions": [],
            "knowledge_graph": {"concepts": [], "relationships": []},
            "entity_graph": {"nodes": [], "edges": []},
            "confidence": 0.5,
        }

    def _report_progress(self, message: str, progress: float):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(message, progress)
        else:
            logger.info(f"[{progress:.0%}] {message}")

    def get_agent_status(self) -> Dict[str, str]:
        """获取所有 Agent 状态"""
        return {
            agent_type.value: agent.status.value
            for agent_type, agent in self._agents.items()
        }

    def get_results(self) -> Dict[str, Any]:
        """获取所有结果"""
        return {
            agent_type.value: result
            for agent_type, result in self._agent_results.items()
        }


# ============================================================================
# 便捷函数
# ============================================================================

def analyze_multi_agent(
    text: str,
    task: str = "",
    depth: str = "standard",
) -> Dict[str, Any]:
    """
    便捷的多智能体分析函数

    Args:
        text: 待分析文本
        task: 分析任务
        depth: 分析深度 (quick/standard/deep/comprehensive)

    Returns:
        分析结果
    """
    coordinator = MultiAgentCoordinator()

    if depth == "quick":
        agent_types = {AgentType.SUMMARY}
    elif depth == "standard":
        agent_types = {AgentType.SUMMARY, AgentType.ENTITY}
    elif depth == "deep":
        agent_types = {
            AgentType.SUMMARY, AgentType.ENTITY, AgentType.RELATION
        }
    else:  # comprehensive
        agent_types = set(AgentType)

    return coordinator.analyze(text, task, agent_types=agent_types)


def quick_analyze(text: str) -> Dict[str, Any]:
    """快速分析 (仅摘要)"""
    return analyze_multi_agent(text, depth="quick")


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 枚举
    "AgentType",
    "AgentStatus",
    "MessageType",
    # 数据类
    "AgentMessage",
    "AgentConfig",
    "AgentResult",
    # Agent
    "BaseAgent",
    "SummaryAgent",
    "EntityAgent",
    "RelationAgent",
    "InsightAgent",
    "SynthesisAgent",
    # 协调器
    "MessageBus",
    "MultiAgentCoordinator",
    # 便捷函数
    "analyze_multi_agent",
    "quick_analyze",
]
