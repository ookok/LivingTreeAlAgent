"""Cell training mixin for IntegrationHub — extracted from hub.py.

Provides cell training, knowledge distillation, code indexing, and
GitHub absorption methods for the integration hub.
"""

from __future__ import annotations

from typing import Any


class CellTrainingMixin:
    """Mixin providing cell/drill training methods to IntegrationHub."""

    async def train_cell(self: Any, name: str, data: list[dict], epochs: int = 3) -> dict:
        if not self._started: await self.start()
        from ..cell import CellAI
        cell = CellAI(name=name, model_name=self.config.cell.default_base_model)
        result = cell.train(data, epochs=epochs)
        self.world.cell_registry.register(cell)
        return result

    async def drill_train(self: Any, cell_name: str, model: str, dataset: list[dict],
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
        return {"success": r.success, "loss": r.loss, "eval_loss": r.eval_loss,
                "model_path": r.model_path, "metrics": r.metrics,
                "training_time": r.training_time_seconds, "error": r.error}

    async def drill_evaluate(self: Any, model_path: str, benchmarks: list[str] | None = None) -> dict:
        if not self._started: await self.start()
        return await self.world.drill.evaluate(model_path, benchmarks)

    async def drill_quantize(self: Any, model_path: str, method: str = "awq") -> dict:
        if not self._started: await self.start()
        r = await self.world.drill.quantize(model_path, method)
        return {"success": r.success, "model_path": r.model_path, "error": r.error}

    async def drill_deploy(self: Any, model_path: str, port: int = 8000) -> dict:
        if not self._started: await self.start()
        return await self.world.drill.deploy(model_path, port)

    async def download_model(self: Any, model_id: str) -> str:
        if not self._started: await self.start()
        return await self.world.drill.download_model(model_id)

    async def distill_knowledge(self: Any, prompts: list[str]) -> list[str]:
        if not self._started: await self.start()
        from ..cell import CellAI
        cell = CellAI(name="distill")
        results = await self.world.distillation.distill_knowledge(cell, prompts, self.world.expert_config)
        self.world.cell_registry.register(cell)
        return results

    async def absorb_github(self: Any, url: str) -> dict:
        if not self._started: await self.start()
        from ..cell import CellAI
        cell = CellAI(name=f"phage_{url.split('/')[-1][:20]}")
        return await self.world.phage.absorb_codebase(cell, url)

    async def index_codebase(self: Any, path: str = ".") -> dict:
        if not self._started: await self.start()
        stats = self.world.code_graph.index(path)
        self.world.code_graph.save()
        return {"files": stats.total_files, "entities": stats.total_entities,
                "edges": stats.total_edges, "languages": stats.languages,
                "build_time_ms": stats.build_time_ms}

    def blast_radius(self: Any, files: list[str]) -> list[dict]:
        results = self.world.code_graph.blast_radius(files)
        return [{"file": r.file, "reason": r.reason, "risk": r.risk} for r in results]


__all__ = ["CellTrainingMixin"]
