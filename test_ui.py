#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LivingTree UI Framework - Test Script

Tests the PyDracula-based UI framework.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        print("  PySide6: OK")
        qt_binding = "PySide6"
    except ImportError:
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt
            print("  PyQt6: OK")
            qt_binding = "PyQt6"
        except ImportError:
            print("  ERROR: Neither PySide6 nor PyQt6 is installed!")
            return False

    # Test UI modules
    try:
        from ui.modules import Settings, UIFunctions
        print("  ui.modules: OK")
    except ImportError as e:
        print(f"  ui.modules: FAILED - {e}")
        return False

    try:
        from ui.theme_manager import ThemeManager, get_theme_manager
        print("  ui.theme_manager: OK")
    except ImportError as e:
        print(f"  ui.theme_manager: FAILED - {e}")
        return False

    try:
        from ui.main_window import MainWindow, Ui_MainWindow
        print("  ui.main_window: OK")
    except ImportError as e:
        print(f"  ui.main_window: FAILED - {e}")
        return False

    return True


def test_theme_manager():
    """Test theme manager"""
    print("\nTesting ThemeManager...")

    from ui.theme_manager import get_theme_manager

    tm = get_theme_manager()

    # Test singleton
    tm2 = get_theme_manager()
    assert tm is tm2, "ThemeManager should be singleton"
    print("  Singleton: OK")

    # Test default theme (light)
    assert tm.is_light == True, "Default theme should be light"
    print("  Default theme (light): OK")

    # Test toggle
    tm.toggle_theme()
    assert tm.is_dark == True, "After toggle, should be dark"
    print("  Toggle theme: OK")

    # Test get theme file
    theme_file = tm.get_theme_file()
    assert os.path.exists(theme_file), f"Theme file should exist: {theme_file}"
    print(f"  Theme file: {theme_file}")

    # Reset to light
    tm.set_theme(True)
    print("  Reset to light: OK")

    return True


def test_theme_files():
    """Test that theme files exist and are readable"""
    print("\nTesting theme files...")

    from ui.theme_manager import get_theme_manager

    tm = get_theme_manager()

    # Light theme
    light_file = tm.get_theme_file()
    with open(light_file, 'r', encoding='utf-8') as f:
        light_content = f.read()
    assert len(light_content) > 0, "Light theme file should not be empty"
    print(f"  Light theme: {len(light_content)} bytes")

    # Dark theme
    tm.set_theme(False)
    dark_file = tm.get_theme_file()
    with open(dark_file, 'r', encoding='utf-8') as f:
        dark_content = f.read()
    assert len(dark_content) > 0, "Dark theme file should not be empty"
    print(f"  Dark theme: {len(dark_content)} bytes")

    # Reset
    tm.set_theme(True)

    return True


def test_qt_application():
    """Test Qt application creation (without showing window)"""
    print("\nTesting Qt application...")

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    print("  QApplication: OK")

    return True


def run_tests():
    """Run all tests"""
    print("=" * 50)
    print("LivingTree UI Framework - Test Suite")
    print("=" * 50)

    all_passed = True

    # Test imports
    if not test_imports():
        all_passed = False

    # Test theme manager
    if not test_theme_manager():
        all_passed = False

    # Test theme files
    if not test_theme_files():
        all_passed = False

    # Test Qt
    if not test_qt_application():
        all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("All tests passed!")
        print("\nTo run the UI:")
        print("  python ui/ui_run.py")
        print("  python ui/ui_run.py --dark")
    else:
        print("Some tests failed!")
    print("=" * 50)

    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
