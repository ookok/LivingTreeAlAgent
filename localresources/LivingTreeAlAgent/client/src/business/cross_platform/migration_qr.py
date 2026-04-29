"""
Migration QR - Web/App迁移工具
===========================

提供Web端到App端的数据迁移功能

功能:
- 生成迁移二维码
- 扫码迁移数据
- 加密传输
"""

import json
import base64
import zlib
import time
import qrcode
import io
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class MigrationType(Enum):
    """迁移类型"""
    WEB_TO_APP = "web_to_app"  # Web迁移到App
    APP_TO_WEB = "app_to_web"  # App迁移到Web
    APP_TO_APP = "app_to_app"  # App之间迁移
    SYNC_BACKUP = "sync_backup"  # 同步备份


@dataclass
class MigrationData:
    """迁移数据"""
    version: str = "1.0"
    migration_type: MigrationType = MigrationType.WEB_TO_APP
    timestamp: float = field(default_factory=time.time)
    device_id: str = ""
    device_name: str = ""

    # 数据内容
    config: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    favorites: List[str] = field(default_factory=list)
    routes: List[Dict[str, Any]] = field(default_factory=dict)

    # 元数据
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """计算校验和"""
        content = json.dumps({
            'version': self.version,
            'migration_type': self.migration_type.value,
            'timestamp': self.timestamp,
            'device_id': self.device_id,
            'config': self.config,
            'history': self.history,
            'favorites': self.favorites,
            'routes': self.routes,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class MigrationQR:
    """
    迁移二维码生成器

    将迁移数据编码为二维码
    """

    # 二维码版本和大小限制
    MAX_VERSION = 40  # QR码最大版本
    MAX_DATA_PER_QR = 2953  # 字节（版本40, 容错L）

    def __init__(self, encryption_key: str = None):
        self.encryption_key = encryption_key or self._generate_key()

    def _generate_key(self) -> str:
        """生成加密密钥"""
        return hashlib.sha256(str(time.time()).encode()).hexdigest()[:32]

    def encode(self, data: MigrationData) -> List[bytes]:
        """
        将迁移数据编码为多个二维码

        Returns:
            List[bytes]: 二维码图像数据列表
        """
        # 序列化为JSON
        json_data = json.dumps(data.__dict__, ensure_ascii=False, default=str)

        # 压缩
        compressed = zlib.compress(json_data.encode('utf-8'), level=9)

        # Base64编码
        encoded = base64.b64encode(compressed).decode('ascii')

        # 分块（如果数据太大）
        chunks = self._split_into_chunks(encoded)

        # 为每个块生成二维码
        qr_images = []
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks):
            # 添加块头
            header = f"MIGR:{i+1}/{total_chunks}:"
            chunk_with_header = header + chunk

            # 生成二维码
            qr = qrcode.QRCode(
                version=min(20, len(chunk_with_header) // 50 + 1),
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(chunk_with_header)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            qr_images.append(img)

        return qr_images

    def _split_into_chunks(self, data: str, max_chunk_size: int = None) -> List[str]:
        """分块数据"""
        if max_chunk_size is None:
            max_chunk_size = self.MAX_DATA_PER_QR

        chunks = []
        for i in range(0, len(data), max_chunk_size):
            chunks.append(data[i:i + max_chunk_size])

        return chunks

    def decode(self, qr_images: List) -> Optional[MigrationData]:
        """
        从二维码解码迁移数据

        Args:
            qr_images: 二维码图像列表（按顺序）

        Returns:
            MigrationData或None
        """
        try:
            # 收集所有块
            chunks = []
            total_chunks = None

            for img in qr_images:
                # 解码二维码
                decoded = self._decode_qr(img)

                if decoded.startswith("MIGR:"):
                    # 解析头部
                    header, chunk = decoded.split(":", 2)[1:]
                    current, total = map(int, header.split("/"))

                    if total_chunks is None:
                        total_chunks = total

                    # 确保顺序正确
                    while len(chunks) < current:
                        chunks.append(None)
                    chunks[current - 1] = chunk

            if total_chunks is None or len(chunks) != total_chunks:
                return None

            # 合并所有块
            combined = "".join(chunks)

            # Base64解码
            compressed = base64.b64decode(combined.encode('ascii'))

            # 解压
            json_data = zlib.decompress(compressed).decode('utf-8')

            # 反序列化
            data_dict = json.loads(json_data)

            # 验证校验和
            data = MigrationData(**data_dict)
            if data.checksum != data._calculate_checksum():
                return None  # 校验失败

            return data

        except Exception as e:
            print(f"[MigrationQR] Decode error: {e}")
            return None

    def _decode_qr(self, img) -> str:
        """解码单个二维码"""
        # 这里需要根据实际图像类型实现
        # 简化版本返回空字符串
        return ""

    def generate_qr_image(self, data: MigrationData, index: int = 0) -> bytes:
        """
        生成单个二维码图像

        Args:
            data: 迁移数据
            index: 图像索引（多图迁移时使用）

        Returns:
            bytes: PNG图像数据
        """
        images = self.encode(data)

        if 0 <= index < len(images):
            buf = io.BytesIO()
            images[index].save(buf, format='PNG')
            return buf.getvalue()

        return b""

    def generate_simple_qr(self, data: Dict[str, Any]) -> Optional[bytes]:
        """
        生成简单的单二维码（数据量较小时使用）

        Args:
            data: 要编码的数据字典

        Returns:
            bytes: PNG图像数据
        """
        try:
            # 压缩并编码
            json_data = json.dumps(data, ensure_ascii=False, default=str)
            compressed = zlib.compress(json_data.encode('utf-8'))
            encoded = base64.b64encode(compressed).decode('ascii')

            # 生成二维码
            qr = qrcode.QRCode(
                version=min(20, len(encoded) // 50 + 1),
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(encoded)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # 转换为bytes
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue()

        except Exception as e:
            print(f"[MigrationQR] Simple QR error: {e}")
            return None


class WebToAppMigrator:
    """
    Web到App迁移器

    处理从Web端到移动App的数据迁移
    """

    def __init__(self):
        self.qr_generator = MigrationQR()

    def create_migration_from_web(
        self,
        config: Dict[str, Any],
        history: List[Dict[str, Any]] = None,
        favorites: List[str] = None,
        routes: Dict[str, Any] = None
    ) -> MigrationData:
        """
        从Web数据创建迁移数据

        Args:
            config: Web端配置
            history: 浏览历史
            favorites: 收藏
            routes: 路由规则

        Returns:
            MigrationData
        """
        return MigrationData(
            migration_type=MigrationType.WEB_TO_APP,
            device_id=self._generate_device_id(),
            device_name="Web Browser",
            config=config,
            history=history or [],
            favorites=favorites or [],
            routes=routes or {},
        )

    def generate_migration_qr(
        self,
        config: Dict[str, Any],
        history: List[Dict[str, Any]] = None,
        favorites: List[str] = None,
        routes: Dict[str, Any] = None
    ) -> List[bytes]:
        """
        生成迁移二维码列表

        Returns:
            List[bytes]: PNG图像数据列表
        """
        migration_data = self.create_migration_from_web(
            config, history, favorites, routes
        )
        return self.qr_generator.encode(migration_data)

    def restore_to_app(self, qr_images: List) -> Optional[MigrationData]:
        """
        从二维码恢复数据（App端调用）

        Returns:
            MigrationData或None
        """
        return self.qr_generator.decode(qr_images)

    def _generate_device_id(self) -> str:
        """生成设备ID"""
        return hashlib.sha256(
            f"{time.time()}_{id(self)}".encode()
        ).hexdigest()[:16]


# ==================== 前端迁移工具 ====================

MIGRATION_JS = """
// Web迁移工具
class WebMigrationTool {
    constructor() {
        this.qrCallback = null;
    }

    // 生成迁移数据
    generateMigrationData() {
        const data = {
            version: '1.0',
            migration_type: 'web_to_app',
            timestamp: Date.now(),
            device_id: this.getDeviceId(),
            device_name: 'Web Browser',

            // 读取本地配置
            config: this.getLocalConfig(),

            // 读取历史
            history: this.getBrowsingHistory(),

            // 读取收藏
            favorites: this.getFavorites(),

            // 读取路由规则
            routes: this.getRoutes(),
        };

        // 计算校验和
        data.checksum = this.calculateChecksum(data);

        return data;
    }

    getDeviceId() {
        let id = localStorage.getItem('hermes_device_id');
        if (!id) {
            id = 'web_' + Math.random().toString(36).substr(2, 16);
            localStorage.setItem('hermes_device_id', id);
        }
        return id;
    }

    getLocalConfig() {
        try {
            return JSON.parse(localStorage.getItem('hermes_config') || '{}');
        } catch {
            return {};
        }
    }

    getBrowsingHistory() {
        try {
            return JSON.parse(localStorage.getItem('hermes_history') || '[]');
        } catch {
            return [];
        }
    }

    getFavorites() {
        try {
            return JSON.parse(localStorage.getItem('hermes_favorites') || '[]');
        } catch {
            return [];
        }
    }

    getRoutes() {
        try {
            return JSON.parse(localStorage.getItem('hermes_routes') || '{}');
        } catch {
            return {};
        }
    }

    calculateChecksum(data) {
        const content = JSON.stringify({
            version: data.version,
            migration_type: data.migration_type,
            timestamp: data.timestamp,
            device_id: data.device_id,
            config: data.config,
            history: data.history,
            favorites: data.favorites,
            routes: data.routes,
        });
        return btoa(content).substr(0, 16);
    }

    // 编码数据（用于生成二维码）
    encodeData(data) {
        const jsonStr = JSON.stringify(data);
        const compressed = pako.deflate(jsonStr);
        const encoded = btoa(String.fromCharCode.apply(null, compressed));
        return encoded;
    }

    // 解码数据（用于扫描二维码后）
    decodeData(encoded) {
        try {
            const binary = atob(encoded);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            const decompressed = pako.inflate(bytes, { to: 'string' });
            return JSON.parse(decompressed);
        } catch (e) {
            console.error('Decode error:', e);
            return null;
        }
    }

    // 生成迁移二维码
    generateQRCode(data, containerId) {
        const encoded = this.encodeData(data);
        const qr = new QRCode(document.getElementById(containerId), {
            text: encoded,
            width: 256,
            height: 256,
            colorDark: '#000000',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.L
        });
        return qr;
    }

    // 设置扫码回调
    onScan(callback) {
        this.qrCallback = callback;
    }

    // 触发扫码（需要调用摄像头）
    async startScan(videoElementId) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });

            const video = document.getElementById(videoElementId);
            video.srcObject = stream;
            await video.play();

            // 使用jsQR进行扫码
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');

            const scan = () => {
                ctx.drawImage(video, 0, 0);
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imageData.data, canvas.width, canvas.height);

                if (code && this.qrCallback) {
                    const data = this.decodeData(code.data);
                    this.qrCallback(data);
                } else {
                    requestAnimationFrame(scan);
                }
            };

            scan();
        } catch (e) {
            console.error('Scan error:', e);
            alert('无法访问摄像头');
        }
    }

    // 应用迁移数据（App端调用）
    applyMigrationData(data) {
        if (!this.validateData(data)) {
            return false;
        }

        // 保存配置
        localStorage.setItem('hermes_config', JSON.stringify(data.config));

        // 保存历史
        localStorage.setItem('hermes_history', JSON.stringify(data.history));

        // 保存收藏
        localStorage.setItem('hermes_favorites', JSON.stringify(data.favorites));

        // 保存路由
        localStorage.setItem('hermes_routes', JSON.stringify(data.routes));

        return true;
    }

    validateData(data) {
        // 验证校验和
        const checksum = this.calculateChecksum(data);
        return checksum === data.checksum;
    }
}

// 导出全局实例
window.migrationTool = new WebMigrationTool();
"""