"""
记忆路由器 - 统一记忆访问接口

功能：
1. 根据查询意图路由到合适的记忆系统
2. 支持短期/中期/长期记忆的自适应选择
3. 结果融合与排序
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class RouteResult:
    """路由结果"""
    memory_type: str
    confidence: float
    latency_ms: int = 0
    result: Optional[Dict] = None


@dataclass
class MemoryQuery:
    """记忆查询请求"""
    query: str
    context: Dict = None
    memory_type: str = None  # short_term/mid_term/long_term/auto
    limit: int = 10
    threshold: float = 0.3


class BrainMemoryRouter:
    """
    大脑记忆路由器 - 统一管理海马体和新皮层的访问
    
    路由策略：
    1. 明确指定类型：直接路由到对应系统
    2. 自动模式：根据查询特征选择最佳记忆系统
    3. 多级回退：短期→中期→长期
    """
    
    def __init__(self):
        self._logger = logger.bind(component="BrainMemoryRouter")
        
        # 延迟加载记忆组件
        self._hippocampus = None
        self._neocortex = None
        self._consolidator = None
        
        # 性能追踪
        self._stats = {
            'queries': {'short_term': 0, 'long_term': 0, 'auto': 0},
            'hits': {'short_term': 0, 'long_term': 0},
            'latency': {'short_term': [], 'long_term': []}
        }
    
    def _init_components(self):
        """延迟初始化组件"""
        if self._hippocampus is None:
            from .hippocampus import Hippocampus
            from .neocortex import Neocortex
            from .memory_consolidation import MemoryConsolidator
            
            self._hippocampus = Hippocampus()
            self._neocortex = Neocortex()
            self._consolidator = MemoryConsolidator(
                hippocampus=self._hippocampus,
                neocortex=self._neocortex
            )
            self._consolidator.start()
            
            self._logger.info("记忆组件初始化完成")
    
    def route(self, query: MemoryQuery) -> List[RouteResult]:
        """
        根据查询选择记忆源
        
        Returns:
            按优先级排序的记忆类型列表
        """
        if query.memory_type:
            # 明确指定类型
            return [RouteResult(memory_type=query.memory_type, confidence=1.0)]
        
        # 自动模式：根据查询特征选择
        return self._auto_route(query)
    
    def _auto_route(self, query: MemoryQuery) -> List[RouteResult]:
        """自动路由决策"""
        routes = []
        
        # 分析查询特征
        query_length = len(query.query)
        
        # 短查询优先检查短期记忆
        if query_length < 20:
            routes.append(RouteResult(memory_type="short_term", confidence=0.7))
        
        # 长查询需要更深入的检索
        routes.append(RouteResult(memory_type="long_term", confidence=0.6))
        
        # 如果有上下文，优先短期记忆
        if query.context and query.context.get("session_id"):
            routes.insert(0, RouteResult(memory_type="short_term", confidence=0.8))
        
        return routes
    
    def query(self, query: str, context: Dict = None, memory_type: str = None) -> Dict:
        """
        统一查询接口
        
        Args:
            query: 查询内容
            context: 上下文信息
            memory_type: 记忆类型 (short_term/long_term/auto)
        
        Returns:
            查询结果字典
        """
        self._init_components()
        
        query_obj = MemoryQuery(
            query=query,
            context=context,
            memory_type=memory_type
        )
        
        routes = self.route(query_obj)
        results = []
        best_result = None
        best_confidence = 0.0
        
        for route in routes:
            start_time = time.time()
            result = None
            
            try:
                if route.memory_type == "short_term":
                    result = self._query_short_term(query, context)
                elif route.memory_type == "long_term":
                    result = self._query_long_term(query, context)
                
                if result:
                    latency_ms = int((time.time() - start_time) * 1000)
                    confidence = result.get("confidence", 0.0)
                    
                    results.append({
                        'memory_type': route.memory_type,
                        'confidence': confidence,
                        'latency_ms': latency_ms,
                        'result': result
                    })
                    
                    # 更新统计
                    self._stats['queries'][route.memory_type] += 1
                    self._stats['latency'][route.memory_type].append(latency_ms)
                    if confidence > 0.5:
                        self._stats['hits'][route.memory_type] += 1
                    
                    # 更新最佳结果
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_result = result
                        best_result["memory_source"] = route.memory_type
                    
                    # 高置信度提前返回
                    if confidence >= 0.9:
                        self._logger.debug(f"高置信度命中 ({confidence})，提前返回")
                        break
            
            except Exception as e:
                self._logger.error(f"查询 {route.memory_type} 失败: {e}")
        
        if best_result is None:
            best_result = {
                'success': False,
                'content': "",
                'confidence': 0.0,
                'memory_source': "none",
                'message': "未找到相关记忆"
            }
        
        best_result['routes'] = [r.memory_type for r in routes]
        best_result['all_results'] = results
        
        return best_result
    
    def _query_short_term(self, query: str, context: Dict = None) -> Dict:
        """查询短期记忆（海马体）"""
        traces = self._hippocampus.retrieve_by_cue(query, limit=5)
        
        if not traces:
            return {'success': False, 'confidence': 0.0, 'content': ""}
        
        # 合并结果
        contents = []
        total_weight = 0.0
        
        for trace in traces:
            contents.append(trace.content)
            total_weight += trace.weight
        
        return {
            'success': True,
            'content': "\n\n".join(contents),
            'confidence': min(1.0, total_weight / len(traces)),
            'sources': [trace.memory_id for trace in traces],
            'memory_type': 'short_term'
        }
    
    def _query_long_term(self, query: str, context: Dict = None) -> Dict:
        """查询长期记忆（新皮层）"""
        nodes = self._neocortex.retrieve_semantic(query, limit=5)
        
        if not nodes:
            return {'success': False, 'confidence': 0.0, 'content': ""}
        
        # 合并结果
        contents = []
        total_similarity = 0.0
        
        for node in nodes:
            contents.append(node['content'])
            total_similarity += node['similarity']
        
        return {
            'success': True,
            'content': "\n\n".join(contents),
            'confidence': min(1.0, total_similarity / len(nodes)),
            'sources': [node['node_id'] for node in nodes],
            'memory_type': 'long_term'
        }
    
    def store(self, content: str, memory_type: str = "short_term", **kwargs) -> str:
        """
        统一存储接口
        
        Args:
            content: 要存储的内容
            memory_type: 记忆类型
            **kwargs: 额外参数
        
        Returns:
            存储的ID
        """
        self._init_components()
        
        memory_id = None
        
        if memory_type == "short_term":
            memory_id = self._hippocampus.encode_memory(content, **kwargs)
        elif memory_type == "long_term":
            memory_id = self._neocortex.store_semantic(content, **kwargs)
        else:
            memory_id = self._hippocampus.encode_memory(content, **kwargs)
        
        # 发布记忆创建事件
        self._publish_memory_event(memory_id, content, memory_type, kwargs.get('metadata', {}))
        
        return memory_id
    
    def _publish_memory_event(self, memory_id: str, content: str, memory_type: str, metadata: Dict):
        """发布记忆事件"""
        try:
            from client.src.business.integration_layer import EventType, publish
            
            event_data = {
                'memory_id': memory_id,
                'content': content,
                'memory_type': memory_type,
                'metadata': metadata
            }
            
            publish(EventType.MEMORY_CREATED, 'brain_memory', event_data)
        except ImportError:
            # 如果集成层未初始化，跳过事件发布
            pass
    
    def store_with_context(self, content: str, context: Dict, **kwargs) -> str:
        """带上下文的存储"""
        metadata = {
            'context': context,
            'timestamp': time.time()
        }
        metadata.update(kwargs.get('metadata', {}))
        
        return self.store(content, metadata=metadata, **kwargs)
    
    def get_stats(self) -> Dict:
        """获取路由器统计"""
        stats = {
            'queries': self._stats['queries'],
            'hits': self._stats['hits'],
            'hit_rate': {},
            'avg_latency': {}
        }
        
        # 计算命中率和平均延迟
        for mem_type in ['short_term', 'long_term']:
            total = self._stats['queries'][mem_type]
            stats['hit_rate'][mem_type] = self._stats['hits'][mem_type] / total if total > 0 else 0
            latencies = self._stats['latency'][mem_type]
            stats['avg_latency'][mem_type] = sum(latencies) / len(latencies) if latencies else 0
        
        # 添加子系统统计
        if self._hippocampus and self._neocortex:
            stats['hippocampus'] = self._hippocampus.get_statistics()
            stats['neocortex'] = self._neocortex.get_graph_summary()
        
        return stats
    
    def get_hippocampus(self):
        """获取海马体实例"""
        self._init_components()
        return self._hippocampus
    
    def get_neocortex(self):
        """获取新皮层实例"""
        self._init_components()
        return self._neocortex
    
    def get_consolidator(self):
        """获取巩固器实例"""
        self._init_components()
        return self._consolidator
    
    def shutdown(self):
        """关闭路由器"""
        if self._consolidator:
            self._consolidator.stop()
        self._logger.info("记忆路由器已关闭")


# 单例模式
_router_instance = None

def get_brain_memory_router() -> BrainMemoryRouter:
    """获取大脑记忆路由器实例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = BrainMemoryRouter()
    return _router_instance