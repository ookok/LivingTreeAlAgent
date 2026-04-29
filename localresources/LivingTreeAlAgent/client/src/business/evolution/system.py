# system.py — 统一调度器

import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from .models import (
    PatchDoc, PatchAction, UIPainPoint, PainType, PainCause,
    WeeklyReport, ClientConfig, EvolutionStats,
    ForumPost, ExternalPlatform, DistillationCategory,
    get_week_id, generate_client_id,
)

from .patch_manager import PatchManager, get_patch_manager, P2PBroadcastService
from .experience_optimizer import ExperienceOptimizer, get_experience_optimizer, IndustryDistiller, get_industry_distiller
from .data_collector import DataCollector, get_data_collector, Content回流Handler, get_回流_handler
from .relay_client import RelayClient, get_relay_client, BotPostingService, get_bot_posting_service
from .forum_client import ForumClient, get_forum_client


class EvolutionSystem:
    """
    智能进化系统 — 统一调度器（终极版）

    整合组件：
    1. PatchManager — 自我修补 + P2P广播
    2. ExperienceOptimizer — 体验优化 + 行业蒸馏
    3. DataCollector — 数据收集 + 内容回流
    4. RelayClient — 中继通信
    5. ForumClient — 论坛客户端
    6. BotPostingService — Bot发帖服务
    """

    def __init__(
        self,
        data_dir: Path = None,
        config: ClientConfig = None,
    ):
        """
        初始化进化系统

        Args:
            data_dir: 数据存储目录
            config: 客户端配置
        """
        self._data_dir = data_dir or self._default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._config = config or ClientConfig()
        if not self._config.client_id:
            self._config.client_id = generate_client_id()

        # 子系统
        self._patch_manager = PatchManager(
            data_dir=self._data_dir / "patches",
            config=self._config,
        )
        self._optimizer = ExperienceOptimizer(
            data_dir=self._data_dir / "experience",
            config=self._config,
        )
        self._collector = DataCollector(
            data_dir=self._data_dir / "collector",
            config=self._config,
        )
        self._relay = RelayClient(
            server_url=self._config.relay_server_url,
            config=self._config,
        )

        # 终极版新增子系统
        self._forum_client: Optional[ForumClient] = None
        self._bot_service: Optional[BotPostingService] = None
        self._回流_handler: Optional[Content回流Handler] = None
        self._industry_distiller: Optional[IndustryDistiller] = None
        self._p2p_service: Optional[P2PBroadcastService] = None

        # 后台线程
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False

        # 统计
        self._stats = EvolutionStats()

        # 日志
        self._logger = logging.getLogger(__name__)

    def _default_data_dir(self) -> Path:
        """默认数据目录"""
        return Path.home() / ".hermes-desktop" / "evolution"

    # ========== 核心接口 ==========

    def create_patch(
        self,
        module: str,
        action: PatchAction,
        old_value: Any,
        new_value: Any,
        reason: str,
        auto_apply: bool = True,
    ) -> Optional[PatchDoc]:
        """
        创建补丁

        Args:
            module: 模块名
            action: 动作类型
            old_value: 旧值
            new_value: 新值
            reason: 原因
            auto_apply: 是否自动应用

        Returns:
            PatchDoc: 补丁或None
        """
        patch = self._patch_manager.create_patch(
            module=module,
            action=action,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
        )

        if patch is None:
            return None

        if auto_apply and self._config.auto_patch:
            self._patch_manager.apply_patch(patch.id)
            self._stats.applied_patches += 1
        else:
            self._stats.total_patches += 1

        self._stats.last_patch_time = int(time.time())
        return patch

    def record_ui_event(
        self,
        event_type: str,
        module: str,
        duration: float = 0,
        metadata: Dict[str, Any] = None,
    ):
        """
        记录UI事件

        Args:
            event_type: 事件类型
            module: 模块名
            duration: 持续时间
            metadata: 额外数据
        """
        self._optimizer.record_event(event_type, module, duration, metadata)

    def generate_hint(self, pain_id: str) -> Optional[Dict[str, Any]]:
        """
        为痛点生成提示卡片

        Args:
            pain_id: 痛点ID

        Returns:
            Dict: 提示卡片内容
        """
        pain_point = None
        for p in self._optimizer.get_unresolved_pain_points():
            if p.id == pain_id:
                pain_point = p
                break

        if pain_point is None:
            return None

        return self._optimizer.generate_hint_card(pain_point)

    def upload_weekly_report(self) -> bool:
        """
        上传周报

        Returns:
            bool: 是否成功
        """
        if not self._config.enabled:
            return False

        # 检查是否应该上传
        if not self._collector.should_upload():
            return False

        # 生成周报
        report = self._collector.generate_weekly_report(
            patches=self._patch_manager.get_applied_patches(),
            pain_points=self._optimizer.get_unresolved_pain_points(),
        )

        # 上传
        success = self._relay.upload_report(report)

        if success:
            self._collector.mark_report_uploaded(report.week_id)
            self._collector.update_upload_time()
            self._stats.reports_uploaded += 1
        else:
            self._collector.mark_report_failed(report.week_id)

        return success

    def fetch_and_apply_rules(self) -> int:
        """
        拉取并应用安全规则

        Returns:
            int: 应用数量
        """
        rules = self._relay.fetch_safety_rules()
        if not rules:
            return 0

        applied = 0
        for rule in rules:
            # 应用规则到白名单/黑名单
            module = rule.get("module", "")
            action = rule.get("action", "")

            if action == "whitelist" and module:
                self._config.whitelist_modules.append(module)
                applied += 1
            elif action == "blacklist" and module:
                self._config.blacklist_modules.append(module)
                applied += 1

        if applied > 0:
            self._patch_manager.update_config(
                whitelist_modules=self._config.whitelist_modules,
                blacklist_modules=self._config.blacklist_modules,
            )

        return applied

    # ========== 调度管理 ==========

    def start_scheduler(self, interval_hours: float = 1.0):
        """
        启动后台调度器

        Args:
            interval_hours: 检查间隔（小时）
        """
        if self._running:
            return

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            args=(interval_hours,),
            daemon=True,
        )
        self._scheduler_thread.start()
        self._logger.info(f"调度器已启动，间隔 {interval_hours}h")

    def stop_scheduler(self):
        """停止后台调度器"""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        self._logger.info("调度器已停止")

    def _scheduler_loop(self, interval_hours: float):
        """
        调度器循环

        Args:
            interval_hours: 检查间隔
        """
        interval_seconds = interval_hours * 3600

        while self._running:
            try:
                # 1. 检查周报上传
                self.upload_weekly_report()

                # 2. 检查服务器健康
                if not self._relay.check_server_health():
                    self._logger.warning("服务器不可达")

                # 3. 拉取安全规则
                self.fetch_and_apply_rules()

                # 4. 自动应用待处理补丁
                self._patch_manager.auto_apply_all()

            except Exception as e:
                self._logger.error(f"调度器错误: {e}")

            time.sleep(interval_seconds)

    # ========== 统计与状态 ==========

    def get_stats(self) -> EvolutionStats:
        """获取进化统计"""
        patch_stats = self._patch_manager.get_stats()
        optimizer_stats = self._optimizer.get_stats()
        collector_stats = self._collector.get_stats()

        stats = EvolutionStats(
            total_patches=patch_stats["total_patches"],
            applied_patches=patch_stats["applied"],
            total_pain_points=optimizer_stats["total_pain_points"],
            resolved_pain_points=optimizer_stats["resolved"],
            reports_generated=collector_stats["total_reports"],
            reports_uploaded=collector_stats["uploaded_reports"],
        )

        return stats

    def get_full_stats(self) -> Dict[str, Any]:
        """获取完整统计（包含所有子系统）"""
        stats = {
            "system": {
                "enabled": self._config.enabled,
                "client_id": self._config.client_id,
                "auto_patch": self._config.auto_patch,
                "auto_upload": self._config.auto_upload,
                "relay_server": self._config.relay_server_url,
            },
            "patch_manager": self._patch_manager.get_stats(),
            "optimizer": self._optimizer.get_stats(),
            "collector": self._collector.get_stats(),
            "evolution": self.get_stats().to_dict(),
        }

        # 终极版新增子系统统计
        try:
            if self._forum_client:
                stats["forum"] = self._forum_client.get_stats()
        except Exception:
            pass

        try:
            if self._回流_handler:
                stats["回流"] = self._回流_handler.get_stats()
        except Exception:
            pass

        try:
            if self._industry_distiller:
                stats["distillation"] = self._industry_distiller.get_stats()
        except Exception:
            pass

        try:
            if self._p2p_service:
                stats["p2p"] = {
                    "running": self._p2p_service.is_running(),
                    "neighbors": len(self._p2p_service.get_neighbors()),
                }
        except Exception:
            pass

        return stats

    def is_enabled(self) -> bool:
        """检查系统是否启用"""
        return self._config.enabled

    def enable(self):
        """启用系统"""
        self._config.enabled = True
        self._collector.update_config(enabled=True)

    def disable(self):
        """禁用系统"""
        self._config.enabled = False
        self._collector.update_config(enabled=False)

    # ========== 快捷访问 ==========

    def get_patch_manager(self) -> PatchManager:
        """获取补丁管理器"""
        return self._patch_manager

    def get_experience_optimizer(self) -> ExperienceOptimizer:
        """获取体验优化器"""
        return self._optimizer

    def get_data_collector(self) -> DataCollector:
        """获取数据收集器"""
        return self._collector

    def get_relay_client(self) -> RelayClient:
        """获取中继客户端"""
        return self._relay

    # ========== 终极版新增：懒加载子系统 ==========

    def _get_forum_client(self) -> ForumClient:
        """获取论坛客户端（懒加载）"""
        if self._forum_client is None:
            self._forum_client = ForumClient(
                data_dir=self._data_dir / "forum",
                client_id=self._config.client_id,
                relay_server_url=self._config.relay_server_url,
            )
        return self._forum_client

    def _get_bot_service(self) -> BotPostingService:
        """获取Bot发帖服务（懒加载）"""
        if self._bot_service is None:
            self._bot_service = BotPostingService(self._relay)
        return self._bot_service

    def _get_回流_handler(self) -> Content回流Handler:
        """获取回流处理器（懒加载）"""
        if self._回流_handler is None:
            self._回流_handler = Content回流Handler(
                data_dir=self._data_dir / "回流",
            )
        return self._回流_handler

    def _get_industry_distiller(self) -> IndustryDistiller:
        """获取行业蒸馏器（懒加载）"""
        if self._industry_distiller is None:
            self._industry_distiller = IndustryDistiller(
                data_dir=self._data_dir / "distillation",
            )
        return self._industry_distiller

    def _get_p2p_service(self) -> P2PBroadcastService:
        """获取P2P广播服务（懒加载）"""
        if self._p2p_service is None:
            self._p2p_service = P2PBroadcastService(self._patch_manager)
        return self._p2p_service

    # ========== 终极版新增：社区共享 ==========

    def share_patch_to_forum(self, patch: PatchDoc) -> ForumPost:
        """
        分享补丁到论坛

        Args:
            patch: 补丁文档

        Returns:
            ForumPost: 论坛帖子
        """
        forum = self._get_forum_client()
        post = forum.create_patch_post(patch)
        forum.publish_post(post.id)
        return post

    def get_forum_feed(self, post_type: str = None, limit: int = 20) -> List[ForumPost]:
        """
        获取论坛动态

        Args:
            post_type: 帖子类型过滤
            limit: 返回数量

        Returns:
            List[ForumPost]: 帖子列表
        """
        forum = self._get_forum_client()
        return forum.fetch_forum_feed(limit=limit)

    # ========== 终极版新增：外部求解 ==========

    def post_to_external(
        self,
        content: str,
        platform: ExternalPlatform,
        attribution_id: str,
    ) -> bool:
        """
        发帖到外部平台

        Args:
            content: 内容
            platform: 目标平台
            attribution_id: 归因ID

        Returns:
            bool: 是否成功
        """
        from .models import ForumPost, ForumPostType

        # 创建临时帖子
        post = ForumPost(
            id=f"ext_{int(time.time())}",
            post_type=ForumPostType.KNOWLEDGE分享,
            title="",
            content=content,
            author_client_id=self._config.client_id,
            timestamp=int(time.time()),
        )

        bot = self._get_bot_service()
        result = bot.post_to_external(post, platform, attribution_id)
        return result is not None and result.status == "success"

    # ========== 终极版新增：行业蒸馏 ==========

    def record_industry_behavior(
        self,
        category: DistillationCategory,
        keywords: List[str],
        context: str = "",
        module: str = "",
    ):
        """
        记录行业行为

        Args:
            category: 行为类别
            keywords: 关键词
            context: 上下文
            module: 来源模块
        """
        distiller = self._get_industry_distiller()
        distiller.record_behavior(category, keywords, context, module)

    def get_distillation_rules(self) -> List[Dict[str, Any]]:
        """
        获取蒸馏规则

        Returns:
            List[Dict]: 规则列表
        """
        distiller = self._get_industry_distiller()
        return [r.to_dict() for r in distiller.get_active_rules()]

    def generate_prompt_augmentation(self) -> str:
        """
        生成 Prompt 增强文本

        Returns:
            str: 增强文本
        """
        distiller = self._get_industry_distiller()
        return distiller.generate_prompt_augmentation()

    # ========== 终极版新增：内容回流 ==========

    def ingest_external_reply(
        self,
        post_id: str,
        platform: ExternalPlatform,
        author: str,
        content: str,
    ) -> bool:
        """
        摄入外部回复

        Args:
            post_id: 外部帖子ID
            platform: 平台
            author: 作者
            content: 内容

        Returns:
            bool: 是否成功
        """
        handler = self._get_回流_handler()
        reply = handler.ingest_reply(post_id, platform, author, content)
        return handler.parse_and_absorb(reply.id)

    def get回流_knowledge(self) -> str:
        """
        获取回流知识库文本

        Returns:
            str: 知识库文本
        """
        handler = self._get_回流_handler()
        return handler.generate_knowledge_base()

    # ========== 终极版新增：P2P 广播 ==========

    def start_p2p_broadcast(self) -> bool:
        """
        启动 P2P 广播服务

        Returns:
            bool: 是否成功
        """
        p2p = self._get_p2p_service()
        return p2p.start()

    def stop_p2p_broadcast(self):
        """停止 P2P 广播服务"""
        p2p = self._get_p2p_service()
        p2p.stop()

    def broadcast_patch(self, patch: PatchDoc) -> bool:
        """
        广播补丁到 P2P 网络

        Args:
            patch: 补丁文档

        Returns:
            bool: 是否成功
        """
        p2p = self._get_p2p_service()
        return p2p.broadcast_patch(patch)

    def get_p2p_neighbors(self) -> int:
        """
        获取 P2P 邻居数量

        Returns:
            int: 邻居数量
        """
        p2p = self._get_p2p_service()
        return len(p2p.get_neighbors())

    # ========== 配置更新 ==========

    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

        # 同步到子系统
        self._patch_manager.update_config(**kwargs)
        self._collector.update_config(**kwargs)

        if "relay_server_url" in kwargs:
            self._relay.set_server_url(kwargs["relay_server_url"])

    def get_config(self) -> ClientConfig:
        """获取配置"""
        return self._config


# 全局单例
_evolution_system_instance: Optional[EvolutionSystem] = None


def get_evolution_system() -> EvolutionSystem:
    """获取进化系统全局实例"""
    global _evolution_system_instance
    if _evolution_system_instance is None:
        _evolution_system_instance = EvolutionSystem()
    return _evolution_system_instance
