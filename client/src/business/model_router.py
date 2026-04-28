"""
ModelRouter - 多后端 LLM 路由器
支持 Ollama、Shimmy、OpenAI 三后端
"""
import sys
import os
import time
import json
import requests
from typing import Dict, List, Any, Optional, Iterator
from enum import Enum
from dataclasses import dataclass, field

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class BackendType(str, Enum):
    """后端类型"""
    OLLAMA = "ollama"
    SHIMMY = "shimmy"
    OPENAI = "openai"


@dataclass
class BackendConfig:
    """后端配置"""
    backend_type: BackendType
    base_url: str
    api_key: str = ""
    model_mapping: Dict[str, str] = field(default_factory=dict)  # 本地模型名 → 后端模型名
    priority: int = 0  # 优先级（数字越小优先级越高）
    enabled: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    backend: BackendType
    size: Optional[int] = None
    modified_at: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class BaseBackend:
    """后端基类"""
    
    def __init__(self, config: BackendConfig):
        self.config = config
        self.base_url = config.base_url
        self.api_key = config.api_key
        
    def chat(self, model: str, messages: List[Dict], **kwargs) -> Dict:
        """对话接口（OpenAI 格式，非流式）"""
        raise NotImplementedError
        
    def chat_stream(self, model: str, messages: List[Dict], **kwargs) -> Iterator[Dict]:
        """对话接口（流式，yield 每个 chunk）"""
        # 默认实现：调用非流式然后 yield 单个结果
        result = self.chat(model, messages, **kwargs)
        yield result
        
    def generate(self, model: str, prompt: str, **kwargs) -> Dict:
        """生成接口（Ollama 格式）"""
        raise NotImplementedError
        
    def list_models(self) -> List[ModelInfo]:
        """列出可用模型"""
        raise NotImplementedError
        
    def health_check(self) -> bool:
        """健康检查"""
        raise NotImplementedError
        
    def _convert_to_openai_format(self, ollama_request: Dict) -> Dict:
        """将 Ollama 格式转换为 OpenAI 格式"""
        # Ollama: {"model": "xxx", "prompt": "xxx", "stream": false}
        # OpenAI: {"model": "xxx", "messages": [{"role": "user", "content": "xxx"}]}
        
        openai_request = {
            "model": ollama_request.get("model"),
            "stream": ollama_request.get("stream", False)
        }
        
        # 将 prompt 转换为 messages
        prompt = ollama_request.get("prompt", "")
        if prompt:
            openai_request["messages"] = [{"role": "user", "content": prompt}]
        
        # 复制其他参数
        for key in ["temperature", "top_p", "max_tokens", "stop"]:
            if key in ollama_request:
                openai_request[key] = ollama_request[key]
        
        return openai_request
        
    def _convert_from_openai_format(self, openai_response: Dict) -> Dict:
        """将 OpenAI 格式转换为 Ollama 格式"""
        # OpenAI: {"choices": [{"message": {"content": "xxx"}}]}
        # Ollama: {"response": "xxx", "done": true}
        
        ollama_response = {
            "model": openai_response.get("model", ""),
            "done": True
        }
        
        # 提取内容
        choices = openai_response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            ollama_response["response"] = message.get("content", "")
        
        return ollama_response


class OllamaBackend(BaseBackend):
    """Ollama 后端（保持现有逻辑）"""
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        # Ollama 默认端口 11434
        if not self.base_url:
            self.base_url = "http://localhost:11434"
        
    def chat(self, model: str, messages: List[Dict], **kwargs) -> Dict:
        """使用 Ollama /api/chat 端点（非流式）"""
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        payload.update(kwargs)
        
        try:
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ollama chat 失败: {e}")
            raise
        
    def chat_stream(self, model: str, messages: List[Dict], **kwargs) -> Iterator[Dict]:
        """使用 Ollama /api/chat 端点（流式 SSE）"""
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        payload.update(kwargs)
        
        try:
            with requests.post(url, json=payload, stream=True, timeout=300) as response:
                response.raise_for_status()
                # SSE 解析
                for line in response.iter_lines():
                    if line:
                        # line 可能是 bytes
                        if isinstance(line, bytes):
                            line = line.decode('utf-8')
                        line = line.strip()
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                break
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Ollama chat_stream 失败: {e}")
            raise
        
    def generate(self, model: str, prompt: str, **kwargs) -> Dict:
        """使用 Ollama /api/generate 端点"""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        payload.update(kwargs)
        
        try:
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ollama generate 失败: {e}")
            raise
        
    def list_models(self) -> List[ModelInfo]:
        """列出 Ollama 模型"""
        url = f"{self.base_url}/api/tags"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get("models", []):
                models.append(ModelInfo(
                    name=model["name"],
                    backend=BackendType.OLLAMA,
                    size=model.get("size"),
                    modified_at=model.get("modified_at"),
                    details=model
                ))
            return models
        except Exception as e:
            logger.error(f"Ollama 列出模型失败: {e}")
            return []
        
    def health_check(self) -> bool:
        """检查 Ollama 健康状态"""
        url = f"{self.base_url}/api/tags"
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False

    def ping(self) -> bool:
        """Ollama 服务是否在线（调用根路径）"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except:
            return False

    def version(self) -> str:
        """获取 Ollama 版本"""
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=5)
            response.raise_for_status()
            return response.json().get("version", "unknown")
        except Exception:
            return "offline"

    # ── Ollama 专有方法 ───────────────────────────────────────
    
    def load_model(self, name: str, keep_alive: str | None = None) -> bool:
        """加载模型到内存"""
        try:
            payload = {"model": name}
            if keep_alive is not None:
                payload["keep_alive"] = keep_alive
            with requests.post(f"{self.base_url}/api/generate", json=payload, timeout=300) as r:
                r.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Ollama 加载模型失败: {e}")
            return False
    
    def unload_model(self, name: str) -> bool:
        """卸载模型（keep_alive=0）"""
        try:
            payload = {"model": name, "keep_alive": 0}
            with requests.post(f"{self.base_url}/api/generate", json=payload, timeout=300) as r:
                r.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Ollama 卸载模型失败: {e}")
            return False
    
    def is_loaded(self, name: str) -> bool:
        """检查模型是否在内存中"""
        try:
            with requests.post(f"{self.base_url}/api/show", json={"name": name}, timeout=5) as r:
                return r.status_code == 200
        except:
            return False
    
    def delete_model(self, name: str) -> bool:
        """从 Ollama 删除模型"""
        try:
            with requests.delete(f"{self.base_url}/api/delete", json={"name": name}, timeout=30) as r:
                r.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Ollama 删除模型失败: {e}")
            return False
    
    def get_model_info(self, name: str) -> Dict:
        """获取模型详细信息"""
        try:
            with requests.post(f"{self.base_url}/api/show", json={"name": name}, timeout=10) as r:
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.error(f"Ollama 获取模型信息失败: {e}")
            return {}


class ShimmyBackend(BaseBackend):
    """Shimmy 后端（OpenAI API 兼容）"""
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        # Shimmy 默认端口 8000
        if not self.base_url:
            self.base_url = "http://localhost:8000"
        
    def chat(self, model: str, messages: List[Dict], **kwargs) -> Dict:
        """使用 OpenAI /v1/chat/completions 端点（非流式）"""
        url = f"{self.base_url}/v1/chat/completions"
        
        # 映射模型名称
        shimmy_model = self.config.model_mapping.get(model, model)
        
        payload = {
            "model": shimmy_model,
            "messages": messages,
            "stream": False
        }
        payload.update(kwargs)
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=300)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Shimmy chat 失败: {e}")
            raise
        
    def chat_stream(self, model: str, messages: List[Dict], **kwargs) -> Iterator[Dict]:
        """使用 OpenAI /v1/chat/completions 端点（流式 SSE）"""
        url = f"{self.base_url}/v1/chat/completions"
        
        # 映射模型名称
        shimmy_model = self.config.model_mapping.get(model, model)
        
        payload = {
            "model": shimmy_model,
            "messages": messages,
            "stream": True
        }
        payload.update(kwargs)
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            with requests.post(url, json=payload, headers=headers, stream=True, timeout=300) as response:
                response.raise_for_status()
                # SSE 解析
                for line in response.iter_lines():
                    if line:
                        # line 可能是 bytes
                        if isinstance(line, bytes):
                            line = line.decode('utf-8')
                        line = line.strip()
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                break
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Shimmy chat_stream 失败: {e}")
            raise
        
    def generate(self, model: str, prompt: str, **kwargs) -> Dict:
        """Shimmy 使用 OpenAI 格式，将 generate 转换为 chat"""
        messages = [{"role": "user", "content": prompt}]
        openai_response = self.chat(model, messages, **kwargs)
        
        # 转换回 Ollama 格式
        return self._convert_from_openai_format(openai_response)
        
    def list_models(self) -> List[ModelInfo]:
        """列出 Shimmy 模型（OpenAI /v1/models 端点）"""
        url = f"{self.base_url}/v1/models"
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get("data", []):
                models.append(ModelInfo(
                    name=model["id"],
                    backend=BackendType.SHIMMY,
                    details=model
                ))
            return models
        except Exception as e:
            logger.error(f"Shimmy 列出模型失败: {e}")
            return []
        
    def health_check(self) -> bool:
        """检查 Shimmy 健康状态"""
        # Shimmy 有 /health 端点
        url = f"{self.base_url}/health"
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False


class OpenAIBackend(BaseBackend):
    """OpenAI 云端后端"""
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        # OpenAI API
        if not self.base_url:
            self.base_url = "https://api.openai.com"
        
        # 必须提供 API Key
        if not self.api_key:
            raise ValueError("OpenAI 后端必须提供 api_key")
        
    def chat(self, model: str, messages: List[Dict], **kwargs) -> Dict:
        """使用 OpenAI /v1/chat/completions 端点"""
        url = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        payload.update(kwargs)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=300)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"OpenAI chat 失败: {e}")
            raise
        
    def generate(self, model: str, prompt: str, **kwargs) -> Dict:
        """OpenAI 使用 chat 接口"""
        messages = [{"role": "user", "content": prompt}]
        openai_response = self.chat(model, messages, **kwargs)
        return self._convert_from_openai_format(openai_response)
        
    def list_models(self) -> List[ModelInfo]:
        """列出 OpenAI 模型"""
        url = f"{self.base_url}/v1/models"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get("data", []):
                models.append(ModelInfo(
                    name=model["id"],
                    backend=BackendType.OPENAI,
                    details=model
                ))
            return models
        except Exception as e:
            logger.error(f"OpenAI 列出模型失败: {e}")
            return []
        
    def health_check(self) -> bool:
        """检查 OpenAI 健康状态"""
        url = f"{self.base_url}/v1/models"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            return response.status_code == 200
        except:
            return False


class ModelRouter:
    """ModelRouter - 多后端 LLM 路由器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self.backends: Dict[str, BaseBackend] = {}
        self.backend_configs: Dict[str, BackendConfig] = {}
        self.enabled_backends: List[str] = []
        
        self._initialized = True
        logger.info("ModelRouter 初始化完成")
        
    def register_backend(self, name: str, config: BackendConfig) -> bool:
        """注册后端"""
        try:
            # 创建后端实例
            if config.backend_type == BackendType.OLLAMA:
                backend = OllamaBackend(config)
            elif config.backend_type == BackendType.SHIMMY:
                backend = ShimmyBackend(config)
            elif config.backend_type == BackendType.OPENAI:
                backend = OpenAIBackend(config)
            else:
                logger.error(f"不支持的后端类型: {config.backend_type}")
                return False
            
            # 保存配置和实例
            self.backend_configs[name] = config
            self.backends[name] = backend
            
            # 如果启用，添加到启用列表
            if config.enabled:
                self.enabled_backends.append(name)
                # 按优先级排序
                self.enabled_backends.sort(key=lambda x: self.backend_configs[x].priority)
            
            logger.info(f"注册后端成功: {name} ({config.backend_type})")
            return True
            
        except Exception as e:
            logger.error(f"注册后端失败: {name}, 错误: {e}")
            return False
        
    def unregister_backend(self, name: str):
        """注销后端"""
        if name in self.backends:
            del self.backends[name]
        if name in self.backend_configs:
            del self.backend_configs[name]
        if name in self.enabled_backends:
            self.enabled_backends.remove(name)
        
        logger.info(f"注销后端: {name}")
        
    def enable_backend(self, name: str):
        """启用后端"""
        if name in self.backend_configs:
            self.backend_configs[name].enabled = True
            if name not in self.enabled_backends:
                self.enabled_backends.append(name)
                self.enabled_backends.sort(key=lambda x: self.backend_configs[x].priority)
            logger.info(f"启用后端: {name}")
        
    def disable_backend(self, name: str):
        """禁用后端"""
        if name in self.backend_configs:
            self.backend_configs[name].enabled = False
            if name in self.enabled_backends:
                self.enabled_backends.remove(name)
            logger.info(f"禁用后端: {name}")
        
    def list_backends(self) -> List[Dict[str, Any]]:
        """列出所有后端"""
        result = []
        for name, config in self.backend_configs.items():
            result.append({
                "name": name,
                "type": config.backend_type,
                "base_url": config.base_url,
                "enabled": config.enabled,
                "priority": config.priority
            })
        return result
        
    def get_backend(self, name: str) -> Optional[BaseBackend]:
        """获取指定后端"""
        return self.backends.get(name)
        
    def route(self, model: str, task_type: str = "default") -> Optional[str]:
        """
        路由到合适的后端
        
        Args:
            model: 模型名称
            task_type: 任务类型（default/chat/generate）
            
        Returns:
            后端名称，如果没有可用后端则返回 None
        """
        # 简单路由逻辑：返回第一个启用的后端
        # TODO: 实现更复杂的路由逻辑（根据模型、任务类型、后端负载等）
        if self.enabled_backends:
            return self.enabled_backends[0]
        return None
        
    def chat(self, model: str, messages: List[Dict], backend: str = None, **kwargs) -> Dict:
        """
        对话接口
        
        Args:
            model: 模型名称
            messages: 消息列表
            backend: 指定后端（如果为 None，则自动路由）
            **kwargs: 其他参数
            
        Returns:
            OpenAI 格式的响应
        """
        # 如果没有指定后端，自动路由
        if backend is None:
            backend = self.route(model)
            if backend is None:
                raise RuntimeError("没有可用的后端")
        
        # 获取后端实例
        backend_instance = self.backends.get(backend)
        if backend_instance is None:
            raise RuntimeError(f"后端不存在: {backend}")
        
        # 调用后端
        return backend_instance.chat(model, messages, **kwargs)
        
    def generate(self, model: str, prompt: str, backend: str = None, **kwargs) -> Dict:
        """
        生成接口
        
        Args:
            model: 模型名称
            prompt: 提示词
            backend: 指定后端（如果为 None，则自动路由）
            **kwargs: 其他参数
            
        Returns:
            Ollama 格式的响应
        """
        # 如果没有指定后端，自动路由
        if backend is None:
            backend = self.route(model)
            if backend is None:
                raise RuntimeError("没有可用的后端")
        
        # 获取后端实例
        backend_instance = self.backends.get(backend)
        if backend_instance is None:
            raise RuntimeError(f"后端不存在: {backend}")
        
        # 调用后端
        return backend_instance.generate(model, prompt, **kwargs)
        
    def list_all_models(self) -> List[ModelInfo]:
        """列出所有后端的模型"""
        all_models = []
        for name in self.enabled_backends:
            backend = self.backends[name]
            try:
                models = backend.list_models()
                all_models.extend(models)
            except Exception as e:
                logger.error(f"列出后端 {name} 的模型失败: {e}")
        
        return all_models
        
    def health_check_all(self) -> Dict[str, bool]:
        """检查所有后端的健康状态"""
        result = {}
        for name, backend in self.backends.items():
            try:
                result[name] = backend.health_check()
            except Exception as e:
                logger.error(f"健康检查失败: {name}, 错误: {e}")
                result[name] = False
        
        return result
        
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_backends": len(self.backends),
            "enabled_backends": len(self.enabled_backends),
            "backends": self.list_backends()
        }


# ==================== 全局单例 ====================
def get_model_router() -> ModelRouter:
    """获取 ModelRouter 单例"""
    return ModelRouter()


# ==================== 快速配置函数 ====================
def setup_default_backends(router: ModelRouter = None) -> ModelRouter:
    """设置默认后端（Ollama + Shimmy）"""
    if router is None:
        router = get_model_router()
    
    # 注册 Ollama 后端（优先级 1）
    ollama_config = BackendConfig(
        backend_type=BackendType.OLLAMA,
        base_url="http://localhost:11434",
        priority=1,
        enabled=True
    )
    router.register_backend("ollama", ollama_config)
    
    # 注册 Shimmy 后端（优先级 2）
    shimmy_config = BackendConfig(
        backend_type=BackendType.SHIMMY,
        base_url="http://localhost:8000",
        priority=2,
        enabled=True
    )
    router.register_backend("shimmy", shimmy_config)
    
    logger.info("默认后端配置完成: Ollama (优先级 1), Shimmy (优先级 2)")
    return router


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("ModelRouter 测试")
    print("=" * 60)
    
    # 创建 ModelRouter
    router = setup_default_backends()
    
    # 列出所有后端
    print("\n[1] 所有后端:")
    for backend in router.list_backends():
        print(f"  - {backend['name']} ({backend['type']}) - {'启用' if backend['enabled'] else '禁用'}")
    
    # 健康检查
    print("\n[2] 健康检查:")
    health = router.health_check_all()
    for name, status in health.items():
        print(f"  - {name}: {'健康' if status else '异常'}")
    
    # 列出所有模型
    print("\n[3] 所有模型:")
    models = router.list_all_models()
    for model in models[:10]:  # 只显示前 10 个
        print(f"  - {model.name} ({model.backend})")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
