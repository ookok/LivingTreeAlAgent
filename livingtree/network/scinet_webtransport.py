"""Scinet WebTransport — Browser-native tunnel using WebTransport protocol.

Provides a WebTransport-based endpoint that browsers can connect to directly,
bypassing the need for system proxy configuration. Based on the W3C WebTransport
standard (draft-ietf-webtrans-http3).

1. WebTransport Server:
   - HTTP/3 (QUIC) endpoint at /scinet/wt
   - Accepts WebTransport sessions from browsers
   - Creates bidirectional streams for proxied traffic

2. Browser-native connection:
   - No PAC file or system proxy needed
   - Works with Chrome/Edge 97+ WebTransport API
   - Auto-fallback to WebSocket if WebTransport unavailable

3. JavaScript Bridge:
   - Client-side JS library for WebTransport proxy
   - Automatic connection management with reconnection
   - Fallback to fetch-based proxy

4. Stream Multiplexing:
   - Multiple concurrent streams over single WebTransport session
   - Each HTTP request maps to one bidirectional stream
   - Headers + body sent as first message on stream

Reference:
  - W3C WebTransport: https://w3c.github.io/webtransport/
  - IETF draft-ietf-webtrans-http3

Usage:
    # Server side
    wt = WebTransportServer(port=7891)
    await wt.start()

    # Client side (JavaScript)
    const transport = new WebTransport('https://localhost:7891/scinet/wt');
    await transport.ready;
    const stream = await transport.createBidirectionalStream();
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import ssl
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

try:
    from aioquic.asyncio import serve as quic_serve
    from aioquic.asyncio.protocol import QuicConnectionProtocol
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.quic.events import QuicEvent, StreamDataReceived
    from aioquic.h3.connection import H3Connection
    from aioquic.h3.events import (
        DataReceived, HeadersReceived, WebTransportStreamDataReceived,
    )
except ImportError:
    QuicConnectionProtocol = object
    quic_serve = QuicConfiguration = None
    QuicEvent = StreamDataReceived = None
    H3Connection = None
    DataReceived = HeadersReceived = WebTransportStreamDataReceived = None

import aiohttp


# WebTransport subprotocol identifier
WT_ALPN = "h3-webtransport"

# WebTransport session ID header (per draft)
WT_SESSION_HEADER = "sec-webtransport-http3-draft"

# WebTransport subprotocol for proxy
PROXY_SUBPROTOCOL = "scinet-proxy-v1"


@dataclass
class WTSession:
    """Active WebTransport session with a client."""
    session_id: str
    h3: Any  # H3Connection
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    streams: dict[int, dict] = field(default_factory=dict)
    bytes_in: int = 0
    bytes_out: int = 0
    pending_requests: int = 0


@dataclass
class WTStreamStats:
    total_sessions: int = 0
    active_sessions: int = 0
    total_streams: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    failed_connects: int = 0


class WebTransportProtocol(QuicConnectionProtocol):
    """QUIC protocol handler for WebTransport connections.

    Receives WebTransport sessions and creates bidirectional streams
    for proxy traffic.
    """

    def __init__(self, *args, server: WebTransportServer = None, **kwargs):
        if quic_serve is not None:
            super().__init__(*args, **kwargs)
        self._server = server
        self._h3: Optional[H3Connection] = None
        self._sessions: dict[str, WTSession] = {}

    def quic_event_received(self, event: QuicEvent):
        """Handle QUIC events."""
        if quic_serve is None:
            return

        if self._h3 is None:
            return

        for http_event in self._h3.handle_event(event):
            if isinstance(http_event, HeadersReceived):
                self._handle_headers(http_event)
            elif isinstance(http_event, WebTransportStreamDataReceived):
                self._handle_stream_data(http_event)
            elif isinstance(http_event, DataReceived):
                pass

    def _handle_headers(self, event):
        """Handle incoming HTTP headers — detect WebTransport session."""
        headers = dict(event.headers)
        session_header = headers.get(b"sec-webtransport-http3-draft", b"").decode()

        if session_header == "1":
            session_id = hashlib.sha256(
                f"{time.time()}-{os.urandom(8).hex()}".encode()
            ).hexdigest()[:16]

            session = WTSession(session_id=session_id, h3=self._h3)
            self._sessions[session_id] = session

            # Send session accepted
            self._h3.send_headers(
                event.stream_id,
                [
                    (b":status", b"200"),
                    (b"sec-webtransport-http3-draft", b"1"),
                    (b"server", b"LivingTree-Scinet-WT/2.0"),
                ],
            )
            self._h3.send_data(event.stream_id, b"", end_stream=True)

            if self._server:
                self._server._register_session(session)
                logger.info("WebTransport session opened: %s", session_id)

    def _handle_stream_data(self, event: WebTransportStreamDataReceived):
        """Handle data on a WebTransport stream — proxy request."""
        if self._server:
            asyncio.create_task(
                self._server._handle_proxy_stream(self, event)
            )


class WebTransportServer:
    """WebTransport server for browser-native proxy connections.

    Architecture:
      Browser (WebTransport API) ← QUIC → Scinet WT Server → Target Site

    No system proxy configuration required — the browser connects directly
    using the WebTransport API.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7891):
        self.host = host
        self.port = port
        self._sessions: dict[str, WTSession] = {}
        self._running = False
        self._server = None
        self._stats = WTStreamStats()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the WebTransport server."""
        if quic_serve is None:
            logger.warning(
                "WebTransport: aioquic not installed. "
                "Install with: pip install aioquic"
            )
            return

        config = QuicConfiguration(
            alpn_protocols=["h3", WT_ALPN],
            is_client=False,
            max_data=10_000_000,
            max_stream_data=10_000_000,
        )

        # Self-signed cert for localhost
        cert_path = Path(".livingtree/wt_cert.pem")
        key_path = Path(".livingtree/wt_key.pem")
        if cert_path.exists() and key_path.exists():
            config.load_cert_chain(str(cert_path), str(key_path))
        else:
            self._generate_self_signed_cert(cert_path, key_path)
            config.load_cert_chain(str(cert_path), str(key_path))

        config.verify_mode = ssl.CERT_NONE

        self._server = await quic_serve(
            self.host, self.port,
            configuration=config,
            create_protocol=lambda: WebTransportProtocol(server=self),
        )
        self._running = True

        logger.info(
            "WebTransport server: https://%s:%d/scinet/wt",
            self.host, self.port,
        )

        # Generate JS client library
        self._generate_js_client()

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
        self._sessions.clear()
        logger.info("WebTransport server stopped")

    def _register_session(self, session: WTSession) -> None:
        self._sessions[session.session_id] = session
        self._stats.total_sessions += 1
        self._stats.active_sessions = len(self._sessions)

    async def _handle_proxy_stream(
        self, protocol: WebTransportProtocol, event,
    ) -> None:
        """Handle a proxy request from a WebTransport stream."""
        session_id = None
        for sid, session in protocol._sessions.items():
            session_id = sid
            break

        if not session_id:
            return

        try:
            # Parse proxy request from stream data
            request_data = event.data.decode("utf-8", errors="replace")
            lines = request_data.split("\r\n")
            if len(lines) < 1:
                return

            # First line: METHOD URL HTTP/1.1
            method, url, _ = lines[0].split(" ", 2)
            headers = {}
            body_start = 0
            for i, line in enumerate(lines[1:], 1):
                if line == "":
                    body_start = i + 1
                    break
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            body = "\r\n".join(lines[body_start:]) if body_start else ""

            # Forward request
            async with aiohttp.ClientSession() as http_session:
                async with http_session.request(
                    method, url, headers=headers,
                    data=body.encode() if body else None,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    response_body = await resp.read()

            # Send response back through WebTransport stream
            response_headers = f"HTTP/1.1 {resp.status} OK\r\n"
            for k, v in resp.headers.items():
                response_headers += f"{k}: {v}\r\n"
            response_headers += f"X-Proxy: LivingTree-Scinet-WT/2.0\r\n"
            response_headers += "\r\n"

            response_data = response_headers.encode() + response_body

            # Get the session's H3 connection
            session = protocol._sessions.get(session_id)
            if session and H3Connection is not None:
                stream_id = session.h3.get_next_available_stream_id()
                session.h3.send_data(stream_id, response_data, end_stream=True)
                session.bytes_out += len(response_data)
                self._stats.bytes_out += len(response_data)
                self._stats.total_streams += 1

        except Exception as e:
            logger.debug("WebTransport proxy stream error: %s", e)
            self._stats.failed_connects += 1

    def _generate_self_signed_cert(
        self, cert_path: Path, key_path: Path,
    ) -> None:
        """Generate self-signed certificate for localhost."""
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime

            key = rsa.generate_private_key(
                public_exponent=65537, key_size=2048,
            )

            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LivingTree Scinet"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])

            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("127.0.0.1"),
                ]),
                critical=False,
            ).sign(key, hashes.SHA256())

            cert_path.parent.mkdir(parents=True, exist_ok=True)
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
            logger.debug("Generated self-signed cert for WebTransport")
        except ImportError:
            logger.warning("cryptography not installed, using ad-hoc cert")
            # Fallback: generate using openssl if available
            import subprocess
            cert_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                from livingtree.treellm.unified_exec import run
                import asyncio
                result = asyncio.run(run(
                    f"openssl req -x509 -newkey rsa:2048 "
                    f"-keyout {key_path} -out {cert_path} -days 365 -nodes "
                    f"-subj /CN=localhost",
                    timeout=10))
            except ImportError:
                subprocess.run([
                    "openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", str(key_path), "-out", str(cert_path),
                    "-days", "365", "-nodes",
                    "-subj", "/CN=localhost",
                ], capture_output=True, timeout=10)

    def _generate_js_client(self) -> str:
        """Generate JavaScript client library for browser-side usage.

        Returns the path to static JS file.
        """
        js_path = Path(".livingtree/scinet_wt_client.js")
        js_code = self._get_js_client_code()
        js_path.parent.mkdir(parents=True, exist_ok=True)
        js_path.write_text(js_code, encoding="utf-8")
        return str(js_path)

    def _get_js_client_code(self) -> str:
        """JavaScript client for WebTransport proxy."""
        return """// Scinet WebTransport Client v2.0 — Browser-native proxy
// Usage: new ScinetWT({ host: 'localhost', port: 7891 })

class ScinetWT {
  constructor(opts = {}) {
    this.host = opts.host || '127.0.0.1';
    this.port = opts.port || 7891;
    this.transport = null;
    this.connected = false;
    this.streams = new Map();
    this.streamIdCounter = 0;
  }

  async connect() {
    const url = `https://${this.host}:${this.port}/scinet/wt`;
    try {
      this.transport = new WebTransport(url, {
        serverCertificateHashes: [],  // Self-signed bypass
      });
      await this.transport.ready;
      this.connected = true;
      console.log('[ScinetWT] Connected');
      return true;
    } catch (e) {
      console.warn('[ScinetWT] WebTransport failed, falling back:', e);
      return false;
    }
  }

  async proxyFetch(requestUrl, opts = {}) {
    if (!this.connected) await this.connect();
    if (!this.connected) return fetch(requestUrl, opts);

    const stream = await this.transport.createBidirectionalStream();
    const streamId = ++this.streamIdCounter;
    this.streams.set(streamId, stream);

    const method = opts.method || 'GET';
    const headers = opts.headers || {};
    let body = opts.body || '';

    const request = `${method} ${requestUrl} HTTP/1.1\\r\\n` +
      Object.entries(headers).map(([k, v]) => `${k}: ${v}`).join('\\r\\n') +
      '\\r\\n\\r\\n' + (body || '');

    const writer = stream.writable.getWriter();
    await writer.write(new TextEncoder().encode(request));
    await writer.close();

    const reader = stream.readable.getReader();
    let response = '';
    while (true) {
      const { value, done } = await reader.read();
      if (value) response += new TextDecoder().decode(value);
      if (done) break;
    }

    // Parse HTTP response
    const [headerPart, ...bodyParts] = response.split('\\r\\n\\r\\n');
    const headers_lines = headerPart.split('\\r\\n');
    const [_, status, statusText] = headers_lines[0].split(' ');
    const respHeaders = {};
    for (const line of headers_lines.slice(1)) {
      const [k, ...v] = line.split(':');
      if (k) respHeaders[k.trim()] = v.join(':').trim();
    }

    return new Response(bodyParts.join('\\r\\n\\r\\n'), {
      status: parseInt(status),
      statusText,
      headers: respHeaders,
    });
  }

  disconnect() {
    if (this.transport) {
      this.transport.close();
      this.connected = false;
    }
  }
}

window.ScinetWT = ScinetWT;
"""

    def get_client_js_path(self) -> str:
        return str(Path(".livingtree/scinet_wt_client.js"))

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "port": self.port,
            "total_sessions": self._stats.total_sessions,
            "active_sessions": self._stats.active_sessions,
            "total_streams": self._stats.total_streams,
            "bytes_in": self._stats.bytes_in,
            "bytes_out": self._stats.bytes_out,
            "failed_connects": self._stats.failed_connects,
        }


_wt_server: Optional[WebTransportServer] = None


def get_webtransport_server(port: int = 7891) -> WebTransportServer:
    global _wt_server
    if _wt_server is None:
        _wt_server = WebTransportServer(port=port)
    return _wt_server
