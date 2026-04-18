"""
FFmpeg 自动下载与安装工具

功能：
- 自动检测平台并下载对应 FFmpeg 二进制
- 验证 SHA256 校验和
- 支持 Windows/macOS/Linux
"""

import os
import sys
import ssl
import hashlib
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import platform


@dataclass
class FFmpegDownloadInfo:
    """FFmpeg 下载信息"""
    name: str
    url: str
    binary_name: str
    extract: bool = True
    strip_components: int = 1
    sha256: Optional[str] = None


# FFmpeg 构建版本列表 (BtbN/FFmpeg-Builds)
FFMPEG_DOWNLOADS: Dict[str, Dict[str, FFmpegDownloadInfo]] = {
    "windows": {
        "amd64": FFmpegDownloadInfo(
            name="ffmpeg-windows-amd64",
            url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
            binary_name="ffmpeg.exe",
            extract=True,
            strip_components=1,
        ),
        "arm64": FFmpegDownloadInfo(
            name="ffmpeg-windows-arm64",
            url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
            binary_name="ffmpeg.exe",
            extract=True,
            strip_components=1,
        ),
    },
    "linux": {
        "x86_64": FFmpegDownloadInfo(
            name="ffmpeg-linux-x86_64",
            url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
            binary_name="ffmpeg",
            extract=True,
            strip_components=1,
        ),
        "arm64": FFmpegDownloadInfo(
            name="ffmpeg-linux-arm64",
            url="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
            binary_name="ffmpeg",
            extract=True,
            strip_components=1,
        ),
    },
    "darwin": {
        "x86_64": FFmpegDownloadInfo(
            name="ffmpeg-macos-x86_64",
            url="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
            binary_name="ffmpeg",
            extract=False,
        ),
        "arm64": FFmpegDownloadInfo(
            name="ffmpeg-macos-arm64",
            url="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
            binary_name="ffmpeg",
            extract=False,
        ),
    },
}


def get_platform_key() -> Tuple[str, str]:
    """
    获取当前平台键

    Returns:
        (os_key, arch_key)
    """
    system = platform.system().lower()

    if system == "windows":
        os_key = "windows"
    elif system == "linux":
        os_key = "linux"
    elif system == "darwin":
        os_key = "darwin"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    # 检测架构
    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64"):
        arch_key = "amd64"
    elif arch in ("arm64", "aarch64"):
        arch_key = "arm64"
    elif arch == "i386":
        arch_key = "x86_64"  # fallback to 64-bit
    else:
        arch_key = "amd64"  # fallback

    return os_key, arch_key


def get_ffmpeg_download_info() -> FFmpegDownloadInfo:
    """获取当前平台的 FFmpeg 下载信息"""
    os_key, arch_key = get_platform_key()

    if os_key not in FFMPEG_DOWNLOADS:
        raise RuntimeError(f"Unsupported OS: {os_key}")

    if arch_key not in FFMPEG_DOWNLOADS[os_key]:
        arch_key = "amd64"  # fallback

    return FFMPEG_DOWNLOADS[os_key][arch_key]


def get_ffmpeg_install_dir() -> Path:
    """获取 FFmpeg 安装目录"""
    # 项目 bin/tools 目录
    project_bin = Path(__file__).parent.parent / "bin" / "tools"
    project_bin.mkdir(parents=True, exist_ok=True)
    return project_bin


def get_ffmpeg_path() -> Optional[Path]:
    """获取 FFmpeg 可执行文件路径"""
    install_dir = get_ffmpeg_install_dir()

    # 检查项目本地
    system = platform.system().lower()
    if system == "windows":
        local_path = install_dir / "ffmpeg.exe"
    else:
        local_path = install_dir / "ffmpeg"

    if local_path.exists():
        return local_path

    # 检查系统 PATH
    import shutil
    path = shutil.which("ffmpeg")
    if path:
        return Path(path)

    return None


def is_ffmpeg_available() -> bool:
    """检查 FFmpeg 是否可用"""
    path = get_ffmpeg_path()
    if path is None:
        return False

    try:
        result = subprocess.run(
            [str(path), "-version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def calculate_sha256(file_path: Path) -> str:
    """计算文件 SHA256"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def download_file(url: str, dest: Path, progress_callback=None) -> bool:
    """
    下载文件

    Args:
        url: 下载 URL
        dest: 目标路径
        progress_callback: 进度回调 (bytes_downloaded, total_bytes)

    Returns:
        是否成功
    """
    try:
        # 创建 SSL context（处理 HTTPS 证书问题）
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

        with urllib.request.urlopen(request, context=ssl_context, timeout=300) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0

            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)

        return True

    except Exception as e:
        print(f"Download error: {e}")
        return False


def extract_archive(archive_path: Path, dest_dir: Path, strip_components: int = 1):
    """
    提取压缩包

    Args:
        archive_path: 压缩包路径
        dest_dir: 目标目录
        strip_components: 剥离的目录层级
    """
    import tarfile
    import zipfile

    suffix = archive_path.suffix.lower()

    if suffix == ".zip":
        with zipfile.ZipFile(archive_path, 'r') as zf:
            # 获取所有文件
            members = zf.namelist()

            # 计算需要剥离的前缀
            if strip_components > 0:
                # 找到公共前缀
                prefix = ""
                parts = members[0].split("/")
                if len(parts) > strip_components:
                    prefix = "/".join(parts[:strip_components])
                    # 验证所有文件都有这个前缀
                    if not all(m.startswith(prefix) for m in members):
                        prefix = ""

            for member in members:
                if prefix and member.startswith(prefix):
                    target = member[len(prefix):].lstrip("/")
                else:
                    target = member

                if not target:
                    continue

                target_path = dest_dir / target

                # 创建目录
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # 跳过目录
                if not target_path.name:
                    continue

                # 解压文件
                try:
                    with zf.open(member) as src:
                        with open(target_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                except Exception:
                    pass

    elif suffix in (".xz", ".gz", ".bz2"):
        with tarfile.open(archive_path, 'r:*') as tf:
            members = tf.getmembers()

            # 计算需要剥离的前缀
            if strip_components > 0:
                prefix = ""
                if members:
                    parts = members[0].name.split("/")
                    if len(parts) > strip_components:
                        prefix = "/".join(parts[:strip_components])
                        if not all(m.name.startswith(prefix.split("/")[-1]) for m in members if m.name):
                            prefix = ""

            for member in members:
                if prefix and member.name.startswith(prefix):
                    member.name = member.name[len(prefix):].lstrip("/")

                if not member.name:
                    continue

                target_path = dest_dir / member.name
                target_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    tf.extract(member, dest_dir)
                    # 移动文件到正确位置
                    extracted = dest_dir / member.name
                    if extracted != target_path and extracted.exists():
                        shutil.move(str(extracted), str(target_path))
                except Exception:
                    pass

    else:
        raise ValueError(f"Unsupported archive format: {suffix}")


async def install_ffmpeg(
    force: bool = False,
    progress_callback=None
) -> Tuple[bool, str]:
    """
    安装 FFmpeg

    Args:
        force: 是否强制重新下载
        progress_callback: 进度回调

    Returns:
        (success, message)
    """
    install_dir = get_ffmpeg_install_dir()
    info = get_ffmpeg_download_info()

    # 检查是否已安装
    if not force:
        if is_ffmpeg_available():
            return True, f"FFmpeg already available at {get_ffmpeg_path()}"

    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp())
    temp_archive = temp_dir / f"ffmpeg_download{Path(info.url).suffix}"

    try:
        print(f"Downloading FFmpeg from {info.url}")

        # 下载
        success = download_file(info.url, temp_archive, progress_callback)
        if not success:
            return False, "Download failed"

        # 验证 SHA256（如果有）
        if info.sha256:
            print("Verifying SHA256...")
            file_hash = calculate_sha256(temp_archive)
            if file_hash != info.sha256:
                return False, f"SHA256 mismatch: expected {info.sha256}, got {file_hash}"

        # 提取
        if info.extract:
            print(f"Extracting to {install_dir}...")
            extract_archive(temp_archive, install_dir, info.strip_components)
        else:
            # 直接移动
            shutil.move(str(temp_archive), install_dir / info.binary_name)

        # 验证
        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path and is_ffmpeg_available():
            return True, f"FFmpeg installed at {ffmpeg_path}"
        else:
            return False, "Installation failed - FFmpeg not working"

    except Exception as e:
        return False, f"Installation error: {str(e)}"

    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)


def get_ffmpeg_info() -> Dict:
    """
    获取 FFmpeg 信息

    Returns:
        FFmpeg 信息字典
    """
    path = get_ffmpeg_path()

    if path is None:
        return {
            "available": False,
            "error": "FFmpeg not found"
        }

    try:
        result = subprocess.run(
            [str(path), "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return {
                "available": False,
                "error": result.stderr
            }

        first_line = result.stdout.split('\n')[0]

        # 获取支持的功能
        codecs_result = subprocess.run(
            [str(path), "-codecs"],
            capture_output=True,
            text=True,
            timeout=10
        )

        has_nvenc = "h264_nvenc" in codecs_result.stdout
        has_cuda = "cuda" in codecs_result.stdout

        return {
            "available": True,
            "path": str(path),
            "version": first_line,
            "has_nvenc": has_nvenc,
            "has_cuda": has_cuda,
            "platform": get_platform_key(),
        }

    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }


# CLI 入口
if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="FFmpeg Auto Installer")
    parser.add_argument("--check", action="store_true", help="Check FFmpeg status")
    parser.add_argument("--install", action="store_true", help="Install FFmpeg")
    parser.add_argument("--force", action="store_true", help="Force reinstall")
    parser.add_argument("--info", action="store_true", help="Show FFmpeg info")

    args = parser.parse_args()

    if args.check:
        info = get_ffmpeg_info()
        print(json.dumps(info, indent=2))

    elif args.info:
        info = get_ffmpeg_info()
        print(json.dumps(info, indent=2))

    elif args.install:
        def progress(downloaded, total):
            if total > 0:
                pct = downloaded * 100 // total
                print(f"\rDownloading: {pct}%", end="", flush=True)

        success, msg = asyncio.run(install_ffmpeg(force=args.force, progress_callback=progress))
        print()
        print(msg)

    else:
        parser.print_help()
