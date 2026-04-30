"""
🕸️ 格式图谱 - Format Graph

一种表示文档格式结构的图模型：

FormatGraph:
  nodes:
    - id: "style_heading1"
      type: "paragraph_style"
      properties: {...}
    - id: "para_001"
      type: "paragraph"
      style_ref: "style_heading1"
      explicit_formats: {...}

  edges:
    - from: "style_normal"
      to: "style_heading1"
      relation: "based_on"  # 样式继承
    - from: "para_001"
      to: "text_001"
      relation: "contains"  # 包含关系

优势：
- 可视化格式继承和覆盖关系
- 支持格式相似性计算
- 便于格式的智能分析和推理
"""

import uuid
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


# ===== 关系类型 =====

class FormatRelation(Enum):
    """格式关系类型"""
    BASED_ON = "based_on"           # 样式继承
    CONTAINS = "contains"           # 包含关系
    APPLIED_TO = "applied_to"       # 样式应用
    OVERRIDES = "overrides"         # 格式覆盖
    REFERENCES = "references"       # 交叉引用
    LINKED_TO = "linked_to"        # 链接关系
    SIBLING_OF = "sibling_of"      # 同级关系


class NodeType(Enum):
    """节点类型"""
    # 样式节点
    PARAGRAPH_STYLE = "paragraph_style"
    CHARACTER_STYLE = "character_style"
    TABLE_STYLE = "table_style"

    # 元素节点
    PARAGRAPH = "paragraph"
    TEXT_RUN = "text_run"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    IMAGE = "image"
    SHAPE = "shape"

    # 格式属性节点
    FONT_PROPERTY = "font_property"
    PARAGRAPH_PROPERTY = "paragraph_property"
    PAGE_PROPERTY = "page_property"

    # 语义节点
    HEADING_NODE = "heading"
    LIST_NODE = "list"
    QUOTE_NODE = "quote"


# ===== 数据类 =====

@dataclass
class FormatNode:
    """
    格式图谱节点

    表示文档中的一个格式实体：
    - 样式定义
    - 文档元素
    - 格式属性
    """
    node_id: str
    node_type: NodeType
    label: str = ""

    # 属性
    properties: Dict[str, Any] = field(default_factory=dict)

    # 样式引用
    style_ref: str = ""           # 引用的样式ID
    explicit_properties: Dict[str, Any] = field(default_factory=dict)  # 显式格式
    inherited_properties: Dict[str, Any] = field(default_factory=dict)  # 继承格式

    # 位置信息
    position: int = 0             # 在父容器中的位置
    depth: int = 0                # 树深度

    # 元数据
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.node_id,
            "type": self.node_type.value,
            "label": self.label,
            "style_ref": self.style_ref,
            "properties": self.properties,
            "explicit": self.explicit_properties,
            "inherited": self.inherited_properties,
            "depth": self.depth,
            "metadata": self.metadata,
        }


@dataclass
class FormatEdge:
    """格式图谱边"""
    from_node: str
    to_node: str
    relation: FormatRelation

    # 额外信息
    properties: Dict = field(default_factory=dict)
    weight: float = 1.0  # 用于相似度计算

    def to_dict(self) -> dict:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "relation": self.relation.value,
            "weight": self.weight,
        }


class FormatGraph:
    """
    格式图谱

    用图模型表示文档的完整格式结构：

    节点表示：
    - 样式 (Style nodes)
    - 元素 (Element nodes)
    - 属性 (Property nodes)

    边表示：
    - 继承 (based_on)
    - 包含 (contains)
    - 应用 (applied_to)
    - 覆盖 (overrides)
    """

    def __init__(self, document_id: str = ""):
        self.document_id = document_id or str(uuid.uuid4())[:8]

        # 节点存储
        self.nodes: Dict[str, FormatNode] = {}

        # 边存储
        self.edges: List[FormatEdge] = []

        # 索引
        self._node_index: Dict[str, Set[str]] = defaultdict(set)  # type -> node_ids
        self._style_elements: Dict[str, List[str]] = defaultdict(list)  # style -> element_ids
        self._parent_children: Dict[str, List[str]] = defaultdict(list)  # parent -> children

        # 统计
        self.stats = {
            "total_nodes": 0,
            "total_edges": 0,
            "styles": 0,
            "elements": 0,
        }

    # ===== 节点操作 =====

    def add_node(self, node: FormatNode) -> str:
        """添加节点"""
        if node.node_id in self.nodes:
            logger.warning(f"节点已存在: {node.node_id}")
            return node.node_id

        self.nodes[node.node_id] = node
        self._node_index[node.node_type.value].add(node.node_id)

        if node.node_type in [NodeType.PARAGRAPH_STYLE, NodeType.CHARACTER_STYLE, NodeType.TABLE_STYLE]:
            self.stats["styles"] += 1
        else:
            self.stats["elements"] += 1

        self.stats["total_nodes"] = len(self.nodes)
        return node.node_id

    def get_node(self, node_id: str) -> Optional[FormatNode]:
        """获取节点"""
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[FormatNode]:
        """按类型获取节点"""
        node_ids = self._node_index.get(node_type.value, set())
        return [self.nodes[nid] for nid in node_ids]

    def update_node(self, node_id: str, properties: Dict[str, Any]):
        """更新节点属性"""
        if node_id in self.nodes:
            self.nodes[node_id].properties.update(properties)

    # ===== 边操作 =====

    def add_edge(self, from_id: str, to_id: str, relation: FormatRelation,
                 properties: Dict = None, weight: float = 1.0) -> bool:
        """添加边"""
        if from_id not in self.nodes:
            logger.warning(f"源节点不存在: {from_id}")
            return False
        if to_id not in self.nodes:
            logger.warning(f"目标节点不存在: {to_id}")
            return False

        edge = FormatEdge(
            from_node=from_id,
            to_node=to_id,
            relation=relation,
            properties=properties or {},
            weight=weight,
        )
        self.edges.append(edge)

        # 更新索引
        if relation == FormatRelation.APPLIED_TO:
            self._style_elements[from_id].append(to_id)
        if relation == FormatRelation.CONTAINS:
            self._parent_children[from_id].append(to_id)

        self.stats["total_edges"] = len(self.edges)
        return True

    def get_outgoing_edges(self, node_id: str) -> List[FormatEdge]:
        """获取出边"""
        return [e for e in self.edges if e.from_node == node_id]

    def get_incoming_edges(self, node_id: str) -> List[FormatEdge]:
        """获取入边"""
        return [e for e in self.edges if e.to_node == node_id]

    def get_elements_by_style(self, style_id: str) -> List[str]:
        """获取应用某样式的元素"""
        return self._style_elements.get(style_id, [])

    def get_children(self, parent_id: str) -> List[str]:
        """获取子元素"""
        return self._parent_children.get(parent_id, [])

    # ===== 格式分析 =====

    def get_style_inheritance_chain(self, style_id: str) -> List[str]:
        """
        获取样式继承链

        例如: heading1 -> based_on -> heading2 -> based_on -> normal
        返回: ["heading1", "heading2", "normal"]
        """
        chain = [style_id]
        current = style_id

        visited = set()
        while current not in visited:
            visited.add(current)
            node = self.get_node(current)
            if not node:
                break

            # 查找 based_on 边
            for edge in self.get_outgoing_edges(current):
                if edge.relation == FormatRelation.BASED_ON:
                    current = edge.to_node
                    chain.append(current)
                    break
            else:
                break

        return chain

    def compute_effective_format(self, element_id: str) -> Dict[str, Any]:
        """
        计算元素的有效格式

        考虑样式继承 + 显式覆盖
        """
        node = self.get_node(element_id)
        if not node:
            return {}

        effective = {}

        # 1. 从样式继承
        if node.style_ref:
            chain = self.get_style_inheritance_chain(node.style_ref)
            # 从链的末端开始合并（normal 基础样式）
            for style_id in reversed(chain):
                style_node = self.get_node(style_id)
                if style_node:
                    effective.update(style_node.properties)

        # 2. 继承格式
        effective.update(node.inherited_properties)

        # 3. 显式格式覆盖
        effective.update(node.explicit_properties)

        return effective

    def find_format_conflicts(self) -> List[Dict]:
        """
        检测格式冲突

        返回冲突列表，每项包含:
        - element_id
        - conflict_type
        - details
        """
        conflicts = []

        for node in self.nodes.values():
            if node.node_type not in [NodeType.PARAGRAPH, NodeType.TEXT_RUN]:
                continue

            explicit = node.explicit_properties
            inherited = node.inherited_properties

            # 检测矛盾的对齐方式
            if "alignment" in explicit and "alignment" in inherited:
                if explicit["alignment"] != inherited["alignment"]:
                    conflicts.append({
                        "element_id": node.node_id,
                        "conflict_type": "alignment_override",
                        "inherited": inherited["alignment"],
                        "explicit": explicit["alignment"],
                        "message": f"元素 {node.node_id} 覆盖了对齐方式",
                    })

            # 检测父子段落的格式不一致
            children = self.get_children(node.node_id)
            if children:
                child_alignments = []
                for child_id in children:
                    child = self.get_node(child_id)
                    if child and "alignment" in child.explicit_properties:
                        child_alignments.append(child.explicit_properties["alignment"])

                if len(set(child_alignments)) > 1:
                    conflicts.append({
                        "element_id": node.node_id,
                        "conflict_type": "sibling_inconsistency",
                        "details": child_alignments,
                        "message": f"同级元素格式不一致",
                    })

        return conflicts

    def compute_format_similarity(self, node_id1: str, node_id2: str) -> float:
        """
        计算两个节点的格式相似度

        返回 0-1 之间的相似度分数
        """
        node1 = self.get_node(node_id1)
        node2 = self.get_node(node_id2)

        if not node1 or not node2:
            return 0.0

        # 获取有效格式
        fmt1 = self.compute_effective_format(node_id1)
        fmt2 = self.compute_effective_format(node_id2)

        if not fmt1 and not fmt2:
            return 1.0
        if not fmt1 or not fmt2:
            return 0.0

        # 计算共同属性
        common_keys = set(fmt1.keys()) & set(fmt2.keys())
        if not common_keys:
            return 0.0

        matches = 0
        for key in common_keys:
            if fmt1[key] == fmt2[key]:
                matches += 1

        return matches / max(len(fmt1), len(fmt2), 1)

    def group_similar_elements(self, threshold: float = 0.8) -> List[List[str]]:
        """
        将相似格式的元素分组

        用于检测格式不一致问题
        """
        elements = [n.node_id for n in self.nodes.values()
                   if n.node_type in [NodeType.PARAGRAPH, NodeType.TEXT_RUN]]

        groups = []
        assigned = set()

        for i, elem1 in enumerate(elements):
            if elem1 in assigned:
                continue

            group = [elem1]
            for elem2 in elements[i+1:]:
                if elem2 in assigned:
                    continue
                if self.compute_format_similarity(elem1, elem2) >= threshold:
                    group.append(elem2)
                    assigned.add(elem2)

            groups.append(group)
            assigned.add(elem1)

        return groups

    # ===== 遍历方法 =====

    def traverse_depth_first(self, start_id: str,
                           relation_filter: FormatRelation = None) -> List[str]:
        """深度优先遍历"""
        result = []
        visited = set()

        def _traverse(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            result.append(node_id)

            for edge in self.get_outgoing_edges(node_id):
                if relation_filter and edge.relation != relation_filter:
                    continue
                _traverse(edge.to_node)

        _traverse(start_id)
        return result

    def get_subgraph(self, root_id: str, max_depth: int = 3) -> 'FormatGraph':
        """提取子图"""
        subgraph = FormatGraph(f"{self.document_id}_subgraph")

        visited = set()
        nodes_to_add = [(root_id, 0)]

        while nodes_to_add:
            node_id, depth = nodes_to_add.pop(0)
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)

            node = self.get_node(node_id)
            if node:
                subgraph.add_node(node)

                for edge in self.get_outgoing_edges(node_id):
                    subgraph.add_edge(edge.from_node, edge.to_node, edge.relation)
                    nodes_to_add.append((edge.to_node, depth + 1))

        return subgraph

    # ===== 导出方法 =====

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "document_id": self.document_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "stats": self.stats,
        }

    def to_graphviz(self) -> str:
        """导出为 Graphviz DOT 格式"""
        lines = ["digraph {"]
        lines.append(f'  label="{self.document_id}";')

        # 节点
        for node in self.nodes.values():
            node_type = node.node_type.value
            color = {
                "paragraph_style": "blue",
                "character_style": "cyan",
                "paragraph": "green",
                "text_run": "lightgreen",
                "table": "orange",
                "heading": "red",
            }.get(node_type, "gray")

            label = node.label[:20] if node.label else node.node_id
            lines.append(f'  "{node.node_id}" [label="{label}", color={color}];')

        # 边
        for edge in self.edges:
            relation = edge.relation.value
            style = "dashed" if relation == "based_on" else "solid"
            lines.append(f'  "{edge.from_node}" -> "{edge.to_node}" [label="{relation}", style={style}];')

        lines.append("}")
        return "\n".join(lines)

    # ===== 构建辅助 =====

    def build_from_elements(self, elements: List, styles: Dict):
        """从格式元素列表构建图谱"""
        # 添加样式节点
        for style_id, style_info in styles.items():
            style_node = FormatNode(
                node_id=style_id,
                node_type=NodeType.PARAGRAPH_STYLE,
                label=style_info.get("name", style_id),
                properties=style_info.get("properties", {}),
            )
            self.add_node(style_node)

            # 添加 based_on 边
            based_on = style_info.get("based_on")
            if based_on:
                self.add_edge(style_id, based_on, FormatRelation.BASED_ON)

        # 添加元素节点
        for i, elem in enumerate(elements):
            node_type = self._element_type_to_node_type(elem.element_type)

            element_node = FormatNode(
                node_id=elem.element_id,
                node_type=node_type,
                label=elem.text_content[:50] if elem.text_content else "",
                style_ref=elem.structural.style_id,
                explicit_properties=self._extract_explicit_formats(elem),
                inherited_properties={},
                position=i,
                depth=0,
            )
            self.add_node(element_node)

            # 添加应用的样式边
            if elem.structural.style_id:
                self.add_edge(
                    elem.structural.style_id,
                    elem.element_id,
                    FormatRelation.APPLIED_TO
                )

    @staticmethod
    def _element_type_to_node_type(elem_type) -> NodeType:
        """元素类型转换"""
        from business.office_automation.format_understanding.format_parser import ElementType

        mapping = {
            ElementType.PARAGRAPH: NodeType.PARAGRAPH,
            ElementType.TEXT_RUN: NodeType.TEXT_RUN,
            ElementType.TABLE: NodeType.TABLE,
            ElementType.TABLE_ROW: NodeType.TABLE_ROW,
            ElementType.TABLE_CELL: NodeType.TABLE_CELL,
            ElementType.IMAGE: NodeType.IMAGE,
            ElementType.SHAPE: NodeType.SHAPE,
        }
        return mapping.get(elem_type, NodeType.PARAGRAPH)

    @staticmethod
    def _extract_explicit_formats(elem) -> Dict:
        """提取显式格式"""
        explicit = {}

        # 视觉格式
        v = elem.visual
        if v.font_name:
            explicit["font_name"] = v.font_name
        if v.font_size:
            explicit["font_size"] = v.font_size
        if v.font_color:
            explicit["font_color"] = v.font_color
        if v.font_bold:
            explicit["font_bold"] = True
        if v.font_italic:
            explicit["font_italic"] = True
        if v.alignment != "left":
            explicit["alignment"] = v.alignment

        return explicit
