"""
智能任务分类器（SmartTaskClassifier）

在 L0 层增加轻量级任务复杂度评估，自动判断需要调用的层级。

功能：
1. 轻量级任务复杂度评估
2. 动态阈值调整（根据资源状况）
3. 支持多种分类策略
4. 可扩展性强

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import re
import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """任务复杂度等级"""
    TRIVIAL = "trivial"       # 极其简单（问候、确认）→ L0
    SIMPLE = "simple"         # 简单（问答、关键词提取）→ L0/L1
    MEDIUM = "medium"         # 中等（摘要、翻译）→ L1/L2
    COMPLEX = "complex"       # 复杂（代码生成、推理）→ L2/L3
    ADVANCED = "advanced"     # 高级（深度推理、创作）→ L3/L4
    EXPERT = "expert"         # 专家级（专业领域、长上下文）→ L4


class TaskType(Enum):
    """任务类型"""
    GREETING = "greeting"           # 问候
    QUESTION = "question"           # 问答
    SUMMARIZATION = "summarization" # 摘要
    TRANSLATION = "translation"     # 翻译
    CODE = "code"                   # 代码相关
    REASONING = "reasoning"         # 推理
    CREATION = "creation"           # 创作
    ANALYSIS = "analysis"           # 分析
    PLANNING = "planning"           # 规划
    UNKNOWN = "unknown"             # 未知


@dataclass
class TaskAnalysis:
    """任务分析结果"""
    complexity: TaskComplexity
    task_type: TaskType
    estimated_tokens: int
    required_context: int
    confidence: float
    suggested_tier: str
    features: Dict[str, float] = field(default_factory=dict)


class SmartTaskClassifier:
    """
    智能任务分类器
    
    使用轻量级规则和特征分析来评估任务复杂度，无需调用大型模型。
    """
    
    # 关键词 → 任务类型 映射
    TASK_TYPE_KEYWORDS = {
        TaskType.GREETING: [
            "你好", "您好", "hello", "hi", "嗨", "早上好", "下午好", "晚上好",
            "再见", "拜拜", "bye", "goodbye"
        ],
        TaskType.SUMMARIZATION: [
            "总结", "摘要", "概括", "简述", "总结一下", "概括一下", "summarize",
            "summary", "brief", "概括来说"
        ],
        TaskType.TRANSLATION: [
            "翻译", "译成", "英文", "中文", "英文翻译", "中文翻译", "translate",
            "translation", "译成英文", "译成中文"
        ],
        TaskType.CODE: [
            "代码", "编程", "python", "java", "javascript", "js", "cpp", "c++",
            "function", "def", "class", "代码实现", "写代码", "coding",
            "debug", "调试", "review", "审查"
        ],
        TaskType.REASONING: [
            "为什么", "因为", "所以", "因此", "推理", "分析", "论证",
            "证明", "推导", "reason", "because", "why", "therefore"
        ],
        TaskType.CREATION: [
            "写", "创作", "生成", "设计", "构思", "创建", "produce",
            "create", "write", "generate"
        ],
        TaskType.PLANNING: [
            "计划", "规划", "方案", "步骤", "流程", "如何", "how",
            "plan", "schedule", "strategy"
        ],
    }
    
    # 复杂度指示词
    COMPLEXITY_INDICATORS = {
        TaskComplexity.TRIVIAL: [
            "是", "不是", "对", "错", "好", "可以", "行", "没问题",
            "yes", "no", "ok", "okay", "sure", "fine"
        ],
        TaskComplexity.SIMPLE: [
            "什么是", "什么叫", "定义", "解释", "说明", "什么", "哪个",
            "who", "what", "where", "when", "which"
        ],
        TaskComplexity.MEDIUM: [
            "总结", "翻译", "改写", "解释一下", "详细说明",
            "explain", "describe", "summarize"
        ],
        TaskComplexity.COMPLEX: [
            "实现", "编写", "设计", "开发", "构建", "解决",
            "implement", "develop", "build", "solve", "create"
        ],
        TaskComplexity.ADVANCED: [
            "深度", "深入", "详细", "全面", "完整", "系统性",
            "deep", "detailed", "comprehensive", "thorough"
        ],
        TaskComplexity.EXPERT: [
            "专家", "专业", "精通", "深入分析", "详细论证",
            "expert", "professional", "specialized"
        ],
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化分类器"""
        self.config = config or {}
        
        # 阈值配置（可根据资源状况动态调整）
        self.thresholds = {
            "trivial_length": self.config.get("trivial_length", 20),
            "simple_length": self.config.get("simple_length", 50),
            "medium_length": self.config.get("medium_length", 150),
            "complex_length": self.config.get("complex_length", 300),
            "advanced_length": self.config.get("advanced_length", 500),
        }
        
        # 特征权重
        self.weights = {
            "length": 0.3,
            "complexity_keywords": 0.25,
            "task_type": 0.25,
            "code_presence": 0.15,
            "structure": 0.05,
        }
        
        logger.info("SmartTaskClassifier 初始化完成")
    
    def analyze(self, prompt: str, context_length: int = 0) -> TaskAnalysis:
        """
        分析任务复杂度
        
        Args:
            prompt: 用户输入
            context_length: 上下文长度（token数）
        
        Returns:
            TaskAnalysis 任务分析结果
        """
        prompt = prompt.strip()
        features = self._extract_features(prompt, context_length)
        complexity = self._determine_complexity(features)
        task_type = self._determine_task_type(prompt)
        suggested_tier = self._suggest_tier(complexity, context_length)
        
        return TaskAnalysis(
            complexity=complexity,
            task_type=task_type,
            estimated_tokens=self._estimate_tokens(prompt),
            required_context=context_length,
            confidence=self._calculate_confidence(features),
            suggested_tier=suggested_tier,
            features=features
        )
    
    def _extract_features(self, prompt: str, context_length: int) -> Dict[str, float]:
        """提取任务特征"""
        features = {}
        
        # 1. 长度特征
        features["length"] = min(len(prompt) / 500, 1.0)
        
        # 2. 复杂度关键词匹配
        complexity_score = 0.0
        complexity_values = {
            TaskComplexity.TRIVIAL: 1,
            TaskComplexity.SIMPLE: 2,
            TaskComplexity.MEDIUM: 3,
            TaskComplexity.COMPLEX: 4,
            TaskComplexity.ADVANCED: 5,
            TaskComplexity.EXPERT: 6,
        }
        for level, keywords in self.COMPLEXITY_INDICATORS.items():
            for kw in keywords:
                if kw.lower() in prompt.lower():
                    complexity_score += complexity_values.get(level, 1)
        features["complexity_keywords"] = min(complexity_score / 10, 1.0)
        
        # 3. 任务类型匹配
        type_score = 0.0
        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in prompt.lower():
                    type_score += 1.0
                    break  # 每个类型只算一次
        features["task_type"] = min(type_score / len(self.TASK_TYPE_KEYWORDS), 1.0)
        
        # 4. 代码存在检测
        code_patterns = [r"`[^`]+`", r"```[\s\S]*?```", r"def\s+\w+", r"function\s+\w+"]
        has_code = any(re.search(pattern, prompt, re.IGNORECASE) for pattern in code_patterns)
        features["code_presence"] = 1.0 if has_code else 0.0
        
        # 5. 结构复杂度（列表、层级等）
        structure_count = prompt.count("步骤") + prompt.count("：") + prompt.count("。")
        features["structure"] = min(structure_count / 10, 1.0)
        
        # 6. 上下文长度
        features["context_length"] = min(context_length / 8192, 1.0)
        
        return features
    
    def _determine_complexity(self, features: Dict[str, float]) -> TaskComplexity:
        """根据特征确定复杂度等级"""
        # 计算综合得分
        score = (
            features["length"] * self.weights["length"] +
            features["complexity_keywords"] * self.weights["complexity_keywords"] +
            features["task_type"] * self.weights["task_type"] +
            features["code_presence"] * self.weights["code_presence"] +
            features["structure"] * self.weights["structure"]
        )
        
        # 根据得分确定复杂度
        if score < 0.15:
            return TaskComplexity.TRIVIAL
        elif score < 0.3:
            return TaskComplexity.SIMPLE
        elif score < 0.5:
            return TaskComplexity.MEDIUM
        elif score < 0.7:
            return TaskComplexity.COMPLEX
        elif score < 0.85:
            return TaskComplexity.ADVANCED
        else:
            return TaskComplexity.EXPERT
    
    def _determine_task_type(self, prompt: str) -> TaskType:
        """确定任务类型"""
        prompt_lower = prompt.lower()
        
        # 检查问候语（优先级最高）
        for kw in self.TASK_TYPE_KEYWORDS[TaskType.GREETING]:
            if kw.lower() in prompt_lower:
                return TaskType.GREETING
        
        # 检查其他类型
        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            if task_type == TaskType.GREETING:
                continue
            for kw in keywords:
                if kw.lower() in prompt_lower:
                    return task_type
        
        # 默认：检查是否是问答
        if "?" in prompt or "？" in prompt:
            return TaskType.QUESTION
        
        return TaskType.UNKNOWN
    
    def _suggest_tier(self, complexity: TaskComplexity, context_length: int) -> str:
        """根据复杂度建议层级"""
        tier_map = {
            TaskComplexity.TRIVIAL: "L0",
            TaskComplexity.SIMPLE: "L1",
            TaskComplexity.MEDIUM: "L2",
            TaskComplexity.COMPLEX: "L3",
            TaskComplexity.ADVANCED: "L3",
            TaskComplexity.EXPERT: "L4",
        }
        
        base_tier = tier_map.get(complexity, "L2")
        
        # 根据上下文长度调整
        if context_length > 8192:
            # 长上下文需要更高层级
            tier_num = int(base_tier[1:])
            return f"L{min(tier_num + 1, 4)}"
        elif context_length > 4096:
            tier_num = int(base_tier[1:])
            return f"L{min(tier_num + 0, 4)}"
        
        return base_tier
    
    def _estimate_tokens(self, prompt: str) -> int:
        """估算 token 数量"""
        # 粗略估算：中文字符约 1.5 token，英文字符约 1/4 token
        char_count = len(prompt)
        ascii_count = sum(1 for c in prompt if ord(c) < 128)
        return int((char_count - ascii_count) * 1.5 + ascii_count * 0.25)
    
    def _calculate_confidence(self, features: Dict[str, float]) -> float:
        """计算分类置信度"""
        # 置信度基于特征的明显程度
        indicators = [
            features["complexity_keywords"],
            features["task_type"],
            features["code_presence"]
        ]
        return sum(indicators) / len(indicators)
    
    def adjust_thresholds(self, resource_usage: float):
        """
        根据资源使用情况动态调整阈值
        
        Args:
            resource_usage: 资源使用率 (0-1)
        """
        # 资源紧张时，提高复杂度阈值，倾向于使用低层级模型
        if resource_usage > 0.8:
            self.thresholds["trivial_length"] = 30
            self.thresholds["simple_length"] = 80
            self.thresholds["medium_length"] = 200
            logger.info("资源紧张，调整阈值以使用更轻量级模型")
        elif resource_usage > 0.5:
            # 中等负载，保持默认阈值
            pass
        else:
            # 资源充足，降低阈值，倾向于使用高层级模型
            self.thresholds["trivial_length"] = 15
            self.thresholds["simple_length"] = 40
            self.thresholds["medium_length"] = 100
            logger.info("资源充足，调整阈值以使用更高质量模型")


# 全局分类器实例
_classifier_instance = None

def get_task_classifier() -> SmartTaskClassifier:
    """获取全局智能任务分类器实例"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = SmartTaskClassifier()
    return _classifier_instance