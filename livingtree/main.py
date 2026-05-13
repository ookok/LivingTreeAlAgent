"""LivingTree AI Agent — Unified CLI Entry Point (CowAgent-inspired)

Usage:
    python -m livingtree                  # Start web server (default)
    python -m livingtree start            # Background start (daemon)
    python -m livingtree stop              # Stop background service
    python -m livingtree restart           # Restart service
    python -m livingtree status            # Service status
    python -m livingtree logs              # View recent logs
    python -m livingtree update            # Git pull + restart
    python -m livingtree web               # Web server with UI
    python -m livingtree server            # API server only
    python -m livingtree client            # Interactive CLI chat
    python -m livingtree test              # Integration tests
    python -m livingtree check             # Environment check
    python -m livingtree skill install X   # Install a skill
    python -m livingtree skill list        # List installed skills
    python -m livingtree channel X         # Set channel (weixin/feishu/...)
    python -m livingtree config            # Show/edit config
    python -m livingtree relay             # Start relay server
    --version, -v                          # Show version
    --help, -h                             # Show this help
"""

import sys
import os
import subprocess
import json as _json

VERSION = "2.2.0"
PID_FILE = ".livingtree/server.pid"
LOG_FILE = ".livingtree/server.log"


def main():
    if len(sys.argv) < 2:
        _start_web()
        return

    command = sys.argv[1].lower()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    if command in ("--version", "-v", "version"):
        print(f"LivingTree AI Agent v{VERSION}")
        return

    if command in ("--help", "-h", "help"):
        _print_usage()
        return

    # ═══ CLI Management (CowAgent style) ═══

    if command == "start":
        _svc_start()
        return
    if command == "stop":
        _svc_stop()
        return
    if command == "restart":
        _svc_restart()
        return
    if command == "status":
        _svc_status()
        return
    if command == "logs":
        _svc_logs()
        return
    if command == "update":
        _svc_update()
        return

    # ═══ Diagnostic commands (no full import needed) ═══

    if command == "deps":
        _svc_deps(sys.argv[2:])
        return
    if command == "trace":
        _svc_trace(sys.argv[2:])
        return
    if command == "secrets":
        _svc_secrets(sys.argv[2:])
        return

    # ═══ Standard commands ═══

    if command in ("web", "ui"):
        _start_web()
        return

    from .integration.launcher import launch, LaunchMode

    if command in ("server", "api"):
        launch(LaunchMode.SERVER)
    elif command in ("client", "cli"):
        launch(LaunchMode.CLIENT)
    elif command == "test":
        launch(LaunchMode.TEST)
    elif command in ("check", "env"):
        launch(LaunchMode.CHECK)
    elif command in ("quick", "q"):
        launch(LaunchMode.QUICK)
    elif command == "config":
        _svc_config(sys.argv[2:])
    elif command == "skill":
        _svc_skill(sys.argv[2:])
    elif command == "channel":
        _svc_channel(sys.argv[2:])
    elif command == "relay":
        from relay_server import main as relay_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        relay_main()
    else:
        print(f"Unknown command: {command}")
        _print_usage()
        sys.exit(1)


# ═══ Service Management ═══

def _get_pid() -> int:
    try:
        return int(Path(PID_FILE).read_text().strip())
    except Exception:
        return 0


def _svc_start():
    pid = _get_pid()
    if pid and _is_running(pid):
        print(f"LivingTree is already running (PID: {pid})")
        return

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        [sys.executable, "-m", "livingtree", "web"],
        stdout=log, stderr=log,
        start_new_session=True,
    )
    Path(PID_FILE).write_text(str(proc.pid))
    print(f"LivingTree started (PID: {proc.pid})")
    print(f"  Web UI: http://localhost:8100/tree/living")
    print(f"  Logs:   {LOG_FILE}")


def _svc_stop():
    pid = _get_pid()
    if not pid or not _is_running(pid):
        print("LivingTree is not running")
        Path(PID_FILE).unlink(missing_ok=True)
        return

    try:
        if os.name == "posix":
            os.kill(pid, 15)
        else:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        print(f"LivingTree stopped (PID: {pid})")
    except Exception as e:
        print(f"Failed to stop: {e}")
    Path(PID_FILE).unlink(missing_ok=True)


def _svc_restart():
    _svc_stop()
    import time
    time.sleep(2)
    _svc_start()


def _svc_status():
    pid = _get_pid()
    if pid and _is_running(pid):
        from datetime import datetime
        try:
            stat = Path(f"/proc/{pid}/stat") if os.name == "posix" else None
            created = Path(PID_FILE).stat().st_mtime if Path(PID_FILE).exists() else 0
            uptime = _json.dumps(int(datetime.now().timestamp() - created)) + "s ago"
        except Exception:
            uptime = "unknown"
        print(f"LivingTree: RUNNING (PID: {pid})")
        print(f"  Started: {uptime}")
        print(f"  Web UI:  http://localhost:8100/tree/living")
    else:
        print("LivingTree: STOPPED")
        Path(PID_FILE).unlink(missing_ok=True)


def _svc_logs():
    n = 20
    args = sys.argv[2:]
    if args and args[0].isdigit():
        n = int(args[0])

    if Path(LOG_FILE).exists():
        lines = Path(LOG_FILE).read_text(errors="replace").strip().split("\n")
        for line in lines[-n:]:
            print(line)
    else:
        print(f"No log file at {LOG_FILE}")


def _svc_update():
    import asyncio
    from .integration.self_updater import run_update
    result = asyncio.run(run_update())
    print(_json.dumps(result, indent=2, ensure_ascii=False))


def _is_running(pid: int) -> bool:
    try:
        if os.name == "posix":
            os.kill(pid, 0)
        else:
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
            return str(pid) in result.stdout
        return True
    except Exception:
        return False


# ═══ Subcommands ═══

def _svc_config(args: list):
    from .config import get_config
    cfg = get_config()
    if not args:
        print(_json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False, default=str))
    else:
        key = args[0]
        if len(args) > 1:
            setattr(cfg, key, _json.loads(args[1]))
            print(f"Set {key} = {args[1]}")
        else:
            print(f"{key}: {getattr(cfg, key, 'N/A')}")


def _svc_skill(args: list):
    import asyncio
    from .core.skill_hub import get_skill_hub

    if not args:
        print("Usage: livingtree skill [install|list|search|uninstall] [name]")
        return

    sub = args[0].lower()
    hub = get_skill_hub()

    if sub == "list":
        skills = hub.list_installed()
        if skills:
            for s in skills:
                print(f"  {s.name} v{s.version} [{s.category}] — {s.description[:60]}")
        else:
            print("  No skills installed. Use 'livingtree skill hub' to browse.")

    elif sub == "hub":
        async def _fetch():
            skills = await hub.fetch_hub_index()
            for s in skills[:20]:
                installed = "✅" if s.name in hub._installed else "📦"
                print(f"  {installed} {s.name} [{s.category}] — {s.description[:60]}")
        asyncio.run(_fetch())

    elif sub in ("install", "i") and len(args) > 1:
        async def _install():
            try:
                meta = await hub.install(args[1])
                if meta:
                    print(f"✅ Installed: {meta.name} v{meta.version}")
                    if meta.tools:
                        print(f"   Tools: {', '.join(meta.tools)}")
            except Exception as e:
                print(f"❌ Install failed: {e}")
        asyncio.run(_install())

    elif sub in ("uninstall", "rm") and len(args) > 1:
        if hub.uninstall(args[1]):
            print(f"✅ Uninstalled: {args[1]}")
        else:
            print(f"❌ Not found: {args[1]}")

    elif sub == "search" and len(args) > 1:
        results = hub.search(args[1])
        for s in results:
            print(f"  {s.name} [{s.category}] — {s.description[:80]}")

    else:
        print(f"Unknown skill command: {sub}")


def _svc_channel(args: list):
    from .network.channel_bridge import get_channel_bridge, ChannelType
    bridge = get_channel_bridge()

    if not args:
        print("Available channels:")
        for ct in ChannelType:
            print(f"  {ct.value}")
        print("Usage: livingtree channel <type>")
        return

    ct = args[0].lower()
    valid = {c.value for c in ChannelType}
    if ct not in valid:
        print(f"Unknown channel: {ct}. Available: {', '.join(valid)}")
        return

    from .network.channel_bridge import ChannelConfig
    cfg = ChannelConfig(channel_type=ChannelType(ct), enabled=True)
    bridge.configure(cfg)
    print(f"Channel set to: {ct}")
    print(f"  Configure via config.json or environment variables (LT_CHANNEL_*)")

    if ct == "weixin":
        print("  Requires: pip install itchat-uos")
    elif ct == "feishu":
        print("  Requires: LT_FEISHU_APP_ID, LT_FEISHU_APP_SECRET")
    elif ct == "dingtalk":
        print("  Requires: LT_DINGTALK_CLIENT_ID, LT_DINGTALK_CLIENT_SECRET")


def _svc_secrets(args: list):
    """Manage encrypted secrets vault."""
    from .config.secrets import get_secret_vault
    vault = get_secret_vault()

    if not args or args[0] == "list":
        keys = vault.keys()
        if keys:
            for k in sorted(keys):
                val = vault.get(k, "")
                masked = val[:8] + "***" + val[-4:] if len(val) > 12 else "***"
                print(f"  {k} = {masked}")
        else:
            print("  No secrets stored. Use 'livingtree secrets set KEY VALUE'")
        return

    sub = args[0].lower()
    if sub in ("set", "add") and len(args) >= 3:
        vault.set(args[1], args[2])
        print(f"✅ Stored: {args[1]} (encrypted at config/secrets.enc)")
    elif sub in ("get", "show") and len(args) >= 2:
        val = vault.get(args[1], "")
        if val:
            masked = val[:8] + "***" + val[-4:] if len(val) > 12 else "***"
            print(f"  {args[1]} = {masked}")
        else:
            print(f"  {args[1]}: not found")
    elif sub in ("delete", "rm", "del") and len(args) >= 2:
        if vault.delete(args[1]):
            print(f"✅ Deleted: {args[1]}")
        else:
            print(f"  {args[1]}: not found")
    else:
        print("Usage: livingtree secrets [list|set KEY VAL|get KEY|delete KEY]")


def _svc_trace(args: list):
    """Diagnostic: visualize trigger chain and routing decisions."""
    print("\n🔍 LivingTree Trace — 触发链可视化\n")

    print("═══ 4-Layer Model Routing ═══")
    print("  L1  Embedding pre-filter    → semantic match scoring")
    print("  L2  Election + alive ping   → latency/quality/cost/capability")
    print("  L3  Inference + self-assess → output quality evaluation")
    print("  L4  Smart fallback          → remaining candidates + local LLM")
    print()

    print("═══ 12-Organ Data Flow ═══")
    organs = [
        ("👁️ Eyes  ", "→ 🧠 Brain"), ("👂 Ears  ", "→ 🧠 Brain"),
        ("🧠 Brain ", "→ ❤️ Heart, 🤲 Hands"), ("❤️ Heart ", "→ 🫁 Lungs, 🩸 Blood"),
        ("🫁 Lungs ", "→ 🧠 Brain"), ("🫀 Liver ", "→ 🤲 Hands"),
        ("🩸 Blood ", "→ 🤲 Hands, 🦵 Legs"), ("🤲 Hands ", "→ 🦵 Legs"),
        ("🦵 Legs  ", "→ (output)"), ("🦴 Bones ", "→ 🧠 Brain, 🤲 Hands"),
        ("🛡️ Immune", "→ 🧠 Brain, 🫀 Liver"), ("🌱 Reprod", "→ (replicate)"),
    ]
    for organ, flow in organs:
        print(f"  {organ} {flow}")

    try:
        from .knowledge.knowledge_lineage import get_lineage
        lineage = get_lineage()
        st = lineage.stats()
        print(f"\n═══ Knowledge Lineage ═══")
        print(f"  Nodes: {st['total_nodes']} | Roots: {st['roots']} | Leaves: {st['leaves']}")
    except Exception:
        pass

    try:
        from .core.awareness_engine import get_awareness
        a = get_awareness()
        r = a.assess_all()
        print(f"\n═══ Awareness ═══")
        print(f"  {r.aggregate:.0%} {r.level} | "
              f"Meta:{r.metacognition.score:.0%} Self:{r.self_awareness.score:.0%} "
              f"Social:{r.social_awareness.score:.0%} Situ:{r.situational_awareness.score:.0%}")
    except Exception:
        pass

    try:
        from .core.vitals import get_vitals
        v = get_vitals().measure()
        print(f"\n═══ Vitals ═══")
        print(f"  CPU:{v['cpu']['percent']:.0f}%({v['cpu']['level']}) RAM:{v['memory']['percent']:.0f}% "
              f"LED:{v['led']['color_hex']} Leaf:{v['leaf_display']['state']}")
    except Exception:
        pass

    print("\n═══ Adaptive Trigger Flow ═══")
    print("  Input → Dynamic Route → Spec Injection → Tool Match")
    print("    → Sandbox Exec → ARQ Verify → Memory Store → DPO Update\n")


def _resolve_relative(current_dir: str, module: str, level: int) -> str:
    """Resolve a relative import to an absolute module path."""
    if not current_dir:
        return module
    parts = current_dir.split(".")
    if level > len(parts):
        return module
    base = ".".join(parts[:len(parts) - level + 1]) if level > 1 else current_dir
    return f"{base}.{module}" if base else module


def _svc_deps(args: list):
    """Generate module dependency topology → DEPENDENCIES.mmd (Mermaid)."""
    import ast
    from pathlib import Path
    from collections import defaultdict

    project_root = Path(__file__).resolve().parent.parent
    tree_dir = project_root / "livingtree"
    if not tree_dir.is_dir():
        print("Run from project root")
        return

    deps: defaultdict[str, set[str]] = defaultdict(set)
    module_paths: dict[str, str] = {}
    categories: dict[str, int] = defaultdict(int)

    for pyfile in tree_dir.rglob("*.py"):
        if ".venv" in str(pyfile) or "__pycache__" in str(pyfile):
            continue
        try:
            content = pyfile.read_text(errors="replace")
            tree = ast.parse(content)
            mod_name = str(pyfile.relative_to(tree_dir)).replace("/", ".").replace("\\", ".").replace(".py", "")
            module_paths[mod_name] = mod_name

            mod_parts = mod_name.split(".")
            mod_dir = ".".join(mod_parts[:-1]) if len(mod_parts) > 1 else ""

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("livingtree"):
                        deps[mod_name].add(node.module)
                    elif node.level and node.level > 0 and node.module:
                        resolved = _resolve_relative(mod_dir, node.module, node.level)
                        if resolved and resolved in module_paths:
                            deps[mod_name].add(resolved)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("livingtree"):
                            deps[mod_name].add(alias.name)
        except Exception:
            continue

    for m in deps:
        parts = m.split(".")
        if len(parts) > 1:
            categories[parts[1]] += 1

    mmd_lines = ["graph TD"]
    for mod, targets in sorted(deps.items()):
        for tgt in sorted(targets):
            if tgt in module_paths:
                a = mod.replace(".", "_")
                b = tgt.replace(".", "_")
                al = mod.split(".")[-1]
                bl = tgt.split(".")[-1]
                if a != b:
                    mmd_lines.append(f"    {a}[{al}] --> {b}[{bl}]")

    out = project_root / "DEPENDENCIES.mmd"
    out.write_text("\n".join(mmd_lines), encoding="utf-8")

    total_edges = sum(len(t) for t in deps.values())
    print(f"DEPENDENCIES.mmd generated: {len(deps)} modules, {total_edges} edges")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} modules")
    print("  Open: https://mermaid.live or VS Code Mermaid preview")


# ═══ Helpers ═══

def _start_web():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    from .integration.launcher import launch, LaunchMode
    launch(LaunchMode.SERVER)


def _print_usage():
    print(f"""
╔══════════════════════════════════════════════╗
║   🌳 生命之树 · LivingTree AI Agent v{VERSION}  ║
║       Digital Lifeform Platform               ║
╚══════════════════════════════════════════════╝

Service Management (CowAgent style):
  start              Background start (daemon)
  stop               Stop background service
  restart            Restart service
  status             Show service status
  logs [N]           View last N log lines (default 20)
  update             Git pull + restart

Server:
  web, ui            Web server with Living Canvas UI
  server, api        API server only
  client, cli        Interactive CLI chat

Skills & Channels:
  skill hub           Browse remote skill marketplace
  skill list          List installed skills
  skill install X     Install skill from hub/GitHub
  skill search X      Search skills
  skill uninstall X   Uninstall skill
  channel X           Set messaging channel (weixin/feishu/...)

Other:
  test               Run integration tests
  check, env         Environment check
  relay              Start relay server
  quick [msg]        Single quick interaction
  config [key] [val] Show/set config
  --version, -v      Show version
  --help, -h         Show this help

Examples:
  livingtree                              # Start web UI
  livingtree start                        # Background daemon
  livingtree skill hub                    # Browse skills
  livingtree skill install ai-reporter     # Install a skill
  livingtree channel weixin               # Enable WeChat
  livingtree logs 50                      # Last 50 log lines
""")
