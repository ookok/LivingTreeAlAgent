"""
任务拆解技能集成测试（Trae SKILL 风格）
======================================

测试内容：
1. TaskDecomposer 增强功能测试
2. 任务拆解技能测试
3. SOLO Plan 管理器测试
4. TaskPlanner 增强功能测试

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

# 导入测试模块
from client.src.business.task_decomposer import (
    TaskDecomposer,
    ProcessType,
    create_architecture_task,
    create_refactoring_task,
    create_task_split_task,
)
from client.src.business.agent_skills.task_decomposition_skills import (
    ArchitectureDesignerSkill,
    CodeRefactorerSkill,
    TaskSplitterProSkill,
    DecompositionSkillFactory,
    register_decomposition_skills,
)
from client.src.business.solo_plan_manager import (
    SoloPlanManager,
    PlanMode,
    ExecutionPhase,
    create_solo_plan_manager,
)
from client.src.business.task_planning import (
    TaskPlanner,
    TaskTree,
    RiskLevel,
    create_task_planner,
)


class TestTaskDecomposerEnhancements:
    """TaskDecomposer 增强功能测试"""
    
    def test_architecture_template_exists(self):
        """测试架构设计模板存在"""
        decomposer = TaskDecomposer()
        assert "architecture" in decomposer.templates
        template = decomposer.templates["architecture"]
        assert template["name"] == "架构设计任务"
        assert template["max_steps"] == 5
        assert template["process_type"] == ProcessType.HIERARCHICAL
    
    def test_refactoring_template_exists(self):
        """测试代码重构模板存在"""
        decomposer = TaskDecomposer()
        assert "refactoring" in decomposer.templates
        template = decomposer.templates["refactoring"]
        assert template["name"] == "代码重构任务"
        assert template["max_steps"] == 4
        assert template["process_type"] == ProcessType.SEQUENTIAL
    
    def test_task_split_template_exists(self):
        """测试任务拆解模板存在"""
        decomposer = TaskDecomposer()
        assert "task_split" in decomposer.templates
        template = decomposer.templates["task_split"]
        assert template["name"] == "任务拆解任务"
        assert template["max_steps"] == 5
        assert template["process_type"] == ProcessType.HIERARCHICAL
    
    def test_detect_architecture_task(self):
        """测试自动检测架构设计任务"""
        decomposer = TaskDecomposer()
        task_type = decomposer.detect_task_type("设计微服务架构系统")
        assert task_type == "architecture"
    
    def test_detect_refactoring_task(self):
        """测试自动检测代码重构任务"""
        decomposer = TaskDecomposer()
        task_type = decomposer.detect_task_type("重构这段复杂代码")
        assert task_type == "refactoring"
    
    def test_detect_task_split_task(self):
        """测试自动检测任务拆解任务"""
        decomposer = TaskDecomposer()
        task_type = decomposer.detect_task_type("任务分解开发需求")
        assert task_type == "task_split"
    
    def test_create_architecture_task(self):
        """测试创建架构设计任务"""
        task = create_architecture_task("开发高可用电商系统")
        assert task is not None
        assert task.metadata.get("task_type") == "architecture"
        assert len(task.steps) == 5
        assert task.process_type == ProcessType.HIERARCHICAL
    
    def test_create_refactoring_task(self):
        """测试创建代码重构任务"""
        task = create_refactoring_task("优化订单处理代码")
        assert task is not None
        assert task.metadata.get("task_type") == "refactoring"
        assert len(task.steps) == 4
        assert task.process_type == ProcessType.SEQUENTIAL
    
    def test_create_task_split_task(self):
        """测试创建任务拆解任务"""
        task = create_task_split_task("开发在线教育系统")
        assert task is not None
        assert task.metadata.get("task_type") == "task_split"
        assert len(task.steps) == 5
        assert task.process_type == ProcessType.HIERARCHICAL


class TestDecompositionSkills:
    """任务拆解技能测试"""
    
    def test_architecture_designer_skill(self):
        """测试架构设计技能"""
        skill = ArchitectureDesignerSkill()
        manifest = skill.get_manifest()
        
        assert manifest.id == "architecture_designer"
        assert manifest.name == "架构设计与系统规划"
        assert manifest.priority == 9
        assert "微服务架构" in manifest.trigger_phrases
        
        # 测试激活技能
        task = skill.activate("开发百万级并发系统")
        assert task is not None
        assert len(task.steps) == 5
    
    def test_code_refactorer_skill(self):
        """测试代码重构技能"""
        skill = CodeRefactorerSkill()
        manifest = skill.get_manifest()
        
        assert manifest.id == "code_refactorer"
        assert manifest.name == "代码重构与优化"
        assert manifest.priority == 8
        assert "重构" in manifest.trigger_phrases
        
        # 测试激活技能
        task = skill.activate("优化这段复杂代码")
        assert task is not None
        assert len(task.steps) == 4
    
    def test_task_splitter_skill(self):
        """测试任务拆解技能"""
        skill = TaskSplitterProSkill()
        manifest = skill.get_manifest()
        
        assert manifest.id == "task_splitter_pro"
        assert manifest.name == "智能任务拆解大师"
        assert manifest.priority == 8
        assert "拆解任务" in manifest.trigger_phrases
        
        # 测试激活技能
        task = skill.activate("开发在线教育管理系统")
        assert task is not None
        assert len(task.steps) == 5
    
    def test_skill_factory(self):
        """测试技能工厂"""
        from client.src.business.agent_skills.task_decomposition_skills import (
            DecompositionSkillType,
            get_architecture_designer,
            get_code_refactorer,
            get_task_splitter,
        )
        
        # 测试获取技能
        arch_skill = get_architecture_designer()
        assert isinstance(arch_skill, ArchitectureDesignerSkill)
        
        ref_skill = get_code_refactorer()
        assert isinstance(ref_skill, CodeRefactorerSkill)
        
        split_skill = get_task_splitter()
        assert isinstance(split_skill, TaskSplitterProSkill)
    
    def test_register_decomposition_skills(self):
        """测试注册所有拆解技能"""
        from client.src.business.agent_skills.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        register_decomposition_skills(registry)
        
        stats = registry.get_stats()
        assert stats["total_skills"] >= 3


class TestSoloPlanManager:
    """SOLO Plan 管理器测试"""
    
    def test_create_plan_manager(self):
        """测试创建 Plan 管理器"""
        manager = create_solo_plan_manager()
        assert isinstance(manager, SoloPlanManager)
        assert not manager.plan_mode
    
    def test_enter_exit_plan_mode(self):
        """测试进入/退出 Plan 模式"""
        manager = SoloPlanManager()
        
        # 进入 Plan 模式
        manager.enter_plan_mode()
        assert manager.plan_mode
        
        # 退出 Plan 模式
        manager.exit_plan_mode()
        assert not manager.plan_mode
    
    def test_start_new_session(self):
        """测试开始新会话"""
        manager = SoloPlanManager()
        session = manager.start_new_session("开发电商系统")
        
        assert session is not None
        assert session.session_id is not None
        assert session.requirement == "开发电商系统"
        assert session.mode == PlanMode.PLANNING
        assert session.phase == ExecutionPhase.DECOMPOSITION
    
    def test_select_decomposition_skill(self):
        """测试智能选择拆解技能"""
        manager = SoloPlanManager()
        
        # 测试架构设计
        skill = manager.select_decomposition_skill("设计微服务架构")
        assert isinstance(skill, ArchitectureDesignerSkill)
        
        # 测试代码重构
        skill = manager.select_decomposition_skill("重构复杂代码")
        assert isinstance(skill, CodeRefactorerSkill)
        
        # 测试任务拆解（默认）
        skill = manager.select_decomposition_skill("开发新项目")
        assert isinstance(skill, TaskSplitterProSkill)
    
    def test_decompose_task(self):
        """测试拆解任务"""
        manager = SoloPlanManager()
        manager.start_new_session("开发高可用系统")
        
        task = manager.decompose_task("开发高可用系统")
        assert task is not None
        assert manager.current_session.decomposed_task == task
        assert manager.current_session.phase == ExecutionPhase.REVIEW


class TestTaskPlannerEnhancements:
    """TaskPlanner 增强功能测试"""
    
    def test_create_task_planner(self):
        """测试创建任务规划器"""
        planner = create_task_planner()
        assert isinstance(planner, TaskPlanner)
    
    def test_risk_detection(self):
        """测试风险检测"""
        planner = TaskPlanner()
        
        # 测试高风险检测
        risk = planner._detect_risk("对接第三方支付接口")
        assert risk is not None
        assert risk.level == RiskLevel.CRITICAL
        
        # 测试中等风险检测
        risk = planner._detect_risk("使用新技术开发功能")
        assert risk is not None
        assert risk.level == RiskLevel.HIGH
        
        # 测试低风险
        risk = planner._detect_risk("编写单元测试")
        assert risk is None
    
    def test_generate_acceptance_criteria(self):
        """测试生成验收标准"""
        planner = TaskPlanner()
        
        criteria = planner._generate_acceptance_criteria(
            "开发用户登录接口",
            "实现用户登录功能"
        )
        
        assert criteria is not None
        assert len(criteria.criteria) > 0
        assert "接口测试通过" in criteria.criteria
    
    @pytest.mark.asyncio
    async def test_decompose_with_trae_skill(self):
        """测试使用 Trae 技能拆解任务"""
        planner = TaskPlanner()
        
        task_tree = await planner.decompose_with_trae_skill("开发在线教育系统")
        
        assert task_tree is not None
        assert isinstance(task_tree, TaskTree)
        assert len(task_tree.tasks) > 1  # 至少有根任务和子任务
        assert len(task_tree.phases) > 0
    
    def test_calculate_critical_path(self):
        """测试计算关键路径"""
        planner = TaskPlanner()
        
        # 创建简单任务树
        from client.src.business.task_planning import Task, TaskType, TaskStatus
        
        root_task = Task(
            id="root",
            title="测试任务",
            description="测试任务",
            task_type=TaskType.OTHER,
            priority=10
        )
        
        task1 = Task(
            id="task1",
            title="核心任务",
            description="核心功能开发",
            task_type=TaskType.CODE_GENERATION,
            priority=10
        )
        
        task2 = Task(
            id="task2",
            title="次要任务",
            description="次要功能开发",
            task_type=TaskType.CODE_GENERATION,
            priority=5
        )
        
        task_tree = TaskTree(
            root_task=root_task,
            tasks={"root": root_task, "task1": task1, "task2": task2}
        )
        
        critical_path = planner._calculate_critical_path(task_tree)
        assert "task1" in critical_path
        assert "root" in critical_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])