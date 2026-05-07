"""Build relay_server.py into standalone relay_server.exe (no Python needed).

Usage: .venv\Scripts\python.exe build_relay_exe.py
Output: dist/relay_server.exe (~25MB single-file)

Runs on Windows Server 2008 through Win11.
Win2008 requires VC++ 2015+ Redistributable installed separately.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).parent
DIST = PROJECT / "dist"
BUILD = PROJECT / "build_relay"


def main():
    print("=== LivingTree Relay Server — Standalone EXE Build ===")
    print(f"    Python: {sys.version}")
    print(f"    Project: {PROJECT}")
    print()

    # 1) Install PyInstaller
    print("[1/4] Checking PyInstaller...")
    try:
        import PyInstaller
        print(f"    PyInstaller {PyInstaller.__version__} OK")
    except ImportError:
        print("    Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # 2) Clean
    print("[2/4] Cleaning build artifacts...")
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)

    # 3) Build
    print("[3/4] Building standalone exe...")
    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--console",
            "--name=relay_server",
            f"--distpath={DIST}",
            f"--workpath={BUILD}",
            "--add-data", f"config{os.sep}secrets.enc{os.pathsep}config",
            "--hidden-import", "aiohttp",
            "--hidden-import", "loguru",
            "--hidden-import", "livingtree.config.secrets",
            "--hidden-import", "livingtree.config.settings",
            "--hidden-import", "livingtree.network.proxy_fetcher",
            "--hidden-import", "livingtree.network.external_access",
            "--hidden-import", "bs4",
            "--hidden-import", "lxml",
            "--exclude-module", "torch",
            "--exclude-module", "pydantic",
            "--exclude-module", "sentence_transformers",
            "--exclude-module", "PIL",
            "--exclude-module", "numpy",
            "--clean",
            "--noconfirm",
            "relay_server.py",
        ],
        cwd=str(PROJECT),
        capture_output=False,
    )

    if result.returncode != 0:
        print("    ERROR: PyInstaller build failed")
        sys.exit(1)

    # 4) Verify
    print("[4/4] Verifying output...")
    exe_path = DIST / "relay_server.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"    SUCCESS: {exe_path}")
        print(f"    Size: {size_mb:.1f} MB")
        print()
        print("=== Deployment ===")
        print("  Copy dist/relay_server.exe to target server")
        print("  Run: relay_server.exe")
        print()
        print("  Win2008: install VC++ 2015+ Redistributable first")
        print("  https://aka.ms/vs/17/release/vc_redist.x64.exe")
    else:
        print("    ERROR: exe not found in dist/")
        sys.exit(1)


if __name__ == "__main__":
    main()
