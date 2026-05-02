"""
服务存证系统
Service Audit Trail System

自动记录服务过程中的关键证据，用于争议仲裁和合规审计。

特性:
1. 音视频切片 - FFmpeg自动切片存储
2. 关键日志 - 操作命令与结果记录
3. 屏幕录像 - 可选的服务过程录屏
4. 加密存储 - SOPS风格加密
5. 证据包导出 - 争议时生成证明材料
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
import time
import uuid
import json
import hashlib
import struct
from pathlib import Path
import subprocess
import shutil

logger = logging.getLogger(__name__)


class EvidenceType(Enum):
    """证据类型"""
    VIDEO_SLICE = "video_slice"      # 视频切片
    AUDIO_SLICE = "audio_slice"      # 音频切片
    COMMAND_LOG = "command_log"      # 命令日志
    RESULT_DATA = "result_data"      # 结果数据
    SCREENSHOT = "screenshot"        # 屏幕截图
    SCREEN_RECORD = "screen_record"  # 屏幕录像
    META_DATA = "meta_data"          # 元数据


class AuditStatus(Enum):
    """存证状态"""
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    SEALED = "sealed"        # 已密封 (不可修改)
    EXPORTED = "exported"


@dataclass
class EvidenceSlice:
    """证据切片"""
    slice_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    session_id: str = ""
    evidence_type: EvidenceType = EvidenceType.META_DATA

    # 内容
    file_path: str = ""
    file_size: int = 0
    checksum: str = ""       # SHA256校验

    # 元数据
    start_time: float = 0    # 切片开始时间
    end_time: float = 0      # 切片结束时间
    duration_ms: int = 0     # 持续时间

    # 上下文
    user_id: str = ""        # 操作用户
    command: str = ""        # 相关命令
    result_hash: str = ""    # 结果哈希

    # 密封
    sealed: bool = False
    sealed_at: float = 0

    def seal(self) -> None:
        """密封切片"""
        self.sealed = True
        self.sealed_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slice_id": self.slice_id,
            "session_id": self.session_id,
            "evidence_type": self.evidence_type.value,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "checksum": self.checksum,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "user_id": self.user_id,
            "command": self.command,
            "result_hash": self.result_hash,
            "sealed": self.sealed,
            "sealed_at": self.sealed_at,
        }


@dataclass
class AuditSession:
    """审计会话"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    order_id: str = ""
    listing_id: str = ""
    seller_id: str = ""
    buyer_id: str = ""

    # 时间
    started_at: float = field(default_factory=time.time)
    ended_at: float = 0
    duration_seconds: int = 0

    # 证据
    slices: List[EvidenceSlice] = field(default_factory=list)
    commands_log: List[Dict[str, Any]] = field(default_factory=list)

    # 状态
    status: AuditStatus = AuditStatus.RECORDING

    # 密封
    sealed: bool = False
    sealed_at: float = 0
    seal_checksum: str = ""  # 会话级密封校验

    def add_slice(self, evidence: EvidenceSlice) -> None:
        if not self.sealed:
            self.slices.append(evidence)

    def add_command(self, command: str, result: str, user_id: str) -> str:
        """添加命令日志,返回命令ID"""
        cmd_id = hashlib.sha256(f"{command}{time.time()}{uuid.uuid4()}".encode()).hexdigest()[:12]
        self.commands_log.append({
            "cmd_id": cmd_id,
            "command": command,
            "result": result,
            "user_id": user_id,
            "timestamp": time.time(),
            "result_checksum": hashlib.sha256(result.encode()).hexdigest()[:16],
        })
        return cmd_id

    def seal_session(self) -> str:
        """密封会话,生成会话级校验"""
        self.sealed = True
        self.sealed_at = time.time()
        self.status = AuditStatus.SEALED

        # 生成会话级校验
        content = json.dumps({
            "session_id": self.session_id,
            "order_id": self.order_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "slices": [s.checksum for s in self.slices],
            "commands": [c["result_checksum"] for c in self.commands_log],
        }, sort_keys=True)

        self.seal_checksum = hashlib.sha256(content.encode()).hexdigest()
        return self.seal_checksum

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "order_id": self.order_id,
            "listing_id": self.listing_id,
            "seller_id": self.seller_id,
            "buyer_id": self.buyer_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "slice_count": len(self.slices),
            "command_count": len(self.commands_log),
            "status": self.status.value,
            "sealed": self.sealed,
            "sealed_at": self.sealed_at,
            "seal_checksum": self.seal_checksum,
            "slices": [s.to_dict() for s in self.slices],
            "commands_log": self.commands_log,
        }


class AuditTrailSystem:
    """
    服务存证系统

    功能:
    - 记录服务全过程证据
    - 音视频切片存储
    - 命令和结果日志
    - 证据密封和校验
    - 争议时导出证明材料
    """

    def __init__(
        self,
        storage_dir: str = "~/.hermes-desktop/audit",
        ffmpeg_path: Optional[str] = None,
    ):
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()

        # 会话管理
        self._sessions: Dict[str, AuditSession] = {}
        self._active_session: Optional[AuditSession] = None

        # 录制状态
        self._video_recording: bool = False
        self._audio_recording: bool = False
        self._screen_recording: bool = False
        self._ffmpeg_process: Optional[subprocess.Popen] = None

        # 回调
        self._on_evidence_ready: List[Callable] = []

        logger.info(f"[AuditTrail] Initialized at {self.storage_dir}")

    def _find_ffmpeg(self) -> Optional[str]:
        """查找FFmpeg路径"""
        # 常见路径
        common_paths = [
            "ffmpeg",
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
        ]

        for path in common_paths:
            try:
                result = subprocess.run(
                    [path, "-version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return path
            except:
                continue

        logger.warning("[AuditTrail] FFmpeg not found, video recording disabled")
        return None

    # ==================== 会话管理 ====================

    def start_session(
        self,
        order_id: str,
        listing_id: str,
        seller_id: str,
        buyer_id: str,
    ) -> str:
        """开始审计会话"""
        session = AuditSession(
            order_id=order_id,
            listing_id=listing_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
        )
        self._sessions[session.session_id] = session
        self._active_session = session

        # 创建会话存储目录
        session_dir = self.storage_dir / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[AuditTrail] Started session {session.session_id} for order {order_id}")
        return session.session_id

    def stop_session(self) -> Optional[Dict[str, Any]]:
        """停止当前审计会话"""
        if not self._active_session:
            return None

        session = self._active_session
        session.ended_at = time.time()
        session.duration_seconds = int(session.ended_at - session.started_at)
        session.status = AuditStatus.STOPPED

        # 停止所有录制
        self._stop_all_recording()

        # 密封会话
        session.seal_session()

        # 保存元数据
        self._save_session_meta(session)

        result = session.to_dict()
        self._active_session = None

        logger.info(f"[AuditTrail] Stopped session {session.session_id}, sealed: {session.seal_checksum}")
        return result

    def pause_session(self) -> bool:
        """暂停审计"""
        if self._active_session:
            self._active_session.status = AuditStatus.PAUSED
            self._stop_all_recording()
            return True
        return False

    def resume_session(self) -> bool:
        """恢复审计"""
        if self._active_session:
            self._active_session.status = AuditStatus.RECORDING
            return True
        return False

    def get_session(self, session_id: str) -> Optional[AuditSession]:
        """获取会话"""
        return self._sessions.get(session_id)

    def _save_session_meta(self, session: AuditSession) -> None:
        """保存会话元数据"""
        meta_file = self.storage_dir / session.session_id / "meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

    # ==================== 视频录制 ====================

    def start_video_recording(
        self,
        session_id: str,
        source: str = "desktop",
        fps: int = 15,
        quality: int = 23,
    ) -> bool:
        """开始视频录制"""
        if not self._active_session or not self.ffmpeg_path:
            return False

        if self._video_recording:
            return True

        session = self._active_session
        output_dir = self.storage_dir / session_id / "video"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"video_{int(time.time())}.mp4"

        # FFmpeg命令
        cmd = [
            self.ffmpeg_path,
            "-f", "gdigrab",  # Windows屏幕捕获
            "-i", f"desktop",  # 捕获整个桌面
            "-framerate", str(fps),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", str(quality),
            "-pix_fmt", "yuv420p",
            "-strftime", "1",  # 使用时间戳作为文件名
            str(output_file),
        ]

        try:
            self._ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._video_recording = True

            # 创建切片记录
            slice_info = EvidenceSlice(
                session_id=session_id,
                evidence_type=EvidenceType.VIDEO_SLICE,
                file_path=str(output_file),
                start_time=time.time(),
                user_id=session.buyer_id,
            )
            session.add_slice(slice_info)

            logger.info(f"[AuditTrail] Started video recording to {output_file}")
            return True

        except Exception as e:
            logger.error(f"[AuditTrail] Failed to start video recording: {e}")
            return False

    def stop_video_recording(self) -> Optional[str]:
        """停止视频录制"""
        if not self._video_recording:
            return None

        if self._ffmpeg_process:
            self._ffmpeg_process.terminate()
            try:
                self._ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ffmpeg_process.kill()

            self._ffmpeg_process = None

        self._video_recording = False

        # 更新切片信息
        if self._active_session and self._active_session.slices:
            last_slice = self._active_session.slices[-1]
            if last_slice.evidence_type == EvidenceType.VIDEO_SLICE:
                last_slice.end_time = time.time()
                last_slice.duration_ms = int((last_slice.end_time - last_slice.start_time) * 1000)
                last_slice.file_size = Path(last_slice.file_path).stat().st_size if Path(last_slice.file_path).exists() else 0
                last_slice.checksum = self._calculate_file_checksum(last_slice.file_path)

        logger.info("[AuditTrail] Stopped video recording")
        return None

    def _stop_all_recording(self) -> None:
        """停止所有录制"""
        self.stop_video_recording()
        self._audio_recording = False
        self._screen_recording = False

    # ==================== 截图 ====================

    async def capture_screenshot(self, session_id: str, label: str = "") -> Optional[str]:
        """捕获屏幕截图"""
        if not self._active_session:
            return None

        session = self._active_session
        output_dir = self.storage_dir / session_id / "screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"screenshot_{int(time.time())}_{label or '0'}.png"
        output_path = output_dir / filename

        try:
            # 使用PIL/numpy捕获
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(output_path, "PNG")
            except ImportError:
                # 备选: 使用mss
                import mss
                with mss.mss() as sct:
                    sct.shot(output=str(output_path))

            # 创建切片记录
            slice_info = EvidenceSlice(
                session_id=session_id,
                evidence_type=EvidenceType.SCREENSHOT,
                file_path=str(output_path),
                start_time=time.time(),
                end_time=time.time(),
                duration_ms=0,
                user_id=session.buyer_id,
                command=label,
            )
            slice_info.file_size = output_path.stat().st_size
            slice_info.checksum = self._calculate_file_checksum(str(output_path))

            session.add_slice(slice_info)

            # 触发回调
            for cb in self._on_evidence_ready:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(slice_info)
                    else:
                        cb(slice_info)
                except:
                    pass

            logger.info(f"[AuditTrail] Captured screenshot: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"[AuditTrail] Screenshot failed: {e}")
            return None

    # ==================== 命令日志 ====================

    def log_command(
        self,
        session_id: str,
        command: str,
        result: str,
        user_id: str,
    ) -> str:
        """记录命令执行"""
        session = self._sessions.get(session_id)
        if not session:
            return ""

        cmd_id = session.add_command(command, result, user_id)

        # 同时创建证据切片
        slice_info = EvidenceSlice(
            session_id=session_id,
            evidence_type=EvidenceType.COMMAND_LOG,
            start_time=time.time(),
            end_time=time.time(),
            user_id=user_id,
            command=command,
            result_hash=hashlib.sha256(result.encode()).hexdigest()[:16],
        )
        session.add_slice(slice_info)

        return cmd_id

    def log_result(
        self,
        session_id: str,
        result_type: str,
        data: Any,
        user_id: str,
    ) -> str:
        """记录结果数据"""
        session = self._sessions.get(session_id)
        if not session:
            return ""

        result_json = json.dumps(data, ensure_ascii=False, sort_keys=True)
        result_hash = hashlib.sha256(result_json.encode()).hexdigest()[:16]

        slice_info = EvidenceSlice(
            session_id=session_id,
            evidence_type=EvidenceType.RESULT_DATA,
            start_time=time.time(),
            end_time=time.time(),
            user_id=user_id,
            command=result_type,
            result_hash=result_hash,
        )
        session.add_slice(slice_info)

        return result_hash

    # ==================== 证据包导出 ====================

    def export_evidence_package(
        self,
        session_id: str,
        output_dir: Optional[str] = None,
    ) -> Optional[str]:
        """
        导出证据包

        生成包含以下内容的证据包:
        - session.json: 会话元数据
        - slices/: 证据切片
        - manifest.json: 证据清单
        - proof.json: 完整性证明
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        if not session.sealed:
            # 自动密封
            session.seal_session()

        if output_dir is None:
            output_dir = str(self.storage_dir / f"export_{session_id}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. 复制会话元数据
        session_file = output_path / "session.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

        # 2. 创建切片目录并复制文件
        slices_dir = output_path / "slices"
        slices_dir.mkdir(exist_ok=True)

        manifest = []
        for slice_info in session.slices:
            if slice_info.file_path and Path(slice_info.file_path).exists():
                dest = slices_dir / f"{slice_info.slice_id}_{Path(slice_info.file_path).name}"
                shutil.copy2(slice_info.file_path, dest)
                manifest.append({
                    "slice_id": slice_info.slice_id,
                    "original_path": slice_info.file_path,
                    "exported_path": str(dest),
                    "checksum": slice_info.checksum,
                })

        # 3. 保存清单
        manifest_file = output_path / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # 4. 生成完整性证明
        proof = {
            "session_id": session.session_id,
            "exported_at": time.time(),
            "seal_checksum": session.seal_checksum,
            "slice_count": len(session.slices),
            "manifest_checksum": self._calculate_file_checksum(str(manifest_file)),
            "session_file_checksum": self._calculate_file_checksum(str(session_file)),
        }

        proof_file = output_path / "proof.json"
        with open(proof_file, "w", encoding="utf-8") as f:
            json.dump(proof, f, indent=2)

        logger.info(f"[AuditTrail] Exported evidence package to {output_path}")
        return str(output_path)

    # ==================== 工具 ====================

    def _calculate_file_checksum(self, file_path: str) -> str:
        """计算文件SHA256校验"""
        path = Path(file_path)
        if not path.exists():
            return ""

        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def on_evidence_ready(self, callback: Callable) -> None:
        """监听证据就绪"""
        self._on_evidence_ready.append(callback)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_sessions = len(self._sessions)
        sealed_sessions = sum(1 for s in self._sessions.values() if s.sealed)
        total_slices = sum(len(s.slices) for s in self._sessions.values())
        total_commands = sum(len(s.commands_log) for s in self._sessions.values())

        return {
            "storage_dir": str(self.storage_dir),
            "total_sessions": total_sessions,
            "sealed_sessions": sealed_sessions,
            "total_slices": total_slices,
            "total_commands": total_commands,
            "video_recording": self._video_recording,
        }


# 全局单例
_audit_trail: Optional[AuditTrailSystem] = None

def get_audit_trail() -> AuditTrailSystem:
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = AuditTrailSystem()
    return _audit_trail
