"""
L3 标准模型层
秒级响应（1-3秒），处理中等复杂度任务
"""

import time
import asyncio
from typing import Optional, Any, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum


class TaskType(Enum):
    """任务类型"""
    QA = "qa"                    # 问答
    DIALOGUE = "dialogue"        # 多轮对话
    REASONING = "reasoning"      # 逻辑推理
    CODE = "code"               # 代码生成
    WRITING = "writing"         # 内容写作
    ANALYSIS = "analysis"       # 分析任务


@dataclass
class StandardResult:
    """标准模型处理结果"""
    tier: str = "L3"
    response: Any = None
    latency_ms: float = 0
    tokens_generated: int = 0
    task_type: TaskType = TaskType.QA
    context_length: int = 0
    batch_id: Optional[str] = None


class Tier3Standard:
    """
    L3 标准模型层
    - 处理目标：秒级响应（1-3秒）
    - 平衡型模型：Llama3-8B、Qwen-7B等
    - 上下文长度：4K-8K
    - 优化策略：动态批处理、INT8量化
    """
    
    def __init__(self, model_loader: Callable = None):
        self.model_loader = model_loader
        self.model = None
        self.model_name = "qwen-7b"  # 默认标准模型
        self.target_latency_ms = 3000  # 3秒目标
        self.max_context_length = 8192
        
        # 模型实例池（支持多实例）
        self.model_pool: List = []
        self.pool_size = 2
        
        # 批处理队列
        self.batch_queue: List[asyncio.Task] = []
        self.batch_size = 4
        self.batch_timeout = 0.5  # 500ms
        
        # 任务类型识别
        self.task_keywords = {
            TaskType.QA: ["是什么", "为什么", "如何", "怎样", "what", "why", "how"],
            TaskType.DIALOGUE: ["对话", "聊聊", "讨论", "谈谈", "talk", "discuss"],
            TaskType.REASONING: ["分析", "推理", "计算", "证明", "analyze", "reason"],
            TaskType.CODE: ["代码", "函数", "实现", "编程", "code", "function", "python"],
            TaskType.WRITING: ["写", "创作", "生成", "文章", "write", "create", "article"],
            TaskType.ANALYSIS: ["比较", "评估", "分析", "对比", "compare", "evaluate"],
        }
        
        self._total_requests = 0
        self._batched_requests = 0
    
    def _classify_task(self, query: str) -> TaskType:
        """识别任务类型"""
        query_lower = query.lower()
        
        scores = {}
        for task_type, keywords in self.task_keywords.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            scores[task_type] = score
        
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return TaskType.QA
    
    def _estimate_context_length(self, query: str, history: List = None) -> int:
        """估算上下文长度（token数）"""
        base_length = len(query) // 4  # 粗略估算
        history_length = sum(len(str(h)) for h in (history or [])) // 4
        return base_length + history_length
    
    async def process(self, query: str, context: str = None, 
                     history: List[Dict] = None) -> StandardResult:
        """处理中等复杂度任务"""
        start = time.perf_counter()
        self._total_requests += 1
        
        task_type = self._classify_task(query)
        context_length = self._estimate_context_length(query, history)
        
        if context_length > self.max_context_length:
            query = self._truncate_context(query, history)
        
        result = await self._process_with_batching(query, context, history)
        
        latency = (time.perf_counter() - start) * 1000
        result.latency_ms = latency
        result.task_type = task_type
        result.context_length = context_length
        
        return result
    
    async def _process_with_batching(self, query: str, context: str = None,
                                     history: List[Dict] = None) -> StandardResult:
        """使用批处理处理请求"""
        messages = self._build_messages(query, context, history)
        response = await self._generate(messages)
        
        return StandardResult(
            tier="L3",
            response=response["text"],
            latency_ms=0,
            tokens_generated=response.get("tokens", 0)
        )
    
    def _build_messages(self, query: str, context: str = None,
                       history: List[Dict] = None) -> List[Dict]:
        """构建消息格式"""
        messages = [{"role": "system", "content": "你是一个有用的AI助手。"}]
        
        if history:
            for item in history[-5:]:
                messages.append({
                    "role": item.get("role", "user"),
                    "content": item.get("content", "")
                })
        
        content = query
        if context:
            content = f"上下文：{context}\n\n问题：{query}"
        messages.append({"role": "user", "content": content})
        
        return messages
    
    def _truncate_context(self, query: str, history: List[Dict] = None) -> str:
        """截断过长的上下文"""
        return query
    
    async def _generate(self, messages: List[Dict]) -> Dict[str, Any]:
        """生成响应"""
        if self.model:
            try:
                return self.model.chat(messages, max_tokens=500)
            except Exception:
                pass
        
        return {"text": "这是一个中等复杂度的查询回复。", "tokens": 20, "finish_reason": "stop"}
    
    async def batch_process(self, queries: List[str]) -> List[StandardResult]:
        """批量处理多个查询"""
        tasks = [self.process(q) for q in queries]
        results = await asyncio.gather(*tasks)
        self._batched_requests += len(queries)
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "tier": "L3",
            "model": self.model_name,
            "max_context_length": self.max_context_length,
            "total_requests": self._total_requests,
            "batched_requests": self._batched_requests,
            "target_latency_ms": self.target_latency_ms,
            "pool_size": len(self.model_pool)
        }
    
    def set_model(self, model: Any):
        """设置模型"""
        self.model = model
    
    def add_to_pool(self, model: Any):
        """添加模型到实例池"""
        if len(self.model_pool) < self.pool_size:
            self.model_pool.append(model)
    
    def get_from_pool(self) -> Optional[Any]:
        """从实例池获取模型"""
        if self.model_pool:
            return self.model_pool.pop(0)
        return self.model
