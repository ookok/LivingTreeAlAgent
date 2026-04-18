"""
用户画像解析器
从对话中实时构建和更新用户画像
"""

import json
import time
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


# ── 常量定义 ─────────────────────────────────────────────────────────

class ExpertiseLevel(str, Enum):
    """知识水平"""
    BEGINNER = "beginner"      # 初学者
    MEDIUM = "medium"          # 中等
    EXPERT = "expert"          # 专家


class DecisionStyle(str, Enum):
    """决策风格"""
    RISK_AVERSE = "risk_averse"        # 保守型
    RISK_TOLERANT = "risk_tolerant"   # 冒险型
    DATA_DRIVEN = "data_driven"        # 数据驱动
    COST_SENSITIVE = "cost_sensitive" # 成本敏感
    INTUITIVE = "intuitive"           # 直觉型


class CommunicationPreference(str, Enum):
    """沟通偏好"""
    CONCISE = "concise"       # 简洁
    DETAILED = "detailed"     # 详细
    ENCOURAGING = "encouraging"  # 鼓励式
    FORMAL = "formal"         # 正式


# 社会角色库
SOCIAL_ROLES = {
    "enterprise_manager": {"name": "企业管理者", "keywords": ["成本", "ROI", "投资回报", "盈利", "预算", "利润"]},
    "government_official": {"name": "政府官员", "keywords": ["法规", "合规", "审批", "政策", "监管", "标准", "文件"]},
    "engineer": {"name": "工程师", "keywords": ["技术", "参数", "方案", "实现", "系统", "架构", "性能"]},
    "researcher": {"name": "研究人员", "keywords": ["研究", "论文", "学术", "实验", "数据", "分析"]},
    "student": {"name": "学生", "keywords": ["学习", "考试", "作业", "课程", "毕业", "论文"]},
    "resident": {"name": "居民", "keywords": ["健康", "环境", "安全", "影响", "投诉", "担心"]},
    "investor": {"name": "投资者", "keywords": ["收益", "回报", "风险", "市场", "投资", "增长"]},
    "legal_professional": {"name": "法务人员", "keywords": ["法律", "条款", "合同", "责任", "权益", "纠纷"]},
}

EXPERTISE_LEVELS = {
    ExpertiseLevel.BEGINNER: {"name": "初学者", "indicators": ["什么是", "基础", "入门", "怎么用", "请解释"]},
    ExpertiseLevel.MEDIUM: {"name": "中等", "indicators": ["原理", "对比", "优化", "建议", "推荐"]},
    ExpertiseLevel.EXPERT: {"name": "专家", "indicators": ["API", "参数调优", "架构设计", "底层", "实现细节", "算法"]},
}

DECISION_STYLES = {
    DecisionStyle.RISK_AVERSE: {"name": "保守型", "keywords": ["风险", "安全", "稳妥", "保障", "万一"]},
    DecisionStyle.RISK_TOLERANT: {"name": "冒险型", "keywords": ["大胆", "激进", "突破", "尝试"]},
    DecisionStyle.DATA_DRIVEN: {"name": "数据驱动", "keywords": ["数据", "统计", "分析", "指标", "量化"]},
    DecisionStyle.COST_SENSITIVE: {"name": "成本敏感", "keywords": ["成本", "费用", "预算", "价格", "性价比"]},
}

COMMUNICATION_PREFERENCES = {
    CommunicationPreference.CONCISE: {"name": "简洁", "indicators": ["简短", "精炼", "要点", "结论先行"]},
    CommunicationPreference.DETAILED: {"name": "详细", "indicators": ["详细", "完整", "解释", "展开"]},
    CommunicationPreference.ENCOURAGING: {"name": "鼓励式", "indicators": ["加油", "没问题", "可以的", "支持"]},
}


# ── 数据模型 ─────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    name: str = ""
    
    # 社会角色（多选，带置信度）
    social_roles: Dict[str, float] = field(default_factory=dict)
    
    # 核心关切（权重 0-1）
    core_concerns: Dict[str, float] = field(default_factory=dict)
    
    # 知识水平
    expertise_level: str = ExpertiseLevel.MEDIUM.value
    
    # 决策风格
    decision_style: str = DecisionStyle.DATA_DRIVEN.value
    
    # 沟通偏好
    communication_preference: str = CommunicationPreference.DETAILED.value
    
    # 画像置信度
    confidence: float = 0.5
    
    # 更新时间
    updated_at: float = field(default_factory=time.time)
    
    # 对话统计
    message_count: int = 0
    total_tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(**data)
    
    def get_primary_role(self) -> Optional[str]:
        """获取最主要的角色"""
        if not self.social_roles:
            return None
        return max(self.social_roles.items(), key=lambda x: x[1])[0]
    
    def get_top_concerns(self, n: int = 3) -> List[str]:
        """获取最重要的关切"""
        sorted_concerns = sorted(self.core_concerns.items(), key=lambda x: x[1], reverse=True)
        return [c[0] for c in sorted_concerns[:n]]


# ── 用户画像解析器 ───────────────────────────────────────────────────

class UserProfileParser:
    """
    用户画像解析器
    从对话历史中实时分析和更新用户画像
    """
    
    def __init__(self, profile_db_path: Optional[Path] = None):
        self.profile_db_path = profile_db_path or self._get_default_db_path()
        self._profiles: Dict[str, UserProfile] = {}
        self._load_profiles()
    
    def _get_default_db_path(self) -> Path:
        """获取默认数据库路径"""
        from core.config import get_config_dir
        return get_config_dir() / "user_profiles.json"
    
    def _load_profiles(self):
        """加载已保存的画像"""
        if self.profile_db_path.exists():
            try:
                with open(self.profile_db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for uid, pdata in data.items():
                        self._profiles[uid] = UserProfile.from_dict(pdata)
            except Exception:
                pass
    
    def _save_profiles(self):
        """保存画像到磁盘"""
        self.profile_db_path.parent.mkdir(parents=True, exist_ok=True)
        data = {uid: p.to_dict() for uid, p in self._profiles.items()}
        with open(self.profile_db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_profile(self, user_id: str) -> UserProfile:
        """获取用户画像（不存在则创建新的）"""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
        return self._profiles[user_id]
    
    def parse_from_message(self, message: str, history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        从单条消息中解析用户特征（无需LLM，基于规则）
        
        Args:
            message: 用户消息
            history: 对话历史
            
        Returns:
            解析结果字典
        """
        message_lower = message.lower()
        results = {
            "likely_roles": [],
            "role_confidences": {},
            "primary_concerns": [],
            "concern_weights": {},
            "expertise_level": ExpertiseLevel.MEDIUM.value,
            "decision_style": DecisionStyle.DATA_DRIVEN.value,
            "communication_preference": CommunicationPreference.DETAILED.value,
            "confidence": 0.5,
            "reasoning": [],
        }
        
        # 1. 检测社会角色
        for role_id, role_info in SOCIAL_ROLES.items():
            matches = 0
            for keyword in role_info["keywords"]:
                if keyword in message_lower:
                    matches += 1
            if matches > 0:
                confidence = min(0.3 + matches * 0.2, 0.95)
                results["role_confidences"][role_id] = confidence
                results["likely_roles"].append(role_id)
                results["reasoning"].append(f"检测到角色关键词: {role_info['name']}")
        
        # 2. 检测核心关切
        concern_patterns = {
            "成本": ["成本", "费用", "价格", "预算", "钱", "贵", "便宜", "划算"],
            "风险": ["风险", "危险", "万一", "安全", "隐患", "担心", "怕"],
            "技术": ["技术", "参数", "性能", "配置", "方案", "实现", "优化"],
            "合规": ["法规", "合规", "标准", "规范", "审批", "许可", "要求"],
            "时间": ["时间", "工期", "进度", "多久", "周期", "效率"],
            "质量": ["质量", "品质", "效果", "性能", "好", "坏"],
            "环保": ["环保", "污染", "排放", "环境", "生态"],
            "市场": ["市场", "竞争", "份额", "需求", "客户", "销售"],
        }
        
        for concern, keywords in concern_patterns.items():
            matches = sum(1 for kw in keywords if kw in message_lower)
            if matches > 0:
                weight = min(0.4 + matches * 0.15, 0.95)
                results["concern_weights"][concern] = weight
                results["primary_concerns"].append(concern)
        
        # 3. 检测知识水平
        for level, info in EXPERTISE_LEVELS.items():
            matches = sum(1 for ind in info["indicators"] if ind in message_lower)
            if matches >= 2:
                results["expertise_level"] = level.value
                results["confidence"] = min(results["confidence"] + 0.15, 0.9)
                results["reasoning"].append(f"知识水平判定: {info['name']}")
                break
        
        # 4. 检测决策风格
        for style, info in DECISION_STYLES.items():
            matches = sum(1 for kw in info["keywords"] if kw in message_lower)
            if matches >= 2:
                results["decision_style"] = style.value
                results["reasoning"].append(f"决策风格判定: {info['name']}")
                break
        
        # 5. 检测沟通偏好
        for pref, info in COMMUNICATION_PREFERENCES.items():
            matches = sum(1 for ind in info["indicators"] if ind in message_lower)
            if matches >= 1:
                results["communication_preference"] = pref.value
                break
        
        # 6. 根据历史推断（如果提供了）
        if history:
            # 检查历史中是否有模式
            short_count = sum(1 for h in history[-5:] if len(h.get("content", "")) < 50)
            if short_count >= 3:
                results["communication_preference"] = CommunicationPreference.CONCISE.value
                results["reasoning"].append("历史显示偏好简短回复")
            
            # 检查是否有专业术语使用增加的趋势
            tech_count = sum(1 for h in history[-3:] if any(kw in h.get("content", "").lower() 
                for kw in ["api", "sdk", "算法", "协议", "架构"]))
            if tech_count >= 2:
                results["expertise_level"] = ExpertiseLevel.EXPERT.value
                results["reasoning"].append("历史显示较高的专业知识")
        
        # 计算总体置信度
        if results["likely_roles"]:
            results["confidence"] = min(results["confidence"] + 0.2, 0.85)
        if results["primary_concerns"]:
            results["confidence"] = min(results["confidence"] + 0.1, 0.9)
        
        return results
    
    async def parse_with_llm(self, message: str, history: List[Dict], 
                             hermes_agent=None) -> Dict[str, Any]:
        """
        使用 LLM 进行更深入的用户画像分析
        
        Args:
            message: 当前消息
            history: 对话历史
            hermes_agent: Hermes Agent 实例
            
        Returns:
            解析结果
        """
        if not hermes_agent:
            # 回退到规则解析
            return self.parse_from_message(message, history)
        
        prompt = f"""请从以下用户消息中分析其可能的社会角色、核心关切和知识水平：

消息：{message}
历史上下文：{json.dumps(history[-5:], ensure_ascii=False)}

请返回JSON格式：
{{
    "likely_roles": ["角色ID1", "角色ID2"],
    "primary_concerns": ["关切1", "关切2"],
    "expertise_level": "beginner|medium|expert",
    "decision_style": "risk_averse|data_driven|cost_sensitive|risk_tolerant|intuitive",
    "communication_preference": "concise|detailed|encouraging|formal",
    "confidence": 0.85,
    "reasoning": "分析理由"
}}

角色ID参考：
- enterprise_manager: 企业管理者
- government_official: 政府官员
- engineer: 工程师
- researcher: 研究人员
- student: 学生
- resident: 居民
- investor: 投资者
- legal_professional: 法务人员
"""
        
        try:
            # 调用 LLM
            response_text = ""
            for chunk in hermes_agent._llm_chat([{"role": "user", "content": prompt}]):
                if chunk.delta:
                    response_text += chunk.delta
            
            # 解析 JSON
            # 提取 JSON 部分
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
        except Exception as e:
            pass
        
        # 回退到规则解析
        return self.parse_from_message(message, history)
    
    def update_profile(self, user_id: str, parsed_result: Dict[str, Any]):
        """
        根据解析结果更新用户画像
        
        Args:
            user_id: 用户ID
            parsed_result: 解析结果
        """
        profile = self.get_profile(user_id)
        
        # 更新社会角色
        role_confidences = parsed_result.get("role_confidences", {})
        for role, conf in role_confidences.items():
            current = profile.social_roles.get(role, 0)
            # 指数移动平均
            profile.social_roles[role] = current * 0.7 + conf * 0.3
        
        # 更新核心关切
        concern_weights = parsed_result.get("concern_weights", {})
        for concern, weight in concern_weights.items():
            current = profile.core_concerns.get(concern, 0.5)
            profile.core_concerns[concern] = current * 0.6 + weight * 0.4
        
        # 更新其他属性（需要更高置信度才更新）
        if parsed_result.get("confidence", 0) > 0.6:
            if "expertise_level" in parsed_result:
                profile.expertise_level = parsed_result["expertise_level"]
            if "decision_style" in parsed_result:
                profile.decision_style = parsed_result["decision_style"]
            if "communication_preference" in parsed_result:
                profile.communication_preference = parsed_result["communication_preference"]
        
        # 更新统计
        profile.message_count += 1
        profile.confidence = min(profile.confidence + 0.02, 0.95)
        profile.updated_at = time.time()
        
        # 保存
        self._save_profiles()
    
    def record_feedback(self, user_id: str, feedback_type: str, expert_id: str):
        """
        记录用户反馈，用于优化画像
        
        Args:
            user_id: 用户ID
            feedback_type: "like" | "dislike"
            expert_id: 专家ID
        """
        profile = self.get_profile(user_id)
        
        if feedback_type == "like":
            # 正反馈：轻微提升置信度
            profile.confidence = min(profile.confidence + 0.05, 0.95)
        else:
            # 负反馈：调整画像方向
            profile.confidence = max(profile.confidence - 0.1, 0.3)
        
        profile.updated_at = time.time()
        self._save_profiles()
    
    def get_all_profiles(self) -> List[UserProfile]:
        """获取所有用户画像"""
        return list(self._profiles.values())
    
    def delete_profile(self, user_id: str):
        """删除用户画像"""
        if user_id in self._profiles:
            del self._profiles[user_id]
            self._save_profiles()
    
    def export_profile(self, user_id: str) -> Optional[Dict]:
        """导出用户画像为字典"""
        profile = self.get_profile(user_id)
        return profile.to_dict() if profile else None
    
    def import_profile(self, data: Dict):
        """导入用户画像"""
        profile = UserProfile.from_dict(data)
        self._profiles[profile.user_id] = profile
        self._save_profiles()
