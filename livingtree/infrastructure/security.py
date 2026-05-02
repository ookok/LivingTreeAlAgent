"""
LivingTree 安全模块
===================

密钥管理、输入验证、速率限制
"""

import re
import hashlib
import hmac
import base64
import secrets
from typing import Optional, Tuple, Dict, Any
from threading import Lock
from datetime import datetime, timedelta
from collections import defaultdict


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100000, dklen=32
    )
    return base64.b64encode(key).decode(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    key, _ = hash_password(password, salt)
    return hmac.compare_digest(key, stored_hash)


_RATE_LIMIT_STORE: Dict[str, list] = defaultdict(list)
_RATE_LIMIT_LOCK = Lock()


def check_rate_limit(key: str, max_requests: int = 100,
                     window_seconds: int = 60) -> bool:
    now = datetime.now()
    with _RATE_LIMIT_LOCK:
        records = _RATE_LIMIT_STORE[key]
        records = [t for t in records if now - t < timedelta(seconds=window_seconds)]
        _RATE_LIMIT_STORE[key] = records

        if len(records) >= max_requests:
            return False

        records.append(now)
        return True


def sanitize_input(text: str, max_length: int = 10000) -> str:
    if not text:
        return ""
    text = text.strip()[:max_length]

    html_pattern = re.compile(r"<[^>]*>")
    text = html_pattern.sub("", text)

    js_patterns = [
        re.compile(r"(?i)javascript\s*:"),
        re.compile(r"(?i)on\w+\s*="),
    ]
    for p in js_patterns:
        text = p.sub("[blocked]", text)

    return text


def generate_api_key() -> str:
    return "ltai_" + secrets.token_urlsafe(32)


__all__ = [
    "hash_password",
    "verify_password",
    "check_rate_limit",
    "sanitize_input",
    "generate_api_key",
]
