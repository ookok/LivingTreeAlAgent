"""Debug TUI launcher — uses pip-installed Textual.

Usage:
    python debug_tui.py            # launch TUI
    python debug_tui.py --check    # verify imports only
"""
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).parent

os.chdir(str(PROJECT.resolve()))
sys.path.insert(0, str(PROJECT.resolve()))

import textual
print(f"Textual {textual.__version__} @ {textual.__file__}")
from livingtree.tui.app import run_tui
print("All imports OK\n")

if "--check" in sys.argv:
    print("Check passed — exiting.")
    sys.exit(0)

print("Launching TUI...\n")
run_tui(workspace=str(Path.cwd()))
