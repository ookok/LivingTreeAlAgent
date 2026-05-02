"""
SelfEvolutionOrchestrator - 自我进化协调器

顶层协调器，整合所有自我进化组件：
- ProjectStructureScanner: 项目结构扫描
- KnowledgeIngestionPipeline: 知识摄入
- CodeEvolutionPlanner: 进化规划
- CodeEvolutionExecutor: 进化执行

提供两种模式：
1. 手动模式：用户输入目标/知识，生成计划，审核后执行
2. 自动模式：周期性扫描项目，发现改进机会，自动进化

安全机制：
- 所有代码变更需要通过 GlobalModelRouter 验证
- 执行前创建备份
- 支持回滚
- 危险操作需要用户确认

Author: LivingTreeAI
Date: 2026-04-29
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from loguru import logger

from business.self_evolution.project_structure_scanner import (
    ProjectStructureScanner, ScanResult, ScanDepth,
)
from business.self_evolution.knowledge_ingestion_pipeline import (
    KnowledgeIngestionPipeline, KnowledgeEntry, KnowledgeSource, IngestionResult,
)
from business.self_evolution.code_evolution_planner import (
    CodeEvolutionPlanner, EvolutionPlan, EvolutionAction, EvolutionStatus,
)
from business.self_evolution.code_evolution_executor import (
    CodeEvolutionExecutor, ExecutionResult, ExecutionLog,
)


@dataclass
class EvolutionSession:
    """进化会话"""
    session_id: str
    started_at: str
    phase: str = "idle"  # idle, scanning, ingesting, planning, executing, done
    scan_result: Optional[ScanResult] = None
    knowledge_entries: List[KnowledgeEntry] = field(default_factory=list)
    plan: Optional[EvolutionPlan] = None
    execution_result: Optional[ExecutionResult] = None
    logs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "phase": self.phase,
            "total_files": self.scan_result.total_files if self.scan_result else 0,
            "knowledge_count": len(self.knowledge_entries),
            "action_count": len(self.plan.actions) if self.plan else 0,
            "completed_count": self.execution_result.completed_actions if self.execution_result else 0,
            "logs": self.logs[-20:],  # 最近 20 条
            "errors": self.errors[-10:],  # 最近 10 条
        }


class SelfEvolutionOrchestrator:
    """
    自我进化协调器

    整合 Scanner + Ingestion + Planner + Executor，
    提供一键自我进化 API 和持续进化循环。

    用法：
        orchestrator = SelfEvolutionOrchestrator(project_root)

        # 手动模式：一步进化
        result = await orchestrator.evolve(goal="增强代码补全能力")

        # 学习新知识
        await orchestrator.learn_from_url("https://example.com/docs")
        await orchestrator.learn_from_text("我发现缓存有问题...", "用户反馈")
        await orchestrator.learn_from_document("/path/to/doc.pdf")
        await orchestrator.learn_from_source_code("/path/to/repo")

        # 自动模式：持续进化
        orchestrator.start_auto_evolution(interval_hours=24)
    """

    HISTORY_DIR = ".evolution_history"
    STATE_FILE = "orchestrator_state.json"

    def __init__(
        self,
        project_root: str,
        auto_approve: bool = False,
        on_progress: Optional[Callable[[str, float], None]] = None,
        on_approve: Optional[Callable[[EvolutionAction], bool]] = None,
    ):
        """
        Args:
            project_root: 项目根目录
            auto_approve: 是否自动批准进化动作
            on_progress: 进度回调 (phase, progress_0_to_1)
            on_approve: 审核回调 (action -> bool)
        """
        self._root = Path(project_root).resolve()
        self._auto_approve = auto_approve
        self._on_progress = on_progress
        self._on_approve = on_approve
        self._logger = logger.bind(component="SelfEvolutionOrchestrator")

        # 初始化组件
        self._scanner = ProjectStructureScanner(str(self._root))
        self._ingestion = KnowledgeIngestionPipeline(str(self._root))
        self._planner = CodeEvolutionPlanner(str(self._root))
        self._executor = CodeEvolutionExecutor(
            str(self._root),
            dry_run=False,
            on_approve=on_approve,
        )

        # 历史记录
        self._history_dir = self._root / self.HISTORY_DIR
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._session_counter = 0

        # 自动进化状态
        self._auto_running = False

    # ── 一步进化（手动模式）─────────────────────────────────

    async def evolve(
        self,
        goal: str = "",
        constraints: Optional[List[str]] = None,
        focus_areas: Optional[List[str]] = None,
        scan_depth: ScanDepth = ScanDepth.MEDIUM,
    ) -> EvolutionSession:
        """
        执行一步完整进化流程

        流程：扫描 → 规划 → 执行

        Args:
            goal: 进化目标（空则自动分析）
            constraints: 约束条件
            focus_areas: 关注领域
            scan_depth: 扫描深度

        Returns:
            EvolutionSession
        """
        self._session_counter += 1
        session = EvolutionSession(
            session_id=f"evo_{self._session_counter:04d}",
            started_at=datetime.now().isoformat(),
        )

        self._log(session, f"🚀 开始进化会话: {goal or '自动分析'}")

        # Phase 1: 扫描项目结构
        session.phase = "scanning"
        self._notify_progress("扫描项目结构...", 0.1)
        try:
            scan_result = self._scanner.scan(depth=scan_depth)
            session.scan_result = scan_result
            self._log(session, f"扫描完成: {scan_result.total_files} 文件, "
                                f"{scan_result.total_lines} 行, "
                                f"{scan_result.total_classes} 类")
        except Exception as e:
            session.errors.append(f"扫描失败: {e}")
            self._log(session, f"扫描失败: {e}")
            session.phase = "done"
            return session

        # Phase 2: 获取未应用知识
        session.phase = "ingesting"
        self._notify_progress("分析知识库...", 0.3)
        unapplied = self._ingestion.get_unapplied_entries()
        session.knowledge_entries = unapplied
        if unapplied:
            self._log(session, f"发现 {len(unapplied)} 条未应用知识")

        # Phase 3: 生成进化计划
        session.phase = "planning"
        self._notify_progress("生成进化计划...", 0.5)
        try:
            plan = await self._planner.create_evolution_plan(
                scan_result=scan_result,
                knowledge_entries=unapplied,
                user_goal=goal,
                user_constraints=constraints,
                focus_areas=focus_areas,
            )
            session.plan = plan
            self._log(session, f"计划已生成: {len(plan.actions)} 个动作")

            if not plan.actions:
                self._log(session, "无需进化动作")
                session.phase = "done"
                return session

        except Exception as e:
            session.errors.append(f"计划生成失败: {e}")
            self._log(session, f"计划生成失败: {e}")
            session.phase = "done"
            return session

        # Phase 4: 执行进化
        session.phase = "executing"
        self._notify_progress("执行进化...", 0.7)
        try:
            exec_result = await self._executor.execute_plan(
                plan,
                auto_approve=self._auto_approve,
            )
            session.execution_result = exec_result
            self._log(session,
                      f"执行完成: {exec_result.completed_actions} 成功, "
                      f"{exec_result.failed_actions} 失败")

            # 标记知识已应用
            for entry in unapplied:
                self._ingestion.mark_applied(entry.id)

        except Exception as e:
            session.errors.append(f"执行失败: {e}")
            self._log(session, f"执行失败: {e}")

        session.phase = "done"
        self._notify_progress("进化完成", 1.0)

        # 保存会话
        self._save_session(session)
        return session

    # ── 知识学习接口 ────────────────────────────────────────

    async def learn_from_url(self, url: str, tags: Optional[List[str]] = None) -> IngestionResult:
        """从 URL 学习"""
        self._logger.info(f"从 URL 学习: {url}")
        return await self._ingestion.ingest_url(url, tags)

    async def learn_from_text(
        self,
        text: str,
        source_name: str = "user_input",
        tags: Optional[List[str]] = None,
    ) -> IngestionResult:
        """从文本学习"""
        self._logger.info(f"从文本学习: {source_name}")
        return await self._ingestion.ingest_text(text, source_name, tags)

    async def learn_from_document(
        self,
        file_path: str,
        tags: Optional[List[str]] = None,
    ) -> IngestionResult:
        """从文档学习"""
        self._logger.info(f"从文档学习: {file_path}")
        return await self._ingestion.ingest_document(file_path, tags)

    async def learn_from_source_code(
        self,
        path: str,
        tags: Optional[List[str]] = None,
    ) -> IngestionResult:
        """从源代码学习"""
        self._logger.info(f"从源代码学习: {path}")
        return await self._ingestion.ingest_source_code(path, tags)

    async def learn_from_git_history(
        self,
        max_commits: int = 50,
    ) -> IngestionResult:
        """从 Git 历史学习"""
        self._logger.info(f"从 Git 历史学习")
        return await self._ingestion.ingest_git_history(
            str(self._root), max_commits
        )

    # ── 项目分析接口 ────────────────────────────────────────

    def scan_project(self, depth: ScanDepth = ScanDepth.MEDIUM) -> ScanResult:
        """扫描项目结构"""
        return self._scanner.scan(depth=depth)

    def get_module_summary(self) -> str:
        """获取模块摘要"""
        return self._scanner.get_module_summary()

    def get_knowledge_summary(self) -> str:
        """获取知识库摘要"""
        return self._ingestion.get_knowledge_summary()

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "project_root": str(self._root),
            "auto_approve": self._auto_approve,
            "auto_running": self._auto_running,
            "knowledge_count": len(self._ingestion.list_entries()),
            "unapplied_knowledge": len(self._ingestion.get_unapplied_entries()),
            "session_count": self._session_counter,
        }

    # ── 自动进化循环 ────────────────────────────────────────

    async def auto_evolve_once(self) -> EvolutionSession:
        """执行一次自动进化（无用户目标，自动发现改进机会）"""
        self._logger.info("自动进化：扫描并发现改进机会")
        return await self.evolve(goal="")

    def start_auto_evolution(
        self,
        interval_hours: int = 24,
        max_iterations: int = 100,
    ):
        """
        启动自动进化循环（后台任务）

        注意：实际生产中应使用 QTimer 或 asyncio 任务
        这里提供接口，实际调度由 UI 层控制
        """
        self._auto_running = True
        self._logger.info(f"自动进化已启用（间隔 {interval_hours} 小时，最多 {max_iterations} 次）")

    def stop_auto_evolution(self):
        """停止自动进化"""
        self._auto_running = False
        self._logger.info("自动进化已停止")

    # ── 历史 ────────────────────────────────────────────────

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取进化历史"""
        sessions = []
        for f in sorted(self._history_dir.glob("session_*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append(data)
            except Exception:
                pass
        return sessions

    # ── 内部方法 ────────────────────────────────────────────

    def _log(self, session: EvolutionSession, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        session.logs.append(entry)
        self._logger.info(entry)

    def _notify_progress(self, message: str, progress: float):
        """通知进度"""
        if self._on_progress:
            try:
                self._on_progress(message, progress)
            except Exception:
                pass

    def _save_session(self, session: EvolutionSession):
        """保存会话到历史"""
        try:
            session_file = self._history_dir / f"session_{session.session_id}.json"
            session_file.write_text(
                json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            self._logger.error(f"保存会话失败: {e}")
