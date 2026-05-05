"""KnowledgeQuality — noise filter + industry governance + terminology dictionary.

    Three pillars of professional-grade knowledge management:

    1. MessageNoiseFilter — suppress noise in P2P/conversation message streams
    2. IndustryGovernance — regulatory monitoring + audit trail + rule engine
    3. IndustryDictionary — auto-extract terms, synonyms, bilingual mapping

    Architecture:
      Incoming messages → NoiseFilter → Signal scoring
      Document generation → Governance rules → Audit trail
      Ingested documents → Dictionary extract → Term normalization

    Usage:
        nf = get_noise_filter()
        sig = nf.score("repeated heartbeat message")
        # → 0.1 (low signal — heartbeat noise)

        ig = get_governance()
        ig.audit("环评报告", "sec4.2.1", "generated", user="zhangsan")
        violations = ig.check_rules("sec4.2.1", content)

        td = get_term_dictionary()
        td.extract_from_document("监测点SO2浓度为0.023mg/m³...")
        # → {so2: "二氧化硫", mg_m3: "毫克每立方米"}
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

QUALITY_DIR = Path(".livingtree/quality")
NOISE_DB = QUALITY_DIR / "noise_filter.json"
AUDIT_LOG = QUALITY_DIR / "audit_trail.jsonl"
DICT_DB = QUALITY_DIR / "dictionary.json"
RULES_DB = QUALITY_DIR / "governance_rules.json"


# ═══ 1. Message Noise Filter ═══

@dataclass
class SignalScore:
    message_hash: str
    score: float = 0.0          # 0.0 (pure noise) to 1.0 (high signal)
    is_duplicate: bool = False
    is_heartbeat: bool = False
    is_spam: bool = False
    reason: str = ""


class MessageNoiseFilter:
    """Deduplicate and score incoming messages by signal value."""

    HEARTBEAT_PATTERNS = [
        r"heartbeat", r"ping", r"alive", r"在线", r"心跳",
        r"^\d+$",  # numeric-only messages
        r"^ok$", r"^ack$",
    ]
    HEARTBEAT_WINDOW = 30  # seconds — suppress repeated heartbeats within this window
    DUPLICATE_THRESHOLD = 0.85  # content similarity threshold

    def __init__(self):
        QUALITY_DIR.mkdir(parents=True, exist_ok=True)
        self._seen: dict[str, float] = {}          # content_hash → last_seen
        self._heartbeat_times: dict[str, float] = {}  # sender → last_heartbeat
        self._message_window: deque[tuple[str, float]] = deque(maxlen=200)
        self._signal_scores: deque[float] = deque(maxlen=100)
        self._load()

    def score(self, content: str, sender: str = "") -> SignalScore:
        """Score a message by signal-to-noise ratio.

        Returns SignalScore with score 0.0 (noise) to 1.0 (signal).
        """
        content_hash = hashlib.sha256(
            (sender + content[:200]).encode()
        ).hexdigest()[:16]

        score = SignalScore(message_hash=content_hash)

        # 1. Exact duplicate check
        if content_hash in self._seen:
            last = self._seen[content_hash]
            if time.time() - last < 60:
                score.is_duplicate = True
                score.score = 0.0
                score.reason = "duplicate within 60s"
                return score

        # 2. Heartbeat detection
        for pattern in self.HEARTBEAT_PATTERNS:
            if re.search(pattern, content.lower()):
                if sender:
                    last_hb = self._heartbeat_times.get(sender, 0)
                    if time.time() - last_hb < self.HEARTBEAT_WINDOW:
                        score.is_heartbeat = True
                        score.score = 0.1
                        score.reason = f"heartbeat suppressed ({self.HEARTBEAT_WINDOW}s window)"
                        return score
                    self._heartbeat_times[sender] = time.time()
                score.score = 0.3
                score.reason = "heartbeat"
                return score

        # 3. Content quality scoring
        content_score = self._content_score(content)
        score.score = max(0.1, content_score)
        self._signal_scores.append(content_score)

        # Track
        self._seen[content_hash] = time.time()
        self._message_window.append((content_hash, time.time()))

        # Clean old entries
        if len(self._seen) > 5000:
            cutoff = time.time() - 3600
            self._seen = {k: v for k, v in self._seen.items() if v > cutoff}

        return score

    def _content_score(self, content: str) -> float:
        """Heuristic content quality scoring."""
        if len(content) < 5:
            return 0.2
        if len(content) > 500:
            return 0.8
        # Penalty for pure punctuation/emoji
        alpha_ratio = sum(1 for c in content if c.isalnum() or c.isspace()) / max(len(content), 1)
        return min(1.0, 0.3 + alpha_ratio * 0.5 + min(len(content) / 100, 0.2))

    def average_signal(self) -> float:
        if not self._signal_scores:
            return 0.5
        return sum(self._signal_scores) / len(self._signal_scores)

    def stats(self) -> dict:
        return {
            "seen_messages": len(self._seen),
            "window_size": len(self._message_window),
            "avg_signal": round(self.average_signal(), 2),
            "heartbeat_senders": len(self._heartbeat_times),
        }

    def _load(self):
        if not NOISE_DB.exists():
            return
        try:
            d = json.loads(NOISE_DB.read_text())
            self._seen = d.get("seen", {})
        except Exception:
            pass

    def _save(self):
        NOISE_DB.write_text(json.dumps({"seen": self._seen}), encoding="utf-8")


# ═══ 2. Industry Governance ═══

@dataclass
class AuditEntry:
    timestamp: float
    domain: str                   # 环评报告 / 安全评价 / 可行性研究
    section: str                  # 4.2.1 / 8.1
    action: str                   # generated / modified / approved / rejected
    user: str = ""
    content_hash: str = ""
    rule_violations: list[str] = field(default_factory=list)
    auto_approved: bool = False


@dataclass
class GovernanceRule:
    id: str
    domain: str
    section: str = ""
    rule: str = ""                # human-readable
    check_fn: str = ""            # auto-check function name
    severity: str = "warning"     # warning / error / block
    standard_ref: str = ""        # GB3095-2012, HJ 2.2-2018


class IndustryGovernance:
    """Regulatory monitoring, audit trail, rule-based approval."""

    BUILTIN_RULES: list[dict] = [
        {"id": "r1", "domain": "环评报告", "rule": "每节数据必须引用标准限值", "severity": "block",
         "standard_ref": "HJ 2.2-2018"},
        {"id": "r2", "domain": "环评报告", "rule": "预测结果必须包含不确定性说明", "severity": "warning",
         "standard_ref": "HJ 2.2-2018"},
        {"id": "r3", "domain": "环评报告", "rule": "监测数据需标注监测时间和方法", "severity": "error",
         "standard_ref": "HJ/T 166-2004"},
        {"id": "r4", "domain": "安全评价", "rule": "危险源辨识需引用设备清单", "severity": "block"},
        {"id": "r5", "domain": "可行性研究", "rule": "财务数据需注明基准年", "severity": "warning"},
        {"id": "r6", "domain": "通用", "rule": "引用外部数据必须标注来源URL或文献", "severity": "error"},
        {"id": "r7", "domain": "通用", "rule": "涉及地理信息需检查坐标系一致性", "severity": "error"},
    ]

    def __init__(self):
        QUALITY_DIR.mkdir(parents=True, exist_ok=True)
        self._rules: dict[str, GovernanceRule] = {}
        self._load_rules()

    def audit(self, domain: str, section: str, action: str, user: str = "", content: str = "") -> AuditEntry:
        """Record an audit trail entry for document operations."""
        entry = AuditEntry(
            timestamp=time.time(),
            domain=domain,
            section=section,
            action=action,
            user=user,
            content_hash=hashlib.sha256(content.encode()).hexdigest()[:16] if content else "",
            rule_violations=[],
        )

        # Check rules
        violations = self.check_rules(domain, section, content)
        entry.rule_violations = [v["rule"] for v in violations]
        entry.auto_approved = len(violations) == 0

        # Log to audit trail
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": entry.timestamp,
                "domain": entry.domain,
                "section": entry.section,
                "action": entry.action,
                "user": entry.user,
                "content_hash": entry.content_hash,
                "violations": entry.rule_violations,
                "auto_approved": entry.auto_approved,
            }, ensure_ascii=False) + "\n")

        if violations:
            logger.warning(f"Governance: {len(violations)} violations in {domain}/{section}")

        return entry

    def check_rules(self, domain: str, section: str = "", content: str = "") -> list[dict]:
        """Check content against governance rules. Returns list of violations."""
        violations = []
        content_lower = content.lower()

        for rule_id, rule in self._rules.items():
            if rule.domain not in (domain, "通用"):
                continue
            if rule.section and section and rule.section not in section:
                continue

            # Heuristic checks
            if "标准限值" in rule.rule or "标准" in rule.rule:
                if content and not any(kw in content_lower for kw in ["gb", "hj", "标准", "限值", "mg/m³"]):
                    violations.append({"rule_id": rule_id, "rule": rule.rule, "severity": rule.severity})
            if "不确定性" in rule.rule:
                if content and not any(kw in content_lower for kw in ["不确定", "误差", "精度", "置信"]):
                    violations.append({"rule_id": rule_id, "rule": rule.rule, "severity": rule.severity})
            if "来源" in rule.rule or "引用" in rule.rule:
                if content and not any(kw in content_lower for kw in ["http", "来源", "引自", "参考文献", "GB", "HJ"]):
                    violations.append({"rule_id": rule_id, "rule": rule.rule, "severity": rule.severity})

        return violations

    def add_rule(self, domain: str, rule: str, severity: str = "warning", standard_ref: str = "") -> str:
        """Add a custom governance rule."""
        rid = f"r{len(self._rules) + 1}"
        self._rules[rid] = GovernanceRule(id=rid, domain=domain, rule=rule, severity=severity, standard_ref=standard_ref)
        self._save_rules()
        return rid

    def get_rules(self, domain: str = "") -> list[GovernanceRule]:
        if domain:
            return [r for r in self._rules.values() if r.domain in (domain, "通用")]
        return list(self._rules.values())

    def recent_audits(self, n: int = 20) -> list[AuditEntry]:
        if not AUDIT_LOG.exists():
            return []
        entries = []
        with open(AUDIT_LOG, encoding="utf-8") as f:
            for line in f.readlines()[-n:]:
                try:
                    d = json.loads(line)
                    entries.append(AuditEntry(**{
                        k: d.get(k, "") if k != "rule_violations" else d.get(k, [])
                        for k in AuditEntry.__dataclass_fields__
                    }))
                except Exception:
                    pass
        return entries

    def _load_rules(self):
        for r in self.BUILTIN_RULES:
            self._rules[r["id"]] = GovernanceRule(**r)
        if RULES_DB.exists():
            try:
                custom = json.loads(RULES_DB.read_text())
                for rid, r in custom.items():
                    self._rules[rid] = GovernanceRule(**r)
            except Exception:
                pass

    def _save_rules(self):
        data = {}
        for rid, r in self._rules.items():
            data[rid] = {"id": r.id, "domain": r.domain, "section": r.section,
                         "rule": r.rule, "severity": r.severity, "standard_ref": r.standard_ref}
        RULES_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══ 3. Industry Dictionary ═══

@dataclass
class Term:
    term: str
    abbreviation: str = ""
    english: str = ""
    category: str = ""
    definition: str = ""
    synonyms: list[str] = field(default_factory=list)
    frequency: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0


class IndustryDictionary:
    """Auto-extract and normalize domain-specific terminology.

    Learns from ingested documents (100 EIA reports → terminology DB).
    Supports synonym mapping, abbreviation expansion, bilingual lookup.
    """

    BUILTIN_EIA_TERMS: list[dict] = [
        {"term": "二氧化硫", "abbr": "SO2", "english": "sulfur dioxide", "category": "污染物"},
        {"term": "氮氧化物", "abbr": "NOx", "english": "nitrogen oxides", "category": "污染物"},
        {"term": "可吸入颗粒物", "abbr": "PM10", "english": "particulate matter 10", "category": "污染物"},
        {"term": "化学需氧量", "abbr": "COD", "english": "chemical oxygen demand", "category": "水质"},
        {"term": "生化需氧量", "abbr": "BOD5", "english": "biochemical oxygen demand", "category": "水质"},
        {"term": "环境空气质量标准", "abbr": "GB3095", "english": "Ambient Air Quality Standard", "category": "标准"},
        {"term": "声环境质量标准", "abbr": "GB3096", "english": "Environmental Noise Standard", "category": "标准"},
        {"term": "环境影响评价", "abbr": "环评", "english": "Environmental Impact Assessment", "category": "通用"},
        {"term": "大气环境防护距离", "abbr": "", "english": "atmospheric environmental protection distance", "category": "通用"},
        {"term": "高斯烟羽模型", "abbr": "", "english": "Gaussian plume model", "category": "模型"},
        {"term": "毫克每立方米", "abbr": "mg/m³", "english": "milligrams per cubic meter", "category": "单位"},
        {"term": "分贝", "abbr": "dB", "english": "decibel", "category": "单位"},
    ]

    def __init__(self):
        QUALITY_DIR.mkdir(parents=True, exist_ok=True)
        self._terms: dict[str, Term] = {}
        self._by_abbr: dict[str, str] = {}  # abbreviation → term
        self._by_english: dict[str, str] = {}  # english → term
        self._load()

    def extract_from_document(self, content: str, domain: str = ""):
        """Scan document text for known terms and learn new ones.

        Auto-detects patterns like:
        - "SO2 (二氧化硫)" → synonym pair
        - "单位: mg/m³" → unit term
        - "GB3095-2012" → standard reference
        """
        content_lower = content.lower()
        new_count = 0

        # Pattern 1: Abbreviation definitions "SO2 (二氧化硫)"
        for m in re.finditer(r'([A-Z][A-Za-z0-9]+)\s*[（(]\s*([\u4e00-\u9fff]+)\s*[）)]', content):
            abbr = m.group(1)
            full = m.group(2)
            if abbr not in self._by_abbr:
                self.add_term(Term(term=full, abbreviation=abbr, category=domain))
                new_count += 1

        # Pattern 2: English-Chinese pairs "sulfur dioxide (SO2) 二氧化硫"
        for m in re.finditer(r'([a-zA-Z\s]{5,40})\s*[（(]\s*([A-Za-z0-9]+)\s*[）)]\s*([\u4e00-\u9fff]+)', content):
            eng = m.group(1).strip()
            abbr = m.group(2)
            cn = m.group(3)
            if abbr not in self._by_abbr:
                self.add_term(Term(term=cn, abbreviation=abbr, english=eng, category=domain))
                new_count += 1

        # Pattern 3: Update frequency for known terms
        for term_name, term_obj in list(self._terms.items()):
            if term_name in content or term_obj.abbreviation in content:
                term_obj.frequency += 1
                term_obj.last_seen = time.time()

        if new_count:
            self._save()
            logger.debug(f"Dictionary: +{new_count} new terms from document")

        return new_count

    def add_term(self, term: Term):
        """Add or merge a term."""
        if term.term in self._terms:
            existing = self._terms[term.term]
            existing.frequency += 1
            existing.last_seen = time.time()
            if term.abbreviation and not existing.abbreviation:
                existing.abbreviation = term.abbreviation
            if term.english and not existing.english:
                existing.english = term.english
        else:
            if not term.first_seen:
                term.first_seen = time.time()
            self._terms[term.term] = term

        if term.abbreviation:
            self._by_abbr[term.abbreviation] = term.term
        if term.english:
            self._by_english[term.english.lower()] = term.term

    def lookup(self, query: str) -> Term | None:
        """Look up a term by name, abbreviation, or English."""
        if query in self._terms:
            return self._terms[query]
        if query in self._by_abbr:
            return self._terms[self._by_abbr[query]]
        if query.lower() in self._by_english:
            return self._terms[self._by_english[query.lower()]]
        # Fuzzy match
        for name, term in self._terms.items():
            if query in name or (term.abbreviation and query in term.abbreviation):
                return term
        return None

    def expand_abbreviations(self, text: str) -> str:
        """Replace known abbreviations with full terms inline."""
        result = text
        for abbr, full in sorted(self._by_abbr.items(), key=lambda x: -len(x[0])):
            if abbr in result and len(abbr) > 1:
                result = result.replace(abbr, f"{abbr}（{full}）")
        return result

    def search(self, query: str, limit: int = 10) -> list[Term]:
        q = query.lower()
        results = []
        for term in self._terms.values():
            score = 0
            if q in term.term.lower():
                score = 3
            elif q in (term.abbreviation or "").lower():
                score = 2
            elif q in (term.english or "").lower():
                score = 1
            if score:
                results.append((term, score))
        results.sort(key=lambda x: -x[1])
        return [r[0] for r in results[:limit]]

    def stats(self) -> dict:
        return {
            "total_terms": len(self._terms),
            "with_abbreviation": sum(1 for t in self._terms.values() if t.abbreviation),
            "with_english": sum(1 for t in self._terms.values() if t.english),
            "by_category": dict(Counter(t.category for t in self._terms.values() if t.category)),
            "most_frequent": sorted(self._terms.values(), key=lambda t: -t.frequency)[:5],
        }

    def _save(self):
        data = {}
        for name, t in self._terms.items():
            data[name] = {
                "term": t.term, "abbreviation": t.abbreviation,
                "english": t.english, "category": t.category,
                "definition": t.definition, "synonyms": t.synonyms,
                "frequency": t.frequency,
                "first_seen": t.first_seen, "last_seen": t.last_seen,
            }
        DICT_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        # Load builtin + persisted
        for bt in self.BUILTIN_EIA_TERMS:
            t = Term(**bt)
            self._terms[t.term] = t
            if t.abbreviation:
                self._by_abbr[t.abbreviation] = t.term
            if t.english:
                self._by_english[t.english.lower()] = t.term

        if DICT_DB.exists():
            try:
                data = json.loads(DICT_DB.read_text())
                for name, d in data.items():
                    if name not in self._terms:
                        t = Term(**d)
                        self._terms[name] = t
                        if t.abbreviation:
                            self._by_abbr[t.abbreviation] = t.term
                        if t.english:
                            self._by_english[t.english.lower()] = t.term
            except Exception:
                pass


from collections import Counter

_nf: MessageNoiseFilter | None = None
_ig: IndustryGovernance | None = None
_td: IndustryDictionary | None = None


def get_noise_filter() -> MessageNoiseFilter:
    global _nf
    if _nf is None:
        _nf = MessageNoiseFilter()
    return _nf

def get_governance() -> IndustryGovernance:
    global _ig
    if _ig is None:
        _ig = IndustryGovernance()
    return _ig

def get_term_dictionary() -> IndustryDictionary:
    global _td
    if _td is None:
        _td = IndustryDictionary()
    return _td
