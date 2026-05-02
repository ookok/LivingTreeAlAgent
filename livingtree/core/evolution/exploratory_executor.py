# -*- coding: utf-8 -*-

"""
ExploratoryExecutor - 探索性执行引擎

在约束下探索多种解决方案，并行执行并选择最优。

核心思想：
    AI 不决定具体怎么做，而是定义"可能性边界"，
    Agent 在其中探索最优解。

用法：
    executor = ExploratoryExecutor()
    result = await executor.explore(
        goal="让网站加载更快",
        constraints=["不改变功能", "不增加服务器成本"],
        metrics=["load_time", "bundle_size"],
    )
    print(result.best_solution)
"""

import logging
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable

logger = logging.getLogger(__name__)


class CandidateStatus(Enum):
    """候选项状态"""
    PENDING = "pending"         # 待执行
    RUNNING = "running"         # 执行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    PRUNED = "pruned"          # 被剪枝（无希望）


@dataclass
class CandidateSolution:
    """候选解决方案"""
    id: str
    description: str
    actions: List[Dict[str, Any]]   # 要执行的动作列表
    estimated_score: float = 0.0    # 预估评分
    actual_score: float = 0.0       # 实际评分
    status: CandidateStatus = CandidateStatus.PENDING
    execution_time: float = 0.0
    output: Optional[str] = None
    error: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ExplorationResult:
    """探索结果"""
    success: bool
    best_solution: Optional[CandidateSolution] = None
    all_solutions: List[CandidateSolution] = field(default_factory=list)
    exploration_time: float = 0.0
    pruned_count: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "best_solution_id": self.best_solution.id if self.best_solution else None,
            "best_score": self.best_solution.actual_score if self.best_solution else 0.0,
            "all_scores": [
                {"id": s.id, "score": s.actual_score, "status": s.status.value}
                for s in self.all_solutions
            ],
            "exploration_time": round(self.exploration_time, 2),
            "pruned_count": self.pruned_count,
            "error": self.error,
        }


class ExploratoryExecutor:
    """探索性执行引擎

    在约束下探索解决方案空间，并行执行多个候选方案，
    实时比较结果，选择最优解。

    用法：
        executor = ExploratoryExecutor(project_root=".")
        result = await executor.explore(
            goal="优化网站加载速度",
            constraints=["不修改业务逻辑", "保持向后兼容"],
            metrics={"load_time": 0.6, "bundle_size": 0.4},
        )
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        max_candidates: int = 5,
        max_parallel: int = 3,
        timeout_per_candidate: float = 60.0,
    ):
        """
        Args:
            project_root: 项目根目录
            max_candidates: 最大候选方案数
            max_parallel: 最大并行执行数
            timeout_per_candidate: 每个候选方案的执行超时（秒）
        """
        self.project_root = project_root
        self.max_candidates = max_candidates
        self.max_parallel = max_parallel
        self.timeout_per_candidate = timeout_per_candidate

    async def explore(
        self,
        goal: str,
        constraints: Optional[List[str]] = None,
        metrics: Optional[Dict[str, float]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExplorationResult:
        """在约束下探索解决方案空间

        Args:
            goal: 目标描述（如"让网站加载更快"）
            constraints: 约束条件列表（如["不改变功能"]）
            metrics: 评估指标及权重（如{"load_time": 0.6, "bundle_size": 0.4}）
            context: 额外上下文（如当前性能数据）

        Returns:
            ExplorationResult: 探索结果（含最优解）
        """
        start_time = time.time()
        constraints = constraints or []
        metrics = metrics or {"score": 1.0}
        context = context or {}

        logger.info(f"[ExploratoryExecutor] 开始探索: {goal}")
        logger.info(f"[ExploratoryExecutor] 约束: {constraints}")
        logger.info(f"[ExploratoryExecutor] 指标: {metrics}")

        try:
            # 1. 生成候选方案
            candidates = await self._generate_candidates(goal, constraints, context)
            logger.info(f"[ExploratoryExecutor] 生成了 {len(candidates)} 个候选方案")

            if not candidates:
                return ExplorationResult(
                    success=False,
                    error="无法生成候选方案",
                )

            # 2. 预估并排序
            candidates = self._estimate_and_sort(candidates)
            candidates = candidates[:self.max_candidates]  # 只保留 top N

            # 3. 并行执行
            results = await self._execute_candidates(candidates)

            # 4. 评估并选择最优
            evaluated = self._evaluate_candidates(results, metrics)
            best = self._select_best(evaluated)

            exploration_time = time.time() - start_time
            pruned_count = sum(
                1 for c in candidates if c.status == CandidateStatus.PRUNED
            )

            logger.info(
                f"[ExploratoryExecutor] 探索完成: "
                f"最优评分={best.actual_score:.2f}, 耗时={exploration_time:.1f}s"
            )

            return ExplorationResult(
                success=best is not None,
                best_solution=best,
                all_solutions=results,
                exploration_time=exploration_time,
                pruned_count=pruned_count,
            )

        except Exception as e:
            logger.error(f"[ExploratoryExecutor] 探索失败: {e}")
            return ExplorationResult(
                success=False,
                error=str(e),
                exploration_time=time.time() - start_time,
            )

    async def _generate_candidates(
        self, goal: str, constraints: List[str], context: Dict[str, Any],
    ) -> List[CandidateSolution]:
        """生成候选方案（使用全局模型路由器）"""
        
        prompt = self._build_candidate_generation_prompt(goal, constraints, context)

        try:
            # 使用全局模型路由器（异步调用）
            from livingtree.core.model.router import get_global_router, ModelCapability
            router = get_global_router()
            
            response = await router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                system_prompt="你是一个探索性解决方案生成器。生成多个创新的候选方案。"
            )

            candidates = self._parse_candidates_response(response)
            return candidates

        except Exception as e:
            logger.error(f"[ExploratoryExecutor] 生成候选方案失败: {e}")
            # 降级：生成一些通用候选方案
            return self._generate_fallback_candidates(goal)

    def _build_candidate_generation_prompt(
        self, goal: str, constraints: List[str], context: Dict[str, Any],
    ) -> str:
        """构建候选方案生成提示词"""
        sections = [
            "你是一个解决方案探索助手。给定目标和约束，生成多个候选解决方案。",
            "",
            f"## 目标\n{goal}",
        ]

        if constraints:
            sections.append("")
            sections.append("## 约束条件")
            for i, c in enumerate(constraints, 1):
                sections.append(f"{i}. {c}")

        if context:
            sections.append("")
            sections.append("## 当前上下文")
            for key, value in context.items():
                val_str = str(value)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                sections.append(f"- {key}: {val_str}")

        sections.extend([
            "",
            "## 输出要求",
            f"请生成 {self.max_candidates} 个候选解决方案，以 JSON 格式输出：",
            "```json",
            "[",
            "  {",
            '    "id": "candidate_1",',
            '    "description": "方案描述",',
            '    "actions": [',
            '      {"action": "FILE_WRITE", "params": {...}},',
            "      ...",
            "    ],",
            '    "estimated_score": 0.8,  // 预估效果评分（0-1）',
            "  },",
            "  ...",
            "]",
            "```",
            "",
            "动作类型可选：FILE_READ, FILE_WRITE, CLI_EXECUTE, CODE_MODIFY, CONFIG_UPDATE",
        ])

        return "\n".join(sections)

    def _parse_candidates_response(self, response: str) -> List[CandidateSolution]:
        """解析 AI 生成的候选方案"""
        import json
        import re

        # 尝试提取 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return self._dicts_to_candidates(data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"[ExploratoryExecutor] JSON 解析失败: {e}")

        # 尝试直接解析
        try:
            data = json.loads(response)
            return self._dicts_to_candidates(data)
        except (json.JSONDecodeError, TypeError):
            pass

        logger.warning("[ExploratoryExecutor] 无法解析候选方案，使用降级方案")
        return []

    def _dicts_to_candidates(self, data: Any) -> List[CandidateSolution]:
        """将 dict 列表转换为 CandidateSolution 列表"""
        candidates = []
        for item in data:
            if not isinstance(item, dict):
                continue
            c = CandidateSolution(
                id=item.get("id", f"candidate_{len(candidates)+1}"),
                description=item.get("description", ""),
                actions=item.get("actions", []),
                estimated_score=float(item.get("estimated_score", 0.5)),
            )
            candidates.append(c)
        return candidates

    def _generate_fallback_candidates(self, goal: str) -> List[CandidateSolution]:
        """降级：生成通用候选方案"""
        return [
            CandidateSolution(
                id="fallback_1",
                description=f"分析现状并给出建议：{goal}",
                actions=[
                    {"action": "analysis", "params": {"goal": goal}},
                ],
                estimated_score=0.4,
            ),
        ]

    def _estimate_and_sort(self, candidates: List[CandidateSolution]) -> List[CandidateSolution]:
        """根据预估评分排序"""
        return sorted(candidates, key=lambda c: c.estimated_score, reverse=True)

    async def _execute_candidates(
        self, candidates: List[CandidateSolution],
    ) -> List[CandidateSolution]:
        """并行执行候选方案

        使用 semaphore 限制并行数。
        """
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def _execute_one(candidate: CandidateSolution) -> CandidateSolution:
            async with semaphore:
                candidate.status = CandidateStatus.RUNNING
                start = time.time()
                try:
                    result = await self._execute_single(candidate)
                    candidate.actual_score = result.get("score", 0.0)
                    candidate.output = result.get("output", "")
                    candidate.metrics = result.get("metrics", {})
                    candidate.status = CandidateStatus.COMPLETED
                except Exception as e:
                    candidate.error = str(e)
                    candidate.status = CandidateStatus.FAILED
                    logger.warning(
                        f"[ExploratoryExecutor] 候选 {candidate.id} 执行失败: {e}"
                    )
                finally:
                    candidate.execution_time = time.time() - start
                return candidate

        tasks = [_execute_one(c) for c in candidates]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _execute_single(self, candidate: CandidateSolution) -> Dict[str, Any]:
        """执行单个候选方案

        根据 actions 列表执行具体操作。
        这是一个简化实现，实际使用中可以对接现有的执行器。
        """
        # 模拟执行：实际使用时应该调用具体的执行器
        # 例如：对接 unified_task_executor 或 skill_executor

        total_score = 0.0
        metrics = {}

        for action in candidate.actions:
            action_type = action.get("action", "")
            params = action.get("params", {})

            # 简化执行：记录动作
            logger.debug(
                f"[ExploratoryExecutor] 执行动作: {action_type}, params={params}"
            )

            # 这里应该对接真实的执行器
            # 暂时返回模拟结果
            if action_type == "analysis":
                total_score += 0.3
                metrics["analysis_complete"] = 1.0
            elif action_type == "FILE_WRITE":
                total_score += 0.5
                metrics["files_written"] = metrics.get("files_written", 0) + 1
            elif action_type == "CLI_EXECUTE":
                total_score += 0.4
                metrics["commands_run"] = metrics.get("commands_run", 0) + 1

        return {
            "score": min(total_score, 1.0),
            "output": f"已执行 {len(candidate.actions)} 个动作",
            "metrics": metrics,
        }

    def _evaluate_candidates(
        self, candidates: List[CandidateSolution], metrics: Dict[str, float],
    ) -> List[CandidateSolution]:
        """根据指标评估候选方案"""
        for c in candidates:
            if c.status != CandidateStatus.COMPLETED:
                continue

            # 综合评分：结合实际评分和指标
            score = c.actual_score
            for metric, weight in metrics.items():
                metric_score = c.metrics.get(metric, 0.0)
                score += metric_score * weight * 0.5  # 指标占 50% 权重

            c.actual_score = min(score, 1.0)

        return candidates

    def _select_best(
        self, candidates: List[CandidateSolution],
    ) -> Optional[CandidateSolution]:
        """选择最优候选方案"""
        completed = [c for c in candidates if c.status == CandidateStatus.COMPLETED]
        if not completed:
            return None
        return max(completed, key=lambda c: c.actual_score)

    async def explore_with_ai_feedback(
        self,
        goal: str,
        constraints: Optional[List[str]] = None,
        metrics: Optional[Dict[str, float]] = None,
        max_iterations: int = 3,
    ) -> ExplorationResult:
        """带 AI 反馈的探索

        执行 → AI 评估 → 优化 → 再执行 → ...
        """
        best_overall = None

        for i in range(max_iterations):
            logger.info(f"[ExploratoryExecutor] AI反馈迭代 {i+1}/{max_iterations}")

            # 探索
            result = await self.explore(goal, constraints, metrics)

            if not result.success:
                break

            # 更新最佳结果
            if best_overall is None or (
                result.best_solution and
                result.best_solution.actual_score > best_overall.actual_score
            ):
                best_overall = result.best_solution

            # AI 评估并给出优化建议
            if result.best_solution:
                feedback = await self._get_ai_feedback(result, goal, constraints)
                if feedback.get("should_stop"):
                    logger.info("[ExploratoryExecutor] AI 建议停止探索")
                    break

                # 将反馈融入下一轮探索
                goal = f"{goal}\n\n优化建议：{feedback.get('suggestion', '')}"

        return ExplorationResult(
            success=best_overall is not None,
            best_solution=best_overall,
            all_solutions=[best_overall] if best_overall else [],
        )

    async def _get_ai_feedback(
        self, result: ExplorationResult, goal: str, constraints: Optional[List[str]],
    ) -> Dict[str, Any]:
        """获取 AI 对探索结果的反馈（使用全局模型路由器）"""
        
        if not result.best_solution:
            return {"should_stop": True}

        prompt = f"""
        你是一个方案评估专家。请评估以下探索结果，并给出是否需要继续探索的建议。

        ## 目标
        {goal}

        ## 最佳方案
        {result.best_solution.description}
        评分：{result.best_solution.actual_score:.2f}

        ## 所有方案评分
        {', '.join(f"{s.id}: {s.actual_score:.2f}" for s in result.all_solutions if s.status == "completed")}

        请以 JSON 格式输出：
        ```json
        {{
            "should_stop": true/false,
            "reason": "原因",
            "suggestion": "优化建议（如果需要继续）"
        }}
        ```
        """

        try:
            # 使用全局模型路由器（异步调用）
            from livingtree.core.model.router import get_global_router, ModelCapability
            router = get_global_router()
            
            response = await router.call_model(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                system_prompt="你是一个方案评估专家。"
            )
            
            return self._parse_feedback_response(response)
        except Exception as e:
            logger.error(f"[ExploratoryExecutor] 获取 AI 反馈失败: {e}")
            return {"should_stop": True}

    def _parse_feedback_response(self, response: str) -> Dict[str, Any]:
        """解析 AI 反馈响应"""
        import json
        import re

        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        return {"should_stop": True, "reason": "无法解析 AI 反馈"}
