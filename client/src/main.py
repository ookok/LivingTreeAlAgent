"""
Hermes Desktop V2.0 - 客户端入口

生命主干 (The Trunk) - 一切功能的承载主体
"""

import sys
import os
from pathlib import Path

# 确保项目根目录在 Python 路径中
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTranslator, QLocale
from PyQt6.QtGui import QIcon, QFont

# 导入客户端组件
from client.src.presentation.main_window import MainWindow
from client.src.infrastructure.config import load_config, DEFAULT_CONFIG, save_config
from client.src.presentation.theme import DARK_QSS

# 导入首次运行引导
try:
    from ui.welcome_wizard import WelcomeWizard
    _has_wizard = True
except ImportError:
    _has_wizard = False


def setup_app() -> QApplication:
    """创建并配置 Qt 应用"""
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)
    app.setApplicationName("Hermes Desktop")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("HermesAI")

    # 高 DPI 支持
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    # 默认字体
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    return app


def check_first_run() -> bool:
    """
    检查是否首次运行

    Returns:
        True: 需要显示主窗口
        False: 应该退出程序
    """
    from core.first_run_config import get_first_run_config

    first_run_mgr = get_first_run_config()

    if not first_run_mgr.is_first_run():
        if first_run_mgr.is_wizard_completed():
            return True
        return True

    return True


def run_wizard(app: QApplication) -> tuple[bool, bool]:
    """
    运行首次启动引导向导

    Returns:
        (should_continue, config_applied)
    """
    from core.first_run_config import get_first_run_config

    first_run_mgr = get_first_run_config()

    if not first_run_mgr.is_first_run() and first_run_mgr.is_wizard_completed():
        return True, True

    if not _has_wizard:
        return True, True

    wizard = WelcomeWizard()
    wizard.setStyleSheet(DARK_QSS)

    result = wizard.exec()

    if result:
        return True, True
    else:
        reply = QMessageBox.question(
            None,
            "取消引导",
            "您取消了配置向导。\n\n"
            "• 点击「跳过」使用默认配置快速启动\n"
            "• 点击「退出」关闭程序，稍后重新配置",
            QMessageBox.StandardButton.Skip,
            QMessageBox.StandardButton.Close
        )

        if reply == QMessageBox.StandardButton.Skip:
            save_config(DEFAULT_CONFIG)
            first_run_mgr.mark_wizard_completed()
            return True, True
        else:
            return False, False


def main():
    """主入口"""
    # 启动 GUI
    app = setup_app()

    # 应用主题
    app.setStyleSheet(DARK_QSS)

    # 检查首次运行
    try:
        from core.first_run_config import get_first_run_config
        first_run_mgr = get_first_run_config()

        if first_run_mgr.is_first_run() or not first_run_mgr.is_wizard_completed():
            should_continue, _ = run_wizard(app)

            if not should_continue:
                sys.exit(0)
    except Exception:
        pass

    # 加载配置
    cfg = load_config()

    # 创建主窗口
    window = MainWindow(cfg)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
