"""
WebRTC 视频通话与直播模块

整体架构:
- 信令服务: signaling_server.py (HTTP + WebSocket)
- ICE选路: ice_selector.py (智能三层选路)
- TURN客户端: turn_client.py (中继连接)
- 直播推流: live_broadcaster.py (录制/RTMP)
"""

from .signaling_server import SignalingServer, get_signaling_server, start_signaling_server
from .ice_selector import IceSelector, IceConfig, IceServer, NetworkTier, select_best_ice_config, get_ice_selector
from .turn_client import TurnClient, TurnCredentials, create_turn_credentials
from .live_broadcaster import LiveBroadcaster, StreamRouter, StreamConfig, StreamMode, get_stream_router

__all__ = [
    # 信令
    "SignalingServer",
    "get_signaling_server",
    "start_signaling_server",
    # ICE
    "IceSelector",
    "IceConfig",
    "IceServer",
    "NetworkTier",
    "select_best_ice_config",
    "get_ice_selector",
    # TURN
    "TurnClient",
    "TurnCredentials",
    "create_turn_credentials",
    # 直播
    "LiveBroadcaster",
    "StreamRouter",
    "StreamConfig",
    "StreamMode",
    "get_stream_router",
]
