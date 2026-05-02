"""
Report Generator — Compatibility Stub
"""

from dataclasses import dataclass


@dataclass
class Report:
    title: str = ""
    content: str = ""
    format: str = "markdown"


class ReportGenerator:
    def __init__(self, model: str = ""):
        self.model = model

    def generate(self, topic: str, template: str = "") -> Report:
        return Report(title=topic, content=f"[Generated report for: {topic}]")


__all__ = ["ReportGenerator", "Report"]
