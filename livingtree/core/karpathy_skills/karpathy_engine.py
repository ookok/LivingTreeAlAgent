"""
Karpathy Skills 核心引擎

基于 Andrej Karpathy 的编程最佳实践
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid

from .skill_configs import get_karpathy_registry
from .workflow import get_karpathy_workflow
from .integration import get_karpathy_integration


class KarpathyMode(Enum):
    """Karpathy 模式"""
    STANDARD = "standard"      # 标准模式
    STRICT = "strict"          # 严格模式
    PERFORMANCE = "performance"  # 性能模式


@dataclass
class KarpathyConfig:
    """Karpathy 配置"""
    mode: KarpathyMode = KarpathyMode.STANDARD
    skill_timeout: int = 600  # 10分钟
    review_depth: str = "deep"  # deep, medium, shallow
    test_coverage: str = "comprehensive"  # comprehensive, basic
    refactor_level: str = "suggestive"  # aggressive, suggestive, conservative
    workspace_dir: str = ".karpathy"


class KarpathyEngine:
    """
    Karpathy 核心引擎

    协调 Karpathy 技能的执行
    """

    def __init__(self, config: Optional[KarpathyConfig] = None):
        self.config = config or KarpathyConfig()
        self.workspace_dir = Path(self.config.workspace_dir)
        self.registry = get_karpathy_registry()
        self.workflow = get_karpathy_workflow()
        self.integration = get_karpathy_integration()
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._setup_workspace()

    def _setup_workspace(self):
        """设置工作空间"""
        dirs = [
            self.workspace_dir,
            self.workspace_dir / "skills",
            self.workspace_dir / "reviews",
            self.workspace_dir / "tests",
            self.workspace_dir / "refactors",
            self.workspace_dir / "docs",
            self.workspace_dir / "configs",
        ]

        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """初始化 Karpathy 引擎"""
        # 注册预设技能
        await self._register_default_skills()
        
        # 初始化工作流
        await self.workflow.initialize()
        
        # 初始化集成
        await self.integration.initialize()

        print(f"[KarpathyEngine] 初始化完成，模式: {self.config.mode.value}")

    async def _register_default_skills(self):
        """注册默认技能"""
        from .skill_configs import (
            CodeReviewSkill,
            TestGeneratorSkill,
            RefactorAdvisorSkill,
            DocWriterSkill,
            PerformanceOptimizerSkill
        )

        skills = [
            CodeReviewSkill(),
            TestGeneratorSkill(),
            RefactorAdvisorSkill(),
            DocWriterSkill(),
            PerformanceOptimizerSkill()
        ]

        for skill in skills:
            await self.registry.register_skill(skill)
            print(f"[KarpathyEngine] 注册技能: {skill.name}")

    async def execute_skill(
        self,
        skill_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行技能

        Args:
            skill_name: 技能名称
            parameters: 技能参数

        Returns:
            Dict: 执行结果
        """
        return await self.registry.execute_skill(skill_name, parameters or {})

    async def run_workflow(
        self,
        workflow_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        运行工作流

        Args:
            workflow_name: 工作流名称
            parameters: 工作流参数

        Returns:
            Dict: 工作流执行结果
        """
        return await self.workflow.run(workflow_name, parameters or {})

    async def code_review(
        self,
        code: str,
        language: Optional[str] = None,
        depth: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        代码审查

        Args:
            code: 代码
            language: 语言
            depth: 审查深度

        Returns:
            Dict: 审查结果
        """
        parameters = {
            "code": code,
            "language": language,
            "depth": depth or self.config.review_depth
        }
        return await self.execute_skill("code_review", parameters)

    async def generate_tests(
        self,
        code: str,
        language: Optional[str] = None,
        coverage: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成测试

        Args:
            code: 代码
            language: 语言
            coverage: 测试覆盖度

        Returns:
            Dict: 测试生成结果
        """
        parameters = {
            "code": code,
            "language": language,
            "coverage": coverage or self.config.test_coverage
        }
        return await self.execute_skill("test_generator", parameters)

    async def get_refactor_suggestions(
        self,
        code: str,
        language: Optional[str] = None,
        level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取重构建议

        Args:
            code: 代码
            language: 语言
            level: 重构级别

        Returns:
            Dict: 重构建议
        """
        parameters = {
            "code": code,
            "language": language,
            "level": level or self.config.refactor_level
        }
        return await self.execute_skill("refactor_advisor", parameters)

    async def generate_docs(
        self,
        code: str,
        language: Optional[str] = None,
        style: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成文档

        Args:
            code: 代码
            language: 语言
            style: 文档风格

        Returns:
            Dict: 文档生成结果
        """
        parameters = {
            "code": code,
            "language": language,
            "style": style or "standard"
        }
        return await self.execute_skill("doc_writer", parameters)

    async def optimize_performance(
        self,
        code: str,
        language: Optional[str] = None,
        target: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        性能优化

        Args:
            code: 代码
            language: 语言
            target: 优化目标

        Returns:
            Dict: 性能优化建议
        """
        parameters = {
            "code": code,
            "language": language,
            "target": target or "speed"
        }
        return await self.execute_skill("performance_optimizer", parameters)

    async def analyze_codebase(
        self,
        codebase_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分析代码库

        Args:
            codebase_path: 代码库路径
            options: 分析选项

        Returns:
            Dict: 分析结果
        """
        return await self.run_workflow("codebase_analysis", {
            "codebase_path": codebase_path,
            "options": options or {}
        })

    def get_skills(self) -> List[str]:
        """
        获取所有技能

        Returns:
            List[str]: 技能列表
        """
        return self.registry.get_skills()

    def get_workflows(self) -> List[str]:
        """
        获取所有工作流

        Returns:
            List[str]: 工作流列表
        """
        return self.workflow.get_workflows()

    def get_config(self) -> KarpathyConfig:
        """
        获取配置

        Returns:
            KarpathyConfig: 配置
        """
        return self.config

    def update_config(self, **kwargs):
        """
        更新配置

        Args:
            **kwargs: 配置参数
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    async def _emit(self, event: str, *args):
        """触发事件"""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args)
                else:
                    handler(*args)
            except Exception as e:
                print(f"[KarpathyEngine] Event handler error: {e}")

    def shutdown(self):
        """关闭引擎"""
        print("[KarpathyEngine] 正在关闭...")
        # 清理资源
        print("[KarpathyEngine] 已关闭")


_global_engine: Optional[KarpathyEngine] = None


def get_karpathy_engine(config: Optional[KarpathyConfig] = None) -> KarpathyEngine:
    """获取 Karpathy 引擎"""
    global _global_engine
    if _global_engine is None:
        _global_engine = KarpathyEngine(config)
    return _global_engine


def create_karpathy_config(**kwargs) -> KarpathyConfig:
    """创建 Karpathy 配置"""
    return KarpathyConfig(**kwargs)