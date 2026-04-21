#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LivingTree AI Agent - Unified Entry Point

Usage:
    python main.py client      # Start desktop client
    python main.py relay       # Start relay server
    python main.py tracker     # Start tracker server
    python main.py app         # Start enterprise app
"""

import sys
import os
import subprocess


def start_client():
    """Start desktop client"""
    print("🌳 Starting LivingTree AI Agent Client...")
    client_main = os.path.join(os.path.dirname(__file__), 'client', 'src', 'main.py')
    os.execv(sys.executable, [sys.executable, client_main])


def start_relay():
    """Start relay server"""
    print("🔄 Starting Relay Server...")
    relay_main = os.path.join(os.path.dirname(__file__), 'server', 'relay_server', 'main.py')
    os.execv(sys.executable, [sys.executable, relay_main])


def start_tracker():
    """Start tracker server"""
    print("📊 Starting Tracker Server...")
    tracker_server = os.path.join(os.path.dirname(__file__), 'server', 'tracker_server.py')
    os.execv(sys.executable, [sys.executable, tracker_server])


def start_app():
    """Start enterprise app"""
    print("🏢 Starting Enterprise App...")
    app_main = os.path.join(os.path.dirname(__file__), 'app', 'main.py')
    os.execv(sys.executable, [sys.executable, app_main])


def main():
    if len(sys.argv) < 2:
        print("LivingTree AI Agent - Unified Entry Point")
        print()
        print("Usage:")
        print("  python main.py client      # Start desktop client")
        print("  python main.py relay       # Start relay server")
        print("  python main.py tracker     # Start tracker server")
        print("  python main.py app         # Start enterprise app")
        print()
        print("Default: client")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == 'client':
        start_client()
    elif command == 'relay':
        start_relay()
    elif command == 'tracker':
        start_tracker()
    elif command == 'app':
        start_app()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: client, relay, tracker, app")
        sys.exit(1)


if __name__ == '__main__':
    main()
