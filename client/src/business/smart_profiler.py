"""
智能性能分析器 - 自动生成优化建议
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Callable, Any, Optional


@dataclass
class ProfileResult:
    """性能分析结果"""
    operation: str
    duration_ms: float
    threshold_ms: float
    exceeded: bool
    suggestion: Optional[str] = None


@dataclass
class OptimizationSuggestion:
    """优化建议"""
    operation: str
    current_duration_ms: float
    threshold_ms: float
    suggestion: str
    priority: str  # low, medium, high
    estimated_improvement: str


class SmartProfiler:
    """智能性能分析器"""
    
    def __init__(self):
        self._profiles: Dict[str, List[float]] = {}
        self._thresholds: Dict[str, float] = {
            "api_call": 1000.0,       # 超过1秒告警
            "database_query": 500.0,   # 超过0.5秒告警
            "code_execution": 10000.0, # 超过10秒告警
            "memory_retrieval": 200.0, # 超过0.2秒告警
            "file_operation": 1000.0,  # 超过1秒告警
            "llm_request": 3000.0,     # 超过3秒告警
        }
        self._suggestions: List[OptimizationSuggestion] = []
    
    async def profile(self, operation: str, func: Callable, *args, **kwargs) -> Any:
        """分析函数执行"""
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            duration = (time.time() - start) * 1000
            self._record_profile(operation, duration)
            
            if duration > self._thresholds.get(operation, 5000.0):
                self._trigger_optimization_suggestion(operation, duration)
    
    def _record_profile(self, operation: str, duration_ms: float):
        """记录性能数据"""
        if operation not in self._profiles:
            self._profiles[operation] = []
        
        self._profiles[operation].append(duration_ms)
        
        # 保留最近100条记录
        if len(self._profiles[operation]) > 100:
            self._profiles[operation].pop(0)
    
    def _trigger_optimization_suggestion(self, operation: str, duration_ms: float):
        """触发优化建议"""
        suggestions = self._generate_suggestions(operation, duration_ms)
        for suggestion in suggestions:
            self._suggestions.append(suggestion)
        
        # 保留最近50条建议
        if len(self._suggestions) > 50:
            self._suggestions.pop(0)
    
    def _generate_suggestions(self, operation: str, duration_ms: float) -> List[OptimizationSuggestion]:
        """生成优化建议"""
        suggestions = []
        threshold = self._thresholds.get(operation, 5000.0)
        
        if operation == "api_call":
            suggestions.append(OptimizationSuggestion(
                operation=operation,
                current_duration_ms=duration_ms,
                threshold_ms=threshold,
                suggestion="考虑启用API调用缓存或切换到更快的API服务",
                priority="high" if duration_ms > threshold * 2 else "medium",
                estimated_improvement="50-70%"
            ))
        
        elif operation == "database_query":
            suggestions.append(OptimizationSuggestion(
                operation=operation,
                current_duration_ms=duration_ms,
                threshold_ms=threshold,
                suggestion="检查数据库索引是否完善，考虑添加查询缓存",
                priority="high" if duration_ms > threshold * 2 else "medium",
                estimated_improvement="60-80%"
            ))
        
        elif operation == "code_execution":
            suggestions.append(OptimizationSuggestion(
                operation=operation,
                current_duration_ms=duration_ms,
                threshold_ms=threshold,
                suggestion="考虑增加代码执行超时时间或优化代码逻辑",
                priority="medium",
                estimated_improvement="30-50%"
            ))
        
        elif operation == "llm_request":
            suggestions.append(OptimizationSuggestion(
                operation=operation,
                current_duration_ms=duration_ms,
                threshold_ms=threshold,
                suggestion="考虑使用更快的模型或启用流式响应",
                priority="high" if duration_ms > threshold * 2 else "medium",
                estimated_improvement="40-60%"
            ))
        
        return suggestions
    
    def get_profiles(self, operation: Optional[str] = None) -> Dict[str, List[float]]:
        """获取性能数据"""
        if operation:
            return {operation: self._profiles.get(operation, [])}
        return self._profiles
    
    def get_suggestions(self, priority: Optional[str] = None) -> List[OptimizationSuggestion]:
        """获取优化建议"""
        if priority:
            return [s for s in self._suggestions if s.priority == priority]
        return list(self._suggestions)
    
    def get_statistics(self, operation: str) -> Dict[str, float]:
        """获取统计信息"""
        data = self._profiles.get(operation, [])
        if not data:
            return {}
        
        return {
            "count": len(data),
            "min": min(data),
            "max": max(data),
            "avg": sum(data) / len(data),
            "p95": sorted(data)[int(len(data) * 0.95)]
        }


def get_profiler() -> SmartProfiler:
    """获取智能性能分析器单例"""
    if not hasattr(get_profiler, '_instance'):
        get_profiler._instance = SmartProfiler()
    return get_profiler._instance