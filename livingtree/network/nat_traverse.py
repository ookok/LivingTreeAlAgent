"""NATTraverser — STUN-based NAT traversal and connectivity testing."""
from __future__ import annotations
import asyncio, socket, struct, random
from typing import Optional
from loguru import logger

STUN_SERVERS = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun.miwifi.com", 3478),
]
STUN_MAGIC = 0x2112A442

class NATTraverser:
    async def get_public_endpoint(self) -> tuple[str, int]:
        for host, port in STUN_SERVERS:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                tid = struct.pack(">I", random.randint(0, 0xFFFFFFFF))
                req = struct.pack(">HHI12s", 0x0001, 0, STUN_MAGIC, tid)
                sock.sendto(req, (host, port))
                data, addr = sock.recvfrom(1024)
                sock.close()
                if len(data) >= 20:
                    resp_type = struct.unpack(">H", data[0:2])[0]
                    if resp_type == 0x0101:
                        port_val = struct.unpack(">H", data[26:28])[0]
                        ip_val = ".".join(str(b) for b in data[28:32])
                        logger.debug(f"NAT public endpoint: {ip_val}:{port_val} (via {host})")
                        return (ip_val, port_val)
            except Exception as e:
                logger.debug(f"STUN {host}: {e}")
                continue
        logger.warning("STUN failed, using fallback")
        return ("0.0.0.0", 0)

    async def try_direct_connect(self, target: tuple[str, int]) -> bool:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target[0], target[1]), timeout=5
            )
            writer.close()
            return True
        except Exception:
            return False

    async def establish_relay(self, target: tuple[str, int]) -> dict | None:
        logger.info(f"Relay to {target} — direct mode only")
        reachable = await self.try_direct_connect(target)
        return {"relay_addr": target[0], "port": target[1]} if reachable else None

    async def is_reachable(self, target: tuple[str, int]) -> bool:
        return await self.try_direct_connect(target)
