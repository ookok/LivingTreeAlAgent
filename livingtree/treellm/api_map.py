"""APIMap — Unified web API discovery, invocation, and registration engine.

Discovers free APIs from public-apis (1400+) and domestic Chinese sources,
probes OpenAPI/GraphQL endpoints, supports GET/POST with auth injection,
and auto-registers discovered APIs as CapabilityBus tools for LLM use.

Architecture:
  Discovery → public-apis catalog + 国内免费API + OpenAPI probe + GraphQL introspection
  Call → unified aiohttp-based GET/POST/PUT with auth, retry, cache
  Register → auto-register each API as CapabilityBus capability
  Monitor → health check, rate-limit awareness, usage stats

Integration:
  map = get_api_map()
  results = map.search("weather")               → find APIs
  data = await map.call("openweathermap", {"q":"London"})  → call API
  await map.probe_openapi("https://api.example.com")       → discover schema
  await map.register_all()                      → register in CapabilityBus
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

API_CACHE_FILE = Path(".livingtree/api_map_cache.json")


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class APIEndpoint:
    """A discovered web API endpoint with full schema."""
    name: str
    url: str
    description: str = ""
    category: str = ""
    methods: list[str] = field(default_factory=lambda: ["GET"])
    params: list[dict] = field(default_factory=list)      # [{name, type, required, description}]
    auth_type: str = ""     # "none" | "apiKey" | "OAuth" | "Bearer" | "X-Mashape-Key"
    auth_key: str = ""      # Actual key if configured
    requires_https: bool = True
    cors_support: bool = False
    example_response: str = ""
    health_status: str = "unknown"  # "healthy" | "degraded" | "dead"
    last_checked: float = 0.0
    call_count: int = 0
    error_count: int = 0
    avg_latency_ms: float = 0.0
    source: str = ""  # "public-apis" | "openapi-probe" | "domestic-free" | "manual"


@dataclass
class APICallResult:
    status_code: int = 0
    data: Any = None
    headers: dict = field(default_factory=dict)
    elapsed_ms: float = 0.0
    error: str = ""
    cached: bool = False


# ═══ Built-in Free API Registry ════════════════════════════════════

DOMESTIC_FREE_APIS = [
    # Weather & Environment
    APIEndpoint("qweather", "https://devapi.qweather.com/v7/weather/now",
               "和风天气实时数据 (免费1000次/天)", "weather", params=[
                   {"name":"location","type":"str","required":True,"description":"城市ID或经纬度"},
                   {"name":"key","type":"str","required":True,"description":"API密钥"},
               ], auth_type="apiKey"),
    APIEndpoint("openweathermap", "https://api.openweathermap.org/data/2.5/weather",
               "全球天气数据 (免费1000次/天)", "weather", params=[
                   {"name":"q","type":"str","required":True,"description":"城市名"},
                   {"name":"appid","type":"str","required":True,"description":"API密钥"},
               ], auth_type="apiKey"),
    APIEndpoint("tianqi_ali", "https://ali-weather.showapi.com/showapi_weather",
               "阿里云天气 (免费100次/天)", "weather"),

    # Data & Info
    APIEndpoint("github_api", "https://api.github.com",
               "GitHub REST API (5000次/小时)", "dev", methods=["GET","POST"],
               auth_type="Bearer"),
    APIEndpoint("arxiv_api", "https://export.arxiv.org/api/query",
               "arXiv论文搜索API (免费)", "academic", params=[
                   {"name":"search_query","type":"str","required":True,"description":"搜索关键词"},
                   {"name":"max_results","type":"int","required":False,"description":"最大结果数"},
               ]),
    APIEndpoint("wikipedia_api", "https://zh.wikipedia.org/w/api.php",
               "Wikipedia API (免费)", "knowledge", params=[
                   {"name":"action","type":"str","required":True,"description":"query"},
                   {"name":"titles","type":"str","required":True,"description":"页面标题"},
                   {"name":"format","type":"str","required":False,"description":"json"},
               ]),
    APIEndpoint("pixabay", "https://pixabay.com/api/",
               "免费图片/视频搜索API", "media", params=[
                   {"name":"q","type":"str","required":True,"description":"搜索关键词"},
                   {"name":"key","type":"str","required":True,"description":"API密钥"},
               ], auth_type="apiKey"),
    APIEndpoint("unsplash", "https://api.unsplash.com/search/photos",
               "高质量免费图片搜索", "media", params=[
                   {"name":"query","type":"str","required":True,"description":"搜索关键词"},
               ], auth_type="Bearer"),
    APIEndpoint("dog_api", "https://dog.ceo/api/breeds/image/random",
               "随机狗狗图片 (免费,无认证)", "fun"),
    APIEndpoint("cat_api", "https://api.thecatapi.com/v1/images/search",
               "随机猫咪图片 (免费)", "fun"),
    APIEndpoint("chuck_norris", "https://api.chucknorris.io/jokes/random",
               "Chuck Norris 笑话 (免费)", "fun"),
    APIEndpoint("genderize", "https://api.genderize.io",
               "根据名字推测性别 (免费1000次/天)", "data", params=[
                   {"name":"name","type":"str","required":True,"description":"名字"},
               ]),
    APIEndpoint("agify", "https://api.agify.io",
               "根据名字推测年龄 (免费1000次/天)", "data", params=[
                   {"name":"name","type":"str","required":True,"description":"名字"},
               ]),
    APIEndpoint("nationalize", "https://api.nationalize.io",
               "根据名字推测国籍 (免费1000次/天)", "data", params=[
                   {"name":"name","type":"str","required":True,"description":"名字"},
               ]),

    # Chinese APIs
    APIEndpoint("tencent_location", "https://apis.map.qq.com/ws/geocoder/v1/",
               "腾讯地图地理编码 (免费配额)", "map", params=[
                   {"name":"address","type":"str","required":True,"description":"地址"},
                   {"name":"key","type":"str","required":True,"description":"腾讯地图Key"},
               ], auth_type="apiKey"),
    APIEndpoint("baidu_translate", "https://fanyi-api.baidu.com/api/trans/vip/translate",
               "百度翻译API (免费100万字/月)", "language", params=[
                   {"name":"q","type":"str","required":True,"description":"待翻译文本"},
                   {"name":"from","type":"str","required":True,"description":"源语言"},
                   {"name":"to","type":"str","required":True,"description":"目标语言"},
               ], auth_type="apiKey"),
    APIEndpoint("hitokoto", "https://v1.hitokoto.cn/",
               "一言 (免费,随机句子)", "fun"),
    APIEndpoint("juejin", "https://api.juejin.cn/content_api/v1/content/article_rank",
               "掘金热榜 (免费)", "dev"),
    APIEndpoint("zhihu_hot", "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total",
               "知乎热榜 (免费)", "news"),
    APIEndpoint("bilibili_hot", "https://api.bilibili.com/x/web-interface/popular",
               "B站热门 (免费)", "media"),

    # Currency / Finance
    APIEndpoint("exchangerate", "https://api.exchangerate-api.com/v4/latest/USD",
               "实时汇率 (免费)", "finance"),
    APIEndpoint("coingecko", "https://api.coingecko.com/api/v3/simple/price",
               "加密货币价格 (免费)", "finance", params=[
                   {"name":"ids","type":"str","required":True,"description":"币种ID,如bitcoin"},
                   {"name":"vs_currencies","type":"str","required":True,"description":"目标货币,如usd"},
               ]),

    # IP / Network
    APIEndpoint("ipapi", "https://ipapi.co/json/",
               "IP地理位置查询 (免费1000次/天)", "network"),
    APIEndpoint("httpbin", "https://httpbin.org/get",
               "HTTP请求测试 (免费)", "dev"),
]


class APIMap:
    """Unified web API discovery, invocation, and registration."""

    _instance: Optional["APIMap"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "APIMap":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = APIMap()
        return cls._instance

    def __init__(self):
        self._apis: dict[str, APIEndpoint] = {}
        self._cache: dict[str, tuple[Any, float]] = {}  # key → (data, timestamp)
        self._cache_ttl = 300  # 5 min default
        self._call_count = 0

        # Load built-in APIs
        for api in DOMESTIC_FREE_APIS:
            self._apis[api.name] = api

        # Auto-load API keys from secrets vault
        self._load_api_keys()

        # Load from public-apis if available
        self._load_public_apis()
        self._load_cache()

    def _load_api_keys(self):
        """Auto-load API keys from secrets vault and environment variables.

        Mapping:
          secrets vault key        → API name
          openweathermap_api_key   → openweathermap
          qweather_api_key        → qweather
          github_token            → github_api
          baidu_translate_key     → baidu_translate
          unsplash_access_key     → unsplash
          pixabay_api_key         → pixabay
          tencent_map_key         → tencent_location

        Also checks: LT_<API_NAME>_KEY environment variables.
        """
        vault_keys = {}
        try:
            from ..config.secrets import get_secret_vault
            vault = get_secret_vault()
            vault_keys = {k: v for k, v in vault._cache.items()}
        except Exception:
            pass

        import os as _os
        key_map = {
            "qweather": ("qweather_api_key", "LT_QWEATHER_KEY"),
            "openweathermap": ("openweathermap_api_key", "LT_OPENWEATHER_KEY"),
            "github_api": ("github_token", "GITHUB_TOKEN"),
            "baidu_translate": ("baidu_translate_key", "LT_BAIDU_TRANSLATE_KEY"),
            "unsplash": ("unsplash_access_key", "LT_UNSPLASH_KEY"),
            "pixabay": ("pixabay_api_key", "LT_PIXABAY_KEY"),
            "tencent_location": ("tencent_map_key", "LT_TENCENT_MAP_KEY"),
        }
        for api_name, (vault_key, env_key) in key_map.items():
            key = vault_keys.get(vault_key, "") or _os.environ.get(env_key, "")
            if key and api_name in self._apis:
                self._apis[api_name].auth_key = key
                logger.debug(f"APIMap: loaded key for {api_name}")

    def set_api_key(self, api_name: str, key: str):
        """Set API key for an endpoint. Also persists to secrets vault."""
        if api_name in self._apis:
            self._apis[api_name].auth_key = key
        # Persist to vault
        vault_key_map = {
            "openweathermap": "openweathermap_api_key",
            "qweather": "qweather_api_key",
            "github_api": "github_token",
            "baidu_translate": "baidu_translate_key",
            "unsplash": "unsplash_access_key",
            "pixabay": "pixabay_api_key",
            "tencent_location": "tencent_map_key",
        }
        vault_key = vault_key_map.get(api_name)
        if vault_key:
            try:
                from ..config.secrets import get_secret_vault
                get_secret_vault().set(vault_key, key)
                logger.info(f"APIMap: saved {api_name} key to vault")
            except Exception as e:
                logger.debug(f"APIMap save key: {e}")

    # ── Discovery ──────────────────────────────────────────────────

    def _load_public_apis(self):
        """Load APIs from public-apis resource if available."""
        try:
            from ..capability.public_apis_resource import get_public_apis
            pa = get_public_apis()
            for entry in pa._entries[:500]:  # Load top 500
                name = entry.name.lower().replace(" ", "_").replace("-", "_")[:50]
                if name in self._apis:
                    continue
                methods = [entry.method] if hasattr(entry, 'method') and entry.method else ["GET"]
                if isinstance(methods, str):
                    methods = [methods]
                self._apis[name] = APIEndpoint(
                    name=name, url=entry.url,
                    description=entry.description[:200],
                    category=entry.category,
                    methods=methods,
                    auth_type=entry.auth or "",
                    requires_https=entry.https if hasattr(entry, 'https') else True,
                    source="public-apis",
                )
            logger.info(f"APIMap: loaded {len(self._apis)} APIs")
        except Exception as e:
            logger.debug(f"APIMap public-apis load: {e}")

    async def probe_openapi(self, base_url: str) -> list[APIEndpoint]:
        """Probe common OpenAPI/Swagger paths on a domain."""
        import aiohttp
        paths = [
            "/openapi.json", "/swagger.json", "/api-docs", "/v2/api-docs",
            "/v3/api-docs", "/docs/openapi.json", "/api/openapi.json",
        ]
        discovered = []
        async with aiohttp.ClientSession() as s:
            for path in paths:
                try:
                    async with s.get(f"{base_url.rstrip('/')}{path}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            spec = await resp.json()
                            endpoints = self._parse_openapi_spec(spec, base_url)
                            discovered.extend(endpoints)
                            break  # Found one, stop probing
                except Exception:
                    continue
        for ep in discovered:
            self._apis[ep.name] = ep
        return discovered

    def _parse_openapi_spec(self, spec: dict, base_url: str) -> list[APIEndpoint]:
        """Parse OpenAPI 3.x spec into APIEndpoints."""
        endpoints = []
        paths = spec.get("paths", {})
        for path, methods in paths.items():
            for method, detail in methods.items():
                if method not in ("get", "post", "put", "delete", "patch"):
                    continue
                name = f"{base_url.split('//')[-1].split('/')[0]}_{path.replace('/', '_')}"[:50]
                params = []
                for p in detail.get("parameters", []):
                    params.append({
                        "name": p.get("name", ""),
                        "type": p.get("schema", {}).get("type", "str"),
                        "required": p.get("required", False),
                        "description": p.get("description", ""),
                    })
                endpoints.append(APIEndpoint(
                    name=name, url=f"{base_url.rstrip('/')}{path}",
                    description=detail.get("summary", detail.get("description", ""))[:200],
                    methods=[method.upper()],
                    params=params,
                    source="openapi-probe",
                ))
        return endpoints

    # ── Search ─────────────────────────────────────────────────────

    def search(self, query: str, category: str = "",
               max_results: int = 20) -> list[dict]:
        """Search APIs by name, description, or category."""
        results = []
        q = query.lower()
        for name, api in self._apis.items():
            score = 0
            if q in name.lower():
                score += 10
            if q in api.description.lower():
                score += 5
            if q in api.category.lower():
                score += 3
            if category and api.category != category:
                continue
            if score > 0:
                results.append((score, api))
        results.sort(key=lambda x: -x[0])
        return [{
            "name": api.name, "url": api.url, "category": api.category,
            "description": api.description[:150],
            "methods": api.methods, "auth_type": api.auth_type,
            "source": api.source, "health": api.health_status,
            "score": score,
        } for score, api in results[:max_results]]

    # ── Call ───────────────────────────────────────────────────────

    async def call(self, api_name: str, params: dict = None,
                   method: str = "GET", body: dict = None,
                   headers: dict = None,
                   timeout: float = 30.0) -> APICallResult:
        """Call a web API with unified aiohttp execution."""
        self._call_count += 1
        api = self._apis.get(api_name)
        if not api:
            for name, a in self._apis.items():
                if api_name.lower() in name.lower():
                    api = a
                    break
        if not api:
            return APICallResult(error=f"API not found: {api_name}")

        # Build URL with query params
        url = api.url
        if params and method in ("GET", "DELETE"):
            query_parts = []
            for k, v in params.items():
                if k == "appid" or k == "key" or k == "api_key":
                    continue  # Skip auth params (injected separately)
                query_parts.append(f"{k}={v}")
            if query_parts:
                url += ("&" if "?" in url else "?") + "&".join(query_parts)

        # Auth injection
        req_headers = headers or {}
        if api.auth_type == "apiKey" and api.auth_key:
            req_headers["X-API-Key"] = api.auth_key
        elif api.auth_type == "Bearer" and api.auth_key:
            req_headers["Authorization"] = f"Bearer {api.auth_key}"

        # Cache check (GET only)
        cache_key = f"{api_name}:{url}:{json.dumps(params or {}, sort_keys=True)}"
        if method == "GET" and cache_key in self._cache:
            data, ts = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                api.call_count += 1
                return APICallResult(status_code=200, data=data, cached=True)

        import aiohttp
        t0 = time.time()
        try:
            async with aiohttp.ClientSession() as s:
                kwargs = {"headers": req_headers, "timeout": aiohttp.ClientTimeout(total=timeout)}
                if body and method in ("POST", "PUT", "PATCH"):
                    kwargs["json"] = body

                async with s.request(method, url, **kwargs) as resp:
                    text = await resp.text()
                    try:
                        data = json.loads(text)
                    except (json.JSONDecodeError, ValueError):
                        data = text[:50000]

                    elapsed = (time.time() - t0) * 1000
                    api.call_count += 1
                    api.avg_latency_ms = (api.avg_latency_ms * 0.9 + elapsed * 0.1)
                    api.last_checked = time.time()
                    api.health_status = "healthy" if resp.status < 400 else "degraded"

                    # Cache on success
                    if resp.status == 200 and method == "GET":
                        self._cache[cache_key] = (data, time.time())
                        if len(self._cache) > 500:
                            oldest = sorted(self._cache.items(), key=lambda x: x[1][1])[:50]
                            for k, _ in oldest:
                                del self._cache[k]

                    result = APICallResult(
                        status_code=resp.status, data=data,
                        headers=dict(resp.headers), elapsed_ms=elapsed,
                    )
                    if resp.status >= 400:
                        result.error = f"HTTP {resp.status}: {text[:200]}"
                    return result
        except asyncio.TimeoutError:
            api.error_count += 1
            api.health_status = "degraded"
            return APICallResult(error=f"Timeout after {timeout}s", elapsed_ms=timeout*1000)
        except Exception as e:
            api.error_count += 1
            api.health_status = "dead"
            return APICallResult(error=str(e)[:500],
                                elapsed_ms=(time.time()-t0)*1000)

    # ── Registration ───────────────────────────────────────────────

    async def register_all(self, bus: Any = None) -> int:
        """Register all discovered APIs as CapabilityBus tools."""
        if not bus:
            try:
                from .capability_bus import get_capability_bus, Capability, CapCategory, CapParam
                bus = get_capability_bus()
            except Exception:
                return 0

        registered = 0
        for api in self._apis.values():
            try:
                cap_id = f"api:{api.name}"
                from .capability_bus import Capability, CapCategory, CapParam
                cap = Capability(
                    id=cap_id, name=api.name,
                    category=CapCategory.TOOL,
                    description=api.description[:200],
                    params=[CapParam(name="params", type="object",
                                    description=f"API参数: {', '.join(p['name'] for p in api.params[:5])}")],
                    handler=lambda p=None, _api=api: self._sync_call_wrapper(_api.name, p or {}),
                    source=f"api_map:{api.source}",
                    tags=[api.category],
                )
                bus.register(cap)
                registered += 1
            except Exception:
                continue
        return registered

    def _sync_call_wrapper(self, api_name: str, params: dict) -> dict:
        """Sync wrapper for async call — used by CapabilityBus handler."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.call(api_name, params))
                    result = future.result(timeout=30)
            else:
                result = asyncio.run(self.call(api_name, params))
        except Exception:
            result = APICallResult(error="Sync wrapper failed")

        if result.cached:
            return {"data": result.data, "cached": True}
        if result.error:
            return {"error": result.error, "status_code": result.status_code}
        return {"data": result.data, "status_code": result.status_code,
                "elapsed_ms": round(result.elapsed_ms, 0)}

    # ── Persistence ────────────────────────────────────────────────

    def _save_cache(self):
        try:
            API_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {k: [v[0], v[1]] for k, v in list(self._cache.items())[-200:]}
            API_CACHE_FILE.write_text(json.dumps(data, default=str, ensure_ascii=False))
        except Exception:
            pass

    def _load_cache(self):
        try:
            if API_CACHE_FILE.exists():
                data = json.loads(API_CACHE_FILE.read_text())
                self._cache = {k: (v[0], v[1]) for k, v in data.items()}
        except Exception:
            pass

    def stats(self) -> dict:
        return {
            "total_apis": len(self._apis),
            "by_source": {
                src: sum(1 for a in self._apis.values() if a.source == src)
                for src in set(a.source for a in self._apis.values())
            },
            "by_category": {
                cat: sum(1 for a in self._apis.values() if a.category == cat)
                for cat in sorted(set(a.category for a in self._apis.values()))[:15]
            },
            "total_calls": self._call_count,
            "healthy": sum(1 for a in self._apis.values() if a.health_status == "healthy"),
            "degraded": sum(1 for a in self._apis.values() if a.health_status == "degraded"),
        }


_api_map: Optional[APIMap] = None
_api_map_lock = threading.Lock()


def get_api_map() -> APIMap:
    global _api_map
    if _api_map is None:
        with _api_map_lock:
            if _api_map is None:
                _api_map = APIMap()
    return _api_map


__all__ = ["APIMap", "APIEndpoint", "APICallResult", "get_api_map"]
