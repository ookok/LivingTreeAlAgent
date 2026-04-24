"""
AI OS 外部集成服务 - Office/WPS 无侵入式调用方案
=============================================

设计原则：最小入侵、零配置、多终端覆盖

三层架构：
1. API Layer    - REST API 暴露 AI OS 能力
2. Agent Layer  - 智能代理处理来自外部的请求
3. Bridge Layer - 多种接入方式（剪贴板、文件、快捷键）

接入方式优先级：
1. 剪贴板监控（最透明，用户无感知）
2. REST API（最通用，程序员友好）
3. Python 脚本（微软官方支持，WPS 也支持）
4. Office Add-in（最原生，但开发成本高）
"""

from .api_server import ExternalAPIServer
from .clipboard_bridge import ClipboardBridge
from .intent_detector import IntentDetector

__all__ = [
    'ExternalAPIServer',
    'ClipboardBridge',
    'IntentDetector',
    'start_external_service',
]


def start_external_service(host: str = "127.0.0.1", port: int = 8898):
    """启动外部集成服务"""
    import asyncio
    from .api_server import run_server

    print(f"""
╔══════════════════════════════════════════════════════════╗
║           AI OS 外部集成服务 v1.0                         ║
╠══════════════════════════════════════════════════════════╣
║  📡 REST API:  http://{host}:{port}/api/v1/             ║
║  📋 剪贴板:    已启用（监控选中内容）                      ║
║  📝 Office:    支持 Word/WPS/Excel                       ║
╠══════════════════════════════════════════════════════════╣
║  示例调用:                                                ║
║  curl -X POST http://{host}:{port}/api/v1/query \\      ║
║    -H "Content-Type: application/json" \\                 ║
║    -d '{{"text": "分析这段话", "context": "word"}}'       ║
╚══════════════════════════════════════════════════════════╝
    """)

    asyncio.run(run_server(host, port))
