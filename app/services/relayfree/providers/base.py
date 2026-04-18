"""
RelayFreeLLM Provider 基类
定义统一接口，所有 Provider 实现需继承此基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    """Provider 状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


@dataclass
class ProviderMetrics:
    """Provider 指标"""
    total_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    last_error: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.success_requests / self.total_requests


@dataclass
class BaseProviderConfig:
    """Provider 基础配置"""
    provider_id: str
    base_url: str
    auth: str = "bearer"  # bearer, header, ak_sk, spark_ws, none
    key_env_var: Optional[str] = None
    secret_env_var: Optional[str] = None
    secret2_env_var: Optional[str] = None
    header_field: str = "Authorization"
    priority: int = 500
    timeout: int = 60
    max_retries: int = 3
    capabilities: List[str] = field(default_factory=list)
    model_mapping: Dict[str, str] = field(default_factory=dict)
    extra_body: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""


class BaseProvider(ABC):
    """
    Provider 抽象基类
    
    所有厂商 Provider 必须实现此接口，
    支持同步/异步请求，自动熔断降级
    """
    
    def __init__(self, config: BaseProviderConfig):
        self.config = config
        self.provider_id = config.provider_id
        self.status = ProviderStatus.HEALTHY
        self.metrics = ProviderMetrics()
        self._health_history: List[bool] = []
        self._lock = asyncio.Lock()
        
    @property
    def is_healthy(self) -> bool:
        return self.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
    
    @property
    def priority(self) -> int:
        return self.config.priority
    
    def get_api_key(self) -> Optional[str]:
        """获取 API Key，支持环境变量"""
        import os
        if not self.config.key_env_var:
            return None
        return os.getenv(self.config.key_env_var)
    
    def get_secret_key(self) -> Optional[str]:
        """获取 Secret Key (AK/SK 场景)"""
        import os
        if not self.config.secret_env_var:
            return None
        return os.getenv(self.config.secret_env_var)
    
    def get_secret2_key(self) -> Optional[str]:
        """获取 Secret2 Key (讯飞等场景)"""
        import os
        if not self.config.secret2_env_var:
            return None
        return os.getenv(self.config.secret2_env_var)
    
    def map_model(self, model: str) -> str:
        """模型别名映射"""
        return self.config.model_mapping.get(model, model)
    
    def _build_headers(self, api_key: Optional[str] = None) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if not api_key:
            api_key = self.get_api_key()
            
        if api_key:
            if self.config.auth == "bearer":
                headers["Authorization"] = f"Bearer {api_key}"
            elif self.config.auth == "header":
                headers[self.config.header_field] = api_key
            elif self.config.auth == "x-api-key":
                headers["x-api-key"] = api_key
        
        return headers
    
    def _record_request(self, success: bool, latency_ms: float, error: Optional[str] = None):
        """记录请求指标"""
        self.metrics.total_requests += 1
        self.metrics.last_request_time = datetime.now()
        
        if success:
            self.metrics.success_requests += 1
        else:
            self.metrics.failed_requests += 1
            self.metrics.last_error = error
        
        # 移动平均计算延迟
        n = self.metrics.total_requests
        old_avg = self.metrics.avg_latency_ms
        self.metrics.avg_latency_ms = old_avg + (latency_ms - old_avg) / n
        
        # 健康历史记录 (最近 10 次)
        self._health_history.append(success)
        if len(self._health_history) > 10:
            self._health_history.pop(0)
        
        # 更新状态
        self._update_status()
    
    def _update_status(self):
        """基于指标更新 Provider 状态"""
        if len(self._health_history) < 5:
            return
            
        recent_success_rate = sum(self._health_history[-5:]) / 5
        
        if recent_success_rate >= 0.8:
            self.status = ProviderStatus.HEALTHY
        elif recent_success_rate >= 0.5:
            self.status = ProviderStatus.DEGRADED
        else:
            self.status = ProviderStatus.UNHEALTHY
    
    def mark_unhealthy(self, error: Optional[str] = None):
        """标记 Provider 不健康"""
        self._record_request(False, 0, error)
        if self.status == ProviderStatus.HEALTHY:
            self.status = ProviderStatus.DEGRADED
    
    async def with_retry(self, coro):
        """带重试的请求包装"""
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                start = time.time()
                result = await coro
                latency = (time.time() - start) * 1000
                self._record_request(True, latency)
                return result
            except Exception as e:
                last_error = str(e)
                latency = (time.time() - start) * 1000
                self._record_request(False, latency, str(e))
                logger.warning(f"[{self.provider_id}] 请求失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
                
        raise Exception(f"[{self.provider_id}] 所有重试均失败: {last_error}")
    
    # ==================== 抽象方法 (必须实现) ====================
    
    @abstractmethod
    async def create_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建对话补全请求
        
        Args:
            model: 模型标识 (可能需要映射)
            messages: 消息列表
            **kwargs: 其他参数 (temperature, max_tokens, stream 等)
            
        Returns:
            OpenAI 兼容格式响应
        """
        pass
    
    async def create_completion_stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        创建流式对话补全请求
        
        默认实现调用 create_completion 并转换为流式事件，
        子类可重写以提供原生流式支持
        """
        # 子类应重写此方法以提供原生流式支持
        response = await self.create_completion(model, messages, stream=True, **kwargs)
        
        # 模拟流式响应
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        for i in range(0, len(content), 10):
            chunk = content[i:i+10]
            yield {
                "choices": [{
                    "delta": {"content": chunk},
                    "index": 0,
                    "finish_reason": None
                }]
            }
            await asyncio.sleep(0.01)
        
        yield {
            "choices": [{
                "delta": {},
                "index": 0,
                "finish_reason": "stop"
            }]
        }
    
    @abstractmethod
    async def list_models(self) -> List[Dict[str, Any]]:
        """列出可用模型"""
        pass
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self.list_models()
            return True
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Provider 信息导出"""
        return {
            "provider_id": self.provider_id,
            "description": self.config.description,
            "priority": self.config.priority,
            "status": self.status.value,
            "capabilities": self.config.capabilities,
            "is_healthy": self.is_healthy,
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "success_rate": f"{self.metrics.success_rate:.1%}",
                "avg_latency_ms": f"{self.metrics.avg_latency_ms:.0f}",
                "last_request": self.metrics.last_request_time.isoformat() if self.metrics.last_request_time else None
            }
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.provider_id} status={self.status.value}>"