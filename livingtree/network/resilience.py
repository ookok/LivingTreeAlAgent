"""Network Resilience — auto proxy/mirror/retry for all network operations.

When a network call fails (timeout, DNS, connection refused), this layer
automatically:
  1. Retries with exponential backoff
  2. Switches to Chinese mirrors for known platforms
  3. Falls back to user-configured proxy (LIVINGTREE_PROXY env var)
  4. Sets pip/npm/git mirror configs in subprocess environments

Used transparently by pkg_manager, self_updater, wt_bootstrap, and all
modules that make HTTP requests or run shell install commands.
"""
from __future__ import annotations

import asyncio
import os
import random
import subprocess
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from loguru import logger

# ═══ Mirror URL patterns ═══

MIRROR_REWRITE: dict[str, str] = {
    # GitHub
    "https://github.com": "https://ghproxy.com/https://github.com",
    "https://raw.githubusercontent.com": "https://ghproxy.com/https://raw.githubusercontent.com",
    "https://api.github.com": "https://ghproxy.com/https://api.github.com",
    # PyPI
    "https://pypi.org": "https://pypi.tuna.tsinghua.edu.cn",
    "https://files.pythonhosted.org": "https://pypi.tuna.tsinghua.edu.cn/packages",
    # npm
    "https://registry.npmjs.org": "https://registry.npmmirror.com",
    # HuggingFace
    "https://huggingface.co": "https://hf-mirror.com",
    # Node.js
    "https://nodejs.org/dist": "https://npmmirror.com/mirrors/node",
    # ModelScope (already Chinese, but add fallback)
    "https://modelscope.cn": "https://modelscope.cn",
}

# Alternative mirrors for when the primary fails
FALLBACK_MIRRORS: dict[str, list[str]] = {
    "github": [
        "https://ghproxy.com/https://github.com",
        "https://mirror.ghproxy.com/https://github.com",
        "https://gh.api.99988866.xyz/https://github.com",
    ],
    "pypi": [
        "https://pypi.tuna.tsinghua.edu.cn/simple",
        "https://mirrors.aliyun.com/pypi/simple",
        "https://mirrors.ustc.edu.cn/pypi/simple",
    ],
    "npm": [
        "https://registry.npmmirror.com",
        "https://registry.npm.taobao.org",
    ],
    "huggingface": [
        "https://hf-mirror.com",
        "https://hf.xeduapi.com",
    ],
}

# ═══ Proxy detection ═══

def _get_proxy() -> str | None:
    """Detect user-configured proxy from env vars + auto-discover from proxy pool."""
    for var in ("LIVINGTREE_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        val = os.environ.get(var, "")
        if val and "://" in val:
            return val

    # Try to load from proxy pool (client-side proxy infrastructure)
    try:
        proxy = _get_proxy_from_pool()
        if proxy:
            return proxy
    except Exception:
        pass

    return None


def _get_proxy_from_pool() -> str | None:
    """Attempt to get a working proxy from the proxy pool."""
    try:
        from .proxy_fetcher import get_proxy_pool
        pool = get_proxy_pool()
        proxy = pool.get_best()
        if proxy and proxy.success_rate > 0.3:
            return proxy.url
    except Exception:
        pass

    return None


# ═══ Overseas domain detection ═══

_OVERSEAS_DOMAINS: set[str] | None = None


def _is_overseas_domain(domain: str) -> bool:
    """Check if domain needs acceleration (non-Chinese site)."""
    cn_suffixes = ('.cn', '.com.cn', '.org.cn', '.edu.cn', '.gov.cn', '.net.cn')
    if domain.endswith(cn_suffixes):
        return False
    local_hosts = ('localhost', '127.0.0.1', '::1', '0.0.0.0')
    if domain in local_hosts:
        return False
    common_overseas = (
        'github.com', 'githubusercontent.com', 'huggingface.co', 'docker.com',
        'pypi.org', 'pythonhosted.org', 'npmjs.com', 'google.com', 'googleapis.com',
        'gstatic.com', 'youtube.com', 'ytimg.com', 'ggpht.com', 'googlevideo.com',
        'stackoverflow.com', 'stackexchange.com', 'serverfault.com', 'superuser.com',
        'askubuntu.com', 'reddit.com', 'medium.com', 'dev.to', 'gitlab.com',
        'arxiv.org', 'wikipedia.org', 'ycombinator.com', 'bitbucket.org',
        'sourceforge.net', 'rubygems.org', 'crates.io', 'nodejs.org',
        'maven.org', 'apache.org', 'android.com', 'python.org',
        'pytorch.org', 'tensorflow.org', 'kubernetes.io', 'flutter.dev',
        'dart.dev', 'golang.org', 'rust-lang.org', 'kernel.org', 'llvm.org',
    )
    if any(domain.endswith(d) or domain == d for d in common_overseas):
        return True
    return domain.endswith(('.com', '.org', '.net', '.io', '.dev', '.ai',
                            '.app', '.co', '.me', '.info', '.us', '.eu'))


def _get_proxy_dict() -> dict[str, str] | None:
    """Get proxy as a dict for httpx/aiohttp."""
    proxy = _get_proxy()
    if not proxy:
        return None
    # Support socks5 by mapping to http transport
    if proxy.startswith("socks5"):
        proxy = proxy.replace("socks5://", "http://")
    return {"http://": proxy, "https://": proxy}


# ═══ Mirror URL rewriting ═══

def rewrite_url(url: str) -> str:
    """Rewrite a URL to use a Chinese mirror if applicable."""
    for original, mirror in MIRROR_REWRITE.items():
        if url.startswith(original):
            rewritten = url.replace(original, mirror, 1)
            if rewritten != url:
                return rewritten
    return url


def get_mirrors(platform: str) -> list[str]:
    """Get fallback mirrors for a platform."""
    return FALLBACK_MIRRORS.get(platform, [])


# ═══ Subprocess env with mirrors ═══

def get_mirror_env() -> dict[str, str]:
    """Return environment variables with Chinese mirrors for pip/npm/git.

    Use this when running subprocess commands to ensure they use mirrors.
    """
    env = os.environ.copy()

    # pip mirrors
    env["PIP_INDEX_URL"] = "https://pypi.tuna.tsinghua.edu.cn/simple"
    env["PIP_TRUSTED_HOST"] = "pypi.tuna.tsinghua.edu.cn"

    # npm mirrors
    env["npm_config_registry"] = "https://registry.npmmirror.com"
    env["NODE_MIRROR"] = "https://npmmirror.com/mirrors/node"

    # HuggingFace
    env["HF_ENDPOINT"] = "https://hf-mirror.com"

    # Proxy (if configured)
    proxy = _get_proxy()
    if proxy:
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["http_proxy"] = proxy
        env["https_proxy"] = proxy

    return env


# ═══ Core retry executor ═══

async def resilient_fetch(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    data: bytes | None = None,
    timeout: float = 30.0,
    max_retries: int = 3,
    use_mirror: bool = True,
    use_proxy: bool = True,
    use_accelerator: bool = True,
) -> tuple[int, bytes, str]:
    """Fetch a URL with automatic accelerator/mirror/proxy/retry fallback.

    Returns (status_code, body_bytes, final_url_used).
    """
    import httpx

    last_error = ""
    urls_to_try = [url]

    # ── SiteAccelerator: attempt optimal IP routing for overseas domains ──
    accelerated_url = None
    if use_accelerator:
        try:
            from .site_accelerator import get_accelerator
            accel = get_accelerator()
            domain = urlparse(url).hostname or ""
            if _is_overseas_domain(domain):
                params = accel.get_optimal_connection_params(url)
                if params.get("resolved_ip"):
                    original_domain = params["original_domain"]
                    accelerated_url = url.replace(
                        f"://{original_domain}", f"://{params['resolved_ip']}"
                    )
                    urls_to_try.insert(0, accelerated_url)
                    logger.debug(
                        "Accelerating %s → %s (est. %.0fms)",
                        original_domain, params["resolved_ip"],
                        params.get("estimated_latency_ms", 0),
                    )
        except Exception as e:
            logger.debug("SiteAccelerator lookup failed: %s", e)

    if use_mirror:
        mirror_url = rewrite_url(url)
        if mirror_url != url:
            urls_to_try.append(mirror_url)

    proxy_dict = _get_proxy_dict() if use_proxy else None

    for attempt in range(max_retries + 1):
        for try_url in urls_to_try:
            try:
                current_headers = dict(headers or {})
                # If using accelerated IP, set Host header
                if accelerated_url and try_url == accelerated_url:
                    original_host = urlparse(url).hostname or ""
                    current_headers["Host"] = original_host

                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout),
                    proxy=proxy_dict.get("http://") if proxy_dict else None,
                    follow_redirects=True,
                ) as client:
                    if method == "GET":
                        resp = await client.get(try_url, headers=current_headers)
                    elif method == "POST":
                        resp = await client.post(try_url, content=data, headers=current_headers)
                    else:
                        resp = await client.request(method, try_url, content=data, headers=current_headers)

                    if resp.status_code < 500:
                        # Report success to accelerator
                        if accelerated_url and try_url == accelerated_url:
                            try:
                                domain = urlparse(url).hostname or ""
                                params = accel.get_optimal_connection_params(url)
                                if params.get("resolved_ip"):
                                    accel._ip_pool.update_ip(domain, params["resolved_ip"],
                                                           latency_ms=50, success=True)
                            except Exception:
                                pass
                        return resp.status_code, resp.content, try_url

                    last_error = f"HTTP {resp.status_code}"

            except httpx.ConnectError:
                last_error = "Connection refused"
                if accelerated_url and try_url == accelerated_url:
                    try:
                        domain = urlparse(url).hostname or ""
                        params = accel.get_optimal_connection_params(url)
                        if params.get("resolved_ip"):
                            accel._ip_pool.update_ip(domain, params["resolved_ip"],
                                                   latency_ms=999, success=False)
                    except Exception:
                        pass
            except httpx.ReadError:
                last_error = "Read error"
            except asyncio.TimeoutError:
                last_error = "Timeout"
            except Exception as e:
                last_error = str(e)[:100]

            if attempt < max_retries:
                delay = 2 ** attempt + random.uniform(0, 1)
                await asyncio.sleep(delay)

    return 0, b"", last_error


def resilient_fetch_sync(
    url: str,
    timeout: float = 30.0,
    max_retries: int = 3,
    headers: dict | None = None,
) -> tuple[int, bytes]:
    """Synchronous version for use in non-async contexts (wt_bootstrap)."""
    import urllib.request
    import ssl

    last_error = b""
    url_to_try = url
    mirror_url = rewrite_url(url)

    ctx = ssl.create_default_context()

    for attempt in range(max_retries + 1):
        for try_url in ([url_to_try, mirror_url] if mirror_url != url_to_try else [url_to_try]):
            try:
                req = urllib.request.Request(try_url, headers=headers or {
                    "User-Agent": "LivingTree/2.1",
                })
                # Apply proxy if configured
                proxy = _get_proxy()
                if proxy:
                    req.set_proxy(proxy, "http")
                    req.set_proxy(proxy, "https")

                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    return resp.status, resp.read()

            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}".encode()
            except urllib.error.URLError as e:
                last_error = str(e.reason).encode()
            except Exception as e:
                last_error = str(e)[:200].encode()

            if attempt < max_retries:
                time.sleep(2 ** attempt + random.uniform(0, 1))

    return 0, last_error


# ═══ Subprocess runner with mirror env ═══

def run_with_mirrors(cmd: list[str], cwd: str | None = None,
                     timeout: int = 300, shell: bool = False) -> tuple[int, str, str]:
    """Run a command with mirror environment variables.

    Returns (returncode, stdout, stderr).
    """
    env = get_mirror_env()
    try:
        if shell:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout, env=env, cwd=cwd, shell=True)
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout, env=env, cwd=cwd)
        return proc.returncode, proc.stdout.strip()[:8000], proc.stderr.strip()[:4000]
    except subprocess.TimeoutExpired:
        return -1, "", "Timed out"
    except Exception as e:
        return -1, "", str(e)[:200]


# ═══ Decorator for auto-retry with backoff ═══

def with_resilience(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator: retry a function with exponential backoff on network errors.

    Detects ConnectionError, TimeoutError, OSError (network-related).
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (ConnectionError, TimeoutError, OSError, asyncio.TimeoutError) as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                        logger.debug(f"Retry {attempt + 1}/{max_retries} in {delay:.1f}s: {e}")
                        await asyncio.sleep(delay)
                except Exception:
                    raise
            raise last_exc or RuntimeError("Max retries exceeded")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, TimeoutError, OSError) as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                        logger.debug(f"Retry {attempt + 1}/{max_retries} in {delay:.1f}s: {e}")
                        time.sleep(delay)
                except Exception:
                    raise
            raise last_exc or RuntimeError("Max retries exceeded")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
