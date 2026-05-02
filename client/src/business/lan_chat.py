"""
LAN Chat — Compatibility Stub
"""

class LANChat:
    def __init__(self, port: int = 9999):
        self.port = port

    def broadcast(self, message: str):
        pass

    def listen(self):
        pass


__all__ = ["LANChat"]
