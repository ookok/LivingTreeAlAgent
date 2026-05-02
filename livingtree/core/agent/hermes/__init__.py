"""
Hermes Agent - 智能编排中枢

⚠️ hermes_agent 子模块有大量未迁移依赖。
仅核心 IntentRecognizer 可通过 livingtree 路径导入。
"""

def __getattr__(name):
    if name == 'IntentRecognizer':
        from livingtree.core.agent.hermes.intent_recognizer import IntentRecognizer
        return IntentRecognizer
    raise AttributeError(f"module 'livingtree.core.agent.hermes' has no attribute '{name}'")

__all__ = ['IntentRecognizer']
