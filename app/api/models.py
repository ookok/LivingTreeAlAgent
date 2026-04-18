"""
API 路由
提供 RESTful API 接口
"""
import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class GenerationRequest:
    """生成请求"""
    prompt: str
    model_id: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9


class APIModels:
    """API 模型路由"""
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """列出本地模型"""
        models = self.model_manager.list_local_models()
        return [m.to_dict() for m in models]
    
    async def download_model(self, model_id: str, model_name: str,
                            source: str = "modelscope") -> Dict[str, Any]:
        """下载模型"""
        task = await self.model_manager.download_model(model_id, model_name, source)
        return task.to_dict()
    
    async def get_download_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取下载状态"""
        task = self.model_manager.get_download_task(task_id)
        return task.to_dict() if task else None
    
    async def load_model(self, model_id: str, model_path: str,
                        config: Optional[Dict] = None) -> Dict[str, Any]:
        """加载模型"""
        success = self.model_manager.load_model(model_path, model_id, config)
        return {"success": success, "model_id": model_id}
    
    async def unload_model(self, model_id: str) -> Dict[str, Any]:
        """卸载模型"""
        success = self.model_manager.unload_model(model_id)
        return {"success": success, "model_id": model_id}
    
    async def get_loaded_models(self) -> List[Dict[str, Any]]:
        """获取已加载模型"""
        return self.model_manager.get_loaded_models()
    
    async def generate(self, request: GenerationRequest) -> Dict[str, Any]:
        """生成文本"""
        try:
            text = self.model_manager.generate(
                prompt=request.prompt,
                model_id=request.model_id,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p
            )
            return {"response": text}
        except Exception as e:
            return {"error": str(e)}


class APISystem:
    """API 系统路由"""
    
    def __init__(self, model_manager, metrics_collector):
        self.model_manager = model_manager
        self.metrics_collector = metrics_collector
    
    async def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        hardware = self.model_manager.refresh_hardware()
        metrics = self.metrics_collector.get_current_metrics()
        
        return {
            "hardware": hardware.to_dict(),
            "loaded_models": len(self.model_manager.model_instances),
            "metrics": {
                "cpu_percent": metrics.cpu_percent if metrics else 0,
                "memory_percent": metrics.memory_percent if metrics else 0,
                "disk_percent": metrics.disk_percent if metrics else 0
            }
        }
    
    async def get_metrics_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指标历史"""
        return self.metrics_collector.get_metrics_history(limit)
    
    async def get_prometheus_metrics(self) -> str:
        """获取 Prometheus 格式指标"""
        return self.metrics_collector.get_prometheus_metrics()
    
    async def get_alerts(self) -> List[Dict[str, Any]]:
        """获取告警"""
        alerts = self.metrics_collector.get_active_alerts()
        return [
            {
                "id": a.id,
                "metric": a.metric,
                "value": a.value,
                "threshold": a.threshold,
                "severity": a.severity.value,
                "message": a.message,
                "start_time": a.start_time.isoformat()
            }
            for a in alerts
        ]
