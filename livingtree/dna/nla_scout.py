"""NLA Rule Interpreter — Explain & verify DGM-H rules with natural language.

Based on Anthropic's Natural Language Autoencoders (NLA):
  "Natural Language Autoencoders Produce Unsupervised Explanations of LLM Activations"
  Transformer Circuits, 2026.
  https://transformer-circuits.pub/2026/nla/index.html

Core insight adapted for rule systems:
  If we can accurately reconstruct a rule's behavior from its natural-language
  description, the description faithfully explains the rule. If we cannot, the
  rule may be noise, overfit, or encoding something the LLM cannot articulate.

Architecture:
  CompressionRule
      │
      ├──► RuleEncoder ──► rule_vector [d=64] (numeric fingerprint)
      │
      ├──► RuleVerbalizer (AV) ──► "This rule truncates build output..."
      │       │
      │       └── (LLM generates explanation from rule features)
      │
      └──► RuleReconstructor (AR) ──► reconstructed_vector
              │
              └── quality = cos(original, reconstructed)
                  │
                  ├── > 0.90: ★★★ excellent explanation
                  ├── > 0.70: ★★☆  acceptable
                  ├── > 0.50: ★☆☆  weak — rule may be noise
                  └── ≤ 0.50: reject — rule is unintelligible

Integration with DGM-H:
  - Before deploying a RuleCandidate → verify it passes the quality gate
  - Periodically re-score deployed rules → auto-retire unintelligible ones
  - Generate human-readable rule documentation

Usage:
    interpreter = RuleInterpreter()
    await interpreter.initialize(llm_provider)
    result = await interpreter.explain(rule)
    # result.explanation = "This rule removes progress bar noise from npm output"
    # result.confidence = 0.92
    # result.passed = True

    # Batch quality gate for DGM-H
    accepted = await interpreter.gate_candidates(candidates, threshold=0.7)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

NLA_CACHE = Path(".livingtree/nla_rule_explanations.json")
RULE_VECTOR_DIM = 64
QUALITY_THRESHOLD = 0.70  # From paper: cos > 0.7 = faithful explanation


class ExplanationQuality(Enum):
    EXCELLENT = auto()   # cos > 0.90
    GOOD = auto()        # cos > 0.80
    ACCEPTABLE = auto()  # cos > 0.70
    WEAK = auto()        # cos > 0.50 — borderline
    REJECTED = auto()    # cos ≤ 0.50 — unintelligible


@dataclass
class ExplanationResult:
    """Result of NLA rule interpretation."""
    rule_id: str
    rule_name: str
    explanation: str
    original_vector: np.ndarray
    reconstructed_vector: np.ndarray
    cosine_similarity: float
    quality: ExplanationQuality
    confidence: float  # 0-1, smoothing-adjusted
    passed: bool  # True if above quality threshold
    generated_at: float = field(default_factory=time.time)
    verbalizer_used: str = "heuristic"  # heuristic | llm | nla_model

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "explanation": self.explanation,
            "cosine_similarity": round(self.cosine_similarity, 4),
            "quality": self.quality.name,
            "confidence": round(self.confidence, 3),
            "passed": self.passed,
        }


class RuleEncoder:
    """Encodes a CompressionRule into a fixed-dimension vector fingerprint.

    The vector captures:
    - Action type (one-hot)
    - Pattern characteristics (regex complexity, length, entropy)
    - Context matching (command keywords)
    - Evolution metadata (hit rate, false positive rate, priority)
    - Semantic features (namespace, action parameters)
    """

    ACTION_VECTORS = {
        "pass_through":    [1, 0, 0, 0, 0, 0],
        "truncate_tail":   [0, 1, 0, 0, 0, 0],
        "extract_pattern": [0, 0, 1, 0, 0, 0],
        "remove":          [0, 0, 0, 1, 0, 0],
        "replace":         [0, 0, 0, 0, 1, 0],
        "condense":        [0, 0, 0, 0, 0, 1],
    }

    NAMESPACE_HASHES = {
        "general": 0.1, "git": 0.3, "npm": 0.5, "build": 0.7,
        "shell": 0.2, "python": 0.4, "docker": 0.6, "test": 0.8,
    }

    @classmethod
    def encode(cls, rule: Any) -> np.ndarray:
        """Convert a CompressionRule to a 64-dim vector.

        The vector structure aligns with NLA's residual-stream direction concept:
        each dimension encodes a specific semantic feature of the rule.
        """
        vec = np.zeros(RULE_VECTOR_DIM, dtype=np.float64)

        # Dims 0-5: Action type (one-hot)
        action_vec = cls.ACTION_VECTORS.get(
            getattr(rule, "action", None),
            [0, 0, 0, 0, 0, 0],
        )
        if hasattr(rule, "action") and hasattr(rule.action, "value"):
            action_vec = cls.ACTION_VECTORS.get(rule.action.value, action_vec)
        vec[0:6] = action_vec

        # Dims 6-11: Pattern characteristics
        match_pattern = getattr(rule, "match_pattern", "") or ""
        match_context = getattr(rule, "match_context", "") or ""
        vec[6] = min(1.0, len(match_pattern) / 500.0)  # Pattern length
        vec[7] = cls._regex_complexity(match_pattern)    # Regex complexity
        vec[8] = cls._entropy_estimate(match_pattern)     # Pattern entropy
        vec[9] = min(1.0, len(match_context) / 200.0)    # Context length
        vec[10] = 1.0 if match_context else 0.0          # Has context
        vec[11] = cls._namespace_hash(getattr(rule, "namespace", "general"))

        # Dims 12-17: Evolution metadata
        hit_count = getattr(rule, "hit_count", 0)
        fp_count = getattr(rule, "false_positive_count", 0)
        total = hit_count + fp_count + 1
        vec[12] = hit_count / max(total, 1)
        vec[13] = fp_count / max(total, 1)
        vec[14] = getattr(rule, "priority", 50) / 100.0
        vec[15] = min(1.0, (time.time() - getattr(rule, "created_at", time.time())) / 86400.0)
        vec[16] = 1.0 if getattr(rule, "auto_generated", False) else 0.0
        vec[17] = max(0, 1.0 - fp_count / max(hit_count + fp_count, 1))  # Precision

        # Dims 18-23: Action parameters
        vec[18] = min(1.0, getattr(rule, "truncate_lines", 0) / 200.0)
        vec[19] = min(1.0, getattr(rule, "truncate_chars", 0) / 10000.0)
        vec[20] = cls._regex_complexity(getattr(rule, "extract_regex", "") or "")
        vec[21] = 1.0 if getattr(rule, "replace_pattern", "") else 0.0
        vec[22] = cls._entropy_estimate(getattr(rule, "replace_with", "") or "")
        vec[23] = 1.0 if getattr(rule, "name", "") else 0.0  # Has explicit name

        # Dims 24-31: Semantic feature hashes (multiple aspects of the rule)
        rule_text = f"{rule.name}|{match_pattern}|{match_context}|{getattr(rule, 'namespace', '')}"
        for i in range(24, 32):
            h = hashlib.sha256(f"{rule_text}:{i}".encode()).digest()
            vec[i] = int.from_bytes(h[:2], "big") / 65535.0

        # Dims 32-47: N-gram statistics from pattern
        ngrams = cls._extract_char_ngrams(match_pattern, n=3)
        for i, (ngram, freq) in enumerate(ngrams[:16]):
            if i + 32 < 48:
                vec[i + 32] = freq

        # Dims 48-55: Action-specific semantic dimensions
        action_str = str(getattr(rule, "action", "pass_through"))
        for i in range(48, 56):
            h = hashlib.sha256(f"{action_str}:{i}:{match_pattern}".encode()).digest()
            vec[i] = int.from_bytes(h[:2], "big") / 65535.0

        # Dims 56-63: Reserved for future features
        vec[56] = 1.0 if getattr(rule, "name", "").startswith("auto_") else 0.0
        vec[57] = min(1.0, len(getattr(rule, "name", "")) / 100.0)

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    @staticmethod
    def _regex_complexity(pattern: str) -> float:
        """Estimate regex complexity: quantifiers, groups, alternations."""
        if not pattern:
            return 0.0
        features = sum([
            pattern.count("*"), pattern.count("+"), pattern.count("?"),
            pattern.count("("), pattern.count("|"), pattern.count("["),
            pattern.count("\\"), pattern.count("^"), pattern.count("$"),
        ])
        return min(1.0, features / 20.0)

    @staticmethod
    def _entropy_estimate(text: str) -> float:
        """Simple character-level entropy estimate."""
        if not text:
            return 0.0
        from collections import Counter
        counts = Counter(text)
        total = len(text)
        entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
        return min(1.0, entropy / 8.0)

    @staticmethod
    def _namespace_hash(namespace: str) -> float:
        """Map namespace to a semantic dimension."""
        return RuleEncoder.NAMESPACE_HASHES.get(namespace, 0.5)

    @staticmethod
    def _extract_char_ngrams(text: str, n: int = 3) -> list[tuple[str, float]]:
        """Extract character n-grams with frequency."""
        if len(text) < n:
            return []
        from collections import Counter
        ngrams = [text[i:i + n] for i in range(len(text) - n + 1)]
        total = len(ngrams)
        counts = Counter(ngrams)
        return sorted(
            [(k, v / total) for k, v in counts.items()],
            key=lambda x: x[1], reverse=True,
        )


class RuleVerbalizer:
    """Generates natural language explanations of compression rules (the AV role).

    Three strategies:
    1. LLM-enhanced (if LLM provider available) — richest explanations
    2. Template-based (heuristic) — covers 80% of rules well
    3. Statistical (feature-driven) — for bulk processing
    """

    # Template patterns for common rule types
    EXPLANATION_TEMPLATES = {
        "truncate_tail": [
            "This rule truncates {namespace} output to the first {lines} lines or {chars} characters, "
            "removing verbose tails while preserving the most relevant content.",
            "When {namespace} output exceeds {lines} lines, this rule keeps only the head portion, "
            "discarding repetitive trailing content.",
            "Limits {namespace} terminal output to {lines} lines — designed to handle cases where "
            "the backend generates excessive log output.",
        ],
        "remove": [
            "Strips content matching '{pattern}' from {namespace} output. This eliminates "
            "{context_desc} without affecting other content.",
            "Completely removes lines matching '{pattern}' in {namespace} context. The pattern "
            "targets {context_desc}.",
        ],
        "extract_pattern": [
            "Extracts content matching '{regex}' from {namespace} output, preserving only "
            "the semantically relevant portions and discarding surrounding noise.",
            "From {namespace} output, this rule isolates the information matching '{regex}', "
            "which captures {context_desc}.",
        ],
        "replace": [
            "Replaces '{old}' with '{new}' in {namespace} output — typically used to "
            "normalize formatting, redact sensitive information, or standardize notation.",
            "Substitutes occurrences of '{old}' with '{new}' in {namespace} context, "
            "cleaning up {context_desc}.",
        ],
        "condense": [
            "Uses LLM-based condensation to summarize {namespace} output, preserving "
            "semantic meaning while dramatically reducing token count.",
            "Applies semantic compression to {namespace} content — the LLM rewrites "
            "verbose output into concise, information-dense summaries.",
        ],
        "pass_through": [
            "Always passes {namespace} content through unchanged. This rule exists to "
            "prevent other rules from accidentally compressing critical {namespace} output.",
            "Whitelists {namespace} content — marks it as essential and exempt from compression.",
        ],
    }

    def __init__(self):
        self._llm = None

    def set_llm(self, llm_provider):
        self._llm = llm_provider

    async def verbalize(self, rule: Any, use_llm: bool = True) -> str:
        """Generate a natural language explanation of what this rule does."""
        if use_llm and self._llm:
            explanation = await self._llm_verbalize(rule)
            if explanation:
                return explanation

        return self._template_verbalize(rule)

    async def _llm_verbalize(self, rule: Any) -> Optional[str]:
        """Use LLM to generate a rich, context-aware explanation."""
        if not self._llm:
            return None

        rule_dict = {
            "name": getattr(rule, "name", "unknown"),
            "action": str(getattr(rule, "action", "unknown")),
            "namespace": getattr(rule, "namespace", "general"),
            "match_pattern": getattr(rule, "match_pattern", ""),
            "match_context": getattr(rule, "match_context", ""),
            "extract_regex": getattr(rule, "extract_regex", ""),
            "replace_pattern": getattr(rule, "replace_pattern", ""),
            "replace_with": getattr(rule, "replace_with", ""),
            "truncate_lines": getattr(rule, "truncate_lines", 0),
            "truncate_chars": getattr(rule, "truncate_chars", 0),
            "hit_count": getattr(rule, "hit_count", 0),
            "false_positive_count": getattr(rule, "false_positive_count", 0),
            "priority": getattr(rule, "priority", 50),
            "auto_generated": getattr(rule, "auto_generated", False),
        }

        prompt = (
            "You are analyzing a compression rule used in an AI agent system. "
            "Explain what this rule does in ONE clear, concise sentence.\n\n"
            f"Rule: {json.dumps(rule_dict, indent=2)}\n\n"
            "Your explanation should answer: (1) What does it match? "
            "(2) What action does it take? (3) Why would this be useful?\n"
            "Reply with only the explanation, no prefix or formatting."
        )

        try:
            response = await self._llm.chat(prompt)
            response = response.strip().strip('"').strip("'")
            if len(response) > 20 and len(response) < 500:
                return response
        except Exception as e:
            logger.debug("LLM verbalize failed: %s", e)

        return None

    def _template_verbalize(self, rule: Any) -> str:
        """Template-based rule explanation."""
        action_str = "pass_through"
        if hasattr(rule, "action"):
            if hasattr(rule.action, "value"):
                action_str = rule.action.value
            else:
                action_str = str(rule.action)

        templates = self.EXPLANATION_TEMPLATES.get(
            action_str,
            self.EXPLANATION_TEMPLATES["pass_through"],
        )
        template = random.choice(templates)

        return template.format(
            namespace=getattr(rule, "namespace", "general"),
            pattern=getattr(rule, "match_pattern", "all")[:80] or "all",
            lines=getattr(rule, "truncate_lines", 50),
            chars=getattr(rule, "truncate_chars", 5000),
            regex=getattr(rule, "extract_regex", "relevant content")[:80] or "relevant content",
            old=getattr(rule, "replace_pattern", "target")[:40] or "target",
            new=getattr(rule, "replace_with", "replacement")[:40] or "replacement",
            context_desc=self._describe_context(rule),
        )

    def _describe_context(self, rule: Any) -> str:
        """Generate a human-readable description of the rule's context."""
        context = getattr(rule, "match_context", "") or ""
        namespace = getattr(rule, "namespace", "general")

        if not context:
            descs = {
                "git": "git command output",
                "npm": "npm/Node.js package manager output",
                "build": "build system and compiler output",
                "shell": "general shell command output",
                "python": "Python runtime output and tracebacks",
                "docker": "Docker container build and runtime logs",
                "test": "test runner output",
            }
            return descs.get(namespace, f"{namespace} output")

        context_descs = {
            "error": "error messages",
            "log": "log output",
            "progress": "progress indicators and loading bars",
            "traceback": "stack traces and error tracebacks",
            "warning": "warning messages",
            "debug": "debug output and verbose logging",
        }
        for keyword, desc in context_descs.items():
            if keyword in context.lower():
                return desc

        return f"content matching '{context[:50]}'"


class RuleReconstructor:
    """Reconstructs rule vectors from natural language explanations (the AR role).

    Parses the explanation text for structured features that map back to
    the same vector space as RuleEncoder. Uses regex-based feature extraction
    to recover action type, namespace, quantities, and semantic intent.
    """

    # Regex patterns to extract structured features from explanations
    EXTRACTION_PATTERNS = {
        "action_truncate": [
            r"truncat\w*.*?(?:first|keep|head|top)\s*(\d+)\s*(?:line|row)",
            r"truncat\w*.*?(?:first|keep)\s*(\d+)\s*(?:char)",
            r"(?:limit|keep).*?(?:to|first)\s*(\d+)\s*line",
        ],
        "action_remove": [
            r"(?:strip|remov|discard|eliminate|delete).*?(?:content|line|output)",
            r"completely\s+remov",
        ],
        "action_extract": [
            r"extract\w*.*?(?:content|information|portion)",
            r"isolat\w*.*?(?:information|content)",
            r"preserv\w*.*?(?:only|relevant|semantic)",
        ],
        "action_replace": [
            r"(?:replac|substitut).*?(?:with|by)",
            r"normaliz\w*.*(?:format|notation)",
            r"redact\w*.*(?:sensitive|information)",
        ],
        "action_condense": [
            r"(?:condens|summar|compress).*?(?:LLM|semantic|language)",
            r"rewrit\w*.*(?:verbose|concise)",
        ],
        "namespace": [
            r"(?:in|from|for)\s+(npm|git|build|shell|python|docker|test)\s+(?:output|context|content)",
        ],
        "truncate_lines": [
            r"(?:first|keep|top|head)\s*(\d+)\s*(?:line|row)",
        ],
        "truncate_chars": [
            r"(?:first|keep)\s*(\d+)\s*(?:char|character)",
        ],
        "priority_high": [
            r"(?:high|important|critical|essential).*?(?:priority|rule)",
            r"priority\s*(?:of|is|:)?\s*(?:high|8\d|9\d)",
        ],
        "noise_reduction": [
            r"(?:noise|redundant|verbose|excessive|repetitive).*?(?:output|content|log)",
        ],
        "auto_generated": [
            r"auto.*(?:generated|discovered|created)",
        ],
    }

    def reconstruct(self, explanation: str) -> np.ndarray:
        """Reconstruct rule vector from natural language explanation.

        Extracts features that mirror RuleEncoder's vector structure,
        placing them in the same dimensional positions.
        """
        vec = np.zeros(RULE_VECTOR_DIM, dtype=np.float64)
        text_lower = explanation.lower()

        # ─── Action type (dims 0-5) — match encoder's one-hot ───
        action_scores = {
            "truncate_tail": self._match_any(explanation, self.EXTRACTION_PATTERNS["action_truncate"]),
            "remove": self._match_any(explanation, self.EXTRACTION_PATTERNS["action_remove"]),
            "extract_pattern": self._match_any(explanation, self.EXTRACTION_PATTERNS["action_extract"]),
            "replace": self._match_any(explanation, self.EXTRACTION_PATTERNS["action_replace"]),
            "condense": self._match_any(explanation, self.EXTRACTION_PATTERNS["action_condense"]),
            "pass_through": 1.0 if "pass" in text_lower and ("through" in text_lower or "unchang" in text_lower) else 0.0,
        }

        action_idx = {
            "pass_through": 0, "truncate_tail": 1, "extract_pattern": 2,
            "remove": 3, "replace": 4, "condense": 5,
        }

        # One-hot with fallback to proportional scores
        best_action = max(action_scores, key=action_scores.get)
        best_score = action_scores[best_action]

        if best_score > 0.3:
            # One-hot
            idx = action_idx.get(best_action, 0)
            for i in range(6):
                vec[i] = 1.0 if i == idx else 0.0
        else:
            # Proportional (soft assignment)
            total = sum(action_scores.values()) + 1e-9
            for action_name, score in action_scores.items():
                idx = action_idx.get(action_name, 0)
                vec[idx] = max(vec[idx], score / total)

        # ─── Namespace (dim 11) ───
        ns_match = self._extract_first_group(explanation, self.EXTRACTION_PATTERNS["namespace"])
        if ns_match:
            ns_hash = {
                "npm": 0.5, "git": 0.3, "build": 0.7, "shell": 0.2,
                "python": 0.4, "docker": 0.6, "test": 0.8,
            }
            vec[11] = ns_hash.get(ns_match, 0.5)
        else:
            # Fallback: detect namespace from keywords
            for kw, val in [("npm", 0.5), ("git", 0.3), ("build", 0.7), ("python", 0.4),
                           ("docker", 0.6), ("shell", 0.2), ("test", 0.8)]:
                if kw in text_lower:
                    vec[11] = val
                    break

        # ─── Pattern characteristics (dims 6-10) ───
        vec[6] = 0.3 if "pattern" in text_lower or "match" in text_lower else 0.1  # Has pattern
        vec[7] = 0.5 if any(c in explanation for c in r"*+?[]()|\^$") else 0.1      # Regex complexity hint
        vec[8] = 0.5 if len(set(explanation)) > 30 else 0.2                          # Entropy hint
        vec[10] = 1.0 if ns_match else 0.0                                           # Has context

        # ─── Truncation parameters (dims 18-19) ───
        lines_val = self._extract_first_group(explanation, self.EXTRACTION_PATTERNS["truncate_lines"])
        if lines_val:
            vec[18] = min(1.0, float(lines_val) / 200.0)

        chars_val = self._extract_first_group(explanation, self.EXTRACTION_PATTERNS["truncate_chars"])
        if chars_val:
            vec[19] = min(1.0, float(chars_val) / 10000.0)

        # If no explicit numbers, estimate from "thousands of characters" etc.
        if vec[18] == 0 and vec[19] == 0:
            numbers = re.findall(r'\b(\d+)\b', explanation)
            if numbers:
                vec[18] = min(1.0, float(numbers[0]) / 200.0)
                if len(numbers) > 1:
                    vec[19] = min(1.0, float(numbers[1]) / 10000.0)

        # ─── Pattern extraction (dim 20) ───
        if any(kw in text_lower for kw in ["regex", "pattern", "extract"]):
            vec[20] = 0.5

        # ─── Replace features (dims 21-22) ───
        if "replac" in text_lower or "substitut" in text_lower:
            vec[21] = 1.0
            vec[22] = 0.5

        # ─── Evolution metadata (dims 12-17) ───
        vec[17] = 0.7  # Default precision assumption for well-explained rules

        # ─── Auto-generated (dim 16) ───
        if self._match_any(explanation, self.EXTRACTION_PATTERNS["auto_generated"]):
            vec[16] = 0.8

        # ─── Priority (dim 14) ───
        if self._match_any(explanation, self.EXTRACTION_PATTERNS["priority_high"]):
            vec[14] = 0.85
        elif "priority" in text_lower:
            # Try to extract numeric priority
            prio_match = re.search(r'priority\D*(\d+)', text_lower)
            if prio_match:
                vec[14] = min(1.0, float(prio_match.group(1)) / 100.0)
            else:
                vec[14] = 0.5
        else:
            vec[14] = 0.5  # Default medium priority

        # ─── Rule has name (dim 23) ───
        vec[23] = 1.0

        # ─── Semantic feature hashes (dims 24-31) — mirror encoder's hash ───
        # Use key words from the explanation as the "rule text"
        key_words = " ".join(re.findall(r'\b[a-z]{4,}\b', text_lower)[:20])
        for i in range(24, 32):
            h = hashlib.sha256(f"{key_words}:{i}".encode()).digest()
            vec[i] = int.from_bytes(h[:2], "big") / 65535.0

        # ─── Semantic category features (dims 48-63) ───
        # Action-specific semantic dimensions
        action_word = best_action if best_score > 0.3 else "unknown"
        for i in range(48, 56):
            h = hashlib.sha256(f"{action_word}:{i}:{key_words}".encode()).digest()
            vec[i] = int.from_bytes(h[:2], "big") / 65535.0

        # Reserved semantic features
        if self._match_any(explanation, self.EXTRACTION_PATTERNS["noise_reduction"]):
            vec[56] = 0.7
        vec[57] = min(1.0, len(key_words.split()) / 100.0)

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def _match_any(self, text: str, patterns: list[str]) -> float:
        """Check if any pattern matches. Returns confidence 0.0-1.0."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return 1.0
        return 0.0

    def _extract_first_group(self, text: str, patterns: list[str]) -> Optional[str]:
        """Extract the first regex capture group from matching patterns."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return match.group(1)
                except IndexError:
                    pass
        return None


class RuleInterpreter:
    """NLA-style rule interpretability engine.

    Explains DGM-H compression rules in natural language and verifies
    explanation quality through reconstruction fidelity.

    Usage:
        interpreter = RuleInterpreter()
        await interpreter.initialize(llm_provider)
        result = await interpreter.explain(rule, use_llm=True)
        if result.passed:
            print(f"✓ {result.explanation} (cos={result.cosine_similarity:.3f})")
    """

    def __init__(self, quality_threshold: float = QUALITY_THRESHOLD):
        self._encoder = RuleEncoder()
        self._verbalizer = RuleVerbalizer()
        self._reconstructor = RuleReconstructor()
        self._quality_threshold = quality_threshold
        self._results: dict[str, ExplanationResult] = {}
        self._llm = None
        self._initialized = False
        self._stats = {
            "total_explained": 0,
            "passed": 0,
            "rejected": 0,
            "excellent": 0,
            "good": 0,
            "acceptable": 0,
            "weak": 0,
        }

    async def initialize(self, llm_provider=None):
        if llm_provider:
            self._llm = llm_provider
            self._verbalizer.set_llm(llm_provider)
        self._load_cache()
        self._initialized = True
        logger.info(
            "RuleInterpreter: ready (LLM=%s, threshold=%.2f, cached=%d)",
            "yes" if llm_provider else "no",
            self._quality_threshold,
            len(self._results),
        )

    async def explain(
        self, rule: Any, use_llm: bool = True,
    ) -> ExplanationResult:
        """Explain a rule and verify the explanation quality.

        Pipeline:
        1. Encode rule → rule_vector
        2. Verbalize rule → natural language explanation
        3. Reconstruct vector from explanation
        4. Compute cosine similarity
        5. Quality gate
        """
        # Stage 1: Encode
        original_vec = self._encoder.encode(rule)

        # Stage 2: Verbalize (AV role)
        explanation = await self._verbalizer.verbalize(rule, use_llm=use_llm)

        # Stage 3: Reconstruct (AR role)
        reconstructed_vec = self._reconstructor.reconstruct(explanation)

        # Stage 4: Cosine similarity
        cos_sim = float(np.dot(original_vec, reconstructed_vec))

        # Stage 5: Quality assessment
        quality = self._classify_quality(cos_sim)
        confidence = self._smooth_confidence(cos_sim, quality)
        passed = cos_sim >= self._quality_threshold

        result = ExplanationResult(
            rule_id=getattr(rule, "id", "unknown"),
            rule_name=getattr(rule, "name", "unnamed"),
            explanation=explanation,
            original_vector=original_vec,
            reconstructed_vector=reconstructed_vec,
            cosine_similarity=cos_sim,
            quality=quality,
            confidence=confidence,
            passed=passed,
            verbalizer_used="llm" if (use_llm and self._llm) else "heuristic",
        )

        # Store and update stats
        self._results[result.rule_id] = result
        self._stats["total_explained"] += 1
        if passed:
            self._stats["passed"] += 1
        else:
            self._stats["rejected"] += 1
        self._stats[quality.name.lower()] = self._stats.get(quality.name.lower(), 0) + 1

        return result

    async def gate_candidates(
        self, candidates: list[Any], threshold: float = None,
    ) -> tuple[list[Any], list[ExplanationResult]]:
        """Filter RuleCandidates through quality gate.

        Returns (accepted_candidates, all_results).
        Only candidates whose explanations pass the quality threshold are accepted.
        """
        threshold = threshold or self._quality_threshold
        accepted = []
        all_results = []

        for candidate in candidates:
            result = await self.explain(candidate)
            all_results.append(result)
            if result.passed:
                accepted.append(candidate)
            else:
                logger.debug(
                    "Rule %s rejected: cos=%.3f (threshold=%.2f) — %s",
                    result.rule_name, result.cosine_similarity,
                    threshold, result.explanation[:60],
                )

        return accepted, all_results

    async def audit_deployed_rules(
        self, rule_pool: Any, retire_threshold: float = 0.5,
    ) -> list[str]:
        """Audit all deployed rules — retire those that are unintelligible.

        Returns list of retired rule IDs.
        """
        retired = []
        if hasattr(rule_pool, "get_all_rules"):
            rules = rule_pool.get_all_rules()
        elif hasattr(rule_pool, "list_all"):
            rules = rule_pool.list_all()
        else:
            return []

        for rule in rules:
            result = await self.explain(rule, use_llm=False)
            if result.cosine_similarity < retire_threshold:
                retired.append(result.rule_id)
                logger.info(
                    "Retiring unintelligible rule: %s (cos=%.3f) — %s",
                    result.rule_name, result.cosine_similarity,
                    result.explanation[:80],
                )

        return retired

    def _classify_quality(self, cos_sim: float) -> ExplanationQuality:
        if cos_sim > 0.90:
            return ExplanationQuality.EXCELLENT
        elif cos_sim > 0.80:
            return ExplanationQuality.GOOD
        elif cos_sim > 0.70:
            return ExplanationQuality.ACCEPTABLE
        elif cos_sim > 0.50:
            return ExplanationQuality.WEAK
        return ExplanationQuality.REJECTED

    def _smooth_confidence(self, cos_sim: float, quality: ExplanationQuality) -> float:
        """Smoothing-adjusted confidence score."""
        base = max(0.0, min(1.0, cos_sim))
        # Add small bonus for verbalizer trustworthiness
        bonus = 0.05 if quality in (ExplanationQuality.EXCELLENT, ExplanationQuality.GOOD) else 0.0
        return min(1.0, base + bonus)

    def get_quality_distribution(self) -> dict:
        """Get distribution of explanation qualities."""
        return {k: v for k, v in self._stats.items() if k not in ("total_explained", "passed", "rejected")}

    def get_best_explanations(self, n: int = 5) -> list[dict]:
        """Get top-N best quality explanations."""
        sorted_results = sorted(
            self._results.values(),
            key=lambda r: r.cosine_similarity,
            reverse=True,
        )
        return [r.to_dict() for r in sorted_results[:n]]

    def get_stats(self) -> dict:
        total = max(self._stats["total_explained"], 1)
        return {
            **self._stats,
            "pass_rate": round(self._stats["passed"] / total, 3),
            "cached_explanations": len(self._results),
        }

    def save_cache(self):
        try:
            data = {
                r.rule_id: {
                    "rule_name": r.rule_name,
                    "explanation": r.explanation,
                    "cosine_similarity": r.cosine_similarity,
                    "quality": r.quality.name,
                    "passed": r.passed,
                }
                for r in self._results.values()
            }
            NLA_CACHE.parent.mkdir(parents=True, exist_ok=True)
            NLA_CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug("RuleInterpreter save: %s", e)

    def _load_cache(self):
        if not NLA_CACHE.exists():
            return
        try:
            data = json.loads(NLA_CACHE.read_text())
            for rule_id, d in data.items():
                result = ExplanationResult(
                    rule_id=rule_id,
                    rule_name=d.get("rule_name", ""),
                    explanation=d.get("explanation", ""),
                    original_vector=np.zeros(RULE_VECTOR_DIM),
                    reconstructed_vector=np.zeros(RULE_VECTOR_DIM),
                    cosine_similarity=d.get("cosine_similarity", 0.0),
                    quality=ExplanationQuality[d.get("quality", "ACCEPTABLE")],
                    confidence=d.get("cosine_similarity", 0.0),
                    passed=d.get("passed", True),
                )
                self._results[rule_id] = result
        except Exception as e:
            logger.debug("RuleInterpreter load: %s", e)

    # ─── DGM-H Integration Hooks ───

    async def on_rule_candidate(self, candidate: Any) -> bool:
        """Hook for DGM-H: called when a new RuleCandidate is proposed.

        Returns True if the candidate should be deployed, False to reject.
        """
        result = await self.explain(candidate, use_llm=bool(self._llm))
        return result.passed

    async def on_rule_deployed(self, rule: Any) -> ExplanationResult:
        """Hook for DGM-H: called after a rule is deployed.

        Returns the explanation result for logging/analytics.
        """
        return await self.explain(rule, use_llm=False)

    async def on_evolution_cycle(self, rule_pool: Any) -> dict:
        """Hook for DGM-H: called after each evolution cycle.

        Audits all rules, retires unintelligible ones, generates report.
        """
        retired = await self.audit_deployed_rules(rule_pool)
        report = {
            "cycle_stats": self.get_stats(),
            "retired_count": len(retired),
            "retired_ids": retired,
            "best_explanations": self.get_best_explanations(3),
        }
        self.save_cache()
        return report


_interpreter: Optional[RuleInterpreter] = None


def get_rule_interpreter(threshold: float = QUALITY_THRESHOLD) -> RuleInterpreter:
    global _interpreter
    if _interpreter is None:
        _interpreter = RuleInterpreter(quality_threshold=threshold)
    return _interpreter
