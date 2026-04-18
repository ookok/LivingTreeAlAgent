"""
DocLifecycle - 自动化文档审核与文件生命周期管理系统

统一的入口模块，整合所有子模块功能。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import uuid

from .models import (
    ActivityLevel, CleanupRule, CleanupStatus, CleanupTask,
    DocumentInfo, DocumentType, FileActivity, FileTier,
    ReportInfo, ReviewLevel, ReviewResult, ReviewStatus, ReviewTask,
    StorageStats
)
from .task_scheduler import TaskScheduler, SchedulerConfig, SchedulerMode, get_task_scheduler
from .document_parser import DocumentParserEngine, get_parser_engine
from .report_generator import ReportGenerator, get_report_generator
from .activity_tracker import ActivityTracker, get_activity_tracker
from .cleanup_manager import CleanupManager, get_cleanup_manager
from .db_operations import DBOperations, get_db_operations

logger = logging.getLogger(__name__)


class DocLifecycleSystem:
    """
    自动化文档审核与文件生命周期管理系统
    
    整合以下功能:
    - 批量文档审核
    - 审核任务调度
    - 多格式报告生成
    - 文件活跃度追踪
    - 自动化清理策略
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 初始化所有子模块
        self._db_ops = get_db_operations()
        self._parser = get_parser_engine()
        self._scheduler = get_task_scheduler()
        self._report_gen = get_report_generator()
        self._activity_tracker = get_activity_tracker()
        self._cleanup_mgr = get_cleanup_manager()
        
        # 注册默认处理器
        self._scheduler.register_handler("default", self._default_review_handler)
        
        # 注册回调
        self._scheduler.register_callback("task_completed", self._on_task_completed)
        
        self._initialized = True
        logger.info("DocLifecycleSystem initialized")
    
    def _default_review_handler(self, task: ReviewTask) -> Dict[str, Any]:
        """默认审核处理器"""
        from .models import ReviewResult
        
        start_time = datetime.now()
        
        try:
            # 获取文档
            doc_info, content, metadata = self._parser.parse(task.doc_info.file_path)
            task.doc_info = doc_info
            
            # 更新进度
            task.progress = 0.3
            
            # 模拟审核分析
            import time
            import random
            
            time.sleep(0.5)  # 模拟处理
            
            # 生成随机评分
            base_score = random.uniform(60, 95)
            
            result = ReviewResult(
                task_id=task.task_id,
                doc_id=task.doc_id,
                quality_score=base_score,
                accuracy_score=base_score + random.uniform(-5, 5),
                completeness_score=base_score + random.uniform(-5, 5),
                consistency_score=base_score + random.uniform(-5, 5),
                clarity_score=base_score + random.uniform(-5, 5),
                professionalism_score=base_score + random.uniform(-5, 5),
                innovation_score=base_score + random.uniform(-10, 10),
                issues=[
                    {
                        "type": "建议",
                        "severity": "low",
                        "description": "建议添加更多示例说明"
                    }
                ] if random.random() > 0.5 else [],
                suggestions=[
                    {
                        "type": "优化建议",
                        "priority": "中",
                        "description": "可以增加文档的可读性"
                    }
                ],
                category=self._categorize_document(doc_info),
                tags=self._extract_tags(doc_info, content),
                summary=f"文档审核完成，整体质量评分 {base_score:.1f}，建议关注内容的完整性和专业性。",
                processing_time=(datetime.now() - start_time).total_seconds(),
                created_at=datetime.now()
            )
            
            # 保存结果
            self._db_ops.save_result(result)
            self._db_ops.save_document(doc_info)
            
            # 更新进度
            task.progress = 0.8
            
            return result.to_dict()
            
        except Exception as e:
            logger.error(f"Review handler error: {e}")
            raise
    
    def _categorize_document(self, doc_info: DocumentInfo) -> str:
        """文档分类"""
        categories = {
            DocumentType.TEXT: "文本",
            DocumentType.MARKDOWN: "文档",
            DocumentType.PDF: "PDF文档",
            DocumentType.DOC: "Word文档",
            DocumentType.DOCX: "Word文档",
            DocumentType.XLS: "Excel表格",
            DocumentType.XLSX: "Excel表格",
            DocumentType.CSV: "数据文件",
            DocumentType.JSON: "数据文件",
            DocumentType.CODE: "代码",
            DocumentType.HTML: "网页",
        }
        return categories.get(doc_info.file_type, "其他")
    
    def _extract_tags(self, doc_info: DocumentInfo, content: str) -> List[str]:
        """提取标签"""
        tags = []
        
        # 基于文件类型
        tags.append(doc_info.file_type.value)
        
        # 基于文件名关键词
        name_lower = doc_info.file_name.lower()
        keyword_map = {
            "report": "报告", "doc": "文档", "test": "测试",
            "spec": "规格", "api": "接口", "readme": "说明",
            "config": "配置", "log": "日志", "data": "数据"
        }
        for key, tag in keyword_map.items():
            if key in name_lower:
                tags.append(tag)
        
        return list(set(tags))[:5]
    
    def _on_task_completed(self, task: ReviewTask):
        """任务完成回调"""
        logger.info(f"Task completed: {task.task_id}")
    
    # ==================== 公开API ====================
    
    def start(self):
        """启动系统"""
        self._scheduler.start()
        self._cleanup_mgr.start_scheduler()
        logger.info("DocLifecycleSystem started")
    
    def stop(self):
        """停止系统"""
        self._scheduler.stop()
        self._cleanup_mgr.stop_scheduler()
        logger.info("DocLifecycleSystem stopped")
    
    def submit_review(self, file_paths: List[str], 
                    review_level: ReviewLevel = ReviewLevel.STANDARD,
                    priority: int = 5) -> List[str]:
        """提交文档审核"""
        task_ids = []
        
        for file_path in file_paths:
            try:
                # 解析文档
                doc_info, _, _ = self._parser.parse(file_path)
                
                # 创建任务
                task = ReviewTask(
                    task_id=str(uuid.uuid4()),
                    doc_id=doc_info.doc_id,
                    doc_info=doc_info,
                    review_level=review_level,
                    priority=priority,
                    status=ReviewStatus.PENDING
                )
                
                # 保存任务
                self._db_ops.save_task(task)
                
                # 提交调度器
                task_id = self._scheduler.submit_task(task)
                task_ids.append(task_id)
                
            except Exception as e:
                logger.error(f"Failed to submit review for {file_path}: {e}")
        
        logger.info(f"Submitted {len(task_ids)} reviews")
        return task_ids
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self._scheduler.get_task(task_id)
        if task:
            return task.to_dict()
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return self._scheduler.cancel_task(task_id)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return self._scheduler.get_queue_status()
    
    def generate_report(self, task_id: str, format: str = "html") -> Optional[ReportInfo]:
        """生成报告"""
        task = self._scheduler.get_task(task_id)
        if not task:
            return None
        
        result = self._db_ops.get_result(task_id)
        if not result:
            return None
        
        if format == "json":
            report = self._report_gen.generate_json_report(result, task)
        else:
            report = self._report_gen.generate_html_report(result, task)
        
        self._db_ops.save_report(report)
        return report
    
    def generate_batch_summary(self, task_ids: List[str]) -> Optional[ReportInfo]:
        """生成批量汇总报告"""
        results = []
        for task_id in task_ids:
            result = self._db_ops.get_result(task_id)
            if result:
                results.append(result)
        
        if not results:
            return None
        
        report = self._report_gen.generate_batch_summary(results)
        self._db_ops.save_report(report)
        return report
    
    def evaluate_file_activity(self, file_path: str) -> FileActivity:
        """评估文件活跃度"""
        return self._activity_tracker.evaluate_activity(file_path)
    
    def batch_evaluate_activity(self, file_paths: List[str]) -> List[FileActivity]:
        """批量评估文件活跃度"""
        return self._activity_tracker.batch_evaluate(file_paths)
    
    def get_cleanup_candidates(self, directory: str, 
                               max_score: float = 20) -> List[FileActivity]:
        """获取可清理文件"""
        return self._activity_tracker.get_cleanup_candidates(directory, max_score)
    
    def execute_cleanup(self, activities: List[FileActivity],
                       dry_run: bool = True) -> Dict[str, Any]:
        """执行清理"""
        tasks = self._cleanup_mgr.create_cleanup_tasks(activities, dry_run=dry_run)
        return self._cleanup_mgr.execute_cleanup(tasks, dry_run=dry_run)
    
    def get_cleanup_rules(self) -> List[CleanupRule]:
        """获取清理规则"""
        return self._cleanup_mgr.get_rules()
    
    def add_cleanup_rule(self, rule: CleanupRule) -> str:
        """添加清理规则"""
        return self._cleanup_mgr.add_rule(rule)
    
    def get_cleanup_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取清理历史"""
        return self._cleanup_mgr.get_history(limit)
    
    def get_trash_contents(self) -> List[Dict[str, Any]]:
        """获取回收站内容"""
        return self._cleanup_mgr.get_trash_contents()
    
    def restore_from_trash(self, file_path: str) -> bool:
        """从回收站恢复"""
        return self._cleanup_mgr.restore_from_trash(file_path)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._db_ops.get_stats()
    
    def get_reports(self, doc_id: Optional[str] = None) -> List[ReportInfo]:
        """获取报告列表"""
        return self._db_ops.get_reports(doc_id)
    
    def get_results(self, doc_id: Optional[str] = None) -> List[ReviewResult]:
        """获取审核结果"""
        return self._db_ops.get_results(doc_id)
    
    # ==================== 事件回调 ====================
    
    def on_task_completed(self, callback: Callable):
        """注册任务完成回调"""
        self._scheduler.register_callback("task_completed", callback)
    
    def on_cleanup_completed(self, callback: Callable):
        """注册清理完成回调"""
        self._cleanup_mgr.register_callback("cleanup_completed", callback)


# 全局实例
_system: Optional[DocLifecycleSystem] = None


def get_doc_lifecycle_system() -> DocLifecycleSystem:
    """获取文档生命周期系统实例"""
    global _system
    if _system is None:
        _system = DocLifecycleSystem()
    return _system


def quick_review(file_path: str) -> ReviewResult:
    """快速审核单个文档"""
    system = get_doc_lifecycle_system()
    
    task_ids = system.submit_review([file_path], review_level=ReviewLevel.QUICK)
    
    if task_ids:
        task_id = task_ids[0]
        # 等待完成
        import time
        for _ in range(60):  # 最多等待60秒
            status = system.get_task_status(task_id)
            if status and status.get("status") == "completed":
                return system._db_ops.get_result(task_id)
            time.sleep(1)
    
    return None


def quick_cleanup(directory: str, dry_run: bool = True) -> Dict[str, Any]:
    """快速清理目录"""
    system = get_doc_lifecycle_system()
    
    # 评估活跃度
    from pathlib import Path
    file_paths = [str(p) for p in Path(directory).rglob('*') if p.is_file()]
    
    activities = system.batch_evaluate_activity(file_paths)
    
    # 执行清理
    return system.execute_cleanup(activities, dry_run=dry_run)
