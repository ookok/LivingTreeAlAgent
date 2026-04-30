"""
智能配置推荐器 - 基于用户使用习惯提供个性化配置建议
"""

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class Recommendation:
    """配置推荐"""
    config_key: str
    value: Any
    reason: str
    confidence: float
    priority: str  # high, medium, low


class SmartConfigRecommender:
    """智能配置推荐器"""
    
    def __init__(self):
        self._usage_patterns = {}
        self._config_history = []
    
    async def recommend(self, usage_data: Dict[str, Any]) -> List[Recommendation]:
        """基于使用数据推荐配置"""
        recommendations = []
        
        # 分析使用模式
        patterns = self._analyze_patterns(usage_data)
        self._usage_patterns = patterns
        
        # 基于代码执行频率推荐
        if patterns.get("code_frequency", 0) > 0.7:
            recommendations.append(Recommendation(
                config_key="code_execution_timeout",
                value=60,
                reason="检测到高频代码执行，建议延长超时时间至60秒",
                confidence=0.9,
                priority="high"
            ))
            
            recommendations.append(Recommendation(
                config_key="enable_code_analysis",
                value=True,
                reason="检测到高频代码执行，建议启用代码分析功能",
                confidence=0.85,
                priority="medium"
            ))
        
        # 基于搜索频率推荐
        if patterns.get("web_search_frequency", 0) > 0.5:
            recommendations.append(Recommendation(
                config_key="search_providers",
                value=["google", "bing", "arxiv", "github"],
                reason="检测到频繁搜索行为，建议启用多搜索引擎",
                confidence=0.85,
                priority="high"
            ))
            
            recommendations.append(Recommendation(
                config_key="search_cache_enabled",
                value=True,
                reason="检测到频繁搜索行为，建议启用搜索缓存",
                confidence=0.75,
                priority="medium"
            ))
        
        # 基于文档分析频率推荐
        if patterns.get("document_analysis_frequency", 0) > 0.6:
            recommendations.append(Recommendation(
                config_key="document_chunk_size",
                value=512,
                reason="检测到频繁文档分析，建议调整文档切分大小",
                confidence=0.8,
                priority="medium"
            ))
        
        # 基于聊天频率推荐
        if patterns.get("chat_frequency", 0) > 0.8:
            recommendations.append(Recommendation(
                config_key="conversation_history_limit",
                value=1000,
                reason="检测到高频聊天，建议增加历史记录限制",
                confidence=0.8,
                priority="medium"
            ))
        
        # 基于内存使用推荐
        if patterns.get("memory_usage", 0) > 0.7:
            recommendations.append(Recommendation(
                config_key="memory_compression",
                value=True,
                reason="检测到高内存使用，建议启用内存压缩",
                confidence=0.7,
                priority="low"
            ))
        
        # 按优先级排序
        recommendations.sort(key=lambda r: {"high": 0, "medium": 1, "low": 2}[r.priority])
        
        return recommendations
    
    def _analyze_patterns(self, usage_data: Dict[str, Any]) -> Dict[str, float]:
        """分析使用模式"""
        patterns = {}
        
        # 计算各类操作频率
        total_actions = sum([
            usage_data.get("code_executions", 0),
            usage_data.get("web_searches", 0),
            usage_data.get("document_analyses", 0),
            usage_data.get("chat_messages", 0)
        ]) or 1
        
        patterns["code_frequency"] = usage_data.get("code_executions", 0) / total_actions
        patterns["web_search_frequency"] = usage_data.get("web_searches", 0) / total_actions
        patterns["document_analysis_frequency"] = usage_data.get("document_analyses", 0) / total_actions
        patterns["chat_frequency"] = usage_data.get("chat_messages", 0) / total_actions
        
        # 内存使用
        patterns["memory_usage"] = usage_data.get("memory_usage", 0.0)
        
        # 平均会话时长
        patterns["avg_session_duration"] = usage_data.get("avg_session_duration", 0)
        
        return patterns
    
    def track_config_change(self, config_key: str, old_value: Any, new_value: Any):
        """追踪配置变更"""
        import time
        self._config_history.append({
            "timestamp": time.time(),
            "config_key": config_key,
            "old_value": old_value,
            "new_value": new_value
        })
    
    def get_usage_patterns(self) -> Dict[str, float]:
        """获取使用模式"""
        return self._usage_patterns.copy()


def get_smart_recommender() -> SmartConfigRecommender:
    """获取智能推荐器单例"""
    if not hasattr(get_smart_recommender, '_instance'):
        get_smart_recommender._instance = SmartConfigRecommender()
    return get_smart_recommender._instance