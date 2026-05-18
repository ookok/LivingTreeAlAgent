"""Diagnostic & config commands — extracted from main.py."""
from __future__ import annotations

import sys, os, json as _json, asyncio, subprocess
from pathlib import Path

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



def _svc_config(args: list):
    """Unified config management: livingtree config [show|set|list] [key] [value]

    Examples:
        livingtree config                     # dump full config
        livingtree config show model          # show model section
        livingtree config set model.temperature 0.5  # set nested key
        livingtree config set user.theme dark # set user preference
        livingtree config list                # list top-level keys
    """
    from .config import get_config
    from .config.settings import reload_config
    import yaml
    cfg = get_config()

    if not args:
        # Dump readable config (exclude API keys)
        d = cfg.model_dump()
        _mask_api_keys(d)
        print(yaml.safe_dump(d, default_flow_style=False, allow_unicode=True, sort_keys=False))
        return

    sub = args[0].lower()

    if sub == "list":
        for k in cfg.model_fields:
            v = getattr(cfg, k, None)
            vtype = type(v).__name__
            print(f"  {k:<20} ({vtype})")
        print(f"\n  Use 'livingtree config show <section>' for details")
        print(f"  Use 'livingtree config set <key> <value>' to modify")
        return

    if sub in ("show", "get"):
        key = args[1] if len(args) > 1 else None
        if not key:
            d = cfg.model_dump()
            _mask_api_keys(d)
            print(yaml.safe_dump(d, default_flow_style=False, allow_unicode=True, sort_keys=False))
            return
        val = _config_get_nested(cfg, key)
        if val is not None:
            if isinstance(val, (dict, list)):
                print(yaml.safe_dump(val, default_flow_style=False, allow_unicode=True))
            else:
                print(f"{key}: {val}")
        else:
            print(f"  Key not found: {key}")
        return

    if sub in ("set", "edit"):
        if len(args) < 3:
            print("Usage: livingtree config set <key> <value>")
            print("Example: livingtree config set model.temperature 0.5")
            return
        key = args[1]
        raw_value = args[2]
        try:
            value = yaml.safe_load(raw_value) if raw_value not in ("true", "false", "null") else \
                    {"true": True, "false": False, "null": None}.get(raw_value, raw_value)
        except Exception:
            value = raw_value
        _config_set_nested(cfg, key, value)
        try:
            cfg.to_yaml(Path("config/livingtree.yaml"))
            print(f"  {key} = {value} (saved to config/livingtree.yaml)")
        except Exception as e:
            print(f"  {key} = {value} (in-memory only, save failed: {e})")
        return

    if sub == "reload":
        cfg = reload_config()
        print("  Config reloaded from disk")
        return

    print("Usage: livingtree config [show|set|list|reload] [key] [value]")



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

TUI:
  tui                Terminal UI dev chat (Textual, streaming, markdown)

Skills & Channels:
  skill hub           Browse remote skill marketplace
  skill list          List installed skills
  skill install X     Install skill from hub/GitHub
  skill search X      Search skills
  skill uninstall X   Uninstall skill
  skill enable X      Enable a skill
  skill disable X     Disable a skill
  skill create X [code] [category]  Create a new skill
  skill discover      Scan SKILL.md files
  skill propose X     Propose a skill from task description
  skill graph         Show skill dependency graph
  skill report        Show skill progression report
  channel X           Set messaging channel (weixin/feishu/...)

Other:
  test               Run integration tests
  canary             Run canary regression tests
  canary baseline    Save current routing as baseline
  check, env         Environment check
  relay              Start relay server
  quick [msg]        Single quick interaction
  config [key] [val] Show/set config
  learn              Learn from trending repos + papers → evolve
  learn github       Search GitHub trending repos
  learn arxiv        Search arXiv latest papers
  learn nature       Search Nature/Semantic Scholar papers
  learn apply        Feed learned patterns into evolution
  learn stats        Show learning statistics
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


__all__ = ["run_deps", "run_trace", "run_secrets", "run_config", "print_usage"]
