"""
Agent Skills 初始化
=================

将所有 Agent Skills 注册到系统中，并集成到现有工作流

自动集成 Trae 任务拆解 SKILL：
- ArchitectureDesignerSkill（架构设计与系统规划）
- CodeRefactorerSkill（代码重构与优化）
- TaskSplitterProSkill（智能任务拆解大师）
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from client.src.business.agent_skills.skill_registry import SkillRegistry, SkillManifest, SkillCategory
from client.src.business.agent_skills.skill_loader import SkillLoader
from client.src.business.agent_skills.skill_executor import SkillExecutor
from client.src.business.agent_skills.slash_commands import SlashCommandRegistry, SlashCommand
from client.src.business.agent_skills.context_aware import ContextAwareLoader
from client.src.business.agent_skills.workflows.spec_driven import SpecDrivenWorkflow
from client.src.business.agent_skills.workflows.test_driven import TestDrivenWorkflow
from client.src.business.agent_skills.workflows.code_review import CodeReviewWorkflow
from client.src.business.agent_skills.workflows.security import SecurityWorkflow
from client.src.business.agent_skills.task_decomposition_skills import (
    DecompositionSkillFactory,
    register_decomposition_skills,
    get_architecture_designer,
    get_code_refactorer,
    get_task_splitter,
)

logger = logging.getLogger(__name__)


class AgentSkillsInitializer:
    """
    Agent Skills 初始化器
    
    负责：
    1. 注册所有技能
    2. 配置斜杠命令
    3. 设置上下文感知加载
    4. 绑定到工作流引擎
    """
    
    def __init__(self):
        self.registry = SkillRegistry()
        self.loader = SkillLoader()
        self.executor = SkillExecutor(self.registry)
        self.slash_commands = SlashCommandRegistry()
        self.context_loader = ContextAwareLoader(self.registry)
        
    def initialize(self) -> Dict[str, Any]:
        """
        初始化所有 Agent Skills
        
        Returns:
            初始化结果
        """
        try:
            # 1. 注册内置技能
            self._register_builtin_skills()
            
            # 2. 自动注册 Trae 任务拆解技能（新增）
            self._register_decomposition_skills()
            
            # 3. 加载 Markdown 技能文件
            self._load_markdown_skills()
            
            # 4. 配置斜杠命令（包含拆解技能）
            self._setup_slash_commands()
            
            # 5. 注册工作流处理器（包含拆解技能）
            self._register_workflow_handlers()
            
            logger.info("[AgentSkills] 初始化完成")
            
            return {
                "success": True,
                "skills_registered": len(self.registry.list_skills()),
                "commands_registered": len(self.slash_commands.list_commands()),
            }
            
        except Exception as e:
            logger.error(f"[AgentSkills] 初始化失败: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def _register_decomposition_skills(self):
        """
        自动注册 Trae 任务拆解技能
        
        包括：
        - ArchitectureDesignerSkill（架构设计与系统规划）
        - CodeRefactorerSkill（代码重构与优化）
        - TaskSplitterProSkill（智能任务拆解大师）
        """
        logger.info("[AgentSkills] 注册 Trae 任务拆解技能")
        
        # 使用工厂函数注册所有拆解技能
        register_decomposition_skills(self.registry)
        
        # 验证注册结果
        arch_skill = get_architecture_designer()
        ref_skill = get_code_refactorer()
        split_skill = get_task_splitter()
        
        logger.info(f"[AgentSkills] 已注册拆解技能: {arch_skill.get_manifest().name}, {ref_skill.get_manifest().name}, {split_skill.get_manifest().name}")
    
    def _register_builtin_skills(self):
        """注册内置技能"""
        builtin_skills = [
            SkillManifest(
                id="spec-driven-development",
                name="Spec-Driven Development",
                description="从规格说明到实现的完整开发流程",
                category=SkillCategory.PLANNING,
                trigger_phrases=["spec", "specification", "规格", "需求"],
                priority=10,
            ),
            SkillManifest(
                id="test-driven-development",
                name="Test-Driven Development",
                description="测试驱动开发工作流",
                category=SkillCategory.TESTING,
                trigger_phrases=["test", "tdd", "测试"],
                priority=9,
            ),
            SkillManifest(
                id="code-review",
                name="Code Review & Quality",
                description="代码审查和质量检查",
                category=SkillCategory.REVIEW,
                trigger_phrases=["review", "审查", "质量"],
                priority=8,
            ),
            SkillManifest(
                id="security-hardening",
                name="Security & Hardening",
                description="安全加固和最佳实践",
                category=SkillCategory.SECURITY,
                trigger_phrases=["security", "安全", "加固"],
                priority=8,
            ),
            SkillManifest(
                id="frontend-ui-engineering",
                name="Frontend UI Engineering",
                description="前端 UI 工程最佳实践",
                category=SkillCategory.UI_UX,
                trigger_phrases=["frontend", "ui", "前端", "组件"],
                priority=7,
            ),
            SkillManifest(
                id="api-design",
                name="API & Interface Design",
                description="API 和接口设计最佳实践",
                category=SkillCategory.DEVELOPMENT,
                trigger_phrases=["api", "接口", "设计"],
                priority=7,
            ),
        ]
        
        for skill in builtin_skills:
            self.registry.register(skill)
            
    def _load_markdown_skills(self):
        """从 Markdown 文件加载技能"""
        skills_data = self.loader.load_all_skills()
        
        for skill_id, data in skills_data.items():
            metadata = data.get("metadata", {})
            content = data.get("content", "")
            
            manifest = SkillManifest(
                id=skill_id,
                name=metadata.get("name", skill_id),
                description=metadata.get("description", ""),
                category=SkillCategory(metadata.get("category", "development")),
                trigger_phrases=metadata.get("trigger_phrases", []),
                priority=metadata.get("priority", 5),
            )
            
            self.registry.register(manifest, content)
            
    def _setup_slash_commands(self):
        """配置斜杠命令"""
        commands = [
            SlashCommand(
                command="spec",
                description="启动 Spec 驱动开发工作流",
                handler=self._handle_spec_command,
                skill_id="spec-driven-development",
                category="development",
            ),
            SlashCommand(
                command="test",
                description="启动测试驱动开发工作流",
                handler=self._handle_test_command,
                skill_id="test-driven-development",
                category="testing",
            ),
            SlashCommand(
                command="review",
                description="启动代码审查工作流",
                handler=self._handle_review_command,
                skill_id="code-review",
                category="review",
            ),
            SlashCommand(
                command="security",
                description="启动安全审查工作流",
                handler=self._handle_security_command,
                skill_id="security-hardening",
                category="security",
            ),
            SlashCommand(
                command="skills",
                description="列出所有可用技能",
                handler=self._handle_skills_list_command,
                category="general",
            ),
            # Trae 任务拆解技能斜杠命令（新增）
            SlashCommand(
                command="arch",
                description="激活架构设计与系统规划 SKILL",
                handler=self._handle_arch_command,
                skill_id="architecture_designer",
                category="planning",
            ),
            SlashCommand(
                command="refactor",
                description="激活代码重构与优化 SKILL",
                handler=self._handle_refactor_command,
                skill_id="code_refactorer",
                category="development",
            ),
            SlashCommand(
                command="decompose",
                description="激活智能任务拆解大师 SKILL",
                handler=self._handle_decompose_command,
                skill_id="task_splitter_pro",
                category="planning",
            ),
            SlashCommand(
                command="plan",
                description="进入 SOLO Plan 模式",
                handler=self._handle_plan_command,
                category="planning",
            ),
        ]
        
        for cmd in commands:
            self.slash_commands.register(cmd)
            
    def _register_workflow_handlers(self):
        """注册工作流处理器"""
        # 注册 Spec 驱动工作流
        spec_workflow = SpecDrivenWorkflow()
        async def spec_handler(ctx, content):
            return await spec_workflow.execute(ctx)
        self.executor.register_handler("spec-driven-development", spec_handler)
        
        # 注册测试驱动工作流
        test_workflow = TestDrivenWorkflow()
        async def test_handler(ctx, content):
            return await test_workflow.execute(ctx)
        self.executor.register_handler("test-driven-development", test_handler)
        
        # 注册代码审查工作流
        review_workflow = CodeReviewWorkflow()
        async def review_handler(ctx, content):
            return await review_workflow.execute(ctx)
        self.executor.register_handler("code-review", review_handler)
        
        # 注册安全加固工作流
        security_workflow = SecurityWorkflow()
        async def security_handler(ctx, content):
            return await security_workflow.execute(ctx)
        self.executor.register_handler("security-hardening", security_handler)
        
    # ─── 斜杠命令处理器 ──────────────────────────────────
    
    def _handle_spec_command(self, args: Dict) -> Dict:
        """处理 /spec 命令"""
        return {
            "command": "/spec",
            "action": "启动 Spec 驱动开发工作流",
            "skill_id": "spec-driven-development",
            "status": "ready",
        }
    
    def _handle_test_command(self, args: Dict) -> Dict:
        """处理 /test 命令"""
        return {
            "command": "/test",
            "action": "启动测试驱动开发工作流",
            "skill_id": "test-driven-development",
            "status": "ready",
        }
    
    def _handle_review_command(self, args: Dict) -> Dict:
        """处理 /review 命令"""
        return {
            "command": "/review",
            "action": "启动代码审查工作流",
            "skill_id": "code-review",
            "status": "ready",
        }
    
    def _handle_security_command(self, args: Dict) -> Dict:
        """处理 /security 命令"""
        return {
            "command": "/security",
            "action": "启动安全审查工作流",
            "skill_id": "security-hardening",
            "status": "ready",
        }
    
    def _handle_skills_list_command(self, args: Dict) -> Dict:
        """处理 /skills 命令"""
        skills = self.registry.list_skills()
        return {
            "command": "/skills",
            "total": len(skills),
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "category": s.category.value,
                }
                for s in skills
            ],
        }
    
    # ─── Trae 任务拆解技能命令处理器（新增）───────────────────────────
    
    def _handle_arch_command(self, args: Dict) -> Dict:
        """处理 /arch 命令 - 激活架构设计与系统规划 SKILL"""
        skill = get_architecture_designer()
        manifest = skill.get_manifest()
        return {
            "command": "/arch",
            "action": f"激活【{manifest.name}】SKILL",
            "skill_id": manifest.id,
            "description": manifest.description,
            "examples": manifest.examples,
            "status": "ready",
        }
    
    def _handle_refactor_command(self, args: Dict) -> Dict:
        """处理 /refactor 命令 - 激活代码重构与优化 SKILL"""
        skill = get_code_refactorer()
        manifest = skill.get_manifest()
        return {
            "command": "/refactor",
            "action": f"激活【{manifest.name}】SKILL",
            "skill_id": manifest.id,
            "description": manifest.description,
            "examples": manifest.examples,
            "status": "ready",
        }
    
    def _handle_decompose_command(self, args: Dict) -> Dict:
        """处理 /decompose 命令 - 激活智能任务拆解大师 SKILL"""
        skill = get_task_splitter()
        manifest = skill.get_manifest()
        return {
            "command": "/decompose",
            "action": f"激活【{manifest.name}】SKILL",
            "skill_id": manifest.id,
            "description": manifest.description,
            "examples": manifest.examples,
            "status": "ready",
        }
    
    def _handle_plan_command(self, args: Dict) -> Dict:
        """处理 /plan 命令 - 进入 SOLO Plan 模式"""
        from client.src.business.solo_plan_manager import get_solo_plan_manager
        
        manager = get_solo_plan_manager()
        manager.enter_plan_mode()
        
        return {
            "command": "/plan",
            "action": "进入 SOLO Plan 模式",
            "status": "plan_mode_active",
            "tips": [
                "Plan 模式下禁止直接执行代码",
                "使用 /arch /refactor /decompose 激活拆解技能",
                "拆解完成后审阅修改",
                "分步执行并验收",
            ],
        }
    
    # ─── 辅助方法 ──────────────────────────────────
    
    def get_registry(self) -> SkillRegistry:
        """获取技能注册中心"""
        return self.registry
    
    def get_executor(self) -> SkillExecutor:
        """获取技能执行引擎"""
        return self.executor
    
    def get_slash_commands(self) -> SlashCommandRegistry:
        """获取斜杠命令注册中心"""
        return self.slash_commands
    
    def get_context_loader(self) -> ContextAwareLoader:
        """获取上下文感知加载器"""
        return self.context_loader
