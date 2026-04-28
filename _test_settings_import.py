"""Test settings_dialog.py import"""
import sys
sys.path.insert(0, r"d:\mhzyapp\LivingTreeAlAgent")

# Test 1: Check PyQt6 QMessageBox has critical method
from PyQt6.QtWidgets import QMessageBox
print("QMessageBox.critical exists:", hasattr(QMessageBox, "critical"))

# Test 2: Try importing the settings dialog
try:
    from client.src.presentation.panels.settings_dialog import SettingsDialog
    print("IMPORT OK: SettingsDialog")
except Exception as e:
    print(f"IMPORT FAIL: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check encrypted_config imports
try:
    from client.src.business.encrypted_config import load_model_config, save_model_config
    print("IMPORT OK: encrypted_config")
except Exception as e:
    print(f"IMPORT FAIL: encrypted_config: {e}")
