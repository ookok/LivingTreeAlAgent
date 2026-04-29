# -*- coding: utf-8 -*-
"""
意图类型和数据结构定义
=======================

定义 IntentEngine 使用的所有数据类型。
from __future__ import annotations
"""


from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set


class IntentType(Enum):
    """
    意图类型枚举
    
    覆盖代码开发全流程：
    - 生成/创建/实现 → 写新代码
    - 修改/重构/优化 → 改现有代码
    - 调试/修复/排查 → 修问题
    - 分析/理解/解释 → 看代码
    - 测试/验证/检查 → 质量保证
    - 部署/发布/配置 → 运维相关
    """
    
    # === 代码生成类 ===
    CODE_GENERATION = "code_generation"        # 生成新代码
    CODE_IMPLEMENTATION = "code_implementation"  # 实现具体功能
    API_DESIGN = "api_design"                  # API 设计
    DATABASE_DESIGN = "database_design"        # 数据库设计
    UI_GENERATION = "ui_generation"           # UI 生成
    
    # === 代码修改类 ===
    CODE_MODIFICATION = "code_modification"   # 修改代码
    CODE_REFACTOR = "code_refactor"           # 重构
    CODE_OPTIMIZATION = "code_optimization"    # 性能优化
    CODE_MIGRATION = "code_migration"          # 迁移/升级
    
    # === 调试修复类 ===
    DEBUGGING = "debugging"                   # 调试
    BUG_FIX = "bug_fix"                       # Bug 修复
    ERROR_RESOLUTION = "error_resolution"     # 错误排查
    ISSUE_ANALYSIS = "issue_analysis"         # 问题分析
    
    # === 代码理解类 ===
    CODE_UNDERSTANDING = "code_understanding" # 理解代码
    CODE_EXPLANATION = "code_explanation"     # 代码解释
    CODE_REVIEW = "code_review"               # 代码审查
    DOCUMENTATION = "documentation"           # 文档生成
    
    # === 测试验证类 ===
    TEST_GENERATION = "test_generation"       # 生成测试
    CODE_VERIFICATION = "code_verification"   # 代码验证
    SECURITY_CHECK = "security_check"        # 安全检查
    PERFORMANCE_ANALYSIS = "performance_analysis"  # 性能分析
    
    # === 运维部署类 ===
    DEPLOYMENT = "deployment"                 # 部署
    CONFIGURATION = "configuration"          # 配置
    ENVIRONMENT_SETUP = "environment_setup"  # 环境搭建
    
    # === 文件操作类 ===
    FILE_OPERATION = "file_operation"         # 文件操作（读/写/删除）
    FOLDER_STRUCTURE = "folder_structure"     # 目录结构
    
    # === 知识问答类 ===
    KNOWLEDGE_QUERY = "knowledge_query"       # 知识查询
    CONCEPT_EXPLANATION = "concept_explanation"  # 概念解释
    BEST_PRACTICE = "best_practice"           # 最佳实践
    
    # === 其他 ===
    UNKNOWN = "unknown"                       # 未知意图
    MULTIPLE = "multiple"                     # 复合意图

    # === 语言处理类 ===
    TRANSLATION = "translation"               # 翻译
    SUMMARIZATION = "summarization"           # 摘要
    PARAPHRASE = "paraphrase"               # 改写

    # === 数据分析类 ===
    DATA_ANALYSIS = "data_analysis"           # 数据分析
    DATA_VISUALIZATION = "data_visualization" # 数据可视化

    # === 内容生成类 ===
    IMAGE_GENERATION = "image_generation"     # 图像生成
    VIDEO_GENERATION = "video_generation"     # 视频生成


class IntentPriority(Enum):
    """意图优先级"""
    CRITICAL = 1   # 必须完成
    HIGH = 2       # 重要
    MEDIUM = 3     # 普通
    LOW = 4        # 可选


class TechStack(Enum):
    """
    支持的技术栈
    
    包含主流编程语言、框架、工具。
    """
    # 语言
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    C_SHARP = "c#"
    CPP = "c++"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    PHP = "php"
    RUBY = "ruby"
    
    # Web 框架
    FASTAPI = "fastapi"
    DJANGO = "django"
    FLASK = "flask"
    EXPRESS = "express"
    NESTJS = "nestjs"
    NEXTJS = "nextjs"
    REACT = "react"
    VUE = "vue"
    ANGULAR = "angular"
    SPRING = "spring"
    SPRING_BOOT = "springboot"
    
    # 数据库
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"
    SQLITE = "sqlite"
    
    # 工具/中间件
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    GIT = "git"
    GITHUB = "github"
    GITLAB = "gitlab"
    JENKINS = "jenkins"
    NGINX = "nginx"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    
    # 云服务
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ALIYUN = "aliyun"
    TENCENT = "tencent"
    
    # AI/ML
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    SKLEARN = "sklearn"
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"


@dataclass
class IntentConstraint:
    """约束条件"""
    constraint_type: str = ""
    name: str = ""
    value: Any = None
    required: bool = False
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.constraint_type,
            "name": self.name,
            "value": self.value,
            "required": self.required,
            "confidence": self.confidence,
        }


@dataclass
class Intent:
    """
    结构化意图
    
    将自然语言转换为结构化的意图描述。
    """
    # 基础信息
    raw_input: str = ""
    intent_type: IntentType = IntentType.UNKNOWN
    action: str = ""
    target: str = ""
    target_description: str = ""
    
    # 技术栈
    tech_stack: List[str] = field(default_factory=list)
    tech_confidence: float = 0.0
    
    # 约束条件
    constraints: List[IntentConstraint] = field(default_factory=list)
    
    # 复合意图
    is_composite: bool = False
    sub_intents: List[Intent] = field(default_factory=list)
    
    # 质量指标
    confidence: float = 0.0
    completeness: float = 0.0
    
    # 优先级
    priority: IntentPriority = IntentPriority.MEDIUM
    
    # 额外信息
    compressed_query: str = ""
    keywords: List[str] = field(default_factory=list)
    language: str = "zh"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.compressed_query:
            self.compressed_query = self.raw_input[:200]
        if not self.keywords:
            self.keywords = self._extract_keywords()
    
    def _extract_keywords(self) -> List[str]:
        import re
        stop_words = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
            "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看", "好", "自己", "这", "那",
            "什么", "怎么", "帮", "一下", "帮我", "这个", "那个",
            "需要", "想要", "能不能", "请", "need", "want", "help"
        }
        # 分词：先用空白字符分，再按中文/英文标点二次分割
        import re
        tokens = re.split(r'\s+', self.raw_input.strip())
        punct = ',，。、！？；：""\'\'（）【】\[\]{}()'
        words = []
        for token in tokens:
            parts = re.split('|'.join(re.escape(c) for c in punct), token)
            words.extend(p.strip() for p in parts if p.strip())
        words = [w.strip().lower() for w in words if w.strip()]
        keywords = [w for w in words if len(w) >= 2 and w not in stop_words]
        return keywords[:20]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_input": self.raw_input[:100] + "..." if len(self.raw_input) > 100 else self.raw_input,
            "intent_type": self.intent_type.value,
            "action": self.action,
            "target": self.target,
            "tech_stack": self.tech_stack,
            "constraints": [c.to_dict() for c in self.constraints],
            "is_composite": self.is_composite,
            "confidence": self.confidence,
            "completeness": self.completeness,
            "priority": self.priority.name,
            "keywords": self.keywords,
        }
    
    def to_prompt_context(self) -> str:
        parts = [f"## 意图类型\n{self.intent_type.value}"]
        if self.action:
            parts.append(f"## 动作\n{self.action}")
        if self.target:
            parts.append(f"## 目标\n{self.target}")
        if self.tech_stack:
            parts.append(f"## 技术栈\n{', '.join(self.tech_stack)}")
        if self.constraints:
            parts.append("## 约束条件")
            for c in self.constraints:
                req = "[必须]" if c.required else "[建议]"
                parts.append(f"- {req} {c.name}: {c.value}")
        return "\n".join(parts)
    
    def get_summary(self) -> str:
        return f"[{self.intent_type.value}] {self.action or '未知动作'} {self.target or ''}".strip()
