
from business.plugin_system import BasePlugin

class TestPlugin(BasePlugin):
    def activate(self):
        pass
    def deactivate(self):
        pass
    def get_extensions(self):
        return {
            "llm_provider_test": lambda: {"provider": "test"}
        }
