"""
LivingTree 软件生命周期管理器
============================

Full migration from client/src/business/software_manager/

支持 winget/chocolatey/scoop/direct_download 四种后端，自动检测和自举安装。
"""

from .manager import SoftwareManager, software_manager
from .metadata import MetadataManager, metadata_manager
from .bootstrap import BootstrapInstaller, bootstrap
from .system_scanner import SystemScanner, system_scanner
from .qwebchannel_bridge import SoftwareManagerBridge, WebChannelSetup
from .backends import PackageManager, PackageInfo, InstallStatus

__all__ = [
    "SoftwareManager",
    "software_manager",
    "MetadataManager",
    "metadata_manager",
    "BootstrapInstaller",
    "bootstrap",
    "SystemScanner",
    "system_scanner",
    "SoftwareManagerBridge",
    "WebChannelSetup",
    "PackageManager",
    "PackageInfo",
    "InstallStatus",
]
