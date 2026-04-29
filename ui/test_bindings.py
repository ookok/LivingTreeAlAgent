# -*- coding: utf-8 -*-
"""
Test script for UI bindings
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test all bindings can be imported"""
    print("Testing bindings import...")

    try:
        from ui.bindings import ChatBinding, IDEBinding, SettingsBinding
        print("  ✓ ChatBinding imported")
        print("  ✓ IDEBinding imported")
        print("  ✓ SettingsBinding imported")
        return True
    except Exception as e:
        print(f"  ✗ Import error: {e}")
        return False

def test_chat_binding():
    """Test ChatBinding"""
    print("\nTesting ChatBinding...")

    try:
        from ui.bindings.chat_binding import ChatBinding

        binding = ChatBinding()
        assert hasattr(binding, 'message_received')
        assert hasattr(binding, 'message_sent')
        assert hasattr(binding, 'connection_status')
        print("  ✓ ChatBinding signals defined")
        print("  ✓ ChatBinding created")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ide_binding():
    """Test IDEBinding"""
    print("\nTesting IDEBinding...")

    try:
        from ui.bindings.ide_binding import IDEBinding

        binding = IDEBinding()
        assert hasattr(binding, 'code_generated')
        assert hasattr(binding, 'execution_result')
        assert hasattr(binding, 'completion_ready')
        print("  ✓ IDEBinding signals defined")
        print("  ✓ IDEBinding created")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_settings_binding():
    """Test SettingsBinding"""
    print("\nTesting SettingsBinding...")

    try:
        from ui.bindings.settings_binding import SettingsBinding

        binding = SettingsBinding()
        assert hasattr(binding, 'setting_changed')
        assert hasattr(binding, 'config_saved')
        assert hasattr(binding, 'CATEGORY_USER')
        assert hasattr(binding, 'CATEGORY_SYSTEM')
        print("  ✓ SettingsBinding signals defined")
        print("  ✓ SettingsBinding constants defined")
        print("  ✓ SettingsBinding created")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_main_window():
    """Test MainWindow with bindings"""
    print("\nTesting MainWindow...")

    try:
        from ui.main_window import MainWindow
        print("  ✓ MainWindow imported")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 50)
    print("UI Bindings Test Suite")
    print("=" * 50)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("ChatBinding", test_chat_binding()))
    results.append(("IDEBinding", test_ide_binding()))
    results.append(("SettingsBinding", test_settings_binding()))
    results.append(("MainWindow", test_main_window()))

    print("\n" + "=" * 50)
    print("Results Summary")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
