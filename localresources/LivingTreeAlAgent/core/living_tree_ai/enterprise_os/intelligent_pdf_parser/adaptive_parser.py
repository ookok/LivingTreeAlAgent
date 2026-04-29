"""
自适应解析器 (Adaptive Parser)

针对不同检测公司的报告格式，构建专用解析规则。
随着使用积累，解析准确性越来越高。

核心思想：
1. 首次遇到新检测公司 → 通用LLM解析 + 人工校验
2. 记录该公司报告特征 → 建立专用解析规则
3. 下次遇到同公司报告 → 专用规则优先
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class CompanyProfile:
    """检测公司画像"""
    company_id: str
    company_name: str           # 公司全称
    short_names: List[str]     # 简称/缩写
    report_templates: List[str]  # 报告模板ID列表
    parsing_rules: Dict[str, Any]  # 解析规则
    field_mappings: Dict[str, str]  # 字段映射
    known_patterns: List[str]   # 已知的报告特征模式
    confidence_boost: float = 0.0  # 置信度加成

    # 统计
    total_parsed: int = 0
    successful_parsed: int = 0
    average_confidence: float = 0.0
    last_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "short_names": self.short_names,
            "report_templates": self.report_templates,
            "parsing_rules": self.parsing_rules,
            "field_mappings": self.field_mappings,
            "known_patterns": self.known_patterns,
            "confidence_boost": self.confidence_boost,
            "total_parsed": self.total_parsed,
            "successful_parsed": self.successful_parsed,
            "average_confidence": self.average_confidence,
            "last_used": self.last_used
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CompanyProfile":
        return cls(**data)


@dataclass
class ParsingFeedback:
    """解析反馈（用于优化）"""
    feedback_id: str
    company_id: str
    file_hash: str
    original_value: str        # AI解析的值
    corrected_value: str        # 用户修正的值
    field_key: str             # 字段名
    correction_type: str        # "replace" / "append" / "remove"
    corrected_by: str = ""
    corrected_at: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "company_id": self.company_id,
            "file_hash": self.file_hash,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "field_key": self.field_key,
            "correction_type": self.correction_type,
            "corrected_by": self.corrected_by,
            "corrected_at": self.corrected_at,
            "notes": self.notes
        }


# ==================== 自适应解析器 ====================

class AdaptiveParser:
    """
    自适应解析器

    工作流程：
    1. 识别检测公司
    2. 查找专用规则
    3. 通用LLM解析 + 规则增强
    4. 记录反馈，持续优化
    """

    # 内置常见检测公司
    BUILTIN_COMPANIES = {
        "中检集团": {
            "short_names": ["中检", "CCIC", "ccic"],
            "patterns": ["中国检验认证集团", "中检集团"],
            "field_mappings": {
                "委托单位": "company_name",
                "受检单位": "company_name",
                "报告编号": "report_id"
            }
        },
        "华测检测": {
            "short_names": ["华测", "CTI", "cti"],
            "patterns": ["华测检测认证集团", "CTI"],
            "field_mappings": {
                "委托方": "company_name",
                "客户名称": "company_name",
                "Report No": "report_id"
            }
        },
        "SGS": {
            "short_names": ["SGS", "sgs"],
            "patterns": ["SGS通标标准技术服务", "SGS-CSTC"],
            "field_mappings": {
                "Client": "company_name",
                "Report No": "report_id"
            }
        },
        "谱尼测试": {
            "short_names": ["谱尼", "PONY", "pony"],
            "patterns": ["谱尼测试集团", "PONY"],
            "field_mappings": {
                "委托单位": "company_name",
                "受检单位": "company_name"
            }
        },
        "国检集团": {
            "short_names": ["国检", "CTC", "ctc"],
            "patterns": ["中国建材检验认证集团", "CTC"],
            "field_mappings": {
                "委托单位": "company_name",
                "工程名称": "project_name"
            }
        },
        "广电计量": {
            "short_names": ["广电计量", "GRGT", "grgt"],
            "patterns": ["广电计量检测集团", "GRGT"],
            "field_mappings": {
                "委托方": "company_name",
                "客户名称": "company_name"
            }
        }
    }

    def __init__(self, profiles_dir: str = "parsing_profiles"):
        """
        初始化自适应解析器

        Args:
            profiles_dir: 公司画像存储目录
        """
        self._profiles_dir = Path(profiles_dir)
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

        self._company_profiles: Dict[str, CompanyProfile] = {}
        self._feedbacks: List[ParsingFeedback] = []

        # 加载内置公司
        self._load_builtin_companies()

        # 加载已保存的画像
        self._load_saved_profiles()

    def _load_builtin_companies(self):
        """加载内置公司"""
        for company_name, config in self.BUILTIN_COMPANIES.items():
            company_id = self._generate_company_id(company_name)
            profile = CompanyProfile(
                company_id=company_id,
                company_name=company_name,
                short_names=config["short_names"],
                known_patterns=config["patterns"],
                field_mappings=config["field_mappings"],
                parsing_rules={},
                report_templates=[]
            )
            self._company_profiles[company_id] = profile

    def _load_saved_profiles(self):
        """加载已保存的公司画像"""
        for path in self._profiles_dir.glob("*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                profile = CompanyProfile.from_dict(data)
                self._company_profiles[profile.company_id] = profile
            except Exception as e:
                logger.warning(f"加载画像失败 {path}: {e}")

    def _generate_company_id(self, company_name: str) -> str:
        """生成公司ID"""
        import hashlib
        return hashlib.md5(company_name.encode()).hexdigest()[:8]

    def _generate_feedback_id(self) -> str:
        """生成反馈ID"""
        import hashlib
        return hashlib.md5(str(datetime.now()).encode()).hexdigest()[:12]

    # ==================== 公共接口 ====================

    async def identify_company(
        self,
        text_content: str,
        llm_callable: Optional[Callable] = None
    ) -> Optional[CompanyProfile]:
        """
        识别检测公司

        Args:
            text_content: PDF文本内容
            llm_callable: LLM调用函数

        Returns:
            CompanyProfile 或 None
        """
        # 1. 快速正则匹配
        for company_id, profile in self._company_profiles.items():
            for pattern in profile.known_patterns:
                if pattern in text_content:
                    profile.last_used = datetime.now().isoformat()
                    return profile

        # 2. LLM智能识别
        if llm_callable:
            company_name = await self._llm_identify_company(text_content, llm_callable)
            if company_name:
                # 查找或创建公司画像
                return self.get_or_create_profile(company_name)

        return None

    async def _llm_identify_company(
        self,
        text_content: str,
        llm_callable: Callable
    ) -> Optional[str]:
        """使用LLM识别公司"""
        prompt = f"""从以下检测报告文本中识别是哪家检测公司。

文本内容（前1000字）：
{text_content[:1000]}

已知检测公司列表：
- 中检集团 (CCIC)
- 华测检测 (CTI)
- SGS
- 谱尼测试
- 国检集团 (CTC)
- 广电计量 (GRGT)
- 其他

请只返回公司名称，如果不在列表中返回"未知"。
只返回公司名称，不要有其他内容。"""

        try:
            response = await llm_callable(prompt)
            company_name = response.strip()
            if company_name and company_name != "未知":
                return company_name
        except Exception as e:
            logger.warning(f"LLM公司识别失败: {e}")

        return None

    def get_or_create_profile(self, company_name: str) -> CompanyProfile:
        """
        获取或创建公司画像

        Args:
            company_name: 公司名称

        Returns:
            CompanyProfile
        """
        # 查找现有画像
        for profile in self._company_profiles.values():
            if (profile.company_name == company_name or
                company_name in profile.short_names):
                return profile

        # 创建新画像
        company_id = self._generate_company_id(company_name)
        profile = CompanyProfile(
            company_id=company_id,
            company_name=company_name,
            short_names=[],
            known_patterns=[],
            field_mappings={},
            parsing_rules={},
            report_templates=[]
        )
        self._company_profiles[company_id] = profile
        return profile

    async def parse_with_profile(
        self,
        text_content: str,
        company: CompanyProfile,
        llm_callable: Optional[Callable] = None,
        base_prompt: str = ""
    ) -> Dict[str, Any]:
        """
        使用公司画像增强解析

        Args:
            text_content: PDF文本内容
            company: 公司画像
            llm_callable: LLM调用函数
            base_prompt: 基础提示词

        Returns:
            增强后的解析结果
        """
        # 构建增强提示词
        enhanced_prompt = self._build_enhanced_prompt(
            text_content,
            company,
            base_prompt
        )

        # 调用LLM
        if llm_callable:
            response = await llm_callable(enhanced_prompt)
            try:
                return json.loads(response)
            except:
                return {}

        return {}

    def _build_enhanced_prompt(
        self,
        text_content: str,
        company: CompanyProfile,
        base_prompt: str
    ) -> str:
        """构建增强提示词"""
        # 截断
        max_chars = 6000  # 更短，因为要留空间给规则
        truncated_text = text_content[:max_chars]

        # 添加公司特定提示
        company_hint = f"""
额外提示（针对 {company.company_name} 的报告）：
- 字段映射：{json.dumps(company.field_mappings, ensure_ascii=False)}
- 已知模式：{', '.join(company.known_patterns[:3])}
"""

        if company.confidence_boost > 0:
            company_hint += f"- 该公司报告解析准确率较高，可适当提高置信度\n"

        prompt = f"""{base_prompt}

{company_hint}
"""

        # 替换占位符
        prompt = prompt.replace("{text_content}", truncated_text)

        return prompt

    def record_feedback(self, feedback: ParsingFeedback):
        """
        记录解析反馈

        Args:
            feedback: 解析反馈
        """
        self._feedbacks.append(feedback)

        # 更新公司画像
        if feedback.company_id in self._company_profiles:
            profile = self._company_profiles[feedback.company_id]
            profile.total_parsed += 1

            # 分析修正类型，更新规则
            self._update_profile_from_feedback(profile, feedback)

            # 保存
            self._save_profile(profile)

    def _update_profile_from_feedback(
        self,
        profile: CompanyProfile,
        feedback: ParsingFeedback
    ):
        """从反馈更新画像"""
        # 更新统计
        profile.successful_parsed += 1
        if profile.total_parsed > 0:
            profile.average_confidence = (
                profile.average_confidence * (profile.total_parsed - 1) + 0.9
            ) / profile.total_parsed

        # 如果是字段映射问题，更新映射
        if feedback.correction_type == "replace":
            field_key = feedback.field_key
            # 尝试识别正确的字段名
            if feedback.corrected_value and feedback.corrected_value not in profile.field_mappings.values():
                # 添加反向映射
                for k, v in list(profile.field_mappings.items()):
                    if v == field_key:
                        profile.field_mappings[k] = feedback.field_key

    def _save_profile(self, profile: CompanyProfile):
        """保存画像"""
        path = self._profiles_dir / f"{profile.company_id}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)

    def get_all_profiles(self) -> List[CompanyProfile]:
        """获取所有公司画像"""
        return list(self._company_profiles.values())

    def get_profile_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._company_profiles)
        total_parsed = sum(p.total_parsed for p in self._company_profiles.values())
        avg_confidence = (
            sum(p.average_confidence * p.total_parsed for p in self._company_profiles.values())
            / max(1, total_parsed)
        )

        return {
            "total_companies": total,
            "total_parsed": total_parsed,
            "average_confidence": avg_confidence,
            "builtin_companies": len(self.BUILTIN_COMPANIES),
            "custom_companies": total - len(self.BUILTIN_COMPANIES)
        }

    async def learn_from_correction(
        self,
        company_name: str,
        field_key: str,
        ai_value: str,
        corrected_value: str,
        file_content: str = ""
    ):
        """
        从修正中学习

        Args:
            company_name: 公司名称
            field_key: 字段名
            ai_value: AI解析值
            corrected_value: 修正值
            file_content: 文件内容（用于提取模式）
        """
        # 获取或创建画像
        profile = self.get_or_create_profile(company_name)

        # 记录反馈
        feedback = ParsingFeedback(
            feedback_id=self._generate_feedback_id(),
            company_id=profile.company_id,
            file_hash="",
            original_value=ai_value,
            corrected_value=corrected_value,
            field_key=field_key,
            correction_type="replace",
            corrected_at=datetime.now().isoformat()
        )

        self.record_feedback(feedback)

        # 如果是新公司，提取特征模式
        if file_content and not profile.known_patterns:
            # 简单提取：公司名称周围的上下文
            import re
            patterns = []
            for short_name in profile.short_names[:2]:
                matches = re.findall(f'.{{0,30}}{short_name}.{{0,30}}', file_content)
                if matches:
                    patterns.append(matches[0][:50])

            if patterns:
                profile.known_patterns.extend(patterns[:3])
                self._save_profile(profile)


# ==================== 便捷函数 ====================

_adaptive_parser: Optional[AdaptiveParser] = None


def get_adaptive_parser(profiles_dir: str = "parsing_profiles") -> AdaptiveParser:
    """获取自适应解析器单例"""
    global _adaptive_parser
    if _adaptive_parser is None:
        _adaptive_parser = AdaptiveParser(profiles_dir)
    return _adaptive_parser