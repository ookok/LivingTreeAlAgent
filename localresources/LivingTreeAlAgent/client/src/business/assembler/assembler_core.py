"""
根系装配园核心 (Root Assembly Garden Core)

生命之树命名法典 — 根系装配园

七阶嫁接管线：
1. 良种搜寻台 (Seed Scouting Table) - 需求解析
2. 良种雷达 (Seed Radar) - 库发现
3. 亲和试验台 (Affinity Test Bench) - 冲突检测
4. 园丁指挥台 (Gardener Command) - 用户决策
5. 育苗温床 (Sapling Bed) - 沙箱安装
6. 萌芽试炼场 (Sprout Trial Ground) - 测试验证
7. 扎根部署 (Rooting Deploy) - 动态上线
"""

import asyncio
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum

from .navigator import StarNavigator, RequirementSpec, InputType
from .radar import OSSRadar, RepoInfo
from .conflict import ConflictDetector, ConflictReport, ResolutionStrategy
from .isolation_bay import IsolationBay, LanguageType, InstallationResult
from .adapter_gen import AdapterGenerator, ToolContract
from .proving_grounds import ProvingGrounds, TestSuiteResult, TestStatus
from .deployment_bay import DeploymentBay, DeployedModule, DeployStatus


class AssemblyStage(Enum):
    """七阶嫁接阶段"""
    SEED_SCOUTING = "良种搜寻"           # 原：星图导航仪
    SEED_RADAR = "良种雷达"             # 原：开源雷达
    AFFINITY_TEST = "亲和试验"          # 原：战术评估
    GARDENER_COMMAND = "园丁裁决"       # 原：指挥官决策
    SAPLING_BED = "育苗温床"            # 原：隔离舱
    SPROUT_TRIAL = "萌芽试炼"           # 原：试射靶场
    ROOTING_DEPLOY = "扎根部署"         # 原：挂载部署
    COMPLETE = "嫁接完成"


@dataclass
class AssemblySession:
    """装配会话"""
    session_id: str
    requirement: Optional[RequirementSpec] = None
    candidate_repos: list[RepoInfo] = field(default_factory=list)
    selected_repo: Optional[RepoInfo] = None
    conflict_report: Optional[ConflictReport] = None
    resolution_strategy: ResolutionStrategy = ResolutionStrategy.COEXIST
    installation_result: Optional[InstallationResult] = None
    test_result: Optional[TestSuiteResult] = None
    deployed_module: Optional[DeployedModule] = None

    # 状态
    current_stage: AssemblyStage = AssemblyStage.SEED_SCOUTING
    is_running: bool = False
    error_message: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "current_stage": self.current_stage.value,
            "is_running": self.is_running,
            "requirement": self.requirement.to_dict() if self.requirement else None,
            "candidate_repos": [r.to_dict() for r in self.candidate_repos],
            "selected_repo": self.selected_repo.to_dict() if self.selected_repo else None,
            "conflict_report": self.conflict_report.to_dict() if self.conflict_report else None,
            "resolution_strategy": self.resolution_strategy.value,
            "installation_result": self.installation_result.to_dict() if self.installation_result else None,
            "test_result": self.test_result.get_summary() if self.test_result else None,
            "deployed_module": self.deployed_module.to_dict() if self.deployed_module else None,
            "error_message": self.error_message,
        }


class RootAssemblyGarden:
    """根系装配园核心"""

    _instance: Optional['StardockAssembler'] = None

    def __init__(self):
        # 组件
        self.navigator = StarNavigator()
        self.radar = OSSRadar()
        self.conflict_detector = ConflictDetector()
        self.isolation_bay = IsolationBay()
        self.adapter_generator = AdapterGenerator()
        self.proving_grounds = ProvingGrounds()
        self.deployment_bay = DeploymentBay()

        # 会话管理
        self._sessions: dict[str, AssemblySession] = {}
        self._callbacks: dict[str, list[Callable]] = {}

    @classmethod
    def get_instance(cls) -> 'StardockAssembler':
        """获取单例"""
        if cls._instance is None:
            cls._instance = StardockAssembler()
        return cls._instance

    # ==================== 回调管理 ====================

    def register_callback(
        self,
        session_id: str,
        callback: Callable
    ):
        """注册会话回调"""
        if session_id not in self._callbacks:
            self._callbacks[session_id] = []
        self._callbacks[session_id].append(callback)

    async def _emit(self, session_id: str, event: str, data: Any):
        """触发回调"""
        if session_id in self._callbacks:
            for cb in self._callbacks[session_id]:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(event, data)
                    else:
                        cb(event, data)
                except Exception:
                    pass

    # ==================== 会话管理 ====================

    def create_session(self) -> AssemblySession:
        """创建装配会话"""
        import uuid
        session_id = f"asm_{uuid.uuid4().hex[:8]}"
        session = AssemblySession(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[AssemblySession]:
        """获取会话"""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str):
        """关闭会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._callbacks:
            del self._callbacks[session_id]

    # ==================== 七阶装配管线 ====================

    async def run_assembly(
        self,
        session_id: str,
        user_input: str,
        auto_resolve: bool = True,
        progress_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None
    ) -> AssemblySession:
        """
        运行完整装配流程

        Args:
            session_id: 会话ID
            user_input: 用户输入
            auto_resolve: 是否自动解决冲突
            progress_callback: 进度回调
            log_callback: 日志回调

        Returns:
            AssemblySession: 装配结果
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        session.is_running = True

        try:
            # 阶段1: 星图导航仪
            await self._stage_navigator(session, user_input, progress_callback, log_callback)

            # 阶段2: 开源雷达
            await self._stage_radar(session, progress_callback, log_callback)

            # 阶段3: 亲和试验
            await self._stage_conflict(session, progress_callback, log_callback)

            # 检查冲突
            if session.conflict_report and session.conflict_report.has_conflict:
                if not auto_resolve:
                    session.current_stage = AssemblyStage.GARDENER_COMMAND
                    await self._emit(session_id, "await_decision", session)
                    return session  # 等待园丁裁决
                else:
                    # 自动选择策略
                    session.resolution_strategy = session.conflict_report.recommended_strategy

            # 阶段4: 育苗温床
            await self._stage_isolation(session, progress_callback, log_callback)

            # 阶段5: 萌芽试炼
            await self._stage_proving(session, progress_callback, log_callback)

            # 检查测试结果
            if session.test_result and not session.test_result.is_all_passed():
                if log_callback:
                    await log_callback("⚠️ 测试未全部通过，可选择回滚或继续部署")
                # 继续部署但不标记为成功

            # 阶段6: 挂载部署
            await self._stage_deployment(session, progress_callback, log_callback)

            session.current_stage = AssemblyStage.COMPLETE

        except Exception as e:
            session.error_message = str(e)
            session.is_running = False

        session.is_running = False
        await self._emit(session_id, "assembly_complete", session)
        return session

    async def resolve_and_continue(
        self,
        session_id: str,
        strategy: ResolutionStrategy
    ) -> AssemblySession:
        """用户决策后继续装配"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        session.resolution_strategy = strategy
        session.current_stage = AssemblyStage.SAPLING_BED

        try:
            # 继续隔离舱安装
            await self._stage_isolation(session, None, None)

            # 继续测试
            await self._stage_proving(session, None, None)

            # 继续部署
            await self._stage_deployment(session, None, None)

            session.current_stage = AssemblyStage.COMPLETE

        except Exception as e:
            session.error_message = str(e)

        session.is_running = False
        await self._emit(session_id, "assembly_complete", session)
        return session

    # ==================== 各阶段实现 ====================

    async def _stage_navigator(
        self,
        session: AssemblySession,
        user_input: str,
        progress: Optional[Callable],
        log: Optional[Callable]
    ):
        """阶段1: 星图导航仪"""
        if progress:
            await progress("📍 阶段1/6: 星图导航仪 - 解析需求...")

        if log:
            await log("\n" + "="*50)
            await log("📍 星图导航仪")
            await log(f"   输入: {user_input}")

        session.requirement = self.navigator.parse(user_input)

        if log:
            spec = session.requirement
            await log(f"   解析结果:")
            await log(f"   - 类型: {spec.input_type.value}")
            await log(f"   - 功能: {', '.join(spec.features)}")
            await log(f"   - 语言: {', '.join([l.value for l in spec.languages])}")
            await log(f"   - 约束: {', '.join(spec.constraints) or '无'}")

        session.current_stage = AssemblyStage.SEED_RADAR

    async def _stage_radar(
        self,
        session: AssemblySession,
        progress: Optional[Callable],
        log: Optional[Callable]
    ):
        """阶段2: 开源雷达"""
        if progress:
            await progress("🔍 阶段2/6: 开源雷达 - 搜索候选库...")

        if log:
            await log("\n" + "="*50)
            await log("🔍 开源雷达")

        query = self.navigator.spec_to_query(session.requirement)

        # 确定语言
        language = None
        if session.requirement.languages:
            for lang in session.requirement.languages:
                if lang.value != "unknown":
                    language = lang.value
                    break

        if log:
            await log(f"   查询: {query}")
            await log(f"   语言: {language or '不限'}")

        # 搜索
        session.candidate_repos = await self.radar.discover(
            query=query,
            language=language,
            max_results=5
        )

        if log:
            await log(f"   发现 {len(session.candidate_repos)} 个候选库")
            for i, repo in enumerate(session.candidate_repos[:3], 1):
                await log(f"   {i}. {repo.name} ({repo.stars}⭐)")

        # 自动选择第一个
        if session.candidate_repos:
            session.selected_repo = session.candidate_repos[0]

        session.current_stage = AssemblyStage.AFFINITY_TEST

    async def _stage_conflict(
        self,
        session: AssemblySession,
        progress: Optional[Callable],
        log: Optional[Callable]
    ):
        """阶段3: 战术评估"""
        if progress:
            await progress("⚠️ 阶段3/6: 战术评估 - 检测冲突...")

        if log:
            await log("\n" + "="*50)
            await log("⚠️ 战术评估")

        # 提取外部库标签
        external_tags = session.requirement.features.copy()
        if session.selected_repo:
            external_tags.append(session.selected_repo.language.lower())

        session.conflict_report = self.conflict_detector.detect(
            external_tags=external_tags,
            external_name=session.selected_repo.name if session.selected_repo else "unknown"
        )

        if log:
            if session.conflict_report.has_conflict:
                await log("   ⚠️ 检测到亲和性问题!")
                await log(session.conflict_report.summary)
            else:
                await log("   ✅ 亲和性良好，可直接嫁接")

        session.current_stage = AssemblyStage.AFFINITY_TEST

    async def _stage_isolation(
        self,
        session: AssemblySession,
        progress: Optional[Callable],
        log: Optional[Callable]
    ):
        """阶段4: 隔离舱"""
        if progress:
            await progress("📦 阶段4/6: 隔离舱 - 安装模块...")

        if log:
            await log("\n" + "="*50)
            await log("📦 隔离舱安装")

        if not session.selected_repo:
            raise ValueError("未选择候选库")

        # 确定语言类型
        lang_type = LanguageType.PYTHON
        if session.selected_repo.language.lower() in ("javascript", "typescript"):
            lang_type = LanguageType.JAVASCRIPT
        elif session.selected_repo.language.lower() == "go":
            lang_type = LanguageType.GO

        if log:
            await log(f"   目标: {session.selected_repo.name}")
            await log(f"   语言: {lang_type.value}")
            await log(f"   策略: {session.resolution_strategy.value}")

        session.installation_result = await self.isolation_bay.install(
            module_name=session.selected_repo.name,
            repo_url=session.selected_repo.url,
            language=lang_type,
            progress_callback=log
        )

        if log:
            if session.installation_result.success:
                await log(f"   ✅ 嫁接成功")
                await log(f"   入口: {session.installation_result.entry_point}")
            else:
                await log(f"   ❌ 嫁接失败: {session.installation_result.error_message}")

        session.current_stage = AssemblyStage.SPROUT_TRIAL

    async def _stage_proving(
        self,
        session: AssemblySession,
        progress: Optional[Callable],
        log: Optional[Callable]
    ):
        """阶段5: 萌芽试炼"""
        if progress:
            await progress("🌱 阶段5/6: 萌芽试炼 - 验证新苗...")

        if log:
            await log("\n" + "="*50)
            await log("🧪 试射靶场")

        if not session.selected_repo:
            raise ValueError("未选择候选库")

        # 创建测试套件
        suite = self.proving_grounds.create_test_suite(
            module_name=session.selected_repo.name,
            repo_info=session.selected_repo.to_dict(),
            installation_result=session.installation_result.to_dict() if session.installation_result else {}
        )

        # 运行测试
        session.test_result = await self.proving_grounds.run_test_suite(
            module_name=session.selected_repo.name,
            progress_callback=log,
            log_callback=log
        )

        if log:
            summary = suite.get_summary()
            await log(f"\n📊 试炼结果: {summary['passed']}/{summary['total']} 通过")

        session.current_stage = AssemblyStage.ROOTING_DEPLOY

    async def _stage_deployment(
        self,
        session: AssemblySession,
        progress: Optional[Callable],
        log: Optional[Callable]
    ):
        """阶段6: 扎根部署"""
        if progress:
            await progress("🌿 阶段6/6: 扎根部署 - 新苗入土...")

        if log:
            await log("\n" + "="*50)
            await log("🚀 挂载部署")

        if not session.selected_repo:
            raise ValueError("未选择候选库")

        # 生成适配器
        adapter_code = self.adapter_generator.generate_python_adapter(
            module_name=session.selected_repo.name,
            repo_info=session.selected_repo.to_dict(),
            installation_result=session.installation_result.to_dict() if session.installation_result else {}
        )

        adapter_path = self.adapter_generator.save_adapter(
            module_name=session.selected_repo.name,
            code=adapter_code,
            adapter_type="python"
        )

        # 生成工具合约
        tool_contract = self.adapter_generator.generate_tool_contract(
            module_name=session.selected_repo.name,
            repo_info=session.selected_repo.to_dict(),
            installation_result=session.installation_result.to_dict() if session.installation_result else {}
        )

        if log:
            await log(f"   适配器: {adapter_path}")

        # 部署
        session.deployed_module = await self.deployment_bay.deploy(
            module_name=session.selected_repo.name,
            repo_info=session.selected_repo.to_dict(),
            installation_result=session.installation_result.to_dict() if session.installation_result else {},
            adapter_path=str(adapter_path),
            tool_contract=tool_contract.to_dict(),
            hot_reload=True
        )

        if log:
            await log(f"   ✅ 部署成功!")
            await log(f"   模块名: ext:{session.selected_repo.name}")

        session.current_stage = AssemblyStage.COMPLETE

    # ==================== 便捷方法 ====================

    async def quick_assemble(
        self,
        user_input: str,
        progress_callback: Optional[Callable] = None
    ) -> AssemblySession:
        """
        快速装配（自动选择）

        Args:
            user_input: 用户输入
            progress_callback: 进度回调

        Returns:
            AssemblySession: 装配结果
        """
        session = self.create_session()
        return await self.run_assembly(
            session_id=session.session_id,
            user_input=user_input,
            auto_resolve=True,
            progress_callback=progress_callback
        )

    def list_deployed(self) -> list[dict]:
        """列出已部署模块"""
        return self.deployment_bay.list_deployed()

    async def uninstall_module(self, module_name: str) -> bool:
        """卸载模块"""
        return await self.deployment_bay.undeploy(module_name)

    def format_session_status(self, session: AssemblySession) -> str:
        """格式化会话状态"""
        lines = [
            f"🚀 **装配会话 {session.session_id}**",
            f"阶段: {session.current_stage.value}",
            f"状态: {'运行中' if session.is_running else '空闲'}",
        ]

        if session.error_message:
            lines.append(f"错误: {session.error_message}")

        if session.selected_repo:
            lines.append(f"选中: {session.selected_repo.name}")

        if session.deployed_module:
            lines.append(f"✅ 已部署: ext:{session.selected_repo.name}")

        return "\n".join(lines)