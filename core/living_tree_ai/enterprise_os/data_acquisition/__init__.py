"""
数据获取模块 (Data Acquisition)

构建"项目数据底座"，实现：
1. 企业背景数据 - 从政府系统自动抓取，填充项目档案
2. 项目过程数据 - 多渠道采集（业主提供/现场采集/监测数据/模型输出）

核心价值：数据不落地，减少顾问重复录入，降低人为差错。
"""

from .enterprise_data_fetcher import (
    # 数据源枚举
    DataSourceType,
    FetchStatus,
    GovernmentSystem,
    # 数据模型
    EnterpriseBasicInfo,
    EnvironmentalRecord,
    SafetyLicense,
    CreditRiskInfo,
    GovernmentData,
    # 企业数据获取器
    EnterpriseDataFetcher,
    get_enterprise_fetcher,
)

from .project_data_collector import (
    # 采集渠道枚举
    CollectionChannel,
    DataFormat,
    CollectionStatus,
    # 数据模型
    ProjectDataItem,
    RawData,
    ProcessedData,
    DataQualityScore,
    # 采集器
    ProjectDataCollector,
    DataQualityEngine,
    get_data_collector,
    get_quality_engine,
)

__all__ = [
    # 企业数据获取
    "DataSourceType",
    "FetchStatus",
    "GovernmentSystem",
    "EnterpriseBasicInfo",
    "EnvironmentalRecord",
    "SafetyLicense",
    "CreditRiskInfo",
    "GovernmentData",
    "EnterpriseDataFetcher",
    "get_enterprise_fetcher",
    # 项目数据采集
    "CollectionChannel",
    "DataFormat",
    "CollectionStatus",
    "ProjectDataItem",
    "RawData",
    "ProcessedData",
    "DataQualityScore",
    "ProjectDataCollector",
    "DataQualityEngine",
    "get_data_collector",
    "get_quality_engine",
]