"""Scinet standalone console — 智能代理独立控制台程序 v2.0.

用法:
    scinet.exe              # 启动代理 (默认端口 7890)
    scinet.exe --port 8080  # 指定端口
    scinet.exe --pac        # 自动配置 Windows 系统代理
    scinet.exe --wt         # 启用 WebTransport

编译:
    pyinstaller --clean scinet.spec
"""

import sys, os, asyncio, signal, argparse, importlib.util

BASE = os.path.dirname(os.path.abspath(__file__))

def _load_module(name: str, path: str):
    """Load a module by file path — bypasses package __init__.py chain."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Import scinet directly, bypassing livingtree/__init__.py heavy chain
_scinet = _load_module("scinet_service", os.path.join(BASE, "livingtree", "network", "scinet_service.py"))
get_scinet = _scinet.get_scinet


def main():
    parser = argparse.ArgumentParser(description="Scinet v2.0 — LivingTree Smart Proxy")
    parser.add_argument("--port", type=int, default=7890, help="代理端口 (默认 7890)")
    parser.add_argument("--pac", action="store_true", help="自动配置 Windows 系统代理")
    parser.add_argument("--wt", action="store_true", help="启用 WebTransport")
    parser.add_argument("--dns", action="store_true", help="启用 Smart DNS 分流")
    parser.add_argument("--dns-port", type=int, default=5353, help="DNS 端口 (默认 5353)")
    args = parser.parse_args()

    scinet = get_scinet(port=args.port)
    dns = None
    if args.dns:
        _dns_mod = _load_module("smart_dns", os.path.join(BASE, "livingtree", "network", "smart_dns.py"))
        dns = _dns_mod.get_smart_dns(port=args.dns_port)

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
                _wt = _load_module("scinet_webtransport", os.path.join(BASE, "livingtree", "network", "scinet_webtransport.py"))
                wt = _wt.get_webtransport_server(port=args.port + 1)
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
