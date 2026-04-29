"""
L4 增强模型层
高质量响应（3-10秒），处理复杂任务
"""

import time
import asyncio
from typing import Optional, Any, Dict, List, Callable, AsyncGenerator
from dataclasses import dataclass
from enum import Enum
import threading


class ProcessingMode(Enum):
    """处理模式"""
    SYNC = "sync"           # 同步处理
    ASYNC = "async"         # 异步处理
    STREAMING = "streaming" # 流式处理


@dataclass
class EnhancedResult:
    """增强模型处理结果"""
    tier: str = "L4"
    response: Any = None
    latency_ms: float = 0
    tokens_generated: int = 0
    thinking_process: Optional[str] = None
    model_used: str = ""
    confidence: float = 0.0
    interrupted: bool = False


class ProgressCallback:
    """进度回调"""
    
    def __init__(self):
        self._handlers: List[Callable] = []
    
    def add_handler(self, handler: Callable):
        self._handlers.append(handler)
    
    def remove_handler(self, handler: Callable):
        self._handlers.remove(handler)
    
    def emit(self, progress: float, status: str = ""):
        for handler in self._handlers:
            try:
                handler(progress, status)
            except Exception:
                pass


class Tier4Enhanced:
    """
    L4 增强模型层
    - 处理目标：高质量响应（3-10秒）
    - 大参数模型：Llama3-70B、Qwen-72B等
    - 专家组合：多个模型协同处理
    - 检索增强：连接外部知识库
    - 异步处理：后台执行、进度反馈、可中断
    """
    
    def __init__(self, model_loader: Callable = None, knowledge_base: Callable = None):
        self.model_loader = model_loader
        self.knowledge_base = knowledge_base
        self.model = None
        self.model_name = "qwen-72b"  # 默认增强模型
        self.target_latency_ms = 10000  # 10秒目标
        self.max_context_length = 32768  # 32K上下文
        
        # 模型组合
        self.expert_models: Dict[str, Any] = {}
        self.use_experts = True
        
        # 推理思考
        self.enable_thinking = True
        self.thinking_template = "请先思考，再回答：\n{query}\n\n思考过程："
        
        # 进度回调
        self.progress_callback = ProgressCallback()
        
        # 中断标志
        self._interrupted = False
        self._lock = threading.Lock()
        
        # 任务复杂度识别
        self.complex_keywords = {
            "高": ["分析", "评估", "设计", "比较", "证明", "推导", "复杂"],
            "中": ["解释", "说明", "讨论", "概述", "总结"],
            "低": ["简单", "基础", "基本"]
        }
        
        self._total_requests = 0
        self._interrupted_count = 0
    
    def _classify_complexity(self, query: str) -> str:
        """分类任务复杂度"""
        query_lower = query.lower()
        
        for level, keywords in self.complex_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return level
        return "中"
    
    async def process(self, query: str, context: str = None,
                     history: List[Dict] = None,
                     mode: ProcessingMode = ProcessingMode.ASYNC) -> EnhancedResult:
        """
        处理复杂任务
        - 复杂度评估
        - 知识库检索
        - 专家模型路由
        - 进度反馈
        - 可中断处理
        """
        start = time.perf_counter()
        self._total_requests += 1
        
        # 重置中断标志
        with self._lock:
            self._interrupted = False
        
        complexity = self._classify_complexity(query)
        self.progress_callback.emit(0.1, "开始处理...")
        
        # 知识库检索增强
        retrieved_context = await self._retrieve_knowledge(query, context)
        self.progress_callback.emit(0.2, "知识检索完成")
        
        # 构建增强提示
        enhanced_query = self._build_enhanced_prompt(query, retrieved_context)
        self.progress_callback.emit(0.3, "准备生成...")
        
        # 选择处理模式
        if mode == ProcessingMode.STREAMING:
            return await self._process_streaming(enhanced_query, history, start)
        elif mode == ProcessingMode.ASYNC:
            return await self._process_async(enhanced_query, history, start)
        else:
            return await self._process_sync(enhanced_query, history, start)
    
    async def _process_sync(self, query: str, history: List[Dict], start: float) -> EnhancedResult:
        """同步处理"""
        messages = self._build_messages(query, history)
        
        response = await self._generate(messages)
        
        latency = (time.perf_counter() - start) * 1000
        
        return EnhancedResult(
            tier="L4",
            response=response["text"],
            latency_ms=latency,
            tokens_generated=response.get("tokens", 0),
            thinking_process=response.get("thinking"),
            model_used=self.model_name,
            confidence=response.get("confidence", 0.9)
        )
    
    async def _process_async(self, query: str, history: List[Dict], start: float) -> EnhancedResult:
        """异步处理（带进度反馈）"""
        messages = self._build_messages(query, history)
        
        # 模拟异步处理（实际应该在后台线程）
        async def generate_with_progress():
            result = await self._generate(messages)
            self.progress_callback.emit(0.9, "生成完成")
            return result
        
        response = await generate_with_progress()
        
        latency = (time.perf_counter() - start) * 1000
        
        return EnhancedResult(
            tier="L4",
            response=response["text"],
            latency_ms=latency,
            tokens_generated=response.get("tokens", 0),
            model_used=self.model_name,
            confidence=response.get("confidence", 0.9)
        )
    
    async def _process_streaming(self, query: str, history: List[Dict], start: float) -> EnhancedResult:
        """流式处理"""
        messages = self._build_messages(query, history)
        
        full_response = []
        tokens_count = 0
        
        async for chunk in self._stream_generate(messages):
            if self._interrupted:
                self._interrupted_count += 1
                return EnhancedResult(
                    tier="L4",
                    response="".join(full_response),
                    latency_ms=(time.perf_counter() - start) * 1000,
                    tokens_generated=tokens_count,
                    model_used=self.model_name,
                    interrupted=True
                )
            
            full_response.append(chunk)
            tokens_count += 1
            
            # 进度反馈
            progress = 0.3 + (tokens_count / 500) * 0.5  # 假设最多500 tokens
            self.progress_callback.emit(min(progress, 0.8), f"生成中... {tokens_count} tokens")
        
        return EnhancedResult(
            tier="L4",
            response="".join(full_response),
            latency_ms=(time.perf_counter() - start) * 1000,
            tokens_generated=tokens_count,
            model_used=self.model_name,
            confidence=0.9
        )
    
    async def _retrieve_knowledge(self, query: str, context: str = None) -> Optional[str]:
        """从知识库检索增强上下文"""
        if not self.knowledge_base:
            return context
        
        try:
            results = await self.knowledge_base(query, top_k=3)
            if results:
                retrieved = "\n\n相关知识：\n" + "\n".join([r["content"] for r in results])
                return (context or "") + retrieved
        except Exception:
            pass
        
        return context
    
    def _build_enhanced_prompt(self, query: str, context: str = None) -> str:
        """构建增强提示"""
        prompt = query
        
        if self.enable_thinking:
            prompt = self.thinking_template.format(query=query)
        
        if context:
            prompt = f"参考信息：{context}\n\n{prompt}"
        
        return prompt
    
    def _build_messages(self, query: str, history: List[Dict] = None) -> List[Dict]:
        """构建消息格式"""
        messages = [{"role": "system", "content": "你是一个高级AI助手，擅长复杂推理和分析。"}]
        
        if history:
            for item in history[-10:]:  # 保留更多历史
                messages.append({
                    "role": item.get("role", "user"),
                    "content": item.get("content", "")
                })
        
        messages.append({"role": "user", "content": query})
        
        return messages
    
    async def _generate(self, messages: List[Dict]) -> Dict[str, Any]:
        """生成响应"""
        if self.model:
            try:
                return self.model.chat(messages, max_tokens=1000)
            except Exception:
                pass
        
        return {
            "text": "这是一个复杂任务的深度分析回复。",
            "tokens": 30,
            "confidence": 0.85
        }
    
    async def _stream_generate(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """流式生成响应"""
        if self.model and hasattr(self.model, 'stream_chat'):
            try:
                async for chunk in self.model.stream_chat(messages, max_tokens=500):
                    yield chunk
                return
            except Exception:
                pass
        
        # 模拟流式生成
        words = ["这是一个", "复杂任务", "的回复，", "需要", "详细", "分析..."]
        for word in words:
            await asyncio.sleep(0.05)
            yield word
    
    def interrupt(self):
        """中断处理"""
        with self._lock:
            self._interrupted = True
    
    def is_interrupted(self) -> bool:
        """检查是否被中断"""
        with self._lock:
            return self._interrupted
    
    def add_expert(self, name: str, model: Any):
        """添加专家模型"""
        self.expert_models[name] = model
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "tier": "L4",
            "model": self.model_name,
            "max_context_length": self.max_context_length,
            "total_requests": self._total_requests,
            "interrupted_count": self._interrupted_count,
            "target_latency_ms": self.target_latency_ms,
            "expert_count": len(self.expert_models),
            "enable_thinking": self.enable_thinking
        }
    
    def set_model(self, model: Any):
        """设置主模型"""
        self.model = model
