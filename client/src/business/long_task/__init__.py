"""
长任务管理模块 (Long Task Management)

整合三大核心能力：
1. 流式处理 - 处理超长文本
2. 智能去重 - 内容和语义级去重
3. 进程隔离 - 进程级隔离和看门狗

参考文档：工程化容错体系设计
"""

from .stream_processor import (
    StreamProcessor,
    get_stream_processor,
    ChunkResult,
    TaskProgress
)

from .smart_deduplication import (
    SmartDeduplication,
    get_smart_deduplication,
    DeduplicationResult
)

from .process_isolation import (
    ProcessIsolationManager,
    get_process_isolation_manager,
    TaskInfo
)

from .integration import (
    LongTaskIntegration,
    get_long_task_integration,
    execute_task,
    get_task_status_info
)


class LongTaskManager:
    """长任务管理器 - 统一接口"""
    
    def __init__(self):
        self._stream_processor = get_stream_processor()
        self._deduplication = get_smart_deduplication()
        self._process_manager = get_process_isolation_manager()
    
    # ===== 流式处理 =====
    
    def process_long_text(self, file_path: str, task_id: str = None, chunk_size: int = 8192):
        """流式处理超长文本文件"""
        return self._stream_processor.process_long_text(file_path, task_id, chunk_size)
    
    def process_text_stream(self, text: str, chunk_size: int = 8192):
        """流式处理内存中的超长文本"""
        return self._stream_processor.process_text_stream(text, chunk_size)
    
    def get_stream_progress(self, task_id: str):
        """获取流式处理进度"""
        return self._stream_processor.get_progress(task_id)
    
    def cancel_stream_task(self, task_id: str):
        """取消流式处理任务"""
        self._stream_processor.cancel_task(task_id)
    
    # ===== 智能去重 =====
    
    def check_duplicate(self, content: str, content_id: str = None):
        """综合去重检查"""
        return self._deduplication.check_duplicate(content, content_id)
    
    def is_duplicate_content(self, content: str):
        """内容级去重检查"""
        return self._deduplication.is_duplicate_content(content)
    
    def is_duplicate_semantic(self, content: str, content_id: str = None):
        """语义级去重检查"""
        return self._deduplication.is_duplicate_semantic(content, content_id)
    
    def set_semantic_threshold(self, threshold: float):
        """设置语义相似度阈值"""
        self._deduplication.set_semantic_threshold(threshold)
    
    # ===== 进程隔离 =====
    
    def submit_task(self, func, *args, **kwargs):
        """提交任务"""
        return self._process_manager.submit_task(func, *args, **kwargs)
    
    def run_task(self, task_id: str, timeout: int = 3600):
        """运行任务（同步）"""
        return self._process_manager.run_task(task_id, timeout)
    
    def run_task_async(self, task_id: str, timeout: int = 3600):
        """运行任务（异步）"""
        self._process_manager.run_task_async(task_id, timeout)
    
    def cancel_task(self, task_id: str):
        """取消任务"""
        self._process_manager.cancel_task(task_id)
    
    def get_task_status(self, task_id: str):
        """获取任务状态"""
        return self._process_manager.get_task_status(task_id)
    
    def shutdown(self):
        """关闭管理器"""
        self._process_manager.shutdown()


# 单例模式
_long_task_manager_instance = None

def get_long_task_manager() -> LongTaskManager:
    """获取长任务管理器实例"""
    global _long_task_manager_instance
    if _long_task_manager_instance is None:
        _long_task_manager_instance = LongTaskManager()
    return _long_task_manager_instance


# 便捷导出
__all__ = [
    # 流式处理
    "StreamProcessor",
    "get_stream_processor",
    "ChunkResult",
    "TaskProgress",
    
    # 智能去重
    "SmartDeduplication",
    "get_smart_deduplication",
    "DeduplicationResult",
    
    # 进程隔离
    "ProcessIsolationManager",
    "get_process_isolation_manager",
    "TaskInfo",
    
    # 统一接口
    "LongTaskManager",
    "get_long_task_manager",
    
    # 系统集成
    "LongTaskIntegration",
    "get_long_task_integration",
    "execute_task",
    "get_task_status_info"
]