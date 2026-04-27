"""
智能增量索引核心模块
实现时空感知的增量索引系统
"""

import os
import time
import asyncio
import threading
import queue
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class VectorLevel(Enum):
    """向量层级"""
    L1 = "file"       # 文件级：整体语义向量
    L2 = "function"   # 函数级：每个函数独立向量
    L3 = "block"      # 代码块级：逻辑段落向量
    L4 = "concept"    # 概念级：提取的关键概念


class ChangeType(Enum):
    """变更类型"""
    MINOR = "minor"       # 小修改
    RESTRUCTURE = "restructure"  # 重构
    DEPENDENCY = "dependency"  # 依赖变更
    CONFIG = "config"     # 配置变更


@dataclass
class ChangeHistory:
    """变更历史"""
    timestamp: float
    change_type: ChangeType
    description: str
    vectors_updated: List[VectorLevel]


@dataclass
class TemporalVector:
    """时空向量"""
    id: str
    vector: List[float]
    timeline: List[ChangeHistory]
    relationships: Dict[str, List[str]]  # {"syntactic": [...], "coedited": [...]}
    level: VectorLevel
    last_updated: float


@dataclass
class FileIndexInfo:
    """文件索引信息"""
    file_path: str
    vectors: Dict[VectorLevel, TemporalVector]
    index_value: float
    last_modified: float
    last_indexed: float
    dependencies: List[str]
    dependents: List[str]


class SmartBatchQueue:
    """
    智能批处理队列
    聚合变化，空闲时批量处理
    """
    
    def __init__(self, max_queue_size: int = 20, idle_time: int = 3, time_window: int = 5):
        self.queue: Dict[str, Any] = {}
        self.max_queue_size = max_queue_size
        self.idle_time = idle_time  # 秒
        self.time_window = time_window  # 秒
        self.last_activity_time = time.time()
        self.processing = False
        self.lock = threading.Lock()
        self.process_callback: Optional[Callable] = None
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_queue)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def queue_change(self, file_path: str, change: Any):
        """队列变更"""
        with self.lock:
            self.queue[file_path] = change
            self.last_activity_time = time.time()
            
            # 检查是否需要立即处理
            if self.should_process_now():
                self._process_batch()
    
    def should_process_now(self) -> bool:
        """判断是否应该立即处理"""
        # 队列满
        if len(self.queue) >= self.max_queue_size:
            return True
        
        # 时间窗口已满
        if time.time() - self.last_activity_time > self.time_window:
            return True
        
        return False
    
    def _monitor_queue(self):
        """监控队列，处理空闲时的批量任务"""
        while True:
            time.sleep(0.5)
            
            with self.lock:
                if not self.processing and self.queue:
                    # 检查空闲时间
                    if time.time() - self.last_activity_time > self.idle_time:
                        self._process_batch()
    
    def _process_batch(self):
        """处理批处理任务"""
        if self.processing or not self.queue:
            return
        
        self.processing = True
        
        try:
            # 复制队列内容
            batch = self.queue.copy()
            self.queue.clear()
            
            # 智能分组并行处理
            if self.process_callback:
                self.process_callback(batch)
                
        finally:
            self.processing = False
    
    def set_process_callback(self, callback: Callable):
        """设置处理回调"""
        self.process_callback = callback
    
    def clear(self):
        """清空队列"""
        with self.lock:
            self.queue.clear()
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        with self.lock:
            return len(self.queue)


class PredictiveIndexer:
    """
    预测性索引
    在保存之前预测并预索引
    """
    
    def __init__(self):
        self.cache: Dict[str, List[float]] = {}
        self.edit_history: Dict[str, List[str]] = {}
        self.prediction_model = None  # 微型预测模型
    
    def on_content_change(self, file_path: str, changes: str):
        """监听编辑行为"""
        # 记录编辑历史
        if file_path not in self.edit_history:
            self.edit_history[file_path] = []
        self.edit_history[file_path].append(changes)
        
        # 预测用户意图
        intent = self.predict_intent(file_path, changes)
        
        # 高置信度时预计算向量
        if intent and intent.get('confidence', 0) > 0.8:
            predicted_code = self.generate_probable_completion(file_path, changes)
            if predicted_code:
                pre_vector = self.compute_embedding(predicted_code)
                if pre_vector:
                    self.cache[file_path] = pre_vector
    
    def on_save(self, file_path: str) -> Optional[List[float]]:
        """用户保存时"""
        if file_path in self.cache:
            # 命中预测！直接使用预计算向量
            vector = self.cache[file_path]
            del self.cache[file_path]
            return vector
        return None
    
    def predict_intent(self, file_path: str, changes: str) -> Optional[Dict[str, Any]]:
        """预测用户意图"""
        # 简单的意图预测逻辑
        # 实际项目中可以使用微型模型
        confidence = 0.7 if len(changes) > 10 else 0.5
        return {
            "intent": "edit",
            "confidence": confidence
        }
    
    def generate_probable_completion(self, file_path: str, changes: str) -> Optional[str]:
        """生成可能的代码完成"""
        # 简单的代码完成生成
        # 实际项目中可以使用更复杂的逻辑
        return changes + "  # 预测的代码完成"
    
    def compute_embedding(self, text: str) -> Optional[List[float]]:
        """计算文本嵌入"""
        # 简单的嵌入计算
        # 实际项目中应该使用真实的嵌入模型
        return [0.1] * 128  # 模拟128维向量
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
    
    def get_cache_size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)


class GitAwareIncrementalStrategy:
    """
    Git感知的增量策略
    分析Git历史，智能决定索引粒度
    """
    
    def __init__(self, project_root: str):
        self.project_root = project_root
    
    def analyze_change(self, file_path: str) -> ChangeType:
        """分析变更类型"""
        # 简单的变更类型分析
        # 实际项目中应该分析Git历史
        if file_path.endswith('.py') or file_path.endswith('.js'):
            return ChangeType.MINOR
        elif file_path.endswith('.json') or file_path.endswith('.yaml'):
            return ChangeType.CONFIG
        else:
            return ChangeType.MINOR
    
    def get_affected_files(self, file_path: str, change_type: ChangeType) -> List[str]:
        """获取受影响的文件"""
        affected_files = [file_path]
        
        # 根据变更类型扩展受影响文件
        if change_type == ChangeType.DEPENDENCY:
            # 查找依赖该文件的文件
            pass
        elif change_type == ChangeType.RESTRUCTURE:
            # 查找相关文件
            pass
        
        return affected_files
    
    def should_reindex(self, file_path: str, last_indexed: float) -> bool:
        """判断是否需要重新索引"""
        try:
            # 检查文件修改时间
            mtime = os.path.getmtime(file_path)
            return mtime > last_indexed
        except Exception:
            return False


class SmartDecisionEngine:
    """
    智能决策引擎
    计算索引价值分数，智能决定索引范围
    """
    
    def __init__(self):
        self.edit_frequency: Dict[str, int] = {}
        self.user_attention: Dict[str, int] = {}
        self.centrality: Dict[str, float] = {}
    
    def calculate_index_value(self, file_path: str) -> float:
        """
        计算索引价值分数
        indexValue = sizeScore * 0.1 + editFreq * 0.2 + centrality * 0.25 + userAttention * 0.2 + recency * 0.1
        """
        # 计算文件大小分数（小文件价值高）
        try:
            size = os.path.getsize(file_path)
            size_score = min(1.0, 10000 / (size + 100))
        except Exception:
            size_score = 0.5
        
        # 编辑频率分数
        edit_freq = self.edit_frequency.get(file_path, 0) / 10.0  # 最多10次编辑
        edit_freq = min(1.0, edit_freq)
        
        # 中心性分数
        centrality = self.centrality.get(file_path, 0.5)
        
        # 用户关注度分数
        user_attention = self.user_attention.get(file_path, 0) / 5.0  # 最多5次关注
        user_attention = min(1.0, user_attention)
        
        # 最近修改分数
        try:
            mtime = os.path.getmtime(file_path)
            recency = min(1.0, (time.time() - mtime) / 86400)  # 一天内为1.0
        except Exception:
            recency = 0.5
        
        # 计算总分数
        index_value = (
            size_score * 0.1 +
            edit_freq * 0.2 +
            centrality * 0.25 +
            user_attention * 0.2 +
            recency * 0.1
        )
        
        # 特殊处理：跳过node_modules等目录
        if 'node_modules' in file_path or 'dist' in file_path or '.git' in file_path:
            index_value = 0.0
        
        return index_value
    
    def should_index(self, file_path: str) -> bool:
        """判断是否应该索引"""
        index_value = self.calculate_index_value(file_path)
        return index_value > 0.3  # 阈值
    
    def update_edit_frequency(self, file_path: str):
        """更新编辑频率"""
        self.edit_frequency[file_path] = self.edit_frequency.get(file_path, 0) + 1
    
    def update_user_attention(self, file_path: str):
        """更新用户关注度"""
        self.user_attention[file_path] = self.user_attention.get(file_path, 0) + 1
    
    def update_centrality(self, file_path: str, centrality: float):
        """更新中心性"""
        self.centrality[file_path] = centrality


class HierarchicalVectorStore:
    """
    分层向量存储
    实现L1-L4分层向量，只更新变动部分
    """
    
    def __init__(self):
        self.vectors: Dict[str, FileIndexInfo] = {}
        self.lock = threading.Lock()
    
    def get_vector(self, file_path: str, level: VectorLevel) -> Optional[TemporalVector]:
        """获取向量"""
        with self.lock:
            if file_path in self.vectors:
                return self.vectors[file_path].vectors.get(level)
        return None
    
    def update_vector(self, file_path: str, level: VectorLevel, vector: List[float], change_type: ChangeType):
        """更新向量"""
        with self.lock:
            if file_path not in self.vectors:
                self.vectors[file_path] = FileIndexInfo(
                    file_path=file_path,
                    vectors={},
                    index_value=0.0,
                    last_modified=time.time(),
                    last_indexed=time.time(),
                    dependencies=[],
                    dependents=[]
                )
            
            # 创建或更新向量
            vector_id = f"{file_path}:{level.value}"
            history = ChangeHistory(
                timestamp=time.time(),
                change_type=change_type,
                description=f"Update {level.value} vector",
                vectors_updated=[level]
            )
            
            temporal_vector = TemporalVector(
                id=vector_id,
                vector=vector,
                timeline=[history],
                relationships={"syntactic": [], "coedited": []},
                level=level,
                last_updated=time.time()
            )
            
            self.vectors[file_path].vectors[level] = temporal_vector
            self.vectors[file_path].last_indexed = time.time()
    
    def get_file_info(self, file_path: str) -> Optional[FileIndexInfo]:
        """获取文件信息"""
        with self.lock:
            return self.vectors.get(file_path)
    
    def update_file_info(self, file_path: str, **updates):
        """更新文件信息"""
        with self.lock:
            if file_path in self.vectors:
                for key, value in updates.items():
                    if hasattr(self.vectors[file_path], key):
                        setattr(self.vectors[file_path], key, value)
    
    def get_all_files(self) -> List[str]:
        """获取所有文件"""
        with self.lock:
            return list(self.vectors.keys())
    
    def remove_file(self, file_path: str):
        """移除文件"""
        with self.lock:
            if file_path in self.vectors:
                del self.vectors[file_path]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            total_vectors = sum(len(info.vectors) for info in self.vectors.values())
            return {
                "total_files": len(self.vectors),
                "total_vectors": total_vectors,
                "average_vectors_per_file": total_vectors / len(self.vectors) if self.vectors else 0
            }


class SmartIncrementalIndexer:
    """
    智能增量索引器
    实现时空感知的增量索引
    """
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.vector_store = HierarchicalVectorStore()
        self.batch_queue = SmartBatchQueue()
        self.predictive_indexer = PredictiveIndexer()
        self.git_strategy = GitAwareIncrementalStrategy(project_root)
        self.decision_engine = SmartDecisionEngine()
        
        # 设置批处理回调
        self.batch_queue.set_process_callback(self._process_batch_update)
    
    def index_file(self, file_path: str, force: bool = False):
        """索引文件"""
        # 检查是否应该索引
        if not force and not self.decision_engine.should_index(file_path):
            return
        
        # 检查是否需要重新索引
        file_info = self.vector_store.get_file_info(file_path)
        if file_info and not self.git_strategy.should_reindex(file_path, file_info.last_indexed) and not force:
            return
        
        # 分析变更类型
        change_type = self.git_strategy.analyze_change(file_path)
        
        # 获取受影响的文件
        affected_files = self.git_strategy.get_affected_files(file_path, change_type)
        
        # 队列变更
        for affected_file in affected_files:
            self.batch_queue.queue_change(affected_file, {
                "change_type": change_type,
                "timestamp": time.time()
            })
    
    def _process_batch_update(self, batch: Dict[str, Any]):
        """处理批处理更新"""
        for file_path, change in batch.items():
            try:
                # 尝试使用预测的向量
                predicted_vector = self.predictive_indexer.on_save(file_path)
                
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 提取不同层级的内容
                l1_content = content  # 文件级
                l2_content = self._extract_functions(content)  # 函数级
                l3_content = self._extract_blocks(content)  # 代码块级
                l4_content = self._extract_concepts(content)  # 概念级
                
                # 计算向量
                l1_vector = predicted_vector or self._compute_vector(l1_content)
                l2_vectors = {func: self._compute_vector(func_content) for func, func_content in l2_content.items()}
                l3_vectors = {block: self._compute_vector(block_content) for block, block_content in l3_content.items()}
                l4_vectors = {concept: self._compute_vector(concept) for concept in l4_content}
                
                # 更新向量
                if l1_vector:
                    self.vector_store.update_vector(file_path, VectorLevel.L1, l1_vector, change["change_type"])
                
                # 更新函数级向量
                for func, vector in l2_vectors.items():
                    # 实际项目中应该为每个函数创建独立的向量
                    pass
                
                # 更新代码块级向量
                for block, vector in l3_vectors.items():
                    # 实际项目中应该为每个代码块创建独立的向量
                    pass
                
                # 更新概念级向量
                for concept, vector in l4_vectors.items():
                    # 实际项目中应该为每个概念创建独立的向量
                    pass
                
                # 更新决策引擎
                self.decision_engine.update_edit_frequency(file_path)
                self.decision_engine.update_user_attention(file_path)
                
                print(f"Indexed file: {file_path}")
                
            except Exception as e:
                print(f"Error indexing file {file_path}: {e}")
    
    def _extract_functions(self, content: str) -> Dict[str, str]:
        """提取函数"""
        # 简单的函数提取
        functions = {}
        lines = content.split('\n')
        in_function = False
        function_name = ""
        function_content = []
        
        for line in lines:
            if line.strip().startswith('def '):
                if in_function:
                    functions[function_name] = '\n'.join(function_content)
                function_name = line.strip().split('def ')[1].split('(')[0]
                function_content = [line]
                in_function = True
            elif in_function:
                function_content.append(line)
                if line.strip() == '':
                    continue
                if line.strip() == 'pass' or (line.strip().startswith('return') and not line.strip().endswith(':')):
                    functions[function_name] = '\n'.join(function_content)
                    in_function = False
        
        if in_function:
            functions[function_name] = '\n'.join(function_content)
        
        return functions
    
    def _extract_blocks(self, content: str) -> Dict[str, str]:
        """提取代码块"""
        # 简单的代码块提取
        blocks = {}
        lines = content.split('\n')
        block_id = 0
        block_content = []
        
        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                block_content.append(line)
            elif block_content:
                blocks[f"block_{block_id}"] = '\n'.join(block_content)
                block_id += 1
                block_content = []
        
        if block_content:
            blocks[f"block_{block_id}"] = '\n'.join(block_content)
        
        return blocks
    
    def _extract_concepts(self, content: str) -> List[str]:
        """提取概念"""
        # 简单的概念提取
        concepts = []
        lines = content.split('\n')
        
        for line in lines:
            if line.strip().startswith('class '):
                concepts.append(line.strip())
            elif line.strip().startswith('def '):
                concepts.append(line.strip())
            elif line.strip().startswith('import '):
                concepts.append(line.strip())
        
        return concepts
    
    def _compute_vector(self, text: str) -> List[float]:
        """计算向量"""
        # 简单的向量计算
        # 实际项目中应该使用真实的嵌入模型
        hash_value = hashlib.md5(text.encode()).hexdigest()
        vector = []
        for i in range(0, len(hash_value), 2):
            if i + 1 < len(hash_value):
                vector.append(int(hash_value[i:i+2], 16) / 255.0)
        # 确保向量长度为128
        while len(vector) < 128:
            vector.append(0.0)
        return vector[:128]
    
    def on_content_change(self, file_path: str, changes: str):
        """内容变更时"""
        self.predictive_indexer.on_content_change(file_path, changes)
    
    def on_save(self, file_path: str):
        """保存时"""
        self.index_file(file_path)
    
    def get_file_index_info(self, file_path: str) -> Optional[FileIndexInfo]:
        """获取文件索引信息"""
        return self.vector_store.get_file_info(file_path)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "vector_store": self.vector_store.get_stats(),
            "batch_queue_size": self.batch_queue.get_queue_size(),
            "predictive_cache_size": self.predictive_indexer.get_cache_size()
        }
    
    def clear_cache(self):
        """清空缓存"""
        self.predictive_indexer.clear_cache()
        self.batch_queue.clear()


# 全局智能增量索引器实例
smart_indexer = None


def get_smart_indexer(project_root: str = None) -> SmartIncrementalIndexer:
    """
    获取智能增量索引器
    
    Args:
        project_root: 项目根目录
        
    Returns:
        SmartIncrementalIndexer: 智能增量索引器实例
    """
    global smart_indexer
    if not smart_indexer:
        smart_indexer = SmartIncrementalIndexer(project_root or os.getcwd())
    return smart_indexer


def create_smart_indexer(project_root: str) -> SmartIncrementalIndexer:
    """
    创建智能增量索引器
    
    Args:
        project_root: 项目根目录
        
    Returns:
        SmartIncrementalIndexer: 智能增量索引器实例
    """
    return SmartIncrementalIndexer(project_root)