"""
Relay Client — Compatibility Stub
"""

class RelayClient:
    def __init__(self, server_url: str = "", api_key: str = ""):
        self.server_url = server_url
        self.api_key = api_key

    def send(self, data: dict) -> dict:
        return {"success": True}

    def receive(self) -> dict:
        return {}


__all__ = ["RelayClient"]
