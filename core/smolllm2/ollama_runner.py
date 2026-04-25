# -*- coding: utf-8 -*-
"""
SmolLM2 Ollama Runner 管理器
=========================

功能：
1. 自动创建/更新 SmolLM2 的 Ollama Modelfile
2. 管理 Ollama 模型生命周期
3. 生成请求与健康检测
"""

import os
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

import httpx

from core.logger import get_logger

from .models import SmolLM2Config
from .downloader import download_smolllm2

logger = get_logger('smolllm2.ollama_runner')


@dataclass
class OllamaStatus:
    """Ollama 状态"""
    available: bool
    version: str = ""
    models: list = None
    error: str = ""


class OllamaRunner:
    """
    SmolLM2 Ollama Runner

    管理 SmolLM2-135M 在 Ollama 中的运行
    """

    def __init__(self, config: Optional[SmolLM2Config] = None):
        self.config = config or SmolLM2Config()
        self._client: Optional[httpx.AsyncClient] = None
        self._model_path: Optional[Path] = None

        # Ollama 模型目录
        self.ollama_dir = Path.home() / ".ollama"
        self.models_dir = self.ollama_dir / "models"

    # ==================== 连接管理 ====================

    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.ollama_host,
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> OllamaStatus:
        """检查 Ollama 健康状态"""
        try:
            resp = await self.client.get("/api/version")
            if resp.status_code == 200:
                version = resp.json().get("version", "")

                # 检查模型是否已加载
                models_resp = await self.client.get("/api/tags")
                models = models_resp.json().get("models", []) if models_resp.status_code == 200 else []

                return OllamaStatus(
                    available=True,
                    version=version,
                    models=[m.get("name") for m in models]
                )
        except Exception as e:
            return OllamaStatus(available=False, error=str(e))

        return OllamaStatus(available=False, error="Unknown error")

    # ==================== 模型管理 ====================

    def _ensure_model_file(self) -> bool:
        """确保 Modelfile 存在"""
        try:
            # 检查本地 GGUF 文件
            gguf_path = self._find_local_gguf()
            if not gguf_path:
                logger.info("未找到本地 GGUF 文件，尝试下载...")
                gguf_path = download_smolllm2()
                if not gguf_path:
                    return False

            self._model_path = gguf_path

            # 创建 Ollama 模型目录
            ollama_models = self.ollama_dir / "models" / "file_context"
            ollama_models.mkdir(parents=True, exist_ok=True)

            # 复制 GGUF 文件到 Ollama 目录
            ollama_gguf_path = ollama_models / gguf_path.name
            if not ollama_gguf_path.exists():
                import shutil
                shutil.copy(gguf_path, ollama_gguf_path)

            # 创建或更新 Modelfile
            modelfile_path = self.ollama_dir / "models" / "Modelfile"
            gguf_rel_path = str(ollama_gguf_path.relative_to(self.ollama_dir / 'models'))
            system_prompt = self.config.system_prompt

            # 避免 f-string 中的 {{}} 冲突，使用普通字符串拼接
            lines = [
                f"FROM {gguf_rel_path}",
                "",
                f"PARAMETER num_ctx {self.config.num_ctx}",
                f"PARAMETER temperature {self.config.temperature}",
                f"PARAMETER num_gpu {self.config.num_gpu}",
                "",
                'TEMPLATE "{{ .System }} {{ .Prompt }}"',
                "",
                f'SYSTEM """{system_prompt}"""',
            ]
            modelfile_content = "\n".join(lines)
            with open(modelfile_path, "w", encoding="utf-8") as f:
                f.write(modelfile_content)

            return True

        except Exception as e:
            logger.info(f"创建 Modelfile 失败: {e}")
            return False

    def _find_local_gguf(self) -> Optional[Path]:
        """查找本地 GGUF 文件"""
        # 优先检查 Hermes 模型目录
        search_dirs = [
            Path.home() / ".hermes-desktop" / "models",
            Path.home() / ".ollama" / "models" / "file_context",
            self.models_dir / "file_context",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for gguf_file in search_dir.glob("*smollm2*.gguf"):
                if "q4_k" in gguf_file.name.lower() or "q5" in gguf_file.name.lower():
                    return gguf_file

            # 任意 SmolLM2 GGUF
            for gguf_file in search_dir.glob("*smollm2*.gguf"):
                return gguf_file

        return None

    async def create_model(self) -> bool:
        """在 Ollama 中创建模型"""
        try:
            # 确保 Modelfile 存在
            if not self._ensure_model_file():
                return False

            # 调用 ollama create
            model_name = self.config.ollama_model_name
            result = subprocess.run(
                ["ollama", "create", model_name, "-f",
                 str(self.ollama_dir / "models" / "Modelfile")],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                logger.info(f"模型 {model_name} 创建成功")
                return True
            else:
                logger.info(f"模型创建失败: {result.stderr}")
                return False

        except Exception as e:
            logger.info(f"创建模型异常: {e}")
            return False

    async def is_model_loaded(self) -> bool:
        """检查模型是否已加载"""
        status = await self.health_check()
        return self.config.ollama_model_name in status.models

    # ==================== 推理调用 ====================

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False
    ) -> str:
        """
        生成响应

        Args:
            prompt: 用户输入
            system: 系统提示词（可选，默认用配置的）
            stream: 是否流式输出

        Returns:
            模型生成的文本
        """
        payload = {
            "model": self.config.ollama_model_name,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": 256,  # 限制输出长度，快反场景不需要太长
            }
        }

        if system:
            payload["system"] = system
        else:
            payload["system"] = self.config.system_prompt

        try:
            resp = await self.client.post("/api/generate", json=payload)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("response", "").strip()
            else:
                raise RuntimeError(f"Ollama 返回错误: {resp.status_code}")
        except Exception as e:
            raise RuntimeError(f"SmolLM2 生成失败: {e}")

    async def chat(
        self,
        messages: list,
        stream: bool = False
    ) -> str:
        """
        对话生成

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            stream: 是否流式输出

        Returns:
            助手回复
        """
        payload = {
            "model": self.config.ollama_model_name,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
            }
        }

        try:
            resp = await self.client.post("/api/chat", json=payload)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("message", {}).get("content", "").strip()
            else:
                raise RuntimeError(f"Ollama 返回错误: {resp.status_code}")
        except Exception as e:
            raise RuntimeError(f"SmolLM2 对话失败: {e}")


# ==================== Runner 管理器 ====================

class OllamaRunnerManager:
    """
    Ollama Runner 管理器

    单例模式管理多个 SmolLM2 实例
    """

    _instance = None
    _runner: Optional[OllamaRunner] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_runner(self, config: Optional[SmolLM2Config] = None) -> OllamaRunner:
        """获取或创建 Runner"""
        if self._runner is None:
            self._runner = OllamaRunner(config)
        return self._runner

    async def ensure_ready(self) -> bool:
        """确保 Runner 就绪"""
        runner = await self.get_runner()

        # 检查 Ollama 是否可用
        status = await runner.health_check()
        if not status.available:
            logger.info(f"Ollama 不可用: {status.error}")
            return False

        # 检查模型是否已加载
        if not await runner.is_model_loaded():
            logger.info("模型未加载，尝试创建...")
            if not await runner.create_model():
                return False

        return True

    async def shutdown(self):
        """关闭 Runner"""
        if self._runner:
            await self._runner.close()
            self._runner = None


# ==================== 快捷函数 ====================

_runner_manager: Optional[OllamaRunnerManager] = None


async def get_runner_manager() -> OllamaRunnerManager:
    """获取 Runner 管理器"""
    global _runner_manager
    if _runner_manager is None:
        _runner_manager = OllamaRunnerManager()
    return _runner_manager


async def quick_generate(prompt: str, system: Optional[str] = None) -> str:
    """快捷生成"""
    manager = await get_runner_manager()
    runner = await manager.get_runner()
    return await runner.generate(prompt, system)
