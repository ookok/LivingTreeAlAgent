"""Baidu Map (百度地图) service integration — server-side only.

API Keys stored in encrypted vault.

Services:
- Geocoding (address → coordinates)
- Reverse geocoding (coordinates → address)
- Place search (POI search with region filter)
- Static map images
- IP location

Reference: https://lbsyun.baidu.com/
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from typing import Any, Optional
from urllib.parse import quote


def _get_key() -> str:
    key = os.environ.get("LT_BAIDU_MAP_KEY", "")
    if key:
        return key
    try:
        from ..config.secrets import get_secret_vault
        vault_key = get_secret_vault().get("baidu_map_key", "")
        if vault_key:
            return vault_key
    except Exception:
        pass
    return ""


def geocode(address: str, city: str = "") -> dict[str, Any]:
    """Convert address to coordinates via Baidu Map geocoding API.

    Returns: {"address": ..., "found": bool, "lat": float, "lng": float, ...}
    """
    key = _get_key()
    if not key:
        return {"address": address, "found": False, "error": "Baidu Map key not configured"}
    params = f"address={quote(address)}&output=json&ak={key}&ret_coordtype=gcj02ll"
    if city:
        params += f"&city={quote(city)}"
    url = f"https://api.map.baidu.com/geocoding/v3/?{params}"
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
            "lat": loc.get("lat", 0), "lng": loc.get("lng", 0),
            "precise": r.get("precise", 0), "confidence": r.get("confidence", 0),
            "level": r.get("level", ""),
        }
    return {"address": address, "found": False, "detail": data.get("message", "")}


def reverse_geocode(lat: float, lng: float) -> dict[str, Any]:
    """Convert coordinates to address via Baidu Map."""
    key = _get_key()
    if not key:
        return {"lat": lat, "lng": lng, "found": False, "error": "Baidu Map key not configured"}
    url = (f"https://api.map.baidu.com/reverse_geocoding/v3/?"
           f"location={lat},{lng}&output=json&ak={key}&extensions_poi=1&coordtype=gcj02ll")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"lat": lat, "lng": lng, "found": False, "error": str(e)}

    if data.get("status") == 0 and data.get("result"):
        r = data["result"]
        comp = r.get("addressComponent", {})
        return {
            "lat": lat, "lng": lng, "found": True,
            "address": r.get("formatted_address", ""),
            "business": r.get("business", ""),
            "province": comp.get("province", ""),
            "city": comp.get("city", ""),
            "district": comp.get("district", ""),
            "street": comp.get("street", ""),
            "adcode": r.get("cityCode", ""),
            "pois": [p.get("name", "") for p in r.get("pois", [])[:5]],
            "poiRegions": [p.get("name", "") for p in r.get("poiRegions", [])[:3]],
        }
    return {"lat": lat, "lng": lng, "found": False, "detail": data.get("message", "")}


def search_place(keyword: str, region: str = "", page_size: int = 10,
                 tag: str = "", scope: int = 1) -> dict[str, Any]:
    """Search for places/POIs via Baidu Map Place API.

    scope: 1=city, 2=nationwide
    """
    key = _get_key()
    if not key:
        return {"keyword": keyword, "found": False, "error": "Baidu Map key not configured"}
    params = f"query={quote(keyword)}&output=json&ak={key}&page_size={page_size}&scope={scope}"
    if region:
        params += f"&region={quote(region)}"
    if tag:
        params += f"&tag={quote(tag)}"
    url = f"https://api.map.baidu.com/place/v2/search?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"keyword": keyword, "found": False, "error": str(e)}

    if data.get("status") == 0 and data.get("results"):
        results = []
        for r in data["results"]:
            loc = r.get("location", {})
            detail_info = r.get("detail_info", {})
            results.append({
                "name": r.get("name", ""), "address": r.get("address", ""),
                "lat": loc.get("lat", 0), "lng": loc.get("lng", 0),
                "province": r.get("province", ""), "city": r.get("city", ""),
                "area": r.get("area", ""), "tel": r.get("telephone", ""),
                "uid": r.get("uid", ""),
                "tag": detail_info.get("tag", ""),
                "rating": detail_info.get("overall_rating", ""),
            })
        return {"keyword": keyword, "found": True, "count": data.get("total", 0), "results": results}
    return {"keyword": keyword, "found": False, "detail": data.get("message", "")}


def place_suggestion(query: str, region: str = "") -> dict[str, Any]:
    """Auto-complete / place suggestion via Baidu Map Suggestion API."""
    key = _get_key()
    if not key:
        return {"query": query, "found": False, "error": "Baidu Map key not configured"}
    params = f"query={quote(query)}&output=json&ak={key}"
    if region:
        params += f"&region={quote(region)}"
    url = f"https://api.map.baidu.com/place/v2/suggestion?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"query": query, "found": False, "error": str(e)}

    if data.get("status") == 0 and data.get("result"):
        results = []
        for r in data["result"]:
            loc = r.get("location", {})
            results.append({
                "name": r.get("name", ""), "city": r.get("city", ""),
                "district": r.get("district", ""),
                "lat": loc.get("lat", 0), "lng": loc.get("lng", 0),
                "uid": r.get("uid", ""),
            })
        return {"query": query, "found": True, "results": results}
    return {"query": query, "found": False, "detail": data.get("message", "")}


def static_map_url(lng: float, lat: float, zoom: int = 14,
                   width: int = 600, height: int = 400,
                   markers: Optional[list[tuple[float, float, str]]] = None) -> str:
    """Get a Baidu static map image URL (center lng,lat)."""
    key = _get_key()
    if not key:
        return ""
    url = (f"https://api.map.baidu.com/staticimage/v2?"
           f"center={lng},{lat}&width={width}&height={height}&zoom={zoom}&ak={key}")
    if markers:
        marker_str = "|".join(f"{m[1]},{m[0]}" for m in markers[:10])
        url += f"&markers={marker_str}&markerStyles=l,A,0xff0000"
    return url


def fetch_static_map(lng: float, lat: float, zoom: int = 14,
                     width: int = 600, height: int = 400) -> Optional[bytes]:
    """Fetch a Baidu static map PNG image."""
    url = static_map_url(lng, lat, zoom, width, height)
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception:
        return None


def static_map_display(lng: float, lat: float, zoom: int = 12,
                       width: int = 80, height: int = 40) -> str:
    """Generate a Unicode block-art map for terminal display."""
    lines = [f"  百度地图 | {lat:.4f}, {lng:.4f} | zoom={zoom}"]
    lines.append("  " + "─" * 58)

    n = 2 ** zoom
    tile_x = int((lng + 180) / 360 * n)
    tile_y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)

    for dy in range(-2, 3):
        row = ""
        for dx in range(-4, 5):
            tx, ty = tile_x + dx, tile_y + dy
            row += "█" if (tx + ty) % 3 != 0 else "░"
        lines.append(f"  {row}")

    static_url = static_map_url(lng, lat, zoom, 200, 200)
    lines.append(f"\n  瓦片中心: ({tile_x}, {tile_y}) | 静态图URL: {static_url or 'key未配置'}")
    return "\n".join(lines)


def map_url(lat: float, lng: float, zoom: int = 14) -> str:
    """Get a browser URL for the Baidu Map viewer."""
    return f"https://map.baidu.com/@{lng},{lat},{zoom}z"


def ip_location(ip: str = "") -> dict[str, Any]:
    """Get location info from IP address."""
    key = _get_key()
    if not key:
        return {"found": False, "error": "Baidu Map key not configured"}
    params = f"ak={key}&coor=gcj02ll"
    if ip:
        params += f"&ip={ip}"
    url = f"https://api.map.baidu.com/location/ip?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LivingTree/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"found": False, "error": str(e)}

    if data.get("status") == 0:
        content = data.get("content", {})
        point = content.get("point", {})
        addr_detail = content.get("address_detail", {})
        return {
            "found": True,
            "address": content.get("address", ""),
            "province": addr_detail.get("province", ""),
            "city": addr_detail.get("city", ""),
            "district": addr_detail.get("district", ""),
            "street": addr_detail.get("street", ""),
            "lat": point.get("y", 0), "lng": point.get("x", 0),
        }
    return {"found": False, "detail": data.get("message", "")}
