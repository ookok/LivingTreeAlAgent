"""
任务设计框架 (Task Design Framework)

实现四个阶段的渐进式训练体系：
- 阶段1：基础理解（读懂工业文档）
- 阶段2：逻辑推理（基于规则和数据进行判断）
- 阶段3：任务规划（调用工具和分解任务）
- 阶段4：全流程生成（端到端生成工业文档）

核心原则：严禁直接端到端训练复杂任务
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskDefinition:
    """任务定义"""
    task_id: str
    name: str
    description: str
    stage: int  # 1-4
    task_type: str
    difficulty: int  # 1-5
    expected_output_format: str
    examples: List[Dict[str, str]] = field(default_factory=list)
    data_requirements: Dict[str, Any] = field(default_factory=dict)
    evaluation_criteria: List[str] = field(default_factory=list)


@dataclass
class StageConfig:
    """阶段配置"""
    stage: int
    name: str
    duration_weeks: int
    description: str
    target_data_count: int
    tasks: List[str] = field(default_factory=list)
    evaluation_metrics: List[str] = field(default_factory=list)


class TaskFramework:
    """
    任务设计框架
    
    实现四个阶段的渐进式训练：
    
    阶段1：基础理解（1-2周）
    - 片段分类、实体识别、风格改写
    
    阶段2：逻辑推理（2-3周）
    - 参数校验、故障归因、方案对比
    
    阶段3：任务规划（3-4周）- 核心阶段
    - 工具选择、步骤拆解、缺口检测
    
    阶段4：全流程生成（持续优化）
    - 端到端文档生成
    """
    
    def __init__(self):
        # 阶段配置
        self.stage_configs: Dict[int, StageConfig] = self._define_stages()
        
        # 任务定义
        self.tasks: Dict[str, TaskDefinition] = self._define_tasks()
        
        # 当前阶段
        self.current_stage = 1
        
        # 统计
        self.completed_tasks = []
        self.task_attempts = {}
        
        print("[TaskFramework] 初始化完成")
    
    def _define_stages(self) -> Dict[int, StageConfig]:
        """定义四个训练阶段"""
        return {
            1: StageConfig(
                stage=1,
                name="基础理解",
                duration_weeks=2,
                description="让模型读懂工业文档的结构与术语",
                target_data_count=10000,
                tasks=["text_classification", "entity_recognition", "style_conversion"],
                evaluation_metrics=["accuracy", "precision", "recall"]
            ),
            2: StageConfig(
                stage=2,
                name="逻辑推理",
                duration_weeks=3,
                description="让模型学会基于规则和数据进行判断",
                target_data_count=20000,
                tasks=["parameter_validation", "fault_diagnosis", "solution_comparison"],
                evaluation_metrics=["accuracy", "reasoning_correctness"]
            ),
            3: StageConfig(
                stage=3,
                name="任务规划",
                duration_weeks=4,
                description="让模型学会调用工具和分解任务（核心阶段）",
                target_data_count=30000,
                tasks=["tool_selection", "task_decomposition", "gap_detection"],
                evaluation_metrics=["tool_call_accuracy", "decomposition_quality"]
            ),
            4: StageConfig(
                stage=4,
                name="全流程生成",
                duration_weeks=-1,  # 持续优化
                description="端到端生成完整、可用的工业文档",
                target_data_count=-1,  # 持续积累
                tasks=["report_generation", "project_design"],
                evaluation_metrics=["expert_rating", "task_completion_rate"]
            )
        }
    
    def _define_tasks(self) -> Dict[str, TaskDefinition]:
        """定义各阶段的任务"""
        return {
            # === 阶段1：基础理解 ===
            "text_classification": TaskDefinition(
                task_id="stage1_text_classification",
                name="片段分类",
                description="给定一段文本，判断它是故障描述、参数列表还是其他类型",
                stage=1,
                task_type="classification",
                difficulty=1,
                expected_output_format="single_label",
                examples=[
                    {"input": "电机转速超过额定值，出现异常噪音", "output": "故障描述"},
                    {"input": "型号：ABC-123，功率：5.5kW，转速：1450rpm", "output": "参数列表"},
                    {"input": "根据GB/T 1800.1-2020标准，公差等级为IT7", "output": "标准引用"}
                ],
                data_requirements={"min_length": 20, "max_length": 200},
                evaluation_criteria=["分类准确率", "边界情况处理"]
            ),
            "entity_recognition": TaskDefinition(
                task_id="stage1_entity_recognition",
                name="实体识别",
                description="从文档中提取设备型号、标准号、公差值等实体",
                stage=1,
                task_type="extraction",
                difficulty=1,
                expected_output_format="json",
                examples=[
                    {"input": "执行标准：GB/T 1184-1996，公差等级IT7", "output": '{"standard": "GB/T 1184-1996", "tolerance": "IT7"}'},
                    {"input": "选用型号为XYZ-456的压力传感器", "output": '{"model": "XYZ-456", "equipment_type": "压力传感器"}'}
                ],
                data_requirements={"must_contain_entities": True},
                evaluation_criteria=["实体提取准确率", "边界完整性"]
            ),
            "style_conversion": TaskDefinition(
                task_id="stage1_style_conversion",
                name="风格改写",
                description="将口语化需求改写为正式的技术语言",
                stage=1,
                task_type="rewriting",
                difficulty=2,
                expected_output_format="text",
                examples=[
                    {"input": "这个零件尺寸不太对，麻烦改一下", "output": "该零件尺寸不符合设计要求，请进行修正"},
                    {"input": "电机有点热，可能要坏", "output": "电机出现异常温升现象，建议进行故障排查"}
                ],
                data_requirements={"must_contain_technical_content": True},
                evaluation_criteria=["专业术语使用", "表达准确性"]
            ),
            
            # === 阶段2：逻辑推理 ===
            "parameter_validation": TaskDefinition(
                task_id="stage2_parameter_validation",
                name="参数校验",
                description="给定一组参数，判断是否违反某标准或规范",
                stage=2,
                task_type="validation",
                difficulty=2,
                expected_output_format="json",
                examples=[
                    {"input": "轴直径50mm，公差等级IT7，上偏差+0.03mm", "output": '{"valid": false, "reason": "IT7级公差在50mm尺寸段为0.025mm，实际偏差0.03mm超出范围"}'},
                    {"input": "工作温度120℃，选用PTFE材质密封", "output": '{"valid": false, "reason": "PTFE长期使用温度不应超过260℃，建议确认实际工况"}'}
                ],
                data_requirements={"must_contain_parameters": True},
                evaluation_criteria=["校验准确率", "标准引用正确性"]
            ),
            "fault_diagnosis": TaskDefinition(
                task_id="stage2_fault_diagnosis",
                name="故障归因",
                description="给定现象，推断可能原因并排除不可能选项",
                stage=2,
                task_type="diagnosis",
                difficulty=3,
                expected_output_format="json",
                examples=[
                    {"input": "电机运行时异响且温度升高", "output": '{"possible_causes": ["轴承损坏", "润滑不足", "过载"], "excluded": ["电源问题"], "suggestion": "优先检查轴承状态"}'},
                    {"input": "流量计读数波动大", "output": '{"possible_causes": ["介质含气泡", "安装不当", "传感器故障"], "excluded": ["电源问题"], "suggestion": "检查管道是否存在气穴"}'}
                ],
                data_requirements={"must_contain_fault_description": True},
                evaluation_criteria=["原因准确性", "排除合理性"]
            ),
            "solution_comparison": TaskDefinition(
                task_id="stage2_solution_comparison",
                name="方案对比",
                description="给出两个方案，基于成本/可靠性等维度进行评价",
                stage=2,
                task_type="comparison",
                difficulty=3,
                expected_output_format="json",
                examples=[
                    {"input": "方案A：使用304不锈钢，成本低；方案B：使用316不锈钢，成本高但耐腐蚀性好", "output": '{"recommendation": "方案B", "reason": "考虑到介质腐蚀性，316不锈钢的长期可靠性更优"}'},
                    {"input": "方案A：进口设备，价格高；方案B：国产设备，价格低", "output": '{"recommendation": "方案B", "reason": "国产设备已满足性能要求，性价比更高"}'}
                ],
                data_requirements={"must_contain_two_options": True},
                evaluation_criteria=["对比维度完整性", "推荐合理性"]
            ),
            
            # === 阶段3：任务规划（核心阶段）===
            "tool_selection": TaskDefinition(
                task_id="stage3_tool_selection",
                name="工具选择",
                description="给定问题，输出需要调用的计算工具列表",
                stage=3,
                task_type="planning",
                difficulty=4,
                expected_output_format="json",
                examples=[
                    {"input": "计算DN100管道在2MPa压力下的壁厚", "output": '{"tools": ["pipe_calculator", "material_lookup"], "reasoning": ["需要计算管道壁厚", "需要查询材料许用应力"]}'},
                    {"input": "绘制电机温升曲线", "output": '{"tools": ["data_extractor", "plot_generator"], "reasoning": ["需要提取测试数据", "需要生成曲线图表"]}'}
                ],
                data_requirements={"must_contain_technical_problem": True},
                evaluation_criteria=["工具选择准确性", "调用顺序合理性"]
            ),
            "task_decomposition": TaskDefinition(
                task_id="stage3_task_decomposition",
                name="步骤拆解",
                description="将复杂任务拆解为可执行的子步骤",
                stage=3,
                task_type="planning",
                difficulty=4,
                expected_output_format="json",
                examples=[
                    {"input": "撰写一份电机测试报告", "output": '{"steps": ["数据提取", "曲线绘制", "数据分析", "结论撰写"], "reasoning": ["先提取测试数据", "再绘制性能曲线", "分析数据趋势", "最后撰写结论"]}'},
                    {"input": "设计一套自动化生产线方案", "output": '{"steps": ["需求分析", "设备选型", "流程设计", "成本估算", "方案评审"], "reasoning": ["先明确需求", "再选择设备", "设计工艺流程", "估算成本", "最后评审"]}'}
                ],
                data_requirements={"must_contain_complex_task": True},
                evaluation_criteria=["步骤完整性", "逻辑顺序正确性"]
            ),
            "gap_detection": TaskDefinition(
                task_id="stage3_gap_detection",
                name="缺口检测",
                description="识别不完整任务中缺失的参数并生成追问",
                stage=3,
                task_type="planning",
                difficulty=5,
                expected_output_format="json",
                examples=[
                    {"input": "为化工厂选择一款流量计", "output": '{"missing_parameters": ["介质类型", "温度", "压力", "精度要求"], "questions": ["请问介质是什么？", "工作温度是多少？", "工作压力是多少？", "精度要求是多少？"]}'},
                    {"input": "计算齿轮强度", "output": '{"missing_parameters": ["材料牌号", "载荷", "转速", "安全系数"], "questions": ["齿轮材料是什么？", "承受的载荷是多少？", "转速是多少？", "要求的安全系数是多少？"]}'}
                ],
                data_requirements={"must_have_missing_info": True},
                evaluation_criteria=["缺口识别完整性", "追问针对性"]
            ),
            
            # === 阶段4：全流程生成 ===
            "report_generation": TaskDefinition(
                task_id="stage4_report_generation",
                name="报告生成",
                description="根据输入数据生成完整的技术报告",
                stage=4,
                task_type="generation",
                difficulty=5,
                expected_output_format="markdown",
                examples=[
                    {"input": "测试对象：电机ABC-123，测试数据：转速1450rpm，温升45℃", "output": "# 电机测试报告\n## 1. 测试对象\n型号：ABC-123\n## 2. 测试结果\n转速：1450rpm\n温升：45℃\n## 3. 结论\n测试合格"}
                ],
                data_requirements={"must_contain_test_data": True},
                evaluation_criteria=["报告完整性", "格式规范性"]
            ),
            "project_design": TaskDefinition(
                task_id="stage4_project_design",
                name="项目设计",
                description="根据需求文档生成完整的技术方案",
                stage=4,
                task_type="generation",
                difficulty=5,
                expected_output_format="markdown",
                examples=[
                    {"input": "需求：设计一条自动化装配线，产能100件/小时", "output": "# 自动化装配线设计方案\n## 1. 需求分析\n产能要求：100件/小时\n## 2. 方案设计\n..."}
                ],
                data_requirements={"must_contain_requirements": True},
                evaluation_criteria=["方案完整性", "技术可行性"]
            )
        }
    
    def get_stage_tasks(self, stage: int) -> List[TaskDefinition]:
        """获取指定阶段的任务列表"""
        stage_config = self.stage_configs.get(stage)
        if not stage_config:
            return []
        
        tasks = []
        for task_id in stage_config.tasks:
            task = self.tasks.get(task_id)
            if task:
                tasks.append(task)
        
        return tasks
    
    def get_task(self, task_id: str) -> Optional[TaskDefinition]:
        """获取任务定义"""
        return self.tasks.get(task_id)
    
    def advance_stage(self):
        """进入下一阶段"""
        if self.current_stage < 4:
            self.current_stage += 1
            print(f"[TaskFramework] 进入阶段 {self.current_stage}: {self.stage_configs[self.current_stage].name}")
        else:
            print("[TaskFramework] 已在最后阶段")
    
    def complete_task(self, task_id: str):
        """标记任务完成"""
        if task_id not in self.completed_tasks:
            self.completed_tasks.append(task_id)
        
        # 更新尝试次数
        self.task_attempts[task_id] = self.task_attempts.get(task_id, 0) + 1
    
    def get_stage_progress(self, stage: int) -> float:
        """获取阶段进度"""
        stage_config = self.stage_configs.get(stage)
        if not stage_config:
            return 0.0
        
        completed = sum(1 for t in stage_config.tasks if t in self.completed_tasks)
        return completed / len(stage_config.tasks) * 100
    
    def get_overall_progress(self) -> float:
        """获取总体进度"""
        total_tasks = sum(len(c.tasks) for c in self.stage_configs.values())
        completed = len(self.completed_tasks)
        return completed / total_tasks * 100
    
    def generate_training_plan(self) -> Dict[str, Any]:
        """生成训练计划"""
        plan = {
            "stages": []
        }
        
        for stage in [1, 2, 3, 4]:
            config = self.stage_configs[stage]
            tasks = self.get_stage_tasks(stage)
            
            stage_info = {
                "stage": stage,
                "name": config.name,
                "duration_weeks": config.duration_weeks,
                "description": config.description,
                "target_data_count": config.target_data_count,
                "tasks": []
            }
            
            for task in tasks:
                stage_info["tasks"].append({
                    "task_id": task.task_id,
                    "name": task.name,
                    "description": task.description,
                    "difficulty": task.difficulty,
                    "examples_count": len(task.examples)
                })
            
            plan["stages"].append(stage_info)
        
        return plan
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "current_stage": self.current_stage,
            "current_stage_name": self.stage_configs[self.current_stage].name,
            "completed_tasks": self.completed_tasks,
            "stage_progress": {
                stage: self.get_stage_progress(stage)
                for stage in [1, 2, 3, 4]
            },
            "overall_progress": self.get_overall_progress(),
            "total_tasks": len(self.tasks),
            "task_attempts": self.task_attempts
        }


def create_task_framework() -> TaskFramework:
    """创建任务框架实例"""
    return TaskFramework()


__all__ = [
    "TaskFramework",
    "TaskDefinition",
    "StageConfig",
    "create_task_framework"
]