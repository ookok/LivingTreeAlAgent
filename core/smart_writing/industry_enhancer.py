# -*- coding: utf-8 -*-
"""
行业增强模式 - Industry Enhancement Mode
=========================================

功能：
1. 行业知识库自动加载
2. 行业特定数据采集增强
3. 行业术语和模板定制
4. 行业标准规范自动引用
5. 行业推理逻辑增强

复用模块：
- SmartWritingEvolutionEngine (知识积累)
- KnowledgeBaseVectorStore (知识存储)

Author: Hermes Desktop Team
"""

import logging
import json
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class IndustryType(Enum):
    """行业类型"""
    CHEMICAL = "chemical"        # 化工
    PHARMACEUTICAL = "pharma"    # 制药
    ELECTRONIC = "electronic"    # 电子
    PAPER = "paper"             # 造纸
    STEEL = "steel"             # 钢铁
    COAL = "coal"               # 煤矿
    SOLAR = "solar"             # 光伏
    WIND = "wind"               # 风电
    REAL_ESTATE = "real_estate" # 房地产
    TRANSPORT = "transport"     # 交通运输
    AGRICULTURE = "agriculture" # 农业
    MUNICIPAL = "municipal"     # 市政
    OTHER = "other"              # 其他


@dataclass
class IndustryConfig:
    """行业配置"""
    industry: IndustryType
    name: str
    aliases: List[str]  # 别名
    
    # 文档类型
    common_doc_types: List[str]
    
    # 行业标准
    standards: List[str]
    
    # 术语词典
    terminology: Dict[str, str]  # 英文 -> 中文
    
    # 关键参数
    key_parameters: List[str]
    
    # 数据采集增强
    data_sources: Dict[str, str]  # 数据类型 -> 来源
    
    # 污染物/关注点
    concerns: List[str]
    
    # 计算模型
    calculation_templates: List[str]


# 行业配置库
INDUSTRY_CONFIGS: Dict[str, IndustryConfig] = {}


def _init_industry_configs():
    """初始化行业配置"""
    
    # 化工行业
    INDUSTRY_CONFIGS["化工"] = IndustryConfig(
        industry=IndustryType.CHEMICAL,
        name="化工行业",
        aliases=["化工", "石油化工", "煤化工", "精细化工"],
        common_doc_types=["eia_report", "feasibility_report", "safety_assessment"],
        standards=[
            "GB 3095-2012", "GB 3838-2002", "GB 3096-2008",
            "HJ 2.2-2018", "HJ 2.3-2018", "GB 50016-2014",
            "GB 18218-2018", "AQ 8001-2007",
        ],
        terminology={
            "EIA": "环境影响评价",
            "VOC": "挥发性有机物",
            "PID": "工艺流程图",
            "FDI": "外国直接投资",
        },
        key_parameters=[
            "产能规模", "投资强度", "能耗指标", "水耗指标",
            "污染物排放量", "万元产值综合能耗",
        ],
        data_sources={
            "market": "中国化工信息网",
            "standards": "工信部标准库",
            "environmental": "生态环境部",
            "safety": "应急管理部",
        },
        concerns=["VOC排放", "废水处理", "固废处置", "重大危险源", "应急预案"],
        calculation_templates=["物料平衡", "污染物排放量", "安全防护距离", "NVP/IRR"],
    )
    
    # 制药行业
    INDUSTRY_CONFIGS["制药"] = IndustryConfig(
        industry=IndustryType.PHARMACEUTICAL,
        name="制药行业",
        aliases=["制药", "生物制药", "中药", "化学制药"],
        common_doc_types=["eia_report", "feasibility_report", "validation_report"],
        standards=[
            "GB 50457-2019", "GB 50016-2014", "GB 3095-2012",
            "HJ 610-2016", "药品生产质量管理规范",
        ],
        terminology={
            "GMP": "药品生产质量管理规范",
            "API": "原料药",
            "Validation": "验证",
        },
        key_parameters=["产能", "清洁生产水平", "用水量", "废水COD"],
        data_sources={
            "market": "医药统计网",
            "standards": "国家药监局",
        },
        concerns=["废水治理", "有机溶剂回收", "恶臭控制", "清洁生产"],
        calculation_templates=["排水量估算", "废气排放量", "清洁生产指标"],
    )
    
    # 光伏行业
    INDUSTRY_CONFIGS["光伏"] = IndustryConfig(
        industry=IndustryType.SOLAR,
        name="光伏行业",
        aliases=["光伏", "太阳能", "新能源"],
        common_doc_types=["eia_report", "feasibility_report", "land_survey"],
        standards=[
            "GB 3095-2012", "HJ 164-2020", "GB 36600-2018",
            "光伏发电站设计规范 GB 50797-2012",
        ],
        terminology={
            "PV": "光伏",
            "MWp": "兆瓦峰值",
            "PR": "系统效率",
        },
        key_parameters=["装机容量", "占地面积", "年发电量", "土地类型"],
        data_sources={
            "weather": "气象局",
            "land": "自然资源部",
        },
        concerns=["土地占用", "生态影响", "光污染", "退役组件处理"],
        calculation_templates=["发电量估算", "占地面积计算", "环境效益分析"],
    )
    
    # 风电行业
    INDUSTRY_CONFIGS["风电"] = IndustryConfig(
        industry=IndustryType.WIND,
        name="风电行业",
        aliases=["风电", "风力发电", "海上风电", "陆上风电"],
        common_doc_types=["eia_report", "feasibility_report", "bird_migration"],
        standards=[
            "HJ 916-2017", "GB 3096-2008",
            "风电场工程设计规范 GB 51095-2015",
        ],
        terminology={
            "WTG": "风力发电机",
            "AEP": "年发电量",
            "CF": "容量系数",
        },
        key_parameters=["装机容量", "风机数量", "轮毂高度", "年发电量"],
        data_sources={
            "wind": "气象局风能资源评估",
            "wildlife": "生态环境部",
        },
        concerns=["鸟类保护", "噪声影响", "电磁辐射", "视觉景观"],
        calculation_templates=["发电量估算", "噪声预测", "风机阴影分析"],
    )
    
    # 钢铁行业
    INDUSTRY_CONFIGS["钢铁"] = IndustryConfig(
        industry=IndustryType.STEEL,
        name="钢铁行业",
        aliases=["钢铁", "冶金", "黑色金属"],
        common_doc_types=["eia_report", "feasibility_report", "safety_assessment"],
        standards=[
            "GB 3095-2012", "GB 28662-2012", "GB 28663-2012",
            "GB 13456-2012", "GB 4915-2013",
        ],
        terminology={
            "BF": "高炉",
            "BOF": "转炉",
            "EAF": "电炉",
        },
        key_parameters=["产能", "工序能耗", "污染物排放量", "吨钢综合能耗"],
        data_sources={
            "market": "中国钢铁工业协会",
            "standards": "工信部",
        },
        concerns=["粉尘排放", "SO2排放", "NOx排放", "固废综合利用"],
        calculation_templates=["污染物排放量", "能耗计算", "清洁生产审核"],
    )
    
    # 市政行业
    INDUSTRY_CONFIGS["市政"] = IndustryConfig(
        industry=IndustryType.MUNICIPAL,
        name="市政行业",
        aliases=["市政", "城市基础设施", "公用事业"],
        common_doc_types=["eia_report", "feasibility_report"],
        standards=[
            "GB 18918-2002", "GB 3096-2008", "GB 12523-2011",
            "城市污水处理厂污染物排放标准",
        ],
        terminology={
            "WWTP": "污水处理厂",
            "WTP": "自来水厂",
            "MBR": "膜生物反应器",
        },
        key_parameters=["处理规模", "服务人口", "进水水质", "出水水质"],
        data_sources={
            "water": "住建部",
            "environmental": "生态环境部",
        },
        concerns=["臭气治理", "污泥处置", "噪声控制", "中水回用"],
        calculation_templates=["处理能力计算", "污染物削减量", "工程投资估算"],
    )


_init_industry_configs()


class IndustryEnhancer:
    """
    行业增强器
    
    使用示例：
    ```python
    enhancer = IndustryEnhancer()
    
    # 激活行业模式
    enhancer.activate("化工")
    
    # 获取行业术语
    terms = enhancer.get_terminology("chemical_industry")
    
    # 获取行业标准
    standards = enhancer.get_standards()
    
    # 获取数据采集配置
    data_config = enhancer.get_data_sources()
    
    # 行业化内容生成
    content = enhancer.enhance_content(basic_content)
    
    # 行业推理
    inference = enhancer.industry_inference(requirement)
    ```
    """
    
    def __init__(self):
        self._active_industry: Optional[IndustryConfig] = None
        self._knowledge_base = None
        self._term_cache: Dict[str, str] = {}
        
    @property
    def knowledge_base(self):
        """延迟加载知识库"""
        if self._knowledge_base is None:
            try:
                from core.knowledge_vector_db import KnowledgeBaseVectorStore
                self._knowledge_base = KnowledgeBaseVectorStore()
            except ImportError:
                logger.warning("KnowledgeBaseVectorStore 未安装")
        return self._knowledge_base
    
    def activate(self, industry_name: str) -> bool:
        """
        激活行业模式
        
        Args:
            industry_name: 行业名称
        
        Returns:
            bool: 是否激活成功
        """
        industry_name = industry_name.strip()
        
        # 精确匹配
        if industry_name in INDUSTRY_CONFIGS:
            self._active_industry = INDUSTRY_CONFIGS[industry_name]
            logger.info(f"已激活行业模式: {self._active_industry.name}")
            return True
            
        # 别名匹配
        for config in INDUSTRY_CONFIGS.values():
            if industry_name in config.aliases:
                self._active_industry = config
                logger.info(f"已激活行业模式: {config.name}")
                return True
                
        # 模糊匹配
        for key, config in INDUSTRY_CONFIGS.items():
            if industry_name in key or key in industry_name:
                self._active_industry = config
                logger.info(f"已激活行业模式(模糊): {config.name}")
                return True
                
        # 未找到，设置默认
        logger.warning(f"未找到匹配行业 '{industry_name}'，使用默认配置")
        self._active_industry = IndustryConfig(
            industry=IndustryType.OTHER,
            name=industry_name,
            aliases=[industry_name],
            common_doc_types=["feasibility_report"],
            standards=[],
            terminology={},
            key_parameters=[],
            data_sources={},
            concerns=["常规关注"],
            calculation_templates=["基础计算"],
        )
        return True
    
    def deactivate(self):
        """关闭行业模式"""
        self._active_industry = None
        logger.info("已关闭行业模式")
    
    def is_active(self) -> bool:
        """是否已激活"""
        return self._active_industry is not None
    
    def get_current_industry(self) -> Optional[str]:
        """获取当前行业"""
        return self._active_industry.name if self._active_industry else None
    
    def get_terminology(self, term: Optional[str] = None) -> Dict[str, str]:
        """
        获取行业术语
        
        Args:
            term: 特定术语（可选）
        
        Returns:
            Dict: 术语词典
        """
        if not self._active_industry:
            return {}
            
        terminology = self._active_industry.terminology.copy()
        
        # 添加行业通用术语
        common_terms = {
            "EIA": "环境影响评价",
            "EHS": "环境健康安全",
            "EMP": "环境管理计划",
            "CCTV": "闭路电视监控",
        }
        terminology.update(common_terms)
        
        if term:
            return {term: terminology.get(term.upper(), terminology.get(term, ""))}
            
        return terminology
    
    def translate_term(self, term: str) -> str:
        """
        翻译/转换术语
        
        Args:
            term: 英文或缩写
        
        Returns:
            str: 中文术语
        """
        if not self._active_industry:
            return term
            
        terminology = self._active_industry.terminology
        return terminology.get(term.upper(), terminology.get(term, term))
    
    def get_standards(self, category: Optional[str] = None) -> List[str]:
        """
        获取行业标准
        
        Args:
            category: 标准类别 (environmental/safety/technical)
        
        Returns:
            List[str]: 标准列表
        """
        if not self._active_industry:
            return []
            
        standards = self._active_industry.standards.copy()
        
        if category == "environmental":
            return [s for s in standards if s.startswith(("GB 30", "GB 38", "HJ"))]
        elif category == "safety":
            return [s for s in standards if s.startswith(("GB 18", "AQ"))]
        elif category == "technical":
            return [s for s in standards if not s.startswith(("GB", "HJ", "AQ"))]
            
        return standards
    
    def get_data_sources(self, data_type: Optional[str] = None) -> Dict[str, str]:
        """
        获取行业数据源
        
        Args:
            data_type: 数据类型 (market/environmental/weather等)
        
        Returns:
            Dict: 数据源配置
        """
        if not self._active_industry:
            return {}
            
        sources = self._active_industry.data_sources.copy()
        
        if data_type:
            return {data_type: sources.get(data_type, "通用数据源")}
            
        return sources
    
    def get_concerns(self) -> List[str]:
        """获取行业关注点"""
        if not self._active_industry:
            return []
        return self._active_industry.concerns
    
    def get_calculation_templates(self) -> List[str]:
        """获取计算模板"""
        if not self._active_industry:
            return []
        return self._active_industry.calculation_templates
    
    def enhance_content(self, content: str, context: Optional[Dict] = None) -> str:
        """
        行业化内容增强
        
        Args:
            content: 原始内容
            context: 上下文信息
        
        Returns:
            str: 增强后的内容
        """
        if not self._active_industry:
            return content
            
        enhanced = content
        
        # 1. 术语替换
        for eng_term, chn_term in self._active_industry.terminology.items():
            # 保留英文缩写时加中文
            if eng_term.isupper() and len(eng_term) <= 5:
                enhanced = enhanced.replace(eng_term, f"{eng_term}({chn_term})")
            else:
                # 完全替换
                pattern = re.compile(re.escape(eng_term), re.IGNORECASE)
                enhanced = pattern.sub(chn_term, enhanced)
                
        # 2. 添加关注点提示
        if context and context.get("add_hints"):
            concerns = self.get_concerns()
            hint_text = "\n\n".join([f"**{c}**: " for c in concerns])
            enhanced += f"\n\n## 行业重点关注\n{hint_text}"
            
        return enhanced
    
    def enhance_data_collection(self, base_config: Dict) -> Dict:
        """
        行业化数据采集配置
        
        Args:
            base_config: 基础采集配置
        
        Returns:
            Dict: 增强后的配置
        """
        if not self._active_industry:
            return base_config
            
        enhanced = base_config.copy()
        
        # 添加行业特定数据源
        industry_sources = self.get_data_sources()
        if "industry_sources" not in enhanced:
            enhanced["industry_sources"] = industry_sources
            
        # 添加关键参数
        enhanced["key_parameters"] = self._active_industry.key_parameters
        
        # 添加关注点
        enhanced["concerns"] = self.get_concerns()
        
        return enhanced
    
    def enhance_review(self, review_config: Dict) -> Dict:
        """
        行业化审核配置
        
        Args:
            review_config: 基础审核配置
        
        Returns:
            Dict: 增强后的配置
        """
        if not self._active_industry:
            return review_config
            
        enhanced = review_config.copy()
        
        # 添加行业标准
        enhanced["industry_standards"] = self.get_standards()
        
        # 添加审核关注点
        enhanced["review_concerns"] = self.get_concerns()
        
        # 添加术语检查
        enhanced["terminology_check"] = list(self._active_industry.terminology.keys())
        
        return enhanced
    
    def industry_inference(self, requirement: str) -> Dict[str, Any]:
        """
        行业推理
        
        根据需求推断行业信息并提供建议
        
        Args:
            requirement: 需求描述
        
        Returns:
            Dict: 推理结果
        """
        import re
        
        result = {
            "detected_industry": None,
            "confidence": 0.0,
            "suggested_doc_types": [],
            "suggested_standards": [],
            "suggested_concerns": [],
            "key_parameters": [],
            "missing_information": [],
        }
        
        # 尝试检测行业
        for name, config in INDUSTRY_CONFIGS.items():
            score = 0
            
            # 检查关键词
            keywords = [name] + config.aliases
            for kw in keywords:
                if kw in requirement:
                    score += 0.5
                    
            # 检查关注点
            for concern in config.concerns:
                if concern in requirement:
                    score += 0.2
                    
            if score > result["confidence"]:
                result["confidence"] = score
                result["detected_industry"] = config.name
                
                # 填充建议
                result["suggested_doc_types"] = config.common_doc_types[:3]
                result["suggested_standards"] = config.standards[:5]
                result["suggested_concerns"] = config.concerns[:5]
                result["key_parameters"] = config.key_parameters[:5]
                
        # 推断缺失信息
        if result["detected_industry"]:
            config = INDUSTRY_CONFIGS.get(result["detected_industry"], None)
            if config:
                # 检查需求中是否有规模信息
                scale_match = re.search(r"(\d+)\s*(?:万吨|万KW|万KWp|万吨/年)", requirement)
                if not scale_match:
                    result["missing_information"].append({
                        "field": "scale",
                        "description": "项目规模",
                        "hint": f"建议提供产能规模，如：年产X万吨",
                    })
                    
                # 检查是否有地点
                location_match = re.search(r"在([^省\s]+)", requirement)
                if not location_match:
                    result["missing_information"].append({
                        "field": "location",
                        "description": "项目地点",
                        "hint": "建议提供具体建设地点",
                    })
                    
        return result
    
    def search_industry_knowledge(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        检索行业知识
        
        Args:
            query: 查询内容
            top_k: 返回数量
        
        Returns:
            List[Dict]: 知识条目
        """
        results = []
        
        # 1. 从知识库检索
        if self.knowledge_base:
            try:
                kb_results = self.knowledge_base.search(
                    f"{self._active_industry.name} {query}" if self._active_industry else query,
                    top_k=top_k
                )
                
                for r in kb_results:
                    results.append({
                        "source": "knowledge_base",
                        "content": r.text[:500],
                        "score": r.score,
                        "metadata": r.metadata,
                    })
            except Exception as e:
                logger.debug(f"知识检索失败: {e}")
                
        # 2. 从行业配置中检索
        if self._active_industry:
            # 术语匹配
            for eng, chn in self._active_industry.terminology.items():
                if query.lower() in eng.lower() or query in chn:
                    results.append({
                        "source": "terminology",
                        "content": f"{eng} = {chn}",
                        "type": "term",
                    })
                    
            # 标准匹配
            for std in self._active_industry.standards:
                if query in std:
                    results.append({
                        "source": "standard",
                        "content": std,
                        "type": "standard",
                    })
                    
        return results[:top_k]
    
    def get_industry_report(self) -> Dict[str, Any]:
        """获取当前行业报告"""
        if not self._active_industry:
            return {"status": "inactive"}
            
        return {
            "status": "active",
            "industry": self._active_industry.name,
            "standards_count": len(self._active_industry.standards),
            "terminology_count": len(self._active_industry.terminology),
            "concerns": self._active_industry.concerns,
            "key_parameters": self._active_industry.key_parameters,
            "data_sources": list(self._active_industry.data_sources.keys()),
            "calculation_templates": self._active_industry.calculation_templates,
        }


# 全局实例
_enhancer: Optional[IndustryEnhancer] = None


def get_industry_enhancer() -> IndustryEnhancer:
    """获取全局行业增强器"""
    global _enhancer
    if _enhancer is None:
        _enhancer = IndustryEnhancer()
    return _enhancer


def quick_activate(industry_name: str) -> bool:
    """快速激活行业模式"""
    enhancer = get_industry_enhancer()
    return enhancer.activate(industry_name)


import re
