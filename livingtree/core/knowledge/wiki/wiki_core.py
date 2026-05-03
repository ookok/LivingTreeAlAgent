"""
LLM Wiki Core

LLM Wiki 核心模块，提供页面管理、版本控制、搜索等功能，集成DeepOnto本体推理。

作者: LivingTreeAI Team
日期: 2026-05-01
版本: 2.1.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)

try:
    from deeponto.reasoner import DLReasoner
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False


@dataclass
class WikiPage:
    """Wiki 页面"""
    id: str
    title: str
    content: str
    author: str = "system"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    revision: int = 1
    is_published: bool = True
    summary: Optional[str] = None


@dataclass
class PageRevision:
    """页面版本"""
    revision_id: str
    page_id: str
    content: str
    author: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    comment: str = ""
    revision_number: int = 1


class WikiCore:
    """
    LLM Wiki 核心
    
    核心功能：
    - 页面管理（创建、读取、更新、删除）
    - 版本控制
    - 页面链接管理
    - 搜索功能
    - 本体推理增强（DeepOnto集成）
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """初始化 Wiki 核心"""
        self._pages: Dict[str, WikiPage] = {}
        self._revisions: Dict[str, List[PageRevision]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        self._ontology_reasoner = None
        self._entity_embedding_service = None
        
        self._storage_path = Path(storage_path) if storage_path else \
            Path.home() / ".hermes-desktop" / "wiki"
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._init_ontology_services()
        self._load_pages()
        logger.info(f"WikiCore v2.1.0 初始化完成，页面数: {len(self._pages)}")
    
    def _init_ontology_services(self):
        """初始化本体推理服务"""
        try:
            from ..deeponto_integration import get_ontology_reasoner, get_entity_embedding_service
            
            self._ontology_reasoner = get_ontology_reasoner()
            self._ontology_reasoner.initialize()
            
            self._entity_embedding_service = get_entity_embedding_service()
            self._entity_embedding_service.initialize()
            
            logger.info("本体推理服务初始化成功")
        except ImportError as e:
            logger.warning(f"本体推理服务初始化失败: {e}")
    
    def _load_pages(self):
        """加载已保存的页面"""
        pages_dir = self._storage_path / "pages"
        pages_dir.mkdir(exist_ok=True)
        
        for page_file in pages_dir.glob("*.json"):
            try:
                with open(page_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    page = WikiPage(**data)
                    self._pages[page.id] = page
                    
                    # 更新标签索引
                    for tag in page.tags:
                        if tag not in self._tag_index:
                            self._tag_index[tag] = []
                        if page.id not in self._tag_index[tag]:
                            self._tag_index[tag].append(page.id)
            except Exception as e:
                logger.error(f"加载页面失败 {page_file}: {e}")
    
    def _save_page(self, page: WikiPage):
        """保存页面"""
        pages_dir = self._storage_path / "pages"
        pages_dir.mkdir(exist_ok=True)
        
        page_file = pages_dir / f"{page.id}.json"
        with open(page_file, "w", encoding="utf-8") as f:
            json.dump({
                "id": page.id,
                "title": page.title,
                "content": page.content,
                "author": page.author,
                "created_at": page.created_at,
                "updated_at": page.updated_at,
                "tags": page.tags,
                "links": page.links,
                "revision": page.revision,
                "is_published": page.is_published,
                "summary": page.summary,
            }, f, ensure_ascii=False, indent=2)
    
    def create_page(self, title: str, content: str, author: str = "system",
                   tags: Optional[List[str]] = None) -> WikiPage:
        """
        创建页面
        
        Args:
            title: 页面标题
            content: 页面内容
            author: 作者
            tags: 标签列表
            
        Returns:
            WikiPage 创建的页面
        """
        page_id = self._generate_page_id(title)
        
        if page_id in self._pages:
            logger.warning(f"页面已存在: {title}")
            return self._pages[page_id]
        
        page = WikiPage(
            id=page_id,
            title=title,
            content=content,
            author=author,
            tags=tags or [],
        )
        
        # 提取链接
        page.links = self._extract_links(content)
        
        # 生成摘要
        page.summary = self._generate_summary(content)
        
        self._pages[page_id] = page
        
        # 更新标签索引
        for tag in page.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if page_id not in self._tag_index[tag]:
                self._tag_index[tag].append(page_id)
        
        # 保存
        self._save_page(page)
        
        logger.info(f"页面创建成功: {title}")
        return page
    
    def get_page(self, page_id: str) -> Optional[WikiPage]:
        """
        获取页面
        
        Args:
            page_id: 页面ID
            
        Returns:
            WikiPage 页面对象
        """
        return self._pages.get(page_id)
    
    def update_page(self, page_id: str, content: str, author: str = "system",
                   comment: str = "") -> bool:
        """
        更新页面
        
        Args:
            page_id: 页面ID
            content: 新内容
            author: 作者
            comment: 更新注释
            
        Returns:
            bool 是否成功
        """
        if page_id not in self._pages:
            logger.error(f"页面不存在: {page_id}")
            return False
        
        page = self._pages[page_id]
        
        # 创建版本记录
        revision = PageRevision(
            revision_id=f"{page_id}_{page.revision}",
            page_id=page_id,
            content=page.content,
            author=page.author,
            comment=comment,
            revision_number=page.revision,
        )
        
        if page_id not in self._revisions:
            self._revisions[page_id] = []
        self._revisions[page_id].append(revision)
        
        # 更新页面
        page.content = content
        page.author = author
        page.updated_at = datetime.now().isoformat()
        page.revision += 1
        page.links = self._extract_links(content)
        page.summary = self._generate_summary(content)
        
        # 更新标签索引（移除旧标签）
        for tag in list(self._tag_index.keys()):
            if page_id in self._tag_index[tag]:
                self._tag_index[tag].remove(page_id)
        
        # 添加新标签
        for tag in page.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if page_id not in self._tag_index[tag]:
                self._tag_index[tag].append(page_id)
        
        # 保存
        self._save_page(page)
        
        logger.info(f"页面更新成功: {page.title} (修订版 {page.revision})")
        return True
    
    def delete_page(self, page_id: str) -> bool:
        """
        删除页面
        
        Args:
            page_id: 页面ID
            
        Returns:
            bool 是否成功
        """
        if page_id not in self._pages:
            logger.error(f"页面不存在: {page_id}")
            return False
        
        page = self._pages[page_id]
        
        # 清理标签索引
        for tag in list(self._tag_index.keys()):
            if page_id in self._tag_index[tag]:
                self._tag_index[tag].remove(page_id)
        
        # 删除文件
        page_file = self._storage_path / "pages" / f"{page_id}.json"
        if page_file.exists():
            page_file.unlink()
        
        del self._pages[page_id]
        
        logger.info(f"页面删除成功: {page.title}")
        return True
    
    def search_pages(self, query: str, tags: Optional[List[str]] = None) -> List[WikiPage]:
        """
        搜索页面
        
        Args:
            query: 搜索词
            tags: 标签过滤
            
        Returns:
            List 匹配的页面列表
        """
        results = []
        query_lower = query.lower()
        
        for page in self._pages.values():
            # 检查是否发布
            if not page.is_published:
                continue
            
            # 标签过滤
            if tags:
                has_all_tags = all(tag in page.tags for tag in tags)
                if not has_all_tags:
                    continue
            
            # 搜索标题和内容
            if (query_lower in page.title.lower() or 
                query_lower in page.content.lower() or
                query_lower in (page.summary or "").lower()):
                results.append(page)
        
        # 按相关性排序
        results.sort(key=lambda p: self._calculate_relevance(p, query), reverse=True)
        return results
    
    def _calculate_relevance(self, page: WikiPage, query: str) -> float:
        """计算页面与查询的相关性"""
        score = 0.0
        query_lower = query.lower()
        
        # 标题匹配
        if query_lower in page.title.lower():
            score += 0.5
        
        # 内容匹配
        content_lower = page.content.lower()
        if query_lower in content_lower:
            score += 0.3
        
        # 摘要匹配
        if page.summary and query_lower in page.summary.lower():
            score += 0.2
        
        return score
    
    def get_pages_by_tag(self, tag: str) -> List[WikiPage]:
        """
        获取指定标签的页面
        
        Args:
            tag: 标签名
            
        Returns:
            List 页面列表
        """
        page_ids = self._tag_index.get(tag, [])
        return [self._pages.get(pid) for pid in page_ids if self._pages.get(pid)]
    
    def get_all_pages(self) -> List[WikiPage]:
        """获取所有页面"""
        return list(self._pages.values())
    
    def get_page_revisions(self, page_id: str) -> List[PageRevision]:
        """
        获取页面版本历史
        
        Args:
            page_id: 页面ID
            
        Returns:
            List 版本列表
        """
        return self._revisions.get(page_id, [])
    
    def get_page_by_title(self, title: str) -> Optional[WikiPage]:
        """
        通过标题获取页面
        
        Args:
            title: 页面标题
            
        Returns:
            WikiPage 页面对象
        """
        page_id = self._generate_page_id(title)
        return self._pages.get(page_id)
    
    def _generate_page_id(self, title: str) -> str:
        """生成页面ID"""
        import hashlib
        return hashlib.md5(title.encode()).hexdigest()[:16]
    
    def _extract_links(self, content: str) -> List[str]:
        """
        从内容中提取 Wiki 链接
        
        支持格式: [[页面标题]]
        """
        import re
        matches = re.findall(r'\[\[([^\]]+)\]\]', content)
        return [self._generate_page_id(m.strip()) for m in matches]
    
    def _generate_summary(self, content: str) -> str:
        """生成页面摘要"""
        # 去除 Markdown 格式
        import re
        text = re.sub(r'[#*`>\[\]]', '', content)
        
        # 取前200个字符
        summary = text.strip()[:200]
        
        # 如果被截断，添加省略号
        if len(text) > 200:
            summary += "..."
        
        return summary
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_pages": len(self._pages),
            "total_revisions": sum(len(rev) for rev in self._revisions.values()),
            "total_tags": len(self._tag_index),
            "published_pages": sum(1 for p in self._pages.values() if p.is_published),
        }


# 全局 Wiki 核心实例
_wiki_core_instance = None

def get_wiki_core() -> WikiCore:
    """获取全局 Wiki 核心实例"""
    global _wiki_core_instance
    if _wiki_core_instance is None:
        _wiki_core_instance = WikiCore()
    return _wiki_core_instance
