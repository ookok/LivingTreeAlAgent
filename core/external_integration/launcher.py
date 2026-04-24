"""
快速启动脚本 - 一键启动所有集成服务
====================================

使用方式：
    python -m core.external_integration

或直接运行：
    python core/external_integration/launcher.py
"""

import sys
import argparse
import threading
import time

# 内部导入
from .api_server import ExternalAPIServer
from .clipboard_bridge import ClipboardBridge, start_clipboard_monitoring


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='AI OS 外部集成服务',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m core.external_integration              # 启动所有服务
  python -m core.external_integration --api-only    # 仅 API 服务
  python -m core.external_integration --clipboard-only  # 仅剪贴板监控
  python -m core.external_integration --port 8899  # 指定端口

快捷键说明:
  Ctrl+Shift+S  - 生成摘要
  Ctrl+Shift+P  - 润色
  Ctrl+Shift+T  - 翻译
  Ctrl+Shift+C  - 纠正错别字
  Ctrl+Shift+Q  - 知识库查询
        """
    )

    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='API 服务地址 (默认: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8898,
        help='API 服务端口 (默认: 8898)'
    )
    parser.add_argument(
        '--api-only',
        action='store_true',
        help='仅启动 API 服务'
    )
    parser.add_argument(
        '--clipboard-only',
        action='store_true',
        help='仅启动剪贴板监控'
    )
    parser.add_argument(
        '--api-key',
        default='',
        help='API 认证密钥'
    )
    parser.add_argument(
        '--poll-interval',
        type=float,
        default=0.5,
        help='剪贴板轮询间隔 (秒)'
    )

    return parser.parse_args()


def run_api_server(host: str, port: int, api_key: str):
    """运行 API 服务器"""
    server = ExternalAPIServer(
        host=host,
        port=port,
        api_keys={api_key: 'external'} if api_key else {},
    )

    try:
        print(f"\n🚀 启动 API 服务器: http://{host}:{port}")
        print("   按 Ctrl+C 停止\n")
        server.run()
    except KeyboardInterrupt:
        print("\n\nAPI 服务器已停止")


def run_clipboard_bridge(poll_interval: float):
    """运行剪贴板监控"""
    bridge = ClipboardBridge(poll_interval=poll_interval)

    # 注册回调
    def on_copy(entry):
        print(f"\n📋 检测到复制: {entry.char_count} 字符")
        print(f"   建议操作:")
        for s in entry.suggestions:
            print(f"   - {s.label} ({s.shortcut})")

    def on_result(action, result):
        print(f"\n✅ 已处理: {action.label}")
        print(f"   结果已复制到剪贴板")

    bridge.register_callback('on_copy', on_copy)
    bridge.register_callback('on_result', on_result)

    bridge.start()
    print("\n🔍 剪贴板监控已启动")
    print("   按 Ctrl+C 停止\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()
        print("\n\n剪贴板监控已停止")


def main():
    """主入口"""
    args = parse_args()

    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ██████╗  ██████╗ ██████╗ ████████╗ ██████╗  ██████╗   ║
║   ██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝██╔═══██╗██╔═══██╗  ║
║   ██████╔╝██║   ██║██████╔╝   ██║   ██║   ██║██║   ██║  ║
║   ██╔═══╝ ██║   ██║██╔══██╗   ██║   ██║   ██║██║   ██║  ║
║   ██║     ╚██████╔╝██║  ██║   ██║   ╚██████╔╝╚██████╔╝  ║
║   ╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝  ╚═════╝   ║
║                                                          ║
║   外部集成服务 v1.0                                        ║
║   让 WPS/Word/Excel 等应用调用 AI OS                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 根据参数启动服务
    if args.clipboard_only:
        # 仅剪贴板
        run_clipboard_bridge(args.poll_interval)

    elif args.api_only:
        # 仅 API
        run_api_server(args.host, args.port, args.api_key)

    else:
        # 全部启动
        # 启动 API 服务线程
        api_thread = threading.Thread(
            target=run_api_server,
            args=(args.host, args.port, args.api_key),
            daemon=True
        )
        api_thread.start()

        # 等待 API 服务启动
        time.sleep(1)

        # 启动剪贴板监控
        print("\n🔍 启动剪贴板监控...")
        run_clipboard_bridge(args.poll_interval)


if __name__ == '__main__':
    main()
