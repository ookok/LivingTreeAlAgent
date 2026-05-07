"""LivingTree AI Agent — Unified CLI Entry Point

Usage:
    python -m livingtree              # Start web server (default)
    python -m livingtree web          # Start web server with UI
    python -m livingtree server       # API server only (no UI)
    python -m livingtree client       # Interactive CLI chat
    python -m livingtree test         # Integration tests
    python -m livingtree check        # Environment check
"""

import sys
import os


def main():
    if len(sys.argv) < 2:
        _start_web()
        return

    command = sys.argv[1].lower()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    if command in ("--version", "-v", "version"):
        print("LivingTree AI Agent v2.1.0")
        return

    if command in ("--help", "-h", "help"):
        _print_usage()
        return

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
    elif command in ("update", "upgrade"):
        from .integration.self_updater import run_update
        import asyncio, json
        result = asyncio.run(run_update())
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Unknown command: {command}")
        _print_usage()
        sys.exit(1)


def _start_web():
    """Start web server with UI and API."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    from .integration.launcher import launch, LaunchMode
    launch(LaunchMode.SERVER)


def _print_usage():
    print("""
LivingTree AI Agent v2.1.0 — Digital Lifeform Platform

Commands:
  (none)          Start web server with UI (default)
  web, ui         Start web server with UI
  server, api     API server (no UI)
  client, cli     Interactive CLI chat
  test            Run integration tests
  check, env      Environment check
  quick [msg]     Single quick interaction
  --version, -v   Show version
  --help, -h      Show this help

Examples:
  python -m livingtree           # Web UI at http://localhost:8100
  python -m livingtree web       # Same as above
  python -m livingtree server    # API only
""")


if __name__ == "__main__":
    main()
