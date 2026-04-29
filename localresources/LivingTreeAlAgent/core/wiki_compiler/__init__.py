"""
LLM Wiki 编译层 - 本地知识库与缓存增强系统
Inspired by Andrej Karpathy's LLM Wiki: https://github.com/garrytan/gbrain

核心设计理念：
1. 三层架构：Raw Material → Wiki(LLM编译) → Schema
2. 编译器模式：预先将源材料编译成结构化中间表示
3. 复利效应：每次查询都在让知识库变聪明
4. 三个核心操作：Ingest → Query → Check 持续迭代

目录结构：
wiki_compiler/
├── __init__.py          # 统一入口
├── models.py            # 数据模型
├── compiler.py          # 编译器核心
├── compiled_cache.py     # 编译器式缓存
├── compounding_engine.py # 复利效应引擎
├── ingest_pipeline.py   # 摄入管道
├── query_engine.py      # 查询引擎
├── check_engine.py      # 检查引擎
├── schema.py            # Schema 配置
└── ui/
    └── panel.py         # PyQt6 管理面板
"""

from .compiler import WikiCompiler
from .compiled_cache import CompiledCache
from .compounding_engine import CompoundingEngine
from .models import (
    RawMaterial,
    WikiPage,
    CompiledAnswer,
    Schema,
    MaterialType
)

__version__ = "1.0.0"
__all__ = [
    "WikiCompiler",
    "CompiledCache",
    "CompoundingEngine",
    "RawMaterial",
    "WikiPage",
    "CompiledAnswer",
    "Schema",
    "MaterialType"
]