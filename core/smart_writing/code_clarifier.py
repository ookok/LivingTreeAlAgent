# -*- coding: utf-8 -*-
"""
代码领域交互式澄清模块 - Code Interactive Clarifier
=================================================

将 InteractiveClarifier 的澄清能力扩展到代码领域。

核心功能：
1. 代码意图澄清（功能、技术栈、约束）
2. 技术栈自动检测
3. 代码风格与规范确认
4. 测试与部署需求澄清

复用模块：
- IntentEngine (意图解析)
- TechStackDetector (技术栈检测)
- CodeSigner (代码签名化，用于理解现有代码)

Author: Hermes Desktop Team
Date: 2026-04-24
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CodeClarifyStage(Enum):
    """代码澄清阶段"""
    INTENT = "intent"              # 意图识别
    TECH_STACK = "tech_stack"      # 技术栈
    REQUIREMENTS = "requirements"  # 功能需求
    CONSTRAINTS = "constraints"    # 约束条件
    STYLE = "style"                # 代码风格
    DEPLOYMENT = "deployment"      # 部署测试
    COMPLETED = "completed"        # 完成


@dataclass
class CodeClarifyQuestion:
    """代码澄清问题"""
    field: str
    question: str
    hint: str = ""
    options: Optional[List[str]] = None
    required: bool = True
    auto_detect: bool = False  # 是否可自动检测
    depends_on: Optional[str] = None  # 依赖字段
    stage: CodeClarifyStage = CodeClarifyStage.REQUIREMENTS
    examples: Optional[List[str]] = None  # 示例选项


@dataclass
class CodeClarifyProgress:
    """代码澄清进度"""
    stage: CodeClarifyStage = CodeClarifyStage.INTENT
    answered: Dict[str, Any] = field(default_factory=dict)
    pending: List[str] = field(default_factory=list)
    detected: Dict[str, Any] = field(default_factory=dict)  # 自动检测结果
    intent_type: Optional[str] = None  # 意图类型


# 支持的编程语言
PROGRAMMING_LANGUAGES = [
    "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "Go",
    "Rust", "PHP", "Ruby", "Swift", "Kotlin", "Scala", "Dart"
]

# Python 框架
PYTHON_FRAMEWORKS = [
    "Django", "Flask", "FastAPI", "PyTorch", "TensorFlow", "Pandas",
    "PyQt6", "Tkinter", "Kivy", "SQLAlchemy"
]

# JavaScript/TypeScript 框架
JS_FRAMEWORKS = [
    "React", "Vue", "Angular", "Node.js", "Express", "Next.js",
    "Nuxt", "Svelte", "NestJS", "Fastify"
]

# Java 框架
JAVA_FRAMEWORKS = [
    "Spring Boot", "Spring MVC", "Hibernate", "MyBatis", "Struts"
]

# 数据库选项
DATABASES = [
    "MySQL", "PostgreSQL", "SQLite", "MongoDB", "Redis",
    "Oracle", "SQL Server", "Elasticsearch", "Neo4j"
]

# API 风格
API_STYLES = [
    "REST", "GraphQL", "gRPC", "WebSocket", "SOAP"
]

# 代码风格
CODE_STYLES = [
    "PEP8 (Python)", "Google Style", "Airbnb Style", "StandardJS",
    "Prettier", "ESLint", "Java Style Guide"
]

# 测试框架
TEST_FRAMEWORKS = {
    "Python": ["pytest", "unittest", "nose2", "doctest"],
    "JavaScript": ["Jest", "Mocha", "Chai", "Cypress"],
    "Java": ["JUnit", "TestNG", "Mockito"],
    "Go": ["testing", "Ginkgo", "GoConvey"],
}

# 部署方式
DEPLOYMENT_METHODS = [
    "Docker", "K8s", "Serverless", "VM", "Bare Metal",
    "Cloud Functions", "CI/CD Pipeline"
]

# 云服务商
CLOUD_PROVIDERS = [
    "AWS", "Azure", "GCP", "阿里云", "腾讯云", "华为云", "自建"
]


class CodeClarifier:
    """
    代码领域交互式澄清器
    
    使用示例：
    ```python
    from core.smart_writing.code_clarifier import CodeClarifier
    
    clarifier = CodeClarifier()
    
    # 开始澄清会话
    session = clarifier.start_session(
        requirement="帮我写一个用户登录接口"
    )
    
    # 获取下一步问题
    questions = clarifier.get_next_questions(session)
    
    # 回答问题
    session = clarifier.answer(session, "language", "Python")
    
    # 完成并生成完整需求
    final = clarifier.complete_session(session)
    ```
    """
    
    def __init__(self):
        self._session_cache: Dict[str, CodeClarifyProgress] = {}
        self._intent_engine = None
        self._tech_detector = None
    
    @property
    def intent_engine(self):
        """延迟加载意图引擎"""
        if self._intent_engine is None:
            try:
                from core.intent_engine import IntentEngine
                self._intent_engine = IntentEngine()
            except ImportError:
                logger.debug("IntentEngine 未安装")
        return self._intent_engine
    
    def start_session(
        self,
        requirement: str,
        existing_data: Optional[Dict] = None,
        context_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        开始代码澄清会话
        
        Args:
            requirement: 原始需求
            existing_data: 已有的数据
            context_files: 上下文文件列表
        
        Returns:
            会话状态
        """
        import uuid
        
        session_id = uuid.uuid4().hex[:8]
        
        # 初始化进度
        progress = CodeClarifyProgress()
        progress.stage = CodeClarifyStage.INTENT
        
        # 从已有数据初始化
        if existing_data:
            progress.answered = existing_data.copy()
            progress.intent_type = existing_data.get("intent_type")
        
        # 尝试自动检测
        self._auto_detect(requirement, context_files, progress)
        
        # 存储会话
        self._session_cache[session_id] = progress
        
        # 生成意图相关问题
        questions = self._generate_intent_questions(requirement, progress)
        progress.pending = [q.field for q in questions if q.required and not q.auto_detect]
        
        progress.stage = CodeClarifyStage.TECH_STACK
        
        return {
            "session_id": session_id,
            "requirement": requirement,
            "stage": progress.stage.value,
            "intent_type": progress.intent_type,
            "questions": [
                {
                    "field": q.field,
                    "question": q.question,
                    "hint": q.hint,
                    "options": q.options,
                    "required": q.required,
                    "auto_detected": q.field in progress.detected,
                    "detected_value": progress.detected.get(q.field),
                    "examples": q.examples,
                }
                for q in questions
            ],
            "detected": progress.detected,
            "progress": self._calculate_progress(progress),
        }
    
    def _auto_detect(
        self,
        requirement: str,
        context_files: Optional[List[str]],
        progress: CodeClarifyProgress
    ):
        """自动检测技术栈和约束"""
        detected = {}
        
        # 1. 从需求中检测语言
        lang = self._detect_language(requirement)
        if lang:
            detected["language"] = lang
            
        # 2. 从需求中检测框架
        framework = self._detect_framework(requirement, lang)
        if framework:
            detected["framework"] = framework
            
        # 3. 从需求中检测数据库
        db = self._detect_database(requirement)
        if db:
            detected["database"] = db
            
        # 4. 从需求中检测意图类型
        intent_type = self._detect_intent_type(requirement)
        if intent_type:
            progress.intent_type = intent_type
            detected["intent_type"] = intent_type
            
        # 5. 从上下文文件检测
        if context_files:
            file_based = self._detect_from_files(context_files)
            detected.update(file_based)
        
        progress.detected = detected
    
    def _detect_language(self, requirement: str) -> Optional[str]:
        """从需求中检测编程语言"""
        requirement_lower = requirement.lower()
        
        # 语言关键词
        lang_patterns = {
            "Python": [r"\bpython\b", r"\bpy\b", r"\bpandas\b", r"\bpytorch\b", r"\btensorflow\b"],
            "JavaScript": [r"\bjavascript\b", r"\bjs\b", r"\bnode\.?js\b", r"\bnpm\b"],
            "TypeScript": [r"\btypescript\b", r"\bts\b", r"\btsx?\b"],
            "Java": [r"\bjava\b", r"\bspring\b", r"\bmaven\b", r"\bgradle\b"],
            "C#": [r"\bc#\b", r"\bdotnet\b", r"\b\.net\b", r"\basp\.net\b"],
            "Go": [r"\bgo\b", r"\bgolang\b"],
            "Rust": [r"\brust\b"],
            "PHP": [r"\bphp\b"],
            "Swift": [r"\bswift\b", r"\biOS\b", r"\bXcode\b"],
            "Kotlin": [r"\bkotlin\b", r"\bandroid\b"],
        }
        
        for lang, patterns in lang_patterns.items():
            for pattern in patterns:
                if re.search(pattern, requirement_lower):
                    return lang
        return None
    
    def _detect_framework(self, requirement: str, lang: Optional[str]) -> Optional[str]:
        """从需求中检测框架"""
        requirement_lower = requirement.lower()
        
        framework_patterns = {
            "Django": [r"\bdjango\b"],
            "Flask": [r"\bflask\b"],
            "FastAPI": [r"\bfastapi\b", r"\bapi\b"],
            "PyQt6": [r"\bpyqt6?\b", r"\bpyqt\b"],
            "React": [r"\breact\b"],
            "Vue": [r"\bvue\b"],
            "Angular": [r"\bangular\b"],
            "Next.js": [r"\bnext\.?js\b"],
            "Spring Boot": [r"\bspring\s*boot\b"],
            "Flutter": [r"\bflutter\b"],
        }
        
        for framework, patterns in framework_patterns.items():
            for pattern in patterns:
                if re.search(pattern, requirement_lower):
                    return framework
        return None
    
    def _detect_database(self, requirement: str) -> Optional[str]:
        """从需求中检测数据库"""
        requirement_lower = requirement.lower()
        
        db_patterns = {
            "MySQL": [r"\bmysql\b"],
            "PostgreSQL": [r"\bpostgresql\b", r"\bpsql\b"],
            "MongoDB": [r"\bmongodb\b", r"\bno-sql\b"],
            "Redis": [r"\bredis\b"],
            "SQLite": [r"\bsqlite\b"],
            "Elasticsearch": [r"\belasticsearch\b", r"\bes\b"],
        }
        
        for db, patterns in db_patterns.items():
            for pattern in patterns:
                if re.search(pattern, requirement_lower):
                    return db
        return None
    
    def _detect_intent_type(self, requirement: str) -> Optional[str]:
        """检测意图类型"""
        requirement_lower = requirement.lower()
        
        # 代码生成类
        if any(kw in requirement_lower for kw in ["写", "创建", "生成", "实现", "build", "create", "implement"]):
            if any(kw in requirement_lower for kw in ["接口", "api", "函数", "方法", "class"]):
                return "CODE_GENERATION"
            if any(kw in requirement_lower for kw in ["web", "网站", "前端", "页面"]):
                return "UI_GENERATION"
            if any(kw in requirement_lower for kw in ["数据库", "表", "model", "schema"]):
                return "DATABASE_DESIGN"
            return "CODE_GENERATION"
        
        # 代码修改类
        if any(kw in requirement_lower for kw in ["修改", "改", "优化", "重构", "refactor", "modify"]):
            return "CODE_MODIFICATION"
        
        # 调试类
        if any(kw in requirement_lower for kw in ["bug", "错误", "修复", "调试", "fix"]):
            return "DEBUGGING"
        
        # 代码审查类
        if any(kw in requirement_lower for kw in ["审查", "review", "检查", "分析"]):
            return "CODE_REVIEW"
        
        # 测试类
        if any(kw in requirement_lower for kw in ["测试", "test", "单元测试", "用例"]):
            return "TEST_GENERATION"
        
        return "CODE_GENERATION"  # 默认
    
    def _detect_from_files(self, files: List[str]) -> Dict[str, Any]:
        """从文件列表检测技术栈"""
        detected = {}
        
        # 统计文件扩展名
        ext_count = {}
        for f in files:
            ext = f.split(".")[-1].lower() if "." in f else ""
            ext_count[ext] = ext_count.get(ext, 0) + 1
        
        # 扩展名映射语言
        ext_to_lang = {
            "py": "Python",
            "js": "JavaScript",
            "ts": "TypeScript",
            "tsx": "TypeScript",
            "jsx": "JavaScript",
            "java": "Java",
            "cs": "C#",
            "cpp": "C++",
            "c": "C",
            "go": "Go",
            "rs": "Rust",
            "rb": "Ruby",
            "php": "PHP",
            "swift": "Swift",
            "kt": "Kotlin",
        }
        
        for ext, count in ext_count.items():
            if ext in ext_to_lang and count >= 2:  # 至少2个文件
                detected["language"] = ext_to_lang[ext]
                break
        
        # 检测配置文件
        for f in files:
            fname = f.lower()
            if "requirements" in fname or "pyproject" in fname:
                detected["language"] = "Python"
            elif "package.json" in fname:
                detected["language"] = "JavaScript"
            elif "pom.xml" in fname or "build.gradle" in fname:
                detected["language"] = "Java"
            elif "go.mod" in fname:
                detected["language"] = "Go"
        
        return detected
    
    def _generate_intent_questions(
        self,
        requirement: str,
        progress: CodeClarifyProgress
    ) -> List[CodeClarifyQuestion]:
        """生成意图相关问题"""
        questions = []
        intent_type = progress.intent_type
        
        # 根据意图类型生成问题
        if intent_type == "CODE_GENERATION":
            questions.extend([
                CodeClarifyQuestion(
                    field="language",
                    question="使用什么编程语言？",
                    hint="请选择或输入编程语言",
                    options=PROGRAMMING_LANGUAGES,
                    stage=CodeClarifyStage.TECH_STACK,
                    auto_detect=True,
                    examples=["Python", "JavaScript", "Go"]
                ),
                CodeClarifyQuestion(
                    field="framework",
                    question="使用什么框架？",
                    hint="如果没有框架要求可跳过",
                    stage=CodeClarifyStage.TECH_STACK,
                    auto_detect=True,
                ),
                CodeClarifyQuestion(
                    field="database",
                    question="需要数据库支持吗？",
                    hint="如果有数据库需求请选择",
                    options=DATABASES,
                    required=False,
                    stage=CodeClarifyStage.TECH_STACK,
                ),
            ])
            
            # 功能相关问题
            questions.extend([
                CodeClarifyQuestion(
                    field="input_params",
                    question="输入参数有哪些？",
                    hint="描述输入数据的结构",
                    required=False,
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
                CodeClarifyQuestion(
                    field="output_format",
                    question="输出格式是什么？",
                    hint="如：JSON、DataFrame、文件等",
                    required=False,
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
                CodeClarifyQuestion(
                    field="api_style",
                    question="API 风格偏好？",
                    options=API_STYLES,
                    required=False,
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
            ])
            
        elif intent_type == "CODE_MODIFICATION":
            questions.extend([
                CodeClarifyQuestion(
                    field="target_files",
                    question="需要修改的文件？",
                    hint="请提供文件路径",
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
                CodeClarifyQuestion(
                    field="modification_type",
                    question="修改类型？",
                    options=["重构优化", "功能扩展", "Bug修复", "安全加固", "性能优化"],
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
                CodeClarifyQuestion(
                    field="keep_compatible",
                    question="是否需要保持向后兼容？",
                    options=["是", "否"],
                    required=False,
                    stage=CodeClarifyStage.CONSTRAINTS,
                ),
            ])
            
        elif intent_type == "DEBUGGING":
            questions.extend([
                CodeClarifyQuestion(
                    field="error_message",
                    question="错误信息是什么？",
                    hint="请粘贴完整的错误信息",
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
                CodeClarifyQuestion(
                    field="error_context",
                    question="在什么场景下出错？",
                    hint="描述触发条件",
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
                CodeClarifyQuestion(
                    field="recent_changes",
                    question="最近有什么代码变更？",
                    required=False,
                    stage=CodeClarifyStage.CONSTRAINTS,
                ),
            ])
            
        elif intent_type == "TEST_GENERATION":
            questions.extend([
                CodeClarifyQuestion(
                    field="test_target",
                    question="需要测试什么？",
                    hint="如：函数名、类名、模块路径",
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
                CodeClarifyQuestion(
                    field="test_framework",
                    question="使用什么测试框架？",
                    options=TEST_FRAMEWORKS.get("Python", ["pytest"]),
                    stage=CodeClarifyStage.TECH_STACK,
                ),
                CodeClarifyQuestion(
                    field="coverage_target",
                    question="覆盖率目标？",
                    options=["高覆盖（80%+）", "标准覆盖（60%+）", "核心功能即可"],
                    required=False,
                    stage=CodeClarifyStage.REQUIREMENTS,
                ),
            ])
        
        # 通用约束问题
        questions.extend([
            CodeClarifyQuestion(
                field="performance",
                question="性能要求？",
                hint="如：响应时间<100ms，支持并发1000+",
                required=False,
                stage=CodeClarifyStage.CONSTRAINTS,
            ),
            CodeClarifyQuestion(
                field="security",
                question="安全要求？",
                options=["无特殊要求", "输入校验", "权限控制", "数据加密", "完全合规"],
                required=False,
                stage=CodeClarifyStage.CONSTRAINTS,
            ),
            CodeClarifyQuestion(
                field="code_style",
                question="代码风格规范？",
                options=CODE_STYLES,
                required=False,
                stage=CodeClarifyStage.STYLE,
            ),
            CodeClarifyQuestion(
                field="deployment",
                question="部署方式？",
                options=DEPLOYMENT_METHODS,
                required=False,
                stage=CodeClarifyStage.DEPLOYMENT,
            ),
        ])
        
        return questions
    
    def get_next_questions(
        self,
        session: Dict[str, Any],
        answered_field: Optional[str] = None
    ) -> List[Dict]:
        """
        获取下一步需要回答的问题
        
        Args:
            session: 会话状态
            answered_field: 已回答的字段
        
        Returns:
            问题列表
        """
        session_id = session.get("session_id")
        if not session_id or session_id not in self._session_cache:
            return []
        
        progress = self._session_cache[session_id]
        
        # 获取意图类型
        intent_type = session.get("intent_type") or progress.intent_type or "CODE_GENERATION"
        
        # 生成问题
        all_questions = self._generate_intent_questions(
            session.get("requirement", ""),
            progress
        )
        
        # 过滤已回答的问题
        pending_questions = [
            q for q in all_questions
            if q.field not in progress.answered
            and (not q.depends_on or q.depends_on in progress.answered)
        ]
        
        # 按阶段排序
        stage_order = [
            CodeClarifyStage.INTENT,
            CodeClarifyStage.TECH_STACK,
            CodeClarifyStage.REQUIREMENTS,
            CodeClarifyStage.CONSTRAINTS,
            CodeClarifyStage.STYLE,
            CodeClarifyStage.DEPLOYMENT,
        ]
        
        def stage_priority(q: CodeClarifyQuestion) -> int:
            try:
                return stage_order.index(q.stage)
            except ValueError:
                return len(stage_order)
        
        pending_questions.sort(key=stage_priority)
        
        return [
            {
                "field": q.field,
                "question": q.question,
                "hint": q.hint,
                "options": q.options,
                "required": q.required,
                "auto_detected": q.field in progress.detected,
                "detected_value": progress.detected.get(q.field),
                "examples": q.examples,
            }
            for q in pending_questions[:5]  # 每次最多5个问题
        ]
    
    def answer(
        self,
        session: Dict[str, Any],
        field: str,
        value: Any
    ) -> Dict[str, Any]:
        """
        回答问题
        
        Args:
            session: 会话状态
            field: 字段名
            value: 回答值
        
        Returns:
            更新后的会话状态
        """
        session_id = session.get("session_id")
        if not session_id or session_id not in self._session_cache:
            return session
        
        progress = self._session_cache[session_id]
        
        # 记录回答
        progress.answered[field] = value
        
        # 移除待处理
        if field in progress.pending:
            progress.pending.remove(field)
        
        # 更新阶段
        all_questions = self._generate_intent_questions(
            session.get("requirement", ""),
            progress
        )
        
        # 检查完成状态
        answered_fields = set(progress.answered.keys())
        required_fields = set(q.field for q in all_questions if q.required)
        
        if answered_fields >= required_fields:
            progress.stage = CodeClarifyStage.COMPLETED
        else:
            # 根据最新回答调整阶段
            answered_stages = set()
            for q in all_questions:
                if q.field in progress.answered:
                    answered_stages.add(q.stage)
            
            # 设置到下一个未完成阶段
            for stage in [CodeClarifyStage.DEPLOYMENT, CodeClarifyStage.STYLE,
                         CodeClarifyStage.CONSTRAINTS, CodeClarifyStage.REQUIREMENTS,
                         CodeClarifyStage.TECH_STACK]:
                if stage not in answered_stages:
                    progress.stage = stage
                    break
        
        # 更新会话
        session["answered"] = progress.answered
        session["stage"] = progress.stage.value
        session["progress"] = self._calculate_progress(progress)
        
        return session
    
    def get_code_suggestions(self, session: Dict[str, Any]) -> List[Dict]:
        """
        获取代码相关建议
        
        Returns:
            建议列表
        """
        suggestions = []
        session_id = session.get("session_id")
        
        if not session_id or session_id not in self._session_cache:
            return suggestions
        
        progress = self._session_cache[session_id]
        answered = progress.answered
        
        # 1. 技术栈建议
        if "language" in answered and "framework" not in answered:
            lang = answered["language"]
            frameworks = PYTHON_FRAMEWORKS if lang == "Python" else \
                        JS_FRAMEWORKS if lang in ["JavaScript", "TypeScript"] else \
                        JAVA_FRAMEWORKS if lang == "Java" else []
            if frameworks:
                suggestions.append({
                    "type": "framework",
                    "title": f"{lang} 推荐框架",
                    "content": "、".join(frameworks[:5]),
                    "action": "select_framework"
                })
        
        # 2. 数据库建议
        if "database" in answered:
            db = answered["database"]
            suggestions.append({
                "type": "orm",
                "title": f"{db} ORM 推荐",
                "content": self._get_orm_suggestion(db),
                "action": "select_orm"
            })
        
        # 3. 代码风格建议
        if "code_style" not in answered:
            suggestions.append({
                "type": "style",
                "title": "代码风格规范",
                "content": "建议使用 PEP8 (Python) / ESLint (JS) 规范",
                "action": "select_style"
            })
        
        # 4. 测试建议
        if "intent_type" in answered and answered["intent_type"] in ["CODE_GENERATION", "CODE_MODIFICATION"]:
            lang = answered.get("language", "Python")
            test_fw = TEST_FRAMEWORKS.get(lang, ["pytest"])
            suggestions.append({
                "type": "testing",
                "title": "建议添加测试",
                "content": f"推荐使用 {test_fw[0]}",
                "action": "add_tests"
            })
        
        return suggestions
    
    def _get_orm_suggestion(self, db: str) -> str:
        """获取 ORM 建议"""
        orm_map = {
            "MySQL": "SQLAlchemy / Django ORM",
            "PostgreSQL": "SQLAlchemy / Django ORM",
            "MongoDB": "MongoEngine / Peewee-Mongo",
            "Redis": "redis-py",
            "SQLite": "SQLAlchemy / Django ORM",
        }
        return orm_map.get(db, "根据项目情况选择")
    
    def complete_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        完成澄清会话，输出完整需求
        
        Returns:
            完整的代码需求信息
        """
        session_id = session.get("session_id")
        if not session_id or session_id not in self._session_cache:
            return session
        
        progress = self._session_cache[session_id]
        
        # 合并自动检测和用户输入
        final_data = {}
        final_data.update(progress.detected)
        final_data.update(progress.answered)
        final_data["intent_type"] = progress.intent_type
        
        # 清理会话
        del self._session_cache[session_id]
        
        return {
            "session_id": session_id,
            "requirement": session.get("requirement"),
            "intent_type": final_data.get("intent_type"),
            "tech_stack": {
                "language": final_data.get("language"),
                "framework": final_data.get("framework"),
                "database": final_data.get("database"),
                "api_style": final_data.get("api_style"),
            },
            "requirements": {
                "input_params": final_data.get("input_params"),
                "output_format": final_data.get("output_format"),
                "test_framework": final_data.get("test_framework"),
                "coverage_target": final_data.get("coverage_target"),
            },
            "constraints": {
                "performance": final_data.get("performance"),
                "security": final_data.get("security"),
                "keep_compatible": final_data.get("keep_compatible"),
                "recent_changes": final_data.get("recent_changes"),
            },
            "style": {
                "code_style": final_data.get("code_style"),
            },
            "deployment": {
                "method": final_data.get("deployment"),
            },
            "completeness": self._calculate_completeness(progress, final_data),
        }
    
    def _calculate_progress(self, progress: CodeClarifyProgress) -> Dict:
        """计算澄清进度"""
        required_count = 5  # 基础必填项
        completed = len(progress.answered) + len(progress.detected)
        
        return {
            "completed": min(completed, required_count),
            "total": required_count,
            "percentage": int(min(completed, required_count) / required_count * 100),
            "auto_detected": len(progress.detected),
            "stage": progress.stage.value,
        }
    
    def _calculate_completeness(
        self,
        progress: CodeClarifyProgress,
        final_data: Dict
    ) -> Dict:
        """计算完整度"""
        critical_fields = ["language", "intent_type"]
        important_fields = ["framework", "database", "modification_type"]
        optional_fields = ["performance", "security", "code_style"]
        
        filled_critical = [f for f in critical_fields if f in final_data and final_data[f]]
        filled_important = [f for f in important_fields if f in final_data and final_data[f]]
        filled_optional = [f for f in optional_fields if f in final_data and final_data[f]]
        
        critical_score = len(filled_critical) / len(critical_fields)
        important_score = len(filled_important) / len(important_fields)
        optional_score = len(filled_optional) / len(optional_fields)
        
        overall = critical_score * 0.6 + important_score * 0.3 + optional_score * 0.1
        
        return {
            "critical_complete": f"{len(filled_critical)}/{len(critical_fields)}",
            "important_complete": f"{len(filled_important)}/{len(important_fields)}",
            "optional_complete": f"{len(filled_optional)}/{len(optional_fields)}",
            "overall_score": round(overall, 2),
            "missing_critical": [f for f in critical_fields if f not in final_data or not final_data[f]],
        }


# 全局实例
_clarifier: Optional[CodeClarifier] = None


def get_code_clarifier() -> CodeClarifier:
    """获取全局代码澄清器实例"""
    global _clarifier
    if _clarifier is None:
        _clarifier = CodeClarifier()
    return _clarifier


def quick_clarify(requirement: str) -> Dict[str, Any]:
    """快速澄清接口"""
    clarifier = get_code_clarifier()
    session = clarifier.start_session(requirement)
    return clarifier.complete_session(session)
