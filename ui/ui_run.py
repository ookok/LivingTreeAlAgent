#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LivingTree AI Agent - UI Entry Point

Starts the LivingTree AI Agent with PyDracula UI framework.
Supports both light and dark themes with easy switching.

Usage:
    python ui_run.py              # Start with default theme (light)
    python ui_run.py --dark       # Start with dark theme
"""

import sys
import os
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("Error: Neither PySide6 nor PyQt6 is installed.")
        print("Please install one of them:")
        print("  pip install PySide6")
        print("  pip install PyQt6")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="LivingTree AI Agent - PyDracula UI")
    parser.add_argument(
        "--dark",
        action="store_true",
        help="Start with dark theme (default: light)"
    )
    args = parser.parse_args()

    # Set initial theme if specified
    if args.dark:
        os.environ["LIVINGTREE_THEME"] = "dark"
    else:
        os.environ["LIVINGTREE_THEME"] = "light"

    # Start application
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("LivingTree AI Agent")
    app.setOrganizationName("LivingTree")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
