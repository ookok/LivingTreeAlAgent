"""IntegrationHub — progressive initialization for instant TUI boot."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

import aiohttp
from loguru import logger

from ..config import LTAIConfig, get_config
from ..observability import setup_observability


class IntegrationHub:
    """Progressive boot: minimal __init__ for instant UI, heavy init deferred.

    lazy=True skips ModelRegistry fetch + LocalScanner scan + package manager check.
    These fire in background after UI is visible.
    """

    def __init__(self, config: Optional[LTAIConfig] = None, lazy: bool = False):
        self.config = config or get_config()
        self.obs = setup_observability(self.config)
        self._session = None
        self._started = False
        self._ready_event = asyncio.Event()
        self._lazy = lazy
        self.world = None
        self.engine = None
        self.cache_optimizer = None
        self.lsp_manager = None
        self.sub_agent_roles = None
        self.struct_memory = None
        # RouteMoA: embedding scorer (initialized at boot)
        self.embedding_scorer = None
        # RouteMoA: layered routing by default
        self._use_layered_routing = True
        # MessageGateway: multi-platform notifications
        self.message_gateway = None
        # Scinet: smart proxy for overseas acceleration
        self.scinet = None
        # UnifiedNotifier: adaptive multi-channel dispatcher
        self.unified_notifier = None

    @property
    def consciousness(self):
        """Delegate to world.consciousness for convenience."""
        return self.world.consciousness if self.world else None

    async def wait_ready(self, timeout: float = 30.0) -> bool:
        """Wait for hub initialization to complete."""
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return self._ready_event.is_set()
        except asyncio.TimeoutError:
            return False

    def _lazy_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def start(self) -> None:
        """Phase 2: Full initialization — heavy sync work in executor, async after."""
        if self._started:
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._init_sync)
        await self._init_async()

    def _init_sync(self) -> None:
        """All synchronous heavy work — runs in thread executor."""
        from ..dna import LivingWorld, DualModelConsciousness, SafetyGuard, LifeEngine
        from ..cell import CellRegistry, CellTrainer, TrainingConfig, Distillation, ExpertConfig
        from ..cell import Mitosis, Phage, Regen, SwiftDrillTrainer
        from ..knowledge import KnowledgeBase, VectorStore, KnowledgeGraph, FormatDiscovery, GapDetector
        from ..capability import SkillFactory, ToolMarket, DocEngine, CodeEngine, MaterialCollector
        from ..capability import CodeGraph, ASTParser
        from ..network import Node, Discovery, NATTraverser, Reputation, EncryptedChannel
        from ..execution import TaskPlanner, Orchestrator, SelfHealer
        from ..execution import MultiAgentQualityChecker
        from ..execution import HumanInTheLoop, TaskCheckpoint, CostAware

        # Create world skeleton
        self.world = LivingWorld(
            consciousness=DualModelConsciousness(
                flash_model=self.config.model.flash_model,
                pro_model=self.config.model.pro_model,
                api_key=self.config.model.deepseek_api_key,
                base_url=self.config.model.deepseek_base_url,
                thinking_enabled=self.config.model.pro_thinking_enabled,
                longcat_api_key=self.config.model.longcat_api_key,
                longcat_base_url=self.config.model.longcat_base_url,
                longcat_flash_model=self.config.model.longcat_flash_model,
                longcat_flash_temperature=self.config.model.longcat_flash_temperature,
                longcat_flash_max_tokens=self.config.model.longcat_flash_max_tokens,
                longcat_models=self.config.model.longcat_models,
                longcat_chat_model=self.config.model.longcat_chat_model,
                xiaomi_api_key=self.config.model.xiaomi_api_key,
                xiaomi_base_url=self.config.model.xiaomi_base_url,
                xiaomi_flash_model=self.config.model.xiaomi_flash_model,
                xiaomi_pro_model=self.config.model.xiaomi_pro_model,
                aliyun_api_key=self.config.model.aliyun_api_key,
                aliyun_base_url=self.config.model.aliyun_base_url,
                aliyun_flash_model=self.config.model.aliyun_flash_model,
                aliyun_pro_model=self.config.model.aliyun_pro_model,
                zhipu_api_key=self.config.model.zhipu_api_key,
                zhipu_base_url=self.config.model.zhipu_base_url,
                zhipu_flash_model=self.config.model.zhipu_flash_model,
                zhipu_pro_model=self.config.model.zhipu_pro_model,
                dmxapi_api_key=self.config.model.dmxapi_api_key,
                dmxapi_base_url=self.config.model.dmxapi_base_url,
                dmxapi_default_model=self.config.model.dmxapi_default_model,
                spark_api_key=self.config.model.spark_api_key,
                spark_base_url=self.config.model.spark_base_url,
                spark_default_model=self.config.model.spark_default_model,
                siliconflow_api_key=self.config.model.siliconflow_api_key,
                siliconflow_base_url=self.config.model.siliconflow_base_url,
                siliconflow_flash_model=self.config.model.siliconflow_flash_model,
                siliconflow_default_model=self.config.model.siliconflow_default_model,
                siliconflow_pro_model=self.config.model.siliconflow_pro_model,
                siliconflow_reasoning_model=self.config.model.siliconflow_reasoning_model,
                siliconflow_small_model=self.config.model.siliconflow_small_model,
                mofang_api_key=self.config.model.mofang_api_key,
                mofang_base_url=self.config.model.mofang_base_url,
                mofang_flash_model=self.config.model.mofang_flash_model,
                mofang_default_model=self.config.model.mofang_default_model,
                mofang_pro_model=self.config.model.mofang_pro_model,
                mofang_reasoning_model=self.config.model.mofang_reasoning_model,
                mofang_small_model=self.config.model.mofang_small_model,
                nvidia_api_key=self.config.model.nvidia_api_key,
                nvidia_base_url=self.config.model.nvidia_base_url,
                nvidia_default_model=self.config.model.nvidia_default_model,
            ),
            safety=SafetyGuard(workspace=str(Path.cwd())),
        )
        self.world.safety.sandbox.audit = self.world.safety.audit

        logger.info(f"🌳 LivingTree v{self.config.version} booting")
        self.world.wire(
            cell_registry=CellRegistry(),
            cell_trainer=CellTrainer(config=TrainingConfig(
                lora_r=self.config.cell.lora_r, lora_alpha=self.config.cell.lora_alpha,
                lora_dropout=self.config.cell.lora_dropout, learning_rate=self.config.cell.learning_rate,
            )),
            distillation=Distillation(),
            expert_config=ExpertConfig(model=self.config.model.pro_model, api_key=self.config.model.deepseek_api_key),
            mitosis=Mitosis(), phage=Phage(), regen=Regen(),
            drill=SwiftDrillTrainer(modelscope_token=self.config.model.deepseek_api_key),
            knowledge_base=KnowledgeBase(), vector_store=VectorStore(),
            knowledge_graph=KnowledgeGraph(), format_discovery=FormatDiscovery(),
            gap_detector=GapDetector(),
            skill_factory=SkillFactory(), tool_market=ToolMarket(),
            doc_engine=DocEngine(), code_engine=CodeEngine(consciousness=self.world.consciousness),
            material_collector=MaterialCollector(),
            node=Node(name=self.config.network.node_name, capabilities=[
                "chat", "code", "documents", "analysis", "eia", "emergency",
            ]),
            discovery=Discovery(), nat_traverser=NATTraverser(),
            reputation=Reputation(decay_interval=self.config.network.reputation_decay),
            encrypted_channel=EncryptedChannel(node_id="", shared_secret=self.config.network.shared_secret),
            task_planner=TaskPlanner(max_depth=self.config.execution.plan_depth),
            orchestrator=Orchestrator(
                max_agents=self.config.execution.orchestrator_max_agents,
                max_parallel=self.config.execution.max_parallel_tasks,
            ),
            self_healer=SelfHealer(check_interval=self.config.execution.heal_check_interval),
            quality_checker=MultiAgentQualityChecker(consciousness=self.world.consciousness),
            metrics=self.obs.metrics, tracer=self.obs.tracer,
        )

        if self.world.node:
            self.world.encrypted_channel.node_id = self.world.node.info.id

        self.world.code_graph = CodeGraph()
        self.world.ast_parser = ASTParser()
        self.world.knowledge_base.genome = self.world.genome
        self.world.hitl = HumanInTheLoop(default_timeout=300.0)
        self.world.checkpoint = TaskCheckpoint(store_path="./data/checkpoints")
        self.world.cost_aware = CostAware(daily_budget_tokens=1_000_000)

        from ..capability.tool_market import register_seed_tools
        self.world.tool_market.set_world(self.world)
        register_seed_tools(self.world.tool_market)

        from ..knowledge.learning_engine import TemplateLearner, SkillDiscoverer, RoleGenerator
        self.world.template_learner = TemplateLearner(kb=self.world.knowledge_base, distillation=self.world.distillation, expert_config=self.world.expert_config)
        self.world.skill_discoverer = SkillDiscoverer(phage=self.world.phage, skill_factory=self.world.skill_factory, ast_parser=self.world.ast_parser, kb=self.world.knowledge_base)
        self.world.role_generator = RoleGenerator(distillation=self.world.distillation, expert_config=self.world.expert_config, kb=self.world.knowledge_base)

        self.engine = LifeEngine(self.world)

        # ── RouteMoA: Embedding-based model scorer ──
        try:
            from ..treellm.embedding_scorer import get_embedding_scorer
            self.embedding_scorer = get_embedding_scorer()
            logger.info(f"RouteMoA embedding scorer initialized ({len(getattr(self.embedding_scorer, '_profiles', []))} profiles)")
        except Exception as e:
            self.embedding_scorer = None
            logger.warning(f"Embedding scorer skipped: {e}")

        # ── RouteMoA: Mixture of Judges + dynamic weights ──
        try:
            from ..treellm.holistic_election import get_election
            election = get_election()
            # Pre-warm by registering all known providers
            for name in self.world.consciousness._llm.provider_names:
                try:
                    election.get_stats(name)
                except Exception:
                    pass
            logger.info("Holistic election + Mixture of Judges initialized")
        except Exception as e:
            logger.warning(f"Election init skipped: {e}")

        # ── Auto-wire new modules ──
        from ..dna.cache_optimizer import CacheOptimizer
        self.cache_optimizer = CacheOptimizer(
            max_tokens=1_000_000,
            cache_budget=0.85,
        )
        self.world.cache_optimizer = self.cache_optimizer

        from ..execution.side_git import SideGit
        self.side_git = SideGit(workspace_path=str(Path.cwd()))
        self.world.side_git = self.side_git

        from ..execution.session_manager import SessionManager
        self.session_manager = SessionManager()
        self.world.session_manager = self.session_manager

        from ..lsp import LSPManager
        self.lsp_manager = LSPManager(opencode_bin=self.opencode_bin_path())
        self.world.lsp_manager = self.lsp_manager

        from ..execution.sub_agent_roles import SubAgentRoles
        self.sub_agent_roles = SubAgentRoles(consciousness=self.world.consciousness)
        self.world.sub_agent_roles = self.sub_agent_roles

        from ..execution.rlm import RLMRunner
        self.rlm_runner = RLMRunner(consciousness=self.world.consciousness, max_workers=16)
        self.world.rlm_runner = self.rlm_runner

        from ..dna.dual_consciousness import DualModelConsciousness
        self.world.skill_discovery = None
        try:
            from ..capability.skill_discovery import SkillDiscoveryManager
            self.world.skill_discovery = SkillDiscoveryManager()
            self.world.skill_discovery.discover_all()
        except Exception as e:
            logger.warning(f"SkillDiscovery skipped: {e}")

        from ..knowledge.struct_mem import StructMemory
        self.struct_memory = StructMemory(world=self.world)
        self.world.struct_memory = self.struct_memory
        logger.debug("StructMemory initialized")

        from ..capability.extraction_engine import ExtractionEngine
        self.extraction_engine = ExtractionEngine(
            api_key=self.config.model.deepseek_api_key,
            base_url=self.config.model.deepseek_base_url,
            model=self.config.model.flash_model,
        )
        self.world.extraction_engine = self.extraction_engine
        logger.debug("ExtractionEngine (LangExtract) initialized")

        if self.world.doc_engine:
            self.world.doc_engine._extraction_engine = self.extraction_engine

        from ..capability.pipeline_engine import PipelineEngine
        self.world.pipeline_engine = PipelineEngine(
            consciousness=self.world.consciousness,
            extraction_engine=self.extraction_engine,
        )
        logger.debug("PipelineEngine initialized")

        if self.world.doc_engine:
            self.world.doc_engine._pipeline_engine = self.world.pipeline_engine

        from ..capability.multimodal_parser import MultimodalParser
        self.world.multimodal_parser = MultimodalParser(
            api_key=self.config.model.deepseek_api_key,
            base_url=self.config.model.deepseek_base_url,
        )
        if self.world.doc_engine:
            self.world.doc_engine._multimodal_parser = self.world.multimodal_parser

        from ..capability.spark_search import SparkSearch
        search_key = ""
        try:
            from ..config.secrets import get_secret_vault
            search_key = get_secret_vault().get("spark_search_key", "")
        except Exception:
            pass
        self.world.spark_search = SparkSearch(api_password=search_key)
        logger.debug("Spark Search initialized")

        from ..capability.web_reach import WebReach
        self.world.web_reach = WebReach(consciousness=self.world.consciousness)
        logger.debug("WebReach initialized")

        # ── Digital Life Form subsystems ──
        from ..dna.biorhythm import Biorhythm
        self.world.biorhythm = Biorhythm(world=self.world)
        logger.debug("Biorhythm initialized")
        
        from ..dna.adaptive_ui import AdaptiveUI
        self.world.adaptive_ui = AdaptiveUI(world=self.world)
        logger.debug("AdaptiveUI initialized")
        
        from ..dna.anticipatory import Anticipatory
        self.world.anticipatory = Anticipatory()
        logger.debug("Anticipatory initialized")
        
        from ..dna.self_narrative import SelfNarrative
        self.world.self_narrative = SelfNarrative(world=self.world)
        self.world.self_narrative.birth()
        logger.debug("SelfNarrative initialized")
        
        from ..network.collective import CollectiveConsciousness
        self.world.collective = CollectiveConsciousness(world=self.world)
        logger.debug("CollectiveConsciousness initialized")

        # ── SwarmCoordinator: Direct P2P collaboration ──
        from ..network.swarm_coordinator import get_swarm
        self.swarm = get_swarm()
        self.swarm._hub = self
        self.world.swarm = self.swarm
        logger.debug("SwarmCoordinator initialized")

        from ..dna.evolution import SelfEvolvingEngine
        self.world.self_evolving = SelfEvolvingEngine(world=self.world)
        logger.debug("SelfEvolvingEngine initialized")

        from ..dna.multi_agent_debate import MultiAgentDebate
        self.world.debate = MultiAgentDebate(consciousness=self.world.consciousness)
        logger.debug("MultiAgentDebate initialized")

        from ..dna.predictive_world import PredictiveWorldModel
        self.world.predictive = PredictiveWorldModel(world=self.world)
        logger.debug("PredictiveWorldModel initialized")

        # Auto-discover vault-based providers
        try:
            from ..config.secrets import get_secret_vault
            from ..treellm.providers import OpenAILikeProvider
            # RouteMoA: expose embedding scorer import for late binding elsewhere
            from ..treellm.embedding_scorer import get_embedding_scorer
            vault = get_secret_vault()
            # Default base URLs for vault-only providers (no separate config entry)
            _DEFAULT_BASE_URLS = {
                "modelscope": "https://api-inference.modelscope.cn/v1",
                "bailing": "https://api.bailing.cn/v1",
                "stepfun": "https://api.stepfun.com/v1",
                "internlm": "https://api.sensenova.cn/v1",
            }
            vault_providers = [
                ("baidu", "baidu_api_key", "baidu_base_url", "baidu_default_model", "ernie-4.0-turbo-8k"),
                ("siliconflow", "siliconflow_api_key", "siliconflow_base_url", "siliconflow_default_model", "Qwen/Qwen2.5-7B-Instruct"),
                ("mofang", "mofang_api_key", "mofang_base_url", "mofang_default_model", "Qwen/Qwen2.5-7B-Instruct"),
                ("nvidia", "nvidia_api_key", "nvidia_base_url", "nvidia_default_model", "deepseek-ai/deepseek-r1"),
                ("modelscope", "modelscope_api_key", "modelscope_base_url", "modelscope_flash_model", "Qwen/Qwen3-8B"),
                ("bailing", "bailing_api_key", "bailing_base_url", "bailing_flash_model", "Baichuan4-Turbo"),
                ("stepfun", "stepfun_api_key", "stepfun_base_url", "stepfun_flash_model", "step-1-flash"),
                ("internlm", "internlm_api_key", "internlm_base_url", "internlm_flash_model", "internlm2.5-7b-chat"),
            ]
            for name, key_name, url_name, model_name, default_model in vault_providers:
                key = vault.get(key_name, "")
                if key:
                    base_url = vault.get(url_name, "") or _DEFAULT_BASE_URLS.get(name, "")
                    model = vault.get(model_name, "") or default_model
                    self.world.consciousness._llm.add_provider(OpenAILikeProvider(
                        name=name, base_url=base_url, api_key=key, default_model=model,
                    ))
                    self.world.consciousness._paid_models.append(name)
                    logger.info(f"Vault provider: {name} ({model})")
        except Exception as e:
            logger.warning(f"Vault providers: {e}")

        # Register web2api as a local provider (no API key needed)
        try:
            from ..treellm.providers import OpenAILikeProvider
            self.world.consciousness._llm.add_provider(OpenAILikeProvider(
                name="web2api", base_url="http://localhost:5001/v1",
                api_key="web2api-local", default_model="deepseek-chat",
            ))
            logger.info("Web2API provider registered for model election")
        except Exception as e:
            logger.warning(f"Web2API provider: {e}")

        # ── Register provider profiles for embedding scorer ──
        if getattr(self, 'embedding_scorer', None):
            try:
                for name in self.world.consciousness._llm.provider_names:
                    self.embedding_scorer.update_profile(name, "", True)
            except Exception as e:
                logger.debug(f"Embedding scorer profile update skipped: {e}")

        from ..dna.conversation_dna import ConversationDNA
        self.world.conversation_dna = ConversationDNA(world=self.world)
        logger.debug("ConversationDNA initialized")

        from ..capability.self_discovery import SelfDiscovery
        self.world.self_discovery = SelfDiscovery()
        logger.debug("SelfDiscovery initialized")

        from ..knowledge.provenance import ProvenanceTracker
        self.world.provenance = ProvenanceTracker()
        logger.debug("ProvenanceTracker initialized")

        from ..capability.memory_pipeline import MemoryPipeline
        self.world.memory_pipeline = MemoryPipeline(
            struct_memory=self.struct_memory,
            conversation_dna=self.world.conversation_dna,
        )
        logger.debug("MemoryPipeline initialized")

        from ..network.offline_mode import DualMode
        self.world.dual_mode = DualMode(
            node=self.world.node,
            knowledge_base=self.world.knowledge_base,
            struct_memory=self.struct_memory,
        )
        logger.debug("DualMode initialized")

        from ..integration.opencode_bridge import OpenCodeBridge
        self.world.opencode_bridge = OpenCodeBridge()
        self.world.opencode_providers = []
        logger.debug("OpenCode bridge initialized (lazy discovery on first election)")

        from ..dna.life_daemon import LifeDaemon
        self.daemon = LifeDaemon(self.world, interval_minutes=30.0)

        # ──────────────────────────────────────────────
        #  v2.2 New Modules: hard-wired initialization
        # ──────────────────────────────────────────────

        # Context Glossary (mattpocock/skills: domain vocabulary)
        from ..knowledge.context_glossary import GLOSSARY
        self.world.context_glossary = GLOSSARY
        logger.debug("ContextGlossary initialized (25 default terms)")

        # Entity Registry (ontology: unified entity identity)
        from ..core.entity_registry import get_entity_registry
        self.world.entity_registry = get_entity_registry()
        logger.debug("EntityRegistry initialized")

        # Project Scaffold (mattpocock/skills: per-project skills)
        from ..config.project_scaffold import PROJECT_SCAFFOLD
        self.world.project_scaffold = PROJECT_SCAFFOLD
        logger.debug("ProjectScaffold initialized")

        # Prompt Version Manager (Langfuse: template versioning)
        from ..treellm.prompt_versioning import PROMPT_VERSION_MANAGER
        self.world.prompt_version_manager = PROMPT_VERSION_MANAGER
        logger.debug("PromptVersionManager initialized (5 default templates)")

        # Skill Catalog (mattpocock/skills: capability bucket routing)
        from ..capability.skill_buckets import SKILL_CATALOG
        self.world.skill_catalog = SKILL_CATALOG
        logger.debug("SkillCatalog initialized (45 modules, 10 buckets)")

        # Batch Executor (Clibor: FIFO/LIFO task queue)
        from ..execution.batch_executor import create_batch_executor
        self.world.batch_executor = create_batch_executor()
        logger.debug("BatchExecutor initialized")

        # React Executor (ReAct: serial Think-Act-Observe loop for exploratory tasks)
        from ..execution.react_executor import get_react_executor
        self.world.react_executor = get_react_executor(self.consciousness)
        logger.debug("ReactExecutor initialized")

        # Foresight Gate (arXiv 2601.03905: simulation decision)
        from ..treellm.foresight_gate import get_foresight_gate
        self.world.foresight_gate = get_foresight_gate()
        logger.debug("ForesightGate initialized")

        # Calibration Tracker (foresight + Agentic Harness: prediction vs actual)
        from ..observability.calibration import get_calibration_tracker
        self.world.calibration_tracker = get_calibration_tracker()
        logger.debug("CalibrationTracker initialized")

        # Claim Checker (AutoResearchClaw: anti-fabrication)
        from ..observability.claim_checker import CLAIM_CHECKER
        self.world.claim_checker = CLAIM_CHECKER
        logger.debug("ClaimChecker initialized")

        # Sentinel (AutoResearchClaw: watchdog monitoring)
        from ..observability.sentinel import get_sentinel
        self.world.sentinel = get_sentinel()
        logger.debug("Sentinel initialized (5 default checks)")

        # Change Manifest (Agentic Harness: falsifiable edit contracts)
        from ..observability.change_manifest import CHANGE_MANIFEST
        self.world.change_manifest = CHANGE_MANIFEST
        logger.debug("ChangeManifest initialized")

        # Harness Registry (Agentic Harness: file-level safety net)
        from ..observability.harness_registry import HARNESS_REGISTRY
        self.world.harness_registry = HARNESS_REGISTRY
        logger.debug("HarnessRegistry initialized")

        # Evolution Store (AutoResearchClaw: cross-run lesson learning)
        from ..dna.evolution_store import EVOLUTION_STORE
        self.world.evolution_store = EVOLUTION_STORE
        logger.debug("EvolutionStore initialized")

        # Agent Roles (Agentic Harness: Evolver/Evaluator/Verifier triad)
        from ..dna.agent_roles import ROLE_TRIAD
        self.world.agent_roles = ROLE_TRIAD
        logger.debug("RoleTriad initialized")

        # HITL Manager (AutoResearchClaw: human-in-the-loop)
        from ..dna.hitl import HITL_MANAGER
        self.world.hitl_manager = HITL_MANAGER
        self.world.hitl = HITL_MANAGER  # Override placeholder
        logger.debug("HITLManager initialized (6 modes)")

        # Ontology Prompt Builder (ontology: concept chain injection)
        from ..treellm.onto_prompt_builder import get_onto_prompt_builder
        self.world.onto_prompt_builder = get_onto_prompt_builder()
        logger.debug("OntoPromptBuilder initialized")

        # Activity Feed (observability: event stream)
        from ..observability.activity_feed import get_activity_feed
        self.world.activity_feed = get_activity_feed()
        logger.debug("ActivityFeed initialized")

        # Error Replay (observability: error reproduction)
        from ..observability.error_replay import get_error_replay
        self.world.error_replay = get_error_replay()
        logger.debug("ErrorReplay initialized")

        # Trust Scorer (observability: trust scoring)
        from ..observability.trust_scoring import get_trust_scorer
        self.world.trust_scorer = get_trust_scorer()
        logger.debug("TrustScorer initialized")

        # Embedding Scorer ref (already initialized above, just wire)
        if self.embedding_scorer:
            self.world.embedding_scorer = self.embedding_scorer
            logger.debug("EmbeddingScorer wired to world")

        # ── OvernightTask: 挂机长任务编排器 ──
        from ..capability.overnight_task import OvernightTask
        self.world.overnight_task = OvernightTask(self)
        logger.debug("OvernightTask initialized")

        # ── MessageGateway: 多平台消息通知 ──
        from .message_gateway import get_gateway
        self.message_gateway = get_gateway()
        self.world.message_gateway = self.message_gateway
        logger.debug("MessageGateway initialized (%s)",
                     ", ".join(self.message_gateway._get_enabled_platforms()))

        # ── UnifiedNotifier: 自适应多通道通知调度 ──
        from .unified_notifier import get_unified_notifier
        self.unified_notifier = get_unified_notifier()
        self.world.unified_notifier = self.unified_notifier
        channels = self.unified_notifier.available_channels
        logger.info("UnifiedNotifier: %d 通道自适应检测 (%s)",
                    len(channels), ", ".join(channels))

    async def _init_async(self) -> None:
        """Async initialization — health checks, node register, daemon start."""
        logger.info(f"  Flash: {self.config.model.flash_model} | Pro: {self.config.model.pro_model}")
        logger.info(f"  Node: {self.world.node.info.name} ({self.world.node.info.id[:12]})")

        # ── ConcurrencyGuard: global resource limiter ──
        try:
            from ..core.concurrency_guard import get_concurrency_guard
            guard = get_concurrency_guard()
            logger.info(f"ConcurrencyGuard initialized (max_concurrent={guard.max_concurrent})")
        except Exception as e:
            guard = None
            logger.debug(f"ConcurrencyGuard: {e}")

        # ── AsyncDisk: batched file I/O ──
        from ..core.async_disk import get_disk
        await get_disk().start()

        # ── Auto-setup environment (package managers + deps) ──
        try:
            from .pkg_manager import ensure_environment
            await ensure_environment(str(self.config._project_root or Path.cwd()))
        except Exception as e:
            logger.debug(f"Env setup skipped: {e}")

        await self._register_health_checks()
        await self.world.self_healer.start()
        await self.world.node.register()
        if guard:
            guard.spawn("hub_heartbeat", self.world.node.heartbeat(self.config.network.heartbeat_interval))
        else:
            asyncio.create_task(self.world.node.heartbeat(self.config.network.heartbeat_interval))
        self._register_agents()

        # ── Model registry (deferred if lazy) ──
        if not self._lazy:
            try:
                from ..treellm.bootstrap import setup_model_registry
                self._model_registry = await setup_model_registry(self.config)
            except Exception as e:
                logger.debug(f"Model registry skipped: {e}")
        else:
            logger.info("Model registry deferred (lazy boot)")

        # ── Economy Engine: 经济范式初始化 ──
        try:
            from ..economy.economic_engine import get_economic_orchestrator
            eco = get_economic_orchestrator()
            logger.info(f"Economic engine online — cumulative ROI: {eco.roi.cumulative_roi()}x")
        except Exception as e:
            logger.debug(f"Economy init skipped: {e}")

        # ── Models.dev sync: 全量模型数据库同步 ──
        try:
            from ..treellm.models_dev_sync import get_models_dev_sync
            sync = get_models_dev_sync()
            if sync._models:
                logger.info(f"Models.dev cache: {len(sync._models)} models")
                asyncio.create_task(sync.refresh())  # Background refresh
        except Exception as e:
            logger.debug(f"Models.dev sync skipped: {e}")

        # ── Local LLM scan (deferred if lazy) ──
        if not self._lazy:
            try:
                await self.world.consciousness.register_local_models()
            except Exception as e:
                logger.debug(f"Local scan skipped: {e}")

        # ── OpenCode serve: force discovery + refresh election ──
        try:
            self.world.consciousness._opencode_cache = []
            await self.world.consciousness._elect()
            status = self.world.consciousness.get_election_status()
            oc_count = len(status.get("opencode_providers", []))
            if oc_count:
                logger.info(f"OpenCode: {oc_count} providers discovered")
        except Exception as e:
            logger.debug(f"OpenCode election: {e}")

        # ── P2P Network (default component, always on) ──
        try:
            from ..network.p2p_node import get_p2p_node
            self._p2p_node = get_p2p_node(self)
            await self._p2p_node.start()
        except Exception as e:
            logger.debug(f"P2P: {e}")

        # ── Autonomous learner: self-evolving engine ──
        try:
            from ..dna.autonomous_learner import get_autonomous_learner
            learner = get_autonomous_learner()
            learner.set_hub(self)
            await learner.start()
        except Exception as e:
            logger.debug(f"Learner init: {e}")

        # ── Cron scheduler ──
        try:
            from ..execution.cron_scheduler import get_scheduler
            sched = get_scheduler()
            async def cron_callback(job):
                logger.info(f"Cron: {job.id} — {job.description}")
            sched.set_callback(cron_callback)
            await sched.start()
        except Exception as e:
            logger.debug(f"Cron init: {e}")

        # ── IdleConsolidator: background knowledge consolidation ──
        try:
            from ..capability.idle_consolidator import get_idle_consolidator
            ic = get_idle_consolidator()
            if guard:
                guard.spawn("hub_idle_consolidator", ic.start(self, idle_threshold=60))
            else:
                asyncio.create_task(ic.start(self, idle_threshold=60))
            logger.info("IdleConsolidator started (60s threshold)")
        except Exception as e:
            logger.debug(f"IdleConsolidator: {e}")

        # ── SessionContinuity: cross-session resume ──
        try:
            from ..capability.session_continuity import get_session_continuity
            sc = get_session_continuity()
            state = sc.load()
            if state and state.last_conversation_summary:
                logger.info(f"Session resume: {state.last_conversation_summary[:60]}...")
        except Exception as e:
            logger.debug(f"SessionContinuity: {e}")

        # ── AgentMarketplace: auto-sync with relay ──
        try:
            from ..capability.agent_marketplace import get_marketplace
            am = get_marketplace()
            asyncio.create_task(am.sync_with_relay(self))
        except Exception as e:
            logger.debug(f"Marketplace: {e}")

        # ── ActivityFeed: unified event stream ──
        try:
            from ..observability.activity_feed import get_activity_feed
            feed = get_activity_feed()
            feed.log("system", "hub", "LivingTree booted", severity="info")
            self.world.activity_feed = feed
            logger.info("ActivityFeed initialized")
        except Exception as e:
            logger.debug(f"ActivityFeed: {e}")

        # ── AgentEval: 4-layer evaluation ──
        try:
            from ..observability.agent_eval import get_eval
            self.world.agent_eval = get_eval()
            logger.info("AgentEval initialized (4-layer)")
        except Exception as e:
            logger.debug(f"AgentEval: {e}")

        # ── TrustScoring: per-agent posture ──
        try:
            from ..observability.trust_scoring import get_trust_scorer
            self.world.trust_scorer = get_trust_scorer()
            logger.info("TrustScoring initialized (profile: standard)")
        except Exception as e:
            logger.debug(f"TrustScoring: {e}")

        # ── ProxyPool: multi-source proxy fetcher ──
        try:
            from ..network.proxy_fetcher import get_proxy_pool
            pool = get_proxy_pool()
            if guard:
                guard.spawn("hub_proxy_pool", pool.start_background())
            else:
                asyncio.create_task(pool.start_background())
            logger.info(f"ProxyPool started ({pool.stats()['total']} cached)")
        except Exception as e:
            logger.debug(f"ProxyPool: {e}")

        # ── DataLineage: document data tracing ──
        try:
            from ..capability.data_lineage import get_data_lineage
            self.world.data_lineage = get_data_lineage()
            logger.info("DataLineage initialized")
        except Exception as e:
            logger.debug(f"DataLineage: {e}")

        # ── AdaptivePractice: idle self-study for weak areas ──
        try:
            from ..capability.adaptive_practice import get_adaptive_practice
            self.world.adaptive_practice = get_adaptive_practice()
            logger.info("AdaptivePractice initialized")
        except Exception as e:
            logger.debug(f"AdaptivePractice: {e}")

        # ── ProgressiveTrust: per-user expertise model ──
        try:
            from ..capability.progressive_trust import get_progressive_trust
            self.world.progressive_trust = get_progressive_trust()
            logger.info("ProgressiveTrust initialized")
        except Exception as e:
            logger.debug(f"ProgressiveTrust: {e}")

        # ── NetworkBrain: autonomous internet knowledge ingestion ──
        try:
            from ..capability.network_brain import get_network_brain
            self.world.network_brain = get_network_brain()
            asyncio.create_task(self._brain_loop())
            logger.info("NetworkBrain initialized (arxiv + github + hn + so + rss)")
        except Exception as e:
            logger.debug(f"NetworkBrain: {e}")

        # ── RemoteAssist: observer message routing ──
        try:
            from ..capability.remote_assist import get_remote_assist
            ra = get_remote_assist()
            self.world.remote_assist = ra
            from ..network.p2p_node import get_p2p_node
            p2p = get_p2p_node()
            p2p.on_message(lambda data: self._handle_observe_message(data, ra))
            logger.info(f"RemoteAssist initialized (ID: {ra.client_id})")
        except Exception as e:
            logger.debug(f"RemoteAssist: {e}")

        # ── ErrorReplay: operation recording + self-healing ──
        try:
            from ..observability.error_replay import get_error_replay
            self.world.error_replay = get_error_replay()
            logger.info("ErrorReplay initialized")
        except Exception as e:
            logger.debug(f"ErrorReplay: {e}")

        if self.lsp_manager:
            try:
                await self.lsp_manager.start()
                logger.debug("LSP Manager started")
            except Exception as e:
                logger.debug(f"LSP start skipped: {e}")

        if self.world.dual_mode:
            try:
                await self.world.dual_mode.start_monitoring()
                status = await self.world.dual_mode.check()
                logger.info(f"DualMode: {'online' if status['online'] else 'offline'} (provider={status['provider']})")
            except Exception as e:
                logger.debug(f"DualMode start: {e}")

        self._started = True
        self._phase = 1
        self._ready_event.set()

        # ── Initialize WeWork Bot (reply + KB sync) ──
        self._init_wework_bot()

        if self.world.biorhythm:
            await self.world.biorhythm.start()

        # ── Start Discovery (LAN broadcast) ──
        if self.world.discovery:
            discovery = self.world.discovery
            if self.world.node:
                discovery.set_node_info(
                    self.world.node.info.id,
                    self.world.node.info.name,
                )
            await discovery.start()
            logger.info("Discovery: LAN broadcast active")

        # ── NAT detection ──
        if self.world.nat_traverser:
            nat_type = await self.world.nat_traverser.detect_nat_type()
            ep = await self.world.nat_traverser.get_public_endpoint()
            logger.info(f"NAT: {nat_type.value} — public {ep[0]}:{ep[1]}")
            asyncio.create_task(self.world.nat_traverser.health_check_loop())

        # ── Start ResilienceBrain ──
        from ..core.resilience_brain import get_resilience
        self.resilience = get_resilience()
        self.resilience._hub = self
        await self.resilience.start()
        logger.info("ResilienceBrain: predictive fault tolerance active")

        # ── Start CapabilityScanner ──
        from ..core.capability_scanner import get_capability_scanner
        self.cap_scanner = get_capability_scanner()
        self.cap_scanner._hub = self
        await self.cap_scanner.start()
        logger.info("CapabilityScanner: external service discovery active")

        # ── Start AutonomousGrowth ──
        from ..core.autonomous_growth import get_growth
        self.growth = get_growth()
        self.growth._hub = self
        logger.info("AutonomousGrowth: self-sufficiency tracking active")

        # ── Environment probe ──
        from ..core.shell_env import probe_summary
        env_summary = probe_summary()
        logger.info(f"Environment toolchain:\n{env_summary}")

        # ── Warm up response cache ──
        from ..core.perf_accel import get_response_cache
        cache = get_response_cache()
        logger.info(f"Response cache ready: {cache.stats()['max_entries']} entries max, TTL {cache._default_ttl}s")

        # ── Start SwarmCoordinator ──
        if self.swarm:
            await self.swarm.start()
            logger.info("Swarm: direct P2P collaboration active")

        await self.daemon.start()
        logger.info("🌳 LivingTree online — autonomous cycles active")

        # ── Sync provider keys from relay (fallback to local if unavailable) ──
        await self._sync_provider_keys_from_relay()

        story = self.daemon._advanced.full_narrative()
        for line in story.split("\n"):
            if line.strip():
                logger.info(line)

        # ── Memory Optimizer: background warm-up (adaptive, no config) ──
        try:
            from ..core.memory_optimizer import get_memory_optimizer
            opt = get_memory_optimizer()
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, opt.warm_up)
            logger.info("MemoryOptimizer warm-up scheduled (adaptive, background)")
        except Exception as e:
            logger.debug(f"MemoryOptimizer: {e}")

        # ── Scinet: smart proxy for overseas acceleration ──
        try:
            from ..network.scinet_service import get_scinet
            self.scinet = get_scinet(port=7890)
            asyncio.create_task(self.scinet.start())
            logger.info("Scinet proxy started (localhost:7890)")
        except Exception as e:
            logger.debug(f"Scinet: {e}")

        # ── ImmuneSystem: auto-defense against adversarial inputs ──
        try:
            from ..dna.immune_system import get_immune_system
            immune = get_immune_system()
            logger.info(f"ImmuneSystem initialized (threat_count={len(immune.known_threats)})")
        except Exception as e:
            logger.debug(f"ImmuneSystem: {e}")

        # ── HormoneNetwork: inter-organ signaling ──
        try:
            from ..dna.hormone_signaling import get_endocrine
            endocrine = get_endocrine()
            await endocrine.start_pulse()
            logger.info("HormoneNetwork initialized — pulse started")
        except Exception as e:
            logger.debug(f"HormoneNetwork: {e}")

        # ── MetabolismEngine: cost budgeting ──
        try:
            from ..economy.metabolism import get_metabolism
            metabolism = get_metabolism()
            daily_budget = getattr(self.config, 'daily_token_budget', 1_000_000)
            daily_cost = getattr(self.config, 'daily_cost_yuan', 50.0)
            metabolism.allocate_daily_budget(total_tokens=daily_budget, total_cost_yuan=daily_cost)
            logger.info(f"MetabolismEngine initialized (budget={daily_budget} tokens, ¥{daily_cost})")
        except Exception as e:
            logger.debug(f"MetabolismEngine: {e}")

        # ── CacheHierarchy: multi-tier response cache ──
        try:
            from ..treellm.cache_hierarchy import get_cache_hierarchy
            cache_h = get_cache_hierarchy()
            logger.info(f"CacheHierarchy initialized (tiers={len(cache_h._tiers)})")
        except Exception as e:
            logger.debug(f"CacheHierarchy: {e}")

        # ── OTEL Integration: OpenTelemetry tracing ──
        try:
            from ..observability.otel_integration import get_otel
            otel = get_otel()
            logger.info(f"OTEL integration initialized (service={otel.service_name})")
        except Exception as e:
            logger.debug(f"OTEL: {e}")

        # ── SwarmEvolution: collective learning ──
        try:
            from ..dna.swarm_evolution import get_swarm_evolution
            swarm_evo = get_swarm_evolution()
            logger.info(f"SwarmEvolution initialized")
        except Exception as e:
            logger.debug(f"SwarmEvolution: {e}")

        # ── EmotionalMemory: experience-weighted recall ──
        try:
            from ..memory.emotional_memory import get_emotional_memory
            emo_mem = get_emotional_memory()
            logger.info(f"EmotionalMemory initialized (entries={len(emo_mem._store)})")
        except Exception as e:
            logger.debug(f"EmotionalMemory: {e}")

    async def _brain_loop(self):
        """Periodic knowledge ingestion cycle."""
        brain = getattr(self.world, 'network_brain', None)
        if not brain:
            return
        await asyncio.sleep(60)
        while True:
            try:
                await brain.ingest_cycle(self)
                await brain.deep_digest(self, max_items=5)
            except Exception as e:
                logger.warning(f"Brain ingest/digest cycle error: {e}")
            await asyncio.sleep(1800)  # 30 minutes

    async def _sync_provider_keys_from_relay(self) -> None:
        """Sync API provider keys and web2api config from relay server.

        Called automatically on boot. Silently falls back to local config
        when relay is unavailable (offline/network error).
        """
        try:
            from ..network.config_sync import get_config_syncer
            syncer = get_config_syncer()

            # Check if relay has a backup of our config
            status = await syncer.check_server_status()
            if status and status.get("has_backup"):
                logger.info(
                    "Relay config backup found (%d API keys, %d accounts, updated %s)",
                    status.get("api_keys_count", 0),
                    status.get("accounts_count", 0),
                    status.get("updated_at", "unknown"),
                )
                logger.info("Use /restore-config to restore from relay")
        except Exception as e:
            logger.debug("Config sync from relay unavailable: %s", e)

    async def restore_config_from_relay(self) -> dict:
        """One-click restore: download encrypted config package from relay.

        Called via /restore-config command. Decrypts and imports:
          - All API keys → SecretVault
          - All web2api accounts → ProviderRegistry

        Returns:
            {"success": bool, "keys_restored": int, "accounts_restored": int, "error": str}
        """
        try:
            from ..network.config_sync import get_config_syncer
            syncer = get_config_syncer()
            package = await syncer.download_all()
            if package:
                return {
                    "success": True,
                    "keys_restored": len(package.api_keys),
                    "accounts_restored": sum(len(v) for v in package.web2api_accounts.values()),
                    "error": "",
                }
            return {
                "success": False, "keys_restored": 0, "accounts_restored": 0,
                "error": "No backup found (server offline or no previous upload)",
            }
        except Exception as e:
            return {"success": False, "keys_restored": 0, "accounts_restored": 0, "error": str(e)}

    async def backup_config_to_relay(self) -> dict:
        """One-click backup: upload encrypted config to relay.

        Called via /backup-config command.

        Returns:
            {"success": bool, "keys_count": int, "accounts_count": int, "error": str}
        """
        try:
            from ..network.config_sync import get_config_syncer
            syncer = get_config_syncer()
            success = await syncer.upload_all()
            status = syncer.check_server_status()
            return {
                "success": success,
                "keys_count": 0,  # filled by server response
                "accounts_count": 0,
                "error": "" if success else "Upload failed — relay unreachable",
            }
        except Exception as e:
            return {"success": False, "keys_count": 0, "accounts_count": 0, "error": str(e)}

    @staticmethod
    def _handle_observe_message(data, ra):
        """Route incoming P2P observe-related messages to UI."""
        try:
            if isinstance(data, str):
                data = json.loads(data)
            msg_type = data.get("type", "")
            if msg_type == "observe_sync":
                fragment = ra.receive_fragment(data)
                # Forward memo/chat messages to Conversation UI
                if fragment.msg_type in ("memo", "message") and fragment.content:
                    logger.info(f"📝 {fragment.sender_role}: {fragment.content[:80]}")
            elif msg_type == "observe_request":
                logger.info(f"Observe request from {data.get('from_id','?')}")
        except Exception as e:
            logger.debug(f"P2P message handling error: {e}")

    async def shutdown(self) -> None:
        if not self._started:
            return
        logger.info("Shutting down...")

        # ── Stop ResilienceBrain ──
        if getattr(self, "resilience", None):
            await self.resilience.stop()

        # ── Stop CapabilityScanner ──
        if getattr(self, "cap_scanner", None):
            await self.cap_scanner.stop()

        # ── Stop Swarm ──
        if getattr(self, "swarm", None):
            await self.swarm.stop()

        # ── Stop Discovery ──
        if self.world.discovery:
            await self.world.discovery.stop()

        # ── Save session continuity ──
        try:
            from ..capability.session_continuity import get_session_continuity
            await get_session_continuity().save(self)
        except Exception as e:
            logger.debug(f"Session continuity save error: {e}")

        await self.daemon.stop()
        await self.world.self_healer.stop()
        await self.world.node.shutdown()
        if self._session:
            await self._session.close()
        self._started = False
        logger.info("🌳 LivingTree offline")

    # ── Overnight Task API ──────────────────────────────────

    async def start_overnight_task(
        self, goal: str,
        notify_platforms: list[str] | None = None,
        notify_interval_minutes: int = 0,
        notify_email: str = "",
    ):
        """启动挂机长任务。

        Args:
            goal: 自然语言目标
            notify_platforms: 通知平台 (cli/telegram/smtp/webhook/all)
            notify_interval_minutes: 进度通知间隔（0=仅完成时通知）
            notify_email: SMTP 邮件地址
        """
        ot = getattr(self.world, "overnight_task", None)
        if not ot:
            logger.error("OvernightTask 未初始化")
            return None
        logger.info("OvernightTask: 开始挂机 — %s", goal[:60])
        status = await ot.start(
            goal,
            notify_platforms=notify_platforms,
            notify_interval_minutes=notify_interval_minutes,
            notify_email=notify_email,
        )
        return status

    async def resume_overnight_task(self):
        """恢复上次中断的挂机任务。"""
        ot = getattr(self.world, "overnight_task", None)
        if not ot:
            return None
        return await ot.resume()

    def stop_overnight_task(self):
        """停止当前挂机任务。"""
        ot = getattr(self.world, "overnight_task", None)
        if ot:
            ot.stop()

    def overnight_task_status(self) -> Optional[dict]:
        """查询挂机任务状态。"""
        ot = getattr(self.world, "overnight_task", None)
        if not ot:
            return None
        s = ot.status
        return {
            "goal": s.goal,
            "state": s.state,
            "percent": s.percent,
            "current_step": s.current_step,
            "completed_steps": s.completed_steps,
            "total_steps": s.total_steps,
            "report_path": s.report_path,
            "elapsed_seconds": s.elapsed_seconds,
        }

    # ── Long Task Natural Language Interface ────────────────

    _LONG_TASK_PATTERNS = [
        "收集", "爬取", "抓取", "搜集", "汇总",
        "研究报告", "可行性", "可行性研究", "环评报告", "安评报告",
        "技术报告", "调研报告", "分析报告", "尽职调查",
        "整理资料", "汇编", "编写报告", "生成报告", "撰写",
        "挂机", "后台任务", "长任务",
    ]

    _TASK_CONTROL_PATTERNS = {
        "cancel": ["取消任务", "取消挂机", "停止任务", "停止挂机", "终止", "cancel", "stop"],
        "pause": ["暂停任务", "暂停挂机", "pause"],
        "resume": ["继续任务", "继续挂机", "恢复任务", "恢复挂机", "resume", "continue"],
        "status": ["任务进度", "挂机进度", "当前进度", "进度", "status", "progress"],
    }

    def _is_long_running_task(self, message: str) -> bool:
        """Detect if user message implies a long-running background task."""
        msg = message.lower().replace(" ", "")
        for pat in self._LONG_TASK_PATTERNS:
            if pat in msg:
                return True
        return False

    async def _handle_long_task_control(self, message: str) -> Optional[dict]:
        """Handle natural language control of running overnight tasks."""
        msg = message.strip().lower()

        # Check for cancel
        for kw in self._TASK_CONTROL_PATTERNS["cancel"]:
            if kw in msg:
                return await self._do_cancel_task()

        # Check for pause
        for kw in self._TASK_CONTROL_PATTERNS["pause"]:
            if kw in msg:
                return await self._do_pause_task()

        # Check for resume
        for kw in self._TASK_CONTROL_PATTERNS["resume"]:
            if kw in msg:
                return await self._do_resume_task()

        # Check for status
        for kw in self._TASK_CONTROL_PATTERNS["status"]:
            if kw in msg:
                return await self._do_task_status()

        return None

    async def _do_cancel_task(self) -> dict:
        ot = getattr(self.world, "overnight_task", None)
        if ot and ot.status.state == "running":
            ot.stop()
            return {"mode": "task_control", "action": "cancelled",
                    "message": "⏸ 挂机任务已请求取消，当前步骤完成后停止"}
        return {"mode": "task_control", "action": "cancelled",
                "message": "没有正在运行的挂机任务"}

    async def _do_pause_task(self) -> dict:
        ot = getattr(self.world, "overnight_task", None)
        if ot and ot.status.state == "running":
            ot.stop()
            return {"mode": "task_control", "action": "paused",
                    "message": "⏸ 挂机任务已暂停，输入「继续任务」恢复"}
        return {"mode": "task_control", "action": "paused",
                "message": "没有正在运行的挂机任务"}

    async def _do_resume_task(self) -> dict:
        ot = getattr(self.world, "overnight_task", None)
        if ot:
            status = await ot.resume()
            if status:
                return {"mode": "task_control", "action": "resumed",
                        "message": f"▶ 已恢复挂机任务（{status.completed_steps}/{status.total_steps} 已完成）"}
        return {"mode": "task_control", "action": "resumed",
                "message": "没有可恢复的挂机任务，请先启动一个长任务"}

    async def _do_task_status(self) -> dict:
        status = self.overnight_task_status()
        if not status:
            return {"mode": "task_control", "action": "status",
                    "message": "没有正在运行或暂停的挂机任务"}
        state_emoji = {"running": "▶", "paused": "⏸", "completed": "✅", "failed": "❌"}
        emoji = state_emoji.get(status["state"], "❓")
        return {
            "mode": "task_control", "action": "status",
            "message": (
                f"{emoji} 挂机任务进度 [{status['state']}]\n"
                f"  目标: {status['goal'][:50]}...\n"
                f"  进度: {status['completed_steps']}/{status['total_steps']} ({status['percent']:.0f}%)\n"
                f"  当前: {status['current_step']}\n"
                f"  耗时: {status['elapsed_seconds']:.0f} 秒"
            ),
        }

    async def _start_background_task(self, goal: str, skip_assessment: bool = False) -> dict:
        """Start overnight task in background, return immediate ack.

        Pre-flight: assesses task clarity before starting.
        Score >= 7 → start immediately. Score < 7 → return clarifying questions.
        """
        ot = getattr(self.world, "overnight_task", None)
        if not ot:
            return {"mode": "chat", "content": "OvernightTask 模块未初始化"}

        if ot.status.state == "running":
            s = ot.status
            return {"mode": "task_control", "action": "already_running",
                    "message": f"已有挂机任务在运行中：{s.goal[:40]}... ({s.completed_steps}/{s.total_steps})\n输入「取消任务」停止，或「任务进度」查看状态"}

        # ── Pre-flight: assess task clarity ──
        if not skip_assessment:
            clarity_result = await self._assess_task_clarity(goal)
            if clarity_result and clarity_result.get("clarity_score", 0) < 7:
                questions = clarity_result.get("clarifying_questions", [])
                missing = clarity_result.get("missing_info", [])
                q_list = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(questions[:3]))
                m_list = ", ".join(missing[:3]) if missing else "具体范围、输出格式、时间约束等"
                return {
                    "mode": "clarify",
                    "action": "need_clarification",
                    "message": (
                        f"🤔 任务目标不够明确（清晰度 {clarity_result['clarity_score']}/10）\n\n"
                        f"缺少信息: {m_list}\n\n"
                        f"请补充以下信息再启动：\n{q_list}\n\n"
                        f"或回复\"直接开始\"跳过验证"
                    ),
                }

        # Start task in background, return immediately
        async def _run_in_background():
            try:
                await self.start_overnight_task(goal)
            except Exception as e:
                logger.error(f"Background task failed: {e}")

        asyncio.create_task(_run_in_background())

        return {
            "mode": "task_control",
            "action": "started",
            "message": (
                f"🔬 长任务已启动，将在后台全自动执行\n"
                f"  目标: {goal[:80]}...\n"
                f"  • 随时输入\"任务进度\"查看状态\n"
                f"  • 输入\"取消任务\"停止\n"
                f"  • 输入\"暂停任务\"暂停（可\"继续任务\"恢复）\n"
                f"  完成后会自动通知你 📬"
            ),
        }

    async def _assess_task_clarity(self, goal: str) -> Optional[dict]:
        """Assess how clear/actionable a task goal is.

        Uses the LLM to score clarity and suggest clarifying questions.
        Score 1-10: <7 means too vague, needs clarification before starting.

        Returns: dict with clarity_score, missing_info, clarifying_questions
        """
        try:
            awareness = self.world.consciousness
            prompt = (
                f"评估以下任务目标的明确度（1-10分）：\n\n"
                f"目标: {goal}\n\n"
                f"检查维度：范围是否清晰？输出物是否明确？涉及领域是否已知？约束条件是否定义？\n\n"
                f"仅返回 JSON（不要其他文字）：\n"
                f'{{"clarity_score": <1-10>, "missing_info": ["缺失维度1","缺失维度2"], '
                f'"clarifying_questions": ["具体追问1","具体追问2","具体追问3"]}}'
            )
            resp = await awareness.think(prompt, model=awareness._llm.flash_model)
            text = resp.get("content", "{}") if isinstance(resp, dict) else str(resp)

            # Extract JSON from response
            import json as _json
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return _json.loads(text[start:end])
        except Exception as e:
            logger.debug("Task clarity assessment skipped: %s", e)

        # Default: assume clear enough (fail-open)
        return {"clarity_score": 8, "missing_info": [], "clarifying_questions": []}

    async def chat(self, message: str, **kwargs) -> dict[str, Any]:
        if not self._started:
            await self.start()
        self.world.metrics.life_cycles.inc()

        # ── Direct-start bypass ──
        if message.strip().lower() in ("直接开始", "直接开始吧", "跳过", "skip", "确认开始", "开始吧"):
            return await self._start_background_task("用户确认: " + message, skip_assessment=True)
        task_result = await self._handle_long_task_control(message)
        if task_result:
            return task_result

        # ── Long-task auto-detection ──
        if self._is_long_running_task(message):
            return await self._start_background_task(message)

        # ── Intent-driven routing (replaces keyword gating) ──
        try:
            intent_result = self.world.consciousness.recognize_intent(message)
            intent = intent_result.get("intent", "general")
            domain = intent_result.get("domain", "general")

            if intent in ("code", "training", "analysis") or domain in ("code", "training"):
                from ..execution.real_pipeline import get_real_orchestrator
                orch = get_real_orchestrator(self)
                ctx = await orch.plan(message)
                if ctx.steps and len(ctx.steps) >= 3:
                    ctx = await orch.execute(ctx)
                    status = orch.get_status(ctx)
                    return {
                        "mode": "pipeline", "intent": intent, "domain": domain,
                        "pipeline": {"steps": [s.__dict__ for s in ctx.steps]},
                        "results": [s.result[:500] for s in ctx.steps if s.result],
                        "stats": {"total": status["total"], "done": status["done"], "failed": status["failed"]},
                    }
        except Exception as e:
            logger.debug(f"Intent routing: {e}")

        mem_context = ""
        if self.struct_memory:
            try:
                entries, synthesis = await self.struct_memory.retrieve_for_query(message)
                mem_context = self.struct_memory.get_context_block(message, entries, synthesis)
            except Exception as e:
                logger.debug(f"StructMemory retrieve error: {e}")

        # ── Dynamic tool discovery (no hardcoded workflows) ──
        try:
            tools = self.world.tool_market.search(message)
            if tools:
                kwargs["available_tools"] = [
                    {"name": t.name, "description": t.description,
                     "category": t.category, "input_schema": t.input_schema}
                    for t in tools[:20]
                ]
                kwargs["tool_market"] = self.world.tool_market
                logger.debug("Tool dispatch: %d tools for '%s'", len(tools), message[:50])
        except Exception as e:
            logger.debug("Tool discovery: %s", e)

        ctx = await self._run_engine(message, mem_context, **kwargs)

        if self.session_manager:
            try:
                from ..execution.session_manager import SessionState
                state = SessionState(
                    session_id=ctx.session_id,
                    workspace=str(Path.cwd()),
                    messages=[{"role": "user", "content": message},
                              {"role": "assistant", "content": str(ctx.metadata.get("cognition", ""))}],
                    total_tokens=ctx.metadata.get("total_tokens", 0),
                    reasoning_effort=getattr(self, '_effort', "max"),
                )
                await self.session_manager.save(state)
            except Exception as e:
                logger.debug(f"Session state save error: {e}")

        cache_stats = {}
        if self.cache_optimizer:
            cache_stats = self.cache_optimizer.stats()

        return {
            "session_id": ctx.session_id, "intent": ctx.intent,
            "plan": ctx.plan, "execution_results": ctx.execution_results,
            "reflections": ctx.reflections, "quality": ctx.quality_reports,
            "generation": self.world.genome.generation,
            "success_rate": ctx.metadata.get("success_rate", 0),
            "cache_stats": cache_stats,
            "side_git_turn": ctx.metadata.get("side_git_turn"),
        }

    async def generate_report(self, template: str, data: dict, requirements: dict | None = None) -> dict:
        if not self._started: await self.start()
        de = self.world.doc_engine
        result = await de.generate_report(template, data, requirements or {})
        doc = await de.auto_format(result["document"])
        path = await de.export_to(doc, self.config.doc_engine.default_format)
        return {**result, "path": str(path), "formatted": doc}

    async def train_cell(self, name: str, data: list[dict], epochs: int = 3) -> dict:
        if not self._started: await self.start()
        from ..cell import CellAI
        cell = CellAI(name=name, model_name=self.config.cell.default_base_model)
        result = cell.train(data, epochs=epochs)
        self.world.cell_registry.register(cell)
        return result

    async def drill_train(self, cell_name: str, model: str, dataset: list[dict],
                          training_type: str = "lora", teacher: str = "", reward: str = "") -> dict:
        if not self._started: await self.start()
        from ..cell import CellAI
        cell = CellAI(name=cell_name, model_name=model)
        self.world.cell_registry.register(cell)
        if training_type == "distill" and teacher:
            r = await self.world.drill.distill(cell, teacher, dataset)
        elif training_type == "grpo":
            r = await self.world.drill.train_grpo(cell, dataset, reward)
        elif training_type == "full":
            r = await self.world.drill.train_full(cell, dataset)
        else:
            r = await self.world.drill.train_lora(cell, dataset)
        return {"success": r.success, "loss": r.loss, "eval_loss": r.eval_loss, "model_path": r.model_path, "metrics": r.metrics, "training_time": r.training_time_seconds, "error": r.error}

    async def drill_evaluate(self, model_path: str, benchmarks: list[str] | None = None) -> dict:
        if not self._started: await self.start()
        return await self.world.drill.evaluate(model_path, benchmarks)

    async def drill_quantize(self, model_path: str, method: str = "awq") -> dict:
        if not self._started: await self.start()
        r = await self.world.drill.quantize(model_path, method)
        return {"success": r.success, "model_path": r.model_path, "error": r.error}

    async def drill_deploy(self, model_path: str, port: int = 8000) -> dict:
        if not self._started: await self.start()
        return await self.world.drill.deploy(model_path, port)

    async def download_model(self, model_id: str) -> str:
        if not self._started: await self.start()
        return await self.world.drill.download_model(model_id)

    async def distill_knowledge(self, prompts: list[str]) -> list[str]:
        if not self._started: await self.start()
        from ..cell import CellAI
        cell = CellAI(name="distill")
        results = await self.world.distillation.distill_knowledge(cell, prompts, self.world.expert_config)
        self.world.cell_registry.register(cell)
        return results

    async def absorb_github(self, url: str) -> dict:
        if not self._started: await self.start()
        from ..cell import CellAI
        cell = CellAI(name=f"phage_{url.split('/')[-1][:20]}")
        return await self.world.phage.absorb_codebase(cell, url)

    async def index_codebase(self, path: str = ".") -> dict:
        if not self._started: await self.start()
        stats = self.world.code_graph.index(path)
        self.world.code_graph.save()
        return {"files": stats.total_files, "entities": stats.total_entities, "edges": stats.total_edges, "languages": stats.languages, "build_time_ms": stats.build_time_ms}

    def blast_radius(self, files: list[str]) -> list[dict]:
        results = self.world.code_graph.blast_radius(files)
        return [{"file": r.file, "reason": r.reason, "risk": r.risk} for r in results]

    async def discover_peers(self) -> list[dict]:
        if not self._started: await self.start()
        peers = await self.world.discovery.discover_lan()
        return [p.model_dump() for p in peers]

    async def generate_code(self, name: str, description: str, domain: str = "general") -> dict:
        if not self._started: await self.start()
        from ..capability.code_engine import CodeSpec
        code = await self.world.code_engine.generate_with_annotation(CodeSpec(name=name, description=description, domain=domain))
        return {"name": code.name, "language": code.language, "code": code.code, "annotations": code.annotations, "formula": code.formula, "quality": code.quality_score, "safety": code.safety_score}

    def status(self) -> dict:
        if not self._started:
            return {"version": self.config.version, "online": False, "phase": "starting"}
        cache_stats = self.cache_optimizer.stats() if self.cache_optimizer else {}
        sessions = self.session_manager.list_sessions.__wrapped__ if hasattr(self.session_manager, 'list_sessions') else []
        return {
            "version": self.config.version, "online": True,
            "engine": self.engine.status(),
            "cells": len(self.world.cell_registry.discover()),
            "network": self.world.node.get_status(),
            "orchestrator": self.world.orchestrator.get_status(),
            "healer": self.world.self_healer.get_status(),
            "audit": self.world.safety.summary(),
            "cache": cache_stats,
            "sub_agents": self.sub_agent_roles.get_status() if self.sub_agent_roles else {},
            "struct_memory": self.struct_memory.get_stats() if self.struct_memory else {},
        }

    def audit_summary(self) -> dict:
        return self.world.safety.summary()

    def verify_audit_chain(self) -> dict:
        valid, idx = self.world.safety.verify_audit()
        return {"valid": valid, "first_broken_index": idx, "total_entries": len(self.world.safety.audit.entries)}

    def opencode_bin_path(self) -> str:
        from pathlib import Path
        base = Path(".livingtree") / "base" / "opencode"
        exe = base / ("opencode.exe" if __import__('sys').platform == "win32" else "opencode")
        if exe.exists():
            return str(exe)
        import shutil
        return shutil.which("opencode") or "opencode"

    async def restore_turn(self, turn_id: int) -> dict:
        if self.side_git:
            ok = await self.side_git.restore(turn_id)
            return {"restored": ok, "turn_id": turn_id}
        return {"restored": False, "error": "SideGit not available"}

    async def revert_turn(self, turn_id: int) -> dict:
        return await self.restore_turn(turn_id)

    async def list_side_git_turns(self) -> list[dict]:
        if self.side_git:
            return await self.side_git.list_turns()
        return []

    async def list_sessions(self) -> list[dict]:
        if self.session_manager:
            return await self.session_manager.list_sessions()
        return []

    async def resume_session(self, session_id: str) -> dict | None:
        if self.session_manager:
            state = await self.session_manager.load(session_id)
            return state.model_dump() if state else None
        return None

    def get_cache_stats(self) -> dict:
        if self.cache_optimizer:
            return self.cache_optimizer.stats()
        return {}

    async def run_rlm_fanout(self, prompt: str, n_workers: int = 4) -> dict:
        if self.rlm_runner:
            result = await self.rlm_runner.fan_out(prompt, n_workers)
            return {
                "summary": result.summary(),
                "worker_count": result.worker_count,
                "success_count": result.success_count,
                "total_tokens": result.total_tokens,
                "results": [{"task_id": r.task_id, "content": r.content[:200], "success": r.success} for r in result.results],
            }
        return {"error": "RLM not available"}

    async def run_implement_verify(self, spec: str) -> dict:
        if self.sub_agent_roles:
            task = await self.sub_agent_roles.run_implement_verify(spec)
            return {
                "task_id": task.id,
                "status": task.status,
                "approved": task.approved,
                "iterations": task.iterations,
                "output": task.final_output[:500] if task.final_output else "",
                "verifier_feedback": task.verifier_feedback[:200] if task.verifier_feedback else "",
            }
        return {"error": "SubAgentRoles not available"}

    async def lsp_check_file(self, file_path: str) -> dict:
        if self.lsp_manager:
            result = await self.lsp_manager.check_file(file_path)
            return {
                "file": file_path,
                "errors": result.errors,
                "warnings": result.warnings,
                "diagnostics": [{"line": d.line, "severity": d.severity, "message": d.message} for d in result.diagnostics[:15]],
            }
        return {"error": "LSP not available"}

    async def generate_agents_md(self) -> dict:
        ws = Path.cwd()
        data = {
            "workspace": str(ws),
            "project_type": "general",
        }
        if (ws / "pyproject.toml").exists():
            data["project_type"] = "python"
        elif (ws / "package.json").exists():
            data["project_type"] = "nodejs"
        elif (ws / "Cargo.toml").exists():
            data["project_type"] = "rust"

        agents_path = ws / "AGENTS.md"
        if agents_path.exists():
            data["exists"] = True
            data["existing_content"] = agents_path.read_text(encoding="utf-8")[:500]
        return data

    async def retrieve_from_memory(self, query: str, top_k: int = 60) -> dict:
        if self.struct_memory:
            entries, synthesis = await self.struct_memory.retrieve_for_query(query, top_k=top_k)
            context = self.struct_memory.get_context_block(query, entries, synthesis)
            return {
                "entries_count": len(entries),
                "synthesis_count": len(synthesis),
                "context_block": context[:5000],
                "stats": self.struct_memory.get_stats(),
            }
        return {"error": "StructMemory not available"}

    async def consolidate_memory(self) -> dict:
        if self.struct_memory:
            blocks = await self.struct_memory.consolidate_if_needed()
            return {
                "consolidated": len(blocks),
                "new_synthesis": [{"id": b.id, "content": b.content[:200]} for b in blocks],
                "stats": self.struct_memory.get_stats(),
            }
        return {"error": "StructMemory not available"}

    def _register_agents(self) -> None:
        from ..execution import AgentSpec, AgentRole
        seeds = [
            ("analyst", ["analyst"], ["analysis", "reasoning", "tool_use"]),
            ("executor", ["executor"], ["execution", "code_gen", "tool_use"]),
            ("collector", ["collector"], ["web_search", "file_read", "knowledge_query"]),
        ]
        for name, roles, caps in seeds:
            self.world.orchestrator.register_agent(AgentSpec(name=name, roles=[AgentRole(name=r, capabilities=caps) for r in roles]))

    async def _register_health_checks(self) -> None:
        async def _check_kb():
            try:
                docs = self.world.knowledge_base.get_by_domain(None)
                return True, {"docs": len(docs)}
            except Exception as e:
                return False, {"error": str(e)}
        async def _check_cells():
            try:
                cells = self.world.cell_registry.discover()
                return True, {"cells": len(cells)}
            except Exception as e:
                return False, {"error": str(e)}
        async def _check_network():
            try:
                s = self.world.node.get_status()
                return s.get("status") == "online", s
            except Exception as e:
                return False, {"error": str(e)}
        for name, fn in [("kb", _check_kb), ("cells", _check_cells), ("network", _check_network)]:
            self.world.self_healer.register_check(name, fn)

    async def _refresh_models_async(self, registry):
        """Background: fetch models from all providers (resource-gated)."""
        from ..observability.system_monitor import get_monitor
        if not get_monitor().can_run_task("ModelRefresh", heavy=True):
            logger.debug("Model refresh deferred (resources)")
            return
        try:
            await registry.refresh_all()
            stats = registry.get_stats()
            total = sum(s["models"] for s in stats.values())
            logger.info(f"Model refresh complete: {total} models from {len(stats)} platforms")
        except Exception as e:
            logger.debug(f"Model refresh: {e}")

    def _init_wework_bot(self) -> None:
        """Initialize the WeChat Work bot, wiring it to the knowledge base."""
        try:
            from .wechat_notifier import init_bot

            bot = init_bot(
                kb=getattr(self.world, 'knowledge_base', None),
                hub=self,
            )
            if bot.enabled:
                logger.info(
                    f"WeWork Bot connected: "
                    f"KB={'ready' if bot.kb else 'pending'}"
                )
        except Exception as e:
            logger.debug(f"WeWork Bot init skipped: {e}")

    async def _run_engine(self, message: str, mem_context: str = "", **kwargs) -> Any:
        """Protected engine execution with timeout + circuit breaker."""
        from ..core.task_guard import get_guard
        guard = get_guard()

        async def _run():
            return await self.engine.run(message, memory_context=mem_context, **kwargs)

        result = await guard.run("chat", _run, timeout=120, max_retries=1)
        if result.success:
            return result.data
        if result.timed_out:
            return {"response": "任务执行超时，请简化问题后重试。", "error": "timeout"}
        if result.circuit_open:
            return {"response": "系统繁忙，请稍后重试。", "error": "circuit_open"}
        return {"response": f"执行异常: {result.error[:200]}", "error": result.error}

    @property
    def model_registry(self):
        return getattr(self, "_model_registry", None)

