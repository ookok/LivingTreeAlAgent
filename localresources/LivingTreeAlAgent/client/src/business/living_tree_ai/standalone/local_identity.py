"""
本地身份自举系统 (Local Identity Bootstrap)
==========================================

核心设计：
- 抛弃"用户ID"，使用"设备指纹+公钥"作为唯一标识
- 无需中心注册，启动时自动生成

自举流程：
1. 检查 ~/.config/your_app/identity.json
2. 若无则生成新的 Ed25519 密钥对
3. 生成设备指纹
"""

import hashlib
import json
import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@dataclass
class DeviceFingerprint:
    """设备指纹"""
    device_id: str              # 唯一设备ID
    platform: str               # 操作系统
    platform_version: str        # 系统版本
    machine: str                # 机器类型
    processor: str               # 处理器
    hostname: str                # 主机名
    mac_address: str             # MAC 地址（哈希）
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class LocalIdentity:
    """
    本地身份

    组成：
    - device_fingerprint: 设备指纹
    - public_key: Ed25519 公钥
    - private_key: Ed25519 私钥（仅本地存储）
    - node_id: 节点唯一标识（格式: fp_<fingerprint_hash>）
    """

    identity_path: Path
    device_fingerprint: Optional[DeviceFingerprint] = None
    public_key: Optional[bytes] = None
    private_key: Optional[bytes] = None
    node_id: Optional[str] = None
    created_at: Optional[datetime] = None

    # 内部状态
    _initialized: bool = False

    async def bootstrap(self) -> bool:
        """
        自举身份

        1. 检查 identity.json 是否存在
        2. 若存在则加载
        3. 若不存在则生成新的
        """
        identity_file = self.identity_path / "identity.json"

        if identity_file.exists():
            return await self._load_identity(identity_file)
        else:
            return await self._generate_identity(identity_file)

    async def _load_identity(self, path: Path) -> bool:
        """加载已有身份"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.node_id = data.get("node_id")
            self.created_at = datetime.fromisoformat(data.get("created_at"))

            # 加载设备指纹
            fp_data = data.get("device_fingerprint", {})
            self.device_fingerprint = DeviceFingerprint(
                device_id=fp_data.get("device_id", ""),
                platform=fp_data.get("platform", ""),
                platform_version=fp_data.get("platform_version", ""),
                machine=fp_data.get("machine", ""),
                processor=fp_data.get("processor", ""),
                hostname=fp_data.get("hostname", ""),
                mac_address=fp_data.get("mac_address", ""),
                generated_at=datetime.fromisoformat(fp_data.get("generated_at", datetime.now().isoformat()))
            )

            # 加载密钥
            if HAS_CRYPTO:
                public_key_data = data.get("public_key")
                private_key_data = data.get("private_key")

                if public_key_data:
                    self.public_key = bytes.fromhex(public_key_data)
                if private_key_data:
                    self.private_key = bytes.fromhex(private_key_data)

            self._initialized = True
            return True

        except Exception as e:
            return False

    async def _generate_identity(self, path: Path) -> bool:
        """生成新身份"""
        try:
            # 1. 生成设备指纹
            self.device_fingerprint = self._generate_device_fingerprint()

            # 2. 生成密钥对
            if HAS_CRYPTO:
                private_key_obj = ed25519.Ed25519PrivateKey.generate()
                public_key_obj = private_key_obj.public_key()

                self.private_key = private_key_obj.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                )
                self.public_key = public_key_obj.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                )
            else:
                # 无 cryptography 库时，使用随机字节
                import os
                self.private_key = os.urandom(32)
                self.public_key = os.urandom(32)

            # 3. 生成节点 ID
            self.node_id = self._generate_node_id()

            # 4. 保存
            self.created_at = datetime.now()
            await self._save_identity(path)

            self._initialized = True
            return True

        except Exception as e:
            return False

    def _generate_device_fingerprint(self) -> DeviceFingerprint:
        """生成设备指纹"""
        # 获取系统信息
        plat = platform.system().lower()
        fp_data = {
            "platform": plat,
            "platform_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
            "hostname": platform.node() or "unknown",
        }

        # 生成唯一设备 ID
        raw_id = f"{json.dumps(fp_data)}{uuid.getnode()}{uuid.uuid4()}"
        device_id = hashlib.sha256(raw_id.encode()).hexdigest()[:16]

        # MAC 地址哈希
        mac = uuid.getnode()
        mac_hash = hashlib.sha256(str(mac).encode()).hexdigest()[:12]

        return DeviceFingerprint(
            device_id=device_id,
            **fp_data,
            mac_address=mac_hash
        )

    def _generate_node_id(self) -> str:
        """生成节点 ID"""
        if not self.public_key:
            raise ValueError("Public key not generated")

        # 使用公钥哈希作为节点 ID
        key_hash = hashlib.sha256(self.public_key).hexdigest()[:16]
        return f"fp_{key_hash}"

    async def _save_identity(self, path: Path):
        """保存身份到文件"""
        data = {
            "node_id": self.node_id,
            "created_at": self.created_at.isoformat(),
            "device_fingerprint": {
                "device_id": self.device_fingerprint.device_id,
                "platform": self.device_fingerprint.platform,
                "platform_version": self.device_fingerprint.platform_version,
                "machine": self.device_fingerprint.machine,
                "processor": self.device_fingerprint.processor,
                "hostname": self.device_fingerprint.hostname,
                "mac_address": self.device_fingerprint.mac_address,
                "generated_at": self.device_fingerprint.generated_at.isoformat(),
            },
            "public_key": self.public_key.hex() if self.public_key else None,
            # 注意：private_key 不应明文存储在实际应用中
            # 这里仅为演示，实际应该使用密钥管理器
            "private_key": self.private_key.hex() if self.private_key else None,
        }

        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def sign(self, data: bytes) -> Optional[bytes]:
        """签名数据"""
        if not HAS_CRYPTO or not self.private_key:
            # 简单模拟签名
            return hashlib.sha256(data + self.private_key or b"fake").digest()

        private_key_obj = ed25519.Ed25519PrivateKey.from_private_bytes(self.private_key)
        return private_key_obj.sign(data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        """验证签名"""
        if not HAS_CRYPTO or not self.public_key:
            return True

        try:
            public_key_obj = ed25519.Ed25519PublicKey.from_public_bytes(self.public_key)
            public_key_obj.verify(signature, data)
            return True
        except Exception:
            return False

    def get_info(self) -> dict[str, Any]:
        """获取身份信息"""
        return {
            "node_id": self.node_id,
            "device_id": self.device_fingerprint.device_id if self.device_fingerprint else None,
            "platform": self.device_fingerprint.platform if self.device_fingerprint else None,
            "hostname": self.device_fingerprint.hostname if self.device_fingerprint else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def create_local_identity(data_dir: Path) -> LocalIdentity:
    """创建本地身份"""
    identity_path = data_dir / "identity"
    return LocalIdentity(identity_path=identity_path)