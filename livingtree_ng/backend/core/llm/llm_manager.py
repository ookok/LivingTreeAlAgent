"""
LLM 管理器 - 管理 LLM 调用和对话历史
"""
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from backend.shared.logger import get_logger
from backend.core.llm.ollama_client import get_ollama_client
from backend.infrastructure.config import get_config

logger = get_logger('llm')


@dataclass
class Conversation:
    """对话"""
    conversation_id: str
    messages: List[Dict] = field(default_factory=list)
    created_at: float = None
    updated_at: float = None
    metadata: Dict = field(default_factory=dict)


class LLMManager:
    """LLM 管理器"""
    
    def __init__(self):
        self.config = get_config()
        self.ollama = get_ollama_client(self.config.ollama.url)
        self.conversations: Dict[str, Conversation] = {}
        
        # 系统提示词
        self.default_system_prompt = """你是 LivingTreeAlAgent，一个智能 AI 助手。
你可以：
- 回答各种问题
- 进行推理和思考
- 记住之前的对话
- 帮助用户完成任务

请友好、专业地回答问题。"""
    
    def chat(
        self,
        user_message: str,
        conversation_id: str = 'default',
        system_prompt: str = None,
        model: str = None
    ) -> Dict:
        """
        对话
        
        Args:
            user_message: 用户消息
            conversation_id: 对话 ID
            system_prompt: 系统提示词
            model: 模型名称
            
        Returns:
            响应字典
        """
        model = model or self.config.ollama.default_model
        system_prompt = system_prompt or self.default_system_prompt
        
        # 获取或创建对话
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = Conversation(
                conversation_id=conversation_id,
                created_at=Path('data').stat().st_mtime
            )
        
        conv = self.conversations[conversation_id]
        
        # 添加用户消息
        conv.messages.append({
            'role': 'user',
            'content': user_message
        })
        
        # 构建请求消息
        messages = [{'role': 'system', 'content': system_prompt}]
        messages.extend(conv.messages[-10:])  # 限制历史长度
        
        # 调用 Ollama
        try:
            logger.debug(f'调用模型: {model}')
            result = self.ollama.chat(model=model, messages=messages)
            
            if 'error' in result:
                return {
                    'error': result['error'],
                    'success': False
                }
            
            # 获取响应
            if 'message' in result:
                assistant_message = result['message']['content']
            else:
                assistant_message = str(result)
            
            # 保存响应
            conv.messages.append({
                'role': 'assistant',
                'content': assistant_message
            })
            
            return {
                'success': True,
                'response': assistant_message,
                'model': model,
                'conversation_id': conversation_id
            }
            
        except Exception as e:
            logger.error(f'LLM 调用失败: {e}')
            return {
                'success': False,
                'error': str(e),
                'response': '抱歉，调用 LLM 时出错了。'
            }
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取对话"""
        return self.conversations.get(conversation_id)
    
    def clear_conversation(self, conversation_id: str):
        """清空对话"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id].messages = []
    
    def list_models(self) -> List[Dict]:
        """获取可用模型"""
        return self.ollama.list_models()
    
    def check_connection(self) -> Dict:
        """检查连接"""
        return self.ollama.test_connection()


# 全局单例
_llm_manager = None


def get_llm_manager() -> LLMManager:
    """获取 LLM 管理器单例"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
