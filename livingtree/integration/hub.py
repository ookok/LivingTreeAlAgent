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
    """Progressive boot: minimal __init__ for instant UI, heavy init in start()."""

    def __init__(self, config: Optional[LTAIConfig] = None):
        # Phase 1: Truly minimal — instant from any thread
        self.config = config or get_config()
        self.obs = setup_observability(self.config)
        self._session = None
        self._started = False
        self._phase = 0
        self.world = None
        self.engine = None
        self.daemon = None

        # Auto-wired new modules (Phase 1 — instant constructors)
        self.cache_optimizer = None
        self.side_git = None
        self.session_manager = None
        self.lsp_manager = None
        self.sub_agent_roles = None
        self.rlm_runner = None
        self.sse_server = None
        self.struct_memory = None
        self.extraction_engine = None

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

        # ── Auto-wire new modules ──
        from ..dna.cache_optimizer import CacheOptimizer
        self.cache_optimizer = CacheOptimizer(
            max_tokens=1_000_000,
            cache_budget=0.85,
        )
        self.world.cache_optimizer = self.cache_optimizer

        from ..execution.side_git import SideGit
        self.side_git = SideGit(workspace=str(Path.cwd()))
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
        except Exception:
            pass

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
        providers = self.world.opencode_bridge.discover_for_election()
        if providers:
            logger.info(f"OpenCode bridge: {len(providers)} providers available")
            self.world.opencode_providers = providers
        else:
            self.world.opencode_providers = []
            logger.debug("OpenCode bridge: no external providers found")

        from ..dna.life_daemon import LifeDaemon
        self.daemon = LifeDaemon(self.world, interval_minutes=30.0)

    async def _init_async(self) -> None:
        """Async initialization — health checks, node register, daemon start."""
        logger.info(f"  Flash: {self.config.model.flash_model} | Pro: {self.config.model.pro_model}")
        logger.info(f"  Node: {self.world.node.info.name} ({self.world.node.info.id[:12]})")

        await self._register_health_checks()
        await self.world.self_healer.start()
        await self.world.node.register()
        asyncio.create_task(self.world.node.heartbeat(self.config.network.heartbeat_interval))
        self._register_agents()

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
        await self.daemon.start()
        logger.info("🌳 LivingTree online — autonomous cycles active")

        story = self.daemon._advanced.full_narrative()
        for line in story.split("\n"):
            if line.strip():
                logger.info(line)

    async def shutdown(self) -> None:
        if not self._started:
            return
        logger.info("Shutting down...")
        await self.daemon.stop()
        await self.world.self_healer.stop()
        await self.world.node.shutdown()
        if self._session:
            await self._session.close()
        self._started = False
        logger.info("🌳 LivingTree offline")

    async def chat(self, message: str, **kwargs) -> dict[str, Any]:
        if not self._started:
            await self.start()
        self.world.metrics.life_cycles.inc()

        pipe_keywords = ["提取", "汇总", "去重", "排序", "过滤", "筛选", "合并",
                         "extract", "summarize", "dedup", "sort", "filter", "merge",
                         "pipeline", "管道", "处理这些文档", "分析这些文件"]
        if self.world.pipeline_engine and any(kw in message.lower() for kw in pipe_keywords):
            try:
                pipe_result = await self.world.pipeline_engine.run_nl(message)
                return {
                    "mode": "pipeline",
                    "pipeline": pipe_result.get("generated_pipeline", {}),
                    "results": pipe_result.get("results", [])[:20],
                    "stats": {
                        "steps": pipe_result.get("steps_executed", 0),
                        "outputs": pipe_result.get("output_count", 0),
                    },
                }
            except Exception as e:
                logger.debug(f"Pipeline auto-dispatch: {e}")

        mem_context = ""
        if self.struct_memory:
            try:
                entries, synthesis = await self.struct_memory.retrieve_for_query(message)
                mem_context = self.struct_memory.get_context_block(message, entries, synthesis)
            except Exception:
                pass

        ctx = await self.engine.run(message, memory_context=mem_context, **kwargs)

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
            except Exception:
                pass

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
