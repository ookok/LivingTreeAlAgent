"""AI 工作流模板注册"""

from ..models.workflow import Workflow


def register_ai_templates():
    """注册 AI 工作流模板
    
    Returns:
        dict: 模板名称到工作流的映射
    """
    templates = {
        # 文本分类工作流
        "text_classification": Workflow(
            id="text_classification",
            name="文本分类工作流",
            description="对输入文本进行分类",
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "name": "输入文本",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "variable_name": "text",
                        "variable_type": "string"
                    }
                },
                {
                    "id": "classifier",
                    "type": "classifier",
                    "name": "文本分类器",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "categories": ["positive", "negative", "neutral"]
                    }
                },
                {
                    "id": "output",
                    "type": "output",
                    "name": "分类结果",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "variable_name": "category"
                    }
                }
            ],
            connections=[
                {"source": "input", "target": "classifier", "source_port": "output", "target_port": "text"},
                {"source": "classifier", "target": "output", "source_port": "category", "target_port": "input"}
            ]
        ),
        
        # 情感分析工作流
        "sentiment_analysis": Workflow(
            id="sentiment_analysis",
            name="情感分析工作流",
            description="分析文本的情感倾向",
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "name": "输入文本",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "variable_name": "text",
                        "variable_type": "string"
                    }
                },
                {
                    "id": "llm",
                    "type": "llm",
                    "name": "情感分析",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "model": "gpt-4",
                        "temperature": 0.3,
                        "max_tokens": 100
                    }
                },
                {
                    "id": "output",
                    "type": "output",
                    "name": "情感分析结果",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "variable_name": "sentiment"
                    }
                }
            ],
            connections=[
                {"source": "input", "target": "llm", "source_port": "output", "target_port": "prompt"},
                {"source": "llm", "target": "output", "source_port": "response", "target_port": "input"}
            ]
        ),
        
        # 问答系统工作流
        "question_answering": Workflow(
            id="question_answering",
            name="问答系统工作流",
            description="基于知识库回答问题",
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "name": "输入问题",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "variable_name": "question",
                        "variable_type": "string"
                    }
                },
                {
                    "id": "knowledge",
                    "type": "knowledge",
                    "name": "知识库检索",
                    "position": {"x": 250, "y": 100},
                    "config": {
                        "knowledge_base": "default",
                        "top_k": 5
                    }
                },
                {
                    "id": "llm",
                    "type": "llm",
                    "name": "回答生成",
                    "position": {"x": 400, "y": 100},
                    "config": {
                        "model": "gpt-4",
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                },
                {
                    "id": "output",
                    "type": "output",
                    "name": "回答结果",
                    "position": {"x": 550, "y": 100},
                    "config": {
                        "variable_name": "answer"
                    }
                }
            ],
            connections=[
                {"source": "input", "target": "knowledge", "source_port": "output", "target_port": "query"},
                {"source": "knowledge", "target": "llm", "source_port": "context", "target_port": "context"},
                {"source": "input", "target": "llm", "source_port": "output", "target_port": "prompt"},
                {"source": "llm", "target": "output", "source_port": "response", "target_port": "input"}
            ]
        ),
        
        # 文本摘要工作流
        "text_summarization": Workflow(
            id="text_summarization",
            name="文本摘要工作流",
            description="生成文本摘要",
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "name": "输入文本",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "variable_name": "text",
                        "variable_type": "string"
                    }
                },
                {
                    "id": "summarizer",
                    "type": "summarizer",
                    "name": "摘要生成",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "max_length": 150
                    }
                },
                {
                    "id": "output",
                    "type": "output",
                    "name": "摘要结果",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "variable_name": "summary"
                    }
                }
            ],
            connections=[
                {"source": "input", "target": "summarizer", "source_port": "output", "target_port": "text"},
                {"source": "summarizer", "target": "output", "source_port": "summary", "target_port": "input"}
            ]
        ),
        
        # 翻译工作流
        "translation": Workflow(
            id="translation",
            name="翻译工作流",
            description="将文本翻译成目标语言",
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "name": "输入文本",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "variable_name": "text",
                        "variable_type": "string"
                    }
                },
                {
                    "id": "llm",
                    "type": "llm",
                    "name": "翻译",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "model": "gpt-4",
                        "temperature": 0.3,
                        "max_tokens": 1000
                    }
                },
                {
                    "id": "output",
                    "type": "output",
                    "name": "翻译结果",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "variable_name": "translation"
                    }
                }
            ],
            connections=[
                {"source": "input", "target": "llm", "source_port": "output", "target_port": "prompt"},
                {"source": "llm", "target": "output", "source_port": "response", "target_port": "input"}
            ]
        ),
        
        # 数据处理工作流
        "data_processing": Workflow(
            id="data_processing",
            name="数据处理工作流",
            description="处理和转换数据",
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "name": "输入数据",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "variable_name": "data",
                        "variable_type": "array"
                    }
                },
                {
                    "id": "filter",
                    "type": "filter",
                    "name": "数据过滤",
                    "position": {"x": 250, "y": 100},
                    "config": {
                        "filter_expression": "item > 0"
                    }
                },
                {
                    "id": "aggregate",
                    "type": "aggregate",
                    "name": "数据聚合",
                    "position": {"x": 400, "y": 100},
                    "config": {
                        "aggregation_type": "sum"
                    }
                },
                {
                    "id": "output",
                    "type": "output",
                    "name": "处理结果",
                    "position": {"x": 550, "y": 100},
                    "config": {
                        "variable_name": "result"
                    }
                }
            ],
            connections=[
                {"source": "input", "target": "filter", "source_port": "output", "target_port": "data"},
                {"source": "filter", "target": "aggregate", "source_port": "filtered_data", "target_port": "data"},
                {"source": "aggregate", "target": "output", "source_port": "result", "target_port": "input"}
            ]
        ),
        
        # 图像描述工作流
        "image_captioning": Workflow(
            id="image_captioning",
            name="图像描述工作流",
            description="为图像生成描述",
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "name": "图像路径",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "variable_name": "image_path",
                        "variable_type": "string"
                    }
                },
                {
                    "id": "llm",
                    "type": "llm",
                    "name": "图像描述",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "model": "gpt-4-vision-preview",
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                },
                {
                    "id": "output",
                    "type": "output",
                    "name": "描述结果",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "variable_name": "caption"
                    }
                }
            ],
            connections=[
                {"source": "input", "target": "llm", "source_port": "output", "target_port": "prompt"},
                {"source": "llm", "target": "output", "source_port": "response", "target_port": "input"}
            ]
        ),
        
        # 代码生成工作流
        "code_generation": Workflow(
            id="code_generation",
            name="代码生成工作流",
            description="根据需求生成代码",
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "name": "需求描述",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "variable_name": "requirements",
                        "variable_type": "string"
                    }
                },
                {
                    "id": "llm",
                    "type": "llm",
                    "name": "代码生成",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "model": "gpt-4",
                        "temperature": 0.7,
                        "max_tokens": 2000
                    }
                },
                {
                    "id": "output",
                    "type": "output",
                    "name": "生成代码",
                    "position": {"x": 500, "y": 100},
                    "config": {
                        "variable_name": "code"
                    }
                }
            ],
            connections=[
                {"source": "input", "target": "llm", "source_port": "output", "target_port": "prompt"},
                {"source": "llm", "target": "output", "source_port": "response", "target_port": "input"}
            ]
        )
    }
    
    print(f"[AITemplates] 注册了 {len(templates)} 个 AI 工作流模板")
    return templates


# 导出模板注册函数
__all__ = ['register_ai_templates']
