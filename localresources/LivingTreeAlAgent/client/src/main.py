# LivingTree AI Agent - Client Main Entry

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.config import load_config


def main():
    app = QApplication(sys.argv)

    # Load configuration
    config = load_config()

    # Create and show main window
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()