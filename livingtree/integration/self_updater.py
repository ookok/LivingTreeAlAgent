"""Self-Updater — Downloads and atomically replaces the livingtree binary.

Inspired by DeepSeek-TUI's `deepseek update` command. Fetches the latest
GitHub release, downloads the platform-correct binary with SHA256
verification, and atomically replaces the running binary.

Usage:
    python -m livingtree update
    livingtree update --check  # check only, don't install
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional

import aiohttp
from loguru import logger


GITHUB_API = "https://api.github.com/repos/your-org/LivingTreeAlAgent/releases/latest"
GITHUB_RELEASES = "https://github.com/your-org/LivingTreeAlAgent/releases/download"


def _get_platform_asset() -> str:
    system = sys.platform
    machine = "x64"

    if system == "win32":
        return "livingtree-windows-x64.exe"
    elif system == "darwin":
        m = "arm64" if "arm" in os.uname().machine else "x64"
        return f"livingtree-macos-{m}"
    else:
        m = "arm64" if "arm" in os.uname().machine else "x64"
        return f"livingtree-linux-{m}"


async def check_update() -> Optional[dict]:
    """Check for available updates. Returns release info or None."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GITHUB_API, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return {
                    "version": data.get("tag_name", "").lstrip("v"),
                    "name": data.get("name", ""),
                    "published_at": data.get("published_at", ""),
                    "url": data.get("html_url", ""),
                }
    except Exception as e:
        logger.debug(f"Update check failed: {e}")
        return None


async def download_update(version: str) -> Optional[Path]:
    """Download the latest release binary. Returns path to downloaded file."""
    asset = _get_platform_asset()
    url = f"{GITHUB_RELEASES}/v{version}/{asset}"
    sha_url = f"{url}.sha256"

    try:
        async with aiohttp.ClientSession() as session:
            sha256_expected = None
            try:
                async with session.get(sha_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        sha256_expected = (await resp.text()).strip().split()[0]
            except Exception:
                pass

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe" if sys.platform == "win32" else "")
            tmp_path = Path(tmp.name)

            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status != 200:
                        logger.error(f"Download failed: {resp.status}")
                        tmp_path.unlink(missing_ok=True)
                        return None

                    with open(tmp_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(65536):
                            f.write(chunk)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

            if sha256_expected:
                actual = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
                if actual != sha256_expected:
                    logger.error(f"SHA256 mismatch: expected {sha256_expected[:16]}, got {actual[:16]}")
                    tmp_path.unlink(missing_ok=True)
                    return None

            return tmp_path

    except Exception as e:
        logger.error(f"Update download failed: {e}")
        return None


async def install_update(downloaded_path: Path) -> bool:
    """Atomically replace the running binary with the downloaded one."""
    current = Path(sys.executable if getattr(sys, 'frozen', False) else sys.argv[0])

    if current.exists():
        backup = current.with_suffix(current.suffix + ".backup")
        shutil.copy2(str(current), str(backup))

    try:
        if sys.platform == "win32":
            old = current.with_suffix(".old.exe")
            if old.exists():
                old.unlink()
            shutil.move(str(current), str(old))
            shutil.move(str(downloaded_path), str(current))
            if old.exists():
                old.unlink()
        else:
            shutil.move(str(downloaded_path), str(current))
            if sys.platform != "win32":
                os.chmod(str(current), 0o755)
    except Exception as e:
        logger.error(f"Install failed: {e}")
        return False

    logger.info(f"Updated to new version at {current}")
    return True


async def run_update(dry_run: bool = False) -> dict:
    """Run a full update check + download + install cycle."""
    info = await check_update()
    if not info:
        return {"status": "no_update", "message": "No updates available"}

    current_version = "2.1.0"
    try:
        from ... import __version__
        current_version = __version__
    except ImportError:
        pass

    if info["version"] and info["version"] <= current_version:
        return {"status": "up_to_date", "current": current_version, "latest": info["version"]}

    if dry_run:
        return {"status": "update_available", "current": current_version, "latest": info["version"]}

    path = await download_update(info["version"])
    if not path:
        return {"status": "download_failed"}

    ok = await install_update(path)
    return {
        "status": "updated" if ok else "install_failed",
        "version": info["version"],
    }
