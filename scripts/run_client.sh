#!/bin/bash
# LivingTree AI Agent - Linux/Mac Startup Script
# Usage:
#   ./scripts/run_client.sh              - Start client (default)
#   ./scripts/run_client.sh client       - Start desktop client
#   ./scripts/run_client.sh relay        - Start relay server
#   ./scripts/run_client.sh tracker      - Start tracker server
#   ./scripts/run_client.sh all          - Start all services

COMMAND="${1:-client}"

case "$COMMAND" in
    client)
        echo "🌳 Starting LivingTree AI Agent Client..."
        python3 main.py client
        ;;
    relay)
        echo "🔄 Starting Relay Server..."
        python3 main.py relay
        ;;
    tracker)
        echo "📊 Starting Tracker Server..."
        python3 main.py tracker
        ;;
    all)
        echo "🌳 Starting All Services..."
        python3 main.py relay &
        sleep 2
        python3 main.py tracker &
        sleep 2
        python3 main.py client
        ;;
    *)
        echo "Usage: $0 [client|relay|tracker|all]"
        exit 1
        ;;
esac
