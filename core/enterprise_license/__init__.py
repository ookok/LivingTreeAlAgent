"""
Enterprise License Client - 企业许可证客户端
==========================================

客户端使用的企业许可证模块，负责：
1. 生成8位码（基于企业名称）
2. 与服务端通信进行序列号验证
3. 企业模式登录验证

流程：
1. 用户输入企业名称 → 客户端生成8位码
2. 用户将8位码和企称名称提供给管理员
3. 管理员在服务端生成序列号
4. 用户输入序列号和8位码进行注册
5. 每次企业模式登录都验证序列号

Author: Hermes Desktop Team
"""

from core.logger import get_logger
logger = get_logger('enterprise_license.__init__')

import os
import re
import json
import hashlib
import uuid
import platform
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ============ 数据模型 ============

@dataclass
class LicenseInfo:
    """许可证信息"""
    enterprise_name: str = ""
    enterprise_code: str = ""  # 8位码
    serial_number: str = ""
    license_key: str = ""
    license_type: str = "standard"
    status: str = "active"
    registered: bool = False
    expires_at: str = ""
    
    # 设备信息
    device_id: str = ""
    device_fingerprint: str = ""


# ============ 许可证客户端 ============

class EnterpriseLicenseClient:
    """企业许可证客户端"""
    
    # 配置文件路径
    CONFIG_DIR = Path("~/.hermes").expanduser()
    LICENSE_FILE = CONFIG_DIR / "enterprise_license.json"
    
    def __init__(self, relay_server_url: str = "http://localhost:8080"):
        self.relay_server_url = relay_server_url.rstrip("/")
        self._license_info: Optional[LicenseInfo] = None
        self._device_id: Optional[str] = None
        self._device_fingerprint: Optional[str] = None
        
        # 确保配置目录存在
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # 加载已保存的许可证信息
        self._load_license_info()
    
    # ============ 设备指纹 ============
    
    def get_device_id(self) -> str:
        """获取设备ID"""
        if self._device_id:
            return self._device_id
        
        # 尝试从配置文件加载
        config_file = self.CONFIG_DIR / "device_id.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._device_id = data.get("device_id", "")
        
        if not self._device_id:
            # 生成新的设备ID
            self._device_id = str(uuid.uuid4())
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump({"device_id": self._device_id}, f)
        
        return self._device_id
    
    def get_device_fingerlogger.info(self) -> str:
        """获取设备指纹"""
        if self._device_fingerprint:
            return self._device_fingerprint
        
        # 生成设备指纹（基于硬件信息）
        parts = [
            platform.system(),
            platform.node(),
            platform.machine(),
            platform.processor(),
            str(uuid.getnode())  # MAC地址
        ]
        
        fingerprint = hashlib.sha256("|".join(parts).encode()).hexdigest()
        self._device_fingerprint = fingerprint
        
        return self._device_fingerprint
    
    # ============ 8位码生成 ============
    
    @staticmethod
    def generate_enterprise_code(enterprise_name: str) -> str:
        """
        客户端：基于企业名称生成8位码
        
        算法：
        1. 规范化企业名称（去除空格、转小写）
        2. SHA256 哈希
        3. 取前8位并添加校验位
        """
        if not enterprise_name or len(enterprise_name.strip()) < 2:
            raise ValueError("企业名称至少需要2个字符")
        
        # 规范化
        normalized = enterprise_name.strip().lower()
        
        # SHA256 哈希
        hash_value = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        
        # 取前8位
        code_base = hash_value[:7].upper()
        
        # 计算校验位
        checksum = sum(ord(c) for c in normalized) % 26 + 65
        checksum_char = chr(checksum)
        
        # 组成8位码
        code = code_base + checksum_char
        
        return code
    
    @staticmethod
    def verify_enterprise_code(enterprise_name: str, code: str) -> bool:
        """验证8位码"""
        if not code or len(code) != 8:
            return False
        
        expected = EnterpriseLicenseClient.generate_enterprise_code(enterprise_name)
        return expected.upper() == code.upper()
    
    # ============ 许可证信息管理 ============
    
    def save_license_info(self, license_info: LicenseInfo):
        """保存许可证信息"""
        self._license_info = license_info
        
        with open(self.LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(license_info), f, ensure_ascii=False, indent=2)
    
    def _load_license_info(self):
        """加载许可证信息"""
        if self.LICENSE_FILE.exists():
            try:
                with open(self.LICENSE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._license_info = LicenseInfo(**data)
            except Exception:
                self._license_info = None
    
    def get_license_info(self) -> Optional[LicenseInfo]:
        """获取许可证信息"""
        return self._license_info
    
    def clear_license_info(self):
        """清除许可证信息"""
        self._license_info = None
        if self.LICENSE_FILE.exists():
            self.LICENSE_FILE.unlink()
    
    def is_registered(self) -> bool:
        """检查是否已注册"""
        return self._license_info is not None and self._license_info.registered
    
    # ============ API 通信 ============
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """发送API请求"""
        import aiohttp
        
        url = f"{self.relay_server_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(url, headers=headers) as resp:
                    return await resp.json()
            else:
                async with session.post(url, json=data, headers=headers) as resp:
                    return await resp.json()
    
    # ============ 注册流程 ============
    
    async def request_code(self, enterprise_name: str) -> Tuple[bool, str, str]:
        """
        步骤1：向服务端请求生成8位码
        
        Returns:
            (success, enterprise_code, code_id)
        """
        try:
            response = await self._request(
                "POST",
                "/api/v1/enterprise/code/generate",
                {"enterprise_name": enterprise_name}
            )
            
            if response.get("success"):
                return True, response["enterprise_code"], response["code_id"]
            else:
                return False, response.get("message", "请求失败"), ""
        
        except Exception as e:
            return False, f"网络错误: {str(e)}", ""
    
    async def register(
        self,
        enterprise_name: str,
        enterprise_code: str,
        serial_number: str,
        license_key: str = ""
    ) -> Tuple[bool, str]:
        """
        步骤2：注册许可证（激活）
        
        用户拿到序列号后调用此接口完成注册。
        """
        try:
            response = await self._request(
                "POST",
                "/api/v1/enterprise/register",
                {
                    "enterprise_name": enterprise_name,
                    "enterprise_code": enterprise_code,
                    "serial_number": serial_number,
                    "device_fingerprint": self.get_device_fingerprint(),
                    "license_key": license_key
                }
            )
            
            if response.get("success"):
                # 保存许可证信息
                license_info = LicenseInfo(
                    enterprise_name=enterprise_name,
                    enterprise_code=enterprise_code.upper(),
                    serial_number=serial_number,
                    license_key=license_key,
                    registered=True,
                    device_id=self.get_device_id(),
                    device_fingerprint=self.get_device_fingerprint()
                )
                self.save_license_info(license_info)
                return True, "注册成功"
            else:
                return False, response.get("message", "注册失败")
        
        except Exception as e:
            return False, f"网络错误: {str(e)}"
    
    async def verify_on_login(self) -> Tuple[bool, str]:
        """
        步骤3：登录时验证许可证
        
        企业模式每次登录都需要调用此方法。
        """
        if not self._license_info:
            return False, "未注册许可证"
        
        try:
            response = await self._request(
                "POST",
                "/api/v1/enterprise/verify",
                {
                    "enterprise_name": self._license_info.enterprise_name,
                    "enterprise_code": self._license_info.enterprise_code,
                    "serial_number": self._license_info.serial_number,
                    "device_fingerprint": self.get_device_fingerprint()
                }
            )
            
            if response.get("success"):
                return True, "验证成功"
            else:
                return False, response.get("message", "验证失败")
        
        except Exception as e:
            return False, f"网络错误: {str(e)}"
    
    async def get_license_info_from_server(self) -> Tuple[bool, Dict[str, Any]]:
        """从服务器获取许可证信息"""
        if not self._license_info:
            return False, {}
        
        try:
            response = await self._request(
                "GET",
                f"/api/v1/enterprise/info/{self._license_info.serial_number}"
            )
            
            if response.get("success"):
                return True, response.get("info", {})
            else:
                return False, {}
        
        except Exception:
            return False, {}
    
    # ============ 离线验证 ============
    
    def validate_locally(self) -> Tuple[bool, str]:
        """
        本地验证（离线时使用）
        
        仅验证本地保存的信息完整性，不连接服务器。
        """
        if not self._license_info:
            return False, "未注册许可证"
        
        # 验证8位码格式
        if not re.match(r"^[A-Z0-9]{8}$", self._license_info.enterprise_code):
            return False, "企业码格式错误"
        
        # 验证序列号格式
        if not re.match(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$",
                        self._license_info.serial_number):
            return False, "序列号格式错误"
        
        # 验证企业码和名称匹配
        expected_code = self.generate_enterprise_code(self._license_info.enterprise_name)
        if expected_code != self._license_info.enterprise_code:
            return False, "企业码与名称不匹配"
        
        return True, "本地验证通过"


# ============ CLI 工具 ============

def main():
    """命令行工具"""
    import argparse

    
    parser = argparse.ArgumentParser(description="企业许可证工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 生成8位码
    code_parser = subparsers.add_parser("generate-code", help="生成8位码")
    code_parser.add_argument("enterprise_name", help="企业名称")
    
    # 验证8位码
    verify_parser = subparsers.add_parser("verify-code", help="验证8位码")
    verify_parser.add_argument("enterprise_name", help="企业名称")
    verify_parser.add_argument("code", help="8位码")
    
    # 注册
    register_parser = subparsers.add_parser("register", help="注册许可证")
    register_parser.add_argument("enterprise_name", help="企业名称")
    register_parser.add_argument("enterprise_code", help="8位码")
    register_parser.add_argument("serial_number", help="序列号")
    
    args = parser.parse_args()
    
    if args.command == "generate-code":
        code = EnterpriseLicenseClient.generate_enterprise_code(args.enterprise_name)
        logger.info(f"企业名称: {args.enterprise_name}")
        logger.info(f"8位码: {code}")
    
    elif args.command == "verify-code":
        valid = EnterpriseLicenseClient.verify_enterprise_code(args.enterprise_name, args.code)
        logger.info(f"验证结果: {'通过' if valid else '失败'}")
    
    elif args.command == "register":
        logger.info("注册功能需要通过桌面客户端操作")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()