"""智能创作助手 - 统一调度器"""

from typing import List, Dict
from .assistant import (
    IntelligentWritingAssistant,
    ContentType, WritingStyle,
    WritingContext, WritingSuggestion, ContentAnalysis,
    create_writing_assistant
)


class CreativeAssistantSystem:
    """创作辅助系统"""
    
    def __init__(self):
        self.assistant = create_writing_assistant()
        self.drafts = {}
    
    def analyze(self, content: str, domain: str = "") -> ContentAnalysis:
        ctx = WritingContext(domain=domain)
        return self.assistant.analyze_content(content, ctx)
    
    def suggest(self, content: str, domain: str = "") -> List[WritingSuggestion]:
        ctx = WritingContext(domain=domain)
        return self.assistant.suggest_completion(content, ctx)
    
    def improve(self, content: str, domain: str = "") -> str:
        ctx = WritingContext(domain=domain)
        return self.assistant.improve_content(content, ctx)
    
    def summarize(self, content: str, max_length: int = 200) -> str:
        return self.assistant.summarize_content(content, max_length)
    
    def generate(self, template: str, params: Dict) -> str:
        return self.assistant.generate_from_template(template, params)
    
    def get_templates(self) -> List[str]:
        return list(self.assistant.templates.keys())


def create_creative_assistant_system() -> CreativeAssistantSystem:
    return CreativeAssistantSystem()
