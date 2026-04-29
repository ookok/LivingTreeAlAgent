# attribution.py — 归因链接追踪系统

import uuid
import json
import hashlib
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from urllib.parse import urlencode, parse_qs, urlparse

from .models import (
    AttributionRecord, AttributionSource, ClickAttribution,
    LandingPageConfig,
)


class AttributionSystem:
    """
    归因追踪系统

    功能：
    1. 短链生成 https://dl.living-tree.ai/v1?from=weibo_bot_8848
    2. 点击归因记录
    3. 渠道效果分析
    4. 分身标识管理
    """

    def __init__(
        self,
        data_dir: Path = None,
        config: LandingPageConfig = None,
    ):
        """
        初始化归因系统

        Args:
            data_dir: 数据存储目录
            config: 落地页配置
        """
        self._data_dir = data_dir or self._default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._config = config or LandingPageConfig()

        # 存储文件
        self._records_file = self._data_dir / "attribution_records.json"
        self._clicks_file = self._data_dir / "click_logs.json"

        # 内存缓存
        self._records: Dict[str, AttributionRecord] = {}
        self._clicks: List[ClickAttribution] = []

        # 加载已有数据
        self._load_records()
        self._load_clicks()

    def _default_data_dir(self) -> Path:
        """默认数据目录"""
        return Path.home() / ".hermes-desktop" / "promotion" / "attribution"

    def _load_records(self):
        """加载归因记录"""
        if self._records_file.exists():
            try:
                with open(self._records_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        record = AttributionRecord.from_dict(item)
                        self._records[record.attribution_id] = record
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_clicks(self):
        """加载点击日志"""
        if self._clicks_file.exists():
            try:
                with open(self._clicks_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self._clicks.append(ClickAttribution(
                            attribution_id=item["attribution_id"],
                            source=AttributionSource(item["source"]),
                            source_identity=item["source_identity"],
                            clicked_at=datetime.fromisoformat(item["clicked_at"]),
                            user_agent=item.get("user_agent", ""),
                            referer=item.get("referer", ""),
                            landing_page=item.get("landing_page", ""),
                        ))
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_records(self):
        """保存归因记录"""
        data = [r.to_dict() for r in self._records.values()]
        with open(self._records_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_clicks(self):
        """保存点击日志"""
        data = [c.to_dict() for c in self._clicks]
        with open(self._clicks_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def generate_short_url(
        self,
        source: AttributionSource,
        source_identity: str,
        campaign_id: Optional[str] = None,
        content_hash: str = "",
        full_url: str = None,
    ) -> AttributionRecord:
        """
        生成归因短链

        Args:
            source: 来源渠道
            source_identity: 分身标识（如 "weibo_bot_8848"）
            campaign_id: 活动ID
            content_hash: 内容哈希（去重用）
            full_url: 完整落地页URL，None则使用默认

        Returns:
            AttributionRecord: 归因记录
        """
        attribution_id = self._generate_id()

        # 完整URL
        if full_url is None:
            full_url = self._build_full_url(attribution_id)

        # 短链格式：https://dl.living-tree.ai/v1?from=weibo_bot_8848&id=xxx
        short_url = self._build_short_url(source, source_identity, attribution_id)

        record = AttributionRecord(
            attribution_id=attribution_id,
            short_url=short_url,
            full_url=full_url,
            source=source,
            source_identity=source_identity,
            campaign_id=campaign_id,
            content_hash=content_hash,
            created_at=datetime.now(),
        )

        self._records[attribution_id] = record
        self._save_records()

        return record

    def _generate_id(self) -> str:
        """生成唯一ID"""
        raw = f"{uuid.uuid4().hex}{datetime.now().isoformat()}".encode()
        return base64.urlsafe_b64encode(
            hashlib.sha256(raw).digest()
        )[:12].decode("ascii")

    def _build_full_url(self, attribution_id: str) -> str:
        """构建完整落地页URL"""
        base = f"https://{self._config.base_domain}/index.html"
        params = urlencode({"id": attribution_id})
        return f"{base}?{params}"

    def _build_short_url(
        self,
        source: AttributionSource,
        source_identity: str,
        attribution_id: str,
    ) -> str:
        """构建短链"""
        base = f"https://{self._config.short_domain}/v1"
        params = urlencode({
            "from": source_identity,
            "id": attribution_id,
        })
        return f"{base}?{params}"

    def parse_short_url(self, short_url: str) -> Optional[Dict[str, Any]]:
        """
        解析短链，提取归因信息

        用于服务端/客户端记录点击

        Args:
            short_url: 短链URL

        Returns:
            Dict: {attribution_id, source_identity, source} 或 None
        """
        try:
            parsed = urlparse(short_url)
            qs = parse_qs(parsed.query)

            attribution_id = qs.get("id", [None])[0]
            from_param = qs.get("from", ["manual"])[0]

            if not attribution_id:
                return None

            return {
                "attribution_id": attribution_id,
                "source_identity": from_param,
                "source": self._identify_source(from_param),
            }
        except Exception:
            return None

    def _identify_source(self, identity: str) -> AttributionSource:
        """从分身标识识别来源渠道"""
        identity_lower = identity.lower()
        for source in AttributionSource:
            if identity_lower.startswith(source.value):
                return source
        return AttributionSource.MANUAL

    def record_click(
        self,
        attribution_id: str,
        user_agent: str = "",
        referer: str = "",
        ip_hash: str = "",
    ) -> bool:
        """
        记录一次点击

        Args:
            attribution_id: 归因ID
            user_agent: 用户代理
            referer: 来源页面
            ip_hash: IP哈希（隐私保护）

        Returns:
            bool: 是否成功记录
        """
        record = self._records.get(attribution_id)
        if record is None:
            return False

        # 更新记录
        record.click_count += 1

        # 记录点击详情
        click = ClickAttribution(
            attribution_id=attribution_id,
            source=record.source,
            source_identity=record.source_identity,
            clicked_at=datetime.now(),
            user_agent=user_agent,
            ip_hash=ip_hash,
            referer=referer,
            landing_page=record.full_url,
        )
        self._clicks.append(click)

        self._save_records()
        self._save_clicks()

        return True

    def get_record(self, attribution_id: str) -> Optional[AttributionRecord]:
        """获取归因记录"""
        return self._records.get(attribution_id)

    def get_records_by_source(
        self,
        source: AttributionSource
    ) -> List[AttributionRecord]:
        """获取指定来源的所有记录"""
        return [
            r for r in self._records.values()
            if r.source == source
        ]

    def get_records_by_identity(
        self,
        source_identity: str
    ) -> List[AttributionRecord]:
        """获取指定分身标识的所有记录"""
        return [
            r for r in self._records.values()
            if r.source_identity == source_identity
        ]

    def get_stats_by_source(self) -> Dict[str, Dict[str, Any]]:
        """获取各渠道统计"""
        stats = {}
        for source in AttributionSource:
            records = self.get_records_by_source(source)
            total_clicks = sum(r.click_count for r in records)
            stats[source.value] = {
                "record_count": len(records),
                "total_clicks": total_clicks,
                "avg_clicks": total_clicks / len(records) if records else 0,
            }
        return stats

    def get_all_stats(self) -> Dict[str, Any]:
        """获取全局统计"""
        total_records = len(self._records)
        total_clicks = sum(r.click_count for r in self._records.values())
        total_visitors = sum(r.unique_visitors for r in self._records.values())
        by_source = self.get_stats_by_source()

        return {
            "total_records": total_records,
            "total_clicks": total_clicks,
            "total_visitors": total_visitors,
            "avg_ctr": total_clicks / total_records if total_records > 0 else 0,
            "by_source": by_source,
        }


# 全局单例
_attribution_instance: Optional[AttributionSystem] = None


def get_attribution_system() -> AttributionSystem:
    """获取归因系统全局实例"""
    global _attribution_instance
    if _attribution_instance is None:
        _attribution_instance = AttributionSystem()
    return _attribution_instance
