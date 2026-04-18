"""
Pion TURN 服务器配置工具

用于在 Windows Server 上部署 simple-turn 中继服务
"""

import asyncio
import logging
import os
import subprocess
import sys
import urllib.request
import zipfile
import tarfile
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class TurnServerConfig:
    """TURN 服务器配置"""

    def __init__(self,
                 host: str = "0.0.0.0",
                 port: int = 3478,
                 users: Optional[List[tuple]] = None,
                 realm: str = "hermes",
                 min_port: int = 49152,
                 max_port: int = 65535,
                 cert_file: str = "",
                 key_file: str = ""):
        self.host = host
        self.port = port
        self.users = users or [("hermes", "hermes123")]
        self.realm = realm
        self.min_port = min_port
        self.max_port = max_port
        self.cert_file = cert_file
        self.key_file = key_file

    def to_env(self) -> dict:
        env = os.environ.copy()
        env["TURN_LISTEN"] = f"{self.host}:{self.port}"
        env["REALM"] = self.realm
        env["USERS"] = ",".join(f"{u}={p}" for u, p in self.users)
        env["MIN_PORT"] = str(self.min_port)
        env["MAX_PORT"] = str(self.max_port)
        if self.cert_file:
            env["CERT_FILE"] = self.cert_file
        if self.key_file:
            env["KEY_FILE"] = self.key_file
        return env

    def to_cli_args(self) -> List[str]:
        args = [
            "--listen", f"{self.host}:{self.port}",
            "--realm", self.realm,
            "--min-port", str(self.min_port),
            "--max-port", str(self.max_port),
        ]
        for u, p in self.users:
            args.extend(["--user", f"{u}:{p}"])
        if self.cert_file:
            args.extend(["--cert", self.cert_file])
        if self.key_file:
            args.extend(["--key", self.key_file])
        return args


class PionTurnManager:
    """Pion Simple-TURN 管理器"""

    RELEASES = {
        "windows_amd64": "https://github.com/pion/simple-turn/releases/download/v2.4.0/simple-turn-windows-amd64.zip",
        "linux_amd64": "https://github.com/pion/simple-turn/releases/download/v2.4.0/simple-turn-linux-amd64.tar.gz",
    }

    def __init__(self, install_dir: str = ""):
        self.install_dir = Path(install_dir) if install_dir else Path.home() / ".hermes-desktop" / "turn"
        self.binary_path = self.install_dir / "simple-turn.exe" if sys.platform == "win32" else self.install_dir / "simple-turn"

    def get_platform(self) -> str:
        import platform
        system = platform.system().lower()
        if system == "windows":
            return "windows_amd64"
        elif system == "linux":
            return "linux_amd64"
        return "linux_amd64"

    async def download(self, progress_callback=None) -> bool:
        """下载 simple-turn 二进制"""
        platform_key = self.get_platform()
        url = self.RELEASES.get(platform_key)
        if not url:
            logger.error(f"不支持的平台: {platform_key}")
            return False

        self.install_dir.mkdir(parents=True, exist_ok=True)
        ext = "zip" if "windows" in platform_key else "tar.gz"
        archive_path = self.install_dir / f"turn_archive.{ext}"

        try:
            logger.info(f"下载 simple-turn from {url}")
            urllib.request.urlretrieve(url, archive_path, progress_callback)

            if "windows" in platform_key:
                with zipfile.ZipFile(archive_path, 'r') as z:
                    z.extractall(self.install_dir)
            else:
                with tarfile.open(archive_path, 'r:gz') as t:
                    t.extractall(self.install_dir)

            archive_path.unlink()
            logger.info(f"安装完成: {self.binary_path}")
            return True
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False

    def is_installed(self) -> bool:
        return self.binary_path.exists()

    def start(self, config: TurnServerConfig, log_file: str = "") -> subprocess.Popen:
        """启动 TURN 服务器"""
        if not self.is_installed():
            raise RuntimeError("simple-turn 未安装")

        cmd = [str(self.binary_path)] + config.to_cli_args()
        logger.info(f"启动 TURN: {' '.join(cmd)}")

        log_fd = open(log_file, "a") if log_file else None
        process = subprocess.Popen(cmd, env=config.to_env(), stdout=log_fd, stderr=subprocess.STDOUT)
        return process

    def stop(self, process: subprocess.Popen):
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


async def install_and_start(host: str = "0.0.0.0", port: int = 3478,
                           user: str = "hermes", password: str = "hermes123",
                           realm: str = "hermes") -> tuple:
    """一键安装并启动 TURN"""
    manager = PionTurnManager()

    if not manager.is_installed():
        print("下载 simple-turn...")
        if not await manager.download():
            return False, "下载失败"

    config = TurnServerConfig(host=host, port=port, users=[(user, password)], realm=realm)
    log_path = manager.install_dir / "turn.log"

    try:
        process = manager.start(config, log_file=str(log_path))
        await asyncio.sleep(1)
        if process.poll() is not None:
            return False, "启动失败"

        return True, f"TURN 已启动 (PID: {process.pid})\n日志: {log_path}"
    except Exception as e:
        return False, f"启动异常: {e}"


def generate_longterm_credential(username: str, password: str, hours: int = 24) -> str:
    """生成长期凭证"""
    import hashlib
    import hmac
    import base64
    import time

    timestamp = int(time.time()) + hours * 3600
    credentials = f"{username}:{timestamp}"
    key = password.encode()
    mac = hmac.new(key, credentials.encode(), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    import argparse
    parser = argparse.ArgumentParser(description="Pion TURN 管理")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3478)
    parser.add_argument("--user", default="hermes")
    parser.add_argument("--password", default="hermes123")
    parser.add_argument("--realm", default="hermes")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()

    if args.download_only:
        manager = PionTurnManager()
        success = asyncio.run(manager.download())
        sys.exit(0 if success else 1)

    success, msg = asyncio.run(install_and_start(
        host=args.host, port=args.port, user=args.user,
        password=args.password, realm=args.realm
    ))
    print(msg)
    sys.exit(0 if success else 1)
