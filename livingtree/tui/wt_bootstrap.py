"""WT Bootstrapper — standalone, no livingtree imports.

Checks for Windows Terminal, downloads if missing, launches TUI.
Supports auto-update via --update flag and automatic version check.
Uses mirror fallback for GitHub downloads.

Usage:
    python -m livingtree.tui.wt_bootstrap [--direct] [--update] [--no-update] [workspace]
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
import time
import zipfile
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request

EXPECTED_VERSION = "1.25.1171.0"
WT_EXE_NAME = "WindowsTerminal.exe"
CURRENT_VERSION = "2.1.0"
WT_VERSION_FILE = ".wt/version.txt"
BOOTSTRAP_MARKER = ".livingtree/wt_bootstrapped"

# ═══ Mirror fallback ═══

GITHUB_MIRRORS = [
    "https://api.github.com",
    "https://ghproxy.com/https://api.github.com",
    "https://mirror.ghproxy.com/https://api.github.com",
]


def _get_wt_installed_version() -> Optional[str]:
    """Read the installed WT version from version file or exe properties."""
    vf = Path(WT_VERSION_FILE)
    if vf.exists():
        try:
            return vf.read_text().strip()
        except Exception:
            pass
    return None


def _check_wt_update_needed() -> tuple[bool, str]:
    """Check if a newer WT version is available on GitHub."""
    try:
        req = Request(
            "https://api.github.com/repos/microsoft/terminal/releases/latest",
            headers={"User-Agent": "LivingTree/2.1", "Accept": "application/json"},
        )
        proxy = os.environ.get("LIVINGTREE_PROXY") or os.environ.get("HTTPS_PROXY") or ""
        if proxy:
            req.set_proxy(proxy, "http")
            req.set_proxy(proxy, "https")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            latest = data.get("tag_name", "").lstrip("v")
            installed = _get_wt_installed_version() or EXPECTED_VERSION
            if latest and latest > installed:
                return True, latest
            return False, installed
    except Exception:
        pass

    # Mirror fallback
    try:
        req = Request(
            "https://ghproxy.com/https://api.github.com/repos/microsoft/terminal/releases/latest",
            headers={"User-Agent": "LivingTree/2.1", "Accept": "application/json"},
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            latest = data.get("tag_name", "").lstrip("v")
            installed = _get_wt_installed_version() or EXPECTED_VERSION
            if latest and latest > installed:
                return True, latest
            return False, installed
    except Exception:
        pass

    return False, "unknown"


def _fetch_with_mirrors(url: str, timeout: int = 30):
    """Fetch URL with GitHub mirror fallback."""
    last_error = b""
    for mirror_base in GITHUB_MIRRORS:
        try_url = url.replace("https://api.github.com", mirror_base)
        if mirror_base != "https://api.github.com":
            try_url = mirror_base + url[len("https://api.github.com"):]
        try:
            req = Request(try_url, headers={"User-Agent": "LivingTree/2.1", "Accept": "application/json"})
            proxy = os.environ.get("LIVINGTREE_PROXY") or os.environ.get("HTTPS_PROXY") or ""
            if proxy:
                req.set_proxy(proxy, "http")
                req.set_proxy(proxy, "https")
            with urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(), try_url
        except Exception as e:
            last_error = str(e)[:200].encode()
            time.sleep(1)
    return 0, last_error, ""

# ═══ Update check (standalone, no livingtree deps) ═══

def check_version_github() -> Optional[dict]:
    """Standalone version check via GitHub API with mirror fallback."""
    code, body, _ = _fetch_with_mirrors(
        "https://api.github.com/repos/ookok/LivingTreeAlAgent/releases/latest"
    )
    if code == 200:
        data = json.loads(body)
        return {
            "version": data.get("tag_name", "").lstrip("v"),
            "name": data.get("name", ""),
            "url": data.get("html_url", ""),
        }

    # Fallback: Gitee
    try:
        req = Request(
            "https://gitee.com/api/v5/repos/ookok/LivingTreeAlAgent/releases/latest",
            headers={"User-Agent": "LivingTree/2.1", "Accept": "application/json"},
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return {
                "version": data.get("tag_name", "").lstrip("v"),
                "name": data.get("name", ""),
                "url": data.get("html_url", ""),
            }
    except Exception:
        return None


def run_update_process() -> tuple[bool, str]:
    """Run the update process as a subprocess."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "livingtree", "update"],
            capture_output=True, text=True, timeout=300,
            cwd=str(Path.cwd()),
        )
        return proc.returncode == 0, proc.stdout[:500] + proc.stderr[:500]
    except subprocess.TimeoutExpired:
        return False, "Update timed out"
    except Exception as e:
        return False, str(e)


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
        # Mirror the download URL
        download_url = download_url.replace(
            "https://github.com",
            "https://ghproxy.com/https://github.com"
        )
        size_mb = (zip_asset.get("size", 0) // 1024 // 1024) if zip_asset else 0
        _log(f"Downloading: {size_mb}MB... ({download_url[:60]}...)")

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


def ensure_bootstrapped(workspace: str = "") -> bool:
    """Ensure WT bootstrap has completed. Called by debug scripts.
    
    Finds or downloads WT, writes a marker file.
    Does NOT launch WT — the caller is already in a terminal.
    
    Returns True if bootstrap is complete (WT available + marker written).
    """
    wt = find_wt()
    if not wt:
        _log("WT not found — downloading...")
        wt = download_wt(".wt")
        if wt:
            need_update, latest = _check_wt_update_needed()
            Path(WT_VERSION_FILE).write_text(latest if latest else EXPECTED_VERSION)
        if not wt:
            _log("WARNING: could not install Windows Terminal")
            return False

    marker = Path(workspace or str(Path.cwd())) / BOOTSTRAP_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(int(time.time())))
    os.environ["LIVINGTREE_WT_BOOTSTRAPPED"] = "1"
    _log("WT bootstrap verified")
    return True


def _write_bootstrap_marker(workspace: str) -> None:
    """Write marker file so --direct can verify bootstrap completed."""
    try:
        marker = Path(workspace) / BOOTSTRAP_MARKER
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(int(time.time())))
    except Exception:
        pass


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

    _write_bootstrap_marker(ws)

    cmd = [
        str(wt_path),
        "--title", title,
        "-d", ws,
        python, "-m", "livingtree", "tui", "--direct",
    ]
    _log(f"Launching: wt -d {ws}")
    log_dir = os.path.join(ws, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = open(os.path.join(log_dir, "wt_error.log"), "a")

    env = os.environ.copy()
    env["LIVINGTREE_WT_BOOTSTRAPPED"] = "1"

    return subprocess.Popen(
        cmd, cwd=ws,
        stdout=subprocess.DEVNULL, stderr=log_file,
        env=env,
    )


def main() -> int:
    args = sys.argv[1:]

    # ── Update flags ──
    do_update = "--update" in args or "-u" in args
    no_update = "--no-update" in args
    args = [a for a in args if a not in ("--update", "-u", "--no-update", "--direct")]

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

    # ── Force update ──
    if do_update:
        _log(f"Checking for updates (v{CURRENT_VERSION})...")
        info = check_version_github()
        if info and info["version"] > CURRENT_VERSION:
            _log(f"Update available: v{info['version']} (current: v{CURRENT_VERSION})")
            _log("Downloading and installing...")
            ok, msg = run_update_process()
            if ok:
                _log(f"✓ Updated to v{info['version']}. Restart required.")
                return 0
            else:
                _log(f"Update failed: {msg}")
        else:
            _log(f"No updates available (v{CURRENT_VERSION})")

    # ── Auto-check (skip if --no-update) ──
    if not no_update and not do_update:
        try:
            info = check_version_github()
            if info and info.get("version", "") > CURRENT_VERSION:
                _log(f"⚠ Update available: v{info['version']} (you have v{CURRENT_VERSION})")
                _log(f"   Run with --update to auto-upgrade, or --no-update to skip")
        except Exception:
            pass

    # Default: ensure + check WT version + launch
    workspace = args[0] if args and not args[0].startswith("-") else str(Path.cwd())
    wt = find_wt()

    # Auto-check WT version if already installed
    if wt and not no_update:
        need_update, latest = _check_wt_update_needed()
        if need_update:
            _log(f"WT update available: v{latest}. Auto-updating...")
            # Force re-download by removing version file
            vf = Path(WT_VERSION_FILE)
            if vf.exists():
                vf.unlink()
            wt_path = Path(".wt") / WT_EXE_NAME
            if wt_path.exists():
                wt_path.unlink()
            wt = download_wt(".wt")
            if wt:
                Path(WT_VERSION_FILE).write_text(latest)
                _log(f"WT updated to v{latest}")

    if not wt:
        _log("WT not found — downloading...")
        wt = download_wt(".wt")
        if wt:
            # Save version after download
            need_update, latest = _check_wt_update_needed()
            Path(WT_VERSION_FILE).write_text(latest if latest else EXPECTED_VERSION)
        if not wt:
            _log("FATAL: could not install Windows Terminal")
            return 1
    launch(wt, workspace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
