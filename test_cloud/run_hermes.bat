@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d %~dp0
python -c "
import sys
sys.path.insert(0, '.')
from ui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication
from core.config import load_config

app = QApplication(sys.argv)
cfg = load_config()
window = MainWindow(cfg)
window.show()
sys.exit(app.exec())
"
