# core/security/models.py
# 安全模块数据模型

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime


class SecurityLevel(Enum):
    """安全级别"""
    UNKNOWN = "unknown"
    TRUSTED = "trusted"      # 受信任
    PARTIAL = "partial"      # 部分信任（需要引导）
    BLOCKED = "blocked"       # 被阻止


class RiskLevel(Enum):
    """风险等级"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FirewallStatus(Enum):
    """防火墙状态"""
    UNKNOWN = "unknown"
    ENABLED = "enabled"
    DISABLED = "disabled"
    PARTIAL = "partial"  # 部分规则已添加


class AntivirusStatus(Enum):
    """杀毒软件状态"""
    UNKNOWN = "unknown"
    PROTECTED = "protected"
    OUTDATED = "outdated"
    DISABLED = "disabled"
    NOT_INSTALLED = "not_installed"


@dataclass
class SecurityConfig:
    """安全配置"""
    app_name: str = "Living Tree AI"
    app_path: str = ""
    app_data_dir: str = ""

    # 网络配置
    p2p_port_range: tuple = (40000, 60000)  # P2P 端口范围
    relay_port: int = 8766                   # 中继服务端口
    web_ui_port: int = 8765                 # Web UI 端口

    # 行为限制
    restrict_to_appdata: bool = True        # 限制操作到 AppData
    allow_network: bool = True              # 允许网络通信
    allow_file_modify: bool = True           # 允许文件修改

    # 首次运行引导
    first_run_completed: bool = False
    firewall_rule_added: bool = False
    antivirus_trusted: bool = False

    def to_dict(self) -> Dict:
        return {
            "app_name": self.app_name,
            "app_path": self.app_path,
            "app_data_dir": self.app_data_dir,
            "p2p_port_range": list(self.p2p_port_range),
            "relay_port": self.relay_port,
            "web_ui_port": self.web_ui_port,
            "restrict_to_appdata": self.restrict_to_appdata,
            "allow_network": self.allow_network,
            "allow_file_modify": self.allow_file_modify,
            "first_run_completed": self.first_run_completed,
            "firewall_rule_added": self.firewall_rule_added,
            "antivirus_trusted": self.antivirus_trusted,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SecurityConfig":
        config = cls()
        config.app_name = data.get("app_name", config.app_name)
        config.app_path = data.get("app_path", config.app_path)
        config.app_data_dir = data.get("app_data_dir", config.app_data_dir)

        port_range = data.get("p2p_port_range", list(config.p2p_port_range))
        config.p2p_port_range = tuple(port_range) if isinstance(port_range, list) else port_range

        config.relay_port = data.get("relay_port", config.relay_port)
        config.web_ui_port = data.get("web_ui_port", config.web_ui_port)
        config.restrict_to_appdata = data.get("restrict_to_appdata", config.restrict_to_appdata)
        config.allow_network = data.get("allow_network", config.allow_network)
        config.allow_file_modify = data.get("allow_file_modify", config.allow_file_modify)
        config.first_run_completed = data.get("first_run_completed", config.first_run_completed)
        config.firewall_rule_added = data.get("firewall_rule_added", config.firewall_rule_added)
        config.antivirus_trusted = data.get("antivirus_trusted", config.antivirus_trusted)
        return config


@dataclass
class SecurityStatus:
    """安全状态"""
    level: SecurityLevel = SecurityLevel.UNKNOWN
    firewall_status: FirewallStatus = FirewallStatus.UNKNOWN
    antivirus_status: AntivirusStatus = AntivirusStatus.UNKNOWN
    detected_antivirus: List[str] = field(default_factory=list)
    blocked_ports: List[int] = field(default_factory=list)
    risk_events: List["BehaviorEvent"] = field(default_factory=list)
    last_check: datetime = field(default_factory=datetime.now)

    issues: List[str] = field(default_factory=list)  # 问题列表
    recommendations: List[str] = field(default_factory=list)  # 建议列表

    @property
    def is_healthy(self) -> bool:
        return (
            self.level == SecurityLevel.TRUSTED
            and len(self.issues) == 0
        )

    @property
    def needs_attention(self) -> bool:
        return (
            self.level in (SecurityLevel.PARTIAL, SecurityLevel.UNKNOWN)
            or len(self.issues) > 0
        )


@dataclass
class FirewallRule:
    """防火墙规则"""
    name: str
    direction: str = "Inbound"  # Inbound/Outbound
    action: str = "Allow"
    protocol: str = "TCP"       # TCP/UDP
    local_ports: str = ""        # 端口或端口范围
    remote_ports: str = "*"
    profiles: str = "Domain,Private,Public"  # 网络类型
    enabled: bool = True
    description: str = ""

    def to_powershell(self) -> str:
        """生成 PowerShell 命令"""
        cmd = f'New-NetFirewallRule -DisplayName "{self.name}" '
        cmd += f'-Direction {self.direction} -Action {self.action} '
        cmd += f'-Protocol {self.protocol} '
        if self.local_ports:
            cmd += f'-LocalPort {self.local_ports} '
        cmd += f'-RemotePort {self.remote_ports} '
        cmd += f'-Profile {self.profiles} '
        if self.description:
            cmd += f'-Description "{self.description}" '
        cmd += "-Enabled True"
        return cmd


@dataclass
class PortConfig:
    """端口配置"""
    port: int
    protocol: str = "TCP"
    service: str = ""
    description: str = ""
    required: bool = True


@dataclass
class BehaviorEvent:
    """行为事件"""
    timestamp: datetime
    event_type: str
    description: str
    risk_level: RiskLevel
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "details": self.details,
        }


@dataclass
class AntivirusProduct:
    """杀毒软件产品"""
    name: str
    vendor: str
    status: AntivirusStatus
    version: Optional[str] = None
    last_update: Optional[str] = None
    real_time_protection: bool = False

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "status": self.status.value,
            "version": self.version,
            "last_update": self.last_update,
            "real_time_protection": self.real_time_protection,
        }


@dataclass
class TrustGuide:
    """信任引导指南"""
    antivirus_name: str
    steps: List[str]
    url: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "antivirus_name": self.antivirus_name,
            "steps": self.steps,
            "url": self.url,
        }