"""
环评工艺知识库 (EIA Process Knowledge Base)
=========================================

作者：Hermes Desktop AI Team
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import os

logger = logging.getLogger(__name__)


@dataclass
class ProcessOntology:
    """工艺本体"""
    process_id: str
    name: str
    category: str
    industry: str
    standard_steps: List[str]
    parameters: Dict[str, Any]
    equipment: List[str]
    pollutants: Dict[str, float]


@dataclass
class EmissionStandard:
    """排放标准"""
    pollutant: str
    standard_code: str
    standard_name: str
    limit: float
    unit: str


class EIAProcessKnowledgeBase:
    """环评工艺知识库"""

    BUILTIN_PROCESSES = {
        "metal_spray": ProcessOntology(
            process_id="metal_spray",
            name="金属喷砂喷漆",
            category="表面处理",
            industry="通用机械",
            standard_steps=["上料", "喷砂", "清洁", "干燥", "喷漆", "流平", "固化", "冷却", "检验", "包装"],
            parameters={"喷砂压力": "0.5MPa", "喷漆厚度": "30μm", "固化温度": "180℃"},
            equipment=["喷砂机", "喷漆房", "固化炉"],
            pollutants={"颗粒物": 0.8, "VOCs": 2.5, "漆渣": 0.1},
        ),
        "welding": ProcessOntology(
            process_id="welding",
            name="焊接装配",
            category="加工",
            industry="通用机械",
            standard_steps=["上料", "下料", "焊接", "打磨", "检验", "包装"],
            parameters={"焊接电流": "150A", "焊接电压": "25V"},
            equipment=["焊机", "打磨机", "通风设备"],
            pollutants={"烟尘": 0.5, "NOx": 0.1},
        ),
    }

    BUILTIN_STANDARDS = {
        "颗粒物": EmissionStandard("颗粒物", "GB 16297-1996", "大气污染物综合排放标准", 20, "mg/m³"),
        "VOCs": EmissionStandard("VOCs", "GB 16297-1996", "大气污染物综合排放标准", 60, "mg/m³"),
        "COD": EmissionStandard("COD", "GB 8978-1996", "污水综合排放标准", 100, "mg/L"),
    }

    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir
        self.processes = dict(self.BUILTIN_PROCESSES)
        self.standards = dict(self.BUILTIN_STANDARDS)
        self.user_prefs: Dict[str, Dict] = {}
        logger.info("环评工艺知识库初始化完成")

    def get_process(self, process_id: str) -> Optional[ProcessOntology]:
        return self.processes.get(process_id)

    def search_processes(self, query: str) -> List[ProcessOntology]:
        results = []
        for proc in self.processes.values():
            if query in proc.name or query in proc.category:
                results.append(proc)
        return results

    def get_standard(self, pollutant: str) -> Optional[EmissionStandard]:
        return self.standards.get(pollutant)

    def get_pollutant_coefficients(self, process_name: str) -> Dict[str, float]:
        for proc in self.processes.values():
            if process_name in proc.name:
                return proc.pollutants
        return {}

    def learn_preference(self, user_id: str, pref_data: Dict):
        self.user_prefs[user_id] = pref_data
        logger.info(f"学习用户偏好: {user_id}")

    def get_preference(self, user_id: str) -> Optional[Dict]:
        return self.user_prefs.get(user_id)
