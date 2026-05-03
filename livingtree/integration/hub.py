"""IntegrationHub — Single boot point for the LivingTree digital life form.

Creates LivingWorld, wires all subsystems, starts services, and exposes
the unified API surface. No scattered DI — everything through the world.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

import aiohttp
from loguru import logger

from ..config import LTAIConfig, get_config
from ..observability import setup_observability


class IntegrationHub:
    """Single entry point — boots the entire living system.

    Usage:
        hub = IntegrationHub()
        await hub.start()
        result = await hub.chat("帮我生成环评报告")
    """

    def __init__(self, config: Optional[LTAIConfig] = None):
        # Lazy imports — only load heavy subsystems on construction
        from ..dna import LifeEngine, LivingWorld, DualModelConsciousness, SafetyGuard
        from ..cell import CellRegistry, CellTrainer, TrainingConfig, Distillation, ExpertConfig
        from ..cell import Mitosis, Phage, Regen, SwiftDrillTrainer
        from ..knowledge import KnowledgeBase, VectorStore, KnowledgeGraph, FormatDiscovery, GapDetector
        from ..capability import SkillFactory, ToolMarket, DocEngine, CodeEngine, MaterialCollector
        from ..capability import CodeGraph, ASTParser
        from ..network import Node, Discovery, NATTraverser, Reputation, EncryptedChannel
        from ..execution import TaskPlanner, Orchestrator, SelfHealer
        from ..execution import MultiAgentQualityChecker
        from ..execution import HumanInTheLoop, TaskCheckpoint, CostAware

        self.config = config or get_config()
        self.obs = setup_observability(self.config)
        self._session = aiohttp.ClientSession()  # shared session

        # ── Build the world ──
        self.world = LivingWorld(
            consciousness=DualModelConsciousness(
                flash_model=self.config.model.flash_model,
                pro_model=self.config.model.pro_model,
                api_key=self.config.model.deepseek_api_key,
                base_url=self.config.model.deepseek_base_url,
                thinking_enabled=self.config.model.pro_thinking_enabled,
            ),
            safety=SafetyGuard(workspace=str(Path.cwd())),
        )

        # Wire sandbox audit reference
        self.world.safety.sandbox.audit = self.world.safety.audit

        # Wire all subsystems
        self.world.wire(
            cell_registry=CellRegistry(),
            cell_trainer=CellTrainer(config=TrainingConfig(
                lora_r=self.config.cell.lora_r, lora_alpha=self.config.cell.lora_alpha,
                lora_dropout=self.config.cell.lora_dropout, learning_rate=self.config.cell.learning_rate,
            )),
            distillation=Distillation(),
            expert_config=ExpertConfig(
                model=self.config.model.pro_model,
                api_key=self.config.model.deepseek_api_key,
            ),
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
            encrypted_channel=EncryptedChannel(
                node_id="", shared_secret=self.config.network.shared_secret,
            ),
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

        # Wire code graph and AST parser
        self.world.code_graph = CodeGraph()
        self.world.ast_parser = ASTParser()

        # Wire genome into knowledge base for policy control
        self.world.knowledge_base.genome = self.world.genome

        # Wire HITL + Checkpoint + CostAware
        self.world.hitl = HumanInTheLoop(default_timeout=300.0)
        self.world.checkpoint = TaskCheckpoint(store_path="./data/checkpoints")
        self.world.cost_aware = CostAware(daily_budget_tokens=1_000_000)

        # Register seed physics models into ToolMarket (all else discovered at runtime)
        from ..capability.tool_market import register_seed_tools
        self.world.tool_market.set_world(self.world)
        register_seed_tools(self.world.tool_market)

        # Wire LearningEngine
        from ..knowledge.learning_engine import TemplateLearner, SkillDiscoverer, RoleGenerator
        self.world.template_learner = TemplateLearner(
            kb=self.world.knowledge_base,
            distillation=self.world.distillation,
            expert_config=self.world.expert_config,
        )
        self.world.skill_discoverer = SkillDiscoverer(
            phage=self.world.phage,
            skill_factory=self.world.skill_factory,
            ast_parser=self.world.ast_parser,
            kb=self.world.knowledge_base,
        )
        self.world.role_generator = RoleGenerator(
            distillation=self.world.distillation,
            expert_config=self.world.expert_config,
            kb=self.world.knowledge_base,
        )

        # ── Create engine (receives the world) ──
        self.engine = LifeEngine(self.world)

        # ── Boot LifeDaemon for autonomous self-driven cycles ──
        from ..dna.life_daemon import LifeDaemon
        self.daemon = LifeDaemon(self.world, interval_minutes=30.0)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        logger.info(f"🌳 LivingTree v{self.config.version} booting")
        logger.info(f"  Flash: {self.config.model.flash_model} | Pro: {self.config.model.pro_model}")
        logger.info(f"  Node: {self.world.node.info.name} ({self.world.node.info.id[:12]})")

        await self._register_health_checks()
        await self.world.self_healer.start()
        await self.world.node.register()
        asyncio.create_task(self.world.node.heartbeat(self.config.network.heartbeat_interval))
        self._register_agents()

        self._started = True
        await self.daemon.start()
        logger.info("🌳 LivingTree online — autonomous cycles active")

        # Print startup narrative
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
        await self._session.close()
        self._started = False
        logger.info("🌳 LivingTree offline")

    # ── Core API ──

    async def chat(self, message: str, **kwargs) -> dict[str, Any]:
        if not self._started:
            await self.start()
        self.world.metrics.life_cycles.inc()
        ctx = await self.engine.run(message, **kwargs)
        return {
            "session_id": ctx.session_id,
            "intent": ctx.intent,
            "plan": ctx.plan,
            "execution_results": ctx.execution_results,
            "reflections": ctx.reflections,
            "quality": ctx.quality_reports,
            "generation": self.world.genome.generation,
            "success_rate": ctx.metadata.get("success_rate", 0),
        }

    async def generate_report(self, template: str, data: dict,
                              requirements: dict | None = None) -> dict:
        de = self.world.doc_engine
        result = await de.generate_report(template, data, requirements or {})
        doc = await de.auto_format(result["document"])
        path = await de.export_to(doc, self.config.doc_engine.default_format)
        return {**result, "path": str(path), "formatted": doc}

    async def train_cell(self, name: str, data: list[dict], epochs: int = 3) -> dict:
        from ..cell import CellAI
        cell = CellAI(name=name, model_name=self.config.cell.default_base_model)
        result = cell.train(data, epochs=epochs)
        self.world.cell_registry.register(cell)
        return result

    async def drill_train(self, cell_name: str, model: str, dataset: list[dict],
                          training_type: str = "lora", teacher: str = "",
                          reward: str = "") -> dict:
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

        return {
            "success": r.success, "loss": r.loss, "eval_loss": r.eval_loss,
            "model_path": r.model_path, "metrics": r.metrics,
            "training_time": r.training_time_seconds, "error": r.error,
        }

    async def drill_evaluate(self, model_path: str, benchmarks: list[str] | None = None) -> dict:
        return await self.world.drill.evaluate(model_path, benchmarks)

    async def drill_quantize(self, model_path: str, method: str = "awq") -> dict:
        r = await self.world.drill.quantize(model_path, method)
        return {"success": r.success, "model_path": r.model_path, "error": r.error}

    async def drill_deploy(self, model_path: str, port: int = 8000) -> dict:
        return await self.world.drill.deploy(model_path, port)

    async def download_model(self, model_id: str) -> str:
        return await self.world.drill.download_model(model_id)

    async def distill_knowledge(self, prompts: list[str]) -> list[str]:
        from ..cell import CellAI
        cell = CellAI(name="distill")
        results = await self.world.distillation.distill_knowledge(
            cell, prompts, self.world.expert_config,
        )
        self.world.cell_registry.register(cell)
        return results

    async def absorb_github(self, url: str) -> dict:
        from ..cell import CellAI
        cell = CellAI(name=f"phage_{url.split('/')[-1][:20]}")
        return await self.world.phage.absorb_codebase(cell, url)

    async def index_codebase(self, path: str = ".") -> dict:
        """Build the code knowledge graph for a project."""
        stats = self.world.code_graph.index(path)
        self.world.code_graph.save()
        return {
            "files": stats.total_files, "entities": stats.total_entities,
            "edges": stats.total_edges, "languages": stats.languages,
            "build_time_ms": stats.build_time_ms,
        }

    def blast_radius(self, files: list[str]) -> list[dict]:
        """Get files affected by changes (blast-radius analysis)."""
        results = self.world.code_graph.blast_radius(files)
        return [{"file": r.file, "reason": r.reason, "risk": r.risk} for r in results]

    async def discover_peers(self) -> list[dict]:
        peers = await self.world.discovery.discover_lan()
        return [p.model_dump() for p in peers]

    async def generate_code(self, name: str, description: str, domain: str = "general") -> dict:
        from ..capability.code_engine import CodeSpec
        code = await self.world.code_engine.generate_with_annotation(
            CodeSpec(name=name, description=description, domain=domain)
        )
        return {
            "name": code.name, "language": code.language, "code": code.code,
            "annotations": code.annotations, "formula": code.formula,
            "quality": code.quality_score, "safety": code.safety_score,
        }

    def status(self) -> dict:
        return {
            "version": self.config.version,
            "online": self._started,
            "engine": self.engine.status(),
            "cells": len(self.world.cell_registry.discover()),
            "network": self.world.node.get_status(),
            "orchestrator": self.world.orchestrator.get_status(),
            "healer": self.world.self_healer.get_status(),
            "audit": self.world.safety.summary(),
        }

    def audit_summary(self) -> dict:
        return self.world.safety.summary()

    def verify_audit_chain(self) -> dict:
        valid, idx = self.world.safety.verify_audit()
        return {"valid": valid, "first_broken_index": idx, "total_entries": len(self.world.safety.audit.entries)}

    # ── Internal ──

    def _register_agents(self) -> None:
        """Register minimal seed agents. Full roles generated dynamically from tasks."""
        from ..execution import AgentSpec, AgentRole
        seeds = [
            ("analyst", ["analyst"], ["analysis", "reasoning", "tool_use"]),
            ("executor", ["executor"], ["execution", "code_gen", "tool_use"]),
            ("collector", ["collector"], ["web_search", "file_read", "knowledge_query"]),
        ]
        for name, roles, caps in seeds:
            self.world.orchestrator.register_agent(AgentSpec(
                name=name,
                roles=[AgentRole(name=r, capabilities=caps) for r in roles],
            ))

    async def _register_health_checks(self) -> None:
        async def _check_kb() -> tuple[bool, dict]:
            try:
                docs = self.world.knowledge_base.get_by_domain(None)
                return True, {"docs": len(docs)}
            except Exception as e:
                return False, {"error": str(e)}

        async def _check_cells() -> tuple[bool, dict]:
            try:
                cells = self.world.cell_registry.discover()
                return True, {"cells": len(cells)}
            except Exception as e:
                return False, {"error": str(e)}

        async def _check_network() -> tuple[bool, dict]:
            try:
                s = self.world.node.get_status()
                return s.get("status") == "online", s
            except Exception as e:
                return False, {"error": str(e)}

        for name, fn in [("kb", _check_kb), ("cells", _check_cells), ("network", _check_network)]:
            self.world.self_healer.register_check(name, fn)
