"""
PermissionEngine - 动态权限策略引擎
安全不是禁用，是智能授权

核心能力：
- 轻量风险评估器（关键词正则 + 语义分类）
- 风险等级判定（低/中/高/极高）
- PyQt 模态对话框审批
- 权限日志记录

风险分类：
- 低：读取本地文件、搜索内容、计算统计
- 中：生成报告、写入日志、创建文档
- 高：删除文件、执行 shell、发送邮件
- 极高：格式化磁盘、系统底层操作
"""

import re
import json
import time
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, TypedDict
from enum import Enum
from datetime import datetime

# 尝试导入 PyQt5/PyQt6
try:
    from PyQt6.QtWidgets import QMessageBox, QWidget
    from PyQt6.QtCore import QObject, pyqtSignal
    QT_AVAILABLE = True
except ImportError:
    try:
        from PyQt5.QtWidgets import QMessageBox, QWidget
        from PyQt5.QtCore import QObject, pyqtSignal
        QT_AVAILABLE = True
    except ImportError:
        QT_AVAILABLE = False
        QMessageBox = None


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"           # 低风险，自动允许
    MEDIUM = "medium"     # 中风险，提示用户
    HIGH = "high"         # 高风险，需确认
    EXTREME = "extreme"   # 极高风险，强制确认

    @property
    def priority(self) -> int:
        return {"low": 0, "medium": 1, "high": 2, "extreme": 3}[self.value]


class PermissionAction(Enum):
    """权限动作类型"""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    DELETE_FILE = "delete_file"
    EXECUTE_COMMAND = "execute_command"
    NETWORK_REQUEST = "network_request"
    SEND_EMAIL = "send_email"
    SYSTEM_COMMAND = "system_command"
    SENSITIVE_DATA = "sensitive_data"
    UNKNOWN = "unknown"


@dataclass
class PermissionRequest:
    """权限请求"""
    request_id: str
    tool_name: str
    action: PermissionAction
    risk_level: RiskLevel
    details: dict
    prompt: str  # 子任务指令
    timestamp: float = field(default_factory=time.time)
    user_response: Optional[bool] = None
    response_timestamp: Optional[float] = None


@dataclass
class RiskPattern:
    """风险模式"""
    pattern: str  # 正则模式
    action: PermissionAction
    base_risk: RiskLevel
    description: str


class RiskAssessmentResult(TypedDict):
    """风险评估结果"""
    risk_level: str
    action: str
    confidence: float
    matched_patterns: list[str]
    requires_approval: bool
    reason: str


class PermissionEngine:
    """
    动态权限策略引擎

    使用两层评估：
    1. 快速过滤（正则 + 关键词）
    2. 深度分析（LLM 语义分类，可选）

    使用示例：
        engine = PermissionEngine(parent_widget)

        # 添加回调
        engine.on_approval_requested.connect(self.show_approval_dialog)

        # 评估权限
        result = engine.assess("删除文件 C:\\temp\\test.txt")
        if result["requires_approval"]:
            # 显示对话框
            approved = engine.request_approval(result)
        else:
            # 自动执行
            pass
    """

    # 内置风险模式
    BUILTIN_PATTERNS: list[RiskPattern] = [
        # 文件操作
        RiskPattern(r"delete[_\s]*(file|dir|folder)", PermissionAction.DELETE_FILE, RiskLevel.HIGH,
                   "删除文件操作"),
        RiskPattern(r"rm[_\s-]?(rf|fr)", PermissionAction.DELETE_FILE, RiskLevel.EXTREME,
                   "强制删除操作"),
        RiskPattern(r"format\s+(drive|disk|c:)", PermissionAction.SYSTEM_COMMAND, RiskLevel.EXTREME,
                   "格式化磁盘"),
        RiskPattern(r"open\s*\(.*['\"]", PermissionAction.READ_FILE, RiskLevel.LOW,
                   "读取文件"),
        RiskPattern(r"write[_\s]*to[_\s]*file", PermissionAction.WRITE_FILE, RiskLevel.MEDIUM,
                   "写入文件"),

        # 网络操作
        RiskPattern(r"requests?\.get", PermissionAction.NETWORK_REQUEST, RiskLevel.MEDIUM,
                   "HTTP GET 请求"),
        RiskPattern(r"requests?\.post", PermissionAction.NETWORK_REQUEST, RiskLevel.HIGH,
                   "HTTP POST 请求"),
        RiskPattern(r"sendgrid|smtp|send[_\s]*mail", PermissionAction.SEND_EMAIL, RiskLevel.HIGH,
                   "发送邮件"),

        # 系统操作
        RiskPattern(r"subprocess\.|os\.system|popen", PermissionAction.EXECUTE_COMMAND, RiskLevel.HIGH,
                   "执行系统命令"),
        RiskPattern(r"shell\s*=\s*true", PermissionAction.EXECUTE_COMMAND, RiskLevel.EXTREME,
                   "Shell 执行"),
        RiskPattern(r"sudo\s+", PermissionAction.SYSTEM_COMMAND, RiskLevel.EXTREME,
                   "sudo 权限操作"),

        # 敏感数据
        RiskPattern(r"password|passwd|secret", PermissionAction.SENSITIVE_DATA, RiskLevel.HIGH,
                   "敏感数据操作"),
        RiskPattern(r"api[_\s]*(key|token)", PermissionAction.SENSITIVE_DATA, RiskLevel.HIGH,
                   "API Key 操作"),
        RiskPattern(r"eval\(|exec\(", PermissionAction.EXECUTE_COMMAND, RiskLevel.EXTREME,
                   "动态代码执行"),
    ]

    def __init__(
        self,
        parent_widget: Optional[QWidget] = None,
        log_path: Optional[str] = None,
        auto_approve_low: bool = True,
        llm_classifier: Optional[Callable] = None,
    ):
        """
        Args:
            parent_widget: PyQt 父窗口（用于模态对话框）
            log_path: 权限日志路径
            auto_approve_low: 低风险自动批准
            llm_classifier: LLM 分类器（可选，用于深度语义分析）
        """
        self.parent_widget = parent_widget
        self.log_path = Path(log_path) if log_path else Path("permissions.log")
        self.auto_approve_low = auto_approve_low
        self.llm_classifier = llm_classifier

        # 权限规则缓存
        self._rules: dict[str, RiskLevel] = {}
        self._request_history: dict[str, PermissionRequest] = {}
        self._lock = threading.Lock()

        # 统计
        self._stats = {
            "total_requests": 0,
            "approved": 0,
            "denied": 0,
            "auto_approved": 0,
        }

        # 配置日志
        self._setup_logger()

        # 用户偏好（持久化）
        self._user_preferences: dict[str, bool] = {}  # tool_name -> auto_approve

    def _setup_logger(self):
        """设置日志记录器"""
        self.logger = logging.getLogger("PermissionEngine")
        self.logger.setLevel(logging.INFO)

        # 文件处理器
        handler = logging.FileHandler(self.log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self.logger.addHandler(handler)

    def assess(self, prompt: str, tool_name: Optional[str] = None) -> RiskAssessmentResult:
        """
        评估权限请求风险

        Args:
            prompt: 子任务指令
            tool_name: 工具名称（可选）

        Returns:
            风险评估结果
        """
        self._stats["total_requests"] += 1

        # 快速正则过滤
        matched_patterns = []
        detected_action = PermissionAction.UNKNOWN
        max_risk = RiskLevel.LOW

        for rp in self.BUILTIN_PATTERNS:
            if re.search(rp.pattern, prompt, re.IGNORECASE):
                matched_patterns.append(rp.description)
                if rp.action != PermissionAction.UNKNOWN:
                    detected_action = rp.action
                if rp.base_risk.priority > max_risk.priority:
                    max_risk = rp.base_risk

        # 用户自定义规则
        if tool_name and tool_name in self._rules:
            custom_risk = self._rules[tool_name]
            if custom_risk.priority > max_risk.priority:
                max_risk = custom_risk
                matched_patterns.append(f"Custom rule for {tool_name}")

        # LLM 深度分析（可选）
        confidence = 0.6  # 基础置信度
        reason = ""

        if self.llm_classifier and max_risk == RiskLevel.MEDIUM:
            try:
                llm_result = self.llm_classifier(prompt)
                if llm_result:
                    confidence = 0.9
                    matched_patterns.append("LLM semantic analysis")
                    # 可以根据 LLM 结果调整风险等级
            except Exception:
                pass

        # 生成原因描述
        if matched_patterns:
            reason = "; ".join(matched_patterns[:3])  # 最多3个原因
        else:
            reason = "No suspicious patterns detected"
            confidence = 0.4

        # 判断是否需要审批
        requires_approval = (
            max_risk in (RiskLevel.HIGH, RiskLevel.EXTREME)
            or (max_risk == RiskLevel.MEDIUM and not self.auto_approve_low)
        )

        # 检查用户偏好
        if tool_name and tool_name in self._user_preferences:
            if self._user_preferences[tool_name]:
                requires_approval = False
                self._stats["auto_approved"] += 1

        return RiskAssessmentResult(
            risk_level=max_risk.value,
            action=detected_action.value,
            confidence=confidence,
            matched_patterns=matched_patterns,
            requires_approval=requires_approval,
            reason=reason,
        )

    def request_approval(self, assessment: RiskAssessmentResult) -> bool:
        """
        请求用户审批（同步）

        Args:
            assessment: 风险评估结果

        Returns:
            用户是否批准
        """
        risk_level = RiskLevel(assessment["risk_level"])

        # 记录请求
        request = PermissionRequest(
            request_id=self._generate_request_id(),
            tool_name="unknown",
            action=PermissionAction(assessment["action"]),
            risk_level=risk_level,
            details=assessment,
            prompt="",
        )

        # 自动批准低风险
        if risk_level == RiskLevel.LOW and self.auto_approve_low:
            self._grant(request)
            return True

        # 模态对话框审批
        if QT_AVAILABLE and self.parent_widget:
            return self._show_qt_dialog(request)
        else:
            # 无 GUI 时的默认行为
            return risk_level == RiskLevel.MEDIUM

    def _show_qt_dialog(self, request: PermissionRequest) -> bool:
        """
        显示 PyQt 审批对话框

        Args:
            request: 权限请求

        Returns:
            用户是否批准
        """
        if not QT_AVAILABLE:
            return True

        # 根据风险等级设置图标和按钮
        risk = request.risk_level

        if risk == RiskLevel.EXTREME:
            icon = QMessageBox.Icon.Warning
            title = "⚠️ 极高风险操作"
            text = (
                f"检测到极高风险操作：\n\n"
                f"类型：{request.action.value}\n"
                f"原因：{request.details.get('reason', 'N/A')}\n\n"
                f"此操作可能导致系统不可用或数据丢失。\n"
                f"是否继续？"
            )
        elif risk == RiskLevel.HIGH:
            icon = QMessageBox.Icon.Question
            title = "🔒 高风险操作"
            text = (
                f"检测到高风险操作：\n\n"
                f"类型：{request.action.value}\n"
                f"原因：{request.details.get('reason', 'N/A')}\n\n"
                f"是否允许执行？"
            )
        else:
            icon = QMessageBox.Icon.Information
            title = "📋 操作确认"
            text = f"是否允许此操作？"

        msg_box = QMessageBox(self.parent_widget)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        # 设置默认按钮
        if risk in (RiskLevel.HIGH, RiskLevel.EXTREME):
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        else:
            msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

        # 添加复选框（记住选择）
        from PyQt6.QtWidgets import QCheckBox
        from PyQt5.QtWidgets import QCheckBox as QCheckBox5

        if risk == RiskLevel.HIGH:
            check_box = QCheckBox("记住我的选择（自动批准此类操作）") if QT_AVAILABLE else None
        else:
            check_box = None

        msg_box.exec()

        # 获取用户选择
        response = msg_box.result() == QMessageBox.StandardButton.Yes

        # 更新请求结果
        request.user_response = response
        request.response_timestamp = time.time()

        # 记录日志
        if response:
            self._grant(request)
        else:
            self._deny(request)

        # 保存用户偏好
        if check_box and check_box.isChecked():
            tool_name = request.details.get("tool_name")
            if tool_name:
                self._user_preferences[tool_name] = response

        return response

    def _generate_request_id(self) -> str:
        """生成唯一请求ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]

    def _grant(self, request: PermissionRequest):
        """记录授权"""
        self._stats["approved"] += 1
        self.logger.info(f"GRANTED | {request.request_id} | {request.action.value} | {request.details.get('risk_level')}")
        request.user_response = True
        request.response_timestamp = time.time()
        self._request_history[request.request_id] = request

    def _deny(self, request: PermissionRequest):
        """记录拒绝"""
        self._stats["denied"] += 1
        self.logger.warning(f"DENIED | {request.request_id} | {request.action.value} | {request.details.get('risk_level')}")
        request.user_response = False
        request.response_timestamp = time.time()
        self._request_history[request.request_id] = request

    def set_rule(self, tool_name: str, risk_level: RiskLevel):
        """
        设置自定义规则

        Args:
            tool_name: 工具名称
            risk_level: 风险等级
        """
        with self._lock:
            self._rules[tool_name] = risk_level
        self.logger.info(f"RULE SET | {tool_name} -> {risk_level.value}")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self._stats.copy()

    def get_history(self, limit: int = 100) -> list[dict]:
        """获取权限历史"""
        history = sorted(
            self._request_history.values(),
            key=lambda r: r.timestamp,
            reverse=True
        )[:limit]

        return [
            {
                "request_id": r.request_id,
                "action": r.action.value,
                "risk_level": r.risk_level.value,
                "response": "approved" if r.user_response else "denied",
                "timestamp": datetime.fromtimestamp(r.timestamp).isoformat(),
            }
            for r in history
        ]

    def export_log(self, path: Optional[str] = None) -> str:
        """导出日志"""
        target = Path(path) if path else self.log_path
        return str(target)


# ── 信号类（跨线程通信）─────────────────────────────────────────────

if QT_AVAILABLE:
    class PermissionSignals(QObject):
        """权限事件信号"""
        approval_requested = None  # pyqtSignal(dict)
        operation_granted = None
        operation_denied = None
        risk_level_changed = None
