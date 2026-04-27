"""
行业分类体系（基于 GB/T 4754-2017 国民经济行业分类）
定期从政府公开数据更新
"""

from typing import Dict, List, Optional
from pathlib import Path
import json
import time

# GB/T 4754-2017 行业分类标准
INDUSTRY_CATEGORIES = {
    "A": {
        "name": "农、林、牧、渔业",
        "code": "A",
        "categories": ["01", "02", "03", "04", "05"]
    },
    "B": {
        "name": "采矿业",
        "code": "B",
        "categories": ["06", "07", "08", "09", "10", "11", "12"]
    },
    "C": {
        "name": "制造业",
        "code": "C",
        "categories": [str(i).zfill(2) for i in range(13, 44)]
    },
    "D": {
        "name": "电力、热力、燃气及水生产和供应业",
        "code": "D",
        "categories": ["44", "45", "46"]
    },
    "E": {
        "name": "建筑业",
        "code": "E",
        "categories": ["47", "48", "49", "50"]
    },
    "F": {
        "name": "批发和零售业",
        "code": "F",
        "categories": ["51", "52"]
    },
    "G": {
        "name": "交通运输、仓储和邮政业",
        "code": "G",
        "categories": ["53", "54", "55", "56", "57", "58", "59", "60"]
    },
    "H": {
        "name": "住宿和餐饮业",
        "code": "H",
        "categories": ["61", "62"]
    },
    "I": {
        "name": "信息传输、软件和信息技术服务业",
        "code": "I",
        "categories": ["63", "64", "65"]
    },
    "J": {
        "name": "金融业",
        "code": "J",
        "categories": ["66", "67", "68", "69"]
    },
    "K": {
        "name": "房地产业",
        "code": "K",
        "categories": ["70"]
    },
    "L": {
        "name": "租赁和商务服务业",
        "code": "L",
        "categories": ["71", "72"]
    },
    "M": {
        "name": "科学研究和技术服务业",
        "code": "M",
        "categories": ["73", "74", "75"]
    },
    "N": {
        "name": "水利、环境和公共设施管理业",
        "code": "N",
        "categories": ["76", "77", "78", "79"]
    },
    "O": {
        "name": "居民服务、修理和其他服务业",
        "code": "O",
        "categories": ["80", "81", "82"]
    },
    "P": {
        "name": "教育",
        "code": "P",
        "categories": ["83"]
    },
    "Q": {
        "name": "卫生和社会工作",
        "code": "Q",
        "categories": ["84", "85"]
    },
    "R": {
        "name": "文化、体育和娱乐业",
        "code": "R",
        "categories": ["86", "87", "88", "89", "90"]
    },
    "S": {
        "name": "公共管理、社会保障和社会组织",
        "code": "S",
        "categories": ["91", "92", "93", "94", "95", "96"]
    },
    "T": {
        "name": "国际组织",
        "code": "T",
        "categories": ["97"]
    }
}

# 职业分类（参考《中华人民共和国职业分类大典》）
OCCUPATION_CATEGORIES = {
    "professionals": {
        "name": "专业技术人员",
        "examples": ["工程师", "医师", "律师", "会计师", "教师", "研究员"]
    },
    "managers": {
        "name": "管理人员",
        "examples": ["企业高管", "项目经理", "部门主管", "行政管理人员"]
    },
    "service_workers": {
        "name": "社会生产服务和生活服务人员",
        "examples": ["销售员", "客服", "餐饮服务员", "物流配送员"]
    },
    "technicians": {
        "name": "生产制造及有关人员",
        "examples": ["技术工人", "设备操作员", "质量检测员"]
    },
    "farmers": {
        "name": "农、林、牧、渔业生产及辅助人员",
        "examples": ["农业技术人员", "养殖人员"]
    },
    "military": {
        "name": "军人",
        "examples": ["军官", "士兵"]
    },
    "others": {
        "name": "不便分类的其他从业人员",
        "examples": []
    }
}

# 专家角色与行业/职业的映射关系
EXPERT_INDUSTRY_MAPPING = {
    "environmental": {
        "primary_industry": "N",
        "related_industries": ["C", "E", "D"],
        "occupations": ["professionals"],
        "keywords": ["环保", "环境", "环评", "监测", "治理", "污染"]
    },
    "it": {
        "primary_industry": "I",
        "related_industries": ["M"],
        "occupations": ["professionals"],
        "keywords": ["软件", "编程", "开发", "IT", "信息", "数据"]
    },
    "finance": {
        "primary_industry": "J",
        "related_industries": ["K", "L"],
        "occupations": ["professionals", "managers"],
        "keywords": ["金融", "投资", "财务", "会计", "税务", "审计"]
    },
    "legal": {
        "primary_industry": "L",
        "related_industries": ["S"],
        "occupations": ["professionals"],
        "keywords": ["法律", "律师", "合同", "合规", "诉讼"]
    },
    "medical": {
        "primary_industry": "Q",
        "related_industries": ["M"],
        "occupations": ["professionals"],
        "keywords": ["医疗", "医生", "护士", "药品", "临床", "健康"]
    },
    "education": {
        "primary_industry": "P",
        "related_industries": ["M"],
        "occupations": ["professionals"],
        "keywords": ["教育", "教学", "培训", "课程", "学习"]
    },
    "engineering": {
        "primary_industry": "M",
        "related_industries": ["E", "C"],
        "occupations": ["professionals"],
        "keywords": ["工程", "设计", "施工", "建筑", "结构"]
    },
    "marketing": {
        "primary_industry": "L",
        "related_industries": ["F", "I"],
        "occupations": ["professionals", "managers"],
        "keywords": ["营销", "市场", "品牌", "推广", "广告", "新媒体"]
    }
}


class IndustryClassifier:
    """行业分类器 - 根据专家描述自动匹配行业分类"""
    
    def __init__(self):
        self.industry_data = INDUSTRY_CATEGORIES.copy()
        self.occupation_data = OCCUPATION_CATEGORIES.copy()
        self.expert_mapping = EXPERT_INDUSTRY_MAPPING.copy()
        self.last_update_check = 0
        self.update_interval = 86400  # 24小时检查一次更新
        
    def classify_expert(self, expert_description: str, expert_name: str = "") -> Dict:
        """
        根据专家描述和名称，自动分类到对应的行业和职业
        
        Args:
            expert_description: 专家描述或训练内容
            expert_name: 专家名称（可选）
            
        Returns:
            分类结果字典，包含行业代码、行业名称、职业类别
        """
        text = (expert_description + " " + expert_name).lower()
        
        # 1. 尝试通过预定义映射匹配
        for category, mapping in self.expert_mapping.items():
            keywords = mapping.get("keywords", [])
            if any(keyword in text for keyword in keywords):
                primary = mapping["primary_industry"]
                return {
                    "industry_code": primary,
                    "industry_name": self.industry_data[primary]["name"],
                    "related_industries": mapping.get("related_industries", []),
                    "occupations": mapping.get("occupations", []),
                    "match_type": "keyword",
                    "category": category
                }
        
        # 2. 通过行业关键词匹配（更细粒度的匹配）
        industry_scores = {}
        for code, data in self.industry_data.items():
            score = self._calculate_industry_relevance(text, code)
            if score > 0:
                industry_scores[code] = score
        
        if industry_scores:
            best_match = max(industry_scores.items(), key=lambda x: x[1])
            industry_code = best_match[0]
            return {
                "industry_code": industry_code,
                "industry_name": self.industry_data[industry_code]["name"],
                "related_industries": [],
                "occupations": ["professionals"],
                "match_type": "relevance",
                "score": best_match[1]
            }
        
        # 3. 默认分类：科学研究和技术服务业
        return {
            "industry_code": "M",
            "industry_name": "科学研究和技术服务业",
            "related_industries": [],
            "occupations": ["professionals"],
            "match_type": "default"
        }
    
    def _calculate_industry_relevance(self, text: str, industry_code: str) -> float:
        """计算文本与行业的相关性得分"""
        # 行业关键词映射（简化版，实际可以扩展）
        industry_keywords = {
            "A": ["农业", "种植", "养殖", "农场", "农产品"],
            "B": ["采矿", "矿山", "石油", "天然气", "煤炭"],
            "C": ["制造", "加工", "生产", "工厂", "产品"],
            "D": ["电力", "能源", "发电", "燃气", "供水"],
            "E": ["建筑", "施工", "工程", "装修", "建设"],
            "F": ["批发", "零售", "销售", "商贸", "电商"],
            "G": ["运输", "物流", "快递", "仓储", "交通"],
            "H": ["酒店", "餐饮", "住宿", "旅游", "饭店"],
            "I": ["软件", "互联网", "IT", "信息", "数据", "编程"],
            "J": ["金融", "银行", "保险", "投资", "证券"],
            "K": ["房地产", "物业", "地产", "楼盘"],
            "L": ["租赁", "商务", "咨询", "服务", "法律"],
            "M": ["科研", "技术", "研究", "开发", "设计"],
            "N": ["环保", "水利", "环境", "公共设施", "绿化"],
            "O": ["居民服务", "修理", "家政", "维修"],
            "P": ["教育", "学校", "培训", "教学", "老师"],
            "Q": ["医疗", "卫生", "医院", "健康", "医生"],
            "R": ["文化", "体育", "娱乐", "媒体", "艺术"],
            "S": ["政府", "公共管理", "社保", "社会组织"],
            "T": ["国际", "外交", "联合国"]
        }
        
        keywords = industry_keywords.get(industry_code, [])
        score = sum(1 for keyword in keywords if keyword in text)
        return score / len(keywords) if keywords else 0
    
    def get_industry_tree(self) -> Dict:
        """获取完整的行业分类树"""
        return {
            "categories": self.industry_data,
            "occupations": self.occupation_data,
            "last_update": time.time()
        }
    
    def check_for_updates(self) -> bool:
        """检查是否有新的行业分类标准（预留接口，可以从政府网站抓取更新）"""
        current_time = time.time()
        if current_time - self.last_update_check > self.update_interval:
            self.last_update_check = current_time
            # TODO: 实现从国家统计局网站自动更新行业分类
            return False
        return False
    
    def update_from_government_data(self) -> bool:
        """
        从政府公开数据更新行业分类
        数据来源：国家统计局 https://www.stats.gov.cn/sj/tjbz/gjtjjbz/
        """
        # TODO: 实现自动更新逻辑
        # 1. 访问国家统计局网站
        # 2. 下载最新的 GB/T 4754 标准
        # 3. 解析并更新 INDUSTRY_CATEGORIES
        # 4. 保存更新记录
        return False


# 全局分类器实例
_classifier_instance = None

def get_industry_classifier() -> IndustryClassifier:
    """获取行业分类器单例"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IndustryClassifier()
    return _classifier_instance


if __name__ == "__main__":
    # 测试代码
    classifier = get_industry_classifier()
    
    # 测试环保专家分类
    result = classifier.classify_expert(" environmental impact assessment expert ", "环评专家")
    print("环保专家分类结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 测试IT专家分类
    result = classifier.classify_expert("software developer with 10 years experience", "软件工程师")
    print("\nIT专家分类结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
