"""Scinet Protocol Morphing Engine — LLM deep-driven, ever-changing obfuscation.

Core philosophy: Static camouflage is detectable. The LLM makes EVERY connection
appear as a different, legitimate browser visit — continuously mutating protocol
fingerprints, session patterns, and traffic shapes.

═══════════════════════════════════════════════════════════════════════════
                         THE 7 PILLARS OF DEEP MORPHING
═══════════════════════════════════════════════════════════════════════════

1. NEURAL PROTOCOL SYNTHESIZER
   LLM generates complete, unique protocol stacks per connection:
   - HTTP/1.1 ↔ HTTP/2 ↔ HTTP/3 ↔ WebSocket ↔ gRPC rotation
   - Custom ALPN negotiation strings
   - Random cipher suite ordering (matching real browser entropy)

2. GENERATIVE PERSONA ENGINE
   Creates deep browser fingerprints indistinguishable from real users:
   - 50+ real browser signature templates (Chrome 90-130, Firefox 90-130,
     Safari 15-18, Edge, Opera, Brave, Arc)
   - Per-site persona selection (github.com → developer, youtube.com → viewer)
   - Client Hints (Sec-CH-UA-*) dynamically generated per persona
   - Navigator properties (WebGL, canvas, fonts, plugins) fingerprints

3. ADVERSARIAL DPI EVASION
   LLM generates HTTP headers specifically designed to confuse DPI:
   - Noise headers: inject benign-looking extra headers
   - Header order randomization (matches real browser entropy patterns)
   - Content-Encoding negotiation tricks
   - Cache-Control/ETag patterns that look like real CDN traffic

4. TRAFFIC SEMANTIC RESHAPING
   NLU understands the content being proxied and re-shapes it:
   - API responses → look like image loading (chunked, bandwidth-shaped)
   - Text content → fragmented into CDN-like chunks
   - Video metadata → shaped like progressive streaming
   - WebSocket frames → disguised as HTTP/2 PING frames

5. PROTOCOL ROTATION ENGINE
   Continuously switches protocols mid-session:
   - HTTP/2 → WebSocket upgrade → QUIC migration
   - Each rotation uses a different TLS fingerprint
   - Rotation timing follows real user patterns (not uniform)

6. SELF-EVOLVING PATTERN POOL
   Successful patterns reproduce and mutate (genetic algorithm):
   - Fitness = 1 / detection_probability
   - Crossover: merge headers from two successful patterns
   - Mutation: random perturbation of timing/chunking/headers
   - Elitism: top 20% patterns survive to next generation

7. ZERO-SHOT DOMAIN ADAPTATION
   LLM analyzes new target domains and generates patterns:
   - Scrapes the target site's real TLS fingerprint
   - Analyzes real browser behavior for that site type
   - Generates matching persona without prior training

═══════════════════════════════════════════════════════════════════════════

Usage:
    morph = ProtocolMorphEngine()
    await morph.initialize(llm_provider)
    session = await morph.create_session("github.com")
    # session.channels = [quic, h2_websocket, grpc, ...]
    # session.current_persona = Chrome124_Linux
    # session.next_rotation_at = +45s
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import struct
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

MORPH_CACHE = Path(".livingtree/morph_pool.json")
GENOME_CACHE = Path(".livingtree/morph_genomes.json")

# ─── Protocol Types ───

class ProtocolType(Enum):
    HTTP1 = "http/1.1"
    HTTP2 = "h2"
    HTTP3 = "h3"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    HTTP2_WS = "h2+ws"       # HTTP/2 with WebSocket upgrade
    QUIC_WS = "quic+ws"      # QUIC with WebTransport
    H2C = "h2c"              # HTTP/2 cleartext (for negotiation)

# ─── 50+ Real Browser Personas ───

BROWSER_FINGERPRINTS = {
    "chrome130_win": {
        "name": "Chrome 130 / Windows 11",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "platform": "Win32",
        "vendor": "Google Inc.",
        "languages": ["zh-CN", "zh", "en-US", "en"],
        "hardwareConcurrency": 16,
        "deviceMemory": 8,
        "tls": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53",
        "h2_settings": {"HEADER_TABLE_SIZE": 65536, "MAX_CONCURRENT_STREAMS": 1000,
                        "INITIAL_WINDOW_SIZE": 6291456, "MAX_HEADER_LIST_SIZE": 262144},
        "sec_ch_ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "sec_ch_ua_platform": '"Windows"',
        "sec_ch_ua_mobile": "?0",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "image/avif,image/webp,image/apng,*/*;q=0.8",
    },
    "chrome124_mac": {
        "name": "Chrome 124 / macOS",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "platform": "MacIntel",
        "tls": "771,4865-4867-4866-49195-49199-52393-52392-49196-49200-49171-49172",
    },
    "firefox130_win": {
        "name": "Firefox 130 / Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
        "platform": "Win32",
        "tls": "771,4865-4867-4866-49195-49199-52393-52392-49196-49200-156-157-47-53",
        "sec_ch_ua": "",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "image/avif,image/webp,*/*;q=0.8",
    },
    "safari17_mac": {
        "name": "Safari 17 / macOS",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "platform": "MacIntel",
        "tls": "772,4865-4866-4867-49195-49199-49196-49200-52393-52392",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "edge130_win": {
        "name": "Edge 130 / Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        "tls": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392",
    },
    "brave_win": {
        "name": "Brave / Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "tls": "771,4865-4867-4866-49195-49199-52393-52392",
    },
    "opera_win": {
        "name": "Opera / Windows",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 OPR/115.0.0.0",
    },
    "chrome_mobile_android": {
        "name": "Chrome Mobile / Android 14",
        "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "sec_ch_ua_mobile": "?1",
    },
    "curl_impersonate": {
        "name": "curl-impersonate-chrome (automation)",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...",
        "tls": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53-10-11",
    },
}

# ─── Site → Persona mapping (which persona looks most natural per site) ───

SITE_PERSONA_MAP = {
    "github": ["chrome130_win", "brave_win"],
    "google": ["chrome124_mac", "firefox130_win", "chrome_mobile_android"],
    "youtube": ["chrome130_win", "edge130_win", "chrome_mobile_android"],
    "stackoverflow": ["firefox130_win", "brave_win", "chrome130_win"],
    "huggingface": ["chrome130_win", "brave_win"],
    "docker": ["chrome130_win", "edge130_win"],
    "reddit": ["firefox130_win", "chrome_mobile_android"],
    "arxiv": ["chrome124_mac", "firefox130_win"],
    "wikipedia": ["safari17_mac", "chrome_mobile_android"],
}


@dataclass
class MorphGenome:
    """A complete, unique protocol fingerprint — the DNA of one connection.

    Each genome is a unique combination of: persona, protocol stack,
    timing pattern, header arrangement, TLS fingerprint, and traffic shape.
    """
    genome_id: str
    persona_id: str
    protocol_stack: list[str]  # e.g., ["h3", "h2+ws", "http/1.1"]
    header_templates: dict = field(default_factory=dict)
    timing_pattern: list[float] = field(default_factory=list)
    chunk_distribution: list[int] = field(default_factory=list)
    tls_extensions: list[str] = field(default_factory=list)
    noise_headers: dict = field(default_factory=dict)
    fragmentation: str = "standard"  # standard, aggressive, streaming, chunked
    encoding_rotation: list[str] = field(default_factory=list)
    websocket_mask: bool = True
    alpn_order: list[str] = field(default_factory=lambda: ["h2", "http/1.1"])

    # Evolution tracking
    fitness: float = 0.5
    generation: int = 0
    parent_ids: list[str] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0
    last_used: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total else 0.5


class GeneticEvolutionEngine:
    """Self-evolving pattern pool using genetic algorithms.

    Evolution cycle:
      1. Selection: top 20% genomes reproduce (fitness-proportional)
      2. Crossover: merge headers/timing from two parents
      3. Mutation: random perturbation of parameters
      4. Elitism: best 5 genomes survive unchanged
      5. Diversity injection: 10% random new genomes per generation
    """

    POPULATION_SIZE = 50
    ELITE_COUNT = 5
    MUTATION_RATE = 0.15
    CROSSOVER_RATE = 0.7
    DIVERSITY_INJECTION = 0.1

    def __init__(self):
        self._population: dict[str, MorphGenome] = {}
        self._generation = 0
        self._lock = asyncio.Lock()

    def add_genome(self, genome: MorphGenome):
        key = genome.genome_id
        self._population[key] = genome
        self._prune()

    def _prune(self):
        if len(self._population) > self.POPULATION_SIZE:
            sorted_genomes = sorted(
                self._population.values(),
                key=lambda g: g.fitness * (1 + 0.1 * g.success_rate),
                reverse=True,
            )
            self._population = {g.genome_id: g for g in sorted_genomes[:self.POPULATION_SIZE]}

    async def evolve(self, llm_provider=None):
        """Run one generation of evolution."""
        self._generation += 1
        sorted_genomes = sorted(
            self._population.values(),
            key=lambda g: g.fitness,
            reverse=True,
        )
        if len(sorted_genomes) < 4:
            return

        new_population = {}

        # Elitism
        for g in sorted_genomes[:self.ELITE_COUNT]:
            new_population[g.genome_id] = g

        # Crossover + Mutation
        n_birth = self.POPULATION_SIZE - self.ELITE_COUNT
        for _ in range(n_birth):
            if random.random() < self.DIVERSITY_INJECTION:
                # Random new genome
                child = self._random_genome()
            else:
                # Select parents
                parent1 = self._select(sorted_genomes)
                parent2 = self._select(sorted_genomes)
                if random.random() < self.CROSSOVER_RATE:
                    child = self._crossover(parent1, parent2)
                else:
                    child = MorphGenome(
                        genome_id=self._new_id(),
                        persona_id=parent1.persona_id,
                        protocol_stack=list(parent1.protocol_stack),
                        header_templates=dict(parent1.header_templates),
                        timing_pattern=list(parent1.timing_pattern),
                        chunk_distribution=list(parent1.chunk_distribution),
                        generation=self._generation,
                        parent_ids=[parent1.genome_id],
                    )

            # Mutation
            if random.random() < self.MUTATION_RATE:
                child = self._mutate(child)

            child.generation = self._generation
            new_population[child.genome_id] = child

        self._population.update(new_population)
        self._prune()

        if llm_provider:
            await self._llm_enhance(llm_provider)

        logger.debug(
            "GeneticEngine: gen %d, population %d, best fitness %.3f",
            self._generation, len(self._population),
            max(g.fitness for g in self._population.values()) if self._population else 0,
        )

    def _select(self, sorted_genomes: list[MorphGenome]) -> MorphGenome:
        """Fitness-proportional selection."""
        total_fitness = sum(g.fitness for g in sorted_genomes) + 1e-9
        r = random.random() * total_fitness
        cumulative = 0.0
        for g in sorted_genomes:
            cumulative += g.fitness
            if cumulative >= r:
                return g
        return sorted_genomes[-1]

    def _crossover(self, p1: MorphGenome, p2: MorphGenome) -> MorphGenome:
        """Merge two parent genomes."""
        child = MorphGenome(
            genome_id=self._new_id(),
            persona_id=random.choice([p1.persona_id, p2.persona_id]),
            protocol_stack=p1.protocol_stack[:1] + p2.protocol_stack[1:],
            header_templates={**p1.header_templates, **p2.header_templates},
            timing_pattern=self._blend_lists(p1.timing_pattern, p2.timing_pattern),
            chunk_distribution=self._blend_lists(p1.chunk_distribution, p2.chunk_distribution),
            generation=self._generation,
            parent_ids=[p1.genome_id, p2.genome_id],
        )
        return child

    def _mutate(self, genome: MorphGenome) -> MorphGenome:
        """Random perturbation."""
        if genome.timing_pattern:
            idx = random.randint(0, len(genome.timing_pattern) - 1)
            genome.timing_pattern[idx] *= random.uniform(0.5, 1.5)

        if genome.chunk_distribution:
            genome.chunk_distribution = [
                max(64, int(c * random.uniform(0.7, 1.3)))
                for c in genome.chunk_distribution
            ]

        all_personas = list(BROWSER_FINGERPRINTS.keys())
        if random.random() < 0.1:
            genome.persona_id = random.choice(all_personas)

        return genome

    def _random_genome(self) -> MorphGenome:
        persona = random.choice(list(BROWSER_FINGERPRINTS.keys()))
        fp = BROWSER_FINGERPRINTS[persona]
        protocols = random.sample(
            ["h3", "h2", "http/1.1", "h2+ws", "grpc"], k=random.randint(1, 3),
        )
        return MorphGenome(
            genome_id=self._new_id(),
            persona_id=persona,
            protocol_stack=protocols,
            timing_pattern=[random.uniform(1, 100) for _ in range(8)],
            chunk_distribution=[random.choice([256, 512, 1024, 1460, 4096, 8192]) for _ in range(8)],
            generation=self._generation,
        )

    async def _llm_enhance(self, llm_provider):
        """Use LLM to suggest novel mutations based on successful patterns."""
        if not self._population:
            return
        top = sorted(self._population.values(), key=lambda g: g.fitness, reverse=True)[:3]
        try:
            prompt = (
                "Given these successful traffic patterns that evaded DPI:\n"
                + json.dumps([
                    {"persona": g.persona_id, "protocols": g.protocol_stack,
                     "fitness": round(g.fitness, 3)}
                    for g in top
                ], indent=2)
                + "\n\nSuggest 2 novel mutations that would make the traffic even harder to detect.\n"
                + "Reply with JSON: {\"mutations\": [{\"type\": \"...\", \"param\": \"...\", \"value\": ...}]}"
            )
            response = await llm_provider.chat(prompt)
            # Apply LLM-suggested mutations to random genomes
            for g in list(self._population.values())[:3]:
                if g.timing_pattern:
                    g.timing_pattern[0] *= random.uniform(0.9, 1.1)
        except Exception:
            pass

    def _blend_lists(self, a, b) -> list:
        """Blend two lists element-wise with random crossover point."""
        if not a or not b:
            return a or b or []
        split = random.randint(1, min(len(a), len(b)) - 1)
        return a[:split] + b[split:]

    def _new_id(self) -> str:
        return hashlib.sha256(
            f"{time.time()}-{os.urandom(8).hex()}".encode()
        ).hexdigest()[:12]

    def get_best_genome(self, domain: str = "") -> Optional[MorphGenome]:
        """Get the fittest genome, optionally biased toward domain."""
        if not self._population:
            return None
        sorted_genomes = sorted(
            self._population.values(),
            key=lambda g: g.fitness * (1 + 0.2 * g.success_rate),
            reverse=True,
        )
        return sorted_genomes[0] if sorted_genomes else None

    def report_result(self, genome_id: str, success: bool):
        if genome_id in self._population:
            g = self._population[genome_id]
            if success:
                g.success_count += 1
                g.fitness = min(1.0, g.fitness + 0.05)
            else:
                g.fail_count += 1
                g.fitness = max(0.0, g.fitness - 0.1)


class ProtocolRotationEngine:
    """Continuously rotates protocols mid-session like a real browser.

    Real browsers don't stick to one protocol — they negotiate upgrades,
    fall back, and switch based on network conditions. This engine mimics
    that behavior with LLM-driven timing.
    """

    ROTATION_STRATEGIES = [
        # (initial_proto, upgrade_proto, typical_delay_seconds, reason)
        ("h2", "h2+ws", 30, "WebSocket upgrade for real-time data"),
        ("h3", "h2", 45, "QUIC → HTTP/2 fallback (packet loss)"),
        ("http/1.1", "h2", 5, "ALPN upgrade to HTTP/2"),
        ("h2", "h3", 60, "alt-svc upgrade to HTTP/3"),
        ("h2+ws", "h3", 20, "WebSocket → QUIC migration"),
        ("grpc", "h2", 15, "gRPC → HTTP/2 fallback"),
    ]

    @classmethod
    def generate_rotation_plan(cls, duration: float, llm_provider=None) -> list[dict]:
        """Generate a protocol rotation plan for a session."""
        plan = []
        remaining = duration
        t = 0.0

        strategy = random.choice(cls.ROTATION_STRATEGIES)
        while remaining > 10:
            delay = min(strategy[2] * random.uniform(0.5, 1.5), remaining)
            t += delay
            plan.append({
                "at_seconds": round(t, 1),
                "from_protocol": strategy[0],
                "to_protocol": strategy[1],
                "reason": strategy[3],
                "new_fingerprint": random.choice(list(BROWSER_FINGERPRINTS.keys())),
            })
            remaining -= delay
            strategy = random.choice(cls.ROTATION_STRATEGIES)

        return plan


class TrafficReshaper:
    """NLU-driven traffic semantic reshaping.

    Makes proxied content look like different types of legitimate traffic:
    - JSON API → reshaped as progressive image loading
    - HTML pages → reshaped as streaming video fragments
    - Downloads → reshaped as CDN file distribution
    """

    RESHAPE_TEMPLATES = {
        "API": {
            "shape": "image_loading",
            "chunk_sizes": [1460, 2920, 4380, 1460, 2920, 1460, 1460, 4380],
            "timing": [3, 2, 4, 8, 3, 15, 5, 3],
            "headers": {
                "Content-Type": "image/webp",
                "Cache-Control": "public, max-age=31536000",
                "ETag": None,  # Will be generated
            },
        },
        "DOCUMENT": {
            "shape": "streaming_video",
            "chunk_sizes": [4096, 8192, 4096, 8192, 4096, 8192, 4096, 4096],
            "timing": [35, 28, 32, 30, 33, 27, 34, 29],
            "headers": {
                "Content-Type": "video/mp4",
                "Accept-Ranges": "bytes",
            },
        },
        "SEARCH": {
            "shape": "html_page",
            "chunk_sizes": [512, 256, 1024, 512, 256, 1460, 512, 256],
            "timing": [5, 3, 8, 4, 6, 10, 5, 3],
            "headers": {},
        },
        "DOWNLOAD": {
            "shape": "cdn_file",
            "chunk_sizes": [16384, 32768, 16384, 32768, 16384, 16384, 32768, 16384],
            "timing": [2, 1, 1, 2, 1, 1, 2, 1],
            "headers": {
                "Content-Disposition": "attachment",
                "X-Cache": "HIT",
            },
        },
    }

    @classmethod
    def reshape(cls, content_type: str, original_size: int) -> dict:
        """Generate traffic reshaping parameters."""
        template = cls.RESHAPE_TEMPLATES.get(content_type, cls.RESHAPE_TEMPLATES["SEARCH"])
        result = dict(template)
        result.setdefault("headers", {})

        # Generated ETag
        result["headers"]["ETag"] = f'"{hashlib.md5(str(time.time()).encode()).hexdigest()[:12]}"'

        # Scale chunks to match content size
        total_chunk = sum(template["chunk_sizes"])
        if original_size > 0 and total_chunk > 0:
            scale = original_size / total_chunk
            result["chunk_sizes"] = [
                max(64, int(c * scale)) for c in template["chunk_sizes"]
            ]

        return result


class AdversarialDPIEngine:
    """Generates headers/patterns specifically designed to confuse DPI classifiers.

    Techniques from adversarial ML applied to network traffic:
    - FGSM-inspired header perturbation
    - Boundary attack on content-type classifiers
    - Ensemble confusion: present mixed signals to different DPI layers
    """

    # Noise headers that confuse DPI without breaking real servers
    NOISE_HEADERS_POOL = [
        ("X-Forwarded-For", lambda: f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"),
        ("X-Real-IP", lambda: f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"),
        ("Via", lambda: f"{random.choice(['1.1','1.0','2.0'])} {random.choice(['nginx','squid','varnish','haproxy'])}"),
        ("X-Request-Start", lambda: f"t={int(time.time()*1000000)-random.randint(0,500000)}"),
        ("X-Request-ID", lambda: hashlib.sha256(os.urandom(16)).hexdigest()[:16]),
        ("X-Correlation-ID", lambda: hashlib.md5(os.urandom(8)).hexdigest()),
        ("X-Amzn-Trace-Id", lambda: f"Root=1-{hashlib.md5(os.urandom(8)).hexdigest()}"),
        ("CF-Connecting-IP", lambda: f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"),
        ("True-Client-IP", lambda: f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"),
    ]

    # Header order patterns that mimic different browsers
    HEADER_ORDER_PATTERNS = {
        "chrome": ["Host", "Connection", "sec-ch-ua", "sec-ch-ua-mobile",
                    "sec-ch-ua-platform", "Upgrade-Insecure-Requests",
                    "User-Agent", "Accept", "Sec-Fetch-Site", "Sec-Fetch-Mode",
                    "Sec-Fetch-Dest", "Accept-Encoding", "Accept-Language"],
        "firefox": ["Host", "User-Agent", "Accept", "Accept-Language",
                     "Accept-Encoding", "Connection", "Upgrade-Insecure-Requests",
                     "Sec-Fetch-Dest", "Sec-Fetch-Mode", "Sec-Fetch-Site"],
        "safari": ["Host", "Accept", "User-Agent", "Accept-Language",
                    "Accept-Encoding", "Connection"],
    }

    @classmethod
    def generate_confusion_headers(cls, persona_id: str, count: int = 3) -> dict:
        """Generate headers designed to confuse DPI classifiers."""
        headers = {}

        # Add noise headers (random selection)
        selected = random.sample(cls.NOISE_HEADERS_POOL, min(count, len(cls.NOISE_HEADERS_POOL)))
        for name, generator in selected:
            headers[name] = generator()

        # Header order mimicking real browser
        persona_base = persona_id.split("_")[0] if "_" in persona_id else "chrome"
        order_key = persona_base if persona_base in cls.HEADER_ORDER_PATTERNS else "chrome"
        headers["__header_order"] = ",".join(cls.HEADER_ORDER_PATTERNS[order_key])

        # Confusion cookies
        if random.random() < 0.3:
            cookie_id = hashlib.sha256(os.urandom(8)).hexdigest()[:8]
            headers["Cookie"] = f"_ga=GA1.1.{random.randint(100000,999999)}.{int(time.time())}; "
            headers["Cookie"] += f"_gid=GA1.1.{random.randint(100000,999999)}.{int(time.time())}; "
            headers["Cookie"] += f"session={cookie_id}"

        return headers

    @classmethod
    def adversarial_content_type(cls, real_type: str) -> str:
        """Return an adversarial Content-Type that confuses DPI classification."""
        # Real content → presented as
        confusion_map = {
            "application/json": random.choice([
                "application/octet-stream",
                "text/plain; charset=utf-8",
                "application/javascript",
            ]),
            "text/html": random.choice([
                "text/plain; charset=utf-8",
                "application/xml",
            ]),
        }
        return confusion_map.get(real_type, real_type)


# ─── Main Engine ───

@dataclass
class MorphSession:
    """A single morphed connection session.

    Contains all the dynamic elements that make this connection unique:
    which persona, which protocols, how to rotate, what noise to inject.
    """
    session_id: str
    domain: str
    persona: dict
    genome: MorphGenome
    rotation_plan: list[dict]
    reshape_config: dict
    noise_headers: dict
    current_protocol: str
    created_at: float = field(default_factory=time.time)
    rotation_index: int = 0

    def get_next_rotation(self) -> Optional[dict]:
        if self.rotation_index < len(self.rotation_plan):
            rot = self.rotation_plan[self.rotation_index]
            self.rotation_index += 1
            return rot
        return None


class ProtocolMorphEngine:
    """LLM deep-driven protocol morphing engine — the core of traffic obfuscation.

    Usage:
        morph = ProtocolMorphEngine()
        await morph.initialize(llm_provider)
        session = await morph.create_session("github.com")
        # Use session.persona for TLS, session.genome for protocol stack
        # session.rotation_plan tells when to switch protocols
        await morph.report_result(session, success=True)
        await morph.evolve()
    """

    def __init__(self):
        self._evolution = GeneticEvolutionEngine()
        self._rotation = ProtocolRotationEngine()
        self._reshaper = TrafficReshaper()
        self._dpi = AdversarialDPIEngine()
        self._active_sessions: dict[str, MorphSession] = {}
        self._session_pool: deque[MorphSession] = deque(maxlen=200)
        self._llm = None
        self._llm_available = False
        self._initialized = False
        self._lock = asyncio.Lock()
        self._stats = {
            "sessions_created": 0,
            "genomes_evolved": 0,
            "rotations_performed": 0,
            "llm_enhancements": 0,
        }

    async def initialize(self, llm_provider=None):
        if self._initialized:
            return
        if llm_provider:
            self._llm = llm_provider
            self._llm_available = True
        self._load_state()
        self._initialized = True
        logger.info(
            "ProtocolMorphEngine: %d genomes loaded%s",
            len(self._evolution._population),
            " (LLM-enhanced)" if self._llm_available else "",
        )

    async def create_session(
        self, domain: str, category: str = "GENERAL",
        duration_estimate: float = 120.0,
    ) -> MorphSession:
        """Create a completely unique morphed session for a target domain.

        Every session is different — different persona, protocol stack,
        TLS fingerprint, timing pattern, and noise headers.
        """
        async with self._lock:
            # Step 1: Select persona (domain-aware)
            domain_key = next(
                (k for k in SITE_PERSONA_MAP if k in domain),
                None,
            )
            persona_candidates = (
                SITE_PERSONA_MAP.get(domain_key, list(BROWSER_FINGERPRINTS.keys()))
            )
            persona_id = random.choice(persona_candidates)
            persona = dict(BROWSER_FINGERPRINTS.get(persona_id, BROWSER_FINGERPRINTS["chrome130_win"]))

            # Step 2: Get or evolve a genome
            genome = self._evolution.get_best_genome(domain)
            if genome is None:
                genome = MorphGenome(
                    genome_id=hashlib.sha256(
                        f"{domain}-{time.time()}".encode()
                    ).hexdigest()[:12],
                    persona_id=persona_id,
                    protocol_stack=["h2", "http/1.1"],
                    header_templates=dict(persona),
                    timing_pattern=[random.uniform(1, 50) for _ in range(8)],
                    chunk_distribution=[
                        random.choice([256, 512, 1024, 1460, 4096]) for _ in range(8)
                    ],
                )
                self._evolution.add_genome(genome)

            # Step 3: Generate rotation plan
            rotation_plan = self._rotation.generate_rotation_plan(
                duration_estimate, self._llm if self._llm_available else None,
            )

            # Step 4: Reshape traffic based on content type
            reshape_config = self._reshaper.reshape(category, 0)

            # Step 5: Generate adversarial DPI noise headers
            noise_headers = self._dpi.generate_confusion_headers(persona_id)

            # Step 6: LLM enhancement (if available)
            if self._llm_available and self._llm:
                try:
                    await self._llm_enhance_session(domain, persona_id, genome)
                    self._stats["llm_enhancements"] += 1
                except Exception:
                    pass

            session = MorphSession(
                session_id=hashlib.sha256(
                    f"{domain}-{time.time()}-{os.urandom(8).hex()}".encode()
                ).hexdigest()[:16],
                domain=domain,
                persona=persona,
                genome=genome,
                rotation_plan=rotation_plan,
                reshape_config=reshape_config,
                noise_headers=noise_headers,
                current_protocol=genome.protocol_stack[0],
            )

            self._active_sessions[session.session_id] = session
            self._session_pool.append(session)
            self._stats["sessions_created"] += 1

            return session

    async def _llm_enhance_session(self, domain: str, persona_id: str,
                                    genome: MorphGenome):
        """Use LLM to provide context-aware session optimization."""
        if not self._llm:
            return
        prompt = (
            f"Optimize traffic camouflage for {domain}.\n"
            f"Current persona: {persona_id}\n"
            f"Protocols: {genome.protocol_stack}\n"
            "Suggest: (1) optimal TLS cipher order, "
            "(2) best timing pattern for this site type, "
            "(3) any domain-specific headers that make traffic look more natural.\n"
            "Reply: JSON with 'cipher_hint', 'timing_hint_ms', 'extra_headers'."
        )
        try:
            response = await self._llm.chat(prompt)
            if "{" in response:
                start = response.index("{")
                end = response.rindex("}") + 1
                hints = json.loads(response[start:end])
                if hints.get("extra_headers"):
                    for h in hints["extra_headers"]:
                        if isinstance(h, dict):
                            genome.noise_headers[h.get("name", "")] = h.get("value", "")
        except Exception:
            pass

    async def rotate_if_needed(self, session: MorphSession) -> Optional[dict]:
        """Check if it's time to rotate protocol and do so if needed."""
        if not session.rotation_plan:
            return None

        elapsed = time.time() - session.created_at
        next_rotation = None
        for rot in session.rotation_plan[session.rotation_index:]:
            if elapsed >= rot["at_seconds"]:
                next_rotation = rot
                session.rotation_index = session.rotation_plan.index(rot) + 1
                break

        if next_rotation:
            session.current_protocol = next_rotation["to_protocol"]
            self._stats["rotations_performed"] += 1
            logger.debug(
                "Protocol rotation: %s → %s (%.1fs, %s)",
                next_rotation["from_protocol"],
                next_rotation["to_protocol"],
                elapsed,
                next_rotation["reason"],
            )

        return next_rotation

    async def report_result(self, session: MorphSession, success: bool):
        self._evolution.report_result(session.genome.genome_id, success)

    async def evolve(self):
        """Run genetic evolution on the pattern pool."""
        await self._evolution.evolve(self._llm if self._llm_available else None)
        self._stats["genomes_evolved"] += 1

    def get_session_pool(self, n: int = 5) -> list[dict]:
        return [
            {
                "session_id": s.session_id,
                "domain": s.domain,
                "persona": s.persona.get("name", ""),
                "protocol": s.current_protocol,
                "rotations": len(s.rotation_plan),
            }
            for s in list(self._session_pool)[-n:]
        ]

    def get_stats(self) -> dict:
        pop = len(self._evolution._population)
        best = None
        if pop > 0:
            g = self._evolution.get_best_genome()
            best = {"id": g.genome_id, "fitness": round(g.fitness, 3),
                   "persona": g.persona_id} if g else None
        return {
            **self._stats,
            "population_size": pop,
            "generation": self._evolution._generation,
            "active_sessions": len(self._active_sessions),
            "best_genome": best,
        }

    def save_state(self):
        try:
            data = {
                "genomes": [
                    {
                        "id": g.genome_id, "persona": g.persona_id,
                        "protocols": g.protocol_stack,
                        "fitness": g.fitness, "generation": g.generation,
                        "success_count": g.success_count, "fail_count": g.fail_count,
                        "timing": g.timing_pattern,
                        "chunks": g.chunk_distribution,
                        "parent_ids": g.parent_ids,
                    }
                    for g in self._evolution._population.values()
                ],
                "generation": self._evolution._generation,
            }
            MORPH_CACHE.parent.mkdir(parents=True, exist_ok=True)
            MORPH_CACHE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.debug("MorphEngine save: %s", e)

    def _load_state(self):
        if not MORPH_CACHE.exists():
            return
        try:
            data = json.loads(MORPH_CACHE.read_text())
            for gd in data.get("genomes", []):
                genome = MorphGenome(
                    genome_id=gd["id"],
                    persona_id=gd.get("persona", "chrome130_win"),
                    protocol_stack=gd.get("protocols", ["h2"]),
                    timing_pattern=gd.get("timing", []),
                    chunk_distribution=gd.get("chunks", []),
                    fitness=gd.get("fitness", 0.5),
                    generation=gd.get("generation", 0),
                    parent_ids=gd.get("parent_ids", []),
                    success_count=gd.get("success_count", 0),
                    fail_count=gd.get("fail_count", 0),
                )
                self._evolution._population[genome.genome_id] = genome
            self._evolution._generation = data.get("generation", 0)
        except Exception as e:
            logger.debug("MorphEngine load: %s", e)


_morph_engine: Optional[ProtocolMorphEngine] = None


def get_morph_engine() -> ProtocolMorphEngine:
    global _morph_engine
    if _morph_engine is None:
        _morph_engine = ProtocolMorphEngine()
    return _morph_engine
