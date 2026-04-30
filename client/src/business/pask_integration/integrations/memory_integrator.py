"""
MemoryIntegrator - 记忆系统集成器

将 PASK 混合记忆系统与现有的 MemoryManager 集成。
"""

from typing import Dict, Any, Optional, List
from loguru import logger
import os
from pathlib import Path

from ..memory_model import HybridMemory, MemoryEntry
from client.src.business.memory_manager import MemoryManager


class MemoryIntegrator:
    """记忆系统集成器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryIntegrator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        """初始化集成器"""
        if self._initialized:
            return
        
        self._logger = logger.bind(component="MemoryIntegrator")
        self._pask_memory = HybridMemory()
        self._memory_manager = MemoryManager()
        
        # 设置默认活跃用户
        self._pask_memory.set_active_user("default")
        
        # 从现有记忆加载数据
        self._load_existing_memory()
        
        self._initialized = True
        self._logger.info("MemoryIntegrator 初始化完成")
    
    def _load_existing_memory(self):
        """从 MemoryManager 加载现有记忆"""
        try:
            # 加载长期记忆
            long_term_content = self._memory_manager.get_memory()
            if long_term_content:
                self._pask_memory.add_knowledge(long_term_content)
                self._logger.debug("已加载长期记忆")
            
            # 加载用户画像
            user_content = self._memory_manager.get_user_profile()
            if user_content:
                self._pask_memory.add_preference(user_content)
                self._logger.debug("已加载用户画像")
                
        except Exception as e:
            self._logger.warning(f"加载现有记忆失败: {e}")
    
    def sync_to_memory_manager(self):
        """同步 PASK 记忆到 MemoryManager"""
        try:
            # 获取所有用户偏好
            preferences = self._pask_memory.get_user_memory("default").get_user_preferences()
            if preferences:
                content = "\n".join([p.content for p in preferences])
                # 追加到用户画像
                self._memory_manager.append_user(content)
            
            # 获取全局知识
            knowledge_entries = self._pask_memory.global_memory._entries
            if knowledge_entries:
                content = "\n".join([k.content for k in knowledge_entries])
                # 追加到长期记忆
                self._memory_manager.append_memory(content)
            
            self._logger.debug("记忆同步完成")
            
        except Exception as e:
            self._logger.error(f"记忆同步失败: {e}")
    
    def add_context(self, content: str):
        """添加上下文（同时更新两个系统）"""
        self._pask_memory.add_context(content)
    
    def add_preference(self, content: str):
        """添加用户偏好（同时更新两个系统）"""
        self._pask_memory.add_preference(content)
        
        # 同步到 MemoryManager（使用 update_user_profile）
        try:
            self._memory_manager.update_user_profile("偏好", content)
        except Exception as e:
            self._logger.warning(f"同步偏好失败: {e}")
    
    def add_knowledge(self, content: str):
        """添加知识（同时更新两个系统）"""
        self._pask_memory.add_knowledge(content)
        
        # 同步到 MemoryManager
        try:
            self._memory_manager.append_memory(content)
        except Exception as e:
            self._logger.warning(f"同步知识失败: {e}")
    
    def search_all(self, query: str) -> List[Any]:
        """搜索所有记忆"""
        return self._pask_memory.search_all(query)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pask_stats = self._pask_memory.get_stats()
        return {
            "pask_workspace": pask_stats["workspace_entries"],
            "pask_global": pask_stats["global_entries"],
            "memory_manager": "active"
        }
    
    @classmethod
    def get_instance(cls) -> "MemoryIntegrator":
        """获取实例"""
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance