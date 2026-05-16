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

SNI_FRAGMENT_SIZE = 40
SNI_FRAGMENT_DELAY = 0.0   # no delay — instant fragmentation


class FragmentedStreamWriter:
    """Wraps asyncio.StreamWriter to fragment writes for DPI evasion.

    Splits each write into 40-byte chunks immediately with no delay.
    TCP_NODELAY ensures OS sends each chunk as a separate TCP segment.
    GFW's DPI sees fragmented segments → can't read full SNI → doesn't block.
    """

    def __init__(self, writer: asyncio.StreamWriter):
        self._w = writer

    async def write(self, data: bytes):
        chunk = SNI_FRAGMENT_SIZE
        for i in range(0, len(data), chunk):
            self._w.write(data[i:i + chunk])

    async def drain(self):
        await self._w.drain()


def wrap_fragmented(writer: asyncio.StreamWriter) -> FragmentedStreamWriter:
    """Wrap an existing StreamWriter for DPI-fragmented writes."""
    return FragmentedStreamWriter(writer)
