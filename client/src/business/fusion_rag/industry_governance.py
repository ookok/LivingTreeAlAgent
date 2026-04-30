"""
行业知识治理模块 (Industry Knowledge Governance)

实现从源头保证知识质量的闭环治理体系：
1. 数据准入与清洗策略
2. 元数据 tagging
3. 术语归一化

核心原则：宁可召回不足，不可幻觉泛滥

集成共享基础设施：
- 统一术语模型：使用共享的 Term 类
- 事件总线：发布治理相关事件
- 缓存层：缓存术语映射和标签
- DeepKE-LLM：智能术语抽取和关系构建
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime

# 导入共享基础设施
from client.src.business.shared import (
    Term,
    EventBus,
    CacheLayer,
    get_event_bus,
    get_cache,
    EVENTS
)

# 导入 DeepKE 术语抽取器
from .deepke_term_extractor import get_term_extractor, get_dict_builder


@dataclass
class DocumentTag:
    """文档标签"""
    industry_domain: str = ""
    application_scenario: str = ""
    timeliness: str = "current"  # current, valid, outdated
    authority_level: int = 1  # 1-5, higher is more authoritative
    source_type: str = "unknown"  # gb/t, technical_manual, patent, paper, internal


@dataclass
class DocumentFilter:
    """文档过滤器配置"""
    whitelist_sources: List[str] = field(default_factory=lambda: [
        "gb/t", "行标", "技术手册", "专利", "权威论文", "内部项目文档"
    ])
    blacklist_sources: List[str] = field(default_factory=lambda: [
        "通用百科", "新闻", "论坛帖子", "博客", "社交媒体"
    ])
    min_authority_level: int = 2
    allow_outdated: bool = False


class IndustryGovernance:
    """
    行业知识治理核心模块
    
    负责从源头保证知识库的行业相关性和质量：
    - 数据准入控制
    - 元数据标签管理
    - 术语归一化
    - 智能术语抽取（基于 DeepKE-LLM）
    
    集成共享基础设施：
    - 统一术语模型：使用共享的 Term 类存储术语
    - 事件总线：发布术语添加、文档验证等事件
    - 缓存层：缓存术语映射，提升查询性能
    - DeepKE-LLM：智能术语抽取和关系构建
    """
    
    def __init__(self):
        # 获取共享基础设施
        self.event_bus = get_event_bus()
        self.cache = get_cache()
        
        # DeepKE-LLM 术语抽取器
        self.term_extractor = get_term_extractor()
        self.dict_builder = get_dict_builder()
        
        # 行业术语表（使用统一的 Term 模型）
        self.term_tables: Dict[str, Dict[str, Term]] = {}
        
        # 文档标签缓存
        self.document_tags: Dict[str, DocumentTag] = {}
        
        # 来源白名单/黑名单
        self.filter = DocumentFilter()
        
        # 行业领域定义
        self.industry_domains = {
            "机械制造": ["机械设计", "加工工艺", "设备维护", "公差配合"],
            "电子电气": ["电路设计", "PLC", "嵌入式", "电机控制"],
            "化工": ["化工工艺", "材料科学", "安全规范", "反应工程"],
            "汽车": ["汽车设计", "动力系统", "自动驾驶", "新能源"],
            "医疗": ["医疗器械", "诊断技术", "药品研发", "医疗设备"],
            "能源": ["电力系统", "新能源", "储能技术", "智能电网"],
            "建筑": ["结构设计", "施工技术", "BIM", "绿色建筑"],
            "物流": ["供应链", "仓储管理", "运输优化", "物联网"]
        }
        
        # 权威等级映射
        self.authority_levels = {
            "国家标准": 5,
            "行业标准": 4,
            "企业标准": 3,
            "权威论文": 4,
            "专利文献": 4,
            "技术手册": 3,
            "内部文档": 2,
            "普通文档": 1
        }
        
        # 统计
        self.total_docs_checked = 0
        self.passed_docs = 0
        self.rejected_docs = 0
        
        # 加载预置术语
        self._load_preset_terms()
        
        print("[IndustryGovernance] 初始化完成（已集成统一术语模型、事件总线、缓存层、DeepKE-LLM）")
    
    def _load_preset_terms(self):
        """加载预置行业术语"""
        preset_terms = {
            "机械制造": [
                ("马达", "电机"), ("光尺", "激光位移传感器"), ("PLC", "可编程逻辑控制器"),
                ("CNC", "数控加工"), ("CAD", "计算机辅助设计"), ("CAM", "计算机辅助制造"),
                ("FEM", "有限元分析"), ("公差", "公差配合"), ("主轴", "主轴组件")
            ],
            "电子电气": [
                ("MCU", "微控制器"), ("FPGA", "现场可编程门阵列"), ("PCB", "印制电路板"),
                ("IoT", "物联网"), ("AIoT", "人工智能物联网"), ("BLE", "蓝牙低功耗"),
                ("UART", "通用异步收发传输器"), ("I2C", "集成电路总线"), ("SPI", "串行外设接口")
            ],
            "化工": [
                ("PLC", "可编程逻辑控制器"), ("PID", "比例积分微分控制"), ("DCS", "分布式控制系统"),
                ("SCADA", "数据采集与监控系统"), ("P&ID", "管道及仪表流程图"), ("HMI", "人机界面")
            ],
            "汽车": [
                ("ECU", "电子控制单元"), ("ABS", "防抱死制动系统"), ("ESP", "电子稳定程序"),
                ("EV", "电动汽车"), ("BEV", "纯电动汽车"), ("HEV", "混合动力汽车"),
                ("ADAS", "高级驾驶辅助系统"), ("V2X", "车对外界信息交换")
            ],
            "能源": [
                ("PV", "光伏发电"), ("Wind", "风力发电"), ("BESS", "电池储能系统"),
                ("EMS", "能源管理系统"), ("SCADA", "数据采集与监控系统"), ("DER", "分布式能源资源")
            ]
        }
        
        for industry, terms in preset_terms.items():
            for dialect, standard in terms:
                self.add_term(dialect, standard, industry)
    
    def add_term(self, dialect_term: str, standard_term: str, industry: str = "通用"):
        """
        添加术语（使用统一术语模型）
        
        Args:
            dialect_term: 方言/别名
            standard_term: 标准术语
            industry: 行业领域
        """
        # 使用统一的 Term 模型
        term = Term(
            dialect_term=dialect_term,
            standard_term=standard_term,
            source_file="preset",
            confidence=1.0,
            term_type="设备",
            industry=industry
        )
        
        # 存储到术语表
        if industry not in self.term_tables:
            self.term_tables[industry] = {}
        self.term_tables[industry][dialect_term] = term
        
        # 缓存术语
        cache_key = f"term:{industry}:{dialect_term}"
        self.cache.set(cache_key, term.to_dict())
        
        # 发布术语添加事件
        self.event_bus.publish(EVENTS["TERM_ADDED"], {
            "term": term.to_dict(),
            "timestamp": datetime.now().isoformat()
        })
        
        print(f"[IndustryGovernance] 添加术语: {dialect_term} -> {standard_term} ({industry})")
    
    def normalize_term(self, term: str, industry: str) -> str:
        """
        术语归一化（使用统一术语模型和缓存）
        
        Args:
            term: 原始术语
            industry: 目标行业
            
        Returns:
            标准化后的术语
        """
        # 先从缓存查找
        cache_key = f"term:{industry}:{term}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached.get("standard_term", term)
        
        # 从术语表查找
        if industry in self.term_tables:
            term_obj = self.term_tables[industry].get(term)
            if term_obj:
                return term_obj.standard_term
        
        # 如果行业表中没有，尝试通用表
        if "通用" in self.term_tables:
            term_obj = self.term_tables["通用"].get(term)
            if term_obj:
                return term_obj.standard_term
        
        return term
    
    def normalize_query(self, query: str, industry: str) -> str:
        """
        对查询进行术语归一化处理（使用统一术语模型）
        
        Args:
            query: 原始查询
            industry: 目标行业
            
        Returns:
            归一化后的查询
        """
        if industry not in self.term_tables:
            return query
        
        normalized = query
        for dialect_term, term_obj in self.term_tables[industry].items():
            normalized = normalized.replace(dialect_term, term_obj.standard_term)
        
        return normalized
    
    def load_synonym_table(self, industry: str, synonyms: Dict[str, str]):
        """
        加载行业同义词表（向后兼容）
        
        Args:
            industry: 行业名称
            synonyms: 同义词映射 {"术语": "标准术语"}
        """
        for dialect_term, standard_term in synonyms.items():
            self.add_term(dialect_term, standard_term, industry)
        print(f"[IndustryGovernance] 加载 {industry} 同义词 {len(synonyms)} 条")
    
    def extract_terms_from_text(self, text: str, industry: str = "通用") -> List[Dict[str, Any]]:
        """
        使用 DeepKE-LLM 从文本中智能抽取术语
        
        Args:
            text: 输入文本
            industry: 目标行业
            
        Returns:
            抽取的术语列表，包含术语名称、类别、定义等
        """
        # 异步调用术语抽取器
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        terms = loop.run_until_complete(self.term_extractor.extract_terms(text, industry))
        loop.close()
        
        result = []
        for term in terms:
            result.append({
                "term": term.term,
                "category": term.category,
                "definition": term.definition,
                "confidence": term.confidence
            })
        
        return result
    
    def extract_relations_from_text(self, text: str, industry: str = "通用") -> List[Dict[str, Any]]:
        """
        使用 DeepKE-LLM 从文本中抽取术语关系
        
        Args:
            text: 输入文本
            industry: 目标行业
            
        Returns:
            抽取的关系列表
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        relations = loop.run_until_complete(self.term_extractor.extract_relations(text, industry))
        loop.close()
        
        result = []
        for rel in relations:
            result.append({
                "term1": rel.term1,
                "relation_type": rel.relation_type,
                "term2": rel.term2,
                "confidence": rel.confidence
            })
        
        return result
    
    def build_industry_dictionary(self, documents: List[str], industry: str, 
                                  export_path: str = None) -> Dict[str, Any]:
        """
        使用 DeepKE-LLM 从文档集合构建行业词典
        
        Args:
            documents: 文档列表
            industry: 行业名称
            export_path: 导出路径（可选）
            
        Returns:
            行业词典
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        dictionary = loop.run_until_complete(
            self.dict_builder.build_and_export(documents, industry, export_path)
        )
        loop.close()
        
        # 将抽取的术语添加到术语表
        for term_name, term_info in dictionary.get("terms", {}).items():
            if term_info.get("confidence", 0) > 0.7:
                standard_term = term_info.get("category", term_name)
                self.add_term(term_name, standard_term, industry)
        
        return dictionary
    
    def update_dictionary_from_docs(self, documents: List[str], industry: str):
        """
        从新文档更新行业词典
        
        Args:
            documents: 新文档列表
            industry: 行业名称
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.dict_builder.update_existing_dict(self, documents, industry))
        loop.close()
    
    def generate_term_definition(self, term: str, industry: str) -> str:
        """
        使用 DeepKE-LLM 为术语生成定义
        
        Args:
            term: 术语名称
            industry: 行业领域
            
        Returns:
            术语定义
        """
        return self.term_extractor.generate_term_definition(term, industry)
    
    def extract_source_type(self, doc_title: str, doc_content: str) -> str:
        """
        自动识别文档来源类型
        
        Args:
            doc_title: 文档标题
            doc_content: 文档内容
            
        Returns:
            来源类型标识
        """
        title = doc_title.lower()
        
        # 国标/行标
        if re.search(r'gb/t\s*\d+', title) or re.search(r'国家标准', title):
            return "gb/t"
        
        # 专利
        if "专利" in title or "patent" in title:
            return "patent"
        
        # 技术手册
        if "手册" in title or "manual" in title:
            return "technical_manual"
        
        # 论文
        if "论文" in title or "paper" in title or "论文" in doc_content[:500]:
            return "paper"
        
        # 内部文档
        if "内部" in title or "internal" in title.lower():
            return "internal"
        
        return "unknown"
    
    def assess_authority(self, source_type: str, doc_title: str) -> int:
        """
        评估文档权威等级
        
        Args:
            source_type: 来源类型
            doc_title: 文档标题
            
        Returns:
            权威等级 (1-5)
        """
        # 根据来源类型
        for level_name, level in self.authority_levels.items():
            if level_name in doc_title:
                return level
        
        # 默认根据类型
        type_levels = {
            "gb/t": 5,
            "patent": 4,
            "technical_manual": 3,
            "paper": 4,
            "internal": 2
        }
        
        return type_levels.get(source_type, 1)
    
    def check_source_whitelist(self, source: str) -> bool:
        """
        检查来源是否在白名单中
        
        Args:
            source: 来源描述
            
        Returns:
            True if allowed, False otherwise
        """
        source_lower = source.lower()
        
        # 检查黑名单
        for black in self.filter.blacklist_sources:
            if black.lower() in source_lower:
                return False
        
        # 检查白名单（如果配置了）
        if self.filter.whitelist_sources:
            for white in self.filter.whitelist_sources:
                if white.lower() in source_lower:
                    return True
            return False
        
        return True
    
    def tag_document(self, doc_id: str, doc_title: str, doc_content: str, 
                    source: str = "unknown") -> DocumentTag:
        """
        为文档生成完整的元数据标签
        
        Args:
            doc_id: 文档ID
            doc_title: 文档标题
            doc_content: 文档内容
            source: 来源描述
            
        Returns:
            DocumentTag 对象
        """
        tag = DocumentTag()
        
        # 识别来源类型
        tag.source_type = self.extract_source_type(doc_title, doc_content)
        
        # 评估权威等级
        tag.authority_level = self.assess_authority(tag.source_type, doc_title)
        
        # 识别行业领域
        tag.industry_domain = self._detect_industry_domain(doc_title, doc_content)
        
        # 识别适用场景
        tag.application_scenario = self._detect_scenario(doc_title, doc_content)
        
        # 判断时效性
        tag.timeliness = self._assess_timeliness(doc_title, doc_content)
        
        # 缓存标签
        self.document_tags[doc_id] = tag
        
        return tag
    
    def _detect_industry_domain(self, title: str, content: str) -> str:
        """
        检测文档所属行业领域
        
        Args:
            title: 文档标题
            content: 文档内容
            
        Returns:
            行业领域名称
        """
        text = (title + " " + content).lower()
        
        for domain, keywords in self.industry_domains.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    return domain
        
        return "通用"
    
    def _detect_scenario(self, title: str, content: str) -> str:
        """
        检测文档适用场景
        
        Args:
            title: 文档标题
            content: 文档内容
            
        Returns:
            场景描述
        """
        text = title + " " + content
        
        scenario_keywords = {
            "设计": ["设计", "选型", "方案"],
            "维护": ["维护", "维修", "故障排除"],
            "工艺": ["工艺", "加工", "制造"],
            "安全": ["安全", "规范", "标准"],
            "检测": ["检测", "测试", "检验"],
            "安装": ["安装", "调试", "部署"]
        }
        
        for scenario, keywords in scenario_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return scenario
        
        return "综合"
    
    def _assess_timeliness(self, title: str, content: str) -> str:
        """
        评估文档时效性
        
        Args:
            title: 文档标题
            content: 文档内容
            
        Returns:
            timeliness 标识 (current, valid, outdated)
        """
        # 查找年份
        year_pattern = r'(20\d{2})'
        years = re.findall(year_pattern, title + " " + content)
        
        if years:
            latest_year = max(int(y) for y in years)
            current_year = datetime.now().year
            
            if latest_year >= current_year - 2:
                return "current"
            elif latest_year >= current_year - 10:
                return "valid"
            else:
                return "outdated"
        
        # 检查是否有修订日期
        if "修订" in title or "更新" in title:
            return "current"
        
        return "valid"
    
    def validate_document(self, doc_id: str, doc_title: str, doc_content: str, 
                         source: str = "unknown") -> Dict[str, Any]:
        """
        完整验证文档是否符合准入标准
        
        Args:
            doc_id: 文档ID
            doc_title: 文档标题
            doc_content: 文档内容
            source: 来源描述
            
        Returns:
            {
                "passed": bool,
                "reason": str,
                "tag": DocumentTag (if passed)
            }
        """
        self.total_docs_checked += 1
        
        # 检查来源白名单
        if not self.check_source_whitelist(source):
            self.rejected_docs += 1
            return {
                "passed": False,
                "reason": f"来源不在白名单: {source}"
            }
        
        # 生成标签
        tag = self.tag_document(doc_id, doc_title, doc_content, source)
        
        # 检查权威等级
        if tag.authority_level < self.filter.min_authority_level:
            self.rejected_docs += 1
            return {
                "passed": False,
                "reason": f"权威等级不足: {tag.authority_level} < {self.filter.min_authority_level}"
            }
        
        # 检查时效性
        if not self.filter.allow_outdated and tag.timeliness == "outdated":
            self.rejected_docs += 1
            return {
                "passed": False,
                "reason": "文档已过期"
            }
        
        self.passed_docs += 1
        return {
            "passed": True,
            "reason": "验证通过",
            "tag": tag
        }
    
    def get_document_tag(self, doc_id: str) -> Optional[DocumentTag]:
        """获取文档标签"""
        return self.document_tags.get(doc_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取治理统计信息"""
        return {
            "total_docs_checked": self.total_docs_checked,
            "passed_docs": self.passed_docs,
            "rejected_docs": self.rejected_docs,
            "pass_rate": self.passed_docs / max(self.total_docs_checked, 1) * 100,
            "active_industries": list(self.synonym_tables.keys()),
            "total_synonyms": sum(len(syn) for syn in self.synonym_tables.values())
        }


# 工业领域默认同义词表
DEFAULT_INDUSTRY_SYNONYMS = {
    "机械制造": {
        "马达": "电机",
        "PLC": "可编程控制器",
        "CNC": "数控机床",
        "公差": "公差配合",
        "加工中心": "数控加工中心",
        "轴承": "滚动轴承",
        "齿轮": "齿轮传动",
        "液压": "液压系统",
        "气动": "气动系统",
        "夹具": "工装夹具"
    },
    "电子电气": {
        "MCU": "微控制器",
        "PCB": "印制电路板",
        "MOS管": "场效应管",
        "IGBT": "绝缘栅双极晶体管",
        "继电器": "电磁继电器",
        "变频器": "变频驱动器",
        "伺服": "伺服电机",
        "传感器": "传感元件"
    },
    "化工": {
        "反应器": "反应釜",
        "精馏塔": "蒸馏塔",
        "换热器": "热交换器",
        "泵": "离心泵",
        "阀门": "控制阀",
        "催化剂": "催化材料",
        "溶剂": "有机溶剂"
    },
    "汽车": {
        "ECU": "电子控制单元",
        "ESP": "电子稳定程序",
        "ABS": "防抱死制动系统",
        "动力电池": "锂离子电池",
        "充电桩": "充电设施",
        "自动驾驶": "智能驾驶",
        "ADAS": "高级驾驶辅助系统"
    },
    "能源": {
        "光伏": "太阳能光伏发电",
        "风电": "风力发电",
        "储能": "储能系统",
        "逆变器": "并网逆变器",
        "充电桩": "电动汽车充电",
        "智能电网": "电网智能化"
    }
}


def create_industry_governance() -> IndustryGovernance:
    """创建行业治理实例并加载默认同义词"""
    governance = IndustryGovernance()
    
    # 加载默认行业同义词
    for industry, synonyms in DEFAULT_INDUSTRY_SYNONYMS.items():
        governance.load_synonym_table(industry, synonyms)
    
    return governance


__all__ = [
    "IndustryGovernance",
    "DocumentTag",
    "DocumentFilter",
    "DEFAULT_INDUSTRY_SYNONYMS",
    "create_industry_governance"
]