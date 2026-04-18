"""
中继服务器定时任务调度器

功能：
- APScheduler 定时任务配置
- 周报邮件发送任务
- 客户端同步任务
- 统计聚合任务

作者：Living Tree AI 进化系统
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ============ 任务调度器 ============

_scheduler = None


def get_scheduler():
    """获取调度器实例（延迟初始化）"""
    global _scheduler
    if _scheduler is None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger

            _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
            logger.info("APScheduler 初始化成功")
        except ImportError:
            logger.warning("APScheduler 未安装，定时任务将不会运行")
            return None
    return _scheduler


def get_current_week_id() -> str:
    """获取当前周 ID (格式: YYYY-Www)"""
    now = datetime.now()
    iso_cal = now.isocalendar()
    return f"{iso_cal[0]}-W{iso_cal[1]:02d}"


# ============ 任务定义 ============

async def weekly_email_job():
    """
    每周邮件报告任务

    触发时间: 每周一 02:00 (Asia/Shanghai)
    """
    from .email_sender import get_email_sender, get_inbox_sync_manager, WeeklyReportGenerator
    from .main import load_weekly_data, aggregate_week

    logger.info("开始执行每周邮件报告任务...")

    try:
        week_id = get_current_week_id()

        # 加载统计数据
        stats_data = load_weekly_data(week_id)
        agg_data = aggregate_week(week_id)

        if not agg_data or agg_data.get("total_patches", 0) == 0:
            logger.info(f"本周 {week_id} 没有数据，跳过邮件发送")
            return

        # 构建统计摘要
        stats = {
            "patches": {
                "count": agg_data.get("total_patches", 0),
                "top_module": agg_data.get("top_modules", [{}])[0].get("module", "N/A") if agg_data.get("top_modules") else "N/A",
                "top_module_count": agg_data.get("top_modules", [{}])[0].get("count", 0) if agg_data.get("top_modules") else 0,
                "distribution": agg_data.get("patch_distribution", {}),
            },
            "pain_points": {
                "count": agg_data.get("total_pain_points", 0),
            },
            "suggestions": {
                "count": 0,  # TODO: 建议数据
            },
        }

        # 发送邮件
        sender = get_email_sender()
        config = sender.config

        if not config.enabled:
            logger.info("邮件功能已禁用，跳过邮件发送")
            return

        html_body = WeeklyReportGenerator.generate_html(stats, week_id, config.web_base_url)
        text_body = WeeklyReportGenerator.generate_text(stats, week_id, config.web_base_url)

        success = await sender.send_email(
            config.recipients,
            f"🌳 Living Tree AI 进化周报 - {week_id}",
            html_body,
            text_body,
        )

        if success:
            # 标记为已同步
            inbox_sync = get_inbox_sync_manager()
            message_id = f"weekly_report_{week_id}"
            inbox_sync.mark_synced(message_id, config.recipients)
            logger.info(f"周报邮件发送成功: {week_id}")
        else:
            logger.error(f"周报邮件发送失败: {week_id}")

    except Exception as e:
        logger.error(f"每周邮件任务执行失败: {e}")


async def client_sync_job():
    """
    客户端同步任务

    触发时间: 每周一 02:30 (Asia/Shanghai)
    """
    from .email_sender import sync_to_client_inboxes

    logger.info("开始执行客户端同步任务...")

    try:
        week_id = get_current_week_id()

        # 获取统计数据
        from .main import aggregate_week
        agg_data = aggregate_week(week_id)

        if not agg_data:
            logger.info(f"本周 {week_id} 没有数据，跳过客户端同步")
            return

        # 同步到客户端
        success = await sync_to_client_inboxes(week_id, agg_data)

        if success:
            logger.info(f"客户端同步成功: {week_id}")
        else:
            logger.error(f"客户端同步失败: {week_id}")

    except Exception as e:
        logger.error(f"客户端同步任务执行失败: {e}")


async def data_cleanup_job():
    """
    数据清理任务

    触发时间: 每周一 03:00 (Asia/Shanghai)
    保留最近 12 周的数据
    """
    import json
    from pathlib import Path

    logger.info("开始执行数据清理任务...")

    try:
        from .main import RAW_DIR, AGG_DIR

        now = datetime.now()
        cutoff_weeks = 12
        deleted_count = 0

        # 遍历原始数据目录
        if RAW_DIR.exists():
            for week_file in RAW_DIR.glob("weekly_*.json"):
                # 检查是否超过保留期限
                week_str = week_file.stem.replace("weekly_", "")
                try:
                    year, week_num = week_str.split("-W")
                    week_date = datetime.strptime(f"{year}-{week_num}-1", "%Y-%W-%w")
                    weeks_ago = (now - week_date).days // 7

                    if weeks_ago > cutoff_weeks:
                        week_file.unlink()
                        deleted_count += 1
                        logger.debug(f"删除过期数据: {week_file.name}")
                except Exception:
                    continue

        # 遍历聚合数据目录
        if AGG_DIR.exists():
            for agg_file in AGG_DIR.glob("module_hits_*.json"):
                week_str = agg_file.stem.replace("module_hits_", "")
                try:
                    year, week_num = week_str.split("-W")
                    week_date = datetime.strptime(f"{year}-{week_num}-1", "%Y-%W-%w")
                    weeks_ago = (now - week_date).days // 7

                    if weeks_ago > cutoff_weeks:
                        agg_file.unlink()
                        logger.debug(f"删除过期聚合: {agg_file.name}")
                except Exception:
                    continue

        logger.info(f"数据清理完成，删除了 {deleted_count} 个过期文件")

    except Exception as e:
        logger.error(f"数据清理任务执行失败: {e}")


# ============ 调度器管理 ============

def setup_scheduled_tasks():
    """配置定时任务"""
    scheduler = get_scheduler()
    if scheduler is None:
        logger.warning("调度器不可用，跳过任务配置")
        return

    # 每周一 02:00 发送周报邮件
    try:
        from apscheduler.triggers.cron import CronTrigger

        scheduler.add_job(
            weekly_email_job,
            CronTrigger(day_of_week="mon", hour=2, minute=0, timezone="Asia/Shanghai"),
            id="weekly_email_job",
            name="每周邮件报告",
            replace_existing=True,
        )
        logger.info("已配置每周邮件报告任务 (周一 02:00)")
    except Exception as e:
        logger.error(f"配置每周邮件任务失败: {e}")

    # 每周一 02:30 同步客户端
    try:
        scheduler.add_job(
            client_sync_job,
            CronTrigger(day_of_week="mon", hour=2, minute=30, timezone="Asia/Shanghai"),
            id="client_sync_job",
            name="客户端同步",
            replace_existing=True,
        )
        logger.info("已配置客户端同步任务 (周一 02:30)")
    except Exception as e:
        logger.error(f"配置客户端同步任务失败: {e}")

    # 每周一 03:00 清理数据
    try:
        scheduler.add_job(
            data_cleanup_job,
            CronTrigger(day_of_week="mon", hour=3, minute=0, timezone="Asia/Shanghai"),
            id="data_cleanup_job",
            name="数据清理",
            replace_existing=True,
        )
        logger.info("已配置数据清理任务 (周一 03:00)")
    except Exception as e:
        logger.error(f"配置数据清理任务失败: {e}")


def start_scheduler():
    """启动调度器"""
    scheduler = get_scheduler()
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info("任务调度器已启动")


def stop_scheduler():
    """停止调度器"""
    scheduler = get_scheduler()
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("任务调度器已停止")


def get_scheduled_jobs() -> list:
    """获取已调度的任务列表"""
    scheduler = get_scheduler()
    if scheduler is None:
        return []

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jobs


# ============ 手动触发 ============

async def trigger_weekly_email_now() -> bool:
    """手动触发周报邮件"""
    logger.info("手动触发周报邮件...")
    await weekly_email_job()
    return True


async def trigger_client_sync_now() -> bool:
    """手动触发客户端同步"""
    logger.info("手动触发客户端同步...")
    await client_sync_job()
    return True
