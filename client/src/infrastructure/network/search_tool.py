# =================================================================
# AISearchTool - AI搜索工具
# =================================================================

from typing import Optional, Dict, Any, List


class AISearchTool:
    """AI搜索工具（占位）"""

    def __init__(self, serper_key: str = None, **kwargs):
        self.serper_key = serper_key
        self._llm_client = None
        self._model = None

    def set_llm_client(self, llm_client, model: str = None):
        """设置 LLM 客户端"""
        self._llm_client = llm_client
        self._model = model

    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """搜索"""
        return []


__all__ = ['AISearchTool']