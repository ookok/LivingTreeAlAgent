"""
Web 工具
"""

import json
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

from ..registry import ToolRegistry


def _web_fetch_handler(ctx: dict, url: str, timeout: int = 15,
                       extract_text: bool = True) -> str:
    if not url.startswith(("http://", "https://")):
        return f"无效的 URL: {url} (必须以 http:// 或 https:// 开头)"
    parsed = urlparse(url)
    if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return f"不允许访问本地地址: {url}"
    try:
        req = Request(url, headers={
            "User-Agent": "LivingTree/2.0",
            "Accept": "text/html,text/plain,*/*",
        })
        with urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            status = resp.status
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                text = raw.decode("latin-1", errors="replace")
    except HTTPError as e:
        return f"HTTP {e.code}: {e.reason} ({url})"
    except URLError as e:
        return f"请求失败: {e.reason} ({url})"
    except Exception as e:
        return f"抓取失败: {e}"

    result = {
        "url": url,
        "status": status,
        "content_type": content_type,
        "size": len(raw),
    }

    if extract_text and "text/html" in content_type:
        text = _strip_html(text)
    result["text"] = text[:8000]
    if len(text) > 8000:
        result["truncated"] = True
        result["text"] += f"\n... (内容被截断，共 {len(text)} 字符)"

    return json.dumps(result, ensure_ascii=False, indent=2)


HTML_TAG_RE = __import__("re").compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    text = HTML_TAG_RE.sub(" ", html)
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


def register_web_tools():
    ToolRegistry.register(
        "web_fetch", "抓取网页内容并提取文本",
        {"type": "object", "properties": {
            "url": {"type": "string", "description": "目标 URL"},
            "timeout": {"type": "integer", "description": "超时秒数，默认15"},
            "extract_text": {"type": "boolean", "description": "是否从 HTML 提取纯文本，默认true"},
        }, "required": ["url"]},
        _web_fetch_handler, "web"
    )
