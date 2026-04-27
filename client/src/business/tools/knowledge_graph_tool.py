"""
KnowledgeGraphTool - 知识图谱工具（BaseTool 包装器）

将现有的 knowledge_graph 功能包装为标准的 BaseTool 子类
"""

from typing import Any, Dict, List, Optional
from loguru import logger

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from client.src.business.knowledge_graph import KnowledgeGraph, Entity, Relation, EntityType, RelationType


class KnowledgeGraphTool(BaseTool):
    """
    知识图谱工具
    
    支持实体-关系建模、知识推理、路径查询。
    
    示例：
        tool = KnowledgeGraphTool()
        
        # 添加实体
        result = tool.execute(
            operation="add_entity",
            entity_id="e1",
            name="张三",
            entity_type="person"
        )
        
        # 添加关系
        result = tool.execute(
            operation="add_relation",
            source_id="e1",
            target_id="e2",
            relation_type="works_for"
        )
        
        # 查询路径
        result = tool.execute(
            operation="find_path",
            source_id="e1",
            target_id="e3"
        )
    """
    
    def __init__(self, graph_id: str = "default"):
        super().__init__(
            name="knowledge_graph",
            description="知识图谱工具，支持实体-关系建模、知识推理、路径查询",
            category="knowledge",
            tags=["knowledge", "graph", "reasoning", "entity", "relation"],
            version="1.0.0"
        )
        self._graph = KnowledgeGraph(graph_id=graph_id)
        self._logger = logger.bind(tool="KnowledgeGraphTool", graph_id=graph_id)
    
    def execute(self, operation: str, **kwargs) -> ToolResult:
        """
        执行知识图谱操作
        
        Args:
            operation: 操作类型
                - add_entity: 添加实体
                - add_relation: 添加关系
                - get_entity: 获取实体
                - get_relations: 获取关系
                - find_path: 查找路径
                - query: 查询实体
                - clear: 清空图谱
            **kwargs: 操作参数
            
        Returns:
            ToolResult 包含操作结果
        """
        try:
            self._logger.info(f"执行操作: {operation}, 参数: {kwargs}")
            
            if operation == "add_entity":
                return self._add_entity(**kwargs)
            elif operation == "add_relation":
                return self._add_relation(**kwargs)
            elif operation == "get_entity":
                return self._get_entity(**kwargs)
            elif operation == "get_relations":
                return self._get_relations(**kwargs)
            elif operation == "find_path":
                return self._find_path(**kwargs)
            elif operation == "query":
                return self._query(**kwargs)
            elif operation == "clear":
                return self._clear(**kwargs)
            else:
                return ToolResult.fail(f"未知操作: {operation}")
        
        except Exception as e:
            self._logger.exception(f"执行操作失败: {operation}")
            return ToolResult.fail(error=str(e))
    
    def _add_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """添加实体"""
        try:
            # 转换 entity_type 字符串为枚举
            type_enum = EntityType(entity_type)
            
            entity = Entity(
                entity_id=entity_id,
                name=name,
                entity_type=type_enum,
                properties=properties or {}
            )
            
            success = self._graph.add_entity(entity)
            
            if success:
                return ToolResult.ok(
                    data={"entity_id": entity_id, "name": name},
                    message=f"实体已添加: {name}"
                )
            else:
                return ToolResult.fail(f"添加实体失败: {entity_id} 已存在")
        
        except Exception as e:
            return ToolResult.fail(error=str(e))
    
    def _add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
        weight: float = 1.0
    ) -> ToolResult:
        """添加关系"""
        try:
            # 转换 relation_type 字符串为枚举
            type_enum = RelationType(relation_type)
            
            relation = Relation(
                relation_id=f"r_{source_id}_{target_id}_{relation_type}",
                source_id=source_id,
                target_id=target_id,
                relation_type=type_enum,
                properties=properties or {},
                weight=weight
            )
            
            success = self._graph.add_relation(relation)
            
            if success:
                return ToolResult.ok(
                    data={
                        "source_id": source_id,
                        "target_id": target_id,
                        "relation_type": relation_type
                    },
                    message=f"关系已添加: {source_id} -[{relation_type}]-> {target_id}"
                )
            else:
                return ToolResult.fail(f"添加关系失败: 实体不存在")
        
        except Exception as e:
            return ToolResult.fail(error=str(e))
    
    def _get_entity(self, entity_id: str) -> ToolResult:
        """获取实体"""
        entity = self._graph.get_entity(entity_id)
        
        if entity:
            return ToolResult.ok(
                data=entity.to_dict(),
                message=f"找到实体: {entity.name}"
            )
        else:
            return ToolResult.fail(f"实体不存在: {entity_id}")
    
    def _get_relations(self, entity_id: str, direction: str = "both") -> ToolResult:
        """获取关系"""
        relations = self._graph.get_relations(entity_id, direction)
        
        return ToolResult.ok(
            data={
                "entity_id": entity_id,
                "relation_count": len(relations),
                "relations": [r.to_dict() for r in relations]
            },
            message=f"找到 {len(relations)} 个关系"
        )
    
    def _find_path(self, source_id: str, target_id: str) -> ToolResult:
        """查找路径"""
        path = self._graph.find_path(source_id, target_id)
        
        if path:
            return ToolResult.ok(
                data={
                    "source_id": source_id,
                    "target_id": target_id,
                    "path_length": len(path),
                    "path": path
                },
                message=f"找到路径，长度: {len(path)}"
            )
        else:
            return ToolResult.fail(f"未找到路径: {source_id} -> {target_id}")
    
    def _query(self, query: str) -> ToolResult:
        """查询实体（简单实现）"""
        results = self._graph.query_entities(query)
        
        return ToolResult.ok(
            data={
                "query": query,
                "result_count": len(results),
                "results": [e.to_dict() for e in results]
            },
            message=f"查询到 {len(results)} 个实体"
        )
    
    def _clear(self) -> ToolResult:
        """清空图谱"""
        self._graph.clear()
        
        return ToolResult.ok(
            data={"status": "cleared"},
            message="图谱已清空"
        )
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """获取工具定义（用于 LLM 调用）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "操作类型",
                        "enum": ["add_entity", "add_relation", "get_entity", "get_relations", "find_path", "query", "clear"]
                    },
                    "entity_id": {"type": "string", "description": "实体 ID"},
                    "name": {"type": "string", "description": "实体名称"},
                    "entity_type": {"type": "string", "description": "实体类型"},
                    "source_id": {"type": "string", "description": "源实体 ID"},
                    "target_id": {"type": "string", "description": "目标实体 ID"},
                    "relation_type": {"type": "string", "description": "关系类型"}
                },
                "required": ["operation"]
            }
        }


# 便捷函数
def create_knowledge_graph(graph_id: str = "default") -> KnowledgeGraphTool:
    """创建知识图谱工具"""
    return KnowledgeGraphTool(graph_id=graph_id)


if __name__ == "__main__":
    # 简单测试
    tool = KnowledgeGraphTool()
    
    # 添加实体
    result = tool.execute(
        operation="add_entity",
        entity_id="person_1",
        name="张三",
        entity_type="person"
    )
    print(f"添加实体: {result.success}, {result.message}")
    
    result = tool.execute(
        operation="add_entity",
        entity_id="org_1",
        name="ABC 公司",
        entity_type="organization"
    )
    print(f"添加实体: {result.success}, {result.message}")
    
    # 添加关系
    result = tool.execute(
        operation="add_relation",
        source_id="person_1",
        target_id="org_1",
        relation_type="works_for"
    )
    print(f"添加关系: {result.success}, {result.message}")


# =============================================================================
# Auto-Registration
# =============================================================================

_registration_done = False

def _auto_register():
    """自动注册工具到 ToolRegistry"""
    global _registration_done
    
    if _registration_done:
        return
    
    try:
        # 创建工具实例
        _tool_instance = KnowledgeGraphTool()
        
        # 获取 ToolRegistry 单例
        from client.src.business.tools.tool_registry import ToolRegistry
        _registry = ToolRegistry.get_instance()
        
        # 注册工具
        success = _registry.register_tool(_tool_instance)
        
        if success:
            import loguru
            loguru.logger.info(f"Auto-registered: {_tool_instance.name}")
        else:
            import loguru
            loguru.logger.warning(f"Auto-registration failed (tool already exists): {_tool_instance.name}")
        
        _registration_done = True
        
    except Exception as e:
        import loguru
        loguru.logger.error(f"Auto-registration error: {e}")


# 执行自动注册
_auto_register()
