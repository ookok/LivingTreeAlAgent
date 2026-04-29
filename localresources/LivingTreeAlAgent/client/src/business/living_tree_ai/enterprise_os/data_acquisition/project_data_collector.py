"""
项目数据采集器 (Project Data Collector)

多渠道采集项目过程数据：
1. 业主提供 - 客户门户上传
2. 现场采集 - 移动端App拍照/录音/核查表
3. 监测数据 - 对接第三方检测机构API
4. 模型输出 - 计算引擎结果

关键设计：所有数据打上Project_ID标签，确保数据隔离且可追溯。
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Union
import json
import hashlib


class CollectionChannel(Enum):
    """采集渠道"""
    CLIENT_UPLOAD = "client_upload"             # 客户门户上传
    MOBILE_APP = "mobile_app"                   # 移动端App采集
    API_INTEGRATION = "api_integration"         # API接口对接
    MODEL_OUTPUT = "model_output"               # 模型计算输出
    AI_EXTRACTION = "ai_extraction"             # AI从文档提取
    MANUAL_ENTRY = "manual_entry"               # 手动录入
    SMART_BROWSER = "smart_browser"             # AI浏览器自动抓取


class DataFormat(Enum):
    """数据格式"""
    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    JSON = "json"
    XML = "xml"
    DATABASE = "database"


class CollectionStatus(Enum):
    """采集状态"""
    PENDING = "pending"
    COLLECTING = "collecting"
    RECEIVED = "received"                       # 已接收
    PROCESSING = "processing"                   # 处理中
    PROCESSED = "processed"                    # 已处理
    VERIFIED = "verified"                      # 已验证
    REJECTED = "rejected"                      # 已拒绝
    FAILED = "failed"


@dataclass
class ProjectDataItem:
    """
    项目数据项

    统一的数据结构，所有采集的数据都转化为此格式。
    """
    # 基础标识
    item_id: str                               # 数据项ID
    project_id: str                            # 项目ID（核心标签）
    parent_item_id: Optional[str] = None       # 父数据项ID（用于关联）

    # 数据描述
    data_name: str                             # 数据名称
    data_type: str                             # 数据类型（工艺流程图、设备清单、监测报告...）
    data_category: str = "general"             # 数据类别（工艺、设备、原料、产品、排放...）
    description: Optional[str] = None          # 详细描述

    # 来源信息
    collection_channel: CollectionChannel = CollectionChannel.MANUAL_ENTRY
    source_file: Optional[str] = None          # 原始文件名
    source_url: Optional[str] = None           # 原始URL（如有）
    uploaded_by: Optional[str] = None           # 上传人
    collected_at: datetime = field(default_factory=datetime.now)  # 采集时间

    # 数据内容
    format: DataFormat = DataFormat.TEXT       # 数据格式
    content: Optional[Any] = None              # 结构化内容
    file_path: Optional[str] = None            # 文件存储路径
    raw_text: Optional[str] = None            # 原始文本（OCR/语音转写后）

    # 质量信息
    quality_score: float = 0.0                  # 质量评分 (0-1)
    is_verified: bool = False                  # 是否已验证
    verified_by: Optional[str] = None          # 验证人
    verified_at: Optional[datetime] = None     # 验证时间

    # 关联信息
    related_doc_ids: List[str] = field(default_factory=list)  # 关联文档ID
    tags: List[str] = field(default_factory=list)              # 标签
    metadata: Dict[str, Any] = field(default_factory=dict)    # 扩展元数据

    # 状态
    status: CollectionStatus = CollectionStatus.PENDING

    # 版本
    version: int = 1                            # 版本号
    previous_version_id: Optional[str] = None  # 前一版本ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "project_id": self.project_id,
            "parent_item_id": self.parent_item_id,
            "data_name": self.data_name,
            "data_type": self.data_type,
            "data_category": self.data_category,
            "description": self.description,
            "collection_channel": self.collection_channel.value,
            "source_file": self.source_file,
            "source_url": self.source_url,
            "uploaded_by": self.uploaded_by,
            "collected_at": self.collected_at.isoformat(),
            "format": self.format.value,
            "content": self.content,
            "file_path": self.file_path,
            "quality_score": self.quality_score,
            "is_verified": self.is_verified,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "related_doc_ids": self.related_doc_ids,
            "tags": self.tags,
            "metadata": self.metadata,
            "status": self.status.value,
            "version": self.version,
        }


@dataclass
class RawData:
    """原始数据（采集后未处理的）"""
    raw_id: str
    project_id: str
    channel: CollectionChannel

    # 原始内容
    raw_content: Any                           # 原始内容（字节流、文件路径、API响应等）
    raw_format: str                            # 原始格式
    raw_size: int = 0                          # 原始大小（字节）

    # 文件信息
    file_name: Optional[str] = None
    file_extension: Optional[str] = None
    mime_type: Optional[str] = None

    # 时间戳
    received_at: datetime = field(default_factory=datetime.now)

    # 处理状态
    is_processed: bool = False
    processed_item_id: Optional[str] = None   # 处理后的ProjectDataItem ID
    processing_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_id": self.raw_id,
            "project_id": self.project_id,
            "channel": self.channel.value,
            "raw_format": self.raw_format,
            "raw_size": self.raw_size,
            "file_name": self.file_name,
            "received_at": self.received_at.isoformat(),
            "is_processed": self.is_processed,
            "processed_item_id": self.processed_item_id,
            "processing_error": self.processing_error,
        }


@dataclass
class ProcessedData:
    """处理后的数据"""
    processed_id: str
    raw_id: str                                # 关联的原始数据
    project_id: str

    # 结构化内容
    structured_content: Dict[str, Any]          # 结构化后的内容

    # 提取的关键字段
    extracted_fields: Dict[str, Any] = field(default_factory=dict)

    # AI提取的摘要
    ai_summary: Optional[str] = None            # AI生成的摘要
    key_entities: List[Dict[str, str]] = field(default_factory=list)  # 关键实体

    # 处理信息
    processed_by: str = "system"               # 处理者（system/AI/人工）
    processed_at: datetime = field(default_factory=datetime.now)

    # 质量评估
    quality_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "processed_id": self.processed_id,
            "raw_id": self.raw_id,
            "project_id": self.project_id,
            "structured_content": self.structured_content,
            "extracted_fields": self.extracted_fields,
            "ai_summary": self.ai_summary,
            "key_entities": self.key_entities,
            "processed_by": self.processed_by,
            "processed_at": self.processed_at.isoformat(),
            "quality_metrics": self.quality_metrics,
        }


@dataclass
class DataQualityScore:
    """数据质量评分"""
    item_id: str
    project_id: str

    # 各项评分 (0-1)
    completeness: float = 0.0                   # 完整性（必填字段是否齐全）
    accuracy: float = 0.0                      # 准确性（数据是否准确）
    consistency: float = 0.0                   # 一致性（与其他数据是否一致）
    timeliness: float = 0.0                    # 时效性（数据是否最新）
    validity: float = 0.0                     # 有效性（格式是否符合要求）

    # 综合评分
    overall: float = 0.0

    # 问题清单
    issues: List[Dict[str, str]] = field(default_factory=list)  # 问题列表

    # 建议
    suggestions: List[str] = field(default_factory=list)

    # 评估时间
    evaluated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        # 自动计算综合评分
        if self.overall == 0.0:
            weights = {
                "completeness": 0.25,
                "accuracy": 0.30,
                "consistency": 0.20,
                "timeliness": 0.10,
                "validity": 0.15,
            }
            self.overall = (
                self.completeness * weights["completeness"] +
                self.accuracy * weights["accuracy"] +
                self.consistency * weights["consistency"] +
                self.timeliness * weights["timeliness"] +
                self.validity * weights["validity"]
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "project_id": self.project_id,
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "consistency": self.consistency,
            "timeliness": self.timeliness,
            "validity": self.validity,
            "overall": self.overall,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class ProjectDataCollector:
    """
    项目数据采集器

    核心功能：
    1. 统一数据入口，支持多种采集渠道
    2. 自动打标签（Project_ID），确保数据隔离
    3. 数据质量检查与评分
    4. 自动分类与关联

    使用示例：
    ```python
    collector = get_data_collector()

    # 业主上传工艺流程图
    item = await collector.collect(
        project_id="PROJ001",
        data_name="工艺流程图",
        data_type="process_flow_diagram",
        channel=CollectionChannel.CLIENT_UPLOAD,
        content={"file_path": "/uploads/pfd.pdf"}
    )

    # 对接监测API
    monitoring_data = await collector.collect_from_api(
        project_id="PROJ001",
        data_type="monitoring_report",
        api_endpoint="https://monitoring-api.example.com/data"
    )

    # 查看采集进度
    progress = collector.get_collection_progress("PROJ001")
    ```
    """

    # 数据类型配置
    DATA_TYPE_CONFIG = {
        # 工艺类
        "process_flow_diagram": {"category": "工艺", "format": [DataFormat.PDF, DataFormat.IMAGE]},
        "process_description": {"category": "工艺", "format": [DataFormat.PDF, DataFormat.WORD]},
        "balance_sheet": {"category": "工艺", "format": [DataFormat.EXCEL]},  # 物料平衡表

        # 设备类
        "equipment_list": {"category": "设备", "format": [DataFormat.EXCEL]},
        "equipment_specification": {"category": "设备", "format": [DataFormat.EXCEL]},

        # 原料类
        "raw_material_list": {"category": "原料", "format": [DataFormat.EXCEL]},
        "material_sds": {"category": "原料", "format": [DataFormat.PDF]},  # 安全数据表

        # 产品类
        "product_list": {"category": "产品", "format": [DataFormat.EXCEL]},
        "product_specification": {"category": "产品", "format": [DataFormat.PDF]},

        # 排放类
        "discharge_data": {"category": "排放", "format": [DataFormat.EXCEL]},
        "monitoring_report": {"category": "排放", "format": [DataFormat.PDF]},

        # 财务类
        "investment_estimate": {"category": "财务", "format": [DataFormat.EXCEL]},
        "operating_cost": {"category": "财务", "format": [DataFormat.EXCEL]},
    }

    def __init__(self):
        self._items: Dict[str, ProjectDataItem] = {}
        self._raw_data: Dict[str, RawData] = {}
        self._processed_data: Dict[str, ProcessedData] = {}
        self._project_items_index: Dict[str, List[str]] = {}  # project_id -> [item_ids]

    async def collect(
        self,
        project_id: str,
        data_name: str,
        data_type: str,
        channel: CollectionChannel = CollectionChannel.MANUAL_ENTRY,
        content: Any = None,
        file_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_item_id: Optional[str] = None,
        **kwargs
    ) -> ProjectDataItem:
        """
        采集数据

        Args:
            project_id: 项目ID
            data_name: 数据名称
            data_type: 数据类型
            channel: 采集渠道
            content: 结构化内容
            file_path: 文件路径（如有）
            metadata: 扩展元数据
            parent_item_id: 父数据项ID

        Returns:
            ProjectDataItem: 采集的数据项
        """
        # 生成ID
        item_id = f"DI:{hashlib.md5(f'{project_id}{data_name}{datetime.now().isoformat()}'.encode()).hexdigest()[:12].upper()}"

        # 获取配置
        config = self.DATA_TYPE_CONFIG.get(data_type, {"category": "general", "format": [DataFormat.TEXT]})

        # 创建数据项
        item = ProjectDataItem(
            item_id=item_id,
            project_id=project_id,
            parent_item_id=parent_item_id,
            data_name=data_name,
            data_type=data_type,
            data_category=config.get("category", "general"),
            collection_channel=channel,
            content=content,
            file_path=file_path,
            metadata=metadata or {},
            status=CollectionStatus.RECEIVED,
        )

        # 设置format
        if file_path:
            ext = file_path.split('.')[-1].lower()
            item.format = self._get_format_from_extension(ext)

        # 存储
        self._items[item_id] = item

        # 更新索引
        if project_id not in self._project_items_index:
            self._project_items_index[project_id] = []
        self._project_items_index[project_id].append(item_id)

        # 处理数据
        await self._process_item(item)

        return item

    async def collect_from_api(
        self,
        project_id: str,
        data_type: str,
        api_endpoint: str,
        api_params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> List[ProjectDataItem]:
        """
        从API接口采集数据

        用于对接第三方检测机构、企业在线监测平台等。
        """
        # 模拟API调用
        # 实际实现中，这里会调用实际的API

        items = []

        # 模拟返回数据
        if "monitoring" in data_type.lower():
            # 监测数据
            item = await self.collect(
                project_id=project_id,
                data_name="在线监测数据",
                data_type=data_type,
                channel=CollectionChannel.API_INTEGRATION,
                content={
                    "monitoring_date": datetime.now().isoformat(),
                    "parameters": {
                        "SO2": 25.5,
                        "NOx": 45.2,
                        "烟尘": 8.3,
                        "COD": 12.0,
                    }
                },
                metadata={"api_endpoint": api_endpoint}
            )
            items.append(item)

        return items

    async def collect_from_model_output(
        self,
        project_id: str,
        model_name: str,
        model_version: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        calculation_type: str,
        **kwargs
    ) -> ProjectDataItem:
        """
        采集模型计算输出

        用于将排放核算、风险评估等模型计算结果存入项目数据。
        """
        item = await self.collect(
            project_id=project_id,
            data_name=f"{calculation_type}计算结果",
            data_type=f"calculation_{calculation_type}",
            channel=CollectionChannel.MODEL_OUTPUT,
            content={
                "model_name": model_name,
                "model_version": model_version,
                "input_parameters": input_data,
                "output_results": output_data,
                "calculation_timestamp": datetime.now().isoformat(),
            },
            metadata={
                "model_name": model_name,
                "model_version": model_version,
                "calculation_type": calculation_type,
            }
        )

        return item

    async def _process_item(self, item: ProjectDataItem) -> None:
        """处理数据项"""
        item.status = CollectionStatus.PROCESSING

        # 1. 数据质量评估
        quality = await self._evaluate_quality(item)
        item.quality_score = quality.overall

        # 2. 自动关联（如果有父项）
        if item.parent_item_id and item.parent_item_id in self._items:
            parent = self._items[item.parent_item_id]
            if item.item_id not in parent.metadata.get("children", []):
                parent.metadata.setdefault("children", []).append(item.item_id)

        item.status = CollectionStatus.PROCESSED

    async def _evaluate_quality(self, item: ProjectDataItem) -> DataQualityScore:
        """评估数据质量"""
        score = DataQualityScore(
            item_id=item.item_id,
            project_id=item.project_id
        )

        # 完整性检查
        required_fields = ["data_name", "data_type", "project_id"]
        missing = [f for f in required_fields if not getattr(item, f, None)]
        score.completeness = 1.0 - (len(missing) / len(required_fields))

        # 准确性检查（简化版，实际应更复杂）
        score.accuracy = 0.9 if item.content else 0.5

        # 一致性检查
        score.consistency = 0.85

        # 时效性检查（采集时间距离现在不超过30天）
        age = (datetime.now() - item.collected_at).days
        score.timeliness = 1.0 if age <= 30 else max(0.5, 1.0 - age / 365)

        # 有效性检查
        score.validity = 0.9 if item.format else 0.5

        # 生成问题和建议
        if score.completeness < 1.0:
            score.issues.append({
                "type": "completeness",
                "description": f"缺少必填字段: {', '.join(missing)}",
                "severity": "high"
            })
            score.suggestions.append("请补充完整必填信息")

        if score.overall < 0.7:
            score.issues.append({
                "type": "quality",
                "description": f"综合质量评分较低: {score.overall:.2f}",
                "severity": "medium"
            })
            score.suggestions.append("建议人工复核此数据项")

        return score

    def _get_format_from_extension(self, ext: str) -> DataFormat:
        """根据扩展名获取格式"""
        mapping = {
            "pdf": DataFormat.PDF,
            "doc": DataFormat.WORD, "docx": DataFormat.WORD,
            "xls": DataFormat.EXCEL, "xlsx": DataFormat.EXCEL,
            "jpg": DataFormat.IMAGE, "jpeg": DataFormat.IMAGE,
            "png": DataFormat.IMAGE, "gif": DataFormat.IMAGE,
            "mp4": DataFormat.VIDEO, "avi": DataFormat.VIDEO,
            "mp3": DataFormat.AUDIO, "wav": DataFormat.AUDIO,
            "txt": DataFormat.TEXT, "json": DataFormat.JSON,
            "xml": DataFormat.XML,
        }
        return mapping.get(ext.lower(), DataFormat.TEXT)

    def get_collection_progress(self, project_id: str) -> Dict[str, Any]:
        """获取项目数据采集进度"""
        if project_id not in self._project_items_index:
            return {
                "project_id": project_id,
                "total_items": 0,
                "by_category": {},
                "by_channel": {},
                "quality_distribution": {},
            }

        item_ids = self._project_items_index[project_id]
        items = [self._items[iid] for iid in item_ids]

        # 按类别统计
        by_category: Dict[str, int] = {}
        for item in items:
            by_category[item.data_category] = by_category.get(item.data_category, 0) + 1

        # 按渠道统计
        by_channel: Dict[str, int] = {}
        for item in items:
            ch = item.collection_channel.value
            by_channel[ch] = by_channel.get(ch, 0) + 1

        # 质量分布
        quality_distribution = {"high": 0, "medium": 0, "low": 0}
        for item in items:
            if item.quality_score >= 0.8:
                quality_distribution["high"] += 1
            elif item.quality_score >= 0.6:
                quality_distribution["medium"] += 1
            else:
                quality_distribution["low"] += 1

        return {
            "project_id": project_id,
            "total_items": len(items),
            "by_category": by_category,
            "by_channel": by_channel,
            "quality_distribution": quality_distribution,
            "average_quality": sum(i.quality_score for i in items) / len(items) if items else 0,
        }

    def get_project_data(
        self,
        project_id: str,
        category: Optional[str] = None,
        data_type: Optional[str] = None,
        include_content: bool = True
    ) -> List[Dict[str, Any]]:
        """获取项目的所有数据"""
        if project_id not in self._project_items_index:
            return []

        item_ids = self._project_items_index[project_id]
        result = []

        for iid in item_ids:
            item = self._items[iid]
            if category and item.data_category != category:
                continue
            if data_type and item.data_type != data_type:
                continue

            item_dict = item.to_dict()
            if not include_content:
                item_dict.pop("content", None)
            result.append(item_dict)

        return result


class DataQualityEngine:
    """
    数据质量引擎

    核心功能：
    1. 多维度质量评估
    2. 问题检测与建议
    3. 自动修正（可能的场景）
    4. 质量趋势分析
    """

    def __init__(self):
        self._quality_history: Dict[str, List[DataQualityScore]] = {}

    async def evaluate(
        self,
        item: ProjectDataItem,
        existing_items: Optional[List[ProjectDataItem]] = None
    ) -> DataQualityScore:
        """评估数据质量"""
        score = DataQualityScore(
            item_id=item.item_id,
            project_id=item.project_id
        )

        # 完整性
        score.completeness = self._evaluate_completeness(item)

        # 准确性（与现有数据比对）
        score.accuracy = await self._evaluate_accuracy(item, existing_items) if existing_items else 0.9

        # 一致性
        score.consistency = self._evaluate_consistency(item, existing_items) if existing_items else 0.85

        # 时效性
        score.timeliness = self._evaluate_timeliness(item)

        # 有效性
        score.validity = self._evaluate_validity(item)

        # 生成问题和建议
        self._generate_feedback(score, item)

        # 记录历史
        if item.project_id not in self._quality_history:
            self._quality_history[item.project_id] = []
        self._quality_history[item.project_id].append(score)

        return score

    def _evaluate_completeness(self, item: ProjectDataItem) -> float:
        """评估完整性"""
        base_score = 0.4

        # 有数据名称 +0.1
        if item.data_name:
            base_score += 0.1

        # 有数据类型 +0.1
        if item.data_type:
            base_score += 0.1

        # 有内容 +0.2
        if item.content:
            base_score += 0.2

        # 有描述 +0.1
        if item.description:
            base_score += 0.1

        return min(1.0, base_score)

    async def _evaluate_accuracy(
        self,
        item: ProjectDataItem,
        existing_items: List[ProjectDataItem]
    ) -> float:
        """评估准确性"""
        # 简化：检查与同类数据的重合度
        similar = [i for i in existing_items if i.data_type == item.data_type and i.item_id != item.item_id]
        if not similar:
            return 0.9  # 无参照物，假设准确

        # 实际应比对具体数值，这里简化处理
        return 0.9

    def _evaluate_consistency(
        self,
        item: ProjectDataItem,
        existing_items: Optional[List[ProjectDataItem]]
    ) -> float:
        """评估一致性"""
        if not existing_items:
            return 0.85

        # 检查项目ID一致性
        project_items = [i for i in existing_items if i.project_id == item.project_id]
        return 0.95 if project_items else 0.7

    def _evaluate_timeliness(self, item: ProjectDataItem) -> float:
        """评估时效性"""
        age_days = (datetime.now() - item.collected_at).days
        if age_days <= 7:
            return 1.0
        elif age_days <= 30:
            return 0.9
        elif age_days <= 90:
            return 0.7
        elif age_days <= 180:
            return 0.5
        else:
            return 0.3

    def _evaluate_validity(self, item: ProjectDataItem) -> float:
        """评估有效性"""
        base = 0.5

        # 格式正确 +0.2
        if item.format:
            base += 0.2

        # 状态正常 +0.15
        if item.status not in [CollectionStatus.FAILED, CollectionStatus.REJECTED]:
            base += 0.15

        # 无错误标记 +0.15
        if not item.metadata.get("has_errors"):
            base += 0.15

        return min(1.0, base)

    def _generate_feedback(self, score: DataQualityScore, item: ProjectDataItem) -> None:
        """生成反馈"""
        if score.completeness < 0.8:
            score.issues.append({
                "type": "completeness",
                "field": "missing_fields",
                "description": "数据项信息不完整",
                "severity": "high"
            })
            score.suggestions.append("请补充完整数据项的基本信息")

        if score.accuracy < 0.7:
            score.issues.append({
                "type": "accuracy",
                "description": "数据准确性存疑",
                "severity": "high"
            })
            score.suggestions.append("请核实数据是否正确，可参考类似项目的数据")

        if score.timeliness < 0.6:
            score.issues.append({
                "type": "timeliness",
                "description": "数据可能已过时",
                "severity": "medium"
            })
            score.suggestions.append("请确认数据是否为最新版本")

        if score.validity < 0.7:
            score.issues.append({
                "type": "validity",
                "description": "数据格式或状态异常",
                "severity": "medium"
            })
            score.suggestions.append("请检查数据格式是否符合要求")

    def get_quality_trend(self, project_id: str) -> Dict[str, Any]:
        """获取质量趋势"""
        if project_id not in self._quality_history:
            return {"trend": "no_data"}

        history = self._quality_history[project_id]
        if len(history) < 2:
            return {"trend": "insufficient_data", "data_points": len(history)}

        # 计算趋势
        recent = history[-5:]  # 最近5个
        scores = [h.overall for h in recent]

        if all(s >= scores[0] for s in scores):
            trend = "improving"
        elif all(s <= scores[0] for s in scores):
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "data_points": len(history),
            "recent_average": sum(scores) / len(scores),
            "latest_score": scores[-1],
        }


# 全局单例
_data_collector: Optional[ProjectDataCollector] = None
_quality_engine: Optional[DataQualityEngine] = None


def get_data_collector() -> ProjectDataCollector:
    """获取数据采集器单例"""
    global _data_collector
    if _data_collector is None:
        _data_collector = ProjectDataCollector()
    return _data_collector


def get_quality_engine() -> DataQualityEngine:
    """获取数据质量引擎单例"""
    global _quality_engine
    if _quality_engine is None:
        _quality_engine = DataQualityEngine()
    return _quality_engine