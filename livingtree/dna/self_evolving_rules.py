"""Self-Evolving Rules Engine — TACO-inspired autonomous compression rule discovery.

Replaces static regex patterns (e.g. output_compressor.py's PHRASES_TO_REMOVE)
with a self-evolving rule engine that:

  1. Observes interaction history (LLM outputs, terminal outputs)
  2. Discovers patterns that can be compressed
  3. Generates rules and validates them
  4. Repairs rules that cause information loss
  5. Feeds rules into the GlobalRulePool for cross-session reuse

Integration:
  - GlobalRulePool: store and retrieve rules
  - OutputCompressor: consume rules for LLM output compression
  - TerminalCompressor: consume rules for terminal output compression
  - MetaMemory: track rule effectiveness over time
  - SelfEvolvingEngine: reuse the same DGM-H pattern for rule evolution

Architecture mirrors TACO's online rule planner/evolver:
  - Observer: scans outputs for compression opportunities
  - Generator: creates candidate rules
  - Tester: validates rules against known output samples
  - Deployer: adds rules to GlobalRulePool (with rollback)
"""

from __future__ import annotations

import re
import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


# ── Evolution metadata ───────────────────────────────────────────────
EVOLVE_DIR = Path(".livingtree/meta/evolve")
EVOLVE_HISTORY = EVOLVE_DIR / "rule_evolution.json"


@dataclass
class RuleCandidate:
    """A proposed compression rule before deployment."""
    id: str
    rule_data: dict  # Will become a CompressionRule
    source: str = ""          # Where this candidate came from
    confidence: float = 0.5   # 0-1, higher = more likely to be good
    test_results: dict = field(default_factory=dict)
    status: str = "pending"   # pending → tested → approved → deployed → rejected
    created_at: float = field(default_factory=time.time)


@dataclass
class EvolutionStats:
    """DGM-H metrics for the rule evolution process itself."""
    candidates_generated: int = 0
    candidates_tested: int = 0
    candidates_deployed: int = 0
    candidates_rejected: int = 0
    rules_repaired: int = 0
    rules_retired: int = 0
    tokens_spent: int = 0
    time_spent_ms: int = 0

    @property
    def deploy_rate(self) -> float:
        return round(self.candidates_deployed / max(self.candidates_generated, 1), 3)


class SelfEvolvingRules:
    """Autonomous compression rule discovery, repair, and lifecycle management.

    Unlike SelfEvolvingEngine (which evolves code), this evolves *compression
    rules* — the patterns that determine what gets filtered from LLM/terminal
    context. Uses the same DGM-H (observe→generate→test→deploy) pipeline.
    """

    MAX_CANDIDATES_PER_CYCLE = 5
    MIN_CONFIDENCE_THRESHOLD = 0.4
    WINDOW_SIZE = 10  # Number of recent observations to analyze

    def __init__(self, pool=None, memory=None, consciousness=None):
        self._pool = pool  # GlobalRulePool
        self._memory = memory  # MetaMemory
        self._consciousness = consciousness  # LLM for high-quality rule generation
        self._observation_history: list[dict] = []
        self._candidates: list[RuleCandidate] = []
        self._stats = EvolutionStats()
        self._load_history()

    # ── DGM-H Cycle: Observe ────────────────────────────────────

    def observe_output(self, raw_output: str, compressed_output: str = "",
                       namespace: str = "general", command: str = "",
                       saving_pct: float = 0.0) -> None:
        """Record an output observation for pattern analysis.

        Called after each compression operation. The observer accumulates
        recent outputs and periodically scans for patterns.

        Args:
            raw_output: The uncompressed output
            compressed_output: The compressed output (for diff analysis)
            namespace: Workflow namespace (git, build, test, shell)
            command: The command that generated this output
            saving_pct: How much was saved (0-100)
        """
        self._observation_history.append({
            "raw": raw_output[:5000],
            "compressed": compressed_output[:5000] if compressed_output else "",
            "namespace": namespace,
            "command": command[:200],
            "saving_pct": saving_pct,
            "timestamp": time.time(),
        })

        # Keep window bounded
        if len(self._observation_history) > 100:
            self._observation_history = self._observation_history[-100:]

    async def observe_and_propose(self) -> list[RuleCandidate]:
        """DGM-H Observe phase: scan recent history and propose new rules.

        Uses heuristics for pattern discovery + optional LLM for refinement.
        Returns candidates ready for testing.
        """
        recent = self._observation_history[-self.WINDOW_SIZE:]
        if len(recent) < 3:
            return []

        candidates = []

        # ── Strategy 1: Low-compression outputs → discover new rules ──
        for obs in recent:
            if obs.get("saving_pct", 100) > 80:
                # Output already well-compressed, skip
                continue

            raw = obs.get("raw", "")
            ns = obs.get("namespace", "general")
            cmd = obs.get("command", "")

            if not raw or len(raw) < 500:
                continue

            # Heuristic: detect repetitive boilerplate
            boilerplate = self._detect_boilerplate(raw)
            if boilerplate:
                candidate = self._create_candidate(
                    action="remove",
                    namespace=ns,
                    match_pattern=boilerplate["pattern"],
                    source=f"boilerplate-detection:{ns}",
                    confidence=boilerplate.get("confidence", 0.6),
                )
                if candidate:
                    candidates.append(candidate)

            # Heuristic: detect verbose but structured output
            if len(raw.splitlines()) > 100:
                structure = self._detect_structured_verbosity(raw)
                if structure:
                    candidate = self._create_candidate(
                        action="truncate_tail",
                        namespace=ns,
                        match_pattern=structure["header_pattern"],
                        truncate_lines=structure.get("suggested_lines", 50),
                        source=f"structure-detection:{ns}",
                        confidence=structure.get("confidence", 0.7),
                    )
                    if candidate:
                        candidates.append(candidate)

        self._candidates = candidates[:self.MAX_CANDIDATES_PER_CYCLE]
        self._stats.candidates_generated += len(self._candidates)
        return self._candidates

    # ── DGM-H Cycle: Generate ───────────────────────────────────

    def _create_candidate(self, action: str, namespace: str = "general",
                          match_pattern: str = "", source: str = "",
                          confidence: float = 0.5, **kwargs) -> RuleCandidate | None:
        """Create a rule candidate from discovered patterns."""
        if not match_pattern:
            return None

        # Validate regex
        try:
            re.compile(match_pattern)
        except re.error:
            logger.debug(f"Invalid regex in candidate: {match_pattern[:60]}")
            return None

        import uuid, hashlib
        cid = hashlib.md5(f"{namespace}-{action}-{uuid.uuid4().hex[:6]}".encode()).hexdigest()[:12]

        from ..execution.global_rule_pool import RuleAction
        rule_data = {
            "id": cid,
            "name": f"evolved-{namespace}-{action}",
            "namespace": namespace,
            "priority": 55,
            "action": action,
            "match_pattern": match_pattern,
            "match_context": "",
            "auto_generated": True,
            "origin_task": f"evolve-{source}",
        }

        # Add action-specific params
        for key, val in kwargs.items():
            if val is not None:
                rule_data[key] = val

        return RuleCandidate(
            id=cid,
            rule_data=rule_data,
            source=source,
            confidence=confidence,
        )

    # ── DGM-H Cycle: Test ───────────────────────────────────────

    def test_candidate(self, candidate: RuleCandidate) -> RuleCandidate:
        """Test a candidate rule against historical observations.

        Validates:
          1. Does the pattern actually match? (sanity)
          2. Does it preserve critical information? (safety)
          3. Does it provide meaningful compression? (utility)
        """
        self._stats.candidates_tested += 1
        import time as _time; t0 = _time.time()

        from ..execution.global_rule_pool import CompressionRule, RuleAction
        rule = CompressionRule.from_dict(candidate.rule_data)

        # Find relevant observations for testing
        relevant_obs = [
            obs for obs in self._observation_history[-20:]
            if obs.get("namespace", "general") == rule.namespace
        ]

        if not relevant_obs:
            candidate.test_results = {"passed": False, "reason": "no_test_data"}
            candidate.status = "tested"
            return candidate

        test_count = 0
        match_count = 0
        saved_chars = 0
        false_positives = 0

        for obs in relevant_obs:
            raw = obs.get("raw", "")
            if not raw:
                continue

            test_count += 1
            matched = False

            if rule.match_pattern:
                try:
                    matched = bool(re.search(rule.match_pattern, raw,
                                             re.IGNORECASE | re.DOTALL))
                except re.error:
                    continue

            if matched:
                match_count += 1
                # Simulate compression
                if rule.action == RuleAction.REMOVE:
                    # Check: would removal lose critical info?
                    if self._contains_critical_info(raw):
                        false_positives += 1
                    else:
                        saved_chars += len(raw)
                elif rule.action == RuleAction.TRUNCATE_TAIL:
                    saved_chars += max(0, len(raw) - rule.truncate_chars)
                elif rule.action == RuleAction.EXTRACT_PATTERN:
                    saved_chars += max(0, len(raw) - min(len(raw) // 4, rule.truncate_chars))
                elif rule.action == RuleAction.REPLACE:
                    try:
                        result, count = re.subn(
                            rule.replace_pattern, rule.replace_with,
                            raw, flags=re.IGNORECASE | re.DOTALL)
                        if count > 0:
                            saved_chars += max(0, len(raw) - len(result))
                    except re.error:
                        pass

        match_rate = match_count / max(test_count, 1)
        fp_rate = false_positives / max(match_count, 1) if match_count > 0 else 0
        passed = match_rate >= 0.1 and fp_rate <= 0.3 and saved_chars > 0

        self._stats.time_spent_ms += int((_time.time() - t0) * 1000)

        candidate.test_results = {
            "passed": passed,
            "test_count": test_count,
            "match_count": match_count,
            "match_rate": round(match_rate, 3),
            "false_positives": false_positives,
            "fp_rate": round(fp_rate, 3),
            "saved_chars": saved_chars,
            "reason": "ok" if passed else ("low_match_rate" if match_rate < 0.1
                      else "high_fp_rate" if fp_rate > 0.3
                      else "no_savings"),
        }
        candidate.status = "tested"
        candidate.confidence = match_rate * (1 - fp_rate)

        return candidate

    # ── DGM-H Cycle: Deploy ─────────────────────────────────────

    def deploy_candidate(self, candidate: RuleCandidate) -> dict:
        """Deploy a tested candidate to the GlobalRulePool."""
        if candidate.status != "tested" or not candidate.test_results.get("passed"):
            candidate.status = "rejected"
            self._stats.candidates_rejected += 1
            return {"deployed": False, "reason": candidate.test_results.get("reason", "not_tested")}

        from ..execution.global_rule_pool import CompressionRule, get_global_rule_pool
        pool = self._pool or get_global_rule_pool()
        rule = CompressionRule.from_dict(candidate.rule_data)

        # Set computed confidence as rule priority
        rule.priority = int(candidate.confidence * 100)
        rule.priority = max(30, min(rule.priority, 70))  # Clamp to 30-70

        if pool.add(rule):
            candidate.status = "deployed"
            self._stats.candidates_deployed += 1
            self._save_history()
            logger.info(f"Deployed rule: {rule.name} (id={rule.id}, conf={candidate.confidence:.2f})")
            return {"deployed": True, "rule_id": rule.id, "name": rule.name}
        else:
            candidate.status = "deploy_failed"
            self._stats.candidates_rejected += 1
            return {"deployed": False, "reason": "pool_full"}

    # ── Rule Repair (TACO's self-repair mechanism) ───────────────

    def repair_rules(self) -> int:
        """Check deployed rules for false positives and repair broken ones.

        TACO principle: rules that cause information loss are detected
        and either repaired (narrowed) or retired (removed).
        """
        from ..execution.global_rule_pool import get_global_rule_pool
        pool = self._pool or get_global_rule_pool()

        repaired = 0

        # Find rules with high false-positive rates
        for rule in pool._rules.values():
            if not rule.auto_generated:
                continue
            if not rule.is_active:
                continue

            total = rule.hit_count + rule.false_positive_count
            if total < 5:
                continue  # Too few samples

            fp_rate = rule.false_positive_count / max(total, 1)

            if fp_rate > 0.5:
                # Rule is causing too many false positives → retire
                pool.remove(rule.id)
                self._stats.rules_retired += 1
                logger.debug(f"Retired rule {rule.name}: fp_rate={fp_rate:.2f}")

            elif fp_rate > 0.3:
                # Rule marginal → reduce priority to minimize impact
                rule.priority = max(10, rule.priority - 20)
                pool.update(rule.id, priority=rule.priority)
                self._stats.rules_repaired += 1
                repaired += 1
                logger.debug(f"Downgraded rule {rule.name}: new_priority={rule.priority}")

        if repaired:
            pool._save()
        return repaired

    # ── Pattern Detection Heuristics ─────────────────────────────

    @staticmethod
    def _detect_boilerplate(text: str) -> dict | None:
        """Detect repetitive boilerplate patterns in text.

        TACO principle: terminal outputs often contain boilerplate
        (progress bars, repeated warnings, setup info) that can be
        safely removed.
        """
        lines = text.splitlines()
        if len(lines) < 10:
            return None

        # Check for identical substrings that repeat
        middle = lines[len(lines)//4:len(lines)*3//4]
        deduped = set(middle)

        if len(deduped) < len(middle) * 0.3:
            # Highly repetitive — propose removal rule
            # Find a representative sample line
            for line in middle:
                if len(line) > 10:
                    escaped = re.escape(line[:40])
                    return {
                        "pattern": f"(?m)^{escaped}.*$",
                        "confidence": min(0.9, 0.5 + (1 - len(deduped) / len(middle))),
                    }

        # Check for common boilerplate indicators
        boilerplate_indicators = [
            (r"(?im)^\s*$", 0.3),
            (r"(?i)^\d{1,3}%\|", 0.8),         # Progress bar
            (r"(?i)^\[[\d/]+\]", 0.7),          # Progress indicator
            (r"(?i)^=+\s*\d+%", 0.8),           # Download progress
            (r"(?i)^\[\*+\s*\]", 0.9),          # Loading bar
        ]

        for pattern, confidence in boilerplate_indicators:
            matches = len(re.findall(pattern, text, re.MULTILINE))
            if matches >= 3:
                return {
                    "pattern": pattern,
                    "confidence": min(confidence + matches * 0.05, 0.95),
                }

        return None

    @staticmethod
    def _detect_structured_verbosity(text: str) -> dict | None:
        """Detect verbose structured output that can be truncated."""
        lines = text.splitlines()
        if len(lines) < 50:
            return None

        # Check for tabular/columnar data
        tabular = 0
        for line in lines:
            if len(re.findall(r'\s{2,}', line)) >= 3:
                tabular += 1

        if tabular > 20:
            # Find a distinctive header or first data line
            for line in lines[:10]:
                if len(line) > 20:
                    escaped = re.escape(line[:50])
                    return {
                        "header_pattern": f"(?m)^{escaped}",
                        "suggested_lines": 30,
                        "confidence": 0.7,
                    }

        # Check for log-style output
        log_lines = 0
        for line in lines:
            if re.match(r'^[\d\-:TZ,.\s]{10,}\s+(INFO|WARN|DEBUG|ERROR|TRACE)', line):
                log_lines += 1

        if log_lines > 30:
            return {
                "header_pattern": r"^[\d\-:TZ,.\s]{10,}",
                "suggested_lines": 20,
                "confidence": 0.75,
            }

        return None

    @staticmethod
    def _contains_critical_info(text: str) -> bool:
        """Check if text contains information that must be preserved."""
        critical_patterns = [
            r"(?i)(Traceback|Error:|FAILED|FATAL|panic!|abort)",
            r"(?i)(TypeError|ValueError|KeyError|SyntaxError|ImportError)",
            r"(?i)(Permission denied|Access denied|not found)",
            r"(?i)(commit [a-f0-9]{7,})",
            r"(?i)(fatal:|refusing to merge)",
        ]
        for pat in critical_patterns:
            if re.search(pat, text):
                return True
        return False

    # ── LLM-enhanced rule generation (for high-confidence candidates) ──

    async def refine_with_llm(self, candidate: RuleCandidate) -> RuleCandidate:
        """Use LLM consciousness to refine a rule candidate.

        Sends the observed pattern and asks the LLM to suggest a more
        precise match pattern or action.
        """
        if not self._consciousness:
            return candidate

        obs_sample = ""
        for obs in self._observation_history[-5:]:
            if obs.get("namespace") == candidate.rule_data.get("namespace"):
                obs_sample = obs.get("raw", "")[:2000]
                break

        if not obs_sample:
            return candidate

        prompt = (
            "Analyze this terminal output and suggest a precise compression rule:\n\n"
            f"Output sample:\n{obs_sample}\n\n"
            f"Current proposed rule: {json.dumps(candidate.rule_data, indent=2)}\n\n"
            "Output JSON with these fields:\n"
            "- action: 'pass_through'|'truncate_tail'|'extract_pattern'|'remove'|'replace'\n"
            "- match_pattern: regex that identifies this type of output\n"
            "- confidence: 0.0-1.0\n"
            "- reason: brief explanation\n"
            '{"action": "...", "match_pattern": "...", "confidence": 0.0, "reason": "..."}'
        )

        try:
            raw = await self._consciousness.query(prompt, max_tokens=512, temperature=0.3)
            data = self._parse_llm_json(raw)
            if data:
                action = data.get("action", candidate.rule_data.get("action", "truncate_tail"))
                if action != candidate.rule_data.get("action"):
                    candidate.rule_data["action"] = action
                if data.get("match_pattern"):
                    try:
                        re.compile(data["match_pattern"])
                        candidate.rule_data["match_pattern"] = data["match_pattern"]
                    except re.error:
                        pass
                if data.get("confidence"):
                    candidate.confidence = float(data["confidence"])
        except Exception as e:
            logger.debug(f"LLM rule refinement: {e}")

        return candidate

    @staticmethod
    def _parse_llm_json(raw: str) -> dict | None:
        try:
            if "```json" in raw:
                start = raw.index("```json") + 7
                end = raw.index("```", start)
                raw = raw[start:end]
            elif "```" in raw:
                start = raw.index("```") + 3
                end = raw.index("```", start)
                raw = raw[start:end]
            raw = raw.strip()
            if raw.startswith("{"):
                return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
        return None

    # ── Halucinate: Creative Rule Generation ────────────────────

    async def hallucinate_rules(
        self, context: str, n_candidates: int = 5,
    ) -> list[RuleCandidate]:
        """Generate creative compression rule candidates by "hallucination".

        Inspired by deep network hallucination in de novo protein design
        (Anishchenko et al., Nature 2021): intentionally generate diverse
        candidate rules, then filter for validity.

        Uses LLM consciousness (if available) to propose novel rules for
        patterns that might appear in this domain, even if not yet observed.
        Falls back to pattern-based rule generation from context if no LLM.

        Args:
            context: Domain context or observation sample to inspire rules.
            n_candidates: Number of creative candidates to generate.

        Returns:
            List of RuleCandidate objects with status="hallucinated".
        """
        max_n = min(n_candidates, self.MAX_CANDIDATES_PER_CYCLE)

        if self._consciousness and hasattr(self._consciousness, 'query'):
            return await self._llm_hallucinate(context, max_n)
        else:
            return self._heuristic_hallucinate(context, max_n)

    async def _llm_hallucinate(
        self, context: str, n: int,
    ) -> list[RuleCandidate]:
        """Use LLM to hallucinate creative compression rules."""
        prompt = (
            f"You are a creative compression rule designer. Given this context "
            f"from a terminal agent workflow, propose {n} NOVEL compression "
            f"rules. Think outside the box — propose rules for patterns that "
            f"MIGHT appear even if they're not in this exact sample.\n\n"
            f"Context sample:\n{context[:3000]}\n\n"
            f"For each rule, specify:\n"
            f"- action: 'extract_pattern'|'remove'|'truncate_tail'|'replace'|'keep_only'\n"
            f"- match_pattern: a valid regex that identifies this type of output\n"
            f"- namespace: 'git'|'build'|'test'|'shell'|'error'|'general'\n"
            f"- confidence: 0.0-1.0 (how likely this rule is useful)\n"
            f"- reason: brief explanation\n\n"
            f"Output JSON array:\n"
            f'[{{"action": "...", "match_pattern": "...", "namespace": "...", '
            f'"confidence": 0.0, "reason": "..."}}]'
        )

        try:
            raw = await self._consciousness.query(
                prompt, max_tokens=800, temperature=0.8)  # Higher temp for creativity
            candidates = self._parse_hallucinated_json(raw, n)
            logger.info(
                f"Hallucinate: generated {len(candidates)}/{n} creative rule candidates")
            return candidates
        except Exception as e:
            logger.debug(f"LLM hallucinate failed: {e}")
            return self._heuristic_hallucinate(context, n)

    def _heuristic_hallucinate(
        self, context: str, n: int,
    ) -> list[RuleCandidate]:
        """Heuristic creative rule generation from context patterns.

        Finds: repeated strings, long lines, common prefix/suffix patterns,
        and generates REMOVE or TRUNCATE rules for them.
        """
        candidates: list[RuleCandidate] = []
        if not context:
            return candidates

        # Find repeated patterns (appear ≥3 times, length ≥10)
        lines = context.split("\n")
        pattern_counts: dict[str, int] = {}
        for line in lines:
            stripped = line.strip()
            if len(stripped) >= 10:
                pattern_counts[stripped] = pattern_counts.get(stripped, 0) + 1

        repeated = [
            (p, c) for p, c in pattern_counts.items()
            if c >= 3 and len(p) >= 15
        ]
        repeated.sort(key=lambda x: x[1], reverse=True)

        for i, (pattern, count) in enumerate(repeated[:n]):
            candidate_id = f"halluc_{int(time.time())}_{i}"
            try:
                escaped = re.escape(pattern)
                candidate = RuleCandidate(
                    id=candidate_id,
                    rule_data={
                        "namespace": "general",
                        "action": "remove",
                        "match_pattern": f"^{escaped}$",
                        "priority": 3,
                        "max_chars": 0,
                    },
                    source="hallucinate_heuristic",
                    confidence=min(0.5 + count * 0.1, 0.9),
                    status="hallucinated",
                )
                candidates.append(candidate)
            except re.error:
                continue

        # Also generate rules for long-line truncation
        long_lines = [
            l for l in lines if len(l) > 500
        ]
        if long_lines:
            cand_id = f"halluc_trunc_{int(time.time())}"
            candidates.append(RuleCandidate(
                id=cand_id,
                rule_data={
                    "namespace": "general",
                    "action": "truncate_tail",
                    "match_pattern": r"^.{500,}",
                    "priority": 2,
                    "max_chars": 200,
                },
                source="hallucinate_heuristic",
                confidence=0.55,
                status="hallucinated",
            ))

        self._stats.candidates_generated += len(candidates)
        return candidates[:n]

    def _parse_hallucinated_json(
        self, raw: str, max_n: int,
    ) -> list[RuleCandidate]:
        """Parse hallucinated rules from LLM JSON array response."""
        try:
            if "```json" in raw:
                start = raw.index("```json") + 7
                end = raw.index("```", start)
                raw = raw[start:end]
            elif "```" in raw:
                start = raw.index("```") + 3
                end = raw.index("```", start)
                raw = raw[start:end]
            raw = raw.strip()

            # Try array first, then single object
            if raw.startswith("["):
                data = json.loads(raw)
            elif raw.startswith("{"):
                data = [json.loads(raw)]
            else:
                return []

            candidates: list[RuleCandidate] = []
            for i, item in enumerate(data[:max_n]):
                candidate_id = f"halluc_{int(time.time())}_{i}"
                try:
                    pattern = item.get("match_pattern", "")
                    if pattern:
                        re.compile(pattern)  # Validate regex
                    candidate = RuleCandidate(
                        id=candidate_id,
                        rule_data={
                            "namespace": item.get("namespace", "general"),
                            "action": item.get("action", "remove"),
                            "match_pattern": pattern,
                            "priority": 3,
                            "max_chars": item.get("max_chars", 0),
                        },
                        source="hallucinate_llm",
                        confidence=float(item.get("confidence", 0.5)),
                        status="hallucinated",
                    )
                    candidates.append(candidate)
                except (re.error, ValueError):
                    continue

            self._stats.candidates_generated += len(candidates)
            return candidates
        except (ValueError, json.JSONDecodeError) as e:
            logger.debug(f"Parse hallucinated JSON: {e}")
            return []

    # ── Validate Candidates ──────────────────────────────────────

    def validate_candidates(
        self, candidates: list[RuleCandidate],
    ) -> list[RuleCandidate]:
        """Filter and validate rule candidates before deployment.

        Checks:
          1. Regex validity (compile test)
          2. No duplicate pattern already in pool
          3. Action is a known valid type
          4. Confidence exceeds minimum threshold

        Args:
            candidates: Raw candidates from hallucinate or observe.

        Returns:
            Validated candidates with status updated to "validated" or "rejected".
        """
        VALID_ACTIONS = {
            "extract_pattern", "remove", "truncate_tail",
            "replace", "keep_only", "pass_through",
        }
        validated: list[RuleCandidate] = []

        for c in candidates:
            # Check 1: Regex validity
            pattern = c.rule_data.get("match_pattern", "")
            if pattern:
                try:
                    re.compile(pattern)
                except re.error:
                    c.status = "rejected"
                    logger.debug(f"Rejected '{c.id}': invalid regex '{pattern}'")
                    continue

            # Check 2: Duplicate check against pool
            if self._pool and hasattr(self._pool, 'get_rules'):
                existing = self._pool.get_rules(
                    namespace=c.rule_data.get("namespace", "general"))
                is_duplicate = any(
                    e.get("match_pattern") == pattern for e in existing)
                if is_duplicate:
                    c.status = "rejected"
                    logger.debug(f"Rejected '{c.id}': duplicate pattern in pool")
                    continue

            # Check 3: Valid action type
            action = c.rule_data.get("action", "")
            if action not in VALID_ACTIONS:
                c.status = "rejected"
                logger.debug(f"Rejected '{c.id}': invalid action '{action}'")
                continue

            # Check 4: Confidence threshold
            if c.confidence < self.MIN_CONFIDENCE_THRESHOLD:
                c.status = "rejected"
                logger.debug(f"Rejected '{c.id}': low confidence {c.confidence:.2f}")
                continue

            # Passed all checks
            c.status = "validated"
            validated.append(c)

        rejected = len(candidates) - len(validated)
        self._stats.candidates_rejected += rejected
        logger.info(
            f"Validated: {len(validated)} passed, {rejected} rejected "
            f"of {len(candidates)} candidates")
        return validated

    # ── Persistence ─────────────────────────────────────────────

    def _save_history(self):
        try:
            EVOLVE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "stats": {
                    "candidates_generated": self._stats.candidates_generated,
                    "candidates_tested": self._stats.candidates_tested,
                    "candidates_deployed": self._stats.candidates_deployed,
                    "candidates_rejected": self._stats.candidates_rejected,
                    "rules_repaired": self._stats.rules_repaired,
                    "rules_retired": self._stats.rules_retired,
                },
                "updated_at": time.time(),
            }
            EVOLVE_HISTORY.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except Exception as e:
            logger.debug(f"Evolve history save: {e}")

    def _load_history(self):
        try:
            if EVOLVE_HISTORY.exists():
                data = json.loads(EVOLVE_HISTORY.read_text(encoding="utf-8"))
                stats = data.get("stats", {})
                self._stats.candidates_generated = stats.get("candidates_generated", 0)
                self._stats.candidates_tested = stats.get("candidates_tested", 0)
                self._stats.candidates_deployed = stats.get("candidates_deployed", 0)
                self._stats.candidates_rejected = stats.get("candidates_rejected", 0)
                self._stats.rules_repaired = stats.get("rules_repaired", 0)
                self._stats.rules_retired = stats.get("rules_retired", 0)
        except Exception as e:
            logger.debug(f"Evolve history load: {e}")

    # ── Full Cycle ──────────────────────────────────────────────

    async def run_evolution_cycle(self) -> dict:
        """Run a complete DGM-H evolution cycle: hallucinate → observe → test → deploy → repair.

        Added hallucinate phase (protein design-inspired): generate creative
        rule candidates from recent context, validate them, and merge with
        observed candidates before testing and deployment.
        """
        result = {
            "candidates_proposed": 0,
            "candidates_tested": 0,
            "candidates_deployed": 0,
            "rules_repaired": 0,
            "hallucinated_generated": 0,
            "hallucinated_validated": 0,
        }

        # Phase 0: Creative Hallucination (inspired by deep network hallucination)
        context = json.dumps(
            [o.get("raw", "")[:500] for o in self._observation_history[-3:]])
        hallucinated = await self.hallucinate_rules(context=context)
        result["hallucinated_generated"] = len(hallucinated)

        # Validate hallucinated candidates
        hallucinated = self.validate_candidates(hallucinated)
        result["hallucinated_validated"] = len(hallucinated)

        # Phase 1: Observe & Propose
        observed = await self.observe_and_propose()
        result["candidates_proposed"] = len(observed)

        # Merge all candidates
        all_candidates = hallucinated + observed
        self._candidates.extend(all_candidates)

        # Phase 2: Test
        for c in all_candidates:
            c = self.test_candidate(c)
            if c.status == "tested":
                result["candidates_tested"] += 1

        # Phase 3: Deploy passing candidates
        for c in all_candidates:
            if c.test_results.get("passed"):
                deploy_result = self.deploy_candidate(c)
                if deploy_result.get("deployed"):
                    result["candidates_deployed"] += 1

        # Phase 4: Repair broken rules
        result["rules_repaired"] = self.repair_rules()
        self._save_history()

        return result


# ── Singleton ────────────────────────────────────────────────────────

_self_evolving_rules: SelfEvolvingRules | None = None


def get_self_evolving_rules(pool=None, memory=None, consciousness=None) -> SelfEvolvingRules:
    """Get or create the singleton SelfEvolvingRules engine."""
    global _self_evolving_rules
    if _self_evolving_rules is None:
        _self_evolving_rules = SelfEvolvingRules(
            pool=pool, memory=memory, consciousness=consciousness)
    return _self_evolving_rules


def reset_self_evolving_rules() -> None:
    """Test helper."""
    global _self_evolving_rules
    _self_evolving_rules = None
