# core/security/security_manager.py
# 安全管理器 - 核心状态检查与信任引导

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

# 尝试导入 psutil 进行进程检测
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from .models import (
    SecurityConfig,
    SecurityStatus,
    SecurityLevel,
    FirewallStatus,
    AntivirusStatus,
)


class SecurityManager:
    """
    安全管理器

    负责：
    1. 安全状态检查（防火墙、杀软、进程行为）
    2. 首次运行引导
    3. 信任级别评估
    4. 修复建议生成
    """

    _instance: Optional["SecurityManager"] = None

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or self._load_or_create_config()
        self._status: Optional[SecurityStatus] = None
        self._last_check: Optional[datetime] = None

        # 初始化子管理器
        self._firewall_mgr = None
        self._antivirus_helper = None
        self._behavior_monitor = None

    @classmethod
    def get_instance(cls) -> "SecurityManager":
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_config_path(self) -> Path:
        """获取配置文件路径"""
        if getattr(sys, 'frozen', False):
            # 打包后的应用
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).parent.parent.parent
        return app_dir / "config" / "security_config.json"

    def _load_or_create_config(self) -> SecurityConfig:
        """加载或创建配置"""
        config_path = self._get_config_path()

        # 默认配置
        app_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]

        # 获取 AppData 目录
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        app_data_dir = Path(appdata) / "LivingTreeAI"

        config = SecurityConfig(
            app_name="Living Tree AI",
            app_path=app_path,
            app_data_dir=str(app_data_dir),
        )

        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                config = SecurityConfig.from_dict(data)
            except Exception:
                pass

        return config

    def save_config(self):
        """保存配置"""
        config_path = self._get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(self.config.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get_status(self, force_refresh: bool = False) -> SecurityStatus:
        """获取安全状态"""
        if self._status is None or force_refresh:
            self._status = self._check_security_status()
            self._last_check = datetime.now()
        return self._status

    def _check_security_status(self) -> SecurityStatus:
        """执行安全状态检查"""
        status = SecurityStatus()
        status.last_check = datetime.now()

        issues = []
        recommendations = []

        # 1. 检查防火墙规则
        firewall_status = self._check_firewall_rules()
        status.firewall_status = firewall_status

        if firewall_status == FirewallStatus.DISABLED:
            issues.append("Windows 防火墙未启用")
            recommendations.append("建议启用 Windows 防火墙保护")
        elif firewall_status == FirewallStatus.PARTIAL:
            issues.append("部分防火墙规则未添加")
            recommendations.append("运行安全设置向导添加必要的防火墙规则")

        # 2. 检查杀毒软件
        av_status, detected_av = self._check_antivirus()
        status.antivirus_status = av_status
        status.detected_antivirus = detected_av

        if av_status == AntivirusStatus.NOT_INSTALLED:
            issues.append("未检测到杀毒软件")
            recommendations.append("建议安装杀毒软件保护系统安全")
        elif av_status == AntivirusStatus.OUTDATED:
            issues.append("杀毒软件可能已过期")
            recommendations.append("请更新杀毒软件病毒库")
        elif av_status == AntivirusStatus.DISABLED:
            issues.append("杀毒软件实时保护已禁用")
            recommendations.append("建议启用杀毒软件实时保护")

        # 3. 检查应用防火墙规则
        app_blocked = self._check_app_firewall_rules()
        status.blocked_ports = app_blocked

        if app_blocked:
            issues.append(f"应用端口可能被防火墙阻止: {app_blocked}")
            recommendations.append("请在防火墙中添加应用例外规则")

        # 4. 评估信任级别
        status.level = self._evaluate_trust_level(status)

        status.issues = issues
        status.recommendations = recommendations

        return status

    def _check_firewall_rules(self) -> FirewallStatus:
        """检查防火墙规则"""
        try:
            import subprocess

            # 检查 Windows 防火墙状态
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            if "State                                 ON" in result.stdout:
                # 检查应用规则
                app_rules = self._get_app_firewall_rules()
                if app_rules:
                    return FirewallStatus.ENABLED
                else:
                    return FirewallStatus.PARTIAL
            else:
                return FirewallStatus.DISABLED

        except Exception:
            return FirewallStatus.UNKNOWN

    def _get_app_firewall_rules(self) -> List[str]:
        """获取应用防火墙规则"""
        try:
            import subprocess

            result = subprocess.run(
                [
                    "netsh", "advfirewall", "firewall", "show", "rule",
                    f"name=all"
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            rules = []
            app_name = self.config.app_name.lower()

            for line in result.stdout.split("\n"):
                if "Rule Name:" in line and app_name in line.lower():
                    rules.append(line.split(":", 1)[1].strip())

            return rules

        except Exception:
            return []

    def _check_app_firewall_rules(self) -> List[int]:
        """检查应用端口是否被阻止"""
        blocked = []

        ports_to_check = [
            self.config.relay_port,
            self.config.web_ui_port,
        ]

        # 添加 P2P 端口范围中的随机端口测试
        import random
        p2p_port = random.randint(self.config.p2p_port_range[0], self.config.p2p_port_range[1])
        ports_to_check.append(p2p_port)

        for port in ports_to_check:
            if not self._is_port_listening(port):
                blocked.append(port)

        return blocked

    def _is_port_listening(self, port: int) -> bool:
        """检查端口是否在监听"""
        if not HAS_PSUTIL:
            return True  # 无法检测，假设正常

        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == "LISTEN":
                    return True
        except Exception:
            pass

        return False

    def _check_antivirus(self) -> tuple:
        """检查杀毒软件"""
        detected = []

        try:
            import subprocess

            # 使用 WMIC 检查杀毒软件
            result = subprocess.run(
                [
                    "wmic", "/namespace:\\\\root\\SecurityCenter2",
                    "path", "AntiVirusProduct", "get", "displayName", "/format:csv"
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=10
            )

            for line in result.stdout.split("\n"):
                line = line.strip()
                if line and "AntiVirusProduct" not in line and "," in line:
                    name = line.split(",")[-1].strip()
                    if name:
                        detected.append(name)

        except Exception:
            pass

        if not detected:
            return AntivirusStatus.NOT_INSTALLED, []

        # 检查是否是已知的安全软件
        known_av = {
            "windows defender": "Windows Defender",
            "windows security": "Windows Security",
            "360": "360安全卫士",
            "qq电脑管家": "腾讯电脑管家",
            "kingsoft": "金山毒霸",
            "rising": "瑞星",
            "jiangmin": "江民",
            "avast": "Avast",
            "avg": "AVG",
            "kaspersky": "卡巴斯基",
            "norton": "Norton",
            "mcafee": "McAfee",
            "eset": "ESET",
            "bitdefender": "Bitdefender",
        }

        status = AntivirusStatus.PROTECTED
        for av_name in detected:
            av_lower = av_name.lower()
            for key, display in known_av.items():
                if key in av_lower:
                    if "defender" in av_lower or "security" in av_lower:
                        status = AntivirusStatus.PROTECTED
                    break

        return status, detected

    def _evaluate_trust_level(self, status: SecurityStatus) -> SecurityLevel:
        """评估信任级别"""
        score = 0

        # 防火墙评分
        if status.firewall_status == FirewallStatus.ENABLED:
            score += 30
        elif status.firewall_status == FirewallStatus.PARTIAL:
            score += 15

        # 杀毒软件评分
        if status.antivirus_status == AntivirusStatus.PROTECTED:
            score += 40
        elif status.antivirus_status == AntivirusStatus.OUTDATED:
            score += 20
        elif status.antivirus_status == AntivirusStatus.DISABLED:
            score += 10

        # 检查应用规则
        if not status.blocked_ports:
            score += 30

        # 评估级别
        if score >= 80:
            return SecurityLevel.TRUSTED
        elif score >= 40:
            return SecurityLevel.PARTIAL
        else:
            return SecurityLevel.BLOCKED

    def complete_first_run_setup(self):
        """完成首次运行设置"""
        self.config.first_run_completed = True
        self.save_config()

    def mark_firewall_added(self):
        """标记防火墙规则已添加"""
        self.config.firewall_rule_added = True
        self.save_config()

    def mark_antivirus_trusted(self):
        """标记杀毒软件已信任"""
        self.config.antivirus_trusted = True
        self.save_config()

    def get_security_report(self) -> Dict:
        """获取安全报告"""
        status = self.get_status()

        report = {
            "app_name": self.config.app_name,
            "app_path": self.config.app_path,
            "check_time": status.last_check.isoformat(),
            "security_level": status.level.value,
            "is_healthy": status.is_healthy,
            "needs_attention": status.needs_attention,
            "firewall": {
                "status": status.firewall_status.value,
                "app_rules_count": len(self._get_app_firewall_rules()),
            },
            "antivirus": {
                "status": status.antivirus_status.value,
                "detected": status.detected_antivirus,
            },
            "blocked_ports": status.blocked_ports,
            "issues": status.issues,
            "recommendations": status.recommendations,
            "config": {
                "first_run_completed": self.config.first_run_completed,
                "firewall_rule_added": self.config.firewall_rule_added,
                "antivirus_trusted": self.config.antivirus_trusted,
            },
        }

        return report

    def reset_security_status(self):
        """重置安全状态（重新检查）"""
        self._status = None
        self._last_check = None


# 全局获取函数
def get_security_manager() -> SecurityManager:
    """获取安全管理器单例"""
    return SecurityManager.get_instance()