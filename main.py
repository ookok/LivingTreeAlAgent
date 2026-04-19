"""
LivingTreeAI - 生命之树 AI 统一入口

支持启动:
- 客户端 (桌面应用)
- 服务端 (中继服务器)
- 追踪服务器
"""

import sys
import os
import argparse
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))


def run_client():
    """启动桌面客户端"""
    print(">> 启动 LivingTreeAI 客户端...")
    print("   生命之树正在苏醒，根系伸向远方...")

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 加载主题
    theme_path = _root / "client" / "src" / "presentation" / "theme.py"
    if theme_path.exists():
        try:
            from ui.theme import DARK_QSS
            app.setStyleSheet(DARK_QSS)
        except ImportError:
            pass

    from client.src.presentation.main_window import MainWindow
    from client.src.infrastructure.config import load_config

    cfg = load_config()
    window = MainWindow(cfg)
    window.show()

    sys.exit(app.exec())


def run_relay_server():
    """启动中继服务器"""
    print("🌐 启动 LivingTreeAI 中继服务器...")
    print("   水源泉眼开启，汇聚信息之流...")

    import uvicorn
    from server.relay_server.main import app

    uvicorn.run(app, host="0.0.0.0", port=8766, log_level="info")


def run_tracker_server():
    """启动追踪服务器"""
    print("📊 启动 LivingTreeAI 追踪服务器...")

    from server.tracker.tracker_server import run_tracker
    run_tracker()


def main():
    """统一入口"""
    parser = argparse.ArgumentParser(
        description="LivingTreeAI - 生命之树 AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py client          # 启动桌面客户端
  python main.py relay           # 启动中继服务器
  python main.py tracker         # 启动追踪服务器
  python main.py all             # 启动所有服务
        """
    )

    parser.add_argument(
        "mode",
        choices=["client", "relay", "tracker", "all"],
        nargs="?",
        default="client",
        help="启动模式 (默认: client)"
    )
    parser.add_argument("--port", type=int, default=8766, help="服务器端口")
    parser.add_argument("--host", default="0.0.0.0", help="服务器地址")

    args = parser.parse_args()

    if args.mode == "client":
        run_client()
    elif args.mode == "relay":
        run_relay_server()
    elif args.mode == "tracker":
        run_tracker_server()
    elif args.mode == "all":
        print("启动所有服务...")
        import threading

        # 启动追踪服务器
        tracker_thread = threading.Thread(target=run_tracker_server, daemon=True)
        tracker_thread.start()
        print("✅ 追踪服务器已启动")

        # 启动中继服务器
        relay_thread = threading.Thread(target=run_relay_server, daemon=True)
        relay_thread.start()
        print("✅ 中继服务器已启动")

        # 启动客户端
        print("✅ 准备启动客户端...")
        run_client()


if __name__ == "__main__":
    main()
