"""
简单但实用的 Ollama 客户端
支持聊天、模型列表、健康检查
"""
import json
import time
from typing import Iterator, Any
from dataclasses import dataclass, field

import requests


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatResponse:
    content: str
    done: bool = False
    usage: dict = field(default_factory=dict)


class OllamaSimpleClient:
    """简单的 Ollama 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    def ping(self) -> bool:
        """检查连接"""
        try:
            self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return True
        except Exception:
            return False
    
    def list_models(self) -> list[dict]:
        """获取模型列表"""
        try:
            r = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            data = r.json()
            models = []
            for m in data.get("models", []):
                models.append({
                    "name": m["name"],
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", "")
                })
            return models
        except Exception:
            return []
    
    def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str = "llama3",
        temperature: float = 0.7
    ) -> Iterator[ChatResponse]:
        """流式聊天"""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "options": {"temperature": temperature}
        }
        
        try:
            with self.session.post(url, json=payload, stream=True, timeout=300) as r:
                for line in r.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                msg = data["message"]
                                content = msg.get("content", "")
                                done = data.get("done", False)
                                usage = data.get("usage", {})
                                yield ChatResponse(
                                    content=content,
                                    done=done,
                                    usage=usage
                                )
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield ChatResponse(content=f"错误: {str(e)}", done=True)
    
    def chat_sync(
        self,
        messages: list[ChatMessage],
        model: str = "llama3",
        temperature: float = 0.7
    ) -> str:
        """同步聊天"""
        full_content = ""
        for chunk in self.chat_stream(messages, model, temperature):
            full_content += chunk.content
            if chunk.done:
                break
        return full_content
    
    def get_version(self) -> str:
        """获取版本（简单版）"""
        try:
            r = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return "Ollama (connected)"
        except Exception:
            return "Ollama (disconnected)"


# 全局单例
_ollama_instance: OllamaSimpleClient | None = None


def get_ollama_client() -> OllamaSimpleClient:
    """获取单例 Ollama 客户端"""
    global _ollama_instance
    if _ollama_instance is None:
        _ollama_instance = OllamaSimpleClient()
    return _ollama_instance
