"""
Question Sanitizer - 问题脱敏器

自动识别并处理用户问题中的敏感信息：
1. 个人隐私（姓名、电话、邮箱、地址）
2. 公司机密（内部项目名、机密数据）
3. 账号密钥（API Key、密码、Token）
4. 泛化处理（将具体问题抽象为通用问题）
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib


@dataclass
class SanitizedQuestion:
    """脱敏后的问题"""
    original: str                          # 原始问题
    sanitized: str                         # 脱敏后的问题
    substitutions: Dict[str, str] = field(default_factory=dict)  # 替换映射
    privacy_level: str = "low"             # 隐私等级: low/medium/high
    generalization_suggestions: List[str] = field(default_factory=list)  # 泛化建议
    sanitized_at: datetime = field(default_factory=datetime.now)


class QuestionSanitizer:
    """
    问题脱敏器

    自动识别并替换：
    - 手机号码、邮箱
    - 姓名、地址
    - API密钥、密码
    - 内部项目名、服务器IP
    """

    # 隐私模式配置
    PRIVACY_PATTERNS = {
        # 手机号码
        "phone": [
            r'1[3-9]\d{9}',  # 中国手机号
            r'\d{3,4}[-\s]?\d{7,8}',  # 固定电话
            r'\+\d{1,3}[-\s]?\d{6,12}',  # 国际电话
        ],
        # 邮箱
        "email": [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        ],
        # 姓名（常见姓氏+名字）
        "name": [
            r'([\u4e00-\u9fa5]{2,3})(先生|女士|同学|经理|总监|总裁|CEO|CTO|CFO|COO)',
            r'([A-Z][a-z]+)\s+([A-Z][a-z]+)',  # 英文名
        ],
        # 地址
        "address": [
            r'[\u4e00-\u9fa5]{1,10}(省|市|区|县)[^\s]{1,30}(路|街|道|巷|号)',
            r'[\u4e00-\u9fa5]{1,10}大厦\d+层',
            r'[\u4e00-\u9fa5]{1,10}(花园|小区|公寓|别墅)',
        ],
        # IP地址
        "ip": [
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+',
        ],
        # API密钥/Token
        "api_key": [
            r'api[_-]?key["\s:=]+["\']?[a-zA-Z0-9_-]{20,}',
            r'secret[_-]?key["\s:=]+["\']?[a-zA-Z0-9_-]{20,}',
            r'token["\s:=]+["\']?[a-zA-Z0-9_-]{20,}',
            r'bearer["\s]+[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',
            r'sk-[a-zA-Z0-9]{32,}',  # OpenAI API Key格式
        ],
        # 密码
        "password": [
            r'password["\s:=]+["\']?[^\s"\']{6,}',
            r'pwd["\s:=]+["\']?[^\s"\']{6,}',
            r'passwd["\s:=]+["\']?[^\s"\']{6,}',
        ],
        # 数据库连接
        "db_connection": [
            r'mongodb://[^\s]+',
            r'mysql://[^\s]+',
            r'postgresql://[^\s]+',
            r'redis://[^\s]+',
        ],
        # 公司内部项目名（常见模式）
        "internal_project": [
            r'(项目|project)[_\s]*(代号|代码|名称)[：:][^\s,，]+',
            r'[A-Z]{2,10}[-_]?\d{4,}',  # 内部项目代码
        ],
        # 身份证号
        "id_card": [
            r'\d{17}[\dXx]',
        ],
    }

    # 泛化映射表
    GENERALIZATION_MAP = {
        # 手机/邮箱 -> 通用占位符
        "phone": "手机号码",
        "email": "邮箱地址",
        "name": "相关人员",
        "address": "具体地址",
        "ip": "服务器IP",
        "api_key": "API密钥",
        "password": "账户密码",
        "db_connection": "数据库连接",
        "internal_project": "内部项目",
        "id_card": "身份证号",
    }

    def __init__(self):
        self.compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译所有正则表达式"""
        for category, patterns in self.PRIVACY_PATTERNS.items():
            self.compiled_patterns[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def sanitize(self, question: str) -> SanitizedQuestion:
        """
        对问题进行脱敏处理

        Args:
            question: 原始问题

        Returns:
            SanitizedQuestion: 脱敏后的问题
        """
        sanitized = question
        substitutions = {}
        detected_types = []

        # 遍历所有模式进行替换
        for category, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(sanitized)
                for match in matches:
                    placeholder = self._generate_placeholder(category, match)
                    sanitized = sanitized.replace(str(match), placeholder)
                    substitutions[placeholder] = self.GENERALIZATION_MAP.get(category, category)
                    if category not in detected_types:
                        detected_types.append(category)

        # 评估隐私等级
        privacy_level = self._assess_privacy_level(detected_types)

        # 生成泛化建议
        suggestions = self._generate_generalization_suggestions(question, detected_types)

        return SanitizedQuestion(
            original=question,
            sanitized=sanitized,
            substitutions=substitutions,
            privacy_level=privacy_level,
            generalization_suggestions=suggestions
        )

    def _generate_placeholder(self, category: str, original: str) -> str:
        """生成占位符"""
        # 使用类别+哈希前6位，确保同内容生成相同占位符
        content_hash = hashlib.md5(str(original).encode()).hexdigest()[:6]
        return f"[{category.upper()}_{content_hash}]"

    def _assess_privacy_level(self, detected_types: List[str]) -> str:
        """评估隐私等级"""
        if not detected_types:
            return "low"

        # 高敏感类别
        high_risk = {"api_key", "password", "db_connection", "id_card"}
        medium_risk = {"phone", "email", "name", "internal_project"}

        if any(t in high_risk for t in detected_types):
            return "high"
        elif any(t in medium_risk for t in detected_types):
            return "medium"
        return "low"

    def _generate_generalization_suggestions(
        self,
        question: str,
        detected_types: List[str]
    ) -> List[str]:
        """生成泛化建议"""
        suggestions = []

        if "phone" in detected_types or "email" in detected_types:
            suggestions.append("建议将联系方式替换为「联系我」或「官方渠道」")

        if "name" in detected_types:
            suggestions.append("建议将具体人名替换为「某工程师」或「项目成员」")

        if "address" in detected_types:
            suggestions.append("建议将具体地址替换为「某地区」或「某园区」")

        if "ip" in detected_types:
            suggestions.append("建议将IP替换为「服务器A」或「内网机器」")

        if "api_key" in detected_types or "password" in detected_types:
            suggestions.append("敏感凭证切勿外泄！建议用环境变量代替")

        if "internal_project" in detected_types:
            suggestions.append("建议将内部项目名替换为通用描述（如「内部系统」）")

        if "db_connection" in detected_types:
            suggestions.append("数据库连接信息不应公开，建议描述为「生产数据库」")

        if not suggestions:
            suggestions.append("问题本身不包含明显隐私信息，可直接提问")

        return suggestions

    def generalize_for_platform(
        self,
        sanitized: str,
        platform: str,
        question_type: str
    ) -> str:
        """
        针对特定平台进一步泛化问题

        Args:
            sanitized: 已脱敏的问题
            platform: 目标平台 (stackoverflow/zhihu/github)
            question_type: 问题类型

        Returns:
            平台适配后的问题
        """
        result = sanitized

        # StackOverflow: 需要更技术化、精确的描述
        if platform == "stackoverflow":
            # 移除口语化表达
            result = re.sub(r'急急急急急急+', '问题如下', result)
            result = re.sub(r'跪求', '求助', result)
            result = re.sub(r'在线等', '', result)
            # 添加技术标签暗示（如果问题中有）
            if any(kw in result.lower() for kw in ['python', 'java', 'js', 'react']):
                pass  # 保留，可能用于标签

        # 知乎: 可以更口语化、叙述性
        elif platform == "zhihu":
            # 可以更随意一些
            result = re.sub(r'\[.+?\]', '某个', result)  # 简化占位符

        # GitHub Issue: 需要精确的错误信息+复现步骤
        elif platform == "github":
            result = re.sub(r'\[.+?\]', '', result)  # 移除所有占位符
            result = result.strip()

        return result

    def extract_search_keywords(self, sanitized: str) -> List[str]:
        """
        从脱敏问题中提取搜索关键词

        Args:
            sanitized: 脱敏后的问题

        Returns:
            关键词列表
        """
        # 移除占位符
        cleaned = re.sub(r'\[.+?\]', '', sanitized)

        # 移除常见停用词
        stopwords = {
            '的', '了', '在', '是', '我', '有', '和', '就',
            '不', '人', '都', '一', '一个', '上', '也', '很',
            '到', '说', '要', '去', '你', '会', '着', '没有',
            '这', '那', '什么', '怎么', '如何', '为什么', '请问',
            '帮忙', '帮助', '求助', '帮忙', '急', '跪求'
        }

        # 简单分词（基于正则）
        words = re.findall(r'[\w\u4e00-\u9fa5]+', cleaned)

        # 过滤停用词和短词
        keywords = [w for w in words if w not in stopwords and len(w) >= 2]

        # 提取技术术语（保留括号内容）
        tech_terms = re.findall(r'\(([^)]+)\)', cleaned)
        keywords.extend(tech_terms)

        # 去重
        return list(dict.fromkeys(keywords))[:10]  # 最多10个关键词
