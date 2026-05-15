"""External Learning Drivers — GitHub trending + arXiv paper + Nature learning.

Three evolution drivers:
  1. GitHub Learner: Search trending repos for related patterns
  2. arXiv Learner: Fetch latest papers → extract insights
  3. Nature Learner: Search Nature.com journals for collective intelligence,
     multi-agent, LLM reasoning, and heterogeneous computing research

All three feed into self_evolution.py's mutation pipeline.
Integration: uses LearningSourceRegistry for user-configurable queries.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════

@dataclass
class LearnedPattern:
    """A code pattern learned from external sources."""
    source: str           # "github" or "arxiv"
    source_url: str
    category: str         # "architecture", "optimization", "security", "pattern"
    title: str
    description: str
    code_snippet: str = ""
    confidence: float = 0.5
    applicable_files: list[str] = field(default_factory=list)
    suggested_change: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class GithubRepo:
    """A discovered GitHub repository."""
    full_name: str
    stars: int
    description: str = ""
    language: str = "Python"
    topics: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    key_files: list[str] = field(default_factory=list)


@dataclass
class ArxivPaper:
    """A discovered arXiv paper."""
    arxiv_id: str
    title: str
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    published: str = ""
    relevance_score: float = 0.0
    key_insights: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════
# Part 1: GitHub Learner
# ═══════════════════════════════════════════════════════

class GitHubLearner:
    """Learn from trending GitHub projects in related domains.

    Searches for: agent frameworks, LLM routers, knowledge graphs,
    autonomous systems, multi-agent architectures.

    Extracts: code patterns, architectural decisions, optimization tricks.
    """

    # Search queries for finding related projects
    SEARCH_QUERIES = [
        ("LLM agent framework Python", "agent_framework"),
        ("multi-agent orchestration autonomous", "multi_agent"),
        ("knowledge graph RAG retrieval", "knowledge_graph"),
        ("LLM router model selection routing", "llm_router"),
        ("AI self-improving autonomous evolution", "self_evolution"),
        ("prompt optimization caching LLM", "prompt_engineering"),
        ("vector store semantic memory embedding", "vector_memory"),
        ("tool-calling function-calling agent Python", "tool_calling"),
    ]

    # LivingTree module → GitHub topic mapping for relevance scoring
    MODULE_TOPICS = {
        "treellm": ["llm", "router", "model-selection", "multi-model"],
        "dna": ["agent", "autonomous", "self-improving", "evolution"],
        "knowledge": ["rag", "retrieval", "knowledge-graph", "vector-store"],
        "execution": ["orchestrator", "task-planner", "pipeline"],
        "capability": ["tool", "skill", "function-calling"],
        "cell": ["training", "fine-tuning", "distillation"],
        "network": ["p2p", "federation", "distributed"],
    }

    def __init__(self):
        self._learned: list[LearnedPattern] = []
        self._repos: list[GithubRepo] = []
        self._cache_file = Path(".livingtree/github_learned.json")
        self._load_cache()

    def search_related_repos(self) -> list[GithubRepo]:
        """Search for related GitHub repositories.

        Uses heuristics based on query relevance + project metadata matching.
        In production: integrates with GitHub API (gh search repos).
        """
        repos = []

        for query, category in self.SEARCH_QUERIES:
            # Heuristic: match query terms against known repos
            # Production: gh search repos --sort stars --limit 10 "QUERY"
            related = self._heuristic_search(query, category)
            repos.extend(related)

        # Deduplicate and sort by relevance
        seen = set()
        unique = []
        for r in sorted(repos, key=lambda x: -x.relevance_score):
            if r.full_name not in seen:
                seen.add(r.full_name)
                unique.append(r)

        self._repos = unique[:20]
        return self._repos

    def extract_patterns(self, repos: list[GithubRepo] = None) -> list[LearnedPattern]:
        """Extract actionable code patterns from discovered repos.

        Maps repo features → LivingTree file → suggested change.
        """
        repos = repos or self._repos
        patterns = []

        for repo in repos[:10]:
            # Match repo topics to LivingTree modules
            matched_modules = self._match_modules(repo)

            for module in matched_modules:
                pattern = self._infer_pattern(repo, module)
                if pattern:
                    patterns.append(pattern)

        self._learned.extend(patterns)
        self._save_cache()
        return patterns

    def apply_learned(self, patterns: list[LearnedPattern] = None) -> dict[str, int]:
        """Apply learned patterns to the codebase.

        Returns: {file_path: changes_applied_count}
        """
        patterns = patterns or self._learned
        applied = {}

        for pattern in patterns:
            if not pattern.applicable_files or not pattern.suggested_change:
                continue

            for file_path in pattern.applicable_files:
                full_path = Path("livingtree") / file_path
                if not full_path.exists():
                    continue

                try:
                    content = full_path.read_text("utf-8")
                    if pattern.suggested_change not in content:
                        # Append improvement as comment near relevant section
                        marker = f"# [GitHub:{pattern.source_url}] {pattern.title}"
                        if marker not in content:
                            new_content = content.rstrip() + f"\n{marker}\n"
                            # Write to evolved directory for review
                            evolved = Path(".livingtree/evolved") / file_path
                            evolved.parent.mkdir(parents=True, exist_ok=True)
                            evolved.write_text(new_content, "utf-8")
                            applied[file_path] = applied.get(file_path, 0) + 1
                except Exception:
                    pass

        return applied

    # ── Heuristic search (replaces GitHub API in production) ──

    def _heuristic_search(self, query: str, category: str) -> list[GithubRepo]:
        """Heuristic GitHub search — production replaces with gh API."""
        # Known high-relevance repos for LivingTree
        KNOWN_REPOS = {
            "agent_framework": [
                GithubRepo("microsoft/autogen", 38000, "Multi-agent conversation framework",
                           topics=["agent", "multi-agent", "llm", "orchestration"]),
                GithubRepo("langchain-ai/langgraph", 12000, "Graph-based agent orchestration",
                           topics=["agent", "graph", "orchestration", "langchain"]),
                GithubRepo("run-llama/llama_index", 38000, "Data framework for LLM apps",
                           topics=["rag", "retrieval", "indexing", "llm"]),
            ],
            "multi_agent": [
                GithubRepo("OpenBMB/ChatDev", 26000, "Multi-agent software development",
                           topics=["multi-agent", "code-generation", "collaboration"]),
                GithubRepo("geekan/MetaGPT", 48000, "Multi-agent meta programming",
                           topics=["multi-agent", "sop", "software-engineering"]),
            ],
            "knowledge_graph": [
                GithubRepo("neo4j/neo4j", 14000, "Graph database",
                           topics=["graph", "knowledge-graph", "database"]),
                GithubRepo("microsoft/graphrag", 22000, "Graph-based RAG",
                           topics=["graphrag", "knowledge-graph", "retrieval"]),
            ],
            "llm_router": [
                GithubRepo("lm-sys/RouteLLM", 5000, "LLM router framework",
                           topics=["router", "llm", "cost-optimization"]),
                GithubRepo("martiansideofthemoon/llm-router", 2000, "LLM routing",
                           topics=["router", "model-selection"]),
            ],
            "self_evolution": [
                GithubRepo("TransformerOptimus/SuperAGI", 16000, "Autonomous AI agent framework",
                           topics=["autonomous", "self-improving", "agent"]),
                GithubRepo("Significant-Gravitas/AutoGPT", 170000, "Autonomous GPT-4 agent",
                           topics=["autonomous", "agent", "self-prompting"]),
            ],
        }

        results = KNOWN_REPOS.get(category, [])
        for r in results:
            # Score relevance based on LivingTree module overlap
            r.relevance_score = self._repo_relevance(r)
        return results

    def _repo_relevance(self, repo: GithubRepo) -> float:
        """Score how relevant a repo is to LivingTree modules."""
        score = 0.0
        for module, topics in self.MODULE_TOPICS.items():
            for topic in topics:
                if topic in repo.topics or topic in repo.description.lower():
                    score += 0.15
        return min(1.0, score + 0.1 * (repo.stars / 10000))

    def _match_modules(self, repo: GithubRepo) -> list[str]:
        """Find which LivingTree modules match a repo's topics."""
        matched = []
        for module, topics in self.MODULE_TOPICS.items():
            for topic in topics:
                if topic in repo.topics or topic.lower() in repo.description.lower():
                    matched.append(module)
                    break
        return matched

    def _infer_pattern(self, repo: GithubRepo, module: str) -> Optional[LearnedPattern]:
        """Infer a code pattern from a repo that's applicable to a LivingTree module."""
        # Module → suggested file mapping
        MODULE_FILES = {
            "treellm": ["treellm/holistic_election.py", "treellm/providers.py"],
            "dna": ["dna/life_engine.py", "dna/life_stage.py"],
            "knowledge": ["knowledge/intelligent_kb.py", "knowledge/knowledge_base.py"],
            "execution": ["execution/orchestrator.py", "execution/task_planner.py"],
            "capability": ["capability/skill_factory.py"],
            "cell": ["cell/trainer.py"],
        }

        files = MODULE_FILES.get(module, [])
        if not files:
            return None

        # Generate a suggested improvement based on repo features
        desc = repo.description.lower()
        suggestion = ""

        if "orchestration" in desc or "multi-agent" in desc:
            suggestion = "Consider graph-based orchestration pattern (ref: {})".format(repo.full_name)
        elif "router" in desc or "routing" in desc:
            suggestion = "Consider cost-aware model routing strategy (ref: {})".format(repo.full_name)
        elif "rag" in desc or "retrieval" in desc:
            suggestion = "Consider hybrid retrieval (dense+sparse) strategy (ref: {})".format(repo.full_name)
        elif "memory" in desc:
            suggestion = "Consider hierarchical memory architecture (ref: {})".format(repo.full_name)

        if not suggestion:
            return None

        return LearnedPattern(
            source="github",
            source_url=f"https://github.com/{repo.full_name}",
            category="pattern",
            title=f"Pattern from {repo.full_name} ({repo.stars}★)",
            description=suggestion,
            applicable_files=files,
            suggested_change=suggestion,
            confidence=repo.relevance_score,
        )

    def _load_cache(self) -> None:
        try:
            if self._cache_file.exists():
                data = json.loads(self._cache_file.read_text("utf-8"))
                self._learned = [LearnedPattern(**p) for p in data.get("patterns", [])]
        except Exception:
            pass

    def _save_cache(self) -> None:
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "patterns": [
                    {"source": p.source, "source_url": p.source_url, "category": p.category,
                     "title": p.title, "description": p.description, "code_snippet": p.code_snippet,
                     "confidence": p.confidence, "applicable_files": p.applicable_files,
                     "suggested_change": p.suggested_change}
                    for p in self._learned[-50:]  # Keep last 50
                ]
            }
            self._cache_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
# Part 2: arXiv Learner
# ═══════════════════════════════════════════════════════

class ArxivLearner:
    """Learn from latest arXiv papers in AI/ML/agents.

    Fetches papers matching LivingTree's domain, extracts key insights,
    and proposes architectural changes based on paper findings.
    """

    # Search queries for arXiv API
    SEARCH_CATEGORIES = [
        ("cs.AI", "artificial intelligence"),
        ("cs.CL", "computation and language"),
        ("cs.MA", "multi-agent systems"),
        ("cs.LG", "machine learning"),
    ]

    # LivingTree capability → arXiv search terms
    DOMAIN_QUERIES = [
        ("agent_framework", "multi-agent LLM orchestration framework autonomous"),
        ("model_routing", "LLM routing model selection cost optimization"),
        ("knowledge_retrieval", "RAG retrieval augmented generation knowledge graph"),
        ("skill_learning", "autonomous skill discovery self-improving agent"),
        ("context_management", "context window optimization prompt compression caching"),
        ("reasoning", "chain of thought reasoning planning verification"),
        ("memory", "hierarchical memory episodic semantic agent memory"),
    ]

    def __init__(self):
        self._learned: list[LearnedPattern] = []
        self._papers: list[ArxivPaper] = []
        self._cache_file = Path(".livingtree/arxiv_learned.json")
        self._paper_cache = Path(".livingtree/arxiv_papers.json")
        self._load_cache()

    def search_recent_papers(self, max_results: int = 50) -> list[ArxivPaper]:
        """Search arXiv for recent papers relevant to LivingTree.

        Production: uses arxiv API (http://export.arxiv.org/api/query).
        Here: heuristic search with known high-relevance papers.
        """
        papers = []

        # Known high-relevance papers (Feb-May 2026) not yet applied
        KNOWN_PAPERS = [
            ArxivPaper("2603.13256", "REDEREF: Probabilistic Multi-Agent Control",
                       "Thompson sampling delegation, reflection-driven re-routing, 28% token reduction",
                       categories=["cs.AI", "cs.MA"], relevance_score=0.95),
            ArxivPaper("2602.01848", "ROMA: Recursive Open Meta-Agent Framework",
                       "Recursive task decomposition with Atomizer/Planner/Executor/Aggregator roles",
                       categories=["cs.AI"], relevance_score=0.90),
            ArxivPaper("2604.17091", "GenericAgent: Context Density Maximization",
                       "Minimal tools + hierarchical memory + self-evolution + context compression",
                       categories=["cs.AI"], relevance_score=0.88),
            ArxivPaper("2602.16873", "AdaptOrch: Task-Adaptive Multi-Agent Orchestration",
                       "O(|V|+|E|) topology routing, parallel/sequential/hierarchical/hybrid selection",
                       categories=["cs.AI", "cs.MA"], relevance_score=0.85),
            ArxivPaper("2603.09716", "AutoAgent: Evolving Cognition + Elastic Memory",
                       "Self-evolving multi-agent with structured prompt-level cognition",
                       categories=["cs.AI"], relevance_score=0.82),
            ArxivPaper("2603.22455", "SkillRouter: Skill Routing at Scale",
                       "1.2B full-text skill routing, 80K skills, 74% Hit@1",
                       categories=["cs.AI", "cs.CL"], relevance_score=0.80),
            ArxivPaper("2603.12933", "AMRO-S: Ant Colony Multi-Agent Routing",
                       "Pheromone-based routing, quality-gated async updates, interpretable traces",
                       categories=["cs.AI", "cs.MA"], relevance_score=0.78),
            ArxivPaper("2603.24639", "ERL: Experiential Reflective Learning",
                       "Heuristic extraction from single-attempt trajectories, 7.8% improvement",
                       categories=["cs.AI"], relevance_score=0.75),
            ArxivPaper("2601.02695", "EvoRoute: Self-Evolving Model Routing",
                       "Pareto-optimal LLM selection, 80% cost reduction, 70% latency reduction",
                       categories=["cs.AI"], relevance_score=0.72),
            ArxivPaper("2604.05149", "EvolveRouter: Co-Evolving Routing + Prompt",
                       "Closed-loop refinement: router diagnostics guide agent improvement",
                       categories=["cs.AI"], relevance_score=0.70),
        ]

        for paper in KNOWN_PAPERS:
            # Score relevance to LivingTree modules
            paper.relevance_score = self._paper_relevance(paper)
            if paper.relevance_score > 0.5:
                papers.append(paper)

        self._papers = sorted(papers, key=lambda x: -x.relevance_score)[:max_results]
        self._save_papers()
        return self._papers

    def extract_insights(self, papers: list[ArxivPaper] = None) -> list[LearnedPattern]:
        """Extract actionable insights from papers → implementable code changes.

        Maps paper findings → specific LivingTree modules → concrete suggestions.
        """
        papers = papers or self._papers
        patterns = []

        for paper in papers[:15]:
            insights = self._extract_insights(paper)
            for insight in insights:
                patterns.append(
                    LearnedPattern(
                        source="arxiv",
                        source_url=f"https://arxiv.org/abs/{paper.arxiv_id}",
                        category="architecture",
                        title=f"[{paper.arxiv_id}] {paper.title[:80]}",
                        description=insight,
                        applicable_files=self._find_applicable_files(insight),
                        suggested_change=insight,
                        confidence=paper.relevance_score,
                    )
                )

        self._learned.extend(patterns)
        self._save_cache()
        return patterns

    def propose_changes(self, patterns: list[LearnedPattern] = None) -> list[dict]:
        """Propose concrete code changes based on paper insights.

        Returns: list of {file, line_hint, suggestion, paper_url} proposals.
        """
        patterns = patterns or self._learned
        proposals = []

        for pattern in patterns[-20:]:
            for file_path in pattern.applicable_files:
                proposals.append({
                    "file": file_path,
                    "suggestion": pattern.suggested_change,
                    "paper": pattern.source_url,
                    "confidence": pattern.confidence,
                    "category": pattern.category,
                })

        return proposals

    # ── Internal ──

    def _paper_relevance(self, paper: ArxivPaper) -> float:
        """Score how relevant a paper is to LivingTree."""
        abstract_lower = (paper.abstract + " " + paper.title).lower()
        score = 0.0

        keywords = {
            "agent": 0.1, "multi-agent": 0.15, "orchestrat": 0.1,
            "routing": 0.1, "router": 0.1, "model selection": 0.1,
            "rag": 0.1, "retrieval": 0.08, "knowledge": 0.08,
            "self-improv": 0.12, "self-evolv": 0.12, "autonomous": 0.1,
            "memory": 0.08, "context": 0.08, "planning": 0.08,
            "skill": 0.1, "tool": 0.08, "reasoning": 0.08,
        }

        for kw, weight in keywords.items():
            if kw in abstract_lower:
                score += weight

        return min(1.0, score)

    def _extract_insights(self, paper: ArxivPaper) -> list[str]:
        """Extract actionable insights from a paper's abstract."""
        insights = []
        abstract_lower = paper.abstract.lower()

        # Pattern matching against known architectural patterns
        if "thompson sampling" in abstract_lower or "belief-guided" in abstract_lower:
            insights.append(
                f"Consider probabilistic agent selection via Thompson sampling "
                f"(ref: {paper.arxiv_id}) — reduces token usage 28%"
            )
        if "recursive" in abstract_lower and "decompos" in abstract_lower:
            insights.append(
                f"Consider recursive task decomposition with Atomizer→Planner→Executor→Aggregator "
                f"(ref: {paper.arxiv_id}) — enables parallel subtask execution"
            )
        if "context" in abstract_lower and ("density" in abstract_lower or "compress" in abstract_lower):
            insights.append(
                f"Consider context density maximization — minimal tools + hierarchical memory + "
                f"self-evolution + truncation (ref: {paper.arxiv_id})"
            )
        if "topology" in abstract_lower or "dag" in abstract_lower.lower():
            insights.append(
                f"Consider task-adaptive topology routing (parallel/sequential/hierarchical/hybrid) "
                f"based on task DAG structure (ref: {paper.arxiv_id})"
            )
        if "cognit" in abstract_lower and "evolv" in abstract_lower:
            insights.append(
                f"Consider cognitive evolution loop — track tool confidence, peer reliability, "
                f"task pattern success rates (ref: {paper.arxiv_id})"
            )
        if "pheromone" in abstract_lower or "ant colony" in abstract_lower:
            insights.append(
                f"Consider ant-colony optimization for multi-agent routing — "
                f"quality-gated async updates (ref: {paper.arxiv_id})"
            )

        if not insights:
            insights.append(
                f"Review findings from {paper.title[:60]} ({paper.arxiv_id}) "
                f"for potential {paper.categories[0] if paper.categories else 'AI'} improvements"
            )

        return insights

    def _find_applicable_files(self, insight: str) -> list[str]:
        """Map insight keywords to LivingTree files."""
        insight_lower = insight.lower()
        files = []

        if "routing" in insight_lower or "selection" in insight_lower:
            files.append("treellm/holistic_election.py")
        if "decompos" in insight_lower or "planning" in insight_lower:
            files.append("execution/task_planner.py")
        if "context" in insight_lower or "memory" in insight_lower:
            files.extend(["dna/life_stage.py", "knowledge/intelligent_kb.py"])
        if "skill" in insight_lower or "tool" in insight_lower:
            files.append("capability/skill_factory.py")
        if "evolution" in insight_lower or "cognit" in insight_lower:
            files.extend(["dna/life_engine.py", "dna/evolution_driver.py"])
        if "token" in insight_lower or "budget" in insight_lower:
            files.append("api/token_accountant.py")

        # Default: most general files
        if not files:
            files = ["dna/life_engine.py", "execution/orchestrator.py"]

        return files

    def _load_cache(self) -> None:
        try:
            if self._cache_file.exists():
                data = json.loads(self._cache_file.read_text("utf-8"))
                self._learned = [LearnedPattern(**p) for p in data.get("patterns", [])]
        except Exception:
            pass

    def _save_cache(self) -> None:
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "patterns": [
                    {"source": p.source, "source_url": p.source_url, "category": p.category,
                     "title": p.title, "description": p.description, "confidence": p.confidence,
                     "applicable_files": p.applicable_files, "suggested_change": p.suggested_change}
                    for p in self._learned[-50:]
                ]
            }
            self._cache_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        except Exception:
            pass

    def _save_papers(self) -> None:
        try:
            self._paper_cache.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "papers": [
                    {
                        "arxiv_id": p.arxiv_id, "title": p.title, "abstract": p.abstract,
                        "authors": p.authors, "published": p.published,
                        "key_insights": p.key_insights, "relevance_score": p.relevance_score,
                    }
                    for p in self._papers[-100:]
                ]
            }
            self._paper_cache.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
# Part 3: Nature Learner
# ═══════════════════════════════════════════════════════

class NatureLearner:
    """Learn from Nature.com papers across relevant journals.

    Searches Nature, Nature Machine Intelligence, Scientific Reports,
    npj Artificial Intelligence, Nature Communications, and Communications
    Chemistry for papers relevant to LivingTree's architecture.

    Extracts: architectural insights, experimental validations,
    collective intelligence patterns, heterogeneous system designs.
    """

    # Nature.com journals to search (via their APIs)
    JOURNALS = [
        ("nature", "Nature"),
        ("natmachintell", "Nature Machine Intelligence"),
        ("srep", "Scientific Reports"),
        ("npjai", "npj Artificial Intelligence"),
        ("ncomms", "Nature Communications"),
        ("npjdigitalmed", "npj Digital Medicine"),
    ]

    # LivingTree-relevant search queries for Nature papers
    DOMAIN_QUERIES = [
        ("multi_agent_orchestration",
         "multi-agent LLM orchestration collective intelligence routing"),
        ("reasoning_depth",
         "chain-of-thought reasoning self-improvement reflection LLM"),
        ("collective_intelligence",
         "swarm intelligence stigmergy collective behavior emergence"),
        ("heterogeneous_computing",
         "heterogeneous GPU kernel disaggregation resource allocation scheduling"),
        ("agent_coordination",
         "autonomous agent coordination modular planning memory"),
    ]

    # Mapping: Nature domain → LivingTree module
    MODULE_MAPPING = {
        "multi_agent_orchestration": ["treellm/core.py", "treellm/holistic_election.py"],
        "reasoning_depth": ["treellm/deep_probe.py", "treellm/adversarial_selfplay.py"],
        "collective_intelligence": ["treellm/fluid_collective.py", "treellm/synapse_aggregator.py"],
        "heterogeneous_computing": ["treellm/reasoning_dependency_graph.py", "treellm/strategic_orchestrator.py"],
        "agent_coordination": ["treellm/competitive_eliminator.py", "dna/external_learner.py"],
    }

    def __init__(self):
        self._learned: list[LearnedPattern] = []
        self._papers: list[ArxivPaper] = []  # Reuse ArxivPaper type for Nature papers
        self._cache_file = Path(".livingtree/nature_learned.json")
        self._paper_cache = Path(".livingtree/nature_papers.json")
        self._load_cache()

    def search_recent_papers(self, max_results: int = 30) -> list[ArxivPaper]:
        """Search Nature.com journals for recent relevant papers.

        Tries Semantic Scholar API first (free, no key needed), falls back
        to heuristic known-paper list. Production can add Nature API key.
        """
        papers = []

        # Try Semantic Scholar API first
        api_papers = self._search_semantic_scholar(max_results)
        if api_papers:
            papers.extend(api_papers)
            logger.info(
                f"NatureLearner: Semantic Scholar returned {len(api_papers)} papers"
            )

        # Fill with heuristics if API returned too few
        if len(papers) < 5:
            for domain, query in self.DOMAIN_QUERIES:
                related = self._heuristic_search(query, domain)
                papers.extend(related)

        seen = set()
        unique = []
        for p in sorted(papers, key=lambda x: -x.relevance_score):
            if p.title not in seen:
                seen.add(p.title)
                unique.append(p)

        self._papers = unique[:max_results]
        self._save_papers()
        logger.info(
            f"NatureLearner: found {len(self._papers)} relevant papers "
            f"across Nature journals"
        )
        return self._papers

    def _search_semantic_scholar(self, max_results: int = 20) -> list[ArxivPaper]:
        """Search Semantic Scholar API for recent relevant papers.

        Semantic Scholar is free, no API key required. Returns up to max_results
        papers matching LivingTree's domain queries across multiple fields.
        """
        papers: list[ArxivPaper] = []
        search_queries = [
            "multi-agent LLM orchestration collective intelligence",
            "large language model reasoning chain-of-thought self-improvement",
            "swarm intelligence stigmergy coordination emergence",
        ]

        try:
            import aiohttp
            import asyncio

            async def _fetch():
                results = []
                async with aiohttp.ClientSession() as session:
                    for query in search_queries[:2]:  # Limit to 2 queries
                        url = (
                            "https://api.semanticscholar.org/graph/v1/paper/search"
                            f"?query={query}&limit={max_results // 2}"
                            "&fields=title,authors,year,journal,externalIds"
                        )
                        try:
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    for p in data.get("data", []):
                                        ext_ids = p.get("externalIds", {})
                                        doi = ext_ids.get("DOI", "")
                                        arxiv_id = ext_ids.get("ArXiv", "")
                                        paper_id = arxiv_id or doi or str(p.get("paperId", ""))

                                        # Filter: only keep Nature-family journals or highly relevant
                                        journal = (p.get("journal") or {}).get("name", "")
                                        journal_lower = journal.lower()
                                        nature_journals = ["nature", "sci rep", "nat commun",
                                                          "nat mach", "npj", "scientific reports"]
                                        is_nature = any(nj in journal_lower for nj in nature_journals)

                                        if is_nature or len(results) < 5:
                                            results.append(ArxivPaper(
                                                arxiv_id=f"ss:{paper_id[:30]}",
                                                title=p.get("title", ""),
                                                authors=[a.get("name", "") for a in (p.get("authors") or [])],
                                                categories=["semantic_scholar"],
                                                published=f"{journal} ({p.get('year', '')})",
                                                relevance_score=0.6 if is_nature else 0.4,
                                                key_insights=[],
                                            ))
                        except Exception:
                            continue
                return results

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In async context, use create_task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _fetch())
                    papers = future.result(timeout=15)
            else:
                papers = asyncio.run(_fetch())

        except ImportError:
            logger.debug("NatureLearner: aiohttp not available for Semantic Scholar API")
        except Exception as e:
            logger.debug(f"NatureLearner Semantic Scholar: {e}")

        return papers[:max_results]

    def _heuristic_search(self, query: str, domain: str) -> list[ArxivPaper]:
        """Heuristic paper discovery from known Nature publications.

        Maps query terms to known high-relevance Nature papers.
        In production: calls Nature API or Semantic Scholar API.
        """
        known_papers: dict[str, list[dict]] = {
            "multi_agent_orchestration": [
                {"title": "Orchestrated multi agents sustain accuracy under clinical-scale workloads",
                 "authors": ["Klang", "Omar", "Raut"], "journal": "npj Health Systems",
                 "year": "2026", "insight": "Multi-agent orchestrator preserves accuracy with 65x fewer tokens"},
                {"title": "Multi-agent AI systems need transparency",
                 "authors": ["Nature Machine Intelligence Editorial"], "journal": "Nat Mach Intell",
                 "year": "2026", "insight": "Framework for evaluating multi-agent transparency and cost"},
                {"title": "Evaluating routing stability and coordination in swarm-based multi-agent TOD",
                 "authors": [], "journal": "Scientific Reports",
                 "year": "2026", "insight": "Coordination metrics: delegation quality, coverage, loop rate, recovery"},
            ],
            "reasoning_depth": [
                {"title": "PRefLexOR: preference-based recursive language modeling for reasoning",
                 "authors": ["Buehler"], "journal": "npj Artificial Intelligence",
                 "year": "2025", "insight": "Recursive self-reflection via reflect tags improves reasoning depth"},
                {"title": "DR-CoT: dynamic recursive chain of thought with meta reasoning",
                 "authors": [], "journal": "Scientific Reports",
                 "year": "2025", "insight": "Voting mechanism with context truncation for ensemble reasoning"},
                {"title": "Use large language model to enhance reasoning of another",
                 "authors": [], "journal": "Scientific Reports",
                 "year": "2026", "insight": "GRPO with structural reward for reasoning improvement"},
            ],
            "collective_intelligence": [
                {"title": "Fluid thinking about collective intelligence",
                 "authors": ["Werfel"], "journal": "Nat Mach Intell",
                 "year": "2026", "insight": "Static vs fluid topologies; mobility as alternative to multiplicity"},
                {"title": "Collective intelligence for AI-assisted chemical synthesis",
                 "authors": ["Li", "Sarkar", "Lu"], "journal": "Nature",
                 "year": "2026", "insight": "2,498 Voronoi-clustered experts for MOSAIC framework"},
                {"title": "Unraveling emergence of collective behavior in networks of cognitive agents",
                 "authors": ["Zomer", "De Domenico"], "journal": "npj Artificial Intelligence",
                 "year": "2026", "insight": "Network topology controls exploration-exploitation in LLM swarms"},
                {"title": "A collective intelligence model for swarm robotics applications",
                 "authors": ["Nitti", "de Tullio", "Federico"], "journal": "Nat Commun",
                 "year": "2025", "insight": "Swarm Cooperation Model for limited-size collectives"},
            ],
            "heterogeneous_computing": [
                {"title": "Tessera: Unlocking Heterogeneous GPUs through Kernel-Granularity Disaggregation",
                 "authors": ["Hu", "Qin", "Wang"], "journal": "arXiv (cs.DC)",
                 "year": "2026", "insight": "Kernel-level disaggregation; heterogeneous pair exceeds homogeneous"},
            ],
            "agent_coordination": [
                {"title": "Modular Agentic Planner for planning with LLMs",
                 "authors": [], "journal": "Nature Communications",
                 "year": "2025", "insight": "Brain-inspired modules: error monitoring, state prediction, task decomposition"},
                {"title": "MCP-SIM: memory-coordinated multi-agent simulation framework",
                 "authors": [], "journal": "npj Artificial Intelligence",
                 "year": "2026", "insight": "Shared persistent memory for 6 specialized simulation agents"},
                {"title": "A self-correcting multi-agent LLM framework",
                 "authors": [], "journal": "npj Artificial Intelligence",
                 "year": "2026", "insight": "Planning-acting-reflecting-revising cycles with memory coordination"},
            ],
        }

        result = []
        for paper in known_papers.get(domain, []):
            title = paper.get("title", "")
            # Compute relevance based on query-term overlap
            query_terms = set(query.lower().split())
            title_terms = set(title.lower().split())
            overlap = len(query_terms & title_terms) / max(len(query_terms), 1)
            relevance = min(1.0, 0.4 + overlap * 0.6)

            result.append(ArxivPaper(
                arxiv_id=f"nature:{paper.get('journal','')}:{paper.get('year','')}",
                title=title,
                authors=paper.get("authors", []),
                categories=[domain],
                published=f"{paper.get('journal','')} ({paper.get('year','')})",
                relevance_score=round(relevance, 3),
                key_insights=[paper.get("insight", "")] if paper.get("insight") else [],
            ))
        return result

    def extract_patterns(self, papers: list[ArxivPaper] | None = None) -> list[LearnedPattern]:
        """Extract actionable patterns from Nature papers."""
        papers = papers or self._papers
        patterns = []

        for paper in papers:
            if not paper.key_insights:
                continue

            # Determine which LivingTree module this maps to
            target_files = []
            for domain_key, files in self.MODULE_MAPPING.items():
                if any(domain_key in cat for cat in paper.categories):
                    target_files = files
                    break

            if not target_files:
                target_files = ["treellm/"]  # Default to treellm

            for insight in paper.key_insights:
                pattern = LearnedPattern(
                    source="nature",
                    source_url=f"https://www.nature.com/search?q={paper.title[:50]}",
                    category="architecture",
                    title=f"[Nature] {paper.title[:80]}",
                    description=insight,
                    confidence=paper.relevance_score,
                    applicable_files=target_files,
                    suggested_change=f"Consider insight from {paper.published}: {insight}",
                )
                patterns.append(pattern)

        self._learned = patterns
        self._save_cache()
        logger.info(f"NatureLearner: extracted {len(patterns)} patterns")
        return patterns

    def _load_cache(self) -> None:
        try:
            if self._cache_file.exists():
                data = json.loads(self._cache_file.read_text("utf-8"))
                self._learned = [LearnedPattern(**p) for p in data.get("patterns", [])]
        except Exception:
            pass

    def _save_cache(self) -> None:
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "patterns": [
                    {"source": p.source, "source_url": p.source_url, "category": p.category,
                     "title": p.title, "description": p.description, "confidence": p.confidence,
                     "applicable_files": p.applicable_files, "suggested_change": p.suggested_change}
                    for p in self._learned[-50:]
                ]
            }
            self._cache_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        except Exception:
            pass

    def _save_papers(self) -> None:
        try:
            self._paper_cache.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "papers": [
                    {
                        "arxiv_id": p.arxiv_id, "title": p.title,
                        "authors": p.authors, "published": p.published,
                        "key_insights": p.key_insights, "relevance_score": p.relevance_score,
                    }
                    for p in self._papers[-50:]
                ]
            }
            self._paper_cache.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
# Part 4: External Evolution Driver (orchestrator)
# ═══════════════════════════════════════════════════════
# Part 3: Unified External Learner
# ═══════════════════════════════════════════════════════

class ExternalEvolutionDriver:
    """Orchestrates GitHub + arXiv learning → feeds into self-evolution pipeline.

    Usage:
        driver = ExternalEvolutionDriver()
        await driver.run_cycle()  # One learning cycle
        driver.feed_to_evolution()  # Push suggestions to self_evolution.py
    """

    def __init__(self):
        self.github = GitHubLearner()
        self.arxiv = ArxivLearner()
        self.nature = NatureLearner()
        self._all_patterns: list[LearnedPattern] = []
        self._last_run = 0.0

    async def run_cycle(self) -> dict:
        """Run one complete external learning cycle.

        Returns: {github_patterns, arxiv_patterns, nature_patterns, total, proposals}
        """
        self._last_run = time.time()
        results = {}

        # GitHub: search related repos → extract patterns
        try:
            repos = self.github.search_related_repos()
            gh_patterns = self.github.extract_patterns(repos)
            results["github_repos"] = len(repos)
            results["github_patterns"] = len(gh_patterns)
            self._all_patterns.extend(gh_patterns)
            logger.info(f"GitHubLearner: {len(repos)} repos → {len(gh_patterns)} patterns")
        except Exception as e:
            logger.warning(f"GitHubLearner: {e}")
            results["github_error"] = str(e)[:100]

        # arXiv: search papers → extract insights → propose changes
        try:
            papers = self.arxiv.search_recent_papers()
            arxiv_patterns = self.arxiv.extract_insights(papers)
            results["arxiv_papers"] = len(papers)
            results["arxiv_patterns"] = len(arxiv_patterns)
            self._all_patterns.extend(arxiv_patterns)
            logger.info(f"ArxivLearner: {len(papers)} papers → {len(arxiv_patterns)} insights")
        except Exception as e:
            logger.warning(f"ArxivLearner: {e}")
            results["arxiv_error"] = str(e)[:100]

        # Nature: search papers → extract patterns
        try:
            nature_papers = self.nature.search_recent_papers()
            nature_patterns = self.nature.extract_patterns(nature_papers)
            results["nature_papers"] = len(nature_papers)
            results["nature_patterns"] = len(nature_patterns)
            self._all_patterns.extend(nature_patterns)
            logger.info(f"NatureLearner: {len(nature_papers)} papers → {len(nature_patterns)} patterns")
        except Exception as e:
            logger.warning(f"NatureLearner: {e}")
            results["nature_error"] = str(e)[:100]

        results["total_patterns"] = len(self._all_patterns)
        results["proposals"] = self.arxiv.propose_changes(self._all_patterns)

        # Persist proposals for cross-process consumption by improve --auto
        self._save_proposals()

        return results

    def _save_proposals(self):
        try:
            proposals_file = Path(".livingtree/learned_proposals.json")
            proposals_file.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "source": p.source, "source_url": p.source_url,
                    "category": p.category, "title": p.title,
                    "description": p.description,
                    "applicable_files": p.applicable_files,
                    "suggested_change": p.suggested_change,
                    "confidence": p.confidence,
                    "timestamp": p.timestamp,
                }
                for p in self._all_patterns[-50:]
            ]
            proposals_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            logger.debug(f"ExternalEvolutionDriver: saved {len(data)} proposals")
        except Exception as e:
            logger.debug(f"ExternalEvolutionDriver save proposals: {e}")

    def feed_to_evolution(self) -> list[dict]:
        """Feed learned patterns into the self-evolution mutation pipeline.

        Returns proposals ready for self_evolution.py to process.
        """
        proposals = []
        for pattern in self._all_patterns[-30:]:
            if pattern.confidence < 0.5:
                continue
            proposals.append({
                "source": pattern.source,
                "url": pattern.source_url,
                "category": pattern.category,
                "files": pattern.applicable_files,
                "change": pattern.suggested_change,
                "confidence": pattern.confidence,
            })
        return proposals

    @property
    def stats(self) -> dict:
        return {
            "total_patterns": len(self._all_patterns),
            "last_run": self._last_run,
            "github_learned": sum(1 for p in self._all_patterns if p.source == "github"),
            "arxiv_learned": sum(1 for p in self._all_patterns if p.source == "arxiv"),
            "nature_learned": sum(1 for p in self._all_patterns if p.source == "nature"),
        }

    # ── Auto-Fetch Loop (OpenHuman-inspired 20-minute cycle) ────

    async def auto_fetch_loop(self, interval_minutes: int = 20,
                              max_iterations: int = 0) -> None:
        """Background loop: automatically fetch new learning content.

        From OpenHuman: "every twenty minutes the core walks each active
        connection and pulls fresh data into the memory tree."

        Runs run_cycle() at the specified interval. Set max_iterations=0
        for infinite loop (suitable for daemon mode).
        """
        import asyncio
        iteration = 0
        logger.info(
            f"ExternalEvolutionDriver: auto-fetch started "
            f"(interval={interval_minutes}min)"
        )
        while max_iterations == 0 or iteration < max_iterations:
            try:
                results = await self.run_cycle()
                logger.info(
                    f"Auto-fetch cycle {iteration + 1}: "
                    f"github={results.get('github_patterns', 0)}, "
                    f"arxiv={results.get('arxiv_patterns', 0)}, "
                    f"nature={results.get('nature_patterns', 0)}"
                )
                # Feed into evolution pipeline
                self.feed_to_evolution()
                # Deposit top patterns into FluidCollective memory tree
                try:
                    from ..treellm.fluid_collective import get_fluid_collective, TraceType
                    fc = get_fluid_collective()
                    for p in self._all_patterns[-5:]:
                        if p.confidence > 0.5:
                            fc.deposit(
                                model=f"learner:{p.source}",
                                content=p.description,
                                trace_type=TraceType.INSIGHT,
                                domain=p.category,
                                confidence=p.confidence,
                            )
                except ImportError:
                    pass
            except Exception as e:
                logger.warning(f"Auto-fetch cycle error: {e}")

            iteration += 1
            if max_iterations == 0 or iteration < max_iterations:
                await asyncio.sleep(interval_minutes * 60)

        logger.info("ExternalEvolutionDriver: auto-fetch stopped")


# ── Singleton ──

_driver: Optional[ExternalEvolutionDriver] = None


def get_external_driver() -> ExternalEvolutionDriver:
    global _driver
    if _driver is None:
        _driver = ExternalEvolutionDriver()
    return _driver
