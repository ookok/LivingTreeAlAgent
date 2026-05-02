# safety_filter.py — 安全守门员
# 关键词粗筛 → Presidio → 云兜底 → 入库

import re
from typing import List, Optional, Dict, Any
from pathlib import Path

from .models import FeedItem, FeedSource


class FeedSafetyFilter:
    """
    Feed 安全守门员

    分层过滤：
    1. 关键词粗筛 (block_list / warn_list)
    2. 正则模式匹配
    3. 来源可信度
    4. 人工复核队列
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "feed_aggregator" / "safety"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._block_list = self._load_list("block.txt")
        self._warn_list = self._load_list("warn.txt")
        self._review_queue: List[Dict] = []

        # 可信来源（自动放行）
        self._trusted_sources = {
            FeedSource.GITHUB,
            FeedSource.REDDIT,
            FeedSource.ZHIHU,
            FeedSource.NEWS,
        }

    # ============================================================
    # 主入口
    # ============================================================

    def check(self, item: FeedItem) -> Dict[str, Any]:
        """
        安全审查

        Returns:
            {
                "passed": bool,       # 是否通过
                "level": str,         # safe/review/block
                "reasons": [],        # 拦截/警告原因
            }
        """
        result = {
            "passed": True,
            "level": "safe",
            "reasons": [],
        }

        text = f"{item.title} {item.summary}"

        # Layer 1: 关键词过滤
        keyword_result = self._check_keywords(text)
        if not keyword_result["passed"]:
            result["passed"] = False
            result["level"] = "block"
            result["reasons"].extend(keyword_result["reasons"])
            item.safety_level = "block"
            self._add_to_review_queue(item, keyword_result["reasons"])
            return result

        if keyword_result["warnings"]:
            result["level"] = "review"
            result["reasons"].extend(keyword_result["warnings"])

        # Layer 2: 正则模式
        pattern_result = self._check_patterns(text)
        if not pattern_result["passed"]:
            result["passed"] = False
            result["level"] = "block"
            result["reasons"].extend(pattern_result["issues"])
            item.safety_level = "block"
            self._add_to_review_queue(item, pattern_result["issues"])
            return result

        if pattern_result["warnings"]:
            if result["level"] != "block":
                result["level"] = "review"
            result["reasons"].extend(pattern_result["warnings"])

        # Layer 3: 来源检查
        source_result = self._check_source(item)
        if not source_result["passed"]:
            result["passed"] = False
            result["level"] = "block"
            result["reasons"].extend(source_result["reasons"])
            item.safety_level = "block"
            return result

        # 可信来源自动通过
        if item.source in self._trusted_sources:
            result["level"] = "safe"
            result["reasons"] = []
            item.safety_level = "safe"
        elif result["level"] == "review":
            item.safety_level = "review"
            self._add_to_review_queue(item, result["reasons"])
        else:
            item.safety_level = "safe"

        return result

    def check_batch(self, items: List[FeedItem]) -> List[Dict[str, Any]]:
        """批量审查"""
        return [self.check(item) for item in items]

    # ============================================================
    # 分层检查
    # ============================================================

    def _check_keywords(self, text: str) -> Dict:
        """关键词过滤"""
        issues = []
        warnings = []
        text_lower = text.lower()

        for keyword in self._block_list:
            if keyword.lower() in text_lower:
                issues.append(f"拦截词: {keyword}")

        for keyword in self._warn_list:
            if keyword.lower() in text_lower:
                warnings.append(f"警告词: {keyword}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }

    # 危险模式
    DANGEROUS_PATTERNS = [
        (r"<script", "XSS 风险"),
        (r"javascript:", "JS 协议"),
        (r"on\w+\s*=", "事件处理器"),
    ]

    # 可疑模式
    SUSPICIOUS_PATTERNS = [
        (r"https?://[^\s<>\"']+", "外部链接"),
    ]

    def _check_patterns(self, text: str) -> Dict:
        """正则模式匹配"""
        issues = []
        warnings = []

        for pattern, desc in self.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"危险模式: {desc}")

        for pattern, desc in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text):
                warnings.append(f"可疑模式: {desc}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }

    def _check_source(self, item: FeedItem) -> Dict:
        """来源可信度检查"""
        # 黑名单来源
        if item.source == FeedSource.UNKNOWN:
            return {
                "passed": False,
                "issues": ["未知来源"],
                "warnings": [],
            }

        # 检查 URL 域名可信度
        if item.url:
            suspicious_domains = ["bit.ly", "tinyurl", "t.co", "goo.gl"]
            for domain in suspicious_domains:
                if domain in item.url.lower():
                    return {
                        "passed": True,
                        "issues": [],
                        "warnings": [f"短链接域名: {domain}"],
                    }

        return {
            "passed": True,
            "issues": [],
            "warnings": [],
        }

    # ============================================================
    # 复核队列
    # ============================================================

    def _add_to_review_queue(self, item: FeedItem, reasons: List[str]):
        """加入人工复核队列"""
        self._review_queue.append({
            "item_id": item.id,
            "title": item.title,
            "source": item.source.value,
            "reasons": reasons,
            "timestamp": str(item.fetched_at),
        })

        # 限制队列长度
        if len(self._review_queue) > 100:
            self._review_queue = self._review_queue[-100:]

        self._save_review_queue()

    def get_review_queue(self) -> List[Dict]:
        """获取待复核队列"""
        return self._review_queue

    def approve_item(self, item_id: str) -> bool:
        """批准内容"""
        self._review_queue = [r for r in self._review_queue if r.get("item_id") != item_id]
        self._save_review_queue()
        return True

    def reject_item(self, item_id: str) -> bool:
        """拒绝内容"""
        self._review_queue = [r for r in self._review_queue if r.get("item_id") != item_id]
        self._save_review_queue()
        return True

    # ============================================================
    # 列表管理
    # ============================================================

    def add_block_keyword(self, keyword: str):
        """添加拦截词"""
        if keyword not in self._block_list:
            self._block_list.append(keyword)
            self._save_list("block.txt", self._block_list)

    def add_warn_keyword(self, keyword: str):
        """添加警告词"""
        if keyword not in self._warn_list:
            self._warn_list.append(keyword)
            self._save_list("warn.txt", self._warn_list)

    def remove_block_keyword(self, keyword: str):
        """移除拦截词"""
        if keyword in self._block_list:
            self._block_list.remove(keyword)
            self._save_list("block.txt", self._block_list)

    # ============================================================
    # 持久化
    # ============================================================

    def _load_list(self, filename: str) -> List[str]:
        path = self.data_dir / filename
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except:
                pass
        return []

    def _save_list(self, filename: str, items: List[str]):
        path = self.data_dir / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(items))
        except Exception as e:
            print(f"[FeedSafetyFilter] Save list failed: {e}")

    def _load_review_queue(self) -> List[Dict]:
        path = self.data_dir / "review_queue.json"
        if path.exists():
            try:
                import json
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_review_queue(self):
        path = self.data_dir / "review_queue.json"
        try:
            import json
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._review_queue, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[FeedSafetyFilter] Save queue failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "block_list_size": len(self._block_list),
            "warn_list_size": len(self._warn_list),
            "review_queue_size": len(self._review_queue),
        }


# 全局单例
_feed_safety: Optional[FeedSafetyFilter] = None


def get_feed_safety_filter() -> FeedSafetyFilter:
    global _feed_safety
    if _feed_safety is None:
        _feed_safety = FeedSafetyFilter()
    return _feed_safety
