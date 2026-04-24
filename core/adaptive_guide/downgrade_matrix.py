"""
功能降级矩阵 - Downgrade Matrix

定义每个高级功能的多个实现级别：
1. 理想方案 (IDEAL) - 配置齐全，效果最佳
2. 免费降级 (FREE) - 使用免费API/服务，配额有限
3. 公开数据 (PUBLIC) - 使用公开数据集，无需认证
4. 本地模拟 (LOCAL) - 本地模拟计算，功能受限

使用示例：
    matrix = DowngradeMatrix()
    impl = matrix.get_best_available("weather_forecast")
    logger.info(f"使用方案: {impl.name}")
"""

import os
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from core.logger import get_logger
logger = get_logger('adaptive_guide.downgrade_matrix')


logger = logging.getLogger(__name__)


class AvailabilityLevel(Enum):
    """可用性级别（从高到低）"""
    IDEAL = "ideal"       # 理想方案 - 完整功能
    FREE = "free"         # 免费降级 - 配额限制
    PUBLIC = "public"     # 公开数据 - 无需认证
    LOCAL = "local"       # 本地模拟 - 功能受限
    UNAVAILABLE = "none"  # 不可用 - 需要引导


class ImplementationType(Enum):
    """实现类型"""
    API = "api"           # 远程API调用
    CLI = "cli"           # 命令行工具
    PYTHON = "python"     # Python库/包
    DOCKER = "docker"     # Docker容器
    MOCK = "mock"         # 模拟/占位


@dataclass
class Implementation:
    """
    单个功能实现
    
    Attributes:
        id: 唯一标识符
        name: 显示名称
        level: 可用性级别
        impl_type: 实现类型
        config_keys: 需要的配置项（如API Key）
        requires_auth: 是否需要认证
        free_quota: 免费配额（每天/每月）
        cost_per_unit: 单位费用
        latency_ms: 预估延迟（毫秒）
        accuracy: 相对准确度 (0.0-1.0)
        capabilities: 支持的功能列表
        limitations: 限制描述
        config_template: 配置模板
        executor: 执行函数
    """
    id: str
    name: str
    level: AvailabilityLevel
    impl_type: ImplementationType
    config_keys: List[str] = field(default_factory=list)
    requires_auth: bool = False
    free_quota: Optional[int] = None  # 每天配额
    cost_per_unit: float = 0.0  # 每1000次
    latency_ms: int = 0
    accuracy: float = 1.0
    capabilities: List[str] = field(default_factory=list)
    limitations: str = ""
    config_template: Dict[str, Any] = field(default_factory=dict)
    # 执行函数签名: def(config: dict, input_data: dict) -> dict
    executor: Optional[Callable] = None
    
    def is_available(self, current_config: Dict[str, Any]) -> bool:
        """检查当前配置下是否可用"""
        if not self.requires_auth:
            return True
        
        # 检查所有必需的配置项
        for key in self.config_keys:
            if key in current_config and current_config[key]:
                return True
            # 检查环境变量
            if os.getenv(key):
                return True
        
        return False
    
    def get_quota_remaining(self) -> Optional[int]:
        """获取剩余配额（如果有限制）"""
        if self.free_quota is None:
            return None
        
        # TODO: 从存储中读取已使用配额
        # 这里简化处理，返回完整配额
        return self.free_quota
    
    def estimate_cost(self, calls: int) -> float:
        """估算费用"""
        return (calls / 1000) * self.cost_per_unit


class DowngradeMatrix:
    """
    功能降级矩阵管理器
    
    维护所有功能的降级实现列表，
    提供自动降级决策能力。
    """
    
    # 全局降级矩阵实例
    _instance: Optional["DowngradeMatrix"] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if DowngradeMatrix._initialized:
            return
        
        # 功能 → 实现列表（按优先级排序）
        self.feature_implementations: Dict[str, List[Implementation]] = {}
        
        # 快速查找表
        self._impl_by_id: Dict[str, Implementation] = {}
        
        # 初始化内置降级策略
        self._init_builtin_implementations()
        
        DowngradeMatrix._initialized = True
        logger.info("DowngradeMatrix initialized with %d features", 
                    len(self.feature_implementations))
    
    @classmethod
    def get_instance(cls) -> "DowngradeMatrix":
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _init_builtin_implementations(self):
        """初始化内置降级实现"""
        
        # ============================================================
        # 天气预测功能降级链
        # ============================================================
        weather_implementations = [
            # Level 1: 理想方案 - 专业商业API
            Implementation(
                id="openweather_pro",
                name="OpenWeatherMap Pro",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["OPENWEATHER_API_KEY"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=0.5,
                latency_ms=100,
                accuracy=0.95,
                capabilities=["实时天气", "逐时预报", "逐日预报", "历史数据", "空气污染", "紫外线"],
                limitations=""
            ),
            # Level 2: 免费方案 - OpenWeatherMap免费层
            Implementation(
                id="openweather_free",
                name="OpenWeatherMap Free",
                level=AvailabilityLevel.FREE,
                impl_type=ImplementationType.API,
                config_keys=["OPENWEATHER_API_KEY"],
                requires_auth=True,
                free_quota=1000,  # 每天1000次
                cost_per_unit=0,
                latency_ms=100,
                accuracy=0.95,
                capabilities=["实时天气", "逐时预报(5天)", "空气污染"],
                limitations="每天1000次请求限额"
            ),
            # Level 3: 公开数据 - Open-Meteo（无需Key）
            Implementation(
                id="openmeteo",
                name="Open-Meteo",
                level=AvailabilityLevel.PUBLIC,
                impl_type=ImplementationType.API,
                config_keys=[],  # 无需认证
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=200,
                accuracy=0.90,
                capabilities=["实时天气", "逐时预报(7天)", "逐日预报(16天)", "历史数据"],
                limitations="不提供空气污染数据"
            ),
            # Level 4: 本地模拟 - 历史数据均值
            Implementation(
                id="weather_mock",
                name="历史数据模拟",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.MOCK,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=1,
                accuracy=0.60,
                capabilities=["基于历史的估算"],
                limitations="仅基于历史平均值，功能有限"
            ),
        ]
        self._register_implementations("weather_forecast", weather_implementations)
        
        # ============================================================
        # 地图服务功能降级链
        # ============================================================
        map_implementations = [
            Implementation(
                id="google_maps",
                name="Google Maps",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["GOOGLE_MAPS_API_KEY"],
                requires_auth=True,
                free_quota=28000,  # 每月28000次免费
                cost_per_unit=0.005,
                latency_ms=50,
                accuracy=0.98,
                capabilities=["道路规划", "地理编码", "地点搜索", "高度数据", "时区"],
                limitations="国内访问受限"
            ),
            Implementation(
                id="amap",
                name="高德地图",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["AMAP_API_KEY"],
                requires_auth=True,
                free_quota=5000,  # 每天5000次
                cost_per_unit=0.01,
                latency_ms=60,
                accuracy=0.95,
                capabilities=["道路规划", "地理编码", "地点搜索", "行政区划"],
                limitations="需要国内服务器"
            ),
            Implementation(
                id="openstreetmap",
                name="OpenStreetMap",
                level=AvailabilityLevel.PUBLIC,
                impl_type=ImplementationType.API,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=150,
                accuracy=0.85,
                capabilities=["地理编码", "基础地图", "路线规划"],
                limitations="数据精度较低，无高级功能"
            ),
            Implementation(
                id="static_coordinates",
                name="静态坐标",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.MOCK,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=0,
                accuracy=0.80,
                capabilities=["坐标展示"],
                limitations="仅支持手动输入坐标"
            ),
        ]
        self._register_implementations("map_service", map_implementations)
        
        # ============================================================
        # AI分析功能降级链
        # ============================================================
        ai_implementations = [
            Implementation(
                id="gpt4",
                name="GPT-4",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["OPENAI_API_KEY"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=30.0,  # $30/1M tokens
                latency_ms=5000,
                accuracy=0.95,
                capabilities=["复杂推理", "代码生成", "长文本理解", "多轮对话"],
                limitations="费用较高"
            ),
            Implementation(
                id="gpt35",
                name="GPT-3.5 Turbo",
                level=AvailabilityLevel.FREE,
                impl_type=ImplementationType.API,
                config_keys=["OPENAI_API_KEY"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=2.0,  # $2/1M tokens
                latency_ms=2000,
                accuracy=0.85,
                capabilities=["基础对话", "代码生成", "文本处理"],
                limitations="推理能力较弱"
            ),
            Implementation(
                id="claude",
                name="Claude",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["ANTHROPIC_API_KEY"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=15.0,
                latency_ms=4000,
                accuracy=0.95,
                capabilities=["长文本", "安全推理", "复杂分析"],
                limitations="上下文窗口有限制"
            ),
            Implementation(
                id="qwen_local",
                name="Qwen 本地模型",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.PYTHON,
                config_keys=["OLLAMA_BASE_URL"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=100,
                accuracy=0.75,
                capabilities=["基础对话", "文本处理"],
                limitations="能力有限，需要本地GPU"
            ),
            Implementation(
                id="rule_engine",
                name="规则引擎",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.MOCK,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=1,
                accuracy=0.50,
                capabilities=["基础模式匹配"],
                limitations="仅支持预定义规则"
            ),
        ]
        self._register_implementations("ai_analysis", ai_implementations)
        
        # ============================================================
        # 空气质量功能降级链
        # ============================================================
        air_implementations = [
            Implementation(
                id="aqicn_pro",
                name="AQICN 认证",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["AQICN_TOKEN"],
                requires_auth=True,
                free_quota=5000,
                cost_per_unit=0.001,
                latency_ms=80,
                accuracy=0.95,
                capabilities=["实时AQI", "历史数据", "多城市", "预报"],
                limitations=""
            ),
            Implementation(
                id="openweather_aqi",
                name="OpenWeatherMap AQI",
                level=AvailabilityLevel.FREE,
                impl_type=ImplementationType.API,
                config_keys=["OPENWEATHER_API_KEY"],
                requires_auth=True,
                free_quota=1000,
                cost_per_unit=0,
                latency_ms=100,
                accuracy=0.90,
                capabilities=["实时AQI", "空气污染指数"],
                limitations="仅支持部分城市"
            ),
            Implementation(
                id="public_station",
                name="公开监测站",
                level=AvailabilityLevel.PUBLIC,
                impl_type=ImplementationType.API,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=500,
                accuracy=0.80,
                capabilities=["国控站数据"],
                limitations="数据更新延迟大，覆盖有限"
            ),
            Implementation(
                id="aqi_mock",
                name="AQI估算",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.MOCK,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=0,
                accuracy=0.40,
                capabilities=["基于天气的估算"],
                limitations="仅估算，不准确"
            ),
        ]
        self._register_implementations("air_quality", air_implementations)
        
        # ============================================================
        # 水质分析功能降级链
        # ============================================================
        water_implementations = [
            Implementation(
                id="epa_water_api",
                name="EPA Water API",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["EPA_API_KEY"],
                requires_auth=True,
                free_quota=10000,
                cost_per_unit=0,
                latency_ms=100,
                accuracy=0.95,
                capabilities=["水质监测", "排放数据", "流域分析"],
                limitations="主要美国数据"
            ),
            Implementation(
                id="china_water_api",
                name="中国水质监测网",
                level=AvailabilityLevel.PUBLIC,
                impl_type=ImplementationType.API,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=200,
                accuracy=0.85,
                capabilities=["国控断面数据", "地表水监测"],
                limitations="数据更新不及时"
            ),
            Implementation(
                id="water_model_local",
                name="本地水质模型",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.PYTHON,
                config_keys=["PYSWMM_AVAILABLE"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=1000,
                accuracy=0.75,
                capabilities=["水质模拟", "污染物预测"],
                limitations="需要本地安装模型"
            ),
            Implementation(
                id="water_mock",
                name="水质估算",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.MOCK,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=0,
                accuracy=0.30,
                capabilities=["基础估算"],
                limitations="仅基于历史统计"
            ),
        ]
        self._register_implementations("water_quality", water_implementations)
        
        # ============================================================
        # 搜索功能降级链
        # ============================================================
        search_implementations = [
            Implementation(
                id="google_search",
                name="Google Search",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["GOOGLE_SEARCH_API_KEY"],
                requires_auth=True,
                free_quota=100,
                cost_per_unit=0.005,
                latency_ms=100,
                accuracy=0.95,
                capabilities=["网页搜索", "新闻搜索", "图片搜索"],
                limitations="国内访问受限"
            ),
            Implementation(
                id="serpapi",
                name="SerpAPI",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["SERPAPI_KEY"],
                requires_auth=True,
                free_quota=100,
                cost_per_unit=0.01,
                latency_ms=200,
                accuracy=0.93,
                capabilities=["多引擎搜索", "结构化结果"],
                limitations=""
            ),
            Implementation(
                id="duckduckgo",
                name="DuckDuckGo",
                level=AvailabilityLevel.PUBLIC,
                impl_type=ImplementationType.API,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=300,
                accuracy=0.75,
                capabilities=["基础搜索", "隐私搜索"],
                limitations="结果质量较低"
            ),
            Implementation(
                id="local_index",
                name="本地索引搜索",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.PYTHON,
                config_keys=["KNOWLEDGE_BASE_PATH"],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=10,
                accuracy=0.70,
                capabilities=["本地文档搜索"],
                limitations="仅搜索本地知识库"
            ),
        ]
        self._register_implementations("search", search_implementations)
        
        # ============================================================
        # 存储功能降级链
        # ============================================================
        storage_implementations = [
            Implementation(
                id="s3_cloud",
                name="S3 云存储",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.API,
                config_keys=["AWS_ACCESS_KEY", "AWS_SECRET_KEY"],
                requires_auth=True,
                free_quota=5 * 1024,  # 5GB免费
                cost_per_unit=0.023,  # $0.023/GB
                latency_ms=50,
                accuracy=1.0,
                capabilities=["对象存储", "CDN分发", "生命周期管理"],
                limitations="需要云账号"
            ),
            Implementation(
                id="local_disk",
                name="本地磁盘",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.PYTHON,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=5,
                accuracy=1.0,
                capabilities=["文件存储", "目录管理"],
                limitations="不可跨设备共享"
            ),
            Implementation(
                id="memory_cache",
                name="内存缓存",
                level=AvailabilityLevel.LOCAL,
                impl_type=ImplementationType.MOCK,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=0,
                accuracy=1.0,
                capabilities=["临时缓存"],
                limitations="重启后丢失"
            ),
        ]
        self._register_implementations("storage", storage_implementations)
        
        # ============================================================
        # 气象模型功能降级链
        # ============================================================
        meteorology_implementations = [
            Implementation(
                id="cmaq_cloud",
                name="CMAQ 云端",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.DOCKER,
                config_keys=["CLOUD_ENDPOINT"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=0.5,  # 每小时
                latency_ms=5000,
                accuracy=0.90,
                capabilities=["区域空气质量模拟", "化学传输模型"],
                limitations="云端计算费用"
            ),
            Implementation(
                id="cmaq_local",
                name="CMAQ 本地",
                level=AvailabilityLevel.FREE,
                impl_type=ImplementationType.DOCKER,
                config_keys=["DOCKER_INSTALLED"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=30000,
                accuracy=0.90,
                capabilities=["区域空气质量模拟"],
                limitations="需要强大本地算力"
            ),
            Implementation(
                id="wrf_cloud",
                name="WRF 云端",
                level=AvailabilityLevel.IDEAL,
                impl_type=ImplementationType.DOCKER,
                config_keys=["CLOUD_ENDPOINT"],
                requires_auth=True,
                free_quota=None,
                cost_per_unit=0.6,
                latency_ms=10000,
                accuracy=0.92,
                capabilities=["天气预报", "气候模拟"],
                limitations="计算资源需求高"
            ),
            Implementation(
                id="openmeteo_forecast",
                name="Open-Meteo 预报",
                level=AvailabilityLevel.PUBLIC,
                impl_type=ImplementationType.API,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=200,
                accuracy=0.80,
                capabilities=["天气预报", "温度预报"],
                limitations="不适合专业气象"
            ),
            Implementation(
                id="nasa_power",
                name="NASA POWER",
                level=AvailabilityLevel.PUBLIC,
                impl_type=ImplementationType.API,
                config_keys=[],
                requires_auth=False,
                free_quota=None,
                cost_per_unit=0,
                latency_ms=300,
                accuracy=0.85,
                capabilities=["气象再分析", "辐射数据"],
                limitations="数据延迟较大"
            ),
        ]
        self._register_implementations("meteorology", meteorology_implementations)
    
    def _register_implementations(self, feature_id: str, implementations: List[Implementation]):
        """注册一组实现"""
        self.feature_implementations[feature_id] = implementations
        for impl in implementations:
            self._impl_by_id[impl.id] = impl
    
    def get_implementations(self, feature_id: str) -> List[Implementation]:
        """获取功能的所有实现（按优先级排序）"""
        return self.feature_implementations.get(feature_id, [])
    
    def get_best_available(
        self, 
        feature_id: str, 
        config: Optional[Dict[str, Any]] = None,
        prefer_free: bool = True
    ) -> Optional[Implementation]:
        """
        获取最佳可用实现
        
        Args:
            feature_id: 功能标识符
            config: 当前配置
            prefer_free: 是否优先选择免费方案
        
        Returns:
            最佳可用实现，如果没有可用方案返回None
        """
        implementations = self.get_implementations(feature_id)
        if not implementations:
            logger.warning("Unknown feature: %s", feature_id)
            return None
        
        config = config or {}
        
        # 如果优先免费，先尝试免费方案
        if prefer_free:
            # 尝试从高到低找可用的
            for impl in implementations:
                if impl.is_available(config):
                    return impl
        else:
            # 优先质量，从理想方案开始
            for impl in implementations:
                if impl.is_available(config) and impl.level == AvailabilityLevel.IDEAL:
                    return impl
            # 如果理想不可用，找次优
            for impl in implementations:
                if impl.is_available(config):
                    return impl
        
        return None
    
    def get_fallback_chain(
        self, 
        feature_id: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> List[Implementation]:
        """
        获取完整的降级链（从高到低）
        
        Returns:
            可用的实现列表
        """
        implementations = self.get_implementations(feature_id)
        config = config or {}
        
        available = [impl for impl in implementations if impl.is_available(config)]
        return available
    
    def get_implementation(self, impl_id: str) -> Optional[Implementation]:
        """通过ID获取实现"""
        return self._impl_by_id.get(impl_id)
    
    def register_feature(
        self, 
        feature_id: str, 
        implementations: List[Implementation]
    ):
        """注册新功能及其实现"""
        self._register_implementations(feature_id, implementations)
    
    def get_all_features(self) -> List[str]:
        """获取所有已注册的功能"""
        return list(self.feature_implementations.keys())
    
    def get_feature_summary(self, feature_id: str) -> Dict[str, Any]:
        """获取功能摘要"""
        implementations = self.get_implementations(feature_id)
        if not implementations:
            return {}
        
        return {
            "feature_id": feature_id,
            "implementations": [
                {
                    "id": impl.id,
                    "name": impl.name,
                    "level": impl.level.value,
                    "available": impl.is_available({}),  # 无配置检查
                    "requires_auth": impl.requires_auth,
                    "free_quota": impl.free_quota,
                }
                for impl in implementations
            ]
        }
    
    def execute_feature(
        self, 
        feature_id: str, 
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        prefer_free: bool = True
    ) -> Dict[str, Any]:
        """
        执行功能，自动选择最佳可用实现
        
        Args:
            feature_id: 功能标识符
            input_data: 输入数据
            config: 当前配置
            prefer_free: 是否优先免费方案
        
        Returns:
            执行结果
        """
        impl = self.get_best_available(feature_id, config, prefer_free)
        
        if impl is None:
            return {
                "success": False,
                "error": f"No available implementation for {feature_id}",
                "requires_guide": True,
                "feature_id": feature_id
            }
        
        if impl.executor is None:
            # 没有执行函数，返回实现信息
            return {
                "success": True,
                "implementation": impl.id,
                "implementation_name": impl.name,
                "level": impl.level.value,
                "requires_config": impl.requires_auth,
                "config_keys_needed": impl.config_keys if not impl.is_available(config or {}) else [],
            }
        
        try:
            result = impl.executor(config or {}, input_data)
            result["implementation"] = impl.id
            result["implementation_name"] = impl.name
            result["level"] = impl.level.value
            return result
        except Exception as e:
            logger.error("Failed to execute %s: %s", impl.id, str(e))
            return {
                "success": False,
                "error": str(e),
                "implementation": impl.id,
                "feature_id": feature_id
            }
    
    def needs_configuration(self, feature_id: str) -> bool:
        """检查功能是否需要配置"""
        implementations = self.get_implementations(feature_id)
        for impl in implementations:
            if impl.level not in (AvailabilityLevel.LOCAL, AvailabilityLevel.PUBLIC):
                if impl.requires_auth or impl.config_keys:
                    return True
        return False
    
    def get_configuring_features(self, config: Dict[str, Any]) -> List[str]:
        """获取当前配置下需要配置的功能"""
        features = []
        for feature_id in self.get_all_features():
            impl = self.get_best_available(feature_id, config, prefer_free=True)
            if impl is None or impl.level in (AvailabilityLevel.LOCAL, AvailabilityLevel.PUBLIC):
                # 可能需要更好方案
                if self.needs_configuration(feature_id):
                    features.append(feature_id)
        return features


# 全局实例
_matrix: Optional[DowngradeMatrix] = None


def get_downgrade_matrix() -> DowngradeMatrix:
    """获取降级矩阵全局实例"""
    global _matrix
    if _matrix is None:
        _matrix = DowngradeMatrix.get_instance()
    return _matrix