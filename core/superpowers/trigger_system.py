"""
智能技能触发系统

基于上下文分析自动激活相关技能
"""

import asyncio
import re
import time
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from .skills import get_skill_registry


class ContextAnalyzer:
    """
    上下文分析器

    分析文本上下文，提取关键词和意图
    """

    def __init__(self):
        self.stop_words = set(stopwords.words('english'))
        self.keyword_patterns = {
            "planning": ["plan", "设计", "架构", "方案", "规划"],
            "implementation": ["implement", "实现", "编码", "开发", "构建"],
            "testing": ["test", "测试", "验证", "检查", "单元测试"],
            "review": ["review", "审查", "代码审查", "检查", "评估"],
            "completion": ["complete", "完成", "结束", "交付", "总结"]
        }

    def analyze(self, context: str) -> Dict[str, Any]:
        """
        分析上下文

        Args:
            context: 上下文文本

        Returns:
            Dict: 分析结果
        """
        context_lower = context.lower()

        # 提取关键词
        keywords = self._extract_keywords(context_lower)

        # 识别意图
        intent = self._identify_intent(keywords, context_lower)

        # 提取实体
        entities = self._extract_entities(context)

        # 分析情绪
        sentiment = self._analyze_sentiment(context)

        return {
            "keywords": keywords,
            "intent": intent,
            "entities": entities,
            "sentiment": sentiment,
            "context_length": len(context),
            "timestamp": time.time()
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词

        Args:
            text: 文本

        Returns:
            List[str]: 关键词列表
        """
        try:
            tokens = word_tokenize(text)
            keywords = [
                word for word in tokens
                if word.isalpha() and word not in self.stop_words
            ]
            return keywords[:20]  # 限制关键词数量
        except Exception:
            # 简化的关键词提取
            words = re.findall(r'\b\w+\b', text)
            return [word for word in words if len(word) > 2][:20]

    def _identify_intent(self, keywords: List[str], text: str) -> str:
        """
        识别意图

        Args:
            keywords: 关键词列表
            text: 文本

        Returns:
            str: 意图
        """
        for intent, patterns in self.keyword_patterns.items():
            for pattern in patterns:
                if pattern.lower() in text:
                    return intent

        # 基于关键词频率识别意图
        intent_scores = {}
        for intent, patterns in self.keyword_patterns.items():
            score = 0
            for pattern in patterns:
                score += text.count(pattern.lower())
            if score > 0:
                intent_scores[intent] = score

        if intent_scores:
            return max(intent_scores, key=intent_scores.get)

        return "general"

    def _extract_entities(self, text: str) -> List[str]:
        """
        提取实体

        Args:
            text: 文本

        Returns:
            List[str]: 实体列表
        """
        # 简单的实体提取
        entities = []

        # 提取文件名
        file_patterns = [
            r'\b\w+\.py\b',
            r'\b\w+\.js\b',
            r'\b\w+\.ts\b',
            r'\b\w+\.html\b',
            r'\b\w+\.css\b'
        ]

        for pattern in file_patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)

        # 提取函数名
        function_patterns = [
            r'def\s+(\w+)\s*\(',
            r'function\s+(\w+)\s*\('
        ]

        for pattern in function_patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)

        return list(set(entities))[:10]  # 去重并限制数量

    def _analyze_sentiment(self, text: str) -> str:
        """
        分析情绪

        Args:
            text: 文本

        Returns:
            str: 情绪
        """
        positive_words = ["good", "great", "excellent", "perfect", "awesome", "success", "pass", "完成", "成功", "优秀"]
        negative_words = ["bad", "terrible", "error", "fail", "issue", "problem", "bug", "错误", "失败", "问题"]

        positive_count = sum(1 for word in positive_words if word in text.lower())
        negative_count = sum(1 for word in negative_words if word in text.lower())

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"


class TriggerSystem:
    """
    触发系统

    基于上下文自动触发相关技能
    """

    def __init__(self, analyzer: Optional[ContextAnalyzer] = None):
        self.analyzer = analyzer or ContextAnalyzer()
        self.skill_registry = get_skill_registry()
        self.trigger_history: List[Dict[str, Any]] = []

    async def analyze_context(self, context: str) -> List[str]:
        """
        分析上下文并推荐技能

        Args:
            context: 上下文文本

        Returns:
            List[str]: 推荐的技能 ID 列表
        """
        analysis = self.analyzer.analyze(context)
        recommended_skills = self._recommend_skills(analysis)

        # 记录触发历史
        trigger_record = {
            "context": context[:100] + "..." if len(context) > 100 else context,
            "analysis": analysis,
            "recommended_skills": recommended_skills,
            "timestamp": time.time()
        }
        self.trigger_history.append(trigger_record)

        return recommended_skills

    def _recommend_skills(self, analysis: Dict[str, Any]) -> List[str]:
        """
        推荐技能

        Args:
            analysis: 上下文分析结果

        Returns:
            List[str]: 推荐的技能 ID 列表
        """
        intent = analysis.get("intent", "general")
        keywords = analysis.get("keywords", [])
        entities = analysis.get("entities", [])

        # 基于意图推荐技能
        intent_skill_map = {
            "planning": ["planning"],
            "implementation": ["implementation"],
            "testing": ["testing"],
            "review": ["review"],
            "completion": ["completion"]
        }

        recommended = intent_skill_map.get(intent, [])

        # 基于关键词推荐技能
        for skill_id in self.skill_registry.get_all_skills():
            metadata = self.skill_registry.get_skill_metadata(skill_id)
            if metadata:
                # 检查技能的触发器
                for trigger in metadata.triggers:
                    if any(trigger.lower() in keyword.lower() for keyword in keywords):
                        if skill_id not in recommended:
                            recommended.append(skill_id)

        # 基于实体推荐技能
        if entities:
            # 检查是否有文件相关的实体
            has_files = any("." in entity for entity in entities)
            if has_files and "implementation" not in recommended:
                recommended.append("implementation")

        return recommended[:3]  # 限制推荐数量

    async def trigger_skills(
        self,
        context: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        触发技能

        Args:
            context: 上下文
            parameters: 参数

        Returns:
            List[Dict]: 技能执行结果
        """
        from .skills import get_skill_executor
        executor = get_skill_executor()

        recommended_skills = await self.analyze_context(context)
        results = []

        for skill_id in recommended_skills:
            result = await executor.execute(skill_id, parameters or {})
            results.append({
                "skill_id": skill_id,
                "result": result
            })

        return results

    def get_trigger_history(self) -> List[Dict[str, Any]]:
        """
        获取触发历史

        Returns:
            List[Dict[str, Any]]: 触发历史
        """
        return self.trigger_history

    def get_trigger_stats(self) -> Dict[str, Any]:
        """
        获取触发统计

        Returns:
            Dict: 触发统计
        """
        if not self.trigger_history:
            return {
                "total_triggers": 0,
                "skill_distribution": {}
            }

        skill_counts = {}
        for record in self.trigger_history:
            for skill in record.get("recommended_skills", []):
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

        return {
            "total_triggers": len(self.trigger_history),
            "skill_distribution": skill_counts,
            "average_skills_per_trigger": sum(len(record.get("recommended_skills", [])) for record in self.trigger_history) / len(self.trigger_history)
        }


# 全局实例

_global_trigger_system: Optional[TriggerSystem] = None
_global_analyzer: Optional[ContextAnalyzer] = None


def get_trigger_system() -> TriggerSystem:
    """获取触发系统"""
    global _global_trigger_system
    if _global_trigger_system is None:
        _global_trigger_system = TriggerSystem(get_context_analyzer())
    return _global_trigger_system


def get_context_analyzer() -> ContextAnalyzer:
    """获取上下文分析器"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = ContextAnalyzer()
    return _global_analyzer