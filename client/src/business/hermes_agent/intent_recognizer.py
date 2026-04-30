"""
意图识别器 (Intent Recognizer)
识别用户意图并提取已知字段，配合 AdaptiveClarifier 实现自适应澄清

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.4)
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging

from business.global_model_router import GlobalModelRouter, ModelCapability


logger = logging.getLogger(__name__)


@dataclass
class Intent:
    """
    意图数据结构

    遵循自我进化原则：
    - 不预置固定的字段定义
    - 从样本/交互中学习字段结构
    """
    raw_input: str
    task_type: str
    fields: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_missing_fields(self) -> List[str]:
        """
        获取缺失的必需字段

        学习型实现：从任务执行结果中学习哪些字段是必需的
        """
        # 基础必需字段（可以从学习中扩展）
        required_fields_map = {
            "query": ["query"],
            "search": ["query"],
            "task": ["task_description"],
            "dialogue": [],
        }

        required = required_fields_map.get(self.task_type, ["input"])
        missing = [f for f in required if f not in self.fields or not self.fields[f]]
        return missing

    def known_fields(self) -> Dict[str, Any]:
        """返回已知的字段"""
        return {k: v for k, v in self.fields.items() if v is not None and v != ""}

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "raw_input": self.raw_input,
            "task_type": self.task_type,
            "fields": self.fields,
            "confidence": self.confidence
        }


class IntentRecognizer:
    """
    意图识别器

    核心原则：
    ❌ 不预置固定的意图分类规则
    ✅ 使用 LLM 动态识别意图
    ✅ 从交互中学习任务类型和必需字段
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.router = GlobalModelRouter()
        self.storage_path = storage_path or Path.home() / ".livingtree" / "intent_patterns.json"
        self.learned_patterns: Dict[str, Dict[str, Any]] = {}
        self._load_patterns()

    def _load_patterns(self):
        """加载已学习的意图模式"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.learned_patterns = json.load(f)
                logger.info(f"✅ 已加载 {len(self.learned_patterns)} 个意图模式")
            except Exception as e:
                logger.warning(f"⚠️ 加载意图模式失败: {e}")

    def _save_patterns(self):
        """保存学习的意图模式"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.learned_patterns, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存意图模式失败: {e}")

    async def recognize(self, user_input: str) -> Intent:
        """
        识别用户意图

        流程：
        1. 使用 LLM 识别意图类型和字段
        2. 如果识别到已知模式，使用学习的模式
        3. 返回结构化的 Intent 对象
        """
        # 先尝试匹配已学习的模式
        matched_pattern = self._match_learned_pattern(user_input)
        if matched_pattern:
            logger.info(f"🎯 匹配到已学习模式: {matched_pattern['task_type']}")
            return self._apply_pattern(user_input, matched_pattern)

        # 使用 LLM 识别
        intent = await self._recognize_with_llm(user_input)

        # 学习新模式
        if intent.confidence > 0.7:
            self._learn_pattern(intent)
            self._save_patterns()

        return intent

    def _match_learned_pattern(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        匹配已学习的意图模式

        使用简单的关键词匹配（可以升级为语义匹配）
        """
        for pattern_key, pattern in self.learned_patterns.items():
            keywords = pattern.get("keywords", [])
            if any(kw in user_input for kw in keywords):
                return pattern
        return None

    def _apply_pattern(self, user_input: str, pattern: Dict[str, Any]) -> Intent:
        """应用匹配的模式提取字段"""
        # 使用 LLM 从输入中提取字段
        fields = self._extract_fields(user_input, pattern.get("field_names", []))

        return Intent(
            raw_input=user_input,
            task_type=pattern["task_type"],
            fields=fields,
            confidence=0.85  # 模式匹配的置信度较高
        )

    async def _recognize_with_llm(self, user_input: str) -> Intent:
        """使用 LLM 识别意图"""
        prompt = f"""
作为一个意图识别专家，分析以下用户输入，识别意图类型和提取相关字段。

用户输入: {user_input}

要求：
1. 判断任务类型（从以下选择或创建新的：query, search, task, dialogue）
2. 提取所有可识别的字段
3. 返回 JSON 格式

返回格式:
{{
    "task_type": "任务类型",
    "fields": {{
        "field1": "值1",
        "field2": "值2"
    }},
    "confidence": 0.9,
    "keywords": ["关键词1", "关键词2"]
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.1
            )

            result = json.loads(response)

            return Intent(
                raw_input=user_input,
                task_type=result.get("task_type", "dialogue"),
                fields=result.get("fields", {}),
                confidence=result.get("confidence", 0.5)
            )

        except Exception as e:
            logger.error(f"❌ LLM 意图识别失败: {e}")
            # 兜底：简单分类
            return self._fallback_recognize(user_input)

    def _extract_fields(self, user_input: str, field_names: List[str]) -> Dict[str, Any]:
        """从输入中提取指定字段（简化实现）"""
        # 这里可以调用 LLM 提取，但为简化先返回空
        return {}

    def _learn_pattern(self, intent: Intent):
        """学习新的意图模式"""
        pattern_key = f"{intent.task_type}_{len(self.learned_patterns)}"

        # 提取关键词（简化：使用输入的前几个词）
        words = intent.raw_input.split()[:3]

        self.learned_patterns[pattern_key] = {
            "task_type": intent.task_type,
            "keywords": words,
            "field_names": list(intent.fields.keys()),
            "usage_count": 1,
            "success_count": 0
        }

        logger.info(f"📝 学习新意图模式: {pattern_key}")

    def _fallback_recognize(self, user_input: str) -> Intent:
        """兜底意图识别（基于规则）"""
        # 简单规则分类
        if any(kw in user_input for kw in ["吗", "？", "?", "什么", "怎么"]):
            task_type = "query"
        elif any(kw in user_input for kw in ["搜索", "查找", "找", "search"]):
            task_type = "search"
        elif len(user_input) > 20:
            task_type = "task"
        else:
            task_type = "dialogue"

        return Intent(
            raw_input=user_input,
            task_type=task_type,
            fields={"input": user_input},
            confidence=0.4
        )

    def update_pattern_success(self, intent: Intent, success: bool):
        """更新模式成功率（从交互反馈中学习）"""
        for pattern_key, pattern in self.learned_patterns.items():
            if pattern["task_type"] == intent.task_type:
                pattern["usage_count"] = pattern.get("usage_count", 0) + 1
                if success:
                    pattern["success_count"] = pattern.get("success_count", 0) + 1
                self._save_patterns()
                break
