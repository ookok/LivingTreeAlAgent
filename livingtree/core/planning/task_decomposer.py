"""
任务分解与链式思考系统（增强版 - 集成 CrewAI Process 模式）

通过结构化拆解任务并串联子任务，引导小模型逐步推理。

支持三种 Process 类型：
1. Sequential Process - 顺序执行
2. Hierarchical Process - 层级执行（Manager Agent 协调）
3. Parallel Process - 并行执行（异步任务）
"""

import concurrent.futures
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ProcessType(Enum):
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"
    PARALLEL = "parallel"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    step_id: str
    title: str
    description: str
    instruction: str
    input_data: Any = None
    output_data: Any = None
    status: StepStatus = StepStatus.PENDING
    error: Optional[str] = None
    confidence: float = 0.0
    depends_on: List[str] = field(default_factory=list)
    async_execution: bool = False

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "confidence": self.confidence,
            "error": self.error,
            "has_output": self.output_data is not None,
            "async_execution": self.async_execution,
        }


@dataclass
class DecomposedTask:
    task_id: str
    original_question: str
    steps: List[TaskStep]
    metadata: Dict[str, Any] = field(default_factory=dict)
    process_type: ProcessType = ProcessType.SEQUENTIAL

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)

    @property
    def progress(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.completed_steps / self.total_steps

    def get_step(self, step_id: str) -> Optional[TaskStep]:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def can_execute_step(self, step_id: str) -> bool:
        step = self.get_step(step_id)
        if not step or step.status != StepStatus.PENDING:
            return False
        for dep_id in step.depends_on:
            dep = self.get_step(dep_id)
            if not dep or dep.status != StepStatus.COMPLETED:
                return False
        return True

    def get_next_executable_step(self) -> Optional[TaskStep]:
        for step in self.steps:
            if self.can_execute_step(step.step_id):
                return step
        return None

    def get_parallel_steps(self) -> List[TaskStep]:
        parallel_steps = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            if all(
                self.get_step(dep_id).status == StepStatus.COMPLETED
                for dep_id in step.depends_on
            ):
                parallel_steps.append(step)
        return parallel_steps


class TaskDecomposer:
    """任务分解器 — CoT 引导的多层分解"""

    DECOMPOSITION_TEMPLATES = {
        "analysis": {
            "name": "分析类任务", "max_steps": 4,
            "process_type": ProcessType.SEQUENTIAL,
            "steps": [
                {"id": "context", "title": "理解背景", "desc": "提取问题中的关键信息和背景条件",
                 "prompt": "请分析以下问题的背景信息，提取关键要素：\n{question}\n\n用简洁的要点列出：1. 主要问题 2. 约束条件 3. 相关因素"},
                {"id": "data_collection", "title": "收集数据", "desc": "整理问题相关的数据和事实",
                 "prompt": "基于上述分析，列出解决问题所需的数据点：\n{context}\n\n列出3-5个关键数据点"},
                {"id": "analysis", "title": "深入分析", "desc": "基于数据进行分析推理",
                 "prompt": "根据收集的数据进行分析：\n{data}\n\n使用因果链条或对比分析的方式，给出核心发现（不超过3点）"},
                {"id": "conclusion", "title": "得出结论", "desc": "综合分析给出最终答案",
                 "prompt": "综合以上分析，给出结论和建议：\n{analysis}\n\n结论应直接回应原问题：{original_question}"},
            ],
        },
        "design": {
            "name": "设计类任务", "max_steps": 5,
            "process_type": ProcessType.HIERARCHICAL,
            "steps": [
                {"id": "requirement", "title": "明确需求", "desc": "理解用户需求和约束条件",
                 "prompt": "分析设计需求：\n{question}\n\n列出：1. 核心目标 2. 功能需求 3. 非功能需求"},
                {"id": "research", "title": "方案调研", "desc": "调研可行方案和技术选型",
                 "prompt": "针对需求：\n{requirements}\n\n列出2-3种可行方案，简述各方案的技术特点、优缺点",
                 "async_execution": True},
                {"id": "architecture", "title": "架构设计", "desc": "设计整体架构",
                 "prompt": "基于需求和方案：\n{requirements}\n{research}\n\n用结构化方式描述架构，包括模块划分和数据流"},
                {"id": "detail", "title": "详细设计", "desc": "关键模块的详细设计",
                 "prompt": "针对关键模块：\n{architecture}\n\n给出具体的实现细节",
                 "async_execution": True},
                {"id": "implementation", "title": "实施计划", "desc": "制定实施步骤和时间线",
                 "prompt": "基于设计：\n{detail}\n\n列出实施步骤（不超过5步）和每步的预期产出"},
            ],
        },
        "writing": {
            "name": "写作类任务", "max_steps": 4,
            "process_type": ProcessType.SEQUENTIAL,
            "steps": [
                {"id": "outline", "title": "确定大纲",
                 "prompt": "为以下主题确定文章大纲：\n{question}\n\n列出：1. 文章类型 2. 核心论点 3. 章节结构（3-5章）"},
                {"id": "research", "title": "收集素材",
                 "prompt": "基于大纲：\n{outline}\n\n列出需要引用的关键资料、数据或案例（3-5个）"},
                {"id": "drafting", "title": "撰写正文",
                 "prompt": "基于大纲和素材：\n{outline}\n{materials}\n\n撰写完整的文章内容"},
                {"id": "polish", "title": "润色完善",
                 "prompt": "检查并润色以下文章：\n{content}\n\n优化：1. 逻辑连贯性 2. 语言表达 3. 格式规范"},
            ],
        },
        "decision": {
            "name": "决策类任务", "max_steps": 5,
            "process_type": ProcessType.HIERARCHICAL,
            "steps": [
                {"id": "problem", "title": "界定问题",
                 "prompt": "界定决策问题：\n{question}\n\n明确：1. 决策目标 2. 决策范围 3. 成功标准"},
                {"id": "options", "title": "列出选项",
                 "prompt": "针对问题：\n{problem}\n\n列出3-4个可行的解决方案选项"},
                {"id": "criteria", "title": "确定标准",
                 "prompt": "基于问题：\n{problem}\n\n确定评估选项的标准（如成本、风险、收益、可执行性），并说明权重"},
                {"id": "evaluate", "title": "评估选项",
                 "prompt": "使用以下标准评估选项：\n{criteria}\n\n对每个选项按标准打分（1-10分）",
                 "async_execution": True},
                {"id": "recommend", "title": "给出建议",
                 "prompt": "基于评估结果：\n{evaluation}\n\n给出推荐方案及理由"},
            ],
        },
        "general": {
            "name": "通用任务", "max_steps": 3,
            "process_type": ProcessType.SEQUENTIAL,
            "steps": [
                {"id": "understand", "title": "理解问题",
                 "prompt": "分析以下问题：\n{question}\n\n用一句话概括核心问题，并列出2-3个相关要点"},
                {"id": "reason", "title": "推理分析",
                 "prompt": "基于对问题的理解：\n{understanding}\n\n进行逐步推理，每步说明理由"},
                {"id": "verify", "title": "验证结果",
                 "prompt": "验证以下回答：\n{answer}\n\n检查：1. 是否完整回答了问题 2. 是否有遗漏"},
            ],
        },
        "architecture": {
            "name": "架构设计任务", "max_steps": 5,
            "process_type": ProcessType.HIERARCHICAL,
            "steps": [
                {"id": "requirements", "title": "需求分析",
                 "prompt": "分析以下架构设计需求：\n{question}\n\n详细列出：1. 核心目标 2. 功能需求清单 3. 非功能需求"},
                {"id": "system_architecture", "title": "系统架构设计",
                 "prompt": "基于需求分析：\n{requirements}\n\n输出系统架构图描述，包括分层架构、核心模块划分",
                 "async_execution": True},
                {"id": "service_split", "title": "服务拆分清单",
                 "prompt": "基于架构设计：\n{system_architecture}\n\n列出服务拆分清单",
                 "async_execution": True},
                {"id": "tech_selection", "title": "核心技术选型",
                 "prompt": "基于服务拆分：\n{service_split}\n\n给出技术选型方案"},
                {"id": "implementation", "title": "实施计划与风险",
                 "prompt": "综合以上分析：\n{tech_selection}\n\n输出实施计划"},
            ],
        },
        "refactoring": {
            "name": "代码重构任务", "max_steps": 4,
            "process_type": ProcessType.SEQUENTIAL,
            "steps": [
                {"id": "analysis", "title": "代码分析",
                 "prompt": "分析以下代码或描述：\n{question}\n\n输出分析结果：代码结构、复杂度、重复代码识别"},
                {"id": "decomposition", "title": "逻辑拆解",
                 "prompt": "基于代码分析：\n{analysis}\n\n进行逻辑拆解：拆分为独立函数/模块"},
                {"id": "decoupling", "title": "依赖解耦",
                 "prompt": "基于逻辑拆解：\n{decomposition}\n\n进行依赖解耦：引入依赖注入"},
                {"id": "optimization", "title": "分层优化",
                 "prompt": "基于依赖解耦：\n{decoupling}\n\n按控制器-服务-数据层重新组织"},
            ],
        },
        "task_split": {
            "name": "任务拆解任务", "max_steps": 5,
            "process_type": ProcessType.HIERARCHICAL,
            "steps": [
                {"id": "phase_decompose", "title": "分阶段拆解",
                 "prompt": "分析以下任务：\n{question}\n\n进行分阶段拆解"},
                {"id": "priority", "title": "优先级排序",
                 "prompt": "基于阶段拆解：\n{phase_decompose}\n\n进行优先级排序",
                 "async_execution": True},
                {"id": "dependencies", "title": "依赖关系梳理",
                 "prompt": "基于阶段拆解：\n{phase_decompose}\n\n梳理依赖关系",
                 "async_execution": True},
                {"id": "risk", "title": "风险识别",
                 "prompt": "基于任务清单：\n{priority}\n\n识别风险"},
                {"id": "task_list", "title": "生成任务清单",
                 "prompt": "综合以上分析：\n{dependencies}\n{risk}\n\n输出可执行任务清单"},
            ],
        },
    }

    def __init__(self, default_process_type: ProcessType = ProcessType.SEQUENTIAL):
        self.templates = self.DECOMPOSITION_TEMPLATES
        self.default_process_type = default_process_type

    def detect_task_type(self, question: str) -> str:
        question_lower = question.lower()

        architecture_keywords = ["架构设计", "系统规划", "微服务", "高可用", "并发", "架构师"]
        if any(k in question_lower for k in architecture_keywords):
            return "architecture"

        task_split_keywords = ["任务分解", "任务规划", "分解任务", "任务清单", "拆解任务"]
        if any(k in question_lower for k in task_split_keywords):
            return "task_split"

        refactoring_keywords = ["重构", "优化", "拆解", "解耦", "重构代码", "代码优化"]
        if any(k in question_lower for k in refactoring_keywords):
            return "refactoring"

        analysis_keywords = ["分析", "评估", "比较", "对比", "预测", "研究", "检查"]
        if any(k in question_lower for k in analysis_keywords):
            return "analysis"

        design_keywords = ["设计", "方案", "架构", "构建", "规划", "策划"]
        if any(k in question_lower for k in design_keywords):
            return "design"

        writing_keywords = ["写", "创作", "文章", "报告", "论文", "总结", "说明"]
        if any(k in question_lower for k in writing_keywords):
            return "writing"

        decision_keywords = ["选择", "决策", "建议", "推荐", "哪个好", "怎么办"]
        if any(k in question_lower for k in decision_keywords):
            return "decision"

        return "general"

    def decompose(
        self, question: str, task_type: str = None,
        max_steps: int = 5, custom_steps: List[Dict] = None,
        process_type: ProcessType = None
    ) -> DecomposedTask:
        if task_type is None:
            task_type = self.detect_task_type(question)

        task_id = f"task_{uuid.uuid4().hex[:8]}"

        if custom_steps:
            steps_config = custom_steps
            process_type = process_type or self.default_process_type
        else:
            template = self.templates.get(task_type, self.templates["general"])
            steps_config = template["steps"][:max_steps]
            process_type = process_type or template.get("process_type", self.default_process_type)

        steps = []
        prev_step_id = None

        for i, config in enumerate(steps_config):
            step_id = config.get("id", f"step_{i+1}")
            instruction = self._build_instruction(config.get("prompt", ""), question)

            step = TaskStep(
                step_id=step_id,
                title=config.get("title", ""),
                description=config.get("desc", ""),
                instruction=instruction,
                depends_on=[prev_step_id] if prev_step_id else [],
                async_execution=config.get("async_execution", False),
            )
            steps.append(step)
            prev_step_id = step_id

        return DecomposedTask(
            task_id=task_id,
            original_question=question,
            steps=steps,
            metadata={"task_type": task_type, "process_type": process_type.value},
            process_type=process_type,
        )

    def _build_instruction(self, template: str, question: str) -> str:
        return template.replace("{question}", question)


class ChainOfThoughtExecutor:
    """链式思考执行器 — 支持三种 Process 模式"""

    def __init__(
        self,
        llm_callable: Callable[[str], str] = None,
        progress_callback: Callable[[TaskStep, int, int], None] = None,
        process_type: ProcessType = ProcessType.SEQUENTIAL,
        manager_llm: Callable[[str], str] = None,
    ):
        self.llm_callable = llm_callable or self._default_llm_call
        self.progress_callback = progress_callback
        self.process_type = process_type
        self.manager_llm = manager_llm

    def execute(
        self, task: DecomposedTask,
        process_type: ProcessType = None
    ) -> DecomposedTask:
        process_type = process_type or task.process_type

        if process_type == ProcessType.SEQUENTIAL:
            return self._execute_sequential(task)
        elif process_type == ProcessType.HIERARCHICAL:
            return self._execute_hierarchical(task)
        elif process_type == ProcessType.PARALLEL:
            return self._execute_parallel(task)
        else:
            raise ValueError(f"Unknown process type: {process_type}")

    def _execute_sequential(self, task: DecomposedTask) -> DecomposedTask:
        if self.progress_callback:
            self.progress_callback(None, 0, task.total_steps)

        for i, step in enumerate(task.steps):
            if not task.can_execute_step(step.step_id):
                step.status = StepStatus.SKIPPED
                continue

            step.status = StepStatus.RUNNING
            try:
                full_instruction = self._inject_context(task, step)
                output = self.llm_callable(full_instruction)
                step.output_data = output
                step.status = StepStatus.COMPLETED
                step.confidence = 0.8
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)

            if self.progress_callback:
                self.progress_callback(step, i + 1, task.total_steps)

        return task

    def _execute_hierarchical(self, task: DecomposedTask) -> DecomposedTask:
        if self.manager_llm is None:
            return self._execute_sequential(task)

        plan = self._manager_plan(task)
        for i, step_id in enumerate(plan.get("execution_order", [])):
            step = task.get_step(step_id)
            if not step:
                continue

            step.status = StepStatus.RUNNING
            try:
                full_instruction = self._inject_context(task, step)
                if plan.get("instructions", {}).get(step_id):
                    full_instruction += f"\n\nManager 指令：{plan['instructions'][step_id]}"
                output = self.llm_callable(full_instruction)
                step.output_data = output
                step.status = StepStatus.COMPLETED
                step.confidence = 0.9
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)

            if self.progress_callback:
                self.progress_callback(step, i + 1, task.total_steps)

        return task

    def _execute_parallel(self, task: DecomposedTask) -> DecomposedTask:
        sync_steps = [s for s in task.steps if not s.async_execution]
        async_steps = [s for s in task.steps
                       if s.async_execution and task.can_execute_step(s.step_id)]

        for step in sync_steps:
            if not task.can_execute_step(step.step_id):
                step.status = StepStatus.SKIPPED
                continue
            step.status = StepStatus.RUNNING
            try:
                output = self.llm_callable(self._inject_context(task, step))
                step.output_data = output
                step.status = StepStatus.COMPLETED
                step.confidence = 0.8
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)

        if async_steps:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(self._execute_step_async, task, step): step
                    for step in async_steps
                }
                for future in concurrent.futures.as_completed(futures):
                    step = futures[future]
                    try:
                        output = future.result()
                        step.output_data = output
                        step.status = StepStatus.COMPLETED
                        step.confidence = 0.8
                    except Exception as e:
                        step.status = StepStatus.FAILED
                        step.error = str(e)

        return task

    def _execute_step_async(self, task: DecomposedTask, step: TaskStep) -> str:
        step.status = StepStatus.RUNNING
        return self.llm_callable(self._inject_context(task, step))

    def _manager_plan(self, task: DecomposedTask) -> Dict[str, Any]:
        manager_prompt = f"""你是一个任务协调 Manager。请为以下任务制定执行计划：

原始问题：{task.original_question}

任务步骤：
{self._format_steps(task.steps)}

请输出JSON格式的执行计划，包含：
1. execution_order: 步骤执行顺序（step_id列表）
2. instructions: 每个步骤的 Manager 指令（字典，key为step_id）
3. validate_results: 是否验证结果（布尔值）

只输出JSON，不要输出其他内容。"""

        try:
            plan_json = self.manager_llm(manager_prompt)
            return json.loads(plan_json)
        except Exception:
            return {
                "execution_order": [s.step_id for s in task.steps],
                "instructions": {},
                "validate_results": False,
            }

    def _format_steps(self, steps: List[TaskStep]) -> str:
        lines = []
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step.title}: {step.description}")
        return "\n".join(lines)

    def _inject_context(self, task: DecomposedTask, step: TaskStep) -> str:
        full_instruction = step.instruction
        for dep_id in step.depends_on:
            dep = task.get_step(dep_id)
            if dep and dep.output_data:
                full_instruction = full_instruction.replace(
                    "{" + dep_id + "}", str(dep.output_data))
        return full_instruction

    def _default_llm_call(self, prompt: str) -> str:
        try:
            from livingtree.core.model.router import get_model_router
            return get_model_router().route(prompt)
        except Exception as e:
            return f"[Error: {str(e)}]"


def create_sequential_task(
    question: str, task_type: str = None, max_steps: int = 5
) -> DecomposedTask:
    decomposer = TaskDecomposer(default_process_type=ProcessType.SEQUENTIAL)
    return decomposer.decompose(
        question=question, task_type=task_type,
        max_steps=max_steps, process_type=ProcessType.SEQUENTIAL)


def create_hierarchical_task(
    question: str, task_type: str = None, max_steps: int = 5
) -> DecomposedTask:
    decomposer = TaskDecomposer(default_process_type=ProcessType.HIERARCHICAL)
    return decomposer.decompose(
        question=question, task_type=task_type,
        max_steps=max_steps, process_type=ProcessType.HIERARCHICAL)


def create_parallel_task(
    question: str, task_type: str = None, max_steps: int = 5
) -> DecomposedTask:
    decomposer = TaskDecomposer(default_process_type=ProcessType.PARALLEL)
    return decomposer.decompose(
        question=question, task_type=task_type,
        max_steps=max_steps, process_type=ProcessType.PARALLEL)


def create_architecture_task(
    question: str, max_steps: int = 5
) -> DecomposedTask:
    decomposer = TaskDecomposer(default_process_type=ProcessType.HIERARCHICAL)
    return decomposer.decompose(
        question=question, task_type="architecture",
        max_steps=max_steps, process_type=ProcessType.HIERARCHICAL)


def create_refactoring_task(
    question: str, max_steps: int = 4
) -> DecomposedTask:
    decomposer = TaskDecomposer(default_process_type=ProcessType.SEQUENTIAL)
    return decomposer.decompose(
        question=question, task_type="refactoring",
        max_steps=max_steps, process_type=ProcessType.SEQUENTIAL)


def create_task_split_task(
    question: str, max_steps: int = 5
) -> DecomposedTask:
    decomposer = TaskDecomposer(default_process_type=ProcessType.HIERARCHICAL)
    return decomposer.decompose(
        question=question, task_type="task_split",
        max_steps=max_steps, process_type=ProcessType.HIERARCHICAL)


__all__ = [
    'ProcessType',
    'StepStatus',
    'TaskStep',
    'DecomposedTask',
    'TaskDecomposer',
    'ChainOfThoughtExecutor',
    'create_sequential_task',
    'create_hierarchical_task',
    'create_parallel_task',
    'create_architecture_task',
    'create_refactoring_task',
    'create_task_split_task',
]
