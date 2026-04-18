# relay_server/shared.py — 共享结构定义与脱敏工具
# 与 core/evolution/models.py 保持同步

"""
此文件为服务器端提供数据模型定义
客户端请使用 core/evolution/models.py
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib
import re


# ============ 枚举定义 ============

class PatchAction(Enum):
    INCREASE_TIMEOUT = "increase_timeout"
    DECREASE_TIMEOUT = "decrease_timeout"
    ENABLE_CACHE = "enable_cache"
    DISABLE_CACHE = "disable_cache"
    ADD_FALLBACK = "add_fallback"
    UPDATE_RETRY = "update_retry"
    UI_SIMPLIFY = "ui_simplify"
    UI_ADD_HINT = "ui_add_hint"
    UI_CHANGE_DEFAULT = "ui_change_default"
    CUSTOM = "custom"


class PainType(Enum):
    REPEATED_HELP = "repeated_help"
    LONG_STAY = "long_stay"
    OPERATION_ROLLBACK = "operation_rollback"
    FORM_ABANDON = "form_abandon"
    CONFUSING_UI = "confusing_ui"
    SLOW_RESPONSE = "slow_response"


class PainCause(Enum):
    INSUFFICIENT_HINT = "insufficient_hint"
    OPTION_COMPLEX = "option_complex"
    DEFAULT_UNREASONABLE = "default_unreasonable"
    FLOW_UNCLEAR = "flow_unclear"
    NETWORK_ISSUE = "network_issue"
    UNKNOWN = "unknown"


# ============ 共享脱敏工具 ============

class Desensitizer:
    """
    脱敏工具（服务器端验证用）
    """

    PATTERNS = [
        (r'password["\']?\s*[:=]\s*["\'][^"\']+["\']', 'password":"***"'),
        (r'token["\']?\s*[:=]\s*["\'][^"\']+["\']', 'token":"***"'),
        (r'secret["\']?\s*[:=]\s*["\'][^"\']+["\']', 'secret":"***"'),
        (r'api_key["\']?\s*[:=]\s*["\'][^"\']+["\']', 'api_key":"***"'),
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '***@***.com'),
        (r'\d{11}', '***'),
        (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '***.***.***.***'),
        (r'[C-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*', '***'),
    ]

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        if not text:
            return text
        result = text
        for pattern, replacement in cls.PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            if isinstance(data, str):
                return cls.sanitize_string(data)
            return data

        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(s in key_lower for s in ["password", "token", "secret", "auth", "key"]):
                result[key] = "***"
                continue

            if isinstance(value, dict):
                result[key] = cls.sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = [cls.sanitize_dict(v) if isinstance(v, dict) else
                              cls.sanitize_string(v) if isinstance(v, str) else v
                              for v in value]
            elif isinstance(value, str):
                result[key] = cls.sanitize_string(value)
            else:
                result[key] = value

        return result


# ============ 工具函数 ============

def get_week_id(t: datetime = None) -> str:
    """获取周标识"""
    if t is None:
        t = datetime.now()
    iso_calendar = t.isocalendar()
    return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"


def hash_for_dedup(*parts: str) -> str:
    """生成去重哈希"""
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]
