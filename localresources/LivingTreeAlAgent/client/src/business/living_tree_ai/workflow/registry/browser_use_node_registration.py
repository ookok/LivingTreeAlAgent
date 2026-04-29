"""
browser-use 节点注册

注册 browser-use 节点到节点注册表
"""

from .node_registry import NodeRegistry, NodeDefinition


def register_browser_use_nodes(registry: NodeRegistry):
    """
    注册 browser-use 节点到节点注册表
    
    Args:
        registry: 节点注册表实例
    """
    # 浏览器自动化节点
    browser_use_node = NodeDefinition(
        node_type="browser_use",
        name="浏览器自动化",
        description="使用 browser-use 执行浏览器自动化任务",
        category="浏览器",
        icon="🌐",
        inputs=[
            {
                "port_id": "input",
                "name": "输入",
                "type": "string"
            }
        ],
        outputs=[
            {
                "port_id": "output",
                "name": "输出",
                "type": "string"
            }
        ],
        config_schema={
            "task_type": {
                "type": "string",
                "title": "任务类型",
                "enum": ["execute", "navigate", "extract_content", "fill_form", "search", "screenshot"]
            },
            "task_params": {
                "type": "object",
                "title": "任务参数",
                "properties": {
                    "task": {
                        "type": "string",
                        "title": "任务描述"
                    },
                    "url": {
                        "type": "string",
                        "title": "目标 URL"
                    },
                    "selector": {
                        "type": "string",
                        "title": "CSS 选择器"
                    },
                    "form_data": {
                        "type": "object",
                        "title": "表单数据"
                    },
                    "query": {
                        "type": "string",
                        "title": "搜索查询"
                    },
                    "engine": {
                        "type": "string",
                        "title": "搜索引擎",
                        "default": "google"
                    },
                    "path": {
                        "type": "string",
                        "title": "保存路径"
                    }
                }
            },
            "result_variable": {
                "type": "string",
                "title": "结果变量名",
                "default": "browser_result"
            },
            "browser_config": {
                "type": "object",
                "title": "浏览器配置",
                "properties": {
                    "use_cloud": {
                        "type": "boolean",
                        "title": "使用云浏览器",
                        "default": false
                    },
                    "kachilu": {
                        "type": "object",
                        "title": "Kachilu 配置",
                        "properties": {
                            "anti_detection": {
                                "type": "boolean",
                                "title": "启用反检测",
                                "default": true
                            },
                            "captcha_bypass": {
                                "type": "boolean",
                                "title": "启用验证码绕过",
                                "default": true
                            },
                            "human_simulation": {
                                "type": "boolean",
                                "title": "启用人类行为模拟",
                                "default": true
                            }
                        }
                    }
                }
            }
        },
        default_config={
            "task_type": "execute",
            "task_params": {
                "task": ""
            },
            "result_variable": "browser_result",
            "browser_config": {
                "use_cloud": false,
                "kachilu": {
                    "anti_detection": true,
                    "captcha_bypass": true,
                    "human_simulation": true
                }
            }
        }
    )
    
    # 注册节点
    registry.register(browser_use_node)


def get_browser_use_nodes() -> list[NodeDefinition]:
    """
    获取 browser-use 节点定义
    
    Returns:
        list[NodeDefinition]: 节点定义列表
    """
    from .node_registry import NodeRegistry
    registry = NodeRegistry()
    return [node for node in registry.get_all() if node.node_type == "browser_use"]
