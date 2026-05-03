"""
统一地理位置模型

合并自:
- local_market/models.py GeoLocation (精确 haversine 距离)
- social_commerce/models.py GeoLocation (模糊 GeoHash 距离 + 交易时段)
- social_commerce/models.py GeoHash 工具类
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Set
import math

from .enums import GeoPrecision


# ============================================================================
# GeoHash 工具类
# ============================================================================

class GeoHash:
    """GeoHash 编码/解码工具"""

    BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

    @classmethod
    def encode(cls, lat: float, lon: float, precision: int = 6) -> str:
        """将经纬度编码为 GeoHash"""
        lat_range, lon_range = (-90.0, 90.0), (-180.0, 180.0)
        bits = []  # type: list[int]
        is_lon = True

        while len([b for b in bits if b != -1]) < precision * 5:
            if is_lon:
                mid = (lon_range[0] + lon_range[1]) / 2
                if lon >= mid:
                    bits.append(1)
                    lon_range = (mid, lon_range[1])
                else:
                    bits.append(0)
                    lon_range = (lon_range[0], mid)
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if lat >= mid:
                    bits.append(1)
                    lat_range = (mid, lat_range[1])
                else:
                    bits.append(0)
                    lat_range = (lat_range[0], mid)
            is_lon = not is_lon

        result = []
        for i in range(0, len(bits), 5):
            chunk = bits[i:i + 5]
            if len(chunk) == 5:
                idx = chunk[0] * 16 + chunk[1] * 8 + chunk[2] * 4 + chunk[3] * 2 + chunk[4]
                result.append(cls.BASE32[idx])

        return "".join(result)

    @classmethod
    def neighbors(cls, geohash: str) -> list[str]:
        """获取相邻 GeoHash（近似）"""
        return [geohash[:-1] + c for c in cls.BASE32 if c != geohash[-1]][:8]


# ============================================================================
# 统一 GeoLocation
# ============================================================================

@dataclass
class GeoLocation:
    """地理位置（统一）
    
    合并了 local_market 的精确距离和 social_commerce 的模糊距离。
    默认使用 haversine 精确距离；当 precision 不为 EXACT 时使用 GeoHash 模糊距离。
    """
    latitude: float = 0.0
    longitude: float = 0.0
    geohash: str = ""
    district: str = ""
    precision: GeoPrecision = GeoPrecision.EXACT
    precision_bits: int = 6            # GeoHash 精度位数（4=城市, 5=区县, 6=街道）

    # 可交易时段（social_commerce 功能）
    available_hours: Set[int] = field(default_factory=set)
    is_traveling: bool = False
    travel_destination: Optional[str] = None

    def __post_init__(self):
        if not self.geohash:
            self.geohash = GeoHash.encode(self.latitude, self.longitude, self.precision_bits)

    @classmethod
    def from_coords(cls, lat: float, lon: float,
                    precision: GeoPrecision = GeoPrecision.EXACT) -> GeoLocation:
        """从坐标创建"""
        bits_map = {
            GeoPrecision.EXACT: 7,
            GeoPrecision.NEIGHBORHOOD: 6,
            GeoPrecision.DISTRICT: 5,
            GeoPrecision.CITY: 4,
        }
        bits = bits_map.get(precision, 6)
        geohash = GeoHash.encode(lat, lon, bits)
        return cls(latitude=lat, longitude=lon, geohash=geohash,
                   precision=precision, precision_bits=bits)

    def distance_to(self, other: GeoLocation) -> float:
        """计算两点距离（公里）
        
        EXACT 精度: haversine 精确距离
        其他精度: GeoHash 前缀模糊距离（0-1归一化）
        """
        if self.precision == GeoPrecision.EXACT:
            return self._haversine_distance(other)
        return self._geohash_distance(other)

    def _haversine_distance(self, other: GeoLocation) -> float:
        """Haversine 精确距离（公里）"""
        R = 6371.0
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    def _geohash_distance(self, other: GeoLocation) -> float:
        """GeoHash 前缀模糊距离（0-1）"""
        if not self.geohash or not other.geohash:
            return float("inf")
        match_len = sum(1 for a, b in zip(self.geohash, other.geohash) if a == b)
        max_len = max(len(self.geohash), len(other.geohash))
        return (max_len - match_len) / max_len if max_len > 0 else 1.0

    def can_trade_with(self, other: GeoLocation, hour: int) -> bool:
        """检查是否可以在指定小时交易"""
        if self.available_hours and hour not in self.available_hours:
            return False
        if other.available_hours and hour not in other.available_hours:
            return False
        return self.distance_to(other) <= self._max_trade_distance()

    def _max_trade_distance(self) -> float:
        """根据精度返回最大可交易距离（公里）"""
        limits = {
            GeoPrecision.EXACT: 5.0,
            GeoPrecision.NEIGHBORHOOD: 10.0,
            GeoPrecision.DISTRICT: 30.0,
            GeoPrecision.CITY: 100.0,
        }
        return limits.get(self.precision, 30.0)

    def to_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "geohash": self.geohash,
            "district": self.district,
            "precision": self.precision.value,
            "precision_bits": self.precision_bits,
            "available_hours": sorted(self.available_hours) if self.available_hours else [],
            "is_traveling": self.is_traveling,
            "travel_destination": self.travel_destination,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GeoLocation:
        return cls(
            latitude=data.get("latitude", 0.0),
            longitude=data.get("longitude", 0.0),
            geohash=data.get("geohash", ""),
            district=data.get("district", ""),
            precision=GeoPrecision(data.get("precision", "exact")),
            precision_bits=data.get("precision_bits", 6),
            available_hours=set(data.get("available_hours", [])),
            is_traveling=data.get("is_traveling", False),
            travel_destination=data.get("travel_destination"),
        )
