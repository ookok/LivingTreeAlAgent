# data_collector.py — 脱敏数据收集与周聚合上传

import json
import re
import time
import hashlib
import gzip
import base64
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import asdict

from .models import (
    WeeklyReport, PatchDoc, UIPainPoint,
    ClientConfig, ReportStatus,
    get_week_id, generate_client_id, hash_for_dedup,
)


class Desensitizer:
    """
    脱敏工具

    过滤敏感信息：
    - 密码/Token/密钥
    - 文件路径
    - 邮箱/手机号
    - IP地址
    """

    # 脱敏模式
    PATTERNS = [
        (r'password["\']?\s*[:=]\s*["\'][^"\']+["\']', 'password":"***"'),
        (r'token["\']?\s*[:=]\s*["\'][^"\']+["\']', 'token":"***"'),
        (r'secret["\']?\s*[:=]\s*["\'][^"\']+["\']', 'secret":"***"'),
        (r'api_key["\']?\s*[:=]\s*["\'][^"\']+["\']', 'api_key":"***"'),
        (r'auth["\']?\s*[:=]\s*["\'][^"\']+["\']', 'auth":"***"'),
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '***@***.com'),
        (r'\d{11}', '***'),
        (r'\d{3,4}[-\s]?\d{3,4}[-\s]?\d{3,4}', '***-***-***'),
        (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '***.***.***.***'),
        (r'[C-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*', '***'),
        (r'/home/[^/\s]+', '/home/***'),
        (r'/Users/[^/\s]+', '/Users/***'),
    ]

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """
        对字符串进行脱敏

        Args:
            text: 原始字符串

        Returns:
            str: 脱敏后字符串
        """
        if not text:
            return text

        result = text
        for pattern, replacement in cls.PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        对字典进行脱敏（递归）

        Args:
            data: 原始字典

        Returns:
            Dict: 脱敏后字典
        """
        if not isinstance(data, dict):
            if isinstance(data, str):
                return cls.sanitize_string(data)
            return data

        result = {}
        for key, value in data.items():
            # 跳过敏感键
            key_lower = key.lower()
            if any(s in key_lower for s in ["password", "token", "secret", "auth", "key"]):
                result[key] = "***"
                continue

            # 递归处理
            if isinstance(value, dict):
                result[key] = cls.sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = [cls.sanitize_dict(v) if isinstance(v, dict) else
                              cls.sanitize_string(v) if isinstance(v, str) else v
                              for v in value]
            elif isinstance(value, str):
                result[key] = cls.sanitize_string(value)
            else:
                result[key] = value

        return result

    @classmethod
    def sanitize_patch(cls, patch: PatchDoc) -> PatchDoc:
        """
        对补丁进行脱敏

        Args:
            patch: 原始补丁

        Returns:
            PatchDoc: 脱敏后补丁
        """
        # 脱敏reason
        patch.reason = cls.sanitize_string(patch.reason)

        # 脱敏old_value/new_value（如果是字符串）
        if isinstance(patch.old_value, str):
            patch.old_value = cls.sanitize_string(patch.old_value)
        if isinstance(patch.new_value, str):
            patch.new_value = cls.sanitize_string(patch.new_value)

        return patch


class DataCollector:
    """
    数据收集器

    功能：
    1. 收集补丁和痛点数据
    2. 脱敏处理
    3. 周聚合生成
    4. 上传管理
    """

    def __init__(
        self,
        data_dir: Path = None,
        config: ClientConfig = None,
    ):
        """
        初始化数据收集器

        Args:
            data_dir: 数据存储目录
            config: 客户端配置
        """
        self._data_dir = data_dir or self._default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._config = config or ClientConfig()
        if not self._config.client_id:
            self._config.client_id = generate_client_id()

        # 存储文件
        self._reports_file = self._data_dir / "reports.json"
        self._pending_file = self._data_dir / "pending_reports.json"
        self._config_file = self._data_dir / "config.json"

        # 内存缓存
        self._reports: Dict[str, WeeklyReport] = {}
        self._pending_reports: List[str] = []  # 待上传报告ID列表

        # 加载数据
        self._load_reports()
        self._load_pending()
        self._load_config()

    def _default_data_dir(self) -> Path:
        """默认数据目录"""
        return Path.home() / ".hermes-desktop" / "evolution" / "collector"

    def _load_reports(self):
        """加载报告"""
        if self._reports_file.exists():
            try:
                with open(self._reports_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for week_id, report_data in data.items():
                        self._reports[week_id] = WeeklyReport.from_dict(report_data)
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_pending(self):
        """加载待上传报告"""
        if self._pending_file.exists():
            try:
                with open(self._pending_file, "r", encoding="utf-8") as f:
                    self._pending_reports = json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_config(self):
        """加载配置"""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._config = ClientConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_reports(self):
        """保存报告"""
        data = {k: v.to_dict() for k, v in self._reports.items()}
        with open(self._reports_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_pending(self):
        """保存待上传列表"""
        with open(self._pending_file, "w", encoding="utf-8") as f:
            json.dump(self._pending_reports, f, ensure_ascii=False, indent=2)

    def _save_config(self):
        """保存配置"""
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(self._config.to_dict(), f, ensure_ascii=False, indent=2)

    def collect_patches(self, patches: List[PatchDoc]) -> List[PatchDoc]:
        """
        收集补丁（脱敏）

        Args:
            patches: 补丁列表

        Returns:
            List[PatchDoc]: 脱敏后补丁
        """
        collected = []
        for patch in patches:
            if patch.status.value == "applied":
                sanitized = Desensitizer.sanitize_patch(patch)
                collected.append(sanitized)
        return collected

    def collect_pain_points(self, pain_points: List[UIPainPoint]) -> List[UIPainPoint]:
        """
        收集痛点（仅未解决）

        Args:
            pain_points: 痛点列表

        Returns:
            List[UIPainPoint]: 未解决痛点
        """
        return [p for p in pain_points if not p.resolved]

    def generate_weekly_report(
        self,
        patches: List[PatchDoc],
        pain_points: List[UIPainPoint],
    ) -> WeeklyReport:
        """
        生成周报

        Args:
            patches: 补丁列表
            pain_points: 痛点列表

        Returns:
            WeeklyReport: 周报
        """
        week_id = get_week_id()

        # 脱敏收集
        collected_patches = self.collect_patches(patches)
        collected_pain_points = self.collect_pain_points(pain_points)

        report = WeeklyReport(
            week_id=week_id,
            client_id=self._config.client_id,
            patches=collected_patches,
            pain_points=collected_pain_points,
            generated_at=int(time.time()),
            status=ReportStatus.PENDING,
            client_version="2.0.0",  # TODO: 从配置读取
            platform="windows",
        )

        # 存储
        self._reports[week_id] = report
        if week_id not in self._pending_reports:
            self._pending_reports.append(week_id)

        self._save_reports()
        self._save_pending()

        return report

    def get_pending_reports(self) -> List[WeeklyReport]:
        """获取待上传报告"""
        return [
            self._reports[wid]
            for wid in self._pending_reports
            if wid in self._reports
        ]

    def mark_report_uploaded(self, week_id: str) -> bool:
        """标记报告为已上传"""
        report = self._reports.get(week_id)
        if report is None:
            return False

        report.mark_uploaded()
        self._save_reports()

        # 从待上传列表移除
        if week_id in self._pending_reports:
            self._pending_reports.remove(week_id)
            self._save_pending()

        return True

    def mark_report_failed(self, week_id: str) -> bool:
        """标记报告上传失败"""
        report = self._reports.get(week_id)
        if report is None:
            return False

        report.status = ReportStatus.FAILED
        self._save_reports()

        return True

    def should_upload(self) -> bool:
        """检查是否应该上传"""
        if not self._config.enabled or not self._config.auto_upload:
            return False

        if self._config.last_upload is None:
            return True

        elapsed = time.time() - self._config.last_upload
        return elapsed >= self._config.min_upload_interval

    def update_upload_time(self):
        """更新上传时间"""
        self._config.last_upload = int(time.time())
        self._save_config()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_reports": len(self._reports),
            "pending_reports": len(self._pending_reports),
            "uploaded_reports": sum(
                1 for r in self._reports.values()
                if r.status == ReportStatus.UPLOADED
            ),
            "last_upload": self._config.last_upload,
            "client_id": self._config.client_id,
        }

    def export_report_json(self, week_id: str) -> Optional[str]:
        """
        导出报告JSON

        Args:
            week_id: 周标识

        Returns:
            str: JSON字符串
        """
        report = self._reports.get(week_id)
        if report is None:
            return None

        return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)

    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        self._save_config()

    def get_config(self) -> ClientConfig:
        """获取配置"""
        return self._config


# 全局单例
_collector_instance: Optional[DataCollector] = None


def get_data_collector() -> DataCollector:
    """获取数据收集器全局实例"""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = DataCollector()
    return _collector_instance


# ============ 终极版新增：内容回流解析 ============

from .models import (
    Reply回流, ExternalPlatform, ExternalPost,
)


class Content回流Handler:
    """
    外部平台回复回流处理器

    功能：
    1. 收集外部平台回复
    2. 解析并内化为知识
    3. 更新 AI 知识库
    """

    def __init__(self, data_dir: Path = None):
        """
        初始化回流处理器

        Args:
            data_dir: 数据存储目录
        """
        self._data_dir = data_dir or self._default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # 存储文件
        self._replies_file = self._data_dir / "回流_replies.json"
        self._absorbed_file = self._data_dir / "absorbed_knowledge.json"

        # 内存缓存
        self._replies: Dict[str, Reply回流] = {}
        self._absorbed_knowledge: List[Dict[str, Any]] = []

        # 加载数据
        self._load_replies()
        self._load_absorbed()

    def _default_data_dir(self) -> Path:
        """默认数据目录"""
        return Path.home() / ".hermes-desktop" / "evolution" / "回流"

    def _load_replies(self):
        """加载回复"""
        if self._replies_file.exists():
            try:
                with open(self._replies_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        reply = Reply回流.from_dict(item)
                        self._replies[reply.id] = reply
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_absorbed(self):
        """加载已内化知识"""
        if self._absorbed_file.exists():
            try:
                with open(self._absorbed_file, "r", encoding="utf-8") as f:
                    self._absorbed_knowledge = json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_replies(self):
        """保存回复"""
        data = [r.to_dict() for r in self._replies.values()]
        with open(self._replies_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_absorbed(self):
        """保存已内化知识"""
        with open(self._absorbed_file, "w", encoding="utf-8") as f:
            json.dump(self._absorbed_knowledge, f, ensure_ascii=False, indent=2)

    def ingest_reply(
        self,
        external_post_id: str,
        platform: ExternalPlatform,
        author: str,
        content: str,
        timestamp: int = None,
    ) -> Reply回流:
        """
        摄入外部回复

        Args:
            external_post_id: 对应的外部帖子ID
            platform: 来源平台
            author: 作者
            content: 回复内容
            timestamp: 发布时间

        Returns:
            Reply回流: 回流记录
        """
        reply_id = hash_for_dedup(external_post_id, author, content, str(timestamp or int(time.time())))

        # 检查是否已存在
        for existing in self._replies.values():
            if (existing.external_post_id == external_post_id and
                    existing.author == author and
                    existing.content == content):
                return existing

        reply = Reply回流(
            id=reply_id,
            external_post_id=external_post_id,
            platform=platform,
            author=author,
            content=content,
            timestamp=timestamp or int(time.time()),
        )

        self._replies[reply_id] = reply
        self._save_replies()

        return reply

    def parse_and_absorb(self, reply_id: str) -> bool:
        """
        解析并内化回复

        Args:
            reply_id: 回复ID

        Returns:
            bool: 是否成功
        """
        reply = self._replies.get(reply_id)
        if reply is None or reply.absorbed:
            return False

        # 简单解析：提取关键词
        keywords = self._extract_keywords(reply.content)

        # 判断是否有帮助
        helpful_keywords = ["有用", "谢谢", "解决了", "helpful", "thanks", "solved", "great"]
        is_helpful = any(kw in reply.content.lower() for kw in helpful_keywords)

        # 更新回复状态
        reply.is_helpful = is_helpful
        reply.absorbed = True
        reply.absorbed_at = int(time.time())
        reply.knowledge_tags = keywords

        # 添加到已内化知识
        knowledge_entry = {
            "source_reply_id": reply_id,
            "source_post_id": reply.external_post_id,
            "platform": reply.platform.value,
            "keywords": keywords,
            "excerpt": reply.content[:200],  # 保留前200字符
            "is_helpful": is_helpful,
            "absorbed_at": reply.absorbed_at,
        }
        self._absorbed_knowledge.append(knowledge_entry)

        self._save_replies()
        self._save_absorbed()

        return True

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词（简单实现）"""
        # 移除标点，分词
        words = re.findall(r'[\w]+', content)
        # 过滤停用词
        stopwords = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must"}
        keywords = [w for w in words if len(w) >= 2 and w not in stopwords]
        # 返回出现最多的前5个
        from collections import Counter
        counter = Counter(keywords)
        return [w for w, _ in counter.most_common(5)]

    def auto_absorb_all(self) -> int:
        """
        自动内化所有未内化回复

        Returns:
            int: 内化数量
        """
        count = 0
        for reply_id in list(self._replies.keys()):
            if self.parse_and_absorb(reply_id):
                count += 1
        return count

    def generate_knowledge_base(self) -> str:
        """
        生成知识库文本（用于注入到 AI）

        Returns:
            str: 知识库文本
        """
        if not self._absorbed_knowledge:
            return ""

        lines = ["[外部知识库 - 回流自用户社区]", ""]

        for entry in self._absorbed_knowledge[-20:]:  # 只保留最近20条
            tags = ", ".join(entry.get("keywords", [])[:3])
            excerpt = entry.get("excerpt", "")[:100]
            helpful = "[有用]" if entry.get("is_helpful") else ""
            lines.append(f"- {tags} {helpful}")
            lines.append(f"  {excerpt}...")

        return "\n".join(lines)

    def get_pending_replies(self) -> List[Reply回流]:
        """获取待内化回复"""
        return [r for r in self._replies.values() if not r.absorbed]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_replies": len(self._replies),
            "absorbed": sum(1 for r in self._replies.values() if r.absorbed),
            "pending": sum(1 for r in self._replies.values() if not r.absorbed),
            "helpful": sum(1 for r in self._replies.values() if r.is_helpful),
            "knowledge_entries": len(self._absorbed_knowledge),
        }


# 全局单例
_回流_handler_instance: Optional[Content回流Handler] = None


def get_回流_handler() -> Content回流Handler:
    """获取回流处理器全局实例"""
    global _回流_handler_instance
    if _回流_handler_instance is None:
        _回流_handler_instance = Content回流Handler()
    return _回流_handler_instance
