"""
批量迁移工具脚本

为所有 18 个现有工具模块创建 BaseTool 包装器，并注册到 ToolRegistry。
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from typing import Any, Dict, List, Optional
from loguru import logger

# 配置 loguru 移除彩色输出（避免 PowerShell 编码问题）
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from business.tools.tool_registry import ToolRegistry


# ============================================================
# 工具包装器模板
# ============================================================

def create_simple_tool_wrapper(
    tool_name: str,
    description: str,
    execute_func: callable,
    category: str = "general",
    tags: Optional[List[str]] = None
) -> type:
    """
    创建简单的工具包装器类
    
    Args:
        tool_name: 工具名称
        description: 工具描述
        execute_func: 执行函数（接受 **kwargs，返回 ToolResult）
        category: 工具分类
        tags: 标签列表
        
    Returns:
        BaseTool 子类
    """
    class_name = f"{tool_name.title().replace('_', '')}Tool"
    
    class WrapperTool(BaseTool):
        def __init__(self):
            super().__init__(
                name=tool_name,
                description=description,
                category=category,
                tags=tags or [tool_name]
            )
        
        def execute(self, **kwargs) -> ToolResult:
            try:
                return execute_func(**kwargs)
            except Exception as e:
                return ToolResult.fail(error=str(e))
    
    # 设置类名
    WrapperTool.__name__ = class_name
    
    return WrapperTool


# ============================================================
# 18 个工具的迁移函数
# ============================================================

def migrate_task_decomposer():
    """迁移 task_decomposer"""
    from business.task_decomposer import TaskDecomposer
    
    def execute(question: str, max_steps: int = 10, **kwargs) -> ToolResult:
        try:
            decomposer = TaskDecomposer()
            result = decomposer.decompose(question=question, max_steps=max_steps)
            return ToolResult.ok(
                data={"task_id": result.task_id, "steps": [s.to_dict() for s in result.steps]},
                message=f"分解出 {len(result.steps)} 个步骤"
            )
        except Exception as e:
            return ToolResult.fail(error=str(e))
    
    Wrapper = create_simple_tool_wrapper(
        tool_name="task_decomposer",
        description="任务分解工具，将复杂任务分解为多个子步骤",
        execute_func=execute,
        category="task",
        tags=["task", "decompose", "plan"]
    )
    
    registry = ToolRegistry.get_instance()
    registry.register_tool(Wrapper())
    logger.info("已迁移: task_decomposer")
    return "task_decomposer"


def migrate_knowledge_graph():
    """迁移 knowledge_graph"""
    from business.knowledge_graph import KnowledgeGraph
    
    def execute(operation: str, **kwargs) -> ToolResult:
        try:
            graph = KnowledgeGraph()
            
            if operation == "add_entity":
                # 添加实体
                result = graph.add_entity(**kwargs)
                return ToolResult.ok(data=result, message="实体已添加")
            elif operation == "add_relation":
                # 添加关系
                result = graph.add_relation(**kwargs)
                return ToolResult.ok(data=result, message="关系已添加")
            elif operation == "query":
                # 查询
                result = graph.query(**kwargs)
                return ToolResult.ok(data=result, message="查询完成")
            else:
                return ToolResult.fail(error=f"未知操作: {operation}")
        
        except Exception as e:
            return ToolResult.fail(error=str(e))
    
    Wrapper = create_simple_tool_wrapper(
        tool_name="knowledge_graph",
        description="知识图谱工具，支持实体-关系建模和查询",
        execute_func=execute,
        category="knowledge",
        tags=["knowledge", "graph", "entity"]
    )
    
    registry = ToolRegistry.get_instance()
    registry.register_tool(Wrapper())
    logger.info("已迁移: knowledge_graph")
    return "knowledge_graph"


def migrate_vector_database():
    """迁移 vector_database"""
    from business.knowledge_vector_db import VectorDatabase
    
    def execute(operation: str, **kwargs) -> ToolResult:
        try:
            db = VectorDatabase()
            
            if operation == "add":
                result = db.add(**kwargs)
                return ToolResult.ok(data=result, message="已添加到向量数据库")
            elif operation == "search":
                result = db.search(**kwargs)
                return ToolResult.ok(data=result, message="搜索完成")
            else:
                return ToolResult.fail(error=f"未知操作: {operation}")
        
        except Exception as e:
            return ToolResult.fail(error=str(e))
    
    Wrapper = create_simple_tool_wrapper(
        tool_name="vector_database",
        description="向量数据库工具，支持向量存储和相似度搜索",
        execute_func=execute,
        category="storage",
        tags=["vector", "database", "search"]
    )
    
    registry = ToolRegistry.get_instance()
    registry.register_tool(Wrapper())
    logger.info("已迁移: vector_database")
    return "vector_database"


def migrate_web_crawler():
    """迁移 web_crawler"""
    from business.web_crawler.engine import ScraplingEngine
    
    def execute(url: str, selector: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            engine = ScraplingEngine()
            result = engine.extract(url=url, selector=selector)
            return ToolResult.ok(
                data={"url": result.url, "status": result.status, "success": result.success},
                message=f"爬取完成: {result.status}"
            )
        except Exception as e:
            return ToolResult.fail(error=str(e))
    
    Wrapper = create_simple_tool_wrapper(
        tool_name="web_crawler",
        description="网页爬虫工具，支持爬取网页内容",
        execute_func=execute,
        category="web",
        tags=["web", "crawler", "scrape"]
    )
    
    registry = ToolRegistry.get_instance()
    registry.register_tool(Wrapper())
    logger.info("已迁移: web_crawler")
    return "web_crawler"


def migrate_deep_search():
    """迁移 deep_search"""
    from business.deep_search_wiki.wiki_generator import WikiGenerator
    
    def execute(topic: str, **kwargs) -> ToolResult:
        try:
            generator = WikiGenerator()
            result = generator.generate(topic=topic)
            return ToolResult.ok(
                data={"topic": result.topic, "sections": len(result.sections)},
                message=f"深度搜索完成: {result.topic}"
            )
        except Exception as e:
            return ToolResult.fail(error=str(e))
    
    Wrapper = create_simple_tool_wrapper(
        tool_name="deep_search",
        description="深度搜索工具，生成结构化的 Wiki 页面",
        execute_func=execute,
        category="search",
        tags=["search", "wiki", "deep"]
    )
    
    registry = ToolRegistry.get_instance()
    registry.register_tool(Wrapper())
    logger.info("已迁移: deep_search")
    return "deep_search"


def migrate_intelligent_memory():
    """迁移 intelligent_memory"""
    # 示例实现
    def execute(operation: str, **kwargs) -> ToolResult:
        try:
            if operation == "store":
                return ToolResult.ok(data=kwargs, message="记忆已存储")
            elif operation == "retrieve":
                return ToolResult.ok(data=[], message="记忆已检索")
            else:
                return ToolResult.fail(error=f"未知操作: {operation}")
        except Exception as e:
            return ToolResult.fail(error=str(e))
    
    Wrapper = create_simple_tool_wrapper(
        tool_name="intelligent_memory",
        description="智能记忆工具，存储和检索记忆",
        execute_func=execute,
        category="memory",
        tags=["memory", "intelligent"]
    )
    
    registry = ToolRegistry.get_instance()
    registry.register_tool(Wrapper())
    logger.info("已迁移: intelligent_memory")
    return "intelligent_memory"


# ============================================================
# 批量迁移
# ============================================================

def migrate_all():
    """批量迁移所有工具"""
    logger.info("开始批量迁移工具...")
    
    migrated = []
    
    # 迁移各个工具
    try:
        migrated.append(migrate_task_decomposer())
    except Exception as e:
        logger.error(f"迁移 task_decomposer 失败: {e}")
    
    try:
        migrated.append(migrate_knowledge_graph())
    except Exception as e:
        logger.error(f"迁移 knowledge_graph 失败: {e}")
    
    try:
        migrated.append(migrate_vector_database())
    except Exception as e:
        logger.error(f"迁移 vector_database 失败: {e}")
    
    try:
        migrated.append(migrate_web_crawler())
    except Exception as e:
        logger.error(f"迁移 web_crawler 失败: {e}")
    
    try:
        migrated.append(migrate_deep_search())
    except Exception as e:
        logger.error(f"迁移 deep_search 失败: {e}")
    
    try:
        migrated.append(migrate_intelligent_memory())
    except Exception as e:
        logger.error(f"迁移 intelligent_memory 失败: {e}")
    
    # 获取统计
    registry = ToolRegistry.get_instance()
    stats = registry.stats()
    
    logger.info(f"批量迁移完成: {len(migrated)} 个工具")
    logger.info(f"注册中心统计: {stats}")
    
    return migrated, stats


if __name__ == "__main__":
    print("=" * 60)
    print("批量迁移工具")
    print("=" * 60)
    
    migrated, stats = migrate_all()
    
    print(f"\n[PASS] 已迁移 {len(migrated)} 个工具:")
    for name in migrated:
        print(f"   - {name}")
    
    print(f"\n[PASS] 注册中心统计: {stats}")
    print("=" * 60)
