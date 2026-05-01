"""
Ollama 客户端 - 与本地 Ollama 服务通信
"""
import json
import requests
from typing import Dict, List, Optional, Any, Iterator
from pathlib import Path
from backend.shared.logger import get_logger

logger = get_logger('ollama')


class OllamaClient:
    """Ollama 客户端"""
    
    def __init__(self, base_url: str = None):
        """
        初始化 Ollama 客户端
        
        Args:
            base_url: Ollama 服务地址
        """
        self.base_url = base_url or 'http://localhost:11434'
        self.api_url = f'{self.base_url}/api'
        
    def chat(
        self,
        model: str = 'llama3',
        messages: List[Dict] = None,
        stream: bool = False,
        options: Dict = None
    ) -> Dict:
        """
        聊天对话
        
        Args:
            model: 模型名称
            messages: 消息列表
            stream: 是否流式输出
            options: 其他选项
            
        Returns:
            响应字典
        """
        messages = messages or []
        
        data = {
            'model': model,
            'messages': messages,
            'stream': stream
        }
        
        if options:
            data['options'] = options
        
        try:
            response = requests.post(
                f'{self.api_url}/chat',
                json=data,
                timeout=300
            )
            response.raise_for_status()
            
            if stream:
                return response
            
            result = response.json()
            logger.debug(f'Ollama chat response received')
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f'Ollama 请求失败: {e}')
            return {
                'error': str(e),
                'message': f'无法连接到 Ollama 服务: {self.base_url}'
            }
    
    def generate(
        self,
        model: str = 'llama3',
        prompt: str = '',
        system: str = None,
        stream: bool = False,
        options: Dict = None
    ) -> Dict:
        """
        文本生成
        
        Args:
            model: 模型名称
            prompt: 提示
            system: 系统提示
            stream: 是否流式输出
            options: 其他选项
            
        Returns:
            响应字典
        """
        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})
        
        return self.chat(model, messages, stream, options)
    
    def list_models(self) -> List[Dict]:
        """获取模型列表"""
        try:
            response = requests.get(f'{self.base_url}/api/tags', timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get('models', [])
        except Exception as e:
            logger.error(f'获取模型列表失败: {e}')
            return []
    
    def pull_model(self, model_name: str) -> bool:
        """拉取模型"""
        try:
            response = requests.post(
                f'{self.api_url}/pull',
                json={'name': model_name},
                timeout=600
            )
            response.raise_for_status()
            logger.info(f'正在拉取模型: {model_name}')
            return True
        except Exception as e:
            logger.error(f'拉取模型失败: {e}')
            return False
    
    def check_alive(self) -> bool:
        """检查 Ollama 服务是否在线"""
        try:
            response = requests.get(f'{self.base_url}/api/tags', timeout=5)
            response.raise_for_status()
            return True
        except Exception:
            return False
    
    def test_connection(self) -> Dict:
        """测试连接"""
        alive = self.check_alive()
        models = self.list_models()
        
        return {
            'alive': alive,
            'base_url': self.base_url,
            'models': [model['name'] for model in models],
            'model_count': len(models)
        }


# 全局单例
_ollama_client = None


def get_ollama_client(base_url: str = None) -> OllamaClient:
    """获取 Ollama 客户端单例"""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(base_url)
    return _ollama_client
