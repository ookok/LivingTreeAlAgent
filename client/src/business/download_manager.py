"""
Download Manager — Compatibility Stub
"""

class DownloadManager:
    def __init__(self):
        self._downloads = []

    def download(self, url: str, dest: str = "") -> str:
        return dest or url.split("/")[-1]

    @property
    def active_count(self) -> int:
        return 0


__all__ = ["DownloadManager"]
