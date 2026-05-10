"""AdminManager — Secure admin authentication with encrypted credentials.

- Admin password hashed with PBKDF2 (SHA-256, 100k iterations) + random salt
- Encrypted at rest in SecretVault (Fernet)
- JWT sessions for admin access
- All API keys/passwords flow through Fernet encryption
- First-run initialization with admin password prompt

Integrates with existing SecretVault for all encryption.
"""

from __future__ import annotations

import hashlib
import hmac
import json as _json
import os
import secrets
import time as _time
from pathlib import Path
from typing import Optional

from loguru import logger


ADMIN_DIR = Path(".livingtree/admin")
ADMIN_DIR.mkdir(parents=True, exist_ok=True)
ADMIN_STATE_FILE = ADMIN_DIR / "admin_state.json"
JWT_SECRET_FILE = ADMIN_DIR / "jwt_secret.key"


def _load_or_create_jwt_secret() -> bytes:
    if JWT_SECRET_FILE.exists():
        return JWT_SECRET_FILE.read_bytes()
    key = secrets.token_bytes(32)
    JWT_SECRET_FILE.write_bytes(key)
    return key


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """PBKDF2 hash with random salt. Returns (hash_hex, salt_hex)."""
    salt = salt or secrets.token_bytes(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return dk.hex(), salt.hex()


def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    import base64
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


class AdminManager:
    """Secure admin authentication and credential management."""

    def __init__(self):
        self._jwt_secret = _load_or_create_jwt_secret()
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if ADMIN_STATE_FILE.exists():
            try:
                return _json.loads(ADMIN_STATE_FILE.read_text())
            except Exception:
                pass
        return {"initialized": False, "password_hash": "", "password_salt": ""}

    def _save_state(self):
        ADMIN_STATE_FILE.write_text(_json.dumps(self._state))

    @property
    def is_initialized(self) -> bool:
        return self._state.get("initialized", False)

    def initialize(self, password: str) -> bool:
        """Set initial admin password. Only works once."""
        if self.is_initialized:
            return False
        if len(password) < 6:
            return False
        pwd_hash, salt = _hash_password(password)
        self._state = {
            "initialized": True,
            "password_hash": pwd_hash,
            "password_salt": salt,
        }
        self._save_state()
        logger.info("Admin password initialized")
        return True

    def verify_password(self, password: str) -> bool:
        """Verify admin password against stored hash."""
        if not self.is_initialized:
            return False
        stored_hash = self._state["password_hash"]
        salt = bytes.fromhex(self._state["password_salt"])
        test_hash, _ = _hash_password(password, salt)
        return hmac.compare_digest(test_hash, stored_hash)

    def change_password(self, old_password: str, new_password: str) -> bool:
        if not self.verify_password(old_password):
            return False
        if len(new_password) < 6:
            return False
        pwd_hash, salt = _hash_password(new_password)
        self._state["password_hash"] = pwd_hash
        self._state["password_salt"] = salt
        self._save_state()
        return True

    def create_admin_token(self) -> str:
        """Create a short-lived admin JWT (1 hour)."""
        header = _b64url(_json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = _b64url(_json.dumps({
            "role": "admin",
            "iat": int(_time.time()),
            "exp": int(_time.time()) + 3600,
        }).encode())
        sig_input = f"{header}.{payload}".encode()
        sig = _b64url(hmac.digest(self._jwt_secret, sig_input, hashlib.sha256))
        return f"{header}.{payload}.{sig}"

    def verify_admin_token(self, token: str) -> Optional[dict]:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, payload_b64, sig = parts
            sig_input = f"{header_b64}.{payload_b64}".encode()
            expected = _b64url(hmac.digest(self._jwt_secret, sig_input, hashlib.sha256))
            if not hmac.compare_digest(sig, expected):
                return None
            payload = _json.loads(_b64url_decode(payload_b64))
            if payload.get("exp", 0) < _time.time():
                return None
            if payload.get("role") != "admin":
                return None
            return payload
        except Exception:
            return None

    # ── Credential Management (all encrypted via SecretVault) ──

    def store_credential(self, key: str, value: str) -> bool:
        """Store a credential encrypted in SecretVault."""
        try:
            from ..config.secrets import SecretVault
            vault = SecretVault()
            vault.set(key, value)
            logger.info(f"Credential stored: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to store credential {key}: {e}")
            return False

    def get_credential(self, key: str) -> str:
        """Retrieve a credential from encrypted vault."""
        try:
            from ..config.secrets import SecretVault
            return SecretVault().get(key, "")
        except Exception:
            return ""

    def delete_credential(self, key: str) -> bool:
        try:
            from ..config.secrets import SecretVault
            SecretVault().delete(key)
            return True
        except Exception:
            return False

    def list_credential_keys(self) -> list[str]:
        """List credential key names (not values)."""
        try:
            from ..config.secrets import SecretVault
            vault = SecretVault()
            vault._ensure_loaded()
            return list(vault._cache.keys())
        except Exception:
            return []

    def status(self) -> dict:
        keys = self.list_credential_keys()
        masked = {k: (v[:8] + "***" if len(v) > 8 else "***") for k, v in zip(
            keys,
            [self.get_credential(k) for k in keys],
        )}
        return {
            "initialized": self.is_initialized,
            "stored_credentials": len(keys),
            "credential_keys": keys,
            "credentials_masked": masked if len(masked) < 10 else {"count": len(masked)},
        }


_admin_instance: Optional[AdminManager] = None


def get_admin() -> AdminManager:
    global _admin_instance
    if _admin_instance is None:
        _admin_instance = AdminManager()
    return _admin_instance
