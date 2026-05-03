"""Windows Terminal configuration generator for LivingTree TUI.

Creates a dedicated WT profile with:
- Custom icon, color scheme, font
- Pre-configured environment (PYTHONPATH, workspace)
- One-click launch from WT dropdown
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from loguru import logger


def generate_wt_profile(
    project_root: str = "",
    profile_name: str = "LivingTree AI Agent",
    icon_path: str = "",
    font_face: str = "Cascadia Code",
    font_size: int = 13,
    color_scheme: str = "One Half Dark",
    output_path: Optional[str] = None,
) -> str:
    """Generate a Windows Terminal profile JSON snippet.

    Returns the profile JSON string. Optionally writes to output_path.

    Usage:
        python -c "from livingtree.tui.wt_config import generate_wt_profile; print(generate_wt_profile())"
    """
    root = Path(project_root) if project_root else Path.cwd()

    profile = {
        "name": profile_name,
        "commandline": f"cmd.exe /k \"cd /d {root} && python -m livingtree tui\"",
        "startingDirectory": str(root),
        "icon": icon_path or "",
        "tabTitle": "LivingTree",
        "suppressApplicationTitle": True,
        "hidden": False,
        "font": {
            "face": font_face,
            "size": font_size,
        },
        "colorScheme": color_scheme,
        "cursorShape": "bar",
        "useAcrylic": True,
        "acrylicOpacity": 0.85,
        "scrollbarState": "hidden",
        "padding": "8, 8, 8, 8",
        "antialiasingMode": "cleartype",
    }

    profile_json = json.dumps(profile, indent=2, ensure_ascii=False)

    if output_path:
        Path(output_path).write_text(profile_json, encoding="utf-8")
        logger.info(f"WT profile written to {output_path}")

    return profile_json


def install_wt_profile(project_root: str = "") -> dict[str, str]:
    """Generate installation instructions for the WT profile.

    Returns a dict with the profile JSON and install instructions.
    """
    profile_json = generate_wt_profile(project_root)
    instructions = """
To install the Windows Terminal profile:

1. Open Windows Terminal
2. Press Ctrl+Shift+, (Settings)
3. Add the profile JSON under "profiles" → "list"
4. Save and restart Windows Terminal

Or use the automatic install script:
    python scripts/install_wt_profile.py
"""
    return {
        "profile_json": profile_json,
        "instructions": instructions,
    }


def create_run_script(project_root: str = "", output_path: str = "") -> str:
    """Create a run.bat script for one-click launch from Windows Terminal."""
    root = Path(project_root) if project_root else Path.cwd()

    script = f"""@echo off
chcp 65001 > nul
title LivingTree AI Agent

set PYTHONPATH={root}

echo.
echo     LivingTree AI Agent v2.0.0
echo     Digital Lifeform Platform
echo     --------------------------
echo.

cd /d "{root}"
python -m livingtree tui %*

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start LivingTree TUI.
    echo Make sure Python and dependencies are installed.
    pause
)
"""

    if output_path:
        Path(output_path).write_text(script, encoding="utf-8")
        logger.info(f"Run script written to {output_path}")

    return script
