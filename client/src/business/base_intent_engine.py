"""
Base Intent Engine
基础意图引擎，为所有意图识别模块提供通用功能。

使用方式：
    from client.src.business.base_intent_engine import BaseIntentEngine, IntentResult
    
    class MyIntentEngine(BaseIntentEngine):
        def parse(self, text: str) -> IntentResult:
            # 实现具体的意图识别逻辑
            pass
"""
import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """意图类型（通用）"""
    UNKNOWN = "unknown"
    CODE_GENERATION = "code_generation"
    CODE_COMPLETION = "code_completion"
    CODE_REVIEW = "code_review"
    BUG_FIX = "bug_fix"
    REFACTORING = "refactoring"
    QUERY = "query"
    EXECUTION = "execution"
    EXPLANATION = "explanation"
    CREATION = "creation"
    MODIFICATION = "modification"
    DELETION = "deletion"
    SEARCH = "search"
    ANALYSIS = "analysis"


class IntentPriority(Enum):
    """意图优先级"""
    P0_CRITICAL = 0
    P1_HIGH = 1
    P2_MEDIUM = 2
    P3_LOW = 3


@dataclass
class IntentResult:
    """意图识别结果"""
    intent_type: IntentType
    confidence: float  # 0.0 - 1.0
    priority: IntentPriority = IntentPriority.P2_MEDIUM
    
    # 提取的参数
    params: Dict[str, Any] = field(default_factory=dict)
    
    # 原始文本
    raw_text: str = ""
    
    # 附加信息
    language: str = "zh"  # zh, en
    tech_stack: List[str] = field(default_factory=list)
    action: str = ""
    target: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "priority": self.priority.value,
            "params": self.params,
            "raw_text": self.raw_text,
            "language": self.language,
            "tech_stack": self.tech_stack,
            "action": self.action,
            "target": self.target,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentResult":
        """从字典创建"""
        return cls(
            intent_type=IntentType(data.get("intent_type", "unknown")),
            confidence=data.get("confidence", 0.0),
            priority=IntentPriority(data.get("priority", 2)),
            params=data.get("params", {}),
            raw_text=data.get("raw_text", ""),
            language=data.get("language", "zh"),
            tech_stack=data.get("tech_stack", []),
            action=data.get("action", ""),
            target=data.get("target", ""),
        )


class BaseIntentEngine:
    """
    基础意图引擎（模板方法模式）
    
    提供通用功能：
    1. 文本预处理（清洗、分词）
    2. 缓存管理（LRU）
    3. 统计信息
    4. 模板方法：parse() 调用 do_parse()
    
    子类只需实现 do_parse(text) -> IntentResult
    
    使用方式：
    class MyEngine(BaseIntentEngine):
        def do_parse(self, text: str) -> IntentResult:
            # 实现具体的意图解析逻辑
            return IntentResult(...)
    """
    
    def __init__(self, enable_cache: bool = True, cache_size: int = 100):
        """
        初始化意图引擎
        
        Args:
            enable_cache: 是否启用缓存
            cache_size: 缓存大小
        """
        self.enable_cache = enable_cache
        self.cache_size = cache_size
        self._cache: Dict[str, IntentResult] = {}
        self._keyword_index: Dict[str, List[IntentType]] = defaultdict(list)
        
        # 统计
        self.total_parsed = 0
        self.cache_hits = 0
        
    def parse(self, text: str) -> IntentResult:
        """
        解析意图（主入口，模板方法）
        
        流程：
        1. 检查缓存
        2. 调用 do_parse()（子类实现）
        3. 存入缓存
        4. 更新统计
        
        Args:
            text: 用户输入文本
            
        Returns:
            IntentResult: 意图识别结果
        """
        # 1. 检查缓存
        if self.enable_cache:
            cached = self.get_from_cache(text)
            if cached is not None:
                self.cache_hits += 1
                return cached
        
        # 2. 调用子类实现
        result = self.do_parse(text)
        
        # 3. 存入缓存
        if self.enable_cache and result is not None:
            self.save_to_cache(text, result)
        
        # 4. 更新统计
        self.total_parsed += 1
        
        return result
    
    def do_parse(self, text: str) -> IntentResult:
        """
        解析意图（钩子方法，子类必须实现）
        
        Args:
            text: 用户输入文本
            
        Returns:
            IntentResult: 意图识别结果
        """
        raise NotImplementedError("Subclasses must implement do_parse()")
    
    def classify(self, text: str) -> Tuple[IntentType, float]:
        """
        分类意图（通用实现，子类可重写）
        
        Args:
            text: 输入文本
            
        Returns:
            Tuple[IntentType, float]: (意图类型, 置信度)
        """
        # 预处理
        cleaned = self.preprocess(text)
        
        # 关键词匹配（基于索引）
        matched_types = []
        for word in cleaned.split():
            if word in self._keyword_index:
                matched_types.extend(self._keyword_index[word])
        
        if matched_types:
            # 返回匹配最多的类型
            from collections import Counter
            counter = Counter(matched_types)
            intent_type = counter.most_common(1)[0][0]
            confidence = counter[intent_type] / len(matched_types)
            return intent_type, min(confidence * 2, 1.0)  # 放大置信度
        
        return IntentType.UNKNOWN, 0.0
    
    def extract_params(self, text: str, intent_type: IntentType) -> Dict[str, Any]:
        """
        提取参数（通用实现，子类可重写）
        
        Args:
            text: 输入文本
            intent_type: 意图类型
            
        Returns:
            Dict: 提取的参数
        """
        params = {}
        
        # 通用参数提取
        # 1. 提取引号中的内容
        quotes = re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
        if quotes:
            params["quoted"] = [q for pair in quotes for q in pair if q]
        
        # 2. 提取语言/技术栈
        tech_keywords = ["python", "javascript", "typescript", "java", "cpp", "rust", "go"]
        for tech in tech_keywords:
            if tech in text.lower():
                params.setdefault("tech_stack", []).append(tech)
        
        # 3. 提取数字
        numbers = re.findall(r'\d+', text)
        if numbers:
            params["numbers"] = [int(n) for n in numbers]
        
        return params
    
    def preprocess(self, text: str) -> str:
        """
        预处理文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清洗后的文本
        """
        # 转小写
        text = text.lower()
        
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def build_keyword_index(self, keyword_map: Dict[str, IntentType]) -> None:
        """
        构建关键词索引（用于快速匹配）
        
        Args:
            keyword_map: {关键词: 意图类型} 映射
        """
        for keyword, intent_type in keyword_map.items():
            self._keyword_index[keyword].append(intent_type)
    
    def get_from_cache(self, text: str) -> Optional[IntentResult]:
        """
        从缓存获取结果
        
        Args:
            text: 输入文本
            
        Returns:
            Optional[IntentResult]: 缓存的结果，如果没有则返回 None
        """
        if not self.enable_cache:
            return None
        
        key = self.preprocess(text)
        if key in self._cache:
            return self._cache[key]
        
        return None
    
    def save_to_cache(self, text: str, result: IntentResult) -> None:
        """
        保存结果到缓存
        
        Args:
            text: 输入文本
            result: 意图识别结果
        """
        if not self.enable_cache:
            return
        
        key = self.preprocess(text)
        
        # LRU 策略：如果缓存满了，删除第一个
        if len(self._cache) >= self.cache_size:
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        
        self._cache[key] = result
    
    def calculate_confidence(self, matches: int, total_keywords: int) -> float:
        """
        计算置信度
        
        Args:
            matches: 匹配的关键词数量
            total_keywords: 总关键词数量
            
        Returns:
            float: 置信度 (0.0 - 1.0)
        """
        if total_keywords == 0:
            return 0.0
        
        base_confidence = matches / total_keywords
        
        # 根据文本长度调整
        length_factor = min(1.0, len(self.preprocess(text)) / 50)
        
        return min(base_confidence * length_factor * 1.5, 1.0)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_parsed": self.total_parsed,
            "cache_size": len(self._cache),
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hits / self.total_parsed if self.total_parsed > 0 else 0,
            "keyword_index_size": sum(len(v) for v in self._keyword_index.values()),
        }
