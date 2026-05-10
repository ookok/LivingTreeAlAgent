"""Video Search Engine — multi-source: Bilibili, YouTube, local files.

Searches video sources by keyword, returns structured results with
title, thumbnail, duration, and embed URL for inline playback.

Sources:
  1. Bilibili   — free API, no key required, largest Chinese video platform
  2. YouTube    — Invidious proxy (no API key needed) or direct API
  3. Local FS   — scans mounted directories via LocalFS bridge
"""

from __future__ import annotations

import asyncio
import hashlib
import json as _json
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode

import httpx
from loguru import logger

BILIBILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/wbi/search/all/v2"
BILIBILI_NAV_API = "https://api.bilibili.com/x/web-interface/nav"
BILIBILI_EMBED = "https://player.bilibili.com/player.html?bvid={bvid}&page=1&high_quality=1"
YOUTUBE_INVIDIOUS_LIST = [
    "https://vid.puffyan.us",
    "https://invidious.snopyta.org",
    "https://yewtu.be",
    "https://invidious.tiekoetter.com",
]
YOUTUBE_EMBED = "https://www.youtube.com/embed/{video_id}"
SCINET_PROXY_URL = "http://127.0.0.1:7890"
SEARCH_TIMEOUT = 10.0
MAX_RESULTS = 6


@dataclass
class VideoResult:
    title: str
    url: str
    embed_url: str = ""
    thumbnail: str = ""
    duration: str = ""
    source: str = ""          # "bilibili", "youtube", "local"
    play_count: str = ""
    author: str = ""
    description: str = ""
    score: float = 0.0


class VideoSearchEngine:
    """Multi-source video search."""

    def __init__(self):
        self._local_mounts: list[Path] = []
        self._scinet_available: Optional[bool] = None

    def set_local_mounts(self, paths: list[str]):
        self._local_mounts = [Path(p) for p in paths if Path(p).is_dir()]

    # ═══ Scinet-aware HTTP client ═══

    async def _scinet_probe(self) -> bool:
        """Check if Scinet proxy is running on localhost:7890."""
        if self._scinet_available is not None:
            return self._scinet_available
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{SCINET_PROXY_URL}/status")
                self._scinet_available = resp.status_code == 200
        except Exception:
            self._scinet_available = False
        if self._scinet_available:
            logger.info("Scinet proxy detected — YouTube will route through tunnel")
        return self._scinet_available

    def _client_for(self, needs_proxy: bool = False) -> httpx.AsyncClient:
        """Get httpx client, optionally routed through Scinet proxy."""
        if needs_proxy:
            return httpx.AsyncClient(
                timeout=SEARCH_TIMEOUT,
                proxy=SCINET_PROXY_URL,
            )
        return httpx.AsyncClient(timeout=SEARCH_TIMEOUT)

    # ═══ Search ═══

    async def search(self, keyword: str, source: str = "all", limit: int = MAX_RESULTS) -> list[VideoResult]:
        """Search videos across all configured sources."""
        if not keyword.strip():
            return []

        results: list[VideoResult] = []
        tasks = []

        if source in ("all", "bilibili"):
            tasks.append(self._search_bilibili(keyword))
        if source in ("all", "youtube"):
            tasks.append(self._search_youtube(keyword))
        if source in ("all", "local") and self._local_mounts:
            tasks.append(self._search_local(keyword))

        if not tasks:
            tasks.append(self._search_bilibili(keyword))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for r in gathered:
            if isinstance(r, list):
                results.extend(r)
            elif isinstance(r, Exception):
                logger.debug(f"Video search source error: {r}")

        results.sort(key=lambda v: v.score, reverse=True)
        return results[:limit]

    # ═══ Bilibili ═══

    def _mix_key(self, img_key: str, sub_key: str) -> str:
        """Bilibili WBI key mixing. See: social/sister/wbi/mix.rust"""
        raw = img_key + sub_key
        mapping = [
            46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
            27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
            37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
            22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 52, 44, 34,
        ]
        return "".join(raw[m] for m in mapping[:len(raw)] if m < len(raw))

    async def _get_wbi_keys(self) -> tuple[str, str]:
        """Fetch WBI img_key and sub_key from Bilibili nav API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(BILIBILI_NAV_API, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.bilibili.com",
                })
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    wbi = data.get("wbi_img", {})
                    img_url = wbi.get("img_url", "")
                    sub_url = wbi.get("sub_url", "")
                    img_key = img_url.split("/")[-1].split(".")[0] if img_url else ""
                    sub_key = sub_url.split("/")[-1].split(".")[0] if sub_url else ""
                    if img_key and sub_key:
                        return img_key, sub_key
        except Exception:
            pass
        return "", ""

    async def _sign_wbi(self, params: dict) -> dict:
        """Sign Bilibili WBI request."""
        img_key, sub_key = await self._get_wbi_keys()
        if not img_key or not sub_key:
            return params

        mixed_key = self._mix_key(img_key, sub_key)
        params["wts"] = int(time.time())
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        query = "&".join(f"{k}={v}" for k, v in sorted_params)
        sign = hashlib.md5((query + mixed_key).encode()).hexdigest()
        params["w_rid"] = sign
        return params

    async def _search_bilibili(self, keyword: str) -> list[VideoResult]:
        try:
            params = {"keyword": keyword, "search_type": "video"}
            params = await self._sign_wbi(params)

            async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
                resp = await client.get(
                    BILIBILI_SEARCH_API,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": "https://www.bilibili.com",
                    },
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                if data.get("code") != 0:
                    return []

                video_items = data.get("data", {}).get("result", [])
                results = []
                for item in video_items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("result_type") != "video":
                        continue
                    for v in item.get("data", [])[:4]:
                        if not isinstance(v, dict):
                            continue
                        bvid = v.get("bvid", "")
                        aid = v.get("aid", 0)
                        play = v.get("play", v.get("video_review", 0)) or 0
                        results.append(VideoResult(
                            title=v.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
                            url=f"https://www.bilibili.com/video/{bvid or f'av{aid}'}",
                            embed_url=BILIBILI_EMBED.format(bvid=bvid or str(aid)) if bvid else f"https://player.bilibili.com/player.html?aid={aid}&page=1",
                            thumbnail=v.get("pic", ""),
                            duration=v.get("duration", ""),
                            source="bilibili",
                            play_count=str(play),
                            author=v.get("author", ""),
                            description=v.get("description", "")[:200],
                            score=float(play) / 10000 + len(v.get("title", "")) / 50,
                        ))
                return results
        except Exception as e:
            logger.debug(f"Bilibili search: {e}")
            return []

    # ═══ YouTube (via Invidious) ═══

    async def _search_youtube(self, keyword: str) -> list[VideoResult]:
        use_proxy = await self._scinet_probe()
        for base_url in YOUTUBE_INVIDIOUS_LIST:
            try:
                url = f"{base_url}/api/v1/search"
                params = {"q": keyword, "type": "video", "sort": "relevance"}
                async with self._client_for(use_proxy) as client:
                    resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                items = data if isinstance(data, list) else data.get("items", data) if isinstance(data, dict) else []
                if isinstance(items, dict):
                    items = items.get("results", items.get("items", []))
                if not isinstance(items, list) or not items:
                    continue

                results = []
                for v in items[:4]:
                    if not isinstance(v, dict):
                        continue
                    vid = v.get("videoId", "")
                    thumbs = v.get("videoThumbnails", [])
                    thumb = thumbs[0]["url"] if thumbs else ""
                    results.append(VideoResult(
                        title=v.get("title", ""),
                        url=f"https://www.youtube.com/watch?v={vid}",
                        embed_url=YOUTUBE_EMBED.format(video_id=vid),
                        thumbnail=thumb,
                        duration=f"{v.get('lengthSeconds', 0) // 60}:{v.get('lengthSeconds', 0) % 60:02d}",
                        source="youtube",
                        play_count=str(v.get("viewCount", "")),
                        author=v.get("author", ""),
                        description=v.get("description", "")[:200],
                        score=float(v.get("viewCount", 0)) / 1000 + len(v.get("title", "")) / 50,
                    ))
                return results
            except Exception:
                continue
        return []

    # ═══ Local Files ═══

    async def _search_local(self, keyword: str) -> list[VideoResult]:
        results = []
        video_exts = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v"}
        kw_lower = keyword.lower()

        for mount in self._local_mounts:
            try:
                for f in list(mount.rglob("*"))[:200]:
                    if f.suffix.lower() in video_exts and kw_lower in f.stem.lower():
                        relative = str(f.relative_to(mount))
                        results.append(VideoResult(
                            title=f.stem.replace("_", " ").replace("-", " "),
                            url=f"/local-file?path={quote(str(f))}",
                            embed_url=f"/local-file?path={quote(str(f))}",
                            duration="",
                            source="local",
                            author="本地文件",
                            description=str(f.parent.relative_to(mount)),
                            score=1.0,
                        ))
            except Exception:
                pass
            if len(results) >= 4:
                break
        return results[:4]

    # ═══ Build HTML card ═══

    def build_card_html(self, video: VideoResult) -> str:
        """Generate an HTMX-enhanced video card HTML fragment."""
        dur = f'<span style="font-size:9px;color:var(--dim);margin-left:4px">{video.duration}</span>' if video.duration else ""
        plays = f'<span style="font-size:9px;color:var(--dim);margin-left:4px">{video.play_count} 播放</span>' if video.play_count else ""
        source_badge = {
            "bilibili": '<span style="background:#fb7299;color:#fff;font-size:8px;padding:1px 5px;border-radius:3px">B站</span>',
            "youtube": '<span style="background:#f00;color:#fff;font-size:8px;padding:1px 5px;border-radius:3px">YT</span>',
            "local": '<span style="background:var(--accent);color:var(--bg);font-size:8px;padding:1px 5px;border-radius:3px">本地</span>',
        }.get(video.source, "")

        thumb_html = f'<img src="{video.thumbnail}" style="width:120px;height:68px;object-fit:cover;border-radius:4px;flex-shrink:0" onerror="this.style.display=\'none\'">' if video.thumbnail else ""

        return f'''<div class="video-card" style="display:flex;gap:8px;padding:8px;margin:4px 0;border-radius:6px;background:var(--panel);cursor:pointer"
  onclick="playVideo(this, '{_escape_attr(video.embed_url)}', '{_escape_attr(video.title)}')">
  {thumb_html}
  <div style="flex:1;min-width:0">
    <div style="font-size:12px;font-weight:600;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">
      {_escape_html(video.title)}
    </div>
    <div style="font-size:10px;color:var(--dim);margin-top:4px">
      {source_badge} {_escape_html(video.author)}{dur}{plays}
    </div>
  </div>
</div>'''

    def build_player_html(self, embed_url: str, title: str) -> str:
        """Generate the inline video player HTML."""
        title_esc = _escape_html(title)
        src_esc = _escape_attr(embed_url)

        if "bilibili" in embed_url:
            return f'''<div class="video-player" style="position:relative;padding-bottom:56.25%;margin:8px 0;border-radius:8px;overflow:hidden;background:#000">
<iframe src="{src_esc}" scrolling="no" border="0" frameborder="0" framespacing="0" allowfullscreen="true"
 style="position:absolute;top:0;left:0;width:100%;height:100%"></iframe>
<div style="position:absolute;top:8px;right:8px">
 <button onclick="closePlayer(this)" style="background:rgba(0,0,0,.6);color:#fff;border:none;padding:4px 10px;border-radius:4px;font-size:12px;cursor:pointer">✕</button>
</div></div>'''

        if "youtube" in embed_url:
            return f'''<div class="video-player" style="position:relative;padding-bottom:56.25%;margin:8px 0;border-radius:8px;overflow:hidden;background:#000">
<iframe src="{src_esc}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen
 style="position:absolute;top:0;left:0;width:100%;height:100%"></iframe>
<div style="position:absolute;top:8px;right:8px">
 <button onclick="closePlayer(this)" style="background:rgba(0,0,0,.6);color:#fff;border:none;padding:4px 10px;border-radius:4px;font-size:12px;cursor:pointer">✕</button>
</div></div>'''

        return f'''<div class="video-player" style="margin:8px 0;padding:8px;border-radius:8px;background:var(--panel)">
<video src="{src_esc}" controls style="width:100%;max-height:400px;border-radius:4px" preload="metadata"></video>
<div style="margin-top:4px;font-size:12px;color:var(--accent)">{title_esc}</div>
<div style="margin-top:4px">
 <button onclick="closePlayer(this)" style="background:var(--panel);border:1px solid var(--border);color:var(--dim);padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer">关闭</button>
</div></div>'''


# ═══ Helpers ═══

def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _escape_attr(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


_instance: Optional[VideoSearchEngine] = None


def get_video_search() -> VideoSearchEngine:
    global _instance
    if _instance is None:
        _instance = VideoSearchEngine()
    return _instance
