"""OpenCode Launcher — Self-contained local install + auto-serve.

Everything lives in `.livingtree/` — zero global pollution.

Directory layout:
    .livingtree/
    ├── nodejs/          ← portable Node.js (auto-downloaded)
    ├── opencode/        ← local npm install (no -g)
    └── opencode_serve.pid

Workflow:
    1. Auto-detect/download portable Node.js → .livingtree/nodejs/
    2. Local install opencode → .livingtree/opencode/node_modules/
    3. Auto-start serve on LivingTree boot
    4. Health check → skip if already running
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger


class OpenCodeLauncher:

    SERVE_PORT = 4096
    NODE_VERSION = "v22.11.0"
    NODE_URL = f"https://nodejs.org/dist/{NODE_VERSION}/node-{NODE_VERSION}-win-x64.zip"

    def __init__(self, workspace: str = ".", hub=None):
        self._hub = hub
        self._workspace = self._resolve_workspace(workspace)
        self._livingtree = self._workspace / ".livingtree"
        self._base = self._livingtree / "base"
        self._node_dir = self._base / "nodejs"
        self._opencode_dir = self._base / "opencode"
        self._node_exe = self._node_dir / "node.exe"
        self._npm_cmd = self._node_dir / "npm.cmd"
        self._opencode_bin = (
            self._opencode_dir / "opencode.exe" if sys.platform == "win32"
            else self._opencode_dir / "opencode"
        )
        self._opencode_npm_bin = self._opencode_dir / "node_modules" / ".bin" / "opencode"
        self._wt_path = self._find_wt()
        self._serve_process: asyncio.subprocess.Process | None = None

    # ── Public ──

    async def ensure_nodejs(self, on_progress=None) -> bool:
        if self._node_exe.exists() and self._npm_cmd.exists():
            return True

        try:
            from .setup_base import is_base_ready, setup_base
            if is_base_ready(self._workspace):
                return True
        except ImportError:
            pass

        if on_progress:
            on_progress("Downloading Node.js (portable, no install)...")

        try:
            import urllib.request, zipfile
            self._node_dir.mkdir(parents=True, exist_ok=True)

            zip_path = self._node_dir / "node.zip"
            self._log("Downloading Node.js...")

            urllib.request.urlretrieve(self.NODE_URL, str(zip_path))

            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zf.extractall(str(self._node_dir))

            zip_path.unlink()

            node_subdir = list(self._node_dir.glob("node-v*"))
            if not node_subdir:
                return False

            node_src = node_subdir[0]
            for item in node_src.iterdir():
                dest = self._node_dir / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
            shutil.rmtree(str(node_src), ignore_errors=True)

            self._node_exe.chmod(0o755) if sys.platform != "win32" else None
            self._log("Node.js ready")

            return self._node_exe.exists()

        except Exception as e:
            self._log(f"Node.js download failed: {e}")
            return False

    async def ensure_opencode(self, on_progress=None) -> bool:
        if self._opencode_bin.exists():
            return True

        system_opencode = shutil.which("opencode") or (
            shutil.which("opencode.exe") if sys.platform == "win32" else None
        )
        if system_opencode:
            if on_progress:
                on_progress("Caching opencode from system...")
            self._opencode_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(system_opencode, str(self._opencode_bin))
            self._log(f"opencode cached from {system_opencode}")
            return True

        if not await self.ensure_nodejs(on_progress):
            return False

        if self._opencode_npm_bin.exists():
            return True

        if on_progress:
            on_progress("Installing opencode via npm...")

        self._opencode_dir.mkdir(parents=True, exist_ok=True)

        try:
            env = os.environ.copy()
            env["PATH"] = str(self._node_dir) + os.pathsep + env.get("PATH", "")
            env["npm_config_prefix"] = str(self._opencode_dir)

            proc = await asyncio.create_subprocess_exec(
                str(self._npm_cmd), "install", "--prefix", str(self._opencode_dir),
                "opencode", "--no-save",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)

            if self._opencode_npm_bin.exists():
                self._log("opencode installed via npm")
                return True

            self._log(f"npm install failed (rc={proc.returncode})")
            return False

        except asyncio.TimeoutError:
            return False
        except Exception as e:
            self._log(f"opencode install failed: {e}")
            return False

    async def is_serve_running(self) -> bool:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"http://localhost:{self.SERVE_PORT}/health",
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def auto_start_serve(self, on_progress=None) -> tuple[bool, str]:
        if await self.is_serve_running():
            return True, "opencode serve already running"

        if not await self.ensure_opencode(on_progress):
            return False, "opencode not available"

        if on_progress:
            on_progress("Starting opencode serve...")

        return await self._start_serve()

    async def auto_start_serve_if_needed(self, on_progress=None) -> tuple[bool, str]:
        if await self.is_serve_running():
            return True, "opencode serve already running"
        return await self.auto_start_serve(on_progress)

    async def launch_tui(self, on_progress=None) -> tuple[bool, str]:
        if not await self.ensure_opencode(on_progress):
            return False, "opencode not available"

        if on_progress:
            on_progress("Launching opencode TUI...")

        return await self._launch_tui()

    async def shutdown_serve(self) -> None:
        if self._serve_process:
            try:
                self._serve_process.terminate()
                await asyncio.wait_for(self._serve_process.wait(), timeout=5)
            except Exception:
                try:
                    self._serve_process.kill()
                except Exception:
                    pass
            self._serve_process = None

    def node_path(self) -> str:
        return str(self._node_dir)

    def opencode_bin_path(self) -> str:
        if self._opencode_bin.exists():
            return str(self._opencode_bin)
        if self._opencode_npm_bin.exists():
            return str(self._opencode_npm_bin)
        return "opencode"

    def _opencode_exe(self) -> str:
        return self.opencode_bin_path()

    # ── Private ──

    async def _start_serve(self) -> tuple[bool, str]:
        env = os.environ.copy()
        env["PATH"] = str(self._node_dir) + os.pathsep + env.get("PATH", "")

        if self._hub and hasattr(self._hub, 'config'):
            c = self._hub.config.model
            if c.deepseek_api_key:
                env["DEEPSEEK_API_KEY"] = c.deepseek_api_key
            if c.longcat_api_key:
                env["LONGCAT_API_KEY"] = c.longcat_api_key
        env["LIVINGTREE_WORKSPACE"] = str(self._workspace)

        try:
            self._serve_process = await asyncio.create_subprocess_exec(
                self._opencode_exe(), "serve",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._workspace),
                env=env,
            )

            for i in range(20):
                await asyncio.sleep(0.5)
                if await self.is_serve_running():
                    self._log("opencode serve started")
                    return True, f"opencode serve ready on :{self.SERVE_PORT}"
                if self._serve_process.returncode is not None:
                    stderr = ""
                    try:
                        stderr = (await self._serve_process.stderr.read()).decode(errors="replace")[:200]
                    except Exception:
                        pass
                    return False, f"opencode serve exited ({self._serve_process.returncode}): {stderr}"

            return True, f"opencode serve starting (pid={self._serve_process.pid})"

        except Exception as e:
            return False, str(e)

    async def _launch_tui(self) -> tuple[bool, str]:
        env = os.environ.copy()
        env["PATH"] = str(self._node_dir) + os.pathsep + env.get("PATH", "")
        ws = str(self._workspace)

        if self._hub and hasattr(self._hub, 'config'):
            c = self._hub.config.model
            if c.deepseek_api_key:
                env["DEEPSEEK_API_KEY"] = c.deepseek_api_key
            if c.longcat_api_key:
                env["LONGCAT_API_KEY"] = c.longcat_api_key

        if self._wt_path:
            try:
                subprocess.Popen(
                    [
                        str(self._wt_path), "-d", ws,
                        "--title", f"OpenCode · {Path(ws).name}",
                        self._opencode_exe(),
                    ],
                    env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
                )
                return True, "OpenCode TUI launched"
            except Exception:
                pass

        try:
            cmd = f'start "OpenCode" cmd /k "cd /d {ws} && {"%s" % self._opencode_bin if self._opencode_bin.exists() else "opencode"}"'
            subprocess.Popen(cmd, shell=True, env=env)
            return True, "OpenCode TUI launched"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _resolve_workspace(workspace: str) -> Path:
        path = Path(workspace)
        if path.is_absolute():
            return path.resolve()
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, cwd=str(workspace), timeout=5,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except Exception:
            pass
        return Path(workspace).resolve()

    @staticmethod
    def _find_wt() -> Path | None:
        local = Path(".wt") / "WindowsTerminal.exe"
        if local.exists():
            return local.resolve()
        return None

    def _log(self, msg: str) -> None:
        logger.debug(f"[OpenCode] {msg}")
