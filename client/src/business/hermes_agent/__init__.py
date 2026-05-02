"""
Hermes Agent - 智能编排中枢 (向后兼容层)

⚠️ 已迁移至 livingtree.core.agent.hermes
本模块保留为兼容层。
"""

def __getattr__(name):
    if name == 'IntentRecognizer':
        from livingtree.core.agent.hermes.intent_recognizer import IntentRecognizer
        return IntentRecognizer
    raise AttributeError(f"module 'client.src.business.hermes_agent' has no attribute '{name}'")

__all__ = ['IntentRecognizer']
