"""
向量数据库集成模块 - 存储工具、技能、专家角色

功能：
1. 将工具、技能、专家角色等元数据存储到向量数据库
2. 根据用户输入进行语义检索，找到相关的工具/技能
3. 为LLM提供上下文信息，帮助决定调用哪个工具
4. 支持增量更新和批量导入

设计目标：
- 简洁易用的API接口
- 支持多种向量数据库后端（Chroma、Pinecone、Weaviate等）
- 提供统一的检索接口
"""

import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class VectorDBType(Enum):
    """向量数据库类型"""
    CHROMA = "chroma"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    FAISS = "faiss"


class ItemType(Enum):
    """存储项目类型"""
    TOOL = "tool"
    SKILL = "skill"
    EXPERT = "expert"
    DOCUMENT = "document"
    KNOWLEDGE = "knowledge"


@dataclass
class VectorItem:
    """向量存储项"""
    id: str
    type: ItemType
    name: str
    description: str
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "metadata": self.metadata,
            "embedding": self.embedding
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VectorItem':
        return cls(
            id=data["id"],
            type=ItemType(data.get("type", "tool")),
            name=data["name"],
            description=data["description"],
            keywords=data.get("keywords", []),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding")
        )


class VectorDBIntegration:
    """
    向量数据库集成类
    
    提供统一的向量存储和检索接口，支持多种后端。
    """
    
    def __init__(self, db_type: VectorDBType = VectorDBType.CHROMA, **kwargs):
        """
        初始化向量数据库
        
        Args:
            db_type: 数据库类型
            kwargs: 数据库连接参数
        """
        self._logger = logger.bind(component="VectorDBIntegration")
        self._db_type = db_type
        self._client = None
        self._collection = None
        self._init_client(**kwargs)
    
    def _init_client(self, **kwargs):
        """初始化数据库客户端"""
        if self._db_type == VectorDBType.CHROMA:
            self._init_chroma(**kwargs)
        else:
            self._logger.warning(f"未支持的数据库类型: {self._db_type}")
    
    def _init_chroma(self, **kwargs):
        """初始化Chroma数据库"""
        if not CHROMADB_AVAILABLE:
            self._logger.error("Chroma DB不可用，请安装: pip install chromadb")
            return
        
        try:
            persist_directory = kwargs.get("persist_directory", "./vector_db")
            
            self._client = chromadb.Client(Settings(
                persist_directory=persist_directory,
                anonymized_telemetry=False
            ))
            
            # 创建或获取集合
            self._collection = self._client.get_or_create_collection(
                name=kwargs.get("collection_name", "livingtree_agents"),
                metadata={"hnsw:space": "cosine"}
            )
            
            self._logger.info(f"Chroma DB初始化成功: {persist_directory}")
        except Exception as e:
            self._logger.error(f"Chroma DB初始化失败: {e}")
    
    def add_item(self, item: VectorItem):
        """添加单个项目到向量数据库"""
        if not self._collection:
            self._logger.warning("数据库未初始化")
            return
        
        try:
            # 创建文档内容
            document = self._build_document(item)
            
            # 添加到数据库
            self._collection.add(
                ids=[item.id],
                documents=[document],
                metadatas=[{
                    "type": item.type.value,
                    "name": item.name,
                    "keywords": json.dumps(item.keywords),
                    "metadata": json.dumps(item.metadata)
                }],
                embeddings=[item.embedding] if item.embedding else None
            )
            
            self._logger.debug(f"添加项目成功: {item.id}")
        except Exception as e:
            self._logger.error(f"添加项目失败: {e}")
    
    def add_items(self, items: List[VectorItem]):
        """批量添加项目"""
        if not self._collection or not items:
            return
        
        try:
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            for item in items:
                ids.append(item.id)
                documents.append(self._build_document(item))
                metadatas.append({
                    "type": item.type.value,
                    "name": item.name,
                    "keywords": json.dumps(item.keywords),
                    "metadata": json.dumps(item.metadata)
                })
                if item.embedding:
                    embeddings.append(item.embedding)
            
            self._collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings if embeddings else None
            )
            
            self._logger.info(f"批量添加成功: {len(items)} 个项目")
        except Exception as e:
            self._logger.error(f"批量添加失败: {e}")
    
    def _build_document(self, item: VectorItem) -> str:
        """构建用于向量化的文档内容"""
        parts = [
            f"类型: {item.type.value}",
            f"名称: {item.name}",
            f"描述: {item.description}"
        ]
        
        if item.keywords:
            parts.append(f"关键词: {', '.join(item.keywords)}")
        
        if item.metadata:
            parts.append(f"元数据: {json.dumps(item.metadata, ensure_ascii=False)}")
        
        return "\n".join(parts)
    
    def search(self, query: str, top_k: int = 5, item_types: Optional[List[ItemType]] = None) -> List[VectorItem]:
        """
        搜索相关项目
        
        Args:
            query: 查询文本
            top_k: 返回数量
            item_types: 过滤类型列表
            
        Returns:
            匹配的项目列表
        """
        if not self._collection:
            return []
        
        try:
            # 构建过滤条件
            where = None
            if item_types:
                where = {
                    "type": {
                        "$in": [t.value for t in item_types]
                    }
                }
            
            # 执行搜索
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where
            )
            
            # 转换结果
            items = []
            for i, id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i]
                items.append(VectorItem(
                    id=id,
                    type=ItemType(metadata.get("type", "tool")),
                    name=metadata.get("name", ""),
                    description=results["documents"][0][i],
                    keywords=json.loads(metadata.get("keywords", "[]")),
                    metadata=json.loads(metadata.get("metadata", "{}"))
                ))
            
            return items
        
        except Exception as e:
            self._logger.error(f"搜索失败: {e}")
            return []
    
    def get_item(self, item_id: str) -> Optional[VectorItem]:
        """获取单个项目"""
        if not self._collection:
            return None
        
        try:
            results = self._collection.get(ids=[item_id])
            
            if results["ids"]:
                metadata = results["metadatas"][0]
                return VectorItem(
                    id=results["ids"][0],
                    type=ItemType(metadata.get("type", "tool")),
                    name=metadata.get("name", ""),
                    description=results["documents"][0],
                    keywords=json.loads(metadata.get("keywords", "[]")),
                    metadata=json.loads(metadata.get("metadata", "{}"))
                )
            
            return None
        
        except Exception as e:
            self._logger.error(f"获取项目失败: {e}")
            return None
    
    def delete_item(self, item_id: str):
        """删除项目"""
        if not self._collection:
            return
        
        try:
            self._collection.delete(ids=[item_id])
            self._logger.debug(f"删除项目成功: {item_id}")
        except Exception as e:
            self._logger.error(f"删除项目失败: {e}")
    
    def update_item(self, item: VectorItem):
        """更新项目"""
        if not self._collection:
            return
        
        try:
            document = self._build_document(item)
            
            self._collection.update(
                ids=[item.id],
                documents=[document],
                metadatas=[{
                    "type": item.type.value,
                    "name": item.name,
                    "keywords": json.dumps(item.keywords),
                    "metadata": json.dumps(item.metadata)
                }],
                embeddings=[item.embedding] if item.embedding else None
            )
            
            self._logger.debug(f"更新项目成功: {item.id}")
        except Exception as e:
            self._logger.error(f"更新项目失败: {e}")
    
    def list_items(self, item_type: Optional[ItemType] = None) -> List[VectorItem]:
        """列出所有项目"""
        if not self._collection:
            return []
        
        try:
            where = None
            if item_type:
                where = {"type": item_type.value}
            
            results = self._collection.get(where=where)
            
            items = []
            for i, id in enumerate(results["ids"]):
                metadata = results["metadatas"][i]
                items.append(VectorItem(
                    id=id,
                    type=ItemType(metadata.get("type", "tool")),
                    name=metadata.get("name", ""),
                    description=results["documents"][i],
                    keywords=json.loads(metadata.get("keywords", "[]")),
                    metadata=json.loads(metadata.get("metadata", "{}"))
                ))
            
            return items
        
        except Exception as e:
            self._logger.error(f"列出项目失败: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        if not self._collection:
            return {}
        
        try:
            count = self._collection.count()
            return {"total_items": count}
        except Exception as e:
            self._logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def clear_all(self):
        """清空所有数据"""
        if not self._collection:
            return
        
        try:
            self._collection.delete(ids=self._collection.get()["ids"])
            self._logger.info("清空所有数据")
        except Exception as e:
            self._logger.error(f"清空数据失败: {e}")


class ToolRegistry:
    """
    工具注册器 - 管理工具、技能、专家角色
    
    提供简洁的API接口，便于向LLM输送工具信息。
    """
    
    def __init__(self, db_path: str = "./vector_db"):
        self._vector_db = VectorDBIntegration(
            VectorDBType.CHROMA,
            persist_directory=db_path,
            collection_name="tools_and_skills"
        )
    
    def register_tool(self, name: str, description: str, keywords: List[str] = None, **metadata):
        """
        注册工具
        
        Args:
            name: 工具名称
            description: 工具描述
            keywords: 关键词列表
            metadata: 其他元数据（如参数、返回值等）
        """
        item = VectorItem(
            id=self._generate_id("tool", name),
            type=ItemType.TOOL,
            name=name,
            description=description,
            keywords=keywords or [],
            metadata=metadata
        )
        self._vector_db.add_item(item)
    
    def register_skill(self, name: str, description: str, keywords: List[str] = None, **metadata):
        """
        注册技能
        
        Args:
            name: 技能名称
            description: 技能描述
            keywords: 关键词列表
            metadata: 其他元数据
        """
        item = VectorItem(
            id=self._generate_id("skill", name),
            type=ItemType.SKILL,
            name=name,
            description=description,
            keywords=keywords or [],
            metadata=metadata
        )
        self._vector_db.add_item(item)
    
    def register_expert(self, name: str, description: str, keywords: List[str] = None, **metadata):
        """
        注册专家角色
        
        Args:
            name: 专家名称
            description: 专家描述
            keywords: 关键词列表
            metadata: 其他元数据（如专长领域等）
        """
        item = VectorItem(
            id=self._generate_id("expert", name),
            type=ItemType.EXPERT,
            name=name,
            description=description,
            keywords=keywords or [],
            metadata=metadata
        )
        self._vector_db.add_item(item)
    
    def _generate_id(self, type_name: str, name: str) -> str:
        """生成唯一ID"""
        return hashlib.md5(f"{type_name}:{name}".encode()).hexdigest()
    
    def recommend_tools(self, query: str, top_k: int = 3) -> List[VectorItem]:
        """
        根据用户查询推荐工具
        
        Args:
            query: 用户输入文本
            top_k: 返回数量
            
        Returns:
            推荐的工具列表
        """
        return self._vector_db.search(query, top_k, [ItemType.TOOL])
    
    def recommend_skills(self, query: str, top_k: int = 3) -> List[VectorItem]:
        """根据用户查询推荐技能"""
        return self._vector_db.search(query, top_k, [ItemType.SKILL])
    
    def recommend_experts(self, query: str, top_k: int = 3) -> List[VectorItem]:
        """根据用户查询推荐专家"""
        return self._vector_db.search(query, top_k, [ItemType.EXPERT])
    
    def recommend_all(self, query: str, top_k: int = 5) -> List[VectorItem]:
        """根据用户查询推荐所有相关项目"""
        return self._vector_db.search(query, top_k)
    
    def get_all_tools(self) -> List[VectorItem]:
        """获取所有工具"""
        return self._vector_db.list_items(ItemType.TOOL)
    
    def get_all_skills(self) -> List[VectorItem]:
        """获取所有技能"""
        return self._vector_db.list_items(ItemType.SKILL)
    
    def get_all_experts(self) -> List[VectorItem]:
        """获取所有专家"""
        return self._vector_db.list_items(ItemType.EXPERT)
    
    def to_llm_context(self, items: List[VectorItem]) -> str:
        """
        将项目列表转换为LLM可理解的上下文格式
        
        Args:
            items: 项目列表
            
        Returns:
            格式化的上下文字符串
        """
        if not items:
            return "无可用工具/技能"
        
        parts = []
        for item in items:
            parts.append(f"""
## {item.name}
- **类型**: {item.type.value}
- **描述**: {item.description}
- **关键词**: {', '.join(item.keywords) if item.keywords else '无'}
- **元数据**: {json.dumps(item.metadata, ensure_ascii=False)}
            """.strip())
        
        return "\n\n".join(parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._vector_db.get_stats()
        stats["tools"] = len(self.get_all_tools())
        stats["skills"] = len(self.get_all_skills())
        stats["experts"] = len(self.get_all_experts())
        return stats


# 全局实例
_tool_registry = None

def get_tool_registry(db_path: str = "./vector_db") -> ToolRegistry:
    """获取全局工具注册器实例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(db_path)
    return _tool_registry


# 示例使用
if __name__ == "__main__":
    # 创建注册器
    registry = get_tool_registry()
    
    # 注册示例工具
    registry.register_tool(
        name="网络搜索",
        description="使用搜索引擎搜索互联网信息",
        keywords=["搜索", "网络", "信息", "查询"],
        parameters={"query": "搜索关键词"},
        returns="搜索结果摘要"
    )
    
    registry.register_tool(
        name="文件读取",
        description="读取本地文件内容",
        keywords=["文件", "读取", "内容"],
        parameters={"file_path": "文件路径"},
        returns="文件内容文本"
    )
    
    # 注册示例技能
    registry.register_skill(
        name="数据分析",
        description="处理和分析数据，生成可视化图表",
        keywords=["数据", "分析", "图表", "可视化"]
    )
    
    # 注册示例专家
    registry.register_expert(
        name="Python编程专家",
        description="精通Python编程，擅长解决编程问题",
        keywords=["Python", "编程", "代码"],
        expertise=["Python", "数据分析", "机器学习"]
    )
    
    # 搜索测试
    results = registry.recommend_tools("我想搜索一些信息")
    print("推荐工具:")
    for item in results:
        print(f"- {item.name}: {item.description}")
    
    # 获取统计
    stats = registry.get_stats()
    print(f"\n统计信息: {stats}")