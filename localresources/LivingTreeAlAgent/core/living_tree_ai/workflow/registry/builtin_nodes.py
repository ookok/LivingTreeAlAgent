"""内置节点定义"""

from .node_registry import NodeRegistry, NodeDefinition


def register_builtin_nodes():
    """注册内置节点"""
    registry = NodeRegistry()
    
    # Start 节点
    registry.register(NodeDefinition(
        node_type="start",
        name="开始",
        description="工作流开始节点，定义输入变量",
        category="control",
        icon="▶",
        inputs=[],
        outputs=[
            {"name": "output", "type": "any", "description": "开始输出"}
        ],
        config_schema={},
        default_config={}
    ))
    
    # End 节点
    registry.register(NodeDefinition(
        node_type="end",
        name="结束",
        description="工作流结束节点，定义输出结果",
        category="control",
        icon="■",
        inputs=[
            {"name": "input", "type": "any", "description": "结束输入"}
        ],
        outputs=[],
        config_schema={},
        default_config={}
    ))
    
    # LLM 节点
    registry.register(NodeDefinition(
        node_type="llm",
        name="大语言模型",
        description="调用大语言模型进行推理",
        category="ai",
        icon="🤖",
        inputs=[
            {"name": "prompt", "type": "string", "description": "提示词"},
            {"name": "context", "type": "any", "description": "上下文"}
        ],
        outputs=[
            {"name": "response", "type": "string", "description": "模型响应"}
        ],
        config_schema={
            "model": {"type": "string", "required": True},
            "temperature": {"type": "number", "default": 0.7},
            "max_tokens": {"type": "number", "default": 2000}
        },
        default_config={
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    ))
    
    # Tool 节点
    registry.register(NodeDefinition(
        node_type="tool",
        name="工具",
        description="调用工具执行特定功能",
        category="tool",
        icon="🔧",
        inputs=[
            {"name": "input", "type": "any", "description": "工具输入"}
        ],
        outputs=[
            {"name": "result", "type": "any", "description": "工具结果"}
        ],
        config_schema={
            "tool_name": {"type": "string", "required": True}
        },
        default_config={
            "tool_name": "read_file"
        }
    ))
    
    # Knowledge 节点
    registry.register(NodeDefinition(
        node_type="knowledge",
        name="知识库",
        description="从知识库检索相关信息",
        category="knowledge",
        icon="📚",
        inputs=[
            {"name": "query", "type": "string", "description": "查询内容"}
        ],
        outputs=[
            {"name": "documents", "type": "array", "description": "检索文档"},
            {"name": "context", "type": "string", "description": "上下文"}
        ],
        config_schema={
            "knowledge_base": {"type": "string", "required": True},
            "top_k": {"type": "number", "default": 5}
        },
        default_config={
            "knowledge_base": "default",
            "top_k": 5
        }
    ))
    
    # Condition 节点
    registry.register(NodeDefinition(
        node_type="condition",
        name="条件分支",
        description="根据条件选择执行分支",
        category="control",
        icon="🔀",
        inputs=[
            {"name": "condition", "type": "boolean", "description": "条件"}
        ],
        outputs=[
            {"name": "true_branch", "type": "any", "description": "条件为真"},
            {"name": "false_branch", "type": "any", "description": "条件为假"}
        ],
        config_schema={
            "expression": {"type": "string", "required": True}
        },
        default_config={
            "expression": "{{input}} == true"
        }
    ))
    
    # Loop 节点
    registry.register(NodeDefinition(
        node_type="loop",
        name="循环",
        description="循环执行节点内容",
        category="control",
        icon="🔄",
        inputs=[
            {"name": "iterable", "type": "array", "description": "迭代对象"}
        ],
        outputs=[
            {"name": "results", "type": "array", "description": "循环结果"}
        ],
        config_schema={
            "max_iterations": {"type": "number", "default": 100}
        },
        default_config={
            "max_iterations": 100
        }
    ))
    
    # Template 节点
    registry.register(NodeDefinition(
        node_type="template",
        name="模板",
        description="使用模板生成内容",
        category="tool",
        icon="📝",
        inputs=[
            {"name": "variables", "type": "object", "description": "模板变量"}
        ],
        outputs=[
            {"name": "output", "type": "string", "description": "模板输出"}
        ],
        config_schema={
            "template": {"type": "string", "required": True}
        },
        default_config={
            "template": "Hello, {{name}}!"
        }
    ))
    
    # Transformer 节点
    registry.register(NodeDefinition(
        node_type="transformer",
        name="数据转换",
        description="转换和格式化数据",
        category="data",
        icon="🔄",
        inputs=[
            {"name": "input", "type": "any", "description": "输入数据"}
        ],
        outputs=[
            {"name": "output", "type": "any", "description": "输出数据"}
        ],
        config_schema={
            "transform_function": {"type": "string", "required": True}
        },
        default_config={
            "transform_function": "json.dumps"
        }
    ))
    
    # Input 节点
    registry.register(NodeDefinition(
        node_type="input",
        name="输入",
        description="定义工作流输入参数",
        category="io",
        icon="📥",
        inputs=[],
        outputs=[
            {"name": "output", "type": "any", "description": "输入值"}
        ],
        config_schema={
            "variable_name": {"type": "string", "required": True},
            "variable_type": {"type": "string", "default": "string"}
        },
        default_config={
            "variable_name": "input",
            "variable_type": "string"
        }
    ))
    
    # Output 节点
    registry.register(NodeDefinition(
        node_type="output",
        name="输出",
        description="定义工作流输出结果",
        category="io",
        icon="📤",
        inputs=[
            {"name": "input", "type": "any", "description": "输出值"}
        ],
        outputs=[],
        config_schema={
            "variable_name": {"type": "string", "required": True}
        },
        default_config={
            "variable_name": "output"
        }
    ))
    
    # 数据过滤节点
    registry.register(NodeDefinition(
        node_type="filter",
        name="数据过滤",
        description="根据条件过滤数据",
        category="data",
        icon="🔍",
        inputs=[
            {"name": "data", "type": "array", "description": "输入数据"}
        ],
        outputs=[
            {"name": "filtered_data", "type": "array", "description": "过滤后的数据"}
        ],
        config_schema={
            "filter_expression": {"type": "string", "required": True}
        },
        default_config={
            "filter_expression": "item > 0"
        }
    ))
    
    # 数据聚合节点
    registry.register(NodeDefinition(
        node_type="aggregate",
        name="数据聚合",
        description="聚合数据计算统计值",
        category="data",
        icon="📊",
        inputs=[
            {"name": "data", "type": "array", "description": "输入数据"}
        ],
        outputs=[
            {"name": "result", "type": "number", "description": "聚合结果"}
        ],
        config_schema={
            "aggregation_type": {"type": "string", "default": "sum"}
        },
        default_config={
            "aggregation_type": "sum"
        }
    ))
    
    # 嵌入生成节点
    registry.register(NodeDefinition(
        node_type="embedding",
        name="嵌入生成",
        description="生成文本嵌入向量",
        category="ai",
        icon="🔮",
        inputs=[
            {"name": "text", "type": "string", "description": "输入文本"}
        ],
        outputs=[
            {"name": "embedding", "type": "array", "description": "嵌入向量"}
        ],
        config_schema={
            "model": {"type": "string", "default": "text-embedding-ada-002"}
        },
        default_config={
            "model": "text-embedding-ada-002"
        }
    ))
    
    # 文本分类节点
    registry.register(NodeDefinition(
        node_type="classifier",
        name="文本分类",
        description="对文本进行分类",
        category="ai",
        icon="🏷️",
        inputs=[
            {"name": "text", "type": "string", "description": "输入文本"}
        ],
        outputs=[
            {"name": "category", "type": "string", "description": "分类结果"}
        ],
        config_schema={
            "categories": {"type": "array", "required": True}
        },
        default_config={
            "categories": ["positive", "negative", "neutral"]
        }
    ))
    
    # 摘要生成节点
    registry.register(NodeDefinition(
        node_type="summarizer",
        name="摘要生成",
        description="生成文本摘要",
        category="ai",
        icon="📝",
        inputs=[
            {"name": "text", "type": "string", "description": "输入文本"}
        ],
        outputs=[
            {"name": "summary", "type": "string", "description": "文本摘要"}
        ],
        config_schema={
            "max_length": {"type": "number", "default": 100}
        },
        default_config={
            "max_length": 100
        }
    ))
    
    # 文件操作节点
    registry.register(NodeDefinition(
        node_type="file_operation",
        name="文件操作",
        description="执行文件读写操作",
        category="tool",
        icon="📁",
        inputs=[
            {"name": "path", "type": "string", "description": "文件路径"},
            {"name": "content", "type": "string", "description": "文件内容"}
        ],
        outputs=[
            {"name": "result", "type": "string", "description": "操作结果"}
        ],
        config_schema={
            "operation": {"type": "string", "default": "read"}
        },
        default_config={
            "operation": "read"
        }
    ))
    
    # 网络请求节点
    registry.register(NodeDefinition(
        node_type="http_request",
        name="网络请求",
        description="发送 HTTP 请求",
        category="tool",
        icon="🌐",
        inputs=[
            {"name": "url", "type": "string", "description": "请求 URL"},
            {"name": "data", "type": "object", "description": "请求数据"}
        ],
        outputs=[
            {"name": "response", "type": "object", "description": "响应结果"}
        ],
        config_schema={
            "method": {"type": "string", "default": "GET"},
            "headers": {"type": "object", "default": {}}
        },
        default_config={
            "method": "GET",
            "headers": {}
        }
    ))
    
    # 并行执行节点
    registry.register(NodeDefinition(
        node_type="parallel",
        name="并行执行",
        description="并行执行多个子任务",
        category="control",
        icon="⚡",
        inputs=[
            {"name": "tasks", "type": "array", "description": "子任务列表"}
        ],
        outputs=[
            {"name": "results", "type": "array", "description": "任务结果"}
        ],
        config_schema={
            "max_concurrency": {"type": "number", "default": 5}
        },
        default_config={
            "max_concurrency": 5
        }
    ))
    
    # 延迟节点
    registry.register(NodeDefinition(
        node_type="delay",
        name="延迟",
        description="延迟执行",
        category="control",
        icon="⏱️",
        inputs=[
            {"name": "input", "type": "any", "description": "输入数据"}
        ],
        outputs=[
            {"name": "output", "type": "any", "description": "输出数据"}
        ],
        config_schema={
            "seconds": {"type": "number", "default": 1}
        },
        default_config={
            "seconds": 1
        }
    ))
    
    # 注册 browser-use 节点
    from .browser_use_node_registration import register_browser_use_nodes
    register_browser_use_nodes(registry)
    
    print(f"[NodeRegistry] 注册了 {len(registry.get_all())} 个内置节点")


# 导出内置节点注册函数
__all__ = ['register_builtin_nodes']
