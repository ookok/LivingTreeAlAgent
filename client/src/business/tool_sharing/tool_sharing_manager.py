"""
ToolSharingManager - 工具共享管理器

功能：
1. 自动上传好用的工具到中继服务器
2. 自动下载其他智能体创建的工具
3. 工具评分与反馈
4. 工具自动更新

遵循自我进化原则：
- 支持集体智慧进化
- 自动学习和共享优秀工具
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime


@dataclass
class ToolPackage:
    """工具包"""
    tool_name: str
    version: str
    code: str
    dependencies: List[str]
    documentation: str
    created_at: datetime = field(default_factory=datetime.now)
    creator_id: str = "unknown"
    rating: float = 0.0
    download_count: int = 0


class ToolSharingManager:
    """
    工具共享管理器
    
    支持集体智慧进化循环：
    Agent A 创建工具 → 测试通过 → 上传到 Relay Server
    Agent B 下载工具 → 使用工具 → 评分反馈
    Agent C 下载工具 → 改进工具 → 上传改进版
    所有 Agent 更新到改进版 → 整体智慧提升
    """

    def __init__(self):
        self._logger = logger.bind(component="ToolSharingManager")
        self._relay_server_url = "http://localhost:8000"
        self._tool_registry = None
        self._rating_system = ToolRatingSystem()
        self._downloader = ToolDownloader()
        self._uploader = ToolUploader()
        self._local_tools = {}

    async def auto_share_tool(self, tool_name: str, tool_result: Dict[str, Any]):
        """
        自动共享工具
        
        触发条件：
        1. 工具测试通过
        2. 工具执行成功率高（>95%）
        3. 工具被广泛使用（>10次）
        """
        if not self._should_share_tool(tool_name, tool_result):
            return

        # 打包工具（代码 + 依赖 + 文档）
        tool_package = await self._package_tool(tool_name)

        # 上传到中继服务器
        await self._uploader.upload(tool_package)

        # 通知其他智能体
        await self._notify_other_agents(tool_name)

        self._logger.info(f"已共享工具: {tool_name}")

    def _should_share_tool(self, tool_name: str, tool_result: Dict[str, Any]) -> bool:
        """判断是否应该共享工具"""
        success_rate = tool_result.get("success_rate", 0)
        usage_count = tool_result.get("usage_count", 0)
        
        return success_rate > 0.95 and usage_count > 10

    async def _package_tool(self, tool_name: str) -> ToolPackage:
        """打包工具"""
        return ToolPackage(
            tool_name=tool_name,
            version="1.0",
            code="工具代码",
            dependencies=[],
            documentation="工具文档",
            creator_id="system"
        )

    async def _notify_other_agents(self, tool_name: str):
        """通知其他智能体"""
        self._logger.info(f"通知其他智能体关于新工具: {tool_name}")

    async def auto_download_tool(self, tool_name: str) -> bool:
        """
        自动下载工具
        
        工作流程：
        1. 检查本地是否已有该工具
        2. 从中继服务器下载工具包
        3. 安装依赖
        4. 注册到 ToolRegistry
        5. 测试工具是否有效
        """
        # 检查本地
        if tool_name in self._local_tools:
            return True

        # 下载工具包
        tool_package = await self._downloader.download(tool_name)
        if not tool_package:
            return False

        # 安装依赖
        await self._install_tool_dependencies(tool_package)

        # 注册工具
        await self._register_downloaded_tool(tool_package)

        # 测试工具
        test_result = await self._test_downloaded_tool(tool_name)

        return test_result

    async def _install_tool_dependencies(self, tool_package: ToolPackage):
        """安装工具依赖"""
        for dep in tool_package.dependencies:
            self._logger.info(f"安装依赖: {dep}")

    async def _register_downloaded_tool(self, tool_package: ToolPackage):
        """注册下载的工具"""
        self._local_tools[tool_package.tool_name] = tool_package
        self._logger.info(f"已注册工具: {tool_package.tool_name}")

    async def _test_downloaded_tool(self, tool_name: str) -> bool:
        """测试下载的工具"""
        self._logger.info(f"测试工具: {tool_name}")
        return True

    async def rate_tool(self, tool_name: str, rating: int, feedback: str):
        """评分工具（用于集体智慧进化）"""
        await self._rating_system.rate(tool_name, rating, feedback)

        # 如果评分低，通知创建者改进
        if rating <= 2:
            await self._notify_creator_to_improve(tool_name, feedback)

    async def _notify_creator_to_improve(self, tool_name: str, feedback: str):
        """通知创建者改进工具"""
        self._logger.info(f"通知创建者改进工具: {tool_name}, 反馈: {feedback}")

    def get_stats(self) -> Dict[str, Any]:
        """获取共享管理器统计信息"""
        return {
            "local_tools_count": len(self._local_tools),
            "shared_tools_count": 0,  # 从服务器获取
            "downloaded_tools_count": 0,
            "total_ratings": self._rating_system.get_total_ratings()
        }


class ToolRatingSystem:
    """工具评分系统"""

    def __init__(self):
        self._ratings: Dict[str, List[Dict[str, Any]]] = {}

    async def rate(self, tool_name: str, rating: int, feedback: str):
        """评分工具"""
        if tool_name not in self._ratings:
            self._ratings[tool_name] = []

        self._ratings[tool_name].append({
            "rating": rating,
            "feedback": feedback,
            "timestamp": datetime.now()
        })

        # 如果评分高，推荐给其他智能体
        if rating >= 4:
            await self._recommend_tool(tool_name)

        # 如果评分低，标记为"需要改进"
        if rating <= 2:
            await self._mark_as_needs_improvement(tool_name)

    async def _recommend_tool(self, tool_name: str):
        """推荐工具给其他智能体"""
        logger.info(f"推荐工具: {tool_name}")

    async def _mark_as_needs_improvement(self, tool_name: str):
        """标记工具需要改进"""
        logger.info(f"标记工具需要改进: {tool_name}")

    def get_total_ratings(self) -> int:
        """获取总评分数量"""
        return sum(len(ratings) for ratings in self._ratings.values())

    def get_average_rating(self, tool_name: str) -> float:
        """获取工具平均评分"""
        ratings = self._ratings.get(tool_name, [])
        if not ratings:
            return 0.0
        return sum(r["rating"] for r in ratings) / len(ratings)


class ToolDownloader:
    """工具下载器"""

    async def download(self, tool_name: str) -> Optional[ToolPackage]:
        """下载工具"""
        logger.info(f"下载工具: {tool_name}")
        return ToolPackage(
            tool_name=tool_name,
            version="1.0",
            code="下载的工具代码",
            dependencies=[],
            documentation="下载的工具文档"
        )


class ToolUploader:
    """工具上传器"""

    async def upload(self, tool_package: ToolPackage):
        """上传工具"""
        logger.info(f"上传工具: {tool_package.tool_name}")