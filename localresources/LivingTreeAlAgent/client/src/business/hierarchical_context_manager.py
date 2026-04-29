"""
分层模型上下文管理系统
实现四类模型的固定窗口大小配置和智能上下文管理
"""

import os
import time
import json
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class ModelType(Enum):
    """模型类型"""
    FAST = "fast"              # 快速反应模型
    VISION = "vision"          # 截图识别模型
    QUERY = "query"            # 结构化查询模型
    REASONING = "reasoning"    # 大数据推理模型


class ContextLevel(Enum):
    """上下文级别"""
    L0 = "L0"  # 最小上下文（快速模型）
    L1 = "L1"  # 中等上下文（视觉模型）
    L2 = "L2"  # 较大上下文（查询模型）
    L3 = "L3"  # 最大上下文（推理模型）


@dataclass
class ModelConfig:
    """模型配置"""
    model_type: ModelType
    window_size: int          # 上下文窗口大小（tokens）
    temperature: float        # 温度参数
    max_tokens: int           # 最大生成tokens
    response_format: Optional[str] = None
    image_detail: Optional[str] = None
    presence_penalty: Optional[float] = None


@dataclass
class ContextTemplate:
    """上下文模板"""
    model_type: ModelType
    structure: Dict[str, str]  # 上下文结构定义
    system_prompt: str        # 系统提示
    token_allocation: Dict[str, float]  # Token分配比例


@dataclass
class SessionCache:
    """会话缓存"""
    session_id: str
    context: Dict[str, Any]
    timestamp: float
    model_usage: Dict[ModelType, int]  # 模型使用次数


@dataclass
class ModelUsage:
    """模型使用情况"""
    model_type: ModelType
    usage_count: int
    avg_response_time: float
    success_rate: float
    token_usage: int
    last_used: float


class HierarchicalContextManager:
    """
    分层模型上下文管理系统
    实现四类模型的固定窗口大小配置和智能上下文管理
    """
    
    def __init__(self):
        # 模型配置
        self.model_configs = {
            ModelType.FAST: ModelConfig(
                model_type=ModelType.FAST,
                window_size=2000,  # 1K-2K tokens
                temperature=0.1,
                max_tokens=1024
            ),
            ModelType.VISION: ModelConfig(
                model_type=ModelType.VISION,
                window_size=4000,  # 2K-4K tokens
                temperature=0.3,
                max_tokens=2048,
                image_detail="auto"
            ),
            ModelType.QUERY: ModelConfig(
                model_type=ModelType.QUERY,
                window_size=8000,  # 4K-8K tokens
                temperature=0.0,
                max_tokens=4096,
                response_format="json_object"
            ),
            ModelType.REASONING: ModelConfig(
                model_type=ModelType.REASONING,
                window_size=16000,  # 8K-16K tokens
                temperature=0.7,
                max_tokens=8192,
                presence_penalty=0.1
            )
        }
        
        # 上下文模板
        self.context_templates = {
            ModelType.FAST: ContextTemplate(
                model_type=ModelType.FAST,
                structure={
                    "currentFocus": "光标周围的10行代码",
                    "recentCommands": ["最后3条命令"],
                    "activeFile": "当前文件名"
                },
                system_prompt="只回答具体问题，不分析。保持回答简洁明了。",
                token_allocation={
                    "currentFocus": 0.6,
                    "recentCommands": 0.3,
                    "activeFile": 0.1
                }
            ),
            ModelType.VISION: ContextTemplate(
                model_type=ModelType.VISION,
                structure={
                    "screenshot": "base64图片",
                    "uiContext": "技术栈（React/Vue）",
                    "relatedCode": "1-2个相似组件"
                },
                system_prompt="专注于UI元素识别和分析，基于提供的截图生成相应的代码。",
                token_allocation={
                    "screenshot": 0.5,
                    "uiContext": 0.2,
                    "relatedCode": 0.3
                }
            ),
            ModelType.QUERY: ContextTemplate(
                model_type=ModelType.QUERY,
                structure={
                    "query": {"type": "SEARCH", "params": {}},
                    "data": ["向量搜索结果", "数据库schema摘要"],
                    "format": "TABLE"
                },
                system_prompt="只基于提供的数据回答，输出结构化格式。",
                token_allocation={
                    "query": 0.2,
                    "data": 0.7,
                    "format": 0.1
                }
            ),
            ModelType.REASONING: ContextTemplate(
                model_type=ModelType.REASONING,
                structure={
                    "problem": "清晰的问题定义",
                    "architecture": "项目骨架",
                    "code": ["核心文件", "相关文件摘要"],
                    "knowledge": "设计模式参考"
                },
                system_prompt="逐步推理，权衡利弊，提供详细的分析和解决方案。",
                token_allocation={
                    "problem": 0.05,
                    "architecture": 0.15,
                    "code": 0.6,
                    "knowledge": 0.2
                }
            )
        }
        
        # 三级缓存
        self.caches = {
            "L1": {},  # 会话缓存（当前对话）
            "L2": {},  # 项目缓存（工作区生命周期）
            "L3": {}   # 磁盘缓存（长期存储）
        }
        
        # 模型使用情况
        self.model_usage = {
            ModelType.FAST: ModelUsage(
                model_type=ModelType.FAST,
                usage_count=0,
                avg_response_time=0.0,
                success_rate=0.0,
                token_usage=0,
                last_used=0.0
            ),
            ModelType.VISION: ModelUsage(
                model_type=ModelType.VISION,
                usage_count=0,
                avg_response_time=0.0,
                success_rate=0.0,
                token_usage=0,
                last_used=0.0
            ),
            ModelType.QUERY: ModelUsage(
                model_type=ModelType.QUERY,
                usage_count=0,
                avg_response_time=0.0,
                success_rate=0.0,
                token_usage=0,
                last_used=0.0
            ),
            ModelType.REASONING: ModelUsage(
                model_type=ModelType.REASONING,
                usage_count=0,
                avg_response_time=0.0,
                success_rate=0.0,
                token_usage=0,
                last_used=0.0
            )
        }
        
        # 预热机制
        self.warmup_cache = {}
        
        # 锁
        self.lock = threading.Lock()
    
    def get_model_config(self, model_type: ModelType) -> ModelConfig:
        """
        获取模型配置
        """
        return self.model_configs.get(model_type)
    
    def get_context_template(self, model_type: ModelType) -> ContextTemplate:
        """
        获取上下文模板
        """
        return self.context_templates.get(model_type)
    
    def create_context(self, model_type: ModelType, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建上下文
        """
        template = self.get_context_template(model_type)
        if not template:
            return data
        
        # 构建上下文
        context = {}
        for key, placeholder in template.structure.items():
            context[key] = data.get(key, placeholder)
        
        # 智能截断
        context = self._smart_truncate(context, model_type)
        
        return context
    
    def _smart_truncate(self, context: Dict[str, Any], model_type: ModelType) -> Dict[str, Any]:
        """
        智能截断上下文
        保留结构（类/函数定义），去除细节（长注释/日志）
        """
        config = self.get_model_config(model_type)
        if not config:
            return context
        
        # 计算当前上下文大小
        current_size = self._estimate_token_size(context)
        max_size = config.window_size * 0.8  # 预留20%空间
        
        if current_size <= max_size:
            return context
        
        # 按Token分配比例截断
        template = self.get_context_template(model_type)
        if template:
            for key, ratio in template.token_allocation.items():
                if key in context:
                    item_size = self._estimate_token_size(context[key])
                    target_size = max_size * ratio
                    
                    if item_size > target_size:
                        context[key] = self._truncate_item(context[key], target_size)
        
        return context
    
    def _estimate_token_size(self, content: Any) -> int:
        """
        估计Token大小
        """
        if isinstance(content, str):
            return len(content) // 4  # 粗略估计：1 token ≈ 4 字符
        elif isinstance(content, dict):
            return sum(self._estimate_token_size(v) for v in content.values())
        elif isinstance(content, list):
            return sum(self._estimate_token_size(item) for item in content)
        else:
            return 0
    
    def _truncate_item(self, item: Any, max_tokens: int) -> Any:
        """
        截断项目
        """
        if isinstance(item, str):
            max_chars = max_tokens * 4
            if len(item) > max_chars:
                # 保留开头和结尾，中间省略
                return item[:max_chars//2] + "..." + item[-max_chars//2:]
            return item
        elif isinstance(item, dict):
            truncated = {}
            total_size = 0
            for key, value in item.items():
                value_size = self._estimate_token_size(value)
                if total_size + value_size <= max_tokens:
                    truncated[key] = value
                    total_size += value_size
                else:
                    remaining = max_tokens - total_size
                    if remaining > 0:
                        truncated[key] = self._truncate_item(value, remaining)
                    break
            return truncated
        elif isinstance(item, list):
            truncated = []
            total_size = 0
            for value in item:
                value_size = self._estimate_token_size(value)
                if total_size + value_size <= max_tokens:
                    truncated.append(value)
                    total_size += value_size
                else:
                    remaining = max_tokens - total_size
                    if remaining > 0:
                        truncated.append(self._truncate_item(value, remaining))
                    break
            return truncated
        else:
            return item
    
    def route_request(self, request: Dict[str, Any]) -> ModelType:
        """
        智能路由请求
        """
        # 基于请求特征选择模型
        input_text = request.get("input", "")
        input_length = len(input_text)
        
        # 包含截图/图片
        if "screenshot" in request or "image" in request:
            return ModelType.VISION
        
        # 数据查询/汇总/搜索
        if "query" in request or "search" in request or "data" in request:
            return ModelType.QUERY
        
        # 简单问题
        if input_length < 100 and any(keyword in input_text.lower() for keyword in ["如何", "什么", "哪里", "怎么"]):
            return ModelType.FAST
        
        # 复杂问题/规划/设计
        return ModelType.REASONING
    
    def update_session_cache(self, session_id: str, context: Dict[str, Any], model_type: ModelType):
        """
        更新会话缓存
        """
        with self.lock:
            # 更新L1缓存（会话缓存）
            self.caches["L1"][session_id] = SessionCache(
                session_id=session_id,
                context=context,
                timestamp=time.time(),
                model_usage={model_type: 1}
            )
            
            # 限制L1缓存大小
            if len(self.caches["L1"]) > 100:
                # 删除最旧的缓存
                oldest_session = min(self.caches["L1"], key=lambda x: self.caches["L1"][x].timestamp)
                del self.caches["L1"][oldest_session]
    
    def get_session_cache(self, session_id: str) -> Optional[SessionCache]:
        """
        获取会话缓存
        """
        with self.lock:
            return self.caches["L1"].get(session_id)
    
    def record_model_usage(self, model_type: ModelType, response_time: float, success: bool, token_usage: int):
        """
        记录模型使用情况
        """
        with self.lock:
            usage = self.model_usage[model_type]
            usage.usage_count += 1
            usage.avg_response_time = ((usage.avg_response_time * (usage.usage_count - 1)) + response_time) / usage.usage_count
            usage.success_rate = ((usage.success_rate * (usage.usage_count - 1)) + (1 if success else 0)) / usage.usage_count
            usage.token_usage += token_usage
            usage.last_used = time.time()
    
    def get_model_usage(self, model_type: ModelType) -> ModelUsage:
        """
        获取模型使用情况
        """
        return self.model_usage[model_type]
    
    def get_all_model_usage(self) -> Dict[ModelType, ModelUsage]:
        """
        获取所有模型使用情况
        """
        return self.model_usage
    
    def warmup_model(self, model_type: ModelType):
        """
        预热模型
        """
        with self.lock:
            if model_type not in self.warmup_cache:
                # 生成预热上下文
                template = self.get_context_template(model_type)
                if template:
                    warmup_context = {}
                    for key, placeholder in template.structure.items():
                        warmup_context[key] = placeholder
                    
                    self.warmup_cache[model_type] = {
                        "context": warmup_context,
                        "timestamp": time.time()
                    }
                    print(f"预热模型: {model_type.value}")
    
    def get_warmup_context(self, model_type: ModelType) -> Optional[Dict[str, Any]]:
        """
        获取预热上下文
        """
        with self.lock:
            warmup = self.warmup_cache.get(model_type)
            if warmup:
                # 检查预热是否过期（1小时）
                if time.time() - warmup["timestamp"] < 3600:
                    return warmup["context"]
                else:
                    # 预热过期，删除
                    del self.warmup_cache[model_type]
            return None
    
    def transfer_result(self, from_model: ModelType, to_model: ModelType, result: Any) -> Dict[str, Any]:
        """
        跨模型结果传递
        只传递摘要，而非原始上下文
        """
        # 生成结果摘要
        summary = self._generate_summary(result)
        
        # 根据目标模型类型构建上下文
        template = self.get_context_template(to_model)
        if not template:
            return {"summary": summary}
        
        # 构建目标模型的上下文
        context = {}
        for key in template.structure:
            if key == "knowledge" or key == "relatedCode" or key == "data":
                context[key] = summary
        
        return context
    
    def _generate_summary(self, result: Any) -> str:
        """
        生成结果摘要
        """
        if isinstance(result, str):
            # 文本摘要
            if len(result) > 200:
                return result[:150] + "..." + result[-50:]
            return result
        elif isinstance(result, dict):
            # 字典摘要
            summary = []
            for key, value in result.items():
                if isinstance(value, str) and len(value) > 50:
                    summary.append(f"{key}: {value[:50]}...")
                else:
                    summary.append(f"{key}: {value}")
            return " | ".join(summary)
        elif isinstance(result, list):
            # 列表摘要
            summary = []
            for item in result[:3]:  # 只取前3个
                if isinstance(item, str) and len(item) > 50:
                    summary.append(item[:50] + "...")
                else:
                    summary.append(str(item))
            if len(result) > 3:
                summary.append(f"... 共{len(result)}项")
            return " | ".join(summary)
        else:
            return str(result)
    
    def optimize_configs(self):
        """
        基于实际使用数据调优配置
        """
        with self.lock:
            for model_type, usage in self.model_usage.items():
                if usage.usage_count > 0:
                    # 基于使用率和成功率调优
                    config = self.model_configs[model_type]
                    
                    # 低使用率+好效果 → 可减少上下文
                    if usage.usage_count < 10 and usage.success_rate > 0.8:
                        config.window_size = max(int(config.window_size * 0.8), 1000)
                        print(f"优化 {model_type.value} 窗口大小: {config.window_size}")
                    
                    # 高使用率+差效果 → 可能需要增加上下文
                    elif usage.usage_count > 50 and usage.success_rate < 0.6:
                        config.window_size = min(int(config.window_size * 1.2), 32000)
                        print(f"优化 {model_type.value} 窗口大小: {config.window_size}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        """
        stats = {
            "cache": {
                "L1": len(self.caches["L1"]),
                "L2": len(self.caches["L2"]),
                "L3": len(self.caches["L3"])
            },
            "model_usage": {},
            "warmup": len(self.warmup_cache)
        }
        
        for model_type, usage in self.model_usage.items():
            stats["model_usage"][model_type.value] = {
                "usage_count": usage.usage_count,
                "avg_response_time": usage.avg_response_time,
                "success_rate": usage.success_rate,
                "token_usage": usage.token_usage,
                "last_used": usage.last_used
            }
        
        return stats
    
    def clear_cache(self, level: Optional[str] = None):
        """
        清理缓存
        """
        with self.lock:
            if level:
                if level in self.caches:
                    self.caches[level].clear()
            else:
                for cache_level in self.caches:
                    self.caches[cache_level].clear()
    
    def save_to_disk(self, path: str):
        """
        保存到磁盘
        """
        data = {
            "model_usage": {},
            "warmup_cache": self.warmup_cache
        }
        
        for model_type, usage in self.model_usage.items():
            data["model_usage"][model_type.value] = {
                "usage_count": usage.usage_count,
                "avg_response_time": usage.avg_response_time,
                "success_rate": usage.success_rate,
                "token_usage": usage.token_usage,
                "last_used": usage.last_used
            }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_from_disk(self, path: str):
        """
        从磁盘加载
        """
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 加载模型使用情况
                if "model_usage" in data:
                    for model_type_str, usage_data in data["model_usage"].items():
                        model_type = ModelType(model_type_str)
                        if model_type in self.model_usage:
                            usage = self.model_usage[model_type]
                            usage.usage_count = usage_data.get("usage_count", 0)
                            usage.avg_response_time = usage_data.get("avg_response_time", 0.0)
                            usage.success_rate = usage_data.get("success_rate", 0.0)
                            usage.token_usage = usage_data.get("token_usage", 0)
                            usage.last_used = usage_data.get("last_used", 0.0)
                
                # 加载预热缓存
                if "warmup_cache" in data:
                    self.warmup_cache = data["warmup_cache"]


# 全局分层上下文管理器实例
hierarchical_context_manager = None


def get_hierarchical_context_manager() -> HierarchicalContextManager:
    """
    获取分层上下文管理器
    
    Returns:
        HierarchicalContextManager: 分层上下文管理器实例
    """
    global hierarchical_context_manager
    if not hierarchical_context_manager:
        hierarchical_context_manager = HierarchicalContextManager()
    return hierarchical_context_manager


def create_hierarchical_context_manager() -> HierarchicalContextManager:
    """
    创建分层上下文管理器
    
    Returns:
        HierarchicalContextManager: 分层上下文管理器实例
    """
    return HierarchicalContextManager()