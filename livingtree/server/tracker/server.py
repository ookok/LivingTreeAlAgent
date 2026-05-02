"""
LivingTree Tracker Server Adapter
==================================

精简版 P2P 追踪器适配器，封装 server/tracker_server.py 的核心功能。
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)


def start_tracker(host: str = "0.0.0.0", port: int = 8765):
    """启动 P2P 追踪器"""
    import asyncio

    try:
        from server.tracker_server import TrackerServer

        async def _run():
            server = TrackerServer(host=host, port=port)
            print(f"[livingtree] Tracker server starting on {host}:{port}")
            await server.start()
            await asyncio.Event().wait()

        asyncio.run(_run())
    except ImportError as e:
        print(f"[livingtree] Failed to start tracker: {e}")


def get_tracker():
    """获取 Tracker 实例"""
    try:
        from server.tracker_server import TrackerServer
        return TrackerServer()
    except ImportError:
        return None


__all__ = ["start_tracker", "get_tracker"]
