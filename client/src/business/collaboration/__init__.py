"""协同创作系统 - 统一调度器"""

from .collab import (
    CollaborationSystem, Workspace, Document, Version, Comment, Activity,
    User, Permission, ActivityType, CursorManager,
    create_collaboration_system
)


def create_collab_system() -> CollaborationSystem:
    return CollaborationSystem()
