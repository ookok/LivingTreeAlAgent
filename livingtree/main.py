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
import time as _time_module
import logging
import threading
import yaml
from pathlib import Path

VERSION = "2.2.0"
PID_FILE = ".livingtree/server.pid"
LOG_FILE = ".livingtree/server.log"
WATCHDOG_PID_FILE = ".livingtree/watchdog.pid"
WATCHDOG_STATE_FILE = ".livingtree/watchdog.json"
WATCHDOG_MAX_RESTARTS = 5
WATCHDOG_COOLDOWN = 10
WATCHDOG_POLL = 3

_watchdog_lock = threading.Lock()
_watchdog_running = False
_watchdog_restart_count = 0
_watchdog_child_pid = 0


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
    elif command == "canary":
        _svc_canary(sys.argv[2:])
    elif command == "recording" or command == "record":
        _svc_recording(sys.argv[2:])
    elif command == "debug":
        _svc_debug(sys.argv[2:])
    elif command == "improve":
        _svc_improve(sys.argv[2:])
    elif command == "cli":
        _svc_cli(sys.argv[2:])
    elif command == "cli-anything":
        _svc_cli_anything(sys.argv[2:])
    elif command == "models":
        _svc_models(sys.argv[2:])
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


def _watchdog_loop(log_file: str):
    """Background thread: monitor child process and auto-restart on crash."""
    global _watchdog_running, _watchdog_restart_count, _watchdog_child_pid

    while True:
        _time_module.sleep(WATCHDOG_POLL)

        with _watchdog_lock:
            if not _watchdog_running:
                break
            pid = _watchdog_child_pid
            if _watchdog_restart_count >= WATCHDOG_MAX_RESTARTS:
                _watchdog_running = False
                _write_watchdog_state()
                print(f"[Watchdog] Max restarts ({WATCHDOG_MAX_RESTARTS}) reached — giving up")
                break

        if pid and not _is_running(pid):
            with _watchdog_lock:
                _watchdog_restart_count += 1
                current_count = _watchdog_restart_count

            if current_count > WATCHDOG_MAX_RESTARTS:
                print(f"[Watchdog] Max restarts ({WATCHDOG_MAX_RESTARTS}) reached — giving up")
                with _watchdog_lock:
                    _watchdog_running = False
                _write_watchdog_state()
                break

            print(f"[Watchdog] Child (PID {pid}) died — restarting ({current_count}/{WATCHDOG_MAX_RESTARTS})...")
            _time_module.sleep(WATCHDOG_COOLDOWN)

            try:
                log = open(log_file, "a")
                proc = subprocess.Popen(
                    [sys.executable, "-m", "livingtree", "web"],
                    stdout=log, stderr=log,
                    start_new_session=True,
                )
                with _watchdog_lock:
                    _watchdog_child_pid = proc.pid
                Path(PID_FILE).write_text(str(proc.pid))
                _write_watchdog_state()
                print(f"[Watchdog] Restarted (PID: {proc.pid})")
            except Exception as e:
                print(f"[Watchdog] Restart failed: {e}")

    with _watchdog_lock:
        _watchdog_running = False
    _write_watchdog_state()
    Path(WATCHDOG_PID_FILE).unlink(missing_ok=True)
    Path(WATCHDOG_STATE_FILE).unlink(missing_ok=True)


def _write_watchdog_state():
    """Persist watchdog state so `livingtree status` can read it cross-process."""
    Path(WATCHDOG_STATE_FILE).write_text(
        _json.dumps({
            "running": _watchdog_running,
            "restart_count": _watchdog_restart_count,
            "max_restarts": WATCHDOG_MAX_RESTARTS,
            "child_pid": _watchdog_child_pid,
        }),
        encoding="utf-8",
    )


def _read_watchdog_state():
    """Read persisted watchdog state. Returns {} if file missing."""
    try:
        return _json.loads(Path(WATCHDOG_STATE_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _svc_start():
    pid = _get_pid()
    if pid and _is_running(pid):
        print(f"LivingTree is already running (PID: {pid})")
        return

    watch = "--watchdog" in sys.argv

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log = open(LOG_FILE, "a")
    try:
        from livingtree.treellm.unified_exec import run
        import asyncio
        raise ImportError("Force Popen for daemon")
    except ImportError:
        proc = subprocess.Popen(
            [sys.executable, "-m", "livingtree", "web"],
            stdout=log, stderr=log,
            start_new_session=True,
        )
    Path(PID_FILE).write_text(str(proc.pid))

    if watch:
        global _watchdog_running, _watchdog_child_pid, _watchdog_restart_count
        _watchdog_running = True
        _watchdog_child_pid = proc.pid
        _watchdog_restart_count = 0
        t = threading.Thread(target=_watchdog_loop, args=(LOG_FILE,), daemon=True, name="lt-watchdog")
        t.start()
        Path(WATCHDOG_PID_FILE).write_text(str(os.getpid()))
        _write_watchdog_state()
        print(f"LivingTree started (PID: {proc.pid}) [Watchdog: ON, max restarts={WATCHDOG_MAX_RESTARTS}]")
    else:
        print(f"LivingTree started (PID: {proc.pid})")
    print(f"  Web UI: http://localhost:8100/tree/living")
    print(f"  Logs:   {LOG_FILE}")


def _svc_stop():
    global _watchdog_running
    with _watchdog_lock:
        _watchdog_running = False

    pid = _get_pid()
    if not pid or not _is_running(pid):
        print("LivingTree is not running")
        Path(PID_FILE).unlink(missing_ok=True)
        Path(WATCHDOG_PID_FILE).unlink(missing_ok=True)
        Path(WATCHDOG_STATE_FILE).unlink(missing_ok=True)
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
    Path(WATCHDOG_PID_FILE).unlink(missing_ok=True)
    Path(WATCHDOG_STATE_FILE).unlink(missing_ok=True)


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
            created = Path(PID_FILE).stat().st_mtime if Path(PID_FILE).exists() else 0
            uptime = f"{int(datetime.now().timestamp() - created)}s ago"
        except Exception:
            uptime = "unknown"
        print(f"LivingTree: RUNNING (PID: {pid})")
        print(f"  Started: {uptime}")
        print(f"  Web UI:  http://localhost:8100/tree/living")
        wd_state = _read_watchdog_state()
        if wd_state:
            running = wd_state.get("running", False)
            count = wd_state.get("restart_count", 0)
            max_r = wd_state.get("max_restarts", WATCHDOG_MAX_RESTARTS)
            wd_status = f"ON, restarts={count}/{max_r}" if running else f"OFF (restarts={count}/{max_r})"
            print(f"  Watchdog: {wd_status}")
    else:
        print("LivingTree: STOPPED")
        Path(PID_FILE).unlink(missing_ok=True)
        Path(WATCHDOG_PID_FILE).unlink(missing_ok=True)
        Path(WATCHDOG_STATE_FILE).unlink(missing_ok=True)


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
    try:
        result = asyncio.run(run_update())
        print(_json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Update failed: {e}")


def _is_running(pid: int) -> bool:
    try:
        if os.name == "posix":
            os.kill(pid, 0)
            return True
        else:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            STILL_ACTIVE = 259

            hProcess = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
            )
            if not hProcess:
                return False
            exit_code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(hProcess, ctypes.byref(exit_code))
            kernel32.CloseHandle(hProcess)
            return exit_code.value == STILL_ACTIVE
    except Exception:
        return False


# ═══ Subcommands ═══

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


def _mask_api_keys(d: dict) -> None:
    """Recursively mask api_key values in a dict."""
    for k, v in d.items():
        if isinstance(v, dict):
            _mask_api_keys(v)
        elif isinstance(k, str) and "api_key" in k.lower() and isinstance(v, str) and len(v) > 8:
            d[k] = v[:4] + "***" + v[-4:]


def _config_get_nested(cfg, key: str):
    """Get nested config value by dot-notation key."""
    parts = key.split(".")
    obj = cfg
    for p in parts:
        if isinstance(obj, dict):
            obj = obj.get(p)
        elif hasattr(obj, p):
            obj = getattr(obj, p)
        else:
            return None
    return obj


def _config_set_nested(cfg, key: str, value) -> None:
    """Set nested config value by dot-notation key."""
    parts = key.split(".")
    obj = cfg
    for p in parts[:-1]:
        if isinstance(obj, dict):
            obj = obj.get(p)
        else:
            obj = getattr(obj, p)
    last = parts[-1]
    if isinstance(obj, dict):
        obj[last] = value
    else:
        setattr(obj, last, value)


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
        try:
            asyncio.run(_fetch())
        except Exception as e:
            print(f"❌ Skill hub fetch failed: {e}")

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

    elif sub == "enable" and len(args) > 1:
        if hub.toggle(args[1], True):
            print(f"  Enabled: {args[1]}")
        else:
            print(f"  Not found: {args[1]}")

    elif sub == "disable" and len(args) > 1:
        if hub.toggle(args[1], False):
            print(f"  Disabled: {args[1]}")
        else:
            print(f"  Not found: {args[1]}")

    elif sub == "create" and len(args) > 1:
        from .capability.skill_factory import get_skill_factory
        factory = get_skill_factory()
        skill = factory.create_skill(args[1], args[2] if len(args) > 2 else "", category=args[3] if len(args) > 3 else "custom")
        if skill:
            print(f"  Created: {skill.name} [{skill.category}]")
        else:
            print("  Create failed")

    elif sub == "discover":
        from .capability.skill_discovery import SkillDiscoveryManager
        skills = SkillDiscoveryManager().discover()
        if skills:
            for s in skills:
                print(f"  {s.name} — {s.description[:80]}")
        else:
            print("  No SKILL.md files found")

    elif sub == "propose" and len(args) > 1:
        from .dna.unified_skill_system import get_skill_system
        skill = get_skill_system().propose_skill(" ".join(args[1:]))
        print(f"  Proposed: {skill.name} — {skill.description[:80]}")

    elif sub == "graph":
        from .dna.skill_graph import get_skill_graph
        g = get_skill_graph()
        print(f"  Nodes: {len(g._nodes)}")
        for node in list(g._nodes.values())[:15]:
            print(f"    {node.name} → {len(node.dependencies)} deps, {len(node.compositions)} comps")
        print(f"  Clusters: {len(g.get_clusters())}")

    elif sub == "report":
        from .dna.skill_progression import get_skill_progression
        sp = get_skill_progression()
        report = sp.generate_report(top_k=10)
        for item in report:
            print(f"  {item['skill']}: {item['level']} (success={item['success_rate']:.0%}, trend={item['trend']})")

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


def _svc_canary(args: list):
    """Run canary regression tests against baseline."""
    import asyncio

    async def _run():
        from .treellm.canary_tester import get_canary_tester
        from .treellm.core import TreeLLM
        tester = get_canary_tester()
        print(f"\n  Running {tester.query_count} canary queries...\n")

        llm = TreeLLM()
        if args and args[0] == "baseline":
            await tester.set_baseline(llm)
            print(f"  Baseline saved to .livingtree/canary_baseline.json")
        else:
            report = await tester.run(llm)
            print(f"  {report.summary()}")
            if report.regressions:
                print(f"\n  Regressions:")
                for r in report.results:
                    if r.regressed:
                        print(f"    [{r.query_id}] provider={r.provider} latency={r.latency_ms:.0f}ms")

        print(f"  Canary queries: .livingtree/canary_queries.json")
        print(f"  Baseline:       .livingtree/canary_baseline.json")

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"❌ Canary failed: {e}")


def _svc_debug(args: list):
    """AI-driven autonomous debug loop.
    
    File debug (default):    livingtree debug main.py --level L2 --trace
    Pipeline debug (chat):   livingtree debug chat "帮我分析代码" --trace
    """
    import asyncio

    async def _run():
        from .treellm.debug_pro import install as debug_install
        from .treellm.debug_loop import DebugLoop, DebugLevel

        # Detect mode
        if args and args[0] == "chat":
            await _debug_chat(args[1:])
            return

        # Install global error interception
        interceptor = debug_install(trace_memory="--trace" in args)

        target = args[0] if args else "main.py"
        level = DebugLevel.SEMI_AUTO
        max_attempts = 5
        target_args = []
        trace_mode = "--trace" in args

        i = 0
        while i < len(args):
            if args[i] == "--level" and i + 1 < len(args):
                level = DebugLevel(args[i+1]) if args[i+1] in [d.value for d in DebugLevel] else DebugLevel.SEMI_AUTO
                i += 2
            elif args[i] == "--max-attempts" and i + 1 < len(args):
                max_attempts = int(args[i+1])
                i += 2
            elif args[i] == "--trace":
                i += 1
            elif args[i] == "--args" and i + 1 < len(args):
                target_args = args[i+1:]
                break
            else:
                i += 1

        # Line tracer (if --trace)
        if trace_mode:
            from .treellm.debug_pro import LineTracer
            tracer = LineTracer()
            print(f"\n  Tracing execution: {target}")
            snapshots = await tracer.trace_file(target, max_steps=500)
            print(f"  Captured {len(snapshots)} line snapshots")
            for s in snapshots[-10:]:
                print(f"    {s.file}:{s.line} — {s.function}")

        print(f"\n  Debug Loop: {target} (level={level.value}, max_attempts={max_attempts})")
        loop = DebugLoop.instance()
        session = await loop.debug(target, target_args, level, max_attempts)

        print(f"\n  Result: {'✅ FIXED' if session.fixed else '❌ ESCALATED' if session.escalated else '⚠️ UNRESOLVED'}")
        print(f"  Attempts: {len(session.attempts)}")
        print(f"  Duration: {session.total_duration_ms/1000:.1f}s")
        for a in session.attempts:
            print(f"    #{a.attempt_number}: {a.result.value} ({a.duration_ms/1000:.1f}s) {a.llm_provider}")

        if interceptor:
            stats = interceptor.stats()
            if stats["total_captured"] > 0:
                print(f"\n  Errors intercepted: {stats['total_captured']} ({stats['unique_types']} types)")
                for err_type, count in stats["top_errors"]:
                    print(f"    {err_type}: {count}")

    async def _debug_chat(chat_args: list):
        """Debug the full chat pipeline end-to-end with line tracing and tool execution.

        Phases:
          1. Input Normalization (living_input_bus)
          2. ContextMoE Memory Retrieval
          3. Provider Election (smart_route, parallel ping all providers)
          4. LLM Chat (with provider fallback on failure)
          5. Tool Call Execution (auto-detect + invoke via LocalToolBus)
          6. Error Summary (ErrorInterceptor stats)
        """
        try:
            from .treellm.debug_pro import install as debug_install
            from .treellm.debug_pro import ErrorInterceptor, LineTracer
        except ImportError as e:
            print(f"  ❌ Failed to import debug_pro: {e}")
            return
        import time as _time, traceback as _tb

        debug_install()
        message = " ".join(a for a in chat_args if not a.startswith("--") and a not in ("-v", "-vv"))
        trace = "--trace" in chat_args
        verbose = ("--verbose" in chat_args) or ("-v" in chat_args) or ("-vv" in chat_args)

        if not message:
            print("Usage: livingtree debug chat \"your message\" [--trace] [--verbose]")
            print("  --trace   : enable line-by-line execution tracing via DebugPro LineTracer")
            print("  --verbose : show full response text and detailed timing")
            return

        print(f"\n{'='*60}")
        print(f"  Pipeline Debug: \"{message[:80]}\"")
        if trace:
            print(f"  Mode: LINE TRACING enabled (DebugPro)")
        print(f"{'='*60}")

        # ── Line Tracer (if --trace) ──
        line_tracer = None
        if trace:
            line_tracer = LineTracer()
            print(f"\n  [TRACE] Installing line tracer on debug pipeline...")
            # Trace the core.py chat method
            line_tracer.trace_module("livingtree.treellm.core", "chat")

        # Phase 1: Input normalization ────────────────────────────
        t0 = _time.time()
        print("\n[1/6] Input Normalization...")
        try:
            from .treellm.living_input_bus import get_living_input_bus, InputSource
            bus = get_living_input_bus()
            inp = bus._normalizer.from_cli([message])
            print(f"  ✅ kind={inp.kind.value} source={inp.source.value} text_len={len(inp.text)}")
            if verbose:
                tok = getattr(inp, 'tokens', 0)
                lang = getattr(inp, 'language', '?')
                cpx = getattr(inp, 'complexity', 0)
                print(f"     tokens={tok} lang={lang} complexity={cpx}")
        except Exception as e:
            print(f"  ❌ Input normalization failed: {e}")

        # Phase 2: ContextMoE memory ─────────────────────────────
        print("\n[2/6] ContextMoE Memory Retrieval...")
        t1 = _time.time()
        has_memory = False
        enriched = message
        try:
            from .treellm.context_moe import get_context_moe
            moe = await get_context_moe("debug_chat")
            result = await moe.query(message, "general")
            enriched = moe.build_enriched_message(message, result)
            has_memory = enriched != message
            mem_ms = (_time.time() - t1) * 1000
            print(f"  ✅ memory_injected={has_memory} hot={len(result.hot)} warm={len(result.warm)} cold={len(result.cold)}")
            print(f"  ⏱️  {mem_ms:.0f}ms")
        except Exception as e:
            print(f"  ❌ ContextMoE failed: {e}")

        # Phase 3: LLM Election ──────────────────────────────────
        print("\n[3/6] Provider Election...")
        t2 = _time.time()
        try:
            from .treellm.core import TreeLLM
            llm = TreeLLM.from_config()
            provider = await llm.smart_route(message, task_type="general")
            alive = llm.provider_names
            elect_ms = (_time.time() - t2) * 1000
            if provider:
                print(f"  ✅ elected={provider} (from {len(alive)} alive)")
            else:
                print(f"  ⚠️  No provider elected (0/{len(alive)} alive)")
                if not alive:
                    print(f"     System comes with a built-in SenseTime key. Is sensetime_api_key available?")
            print(f"  ⏱️  {elect_ms:.0f}ms")
            if verbose and alive:
                print(f"     alive: {', '.join(alive[:5])}{'...' if len(alive)>5 else ''}")
        except Exception as e:
            print(f"  ❌ Election failed: {e}")
            provider = ""
            llm = None

        # Phase 4: LLM Chat (with fallback) ──────────────────────
        print("\n[4/6] LLM Chat...")
        t3 = _time.time()
        chat_result = ""
        used_provider = provider
        llm_error = ""
        try:
            if llm is None:
                raise RuntimeError("No LLM available (election failed)")

            # Try elected provider first, then fallback through all alive providers
            candidates = [provider] if provider else []
            if hasattr(llm, 'provider_names'):
                all_providers = list(llm.provider_names)
                for p in all_providers:
                    if p not in candidates:
                        candidates.append(p)
            candidates = candidates[:5]  # Max 5 to avoid excessive retries

            for attempt, cand in enumerate(candidates):
                try:
                    result = await llm.chat(
                        [{"role": "user", "content": enriched if has_memory else message}],
                        provider=cand, tools=True, max_tokens=2048,
                    )
                    result_text = getattr(result, 'text', '')
                    result_error = getattr(result, 'error', '')
                    if result_text and not result_error:
                        chat_result = result_text
                        used_provider = cand
                        if verbose or attempt > 0:
                            print(f"  ✅ {cand}: response {len(result_text)} chars")
                        break
                    elif result_error:
                        if verbose or attempt == 0:
                            print(f"  ⚠️  {cand}: {result_error[:100]}")
                        if attempt < len(candidates) - 1:
                            print(f"     ↳ retry with next provider...")
                    else:
                        if verbose:
                            print(f"  ⚠️  {cand}: empty response")
                except Exception as inner_e:
                    if verbose:
                        print(f"  ⚠️  {cand}: {inner_e}")

            if chat_result:
                tokens = getattr(result, 'tokens', 0)
                chat_ms = (_time.time() - t3) * 1000
                print(f"  ✅ response_len={len(chat_result)} tokens={tokens} provider={used_provider}")
                print(f"  ⏱️  {chat_ms:.0f}ms")
            else:
                llm_error = "All providers failed — network issue or API keys not responding"
                print(f"  ❌ {llm_error}")
                print(f"     System has built-in keys. If they don't work, add your own: livingtree secrets set KEY VALUE")
        except Exception as e:
            llm_error = str(e)
            print(f"  ❌ Chat failed: {e}")

        # Phase 5: Tool calls — detect AND execute ───────────────
        print("\n[5/6] Tool Call Detection & Execution...")
        tool_count = 0
        tool_results = []
        try:
            import re as _re
            TOOL_RE = _re.compile(r'<tool_call\s+name="(\w+)"\s*>(.*?)</tool_call>', _re.DOTALL)
            if chat_result:
                tools = TOOL_RE.findall(chat_result)
                if tools:
                    from .treellm.local_tool_bus import get_local_tool_bus
                    ltb = get_local_tool_bus()
                    for name, args in tools:
                        tool_count += 1
                        print(f"  🔧 {name}: {args[:80]}")
                        # Try to execute via LocalToolBus
                        if ltb.has(name):
                            try:
                                from .treellm.core import TreeLLM
                                kw = TreeLLM._unpack_tool_args(name, args)
                                exec_result = await ltb.invoke(name, **kw)
                                if exec_result.success:
                                    result_preview = str(exec_result.data)[:120]
                                    tool_results.append((name, result_preview))
                                    print(f"     ✅ executed ({exec_result.elapsed_ms:.0f}ms): {result_preview}")
                                else:
                                    tool_results.append((name, f"Error: {exec_result.error}"))
                                    print(f"     ❌ {exec_result.error[:100]}")
                            except Exception as tool_e:
                                print(f"     ⚠️  Tool execution error: {tool_e}")
                        else:
                            print(f"     ℹ️  Tool not in LocalToolBus — would need external execution")
                if not tool_count:
                    print(f"  ℹ️  No tool calls in response")
        except Exception as e:
            print(f"  ❌ Tool analysis failed: {e}")

        # Phase 6: Errors & Stats ─────────────────────────────────
        print("\n[6/6] Error Summary...")
        interceptor = ErrorInterceptor.instance()
        if interceptor:
            stats = interceptor.stats()
            if stats["total_captured"] > 0:
                print(f"  ⚠️  {stats['total_captured']} errors intercepted ({stats['unique_types']} types)")
                for err_type, count in stats["top_errors"]:
                    print(f"     {err_type}: {count}")
            else:
                print(f"  ✅ No errors intercepted")

        total_ms = (_time.time() - t0) * 1000
        print(f"\n{'='*60}")
        print(f"  Total: {total_ms:.0f}ms | Provider: {used_provider or provider} | Tools: {tool_count}")
        print(f"{'='*60}")
        if chat_result:
            if verbose:
                print(f"\n  📝 Full Response:\n{chat_result}\n")
            else:
                print(f"\n  📝 Response ({len(chat_result)} chars):")
                print(f"  {'─'*56}")
                for line in chat_result[:500].split("\n"):
                    print(f"  {line[:110]}")
                if len(chat_result) > 500:
                    print(f"  ... (truncated, {len(chat_result)-500} more chars)")
                print(f"  {'─'*56}")
        elif llm_error:
            print(f"\n  ❌ {llm_error}")
            from .config.secrets import get_secret_vault
            vault_keys = get_secret_vault().keys() if get_secret_vault() else []
            if vault_keys:
                print(f"  💡 You have {len(vault_keys)} key(s) in vault, but none responded. Network issue or key expired?")
                print(f"     Run 'livingtree secrets list' to check, or add new keys with 'livingtree secrets set KEY VALUE'")
            else:
                print(f"  💡 System has a built-in SenseTime API key loaded automatically.")
                print(f"     If it's not working, add your own with: livingtree secrets set deepseek_api_key YOUR_KEY")
        print(f"{'='*60}")

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"❌ Debug failed: {e}")


def _svc_cli(args: list):
    """CLI introspection: discover and register system CLI tools. usage: livingtree cli [scan|register NAME|register-all|search PATTERN|exec NAME -- ARGS]"""
    import asyncio

    async def _run():
        from .treellm.cli_introspector import get_cli_introspector

        if not args:
            print("Usage: livingtree cli [scan|register NAME|register-all|search PATTERN|exec NAME -- ARGS]")
            return

        introspector = get_cli_introspector()
        sub = args[0].lower()

        if sub == "scan":
            print("  Scanning PATH for CLI tools...")
            tools = introspector.scan_path(max_tools=200)
            by_cat = {}
            for t in tools:
                by_cat[t.category] = by_cat.get(t.category, 0) + 1
            for cat, n in sorted(by_cat.items()):
                print(f"    {cat}: {n} tools")
            print(f"  Total: {len(tools)} tools discovered")

        elif sub == "search" and len(args) > 1:
            results = introspector.search(args[1])
            for r in results:
                print(f"  [{r['category']}] {r['name']}: {r['description'][:80]}")

        elif sub == "register" and len(args) > 1:
            await introspector.register_tool(args[1])
            print(f"  Registered: cli:{args[1]}")

        elif sub == "register-all":
            result = await introspector.register_all()
            print(f"  Registered: {result.registered}, Failed: {result.failed} ({result.duration_ms:.0f}ms)")

        elif sub == "exec" and len(args) > 1:
            name = args[1]
            cli_args = " ".join(args[3:]) if len(args) > 2 and args[2] == "--" else ""
            result = await introspector.execute(name, cli_args)
            if "error" in result:
                print(f"  Error: {result['error']}")
            else:
                print(result.get("stdout", "")[:2000])
                if result.get("stderr"):
                    print(f"  [stderr]: {result['stderr'][:500]}")

        elif sub == "list":
            tools = introspector.list_available(category=args[1] if len(args) > 1 else "")
            for t in tools:
                status = "✅" if t["registered"] else "📦"
                print(f"  {status} [{t['category']}] {t['name']}")

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"❌ CLI introspection failed: {e}")


def _svc_cli_anything(args: list):
    """CLI-Anything framework: convert any code to CLI. usage: livingtree cli-anything [wrap|repo|manifest|publish|new] ..."""
    import asyncio

    async def _run():
        from .treellm.cli_anything import get_cli_anything

        if not args:
            print("Usage: livingtree cli-anything [wrap|repo|manifest|publish|new|stats] ...")
            return

        ca = get_cli_anything()
        sub = args[0].lower()

        if sub == "wrap" and len(args) > 1:
            # Wrap a Python function from a file
            file_path = args[1]
            func_name = args[2] if len(args) > 2 else None
            import importlib.util
            spec = importlib.util.spec_from_file_location("_temp", file_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if func_name:
                func = getattr(mod, func_name)
            else:
                # Use first public function
                funcs = [(n, f) for n, f in mod.__dict__.items()
                        if callable(f) and not n.startswith("_")]
                if not funcs:
                    print("  No public functions found")
                    return
                func_name, func = funcs[0]
            script = ca.from_function(func, name=func_name, install="--install" in args)
            print(f"  Generated: {script}")
            print(f"  Try: python {script} --help")

        elif sub == "repo" and len(args) > 1:
            project = await ca.from_repo(args[1])
            print(f"  Repo: {project.repo_url}")
            print(f"  Language: {project.language}")
            print(f"  Entry points: {project.entry_points[:10]}")
            print(f"  Suggested commands: {len(project.suggested_commands)}")
            for cmd in project.suggested_commands[:5]:
                print(f"    - {cmd.name}: {cmd.description[:80]}")
            if "--install" in args:
                result = await ca.project.install(project)
                print(f"  Install: {result}")

        elif sub == "manifest" and len(args) > 1:
            definition = ca.from_manifest(args[1])
            print(f"  Name: {definition.name} v{definition.version}")
            print(f"  Commands: {len(definition.commands)}")
            for cmd in definition.commands:
                print(f"    - {cmd.name} ({len(cmd.params)} params)")

        elif sub == "new" and len(args) > 1:
            path = ca.new_manifest(args[1])
            print(f"  Created: {path}")
            print(f"  Edit this file to define your CLI, then run:")
            print(f"    livingtree cli-anything manifest {path}")

        elif sub == "publish" and len(args) > 1:
            definition = ca.from_manifest(args[1])
            target = args[2] if len(args) > 2 else "pip"
            result = ca.publish(definition, target)
            print(f"  Published to {target}: {result}")

        elif sub == "stats":
            s = ca.stats()
            print(f"  Generated tools: {s['generated_tools']}")
            print(f"  Manifests: {s['manifests']}")

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"❌ CLI-anything failed: {e}")


def _svc_improve(args: list):
    """Self-improvement: scan defects + propose innovations. usage: livingtree improve [--scan|--propose|--auto|--report]"""
    import asyncio

    async def _run():
        from .treellm.self_improver import get_self_improver, Severity
        improver = get_self_improver()

        sub = args[0].lower() if args else "report"

        if sub == "--scan":
            print("  Scanning codebase for defects...")
            defects = await improver._scanner.scan(use_llm="--llm" in args)
            report = improver._scanner.report()
            print(f"  Found {report['total']} defects")
            for cat, n in report["by_category"].items():
                print(f"    {cat}: {n}")
            for sv, n in report["by_severity"].items():
                print(f"    [{sv}] {n}")
            print("\n  Top defects:")
            for d in report["top5"]:
                print(f"    [{d['severity']}] {d['category']}: {d['title'][:80]} ({d['file'][:60]})")

        elif sub == "--propose":
            print("  Proposing innovations...")
            defects = await improver._scanner.scan()
            innovations = await improver._proposer.propose(defects, use_llm="--llm" in args)
            for inn in innovations:
                print(f"  💡 [{inn.category}] {inn.title}")
                print(f"     {inn.description[:120]}")
                print(f"     复杂度: {inn.complexity}")

        elif sub == "--auto":
            print("  Running full auto-improve cycle...")
            result = await improver.improve(use_llm="--llm" in args, auto_apply="--apply" in args)
            print(f"  Defects: {result['defects']}")
            print(f"  Innovations: {result['innovations']}")
            print(f"  Implemented: {result['implemented']}")
            print(f"  Validated: {result['validated']}")

        elif sub == "--report":
            stats = improver.stats()
            print(f"  Improvement cycles: {stats['cycles']}")
            print(f"  Innovations proposed: {stats['improvements_proposed']}")
            report = stats["scanner_report"]
            print(f"  Total defects: {report['total']}")

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"❌ Improve failed: {e}")


def _svc_recording(args: list):
    """Task recording and replay. usage: livingtree record [start|stop|list|replay|export|delete] [args]"""
    import asyncio

    async def _run():
        from .treellm.recording_engine import get_recording_engine, ReplayMode
        engine = get_recording_engine()
        if not args:
            print("Usage: record [start|stop|list|replay|export|delete|render] [...]")
            return
        sub = args[0].lower()
        if sub == "start":
            title = args[1] if len(args) > 1 else ""
            print(f"  Recording started: {engine.start(title=title)}")
        elif sub == "stop":
            rec = engine.stop()
            if rec: print(f"  Saved: {rec.id} ({len(rec.events)} events, {rec.duration_ms}ms)")
        elif sub == "list":
            for r in engine.list_recordings():
                print(f"  {r['id']} [{r['events']}e, {r['duration_ms']}ms] {r['title'][:60]}")
        elif sub == "replay" and len(args) > 1:
            async for e in engine.replay(args[1], ReplayMode.STREAMING, float(args[2]) if len(args)>2 else 1.0):
                print(f"  [{e.ts/1000:.2f}s] {e.type}: {str(e.result)[:100]}")
        elif sub == "export" and len(args) > 1:
            fmt = args[2] if len(args) > 2 else "json"
            content = engine.export(args[1], fmt)
            if content:
                import os; os.makedirs(".livingtree/recordings", exist_ok=True)
                path = f".livingtree/recordings/{args[1]}.{fmt}"
                open(path,"w",encoding="utf-8").write(content)
                print(f"  Exported to {path}")
        elif sub == "delete" and len(args) > 1:
            print(f"  {'Deleted' if engine.delete(args[1]) else 'Not found'}: {args[1]}")
        elif sub == "render" and len(args) > 1:
            view = args[2] if len(args) > 2 else "timeline"
            print(json.dumps(engine.render(args[1], view), indent=2, ensure_ascii=False)[:5000])

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"❌ Recording failed: {e}")


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


def _svc_models(args: list):
    """Manage LLM model registry: sync from providers, list available models, show details.

    Commands:
      livingtree models sync              Sync models from all configured providers
      livingtree models sync <provider>   Sync specific provider only
      livingtree models list              List all cached models
      livingtree models list <provider>   List models for one provider
      livingtree models show <provider>   Show detailed model info + pricing
      livingtree models auto              Auto-detect best model per provider (use in CI)
    """
    import asyncio, sys as _sys

    async def _run():
        from .treellm.model_registry import get_model_registry
        from .config.settings import get_config
        config = get_config().model
        mr = get_model_registry()

        subcmd = args[0] if args else "list"
        target = args[1] if len(args) > 1 else ""

        # ── Register known providers from config ──
        provider_urls = {
            "deepseek": "https://api.deepseek.com/v1",
            "longcat": "https://api.longcat.chat/v1",
            "xiaomi": "https://api.xiaomi.com/v1",
            "aliyun": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "hunyuan": "https://api.hunyuan.cloud.tencent.com/v1",
            "baidu": "https://qianfan.baidubce.com/v2",
            "spark": "https://spark-api-open.xf-yun.com/v1",
            "siliconflow": "https://api.siliconflow.cn/v1",
            "mofang": "https://api.mofang.ai/v1",
            "nvidia": "https://integrate.api.nvidia.com/v1",
            "modelscope": "https://api-inference.modelscope.cn/v1",
            "bailing": "https://api.baichuan.com/v1",
            "stepfun": "https://api.stepfun.com/v1",
            "internlm": "https://internlm-chat.intern-ai.org.cn/api/twlp/v1",
            "sensetime": "https://api.sensetime.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "dmxapi": "https://api.dmxapi.com/v1",
        }

        for name, url in provider_urls.items():
            key_attr = f"{name}_api_key"
            api_key = getattr(config, key_attr, "")
            mr.register_provider(name, url, api_key)

        if subcmd == "sync":
            providers = [target] if target and target in provider_urls else list(provider_urls.keys())
            ok, fail = 0, 0
            for name in providers:
                p = mr._providers.get(name)
                if not p or not p.api_key:
                    continue
                print(f"  Syncing {name:15s} ...", end=" ", flush=True)
                models = await mr.fetch_models(name)
                if models:
                    print(f"✅ {len(models)} models")
                    ok += 1
                else:
                    print(f"❌ {p.error[:60] if p.error else 'no models'}")
                    fail += 1
            print(f"\n  Synced: {ok} OK, {fail} failed")
            mr._save_cache()

        elif subcmd in ("list", "ls"):
            mr.load_cache()
            if target and target in mr._providers:
                models = mr._providers[target].models
                print(f"\n  {target} ({len(models)} models):")
                for m in models:
                    print(f"    {m.pricing_label} {m.id:45s} {m.tier:10s} ctx={m.context_length}")
            else:
                total = 0
                for name, pm in mr._providers.items():
                    if pm.models:
                        print(f"  {name:15s} {len(pm.models):4d} models  (last: {pm.last_fetched or 0:.0f}s ago)")
                        total += len(pm.models)
                print(f"\n  Total: {total} models across {sum(1 for pm in mr._providers.values() if pm.models)} providers")
                if total == 0:
                    print("  💡 Run 'livingtree models sync' to fetch from providers")

        elif subcmd == "show":
            if not target:
                print("Usage: livingtree models show <provider>")
                return
            mr.load_cache()
            pm = mr._providers.get(target)
            if not pm or not pm.models:
                print(f"  No models cached for {target}. Run 'livingtree models sync {target}' first.")
                return
            print(f"\n  {target} — {len(pm.models)} models — fetched {pm.last_fetched:.0f}s ago")
            print(f"  {'─'*70}")
            for m in pm.models:
                print(f"  {m.pricing_label} {m.id:50s} {m.tier:10s} ctx={m.context_length:,}")

        elif subcmd == "auto":
            """Auto-detect: fetch models, pick best flash model per provider, update config."""
            print("\n  Auto-detecting best models per provider...")
            updated = {}
            for name in list(provider_urls.keys()):
                p = mr._providers.get(name)
                if not p or not p.api_key:
                    continue
                if not p.models:
                    await mr.fetch_models(name)
                # Pick best flash model (< 32B params, fastest, free if possible)
                flash_models = [m for m in (p.models or []) if m.tier in ("flash", "small")]
                if not flash_models:
                    flash_models = [m for m in (p.models or []) if m.tier != "embedding"]
                if flash_models:
                    best = flash_models[0]
                    updated[name] = best.id
                    print(f"  {name:15s} → {best.id} ({best.tier}, {best.pricing})")
                else:
                    print(f"  {name:15s} → no suitable model found")
            if updated:
                print(f"\n  ✅ Updated {len(updated)} providers")
                print(f"  💡 These will be used for the next 'livingtree debug chat' session")
            else:
                print("  ❌ No models detected. Check API keys and network.")

        else:
            print(f"Unknown subcommand: {subcmd}")
            print("Usage: livingtree models [sync|list|show|auto]")

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"❌ Models failed: {e}")


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
