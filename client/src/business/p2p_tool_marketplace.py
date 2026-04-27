"""
P2P Tool Marketplace - 工具市场（P2P 共享）

允许不同 LivingTreeAIAgent 实例之间共享工具。

核心功能：
1. 工具发布 - 将本地工具发布到 P2P 网络
2. 工具发现 - 从 P2P 网络发现可用工具
3. 工具安装 - 从 P2P 网络下载并安装工具
4. 版本管理 - 工具版本检查和更新
5. 信誉系统 - 工具质量评价

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


class ToolListingStatus(Enum):
    """工具发布状态"""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


@dataclass
class ToolListing:
    """工具发布项"""
    id: str
    tool_name: str
    version: str
    seller_node_id: str
    description: str
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    install_command: List[str] = field(default_factory=list)
    file_hash: str = ""
    file_size: int = 0
    download_url: str = ""  # P2P 网络中的文件哈希
    status: ToolListingStatus = ToolListingStatus.DRAFT
    rating: float = 0.0
    rating_count: int = 0
    download_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "version": self.version,
            "seller_node_id": self.seller_node_id,
            "description": self.description,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "install_command": self.install_command,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "download_url": self.download_url,
            "status": self.status.value,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "download_count": self.download_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolListing":
        """从字典创建"""
        return cls(
            id=data["id"],
            tool_name=data["tool_name"],
            version=data["version"],
            seller_node_id=data["seller_node_id"],
            description=data["description"],
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", []),
            install_command=data.get("install_command", []),
            file_hash=data.get("file_hash", ""),
            file_size=data.get("file_size", 0),
            download_url=data.get("download_url", ""),
            status=ToolListingStatus(data.get("status", "draft")),
            rating=data.get("rating", 0.0),
            rating_count=data.get("rating_count", 0),
            download_count=data.get("download_count", 0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ToolReview:
    """工具评价"""
    id: str
    tool_listing_id: str
    reviewer_node_id: str
    rating: float
    comment: str = ""
    created_at: float = field(default_factory=time.time)


class P2PToolMarketplace:
    """
    P2P 工具市场
    
    核心功能：
    1. 发布工具到 P2P 网络
    2. 从 P2P 网络发现工具
    3. 下载并安装工具
    4. 评价工具
    
    用法：
        marketplace = P2PToolMarketplace()
        await marketplace.publish_tool("my_tool")
        tools = await marketplace.discover_tools("data analysis")
    """
    
    def __init__(self, node_id: Optional[str] = None):
        """
        初始化 P2P 工具市场
        
        Args:
            node_id: 当前节点 ID（如果为 None，则自动获取）
        """
        self._node_id = node_id or self._get_node_id()
        self._listings: Dict[str, ToolListing] = {}
        self._reviews: Dict[str, List[ToolReview]] = {}
        self._installed_tools: Dict[str, str] = {}  # {tool_name: install_path}
        self._lock = threading.RLock()
        
        # P2P 网络接口（延迟初始化）
        self._p2p_connector = None
        self._p2p_storage = None
        
        logger.info(f"[P2PToolMarketplace] 初始化完成，节点 ID: {self._node_id}")
    
    def _get_node_id(self) -> str:
        """获取当前节点 ID"""
        try:
            from client.src.business.p2p_connector import get_p2p_connector
            connector = get_p2p_connector()
            return connector.node_id
        except Exception as e:
            logger.warning(f"获取节点 ID 失败: {e}，使用随机 ID")
            import uuid
            return f"node_{uuid.uuid4().hex[:8]}"
    
    def _get_p2p_connector(self):
        """获取 P2P 连接器（延迟初始化）"""
        if self._p2p_connector is None:
            try:
                from client.src.business.p2p_connector import get_p2p_connector
                self._p2p_connector = get_p2p_connector()
            except Exception as e:
                logger.error(f"初始化 P2P 连接器失败: {e}")
                return None
        return self._p2p_connector
    
    # ── 工具发布 ──────────────────────────────────────────────────────
    
    async def publish_tool(
        self,
        tool_name: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        发布工具到 P2P 网络
        
        Args:
            tool_name: 工具名称
            description: 工具描述（如果为空，则从工具定义中获取）
            tags: 标签
            
        Returns:
            发布结果
        """
        logger.info(f"[P2PToolMarketplace] 发布工具: {tool_name}")
        
        # 1. 查找工具文件
        tool_file = self._find_tool_file(tool_name)
        if not tool_file:
            return {
                "success": False,
                "error": f"未找到工具文件: {tool_name}",
            }
        
        # 2. 读取工具代码
        try:
            with open(tool_file, 'r', encoding='utf-8') as f:
                tool_code = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": f"读取工具文件失败: {e}",
            }
        
        # 3. 计算文件哈希
        file_hash = hashlib.sha256(tool_code.encode()).hexdigest()
        file_size = len(tool_code.encode())
        
        # 4. 获取工具元数据
        tool_metadata = self._extract_tool_metadata(tool_name, tool_file)
        version = tool_metadata.get("version", "1.0.0")
        
        if not description:
            description = tool_metadata.get("description", "")
        
        if not tags:
            tags = tool_metadata.get("tags", [])
        
        # 5. 上传到 P2P 网络（获取下载 URL）
        download_url = await self._upload_to_p2p(tool_code, file_hash)
        
        if not download_url:
            return {
                "success": False,
                "error": "上传到 P2P 网络失败",
            }
        
        # 6. 创建工具发布项
        tool_listing = ToolListing(
            id=self._generate_listing_id(tool_name),
            tool_name=tool_name,
            version=version,
            seller_node_id=self._node_id,
            description=description,
            tags=tags,
            dependencies=tool_metadata.get("dependencies", []),
            install_command=tool_metadata.get("install_command", []),
            file_hash=file_hash,
            file_size=file_size,
            download_url=download_url,
            status=ToolListingStatus.PUBLISHED,
            metadata=tool_metadata,
        )
        
        # 7. 保存到本地
        with self._lock:
            self._listings[tool_listing.id] = tool_listing
        
        # 8. 广播到 P2P 网络
        await self._broadcast_listing(tool_listing)
        
        logger.info(f"[P2PToolMarketplace] 工具发布成功: {tool_name}, ID: {tool_listing.id}")
        
        return {
            "success": True,
            "listing_id": tool_listing.id,
            "tool_name": tool_name,
            "version": version,
            "download_url": download_url,
        }
    
    # ── 工具发现 ──────────────────────────────────────────────────────
    
    async def discover_tools(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        min_rating: float = 0.0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        从 P2P 网络发现工具
        
        Args:
            query: 搜索查询
            tags: 标签过滤
            min_rating: 最低评分
            limit: 最多返回数量
            
        Returns:
            工具列表
        """
        logger.info(f"[P2PToolMarketplace] 发现工具: {query}")
        
        # 1. 从 P2P 网络获取所有工具发布项
        remote_listings = await self._fetch_remote_listings()
        
        # 2. 合并本地和远程发布项
        all_listings = list(self._listings.values()) + remote_listings
        
        # 3. 过滤
        filtered = []
        for listing in all_listings:
            # 状态过滤
            if listing.status != ToolListingStatus.PUBLISHED:
                continue
            
            # 评分过滤
            if listing.rating < min_rating:
                continue
            
            # 标签过滤
            if tags:
                if not any(tag in listing.tags for tag in tags):
                    continue
            
            # 查询匹配（简单关键词匹配）
            if query:
                query_lower = query.lower()
                if (query_lower not in listing.tool_name.lower() and
                    query_lower not in listing.description.lower() and
                    not any(query_lower in tag.lower() for tag in listing.tags)):
                    continue
            
            filtered.append(listing)
        
        # 4. 排序（按评分降序，然后按下载次数降序）
        filtered.sort(key=lambda x: (-x.rating, -x.download_count))
        
        # 5. 限制数量
        filtered = filtered[:limit]
        
        # 6. 转换为字典
        result = [listing.to_dict() for listing in filtered]
        
        logger.info(f"[P2PToolMarketplace] 发现 {len(result)} 个工具")
        
        return result
    
    # ── 工具安装 ──────────────────────────────────────────────────────
    
    async def install_tool(
        self,
        listing_id: str,
        target_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        从 P2P 网络安装工具
        
        Args:
            listing_id: 工具发布项 ID
            target_dir: 安装目录（如果为 None，则安装到默认目录）
            
        Returns:
            安装结果
        """
        logger.info(f"[P2PToolMarketplace] 安装工具: {listing_id}")
        
        # 1. 查找工具发布项
        listing = self._get_listing(listing_id)
        if not listing:
            return {
                "success": False,
                "error": f"未找到工具发布项: {listing_id}",
            }
        
        # 2. 下载工具代码
        tool_code = await self._download_from_p2p(listing.download_url, listing.file_hash)
        
        if not tool_code:
            return {
                "success": False,
                "error": "从 P2P 网络下载工具失败",
            }
        
        # 3. 验证文件哈希
        actual_hash = hashlib.sha256(tool_code.encode()).hexdigest()
        if actual_hash != listing.file_hash:
            return {
                "success": False,
                "error": f"文件哈希验证失败: expected={listing.file_hash}, actual={actual_hash}",
            }
        
        # 4. 安装工具
        if not target_dir:
            target_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "client", "src", "business", "tools"
            )
        
        target_file = os.path.join(target_dir, f"{listing.tool_name}.py")
        
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(tool_code)
            logger.info(f"[P2PToolMarketplace] 工具已安装: {target_file}")
        except Exception as e:
            return {
                "success": False,
                "error": f"写入工具文件失败: {e}",
            }
        
        # 5. 安装依赖
        if listing.dependencies:
            await self._install_dependencies(listing.dependencies)
        
        # 6. 注册到 ToolRegistry
        try:
            from client.src.business.tools.register_all_tools import register_all_tools
            register_all_tools()
            logger.info(f"[P2PToolMarketplace] 工具已注册: {listing.tool_name}")
        except Exception as e:
            logger.warning(f"[P2PToolMarketplace] 注册工具失败: {e}")
        
        # 7. 更新下载次数
        listing.download_count += 1
        
        # 8. 保存到已安装工具列表
        with self._lock:
            self._installed_tools[listing.tool_name] = target_file
        
        return {
            "success": True,
            "tool_name": listing.tool_name,
            "version": listing.version,
            "install_path": target_file,
        }
    
    # ── 工具评价 ──────────────────────────────────────────────────────
    
    async def review_tool(
        self,
        listing_id: str,
        rating: float,
        comment: str = "",
    ) -> Dict[str, Any]:
        """
        评价工具
        
        Args:
            listing_id: 工具发布项 ID
            rating: 评分（0.0 - 5.0）
            comment: 评价内容
            
        Returns:
            评价结果
        """
        logger.info(f"[P2PToolMarketplace] 评价工具: {listing_id}, rating={rating}")
        
        # 1. 查找工具发布项
        listing = self._get_listing(listing_id)
        if not listing:
            return {
                "success": False,
                "error": f"未找到工具发布项: {listing_id}",
            }
        
        # 2. 创建评价
        review = ToolReview(
            id=self._generate_review_id(),
            tool_listing_id=listing_id,
            reviewer_node_id=self._node_id,
            rating=rating,
            comment=comment,
        )
        
        # 3. 保存到本地
        with self._lock:
            if listing.id not in self._reviews:
                self._reviews[listing.id] = []
            self._reviews[listing.id].append(review)
        
        # 4. 更新工具评分
        reviews = self._reviews.get(listing.id, [])
        total_rating = sum(r.rating for r in reviews)
        listing.rating = total_rating / len(reviews)
        listing.rating_count = len(reviews)
        
        # 5. 广播到 P2P 网络
        await self._broadcast_review(review)
        
        logger.info(f"[P2PToolMarketplace] 评价成功: {listing.tool_name}, rating={listing.rating}")
        
        return {
            "success": True,
            "listing_id": listing.id,
            "tool_name": listing.tool_name,
            "new_rating": listing.rating,
            "rating_count": listing.rating_count,
        }
    
    # ── 辅助方法 ─────────────────────────────────────────────────────
    
    def _find_tool_file(self, tool_name: str) -> Optional[str]:
        """查找工具文件"""
        # 从 ToolRegistry 获取工具
        try:
            from client.src.business.tools.tool_registry import ToolRegistry
            registry = ToolRegistry.get_instance()
            tool = registry.get_tool(tool_name)
            if tool and hasattr(tool, '__file__'):
                return tool.__file__
        except Exception:
            pass
        
        # 搜索工具文件
        tools_dir = Path("client/src/business/tools")
        for py_file in tools_dir.rglob("*.py"):
            if tool_name in py_file.name:
                return str(py_file)
        
        return None
    
    def _extract_tool_metadata(self, tool_name: str, tool_file: str) -> Dict[str, Any]:
        """提取工具元数据"""
        metadata = {
            "version": "1.0.0",
            "description": "",
            "tags": [],
            "dependencies": [],
            "install_command": [],
        }
        
        try:
            with open(tool_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取版本
            import re
            version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if version_match:
                metadata["version"] = version_match.group(1)
            
            # 提取描述
            desc_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            if desc_match:
                metadata["description"] = desc_match.group(1).strip()[:200]
            
            # 提取标签
            tags_match = re.search(r'tags\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if tags_match:
                tags_str = tags_match.group(1)
                metadata["tags"] = [tag.strip().strip("'\"") for tag in tags_str.split(",") if tag.strip()]
            
        except Exception as e:
            logger.error(f"提取工具元数据失败: {e}")
        
        return metadata
    
    async def _upload_to_p2p(self, content: str, file_hash: str) -> Optional[str]:
        """上传内容到 P2P 网络"""
        connector = self._get_p2p_connector()
        if not connector:
            # 如果没有 P2P 连接器，则保存到本地临时文件
            temp_dir = tempfile.mkdtemp()
            temp_file = os.path.join(temp_dir, f"{file_hash}.py")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"file://{temp_file}"
        
        try:
            # 上传到 P2P 网络
            result = connector.store_content(content.encode(), file_hash)
            if result.success:
                return result.content_hash
            else:
                logger.error(f"上传到 P2P 网络失败: {result.error}")
                return None
        except Exception as e:
            logger.error(f"上传到 P2P 网络失败: {e}")
            return None
    
    async def _download_from_p2p(self, url: str, expected_hash: str) -> Optional[str]:
        """从 P2P 网络下载内容"""
        connector = self._get_p2p_connector()
        if not connector:
            # 如果没有 P2P 连接器，则从本地文件读取
            if url.startswith("file://"):
                local_path = url[7:]
                try:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"读取本地文件失败: {e}")
                    return None
            return None
        
        try:
            # 从 P2P 网络下载
            result = connector.retrieve_content(url)
            if result.success:
                return result.content.decode()
            else:
                logger.error(f"从 P2P 网络下载失败: {result.error}")
                return None
        except Exception as e:
            logger.error(f"从 P2P 网络下载失败: {e}")
            return None
    
    async def _broadcast_listing(self, listing: ToolListing):
        """广播工具发布项到 P2P 网络"""
        connector = self._get_p2p_connector()
        if not connector:
            logger.warning("[P2PToolMarketplace] 未连接到 P2P 网络，跳过广播")
            return
        
        try:
            # 广播到 P2P 网络
            message = {
                "type": "tool_listing",
                "data": listing.to_dict(),
            }
            connector.broadcast(json.dumps(message))
            logger.info(f"[P2PToolMarketplace] 已广播工具发布项: {listing.tool_name}")
        except Exception as e:
            logger.error(f"广播工具发布项失败: {e}")
    
    async def _broadcast_review(self, review: ToolReview):
        """广播工具评价到 P2P 网络"""
        connector = self._get_p2p_connector()
        if not connector:
            logger.warning("[P2PToolMarketplace] 未连接到 P2P 网络，跳过广播")
            return
        
        try:
            # 广播到 P2P 网络
            message = {
                "type": "tool_review",
                "data": {
                    "id": review.id,
                    "tool_listing_id": review.tool_listing_id,
                    "reviewer_node_id": review.reviewer_node_id,
                    "rating": review.rating,
                    "comment": review.comment,
                    "created_at": review.created_at,
                },
            }
            connector.broadcast(json.dumps(message))
            logger.info(f"[P2PToolMarketplace] 已广播工具评价: {review.tool_listing_id}")
        except Exception as e:
            logger.error(f"广播工具评价失败: {e}")
    
    async def _fetch_remote_listings(self) -> List[ToolListing]:
        """从 P2P 网络获取远程工具发布项"""
        connector = self._get_p2p_connector()
        if not connector:
            return []
        
        try:
            # 从 P2P 网络获取所有工具发布项
            messages = connector.get_broadcast_messages(message_type="tool_listing")
            listings = []
            for msg in messages:
                try:
                    data = json.loads(msg)
                    if data.get("type") == "tool_listing":
                        listing = ToolListing.from_dict(data["data"])
                        listings.append(listing)
                except Exception:
                    continue
            return listings
        except Exception as e:
            logger.error(f"从 P2P 网络获取工具发布项失败: {e}")
            return []
    
    async def _install_dependencies(self, dependencies: List[str]):
        """安装依赖"""
        for dep in dependencies:
            try:
                # 尝试使用 pip 安装
                import subprocess
                result = subprocess.run(
                    ["pip", "install", dep],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    logger.info(f"[P2PToolMarketplace] 依赖安装成功: {dep}")
                else:
                    logger.warning(f"[P2PToolMarketplace] 依赖安装失败: {dep}, error={result.stderr}")
            except Exception as e:
                logger.error(f"[P2PToolMarketplace] 安装依赖失败: {dep}, error={e}")
    
    def _get_listing(self, listing_id: str) -> Optional[ToolListing]:
        """获取工具发布项"""
        with self._lock:
            # 从本地查找
            if listing_id in self._listings:
                return self._listings[listing_id]
        
        # 从远程查找（简化版：只查找本地）
        return None
    
    def _generate_listing_id(self, tool_name: str) -> str:
        """生成工具发布项 ID"""
        import uuid
        return f"tool_{tool_name}_{uuid.uuid4().hex[:8]}"
    
    def _generate_review_id(self) -> str:
        """生成评价 ID"""
        import uuid
        return f"review_{uuid.uuid4().hex[:8]}"


async def test_p2p_tool_marketplace():
    """测试 P2P 工具市场"""
    import sys
    
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
    
    print("=" * 60)
    print("测试 P2PToolMarketplace")
    print("=" * 60)
    
    # 创建市场
    marketplace = P2PToolMarketplace()
    
    # 测试发布工具
    print("\n测试发布工具...")
    result = await marketplace.publish_tool(
        tool_name="web_crawler",
        description="网页爬虫工具",
        tags=["web", "crawler", "data"],
    )
    print(f"发布结果: success={result.get('success')}, msg={result.get('error', result.get('listing_id'))}")
    
    # 测试发现工具
    print("\n测试发现工具...")
    tools = await marketplace.discover_tools("web")
    print(f"发现工具数量: {len(tools)}")
    for tool in tools[:3]:
        print(f"  - {tool['tool_name']}: {tool['description'][:50]}...")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_p2p_tool_marketplace())
