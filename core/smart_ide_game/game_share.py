"""
游戏分享系统模块
提供游戏分享、二维码、短链接、邀请码等功能
"""
import asyncio
import json
import hashlib
import uuid
import base64
import zlib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random
import string
import io


class ShareMode(Enum):
    """分享模式"""
    FULL_GAME = "full_game"       # 完整游戏
    CLOUD_GAME = "cloud_game"      # 云游戏
    ROOM_LINK = "room_link"        # 房间链接
    QR_CODE = "qr_code"            # 二维码
    INVITE_CODE = "invite_code"    # 邀请码
    GAME_STATE = "game_state"      # 游戏状态
    RECORDING = "recording"        # 录像
    SCREENSHOT = "screenshot"      # 截图


class ShareStatus(Enum):
    """分享状态"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    MAX_ACCESS = "max_access"


@dataclass
class ShareLink:
    """分享链接"""
    id: str
    share_mode: ShareMode
    target_id: str  # 游戏ID、房间ID等
    short_code: str
    url: str
    title: str = ""
    description: str = ""
    thumbnail: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_access_count: Optional[int] = None
    access_count: int = 0
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SharePermission:
    """分享权限"""
    can_view: bool = True
    can_download: bool = False
    can_invite: bool = False
    can_edit: bool = False
    require_auth: bool = False


class ShortCodeGenerator:
    """短码生成器"""

    def __init__(self, length: int = 8):
        self.length = length
        self.charset = string.ascii_letters + string.digits
        self.used_codes: Set[str] = set()

    def generate(self) -> str:
        """生成短码"""
        for _ in range(100):  # 最多尝试100次
            code = ''.join(random.choices(self.charset, k=self.length))
            if code not in self.used_codes:
                self.used_codes.add(code)
                return code
        # 如果所有代码都被使用，返回一个带时间戳的代码
        return f"{uuid.uuid4().hex[:self.length]}"

    def revoke(self, code: str) -> bool:
        """撤销代码"""
        if code in self.used_codes:
            self.used_codes.remove(code)
            return True
        return False

    def is_used(self, code: str) -> bool:
        """检查代码是否已使用"""
        return code in self.used_codes


class QRCodeGenerator:
    """二维码生成器"""

    def __init__(self):
        self.cache: Dict[str, bytes] = {}

    async def generate(
        self,
        data: str,
        size: int = 300,
        error_correction: str = "M"
    ) -> bytes:
        """生成二维码"""
        # 检查缓存
        cache_key = f"{data}:{size}:{error_correction}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            # 尝试使用qrcode库
            import qrcode
            import qrcode.constants
from core.logger import get_logger
logger = get_logger('smart_ide_game.game_share')


            error_levels = {
                "L": qrcode.constants.ERROR_CORRECT_L,
                "M": qrcode.constants.ERROR_CORRECT_M,
                "Q": qrcode.constants.ERROR_CORRECT_Q,
                "H": qrcode.constants.ERROR_CORRECT_H,
            }

            qr = qrcode.QRCode(
                version=1,
                error_correction=error_levels.get(error_correction, qrcode.constants.ERROR_CORRECT_M),
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            
            # 调整大小
            if size != 300:
                img = img.resize((size, size))

            # 转换为字节
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            result = buffer.getvalue()

            self.cache[cache_key] = result
            return result

        except ImportError:
            # 如果qrcode库不可用，返回占位符
            return self._generate_placeholder()

    def _generate_placeholder(self) -> bytes:
        """生成占位符（简单的PNG）"""
        # 创建一个最小的有效PNG（1x1透明像素）
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        return png_data


class InviteCodeGenerator:
    """邀请码生成器"""

    def __init__(self):
        self.codes: Dict[str, Dict[str, Any]] = {}

    def generate(
        self,
        target_id: str,
        created_by: str,
        max_uses: int = 1,
        expires_in_hours: int = 24,
        permission: SharePermission = None
    ) -> str:
        """生成邀请码"""
        # 生成6位字母数字码
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        self.codes[code] = {
            "target_id": target_id,
            "created_by": created_by,
            "max_uses": max_uses,
            "used_count": 0,
            "expires_at": datetime.now() + timedelta(hours=expires_in_hours),
            "permission": permission or SharePermission(),
            "created_at": datetime.now()
        }

        return code

    def validate(self, code: str) -> Optional[Dict[str, Any]]:
        """验证邀请码"""
        if code not in self.codes:
            return None

        info = self.codes[code]

        # 检查过期
        if info["expires_at"] and datetime.now() > info["expires_at"]:
            return None

        # 检查使用次数
        if info["used_count"] >= info["max_uses"]:
            return None

        return info

    def use(self, code: str, user_id: str) -> bool:
        """使用邀请码"""
        info = self.validate(code)
        if info:
            info["used_count"] += 1
            return True
        return False

    def revoke(self, code: str) -> bool:
        """撤销邀请码"""
        if code in self.codes:
            del self.codes[code]
            return True
        return False


class GameShare:
    """游戏分享"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or f"{os.path.expanduser('~')}/.hermes-desktop/game_shares"
        os.makedirs(self.storage_path, exist_ok=True)
        
        self.shares: Dict[str, ShareLink] = {}
        self.short_code_gen = ShortCodeGenerator()
        self.qr_gen = QRCodeGenerator()
        self.invite_gen = InviteCodeGenerator()
        self.relay_server: Optional[str] = None
        
        self._load_shares()

    def _load_shares(self):
        """加载分享"""
        index_file = os.path.join(self.storage_path, "shares.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data.get("shares", []):
                        self.shares[item["id"]] = ShareLink(
                            id=item["id"],
                            share_mode=ShareMode(item["share_mode"]),
                            target_id=item["target_id"],
                            short_code=item["short_code"],
                            url=item["url"],
                            title=item.get("title", ""),
                            description=item.get("description", ""),
                            expires_at=datetime.fromisoformat(item["expires_at"]) if item.get("expires_at") else None,
                            max_access_count=item.get("max_access_count"),
                            access_count=item.get("access_count", 0),
                            created_by=item.get("created_by", ""),
                            created_at=datetime.fromisoformat(item.get("created_at", datetime.now().isoformat())),
                            metadata=item.get("metadata", {}),
                        )
            except Exception as e:
                logger.info(f"Failed to load shares: {e}")

    def _save_shares(self):
        """保存分享"""
        index_file = os.path.join(self.storage_path, "shares.json")
        data = {
            "shares": [
                {
                    "id": s.id,
                    "share_mode": s.share_mode.value,
                    "target_id": s.target_id,
                    "short_code": s.short_code,
                    "url": s.url,
                    "title": s.title,
                    "description": s.description,
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "max_access_count": s.max_access_count,
                    "access_count": s.access_count,
                    "created_by": s.created_by,
                    "created_at": s.created_at.isoformat(),
                    "metadata": s.metadata,
                }
                for s in self.shares.values()
            ]
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def set_relay_server(self, server_url: str):
        """设置中继服务器"""
        self.relay_server = server_url

    def create_share(
        self,
        share_mode: ShareMode,
        target_id: str,
        title: str = "",
        description: str = "",
        expires_in_days: int = 7,
        max_access: Optional[int] = None,
        created_by: str = ""
    ) -> ShareLink:
        """创建分享"""
        share_id = str(uuid.uuid4())[:12]
        short_code = self.short_code_gen.generate()
        
        # 构建URL
        base_url = self.relay_server or "https://share.hermes.local"
        url = f"{base_url}/s/{share_code}"

        share = ShareLink(
            id=share_id,
            share_mode=share_mode,
            target_id=target_id,
            short_code=short_code,
            url=url,
            title=title,
            description=description,
            expires_at=datetime.now() + timedelta(days=expires_in_days) if expires_in_days > 0 else None,
            max_access_count=max_access,
            created_by=created_by,
        )

        self.shares[share_id] = share
        self._save_shares()

        return share

    async def create_room_share(
        self,
        room_id: str,
        created_by: str,
        expires_in_hours: int = 24,
        password: Optional[str] = None
    ) -> ShareLink:
        """创建房间分享"""
        share = self.create_share(
            share_mode=ShareMode.ROOM_LINK,
            target_id=room_id,
            title=f"游戏房间邀请",
            description=f"加入游戏房间 {room_id}",
            expires_in_days=expires_in_hours // 24 if expires_in_hours <= 30 else 7,
            created_by=created_by
        )

        share.metadata["password"] = password
        self._save_shares()

        return share

    async def create_game_share(
        self,
        game_id: str,
        created_by: str,
        expires_in_days: int = 7
    ) -> ShareLink:
        """创建游戏分享"""
        share = self.create_share(
            share_mode=ShareMode.FULL_GAME,
            target_id=game_id,
            title=f"游戏分享",
            expires_in_days=expires_in_days,
            created_by=created_by
        )

        return share

    async def create_cloud_game_share(
        self,
        room_id: str,
        created_by: str,
        expires_in_hours: int = 2
    ) -> ShareLink:
        """创建云游戏分享"""
        share = self.create_share(
            share_mode=ShareMode.CLOUD_GAME,
            target_id=room_id,
            title=f"云游戏会话",
            expires_in_days=expires_in_hours // 24,
            created_by=created_by
        )

        return share

    async def generate_qr_code(self, share_id: str, size: int = 300) -> Optional[bytes]:
        """生成二维码"""
        share = self.shares.get(share_id)
        if not share:
            return None

        return await self.qr_gen.generate(share.url, size=size)

    def create_invite_code(
        self,
        target_id: str,
        created_by: str,
        max_uses: int = 1,
        expires_in_hours: int = 24,
        permission: SharePermission = None
    ) -> str:
        """创建邀请码"""
        return self.invite_gen.generate(
            target_id=target_id,
            created_by=created_by,
            max_uses=max_uses,
            expires_in_hours=expires_in_hours,
            permission=permission
        )

    def validate_invite_code(self, code: str) -> Optional[Dict[str, Any]]:
        """验证邀请码"""
        return self.invite_gen.validate(code)

    def access_share(self, share_id: str) -> Optional[ShareLink]:
        """访问分享"""
        share = self.shares.get(share_id)
        if not share:
            return None

        # 检查过期
        if share.expires_at and datetime.now() > share.expires_at:
            return None

        # 检查访问次数
        if share.max_access_count and share.access_count >= share.max_access_count:
            return None

        # 增加访问计数
        share.access_count += 1
        share.last_accessed = datetime.now()
        self._save_shares()

        return share

    def access_by_short_code(self, short_code: str) -> Optional[ShareLink]:
        """通过短码访问"""
        for share in self.shares.values():
            if share.short_code == short_code:
                return self.access_share(share.id)
        return None

    def revoke_share(self, share_id: str) -> bool:
        """撤销分享"""
        if share_id in self.shares:
            del self.shares[share_id]
            self._save_shares()
            return True
        return False

    def get_share(self, share_id: str) -> Optional[ShareLink]:
        """获取分享"""
        return self.shares.get(share_id)

    def get_my_shares(self, user_id: str) -> List[ShareLink]:
        """获取我的分享"""
        return [s for s in self.shares.values() if s.created_by == user_id]

    def cleanup_expired(self) -> int:
        """清理过期分享"""
        now = datetime.now()
        expired = [
            share_id for share_id, share in self.shares.items()
            if share.expires_at and now > share.expires_at
        ]

        for share_id in expired:
            del self.shares[share_id]

        if expired:
            self._save_shares()

        return len(expired)

    def get_share_stats(self) -> Dict[str, Any]:
        """获取分享统计"""
        total_shares = len(self.shares)
        total_access = sum(s.access_count for s in self.shares.values())
        active_shares = sum(
            1 for s in self.shares.values()
            if (not s.expires_at or datetime.now() < s.expires_at)
        )

        return {
            "total_shares": total_shares,
            "active_shares": active_shares,
            "total_access": total_access,
            "shares_by_mode": {
                mode.value: sum(1 for s in self.shares.values() if s.share_mode == mode)
                for mode in ShareMode
            }
        }


class GameRecording:
    """游戏录像"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or f"{os.path.expanduser('~')}/.hermes-desktop/game_recordings"
        os.makedirs(self.storage_path, exist_ok=True)
        self.recordings: Dict[str, Dict[str, Any]] = {}
        self._current_recording: Optional[str] = None
        self._recording_data: List[Dict] = []

    def start_recording(self, session_id: str, metadata: Dict[str, Any] = None) -> str:
        """开始录像"""
        self._current_recording = session_id
        self._recording_data = []
        
        self.recordings[session_id] = {
            "id": session_id,
            "start_time": datetime.now(),
            "end_time": None,
            "duration": 0,
            "frame_count": 0,
            "metadata": metadata or {},
            "events": []
        }
        
        return session_id

    def record_frame(self, frame_data: Dict[str, Any]):
        """录制帧"""
        if self._current_recording:
            self._recording_data.append({
                "timestamp": datetime.now().timestamp(),
                "data": frame_data
            })

    def record_event(self, event_type: str, event_data: Dict[str, Any]):
        """录制事件"""
        if self._current_recording:
            self.recordings[self._current_recording]["events"].append({
                "type": event_type,
                "data": event_data,
                "timestamp": datetime.now().timestamp()
            })

    def stop_recording(self) -> Optional[Dict[str, Any]]:
        """停止录像"""
        if not self._current_recording:
            return None

        recording = self.recordings[self._current_recording]
        recording["end_time"] = datetime.now()
        recording["duration"] = (recording["end_time"] - recording["start_time"]).total_seconds()
        recording["frame_count"] = len(self._recording_data)

        # 保存录像数据
        filename = f"{self._current_recording}.json.gz"
        filepath = os.path.join(self.storage_path, filename)
        
        with open(filepath, 'wb') as f:
            compressed = zlib.compress(json.dumps(self._recording_data).encode('utf-8'))
            f.write(compressed)

        self._current_recording = None
        self._recording_data = []

        return recording

    def get_recording(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取录像信息"""
        return self.recordings.get(session_id)

    def load_recording_data(self, session_id: str) -> List[Dict]:
        """加载录像数据"""
        filename = f"{session_id}.json.gz"
        filepath = os.path.join(self.storage_path, filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                compressed = f.read()
                return json.loads(zlib.decompress(compressed).decode('utf-8'))
        
        return []


class GameScreenshot:
    """游戏截图"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or f"{os.path.expanduser('~')}/.hermes-desktop/game_screenshots"
        os.makedirs(self.storage_path, exist_ok=True)
        self.screenshots: Dict[str, Dict[str, Any]] = {}

    async def capture(
        self,
        image_data: bytes,
        game_id: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """捕获截图"""
        screenshot_id = str(uuid.uuid4())[:12]
        filename = f"{screenshot_id}.png"
        filepath = os.path.join(self.storage_path, filename)
        
        # 保存图片
        with open(filepath, 'wb') as f:
            f.write(image_data)

        # 保存元数据
        self.screenshots[screenshot_id] = {
            "id": screenshot_id,
            "filename": filename,
            "game_id": game_id,
            "path": filepath,
            "size": len(image_data),
            "captured_at": datetime.now(),
            "metadata": metadata or {}
        }

        return screenshot_id

    def get_screenshot(self, screenshot_id: str) -> Optional[bytes]:
        """获取截图"""
        if screenshot_id in self.screenshots:
            filepath = self.screenshots[screenshot_id]["path"]
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    return f.read()
        return None


# 便捷函数
def create_share_link(
    share_mode: ShareMode,
    target_id: str,
    expires_in_days: int = 7
) -> ShareLink:
    """创建分享链接"""
    share_id = str(uuid.uuid4())[:12]
    short_code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    return ShareLink(
        id=share_id,
        share_mode=share_mode,
        target_id=target_id,
        short_code=short_code,
        url=f"https://share.hermes.local/s/{short_code}",
        expires_at=datetime.now() + timedelta(days=expires_in_days) if expires_in_days > 0 else None,
    )
