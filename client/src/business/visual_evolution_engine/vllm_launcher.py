"""
vLLM 高性能推理服务器
======================

vLLM 优势:
- PagedAttention: 显存利用率提升 2-4 倍
- 吞吐量: 比 HuggingFace Transformers 快 24 倍
- 支持连续批处理
- 零拷贝 KV 缓存

Author: Hermes Desktop Team
"""

import subprocess
import asyncio
import httpx
from typing import Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class vLLMServerConfig:
    """vLLM 服务器配置"""
    model: str = "qwen2.5:7b"
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 性能参数
    tensor_parallel_size: int = 1  # GPU 数量
    gpu_memory_utilization: float = 0.90  # GPU 显存利用率
    max_num_batched_tokens: int = 8192
    max_num_seqs: int = 256
    
    # 上下文
    max_model_len: int = 8192
    context_size: int = 8192
    
    # 其他
    dtype: str = "half"  # half, float16, bfloat16
    enforcement_eager: bool = False  # 调试用
    trust_remote_code: bool = True


class vLLMServer:
    """
    vLLM 推理服务器管理器
    
    功能:
    - 自动下载和启动模型
    - 健康检查和监控
    - 自动重启
    - 优雅关闭
    """
    
    def __init__(self, config: Optional[vLLMServerConfig] = None):
        self.config = config or vLLMServerConfig()
        self.process: Optional[subprocess.Popen] = None
        self.base_url = f"http://{self.config.host}:{self.config.port}"
        self._running = False
    
    async def start(self, model_path: Optional[str] = None) -> bool:
        """
        启动 vLLM 服务器
        
        Args:
            model_path: 模型路径或 HuggingFace 模型名
            
        Returns:
            是否启动成功
        """
        if self._running:
            logger.info("vLLM server already running")
            return True
        
        # 构建命令
        model = model_path or self.config.model
        
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model,
            "--host", self.config.host,
            "--port", str(self.config.port),
            "--dtype", self.config.dtype,
            "--gpu-memory-utilization", str(self.config.gpu_memory_utilization),
            "--max-model-len", str(self.config.max_model_len),
            "--tensor-parallel-size", str(self.config.tensor_parallel_size),
            "--trust-remote-code",
        ]
        
        if self.config.max_num_batched_tokens:
            cmd.extend(["--max-num-batched-tokens", str(self.config.max_num_batched_tokens)])
        
        if self.config.max_num_seqs:
            cmd.extend(["--max-num-seqs", str(self.config.max_num_seqs)])
        
        logger.info(f"Starting vLLM: {' '.join(cmd)}")
        
        try:
            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            
            # 等待服务就绪
            if await self._wait_for_ready(timeout=120):
                self._running = True
                logger.info(f"vLLM server ready at {self.base_url}")
                return True
            else:
                logger.error("vLLM server failed to start")
                return False
                
        except FileNotFoundError:
            logger.error("vLLM not installed. Run: pip install vllm")
            return False
        except Exception as e:
            logger.error(f"Failed to start vLLM: {e}")
            return False
    
    async def _wait_for_ready(self, timeout: int = 120) -> bool:
        """等待服务就绪"""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(f"{self.base_url}/health")
                    if r.status_code == 200:
                        return True
            except:
                pass
            
            # 检查进程是否还在运行
            if self.process and self.process.poll() is not None:
                # 读取错误输出
                if self.process.stdout:
                    output = self.process.stdout.read(500)
                    logger.error(f"vLLM process exited: {output}")
                return False
            
            await asyncio.sleep(2)
        
        return False
    
    async def stop(self):
        """优雅关闭服务器"""
        if not self._running:
            return
        
        logger.info("Stopping vLLM server...")
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        
        self._running = False
        logger.info("vLLM server stopped")
    
    async def restart(self, model_path: Optional[str] = None):
        """重启服务器"""
        await self.stop()
        await asyncio.sleep(5)  # 等待资源释放
        await self.start(model_path)
    
    async def chat(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """发送聊天请求"""
        model = model or self.config.model
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    **kwargs,
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    
    def is_running(self) -> bool:
        """检查是否运行中"""
        return self._running and self.process and self.process.poll() is None
    
    async def get_stats(self) -> dict:
        """获取统计信息"""
        if not self.is_running():
            return {"status": "stopped"}
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/stats")
                if r.status_code == 200:
                    return r.json()
        except:
            pass
        
        return {"status": "unknown"}


# ─────────────────────────────────────────────────────────────────────────────
# 模型选择策略
# ─────────────────────────────────────────────────────────────────────────────

class ModelSelector:
    """
    模型选择器
    
    根据任务类型和硬件自动选择最优模型
    """
    
    # 模型性能分级
    MODELS = {
        # 快速响应 (CPU 或 低配GPU)
        "fast": [
            ("qwen2.5:0.5b", "local"),
            ("phi3:3.8b", "local"),
            ("llama3.2:1b", "local"),
        ],
        
        # 均衡 (中配GPU)
        "balanced": [
            ("qwen2.5:7b", "vllm"),
            ("qwen2.5:7b", "ollama"),
            ("llama3.2:7b", "vllm"),
        ],
        
        # 高质量 (高配GPU)
        "quality": [
            ("qwen2.5:14b", "vllm"),
            ("qwen2.5:32b", "vllm"),
            ("llama3.1:8b", "vllm"),
        ],
        
        # 最高质量 (远程)
        "premium": [
            ("deepseek-chat", "remote"),
            ("gpt-4o", "remote"),
            ("claude-3.5", "remote"),
        ],
    }
    
    # 硬件到策略映射
    HARDWARE_STRATEGY = {
        # (cpu_cores, memory_gb, has_gpu, gpu_memory_gb) -> strategy
        (4, 8, False, 0): "fast",
        (8, 16, False, 0): "fast",
        (8, 16, True, 8): "balanced",
        (12, 32, True, 16): "balanced",
        (12, 64, True, 24): "quality",
        (16, 128, True, 40): "quality",
        (0, 0, False, 0): "premium",  # 网络优先
    }
    
    @classmethod
    def get_strategy(cls, cpu_cores: int, memory_gb: float, 
                     has_gpu: bool, gpu_memory_gb: float) -> str:
        """根据硬件选择策略"""
        key = (cpu_cores, memory_gb, has_gpu, gpu_memory_gb)
        
        # 精确匹配
        if key in cls.HARDWARE_STRATEGY:
            return cls.HARDWARE_STRATEGY[key]
        
        # 模糊匹配
        if has_gpu:
            if gpu_memory_gb >= 20:
                return "quality"
            elif gpu_memory_gb >= 8:
                return "balanced"
            else:
                return "fast"
        else:
            if memory_gb >= 16:
                return "fast"
            else:
                return "fast"  # 只能小模型
    
    @classmethod
    def select_model(cls, strategy: str) -> tuple:
        """选择模型"""
        models = cls.MODELS.get(strategy, cls.MODELS["fast"])
        return models[0]  # 返回第一个选项


# ─────────────────────────────────────────────────────────────────────────────
# 一键部署脚本
# ─────────────────────────────────────────────────────────────────────────────

def install_vllm():
    """安装 vLLM"""
    logger.info("Installing vLLM...")
    subprocess.run(
        ["pip", "install", "vllm", "--upgrade"],
        check=True,
    )
    logger.info("vLLM installed successfully")


async def quick_start(
    model: str = "qwen2.5:7b",
    port: int = 8000,
    gpu_memory_utilization: float = 0.90,
) -> vLLMServer:
    """
    快速启动 vLLM 服务器
    
    Usage:
        server = await quick_start("qwen2.5:7b")
        response = await server.chat([{"role": "user", "content": "Hello!"}])
        await server.stop()
    """
    config = vLLMServerConfig(
        model=model,
        port=port,
        gpu_memory_utilization=gpu_memory_utilization,
    )
    
    server = vLLMServer(config)
    
    success = await server.start()
    if not success:
        raise RuntimeError(f"Failed to start vLLM server for model: {model}")
    
    return server


# ─────────────────────────────────────────────────────────────────────────────
# 使用示例
# ─────────────────────────────────────────────────────────────────────────────

async def example():
    """使用示例"""
    # 1. 快速启动
    server = await quick_start("qwen2.5:7b")
    
    try:
        # 2. 发送请求
        response = await server.chat([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"}
        ])
        print(f"Response: {response}")
        
        # 3. 获取统计
        stats = await server.get_stats()
        print(f"Stats: {stats}")
        
    finally:
        # 4. 关闭
        await server.stop()


if __name__ == "__main__":
    asyncio.run(example())
