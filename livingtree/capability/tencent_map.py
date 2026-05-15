"""Tencent Map (腾讯地图) service integration.

API Key stored in encrypted vault.

Services:
- Geocoding (address → coordinates)
- Reverse geocoding (coordinates → address)
- Place search (POI search)
- Static map images
- Map tile display (terminal Unicode block fallback)

Reference: https://lbs.qq.com/
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from typing import Any, Optional
from urllib.parse import quote


def _get_key() -> str:
    # 1. Environment variable
    key = os.environ.get("LT_TENCENT_MAP_KEY", "")
    if key:
        return key
    # 2. Encrypted vault
    try:
        from ..config.secrets import get_secret_vault
        vault_key = get_secret_vault().get("tencent_map_key", "")
        if vault_key:
            return vault_key
    except Exception:
        pass
    return ""


def geocode(address: str, city: str = "") -> dict[str, Any]:
    """Convert address to coordinates via Tencent Map geocoding API.

    Returns: {"address": ..., "found": bool, "lat": float, "lon": float, ...}
    """
    key = _get_key()
    if not key:
        return {"address": address, "found": False, "error": "Tencent Map key not configured"}
    params = f"address={quote(address)}&key={key}"
    if city:
        params += f"&region={quote(city)}"
    url = f"https://apis.map.qq.com/ws/geocoder/v1/?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"address": address, "found": False, "error": str(e)}

    if data.get("status") == 0 and data.get("result"):
        r = data["result"]
        loc = r.get("location", {})
        return {
            "address": address, "found": True,
            "lat": loc.get("lat", 0), "lon": loc.get("lng", 0),
            "title": r.get("title", address),
            "province": r.get("address_components", {}).get("province", ""),
            "city": r.get("address_components", {}).get("city", ""),
            "district": r.get("address_components", {}).get("district", ""),
            "reliability": r.get("reliability", 0),
        }
    return {"address": address, "found": False, "detail": data.get("message", "")}


def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    """Convert coordinates to address via Tencent Map."""
    key = _get_key()
    if not key:
        return {"lat": lat, "lon": lon, "found": False, "error": "Tencent Map key not configured"}
    url = f"https://apis.map.qq.com/ws/geocoder/v1/?location={lat},{lon}&key={key}&get_poi=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"lat": lat, "lon": lon, "found": False, "error": str(e)}

    if data.get("status") == 0 and data.get("result"):
        r = data["result"]
        comp = r.get("address_component", {})
        ad = r.get("ad_info", {})
        pois = r.get("pois", [])
        return {
            "lat": lat, "lon": lon, "found": True,
            "address": r.get("address", ""),
            "formatted": r.get("formatted_addresses", {}).get("recommend", r.get("address", "")),
            "province": comp.get("province", ""),
            "city": comp.get("city", ""),
            "district": comp.get("district", ""),
            "adcode": ad.get("adcode", ""),
            "nearby_pois": [p.get("title", "") for p in pois[:5]],
        }
    return {"lat": lat, "lon": lon, "found": False, "detail": data.get("message", "")}


def search_place(keyword: str, region: str = "", page_size: int = 10) -> dict[str, Any]:
    """Search for places/POIs via Tencent Map."""
    key = _get_key()
    if not key:
        return {"keyword": keyword, "found": False, "error": "Tencent Map key not configured"}
    params = f"keyword={quote(keyword)}&key={key}&page_size={page_size}"
    if region:
        params += f"&boundary=region({quote(region)},0)"
    url = f"https://apis.map.qq.com/ws/place/v1/search?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"keyword": keyword, "found": False, "error": str(e)}

    if data.get("status") == 0 and data.get("data"):
        results = []
        for r in data["data"]:
            loc = r.get("location", {})
            results.append({
                "title": r.get("title", ""),
                "address": r.get("address", ""),
                "lat": loc.get("lat", 0), "lon": loc.get("lng", 0),
                "category": r.get("category", ""),
                "tel": r.get("tel", ""),
                "distance": r.get("_distance", 0),
            })
        return {"keyword": keyword, "found": True, "count": data.get("count", 0), "results": results}
    return {"keyword": keyword, "found": False, "detail": data.get("message", "")}


def static_map_url(lat: float, lon: float, zoom: int = 14,
                   width: int = 600, height: int = 400,
                   markers: Optional[list[tuple[float, float]]] = None) -> str:
    """Get a Tencent static map image URL."""
    key = _get_key()
    if not key:
        return ""
    center = f"{lat},{lon}"
    url = (f"https://apis.map.qq.com/ws/staticmap/v2/"
           f"?center={center}&zoom={zoom}&size={width}*{height}&key={key}")
    if markers:
        marker_str = "|".join(f"{m[0]},{m[1]}" for m in markers[:10])
        url += f"&markers=size:small|color:0xE8463A|{marker_str}"
    return url


def fetch_static_map(lat: float, lon: float, zoom: int = 14,
                     width: int = 600, height: int = 400) -> Optional[bytes]:
    """Fetch a static map PNG image."""
    url = static_map_url(lat, lon, zoom, width, height)
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception:
        return None


def static_map_display(lat: float, lon: float, zoom: int = 12,
                       width: int = 80, height: int = 40) -> str:
    """Generate a Unicode block-art map for terminal display.

    Uses simple coordinate grid since Tencent static maps are image-based.
    """
    lines = [f"  腾讯地图 | {lat:.4f}, {lon:.4f} | zoom={zoom}"]
    lines.append("  " + "─" * 58)

    # Tile grid approximation
    n = 2 ** zoom
    tile_x = int((lon + 180) / 360 * n)
    tile_y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)

    # Simplified terminal grid
    for dy in range(-2, 3):
        row = ""
        for dx in range(-4, 5):
            tx, ty = tile_x + dx, tile_y + dy
            # Simple ASCII art to represent land/water
            row += "█" if (tx + ty) % 3 != 0 else "░"
        lines.append(f"  {row}")

    lines.append(f"\n  瓦片中心: ({tile_x}, {tile_y}) | 静态图URL: {static_map_url(lat, lon, zoom, 200, 200) or 'key未配置'}")
    return "\n".join(lines)


def map_url(lat: float, lon: float, zoom: int = 14) -> str:
    """Get a browser URL for the Tencent Map viewer."""
    return f"https://map.qq.com/?lat={lat}&lng={lon}&zoom={zoom}"
