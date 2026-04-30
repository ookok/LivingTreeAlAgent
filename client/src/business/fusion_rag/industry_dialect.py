"""
行业方言词典模块 (Industry Dialect Dictionary)

实现针对特定地域/企业的非标术语管理：
1. 收集本地企业常用的非标术语（如特定产线的俗称）
2. 建立同义词库，避免本地知识因称呼不同而被忽略
3. 支持动态扩展和导入/导出

核心原则：让系统理解"行业方言"，避免知识盲区
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class DialectEntry:
    """方言条目"""
    alias: str
    standard_term: str
    industry: str
    region: str = ""  # 地域标识，如"南京"
    source: str = "unknown"  # 来源：人工录入、自动发现、用户反馈
    confidence: float = 1.0  # 置信度
    usage_count: int = 0  # 使用次数


@dataclass
class DialectStatistics:
    """方言统计"""
    total_entries: int = 0
    by_industry: Dict[str, int] = field(default_factory=dict)
    by_region: Dict[str, int] = field(default_factory=dict)
    total_lookups: int = 0
    hit_count: int = 0


class IndustryDialectDict:
    """
    行业方言词典
    
    管理特定地域/企业的非标术语：
    - 南京行业方言
    - 特定产线俗称
    - 企业内部术语
    """
    
    def __init__(self):
        # 方言条目存储
        self.entries: Dict[str, List[DialectEntry]] = {}  # alias -> [entries]
        
        # 反向索引：标准术语 -> 别名列表
        self.reverse_index: Dict[str, List[str]] = {}
        
        # 统计信息
        self.stats = DialectStatistics()
        
        # 内置南京地区工业方言
        self._load_nanjing_dialect()
        
        print("[IndustryDialectDict] 初始化完成")
    
    def _load_nanjing_dialect(self):
        """加载南京地区工业方言"""
        nanjing_entries = [
            # 机械制造
            ("南机", "南京机床厂", "机械制造", "南京", "builtin", 1.0),
            ("华电", "南京华电集团", "能源", "南京", "builtin", 1.0),
            ("十四所", "中国电子科技集团公司第十四研究所", "电子电气", "南京", "builtin", 1.0),
            ("南钢", "南京钢铁集团", "冶金", "南京", "builtin", 1.0),
            
            # 特定产线俗称
            ("A线", "一号生产线", "通用", "南京", "builtin", 0.9),
            ("B线", "二号生产线", "通用", "南京", "builtin", 0.9),
            ("老线", "旧生产线", "通用", "南京", "builtin", 0.8),
            ("新线", "新生产线", "通用", "南京", "builtin", 0.8),
            
            # 本地企业简称
            ("熊猫", "南京熊猫电子股份有限公司", "电子电气", "南京", "builtin", 1.0),
            ("金城", "金城集团有限公司", "机械制造", "南京", "builtin", 1.0),
            ("晨光", "南京晨光集团有限责任公司", "机械制造", "南京", "builtin", 1.0),
            
            # 技术术语变体
            ("数车", "数控车床", "机械制造", "南京", "builtin", 0.95),
            ("铣床", "数控铣床", "机械制造", "南京", "builtin", 0.95),
            ("加工中心", "数控加工中心", "机械制造", "南京", "builtin", 0.95),
            
            # 化工行业
            ("扬子", "扬子石化", "化工", "南京", "builtin", 1.0),
            ("金陵石化", "中国石化金陵分公司", "化工", "南京", "builtin", 1.0),
            
            # 汽车行业
            ("南汽", "南京汽车集团", "汽车", "南京", "builtin", 1.0),
            ("上汽大通", "上汽大通汽车有限公司", "汽车", "南京", "builtin", 1.0),
            
            # 医疗行业
            ("省人民", "江苏省人民医院", "医疗", "南京", "builtin", 1.0),
            ("鼓楼医院", "南京大学医学院附属鼓楼医院", "医疗", "南京", "builtin", 1.0)
        ]
        
        for alias, standard, industry, region, source, confidence in nanjing_entries:
            self.add_entry(alias, standard, industry, region, source, confidence)
    
    def add_entry(self, alias: str, standard_term: str, industry: str,
                 region: str = "", source: str = "manual", confidence: float = 1.0):
        """
        添加方言条目
        
        Args:
            alias: 别名/方言术语
            standard_term: 标准术语
            industry: 所属行业
            region: 地域
            source: 来源
            confidence: 置信度
        """
        entry = DialectEntry(
            alias=alias,
            standard_term=standard_term,
            industry=industry,
            region=region,
            source=source,
            confidence=confidence
        )
        
        # 添加到主索引
        if alias not in self.entries:
            self.entries[alias] = []
        self.entries[alias].append(entry)
        
        # 添加到反向索引
        if standard_term not in self.reverse_index:
            self.reverse_index[standard_term] = []
        if alias not in self.reverse_index[standard_term]:
            self.reverse_index[standard_term].append(alias)
        
        # 更新统计
        self.stats.total_entries += 1
        self.stats.by_industry[industry] = self.stats.by_industry.get(industry, 0) + 1
        if region:
            self.stats.by_region[region] = self.stats.by_region.get(region, 0) + 1
    
    def lookup(self, term: str, industry: str = "通用", 
              region: str = "") -> Optional[str]:
        """
        查找方言对应的标准术语
        
        Args:
            term: 输入术语
            industry: 行业过滤
            region: 地域过滤
            
        Returns:
            标准术语，或 None
        """
        self.stats.total_lookups += 1
        
        # 精确匹配
        if term in self.entries:
            entries = self.entries[term]
            
            # 按行业和地域过滤
            filtered = []
            for entry in entries:
                if industry and entry.industry != industry and industry != "通用":
                    continue
                if region and entry.region != region:
                    continue
                filtered.append(entry)
            
            if filtered:
                # 选择置信度最高的
                filtered.sort(key=lambda x: x.confidence, reverse=True)
                best_entry = filtered[0]
                best_entry.usage_count += 1
                self.stats.hit_count += 1
                return best_entry.standard_term
        
        return None
    
    def expand_query(self, query: str, industry: str = "通用",
                    region: str = "") -> List[str]:
        """
        将查询中的方言术语扩展为标准术语和所有可能的别名
        
        Args:
            query: 原始查询
            industry: 行业
            region: 地域
            
        Returns:
            扩展后的查询列表（包含原始查询）
        """
        queries = [query]
        original_query = query
        
        # 查找所有可能的方言术语
        for alias, entries in self.entries.items():
            if alias in query:
                # 找到匹配的方言
                for entry in entries:
                    if industry and entry.industry != industry and industry != "通用":
                        continue
                    if region and entry.region != region:
                        continue
                    
                    # 替换为标准术语
                    expanded = query.replace(alias, entry.standard_term)
                    if expanded != query and expanded not in queries:
                        queries.append(expanded)
                    
                    # 添加包含标准术语的变体
                    if entry.standard_term not in query:
                        variant = f"{query} {entry.standard_term}"
                        if variant not in queries:
                            queries.append(variant)
        
        return queries
    
    def get_aliases(self, standard_term: str) -> List[str]:
        """
        获取标准术语的所有别名
        
        Args:
            standard_term: 标准术语
            
        Returns:
            别名列表
        """
        return self.reverse_index.get(standard_term, [])
    
    def remove_entry(self, alias: str, standard_term: Optional[str] = None):
        """
        删除方言条目
        
        Args:
            alias: 别名
            standard_term: 标准术语（可选，用于精确删除）
        """
        if alias not in self.entries:
            return
        
        if standard_term:
            # 精确删除特定条目
            self.entries[alias] = [
                e for e in self.entries[alias] 
                if e.standard_term != standard_term
            ]
            # 清理空列表
            if not self.entries[alias]:
                del self.entries[alias]
        else:
            # 删除所有该别名的条目
            del self.entries[alias]
        
        # 更新统计
        self.stats.total_entries = sum(len(entries) for entries in self.entries.values())
    
    def import_from_json(self, json_data: str):
        """
        从JSON导入方言数据
        
        Args:
            json_data: JSON格式的方言数据
        """
        try:
            data = json.loads(json_data)
            
            for entry in data:
                self.add_entry(
                    alias=entry["alias"],
                    standard_term=entry["standard_term"],
                    industry=entry.get("industry", "通用"),
                    region=entry.get("region", ""),
                    source=entry.get("source", "imported"),
                    confidence=entry.get("confidence", 1.0)
                )
            
            print(f"[IndustryDialectDict] 导入了 {len(data)} 条方言条目")
        except Exception as e:
            print(f"[IndustryDialectDict] 导入失败: {e}")
    
    def export_to_json(self) -> str:
        """导出方言数据为JSON"""
        data = []
        
        for alias, entries in self.entries.items():
            for entry in entries:
                data.append({
                    "alias": entry.alias,
                    "standard_term": entry.standard_term,
                    "industry": entry.industry,
                    "region": entry.region,
                    "source": entry.source,
                    "confidence": entry.confidence,
                    "usage_count": entry.usage_count
                })
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def suggest_aliases(self, text: str, industry: str = "通用") -> List[Tuple[str, str]]:
        """
        从文本中识别可能需要添加的方言术语
        
        Args:
            text: 输入文本
            industry: 目标行业
            
        Returns:
            [(疑似方言, 建议标准术语)] 列表
        """
        suggestions = []
        
        # 简单规则：识别可能是企业简称的词
        patterns = [
            # 两个字的可能简称
            r'([\u4e00-\u9fa5]{2})(集团|公司|股份)?',
            # 特定前缀
            r'(南|北|东|西)([\u4e00-\u9fa5]{1,2})'
        ]
        
        import re
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    term = ''.join(match)
                else:
                    term = match
                
                # 检查是否已经存在
                if term not in self.entries:
                    # 建议标准术语（直接使用原词）
                    suggestions.append((term, term))
        
        return list(set(suggestions))  # 去重
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_entries": self.stats.total_entries,
            "total_lookups": self.stats.total_lookups,
            "hit_count": self.stats.hit_count,
            "hit_rate": self.stats.hit_count / max(self.stats.total_lookups, 1) * 100,
            "by_industry": dict(self.stats.by_industry),
            "by_region": dict(self.stats.by_region)
        }


def create_industry_dialect_dict() -> IndustryDialectDict:
    """创建行业方言词典实例"""
    return IndustryDialectDict()


# 预设的行业方言数据
PRESET_DIALECTS = {
    "南京": {
        "机械制造": [
            ("南机", "南京机床厂"),
            ("数车", "数控车床"),
            ("加工中心", "数控加工中心")
        ],
        "电子电气": [
            ("十四所", "中国电子科技集团公司第十四研究所"),
            ("熊猫", "南京熊猫电子股份有限公司")
        ],
        "化工": [
            ("扬子", "扬子石化"),
            ("金陵石化", "中国石化金陵分公司")
        ],
        "汽车": [
            ("南汽", "南京汽车集团"),
            ("上汽大通", "上汽大通汽车有限公司")
        ]
    },
    "通用": {
        "通用": [
            ("A线", "一号生产线"),
            ("B线", "二号生产线"),
            ("老线", "旧生产线"),
            ("新线", "新生产线")
        ]
    }
}


__all__ = [
    "IndustryDialectDict",
    "DialectEntry",
    "DialectStatistics",
    "create_industry_dialect_dict",
    "PRESET_DIALECTS"
]