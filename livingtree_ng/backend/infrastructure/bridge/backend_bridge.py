"""
LivingTree NG - 前后端桥接层 - WebChannel通信
集成配置、模型管理、会话、记忆等功能
支持多种LLM提供商（DeepSeek、阿里云、腾讯云、MiniMax、GLM、Kimi等）
"""

import json
import logging
from typing import Dict, Any
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

from backend.shared.logger import get_logger
from backend.infrastructure.config import config
from backend.core.llm.ollama_simple import get_ollama_client, ChatMessage
from backend.core.session.manager import get_session_manager
from backend.core.llm.model_manager import get_model_manager
from backend.core.memory.simple_memory import get_memory_manager
from backend.infrastructure.config.llm_config import llm_config_manager
from backend.infrastructure.llm.multi_provider_client import llm_client

logger = get_logger('bridge')


class BackendBridge(QObject):
    """后端桥接 - 暴露给JavaScript的API"""
    
    # 信号：后端→前端
    eventReceived = pyqtSignal(str)  # JSON事件
    
    def __init__(self):
        super().__init__()
        
        # 初始化核心系统
        self.ollama = get_ollama_client()
        self.sessions = get_session_manager()
        self.models = get_model_manager(config)
        self.memory = get_memory_manager(config)
        
        logger.info('BackendBridge initialized')
    
    # =========================================================================
    # 暴露给前端的API
    # =========================================================================
    
    @pyqtSlot(str, result=str)
    def ping(self, message: str) -> str:
        """测试连接"""
        return json.dumps({
            'status': 'ok',
            'message': f'Pong: {message}',
            'version': '2.1.0'
        })
    
    @pyqtSlot(result=str)
    def getConfig(self) -> str:
        """获取当前配置"""
        try:
            return json.dumps({
                'status': 'ok',
                'config': config.to_dict()
            })
        except Exception as e:
            logger.error(f"Get config error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    # ========================================
    # LLM提供商管理API
    # ========================================
    
    @pyqtSlot(result=str)
    def listProviders(self) -> str:
        """获取所有LLM提供商列表"""
        try:
            providers = llm_config_manager.list_providers()
            return json.dumps({
                'status': 'ok',
                'providers': providers,
                'current_provider': llm_config_manager.config.current_provider,
                'current_model': llm_config_manager.config.current_model
            })
        except Exception as e:
            logger.error(f"List providers error: {e}")
            return json.dumps({'status': 'error', 'error': str(e), 'providers': []})
    
    @pyqtSlot(str, result=str)
    def setCurrentProvider(self, provider_name: str) -> str:
        """设置当前LLM提供商"""
        try:
            llm_config_manager.set_current_provider(provider_name)
            return json.dumps({
                'status': 'ok',
                'provider': provider_name,
                'model': llm_config_manager.config.current_model
            })
        except Exception as e:
            logger.error(f"Set provider error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    @pyqtSlot(str, str, result=str)
    def setProviderApiKey(self, provider_name: str, api_key: str) -> str:
        """设置提供商的API密钥（加密保存）"""
        try:
            llm_config_manager.set_provider_api_key(provider_name, api_key)
            return json.dumps({'status': 'ok'})
        except Exception as e:
            logger.error(f"Set API key error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    @pyqtSlot(str, str, result=str)
    def setProviderBaseUrl(self, provider_name: str, base_url: str) -> str:
        """设置提供商的API地址"""
        try:
            provider = llm_config_manager.config.get_provider(provider_name)
            if provider:
                provider.base_url = base_url
                llm_config_manager.save_config()
                return json.dumps({'status': 'ok'})
            else:
                return json.dumps({'status': 'error', 'error': 'Provider not found'})
        except Exception as e:
            logger.error(f"Set base URL error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    @pyqtSlot(str, result=str)
    def getProviderModels(self, provider_name: str) -> str:
        """获取提供商的模型列表"""
        try:
            provider = llm_config_manager.config.get_provider(provider_name)
            if provider:
                return json.dumps({
                    'status': 'ok',
                    'models': provider.models,
                    'thinking_mode': provider.thinking_mode
                })
            else:
                return json.dumps({'status': 'error', 'error': 'Provider not found'})
        except Exception as e:
            logger.error(f"Get provider models error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    # ========================================
    # 会话管理API
    # ========================================
    
    @pyqtSlot(str, result=str)
    def createSession(self, name: str) -> str:
        """创建会话"""
        try:
            session = self.sessions.create_session(name)
            return json.dumps({
                'status': 'ok', 
                'session_id': session.id,
                'title': session.title
            })
        except Exception as e:
            logger.error(f"Create session error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    @pyqtSlot(result=str)
    def listSessions(self) -> str:
        """获取会话列表"""
        try:
            sessions = self.sessions.list_sessions()
            return json.dumps({
                'status': 'ok', 
                'sessions': [
                    {
                        'id': s.id,
                        'title': s.title,
                        'created_at': s.created_at,
                        'updated_at': s.updated_at
                    } for s in sessions
                ]
            })
        except Exception as e:
            logger.error(f"List sessions error: {e}")
            return json.dumps({'status': 'error', 'error': str(e), 'sessions': []})
    
    @pyqtSlot(str, result=str)
    def getSession(self, session_id: str) -> str:
        """获取单个会话"""
        try:
            session = self.sessions.get_session(session_id)
            if session is None:
                return json.dumps({'status': 'error', 'error': 'Session not found'})
            
            messages = self.sessions.get_messages(session_id)
            
            return json.dumps({
                'status': 'ok', 
                'session': {
                    'id': session.id,
                    'title': session.title
                },
                'messages': [
                    {'role': m.role, 'content': m.content, 'timestamp': m.timestamp} 
                    for m in messages
                ]
            })
        except Exception as e:
            logger.error(f"Get session error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    @pyqtSlot(str, result=str)
    def deleteSession(self, session_id: str) -> str:
        """删除会话"""
        try:
            self.sessions.delete_session(session_id)
            self.memory.clear_session(session_id)
            return json.dumps({'status': 'ok'})
        except Exception as e:
            logger.error(f"Delete session error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    # ========================================
    # 模型管理API
    # ========================================
    
    @pyqtSlot(result=str)
    def listModels(self) -> str:
        """获取可用模型列表（包括当前提供商的模型）"""
        try:
            models = self.models.get_available_models()
            current_model = self.models.get_current_model()
            
            provider_models = llm_client.list_models()
            
            return json.dumps({
                'status': 'ok',
                'models': [
                    {
                        'name': m.name,
                        'available': m.available,
                        'description': m.description,
                        'backend': m.backend
                    } for m in models
                ] + provider_models,
                'current_model': current_model,
                'provider_models': provider_models
            })
        except Exception as e:
            logger.error(f"List models error: {e}")
            return json.dumps({'status': 'error', 'error': str(e), 'models': []})
    
    @pyqtSlot(str, result=str)
    def setCurrentModel(self, model_name: str) -> str:
        """设置当前模型"""
        try:
            llm_config_manager.set_current_model(model_name)
            self.models.set_current_model(model_name)
            return json.dumps({'status': 'ok'})
        except Exception as e:
            logger.error(f"Set model error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    @pyqtSlot(result=str)
    def getCurrentModel(self) -> str:
        """获取当前模型"""
        try:
            model_name = llm_config_manager.config.current_model
            return json.dumps({
                'status': 'ok',
                'model': model_name,
                'provider': llm_config_manager.config.current_provider
            })
        except Exception as e:
            logger.error(f"Get model error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    # ========================================
    # LLM聊天API
    # ========================================
    
    @pyqtSlot(str, str, result=str)
    def llmChatSync(self, session_id: str, user_content: str) -> str:
        """
        同步聊天（存数据库）
        
        Args:
            session_id: 会话ID
            user_content: 用户消息
            
        Returns:
            JSON响应
        """
        try:
            logger.info(f'Chat [{session_id}]: {user_content[:50]}...')
            
            provider = llm_config_manager.config.get_current_provider()
            model_name = llm_config_manager.config.current_model
            
            self.sessions.add_message(session_id, "user", user_content)
            
            self.memory.add_memory(
                content=f"用户: {user_content}",
                memory_type="chat",
                session_id=session_id,
                metadata={"role": "user"}
            )
            
            msgs = self.sessions.get_messages(session_id)
            history = [ChatMessage(role=m.role, content=m.content) for m in msgs]
            
            if provider and provider.api_key:
                try:
                    response = llm_client.chat_sync(history, model_name)
                except Exception as e:
                    logger.error(f"LLM call error: {e}")
                    response = f"抱歉，LLM调用失败：{str(e)}"
            elif self.ollama.ping():
                try:
                    response = self.ollama.chat_sync(history, model=model_name)
                except Exception as e:
                    logger.error(f"Ollama call error: {e}")
                    response = f"抱歉，Ollama调用失败：{str(e)}"
            else:
                response = f"演示回复 (模型: {model_name})，内容：{user_content}"
            
            self.sessions.add_message(session_id, "assistant", response)
            
            self.memory.add_memory(
                content=f"助手: {response}",
                memory_type="chat",
                session_id=session_id,
                metadata={"role": "assistant"}
            )
            
            return json.dumps({
                'status': 'ok', 
                'response': response,
                'model': model_name,
                'provider': provider.display_name if provider else 'Ollama'
            })
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return json.dumps({
                'status': 'error', 
                'error': str(e), 
                'response': '抱歉，出错了！'
            })
    
    @pyqtSlot(result=str)
    def llmCheckConnection(self) -> str:
        """检查LLM连接"""
        try:
            provider = llm_config_manager.config.get_current_provider()
            
            if provider and provider.api_key:
                result = llm_client.check_connection()
            else:
                alive = self.ollama.ping()
                version = self.ollama.get_version()
                result = {'alive': alive, 'version': version, 'provider': 'Ollama'}
            
            return json.dumps({
                'status': 'ok', 
                'result': result
            })
        except Exception as e:
            logger.error(f"Check connection error: {e}")
            return json.dumps({
                'status': 'error', 
                'error': str(e), 
                'result': {'alive': False}
            })
    
    @pyqtSlot(str, result=str)
    def setOllamaUrl(self, url: str) -> str:
        """设置Ollama URL"""
        try:
            self.ollama.base_url = url.rstrip("/")
            config.ollama.url = url.rstrip("/")
            return json.dumps({'status': 'ok'})
        except Exception as e:
            logger.error(f"Set URL error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    # ========================================
    # 记忆API
    # ========================================
    
    @pyqtSlot(str, str, str, result=str)
    def addMemory(self, content: str, memory_type: str = "text", 
                  session_id: str = "") -> str:
        """添加记忆"""
        try:
            memory_id = self.memory.add_memory(
                content=content,
                memory_type=memory_type,
                session_id=session_id if session_id else None
            )
            return json.dumps({
                'status': 'ok',
                'memory_id': memory_id
            })
        except Exception as e:
            logger.error(f"Add memory error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    @pyqtSlot(str, str, int, result=str)
    def searchMemory(self, query: str, session_id: str = "", 
                     limit: int = 10) -> str:
        """搜索记忆"""
        try:
            results = self.memory.search_memories(
                query=query,
                session_id=session_id if session_id else None,
                limit=limit
            )
            return json.dumps({
                'status': 'ok',
                'results': results
            })
        except Exception as e:
            logger.error(f"Search memory error: {e}")
            return json.dumps({'status': 'error', 'error': str(e), 'results': []})
    
    @pyqtSlot(str, int, result=str)
    def getSessionHistory(self, session_id: str, limit: int = 50) -> str:
        """获取会话历史"""
        try:
            history = self.memory.get_session_history(session_id, limit)
            return json.dumps({
                'status': 'ok',
                'history': history
            })
        except Exception as e:
            logger.error(f"Get history error: {e}")
            return json.dumps({'status': 'error', 'error': str(e), 'history': []})
    
    @pyqtSlot(result=str)
    def getMemoryStats(self) -> str:
        """获取记忆统计"""
        try:
            stats = self.memory.get_stats()
            return json.dumps({
                'status': 'ok',
                'stats': stats
            })
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    @pyqtSlot(str, result=str)
    def deleteMemory(self, memory_id: str) -> str:
        """删除记忆"""
        try:
            deleted = self.memory.delete_memory(memory_id)
            return json.dumps({
                'status': 'ok',
                'deleted': deleted
            })
        except Exception as e:
            logger.error(f"Delete memory error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
    
    # ========================================
    # 系统API
    # ========================================
    
    @pyqtSlot(result=str)
    def getSystemInfo(self) -> str:
        """获取系统信息"""
        try:
            import platform
            import sys
            
            return json.dumps({
                'status': 'ok',
                'info': {
                    'version': '2.1.0',
                    'platform': platform.system(),
                    'python_version': sys.version,
                    'config': config.to_dict()
                }
            })
        except Exception as e:
            logger.error(f"Get system info error: {e}")
            return json.dumps({'status': 'error', 'error': str(e)})
