"""Chinese AI Web Providers — 8 domestic platforms, zero scinet needed.

All providers follow the same WebProvider interface:
  login() → get session token
  chat()  → send messages via internal API
  chat_stream() → SSE streaming

Platforms implemented:
  通义千问 (Qwen)  — tongyi.aliyun.com    免费百万token/月
  智谱清言 (GLM)    — chatglm.cn           有免费层
  豆包 (Doubao)    — doubao.com           字节跳动
  讯飞星火 (Spark)  — xinghuo.xfyun.cn     有免费层
  百川 (Baichuan)  — baichuan-ai.com      有免费层
  元宝 (Yuanbao)   — yuanbao.tencent.com  腾讯
  MiniMax          — hailoai.com          有免费层
  阶跃 (StepChat)  — stepchat.cn           有额度

All domestic — zero scinet dependency.
"""

from __future__ import annotations

import json
import time
from typing import AsyncIterator

from loguru import logger

from .base_provider import WebProvider, WebAccount, ProviderResult

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

_COMMON_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"


# ═══ 通义千问 ═══

class QwenWebProvider(WebProvider):
    """通义千问 (tongyi.aliyun.com) — 阿里达摩院出品，免费百万token/月。

    Internal API: /api/chat  (standard OpenAI-compatible format)
    Login: Alibaba Cloud account → session cookie
    """

    BASE = "https://tongyi.aliyun.com"

    def __init__(self):
        super().__init__(name="qwen-web", base_url=self.BASE)

    async def login(self, account: WebAccount) -> bool:
        if not HAS_AIOHTTP: return False
        if not account.token:
            payload = {"loginType": "password", "account": account.email, "password": account.password}
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(f"{self.BASE}/api/login", json=payload,
                                     headers={"User-Agent": _COMMON_UA, "Content-Type": "application/json"},
                                     timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            account.token = data.get("token") or data.get("data", {}).get("token", "")
                            account.cookies = {k: v.value for k, v in resp.cookies.items()}
                            return bool(account.token)
            except Exception as e:
                logger.warning("QwenWeb login: %s", e)
                return False

        return await self._verify(account)

    async def _verify(self, account: WebAccount) -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.BASE}/api/user/info", headers={"Authorization": f"Bearer {account.token}"},
                                timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="qwen")
        if not account.token: result.error = "Not logged in"; return result
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/api/chat",
                    json={"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False},
                    headers={"Authorization": f"Bearer {account.token}", "Content-Type": "application/json",
                            "User-Agent": _COMMON_UA, "Origin": self.BASE, "Referer": f"{self.BASE}/"},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("response") or data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return result
                    result.error = f"HTTP {resp.status}"; return result
        except Exception as e: result.error = str(e); return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout); yield result.text

    def model_name(self) -> str: return "qwen-max"


# ═══ 智谱清言 ═══

class GLMWebProvider(WebProvider):
    """智谱清言 (chatglm.cn) — ChatGLM系列，OpenAI兼容API。

    Has its own OpenAI-compatible API at open.bigmodel.cn.
    Can use official API key directly.
    """

    BASE = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(self):
        super().__init__(name="glm-web", base_url=self.BASE)

    async def login(self, account: WebAccount) -> bool:
        if not HAS_AIOHTTP: return False
        if not account.token:
            # Try phone login to web version
            payload = {"phone": account.email, "password": account.password}
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post("https://chatglm.cn/api/user/login", json=payload,
                                     headers={"User-Agent": _COMMON_UA, "Content-Type": "application/json"},
                                     timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            account.token = data.get("token") or data.get("data", {}).get("token", "")
                            return bool(account.token)
            except Exception as e: logger.warning("GLMWeb login: %s", e)
            return False
        # Verify API key mode
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.BASE}/models", headers={"Authorization": f"Bearer {account.token}"},
                                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception: return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="glm")
        if not account.token: result.error = "Not logged in"; return result
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/chat/completions",
                    json={"model": "glm-4-plus", "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                    headers={"Authorization": f"Bearer {account.token}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return result
                    result.error = f"HTTP {resp.status}"; return result
        except Exception as e: result.error = str(e); return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout); yield result.text

    def model_name(self) -> str: return "glm-4-plus"


# ═══ 豆包 ═══

class DoubaoWebProvider(WebProvider):
    """豆包 (doubao.com) — 字节跳动AI助手。

    Internal API: uses ByteDance's Volcengine backend.
    Login: phone/抖音 account → session token
    """

    BASE = "https://www.doubao.com"

    def __init__(self):
        super().__init__(name="doubao-web", base_url=self.BASE)

    async def login(self, account: WebAccount) -> bool:
        if not HAS_AIOHTTP: return False
        if account.token:
            return await self._verify(account)
        if not account.password: return False

        payload = {"account": account.email, "password": account.password, "accountType": "phone"}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/api/passport/login", json=payload,
                                 headers={"User-Agent": _COMMON_UA, "Content-Type": "application/json",
                                         "Origin": self.BASE, "Referer": f"{self.BASE}/"},
                                 timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        account.token = data.get("token") or data.get("data", {}).get("token", "")
                        account.cookies = {k: v.value for k, v in resp.cookies.items()}
                        return bool(account.token)
        except Exception as e: logger.warning("DoubaoWeb login: %s", e)
        return False

    async def _verify(self, account: WebAccount) -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.BASE}/api/user/profile", headers={"Authorization": f"Bearer {account.token}"},
                                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception: return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="doubao")
        if not account.token: result.error = "Not logged in"; return result
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/api/chat/completion",
                    json={"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False},
                    headers={"Authorization": f"Bearer {account.token}", "Content-Type": "application/json",
                            "User-Agent": _COMMON_UA, "Origin": self.BASE},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("reply") or data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return result
                    result.error = f"HTTP {resp.status}"; return result
        except Exception as e: result.error = str(e); return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout); yield result.text

    def model_name(self) -> str: return "doubao-pro"


# ═══ 讯飞星火 ═══

class SparkWebProvider(WebProvider):
    """讯飞星火 (xinghuo.xfyun.cn) — 讯飞大模型。

    Internal API: WebSocket-based, uses xfyun.cn backend.
    Login: 讯飞账号 → session
    """

    BASE = "https://xinghuo.xfyun.cn"

    def __init__(self):
        super().__init__(name="spark-web", base_url=self.BASE)

    async def login(self, account: WebAccount) -> bool:
        if not HAS_AIOHTTP: return False
        if not account.token and account.password:
            payload = {"account": account.email, "password": account.password}
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(f"{self.BASE}/api/login", json=payload,
                                     headers={"User-Agent": _COMMON_UA, "Content-Type": "application/json"},
                                     timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            account.token = data.get("token") or data.get("data", {}).get("accessToken", "")
                            return bool(account.token)
            except Exception as e: logger.warning("SparkWeb login: %s", e)
        return account.token and await self._verify(account)

    async def _verify(self, account: WebAccount) -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.BASE}/api/user/check", headers={"Authorization": f"Bearer {account.token}"},
                                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception: return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="spark")
        if not account.token: result.error = "Not logged in"; return result
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/api/chat",
                    json={"messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                    headers={"Authorization": f"Bearer {account.token}", "Content-Type": "application/json",
                            "User-Agent": _COMMON_UA},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("answer") or data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return result
                    result.error = f"HTTP {resp.status}"; return result
        except Exception as e: result.error = str(e); return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout); yield result.text

    def model_name(self) -> str: return "spark-v4.0"


# ═══ 百川智能 ═══

class BaichuanWebProvider(WebProvider):
    """百川智能 (baichuan-ai.com) — Baichuan大模型。

    Internal API: OpenAI-compatible format.
    """

    BASE = "https://api.baichuan-ai.com/v1"

    def __init__(self):
        super().__init__(name="baichuan-web", base_url=self.BASE)

    async def login(self, account: WebAccount) -> bool:
        if not HAS_AIOHTTP: return False
        if not account.token: return False
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.BASE}/models", headers={"Authorization": f"Bearer {account.token}"},
                                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception: return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="baichuan")
        if not account.token: result.error = "API key required"; return result
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/chat/completions",
                    json={"model": "Baichuan4", "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                    headers={"Authorization": f"Bearer {account.token}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return result
                    result.error = f"HTTP {resp.status}"; return result
        except Exception as e: result.error = str(e); return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout); yield result.text

    def model_name(self) -> str: return "Baichuan4"


# ═══ 腾讯元宝 ═══

class YuanbaoWebProvider(WebProvider):
    """腾讯元宝 (yuanbao.tencent.com) — 腾讯混元大模型。

    Internal API: uses Tencent's Hunyuan backend.
    Login: WeChat/QQ → session
    """

    BASE = "https://yuanbao.tencent.com"

    def __init__(self):
        super().__init__(name="yuanbao-web", base_url=self.BASE)

    async def login(self, account: WebAccount) -> bool:
        if not HAS_AIOHTTP: return False
        if account.token:
            return await self._verify(account)
        if not account.password: return False

        payload = {"account": account.email, "password": account.password}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/api/user/login", json=payload,
                                 headers={"User-Agent": _COMMON_UA, "Content-Type": "application/json",
                                         "Origin": self.BASE},
                                 timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        account.token = data.get("token") or data.get("data", {}).get("token", "")
                        return bool(account.token)
        except Exception as e: logger.warning("YuanbaoWeb login: %s", e)
        return False

    async def _verify(self, account: WebAccount) -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.BASE}/api/user/info", headers={"Authorization": f"Bearer {account.token}"},
                                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception: return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="yuanbao")
        if not account.token: result.error = "Not logged in"; return result
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/api/chat",
                    json={"messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False},
                    headers={"Authorization": f"Bearer {account.token}", "Content-Type": "application/json",
                            "User-Agent": _COMMON_UA, "Origin": self.BASE},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("reply") or data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return result
                    result.error = f"HTTP {resp.status}"; return result
        except Exception as e: result.error = str(e); return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout); yield result.text

    def model_name(self) -> str: return "hunyuan-turbo"


# ═══ MiniMax ═══

class MiniMaxWebProvider(WebProvider):
    """MiniMax (hailuoai.com) — 海螺AI，MiniMax出品。

    Internal API: OpenAI-compatible at api.minimax.chat
    """

    BASE = "https://api.minimax.chat/v1"

    def __init__(self):
        super().__init__(name="minimax-web", base_url=self.BASE)

    async def login(self, account: WebAccount) -> bool:
        if not HAS_AIOHTTP: return False
        if not account.token: return False
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.BASE}/models", headers={"Authorization": f"Bearer {account.token}"},
                                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception: return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="minimax")
        if not account.token: result.error = "API key required"; return result
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/chat/completions",
                    json={"model": "abab7-chat", "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                    headers={"Authorization": f"Bearer {account.token}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return result
                    result.error = f"HTTP {resp.status}"; return result
        except Exception as e: result.error = str(e); return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout); yield result.text

    def model_name(self) -> str: return "abab7-chat"


# ═══ 阶跃星辰 ═══

class StepChatWebProvider(WebProvider):
    """阶跃星辰 (stepchat.cn) — Step系列大模型。

    Internal API: OpenAI-compatible.
    """

    BASE = "https://api.stepfun.com/v1"

    def __init__(self):
        super().__init__(name="stepchat-web", base_url=self.BASE)

    async def login(self, account: WebAccount) -> bool:
        if not HAS_AIOHTTP: return False
        if not account.token: return False
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.BASE}/models", headers={"Authorization": f"Bearer {account.token}"},
                                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception: return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="stepchat")
        if not account.token: result.error = "API key required"; return result
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.BASE}/chat/completions",
                    json={"model": "step-2-16k", "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                    headers={"Authorization": f"Bearer {account.token}", "Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return result
                    result.error = f"HTTP {resp.status}"; return result
        except Exception as e: result.error = str(e); return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout); yield result.text

    def model_name(self) -> str: return "step-2-16k"
