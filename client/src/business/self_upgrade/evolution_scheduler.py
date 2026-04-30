# evolution_scheduler.py — 进化调度器
# 闲置时触发 / 冲突时触发 / 发布前触发

import asyncio
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, List, Dict, Any
from pathlib import Path

from .models import EvolutionTask
from business.config import UnifiedConfig


class EvolutionScheduler:
    """
    进化任务调度器

    触发条件：
    1. 空闲触发 — 无用户操作 N 分钟后启动
    2. 冲突触发 — 用户纠正 AI 时触发
    3. 发布触发 — 内容发布前必经安全管道
    4. 手动触发 — 用户主动启动
    """

    def __init__(self, idle_minutes: int = None):
        # 从配置获取参数
        evo_config = UnifiedConfig.get_instance().get_evolution_config()
        if idle_minutes is None:
            idle_minutes = evo_config.get("idle_minutes", 5)
        self.idle_minutes = idle_minutes
        self._last_activity = time.time()
        self._idle_check_interval = evo_config.get("check_interval", 30)  # 秒
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._thread_join_timeout = evo_config.get("thread_join_timeout", 2.0)  # 线程 join 超时（秒）

        # 回调函数
        self._on_idle_debate: Optional[Callable] = None
        self._on_idle_external: Optional[Callable] = None
        self._on_conflict: Optional[Callable] = None
        self._on_publish: Optional[Callable] = None

        # 任务历史
        self.data_dir = Path.home() / ".hermes-desktop" / "self_upgrade"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: List[EvolutionTask] = []

    # ============================================================
    # 生命周期管理
    # ============================================================

    def start(self):
        """启动调度器"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._idle_loop, daemon=True)
        self._thread.start()
        print("[EvolutionScheduler] Started")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._thread_join_timeout)
        print("[EvolutionScheduler] Stopped")

    def _idle_loop(self):
        """空闲检测循环"""
        while self._running:
            try:
                if self._is_idle():
                    self._trigger_idle_evolution()
                time.sleep(self._idle_check_interval)
            except Exception as e:
                print(f"[EvolutionScheduler] Idle loop error: {e}")

    def _is_idle(self) -> bool:
        """检查是否空闲"""
        idle_seconds = (time.time() - self._last_activity)
        return idle_seconds >= (self.idle_minutes * 60)

    # ============================================================
    # 活动记录（被其他模块调用）
    # ============================================================

    def record_activity(self):
        """记录用户活动（重置空闲计时器）"""
        self._last_activity = time.time()

    # ============================================================
    # 触发器
    # ============================================================

    def trigger_idle_debate(self, topic: str, context: Optional[Dict] = None) -> EvolutionTask:
        """手动触发空闲辩论"""
        task = EvolutionTask(
            id=self._gen_task_id(),
            task_type="debate",
            trigger="idle",
            topic=topic,
        )
        self._run_task(task, context)
        return task

    def trigger_conflict(
        self,
        original_belief: str,
        user_correction: str,
        context: Optional[Dict] = None,
    ) -> EvolutionTask:
        """
        冲突触发 — 用户纠正 AI 时调用

        Args:
            original_belief: AI 原认知
            user_correction: 用户纠正内容
        """
        task = EvolutionTask(
            id=self._gen_task_id(),
            task_type="debate",
            trigger="conflict",
            topic=f"用户纠正: {original_belief[:50]}",
        )
        self._run_task(task, {
            **(context or {}),
            "original_belief": original_belief,
            "user_correction": user_correction,
        })
        return task

    def trigger_publish_check(
        self,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> EvolutionTask:
        """
        发布前安全检查
        """
        task = EvolutionTask(
            id=self._gen_task_id(),
            task_type="safety",
            trigger="publish",
            topic="发布前安全审查",
        )

        from .safety_pipeline import check_safety
        result = check_safety(content, metadata)

        task.result_summary = (
            "通过" if result.passed else "拦截"
        ) + f", 等级: {result.level.value}"
        task.status = "completed"
        task.completed_at = datetime.now()

        if not result.passed:
            task.error_message = "; ".join(result.issues)

        self.tasks.append(task)
        return task

    def trigger_manual(
        self,
        task_type: str,
        topic: str,
        context: Optional[Dict] = None,
    ) -> EvolutionTask:
        """手动触发任意任务"""
        task = EvolutionTask(
            id=self._gen_task_id(),
            task_type=task_type,
            trigger="manual",
            topic=topic,
        )
        self._run_task(task, context)
        return task

    # ============================================================
    # 任务执行
    # ============================================================

    def _run_task(self, task: EvolutionTask, context: Optional[Dict]):
        """异步执行任务"""
        task.status = "running"
        self.tasks.append(task)

        try:
            if task.task_type == "debate":
                self._execute_debate(task, context)
            elif task.task_type == "external":
                self._execute_external(task, context)
            elif task.task_type == "review":
                self._execute_review(task, context)
            elif task.task_type == "safety":
                self._execute_safety(task, context)
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)

        task.completed_at = datetime.now()

    def _execute_debate(self, task: EvolutionTask, context: Optional[Dict]):
        """执行辩论任务"""
        from .debate_engine import get_debate_engine
        engine = get_debate_engine()

        try:
            # 同步调用
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            record = loop.run_until_complete(
                engine.debate(
                    topic=task.topic,
                    topic_category=context.get("category", "general") if context else "general",
                    context=context or {},
                )
            )
            loop.close()

            task.result_summary = f"辩论完成，结论: {record.final_conclusion[:100]}"
            task.status = "completed"
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)

    def _execute_external(self, task: EvolutionTask, context: Optional[Dict]):
        """执行外部吸收任务"""
        from .external_absorption import get_external_absorption
        absorber = get_external_absorption()

        # 抓取 GitHub Issues 作为演示
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            insights = loop.run_until_complete(
                absorber.fetch_github_issues("microsoft/vscode", limit=5)
            )
            loop.close()

            task.result_summary = f"抓取 {len(insights)} 条外部内容"
            task.status = "completed"
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)

    def _execute_review(self, task: EvolutionTask, context: Optional[Dict]):
        """执行人工审核任务"""
        task.result_summary = "等待人工审核"
        # 审核任务不自动完成

    def _execute_safety(self, task: EvolutionTask, context: Optional[Dict]):
        """执行安全检查"""
        from .safety_pipeline import check_safety
        content = context.get("content", "") if context else ""
        result = check_safety(content, context)

        task.result_summary = "通过" if result.passed else "拦截"
        task.status = "completed"

    # ============================================================
    # 空闲进化
    # ============================================================

    def _trigger_idle_evolution(self):
        """触发空闲进化"""
        if self._on_idle_debate:
            topic = self._pick_idle_topic()
            if topic:
                try:
                    self._on_idle_debate(topic)
                except Exception as e:
                    print(f"[EvolutionScheduler] Idle debate failed: {e}")

        if self._on_idle_external:
            try:
                self._on_idle_external()
            except Exception as e:
                print(f"[EvolutionScheduler] Idle external failed: {e}")

    def _pick_idle_topic(self) -> str:
        """选择空闲辩论主题"""
        # 从知识库中选择待审核或争议性主题
        from .knowledge_base import get_knowledge_base
        kb = get_knowledge_base()

        pending = kb.get_all(verdict=None, limit=5)
        if pending:
            return f"重新审视: {pending[0].key}"

        # 默认主题
        return "AI 助手的最佳交互模式是什么？"

    # ============================================================
    # 辅助
    # ============================================================

    def _gen_task_id(self) -> str:
        return f"evo_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def get_recent_tasks(self, limit: int = 20) -> List[EvolutionTask]:
        """获取最近任务"""
        return sorted(self.tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "total_tasks": len(self.tasks),
            "running": sum(1 for t in self.tasks if t.status == "running"),
            "completed": sum(1 for t in self.tasks if t.status == "completed"),
            "failed": sum(1 for t in self.tasks if t.status == "failed"),
            "idle_minutes": self.idle_minutes,
            "seconds_since_activity": int(time.time() - self._last_activity),
        }


# 全局单例
_scheduler: Optional[EvolutionScheduler] = None


def get_evolution_scheduler() -> EvolutionScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = EvolutionScheduler()
    return _scheduler
