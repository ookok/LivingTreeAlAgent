"""
ContextEngine - 上下文引擎

实现 OpenViking 的上下文数据库集成：
1. 三层信息模型（L0/L1/L2）
2. 文件系统范式（viking:// 协议）
3. 目录递归检索
4. 多租户隔离支持

核心功能：
- read_abstract() - 读取L0层（快速过滤）
- read_overview() - 读取L1层（决策参考）
- read() - 读取L2层（完整内容）
- search() - 搜索上下文
- ls() - 列出目录
- add_resource() - 添加资源

借鉴 OpenViking 的设计理念：文件系统范式 + 三层信息模型

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import os
import json
import time


class ContextLevel(Enum):
    """上下文层级"""
    L0 = "l0"  # Abstract (摘要) - ~100 tokens
    L1 = "l1"  # Overview (概览) - ~2000 tokens
    L2 = "l2"  # Details (详情) - 无限制


@dataclass
class ContextEntry:
    """
    上下文条目
    
    代表一个上下文资源，包含三层信息。
    """
    uri: str
    l0_abstract: str = ""           # L0层：摘要 (~100 tokens)
    l1_overview: str = ""           # L1层：概览 (~2000 tokens)
    l2_details: str = ""            # L2层：详情（完整内容）
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    
    def get_level_content(self, level: ContextLevel) -> str:
        """获取指定层级的内容"""
        if level == ContextLevel.L0:
            return self.l0_abstract
        elif level == ContextLevel.L1:
            return self.l1_overview
        elif level == ContextLevel.L2:
            return self.l2_details
        return ""


@dataclass
class SearchResult:
    """
    搜索结果
    """
    uri: str
    score: float
    l0_abstract: str
    l1_overview: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestContext:
    """
    请求上下文（多租户隔离）
    
    携带 account_id 和 user 身份，强制执行多租户隔离。
    """
    account_id: str
    user_id: str
    tenant_id: Optional[str] = None


class ContextEngine:
    """
    上下文引擎
    
    封装 OpenViking 的核心功能：
    1. 三层信息模型（L0/L1/L2）
    2. 文件系统范式（viking:// 协议）
    3. 目录递归检索
    4. 多租户隔离
    
    Viking URI 结构：
        viking://account_id/user/path/to/resource
    
    目录结构：
        viking://account_id/user/memories/...
        viking://account_id/user/resources/...
        viking://account_id/user/skills/...
    """
    
    def __init__(self, base_uri: str = "viking://default/default"):
        self._logger = logger.bind(component="ContextEngine")
        
        # 内存存储（实际应用中可替换为 OpenViking SDK）
        self._store: Dict[str, ContextEntry] = {}
        
        # 当前请求上下文（多租户隔离）
        self._request_context: Optional[RequestContext] = None
        
        # 基础URI
        self._base_uri = base_uri
        
        # 初始化默认目录结构
        self._init_default_structure()
        
        self._logger.info("✅ ContextEngine 初始化完成")
    
    def _init_default_structure(self):
        """初始化默认目录结构"""
        default_dirs = [
            "memories/",
            "resources/", 
            "skills/",
            "contexts/",
            "projects/"
        ]
        
        for dir_name in default_dirs:
            uri = f"{self._base_uri}/{dir_name}"
            if uri not in self._store:
                self._store[uri] = ContextEntry(
                    uri=uri,
                    l0_abstract=f"目录: {dir_name}",
                    l1_overview=f"默认目录 {dir_name}",
                    metadata={"type": "directory"}
                )
    
    def set_request_context(self, context: RequestContext):
        """
        设置请求上下文（多租户隔离）
        
        Args:
            context: 请求上下文
        """
        self._request_context = context
        self._base_uri = f"viking://{context.account_id}/{context.user_id}"
        self._logger.debug(f"🔧 设置请求上下文: {self._base_uri}")
    
    def get_request_context(self) -> Optional[RequestContext]:
        """获取当前请求上下文"""
        return self._request_context
    
    def add_resource(self, path: str, content: str, metadata: Dict[str, Any] = None):
        """
        添加资源
        
        Args:
            path: 资源路径（相对路径或完整URI）
            content: 资源内容
            metadata: 元数据
        """
        # 解析URI
        uri = self._resolve_uri(path)
        
        # 生成三层内容
        l0_abstract = self._generate_l0(content)
        l1_overview = self._generate_l1(content)
        
        # 创建上下文条目
        entry = ContextEntry(
            uri=uri,
            l0_abstract=l0_abstract,
            l1_overview=l1_overview,
            l2_details=content,
            metadata=metadata or {}
        )
        
        self._store[uri] = entry
        self._logger.info(f"📥 添加资源: {uri}")
    
    def _resolve_uri(self, path: str) -> str:
        """
        解析路径为完整URI
        
        Args:
            path: 路径（相对路径或完整URI）
            
        Returns:
            完整URI
        """
        if path.startswith("viking://"):
            return path
        
        # 相对路径，拼接基础URI
        return f"{self._base_uri}/{path}"
    
    def _generate_l0(self, content: str) -> str:
        """
        生成L0摘要（~100 tokens）
        
        Args:
            content: 原始内容
            
        Returns:
            L0摘要
        """
        # 简化实现：取前100字符
        return content[:100] + "..." if len(content) > 100 else content
    
    def _generate_l1(self, content: str) -> str:
        """
        生成L1概览（~2000 tokens）
        
        Args:
            content: 原始内容
            
        Returns:
            L1概览
        """
        # 简化实现：取前2000字符
        return content[:2000] + "..." if len(content) > 2000 else content
    
    def read_abstract(self, uri: str) -> Optional[str]:
        """
        读取L0层（快速过滤）
        
        Args:
            uri: 资源URI
            
        Returns:
            L0摘要（如果存在）
        """
        full_uri = self._resolve_uri(uri)
        entry = self._store.get(full_uri)
        
        if entry:
            return entry.l0_abstract
        
        return None
    
    def read_overview(self, uri: str) -> Optional[str]:
        """
        读取L1层（决策参考）
        
        Args:
            uri: 资源URI
            
        Returns:
            L1概览（如果存在）
        """
        full_uri = self._resolve_uri(uri)
        entry = self._store.get(full_uri)
        
        if entry:
            return entry.l1_overview
        
        return None
    
    def read(self, uri: str) -> Optional[str]:
        """
        读取L2层（完整内容）
        
        Args:
            uri: 资源URI
            
        Returns:
            L2详情（如果存在）
        """
        full_uri = self._resolve_uri(uri)
        entry = self._store.get(full_uri)
        
        if entry:
            return entry.l2_details
        
        return None
    
    def ls(self, uri: str = "") -> List[Dict[str, Any]]:
        """
        列出目录内容
        
        Args:
            uri: 目录URI（默认为当前基础URI）
            
        Returns:
            目录内容列表
        """
        if not uri:
            uri = self._base_uri
        
        full_uri = self._resolve_uri(uri)
        
        # 确保URI以/结尾
        if not full_uri.endswith("/"):
            full_uri += "/"
        
        # 查找所有子路径
        results = []
        for key, entry in self._store.items():
            if key.startswith(full_uri) and key != full_uri:
                # 获取相对路径
                relative_path = key[len(full_uri):]
                
                # 只获取直接子项（不递归）
                if "/" not in relative_path:
                    results.append({
                        "name": relative_path,
                        "uri": key,
                        "type": entry.metadata.get("type", "file"),
                        "abstract": entry.l0_abstract
                    })
        
        return results
    
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        搜索上下文
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            搜索结果列表
        """
        results = []
        
        for uri, entry in self._store.items():
            # 在三层内容中搜索
            if (query.lower() in entry.l0_abstract.lower() or
                query.lower() in entry.l1_overview.lower() or
                query.lower() in entry.l2_details.lower()):
                
                # 计算匹配分数
                score = self._calculate_score(query, entry)
                
                results.append(SearchResult(
                    uri=uri,
                    score=score,
                    l0_abstract=entry.l0_abstract,
                    l1_overview=entry.l1_overview,
                    metadata=entry.metadata
                ))
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:limit]
    
    def _calculate_score(self, query: str, entry: ContextEntry) -> float:
        """
        计算搜索匹配分数
        
        Args:
            query: 搜索关键词
            entry: 上下文条目
            
        Returns:
            匹配分数（0-1）
        """
        score = 0.0
        query_lower = query.lower()
        
        # L0层匹配权重最高
        if query_lower in entry.l0_abstract.lower():
            score += 0.5
        
        # L1层匹配权重次之
        if query_lower in entry.l1_overview.lower():
            score += 0.3
        
        # L2层匹配权重最低
        if query_lower in entry.l2_details.lower():
            score += 0.2
        
        return score
    
    def recursive_search(self, query: str, base_uri: str = "", depth: int = 3) -> List[SearchResult]:
        """
        目录递归检索
        
        Args:
            query: 搜索关键词
            base_uri: 基础目录URI
            depth: 递归深度
            
        Returns:
            搜索结果列表
        """
        if not base_uri:
            base_uri = self._base_uri
        
        full_uri = self._resolve_uri(base_uri)
        
        # 先在当前目录搜索
        results = []
        
        # 递归搜索
        def search_recursive(current_uri: str, current_depth: int):
            if current_depth > depth:
                return
            
            # 搜索当前目录下的内容
            for uri, entry in self._store.items():
                if uri.startswith(current_uri):
                    if query.lower() in entry.l0_abstract.lower():
                        score = self._calculate_score(query, entry)
                        results.append(SearchResult(
                            uri=uri,
                            score=score * (1 - current_depth * 0.1),  # 深度惩罚
                            l0_abstract=entry.l0_abstract,
                            l1_overview=entry.l1_overview,
                            metadata=entry.metadata
                        ))
            
            # 递归子目录
            if current_depth < depth:
                subdirs = self.ls(current_uri)
                for subdir in subdirs:
                    if subdir.get("type") == "directory":
                        search_recursive(subdir["uri"], current_depth + 1)
        
        search_recursive(full_uri, 0)
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    def delete_resource(self, uri: str):
        """
        删除资源
        
        Args:
            uri: 资源URI
        """
        full_uri = self._resolve_uri(uri)
        
        if full_uri in self._store:
            del self._store[full_uri]
            self._logger.info(f"🗑️ 删除资源: {uri}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_resources": len(self._store),
            "base_uri": self._base_uri,
            "has_context": self._request_context is not None
        }


# 创建全局实例
context_engine = ContextEngine()


def get_context_engine() -> ContextEngine:
    """获取上下文引擎实例"""
    return context_engine


# 测试函数
async def test_context_engine():
    """测试上下文引擎"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ContextEngine")
    print("=" * 60)
    
    engine = ContextEngine()
    
    # 1. 设置请求上下文
    print("\n[1] 设置请求上下文...")
    ctx = RequestContext(account_id="test_account", user_id="test_user")
    engine.set_request_context(ctx)
    print(f"    ✓ 上下文URI: {engine._base_uri}")
    
    # 2. 添加资源
    print("\n[2] 添加资源...")
    engine.add_resource(
        "memories/test_memory.txt",
        "这是一段测试记忆内容，包含很多信息。" * 50,
        {"type": "memory", "category": "test"}
    )
    engine.add_resource(
        "resources/document.md",
        "# 测试文档\n\n这是一个测试文档的内容。\n\n## 章节\n\n更多内容...",
        {"type": "document", "format": "markdown"}
    )
    print(f"    ✓ 资源数量: {engine.get_stats()['total_resources']}")
    
    # 3. 读取L0层
    print("\n[3] 读取L0层...")
    l0 = engine.read_abstract("memories/test_memory.txt")
    print(f"    ✓ L0摘要长度: {len(l0)}")
    print(f"    ✓ L0内容: {l0[:50]}...")
    
    # 4. 读取L1层
    print("\n[4] 读取L1层...")
    l1 = engine.read_overview("memories/test_memory.txt")
    print(f"    ✓ L1概览长度: {len(l1)}")
    
    # 5. 读取L2层
    print("\n[5] 读取L2层...")
    l2 = engine.read("memories/test_memory.txt")
    print(f"    ✓ L2详情长度: {len(l2)}")
    
    # 6. 列出目录
    print("\n[6] 列出目录...")
    items = engine.ls()
    print(f"    ✓ 目录项数量: {len(items)}")
    for item in items:
        print(f"      - {item['name']} ({item['type']})")
    
    # 7. 搜索上下文
    print("\n[7] 搜索上下文...")
    results = engine.search("测试")
    print(f"    ✓ 搜索结果数量: {len(results)}")
    for result in results:
        print(f"      - {result.uri} (分数: {result.score:.2f})")
    
    # 8. 递归搜索
    print("\n[8] 递归搜索...")
    results = engine.recursive_search("测试", depth=2)
    print(f"    ✓ 递归搜索结果数量: {len(results)}")
    
    # 9. 删除资源
    print("\n[9] 删除资源...")
    engine.delete_resource("resources/document.md")
    print(f"    ✓ 删除后资源数量: {engine.get_stats()['total_resources']}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_context_engine())