"""
分布式环境数据网络
==================

P2P节点数据共享系统：
1. 节点共享的"环境本底库"
2. 模型参数包交换
3. 行业知识协同

这是区别于传统软件的最大亮点——"行业记忆"

Author: Hermes Desktop EIA System
"""

import json
import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import asyncio.lock


class DataCategory(str, Enum):
    """数据类别"""
    AIR_BASELINE = "air_baseline"         # 空气质量本底
    WATER_BASELINE = "water_baseline"     # 水质本底
    SOIL_BASELINE = "soil_baseline"       # 土壤本底
    NOISE_BASELINE = "noise_baseline"     # 噪声本底
    METEO_DATA = "meteo_data"             # 气象数据
    EMISSION_FACTORS = "emission_factors" # 排放因子
    MODEL_PARAMS = "model_params"         # 模型参数
    MONITORING_REPORT = "monitoring_report"  # 监测报告（脱敏后）


class DataQuality(str, Enum):
    """数据质量等级"""
    VERIFIED = "verified"                 # 已验证（官方/权威）
    VALIDATED = "validated"              # 已验证（同行评审）
    UNVERIFIED = "unverified"            # 未验证
    SUSPECTED = "suspected"              # 可疑/需核实


class NodeRole(str, Enum):
    """节点角色"""
    CONTRIBUTOR = "contributor"          # 数据贡献者
    CONSUMER = "consumer"                # 数据消费者
    VALIDATOR = "validator"              # 验证节点
    SUPERVISOR = "supervisor"            # 监督节点


@dataclass
class DataPackage:
    """数据包"""
    id: str
    category: DataCategory
    title: str
    description: str
    region: str                          # 区域
    time_period: str                      # 时间范围
    provider_node: str                   # 提供节点ID
    provider_name: str                   # 提供者名称
    created_at: datetime
    updated_at: datetime
    data: Dict[str, Any]                 # 数据内容
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    quality: DataQuality = DataQuality.UNVERIFIED
    download_count: int = 0
    rating: float = 0.0
    tags: List[str] = field(default_factory=list)
    is_public: bool = True               # 是否公开共享
    license: str = "CC-BY-NC-SA"         # 许可证


@dataclass
class ModelParameterPackage:
    """模型参数包"""
    id: str
    name: str
    description: str
    region: str                          # 适用区域
    region_code: str                     # 区域代码
    model_type: str                      # 模型类型
    parameters: Dict[str, Any]          # 参数值
    validation_results: Dict[str, float] = field(default_factory=dict)  # 验证结果
    source: str = ""                      # 数据来源
    provider: str = ""
    created_at: datetime
    accuracy: float = 0.0                # 准确度评估


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    node_name: str
    role: NodeRole
    region: str
    specialties: List[str] = field(default_factory=list)  # 专业领域
    contribution_score: float = 0.0     # 贡献评分
    reputation: float = 0.0             # 信誉评分
    data_count: int = 0                  # 提供数据量
    uptime: float = 0.0                 # 在线时长
    last_active: datetime = None
    is_online: bool = False


@dataclass
class DataRequest:
    """数据请求"""
    id: str
    requester_id: str
    category: DataCategory
    region: str
    time_period: str
    description: str
    urgency: str = "normal"             # normal/urgent
    status: str = "pending"              # pending/fulfilled/declined
    created_at: datetime
    responses: List[str] = field(default_factory=list)  # 响应节点列表


@dataclass
class DataSharingStats:
    """数据共享统计"""
    total_packages: int = 0
    total_downloads: int = 0
    total_nodes: int = 0
    online_nodes: int = 0
    top_providers: List[Dict] = field(default_factory=list)
    popular_categories: List[Dict] = field(default_factory=list)


class DataAnonymizer:
    """
    数据脱敏器

    确保共享数据不包含敏感信息
    """

    @staticmethod
    def anonymize_report(report: Dict) -> Dict:
        """
        脱敏监测报告

        移除：
        - 企业具体名称
        - 精确位置（保留区域精度）
        - 联系人信息
        """
        anonymized = report.copy()

        # 移除敏感字段
        sensitive_fields = [
            "company_name", "company_address", "contact_person",
            "contact_phone", "detailed_location", "gps_coordinates"
        ]

        for field in sensitive_fields:
            if field in anonymized:
                anonymized[field] = "[已脱敏]"

        # 模糊化精确位置
        if "latitude" in anonymized:
            anonymized["latitude"] = round(anonymized["latitude"], 2)  # 保留0.01度精度
        if "longitude" in anonymized:
            anonymized["longitude"] = round(anonymized["longitude"], 2)

        anonymized["_anonymized"] = True
        anonymized["_anonymized_at"] = datetime.now().isoformat()

        return anonymized

    @staticmethod
    def verify_anonymized(data: Dict) -> bool:
        """验证数据是否已脱敏"""
        return data.get("_anonymized", False)


class P2PBaselineNetwork:
    """
    P2P环境本底数据网络

    功能：
    1. 节点注册与发现
    2. 数据包发布与订阅
    3. 数据检索与下载
    4. 模型参数交换
    5. 信誉评分系统
    """

    def __init__(self, node_id: str = None, node_name: str = ""):
        self.node_id = node_id or str(uuid.uuid4())[:12]
        self.node_name = node_name or f"节点_{self.node_id[:6]}"

        # 数据存储
        self._local_packages: Dict[str, DataPackage] = {}
        self._parameter_packages: Dict[str, ModelParameterPackage] = {}
        self._node_registry: Dict[str, NodeInfo] = {}
        self._data_requests: Dict[str, DataRequest] = {}

        # 本地数据
        self._my_data: List[DataPackage] = []
        self._my_downloads: List[str] = []  # 下载记录

        # 统计
        self._stats = DataSharingStats()

        # 事件回调
        self._on_new_data: Optional[Callable] = None
        self._on_data_request: Optional[Callable] = None

        # 在线状态
        self._is_online = False

        # 初始化本地节点信息
        self._self_info = NodeInfo(
            node_id=self.node_id,
            node_name=self.node_name,
            role=NodeRole.CONTRIBUTOR,
            region="",
            last_active=datetime.now()
        )

    async def start(self):
        """启动P2P网络"""
        self._is_online = True
        self._self_info.is_online = True
        self._self_info.last_active = datetime.now()

        # 注册本节点
        await self.register_node(self._self_info)

    async def stop(self):
        """停止P2P网络"""
        self._is_online = False
        self._self_info.is_online = False

    async def register_node(self, node: NodeInfo) -> bool:
        """
        注册节点

        实际需要通过P2P网络广播
        """
        self._node_registry[node.node_id] = node
        return True

    async def discover_nodes(
        self,
        region: str = None,
        specialty: str = None
    ) -> List[NodeInfo]:
        """
        发现节点

        实际需要通过Kademlia DHT或广播发现
        """
        nodes = list(self._node_registry.values())

        # 过滤
        if region:
            nodes = [n for n in nodes if region in n.region]
        if specialty:
            nodes = [n for n in nodes if specialty in n.specialties]

        return [n for n in nodes if n.node_id != self.node_id]

    # ============ 数据包管理 ============

    async def publish_data(
        self,
        category: DataCategory,
        title: str,
        description: str,
        region: str,
        time_period: str,
        data: Dict,
        metadata: Dict = None,
        tags: List[str] = None,
        is_public: bool = True
    ) -> DataPackage:
        """
        发布数据

        Args:
            category: 数据类别
            title: 数据标题
            description: 描述
            region: 区域
            time_period: 时间范围
            data: 数据内容
            metadata: 元数据
            tags: 标签
            is_public: 是否公开

        Returns:
            DataPackage: 创建的数据包
        """
        package = DataPackage(
            id=str(uuid.uuid4())[:12],
            category=category,
            title=title,
            description=description,
            region=region,
            time_period=time_period,
            provider_node=self.node_id,
            provider_name=self.node_name,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            data=data,
            metadata=metadata or {},
            quality=DataQuality.UNVERIFIED,
            tags=tags or [],
            is_public=is_public
        )

        # 脱敏处理
        if category == DataCategory.MONITORING_REPORT:
            package.data = DataAnonymizer.anonymize_report(data)

        # 存储本地
        self._local_packages[package.id] = package
        self._my_data.append(package)

        # 计算哈希
        package.metadata["content_hash"] = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]

        return package

    async def search_data(
        self,
        category: DataCategory = None,
        region: str = None,
        time_period: str = None,
        keyword: str = None,
        quality: DataQuality = None,
        limit: int = 20
    ) -> List[DataPackage]:
        """
        搜索数据

        实际通过P2P网络广播查询请求
        """
        results = []

        # 搜索本地数据
        for pkg in self._local_packages.values():
            if not pkg.is_public:
                continue

            if category and pkg.category != category:
                continue
            if region and region not in pkg.region:
                continue
            if time_period and time_period not in pkg.time_period:
                continue
            if keyword and keyword not in pkg.title and keyword not in pkg.description:
                continue
            if quality and pkg.quality != quality:
                continue

            results.append(pkg)

        # 按质量评分排序
        results.sort(key=lambda x: (x.quality.value, x.rating, x.download_count), reverse=True)

        return results[:limit]

    async def download_data(
        self,
        package_id: str,
        callback: Callable = None
    ) -> Optional[DataPackage]:
        """
        下载数据包

        实际通过P2P网络从源节点获取
        """
        # 查找本地缓存
        if package_id in self._local_packages:
            pkg = self._local_packages[package_id]
            pkg.download_count += 1
            self._my_downloads.append(package_id)
            return pkg

        # 模拟从网络下载
        # 实际需要P2P传输协议

        return None

    # ============ 模型参数包 ============

    async def publish_model_params(
        self,
        name: str,
        description: str,
        region: str,
        region_code: str,
        model_type: str,
        parameters: Dict,
        source: str = ""
    ) -> ModelParameterPackage:
        """
        发布模型参数包

        用于节点间交换经过验证的本地化模型参数
        """
        package = ModelParameterPackage(
            id=str(uuid.uuid4())[:12],
            name=name,
            description=description,
            region=region,
            region_code=region_code,
            model_type=model_type,
            parameters=parameters,
            source=source,
            provider=self.node_name,
            created_at=datetime.now()
        )

        self._parameter_packages[package.id] = package

        return package

    async def get_localized_params(
        self,
        region: str,
        model_type: str = "gaussian_plume"
    ) -> Optional[ModelParameterPackage]:
        """
        获取本地化模型参数

        这是P2P网络的核心价值：
        比通用模型更精准的本地化参数
        """
        for pkg in self._parameter_packages.values():
            if region in pkg.region and model_type in pkg.model_type:
                return pkg

        return None

    # ============ 数据请求 ============

    async def request_data(
        self,
        category: DataCategory,
        region: str,
        time_period: str,
        description: str = "",
        urgency: str = "normal"
    ) -> DataRequest:
        """
        发布数据请求

        当搜索不到需要的数据时，可以发布请求
        """
        request = DataRequest(
            id=str(uuid.uuid4())[:12],
            requester_id=self.node_id,
            category=category,
            region=region,
            time_period=time_period,
            description=description,
            urgency=urgency,
            created_at=datetime.now()
        )

        self._data_requests[request.id] = request

        return request

    # ============ 信誉与评分 ============

    async def rate_data(
        self,
        package_id: str,
        rating: float,
        comment: str = ""
    ) -> bool:
        """
        评价数据包

        影响数据包的质量评分
        """
        if package_id not in self._local_packages:
            return False

        pkg = self._local_packages[package_id]

        # 更新评分
        old_count = pkg.download_count
        old_rating = pkg.rating

        # 增量更新评分
        pkg.rating = (old_rating * old_count + rating) / (old_count + 1) if old_count > 0 else rating

        return True

    async def validate_data(
        self,
        package_id: str,
        is_valid: bool,
        validator_id: str = None
    ) -> bool:
        """
        验证数据包

        提升数据质量等级
        """
        if package_id not in self._local_packages:
            return False

        pkg = self._local_packages[package_id]

        if is_valid:
            if pkg.quality == DataQuality.UNVERIFIED:
                pkg.quality = DataQuality.VALIDATED
            elif pkg.quality == DataQuality.VALIDATED:
                pkg.quality = DataQuality.VERIFIED

        return True

    # ============ 统计 ============

    async def get_network_stats(self) -> DataSharingStats:
        """获取网络统计"""
        stats = DataSharingStats()

        stats.total_packages = len(self._local_packages)
        stats.total_downloads = sum(p.download_count for p in self._local_packages.values())
        stats.total_nodes = len(self._node_registry)
        stats.online_nodes = sum(1 for n in self._node_registry.values() if n.is_online)

        # 热门类别
        categories = {}
        for pkg in self._local_packages.values():
            cat = pkg.category.value
            categories[cat] = categories.get(cat, 0) + 1

        stats.popular_categories = sorted(
            [{"category": k, "count": v} for k, v in categories.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:5]

        return stats

    # ============ 便捷方法 ============

    async def share_monitoring_report(
        self,
        report_data: Dict,
        region: str,
        time_period: str,
        tags: List[str] = None
    ) -> DataPackage:
        """便捷方法：分享监测报告（自动脱敏）"""
        return await self.publish_data(
            category=DataCategory.MONITORING_REPORT,
            title=report_data.get("title", "监测报告"),
            description=report_data.get("description", ""),
            region=region,
            time_period=time_period,
            data=report_data,
            tags=tags or ["监测报告", region]
        )

    async def get_environmental_baseline(
        self,
        region: str,
        baseline_type: str = "air"
    ) -> Optional[Dict]:
        """
        获取环境本底数据

        从P2P网络搜索
        """
        category_map = {
            "air": DataCategory.AIR_BASELINE,
            "water": DataCategory.WATER_BASELINE,
            "soil": DataCategory.SOIL_BASELINE,
            "noise": DataCategory.NOISE_BASELINE
        }

        category = category_map.get(baseline_type, DataCategory.AIR_BASELINE)

        results = await self.search_data(
            category=category,
            region=region,
            quality=DataQuality.VERIFIED,
            limit=5
        )

        if results:
            # 返回最新、最优的数据
            return results[0].data

        return None

    def get_my_contributions(self) -> List[DataPackage]:
        """获取我的贡献"""
        return self._my_data.copy()

    def get_my_downloads(self) -> List[DataPackage]:
        """获取我的下载记录"""
        return [self._local_packages.get(pid) for pid in self._my_downloads
                if pid in self._local_packages]


# ============ 典型参数库 ============

class TypicalParametersLibrary:
    """
    典型参数库

    内置各地区经验参数
    解决新建项目缺乏历史数据的痛点
    """

    def __init__(self):
        # 大气扩散参数（按区域）
        self.diffusion_params = {
            "华东平原": {
                "a": 0.076,
                "b": 0.90,
                "c": 0.15,
                "d": 0.70,
                "description": "适用于江苏、安徽、山东平原地区"
            },
            "华北平原": {
                "a": 0.11,
                "b": 0.91,
                "c": 0.18,
                "d": 0.72,
                "description": "适用于河北、河南平原地区"
            },
            "四川盆地": {
                "a": 0.08,
                "b": 0.78,
                "c": 0.12,
                "d": 0.65,
                "description": "适用于四川盆地及类似地形"
            }
        }

        # 行业排放因子
        self.emission_factors = {
            "化工": {
                "SO2": {"value": 15.5, "unit": "kg/t产品", "description": "催化燃烧"},
                "NOx": {"value": 8.2, "unit": "kg/t产品", "description": ""},
                "烟粉尘": {"value": 5.0, "unit": "kg/t产品", "description": ""},
            },
            "电力": {
                "SO2": {"value": 2.5, "unit": "kg/t标煤", "description": "燃煤电厂"},
                "NOx": {"value": 3.5, "unit": "kg/t标煤", "description": ""},
                "烟粉尘": {"value": 1.2, "unit": "kg/t标煤", "description": ""},
            },
            "钢铁": {
                "SO2": {"value": 1.8, "unit": "kg/t铁", "description": "烧结工序"},
                "NOx": {"value": 1.5, "unit": "kg/t铁", "description": ""},
                "烟粉尘": {"value": 8.0, "unit": "kg/t铁", "description": ""},
            }
        }

    def get_diffusion_params(self, region: str = None) -> Dict:
        """获取扩散参数"""
        if region:
            for key, params in self.diffusion_params.items():
                if key in region:
                    return params
        return self.diffusion_params.get("华东平原", {})

    def get_emission_factor(self, industry: str, pollutant: str) -> Optional[Dict]:
        """获取排放因子"""
        return self.emission_factors.get(industry, {}).get(pollutant)


# ============ 全局实例 ============

_p2p_network: Optional[P2PBaselineNetwork] = None
_param_library: Optional[TypicalParametersLibrary] = None


def get_p2p_network(node_id: str = None, node_name: str = "") -> P2PBaselineNetwork:
    """获取P2P网络实例"""
    global _p2p_network
    if _p2p_network is None:
        _p2p_network = P2PBaselineNetwork(node_id, node_name)
    return _p2p_network


def get_param_library() -> TypicalParametersLibrary:
    """获取典型参数库"""
    global _param_library
    if _param_library is None:
        _param_library = TypicalParametersLibrary()
    return _param_library
