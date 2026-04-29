"""
统一环保数据湖 - Environmental Data Lake
=======================================

接入20+类数据源，构建环保数据基础设施

数据源分类：
- 企业内部：DCS、MES、ERP、在线监测、视频监控
- 企业外部：气象、水文、空气质量、排污许可平台、企业信用信息
- 公开数据：环评论坛、投诉平台、学术论文、专利库
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading


class DataSourceType(Enum):
    """数据源类型"""
    DCS = "dcs"                   # 分布式控制系统
    MES = "mes"                   # 生产执行系统
    ERP = "erp"                   # 企业资源计划
    ONLINE_MONITOR = "online"     # 在线监测
    VIDEO = "video"              # 视频监控
    WEATHER = "weather"          # 气象数据
    HYDROLOGY = "hydrology"       # 水文数据
    AIR_QUALITY = "air_quality"   # 空气质量
    PERMIT_PLATFORM = "permit"   # 排污许可平台
    CREDIT_INFO = "credit"        # 企业信用信息
    EIA_FORUM = "eia_forum"      # 环评论坛
    COMPLAINT = "complaint"       # 投诉平台
    ACADEMIC = "academic"        # 学术论文
    PATENT = "patent"            # 专利库


class DataQuality(Enum):
    """数据质量"""
    EXCELLENT = "excellent"  # 实时、准确、完整
    GOOD = "good"            # 较实时、准确
    FAIR = "fair"            # 存在延迟或缺失
    POOR = "poor"            # 质量较差


@dataclass
class DataSource:
    """数据源配置"""
    source_id: str
    source_name: str
    source_type: DataSourceType

    # 连接信息
    endpoint: str = ""
    api_key: str = ""
    username: str = ""
    password: str = ""

    # 配置
    refresh_interval: int = 300  # 秒
    timeout: int = 30
    retry_count: int = 3

    # 状态
    status: str = "disconnected"  # connected/disconnected/error
    last_sync: str = ""
    quality: DataQuality = DataQuality.GOOD

    # 统计
    record_count: int = 0
    error_count: int = 0


@dataclass
class DataRecord:
    """数据记录"""
    record_id: str
    source_id: str
    source_type: DataSourceType

    # 时间
    timestamp: str = ""
    data_date: str = ""

    # 内容
    data_type: str = ""
    data_key: str = ""
    data_value: Any = ""

    # 元数据
    unit: str = ""
    location: str = ""
    tags: List[str] = field(default_factory=list)

    # 质量标记
    quality: DataQuality = DataQuality.GOOD
    quality_score: float = 1.0  # 0-1


@dataclass
class DataQuery:
    """数据查询"""
    query_id: str
    project_id: str

    # 查询条件
    data_types: List[str] = field(default_factory=list)
    source_types: List[DataSourceType] = field(default_factory=list)
    time_range: tuple = None  # (start, end)
    location_filter: Dict = field(default_factory=dict)

    # 聚合选项
    aggregate: str = ""  # none/hour/day/week/month
    group_by: List[str] = field(default_factory=list)

    # 结果
    results: List[DataRecord] = field(default_factory=list)
    total_count: int = 0


class EnvDataLake:
    """
    统一环保数据湖
    =============

    核心功能：
    1. 多源数据接入 - 20+类数据源统一管理
    2. 实时数据同步 - 定时ETL任务
    3. 数据质量监控 - 完整性、准确性检查
    4. 智能数据查询 - 跨源聚合分析
    5. 数据血缘追踪 - 全链路溯源
    """

    def __init__(self):
        # 数据源注册
        self._data_sources: Dict[str, DataSource] = {}

        # 数据存储 (实际应对接时序数据库/图数据库)
        self._data_store: Dict[str, List[DataRecord]] = {}

        # 同步任务
        self._sync_tasks: Dict[str, threading.Thread] = {}

        # 回调函数
        self._callbacks: Dict[str, List[Callable]] = {}

        # 初始化默认数据源
        self._init_default_sources()

    def _init_default_sources(self):
        """初始化默认数据源"""
        default_sources = [
            # 企业内部
            DataSource(
                source_id="DCS-001",
                source_name="1号生产线DCS",
                source_type=DataSourceType.DCS,
                endpoint="192.168.1.100:502",
                refresh_interval=10
            ),
            DataSource(
                source_id="ONLINE-001",
                source_name="废气在线监测",
                source_type=DataSourceType.ONLINE_MONITOR,
                endpoint="https://env-monitor.example.com/api",
                refresh_interval=60
            ),
            DataSource(
                source_id="ONLINE-002",
                source_name="废水在线监测",
                source_type=DataSourceType.ONLINE_MONITOR,
                endpoint="https://env-monitor.example.com/api",
                refresh_interval=60
            ),
            # 气象
            DataSource(
                source_id="WEATHER-001",
                source_name="南京气象站",
                source_type=DataSourceType.WEATHER,
                endpoint="https://weather.example.com/api",
                refresh_interval=300
            ),
            # 空气质量
            DataSource(
                source_id="AIR-001",
                source_name="国控空气站",
                source_type=DataSourceType.AIR_QUALITY,
                endpoint="https://air-quality.example.com/api",
                refresh_interval=60
            ),
            # 排污许可
            DataSource(
                source_id="PERMIT-001",
                source_name="全国排污许可平台",
                source_type=DataSourceType.PERMIT_PLATFORM,
                endpoint="https://permit.mee.gov.cn/api",
                refresh_interval=3600
            ),
        ]

        for source in default_sources:
            self._data_sources[source.source_id] = source

    def register_source(self, source_config: Dict) -> str:
        """注册新数据源"""
        source = DataSource(
            source_id=source_config.get('source_id', str(uuid.uuid4())[:12]),
            source_name=source_config['source_name'],
            source_type=DataSourceType(source_config['source_type']),
            endpoint=source_config.get('endpoint', ''),
            api_key=source_config.get('api_key', ''),
            refresh_interval=source_config.get('refresh_interval', 300)
        )

        self._data_sources[source.source_id] = source
        return source.source_id

    def connect_source(self, source_id: str) -> bool:
        """连接数据源"""
        source = self._data_sources.get(source_id)
        if not source:
            return False

        # 模拟连接
        source.status = "connected"
        source.last_sync = datetime.now().isoformat()
        return True

    def sync_data(self, source_id: str, data: List[Dict]) -> int:
        """
        同步数据
        =======

        将数据写入数据湖
        """
        source = self._data_sources.get(source_id)
        if not source:
            return 0

        records = []
        for item in data:
            record = DataRecord(
                record_id=str(uuid.uuid4())[:12],
                source_id=source_id,
                source_type=source.source_type,
                timestamp=item.get('timestamp', datetime.now().isoformat()),
                data_date=item.get('date', datetime.now().strftime('%Y-%m-%d')),
                data_type=item.get('type', ''),
                data_key=item.get('key', ''),
                data_value=item.get('value'),
                unit=item.get('unit', ''),
                location=item.get('location', ''),
                quality=DataQuality(item.get('quality', 'good'))
            )
            records.append(record)

        # 存储
        if source_id not in self._data_store:
            self._data_store[source_id] = []
        self._data_store[source_id].extend(records)

        # 更新统计
        source.record_count += len(records)
        source.last_sync = datetime.now().isoformat()

        # 触发回调
        self._trigger_callbacks(source_id, records)

        return len(records)

    def query(self, project_id: str,
              data_types: List[str] = None,
              source_types: List[DataSourceType] = None,
              start_date: str = None,
              end_date: str = None,
              aggregate: str = "none") -> DataQuery:
        """
        数据查询
        =======

        跨源聚合查询
        """
        query = DataQuery(
            query_id=str(uuid.uuid4())[:12],
            project_id=project_id,
            data_types=data_types or [],
            source_types=source_types or [],
            aggregate=aggregate
        )

        if start_date:
            query.time_range = (start_date, end_date or datetime.now().strftime('%Y-%m-%d'))

        # 执行查询
        results = []
        for source_id, records in self._data_store.items():
            source = self._data_sources.get(source_id)
            if not source:
                continue

            # 过滤源类型
            if source_types and source.source_type not in source_types:
                continue

            for record in records:
                # 过滤数据类型
                if data_types and record.data_type not in data_types:
                    continue

                # 过滤时间
                if query.time_range:
                    start, end = query.time_range
                    if not (start <= record.data_date <= end):
                        continue

                results.append(record)

        query.results = results
        query.total_count = len(results)

        # 聚合
        if aggregate != "none":
            query.results = self._aggregate_results(results, aggregate)

        return query

    def _aggregate_results(self, records: List[DataRecord],
                          aggregate: str) -> List[DataRecord]:
        """聚合结果"""
        # 按天聚合
        if aggregate == "day":
            daily_data = {}
            for record in records:
                key = (record.data_key, record.data_date[:10])
                if key not in daily_data:
                    daily_data[key] = []
                daily_data[key].append(record)

            aggregated = []
            for (data_key, date), group in daily_data.items():
                values = [r.data_value for r in group if isinstance(r.data_value, (int, float))]
                avg_value = sum(values) / len(values) if values else 0

                aggregated.append(DataRecord(
                    record_id=f"AGG-{data_key}-{date}",
                    source_id=group[0].source_id,
                    source_type=group[0].source_type,
                    timestamp=date,
                    data_date=date,
                    data_key=data_key,
                    data_value=round(avg_value, 2),
                    unit=group[0].unit,
                    quality=DataQuality.GOOD
                ))

            return aggregated

        return records

    def register_callback(self, source_id: str, callback: Callable):
        """注册数据回调"""
        if source_id not in self._callbacks:
            self._callbacks[source_id] = []
        self._callbacks[source_id].append(callback)

    def _trigger_callbacks(self, source_id: str, records: List[DataRecord]):
        """触发回调"""
        callbacks = self._callbacks.get(source_id, [])
        for callback in callbacks:
            try:
                callback(source_id, records)
            except Exception as e:
                print(f"[数据湖] 回调执行失败: {e}")

    def get_data_quality_report(self, source_id: str = None) -> Dict:
        """数据质量报告"""
        if source_id:
            source = self._data_sources.get(source_id)
            if not source:
                return {}
            sources = [source]
        else:
            sources = self._data_sources.values()

        report = {
            "report_date": datetime.now().isoformat(),
            "total_sources": len(sources),
            "connected_sources": sum(1 for s in sources if s.status == "connected"),
            "sources": []
        }

        for source in sources:
            report["sources"].append({
                "source_id": source.source_id,
                "source_name": source.source_name,
                "source_type": source.source_type.value,
                "status": source.status,
                "quality": source.quality.value,
                "record_count": source.record_count,
                "last_sync": source.last_sync,
                "error_count": source.error_count
            })

        return report

    def get_source_status(self) -> List[Dict]:
        """获取数据源状态"""
        return [{
            "source_id": s.source_id,
            "source_name": s.source_name,
            "source_type": s.source_type.value,
            "status": s.status,
            "last_sync": s.last_sync,
            "quality": s.quality.value,
            "record_count": s.record_count
        } for s in self._data_sources.values()]

    def export_to_graph(self, project_id: str,
                        kg_manager) -> bool:
        """
        导出到知识图谱
        ============

        将数据湖中的环境数据同步到知识图谱
        """
        # 查询最近的数据
        query = self.query(
            project_id=project_id,
            source_types=[DataSourceType.ONLINE_MONITOR],
            end_date=datetime.now().strftime('%Y-%m-%d')
        )

        # 转换为图谱实体
        for record in query.results:
            # 创建监测数据实体
            entity = {
                "entity_type": "MonitoringData",
                "properties": {
                    "source": record.source_id,
                    "data_type": record.data_type,
                    "value": record.data_value,
                    "unit": record.unit,
                    "timestamp": record.timestamp,
                    "quality": record.quality.value
                }
            }

            # 实际调用知识图谱API
            # kg_manager.add_entity(project_id, entity)

        return True


# 全局单例
_data_lake = None

def get_data_lake() -> EnvDataLake:
    """获取数据湖单例"""
    global _data_lake
    if _data_lake is None:
        _data_lake = EnvDataLake()
    return _data_lake
