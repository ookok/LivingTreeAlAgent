#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Error Classifier - 错误分类引擎
================================

功能：
1. 错误自动分类
2. 错误码管理
3. 错误模式识别

错误分类体系：
A. 系统级错误
   - RESOURCE: 资源不足 (内存/CPU/存储)
   - DEPENDENCY: 依赖服务不可用
   - CONFIG: 配置错误

B. 应用级错误
   - VALIDATION: 输入验证失败
   - BUSINESS: 业务逻辑错误
   - DATA: 数据一致性错误

C. 网络级错误
   - NETWORK: 网络连接错误
   - TIMEOUT: 操作超时
   - PROTOCOL: 协议错误

D. 用户级错误
   - PERMISSION: 权限不足
   - INPUT_FORMAT: 输入格式错误
   - INVALID_OP: 无效操作

E. AI相关错误
   - AI_MODEL: AI模型错误
   - AI_INFERENCE: AI推理错误
   - AI_CONTEXT: 上下文错误

Usage:
    from client.src.business.intelligent_diagnosis import classify_error

    category = classify_error(exception_or_message)
"""

import re
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .structured_logger import ErrorCategory, StructuredLogger, get_logger


# 错误模式定义
_ERROR_PATTERNS = {
    # 内存相关
    (ErrorCategory.RESOURCE, "memory"): [
        r"out of memory",
        r"oom",
        r"memory error",
        r"内存不足",
        r"memory allocation failed",
        r"cannot allocate",
    ],
    # 磁盘相关
    (ErrorCategory.RESOURCE, "disk"): [
        r"no space left",
        r"disk full",
        r"磁盘空间不足",
        r"space left on device",
    ],
    # CPU相关
    (ErrorCategory.RESOURCE, "cpu"): [
        r"cpu overload",
        r"cpu 100%",
        r"too hot",
        r"thermal throttling",
    ],

    # 网络超时
    (ErrorCategory.TIMEOUT, "timeout"): [
        r"timeout",
        r"timed out",
        r"超时",
        r"connection timeout",
        r"read timeout",
        r"write timeout",
    ],
    # 网络连接
    (ErrorCategory.NETWORK, "connection"): [
        r"connection refused",
        r"connection reset",
        r"connection closed",
        r"连接被拒绝",
        r"连接超时",
        r"无法连接",
        r"host unreachable",
        r"network unreachable",
    ],
    # DNS
    (ErrorCategory.NETWORK, "dns"): [
        r"dns",
        r"name resolution",
        r"域名解析",
        r"getaddrinfo",
    ],

    # AI模型
    (ErrorCategory.AI_MODEL, "model"): [
        r"model not found",
        r"model load failed",
        r"模型加载失败",
        r"invalid model",
        r"model file corrupted",
    ],
    # AI推理
    (ErrorCategory.AI_INFERENCE, "inference"): [
        r"inference failed",
        r"inference error",
        r"推理失败",
        r"generation failed",
    ],
    # 上下文
    (ErrorCategory.AI_CONTEXT, "context"): [
        r"context length",
        r"context overflow",
        r"上下文超限",
        r"too many tokens",
        r"max tokens exceeded",
    ],

    # 配置
    (ErrorCategory.CONFIG, "config"): [
        r"config error",
        r"configuration",
        r"配置错误",
        r"invalid config",
        r"missing config",
    ],
    # 权限
    (ErrorCategory.PERMISSION, "permission"): [
        r"permission denied",
        r"access denied",
        r"权限不足",
        r"forbidden",
        r"unauthorized",
        r"not permitted",
    ],
    # 服务不可用
    (ErrorCategory.DEPENDENCY, "dependency"): [
        r"service unavailable",
        r"service down",
        r"服务不可用",
        r"dependency failed",
        r"dependency not found",
    ],
}


@dataclass
class ClassificationResult:
    """分类结果"""
    category: ErrorCategory
    subcategory: str
    error_code: str
    confidence: float  # 0.0 - 1.0
    matched_pattern: str
    suggested_fix: str
    auto_fixable: bool


class ErrorClassifier:
    """
    错误分类器

    基于规则和模式的错误分类引擎
    """

    _instance: Optional['ErrorClassifier'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.logger = get_logger("error_classifier")

        # 编译正则表达式
        self._compiled_patterns: Dict[Tuple[ErrorCategory, str], List[re.Pattern]] = {}
        for (cat, sub), patterns in _ERROR_PATTERNS.items():
            self._compiled_patterns[(cat, sub)] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        # 分类计数
        self._classification_counts: Dict[ErrorCategory, int] = {}

        self._initialized = True

    def classify(
        self,
        error: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """
        分类错误

        Args:
            error: 错误对象（Exception 或字符串消息）
            context: 可选的上下文信息

        Returns:
            ClassificationResult 分类结果
        """
        # 提取错误消息
        if isinstance(error, Exception):
            message = str(error)
            error_type = type(error).__name__
        else:
            message = str(error)
            error_type = "Unknown"

        # 搜索匹配
        best_match: Optional[Tuple[ErrorCategory, str, float, str]] = None

        for (cat, sub), patterns in self._compiled_patterns.items():
            for pattern in patterns:
                match = pattern.search(message)
                if match:
                    confidence = 0.7 + 0.3 * (len(match.group()) / max(len(message), 1))
                    if best_match is None or confidence > best_match[2]:
                        best_match = (cat, sub, confidence, pattern.pattern)

        # 如果没有匹配
        if best_match is None:
            result = ClassificationResult(
                category=ErrorCategory.UNKNOWN,
                subcategory="unknown",
                error_code=self._generate_error_code(ErrorCategory.UNKNOWN, ""),
                confidence=0.1,
                matched_pattern="",
                suggested_fix="请查看详细日志或联系技术支持",
                auto_fixable=False
            )
        else:
            cat, sub, conf, matched = best_match

            # 更新计数
            self._classification_counts[cat] = self._classification_counts.get(cat, 0) + 1

            result = ClassificationResult(
                category=cat,
                subcategory=sub,
                error_code=self._generate_error_code(cat, sub),
                confidence=conf,
                matched_pattern=matched,
                suggested_fix=self._get_fix_suggestion(cat, sub),
                auto_fixable=self._is_auto_fixable(cat, sub)
            )

        self.logger.debug(f"Classified: {error_type} -> {result.category.value}/{result.subcategory} ({result.confidence:.2f})")
        return result

    def _generate_error_code(self, category: ErrorCategory, subcategory: str) -> str:
        """生成错误码"""
        prefix_map = {
            ErrorCategory.RESOURCE: "RES",
            ErrorCategory.NETWORK: "NET",
            ErrorCategory.TIMEOUT: "TMO",
            ErrorCategory.AI_MODEL: "AIM",
            ErrorCategory.AI_INFERENCE: "INF",
            ErrorCategory.AI_CONTEXT: "CTX",
            ErrorCategory.CONFIG: "CFG",
            ErrorCategory.PERMISSION: "PRM",
            ErrorCategory.DEPENDENCY: "DEP",
            ErrorCategory.VALIDATION: "VAL",
            ErrorCategory.BUSINESS: "BSN",
            ErrorCategory.DATA: "DAT",
            ErrorCategory.PROTOCOL: "PRO",
            ErrorCategory.INPUT_FORMAT: "FMT",
            ErrorCategory.INVALID_OP: "OPR",
            ErrorCategory.UNKNOWN: "UNK",
        }

        prefix = prefix_map.get(category, "UNK")

        # 子类别映射到数字
        sub_map = {
            "memory": "01",
            "disk": "02",
            "cpu": "03",
            "timeout": "01",
            "connection": "01",
            "dns": "02",
            "model": "01",
            "inference": "02",
            "context": "03",
            "config": "01",
            "permission": "01",
            "dependency": "01",
        }

        num = sub_map.get(subcategory, "00")
        return f"{prefix}_{num}"

    def _get_fix_suggestion(self, category: ErrorCategory, subcategory: str) -> str:
        """获取修复建议"""
        suggestions = {
            (ErrorCategory.RESOURCE, "memory"): "1. 清理系统缓存 2. 关闭其他程序 3. 增加物理内存",
            (ErrorCategory.RESOURCE, "disk"): "1. 清理临时文件 2. 删除日志文件 3. 扩展存储空间",
            (ErrorCategory.RESOURCE, "cpu"): "1. 降低并发负载 2. 优化算法 3. 检查恶意软件",
            (ErrorCategory.TIMEOUT, "timeout"): "1. 检查网络连接 2. 增加超时时间 3. 重试操作",
            (ErrorCategory.NETWORK, "connection"): "1. 确认目标服务运行中 2. 检查防火墙 3. 验证网络可达",
            (ErrorCategory.NETWORK, "dns"): "1. 检查DNS配置 2. 使用IP地址直接连接 3. 更换DNS服务器",
            (ErrorCategory.AI_MODEL, "model"): "1. 重新下载模型 2. 验证模型文件完整性 3. 检查模型路径",
            (ErrorCategory.AI_INFERENCE, "inference"): "1. 简化输入 2. 使用更小模型 3. 检查模型兼容性",
            (ErrorCategory.AI_CONTEXT, "context"): "1. 缩短输入长度 2. 启用上下文滚动 3. 使用更大上下文模型",
            (ErrorCategory.CONFIG, "config"): "1. 检查配置文件语法 2. 恢复默认配置 3. 查看配置文档",
            (ErrorCategory.PERMISSION, "permission"): "1. 检查文件权限 2. 使用管理员运行 3. 加入正确用户组",
            (ErrorCategory.DEPENDENCY, "dependency"): "1. 重启依赖服务 2. 检查服务状态 3. 查看服务日志",
        }

        key = (category, subcategory)
        return suggestions.get(key, "请查看系统文档获取帮助")

    def _is_auto_fixable(self, category: ErrorCategory, subcategory: str) -> bool:
        """判断是否可自动修复"""
        auto_fixable = {
            (ErrorCategory.RESOURCE, "disk"): True,
            (ErrorCategory.TIMEOUT, "timeout"): True,
            (ErrorCategory.AI_CONTEXT, "context"): True,
            (ErrorCategory.CONFIG, "config"): True,
        }

        return auto_fixable.get((category, subcategory), False)

    def get_statistics(self) -> Dict[str, Any]:
        """获取分类统计"""
        return {
            "total_classifications": sum(self._classification_counts.values()),
            "by_category": dict(self._classification_counts)
        }


# 便捷函数
_classifier: Optional[ErrorClassifier] = None


def get_classifier() -> ErrorClassifier:
    """获取分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = ErrorClassifier()
    return _classifier


def classify_error(error: Any, context: Optional[Dict[str, Any]] = None) -> ClassificationResult:
    """
    便捷函数：分类错误

    Usage:
        result = classify_error(exception)
        print(result.category, result.suggested_fix)
    """
    return get_classifier().classify(error, context)


if __name__ == "__main__":
    # 测试错误分类
    classifier = get_classifier()

    test_errors = [
        Exception("Connection timeout after 5000ms"),
        Exception("Out of memory error - OOM"),
        Exception("Permission denied: /etc/config"),
        Exception("Model load failed: llama model not found"),
        Exception("Context length exceeded: 4096 > 2048"),
        "Disk full, no space left on device",
        "Unknown error occurred",
    ]

    print("=" * 60)
    print("Error Classifier Test")
    print("=" * 60)

    for err in test_errors:
        result = classifier.classify(err)
        print(f"\nInput: {err}")
        print(f"Category: {result.category.value}/{result.subcategory}")
        print(f"Code: {result.error_code}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Fix: {result.suggested_fix}")
        print(f"Auto-fix: {result.auto_fixable}")

    print("\n" + "=" * 60)
    print("Test completed!")
