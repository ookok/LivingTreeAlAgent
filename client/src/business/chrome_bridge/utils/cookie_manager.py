"""
Cookie Manager - Cookie 管理器
==============================

管理浏览器 Cookie 的导入/导出，
实现 Chrome 会话的完美复用（登录状态迁移）。

支持格式：
- Chrome Cookie 格式（JSON，从 Chrome DevTools Protocol 获取）
- Netscape Cookie 格式（curl/wget 兼容）
- JSON 通用格式
"""

import json
import os
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime


class CookieManager:
    """
    Cookie 管理器

    实现 Cookie 的跨浏览器/跨会话迁移，
    核心能力：从 Chrome 导出 Cookie，注入到目标页面。
    """

    def __init__(self, chrome_profile_dir: Optional[str] = None):
        """
        初始化 Cookie 管理器

        Args:
            chrome_profile_dir: Chrome Profile 目录路径
                            （如：C:/Users/用户名/AppData/Local/Google/Chrome/User Data/Default）
        """
        self.chrome_profile_dir = chrome_profile_dir or self._detect_chrome_profile_dir()
        self._logger = None  # 延迟导入 loguru

    def _detect_chrome_profile_dir(self) -> Optional[str]:
        """自动检测 Chrome Profile 目录"""
        if os.name == "nt":  # Windows
            base = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
            default_profile = os.path.join(base, "Default")
            if os.path.exists(default_profile):
                return default_profile
        elif os.name == "posix":  # macOS / Linux
            # macOS
            mac_path = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default")
            if os.path.exists(mac_path):
                return mac_path
            # Linux
            linux_path = os.path.expanduser("~/.config/google-chrome/Default")
            if os.path.exists(linux_path):
                return linux_path
        return None

    # ============================================================
    # 从 Chrome 直接读取 Cookie（通过 CDP，推荐）
    # ============================================================

    async def fetch_from_cdp(self, cdp_helper, page_id: str, urls: List[str] = None) -> List[Dict]:
        """
        通过 CDP 从当前页面获取 Cookie（推荐方式）

        Args:
            cdp_helper: CDPHelper 实例
            page_id: 页面 ID
            urls: 限制获取指定 URL 的 Cookie（可选）

        Returns:
            Cookie 列表（CDP 格式）
        """
        params = {}
        if urls:
            params["urls"] = urls
        result = await cdp_helper.send_cdp_command(
            page_id, "Network.getCookies", params
        )
        return result.get("result", {}).get("cookies", [])

    async def inject_via_cdp(self, cdp_helper, page_id: str, cookies: List[Dict], url: str = None):
        """
        通过 CDP 注入 Cookie 到页面（推荐方式）

        Args:
            cdp_helper: CDPHelper 实例
            page_id: 页面 ID
            cookies: Cookie 列表
            url: 目标 URL（用于设置 domain，可选）
        """
        for cookie in cookies:
            # CDP 格式：需要 name, value, domain, path 等字段
            params = {
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain", ""),
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", False),
                "httpOnly": cookie.get("httpOnly", False),
                "sameSite": cookie.get("sameSite", "None"),
            }
            if "expires" in cookie and cookie["expires"] > 0:
                params["expires"] = cookie["expires"]

            await cdp_helper.send_cdp_command(
                page_id, "Network.setCookie", params
            )

    # ============================================================
    # Chrome Cookie 文件操作（直接读取 SQLite）
    # ============================================================

    def read_from_chrome_file(self, domain_filter: str = None) -> List[Dict]:
        """
        直接从 Chrome 的 Cookies SQLite 文件读取

        注意：需要 Chrome 未运行时才能读取（文件被锁定）

        Args:
            domain_filter: 域名过滤（如 "github.com"）

        Returns:
            Cookie 列表
        """
        if not self.chrome_profile_dir:
            raise RuntimeError("未找到 Chrome Profile 目录")

        cookies_db = os.path.join(self.chrome_profile_dir, "Cookies")
        if not os.path.exists(cookies_db):
            raise FileNotFoundError(f"Chrome Cookies 文件不存在: {cookies_db}")

        try:
            import sqlite3
            conn = sqlite3.connect(cookies_db)
            cursor = conn.cursor()

            query = "SELECT name, value, domain, path, expires_utc, is_secure, is_httponly, samesite FROM cookies"
            params = []
            if domain_filter:
                query += " WHERE domain LIKE ?"
                params.append(f"%{domain_filter}%")

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            cookies = []
            for row in rows:
                cookies.append({
                    "name": row[0],
                    "value": row[1],
                    "domain": row[2],
                    "path": row[3],
                    "expires": row[4],
                    "secure": bool(row[5]),
                    "httpOnly": bool(row[6]),
                    "sameSite": ["None", "Lax", "Strict"][row[7] if row[7] < 3 else 0],
                })
            return cookies

        except ImportError:
            raise RuntimeError("需要 sqlite3 库来读取 Chrome Cookies 文件")
        except Exception as e:
            raise RuntimeError(f"读取 Chrome Cookies 失败: {e}")

    # ============================================================
    # 文件导入/导出
    # ============================================================

    def export_to_json(self, cookies: List[Dict], filepath: str):
        """
        导出 Cookie 到 JSON 文件

        Args:
            cookies: Cookie 列表
            filepath: 输出文件路径
        """
        data = {
            "export_time": datetime.now().isoformat(),
            "count": len(cookies),
            "cookies": cookies
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def import_from_json(self, filepath: str) -> List[Dict]:
        """
        从 JSON 文件导入 Cookie

        Args:
            filepath: JSON 文件路径

        Returns:
            Cookie 列表
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("cookies", [])

    def export_to_netscape(self, cookies: List[Dict], filepath: str):
        """
        导出 Cookie 到 Netscape 格式（curl/wget 兼容）

        Args:
            cookies: Cookie 列表
            filepath: 输出文件路径
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This file was generated by ChromeBridge CookieManager\n")
            for cookie in cookies:
                domain = cookie.get("domain", "")
                # Netscape 格式：domain flag, domain, path, secure, expires, name, value
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                domain = domain.lstrip(".")
                path = cookie.get("path", "/")
                secure = "TRUE" if cookie.get("secure") else "FALSE"
                expires = str(cookie.get("expires", 0))
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                f.write(f"{flag}\t{domain}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")

    @staticmethod
    def parse_netscape(filepath: str) -> List[Dict]:
        """
        解析 Netscape Cookie 文件

        Args:
            filepath: Netscape Cookie 文件路径

        Returns:
            Cookie 列表
        """
        cookies = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    cookies.append({
                        "domain": parts[1],
                        "path": parts[2],
                        "secure": parts[3] == "TRUE",
                        "expires": int(parts[4]) if parts[4].isdigit() else 0,
                        "name": parts[5],
                        "value": parts[6],
                    })
        return cookies

    # ============================================================
    # Cookie 工具方法
    # ============================================================

    @staticmethod
    def filter_by_domain(cookies: List[Dict], domain: str) -> List[Dict]:
        """按域名过滤 Cookie"""
        return [c for c in cookies if domain in c.get("domain", "")]

    @staticmethod
    def to_header_string(cookies: List[Dict]) -> str:
        """将 Cookie 列表转换为 HTTP Cookie 头字符串"""
        return "; ".join([f"{c['name']}={c['value']}" for c in cookies])

    @staticmethod
    def from_header_string(header: str) -> List[Dict]:
        """从 HTTP Cookie 头字符串解析 Cookie"""
        cookies = []
        for part in header.split(";"):
            part = part.strip()
            if "=" in part:
                name, value = part.split("=", 1)
                cookies.append({"name": name.strip(), "value": value.strip()})
        return cookies


# ============================================================
# 全局单例
# ============================================================

_cookie_manager_instance: Optional[CookieManager] = None


def get_cookie_manager(chrome_profile_dir: Optional[str] = None) -> CookieManager:
    """获取全局 CookieManager 实例"""
    global _cookie_manager_instance
    if _cookie_manager_instance is None:
        _cookie_manager_instance = CookieManager(chrome_profile_dir=chrome_profile_dir)
    return _cookie_manager_instance
