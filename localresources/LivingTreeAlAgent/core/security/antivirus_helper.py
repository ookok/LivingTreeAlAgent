# core/security/antivirus_helper.py
# 杀毒软件检测与信任引导

import subprocess
import sys
from typing import List, Optional, Dict

from .models import (
    AntivirusProduct,
    AntivirusStatus,
    TrustGuide,
)


class AntivirusHelper:
    """
    杀毒软件检测与信任引导

    负责：
    1. 检测系统安装的杀毒软件
    2. 评估杀软状态
    3. 生成信任引导步骤
    4. 提供一键信任功能
    """

    _instance: Optional["AntivirusHelper"] = None

    # 已知杀毒软件特征
    KNOWN_AV = {
        "windows defender": {
            "vendor": "Microsoft",
            "trust_steps": [
                "打开 Windows 安全中心",
                "选择 '病毒和威胁防护'",
                "点击 '管理设置'",
                "将 Living Tree AI 添加到排除项",
            ],
            "trust_url": "ms-settings:windowsdefender"
        },
        "360": {
            "vendor": "360",
            "trust_steps": [
                "打开 360 安全卫士",
                "点击 '病毒防护'",
                "进入 '信任管理' 或 '白名单'",
                "添加 Living Tree AI 目录到信任列表",
            ],
            "trust_url": None
        },
        "qq电脑管家": {
            "vendor": "Tencent",
            "trust_steps": [
                "打开腾讯电脑管家",
                "点击 '病毒查杀'",
                "选择 '信任区' 或 '白名单'",
                "添加 Living Tree AI 目录到信任列表",
            ],
            "trust_url": None
        },
        "kingsoft": {
            "vendor": "Kingsoft",
            "trust_steps": [
                "打开金山毒霸",
                "点击 '病毒查杀'",
                "进入 '信任设置'",
                "添加 Living Tree AI 目录",
            ],
            "trust_url": None
        },
        "kaspersky": {
            "vendor": "Kaspersky",
            "trust_steps": [
                "打开卡巴斯基安全软件",
                "点击 '设置'",
                "选择 '附加' -> '威胁和排除'",
                "点击 '管理排除' 或 '信任程序'",
                "添加 Living Tree AI",
            ],
            "trust_url": None
        },
        "norton": {
            "vendor": "Norton",
            "trust_steps": [
                "打开 Norton Security",
                "点击 '设置' 或 '高级'",
                "选择 '防病毒' 或 '智能防火墙'",
                "点击 '排除/低风险' -> '添加项目'",
                "添加 Living Tree AI",
            ],
            "trust_url": None
        },
        "mcafee": {
            "vendor": "McAfee",
            "trust_steps": [
                "打开 McAfee",
                "点击 '导航' -> '设置'",
                "选择 '实时扫描' -> '排除项'",
                "添加 Living Tree AI 目录",
            ],
            "trust_url": None
        },
        "avast": {
            "vendor": "Avast",
            "trust_steps": [
                "打开 Avast",
                "点击 '保护' -> '防火墙'",
                "进入 '应用程序规则'",
                "找到 Living Tree AI 或添加新程序",
                "设置为 '允许'",
            ],
            "trust_url": None
        },
        "avg": {
            "vendor": "AVG",
            "trust_steps": [
                "打开 AVG",
                "点击 '保护' -> '防火墙'",
                "进入 '应用程序'",
                "添加 Living Tree AI 并设置允许",
            ],
            "trust_url": None
        },
        "bitdefender": {
            "vendor": "Bitdefender",
            "trust_steps": [
                "打开 Bitdefender",
                "点击 '防护' -> '高级'",
                "进入 '排除' 设置",
                "添加 Living Tree AI 到排除列表",
            ],
            "trust_url": None
        },
        "eset": {
            "vendor": "ESET",
            "trust_steps": [
                "打开 ESET",
                "点击 '设置' -> '进入高级设置'",
                "选择 '计算机' -> '排除'",
                "添加 Living Tree AI 目录",
            ],
            "trust_url": None
        },
        "小红伞": {
            "vendor": "Avira",
            "trust_steps": [
                "打开 Avira",
                "点击 '安全' -> '防火墙'",
                "进入 '应用程序规则'",
                "添加 Living Tree AI",
            ],
            "trust_url": None
        },
        "火绒": {
            "vendor": "Huorong",
            "trust_steps": [
                "打开火绒安全",
                "点击 '安全工具' -> '信任管理'",
                "进入 '程序执行控制'",
                "添加 Living Tree AI 到信任列表",
            ],
            "trust_url": None
        },
    }

    @classmethod
    def get_instance(cls) -> "AntivirusHelper":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _run_wmic(self, query: str) -> str:
        """执行 WMIC 查询"""
        try:
            result = subprocess.run(
                ["wmic", "/namespace:\\\\root\\SecurityCenter2", "path", query],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=15
            )
            return result.stdout
        except Exception:
            return ""

    def _run_powershell(self, script: str) -> str:
        """执行 PowerShell"""
        try:
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30
            )
            return result.stdout
        except Exception:
            return ""

    def detect_antivirus(self) -> List[AntivirusProduct]:
        """检测系统杀毒软件"""
        products = []

        # 方法1: WMIC
        av_raw = self._run_wmic("AntiVirusProduct get * /format:csv")
        for line in av_raw.split("\n"):
            line = line.strip()
            if line and "," in line and "Node" not in line:
                parts = line.split(",")
                if len(parts) >= 4:
                    name = parts[-1].strip()
                    if name:
                        products.append(AntivirusProduct(
                            name=name,
                            vendor=self._identify_vendor(name),
                            status=AntivirusStatus.PROTECTED
                        ))

        # 方法2: PowerShell Get-MpComputerStatus (Windows Defender)
        defender_found = False
        for p in products:
            if "defender" in p.name.lower():
                defender_found = True
                break

        if not defender_found:
            ps_output = self._run_powershell(
                "Get-MpComputerStatus | Select-Object -Property AntivirusEnabled, RealTimeProtectionEnabled | ConvertTo-Json"
            )
            if ps_output.strip():
                import json
                try:
                    data = json.loads(ps_output)
                    if data.get("AntivirusEnabled"):
                        products.append(AntivirusProduct(
                            name="Windows Defender",
                            vendor="Microsoft",
                            status=AntivirusStatus.PROTECTED,
                            real_time_protection=data.get("RealTimeProtectionEnabled", False)
                        ))
                except json.JSONDecodeError:
                    pass

        # 去重
        seen = set()
        unique = []
        for p in products:
            if p.name not in seen:
                seen.add(p.name)
                unique.append(p)

        return unique

    def _identify_vendor(self, av_name: str) -> str:
        """识别杀软厂商"""
        name_lower = av_name.lower()

        for key, info in self.KNOWN_AV.items():
            if key in name_lower:
                return info["vendor"]

        return "Unknown"

    def get_antivirus_status(self) -> tuple:
        """获取杀软状态"""
        products = self.detect_antivirus()

        if not products:
            return AntivirusStatus.NOT_INSTALLED, []

        # 检查是否有实时保护
        has_realtime = any(p.real_time_protection for p in products)

        # 检查是否过期（这里简化处理）
        outdated = False

        if not has_realtime:
            return AntivirusStatus.DISABLED, products
        elif outdated:
            return AntivirusStatus.OUTDATED, products
        else:
            return AntivirusStatus.PROTECTED, products

    def get_trust_guide(self, av_name: str) -> Optional[TrustGuide]:
        """获取信任引导"""
        name_lower = av_name.lower()

        for key, info in self.KNOWN_AV.items():
            if key in name_lower:
                return TrustGuide(
                    antivirus_name=info["vendor"],
                    steps=info["trust_steps"],
                    url=info.get("trust_url")
                )

        # 通用引导
        return TrustGuide(
            antivirus_name="通用",
            steps=[
                "打开您的杀毒软件",
                "查找 '信任'、'排除' 或 '白名单' 设置",
                "将 Living Tree AI 目录添加到信任列表",
                "确保文件和网络访问被允许",
            ],
            url=None
        )

    def get_all_trust_guides(self) -> List[TrustGuide]:
        """获取所有已知杀软的信任引导"""
        guides = []

        for key, info in self.KNOWN_AV.items():
            guides.append(TrustGuide(
                antivirus_name=info["vendor"],
                steps=info["trust_steps"],
                url=info.get("trust_url")
            ))

        return guides

    def open_trust_settings(self, av_name: str) -> bool:
        """打开信任设置页面"""
        guide = self.get_trust_guide(av_name)

        if guide and guide.url:
            try:
                import webbrowser
                webbrowser.open(guide.url)
                return True
            except Exception:
                pass

        return False

    def check_if_trusted(self, app_path: str) -> bool:
        """
        检查应用是否被信任
        注意: 这是一个启发式检查，可能不准确
        """
        # 检查 Windows Defender 排除
        ps_script = f'''
        Get-MpPreference | Where-Object {{$_.ExclusionPath -contains "{app_path}"}} | Measure-Object | Select-Object -ExpandProperty Count
        '''

        result = self._run_powershell(ps_script)
        try:
            count = int(result.strip())
            if count > 0:
                return True
        except ValueError:
            pass

        return False

    def add_to_defender_exclusions(self, path: str) -> tuple:
        """添加到 Windows Defender 排除项"""
        ps_script = f'''
        Add-MpPreference -ExclusionPath "{path}" -ErrorAction SilentlyContinue
        '''

        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=30
        )

        if result.returncode == 0:
            return True, "已添加到 Windows Defender 排除项"
        else:
            return False, f"添加失败: {result.stderr or '权限不足'}"

    def generate_diagnostic_report(self) -> Dict:
        """生成诊断报告"""
        status, products = self.get_antivirus_status()

        report = {
            "detection_time": self._get_current_time(),
            "status": status.value,
            "products": [p.to_dict() for p in products],
            "trust_guides": [],
        }

        # 添加信任引导
        for product in products:
            guide = self.get_trust_guide(product.name)
            if guide:
                report["trust_guides"].append(guide.to_dict())

        return report

    def _get_current_time(self) -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 全局获取函数
def get_antivirus_helper() -> AntivirusHelper:
    """获取杀毒软件助手单例"""
    return AntivirusHelper.get_instance()