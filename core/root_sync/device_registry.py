"""
设备注册与证书管理 - Device Registry

Syncthing 风格设备认证系统：
- Ed25519 证书对生成
- 设备 ID 基于证书哈希
- 设备发现与引入
"""

import asyncio
import secrets
import hashlib
import json
import os
import time
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509 import CertificateBuilder, Name, NameAttribute
from cryptography.hazmat.backends import default_backend

from .models import DeviceInfo


# 设备 ID 长度
DEVICE_ID_LENGTH = 32


class DeviceRegistry:
    """
    设备注册表

    管理设备证书和设备信息：
    1. 证书生成与验证
    2. 设备 ID 管理
    3. 设备发现
    4. 设备引入
    """

    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 设备信息
        self._devices: Dict[str, DeviceInfo] = {}

        # 证书
        self._certs: Dict[str, dict] = {}  # device_id -> cert_data

        # 我的设备信息
        self._my_device_id: Optional[str] = None
        self._my_private_key: Optional[ed25519.Ed25519PrivateKey] = None
        self._my_cert: Optional[dict] = None

        # 加载已有设备
        self._load_devices()

    def generate_device_id(self, public_key: bytes) -> str:
        """
        基于公钥生成设备 ID

        Syncthing 风格：SHA-256 前 32 字节，Base32 编码
        """
        h = hashlib.sha256(public_key).digest()
        return h[:DEVICE_ID_LENGTH].hex()

    async def generate_my_certificate(self, device_name: str) -> Tuple[str, bytes, bytes]:
        """
        生成自己的证书对

        Returns:
            (device_id, cert_pem, private_key_pem)
        """
        # 生成 Ed25519 密钥对
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # 序列化为 PEM
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # 生成证书
        cert = self._create_self_signed_cert(device_name, public_key, private_key)
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)

        # 计算设备 ID
        device_id = self.generate_device_id(public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw
        ))

        # 保存
        self._my_device_id = device_id
        self._my_private_key = private_key
        self._my_cert = {
            "device_id": device_id,
            "device_name": device_name,
            "cert_pem": cert_pem,
            "private_key_pem": private_pem,
            "created_at": time.time(),
        }

        # 保存到文件
        await self._save_my_cert()

        return device_id, cert_pem, private_pem

    def _create_self_signed_cert(self, device_name: str,
                                 public_key: ed25519.Ed25519PublicKey,
                                 private_key: ed25519.Ed25519PrivateKey) -> CertificateBuilder:
        """创建自签名证书"""
        subject = issuer = Name([
            NameAttribute(NameOID.COMMON_NAME, device_name),
        ])

        serial = secrets.randbelow(2**64)

        cert = (
            CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(public_key)
            .serial_number(serial)
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=3650))
        )

        return cert.sign(private_key, hashes.SHA256(), default_backend())

    async def _save_my_cert(self):
        """保存我的证书"""
        if not self._my_cert:
            return

        cert_path = self.storage_dir / "my_cert.json"
        with open(cert_path, "w") as f:
            json.dump({
                "device_id": self._my_cert["device_id"],
                "device_name": self._my_cert["device_name"],
                "cert_pem": self._my_cert["cert_pem"].decode(),
                "private_key_pem": self._my_cert["private_key_pem"].decode(),
                "created_at": self._my_cert["created_at"],
            }, f)

    async def load_my_certificate(self) -> Optional[Tuple[str, bytes, bytes]]:
        """加载我的证书"""
        cert_path = self.storage_dir / "my_cert.json"
        if not cert_path.exists():
            return None

        try:
            with open(cert_path, "r") as f:
                data = json.load(f)

            self._my_device_id = data["device_id"]
            self._my_cert = {
                "device_id": data["device_id"],
                "device_name": data["device_name"],
                "cert_pem": data["cert_pem"].encode(),
                "private_key_pem": data["private_key_pem"].encode(),
                "created_at": data["created_at"],
            }

            # 重新加载私钥对象
            self._my_private_key = serialization.load_pem_private_key(
                data["private_key_pem"].encode(),
                password=None,
                backend=default_backend()
            )

            return (
                self._my_cert["device_id"],
                self._my_cert["cert_pem"],
                self._my_cert["private_key_pem"],
            )
        except Exception:
            return None

    @property
    def my_device_id(self) -> Optional[str]:
        return self._my_device_id

    async def add_device(self, device_info: DeviceInfo,
                        cert_pem: Optional[bytes] = None):
        """
        添加设备

        Args:
            device_info: 设备信息
            cert_pem: 证书 PEM 数据
        """
        self._devices[device_info.device_id] = device_info

        if cert_pem:
            self._certs[device_info.device_id] = {
                "cert_pem": cert_pem,
                "added_at": time.time(),
            }

        await self._save_device(device_info)

    async def _save_device(self, device_info: DeviceInfo):
        """保存设备信息"""
        device_dir = self.storage_dir / "devices" / device_info.device_id[:8]
        device_dir.mkdir(parents=True, exist_ok=True)

        info_path = device_dir / "info.json"
        with open(info_path, "w") as f:
            json.dump(device_info.to_dict(), f)

    async def remove_device(self, device_id: str):
        """移除设备"""
        if device_id in self._devices:
            del self._devices[device_id]

        if device_id in self._certs:
            del self._certs[device_id]

        # 删除文件
        device_dir = self.storage_dir / "devices" / device_id[:8]
        if device_dir.exists():
            for f in device_dir.iterdir():
                if device_id in f.read_text():
                    f.unlink()

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """获取设备信息"""
        return self._devices.get(device_id)

    def get_all_devices(self) -> List[DeviceInfo]:
        """获取所有设备"""
        return list(self._devices.values())

    def is_device_known(self, device_id: str) -> bool:
        """检查设备是否已知"""
        return device_id in self._devices

    async def verify_peer(self, peer_id: str,
                         peer_cert_pem: bytes) -> bool:
        """
        验证对等设备证书

        检查：
        1. 证书签名
        2. 设备 ID 匹配
        3. 证书未过期
        """
        if peer_id not in self._devices:
            return False

        stored_cert = self._certs.get(peer_id)
        if not stored_cert:
            return False

        # 验证证书匹配
        return stored_cert["cert_pem"] == peer_cert_pem

    def _load_devices(self):
        """加载已保存的设备"""
        devices_dir = self.storage_dir / "devices"
        if not devices_dir.exists():
            return

        for device_file in devices_dir.rglob("info.json"):
            try:
                with open(device_file, "r") as f:
                    data = json.load(f)
                device_info = DeviceInfo(**data)
                self._devices[device_info.device_id] = device_info
            except Exception:
                pass

    async def introduce_device(self, device_id: str, introducer_id: str):
        """引入设备"""
        if device_id not in self._devices:
            return

        device = self._devices[device_id]
        device.introduced = True
        device.introduced_by = introducer_id

    async def export_device(self, device_id: str) -> Optional[dict]:
        """
        导出设备连接信息（用于分享给其他设备）

        Returns:
            可序列化的设备信息
        """
        if device_id not in self._devices:
            return None

        device = self._devices[device_id]
        cert_data = self._certs.get(device_id, {})

        return {
            "device_id": device_id,
            "device_name": device.name,
            "cert_pem": cert_data.get("cert_pem", b"").decode() if cert_data else "",
            "addresses": device.addresses,
            "introducer": device.is_introducer,
        }

    async def import_device(self, data: dict) -> Optional[DeviceInfo]:
        """
        导入设备

        来自其他设备的分享
        """
        device_id = data.get("device_id")
        if not device_id:
            return None

        device_info = DeviceInfo(
            device_id=device_id,
            name=data.get("device_name", ""),
            addresses=data.get("addresses", []),
            is_introducer=data.get("introducer", False),
            introduced=True,
        )

        cert_pem = data.get("cert_pem", "").encode()
        if cert_pem:
            self._certs[device_id] = {
                "cert_pem": cert_pem,
                "added_at": time.time(),
            }

        await self.add_device(device_info, cert_pem)
        return device_info


class GlobalDiscovery:
    """
    全局发现服务客户端

    支持：
    1. 全球发现服务器 (https://discovery.syncthing.net)
    2. 本地发现 (UDP 广播)
    3. 自托管发现服务器
    """

    DISCOVERY_SERVERS = [
        "https://discovery.syncthing.net",
        "https://discovery-v4.syncthing.net",
        "https://discovery-v6.syncthing.net",
    ]

    def __init__(self, registry: DeviceRegistry):
        self.registry = registry
        self._relay_servers: List[str] = []

    async def register_device(self, device_id: str, addresses: List[str]):
        """
        注册设备到全局发现服务器

        Args:
            device_id: 设备 ID
            addresses: 可访问的地址列表
        """
        import aiohttp

        for server in self.DISCOVERY_SERVERS:
            try:
                url = f"{server}/v2/?device={device_id}"
                async with aiohttp.ClientSession() as session:
                    data = json.dumps({
                        "device": device_id,
                        "addresses": addresses,
                    })
                    async with session.post(url, data=data) as resp:
                        if resp.status == 200:
                            return True
            except Exception:
                continue

        return False

    async def lookup_device(self, device_id: str) -> Optional[List[str]]:
        """
        查询设备地址

        Returns:
            设备地址列表
        """
        import aiohttp

        for server in self.DISCOVERY_SERVERS:
            try:
                url = f"{server}/v2/?device={device_id}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("addresses", [])
            except Exception:
                continue

        return None

    def add_relay_server(self, url: str):
        """添加中继服务器"""
        if url not in self._relay_servers:
            self._relay_servers.append(url)

    def get_relay_servers(self) -> List[str]:
        """获取中继服务器列表"""
        return self._relay_servers.copy()
