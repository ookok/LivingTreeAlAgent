# LivingTree AI Agent - Client Main Entry

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6.QtWidgets import QApplication
from client.src.presentation.panels.home_page import HomePage


def main():
    app = QApplication(sys.argv)
    window = HomePage()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
