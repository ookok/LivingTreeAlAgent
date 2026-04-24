# -*- coding: utf-8 -*-
"""
Error Pattern Models - 错误模式数据模型
=====================================

三层知识表示：
1. 表层特征层：错误表现、错误信息、上下文
2. 模式抽象层：错误类型、根本原因、影响范围
3. 修复方案层：具体修复步骤、验证方法、预防措施

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Set


# ═══════════════════════════════════════════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorCategory(Enum):
    """错误类别"""
    # 编码相关
    ENCODING = "encoding"              # 编码错误
    # 文件相关
    FILE_IO = "file_io"                # 文件IO错误
    # 网络相关
    NETWORK = "network"                 # 网络错误
    # 语法相关
    SYNTAX = "syntax"                  # 语法错误
    # 逻辑相关
    LOGIC = "logic"                   # 逻辑错误
    # 资源相关
    RESOURCE = "resource"              # 资源错误
    # 配置相关
    CONFIG = "config"                  # 配置错误
    # 依赖相关
    DEPENDENCY = "dependency"          # 依赖错误
    # 运行时
    RUNTIME = "runtime"                # 运行时错误
    # 未知
    UNKNOWN = "unknown"                # 未知错误


class ErrorSeverity(Enum):
    """错误严重程度"""
    BLOCKING = "blocking"    # 阻塞性（无法继续）
    CRITICAL = "critical"   # 严重（功能不可用）
    WARNING = "warning"    # 警告（功能受限）
    INFO = "info"          # 信息（不影响功能）


class FixStatus(Enum):
    """修复状态"""
    PENDING = "pending"          # 待修复
    IN_PROGRESS = "in_progress"  # 修复中
    SUCCESS = "success"          # 修复成功
    FAILED = "failed"           # 修复失败
    PARTIAL = "partial"         # 部分修复


class FixConfidence(Enum):
    """修复置信度"""
    HIGH = 0.9     # 高置信度
    MEDIUM = 0.6  # 中置信度
    LOW = 0.3     # 低置信度
    UNKNOWN = 0.0 # 未知


# ═══════════════════════════════════════════════════════════════════════════════
# 表层特征层
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ErrorSurfaceFeatures:
    """
    表层特征层
    
    错误的表现形式，可直接观测到的特征
    """
    # 原始错误信息
    raw_message: str
    error_type: str                    # 错误类型名，如 "UnicodeDecodeError"
    error_code: Optional[str] = None   # 错误代码
    
    # 上下文信息
    file_path: Optional[str] = None    # 相关文件路径
    line_number: Optional[int] = None   # 行号
    function_name: Optional[str] = None # 函数名
    
    # 环境信息
    os_platform: Optional[str] = None   # 操作系统
    python_version: Optional[str] = None # Python版本
    environment: Optional[str] = None   # 环境名称
    
    # 操作上下文
    operation_type: Optional[str] = None # 操作类型：read/write/network/execute
    target_resource: Optional[str] = None # 目标资源
    input_data_type: Optional[str] = None # 输入数据类型
    
    # 时间信息
    occurred_at: datetime = field(default_factory=datetime.now)
    
    def get_fingerprint(self) -> str:
        """生成错误指纹（基于关键特征的哈希）"""
        key_features = f"{self.error_type}:{self.error_code or ''}:{self.operation_type or ''}"
        return hashlib.md5(key_features.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_message": self.raw_message,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "function_name": self.function_name,
            "os_platform": self.os_platform,
            "python_version": self.python_version,
            "environment": self.environment,
            "operation_type": self.operation_type,
            "target_resource": self.target_resource,
            "input_data_type": self.input_data_type,
            "occurred_at": self.occurred_at.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 模式抽象层
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ErrorPattern:
    """
    模式抽象层
    
    从具体错误中抽象出的通用模式
    """
    # 模式标识
    pattern_id: str
    pattern_name: str                    # 模式名称，如 "字符编码不匹配"
    
    # 错误分类
    category: ErrorCategory              # 错误类别
    severity: ErrorSeverity              # 严重程度
    root_cause_type: str                 # 根本原因类型
    
    # 模式特征（抽象化）
    error_type_pattern: str              # 错误类型模式，如 ".*Decode.*Error"
    message_keywords: List[str]         # 关键词列表
    trigger_conditions: List[str]       # 触发条件
    
    # 影响范围
    affected_systems: List[str]          # 受影响系统
    impact_scope: str                    # 影响范围描述
    
    # 相关模式
    related_patterns: List[str] = field(default_factory=list)  # 相关模式ID
    derived_from: Optional[str] = None   # 派生自的模式
    
    # 统计
    occurrence_count: int = 0            # 发生次数
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    
    # 派生变体
    variants: List[str] = field(default_factory=list)  # 变体模式ID
    
    def get_pattern_signature(self) -> str:
        """获取模式签名"""
        signature_data = f"{self.category.value}:{self.root_cause_type}:{':'.join(sorted(self.message_keywords))}"
        return hashlib.sha256(signature_data.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "category": self.category.value,
            "severity": self.severity.value,
            "root_cause_type": self.root_cause_type,
            "error_type_pattern": self.error_type_pattern,
            "message_keywords": self.message_keywords,
            "trigger_conditions": self.trigger_conditions,
            "affected_systems": self.affected_systems,
            "impact_scope": self.impact_scope,
            "related_patterns": self.related_patterns,
            "derived_from": self.derived_from,
            "occurrence_count": self.occurrence_count,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "variants": self.variants,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 修复方案层
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FixStep:
    """修复步骤"""
    step_id: int
    description: str                     # 步骤描述
    action_type: str                     # 动作类型：check/fix/verify/configure
    command: Optional[str] = None        # 执行命令
    parameters: Dict[str, Any] = field(default_factory=dict)  # 参数
    risk_level: str = "low"             # 风险等级：low/medium/high
    reversible: bool = True              # 是否可逆
    requires_confirm: bool = False       # 是否需要确认


@dataclass
class FixTemplate:
    """
    修复方案模板
    
    可复用的修复方案
    """
    # 模板标识（必需）
    template_id: str
    template_name: str                   # 模板名称
    
    # 适用范围（必需）
    applicable_patterns: List[str]      # 适用的模式ID列表
    applicable_categories: List[ErrorCategory]  # 适用的类别
    applicable_contexts: List[str]      # 适用的上下文类型
    
    # 修复方案（必需）
    steps: List[FixStep]                 # 修复步骤
    verification_method: str            # 验证方法描述
    
    # 可选字段
    version: str = "1.0"                 # 版本
    estimated_duration: float = 60.0    # 预估耗时（秒）
    verification_command: Optional[str] = None  # 验证命令
    prevention_tips: List[str] = field(default_factory=list)  # 预防建议
    context_requirements: Dict[str, Any] = field(default_factory=dict)  # 上下文要求
    dependencies: List[str] = field(default_factory=list)  # 依赖的模板
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    avg_execution_time: float = 0.0
    created_by: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    @property
    def confidence(self) -> FixConfidence:
        """置信度"""
        rate = self.success_rate
        usage = self.success_count + self.failure_count
        
        if rate >= 0.8 and usage >= 5:
            return FixConfidence.HIGH
        elif rate >= 0.5 and usage >= 2:
            return FixConfidence.MEDIUM
        elif usage > 0:
            return FixConfidence.LOW
        return FixConfidence.UNKNOWN
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "version": self.version,
            "applicable_patterns": self.applicable_patterns,
            "applicable_categories": [c.value for c in self.applicable_categories],
            "applicable_contexts": self.applicable_contexts,
            "steps": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "action_type": s.action_type,
                    "command": s.command,
                    "parameters": s.parameters,
                    "risk_level": s.risk_level,
                    "reversible": s.reversible,
                    "requires_confirm": s.requires_confirm,
                }
                for s in self.steps
            ],
            "estimated_duration": self.estimated_duration,
            "verification_method": self.verification_method,
            "verification_command": self.verification_command,
            "prevention_tips": self.prevention_tips,
            "context_requirements": self.context_requirements,
            "dependencies": self.dependencies,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "avg_execution_time": self.avg_execution_time,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 完整错误记录
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ErrorRecord:
    """
    完整错误记录
    
    包含三层知识表示的完整错误案例
    """
    # 记录标识
    record_id: str
    fingerprint: str                    # 错误指纹
    
    # 表层特征
    surface: ErrorSurfaceFeatures
    
    # 识别出的模式
    matched_pattern: Optional[ErrorPattern] = None
    pattern_confidence: float = 0.0     # 模式匹配置信度
    
    # 修复方案
    applied_template: Optional[FixTemplate] = None
    fix_status: FixStatus = FixStatus.PENDING
    custom_steps: List[str] = field(default_factory=list)  # 自定义步骤
    
    # 修复历史
    fix_attempts: List[Dict[str, Any]] = field(default_factory=list)
    successful_fix: Optional[str] = None  # 成功修复的描述
    
    # 上下文
    session_context: Dict[str, Any] = field(default_factory=dict)  # 会话上下文
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    
    # 标签
    tags: List[str] = field(default_factory=list)
    
    def add_fix_attempt(
        self,
        template_id: str,
        success: bool,
        execution_time: float,
        error_message: Optional[str] = None,
    ):
        """添加修复尝试"""
        self.fix_attempts.append({
            "template_id": template_id,
            "success": success,
            "execution_time": execution_time,
            "error_message": error_message,
            "attempted_at": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()
    
    def mark_resolved(self, template_id: str):
        """标记为已解决"""
        self.fix_status = FixStatus.SUCCESS
        self.resolved_at = datetime.now()
        self.successful_fix = template_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "fingerprint": self.fingerprint,
            "surface": self.surface.to_dict(),
            "matched_pattern": self.matched_pattern.to_dict() if self.matched_pattern else None,
            "pattern_confidence": self.pattern_confidence,
            "applied_template": self.applied_template.to_dict() if self.applied_template else None,
            "fix_status": self.fix_status.value,
            "custom_steps": self.custom_steps,
            "fix_attempts": self.fix_attempts,
            "successful_fix": self.successful_fix,
            "session_context": self.session_context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "tags": self.tags,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 模式匹配结果
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PatternMatchResult:
    """模式匹配结果"""
    pattern: ErrorPattern
    confidence: float                   # 置信度 0-1
    matched_features: Dict[str, Any]    # 匹配到的特征
    missing_features: List[str]          # 缺失的特征
    similarity_score: float             # 相似度分数
    
    # 推荐模板
    recommended_templates: List[FixTemplate] = field(default_factory=list)
    template_scores: Dict[str, float] = field(default_factory=dict)
    
    # 上下文适应度
    context_fitness: float = 0.5        # 上下文适应度 0-1


# ═══════════════════════════════════════════════════════════════════════════════
# 预定义错误模式库
# ═══════════════════════════════════════════════════════════════════════════════

PRESET_PATTERNS = {
    "encoding_mismatch": ErrorPattern(
        pattern_id="encoding_mismatch",
        pattern_name="字符编码不匹配",
        category=ErrorCategory.ENCODING,
        severity=ErrorSeverity.WARNING,
        root_cause_type="encoding_mismatch",
        error_type_pattern=".*Decode.*Error|.*Encode.*Error",
        message_keywords=["utf-8", "gbk", "codec", "decode", "encode", "codec can't decode"],
        trigger_conditions=["读取文件", "网络请求", "数据库连接"],
        affected_systems=["file_io", "network", "database"],
        impact_scope="数据读写异常，可能导致信息丢失或乱码",
    ),
    
    "file_not_found": ErrorPattern(
        pattern_id="file_not_found",
        pattern_name="文件未找到",
        category=ErrorCategory.FILE_IO,
        severity=ErrorSeverity.WARNING,
        root_cause_type="path_error",
        error_type_pattern="FileNotFoundError|FileExistsError|No such file",
        message_keywords=["not found", "no such file", "exists"],
        trigger_conditions=["读取文件", "打开文件", "导入模块"],
        affected_systems=["file_io", "import_system"],
        impact_scope="程序无法访问指定资源",
    ),
    
    "network_timeout": ErrorPattern(
        pattern_id="network_timeout",
        pattern_name="网络超时",
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.WARNING,
        root_cause_type="timeout",
        error_type_pattern="TimeoutError|RequestTimeout|ConnectionTimeout",
        message_keywords=["timeout", "timed out", "connection timeout"],
        trigger_conditions=["HTTP请求", "数据库连接", "远程调用"],
        affected_systems=["network", "database", "api_client"],
        impact_scope="外部服务调用失败，可能影响业务流程",
    ),
    
    "import_error": ErrorPattern(
        pattern_id="import_error",
        pattern_name="模块导入错误",
        category=ErrorCategory.DEPENDENCY,
        severity=ErrorSeverity.CRITICAL,
        root_cause_type="missing_dependency",
        error_type_pattern="ImportError|ModuleNotFoundError|Cannot import",
        message_keywords=["cannot import", "no module named", "import error"],
        trigger_conditions=["导入模块", "启动应用", "运行脚本"],
        affected_systems=["python_runtime", "dependency_manager"],
        impact_scope="程序无法启动或特定功能不可用",
    ),
    
    "syntax_error": ErrorPattern(
        pattern_id="syntax_error",
        pattern_name="语法错误",
        category=ErrorCategory.SYNTAX,
        severity=ErrorSeverity.BLOCKING,
        root_cause_type="syntax_mistake",
        error_type_pattern="SyntaxError|IndentationError|TabError",
        message_keywords=["syntax error", "invalid syntax", "expected", "indentation"],
        trigger_conditions=["解析代码", "执行脚本", "导入模块"],
        affected_systems=["python_parser", "ide"],
        impact_scope="代码无法执行",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# 预定义修复模板库
# ═══════════════════════════════════════════════════════════════════════════════

PRESET_TEMPLATES = {
    "fix_encoding_auto_detect": FixTemplate(
        template_id="fix_encoding_auto_detect",
        template_name="自动检测并修复编码",
        applicable_patterns=["encoding_mismatch"],
        applicable_categories=[ErrorCategory.ENCODING],
        applicable_contexts=["file_read", "network_request"],
        steps=[
            FixStep(step_id=1, description="检测文件实际编码", action_type="check",
                   command="chardet.detect()", risk_level="low"),
            FixStep(step_id=2, description="使用检测到的编码重新读取", action_type="fix",
                   command="open(file, encoding=detected_encoding)", risk_level="low"),
            FixStep(step_id=3, description="转换为UTF-8编码", action_type="fix",
                   command=".encode('utf-8').decode('utf-8')", risk_level="low"),
            FixStep(step_id=4, description="验证修复结果", action_type="verify",
                   risk_level="low"),
        ],
        verification_method="重新执行读取操作，验证无乱码",
        prevention_tips=[
            "处理文件前先检测编码",
            "统一使用UTF-8编码",
            "配置文件指定编码格式",
        ],
    ),
    
    "fix_retry_exponential": FixTemplate(
        template_id="fix_retry_exponential",
        template_name="指数退避重试",
        applicable_patterns=["network_timeout"],
        applicable_categories=[ErrorCategory.NETWORK, ErrorCategory.RUNTIME],
        applicable_contexts=["api_call", "database_query"],
        steps=[
            FixStep(step_id=1, description="捕获超时异常", action_type="check",
                   command="except TimeoutError", risk_level="low"),
            FixStep(step_id=2, description="实现指数退避等待", action_type="fix",
                   parameters={"base_delay": 1, "max_delay": 60, "factor": 2},
                   risk_level="low"),
            FixStep(step_id=3, description="添加最大重试次数限制", action_type="fix",
                   parameters={"max_retries": 3}, risk_level="low"),
            FixStep(step_id=4, description="验证重试机制", action_type="verify",
                   risk_level="low"),
        ],
        estimated_duration=30.0,
        verification_method="模拟超时场景，验证重试行为",
        prevention_tips=[
            "设置合理的超时时间",
            "实现重试机制",
            "记录重试日志",
        ],
    ),
    
    "fix_missing_dependency": FixTemplate(
        template_id="fix_missing_dependency",
        template_name="修复缺失依赖",
        applicable_patterns=["import_error"],
        applicable_categories=[ErrorCategory.DEPENDENCY],
        applicable_contexts=["import_module", "startup"],
        steps=[
            FixStep(step_id=1, description="识别缺失的模块名", action_type="check",
                   command="解析ImportError消息", risk_level="low"),
            FixStep(step_id=2, description="检查是否已安装", action_type="check",
                   command="pip show {module_name}", risk_level="low"),
            FixStep(step_id=3, description="安装缺失的包", action_type="fix",
                   command="pip install {module_name}", risk_level="medium",
                   requires_confirm=True),
            FixStep(step_id=4, description="验证安装", action_type="verify",
                   command="import {module_name}", risk_level="low"),
        ],
        estimated_duration=120.0,
        verification_method="成功导入模块",
        prevention_tips=[
            "使用requirements.txt管理依赖",
            "创建虚拟环境隔离项目",
            "定期更新依赖版本",
        ],
    ),
}
