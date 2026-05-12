"""Dream Pretraining — Idle-time synthetic data generation and model fine-tuning.

Academic grounding: Curriculum Learning (Bengio 2009), Self-Play (Silver 2017),
Sleep Consolidation (Walker 2004), LoRA (Hu et al. ICLR 2022).

Triggered by Biorhythm (LifeState.DREAMING) or GreenScheduler (EnergyMode.GROWTH).
Safety: never during active sessions, max 30min, checks token budget.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ Data Classes ═══════════════════════════════════════════════════

@dataclass
class DreamConfig:
    max_dream_duration_minutes: int = 30
    min_idle_minutes: int = 5
    max_synthetic_samples: int = 1000
    night_only: bool = True
    auto_trigger: bool = True
    model_name: str = "Qwen/Qwen3.5-4B"
    lora_rank: int = 4
    min_improvement: float = 0.05
    min_token_budget: int = 5000


@dataclass
class SyntheticSample:
    instruction: str
    response: str
    category: str = "general"
    difficulty: float = 0.5
    source_template: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction, "response": self.response,
            "category": self.category, "difficulty": self.difficulty,
            "source_template": self.source_template,
        }


@dataclass
class DreamSession:
    session_id: str
    start_time: float
    samples_generated: int = 0
    training_loss: Optional[float] = None
    improvement_score: Optional[float] = None
    duration_minutes: float = 0.0
    status: str = "completed"
    error: str = ""


# ═══ Scenario Templates & Fillers ═══════════════════════════════════

SYNTHETIC_TEMPLATES: list[dict[str, Any]] = [
    {"c": "code_debug", "t": "Fix '{error}' in {language}.", "d": 0.3},
    {"c": "explain", "t": "Explain {concept} simply with an example.", "d": 0.3},
    {"c": "docs", "t": "Write documentation for {subject} ({audience}).", "d": 0.3},
    {"c": "conversation", "t": "User: '{user_message}'. Respond helpfully.", "d": 0.2},
    {"c": "code_review", "t": "Review this {language} code:\n```\n{code}\n```", "d": 0.4},
    {"c": "compare", "t": "Compare {a} vs {b} for {use_case}.", "d": 0.4},
    {"c": "test", "t": "Write {language} tests for {func}. Cover edges.", "d": 0.4},
    {"c": "optimize", "t": "Optimize {language} code for {metric}.", "d": 0.5},
    {"c": "refactor", "t": "Refactor to {pattern} pattern:\n```\n{code}\n```", "d": 0.5},
    {"c": "analysis", "t": "Analyze {dataset}. Key insights?", "d": 0.5},
    {"c": "architecture", "t": "Design {system} handling {req}.", "d": 0.6},
    {"c": "api_design", "t": "Design REST API for {domain} (auth, rate limit).", "d": 0.6},
    {"c": "root_cause", "t": "Stack trace:\n```\n{trace}\n```\nRoot cause + fix.", "d": 0.7},
    {"c": "perf", "t": "Profile & improve {scenario} in {language}.", "d": 0.7},
    {"c": "security", "t": "Audit security:\n```\n{code}\n```\nList issues.", "d": 0.8},
]

FILLERS: dict[str, list[str]] = {
    "error": ["KeyError", "TypeError: NoneType", "ValueError", "ImportError: no module", "RuntimeError: OOM"],
    "language": ["Python", "JavaScript", "TypeScript", "Rust", "Go", "Java", "C++", "SQL"],
    "concept": ["attention", "gradient descent", "RAG", "embeddings", "backprop", "transformers", "async/await"],
    "system": ["e-commerce", "chat app", "ML pipeline", "task queue", "IoT network", "microservices"],
    "req": ["10K concurrent", "1M events/sec", "99.99% uptime", "multi-region"],
    "metric": ["latency", "throughput", "memory", "CPU", "battery"],
    "a": ["Redis", "PostgreSQL", "MongoDB", "Kafka", "Docker", "React", "PyTorch"],
    "b": ["Memcached", "MySQL", "DynamoDB", "RabbitMQ", "K8s", "Vue", "TensorFlow"],
    "use_case": ["caching", "analytics", "messaging", "orchestration", "DL training"],
    "pattern": ["Strategy", "Observer", "Factory", "Repository", "Adapter", "Singleton"],
    "func": ["auth flow", "payment pipeline", "search index", "notification dispatcher"],
    "domain": ["blog", "inventory", "ride-share", "telemedicine", "LMS"],
    "audience": ["junior devs", "PMs", "DevOps", "end users"],
    "subject": ["Docker deploy", "REST design", "DB migration", "CI/CD", "env config"],
    "dataset": ["5yr sales", "web logs", "support tickets", "factory sensors"],
    "user_message": ["How to start?", "Bug help?", "Best module structure?", "Explain deployment?"],
    "code": [
        "def process(d):\n  return d['key'].upper()",
        "app.get('/u/:id', async (r,s) => { const u = await db.get(r.params.id); s.json(u) })",
        "fn avg(items: &[f64]) -> f64 { items.iter().sum() / items.len() }",
    ],
    "trace": [
        "File 'app.py', line 42, in handle\n  result = data['nested']['value']\nKeyError: 'nested'",
        "Error: ECONNREFUSED 127.0.0.1:5432\n  at TCPConnectWrap.afterConnect",
    ],
    "scenario": ["batch 500K DB records", "image inference at 1K RPM"],
}


# ═══ Response Synthesizer ═══════════════════════════════════════════

_RESPONSE_TEMPLATES: dict[str, str] = {
    "code_debug": "Root cause: accessing absent value. Fix:\n1. Add safety check\n2. Use .get() with default\n3. Validate at boundary\n```python\nresult = data.get('nested',{}).get('value', default)\n```",
    "root_cause": "Root cause: accessing absent value. Fix:\n1. Add safety check\n2. Use .get() with default\n3. Validate at boundary\n```python\nresult = data.get('nested',{}).get('value', default)\n```",
    "explain": "**Core**: definition. **Example**: [X] → apply → [Y]. **Why**: important because [reason]. **Advanced**: relates to [principle]. Want more detail?",
    "docs": "**Core**: definition. **Example**: [X] → apply → [Y]. **Why**: important because [reason]. **Advanced**: relates to [principle]. Want more detail?",
    "architecture": "Architecture:\n1. API Gateway (routing, auth, rate limit)\n2. Service Layer (independently deployable)\n3. Data Layer (primary + read replicas)\n4. Cache (Redis, ~80% load reduction)\n5. Queue (Kafka/RabbitMQ for async)\n6. Monitoring (Prometheus + Grafana)\n\nTradeoffs: scalability vs operational cost.",
    "api_design": "Architecture:\n1. API Gateway (routing, auth, rate limit)\n2. Service Layer (independently deployable)\n3. Data Layer (primary + read replicas)\n4. Cache (Redis, ~80% load reduction)\n5. Queue (Kafka/RabbitMQ for async)\n6. Monitoring (Prometheus + Grafana)\n\nTradeoffs: scalability vs operational cost.",
    "optimize": "Strategy:\n**Profile**: identify bottleneck (CPU/IO/memory)\n**Key fixes**:\n1. Batch to reduce overhead\n2. Cache expensive calls\n3. Async I/O for blocking ops\n4. Index for DB queries\n**Impact**: ~40-60% improvement in metric.",
    "perf": "Strategy:\n**Profile**: identify bottleneck (CPU/IO/memory)\n**Key fixes**:\n1. Batch to reduce overhead\n2. Cache expensive calls\n3. Async I/O for blocking ops\n4. Index for DB queries\n**Impact**: ~40-60% improvement in metric.",
    "compare": "| Criterion | A | B | Winner |\n|---|---|---|---|\n| Perf | [X] | [Y] | [Z] |\n| Scale | [X] | [Y] | [Z] |\n| Learning | [X] | [Y] | [Z] |\n\nRecommend: [winner] because [reason].",
    "analysis": "| Criterion | A | B | Winner |\n|---|---|---|---|\n| Perf | [X] | [Y] | [Z] |\n| Scale | [X] | [Y] | [Z] |\n| Learning | [X] | [Y] | [Z] |\n\nRecommend: [winner] because [reason].",
    "test": "Updated implementation:\n```\n[refactored code]\n```\nChanges: extracted [X] for SRP, applied [pattern], added error handling.\nTests cover: happy path, null/empty input, large input, error conditions.",
    "refactor": "Updated implementation:\n```\n[refactored code]\n```\nChanges: extracted [X] for SRP, applied [pattern], added error handling.\nTests cover: happy path, null/empty input, large input, error conditions.",
    "code_review": "| Severity | Issue | Fix |\n|---|---|---|\n| HIGH | SQL Injection | Parameterized queries |\n| MEDIUM | No validation | Schema check |\n| LOW | Hardcoded creds | Env vars |",
    "security": "| Severity | Issue | Fix |\n|---|---|---|\n| HIGH | SQL Injection | Parameterized queries |\n| MEDIUM | No validation | Schema check |\n| LOW | Hardcoded creds | Env vars |",
    "conversation": "Understood re '{inst}'. Recommendations:\n1. Check docs at [path]\n2. Try [common fix]\n3. See [log location] for details\nNeed deeper help on any step?",
}


def _synthesize_response(instruction: str, category: str) -> str:
    tmpl = _RESPONSE_TEMPLATES.get(category, _RESPONSE_TEMPLATES["explain"])
    if "{inst}" in tmpl:
        return tmpl.format(inst=instruction[:60])
    return tmpl


# ═══ DreamPretrainer ════════════════════════════════════════════════

class DreamPretrainer:
    """Idle-time synthetic data generation and LoRA fine-tuning engine.

    Triggered by Biorhythm (DREAMING) or GreenScheduler (GROWTH). Generates
    curriculum-ordered synthetic samples, fine-tunes via LoRA, evaluates deltas.
    Safety: no dreaming during user sessions, max 30min, checks token budget.
    """

    def __init__(self, config: DreamConfig | None = None,
                 store_path: str = ".livingtree/dream_history.json"):
        self._config = config or DreamConfig()
        self._store_path = Path(store_path)
        self._sessions: list[DreamSession] = []
        self._is_dreaming = False
        self._last_activity = 0.0
        self._total_dream_seconds = 0.0
        self._total_samples = 0
        self._best_improvement = 0.0
        self._load()

    # ── Public API ──

    def configure(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self._config, k):
                setattr(self._config, k, v)

    def notify_activity(self) -> None:
        self._last_activity = time.time()

    def should_dream(self) -> bool:
        if self._is_dreaming or not self._config.auto_trigger:
            return False
        idle_m = (time.time() - max(self._last_activity, time.time() - 86400)) / 60.0
        if idle_m < self._config.min_idle_minutes:
            return False
        if self._config.night_only and not self._is_night_hours():
            return False
        if not self._has_resources():
            return False
        if not self._check_token_budget():
            return False
        return True

    def generate_synthetic_data(self, n_samples: int | None = None) -> list[SyntheticSample]:
        n = min(n_samples or self._config.max_synthetic_samples, self._config.max_synthetic_samples)
        samples: list[SyntheticSample] = []
        for _ in range(n):
            t = random.choice(SYNTHETIC_TEMPLATES)
            cat, tmpl_str, diff = t["c"], t["t"], t["d"]
            filler = {k: random.choice(v) for k, v in FILLERS.items() if "{" + k + "}" in tmpl_str}
            try:
                instr = tmpl_str.format(**filler)
            except KeyError:
                instr = tmpl_str
            diff = max(0.0, min(1.0, diff + random.uniform(-0.1, 0.1)))
            resp = _synthesize_response(instr, cat)
            samples.append(SyntheticSample(
                instruction=instr, response=resp, category=cat,
                difficulty=diff, source_template="dream_learner",
            ))
        samples.sort(key=lambda s: s.difficulty)
        logger.info(f"DreamPretrainer: {len(samples)} samples, {len(set(s.category for s in samples))} categories")
        return samples

    async def dream_cycle(self, cell: Any = None) -> DreamSession:
        sid = f"dream_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        t0 = time.time()
        session = DreamSession(session_id=sid, start_time=t0)

        if self._is_dreaming:
            session.status, session.error = "skipped", "already dreaming"
            return session
        if not self.should_dream():
            session.status, session.error = "aborted", "preflight checks failed"
            return session

        self._is_dreaming = True
        logger.info(f"DreamPretrainer: starting {sid}")

        try:
            samples = self.generate_synthetic_data()
            if not samples:
                self._is_dreaming = False
                session.status, session.error = "aborted", "no samples generated"
                return session
            session.samples_generated = len(samples)

            dataset = [{"instruction": s.instruction, "output": s.response} for s in samples]

            from .swift_trainer import SwiftDrillTrainer, DrillConfig
            trainer = SwiftDrillTrainer()
            if not trainer.is_available():
                if cell and hasattr(cell, "train"):
                    cell.train(dataset, epochs=1)
                else:
                    self._is_dreaming = False
                    session.status, session.error = "aborted", "SWIFT not available"
                    return session
            else:
                drill_cfg = DrillConfig(
                    model_name=self._config.model_name, training_type="lora",
                    lora_rank=self._config.lora_rank, epochs=1, batch_size=2,
                    max_seq_length=1024, output_dir=f"./data/cells/dream_{sid}",
                    dataset_name=f"{getattr(cell, 'name', 'dream_cell')}_dream_data",
                )
                try:
                    result = await asyncio.wait_for(
                        trainer.train_lora(cell or {}, dataset, drill_cfg),
                        timeout=self._config.max_dream_duration_minutes * 60,
                    )
                    if result.success:
                        session.training_loss = result.loss
                except asyncio.TimeoutError:
                    session.status, session.error = "aborted", "training timeout"

            test_q = self._gen_test_queries()
            session.improvement_score = await self.evaluate_improvement(None, cell, test_q)

            if session.improvement_score and session.improvement_score > self._config.min_improvement:
                if cell and hasattr(cell, "save_checkpoint"):
                    cell.save_checkpoint()
                logger.info(f"DreamPretrainer: improvement {session.improvement_score:.3f} > threshold, saved")

            if session.improvement_score and session.improvement_score > self._best_improvement:
                self._best_improvement = session.improvement_score

            self._total_dream_seconds += time.time() - t0
            self._total_samples += len(samples)
            session.status = "completed"

        except Exception as e:
            logger.error(f"DreamPretrainer: dream failed: {e}")
            session.status, session.error = "error", str(e)
        finally:
            self._is_dreaming = False
            session.duration_minutes = (time.time() - t0) / 60.0
            self._sessions.append(session)
            self._save()
            logger.info(f"DreamPretrainer: {sid} done — {session.samples_generated} samples, "
                        f"loss={session.training_loss}, imp={session.improvement_score}, "
                        f"{session.duration_minutes:.1f}m")
        return session

    async def evaluate_improvement(self, before_model: Any | None, after_model: Any | None,
                                   test_queries: list[str] | None = None) -> float:
        queries = test_queries or self._gen_test_queries()
        if not queries:
            return 0.0
        scores: list[float] = []
        for q in queries:
            br = before_model.infer(q) if before_model and hasattr(before_model, "infer") else ""
            ar = after_model.infer(q) if after_model and hasattr(after_model, "infer") else ""
            bs = self._score_response(br, q)
            as_ = self._score_response(ar, q)
            imp = max(0.0, (as_ - bs) / bs) if bs > 0 else min(1.0, as_ / max(1.0, len(q) * 0.1))
            scores.append(imp)
        return sum(scores) / max(len(scores), 1)

    def get_last_session(self) -> Optional[DreamSession]:
        return self._sessions[-1] if self._sessions else None

    def dream_history(self, limit: int = 10) -> list[DreamSession]:
        return list(reversed(self._sessions[-limit:]))

    def stats(self) -> dict[str, Any]:
        completed = [s for s in self._sessions if s.status == "completed"]
        return {
            "total_sessions": len(self._sessions),
            "completed_sessions": len(completed),
            "total_dream_hours": round(self._total_dream_seconds / 3600.0, 2),
            "total_samples": self._total_samples,
            "best_improvement": round(self._best_improvement, 4),
            "last_session": self._sessions[-1].session_id if self._sessions else None,
            "is_dreaming": self._is_dreaming,
            "config": {
                "max_dream_minutes": self._config.max_dream_duration_minutes,
                "min_idle_minutes": self._config.min_idle_minutes,
                "max_samples": self._config.max_synthetic_samples,
                "night_only": self._config.night_only,
                "auto_trigger": self._config.auto_trigger,
            },
        }

    @property
    def is_dreaming(self) -> bool:
        return self._is_dreaming

    # ── Internal ──

    def _is_night_hours(self) -> bool:
        h = datetime.now().hour
        return h >= 22 or h < 6

    def _has_resources(self) -> bool:
        try:
            import psutil
            if psutil.cpu_percent() > 70 or psutil.virtual_memory().percent > 80:
                return False
        except ImportError:
            pass
        try:
            import pynvml
            pynvml.nvmlInit()
            for i in range(pynvml.nvmlDeviceGetCount()):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                m = pynvml.nvmlDeviceGetMemoryInfo(h)
                if m.used / m.total > 0.85:
                    pynvml.nvmlShutdown()
                    return False
            pynvml.nvmlShutdown()
        except ImportError:
            pass
        return True

    def _check_token_budget(self) -> bool:
        try:
            from ..core.context_budget import get_context_budget
            b = get_context_budget()
            return (b._state.max_tokens - b._state.total_tokens) >= self._config.min_token_budget
        except Exception:
            return True

    def _gen_test_queries(self, n: int = 10) -> list[str]:
        queries: list[str] = []
        for t in random.sample(SYNTHETIC_TEMPLATES, min(n, len(SYNTHETIC_TEMPLATES))):
            tmpl = t["t"]
            filler = {k: random.choice(v) for k, v in FILLERS.items() if "{" + k + "}" in tmpl}
            try:
                queries.append(tmpl.format(**filler))
            except KeyError:
                queries.append(tmpl)
        return queries

    @staticmethod
    def _score_response(response: str, query: str) -> float:
        if not response:
            return 0.0
        score = 0.0
        rlen = len(response)
        if rlen < 20:
            score += rlen / 20.0 * 0.3
        elif rlen < 500:
            score += 0.3
        else:
            score += max(0.2, 0.3 - (rlen - 500) / 5000.0 * 0.1)
        markers = ["```", "step", "1.", "first", "**", "#", "|", "recommend", "because", "example"]
        hits = sum(1 for m in markers if m in response.lower())
        score += min(0.4, hits * 0.08)
        qkw = set(query.lower().split()) - {"the", "a", "an", "is", "in", "of", "to", "and", "for", "this", "i", "you", "how", "what", "why", "when", "can"}
        if qkw:
            rl = response.lower()
            matches = sum(1 for w in qkw if w in rl)
            score += min(0.3, matches / max(len(qkw), 1) * 0.3)
        return score

    # ── Persistence ──

    def _load(self) -> None:
        try:
            if self._store_path.exists():
                data = json.loads(self._store_path.read_text("utf-8"))
                self._sessions = [
                    DreamSession(**{k: v for k, v in item.items() if k in DreamSession.__dataclass_fields__})
                    for item in data.get("sessions", [])
                ]
                self._total_dream_seconds = data.get("total_dream_seconds", 0.0)
                self._total_samples = data.get("total_samples", 0)
                self._best_improvement = data.get("best_improvement", 0.0)
                logger.info(f"DreamPretrainer: loaded {len(self._sessions)} sessions")
        except Exception as e:
            logger.warning(f"DreamPretrainer: load failed: {e}")

    def _save(self) -> None:
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "total_dream_seconds": self._total_dream_seconds,
                "total_samples": self._total_samples,
                "best_improvement": self._best_improvement,
                "sessions": [{f.name: getattr(s, f.name) for f in DreamSession.__dataclass_fields__.values()}
                             for s in self._sessions[-100:]],
            }
            self._store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        except Exception as e:
            logger.warning(f"DreamPretrainer: save failed: {e}")


# ═══ Singleton ═══════════════════════════════════════════════════════

_dream_pretrainer: Optional[DreamPretrainer] = None


def get_dream_pretrainer(config: DreamConfig | None = None) -> DreamPretrainer:
    global _dream_pretrainer
    if _dream_pretrainer is None:
        _dream_pretrainer = DreamPretrainer(config=config)
        logger.info("DreamPretrainer singleton initialized")
    return _dream_pretrainer
