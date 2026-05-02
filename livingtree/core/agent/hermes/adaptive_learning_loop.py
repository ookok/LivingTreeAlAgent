"""
自适应学习循环 (Adaptive Learning Loop)
遵循自我进化原则：从反馈中学习最优策略，而非预置规则

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.4.1)

核心借鉴: DeepTutor (匹配度70%)
- 从反馈中学习最优策略
- 评估结果质量
- 生成变体测试
- 更新策略
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
from enum import Enum

from business.global_model_router import GlobalModelRouter, ModelCapability
from business.hermes_agent.intent_recognizer import Intent


logger = logging.getLogger(__name__)


class LearningMode(Enum):
    """学习模式"""
    SUPERVISED = "supervised"      # 有监督学习（有标签）
    REINFORCEMENT = "reinforcement"  # 强化学习（奖励信号）
    UNSUPERVISED = "unsupervised"   # 无监督学习（模式发现）


@dataclass
class LearningSample:
    """学习样本"""
    task: str
    result: Any
    quality_score: float
    feedback: Optional[Dict[str, Any]] = None
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """策略 - 从学习中优化"""
    name: str
    action_space: List[str]
    success_rate: float = 0.0
    total_trials: int = 0
    successful_trials: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""

    def update(self, success: bool):
        """更新策略"""
        self.total_trials += 1
        if success:
            self.successful_trials += 1
        self.success_rate = self.successful_trials / self.total_trials


class AdaptiveLearningLoop:
    """
    自适应学习循环

    核心原则：
    ❌ 不预置固定的学习规则
    ✅ 从任务执行结果中学习
    ✅ 评估结果质量
    ✅ 生成变体测试
    ✅ 动态更新策略

    学习循环：
    执行任务 → 评估结果 → 记录样本 → 生成变体 → 测试变体 → 更新策略
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.router = GlobalModelRouter()
        self.storage_path = storage_path or Path.home() / ".livingtree" / "adaptive_learning.json"
        self.policies: Dict[str, Policy] = {}
        self.learning_history: List[LearningSample] = []
        self.variants_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._load_learning_data()

    def _load_learning_data(self):
        """加载学习数据"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for policy_name, policy_data in data.get("policies", {}).items():
                        self.policies[policy_name] = Policy(**policy_data)
                    self.learning_history = [
                        LearningSample(**s) for s in data.get("history", [])
                    ]
                logger.info(f"✅ 已加载 {len(self.policies)} 个策略，{len(self.learning_history)} 个学习样本")
            except Exception as e:
                logger.warning(f"⚠️ 加载学习数据失败: {e}")

    def _save_learning_data(self):
        """保存学习数据"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "policies": {
                    name: {
                        "name": p.name,
                        "action_space": p.action_space,
                        "success_rate": p.success_rate,
                        "total_trials": p.total_trials,
                        "successful_trials": p.successful_trials,
                        "parameters": p.parameters,
                        "updated_at": p.updated_at
                    }
                    for name, p in self.policies.items()
                },
                "history": [
                    {
                        "task": s.task,
                        "result": str(s.result),
                        "quality_score": s.quality_score,
                        "feedback": s.feedback,
                        "timestamp": s.timestamp
                    }
                    for s in self.learning_history[-500:]  # 只保留最近500条
                ]
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存学习数据失败: {e}")

    async def learn(self, task: str, result: Any, feedback: Optional[Dict[str, Any]] = None):
        """
        从任务执行中学习

        流程：
        1. 评估结果质量
        2. 记录学习样本
        3. 如果质量低，生成变体
        4. 更新策略
        """
        logger.info(f"📚 开始学习: {task[:50]}...")

        # 1. 评估结果质量
        quality_score = await self._evaluate_quality(task, result, feedback)

        # 2. 记录学习样本
        sample = LearningSample(
            task=task,
            result=result,
            quality_score=quality_score,
            feedback=feedback,
            timestamp=self._get_timestamp()
        )
        self.learning_history.append(sample)

        # 3. 如果质量低，生成变体
        if quality_score < 0.6:
            logger.info(f"🔄 质量分数低 ({quality_score:.2f})，生成变体...")
            variants = await self._generate_variants(task, result, quality_score)
            await self._test_variants(task, variants)

        # 4. 更新策略
        await self._update_policy(task, quality_score)

        self._save_learning_data()
        logger.info(f"✅ 学习完成: 质量分数 {quality_score:.2f}")

        return quality_score

    async def _evaluate_quality(self, task: str, result: Any, feedback: Optional[Dict[str, Any]]) -> float:
        """
        评估结果质量

        学习型实现：
        - 如果有用户反馈，优先使用反馈
        - 否则使用LLM评估
        - 从评估中学习评估标准
        """
        # 如果有用户反馈，直接使用
        if feedback and "rating" in feedback:
            logger.info(f"📝 使用用户反馈评估")
            return feedback["rating"]

        # 使用LLM评估
        logger.info(f"🤖 使用LLM评估质量...")
        prompt = f"""
作为一个质量评估专家，评估以下任务执行结果的质量。

任务: {task}
结果: {str(result)[:500]}

评估标准：
1. 完整性（是否完成了所有要求）
2. 准确性（结果是否正确）
3. 效率（是否高效完成）

要求：
返回 JSON 格式: {{"quality_score": 0.8, "reason": "评估理由"}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.1
            )
            result_json = json.loads(response)
            quality_score = result_json.get("quality_score", 0.5)
            logger.info(f"📊 质量评估: {quality_score:.2f} - {result_json.get('reason', '')}")
            return quality_score
        except Exception as e:
            logger.error(f"❌ 质量评估失败: {e}")
            return 0.5  # 默认中等质量

    async def _generate_variants(self, task: str, result: Any, quality_score: float) -> List[Dict[str, Any]]:
        """
        生成变体

        学习型实现：
        - 分析低质量原因
        - 生成改进变体
        - 从历史事件中学习有效的变体模式
        """
        logger.info(f"🧪 生成改进变体...")

        # 检查缓存
        cache_key = f"{task[:50]}_{quality_score:.1f}"
        if cache_key in self.variants_cache:
            logger.info(f"♻️ 使用缓存的变体")
            return self.variants_cache[cache_key]

        prompt = f"""
作为一个改进策略专家，分析以下低质量结果，生成改进变体。

任务: {task}
结果: {str(result)[:500]}
质量分数: {quality_score}

要求：
1. 分析低质量的原因
2. 生成 3-5 个改进变体
3. 每个变体说明改进点
4. 返回 JSON 格式

返回格式:
{{
    "analysis": "低质量原因分析",
    "variants": [
        {{"name": "变体1", "improvement": "改进点", "strategy": "改进策略"}},
        ...
    ]
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )
            result_json = json.loads(response)
            variants = result_json.get("variants", [])

            # 缓存变体
            self.variants_cache[cache_key] = variants

            logger.info(f"✅ 生成了 {len(variants)} 个变体")
            return variants
        except Exception as e:
            logger.error(f"❌ 生成变体失败: {e}")
            return []

    async def _test_variants(self, task: str, variants: List[Dict[str, Any]]):
        """
        测试变体

        学习型实现：
        - 模拟执行变体
        - 评估变体质量
        - 记录测试结果
        """
        logger.info(f"🧪 测试 {len(variants)} 个变体...")

        for variant in variants:
            # 模拟执行（实际应该调用相应的执行器）
            logger.info(f"  🧪 测试变体: {variant.get('name', 'unknown')}")

            # 这里应该实际执行变体并评估
            # 为简化，我们使用LLM模拟评估
            simulated_result = f"模拟执行变体: {variant.get('name', '')}"
            simulated_quality = await self._evaluate_quality(task, simulated_result, None)

            logger.info(f"    质量分数: {simulated_quality:.2f}")

            # 如果变体质量高，记录为成功模式
            if simulated_quality > 0.8:
                logger.info(f"  ✅ 发现高质量变体!")

    async def _update_policy(self, task: str, quality_score: float):
        """
        更新策略

        学习型实现：
        - 识别任务类型
        - 更新对应策略的成功率
        - 动态调整参数
        """
        # 识别任务类型（简化：使用关键词）
        task_type = self._identify_task_type(task)

        if task_type not in self.policies:
            # 新策略
            self.policies[task_type] = Policy(
                name=task_type,
                action_space=self._get_action_space(task_type),
                updated_at=self._get_timestamp()
            )

        policy = self.policies[task_type]
        success = quality_score > 0.6
        policy.update(success)

        logger.info(f"📈 策略更新: {task_type} 成功率 {policy.success_rate:.2f} ({policy.successful_trials}/{policy.total_trials})")

    def _identify_task_type(self, task: str) -> str:
        """识别任务类型"""
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["搜索", "查找", "search"]):
            return "search"
        elif any(kw in task_lower for kw in ["生成", "创建", "create", "generate"]):
            return "generation"
        elif any(kw in task_lower for kw in ["分析", "评估", "analyze"]):
            return "analysis"
        else:
            return "general"

    def _get_action_space(self, task_type: str) -> List[str]:
        """获取动作空间"""
        # 简化：返回预定义动作（实际应该从学习中扩展）
        action_spaces = {
            "search": ["keyword_extraction", "query_expansion", "result_ranking"],
            "generation": ["outline_creation", "content_expansion", "style_adjustment"],
            "analysis": ["data_extraction", "pattern_recognition", "conclusion_generation"],
            "general": ["task_decomposition", "tool_selection", "result_synthesis"]
        }
        return action_spaces.get(task_type, action_spaces["general"])

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    async def get_learning_stats(self) -> Dict[str, Any]:
        """获取学习统计"""
        if not self.policies:
            return {"total_policies": 0}

        total_trials = sum(p.total_trials for p in self.policies.values())
        avg_success_rate = sum(p.success_rate for p in self.policies.values()) / len(self.policies)

        return {
            "total_policies": len(self.policies),
            "total_trials": total_trials,
            "average_success_rate": round(avg_success_rate, 2),
            "total_learning_samples": len(self.learning_history),
            "policies": [
                {
                    "name": p.name,
                    "success_rate": round(p.success_rate, 2),
                    "total_trials": p.total_trials
                }
                for p in sorted(self.policies.values(), key=lambda x: x.success_rate, reverse=True)
            ]
        }

    async def reset_policy(self, policy_name: str) -> bool:
        """重置策略"""
        if policy_name in self.policies:
            del self.policies[policy_name]
            self._save_learning_data()
            logger.info(f"🗑️ 已重置策略: {policy_name}")
            return True
        return False
