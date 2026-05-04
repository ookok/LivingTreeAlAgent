"""Debug TUI launcher — imports local textual from tui/textual/src/textual.

Usage:
    python debug_tui.py            # launch TUI
    python debug_tui.py --check    # verify imports only
"""
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).parent
LOCAL_TEXTUAL_SRC = PROJECT / "livingtree" / "tui" / "textual" / "src"

# Ensure CWD is project root (required for relative config paths)
os.chdir(str(PROJECT.resolve()))

# 1. local textual source (takes priority over pip-installed)
sys.path.insert(0, str(LOCAL_TEXTUAL_SRC.resolve()))
# 2. project root for livingtree package
sys.path.insert(0, str(PROJECT.resolve()))

print(f"Textual source: {LOCAL_TEXTUAL_SRC}")

# -- verify imports --
import textual
print(f"Textual @ {textual.__file__}")
from livingtree.tui.app import run_tui
print("All imports OK\n")

if "--check" in sys.argv:
    print("Check passed — exiting.")
    sys.exit(0)

print("Launching TUI — check data/logs/livingtree.log for boot progress\n")
run_tui(workspace=str(Path.cwd()))
