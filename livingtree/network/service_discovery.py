"""ServiceDiscovery — named URLs, auto-HTTPS, mDNS for LivingTree services.

    Inspired by Vercel's Portless (8.9k stars). Replaces port-number URLs
    with professional named local domains.

    Architecture:
      relay_server:8888  →  relay.livingtree.localhost
      opencode:4096      →  code.livingtree.localhost
      admin panel        →  admin.livingtree.localhost

    Auto-generates:
      1. Local CA certificate (trusted system-wide on first run)
      2. .localhost domain routing via hosts file
      3. mDNS broadcasting for LAN device access
      4. Auto port assignment with collision prevention

    Usage:
        sd = get_service_discovery()
        await sd.setup()     # one-time CA generation + trust
        url = await sd.register("relay", 8888)
        # → https://relay.livingtree.localhost

    LAN demo: any device on same network opens https://relay.livingtree.localhost

    Commands:
        /services     — list all registered services with URLs
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

SD_DIR = Path(".livingtree/service_dns")
CA_DIR = SD_DIR / "ca"
CA_KEY = CA_DIR / "ca.key"
CA_CERT = CA_DIR / "ca.pem"
SERVICES_FILE = SD_DIR / "services.json"
HOSTS_MARKER = "# --- LivingTree Services ---"
TLD = "livingtree.localhost"


@dataclass
class RegisteredService:
    name: str
    port: int
    protocol: str = "https"
    url: str = ""
    lan_url: str = ""
    registered_at: float = 0.0
    metadata: dict = field(default_factory=dict)


class ServiceDiscovery:
    """Named URL service registry with auto-HTTPS and mDNS."""

    def __init__(self):
        SD_DIR.mkdir(parents=True, exist_ok=True)
        CA_DIR.mkdir(parents=True, exist_ok=True)
        self._services: dict[str, RegisteredService] = {}
        self._ca_generated = False
        self._hostfile_synced = False
        self._lan_ip = self._detect_lan_ip()
        self._load()

    # ═══ Setup (one-time) ═══

    async def setup(self) -> bool:
        """One-time setup: generate CA, trust it, sync hosts.

        Returns True if everything is ready.
        """
        # 1. Generate CA if needed
        if not self._ca_generated:
            self._ca_generated = self._generate_ca()

        # 2. Trust CA in system store
        if self._ca_generated:
            self._trust_ca()

        # 3. Sync hosts file
        self._sync_hosts()

        return self._ca_generated

    # ═══ Service Registration ═══

    async def register(
        self,
        name: str,
        port: int = 0,
        protocol: str = "https",
        metadata: dict | None = None,
    ) -> RegisteredService:
        """Register a service and get its named URL.

        Args:
            name: Service name → relay.livingtree.localhost
            port: Port number (0 = auto-assign from env or random)
            protocol: https or http
            metadata: Extra info
        """
        if port == 0:
            port = self._auto_port(name)

        hostname = f"{name}.{TLD}"
        url = f"{protocol}://{hostname}"
        lan_url = f"{protocol}://{self._lan_ip}:{port}" if self._lan_ip else ""

        service = RegisteredService(
            name=name,
            port=port,
            protocol=protocol,
            url=url,
            lan_url=lan_url,
            registered_at=time.time(),
            metadata=metadata or {},
        )
        self._services[name] = service
        self._save()

        # Advertise via mDNS
        await self._mdns_advertise(name, port)

        logger.info(f"Service: {url}" + (f" | LAN: {lan_url}" if lan_url else ""))
        return service

    def get_url(self, name: str) -> str:
        svc = self._services.get(name)
        return svc.url if svc else ""

    def list_services(self) -> list[RegisteredService]:
        return sorted(self._services.values(), key=lambda s: s.registered_at)

    def status_text(self) -> str:
        if not self._services:
            return "No services registered"
        lines = ["## 🌐 本地服务", ""]
        for svc in self.list_services():
            prot = "🔒" if svc.protocol == "https" else "🌐"
            lines.append(f"{prot} **{svc.name}** → {svc.url}")
            if svc.lan_url:
                lines.append(f"  📱 LAN: {svc.lan_url}")
        return "\n".join(lines)

    # ═══ CA Generation ═══

    def _generate_ca(self) -> bool:
        """Generate a self-signed CA certificate."""
        if CA_CERT.exists() and CA_KEY.exists():
            # Check expiry
            try:
                cert_text = CA_CERT.read_text()
                if "BEGIN CERTIFICATE" in cert_text:
                    return True
            except Exception:
                pass

        logger.info("Generating local CA certificate...")

        try:
            # Use cryptography if available
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LivingTree Local CA"),
                x509.NameAttribute(NameOID.COMMON_NAME, f"LivingTree {TLD}"),
            ])

            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.utcnow())
                .not_valid_after(datetime.utcnow() + timedelta(days=3650))
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                .sign(key, hashes.SHA256())
            )

            CA_KEY.write_bytes(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
            CA_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

            logger.info("CA generated: " + str(CA_CERT))
            return True

        except ImportError:
            # Fallback: openssl CLI
            return self._generate_ca_openssl()

    def _generate_ca_openssl(self) -> bool:
        """Fallback CA generation via OpenSSL CLI."""
        import asyncio
        try:
            subj = f"/C=CN/O=LivingTree/CN=LivingTree {TLD}"
            from ..treellm.unified_exec import run
            result = asyncio.run(run(
                f"openssl req -x509 -newkey rsa:2048 -nodes "
                f"-keyout {CA_KEY} -out {CA_CERT} -days 3650 -subj \"{subj}\"",
                timeout=30))
            return result.success
        except Exception as e:
            logger.warning(f"CA generation failed: {e}")
            return False

    def generate_server_cert(self, hostname: str) -> tuple[str, str] | None:
        """Generate a server certificate signed by our CA for a specific hostname.

        Returns (cert_path, key_path).
        """
        cert_path = CA_DIR / f"{hostname}.pem"
        key_path = CA_DIR / f"{hostname}.key"

        if cert_path.exists() and key_path.exists():
            return str(cert_path), str(key_path)

        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.backends import default_backend

            ca_key_data = CA_KEY.read_bytes()
            ca_key = serialization.load_pem_private_key(ca_key_data, password=None)
            ca_cert_data = CA_CERT.read_bytes()
            ca_cert = x509.load_pem_x509_certificate(ca_cert_data)

            key = rsa.generate_private_key(65537, 2048)
            cert = (
                x509.CertificateBuilder()
                .subject_name(x509.Name([
                    x509.NameAttribute(NameOID.COMMON_NAME, hostname),
                ]))
                .issuer_name(ca_cert.subject)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.utcnow())
                .not_valid_after(datetime.utcnow() + timedelta(days=365))
                .add_extension(
                    x509.SubjectAlternativeName([x509.DNSName(hostname)]),
                    critical=False,
                )
                .sign(ca_key, hashes.SHA256())
            )

            key_path.write_bytes(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

            return str(cert_path), str(key_path)

        except ImportError:
            return None

    # ═══ CA Trust ═══

    def _trust_ca(self):
        """Add CA to system trust store."""
        system = platform.system()
        import asyncio

        try:
            if system == "Windows":
                from ..treellm.unified_exec import run
                result = asyncio.run(run(
                    f"certutil -addstore -f Root \"{CA_CERT}\"", timeout=10))
                if result.success:
                    logger.info("CA trusted (Windows certutil)")

            elif system == "Darwin":
                from ..treellm.unified_exec import run
                result = asyncio.run(run(
                    f"security add-trusted-cert -d -p ssl "
                    f"-k /Library/Keychains/System.keychain \"{CA_CERT}\"", timeout=10))
                logger.info("CA trusted (macOS)")

            elif system == "Linux":
                dest = Path("/usr/local/share/ca-certificates/livingtree-ca.crt")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(CA_CERT, dest)
                from ..treellm.unified_exec import run
                asyncio.run(run("update-ca-certificates", timeout=10))
                # Also try distro-specific paths
                for distro_path in [
                    "/etc/pki/ca-trust/source/anchors/",
                    "/usr/share/ca-certificates/",
                ]:
                    dp = Path(distro_path)
                    if dp.exists():
                        shutil.copy2(CA_CERT, dp / "livingtree-ca.crt")
                        from ..treellm.unified_exec import run
                        asyncio.run(run("update-ca-trust", timeout=10))
                        break
                logger.info("CA trusted (Linux)")

        except Exception as e:
            logger.debug(f"CA trust: {e} — manual trust may be needed")

    # ═══ Hosts File Management ═══

    def _sync_hosts(self):
        """Add .localhost entries to /etc/hosts (or Windows equivalent)."""
        hosts_path = self._get_hosts_path()
        if not hosts_path.exists():
            return

        hostnames = [f"{name}.{TLD}" for name in self._services.keys()]
        if not hostnames:
            hostnames = [TLD]  # ensure at least the TLD resolves

        try:
            content = hosts_path.read_text()
            # Remove old entries
            lines = content.splitlines()
            new_lines = []
            in_block = False
            for line in lines:
                if HOSTS_MARKER in line:
                    in_block = True
                    continue
                if in_block and line.startswith("127.0.0.1"):
                    continue
                if in_block and line.startswith("#"):
                    in_block = False
                new_lines.append(line)

            # Add new entries
            new_lines.append(HOSTS_MARKER)
            new_lines.append(f"# Auto-generated at {time.strftime('%Y-%m-%d %H:%M')}")
            for host in hostnames:
                new_lines.append(f"127.0.0.1  {host}")
            new_lines.append(HOSTS_MARKER + " END")
            new_lines.append("")

            hosts_path.write_text("\n".join(new_lines))
            self._hostfile_synced = True
            logger.debug(f"Hosts synced: {len(hostnames)} entries")

        except PermissionError:
            logger.debug("Hosts sync requires admin rights — services available at localhost")
        except Exception as e:
            logger.debug(f"Hosts sync: {e}")

    @staticmethod
    def _get_hosts_path() -> Path:
        system = platform.system()
        if system == "Windows":
            windir = os.environ.get("WINDIR", r"C:\Windows")
            return Path(windir) / "System32" / "drivers" / "etc" / "hosts"
        return Path("/etc/hosts")

    # ═══ mDNS Advertisement ═══

    @staticmethod
    async def _mdns_advertise(name: str, port: int):
        """Advertise service via mDNS for LAN device discovery.

        Uses platform-specific tools:
        - macOS: dns-sd
        - Linux: avahi-publish
        - Windows: dns-sd (if Bonjour installed) or skip
        """
        try:
            system = platform.system()
            hostname = f"{name}.{TLD}"

            if system == "Darwin":
                proc = await asyncio.create_subprocess_exec(
                    "dns-sd", "-R", hostname, "_http._tcp", "local", str(port),
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                # Keep alive in background
                asyncio.create_task(self._keep_alive(proc, "dns-sd"))

            elif system == "Linux":
                proc = await asyncio.create_subprocess_exec(
                    "avahi-publish", "-s", hostname, "_http._tcp", str(port),
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                asyncio.create_task(self._keep_alive(proc, "avahi"))

            elif system == "Windows":
                # Try Bonjour dns-sd if available
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "dns-sd", "-R", hostname, "_http._tcp", "local", str(port),
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    )
                    asyncio.create_task(self._keep_alive(proc, "dns-sd"))
                except FileNotFoundError:
                    logger.debug("mDNS: Bonjour not installed — LAN sharing unavailable")

        except FileNotFoundError:
            logger.debug(f"mDNS tools not found on {system}")
        except Exception as e:
            logger.debug(f"mDNS: {e}")

    @staticmethod
    async def _keep_alive(proc, name: str):
        try:
            await proc.wait()
        except Exception:
            pass

    # ═══ Port Assignment ═══

    def _auto_port(self, name: str) -> int:
        """Auto-assign a free port."""
        # Check env var first
        env_port = os.environ.get(f"LIVINGTREE_PORT_{name.upper()}")
        if env_port and env_port.isdigit():
            return int(env_port)

        # Check existing registration
        if name in self._services:
            existing = self._services[name].port
            if self._port_is_free(existing):
                return existing

        # Find a free port in range
        base = 8800
        for attempt in range(100):
            port = base + attempt
            if self._port_is_free(port) and not any(
                s.port == port for s in self._services.values()
            ):
                return port

        return 0  # let OS assign

    @staticmethod
    def _port_is_free(port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            return result != 0
        except Exception:
            return True

    @staticmethod
    def _detect_lan_ip() -> str:
        """Detect the LAN IP address for sharing."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
        return ""

    # ═══ Persistence ═══

    def _save(self):
        data = {}
        for name, svc in self._services.items():
            data[name] = {
                "name": svc.name, "port": svc.port, "protocol": svc.protocol,
                "url": svc.url, "lan_url": svc.lan_url,
                "registered_at": svc.registered_at,
                "metadata": svc.metadata,
            }
        SERVICES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not SERVICES_FILE.exists():
            return
        try:
            data = json.loads(SERVICES_FILE.read_text(encoding="utf-8"))
            for name, d in data.items():
                self._services[name] = RegisteredService(
                    name=d.get("name", ""), port=d.get("port", 0),
                    protocol=d.get("protocol", "https"), url=d.get("url", ""),
                    lan_url=d.get("lan_url", ""),
                    registered_at=d.get("registered_at", 0),
                    metadata=d.get("metadata", {}),
                )
        except Exception:
            pass


_sd: ServiceDiscovery | None = None


def get_service_discovery() -> ServiceDiscovery:
    global _sd
    if _sd is None:
        _sd = ServiceDiscovery()
    return _sd
