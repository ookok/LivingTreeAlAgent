"""Self-Updater — GitHub/Gitee source sync + dependency auto-install.

Checks GitHub (primary) and Gitee (mirror) for new releases, downloads zip
or git-pulls, auto-installs/changes dependencies via pip/uv, and restarts.

Integrates with wt_bootstrap.py for one-click update on launch.

Usage:
    python -m livingtree update             # Full update cycle
    python -m livingtree update --check     # Check only
    python -m livingtree update --dry-run   # Show what would change
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import aiohttp
from loguru import logger

# ═══ Repo config ═══
GITHUB_REPO = "ookok/LivingTreeAlAgent"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_ZIP = f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{{tag}}.zip"

# Gitee mirror (same repo name convention)
GITEE_REPO = "ookok/LivingTreeAlAgent"
GITEE_API = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases/latest"
GITEE_ZIP = f"https://gitee.com/{GITEE_REPO}/repository/archive/{{tag}}.zip"

CURRENT_VERSION = "2.1.0"
PROJECT_ROOT = Path(__file__).parent.parent.parent  # livingtree/ parent


def _get_version() -> str:
    from .. import __version__
    return __version__


async def _fetch_json(url: str, timeout: int = 15) -> dict | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                                   headers={"User-Agent": "LivingTree/2.1"}) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.debug(f"Fetch {url}: {e}")
    return None


async def check_update(use_mirror: bool = False) -> Optional[dict]:
    """Check for available updates from GitHub or Gitee mirror."""
    url = GITEE_API if use_mirror else GITHUB_API
    data = await _fetch_json(url)
    if not data:
        if not use_mirror:
            logger.info("GitHub unreachable, trying Gitee mirror...")
            return await check_update(use_mirror=True)
        return None

    return {
        "version": data.get("tag_name", "").lstrip("v"),
        "name": data.get("name", ""),
        "published_at": data.get("published_at", ""),
        "url": data.get("html_url", ""),
        "zip_url": data.get("zipball_url", ""),
        "body": data.get("body", "")[:500],
    }


async def download_source(tag: str, use_mirror: bool = False) -> Optional[Path]:
    """Download release source zip. Returns path to extracted directory."""
    zip_url = GITEE_ZIP if use_mirror else GITHUB_ZIP
    url = zip_url.format(tag=f"v{tag}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="livingtree_update_"))
    zip_path = tmp_dir / "source.zip"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=300),
                                   headers={"User-Agent": "LivingTree/2.1"}) as resp:
                if resp.status != 200:
                    logger.error(f"Download failed: HTTP {resp.status}")
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    return None

                with open(zip_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        f.write(chunk)

        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # GitHub wraps in repo-tag/ dir; find the actual content
        contents = list(extract_dir.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            return contents[0]

        return extract_dir

    except Exception as e:
        logger.error(f"Download failed: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return None


async def git_pull_update() -> tuple[bool, str]:
    """Update via git pull (if project is a git repo)."""
    if not (PROJECT_ROOT / ".git").exists():
        return False, "Not a git repository"

    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "pull", "--ff-only", "origin", "main",
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        out = stdout.decode(errors="replace").strip()

        if proc.returncode != 0:
            err = stderr.decode(errors="replace")[:300]
            return False, f"Git pull failed: {err}"

        if "Already up to date" in out:
            return True, "Already up to date"

        return True, out[:500]
    except asyncio.TimeoutError:
        return False, "Git pull timed out"
    except FileNotFoundError:
        return False, "Git not found on PATH"
    except Exception as e:
        return False, str(e)


# ═══ Dependency management ═══

def find_package_manager() -> str | None:
    from .pkg_manager import has_binary
    for pm in ["uv", "pip"]:
        if has_binary(pm):
            return pm
    return None


def install_dependencies(pm: str | None = None) -> tuple[bool, str]:
    from .pkg_manager import install_project_deps
    return install_project_deps(PROJECT_ROOT)


def ensure_package_manager() -> tuple[bool, str]:
    """Ensure a package manager is available."""
    from .pkg_manager import ensure_package_manager as epm
    return epm()


# ═══ Source merge ═══

def merge_source(new_source: Path) -> tuple[bool, str]:
    """Copy new source files into project, skipping .git, __pycache__, etc."""
    skip_patterns = {".git", "__pycache__", ".open-mem", ".livingtree",
                     "data", "config", "node_modules", ".wt",
                     "toad", ".venv", "venv", ".env"}

    copied, skipped, errors = 0, 0, 0
    for item in new_source.rglob("*"):
        rel = item.relative_to(new_source)
        parts = rel.parts
        if any(p.startswith(".") and p not in (".gitignore", ".gitattributes", ".env.example")
               for p in parts):
            continue
        if set(parts) & skip_patterns:
            continue

        dest = PROJECT_ROOT / rel
        try:
            if item.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(item), str(dest))
                copied += 1
        except Exception:
            errors += 1

    return copied > 0, f"Copied {copied} files, {errors} errors"


# ═══ Full update cycle ═══

async def run_update(
    dry_run: bool = False,
    check_only: bool = False,
    use_mirror: bool = False,
    install_deps: bool = True,
) -> dict:
    """Run full update: check → download → merge → deps → restart signal."""
    current = _get_version()

    # Step 1: Try git pull (fastest)
    git_ok, git_msg = await git_pull_update()
    if git_ok and "Already up to date" not in git_msg:
        logger.info(f"Updated via git: {git_msg}")
        if install_deps:
            ok, msg = install_dependencies()
            logger.info(f"Deps: {msg}")
        return {
            "status": "updated",
            "method": "git",
            "current": current,
            "message": git_msg,
            "restart_required": True,
        }

    # Step 2: Check GitHub/Gitee for newer release
    info = await check_update(use_mirror=use_mirror)
    if not info:
        return {"status": "no_update", "message": "Could not check for updates"}

    latest = info["version"]
    if latest <= current:
        return {"status": "up_to_date", "current": current, "latest": latest}

    if check_only:
        return {"status": "update_available", "current": current, "latest": latest,
                "name": info["name"], "url": info["url"]}

    if dry_run:
        return {"status": "would_update", "current": current, "latest": latest,
                "changes": info["body"]}

    # Step 3: Download source
    logger.info(f"Downloading v{latest}...")
    src = await download_source(latest, use_mirror=use_mirror)
    if not src:
        return {"status": "download_failed", "message": "Could not download source"}

    # Step 4: Merge source
    ok, msg = merge_source(src)
    if not ok:
        return {"status": "merge_failed", "message": msg}

    # Step 5: Install dependencies
    dep_ok, dep_msg = True, ""
    if install_deps:
        dep_ok, dep_msg = install_dependencies()

    # Cleanup
    shutil.rmtree(src.parent.parent, ignore_errors=True)

    return {
        "status": "updated",
        "method": "download",
        "version": latest,
        "current": current,
        "merge": msg,
        "deps": dep_msg if dep_ok else f"WARN: {dep_msg}",
        "restart_required": True,
    }


# ═══ Version check (fast, for startup) ═══

async def version_check() -> dict:
    """Quick version check, returns immediately if up to date."""
    try:
        info = await check_update()
        if not info:
            return {"status": "unknown"}

        latest = info["version"]
        current = _get_version()
        if latest <= current:
            return {"status": "up_to_date", "current": current}

        return {"status": "outdated", "current": current, "latest": latest,
                "name": info["name"], "url": info["url"]}
    except Exception:
        return {"status": "error"}


# ═══ CLI entry ═══

async def _cli():
    import argparse
    parser = argparse.ArgumentParser(description="LivingTree Self-Updater")
    parser.add_argument("--check", action="store_true", help="Check only")
    parser.add_argument("--dry-run", action="store_true", help="Preview without applying")
    parser.add_argument("--mirror", action="store_true", help="Use Gitee mirror")
    parser.add_argument("--no-deps", action="store_true", help="Skip dependency install")
    args = parser.parse_args()

    result = await run_update(
        check_only=args.check,
        dry_run=args.dry_run,
        use_mirror=args.mirror,
        install_deps=not args.no_deps,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("restart_required"):
        print("\n⚠ Restart required to apply updates.")


if __name__ == "__main__":
    asyncio.run(_cli())
