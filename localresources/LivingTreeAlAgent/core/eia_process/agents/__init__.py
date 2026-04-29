"""
工艺理解智能体 (Process Parser Agent)
====================================

职责：
1. 解析简写工艺，识别工艺类型
2. 建立初步工艺链
3. 识别缺失环节
4. 评估工艺复杂度

作者：Hermes Desktop AI Team
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from core.eia_process import ProcessType, ProcessStep

logger = logging.getLogger(__name__)


class ProcessCategory(Enum):
    """工艺类别"""
    PRETREATMENT = "前处理"          # 除油、除锈、清洗
    SURFACE_TREATMENT = "表面处理"   # 喷砂、喷丸、磷化
    COATING = "涂装"                 # 喷漆、喷粉、电泳
    POST_TREATMENT = "后处理"        # 固化、冷却、检验
    MACHINING = "加工"               # 车铣刨磨
    ASSEMBLY = "装配"               # 装配、焊接
    AUXILIARY = "辅助"               # 运输、除尘、压缩
    QUALITY = "质量"                 # 检验、测试
    PACKAGING = "包装"              # 包装、入库


@dataclass
class ProcessParseResult:
    """工艺解析结果"""
    # 输入
    raw_input: str                          # 原始输入
    raw_steps: List[str]                    # 原始工序列表

    # 解析结果
    standard_steps: List[str]                # 标准化工序
    process_type: ProcessType                # 工艺类型
    category: ProcessCategory                # 工艺类别
    industry: str                            # 所属行业

    # 工艺分析
    complexity: str                          # 复杂度: 简单/中等/复杂
    missing_pre_steps: List[str] = field(default_factory=list)    # 缺失前处理
    missing_post_steps: List[str] = field(default_factory=list)   # 缺失后处理
    missing_aux_steps: List[str] = field(default_factory=list)    # 缺失辅助工序

    # 风险提示
    high_pollution_steps: List[str] = field(default_factory=list)  # 高污染工序
    high_energy_steps: List[str] = field(default_factory=list)     # 高能耗工序
    safety_risk_steps: List[str] = field(default_factory=list)     # 安全风险工序

    # 推断信息
    inferred_material: str = ""              # 推断材料
    inferred_scale: str = ""                  # 推断规模
    inferred_equipment: List[str] = field(default_factory=list)     # 推断设备

    # 置信度
    confidence: float = 0.0                  # 解析置信度 0-1


class ProcessParser:
    """
    工艺理解智能体

    核心能力：
    1. 简写到标准工艺的映射
    2. 工艺类型识别
    3. 缺失环节推断
    4. 风险识别
    """

    # 简写到标准工艺的映射
    SHORT_TO_STANDARD = {
        # 表面处理
        "上料": "上料",
        "下料": "下料",
        "喷砂": "喷砂处理",
        "喷丸": "喷丸处理",
        "抛丸": "抛丸处理",
        "打磨": "打磨处理",
        "抛光": "抛光处理",
        "除油": "除油处理",
        "脱脂": "除油处理",
        "除锈": "除锈处理",
        "酸洗": "酸洗处理",
        "碱洗": "碱洗处理",
        "水洗": "水洗",
        "清水洗": "水洗",
        "纯水洗": "纯水洗",
        "干燥": "干燥",
        "烘干": "烘干",
        "磷化": "磷化处理",
        "表调": "表面调整",
        "钝化": "钝化处理",
        "喷漆": "喷漆",
        "烤漆": "烤漆",
        "浸漆": "浸漆",
        "喷粉": "喷粉",
        "电泳": "电泳涂装",
        "固化": "固化",
        "流平": "流平",
        "冷却": "冷却",
        "检验": "检验",
        "检测": "检测",
        "测试": "测试",
        "包装": "包装",
        "入库": "入库",

        # 机械加工
        "车": "车削",
        "铣": "铣削",
        "刨": "刨削",
        "磨": "磨削",
        "钻": "钻孔",
        "镗": "镗孔",
        "冲压": "冲压",
        "折弯": "折弯",
        "拉伸": "拉伸",
        "焊接": "焊接",
        "切割": "切割",
        "锯切": "锯切",

        # 铸造
        "熔炼": "熔炼",
        "铸造": "铸造",
        "浇注": "浇注",
        "造型": "造型",
        "清砂": "清砂",
        "退火": "退火",
        "正火": "正火",
        "淬火": "淬火",
        "回火": "回火",

        # 化工
        "配料": "配料",
        "混合": "混合",
        "搅拌": "搅拌",
        "加热": "加热",
        "冷却": "冷却",
        "蒸馏": "蒸馏",
        "萃取": "萃取",
        "过滤": "过滤",
        "干燥": "干燥",
        "粉碎": "粉碎",
        "筛分": "筛分",

        # 辅助工序
        "除尘": "除尘",
        "通风": "通风",
        "空压": "压缩空气",
        "喷淋": "喷淋",
        "沉降": "沉降",
        "过滤": "过滤",
    }

    # 工序类别映射
    STEP_CATEGORY_MAP = {
        "上料": ProcessCategory.AUXILIARY,
        "下料": ProcessCategory.AUXILIARY,
        "除油处理": ProcessCategory.PRETREATMENT,
        "脱脂处理": ProcessCategory.PRETREATMENT,
        "除锈处理": ProcessCategory.PRETREATMENT,
        "酸洗处理": ProcessCategory.PRETREATMENT,
        "碱洗处理": ProcessCategory.PRETREATMENT,
        "水洗": ProcessCategory.PRETREATMENT,
        "纯水洗": ProcessCategory.PRETREATMENT,
        "表面调整": ProcessCategory.PRETREATMENT,
        "磷化处理": ProcessCategory.PRETREATMENT,
        "钝化处理": ProcessCategory.PRETREATMENT,
        "喷砂处理": ProcessCategory.SURFACE_TREATMENT,
        "喷丸处理": ProcessCategory.SURFACE_TREATMENT,
        "抛丸处理": ProcessCategory.SURFACE_TREATMENT,
        "打磨处理": ProcessCategory.SURFACE_TREATMENT,
        "抛光处理": ProcessCategory.SURFACE_TREATMENT,
        "喷漆": ProcessCategory.COATING,
        "烤漆": ProcessCategory.COATING,
        "浸漆": ProcessCategory.COATING,
        "喷粉": ProcessCategory.COATING,
        "电泳涂装": ProcessCategory.COATING,
        "流平": ProcessCategory.POST_TREATMENT,
        "固化": ProcessCategory.POST_TREATMENT,
        "烘干": ProcessCategory.POST_TREATMENT,
        "干燥": ProcessCategory.POST_TREATMENT,
        "冷却": ProcessCategory.POST_TREATMENT,
        "检验": ProcessCategory.QUALITY,
        "检测": ProcessCategory.QUALITY,
        "测试": ProcessCategory.QUALITY,
        "包装": ProcessCategory.PACKAGING,
        "入库": ProcessCategory.PACKAGING,
        "车削": ProcessCategory.MACHINING,
        "铣削": ProcessCategory.MACHINING,
        "刨削": ProcessCategory.MACHINING,
        "磨削": ProcessCategory.MACHINING,
        "钻孔": ProcessCategory.MACHINING,
        "镗孔": ProcessCategory.MACHINING,
        "冲压": ProcessCategory.MACHINING,
        "折弯": ProcessCategory.MACHINING,
        "焊接": ProcessCategory.ASSEMBLY,
        "切割": ProcessCategory.MACHINING,
    }

    # 高污染工序
    HIGH_POLLUTION_STEPS = {
        "喷砂处理", "喷丸处理", "抛丸处理",  # 粉尘
        "喷漆", "烤漆", "浸漆", "喷粉",       # VOCs
        "酸洗处理", "碱洗处理",                # 酸碱
        "电泳涂装",                            # 电泳漆
        "熔炼", "铸造",                        # 烟尘
        "焊接",                                 # 烟尘
        "淬火", "回火",                        # 烟尘
    }

    # 高能耗工序
    HIGH_ENERGY_STEPS = {
        "固化", "烘干", "干燥", "加热",  # 热能
        "熔炼", "淬火", "回火",           # 高温
        "电泳涂装",                         # 电能
        "空压", "除尘",                     # 电能
    }

    # 安全风险工序
    SAFETY_RISK_STEPS = {
        "喷砂处理": "粉尘爆炸",
        "喷漆": "易燃易爆",
        "烤漆": "火灾",
        "焊接": "电击、弧光",
        "酸洗处理": "化学灼伤",
        "碱洗处理": "化学灼伤",
        "淬火": "烫伤",
        "熔炼": "高温烫伤",
        "空压": "压力容器",
    }

    def __init__(self):
        """初始化工艺理解智能体"""
        self.short_to_standard = self.SHORT_TO_STANDARD
        self.step_category_map = self.STEP_CATEGORY_MAP

        # 工艺链模式库
        self.process_patterns = self._build_process_patterns()

        logger.info("工艺理解智能体初始化完成")

    def _build_process_patterns(self) -> Dict[str, List[str]]:
        """构建工艺链模式库"""
        return {
            # 金属表面涂装标准流程
            "metal_coating": [
                "上料", "除油处理", "水洗", "除锈处理", "水洗",
                "表面调整", "磷化处理", "水洗", "纯水洗", "干燥",
                "喷漆", "流平", "固化", "冷却", "检验", "包装"
            ],
            # 喷漆简化流程
            "simple_spray_coating": [
                "上料", "打磨处理", "清洁", "干燥",
                "喷漆", "流平", "固化", "冷却", "检验", "包装"
            ],
            # 喷砂+喷漆流程
            "sandblast_coating": [
                "上料", "喷砂处理", "清洁", "干燥",
                "喷漆", "流平", "固化", "冷却", "检验", "包装"
            ],
            # 机械加工标准流程
            "machining": [
                "上料", "下料", "车削", "铣削", "磨削",
                "检验", "包装"
            ],
            # 焊接装配流程
            "welding": [
                "上料", "下料", "切割", "焊接", "打磨",
                "检验", "包装"
            ],
        }

    def parse(self, raw_input: str) -> ProcessParseResult:
        """
        解析简写工艺

        Args:
            raw_input: 原始输入，如 "上料、喷砂、打磨、喷漆"

        Returns:
            ProcessParseResult: 解析结果
        """
        logger.info(f"解析工艺输入: {raw_input}")

        # 1. 分割原始工序
        raw_steps = self._split_steps(raw_input)

        # 2. 转换为标准化工序
        standard_steps = self._normalize_steps(raw_steps)

        # 3. 识别工艺类型
        process_type, category, industry = self._identify_process_type(standard_steps)

        # 4. 评估复杂度
        complexity = self._evaluate_complexity(standard_steps)

        # 5. 识别缺失环节
        missing = self._identify_missing_steps(standard_steps, process_type)

        # 6. 识别风险工序
        risks = self._identify_risks(standard_steps)

        # 7. 推断其他信息
        inferred = self._infer_additional_info(standard_steps)

        # 8. 计算置信度
        confidence = self._calculate_confidence(standard_steps, process_type)

        result = ProcessParseResult(
            raw_input=raw_input,
            raw_steps=raw_steps,
            standard_steps=standard_steps,
            process_type=process_type,
            category=category,
            industry=industry,
            complexity=complexity,
            missing_pre_steps=missing["pre"],
            missing_post_steps=missing["post"],
            missing_aux_steps=missing["aux"],
            high_pollution_steps=risks["pollution"],
            high_energy_steps=risks["energy"],
            safety_risk_steps=risks["safety"],
            inferred_material=inferred["material"],
            inferred_scale=inferred["scale"],
            inferred_equipment=inferred["equipment"],
            confidence=confidence,
        )

        logger.info(f"解析完成: 置信度={confidence:.2f}, 类型={process_type.value}")
        return result

    def _split_steps(self, raw_input: str) -> List[str]:
        """分割原始工序"""
        # 支持多种分隔符
        separators = ["、", ",", "，", ";", "；", "→", "->", ">", "\n"]
        steps = raw_input

        for sep in separators:
            steps = steps.replace(sep, ",")

        # 分割并清理
        raw_steps = [s.strip() for s in steps.split(",")]
        raw_steps = [s for s in raw_steps if s]  # 去除空字符串

        return raw_steps

    def _normalize_steps(self, raw_steps: List[str]) -> List[str]:
        """转换为标准化工序"""
        standard_steps = []

        for step in raw_steps:
            # 精确匹配
            if step in self.short_to_standard:
                standard = self.short_to_standard[step]
                if standard not in standard_steps:
                    standard_steps.append(standard)
            else:
                # 模糊匹配
                normalized = self._fuzzy_match(step)
                if normalized and normalized not in standard_steps:
                    standard_steps.append(normalized)
                elif step not in standard_steps:
                    # 保留原始名称
                    standard_steps.append(step)

        return standard_steps

    def _fuzzy_match(self, step: str) -> Optional[str]:
        """模糊匹配"""
        step_lower = step.lower()

        # 包含匹配
        for short, standard in self.short_to_standard.items():
            if short in step_lower or step_lower in short:
                return standard

        return None

    def _identify_process_type(self, steps: List[str]) -> Tuple[ProcessType, ProcessCategory, str]:
        """识别工艺类型"""
        step_set = set(steps)

        # 涂装类
        coating_steps = {"喷漆", "烤漆", "浸漆", "喷粉", "电泳涂装", "固化"}
        if len(step_set & coating_steps) >= 2:
            if "磷化处理" in step_set or "除油处理" in step_set:
                return ProcessType.SURFACE_TREATMENT, ProcessCategory.COATING, "金属表面涂装"
            return ProcessType.COATING, ProcessCategory.COATING, "涂装"

        # 表面处理类
        surface_steps = {"喷砂处理", "喷丸处理", "抛丸处理", "打磨处理", "抛光处理"}
        if len(step_set & surface_steps) >= 1:
            if coating_steps & step_set:
                return ProcessType.SURFACE_TREATMENT, ProcessCategory.SURFACE_TREATMENT, "表面处理"
            return ProcessType.SURFACE_TREATMENT, ProcessCategory.SURFACE_TREATMENT, "表面处理"

        # 机械加工类
        machining_steps = {"车削", "铣削", "刨削", "磨削", "钻孔", "镗孔"}
        if len(step_set & machining_steps) >= 1:
            return ProcessType.MACHINING, ProcessCategory.MACHINING, "机械加工"

        # 热处理类
        heat_steps = {"淬火", "回火", "正火", "退火", "渗碳"}
        if len(step_set & heat_steps) >= 1:
            return ProcessType.HEAT_TREATMENT, ProcessCategory.MACHINING, "热处理"

        # 铸造类
        casting_steps = {"熔炼", "铸造", "浇注", "造型", "清砂"}
        if len(step_set & casting_steps) >= 2:
            return ProcessType.CASTING, ProcessCategory.MACHINING, "铸造"

        # 焊接类
        if "焊接" in step_set:
            return ProcessType.WELDING, ProcessCategory.ASSEMBLY, "焊接加工"

        # 电子制造
        if "回流焊" in step_set or "波峰焊" in step_set:
            return ProcessType.ELECTRONICS, ProcessCategory.ASSEMBLY, "电子制造"

        return ProcessType.GENERAL, ProcessCategory.AUXILIARY, "通用"

    def _evaluate_complexity(self, steps: List[str]) -> str:
        """评估复杂度"""
        n = len(steps)

        if n <= 3:
            return "简单"
        elif n <= 7:
            return "中等"
        else:
            return "复杂"

    def _identify_missing_steps(self, steps: List[str], process_type: ProcessType) -> Dict[str, List[str]]:
        """识别缺失环节"""
        missing = {"pre": [], "post": [], "aux": []}

        if not steps:
            return missing

        first_step = steps[0]
        last_step = steps[-1]

        # 前处理缺失检测
        pretreat_steps = {"除油处理", "水洗", "除锈处理", "磷化处理", "表面调整"}
        has_pretreat = bool(set(steps) & pretreat_steps)

        if process_type in [ProcessType.SURFACE_TREATMENT, ProcessType.COATING]:
            if not has_pretreat and "打磨处理" not in steps:
                missing["pre"].append("建议添加: 除油、清洁等前处理工序")

        # 后处理缺失检测
        post_steps = {"检验", "检测", "测试", "包装"}
        has_post = bool(set(steps) & post_steps)

        if process_type == ProcessType.COATING and not has_post:
            missing["post"].append("建议添加: 检验、包装等后处理工序")

        # 辅助工序缺失
        if "喷漆" in steps or "烤漆" in steps:
            if "通风" not in steps and "除尘" not in steps:
                missing["aux"].append("建议添加: 除尘、通风设施")

        return missing

    def _identify_risks(self, steps: List[str]) -> Dict[str, List[str]]:
        """识别风险工序"""
        step_set = set(steps)

        risks = {
            "pollution": list(step_set & self.HIGH_POLLUTION_STEPS),
            "energy": list(step_set & self.HIGH_ENERGY_STEPS),
            "safety": []
        }

        for step in step_set:
            if step in self.SAFETY_RISK_STEPS:
                risks["safety"].append(f"{step}: {self.SAFETY_RISK_STEPS[step]}")

        return risks

    def _infer_additional_info(self, steps: List[str]) -> Dict[str, Any]:
        """推断附加信息"""
        info = {
            "material": "",
            "scale": "中等",
            "equipment": []
        }

        step_set = set(steps)

        # 材料推断
        if "喷砂处理" in step_set or "喷丸处理" in step_set or "抛丸处理" in step_set:
            info["material"] = "金属"
        elif "磷化处理" in step_set:
            info["material"] = "钢铁"
        elif "喷漆" in step_set or "烤漆" in step_set:
            info["material"] = "金属/塑料"

        # 规模推断（基于工序数量）
        if len(steps) <= 3:
            info["scale"] = "小批量"
        elif len(steps) <= 7:
            info["scale"] = "中等批量"
        else:
            info["scale"] = "大批量"

        # 设备推断
        for step in steps:
            if step == "喷砂处理":
                info["equipment"].extend(["喷砂机", "除尘器"])
            elif step == "喷漆":
                info["equipment"].extend(["喷漆房", "空压机", "废气处理"])
            elif step == "打磨处理":
                info["equipment"].extend(["打磨机", "集尘器"])
            elif step == "焊接":
                info["equipment"].append("焊接设备")
            elif step == "固化" or step == "烘干":
                info["equipment"].append("固化炉/烘箱")

        return info

    def _calculate_confidence(self, steps: List[str], process_type: ProcessType) -> float:
        """计算置信度"""
        if not steps:
            return 0.0

        confidence = 0.5  # 基础置信度

        # 步骤标准化率高
        standard_count = sum(1 for s in steps if s in self.short_to_standard)
        confidence += 0.2 * (standard_count / len(steps))

        # 工序完整
        if len(steps) >= 3:
            confidence += 0.15

        # 类型识别清晰
        if process_type != ProcessType.UNKNOWN:
            confidence += 0.15

        return min(confidence, 1.0)

    def parse_to_dict(self, raw_input: str) -> Dict[str, Any]:
        """解析并返回字典格式"""
        result = self.parse(raw_input)
        return {
            "raw_input": result.raw_input,
            "raw_steps": result.raw_steps,
            "standard_steps": result.standard_steps,
            "process_type": result.process_type.value,
            "category": result.category.value,
            "industry": result.industry,
            "complexity": result.complexity,
            "missing_pre_steps": result.missing_pre_steps,
            "missing_post_steps": result.missing_post_steps,
            "missing_aux_steps": result.missing_aux_steps,
            "high_pollution_steps": result.high_pollution_steps,
            "high_energy_steps": result.high_energy_steps,
            "safety_risk_steps": result.safety_risk_steps,
            "inferred_material": result.inferred_material,
            "inferred_scale": result.inferred_scale,
            "inferred_equipment": result.inferred_equipment,
            "confidence": result.confidence,
        }
