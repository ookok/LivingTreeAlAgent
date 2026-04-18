# core/security/firewall_manager.py
# 防火墙管理器 - Windows 防火墙规则自动化

import subprocess
import sys
from typing import List, Optional, Dict
from pathlib import Path

from .models import FirewallRule, PortConfig


class FirewallManager:
    """
    防火墙管理器

    负责：
    1. 添加/删除 Windows 防火墙规则
    2. 端口管理
    3. 规则查询与状态检查
    """

    _instance: Optional["FirewallManager"] = None

    def __init__(self):
        self._app_name = "Living Tree AI"
        self._rules_prefix = "LT"

    @classmethod
    def get_instance(cls) -> "FirewallManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _run_netsh(self, command: List[str]) -> tuple:
        """执行 netsh 命令"""
        try:
            result = subprocess.run(
                ["netsh"] + command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "命令执行超时"
        except Exception as e:
            return False, "", str(e)

    def _run_powershell(self, script: str) -> tuple:
        """执行 PowerShell 命令"""
        try:
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=60
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "PowerShell 执行超时"
        except Exception as e:
            return False, "", str(e)

    def is_admin(self) -> bool:
        """检查是否具有管理员权限"""
        try:
            # 尝试创建需要管理员权限的防火墙规则（测试）
            success, _, _ = self._run_netsh([
                "advfirewall", "firewall", "show", "rule", "name=all"
            ])
            return success
        except Exception:
            return False

    def get_all_rules(self) -> List[Dict]:
        """获取所有防火墙规则"""
        rules = []

        success, stdout, _ = self._run_powershell(
            'Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*Living Tree*" -or $_.DisplayName -like "*LT*"} | '
            'Select-Object Name, DisplayName, Direction, Action, Enabled, Profile | ConvertTo-Json -Compress'
        )

        if success and stdout.strip():
            try:
                import json
                data = json.loads(stdout)
                if isinstance(data, dict):
                    rules.append(data)
                elif isinstance(data, list):
                    rules.extend(data)
            except json.JSONDecodeError:
                pass

        return rules

    def add_rule(self, rule: FirewallRule) -> tuple:
        """
        添加防火墙规则

        返回: (success, message)
        """
        # 构建 PowerShell 命令
        ps_cmd = f'''
$rule = New-Object -ComObject HNetCfg.FWRule
$rule.Name = "{self._rules_prefix}_{rule.name}"
$rule.DisplayName = "{rule.name}"
$rule.Direction = {"1" if rule.direction == "Inbound" else "2"}
$rule.Action = {"0" if rule.action == "Allow" else "1"}
$rule.Protocol = {"6" if rule.protocol == "TCP" else "17"}
'''

        if rule.local_ports:
            ps_cmd += f'$rule.LocalPorts = "{rule.local_ports}"\n'
        if rule.remote_ports and rule.remote_ports != "*":
            ps_cmd += f'$rule.RemotePorts = "{rule.remote_ports}"\n'

        ps_cmd += f'$rule.Enabled = {"-1" if rule.enabled else "0"}\n'
        ps_cmd += f'$rule.Description = "{rule.description}"\n'

        # 简化方案：使用 netsh
        netsh_cmd = [
            "advfirewall", "firewall", "add", "rule",
            f'name="{self._rules_prefix}_{rule.name}"',
            f'dir={rule.direction}',
            f'action={rule.action}',
            f'protocol={rule.protocol}',
        ]

        if rule.local_ports:
            netsh_cmd.append(f'localport={rule.local_ports}')
        if rule.remote_ports and rule.remote_ports != "*":
            netsh_cmd.append(f'remoteport={rule.remote_ports}')

        netsh_cmd.append(f'program="{self._get_app_path()}"')
        netsh_cmd.append(f'description="{rule.description}"')

        success, stdout, stderr = self._run_netsh(netsh_cmd)

        if success:
            return True, f"规则 '{rule.name}' 添加成功"
        else:
            # 尝试 PowerShell 方式
            ps_cmd = f'''
New-NetFirewallRule -DisplayName "{rule.name}" `
    -Direction {rule.direction} -Action {rule.action} `
    -Protocol {rule.protocol} `
'''

            if rule.local_ports:
                ps_cmd += f'    -LocalPort {rule.local_ports} `\n'
            if rule.remote_ports and rule.remote_ports != "*":
                ps_cmd += f'    -RemotePort {rule.remote_ports} `\n'

            ps_cmd += f'    -Program "{self._get_app_path()}" `\n'
            ps_cmd += f'    -Description "{rule.description}" `\n'
            ps_cmd += f'    -Profile Any -Enabled True'

            success, stdout, stderr = self._run_powershell(ps_cmd)

            if success:
                return True, f"规则 '{rule.name}' 添加成功 (PowerShell)"
            else:
                return False, f"添加规则失败: {stderr or stdout}"

    def remove_rule(self, rule_name: str) -> tuple:
        """删除防火墙规则"""
        # 先尝试精确名称
        success, stdout, stderr = self._run_netsh([
            "advfirewall", "firewall", "delete", "rule",
            f'name="{self._rules_prefix}_{rule_name}"'
        ])

        if not success:
            # 尝试通配符删除
            success, stdout, stderr = self._run_powershell(
                f'Remove-NetFirewallRule -DisplayName "*{rule_name}*"'
            )

        if success:
            return True, f"规则 '{rule_name}' 删除成功"
        else:
            return False, f"删除规则失败: {stderr or stdout}"

    def add_app_rules(self) -> tuple:
        """添加应用所需的全部防火墙规则"""
        app_path = self._get_app_path()

        rules_to_add = [
            FirewallRule(
                name=f"{self._app_name} - P2P Discovery",
                direction="Inbound",
                action="Allow",
                protocol="UDP",
                local_ports="40000-60000",
                description="Living Tree AI P2P 节点发现端口"
            ),
            FirewallRule(
                name=f"{self._app_name} - Relay Server",
                direction="Inbound",
                action="Allow",
                protocol="TCP",
                local_ports="8766",
                description="Living Tree AI 中继服务器端口"
            ),
            FirewallRule(
                name=f"{self._app_name} - Web UI",
                direction="Inbound",
                action="Allow",
                protocol="TCP",
                local_ports="8765",
                description="Living Tree AI Web UI 端口"
            ),
            FirewallRule(
                name=f"{self._app_name} - LAN Chat",
                direction="Inbound",
                action="Allow",
                protocol="UDP",
                local_ports="5000-5100",
                description="Living Tree AI 局域网聊天端口"
            ),
        ]

        failed = []
        for rule in rules_to_add:
            success, msg = self.add_rule(rule)
            if not success:
                failed.append(msg)

        if failed:
            return False, f"部分规则添加失败: {'; '.join(failed)}"
        else:
            return True, f"成功添加 {len(rules_to_add)} 条防火墙规则"

    def check_rule_exists(self, rule_name: str) -> bool:
        """检查规则是否存在"""
        success, stdout, _ = self._run_netsh([
            "advfirewall", "firewall", "show", "rule",
            f'name="{self._rules_prefix}_{rule_name}"'
        ])
        return success and "Rule Name:" in stdout

    def enable_rule(self, rule_name: str) -> tuple:
        """启用规则"""
        success, stdout, stderr = self._run_netsh([
            "advfirewall", "firewall", "set", "rule",
            f'name="{self._rules_prefix}_{rule_name}"',
            "new",
            "enable=yes"
        ])

        if success:
            return True, f"规则 '{rule_name}' 已启用"
        else:
            return False, f"启用规则失败: {stderr}"

    def disable_rule(self, rule_name: str) -> tuple:
        """禁用规则"""
        success, stdout, stderr = self._run_netsh([
            "advfirewall", "firewall", "set", "rule",
            f'name="{self._rules_prefix}_{rule_name}"',
            "new",
            "enable=no"
        ])

        if success:
            return True, f"规则 '{rule_name}' 已禁用"
        else:
            return False, f"禁用规则失败: {stderr}"

    def get_firewall_status(self) -> Dict:
        """获取防火墙状态"""
        # 检查防火墙是否启用
        success, stdout, _ = self._run_netsh([
            "advfirewall", "show", "allprofiles", "state"
        ])

        profiles = {
            "Domain": False,
            "Private": False,
            "Public": False
        }

        if success:
            for line in stdout.split("\n"):
                line = line.strip()
                if "Domain Profile" in line:
                    current_profile = "Domain"
                elif "Private Profile" in line:
                    current_profile = "Private"
                elif "Public Profile" in line:
                    current_profile = "Public"
                elif "State" in line and "ON" in line:
                    profiles[current_profile] = True

        # 获取应用规则
        app_rules = self.get_all_rules()

        return {
            "firewall_enabled": any(profiles.values()),
            "profiles": profiles,
            "app_rules": app_rules,
            "is_admin": self.is_admin(),
        }

    def _get_app_path(self) -> str:
        """获取应用路径"""
        if getattr(sys, 'frozen', False):
            return sys.executable
        else:
            return str(Path(sys.argv[0]).parent / "main.py")

    def open_port(self, port: int, protocol: str = "TCP", name: Optional[str] = None) -> tuple:
        """开放单个端口"""
        if name is None:
            name = f"{self._app_name} - Port {port}"

        rule = FirewallRule(
            name=name,
            direction="Inbound",
            action="Allow",
            protocol=protocol,
            local_ports=str(port),
            description=f"开放端口 {port}/{protocol}"
        )

        return self.add_rule(rule)

    def close_port(self, port: int, protocol: str = "TCP") -> tuple:
        """关闭端口（删除规则）"""
        name = f"{self._app_name} - Port {port}"
        return self.remove_rule(name)


# 全局获取函数
def get_firewall_manager() -> FirewallManager:
    """获取防火墙管理器单例"""
    return FirewallManager.get_instance()