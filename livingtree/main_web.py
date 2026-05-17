"""Web/desktop startup commands — extracted from main.py."""
from __future__ import annotations

import sys, os, subprocess
from pathlib import Path
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync


def _start_web():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    from .integration.launcher import launch, LaunchMode
    launch(LaunchMode.SERVER)



def _start_desktop():
    """Launch LivingTree as a native desktop app via pywebview."""
    from .desktop_shell import DesktopShell
    shell = DesktopShell()
    shell.start(debug="--debug" in sys.argv)



def _build_exe():
    """Build standalone exe using PyInstaller."""
    print("🔨 Building LivingTree.exe...")
    import subprocess

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--name", "LivingTree",
        "--add-data", f"config{os.pathsep}config",
        "--add-data", f"client{os.pathsep}client",
        "--hidden-import", "livingtree",
        "--hidden-import", "webview",
        "--hidden-import", "aiohttp",
        "livingtree/__main__.py",
    ]
    subprocess.run(cmd, check=True)
    print("✅ LivingTree.exe built in dist/")



__all__ = ["start_web", "start_desktop", "build_exe"]
