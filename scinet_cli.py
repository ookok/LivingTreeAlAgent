"""Scinet standalone console — 智能代理独立控制台程序 v2.0.

用法:
    scinet.exe              # 启动代理 (默认端口 7890)
    scinet.exe --port 8080  # 指定端口
    scinet.exe --pac        # 自动配置 Windows 系统代理
    scinet.exe --wt         # 启用 WebTransport

编译:
    pyinstaller --clean scinet.spec
"""

import sys, os, asyncio, signal, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from livingtree.network.scinet_service import get_scinet


def main():
    parser = argparse.ArgumentParser(description="Scinet v2.0 — LivingTree Smart Proxy")
    parser.add_argument("--port", type=int, default=7890, help="代理端口 (默认 7890)")
    parser.add_argument("--no-pac", action="store_true", help="不要自动配置 Windows 系统代理")
    parser.add_argument("--wt", action="store_true", help="启用 WebTransport")
    parser.add_argument("--dns", action="store_true", help="启用 Smart DNS 分流")
    parser.add_argument("--dns-port", type=int, default=5353, help="DNS 端口 (默认 5353)")
    args = parser.parse_args()

    scinet = get_scinet(port=args.port)
    dns = None
    if args.dns:
        from livingtree.network.smart_dns import get_smart_dns
        dns = get_smart_dns(port=args.dns_port)

    async def run():
        print(f"[Scinet v2.0] Starting on port {args.port}...")
        status = await scinet.start()
        await asyncio.sleep(1)

        print(f"\n  Status:    {'RUNNING' if status.running else 'FAILED'}")
        print(f"  Proxy:     http://127.0.0.1:{args.port}")
        print(f"  PAC:       http://127.0.0.1:{args.port}/pac")

        if scinet._proxy_pool:
            ps = scinet._proxy_pool.stats()
            print(f"  Proxies:   {ps['total']} total, {ps['healthy']} healthy")

        if scinet._v2_enabled:
            print(f"  Engine:    BanditRL + GNN Topology + Federated + QUIC + Cache")

        if args.pac and sys.platform == "win32":
            scinet.set_windows_proxy(True)
            print(f"  System:    Windows proxy configured -> 127.0.0.1:{args.port}")

        if args.dns and dns:
            try:
                await dns.start()
                print(f"  DNS:       127.0.0.1:{args.dns_port}")
            except Exception as e:
                print(f"  DNS:       error ({e})")

        if args.wt:
            try:
                from livingtree.network.scinet_webtransport import get_webtransport_server
                wt = get_webtransport_server(port=args.port + 1)
                await wt.start()
                print(f"  WebTransport: https://127.0.0.1:{args.port + 1}/scinet/wt")
            except Exception as e:
                print(f"  WebTransport: unavailable ({e})")

        print(f"\n  按 Ctrl+C 停止...\n")

        stop_event = asyncio.Event()
        def _shutdown():
            print("\n[Scinet] Shutting down...")
            stop_event.set()

        if sys.platform == "win32":
            signal.signal(signal.SIGINT, lambda s, f: _shutdown())
        else:
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGINT, _shutdown)
            loop.add_signal_handler(signal.SIGTERM, _shutdown)

        await stop_event.wait()

        if args.pac and sys.platform == "win32":
            scinet.set_windows_proxy(False)
        await scinet.stop()
        print("[Scinet] Stopped.")

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n[Scinet] Interrupted.")


if __name__ == "__main__":
    main()
