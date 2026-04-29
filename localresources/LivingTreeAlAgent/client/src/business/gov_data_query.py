"""
政府开放资料查询系统 V2.0 - GovDataQuery
GovDataQuery - Global Government Open Data Query

设计思路 (借鉴 gov_openapi_agent / moenv_openapi_agent):
1. 通过自然语言查询全球政府开放资料
2. 支持多地区/多国家数据平台
3. OpenAPI 规范动态加载 API 工具
4. 统一认证管理 + 备用爬虫方案
5. 结果自然语言展示

支持的地区：
- 🇨🇳 中国大陆：国家统计局、各省市政府数据平台、部委数据
- 🇹🇼 台湾：环保署、交通部、水利署、气象局
- 🇭🇰 香港：政府资料一线通
- 🇲🇴 澳门：统计暨普查局
- 🌍 全球：美国 data.gov、欧盟 open data、各国政府开放平台
"""

import json
import re
import time
import socket
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import urllib.request
import urllib.parse
import urllib.error


class RegionType(Enum):
    """地区类型"""
    # 大中华区
    CN = "cn"           # 中国大陆
    TW = "tw"           # 台湾
    HK = "hk"           # 香港
    MO = "mo"           # 澳门

    # 全球
    US = "us"           # 美国
    EU = "eu"           # 欧盟
    JP = "jp"           # 日本
    KR = "kr"           # 韩国
    SG = "sg"           # 新加坡
    GLOBAL = "global"   # 全球综合


class PlatformType(Enum):
    """平台类型"""
    # 🇨🇳 中国大陆
    CN_STATS = "cn_stats"           # 国家统计局
    CN_CHINADATA = "cn_chinadata"     # chinadata.live 替代接口
    CN_GOVOPEN = "cn_govopen"         # 各省市政府数据开放平台

    # 🇹🇼 台湾
    MOENV = "moenv"           # 环保署
    TDX = "tdx"               # 交通部运输资料
    WRA = "wra"               # 经济部水利署
    CWA = "cwa"               # 气象局

    # 🇭🇰 香港
    HK_GOV = "hk_gov"         # 香港政府资料一线通

    # 🇲🇴 澳门
    MO_STAT = "mo_stat"        # 澳门统计暨普查局

    # 🌍 全球
    US_DATA_GOV = "us_data_gov"   # 美国政府开放平台
    EU_OPEN_DATA = "eu_open_data"  # 欧盟开放数据
    WORLD_BANK = "world_bank"      # 世界银行
    UN_DATA = "un_data"            # 联合国数据


@dataclass
class ApiEndpoint:
    """API 端点定义"""
    name: str          # 端点名称（中文）
    name_en: str       # 端点名称（英文）
    path: str          # API 路径
    method: str = "GET"
    description: str = ""
    params: List[Dict] = field(default_factory=list)
    auth_required: bool = False


@dataclass
class PlatformConfig:
    """平台配置"""
    id: str
    name: str                          # 平台名称（中文）
    name_en: str                       # 平台名称（英文）
    region: RegionType                  # 所属地区
    base_url: str                      # API 基础 URL
    auth_type: str                     # "api_key", "oauth2", "none", "cnstats"
    auth_env_var: Optional[str] = None
    oauth2_config: Optional[Dict] = None
    endpoints: List[ApiEndpoint] = field(default_factory=list)
    enabled: bool = True
    # 备用方案（当 API 不可用时）
    fallback_url: Optional[str] = None
    fallback_type: Optional[str] = None  # "web_scraper", "csv", "json"


@dataclass
class QueryResult:
    """查询结果"""
    success: bool
    platform: str
    platform_en: str
    endpoint: str
    region: str
    data: Any = None
    error: Optional[str] = None
    raw_response: Optional[Dict] = None
    timestamp: float = field(default_factory=time.time)


class GovDataQuery:
    """
    全球政府开放资料查询核心类

    使用方式：
    1. 初始化时加载各平台配置
    2. 通过自然语言查询接口获取数据
    3. 结果自动转换为自然语言描述

    地区覆盖：
    - 🇨🇳 中国大陆：国家统计局 API、省市政府数据平台
    - 🇹🇼 台湾：环保署、交通部、水利署、气象局
    - 🇭🇰 香港：政府资料一线通
    - 🇲🇴 澳门：统计暨普查局
    - 🌍 全球：美国、欧盟、日本、韩国、新加坡等
    """

    # 地区名称映射
    REGION_NAMES = {
        RegionType.CN: "🇨🇳 中国大陆",
        RegionType.TW: "🇹🇼 台湾",
        RegionType.HK: "🇭🇰 香港",
        RegionType.MO: "🇲🇴 澳门",
        RegionType.US: "🇺🇸 美国",
        RegionType.EU: "🇪🇺 欧盟",
        RegionType.JP: "🇯🇵 日本",
        RegionType.KR: "🇰🇷 韩国",
        RegionType.SG: "🇸🇬 新加坡",
        RegionType.GLOBAL: "🌍 全球",
    }

    # 平台配置
    PLATFORMS: Dict[str, PlatformConfig] = {}

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化政府资料查询系统

        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent / "gov_openapi_specs"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 运行时数据
        self._auth_tokens: Dict[str, str] = {}
        self._token_expires: Dict[str, float] = {}
        self._cn_stats_available = True  # cn-stats 库可用性

        # 加载平台配置
        self._init_platforms()
        self._check_cnstats()

    def _init_platforms(self):
        """初始化所有平台配置"""
        self._init_cn_platforms()
        self._init_tw_platforms()
        self._init_hk_mo_platforms()
        self._init_global_platforms()

    def _init_cn_platforms(self):
        """初始化中国大陆平台"""
        # 国家统计局 (cn-stats 库)
        self.PLATFORMS[PlatformType.CN_STATS.value] = PlatformConfig(
            id="cn_stats",
            name="国家统计局",
            name_en="National Bureau of Statistics of China",
            region=RegionType.CN,
            base_url="https://data.stats.gov.cn/api",
            auth_type="cnstats",
            endpoints=[
                ApiEndpoint(
                    name="国内生产总值(GDP)",
                    name_en="GDP",
                    path="easyquery",
                    description="季度/年度国民经济核算数据",
                    params=[{"name": "zbcode", "description": "指标代码", "required": True}]
                ),
                ApiEndpoint(
                    name="居民消费价格指数(CPI)",
                    name_en="CPI",
                    path="easyquery",
                    description="通货膨胀指标",
                    params=[]
                ),
                ApiEndpoint(
                    name="工业增加值",
                    name_en="Industrial Added Value",
                    path="easyquery",
                    description="工业生产指数",
                    params=[]
                ),
                ApiEndpoint(
                    name="固定资产投资",
                    name_en="Fixed Asset Investment",
                    path="easyquery",
                    description="固定资产投资数据",
                    params=[]
                ),
                ApiEndpoint(
                    name="社会消费品零售总额",
                    name_en="Total Retail Sales",
                    path="easyquery",
                    description="消费数据",
                    params=[]
                ),
                ApiEndpoint(
                    name="货币供应量",
                    name_en="Money Supply",
                    path="easyquery",
                    description="M0/M1/M2货币供应量",
                    params=[]
                ),
                ApiEndpoint(
                    name="城镇调查失业率",
                    name_en="Urban Unemployment Rate",
                    path="easyquery",
                    description="就业数据",
                    params=[]
                ),
                ApiEndpoint(
                    name="分省年度数据",
                    name_en="Provincial Annual Data",
                    path="easyquery",
                    description="各省份年度统计指标",
                    params=[{"name": "regcode", "description": "地区代码", "required": False}]
                ),
            ]
        )

        # chinadata.live 替代 API (无需认证)
        self.PLATFORMS[PlatformType.CN_CHINADATA.value] = PlatformConfig(
            id="cn_chinadata",
            name="中国宏观数据(备用)",
            name_en="China Macro Data (Alternative)",
            region=RegionType.CN,
            base_url="https://chinadata.live/api/v2/data",
            auth_type="none",
            fallback_type="json",
            endpoints=[
                ApiEndpoint(
                    name="新能源汽车销量对比",
                    name_en="EV Sales Comparison",
                    path="ev-sales-comparison",
                    description="中国vs美国新能源汽车销量",
                    params=[]
                ),
                ApiEndpoint(
                    name="GDP增速",
                    name_en="GDP Growth Rate",
                    path="china-gdp-growth",
                    description="中国GDP季度增速",
                    params=[]
                ),
                ApiEndpoint(
                    name="CPI同比",
                    name_en="CPI YoY",
                    path="china-cpi-yoy",
                    description="居民消费价格指数同比",
                    params=[]
                ),
                ApiEndpoint(
                    name="PPI同比",
                    name_en="PPI YoY",
                    path="china-ppi-yoy",
                    description="生产者物价指数同比",
                    params=[]
                ),
                ApiEndpoint(
                    name="贸易顺差",
                    name_en="Trade Surplus",
                    path="china-trade-surplus",
                    description="进出口贸易差额",
                    params=[]
                ),
                ApiEndpoint(
                    name="外汇储备",
                    name_en="Foreign Exchange Reserves",
                    path="china-forex-reserves",
                    description="外汇储备数据",
                    params=[]
                ),
            ]
        )

        # 各省市政府数据开放平台 (通用配置)
        self.PLATFORMS[PlatformType.CN_GOVOPEN.value] = PlatformConfig(
            id="cn_govopen",
            name="省级政府数据开放平台",
            name_en="Provincial Government Open Data",
            region=RegionType.CN,
            base_url="https://data.{province}.gov.cn/api",
            auth_type="none",
            fallback_type="web_scraper",
            endpoints=[
                ApiEndpoint(
                    name="环境质量数据",
                    name_en="Environmental Quality",
                    path="/resource/query",
                    description="空气质量、水质等环境监测数据",
                    params=[{"name": "type", "description": "数据类型", "required": False}]
                ),
                ApiEndpoint(
                    name="公共设施数据",
                    name_en="Public Facilities",
                    path="/resource/query",
                    description="学校、医院等公共设施分布",
                    params=[]
                ),
                ApiEndpoint(
                    name="企业信用数据",
                    name_en="Business Credit",
                    path="/resource/query",
                    description="企业信用信息",
                    params=[]
                ),
            ]
        )

    def _init_tw_platforms(self):
        """初始化台湾平台"""
        # 环保署
        self.PLATFORMS[PlatformType.MOENV.value] = PlatformConfig(
            id="moenv",
            name="环保署环境资料开放平台",
            name_en="MOENV Open Data",
            region=RegionType.TW,
            base_url="https://data.moenv.gov.tw/api",
            auth_type="api_key",
            auth_env_var="MOENV_API_KEY",
            endpoints=[
                ApiEndpoint(
                    name="空气品质预报资料",
                    name_en="Air Quality Forecast",
                    path="/v2/airquantityforecast",
                    description="未来72小时空气品质预报",
                    params=[]
                ),
                ApiEndpoint(
                    name="空气质量监测资料",
                    name_en="Air Quality Monitoring",
                    path="/v3/airquality",
                    description="实时空气质量监测数据",
                    params=[{"name": "city", "description": "县市名称", "required": False}]
                ),
                ApiEndpoint(
                    name="PM2.5监测资料",
                    name_en="PM2.5 Monitoring",
                    path="/v2/pm25",
                    description="细悬浮微粒(PM2.5)监测数据",
                    params=[]
                ),
                ApiEndpoint(
                    name="酸雨监测资料",
                    name_en="Acid Rain Monitoring",
                    path="/v2/acidrain",
                    description="酸雨监测历史资料",
                    params=[{"name": "date", "description": "日期", "required": False}]
                ),
            ]
        )

        # 交通部 TDX
        self.PLATFORMS[PlatformType.TDX.value] = PlatformConfig(
            id="tdx",
            name="交通部运输资料流通服务平台",
            name_en="TDX Transport Data",
            region=RegionType.TW,
            base_url="https://tdx.transportdata.tw/api",
            auth_type="oauth2",
            oauth2_config={
                "client_id_env": "TDX_CLIENT_ID",
                "client_secret_env": "TDX_CLIENT_SECRET",
                "token_url": "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
            },
            endpoints=[
                ApiEndpoint(
                    name="公交动态资料",
                    name_en="Bus Real-time Data",
                    path="/v2/api/Bus/RealTimeByCity",
                    description="市区公车实时到站资讯",
                    params=[{"name": "city", "description": "县市编码", "required": False}]
                ),
                ApiEndpoint(
                    name="高铁时刻表",
                    name_en="THSRC Schedule",
                    path="/v3/Rail/THSRC/TrainSchedule",
                    description="高铁列车时刻表",
                    params=[]
                ),
                ApiEndpoint(
                    name="台铁时刻表",
                    name_en="TRA Train Schedule",
                    path="/v3/Rail/TRA/TrainSchedule",
                    description="台铁列车时刻表",
                    params=[]
                ),
                ApiEndpoint(
                    name="YouBike即时资料",
                    name_en="YouBike Real-time",
                    path="/v2/api/Bike/Station/NearBy",
                    description="YouBike微笑单车租借站资讯",
                    params=[{"name": "lat", "description": "纬度", "required": False}, {"name": "lon", "description": "经度", "required": False}]
                ),
            ]
        )

        # 水利署
        self.PLATFORMS[PlatformType.WRA.value] = PlatformConfig(
            id="wra",
            name="经济部水利署水利资料开放平台",
            name_en="WRA Water Resources",
            region=RegionType.TW,
            base_url="https://wra.gov.tw/api",
            auth_type="none",
            endpoints=[
                ApiEndpoint(
                    name="水库蓄水资料",
                    name_en="Reservoir Water Level",
                    path="/v2/reservoir",
                    description="全台水库实时蓄水率",
                    params=[]
                ),
                ApiEndpoint(
                    name="河川流量资料",
                    name_en="River Flow",
                    path="/v2/riverflow",
                    description="主要河川流量监测资料",
                    params=[{"name": "river", "description": "河川名称", "required": False}]
                ),
                ApiEndpoint(
                    name="雨量观测资料",
                    name_en="Rainfall Observation",
                    path="/v2/rainfall",
                    description="全台雨量站观测资料",
                    params=[{"name": "date", "description": "日期", "required": False}]
                ),
            ]
        )

        # 气象局
        self.PLATFORMS[PlatformType.CWA.value] = PlatformConfig(
            id="cwa",
            name="气象局资料开放平台",
            name_en="CWA Weather",
            region=RegionType.TW,
            base_url="https://opendata.cwa.gov.tw/api",
            auth_type="api_key",
            auth_env_var="CWA_API_KEY",
            endpoints=[
                ApiEndpoint(
                    name="天气预报",
                    name_en="Weather Forecast",
                    path="/v2/api/forecast",
                    description="未来36小时天气预报",
                    params=[{"name": "locationId", "description": "乡镇地区代码", "required": False}]
                ),
                ApiEndpoint(
                    name="地震资料",
                    name_en="Earthquake Data",
                    path="/v2/api/earthquake",
                    description="最近地震活动资料",
                    params=[]
                ),
                ApiEndpoint(
                    name="雨量资料",
                    name_en="Rainfall Data",
                    path="/v2/api/rainfall",
                    description="雨量观测资料",
                    params=[{"name": "time", "description": "时间范围", "required": False}]
                ),
            ]
        )

    def _init_hk_mo_platforms(self):
        """初始化港澳平台"""
        # 香港政府资料一线通
        self.PLATFORMS[PlatformType.HK_GOV.value] = PlatformConfig(
            id="hk_gov",
            name="香港政府资料一线通",
            name_en="Hong Kong Gov Data",
            region=RegionType.HK,
            base_url="https://api.data.gov.hk/v1",
            auth_type="api_key",
            auth_env_var="HK_GOV_API_KEY",
            fallback_type="json",
            endpoints=[
                ApiEndpoint(
                    name="实时空气质素",
                    name_en="Real-time Air Quality",
                    path="/convert/find-by-postcodes",
                    description="香港空气质量指数",
                    params=[]
                ),
                ApiEndpoint(
                    name="天文台天气预报",
                    name_en="Weather Forecast",
                    path="/weather/united-kingdom/general",
                    description="香港天气预报",
                    params=[]
                ),
            ]
        )

        # 澳门统计暨普查局
        self.PLATFORMS[PlatformType.MO_STAT.value] = PlatformConfig(
            id="mo_stat",
            name="澳门统计暨普查局",
            name_en="Macao Statistics Service",
            region=RegionType.MO,
            base_url="https://www.dsec.gov.mo/api",
            auth_type="none",
            fallback_type="web_scraper",
            endpoints=[
                ApiEndpoint(
                    name="宏观经济统计",
                    name_en="Macroeconomic Statistics",
                    path="/get-data/{category}",
                    description="GDP、消费、贸易等宏观经济数据",
                    params=[{"name": "category", "description": "数据类别", "required": True}]
                ),
                ApiEndpoint(
                    name="人口统计",
                    name_en="Population Statistics",
                    path="/get-data/{category}",
                    description="人口数据",
                    params=[]
                ),
            ]
        )

    def _init_global_platforms(self):
        """初始化全球平台"""
        # 美国政府开放数据
        self.PLATFORMS[PlatformType.US_DATA_GOV.value] = PlatformConfig(
            id="us_data_gov",
            name="美国政府开放数据",
            name_en="US Government Open Data",
            region=RegionType.US,
            base_url="https://api.data.gov/ed/federalgovernment/v2",
            auth_type="api_key",
            auth_env_var="US_DATA_GOV_API_KEY",
            fallback_url="https://www.data.gov/api/action/package_list",
            fallback_type="json",
            endpoints=[
                ApiEndpoint(
                    name="数据集目录",
                    name_en="Dataset Catalog",
                    path="/records",
                    description="联邦政府开放数据集列表",
                    params=[{"name": "limit", "description": "返回数量", "required": False}]
                ),
            ]
        )

        # 世界银行
        self.PLATFORMS[PlatformType.WORLD_BANK.value] = PlatformConfig(
            id="world_bank",
            name="世界银行开放数据",
            name_en="World Bank Open Data",
            region=RegionType.GLOBAL,
            base_url="https://api.worldbank.org/v2",
            auth_type="none",
            fallback_type="json",
            endpoints=[
                ApiEndpoint(
                    name="GDP数据",
                    name_en="GDP Data",
                    path="/country/{country}/indicator/NY.GDP.MKTP.CD",
                    description="各国GDP数据",
                    params=[{"name": "country", "description": "国家代码(如CN)", "required": True}]
                ),
                ApiEndpoint(
                    name="人口数据",
                    name_en="Population Data",
                    path="/country/{country}/indicator/SP.POP.TOTL",
                    description="各国人口数据",
                    params=[{"name": "country", "description": "国家代码", "required": True}]
                ),
            ]
        )

        # 联合国数据
        self.PLATFORMS[PlatformType.UN_DATA.value] = PlatformConfig(
            id="un_data",
            name="联合国数据平台",
            name_en="UN Data",
            region=RegionType.GLOBAL,
            base_url="https://data.un.org/ws",
            auth_type="none",
            fallback_type="json",
            endpoints=[
                ApiEndpoint(
                    name="可持续发展目标",
                    name_en="Sustainable Development Goals",
                    path="/rest/data/UNDATA,DF_UNDATA_SDG,GALL",
                    description="联合国可持续发展目标数据",
                    params=[]
                ),
            ]
        )

    def _check_cnstats(self):
        """检查 cn-stats 库是否可用"""
        try:
            from cnstats.stats import stats
            self._cn_stats_available = True
        except ImportError:
            self._cn_stats_available = False

    def _get_api_key(self, env_var: str) -> Optional[str]:
        """获取 API Key"""
        import os
        return os.environ.get(env_var)

    def _get_oauth2_token(self, platform: PlatformConfig) -> Optional[str]:
        """获取 OAuth2 访问令牌"""
        import os

        if platform.id in self._auth_tokens:
            if time.time() < self._token_expires.get(platform.id, 0):
                return self._auth_tokens[platform.id]

        oauth2 = platform.oauth2_config
        if not oauth2:
            return None

        client_id = os.environ.get(oauth2["client_id_env"])
        client_secret = os.environ.get(oauth2["client_secret_env"])

        if not client_id or not client_secret:
            return None

        try:
            data = urllib.parse.urlencode({
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            }).encode()

            req = urllib.request.Request(
                oauth2["token_url"],
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
                token = result.get("access_token")
                expires_in = result.get("expires_in", 3600)

                if token:
                    self._auth_tokens[platform.id] = token
                    self._token_expires[platform.id] = time.time() + expires_in - 60
                    return token

        except Exception:
            pass

        return None

    def _build_url(self, platform: PlatformConfig, endpoint: ApiEndpoint, params: Dict = None) -> str:
        """构建完整 URL"""
        url = f"{platform.base_url}{endpoint.path}"

        query_params = {}
        if params:
            query_params.update(params)

        if platform.auth_type == "api_key" and platform.auth_env_var:
            api_key = self._get_api_key(platform.auth_env_var)
            if api_key:
                query_params["api_key"] = api_key

        if query_params:
            url += "?" + urllib.parse.urlencode(query_params)

        return url

    def _make_request(self, url: str, platform: PlatformConfig) -> Dict:
        """发送 HTTP 请求"""
        try:
            req = urllib.request.Request(url)

            if platform.auth_type == "oauth2":
                token = self._get_oauth2_token(platform)
                if token:
                    req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())

        except urllib.error.HTTPError as e:
            return {"error": f"HTTP错误: {e.code}"}
        except urllib.error.URLError as e:
            return {"error": f"网络错误: {e.reason}"}
        except Exception as e:
            return {"error": f"请求失败: {str(e)}"}

    def _query_cn_stats(self, endpoint: ApiEndpoint, params: Dict = None) -> QueryResult:
        """使用 cn-stats 查询国家统计局数据"""
        if not self._cn_stats_available:
            return QueryResult(
                success=False,
                platform="国家统计局",
                platform_en="National Bureau of Statistics",
                endpoint=endpoint.name,
                region="🇨🇳 中国大陆",
                error="cn-stats 库未安装。请运行: pip install cn-stats"
            )

        try:
            from cnstats.stats import stats

            # 指标代码映射
            zbcode_map = {
                "国内生产总值(GDP)": "A010101",
                "居民消费价格指数(CPI)": "A01",
                "工业增加值": "A02",
                "固定资产投资": "A04",
                "社会消费品零售总额": "A07",
                "货币供应量": "A0D01",
                "城镇调查失业率": "A0E",
            }

            zbcode = zbcode_map.get(endpoint.name, "A010101")
            datestr = params.get("date", "202401") if params else "202401"
            regcode = params.get("regcode", "") if params else ""

            if regcode:
                result = stats(zbcode=zbcode, datestr=datestr, regcode=regcode, as_df=False)
            else:
                result = stats(zbcode=zbcode, datestr=datestr, as_df=False)

            return QueryResult(
                success=True,
                platform="国家统计局",
                platform_en="National Bureau of Statistics",
                endpoint=endpoint.name,
                region="🇨🇳 中国大陆",
                data=result,
                raw_response=result
            )

        except Exception as e:
            return QueryResult(
                success=False,
                platform="国家统计局",
                platform_en="National Bureau of Statistics",
                endpoint=endpoint.name,
                region="🇨🇳 中国大陆",
                error=str(e)
            )

    def _query_chinadata_live(self, platform: PlatformConfig, endpoint: ApiEndpoint) -> QueryResult:
        """查询 chinadata.live API"""
        url = f"{platform.base_url}/{endpoint.path}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())

                return QueryResult(
                    success=True,
                    platform=platform.name,
                    platform_en=platform.name_en,
                    endpoint=endpoint.name,
                    region=self.REGION_NAMES.get(platform.region, ""),
                    data=data,
                    raw_response=data
                )

        except Exception as e:
            return QueryResult(
                success=False,
                platform=platform.name,
                platform_en=platform.name_en,
                endpoint=endpoint.name,
                region=self.REGION_NAMES.get(platform.region, ""),
                error=str(e)
            )

    # ------------------------------------------------------------------
    # 自然语言查询接口
    # ------------------------------------------------------------------

    def query_by_natural_language(self, query: str, region: str = None) -> List[QueryResult]:
        """
        通过自然语言查询政府开放资料

        Args:
            query: 自然语言查询，如"中国GDP"、"台北空气品质"
            region: 可选的地区筛选，如 "cn", "tw", "hk"

        Returns:
            查询结果列表
        """
        results = []
        intent = self._identify_intent(query, region)

        if intent["platform"] and intent["endpoints"]:
            platform = self.PLATFORMS.get(intent["platform"])
            if platform and platform.enabled:
                for ep in intent["endpoints"]:
                    if platform.auth_type == "cnstats":
                        result = self._query_cn_stats(ep, intent.get("params", {}))
                    elif platform.id == "cn_chinadata":
                        result = self._query_chinadata_live(platform, ep)
                    else:
                        result = self._query_endpoint(platform, ep, intent.get("params", {}))
                    results.append(result)
        else:
            results = self._fuzzy_query(query, region)

        return results

    def _identify_intent(self, query: str, region: str = None) -> Dict:
        """
        识别查询意图

        Args:
            query: 自然语言查询
            region: 地区筛选

        Returns:
            {"platform": str, "endpoints": list, "params": dict}
        """
        query_lower = query.lower()
        intent = {"platform": None, "endpoints": [], "params": {}}

        # 地区识别
        detected_region = self._detect_region(query)

        # 🇨🇳 中国大陆数据识别
        cn_keywords = ["中国", "大陆", "全国", "国内", "gdp", "cpi", "人口", "经济"]
        if any(k in query_lower for k in cn_keywords) or region == "cn":
            intent["platform"] = "cn_stats"
            intent["params"] = self._extract_cn_params(query)

            # 根据关键词选择具体端点
            if "gdp" in query_lower or "国内生产总值" in query or "经济" in query:
                intent["endpoints"] = [self._find_endpoint("cn_stats", "GDP")]
            elif "cpi" in query_lower or "物价" in query or "通胀" in query:
                intent["endpoints"] = [self._find_endpoint("cn_stats", "CPI")]
            elif "失业" in query or "就业" in query:
                intent["endpoints"] = [self._find_endpoint("cn_stats", "失业")]
            elif "工业" in query or "生产" in query:
                intent["endpoints"] = [self._find_endpoint("cn_stats", "工业")]
            elif "投资" in query:
                intent["endpoints"] = [self._find_endpoint("cn_stats", "固定资产")]
            elif "消费" in query or "零售" in query:
                intent["endpoints"] = [self._find_endpoint("cn_stats", "零售")]
            else:
                intent["endpoints"] = [self._find_endpoint("cn_stats", "GDP")]

        # 🇹🇼 台湾数据识别
        tw_keywords = ["台湾", "台北", "台中", "高雄", "台铁", "高铁", "公车", "youbike"]
        if any(k in query_lower for k in tw_keywords) or region == "tw":
            if "空气" in query_lower or "空品" in query_lower or "pm2" in query_lower:
                intent["platform"] = "moenv"
                intent["endpoints"] = [self._find_endpoint("moenv", self._get_tw_endpoint_key(query))]
            elif "公车" in query_lower or "公交" in query_lower:
                intent["platform"] = "tdx"
                intent["endpoints"] = [self._find_endpoint("tdx", "公交")]
            elif "高铁" in query:
                intent["platform"] = "tdx"
                intent["endpoints"] = [self._find_endpoint("tdx", "高铁")]
            elif "台铁" in query:
                intent["platform"] = "tdx"
                intent["endpoints"] = [self._find_endpoint("tdx", "台铁")]
            elif "bike" in query_lower:
                intent["platform"] = "tdx"
                intent["endpoints"] = [self._find_endpoint("tdx", "YouBike")]
            elif "水库" in query or "蓄水" in query or "水利" in query:
                intent["platform"] = "wra"
                intent["endpoints"] = [self._find_endpoint("wra", "水库")]
            elif "天气" in query or "气象" in query:
                intent["platform"] = "cwa"
                intent["endpoints"] = [self._find_endpoint("cwa", "天气")]
            elif "地震" in query:
                intent["platform"] = "cwa"
                intent["endpoints"] = [self._find_endpoint("cwa", "地震")]
            elif "雨量" in query:
                intent["platform"] = "wra"
                intent["endpoints"] = [self._find_endpoint("wra", "雨量")]
            else:
                intent["platform"] = "moenv"
                intent["endpoints"] = [self._find_endpoint("moenv", "空气")]

        # 🇭🇰 香港数据识别
        hk_keywords = ["香港", "hong kong", "hk"]
        if any(k in query_lower for k in hk_keywords) or region == "hk":
            if "空气" in query_lower:
                intent["platform"] = "hk_gov"
                intent["endpoints"] = [self._find_endpoint("hk_gov", "空气")]
            else:
                intent["platform"] = "hk_gov"
                intent["endpoints"] = [self._find_endpoint("hk_gov", "天气")]

        # 🇲🇴 澳门数据识别
        mo_keywords = ["澳门", "macau", "mo"]
        if any(k in query_lower for k in mo_keywords) or region == "mo":
            intent["platform"] = "mo_stat"
            if "人口" in query:
                intent["endpoints"] = [self._find_endpoint("mo_stat", "人口")]
            else:
                intent["endpoints"] = [self._find_endpoint("mo_stat", "宏观经济")]

        # 🌍 全球/世界银行数据
        global_keywords = ["世界", "全球", "world", "global", "各国"]
        if any(k in query_lower for k in global_keywords):
            if "gdp" in query_lower:
                intent["platform"] = "world_bank"
                intent["endpoints"] = [self._find_endpoint("world_bank", "GDP")]
            elif "人口" in query:
                intent["platform"] = "world_bank"
                intent["endpoints"] = [self._find_endpoint("world_bank", "人口")]
            else:
                intent["platform"] = "world_bank"
                intent["endpoints"] = [self._find_endpoint("world_bank", "GDP")]

        # 美国数据
        us_keywords = ["美国", "usa", "united states"]
        if any(k in query_lower for k in us_keywords):
            intent["platform"] = "us_data_gov"
            intent["endpoints"] = [self._find_endpoint("us_data_gov", "数据集")]

        # 清理空的端点列表
        intent["endpoints"] = [e for e in intent["endpoints"] if e]

        return intent

    def _detect_region(self, query: str) -> Optional[RegionType]:
        """检测查询涉及的地区"""
        query_lower = query.lower()

        cn_words = ["中国", "大陆", "全国", "国内", "北京", "上海", "广东"]
        if any(w in query for w in cn_words):
            return RegionType.CN

        tw_words = ["台湾", "台北", "台中", "高雄", "台南"]
        if any(w in query for w in tw_words):
            return RegionType.TW

        hk_words = ["香港", "hong kong"]
        if any(w in query_lower for w in hk_words):
            return RegionType.HK

        mo_words = ["澳门", "macau"]
        if any(w in query_lower for w in mo_words):
            return RegionType.MO

        us_words = ["美国", "usa", "united states"]
        if any(w in query_lower for w in us_words):
            return RegionType.US

        return None

    def _get_tw_endpoint_key(self, query: str) -> str:
        """根据查询获取台湾端点关键词"""
        if "pm2" in query.lower():
            return "PM2"
        elif "酸雨" in query:
            return "酸雨"
        elif "预报" in query:
            return "预报"
        return "空气"

    def _extract_cn_params(self, query: str) -> Dict:
        """提取大陆数据查询参数"""
        params = {}

        # 提取日期
        date_pattern = r'(\d{4})年?(\d{0,2})?'
        match = re.search(date_pattern, query)
        if match:
            year = match.group(1)
            month = match.group(2) if match.group(2) else ""
            params["date"] = f"{year}{month}" if month else f"{year}01"

        # 提取省份
        provinces = ["北京", "上海", "广东", "浙江", "江苏", "四川", "湖北", "湖南", "山东", "河南"]
        for prov in provinces:
            if prov in query:
                # 省份代码映射
                prov_codes = {
                    "北京": "110000", "上海": "310000", "广东": "440000",
                    "浙江": "330000", "江苏": "320000", "四川": "510000"
                }
                params["regcode"] = prov_codes.get(prov, "")
                break

        return params

    def _find_endpoint(self, platform_id: str, keyword: str) -> Optional[ApiEndpoint]:
        """查找匹配的端点"""
        platform = self.PLATFORMS.get(platform_id)
        if not platform:
            return None

        keyword_lower = keyword.lower()
        for ep in platform.endpoints:
            if keyword_lower in ep.name.lower() or keyword_lower in ep.name_en.lower():
                return ep

        return platform.endpoints[0] if platform.endpoints else None

    def _query_endpoint(self, platform: PlatformConfig, endpoint: ApiEndpoint, params: Dict = None) -> QueryResult:
        """查询指定端点"""
        url = self._build_url(platform, endpoint, params)
        raw = self._make_request(url, platform)

        if "error" in raw:
            return QueryResult(
                success=False,
                platform=platform.name,
                platform_en=platform.name_en,
                endpoint=endpoint.name,
                region=self.REGION_NAMES.get(platform.region, ""),
                error=raw.get("error")
            )

        return QueryResult(
            success=True,
            platform=platform.name,
            platform_en=platform.name_en,
            endpoint=endpoint.name,
            region=self.REGION_NAMES.get(platform.region, ""),
            data=raw,
            raw_response=raw
        )

    def _fuzzy_query(self, query: str, region: str = None) -> List[QueryResult]:
        """模糊查询所有平台"""
        results = []

        for pid, platform in self.PLATFORMS.items():
            if not platform.enabled:
                continue

            # 地区筛选
            if region:
                if region == "cn" and platform.region != RegionType.CN:
                    continue
                elif region == "tw" and platform.region != RegionType.TW:
                    continue

            for endpoint in platform.endpoints:
                if self._matches_query(endpoint, query):
                    if platform.auth_type == "cnstats":
                        result = self._query_cn_stats(endpoint)
                    elif platform.id == "cn_chinadata":
                        result = self._query_chinadata_live(platform, endpoint)
                    else:
                        result = self._query_endpoint(platform, endpoint)
                    if result.success:
                        results.append(result)

        return results

    def _matches_query(self, endpoint: ApiEndpoint, query: str) -> bool:
        """检查端点是否匹配查询"""
        query_lower = query.lower()
        text = f"{endpoint.name} {endpoint.name_en} {endpoint.description}".lower()
        return query_lower in text or any(k in text for k in query_lower.split())

    # ------------------------------------------------------------------
    # 结果格式化
    # ------------------------------------------------------------------

    def format_result_natural(self, result: QueryResult) -> str:
        """
        将查询结果转换为自然语言描述
        """
        if not result.success:
            return f"❌ 查询失败：{result.endpoint} - {result.error}"

        try:
            # 根据平台选择格式化方法
            if result.platform == "国家统计局":
                return self._format_cn_stats(result)
            elif "chinadata" in result.platform.lower():
                return self._format_chinadata(result)
            elif "空气" in result.endpoint or "air" in result.endpoint.lower():
                return self._format_air_quality(result)
            elif "水库" in result.endpoint or "蓄水" in result.endpoint:
                return self._format_reservoir(result)
            elif "公车" in result.endpoint or "公交" in result.endpoint:
                return self._format_bus(result)
            elif "天气" in result.endpoint or "气象" in result.endpoint:
                return self._format_weather(result)
            elif "雨量" in result.endpoint:
                return self._format_rainfall(result)
            elif "GDP" in result.endpoint.upper() or "国内生产总值" in result.endpoint:
                return self._format_gdp(result)
            else:
                return self._format_generic(result)

        except Exception as e:
            return f"⚠️ 资料解析失败：{str(e)}\n\n原始资料：{json.dumps(result.raw_response, ensure_ascii=False, indent=2)[:500]}"

    def _format_cn_stats(self, result: QueryResult) -> str:
        """格式化国家统计局数据"""
        try:
            data = result.raw_response
            lines = [f"📊 **{result.platform} - {result.endpoint}**\n"]

            if isinstance(data, dict):
                if "data" in data:
                    for item in data["data"][:10]:
                        name = item.get("name", item.get("zbcode", ""))
                        value = item.get("data", item.get("value", ""))
                        unit = item.get("unit", "")
                        lines.append(f"- {name}: {value} {unit}")
                elif "result" in data:
                    for item in data["result"]["data"][:10]:
                        ind = item.get("indicator", [])
                        val = item.get("data", [])
                        if ind and val:
                            lines.append(f"- {ind[0]}: {val[0]}")
            elif isinstance(data, list):
                for item in data[:10]:
                    lines.append(f"- {item}")

            return "\n".join(lines)

        except Exception as e:
            return f"国家统计局资料解析异常：{str(e)}\n\n{json.dumps(result.raw_response, ensure_ascii=False, indent=2)[:500]}"

    def _format_chinadata(self, result: QueryResult) -> str:
        """格式化 chinadata.live 数据"""
        try:
            data = result.raw_response
            lines = [f"📈 **{result.platform} - {result.endpoint}**\n"]

            if isinstance(data, dict) and "data" in data:
                chart_data = data["data"]
                title = chart_data.get("title", result.endpoint)
                records = chart_data.get("data", [])

                lines.append(f"**{title}**\n")

                for record in records[-10:]:  # 最近10条
                    if isinstance(record, dict):
                        date = record.get("date", "")
                        # 显示所有数值字段
                        for k, v in record.items():
                            if k != "date" and v:
                                lines.append(f"- {date}: {k} = {v}")
                    else:
                        lines.append(f"- {record}")

            return "\n".join(lines)

        except Exception as e:
            return f"数据解析异常：{str(e)}\n\n{json.dumps(result.raw_response, ensure_ascii=False, indent=2)[:500]}"

    def _format_gdp(self, result: QueryResult) -> str:
        """格式化GDP数据"""
        try:
            data = result.raw_response
            lines = [f"📈 **{result.platform}**\n"]

            if isinstance(data, dict):
                if "data" in data:
                    for item in data["data"][:10]:
                        date = item.get("date", "")
                        value = item.get("value", item.get("china", ""))
                        unit = "亿元" if float(value) > 10000 else ""
                        lines.append(f"- {date}: {value} {unit}")
            elif isinstance(data, list):
                for item in data[:10]:
                    lines.append(str(item))

            return "\n".join(lines)

        except Exception as e:
            return self._format_generic(result)

    def _format_air_quality(self, result: QueryResult) -> str:
        """格式化空气品质资料"""
        try:
            data = result.raw_response
            lines = [f"🌬️ **{result.endpoint}**\n"]

            records = data.get("records", data) if isinstance(data, dict) else data
            if isinstance(records, dict):
                records = [records]

            for record in records[:5]:
                site = record.get("siteName", record.get("SiteName", "未知"))
                aqi = record.get("aqi", record.get("AQI", ""))
                status = self._get_aqi_status(aqi)
                lines.append(f"📍 {site}")
                lines.append(f"   AQI: {aqi} ({status})")

                pm25 = record.get("pm25", record.get("PM2.5", ""))
                if pm25:
                    lines.append(f"   PM2.5: {pm25} μg/m³")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"空气品质资料解析异常：{str(e)}"

    def _get_aqi_status(self, aqi: str) -> str:
        """获取AQI状态描述"""
        try:
            aqi_val = int(aqi)
            if aqi_val <= 50:
                return "良好 🟢"
            elif aqi_val <= 100:
                return "普通 🟡"
            elif aqi_val <= 150:
                return "对敏感族群不健康 🟠"
            elif aqi_val <= 200:
                return "对所有人不健康 🔴"
            elif aqi_val <= 300:
                return "非常不健康 🟣"
            else:
                return "危害 ⚫"
        except:
            return "未知"

    def _format_reservoir(self, result: QueryResult) -> str:
        """格式化水库资料"""
        try:
            data = result.raw_response
            lines = [f"💧 **{result.endpoint}**\n"]

            records = data.get("records", data) if isinstance(data, dict) else data
            if isinstance(records, dict):
                records = [records]

            for record in records:
                name = record.get("reservoirName", record.get("name", ""))
                percent = record.get("waterLevelPercent", record.get("percent", ""))
                lines.append(f"📍 {name}")
                if percent:
                    lines.append(f"   蓄水率: {percent}%")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"水库资料解析异常：{str(e)}"

    def _format_bus(self, result: QueryResult) -> str:
        """格式化公车资料"""
        try:
            data = result.raw_response
            lines = [f"🚌 **{result.endpoint}**\n"]

            records = data.get("records", data) if isinstance(data, dict) else data
            if isinstance(records, dict):
                records = [records]

            for record in records[:5]:
                route = record.get("routeName", record.get("RouteName", ""))
                arrival = record.get("stopName", record.get("StopName", ""))
                time_val = record.get("preArrivalTime", record.get("time", ""))

                lines.append(f"🚌 路线: {route}")
                lines.append(f"   站牌: {arrival}")
                if time_val:
                    lines.append(f"   预计到站: {time_val} 分钟")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"公车资料解析异常：{str(e)}"

    def _format_weather(self, result: QueryResult) -> str:
        """格式化天气预报"""
        try:
            data = result.raw_response
            lines = [f"🌤️ **{result.endpoint}**\n"]

            records = data.get("records", data) if isinstance(data, dict) else data
            if isinstance(records, dict):
                records = [records]

            for record in records[:3]:
                location = record.get("locationName", record.get("name", ""))
                lines.append(f"📍 {location}")

                elements = record.get("weatherElement", [])
                for elem in elements:
                    elem_name = elem.get("elementName", "")
                    elem_value = elem.get("value", "")
                    if "Temperature" in elem_name:
                        lines.append(f"   温度: {elem_value}°C")
                    elif elem_name == "PoP":
                        lines.append(f"   降雨机率: {elem_value}%")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"天气预报解析异常：{str(e)}"

    def _format_rainfall(self, result: QueryResult) -> str:
        """格式化雨量资料"""
        try:
            data = result.raw_response
            lines = [f"🌧️ **{result.endpoint}**\n"]

            records = data.get("records", data) if isinstance(data, dict) else data
            if isinstance(records, dict):
                records = [records]

            for record in records[:5]:
                station = record.get("stationName", record.get("name", ""))
                rainfall = record.get("rainfall", record.get("value", ""))
                lines.append(f"📍 {station}")
                lines.append(f"   雨量: {rainfall} mm")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            return f"雨量资料解析异常：{str(e)}"

    def _format_generic(self, result: QueryResult) -> str:
        """通用格式化"""
        try:
            data = result.raw_response
            lines = [f"📊 **{result.platform} - {result.endpoint}**\n"]

            if isinstance(data, dict):
                if "records" in data:
                    records = data["records"]
                    lines.append(f"共 {len(records)} 笔资料：\n")
                    for r in records[:10]:
                        lines.append(str(r))
                else:
                    lines.append(json.dumps(data, ensure_ascii=False, indent=2)[:500])
            elif isinstance(data, list):
                lines.append(f"共 {len(data)} 笔资料：\n")
                for item in data[:10]:
                    lines.append(str(item))
            else:
                lines.append(str(data))

            return "\n".join(lines)

        except Exception as e:
            return f"资料解析异常：{str(e)}\n\n{str(result.raw_response)[:500]}"

    # ------------------------------------------------------------------
    # 工具接口
    # ------------------------------------------------------------------

    def list_regions(self) -> List[Dict]:
        """列出所有支持的地区"""
        regions = {}
        for platform in self.PLATFORMS.values():
            if platform.enabled:
                rid = platform.region.value
                if rid not in regions:
                    regions[rid] = {
                        "id": rid,
                        "name": self.REGION_NAMES.get(platform.region, platform.region.value),
                        "platform_count": 0
                    }
                regions[rid]["platform_count"] += 1

        return list(regions.values())

    def list_platforms(self, region: str = None) -> List[Dict]:
        """列出所有可用平台"""
        result = []
        for p in self.PLATFORMS.values():
            if p.enabled:
                if region and p.region.value != region:
                    continue
                result.append({
                    "id": p.id,
                    "name": p.name,
                    "name_en": p.name_en,
                    "region": self.REGION_NAMES.get(p.region, p.region.value),
                    "region_id": p.region.value,
                    "enabled": p.enabled,
                    "endpoint_count": len(p.endpoints)
                })
        return result

    def list_endpoints(self, platform_id: str = None) -> List[Dict]:
        """列出端点"""
        if platform_id:
            platform = self.PLATFORMS.get(platform_id)
            if not platform:
                return []
            platforms = [platform]
        else:
            platforms = self.PLATFORMS.values()

        result = []
        for p in platforms:
            for ep in p.endpoints:
                result.append({
                    "platform": p.name,
                    "platform_id": p.id,
                    "region": self.REGION_NAMES.get(p.region, ""),
                    "name": ep.name,
                    "name_en": ep.name_en,
                    "path": ep.path,
                    "description": ep.description
                })

        return result

    def query_direct(self, platform_id: str, endpoint_name: str, params: Dict = None) -> QueryResult:
        """直接查询指定平台和端点"""
        platform = self.PLATFORMS.get(platform_id)
        if not platform:
            return QueryResult(
                success=False,
                platform="",
                platform_en="",
                endpoint=endpoint_name,
                region="",
                error=f"未知平台: {platform_id}"
            )

        endpoint = None
        for ep in platform.endpoints:
            if endpoint_name in ep.name or endpoint_name in ep.name_en:
                endpoint = ep
                break

        if not endpoint:
            return QueryResult(
                success=False,
                platform=platform.name,
                platform_en=platform.name_en,
                endpoint=endpoint_name,
                region=self.REGION_NAMES.get(platform.region, ""),
                error=f"未知端点: {endpoint_name}"
            )

        if platform.auth_type == "cnstats":
            return self._query_cn_stats(endpoint, params or {})
        elif platform.id == "cn_chinadata":
            return self._query_chinadata_live(platform, endpoint)
        else:
            return self._query_endpoint(platform, endpoint, params or {})

    def get_region_stats(self) -> Dict[str, Dict]:
        """获取各地区统计信息"""
        stats = {}
        for p in self.PLATFORMS.values():
            rid = p.region.value
            if rid not in stats:
                stats[rid] = {
                    "region": self.REGION_NAMES.get(p.region, rid),
                    "platform_count": 0,
                    "endpoint_count": 0,
                    "platforms": []
                }
            stats[rid]["platform_count"] += 1
            stats[rid]["endpoint_count"] += len(p.endpoints)
            stats[rid]["platforms"].append(p.name)

        return stats


# ============ 全局单例 ============

_instance: Optional[GovDataQuery] = None


def get_gov_data_query() -> GovDataQuery:
    """获取全局实例"""
    global _instance
    if _instance is None:
        _instance = GovDataQuery()
    return _instance


def reset_gov_data_query():
    """重置实例"""
    global _instance
    _instance = None