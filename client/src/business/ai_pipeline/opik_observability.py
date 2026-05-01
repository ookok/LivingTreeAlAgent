"""
Opik 可观测性平台集成

核心功能：
1. LLM 调用追踪与监控
2. 性能指标收集与分析
3. 成本追踪与优化建议
4. 质量评估与反馈收集
5. 支持多种 LLM 提供商（DeepSeek、OpenAI、Ollama等）

使用方式：
    from opik_observability import OpikObserver, LlmCallTracker
    
    # 初始化观测器
    observer = OpikObserver()
    
    # 追踪 LLM 调用
    with LlmCallTracker(observer, model="deepseek-v4-pro") as tracker:
        response = await call_llm(prompt)
        tracker.record_response(response, usage)
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import uuid
from loguru import logger

# 尝试导入 Opik
try:
    import opik
    from opik import Opik as OpikClient
    from opik.tracing import trace
    OPIK_AVAILABLE = True
except ImportError:
    OPIK_AVAILABLE = False
    OpikClient = None
    trace = lambda x: x


class LlmProvider(Enum):
    """LLM 提供商"""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LlmModel(Enum):
    """LLM 模型"""
    # DeepSeek
    DEEPSEEK_FLASH = "deepseek-v4-flash"
    DEEPSEEK_PRO = "deepseek-v4-pro"
    
    # OpenAI
    GPT_4 = "gpt-4"
    GPT_35_TURBO = "gpt-3.5-turbo"
    
    # Ollama
    LLAMA3 = "llama3"
    QWEN = "qwen"


@dataclass
class LlmCallMetrics:
    """LLM 调用指标"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None
    model: str = ""
    provider: str = ""


@dataclass
class LlmCallRecord:
    """LLM 调用记录"""
    id: str
    timestamp: datetime
    model: str
    provider: str
    prompt: str
    response: str
    metrics: LlmCallMetrics
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LlmCallTracker:
    """LLM 调用追踪器（上下文管理器）"""
    
    def __init__(self, observer: 'OpikObserver', model: str, provider: str):
        self.observer = observer
        self.model = model
        self.provider = provider
        self.start_time = 0
        self.call_id = str(uuid.uuid4())[:8]
    
    def __enter__(self):
        self.start_time = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.metrics = LlmCallMetrics(
                model=self.model,
                provider=self.provider,
                success=False,
                error=str(exc_val)
            )
        self.observer.record_call(self)
    
    async def __aenter__(self):
        self.start_time = asyncio.get_event_loop().time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.metrics = LlmCallMetrics(
                model=self.model,
                provider=self.provider,
                success=False,
                error=str(exc_val)
            )
        self.observer.record_call(self)
    
    def record_response(self, response: str, usage: Dict[str, Any]):
        """记录响应和用量"""
        end_time = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else time.time()
        
        self.metrics = LlmCallMetrics(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=int((end_time - self.start_time) * 1000),
            cost_usd=self._calculate_cost(usage),
            success=True,
            model=self.model,
            provider=self.provider
        )
        self.response = response
    
    def _calculate_cost(self, usage: Dict[str, Any]) -> float:
        """计算调用成本"""
        # 简化的成本计算（实际应根据各提供商定价更新）
        cost_per_1k_tokens = {
            "deepseek-v4-flash": 0.0002,
            "deepseek-v4-pro": 0.0005,
            "gpt-4": 0.01,
            "gpt-3.5-turbo": 0.0015,
            "llama3": 0.0  # 本地模型无成本
        }
        
        rate = cost_per_1k_tokens.get(self.model, 0.0003)
        return (usage.get("total_tokens", 0) / 1000) * rate


class OpikObserver:
    """
    Opik 可观测性平台
    
    核心功能：
    1. LLM 调用追踪与监控
    2. 性能指标收集与分析
    3. 成本追踪与优化建议
    4. 质量评估与反馈收集
    """
    
    def __init__(self, project_name: str = "AI-Pipeline"):
        self._logger = logger.bind(component="OpikObserver")
        self._project_name = project_name
        self._opik_client = None
        self._call_records: List[LlmCallRecord] = []
        self._metrics_cache = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "avg_latency_ms": 0,
            "success_rate": 0.0,
            "model_usage": {},
            "provider_usage": {}
        }
        
        self._init_opik()
    
    def _init_opik(self):
        """初始化 Opik 客户端"""
        if OPIK_AVAILABLE:
            try:
                self._opik_client = OpikClient(project_name=self._project_name)
                self._logger.info("Opik 客户端初始化成功")
            except Exception as e:
                self._logger.warning(f"Opik 初始化失败: {e}")
    
    def record_call(self, tracker: LlmCallTracker):
        """记录 LLM 调用"""
        record = LlmCallRecord(
            id=tracker.call_id,
            timestamp=datetime.now(),
            model=tracker.model,
            provider=tracker.provider,
            prompt=getattr(tracker, 'prompt', "")[:100],
            response=getattr(tracker, 'response', "")[:100],
            metrics=tracker.metrics,
            tags={"pipeline": "ai-pipeline"},
            metadata={"call_id": tracker.call_id}
        )
        
        self._call_records.append(record)
        self._update_metrics(tracker.metrics)
        
        # 通过 Opik 追踪
        if self._opik_client:
            self._track_with_opik(record)
        
        self._logger.debug(f"记录 LLM 调用: {tracker.model}, tokens: {tracker.metrics.total_tokens}")
    
    def _update_metrics(self, metrics: LlmCallMetrics):
        """更新聚合指标"""
        self._metrics_cache["total_calls"] += 1
        self._metrics_cache["total_tokens"] += metrics.total_tokens
        self._metrics_cache["total_cost_usd"] += metrics.cost_usd
        
        if metrics.success:
            self._metrics_cache["success_rate"] = (
                (self._metrics_cache["success_rate"] * (self._metrics_cache["total_calls"] - 1) + 1) 
                / self._metrics_cache["total_calls"]
            )
        else:
            self._metrics_cache["success_rate"] = (
                self._metrics_cache["success_rate"] * (self._metrics_cache["total_calls"] - 1) 
                / self._metrics_cache["total_calls"]
            )
        
        # 模型使用统计
        if metrics.model not in self._metrics_cache["model_usage"]:
            self._metrics_cache["model_usage"][metrics.model] = 0
        self._metrics_cache["model_usage"][metrics.model] += 1
        
        # 提供商使用统计
        if metrics.provider not in self._metrics_cache["provider_usage"]:
            self._metrics_cache["provider_usage"][metrics.provider] = 0
        self._metrics_cache["provider_usage"][metrics.provider] += 1
    
    def _track_with_opik(self, record: LlmCallRecord):
        """通过 Opik 追踪调用"""
        try:
            # 创建追踪 span
            import opik.tracing as opik_tracing
            
            with opik_tracing.start_span(
                name=f"llm_call_{record.model}",
                attributes={
                    "model": record.model,
                    "provider": record.provider,
                    "prompt_tokens": record.metrics.prompt_tokens,
                    "completion_tokens": record.metrics.completion_tokens,
                    "total_tokens": record.metrics.total_tokens,
                    "cost_usd": record.metrics.cost_usd,
                    "success": record.metrics.success
                }
            ) as span:
                span.set_output(record.response[:200])
                
        except Exception as e:
            self._logger.debug(f"Opik 追踪失败: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取聚合指标"""
        return {
            "total_calls": self._metrics_cache["total_calls"],
            "total_tokens": self._metrics_cache["total_tokens"],
            "total_cost_usd": round(self._metrics_cache["total_cost_usd"], 4),
            "success_rate": round(self._metrics_cache["success_rate"] * 100, 2),
            "model_usage": self._metrics_cache["model_usage"],
            "provider_usage": self._metrics_cache["provider_usage"],
            "recent_calls": [
                {
                    "id": r.id,
                    "model": r.model,
                    "timestamp": r.timestamp.isoformat(),
                    "tokens": r.metrics.total_tokens,
                    "success": r.metrics.success
                } for r in self._call_records[-10:]
            ]
        }
    
    def evaluate_quality(self, prompt: str, response: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """评估 LLM 响应质量"""
        evaluation = {
            "prompt_length": len(prompt),
            "response_length": len(response),
            "relevance": self._evaluate_relevance(prompt, response),
            "coherence": self._evaluate_coherence(response),
            "completeness": self._evaluate_completeness(prompt, response),
            "overall_score": 0.0
        }
        
        evaluation["overall_score"] = round(
            (evaluation["relevance"] + evaluation["coherence"] + evaluation["completeness"]) / 3,
            2
        )
        
        return evaluation
    
    def _evaluate_relevance(self, prompt: str, response: str) -> float:
        """评估相关性"""
        prompt_keywords = set(prompt.lower().split()[:10])
        response_keywords = set(response.lower().split()[:20])
        overlap = len(prompt_keywords & response_keywords)
        return min(1.0, overlap / len(prompt_keywords)) if prompt_keywords else 0.5
    
    def _evaluate_coherence(self, response: str) -> float:
        """评估连贯性"""
        sentences = response.split('.')
        if len(sentences) < 2:
            return 0.7
        
        # 简单的连贯性评分
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        return min(1.0, avg_sentence_length / 15)
    
    def _evaluate_completeness(self, prompt: str, response: str) -> float:
        """评估完整性"""
        # 基于关键词覆盖率的简单评估
        prompt_words = prompt.lower().split()
        response_words = response.lower().split()
        
        covered = sum(1 for w in prompt_words if w in response_words)
        return min(1.0, covered / len(prompt_words)) if prompt_words else 0.5
    
    def generate_report(self) -> str:
        """生成可观测性报告"""
        metrics = self.get_metrics()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AI Pipeline LLM 可观测性报告                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  📊 概览统计                                                             ║
║  ───────────────────────────────────────────────────────────────────────   ║
║  总调用次数:      {metrics['total_calls']:>10} 次                           ║
║  总 Token 数:    {metrics['total_tokens']:>10}                             ║
║  总成本(USD):    ${metrics['total_cost_usd']:>10.4f}                        ║
║  成功率:         {metrics['success_rate']:>10.2f}%                         ║
║                                                                          ║
║  🤖 模型使用分布                                                          ║
║  ───────────────────────────────────────────────────────────────────────   ║
"""
        
        for model, count in metrics['model_usage'].items():
            percentage = (count / metrics['total_calls']) * 100 if metrics['total_calls'] > 0 else 0
            report += f"║  {model:20}  {count:5} 次  ({percentage:5.1f}%)\n"
        
        report += f"""
║                                                                          ║
║  🏢 提供商使用分布                                                         ║
║  ───────────────────────────────────────────────────────────────────────   ║
"""
        
        for provider, count in metrics['provider_usage'].items():
            percentage = (count / metrics['total_calls']) * 100 if metrics['total_calls'] > 0 else 0
            report += f"║  {provider:20}  {count:5} 次  ({percentage:5.1f}%)\n"
        
        report += f"""
║                                                                          ║
║  📝 最近调用记录                                                          ║
║  ───────────────────────────────────────────────────────────────────────   ║
"""
        
        for call in metrics['recent_calls']:
            status = "✅" if call['success'] else "❌"
            report += f"║  {status} {call['id']}  {call['model']:20}  {call['tokens']:5} tokens\n"
        
        report += f"""
╚══════════════════════════════════════════════════════════════════════════════╝
        """
        
        return report
    
    def reset_metrics(self):
        """重置指标"""
        self._call_records.clear()
        self._metrics_cache = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "avg_latency_ms": 0,
            "success_rate": 0.0,
            "model_usage": {},
            "provider_usage": {}
        }


# ============= 全局单例 =============

_global_observer: Optional[OpikObserver] = None


def get_opik_observer() -> OpikObserver:
    """获取全局 Opik 观测器单例"""
    global _global_observer
    if _global_observer is None:
        _global_observer = OpikObserver(project_name="AI-Pipeline")
    return _global_observer


# ============= 快捷装饰器 =============

def track_llm_call(model: str, provider: str):
    """
    装饰器：追踪 LLM 调用
    
    Usage:
        @track_llm_call(model="deepseek-v4-pro", provider="deepseek")
        async def call_llm(prompt: str) -> str:
            # ...
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            observer = get_opik_observer()
            
            with LlmCallTracker(observer, model, provider) as tracker:
                result = await func(*args, **kwargs)
                
                if isinstance(result, dict):
                    tracker.record_response(
                        result.get("response", ""),
                        result.get("usage", {})
                    )
                else:
                    tracker.record_response(str(result), {})
                
                return result
        
        def sync_wrapper(*args, **kwargs):
            observer = get_opik_observer()
            
            with LlmCallTracker(observer, model, provider) as tracker:
                result = func(*args, **kwargs)
                
                if isinstance(result, dict):
                    tracker.record_response(
                        result.get("response", ""),
                        result.get("usage", {})
                    )
                else:
                    tracker.record_response(str(result), {})
                
                return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ============= DeepSeek Thinking 模式支持 =============

class DeepSeekClient:
    """
    DeepSeek API 客户端（支持 Thinking 模式）
    
    DeepSeek-V4-Pro 支持 thinking 模式，需要正确的 API 参数。
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.observer = get_opik_observer()
    
    async def chat_completion(self, model: str, messages: List[Dict[str, str]], 
                             max_tokens: int = 1024, thinking: bool = False) -> Dict[str, Any]:
        """
        调用 DeepSeek API
        
        Args:
            model: 模型名称 (deepseek-v4-flash 或 deepseek-v4-pro)
            messages: 消息列表
            max_tokens: 最大 token 数
            thinking: 是否启用 thinking 模式（仅 Pro 模型支持）
        
        Returns:
            响应结果
        """
        import httpx
        
        url = f"{self.base_url}/chat/completions"
        
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        # Thinking 模式参数（DeepSeek V4 Pro 支持）
        if thinking and "pro" in model.lower():
            data["thinking"] = {
                "type": "enabled",
                "thought": True,
                "thought_num": 5,
                "thought_max_token": 512
            }
        
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=data
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("choices"):
                response_text = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                
                # 记录到观测器
                with LlmCallTracker(self.observer, model, "deepseek") as tracker:
                    tracker.record_response(response_text, usage)
                
                return {
                    "response": response_text,
                    "usage": usage,
                    "thinking": thinking,
                    "model": model
                }
        
        return {}


# ============= 测试函数 =============

async def test_opik_integration():
    """测试 Opik 集成"""
    print("🧪 测试 Opik 可观测性集成")
    print("="*60)
    
    # 初始化观测器
    observer = get_opik_observer()
    
    # 测试追踪器
    with LlmCallTracker(observer, "deepseek-v4-pro", "deepseek") as tracker:
        tracker.prompt = "测试提示词"
        tracker.record_response("测试响应", {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})
    
    # 获取指标
    metrics = observer.get_metrics()
    print(f"✅ 指标收集成功")
    print(f"   总调用: {metrics['total_calls']}")
    print(f"   总Token: {metrics['total_tokens']}")
    print(f"   成功率: {metrics['success_rate']}%")
    
    # 生成报告
    report = observer.generate_report()
    print("\n📊 可观测性报告:")
    print(report)
    
    return True


if __name__ == "__main__":
    asyncio.run(test_opik_integration())