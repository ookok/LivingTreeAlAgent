"""
好奇心引擎 - 核心实现

基于强化学习中的Curiosity-driven Exploration机制，
用"信息增益(Information Gain)"作为奖励信号。
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable

from ..fusion_rag.engine import FusionRAGEngine
from ..knowledge_graph.graph import KnowledgeGraph
from .file_monitor import FileMonitor, FileChange, FileChangeType

logger = logging.getLogger(__name__)


class CuriosityLevel(Enum):
    """好奇心级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LearningTask:
    """学习任务"""
    task_id: str
    task_type: str
    description: str
    curiosity_score: float
    priority: int
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NoveltyDetection:
    """新颖性检测结果"""
    is_novel: bool
    novelty_score: float
    existing_knowledge: List[str] = field(default_factory=list)
    missing_knowledge: List[str] = field(default_factory=list)


class LearningStrategy(Enum):
    """学习策略"""
    CORE_ONLY = "core_only"       # 只学习核心文档
    CORE_FIRST = "core_first"     # 核心优先，空闲时学习其他
    ALL = "all"                   # 全部学习
    ON_DEMAND = "on_demand"       # 按需学习


class CuriosityEngine:
    """
    好奇心引擎
    
    核心能力：
    1. 自动扫描本地文件系统（极速扫描）
    2. 计算信息增益作为好奇心权重
    3. 当好奇心超过阈值时触发自主学习
    4. 管理学习任务队列
    5. 智能学习策略（核心优先/按需学习）
    """
    
    def __init__(self):
        self.file_monitor = FileMonitor()
        self.auto_scanner = AutoScanner()
        self.rag_engine = FusionRAGEngine()
        self.knowledge_graph = KnowledgeGraph()
        
        self.curiosity_threshold = 0.7
        self.learning_tasks: Dict[str, LearningTask] = {}
        self.processed_files: set = set()
        
        # 学习策略
        self.learning_strategy = LearningStrategy.CORE_FIRST
        self.max_concurrent_tasks = 3
        self.resource_limit = 0.8  # CPU/内存使用上限
        
        # 注册文件变化回调
        self.file_monitor.register_callback(self._on_file_change)
        
        # Idle循环状态
        self.is_idle_running = False
        self.idle_interval = 60  # 60秒检查一次
        
        # 扫描状态
        self.last_scan_time = 0
        self.scan_interval = 3600  # 每小时扫描一次
    
    def start(self):
        """启动好奇心引擎"""
        self.file_monitor.start()
        self._start_idle_loop()
        logger.info("🚀 好奇心引擎启动")
    
    def stop(self):
        """停止好奇心引擎"""
        self.file_monitor.stop()
        self.is_idle_running = False
        logger.info("🛑 好奇心引擎停止")
    
    def add_monitor_path(self, path: str, file_patterns: Optional[List[str]] = None):
        """添加监控路径"""
        self.file_monitor.add_monitor_path(path, file_patterns)
    
    def calculate_curiosity(self, content: str, source: str = "") -> float:
        """
        计算好奇心分数（信息增益）
        
        好奇心 = 新颖性 × 实用性
        
        Args:
            content: 新信息内容
            source: 信息来源
        
        Returns:
            好奇心分数 (0-1)
        """
        # 检测新颖性
        novelty = self._calculate_novelty(content)
        
        # 评估实用性
        utility = self._estimate_utility(content, source)
        
        # 好奇心 = 新颖性 × 实用性
        curiosity = novelty * utility
        
        logger.debug(f"📊 好奇心计算 - 新颖性: {novelty:.2f}, 实用性: {utility:.2f}, 总分: {curiosity:.2f}")
        
        return curiosity
    
    def _calculate_novelty(self, content: str) -> float:
        """
        计算新颖性分数
        
        通过对比现有知识图谱，评估信息的新颖程度。
        """
        if not content:
            return 0.0
        
        # 提取关键词/实体
        entities = self._extract_entities(content)
        
        if not entities:
            return 0.5  # 中等新颖度
        
        # 检查知识图谱中已有的实体
        known_count = 0
        unknown_count = 0
        
        for entity in entities:
            if self.knowledge_graph.has_node(entity):
                known_count += 1
            else:
                unknown_count += 1
        
        total = known_count + unknown_count
        if total == 0:
            return 0.5
        
        # 新颖性 = 未知实体比例
        novelty = unknown_count / total
        
        return min(novelty, 1.0)
    
    def _estimate_utility(self, content: str, source: str) -> float:
        """
        评估信息的实用性
        
        考虑因素：
        1. 来源权威性
        2. 与当前技能的相关性
        3. 潜在应用价值
        """
        utility = 0.5  # 基础分
        
        # 来源权重
        authoritative_sources = ["政府", "国家标准", "生态环境部", "卫健委", "GB/T", "GB"]
        for source_keyword in authoritative_sources:
            if source_keyword.lower() in source.lower() or source_keyword.lower() in content.lower():
                utility += 0.2
                break
        
        # 内容相关性
        relevant_keywords = ["标准", "规范", "导则", "方法", "计算", "模型", "评估"]
        for keyword in relevant_keywords:
            if keyword in content:
                utility += 0.1
        
        return min(utility, 1.0)
    
    def _extract_entities(self, content: str) -> List[str]:
        """
        从文本中提取实体
        
        简化实现：提取可能的专业术语
        """
        import re
        
        # 提取标准号（如 GB XXXX-XXXX）
        standards = re.findall(r"GB\s*[T/]?\s*\d+-\d+", content)
        # 提取专业术语（中文词）
        terms = re.findall(r"[\u4e00-\u9fa5]{2,8}", content)
        
        # 去重并限制数量
        entities = list(set(standards + terms))[:20]
        
        return entities
    
    def detect_novelty(self, content: str) -> NoveltyDetection:
        """检测新颖性"""
        entities = self._extract_entities(content)
        
        existing = []
        missing = []
        
        for entity in entities:
            if self.knowledge_graph.has_node(entity):
                existing.append(entity)
            else:
                missing.append(entity)
        
        is_novel = len(missing) > 0
        novelty_score = len(missing) / max(len(entities), 1)
        
        return NoveltyDetection(
            is_novel=is_novel,
            novelty_score=novelty_score,
            existing_knowledge=existing,
            missing_knowledge=missing
        )
    
    def trigger_autonomous_learning(self, content: str, source: str = "") -> Optional[LearningTask]:
        """
        触发自主学习
        
        当好奇心分数超过阈值时，创建学习任务。
        
        Args:
            content: 新信息内容
            source: 信息来源
        
        Returns:
            LearningTask 如果触发成功，否则 None
        """
        curiosity = self.calculate_curiosity(content, source)
        
        if curiosity < self.curiosity_threshold:
            logger.debug(f"😴 好奇心不足 ({curiosity:.2f} < {self.curiosity_threshold})")
            return None
        
        # 创建学习任务
        task = LearningTask(
            task_id=f"learn_{uuid.uuid4().hex[:8]}",
            task_type="autonomous_learning",
            description=f"学习新内容: {source or '未知来源'}",
            curiosity_score=curiosity,
            priority=self._calculate_priority(curiosity),
            metadata={
                "content": content[:500],
                "source": source,
                "curiosity_score": curiosity
            }
        )
        
        self.learning_tasks[task.task_id] = task
        
        logger.info(f"🧠 触发自主学习任务: {task.task_id} (好奇心: {curiosity:.2f})")
        
        # 立即执行学习任务
        asyncio.create_task(self._execute_learning_task(task))
        
        return task
    
    def _calculate_priority(self, curiosity: float) -> int:
        """根据好奇心分数计算优先级"""
        if curiosity >= 0.9:
            return 1  # 最高优先级
        elif curiosity >= 0.8:
            return 2
        elif curiosity >= 0.7:
            return 3
        else:
            return 4
    
    async def _execute_learning_task(self, task: LearningTask):
        """执行学习任务"""
        try:
            task.status = "running"
            logger.info(f"🔄 开始学习任务: {task.task_id}")
            
            # 解析内容
            content = task.metadata.get("content", "")
            
            # 检测新颖性
            novelty = self.detect_novelty(content)
            
            # 如果有新知识，触发SICA引擎学习
            if novelty.is_novel and novelty.missing_knowledge:
                await self._learn_new_knowledge(novelty, task)
            
            task.status = "completed"
            logger.info(f"✅ 学习任务完成: {task.task_id}")
            
        except Exception as e:
            task.status = "failed"
            logger.error(f"❌ 学习任务失败 {task.task_id}: {e}")
    
    async def _learn_new_knowledge(self, novelty: NoveltyDetection, task: LearningTask):
        """学习新知识"""
        logger.info(f"📚 学习新知识: {novelty.missing_knowledge}")
        
        # 1. 将新实体添加到知识图谱
        for entity in novelty.missing_knowledge:
            self.knowledge_graph.add_node(entity, {"type": "concept"})
            logger.debug(f"➕ 添加实体: {entity}")
        
        # 2. 生成学习总结
        summary = f"学习了新的概念: {', '.join(novelty.missing_knowledge)}"
        
        # 3. 更新任务元数据
        task.metadata["learned_concepts"] = novelty.missing_knowledge
        task.metadata["summary"] = summary
    
    def _on_file_change(self, change: FileChange):
        """文件变化回调"""
        if change.change_type == FileChangeType.DELETED:
            return
        
        file_path = change.file_path
        
        # 跳过已处理的文件
        if file_path in self.processed_files:
            return
        
        try:
            # 读取文件内容
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            # 计算好奇心并触发学习
            self.trigger_autonomous_learning(content, file_path)
            
            # 标记为已处理
            self.processed_files.add(file_path)
            
        except Exception as e:
            logger.error(f"处理文件变化失败 {file_path}: {e}")
    
    def _start_idle_loop(self):
        """启动Idle循环"""
        self.is_idle_running = True
        
        async def idle_loop():
            while self.is_idle_running:
                await asyncio.sleep(self.idle_interval)
                await self._idle_check()
        
        asyncio.create_task(idle_loop())
    
    async def _idle_check(self):
        """Idle时检查"""
        # 检查是否有待处理任务
        pending_tasks = [t for t in self.learning_tasks.values() if t.status == "pending"]
        
        if pending_tasks:
            # 执行优先级最高的任务
            pending_tasks.sort(key=lambda t: t.priority)
            task = pending_tasks[0]
            await self._execute_learning_task(task)
    
    def get_curiosity_level(self, score: float) -> CuriosityLevel:
        """获取好奇心级别"""
        if score >= 0.9:
            return CuriosityLevel.CRITICAL
        elif score >= 0.8:
            return CuriosityLevel.HIGH
        elif score >= 0.6:
            return CuriosityLevel.MEDIUM
        else:
            return CuriosityLevel.LOW
    
    def get_learning_tasks(self, status: Optional[str] = None) -> List[LearningTask]:
        """获取学习任务列表"""
        tasks = list(self.learning_tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.priority)
    
    def set_learning_strategy(self, strategy: LearningStrategy):
        """设置学习策略"""
        self.learning_strategy = strategy
        logger.info(f"📋 学习策略已更新: {strategy.value}")
    
    def auto_scan(self) -> Dict[str, Any]:
        """
        自动扫描本地文件系统
        
        Returns:
            扫描结果摘要
        """
        logger.info("🔍 开始自动扫描本地文件系统...")
        
        # 检查资源使用情况
        if not self._check_resource_usage():
            logger.info("⏳ 资源使用过高，跳过扫描")
            return {"success": False, "reason": "资源使用过高"}
        
        try:
            result = self.auto_scanner.scan()
            self.last_scan_time = time.time()
            
            logger.info(f"✅ 扫描完成: 发现 {result.total_count} 个文件, 其中核心文档 {result.core_count} 个, 耗时 {result.execution_time:.2f} 秒")
            
            # 根据策略处理文件
            self._execute_learning_strategy()
            
            return {
                "success": True,
                "total_files": result.total_count,
                "core_files": result.core_count,
                "execution_time": result.execution_time,
                "directories_scanned": result.directories_scanned
            }
        
        except Exception as e:
            logger.error(f"❌ 扫描失败: {e}")
            return {"success": False, "reason": str(e)}
    
    def _check_resource_usage(self) -> bool:
        """检查资源使用情况"""
        try:
            import psutil
            
            cpu_usage = psutil.cpu_percent()
            memory_usage = psutil.virtual_memory().percent
            
            if cpu_usage > self.resource_limit * 100 or memory_usage > self.resource_limit * 100:
                logger.debug(f"资源使用过高 - CPU: {cpu_usage}%, 内存: {memory_usage}%")
                return False
            
            return True
        except Exception:
            # 如果无法获取资源信息，默认允许执行
            return True
    
    def _execute_learning_strategy(self):
        """执行学习策略"""
        if self.learning_strategy == LearningStrategy.CORE_ONLY:
            files = self.auto_scanner.get_core_documents()
        elif self.learning_strategy == LearningStrategy.CORE_FIRST:
            # 先处理核心文档，非核心文档留到按需学习
            files = self.auto_scanner.get_core_documents()
        elif self.learning_strategy == LearningStrategy.ALL:
            files = self.auto_scanner.get_unprocessed_files()
        elif self.learning_strategy == LearningStrategy.ON_DEMAND:
            # 按需模式不自动处理
            return
        else:
            files = []
        
        # 限制并发任务数量
        running_tasks = [t for t in self.learning_tasks.values() if t.status == "running"]
        available_slots = self.max_concurrent_tasks - len(running_tasks)
        
        for file in files[:available_slots]:
            self._schedule_file_learning(file)
    
    def _schedule_file_learning(self, file):
        """调度文件学习"""
        try:
            with open(file.path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            curiosity = self.calculate_curiosity(content, file.path)
            
            if curiosity >= self.curiosity_threshold:
                task = LearningTask(
                    task_id=f"learn_{uuid.uuid4().hex[:8]}",
                    task_type="auto_scan_learning",
                    description=f"学习文件: {file.path}",
                    curiosity_score=curiosity,
                    priority=file.priority,
                    metadata={
                        "content": content[:500],
                        "source": file.path,
                        "file_type": file.file_type,
                        "is_core": file.is_core
                    }
                )
                
                self.learning_tasks[task.task_id] = task
                file.processed = True
                
                # 静默执行，不输出日志
                asyncio.create_task(self._execute_learning_task_silent(task))
                
                logger.debug(f"📚 已调度学习任务: {file.path}")
        
        except Exception as e:
            logger.debug(f"调度文件学习失败 {file.path}: {e}")
    
    async def _execute_learning_task_silent(self, task: LearningTask):
        """静默执行学习任务（不输出详细日志）"""
        try:
            task.status = "running"
            
            content = task.metadata.get("content", "")
            novelty = self.detect_novelty(content)
            
            if novelty.is_novel and novelty.missing_knowledge:
                await self._learn_new_knowledge(novelty, task)
            
            task.status = "completed"
            
        except Exception:
            task.status = "failed"
    
    def learn_on_demand(self, file_path: str) -> Optional[LearningTask]:
        """
        按需学习指定文件
        
        Args:
            file_path: 文件路径
        
        Returns:
            LearningTask 如果成功，否则 None
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            return self.trigger_autonomous_learning(content, file_path)
        
        except Exception as e:
            logger.error(f"按需学习失败 {file_path}: {e}")
            return None
    
    def get_scan_results(self) -> List[Dict[str, Any]]:
        """获取扫描结果"""
        return [{
            "path": f.path,
            "file_type": f.file_type,
            "size": f.size,
            "priority": f.priority,
            "is_core": f.is_core,
            "processed": f.processed,
            "modified_time": datetime.fromtimestamp(f.modified_time).isoformat()
        } for f in self.auto_scanner.scan_results]
    
    def clear_scan_results(self):
        """清除扫描结果"""
        self.auto_scanner.clear_results()


# 单例模式
_curiosity_engine = None


def get_curiosity_engine() -> CuriosityEngine:
    """获取好奇心引擎单例"""
    global _curiosity_engine
    if _curiosity_engine is None:
        _curiosity_engine = CuriosityEngine()
    return _curiosity_engine