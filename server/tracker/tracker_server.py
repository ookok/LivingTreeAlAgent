"""
DeCommerce 云端Tracker服务器
Cloud Tracker Server

功能:
- 商品/服务目录维护
- 卖家注册与心跳
- 信令转发 (SDP Offer/Answer/ICE)
- 会话撮合
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, Optional, List
from aiohttp import web
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrackerServer:
    """
    云端Tracker服务器

    运行在你的Windows公网服务器上
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port

        # 数据存储
        self._sellers: Dict[str, Dict[str, Any]] = {}  # seller_id -> seller info
        self._listings: Dict[str, Dict[str, Any]] = {}  # listing_id -> listing info
        self._sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> session info

        # WebSocket连接
        self._ws_connections: Dict[str, web.WebSocketResponse] = {}  # seller_id -> ws

        # 信令队列
        self._signal_queues: Dict[str, asyncio.Queue] = {}  # session_id -> queue

        # 应用
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None

    async def start(self) -> None:
        """启动服务器"""
        self._app = web.Application()

        # 路由
        self._setup_routes()

        # 启动
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

        logger.info(f"[TrackerServer] Started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """停止服务器"""
        if self._runner:
            await self._runner.cleanup()
        logger.info(f"[TrackerServer] Stopped")

    def _setup_routes(self) -> None:
        """设置路由"""
        app = self._app

        # 卖家相关
        app.router.add_post("/api/sellers/register", self.handle_seller_register)
        app.router.add_post("/api/sellers/unregister", self.handle_seller_unregister)
        app.router.add_get("/api/sellers", self.handle_sellers_list)
        app.router.add_get("/api/sellers/{seller_id}", self.handle_seller_info)

        # 商品相关
        app.router.add_post("/api/listings/register", self.handle_listing_register)
        app.router.add_post("/api/listings/unregister", self.handle_listing_unregister)
        app.router.add_get("/api/listings", self.handle_listings_list)
        app.router.add_get("/api/listings/{listing_id}", self.handle_listing_info)

        # 心跳
        app.router.add_post("/api/heartbeat", self.handle_heartbeat)

        # 信令
        app.router.add_post("/api/signal", self.handle_signal)
        app.router.add_post("/api/signal/ice", self.handle_ice_candidate)

        # 会话
        app.router.add_post("/api/sessions/create", self.handle_session_create)
        app.router.add_get("/api/sessions/{session_id}", self.handle_session_info)

    # ==================== 卖家管理 ====================

    async def handle_seller_register(self, request: web.Request) -> web.Response:
        """注册卖家"""
        try:
            data = await request.json()
            seller = data.get("seller")
            endpoint = data.get("endpoint")

            if not seller:
                return web.json_response({"error": "No seller data"}, status=400)

            seller_id = seller.get("id")
            if not seller_id:
                return web.json_response({"error": "No seller ID"}, status=400)

            seller["registered_at"] = time.time()
            seller["last_heartbeat"] = time.time()
            seller["endpoint"] = endpoint

            self._sellers[seller_id] = seller

            logger.info(f"[TrackerServer] Registered seller: {seller_id}")

            return web.json_response({"status": "ok", "seller_id": seller_id})

        except Exception as e:
            logger.error(f"[TrackerServer] Seller register error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_seller_unregister(self, request: web.Request) -> web.Response:
        """注销卖家"""
        try:
            data = await request.json()
            seller_id = data.get("seller_id")

            if seller_id in self._sellers:
                del self._sellers[seller_id]
                logger.info(f"[TrackerServer] Unregistered seller: {seller_id}")

            return web.json_response({"status": "ok"})

        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_sellers_list(self, request: web.Request) -> web.Response:
        """获取卖家列表"""
        online_only = request.query.get("online") == "true"

        sellers = []
        for seller in self._sellers.values():
            if online_only:
                # 检查心跳
                last_hb = seller.get("last_heartbeat", 0)
                if time.time() - last_hb > 60:  # 60秒内有心跳视为在线
                    continue

            sellers.append(seller)

        return web.json_response(sellers)

    async def handle_seller_info(self, request: web.Request) -> web.Response:
        """获取卖家信息"""
        seller_id = request.match_info["seller_id"]

        seller = self._sellers.get(seller_id)
        if not seller:
            return web.json_response({"error": "Not found"}, status=404)

        return web.json_response(seller)

    # ==================== 商品管理 ====================

    async def handle_listing_register(self, request: web.Request) -> web.Response:
        """注册商品"""
        try:
            data = await request.json()

            listing_id = data.get("id")
            if not listing_id:
                listing_id = str(uuid.uuid4())[:12]
                data["id"] = listing_id

            data["registered_at"] = time.time()
            data["updated_at"] = time.time()

            self._listings[listing_id] = data

            logger.info(f"[TrackerServer] Registered listing: {listing_id}")

            return web.json_response({"status": "ok", "listing_id": listing_id})

        except Exception as e:
            logger.error(f"[TrackerServer] Listing register error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_listing_unregister(self, request: web.Request) -> web.Response:
        """注销商品"""
        try:
            data = await request.json()
            listing_id = data.get("listing_id")

            if listing_id in self._listings:
                del self._listings[listing_id]
                logger.info(f"[TrackerServer] Unregistered listing: {listing_id}")

            return web.json_response({"status": "ok"})

        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_listings_list(self, request: web.Request) -> web.Response:
        """获取商品列表"""
        # 过滤参数
        seller_id = request.query.get("seller_id")
        service_type = request.query.get("service_type")
        live_only = request.query.get("live_only") == "true"

        listings = []
        for listing in self._listings.values():
            # 状态过滤
            if listing.get("status") != "online":
                continue

            # 卖家过滤
            if seller_id and listing.get("seller_id") != seller_id:
                continue

            # 类型过滤
            if service_type and listing.get("service_type") != service_type:
                continue

            # 实时可用过滤
            if live_only and not listing.get("is_live_available"):
                continue

            listings.append(listing)

        # 按更新时间排序
        listings.sort(key=lambda x: x.get("updated_at", 0), reverse=True)

        return web.json_response(listings)

    async def handle_listing_info(self, request: web.Request) -> web.Response:
        """获取商品信息"""
        listing_id = request.match_info["listing_id"]

        listing = self._listings.get(listing_id)
        if not listing:
            return web.json_response({"error": "Not found"}, status=404)

        return web.json_response(listing)

    # ==================== 心跳 ====================

    async def handle_heartbeat(self, request: web.Request) -> web.Response:
        """处理心跳"""
        try:
            data = await request.json()
            seller_id = data.get("seller_id")

            if seller_id in self._sellers:
                self._sellers[seller_id]["last_heartbeat"] = time.time()
                self._sellers[seller_id]["active_sessions"] = data.get("active_sessions", 0)

            return web.json_response({"status": "ok"})

        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ==================== 信令 ====================

    async def handle_signal(self, request: web.Request) -> web.Response:
        """处理信令 (Offer/Answer)"""
        try:
            data = await request.json()
            msg_type = data.get("type")
            session_id = data.get("session_id")
            from_user = data.get("from")
            to_user = data.get("to")
            sdp = data.get("sdp")

            # 找到目标卖家的WebSocket连接
            target_ws = self._ws_connections.get(to_user)
            if target_ws:
                await target_ws.send_json({
                    "type": msg_type,
                    "session_id": session_id,
                    "from": from_user,
                    "sdp": sdp,
                })
            else:
                # 存入队列供后续获取
                if session_id not in self._signal_queues:
                    self._signal_queues[session_id] = asyncio.Queue()
                await self._signal_queues[session_id].put({
                    "type": msg_type,
                    "from": from_user,
                    "sdp": sdp,
                })

            return web.json_response({"status": "ok"})

        except Exception as e:
            logger.error(f"[TrackerServer] Signal error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_ice_candidate(self, request: web.Request) -> web.Response:
        """处理ICE候选"""
        try:
            data = await request.json()
            session_id = data.get("session_id")
            from_user = data.get("from")
            to_user = data.get("to")
            candidate = data.get("candidate")

            # 转发给目标
            target_ws = self._ws_connections.get(to_user)
            if target_ws:
                await target_ws.send_json({
                    "type": "ice_candidate",
                    "session_id": session_id,
                    "from": from_user,
                    "candidate": candidate,
                })

            return web.json_response({"status": "ok"})

        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ==================== 会话 ====================

    async def handle_session_create(self, request: web.Request) -> web.Response:
        """创建会话"""
        try:
            data = await request.json()
            listing_id = data.get("listing_id")
            buyer_id = data.get("buyer_id")

            listing = self._listings.get(listing_id)
            if not listing:
                return web.json_response({"error": "Listing not found"}, status=404)

            # 创建会话
            session_id = str(uuid.uuid4())[:12]
            session = {
                "id": session_id,
                "listing_id": listing_id,
                "seller_id": listing.get("seller_id"),
                "buyer_id": buyer_id,
                "status": "pending",
                "created_at": time.time(),
            }

            self._sessions[session_id] = session

            return web.json_response({
                "status": "ok",
                "session_id": session_id,
                "listing": listing,
            })

        except Exception as e:
            logger.error(f"[TrackerServer] Session create error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_session_info(self, request: web.Request) -> web.Response:
        """获取会话信息"""
        session_id = request.match_info["session_id"]

        session = self._sessions.get(session_id)
        if not session:
            return web.json_response({"error": "Not found"}, status=404)

        return web.json_response(session)

    # ==================== WebSocket ====================

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket连接 (供卖家使用)"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        seller_id = None

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")

                    if msg_type == "register":
                        # 卖家注册WebSocket
                        seller_id = data.get("seller_id")
                        self._ws_connections[seller_id] = ws
                        await ws.send_json({"type": "registered", "seller_id": seller_id})

                    elif msg_type == "offer":
                        # 转发Offer
                        to_user = data.get("to")
                        target_ws = self._ws_connections.get(to_user)
                        if target_ws:
                            await target_ws.send_json({
                                "type": "offer",
                                "session_id": data.get("session_id"),
                                "sdp": data.get("sdp"),
                            })

                    elif msg_type == "answer":
                        # 转发Answer
                        to_user = data.get("to")
                        target_ws = self._ws_connections.get(to_user)
                        if target_ws:
                            await target_ws.send_json({
                                "type": "answer",
                                "session_id": data.get("session_id"),
                                "sdp": data.get("sdp"),
                            })

                    elif msg_type == "ice_candidate":
                        # 转发ICE
                        to_user = data.get("to")
                        target_ws = self._ws_connections.get(to_user)
                        if target_ws:
                            await target_ws.send_json({
                                "type": "ice_candidate",
                                "candidate": data.get("candidate"),
                            })

        finally:
            if seller_id and seller_id in self._ws_connections:
                del self._ws_connections[seller_id]

        return ws

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取服务器统计"""
        return {
            "sellers": len(self._sellers),
            "listings": len(self._listings),
            "sessions": len(self._sessions),
            "ws_connections": len(self._ws_connections),
        }


# 全局服务器实例
_server: Optional[TrackerServer] = None


async def get_tracker_server(host: str = "0.0.0.0", port: int = 8765) -> TrackerServer:
    """获取Tracker服务器实例"""
    global _server
    if _server is None:
        _server = TrackerServer(host, port)
        await _server.start()
    return _server


async def stop_tracker_server() -> None:
    """停止Tracker服务器"""
    global _server
    if _server:
        await _server.stop()
        _server = None


# CLI入口
if __name__ == "__main__":
    async def main():
        server = await get_tracker_server("0.0.0.0", 8765)
        print(f"Tracker Server running on http://0.0.0.0:8765")
        print(f"Press Ctrl+C to stop")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            await stop_tracker_server()

    asyncio.run(main())