"""
流式处理器 (Stream Processor)

核心功能：
1. 滑动窗口分块处理超长文本
2. 支持断点续传机制
3. 内存占用恒定，与文件大小无关

参考文档：超长问答：流式分块与断点续传
"""

import os
import uuid
import json
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ChunkResult:
    """分块处理结果"""
    chunk_index: int
    content: str
    metadata: Dict = field(default_factory=dict)
    is_last: bool = False


@dataclass
class TaskProgress:
    """任务进度档案"""
    task_id: str
    file_path: str
    processed_chunks: int = 0
    total_chunks: int = 0
    checkpoint_path: str = ""
    status: str = "pending"  # pending/running/completed/failed
    error_message: str = ""
    created_at: float = field(default_factory=lambda: 0.0)
    updated_at: float = field(default_factory=lambda: 0.0)


class StreamProcessor:
    """流式处理器 - 处理超长文本的核心组件"""
    
    DEFAULT_CHUNK_SIZE = 8192  # 8KB
    CHECKPOINT_DIR = "./checkpoints"
    
    def __init__(self):
        self._logger = logger.bind(component="StreamProcessor")
        self._progress_cache: Dict[str, TaskProgress] = {}
        
        # 创建检查点目录
        os.makedirs(self.CHECKPOINT_DIR, exist_ok=True)
    
    def process_long_text(self, file_path: str, task_id: str = None, 
                        chunk_size: int = DEFAULT_CHUNK_SIZE) -> Generator[ChunkResult, None, None]:
        """
        流式处理超长文本
        
        Args:
            file_path: 文件路径
            task_id: 任务ID（可选，用于断点续传）
            chunk_size: 分块大小（默认8KB）
        
        Yields:
            分块处理结果
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 生成任务ID
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        # 获取文件大小和总分块数
        file_size = os.path.getsize(file_path)
        total_chunks = (file_size // chunk_size) + 1
        
        # 加载检查点（如果存在）
        progress = self._load_checkpoint(task_id)
        if progress.processed_chunks > 0:
            self._logger.info(f"从断点恢复任务: {task_id}, 已处理 {progress.processed_chunks}/{total_chunks}")
        
        # 打开文件并定位到断点
        with open(file_path, 'rb') as f:
            # 跳过已处理的块
            f.seek(progress.processed_chunks * chunk_size)
            
            chunk_index = progress.processed_chunks
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                # 处理当前块
                result = ChunkResult(
                    chunk_index=chunk_index,
                    content=chunk.decode('utf-8', errors='replace'),
                    is_last=(chunk_index == total_chunks - 1)
                )
                
                yield result
                
                # 更新进度并保存检查点
                chunk_index += 1
                self._update_progress(task_id, chunk_index, total_chunks, file_path)
        
        # 标记任务完成
        self._complete_task(task_id)
        self._logger.info(f"任务完成: {task_id}")
    
    def process_text_stream(self, text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Generator[ChunkResult, None, None]:
        """
        流式处理内存中的超长文本
        
        Args:
            text: 超长文本内容
            chunk_size: 分块大小
        
        Yields:
            分块处理结果
        """
        total_chunks = (len(text) // chunk_size) + 1
        
        for i in range(total_chunks):
            start = i * chunk_size
            end = min((i + 1) * chunk_size, len(text))
            chunk_content = text[start:end]
            
            yield ChunkResult(
                chunk_index=i,
                content=chunk_content,
                is_last=(i == total_chunks - 1)
            )
    
    def _update_progress(self, task_id: str, processed_chunks: int, total_chunks: int, file_path: str):
        """更新任务进度并保存检查点"""
        checkpoint_path = os.path.join(self.CHECKPOINT_DIR, f"{task_id}.ckpt")
        
        progress = TaskProgress(
            task_id=task_id,
            file_path=file_path,
            processed_chunks=processed_chunks,
            total_chunks=total_chunks,
            checkpoint_path=checkpoint_path,
            status="running",
            updated_at=0.0  # 简化实现
        )
        
        self._progress_cache[task_id] = progress
        
        # 保存到文件
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump({
                "task_id": task_id,
                "file_path": file_path,
                "processed_chunks": processed_chunks,
                "total_chunks": total_chunks,
                "checkpoint_path": checkpoint_path,
                "status": "running",
                "updated_at": 0.0
            }, f, ensure_ascii=False)
    
    def _load_checkpoint(self, task_id: str) -> TaskProgress:
        """加载任务检查点"""
        checkpoint_path = os.path.join(self.CHECKPOINT_DIR, f"{task_id}.ckpt")
        
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return TaskProgress(**data)
            except Exception as e:
                self._logger.warning(f"加载检查点失败: {e}")
        
        return TaskProgress(task_id=task_id, file_path="", processed_chunks=0)
    
    def _complete_task(self, task_id: str):
        """标记任务完成并清理检查点"""
        checkpoint_path = os.path.join(self.CHECKPOINT_DIR, f"{task_id}.ckpt")
        
        if os.path.exists(checkpoint_path):
            try:
                os.remove(checkpoint_path)
            except Exception as e:
                self._logger.warning(f"删除检查点失败: {e}")
        
        if task_id in self._progress_cache:
            self._progress_cache[task_id].status = "completed"
    
    def get_progress(self, task_id: str) -> Optional[TaskProgress]:
        """获取任务进度"""
        return self._progress_cache.get(task_id)
    
    def cancel_task(self, task_id: str):
        """取消任务并清理资源"""
        checkpoint_path = os.path.join(self.CHECKPOINT_DIR, f"{task_id}.ckpt")
        
        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
        
        if task_id in self._progress_cache:
            self._progress_cache[task_id].status = "cancelled"
            del self._progress_cache[task_id]


# 单例模式
_stream_processor_instance = None

def get_stream_processor() -> StreamProcessor:
    """获取流式处理器实例"""
    global _stream_processor_instance
    if _stream_processor_instance is None:
        _stream_processor_instance = StreamProcessor()
    return _stream_processor_instance


if __name__ == "__main__":
    print("=" * 60)
    print("流式处理器测试")
    print("=" * 60)
    
    processor = get_stream_processor()
    
    # 创建测试文件
    test_content = "这是一段超长文本的测试内容。" * 10000
    test_file = "./test_long_text.txt"
    
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"测试文件大小: {os.path.getsize(test_file)} 字节")
    
    # 测试流式处理
    print("\n[1] 流式处理测试")
    chunk_count = 0
    for chunk_result in processor.process_long_text(test_file):
        chunk_count += 1
        if chunk_count % 10 == 0:
            print(f"已处理 {chunk_count} 个块")
    
    print(f"总块数: {chunk_count}")
    
    # 测试断点续传
    print("\n[2] 断点续传测试")
    task_id = "test_resume_task"
    
    # 模拟处理一半后中断
    chunk_count = 0
    try:
        for chunk_result in processor.process_long_text(test_file, task_id=task_id):
            chunk_count += 1
            if chunk_count == 5:
                raise KeyboardInterrupt("模拟中断")
    except KeyboardInterrupt:
        print(f"任务中断，已处理 {chunk_count} 个块")
    
    # 从断点恢复
    chunk_count_resumed = 0
    for chunk_result in processor.process_long_text(test_file, task_id=task_id):
        chunk_count_resumed += 1
    
    print(f"恢复后处理块数: {chunk_count_resumed}")
    
    # 清理测试文件
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)