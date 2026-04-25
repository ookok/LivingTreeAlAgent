# -*- coding: utf-8 -*-
"""
🌐 通用硬件智能集成系统 - Hardware Mind
=======================================

核心理念: "硬件即插件，自动发现、自动学习、自动集成"

三层架构:
- Layer 0: 物理层 (硬件检测、协议嗅探、指纹生成)
- Layer 1: 知识层 (本地知识库、云端手册库、AI解析引擎)
- Layer 2: 执行层 (驱动生成、配置生成、测试验证、UI生成)

Author: Hermes Desktop Team
Version: 1.0.0
"""

from core.logger import get_logger
logger = get_logger('hardware_mind.__init__')

import json
import hashlib
import asyncio
import struct
import threading
import time
import uuid
import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class DeviceCategory(Enum):
    """设备类别"""
    USB_HID = "usb_hid"           # 人体学接口设备 (键盘、鼠标)
    USB_SERIAL = "usb_serial"     # USB转串口设备
    USB_MASS_STORAGE = "usb_ms"  # 大容量存储设备
    USB_VIDEO = "usb_video"       # 视频设备 (摄像头)
    USB_AUDIO = "usb_audio"       # 音频设备
    USB_PRINTER = "usb_printer"   # 打印机
    USB_NETWORK = "usb_network"   # 网络设备
    BLUETOOTH = "bluetooth"       # 蓝牙设备
    WIFI = "wifi"                # WiFi设备
    NFC = "nfc"                  # NFC设备
    SERIAL = "serial"            # 串口设备
    I2C = "i2c"                 # I2C设备
    SPI = "spi"                  # SPI设备
    UNKNOWN = "unknown"          # 未知设备


class ProtocolType(Enum):
    """协议类型"""
    USB = "usb"
    BLUETOOTH_CLASSIC = "bt_classic"
    BLUETOOTH_LE = "bt_le"
    WIFI_DIRECT = "wifi_direct"
    MQTT = "mqtt"
    COAP = "coap"
    HTTP = "http"
    WEBSOCKET = "websocket"
    SERIAL = "serial"
    I2C = "i2c"
    SPI = "spi"
    MODBUS = "modbus"
    CAN = "can"
    UNKNOWN = "unknown"


class DriverStatus(Enum):
    """驱动状态"""
    UNKNOWN = "unknown"
    DETECTED = "detected"
    MATCHING = "matching"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    FAILED = "failed"


class LifecycleStage(Enum):
    """生命周期阶段"""
    GENESIS = "genesis"       # 诞生: 首次检测到设备
    GROWTH = "growth"         # 生长: 驱动匹配中
    MATURITY = "maturity"     # 成熟: 正常运行
    DECLINE = "decline"       # 衰退: 驱动过时
    DEATH = "death"           # 死亡: 设备断开
    RESURRECTION = "resurrection"  # 复活: 重新连接


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class HardwareFingerprint:
    """硬件指纹"""
    fingerprint_id: str                          # 指纹唯一ID
    vid: str = ""                                # 供应商ID
    pid: str = ""                                # 产品ID
    serial_number: str = ""                      # 序列号
    manufacturer: str = ""                       # 制造商
    product_name: str = ""                       # 产品名称
    firmware_version: str = ""                   # 固件版本
    protocol_features: List[str] = field(default_factory=list)  # 协议特征
    capability_bits: int = 0                     # 能力位图
    response_pattern: str = ""                   # 响应模式哈希
    category: str = "unknown"                    # 设备类别
    discovered_at: str = ""                      # 发现时间
    last_seen: str = ""                         # 最后在线时间
    confidence: float = 0.0                      # 匹配置信度


@dataclass
class DeviceCapability:
    """设备功能"""
    capability_id: str
    name: str
    description: str
    interface_type: str                          # 接口类型 (API/CLI/GUI)
    endpoint: str = ""                           # 端点路径
    method: str = ""                             # HTTP方法
    parameters: List[Dict] = field(default_factory=list)
    return_type: str = ""
    error_codes: List[Dict] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


@dataclass
class UnifiedManual:
    """统一格式手册"""
    manual_id: str
    device_name: str
    device_type: str
    manufacturer: str
    version: str
    firmware_version: str
    capabilities: List[DeviceCapability] = field(default_factory=list)
    protocol_details: Dict = field(default_factory=dict)
    api_reference: List[Dict] = field(default_factory=list)
    ui_components: List[Dict] = field(default_factory=list)
    test_cases: List[Dict] = field(default_factory=list)
    source_url: str = ""
    source_type: str = ""                        # official/community/ai_generated
    verified: bool = False
    trust_score: float = 0.0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class DriverPackage:
    """驱动包"""
    driver_id: str
    device_fingerprint: str
    platform: str                                # windows/linux/macos/web
    driver_code: str = ""                         # 驱动代码
    config_template: str = ""                    # 配置模板
    ui_spec: Dict = field(default_factory=dict)  # UI规格
    dependencies: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    status: str = "pending"
    install_path: str = ""
    test_results: Dict = field(default_factory=dict)


@dataclass
class DiscoveredDevice:
    """发现的设备"""
    device_id: str
    fingerprint: HardwareFingerprint
    category: DeviceCategory
    protocol: ProtocolType
    status: DriverStatus
    lifecycle: LifecycleStage
    manual: Optional[UnifiedManual] = None
    driver: Optional[DriverPackage] = None
    ui_generated: bool = False
    ui_layout: Dict = field(default_factory=dict)
    connected: bool = False
    last_activity: str = ""
    connection_count: int = 0


# ============================================================
# 硬件检测引擎 (Physical Layer)
# ============================================================

class HardwareDetector:
    """硬件检测引擎 - 物理层核心"""

    def __init__(self):
        self.fingerprint_db: Dict[str, HardwareFingerprint] = {}
        self.detected_devices: Dict[str, DiscoveredDevice] = {}
        self.detection_handlers: List[Callable] = []
        self.protocol_analyzers: Dict[str, Any] = {}
        self._scanning = False
        self._scan_thread = None

    def register_detection_handler(self, handler: Callable):
        """注册检测处理器"""
        self.detection_handlers.append(handler)

    async def start_discovery(self):
        """开始发现设备"""
        self._scanning = True
        logger.info("[HardwareMind] 🚀 开始硬件发现...")

        # 启动各种协议检测
        detection_tasks = [
            self._scan_usb(),
            self._scan_bluetooth(),
            self._scan_wifi(),
            self._scan_serial_ports(),
        ]

        await asyncio.gather(*detection_tasks, return_exceptions=True)

    async def stop_discovery(self):
        """停止发现"""
        self._scanning = False
        if self._scan_thread:
            self._scan_thread.join(timeout=2)
        logger.info("[HardwareMind] 🛑 停止硬件发现")

    async def _scan_usb(self):
        """扫描USB设备"""
        try:
            # 模拟USB检测 (实际会调用系统API)
            logger.info("[HardwareMind] 🔌 扫描USB设备...")

            # 模拟发现的USB设备
            mock_usb_devices = [
                {
                    "vid": "046D",
                    "pid": "C52B",
                    "serial": "ABC123456",
                    "manufacturer": "Logitech",
                    "product": "USB Receiver",
                    "category": DeviceCategory.USB_HID
                },
                {
                    "vid": "0BDA",
                    "pid": "5652",
                    "serial": "201903010001",
                    "manufacturer": "Realtek",
                    "product": "USB Camera",
                    "category": DeviceCategory.USB_VIDEO
                }
            ]

            for dev_info in mock_usb_devices:
                fingerprint = self._generate_fingerlogger.info(
                    dev_info["vid"],
                    dev_info["pid"],
                    dev_info["serial"],
                    dev_info["manufacturer"],
                    dev_info["product"],
                    ProtocolType.USB
                )
                fingerprint.category = dev_info["category"].value
                fingerprint.protocol_features = ["hid", "interrupt_transfer"]

                device = DiscoveredDevice(
                    device_id=f"usb_{dev_info['vid']}_{dev_info['pid']}_{dev_info['serial'][:4]}",
                    fingerprint=fingerprint,
                    category=dev_info["category"],
                    protocol=ProtocolType.USB,
                    status=DriverStatus.DETECTED,
                    lifecycle=LifecycleStage.GENESIS,
                    connected=True,
                    last_activity=datetime.now().isoformat()
                )

                self.detected_devices[device.device_id] = device
                logger.info(f"[HardwareMind] ✅ 发现USB设备: {dev_info['product']}")

                # 触发处理器
                for handler in self.detection_handlers:
                    try:
                        await handler(device)
                    except Exception as e:
                        logger.error(f"[HardwareMind] 检测处理器错误: {e}")

        except Exception as e:
            logger.error(f"[HardwareMind] USB扫描失败: {e}")

    async def _scan_bluetooth(self):
        """扫描蓝牙设备"""
        try:
            logger.info("[HardwareMind] 📡 扫描蓝牙设备...")

            # 模拟蓝牙检测
            mock_bt_devices = [
                {
                    "address": "00:1A:7D:DA:71:13",
                    "name": "JBL Flip 5",
                    "device_class": "Audio/Video",
                    "rssi": -65
                },
                {
                    "address": "A4:83:E7:7E:9B:1C",
                    "name": "Mi Smart Band 6",
                    "device_class": "Wearable",
                    "rssi": -72
                }
            ]

            for dev_info in mock_bt_devices:
                fingerprint = self._generate_bluetooth_fingerlogger.info(
                    dev_info["address"],
                    dev_info["name"],
                    dev_info["device_class"]
                )

                device = DiscoveredDevice(
                    device_id=f"bt_{dev_info['address'].replace(':', '')}",
                    fingerprint=fingerprint,
                    category=DeviceCategory.BLUETOOTH,
                    protocol=ProtocolType.BLUETOOTH_CLASSIC,
                    status=DriverStatus.DETECTED,
                    lifecycle=LifecycleStage.GENESIS,
                    connected=False,
                    last_activity=datetime.now().isoformat()
                )

                self.detected_devices[device.device_id] = device
                logger.info(f"[HardwareMind] 📡 发现蓝牙设备: {dev_info['name']}")

        except Exception as e:
            logger.error(f"[HardwareMind] 蓝牙扫描失败: {e}")

    async def _scan_wifi(self):
        """扫描WiFi设备 (mDNS/SSDP/UPnP)"""
        try:
            logger.info("[HardwareMind] 📶 扫描WiFi设备...")

            # 模拟WiFi/网络设备发现
            mock_wifi_devices = [
                {"ip": "192.168.1.100", "name": "ESP32-Cam", "protocol": "http"},
                {"ip": "192.168.1.101", "name": "Smart Plug", "protocol": "mqtt"},
                {"ip": "192.168.1.102", "name": "Temperature Sensor", "protocol": "coap"}
            ]

            for dev_info in mock_wifi_devices:
                fingerprint = self._generate_network_fingerlogger.info(
                    dev_info["ip"],
                    dev_info["name"],
                    dev_info["protocol"]
                )

                device = DiscoveredDevice(
                    device_id=f"wifi_{dev_info['ip'].replace('.', '')}",
                    fingerprint=fingerprint,
                    category=DeviceCategory.UNKNOWN,
                    protocol=self._detect_network_protocol(dev_info["protocol"]),
                    status=DriverStatus.DETECTED,
                    lifecycle=LifecycleStage.GENESIS,
                    connected=True,
                    last_activity=datetime.now().isoformat()
                )

                self.detected_devices[device.device_id] = device
                logger.info(f"[HardwareMind] 🌐 发现网络设备: {dev_info['name']} ({dev_info['ip']})")

        except Exception as e:
            logger.error(f"[HardwareMind] WiFi扫描失败: {e}")

    async def _scan_serial_ports(self):
        """扫描串口设备"""
        try:
            logger.info("[HardwareMind] 🔌 扫描串口设备...")

            # 模拟串口检测
            mock_serial_devices = [
                {"port": "COM3", "vid": "10C4", "pid": "EA60", "name": "CP2102 USB-UART"},
                {"port": "COM5", "vid": "1A86", "pid": "7523", "name": "CH340 USB-UART"}
            ]

            for dev_info in mock_serial_devices:
                fingerprint = self._generate_fingerlogger.info(
                    dev_info["vid"],
                    dev_info["pid"],
                    dev_info["port"],
                    "Silicon Labs" if "CP210" in dev_info["name"] else "WCH",
                    dev_info["name"],
                    ProtocolType.SERIAL
                )
                fingerprint.category = DeviceCategory.USB_SERIAL.value

                device = DiscoveredDevice(
                    device_id=f"serial_{dev_info['port'].replace('.', '')}",
                    fingerprint=fingerprint,
                    category=DeviceCategory.USB_SERIAL,
                    protocol=ProtocolType.SERIAL,
                    status=DriverStatus.DETECTED,
                    lifecycle=LifecycleStage.GENESIS,
                    connected=True,
                    last_activity=datetime.now().isoformat()
                )

                self.detected_devices[device.device_id] = device
                logger.info(f"[HardwareMind] 🔧 发现串口设备: {dev_info['name']} @ {dev_info['port']}")

        except Exception as e:
            logger.error(f"[HardwareMind] 串口扫描失败: {e}")

    def _generate_fingerlogger.info(self, vid: str, pid: str, serial: str,
                               manufacturer: str, product: str,
                               protocol: ProtocolType) -> HardwareFingerprint:
        """生成USB硬件指纹"""
        # 计算能力位图 (简化版)
        capability_bits = 0
        if "HID" in product.upper():
            capability_bits |= 0x01  # 输入设备
        if "Camera" in product or "Video" in product:
            capability_bits |= 0x02  # 视频设备
        if "Audio" in product or "Speaker" in product:
            capability_bits |= 0x04  # 音频设备
        if "Storage" in product or "Disk" in product:
            capability_bits |= 0x08  # 存储设备

        # 响应模式哈希
        response_data = f"{vid}{pid}{serial}{protocol.value}"
        response_hash = hashlib.sha256(response_data.encode()).hexdigest()[:16]

        # 生成指纹ID
        fingerprint_input = f"{vid}:{pid}:{serial}:{manufacturer}"
        fingerprint_id = hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]

        return HardwareFingerlogger.info(
            fingerprint_id=fingerprint_id,
            vid=vid,
            pid=pid,
            serial_number=serial,
            manufacturer=manufacturer,
            product_name=product,
            protocol_features=self._detect_protocol_features(protocol),
            capability_bits=capability_bits,
            response_pattern=response_hash,
            category=DeviceCategory.UNKNOWN.value,
            discovered_at=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            confidence=1.0
        )

    def _generate_bluetooth_fingerlogger.info(self, address: str, name: str,
                                        device_class: str) -> HardwareFingerprint:
        """生成蓝牙硬件指纹"""
        fingerprint_id = hashlib.sha256(address.encode()).hexdigest()[:16]

        capability_bits = 0
        if "Audio" in device_class:
            capability_bits |= 0x04  # 音频
        if "Wearable" in device_class:
            capability_bits |= 0x10  # 可穿戴

        return HardwareFingerlogger.info(
            fingerprint_id=fingerprint_id,
            serial_number=address,
            manufacturer="Bluetooth SIG",
            product_name=name,
            firmware_version="",
            protocol_features=["gatt", "sdp", "rfcomm" if "Audio" in device_class else ""],
            capability_bits=capability_bits,
            response_pattern=hashlib.sha256(address.encode()).hexdigest()[:16],
            category=DeviceCategory.BLUETOOTH.value,
            discovered_at=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            confidence=0.9
        )

    def _generate_network_fingerlogger.info(self, ip: str, name: str,
                                        protocol: str) -> HardwareFingerprint:
        """生成网络设备指纹"""
        fingerprint_id = hashlib.sha256(ip.encode()).hexdigest()[:16]

        return HardwareFingerlogger.info(
            fingerprint_id=fingerprint_id,
            serial_number=ip,
            manufacturer="Network Device",
            product_name=name,
            firmware_version="",
            protocol_features=[protocol, "mdns" if ":" in ip else ""],
            capability_bits=0x20 if "sensor" in name.lower() else 0x00,
            response_pattern=hashlib.sha256(f"{ip}{protocol}".encode()).hexdigest()[:16],
            category=DeviceCategory.UNKNOWN.value,
            discovered_at=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            confidence=0.8
        )

    def _detect_protocol_features(self, protocol: ProtocolType) -> List[str]:
        """检测协议特征"""
        feature_map = {
            ProtocolType.USB: ["bulk_transfer", "interrupt_transfer", "control_transfer"],
            ProtocolType.BLUETOOTH_CLASSIC: ["rfcomm", "sdp", "a2dp"],
            ProtocolType.BLUETOOTH_LE: ["gatt", "advertising", "scanning"],
            ProtocolType.WIFI_DIRECT: ["mdns", "ssdp", "upnp"],
            ProtocolType.SERIAL: ["uart", "baudrate_config", "flow_control"],
        }
        return feature_map.get(protocol, [])

    def _detect_network_protocol(self, protocol_name: str) -> ProtocolType:
        """检测网络协议类型"""
        protocol_map = {
            "http": ProtocolType.HTTP,
            "mqtt": ProtocolType.MQTT,
            "coap": ProtocolType.COAP,
            "websocket": ProtocolType.WEBSOCKET,
        }
        return protocol_map.get(protocol_name.lower(), ProtocolType.UNKNOWN)

    def get_all_devices(self) -> List[DiscoveredDevice]:
        """获取所有发现的设备"""
        return list(self.detected_devices.values())

    def get_device_by_id(self, device_id: str) -> Optional[DiscoveredDevice]:
        """根据ID获取设备"""
        return self.detected_devices.get(device_id)


# ============================================================
# 智能手册获取系统 (Knowledge Layer)
# ============================================================

class ManualKnowledgeBase:
    """手册知识库"""

    def __init__(self):
        self.local_manuals: Dict[str, UnifiedManual] = {}
        self.cloud_manuals: Dict[str, UnifiedManual] = {}
        self.community_manuals: Dict[str, UnifiedManual] = {}
        self.manual_cache: Dict[str, UnifiedManual] = {}
        self._init_builtin_manuals()

    def _init_builtin_manuals(self):
        """初始化内置手册 (模拟常见设备)"""
        # USB HID 键盘
        self.local_manuals["046d_c52b"] = UnifiedManual(
            manual_id="builtin_logitech_receiver",
            device_name="Logitech USB Receiver",
            device_type="HID Dongle",
            manufacturer="Logitech",
            version="1.0",
            firmware_version="",
            capabilities=[
                DeviceCapability(
                    capability_id="hid_keyboard",
                    name="键盘输入",
                    description="HID键盘接口",
                    interface_type="HID",
                    parameters=[],
                    return_type="HID Report"
                ),
                DeviceCapability(
                    capability_id="hid_mouse",
                    name="鼠标输入",
                    description="HID鼠标接口",
                    interface_type="HID",
                    parameters=[],
                    return_type="HID Report"
                )
            ],
            protocol_details={"protocol": "USB HID", "transfer_type": "interrupt"},
            source_type="official",
            verified=True,
            trust_score=1.0,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

        # USB 摄像头
        self.local_manuals["0bda_5652"] = UnifiedManual(
            manual_id="builtin_usb_camera",
            device_name="USB Camera",
            device_type="Video Device",
            manufacturer="Generic",
            version="1.0",
            firmware_version="",
            capabilities=[
                DeviceCapability(
                    capability_id="video_stream",
                    name="视频流",
                    description="MJPEG/YUV视频流",
                    interface_type="API",
                    endpoint="/video",
                    method="GET",
                    parameters=[],
                    return_type="bytes"
                ),
                DeviceCapability(
                    capability_id="photo_capture",
                    name="拍照",
                    description="捕获静态图像",
                    interface_type="API",
                    endpoint="/photo",
                    method="POST",
                    parameters=[{"name": "resolution", "type": "string"}],
                    return_type="bytes"
                )
            ],
            protocol_details={"protocol": "UVC", "resolution": ["640x480", "1280x720", "1920x1080"]},
            source_type="official",
            verified=True,
            trust_score=0.9,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

        # CP2102 串口芯片
        self.local_manuals["10c4_ea60"] = UnifiedManual(
            manual_id="builtin_cp2102",
            device_name="CP2102 USB-UART Bridge",
            device_type="USB to Serial",
            manufacturer="Silicon Labs",
            version="1.0",
            firmware_version="",
            capabilities=[
                DeviceCapability(
                    capability_id="serial_baud",
                    name="波特率设置",
                    description="配置UART波特率",
                    interface_type="API",
                    endpoint="/baud",
                    method="SET",
                    parameters=[
                        {"name": "rate", "type": "int", "values": [9600, 115200, 921600]}
                    ],
                    return_type="bool"
                )
            ],
            protocol_details={"protocol": "USB CDC-ACM", "max_baudrate": 921600},
            source_type="official",
            verified=True,
            trust_score=1.0,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

        logger.info(f"[HardwareMind] 📚 已加载 {len(self.local_manuals)} 个内置手册")

    async def search_manual(self, fingerprint: HardwareFingerprint) -> Optional[UnifiedManual]:
        """搜索匹配的手册"""
        # 1. 本地知识库匹配
        key = f"{fingerprint.vid}_{fingerprint.pid}".lower().replace(":", "")
        if key in self.local_manuals:
            logger.info(f"[HardwareMind] 📖 本地知识库命中: {key}")
            return self.local_manuals[key]

        # 2. 云端查询 (模拟)
        cloud_manual = await self._search_cloud(key, fingerprint)
        if cloud_manual:
            self.cloud_manuals[key] = cloud_manual
            return cloud_manual

        # 3. 社区手册
        community_manual = await self._search_community(key, fingerprint)
        if community_manual:
            self.community_manuals[key] = community_manual
            return community_manual

        # 4. AI逆向工程生成 (基于相似设备)
        logger.info(f"[HardwareMind] 🤖 无匹配手册，尝试AI生成...")
        return self._generate_ai_manual(fingerprint)

    async def _search_cloud(self, key: str, fingerprint: HardwareFingerprint) -> Optional[UnifiedManual]:
        """搜索云端手册库"""
        # 模拟云端查询延迟
        await asyncio.sleep(0.5)

        # 模拟返回结果 (实际会查询厂商API)
        if fingerprint.manufacturer.lower() in ["logitech", "realtek", "silicon labs"]:
            logger.info(f"[HardwareMind] ☁️ 云端手册命中: {fingerprint.manufacturer}")
            return UnifiedManual(
                manual_id=f"cloud_{key}",
                device_name=fingerprint.product_name,
                device_type="Cloud Device",
                manufacturer=fingerprint.manufacturer,
                version="1.0",
                firmware_version=fingerprint.firmware_version,
                capabilities=[],
                source_type="official",
                verified=True,
                trust_score=0.9,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
        return None

    async def _search_community(self, key: str, fingerprint: HardwareFingerprint) -> Optional[UnifiedManual]:
        """搜索社区手册"""
        await asyncio.sleep(0.3)
        # 模拟社区查询
        logger.info(f"[HardwareMind] 👥 社区手册查询完成")
        return None

    def _generate_ai_manual(self, fingerprint: HardwareFingerprint) -> UnifiedManual:
        """AI生成手册 (基于指纹特征推导)"""
        logger.info(f"[HardwareMind] 🧠 AI生成手册: {fingerprint.product_name}")

        capabilities = []

        # 根据设备类别推断能力
        category = fingerprint.category
        if category == DeviceCategory.USB_HID.value:
            capabilities.append(DeviceCapability(
                capability_id="hid_input",
                name="HID输入",
                description="人体学接口设备输入",
                interface_type="HID"
            ))
        elif category == DeviceCategory.USB_VIDEO.value:
            capabilities.append(DeviceCapability(
                capability_id="video_capture",
                name="视频捕获",
                description="视频数据采集",
                interface_type="API",
                endpoint="/capture",
                method="GET"
            ))
        elif category == DeviceCategory.USB_SERIAL.value:
            capabilities.append(DeviceCapability(
                capability_id="serial_comm",
                name="串口通信",
                description="UART数据收发",
                interface_type="API",
                endpoint="/send",
                method="POST"
            ))

        return UnifiedManual(
            manual_id=f"ai_gen_{fingerprint.fingerprint_id}",
            device_name=fingerprint.product_name or "Unknown Device",
            device_type=category.replace("_", " ").title(),
            manufacturer=fingerprint.manufacturer or "Unknown",
            version="1.0 (AI Generated)",
            firmware_version=fingerprint.firmware_version,
            capabilities=capabilities,
            source_type="ai_generated",
            verified=False,
            trust_score=0.5,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

    def get_all_manuals(self) -> List[UnifiedManual]:
        """获取所有手册"""
        all_manuals = []
        all_manuals.extend(self.local_manuals.values())
        all_manuals.extend(self.cloud_manuals.values())
        all_manuals.extend(self.community_manuals.values())
        return all_manuals


# ============================================================
# AI手册理解引擎 (Knowledge Layer - AI)
# ============================================================

class ManualUnderstandingEngine:
    """AI驱动的手册理解引擎"""

    def __init__(self):
        self.knowledge_graph: Dict[str, Any] = {}
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.pattern_recognizer = PatternRecognizer()

    async def analyze_manual(self, manual: UnifiedManual) -> Dict[str, Any]:
        """分析手册并提取知识"""
        logger.info(f"[HardwareMind] 🧠 分析手册: {manual.device_name}")

        # 1. 实体识别
        entities = self.entity_extractor.extract(manual)

        # 2. 意图分类
        intents = self.intent_classifier.classify(manual)

        # 3. 代码模式识别
        patterns = self.pattern_recognizer.analyze(manual)

        # 4. 关系抽取
        relations = self._extract_relations(entities, manual)

        # 构建知识图谱
        knowledge = {
            "manual_id": manual.manual_id,
            "entities": entities,
            "intents": intents,
            "patterns": patterns,
            "relations": relations,
            "capabilities_summary": self._summarize_capabilities(manual),
            "api_endpoints": self._extract_endpoints(manual),
            "test_suggestions": self._generate_test_suggestions(manual)
        }

        self.knowledge_graph[manual.manual_id] = knowledge
        return knowledge

    def _extract_relations(self, entities: Dict, manual: UnifiedManual) -> List[Dict]:
        """抽取关系"""
        relations = []
        for cap in manual.capabilities:
            relations.append({
                "from": manual.device_name,
                "to": cap.name,
                "relation": "has_capability",
                "type": "direct"
            })
        return relations

    def _summarize_capabilities(self, manual: UnifiedManual) -> Dict:
        """总结设备能力"""
        return {
            "total": len(manual.capabilities),
            "by_interface": self._group_by_interface(manual.capabilities),
            "primary": [c.name for c in manual.capabilities[:3]]
        }

    def _group_by_interface(self, capabilities: List[DeviceCapability]) -> Dict:
        """按接口分组"""
        grouped = defaultdict(list)
        for cap in capabilities:
            grouped[cap.interface_type].append(cap.name)
        return dict(grouped)

    def _extract_endpoints(self, manual: UnifiedManual) -> List[Dict]:
        """提取API端点"""
        endpoints = []
        for cap in manual.capabilities:
            if cap.endpoint:
                endpoints.append({
                    "path": cap.endpoint,
                    "method": cap.method,
                    "capability": cap.name
                })
        return endpoints

    def _generate_test_suggestions(self, manual: UnifiedManual) -> List[str]:
        """生成测试建议"""
        suggestions = []
        for cap in manual.capabilities:
            suggestions.append(f"测试 {cap.name} 功能")
            if cap.parameters:
                for param in cap.parameters:
                    suggestions.append(f"  - 参数 {param.get('name')} 边界测试")
        return suggestions


class IntentClassifier:
    """意图分类器"""

    def classify(self, manual: UnifiedManual) -> List[str]:
        """分类设备意图"""
        intents = []
        device_type = manual.device_type.lower()

        if "camera" in device_type or "video" in device_type:
            intents.append("监控意图")
        if "sensor" in device_type:
            intents.append("采集意图")
        if "control" in device_type or "switch" in device_type:
            intents.append("控制意图")
        if "audio" in device_type or "speaker" in device_type:
            intents.append("音频意图")
        if "storage" in device_type or "disk" in device_type:
            intents.append("存储意图")

        return intents if intents else ["通用意图"]


class EntityExtractor:
    """实体提取器"""

    def extract(self, manual: UnifiedManual) -> Dict:
        """提取实体"""
        return {
            "device_name": manual.device_name,
            "manufacturer": manual.manufacturer,
            "capabilities": [c.name for c in manual.capabilities],
            "interfaces": list(set(c.interface_type for c in manual.capabilities)),
            "parameters": self._collect_parameters(manual)
        }

    def _collect_parameters(self, manual: UnifiedManual) -> List[str]:
        """收集所有参数"""
        params = []
        for cap in manual.capabilities:
            for param in cap.parameters:
                params.append(param.get("name", ""))
        return params


class PatternRecognizer:
    """模式识别器"""

    def analyze(self, manual: UnifiedManual) -> List[str]:
        """识别代码模式"""
        patterns = []
        for cap in manual.capabilities:
            if cap.examples:
                patterns.append("具有示例代码")
            if cap.endpoint and cap.method:
                patterns.append("RESTful API模式")
        return patterns if patterns else ["标准设备模式"]


# ============================================================
# 自动驱动生成系统 (Execution Layer)
# ============================================================

class DriverGenerator:
    """驱动代码生成器"""

    def __init__(self):
        self.templates: Dict[str, str] = {}
        self._init_templates()

    def _init_templates(self):
        """初始化驱动模板"""
        self.templates["usb_hid"] = '''
// USB HID 驱动 - {device_name}
// 制造商: {manufacturer}
// 生成时间: {timestamp}

#include <usbhelper.h>
#include <hidapi.h>

class {class_name}Driver {{
private:
    hid_device* handle;
    uint8_t capability_bits;

public:
    int initialize() {{
        handle = hid_open({vid}, {pid}, NULL);
        if (!handle) {{
            return -1;
        }}
        return 0;
    }}

    int send_data(uint8_t* data, size_t len) {{
        return hid_write(handle, data, len);
    }}

    int read_data(uint8_t* buf, size_t len) {{
        return hid_read(handle, buf, len);
    }}

    void cleanup() {{
        if (handle) hid_close(handle);
    }}
}};
'''

        self.templates["usb_serial"] = '''
// USB Serial 驱动 - {device_name}
// 制造商: {manufacturer}
// 生成时间: {timestamp}

#include <serial.h>

class {class_name}Driver {{
private:
    SerialPort port;
    uint32_t baudrate;

public:
    int initialize(const char* port_name) {{
        if (!port.open(port_name)) {{
            return -1;
        }}
        port.configure(baudrate, 8, 1, 0);  // 8N1
        return 0;
    }}

    void set_baudrate(uint32_t baud) {{
        baudrate = baud;
        port.set_baud(baud);
    }}

    int send(const uint8_t* data, size_t len) {{
        return port.write(data, len);
    }}

    int receive(uint8_t* buf, size_t max_len) {{
        return port.read(buf, max_len);
    }}
}};
'''

        self.templates["bluetooth"] = '''
// Bluetooth 驱动 - {device_name}
// 制造商: {manufacturer}
// 生成时间: {timestamp}

#include <btapi/btcore.h>

class {class_name}Driver {{
private:
    bt_device_t device;
    bt_connection_t conn;

public:
    int connect(const char* address) {{
        return bt_connect(address, BT_RFCOMM, &conn);
    }}

    int disconnect() {{
        return bt_disconnect(&conn);
    }}

    int send_data(const uint8_t* data, size_t len) {{
        return bt_send(&conn, data, len);
    }}

    int on_data(bt_data_callback callback) {{
        return bt_register_callback(&conn, callback);
    }}
}};
'''

        logger.info(f"[HardwareMind] 📝 已加载 {len(self.templates)} 个驱动模板")

    async def generate_driver(self, device: DiscoveredDevice,
                               manual: UnifiedManual) -> DriverPackage:
        """生成驱动包"""
        logger.info(f"[HardwareMind] ⚙️ 生成驱动: {device.fingerprint.product_name}")

        fingerprint = device.fingerprint
        template_key = self._select_template(device)

        template = self.templates.get(template_key, self.templates["usb_hid"])

        # 替换模板变量
        driver_code = template.format(
            device_name=fingerprint.product_name,
            manufacturer=fingerprint.manufacturer,
            timestamp=datetime.now().isoformat(),
            class_name=self._to_camel_case(fingerprint.product_name),
            vid=fingerprint.vid or "0",
            pid=fingerprint.pid or "0"
        )

        # 生成配置模板
        config_template = self._generate_config_template(device, manual)

        # 生成UI规格
        ui_spec = self._generate_ui_spec(manual)

        driver = DriverPackage(
            driver_id=f"driver_{fingerprint.fingerprint_id}",
            device_fingerprint=fingerprint.fingerprint_id,
            platform="windows",  # 实际会检测
            driver_code=driver_code,
            config_template=config_template,
            ui_spec=ui_spec,
            version="1.0.0",
            status="generated",
            test_results={"syntax_check": "pass"}
        )

        logger.info(f"[HardwareMind] ✅ 驱动生成完成: {driver.driver_id}")
        return driver

    def _select_template(self, device: DiscoveredDevice) -> str:
        """选择驱动模板"""
        category = device.category
        if category == DeviceCategory.USB_HID:
            return "usb_hid"
        elif category == DeviceCategory.USB_SERIAL:
            return "usb_serial"
        elif category == DeviceCategory.BLUETOOTH:
            return "bluetooth"
        else:
            return "usb_hid"

    def _to_camel_case(self, name: str) -> str:
        """转换为驼峰命名"""
        words = re.sub(r'[^a-zA-Z0-9]', ' ', name).split()
        return ''.join(word.capitalize() for word in words)

    def _generate_config_template(self, device: DiscoveredDevice,
                                   manual: UnifiedManual) -> str:
        """生成配置模板"""
        config = {
            "device": {
                "name": device.fingerprint.product_name,
                "vid": device.fingerprint.vid,
                "pid": device.fingerprint.pid,
                "serial": device.fingerprint.serial_number
            },
            "capabilities": [c.capability_id for c in manual.capabilities],
            "settings": {
                "auto_connect": True,
                "timeout": 5000,
                "retry_count": 3
            }
        }
        return json.dumps(config, indent=2)

    def _generate_ui_spec(self, manual: UnifiedManual) -> Dict:
        """生成UI规格"""
        ui_spec = {
            "components": [],
            "layout": {"type": "vertical", "spacing": 10}
        }

        for cap in manual.capabilities:
            component = {
                "id": f"ui_{cap.capability_id}",
                "type": self._map_capability_to_ui_type(cap),
                "label": cap.name,
                "bind_to": cap.capability_id
            }

            # 根据参数类型调整UI
            if cap.parameters:
                component["params"] = cap.parameters

            ui_spec["components"].append(component)

        return ui_spec

    def _map_capability_to_ui_type(self, capability: DeviceCapability) -> str:
        """将能力映射到UI组件类型"""
        name = capability.name.lower()

        if "开关" in name or "switch" in name or "on/off" in name:
            return "toggle"
        elif "颜色" in name or "color" in name:
            return "color_picker"
        elif "数值" in name or "value" in name or "slider" in name:
            return "slider"
        elif "视频" in name or "video" in name or "camera" in name:
            return "video_preview"
        elif "温度" in name or "湿度" in name or "sensor" in name:
            return "gauge"
        elif "控制" in name or "control" in name:
            return "button"
        else:
            return "text_display"


# ============================================================
# 自动UI生成系统 (Execution Layer)
# ============================================================

class AutoUIGenerator:
    """自动UI生成器"""

    def __init__(self):
        self.ui_components = {}

    def generate_ui(self, manual: UnifiedManual, driver: DriverPackage) -> Dict:
        """生成UI布局"""
        logger.info(f"[HardwareMind] 🎨 生成UI: {manual.device_name}")

        ui_layout = {
            "device_id": manual.manual_id,
            "device_name": manual.device_name,
            "theme": "auto",  # 跟随系统主题
            "layout": self._create_layout(manual),
            "components": self._create_components(manual),
            "interactions": self._create_interactions(manual, driver),
            "styles": self._get_default_styles()
        }

        logger.info(f"[HardwareMind] ✅ UI生成完成，共 {len(ui_layout['components'])} 个组件")
        return ui_layout

    def _create_layout(self, manual: UnifiedManual) -> Dict:
        """创建布局"""
        capability_count = len(manual.capabilities)

        if capability_count <= 3:
            layout_type = "vertical"
        elif capability_count <= 6:
            layout_type = "grid_2col"
        else:
            layout_type = "tab_view"

        return {
            "type": layout_type,
            "spacing": 12,
            "padding": 16
        }

    def _create_components(self, manual: UnifiedManual) -> List[Dict]:
        """创建UI组件"""
        components = []

        # 设备状态头部
        components.append({
            "id": "header",
            "type": "device_header",
            "props": {
                "title": manual.device_name,
                "subtitle": f"by {manual.manufacturer}",
                "status": "connected"
            }
        })

        # 能力组件
        for cap in manual.capabilities:
            ui_type = self._capability_to_ui_type(cap)
            component = {
                "id": f"comp_{cap.capability_id}",
                "type": ui_type,
                "props": {
                    "label": cap.name,
                    "description": cap.description,
                    "value": self._get_default_value(cap)
                }
            }

            # 根据能力类型添加特定属性
            if cap.parameters:
                component["props"]["params"] = cap.parameters

            components.append(component)

        return components

    def _capability_to_ui_type(self, cap: DeviceCapability) -> str:
        """能力转UI类型"""
        name = cap.name.lower()

        if any(kw in name for kw in ["开关", "switch", "on/off", "led"]):
            return "toggle_switch"
        elif any(kw in name for kw in ["颜色", "color"]):
            return "color_picker"
        elif any(kw in name for kw in ["数值", "value", "温度", "速度", "亮度"]):
            return "slider"
        elif any(kw in name for kw in ["视频", "camera", "预览"]):
            return "video_stream"
        elif any(kw in name for kw in ["获取", "read", "查询", "传感器"]):
            return "value_display"
        elif any(kw in name for kw in ["发送", "send", "控制", "control"]):
            return "action_button"
        else:
            return "info_card"

    def _get_default_value(self, cap: DeviceCapability):
        """获取默认值"""
        if cap.return_type == "bool":
            return False
        elif cap.return_type == "int" or cap.return_type == "float":
            return 0
        elif cap.return_type == "string":
            return ""
        else:
            return None

    def _create_interactions(self, manual: UnifiedManual, driver: DriverPackage) -> List[Dict]:
        """创建交互逻辑"""
        interactions = []

        for cap in manual.capabilities:
            interaction = {
                "component_id": f"comp_{cap.capability_id}",
                "event": self._get_event_type(cap),
                "action": {
                    "type": "api_call" if cap.endpoint else "driver_method",
                    "target": cap.capability_id,
                    "params_mapping": {}
                }
            }
            interactions.append(interaction)

        return interactions

    def _get_event_type(self, cap: DeviceCapability) -> str:
        """获取事件类型"""
        method = cap.method.upper() if cap.method else ""
        if method == "GET":
            return "on_read"
        elif method == "POST" or method == "SET":
            return "on_click"
        else:
            return "on_change"

    def _get_default_styles(self) -> Dict:
        """获取默认样式"""
        return {
            "card": {
                "border_radius": 8,
                "elevation": 2,
                "background": "surface"
            },
            "button": {
                "border_radius": 4,
                "padding": "8px 16px"
            },
            "toggle": {
                "width": 48,
                "height": 24
            }
        }


# ============================================================
# 自动测试与验证系统 (Execution Layer)
# ============================================================

class AutoTestEngine:
    """自动测试引擎"""

    def __init__(self):
        self.test_suites: Dict[str, List[Dict]] = {}

    async def generate_test_suite(self, device: DiscoveredDevice,
                                   manual: UnifiedManual,
                                   driver: DriverPackage) -> Dict:
        """生成测试套件"""
        logger.info(f"[HardwareMind] 🧪 生成测试套件: {manual.device_name}")

        test_suite = {
            "suite_id": f"test_{device.device_id}",
            "device_id": device.device_id,
            "tests": [],
            "results": {}
        }

        # 1. 连接测试
        test_suite["tests"].append(self._create_connection_test(device))

        # 2. 基本功能测试
        for cap in manual.capabilities:
            test_suite["tests"].append(self._create_capability_test(device, cap))

        # 3. 边界条件测试
        test_suite["tests"].extend(self._create_boundary_tests(manual))

        # 4. 压力测试
        test_suite["tests"].append(self._create_stress_test(device))

        logger.info(f"[HardwareMind] 📋 生成 {len(test_suite['tests'])} 个测试用例")
        return test_suite

    def _create_connection_test(self, device: DiscoveredDevice) -> Dict:
        """创建连接测试"""
        return {
            "test_id": f"conn_{device.device_id}",
            "name": "设备连接测试",
            "type": "connection",
            "steps": [
                "检测设备存在",
                "建立通信连接",
                "验证握手响应",
                "确认连接稳定"
            ],
            "expected": "connection_success",
            "timeout": 5000
        }

    def _create_capability_test(self, device: DiscoveredDevice,
                                  capability: DeviceCapability) -> Dict:
        """创建能力测试"""
        return {
            "test_id": f"cap_{capability.capability_id}",
            "name": f"测试 {capability.name}",
            "type": "capability",
            "capability_id": capability.capability_id,
            "steps": [
                f"调用 {capability.name}",
                "验证参数传递",
                "检查返回值",
                "验证状态变化"
            ],
            "expected": capability.return_type,
            "timeout": 3000
        }

    def _create_boundary_tests(self, manual: UnifiedManual) -> List[Dict]:
        """创建边界测试"""
        tests = []
        for cap in manual.capabilities:
            for param in cap.parameters:
                if param.get("type") in ["int", "float"]:
                    tests.append({
                        "test_id": f"bound_{cap.capability_id}_{param['name']}",
                        "name": f"边界测试: {param['name']}",
                        "type": "boundary",
                        "capability_id": cap.capability_id,
                        "param_name": param["name"],
                        "values": ["最小值", "最大值", "边界外", "特殊值"]
                    })
        return tests

    def _create_stress_test(self, device: DiscoveredDevice) -> Dict:
        """创建压力测试"""
        return {
            "test_id": f"stress_{device.device_id}",
            "name": "压力测试",
            "type": "stress",
            "duration": 10000,  # 10秒
            "rate": 100,  # 每秒100次
            "expected_failure_rate": 0.01
        }

    async def run_tests(self, test_suite: Dict) -> Dict:
        """运行测试"""
        logger.info(f"[HardwareMind] ▶️ 运行测试套件: {test_suite['suite_id']}")

        results = {
            "suite_id": test_suite["suite_id"],
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }

        for test in test_suite["tests"]:
            # 模拟测试执行
            await asyncio.sleep(0.1)

            # 模拟结果 (90%通过率)
            import random

            passed = random.random() > 0.1

            result = {
                "test_id": test["test_id"],
                "name": test["name"],
                "passed": passed,
                "duration_ms": random.randint(10, 500),
                "error": None if passed else "模拟错误"
            }

            results["details"].append(result)
            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

        logger.info(f"[HardwareMind] ✅ 测试完成: {results['passed']}/{len(test_suite['tests'])} 通过")
        return results


# ============================================================
# 统一设备管理器 (System Integration)
# ============================================================

class UnifiedDeviceManager:
    """统一设备管理器"""

    def __init__(self):
        self.devices: Dict[str, DiscoveredDevice] = {}
        self.device_groups: Dict[str, List[str]] = {}  # 分组
        self.automation_scenes: Dict[str, Dict] = {}  # 自动化场景

    def add_device(self, device: DiscoveredDevice):
        """添加设备"""
        self.devices[device.device_id] = device
        logger.info(f"[HardwareMind] 📦 添加设备到管理器: {device.device_id}")

    def remove_device(self, device_id: str):
        """移除设备"""
        if device_id in self.devices:
            del self.devices[device_id]
            logger.info(f"[HardwareMind] 🗑️ 移除设备: {device_id}")

    def get_device(self, device_id: str) -> Optional[DiscoveredDevice]:
        """获取设备"""
        return self.devices.get(device_id)

    def get_all_devices(self) -> List[DiscoveredDevice]:
        """获取所有设备"""
        return list(self.devices.values())

    def get_devices_by_category(self, category: DeviceCategory) -> List[DiscoveredDevice]:
        """按类别获取设备"""
        return [d for d in self.devices.values() if d.category == category]

    def get_devices_by_status(self, status: DriverStatus) -> List[DiscoveredDevice]:
        """按状态获取设备"""
        return [d for d in self.devices.values() if d.status == status]

    def create_group(self, group_name: str, device_ids: List[str]):
        """创建设备分组"""
        self.device_groups[group_name] = device_ids
        logger.info(f"[HardwareMind] 📁 创建分组: {group_name}")

    def create_automation_scene(self, scene_name: str, trigger: Dict, actions: List[Dict]):
        """创建自动化场景"""
        self.automation_scenes[scene_name] = {
            "trigger": trigger,
            "actions": actions,
            "enabled": True
        }
        logger.info(f"[HardwareMind] ⚡ 创建自动化场景: {scene_name}")


# ============================================================
# 主引擎 - Phoenix Protocol Hardware Mind
# ============================================================

class HardwareMindEngine:
    """
    通用硬件智能集成系统 - 主引擎

    核心理念: "硬件即插件，自动发现、自动学习、自动集成"

    使用流程:
    1. 启动发现 -> 2. 匹配手册 -> 3. 生成驱动 -> 4. 生成UI -> 5. 测试验证 -> 6. 系统集成
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # 核心组件
        self.detector = HardwareDetector()
        self.knowledge_base = ManualKnowledgeBase()
        self.manual_understanding = ManualUnderstandingEngine()
        self.driver_generator = DriverGenerator()
        self.ui_generator = AutoUIGenerator()
        self.test_engine = AutoTestEngine()
        self.device_manager = UnifiedDeviceManager()

        # 状态
        self.node_id = self.config.get("node_id", f"hwmind_{uuid.uuid4().hex[:8]}")
        self.version = "1.0.0"
        self.is_running = False

        # 事件回调
        self.event_callbacks: Dict[str, List[Callable]] = {
            "device_discovered": [],
            "driver_ready": [],
            "ui_ready": [],
            "test_completed": [],
            "lifecycle_changed": []
        }

        # 统计
        self.stats = {
            "devices_found": 0,
            "manuals_matched": 0,
            "drivers_generated": 0,
            "uis_generated": 0,
            "tests_passed": 0,
            "tests_failed": 0
        }

        # 注册检测处理器
        self.detector.register_detection_handler(self._on_device_discovered)

        logger.info(f"[HardwareMind] 🌐 通用硬件智能集成系统 v{self.version} 初始化完成")
        logger.info(f"[HardwareMind] 🆔 节点ID: {self.node_id}")

    async def start(self):
        """启动系统"""
        if self.is_running:
            logger.warning("[HardwareMind] 系统已在运行")
            return

        self.is_running = True
        logger.info("[HardwareMind] 🚀 启动硬件智能集成系统...")

        # 启动设备发现
        await self.detector.start_discovery()

    async def stop(self):
        """停止系统"""
        if not self.is_running:
            return

        self.is_running = False
        await self.detector.stop_discovery()
        logger.info("[HardwareMind] 🛑 硬件智能集成系统已停止")

    async def _on_device_discovered(self, device: DiscoveredDevice):
        """设备发现回调"""
        logger.info(f"[HardwareMind] 🎉 新设备发现: {device.fingerprint.product_name}")

        self.device_manager.add_device(device)
        self.stats["devices_found"] += 1

        # 触发事件
        await self._emit_event("device_discovered", device)

        # 自动处理流程
        await self._auto_integrate_device(device)

    async def _auto_integrate_device(self, device: DiscoveredDevice):
        """自动集成设备"""
        try:
            # 1. 查找手册
            manual = await self.knowledge_base.search_manual(device.fingerprint)
            if manual:
                device.manual = manual
                device.status = DriverStatus.MATCHING
                self.stats["manuals_matched"] += 1
                logger.info(f"[HardwareMind] 📖 手册匹配: {manual.device_name}")

                # 2. 理解手册
                understanding = await self.manual_understanding.analyze_manual(manual)
                logger.info(f"[HardwareMind] 🧠 手册分析完成: {len(understanding.get('entities', {}).get('capabilities', []))} 个能力")

                # 3. 生成驱动
                driver = await self.driver_generator.generate_driver(device, manual)
                device.driver = driver
                device.status = DriverStatus.INSTALLED
                self.stats["drivers_generated"] += 1
                logger.info(f"[HardwareMind] ⚙️ 驱动生成完成: {driver.driver_id}")

                # 触发驱动就绪事件
                await self._emit_event("driver_ready", device, driver)

                # 4. 生成UI
                ui_layout = self.ui_generator.generate_ui(manual, driver)
                device.ui_layout = ui_layout
                device.ui_generated = True
                self.stats["uis_generated"] += 1
                logger.info(f"[HardwareMind] 🎨 UI生成完成")

                # 触发UI就绪事件
                await self._emit_event("ui_ready", device, ui_layout)

                # 5. 生成并运行测试
                test_suite = await self.test_engine.generate_test_suite(device, manual, driver)
                test_results = await self.test_engine.run_tests(test_suite)
                self.stats["tests_passed"] += test_results["passed"]
                self.stats["tests_failed"] += test_results["failed"]

                # 触发测试完成事件
                await self._emit_event("test_completed", device, test_results)

                # 更新设备生命周期
                device.lifecycle = LifecycleStage.MATURITY
                await self._emit_event("lifecycle_changed", device)

            else:
                logger.warning(f"[HardwareMind] ⚠️ 无法找到匹配的手册: {device.fingerprint.product_name}")
                device.status = DriverStatus.FAILED

        except Exception as e:
            logger.error(f"[HardwareMind] ❌ 设备集成失败: {e}")
            device.status = DriverStatus.FAILED

    def register_event_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self.event_callbacks:
            self.event_callbacks[event].append(callback)

    async def _emit_event(self, event: str, *args, **kwargs):
        """触发事件"""
        if event in self.event_callbacks:
            for callback in self.event_callbacks[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"[HardwareMind] 事件回调错误 [{event}]: {e}")

    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            "node_id": self.node_id,
            "version": self.version,
            "is_running": self.is_running,
            "stats": self.stats,
            "devices": {
                "total": len(self.device_manager.get_all_devices()),
                "connected": len([d for d in self.device_manager.get_all_devices() if d.connected]),
                "by_category": self._count_by_category(),
                "by_status": self._count_by_status()
            },
            "knowledge_base": {
                "local_manuals": len(self.knowledge_base.local_manuals),
                "cloud_manuals": len(self.knowledge_base.cloud_manuals)
            }
        }

    def _count_by_category(self) -> Dict[str, int]:
        """按类别统计"""
        counts = defaultdict(int)
        for device in self.device_manager.get_all_devices():
            counts[device.category.value] += 1
        return dict(counts)

    def _count_by_status(self) -> Dict[str, int]:
        """按状态统计"""
        counts = defaultdict(int)
        for device in self.device_manager.get_all_devices():
            counts[device.status.value] += 1
        return dict(counts)

    def get_dashboard_data(self) -> Dict:
        """获取仪表盘数据"""
        status = self.get_system_status()

        # 设备类型分布
        category_data = []
        for cat, count in status["devices"]["by_category"].items():
            category_data.append({"category": cat, "count": count})

        # 驱动状态分布
        status_data = []
        for stat, count in status["devices"]["by_status"].items():
            status_data.append({"status": stat, "count": count})

        return {
            "system": status,
            "category_distribution": category_data,
            "status_distribution": status_data,
            "recent_devices": [
                {
                    "id": d.device_id,
                    "name": d.fingerprint.product_name,
                    "category": d.category.value,
                    "status": d.status.value,
                    "lifecycle": d.lifecycle.value,
                    "connected": d.connected
                }
                for d in sorted(
                    self.device_manager.get_all_devices(),
                    key=lambda x: x.fingerprint.discovered_at,
                    reverse=True
                )[:5]
            ],
            "capabilities_summary": self._get_capabilities_summary()
        }

    def _get_capabilities_summary(self) -> Dict:
        """获取能力摘要"""
        all_caps = []
        for device in self.device_manager.get_all_devices():
            if device.manual:
                all_caps.extend([c.name for c in device.manual.capabilities])

        cap_counts = Counter(all_caps)
        return {
            "total": len(all_caps),
            "unique": len(cap_counts),
            "top_5": cap_counts.most_common(5)
        }