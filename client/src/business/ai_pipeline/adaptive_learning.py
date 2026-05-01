"""
自适应学习系统 - AdaptiveLearningSystem

核心功能：
1. 团队编码风格学习
2. 需求模式识别
3. 持续优化策略
4. 反馈收集与分析
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from pathlib import Path
from loguru import logger


class LearningMode(Enum):
    """学习模式"""
    ACTIVE = "active"
    PASSIVE = "passive"
    OBSERVATION = "observation"


class PatternType(Enum):
    """模式类型"""
    CODING_STYLE = "coding_style"
    REQUIREMENT_PATTERN = "requirement_pattern"
    PROBLEM_SOLUTION = "problem_solution"
    BEST_PRACTICE = "best_practice"


@dataclass
class Pattern:
    """模式记录"""
    id: str
    type: PatternType
    name: str
    description: str
    examples: List[str] = field(default_factory=list)
    confidence: float = 0.0
    usage_count: int = 0


@dataclass
class FeedbackRecord:
    """反馈记录"""
    id: str
    task_id: str
    user_id: str
    feedback_type: str
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StylePreference:
    """编码风格偏好"""
    indent_style: str = "spaces"
    indent_size: int = 4
    line_length: int = 88
    quote_style: str = "double"
    naming_convention: str = "snake_case"
    docstring_style: str = "google"


class AdaptiveLearningSystem:
    """
    自适应学习系统
    
    核心特性：
    1. 团队编码风格学习 - 自动学习团队代码风格并应用
    2. 需求模式识别 - 识别重复需求模式，复用已有解决方案
    3. 持续优化 - 根据执行反馈不断优化生成质量
    4. 反馈驱动改进 - 收集用户反馈，持续改进模型
    """

    def __init__(self):
        self._logger = logger.bind(component="AdaptiveLearningSystem")
        self._patterns: Dict[str, Pattern] = {}
        self._feedback_records: List[FeedbackRecord] = []
        self._style_preferences = StylePreference()
        self._learning_mode = LearningMode.ACTIVE
        self._data_dir = Path.home() / ".livingtree" / "learning_data"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        self._load_patterns()

    def _load_patterns(self):
        """加载已学习的模式"""
        patterns_file = self._data_dir / "patterns.json"
        if patterns_file.exists():
            try:
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for pattern_data in data:
                    pattern = Pattern(
                        id=pattern_data["id"],
                        type=PatternType(pattern_data["type"]),
                        name=pattern_data["name"],
                        description=pattern_data["description"],
                        examples=pattern_data.get("examples", []),
                        confidence=pattern_data.get("confidence", 0.0),
                        usage_count=pattern_data.get("usage_count", 0)
                    )
                    self._patterns[pattern.id] = pattern
                
                self._logger.info(f"加载了 {len(self._patterns)} 个模式")
            except Exception as e:
                self._logger.error(f"加载模式失败: {e}")

    def _save_patterns(self):
        """保存模式到文件"""
        patterns_file = self._data_dir / "patterns.json"
        data = [
            {
                "id": p.id,
                "type": p.type.value,
                "name": p.name,
                "description": p.description,
                "examples": p.examples,
                "confidence": p.confidence,
                "usage_count": p.usage_count
            }
            for p in self._patterns.values()
        ]
        
        with open(patterns_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def learn_coding_style(self, code_samples: List[str]):
        """学习团队编码风格"""
        self._logger.info("开始学习编码风格...")
        
        if not code_samples:
            return
        
        # 分析缩进风格
        self._analyze_indent_style(code_samples)
        
        # 分析命名约定
        self._analyze_naming_convention(code_samples)
        
        # 分析文档风格
        self._analyze_docstring_style(code_samples)
        
        self._logger.info("编码风格学习完成")

    def _analyze_indent_style(self, code_samples: List[str]):
        """分析缩进风格"""
        space_counts = []
        tab_counts = []
        
        for sample in code_samples:
            for line in sample.split("\n"):
                stripped = line.lstrip()
                if stripped:
                    indent = line[:len(line) - len(stripped)]
                    if indent.startswith(" "):
                        space_counts.append(len(indent))
                    elif indent.startswith("\t"):
                        tab_counts.append(len(indent))
        
        if space_counts:
            self._style_preferences.indent_style = "spaces"
            self._style_preferences.indent_size = round(sum(space_counts) / len(space_counts))
        elif tab_counts:
            self._style_preferences.indent_style = "tabs"
            self._style_preferences.indent_size = round(sum(tab_counts) / len(tab_counts))

    def _analyze_naming_convention(self, code_samples: List[str]):
        """分析命名约定"""
        snake_case = 0
        camel_case = 0
        pascal_case = 0
        
        import re
        
        for sample in code_samples:
            # 查找变量名
            variables = re.findall(r'\b[a-z_][a-z0-9_]*\b', sample)
            snake_case += len(variables)
            
            # 查找驼峰命名
            camel_vars = re.findall(r'\b[a-z][a-zA-Z0-9]*\b', sample)
            camel_case += len(camel_vars)
            
            # 查找 Pascal 命名
            pascal_vars = re.findall(r'\b[A-Z][a-zA-Z0-9]*\b', sample)
            pascal_case += len(pascal_vars)
        
        total = snake_case + camel_case + pascal_case
        if total > 0:
            if snake_case > camel_case and snake_case > pascal_case:
                self._style_preferences.naming_convention = "snake_case"
            elif camel_case > snake_case and camel_case > pascal_case:
                self._style_preferences.naming_convention = "camelCase"
            else:
                self._style_preferences.naming_convention = "PascalCase"

    def _analyze_docstring_style(self, code_samples: List[str]):
        """分析文档风格"""
        google_style = 0
        numpy_style = 0
        reST_style = 0
        
        for sample in code_samples:
            if ":param" in sample and ":return" in sample:
                google_style += 1
            elif "Parameters" in sample and "Returns" in sample:
                numpy_style += 1
            elif ":param:" in sample:
                reST_style += 1
        
        if google_style >= numpy_style and google_style >= reST_style:
            self._style_preferences.docstring_style = "google"
        elif numpy_style >= google_style and numpy_style >= reST_style:
            self._style_preferences.docstring_style = "numpy"
        else:
            self._style_preferences.docstring_style = "rest"

    async def recognize_pattern(self, requirement: str) -> Optional[Pattern]:
        """识别需求模式"""
        self._logger.debug(f"识别需求模式: {requirement}")
        
        for pattern in self._patterns.values():
            if pattern.type == PatternType.REQUIREMENT_PATTERN:
                for example in pattern.examples:
                    if self._match_pattern(example, requirement):
                        pattern.usage_count += 1
                        return pattern
        
        return None

    def _match_pattern(self, pattern: str, text: str) -> bool:
        """简单的模式匹配"""
        pattern_keywords = pattern.lower().split()
        text_keywords = text.lower().split()
        
        matched = sum(1 for kw in pattern_keywords if kw in text_keywords)
        return matched >= len(pattern_keywords) * 0.6

    async def add_pattern(self, type: PatternType, name: str, description: str, example: str):
        """添加新模式"""
        import time
        
        pattern_id = f"pattern_{type.value}_{int(time.time())}"
        
        pattern = Pattern(
            id=pattern_id,
            type=type,
            name=name,
            description=description,
            examples=[example],
            confidence=0.7
        )
        
        self._patterns[pattern_id] = pattern
        self._save_patterns()
        
        self._logger.info(f"添加新模式: {name}")

    async def collect_feedback(self, task_id: str, user_id: str, feedback_type: str, content: str, metadata: Dict[str, Any] = None):
        """收集反馈"""
        import time
        
        feedback = FeedbackRecord(
            id=f"feedback_{int(time.time())}",
            task_id=task_id,
            user_id=user_id,
            feedback_type=feedback_type,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self._feedback_records.append(feedback)
        
        # 分析反馈并更新模式
        await self._analyze_feedback(feedback)
        
        self._logger.info(f"收集到反馈: {feedback_type}")

    async def _analyze_feedback(self, feedback: FeedbackRecord):
        """分析反馈"""
        # 如果是正面反馈，增加相关模式的置信度
        if feedback.feedback_type == "positive":
            # 查找相关模式并更新
            for pattern in self._patterns.values():
                if any(kw in feedback.content.lower() for kw in pattern.name.lower().split()):
                    pattern.confidence = min(1.0, pattern.confidence + 0.05)
        
        # 如果是负面反馈，减少相关模式的置信度
        elif feedback.feedback_type == "negative":
            for pattern in self._patterns.values():
                if any(kw in feedback.content.lower() for kw in pattern.name.lower().split()):
                    pattern.confidence = max(0.0, pattern.confidence - 0.1)
        
        self._save_patterns()

    async def optimize_generation(self, code: str, task_context: Dict[str, Any]) -> str:
        """优化代码生成"""
        # 应用学习到的编码风格
        code = self._apply_style_preferences(code)
        
        # 应用最佳实践模式
        code = await self._apply_best_practices(code, task_context)
        
        return code

    def _apply_style_preferences(self, code: str) -> str:
        """应用编码风格偏好"""
        lines = code.split("\n")
        result = []
        
        for line in lines:
            # 应用缩进
            if line.strip():
                stripped = line.lstrip()
                indent_length = len(line) - len(stripped)
                
                if self._style_preferences.indent_style == "spaces":
                    new_indent = " " * (indent_length // 4 * self._style_preferences.indent_size)
                else:
                    new_indent = "\t" * (indent_length // self._style_preferences.indent_size)
                
                result.append(new_indent + stripped)
            else:
                result.append(line)
        
        return "\n".join(result)

    async def _apply_best_practices(self, code: str, context: Dict[str, Any]) -> str:
        """应用最佳实践"""
        # 查找相关的最佳实践模式
        for pattern in self._patterns.values():
            if pattern.type == PatternType.BEST_PRACTICE:
                # 简单的模式应用
                for example in pattern.examples:
                    if example in code:
                        code = code.replace(example, pattern.description)
        
        return code

    def get_style_preferences(self) -> StylePreference:
        """获取编码风格偏好"""
        return self._style_preferences

    def get_patterns(self, type: Optional[PatternType] = None) -> List[Pattern]:
        """获取模式列表"""
        if type:
            return [p for p in self._patterns.values() if p.type == type]
        return list(self._patterns.values())

    def get_feedback_summary(self) -> Dict[str, Any]:
        """获取反馈摘要"""
        positive = sum(1 for f in self._feedback_records if f.feedback_type == "positive")
        negative = sum(1 for f in self._feedback_records if f.feedback_type == "negative")
        neutral = len(self._feedback_records) - positive - negative
        
        return {
            "total": len(self._feedback_records),
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "trend": "improving" if positive > negative else "declining" if negative > positive else "stable"
        }


def get_adaptive_learning_system() -> AdaptiveLearningSystem:
    """获取自适应学习系统单例"""
    global _learning_instance
    if _learning_instance is None:
        _learning_instance = AdaptiveLearningSystem()
    return _learning_instance


_learning_instance = None