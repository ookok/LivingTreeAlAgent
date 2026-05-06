"""Smart DNS Split Tunnel — zero-config overseas acceleration.

Core innovation: local DNS server that auto-routes overseas domains to
optimal IPs while passing Chinese domains through normally.

How it works:
  1. Run local DNS server on 127.0.0.1:53 (or :5353 if 53 requires admin)
  2. Set system DNS to 127.0.0.1 (one-time)
  3. All DNS queries flow through:
     - .cn / known Chinese domains → forward to upstream DNS (direct)
     - Overseas domains (github.com, etc.) → return optimal IP from pool
     - Unknown domains → DoH resolve + cache

Zero config advantages over HTTP proxy:
  - No browser/proxy settings needed (just change DNS once)
  - Works for ALL apps: git, pip, npm, curl, browsers, IDEs
  - No certificate issues (DNS only, no TLS MITM)
  - No PAC file needed
  - Transparent to applications
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ DNS Protocol Constants ═══

DNS_PORT = 53
DNS_ALT_PORT = 5353  # Alternative port (no admin required)

# Upstream DNS servers
UPSTREAM_DNS = [
    ("223.5.5.5", 53),     # AliDNS
    ("119.29.29.29", 53),   # DNSPod
    ("114.114.114.114", 53),  # 114DNS
]
UPSTREAM_DOH = "https://dns.alidns.com/dns-query"

# DNS record types
TYPE_A = 1
TYPE_AAAA = 28
CLASS_IN = 1


@dataclass
class DNSCacheEntry:
    """Cached DNS resolution result."""
    domain: str
    ip: str
    ttl: int = 300
    resolved_at: float = field(default_factory=time.time)

    @property
    def expired(self) -> bool:
        return time.time() - self.resolved_at > self.ttl


@dataclass
class SmartDNSStatus:
    """Smart DNS server status."""
    running: bool = False
    port: int = DNS_ALT_PORT
    total_queries: int = 0
    accelerated_queries: int = 0   # returned from IP pool
    forwarded_queries: int = 0     # forwarded to upstream
    cached_hits: int = 0
    uptime_seconds: float = 0.0
    cache_size: int = 0


class SmartDNSServer:
    """Zero-config Smart DNS Split Tunnel.

    Usage:
        dns = SmartDNSServer(port=5353)  # 5353 = no admin required
        await dns.start()
        # Set system DNS to 127.0.0.1:5353 (or 127.0.0.1 if port 53)
        # All overseas sites now auto-accelerated!

        dns.get_status()
        await dns.stop()
    """

    def __init__(self, port: int = DNS_ALT_PORT, upstream_port: int = DNS_PORT):
        self.port = port
        self.upstream_port = upstream_port
        self._status = SmartDNSStatus(port=port)
        self._lock = threading.RLock()
        self._running = False
        self._server: Optional[asyncio.AbstractServer] = None
        self._start_time: float = 0.0

        # DNS cache
        self._cache: dict[str, DNSCacheEntry] = {}
        self._ip_pool: Any = None

        # Chinese domain patterns
        self._cn_suffixes = ('.cn', '.com.cn', '.org.cn', '.edu.cn', '.gov.cn',
                            '.net.cn', '.ac.cn', '.mil.cn')
        self._local_domains = {'localhost', 'local', 'home', 'lan'}

    async def start(self) -> SmartDNSStatus:
        if self._running:
            return self._status

        await self._init_ip_pool()

        loop = asyncio.get_event_loop()
        try:
            self._server = await loop.create_datagram_endpoint(
                lambda: _DNSProtocol(self),
                local_addr=('127.0.0.1', self.port),
            )
        except OSError as e:
            logger.error("SmartDNS: port %d in use — try port %d", self.port, DNS_ALT_PORT)
            raise RuntimeError(f"Port {self.port} occupied") from e

        self._running = True
        self._start_time = time.time()
        self._status.running = True

        logger.info("SmartDNS: listening on 127.0.0.1:%d", self.port)
        logger.info("  Set DNS to 127.0.0.1 to enable (or 127.0.0.1:%d if using custom port)", self.port)
        logger.info("  Chinese domains → direct | Overseas → accelerated | Others → DoH + cache")
        return self._status

    async def stop(self) -> SmartDNSStatus:
        if not self._running:
            return self._status

        if self._server:
            self._server.close()
            self._server = None

        self._running = False
        self._status.running = False
        self._status.uptime_seconds = time.time() - self._start_time

        logger.info("SmartDNS: stopped (%d queries, %d accelerated)",
                   self._status.total_queries, self._status.accelerated_queries)
        return self._status

    def get_status(self) -> SmartDNSStatus:
        with self._lock:
            if self._running:
                self._status.uptime_seconds = time.time() - self._start_time
                self._status.cache_size = len(self._cache)
            return self._status

    # ═══ DNS Resolution Logic ═══

    async def resolve(self, domain: str, qtype: int = TYPE_A) -> str:
        """Resolve a domain: check IP pool → cache → upstream DNS."""
        with self._lock:
            self._status.total_queries += 1

        # Check cache
        cache_key = f"{domain}:{qtype}"
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and not cached.expired:
                self._status.cached_hits += 1
                return cached.ip

        # Chinese domain → pass through (don't accelerate)
        if self._is_chinese_domain(domain):
            return await self._forward_to_upstream(domain, qtype)

        # Overseas domain → check IP pool
        ip = self._get_from_pool(domain)
        if ip:
            with self._lock:
                self._status.accelerated_queries += 1
                self._cache[cache_key] = DNSCacheEntry(domain=domain, ip=ip)
            return ip

        # Unknown domain → forward + cache
        ip = await self._forward_to_upstream(domain, qtype)
        if ip:
            with self._lock:
                self._status.forwarded_queries += 1
                self._cache[cache_key] = DNSCacheEntry(domain=domain, ip=ip)
        return ip

    # ═══ Helpers ═══

    def _is_chinese_domain(self, domain: str) -> bool:
        domain = domain.lower().rstrip('.')
        if domain in self._local_domains:
            return True
        return any(domain.endswith(s) for s in self._cn_suffixes)

    def _get_from_pool(self, domain: str) -> str:
        """Get optimal IP from the pre-tested IP pool."""
        if not self._ip_pool:
            return ""
        try:
            best = self._ip_pool.get_best(domain)
            if best and best.is_healthy:
                return best.ip
        except Exception:
            pass
        return ""

    async def _forward_to_upstream(self, domain: str, qtype: int = TYPE_A) -> str:
        """Forward DNS query to upstream DNS server."""
        # Try DoH first
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                params = {"name": domain, "type": qtype}
                async with session.get(UPSTREAM_DOH, params=params,
                                      timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        answers = data.get("Answer", [])
                        for ans in answers:
                            if ans.get("type") == qtype:
                                return ans.get("data", "")
        except Exception:
            pass

        # Fallback: UDP DNS query
        try:
            for upstream_host, upstream_port in UPSTREAM_DNS:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(2.0)
                query = self._build_dns_query(domain, qtype)
                sock.sendto(query, (upstream_host, upstream_port))
                data, _ = sock.recvfrom(512)
                sock.close()
                ip = self._parse_dns_response(data)
                if ip:
                    return ip
        except Exception:
            pass

        return ""

    @staticmethod
    def _build_dns_query(domain: str, qtype: int = TYPE_A) -> bytes:
        """Build a DNS query packet."""
        transaction_id = int(time.time() * 1000) % 65536
        flags = 0x0100  # Standard query, recursion desired
        questions = 1

        header = struct.pack(">HHHHHH", transaction_id, flags, questions, 0, 0, 0)

        # Encode domain name
        qname = b""
        for part in domain.rstrip(".").split("."):
            qname += bytes([len(part)]) + part.encode()
        qname += b"\x00"

        question = qname + struct.pack(">HH", qtype, CLASS_IN)
        return header + question

    @staticmethod
    def _parse_dns_response(data: bytes) -> str:
        """Parse DNS response, extract first A record IP."""
        try:
            if len(data) < 12:
                return ""
            answers = struct.unpack(">H", data[6:8])[0]
            if answers == 0:
                return ""

            # Skip header (12 bytes) + question section
            pos = 12
            while pos < len(data) and data[pos] != 0:
                if data[pos] & 0xC0 == 0xC0:
                    pos += 2
                    break
                pos += data[pos] + 1
            if data[pos] == 0:
                pos += 1
            pos += 4  # Skip QTYPE + QCLASS

            # Read answers
            for _ in range(answers):
                if pos + 12 > len(data):
                    break
                if data[pos] & 0xC0 == 0xC0:
                    pos += 2
                else:
                    while pos < len(data) and data[pos] != 0:
                        pos += data[pos] + 1
                    pos += 1
                rtype = struct.unpack(">H", data[pos:pos+2])[0]
                pos += 8  # Skip type(2) + class(2) + ttl(4)
                rdlength = struct.unpack(">H", data[pos:pos+2])[0]
                pos += 2
                if rtype == TYPE_A and rdlength == 4:
                    ip = ".".join(str(b) for b in data[pos:pos+4])
                    return ip
                pos += rdlength
        except Exception:
            pass
        return ""

    async def _init_ip_pool(self) -> None:
        try:
            from .domain_ip_pool import DomainIPPool
            self._ip_pool = DomainIPPool()
            await self._ip_pool.initialize()
        except Exception as e:
            logger.debug("SmartDNS: IP pool init skipped: %s", e)


# ═══ DNS Protocol Handler (asyncio UDP) ═══

class _DNSProtocol(asyncio.DatagramProtocol):
    """Async UDP DNS protocol handler."""

    def __init__(self, server: SmartDNSServer):
        self._server = server
        self._transport = None

    def connection_made(self, transport):
        self._transport = transport

    def datagram_received(self, data, addr):
        """Handle incoming DNS query."""
        if len(data) < 12:
            return

        # Parse domain from query
        domain = self._parse_query_domain(data)
        if not domain:
            return

        qtype = struct.unpack(">H", data[4:6])[0] if len(data) > 6 else TYPE_A

        # Resolve asynchronously
        asyncio.ensure_future(self._handle_query(data, addr, domain, qtype))

    async def _handle_query(self, query_data: bytes, addr: tuple,
                            domain: str, qtype: int):
        ip = await self._server.resolve(domain, qtype)
        if ip and self._transport:
            response = self._build_response(query_data, ip)
            self._transport.sendto(response, addr)

    @staticmethod
    def _parse_query_domain(data: bytes) -> str:
        """Extract domain name from DNS query."""
        try:
            parts = []
            pos = 12  # Skip header
            while pos < len(data) and data[pos] != 0:
                length = data[pos]
                if length & 0xC0 == 0xC0:
                    break
                pos += 1
                if pos + length <= len(data):
                    parts.append(data[pos:pos+length].decode('ascii', errors='replace'))
                    pos += length
            return ".".join(parts) if parts else ""
        except Exception:
            return ""

    @staticmethod
    def _build_response(query: bytes, ip: str) -> bytes:
        """Build a minimal DNS response."""
        if len(query) < 12:
            return b""
        transaction_id = query[:2]
        flags = struct.pack(">H", 0x8180)  # Standard response, no error
        header = transaction_id + flags + query[4:6] + struct.pack(">HHHH", 1, 0, 0, 0)

        # Copy question section
        pos = 12
        while pos < len(query) and query[pos] != 0:
            if query[pos] & 0xC0 == 0xC0:
                pos += 2
                break
            pos += query[pos] + 1
        if pos < len(query) and query[pos] == 0:
            pos += 1
        question = query[12:pos+4]

        # Build answer
        ip_parts = [int(p) for p in ip.split(".")]
        answer_name = b"\xc0\x0c"  # Pointer to question
        answer = answer_name + struct.pack(">HHIH", TYPE_A, CLASS_IN, 300, 4) + bytes(ip_parts)

        return header + question + answer


# ═══ WPAD / PAC Auto-Discovery ═══

def generate_wpad_dat(proxy_host: str = "127.0.0.1", proxy_port: int = 7890) -> str:
    """Generate a wpad.dat PAC file for Windows auto-discovery.

    Place at http://wpad/wpad.dat or serve locally.
    """
    from .scinet_service import PAC_TEMPLATE
    return PAC_TEMPLATE.format(port=proxy_port, accelerated_domains="")


# ═══ One-Click System Toggle ═══

class SystemProxyToggle:
    """One-click system proxy on/off for Windows/macOS/Linux."""

    @staticmethod
    def enable_windows(proxy_host: str = "127.0.0.1", proxy_port: int = 7890) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0, winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ,
                            f"{proxy_host}:{proxy_port}")
            winreg.CloseKey(key)
            logger.info("SystemProxy: Windows enabled → %s:%d", proxy_host, proxy_port)
            return True
        except Exception as e:
            logger.warning("SystemProxy: %s", e)
            return False

    @staticmethod
    def disable_windows() -> bool:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0, winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            logger.info("SystemProxy: Windows disabled")
            return True
        except Exception as e:
            logger.warning("SystemProxy: %s", e)
            return False

    @staticmethod
    def enable_dns(dns_ip: str = "127.0.0.1") -> bool:
        """Set system DNS to SmartDNS (simplest zero-config approach)."""
        try:
            import winreg
            # Get active network interface
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces",
                0, winreg.KEY_READ,
            )
            # Find first interface with DhcpNameServer
            for i in range(100):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
                    try:
                        winreg.QueryValueEx(subkey, "DhcpNameServer")
                        winreg.SetValueEx(subkey, "NameServer", 0, winreg.REG_SZ, dns_ip)
                        winreg.CloseKey(subkey)
                        logger.info("SystemProxy: DNS set to %s on interface %s", dns_ip, subkey_name)
                        return True
                    except Exception:
                        winreg.CloseKey(subkey)
                except Exception:
                    break
            winreg.CloseKey(key)
            logger.warning("SystemProxy: no active interface found for DNS change")
            return False
        except Exception as e:
            logger.warning("SystemProxy DNS: %s", e)
            return False


# ═══ Singleton ═══

_smart_dns: Optional[SmartDNSServer] = None
_sdns_lock = threading.Lock()


def get_smart_dns(port: int = DNS_ALT_PORT) -> SmartDNSServer:
    global _smart_dns
    if _smart_dns is None:
        with _sdns_lock:
            if _smart_dns is None:
                _smart_dns = SmartDNSServer(port=port)
    return _smart_dns
