"""
Relay Server — Compatibility Stub
"""

class RelayServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8888):
        self.host = host
        self.port = port

    def start(self):
        pass

    def stop(self):
        pass


__all__ = ["RelayServer"]
