"""
思维链数据构造器 (Reasoning Chain Builder)

专门构造包含显式推理步骤的训练样本，让模型学会"思考"。

核心功能：
1. 构造选型任务的思维链
2. 构造故障诊断的思维链
3. 构造方案对比的思维链
4. 支持多种推理模式（演绎、归纳、排除）
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_number: int
    description: str
    type: str = "deduction"  # deduction, induction, elimination, comparison
    confidence: float = 1.0
    evidence: Optional[str] = None  # 依据（如标准号、公式、经验）


@dataclass
class ReasoningChainSample:
    """思维链训练样本"""
    instruction: str
    input_data: str
    reasoning_steps: List[ReasoningStep]
    final_answer: str
    uncertainty: Optional[str] = None
    task_type: str = "selection"
    difficulty: int = 1  # 1-5
    domain: str = "general"
    created_at: datetime = field(default_factory=datetime.now)


class ReasoningChainBuilder:
    """
    思维链构造器
    
    专门构造包含显式推理步骤的训练样本：
    1. 选型任务：逐步排除、权衡选择
    2. 故障诊断：现象分析、原因排查
    3. 方案对比：多维度评估
    """
    
    def __init__(self):
        # 行业知识规则库
        self.domain_rules: Dict[str, List[Dict]] = {}
        
        # 标准库
        self.standards = {
            "GB/T 1184-1996": "形状和位置公差 未注公差值",
            "GB/T 1800.1-2020": "极限与配合 第1部分：公差、偏差和配合的基础",
            "GB/T 8163-2018": "输送流体用无缝钢管",
            "GB 7258-2017": "机动车运行安全技术条件"
        }
        
        # 材料特性库
        self.materials = {
            "304不锈钢": {"corrosion_resistance": "高", "temperature_limit": 870, "cost": "中"},
            "316不锈钢": {"corrosion_resistance": "极高", "temperature_limit": 870, "cost": "高"},
            "哈氏C-276": {"corrosion_resistance": "极高", "temperature_limit": 1093, "cost": "极高"},
            "PTFE": {"corrosion_resistance": "极高", "temperature_limit": 260, "cost": "中"},
            "Q235": {"corrosion_resistance": "低", "temperature_limit": 600, "cost": "低"},
            "45号钢": {"corrosion_resistance": "低", "temperature_limit": 600, "cost": "低"}
        }
        
        # 设备类型库
        self.equipment_types = {
            "流量计": ["电磁流量计", "涡街流量计", "差压流量计", "金属管浮子流量计", "超声波流量计"],
            "温度传感器": ["PT100", "热电偶K型", "热电偶J型", "热敏电阻"],
            "压力传感器": ["压电式", "应变式", "电容式", "压阻式"],
            "电机": ["异步电机", "永磁同步电机", "伺服电机", "步进电机"]
        }
        
        # 构造的样本
        self.samples: List[ReasoningChainSample] = []
        
        # 统计
        self.total_samples = 0
        self.samples_by_domain = {}
        
        print("[ReasoningChainBuilder] 初始化完成")
    
    def add_domain_rules(self, domain: str, rules: List[Dict]):
        """
        添加行业规则
        
        Args:
            domain: 行业领域
            rules: 规则列表，每个规则包含 condition 和 conclusion
        """
        if domain not in self.domain_rules:
            self.domain_rules[domain] = []
        self.domain_rules[domain].extend(rules)
        print(f"[ReasoningChainBuilder] 添加 {len(rules)} 条 {domain} 规则")
    
    def build_selection_chain(self, instruction: str, input_data: str, 
                             domain: str = "general") -> ReasoningChainSample:
        """
        构建选型任务的思维链
        
        Args:
            instruction: 指令
            input_data: 输入数据（包含选型条件）
            domain: 行业领域
            
        Returns:
            包含思维链的训练样本
        """
        reasoning_steps = []
        step_num = 1
        
        # 步骤1：解析输入条件
        conditions = self._parse_conditions(input_data)
        reasoning_steps.append(ReasoningStep(
            step_number=step_num,
            description=f"解析输入条件：{', '.join([f'{k}: {v}' for k, v in conditions.items()])}",
            type="deduction",
            confidence=1.0
        ))
        step_num += 1
        
        # 步骤2：环境判定
        if "介质" in conditions or "环境" in conditions:
            medium = conditions.get("介质", conditions.get("环境", ""))
            material = self._determine_material(medium)
            reasoning_steps.append(ReasoningStep(
                step_number=step_num,
                description=f"环境判定：{medium} → 推荐材质：{material}",
                type="deduction",
                confidence=0.9
            ))
            step_num += 1
        
        # 步骤3：温度/压力筛选
        if "温度" in conditions:
            temp = float(conditions["温度"].replace("℃", "").strip())
            excluded = self._exclude_by_temperature(temp)
            if excluded:
                reasoning_steps.append(ReasoningStep(
                    step_number=step_num,
                    description=f"温度筛选：{temp}℃ 排除{', '.join(excluded)}",
                    type="elimination",
                    confidence=0.95
                ))
                step_num += 1
        
        # 步骤4：类型筛选
        equipment_type = self._extract_equipment_type(input_data)
        if equipment_type:
            types = self.equipment_types.get(equipment_type, [])
            reasoning_steps.append(ReasoningStep(
                step_number=step_num,
                description=f"类型筛选：{equipment_type}可选类型：{', '.join(types)}",
                type="deduction",
                confidence=0.9
            ))
            step_num += 1
        
        # 步骤5：精度/性能权衡
        if "精度" in conditions or "误差" in conditions:
            accuracy = conditions.get("精度", conditions.get("误差", ""))
            reasoning_steps.append(ReasoningStep(
                step_number=step_num,
                description=f"精度权衡：要求{accuracy}，选择满足要求的型号",
                type="comparison",
                confidence=0.85
            ))
            step_num += 1
        
        # 生成最终答案
        final_answer = self._generate_final_answer(equipment_type, conditions, reasoning_steps)
        
        # 生成不确定性说明
        uncertainty = self._generate_uncertainty(conditions)
        
        sample = ReasoningChainSample(
            instruction=instruction,
            input_data=input_data,
            reasoning_steps=reasoning_steps,
            final_answer=final_answer,
            uncertainty=uncertainty,
            task_type="selection",
            difficulty=self._calculate_difficulty(reasoning_steps),
            domain=domain
        )
        
        self._add_sample(sample)
        return sample
    
    def build_diagnosis_chain(self, instruction: str, input_data: str,
                             domain: str = "general") -> ReasoningChainSample:
        """
        构建故障诊断的思维链
        
        Args:
            instruction: 指令
            input_data: 输入数据（包含故障现象）
            domain: 行业领域
            
        Returns:
            包含思维链的训练样本
        """
        reasoning_steps = []
        step_num = 1
        
        # 步骤1：现象描述
        reasoning_steps.append(ReasoningStep(
            step_number=step_num,
            description=f"现象确认：{input_data}",
            type="deduction",
            confidence=1.0
        ))
        step_num += 1
        
        # 步骤2：初步分析
        symptoms = self._extract_symptoms(input_data)
        reasoning_steps.append(ReasoningStep(
            step_number=step_num,
            description=f"症状提取：{', '.join(symptoms)}",
            type="deduction",
            confidence=0.95
        ))
        step_num += 1
        
        # 步骤3：可能原因列举
        causes = self._list_possible_causes(symptoms)
        reasoning_steps.append(ReasoningStep(
            step_number=step_num,
            description=f"可能原因：{', '.join(causes)}",
            type="induction",
            confidence=0.8
        ))
        step_num += 1
        
        # 步骤4：逐一排除
        for i, cause in enumerate(causes[:-1], 1):
            reasoning_steps.append(ReasoningStep(
                step_number=step_num,
                description=f"排除原因{i}：{cause}（依据：经验/测试）",
                type="elimination",
                confidence=0.85
            ))
            step_num += 1
        
        # 步骤5：确定根本原因
        if causes:
            reasoning_steps.append(ReasoningStep(
                step_number=step_num,
                description=f"确定根本原因：{causes[-1]}",
                type="deduction",
                confidence=0.9
            ))
            step_num += 1
        
        # 步骤6：给出解决方案
        solution = self._generate_solution(causes[-1] if causes else "")
        reasoning_steps.append(ReasoningStep(
            step_number=step_num,
            description=f"解决方案：{solution}",
            type="deduction",
            confidence=0.85
        ))
        
        final_answer = f"根据分析，故障原因可能是{causes[-1] if causes else '未知'}。{solution}"
        uncertainty = "以上分析基于经验推断，建议通过实际检测验证。"
        
        sample = ReasoningChainSample(
            instruction=instruction,
            input_data=input_data,
            reasoning_steps=reasoning_steps,
            final_answer=final_answer,
            uncertainty=uncertainty,
            task_type="diagnosis",
            difficulty=self._calculate_difficulty(reasoning_steps),
            domain=domain
        )
        
        self._add_sample(sample)
        return sample
    
    def build_comparison_chain(self, instruction: str, input_data: str,
                              domain: str = "general") -> ReasoningChainSample:
        """
        构建方案对比的思维链
        
        Args:
            instruction: 指令
            input_data: 输入数据（包含两个方案）
            domain: 行业领域
            
        Returns:
            包含思维链的训练样本
        """
        reasoning_steps = []
        step_num = 1
        
        # 步骤1：解析方案
        plans = self._parse_plans(input_data)
        reasoning_steps.append(ReasoningStep(
            step_number=step_num,
            description=f"方案解析：方案A={plans.get('A', '')}，方案B={plans.get('B', '')}",
            type="deduction",
            confidence=1.0
        ))
        step_num += 1
        
        # 步骤2：维度对比
        dimensions = ["成本", "可靠性", "维护难度", "性能", "工期"]
        for dim in dimensions:
            reasoning_steps.append(ReasoningStep(
                step_number=step_num,
                description=f"{dim}对比：方案A vs 方案B",
                type="comparison",
                confidence=0.85
            ))
            step_num += 1
        
        # 步骤3：权重分析
        reasoning_steps.append(ReasoningStep(
            step_number=step_num,
            description="权重分析：根据项目需求分配各维度权重",
            type="deduction",
            confidence=0.8
        ))
        step_num += 1
        
        # 步骤4：综合评估
        reasoning_steps.append(ReasoningStep(
            step_number=step_num,
            description="综合评估：计算各方案得分",
            type="deduction",
            confidence=0.85
        ))
        
        final_answer = "综合以上分析，建议选择方案A（或方案B）。"
        uncertainty = "评估基于当前信息，实际决策需考虑更多项目约束。"
        
        sample = ReasoningChainSample(
            instruction=instruction,
            input_data=input_data,
            reasoning_steps=reasoning_steps,
            final_answer=final_answer,
            uncertainty=uncertainty,
            task_type="comparison",
            difficulty=self._calculate_difficulty(reasoning_steps),
            domain=domain
        )
        
        self._add_sample(sample)
        return sample
    
    def _parse_conditions(self, input_data: str) -> Dict[str, str]:
        """解析输入条件"""
        conditions = {}
        
        # 匹配"介质为XX"模式
        match = re.search(r'介质[为是]?\s*([\u4e00-\u9fa5a-zA-Z]+)', input_data)
        if match:
            conditions["介质"] = match.group(1)
        
        # 匹配"温度XX"模式
        match = re.search(r'温度\s*([\d.]+)\s*℃', input_data)
        if match:
            conditions["温度"] = f"{match.group(1)}℃"
        
        # 匹配"压力XX"模式
        match = re.search(r'压力\s*([\d.]+)\s*MPa', input_data)
        if match:
            conditions["压力"] = f"{match.group(1)}MPa"
        
        # 匹配"精度XX"模式
        match = re.search(r'精度\s*[要求为]?\s*([\d.]+[%℃])', input_data)
        if match:
            conditions["精度"] = match.group(1)
        
        return conditions
    
    def _determine_material(self, medium: str) -> str:
        """根据介质确定推荐材质"""
        medium_lower = medium.lower()
        
        if "硫酸" in medium_lower or "腐蚀" in medium_lower:
            return "哈氏C-276或PTFE"
        elif "水" in medium_lower or "油" in medium_lower:
            return "304不锈钢"
        elif "高温" in medium_lower:
            return "耐高温合金"
        else:
            return "碳钢或不锈钢"
    
    def _exclude_by_temperature(self, temp: float) -> List[str]:
        """根据温度排除不合适的选项"""
        excluded = []
        
        if temp > 200:
            excluded.append("塑料材质")
        if temp > 400:
            excluded.append("普通橡胶")
        if temp < -40:
            excluded.append("常规传感器")
        
        return excluded
    
    def _extract_equipment_type(self, input_data: str) -> Optional[str]:
        """提取设备类型"""
        for eq_type in self.equipment_types.keys():
            if eq_type in input_data:
                return eq_type
        return None
    
    def _generate_final_answer(self, equipment_type: str, conditions: Dict, 
                              steps: List[ReasoningStep]) -> str:
        """生成最终答案"""
        material = self._determine_material(conditions.get("介质", ""))
        eq_types = self.equipment_types.get(equipment_type, [])
        
        if eq_types:
            main_type = eq_types[0]
        else:
            main_type = equipment_type or "设备"
        
        return f"推荐选用**{main_type}**，材质建议**{material}**。"
    
    def _generate_uncertainty(self, conditions: Dict) -> str:
        """生成不确定性说明"""
        missing = []
        if "浓度" not in conditions and ("硫酸" in conditions.get("介质", "") or "酸" in conditions.get("介质", "")):
            missing.append("浓度")
        if "压力" not in conditions:
            missing.append("压力")
        
        if missing:
            return f"需确认{','.join(missing)}等参数，以便给出更精确的建议。"
        return None
    
    def _extract_symptoms(self, input_data: str) -> List[str]:
        """提取故障症状"""
        symptom_patterns = [
            r'(过热|温度过高)',
            r'(异响|噪音大)',
            r'(振动|抖动)',
            r'(泄漏|渗漏)',
            r'(报警|故障灯)',
            r'(停机|无法启动)',
            r'(性能下降|效率降低)'
        ]
        
        symptoms = []
        for pattern in symptom_patterns:
            match = re.search(pattern, input_data)
            if match:
                symptoms.append(match.group(1))
        
        if not symptoms:
            symptoms = ["异常现象"]
        
        return symptoms
    
    def _list_possible_causes(self, symptoms: List[str]) -> List[str]:
        """列举可能原因"""
        cause_map = {
            "过热": ["散热不良", "过载运行", "轴承损坏", "润滑不足"],
            "异响": ["轴承磨损", "齿轮损坏", "松动件", "不平衡"],
            "振动": ["不平衡", "不对中", "轴承问题", "基础松动"],
            "泄漏": ["密封损坏", "法兰松动", "焊缝缺陷", "腐蚀"]
        }
        
        causes = []
        for symptom in symptoms:
            if symptom in cause_map:
                causes.extend(cause_map[symptom])
        
        if not causes:
            causes = ["待排查"]
        
        return list(set(causes))[:4]  # 最多4个原因
    
    def _generate_solution(self, cause: str) -> str:
        """生成解决方案"""
        solution_map = {
            "轴承损坏": "建议更换轴承并检查润滑系统。",
            "散热不良": "建议清理散热器或增加散热措施。",
            "密封损坏": "建议更换密封件并检查密封面。",
            "过载运行": "建议检查负载情况，必要时降低负载。"
        }
        
        return solution_map.get(cause, "建议进一步检查确认具体原因。")
    
    def _parse_plans(self, input_data: str) -> Dict[str, str]:
        """解析方案内容"""
        plans = {}
        
        match = re.search(r'方案[AB]：(.+?)(?=方案[AB]|$)', input_data, re.DOTALL)
        if match:
            plans["A"] = match.group(1).strip()
        
        return plans
    
    def _calculate_difficulty(self, steps: List[ReasoningStep]) -> int:
        """计算难度"""
        complexity = len(steps)
        if complexity <= 3:
            return 1
        elif complexity <= 5:
            return 2
        elif complexity <= 7:
            return 3
        elif complexity <= 9:
            return 4
        else:
            return 5
    
    def _add_sample(self, sample: ReasoningChainSample):
        """添加样本"""
        self.samples.append(sample)
        self.total_samples += 1
        
        if sample.domain not in self.samples_by_domain:
            self.samples_by_domain[sample.domain] = 0
        self.samples_by_domain[sample.domain] += 1
    
    def export_to_json(self, filepath: str):
        """导出为JSON"""
        data = []
        for sample in self.samples:
            steps = []
            for step in sample.reasoning_steps:
                steps.append({
                    "step_number": step.step_number,
                    "description": step.description,
                    "type": step.type,
                    "confidence": step.confidence,
                    "evidence": step.evidence
                })
            
            data.append({
                "instruction": sample.instruction,
                "input": sample.input_data,
                "reasoning": steps,
                "output": sample.final_answer,
                "uncertainty": sample.uncertainty,
                "task_type": sample.task_type,
                "difficulty": sample.difficulty,
                "domain": sample.domain,
                "created_at": sample.created_at.isoformat()
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[ReasoningChainBuilder] 导出 {len(data)} 条思维链样本")
    
    def import_from_json(self, filepath: str):
        """从JSON导入"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            steps = []
            for step_data in item.get("reasoning", []):
                steps.append(ReasoningStep(
                    step_number=step_data["step_number"],
                    description=step_data["description"],
                    type=step_data.get("type", "deduction"),
                    confidence=step_data.get("confidence", 1.0),
                    evidence=step_data.get("evidence")
                ))
            
            sample = ReasoningChainSample(
                instruction=item["instruction"],
                input_data=item["input"],
                reasoning_steps=steps,
                final_answer=item["output"],
                uncertainty=item.get("uncertainty"),
                task_type=item.get("task_type", "selection"),
                difficulty=item.get("difficulty", 1),
                domain=item.get("domain", "general")
            )
            self._add_sample(sample)
        
        print(f"[ReasoningChainBuilder] 导入 {len(data)} 条思维链样本")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_samples": self.total_samples,
            "samples_by_domain": self.samples_by_domain,
            "domains": list(self.domain_rules.keys()),
            "average_difficulty": sum(s.difficulty for s in self.samples) / max(len(self.samples), 1)
        }


# 正则表达式导入（在类定义之后）
import re


def create_reasoning_chain_builder() -> ReasoningChainBuilder:
    """创建思维链构造器实例"""
    return ReasoningChainBuilder()


__all__ = [
    "ReasoningChainBuilder",
    "ReasoningChainSample",
    "ReasoningStep",
    "create_reasoning_chain_builder"
]