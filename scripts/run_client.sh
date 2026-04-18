#!/bin/bash
# Hermes Desktop V2.0 - Linux/Mac 启动脚本

echo "╔══════════════════════════════════════════════╗"
echo "║   Hermes Desktop V2.0                       ║"
echo "║   生命主干 - The Trunk                      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

MODE=${1:-client}

case $MODE in
    client)
        echo "🚀 启动桌面客户端..."
        python main.py client
        ;;
    relay)
        echo "🌐 启动中继服务器..."
        python -m uvicorn server.relay_server.main:app --host 0.0.0.0 --port 8766
        ;;
    tracker)
        echo "📊 启动追踪服务器..."
        python server/tracker/tracker_server.py
        ;;
    all)
        echo "🚀 启动所有服务..."
        python -m uvicorn server.relay_server.main:app --host 0.0.0.0 --port 8766 &
        python server/tracker/tracker_server.py &
        python main.py client
        ;;
    *)
        echo "用法: ./run.sh [client|relay|tracker|all]"
        ;;
esac
