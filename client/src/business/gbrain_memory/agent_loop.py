"""
GBrain Brain-Agent 循环
实现记忆系统的核心工作流：信号 → 实体检测 → READ → WRITE → Sync

灵感来源：GBrain 的 Brain-First Lookup 和复利增长引擎
"""

import json
import time
import threading
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from business.gbrain_memory.models import (
    BrainPage, MemoryCategory, TimelineEntry, EvidenceSource,
    EntityMention, MemoryQuery
)
from business.gbrain_memory.page_manager import PageManager
from business.gbrain_memory.search_engine import SearchEngine


class SignalType(Enum):
    """信号类型"""
    USER_MESSAGE = "user_message"
    AI_RESPONSE = "ai_response"
    EXTERNAL_API_RESULT = "external_api_result"
    SCHEDULED_TRIGGER = "scheduled_trigger"
    MANUAL_INPUT = "manual_input"


@dataclass
class BrainSignal:
    """大脑信号"""
    signal_type: SignalType
    content: str
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "system"


@dataclass
class EntityDetection:
    """实体检测结果"""
    entities: List[Dict[str, str]]
    original_thoughts: List[str]
    context: str


@dataclass
class AgentResponse:
    """Agent 响应"""
    answer: str
    context_used: List[str]
    new_memories: List[Dict[str, str]]
    suggestions: List[str]


class BrainAgentLoop:
    """
    Brain-Agent 循环

    核心流程：
    1. Signal: 接收信号
    2. Entity Detection: 检测实体和原创想法
    3. READ: 先查大脑（Brain-First Lookup）
    4. WRITE: 更新大脑
    """

    def __init__(
        self,
        brain_dir: str | Path = None,
        llm_client: Any = None
    ):
        self.page_manager = PageManager(brain_dir)
        self.search_engine = SearchEngine(brain_dir)
        self.llm_client = llm_client

        self.config = {
            "auto_entity_detection": True,
            "auto_memory_write": True,
            "priority_threshold": 0.7,
            "max_context_pages": 5,
            "dream_cycle_enabled": False,
        }

        self.on_memory_created: Optional[Callable[[BrainPage], None]] = None
        self.on_memory_updated: Optional[Callable[[BrainPage], None]] = None

    def process(
        self,
        signal: BrainSignal,
        user_question: str = None,
        generate_response: bool = True
    ) -> AgentResponse:
        """处理大脑信号"""
        entity_result = self._detect_entities(signal)
        context_pages = self._brain_first_lookup(entity_result)

        answer = ""
        if generate_response and user_question:
            answer = self._generate_with_context(user_question, context_pages, entity_result)

        new_memories = []
        if self.config["auto_memory_write"]:
            new_memories = self._auto_write_memory(signal, entity_result)

        return AgentResponse(
            answer=answer,
            context_used=[p.page.id for p in context_pages],
            new_memories=new_memories,
            suggestions=self._generate_suggestions(entity_result, context_pages)
        )

    def _detect_entities(self, signal: BrainSignal) -> EntityDetection:
        """实体检测"""
        content = signal.content
        entities = []
        original_thoughts = []

        # 人物检测
        name_pattern = r'([A-Z\u4e00-\u9fa5]{2,4})(?:说|认为|提出|发现|开发|创建|表示|指出)'
        names = re.findall(name_pattern, content)
        for name in names:
            entities.append({"name": name, "type": "person", "confidence": 0.8})

        # 公司检测
        company_pattern = r'([A-Z\u4e00-\u9fa5]+公司|[A-Z\u4e00-\u9fa5]+集团|[A-Z\u4e00-\u9fa5]+企业)'
        companies = re.findall(company_pattern, content)
        for company in companies:
            entities.append({"name": company, "type": "company", "confidence": 0.8})

        # 原创想法检测
        thought_patterns = [
            r'我认为?(.+?)[。\n]',
            r'我的想法是?(.+?)[。\n]',
            r'我觉得?(.+?)[。\n]',
            r'创意[：:](.+?)[。\n]',
            r'想法[：:](.+?)[。\n]'
        ]
        for pattern in thought_patterns:
            matches = re.findall(pattern, content)
            original_thoughts.extend(matches)

        return EntityDetection(
            entities=entities,
            original_thoughts=original_thoughts,
            context=content[:200]
        )

    def _brain_first_lookup(self, entity_result: EntityDetection) -> List[Any]:
        """Brain-First Lookup"""
        all_keywords = [e["name"] for e in entity_result.entities]
        all_keywords.extend(entity_result.original_thoughts)

        if not all_keywords:
            return []

        query = MemoryQuery(keywords=all_keywords[:5], limit=self.config["max_context_pages"])
        results = self.search_engine.search(query)
        return [r for r in results if r.relevance_score >= 0.3]

    def _generate_with_context(
        self,
        question: str,
        context_pages: List[Any],
        entity_result: EntityDetection
    ) -> str:
        """带上下文生成回答"""
        if not context_pages:
            return ""

        context_parts = []
        for result in context_pages[:3]:
            page = result.page
            context_parts.append(f"【{page.title}】")
            if page.compiled_truth.summary:
                context_parts.append(page.compiled_truth.summary)

        if not context_parts:
            return ""

        context_str = "\n".join(context_parts)
        return f"[参考记忆生成]\n{context_str}"

    def _auto_write_memory(
        self,
        signal: BrainSignal,
        entity_result: EntityDetection
    ) -> List[Dict[str, str]]:
        """自动写入记忆"""
        created_memories = []

        for thought in entity_result.original_thoughts:
            page = self.page_manager.create_page(
                title=f"想法_{int(time.time())}",
                category=MemoryCategory.ORIGINALS,
                content=thought,
                source=f"信号: {signal.signal_type.value}",
                source_type=EvidenceSource.USER_MESSAGE,
                tags=["原创想法", "自动创建"]
            )
            created_memories.append({"id": page.id, "title": page.title, "type": "original_thought"})
            if self.on_memory_created:
                self.on_memory_created(page)

        for entity in entity_result.entities:
            if entity["confidence"] < self.config["priority_threshold"]:
                continue

            existing = self._find_entity_page(entity["name"])
            if existing:
                self.page_manager.append_timeline(
                    page_id=existing.id,
                    content=f"在上下文中被提及：{signal.content[:100]}",
                    source=f"信号: {signal.signal_type.value}",
                    source_type=EvidenceSource.USER_MESSAGE,
                    context=entity_result.context
                )
            else:
                category = self._infer_category(entity["type"])
                page = self.page_manager.create_page(
                    title=entity["name"],
                    category=category,
                    content=f"首次提及：{signal.content[:200]}",
                    source=f"信号: {signal.signal_type.value}",
                    source_type=EvidenceSource.USER_MESSAGE,
                    tags=[entity["type"], "实体"]
                )
                created_memories.append({"id": page.id, "title": page.title, "type": "entity"})
                if self.on_memory_created:
                    self.on_memory_created(page)

        return created_memories

    def _find_entity_page(self, entity_name: str) -> Optional[BrainPage]:
        """查找实体页面"""
        page = self.page_manager.find_page_by_alias(entity_name)
        if page:
            return page

        pages = self.page_manager.search_pages(keywords=[entity_name])
        for p in pages:
            if p.title == entity_name or entity_name in p.aliases:
                return p

        return None

    def _infer_category(self, entity_type: str) -> MemoryCategory:
        """推断分类"""
        mapping = {
            "person": MemoryCategory.PEOPLE,
            "company": MemoryCategory.COMPANIES,
            "concept": MemoryCategory.CONCEPTS,
            "project": MemoryCategory.PROJECTS,
            "event": MemoryCategory.MEETINGS,
        }
        return mapping.get(entity_type, MemoryCategory.UNCLASSIFIED)

    def _generate_suggestions(
        self,
        entity_result: EntityDetection,
        context_pages: List[Any]
    ) -> List[str]:
        """生成建议"""
        suggestions = []
        if len(entity_result.entities) > 0:
            suggestions.append(f"检测到 {len(entity_result.entities)} 个新实体")
        if entity_result.original_thoughts:
            suggestions.append("发现原创想法，建议查看")
        if context_pages:
            suggestions.append(f"使用了 {len(context_pages)} 个记忆页面")
        return suggestions

    def dream_cycle(self) -> Dict[str, Any]:
        """夜间循环"""
        if not self.config["dream_cycle_enabled"]:
            return {"status": "disabled"}

        start_time = time.time()
        actions = []

        today_start = start_time - 86400
        conversations = self.search_engine.search_conversations(start_time=today_start, limit=50)

        for conv in conversations:
            entity_result = self._detect_entities(
                BrainSignal(
                    signal_type=SignalType.DREAM_CYCLE,
                    content=conv.page.compiled_truth.summary or "",
                    source="dream_cycle"
                )
            )
            for entity in entity_result.entities:
                self._enrich_entity(entity, conv.page.id)
            actions.append(f"丰富实体: {len(entity_result.entities)}")

        duration = time.time() - start_time
        return {"status": "completed", "conversations_processed": len(conversations), "actions": actions, "duration": duration}

    def _enrich_entity(self, entity: Dict[str, str], source_page_id: str):
        """丰富实体"""
        pass

    def query(self, question: str, use_brain_first: bool = True) -> Dict[str, Any]:
        """便捷查询"""
        signal = BrainSignal(
            signal_type=SignalType.USER_MESSAGE,
            content=question,
            context={"original_question": question}
        )

        response = self.process(signal=signal, user_question=question, generate_response=True)

        return {
            "answer": response.answer,
            "context_pages": response.context_used,
            "new_memories": response.new_memories,
            "suggestions": response.suggestions
        }

    def remember(
        self,
        content: str,
        title: str = None,
        category: MemoryCategory = MemoryCategory.UNCLASSIFIED,
        tags: List[str] = None,
        source: str = "manual"
    ) -> BrainPage:
        """手动添加记忆"""
        page = self.page_manager.create_page(
            title=title or f"记忆_{int(time.time())}",
            category=category,
            content=content,
            source=source,
            source_type=EvidenceSource.MANUAL_ENTRY,
            tags=tags
        )

        if self.on_memory_created:
            self.on_memory_created(page)

        return page

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "page_count": self.page_manager.get_page_count(),
            "search_stats": self.search_engine.get_search_stats(),
            "config": self.config
        }
