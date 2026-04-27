"""
ToolRegistry - 工具注册中心（单例模式）
所有工具通过此类注册和调用

增强功能（P2-6）：
- discover(): 语义搜索工具（向量检索）
- 自动生成工具描述的向量嵌入
- 支持混合搜索（关键字 + 语义）
"""

from typing import Any, Dict, List, Optional, Type, Callable, Tuple
from loguru import logger
import threading
import sqlite3
import json
import numpy as np  # 需要：pip install numpy
from pathlib import Path

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_definition import ToolDefinition
from client.src.business.tools.tool_result import ToolResult


class ToolRegistry:
    """
    工具注册中心（单例模式）
    
    职责：
    - 工具注册/注销
    - 工具查找/搜索
    - 工具执行
    - 工具生命周期管理
    
    用法：
        registry = ToolRegistry.get_instance()
        registry.register_tool(my_tool)
        result = registry.execute_tool("my_tool", param1="value1")
    """
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """初始化注册中心"""
        if ToolRegistry._instance is not None:
            raise RuntimeError("ToolRegistry 是单例类，请使用 ToolRegistry.get_instance() 获取实例")
        
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, List[str]] = {}  # category -> [tool_names]
        self._tags: Dict[str, List[str]] = {}       # tag -> [tool_names]
        self._logger = logger.bind(component="ToolRegistry")
        
        # P2-6: 语义搜索支持
        self._embeddings: Dict[str, List[float]] = {}  # tool_name -> embedding vector
        self._embedding_model: str = "nomic-embed-text"  # Ollama 嵌入模型
        self._ollama_url: str = "http://localhost:11434"
        self._enable_semantic_search: bool = True
        
        # 嵌入向量持久化（SQLite）
        self._embedding_db_path: Path = Path.home() / ".livingtree" / "tool_embeddings.db"
        self._init_embedding_db()
        self._load_embeddings_from_db()
        
        self._logger.info("ToolRegistry 初始化完成（语义搜索已启用）")
    
    def register_tool(
        self, 
        tool: Optional[BaseTool] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        handler: Optional[Callable] = None,
        **kwargs
    ) -> bool:
        """
        注册工具（支持两种用法）
        
        用法 1（推荐）：
            registry.register_tool(my_tool)
        
        用法 2（快速注册函数）：
            registry.register_tool(
                name="my_tool",
                description="我的工具",
                handler=my_function
            )
        
        Returns:
            是否注册成功
        """
        # 用法 2：快速注册函数
        if tool is None and name is not None and handler is not None:
            from client.src.business.tools.tool_definition import ToolDefinition
            
            definition = ToolDefinition(
                name=name,
                description=description or "",
                handler=handler,
                **kwargs
            )
            
            # 创建匿名工具类
            class AnonymousTool(BaseTool):
                def execute(self, *args, **kwargs) -> ToolResult:
                    try:
                        result = handler(*args, **kwargs)
                        return ToolResult(success=True, data=result)
                    except Exception as e:
                        return ToolResult(success=False, error=str(e))
            
            tool = AnonymousTool(name, description or "")
            tool._definition = definition
        
        # 用法 1：注册工具实例
        if not isinstance(tool, BaseTool):
            self._logger.error(f"注册失败：{tool} 不是 BaseTool 的实例")
            return False
        
        if tool.name in self._tools:
            self._logger.warning(f"工具 {tool.name} 已存在，将覆盖")
        
        # 注册工具
        self._tools[tool.name] = tool
        
        # 更新分类索引
        category = tool.definition.category
        if category not in self._categories:
            self._categories[category] = []
        if tool.name not in self._categories[category]:
            self._categories[category].append(tool.name)
        
        # 更新标签索引
        for tag in tool.definition.tags:
            if tag not in self._tags:
                self._tags[tag] = []
            if tool.name not in self._tags[tag]:
                self._tags[tag].append(tool.name)
        
        # P2-6: 自动生成工具嵌入向量
        if self._enable_semantic_search:
            self._generate_tool_embedding(tool)
        
        self._logger.info(f"工具已注册: {tool.name} (分类: {category})")
        return True
    
    def unregister_tool(self, name: str) -> bool:
        """
        注销工具
        
        Args:
            name: 工具名称
            
        Returns:
            是否注销成功
        """
        if name not in self._tools:
            self._logger.warning(f"工具 {name} 不存在，无法注销")
            return False
        
        tool = self._tools[name]
        
        # 从分类索引中移除
        category = tool.definition.category
        if category in self._categories:
            self._categories[category] = [t for t in self._categories[category] if t != name]
        
        # 从标签索引中移除
        for tag in tool.definition.tags:
            if tag in self._tags:
                self._tags[tag] = [t for t in self._tags[tag] if t != name]
        
        # 注销工具
        del self._tools[name]
        
        self._logger.info(f"工具已注销: {name}")
        return True
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            工具实例，不存在则返回 None
        """
        tool = self._tools.get(name)
        if tool is None:
            self._logger.warning(f"工具 {name} 不存在")
            return None
        
        if not tool.definition.is_enabled:
            self._logger.warning(f"工具 {name} 已被禁用")
            return None
        
        return tool
    
    def execute_tool(self, name: str, *args, **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            name: 工具名称
            *args, **kwargs: 传递给工具的参数
            
        Returns:
            ToolResult 对象
        """
        tool = self.get_tool(name)
        if tool is None:
            return ToolResult(success=False, error=f"工具 {name} 不存在或已被禁用")
        
        try:
            self._logger.info(f"执行工具: {name}, 参数: {kwargs}")
            result = tool(*args, **kwargs)
            
            if not isinstance(result, ToolResult):
                # 如果工具返回的不是 ToolResult，自动包装
                result = ToolResult(success=True, data=result)
            
            return result
        
        except Exception as e:
            self._logger.exception(f"执行工具 {name} 时发生异常")
            return ToolResult(success=False, error=str(e))
    
    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        """
        列出所有工具
        
        Args:
            category: 可选，按分类过滤
            
        Returns:
            工具定义列表
        """
        if category:
            tool_names = self._categories.get(category, [])
            return [self._tools[name].definition for name in tool_names if name in self._tools]
        
        return [tool.definition for tool in self._tools.values()]
    
    def search_tools(self, query: str) -> List[ToolDefinition]:
        """
        搜索工具（按名称、描述、标签）
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的工具定义列表
        """
        query = query.lower()
        results = []
        
        for tool in self._tools.values():
            definition = tool.definition
            
            # 搜索名称
            if query in definition.name.lower():
                results.append(definition)
                continue
            
            # 搜索描述
            if query in definition.description.lower():
                results.append(definition)
                continue
            
            # 搜索标签
            if any(query in tag.lower() for tag in definition.tags):
                results.append(definition)
                continue
        
        return results
    
    def enable_tool(self, name: str) -> bool:
        """启用工具"""
        if name not in self._tools:
            return False
        self._tools[name].definition.is_enabled = True
        self._logger.info(f"工具已启用: {name}")
        return True
    
    def disable_tool(self, name: str) -> bool:
        """禁用工具"""
        if name not in self._tools:
            return False
        self._tools[name].definition.is_enabled = False
        self._logger.info(f"工具已禁用: {name}")
        return True
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._categories.keys())
    
    def get_tools_by_tag(self, tag: str) -> List[ToolDefinition]:
        """按标签获取工具"""
        tool_names = self._tags.get(tag, [])
        return [self._tools[name].definition for name in tool_names if name in self._tools]
    
    def clear(self):
        """清空所有工具（用于测试）"""
        self._tools.clear()
        self._categories.clear()
        self._tags.clear()
        self._logger.info("已清空所有工具")
    
    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tools": len(self._tools),
            "categories": {k: len(v) for k, v in self._categories.items()},
            "enabled": sum(1 for t in self._tools.values() if t.definition.is_enabled),
            "disabled": sum(1 for t in self._tools.values() if not t.definition.is_enabled),
            "semantic_search": {
                "enabled": self._enable_semantic_search,
                "embeddings_count": len(self._embeddings),
                "embedding_model": self._embedding_model
            }
        }
    
    # ============================================================
    # P2-6: 语义搜索增强
    # ============================================================
    
    def _init_embedding_db(self):
        """初始化嵌入向量数据库"""
        try:
            self._embedding_db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._embedding_db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_embeddings (
                    tool_name TEXT PRIMARY KEY,
                    embedding TEXT NOT NULL,  -- JSON array
                    model TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
            self._logger.info(f"嵌入数据库初始化完成: {self._embedding_db_path}")
        except Exception as e:
            self._logger.error(f"初始化嵌入数据库失败: {e}")
            self._enable_semantic_search = False
    
    def _load_embeddings_from_db(self):
        """从数据库加载已存在的嵌入向量"""
        if not self._embedding_db_path.exists():
            return
        
        try:
            conn = sqlite3.connect(str(self._embedding_db_path))
            rows = conn.execute("SELECT tool_name, embedding FROM tool_embeddings").fetchall()
            for row in rows:
                tool_name = row[0]
                embedding = json.loads(row[1])
                self._embeddings[tool_name] = embedding
            conn.close()
            self._logger.info(f"从数据库加载了 {len(rows)} 个工具嵌入向量")
        except Exception as e:
            self._logger.error(f"加载嵌入向量失败: {e}")
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取文本的嵌入向量（调用 Ollama API）
        
        Args:
            text: 输入文本（工具名称+描述）
        
        Returns:
            嵌入向量（768维），失败返回 None
        """
        try:
            import requests
            
            response = requests.post(
                f"{self._ollama_url}/api/embeddings",
                json={
                    "model": self._embedding_model,
                    "prompt": text
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                embedding = data.get("embedding", [])
                if embedding:
                    return embedding
            else:
                self._logger.warning(f"Ollama 嵌入 API 返回 {response.status_code}")
                return None
        except Exception as e:
            self._logger.error(f"获取嵌入向量失败: {e}")
            return None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
        
        Returns:
            相似度 [0, 1]，越大越相似
        """
        try:
            import numpy as np
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(dot_product / (norm1 * norm2))
        except Exception:
            # 如果 numpy 不可用，使用纯 Python 实现
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot_product / (norm1 * norm2)
    
    def _generate_tool_embedding(self, tool: BaseTool):
        """
        为工具生成嵌入向量（异步，不阻塞注册）
        
        Args:
            tool: 工具实例
        """
        if not self._enable_semantic_search:
            return
        
        definition = tool.definition
        # 组合工具名称、描述、标签作为嵌入文本
        text = f"{definition.name} {definition.description} {' '.join(definition.tags)}"
        
        embedding = self._get_embedding(text)
        if embedding:
            self._embeddings[definition.name] = embedding
            
            # 持久化到数据库
            try:
                conn = sqlite3.connect(str(self._embedding_db_path))
                conn.execute("""
                    INSERT OR REPLACE INTO tool_embeddings
                    (tool_name, embedding, model) VALUES (?, ?, ?)
                """, (definition.name, json.dumps(embedding), self._embedding_model))
                conn.commit()
                conn.close()
            except Exception as e:
                self._logger.error(f"保存嵌入向量失败: {e}")
            
            self._logger.debug(f"生成工具嵌入向量: {definition.name}")
    
    def discover(self, query: str, top_k: int = 5,
                use_semantic: bool = True) -> List[Tuple[ToolDefinition, float]]:
        """
        语义搜索工具（增强版 search_tools）
        
        Args:
            query: 搜索查询
            top_k: 返回最相关的 top_k 个工具
            use_semantic: 是否使用语义搜索（False 则退化为关键字搜索）
        
        Returns:
            List of (ToolDefinition, score), 按相似度降序排列
        """
        if not use_semantic or not self._enable_semantic_search:
            # 退化为关键字搜索
            results = []
            query_lower = query.lower()
            for tool in self._tools.values():
                definition = tool.definition
                score = 0.0
                
                if query_lower in definition.name.lower():
                    score = 1.0
                elif query_lower in definition.description.lower():
                    score = 0.8
                elif any(query_lower in tag.lower() for tag in definition.tags):
                    score = 0.6
                
                if score > 0:
                    results.append((definition, score))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        
        # 语义搜索
        query_embedding = self._get_embedding(query)
        if not query_embedding:
            self._logger.warning("无法生成查询嵌入向量，退化为关键字搜索")
            return self.discover(query, top_k, use_semantic=False)
        
        # 计算相似度
        results = []
        for tool in self._tools.values():
            definition = tool.definition
            tool_name = definition.name
            
            if tool_name not in self._embeddings:
                # 异步生成嵌入（这里简化，直接生成）
                self._generate_tool_embedding(tool)
                if tool_name not in self._embeddings:
                    continue  # 跳过无法生成嵌入的工具
            
            similarity = self._cosine_similarity(
                query_embedding,
                self._embeddings[tool_name]
            )
            
            if similarity > 0.3:  # 相似度阈值
                results.append((definition, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def enable_semantic_search(self, enable: bool = True,
                              embedding_model: Optional[str] = None,
                              ollama_url: Optional[str] = None):
        """
        启用/禁用语义搜索
        
        Args:
            enable: 是否启用
            embedding_model: 嵌入模型名称（如 "nomic-embed-text"）
            ollama_url: Ollama API 地址
        """
        self._enable_semantic_search = enable
        if embedding_model:
            self._embedding_model = embedding_model
        if ollama_url:
            self._ollama_url = ollama_url
        
        self._logger.info(f"语义搜索已{'启用' if enable else '禁用'}, 模型: {self._embedding_model}")
        
        # 如果启用，预生成所有工具的嵌入
        if enable:
            for tool in self._tools.values():
                if tool.definition.name not in self._embeddings:
                    self._generate_tool_embedding(tool)

