# -*- coding: utf-8 -*-
"""
实时协作模块 - Real-time Collaboration Module
=============================================

功能：
1. 团队工作空间
2. 实时多人编辑
3. 任务分配与追踪
4. 评论与反馈
5. 通知系统

Author: Hermes Desktop Team
"""

from .workspace import Workspace, WorkspaceMember, WorkspaceRole
from .presence import PresenceManager, UserPresence
from .comments import Comment, CommentThread
from .notifications import Notification, NotificationManager
from .tasks import TeamTask, TaskAssignment

__all__ = [
    'Workspace',
    'WorkspaceMember',
    'WorkspaceRole',
    'PresenceManager',
    'UserPresence',
    'Comment',
    'CommentThread',
    'Notification',
    'NotificationManager',
    'TeamTask',
    'TaskAssignment',
]
