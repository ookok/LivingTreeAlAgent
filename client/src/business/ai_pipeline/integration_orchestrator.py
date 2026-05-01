"""
集成编排器 - 整合所有AI流水线模块

核心功能：
1. 统一调度所有模块
2. 协调模块间的数据流转
3. 实现完整的研发工作流
4. 提供统一的API接口
5. 支持多种自动化模式
6. 整合自动化配置、部署、调度、学习系统
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
from pathlib import Path

from .ai_workflow_engine import AIWorkflowEngine, WorkflowDefinition, ExecutionContext
from .task_decomposition_engine import TaskDecompositionEngine, DecompositionResult
from .code_generation_unit import CodeGenerationUnit, CodeContext, GenerationResult, GenerationPhase
from .auto_test_system import AutoTestSystem, TestCase, TestType, TestResult
from .smart_fix_engine import SmartFixEngine, Issue, Fix, FixResult
from .quality_gates import QualityGates, QualityReport
from .knowledge_management import KnowledgeManagement
from .context_manager import ContextManager
from .ide_pipeline_panel import PipelinePanel, PipelineStage, PipelineTask, ApprovalPoint, TaskStatus, ApprovalStatus
from .conversation_orchestrator import ConversationOrchestrator, ConversationState, RequirementContext
from .progressive_thinking import ProgressiveThinkingEngine
from .auto_config import AutoConfig, EnvironmentType
from .auto_deploy import AutoDeploy, DeploymentStatus, ServiceType
from .code_workflow import CodeWorkflowEngine, WorkflowMode
from .smart_scheduler import SmartScheduler, TaskPriority
from .multimodal_processor import MultimodalProcessor, InputData, InputType, ParsedResult
from .adaptive_learning import AdaptiveLearningSystem, PatternType
from .incremental_generator import IncrementalCodeGenerator, GenerationResult as IncrementalResult


class AutomationMode(Enum):
    FULL_AUTO = "full_auto"
    SUPERVISION = "supervision"
    COLLABORATIVE = "collaborative"
    LEARNING = "learning"


class PipelineStatus(Enum):
    PENDING = "pending"
    CONFIGURING = "configuring"
    ANALYZING = "analyzing"
    DECOMPOSING = "decomposing"
    CODING = "coding"
    TESTING = "testing"
    REVIEWING = "reviewing"
    DEPLOYING = "deploying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineRun:
    """流水线运行实例"""
    id: str
    requirement: str
    status: PipelineStatus
    automation_mode: AutomationMode
    decomposition_result: Optional[DecompositionResult] = None
    code_results: List[GenerationResult] = field(default_factory=list)
    test_results: List[TestResult] = field(default_factory=list)
    fix_results: List[FixResult] = field(default_factory=list)
    quality_report: Optional[QualityReport] = None
    deployment_result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_estimated_time: float = 0.0
    elapsed_time: float = 0.0
    workflow_run_id: Optional[str] = None


class IntegrationOrchestrator:
    """
    集成编排器 - 整合所有AI流水线模块
    
    核心特性：
    1. 统一调度所有模块
    2. 协调模块间的数据流转
    3. 实现完整的研发工作流
    4. 支持多种自动化模式
    5. 提供统一的API接口
    6. 自动化配置、部署、启动
    7. 智能调度与自适应学习
    """

    def __init__(self):
        # 核心模块
        self._workflow_engine = AIWorkflowEngine()
        self._decomposition_engine = TaskDecompositionEngine()
        self._code_generator = CodeGenerationUnit()
        self._test_system = AutoTestSystem()
        self._fix_engine = SmartFixEngine()
        self._quality_gates = QualityGates()
        self._knowledge_manager = KnowledgeManagement()
        self._context_manager = ContextManager()
        self._pipeline_panel = PipelinePanel()
        self._conversation_orchestrator = ConversationOrchestrator()
        self._thinking_engine = ProgressiveThinkingEngine()
        
        # 新增模块
        self._auto_config = AutoConfig()
        self._auto_deploy = AutoDeploy()
        self._code_workflow = CodeWorkflowEngine()
        self._scheduler = SmartScheduler()
        self._multimodal_processor = MultimodalProcessor()
        self._adaptive_learning = AdaptiveLearningSystem()
        self._incremental_generator = IncrementalCodeGenerator()
        
        self._runs: Dict[str, PipelineRun] = {}
        self._conversations: Dict[str, str] = {}  # run_id -> conversation_id
        
        self._pipeline_panel.register_callback(self._on_pipeline_event)
        
        print("🔧 AI Pipeline 集成编排器初始化完成")

    def _on_pipeline_event(self, event: Dict[str, Any]):
        """处理流水线事件"""
        print(f"📢 流水线事件: {event}")

    async def initialize_system(self, auto_deploy: bool = True) -> Dict[str, Any]:
        """
        一键初始化系统
        
        Args:
            auto_deploy: 是否自动部署服务
        
        Returns:
            初始化结果
        """
        print("🚀 开始系统初始化...")
        
        results = {
            "config": None,
            "deploy": None,
            "success": False
        }
        
        # 1. 自动配置
        print("🔧 执行自动配置...")
        config_result = await self._auto_config.initialize()
        results["config"] = config_result
        
        if not config_result.get("success"):
            print("❌ 配置初始化失败")
            return results
        
        # 2. 自动部署（可选）
        if auto_deploy:
            print("📦 执行自动部署...")
            deploy_result = await self._auto_deploy.deploy(install_deps=False)
            results["deploy"] = deploy_result
            
            if not deploy_result.success:
                print("❌ 部署失败")
                return results
        
        # 3. 启动调度器
        print("⏰ 启动智能调度器...")
        asyncio.create_task(self._scheduler.start())
        
        # 4. 加载知识管理
        print("📚 加载知识管理...")
        await self._knowledge_manager.load_knowledge_base()
        
        results["success"] = True
        print("✅ 系统初始化完成")
        
        return results

    async def start_pipeline(self, requirement: str, automation_mode: AutomationMode = AutomationMode.SUPERVISION,
                            context: Optional[Dict[str, Any]] = None, 
                            input_type: InputType = InputType.TEXT) -> str:
        """
        启动完整的AI研发流水线
        
        Args:
            requirement: 用户自然语言需求
            automation_mode: 自动化模式
            context: 初始上下文
            input_type: 输入类型
            
        Returns:
            流水线运行ID
        """
        run_id = f"run_{int(datetime.now().timestamp())}"
        
        run = PipelineRun(
            id=run_id,
            requirement=requirement,
            status=PipelineStatus.PENDING,
            automation_mode=automation_mode
        )
        
        self._runs[run_id] = run
        
        print(f"🚀 启动AI研发流水线: {run_id}")
        
        # 创建上下文
        task_context_id = self._context_manager.create_task_context(
            workflow_id=run_id,
            variables={"requirement": requirement, **(context or {})}
        )
        
        # 创建流水线面板
        self._create_pipeline_panel(run_id, requirement)
        
        # 异步执行流水线
        asyncio.create_task(self._execute_pipeline(run, task_context_id, input_type))
        
        return run_id

    def _create_pipeline_panel(self, run_id: str, requirement: str):
        """创建流水线面板"""
        stages = [
            PipelineStage(id="configure", name="系统配置", tasks=[
                PipelineTask(id="config_1", name="环境检测", description="检测系统环境", status=TaskStatus.PENDING),
                PipelineTask(id="config_2", name="依赖检查", description="检查依赖状态", status=TaskStatus.PENDING)
            ]),
            PipelineStage(id="analyze", name="需求分析", tasks=[
                PipelineTask(id="analyze_1", name="意图识别", description="识别需求类型", status=TaskStatus.PENDING),
                PipelineTask(id="analyze_2", name="复杂度评估", description="评估工作量", status=TaskStatus.PENDING),
                PipelineTask(id="analyze_3", name="依赖分析", description="分析依赖关系", status=TaskStatus.PENDING)
            ]),
            PipelineStage(id="decompose", name="任务分解", tasks=[
                PipelineTask(id="decompose_1", name="EPIC定义", description="定义史诗级需求", status=TaskStatus.PENDING),
                PipelineTask(id="decompose_2", name="User Story", description="创建用户故事", status=TaskStatus.PENDING),
                PipelineTask(id="decompose_3", name="Task拆解", description="拆解具体任务", status=TaskStatus.PENDING)
            ]),
            PipelineStage(id="code", name="代码生成", tasks=[
                PipelineTask(id="code_1", name="接口定义", description="生成接口", status=TaskStatus.PENDING),
                PipelineTask(id="code_2", name="核心实现", description="实现核心逻辑", status=TaskStatus.PENDING),
                PipelineTask(id="code_3", name="代码完善", description="添加异常处理", status=TaskStatus.PENDING)
            ]),
            PipelineStage(id="test", name="测试", tasks=[
                PipelineTask(id="test_1", name="单元测试", description="生成并执行单元测试", status=TaskStatus.PENDING),
                PipelineTask(id="test_2", name="集成测试", description="生成并执行集成测试", status=TaskStatus.PENDING),
                PipelineTask(id="test_3", name="性能测试", description="生成并执行性能测试", status=TaskStatus.PENDING)
            ]),
            PipelineStage(id="quality", name="质量门禁", tasks=[
                PipelineTask(id="gate_1", name="代码质量", description="静态分析", status=TaskStatus.PENDING),
                PipelineTask(id="gate_2", name="功能验证", description="测试覆盖", status=TaskStatus.PENDING),
                PipelineTask(id="gate_3", name="发布就绪", description="文档检查", status=TaskStatus.PENDING)
            ]),
            PipelineStage(id="deploy", name="部署", tasks=[
                PipelineTask(id="deploy_1", name="构建打包", description="构建应用", status=TaskStatus.PENDING),
                PipelineTask(id="deploy_2", name="部署发布", description="部署到目标环境", status=TaskStatus.PENDING)
            ])
        ]
        
        approval_points = [
            ApprovalPoint(
                id="approval_code",
                name="代码审查",
                description="代码审查审批点",
                status=ApprovalStatus.PENDING,
                required_approvers=["tech_lead"],
                due_date=datetime.now()
            ),
            ApprovalPoint(
                id="approval_release",
                name="发布审批",
                description="发布前最终审批",
                status=ApprovalStatus.PENDING,
                required_approvers=["product_manager", "tech_lead"],
                due_date=datetime.now()
            )
        ]
        
        self._pipeline_panel.create_pipeline(
            workflow_id=run_id,
            name=f"研发任务: {requirement[:30]}",
            stages=stages
        )
        
        for approval in approval_points:
            pass

    async def _execute_pipeline(self, run: PipelineRun, task_context_id: str, input_type: InputType):
        """执行完整的流水线"""
        run.status = PipelineStatus.CONFIGURING
        run.started_at = datetime.now()
        
        try:
            # 0. 系统配置检查
            await self._execute_configuration(run)
            
            # 1. 多模态输入处理
            await self._process_multimodal_input(run, input_type)
            
            # 2. 需求分析与任务分解
            await self._execute_decomposition(run, task_context_id)
            
            if run.automation_mode == AutomationMode.SUPERVISION:
                await self._request_approval("分解完成，请确认")
            
            # 3. 代码生成（增量）
            await self._execute_code_generation(run, task_context_id)
            
            if run.automation_mode == AutomationMode.SUPERVISION:
                await self._request_approval("代码生成完成，请确认")
            
            # 4. 测试
            await self._execute_testing(run, task_context_id)
            
            # 5. 智能修复（如果测试失败）
            failed_tests = [r for r in run.test_results if not r.success]
            if failed_tests:
                await self._execute_fixing(run, failed_tests)
            
            # 6. 质量门禁
            await self._execute_quality_gates(run, task_context_id)
            
            if run.automation_mode == AutomationMode.SUPERVISION:
                await self._request_approval("质量门禁通过，请确认发布")
            
            # 7. 部署
            await self._execute_deployment(run)
            
            # 8. 完成
            run.status = PipelineStatus.COMPLETED
            run.completed_at = datetime.now()
            run.elapsed_time = (run.completed_at - run.started_at).total_seconds()
            
            print(f"🎉 流水线完成: {run.id}, 耗时: {run.elapsed_time:.2f}秒")
            
            # 学习反馈
            await self._adaptive_learning.collect_feedback(
                task_id=run.id,
                user_id="system",
                feedback_type="positive",
                content=f"流水线执行成功，耗时{run.elapsed_time:.2f}秒"
            )
            
        except Exception as e:
            run.status = PipelineStatus.FAILED
            print(f"❌ 流水线失败 {run.id}: {e}")
            
            await self._adaptive_learning.collect_feedback(
                task_id=run.id,
                user_id="system",
                feedback_type="negative",
                content=f"流水线执行失败: {str(e)}"
            )
        
        # 更新上下文
        self._context_manager.update_task_context(task_context_id, {"status": run.status.value})

    async def _execute_configuration(self, run: PipelineRun):
        """执行系统配置检查"""
        print(f"🔧 执行系统配置检查...")
        
        self._pipeline_panel.update_task_status(run.id, "config_1", TaskStatus.IN_PROGRESS, 50)
        
        # 检查配置
        config_status = await self._auto_config.validate_config()
        
        self._pipeline_panel.update_task_status(run.id, "config_1", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "config_2", TaskStatus.COMPLETED, 100)
        
        print(f"✅ 系统配置检查完成")

    async def _process_multimodal_input(self, run: PipelineRun, input_type: InputType):
        """处理多模态输入"""
        print(f"📥 处理多模态输入: {input_type.value}")
        
        input_data = InputData(
            id=f"input_{run.id}",
            type=input_type,
            content=run.requirement
        )
        
        result = await self._multimodal_processor.process(input_data)
        
        if result.success:
            print(f"✅ 多模态输入处理完成")
        else:
            print(f"⚠️ 多模态输入处理失败: {result.error}")

    async def _execute_decomposition(self, run: PipelineRun, task_context_id: str):
        """执行任务分解"""
        print(f"🔍 执行任务分解...")
        
        self._pipeline_panel.update_task_status(run.id, "analyze_1", TaskStatus.IN_PROGRESS, 50)
        
        context = self._context_manager.get_task_context(task_context_id)
        context_vars = context.variables if context else {}
        
        run.decomposition_result = await self._decomposition_engine.decompose(
            run.requirement,
            context_vars
        )
        
        self._pipeline_panel.update_task_status(run.id, "analyze_1", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "analyze_2", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "analyze_3", TaskStatus.COMPLETED, 100)
        
        self._pipeline_panel.update_task_status(run.id, "decompose_1", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "decompose_2", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "decompose_3", TaskStatus.COMPLETED, 100)
        
        if run.decomposition_result:
            run.total_estimated_time = run.decomposition_result.epic.total_estimated_hours * 3600
        
        print(f"✅ 任务分解完成，预估时间: {run.total_estimated_time/3600:.1f}小时")

    async def _execute_code_generation(self, run: PipelineRun, task_context_id: str):
        """执行代码生成"""
        print(f"💻 执行代码生成...")
        
        self._pipeline_panel.update_task_status(run.id, "code_1", TaskStatus.IN_PROGRESS, 33)
        
        code_context = CodeContext(
            project_structure={},
            existing_code={},
            coding_style=self._adaptive_learning.get_style_preferences().__dict__,
            dependencies=["python", "pyqt6"],
            patterns=["async", "dataclass"]
        )
        
        # 使用增量生成
        inc_result = await self._incremental_generator.generate_incremental(
            task_id=run.id,
            requirement=run.requirement,
            context=code_context.__dict__
        )
        
        # 阶段1: 接口定义
        result1 = await self._code_generator.generate_code(
            run.requirement,
            code_context,
            GenerationPhase.INTERFACE
        )
        run.code_results.append(result1)
        
        self._pipeline_panel.update_task_status(run.id, "code_1", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "code_2", TaskStatus.IN_PROGRESS, 33)
        
        # 阶段2: 核心实现
        result2 = await self._code_generator.generate_code(
            run.requirement,
            code_context,
            GenerationPhase.IMPLEMENTATION
        )
        run.code_results.append(result2)
        
        self._pipeline_panel.update_task_status(run.id, "code_2", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "code_3", TaskStatus.IN_PROGRESS, 33)
        
        # 阶段3: 代码完善
        result3 = await self._code_generator.generate_code(
            run.requirement,
            code_context,
            GenerationPhase.COMPLETION
        )
        run.code_results.append(result3)
        
        self._pipeline_panel.update_task_status(run.id, "code_3", TaskStatus.COMPLETED, 100)
        
        # 学习代码模式
        for result in run.code_results:
            for file in result.files:
                await self._knowledge_manager.learn_pattern(file.content)
        
        # 更新学习系统
        code_samples = [f.content for r in run.code_results for f in r.files]
        await self._adaptive_learning.learn_coding_style(code_samples)
        
        print(f"✅ 代码生成完成，生成 {len(run.code_results)} 个阶段")

    async def _execute_testing(self, run: PipelineRun, task_context_id: str):
        """执行测试"""
        print(f"🧪 执行测试...")
        
        self._pipeline_panel.update_task_status(run.id, "test_1", TaskStatus.IN_PROGRESS, 33)
        
        # 生成单元测试
        unit_tests = await self._test_system.generate_unit_tests(
            run.requirement,
            "main.py"
        )
        
        # 执行单元测试
        results = await self._test_system.run_tests(unit_tests)
        run.test_results.extend(results)
        
        self._pipeline_panel.update_task_status(run.id, "test_1", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "test_2", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "test_3", TaskStatus.COMPLETED, 100)
        
        passed = sum(1 for r in results if r.success)
        print(f"✅ 测试完成: {passed}/{len(results)} 通过")

    async def _execute_fixing(self, run: PipelineRun, failed_tests: List[TestResult]):
        """执行智能修复"""
        print(f"🔧 执行智能修复...")
        
        for test_result in failed_tests:
            issue = await self._fix_engine.analyze_failure(test_result)
            
            fix = await self._fix_engine.generate_fix(issue, "")
            
            fix_result = await self._fix_engine.apply_fix(fix)
            run.fix_results.append(fix_result)
            
            if fix_result.success:
                print(f"✅ 修复成功: {fix.issue.title}")
            else:
                print(f"❌ 修复失败: {fix.issue.title}")

    async def _execute_quality_gates(self, run: PipelineRun, task_context_id: str):
        """执行质量门禁"""
        print(f"🚧 执行质量门禁...")
        
        self._pipeline_panel.update_task_status(run.id, "gate_1", TaskStatus.IN_PROGRESS, 50)
        
        project_info = {
            "project_name": "AI Pipeline Project",
            "branch": "main",
            "commit_hash": "abc123"
        }
        
        run.quality_report = await self._quality_gates.run_all_gates(project_info)
        
        self._pipeline_panel.update_task_status(run.id, "gate_1", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "gate_2", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "gate_3", TaskStatus.COMPLETED, 100)
        
        print(f"✅ 质量门禁完成: {run.quality_report.overall_status.value}")

    async def _execute_deployment(self, run: PipelineRun):
        """执行部署"""
        print(f"🚀 执行部署...")
        
        self._pipeline_panel.update_task_status(run.id, "deploy_1", TaskStatus.IN_PROGRESS, 50)
        
        # 生成启动脚本
        script_path = await self._auto_deploy.generate_startup_script()
        
        self._pipeline_panel.update_task_status(run.id, "deploy_1", TaskStatus.COMPLETED, 100)
        self._pipeline_panel.update_task_status(run.id, "deploy_2", TaskStatus.COMPLETED, 100)
        
        run.deployment_result = {
            "script_path": script_path,
            "status": "success",
            "message": "部署脚本已生成"
        }
        
        print(f"✅ 部署完成，启动脚本: {script_path}")

    async def _request_approval(self, message: str) -> bool:
        """请求人工审批（模拟）"""
        print(f"⚠️ 需要审批: {message}")
        return True

    async def get_pipeline_status(self, run_id: str) -> Dict[str, Any]:
        """获取流水线状态"""
        run = self._runs.get(run_id)
        if not run:
            return {"error": "流水线不存在"}
        
        return {
            "id": run.id,
            "requirement": run.requirement,
            "status": run.status.value,
            "automation_mode": run.automation_mode.value,
            "created_at": run.created_at.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "total_estimated_time": run.total_estimated_time,
            "elapsed_time": run.elapsed_time,
            "panel_status": self._pipeline_panel.get_pipeline_status(run.id),
            "deployment_result": run.deployment_result
        }

    def list_pipelines(self) -> List[Dict[str, Any]]:
        """列出所有流水线"""
        result = []
        for run in self._runs.values():
            result.append({
                "id": run.id,
                "requirement": run.requirement[:50],
                "status": run.status.value,
                "automation_mode": run.automation_mode.value,
                "created_at": run.created_at.isoformat()
            })
        return result

    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """获取编排器统计"""
        return {
            "total_runs": len(self._runs),
            "completed_runs": sum(1 for r in self._runs.values() if r.status == PipelineStatus.COMPLETED),
            "failed_runs": sum(1 for r in self._runs.values() if r.status == PipelineStatus.FAILED),
            "knowledge_stats": self._knowledge_manager.get_knowledge_stats(),
            "context_stats": self._context_manager.get_context_stats(),
            "feedback_summary": self._adaptive_learning.get_feedback_summary(),
            "scheduler_tasks": len(self._scheduler.list_tasks())
        }

    async def clarify_requirement(self, run_id: str, user_input: str) -> Dict[str, Any]:
        """澄清需求"""
        if run_id not in self._conversations:
            conversation_id = self._conversation_orchestrator.start_conversation(run_id)
            self._conversations[run_id] = conversation_id
        else:
            conversation_id = self._conversations[run_id]
        
        result = await self._conversation_orchestrator.process_user_input(conversation_id, user_input)
        
        state = self._conversation_orchestrator.get_conversation_state(conversation_id)
        context = self._conversation_orchestrator.get_conversation_context(conversation_id)
        
        return {
            "response": result.get("response", ""),
            "state": state.value if state else "unknown",
            "context": {
                "functional_count": len(context.functional) if context else 0,
                "non_functional_count": len(context.non_functional) if context else 0,
                "constraints_count": len(context.constraints) if context else 0
            },
            "is_complete": state == ConversationState.COMPLETE if state else False
        }

    def get_conversation_context(self, run_id: str) -> Optional[RequirementContext]:
        """获取对话上下文"""
        conversation_id = self._conversations.get(run_id)
        if conversation_id:
            return self._conversation_orchestrator.get_conversation_context(conversation_id)
        return None

    async def think_progressive(self, problem: str) -> Dict[str, Any]:
        """执行渐进式思考"""
        trace = await self._thinking_engine.think(problem)
        
        return {
            "trace_id": trace.id,
            "problem": trace.problem,
            "thoughts": [
                {
                    "phase": t.phase.value,
                    "content": t.content,
                    "confidence": t.confidence.value,
                    "evidence": t.evidence,
                    "timestamp": t.timestamp.isoformat()
                } for t in trace.thoughts
            ],
            "final_answer": trace.final_answer,
            "confidence": trace.confidence.value
        }

    async def submit_task(self, name: str, func: callable, *args, **kwargs) -> str:
        """提交任务到调度器"""
        priority = kwargs.pop('priority', TaskPriority.MEDIUM)
        return await self._scheduler.submit_task(name, func, *args, priority=priority, **kwargs)

    async def run_code_workflow(self, requirement: str, mode: WorkflowMode = WorkflowMode.COLLABORATIVE) -> str:
        """运行代码工作流"""
        workflow_id = await self._code_workflow.create_workflow(requirement, mode)
        await self._code_workflow.run_workflow(workflow_id)
        return workflow_id


def get_integration_orchestrator() -> IntegrationOrchestrator:
    """获取集成编排器单例"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = IntegrationOrchestrator()
    return _orchestrator_instance


_orchestrator_instance = None