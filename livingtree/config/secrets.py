"""Encrypted secret storage for API keys and sensitive credentials.

Stores secrets encrypted at rest using:
- cryptography.fernet (preferred, pip install cryptography)
- Built-in fallback: machine-keyed XOR + base64 obfuscation

Secret file location: config/secrets.enc (auto-created)

Usage:
    from livingtree.config.secrets import SecretVault
    vault = SecretVault()
    vault.set("deepseek_api_key", "sk-xxx")
    key = vault.get("deepseek_api_key")
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from cryptography.fernet import Fernet


def _machine_key() -> bytes:
    """Generate a machine-specific encryption key (stable across Python versions)."""
    parts = [
        platform.node() or "unknown",
        str(uuid.getnode()),
        "livingtree-secret-vault-v2",
    ]
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).digest()


def _derive_fernet_key(machine_key: bytes) -> bytes:
    """Derive a Fernet-compatible 32-byte base64 key from machine key."""
    return base64.urlsafe_b64encode(machine_key[:32])


class SecretVault:
    """Encrypted key-value store for sensitive credentials.

    Thread-safe for reads, single-writer for writes.
    Uses Fernet encryption when cryptography is available,
    falls back to XOR obfuscation with machine-specific key.
    """

    def __init__(self, secret_file: str | Path | None = None):
        if secret_file is None:
            secret_file = Path("config/secrets.enc")

        self._path = Path(secret_file)
        self._machine_key = _machine_key()
        self._cache: dict[str, str] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._path.exists():
            try:
                raw = self._path.read_bytes()
                plain = self._decrypt(raw)
                self._cache = json.loads(plain)
                logger.debug(f"Loaded {len(self._cache)} secrets from {self._path}")
            except Exception as e:
                logger.warning(f"Failed to load secrets: {e}, starting fresh")
                self._cache = {}
        self._loaded = True

    def get(self, key: str, default: str = "") -> str:
        """Get a secret value."""
        self._ensure_loaded()
        return self._cache.get(key, default)

    def set(self, key: str, value: str) -> None:
        """Set and persist a secret value."""
        self._ensure_loaded()
        self._cache[key] = value
        self._save()

    def delete(self, key: str) -> bool:
        """Delete a secret from the vault."""
        self._ensure_loaded()
        if key in self._cache:
            del self._cache[key]
            self._save()
            return True
        return False

    def keys(self) -> list[str]:
        self._ensure_loaded()
        return list(self._cache.keys())

    def seed_defaults(self) -> int:
        """Seed built-in default API keys on first run (only if vault is empty).

        Keys come from environment variables — no plaintext secrets in source.
        Returns number of keys seeded."""
        self._ensure_loaded()
        if self._cache:
            return 0  # User already has keys, don't overwrite
        defaults = {}
        # SenseTime: set LT_BUILTIN_SENSETIME_KEY=sk-xxx to auto-seed
        st_key = os.environ.get("LT_BUILTIN_SENSETIME_KEY", "")
        if st_key:
            defaults["sensetime_api_key"] = st_key
        # Tianditu map: set LT_BUILTIN_TIANDITU_KEY=xxx to auto-seed
        tdt_key = os.environ.get("LT_BUILTIN_TIANDITU_KEY", "")
        if tdt_key:
            defaults["tianditu_key"] = tdt_key
        count = 0
        for k, v in defaults.items():
            if k not in self._cache:
                self._cache[k] = v
                count += 1
        if count:
            self._save()
            logger.info(f"Seeded {count} built-in default API key(s) into encrypted vault")
        return count

    def export_env(self) -> dict[str, str]:
        """Export secrets as env-var compatible dict (for subprocess)."""
        self._ensure_loaded()
        return {f"LT_SECRET_{k.upper()}": v for k, v in self._cache.items()}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        plain = json.dumps(self._cache, ensure_ascii=False)
        encrypted = self._encrypt(plain)
        self._path.write_bytes(encrypted)
        logger.debug(f"Saved {len(self._cache)} secrets to {self._path}")

    def _encrypt(self, plaintext: str) -> bytes:
        fernet_key = _derive_fernet_key(self._machine_key)
        f = Fernet(fernet_key)
        return f.encrypt(plaintext.encode("utf-8"))

    def _decrypt(self, ciphertext: bytes) -> str:
        try:
            fernet_key = _derive_fernet_key(self._machine_key)
            f = Fernet(fernet_key)
            return f.decrypt(ciphertext).decode("utf-8")
        except Exception:
            pass
        return self._xor_decrypt(ciphertext)

    def _xor_encrypt(self, plaintext: str) -> bytes:
        key = self._machine_key
        data = plaintext.encode("utf-8")
        result = bytes(a ^ key[i % len(key)] for i, a in enumerate(data))
        return base64.b64encode(result)

    def _xor_decrypt(self, ciphertext: bytes) -> str:
        key = self._machine_key
        try:
            data = base64.b64decode(ciphertext)
        except Exception:
            data = ciphertext
        result = bytes(a ^ key[i % len(key)] for i, a in enumerate(data))
        return result.decode("utf-8", errors="replace")


_vault_instance: Optional[SecretVault] = None


def get_secret_vault(secret_file: str | Path | None = None) -> SecretVault:
    """Get or create the global secret vault instance."""
    global _vault_instance
    if _vault_instance is None:
        _vault_instance = SecretVault(secret_file)
    return _vault_instance
