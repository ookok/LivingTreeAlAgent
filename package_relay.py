"""Package relay server into a deployable zip archive.

    Usage: .venv\Scripts\python.exe package_relay.py

    Output: dist/relay_server_package.zip containing:
      relay_server.exe       — standalone server (no Python needed)
      start_relay.bat        — one-click launcher
      install_crt.bat        — VC++ redist installer (Win2008)
      config/                — secrets.enc + config.yaml
      README.txt             — quickstart guide

    Deploy steps on target:
      1. Extract relay_server_package.zip
      2. If Win2008: run install_crt.bat (first time only)
      3. Run start_relay.bat
      4. Open https://relay.livingtree.localhost/admin
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

PROJECT = Path(__file__).parent
DIST = PROJECT / "dist"
PACKAGE = DIST / "relay_package"
PACKAGE_ZIP = DIST / f"relay_server_{time.strftime('%Y%m%d')}.zip"


def main():
    print("=" * 60)
    print("  LivingTree Relay Server — Package Builder")
    print("=" * 60)
    print()

    # 1) Clean
    print("[1/5] Cleaning...")
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True, exist_ok=True)

    # 2) Build exe if not exists
    exe_path = DIST / "relay_server.exe"
    if not exe_path.exists():
        print("[2/5] Building relay_server.exe...")
        result = subprocess.run(
            [sys.executable, "build_relay_exe.py"],
            cwd=str(PROJECT), capture_output=False,
        )
        if result.returncode != 0 or not exe_path.exists():
            print("ERROR: Build failed. Run build_relay_exe.py manually.")
            sys.exit(1)
    else:
        print("[2/5] relay_server.exe found (skip build)")

    # 3) Copy files
    print("[3/5] Assembling package...")

    # Main exe
    shutil.copy2(exe_path, PACKAGE / "relay_server.exe")
    print(f"  + relay_server.exe ({exe_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Config
    config_dir = PACKAGE / "config"
    config_dir.mkdir(exist_ok=True)
    for fname in ["secrets.enc", "config.yaml"]:
        src = PROJECT / "config" / fname
        if src.exists():
            shutil.copy2(src, config_dir / fname)
            print(f"  + config/{fname}")

    # Data dirs
    for dname in [".livingtree"]:
        (PACKAGE / dname).mkdir(exist_ok=True)

    # 4) Create launchers
    print("[4/5] Creating scripts...")

    # Start script
    start_bat = PACKAGE / "start_relay.bat"
    start_bat.write_text(
        '@echo off\r\n'
        'title LivingTree Relay Server\r\n'
        'chcp 65001 >nul\r\n'
        'echo ========================================\r\n'
        'echo  LivingTree Relay Server\r\n'
        'echo  Port: 8888\r\n'
        'echo  Admin: http://www.mogoo.com.cn:8888/admin\r\n'
        'echo  Named: https://relay.livingtree.localhost/admin\r\n'
        'echo ========================================\r\n'
        'echo.\r\n'
        'echo Starting relay server...\r\n'
        'echo.\r\n'
        'relay_server.exe --port 8888 --host 0.0.0.0\r\n'
        'if %ERRORLEVEL% NEQ 0 (\r\n'
        '    echo.\r\n'
        '    echo [ERROR] Server failed. Troubleshooting:\r\n'
        '    echo   1. Run install_crt.bat (VC++ Redist on Win2008)\r\n'
        '    echo   2. Check port 8888 is not in use\r\n'
        '    echo   3. Ensure config/secrets.enc exists\r\n'
        '    echo.\r\n'
        '    pause\r\n'
        ')\r\n',
        encoding="ascii",
    )
    print("  + start_relay.bat")

    # CRT installer
    crt_bat = PACKAGE / "install_crt.bat"
    crt_bat.write_text(
        '@echo off\r\n'
        'title Install VC++ Redistributable\r\n'
        'echo Installing VC++ 2015-2022 Redistributable...\r\n'
        'echo Required for Windows Server 2008\r\n'
        'echo.\r\n'
        'bitsadmin /transfer "VC_Redist" "https://aka.ms/vs/17/release/vc_redist.x64.exe" "%TEMP%\\vc_redist.x64.exe"\r\n'
        'if exist "%TEMP%\\vc_redist.x64.exe" (\r\n'
        '    echo Installing...\r\n'
        '    "%TEMP%\\vc_redist.x64.exe" /quiet /norestart\r\n'
        '    del "%TEMP%\\vc_redist.x64.exe"\r\n'
        '    echo Done. You can now run start_relay.bat\r\n'
        ') else (\r\n'
        '    echo Download failed. Install manually:\r\n'
        '    echo https://aka.ms/vs/17/release/vc_redist.x64.exe\r\n'
        ')\r\n'
        'pause\r\n',
        encoding="ascii",
    )
    print("  + install_crt.bat")

    # README
    readme = PACKAGE / "README.txt"
    readme.write_text(
        "LivingTree Relay Server — Quick Start\n"
        "======================================\n\n"
        "1) First time on Windows Server 2008: run install_crt.bat\n"
        "2) Run start_relay.bat\n"
        "3) Open admin panel:\n"
        "     https://relay.livingtree.localhost/admin\n"
        "   or:\n"
        "     http://www.mogoo.com.cn:8888/admin\n\n"
        "Admin Login:\n"
        "  Username: admin\n"
        "  Password: admin123 (change immediately via admin panel)\n\n"
        "Ports: 8888 (HTTP), 443 (HTTPS named URL)\n"
        "Firewall: ensure port 8888 is open\n\n"
        "Features:\n"
        "  - Account management (add/delete/reset users)\n"
        "  - API key per user (auto-generated)\n"
        "  - LLM subscription pooling (share Claude/OpenAI subscriptions)\n"
        "  - P2P signaling + WebSocket relay\n"
        "  - Token cost tracking per user\n"
        "  - External network health check\n"
        "  - Relay pool auto-sync\n\n"
        "API Endpoints (require user API key):\n"
        "  POST /v1/chat/completions  — OpenAI-compatible LLM proxy\n"
        "  POST /login                 — Get API key\n"
        "  POST /cost/report           — Report token usage\n"
        "  GET  /peers/discover         — P2P node list\n\n"
        "No Python installation required.\n"
        f"Package built: {time.strftime('%Y-%m-%d %H:%M')}\n",
        encoding="utf-8",
    )
    print("  + README.txt")

    # 5) Zip
    print("[5/5] Creating zip archive...")
    if PACKAGE_ZIP.exists():
        PACKAGE_ZIP.unlink()

    with zipfile.ZipFile(PACKAGE_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PACKAGE):
            for fname in files:
                fpath = Path(root) / fname
                arcname = str(fpath.relative_to(PACKAGE))
                zf.write(fpath, arcname)

    size_mb = PACKAGE_ZIP.stat().st_size / 1024 / 1024
    print()
    print("=" * 60)
    print(f"  Package: {PACKAGE_ZIP.name}")
    print(f"  Size: {size_mb:.1f} MB")
    print(f"  Path: {PACKAGE_ZIP}")
    print("=" * 60)
    print()
    print("Deploy:")
    print(f"  1. Copy {PACKAGE_ZIP.name} to target server")
    print("  2. Extract zip")
    print("  3. Run install_crt.bat (Win2008 only)")
    print("  4. Run start_relay.bat")
    print()


if __name__ == "__main__":
    main()
