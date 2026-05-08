"""Scinet standalone console — 智能代理独立控制台程序.

用法:
    scinet.exe              # 启动代理 (默认端口 7890)
    scinet.exe --port 8080  # 指定端口
    scinet.exe --pac        # 生成 PAC 文件

编译:
    pyinstaller --onefile --name scinet scinet_cli.py
"""

import sys
import asyncio
import signal
import argparse

def main():
    parser = argparse.ArgumentParser(description="Scinet — LivingTree 智能代理")
    parser.add_argument("--port", type=int, default=7890, help="代理端口 (默认 7890)")
    parser.add_argument("--pac", action="store_true", help="生成 PAC 文件")
    args = parser.parse_args()

    from livingtree.network.scinet_service import get_scinet

    scinet = get_scinet(port=args.port)

    if args.pac:
        # Generate PAC file and exit
        pac_url = scinet.generate_pac()
        print(f"[Scinet] PAC file → {pac_url}")
        return

    async def run():
        print(f"[Scinet] Starting on port {args.port}...")
        status = await scinet.start()
        print(f"[Scinet] {'RUNNING' if status.running else 'FAILED'}")
        print(f"  Port:     {status.port}")
        print(f"  IP Pool:  {status.domain_ip_pool_ready}")
        print(f"  Proxy:    {status.proxy_pool_ready}")
        print(f"  Accel:    {status.accelerator_ready}")
        print(f"\n  Proxy:    http://127.0.0.1:{args.port}")
        print(f"  PAC:      http://127.0.0.1:{args.port}/proxy.pac")
        print(f"\n按 Ctrl+C 停止...\n")

        # Wait for shutdown
        stop_event = asyncio.Event()
        loop = asyncio.get_event_loop()

        def _shutdown():
            print("\n[Scinet] Shutting down...")
            stop_event.set()

        if sys.platform == "win32":
            signal.signal(signal.SIGINT, lambda s, f: _shutdown())
        else:
            loop.add_signal_handler(signal.SIGINT, _shutdown)
            loop.add_signal_handler(signal.SIGTERM, _shutdown)

        await stop_event.wait()
        await scinet.stop()
        print("[Scinet] Stopped.")

    asyncio.run(run())


if __name__ == "__main__":
    main()
