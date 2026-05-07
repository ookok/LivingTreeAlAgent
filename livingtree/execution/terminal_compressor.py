"""TerminalCompressor — TACO-inspired terminal output compression middleware.

Sits between terminal/shell execution and the LLM context window.
Instead of naive truncation (observation[:500]), intelligently compresses
terminal outputs using structured rules from the GlobalRulePool.

Design principles (from TACO paper):
  1. Preserve task-critical signals (errors, test failures, git status)
  2. Discard low-value noise (boilerplate, progress bars, npm warnings)
  3. Adapt to workflow type (git, build, test, shell — different rules)
  4. Self-evolve: unused rules are pruned, new patterns are discovered

Usage:
    compressor = get_terminal_compressor()
    result = compressor.compress(output, command="git log --oneline")
    # result.compressed → ready for LLM context
    # result.saved_chars → token savings
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from .global_rule_pool import (
    CompressionRule, GlobalRulePool, RuleAction,
    get_global_rule_pool,
)

# ── Default limits ───────────────────────────────────────────────────
DEFAULT_MAX_CHARS = 3000        # Max chars after compression
DEFAULT_MAX_LINES = 200         # Max lines after compression
DEFAULT_TRUNCATE_LINES = 50     # Truncate to N lines if no rules match
DEFAULT_TRUNCATE_CHARS = 2000   # Truncate to N chars if no rules match


@dataclass
class CompressorStats:
    """Compression statistics for monitoring and evolution."""
    total_input_chars: int = 0
    total_output_chars: int = 0
    total_calls: int = 0
    rules_applied: int = 0
    fallback_truncations: int = 0
    pass_throughs: int = 0

    @property
    def compression_ratio(self) -> float:
        return round(self.total_output_chars / max(self.total_input_chars, 1), 3)

    @property
    def avg_saving_pct(self) -> float:
        saved = self.total_input_chars - self.total_output_chars
        return round(saved / max(self.total_input_chars, 1) * 100, 1)


@dataclass
class CompressResult:
    """Result of a compression operation."""
    original: str
    compressed: str = ""
    rules_applied: list[CompressionRule] = field(default_factory=list)
    original_chars: int = 0
    compressed_chars: int = 0
    method: str = "none"  # "rule", "fallback", "passthrough", "none"

    @property
    def saved_chars(self) -> int:
        return self.original_chars - self.compressed_chars

    @property
    def saving_pct(self) -> float:
        return round(self.saved_chars / max(self.original_chars, 1) * 100, 1)


class TerminalCompressor:
    """TACO-style terminal output compression with rule-based intelligence.

    Pipeline:
      1. Check if output is "small enough" → pass through
      2. Detect workflow namespace from command (git, build, test, shell)
      3. Find and apply matching rules from GlobalRulePool
      4. If no rules match → smart fallback truncation
      5. Track stats for rule evolution
    """

    def __init__(self, pool: GlobalRulePool | None = None,
                 max_chars: int = DEFAULT_MAX_CHARS,
                 max_lines: int = DEFAULT_MAX_LINES):
        self._pool = pool or get_global_rule_pool()
        self.max_chars = max_chars
        self.max_lines = max_lines
        self.stats = CompressorStats()

    def compress(self, output: str, command: str = "",
                 namespace: str = "", context: str = "") -> CompressResult:
        """Compress terminal output using rule-based matching.

        Args:
            output: Raw terminal output to compress
            command: The shell command that produced this output
            namespace: Override namespace detection (git/build/test/shell)
            context: Additional context (e.g. task description)

        Returns:
            CompressResult with compressed text and metadata
        """
        self.stats.total_calls += 1
        result = CompressResult(
            original=output,
            original_chars=len(output),
        )

        # ── Step 0: Small output → pass through ──
        if len(output) < 200 and len(output.splitlines()) < 5:
            result.compressed = output
            result.compressed_chars = len(output)
            result.method = "passthrough"
            self.stats.pass_throughs += 1
            self.stats.total_input_chars += len(output)
            self.stats.total_output_chars += len(output)
            return result

        # ── Step 1: Detect namespace ──
        if not namespace:
            namespace = self._detect_namespace(command, output)
        context = context or command

        # ── Step 2: Apply matching rules ──
        compressed, applied_rules = self._pool.apply_all_matching(
            output, namespace=namespace, context=context)

        # ── Step 3: If rules applied, check saturation ──
        if applied_rules:
            result.rules_applied = applied_rules
            # Post-rule: ensure not too large
            if len(compressed) > self.max_chars * 2:
                compressed = self._smart_truncate(
                    compressed, self.max_chars, self.max_lines)
            result.compressed = compressed
            result.compressed_chars = len(compressed)
            result.method = "rule"
            self.stats.rules_applied += len(applied_rules)
            self.stats.total_input_chars += len(output)
            self.stats.total_output_chars += len(compressed)
            return result

        # ── Step 4: No rules matched → fallback truncation ──
        compressed = self._smart_truncate(output, self.max_chars, self.max_lines)
        result.compressed = compressed
        result.compressed_chars = len(compressed)
        result.method = "fallback"
        self.stats.fallback_truncations += 1
        self.stats.total_input_chars += len(output)
        self.stats.total_output_chars += len(compressed)
        return result

    def compress_many(self, outputs: list[tuple[str, str]]) -> list[CompressResult]:
        """Compress multiple terminal outputs. Each tuple: (output, command)."""
        return [self.compress(out, cmd) for out, cmd in outputs]

    def _detect_namespace(self, command: str, output: str = "") -> str:
        """Detect workflow namespace from command string.

        Uses regex matching against command, then output as fallback.
        """
        if not command:
            return "shell"

        cmd_lower = command.lower().strip()

        # Exact command checks (ordered by specificity)
        namespace_patterns = [
            (r"\bgit\b", "git"),
            (r"\bnpm\b", "build"),
            (r"\byarn\b", "build"),
            (r"\bpip\s+install\b", "build"),
            (r"\bpip\s+uninstall\b", "build"),
            (r"\bcargo\b", "build"),
            (r"\bgo\s+(build|install|mod)\b", "build"),
            (r"\bdocker\s+(build|compose)\b", "build"),
            (r"\bmake\b", "build"),
            (r"\bnpx\b", "build"),
            (r"\bpytest\b", "test"),
            (r"\bunittest\b", "test"),
            (r"\bgo\s+test\b", "test"),
            (r"\bcargo\s+test\b", "test"),
            (r"\bjest\b", "test"),
            (r"\bvitest\b", "test"),
            (r"\bmocha\b", "test"),
            (r"\bpython\b", "shell"),
            (r"\bnode\b", "shell"),
            (r"\bcurl\b", "shell"),
            (r"\bwget\b", "shell"),
        ]

        for pattern, ns in namespace_patterns:
            if re.search(pattern, cmd_lower):
                return ns

        # Fallback: check output for error indicators
        if output:
            if re.search(r"(?mi)(Traceback|Error:|FAILED|AssertionError|panic!|fatal:)", output):
                return "error"

        return "shell"

    @staticmethod
    def _smart_truncate(text: str, max_chars: int, max_lines: int) -> str:
        """Intelligent truncation: preserve head + tail for long outputs.

        Unlike naive text[:N], this keeps the first ~80% and last ~20%,
        so critical context (errors at the END of build output) is preserved.
        """
        lines = text.splitlines()

        # Small output → no truncation
        if len(lines) <= max_lines and len(text) <= max_chars:
            return text

        if len(lines) > max_lines:
            head_lines = int(max_lines * 0.7)
            tail_lines = int(max_lines * 0.3)

            # Keep head + tail, skip middle
            if head_lines + tail_lines < len(lines):
                kept = lines[:head_lines] + [
                    f"\n[... {len(lines) - head_lines - tail_lines} lines truncated by TerminalCompressor ...]\n"
                ] + lines[-tail_lines:]
                text = "\n".join(kept)
            else:
                text = "\n".join(lines[:max_lines])

        if len(text) > max_chars:
            # Head-tail truncation for characters too
            head_chars = int(max_chars * 0.8)
            if head_chars < len(text):
                tail = text[-int(max_chars * 0.2):]
                text = text[:head_chars] + f"\n[... {len(text) - max_chars} chars truncated ...]\n" + tail

        return text[:max_chars]

    # ── Rule proposal (for self-evolution) ──────────────────────

    def propose_rule(self, output: str, command: str = "",
                     namespace: str = "") -> CompressionRule | None:
        """Analyze uncompressed output and propose a new compression rule.

        Called by self_evolving_rules when an output was too large and
        no existing rule matched. Uses heuristics to generate rule candidates.

        Returns a proposed rule (not yet added to pool) or None.
        """
        if not output or len(output) < 500:
            return None

        ns = namespace or self._detect_namespace(command, output)
        lines = output.splitlines()
        line_count = len(lines)
        char_count = len(output)

        import hashlib, uuid

        # Heuristic 1: Very long output with repetitive patterns
        # → propose truncation rule
        if line_count > 100:
            # Find a distinctive header line for the match_pattern
            sample = lines[0] if lines else ""
            sample = re.sub(r'[^\w\s\-\[\]\(\)\.:,/]', '', sample)[:80]

            rule_id = hashlib.md5(f"{ns}-truncate-{uuid.uuid4().hex[:6]}".encode()).hexdigest()[:12]
            return CompressionRule(
                id=rule_id,
                name=f"auto-{ns}-truncate",
                namespace=ns,
                priority=60,
                action=RuleAction.TRUNCATE_TAIL,
                match_pattern=re.escape(sample),
                match_context=re.escape(command[:100]),
                truncate_lines=50,
                truncate_chars=3000,
                auto_generated=True,
                origin_task="auto-propose",
            )

        # Heuristic 2: Output matches known repetitive patterns
        # → propose removal or extraction rule
        removal_patterns: list[tuple[str, str, str | None]] = [
            (r"(?i)warning", "remove", r"(?i)^.*[Ww]arning.*$"),
            (r"(?m)^\s*$", "remove", r"(?m)^\s*$"),
            (r"(?m)^\d{1,3}%", "replace", r"(\d{1,3}%).*"),
        ]

        for detect, action_name, rule_pattern in removal_patterns:
            if detect and not re.search(detect, output):
                continue
            if not rule_pattern:
                continue
                rule_id = hashlib.md5(f"{ns}-{action_name}-{uuid.uuid4().hex[:6]}".encode()).hexdigest()[:12]
                action = RuleAction(action_name)
                rule = CompressionRule(
                    id=rule_id,
                    name=f"auto-{ns}-{action_name}",
                    namespace=ns,
                    priority=55,
                    action=action,
                    match_pattern=detect,
                )
                if action == RuleAction.REMOVE:
                    rule.match_pattern = rule_pattern
                elif action == RuleAction.REPLACE:
                    rule.replace_pattern = rule_pattern
                    rule.replace_with = r"\1"
                rule.auto_generated = True
                rule.origin_task = "auto-propose"
                return rule

        return None

    # ── Statistics ──────────────────────────────────────────────

    def get_snapshot(self) -> dict[str, Any]:
        return {
            "stats": {
                "calls": self.stats.total_calls,
                "input_chars": self.stats.total_input_chars,
                "output_chars": self.stats.total_output_chars,
                "compression_ratio": self.stats.compression_ratio,
                "avg_saving_pct": self.stats.avg_saving_pct,
                "rules_applied": self.stats.rules_applied,
                "fallbacks": self.stats.fallback_truncations,
            },
            "pool_stats": self._pool.stats(),
            "config": {
                "max_chars": self.max_chars,
                "max_lines": self.max_lines,
            },
        }


# ── Singleton ────────────────────────────────────────────────────────

_terminal_compressor: TerminalCompressor | None = None


def get_terminal_compressor(**kwargs) -> TerminalCompressor:
    """Get or create the singleton TerminalCompressor."""
    global _terminal_compressor
    if _terminal_compressor is None:
        _terminal_compressor = TerminalCompressor(**kwargs)
    return _terminal_compressor


def reset_terminal_compressor() -> None:
    """Test helper: reset the singleton."""
    global _terminal_compressor
    _terminal_compressor = None
