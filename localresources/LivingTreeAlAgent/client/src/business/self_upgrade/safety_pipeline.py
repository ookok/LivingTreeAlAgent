# safety_pipeline.py — 安全审查管道

import re
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime

from .models import SafetyCheckResult, SafetyLevel


class SafetyPipeline:
    """
    安全审查管道（分层设计）

    Layer 1: KeywordFilter — 关键词本地过滤
    Layer 2: PatternMatch — 正则模式匹配
    Layer 3: ContentClassifier — 内容分类（待扩展 Presidio）
    Layer 4: HumanReview — 人类终审
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "safety"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._block_list = self._load_block_list()
        self._warn_list = self._load_warn_list()
        self._strict_mode = True

    # ============================================================
    # 公开 API
    # ============================================================

    def check(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> SafetyCheckResult:
        """
        主审查入口

        Args:
            content: 待审查内容
            metadata: 额外元数据（来源/类型/作者等）

        Returns:
            SafetyCheckResult
        """
        result = SafetyCheckResult(
            passed=True,
            level=SafetyLevel.SAFE,
            issues=[],
            warnings=[],
            details=metadata or {}
        )

        # Layer 1: 关键词过滤
        keyword_result = self._check_keywords(content)
        if not keyword_result["passed"]:
            result.passed = False
            result.level = SafetyLevel.BLOCK
            result.issues.extend(keyword_result["issues"])
            return result

        if keyword_result["warnings"]:
            result.warnings.extend(keyword_result["warnings"])
            if self._strict_mode:
                result.level = SafetyLevel.REVIEW

        # Layer 2: 模式匹配
        pattern_result = self._check_patterns(content)
        if not pattern_result["passed"]:
            result.passed = False
            result.level = SafetyLevel.BLOCK
            result.issues.extend(pattern_result["issues"])
            return result

        if pattern_result["warnings"]:
            result.warnings.extend(pattern_result["warnings"])
            if self._strict_mode and result.level != SafetyLevel.REVIEW:
                result.level = SafetyLevel.REVIEW

        # Layer 3: 外部链接安全检查
        link_result = self._check_external_links(content)
        if link_result["warnings"]:
            result.warnings.extend(link_result["warnings"])

        # Layer 4: 来源检查
        if metadata:
            source_check = self._check_source(metadata)
            if source_check["issues"]:
                result.issues.extend(source_check["issues"])
                result.passed = False
                result.level = SafetyLevel.BLOCK

        return result

    def check_batch(self, contents: List[str]) -> List[SafetyCheckResult]:
        """批量审查"""
        return [self.check(c) for c in contents]

    def add_to_block_list(self, keyword: str, reason: str = ""):
        """添加到拦截列表"""
        entry = {"keyword": keyword, "reason": reason, "added_at": datetime.now().isoformat()}
        if keyword not in [e["keyword"] for e in self._block_list]:
            self._block_list.append(entry)
            self._save_block_list()

    def add_to_warn_list(self, keyword: str, reason: str = ""):
        """添加到警告列表"""
        entry = {"keyword": keyword, "reason": reason, "added_at": datetime.now().isoformat()}
        if keyword not in [e["keyword"] for e in self._warn_list]:
            self._warn_list.append(entry)
            self._save_warn_list()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "block_list_size": len(self._block_list),
            "warn_list_size": len(self._warn_list),
            "strict_mode": self._strict_mode,
        }

    # ============================================================
    # Layer 1: 关键词过滤
    # ============================================================

    def _check_keywords(self, content: str) -> Dict:
        """
        关键词过滤

        Returns:
            {"passed": bool, "issues": [], "warnings": []}
        """
        issues = []
        warnings = []

        # 检查拦截列表
        for entry in self._block_list:
            if entry["keyword"].lower() in content.lower():
                issues.append(f"拦截词命中: {entry['keyword']}")

        # 检查警告列表
        for entry in self._warn_list:
            if entry["keyword"].lower() in content.lower():
                warnings.append(f"警告词命中: {entry['keyword']}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }

    # ============================================================
    # Layer 2: 正则模式匹配
    # ============================================================

    # 高风险模式
    DANGEROUS_PATTERNS = [
        # 恶意代码模式
        (r"<script[^>]*>.*?</script>", "XSS注入风险"),
        (r"javascript:", "JavaScript协议"),
        (r"on\w+\s*=", "事件处理器注入"),
        # 隐私泄露模式
        (r"\b\d{15,18}\b", "疑似身份证号"),
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "疑似银行卡号"),
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "邮箱地址"),
    ]

    # 中风险模式
    SUSPICIOUS_PATTERNS = [
        (r"https?://[^\s<>\"']+", "外部链接"),
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP地址"),
    ]

    def _check_patterns(self, content: str) -> Dict:
        issues = []
        warnings = []

        # 高风险检查
        for pattern, desc in self.DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                issues.append(f"危险模式: {desc}")

        # 中风险检查
        for pattern, desc in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append(f"可疑模式: {desc}")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }

    # ============================================================
    # Layer 3: 外部链接安全
    # ============================================================

    UNSAFE_DOMAINS = [
        "phishing", "malware", "spam", "scam",
        "888", "bet", "casino", "gambling",
    ]

    def _check_external_links(self, content: str) -> Dict:
        warnings = []
        urls = re.findall(r'https?://[^\s<>"\']+', content)

        for url in urls:
            try:
                domain = url.split('/')[2].lower()
                for unsafe in self.UNSAFE_DOMAINS:
                    if unsafe in domain:
                        warnings.append(f"可疑域名: {domain}")
                        break
            except:
                pass

        return {"warnings": warnings}

    # ============================================================
    # Layer 4: 来源检查
    # ============================================================

    def _check_source(self, metadata: Dict[str, Any]) -> Dict:
        issues = []
        source = metadata.get("source", "").lower()

        # 检查黑名单来源
        blacklisted = ["unknown", "anonymous", "untrusted"]
        if source in blacklisted:
            issues.append(f"不可信来源: {source}")

        return {"issues": issues}

    # ============================================================
    # 持久化
    # ============================================================

    def _load_block_list(self) -> List[Dict]:
        path = self.data_dir / "block_list.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_block_list(self):
        path = self.data_dir / "block_list.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._block_list, f, ensure_ascii=False, indent=2)

    def _load_warn_list(self) -> List[Dict]:
        path = self.data_dir / "warn_list.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_warn_list(self):
        path = self.data_dir / "warn_list.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._warn_list, f, ensure_ascii=False, indent=2)


# 全局单例
_safety_pipeline: Optional[SafetyPipeline] = None


def get_safety_pipeline() -> SafetyPipeline:
    global _safety_pipeline
    if _safety_pipeline is None:
        _safety_pipeline = SafetyPipeline()
    return _safety_pipeline


# 便捷函数
def check_safety(content: str, metadata: Optional[Dict[str, Any]] = None) -> SafetyCheckResult:
    """快捷安全审查"""
    return get_safety_pipeline().check(content, metadata)
