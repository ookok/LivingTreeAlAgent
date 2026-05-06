"""Web2API — turn any AI web interface into an OpenAI-compatible API.

Core architecture:
  WebProvider (abstract) → implements login/chat/stream for one platform
  AccountPool            → multi-account round-robin + health check
  Web2APIServer          → FastAPI server exposing /v1/chat/completions

Extensible: add new providers by subclassing WebProvider and registering.
  - DeepSeekProvider: chat.deepseek.com → done
  - ClaudeProvider:   claude.ai → template
  - GeminiProvider:   gemini.google.com → template
  - KimiProvider:     kimi.moonshot.cn → template
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, AsyncIterator

from loguru import logger


# ═══ Data Models ═══

class AccountStatus(str, Enum):
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    BANNED = "banned"
    EXPIRED = "expired"


@dataclass
class WebAccount:
    """A single AI web account."""
    email: str
    password: str = ""
    token: str = ""            # auth token (refreshed on login)
    cookies: dict = field(default_factory=dict)
    status: AccountStatus = AccountStatus.ACTIVE
    last_used: float = 0.0
    request_count: int = 0
    error_count: int = 0
    cooldown_until: float = 0.0

    def is_available(self) -> bool:
        if self.status != AccountStatus.ACTIVE:
            return False
        if self.cooldown_until > time.time():
            return False
        return True


@dataclass
class ProviderResult:
    """Unified result from any web provider."""
    text: str = ""
    reasoning: str = ""
    tokens: int = 0
    model: str = ""
    finish_reason: str = "stop"
    error: str = ""
    account_used: str = ""


# ═══ Abstract Provider ═══

class WebProvider(ABC):
    """Abstract base for any AI web interface provider.

    To add a new platform, subclass and implement:
      - login():      authenticate and get session token
      - chat():       send a message, get response
      - chat_stream(): streaming version
    """

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url

    @abstractmethod
    async def login(self, account: WebAccount) -> bool:
        """Login and populate account.token/cookies."""

    @abstractmethod
    async def chat(
        self, messages: list[dict], account: WebAccount,
        temperature: float = 0.7, max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> ProviderResult:
        """Send a chat request and return the complete response."""

    @abstractmethod
    async def chat_stream(
        self, messages: list[dict], account: WebAccount,
        temperature: float = 0.7, max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> AsyncIterator[str]:
        """Streaming version — yields text chunks."""

    def supports_tools(self) -> bool:
        return False

    def model_name(self) -> str:
        return self.name


# ═══ Account Pool ═══

class AccountPool:
    """Multi-account pool with round-robin + health management."""

    def __init__(self):
        self._accounts: list[WebAccount] = []
        self._index: int = 0
        self._lock = asyncio.Lock()

    def add(self, account: WebAccount) -> None:
        self._accounts.append(account)

    def remove(self, email: str) -> None:
        self._accounts = [a for a in self._accounts if a.email != email]

    async def acquire(self) -> Optional[WebAccount]:
        """Get the next available account (round-robin)."""
        async with self._lock:
            if not self._accounts:
                return None
            active = [a for a in self._accounts if a.is_available()]
            if not active:
                return None

            for _ in range(len(active)):
                self._index = (self._index + 1) % len(active)
                account = active[self._index]
                if account.is_available():
                    account.last_used = time.time()
                    account.request_count += 1
                    return account

            return None

    def mark_error(self, account: WebAccount) -> None:
        account.error_count += 1
        if account.error_count >= 5:
            account.status = AccountStatus.RATE_LIMITED
            account.cooldown_until = time.time() + 300
            logger.warning("AccountPool: %s rate-limited for 5min", account.email)

    def mark_success(self, account: WebAccount) -> None:
        account.error_count = 0

    def get_stats(self) -> dict:
        return {
            "total": len(self._accounts),
            "active": sum(1 for a in self._accounts if a.status == AccountStatus.ACTIVE),
            "rate_limited": sum(1 for a in self._accounts if a.status == AccountStatus.RATE_LIMITED),
            "total_requests": sum(a.request_count for a in self._accounts),
        }
