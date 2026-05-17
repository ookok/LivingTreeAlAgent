"""Overnight task mixin for IntegrationHub — extracted from hub.py."""
from __future__ import annotations
from typing import Any

class OvernightTaskMixin:
    """Mixin providing overnight/long-running task methods."""

    async def start_overnight_task(
        self, goal: str,
        notify_platforms: list[str] | None = None,
        notify_interval_minutes: int = 0,
        notify_email: str = "",
    ):
        """启动挂机长任务。

        Args:
            goal: 自然语言目标
            notify_platforms: 通知平台 (cli/telegram/smtp/webhook/all)
            notify_interval_minutes: 进度通知间隔（0=仅完成时通知）
            notify_email: SMTP 邮件地址
        """
        ot = getattr(self.world, "overnight_task", None)
        if not ot:
            logger.error("OvernightTask 未初始化")
            return None
        logger.info("OvernightTask: 开始挂机 — %s", goal[:60])
        status = await ot.start(
            goal,
            notify_platforms=notify_platforms,
            notify_interval_minutes=notify_interval_minutes,
            notify_email=notify_email,
        )
        return status

    async def resume_overnight_task(self):
        """恢复上次中断的挂机任务。"""
        ot = getattr(self.world, "overnight_task", None)
        if not ot:
            return None
        return await ot.resume()

    def stop_overnight_task(self):
        """停止当前挂机任务。"""
        ot = getattr(self.world, "overnight_task", None)
        if ot:
            ot.stop()

    def overnight_task_status(self) -> Optional[dict]:
        """查询挂机任务状态。"""
        ot = getattr(self.world, "overnight_task", None)
        if not ot:
            return None
        s = ot.status
        return {
            "goal": s.goal,
            "state": s.state,
            "percent": s.percent,
            "current_step": s.current_step,
            "completed_steps": s.completed_steps,
            "total_steps": s.total_steps,
            "report_path": s.report_path,
            "elapsed_seconds": s.elapsed_seconds,
        }

__all__ = ["OvernightTaskMixin"]
