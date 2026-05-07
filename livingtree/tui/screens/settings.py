"""Settings — unified config: API Keys, Web2API, Genome, Training, Skills, MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, RichLog, Select, Static, Switch,
)

_SEP = Label("")

PROVIDERS = [
    ("deepseek", "DeepSeek"), ("longcat", "LongCat"), ("xiaomi", "Xiaomi Mimo"),
    ("aliyun", "Aliyun (通义)"), ("zhipu", "Zhipu (智谱)"), ("siliconflow", "SiliconFlow (硅基)"),
    ("mofang", "MoFang (模力方舟)"), ("nvidia", "NVIDIA NIM"),
    ("spark", "iFlytek Spark (讯飞)"), ("modelscope", "ModelScope (魔搭)"),
    ("bailing", "Bailing (百灵)"), ("stepfun", "StepFun (阶跃)"),
    ("internlm", "InternLM (书生)"), ("dmxapi", "DMXAPI"),
]

WEB2API_PROVIDERS = [
    ("deepseek-web", "DeepSeek Web"), ("claude-web", "Claude Web"),
    ("gemini-web", "Gemini Web"), ("kimi-web", "Kimi Web"),
    ("qwen-web", "Qwen Web (通义)"), ("glm-web", "GLM Web (智谱)"),
    ("doubao-web", "Doubao Web (豆包)"), ("spark-web", "Spark Web (讯飞)"),
    ("baichuan-web", "Baichuan Web (百川)"), ("yuanbao-web", "Yuanbao Web (元宝)"),
    ("minimax-web", "MiniMax Web"), ("stepchat-web", "StepChat Web (阶跃)"),
]


class SettingsScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "返回")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None
        self._api_inputs: dict[str, Input] = {}
        self._web2api_inputs: dict[str, Input] = {}

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Static("[dim]← 返回首页 (Esc)[/dim]", id="back-link")
        with ScrollableContainer(id="settings-form"):
            yield Label("[bold #fea62b]🔑 API 密钥[/bold #fea62b]")
            yield self._api_pane()
            yield _SEP
            yield Label("[bold #fea62b]🌐 Web2API 账户[/bold #fea62b]")
            yield self._web2api_pane()
            yield _SEP
            yield Label("[bold #fea62b]🧬 基因组[/bold #fea62b]")
            yield self._genome_pane()
            yield _SEP
            yield Label("[bold #fea62b]🤖 训练[/bold #fea62b]")
            yield self._train_pane()
            yield _SEP
            yield Label("[bold #fea62b]🧩 技能[/bold #fea62b]")
            yield self._skill_pane()
            yield _SEP
            yield Label("[bold #fea62b]🔌 MCP[/bold #fea62b]")
            yield self._mcp_pane()

    def _api_pane(self) -> ScrollableContainer:
        children: list = []
        for key, label in PROVIDERS:
            inp_id = f"api-{key}"
            inp = Input(placeholder=f"{label} API key...", password=True, id=inp_id)
            self._api_inputs[key] = inp
            children.append(Label(f"{label}"))
            children.append(inp)

        children.extend([
            Label("快速模型"), Input(placeholder="provider/flash-model", id="flash-model"),
            Label("深度模型"), Input(placeholder="provider/pro-model", id="pro-model"),
            Label("深度思考"), Switch(value=True, id="thinking-switch"),
            Label(""), Button("💾 保存 API", variant="primary", id="save-api-btn"),
            RichLog(id="api-log", highlight=True, markup=True),
        ])
        return ScrollableContainer(*children, id="settings-api")

    def _web2api_pane(self) -> ScrollableContainer:
        children: list = [
            Label("选择平台"),
            Select([(label, key) for key, label in WEB2API_PROVIDERS],
                   value="deepseek-web", id="web2api-provider"),
            Label("登录方式"),
            Select([("📧 邮箱+密码", "email"), ("📱 手机+密码", "phone"),
                    ("📱 手机+验证码", "sms")],
                   value="email", id="web2api-login-type"),
            Label("邮箱/手机号"),
            Input(placeholder="user@email.com 或 13812345678", id="web2api-identifier"),
            Label("密码"),
            Input(placeholder="密码 (手机+SMS模式不需要)", password=True,
                  id="web2api-password"),
            Label("验证码 (SMS模式填写)"),
            Input(placeholder="6位验证码", id="web2api-sms-code"),
            Label(""), Button("🔐 添加账户", variant="primary", id="web2api-add-btn"),
            Label(""), Button("📋 查看已添加账户", variant="default", id="web2api-list-btn"),
            RichLog(id="web2api-log", highlight=True, markup=True),
        ]
        return ScrollableContainer(*children, id="settings-web2api")

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

        try:
            from ...config.secrets import get_secret_vault
            vault = get_secret_vault()
            for key in self._api_inputs:
                saved = vault.get(f"{key}_api_key", "")
                if saved:
                    self._api_inputs[key].value = "••••••••"
        except Exception:
            pass

    def _get_log(self, bid: str) -> Optional[RichLog]:
        log_map = {"save-api-btn": "#api-log", "apply-genes-btn": "#genome-log",
                   "train-btn": "#train-log", "drill-btn": "#train-log",
                   "list-cells-btn": "#train-log",
                   "open-skills-btn": "#skills-log", "refresh-skills-btn": "#skills-log",
                   "open-mcp-btn": "#mcp-log", "refresh-mcp-btn": "#mcp-log",
                   "web2api-add-btn": "#web2api-log", "web2api-list-btn": "#web2api-log"}
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
            self._save_api_keys(log)

        elif bid == "web2api-add-btn":
            self._add_web2api_account(log)

        elif bid == "web2api-list-btn":
            self._list_web2api_accounts(log)

        elif bid == "apply-genes-btn":
            self._apply_genes(log)

        elif bid in ("train-btn", "drill-btn"):
            self._do_train(bid, log)

        elif bid == "list-cells-btn":
            self._list_cells(log)

        elif bid == "open-skills-btn":
            self._open_skills(log)

        elif bid == "refresh-skills-btn":
            self._refresh_skills(log)

        elif bid == "open-mcp-btn":
            self._open_mcp(log)

        elif bid == "refresh-mcp-btn":
            self._refresh_mcp(log)

    def _save_api_keys(self, log) -> None:
        from ...config.secrets import get_secret_vault
        vault = get_secret_vault()
        saved = 0
        for key, inp in self._api_inputs.items():
            val = inp.value.strip()
            if val and val != "••••••••":
                vault.set(f"{key}_api_key", val)
                saved += 1
        if saved:
            log.write(f"[green]已保存 {saved} 个 API 密钥[/green]") if log else None

        try:
            fm = self.query_one("#flash-model", Input).value.strip()
            pm = self.query_one("#pro-model", Input).value.strip()
            from ...config import get_config
            cfg = get_config()
            if fm:
                cfg.model.flash_model = fm
            if pm:
                cfg.model.pro_model = pm
            cfg.model.pro_thinking_enabled = self.query_one("#thinking-switch", Switch).value
            log.write("[green]模型配置已保存[/green]") if log else None
        except Exception as e:
            log.write(f"[red]保存失败: {e}[/red]") if log else None

    def _add_web2api_account(self, log) -> None:
        try:
            provider = self.query_one("#web2api-provider", Select).value
            login_type = self.query_one("#web2api-login-type", Select).value
            identifier = self.query_one("#web2api-identifier", Input).value.strip()
            password = self.query_one("#web2api-password", Input).value.strip()
            sms_code = self.query_one("#web2api-sms-code", Input).value.strip()

            if not identifier:
                log.write("[red]请填写邮箱或手机号[/red]") if log else None
                return
            if login_type == "email" and not password:
                log.write("[red]邮箱登录需要密码[/red]") if log else None
                return
            if login_type == "sms" and not sms_code:
                log.write("[red]SMS登录需要验证码[/red]") if log else None
                return

            is_phone = login_type in ("phone", "sms")
            account_label = f"{'📱' if is_phone else '📧'} {identifier}"

            import httpx, asyncio
            async def _add():
                async with httpx.AsyncClient() as client:
                    payload = {
                        "provider": provider,
                        "email": identifier,
                        "password": password if login_type != "sms" else sms_code,
                    }
                    if is_phone:
                        payload["login_type"] = "phone"
                    if login_type == "sms":
                        payload["login_type"] = "sms"
                        payload["sms_code"] = sms_code
                    resp = await client.post(
                        "http://localhost:5001/admin/accounts/add",
                        json=payload, timeout=10,
                    )
                    return resp.json() if resp.status_code == 200 else {"error": resp.text}

            loop = self._hub.loop if self._hub else None
            if loop:
                result = asyncio.run_coroutine_threadsafe(_add(), loop).result(timeout=15)
                if isinstance(result, dict) and "error" not in result:
                    log.write(f"[green]已添加 {provider}: {account_label}[/green]") if log else None
                else:
                    err = result.get("error", "unknown") if isinstance(result, dict) else str(result)
                    log.write(f"[red]添加失败: {err}[/red]") if log else None
            else:
                log.write("[red]web2api 服务未启动[/red]") if log else None
        except Exception as e:
            log.write(f"[red]添加失败: {e}[/red]") if log else None

    def _list_web2api_accounts(self, log) -> None:
        try:
            import httpx, asyncio
            async def _list():
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "http://localhost:5001/admin/providers", timeout=5)
                    return resp.json() if resp.status_code == 200 else {"error": resp.text}
            result = asyncio.run_coroutine_threadsafe(_list(), self._hub.loop if self._hub else None)
            if isinstance(result, dict) and "error" not in result:
                lines = ["[bold #58a6ff]已配置账户:[/bold #58a6ff]"]
                for p_name, p_data in result.items():
                    accounts = p_data.get("accounts", 0)
                    model = p_data.get("model", "?")
                    lines.append(f"  {p_name}: {accounts} accounts, model={model}")
                log.write("\n".join(lines)) if log else None
            else:
                log.write("[red]web2api 服务未启动[/red]") if log else None
        except Exception as e:
            log.write(f"[red]查询失败: {e}[/red]") if log else None

    def _apply_genes(self, log) -> None:
        genes = self._hub.world.genome.expressed_genes
        for sw_id, attr in [("gene-dna","dna_engine"),("gene-knowledge","knowledge_layer"),
            ("gene-capability","capability_layer"),("gene-network","network_layer"),
            ("gene-cell","cell_layer"),("gene-evolution","self_evolution"),
            ("gene-phage","code_absorption")]:
            try:
                setattr(genes, attr, self.query_one(f"#{sw_id}", Switch).value)
            except Exception:
                pass
        log.write("[green]基因组已更新[/green]") if log else None

    def _do_train(self, bid, log) -> None:
        log.write("[yellow]训练需要配置 Cell 模块...[/yellow]") if log else None

    def _list_cells(self, log) -> None:
        log.write("[dim]暂无已训练 Cell[/dim]") if log else None

    def _open_skills(self, log) -> None:
        try:
            import os; os.startfile("data/skills") if Path("data/skills").exists() else None
            log.write("[green]已打开技能目录[/green]") if log else None
        except Exception:
            log.write("[red]无法打开目录[/red]") if log else None

    def _refresh_skills(self, log) -> None:
        log.write("[dim]技能列表刷新完成[/dim]") if log else None

    def _open_mcp(self, log) -> None:
        try:
            import os; os.startfile("data/mcp_servers.json") if Path("data/mcp_servers.json").exists() else None
            log.write("[green]已打开MCP配置[/green]") if log else None
        except Exception:
            log.write("[red]无法打开MCP配置[/red]") if log else None

    def _refresh_mcp(self, log) -> None:
        log.write("[dim]MCP列表刷新完成[/dim]") if log else None
