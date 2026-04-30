"""
Token优化器 (Token Optimizer)
=============================

集成 Token Savior 功能，实现：
1. 智能截断 - 根据上下文重要性截断文本
2. 语义压缩 - 保留核心语义的同时减少Token
3. 冗余去除 - 去除重复和低信息量内容
4. 动态优化 - 根据目标Token数自动调整

核心特性：
- 支持多种优化策略
- 可配置的压缩级别
- 保留技术准确性
- 支持中文和英文

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class OptimizationLevel(Enum):
    """优化级别"""
    LITE = "lite"           # 轻量级优化（保留大部分内容）
    BALANCED = "balanced"   # 平衡优化（默认）
    AGGRESSIVE = "aggressive" # 激进优化（大幅压缩）
    EXTREME = "extreme"     # 极端优化（最小化输出）


class OptimizationStrategy(Enum):
    """优化策略"""
    TRUNCATE = "truncate"           # 简单截断
    SEMANTIC = "semantic"           # 语义压缩
    REDUNDANCY = "redundancy"       # 冗余去除
    HYBRID = "hybrid"               # 混合策略（默认）


@dataclass
class OptimizationResult:
    """优化结果"""
    optimized_text: str
    original_tokens: int
    optimized_tokens: int
    compression_ratio: float
    strategy: OptimizationStrategy
    level: OptimizationLevel


class TokenOptimizer:
    """
    Token优化器
    
    核心功能：
    1. 智能截断 - 根据上下文重要性截断文本
    2. 语义压缩 - 保留核心语义的同时减少Token
    3. 冗余去除 - 去除重复和低信息量内容
    4. 动态优化 - 根据目标Token数自动调整
    
    参考项目：https://github.com/Mibayy/token-savior
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 配置参数
        self._config = {
            "default_level": "balanced",
            "default_strategy": "hybrid",
            "min_tokens": 100,
            "max_tokens": 8192,
            "redundancy_threshold": 0.3,  # 重复率阈值
        }
        
        # 停用词列表（用于冗余检测）
        self._stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare",
            "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
            "from", "as", "into", "through", "during", "before", "after",
            "above", "below", "between", "under", "again", "further", "then",
            "once", "here", "there", "when", "where", "why", "how", "all",
            "each", "few", "more", "most", "other", "some", "such", "no",
            "nor", "not", "only", "own", "same", "so", "than", "too", "very",
            "just", "but", "if", "or", "and", "because", "until", "while",
            "this", "that", "these", "those", "i", "you", "he", "she", "it",
            "we", "they", "me", "him", "her", "us", "them", "my", "your",
            "his", "its", "our", "their", "what", "which", "who", "whom",
            "whose", "我", "你", "他", "她", "它", "我们", "他们", "这", "那",
            "的", "了", "和", "是", "在", "有", "我", "他", "不", "人", "都",
            "一", "一个", "上", "也", "很", "到", "说", "要", "去", "着",
            "没有", "看", "好", "自己", "这", "那", "个", "们", "我", "你",
            "他", "她", "它", "这", "那", "什么", "怎么", "为什么", "如何",
        }
        
        # 标点符号模式
        self._punctuation_pattern = re.compile(r'[，。！？、；：""''（）\[\]{}<>《》【】——…·]')
        
        self._initialized = True
        logger.info("[TokenOptimizer] Token优化器初始化完成")
    
    def configure(self, **kwargs):
        """配置优化器"""
        self._config.update(kwargs)
        logger.info(f"[TokenOptimizer] 配置更新: {kwargs}")
    
    def optimize(self, text: str, target_tokens: int = None, 
                 level: OptimizationLevel = None, 
                 strategy: OptimizationStrategy = None) -> OptimizationResult:
        """
        优化文本，减少Token数量
        
        Args:
            text: 原始文本
            target_tokens: 目标Token数（可选）
            level: 优化级别（可选）
            strategy: 优化策略（可选）
            
        Returns:
            OptimizationResult: 优化结果
        """
        # 使用默认配置
        level = level or OptimizationLevel(self._config["default_level"])
        strategy = strategy or OptimizationStrategy(self._config["default_strategy"])
        
        # 计算原始Token数（粗略估算）
        original_tokens = self._count_tokens(text)
        
        # 如果已经小于最小Token数，直接返回
        if original_tokens <= self._config["min_tokens"]:
            return OptimizationResult(
                optimized_text=text,
                original_tokens=original_tokens,
                optimized_tokens=original_tokens,
                compression_ratio=1.0,
                strategy=strategy,
                level=level
            )
        
        # 确定目标Token数
        if target_tokens:
            target = max(target_tokens, self._config["min_tokens"])
        else:
            target = self._calculate_target(original_tokens, level)
        
        # 根据策略进行优化
        optimized_text = text
        if strategy == OptimizationStrategy.TRUNCATE:
            optimized_text = self._truncate(text, target)
        elif strategy == OptimizationStrategy.SEMANTIC:
            optimized_text = self._semantic_compress(text, target)
        elif strategy == OptimizationStrategy.REDUNDANCY:
            optimized_text = self._remove_redundancy(text, target)
        else:  # HYBRID
            optimized_text = self._hybrid_optimize(text, target, level)
        
        # 计算优化后的Token数
        optimized_tokens = self._count_tokens(optimized_text)
        
        return OptimizationResult(
            optimized_text=optimized_text,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            compression_ratio=optimized_tokens / original_tokens if original_tokens > 0 else 1.0,
            strategy=strategy,
            level=level
        )
    
    def _calculate_target(self, original_tokens: int, level: OptimizationLevel) -> int:
        """根据优化级别计算目标Token数"""
        ratios = {
            OptimizationLevel.LITE: 0.8,      # 保留80%
            OptimizationLevel.BALANCED: 0.5,   # 保留50%
            OptimizationLevel.AGGRESSIVE: 0.3, # 保留30%
            OptimizationLevel.EXTREME: 0.1,    # 保留10%
        }
        
        ratio = ratios.get(level, 0.5)
        target = int(original_tokens * ratio)
        
        return max(target, self._config["min_tokens"])
    
    def _count_tokens(self, text: str) -> int:
        """估算Token数（粗略估算）"""
        # 英文按空格分词，中文按字符
        # 实际应用中应使用tiktoken或类似库
        if not text:
            return 0
        
        # 简单估算：英文单词数 + 中文字符数 * 0.5
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]+', text))
        
        return english_words + int(chinese_chars * 0.5)
    
    def _truncate(self, text: str, target_tokens: int) -> str:
        """简单截断策略"""
        if self._count_tokens(text) <= target_tokens:
            return text
        
        # 按句子截断，尽量保留完整句子
        sentences = self._split_sentences(text)
        result = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)
            if current_tokens + sentence_tokens <= target_tokens:
                result.append(sentence)
                current_tokens += sentence_tokens
            else:
                break
        
        return " ".join(result)
    
    def _semantic_compress(self, text: str, target_tokens: int) -> str:
        """语义压缩策略"""
        if self._count_tokens(text) <= target_tokens:
            return text
        
        # 去除多余空格和换行
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 去除重复内容
        text = self._deduplicate(text)
        
        # 简化句子结构
        text = self._simplify_sentences(text)
        
        # 如果还需要压缩，进行截断
        if self._count_tokens(text) > target_tokens:
            text = self._truncate(text, target_tokens)
        
        return text
    
    def _remove_redundancy(self, text: str, target_tokens: int) -> str:
        """冗余去除策略"""
        if self._count_tokens(text) <= target_tokens:
            return text
        
        # 去除停用词（保留关键信息）
        text = self._remove_stop_words(text)
        
        # 去除重复段落
        text = self._deduplicate(text)
        
        # 去除标点符号周围的多余空格
        text = self._normalize_punctuation(text)
        
        return text
    
    def _hybrid_optimize(self, text: str, target_tokens: int, level: OptimizationLevel) -> str:
        """混合优化策略"""
        # 步骤1：去除冗余
        result = self._remove_redundancy(text, target_tokens)
        
        # 如果还需要压缩，进行语义压缩
        if self._count_tokens(result) > target_tokens:
            result = self._semantic_compress(result, target_tokens)
        
        # 如果还需要压缩，进行截断
        if self._count_tokens(result) > target_tokens:
            result = self._truncate(result, target_tokens)
        
        return result
    
    def _split_sentences(self, text: str) -> List[str]:
        """按句子分割文本"""
        # 中文和英文句子分割
        pattern = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!|。|！|？)\s'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _deduplicate(self, text: str) -> str:
        """去除重复内容"""
        lines = text.split('\n')
        seen = set()
        result = []
        
        for line in lines:
            line_normalized = line.strip().lower()
            if line_normalized not in seen:
                seen.add(line_normalized)
                result.append(line)
        
        return '\n'.join(result)
    
    def _simplify_sentences(self, text: str) -> str:
        """简化句子结构"""
        # 去除不必要的修饰词
        simplified = text
        
        # 去除"非常"、"十分"、"特别"等增强词
        simplified = re.sub(r'非常|十分|特别|极其|相当', '', simplified)
        
        # 去除"基本上"、"基本上来说"等
        simplified = re.sub(r'基本上(来说)?|本质上(来说)?', '', simplified)
        
        # 去除"也就是说"、"换句话说"等
        simplified = re.sub(r'也就是说|换句话说|即', '', simplified)
        
        return simplified
    
    def _remove_stop_words(self, text: str) -> str:
        """去除停用词（保留关键信息）"""
        words = text.split()
        filtered = [word for word in words if word.lower() not in self._stop_words]
        return ' '.join(filtered)
    
    def _normalize_punctuation(self, text: str) -> str:
        """标准化标点符号"""
        # 去除标点符号周围的多余空格
        text = re.sub(r'\s*([，。！？、；：""''（）\[\]{}])\s*', r'\1', text)
        return text
    
    def optimize_prompt(self, prompt: str, max_tokens: int = 4096) -> OptimizationResult:
        """
        便捷方法：优化Prompt
        
        Args:
            prompt: 原始Prompt
            max_tokens: 最大Token数
            
        Returns:
            优化结果
        """
        return self.optimize(prompt, target_tokens=max_tokens)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "config": self._config,
            "stop_words_count": len(self._stop_words),
        }


# 便捷函数
def get_token_optimizer() -> TokenOptimizer:
    """获取Token优化器单例"""
    return TokenOptimizer()


__all__ = [
    "OptimizationLevel",
    "OptimizationStrategy",
    "OptimizationResult",
    "TokenOptimizer",
    "get_token_optimizer",
]