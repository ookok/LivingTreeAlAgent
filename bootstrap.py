"""Bootstrap — unified entry point for LivingTree TUI."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT = Path(__file__).parent.parent

def bootstrap():
    """Ensure local textual + project root then launch TUI."""
    local_textual = PROJECT / "tui" / "textual" / "src"
    if local_textual.is_dir():
        sys.path.insert(0, str(local_textual.resolve()))
    sys.path.insert(0, str(PROJECT.resolve()))
    os.chdir(str(PROJECT.resolve()))

    from livingtree.tui.app import run_tui
    run_tui(workspace=str(PROJECT.resolve()))

if __name__ == "__main__":
    bootstrap()
