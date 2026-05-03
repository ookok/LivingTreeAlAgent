"""Settings — Configuration + Cell training hub.

Integrated commands: train_cell, drill_train, absorb_codebase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, RichLog, Select, Static, Switch,
)


TRAINING_TYPES = [("lora", "LoRA"), ("full", "Full"), ("distill", "Distill"), ("grpo", "GRPO")]


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(
            Static("[bold]Configuration[/bold]", id="settings-title"),

            Label("API Key"),
            Input(placeholder="sk-... (encrypted)", password=True, id="settings-api-key"),
            Label("Flash Model"),
            Input(placeholder="provider/flash-model", id="settings-flash"),
            Label("Pro Model"),
            Input(placeholder="provider/pro-model", id="settings-pro"),
            Label("Pro Thinking"),
            Switch(value=True, id="settings-thinking"),
            Label("Workspace"),
            Input(placeholder=str(Path.cwd()), id="settings-workspace"),
            Label(""),
            Horizontal(
                Button("Save", variant="primary", id="save-btn"),
                Button("Reload", variant="default", id="reload-btn"),
                id="config-buttons",
            ),

            Static("[bold]Genome Gene Expression[/bold]", id="genome-title"),
            Label("DNA Engine (环境/安全)"),
            Switch(value=True, id="gene-dna"),
            Label("Knowledge Layer (知识库)"),
            Switch(value=True, id="gene-knowledge"),
            Label("Capability Layer (技能/工具)"),
            Switch(value=True, id="gene-capability"),
            Label("Network Layer (P2P网络)"),
            Switch(value=True, id="gene-network"),
            Label("Cell Layer (细胞AI训练)"),
            Switch(value=True, id="gene-cell"),
            Label("Self Evolution (自主进化)"),
            Switch(value=False, id="gene-evolution"),
            Label("Code Absorption (代码吞噬)"),
            Switch(value=False, id="gene-phage"),
            Label(""),
            Horizontal(
                Button("Apply Genes", variant="primary", id="apply-genes-btn"),
                id="genome-buttons",
            ),

            Static("[bold]Cell Training[/bold]", id="train-title"),
            Label("Cell Name"),
            Input(placeholder="my_expert_cell", id="cell-name"),
            Label("Model (ModelScope ID)"),
            Input(placeholder="Qwen/Qwen3.5-4B", id="cell-model"),
            Label("Training Type"),
            Select(TRAINING_TYPES, prompt="Type", value="lora", id="train-type"),
            Label("Codebase Path"),
            Input(placeholder="./path/to/repo", id="codebase-path"),
            Label(""),
            Horizontal(
                Button("Train Cell", variant="primary", id="train-btn"),
                Button("Drill Train", variant="primary", id="drill-btn"),
                Button("Absorb Code", variant="primary", id="absorb-btn"),
                Button("List Cells", variant="default", id="list-cells-btn"),
                id="train-buttons",
            ),
            RichLog(id="settings-log", highlight=True, markup=True),
            id="settings-form",
        )

    def on_mount(self) -> None:
        self._load()
        log = self.query_one("#settings-log", RichLog)
        log.write("[green]Settings loaded[/green]")

    def _load(self) -> None:
        if not self._hub or not hasattr(self._hub, 'config'):
            return
        c = self._hub.config
        try:
            self.query_one("#settings-flash", Input).value = c.model.flash_model
            self.query_one("#settings-pro", Input).value = c.model.pro_model
            self.query_one("#settings-thinking", Switch).value = c.model.pro_thinking_enabled
            # Load genome
            genes = self._hub.world.genome.expressed_genes
            self.query_one("#gene-dna", Switch).value = genes.dna_engine
            self.query_one("#gene-knowledge", Switch).value = genes.knowledge_layer
            self.query_one("#gene-capability", Switch).value = genes.capability_layer
            self.query_one("#gene-network", Switch).value = genes.network_layer
            self.query_one("#gene-cell", Switch).value = genes.cell_layer
            self.query_one("#gene-evolution", Switch).value = genes.self_evolution
            self.query_one("#gene-phage", Switch).value = genes.code_absorption
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        log = self.query_one("#settings-log", RichLog)
        btn = event.button.id

        if btn == "save-btn":
            key = self.query_one("#settings-api-key", Input).value
            if key and self._hub:
                from ...config.secrets import get_secret_vault
                get_secret_vault().set("deepseek_api_key", key)
                log.write("[green]Key encrypted & saved[/green]")
            log.write("[green]Saved[/green]")

        elif btn == "reload-btn":
            self._load()
            log.write("[green]Reloaded[/green]")

        elif btn == "train-btn":
            self.cmd_train_cell()
        elif btn == "drill-btn":
            self.cmd_drill_train()
        elif btn == "absorb-btn":
            self.cmd_absorb_codebase()
        elif btn == "list-cells-btn":
            if self._hub:
                cells = self._hub.world.cell_registry.discover()
                log.write(f"[bold]Cells: {len(cells)}[/bold]")
                for c in cells:
                    name = getattr(c, 'name', str(c)[:30])
                    log.write(f"  {name}")

        elif btn == "apply-genes-btn":
            self._apply_genes()

    # ── Tool commands ──

    async def cmd_train_cell(self) -> None:
        log = self.query_one("#settings-log", RichLog)
        name = self.query_one("#cell-name", Input).value.strip()
        if not name:
            log.write("[yellow]Enter cell name[/yellow]")
            return
        if self._hub:
            from ...cell.cell_ai import CellAI
            cell = CellAI(name=name)
            self._hub.world.cell_registry.register(cell)
            log.write(f"[green]Cell '{name}' registered[/green]")

    async def cmd_drill_train(self) -> None:
        log = self.query_one("#settings-log", RichLog)
        name = self.query_one("#cell-name", Input).value.strip()
        model = self.query_one("#cell-model", Input).value.strip()
        ttype = str(self.query_one("#train-type", Select).value or "lora")
        if not name or not model:
            log.write("[yellow]Enter cell name and model[/yellow]")
            return
        if self._hub:
            r = await self._hub.drill_train(name, model, [], ttype)
            log.write(f"[green]Drill: {'OK' if r.get('success') else 'FAIL'} loss={r.get('loss', 'N/A')}[/green]")

    async def cmd_absorb_codebase(self) -> None:
        log = self.query_one("#settings-log", RichLog)
        path = self.query_one("#codebase-path", Input).value.strip()
        if not path:
            log.write("[yellow]Enter codebase path[/yellow]")
            return
        if self._hub:
            r = await self._hub.absorb_github(path)
            log.write(f"[green]Absorbed: {r.get('functions_found', 0)} functions[/green]")

    def _apply_genes(self) -> None:
        """Apply genome gene expression changes from switches."""
        log = self.query_one("#settings-log", RichLog)
        if not self._hub:
            return
        genes = self._hub.world.genome.expressed_genes
        genes.dna_engine = self._get_switch("gene-dna")
        genes.knowledge_layer = self._get_switch("gene-knowledge")
        genes.capability_layer = self._get_switch("gene-capability")
        genes.network_layer = self._get_switch("gene-network")
        genes.cell_layer = self._get_switch("gene-cell")
        genes.self_evolution = self._get_switch("gene-evolution")
        genes.code_absorption = self._get_switch("gene-phage")
        self._hub.world.genome.add_mutation(
            f"Gene expression toggled: dna={genes.dna_engine} kb={genes.knowledge_layer}",
            source="ui_settings",
        )
        log.write(f"[green]Genes applied (gen {self._hub.world.genome.generation})[/green]")

    def _get_switch(self, switch_id: str) -> bool:
        try:
            return self.query_one(f"#{switch_id}", Switch).value
        except Exception:
            return True

    async def refresh(self) -> None:
        self._load()
