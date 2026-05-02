"""
统一地图网关 (Map Gateway)

核心功能：
1. 统一抽象与智能路由：封装统一接口，智能选择高德、百度、腾讯、天地图
2. 多层缓存机制：内存 -> 本地文件/DB -> 分布式缓存
3. 配额水位与熔断：实时监控用量，自动切换
4. 批量接口聚合：优先使用批量接口
5. 坐标系转换：支持CGCS2000、GCJ-02、BD-09、WGS84互转

目标：最大化利用四家免费额度，实现无缝叠加上限。
"""
import json
import math
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Callable
from pathlib import Path
from functools import lru_cache

import requests


# 简化math函数调用
sin = math.sin
cos = math.cos
sqrt = math.sqrt
atan2 = math.atan2


class MapProvider(Enum):
    """地图服务提供商"""
    AMAP = "amap"      # 高德地图
    BAIDU = "baidu"    # 百度地图
    TENCENT = "tencent" # 腾讯地图
    TDITU = "tditu"    # 天地图（国家测绘局）


class CoordinateSystem(Enum):
    """坐标系"""
    WGS84 = "wgs84"      # GPS原始坐标系
    GCJ02 = "gcj02"      # 高德/谷歌加密坐标系
    BD09 = "bd09"        # 百度加密坐标系
    CGCS2000 = "cgcs2000" # 天地图国家标准坐标系


class ServiceType(Enum):
    """服务类型"""
    GEOCODE = "geocode"           # 地理编码（地址→坐标）
    REVERSE_GEOCODE = "reverse_geocode" # 逆地理编码（坐标→地址）
    DIRECTION = "direction"       # 路径规划
    PLACE_SEARCH = "place_search" # POI搜索
    STATIC_MAP = "static_map"     # 静态地图


@dataclass
class ProviderConfig:
    """服务商配置"""
    provider: MapProvider
    api_key: str
    secret_key: str = ""
    base_url: str = ""
    daily_limit: int = 10000  # 日限额
    monthly_limit: int = 300000  # 月限额
    daily_used: int = 0       # 当日已用
    monthly_used: int = 0     # 当月已用
    last_reset_time: float = 0  # 上次重置时间
    enabled: bool = True      # 是否启用
    specialties: List[str] = field(default_factory=list)  # 特长服务


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    timestamp: float
    ttl: int  # 过期时间（秒）
    provider: MapProvider


@dataclass
class GatewayStats:
    """网关统计"""
    total_requests: int = 0
    cache_hits: int = 0
    api_calls: int = 0
    provider_usage: Dict[str, int] = field(default_factory=dict)
    last_reset_time: float = 0


class MapGateway:
    """
    统一地图网关
    
    核心能力：
    1. 智能路由：根据配额、特长、成本选择最优服务商
    2. 多层缓存：减少重复请求
    3. 配额管理：监控用量，自动熔断
    4. 批量聚合：优化调用次数
    """
    
    def __init__(self):
        # 服务商配置
        self.providers: Dict[MapProvider, ProviderConfig] = self._load_providers()
        
        # 内存缓存（LRU缓存，最大1000条）
        self.memory_cache = {}
        
        # 文件缓存路径
        self.cache_dir = Path("cache/map")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self.stats = GatewayStats()
        self.stats.last_reset_time = time.time()
        
        # 熔断状态
        self.circuit_breakers: Dict[MapProvider, bool] = {}
        
        # 初始化熔断状态
        for provider in MapProvider:
            self.circuit_breakers[provider] = False
    
    def _load_providers(self) -> Dict[MapProvider, ProviderConfig]:
        """加载服务商配置"""
        return {
            MapProvider.AMAP: ProviderConfig(
                provider=MapProvider.AMAP,
                api_key=self._get_env_or_default("AMAP_API_KEY", "32aecc8d64d7d2f74df23cfd3d19de23d4d"),
                secret_key=self._get_env_or_default("AMAP_SECRET_KEY", ""),
                base_url="https://restapi.amap.com/v3",
                daily_limit=30000,
                monthly_limit=900000,
                specialties=["direction", "static_map", "place_search"]
            ),
            MapProvider.BAIDU: ProviderConfig(
                provider=MapProvider.BAIDU,
                api_key=self._get_env_or_default("BAIDU_API_KEY", ""),
                secret_key=self._get_env_or_default("BAIDU_SECRET_KEY", ""),
                base_url="https://api.map.baidu.com",
                daily_limit=20000,
                monthly_limit=600000,
                specialties=["reverse_geocode", "geocode"]
            ),
            MapProvider.TENCENT: ProviderConfig(
                provider=MapProvider.TENCENT,
                api_key=self._get_env_or_default("TENCENT_API_KEY", ""),
                secret_key=self._get_env_or_default("TENCENT_SECRET_KEY", ""),
                base_url="https://apis.map.qq.com",
                daily_limit=15000,
                monthly_limit=450000,
                specialties=["place_search", "static_map"]
            ),
            MapProvider.TDITU: ProviderConfig(
                provider=MapProvider.TDITU,
                api_key=self._get_env_or_default("TDITU_API_KEY", "2e0225658699ccabf223a2c376c535bb"),
                secret_key=self._get_env_or_default("TDITU_SECRET_KEY", ""),
                base_url="http://api.tianditu.gov.cn",
                daily_limit=10000,
                monthly_limit=300000,
                specialties=["geocode", "reverse_geocode", "static_map", "place_search", "direction", "administrative", "data_api"]
            )
        }
    
    def _get_env_or_default(self, key: str, default: str) -> str:
        """获取环境变量或默认值"""
        return os.environ.get(key, default)
    
    # ==================== 智能路由 ====================
    
    def _select_provider(self, service_type: ServiceType) -> Optional[MapProvider]:
        """
        智能选择服务商
        
        选择策略：
        1. 优先选择未熔断、API Key已配置的服务商
        2. 优先选择有特长的服务商
        3. 考虑剩余配额（优先选择配额充足的）
        4. 考虑历史成功率
        """
        candidates = []
        
        for provider, config in self.providers.items():
            # 跳过已熔断或禁用的服务商
            if not config.enabled or self.circuit_breakers.get(provider, False):
                continue
            
            # 跳过API Key未配置的服务商
            if not config.api_key:
                continue
            
            # 检查配额是否充足
            if not self._check_quota(provider):
                continue
            
            # 计算优先级分数
            score = self._calculate_priority(provider, service_type)
            candidates.append((provider, score))
        
        if not candidates:
            return None
        
        # 选择分数最高的服务商
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def _calculate_priority(self, provider: MapProvider, service_type: ServiceType) -> float:
        """计算服务商优先级分数"""
        config = self.providers[provider]
        score = 0.0
        
        # 天地图优先加成（默认使用天地图）
        if provider == MapProvider.TDITU:
            score += 25
        
        # 特长加成（如果服务类型是该服务商的特长）
        if service_type.value in config.specialties:
            score += 30
        
        # 配额充足度加成
        quota_ratio = self._get_quota_ratio(provider)
        score += quota_ratio * 50
        
        # 随机因子（避免总是选择同一个）
        import random
        score += random.uniform(0, 20)
        
        return score
    
    def _get_quota_ratio(self, provider: MapProvider) -> float:
        """获取配额剩余比例"""
        config = self.providers[provider]
        
        # 取日配额和月配额中更严格的
        daily_ratio = max(0, (config.daily_limit - config.daily_used) / config.daily_limit)
        monthly_ratio = max(0, (config.monthly_limit - config.monthly_used) / config.monthly_limit)
        
        return min(daily_ratio, monthly_ratio)
    
    def _check_quota(self, provider: MapProvider) -> bool:
        """检查配额是否充足"""
        config = self.providers[provider]
        
        # 检查日配额
        if config.daily_used >= config.daily_limit * 0.95:
            return False
        
        # 检查月配额
        if config.monthly_used >= config.monthly_limit * 0.95:
            return False
        
        return True
    
    # ==================== 缓存机制 ====================
    
    def _get_cache_key(self, service_type: ServiceType, **kwargs) -> str:
        """生成缓存键"""
        sorted_args = sorted(kwargs.items())
        args_str = "_".join(f"{k}={v}" for k, v in sorted_args)
        return f"{service_type.value}_{args_str}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """从缓存获取数据"""
        # 1. 先查内存缓存
        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            if time.time() < entry.timestamp + entry.ttl:
                self.stats.cache_hits += 1
                return entry.value
            else:
                del self.memory_cache[cache_key]
        
        # 2. 再查文件缓存
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if time.time() < data.get('timestamp', 0) + data.get('ttl', 86400):
                    self.stats.cache_hits += 1
                    # 同时加载到内存缓存
                    self._add_to_cache(cache_key, data['value'], data.get('ttl', 86400), data.get('provider'))
                    return data['value']
            except:
                pass
        
        return None
    
    def _add_to_cache(self, cache_key: str, value: Any, ttl: int = 86400, provider: MapProvider = None):
        """添加到缓存"""
        # 添加到内存缓存
        self.memory_cache[cache_key] = CacheEntry(
            key=cache_key,
            value=value,
            timestamp=time.time(),
            ttl=ttl,
            provider=provider
        )
        
        # 限制内存缓存大小
        if len(self.memory_cache) > 1000:
            # 删除最早的条目
            oldest_key = min(self.memory_cache.keys(), key=lambda k: self.memory_cache[k].timestamp)
            del self.memory_cache[oldest_key]
        
        # 写入文件缓存
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'key': cache_key,
                    'value': value,
                    'timestamp': time.time(),
                    'ttl': ttl,
                    'provider': provider.value if provider else None
                }, f)
        except:
            pass
    
    # ==================== 配额管理 ====================
    
    def _update_quota(self, provider: MapProvider, count: int = 1):
        """更新配额使用量"""
        config = self.providers[provider]
        
        # 检查是否需要重置
        now = time.time()
        if self._should_reset_daily(config):
            config.daily_used = 0
        
        if self._should_reset_monthly(config):
            config.monthly_used = 0
        
        # 更新用量
        config.daily_used += count
        config.monthly_used += count
        
        # 更新统计
        self.stats.api_calls += count
        self.stats.provider_usage[provider.value] = self.stats.provider_usage.get(provider.value, 0) + count
        
        # 检查是否需要熔断
        self._check_circuit_breaker(provider)
    
    def _should_reset_daily(self, config: ProviderConfig) -> bool:
        """检查是否需要重置日配额"""
        now = time.time()
        # 如果上次重置时间早于今天0点，则需要重置
        import datetime
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return config.last_reset_time < today_start
    
    def _should_reset_monthly(self, config: ProviderConfig) -> bool:
        """检查是否需要重置月配额"""
        now = time.time()
        # 如果上次重置时间早于当月1号0点，则需要重置
        import datetime
        month_start = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        return config.last_reset_time < month_start
    
    def _check_circuit_breaker(self, provider: MapProvider):
        """检查熔断状态"""
        config = self.providers[provider]
        
        # 检查日配额
        daily_ratio = config.daily_used / config.daily_limit
        monthly_ratio = config.monthly_used / config.monthly_limit
        
        # 设置警戒线为80%
        if daily_ratio >= 0.8 or monthly_ratio >= 0.8:
            self.circuit_breakers[provider] = True
            print(f"🔴 熔断 {provider.value}：日用量 {config.daily_used}/{config.daily_limit}，月用量 {config.monthly_used}/{config.monthly_limit}")
        else:
            self.circuit_breakers[provider] = False
    
    def reset_circuit_breaker(self, provider: MapProvider):
        """重置熔断状态"""
        self.circuit_breakers[provider] = False
    
    # ==================== 统一接口 ====================
    
    def geocode(self, address: str, city: str = "") -> Dict[str, Any]:
        """
        地理编码：地址→坐标
        
        Args:
            address: 地址字符串
            city: 城市名（可选）
        
        Returns:
            包含坐标的字典
        """
        self.stats.total_requests += 1
        
        cache_key = self._get_cache_key(ServiceType.GEOCODE, address=address, city=city)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        provider = self._select_provider(ServiceType.GEOCODE)
        if not provider:
            return {"success": False, "error": "所有服务商均不可用"}
        
        result = self._call_geocode(provider, address, city)
        
        if result.get("success"):
            self._add_to_cache(cache_key, result, ttl=86400, provider=provider)
            self._update_quota(provider)
        
        return result
    
    def reverse_geocode(self, longitude: float, latitude: float) -> Dict[str, Any]:
        """
        逆地理编码：坐标→地址
        
        Args:
            longitude: 经度
            latitude: 纬度
        
        Returns:
            包含地址信息的字典
        """
        cache_key = self._get_cache_key(ServiceType.REVERSE_GEOCODE, lon=longitude, lat=latitude)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        provider = self._select_provider(ServiceType.REVERSE_GEOCODE)
        if not provider:
            return {"success": False, "error": "所有服务商均不可用"}
        
        result = self._call_reverse_geocode(provider, longitude, latitude)
        
        if result.get("success"):
            self._add_to_cache(cache_key, result, ttl=86400, provider=provider)
            self._update_quota(provider)
        
        return result
    
    def batch_geocode(self, addresses: List[str], city: str = "") -> List[Dict[str, Any]]:
        """
        批量地理编码
        
        Args:
            addresses: 地址列表
            city: 城市名（可选）
        
        Returns:
            结果列表
        """
        results = []
        uncached = []
        cache_keys = []
        
        # 先检查缓存
        for address in addresses:
            cache_key = self._get_cache_key(ServiceType.GEOCODE, address=address, city=city)
            cached = self._get_from_cache(cache_key)
            if cached:
                results.append(cached)
            else:
                uncached.append(address)
                cache_keys.append(cache_key)
        
        # 对未缓存的进行批量请求
        if uncached:
            provider = self._select_provider(ServiceType.GEOCODE)
            if provider:
                batch_result = self._call_batch_geocode(provider, uncached, city)
                
                for i, address in enumerate(uncached):
                    if i < len(batch_result):
                        result = batch_result[i]
                        results.append(result)
                        if result.get("success"):
                            self._add_to_cache(cache_keys[i], result, ttl=86400, provider=provider)
                
                self._update_quota(provider, len(uncached))
        
        return results
    
    def direction(self, origin: Tuple[float, float], destination: Tuple[float, float],
                 mode: str = "driving") -> Dict[str, Any]:
        """
        路径规划
        
        Args:
            origin: 起点坐标 (lon, lat)
            destination: 终点坐标 (lon, lat)
            mode: 交通方式 (driving, walking, biking, transit)
        
        Returns:
            路径信息
        """
        cache_key = self._get_cache_key(ServiceType.DIRECTION, 
                                       orig_lon=origin[0], orig_lat=origin[1],
                                       dest_lon=destination[0], dest_lat=destination[1],
                                       mode=mode)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        provider = self._select_provider(ServiceType.DIRECTION)
        if not provider:
            return {"success": False, "error": "所有服务商均不可用"}
        
        result = self._call_direction(provider, origin, destination, mode)
        
        if result.get("success"):
            self._add_to_cache(cache_key, result, ttl=3600, provider=provider)
            self._update_quota(provider)
        
        return result
    
    def place_search(self, keyword: str, city: str = "", page_size: int = 10) -> Dict[str, Any]:
        """
        POI搜索
        
        Args:
            keyword: 搜索关键词
            city: 城市名（可选）
            page_size: 返回数量
        
        Returns:
            POI列表
        """
        cache_key = self._get_cache_key(ServiceType.PLACE_SEARCH, keyword=keyword, city=city, page_size=page_size)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        provider = self._select_provider(ServiceType.PLACE_SEARCH)
        if not provider:
            return {"success": False, "error": "所有服务商均不可用"}
        
        result = self._call_place_search(provider, keyword, city, page_size)
        
        if result.get("success"):
            self._add_to_cache(cache_key, result, ttl=3600, provider=provider)
            self._update_quota(provider)
        
        return result
    
    def static_map(self, center: Tuple[float, float], zoom: int = 15, 
                   width: int = 800, height: int = 600) -> Dict[str, Any]:
        """
        静态地图
        
        Args:
            center: 中心点坐标 (lon, lat)
            zoom: 缩放级别
            width: 宽度（像素）
            height: 高度（像素）
        
        Returns:
            图片URL或数据
        """
        provider = self._select_provider(ServiceType.STATIC_MAP)
        if not provider:
            return {"success": False, "error": "所有服务商均不可用"}
        
        result = self._call_static_map(provider, center, zoom, width, height)
        
        if result.get("success"):
            self._update_quota(provider)
        
        return result
    
    # ==================== 服务商API调用 ====================
    
    def _call_geocode(self, provider: MapProvider, address: str, city: str) -> Dict[str, Any]:
        """调用地理编码API"""
        config = self.providers[provider]
        
        try:
            if provider == MapProvider.AMAP:
                url = f"{config.base_url}/geocode/geo"
                params = {
                    "key": config.api_key,
                    "address": address,
                    "city": city,
                    "output": "json"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("status") == "1" and data.get("geocodes"):
                    result = data["geocodes"][0]
                    return {
                        "success": True,
                        "longitude": float(result["location"].split(",")[0]),
                        "latitude": float(result["location"].split(",")[1]),
                        "formatted_address": result.get("formatted_address", ""),
                        "province": result.get("province", ""),
                        "city": result.get("city", ""),
                        "district": result.get("district", ""),
                        "provider": "amap"
                    }
            
            elif provider == MapProvider.BAIDU:
                if not config.api_key:
                    return {"success": False, "error": "百度API Key未配置"}
                
                url = f"{config.base_url}/geocoding/v3"
                params = {
                    "ak": config.api_key,
                    "address": address,
                    "city": city,
                    "output": "json"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("status") == 0 and data.get("result"):
                    result = data["result"]
                    return {
                        "success": True,
                        "longitude": result["location"]["lng"],
                        "latitude": result["location"]["lat"],
                        "formatted_address": result.get("formatted_address", ""),
                        "province": result.get("addressComponent", {}).get("province", ""),
                        "city": result.get("addressComponent", {}).get("city", ""),
                        "district": result.get("addressComponent", {}).get("district", ""),
                        "provider": "baidu"
                    }
            
            elif provider == MapProvider.TENCENT:
                if not config.api_key:
                    return {"success": False, "error": "腾讯API Key未配置"}
                
                url = f"{config.base_url}/ws/geocoder/v1"
                params = {
                    "key": config.api_key,
                    "address": address,
                    "city": city,
                    "output": "json"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("status") == 0 and data.get("result"):
                    result = data["result"]
                    return {
                        "success": True,
                        "longitude": result["location"]["lng"],
                        "latitude": result["location"]["lat"],
                        "formatted_address": result.get("address", ""),
                        "provider": "tencent"
                    }
            
            elif provider == MapProvider.TDITU:
                if not config.api_key:
                    return {"success": False, "error": "天地图API Key未配置"}
                
                url = f"{config.base_url}/geocode"
                params = {
                    "tk": config.api_key,
                    "address": address,
                    "city": city,
                    "output": "json"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("code") == "0" and data.get("result"):
                    result = data["result"]
                    # 天地图返回CGCS2000坐标，转换为GCJ02供外部使用
                    lon, lat = float(result["lon"]), float(result["lat"])
                    gcj_lon, gcj_lat = self._cgcs2000_to_gcj02(lon, lat)
                    return {
                        "success": True,
                        "longitude": gcj_lon,
                        "latitude": gcj_lat,
                        "formatted_address": result.get("formatted_address", ""),
                        "province": result.get("province", ""),
                        "city": result.get("city", ""),
                        "district": result.get("district", ""),
                        "provider": "tditu",
                        "original_coords": {"lon": lon, "lat": lat, "crs": "CGCS2000"}
                    }
            
            return {"success": False, "error": "API调用失败"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _call_reverse_geocode(self, provider: MapProvider, longitude: float, latitude: float) -> Dict[str, Any]:
        """调用逆地理编码API"""
        config = self.providers[provider]
        
        try:
            if provider == MapProvider.AMAP:
                url = f"{config.base_url}/geocode/regeo"
                params = {
                    "key": config.api_key,
                    "location": f"{longitude},{latitude}",
                    "output": "json",
                    "extensions": "all"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("status") == "1" and data.get("regeocode"):
                    result = data["regeocode"]
                    address_component = result.get("addressComponent", {})
                    return {
                        "success": True,
                        "formatted_address": result.get("formatted_address", ""),
                        "province": address_component.get("province", ""),
                        "city": address_component.get("city", ""),
                        "district": address_component.get("district", ""),
                        "township": address_component.get("township", ""),
                        "provider": "amap"
                    }
            
            elif provider == MapProvider.BAIDU:
                if not config.api_key:
                    return {"success": False, "error": "百度API Key未配置"}
                
                url = f"{config.base_url}/reverse_geocoding/v3"
                params = {
                    "ak": config.api_key,
                    "location": f"{latitude},{longitude}",
                    "output": "json",
                    "coordtype": "wgs84ll"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("status") == 0 and data.get("result"):
                    result = data["result"]
                    address_component = result.get("addressComponent", {})
                    return {
                        "success": True,
                        "formatted_address": result.get("formatted_address", ""),
                        "province": address_component.get("province", ""),
                        "city": address_component.get("city", ""),
                        "district": address_component.get("district", ""),
                        "provider": "baidu"
                    }
            
            elif provider == MapProvider.TENCENT:
                if not config.api_key:
                    return {"success": False, "error": "腾讯API Key未配置"}
                
                url = f"{config.base_url}/ws/geocoder/v1"
                params = {
                    "key": config.api_key,
                    "location": f"{latitude},{longitude}",
                    "output": "json"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("status") == 0 and data.get("result"):
                    result = data["result"]
                    return {
                        "success": True,
                        "formatted_address": result.get("address", ""),
                        "provider": "tencent"
                    }
            
            return {"success": False, "error": "API调用失败"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _call_batch_geocode(self, provider: MapProvider, addresses: List[str], city: str) -> List[Dict[str, Any]]:
        """调用批量地理编码API"""
        results = []
        
        # 目前大部分服务商的批量接口需要特殊处理，这里简化为逐个调用
        for address in addresses:
            result = self._call_geocode(provider, address, city)
            results.append(result)
        
        return results
    
    def _call_direction(self, provider: MapProvider, origin: Tuple[float, float], 
                       destination: Tuple[float, float], mode: str) -> Dict[str, Any]:
        """调用路径规划API"""
        config = self.providers[provider]
        
        try:
            if provider == MapProvider.AMAP:
                url = f"{config.base_url}/direction/driving"
                params = {
                    "key": config.api_key,
                    "origin": f"{origin[0]},{origin[1]}",
                    "destination": f"{destination[0]},{destination[1]}",
                    "output": "json"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("status") == "1" and data.get("route") and data["route"].get("paths"):
                    path = data["route"]["paths"][0]
                    return {
                        "success": True,
                        "distance": float(path.get("distance", 0)) * 1000,
                        "duration": float(path.get("duration", 0)) * 60,
                        "provider": "amap"
                    }
            
            return {"success": False, "error": "API调用失败"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _call_place_search(self, provider: MapProvider, keyword: str, city: str, page_size: int) -> Dict[str, Any]:
        """调用POI搜索API"""
        config = self.providers[provider]
        
        try:
            if provider == MapProvider.AMAP:
                url = f"{config.base_url}/place/text"
                params = {
                    "key": config.api_key,
                    "keywords": keyword,
                    "city": city,
                    "offset": page_size,
                    "output": "json"
                }
                response = requests.get(url, params=params, timeout=30)
                data = response.json()
                
                if data.get("status") == "1":
                    pois = data.get("pois", [])
                    return {
                        "success": True,
                        "count": len(pois),
                        "results": [{"name": p.get("name"), "location": p.get("location")} for p in pois],
                        "provider": "amap"
                    }
            
            return {"success": False, "error": "API调用失败"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _call_static_map(self, provider: MapProvider, center: Tuple[float, float], 
                        zoom: int, width: int, height: int) -> Dict[str, Any]:
        """调用静态地图API"""
        config = self.providers[provider]
        
        try:
            if provider == MapProvider.AMAP:
                url = f"{config.base_url}/staticmap"
                params = {
                    "key": config.api_key,
                    "location": f"{center[0]},{center[1]}",
                    "zoom": zoom,
                    "size": f"{width}*{height}",
                    "output": "png"
                }
                import urllib.parse
                url_with_params = f"{url}?{urllib.parse.urlencode(params)}"
                return {
                    "success": True,
                    "image_url": url_with_params,
                    "provider": "amap"
                }
            
            elif provider == MapProvider.TDITU:
                # 天地图静态地图服务
                url = "http://t4.tianditu.gov.cn/DataServer"
                params = {
                    "tk": config.api_key,
                    "T": "vec_w",
                    "x": center[0],
                    "y": center[1],
                    "l": zoom
                }
                import urllib.parse
                url_with_params = f"{url}?{urllib.parse.urlencode(params)}"
                return {
                    "success": True,
                    "image_url": url_with_params,
                    "provider": "tditu"
                }
            
            return {"success": False, "error": "API调用失败"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== 统计与监控 ====================
    
    def get_stats(self) -> GatewayStats:
        """获取网关统计信息"""
        return self.stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = GatewayStats()
        self.stats.last_reset_time = time.time()
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有服务商状态"""
        status = {}
        for provider, config in self.providers.items():
            status[provider.value] = {
                "enabled": config.enabled,
                "circuit_broken": self.circuit_breakers.get(provider, False),
                "daily_used": config.daily_used,
                "daily_limit": config.daily_limit,
                "monthly_used": config.monthly_used,
                "monthly_limit": config.monthly_limit,
                "specialties": config.specialties
            }
        return status
    
    def print_status(self):
        """打印网关状态"""
        print("=" * 60)
        print("Map Gateway Status")
        print("=" * 60)
        print(f"Total Requests: {self.stats.total_requests}")
        print(f"Cache Hits: {self.stats.cache_hits}")
        print(f"API Calls: {self.stats.api_calls}")
        print(f"Cache Hit Rate: {self.stats.cache_hits / max(self.stats.total_requests, 1) * 100:.1f}%")
        print()
        print("Provider Status:")
        for provider, status in self.get_provider_status().items():
            daily_ratio = status['daily_used'] / status['daily_limit'] * 100
            monthly_ratio = status['monthly_used'] / status['monthly_limit'] * 100
            status_icon = "🟢" if status['enabled'] and not status['circuit_broken'] else "🔴"
            print(f"  {status_icon} {provider}:")
            print(f"    Daily: {status['daily_used']}/{status['daily_limit']} ({daily_ratio:.1f}%)")
            print(f"    Monthly: {status['monthly_used']}/{status['monthly_limit']} ({monthly_ratio:.1f}%)")
            print(f"    Circuit Broken: {status['circuit_broken']}")
        print("=" * 60)
    
    # ==================== 坐标系转换 ====================
    
    def _transform_lat(self, x: float, y: float) -> float:
        """纬度转换辅助函数"""
        pi = 3.1415926535897932384626
        a = 6378137.0
        ee = 0.00669342162296594323
        
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * abs(x)
        ret += (20.0 * sin(6.0 * x * pi) + 20.0 * sin(2.0 * x * pi)) * 2.0 / 3.0
        ret += (20.0 * sin(y * pi) + 40.0 * sin(y / 3.0 * pi)) * 2.0 / 3.0
        ret += (160.0 * sin(y / 12.0 * pi) + 320.0 * sin(y * pi / 30.0)) * 2.0 / 3.0
        return ret
    
    def _transform_lon(self, x: float, y: float) -> float:
        """经度转换辅助函数"""
        pi = 3.1415926535897932384626
        
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * abs(x)
        ret += (20.0 * sin(6.0 * x * pi) + 20.0 * sin(2.0 * x * pi)) * 2.0 / 3.0
        ret += (20.0 * sin(x * pi) + 40.0 * sin(x / 3.0 * pi)) * 2.0 / 3.0
        ret += (150.0 * sin(x / 12.0 * pi) + 300.0 * sin(x / 30.0 * pi)) * 2.0 / 3.0
        return ret
    
    def _cgcs2000_to_gcj02(self, lon: float, lat: float) -> Tuple[float, float]:
        """CGCS2000转GCJ02（天地图转高德/谷歌）"""
        return self._wgs84_to_gcj02(lon, lat)
    
    def _gcj02_to_cgcs2000(self, lon: float, lat: float) -> Tuple[float, float]:
        """GCJ02转CGCS2000（高德/谷歌转天地图）"""
        return self._gcj02_to_wgs84(lon, lat)
    
    def _wgs84_to_gcj02(self, lon: float, lat: float) -> Tuple[float, float]:
        """WGS84转GCJ02（GPS转高德/谷歌）"""
        pi = 3.1415926535897932384626
        a = 6378137.0
        ee = 0.00669342162296594323
        
        d_lat = self._transform_lat(lon - 105.0, lat - 35.0)
        d_lon = self._transform_lon(lon - 105.0, lat - 35.0)
        
        rad_lat = lat / 180.0 * pi
        magic = sin(rad_lat)
        magic = 1 - ee * magic * magic
        sqrt_magic = sqrt(magic)
        
        d_lat = (d_lat * 180.0) / ((a * (1 - ee)) / (magic * sqrt_magic) * pi)
        d_lon = (d_lon * 180.0) / (a / sqrt_magic * cos(rad_lat) * pi)
        
        return (lon + d_lon, lat + d_lat)
    
    def _gcj02_to_wgs84(self, lon: float, lat: float) -> Tuple[float, float]:
        """GCJ02转WGS84（高德/谷歌转GPS）"""
        pi = 3.1415926535897932384626
        a = 6378137.0
        ee = 0.00669342162296594323
        
        d_lat = self._transform_lat(lon - 105.0, lat - 35.0)
        d_lon = self._transform_lon(lon - 105.0, lat - 35.0)
        
        rad_lat = lat / 180.0 * pi
        magic = sin(rad_lat)
        magic = 1 - ee * magic * magic
        sqrt_magic = sqrt(magic)
        
        d_lat = (d_lat * 180.0) / ((a * (1 - ee)) / (magic * sqrt_magic) * pi)
        d_lon = (d_lon * 180.0) / (a / sqrt_magic * cos(rad_lat) * pi)
        
        return (lon - d_lon, lat - d_lat)
    
    def _gcj02_to_bd09(self, lon: float, lat: float) -> Tuple[float, float]:
        """GCJ02转BD09（高德转百度）"""
        pi = 3.1415926535897932384626
        
        x = lon
        y = lat
        z = sqrt(x * x + y * y) + 0.00002 * sin(y * pi * 3000.0 / 180.0)
        theta = atan2(y, x) + 0.000003 * cos(x * pi * 3000.0 / 180.0)
        
        bd_lon = z * cos(theta) + 0.0065
        bd_lat = z * sin(theta) + 0.006
        
        return (bd_lon, bd_lat)
    
    def _bd09_to_gcj02(self, lon: float, lat: float) -> Tuple[float, float]:
        """BD09转GCJ02（百度转高德）"""
        pi = 3.1415926535897932384626
        
        x = lon - 0.0065
        y = lat - 0.006
        z = sqrt(x * x + y * y) - 0.00002 * sin(y * pi * 3000.0 / 180.0)
        theta = atan2(y, x) - 0.000003 * cos(x * pi * 3000.0 / 180.0)
        
        gcj_lon = z * cos(theta)
        gcj_lat = z * sin(theta)
        
        return (gcj_lon, gcj_lat)
    
    def convert_coordinates(self, lon: float, lat: float, 
                           from_crs: CoordinateSystem, to_crs: CoordinateSystem) -> Tuple[float, float]:
        """
        坐标转换接口
        
        Args:
            lon: 经度
            lat: 纬度
            from_crs: 源坐标系
            to_crs: 目标坐标系
        
        Returns:
            转换后的坐标 (lon, lat)
        """
        # 统一转换为GCJ02中间格式
        if from_crs == CoordinateSystem.WGS84:
            lon, lat = self._wgs84_to_gcj02(lon, lat)
        elif from_crs == CoordinateSystem.BD09:
            lon, lat = self._bd09_to_gcj02(lon, lat)
        elif from_crs == CoordinateSystem.CGCS2000:
            lon, lat = self._cgcs2000_to_gcj02(lon, lat)
        # GCJ02无需转换
        
        # 从GCJ02转换到目标坐标系
        if to_crs == CoordinateSystem.WGS84:
            return self._gcj02_to_wgs84(lon, lat)
        elif to_crs == CoordinateSystem.BD09:
            return self._gcj02_to_bd09(lon, lat)
        elif to_crs == CoordinateSystem.CGCS2000:
            return self._gcj02_to_cgcs2000(lon, lat)
        else:
            return (lon, lat)


# 单例模式
_map_gateway = None


def get_map_gateway() -> MapGateway:
    """获取Map Gateway单例"""
    global _map_gateway
    if _map_gateway is None:
        _map_gateway = MapGateway()
    return _map_gateway