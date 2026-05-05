"""LivingTree AI Agent — Unified CLI Entry Point

Usage:
    python -m livingtree client      # Interactive CLI chat client
    python -m livingtree server      # FastAPI server (http://localhost:8100)
    python -m livingtree tui         # Textual TUI (Windows Terminal)
    python -m livingtree test        # Integration tests
    python -m livingtree check       # Environment check
    python -m livingtree quick <msg> # Single quick interaction
    python main.py livingtree <cmd>  # Via root main.py
"""

import sys
import os
import json


def main():
    """CLI entry point for the livingtree module."""
    if len(sys.argv) < 2:
        _print_usage()
        sys.exit(0)

    command = sys.argv[1].lower()
    args = sys.argv[2:]

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    if command in ("tui", "terminal", "textual"):
        workspace_args = [a for a in args if not a.startswith("-")]
        workspace = workspace_args[0] if workspace_args else os.getcwd()
        if "--direct" in args:
            os.chdir(project_root)
            from .tui.app import run_tui
            run_tui(workspace=workspace)
        else:
            import subprocess
            bootstrapper = os.path.join(os.path.dirname(__file__), "tui", "wt_bootstrap.py")
            subprocess.Popen([sys.executable, bootstrapper, workspace], cwd=project_root)
        return

    if command in ("--version", "-v", "version"):
        from . import __version__
        print(f"LivingTree AI Agent v{__version__}")
        return

    if command in ("--help", "-h", "help"):
        _print_usage()
        return

    from .integration.launcher import launch, LaunchMode

    if command in ("client", "cli"):
        launch(LaunchMode.CLIENT)
    elif command in ("server", "api"):
        launch(LaunchMode.SERVER)
    elif command == "test":
        launch(LaunchMode.TEST)
    elif command in ("check", "env"):
        launch(LaunchMode.CHECK)
    elif command in ("quick", "q"):
        launch(LaunchMode.QUICK)
    elif command in ("update", "upgrade"):
        from .integration.self_updater import run_update
        import asyncio
        result = asyncio.run(run_update())
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("restart_required"):
            print("\n⚠ 重启以应用更新: python -m livingtree tui --update")
    elif command == "_update_cli":
        # Internal: direct update from CLI without full hub boot
        from .integration.self_updater import run_update
        import asyncio
        result = asyncio.run(run_update(
            check_only="--check" in args,
            dry_run="--dry-run" in args,
            use_mirror="--mirror" in args,
            install_deps="--no-deps" not in args,
        ))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Unknown command: {command}")
        _print_usage()
        sys.exit(1)


def _print_usage():
    print(f"""
LivingTree AI Agent v2.0.0 — Digital Lifeform Platform

Commands:
  client, cli      Interactive CLI chat client
  server, api      Start FastAPI server (http://localhost:8100)
  tui, terminal    Launch Textual TUI (Windows Terminal)
  test             Run integration tests
  check, env       Environment check
  quick [msg]      Single quick interaction
  --version, -v    Show version
  --help, -h       Show this help

Examples:
  python -m livingtree tui
  python -m livingtree client
  python -m livingtree server
  python -m livingtree test
""")


if __name__ == "__main__":
    main()
