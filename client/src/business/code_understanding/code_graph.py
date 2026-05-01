"""
代码图 - 代码依赖关系可视化

核心功能：
1. 构建代码依赖图
2. 可视化代码结构
3. 依赖关系分析
4. 影响范围分析
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class GraphNode:
    """图节点"""
    id: str
    name: str
    type: str  # file, class, function, module
    file_path: Optional[str] = None
    line: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """图边"""
    source: str
    target: str
    type: str  # import, call, inherit, reference
    label: Optional[str] = None


@dataclass
class CodeGraphData:
    """代码图数据"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: Dict[str, Any] = field(default_factory=dict)


class CodeGraph:
    """
    代码图 - 代码依赖关系可视化
    
    核心特性：
    1. 构建代码依赖图
    2. 可视化代码结构
    3. 依赖关系分析
    4. 影响范围分析
    """

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        self._file_nodes: Dict[str, str] = {}  # file_path -> node_id

    def add_file(self, file_path: str, language: str = "python") -> str:
        """添加文件节点"""
        node_id = f"file_{file_path.replace('/', '_').replace('.', '_')}"
        
        if node_id not in self._nodes:
            node = GraphNode(
                id=node_id,
                name=Path(file_path).name,
                type='file',
                file_path=file_path,
                metadata={'language': language}
            )
            self._nodes[node_id] = node
            self._file_nodes[file_path] = node_id
        
        return node_id

    def add_symbol(self, file_path: str, name: str, symbol_type: str, line: int = 0):
        """添加符号节点"""
        # 确保文件节点存在
        file_node_id = self.add_file(file_path)
        
        symbol_id = f"{file_node_id}_{symbol_type}_{name}"
        
        if symbol_id not in self._nodes:
            node = GraphNode(
                id=symbol_id,
                name=name,
                type=symbol_type,
                file_path=file_path,
                line=line
            )
            self._nodes[symbol_id] = node
            
            # 添加文件到符号的边
            self._edges.append(GraphEdge(
                source=file_node_id,
                target=symbol_id,
                type='contains',
                label='contains'
            ))
        
        return symbol_id

    def add_dependency(self, source_id: str, target_id: str, dep_type: str = 'reference'):
        """添加依赖关系"""
        if source_id not in self._nodes or target_id not in self._nodes:
            return
        
        # 避免重复边
        for edge in self._edges:
            if edge.source == source_id and edge.target == target_id and edge.type == dep_type:
                return
        
        self._edges.append(GraphEdge(
            source=source_id,
            target=target_id,
            type=dep_type,
            label=dep_type
        ))

    def add_import(self, from_file: str, import_name: str, to_file: Optional[str] = None):
        """添加导入关系"""
        from_node_id = self.add_file(from_file)
        
        if to_file:
            to_node_id = self.add_file(to_file)
            self._edges.append(GraphEdge(
                source=from_node_id,
                target=to_node_id,
                type='import',
                label=import_name
            ))
        else:
            # 外部依赖
            ext_node_id = f"ext_{import_name}"
            if ext_node_id not in self._nodes:
                self._nodes[ext_node_id] = GraphNode(
                    id=ext_node_id,
                    name=import_name,
                    type='external'
                )
            
            self._edges.append(GraphEdge(
                source=from_node_id,
                target=ext_node_id,
                type='import',
                label=import_name
            ))

    def add_call(self, caller_file: str, caller_name: str, callee_file: str, callee_name: str):
        """添加调用关系"""
        caller_id = self.add_symbol(caller_file, caller_name, 'function')
        callee_id = self.add_symbol(callee_file, callee_name, 'function')
        
        self._edges.append(GraphEdge(
            source=caller_id,
            target=callee_id,
            type='call',
            label='calls'
        ))

    def get_dependencies(self, node_id: str) -> List[GraphNode]:
        """获取节点的依赖"""
        dependencies = []
        for edge in self._edges:
            if edge.source == node_id:
                if edge.target in self._nodes:
                    dependencies.append(self._nodes[edge.target])
        return dependencies

    def get_dependents(self, node_id: str) -> List[GraphNode]:
        """获取依赖该节点的所有节点"""
        dependents = []
        for edge in self._edges:
            if edge.target == node_id:
                if edge.source in self._nodes:
                    dependents.append(self._nodes[edge.source])
        return dependents

    def analyze_impact(self, file_path: str) -> Dict[str, Any]:
        """分析文件变更的影响范围"""
        file_node_id = self._file_nodes.get(file_path)
        if not file_node_id:
            return {"error": "文件不存在"}
        
        impacted_nodes = set()
        visited = set()
        queue = [file_node_id]
        
        # BFS遍历依赖链
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            
            visited.add(current)
            
            # 获取所有依赖当前节点的节点
            dependents = self.get_dependents(current)
            for dep in dependents:
                impacted_nodes.add(dep.id)
                queue.append(dep.id)
        
        impacted_files = set()
        for node_id in impacted_nodes:
            node = self._nodes[node_id]
            if node.file_path:
                impacted_files.add(node.file_path)
        
        return {
            "file": file_path,
            "impacted_nodes": len(impacted_nodes),
            "impacted_files": list(impacted_files),
            "impacted_symbols": [self._nodes[n].name for n in impacted_nodes if self._nodes[n].type != 'file']
        }

    def find_cycles(self) -> List[List[str]]:
        """查找循环依赖"""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node_id, path):
            if node_id in rec_stack:
                # 找到循环
                idx = path.index(node_id)
                cycles.append(path[idx:])
                return
            
            if node_id in visited:
                return
            
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for edge in self._edges:
                if edge.source == node_id:
                    dfs(edge.target, path + [node_id])
            
            rec_stack.remove(node_id)
        
        for node_id in self._nodes:
            if node_id not in visited:
                dfs(node_id, [])
        
        return cycles

    def get_graph_data(self) -> CodeGraphData:
        """获取图数据"""
        return CodeGraphData(
            nodes=list(self._nodes.values()),
            edges=self._edges
        )

    def to_json(self) -> str:
        """转换为JSON"""
        data = {
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "type": node.type,
                    "file_path": node.file_path,
                    "line": node.line,
                    "metadata": node.metadata
                }
                for node in self._nodes.values()
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.type,
                    "label": edge.label
                }
                for edge in self._edges
            ]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def from_json(self, json_str: str):
        """从JSON加载"""
        data = json.loads(json_str)
        
        self._nodes = {}
        self._edges = []
        self._file_nodes = {}
        
        for node_data in data.get("nodes", []):
            node = GraphNode(
                id=node_data["id"],
                name=node_data["name"],
                type=node_data["type"],
                file_path=node_data.get("file_path"),
                line=node_data.get("line", 0),
                metadata=node_data.get("metadata", {})
            )
            self._nodes[node.id] = node
            
            if node.type == 'file' and node.file_path:
                self._file_nodes[node.file_path] = node.id
        
        for edge_data in data.get("edges", []):
            self._edges.append(GraphEdge(
                source=edge_data["source"],
                target=edge_data["target"],
                type=edge_data["type"],
                label=edge_data.get("label")
            ))

    def clear(self):
        """清空图"""
        self._nodes = {}
        self._edges = []
        self._file_nodes = {}


def get_code_graph() -> CodeGraph:
    """获取代码图实例"""
    return CodeGraph()