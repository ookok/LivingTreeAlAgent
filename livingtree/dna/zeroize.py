"""ZeroizingSecret — Auto-wiping sensitive values from memory.

Inspired by OpenFang's Zeroizing<String>: automatically overwrites
memory with zeros when the value goes out of scope.

Usage:
    key = ZeroizingSecret("sk-xxx")
    # ... use key (only via get() or context manager) ...
    # key is auto-wiped on garbage collection

Never use str() directly — always use get() which returns a copy.
"""

from __future__ import annotations

import ctypes
import threading
from typing import Optional


class ZeroizingSecret:
    """A string that zeroizes its memory when no longer needed.

    Stores the value in a mutable bytearray. On garbage collection
    or explicit wipe(), overwrites with zeros before deallocation.
    """

    def __init__(self, value: str, encoding: str = "utf-8"):
        self._encoding = encoding
        self._data = bytearray(value.encode(encoding))
        self._lock = threading.Lock()

    def get(self) -> str:
        """Get the secret value. Returns a copy — never the raw buffer."""
        with self._lock:
            return bytes(self._data).decode(self._encoding)

    def wipe(self) -> None:
        """Explicitly zeroize the secret now."""
        with self._lock:
            for i in range(len(self._data)):
                self._data[i] = 0

    def __len__(self) -> int:
        return len(self._data)

    def __str__(self) -> str:
        return "[SECRET]"

    def __repr__(self) -> str:
        return f"ZeroizingSecret(len={len(self._data)})"

    def __del__(self):
        self.wipe()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.wipe()

    @staticmethod
    def from_bytes(data: bytes, encoding: str = "utf-8") -> "ZeroizingSecret":
        s = ZeroizingSecret("")
        s._data = bytearray(data)
        s._encoding = encoding
        return s


class SecretPool:
    """Manages a pool of ZeroizingSecrets with keyed access.

    All secrets are wiped when the pool is destroyed.
    """

    def __init__(self):
        self._secrets: dict[str, ZeroizingSecret] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._secrets:
                self._secrets[key].wipe()
            self._secrets[key] = ZeroizingSecret(value)

    def get(self, key: str, default: str = "") -> str:
        with self._lock:
            secret = self._secrets.get(key)
            return secret.get() if secret else default

    def wipe(self, key: str) -> None:
        with self._lock:
            secret = self._secrets.pop(key, None)
            if secret:
                secret.wipe()

    def wipe_all(self) -> None:
        with self._lock:
            for secret in self._secrets.values():
                secret.wipe()
            self._secrets.clear()

    def __del__(self):
        self.wipe_all()
