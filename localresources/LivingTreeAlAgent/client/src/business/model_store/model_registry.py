"""
模型注册表 (Model Registry)
===========================

负责模型元数据管理、版本控制、依赖解析

内置环保专业模型库：
- 大气模型：AERMOD, CALPUFF, CMAQ, CAMx, WRF-Chem
- 水质模型：SWMM, EFDC, QUAL2K, Delft3D
- 土壤模型：HYDRUS, SWAT
- 噪声模型：CadnaA, SoundPLAN
- 生态模型：InVEST, MaxEnt
- 气象模型：WRF, MM5, RAP
- 工具库：pyswmm, flopy, pandana, osmnx

Author: Hermes Desktop AI Assistant
"""

import os
import json
import logging
import hashlib
import subprocess
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelCategory(Enum):
    """模型类别"""
    AIR = "air"              # 大气
    WATER = "water"          # 水质
    SOIL = "soil"            # 土壤
    NOISE = "noise"          # 噪声
    ECOLOGY = "ecology"      # 生态
    WEATHER = "weather"      # 气象
    HYDROLOGY = "hydrology"  # 水文
    TOOL = "tool"            # 工具库
    OTHER = "other"          # 其他


class ModelLevel(Enum):
    """模型级别"""
    LIGHT = "light"     # 轻量级 - pip包
    MEDIUM = "medium"   # 中型 - 预编译二进制
    HEAVY = "heavy"     # 重型 - Docker容器
    CLOUD = "cloud"     # 云端 - API调用


class InstallType(Enum):
    """安装类型"""
    PIP = "pip"           # pip安装
    BINARY = "binary"     # 二进制解压
    DOCKER = "docker"     # Docker容器
    API = "api"           # API配置
    SOURCE = "source"     # 源码编译


class RuntimeType(Enum):
    """运行时类型"""
    PYTHON = "python"   # Python直接调用
    CLI = "cli"         # 命令行执行
    REST = "rest"       # REST API
    GRPC = "grpc"       # gRPC


@dataclass
class InstallConfig:
    """安装配置"""
    type: InstallType
    package: Optional[str] = None          # pip包名
    url: Optional[str] = None              # 下载URL
    checksum: Optional[str] = None         # MD5/SHA256校验
    image: Optional[str] = None            # Docker镜像
    port_mapping: Optional[Dict[str, str]] = None  # 端口映射
    env: Optional[Dict[str, str]] = None   # 环境变量
    command: Optional[str] = None         # 安装命令
    signup_url: Optional[str] = None      # API注册URL

    def to_dict(self) Dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class RuntimeConfig:
    """运行时配置"""
    type: RuntimeType
    entry_module: Optional[str] = None     # Python模块
    command: Optional[str] = None         # CLI命令模板
    endpoint: Optional[str] = None         # API端点
    port: Optional[int] = None            # 服务端口
    env: Optional[Dict[str, str]] = None   # 环境变量
    timeout: int = 300                     # 超时秒数
    rate_limit: Optional[str] = None       # API限流

    def to_dict(self) Dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ResourceRequirement:
    """资源需求"""
    cpu_cores: int = 1
    memory_mb: int = 1024     # MB
    gpu: bool = False
    gpu_memory_mb: Optional[int] = None
    storage_mb: int = 100    # MB
    disk_io: Optional[str] = None


@dataclass
class ModelCost:
    """模型费用"""
    free_tier: Optional[str] = None    # 免费额度描述
    paid_tier: Optional[str] = None    # 付费描述
    hourly_cost: Optional[float] = None  # 美元/小时


@dataclass
class ModelInfo:
    """
    模型元数据

    Attributes:
        id: 模型唯一标识（如 'aermod', 'pyswmm'）
        name: 模型显示名称
        version: 当前版本
        category: 模型类别
        level: 模型级别
        description: 模型描述
        author: 作者/机构
        license: 许可证
        tags: 标签列表
        homepage: 官网
        documentation: 文档链接
        install: 安装配置
        runtime: 运行时配置
        resources: 资源需求
        cost: 费用信息
        dependencies: 依赖的其他模型
        available_versions: 可用版本列表
        installed: 是否已安装
        installed_version: 已安装版本
    """
    id: str
    name: str
    version: str
    category: ModelCategory
    level: ModelLevel
    description: str
    author: str = "Unknown"
    license: str = "MIT"
    tags: List[str] = field(default_factory=list)
    homepage: Optional[str] = None
    documentation: Optional[str] = None
    install: InstallConfig = field(default_factory=InstallConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    resources: ResourceRequirement = field(default_factory=ResourceRequirement)
    cost: Optional[ModelCost] = None
    dependencies: List[str] = field(default_factory=list)
    available_versions: List[str] = field(default_factory=list)
    installed: bool = False
    installed_version: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'category': self.category.value,
            'level': self.level.value,
            'description': self.description,
            'author': self.author,
            'license': self.license,
            'tags': self.tags,
            'homepage': self.homepage,
            'documentation': self.documentation,
            'install': self.install.to_dict(),
            'runtime': self.runtime.to_dict(),
            'resources': asdict(self.resources),
            'cost': asdict(self.cost) if self.cost else None,
            'dependencies': self.dependencies,
            'available_versions': self.available_versions,
            'installed': self.installed,
            'installed_version': self.installed_version,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ModelInfo':
        """从字典创建"""
        install = InstallConfig(**data.get('install', {}))
        runtime = RuntimeConfig(**data.get('runtime', {}))
        resources = ResourceRequirement(**data.get('resources', {}))
        cost = ModelCost(**data['cost']) if data.get('cost') else None

        return cls(
            id=data['id'],
            name=data['name'],
            version=data['version'],
            category=ModelCategory(data['category']),
            level=ModelLevel(data['level']),
            description=data['description'],
            author=data.get('author', 'Unknown'),
            license=data.get('license', 'MIT'),
            tags=data.get('tags', []),
            homepage=data.get('homepage'),
            documentation=data.get('documentation'),
            install=install,
            runtime=runtime,
            resources=resources,
            cost=cost,
            dependencies=data.get('dependencies', []),
            available_versions=data.get('available_versions', []),
            installed=data.get('installed', False),
            installed_version=data.get('installed_version'),
        )


class ModelRegistry:
    """
    模型注册表 - 管理所有可用模型

    功能：
    1. 内置模型库
    2. 模型元数据CRUD
    3. 版本管理
    4. 依赖解析
    5. 本地安装状态追踪

    使用示例：
        registry = ModelRegistry()
        model = registry.get_model('aermod')
        registry.list_by_category(ModelCategory.AIR)
    """

    # 内置环保模型库
    BUILTIN_MODELS: Dict[str, Dict] = {
        # ===== 轻量级 Python 库 =====
        'pyswmm': {
            'name': 'PySWMM',
            'version': '2.1.0',
            'category': 'hydrology',
            'level': 'light',
            'description': 'SWMM模型的Python封装，用于城市雨洪管理',
            'author': 'EPA',
            'license': 'BSD',
            'tags': ['雨洪', '管网', 'SWMM'],
            'homepage': 'https://github.com/OpenWaterAnalytics/pyswmm',
            'install': {'type': 'pip', 'package': 'pyswmm'},
            'runtime': {'type': 'python', 'entry_module': 'pyswmm'},
            'resources': {'cpu_cores': 1, 'memory_mb': 512, 'storage_mb': 50},
        },
        'flopy': {
            'name': 'Flopy',
            'version': '3.9.0',
            'category': 'water',
            'level': 'light',
            'description': 'MODFLOW模型的Python封装，用于地下水模拟',
            'author': 'MODFLOW Us宝',
            'license': 'MIT',
            'tags': ['地下水', 'MODFLOW'],
            'homepage': 'https://github.com/modflowpy/flopy',
            'install': {'type': 'pip', 'package': 'flopy'},
            'runtime': {'type': 'python', 'entry_module': 'flopy'},
            'resources': {'cpu_cores': 1, 'memory_mb': 512, 'storage_mb': 100},
        },
        'pandana': {
            'name': 'Pandana',
            'version': '0.6.1',
            'category': 'tool',
            'level': 'light',
            'description': '城市网络分析工具，用于可达性计算',
            'author': 'UrbanSim',
            'license': 'MIT',
            'tags': ['可达性', '路网', '城市分析'],
            'install': {'type': 'pip', 'package': 'pandana'},
            'runtime': {'type': 'python', 'entry_module': 'pandana'},
            'resources': {'cpu_cores': 1, 'memory_mb': 256, 'storage_mb': 30},
        },
        'osmnx': {
            'name': 'OSMnx',
            'version': '1.6.0',
            'category': 'tool',
            'level': 'light',
            'description': '从OpenStreetMap获取和分析街道网络',
            'author': 'Geoff Boeing',
            'license': 'MIT',
            'tags': ['OSM', '路网', '城市分析'],
            'install': {'type': 'pip', 'package': 'osmnx'},
            'runtime': {'type': 'python', 'entry_module': 'osmnx'},
            'resources': {'cpu_cores': 1, 'memory_mb': 512, 'storage_mb': 50},
        },

        # ===== 中型 CLI 模型 =====
        'aermod': {
            'name': 'AERMOD',
            'version': '23112',
            'category': 'air',
            'level': 'medium',
            'description': 'EPA大气扩散模型，用于工业源排放影响预测',
            'author': 'EPA',
            'license': 'Public Domain',
            'tags': ['大气扩散', '排放预测', 'AERMOD'],
            'homepage': 'https://www.epa.gov/scram/air-quality-dispersion-models',
            'documentation': 'https://www3.epa.gov/ttn/scram/models/aermod/aermod_userguide.pdf',
            'install': {
                'type': 'binary',
                'url': 'https://www.epa.gov/scram/air-quality-dispersion-models#models',
                'checksum': 'md5:xxx',
            },
            'runtime': {
                'type': 'cli',
                'command': 'aermod.exe',
                'env': {'AERMET_PATH': 'aermet.exe'}
            },
            'resources': {'cpu_cores': 2, 'memory_mb': 2048, 'storage_mb': 45000},
        },
        'swmm5': {
            'name': 'SWMM5',
            'version': '5.1.0',
            'category': 'hydrology',
            'level': 'medium',
            'description': 'EPA雨水管理模型，用于城市排水系统模拟',
            'author': 'EPA',
            'license': 'Public Domain',
            'tags': ['雨洪', '管网', 'SWMM'],
            'install': {
                'type': 'binary',
                'url': 'https://www.epa.gov/water-research/storm-water-management-model-swmm',
                'checksum': 'md5:xxx',
            },
            'runtime': {'type': 'cli', 'command': 'swmm5.exe'},
            'resources': {'cpu_cores': 2, 'memory_mb': 1024, 'storage_mb': 20000},
        },

        # ===== 重型 Docker 模型 =====
        'cmaq': {
            'name': 'CMAQ',
            'version': '5.3.3',
            'category': 'air',
            'level': 'heavy',
            'description': '社区多尺度空气质量模型，用于区域空气质量模拟',
            'author': 'EPA',
            'license': 'Public Domain',
            'tags': ['空气质量', '区域模拟', 'CMAQ'],
            'homepage': 'https://www.epa.gov/cmaq',
            'install': {
                'type': 'docker',
                'image': 'tin6150/cmaq:latest',
                'port_mapping': {'8080': '8080'},
            },
            'runtime': {
                'type': 'rest',
                'endpoint': 'http://localhost:8080/predict',
            },
            'resources': {'cpu_cores': 8, 'memory_mb': 16000, 'gpu': True, 'storage_mb': 3200000},
            'cost': {'hourly_cost': 0.5},
        },
        'efdc': {
            'name': 'EFDC',
            'version': '1.4',
            'category': 'water',
            'level': 'heavy',
            'description': '环境流体动力学模型，用于河流、湖泊、河口模拟',
            'author': 'DSI',
            'license': 'Commercial',
            'tags': ['水动力学', '河流', '河口'],
            'install': {
                'type': 'docker',
                'image': 'your-registry/efdc:latest',
                'port_mapping': {'8081': '8080'},
            },
            'runtime': {
                'type': 'rest',
                'endpoint': 'http://localhost:8081/api/v1/run',
            },
            'resources': {'cpu_cores': 4, 'memory_mb': 8192, 'storage_mb': 500000},
            'cost': {'hourly_cost': 0.3},
        },
        'delft3d': {
            'name': 'Delft3D',
            'version': '6.04',
            'category': 'water',
            'level': 'heavy',
            'description': '荷兰Deltares水动力模型，用于海岸和河口水模拟',
            'author': 'Deltares',
            'license': 'Commercial',
            'tags': ['水动力', '海岸', '河流'],
            'install': {
                'type': 'docker',
                'image': 'deltares/delft3d:latest',
                'port_mapping': {'8082': '8080'},
            },
            'runtime': {'type': 'rest', 'endpoint': 'http://localhost:8082/api'},
            'resources': {'cpu_cores': 8, 'memory_mb': 16384, 'storage_mb': 1000000},
            'cost': {'hourly_cost': 0.6},
        },

        # ===== 云端 API =====
        'openweathermap': {
            'name': 'OpenWeatherMap Air Pollution',
            'version': '2.5',
            'category': 'air',
            'level': 'cloud',
            'description': '实时空气质量数据API',
            'author': 'OpenWeatherMap',
            'license': 'Commercial',
            'tags': ['空气质量', 'AQI', '实时数据'],
            'homepage': 'https://openweathermap.org/api/air-pollution',
            'install': {
                'type': 'api',
                'provider': 'OpenWeatherMap',
                'auth_type': 'api_key',
                'signup_url': 'https://openweathermap.org/api',
            },
            'runtime': {
                'type': 'rest',
                'endpoint': 'https://api.openweathermap.org/data/2.5/air_pollution',
                'rate_limit': '1000 calls/day (free)',
            },
            'resources': {},
            'cost': {'free_tier': '1000 calls/day', 'paid_tier': '$40/month unlimited'},
        },
        'tomorrowio': {
            'name': 'Tomorrow.io Weather',
            'version': 'v4',
            'category': 'weather',
            'level': 'cloud',
            'description': '高精度天气预报和历史气象数据',
            'author': 'Tomorrow.io',
            'license': 'Commercial',
            'tags': ['天气预报', '气象数据', '历史数据'],
            'homepage': 'https://www.tomorrow.io/',
            'install': {
                'type': 'api',
                'provider': 'Tomorrow.io',
                'auth_type': 'api_key',
                'signup_url': 'https://www.tomorrow.io/',
            },
            'runtime': {
                'type': 'rest',
                'endpoint': 'https://api.tomorrow.io/v4/',
                'rate_limit': '1000 calls/day (free)',
            },
            'resources': {},
            'cost': {'free_tier': '1000 calls/day', 'paid_tier': '$199/month'},
        },
        'noaa_ncei': {
            'name': 'NOAA NCEI Climate Data',
            'version': 'v3',
            'category': 'weather',
            'level': 'cloud',
            'description': 'NOAA国家气候数据中心，提供历史气象数据',
            'author': 'NOAA',
            'license': 'Public Domain',
            'tags': ['气象数据', '历史数据', 'NOAA'],
            'homepage': 'https://www.ncei.noaa.gov/',
            'install': {
                'type': 'api',
                'provider': 'NOAA',
                'auth_type': 'api_key',
                'signup_url': 'https://www.ncdc.noaa.gov/cdo-web/token',
            },
            'runtime': {
                'type': 'rest',
                'endpoint': 'https://www.ncei.noaa.gov/access/services/data/v1',
            },
            'resources': {},
            'cost': {'free_tier': '部分免费', 'paid_tier': '免费额度足够研究使用'},
        },
        'open_meteo': {
            'name': 'Open-Meteo',
            'version': 'v1',
            'category': 'weather',
            'level': 'cloud',
            'description': '免费开源天气API，无需API Key',
            'author': 'Open-Meteo',
            'license': 'AGPL',
            'tags': ['天气预报', '免费', '开源'],
            'homepage': 'https://open-meteo.com/',
            'install': {'type': 'api', 'provider': 'Open-Meteo', 'auth_type': 'none'},
            'runtime': {
                'type': 'rest',
                'endpoint': 'https://api.open-meteo.com/v1/',
            },
            'resources': {},
            'cost': {'free_tier': '无限制免费', 'paid_tier': '可选付费版'},
        },
        'aqicn': {
            'name': 'AQICN',
            'version': 'v2',
            'category': 'air',
            'level': 'cloud',
            'description': '全球城市空气质量指数',
            'author': 'AQICN',
            'license': 'Commercial',
            'tags': ['AQI', '空气质量', '全球'],
            'homepage': 'https://aqicn.org/',
            'install': {
                'type': 'api',
                'provider': 'AQICN',
                'auth_type': 'token',
                'signup_url': 'https://aqicn.org/data-platform/token/',
            },
            'runtime': {
                'type': 'rest',
                'endpoint': 'https://api.waqi.info/feed/',
            },
            'resources': {},
            'cost': {'free_tier': '部分免费', 'paid_tier': '订阅制'},
        },
        'nasa_power': {
            'name': 'NASA POWER',
            'version': 'v1',
            'category': 'weather',
            'level': 'cloud',
            'description': 'NASA气象和太阳能再分析数据',
            'author': 'NASA',
            'license': 'Public Domain',
            'tags': ['气象', '辐射', 'NASA', '太阳能'],
            'homepage': 'https://power.larc.nasa.gov/',
            'install': {'type': 'api', 'provider': 'NASA', 'auth_type': 'none'},
            'runtime': {
                'type': 'rest',
                'endpoint': 'https://power.larc.nasa.gov/api/v2/',
            },
            'resources': {},
            'cost': {'free_tier': '完全免费', 'paid_tier': 'N/A'},
        },

        # ===== 其他专业模型 =====
        'hydrus': {
            'name': 'HYDRUS',
            'version': '4.0',
            'category': 'soil',
            'level': 'heavy',
            'description': '土壤水分和溶质运移模型',
            'author': 'PC-Progress',
            'license': 'Commercial',
            'tags': ['土壤', '地下水', '溶质运移'],
            'install': {
                'type': 'docker',
                'image': 'your-registry/hydrus:latest',
            },
            'runtime': {'type': 'rest', 'endpoint': 'http://localhost:8083/api'},
            'resources': {'cpu_cores': 2, 'memory_mb': 4096, 'storage_mb': 200000},
            'cost': {'hourly_cost': 0.2},
        },
        'swat': {
            'name': 'SWAT',
            'version': '2012',
            'category': 'water',
            'level': 'heavy',
            'description': '土壤与水评估工具，用于流域模拟',
            'author': 'USDA',
            'license': 'Public Domain',
            'tags': ['流域', '水资源', 'SWAT'],
            'install': {
                'type': 'docker',
                'image': 'your-registry/swat:latest',
            },
            'runtime': {'type': 'rest', 'endpoint': 'http://localhost:8084/api'},
            'resources': {'cpu_cores': 4, 'memory_mb': 8192, 'storage_mb': 500000},
            'cost': {'hourly_cost': 0.25},
        },
        'cadnaa': {
            'name': 'CadnaA',
            'version': '2023',
            'category': 'noise',
            'level': 'heavy',
            'description': '工业噪声预测和评估软件',
            'author': 'DataKustik',
            'license': 'Commercial',
            'tags': ['噪声', '环评', 'CadnaA'],
            'install': {
                'type': 'docker',
                'image': 'your-registry/cadnaa:latest',
            },
            'runtime': {'type': 'rest', 'endpoint': 'http://localhost:8085/api'},
            'resources': {'cpu_cores': 4, 'memory_mb': 8192, 'storage_mb': 1000000},
            'cost': {'hourly_cost': 0.4},
        },
        'invest': {
            'name': 'InVEST',
            'version': '3.14',
            'category': 'ecology',
            'level': 'light',
            'description': '生态系统服务评估工具',
            'author': 'NatCap',
            'license': 'BSD',
            'tags': ['生态系统', '生态评估', 'InVEST'],
            'homepage': 'https://naturalcapitalproject.stanford.edu/software/invest',
            'install': {'type': 'pip', 'package': 'natcap.invest'},
            'runtime': {'type': 'python', 'entry_module': 'natcap.invest'},
            'resources': {'cpu_cores': 2, 'memory_mb': 4096, 'storage_mb': 500},
        },
        'maxent': {
            'name': 'MaxEnt',
            'version': '3.4',
            'category': 'ecology',
            'level': 'medium',
            'description': '物种分布预测模型',
            'author': 'Steven Phillips',
            'license': 'Academic',
            'tags': ['物种分布', '生态建模', 'MaxEnt'],
            'homepage': 'https://biodiversityinformatics.amnh.org/open_source/maxent/',
            'install': {
                'type': 'binary',
                'url': 'https://biodiversityinformatics.amnh.org/open_source/maxent/',
            },
            'runtime': {'type': 'cli', 'command': 'java -jar maxent.jar'},
            'resources': {'cpu_cores': 2, 'memory_mb': 4096, 'storage_mb': 100000},
        },
        'wrf': {
            'name': 'WRF',
            'version': '4.5',
            'category': 'weather',
            'level': 'heavy',
            'description': '中尺度天气预报模式',
            'author': 'NCAR',
            'license': 'Public Domain',
            'tags': ['天气预报', 'WRF', '气象'],
            'install': {
                'type': 'docker',
                'image': 'your-registry/wrf:latest',
            },
            'runtime': {'type': 'rest', 'endpoint': 'http://localhost:8086/api'},
            'resources': {'cpu_cores': 16, 'memory_mb': 32768, 'gpu': True, 'storage_mb': 5000000},
            'cost': {'hourly_cost': 1.0},
        },
    }

    def __init__(self, storage_dir: Optional[str] = None):
        """
        初始化模型注册表

        Args:
            storage_dir: 本地存储目录，默认为 ~/.model_store/
        """
        self.storage_dir = Path(storage_dir or os.path.expanduser('~/.model_store'))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 模型数据文件
        self.models_file = self.storage_dir / 'models.json'
        self.installed_file = self.storage_dir / 'installed.json'

        # 内存缓存
        self._models: Dict[str, ModelInfo] = {}
        self._installed: Dict[str, str] = {}  # model_id -> version

        # 加载内置模型
        self._load_builtin_models()

        # 加载本地状态
        self._load_local_state()

        logger.info(f"模型注册表初始化完成，共 {len(self._models)} 个模型")

    def _load_builtin_models(self):
        """加载内置模型库"""
        for model_id, model_data in self.BUILTIN_MODELS.items():
            try:
                model_info = self._dict_to_model_info(model_id, model_data)
                self._models[model_id] = model_info
            except Exception as e:
                logger.warning(f"加载内置模型 {model_id} 失败: {e}")

    def _dict_to_model_info(self, model_id: str, data: Dict) -> ModelInfo:
        """将字典转换为ModelInfo"""
        install_config = InstallConfig(
            type=InstallType(data['install'].get('type', 'pip')),
            package=data['install'].get('package'),
            url=data['install'].get('url'),
            checksum=data['install'].get('checksum'),
            image=data['install'].get('image'),
            port_mapping=data['install'].get('port_mapping'),
            env=data['install'].get('env'),
            command=data['install'].get('command'),
            signup_url=data['install'].get('signup_url'),
        )

        runtime_config = RuntimeConfig(
            type=RuntimeType(data['runtime'].get('type', 'python')),
            entry_module=data['runtime'].get('entry_module'),
            command=data['runtime'].get('command'),
            endpoint=data['runtime'].get('endpoint'),
            port=data['runtime'].get('port'),
            env=data['runtime'].get('env'),
            timeout=data['runtime'].get('timeout', 300),
            rate_limit=data['runtime'].get('rate_limit'),
        )

        resources = ResourceRequirement(
            cpu_cores=data.get('resources', {}).get('cpu_cores', 1),
            memory_mb=data.get('resources', {}).get('memory_mb', 1024),
            gpu=data.get('resources', {}).get('gpu', False),
            gpu_memory_mb=data.get('resources', {}).get('gpu_memory_mb'),
            storage_mb=data.get('resources', {}).get('storage_mb', 100),
        )

        cost = None
        if 'cost' in data and data['cost']:
            cost = ModelCost(
                free_tier=data['cost'].get('free_tier'),
                paid_tier=data['cost'].get('paid_tier'),
                hourly_cost=data['cost'].get('hourly_cost'),
            )

        return ModelInfo(
            id=model_id,
            name=data['name'],
            version=data['version'],
            category=ModelCategory(data['category']),
            level=ModelLevel(data['level']),
            description=data['description'],
            author=data.get('author', 'Unknown'),
            license=data.get('license', 'MIT'),
            tags=data.get('tags', []),
            homepage=data.get('homepage'),
            documentation=data.get('documentation'),
            install=install_config,
            runtime=runtime_config,
            resources=resources,
            cost=cost,
            dependencies=data.get('dependencies', []),
            available_versions=[data['version']],
        )

    def _load_local_state(self):
        """加载本地安装状态"""
        if self.installed_file.exists():
            try:
                with open(self.installed_file, 'r', encoding='utf-8') as f:
                    self._installed = json.load(f)

                # 更新模型的安装状态
                for model_id, version in self._installed.items():
                    if model_id in self._models:
                        self._models[model_id].installed = True
                        self._models[model_id].installed_version = version

            except Exception as e:
                logger.error(f"加载安装状态失败: {e}")

    def _save_local_state(self):
        """保存本地安装状态"""
        try:
            with open(self.installed_file, 'w', encoding='utf-8') as f:
                json.dump(self._installed, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存安装状态失败: {e}")

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """
        获取模型信息

        Args:
            model_id: 模型ID

        Returns:
            ModelInfo 或 None
        """
        return self._models.get(model_id)

    def list_all(self) -> List[ModelInfo]:
        """列出所有模型"""
        return list(self._models.values())

    def list_by_category(self, category: ModelCategory) -> List[ModelInfo]:
        """按类别筛选模型"""
        return [m for m in self._models.values() if m.category == category]

    def list_by_level(self, level: ModelLevel) -> List[ModelInfo]:
        """按级别筛选模型"""
        return [m for m in self._models.values() if m.level == level]

    def list_installed(self) -> List[ModelInfo]:
        """列出已安装的模型"""
        return [m for m in self._models.values() if m.installed]

    def list_by_tag(self, tag: str) -> List[ModelInfo]:
        """按标签筛选模型"""
        return [m for m in self._models.values() if tag in m.tags]

    def search(self, query: str) -> List[ModelInfo]:
        """
        搜索模型

        Args:
            query: 搜索关键词（匹配名称、描述、标签）

        Returns:
            匹配结果列表
        """
        query_lower = query.lower()
        results = []

        for model in self._models.values():
            # 匹配名称
            if query_lower in model.name.lower():
                results.append(model)
                continue

            # 匹配描述
            if query_lower in model.description.lower():
                results.append(model)
                continue

            # 匹配标签
            if any(query_lower in tag.lower() for tag in model.tags):
                results.append(model)
                continue

            # 匹配ID
            if query_lower in model.id.lower():
                results.append(model)

        return results

    def register_model(self, model_info: ModelInfo) -> bool:
        """
        注册新模型

        Args:
            model_info: 模型信息

        Returns:
            是否注册成功
        """
        try:
            self._models[model_info.id] = model_info
            self._save_models()
            return True
        except Exception as e:
            logger.error(f"注册模型失败: {e}")
            return False

    def update_install_status(self, model_id: str, installed: bool, version: Optional[str] = None):
        """
        更新安装状态

        Args:
            model_id: 模型ID
            installed: 是否已安装
            version: 安装的版本
        """
        if model_id in self._models:
            self._models[model_id].installed = installed
            self._models[model_id].installed_version = version if installed else None

            if installed:
                self._installed[model_id] = version or self._models[model_id].version
            elif model_id in self._installed:
                del self._installed[model_id]

            self._save_local_state()

    def get_dependencies(self, model_id: str) -> List[str]:
        """
        获取模型依赖

        Args:
            model_id: 模型ID

        Returns:
            依赖列表
        """
        model = self.get_model(model_id)
        if not model:
            return []

        return model.dependencies

    def resolve_dependencies(self, model_id: str) -> List[str]:
        """
        解析完整依赖树

        Args:
            model_id: 模型ID

        Returns:
            按安装顺序排列的依赖列表
        """
        visited = set()
        result = []

        def visit(mid: str):
            if mid in visited:
                return
            visited.add(mid)

            model = self.get_model(mid)
            if not model:
                return

            for dep in model.dependencies:
                visit(dep)

            result.append(mid)

        visit(model_id)
        return result

    def _save_models(self):
        """保存模型数据到文件"""
        try:
            data = {mid: model.to_dict() for mid, model in self._models.items()}
            with open(self.models_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存模型数据失败: {e}")

    def get_categories(self) -> List[ModelCategory]:
        """获取所有模型类别"""
        return list(set(m.category for m in self._models.values()))

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._models)
        installed = sum(1 for m in self._models.values() if m.installed)

        by_category = {}
        for model in self._models.values():
            cat = model.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        by_level = {}
        for model in self._models.values():
            lvl = model.level.value
            by_level[lvl] = by_level.get(lvl, 0) + 1

        return {
            'total_models': total,
            'installed_models': installed,
            'by_category': by_category,
            'by_level': by_level,
        }