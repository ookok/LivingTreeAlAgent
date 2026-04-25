# system.py — 升级扫描系统统一调度器

"""
升级扫描系统（终极版）统一调度器

整合六大核心模块：
1. 开源库扫描与决策 (MultiSourceScanner + DecisionEngine)
2. 择优替换适配器 (AdapterWrapper)
3. 数据平滑迁移 (DataMigrationManager)
4. 补丁安全过渡 (PatchTransitionManager)
5. 多源镜像加速 (MirrorAccelerator + MultiSourceDownloader)
6. 社区驱动进化 (HotArticleCollector + ProposalGenerator)
"""

import asyncio
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import asdict
from datetime import datetime


from .scanner_models import (
    UpgradeStats, ScanSource, ReplacementDecision, DataVersion,
    MirrorSource,
)
from .scanner import MultiSourceScanner, ScanCache, get_scanner
from .decision_engine import DecisionEngine, get_decision_engine, get_mirror_manager
from .adapter_wrapper import AdapterWrapper, get_adapter_wrapper
from .data_migration import (
    DataMigrationManager, VersionManager,
    get_migration_manager, get_version_manager,
)
from .patch_transition import PatchTransitionManager, get_transition_manager
from .mirror_accelerator import (
    MirrorConfigManager, MultiSourceDownloader, GitHubAccelerator,
    get_mirror_config_manager, get_downloader, get_github_accelerator,
)
from .community_evolution import (
    HotArticleCollector, ProposalGenerator, CommunityEvolutionScheduler,
    get_hot_collector, get_proposal_generator, get_evolution_scheduler,
)


logger = logging.getLogger(__name__)


# ============ 升级扫描系统 ============

class UpgradeScannerSystem:
    """
    升级扫描系统 - 统一调度器

    用法:
    ```python
    system = UpgradeScannerSystem()

    # 扫描模块
    result = await system.scan_module("pdf_parser", "pdf_parser")

    # 决策
    decision = system.evaluate_and_decide("pdf_parser", candidates)

    # 适配封装
    adapter = system.create_adapter("pdf_parser", candidate)

    # 迁移数据
    system.migrate_data("config", "v1", "v2")

    # 补丁过渡
    system.execute_patch_transition(["network_retry", "cache"])

    # 下载加速
    await system.download_with_acceleration(url, dest)

    # 社区进化
    proposals = system.auto_generate_proposals()
    ```
    """

    def __init__(
        self,
        data_dir: Path = None,
        client_id: str = "",
    ):
        if data_dir is None:
            data_dir = Path.home() / ".hermes-desktop" / "upgrade_scanner"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._data_dir = data_dir

        self._client_id = client_id or f"client_{int(time.time())}"
        self._enabled = True

        # 子系统 (懒加载)
        self._scanner: Optional[MultiSourceScanner] = None
        self._decision_engine: Optional[DecisionEngine] = None
        self._adapter_wrapper: Optional[AdapterWrapper] = None
        self._migration_manager: Optional[DataMigrationManager] = None
        self._version_manager: Optional[VersionManager] = None
        self._transition_manager: Optional[PatchTransitionManager] = None
        self._mirror_config: Optional[MirrorConfigManager] = None
        self._downloader: Optional[MultiSourceDownloader] = None
        self._github_accelerator: Optional[GitHubAccelerator] = None
        self._hot_collector: Optional[HotArticleCollector] = None
        self._proposal_generator: Optional[ProposalGenerator] = None
        self._evolution_scheduler: Optional[CommunityEvolutionScheduler] = None

        # 统计
        self._stats = UpgradeStats()

        # 后台调度线程
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False

    # ============ 子系统访问器 ============

    @property
    def scanner(self) -> MultiSourceScanner:
        if self._scanner is None:
            self._scanner = get_scanner()
        return self._scanner

    @property
    def decision_engine(self) -> DecisionEngine:
        if self._decision_engine is None:
            self._decision_engine = get_decision_engine()
        return self._decision_engine

    @property
    def adapter_wrapper(self) -> AdapterWrapper:
        if self._adapter_wrapper is None:
            self._adapter_wrapper = get_adapter_wrapper()
        return self._adapter_wrapper

    @property
    def migration_manager(self) -> DataMigrationManager:
        if self._migration_manager is None:
            self._migration_manager = get_migration_manager()
        return self._migration_manager

    @property
    def version_manager(self) -> VersionManager:
        if self._version_manager is None:
            self._version_manager = get_version_manager()
        return self._version_manager

    @property
    def transition_manager(self) -> PatchTransitionManager:
        if self._transition_manager is None:
            self._transition_manager = get_transition_manager()
        return self._transition_manager

    @property
    def mirror_config(self) -> MirrorConfigManager:
        if self._mirror_config is None:
            self._mirror_config = get_mirror_config_manager()
        return self._mirror_config

    @property
    def downloader(self) -> MultiSourceDownloader:
        if self._downloader is None:
            self._downloader = get_downloader()
        return self._downloader

    @property
    def github_accelerator(self) -> GitHubAccelerator:
        if self._github_accelerator is None:
            self._github_accelerator = get_github_accelerator()
        return self._github_accelerator

    @property
    def hot_collector(self) -> HotArticleCollector:
        if self._hot_collector is None:
            self._hot_collector = get_hot_collector()
        return self._hot_collector

    @property
    def proposal_generator(self) -> ProposalGenerator:
        if self._proposal_generator is None:
            self._proposal_generator = get_proposal_generator()
        return self._proposal_generator

    @property
    def evolution_scheduler(self) -> CommunityEvolutionScheduler:
        if self._evolution_scheduler is None:
            self._evolution_scheduler = get_evolution_scheduler()
        return self._evolution_scheduler

    # ============ 核心API ============

    async def scan_module(
        self,
        module_name: str,
        module_category: str,
        sources: List[ScanSource] = None,
    ) -> Dict[str, Any]:
        """
        扫描模块，寻找更优开源库

        Args:
            module_name: 模块名
            module_category: 模块分类
            sources: 扫描来源

        Returns:
            Dict: 扫描结果
        """
        if not self._enabled:
            return {"status": "disabled"}

        try:
            task = await self.scanner.scan_all(
                module_name=module_name,
                module_category=module_category,
                sources=sources,
            )

            self._stats.total_scans += 1

            return {
                "status": "completed",
                "task_id": task.id,
                "module_name": module_name,
                "candidates": [c.to_dict() for c in task.candidates],
                "candidate_count": len(task.candidates),
            }

        except Exception as e:
            logger.error(f"Scan failed for {module_name}: {e}")
            return {"status": "error", "message": str(e)}

    def evaluate_candidates(
        self,
        module_name: str,
        candidates: List[Any],
        custom_code_size: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        评估候选库

        Args:
            module_name: 模块名
            candidates: 候选库列表
            custom_code_size: 自研代码行数

        Returns:
            List[Dict]: 评估结果
        """
        return self.decision_engine.batch_evaluate(
            candidates=candidates,
            module_name=module_name,
            custom_code_size=custom_code_size,
        )

    def decide_best_candidate(
        self,
        module_name: str,
        candidates: List[Any],
        custom_code_size: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        获取最佳候选并决策

        Returns:
            最佳候选的评估结果
        """
        return self.decision_engine.get_best_candidate(
            candidates=candidates,
            module_name=module_name,
            custom_code_size=custom_code_size,
        )

    def create_adapter(
        self,
        module_name: str,
        library_name: str,
        library_version: str,
    ) -> Optional[Dict[str, Any]]:
        """
        创建适配器

        Args:
            module_name: 原始模块名
            library_name: 开源库名
            library_version: 开源库版本

        Returns:
            Dict: 适配器元数据
        """
        try:
            metadata = self.adapter_wrapper.create_adapter(
                module_name=module_name,
                library_name=library_name,
                library_version=library_version,
            )

            return metadata.to_dict() if hasattr(metadata, 'to_dict') else {
                "adapter_id": metadata.adapter_id,
                "class_name": metadata.class_name,
                "status": metadata.status,
            }
        except Exception as e:
            logger.error(f"Create adapter failed: {e}")
            return None

    def install_adapter(self, adapter_id: str) -> bool:
        """安装适配器 (安装开源库依赖)"""
        return self.adapter_wrapper.install_adapter(adapter_id)

    def activate_adapter(self, adapter_id: str) -> bool:
        """激活适配器 (替换原始模块)"""
        return self.adapter_wrapper.activate_adapter(adapter_id)

    def deactivate_adapter(self, adapter_id: str) -> bool:
        """停用适配器 (恢复原始模块)"""
        return self.adapter_wrapper.deactivate_adapter(adapter_id)

    # ============ 数据迁移API ============

    def get_current_version(self) -> str:
        """获取当前数据版本"""
        return self.version_manager.get_version()

    def register_migration(
        self,
        file_path: str,
        from_version: str,
        to_version: str,
        strategy: str = "lazy",
    ) -> str:
        """
        注册迁移任务

        Args:
            file_path: 文件路径
            from_version: 源版本
            to_version: 目标版本
            strategy: 迁移策略 (lazy/eager/dual_read)

        Returns:
            str: 迁移ID
        """
        return self.migration_manager.register_migration(
            file_path=file_path,
            from_version=from_version,
            to_version=to_version,
            strategy=strategy,
        )

    def execute_migration(
        self,
        migration_id: str,
        converter: Callable[[Dict], Dict],
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        执行迁移

        Args:
            migration_id: 迁移ID
            converter: 转换函数
            batch_size: 批处理大小

        Returns:
            Dict: 执行结果
        """
        result = self.migration_manager.execute_migration(
            migration_id=migration_id,
            converter=converter,
            batch_size=batch_size,
        )

        if result.get("status") == "completed":
            self._stats.migrations_completed += 1

        return result

    def rollback_migration(self, migration_id: str) -> bool:
        """回滚迁移"""
        return self.migration_manager.rollback_migration(migration_id)

    # ============ 补丁过渡API ============

    def execute_patch_transition(
        self,
        upgraded_modules: List[str],
        oss_candidates: Dict[str, Dict] = None,
    ) -> Dict[str, Any]:
        """
        执行升级后补丁过渡

        Args:
            upgraded_modules: 已升级的模块列表
            oss_candidates: 开源库候选信息

        Returns:
            Dict: 执行结果
        """
        # 获取现有补丁
        existing_patches = []
        patch_manager = self._get_patch_manager()
        if patch_manager:
            try:
                existing_patches = [
                    p.to_dict() if hasattr(p, 'to_dict') else p
                    for p in patch_manager.get_applied_patches()
                ]
            except Exception:
                pass

        # 执行过渡
        results = self.transition_manager.execute_upgrade_transition(
            upgraded_modules=upgraded_modules,
            oss_candidates=oss_candidates or {},
        )

        self._stats.legacy_patches_reviewed += len(results.get("pending_review", []))

        return results

    def get_patch_review_notifications(self) -> List[Dict]:
        """获取补丁审核通知"""
        return self.transition_manager.generate_review_notifications()

    def confirm_patch_review(
        self,
        patch_id: str,
        action: str,
        user_confirmed: bool = False,
    ) -> bool:
        """确认补丁审核"""
        return self.transition_manager.confirm_review(
            patch_id=patch_id,
            action=action,
            user_confirmed=user_confirmed,
        )

    def _get_patch_manager(self):
        """获取补丁管理器 (如果可用)"""
        try:
            from client.src.business.evolution import get_evolution_system
            evo = get_evolution_system()
            return evo.get_patch_manager()
        except Exception:
            return None

    # ============ 镜像加速API ============

    def get_best_mirror(self, source_type: str = "github") -> Optional[Dict]:
        """获取最佳镜像"""
        mirror = self.mirror_config.get_best_mirror(source_type)
        if mirror:
            return {
                "name": mirror.name,
                "base_url": mirror.base_url,
                "health_score": mirror.health_score,
            }
        return None

    async def download_with_acceleration(
        self,
        url: str,
        dest_path: Path = None,
        progress_callback: Callable = None,
    ) -> Optional[Path]:
        """
        使用镜像加速下载

        Args:
            url: 源URL
            dest_path: 目标路径
            progress_callback: 进度回调

        Returns:
            Path: 下载后的文件路径
        """
        return await self.downloader.download(
            url=url,
            dest_path=dest_path,
            progress_callback=progress_callback,
        )

    async def download_github_release(
        self,
        repo: str,
        tag: str,
        filename: str,
        dest_dir: Path = None,
    ) -> Optional[Path]:
        """
        下载GitHub Release文件 (自动加速)

        Args:
            repo: 仓库 (owner/repo)
            tag: 版本标签
            filename: 文件名
            dest_dir: 目标目录

        Returns:
            Path: 下载后的文件路径
        """
        return await self.github_accelerator.download_release(
            repo=repo,
            tag=tag,
            filename=filename,
            dest_dir=dest_dir,
        )

    async def check_mirror_health(self) -> Dict[str, bool]:
        """检查所有镜像健康状态"""
        return await self.mirror_config.check_all_mirrors()

    # ============ 社区进化API ============

    async def collect_hot_articles(
        self,
        sources: List[str] = None,
    ) -> List[Dict]:
        """
        采集热点文章

        Args:
            sources: 来源列表 (github_trending/hackernews)

        Returns:
            List[Dict]: 文章列表
        """
        articles = []

        if sources is None or "github_trending" in sources:
            articles.extend(await self.hot_collector.collect_github_trending())

        if sources is None or "hackernews" in sources:
            articles.extend(await self.hot_collector.collect_hackernews())

        return [a.to_dict() if hasattr(a, 'to_dict') else a for a in articles]

    def auto_generate_proposals(self) -> List[Dict]:
        """
        自动生成架构升级提案

        Returns:
            List[Dict]: 新生成的提案
        """
        proposals = self.proposal_generator.auto_generate_proposals()
        self._stats.proposals_generated += len(proposals)
        return [p.to_dict() if hasattr(p, 'to_dict') else p for p in proposals]

    def publish_proposal(self, proposal_id: str) -> bool:
        """发布提案到社区"""
        return self.proposal_generator.publish_proposal(proposal_id)

    def upvote_proposal(self, proposal_id: str) -> int:
        """为提案点赞"""
        return self.proposal_generator.upvote_proposal(proposal_id)

    def decide_proposal(
        self,
        proposal_id: str,
        decision: str,
        note: str = "",
    ) -> bool:
        """提案表决"""
        result = self.proposal_generator.decide_proposal(
            proposal_id=proposal_id,
            decision=decision,
            note=note,
        )
        if result and decision == "approved":
            self._stats.proposals_approved += 1
        return result

    def get_community_stats(self) -> Dict[str, Any]:
        """获取社区统计"""
        return self.evolution_scheduler.get_statistics()

    # ============ 调度管理 ============

    async def start_scheduler(self, interval_hours: float = 24.0):
        """启动后台调度"""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(
            self._scheduler_loop(interval_hours)
        )
        logger.info(f"Upgrade scanner scheduler started (interval: {interval_hours}h)")

    async def stop_scheduler(self):
        """停止后台调度"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Upgrade scanner scheduler stopped")

    async def _scheduler_loop(self, interval_hours: float):
        """调度循环"""
        while self._running:
            try:
                # 1. 采集热点
                await self.collect_hot_articles()

                # 2. 生成提案
                self.auto_generate_proposals()

                # 3. 检查镜像健康
                await self.check_mirror_health()

            except Exception as e:
                logger.error(f"Scheduler cycle error: {e}")

            await asyncio.sleep(interval_hours * 3600)

    # ============ 统计与状态 ============

    def get_stats(self) -> UpgradeStats:
        """获取统计"""
        return self._stats

    def get_full_stats(self) -> Dict[str, Any]:
        """获取完整统计"""
        return {
            "upgrade_scanner": self._stats.to_dict(),
            "mirrors": {
                "total": len(self.mirror_config.get_all_mirrors()),
                "enabled": len(self.mirror_config.get_mirrors(enabled_only=True)),
            },
            "adapters": {
                "total": len(self.adapter_wrapper.get_all_adapters()),
                "active": len([a for a in self.adapter_wrapper.get_all_adapters() if a.status == "active"]),
            },
            "migrations": {
                "total": len(self.migration_manager.get_all_migrations()),
            },
            "patch_transition": {
                "legacy": len(self.transition_manager.get_legacy_patches()),
                "pending_review": len(self.transition_manager.get_pending_review()),
            },
            "community": self.get_community_stats(),
        }

    def enable(self):
        """启用系统"""
        self._enabled = True

    def disable(self):
        """禁用系统"""
        self._enabled = False

    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self._enabled


# ============ 全局实例 ============

_upgrade_system: Optional[UpgradeScannerSystem] = None


def get_upgrade_system() -> UpgradeScannerSystem:
    """获取升级扫描系统全局实例"""
    global _upgrade_system
    if _upgrade_system is None:
        _upgrade_system = UpgradeScannerSystem()
    return _upgrade_system


# ============ 便捷函数 ============

async def quick_scan(module_category: str) -> Dict[str, Any]:
    """
    快速扫描 (便捷函数)

    Args:
        module_category: 模块分类

    Returns:
        Dict: 扫描结果和最佳决策
    """
    system = get_upgrade_system()

    # 扫描
    scan_result = await system.scan_module(
        module_name=module_category,
        module_category=module_category,
    )

    if scan_result.get("status") != "completed":
        return scan_result

    # 获取最佳候选
    candidates = scan_result.get("candidates", [])
    best = system.decide_best_candidate(
        module_name=module_category,
        candidates=candidates,
    )

    return {
        "scan_result": scan_result,
        "best_candidate": best,
    }
