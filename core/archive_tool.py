"""
Archive Tool - NanaZip/7z 压缩/解压引擎封装
用于 Hermes Desktop 桌面客户端

核心功能:
- 压缩/解压 7z/zip/tar/gz 等格式
- 子进程异步执行
- 进度回调
- 智能回退 (NanaZip → 7zip → python zipfile)
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

# psutil 是可选依赖
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ============= 常量定义 =============

class ArchiveFormat(Enum):
    """支持的压缩格式"""
    SEVENZ = ("7z", "7-zip", ".7z")
    ZIP = ("zip", "zip", ".zip")
    TAR = ("tar", "tar", ".tar")
    TAR_GZ = ("tar.gz", "tar gzip", ".tar.gz")
    TAR_BZ2 = ("tar.bz2", "tar bzip2", ".tar.bz2")
    TAR_XZ = ("tar.xz", "tar xz", ".tar.xz")
    WIM = ("wim", "wim", ".wim")
    GZ = ("gz", "gzip", ".gz")
    BZ2 = ("bz2", "bzip2", ".bz2")
    XZ = ("xz", "xz", ".xz")

    def __init__(self, id: str, display_name: str, ext: str):
        self.id = id
        self.display_name = display_name
        self.ext = ext

    @classmethod
    def from_ext(cls, ext: str) -> "ArchiveFormat":
        """根据扩展名获取格式"""
        ext = ext.lower().lstrip(".")
        for fmt in cls:
            if fmt.ext.lstrip(".") == ext or ext in fmt.id:
                return fmt
        return cls.ZIP  # 默认 ZIP


class CompressionLevel(Enum):
    """压缩级别"""
    STORE = ("0", "仅存储")
    FASTEST = ("1", "最快")
    FAST = ("3", "快速")
    NORMAL = ("5", "标准")
    MAXIMUM = ("7", "最大")
    ULTRA = ("9", "极限")

    def __init__(self, flag: str, desc: str):
        self.flag = flag
        self.desc = desc


# ============= 数据模型 =============

@dataclass
class ArchiveTask:
    """压缩/解压任务"""
    task_id: str
    operation: str  # "compress" or "extract"
    source: str
    output: str
    format: ArchiveFormat = ArchiveFormat.ZIP
    level: CompressionLevel = CompressionLevel.NORMAL
    password: Optional[str] = None
    split_size: Optional[int] = None  # 分卷大小 (bytes)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending/running/completed/failed/cancelled
    progress: float = 0.0  # 0.0 ~ 1.0
    error: Optional[str] = None
    output_size: Optional[int] = None  # bytes
    source_size: Optional[int] = None  # bytes
    stdout: str = ""
    stderr: str = ""


@dataclass
class ArchiveConfig:
    """压缩配置"""
    binary_path: Optional[str] = None
    compression_level: CompressionLevel = CompressionLevel.NORMAL
    dictionary_size: str = "64mb"
    threads: int = 0  # 0 = auto
    solid_archive: bool = True
    show_progress: bool = True

    @property
    def thread_count(self) -> int:
        if self.threads > 0:
            return self.threads
        if HAS_PSUTIL:
            return psutil.cpu_count(logical=True) or 4
        return 4  # 默认4线程


# ============= 核心类 =============

class ArchiveTool:
    """
    压缩/解压工具封装
    支持 NanaZip (Windows 优先) / 7zip / 系统 zipfile 回退
    """

    def __init__(self, config: Optional[ArchiveConfig] = None):
        self.config = config or ArchiveConfig()
        self._binary_path: Optional[str] = None
        self._available: bool = False
        self._backend: str = "none"  # nanazip / 7zip / python
        self._tasks: dict[str, ArchiveTask] = {}
        self._progress_callback: Optional[Callable[[str, float], None]] = None

    # ── 初始化 ─────────────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """初始化工具，检测可用后端"""
        # 1. 尝试 NanaZip
        self._binary_path = self._find_nanazip()
        if self._binary_path:
            self._backend = "nanazip"
            self._available = True
            return True

        # 2. 尝试 7zip
        self._binary_path = self._find_7zip()
        if self._binary_path:
            self._backend = "7zip"
            self._available = True
            return True

        # 3. 回退到 Python zipfile
        self._backend = "python"
        self._available = True
        return True

    def _find_nanazip(self) -> Optional[str]:
        """查找 NanaZip 可执行文件"""
        # 优先从配置路径
        if self.config.binary_path and Path(self.config.binary_path).exists():
            return self.config.binary_path

        # 从工具目录
        tool_dir = self._get_tool_dir()
        nanazip_path = tool_dir / "NanaZip.exe"
        if nanazip_path.exists():
            return str(nanazip_path)

        # 从 PATH
        for path in os.environ.get("PATH", "").split(os.pathsep):
            p = Path(path) / "NanaZip.exe"
            if p.exists():
                return str(p)

        return None

    def _find_7zip(self) -> Optional[str]:
        """查找 7zip 可执行文件"""
        paths = [
            Path("C:/Program Files/7-Zip/7z.exe"),
            Path("C:/Program Files (x86)/7-Zip/7z.exe"),
        ]
        for p in paths:
            if p.exists():
                return str(p)

        # 从 PATH
        for path in os.environ.get("PATH", "").split(os.pathsep):
            p = Path(path) / "7z.exe"
            if p.exists():
                return str(p)

        return None

    def _get_tool_dir(self) -> Path:
        """获取工具目录"""
        base = Path(os.environ.get("HERMES_TOOLS", "~/.hermes-desktop/tools")).expanduser()
        return base / "nanazip"

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def backend(self) -> str:
        return self._backend

    # ── 压缩 ──────────────────────────────────────────────────────────

    async def compress(
        self,
        source: str,
        output: str,
        format: ArchiveFormat = ArchiveFormat.ZIP,
        level: CompressionLevel = CompressionLevel.NORMAL,
        password: Optional[str] = None,
        split_size: Optional[int] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> ArchiveTask:
        """
        压缩文件或目录

        Args:
            source: 源文件或目录路径
            output: 输出压缩包路径
            format: 压缩格式
            level: 压缩级别
            password: 密码 (可选)
            split_size: 分卷大小 bytes (可选)
            progress_callback: 进度回调

        Returns:
            ArchiveTask: 任务结果
        """
        task = ArchiveTask(
            task_id=self._generate_id(),
            operation="compress",
            source=str(Path(source).absolute()),
            output=str(Path(output).absolute()),
            format=format,
            level=level,
            password=password,
            split_size=split_size,
        )
        task.source_size = self._get_size(source)
        self._tasks[task.task_id] = task
        self._progress_callback = progress_callback

        try:
            task.status = "running"
            task.started_at = datetime.now()

            if self._backend == "python":
                await self._compress_python(task)
            else:
                await self._compress_cli(task)

            task.status = "completed"
            task.completed_at = datetime.now()
            task.progress = 1.0
            task.output_size = self._get_size(output)

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()

        return task

    async def _compress_cli(self, task: ArchiveTask) -> None:
        """使用 CLI 工具压缩"""
        cmd = self._build_compress_cmd(task)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        task.stdout = stdout.decode(errors="ignore")
        task.stderr = stderr.decode(errors="ignore")

        if proc.returncode != 0:
            raise RuntimeError(f"压缩失败: {task.stderr or task.stdout}")

    def _build_compress_cmd(self, task: ArchiveTask) -> list[str]:
        """构建压缩命令"""
        cmd = [self._binary_path, "a"]  # Add

        # 格式
        cmd.extend(["-t" + task.format.id])

        # 压缩级别
        cmd.append("-mx=" + task.level.flag)

        # 线程数
        if self.config.threads > 0:
            cmd.extend(["-mmt=" + str(self.config.threads)])

        # 密码
        if task.password:
            cmd.extend(["-p" + task.password])

        # 分卷
        if task.split_size:
            # -v{size} 格式如 -v100m
            size_mb = task.split_size // (1024 * 1024)
            cmd.append(f"-v{size_mb}m")

        # 输出文件
        cmd.append(task.output)

        # 源文件
        src_path = Path(task.source)
        if src_path.is_dir():
            cmd.append(str(src_path / "*"))
        else:
            cmd.append(task.source)

        return cmd

    async def _compress_python(self, task: ArchiveTask) -> None:
        """使用 Python zipfile 压缩 (最后回退)"""
        import zipfile

        output_path = Path(task.output)
        source_path = Path(task.source)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if source_path.is_dir():
                for file in source_path.rglob("*"):
                    if file.is_file():
                        arcname = file.relative_to(source_path.parent)
                        zf.write(file, arcname)
                        await asyncio.sleep(0)  # 让出控制权
            else:
                zf.write(source_path, source_path.name)

    # ── 解压 ──────────────────────────────────────────────────────────

    async def extract(
        self,
        archive: str,
        output_dir: str,
        password: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> ArchiveTask:
        """
        解压压缩包

        Args:
            archive: 压缩包路径
            output_dir: 输出目录
            password: 密码 (可选)
            progress_callback: 进度回调

        Returns:
            ArchiveTask: 任务结果
        """
        task = ArchiveTask(
            task_id=self._generate_id(),
            operation="extract",
            source=str(Path(archive).absolute()),
            output=str(Path(output_dir).absolute()),
            password=password,
        )
        task.source_size = self._get_size(archive)
        self._tasks[task.task_id] = task
        self._progress_callback = progress_callback

        try:
            task.status = "running"
            task.started_at = datetime.now()

            if self._backend == "python":
                await self._extract_python(task)
            else:
                await self._extract_cli(task)

            task.status = "completed"
            task.completed_at = datetime.now()
            task.progress = 1.0

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()

        return task

    async def _extract_cli(self, task: ArchiveTask) -> None:
        """使用 CLI 工具解压"""
        cmd = self._build_extract_cmd(task)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        task.stdout = stdout.decode(errors="ignore")
        task.stderr = stderr.decode(errors="ignore")

        if proc.returncode != 0:
            raise RuntimeError(f"解压失败: {task.stderr or task.stdout}")

    def _build_extract_cmd(self, task: ArchiveTask) -> list[str]:
        """构建解压命令"""
        cmd = [self._binary_path, "x"]  # Extract with full paths

        # 覆盖已存在文件
        cmd.append("-y")

        # 密码
        if task.password:
            cmd.extend(["-p" + task.password])

        # 输出目录
        cmd.extend(["-o" + task.output])

        # 源文件
        cmd.append(task.source)

        return cmd

    async def _extract_python(self, task: ArchiveTask) -> None:
        """使用 Python zipfile 解压 (最后回退)"""
        import zipfile

        archive_path = Path(task.source)
        output_path = Path(task.output)
        output_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(output_path)

    # ── 工具方法 ──────────────────────────────────────────────────────

    async def list_contents(self, archive: str) -> list[dict]:
        """列出压缩包内容"""
        if self._backend == "python":
            return await self._list_python(archive)
        return await self._list_cli(archive)

    async def _list_cli(self, archive: str) -> list[dict]:
        """使用 CLI 列出内容"""
        cmd = [self._binary_path, "l", archive]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="ignore")

        # 简单解析 7z list 输出
        files = []
        for line in output.split("\n"):
            if line.startswith("   "):
                parts = line.split()
                if len(parts) >= 5:
                    files.append({
                        "name": " ".join(parts[3:]),
                        "size": parts[1] if len(parts) > 1 else "0",
                        "modified": " ".join(parts[2:3]) if len(parts) > 2 else "",
                    })
        return files

    async def _list_python(self, archive: str) -> list[dict]:
        """使用 Python 列出内容"""
        import zipfile
        files = []
        with zipfile.ZipFile(archive, "r") as zf:
            for info in zf.infolist():
                files.append({
                    "name": info.filename,
                    "size": str(info.file_size),
                    "modified": datetime(*info.date_time).isoformat() if info.date_time else "",
                })
        return files

    async def test_archive(self, archive: str, password: Optional[str] = None) -> bool:
        """测试压缩包完整性"""
        if self._backend == "python":
            import zipfile
            try:
                with zipfile.ZipFile(archive, "r") as zf:
                    zf.testzip()
                return True
            except Exception:
                return False

        cmd = [self._binary_path, "t", archive]
        if password:
            cmd.extend(["-p" + password])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    def get_task(self, task_id: str) -> Optional[ArchiveTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if task and task.status in ("pending", "running"):
            task.status = "cancelled"
            return True
        return False

    # ── 辅助方法 ──────────────────────────────────────────────────────

    @staticmethod
    def _generate_id() -> str:
        import uuid
        return f"arc_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _get_size(path: str) -> int:
        """获取文件或目录大小"""
        p = Path(path)
        if not p.exists():
            return 0
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

    @staticmethod
    def format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @staticmethod
    def guess_format(filename: str) -> ArchiveFormat:
        """根据文件名猜测格式"""
        ext = Path(filename).suffix
        return ArchiveFormat.from_ext(ext)


# ============= 全局单例 =============

_archive_tool: Optional[ArchiveTool] = None


def get_archive_tool() -> ArchiveTool:
    """获取全局 ArchiveTool 实例"""
    global _archive_tool
    if _archive_tool is None:
        _archive_tool = ArchiveTool()
    return _archive_tool


async def init_archive_tool() -> ArchiveTool:
    """初始化并返回 ArchiveTool"""
    tool = get_archive_tool()
    await tool.initialize()
    return tool
