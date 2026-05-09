"""Open-Meteo Weather Client — free, open-source weather & climate data.

Open-Meteo (https://open-meteo.com):
  - Free for non-commercial use, no API key required
  - 16-day hourly forecast at 1.5km resolution
  - 80-year historical weather archive (ERA5 reanalysis)
  - Data from NOAA GFS, ECMWF IFS, DWD ICON, etc.
  - Air quality, marine, and climate indices available

LivingTree integration points:
  1. 环评报告 (EIA): wind/pollution dispersion modeling context
  2. KnowledgeBase: historical weather as factual retrieval context
  3. LifeEngine: real-world environmental context for grounded decisions
  4. ResearchTeam: weather data as analysis input for Data Agent
  5. SpatialAwareness: weather layer on top of spatial topology

API endpoints (all free, no key):
  Forecast:    https://api.open-meteo.com/v1/forecast
  Historical:  https://archive-api.open-meteo.com/v1/archive
  AirQuality:  https://air-quality-api.open-meteo.com/v1/air-quality
  Geocoding:   https://geocoding-api.open-meteo.com/v1/search

Rate limits: 10,000 calls/day, 600 calls/min (generous for non-commercial)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


# ═══ Data Types ═══


@dataclass
class WeatherCurrent:
    """Current weather snapshot at a location."""
    latitude: float
    longitude: float
    timestamp: str
    temperature: float          # °C at 2m
    humidity: float             # % relative humidity
    wind_speed: float           # km/h at 10m
    wind_direction: float       # degrees (0=N, 90=E)
    precipitation: float        # mm
    pressure: float             # hPa
    cloud_cover: float          # %
    weather_code: int           # WMO weather code
    description: str = ""

    def to_context(self) -> str:
        return (
            f"当前天气: {self.temperature:.1f}°C, "
            f"湿度{self.humidity:.0f}%, "
            f"风速{self.wind_speed:.1f}km/h {self._wind_dir_name()}, "
            f"降水{self.precipitation:.1f}mm, "
            f"气压{self.pressure:.0f}hPa, "
            f"{self.description}"
        )

    def _wind_dir_name(self) -> str:
        dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        idx = round(self.wind_direction / 45) % 8
        return dirs[idx]


@dataclass  
class WeatherHourly:
    """Hourly weather forecast row."""
    time: str
    temperature: float
    humidity: float
    wind_speed: float
    wind_direction: float
    precipitation: float
    pressure: float
    cloud_cover: float
    weather_code: int


@dataclass
class WeatherDaily:
    """Daily weather summary."""
    date: str
    temp_max: float
    temp_min: float
    precipitation_sum: float
    wind_speed_max: float
    sunrise: str = ""
    sunset: str = ""
    description: str = ""


@dataclass
class WeatherReport:
    """Complete weather report for a location + time range."""
    location: str                # Resolved location name
    latitude: float
    longitude: float
    current: WeatherCurrent | None = None
    hourly: list[WeatherHourly] = field(default_factory=list)
    daily: list[WeatherDaily] = field(default_factory=list)
    source: str = "open-meteo"
    fetched_at: str = ""
    cached: bool = False

    def summary(self, hours: int = 24) -> str:
        """Human-readable summary for LLM context injection."""
        parts = []
        if self.current:
            parts.append(self.current.to_context())
        if self.hourly:
            next_24h = self.hourly[:hours]
            avg_temp = sum(h.temperature for h in next_24h) / len(next_24h)
            total_precip = sum(h.precipitation for h in next_24h)
            max_wind = max(h.wind_speed for h in next_24h)
            parts.append(
                f"未来{hours}h: 均温{avg_temp:.1f}°C, "
                f"总降水{total_precip:.1f}mm, 最大风速{max_wind:.1f}km/h"
            )
        if self.daily:
            d = self.daily[0]
            parts.append(
                f"今日: {d.temp_min:.0f}~{d.temp_max:.0f}°C, "
                f"降水{d.precipitation_sum:.1f}mm, {d.description}"
            )
        return " | ".join(parts)

    def to_knowledge_doc(self) -> dict:
        """Convert to KnowledgeBase document format."""
        return {
            "title": f"weather:{self.location}:{self.fetched_at[:10]}",
            "content": self.summary(hours=48),
            "tags": ["weather", "environmental", "forecast"],
            "metadata": {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "fetched_at": self.fetched_at,
                "source": self.source,
                "has_current": self.current is not None,
                "hourly_hours": len(self.hourly),
                "daily_days": len(self.daily),
            },
        }


@dataclass 
class AirQualityData:
    """Air quality data for a location."""
    latitude: float
    longitude: float
    timestamp: str
    pm2_5: float = -1           # μg/m³
    pm10: float = -1
    no2: float = -1             # μg/m³  
    so2: float = -1             # μg/m³
    o3: float = -1              # μg/m³
    co: float = -1              # μg/m³
    european_aqi: float = -1     # 0-500+

    def to_context(self) -> str:
        parts = []
        if self.pm2_5 >= 0:
            parts.append(f"PM2.5: {self.pm2_5:.0f}μg/m³")
        if self.pm10 >= 0:
            parts.append(f"PM10: {self.pm10:.0f}μg/m³")
        if self.so2 >= 0:
            parts.append(f"SO₂: {self.so2:.0f}μg/m³")
        if self.no2 >= 0:
            parts.append(f"NO₂: {self.no2:.0f}μg/m³")
        return "空气质量: " + ", ".join(parts) if parts else ""


# ═══ WMO Weather Code Mapping ═══

WMO_CODES: dict[int, str] = {
    0: "晴天", 1: "大部晴朗", 2: "多云", 3: "阴天",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "小阵雨", 81: "阵雨", 82: "大阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷暴", 96: "雷暴+小冰雹", 99: "雷暴+大冰雹",
}


# ═══ Open-Meteo Client ═══


class OpenMeteoClient:
    """Free, no-key weather and climate data client.

    All endpoints are free for non-commercial use. No registration needed.
    Built-in disk cache to avoid redundant calls and respect rate limits.

    Usage:
        om = OpenMeteoClient()
        report = await om.get_forecast(39.9, 116.4, city="北京")
        history = await om.get_history(39.9, 116.4, days=365)
        aq = await om.get_air_quality(39.9, 116.4)
    """

    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
    AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

    # WMO codes that indicate precipitation
    RAIN_CODES = {51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99}
    SNOW_CODES = {71, 73, 75, 85, 86}

    def __init__(self, cache_dir: str = ".livingtree/weather_cache",
                 cache_ttl_minutes: int = 30):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = cache_ttl_minutes * 60  # seconds
        self._session = None
        self._call_count = 0
        self._last_call_time = 0.0
        self._min_interval = 0.1  # 100ms between calls (well within 600/min)

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    # ═══ Forecast ═══

    async def get_forecast(
        self, latitude: float, longitude: float,
        city: str = "", days: int = 7, hourly_vars: list[str] | None = None,
    ) -> WeatherReport:
        """Get current weather + multi-day hourly forecast.

        Args:
            latitude/longitude: Coordinates
            city: Location name for display
            days: Forecast days (1-16)
            hourly_vars: Extra hourly variables (default: standard set)

        Returns:
            WeatherReport with current + hourly + daily data
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,"
                       "wind_direction_10m,precipitation,pressure_msl,"
                       "cloud_cover,weather_code",
            "hourly": ",".join(hourly_vars or [
                "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                "wind_direction_10m", "precipitation", "pressure_msl",
                "cloud_cover", "weather_code",
            ]),
            "daily": "temperature_2m_max,temperature_2m_min,"
                     "precipitation_sum,wind_speed_10m_max,"
                     "sunrise,sunset,weather_code",
            "timezone": "auto",
            "forecast_days": min(days, 16),
        }

        data = await self._fetch(self.FORECAST_URL, params, cache_key=f"fc_{latitude}_{longitude}")
        return self._parse_forecast(data, latitude, longitude, city)

    # ═══ Historical ═══

    async def get_history(
        self, latitude: float, longitude: float,
        start_date: str | None = None, end_date: str | None = None,
        days: int = 30, city: str = "",
    ) -> WeatherReport:
        """Get historical weather data (up to 80 years).

        Args:
            latitude/longitude: Coordinates
            start_date/end_date: YYYY-MM-DD range
            days: If no dates given, go back N days from today

        Returns:
            WeatherReport with historical hourly + daily data
        """
        if not start_date:
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            start_date = start.strftime("%Y-%m-%d")
            end_date = end.strftime("%Y-%m-%d")

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,"
                      "wind_direction_10m,precipitation,pressure_msl,"
                      "cloud_cover,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,"
                     "precipitation_sum,wind_speed_10m_max,weather_code",
            "timezone": "auto",
        }

        cache_key = f"hist_{latitude}_{longitude}_{start_date}_{end_date}"
        data = await self._fetch(self.HISTORICAL_URL, params, cache_key=cache_key)
        return self._parse_forecast(data, latitude, longitude, city, is_history=True)

    # ═══ Air Quality ═══

    async def get_air_quality(
        self, latitude: float, longitude: float,
    ) -> AirQualityData:
        """Get current air quality data."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,"
                       "ozone,carbon_monoxide,european_aqi",
        }

        data = await self._fetch(
            self.AIR_QUALITY_URL, params,
            cache_key=f"aq_{latitude}_{longitude}")

        current = data.get("current", {})
        return AirQualityData(
            latitude=latitude, longitude=longitude,
            timestamp=current.get("time", ""),
            pm2_5=current.get("pm2_5", -1) or -1,
            pm10=current.get("pm10", -1) or -1,
            no2=current.get("nitrogen_dioxide", -1) or -1,
            so2=current.get("sulphur_dioxide", -1) or -1,
            o3=current.get("ozone", -1) or -1,
            co=current.get("carbon_monoxide", -1) or -1,
            european_aqi=current.get("european_aqi", -1) or -1,
        )

    # ═══ Geocoding ═══

    async def geocode(self, city_name: str, count: int = 3) -> list[dict]:
        """Resolve city name to coordinates."""
        params = {"name": city_name, "count": count, "language": "zh"}
        data = await self._fetch(
            self.GEOCODING_URL, params, cache_key=f"geo_{city_name}")
        results = data.get("results", [])
        return [
            {
                "name": r.get("name", city_name),
                "country": r.get("country", ""),
                "latitude": r.get("latitude", 0),
                "longitude": r.get("longitude", 0),
                "timezone": r.get("timezone", ""),
            }
            for r in results
        ]

    # ═══ Convenience Methods ═══

    async def get_for_city(
        self, city: str, days: int = 7,
    ) -> WeatherReport | None:
        """Get weather forecast for a named city."""
        geo = await self.geocode(city)
        if not geo:
            return None
        loc = geo[0]
        return await self.get_forecast(loc["latitude"], loc["longitude"], city=city, days=days)

    async def get_environmental_context(
        self, latitude: float, longitude: float, city: str = "",
    ) -> str:
        """Get a combined weather + air quality context string for EIA reports."""
        weather = await self.get_forecast(latitude, longitude, city=city, days=7)
        aq = await self.get_air_quality(latitude, longitude)

        parts = [f"## 气象环境数据 ({city or f'{latitude},{longitude}'})"]
        parts.append(weather.summary(hours=72))
        parts.append(aq.to_context())

        # Wind rose summary for pollution modeling
        if weather.hourly:
            winds = weather.hourly[:72]
            avg_wind = sum(h.wind_speed for h in winds) / len(winds)
            # Dominant wind direction
            dir_counts = {}
            for h in winds:
                octant = round(h.wind_direction / 45) % 8
                dir_counts[octant] = dir_counts.get(octant, 0) + 1
            dominant = max(dir_counts, key=dir_counts.get)
            dir_names = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
            parts.append(f"主导风向: {dir_names[dominant]}, 平均风速: {avg_wind:.1f}km/h")

        return "\n".join(parts)

    # ═══ Core Fetch with Caching ═══

    async def _fetch(
        self, url: str, params: dict, cache_key: str = "",
    ) -> dict:
        """Fetch JSON from API with disk cache + rate limiting."""
        # Check cache
        if cache_key:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        # Rate limit: ensure min interval between calls
        elapsed = time.time() - self._last_call_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)

        session = await self._get_session()
        try:
            async with session.get(url, params=params, timeout=15) as resp:
                self._last_call_time = time.time()
                self._call_count += 1
                data = await resp.json()

                # Cache result
                if cache_key and resp.status == 200:
                    self._cache_set(cache_key, data)

                return data
        except Exception as e:
            logger.warning(f"Open-Meteo fetch failed ({url}): {e}")
            # Return cached data even if expired, as fallback
            if cache_key:
                stale = self._cache_get(cache_key, ignore_ttl=True)
                if stale is not None:
                    return stale
            return {}

    # ═══ Cache Layer ═══

    def _cache_path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() else "_" for c in key)
        return self._cache_dir / f"{safe}.json"

    def _cache_get(self, key: str, ignore_ttl: bool = False) -> dict | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            ts = data.get("_cached_at", 0)
            if not ignore_ttl and (time.time() - ts) > self._cache_ttl:
                return None
            return data.get("_payload", {})
        except Exception:
            return None

    def _cache_set(self, key: str, payload: dict) -> None:
        data = {
            "_cached_at": time.time(),
            "_payload": payload,
        }
        path = self._cache_path(key)
        try:
            path.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    # ═══ Parsing ═══

    def _parse_forecast(
        self, data: dict, lat: float, lon: float, city: str,
        is_history: bool = False,
    ) -> WeatherReport:
        now = datetime.now(timezone.utc).isoformat()

        # Current
        current = None
        cur = data.get("current", {})
        if cur:
            current = WeatherCurrent(
                latitude=lat, longitude=lon,
                timestamp=cur.get("time", now),
                temperature=cur.get("temperature_2m", 0) or 0,
                humidity=cur.get("relative_humidity_2m", 0) or 0,
                wind_speed=cur.get("wind_speed_10m", 0) or 0,
                wind_direction=cur.get("wind_direction_10m", 0) or 0,
                precipitation=cur.get("precipitation", 0) or 0,
                pressure=cur.get("pressure_msl", 1013) or 1013,
                cloud_cover=cur.get("cloud_cover", 0) or 0,
                weather_code=cur.get("weather_code", 0) or 0,
                description=WMO_CODES.get(cur.get("weather_code", 0) or 0, "未知"),
            )

        # Hourly
        hourly_data = data.get("hourly", {})
        times = hourly_data.get("time", [])
        hourly = []
        for i, t in enumerate(times):
            hourly.append(WeatherHourly(
                time=t,
                temperature=hourly_data.get("temperature_2m", [])[i] if i < len(hourly_data.get("temperature_2m", [])) else 0,
                humidity=hourly_data.get("relative_humidity_2m", [])[i] if i < len(hourly_data.get("relative_humidity_2m", [])) else 0,
                wind_speed=hourly_data.get("wind_speed_10m", [])[i] if i < len(hourly_data.get("wind_speed_10m", [])) else 0,
                wind_direction=hourly_data.get("wind_direction_10m", [])[i] if i < len(hourly_data.get("wind_direction_10m", [])) else 0,
                precipitation=hourly_data.get("precipitation", [])[i] if i < len(hourly_data.get("precipitation", [])) else 0,
                pressure=hourly_data.get("pressure_msl", [])[i] if i < len(hourly_data.get("pressure_msl", [])) else 1013,
                cloud_cover=hourly_data.get("cloud_cover", [])[i] if i < len(hourly_data.get("cloud_cover", [])) else 0,
                weather_code=hourly_data.get("weather_code", [])[i] if i < len(hourly_data.get("weather_code", [])) else 0,
            ))

        # Daily
        daily_data = data.get("daily", {})
        daily_times = daily_data.get("time", [])
        daily = []
        for i, t in enumerate(daily_times):
            daily.append(WeatherDaily(
                date=t,
                temp_max=daily_data.get("temperature_2m_max", [])[i] if i < len(daily_data.get("temperature_2m_max", [])) else 0,
                temp_min=daily_data.get("temperature_2m_min", [])[i] if i < len(daily_data.get("temperature_2m_min", [])) else 0,
                precipitation_sum=daily_data.get("precipitation_sum", [])[i] if i < len(daily_data.get("precipitation_sum", [])) else 0,
                wind_speed_max=daily_data.get("wind_speed_10m_max", [])[i] if i < len(daily_data.get("wind_speed_10m_max", [])) else 0,
                sunrise=daily_data.get("sunrise", [])[i] if i < len(daily_data.get("sunrise", [])) else "",
                sunset=daily_data.get("sunset", [])[i] if i < len(daily_data.get("sunset", [])) else "",
                description=WMO_CODES.get(daily_data.get("weather_code", [])[i] if i < len(daily_data.get("weather_code", [])) else 0, ""),
            ))

        return WeatherReport(
            location=city or f"{lat},{lon}",
            latitude=lat, longitude=lon,
            current=current, hourly=hourly, daily=daily,
            fetched_at=now, cached=False,
        )

    # ═══ Stats ═══

    def stats(self) -> dict[str, Any]:
        cache_files = list(self._cache_dir.glob("*.json"))
        return {
            "api_calls": self._call_count,
            "cache_entries": len(cache_files),
            "cache_dir": str(self._cache_dir),
            "cache_ttl_minutes": self._cache_ttl // 60,
        }

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None


# ═══ Singleton ═══

_om_client: OpenMeteoClient | None = None


def get_weather_client() -> OpenMeteoClient:
    global _om_client
    if _om_client is None:
        _om_client = OpenMeteoClient()
    return _om_client


# ═══ LifeEngine Integration Helper ═══

async def inject_weather_context(latitude: float, longitude: float, city: str = "") -> str:
    """Get weather context for injection into LifeEngine/LifeContext.

    Usage in LifeEngine._cognize:
        weather_ctx = await inject_weather_context(39.9, 116.4, "北京")
        ctx.metadata["environmental_context"] = weather_ctx
    """
    om = get_weather_client()
    return await om.get_environmental_context(latitude, longitude, city)


__all__ = [
    "OpenMeteoClient", "WeatherReport", "WeatherCurrent",
    "WeatherHourly", "WeatherDaily", "AirQualityData",
    "get_weather_client", "inject_weather_context",
]
