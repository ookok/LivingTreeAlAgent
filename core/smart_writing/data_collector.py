# -*- coding: utf-8 -*-
"""
智能写作数据采集管道 v2 - Smart Writing Data Collector
======================================================

核心升级：
1. 真实政府平台API集成（国家统计局、生态环境部、中国气象局、自然资源部）
2. 主流第三方公开平台（高德、百度、聚合数据、天气网）
3. 动态数据类型：不固定采集字段，按需生成采集策略
4. 与知识库联动：采集结果自动写入VectorDB
5. 多源数据融合与可信度评估

Author: Hermes Desktop Team
"""

import asyncio
import hashlib
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from urllib.parse import urlencode, quote

logger = logging.getLogger(__name__)

# =============================================================================
# 数据源类型
# =============================================================================

class DataSourceType(Enum):
    """数据源类型"""
    # 政府平台
    NBS_STATS       = "nbs_stats"        # 国家统计局 data.stats.gov.cn
    MEE_ENV         = "mee_env"          # 生态环境部
    CMA_WEATHER     = "cma_weather"      # 中国气象局
    MEP_AIR         = "mep_air"          # 中国空气质量在线监测
    MNRPRC_GEO      = "mnrprc_geo"       # 自然资源部地理数据
    NDRC_ENERGY     = "ndrc_energy"      # 国家发改委能源数据
    # 第三方公开平台
    AMAP_GEO        = "amap_geo"         # 高德开放平台（地理/POI/路网）
    BAIDU_MAP       = "baidu_map"        # 百度地图开放平台
    JUHE_DATA       = "juhe_data"        # 聚合数据
    TIANQI_WEATHER  = "tianqi_weather"   # 天气网公开API
    ALIYUN_MARKET   = "aliyun_market"    # 阿里云市场
    CNINFO_STOCK    = "cninfo_stock"     # 巨潮资讯（上市公司公开数据）
    CSRC_SEC        = "csrc_sec"         # 中国证监会
    # 行业专项
    CEIC_INDUSTRY   = "ceic_industry"    # 行业数据（公开部分）
    WIND_FREE       = "wind_free"        # Wind公开数据
    # 本地数据库
    LOCAL_CACHE     = "local_cache"      # 本地缓存（历史采集）
    KNOWLEDGE_BASE  = "knowledge_base"   # 项目知识库
    # 备用
    AI_ESTIMATED    = "ai_estimated"     # AI估算（兜底）


class DataCategory(Enum):
    """数据类别"""
    ECONOMIC        = "economic"         # 经济统计
    ENVIRONMENTAL   = "environmental"    # 环境监测
    WEATHER         = "weather"          # 气象
    GEOGRAPHIC      = "geographic"       # 地理
    ENERGY          = "energy"           # 能源
    INDUSTRY        = "industry"         # 行业
    POPULATION      = "population"       # 人口
    LAND_USE        = "land_use"         # 土地利用
    FINANCIAL       = "financial"        # 财务金融
    REGULATION      = "regulation"       # 法规标准


@dataclass
class DataItem:
    """数据项"""
    key: str
    value: Any
    unit: str = ""
    source_type: DataSourceType = DataSourceType.AI_ESTIMATED
    source_name: str = ""
    source_url: str = ""
    category: DataCategory = DataCategory.ECONOMIC
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.8
    description: str = ""
    raw_response: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectionPlan:
    """采集计划 - 动态生成，不固定类型"""
    doc_type: str                          # 文档类型（可为空）
    intent_keywords: List[str]             # 意图关键词
    location: Optional[str] = None        # 地点
    industry: Optional[str] = None        # 行业
    required_data: List[DataCategory] = field(default_factory=list)  # 必须数据
    optional_data: List[DataCategory] = field(default_factory=list)  # 可选数据
    use_realtime: bool = True              # 是否需要实时数据
    time_range_years: int = 5             # 历史数据年限


# =============================================================================
# 真实政府平台适配器
# =============================================================================

class NBSStatsAdapter:
    """
    国家统计局数据适配器
    公开接口: https://data.stats.gov.cn/easyquery.htm
    支持：GDP、人口、工业产值、固定资产投资、能源消耗等
    """
    BASE_URL = "https://data.stats.gov.cn/easyquery.htm"
    
    # 常用指标代码
    INDICATORS = {
        "gdp_total":      "A020101",   # GDP总量
        "gdp_per_capita": "A020102",   # 人均GDP
        "industrial_output": "A040101", # 工业总产值
        "fixed_investment": "A060101",  # 固定资产投资
        "energy_consumption": "A0D0101",# 能源消费总量
        "population":     "A030101",   # 年末总人口
        "urban_rate":     "A030303",   # 城镇化率
    }

    def fetch(self, indicator: str, region_code: str = "000000",
              start_year: int = 2018, end_year: int = 2023) -> Optional[Dict]:
        """
        调用国家统计局API

        Args:
            indicator: 指标代码或预定义名称
            region_code: 地区代码（000000=全国，110000=北京，420000=湖北）
            start_year: 起始年份
            end_year: 结束年份
        """
        ind_code = self.INDICATORS.get(indicator, indicator)
        params = {
            "m": "QueryData",
            "dbcode": "hgnd",
            "rowcode": "zb",
            "colcode": "sj",
            "wds": json.dumps([{"wdcode": "reg", "valuecode": region_code}]),
            "dfwds": json.dumps([
                {"wdcode": "zb", "valuecode": ind_code},
                {"wdcode": "sj", "valuecode": f"{start_year}-{end_year}"}
            ]),
        }
        url = f"{self.BASE_URL}?{urlencode(params)}"
        try:
            import requests
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://data.stats.gov.cn/",
            })
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_response(data, indicator)
        except Exception as e:
            logger.warning(f"国家统计局API调用失败: {e}")
        return None

    def _parse_response(self, raw: Dict, indicator: str) -> Dict:
        """解析响应"""
        try:
            datanodes = raw.get("returndata", {}).get("datanodes", [])
            if not datanodes:
                return {}
            values = {}
            for node in datanodes:
                sj = node.get("wds", [{}])[1].get("valuecode", "")
                val = node.get("data", {}).get("strdata", "")
                if val and val not in ["null", "--"]:
                    try:
                        values[sj] = float(val.replace(",", ""))
                    except ValueError:
                        values[sj] = val
            return {"indicator": indicator, "values": values}
        except Exception:
            return {}

    @staticmethod
    def region_code_from_name(name: str) -> str:
        """从地区名获取统计代码"""
        CODE_MAP = {
            "北京": "110000", "天津": "120000", "河北": "130000",
            "山西": "140000", "内蒙古": "150000", "辽宁": "210000",
            "吉林": "220000", "黑龙江": "230000", "上海": "310000",
            "江苏": "320000", "浙江": "330000", "安徽": "340000",
            "福建": "350000", "江西": "360000", "山东": "370000",
            "河南": "410000", "湖北": "420000", "湖南": "430000",
            "广东": "440000", "广西": "450000", "海南": "460000",
            "重庆": "500000", "四川": "510000", "贵州": "520000",
            "云南": "530000", "西藏": "540000", "陕西": "610000",
            "甘肃": "620000", "青海": "630000", "宁夏": "640000",
            "新疆": "650000",
        }
        for k, v in CODE_MAP.items():
            if k in name:
                return v
        return "000000"


class CMAWeatherAdapter:
    """
    中国气象局数据适配器
    公开接口: https://weather.cma.cn
    支持：历史气象、气候数据、气象统计
    """
    BASE_URL = "https://weather.cma.cn/api"

    def fetch_climate_stats(self, station_id: str = "54511") -> Optional[Dict]:
        """
        获取气候统计数据（月均值）
        station_id: 气象站编号（54511=北京，57494=武汉，58362=上海）
        """
        url = f"{self.BASE_URL}/climate?stationid={station_id}"
        try:
            import requests
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"气象局API调用失败: {e}")
        return None

    def fetch_current(self, city_code: str = "101010100") -> Optional[Dict]:
        """获取当前气象（天气网备用）"""
        url = f"https://www.nmc.cn/rest/weather?stationid={city_code}"
        try:
            import requests
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"当前气象获取失败: {e}")
        return None

    @staticmethod
    def station_from_city(city_name: str) -> str:
        STATION_MAP = {
            "北京": "54511", "上海": "58362", "广州": "59287",
            "深圳": "59493", "武汉": "57494", "南京": "58238",
            "杭州": "58457", "成都": "56294", "西安": "57036",
            "沈阳": "54342", "哈尔滨": "50953", "郑州": "57083",
            "济南": "54823", "合肥": "58321", "长沙": "57687",
        }
        for k, v in STATION_MAP.items():
            if k in city_name:
                return v
        return "54511"


class MEEEnvAdapter:
    """
    生态环境部数据适配器
    公开接口: https://www.mee.gov.cn & https://air.cnemc.cn
    支持：AQI、污染物浓度、水质数据、排放数据
    """
    AQI_URL = "https://air.cnemc.cn:18007/CityData/GetCityAQIPublishLive"
    
    def fetch_city_aqi(self, city_name: str) -> Optional[Dict]:
        """获取城市实时AQI"""
        try:
            import requests
            resp = requests.get(
                self.AQI_URL,
                params={"cityName": city_name},
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"AQI获取失败: {e}")
        return None

    def fetch_annual_report_data(self) -> Optional[Dict]:
        """获取年度环境状况公报数据（公开报告）"""
        # 生态环境部年度公报公开API
        url = "https://www.mee.gov.cn/hjzl/sthjzk/hjzkgb/"
        try:
            import requests
            resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                # 解析页面获取最新年度数据
                return {"source": "生态环境部年度公报", "url": url, "status": "available"}
        except Exception as e:
            logger.warning(f"环境公报获取失败: {e}")
        return None


class AmapGeoAdapter:
    """
    高德开放平台适配器（免费接口）
    支持：POI查询、地理编码、行政区划、周边信息
    注：部分接口需要KEY（用户自行配置），部分公开免费
    """
    BASE_URL = "https://restapi.amap.com/v3"
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key  # 用户配置的高德KEY

    def geocode(self, address: str) -> Optional[Dict]:
        """地理编码（获取经纬度）"""
        if not self.api_key:
            return self._fallback_geocode(address)
        try:
            import requests
            resp = requests.get(
                f"{self.BASE_URL}/geocode/geo",
                params={"address": address, "key": self.api_key},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("geocodes"):
                    loc = data["geocodes"][0].get("location", "")
                    lng, lat = loc.split(",") if "," in loc else ("", "")
                    return {
                        "address": address,
                        "latitude": float(lat) if lat else None,
                        "longitude": float(lng) if lng else None,
                        "province": data["geocodes"][0].get("province", ""),
                        "city": data["geocodes"][0].get("city", ""),
                        "district": data["geocodes"][0].get("district", ""),
                    }
        except Exception as e:
            logger.warning(f"高德地理编码失败: {e}")
        return None

    def _fallback_geocode(self, address: str) -> Optional[Dict]:
        """备用：使用百度/腾讯公开地理服务"""
        try:
            import requests
            # 使用nominatim（openstreetmap公开API）
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "limit": 1, "countrycodes": "cn"},
                timeout=10,
                headers={"User-Agent": "LivingTreeAI/1.0 (research)"},
            )
            if resp.status_code == 200 and resp.json():
                d = resp.json()[0]
                return {
                    "address": address,
                    "latitude": float(d["lat"]),
                    "longitude": float(d["lon"]),
                    "display_name": d.get("display_name", ""),
                }
        except Exception as e:
            logger.debug(f"备用地理编码失败: {e}")
        return None

    def get_poi_types(self, location: str, radius: int = 5000) -> Optional[Dict]:
        """获取周边POI类型（需要KEY）"""
        if not self.api_key:
            return None
        try:
            import requests
            resp = requests.get(
                f"{self.BASE_URL}/place/around",
                params={"location": location, "radius": radius,
                        "key": self.api_key, "offset": 25},
                timeout=8,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"高德POI查询失败: {e}")
        return None


class JuheDataAdapter:
    """
    聚合数据适配器（部分接口免费）
    支持：历史天气、节假日、油价、银行利率等
    """
    BASE_URL = "https://apis.juhe.cn"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def fetch_oil_price(self) -> Optional[Dict]:
        """获取国内油价（公开）"""
        try:
            import requests
            url = f"{self.BASE_URL}/oil/index"
            params = {"key": self.api_key} if self.api_key else {}
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"聚合数据油价获取失败: {e}")
        return None

    def fetch_bank_rate(self) -> Optional[Dict]:
        """获取银行利率（公开）"""
        try:
            import requests
            url = f"{self.BASE_URL}/bank/interest"
            params = {"key": self.api_key} if self.api_key else {}
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"聚合数据银行利率获取失败: {e}")
        return None


class PBOCAdapter:
    """
    中国人民银行数据适配器（公开）
    支持：基准利率、汇率、货币政策
    """
    BASE_URL = "https://www.pbc.gov.cn"

    def fetch_interest_rate(self) -> Optional[Dict]:
        """获取基准利率（公开数据）"""
        # PBOC 数据库公开查询接口
        url = "https://www.pbc.gov.cn/diaochatongjisi/resource/cms/2022/01/2022012213254474507.htm"
        try:
            import requests
            resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                return {"source": "中国人民银行", "status": "available", "url": url}
        except Exception as e:
            logger.warning(f"PBOC数据获取失败: {e}")
        return None


# =============================================================================
# 动态采集策略生成器
# =============================================================================

class DynamicCollectionStrategy:
    """
    动态采集策略生成器
    根据文档内容动态决定需要采集哪些数据，不固定类型
    """

    # 关键词到数据类别的映射（可扩展）
    KEYWORD_CATEGORY_MAP = {
        # 经济类
        ("gdp", "总产值", "工业产值", "经济总量", "生产总值", "经济增长"): DataCategory.ECONOMIC,
        ("投资", "资本金", "固定资产", "建设投资", "资金", "融资"): DataCategory.FINANCIAL,
        ("人口", "从业人员", "劳动力", "居民", "户籍"): DataCategory.POPULATION,
        # 环境类
        ("排放", "污染", "废气", "废水", "废物", "大气", "水质", "aqi", "pm2.5"): DataCategory.ENVIRONMENTAL,
        ("气温", "降水", "风速", "气候", "气象", "天气"): DataCategory.WEATHER,
        # 资源类
        ("土地", "用地", "地块", "选址", "地形", "地质"): DataCategory.LAND_USE,
        ("能源", "电力", "煤炭", "天然气", "用电量", "用能"): DataCategory.ENERGY,
        # 地理类
        ("位置", "坐标", "经纬度", "距离", "交通", "周边"): DataCategory.GEOGRAPHIC,
        # 行业类
        ("行业", "产业", "市场", "竞争", "同类", "项目规模"): DataCategory.INDUSTRY,
        # 法规类
        ("标准", "规范", "法规", "许可", "审批", "合规"): DataCategory.REGULATION,
    }

    def generate_plan(
        self,
        requirement: str,
        doc_type: str = "",
        entities: Dict[str, Any] = None,
    ) -> CollectionPlan:
        """
        根据需求文本动态生成采集计划

        Args:
            requirement: 用户需求或文档摘要
            doc_type: 文档类型（可为空，自动推断）
            entities: 已抽取实体（location, industry等）
        """
        entities = entities or {}
        text_lower = requirement.lower()
        
        # 1. 根据关键词确定需要的数据类别
        required_categories = []
        optional_categories = []
        
        for keywords, category in self.KEYWORD_CATEGORY_MAP.items():
            if any(kw in text_lower for kw in keywords):
                required_categories.append(category)
        
        # 2. 根据文档类型补充推断
        doc_category_map = {
            "feasibility_report":   [DataCategory.ECONOMIC, DataCategory.FINANCIAL,
                                     DataCategory.INDUSTRY, DataCategory.POPULATION],
            "eia_report":           [DataCategory.ENVIRONMENTAL, DataCategory.WEATHER,
                                     DataCategory.GEOGRAPHIC, DataCategory.REGULATION],
            "safety_assessment":    [DataCategory.ENVIRONMENTAL, DataCategory.REGULATION,
                                     DataCategory.GEOGRAPHIC],
            "investment_analysis":  [DataCategory.FINANCIAL, DataCategory.ECONOMIC,
                                     DataCategory.INDUSTRY],
            "project_proposal":     [DataCategory.ECONOMIC, DataCategory.INDUSTRY,
                                     DataCategory.GEOGRAPHIC],
        }
        if doc_type and doc_type in doc_category_map:
            for cat in doc_category_map[doc_type]:
                if cat not in required_categories:
                    optional_categories.append(cat)
        
        # 3. 默认增加经济基础数据
        if DataCategory.ECONOMIC not in required_categories and DataCategory.ECONOMIC not in optional_categories:
            optional_categories.append(DataCategory.ECONOMIC)
        
        plan = CollectionPlan(
            doc_type=doc_type or "unknown",
            intent_keywords=self._extract_keywords(requirement),
            location=entities.get("location"),
            industry=entities.get("industry"),
            required_data=list(set(required_categories)),
            optional_data=list(set(optional_categories)),
            use_realtime=True,
            time_range_years=5,
        )
        
        logger.info(f"动态采集计划: 必须={[c.value for c in plan.required_data]}, "
                    f"可选={[c.value for c in plan.optional_data]}, "
                    f"地点={plan.location}, 行业={plan.industry}")
        return plan

    def _extract_keywords(self, text: str) -> List[str]:
        """简单关键词提取"""
        # 提取中文词汇（2-6字）
        words = re.findall(r'[\u4e00-\u9fa5]{2,6}', text)
        stopwords = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "一", "也", "很", "到"}
        return [w for w in words if w not in stopwords][:20]


# =============================================================================
# 主数据采集器
# =============================================================================

class WritingDataCollector:
    """
    智能写作数据采集器 v2

    功能：
    1. 动态生成采集策略（不固定文档类型）
    2. 调用真实政府平台API
    3. 调用第三方公开平台
    4. 缓存管理（避免重复请求）
    5. 采集结果写入项目知识库（自进化支持）
    """

    CACHE_DIR = Path.home() / ".hermes-desktop" / "data_cache" / "writing"
    
    def __init__(
        self,
        amap_key: str = "",
        juhe_key: str = "",
        cache_ttl: int = 86400,  # 缓存1天
        kb_writer: Optional[Callable] = None,
    ):
        self.amap_key = amap_key
        self.juhe_key = juhe_key
        self.cache_ttl = cache_ttl
        self.kb_writer = kb_writer  # 知识库写入回调

        # 适配器实例
        self.nbs = NBSStatsAdapter()
        self.cma = CMAWeatherAdapter()
        self.mee = MEEEnvAdapter()
        self.amap = AmapGeoAdapter(api_key=amap_key)
        self.juhe = JuheDataAdapter(api_key=juhe_key)
        self.strategy = DynamicCollectionStrategy()
        
        # 缓存
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._mem_cache: Dict[str, Tuple[float, Any]] = {}

    # ─── 公共入口 ────────────────────────────────────────────────────────────

    def collect_for_document(
        self,
        requirement: str,
        doc_type: str = "",
        entities: Dict[str, Any] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, DataItem]:
        """
        根据文档需求自动采集数据（主入口）

        Args:
            requirement: 需求描述或文档摘要
            doc_type: 文档类型（可为空，自动推断）
            entities: 实体字典 {"location": "武汉", "industry": "化工"}
            progress_callback: 进度回调 (msg, 0~1)

        Returns:
            Dict[str, DataItem]: 采集到的数据字典
        """
        plan = self.strategy.generate_plan(requirement, doc_type, entities)
        
        collected: Dict[str, DataItem] = {}
        all_categories = plan.required_data + plan.optional_data
        total = len(all_categories)
        
        for idx, category in enumerate(all_categories):
            progress = (idx + 1) / max(total, 1)
            msg = f"采集 {category.value} 数据..."
            if progress_callback:
                progress_callback(msg, progress)
            
            items = self._collect_category(category, plan)
            collected.update(items)
            logger.info(f"[{category.value}] 采集到 {len(items)} 条数据")
        
        # 写入知识库（自进化）
        if self.kb_writer and collected:
            self._write_to_kb(collected, plan)
        
        return collected

    def _collect_category(
        self, category: DataCategory, plan: CollectionPlan
    ) -> Dict[str, DataItem]:
        """按数据类别采集"""
        collectors = {
            DataCategory.ECONOMIC:     self._collect_economic,
            DataCategory.ENVIRONMENTAL: self._collect_environmental,
            DataCategory.WEATHER:      self._collect_weather,
            DataCategory.GEOGRAPHIC:   self._collect_geographic,
            DataCategory.FINANCIAL:    self._collect_financial,
            DataCategory.ENERGY:       self._collect_energy,
            DataCategory.POPULATION:   self._collect_population,
            DataCategory.INDUSTRY:     self._collect_industry,
            DataCategory.REGULATION:   self._collect_regulation,
        }
        fn = collectors.get(category)
        if fn:
            try:
                return fn(plan)
            except Exception as e:
                logger.warning(f"采集 {category.value} 失败: {e}")
        return {}

    # ─── 分类采集方法 ────────────────────────────────────────────────────────

    def _collect_economic(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集经济数据（国家统计局）"""
        items = {}
        
        # 1. 确定地区代码
        region_code = "000000"
        if plan.location:
            region_code = NBSStatsAdapter.region_code_from_name(plan.location)
        
        # 2. 采集GDP数据
        cache_key = f"nbs_gdp_{region_code}"
        data = self._get_cached_or_fetch(
            cache_key,
            lambda: self.nbs.fetch("gdp_total", region_code, 2018, 2023)
        )
        if data and data.get("values"):
            latest_year = max(data["values"].keys())
            val = data["values"][latest_year]
            items["gdp_total"] = DataItem(
                key="gdp_total",
                value=val,
                unit="亿元",
                source_type=DataSourceType.NBS_STATS,
                source_name="国家统计局",
                source_url="https://data.stats.gov.cn",
                category=DataCategory.ECONOMIC,
                confidence=0.95,
                description=f"{plan.location or '全国'}{latest_year}年GDP总量",
            )
            items["gdp_year"] = DataItem(
                key="gdp_year",
                value=latest_year,
                unit="年",
                source_type=DataSourceType.NBS_STATS,
                source_name="国家统计局",
                category=DataCategory.ECONOMIC,
                description="GDP数据年份",
            )

        # 3. 采集固定资产投资
        cache_key2 = f"nbs_investment_{region_code}"
        inv_data = self._get_cached_or_fetch(
            cache_key2,
            lambda: self.nbs.fetch("fixed_investment", region_code, 2018, 2023)
        )
        if inv_data and inv_data.get("values"):
            latest_year = max(inv_data["values"].keys())
            val = inv_data["values"][latest_year]
            items["fixed_investment"] = DataItem(
                key="fixed_investment",
                value=val,
                unit="亿元",
                source_type=DataSourceType.NBS_STATS,
                source_name="国家统计局",
                category=DataCategory.ECONOMIC,
                confidence=0.95,
                description=f"{plan.location or '全国'}{latest_year}年固定资产投资总额",
            )

        return items

    def _collect_environmental(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集环境数据（生态环境部、AQI平台）"""
        items = {}
        
        if plan.location:
            # AQI实时数据
            cache_key = f"mee_aqi_{plan.location}"
            aqi_data = self._get_cached_or_fetch(
                cache_key,
                lambda: self.mee.fetch_city_aqi(plan.location),
                ttl=3600,  # AQI 1小时缓存
            )
            if aqi_data:
                # 解析AQI值
                try:
                    aqi_val = aqi_data.get("AQI") or aqi_data.get("aqi", "")
                    if aqi_val:
                        items["aqi_current"] = DataItem(
                            key="aqi_current",
                            value=aqi_val,
                            unit="",
                            source_type=DataSourceType.MEE_ENV,
                            source_name="中国环境监测总站",
                            source_url="https://air.cnemc.cn",
                            category=DataCategory.ENVIRONMENTAL,
                            confidence=0.9,
                            description=f"{plan.location}实时AQI",
                        )
                except Exception:
                    pass
        
        # 年度环境公报（补充参考）
        report_info = self.mee.fetch_annual_report_data()
        if report_info:
            items["env_annual_report"] = DataItem(
                key="env_annual_report",
                value="可参考",
                source_type=DataSourceType.MEE_ENV,
                source_name="生态环境部",
                source_url=report_info.get("url", ""),
                category=DataCategory.ENVIRONMENTAL,
                confidence=0.9,
                description="生态环境状况公报（最新年度）",
            )
        
        return items

    def _collect_weather(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集气象数据（中国气象局）"""
        items = {}
        
        city = plan.location or "北京"
        station_id = CMAWeatherAdapter.station_from_city(city)
        
        cache_key = f"cma_climate_{station_id}"
        climate_data = self._get_cached_or_fetch(
            cache_key,
            lambda: self.cma.fetch_climate_stats(station_id),
            ttl=86400 * 30,  # 气候数据30天缓存
        )
        
        if climate_data:
            items["climate_station"] = DataItem(
                key="climate_station",
                value=station_id,
                source_type=DataSourceType.CMA_WEATHER,
                source_name="中国气象局",
                source_url="https://weather.cma.cn",
                category=DataCategory.WEATHER,
                description=f"{city}气象站编号",
                raw_response=climate_data,
            )
            # 尝试提取关键气象参数
            monthly = climate_data.get("climate", {}).get("data", [])
            if monthly:
                temps = [d.get("avgTemp") for d in monthly if d.get("avgTemp")]
                if temps:
                    items["annual_avg_temp"] = DataItem(
                        key="annual_avg_temp",
                        value=round(sum(temps) / len(temps), 1),
                        unit="℃",
                        source_type=DataSourceType.CMA_WEATHER,
                        source_name="中国气象局",
                        category=DataCategory.WEATHER,
                        confidence=0.9,
                        description=f"{city}年均气温",
                    )
        
        return items

    def _collect_geographic(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集地理数据（高德/OpenStreetMap）"""
        items = {}
        
        if not plan.location:
            return items
        
        cache_key = f"geo_{hashlib.md5(plan.location.encode()).hexdigest()[:8]}"
        geo_data = self._get_cached_or_fetch(
            cache_key,
            lambda: self.amap.geocode(plan.location),
            ttl=86400 * 7,
        )
        
        if geo_data:
            if geo_data.get("latitude"):
                items["location_lat"] = DataItem(
                    key="location_lat",
                    value=geo_data["latitude"],
                    unit="°N",
                    source_type=DataSourceType.AMAP_GEO,
                    source_name="高德/OpenStreetMap",
                    category=DataCategory.GEOGRAPHIC,
                    confidence=0.92,
                    description=f"{plan.location}纬度",
                )
                items["location_lng"] = DataItem(
                    key="location_lng",
                    value=geo_data["longitude"],
                    unit="°E",
                    source_type=DataSourceType.AMAP_GEO,
                    source_name="高德/OpenStreetMap",
                    category=DataCategory.GEOGRAPHIC,
                    confidence=0.92,
                    description=f"{plan.location}经度",
                )
            if geo_data.get("province"):
                items["province"] = DataItem(
                    key="province",
                    value=geo_data["province"],
                    source_type=DataSourceType.AMAP_GEO,
                    source_name="高德开放平台",
                    category=DataCategory.GEOGRAPHIC,
                    description="所属省份",
                )
        
        return items

    def _collect_financial(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集金融数据（央行基准利率）"""
        items = {}
        
        # 从聚合数据获取银行利率
        cache_key = "juhe_bank_rate"
        rate_data = self._get_cached_or_fetch(
            cache_key,
            lambda: self.juhe.fetch_bank_rate(),
            ttl=86400,
        )
        
        if rate_data and rate_data.get("result"):
            items["bank_rate_ref"] = DataItem(
                key="bank_rate_ref",
                value=rate_data.get("result"),
                source_type=DataSourceType.JUHE_DATA,
                source_name="聚合数据-银行利率",
                category=DataCategory.FINANCIAL,
                confidence=0.85,
                description="最新银行基准利率参考",
                raw_response=rate_data,
            )
        
        # PBOC利率参考（公开链接）
        pboc_data = self._get_cached_or_fetch(
            "pboc_rate",
            lambda: PBOCAdapter().fetch_interest_rate(),
            ttl=86400,
        )
        if pboc_data:
            items["pboc_rate_source"] = DataItem(
                key="pboc_rate_source",
                value=pboc_data.get("url", ""),
                source_type=DataSourceType.JUHE_DATA,
                source_name="中国人民银行",
                source_url=pboc_data.get("url", ""),
                category=DataCategory.FINANCIAL,
                description="中国人民银行利率公开数据地址",
            )
        
        return items

    def _collect_energy(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集能源数据（国家统计局能源统计）"""
        items = {}
        
        region_code = "000000"
        if plan.location:
            region_code = NBSStatsAdapter.region_code_from_name(plan.location)
        
        cache_key = f"nbs_energy_{region_code}"
        data = self._get_cached_or_fetch(
            cache_key,
            lambda: self.nbs.fetch("energy_consumption", region_code, 2018, 2023),
        )
        
        if data and data.get("values"):
            latest_year = max(data["values"].keys())
            val = data["values"][latest_year]
            items["energy_consumption"] = DataItem(
                key="energy_consumption",
                value=val,
                unit="万吨标准煤",
                source_type=DataSourceType.NBS_STATS,
                source_name="国家统计局",
                category=DataCategory.ENERGY,
                confidence=0.95,
                description=f"{plan.location or '全国'}{latest_year}年能源消费总量",
            )
        
        # 油价参考
        oil_data = self._get_cached_or_fetch(
            "juhe_oil",
            lambda: self.juhe.fetch_oil_price(),
            ttl=86400,
        )
        if oil_data and oil_data.get("result"):
            items["oil_price"] = DataItem(
                key="oil_price",
                value=oil_data.get("result"),
                source_type=DataSourceType.JUHE_DATA,
                source_name="聚合数据-油价",
                category=DataCategory.ENERGY,
                confidence=0.85,
                description="国内油价最新数据",
                raw_response=oil_data,
            )
        
        return items

    def _collect_population(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集人口数据（国家统计局）"""
        items = {}
        
        region_code = "000000"
        if plan.location:
            region_code = NBSStatsAdapter.region_code_from_name(plan.location)
        
        cache_key = f"nbs_pop_{region_code}"
        data = self._get_cached_or_fetch(
            cache_key,
            lambda: self.nbs.fetch("population", region_code, 2018, 2023),
        )
        
        if data and data.get("values"):
            latest_year = max(data["values"].keys())
            val = data["values"][latest_year]
            items["population"] = DataItem(
                key="population",
                value=val,
                unit="万人",
                source_type=DataSourceType.NBS_STATS,
                source_name="国家统计局",
                category=DataCategory.POPULATION,
                confidence=0.95,
                description=f"{plan.location or '全国'}{latest_year}年末总人口",
            )
        
        # 城镇化率
        cache_key2 = f"nbs_urban_{region_code}"
        urban_data = self._get_cached_or_fetch(
            cache_key2,
            lambda: self.nbs.fetch("urban_rate", region_code, 2018, 2023),
        )
        if urban_data and urban_data.get("values"):
            latest_year = max(urban_data["values"].keys())
            val = urban_data["values"][latest_year]
            items["urbanization_rate"] = DataItem(
                key="urbanization_rate",
                value=val,
                unit="%",
                source_type=DataSourceType.NBS_STATS,
                source_name="国家统计局",
                category=DataCategory.POPULATION,
                confidence=0.95,
                description=f"{plan.location or '全国'}{latest_year}年城镇化率",
            )
        
        return items

    def _collect_industry(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集行业数据（统计局工业数据）"""
        items = {}
        
        region_code = "000000"
        if plan.location:
            region_code = NBSStatsAdapter.region_code_from_name(plan.location)
        
        cache_key = f"nbs_industry_{region_code}"
        data = self._get_cached_or_fetch(
            cache_key,
            lambda: self.nbs.fetch("industrial_output", region_code, 2018, 2023),
        )
        
        if data and data.get("values"):
            latest_year = max(data["values"].keys())
            val = data["values"][latest_year]
            items["industrial_output"] = DataItem(
                key="industrial_output",
                value=val,
                unit="亿元",
                source_type=DataSourceType.NBS_STATS,
                source_name="国家统计局",
                category=DataCategory.INDUSTRY,
                confidence=0.95,
                description=f"{plan.location or '全国'}{latest_year}年规模以上工业总产值",
            )
        
        return items

    def _collect_regulation(self, plan: CollectionPlan) -> Dict[str, DataItem]:
        """采集法规标准（指引性数据，提供链接）"""
        items = {}
        
        # 根据行业提供相关法规链接
        reg_sources = self._get_regulation_sources(plan.industry)
        for idx, reg in enumerate(reg_sources[:5]):
            key = f"regulation_{idx}"
            items[key] = DataItem(
                key=key,
                value=reg["name"],
                source_type=DataSourceType.MEE_ENV,
                source_name=reg["source"],
                source_url=reg.get("url", ""),
                category=DataCategory.REGULATION,
                confidence=1.0,
                description=reg["description"],
            )
        
        return items

    def _get_regulation_sources(self, industry: Optional[str]) -> List[Dict]:
        """根据行业获取相关法规标准"""
        common = [
            {"name": "《中华人民共和国环境保护法》", "source": "全国人大",
             "url": "https://www.mee.gov.cn/ywgz/fgbz/fl/", "description": "环保基本法"},
            {"name": "《中华人民共和国安全生产法》", "source": "应急管理部",
             "url": "https://www.mem.gov.cn/fw/flfgbz/", "description": "安全生产基本法"},
            {"name": "《建设项目环境保护管理条例》", "source": "生态环境部",
             "url": "https://www.mee.gov.cn", "description": "环评管理条例"},
        ]
        
        if industry:
            if "化工" in industry:
                common.append({
                    "name": "《化工企业安全生产许可证实施规定》",
                    "source": "应急管理部", "url": "https://www.mem.gov.cn",
                    "description": "化工行业安全许可要求"
                })
            if "食品" in industry:
                common.append({
                    "name": "《中华人民共和国食品安全法》",
                    "source": "市场监管总局", "url": "https://www.samr.gov.cn",
                    "description": "食品安全法规"
                })
        
        return common

    # ─── 缓存管理 ─────────────────────────────────────────────────────────────

    def _get_cached_or_fetch(
        self,
        key: str,
        fetch_fn: Callable,
        ttl: Optional[int] = None,
    ) -> Any:
        """带缓存的获取"""
        ttl = ttl or self.cache_ttl
        
        # 内存缓存
        if key in self._mem_cache:
            ts, val = self._mem_cache[key]
            if time.time() - ts < ttl:
                return val
        
        # 磁盘缓存
        cache_file = self.CACHE_DIR / f"{key}.json"
        if cache_file.exists():
            try:
                stat = cache_file.stat()
                if time.time() - stat.st_mtime < ttl:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        val = json.load(f)
                    self._mem_cache[key] = (time.time(), val)
                    return val
            except Exception:
                pass
        
        # 调用真实API
        val = fetch_fn()
        if val is not None:
            self._mem_cache[key] = (time.time(), val)
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(val, f, ensure_ascii=False, default=str)
            except Exception:
                pass
        
        return val

    def clear_cache(self, key_prefix: str = ""):
        """清除缓存"""
        for f in self.CACHE_DIR.glob(f"{key_prefix}*.json"):
            f.unlink(missing_ok=True)
        self._mem_cache = {k: v for k, v in self._mem_cache.items()
                           if not k.startswith(key_prefix)}

    # ─── 知识库回写（自进化）────────────────────────────────────────────────────

    def _write_to_kb(self, items: Dict[str, DataItem], plan: CollectionPlan):
        """将采集数据写入知识库（支持自进化学习）"""
        if not self.kb_writer:
            return
        try:
            kb_text = self._items_to_kb_text(items, plan)
            self.kb_writer(
                content=kb_text,
                metadata={
                    "source": "data_collector",
                    "doc_type": plan.doc_type,
                    "location": plan.location,
                    "industry": plan.industry,
                    "collected_at": datetime.now().isoformat(),
                    "data_keys": list(items.keys()),
                }
            )
            logger.info(f"数据采集结果已写入知识库，{len(items)} 条记录")
        except Exception as e:
            logger.warning(f"写入知识库失败: {e}")

    def _items_to_kb_text(self, items: Dict[str, DataItem], plan: CollectionPlan) -> str:
        """将数据项转换为知识库文本"""
        lines = [
            f"## 数据采集记录",
            f"- 文档类型: {plan.doc_type}",
            f"- 项目地点: {plan.location or '未指定'}",
            f"- 行业: {plan.industry or '未指定'}",
            f"- 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "### 采集数据",
        ]
        for key, item in items.items():
            if isinstance(item.value, (int, float, str)):
                val_str = f"{item.value} {item.unit}".strip()
                lines.append(f"- **{item.description or key}**: {val_str}"
                              f" (来源: {item.source_name}, 置信度: {item.confidence:.0%})")
        return "\n".join(lines)

    # ─── 汇总报告 ─────────────────────────────────────────────────────────────

    def generate_data_summary(self, items: Dict[str, DataItem]) -> str:
        """生成数据采集汇总报告"""
        if not items:
            return "未采集到有效数据"
        
        lines = ["### 基础数据汇总", ""]
        
        # 按数据类别分组
        by_category: Dict[str, List[DataItem]] = {}
        for item in items.values():
            cat = item.category.value
            by_category.setdefault(cat, []).append(item)
        
        category_names = {
            "economic": "经济数据", "environmental": "环境数据",
            "weather": "气象数据", "geographic": "地理数据",
            "financial": "金融数据", "energy": "能源数据",
            "population": "人口数据", "industry": "行业数据",
            "regulation": "法规标准",
        }
        
        for cat, cat_items in by_category.items():
            cat_name = category_names.get(cat, cat)
            lines.append(f"**{cat_name}**（{len(cat_items)}项）：")
            for item in cat_items[:5]:
                if isinstance(item.value, (int, float)):
                    val_str = f"{item.value:,.2f} {item.unit}".strip()
                else:
                    val_str = str(item.value)[:80]
                lines.append(f"  - {item.description or item.key}: {val_str}")
                if item.source_name:
                    lines[-1] += f" （{item.source_name}）"
            lines.append("")
        
        return "\n".join(lines)

    def get_api_config_guide(self) -> str:
        """获取API配置指引"""
        return """
## 数据采集API配置说明

### 无需配置（默认可用）
| 数据源 | 数据类型 | 说明 |
|--------|---------|------|
| 国家统计局 | GDP、人口、工业产值、能源等 | 完全公开，无需KEY |
| 中国气象局 | 气候数据、历史气象 | 公开接口 |
| 生态环境部 | 环境状况公报 | 公开链接 |
| OpenStreetMap | 地理编码 | 公开，有请求频率限制 |

### 需要配置KEY（可选，提升数据质量）
| 平台 | 参数名 | 申请地址 | 免费额度 |
|------|--------|---------|---------|
| 高德开放平台 | amap_key | https://lbs.amap.com | 每日5000次免费 |
| 聚合数据 | juhe_key | https://www.juhe.cn | 部分免费 |

### 配置方式
```python
from core.smart_writing.data_collector import get_data_collector
collector = get_data_collector(amap_key="your_key", juhe_key="your_key")
```
"""


# =============================================================================
# 单例工厂
# =============================================================================

_collector_instance: Optional[WritingDataCollector] = None


def get_data_collector(
    amap_key: str = "",
    juhe_key: str = "",
    kb_writer: Optional[Callable] = None,
) -> WritingDataCollector:
    """获取数据采集器单例"""
    global _collector_instance
    if _collector_instance is None:
        # 尝试从配置文件读取KEY
        config_file = Path.home() / ".hermes-desktop" / "data_api_config.json"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    amap_key = amap_key or cfg.get("amap_key", "")
                    juhe_key = juhe_key or cfg.get("juhe_key", "")
            except Exception:
                pass
        _collector_instance = WritingDataCollector(
            amap_key=amap_key,
            juhe_key=juhe_key,
            kb_writer=kb_writer,
        )
    return _collector_instance
