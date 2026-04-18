# relay_server/__init__.py
# 中继服务器 — FastAPI + 文件存储 + 静态页

"""
中继服务器架构：

1. 数据接收 (/api/collect)
   - 接收客户端周报
   - 字段验证/去重/存储

2. 数据聚合 (定时任务)
   - 模块热度TOP10
   - 补丁类型分布
   - 周环比变化

3. Web管理 (/web/)
   - 周数据表
   - 热力图/趋势图
   - 数据下载

4. 邮件系统 (/api/email/)
   - SMTP 邮件发送
   - 周报邮件生成
   - 定时任务调度
   - 客户端邮箱同步
"""

from .email_sender import (
    EmailConfig,
    EmailSender,
    WeeklyReportGenerator,
    InboxSyncManager,
    get_email_sender,
    get_inbox_sync_manager,
    send_weekly_report,
)

from .email_tasks import (
    setup_scheduled_tasks,
    start_scheduler,
    stop_scheduler,
    get_scheduled_jobs,
    trigger_weekly_email_now,
    trigger_client_sync_now,
)

__version__ = "1.1.0"

__all__ = [
    "EmailConfig",
    "EmailSender",
    "WeeklyReportGenerator",
    "InboxSyncManager",
    "get_email_sender",
    "get_inbox_sync_manager",
    "send_weekly_report",
    "setup_scheduled_tasks",
    "start_scheduler",
    "stop_scheduler",
    "get_scheduled_jobs",
    "trigger_weekly_email_now",
    "trigger_client_sync_now",
]
