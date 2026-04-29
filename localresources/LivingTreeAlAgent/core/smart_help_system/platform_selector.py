"""
Platform Selector - 平台选择器

根据问题特征自动选择最合适的提问平台：
- StackOverflow: 技术编程问题
- 知乎: 概念理解、经验分享
- GitHub: Bug报告、功能建议
- CSDN/博客园: 中文技术问题
- Reddit: 社区讨论
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


class Platform(Enum):
    """支持的目标平台"""
    STACKOVERFLOW = "stackoverflow"
    ZHIHU = "zhihu"
    GITHUB = "github"
    CSDN = "csdn"
    BLOGGER = "blogger"  # 博客园
    REDDIT = "reddit"
    V2EX = "v2ex"
    CHATGPT = "chatgpt"  # AI社区


class QuestionType(Enum):
    """问题类型"""
    # 编程相关
    BUG_REPORT = "bug_report"           # Bug报告
    ERROR_DEBUG = "error_debug"          # 错误调试
    CODE_OPTIMIZATION = "code_optim"    # 代码优化
    API_USAGE = "api_usage"              # API使用
    FRAMEWORK_QUESTION = "framework"    # 框架问题
    LANGUAGE_QUESTION = "language"      # 语言问题
    DATABASE_QUESTION = "database"      # 数据库问题
    DEVOPS_QUESTION = "devops"          # DevOps问题

    # 非编程
    CONCEPT_UNDERSTAND = "concept"       # 概念理解
    TOOL_RECOMMEND = "tool_recommend"   # 工具推荐
    CAREER_ADVICE = "career"           # 职业建议
    PROJECT_IDEA = "project_idea"       # 项目思路

    # 其他
    GENERAL = "general"                  # 通用问题
    UNKNOWN = "unknown"                 # 未知


@dataclass
class PlatformInfo:
    """平台信息"""
    platform: Platform
    name: str
    url: str
    language: str  # zh/en
    specialties: List[str]
    response_time: str  # 平均响应时间
    quality_score: float  # 答案质量评分 0-10
    community_size: str  # 社区规模


@dataclass
class SelectionResult:
    """平台选择结果"""
    primary_platform: Platform
    alternative_platforms: List[Platform]
    question_type: QuestionType
    confidence: float  # 选择置信度 0-1
    reasoning: str
    suggested_tags: List[str]


class PlatformSelector:
    """
    平台选择器

    根据问题内容自动判断：
    1. 问题类型（Bug/调试/概念/工具推荐...）
    2. 最合适平台
    3. 备选平台列表
    """

    # 平台数据库
    PLATFORMS: Dict[Platform, PlatformInfo] = {
        Platform.STACKOVERFLOW: PlatformInfo(
            platform=Platform.STACKOVERFLOW,
            name="Stack Overflow",
            url="https://stackoverflow.com",
            language="en",
            specialties=["编程问题", "错误调试", "代码优化", "API使用"],
            response_time="几分钟~几小时",
            quality_score=9.0,
            community_size="千万级"
        ),
        Platform.ZHIHU: PlatformInfo(
            platform=Platform.ZHIHU,
            name="知乎",
            url="https://www.zhihu.com",
            language="zh",
            specialties=["概念理解", "经验分享", "职业发展", "工具推荐"],
            response_time="几小时~几天",
            quality_score=7.5,
            community_size="亿级"
        ),
        Platform.GITHUB: PlatformInfo(
            platform=Platform.GITHUB,
            name="GitHub Issues",
            url="https://github.com",
            language="en",
            specialties=["Bug报告", "功能建议", "开源项目问题"],
            response_time="几天~几周",
            quality_score=8.0,
            community_size="亿级"
        ),
        Platform.CSDN: PlatformInfo(
            platform=Platform.CSDN,
            name="CSDN",
            url="https://www.csdn.net",
            language="zh",
            specialties=["技术问题", "中文博客", "教程分享"],
            response_time="几小时~几天",
            quality_score=6.5,
            community_size="千万级"
        ),
        Platform.BLOGGER: PlatformInfo(
            platform=Platform.BLOGGER,
            name="博客园",
            url="https://www.cnblogs.com",
            language="zh",
            specialties=["技术博客", "经验总结", "问题讨论"],
            response_time="几天~几周",
            quality_score=7.0,
            community_size="百万级"
        ),
        Platform.REDDIT: PlatformInfo(
            platform=Platform.REDDIT,
            name="Reddit",
            url="https://www.reddit.com",
            language="en",
            specialties=["社区讨论", "技术新闻", "开源项目"],
            response_time="几分钟~几小时",
            quality_score=7.5,
            community_size="亿级"
        ),
        Platform.V2EX: PlatformInfo(
            platform=Platform.V2EX,
            name="V2EX",
            url="https://www.v2ex.com",
            language="zh",
            specialties=["程序员社区", "工具推荐", "创意讨论"],
            response_time="几分钟~几小时",
            quality_score=7.5,
            community_size="百万级"
        ),
        Platform.CHATGPT: PlatformInfo(
            platform=Platform.CHATGPT,
            name="ChatGPT AI社区",
            url="https://community.openai.com",
            language="en",
            specialties=["AI问题", "GPT使用", "Prompt工程"],
            response_time="几分钟~几小时",
            quality_score=8.0,
            community_size="百万级"
        ),
    }

    # 问题类型关键词映射
    QUESTION_TYPE_PATTERNS: Dict[QuestionType, List[str]] = {
        QuestionType.BUG_REPORT: [
            "bug", "崩溃", "闪退", "异常退出", "报错", "crash",
            "segmentation fault", "core dumped"
        ],
        QuestionType.ERROR_DEBUG: [
            "错误", "exception", "error", "调试", "debug",
            "怎么解决", "如何解决", "怎么处理", "怎么办"
        ],
        QuestionType.CODE_OPTIMIZATION: [
            "优化", "性能", "卡顿", "慢", "optimize", "performance",
            "加快", "提升速度", "重构", "refactor"
        ],
        QuestionType.API_USAGE: [
            "api", "接口", "sdk", "调用", "如何使用", "怎么用",
            "使用教程", "example", "demo"
        ],
        QuestionType.FRAMEWORK_QUESTION: [
            "django", "flask", "react", "vue", "spring", "springboot",
            "框架", "nextjs", "nuxt", "angular"
        ],
        QuestionType.LANGUAGE_QUESTION: [
            "python", "java", "javascript", "typescript", "golang",
            "rust", "c++", "c#", "ruby", "php", "语言"
        ],
        QuestionType.DATABASE_QUESTION: [
            "数据库", "mysql", "postgresql", "mongodb", "redis",
            "sql", "查询", "索引", "优化", "迁移"
        ],
        QuestionType.DEVOPS_QUESTION: [
            "docker", "kubernetes", "k8s", "ci/cd", "jenkins",
            "部署", "运维", "服务器", "nginx", "linux"
        ],
        QuestionType.CONCEPT_UNDERSTAND: [
            "是什么", "什么意思", "理解", "概念", "原理",
            "how does work", "what is", "区别", "对比"
        ],
        QuestionType.TOOL_RECOMMEND: [
            "推荐", "哪个好", "比较好", "有什么", "工具",
            "recommend", "alternative", "替代", "vs", "比较"
        ],
        QuestionType.CAREER_ADVICE: [
            "职业", "发展", "前景", "薪资", "面试", "简历",
            "career", "job", "interview", "offer"
        ],
        QuestionType.PROJECT_IDEA: [
            "项目", "想法", "创意", "思路", "方案",
            "project", "idea", "how to build", "从头开始"
        ],
    }

    # 问题类型到平台的映射
    TYPE_TO_PLATFORM_SCORES: Dict[QuestionType, Dict[Platform, float]] = {
        QuestionType.ERROR_DEBUG: {
            Platform.STACKOVERFLOW: 0.95,
            Platform.CSDN: 0.70,
            Platform.GITHUB: 0.50,
            Platform.ZHIHU: 0.30,
        },
        QuestionType.BUG_REPORT: {
            Platform.GITHUB: 0.90,
            Platform.STACKOVERFLOW: 0.60,
            Platform.CSDN: 0.50,
        },
        QuestionType.CODE_OPTIMIZATION: {
            Platform.STACKOVERFLOW: 0.90,
            Platform.CSDN: 0.65,
            Platform.ZHIHU: 0.50,
        },
        QuestionType.API_USAGE: {
            Platform.STACKOVERFLOW: 0.85,
            Platform.CSDN: 0.70,
            Platform.GITHUB: 0.50,
        },
        QuestionType.FRAMEWORK_QUESTION: {
            Platform.STACKOVERFLOW: 0.85,
            Platform.GITHUB: 0.70,
            Platform.CSDN: 0.65,
        },
        QuestionType.LANGUAGE_QUESTION: {
            Platform.STACKOVERFLOW: 0.90,
            Platform.CSDN: 0.60,
            Platform.ZHIHU: 0.50,
        },
        QuestionType.DATABASE_QUESTION: {
            Platform.STACKOVERFLOW: 0.90,
            Platform.CSDN: 0.75,
            Platform.GITHUB: 0.40,
        },
        QuestionType.DEVOPS_QUESTION: {
            Platform.STACKOVERFLOW: 0.85,
            Platform.V2EX: 0.60,
            Platform.REDDIT: 0.55,
            Platform.CSDN: 0.60,
        },
        QuestionType.CONCEPT_UNDERSTAND: {
            Platform.ZHIHU: 0.90,
            Platform.STACKOVERFLOW: 0.60,
            Platform.BLOGGER: 0.55,
        },
        QuestionType.TOOL_RECOMMEND: {
            Platform.ZHIHU: 0.85,
            Platform.V2EX: 0.75,
            Platform.REDDIT: 0.65,
        },
        QuestionType.CAREER_ADVICE: {
            Platform.ZHIHU: 0.95,
            Platform.V2EX: 0.60,
            Platform.REDDIT: 0.50,
        },
        QuestionType.PROJECT_IDEA: {
            Platform.ZHIHU: 0.85,
            Platform.REDDIT: 0.70,
            Platform.V2EX: 0.65,
        },
        QuestionType.GENERAL: {
            Platform.STACKOVERFLOW: 0.60,
            Platform.ZHIHU: 0.60,
            Platform.CSDN: 0.50,
        },
    }

    # 语言偏好平台
    CHINESE_PLATFORMS = {
        Platform.ZHIHU, Platform.CSDN, Platform.BLOGGER, Platform.V2EX
    }
    ENGLISH_PLATFORMS = {
        Platform.STACKOVERFLOW, Platform.GITHUB, Platform.REDDIT, Platform.CHATGPT
    }

    def select(
        self,
        question: str,
        preferred_language: Optional[str] = None,
        preferred_platforms: Optional[List[Platform]] = None
    ) -> SelectionResult:
        """
        选择最合适平台

        Args:
            question: 问题内容
            preferred_language: 语言偏好 (zh/en/auto)
            preferred_platforms: 优先平台列表

        Returns:
            SelectionResult: 选择结果
        """
        # 1. 判断问题类型
        question_type = self._classify_question(question)

        # 2. 判断语言
        language = self._detect_language(question, preferred_language)

        # 3. 获取候选平台
        candidates = self._get_candidate_platforms(question_type, language, preferred_platforms)

        # 4. 计算平台得分
        platform_scores = self._calculate_scores(question, question_type, candidates)

        # 5. 选择最佳平台
        sorted_platforms = sorted(platform_scores.items(), key=lambda x: x[1], reverse=True)

        primary = sorted_platforms[0][0] if sorted_platforms else Platform.STACKOVERFLOW
        alternatives = [p for p, _ in sorted_platforms[1:4]]  # 取前3个备选

        # 6. 生成标签建议
        tags = self._suggest_tags(question, question_type)

        # 7. 生成推理说明
        reasoning = self._generate_reasoning(question_type, primary, language)

        confidence = sorted_platforms[0][1] if sorted_platforms else 0.5

        return SelectionResult(
            primary_platform=primary,
            alternative_platforms=alternatives,
            question_type=question_type,
            confidence=confidence,
            reasoning=reasoning,
            suggested_tags=tags
        )

    def _classify_question(self, question: str) -> QuestionType:
        """分类问题类型"""
        scores: Dict[QuestionType, int] = {}

        for qtype, patterns in self.QUESTION_TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if pattern.lower() in question.lower():
                    score += 1
            if score > 0:
                scores[qtype] = score

        if not scores:
            return QuestionType.UNKNOWN

        # 返回得分最高的类型
        return max(scores.items(), key=lambda x: x[1])[0]

    def _detect_language(
        self,
        question: str,
        preferred: Optional[str]
    ) -> str:
        """检测问题语言"""
        if preferred and preferred != "auto":
            return preferred

        # 统计中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', question))
        total_chars = len(re.findall(r'[\w\u4e00-\u9fa5]', question))

        if total_chars == 0:
            return "en"

        chinese_ratio = chinese_chars / total_chars

        if chinese_ratio > 0.3:
            return "zh"
        return "en"

    def _get_candidate_platforms(
        self,
        question_type: QuestionType,
        language: str,
        preferred: Optional[List[Platform]]
    ) -> List[Platform]:
        """获取候选平台列表"""
        candidates = set()

        # 添加用户偏好
        if preferred:
            candidates.update(preferred)

        # 添加类型相关平台
        if question_type in self.TYPE_TO_PLATFORM_SCORES:
            candidates.update(self.TYPE_TO_PLATFORM_SCORES[question_type].keys())

        # 按语言过滤
        if language == "zh":
            candidates = candidates & self.CHINESE_PLATFORMS
        else:
            candidates = candidates & self.ENGLISH_PLATFORMS

        # 确保至少有候选
        if not candidates:
            if language == "zh":
                return [Platform.CSDN, Platform.ZHIHU]
            return [Platform.STACKOVERFLOW]

        return list(candidates)

    def _calculate_scores(
        self,
        question: str,
        question_type: QuestionType,
        candidates: List[Platform]
    ) -> Dict[Platform, float]:
        """计算平台得分"""
        scores = {}

        # 获取类型基础分
        type_scores = self.TYPE_TO_PLATFORM_SCORES.get(question_type, {})

        for platform in candidates:
            base_score = type_scores.get(platform, 0.5)

            # 乘以平台质量系数
            platform_info = self.PLATFORMS.get(platform)
            if platform_info:
                quality_factor = platform_info.quality_score / 10.0
                scores[platform] = base_score * quality_factor
            else:
                scores[platform] = base_score

        return scores

    def _suggest_tags(self, question: str, question_type: QuestionType) -> List[str]:
        """建议标签"""
        tags = []

        # 从问题中提取技术关键词
        tech_keywords = {
            'python', 'java', 'javascript', 'typescript', 'react', 'vue',
            'angular', 'django', 'flask', 'spring', 'springboot',
            'mysql', 'mongodb', 'redis', 'docker', 'kubernetes',
            'linux', 'windows', 'macos', 'git', 'github',
            'api', 'http', 'json', 'xml', 'html', 'css',
            'machine learning', 'deep learning', 'nlp', 'ai',
        }

        question_lower = question.lower()
        for keyword in tech_keywords:
            if keyword in question_lower:
                tags.append(keyword)

        # 根据问题类型添加标签
        type_tags = {
            QuestionType.ERROR_DEBUG: ['debugging', 'error-handling'],
            QuestionType.CODE_OPTIMIZATION: ['performance', 'optimization'],
            QuestionType.API_USAGE: ['api-design', 'sdk'],
            QuestionType.BUG_REPORT: ['bug-report'],
            QuestionType.DEVOPS_QUESTION: ['devops', 'deployment'],
        }
        tags.extend(type_tags.get(question_type, []))

        # 去重，最多返回10个
        return list(dict.fromkeys(tags))[:10]

    def _generate_reasoning(
        self,
        question_type: QuestionType,
        platform: Platform,
        language: str
    ) -> str:
        """生成推理说明"""
        platform_info = self.PLATFORMS.get(platform)
        platform_name = platform_info.name if platform_info else platform.value

        type_names = {
            QuestionType.ERROR_DEBUG: "错误调试类",
            QuestionType.BUG_REPORT: "Bug报告类",
            QuestionType.CODE_OPTIMIZATION: "代码优化类",
            QuestionType.API_USAGE: "API使用类",
            QuestionType.FRAMEWORK_QUESTION: "框架问题类",
            QuestionType.LANGUAGE_QUESTION: "语言问题类",
            QuestionType.DATABASE_QUESTION: "数据库类",
            QuestionType.DEVOPS_QUESTION: "DevOps类",
            QuestionType.CONCEPT_UNDERSTAND: "概念理解类",
            QuestionType.TOOL_RECOMMEND: "工具推荐类",
            QuestionType.CAREER_ADVICE: "职业建议类",
            QuestionType.PROJECT_IDEA: "项目思路类",
            QuestionType.GENERAL: "通用类",
            QuestionType.UNKNOWN: "未知类",
        }

        reasoning = f"判定为{type_names.get(question_type, '通用')}问题，"
        reasoning += f"选择{platform_name}（{language}语平台）"

        if platform_info:
            reasoning += f"，预计响应时间{platform_info.response_time}，"
            reasoning += f"社区规模{platform_info.community_size}，"
            reasoning += f"答案质量评分{platform_info.quality_score}/10"

        return reasoning

    def get_platform_info(self, platform: Platform) -> Optional[PlatformInfo]:
        """获取平台详细信息"""
        return self.PLATFORMS.get(platform)

    def compare_platforms(
        self,
        platform1: Platform,
        platform2: Platform
    ) -> Dict[str, Any]:
        """对比两个平台"""
        info1 = self.PLATFORMS.get(platform1)
        info2 = self.PLATFORMS.get(platform2)

        if not info1 or not info2:
            return {}

        return {
            "platform1": {
                "name": info1.name,
                "language": info1.language,
                "quality": info1.quality_score,
                "response_time": info1.response_time,
            },
            "platform2": {
                "name": info2.name,
                "language": info2.language,
                "quality": info2.quality_score,
                "response_time": info2.response_time,
            },
            "recommendation": info1.name if info1.quality_score > info2.quality_score else info2.name
        }
