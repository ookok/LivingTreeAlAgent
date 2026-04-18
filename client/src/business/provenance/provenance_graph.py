# =================================================================
# 图谱关系层 - Provenance Graph
# =================================================================
# 功能：
# 1. 节点关系存储和查询
# 2. 溯源路径查询
# 3. 图谱遍历
# 4. 血缘分析
# =================================================================

import json
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import threading


class RelationType(Enum):
    """关系类型"""
    # 知识关系
    DERIVED_FROM = "derived_from"     # 派生自
    CITES = "cites"                   # 引用
    VERSIONS = "versions"            # 版本关系
    BRANCHES_FROM = "branches_from"  # 分支

    # 组成关系
    PART_OF = "part_of"             # 组成部分
    CONTAINS = "contains"           # 包含
    ASSEMBLY_OF = "assembly_of"    # 装配来源

    # 流程关系
    INPUT_OF = "input_of"           # 输入
    OUTPUT_OF = "output_of"         # 输出
    PRECEDES = "precedes"           # 在...之前
    FOLLOWS = "follows"             # 在...之后

    # 所有权
    OWNED_BY = "owned_by"           # 所属
    CREATED_BY = "created_by"       # 创建者

    # 溯源专用
    SOURCE_OF = "source_of"         # 来源
    PROVENANCE_PATH = "provenance_path"  # 溯源路径


@dataclass
class GraphEdge:
    """图谱边（关系）"""
    edge_id: str
    source_id: str
    target_id: str
    relation: RelationType

    # 属性
    properties: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    created_at: float = field(default_factory=time.time)
    created_by: str = "system"

    def __post_init__(self):
        if not self.edge_id:
            self.edge_id = str(uuid.uuid4())[:12]

    @property
    def display_text(self) -> str:
        """获取显示文本"""
        relation_texts = {
            RelationType.DERIVED_FROM: "派生自",
            RelationType.CITES: "引用",
            RelationType.VERSIONS: "版本",
            RelationType.BRANCHES_FROM: "分支自",
            RelationType.PART_OF: "属于",
            RelationType.CONTAINS: "包含",
            RelationType.ASSEMBLY_OF: "装配来源",
            RelationType.INPUT_OF: "输入到",
            RelationType.OUTPUT_OF: "产出",
            RelationType.PRECEDES: "在...之前",
            RelationType.FOLLOWS: "跟随",
            RelationType.OWNED_BY: "所属",
            RelationType.CREATED_BY: "创建者",
            RelationType.SOURCE_OF: "来源",
            RelationType.PROVENANCE_PATH: "溯源路径",
        }
        return relation_texts.get(self.relation, self.relation.value)


@dataclass
class GraphQuery:
    """图谱查询"""
    query_id: str
    query_type: str                 # trace /血缘/路径/邻居

    # 查询条件
    start_node_id: str = ""
    end_node_id: str = ""
    relation_types: List[str] = field(default_factory=list)
    max_depth: int = 5

    # 节点过滤
    node_types: List[str] = field(default_factory=list)
    node_tags: List[str] = field(default_factory=list)

    # 结果
    results: List[Any] = field(default_factory=list)
    path: List[str] = field(default_factory=list)  # 路径节点ID列表

    execution_time: float = 0       # 执行时间（毫秒）

    @property
    def result_count(self) -> int:
        return len(self.results)


class ProvenanceGraph:
    """
    溯源图谱

    核心功能：
    1. 节点和关系存储
    2. 溯源路径查询
    3. 血缘分析
    4. 图遍历算法
    """

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = str(Path.home() / ".hermes-desktop" / "provenance" / "graph")

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 内存索引
        self._nodes: Dict[str, Dict[str, Any]] = {}     # node_id -> node_data
        self._edges: List[GraphEdge] = []               # 所有边
        self._outgoing: Dict[str, List[str]] = {}      # source_id -> [(target_id, edge_id)]
        self._incoming: Dict[str, List[str]] = {}      # target_id -> [(source_id, edge_id)]

        # 索引
        self._node_type_index: Dict[str, Set[str]] = {}  # node_type -> node_ids
        self._tag_index: Dict[str, Set[str]] = {}       # tag -> node_ids

        # 锁
        self._lock = threading.Lock()

        # 加载数据
        self._load_graph()

    def _load_graph(self):
        """加载图数据"""
        nodes_file = self.storage_path / "nodes.json"
        edges_file = self.storage_path / "edges.jsonl"

        # 加载节点
        if nodes_file.exists():
            try:
                with open(nodes_file, "r", encoding="utf-8") as f:
                    nodes_data = json.load(f)
                    for node_id, node_data in nodes_data.items():
                        self._add_node_to_index(node_id, node_data)
            except Exception as e:
                print(f"[ProvenanceGraph] Failed to load nodes: {e}")

        # 加载边
        if edges_file.exists():
            try:
                with open(edges_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            edge_data = json.loads(line)
                            edge = GraphEdge(
                                edge_id=edge_data["edge_id"],
                                source_id=edge_data["source_id"],
                                target_id=edge_data["target_id"],
                                relation=RelationType(edge_data["relation"]),
                                properties=edge_data.get("properties", {}),
                                created_at=edge_data.get("created_at", time.time()),
                                created_by=edge_data.get("created_by", "system")
                            )
                            self._add_edge_to_index(edge)
            except Exception as e:
                print(f"[ProvenanceGraph] Failed to load edges: {e}")

    def _save_nodes(self):
        """保存节点"""
        nodes_file = self.storage_path / "nodes.json"
        with open(nodes_file, "w", encoding="utf-8") as f:
            json.dump(self._nodes, f, ensure_ascii=False, indent=2)

    def _save_edge(self, edge: GraphEdge):
        """保存边"""
        edges_file = self.storage_path / "edges.jsonl"
        with open(edges_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "edge_id": edge.edge_id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relation": edge.relation.value,
                "properties": edge.properties,
                "created_at": edge.created_at,
                "created_by": edge.created_by
            }, ensure_ascii=False) + "\n")

    def _add_node_to_index(self, node_id: str, node_data: Dict[str, Any]):
        """添加节点到索引"""
        self._nodes[node_id] = node_data

        # 类型索引
        node_type = node_data.get("node_type", "unknown")
        if node_type not in self._node_type_index:
            self._node_type_index[node_type] = set()
        self._node_type_index[node_type].add(node_id)

        # 标签索引
        for tag in node_data.get("tags", []):
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(node_id)

    def _add_edge_to_index(self, edge: GraphEdge):
        """添加边到索引"""
        self._edges.append(edge)

        # 出边索引
        if edge.source_id not in self._outgoing:
            self._outgoing[edge.source_id] = []
        self._outgoing[edge.source_id].append((edge.target_id, edge.edge_id))

        # 入边索引
        if edge.target_id not in self._incoming:
            self._incoming[edge.target_id] = []
        self._incoming[edge.target_id].append((edge.source_id, edge.edge_id))

    # ========== 节点操作 ==========

    def add_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        properties: Dict[str, Any] = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        添加节点

        Args:
            node_id: 节点ID
            node_type: 节点类型
            name: 节点名称
            properties: 属性
            tags: 标签
            metadata: 元数据

        Returns:
            节点ID
        """
        node_data = {
            "node_id": node_id,
            "node_type": node_type,
            "name": name,
            "properties": properties or {},
            "tags": tags or [],
            "metadata": metadata or {},
            "created_at": time.time(),
            "updated_at": time.time()
        }

        with self._lock:
            self._add_node_to_index(node_id, node_data)
            self._save_nodes()

        return node_id

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        return self._nodes.get(node_id)

    def update_node(
        self,
        node_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """更新节点"""
        if node_id not in self._nodes:
            return False

        with self._lock:
            self._nodes[node_id].update(updates)
            self._nodes[node_id]["updated_at"] = time.time()
            self._save_nodes()

        return True

    def delete_node(self, node_id: str) -> bool:
        """删除节点（标记删除）"""
        if node_id not in self._nodes:
            return False

        with self._lock:
            self._nodes[node_id]["is_deleted"] = True
            self._nodes[node_id]["deleted_at"] = time.time()
            self._save_nodes()

        return True

    # ========== 边操作 ==========

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        properties: Dict[str, Any] = None,
        created_by: str = "system"
    ) -> Optional[GraphEdge]:
        """
        添加边

        Args:
            source_id: 源节点ID
            target_id: 目标节点ID
            relation: 关系类型
            properties: 关系属性
            created_by: 创建者

        Returns:
            创建的边
        """
        # 验证节点存在
        if source_id not in self._nodes or target_id not in self._nodes:
            return None

        edge = GraphEdge(
            edge_id=str(uuid.uuid4())[:12],
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            properties=properties or {},
            created_by=created_by
        )

        with self._lock:
            self._add_edge_to_index(edge)
            self._save_edge(edge)

        return edge

    def get_edges(
        self,
        node_id: str,
        direction: str = "both"  # outgoing / incoming / both
    ) -> List[Tuple[str, GraphEdge]]:
        """
        获取节点的所有边

        Args:
            node_id: 节点ID
            direction: 方向 (outgoing/incoming/both)

        Returns:
            [(关联节点ID, 边)]
        """
        results = []

        if direction in ["outgoing", "both"]:
            for target_id, edge_id in self._outgoing.get(node_id, []):
                edge = self._get_edge_by_id(edge_id)
                if edge:
                    results.append((target_id, edge))

        if direction in ["incoming", "both"]:
            for source_id, edge_id in self._incoming.get(node_id, []):
                edge = self._get_edge_by_id(edge_id)
                if edge:
                    results.append((source_id, edge))

        return results

    def _get_edge_by_id(self, edge_id: str) -> Optional[GraphEdge]:
        """根据ID获取边"""
        for edge in self._edges:
            if edge.edge_id == edge_id:
                return edge
        return None

    # ========== 溯源查询 ==========

    def trace_provenance(
        self,
        node_id: str,
        max_depth: int = 10,
        relation_types: List[RelationType] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        溯源查询 - 追踪到源头

        使用 BFS 从当前节点向上追溯到源头

        Returns:
            所有溯源路径列表
        """
        if node_id not in self._nodes:
            return []

        paths = []
        visited = set()

        def bfs(current_id: str, current_path: List[Dict[str, Any]], depth: int):
            if depth > max_depth:
                return

            path_key = tuple(sorted(current_path, key=lambda x: x["node_id"]))
            if path_key in visited:
                return
            visited.add(path_key)

            # 查找入边（来源）
            for source_id, edge in self.get_edges(current_id, "incoming"):
                if relation_types and edge.relation not in relation_types:
                    continue

                source_node = self._nodes.get(source_id)
                if not source_node:
                    continue

                new_step = {
                    "node_id": source_id,
                    "node_name": source_node.get("name", ""),
                    "node_type": source_node.get("node_type", ""),
                    "relation": edge.relation.value,
                    "depth": depth
                }

                new_path = current_path + [new_step]

                # 如果没有更多来源，这就是一条完整路径
                incoming_count = len(self.get_edges(source_id, "incoming"))
                if incoming_count == 0:
                    paths.append(new_path)
                else:
                    bfs(source_id, new_path, depth + 1)

        # 从当前节点开始
        current_node = self._nodes[node_id]
        initial_path = [{
            "node_id": node_id,
            "node_name": current_node.get("name", ""),
            "node_type": current_node.get("node_type", ""),
            "relation": "",
            "depth": 0
        }]

        bfs(node_id, initial_path, 1)

        return paths

    def trace_derivation(
        self,
        node_id: str,
        max_depth: int = 10
    ) -> List[List[Dict[str, Any]]]:
        """
        追踪派生 - 从源头到当前节点

        Returns:
            所有派生路径列表
        """
        if node_id not in self._nodes:
            return []

        paths = []
        visited = set()

        def bfs(current_id: str, current_path: List[Dict[str, Any]], depth: int):
            if depth > max_depth:
                return

            path_key = tuple(sorted(current_path, key=lambda x: x["node_id"]))
            if path_key in visited:
                return
            visited.add(path_key)

            # 查找出边（派生）
            for target_id, edge in self.get_edges(current_id, "outgoing"):
                if edge.relation != RelationType.DERIVED_FROM:
                    continue

                target_node = self._nodes.get(target_id)
                if not target_node:
                    continue

                new_step = {
                    "node_id": target_id,
                    "node_name": target_node.get("name", ""),
                    "node_type": target_node.get("node_type", ""),
                    "relation": edge.relation.value,
                    "depth": depth
                }

                new_path = current_path + [new_step]

                # 如果没有更多出边，这就是一条完整路径
                outgoing_count = len([
                    e for e in self.get_edges(target_id, "outgoing")
                    if e[1].relation == RelationType.DERIVED_FROM
                ])
                if outgoing_count == 0:
                    paths.append(new_path)
                else:
                    bfs(target_id, new_path, depth + 1)

        # 从源头开始（找没有入边的节点）
        for path in self.trace_provenance(node_id, max_depth, relation_types=[RelationType.DERIVED_FROM]):
            # 反转路径
            paths.append(path[::-1])

        return paths

    def find_ancestors(
        self,
        node_id: str,
        relation_type: RelationType = None,
        max_depth: int = 10
    ) -> Set[str]:
        """
        查找所有祖先节点

        Returns:
            祖先节点ID集合
        """
        ancestors = set()

        def dfs(current_id: str, depth: int):
            if depth > max_depth:
                return

            for source_id, edge in self.get_edges(current_id, "incoming"):
                if relation_type and edge.relation != relation_type:
                    continue

                ancestors.add(source_id)
                dfs(source_id, depth + 1)

        dfs(node_id, 0)
        return ancestors

    def find_descendants(
        self,
        node_id: str,
        relation_type: RelationType = None,
        max_depth: int = 10
    ) -> Set[str]:
        """
        查找所有后代节点

        Returns:
            后代节点ID集合
        """
        descendants = set()

        def dfs(current_id: str, depth: int):
            if depth > max_depth:
                return

            for target_id, edge in self.get_edges(current_id, "outgoing"):
                if relation_type and edge.relation != relation_type:
                    continue

                descendants.add(target_id)
                dfs(target_id, depth + 1)

        dfs(node_id, 0)
        return descendants

    # ========== 血缘分析 ==========

    def find_common_ancestor(
        self,
        node_id1: str,
        node_id2: str
    ) -> Optional[str]:
        """
        查找两个节点的最近公共祖先

        Returns:
            公共祖先节点ID
        """
        ancestors1 = self.find_ancestors(node_id1)
        ancestors2 = self.find_ancestors(node_id2)

        common = ancestors1 & ancestors2
        if not common:
            return None

        # 返回深度最小的（最近的）
        min_depth = float('inf')
        result = None

        for ancestor_id in common:
            paths = self.trace_provenance(node_id1)
            for path in paths:
                for step in path:
                    if step["node_id"] == ancestor_id:
                        if step["depth"] < min_depth:
                            min_depth = step["depth"]
                            result = ancestor_id

        return result

    def calculate_lineage_score(
        self,
        source_id: str,
        target_id: str
    ) -> float:
        """
        计算血缘紧密度分数

        考虑因素：
        - 路径长度
        - 中间节点数量
        - 关系类型权重

        Returns:
            分数 0-1
        """
        paths = self.trace_provenance(target_id)
        if not paths:
            return 0.0

        best_score = 0.0

        for path in paths:
            # 检查路径是否包含源节点
            source_in_path = any(step["node_id"] == source_id for step in path)
            if not source_in_path:
                continue

            # 计算路径分数
            depth = len(path)
            depth_factor = 1.0 / (1 + depth * 0.2)  # 越深分数越低

            # 关系类型权重
            relation_weights = {
                RelationType.DERIVED_FROM: 1.0,
                RelationType.SOURCE_OF: 0.9,
                RelationType.INPUT_OF: 0.8,
                RelationType.PART_OF: 0.7,
            }

            avg_relation_weight = 0.0
            for step in path:
                if step.get("relation"):
                    try:
                        rel = RelationType(step["relation"])
                        avg_relation_weight += relation_weights.get(rel, 0.5)
                    except ValueError:
                        avg_relation_weight += 0.5

            avg_relation_weight /= max(len(path), 1)

            score = depth_factor * avg_relation_weight
            best_score = max(best_score, score)

        return best_score

    # ========== 查询 ==========

    def query_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """按类型查询节点"""
        node_ids = self._node_type_index.get(node_type, set())
        return [self._nodes[nid] for nid in node_ids if nid in self._nodes]

    def query_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """按标签查询节点"""
        node_ids = self._tag_index.get(tag, set())
        return [self._nodes[nid] for nid in node_ids if nid in self._nodes]

    def query_neighbors(
        self,
        node_id: str,
        relation_type: RelationType = None,
        direction: str = "both"
    ) -> List[Dict[str, Any]]:
        """
        查询邻居节点

        Args:
            node_id: 节点ID
            relation_type: 关系类型过滤
            direction: 方向

        Returns:
            邻居节点列表
        """
        neighbors = []

        for neighbor_id, edge in self.get_edges(node_id, direction):
            if relation_type and edge.relation != relation_type:
                continue

            neighbor_node = self._nodes.get(neighbor_id)
            if neighbor_node:
                neighbors.append({
                    **neighbor_node,
                    "relation": edge.relation.value,
                    "relation_display": edge.display_text
                })

        return neighbors

    # ========== 统计 ==========

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "nodes_by_type": {
                ntype: len(node_ids)
                for ntype, node_ids in self._node_type_index.items()
            },
            "top_tags": sorted(
                [(tag, len(node_ids)) for tag, node_ids in self._tag_index.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }

    # ========== 导出 ==========

    def export_subgraph(
        self,
        node_ids: List[str],
        filepath: str = None
    ) -> str:
        """
        导出子图

        Args:
            node_ids: 节点ID列表
            filepath: 导出文件路径

        Returns:
            导出文件路径
        """
        if filepath is None:
            filepath = str(self.storage_path / f"subgraph_{int(time.time())}.json")

        node_set = set(node_ids)

        # 收集子图中的所有节点
        subgraph_nodes = {}
        for node_id in node_ids:
            if node_id in self._nodes:
                subgraph_nodes[node_id] = self._nodes[node_id]

        # 收集子图中的边
        subgraph_edges = []
        for edge in self._edges:
            if edge.source_id in node_set and edge.target_id in node_set:
                subgraph_edges.append({
                    "edge_id": edge.edge_id,
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "relation": edge.relation.value,
                    "properties": edge.properties
                })

        data = {
            "nodes": subgraph_nodes,
            "edges": subgraph_edges,
            "exported_at": time.time()
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return filepath

    def import_graph(self, filepath: str, merge: bool = True):
        """
        导入图数据

        Args:
            filepath: 导入文件路径
            merge: 是否合并（True追加，False替换）
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not merge:
            # 清空现有数据
            self._nodes.clear()
            self._edges.clear()
            self._outgoing.clear()
            self._incoming.clear()
            self._node_type_index.clear()
            self._tag_index.clear()

        # 导入节点
        for node_id, node_data in data.get("nodes", {}).items():
            self._add_node_to_index(node_id, node_data)

        # 导入边
        for edge_data in data.get("edges", []):
            edge = GraphEdge(
                edge_id=edge_data["edge_id"],
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                relation=RelationType(edge_data["relation"]),
                properties=edge_data.get("properties", {})
            )
            self._add_edge_to_index(edge)

        self._save_nodes()
