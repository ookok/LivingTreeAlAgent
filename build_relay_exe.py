"""Build script: packs relay_server.py into standalone relay_server.exe.

    Usage: python build_relay_exe.py

    Output: dist/relay_server.exe (single-file, no Python install needed)

    The resulting .exe embeds Python 3.14 runtime + all dependencies. Runs on:
    - Windows Server 2008 (with bundled CRT DLLs)
    - Windows 7/8/10/11
    - Windows Server 2012+

    Requires: pip install pyinstaller
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

    # 3) Build with PyInstaller
    print("[3/4] Building standalone exe...")
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['relay_server.py'],
    pathex=[str(Path('{PROJECT}'))],
    binaries=[],
    datas=[
        ('config/secrets.enc', 'config/'),
    ],
    hiddenimports=[
        'aiohttp', 'loguru', 'livingtree.config.secrets',
        'livingtree.config.settings',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Bundle VC++ redistributable for Win2008 compatibility
import glob as _glob
import struct as _struct

is_64bit = _struct.calcsize("P") == 8
arch = "amd64" if is_64bit else "x86"

# Find and bundle vcruntime + ucrtbase if available
vcr_paths = []
for candidate in [
    rf'C:\\Windows\\System32\\vcruntime140.dll',
    rf'C:\\Windows\\SysWOW64\\vcruntime140.dll',
]:
    if Path(candidate).exists():
        vcr_paths.append((candidate, '.'))

for candidate in [
    rf'C:\\Windows\\System32\\ucrtbase.dll',
]:
    if Path(candidate).exists():
        vcr_paths.append((candidate, '.'))

if vcr_paths:
    a.binaries += vcr_paths
    print(f"Bundled CRT DLLs: {{vcr_paths}}")

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='relay_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# Also create a one-folder version for debugging
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='relay_server_folder',
)
"""

    spec_file = PROJECT / "relay_server.spec"
    spec_file.write_text(spec_content, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_file)],
        cwd=str(PROJECT),
        capture_output=False,
    )

    if result.returncode != 0:
        print("    ERROR: PyInstaller build failed")
        sys.exit(1)

    # 4) Verify + report
    print("[4/4] Verifying output...")
    exe_path = DIST / "relay_server.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"    SUCCESS: {exe_path}")
        print(f"    Size: {size_mb:.1f} MB")
        print()
        print("=== Deployment ===")
        print("  Copy dist/relay_server.exe to target server")
        print("  Create config/ directory with secrets.enc alongside the exe")
        print("  Run: relay_server.exe")
        print()
        print("  For Windows Server 2008:")
        print("  - Ensure Visual C++ 2015+ Redistributable is installed")
        print("  - Or run deploy_win2008.bat to bundle everything")
    else:
        print("    ERROR: exe not found in dist/")
        sys.exit(1)


if __name__ == "__main__":
    main()
