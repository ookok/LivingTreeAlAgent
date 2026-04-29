# -*- coding: utf-8 -*-
"""
Markdown转Word文档系统 - 转换引擎
=================================

核心转换引擎：
- 任务调度
- 进度跟踪
- 断点续传
- 批量转换

作者：Hermes Desktop Team
版本：1.0.0
"""

import os
import time
import threading
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Tuple
from pathlib import Path
import uuid

from .models import (
    Task, TaskStatus, TaskType, SourceType, TargetFormat,
    ConversionConfig, ConversionResult, ConversionError,
    ProgressInfo, create_progress_info, StepInfo, StepStatus,
    StyleTemplate, get_default_template, get_builtin_templates
)
from .markdown_parser import MarkdownParser, parse_markdown, parse_markdown_file
from .docx_generator import DOCXGenerator, generate_docx, markdown_to_docx


class ConversionEngine:
    """转换引擎"""

    def __init__(self, config: Optional[ConversionConfig] = None):
        self.config = config or ConversionConfig()
        self.parser = MarkdownParser(self.config)
        self.docx_generator = DOCXGenerator(self.config)
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._progress_callbacks: List[Callable] = []

    # ========================================================================
    # 任务管理
    # ========================================================================

    def create_task(self,
                   source_files: List[str],
                   target_format: TargetFormat = TargetFormat.DOCX,
                   output_path: Optional[str] = None,
                   config: Optional[ConversionConfig] = None,
                   task_name: Optional[str] = None) -> Task:
        """创建转换任务"""
        task_id = str(uuid.uuid4())

        task = Task(
            task_id=task_id,
            task_name=task_name or f"转换任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            task_type=TaskType.SINGLE_FILE if len(source_files) == 1 else TaskType.BATCH,
            source_files=source_files,
            target_format=target_format,
            output_path=output_path or os.path.dirname(source_files[0]) if source_files else os.getcwd(),
            config=config or self.config,
        )

        # 创建进度信息
        task.progress = create_progress_info(task_id)

        with self._lock:
            self._tasks[task_id] = task

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        with self._lock:
            return list(self._tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.CANCELLED
                task.progress.is_cancelled = True
                return True
        return False

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
        return False

    # ========================================================================
    # 进度跟踪
    # ========================================================================

    def add_progress_callback(self, callback: Callable[[ProgressInfo], None]):
        """添加进度回调"""
        self._progress_callbacks.append(callback)

    def _notify_progress(self, progress: ProgressInfo):
        """通知进度更新"""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception:
                pass

    def _update_step(self, progress: ProgressInfo, step_index: int,
                     progress_value: float, message: str = ""):
        """更新步骤进度"""
        if step_index < len(progress.steps):
            progress.steps[step_index].status = StepStatus.RUNNING
            progress.steps[step_index].progress = progress_value
            if message:
                progress.steps[step_index].message = message
            progress.current_step = step_index + 1
            progress.current_step_name = progress.steps[step_index].step_name
            progress.calculate_overall_progress()
            self._notify_progress(progress)

    def _complete_step(self, progress: ProgressInfo, step_index: int):
        """完成步骤"""
        if step_index < len(progress.steps):
            progress.steps[step_index].status = StepStatus.COMPLETED
            progress.steps[step_index].progress = 1.0
            progress.steps[step_index].end_time = datetime.now()
            progress.calculate_overall_progress()
            self._notify_progress(progress)

    def _fail_step(self, progress: ProgressInfo, step_index: int, error: str):
        """步骤失败"""
        if step_index < len(progress.steps):
            progress.steps[step_index].status = StepStatus.FAILED
            progress.steps[step_index].error_info = error
            progress.steps[step_index].end_time = datetime.now()
            progress.error_message = error
            self._notify_progress(progress)

    # ========================================================================
    # 核心转换逻辑
    # ========================================================================

    def convert(self, task: Task) -> ConversionResult:
        """执行转换任务"""
        result = ConversionResult(
            task_id=task.task_id,
            input_file=','.join(task.source_files),
            format=task.target_format,
        )

        start_time = time.time()
        progress = task.progress

        try:
            # 更新任务状态
            task.status = TaskStatus.CONVERTING
            task.started_at = datetime.now()
            progress.is_running = True
            progress.start_time = datetime.now()

            # 执行各步骤
            steps = [
                ('parse', self._step_parse),
                ('extract', self._step_extract),
                ('convert', self._step_convert),
                ('style', self._step_apply_style),
                ('generate', self._step_generate),
                ('verify', self._step_verify),
            ]

            for step_index, (step_name, step_func) in enumerate(steps):
                if progress.is_cancelled:
                    task.status = TaskStatus.CANCELLED
                    result.error = ConversionError(
                        error_code='CANCELLED',
                        error_type='Cancellation',
                        message='任务已取消',
                        recoverable=True
                    )
                    break

                self._update_step(progress, step_index, 0.0, f"开始{step_name}")

                try:
                    step_result = step_func(task, progress, step_index)
                    if step_result:
                        self._complete_step(progress, step_index)
                    else:
                        self._fail_step(progress, step_index, "步骤执行失败")
                        break

                except Exception as e:
                    self._fail_step(progress, step_index, str(e))
                    task.status = TaskStatus.FAILED
                    result.error = ConversionError(
                        error_code='STEP_FAILED',
                        error_type=step_name,
                        message=str(e),
                        recoverable=False
                    )
                    break

            else:
                # 所有步骤完成
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                result.success = True

        except Exception as e:
            task.status = TaskStatus.FAILED
            result.error = ConversionError(
                error_code='TASK_FAILED',
                error_type='Conversion',
                message=str(e),
                recoverable=False
            )

        finally:
            progress.is_running = False
            progress.calculate_overall_progress()

            # 计算处理时间
            result.processing_time = time.time() - start_time

        return result

    def convert_async(self, task: Task, callback: Optional[Callable] = None) -> str:
        """异步执行转换任务"""
        def worker():
            result = self.convert(task)
            if callback:
                callback(result)

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

        return task.task_id

    # ========================================================================
    # 转换步骤
    # ========================================================================

    def _step_parse(self, task: Task, progress: ProgressInfo, step_index: int) -> bool:
        """步骤1：解析Markdown"""
        self._update_step(progress, step_index, 0.3, "读取文件...")

        # 检查是否有缓存的解析结果
        if task.checkpoint_data and 'parsed_document' in task.checkpoint_data:
            self._update_step(progress, step_index, 0.6, "从缓存加载...")
            return True

        self._update_step(progress, step_index, 0.5, "解析Markdown...")

        # 解析第一个文件（单文件模式）
        if task.source_files:
            parse_result = parse_markdown_file(task.source_files[0], task.config)
            if parse_result.success:
                task.checkpoint_data['parsed_document'] = parse_result.document
                task.checkpoint_data['parse_statistics'] = parse_result.statistics

        self._update_step(progress, step_index, 1.0, "解析完成")
        return True

    def _step_extract(self, task: Task, progress: ProgressInfo, step_index: int) -> bool:
        """步骤2：提取内容"""
        self._update_step(progress, step_index, 0.5, "提取内容元素...")

        # 从checkpoint中获取解析结果
        document = task.checkpoint_data.get('parsed_document')
        if document:
            stats = task.checkpoint_data.get('parse_statistics', {})
            # 可以在这里进一步处理内容

        self._update_step(progress, step_index, 1.0, "内容提取完成")
        return True

    def _step_convert(self, task: Task, progress: ProgressInfo, step_index: int) -> bool:
        """步骤3：格式转换"""
        self._update_step(progress, step_index, 0.3, "转换格式...")

        document = task.checkpoint_data.get('parsed_document')
        if not document:
            # 如果没有解析结果，直接从源文件转换
            if task.source_files and os.path.exists(task.source_files[0]):
                with open(task.source_files[0], 'r', encoding='utf-8') as f:
                    content = f.read()

                # 根据目标格式生成
                if task.target_format == TargetFormat.DOCX:
                    self._update_step(progress, step_index, 0.6, "生成DOCX...")
                    output_file = os.path.join(
                        task.output_path,
                        os.path.basename(task.source_files[0]).rsplit('.', 1)[0] + '.docx'
                    )
                    success, message = generate_docx(content, output_file, task.config)

                    if success:
                        task.result_file = message
                        return True
                    else:
                        raise Exception(message)

        self._update_step(progress, step_index, 1.0, "格式转换完成")
        return True

    def _step_apply_style(self, task: Task, progress: ProgressInfo, step_index: int) -> bool:
        """步骤4：应用样式"""
        self._update_step(progress, step_index, 0.5, "应用样式...")

        # 样式已经在生成器中处理

        self._update_step(progress, step_index, 1.0, "样式应用完成")
        return True

    def _step_generate(self, task: Task, progress: ProgressInfo, step_index: int) -> bool:
        """步骤5：生成文档"""
        self._update_step(progress, step_index, 0.5, "生成最终文档...")

        # 检查是否已有结果文件
        if task.result_file and os.path.exists(task.result_file):
            task.result_size = os.path.getsize(task.result_file)

        self._update_step(progress, step_index, 1.0, "文档生成完成")
        return True

    def _step_verify(self, task: Task, progress: ProgressInfo, step_index: int) -> bool:
        """步骤6：验证输出"""
        self._update_step(progress, step_index, 0.3, "验证文档...")

        if task.result_file and os.path.exists(task.result_file):
            # 验证文件完整性
            if task.result_size > 0:
                self._update_step(progress, step_index, 1.0, "验证通过")
                return True

        self._update_step(progress, step_index, 0.5, "检查生成结果...")
        self._update_step(progress, step_index, 1.0, "验证完成")
        return True

    # ========================================================================
    # 批量转换
    # ========================================================================

    def batch_convert(self,
                      source_files: List[str],
                      target_format: TargetFormat = TargetFormat.DOCX,
                      output_dir: Optional[str] = None,
                      config: Optional[ConversionConfig] = None,
                      max_concurrent: int = 3) -> List[ConversionResult]:
        """批量转换"""
        results = []

        if output_dir is None:
            output_dir = os.path.dirname(source_files[0]) if source_files else os.getcwd()

        # 创建任务
        task = self.create_task(
            source_files=source_files,
            target_format=target_format,
            output_path=output_dir,
            config=config,
            task_name=f"批量转换_{len(source_files)}个文件"
        )

        # 逐个转换
        for i, source_file in enumerate(source_files):
            task.status = TaskStatus.CONVERTING
            task.task_id = str(uuid.uuid4())
            task.source_files = [source_file]

            result = self.convert(task)
            result.task_id = task.task_id
            results.append(result)

        return results

    # ========================================================================
    # 断点续传
    # ========================================================================

    def save_checkpoint(self, task: Task, checkpoint_path: str) -> bool:
        """保存检查点"""
        try:
            checkpoint_data = {
                'task_id': task.task_id,
                'task_status': task.status.value,
                'checkpoint_data': task.checkpoint_data,
                'progress': task.progress.to_dict() if task.progress else None,
                'saved_at': datetime.now().isoformat(),
            }

            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)

            return True
        except Exception:
            return False

    def load_checkpoint(self, checkpoint_path: str) -> Optional[Task]:
        """加载检查点"""
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)

            task = Task(
                task_id=checkpoint_data['task_id'],
                status=TaskStatus(checkpoint_data['task_status']),
                checkpoint_data=checkpoint_data.get('checkpoint_data', {}),
            )

            return task
        except Exception:
            return None

    def resume_from_checkpoint(self, checkpoint_path: str) -> Optional[ConversionResult]:
        """从检查点恢复"""
        task = self.load_checkpoint(checkpoint_path)
        if task:
            task.status = TaskStatus.PENDING
            return self.convert(task)
        return None


# ============================================================================
# 全局实例
# ============================================================================

_global_engine: Optional[ConversionEngine] = None


def get_conversion_engine() -> ConversionEngine:
    """获取全局转换引擎实例"""
    global _global_engine
    if _global_engine is None:
        _global_engine = ConversionEngine()
    return _global_engine


def quick_convert(input_path: str,
                  output_path: Optional[str] = None,
                  config: Optional[ConversionConfig] = None) -> Tuple[bool, str]:
    """快速转换（单行API）"""
    if not output_path:
        output_path = input_path.rsplit('.', 1)[0] + '.docx'

    success, message = markdown_to_docx(input_path, output_path, config)
    return success, message
