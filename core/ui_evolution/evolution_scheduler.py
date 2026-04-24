# -*- coding: utf-8 -*-
"""
进化调度器 (Evolution Scheduler)
================================

管理 UI 预测系统的三级进化机制：

1. 即时学习（秒级）: RAG 知识库实时更新
2. 增量训练（小时级）: 重新训练 TF-IDF 模型
3. 深度优化（周级）: 模型调优

Author: LivingTreeAI Team
Date: 2026-04-24
"""

import json
import threading
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import queue


# =============================================================================
# 数据模型
# =============================================================================

class EvolutionLevel(Enum):
    """进化级别"""
    INSTANT = "instant"      # 即时学习（秒级）
    INCREMENTAL = "incremental"  # 增量训练（小时级）
    DEEP = "deep"            # 深度优化（周级）


@dataclass
class EvolutionTask:
    """进化任务"""
    task_id: str
    level: EvolutionLevel
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed
    data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class EvolutionStats:
    """进化统计"""
    instant_updates: int = 0      # 即时更新次数
    incremental_trains: int = 0   # 增量训练次数
    deep_optimizations: int = 0   # 深度优化次数
    
    last_instant: Optional[datetime] = None
    last_incremental: Optional[datetime] = None
    last_deep: Optional[datetime] = None
    
    total_samples: int = 0        # 累计样本数
    model_accuracy: float = 0.0    # 当前模型准确率
    
    pending_tasks: int = 0         # 待处理任务


# =============================================================================
# 知识条目
# =============================================================================

@dataclass
class KnowledgeEntry:
    """知识库条目"""
    id: Optional[int] = None
    context_pattern: str = ""      # 上下文模式
    action: str = ""               # 操作
    success_rate: float = 1.0      # 成功率
    usage_count: int = 0           # 使用次数
    last_used: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    is_positive: bool = True       # 是否正向样本


class KnowledgeBase:
    """
    轻量级知识库（RAG 引擎）
    
    存储操作-上下文映射，支持即时检索和更新。
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path.home() / ".hermes-desktop" / "ui_knowledge.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._entries: Dict[str, List[KnowledgeEntry]] = defaultdict(list)
        self._lock = threading.Lock()
        
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_pattern TEXT NOT NULL,
                action TEXT NOT NULL,
                success_rate REAL DEFAULT 1.0,
                usage_count INTEGER DEFAULT 0,
                last_used TEXT,
                created_at TEXT,
                is_positive INTEGER DEFAULT 1
            )
        """)
        
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_pattern ON knowledge(context_pattern)")
        self._conn.commit()
    
    def add_entry(
        self,
        context_pattern: str,
        action: str,
        success: bool = True,
    ):
        """添加知识条目"""
        with self._lock:
            # 检查是否已存在
            cursor = self._conn.execute("""
                SELECT * FROM knowledge 
                WHERE context_pattern = ? AND action = ?
            """, (context_pattern, action))
            
            row = cursor.fetchone()
            
            if row:
                # 更新现有条目
                new_count = row["usage_count"] + 1
                new_rate = (row["success_rate"] * row["usage_count"] + (1 if success else 0)) / new_count
                
                self._conn.execute("""
                    UPDATE knowledge 
                    SET usage_count = ?,
                        success_rate = ?,
                        last_used = ?,
                        is_positive = ?
                    WHERE id = ?
                """, (
                    new_count,
                    new_rate,
                    datetime.now().isoformat(),
                    1 if success else 0,
                    row["id"],
                ))
            else:
                # 新增条目
                self._conn.execute("""
                    INSERT INTO knowledge 
                    (context_pattern, action, success_rate, usage_count, last_used, created_at, is_positive)
                    VALUES (?, ?, ?, 1, ?, ?, ?)
                """, (
                    context_pattern,
                    action,
                    1.0 if success else 0.0,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    1 if success else 0,
                ))
            
            self._conn.commit()
    
    def search(
        self,
        context_pattern: str,
        limit: int = 5,
    ) -> List[KnowledgeEntry]:
        """搜索相关知识"""
        with self._lock:
            cursor = self._conn.execute("""
                SELECT * FROM knowledge 
                WHERE context_pattern LIKE ?
                ORDER BY success_rate DESC, usage_count DESC
                LIMIT ?
            """, (f"%{context_pattern}%", limit))
            
            entries = []
            for row in cursor.fetchall():
                entries.append(KnowledgeEntry(
                    id=row["id"],
                    context_pattern=row["context_pattern"],
                    action=row["action"],
                    success_rate=row["success_rate"],
                    usage_count=row["usage_count"],
                    last_used=datetime.fromisoformat(row["last_used"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    is_positive=bool(row["is_positive"]),
                ))
            
            return entries
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        with self._lock:
            cursor = self._conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(usage_count) as total_usage,
                       AVG(success_rate) as avg_rate
                FROM knowledge
            """)
            
            row = cursor.fetchone()
            return {
                "total_entries": row[0] or 0,
                "total_usage": row[1] or 0,
                "avg_success_rate": row[2] or 0.0,
            }


# =============================================================================
# 进化调度器
# =============================================================================

class EvolutionScheduler:
    """
    进化调度器
    
    管理三级进化机制：
    1. 即时学习：记录到知识库，立即生效
    2. 增量训练：积累样本后重新训练模型
    3. 深度优化：定期全量优化
    """
    
    # 配置
    INSTANT_THRESHOLD = 1       # 即时学习阈值
    INCREMENTAL_THRESHOLD = 50  # 增量训练样本数
    DEEP_THRESHOLD = 500        # 深度优化样本数
    
    # 调度间隔
    INSTANT_INTERVAL = 0        # 即时
    INCREMENTAL_INTERVAL = 3600  # 1小时
    DEEP_INTERVAL = 604800       # 1周
    
    def __init__(
        self,
        predictor,  # TFIDFPredictor
        feedback_collector,  # FeedbackCollector
        model_save_path: str = None,
    ):
        self.predictor = predictor
        self.feedback_collector = feedback_collector
        self.knowledge_base = KnowledgeBase()
        
        self.model_save_path = Path(model_save_path) if model_save_path else None
        
        # 任务队列
        self._task_queue: queue.Queue = queue.Queue()
        
        # 统计
        self._stats = EvolutionStats()
        
        # 锁
        self._lock = threading.Lock()
        
        # 运行状态
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # 回调
        self._callbacks: Dict[EvolutionLevel, List[Callable]] = defaultdict(list)
    
    def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
    
    def stop(self):
        """停止调度器"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
    
    def _worker_loop(self):
        """工作循环"""
        while self._running:
            try:
                # 处理任务队列
                try:
                    task = self._task_queue.get(timeout=1)
                    self._execute_task(task)
                except queue.Empty:
                    pass
                
                # 检查定时任务
                self._check_scheduled_tasks()
                
            except Exception as e:
                print(f"进化调度器错误: {e}")
    
    def _check_scheduled_tasks(self):
        """检查定时任务"""
        now = datetime.now()
        
        # 检查增量训练
        if self._stats.last_incremental is None or \
           (now - self._stats.last_incremental).total_seconds() >= self.INCREMENTAL_INTERVAL:
            samples = self.feedback_collector.get_training_data(min_samples=10)
            if len(samples) >= self.INCREMENTAL_THRESHOLD:
                self.schedule_evolution(EvolutionLevel.INCREMENTAL)
    
    def schedule_evolution(
        self,
        level: EvolutionLevel,
        data: Dict[str, Any] = None,
    ):
        """调度进化任务"""
        task = EvolutionTask(
            task_id=f"{level.value}_{int(time.time())}",
            level=level,
            data=data or {},
        )
        
        if level == EvolutionLevel.INSTANT:
            task.scheduled_at = datetime.now()
        elif level == EvolutionLevel.INCREMENTAL:
            task.scheduled_at = datetime.now()
        else:
            task.scheduled_at = datetime.now() + timedelta(seconds=self.DEEP_INTERVAL)
        
        self._task_queue.put(task)
        
        with self._lock:
            self._stats.pending_tasks += 1
    
    def _execute_task(self, task: EvolutionTask):
        """执行进化任务"""
        task.status = "running"
        
        try:
            if task.level == EvolutionLevel.INSTANT:
                self._execute_instant_learning(task)
            elif task.level == EvolutionLevel.INCREMENTAL:
                self._execute_incremental_training(task)
            elif task.level == EvolutionLevel.DEEP:
                self._execute_deep_optimization(task)
            
            task.status = "completed"
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
        
        finally:
            with self._lock:
                self._stats.pending_tasks -= 1
            
            # 执行回调
            for callback in self._callbacks[task.level]:
                try:
                    callback(task)
                except Exception:
                    pass
    
    def _execute_instant_learning(self, task: EvolutionTask):
        """即时学习"""
        # 从反馈收集器获取最新数据
        data = task.data
        
        # 提取上下文和动作
        context = data.get("context", "")
        action = data.get("action", "")
        success = data.get("success", True)
        
        if context and action:
            # 添加到知识库
            self.knowledge_base.add_entry(context, action, success)
            
            # 更新预测器
            sequence = data.get("sequence", [])
            self.predictor.incremental_update(sequence, action, success)
            
            # 更新统计
            with self._lock:
                self._stats.instant_updates += 1
                self._stats.last_instant = datetime.now()
                self._stats.total_samples += 1
    
    def _execute_incremental_training(self, task: EvolutionTask):
        """增量训练"""
        # 获取训练数据
        training_data = self.feedback_collector.get_training_data(min_samples=10)
        
        if len(training_data) < self.INCREMENTAL_THRESHOLD:
            return
        
        # 提取序列
        sequences = [item["sequence"] for item in training_data]
        
        # 训练模型
        self.predictor.train(
            sequences,
            save_path=str(self.model_save_path) if self.model_save_path else None,
        )
        
        # 更新统计
        with self._lock:
            self._stats.incremental_trains += 1
            self._stats.last_incremental = datetime.now()
            self._stats.total_samples = len(training_data)
            
            # 更新模型准确率
            stats = self.feedback_collector.get_stats()
            self._stats.model_accuracy = stats.acceptance_rate
        
        task.result = {
            "samples_trained": len(training_data),
            "model_saved": str(self.model_save_path) if self.model_save_path else None,
        }
    
    def _execute_deep_optimization(self, task: EvolutionTask):
        """深度优化"""
        # TODO: 实现深度优化（Prompt Tuning / LoRA）
        # 目前仅记录
        with self._lock:
            self._stats.deep_optimizations += 1
            self._stats.last_deep = datetime.now()
    
    def on_evolution(self, level: EvolutionLevel, callback: Callable):
        """注册进化回调"""
        self._callbacks[level].append(callback)
    
    def trigger_learning(
        self,
        context: str,
        action: str,
        sequence: List[str],
        success: bool = True,
    ):
        """触发即时学习"""
        self.schedule_evolution(
            EvolutionLevel.INSTANT,
            data={
                "context": context,
                "action": action,
                "sequence": sequence,
                "success": success,
            }
        )
    
    def get_stats(self) -> EvolutionStats:
        """获取统计"""
        with self._lock:
            stats = EvolutionStats(
                instant_updates=self._stats.instant_updates,
                incremental_trains=self._stats.incremental_trains,
                deep_optimizations=self._stats.deep_optimizations,
                last_instant=self._stats.last_instant,
                last_incremental=self._stats.last_incremental,
                last_deep=self._stats.last_deep,
                total_samples=self._stats.total_samples,
                model_accuracy=self._stats.model_accuracy,
                pending_tasks=self._stats.pending_tasks,
            )
            return stats
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """获取知识库统计"""
        return self.knowledge_base.get_stats()


# =============================================================================
# 全局实例管理
# =============================================================================

_global_scheduler: Optional[EvolutionScheduler] = None


def get_evolution_scheduler() -> EvolutionScheduler:
    """获取全局进化调度器"""
    global _global_scheduler
    
    if _global_scheduler is None:
        # 导入依赖
        from .tfidf_predictor import get_predictor
        from .feedback_collector import get_feedback_collector
        
        _global_scheduler = EvolutionScheduler(
            predictor=get_predictor(),
            feedback_collector=get_feedback_collector(),
        )
        _global_scheduler.start()
    
    return _global_scheduler


# =============================================================================
# 便捷函数
# =============================================================================

def trigger_learning(
    context: str,
    action: str,
    sequence: List[str],
    success: bool = True,
):
    """
    触发即时学习
    
    使用示例:
    ```python
    from core.ui_evolution import trigger_learning
    
    # 用户接受了建议
    trigger_learning(
        context="click:send",
        action="click:send",
        sequence=["click:input", "input:msg"],
        success=True,
    )
    
    # 用户纠正了建议
    trigger_learning(
        context="click:send",
        action="click:cancel",  # 实际执行的操作
        sequence=["click:input", "input:msg"],
        success=False,
    )
    ```
    """
    scheduler = get_evolution_scheduler()
    scheduler.trigger_learning(context, action, sequence, success)


def get_evolution_status() -> Dict[str, Any]:
    """获取进化状态"""
    scheduler = get_evolution_scheduler()
    stats = scheduler.get_stats()
    
    return {
        "instant_updates": stats.instant_updates,
        "incremental_trains": stats.incremental_trains,
        "deep_optimizations": stats.deep_optimizations,
        "total_samples": stats.total_samples,
        "model_accuracy": f"{stats.model_accuracy:.1%}",
        "last_instant": stats.last_instant.isoformat() if stats.last_instant else None,
        "last_incremental": stats.last_incremental.isoformat() if stats.last_incremental else None,
        "knowledge_entries": scheduler.get_knowledge_stats(),
    }
