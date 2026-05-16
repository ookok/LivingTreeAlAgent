"""DPI Bypass v2 — ClientHello fragmentation at TCP level.

Based on: zapret/GoodbyeDPI (tcp_segmentation technique)
Pure Python, no driver needed. Works because scinet IS the proxy.

Principle:
  Browser → scinet (127.0.0.1:7890) → GitHub
  scinet receives complete ClientHello from browser
  scinet splits it into N fragments (each < 50 bytes) when sending to GitHub
  GFW's DPI sees small fragments → can't read full SNI → doesn't block
  
  GitHub's TCP stack reassembles normally → TLS works
"""

import asyncio
import time
from loguru import logger

SNI_FRAGMENT_SIZE = 40  # bytes per fragment
SNI_FRAGMENT_DELAY = 0.01  # seconds between fragments


class FragmentedStreamWriter:
    """Wraps asyncio.StreamWriter to fragment writes for DPI evasion.

    Automatically splits any write into small chunks with delays.
    The first 200 bytes (ClientHello header) are most critical.
    """

    def __init__(self, writer: asyncio.StreamWriter):
        self._w = writer

    async def write(self, data: bytes):
        """Write data in fragments to avoid DPI detection."""
        if len(data) <= SNI_FRAGMENT_SIZE:
            self._w.write(data)
            await self._w.drain()
            return

        total = len(data)
        offset = 0
        
        # First byte: send alone (triggers DPI to start buffering)
        self._w.write(data[0:1])
        await self._w.drain()
        await asyncio.sleep(SNI_FRAGMENT_DELAY)
        offset = 1

        # Fragment the rest into small chunks
        while offset < total:
            size = min(SNI_FRAGMENT_SIZE, total - offset)
            # Occasionally send a single byte to really confuse DPI
            if size > 1 and offset % 3 == 0:
                self._w.write(data[offset:offset + 1])
                await self._w.drain()
                await asyncio.sleep(SNI_FRAGMENT_DELAY)
                offset += 1
                continue
            
            self._w.write(data[offset:offset + size])
            await self._w.drain()
            await asyncio.sleep(SNI_FRAGMENT_DELAY)
            offset += size

        logger.debug("DPI frag: %d bytes → %d fragments", total,
                     max(1, total // SNI_FRAGMENT_SIZE + 1))

    async def drain(self):
        return await self._w.drain()

    def close(self):
        self._w.close()
        return self._w.wait_closed()

    def get_extra_info(self, name, default=None):
        return self._w.get_extra_info(name, default)

    def __getattr__(self, name):
        return getattr(self._w, name)


async def dpi_fragmented_connect(host: str, port: int, timeout: float = 8.0) -> tuple | None:
    """Connect to host:port with ClientHello fragmentation.
    
    Opens a TCP connection, then returns a FragmentedStreamWriter
    that automatically splits all writes into tiny chunks.
    
    The CONNECT tunnel replaces the remote_writer with this,
    so the browser's ClientHello gets fragmented automatically.
    """
    import asyncio as _aio
    
    try:
        r, w = await _aio.wait_for(
            _aio.open_connection(host, port), timeout=timeout,
        )
        # Wrap writer for DPI fragmentation
        return r, FragmentedStreamWriter(w)
    except Exception:
        return None, None


# ═══ Relay fragmenter — wraps existing tunnel ═══

def wrap_fragmented(writer: asyncio.StreamWriter) -> FragmentedStreamWriter:
    """Wrap an existing StreamWriter for DPI-fragmented writes."""
    return FragmentedStreamWriter(writer)
