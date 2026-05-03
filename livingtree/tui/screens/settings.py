"""Settings — unified config: API, Genome, Training, Skills, MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, RichLog, Select, Switch, TabbedContent, TabPane,
)


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        with TabbedContent(id="settings-tabs"):
            with TabPane("🔑 API"):
                yield self._api_pane()
            with TabPane("🧬 基因组"):
                yield self._genome_pane()
            with TabPane("🤖 训练"):
                yield self._train_pane()
            with TabPane("🧩 技能"):
                yield self._skill_pane()
            with TabPane("🔌 MCP"):
                yield self._mcp_pane()

    def _api_pane(self) -> ScrollableContainer:
        return ScrollableContainer(
            Label("API 密钥"), Input(placeholder="sk-... (加密)", password=True, id="api-key"),
            Label("快速模型"), Input(placeholder="provider/flash-model", id="flash-model"),
            Label("深度模型"), Input(placeholder="provider/pro-model", id="pro-model"),
            Label("深度思考"), Switch(value=True, id="thinking-switch"),
            Label(""), Button("💾 保存", variant="primary", id="save-api-btn"),
            RichLog(id="api-log", highlight=True, markup=True),
            id="settings-api",
        )

    def _genome_pane(self) -> ScrollableContainer:
        genes = ["DNA引擎(环境/安全)","知识层","能力层(技能/工具)","网络层(P2P)","细胞层(AI训练)","自主进化","代码吞噬"]
        ids = ["gene-dna","gene-knowledge","gene-capability","gene-network","gene-cell","gene-evolution","gene-phage"]
        children = []
        for g, i in zip(genes, ids):
            children.extend([Label(g), Switch(value=True, id=i)])
        children.extend([Label(""), Button("🧬 应用基因", variant="primary", id="apply-genes-btn")])
        children.append(RichLog(id="genome-log", highlight=True, markup=True))
        return ScrollableContainer(*children, id="settings-genome")

    def _train_pane(self) -> ScrollableContainer:
        return ScrollableContainer(
            Label("细胞名称"), Input(placeholder="my_cell", id="cell-name"),
            Label("模型ID"), Input(placeholder="Qwen/Qwen3.5-4B", id="cell-model"),
            Label("训练类型"), Select([("LoRA","lora"),("全参","full"),("蒸馏","distill"),("GRPO","grpo")], value="lora", id="train-type"),
            Label(""), Horizontal(
                Button("🚀 训练", variant="primary", id="train-btn"),
                Button("🧪 Drill", variant="primary", id="drill-btn"),
                Button("📋 列表", variant="default", id="list-cells-btn"),
            ),
            RichLog(id="train-log", highlight=True, markup=True),
            id="settings-train",
        )

    def _skill_pane(self) -> ScrollableContainer:
        return ScrollableContainer(
            Label("技能管理 — data/skills/*.md (SKILL.md 格式)"), Label(""),
            Button("📂 打开技能目录", variant="default", id="open-skills-btn"),
            Button("🔄 刷新技能列表", variant="default", id="refresh-skills-btn"),
            RichLog(id="skills-log", highlight=True, markup=True),
            id="settings-skills",
        )

    def _mcp_pane(self) -> ScrollableContainer:
        return ScrollableContainer(
            Label("MCP 服务器配置 — data/mcp_servers.json"), Label(""),
            Button("📂 打开MCP配置", variant="default", id="open-mcp-btn"),
            Button("🔄 刷新MCP列表", variant="default", id="refresh-mcp-btn"),
            RichLog(id="mcp-log", highlight=True, markup=True),
            id="settings-mcp",
        )

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        if not self._hub:
            return
        c = self._hub.config
        try:
            self.query_one("#flash-model", Input).value = c.model.flash_model
            self.query_one("#pro-model", Input).value = c.model.pro_model
            self.query_one("#thinking-switch", Switch).value = c.model.pro_thinking_enabled
        except Exception:
            pass

    def _get_log(self, bid: str) -> Optional[RichLog]:
        log_map = {"save-api-btn": "#api-log", "apply-genes-btn": "#genome-log",
                   "train-btn": "#train-log", "drill-btn": "#train-log",
                   "list-cells-btn": "#train-log",
                   "open-skills-btn": "#skills-log", "refresh-skills-btn": "#skills-log",
                   "open-mcp-btn": "#mcp-log", "refresh-mcp-btn": "#mcp-log"}
        wid = log_map.get(bid)
        if wid:
            try:
                return self.query_one(wid, RichLog)
            except Exception:
                pass
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        log = self._get_log(bid)

        if bid == "save-api-btn":
            key = self.query_one("#api-key", Input).value
            if key:
                from ...config.secrets import get_secret_vault
                get_secret_vault().set("deepseek_api_key", key)
            log.write("[green]已保存[/green]") if log else None

        elif bid == "apply-genes-btn":
            genes = self._hub.world.genome.expressed_genes
            for sw_id, attr in [("gene-dna","dna_engine"),("gene-knowledge","knowledge_layer"),
                ("gene-capability","capability_layer"),("gene-network","network_layer"),
                ("gene-cell","cell_layer"),("gene-evolution","self_evolution"),
                ("gene-phage","code_absorption")]:
                try:
                    setattr(genes, attr, self.query_one(f"#{sw_id}", Switch).value)
                except Exception:
                    pass
            self._hub.world.genome.add_mutation("基因表达已切换", source="ui")
            log.write(f"[green]基因组已应用 (第{self._hub.world.genome.generation}代)[/green]") if log else None

        elif bid == "train-btn":
            name = self.query_one("#cell-name", Input).value.strip()
            if name and self._hub:
                from ...cell.cell_ai import CellAI
                cell = CellAI(name=name)
                self._hub.world.cell_registry.register(cell)
            log.write(f"[green]细胞 '{name}' 已注册[/green]") if log else None

        elif bid == "drill-btn":
            log.write("[yellow]MS-SWIFT 需要安装 ms-swift[/yellow]") if log else None

        elif bid == "list-cells-btn":
            cells = self._hub.world.cell_registry.discover()
            for c in cells[:20]:
                log.write(f"  {getattr(c,'name',str(c)[:30])}") if log else None

        elif bid in ("open-skills-btn", "refresh-skills-btn"):
            import os
            os.startfile("data/skills") if os.path.exists("data/skills") else None
            log.write("[green]技能目录: data/skills/[/green]") if log else None

        elif bid in ("open-mcp-btn", "refresh-mcp-btn"):
            import json
            try:
                config = json.loads(Path("data/mcp_servers.json").read_text())
                servers = list(config.get("mcpServers", {}).keys())
                log.write(f"[green]MCP 服务器 ({len(servers)}): {', '.join(servers[:10])}[/green]") if log else None
            except Exception:
                log.write("[yellow]MCP 配置不存在[/yellow]") if log else None

    async def refresh(self, **kwargs) -> None:
        self._load()
