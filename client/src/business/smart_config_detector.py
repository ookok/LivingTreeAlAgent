"""
智能配置检测器 - 检测聊天消息中涉及的需要配置的功能
"""

from typing import List, Dict, Any


class SmartConfigDetector:
    """智能配置检测器"""
    
    def __init__(self):
        self._config_triggers = {
            "openai": {
                "name": "OpenAI API",
                "triggers": ["openai", "gpt", "chatgpt", "api key", "api_key"],
                "description": "使用OpenAI模型需要配置API密钥"
            },
            "ollama": {
                "name": "Ollama",
                "triggers": ["ollama", "local model", "本地模型"],
                "description": "使用本地Ollama模型需要配置服务地址"
            },
            "browser": {
                "name": "浏览器自动化",
                "triggers": ["浏览器", "网页", "web", "chrome", "浏览", "访问"],
                "description": "浏览器自动化功能需要配置浏览器路径"
            },
            "wecom": {
                "name": "企业微信",
                "triggers": ["企业微信", "wecom", "工作微信"],
                "description": "企业微信功能需要配置API密钥"
            },
            "wechat": {
                "name": "微信",
                "triggers": ["微信", "wechat", "朋友圈"],
                "description": "微信功能需要配置本地数据库路径"
            },
            "mcp": {
                "name": "MCP工具",
                "triggers": ["mcp", "tool", "plugin", "工具调用"],
                "description": "MCP工具需要配置服务器地址"
            },
            "search": {
                "name": "智能搜索",
                "triggers": ["搜索", "web search", "联网", "查询"],
                "description": "智能搜索功能需要配置搜索引擎"
            },
            "github": {
                "name": "GitHub",
                "triggers": ["github", "仓库", "代码", "repo"],
                "description": "GitHub功能需要配置访问令牌"
            }
        }
    
    async def detect_config_needs(self, message: str, context: Dict[str, Any] = None) -> List[Dict[str, str]]:
        """检测消息中涉及的需要配置的功能"""
        detected = []
        message_lower = message.lower()
        
        for config_key, config_info in self._config_triggers.items():
            for trigger in config_info["triggers"]:
                if trigger.lower() in message_lower:
                    detected.append({
                        "key": config_key,
                        "name": config_info["name"],
                        "description": config_info["description"],
                        "trigger": trigger
                    })
                    break
        
        return detected
    
    def get_config_info(self, config_key: str) -> Dict[str, str]:
        """获取配置项信息"""
        return self._config_triggers.get(config_key, {})
    
    def get_all_config_types(self) -> List[str]:
        """获取所有配置类型"""
        return list(self._config_triggers.keys())


def get_config_detector() -> SmartConfigDetector:
    """获取配置检测器单例"""
    if not hasattr(get_config_detector, '_instance'):
        get_config_detector._instance = SmartConfigDetector()
    return get_config_detector._instance