"""
External AI Client - 外部AI客户端
================================

支持:
1. 豆包 (Doubao) - GUI自动化调用
2. 元宝 (Yuanbao) - GUI自动化调用
3. API直连 (可选)

降级策略:
- 首选GUI自动化（用户已登录的情况下）
- 备选API直连（如果有API Key）
"""

from __future__ import annotations

import sys
import time
import subprocess
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

try:
    from core.config.unified_config import get_config as _get_unified_config
    _uconfig_ea = _get_unified_config()
except Exception:
    _uconfig_ea = None

def _ea_get(key: str, default):
    return _uconfig_ea.get(key, default) if _uconfig_ea else default

logger = logging.getLogger(__name__)


class ExternalAIType(Enum):
    """外部AI类型"""
    DOUBAN = "douban"
    YUANBAO = "yuanbao"
    KIMI = "kimi"
    OTHER = "other"


@dataclass
class ExternalAIResult:
    """外部AI调用结果"""
    success: bool
    response: str = ""
    error: str = ""
    source: ExternalAIType = ExternalAIType.OTHER
    method: str = ""  # "gui" / "api"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "response": self.response,
            "error": self.error,
            "source": self.source.value,
            "method": self.method,
            "metadata": self.metadata,
        }


class ExternalAIClient:
    """
    外部AI客户端

    支持多种外部AI服务的调用
    """

    # 应用路径配置
    APP_PATHS = {
        "douban": {
            "win32": [
                r"C:\Program Files\Douban\Douban.exe",
                r"C:\Program Files (x86)\Douban\Douban.exe",
            ],
            "darwin": ["/Applications/Douban.app"],
        },
        "yuanbao": {
            "win32": [
                r"C:\Program Files\Tencent\Yuanbao\Yuanbao.exe",
                r"C:\Program Files (x86)\Tencent\Yuanbao\Yuanbao.exe",
            ],
            "darwin": ["/Applications/Yuanbao.app"],
        },
    }

    def __init__(self):
        self.platform = sys.platform
        self.last_result: Optional[ExternalAIResult] = None

    def call(
        self,
        prompt: str,
        ai_type: ExternalAIType = ExternalAIType.DOUBAN,
        method: str = "gui",
        callback: Optional[Callable[[str], None]] = None,
    ) -> ExternalAIResult:
        """
        调用外部AI

        Args:
            prompt: 优化后的提示词
            ai_type: AI类型
            method: 调用方式 ("gui" / "clipboard")
            callback: 进度回调

        Returns:
            ExternalAIResult: 调用结果
        """
        if method == "gui":
            return self._call_gui(prompt, ai_type, callback)
        else:
            return self._call_clipboard(prompt, ai_type)

    def _call_gui(
        self,
        prompt: str,
        ai_type: ExternalAIType,
        callback: Optional[Callable[[str], None]] = None,
    ) -> ExternalAIResult:
        """通过GUI自动化调用"""
        app_name = self._get_app_name(ai_type)

        # 1. 检查应用是否可用
        app_path = self._find_app(ai_type)
        if not app_path:
            return ExternalAIResult(
                success=False,
                error=f"未找到 {app_name}，请确认已安装",
                source=ai_type,
                method="gui",
            )

        try:
            # 2. 复制提示词到剪贴板
            self._copy_to_clipboard(prompt)
            if callback:
                callback("提示词已复制到剪贴板")

            # 3. 打开应用
            if not self._open_app(app_path):
                return ExternalAIResult(
                    success=False,
                    error=f"无法打开 {app_name}",
                    source=ai_type,
                    method="gui",
                )
            if callback:
                callback(f"已打开 {app_name}")

            # 4. 等待用户操作
            time.sleep(_ea_get("delays.wait_short", 2))

            # 5. 尝试执行粘贴和发送（如果有自动化接口）
            # 注意：大多数应用不支持自动化，这里作为提示
            if callback:
                callback("请在AI窗口中粘贴并发送问题")

            return ExternalAIResult(
                success=True,
                response="提示词已准备，请在AI窗口中粘贴并发送",
                source=ai_type,
                method="gui",
                metadata={
                    "app_path": str(app_path),
                    "instruction": "请手动粘贴提示词并发送，结果可复制回本应用",
                }
            )

        except Exception as e:
            logger.error(f"GUI调用失败: {e}")
            return ExternalAIResult(
                success=False,
                error=str(e),
                source=ti_type,
                method="gui",
            )

    def _call_clipboard(
        self,
        prompt: str,
        ai_type: ExternalAIType,
    ) -> ExternalAIResult:
        """仅复制到剪贴板"""
        app_name = self._get_app_name(ai_type)

        try:
            self._copy_to_clipboard(prompt)

            return ExternalAIResult(
                success=True,
                response=f"提示词已复制到剪贴板，请打开{app_name}粘贴使用",
                source=ai_type,
                method="clipboard",
                metadata={
                    "instruction": f"1. 打开{app_name}\n2. 粘贴并发送\n3. 复制回答回本应用",
                }
            )

        except Exception as e:
            return ExternalAIResult(
                success=False,
                error=str(e),
                source=ai_type,
                method="clipboard",
            )

    def _get_app_name(self, ai_type: ExternalAIType) -> str:
        """获取应用名称"""
        names = {
            ExternalAIType.DOUBAN: "豆包",
            ExternalAIType.YUANBAO: "元宝",
            ExternalAIType.KIMI: "Kimi",
        }
        return names.get(ai_type, "AI助手")

    def _find_app(self, ai_type: ExternalAIType) -> Optional[Path]:
        """查找应用路径"""
        paths = self.APP_PATHS.get(ai_type.value, {}).get(self.platform, [])

        for path_str in paths:
            path = Path(path_str)
            if path.exists():
                return path

        # 尝试常见位置
        common_paths = self._get_common_paths(ai_type)
        for path in common_paths:
            if path.exists():
                return path

        return None

    def _get_common_paths(self, ai_type: ExternalAIType) -> List[Path]:
        """获取常见路径"""
        if self.platform == "win32":
            base = Path("C:/Program Files")
        else:
            base = Path("/Applications")

        names = {
            ExternalAIType.DOUBAN: ["Douban", "豆包"],
            ExternalAIType.YUANBAO: ["Yuanbao", "元宝"],
        }

        paths = []
        for name in names.get(ai_type, []):
            if self.platform == "win32":
                paths.extend([
                    base / name / f"{name}.exe",
                    base / "Tencent" / name / f"{name}.exe",
                ])
            else:
                paths.append(base / f"{name}.app")

        return paths

    def _open_app(self, path: Path) -> bool:
        """打开应用"""
        try:
            if self.platform == "win32":
                subprocess.Popen(
                    ["start", "", str(path)],
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["open", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return True
        except Exception as e:
            logger.error(f"打开应用失败: {e}")
            return False

    def _copy_to_clipboard(self, text: str) -> bool:
        """复制到剪贴板"""
        try:
            if self.platform == "win32":
                # Windows
                subprocess.run(
                    ["powershell", "-Command", f"Set-Clipboard -Value '{text.replace(chr(39), chr(39)+chr(39))}'"],
                    capture_output=True,
                    check=True,
                )
            else:
                # macOS
                subprocess.run(
                    ["pbcopy"],
                    input=text.encode(),
                    check=True,
                )
            return True
        except Exception as e:
            logger.error(f"复制到剪贴板失败: {e}")
            # 尝试回退方案
            try:
                import pyperclip
                pyperclip.copy(text)
                return True
            except ImportError:
                logger.warning("pyperclip 未安装，剪贴板功能不可用")
                return False
            except Exception:
                return False

    def check_available(self, ai_type: ExternalAIType) -> Dict[str, Any]:
        """检查AI是否可用"""
        app_path = self._find_app(ai_type)
        return {
            "available": app_path is not None,
            "app_path": str(app_path) if app_path else None,
            "app_name": self._get_app_name(ai_type),
            "platform": self.platform,
        }

    def get_all_available(self) -> Dict[str, Dict[str, Any]]:
        """获取所有AI的可用性"""
        return {
            "douban": self.check_available(ExternalAIType.DOUBAN),
            "yuanbao": self.check_available(ExternalAIType.YUANBAO),
        }


# 全局实例
_client: Optional[ExternalAIClient] = None


def get_external_ai_client() -> ExternalAIClient:
    """获取外部AI客户端实例"""
    global _client
    if _client is None:
        _client = ExternalAIClient()
    return _client