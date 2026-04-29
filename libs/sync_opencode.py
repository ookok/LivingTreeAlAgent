#!/usr/bin/env python3
"""
OpenCode 嵌入式仓库同步脚本
==========================

快速同步 libs/ 目录下的所有嵌入式仓库。

用法:
    python sync_opencode.py [--force] [--verbose]

选项:
    --force     强制同步 (git reset --hard)
    --verbose   详细输出
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

# ============================================================================
# 配置
# ============================================================================

REPOS = {
    "opencode-core": {
        "url": "https://github.com/opencode-ai/opencode.git",
        "branch": "main",
        "shallow": True,
        "description": "OpenCode CLI 核心"
    },
    "oh-my-opencode": {
        "url": "https://github.com/code-yeongyu/oh-my-opencode.git",
        "branch": "master",
        "shallow": False,  # 需要完整历史用于构建
        "description": "oh-my-opencode 插件集合"
    }
}

# 尝试多种方式定位 libs
def find_libs() -> Optional[Path]:
    """查找 libs 目录"""
    # 1. 相对于脚本
    script = Path(__file__).resolve()
    libs = script.parent.parent.parent / "libs"
    if libs.exists():
        return libs
    
    # 2. 相对于工作目录
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents, Path(__file__).parent.parent]:
        libs = parent / "libs"
        if libs.exists():
            return libs
    
    return None

LIBS_DIR = find_libs()


# ============================================================================
# 工具函数
# ============================================================================

def run_cmd(cmd: list, cwd: Path, timeout: int = 180) -> tuple:
    """运行命令并返回 (success, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def print_status(symbol: str, message: str, verbose: bool = False):
    """打印状态"""
    print(f"{symbol} {message}")
    if verbose:
        print()


# ============================================================================
# 仓库操作
# ============================================================================

def clone_repo(name: str, info: Dict, libs_dir: Path, verbose: bool = False) -> bool:
    """克隆仓库"""
    repo_dir = libs_dir / name
    url = info["url"]
    branch = info["branch"]
    
    if repo_dir.exists():
        print_status("⚠️", f"{name}: Already exists, skipping clone")
        return True
    
    print_status("📦", f"Cloning {name}...")
    print_status("   ", f"URL: {url}")
    print_status("   ", f"Branch: {branch}")
    
    cmd = ["git", "clone"]
    if info.get("shallow", False):
        cmd.extend(["--depth", "1"])
    cmd.extend(["--branch", branch, url, str(repo_dir)])
    
    success, stdout, stderr = run_cmd(cmd, libs_dir)
    
    if success:
        print_status("✅", f"{name}: Cloned successfully")
    else:
        print_status("❌", f"{name}: Clone failed - {stderr}")
    
    return success


def sync_repo(name: str, info: Dict, libs_dir: Path, force: bool = False, verbose: bool = False) -> bool:
    """同步仓库"""
    repo_dir = libs_dir / name
    
    if not repo_dir.exists():
        return clone_repo(name, info, libs_dir, verbose)
    
    print_status("🔄", f"Syncing {name}...")
    
    # Fetch remote
    print_status("   ", "Fetching updates...", verbose)
    success, _, _ = run_cmd(["git", "fetch", "origin"], repo_dir, timeout=60)
    
    if not success:
        print_status("⚠️", f"{name}: Fetch failed, trying local operations", verbose)
    
    # Get current and remote commits
    success, current, _ = run_cmd(
        ["git", "rev-parse", "HEAD"],
        repo_dir
    )
    current = current.strip() if success else ""
    
    success, remote, _ = run_cmd(
        ["git", "rev-parse", f"origin/{info['branch']}"],
        repo_dir
    )
    remote = remote.strip() if success else ""
    
    # Check if up to date
    if current == remote and not force:
        print_status("✅", f"{name}: Already up to date")
        return True
    
    # Pull or reset
    if force:
        print_status("   ", f"Force sync: resetting to origin/{info['branch']}", verbose)
        success, _, stderr = run_cmd(
            ["git", "reset", "--hard", f"origin/{info['branch']}"],
            repo_dir
        )
    else:
        print_status("   ", "Pulling updates...", verbose)
        success, _, stderr = run_cmd(
            ["git", "pull", "origin", info["branch"]],
            repo_dir
        )
    
    if success:
        print_status("✅", f"{name}: Synced successfully")
    else:
        print_status("❌", f"{name}: Sync failed - {stderr}")
    
    return success


def build_plugin(name: str, libs_dir: Path, verbose: bool = False) -> bool:
    """构建插件"""
    if name != "oh-my-opencode":
        return True
    
    plugin_dir = libs_dir / name
    
    # 检查构建产物
    dist_index = plugin_dir / "dist" / "index.js"
    if dist_index.exists():
        print_status("✅", f"{name}: Already built")
        return True
    
    # 检查 package.json
    package_json = plugin_dir / "package.json"
    if not package_json.exists():
        print_status("⚠️", f"{name}: No package.json found")
        return False
    
    print_status("🔧", f"Building {name}...")
    
    # 尝试 Bun
    bun_available = subprocess.run(
        ["bun", "--version"],
        capture_output=True,
        timeout=5
    ).returncode == 0
    
    if bun_available:
        print_status("   ", "Using Bun...", verbose)
        cmd = ["bun"]
    else:
        # 尝试 npm
        npm_available = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            timeout=5
        ).returncode == 0
        
        if npm_available:
            print_status("   ", "Using npm as fallback...", verbose)
            cmd = ["npm"]
        else:
            print_status("❌", f"{name}: Neither bun nor npm available")
            return False
    
    # Install dependencies
    success, _, stderr = run_cmd(
        cmd + ["install"],
        plugin_dir,
        timeout=180
    )
    
    if not success:
        print_status("❌", f"{name}: Install failed - {stderr}")
        return False
    
    # Build
    success, _, stderr = run_cmd(
        cmd + (["run", "build"] if cmd[0] == "bun" else ["run", "build"]),
        plugin_dir,
        timeout=120
    )
    
    if success:
        print_status("✅", f"{name}: Built successfully")
    else:
        print_status("❌", f"{name}: Build failed - {stderr}")
    
    return success


# ============================================================================
# 主函数
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Sync OpenCode embedded repositories"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force sync (git reset --hard)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip building plugins"
    )
    parser.add_argument(
        "--repo",
        choices=list(REPOS.keys()),
        help="Sync specific repo only"
    )
    
    args = parser.parse_args()
    
    # 检查 libs 目录
    if not LIBS_DIR:
        print("❌ Cannot find libs directory")
        sys.exit(1)
    
    print("=" * 60)
    print("OpenCode Embedded Repository Sync")
    print("=" * 60)
    print(f"Libs directory: {LIBS_DIR}")
    print(f"Mode: {'Force' if args.force else 'Normal'}")
    print()
    
    # 同步仓库
    repos_to_sync = {args.repo: REPOS[args.repo]} if args.repo else REPOS
    
    results = {}
    for name, info in repos_to_sync.items():
        print()
        success = sync_repo(
            name, info, LIBS_DIR,
            force=args.force,
            verbose=args.verbose
        )
        results[name] = success
        
        # 构建插件
        if success and not args.no_build and name == "oh-my-opencode":
            print()
            results[f"{name}_build"] = build_plugin(name, LIBS_DIR, args.verbose)
    
    # 总结
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    for name, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    print()
    print(f"Total: {success_count}/{total_count} succeeded")
    
    sys.exit(0 if success_count == total_count else 1)


if __name__ == "__main__":
    main()
