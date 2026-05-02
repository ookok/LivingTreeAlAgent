"""
Remote API Client — Compatibility Stub
"""


class RemoteAPIClient:
    def __init__(self, base_url: str = ""):
        self.base_url = base_url

    def call(self, endpoint: str, data: dict = None) -> dict:
        return {"success": True}

    def get(self, endpoint: str) -> dict:
        return {}


__all__ = ["RemoteAPIClient"]
