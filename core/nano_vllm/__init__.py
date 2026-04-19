"""
Nano-vLLM 客户端适配器
轻量级 vLLM 实现

借鉴 https://github.com/GeeeekExplorer/nano-vllm
约 1200 行 Python 代码实现 vLLM 核心功能
"""

import os
import re
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Iterator
from dataclasses import dataclass


@dataclass
class SamplingParams:
    """采样参数"""
    temperature: float = 0.6
    top_p: float = 0.9
    max_tokens: int = 256
    stop: Optional[List[str]] = None
    repetition_penalty: float = 1.0


@dataclass
class Output:
    """输出结果"""
    text: str
    token_ids: List[int] = None
    finish_reason: str = "stop"


class NanoVLLMClient:
    """
    Nano-vLLM 客户端

    特性：
    - API 兼容 vLLM
    - 前缀缓存
    - 张量并行
    - 轻量级 (~1200 行代码)
    """

    def __init__(
        self,
        model_path: str,
        tensor_parallel_size: int = 1,
        enforce_eager: bool = True,
        gpu_memory_utilization: float = 0.9,
        max_model_len: int = 4096,
        port: int = 8000,
        host: str = "localhost"
    ):
        self.model_path = Path(model_path)
        self.tensor_parallel_size = tensor_parallel_size
        self.enforce_eager = enforce_eager
        self.gpu_memory_utilization = gpu_memory_utilization
        self.max_model_len = max_model_len
        self.port = port
        self.host = host

        self.base_url = f"http://{host}:{port}"
        self._process: Optional[subprocess.Popen] = None
        self._is_running = False

    def start_server(self, cuda_visible_devices: str = None) -> bool:
        """
        启动 Nano-vLLM 服务器

        Args:
            cuda_visible_devices: GPU 设备号，如 "0,1"

        Returns:
            是否启动成功
        """
        # 检查 nanovllm 是否安装
        try:
            import nanovllm
            print(f"[NanoVLLMClient] nanovllm 版本: {nanovllm.__version__}")
        except ImportError:
            print("[NanoVLLMClient] nanovllm 未安装，请运行: pip install nanovllm")
            return False

        # 构建命令
        cmd = [
            "python", "-m", "nanovllm",
            "--model", str(self.model_path),
            "--tensor-parallel-size", str(self.tensor_parallel_size),
            "--gpu-memory-utilization", str(self.gpu_memory_utilization),
            "--max-model-len", str(self.max_model_len),
            "--port", str(self.port),
            "--host", self.host,
        ]

        if self.enforce_eager:
            cmd.append("--enforce-eager")

        env = os.environ.copy()
        if cuda_visible_devices:
            env["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices

        print(f"[NanoVLLMClient] 启动命令: {' '.join(cmd)}")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )

            # 检查是否启动成功
            import time
            start_time = time.time()
            timeout = 30
            
            while time.time() - start_time < timeout:
                # 检查进程是否还在运行
                if self._process.poll() is not None:
                    # 进程已经退出，读取错误信息
                    stdout, stderr = self._process.communicate()
                    print(f"[NanoVLLMClient] 服务启动失败，退出码: {self._process.returncode}")
                    print(f"[NanoVLLMClient] 标准输出: {stdout}")
                    print(f"[NanoVLLMClient] 标准错误: {stderr}")
                    return False
                
                # 尝试读取输出
                try:
                    stdout_line = self._process.stdout.readline()
                    if stdout_line:
                        print(f"[NanoVLLMClient] 服务输出: {stdout_line.strip()}")
                        if "Server started" in stdout_line or "Listening on" in stdout_line:
                            print(f"[NanoVLLMClient] 服务启动成功")
                            self._is_running = True
                            return True
                except Exception:
                    pass
                
                time.sleep(1)
            
            # 超时
            print(f"[NanoVLLMClient] 服务启动超时 ({timeout}秒)")
            self._process.terminate()
            self._process.wait()
            return False
        except Exception as e:
            print(f"[NanoVLLMClient] 启动 Nano-vLLM 失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def stop_server(self):
        """停止服务器"""
        if self._process:
            self._process.terminate()
            self._process.wait()
            self._is_running = False

    def is_running(self) -> bool:
        """检查服务是否运行"""
        return self._is_running

    def generate(
        self,
        prompts: Union[str, List[str]],
        sampling_params: Optional[SamplingParams] = None,
        **kwargs
    ) -> List[Output]:
        """
        生成文本

        API 与 vLLM 兼容
        """
        if sampling_params is None:
            sampling_params = SamplingParams()

        if isinstance(prompts, str):
            prompts = [prompts]

        # 构造请求
        request = {
            "prompt": prompts[0] if len(prompts) == 1 else prompts,
            "temperature": sampling_params.temperature,
            "top_p": sampling_params.top_p,
            "max_tokens": sampling_params.max_tokens,
            "stop": sampling_params.stop or [],
            "repetition_penalty": sampling_params.repetition_penalty,
        }
        request.update(kwargs)

        # 调用 API
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(
                f"{self.base_url}/generate",
                data=json.dumps(request).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))

            outputs = []
            if isinstance(result, dict) and "text" in result:
                texts = result["text"]
                if isinstance(texts, str):
                    texts = [texts]
                for text in texts:
                    outputs.append(Output(
                        text=text,
                        token_ids=result.get("token_ids", []),
                        finish_reason=result.get("finish_reason", "stop")
                    ))
            else:
                outputs.append(Output(text=str(result)))

            return outputs

        except urllib.error.URLError as e:
            # 如果服务未启动，返回模拟结果
            return [Output(text=f"[Nano-vLLM 未运行: {e}]")]

    def generate_stream(
        self,
        prompt: str,
        sampling_params: Optional[SamplingParams] = None,
        **kwargs
    ) -> Iterator[str]:
        """
        流式生成
        """
        if sampling_params is None:
            sampling_params = SamplingParams()

        request = {
            "prompt": prompt,
            "temperature": sampling_params.temperature,
            "top_p": sampling_params.top_p,
            "max_tokens": sampling_params.max_tokens,
            "stream": True,
        }
        request.update(kwargs)

        import urllib.request
        import urllib.error

        print(f"[NanoVLLMClient] 发送流式请求到: {self.base_url}/generate")
        print(f"[NanoVLLMClient] 请求参数: {json.dumps(request, ensure_ascii=False)[:200]}...")

        req = urllib.request.Request(
            f"{self.base_url}/generate",
            data=json.dumps(request).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            print(f"[NanoVLLMClient] 等待响应...")
            with urllib.request.urlopen(req, timeout=30) as response:
                print(f"[NanoVLLMClient] 收到响应，状态码: {response.getcode()}")
                print(f"[NanoVLLMClient] 响应头: {dict(response.getheaders())}")
                for i, line in enumerate(response):
                    if line:
                        line_str = line.decode('utf-8')
                        print(f"[NanoVLLMClient] 收到行 {i}: {line_str}")
                        try:
                            data = json.loads(line_str)
                            if "text" in data:
                                print(f"[NanoVLLMClient] 收到文本: {data['text']}")
                                yield data["text"]
                        except json.JSONDecodeError as e:
                            print(f"[NanoVLLMClient] JSON 解析错误: {e}")
                            yield f"[JSON Error: {e}]"
        except urllib.error.URLError as e:
            print(f"[NanoVLLMClient] URL 错误: {e}")
            yield f"[URL Error: {e}]"
        except Exception as e:
            print(f"[NanoVLLMClient] 其他错误: {e}")
            import traceback
            traceback.print_exc()
            yield f"[Error: {e}]"

    def get_tokenizer(self):
        """获取分词器（占位）"""
        # Nano-vLLM 内部处理分词
        return None


class LocalVLLMManager:
    """
    本地 vLLM 模型管理器

    支持：
    - Nano-vLLM
    - 标准 vLLM
    - llama-cpp-python
    """

    def __init__(self, models_dir: str = None):
        from core.config import get_config_dir

        if models_dir is None:
            models_dir = get_config_dir() / "models"

        self.models_dir = Path(models_dir)
        self.clients: Dict[str, NanoVLLMClient] = {}
        self.current_model: Optional[str] = None

    def register_model(
        self,
        name: str,
        model_path: str,
        **kwargs
    ) -> bool:
        """
        注册模型

        Args:
            name: 模型名称
            model_path: 模型路径
            **kwargs: 其他参数

        Returns:
            是否注册成功
        """
        if not Path(model_path).exists():
            print(f"模型路径不存在: {model_path}")
            return False

        try:
            client = NanoVLLMClient(model_path=model_path, **kwargs)
            self.clients[name] = client
            return True
        except Exception as e:
            print(f"注册模型失败: {e}")
            return False

    def start_model(self, name: str, **kwargs) -> bool:
        """启动指定模型"""
        if name not in self.clients:
            print(f"模型未注册: {name}")
            return False

        client = self.clients[name]
        return client.start_server(**kwargs)

    def stop_model(self, name: str = None):
        """停止模型"""
        if name:
            if name in self.clients:
                self.clients[name].stop_server()
        else:
            for client in self.clients.values():
                client.stop_server()

    def generate(
        self,
        prompt: str,
        model: str = None,
        **kwargs
    ) -> Output:
        """
        使用指定模型生成

        Args:
            prompt: 提示词
            model: 模型名称，默认使用当前模型
            **kwargs: 采样参数

        Returns:
            Output 对象
        """
        model_name = model or self.current_model
        if not model_name or model_name not in self.clients:
            return Output(text="[无可用模型]")

        client = self.clients[model_name]
        results = client.generate(prompts=[prompt], **kwargs)
        return results[0] if results else Output(text="[生成失败]")

    def list_models(self) -> List[Dict[str, Any]]:
        """列出已注册模型"""
        return [
            {
                "name": name,
                "path": str(client.model_path),
                "running": client.is_running()
            }
            for name, client in self.clients.items()
        ]

    def set_current_model(self, name: str):
        """设置当前模型"""
        if name in self.clients:
            self.current_model = name
        else:
            print(f"模型未注册: {name}")

    def get_current_model(self) -> Optional[str]:
        """获取当前模型"""
        return self.current_model


# 单例
_vllm_manager: Optional[LocalVLLMManager] = None


def get_vllm_manager() -> LocalVLLMManager:
    """获取 vLLM 管理器单例"""
    global _vllm_manager
    if _vllm_manager is None:
        _vllm_manager = LocalVLLMManager()
    return _vllm_manager
