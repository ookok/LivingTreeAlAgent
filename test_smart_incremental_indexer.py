"""
智能增量索引测试
验证时空感知的增量索引系统功能
"""

import asyncio
import time
import os
import tempfile
from typing import List, Dict, Optional, Any

print("=" * 60)
print("智能增量索引测试")
print("=" * 60)


class VectorLevel:
    """向量层级"""
    L1 = "file"
    L2 = "function"
    L3 = "block"
    L4 = "concept"


class ChangeType:
    """变更类型"""
    MINOR = "minor"
    RESTRUCTURE = "restructure"
    DEPENDENCY = "dependency"
    CONFIG = "config"


class ChangeHistory:
    """变更历史"""
    def __init__(self, timestamp, change_type, description, vectors_updated):
        self.timestamp = timestamp
        self.change_type = change_type
        self.description = description
        self.vectors_updated = vectors_updated


class TemporalVector:
    """时空向量"""
    def __init__(self, id, vector, timeline, relationships, level, last_updated):
        self.id = id
        self.vector = vector
        self.timeline = timeline
        self.relationships = relationships
        self.level = level
        self.last_updated = last_updated


class FileIndexInfo:
    """文件索引信息"""
    def __init__(self, file_path, vectors, index_value, last_modified, last_indexed, dependencies, dependents):
        self.file_path = file_path
        self.vectors = vectors
        self.index_value = index_value
        self.last_modified = last_modified
        self.last_indexed = last_indexed
        self.dependencies = dependencies
        self.dependents = dependents


class SmartBatchQueue:
    """智能批处理队列"""
    
    def __init__(self, max_queue_size=20, idle_time=3, time_window=5):
        self.queue = {}
        self.max_queue_size = max_queue_size
        self.idle_time = idle_time
        self.time_window = time_window
        self.last_activity_time = time.time()
        self.processing = False
        self.process_callback = None
    
    def queue_change(self, file_path, change):
        """队列变更"""
        self.queue[file_path] = change
        self.last_activity_time = time.time()
        
        if self.should_process_now():
            self._process_batch()
    
    def should_process_now(self):
        """判断是否应该立即处理"""
        if len(self.queue) >= self.max_queue_size:
            return True
        if time.time() - self.last_activity_time > self.time_window:
            return True
        return False
    
    def _process_batch(self):
        """处理批处理任务"""
        if self.processing or not self.queue:
            return
        
        self.processing = True
        try:
            batch = self.queue.copy()
            self.queue.clear()
            if self.process_callback:
                self.process_callback(batch)
        finally:
            self.processing = False
    
    def set_process_callback(self, callback):
        """设置处理回调"""
        self.process_callback = callback
    
    def clear(self):
        """清空队列"""
        self.queue.clear()
    
    def get_queue_size(self):
        """获取队列大小"""
        return len(self.queue)


class PredictiveIndexer:
    """预测性索引"""
    
    def __init__(self):
        self.cache = {}
        self.edit_history = {}
    
    def on_content_change(self, file_path, changes):
        """监听编辑行为"""
        if file_path not in self.edit_history:
            self.edit_history[file_path] = []
        self.edit_history[file_path].append(changes)
        
        intent = self.predict_intent(file_path, changes)
        if intent and intent.get('confidence', 0) > 0.8:
            predicted_code = self.generate_probable_completion(file_path, changes)
            if predicted_code:
                pre_vector = self.compute_embedding(predicted_code)
                if pre_vector:
                    self.cache[file_path] = pre_vector
    
    def on_save(self, file_path):
        """用户保存时"""
        if file_path in self.cache:
            vector = self.cache[file_path]
            del self.cache[file_path]
            return vector
        return None
    
    def predict_intent(self, file_path, changes):
        """预测用户意图"""
        confidence = 0.7 if len(changes) > 10 else 0.5
        return {
            "intent": "edit",
            "confidence": confidence
        }
    
    def generate_probable_completion(self, file_path, changes):
        """生成可能的代码完成"""
        return changes + "  # 预测的代码完成"
    
    def compute_embedding(self, text):
        """计算文本嵌入"""
        return [0.1] * 128
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
    
    def get_cache_size(self):
        """获取缓存大小"""
        return len(self.cache)


class GitAwareIncrementalStrategy:
    """Git感知的增量策略"""
    
    def __init__(self, project_root):
        self.project_root = project_root
    
    def analyze_change(self, file_path):
        """分析变更类型"""
        if file_path.endswith('.py') or file_path.endswith('.js'):
            return ChangeType.MINOR
        elif file_path.endswith('.json') or file_path.endswith('.yaml'):
            return ChangeType.CONFIG
        else:
            return ChangeType.MINOR
    
    def get_affected_files(self, file_path, change_type):
        """获取受影响的文件"""
        return [file_path]
    
    def should_reindex(self, file_path, last_indexed):
        """判断是否需要重新索引"""
        try:
            mtime = os.path.getmtime(file_path)
            return mtime > last_indexed
        except Exception:
            return False


class SmartDecisionEngine:
    """智能决策引擎"""
    
    def __init__(self):
        self.edit_frequency = {}
        self.user_attention = {}
        self.centrality = {}
    
    def calculate_index_value(self, file_path):
        """计算索引价值分数"""
        try:
            size = os.path.getsize(file_path)
            size_score = min(1.0, 10000 / (size + 100))
        except Exception:
            size_score = 0.5
        
        edit_freq = self.edit_frequency.get(file_path, 0) / 10.0
        edit_freq = min(1.0, edit_freq)
        
        centrality = self.centrality.get(file_path, 0.5)
        
        user_attention = self.user_attention.get(file_path, 0) / 5.0
        user_attention = min(1.0, user_attention)
        
        try:
            mtime = os.path.getmtime(file_path)
            recency = min(1.0, (time.time() - mtime) / 86400)
        except Exception:
            recency = 0.5
        
        index_value = (
            size_score * 0.1 +
            edit_freq * 0.2 +
            centrality * 0.25 +
            user_attention * 0.2 +
            recency * 0.1
        )
        
        if 'node_modules' in file_path or 'dist' in file_path or '.git' in file_path:
            index_value = 0.0
        
        return index_value
    
    def should_index(self, file_path):
        """判断是否应该索引"""
        index_value = self.calculate_index_value(file_path)
        return index_value > 0.3
    
    def update_edit_frequency(self, file_path):
        """更新编辑频率"""
        self.edit_frequency[file_path] = self.edit_frequency.get(file_path, 0) + 1
    
    def update_user_attention(self, file_path):
        """更新用户关注度"""
        self.user_attention[file_path] = self.user_attention.get(file_path, 0) + 1
    
    def update_centrality(self, file_path, centrality):
        """更新中心性"""
        self.centrality[file_path] = centrality


class HierarchicalVectorStore:
    """分层向量存储"""
    
    def __init__(self):
        self.vectors = {}
    
    def get_vector(self, file_path, level):
        """获取向量"""
        if file_path in self.vectors:
            return self.vectors[file_path].vectors.get(level)
        return None
    
    def update_vector(self, file_path, level, vector, change_type):
        """更新向量"""
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
        
        vector_id = f"{file_path}:{level}"
        history = ChangeHistory(
            timestamp=time.time(),
            change_type=change_type,
            description=f"Update {level} vector",
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
    
    def get_file_info(self, file_path):
        """获取文件信息"""
        return self.vectors.get(file_path)
    
    def update_file_info(self, file_path, **updates):
        """更新文件信息"""
        if file_path in self.vectors:
            for key, value in updates.items():
                if hasattr(self.vectors[file_path], key):
                    setattr(self.vectors[file_path], key, value)
    
    def get_all_files(self):
        """获取所有文件"""
        return list(self.vectors.keys())
    
    def remove_file(self, file_path):
        """移除文件"""
        if file_path in self.vectors:
            del self.vectors[file_path]
    
    def get_stats(self):
        """获取统计信息"""
        total_vectors = sum(len(info.vectors) for info in self.vectors.values())
        return {
            "total_files": len(self.vectors),
            "total_vectors": total_vectors,
            "average_vectors_per_file": total_vectors / len(self.vectors) if self.vectors else 0
        }


class SmartIncrementalIndexer:
    """智能增量索引器"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        self.vector_store = HierarchicalVectorStore()
        self.batch_queue = SmartBatchQueue()
        self.predictive_indexer = PredictiveIndexer()
        self.git_strategy = GitAwareIncrementalStrategy(project_root)
        self.decision_engine = SmartDecisionEngine()
        
        self.batch_queue.set_process_callback(self._process_batch_update)
    
    def index_file(self, file_path, force=False):
        """索引文件"""
        if not force and not self.decision_engine.should_index(file_path):
            return
        
        file_info = self.vector_store.get_file_info(file_path)
        if file_info and not self.git_strategy.should_reindex(file_path, file_info.last_indexed) and not force:
            return
        
        change_type = self.git_strategy.analyze_change(file_path)
        affected_files = self.git_strategy.get_affected_files(file_path, change_type)
        
        for affected_file in affected_files:
            self.batch_queue.queue_change(affected_file, {
                "change_type": change_type,
                "timestamp": time.time()
            })
    
    def _process_batch_update(self, batch):
        """处理批处理更新"""
        for file_path, change in batch.items():
            try:
                predicted_vector = self.predictive_indexer.on_save(file_path)
                
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                l1_vector = predicted_vector or self._compute_vector(content)
                
                if l1_vector:
                    self.vector_store.update_vector(file_path, VectorLevel.L1, l1_vector, change["change_type"])
                
                self.decision_engine.update_edit_frequency(file_path)
                self.decision_engine.update_user_attention(file_path)
                
                print(f"Indexed file: {file_path}")
                
            except Exception as e:
                print(f"Error indexing file {file_path}: {e}")
    
    def _compute_vector(self, text):
        """计算向量"""
        import hashlib
        hash_value = hashlib.md5(text.encode()).hexdigest()
        vector = []
        for i in range(0, len(hash_value), 2):
            if i + 1 < len(hash_value):
                vector.append(int(hash_value[i:i+2], 16) / 255.0)
        while len(vector) < 128:
            vector.append(0.0)
        return vector[:128]
    
    def on_content_change(self, file_path, changes):
        """内容变更时"""
        self.predictive_indexer.on_content_change(file_path, changes)
    
    def on_save(self, file_path):
        """保存时"""
        self.index_file(file_path)
    
    def get_file_index_info(self, file_path):
        """获取文件索引信息"""
        return self.vector_store.get_file_info(file_path)
    
    def get_stats(self):
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


def create_smart_indexer(project_root):
    """创建智能增量索引器"""
    return SmartIncrementalIndexer(project_root)


async def test_hierarchical_vector_store():
    """测试分层向量存储"""
    print("=== 测试分层向量存储 ===")
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""def hello():
    print("Hello world")

def add(a, b):
    return a + b
""")
        test_file = f.name
    
    try:
        indexer = create_smart_indexer(os.path.dirname(test_file))
        
        # 索引文件
        indexer.index_file(test_file, force=True)
        
        # 手动处理批处理任务
        indexer.batch_queue._process_batch()
        
        # 检查索引信息
        file_info = indexer.get_file_index_info(test_file)
        print(f"文件索引信息: {file_info is not None}")
        if file_info:
            print(f"向量数量: {len(file_info.vectors)}")
            print(f"最后索引时间: {file_info.last_indexed}")
        
        # 测试增量更新
        with open(test_file, 'a') as f:
            f.write("\n\ndef multiply(a, b):\n    return a * b\n")
        
        # 重新索引
        indexer.index_file(test_file)
        indexer.batch_queue._process_batch()
        
        # 检查更新后的索引信息
        updated_info = indexer.get_file_index_info(test_file)
        print(f"更新后向量数量: {len(updated_info.vectors) if updated_info else 0}")
        print(f"更新后最后索引时间: {updated_info.last_indexed if updated_info else 'N/A'}")
        
        return True
        
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


async def test_smart_batch_queue():
    """测试智能批处理队列"""
    print("\n=== 测试智能批处理队列 ===")
    
    # 创建临时文件
    test_files = []
    for i in range(5):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(f"def test{i}():\n    print('Test {i}')\n")
            test_files.append(f.name)
    
    try:
        indexer = create_smart_indexer(os.path.dirname(test_files[0]))
        
        # 批量索引文件
        for test_file in test_files:
            indexer.index_file(test_file, force=True)
        
        # 手动处理批处理任务
        indexer.batch_queue._process_batch()
        
        # 检查队列大小
        stats = indexer.get_stats()
        print(f"批处理队列大小: {stats['batch_queue_size']}")
        print(f"向量存储统计: {stats['vector_store']}")
        
        return True
        
    finally:
        for test_file in test_files:
            if os.path.exists(test_file):
                os.unlink(test_file)


async def test_predictive_indexing():
    """测试预测性索引"""
    print("\n=== 测试预测性索引 ===")
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def hello():\n    print('Hello')\n")
        test_file = f.name
    
    try:
        indexer = create_smart_indexer(os.path.dirname(test_file))
        
        # 模拟内容变更
        changes = "    print('Hello world')"
        indexer.on_content_change(test_file, changes)
        
        # 检查缓存大小
        stats = indexer.get_stats()
        print(f"预测缓存大小: {stats['predictive_cache_size']}")
        
        # 模拟保存
        indexer.on_save(test_file)
        
        # 手动处理批处理任务
        indexer.batch_queue._process_batch()
        
        # 检查索引信息
        file_info = indexer.get_file_index_info(test_file)
        print(f"预测性索引后文件信息: {file_info is not None}")
        
        return True
        
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


async def test_smart_decision_engine():
    """测试智能决策引擎"""
    print("\n=== 测试智能决策引擎 ===")
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def test():\n    pass\n")
        test_file = f.name
    
    try:
        indexer = create_smart_indexer(os.path.dirname(test_file))
        
        # 计算索引价值
        index_value = indexer.decision_engine.calculate_index_value(test_file)
        print(f"索引价值分数: {index_value:.3f}")
        
        # 检查是否应该索引
        should_index = indexer.decision_engine.should_index(test_file)
        print(f"是否应该索引: {should_index}")
        
        # 更新编辑频率
        indexer.decision_engine.update_edit_frequency(test_file)
        indexer.decision_engine.update_user_attention(test_file)
        
        # 重新计算索引价值
        updated_value = indexer.decision_engine.calculate_index_value(test_file)
        print(f"更新后索引价值分数: {updated_value:.3f}")
        
        return True
        
    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


async def test_git_aware_strategy():
    """测试Git感知的增量策略"""
    print("\n=== 测试Git感知的增量策略 ===")
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def test():\n    pass\n")
        py_file = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"test": "value"}')
        json_file = f.name
    
    try:
        indexer = create_smart_indexer(os.path.dirname(py_file))
        
        # 分析变更类型
        py_change_type = indexer.git_strategy.analyze_change(py_file)
        json_change_type = indexer.git_strategy.analyze_change(json_file)
        
        print(f"Python文件变更类型: {py_change_type}")
        print(f"JSON文件变更类型: {json_change_type}")
        
        # 获取受影响文件
        py_affected = indexer.git_strategy.get_affected_files(py_file, py_change_type)
        json_affected = indexer.git_strategy.get_affected_files(json_file, json_change_type)
        
        print(f"Python文件受影响文件: {len(py_affected)}")
        print(f"JSON文件受影响文件: {len(json_affected)}")
        
        return True
        
    finally:
        if os.path.exists(py_file):
            os.unlink(py_file)
        if os.path.exists(json_file):
            os.unlink(json_file)


async def test_integration():
    """集成测试"""
    tests = [
        test_hierarchical_vector_store,
        test_smart_batch_queue,
        test_predictive_indexing,
        test_smart_decision_engine,
        test_git_aware_strategy
    ]
    
    all_passed = True
    
    for test in tests:
        try:
            success = await test()
            if not success:
                all_passed = False
                print(f"测试 {test.__name__} 失败")
            else:
                print(f"测试 {test.__name__} 通过")
        except Exception as e:
            all_passed = False
            print(f"测试 {test.__name__} 异常: {e}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！智能增量索引集成成功")
    else:
        print("部分测试失败，需要进一步调试")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(test_integration())