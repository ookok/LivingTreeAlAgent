"""
工艺扩展智能体 (Process Expander Agent)
=======================================

职责：
1. 从简写推导完整工艺链
2. 补充隐藏工序
3. 关联工艺参数
4. 智能设备推荐

作者：Hermes Desktop AI Team
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from business.eia_process import ProcessType, ProcessStep

logger = logging.getLogger(__name__)


class ProcessExpander:
    """
    工艺扩展智能体 - 从简写推导完整工艺链
    """

    # 标准工艺链模板
    STANDARD_CHAINS = {
        "metal_coating": {
            "name": "金属表面涂装",
            "steps": ["上料", "除油", "水洗", "除锈", "水洗", "表调", "磷化", "水洗", "纯水洗", "干燥",
                     "喷砂", "清洁", "遮蔽", "喷漆", "流平", "固化", "冷却", "检验", "包装", "入库"]
        },
        "simple_coating": {
            "name": "简化涂装",
            "steps": ["上料", "打磨", "清洁", "干燥", "喷漆", "流平", "固化", "冷却", "检验", "包装"]
        },
        "sandblast_coating": {
            "name": "喷砂+喷漆",
            "steps": ["上料", "喷砂", "清洁", "干燥", "喷漆", "流平", "固化", "冷却", "检验", "包装"]
        },
        "machining": {
            "name": "机械加工",
            "steps": ["上料", "下料", "粗加工", "精加工", "检验", "包装"]
        },
        "welding": {
            "name": "焊接加工",
            "steps": ["上料", "下料", "焊接", "打磨", "检验", "包装"]
        },
    }

    # 工序参数模板
    STEP_PARAMS = {
        "喷砂": {"压力": "0.5MPa", "砂料": "钢砂", "目数": "40目", "时间": "5min"},
        "喷漆": {"涂料": "环氧聚氨酯", "厚度": "30μm", "遍数": "2遍", "压力": "0.4MPa"},
        "打磨": {"目数": "320目", "转速": "2500rpm", "时间": "3min"},
        "固化": {"温度": "180℃", "时间": "30min"},
        "磷化": {"温度": "55℃", "时间": "10min", "酸度": "25点"},
        "除油": {"温度": "60℃", "时间": "8min"},
    }

    # 必要的前后工序规则
    NECESSARY_RULES = {
        "喷砂": {"after": [], "before": ["清洁", "干燥"]},
        "喷漆": {"after": ["清洁", "干燥"], "before": ["流平", "固化"]},
        "固化": {"after": ["喷漆", "流平"], "before": ["冷却"]},
        "磷化": {"after": ["除油", "表调"], "before": ["水洗", "干燥"]},
    }

    # 设备推荐
    EQUIPMENT_REC = {
        "喷砂": ["喷砂机", "除尘器", "空压机"],
        "喷漆": ["喷漆房", "空压机", "废气处理"],
        "打磨": ["打磨机", "集尘器"],
        "固化": ["固化炉", "温控系统"],
        "磷化": ["磷化槽", "行车"],
        "焊接": ["焊机", "通风设备"],
    }

    def __init__(self):
        logger.info("工艺扩展智能体初始化完成")

    def expand(self, steps: List[str], process_type: ProcessType = None) -> Dict[str, Any]:
        """
        扩展简写工艺为完整工艺链

        Args:
            steps: 标准化工序列表
            process_type: 工艺类型

        Returns:
            扩展结果字典
        """
        logger.info(f"扩展工艺链: {steps}")

        if not steps:
            return {"error": "无工序输入"}

        # 1. 匹配工艺模板
        matched = self._match_pattern(steps)

        # 2. 构建完整工序链
        complete = self._build_chain(steps, matched)

        # 3. 填充参数
        params = self._fill_params(complete)

        # 4. 推荐设备
        equipment = self._recommend_equipment(complete)

        # 5. 估算消耗
        materials, energy, waste = self._estimate(complete)

        # 6. 计算置信度
        confidence = len(steps) / max(len(complete), 1) * 0.5 + 0.3

        return {
            "original_steps": steps,
            "complete_chain": complete,
            "pattern": matched.get("name", "未知") if matched else "链式扩展",
            "parameters": params,
            "equipment": equipment,
            "materials": materials,
            "energy_consumption": energy,
            "waste": waste,
            "confidence": min(confidence, 0.95),
            "inference": self._build_inference(steps, complete),
        }

    def _match_pattern(self, steps: List[str]) -> Optional[Dict]:
        """匹配最佳工艺模板"""
        step_set = set(steps)
        best_score = 0
        best_match = None

        for pid, pattern in self.STANDARD_CHAINS.items():
            pattern_set = set(pattern["steps"])
            score = len(step_set & pattern_set) / max(len(step_set), 1)
            if score > best_score and score > 0.3:
                best_score = score
                best_match = pattern

        return best_match

    def _build_chain(self, steps: List[str], matched: Optional[Dict]) -> List[str]:
        """构建完整工序链"""
        if matched:
            # 使用模板
            return matched["steps"]
        else:
            # 链式扩展
            complete = []
            prev = None

            for step in steps:
                # 检查必要前置
                if step in self.NECESSARY_RULES:
                    for before in self.NECESSARY_RULES[step].get("after", []):
                        if before not in complete:
                            complete.append(before)

                if step not in complete:
                    complete.append(step)

                # 检查必要后置
                if step in self.NECESSARY_RULES:
                    for after in self.NECESSARY_RULES[step].get("before", []):
                        if after not in complete:
                            complete.append(after)

            # 添加首尾
            if complete and complete[0] != "上料":
                complete.insert(0, "上料")
            if complete and complete[-1] not in ["检验", "包装", "入库"]:
                complete.extend(["检验", "包装", "入库"])

            return complete

    def _fill_params(self, chain: List[str]) -> Dict[str, Dict]:
        """填充工艺参数"""
        return {step: self.STEP_PARAMS.get(step, {}) for step in chain if step in self.STEP_PARAMS}

    def _recommend_equipment(self, chain: List[str]) -> List[str]:
        """推荐设备"""
        equipment = []
        for step in chain:
            if step in self.EQUIPMENT_REC:
                for eq in self.EQUIPMENT_REC[step]:
                    if eq not in equipment:
                        equipment.append(eq)
        return equipment

    def _estimate(self, chain: List[str]) -> Tuple[Dict, float, Dict]:
        """估算材料消耗和废物产生"""
        materials = {}
        energy = 0.0
        waste = {}

        for step in chain:
            if step == "喷砂":
                materials["砂料"] = materials.get("砂料", 0) + 0.5
                energy += 5.0
                waste["粉尘"] = waste.get("粉尘", 0) + 0.8
            elif step == "喷漆":
                materials["涂料"] = materials.get("涂料", 0) + 2.0
                energy += 10.0
                waste["VOCs"] = waste.get("VOCs", 0) + 2.0
                waste["漆渣"] = waste.get("漆渣", 0) + 0.1
            elif step == "固化":
                energy += 30.0
            elif step == "打磨":
                waste["粉尘"] = waste.get("粉尘", 0) + 0.3

        return materials, energy, waste

    def _build_inference(self, original: List[str], complete: List[str]) -> Dict[str, str]:
        """构建推断依据"""
        inferred = {}
        for step in complete:
            if step not in original:
                if step == "清洁":
                    inferred[step] = "推断：处理后必须清洁"
                elif step == "干燥":
                    inferred[step] = "推断：表面需干燥"
                elif step == "流平":
                    inferred[step] = "推断：喷漆后需流平"
                elif step == "固化":
                    inferred[step] = "推断：涂料需固化"
        return inferred
