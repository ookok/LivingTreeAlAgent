#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NLG Generator - 自然语言生成系统
==================================

功能：
1. 用户友好描述生成
2. 自适应解释模板
3. 多级别输出（新手/高级/开发者）

层级化描述：
1. 简单描述（面向普通用户）
2. 详细描述（面向高级用户）
3. 技术描述（面向开发者）

Usage:
    from business.intelligent_diagnosis import NLGGenerator, UserLevel

    nlg = NLGGenerator()
    desc = nlg.generate(error_entry, UserLevel.NOVICE)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .structured_logger import ErrorCategory
from .diagnosis_engine import DiagnosisResult, ConfidenceLevel


class UserLevel(Enum):
    """用户级别"""
    NOVICE = "novice"          # 新手用户
    INTERMEDIATE = "intermediate"  # 中级用户
    ADVANCED = "advanced"      # 高级用户
    DEVELOPER = "developer"    # 开发者


@dataclass
class NLGConfig:
    """NLG 配置"""
    include_timestamp: bool = True
    include_trace_id: bool = True
    include_technical: bool = False
    include_suggestions: bool = True
    language: str = "zh-CN"  # zh-CN 或 en-US


class NLGGenerator:
    """
    自然语言生成器

    将技术错误信息转换为用户友好的自然语言描述
    """

    # 错误模式到友好消息的映射
    ERROR_MESSAGES = {
        ErrorCategory.NETWORK: {
            "template_novice": "网络连接遇到了问题，请检查您的网络设置后重试。",
            "template_intermediate": "无法连接到目标服务器，可能原因：网络不稳定、服务器无响应、防火墙阻断。",
            "template_advanced": "网络错误：{message}。建议检查网络配置或联系管理员。",
        },
        ErrorCategory.RESOURCE: {
            "template_novice": "系统资源不足，请关闭一些程序后再试。",
            "template_intermediate": "系统资源（内存/磁盘）不足，可能影响系统性能。",
            "template_advanced": "资源错误：{message}。当前资源使用情况：{context}",
        },
        ErrorCategory.AI_MODEL: {
            "template_novice": "AI模型加载失败，请稍后重试。",
            "template_intermediate": "AI模型遇到问题，可能需要重新加载或选择其他模型。",
            "template_advanced": "AI模型错误：{message}。模型路径：{model_path}",
        },
        ErrorCategory.TIMEOUT: {
            "template_novice": "请求超时，请稍后重试。",
            "template_intermediate": "操作响应超时，可能服务器繁忙或网络延迟。",
            "template_advanced": "超时错误：{message}。当前超时设置：{timeout}s",
        },
        ErrorCategory.DEPENDENCY: {
            "template_novice": "某个服务暂时不可用，请稍后重试。",
            "template_intermediate": "依赖的服务（{service}）不可用，请检查服务状态。",
            "template_advanced": "依赖服务错误：{message}。服务：{service}",
        },
        ErrorCategory.CONFIG: {
            "template_novice": "系统配置有问题，请检查设置或联系技术支持。",
            "template_intermediate": "配置项（{config_key}）无效或缺失。",
            "template_advanced": "配置错误：{message}。配置项：{config_key}",
        },
        ErrorCategory.PERMISSION: {
            "template_novice": "您没有权限执行此操作。",
            "template_intermediate": "权限不足，当前用户无法执行此操作。",
            "template_advanced": "权限错误：{message}。所需权限：{required_permission}",
        },
    }

    # 系统友好消息模板
    SYSTEM_MESSAGES = {
        "error_occurred": "抱歉，系统在处理您的请求时遇到了一些问题。",
        "auto_recovery": "系统正在尝试自动恢复...",
        "recovery_success": "系统已自动恢复，您可以继续使用。",
        "recovery_failed": "系统无法自动恢复，建议您刷新页面或联系技术支持。",
        "maintenance": "系统正在进行维护，请稍后再试。",
    }

    def __init__(self, config: Optional[NLGConfig] = None):
        self.config = config or NLGConfig()

    def generate(
        self,
        error_entry: Dict[str, Any],
        user_level: UserLevel = UserLevel.NOVICE,
        diagnosis: Optional[DiagnosisResult] = None
    ) -> str:
        """
        生成用户友好的错误描述

        Args:
            error_entry: 错误日志条目
            user_level: 用户级别
            diagnosis: 可选的诊断结果

        Returns:
            str 用户友好的描述
        """
        category_str = error_entry.get("error_category", "UNKNOWN")
        try:
            category = ErrorCategory(category_str)
        except:
            category = ErrorCategory.UNKNOWN

        message = error_entry.get("message", "")
        context = error_entry.get("context", {})
        error_code = error_entry.get("error_code", "")

        if user_level == UserLevel.NOVICE:
            return self._generate_novice(category, message, error_entry)
        elif user_level == UserLevel.INTERMEDIATE:
            return self._generate_intermediate(category, message, context, diagnosis)
        elif user_level == UserLevel.ADVANCED:
            return self._generate_advanced(category, message, context, error_entry)
        else:  # DEVELOPER
            return self._generate_developer(error_entry, diagnosis)

    def _generate_novice(
        self,
        category: ErrorCategory,
        message: str,
        error_entry: Dict[str, Any]
    ) -> str:
        """为新手用户生成描述"""
        templates = self.ERROR_MESSAGES.get(category, {})
        template = templates.get("template_novice", templates.get("template_intermediate", self.SYSTEM_MESSAGES["error_occurred"]))

        # 简单化技术细节
        if "{message}" in template:
            # 提取最基本的信息
            simple_message = self._simplify_message(message)
            template = template.replace("{message}", simple_message)

        # 添加自动恢复信息
        if error_entry.get("diagnosis", {}).get("auto_fix_possible"):
            template += " 系统正在尝试自动修复..."

        return template

    def _generate_intermediate(
        self,
        category: ErrorCategory,
        message: str,
        context: Dict[str, Any],
        diagnosis: Optional[DiagnosisResult]
    ) -> str:
        """为中级用户生成描述"""
        templates = self.ERROR_MESSAGES.get(category, {})
        template = templates.get("template_intermediate", self.SYSTEM_MESSAGES["error_occurred"])

        # 替换占位符
        replacements = {
            "{message}": self._simplify_message(message),
            "{service}": context.get("service_name", "未知服务"),
            "{config_key}": context.get("config_key", "未知配置"),
        }

        for key, value in replacements.items():
            template = template.replace(key, str(value))

        # 添加建议
        if diagnosis and diagnosis.suggested_fix:
            template += f"\n\n建议：{diagnosis.suggested_fix}"

        # 添加自动处理信息
        if diagnosis and diagnosis.auto_fix_possible:
            template += "\n\n[系统将尝试自动处理]"

        return template

    def _generate_advanced(
        self,
        category: ErrorCategory,
        message: str,
        context: Dict[str, Any],
        error_entry: Dict[str, Any]
    ) -> str:
        """为高级用户生成描述"""
        templates = self.ERROR_MESSAGES.get(category, {})
        template = templates.get("template_advanced",
            f"错误：{message}")

        # 替换占位符
        replacements = {
            "{message}": message,
            "{context}": str(context),
            "{model_path}": context.get("model_path", "未知"),
            "{timeout}": str(context.get("timeout", "N/A")),
            "{service}": context.get("service", "未知"),
            "{config_key}": context.get("config_key", "未知"),
            "{required_permission}": context.get("required_permission", "未知"),
        }

        for key, value in replacements.items():
            template = template.replace(key, str(value))

        # 添加诊断信息
        diagnosis = error_entry.get("diagnosis", {})
        if diagnosis:
            if diagnosis.get("probable_cause"):
                template += f"\n\n可能原因：{diagnosis['probable_cause']}"
            if diagnosis.get("suggested_fix"):
                template += f"\n建议方案：{diagnosis['suggested_fix']}"

        # 添加详细信息
        template += f"\n\n分类：{category.value}"
        if error_entry.get("error_code"):
            template += f"\n错误码：{error_entry['error_code']}"

        return template

    def _generate_developer(
        self,
        error_entry: Dict[str, Any],
        diagnosis: Optional[DiagnosisResult]
    ) -> str:
        """为开发者生成描述"""
        lines = []

        # 头部
        lines.append("=" * 60)
        lines.append("DEVELOPER ERROR REPORT")
        lines.append("=" * 60)

        # 基础信息
        lines.append(f"\n[ERROR CODE] {error_entry.get('error_code', 'N/A')}")
        lines.append(f"[CATEGORY] {error_entry.get('error_category', 'UNKNOWN')}")
        lines.append(f"[TIMESTAMP] {error_entry.get('timestamp', 'N/A')}")

        if self.config.include_trace_id:
            lines.append(f"[TRACE ID] {error_entry.get('trace_id', 'N/A')}")

        # 错误消息
        lines.append(f"\n[MESSAGE]")
        lines.append(error_entry.get('message', 'No message'))

        # 上下文
        if error_entry.get('context'):
            lines.append(f"\n[CONTEXT]")
            for key, value in error_entry['context'].items():
                lines.append(f"  {key}: {value}")

        # 诊断信息
        if diagnosis:
            lines.append(f"\n[DIAGNOSIS]")
            lines.append(f"  Probable Cause: {diagnosis.probable_cause}")
            lines.append(f"  Confidence: {diagnosis.confidence:.2f} ({diagnosis.confidence_level.value})")
            lines.append(f"  Suggested Fix: {diagnosis.suggested_fix}")
            lines.append(f"  Auto-fix Possible: {diagnosis.auto_fix_possible}")
            lines.append(f"  Pattern Match: {diagnosis.pattern_match}")

            if diagnosis.related_errors:
                lines.append(f"\n  Related Errors: {len(diagnosis.related_errors)}")

        # 技术详情
        if error_entry.get('technical_details'):
            lines.append(f"\n[TECHNICAL DETAILS]")
            tech = error_entry['technical_details']
            if tech.get('stack_trace'):
                lines.append("  Stack Trace:")
                for line in tech['stack_trace'][-5:]:  # 只显示最后5行
                    lines.append(f"    {line.strip()}")
            if tech.get('function'):
                lines.append(f"  Function: {tech['function']}")
            if tech.get('line'):
                lines.append(f"  Line: {tech['line']}")

        # 元数据
        if error_entry.get('metadata'):
            lines.append(f"\n[METADATA]")
            for key, value in error_entry['metadata'].items():
                lines.append(f"  {key}: {value}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)

    def _simplify_message(self, message: str) -> str:
        """
        简化技术消息为用户可理解的描述

        例如：
        "Connection timeout after 5000ms to 127.0.0.1:11434"
        -> "连接超时"
        """
        # 时钟超时
        if "timeout" in message.lower() or "超时" in message:
            return "连接超时"

        # 连接被拒绝
        if "refused" in message.lower() or "拒绝" in message:
            return "连接被拒绝"

        # 内存不足
        if "memory" in message.lower() or "内存" in message:
            return "内存不足"

        # 磁盘空间
        if "disk" in message.lower() or "磁盘" in message or "space" in message.lower():
            return "存储空间不足"

        # 权限
        if "permission" in message.lower() or "权限" in message or "denied" in message.lower():
            return "权限不足"

        # 默认：截断长消息
        if len(message) > 50:
            return message[:50] + "..."
        return message

    def generate_recovery_message(
        self,
        success: bool,
        action_taken: str,
        user_level: UserLevel = UserLevel.NOVICE
    ) -> str:
        """
        生成恢复消息

        Args:
            success: 恢复是否成功
            action_taken: 采取的恢复动作
            user_level: 用户级别

        Returns:
            str 恢复消息
        """
        if success:
            if user_level == UserLevel.NOVICE:
                return "问题已解决，系统已恢复正常。"
            elif user_level == UserLevel.DEVELOPER:
                return f"恢复成功。动作：{action_taken}"
            else:
                return f"系统已自动恢复。{action_taken}"
        else:
            if user_level == UserLevel.NOVICE:
                return "系统无法自动解决此问题，建议您刷新页面或联系技术支持。"
            elif user_level == UserLevel.DEVELOPER:
                return f"自动恢复失败。动作：{action_taken}"
            else:
                return f"自动恢复失败。{action_taken}。请手动处理。"

    def generate_batch_summary(
        self,
        errors: List[Dict[str, Any]],
        user_level: UserLevel = UserLevel.NOVICE
    ) -> str:
        """
        生成批量错误的摘要

        Args:
            errors: 错误列表
            user_level: 用户级别

        Returns:
            str 摘要消息
        """
        if not errors:
            return "没有检测到错误。"

        # 按分类统计
        category_counts: Dict[str, int] = {}
        for err in errors:
            cat = err.get("error_category", "UNKNOWN")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        if user_level == UserLevel.NOVICE:
            total = len(errors)
            return f"检测到 {total} 个问题。系统正在处理中..."
        elif user_level == UserLevel.DEVELOPER:
            lines = ["ERROR SUMMARY", "-" * 40]
            for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  {cat}: {count}")
            return "\n".join(lines)
        else:
            lines = [f"检测到 {len(errors)} 个错误："]
            for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  - {cat}: {count}")
            return "\n".join(lines)


# 便捷函数
def generate_user_friendly_error(
    error_entry: Dict[str, Any],
    user_level: UserLevel = UserLevel.NOVICE,
    diagnosis: Optional[DiagnosisResult] = None
) -> str:
    """
    便捷函数：生成用户友好的错误描述

    Usage:
        msg = generate_user_friendly_error(error_entry, UserLevel.NOVICE)
    """
    generator = NLGGenerator()
    return generator.generate(error_entry, user_level, diagnosis)


def generate_recovery_message(
    success: bool,
    action_taken: str,
    user_level: UserLevel = UserLevel.NOVICE
) -> str:
    """便捷函数：生成恢复消息"""
    generator = NLGGenerator()
    return generator.generate_recovery_message(success, action_taken, user_level)


if __name__ == "__main__":
    # 测试 NLG 生成器
    generator = NLGGenerator()

    # 测试错误
    test_errors = [
        {
            "message": "Connection timeout after 5000ms to 127.0.0.1:11434",
            "error_code": "NET_001",
            "error_category": "NETWORK",
            "trace_id": "tr_abc123",
            "context": {"host": "127.0.0.1", "port": 11434},
            "diagnosis": {
                "probable_cause": "网络不稳定",
                "suggested_fix": "检查网络连接",
                "auto_fix_possible": True
            }
        },
        {
            "message": "Out of memory error - allocated 15GB of 16GB",
            "error_code": "RES_001",
            "error_category": "RESOURCE",
            "context": {"memory_used": "15GB", "memory_total": "16GB"}
        }
    ]

    print("=" * 60)
    print("NLG Generator Test")
    print("=" * 60)

    for level in UserLevel:
        print(f"\n### {level.value.upper()} ###")
        for err in test_errors:
            result = generator.generate(err, level)
            print(f"\n[{err['error_category']}] {result[:100]}...")

    print("\n" + "=" * 60)
    print("Test completed!")
