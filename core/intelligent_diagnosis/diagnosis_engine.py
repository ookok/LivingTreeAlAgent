#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnosis Engine - 智能诊断引擎
================================

功能：
1. 模式识别与关联分析
2. 根因分析（决策树、相关性、时序分析）
3. 诊断结果生成
4. 修复建议推荐

技术选型：
- 内置实现：基于规则的诊断
- 可扩展：支持插件化的专业诊断器

Usage:
    engine = DiagnosisEngine()
    result = engine.diagnose(error_entry)
    print(result.probable_cause, result.confidence, result.suggested_fix)
"""

import os
import re
import json
import threading
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

from .structured_logger import (
    StructuredLogger,
    ErrorCategory,
    STANDARD_ERROR_CODES,
    get_logger,
    LogLevel
)


class ConfidenceLevel(Enum):
    """置信度级别"""
    VERY_HIGH = "VERY_HIGH"  # >= 0.9
    HIGH = "HIGH"            # >= 0.7
    MEDIUM = "MEDIUM"        # >= 0.5
    LOW = "LOW"              # >= 0.3
    VERY_LOW = "VERY_LOW"    # < 0.3


@dataclass
class DiagnosisResult:
    """诊断结果"""
    error_code: str
    error_category: ErrorCategory
    probable_cause: str
    confidence: float  # 0.0 - 1.0
    confidence_level: ConfidenceLevel
    suggested_fix: str
    auto_fix_possible: bool
    related_errors: List[Dict[str, Any]] = field(default_factory=list)
    pattern_match: Optional[str] = None
    root_cause: Optional[str] = None
    fix_history: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "error_category": self.error_category.value,
            "probable_cause": self.probable_cause,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "suggested_fix": self.suggested_fix,
            "auto_fix_possible": self.auto_fix_possible,
            "related_errors": self.related_errors,
            "pattern_match": self.pattern_match,
            "root_cause": self.root_cause,
            "fix_history": self.fix_history,
            "metadata": self.metadata
        }


class DiagnosisPattern:
    """
    诊断模式定义

    模式匹配规则：
    - 关键词匹配
    - 正则匹配
    - 上下文匹配
    - 时序匹配
    """

    def __init__(
        self,
        pattern_id: str,
        name: str,
        description: str,
        keywords: Optional[List[str]] = None,
        regex: Optional[str] = None,
        error_category: Optional[ErrorCategory] = None,
        required_context_keys: Optional[List[str]] = None,
        probability: float = 0.5
    ):
        self.pattern_id = pattern_id
        self.name = name
        self.description = description
        self.keywords = keywords or []
        self.regex = re.compile(regex) if regex else None
        self.error_category = error_category
        self.required_context_keys = required_context_keys or []
        self.base_probability = probability

    def match(self, entry: Dict[str, Any]) -> Tuple[bool, float]:
        """
        检查是否匹配此模式

        Returns:
            (is_match, confidence)
        """
        score = 0.0
        max_score = 0.0

        # 关键词匹配
        if self.keywords:
            max_score += len(self.keywords)
            message = entry.get("message", "").lower()
            context_str = json.dumps(entry.get("context", {}), ensure_ascii=False).lower()

            for kw in self.keywords:
                if kw.lower() in message or kw.lower() in context_str:
                    score += 1.0

        # 正则匹配
        if self.regex:
            max_score += 1.0
            text = entry.get("message", "")
            if self.regex.search(text):
                score += 1.0

        # 上下文键匹配
        if self.required_context_keys:
            max_score += len(self.required_context_keys)
            context = entry.get("context", {})
            for key in self.required_context_keys:
                if key in context:
                    score += 1.0

        # 分类匹配
        if self.error_category:
            max_score += 1.0
            if entry.get("error_category") == self.error_category.value:
                score += 1.0

        if max_score == 0:
            return False, 0.0

        confidence = (score / max_score) * self.base_probability
        return confidence > 0.3, confidence


class RootCauseChain:
    """
    根因链分析

    分析错误之间的因果关系：
    1. 时间序列：同一时间段内的多个错误
    2. 依赖关系：错误之间的依赖
    3. 传播路径：错误如何传播
    """

    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)  # error_id -> [dependent_ids]

    def add_error(self, error_entry: Dict[str, Any]):
        """添加错误到链"""
        error_id = error_entry.get("error_code") or str(hash(error_entry.get("message", "")))
        self.errors.append({**error_entry, "error_id": error_id})

    def build_chain(self):
        """构建错误因果链"""
        # 按时间排序
        self.errors.sort(key=lambda x: x.get("timestamp", ""))

        # 简单的时间窗口关联（5分钟内）
        time_window = timedelta(minutes=5)

        for i, err in enumerate(self.errors):
            for j, other in enumerate(self.errors[i+1:], i+1):
                if self._is_related(err, other, time_window):
                    self.adjacency[err["error_id"]].add(other["error_id"])

    def _is_related(self, err1: Dict, err2: Dict, window: timedelta) -> bool:
        """检查两个错误是否相关"""
        # 时间接近性
        try:
            t1 = datetime.fromisoformat(err1.get("timestamp", ""))
            t2 = datetime.fromisoformat(err2.get("timestamp", ""))
            if abs(t1 - t2) > window:
                return False
        except:
            pass

        # 共享上下文
        ctx1 = set(err1.get("context", {}).keys())
        ctx2 = set(err2.get("context", {}).keys())
        if ctx1 & ctx2:  # 有共同的上下文键
            return True

        # 相同的错误分类
        if err1.get("error_category") == err2.get("error_category"):
            return True

        return False

    def find_root_cause(self) -> Optional[str]:
        """找到根因（入度为0的错误）"""
        if not self.errors:
            return None

        all_dependents = set()
        for deps in self.adjacency.values():
            all_dependents.update(deps)

        # 根因是没有被任何其他错误依赖的错误
        for err in self.errors:
            if err["error_id"] not in all_dependents:
                return err["error_id"]

        # 如果都是相互依赖，返回最早的
        return self.errors[0]["error_id"] if self.errors else None


class DiagnosisEngine:
    """
    智能诊断引擎

    功能：
    1. 基于模式的诊断
    2. 根因分析
    3. 关联分析
    4. 诊断知识库学习
    """

    _instance: Optional['DiagnosisEngine'] = None
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

        self.logger = get_logger("diagnosis_engine")

        # 诊断模式库
        self.patterns: List[DiagnosisPattern] = []
        self._init_default_patterns()

        # 历史诊断记录（用于学习）
        self.diagnosis_history: deque = deque(maxlen=1000)

        # 诊断计数（用于模式优化）
        self.pattern_usage: Dict[str, int] = defaultdict(int)

        # 知识库路径
        self.knowledge_dir = os.path.join(
            os.path.expanduser("~"),
            ".living_tree_ai",
            "diagnosis_knowledge"
        )
        os.makedirs(self.knowledge_dir, exist_ok=True)

        self._initialized = True

    def _init_default_patterns(self):
        """初始化默认诊断模式"""

        # 网络超时模式
        self.patterns.append(DiagnosisPattern(
            pattern_id="NET_TIMEOUT",
            name="网络超时",
            description="检测网络超时问题",
            keywords=["timeout", "超时", "timed out", "连接超时"],
            error_category=ErrorCategory.NETWORK,
            probability=0.8
        ))

        # 内存不足模式
        self.patterns.append(DiagnosisPattern(
            pattern_id="MEMORY_LOW",
            name="内存不足",
            description="检测内存不足问题",
            keywords=["memory", "内存", "out of memory", "OOM", "内存不足"],
            error_category=ErrorCategory.RESOURCE,
            probability=0.9
        ))

        # AI模型加载失败
        self.patterns.append(DiagnosisPattern(
            pattern_id="AI_MODEL_FAIL",
            name="AI模型加载失败",
            description="检测AI模型相关错误",
            keywords=["model", "模型", "llama", "load failed", "模型加载"],
            error_category=ErrorCategory.AI_MODEL,
            probability=0.85
        ))

        # 磁盘空间不足
        self.patterns.append(DiagnosisPattern(
            pattern_id="DISK_FULL",
            name="磁盘空间不足",
            description="检测磁盘空间问题",
            keywords=["disk", "磁盘", "space", "空间", "no space", "空间不足"],
            error_category=ErrorCategory.RESOURCE,
            probability=0.9
        ))

        # 连接被拒绝
        self.patterns.append(DiagnosisPattern(
            pattern_id="CONN_REFUSED",
            name="连接被拒绝",
            description="检测连接被拒绝",
            keywords=["refused", "拒绝", "connection refused", "无法连接"],
            error_category=ErrorCategory.NETWORK,
            probability=0.85
        ))

        # 配置错误
        self.patterns.append(DiagnosisPattern(
            pattern_id="CONFIG_ERROR",
            name="配置错误",
            description="检测配置问题",
            keywords=["config", "配置", "configuration", "setting"],
            error_category=ErrorCategory.CONFIG,
            probability=0.7
        ))

        # 服务不可用
        self.patterns.append(DiagnosisPattern(
            pattern_id="SERVICE_DOWN",
            name="服务不可用",
            description="检测依赖服务问题",
            keywords=["unavailable", "不可用", "not available", "服务"],
            error_category=ErrorCategory.DEPENDENCY,
            probability=0.75
        ))

        # 权限不足
        self.patterns.append(DiagnosisPattern(
            pattern_id="PERMISSION_DENIED",
            name="权限不足",
            description="检测权限问题",
            keywords=["permission", "权限", "denied", "拒绝访问", "access denied"],
            error_category=ErrorCategory.PERMISSION,
            probability=0.9
        ))

    def diagnose(
        self,
        error_entry: Dict[str, Any],
        context_errors: Optional[List[Dict[str, Any]]] = None
    ) -> DiagnosisResult:
        """
        诊断错误

        Args:
            error_entry: 错误日志条目
            context_errors: 上下文中的其他相关错误

        Returns:
            DiagnosisResult 诊断结果
        """
        # 1. 模式匹配
        matched_patterns = []
        for pattern in self.patterns:
            is_match, confidence = pattern.match(error_entry)
            if is_match:
                matched_patterns.append((pattern, confidence))

        # 2. 选择最佳匹配
        if matched_patterns:
            matched_patterns.sort(key=lambda x: x[1], reverse=True)
            best_pattern, best_confidence = matched_patterns[0]

            # 更新使用计数
            self.pattern_usage[best_pattern.pattern_id] += 1

            # 构建诊断结果
            result = self._build_diagnosis_result(
                error_entry,
                best_pattern,
                best_confidence,
                context_errors
            )
        else:
            # 无匹配，使用通用诊断
            result = self._generic_diagnosis(error_entry)

        # 3. 根因分析（如果有多条相关错误）
        if context_errors and len(context_errors) > 1:
            root_cause = self._analyze_root_cause(error_entry, context_errors)
            if root_cause:
                result.root_cause = root_cause

        # 4. 记录诊断历史
        self.diagnosis_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_entry": error_entry,
            "result": result.to_dict()
        })

        return result

    def _build_diagnosis_result(
        self,
        error_entry: Dict[str, Any],
        pattern: DiagnosisPattern,
        confidence: float,
        context_errors: Optional[List[Dict[str, Any]]]
    ) -> DiagnosisResult:
        """构建诊断结果"""
        error_code = error_entry.get("error_code") or f"{pattern.pattern_id}_001"
        error_category = ErrorCategory(pattern.error_category.value) if pattern.error_category else ErrorCategory.UNKNOWN

        # 从标准错误码库获取信息
        err_info = STANDARD_ERROR_CODES.get(error_code, {})

        # 生成诊断消息
        cause = self._generate_cause_description(error_entry, pattern)
        fix = self._generate_fix_suggestion(error_entry, pattern, err_info)

        # 置信度级别
        if confidence >= 0.9:
            conf_level = ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.7:
            conf_level = ConfidenceLevel.HIGH
        elif confidence >= 0.5:
            conf_level = ConfidenceLevel.MEDIUM
        elif confidence >= 0.3:
            conf_level = ConfidenceLevel.LOW
        else:
            conf_level = ConfidenceLevel.VERY_LOW

        return DiagnosisResult(
            error_code=error_code,
            error_category=error_category,
            probable_cause=cause,
            confidence=confidence,
            confidence_level=conf_level,
            suggested_fix=fix,
            auto_fix_possible=err_info.get("auto_fix", pattern.base_probability > 0.7),
            related_errors=context_errors[:5] if context_errors else [],
            pattern_match=pattern.name,
            metadata={
                "pattern_id": pattern.pattern_id,
                "match_confidence": confidence
            }
        )

    def _generic_diagnosis(self, error_entry: Dict[str, Any]) -> DiagnosisResult:
        """通用诊断（无模式匹配时）"""
        message = error_entry.get("message", "")
        error_category_str = error_entry.get("error_category", "UNKNOWN")

        try:
            error_category = ErrorCategory(error_category_str)
        except:
            error_category = ErrorCategory.UNKNOWN

        return DiagnosisResult(
            error_code="UNK_001",
            error_category=error_category,
            probable_cause=f"未知错误: {message[:100]}",
            confidence=0.1,
            confidence_level=ConfidenceLevel.VERY_LOW,
            suggested_fix="请查看详细日志或联系技术支持",
            auto_fix_possible=False
        )

    def _generate_cause_description(
        self,
        error_entry: Dict[str, Any],
        pattern: DiagnosisPattern
    ) -> str:
        """生成原因描述"""
        message = error_entry.get("message", "")

        # 基于模式的描述模板
        templates = {
            "NET_TIMEOUT": "网络连接超时，可能原因：网络不稳定、目标服务响应慢、防火墙阻断",
            "MEMORY_LOW": "系统内存不足，可能原因：内存泄漏、大型模型加载、并发任务过多",
            "AI_MODEL_FAIL": "AI模型加载或运行失败，可能原因：模型文件损坏、格式不兼容、显存不足",
            "DISK_FULL": "磁盘空间不足，可能原因：日志文件过多、缓存未清理、大文件占用",
            "CONN_REFUSED": "连接被拒绝，可能原因：服务未启动、端口被占用、防火墙规则",
            "CONFIG_ERROR": "配置错误，可能原因：配置项缺失、值类型错误、路径不存在",
            "SERVICE_DOWN": "依赖服务不可用，可能原因：服务崩溃、资源不足、网络隔离",
            "PERMISSION_DENIED": "权限不足，可能原因：文件权限、系统安全策略、用户组限制",
        }

        return templates.get(pattern.pattern_id, f"检测到{pattern.name}问题")

    def _generate_fix_suggestion(
        self,
        error_entry: Dict[str, Any],
        pattern: DiagnosisPattern,
        err_info: Dict[str, Any]
    ) -> str:
        """生成修复建议"""
        # 已有建议
        if err_info.get("name"):
            return f"建议修复{err_info['name']}问题"

        # 基于模式的建议
        templates = {
            "NET_TIMEOUT": "1. 检查网络连接 2. 尝试重连 3. 增加超时时间",
            "MEMORY_LOW": "1. 清理缓存 2. 关闭其他程序 3. 增加物理内存",
            "AI_MODEL_FAIL": "1. 重新下载模型 2. 检查模型路径 3. 使用更小的模型",
            "DISK_FULL": "1. 清理日志文件 2. 删除缓存 3. 扩展磁盘空间",
            "CONN_REFUSED": "1. 确认目标服务已启动 2. 检查端口配置 3. 检查防火墙",
            "CONFIG_ERROR": "1. 检查配置文件语法 2. 恢复默认配置 3. 查看配置文档",
            "SERVICE_DOWN": "1. 重启服务 2. 检查服务依赖 3. 查看服务日志",
            "PERMISSION_DENIED": "1. 检查文件权限 2. 使用管理员运行 3. 加入正确用户组",
        }

        return templates.get(pattern.pattern_id, "请查看系统文档获取帮助")

    def _analyze_root_cause(
        self,
        primary_error: Dict[str, Any],
        context_errors: List[Dict[str, Any]]
    ) -> Optional[str]:
        """分析根因"""
        chain = RootCauseChain()
        chain.add_error(primary_error)
        for err in context_errors:
            chain.add_error(err)

        chain.build_chain()
        return chain.find_root_cause()

    def add_pattern(self, pattern: DiagnosisPattern):
        """添加诊断模式"""
        self.patterns.append(pattern)
        self.logger.info(f"Added new diagnosis pattern: {pattern.pattern_id}")

    def learn_from_fix(
        self,
        error_entry: Dict[str, Any],
        fix_action: str,
        success: bool
    ):
        """
        从修复中学习

        Args:
            error_entry: 错误条目
            fix_action: 执行的修复动作
            success: 修复是否成功
        """
        # 更新模式置信度
        for pattern, conf in [(p, c) for p in self.patterns for pp, c in [(p, self.pattern_usage.get(p.pattern_id, 0))]]:
            if pattern.match(error_entry)[0]:
                if success:
                    pattern.base_probability = min(1.0, pattern.base_probability * 1.1)
                else:
                    pattern.base_probability *= 0.9

        # 保存学习结果
        self._save_learning_data(error_entry, fix_action, success)

    def _save_learning_data(
        self,
        error_entry: Dict[str, Any],
        fix_action: str,
        success: bool
    ):
        """保存学习数据"""
        learning_file = os.path.join(self.knowledge_dir, "learning_history.jsonl")
        with open(learning_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": error_entry,
                "fix_action": fix_action,
                "success": success
            }, ensure_ascii=False) + "\n")

    def get_statistics(self) -> Dict[str, Any]:
        """获取诊断统计"""
        return {
            "total_patterns": len(self.patterns),
            "total_diagnoses": len(self.diagnosis_history),
            "pattern_usage": dict(self.pattern_usage),
            "category_distribution": self._get_category_distribution()
        }

    def _get_category_distribution(self) -> Dict[str, int]:
        """获取错误分类分布"""
        dist = defaultdict(int)
        for record in self.diagnosis_history:
            cat = record["error_entry"].get("error_category", "UNKNOWN")
            dist[cat] += 1
        return dict(dist)


# 全局实例获取
_diagnosis_engine: Optional[DiagnosisEngine] = None


def get_diagnosis_engine() -> DiagnosisEngine:
    """获取诊断引擎单例"""
    global _diagnosis_engine
    if _diagnosis_engine is None:
        _diagnosis_engine = DiagnosisEngine()
    return _diagnosis_engine


# 便捷函数
def diagnose(error_entry: Dict[str, Any]) -> DiagnosisResult:
    """便捷诊断函数"""
    return get_diagnosis_engine().diagnose(error_entry)


if __name__ == "__main__":
    # 测试诊断引擎
    engine = get_diagnosis_engine()

    # 测试错误条目
    test_errors = [
        {
            "message": "Connection timeout after 5000ms",
            "error_code": "NET_001",
            "error_category": "NETWORK",
            "context": {"host": "127.0.0.1", "port": 11434}
        },
        {
            "message": "Out of memory error",
            "error_code": "RES_001",
            "error_category": "RESOURCE",
            "context": {"memory_used": "15GB", "memory_total": "16GB"}
        }
    ]

    print("=" * 60)
    print("Diagnosis Engine Test")
    print("=" * 60)

    for err in test_errors:
        result = engine.diagnose(err)
        print(f"\n[Input] {err['message']}")
        print(f"[Diagnosis] {result.probable_cause}")
        print(f"[Confidence] {result.confidence:.2f} ({result.confidence_level.value})")
        print(f"[Fix] {result.suggested_fix}")
        print(f"[Auto-fix] {'Yes' if result.auto_fix_possible else 'No'}")

    print("\n" + "=" * 60)
    print("Test completed!")
