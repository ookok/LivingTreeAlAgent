"""
API Gateway — Compatibility Stub

Functionality migrated to livingtree.adapters.api.gateway.
"""


class APIGateway:
    def __init__(self):
        self._handlers = {}

    def route(self, path: str, data: dict = None) -> dict:
        return {"path": path, "success": True}


__all__ = ["APIGateway"]
