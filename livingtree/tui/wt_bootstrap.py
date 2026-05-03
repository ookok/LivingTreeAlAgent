"""WT Bootstrapper — standalone, no livingtree imports.

Checks for Windows Terminal, downloads if missing, launches TUI.
Fully independent — no litellm, no config, no DNA layer.

Usage:
    python -m livingtree.tui.wt_bootstrap [--direct] [workspace]
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request

EXPECTED_VERSION = "1.25.1171.0"
WT_EXE_NAME = "WindowsTerminal.exe"


def _log(msg: str) -> None:
    try:
        print(f"[WT] {msg}", flush=True)
    except (OSError, IOError):
        pass


def _is_x64() -> bool:
    return struct.calcsize("P") == 8 and platform.machine().lower() in ("amd64", "x86_64")


def find_wt() -> Optional[Path]:
    for search in [
        Path(".wt") / WT_EXE_NAME,
    ]:
        if search.exists():
            return search.resolve()

    wt_cmd = shutil.which("wt.exe")
    if wt_cmd:
        return Path(wt_cmd).resolve()

    msix = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps"
    if msix.exists():
        for d in msix.glob("Microsoft.WindowsTerminal_*"):
            exe = d / WT_EXE_NAME
            if exe.exists():
                return exe

    return None


def download_wt(target_dir: str = ".wt") -> Optional[Path]:
    if not _is_x64():
        _log("x64 Windows required")
        return None

    target = Path(target_dir)
    existing = target / WT_EXE_NAME
    if existing.exists():
        _log(f"Already installed: {existing}")
        return existing

    _log(f"Downloading Windows Terminal...")
    try:
        req = Request(
            "https://api.github.com/repos/microsoft/terminal/releases/latest",
            headers={"User-Agent": "LivingTree-WT/2.0", "Accept": "application/json"},
        )
        with urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read())

        tag = release.get("tag_name", "")
        _log(f"Latest: {tag}")

        zip_asset = None
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name.endswith("_x64.zip") and "PreinstallKit" not in name:
                zip_asset = asset
                break

        download_url = (
            zip_asset["browser_download_url"]
            if zip_asset
            else f"https://github.com/microsoft/terminal/releases/download/{tag}/Microsoft.WindowsTerminal_{tag.lstrip('v')}_x64.zip"
        )
        size_mb = (zip_asset.get("size", 0) // 1024 // 1024) if zip_asset else 0
        _log(f"Downloading: {size_mb}MB...")

        target.mkdir(parents=True, exist_ok=True)
        zip_path = target / "wt_temp.zip"
        req2 = Request(download_url, headers={"User-Agent": "LivingTree-WT/2.0"})
        with urlopen(req2, timeout=600) as resp:
            with open(zip_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)

        _log("Extracting...")
        extract_dir = target / "wt_extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        wt_exe = None
        for root, _, files in os.walk(extract_dir):
            if WT_EXE_NAME in files:
                src = Path(root) / WT_EXE_NAME
                wt_exe = target / WT_EXE_NAME
                shutil.move(str(src), str(wt_exe))
                break

        zip_path.unlink(missing_ok=True)
        shutil.rmtree(extract_dir, ignore_errors=True)

        if wt_exe and wt_exe.exists():
            _log(f"Installed: {wt_exe}")
            return wt_exe
        _log("ERROR: could not find WindowsTerminal.exe in extracted files")
        return None

    except Exception as e:
        _log(f"Download failed: {e}")
        return None


def launch(wt_path: Path, workspace: str = "", title: str = "🌳 LivingTree AI Agent") -> subprocess.Popen:
    ws = workspace or str(Path.cwd())
    # Inside Windows Terminal we need python.exe (not pythonw)
    python_exe = Path(sys.executable)
    if python_exe.name == "pythonw.exe":
        python = str(python_exe.parent / "python.exe")
        if not Path(python).exists():
            python = sys.executable
    else:
        python = sys.executable

    cmd = [
        str(wt_path),
        "--title", title,
        "-d", ws,
        python, "-m", "livingtree", "tui", "--direct",
    ]
    _log(f"Launching: wt -d {ws}")
    return subprocess.Popen(
        cmd, cwd=ws,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def main() -> int:
    args = sys.argv[1:]
    if "--check" in args:
        wt = find_wt()
        if wt:
            _log(f"Found: {wt}")
            return 0
        _log("Not found")
        return 1

    if "--download" in args:
        wt = download_wt(".wt")
        return 0 if wt else 1

    # Default: ensure + launch
    workspace = args[0] if args and not args[0].startswith("-") else str(Path.cwd())
    wt = find_wt()
    if not wt:
        _log("WT not found — downloading...")
        wt = download_wt(".wt")
        if not wt:
            _log("FATAL: could not install Windows Terminal")
            return 1
    launch(wt, workspace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
