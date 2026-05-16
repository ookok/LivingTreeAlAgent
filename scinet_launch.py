"""Scinet v2.0 — One-click proxy launcher.

Usage:
    python scinet_launch.py                # start + auto-configure system proxy
    python scinet_launch.py --no-pac       # start WITHOUT system proxy config
    python scinet_launch.py --port 8080    # custom port
    python scinet_launch.py --wt           # enable WebTransport (port+1)

Features:
    - Auto-configures Windows system proxy (127.0.0.1:{port})
    - Local HTTP/HTTPS proxy on 127.0.0.1:{port}
    - 6-source proxy pool auto-refresh (every 10min)
    - 100+ overseas domain IP pool with pre-tested optimal IPs
    - v2.0 Engine: BanditRL + GNN Topology + Federated + QUIC + Cache
    - Management UI: http://127.0.0.1:{port}/
    - PAC auto-config: http://127.0.0.1:{port}/pac
    - API status: http://127.0.0.1:{port}/v2/status
"""

import asyncio
import signal
import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from livingtree.network.scinet_service import ScinetService, get_scinet

BANNER = r"""
  ╔══════════════════════════════════════════════════╗
  ║        🌐 Scinet v2.0 — Smart Proxy             ║
  ║   RL Bandit · GNN Topology · QUIC Tunnel        ║
  ║   Federated Learning · Semantic Cache           ║
  ╚══════════════════════════════════════════════════╝
"""

USAGE_TIPS = """
  Browser Setup:
    Proxy:  127.0.0.1:{port}
    PAC:    http://127.0.0.1:{port}/pac
    
  Test:
    curl -x http://127.0.0.1:{port} https://github.com
    
  Dashboard:
    http://127.0.0.1:{port}/v2/status
    
  Commands:
    Ctrl+C  — Stop Scinet
"""


async def main():
    parser = argparse.ArgumentParser(description="Scinet v2.0 — Smart Proxy Launcher")
    parser.add_argument("--port", type=int, default=7890, help="Proxy port (default: 7890)")
    parser.add_argument("--no-pac", action="store_true", help="Do NOT auto-set Windows system proxy")
    parser.add_argument("--wt", action="store_true", help="Enable WebTransport (port+1)")
    args = parser.parse_args()

    print(BANNER)
    print(f"  Starting on port {args.port}...\n")

    scinet = ScinetService(port=args.port)

    status = await scinet.start()
    if not status.running:
        print(f"\n  ✗ Failed to start on port {args.port}")
        return 1

    # Show status
    await asyncio.sleep(3)
    stats = scinet.get_status()

    print(f"  ✓ Proxy:    http://127.0.0.1:{args.port}")
    print(f"  ✓ PAC:      http://127.0.0.1:{args.port}/pac")
    print(f"  ✓ Status:   http://127.0.0.1:{args.port}/v2/status")
    print(f"  ✓ Subsystems: DomainIPPool + ProxyPool(6 sources) + v2.0 Engine")

    # Proxy pool info
    if scinet._proxy_pool:
        pstats = scinet._proxy_pool.stats()
        print(f"  ✓ Proxies:  {pstats['total']} total, {pstats['healthy']} healthy")

    # IP pool info
    if scinet._ip_pool:
        ipstats = scinet._ip_pool.get_stats()
        print(f"  ✓ IP Pool:  {ipstats['total_domains']} domains, {ipstats['total_ips']} IPs")

    # v2.0 engine
    if scinet._v2_enabled:
        print(f"  ✓ Engine:   BanditRL + GNN + Federated + QUIC + Cache")

    print(USAGE_TIPS.format(port=args.port))

    # Windows system proxy auto-config
    if not args.no_pac and sys.platform == "win32":
        scinet.set_windows_proxy(True)
        print("  ✓ Windows system proxy configured")

    # WebTransport
    if args.wt:
        try:
            from livingtree.network.scinet_webtransport import get_webtransport_server
            wt = get_webtransport_server(port=args.port + 1)
            await wt.start()
            print(f"  ✓ WebTransport: https://127.0.0.1:{args.port + 1}/scinet/wt")
        except Exception as e:
            print(f"  ⚠ WebTransport failed: {e}")

    # Periodic status refresh
    last_status_time = time.time()

    async def periodic_status():
        nonlocal last_status_time
        while scinet._running:
            await asyncio.sleep(30)
            now = time.time()
            if now - last_status_time > 20:
                s = scinet.get_status()
                ps = scinet._proxy_pool.stats() if scinet._proxy_pool else {}
                print(f"\n  [{time.strftime('%H:%M:%S')}] Requests: {s.total_requests} | "
                      f"Success: {s.success_requests}/{s.total_requests} | "
                      f"Proxies: {ps.get('healthy', 0)}/{ps.get('total', 0)}")

    status_task = asyncio.create_task(periodic_status())

    # Wait for shutdown signal
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    if sys.platform == "win32":
        signal.signal(signal.SIGINT, lambda s, f: stop_event.set())
    else:
        loop.add_signal_handler(signal.SIGINT, stop_event.set)
        loop.add_signal_handler(signal.SIGTERM, stop_event.set)

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        print("\n\n  Shutting down...")
        status_task.cancel()
        if not args.no_pac and sys.platform == "win32":
            scinet.set_windows_proxy(False)
        if args.wt:
            from livingtree.network.scinet_webtransport import get_webtransport_server
            await get_webtransport_server().stop()
        await scinet.stop()
        print("  ✓ Scinet stopped. Goodbye.\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        sys.exit(0)
