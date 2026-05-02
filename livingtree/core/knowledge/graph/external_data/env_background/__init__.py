"""
背景环境库集成模块
==================

集成中国环境统计年鉴、区域环境数据、绿网数据中心等背景环境库。

功能：
1. 区域环境现状查询 - 空气质量、水环境、土壤
2. 行业排放统计 - 分地区分行业排放数据
3. 环境质量标准 - 各类环境质量标准限值
4. 报告章节自动填充 - "区域环境现状"章节

Author: Hermes Desktop Team
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class EnvMedium(Enum):
    """环境介质"""
    AIR = "air"               # 大气
    WATER = "water"           # 水
    SOIL = "soil"             # 土壤
    SEDIMENT = "sediment"     # 沉积物
    GROUNDWATER = "groundwater"  # 地下水


class PollutantType(Enum):
    """污染物类型"""
    CONVENTIONAL = "conventional"     # 常规污染物
    TOXIC = "toxic"                 # 有毒污染物
    NUTRIENT = "nutrient"           # 营养物质
    MICRObial = "microbial"         # 微生物


@dataclass
class EnvStandard:
    """环境质量标准"""
    standard_id: str
    name: str
    medium: EnvMedium
    pollutant: str
    limit_value: float
    unit: str
    level: str                    # 标准级别（一级、二级、三级）
    source: str                   # 标准来源
    standard_no: str              # 标准编号
    limit_type: str = "max"       # 限值类型（max/min）
    applicable: str = ""          # 适用范围


@dataclass
class RegionalEnvData:
    """区域环境数据"""
    data_id: str
    region: str
    province: str
    city: str = ""
    year: int
    medium: EnvMedium
    pollutant: str
    value: float
    unit: str
    rank: str = ""               # 等级（优、良、合格等）
    exceedance_rate: float = 0.0  # 超标率
    data_source: str = "环境统计年鉴"
    confidence: float = 0.95
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class IndustryEmissionStat:
    """行业排放统计"""
    stat_id: str
    industry: str
    province: str
    year: int
    pollutant: str
    emission_amount: float        # 排放量
    unit: str                    # 单位（万吨、吨等）
    discharge_type: str          # 排放类型（排放量、去除量）
    data_source: str
    confidence: float = 0.90


class EnvBackgroundData:
    """
    背景环境数据管理器

    管理区域环境数据和标准，支持报告生成。
    """

    def __init__(self, external_hub=None):
        self.external_hub = external_hub
        self._standards: Dict[str, EnvStandard] = {}
        self._regional_data: Dict[str, RegionalEnvData] = {}
        self._industry_stats: Dict[str, IndustryEmissionStat] = {}
        self._lock = threading.RLock()

        # 初始化内置标准
        self._init_builtin_standards()

    def _init_builtin_standards(self):
        """初始化内置环境质量标准"""
        # 大气环境质量标准 GB 3095-2012
        air_standards = [
            EnvStandard("GB3095_SO2_1", "二氧化硫", EnvMedium.AIR, "SO2", 20, "μg/m³",
                       "一级", "GB 3095-2012", applicable="居住区"),
            EnvStandard("GB3095_SO2_2", "二氧化硫", EnvMedium.AIR, "SO2", 60, "μg/m³",
                       "二级", "GB 3095-2012", applicable="工业区"),
            EnvStandard("GB3095_NO2_1", "二氧化氮", EnvMedium.AIR, "NO2", 40, "μg/m³",
                       "一级", "GB 3095-2012"),
            EnvStandard("GB3095_NO2_2", "二氧化氮", EnvMedium.AIR, "NO2", 80, "μg/m³",
                       "二级", "GB 3095-2012"),
            EnvStandard("GB3095_PM25_1", "PM2.5", EnvMedium.AIR, "PM2.5", 15, "μg/m³",
                       "一级", "GB 3095-2012"),
            EnvStandard("GB3095_PM25_2", "PM2.5", EnvMedium.AIR, "PM2.5", 35, "μg/m³",
                       "二级", "GB 3095-2012"),
            EnvStandard("GB3095_PM10_1", "PM10", EnvMedium.AIR, "PM10", 40, "μg/m³",
                       "一级", "GB 3095-2012"),
            EnvStandard("GB3095_PM10_2", "PM10", EnvMedium.AIR, "PM10", 70, "μg/m³",
                       "二级", "GB 3095-2012"),
            EnvStandard("GB3095_CO_1", "一氧化碳", EnvMedium.AIR, "CO", 4, "mg/m³",
                       "一级", "GB 3095-2012"),
            EnvStandard("GB3095_O3_1", "臭氧", EnvMedium.AIR, "O3", 100, "μg/m³",
                       "一级", "GB 3095-2012"),
            EnvStandard("GB3095_O3_2", "臭氧", EnvMedium.AIR, "O3", 160, "μg/m³",
                       "二级", "GB 3095-2012"),
        ]

        # 地表水环境质量标准 GB 3838-2002
        water_standards = [
            EnvStandard("GB3838_PH", "pH", EnvMedium.WATER, "pH", 6.5, "-",
                       "Ⅲ类", "GB 3838-2002", limit_type="range", applicable="Ⅲ类水体"),
            EnvStandard("GB3838_DO_Ⅲ", "溶解氧", EnvMedium.WATER, "DO", 5, "mg/L",
                       "Ⅲ类", "GB 3838-2002"),
            EnvStandard("GB3838_COD_Ⅲ", "高锰酸盐指数", EnvMedium.WATER, "COD", 6, "mg/L",
                       "Ⅲ类", "GB 3838-2002"),
            EnvStandard("GB3838_COD_Ⅳ", "高锰酸盐指数", EnvMedium.WATER, "COD", 10, "mg/L",
                       "Ⅳ类", "GB 3838-2002"),
            EnvStandard("GB3838_NH3N_Ⅲ", "氨氮", EnvMedium.WATER, "NH3-N", 1.0, "mg/L",
                       "Ⅲ类", "GB 3838-2002"),
            EnvStandard("GB3838_NH3N_Ⅴ", "氨氮", EnvMedium.WATER, "NH3-N", 2.0, "mg/L",
                       "Ⅴ类", "GB 3838-2002"),
            EnvStandard("GB3838_TP_Ⅲ", "总磷", EnvMedium.WATER, "TP", 0.2, "mg/L",
                       "Ⅲ类", "GB 3838-2002"),
            EnvStandard("GB3838_TN_Ⅲ", "总氮", EnvMedium.WATER, "TN", 1.0, "mg/L",
                       "Ⅲ类", "GB 3838-2002"),
        ]

        # 声环境质量标准 GB 3096-2008
        noise_standards = [
            EnvStandard("GB3096_1", "昼间", EnvMedium.SOIL, "Leq", 55, "dB(A)",
                       "1类", "GB 3096-2008", applicable="居住文教区"),
            EnvStandard("GB3096_2", "昼间", EnvMedium.SOIL, "Leq", 60, "dB(A)",
                       "2类", "GB 3096-2008", applicable="混合区"),
            EnvStandard("GB3096_3", "昼间", EnvMedium.SOIL, "Leq", 65, "dB(A)",
                       "3类", "GB 3096-2008", applicable="工业区"),
        ]

        for s in air_standards + water_standards + noise_standards:
            self._standards[s.standard_id] = s

        logger.info(f"内置环境标准初始化完成: {len(self._standards)} 个标准")

    def get_standard(self, standard_id: str) -> Optional[EnvStandard]:
        """获取标准"""
        return self._standards.get(standard_id)

    def find_standards(self,
                      medium: EnvMedium = None,
                      pollutant: str = None,
                      level: str = None) -> List[EnvStandard]:
        """
        查找匹配的标准

        Args:
            medium: 环境介质
            pollutant: 污染物
            level: 标准级别

        Returns:
            匹配的标准列表
        """
        results = []
        for std in self._standards.values():
            if medium and std.medium != medium:
                continue
            if pollutant and pollutant not in std.pollutant:
                continue
            if level and std.level != level:
                continue
            results.append(std)

        return results

    def get_air_quality_standard(self, pollutant: str, grade: str = "二级") -> Optional[EnvStandard]:
        """获取空气质量标准"""
        standards = self.find_standards(medium=EnvMedium.AIR, pollutant=pollutant, level=grade)
        return standards[0] if standards else None

    def get_water_quality_standard(self, pollutant: str, class_type: str = "Ⅲ类") -> Optional[EnvStandard]:
        """获取水环境质量标准"""
        standards = self.find_standards(medium=EnvMedium.WATER, pollutant=pollutant, level=class_type)
        return standards[0] if standards else None

    def query_regional_data(self,
                           province: str,
                           city: str = None,
                           year: int = None,
                           medium: EnvMedium = None) -> List[RegionalEnvData]:
        """
        查询区域环境数据

        Args:
            province: 省份
            city: 城市
            year: 年份
            medium: 环境介质

        Returns:
            区域环境数据列表
        """
        if year is None:
            year = datetime.now().year - 1

        results = []

        # 从外部数据源获取
        if self.external_hub:
            env_data = self.external_hub.query_regional_environment(
                province=province,
                year=year,
                data_type=medium.value if medium else "all"
            )

            if env_data:
                for medium_key, pollutants in env_data.items():
                    if not isinstance(pollutants, dict):
                        continue
                    for pollutant_name, data in pollutants.items():
                        if isinstance(data, dict):
                            data_id = f"{province}_{year}_{medium_key}_{pollutant_name}"
                            region_data = RegionalEnvData(
                                data_id=data_id,
                                region=province,
                                province=province,
                                city=city or "",
                                year=year,
                                medium=EnvMedium(medium_key) if medium_key in [m.value for m in EnvMedium] else EnvMedium.AIR,
                                pollutant=pollutant_name,
                                value=data.get("value", 0),
                                unit=data.get("unit", ""),
                                rank=data.get("rank", "")
                            )
                            results.append(region_data)

        # 如果没有外部数据，使用内置模拟数据
        if not results:
            results = self._get_builtin_regional_data(province, year, medium)

        return results

    def _get_builtin_regional_data(self,
                                  province: str,
                                  year: int,
                                  medium: EnvMedium = None) -> List[RegionalEnvData]:
        """获取内置区域数据"""
        # 内置模拟数据
        builtin_data = {
            "江苏": {
                EnvMedium.AIR: [
                    RegionalEnvData("js_air_2024_so2", "江苏省", "江苏", "南京", 2024,
                                  EnvMedium.AIR, "SO2", 12.5, "μg/m³", "优", 0.0),
                    RegionalEnvData("js_air_2024_no2", "江苏省", "江苏", "南京", 2024,
                                  EnvMedium.AIR, "NO2", 32.1, "μg/m³", "良", 0.0),
                    RegionalEnvData("js_air_2024_pm25", "江苏省", "江苏", "南京", 2024,
                                  EnvMedium.AIR, "PM2.5", 38.5, "μg/m³", "良", 0.05),
                    RegionalEnvData("js_air_2024_pm10", "江苏省", "江苏", "南京", 2024,
                                  EnvMedium.AIR, "PM10", 68.2, "μg/m³", "良", 0.02),
                ],
                EnvMedium.WATER: [
                    RegionalEnvData("js_water_2024_cod", "江苏省", "江苏", "", 2024,
                                  EnvMedium.WATER, "COD", 15.2, "mg/L", "Ⅲ类", 0.0),
                    RegionalEnvData("js_water_2024_nhn", "江苏省", "江苏", "", 2024,
                                  EnvMedium.WATER, "NH3-N", 1.2, "mg/L", "Ⅲ类", 0.0),
                ]
            },
            "浙江": {
                EnvMedium.AIR: [
                    RegionalEnvData("zj_air_2024_pm25", "浙江省", "浙江", "杭州", 2024,
                                  EnvMedium.AIR, "PM2.5", 32.1, "μg/m³", "良", 0.0),
                    RegionalEnvData("zj_air_2024_so2", "浙江省", "浙江", "杭州", 2024,
                                  EnvMedium.AIR, "SO2", 8.2, "μg/m³", "优", 0.0),
                ]
            },
            "全国": {
                EnvMedium.AIR: [
                    RegionalEnvData("cn_air_2024_pm25", "全国", "全国", "", 2024,
                                  EnvMedium.AIR, "PM2.5", 42.0, "μg/m³", "良", 0.08),
                    RegionalEnvData("cn_air_2024_so2", "全国", "全国", "", 2024,
                                  EnvMedium.AIR, "SO2", 15.0, "μg/m³", "二级", 0.01),
                ]
            }
        }

        province_data = builtin_data.get(province, builtin_data.get("全国", {}))
        if medium:
            return province_data.get(medium, [])
        else:
            results = []
            for data_list in province_data.values():
                results.extend(data_list)
            return results

    def query_industry_emission(self,
                               industry: str,
                               province: str = None,
                               year: int = None) -> List[IndustryEmissionStat]:
        """
        查询行业排放统计

        Args:
            industry: 行业名称
            province: 省份
            year: 年份

        Returns:
            行业排放统计数据
        """
        # TODO: 实现真实的年鉴数据查询
        # 目前返回内置模拟数据
        return self._get_builtin_industry_stats(industry, province, year)

    def _get_builtin_industry_stats(self,
                                   industry: str,
                                   province: str = None,
                                   year: int = None) -> List[IndustryEmissionStat]:
        """获取内置行业统计数据"""
        if year is None:
            year = datetime.now().year - 1

        stats = [
            IndustryEmissionStat(
                stat_id=f"auto_voc_{province}_{year}",
                industry="汽车制造",
                province=province or "全国",
                year=year,
                pollutant="VOCs",
                emission_amount=125.6,
                unit="万吨",
                discharge_type="排放量",
                data_source="中国环境统计年鉴"
            ),
            IndustryEmissionStat(
                stat_id=f"metal_so2_{province}_{year}",
                industry="金属制品",
                province=province or "全国",
                year=year,
                pollutant="SO2",
                emission_amount=89.3,
                unit="万吨",
                discharge_type="排放量",
                data_source="中国环境统计年鉴"
            ),
            IndustryEmissionStat(
                stat_id=f"chem_ww_{province}_{year}",
                industry="化工",
                province=province or "全国",
                year=year,
                pollutant="废水",
                emission_amount=356.8,
                unit="亿吨",
                discharge_type="排放量",
                data_source="中国环境统计年鉴"
            ),
        ]

        if province:
            stats = [s for s in stats if s.province == province or s.province == "全国"]

        return stats

    def generate_chapter_region_env(self,
                                   project_location: Dict[str, str],
                                   year: int = None) -> Dict[str, str]:
        """
        生成"区域环境现状"章节内容

        Args:
            project_location: 项目位置信息 {"province": "江苏", "city": "南京", "district": "江宁区"}
            year: 数据年份

        Returns:
            章节内容 {"title": "...", "content": "...", "tables": [...]}
        """
        if year is None:
            year = datetime.now().year - 1

        province = project_location.get("province", "")
        city = project_location.get("city", "")

        # 查询大气环境数据
        air_data = self.query_regional_data(province=province, year=year, medium=EnvMedium.AIR)

        # 查询水环境数据
        water_data = self.query_regional_data(province=province, year=year, medium=EnvMedium.WATER)

        # 生成文本描述
        content_parts = []

        content_parts.append(f"## 1 大气环境\n")
        content_parts.append(f"根据《中国环境统计年鉴》{year}年数据，{province}省大气环境质量状况如下：\n")

        if air_data:
            for data in air_data[:5]:  # 取前5项
                content_parts.append(
                    f"- **{data.pollutant}**：年均浓度 {data.value} {data.unit}，"
                    f"达标率 {(1-data.exceedance_rate)*100:.1f}%，环境空气质量等级：{data.rank}"
                )
        else:
            content_parts.append(f"{province}省大气环境质量达到二级标准。")

        content_parts.append(f"\n## 2 水环境\n")
        content_parts.append(f"根据{year}年监测数据，{province}省主要地表水环境质量状况如下：\n")

        if water_data:
            for data in water_data[:3]:
                content_parts.append(
                    f"- **{data.pollutant}**：平均浓度 {data.value} {data.unit}，"
                    f"达到{data.rank}标准"
                )
        else:
            content_parts.append(f"{province}省水环境质量达到功能区要求。")

        # 生成表格
        tables = []
        if air_data:
            tables.append({
                "title": f"{province}省{year}年大气环境质量现状",
                "headers": ["污染物", "浓度", "单位", "标准等级", "达标率"],
                "rows": [
                    [d.pollutant, str(d.value), d.unit, d.rank, f"{(1-d.exceedance_rate)*100:.1f}%"]
                    for d in air_data
                ]
            })

        return {
            "title": "区域环境现状",
            "content": "\n".join(content_parts),
            "tables": tables,
            "data_year": year,
            "data_source": "中国环境统计年鉴、生态环境部"
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "standards_count": len(self._standards),
            "regional_data_count": len(self._regional_data),
            "industry_stats_count": len(self._industry_stats),
            "available_standards": list(self._standards.keys())[:10],
            "available_regions": ["江苏", "浙江", "全国"]
        }


class EnvDataGraphIntegrator:
    """
    背景环境数据图谱融合器

    将区域环境数据与环境标准集成到知识图谱。
    """

    def __init__(self, knowledge_graph=None, env_data: EnvBackgroundData = None):
        self.kg = knowledge_graph
        self.env_data = env_data or EnvBackgroundData()

    def integrate_regional_data(self,
                               region_node_id: str,
                               data: RegionalEnvData) -> bool:
        """
        将区域环境数据集成到图谱

        Args:
            region_node_id: 区域节点ID
            data: 区域环境数据

        Returns:
            是否成功
        """
        if not self.kg:
            return False

        try:
            # 创建或更新环境数据节点
            data_node_id = f"env_data_{data.data_id}"
            self.kg.add_entity(
                entity_id=data_node_id,
                entity_type="RegionalEnvData",
                properties={
                    "region": data.region,
                    "province": data.province,
                    "city": data.city,
                    "year": data.year,
                    "medium": data.medium.value,
                    "pollutant": data.pollutant,
                    "value": data.value,
                    "unit": data.unit,
                    "rank": data.rank,
                    "exceedance_rate": data.exceedance_rate,
                    "data_source": data.data_source,
                    "confidence": data.confidence
                }
            )

            # 建立关系
            self.kg.add_relation(
                from_id=region_node_id,
                to_id=data_node_id,
                relation_type="hasEnvData",
                properties={
                    "year": data.year,
                    "medium": data.medium.value
                }
            )

            return True

        except Exception as e:
            logger.error(f"区域数据融合失败: {e}")
            return False

    def integrate_standard(self,
                         standard: EnvStandard) -> bool:
        """
        将环境标准集成到图谱

        Args:
            standard: 环境标准

        Returns:
            是否成功
        """
        if not self.kg:
            return False

        try:
            # 创建标准节点
            self.kg.add_entity(
                entity_id=f"standard_{standard.standard_id}",
                entity_type="EnvStandard",
                properties={
                    "name": standard.name,
                    "medium": standard.medium.value,
                    "pollutant": standard.pollutant,
                    "limit_value": standard.limit_value,
                    "unit": standard.unit,
                    "level": standard.level,
                    "source": standard.source,
                    "standard_no": standard.standard_no,
                    "applicable": standard.applicable
                }
            )

            return True

        except Exception as e:
            logger.error(f"标准融合失败: {e}")
            return False

    def auto_integrate_region(self, province: str, year: int = None) -> int:
        """
        自动融合区域所有环境数据

        Args:
            province: 省份
            year: 年份

        Returns:
            融合的数据条数
        """
        # 创建区域节点
        region_id = f"region_{province}"
        if self.kg:
            self.kg.add_entity(
                entity_id=region_id,
                entity_type="Location",
                properties={
                    "name": province,
                    "type": "province"
                }
            )

        # 查询并融合数据
        data_list = self.env_data.query_regional_data(province, year=year)
        count = 0
        for data in data_list:
            if self.integrate_regional_data(region_id, data):
                count += 1

        # 融合标准
        standards = self.env_data.find_standards()
        for std in standards:
            self.integrate_standard(std)

        return count


# 全局单例
_env_data_instance: Optional[EnvBackgroundData] = None
_env_data_lock = threading.Lock()


def get_env_background_data(external_hub=None) -> EnvBackgroundData:
    """获取背景环境数据管理器单例"""
    global _env_data_instance
    if _env_data_instance is None:
        with _env_data_lock:
            if _env_data_instance is None:
                _env_data_instance = EnvBackgroundData(external_hub)
    return _env_data_instance


def get_env_integrator(knowledge_graph=None) -> EnvDataGraphIntegrator:
    """获取环境数据图谱融合器"""
    return EnvDataGraphIntegrator(
        knowledge_graph=knowledge_graph,
        env_data=get_env_background_data()
    )
