"""Base Environment — Pre-download Node.js + opencode to .livingtree/base/

Run once to cache everything locally. Subsequent LivingTree startups skip all
network downloads. Can be distributed with the project (add to .gitignore by
choice — binaries are large).

Usage:
    # Manual pre-download once:
    python -m livingtree.tui.setup_base
    
    # Then LivingTree auto-uses the cache:
    python -m livingtree tui
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

_NODE_VERSION = "v22.11.0"
_NODE_URL = f"https://nodejs.org/dist/{_NODE_VERSION}/node-{_NODE_VERSION}-win-x64.zip"


def setup_base(workspace: str | Path = ".") -> tuple[bool, str]:
    workspace = Path(workspace).resolve()
    base = workspace / ".livingtree" / "base"
    base.mkdir(parents=True, exist_ok=True)

    ok, msg = _ensure_nodejs(base)
    if not ok:
        return False, f"Node.js: {msg}"

    ok, msg = _ensure_opencode(base, workspace)
    if not ok:
        return False, f"opencode: {msg}"

    return True, "Base environment ready"


def is_base_ready(workspace: str | Path = ".") -> bool:
    workspace = Path(workspace).resolve()
    base = workspace / ".livingtree" / "base"
    return (
        (base / "nodejs" / "node.exe").exists()
        and (base / "nodejs" / "npm.cmd").exists()
        and (base / "opencode" / "node_modules" / ".bin" / "opencode").exists()
    )


def _ensure_nodejs(base: Path) -> tuple[bool, str]:
    node_dir = base / "nodejs"
    if (node_dir / "node.exe").exists() and (node_dir / "npm.cmd").exists():
        return True, "Node.js cached"

    print("[base] Downloading Node.js... (this may take 2-3 minutes)")
    node_dir.mkdir(parents=True, exist_ok=True)

    try:
        zip_path = node_dir / "node.zip"
        urllib.request.urlretrieve(_NODE_URL, str(zip_path))

        print("[base] Extracting...")
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            zf.extractall(str(node_dir))

        zip_path.unlink()

        subdirs = list(node_dir.glob("node-v*"))
        if not subdirs:
            return False, "Extraction failed — no node directory found"

        src = subdirs[0]
        for item in src.iterdir():
            dest = node_dir / item.name
            if not dest.exists():
                shutil.move(str(item), str(dest))
        shutil.rmtree(str(src), ignore_errors=True)

        print(f"[base] Node.js cached ({_NODE_VERSION})")
        return True, f"Node.js {_NODE_VERSION} cached"

    except Exception as e:
        return False, str(e)


def _ensure_opencode(base: Path, workspace: Path) -> tuple[bool, str]:
    opencode_dir = base / "opencode"
    bin_path = opencode_dir / "node_modules" / ".bin" / "opencode"
    node_dir = base / "nodejs"

    if bin_path.exists():
        return True, "opencode cached"

    if not (node_dir / "npm.cmd").exists():
        return False, "Node.js not cached yet"

    print("[base] Installing opencode locally... (may take 1-2 minutes)")
    opencode_dir.mkdir(parents=True, exist_ok=True)

    env = _get_env_with_node(str(node_dir))

    try:
        proc = subprocess.run(
            [str(node_dir / "npm.cmd"), "install", "--prefix", str(opencode_dir),
             "opencode", "--no-save"],
            capture_output=True, text=True, env=env, timeout=300,
        )

        if bin_path.exists():
            print("[base] opencode cached")
            return True, "opencode cached"

        return False, f"npm install failed: {proc.stderr[:200]}"

    except subprocess.TimeoutExpired:
        return False, "npm install timed out"
    except Exception as e:
        return False, str(e)


def _get_env_with_node(node_dir: str) -> dict:
    import os
    env = os.environ.copy()
    env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")
    env["npm_config_prefix"] = node_dir
    return env


def main():
    workspace = Path.cwd()
    print(f"[base] Setting up base environment for {workspace}")
    ok, msg = setup_base(workspace)
    if ok:
        print(f"[base] Done: {msg}")
    else:
        print(f"[base] Failed: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
