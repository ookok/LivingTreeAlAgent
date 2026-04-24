# -*- coding: utf-8 -*-
"""
Error Knowledge Base - 错误知识库
================================

智能错误修复记忆与复用系统

核心功能：
1. 错误记录存储和检索
2. 模式匹配和学习
3. 修复方案推荐
4. 知识进化

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from collections import deque
import threading

try:
    from .error_models import (
        ErrorSurfaceFeatures,
        ErrorPattern,
        FixTemplate,
        ErrorRecord,
        FixStatus,
        PRESET_PATTERNS,
        PRESET_TEMPLATES,
    )
except ImportError:
    from error_models import (
        ErrorSurfaceFeatures,
        ErrorPattern,
        FixTemplate,
        ErrorRecord,
        FixStatus,
        PRESET_PATTERNS,
        PRESET_TEMPLATES,
    )

try:
    from .pattern_matcher import ErrorPatternMatcher, MatcherConfig, get_matcher
except ImportError:
    from pattern_matcher import ErrorPatternMatcher, MatcherConfig, get_matcher


# ═══════════════════════════════════════════════════════════════════════════════
# 知识库配置
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class KnowledgeBaseConfig:
    """知识库配置"""
    storage_path: str = "./error_knowledge"  # 存储路径
    max_records: int = 10000                 # 最大记录数
    max_patterns: int = 1000                 # 最大模式数
    max_templates: int = 500                 # 最大模板数
    
    # 自动学习
    auto_learn_enabled: bool = True          # 自动学习新模式
    auto_template_creation: bool = True       # 自动创建模板
    
    # 知识清理
    cleanup_enabled: bool = True              # 自动清理
    min_success_rate: float = 0.3            # 最小成功率阈值
    max_age_days: int = 90                   # 最大保存天数


# ═══════════════════════════════════════════════════════════════════════════════
# 错误知识库
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorKnowledgeBase:
    """
    错误知识库
    
    存储、检索、学习错误修复知识
    """

    def __init__(
        self,
        config: Optional[KnowledgeBaseConfig] = None,
        matcher: Optional[ErrorPatternMatcher] = None,
    ):
        self.config = config or KnowledgeBaseConfig()
        self.matcher = matcher or get_matcher()
        
        # 确保存储目录存在
        os.makedirs(self.config.storage_path, exist_ok=True)
        
        # 存储结构
        self._records: Dict[str, ErrorRecord] = {}
        self._patterns: Dict[str, ErrorPattern] = {}
        self._templates: Dict[str, FixTemplate] = {}
        
        # 索引
        self._fingerprint_index: Dict[str, List[str]] = {}  # fingerprint -> record_ids
        self._category_index: Dict[str, List[str]] = {}  # category -> pattern_ids
        
        # 缓存
        self._recent_records: deque = deque(maxlen=100)
        
        # 锁
        self._lock = threading.RLock()
        
        # 回调
        self._on_new_pattern: Optional[Callable] = None
        self._on_new_template: Optional[Callable] = None
        
        # 加载预定义数据
        self._load_preset_data()
        
        # 加载持久化数据
        self._load_persistent_data()
        
        print(f"[ErrorKnowledgeBase] 已初始化")
        print(f"  - 存储路径: {self.config.storage_path}")
        print(f"  - 预定义模式: {len(PRESET_PATTERNS)}")
        print(f"  - 预定义模板: {len(PRESET_TEMPLATES)}")

    def _load_preset_data(self):
        """加载预定义数据"""
        for pattern_id, pattern in PRESET_PATTERNS.items():
            self._patterns[pattern_id] = pattern
            self.matcher.register_pattern(pattern)
        
        for template_id, template in PRESET_TEMPLATES.items():
            self._templates[template_id] = template
            self.matcher.register_template(template)

    def _load_persistent_data(self):
        """加载持久化数据"""
        records_file = os.path.join(self.config.storage_path, "records.json")
        patterns_file = os.path.join(self.config.storage_path, "patterns.json")
        templates_file = os.path.join(self.config.storage_path, "templates.json")
        
        # 加载记录
        if os.path.exists(records_file):
            try:
                with open(records_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for record_data in data.get("records", []):
                        record = self._deserialize_record(record_data)
                        if record:
                            self._records[record.record_id] = record
                            self._index_record(record)
                print(f"  - 加载记录: {len(self._records)}")
            except Exception as e:
                print(f"  - 加载记录失败: {e}")
        
        # 加载自定义模式
        if os.path.exists(patterns_file):
            try:
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for pattern_data in data.get("patterns", []):
                        try:
                            pattern = self._deserialize_pattern(pattern_data)
                            if pattern:
                                self._patterns[pattern.pattern_id] = pattern
                                self.matcher.register_pattern(pattern)
                        except Exception:
                            pass
                print(f"  - 加载模式: {len(self._patterns)}")
            except Exception as e:
                print(f"  - 加载模式失败: {e}")
        
        # 加载自定义模板
        if os.path.exists(templates_file):
            try:
                with open(templates_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for template_data in data.get("templates", []):
                        try:
                            template = self._deserialize_template(template_data)
                            if template:
                                self._templates[template.template_id] = template
                                self.matcher.register_template(template)
                        except Exception:
                            pass
                print(f"  - 加载模板: {len(self._templates)}")
            except Exception as e:
                print(f"  - 加载模板失败: {e}")

    def _save_persistent_data(self):
        """保存持久化数据"""
        records_file = os.path.join(self.config.storage_path, "records.json")
        patterns_file = os.path.join(self.config.storage_path, "patterns.json")
        templates_file = os.path.join(self.config.storage_path, "templates.json")
        
        try:
            # 保存记录
            with open(records_file, 'w', encoding='utf-8') as f:
                data = {
                    "records": [r.to_dict() for r in self._records.values()],
                    "updated_at": datetime.now().isoformat(),
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 保存自定义模式
            with open(patterns_file, 'w', encoding='utf-8') as f:
                data = {
                    "patterns": [p.to_dict() for p in self._patterns.values()],
                    "updated_at": datetime.now().isoformat(),
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 保存自定义模板
            with open(templates_file, 'w', encoding='utf-8') as f:
                data = {
                    "templates": [t.to_dict() for t in self._templates.values()],
                    "updated_at": datetime.now().isoformat(),
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ErrorKnowledgeBase] 保存失败: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 核心操作
    # ═══════════════════════════════════════════════════════════════════════════

    def record_error(
        self,
        surface: ErrorSurfaceFeatures,
        context: Optional[Dict[str, Any]] = None,
    ) -> ErrorRecord:
        """
        记录错误
        
        Args:
            surface: 错误表层特征
            context: 额外上下文
            
        Returns:
            创建的错误记录
        """
        with self._lock:
            # 生成记录ID和指纹
            record_id = str(uuid.uuid4())
            fingerprint = surface.get_fingerprint()
            
            # 创建记录
            record = ErrorRecord(
                record_id=record_id,
                fingerprint=fingerprint,
                surface=surface,
                session_context=context or {},
            )
            
            # 索引
            self._records[record_id] = record
            self._index_record(record)
            self._recent_records.append(record)
            
            # 模式匹配
            matches = self.matcher.find_matching_patterns(surface, context)
            if matches:
                best_match = matches[0]
                record.matched_pattern = best_match.pattern
                record.pattern_confidence = best_match.confidence
            
            return record

    def find_solution(
        self,
        surface: ErrorSurfaceFeatures,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        查找解决方案
        
        Args:
            surface: 错误表层特征
            context: 额外上下文
            
        Returns:
            包含匹配模式和推荐模板的字典
        """
        # 查找匹配模式
        matches = self.matcher.find_matching_patterns(surface, context)
        
        if not matches:
            return {
                "success": False,
                "message": "未找到匹配的错误模式",
                "suggestion": "请提供更多信息或手动创建错误模式",
            }
        
        best_match = matches[0]
        
        # 获取推荐模板
        templates = best_match.recommended_templates
        if not templates:
            templates = []
        
        return {
            "success": True,
            "matched_pattern": {
                "pattern_id": best_match.pattern.pattern_id,
                "pattern_name": best_match.pattern.pattern_name,
                "confidence": best_match.confidence,
                "category": best_match.pattern.category.value,
                "root_cause": best_match.pattern.root_cause_type,
                "prevention_tips": self._get_pattern_prevention(best_match.pattern),
            },
            "recommended_templates": [
                {
                    "template_id": t.template_id,
                    "template_name": t.template_name,
                    "success_rate": t.success_rate,
                    "confidence": t.confidence.value,
                    "estimated_duration": t.estimated_duration,
                    "steps": [s.description for s in t.steps],
                }
                for t in templates[:3]
            ],
            "alternative_patterns": [
                {
                    "pattern_id": m.pattern.pattern_id,
                    "pattern_name": m.pattern.pattern_name,
                    "confidence": m.confidence,
                }
                for m in matches[1:3]
            ],
        }

    def apply_fix(
        self,
        record_id: str,
        template_id: str,
        success: bool,
        execution_time: float = 0.0,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        应用修复
        
        Args:
            record_id: 错误记录ID
            template_id: 使用的模板ID
            success: 是否成功
            execution_time: 执行时间
            error_message: 错误信息
            
        Returns:
            是否成功
        """
        with self._lock:
            if record_id not in self._records:
                return False
            
            record = self._records[record_id]
            template = self._templates.get(template_id)
            
            # 记录修复尝试
            record.add_fix_attempt(
                template_id=template_id,
                success=success,
                execution_time=execution_time,
                error_message=error_message,
            )
            
            # 更新模板统计
            if template:
                if success:
                    template.success_count += 1
                else:
                    template.failure_count += 1
            
            # 更新模式统计
            if record.matched_pattern:
                pattern = record.matched_pattern
                pattern.occurrence_count += 1
                pattern.last_seen = datetime.now()
            
            # 标记成功
            if success:
                record.mark_resolved(template_id)
                
                # 从修复中学习
                if self.config.auto_learn_enabled:
                    self._learn_from_fix(record, template)
            
            return True

    def learn_from_fix(
        self,
        record_id: str,
        custom_fix_steps: List[str],
        success: bool,
    ) -> Optional[str]:
        """
        从修复中学习，创建新模板
        
        Args:
            record_id: 错误记录ID
            custom_fix_steps: 自定义修复步骤
            success: 是否成功
            
        Returns:
            新创建的模板ID，如果没有学习到则返回None
        """
        if not success or not custom_fix_steps:
            return None
        
        with self._lock:
            if record_id not in self._records:
                return None
            
            record = self._records[record_id]
            
            # 检查是否需要创建新模板
            if record.matched_pattern:
                existing_templates = [
                    t for t in self._templates.values()
                    if record.matched_pattern.pattern_id in t.applicable_patterns
                ]
                
                # 如果没有现有模板或现有模板效果不好，创建新的
                if not existing_templates or all(t.success_rate < 0.7 for t in existing_templates):
                    # 创建新模板
                    template_id = self._create_template_from_fix(record, custom_fix_steps)
                    return template_id
            
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════════════════════

    def _index_record(self, record: ErrorRecord):
        """索引记录"""
        # 指纹索引
        fp = record.fingerprint
        if fp not in self._fingerprint_index:
            self._fingerprint_index[fp] = []
        self._fingerprint_index[fp].append(record.record_id)
        
        # 类别索引
        if record.matched_pattern:
            cat = record.matched_pattern.category.value
            if cat not in self._category_index:
                self._category_index[cat] = []
            self._category_index[cat].append(record.matched_pattern.pattern_id)

    def _get_pattern_prevention(self, pattern: ErrorPattern) -> List[str]:
        """获取模式的预防建议"""
        prevention = []
        
        for template in self._templates.values():
            if pattern.pattern_id in template.applicable_patterns:
                prevention.extend(template.prevention_tips)
        
        return list(set(prevention))[:5]

    def _learn_from_fix(self, record: ErrorRecord, template: Optional[FixTemplate]):
        """从修复中学习"""
        # 更新模式统计
        if record.matched_pattern:
            pattern = record.matched_pattern
            pattern.occurrence_count += 1
            
            # 如果成功率提高，可以提升置信度
            if template and template.success_rate > 0.8:
                # 潜在的自动注册逻辑
                pass

    def _create_template_from_fix(
        self,
        record: ErrorRecord,
        fix_steps: List[str],
    ) -> Optional[str]:
        """从修复创建模板"""
        if not record.matched_pattern:
            return None
        
        template_id = f"auto_{record.matched_pattern.pattern_id}_{len(fix_steps)}"
        
        from .error_models import FixStep
        
        steps = [
            FixStep(
                step_id=i + 1,
                description=step,
                action_type="custom",
            )
            for i, step in enumerate(fix_steps)
        ]
        
        template = FixTemplate(
            template_id=template_id,
            template_name=f"自动生成: {record.matched_pattern.pattern_name}",
            applicable_patterns=[record.matched_pattern.pattern_id],
            applicable_categories=[record.matched_pattern.category],
            steps=steps,
            success_count=1,
            created_by="auto_learner",
        )
        
        self._templates[template_id] = template
        self.matcher.register_template(template)
        
        # 触发回调
        if self._on_new_template:
            self._on_new_template(template)
        
        return template_id

    # ═══════════════════════════════════════════════════════════════════════════
    # 序列化/反序列化
    # ═══════════════════════════════════════════════════════════════════════════

    def _deserialize_record(self, data: Dict) -> Optional[ErrorRecord]:
        """反序列化记录"""
        try:
            from .error_models import ErrorCategory
            
            surface_data = data.get("surface", {})
            surface = ErrorSurfaceFeatures(
                raw_message=surface_data.get("raw_message", ""),
                error_type=surface_data.get("error_type", ""),
                error_code=surface_data.get("error_code"),
                occurred_at=datetime.fromisoformat(surface_data.get("occurred_at", datetime.now().isoformat())),
            )
            
            record = ErrorRecord(
                record_id=data.get("record_id", str(uuid.uuid4())),
                fingerprint=data.get("fingerprint", ""),
                surface=surface,
                fix_status=FixStatus(data.get("fix_status", "pending")),
                custom_steps=data.get("custom_steps", []),
                fix_attempts=data.get("fix_attempts", []),
                successful_fix=data.get("successful_fix"),
                session_context=data.get("session_context", {}),
            )
            
            return record
        except Exception:
            return None

    def _deserialize_pattern(self, data: Dict) -> Optional[ErrorPattern]:
        """反序列化模式"""
        try:
            from .error_models import ErrorCategory, ErrorSeverity
            
            return ErrorPattern(
                pattern_id=data.get("pattern_id", ""),
                pattern_name=data.get("pattern_name", ""),
                category=ErrorCategory(data.get("category", "unknown")),
                severity=ErrorSeverity(data.get("severity", "warning")),
                root_cause_type=data.get("root_cause_type", ""),
                error_type_pattern=data.get("error_type_pattern", ""),
                message_keywords=data.get("message_keywords", []),
                trigger_conditions=data.get("trigger_conditions", []),
                affected_systems=data.get("affected_systems", []),
                impact_scope=data.get("impact_scope", ""),
            )
        except Exception:
            return None

    def _deserialize_template(self, data: Dict) -> Optional[FixTemplate]:
        """反序列化模板"""
        try:
            from .error_models import ErrorCategory, FixStep
            
            steps = [
                FixStep(
                    step_id=s.get("step_id", i + 1),
                    description=s.get("description", ""),
                    action_type=s.get("action_type", "unknown"),
                    command=s.get("command"),
                    parameters=s.get("parameters", {}),
                    risk_level=s.get("risk_level", "low"),
                    reversible=s.get("reversible", True),
                    requires_confirm=s.get("requires_confirm", False),
                )
                for i, s in enumerate(data.get("steps", []))
            ]
            
            return FixTemplate(
                template_id=data.get("template_id", ""),
                template_name=data.get("template_name", ""),
                applicable_patterns=data.get("applicable_patterns", []),
                applicable_categories=[
                    ErrorCategory(c) for c in data.get("applicable_categories", [])
                ],
                steps=steps,
                verification_method=data.get("verification_method", ""),
                prevention_tips=data.get("prevention_tips", []),
                success_count=data.get("success_count", 0),
                failure_count=data.get("failure_count", 0),
            )
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # 统计和查询
    # ═══════════════════════════════════════════════════════════════════════════

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total_records = len(self._records)
            resolved = sum(1 for r in self._records.values() if r.fix_status.value == "success")
            
            # 按类别统计
            category_stats = {}
            for pattern in self._patterns.values():
                cat = pattern.category.value
                category_stats[cat] = category_stats.get(cat, 0) + pattern.occurrence_count
            
            # 模板成功率
            template_stats = [
                {
                    "template_id": t.template_id,
                    "success_rate": t.success_rate,
                    "usage_count": t.success_count + t.failure_count,
                }
                for t in self._templates.values()
            ]
            template_stats.sort(key=lambda x: x["usage_count"], reverse=True)
            
            return {
                "total_records": total_records,
                "resolved_records": resolved,
                "resolution_rate": resolved / total_records if total_records > 0 else 0,
                "total_patterns": len(self._patterns),
                "total_templates": len(self._templates),
                "category_stats": category_stats,
                "top_templates": template_stats[:5],
                "recent_records": len(self._recent_records),
            }

    def find_similar_errors(self, fingerprint: str) -> List[ErrorRecord]:
        """查找相似错误"""
        record_ids = self._fingerprint_index.get(fingerprint, [])
        return [self._records[rid] for rid in record_ids if rid in self._records]

    def set_on_new_template_callback(self, callback: Callable):
        """设置新模板回调"""
        self._on_new_template = callback


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════

_kb: Optional[ErrorKnowledgeBase] = None


def get_knowledge_base() -> ErrorKnowledgeBase:
    """获取知识库实例"""
    global _kb
    if _kb is None:
        _kb = ErrorKnowledgeBase()
    return _kb
