# =================================================================
# 跨页字段记忆 - Form Memory
# =================================================================
# 功能：
# 1. 跨页字段继承（同类型字段自动建议）
# 2. 填表历史记录
# 3. 字段模式识别
# 4. 进度保存与恢复
# =================================================================

import json
import time
import uuid
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict

from .form_parser import FieldSemanticType


@dataclass
class FieldValueRecord:
    """字段值记录"""
    # 标识
    record_id: str
    field_semantic_type: str          # 语义类型
    field_name_pattern: str            # 字段名模式（模糊匹配）
    field_label_pattern: str           # 字段标签模式

    # 值
    value: str
    value_hash: str                   # 值哈希（用于去重）

    # 来源
    source: str                        # "manual", "auto", "ai"
    source_url: str = ""               # 来源页面 URL
    source_domain: str = ""            # 来源域名

    # 统计
    use_count: int = 1                # 使用次数
    success_count: int = 1            # 成功次数（用户采用）
    fail_count: int = 0                # 失败次数（用户拒绝）
    last_used: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    # 标签
    tags: List[str] = field(default_factory=list)
    # 如：["企业信息", "常用", "个人"]

    def update_success(self):
        """更新成功"""
        self.success_count += 1
        self.use_count += 1
        self.last_used = time.time()

    def update_fail(self):
        """更新失败"""
        self.fail_count += 1
        self.use_count += 1

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.use_count == 0:
            return 0.0
        return self.success_count / self.use_count


@dataclass
class FieldPattern:
    """字段模式"""
    pattern_id: str
    domain: str                        # 域名

    # 匹配规则
    field_name_regex: str = ""
    field_label_regex: str = ""
    semantic_type: str = ""

    # 对应的值记录
    value_record_ids: List[str] = field(default_factory=list)

    # 统计
    match_count: int = 0
    last_matched: float = 0

    def add_value_record(self, record_id: str):
        """添加值记录"""
        if record_id not in self.value_record_ids:
            self.value_record_ids.append(record_id)


@dataclass
class FormSession:
    """表单会话（用于进度保存）"""
    session_id: str
    url: str
    domain: str
    form_id: str

    # 字段填充状态
    filled_fields: Dict[str, str] = field(default_factory=dict)
    # {field_name: value}

    # 时间
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float = 0

    # 状态
    is_completed: bool = False
    is_abandoned: bool = False


class FormMemory:
    """
    跨页字段记忆管理器

    功能：
    1. 跨页字段继承
    2. 填表历史
    3. 智能建议排序
    4. 进度保存/恢复
    """

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = str(Path.home() / ".hermes-desktop" / "form_memory")

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 内存缓存
        self._records: Dict[str, FieldValueRecord] = {}
        self._patterns: Dict[str, FieldPattern] = {}
        self._sessions: Dict[str, FormSession] = {}
        self._domains: Dict[str, List[str]] = defaultdict(list)  # domain -> record_ids

        # 加载数据
        self._load_all()

    def _load_all(self):
        """加载所有数据"""
        self._load_records()
        self._load_patterns()
        self._load_sessions()

    def _load_records(self):
        """加载记录"""
        records_file = self.storage_path / "records.json"
        if records_file.exists():
            try:
                with open(records_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for rec_data in data.values():
                        record = FieldValueRecord(**rec_data)
                        self._records[record.record_id] = record
            except Exception:
                pass

    def _load_patterns(self):
        """加载模式"""
        patterns_file = self.storage_path / "patterns.json"
        if patterns_file.exists():
            try:
                with open(patterns_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for pat_data in data.values():
                        pattern = FieldPattern(**pat_data)
                        self._patterns[pattern.pattern_id] = pattern
            except Exception:
                pass

    def _load_sessions(self):
        """加载会话"""
        sessions_file = self.storage_path / "sessions.json"
        if sessions_file.exists():
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for ses_data in data.values():
                        session = FormSession(**ses_data)
                        self._sessions[session.session_id] = session
            except Exception:
                pass

    def _save_records(self):
        """保存记录"""
        records_file = self.storage_path / "records.json"
        data = {rid: asdict(rec) for rid, rec in self._records.items()}
        with open(records_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_patterns(self):
        """保存模式"""
        patterns_file = self.storage_path / "patterns.json"
        data = {pid: asdict(pat) for pid, pat in self._patterns.items()}
        with open(patterns_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_sessions(self):
        """保存会话"""
        sessions_file = self.storage_path / "sessions.json"
        data = {sid: asdict(ses) for sid, ses in self._sessions.items()}
        with open(sessions_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ========== 记录管理 ==========

    def add_record(
        self,
        semantic_type: FieldSemanticType,
        field_name: str,
        field_label: str,
        value: str,
        source: str = "manual",
        source_url: str = "",
        tags: List[str] = None
    ) -> FieldValueRecord:
        """
        添加字段值记录

        Args:
            semantic_type: 字段语义类型
            field_name: 字段名
            field_label: 字段标签
            value: 值
            source: 来源
            source_url: 来源 URL
            tags: 标签

        Returns:
            创建的记录
        """
        # 计算值哈希
        value_hash = hashlib.md5(value.encode()).hexdigest()

        # 检查是否已存在
        for record in self._records.values():
            if record.value_hash == value_hash and record.field_semantic_type == semantic_type.value:
                # 更新使用次数
                record.use_count += 1
                record.last_used = time.time()
                self._save_records()
                return record

        # 创建新记录
        record = FieldValueRecord(
            record_id=str(uuid.uuid4())[:12],
            field_semantic_type=semantic_type.value,
            field_name_pattern=self._create_pattern(field_name),
            field_label_pattern=self._create_pattern(field_label),
            value=value,
            value_hash=value_hash,
            source=source,
            source_url=source_url,
            source_domain=self._extract_domain(source_url),
            tags=tags or []
        )

        self._records[record.record_id] = record

        # 更新域名索引
        if record.source_domain:
            self._domains[record.source_domain].append(record.record_id)

        # 更新或创建模式
        self._update_pattern(semantic_type, field_name, field_label, record.record_id)

        self._save_records()
        return record

    def _create_pattern(self, text: str) -> str:
        """从文本创建模糊匹配模式"""
        if not text:
            return ""
        # 简化：只保留关键字符
        import re
        # 移除标点，保留中文和英文
        cleaned = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", text)
        return cleaned.lower()

    def _extract_domain(self, url: str) -> str:
        """提取域名"""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return ""

    def _update_pattern(
        self,
        semantic_type: FieldSemanticType,
        field_name: str,
        field_label: str,
        record_id: str
    ):
        """更新字段模式"""
        domain = ""  # 可以从上下文获取

        # 查找或创建模式
        pattern_key = f"{domain}:{semantic_type.value}"
        if pattern_key not in self._patterns:
            self._patterns[pattern_key] = FieldPattern(
                pattern_id=pattern_key,
                domain=domain,
                semantic_type=semantic_type.value
            )

        pattern = self._patterns[pattern_key]
        pattern.add_value_record(record_id)
        pattern.match_count += 1
        pattern.last_matched = time.time()

        self._save_patterns()

    # ========== 查询 ==========

    def get_suggestions(
        self,
        semantic_type: FieldSemanticType,
        field_name: str = "",
        field_label: str = "",
        domain: str = "",
        limit: int = 5
    ) -> List[FieldValueRecord]:
        """
        获取字段值建议

        Args:
            semantic_type: 字段语义类型
            field_name: 字段名
            field_label: 字段标签
            domain: 域名
            limit: 返回数量

        Returns:
            建议列表，按相关度和使用频率排序
        """
        candidates = []

        # 1. 同语义类型记录
        for record in self._records.values():
            if record.field_semantic_type == semantic_type.value:
                candidates.append(record)

        # 2. 同一域名记录优先
        if domain:
            domain_records = [r for r in candidates if r.source_domain == domain]
            if domain_records:
                # 合并，但提升域名匹配的排序
                for r in domain_records:
                    r._domain_match = True
            else:
                for r in candidates:
                    r._domain_match = False
        else:
            for r in candidates:
                r._domain_match = False

        # 3. 按综合评分排序
        def score(record: FieldValueRecord) -> float:
            # 时间衰减因子（越新的记录权重越高）
            days_old = (time.time() - record.last_used) / (24 * 3600)
            time_factor = max(0.5, 1 - days_old * 0.05)

            # 使用频率因子
            use_factor = min(1.0, record.use_count / 10)

            # 成功率因子
            success_factor = record.success_rate

            # 域名匹配因子
            domain_factor = 1.2 if getattr(record, '_domain_match', False) else 1.0

            return time_factor * (0.3 + use_factor * 0.3 + success_factor * 0.4) * domain_factor

        candidates.sort(key=score, reverse=True)

        return candidates[:limit]

    def record_usage(
        self,
        record_id: str,
        success: bool
    ):
        """
        记录使用结果

        Args:
            record_id: 记录 ID
            success: 是否成功采用
        """
        if record_id in self._records:
            record = self._records[record_id]
            if success:
                record.update_success()
            else:
                record.update_fail()
            self._save_records()

    # ========== 会话管理 ==========

    def create_session(
        self,
        url: str,
        form_id: str
    ) -> FormSession:
        """创建表单会话"""
        session = FormSession(
            session_id=str(uuid.uuid4())[:12],
            url=url,
            domain=self._extract_domain(url),
            form_id=form_id
        )
        self._sessions[session.session_id] = session
        self._save_sessions()
        return session

    def update_session(
        self,
        session_id: str,
        field_name: str,
        value: str
    ):
        """更新会话进度"""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.filled_fields[field_name] = value
            session.updated_at = time.time()
            self._save_sessions()

    def get_session(
        self,
        url: str,
        form_id: str = ""
    ) -> Optional[FormSession]:
        """获取未完成的会话"""
        domain = self._extract_domain(url)

        for session in self._sessions.values():
            if session.domain == domain and not session.is_completed and not session.is_abandoned:
                # 检查是否超过7天
                if time.time() - session.updated_at < 7 * 24 * 3600:
                    return session

        return None

    def complete_session(self, session_id: str):
        """标记会话完成"""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.is_completed = True
            session.completed_at = time.time()

            # 从记录的值添加到记忆
            for field_name, value in session.filled_fields.items():
                # 需要知道语义类型，这里简化处理
                pass

            self._save_sessions()

    def abandon_session(self, session_id: str):
        """放弃会话"""
        if session_id in self._sessions:
            self._sessions[session_id].is_abandoned = True
            self._save_sessions()

    # ========== 工具方法 ==========

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_records = len(self._records)
        total_sessions = len(self._sessions)
        completed_sessions = sum(1 for s in self._sessions.values() if s.is_completed)

        # 按语义类型统计
        by_type = defaultdict(int)
        for record in self._records.values():
            by_type[record.field_semantic_type] += 1

        return {
            "total_records": total_records,
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "records_by_type": dict(by_type),
            "domains_count": len(self._domains),
        }

    def clear_old_sessions(self, days: int = 30):
        """清理旧会话"""
        cutoff = time.time() - days * 24 * 3600
        to_remove = []

        for session_id, session in self._sessions.items():
            if session.updated_at < cutoff and not session.is_completed:
                to_remove.append(session_id)

        for session_id in to_remove:
            del self._sessions[session_id]

        if to_remove:
            self._save_sessions()

        return len(to_remove)

    def export_records(self, filepath: str, semantic_types: List[str] = None):
        """导出记录"""
        records = list(self._records.values())
        if semantic_types:
            records = [r for r in records if r.field_semantic_type in semantic_types]

        data = [asdict(r) for r in records]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_records(self, filepath: str, merge: bool = True):
        """导入记录"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if merge:
            for rec_data in data:
                rec = FieldValueRecord(**rec_data)
                if rec.record_id not in self._records:
                    self._records[rec.record_id] = rec
        else:
            self._records.clear()
            for rec_data in data:
                rec = FieldValueRecord(**rec_data)
                self._records[rec.record_id] = rec

        self._save_records()
