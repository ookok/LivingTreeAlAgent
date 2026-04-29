"""
任务分解与链式思考系统
Task Decomposer for Small Models

通过结构化拆解任务并串联子任务，引导小模型逐步推理，
从而提升精准回答能力。
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Iterator
from typing import List, Dict, Any


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
    
    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "confidence": self.confidence,
            "error": self.error,
            "has_output": self.output_data is not None
        }


@dataclass
class DecomposedTask:
    """分解后的任务"""
    task_id: str
    original_question: str
    steps: List[TaskStep]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
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


class TaskDecomposer:
    """
    任务分解器
    
    将复杂问题拆解为有序、可执行的子步骤，
    适用于参数有限的小模型。
    """
    
    # 内置分解模板
    DECOMPOSITION_TEMPLATES = {
        "analysis": {
            "name": "分析类任务",
            "max_steps": 4,
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
                    "prompt": "针对需求：\n{requirements}\n\n列出2-3种可行方案，简述各方案的技术特点、优缺点"
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
                    "prompt": "针对关键模块：\n{architecture}\n\n给出具体的实现细节，包括接口定义和关键逻辑"
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
                    "prompt": "使用以下标准评估选项：\n{criteria}\n\n对每个选项按标准打分（1-10分），并说明理由"
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
        }
    }
    
    def __init__(self):
        """初始化分解器"""
        self.templates = self.DECOMPOSITION_TEMPLATES
    
    def detect_task_type(self, question: str) -> str:
        """
        自动检测任务类型
        
        Args:
            question: 用户问题
            
        Returns:
            任务类型: analysis / design / writing / decision / general
        """
        question_lower = question.lower()
        
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
        custom_steps: List[Dict] = None
    ) -> DecomposedTask:
        """
        分解任务
        
        Args:
            question: 用户问题
            task_type: 任务类型（自动检测如果为None）
            max_steps: 最大步骤数（超过会合并）
            custom_steps: 自定义步骤列表
            
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
        else:
            template = self.templates.get(task_type, self.templates["general"])
            steps_config = template["steps"][:max_steps]
        
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
                depends_on=[prev_step_id] if prev_step_id else []
            )
            steps.append(step)
            prev_step_id = step_id
        
        return DecomposedTask(
            task_id=task_id,
            original_question=question,
            steps=steps,
            metadata={"task_type": task_type}
        )
    
    def _build_instruction(self, template: str, question: str) -> str:
        """构建带变量的指令"""
        instruction = template.replace("{question}", question)
        
        # 保留占位符，让执行时替换
        # {context}, {data}, {analysis} 等将在执行时动态替换
        return instruction


class ChainOfThoughtExecutor:
    """
    链式思考执行器
    
    按照依赖顺序执行分解后的任务步骤，
    传递上下文，实现链式推理。
    """
    
    def __init__(
        self,
        llm_callable: Callable[[str], str] = None,
        progress_callback: Callable[[TaskStep, int, int], None] = None
    ):
        """
        初始化执行器
        
        Args:
            llm_callable: LLM调用函数，签名为 (prompt: str) -> str
            progress_callback: 进度回调，签名为 (step: TaskStep, current: int, total: int) -> None
        """
        self.llm_callable = llm_callable or self._default_llm_call
        self.progress_callback = progress_callback
    
    def execute(self, task: DecomposedTask) -> DecomposedTask:
        """
        执行分解后的任务
        
        Args:
            task: 分解后的任务
            
        Returns:
            完成任务（带输出数据）
        """
        # 按顺序执行步骤
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
    
    def execute_async(
        self, 
        task: DecomposedTask,
        callback: Callable[[DecomposedTask], None] = None
    ) -> None:
        """
        异步执行任务（用于非阻塞UI）
        
        Args:
            task: 分解后的任务
            callback: 完成回调
        """
        import threading
        
        def run():
            result = self.execute(task)
            if callback:
                callback(result)
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    
    def _inject_context(self, task: DecomposedTask, step: TaskStep) -> str:
        """注入前置步骤的输出作为上下文"""
        instruction = step.instruction
        
        # 收集前置步骤的输出
        for dep_id in step.depends_on:
            dep = task.get_step(dep_id)
            if dep and dep.output_data:
                # 根据依赖步骤ID注入对应变量
                if dep_id == "context":
                    instruction = instruction.replace("{context}", dep.output_data)
                elif dep_id == "data" or dep_id == "data_collection":
                    instruction = instruction.replace("{data}", dep.output_data)
                elif dep_id == "materials":
                    instruction = instruction.replace("{materials}", dep.output_data)
                elif dep_id == "requirements":
                    instruction = instruction.replace("{requirements}", dep.output_data)
                elif dep_id == "research":
                    instruction = instruction.replace("{research}", dep.output_data)
                elif dep_id == "architecture":
                    instruction = instruction.replace("{architecture}", dep.output_data)
                elif dep_id == "outline":
                    instruction = instruction.replace("{outline}", dep.output_data)
                elif dep_id == "analysis":
                    instruction = instruction.replace("{analysis}", dep.output_data)
                elif dep_id == "evaluation":
                    instruction = instruction.replace("{evaluation}", dep.output_data)
                elif dep_id == "understanding":
                    instruction = instruction.replace("{understanding}", dep.output_data)
                elif dep_id == "content":
                    instruction = instruction.replace("{content}", dep.output_data)
                elif dep_id == "answer":
                    instruction = instruction.replace("{answer}", dep.output_data)
                elif dep_id == "problem":
                    instruction = instruction.replace("{problem}", dep.output_data)
                elif dep_id == "options":
                    instruction = instruction.replace("{options}", dep.output_data)
                elif dep_id == "criteria":
                    instruction = instruction.replace("{criteria}", dep.output_data)
                elif dep_id == "detail" or dep_id == "detail_design":
                    instruction = instruction.replace("{detail}", dep.output_data)
        
        # 保留原问题
        instruction = instruction.replace("{original_question}", task.original_question)
        
        return instruction
    
    def _default_llm_call(self, prompt: str) -> str:
        """默认的LLM调用（用于测试）"""
        return f"[模拟响应]: {prompt[:100]}..."


def format_task_result(task: DecomposedTask) -> str:
    """
    格式化任务结果为可读文本
    
    Args:
        task: 完成任务
        
    Returns:
        格式化后的结果文本
    """
    lines = []
    lines.append(f"# 任务完成报告\n")
    lines.append(f"**原始问题**: {task.original_question}\n")
    lines.append(f"**任务类型**: {task.metadata.get('task_type', 'general')}\n")
    lines.append(f"**进度**: {task.completed_steps}/{task.total_steps} 步骤完成\n")
    lines.append(f"\n---\n\n")
    
    for step in task.steps:
        lines.append(f"## {step.step_id}. {step.title}\n")
        lines.append(f"**状态**: {step.status.value}")
        
        if step.description:
            lines.append(f" | *{step.description}*")
        lines.append("\n")
        
        if step.output_data:
            lines.append(f"{step.output_data}\n")
        elif step.error:
            lines.append(f"❌ 错误: {step.error}\n")
        
        lines.append("\n")
    
    return "".join(lines)


def get_chain_of_thought_prompt(question: str) -> str:
    """
    获取链式思考提示词
    
    用于直接发送给不支持结构化分解的小模型。
    
    Args:
        question: 用户问题
        
    Returns:
        链式思考提示词
    """
    return f"""请采用链式思考方式，逐步分析和回答以下问题。

**问题**: {question}

**思考步骤**:
1. 首先理解问题的核心要点
2. 然后进行逐步推理，每步说明理由
3. 最后给出完整答案

请在回答中明确标注你的思考过程：
- 第一步：...
- 第二步：...
- 第三步：...

最后：
- 结论：...
- 置信度：（你对答案的确信程度：高/中/低）
"""
