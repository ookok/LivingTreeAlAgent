# -*- coding: utf-8 -*-
"""
Markdown转Word文档系统 - Markdown to Word Document System
=========================================================
核心数据模型定义

功能：
- 多格式转换引擎（Markdown → DOCX/PDF/HTML/TXT）
- 知识库集成模块
- 进度管理系统
- 断点续传功能
- 样式模板系统

作者：Hermes Desktop Team
版本：1.0.0
"""

from .models import (
    # 枚举定义
    TaskStatus, TaskType, SourceType, TargetFormat,
    ElementType, StyleType, StepStatus, TemplateCategory,
    LinkMode, ImageMode, CodeHighlight,
    # 任务相关
    Task, ProgressInfo, StepInfo,
    # 文档相关
    DocumentNode, DocumentElement,
    # 样式相关
    StyleTemplate, StyleConfig,
    # 知识库相关
    KnowledgeSource, SourceConfig,
    # 配置相关
    ConversionConfig, ImageConfig, LinkConfig, CodeConfig,
    TableConfig, MathConfig, PageConfig, HeaderFooterConfig, TOCConfig,
    # 结果相关
    ConversionResult, ConversionError, TemplateInfo,
    # 便利函数
    get_default_template, get_builtin_templates, get_default_steps,
    create_progress_info,
)

from .markdown_parser import (
    MarkdownParser, parse_markdown, parse_markdown_file,
)
from .docx_generator import (
    DOCXGenerator, generate_docx, markdown_to_docx,
)
from .converter import (
    ConversionEngine, get_conversion_engine, quick_convert,
)
from .knowledge_base import (
    DocumentInfo, KnowledgeBaseManager, get_knowledge_base_manager,
    create_local_source, create_git_source,
)

__all__ = [
    # 枚举定义
    'TaskStatus', 'TaskType', 'SourceType', 'TargetFormat',
    'ElementType', 'StyleType', 'StepStatus', 'TemplateCategory',
    'LinkMode', 'ImageMode', 'CodeHighlight',
    # 任务相关
    'Task', 'ProgressInfo', 'StepInfo',
    # 文档相关
    'DocumentNode', 'DocumentElement',
    # 样式相关
    'StyleTemplate', 'StyleConfig',
    # 知识库相关
    'KnowledgeSource', 'SourceConfig', 'DocumentInfo',
    'KnowledgeBaseManager', 'get_knowledge_base_manager',
    'create_local_source', 'create_git_source',
    # 配置相关
    'ConversionConfig', 'ImageConfig', 'LinkConfig', 'CodeConfig',
    'TableConfig', 'MathConfig', 'PageConfig', 'HeaderFooterConfig', 'TOCConfig',
    # 结果相关
    'ConversionResult', 'ConversionError', 'TemplateInfo',
    # 便利函数
    'get_default_template', 'get_builtin_templates', 'get_default_steps',
    'create_progress_info',
    # 解析器
    'MarkdownParser', 'parse_markdown', 'parse_markdown_file',
    # 生成器
    'DOCXGenerator', 'generate_docx', 'markdown_to_docx',
    # 引擎
    'ConversionEngine', 'get_conversion_engine', 'quick_convert',
]
