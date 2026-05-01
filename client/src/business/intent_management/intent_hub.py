"""
Unified Intent Definition Hub

统一意图定义中心，提供意图模式管理、版本控制、自动进化能力。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class IntentPriority(Enum):
    """意图优先级"""
    CRITICAL = 0      # 关键
    HIGH = 1          # 高
    MEDIUM = 2        # 中等
    LOW = 3           # 低


@dataclass
class IntentPattern:
    """意图模式"""
    pattern: str       # 匹配模式（支持通配符*）
    confidence: float = 1.0  # 匹配置信度


@dataclass
class IntentDefinition:
    """意图定义"""
    intent_id: str
    name: str
    description: Optional[str] = None
    patterns: List[IntentPattern] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    handlers: List[str] = field(default_factory=list)
    priority: IntentPriority = IntentPriority.MEDIUM
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True


@dataclass
class IntentVersion:
    """意图版本"""
    version_id: str
    intent_id: str
    definition: IntentDefinition
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    change_note: str = ""


@dataclass
class IntentEvolution:
    """意图进化记录"""
    intent_id: str
    feedback_count: int = 0
    success_rate: float = 0.0
    suggested_patterns: List[str] = field(default_factory=list)
    last_evolved_at: Optional[str] = None


class UnifiedIntentHub:
    """
    统一意图定义中心
    
    核心功能：
    - 意图模式定义与管理
    - 版本控制与回滚
    - 基于反馈的自动进化
    - 意图检索与匹配
    """
    
    def __init__(self):
        """初始化意图中心"""
        self._intents: Dict[str, IntentDefinition] = {}
        self._versions: Dict[str, List[IntentVersion]] = {}
        self._evolution: Dict[str, IntentEvolution] = {}
        
        # 内置意图定义
        self._load_builtin_intents()
        
        logger.info("UnifiedIntentHub 初始化完成")
    
    def _load_builtin_intents(self):
        """加载内置意图定义"""
        builtin_intents = [
            {
                "intent_id": "tech_question",
                "name": "技术问题咨询",
                "description": "用户询问技术相关问题",
                "patterns": ["如何解决*", "*怎么处理", "*问题", "*错误", "如何实现*"],
                "entities": ["tech_term", "error_code", "framework"],
                "handlers": ["FusionRAG", "LLMWiki"],
                "priority": IntentPriority.HIGH,
            },
            {
                "intent_id": "general_qa",
                "name": "通用问答",
                "description": "用户提出一般性问题",
                "patterns": ["什么是*", "*是什么", "为什么*", "介绍一下*"],
                "entities": ["concept", "term"],
                "handlers": ["FusionRAG", "LLMWiki"],
                "priority": IntentPriority.MEDIUM,
            },
            {
                "intent_id": "task_request",
                "name": "任务请求",
                "description": "用户请求执行某个任务",
                "patterns": ["帮我*", "请*", "能否*", "我想*"],
                "entities": ["action", "target"],
                "handlers": ["SmartModuleScheduler", "AgentExecutor"],
                "priority": IntentPriority.HIGH,
            },
            {
                "intent_id": "chat",
                "name": "闲聊",
                "description": "用户进行日常对话",
                "patterns": ["你好", "嗨", "在吗", "聊聊天"],
                "entities": [],
                "handlers": ["ChatAgent"],
                "priority": IntentPriority.LOW,
            },
            {
                "intent_id": "summarization",
                "name": "总结",
                "description": "用户请求总结内容",
                "patterns": ["总结一下", "*的总结", "概括一下"],
                "entities": ["document", "topic"],
                "handlers": ["SummarizationEngine"],
                "priority": IntentPriority.MEDIUM,
            },
            {
                "intent_id": "translation",
                "name": "翻译",
                "description": "用户请求翻译",
                "patterns": ["翻译", "翻译成*", "*怎么说"],
                "entities": ["text", "target_language"],
                "handlers": ["TranslationService"],
                "priority": IntentPriority.MEDIUM,
            },
            {
                "intent_id": "creative",
                "name": "创意生成",
                "description": "用户请求创意内容生成",
                "patterns": ["写一首诗", "编一个故事", "生成*"],
                "entities": ["content_type", "topic"],
                "handlers": ["CreativeGenerator"],
                "priority": IntentPriority.LOW,
            },
        ]
        
        for intent_data in builtin_intents:
            patterns = [IntentPattern(pattern=p) for p in intent_data.pop("patterns")]
            intent = IntentDefinition(**intent_data, patterns=patterns)
            self._intents[intent.intent_id] = intent
    
    def define_intent(self, intent_id: str, name: str, **kwargs) -> IntentDefinition:
        """
        定义意图
        
        Args:
            intent_id: 意图ID
            name: 意图名称
            **kwargs: 其他参数（patterns, entities, handlers, priority等）
        
        Returns:
            IntentDefinition 意图定义
        """
        # 保存旧版本
        if intent_id in self._intents:
            self._save_version(intent_id, change_note="更新意图")
        
        patterns = kwargs.pop("patterns", [])
        pattern_objects = [IntentPattern(pattern=p) for p in patterns]
        
        intent = IntentDefinition(
            intent_id=intent_id,
            name=name,
            patterns=pattern_objects,
            **kwargs
        )
        
        self._intents[intent_id] = intent
        
        # 初始化进化记录
        if intent_id not in self._evolution:
            self._evolution[intent_id] = IntentEvolution(intent_id=intent_id)
        
        logger.info(f"意图定义创建/更新: {intent_id}")
        return intent
    
    def get_intent(self, intent_id: str) -> Optional[IntentDefinition]:
        """
        获取意图定义
        
        Args:
            intent_id: 意图ID
            
        Returns:
            IntentDefinition 意图定义
        """
        return self._intents.get(intent_id)
    
    def delete_intent(self, intent_id: str) -> bool:
        """
        删除意图
        
        Args:
            intent_id: 意图ID
            
        Returns:
            bool 是否成功
        """
        if intent_id not in self._intents:
            logger.warning(f"意图不存在: {intent_id}")
            return False
        
        # 保存最后版本
        self._save_version(intent_id, change_note="删除意图")
        
        del self._intents[intent_id]
        logger.info(f"意图已删除: {intent_id}")
        return True
    
    def list_intents(self, active_only: bool = True) -> List[IntentDefinition]:
        """
        获取意图列表
        
        Args:
            active_only: 是否只返回活跃意图
            
        Returns:
            List 意图列表
        """
        intents = list(self._intents.values())
        if active_only:
            intents = [i for i in intents if i.is_active]
        return sorted(intents, key=lambda x: x.priority.value)
    
    def match_intent(self, query: str) -> List[Dict[str, Any]]:
        """
        匹配意图
        
        Args:
            query: 用户查询
            
        Returns:
            List 匹配的意图列表（按置信度排序）
        """
        matches = []
        
        for intent in self._intents.values():
            if not intent.is_active:
                continue
            
            for pattern in intent.patterns:
                if self._match_pattern(query, pattern.pattern):
                    matches.append({
                        "intent_id": intent.intent_id,
                        "name": intent.name,
                        "confidence": pattern.confidence,
                        "priority": intent.priority.value,
                        "handlers": intent.handlers,
                    })
        
        # 按置信度和优先级排序
        matches.sort(key=lambda x: (x["confidence"], -x["priority"]), reverse=True)
        return matches
    
    def _match_pattern(self, query: str, pattern: str) -> bool:
        """
        模式匹配
        
        Args:
            query: 用户查询
            pattern: 匹配模式
            
        Returns:
            bool 是否匹配
        """
        # 支持通配符*
        pattern = pattern.replace("*", ".*")
        import re
        return bool(re.search(pattern, query, re.IGNORECASE))
    
    def _save_version(self, intent_id: str, change_note: str = ""):
        """
        保存版本
        
        Args:
            intent_id: 意图ID
            change_note: 变更说明
        """
        intent = self._intents.get(intent_id)
        if not intent:
            return
        
        version_id = f"{intent_id}_v{len(self._versions.get(intent_id, [])) + 1}"
        version = IntentVersion(
            version_id=version_id,
            intent_id=intent_id,
            definition=intent,
            change_note=change_note,
        )
        
        if intent_id not in self._versions:
            self._versions[intent_id] = []
        self._versions[intent_id].append(version)
        
        logger.debug(f"版本保存: {version_id}")
    
    def get_versions(self, intent_id: str) -> List[IntentVersion]:
        """
        获取意图版本历史
        
        Args:
            intent_id: 意图ID
            
        Returns:
            List 版本列表
        """
        return self._versions.get(intent_id, [])
    
    def rollback_version(self, intent_id: str, version_id: str) -> bool:
        """
        回滚到指定版本
        
        Args:
            intent_id: 意图ID
            version_id: 版本ID
            
        Returns:
            bool 是否成功
        """
        versions = self._versions.get(intent_id, [])
        for version in versions:
            if version.version_id == version_id:
                # 保存当前版本
                self._save_version(intent_id, change_note=f"回滚到 {version_id}")
                
                # 恢复旧版本
                self._intents[intent_id] = version.definition
                logger.info(f"意图已回滚到版本: {version_id}")
                return True
        
        logger.warning(f"版本不存在: {version_id}")
        return False
    
    def record_feedback(self, intent_id: str, success: bool):
        """
        记录用户反馈
        
        Args:
            intent_id: 意图ID
            success: 是否成功
        """
        if intent_id not in self._evolution:
            self._evolution[intent_id] = IntentEvolution(intent_id=intent_id)
        
        evolution = self._evolution[intent_id]
        evolution.feedback_count += 1
        
        # 计算成功率
        if success:
            evolution.success_rate = (evolution.success_rate * (evolution.feedback_count - 1) + 1) / evolution.feedback_count
        else:
            evolution.success_rate = (evolution.success_rate * (evolution.feedback_count - 1)) / evolution.feedback_count
        
        logger.debug(f"反馈记录: {intent_id}, 成功率: {evolution.success_rate:.2f}")
    
    def suggest_patterns(self, intent_id: str, sample_queries: List[str]):
        """
        基于样本查询建议新模式
        
        Args:
            intent_id: 意图ID
            sample_queries: 样本查询列表
        """
        if intent_id not in self._evolution:
            self._evolution[intent_id] = IntentEvolution(intent_id=intent_id)
        
        evolution = self._evolution[intent_id]
        
        # 分析样本查询，提取模式
        patterns = []
        for query in sample_queries:
            # 简单模式提取：提取动词+宾语结构
            pattern = self._extract_pattern(query)
            if pattern and pattern not in patterns:
                patterns.append(pattern)
        
        evolution.suggested_patterns = patterns
        logger.info(f"为 {intent_id} 建议 {len(patterns)} 个新模式")
    
    def _extract_pattern(self, query: str) -> Optional[str]:
        """
        从查询中提取模式
        
        Args:
            query: 用户查询
            
        Returns:
            str 提取的模式
        """
        # 简单实现：返回查询模板
        keywords = ["如何", "什么", "为什么", "帮我", "请", "我想"]
        for kw in keywords:
            if kw in query:
                idx = query.index(kw)
                return kw + "*"
        
        return None
    
    def evolve_intent(self, intent_id: str):
        """
        自动进化意图
        
        Args:
            intent_id: 意图ID
        """
        evolution = self._evolution.get(intent_id)
        if not evolution or not evolution.suggested_patterns:
            return
        
        intent = self._intents.get(intent_id)
        if not intent:
            return
        
        # 添加建议的模式
        for pattern_str in evolution.suggested_patterns:
            exists = any(p.pattern == pattern_str for p in intent.patterns)
            if not exists:
                intent.patterns.append(IntentPattern(pattern=pattern_str, confidence=0.8))
        
        intent.version = f"{float(intent.version) + 0.1:.1f}"
        intent.updated_at = datetime.now().isoformat()
        evolution.last_evolved_at = datetime.now().isoformat()
        evolution.suggested_patterns = []
        
        logger.info(f"意图进化完成: {intent_id}, 新版本: {intent.version}")
    
    def get_evolution_info(self, intent_id: str) -> Optional[IntentEvolution]:
        """
        获取意图进化信息
        
        Args:
            intent_id: 意图ID
            
        Returns:
            IntentEvolution 进化信息
        """
        return self._evolution.get(intent_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        active_count = sum(1 for i in self._intents.values() if i.is_active)
        
        avg_success_rate = 0
        if self._evolution:
            avg_success_rate = sum(e.success_rate for e in self._evolution.values()) / len(self._evolution)
        
        return {
            "total_intents": len(self._intents),
            "active_intents": active_count,
            "total_versions": sum(len(v) for v in self._versions.values()),
            "avg_success_rate": avg_success_rate,
        }


# 全局意图中心实例
_intent_hub_instance = None

def get_unified_intent_hub() -> UnifiedIntentHub:
    """获取全局意图中心实例"""
    global _intent_hub_instance
    if _intent_hub_instance is None:
        _intent_hub_instance = UnifiedIntentHub()
    return _intent_hub_instance