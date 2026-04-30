"""
任务分解与链式思考系统（增强版 - 集成 CrewAI Process 模式）

通过结构化拆解任务并串联子任务，引导小模型逐步推理，
从而提升精准回答能力。

新增特性（借鉴 CrewAI）：
1. Sequential Process - 顺序执行
2. Hierarchical Process - 层级执行（Manager Agent 协调）
3. Parallel Process - 并行执行（异步任务）
"""

import json
import re
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Iterator
from typing import List, Dict, Any
from datetime import datetime


# ==================== Process 模式定义（借鉴 CrewAI）====================

class ProcessType(Enum):
    """任务执行流程类型（借鉴 CrewAI）"""
    SEQUENTIAL = "sequential"       # 顺序执行
    HIERARCHICAL = "hierarchical"  # 层级执行（Manager 协调）
    PARALLEL = "parallel"           # 并行执行（异步）


class StepStatus(Enum):
    """子步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    """任务步骤"""
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
    async_execution: bool = False  # 是否异步执行（用于 PARALLEL 模式）
    
    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "confidence": self.confidence,
            "error": self.error,
            "has_output": self.output_data is not None,
            "async_execution": self.async_execution
        }


@dataclass
class DecomposedTask:
    """分解后的任务"""
    task_id: str
    original_question: str
    steps: List[TaskStep]
    metadata: Dict[str, Any] = field(default_factory=dict)
    process_type: ProcessType = ProcessType.SEQUENTIAL  # 执行流程类型
    
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
        """检查步骤是否可执行（依赖已满足）"""
        step = self.get_step(step_id)
        if not step:
            return False
        if step.status != StepStatus.PENDING:
            return False
        for dep_id in step.depends_on:
            dep = self.get_step(dep_id)
            if not dep or dep.status != StepStatus.COMPLETED:
                return False
        return True
    
    def get_next_executable_step(self) -> Optional[TaskStep]:
        """获取下一个可执行的步骤"""
        for step in self.steps:
            if self.can_execute_step(step.step_id):
                return step
        return None
    
    def get_parallel_steps(self) -> List[TaskStep]:
        """
        获取可并行执行的步骤列表
        
        Returns:
            可并行执行的步骤列表（互相无依赖）
        """
        parallel_steps = []
        
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            
            # 检查依赖是否满足
            if all(
                self.get_step(dep_id).status == StepStatus.COMPLETED
                for dep_id in step.depends_on
            ):
                parallel_steps.append(step)
        
        return parallel_steps


# ==================== 任务分解器 ====================

class TaskDecomposer:
    """
    任务分解器（增强版 - 支持 CrewAI Process 模式）
    
    将复杂问题拆解为有序、可执行的子步骤，
    适用于参数有限的小模型。
    
    新增特性：
    - 支持三种 Process 类型（sequential/hierarchical/parallel）
    - 支持异步任务执行
    - 支持 Manager Agent 协调（hierarchical 模式）
    """
    
    # 内置分解模板
    DECOMPOSITION_TEMPLATES = {
        "analysis": {
            "name": "分析类任务",
            "max_steps": 4,
            "process_type": ProcessType.SEQUENTIAL,
            "steps": [
                {
                    "id": "context",
                    "title": "理解背景",
                    "desc": "提取问题中的关键信息和背景条件",
                    "prompt": "请分析以下问题的背景信息，提取关键要素：\n{question}\n\n用简洁的要点列出：1. 主要问题 2. 约束条件 3. 相关因素"
                },
                {
                    "id": "data_collection",
                    "title": "收集数据",
                    "desc": "整理问题相关的数据和事实",
                    "prompt": "基于上述分析，列出解决问题所需的数据点：\n{context}\n\n列出3-5个关键数据点，说明每个数据点的来源或计算方式"
                },
                {
                    "id": "analysis",
                    "title": "深入分析",
                    "desc": "基于数据进行分析推理",
                    "prompt": "根据收集的数据进行分析：\n{data}\n\n使用因果链条或对比分析的方式，给出核心发现（不超过3点）"
                },
                {
                    "id": "conclusion",
                    "title": "得出结论",
                    "desc": "综合分析给出最终答案",
                    "prompt": "综合以上分析，给出结论和建议：\n{analysis}\n\n结论应直接回应原问题：{original_question}"
                }
            ]
        },
        "design": {
            "name": "设计类任务",
            "max_steps": 5,
            "process_type": ProcessType.HIERARCHICAL,  # 设计任务适合层级执行
            "steps": [
                {
                    "id": "requirement",
                    "title": "明确需求",
                    "desc": "理解用户需求和约束条件",
                    "prompt": "分析设计需求：\n{question}\n\n列出：1. 核心目标 2. 功能需求 3. 非功能需求（性能/安全/易用性）"
                },
                {
                    "id": "research",
                    "title": "方案调研",
                    "desc": "调研可行方案和技术选型",
                    "prompt": "针对需求：\n{requirements}\n\n列出2-3种可行方案，简述各方案的技术特点、优缺点",
                    "async_execution": True  # 可并行调研
                },
                {
                    "id": "architecture",
                    "title": "架构设计",
                    "desc": "设计整体架构",
                    "prompt": "基于需求和方案：\n{requirements}\n{research}\n\n用结构化方式描述架构，包括模块划分和数据流"
                },
                {
                    "id": "detail",
                    "title": "详细设计",
                    "desc": "关键模块的详细设计",
                    "prompt": "针对关键模块：\n{architecture}\n\n给出具体的实现细节，包括接口定义和关键逻辑",
                    "async_execution": True  # 可并行设计
                },
                {
                    "id": "implementation",
                    "title": "实施计划",
                    "desc": "制定实施步骤和时间线",
                    "prompt": "基于设计：\n{detail}\n\n列出实施步骤（不超过5步）和每步的预期产出"
                }
            ]
        },
        "writing": {
            "name": "写作类任务",
            "max_steps": 4,
            "process_type": ProcessType.SEQUENTIAL,
            "steps": [
                {
                    "id": "outline",
                    "title": "确定大纲",
                    "desc": "分析主题并确定文章结构",
                    "prompt": "为以下主题确定文章大纲：\n{question}\n\n列出：1. 文章类型 2. 核心论点 3. 章节结构（3-5章）"
                },
                {
                    "id": "research",
                    "title": "收集素材",
                    "desc": "整理相关资料和数据",
                    "prompt": "基于大纲：\n{outline}\n\n列出需要引用的关键资料、数据或案例（3-5个）"
                },
                {
                    "id": "drafting",
                    "title": "撰写正文",
                    "desc": "按照大纲撰写各章节",
                    "prompt": "基于大纲和素材：\n{outline}\n{materials}\n\n撰写完整的文章内容，使用规范的学术/正式语言"
                },
                {
                    "id": "polish",
                    "title": "润色完善",
                    "desc": "检查逻辑、语法、格式",
                    "prompt": "检查并润色以下文章：\n{content}\n\n优化：1. 逻辑连贯性 2. 语言表达 3. 格式规范"
                }
            ]
        },
        "decision": {
            "name": "决策类任务",
            "max_steps": 5,
            "process_type": ProcessType.HIERARCHICAL,  # 决策任务适合层级执行
            "steps": [
                {
                    "id": "problem",
                    "title": "界定问题",
                    "desc": "明确决策要解决的问题",
                    "prompt": "界定决策问题：\n{question}\n\n明确：1. 决策目标 2. 决策范围 3. 成功标准"
                },
                {
                    "id": "options",
                    "title": "列出选项",
                    "desc": "生成可能的解决方案",
                    "prompt": "针对问题：\n{problem}\n\n列出3-4个可行的解决方案选项"
                },
                {
                    "id": "criteria",
                    "title": "确定标准",
                    "desc": "确定评估标准和权重",
                    "prompt": "基于问题：\n{problem}\n\n确定评估选项的标准（如成本、风险、收益、可执行性），并说明权重"
                },
                {
                    "id": "evaluate",
                    "title": "评估选项",
                    "desc": "按标准评估各选项",
                    "prompt": "使用以下标准评估选项：\n{criteria}\n\n对每个选项按标准打分（1-10分），并说明理由",
                    "async_execution": True  # 可并行评估
                },
                {
                    "id": "recommend",
                    "title": "给出建议",
                    "desc": "基于评估给出推荐",
                    "prompt": "基于评估结果：\n{evaluation}\n\n给出推荐方案及理由，说明风险和注意事项"
                }
            ]
        },
        "general": {
            "name": "通用任务",
            "max_steps": 3,
            "process_type": ProcessType.SEQUENTIAL,
            "steps": [
                {
                    "id": "understand",
                    "title": "理解问题",
                    "desc": "分析问题的核心要点",
                    "prompt": "分析以下问题：\n{question}\n\n用一句话概括核心问题，并列出2-3个相关要点"
                },
                {
                    "id": "reason",
                    "title": "推理分析",
                    "desc": "逐步推理得出解答",
                    "prompt": "基于对问题的理解：\n{understanding}\n\n进行逐步推理，每步说明理由，最终得出答案"
                },
                {
                    "id": "verify",
                    "title": "验证结果",
                    "desc": "检查答案是否完整准确",
                    "prompt": "验证以下回答：\n{answer}\n\n检查：1. 是否完整回答了问题 2. 是否有遗漏 3. 是否有错误"
                }
            ]
        },
        "architecture": {
            "name": "架构设计任务",
            "max_steps": 5,
            "process_type": ProcessType.HIERARCHICAL,
            "steps": [
                {
                    "id": "requirements",
                    "title": "需求分析",
                    "desc": "深入分析业务需求和约束条件",
                    "prompt": "分析以下架构设计需求：\n{question}\n\n详细列出：1. 核心目标 2. 功能需求清单 3. 非功能需求（性能/安全/高可用/扩展性）4. 技术约束"
                },
                {
                    "id": "system_architecture",
                    "title": "系统架构设计",
                    "desc": "设计整体系统架构图",
                    "prompt": "基于需求分析：\n{requirements}\n\n输出系统架构图描述，包括：1. 分层架构（展示层/服务层/数据层）2. 核心模块划分 3. 关键数据流 4. 外部系统集成点",
                    "async_execution": True
                },
                {
                    "id": "service_split",
                    "title": "服务拆分清单",
                    "desc": "微服务拆分与边界定义",
                    "prompt": "基于架构设计：\n{system_architecture}\n\n列出服务拆分清单：1. 每个服务的职责边界 2. 服务间接口定义 3. 调用关系图 4. 数据一致性策略",
                    "async_execution": True
                },
                {
                    "id": "tech_selection",
                    "title": "核心技术选型",
                    "desc": "按模块推荐适配技术栈",
                    "prompt": "基于服务拆分：\n{service_split}\n\n给出技术选型方案：1. 语言与框架选择 2. 数据库选型（主从/分片策略）3. 中间件（缓存/MQ/网关）4. 部署架构（容器/K8s/云原生）"
                },
                {
                    "id": "implementation",
                    "title": "实施计划与风险",
                    "desc": "制定实施步骤、时间线与风险预案",
                    "prompt": "综合以上分析：\n{tech_selection}\n\n输出实施计划：1. 分阶段实施步骤（不超过5步）2. 每步预期产出 3. 高风险点识别与应对方案 4. 验收标准"
                }
            ]
        },
        "refactoring": {
            "name": "代码重构任务",
            "max_steps": 4,
            "process_type": ProcessType.SEQUENTIAL,
            "steps": [
                {
                    "id": "analysis",
                    "title": "代码分析",
                    "desc": "分析代码结构、复杂度和问题点",
                    "prompt": "分析以下代码或描述：\n{question}\n\n输出分析结果：1. 代码结构概览 2. 复杂度分析（圈复杂度/嵌套深度）3. 重复代码识别 4. 潜在问题点（耦合度/可维护性/可测试性）"
                },
                {
                    "id": "decomposition",
                    "title": "逻辑拆解",
                    "desc": "拆解复杂逻辑为独立函数/模块",
                    "prompt": "基于代码分析：\n{analysis}\n\n进行逻辑拆解：1. 识别可提取的公共方法 2. 拆分复杂函数为小函数 3. 消除重复代码 4. 定义函数职责边界"
                },
                {
                    "id": "decoupling",
                    "title": "依赖解耦",
                    "desc": "拆解模块间强耦合关系",
                    "prompt": "基于逻辑拆解：\n{decomposition}\n\n进行依赖解耦：1. 识别模块间强耦合点 2. 设计独立接口 3. 引入依赖注入 4. 降低模块间关联度"
                },
                {
                    "id": "optimization",
                    "title": "分层优化",
                    "desc": "按架构分层优化代码结构",
                    "prompt": "基于依赖解耦：\n{decoupling}\n\n进行分层优化：1. 按控制器-服务-数据层重新组织 2. 添加接口定义 3. 优化错误处理 4. 添加类型注解和文档 5. 保持原有业务逻辑不变"
                }
            ]
        },
        "task_split": {
            "name": "任务拆解任务",
            "max_steps": 5,
            "process_type": ProcessType.HIERARCHICAL,
            "steps": [
                {
                    "id": "phase_decompose",
                    "title": "分阶段拆解",
                    "desc": "将大型任务分解为阶段",
                    "prompt": "分析以下任务：\n{question}\n\n进行分阶段拆解：1. 需求分析阶段 2. 设计阶段 3. 开发阶段 4. 测试阶段 5. 部署阶段，每个阶段的核心产出"
                },
                {
                    "id": "priority",
                    "title": "优先级排序",
                    "desc": "为任务分配优先级",
                    "prompt": "基于阶段拆解：\n{phase_decompose}\n\n进行优先级排序：1. 核心任务（必须优先完成）2. 次要任务（重要但非紧急）3. 边缘任务（锦上添花），说明优先级依据",
                    "async_execution": True
                },
                {
                    "id": "dependencies",
                    "title": "依赖关系梳理",
                    "desc": "梳理任务间的依赖关系",
                    "prompt": "基于阶段拆解：\n{phase_decompose}\n\n梳理依赖关系：1. 任务间依赖图 2. 并行任务识别 3. 关键路径分析 4. 前置条件清单",
                    "async_execution": True
                },
                {
                    "id": "risk",
                    "title": "风险识别",
                    "desc": "识别高风险任务和应对方案",
                    "prompt": "基于任务清单：\n{priority}\n\n识别风险：1. 高风险任务（如第三方接口对接/复杂算法）2. 风险等级评估 3. 应对方案 4. 备选方案"
                },
                {
                    "id": "task_list",
                    "title": "生成任务清单",
                    "desc": "输出可直接执行的任务清单",
                    "prompt": "综合以上分析：\n{dependencies}\n{risk}\n\n输出可执行任务清单：1. 任务ID 2. 任务名称 3. 描述 4. 优先级 5. 依赖任务ID 6. 预估时间 7. 负责人（可选）"
                }
            ]
        }
    }
    
    def __init__(self, default_process_type: ProcessType = ProcessType.SEQUENTIAL):
        """
        初始化分解器
        
        Args:
            default_process_type: 默认执行流程类型
        """
        self.templates = self.DECOMPOSITION_TEMPLATES
        self.default_process_type = default_process_type
    
    def detect_task_type(self, question: str) -> str:
        """
        自动检测任务类型
        
        Args:
            question: 用户问题
            
        Returns:
            任务类型: analysis / design / writing / decision / architecture / refactoring / task_split / general
        """
        question_lower = question.lower()
        
        # 架构设计类关键词（优先级最高）
        architecture_keywords = ["架构设计", "系统规划", "微服务", "高可用", "并发", "架构师"]
        if any(k in question_lower for k in architecture_keywords):
            return "architecture"
        
        # 任务拆解类关键词（优先级高于重构，因为更具体）
        task_split_keywords = ["任务分解", "任务规划", "分解任务", "任务清单", "拆解任务"]
        if any(k in question_lower for k in task_split_keywords):
            return "task_split"
        
        # 代码重构类关键词
        refactoring_keywords = ["重构", "优化", "拆解", "解耦", "重构代码", "代码优化"]
        if any(k in question_lower for k in refactoring_keywords):
            return "refactoring"
        
        # 分析类关键词
        analysis_keywords = ["分析", "评估", "比较", "对比", "预测", "研究", "检查"]
        if any(k in question_lower for k in analysis_keywords):
            return "analysis"
        
        # 设计类关键词
        design_keywords = ["设计", "方案", "架构", "构建", "规划", "策划"]
        if any(k in question_lower for k in design_keywords):
            return "design"
        
        # 写作类关键词
        writing_keywords = ["写", "创作", "文章", "报告", "论文", "总结", "说明"]
        if any(k in question_lower for k in writing_keywords):
            return "writing"
        
        # 决策类关键词
        decision_keywords = ["选择", "决策", "建议", "推荐", "哪个好", "怎么办"]
        if any(k in question_lower for k in decision_keywords):
            return "decision"
        
        return "general"
    
    def decompose(
        self, 
        question: str, 
        task_type: str = None,
        max_steps: int = 5,
        custom_steps: List[Dict] = None,
        process_type: ProcessType = None
    ) -> DecomposedTask:
        """
        分解任务（增强版 - 支持 Process 类型）
        
        Args:
            question: 用户问题
            task_type: 任务类型（自动检测如果为None）
            max_steps: 最大步骤数（超过会合并）
            custom_steps: 自定义步骤列表
            process_type: 执行流程类型（如果为None，使用模板默认值）
            
        Returns:
            DecomposedTask: 分解后的任务
        """
        import uuid
        
        # 自动检测任务类型
        if task_type is None:
            task_type = self.detect_task_type(question)
        
        # 生成任务ID
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        # 获取模板
        if custom_steps:
            steps_config = custom_steps
            process_type = process_type or self.default_process_type
        else:
            template = self.templates.get(task_type, self.templates["general"])
            steps_config = template["steps"][:max_steps]
            process_type = process_type or template.get("process_type", self.default_process_type)
        
        # 构建步骤
        steps = []
        prev_step_id = None
        
        for i, config in enumerate(steps_config):
            step_id = config.get("id", f"step_{i+1}")
            
            # 构建指令（替换变量）
            instruction = self._build_instruction(config.get("prompt", ""), question)
            
            step = TaskStep(
                step_id=step_id,
                title=config["title"],
                description=config.get("desc", ""),
                instruction=instruction,
                depends_on=[prev_step_id] if prev_step_id else [],
                async_execution=config.get("async_execution", False)  # 新增：异步执行标志
            )
            steps.append(step)
            prev_step_id = step_id
        
        return DecomposedTask(
            task_id=task_id,
            original_question=question,
            steps=steps,
            metadata={"task_type": task_type, "process_type": process_type.value},
            process_type=process_type
        )
    
    def _build_instruction(self, template: str, question: str) -> str:
        """构建带变量的指令"""
        instruction = template.replace("{question}", question)
        
        # 保留占位符，让执行时替换
        # {context}, {data}, {analysis} 等将在执行时动态替换
        return instruction


# ==================== 执行器（支持三种 Process 模式）====================

class ChainOfThoughtExecutor:
    """
    链式思考执行器（增强版 - 支持 CrewAI Process 模式）
    
    按照指定的流程类型执行分解后的任务步骤：
    1. Sequential - 顺序执行
    2. Hierarchical - 层级执行（Manager 协调）
    3. Parallel - 并行执行（异步任务）
    """
    
    def __init__(
        self,
        llm_callable: Callable[[str], str] = None,
        progress_callback: Callable[[TaskStep, int, int], None] = None,
        process_type: ProcessType = ProcessType.SEQUENTIAL,
        manager_llm: Callable[[str], str] = None
    ):
        """
        初始化执行器
        
        Args:
            llm_callable: LLM调用函数，签名为 (prompt: str) -> str
            progress_callback: 进度回调，签名为 (step: TaskStep, current: int, total: int) -> None
            process_type: 执行流程类型
            manager_llm: Manager LLM（用于 HIERARCHICAL 模式）
        """
        self.llm_callable = llm_callable or self._default_llm_call
        self.progress_callback = progress_callback
        self.process_type = process_type
        self.manager_llm = manager_llm
    
    def execute(
        self, 
        task: DecomposedTask,
        process_type: ProcessType = None
    ) -> DecomposedTask:
        """
        执行分解后的任务（支持三种 Process 模式）
        
        Args:
            task: 分解后的任务
            process_type: 执行流程类型（如果为None，使用 task.process_type）
            
        Returns:
            完成任务（带输出数据）
        """
        # 确定执行流程类型
        process_type = process_type or task.process_type
        
        # 根据流程类型选择执行策略
        if process_type == ProcessType.SEQUENTIAL:
            return self._execute_sequential(task)
        elif process_type == ProcessType.HIERARCHICAL:
            return self._execute_hierarchical(task)
        elif process_type == ProcessType.PARALLEL:
            return self._execute_parallel(task)
        else:
            raise ValueError(f"Unknown process type: {process_type}")
    
    def _execute_sequential(self, task: DecomposedTask) -> DecomposedTask:
        """
        顺序执行（Sequential Process）
        
        按照依赖顺序逐个执行步骤。
        """
        if self.progress_callback:
            self.progress_callback(None, 0, task.total_steps, "sequential")
        
        for i, step in enumerate(task.steps):
            # 检查依赖
            if not task.can_execute_step(step.step_id):
                step.status = StepStatus.SKIPPED
                continue
            
            # 执行步骤
            step.status = StepStatus.RUNNING
            
            try:
                # 构建完整指令（注入前置步骤输出）
                full_instruction = self._inject_context(task, step)
                
                # 调用LLM
                output = self.llm_callable(full_instruction)
                
                step.output_data = output
                step.status = StepStatus.COMPLETED
                step.confidence = 0.8  # 简化的置信度
                
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
            
            # 回调
            if self.progress_callback:
                self.progress_callback(step, i + 1, task.total_steps)
        
        return task
    
    def _execute_hierarchical(self, task: DecomposedTask) -> DecomposedTask:
        """
        层级执行（Hierarchical Process）
        
        使用 Manager LLM 协调任务执行：
        1. Manager 制定执行计划
        2. 分配子任务给 Worker
        3. 验证结果并决定下一步
        """
        if self.progress_callback:
            self.progress_callback(None, 0, task.total_steps, "hierarchical")
        
        # 如果没有 Manager LLM，降级为 Sequential
        if self.manager_llm is None:
            if self.progress_callback:
                self.progress_callback(None, 0, 0, "no_manager_fallback_to_sequential")
            return self._execute_sequential(task)
        
        # Manager 制定执行计划
        plan = self._manager_plan(task)
        
        if self.progress_callback:
            self.progress_callback(None, 0, task.total_steps, f"manager_plan: {plan}")
        
        # 按 Manager 计划执行
        for i, step_id in enumerate(plan["execution_order"]):
            step = task.get_step(step_id)
            if not step:
                continue
            
            # 执行步骤
            step.status = StepStatus.RUNNING
            
            try:
                # 构建完整指令（注入前置步骤输出和 Manager 指令）
                full_instruction = self._inject_context(task, step)
                full_instruction += f"\n\nManager 指令：{plan.get('instructions', {}).get(step_id, '')}"
                
                # 调用LLM
                output = self.llm_callable(full_instruction)
                
                step.output_data = output
                step.status = StepStatus.COMPLETED
                step.confidence = 0.9  # Manager 协调的任务置信度更高
                
                # Manager 验证结果
                if plan.get("validate_results", False):
                    is_valid = self._manager_validate(step, plan)
                    if not is_valid:
                        # 重新执行
                        step.status = StepStatus.RUNNING
                        output = self.llm_callable(full_instruction + "\n\n请修正之前的错误，重新执行。")
                        step.output_data = output
                        step.status = StepStatus.COMPLETED
                
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
            
            # 回调
            if self.progress_callback:
                self.progress_callback(step, i + 1, task.total_steps)
        
        return task
    
    def _execute_parallel(self, task: DecomposedTask) -> DecomposedTask:
        """
        并行执行（Parallel Process）
        
        并发执行无依赖的异步任务，提高执行效率。
        """
        if self.progress_callback:
            self.progress_callback(None, 0, task.total_steps, "parallel")
        
        import concurrent.futures
        
        # 分组：可以并行的步骤 vs 必须串行的步骤
        parallel_groups = []
        sequential_steps = []
        
        # 简单策略：标记了 async_execution=True 的步骤可以并行
        async_steps = [s for s in task.steps if s.async_execution and task.can_execute_step(s.step_id)]
        sync_steps = [s for s in task.steps if not s.async_execution]
        
        # 执行同步步骤（按依赖顺序）
        for step in sync_steps:
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
                idx = task.steps.index(step)
                self.progress_callback(step, idx + 1, task.total_steps)
        
        # 并发执行异步步骤
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
                    
                    if self.progress_callback:
                        idx = task.steps.index(step)
                        self.progress_callback(step, idx + 1, task.total_steps)
        
        return task
    
    def _execute_step_async(self, task: DecomposedTask, step: TaskStep) -> str:
        """
        异步执行单个步骤
        
        Args:
            task: 任务
            step: 步骤
            
        Returns:
            执行结果
        """
        step.status = StepStatus.RUNNING
        
        # 构建完整指令
        full_instruction = self._inject_context(task, step)
        
        # 调用LLM
        output = self.llm_callable(full_instruction)
        
        return output
    
    def _manager_plan(self, task: DecomposedTask) -> Dict[str, Any]:
        """
        Manager LLM 制定执行计划
        
        Args:
            task: 分解后的任务
            
        Returns:
            执行计划字典
        """
        # 构建 Manager 提示
        manager_prompt = f"""
        你是一个任务协调 Manager。请为以下任务制定执行计划：
        
        原始问题：{task.original_question}
        
        任务步骤：
        {self._format_steps(task.steps)}
        
        请输出JSON格式的执行计划，包含：
        1. execution_order: 步骤执行顺序（step_id列表）
        2. instructions: 每个步骤的 Manager 指令（字典，key为step_id）
        3. validate_results: 是否验证结果（布尔值）
        
        只输出JSON，不要输出其他内容。
        """
        
        try:
            # 调用 Manager LLM
            plan_json = self.manager_llm(manager_prompt)
            
            # 解析JSON
            plan = json.loads(plan_json)
            
            return plan
        except Exception as e:
            # 解析失败，使用默认顺序
            return {
                "execution_order": [s.step_id for s in task.steps],
                "instructions": {},
                "validate_results": False
            }
    
    def _manager_validate(self, step: TaskStep, plan: Dict[str, Any]) -> bool:
        """
        Manager 验证步骤结果
        
        Args:
            step: 已完成的步骤
            plan: 执行计划
            
        Returns:
            结果是否有效
        """
        validation_prompt = f"""
        你是一个质量验证 Manager。请验证以下结果是否满意：
        
        步骤：{step.title}
        指令：{step.instruction}
        结果：{step.output_data}
        
        如果结果满意，输出 "VALID"。
        如果不满意，输出 "INVALID: <原因>"。
        """
        
        try:
            validation_result = self.manager_llm(validation_prompt)
            
            if "VALID" in validation_result.upper():
                return True
            else:
                return False
        except Exception:
            return True  # 验证失败时默认通过
    
    def _inject_context(self, task: DecomposedTask, step: TaskStep) -> str:
        """
        注入上下文（前置步骤的输出）
        
        Args:
            task: 任务
            step: 当前步骤
            
        Returns:
            完整的指令（带上下文）
        """
        full_instruction = step.instruction
        
        # 替换上下文占位符
        for dep_id in step.depends_on:
            dep = task.get_step(dep_id)
            if dep and dep.output_data:
                placeholder = "{" + dep_id + "}"
                full_instruction = full_instruction.replace(
                    placeholder, 
                    str(dep.output_data)
                )
        
        return full_instruction
    
    def _format_steps(self, steps: List[TaskStep]) -> str:
        """格式化步骤列表（用于 Manager 提示）"""
        lines = []
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step.title}: {step.description}")
        return "\n".join(lines)
    
    def _default_llm_call(self, prompt: str) -> str:
        """默认的LLM调用（使用 GlobalModelRouter）"""
        try:
            from client.src.business.global_model_router import call_model_sync, ModelCapability
            return call_model_sync(ModelCapability.CHAT, prompt)
        except Exception as e:
            return f"[Error: {str(e)}]"


# ==================== 便捷函数 ====================

def create_sequential_task(
    question: str,
    task_type: str = None,
    max_steps: int = 5
) -> DecomposedTask:
    """
    创建 Sequential 流程的任务
    
    Args:
        question: 用户问题
        task_type: 任务类型
        max_steps: 最大步骤数
        
    Returns:
        DecomposedTask
    """
    decomposer = TaskDecomposer(default_process_type=ProcessType.SEQUENTIAL)
    return decomposer.decompose(
        question=question,
        task_type=task_type,
        max_steps=max_steps,
        process_type=ProcessType.SEQUENTIAL
    )


def create_hierarchical_task(
    question: str,
    task_type: str = None,
    max_steps: int = 5
) -> DecomposedTask:
    """
    创建 Hierarchical 流程的任务
    
    Args:
        question: 用户问题
        task_type: 任务类型
        max_steps: 最大步骤数
        
    Returns:
        DecomposedTask
    """
    decomposer = TaskDecomposer(default_process_type=ProcessType.HIERARCHICAL)
    return decomposer.decompose(
        question=question,
        task_type=task_type,
        max_steps=max_steps,
        process_type=ProcessType.HIERARCHICAL
    )


def create_parallel_task(
    question: str,
    task_type: str = None,
    max_steps: int = 5
) -> DecomposedTask:
    """
    创建 Parallel 流程的任务
    
    Args:
        question: 用户问题
        task_type: 任务类型
        max_steps: 最大步骤数
        
    Returns:
        DecomposedTask
    """
    decomposer = TaskDecomposer(default_process_type=ProcessType.PARALLEL)
    return decomposer.decompose(
        question=question,
        task_type=task_type,
        max_steps=max_steps,
        process_type=ProcessType.PARALLEL
    )


def create_architecture_task(
    question: str,
    max_steps: int = 5
) -> DecomposedTask:
    """
    创建架构设计任务（Trae 架构设计与系统规划 SKILL）
    
    Args:
        question: 用户需求描述
        max_steps: 最大步骤数
        
    Returns:
        DecomposedTask
    """
    decomposer = TaskDecomposer(default_process_type=ProcessType.HIERARCHICAL)
    return decomposer.decompose(
        question=question,
        task_type="architecture",
        max_steps=max_steps,
        process_type=ProcessType.HIERARCHICAL
    )


def create_refactoring_task(
    question: str,
    max_steps: int = 4
) -> DecomposedTask:
    """
    创建代码重构任务（Trae 代码重构与优化 SKILL）
    
    Args:
        question: 代码描述或代码片段
        max_steps: 最大步骤数
        
    Returns:
        DecomposedTask
    """
    decomposer = TaskDecomposer(default_process_type=ProcessType.SEQUENTIAL)
    return decomposer.decompose(
        question=question,
        task_type="refactoring",
        max_steps=max_steps,
        process_type=ProcessType.SEQUENTIAL
    )


def create_task_split_task(
    question: str,
    max_steps: int = 5
) -> DecomposedTask:
    """
    创建任务拆解任务（Trae 智能任务拆解大师 SKILL）
    
    Args:
        question: 用户需求描述
        max_steps: 最大步骤数
        
    Returns:
        DecomposedTask
    """
    decomposer = TaskDecomposer(default_process_type=ProcessType.HIERARCHICAL)
    return decomposer.decompose(
        question=question,
        task_type="task_split",
        max_steps=max_steps,
        process_type=ProcessType.HIERARCHICAL
    )


# 导出
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
    'create_task_split_task'
]
