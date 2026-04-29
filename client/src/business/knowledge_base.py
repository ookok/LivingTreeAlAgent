"""
本地知识库系统
存储和管理开发知识、代码片段、解决方案等
"""

import os
import json
import pickle
import hashlib
import asyncio
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class KnowledgeType(Enum):
    """知识类型"""
    CODE_SNIPPET = "code_snippet"
    SOLUTION = "solution"
    DOCUMENTATION = "documentation"
    EXAMPLE = "example"
    TIP = "tip"
    BEST_PRACTICE = "best_practice"
    ERROR_FIX = "error_fix"


class KnowledgeDomain(Enum):
    """知识领域"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    REACT = "react"
    VUE = "vue"
    NODEJS = "nodejs"
    FLASK = "flask"
    DJANGO = "django"
    DATABASE = "database"
    DEVOPS = "devops"
    FRONTEND = "frontend"
    BACKEND = "backend"
    MOBILE = "mobile"
    OTHER = "other"


@dataclass
class KnowledgeItem:
    """知识项"""
    id: str
    title: str
    content: str
    knowledge_type: KnowledgeType
    domain: KnowledgeDomain
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    rating: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeStore:
    """知识存储"""
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/knowledge")
        os.makedirs(self.storage_path, exist_ok=True)
        self.knowledge_items: Dict[str, KnowledgeItem] = {}
        self._load_items()
    
    def _load_items(self):
        """加载知识项"""
        index_file = os.path.join(self.storage_path, "index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                    for item_id, item_data in index.items():
                        item = KnowledgeItem(
                            id=item_id,
                            title=item_data['title'],
                            content=item_data['content'],
                            knowledge_type=KnowledgeType(item_data['knowledge_type']),
                            domain=KnowledgeDomain(item_data['domain']),
                            tags=item_data.get('tags', []),
                            created_at=datetime.fromisoformat(item_data.get('created_at')),
                            updated_at=datetime.fromisoformat(item_data.get('updated_at')),
                            usage_count=item_data.get('usage_count', 0),
                            rating=item_data.get('rating', 0.0),
                            metadata=item_data.get('metadata', {})
                        )
                        self.knowledge_items[item_id] = item
            except Exception as e:
                print(f"加载知识项失败: {e}")
    
    def _save_items(self):
        """保存知识项"""
        index_file = os.path.join(self.storage_path, "index.json")
        index = {}
        for item_id, item in self.knowledge_items.items():
            index[item_id] = {
                'title': item.title,
                'content': item.content,
                'knowledge_type': item.knowledge_type.value,
                'domain': item.domain.value,
                'tags': item.tags,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat(),
                'usage_count': item.usage_count,
                'rating': item.rating,
                'metadata': item.metadata
            }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    
    def add_item(self, item: KnowledgeItem) -> bool:
        """添加知识项"""
        self.knowledge_items[item.id] = item
        self._save_items()
        return True
    
    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新知识项"""
        if item_id not in self.knowledge_items:
            return False
        
        item = self.knowledge_items[item_id]
        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)
        item.updated_at = datetime.now()
        self._save_items()
        return True
    
    def delete_item(self, item_id: str) -> bool:
        """删除知识项"""
        if item_id in self.knowledge_items:
            del self.knowledge_items[item_id]
            self._save_items()
            return True
        return False
    
    def get_item(self, item_id: str) -> Optional[KnowledgeItem]:
        """获取知识项"""
        item = self.knowledge_items.get(item_id)
        if item:
            item.usage_count += 1
            self._save_items()
        return item
    
    def list_items(self, **filters) -> List[KnowledgeItem]:
        """列出知识项"""
        items = list(self.knowledge_items.values())
        
        # 应用过滤
        if 'knowledge_type' in filters:
            items = [item for item in items if item.knowledge_type == filters['knowledge_type']]
        if 'domain' in filters:
            items = [item for item in items if item.domain == filters['domain']]
        if 'tags' in filters:
            tags = filters['tags']
            items = [item for item in items if any(tag in item.tags for tag in tags)]
        
        # 按使用次数和评分排序
        items.sort(key=lambda x: (x.usage_count, x.rating), reverse=True)
        
        return items
    
    def search_items(self, query: str) -> List[KnowledgeItem]:
        """搜索知识项"""
        results = []
        query_lower = query.lower()
        
        for item in self.knowledge_items.values():
            score = 0
            
            # 标题匹配
            if query_lower in item.title.lower():
                score += 3
            
            # 内容匹配
            if query_lower in item.content.lower():
                score += 2
            
            # 标签匹配
            if any(query_lower in tag.lower() for tag in item.tags):
                score += 1
            
            if score > 0:
                results.append((score, item))
        
        # 按得分排序
        results.sort(reverse=True, key=lambda x: x[0])
        return [item for _, item in results]
    
    def get_recommendations(self, context: str) -> List[KnowledgeItem]:
        """获取推荐知识项"""
        # 简单的推荐逻辑
        results = self.search_items(context)
        return results[:5]  # 返回前5个结果


class EmbeddingManager:
    """嵌入管理器"""
    
    def __init__(self):
        self.embeddings: Dict[str, List[float]] = {}
        self.embedding_dim = 768  # 默认维度
    
    def generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入"""
        # 简化的嵌入生成
        # 实际项目中可以使用Sentence-BERT等模型
        hash_value = hashlib.md5(text.encode()).hexdigest()
        embedding = [float(int(hash_value[i:i+2], 16) / 255.0) for i in range(0, 32, 2)]
        # 填充到指定维度
        while len(embedding) < self.embedding_dim:
            embedding.append(0.0)
        return embedding[:self.embedding_dim]
    
    def get_embedding(self, item_id: str, text: str) -> List[float]:
        """获取嵌入"""
        if item_id not in self.embeddings:
            self.embeddings[item_id] = self.generate_embedding(text)
        return self.embeddings[item_id]
    
    def save_embeddings(self, path: str):
        """保存嵌入"""
        with open(path, 'wb') as f:
            pickle.dump(self.embeddings, f)
    
    def load_embeddings(self, path: str):
        """加载嵌入"""
        if os.path.exists(path):
            with open(path, 'rb') as f:
                self.embeddings = pickle.load(f)


class KnowledgeBase:
    """知识库"""
    
    def __init__(self, storage_path: str = None):
        self.knowledge_store = KnowledgeStore(storage_path)
        self.embedding_manager = EmbeddingManager()
        self._load_embeddings()
    
    def _load_embeddings(self):
        """加载嵌入"""
        embedding_path = os.path.join(self.knowledge_store.storage_path, "embeddings.pkl")
        self.embedding_manager.load_embeddings(embedding_path)
    
    def _save_embeddings(self):
        """保存嵌入"""
        embedding_path = os.path.join(self.knowledge_store.storage_path, "embeddings.pkl")
        self.embedding_manager.save_embeddings(embedding_path)
    
    def add_knowledge(self, title: str, content: str, knowledge_type: KnowledgeType, domain: KnowledgeDomain, tags: List[str] = None) -> str:
        """添加知识"""
        timestamp = int(datetime.now().timestamp())
        md5_hash = hashlib.md5((title + content).encode()).hexdigest()[:8]
        item_id = f"knowledge_{timestamp}_{md5_hash}"
        
        item = KnowledgeItem(
            id=item_id,
            title=title,
            content=content,
            knowledge_type=knowledge_type,
            domain=domain,
            tags=tags or []
        )
        
        self.knowledge_store.add_item(item)
        
        # 生成嵌入
        self.embedding_manager.get_embedding(item_id, content)
        self._save_embeddings()
        
        return item_id
    
    def update_knowledge(self, item_id: str, **updates) -> bool:
        """更新知识"""
        success = self.knowledge_store.update_item(item_id, updates)
        if success and 'content' in updates:
            # 更新嵌入
            self.embedding_manager.embeddings.pop(item_id, None)
            item = self.knowledge_store.get_item(item_id)
            if item:
                self.embedding_manager.get_embedding(item_id, item.content)
                self._save_embeddings()
        return success
    
    def delete_knowledge(self, item_id: str) -> bool:
        """删除知识"""
        success = self.knowledge_store.delete_item(item_id)
        if success:
            self.embedding_manager.embeddings.pop(item_id, None)
            self._save_embeddings()
        return success
    
    def get_knowledge(self, item_id: str) -> Optional[KnowledgeItem]:
        """获取知识"""
        return self.knowledge_store.get_item(item_id)
    
    def search_knowledge(self, query: str) -> List[KnowledgeItem]:
        """搜索知识"""
        return self.knowledge_store.search_items(query)
    
    def get_recommendations(self, context: str) -> List[KnowledgeItem]:
        """获取推荐知识"""
        return self.knowledge_store.get_recommendations(context)
    
    def get_knowledge_by_type(self, knowledge_type: KnowledgeType) -> List[KnowledgeItem]:
        """按类型获取知识"""
        return self.knowledge_store.list_items(knowledge_type=knowledge_type)
    
    def get_knowledge_by_domain(self, domain: KnowledgeDomain) -> List[KnowledgeItem]:
        """按领域获取知识"""
        return self.knowledge_store.list_items(domain=domain)
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """获取知识统计"""
        all_items = self.knowledge_store.list_items()
        stats = {
            'total_items': len(all_items),
            'items_by_type': {},
            'items_by_domain': {},
            'most_used': [],
            'highest_rated': []
        }
        
        # 按类型统计
        for item in all_items:
            stats['items_by_type'][item.knowledge_type.value] = stats['items_by_type'].get(item.knowledge_type.value, 0) + 1
            stats['items_by_domain'][item.domain.value] = stats['items_by_domain'].get(item.domain.value, 0) + 1
        
        # 最常用的知识
        most_used = sorted(all_items, key=lambda x: x.usage_count, reverse=True)[:5]
        stats['most_used'] = [{'id': item.id, 'title': item.title, 'usage_count': item.usage_count} for item in most_used]
        
        # 评分最高的知识
        highest_rated = sorted(all_items, key=lambda x: x.rating, reverse=True)[:5]
        stats['highest_rated'] = [{'id': item.id, 'title': item.title, 'rating': item.rating} for item in highest_rated]
        
        return stats
    
    def import_knowledge(self, file_path: str) -> bool:
        """导入知识"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item_data in data:
                    item = KnowledgeItem(
                        id=item_data['id'],
                        title=item_data['title'],
                        content=item_data['content'],
                        knowledge_type=KnowledgeType(item_data['knowledge_type']),
                        domain=KnowledgeDomain(item_data['domain']),
                        tags=item_data.get('tags', []),
                        created_at=datetime.fromisoformat(item_data.get('created_at')),
                        updated_at=datetime.fromisoformat(item_data.get('updated_at')),
                        usage_count=item_data.get('usage_count', 0),
                        rating=item_data.get('rating', 0.0),
                        metadata=item_data.get('metadata', {})
                    )
                    self.knowledge_store.add_item(item)
                    self.embedding_manager.get_embedding(item.id, item.content)
            self._save_embeddings()
            return True
        except Exception as e:
            print(f"导入知识失败: {e}")
            return False
    
    def export_knowledge(self, file_path: str) -> bool:
        """导出知识"""
        try:
            items = self.knowledge_store.list_items()
            data = []
            for item in items:
                data.append({
                    'id': item.id,
                    'title': item.title,
                    'content': item.content,
                    'knowledge_type': item.knowledge_type.value,
                    'domain': item.domain.value,
                    'tags': item.tags,
                    'created_at': item.created_at.isoformat(),
                    'updated_at': item.updated_at.isoformat(),
                    'usage_count': item.usage_count,
                    'rating': item.rating,
                    'metadata': item.metadata
                })
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"导出知识失败: {e}")
            return False


def create_knowledge_base(storage_path: str = None) -> KnowledgeBase:
    """
    创建知识库
    
    Args:
        storage_path: 存储路径
        
    Returns:
        KnowledgeBase: 知识库实例
    """
    return KnowledgeBase(storage_path)


def get_default_knowledge() -> List[Dict[str, Any]]:
    """
    获取默认知识
    
    Returns:
        List[Dict[str, Any]]: 默认知识列表
    """
    return [
        {
            'title': 'Python 函数定义',
            'content': 'def function_name(parameters):\n    """函数文档"""\n    # 函数体\n    return result',
            'knowledge_type': 'code_snippet',
            'domain': 'python',
            'tags': ['python', 'function', 'basics']
        },
        {
            'title': 'React 组件定义',
            'content': 'import React from \'react\';\n\nconst Component = () => {\n    return (\n        <div>Hello World</div>\n    );\n};\n\nexport default Component;',
            'knowledge_type': 'code_snippet',
            'domain': 'react',
            'tags': ['react', 'component', 'basics']
        },
        {
            'title': '常见错误：NameError',
            'content': 'NameError: name \'x\' is not defined\n\n解决方法：\n1. 检查变量名拼写\n2. 确保变量在使用前已定义\n3. 检查导入语句',
            'knowledge_type': 'error_fix',
            'domain': 'python',
            'tags': ['error', 'python', 'debugging']
        }
    ]