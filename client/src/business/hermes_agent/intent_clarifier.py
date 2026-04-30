"""
自适应意图澄清器 (Adaptive Clarifier)
遵循自我进化原则：从交互中学习澄清策略，而非硬编码问题列表

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.4)
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging

from business.global_model_router import GlobalModelRouter, ModelCapability
from business.hermes_agent.intent_recognizer import Intent, IntentRecognizer


logger = logging.getLogger(__name__)


@dataclass
class ClarificationStrategy:
    """澄清策略 - 从交互中学习"""
    field_name: str
    question_template: str
    success_rate: float = 0.0
    usage_count: int = 0
    last_updated: str = ""

    def update_success(self, success: bool):
        """更新成功率"""
        self.usage_count += 1
        if success:
            self.success_rate = (self.success_rate * (self.usage_count - 1) + 1.0) / self.usage_count
        else:
            self.success_rate = (self.success_rate * (self.usage_count - 1)) / self.usage_count


@dataclass
class ClarificationResult:
    """澄清结果"""
    clarified_intent: Intent
    missing_fields: List[str]
    clarification_history: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class AdaptiveClarifier:
    """
    自适应意图澄清器

    核心原则：
    ❌ 不预置固定的澄清问题列表
    ✅ 从交互中学习任务特定的澄清策略
    ✅ 动态优化澄清问题的表达方式
    ✅ 记录澄清成功率，持续优化
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.router = GlobalModelRouter()
        self.recognizer = IntentRecognizer()
        self.storage_path = storage_path or Path.home() / ".livingtree" / "clarifier_strategies.json"
        self.learned_strategies: Dict[str, ClarificationStrategy] = {}
        self.clarification_history: List[Dict[str, Any]] = []
        self._load_strategies()

    def _load_strategies(self):
        """加载已学习的澄清策略"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for field, strategy_data in data.get("strategies", {}).items():
                        self.learned_strategies[field] = ClarificationStrategy(**strategy_data)
                    self.clarification_history = data.get("history", [])
                logger.info(f"✅ 已加载 {len(self.learned_strategies)} 个澄清策略")
            except Exception as e:
                logger.warning(f"⚠️ 加载澄清策略失败: {e}")

    def _save_strategies(self):
        """保存学习的澄清策略"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "strategies": {
                    field: {
                        "field_name": s.field_name,
                        "question_template": s.question_template,
                        "success_rate": s.success_rate,
                        "usage_count": s.usage_count,
                        "last_updated": s.last_updated
                    }
                    for field, s in self.learned_strategies.items()
                },
                "history": self.clarification_history[-100:]  # 只保留最近100条
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存澄清策略失败: {e}")

    async def clarify(self, intent: Intent) -> str:
        """
        自适应澄清入口

        流程：
        1. 分析缺失信息
        2. 获取/学习最佳澄清策略
        3. 生成自然语言澄清问题
        """
        missing_fields = intent.get_missing_fields()

        if not missing_fields:
            return ""

        # 对每个缺失字段生成澄清问题
        questions = []
        for field in missing_fields:
            strategy = await self._get_or_learn_strategy(intent, field)
            question = await self._generate_clarification(intent, field, strategy)
            questions.append(question)

        # 合并为自然的对话式澄清
        combined = await self._combine_questions(intent, questions)
        return combined

    async def _get_or_learn_strategy(self, intent: Intent, field: str) -> ClarificationStrategy:
        """
        获取或学习澄清策略

        如果已学习过，返回成功率最高的策略
        如果未学习，调用LLM生成初始策略
        """
        # 生成策略键：任务类型 + 缺失字段
        strategy_key = f"{intent.task_type}:{field}"

        if strategy_key in self.learned_strategies:
            strategy = self.learned_strategies[strategy_key]
            logger.info(f"🧠 使用已学习策略: {strategy_key} (成功率: {strategy.success_rate:.2%})")
            return strategy

        # 未学习过，生成初始策略
        logger.info(f"🎓 学习新澄清策略: {strategy_key}")
        strategy = await self._learn_initial_strategy(intent, field)
        self.learned_strategies[strategy_key] = strategy
        self._save_strategies()
        return strategy

    async def _learn_initial_strategy(self, intent: Intent, field: str) -> ClarificationStrategy:
        """使用LLM学习初始澄清策略"""
        prompt = f"""
作为一个意图澄清专家，你需要为以下场景生成澄清问题模板。

任务类型: {intent.task_type}
用户原始输入: {intent.raw_input}
缺失字段: {field}
已知信息: {json.dumps(intent.known_fields(), ensure_ascii=False)}

要求：
1. 生成自然、友好的澄清问题（不要生硬地列出字段）
2. 问题应该引导用户提供缺失的信息
3. 可以根据已知信息推断出合理的默认值并询问确认
4. 返回JSON格式: {{"question_template": "问题模板", "reason": "为什么这样问"}}

示例：
输入: "帮我查一下北京天气"
缺失: 日期
输出: {{"question_template": "好的，你想查北京哪一天的天气呢？今天还是明天？", "reason": "天气查询需要明确日期，提供今天/明天选项降低用户认知负担"}}

只返回JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )

            # 解析响应
            result = json.loads(response)
            strategy = ClarificationStrategy(
                field_name=field,
                question_template=result["question_template"],
                success_rate=0.5,  # 初始成功率
                usage_count=0
            )
            return strategy

        except Exception as e:
            logger.error(f"❌ 学习策略失败: {e}")
            # 返回兜底策略
            return ClarificationStrategy(
                field_name=field,
                question_template=f"请问{field}是什么？",
                success_rate=0.3,
                usage_count=0
            )

    async def _generate_clarification(self, intent: Intent, field: str, strategy: ClarificationStrategy) -> str:
        """根据策略生成具体的澄清问题"""
        # 直接返回学习到的问题模板（可以根据已知信息动态替换）
        question = strategy.question_template

        # 简单变量替换（可以扩展为更复杂的模板引擎）
        if "{field}" in question:
            question = question.replace("{field}", field)

        return question

    async def _combine_questions(self, intent: Intent, questions: List[str]) -> str:
        """将多个问题合并为自然的对话"""
        if len(questions) == 1:
            return questions[0]

        # 使用LLM自然合并
        prompt = f"""
请将以下多个澄清问题合并为一个自然、流畅的对话式提问。

问题列表:
{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(questions))}

要求：
1. 保持友好、自然的语气
2. 可以按逻辑分组提问
3. 不要生硬地罗列
4. 返回合并后的提问文本

只返回合并后的文本，不要有其他内容。
"""

        try:
            combined = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )
            return combined
        except Exception:
            # 兜底：简单拼接
            return "、".join(questions[:-1]) + f"还有{questions[-1]}" if len(questions) > 1 else questions[0]

    async def learn_from_interaction(self, interaction: Dict[str, Any]):
        """
        从交互中学习，优化澄清策略

        交互格式:
        {
            "intent": Intent,
            "clarification": str,
            "user_response": str,
            "success": bool,  # 是否成功获取了缺失信息
            "task_completed": bool  # 任务是否最终完成
        }
        """
        intent = interaction["intent"]
        missing_fields = intent.get_missing_fields()

        for field in missing_fields:
            strategy_key = f"{intent.task_type}:{field}"
            if strategy_key in self.learned_strategies:
                strategy = self.learned_strategies[strategy_key]
                success = interaction.get("success", False)
                strategy.update_success(success)

                # 如果成功率低，重新学习策略
                if strategy.success_rate < 0.4 and strategy.usage_count >= 3:
                    logger.info(f"🔄 重新学习策略: {strategy_key} (当前成功率: {strategy.success_rate:.2%})")
                    new_strategy = await self._learn_initial_strategy(intent, field)
                    self.learned_strategies[strategy_key] = new_strategy

        # 记录交互历史
        self.clarification_history.append({
            "timestamp": interaction.get("timestamp", ""),
            "task_type": intent.task_type,
            "missing_fields": missing_fields,
            "success": interaction.get("success", False),
            "task_completed": interaction.get("task_completed", False)
        })

        self._save_strategies()
        logger.info(f"📝 已更新澄清策略，历史记录: {len(self.clarification_history)} 条")

    def get_strategy_stats(self) -> Dict[str, Any]:
        """获取策略统计信息"""
        if not self.learned_strategies:
            return {"total_strategies": 0}

        success_rates = [s.success_rate for s in self.learned_strategies.values()]
        return {
            "total_strategies": len(self.learned_strategies),
            "average_success_rate": sum(success_rates) / len(success_rates),
            "total_interactions": len(self.clarification_history),
            "strategies": [
                {
                    "field": s.field_name,
                    "success_rate": f"{s.success_rate:.2%}",
                    "usage_count": s.usage_count
                }
                for s in sorted(self.learned_strategies.values(), key=lambda x: x.success_rate, reverse=True)
            ]
        }
