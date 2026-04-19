# =================================================================
# TaskProgress - 任务进度管理器
# =================================================================

from PyQt6.QtCore import QObject, pyqtSignal


class TaskProgressManager(QObject):
    """任务进度管理器（占位）"""

    task_updated = pyqtSignal(str, int)  # task_id, progress
    task_completed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def update_progress(self, task_id: str, progress: int):
        """更新进度"""
        self.task_updated.emit(task_id, progress)


_global_manager = None


def get_task_progress_manager(parent=None) -> TaskProgressManager:
    """获取任务进度管理器单例"""
    global _global_manager
    if _global_manager is None:
        _global_manager = TaskProgressManager(parent)
    return _global_manager


__all__ = ['TaskProgressManager', 'get_task_progress_manager']