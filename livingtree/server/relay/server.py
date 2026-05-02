"""
LivingTree Relay Server Adapter
================================

精简版中继服务器适配器，封装 server/relay_server/ 的核心功能。
用于 livingtree/server/relay/ 的过渡迁移。
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)


def start_relay(host: str = "0.0.0.0", port: int = 8000):
    """启动中继服务器"""
    try:
        from server.relay_server.main import app
        import uvicorn

        print(f"[livingtree] Relay server starting on {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")
    except ImportError as e:
        print(f"[livingtree] Failed to start relay: {e}")
        print("[livingtree] Try: pip install -e ./server/relay_server")


def get_relay_app():
    """获取 FastAPI 应用实例"""
    try:
        from server.relay_server.main import app
        return app
    except ImportError:
        return None


__all__ = ["start_relay", "get_relay_app"]
