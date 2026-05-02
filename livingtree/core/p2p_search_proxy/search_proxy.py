"""
P2P 搜索代理服务

核心搜索引擎代理实现
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .models import (
    SearchTask, SearchResult, SearchEngineType,
    SearchResultStatus, P2PSearchConfig, SearchRouteDecision
)
from .capability_registry import CapabilityRegistry
from ..agent_reach import AgentReachClient, SearchEngine

logger = logging.getLogger(__name__)


class P2PSearchProxy:
    """
    P2P 搜索代理服务

    核心功能：
    1. 搜索请求路由分发（直连/P2P/Relay）
    2. 外网节点能力注册与发现
    3. Agent-Reach 远程调用封装
    4. 结果缓存与统计
    """

    def __init__(
        self,
        node_id: str,
        config: Optional[P2PSearchConfig] = None,
        data_dir: Optional[str] = None
    ):
        self.node_id = node_id
        self.config = config or P2PSearchConfig()

        # 数据目录
        self.data_dir = Path(data_dir or f"~/.hermes-p2p-search/{node_id}")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 能力注册表
        self.capability_registry = CapabilityRegistry(self.config)

        # Agent-Reach 本地实例
        self.agent_reach: Optional[AgentReachClient] = None

        # 任务历史缓存
        self._task_cache: dict[str, SearchTask] = {}
        self._cache_ttl = 300  # 5分钟缓存

        # 统计
        self.stats = {
            "total_requests": 0,
            "direct_success": 0,
            "p2p_success": 0,
            "fallback_count": 0,
            "error_count": 0,
        }

        self._running = False

    async def start(self):
        """启动搜索代理服务"""
        logger.info(f"Starting P2P Search Proxy for node {self.node_id}...")

        # 启动能力注册表
        await self.capability_registry.start()

        # 初始化 Agent-Reach
        try:
            self.agent_reach = AgentReachClient()
            agent_reach_ok = await asyncio.to_thread(self.agent_reach.check_installation)
            if agent_reach_ok:
                logger.info("Agent-Reach is available")
            else:
                logger.warning("Agent-Reach not installed")
        except Exception as e:
            logger.warning(f"Agent-Reach initialization failed: {e}")
            self.agent_reach = None

        # 广告本地能力
        if self.config.advertise_external_net:
            await self._advertise_capabilities()

        self._running = True
        logger.info(f"P2P Search Proxy started successfully")

    async def stop(self):
        """停止搜索代理服务"""
        logger.info(f"Stopping P2P Search Proxy...")
        self._running = False
        await self.capability_registry.stop()
        logger.info(f"P2P Search Proxy stopped")

    # ==================== 搜索接口 ====================

    async def search(
        self,
        query: str,
        engine: SearchEngineType = SearchEngineType.DUCKDUCKGO,
        max_results: int = 5,
        use_p2p: bool = False
    ) -> SearchTask:
        """
        执行搜索请求

        Args:
            query: 搜索关键词
            engine: 搜索引擎
            max_results: 最大结果数
            use_p2p: 是否强制使用P2P

        Returns:
            SearchTask: 搜索任务（包含结果）
        """
        task = SearchTask(
            query=query,
            engine=engine,
            max_results=max_results,
            use_p2p=use_p2p,
            source_node=self.node_id,
        )

        self.stats["total_requests"] += 1
        start_time = time.time()

        # 检查缓存
        cache_key = self._get_cache_key(query, engine)
        if not use_p2p and cache_key in self._task_cache:
            cached_task = self._task_cache[cache_key]
            if time.time() - cached_task.created_at < self._cache_ttl:
                logger.debug(f"Cache hit for query: {query[:30]}...")
                return cached_task

        # 获取路由决策
        route = await self.capability_registry.get_best_route(task)

        try:
            if route.route_type == "direct":
                task.route_type = "direct"
                await self._search_direct(task)
                self.stats["direct_success"] += 1

            elif route.route_type == "p2p":
                task.route_type = "p2p"
                task.target_node = route.target_node
                await self._search_via_p2p(task)
                self.stats["p2p_success"] += 1

            elif route.route_type == "direct" and task.status == SearchResultStatus.BLOCKED:
                # 直连被阻，尝试P2P
                logger.info("Direct search blocked, trying P2P...")
                self.stats["fallback_count"] += 1
                task.route_type = "p2p"
                await self._search_via_p2p(task)

            else:
                task.status = SearchResultStatus.ERROR
                task.error = f"Unknown route type: {route.route_type}"

        except Exception as e:
            logger.error(f"Search error: {e}")
            task.status = SearchResultStatus.ERROR
            task.error = str(e)
            self.stats["error_count"] += 1

        finally:
            task.latency_ms = (time.time() - start_time) * 1000
            self._task_cache[cache_key] = task

        return task

    async def _search_direct(self, task: SearchTask):
        """直连搜索（本地执行）"""
        if not self.agent_reach:
            task.status = SearchResultStatus.ERROR
            task.error = "Agent-Reach not available"
            return

        try:
            # 调用 Agent-Reach
            results = await asyncio.to_thread(
                self.agent_reach.search,
                query=task.query,
                engine=task.engine.value,
                max_results=task.max_results
            )

            task.results = [
                SearchResult(
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                    url=r.get("url", ""),
                    platform=r.get("platform", task.engine.value),
                    score=r.get("score", 0.0)
                )
                for r in results
            ]
            task.status = SearchResultStatus.SUCCESS

        except Exception as e:
            # 检测是否被封锁
            error_str = str(e).lower()
            if any(kw in error_str for kw in ["blocked", "forbidden", "403", "access denied"]):
                task.status = SearchResultStatus.BLOCKED
            else:
                task.status = SearchResultStatus.ERROR
            task.error = str(e)

    async def _search_via_p2p(self, task: SearchTask):
        """
        通过 P2P 节点执行搜索

        Args:
            task: 搜索任务
        """
        if not task.target_node:
            task.status = SearchResultStatus.NO_PEER
            task.error = "No target P2P node specified"
            return

        try:
            # 发送搜索请求到目标节点
            request_data = {
                "action": "search",
                "query": task.query,
                "engine": task.engine.value,
                "max_results": task.max_results,
                "task_id": task.task_id,
            }

            # 通过中继服务器发送
            response = await self._send_to_peer(
                node_id=task.target_node,
                data=request_data,
                timeout=self.config.p2p_timeout
            )

            if response and response.get("status") == "success":
                task.results = [
                    SearchResult(**r) for r in response.get("results", [])
                ]
                task.status = SearchResultStatus.SUCCESS

                # 更新节点统计
                await self.capability_registry.update_peer_stats(
                    task.target_node, success=True, latency_ms=task.latency_ms
                )
            else:
                task.status = SearchResultStatus.ERROR
                task.error = response.get("error", "Unknown error")
                await self.capability_registry.update_peer_stats(
                    task.target_node, success=False
                )

        except asyncio.TimeoutError:
            task.status = SearchResultStatus.TIMEOUT
            task.error = "P2P search timeout"
            await self.capability_registry.update_peer_stats(
                task.target_node, success=False
            )
        except Exception as e:
            task.status = SearchResultStatus.ERROR
            task.error = str(e)
            await self.capability_registry.update_peer_stats(
                task.target_node, success=False
            )

    async def _send_to_peer(
        self,
        node_id: str,
        data: dict,
        timeout: int = 15
    ) -> Optional[dict]:
        """
        通过中继服务器发送消息到对等节点

        Args:
            node_id: 目标节点ID
            data: 消息数据
            timeout: 超时时间

        Returns:
            响应数据
        """
        # 尝试使用已连接的中继客户端
        # 这里需要集成现有的 relay_client

        # 简化实现：如果配置了中继服务器，使用它
        if self.config.relay_servers:
            try:
                relay_host, relay_port = self.config.relay_servers[0].split(":")
                relay_port = int(relay_port)

                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(relay_host, relay_port),
                    timeout=5
                )

                # 发送请求
                request = json.dumps({
                    "type": "search_proxy",
                    "source": self.node_id,
                    "target": node_id,
                    "payload": data
                }).encode("utf-8")

                writer.write(len(request).to_bytes(4, "big"))
                writer.write(request)
                await writer.drain()

                # 接收响应
                response_len_bytes = await asyncio.wait_for(
                    reader.read(4), timeout=timeout
                )
                if response_len_bytes:
                    response_len = int.from_bytes(response_len_bytes, "big")
                    response_data = await asyncio.wait_for(
                        reader.read(response_len), timeout=timeout
                    )

                    writer.close()
                    await writer.wait_closed()

                    return json.loads(response_data.decode("utf-8"))

            except Exception as e:
                logger.error(f"Failed to send via relay: {e}")

        # 如果中继失败，尝试P2P直连
        return await self._send_direct(node_id, data, timeout)

    async def _send_direct(
        self,
        node_id: str,
        data: dict,
        timeout: int = 15
    ) -> Optional[dict]:
        """尝试直接P2P连接发送"""
        # 这里需要集成 p2p_node 的连接能力
        # 简化实现：返回错误
        logger.warning(f"Direct P2P not implemented, node: {node_id}")
        return {"status": "error", "error": "Direct P2P not available"}

    # ==================== 远程搜索处理（外网节点调用） ====================

    async def handle_remote_search(self, task_data: dict) -> dict:
        """
        处理来自其他节点的远程搜索请求

        此方法在外网节点上被调用

        Args:
            task_data: 任务数据

        Returns:
            搜索结果
        """
        task = SearchTask(
            task_id=task_data.get("task_id", uuid.uuid4().hex[:12]),
            query=task_data.get("query", ""),
            engine=SearchEngineType(task_data.get("engine", "duckduckgo")),
            max_results=task_data.get("max_results", 5),
        )

        await self._search_direct(task)

        return {
            "status": "success" if task.status == SearchResultStatus.SUCCESS else "error",
            "task_id": task.task_id,
            "results": [r.to_dict() for r in task.results],
            "error": task.error,
            "latency_ms": task.latency_ms,
        }

    # ==================== 能力广告 ====================

    async def _advertise_capabilities(self):
        """广告本地节点能力"""
        capabilities = PeerCapability.NONE.value

        if self.config.advertise_external_net:
            capabilities |= PeerCapability.HAS_EXTERNAL_NET.value

        if self.agent_reach:
            capabilities |= PeerCapability.HAS_SEARCH_TOOLS.value

        # 通过中继服务器广播能力
        if self.config.relay_servers:
            try:
                relay_host, relay_port = self.config.relay_servers[0].split(":")
                await self._broadcast_capability(
                    relay_host, int(relay_port), capabilities
                )
            except Exception as e:
                logger.error(f"Failed to advertise capabilities: {e}")

    async def _broadcast_capability(
        self,
        relay_host: str,
        relay_port: int,
        capabilities: int
    ):
        """广播节点能力到中继服务器"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(relay_host, relay_port),
                timeout=5
            )

            message = json.dumps({
                "type": "capability_announce",
                "node_id": self.node_id,
                "capabilities": capabilities,
                "timestamp": time.time()
            }).encode("utf-8")

            writer.write(len(message).to_bytes(4, "big"))
            writer.write(message)
            await writer.drain()

            writer.close()
            await writer.wait_closed()

            logger.info(f"Advertised capabilities: {capabilities}")

        except Exception as e:
            logger.error(f"Failed to broadcast capability: {e}")

    # ==================== 工具方法 ====================

    def _get_cache_key(self, query: str, engine: SearchEngineType) -> str:
        """生成缓存键"""
        return f"{engine.value}:{query[:50]}"

    def get_stats(self) -> dict:
        """获取统计信息"""
        total = self.stats["total_requests"]
        success = self.stats["direct_success"] + self.stats["p2p_success"]

        return {
            **self.stats,
            "peer_count": self.capability_registry.get_peer_count(),
            "cache_size": len(self._task_cache),
            "success_rate": success / total if total > 0 else 0,
        }

    async def register_external_peer(self, node_id: str, capabilities: int, latency_ms: float = 0.0):
        """
        注册外部对等节点（当收到能力广播时调用）

        Args:
            node_id: 节点ID
            capabilities: 能力位掩码
            latency_ms: 延迟
        """
        from .models import PeerSearchCapability

        cap = PeerSearchCapability(
            node_id=node_id,
            capabilities=capabilities,
            latency_ms=latency_ms
        )
        await self.capability_registry.register_peer(cap)
