"""
知识图谱构建器
从代码库中提取实体和关系，构建知识图谱
"""

import ast
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """实体"""
    id: str
    type: str  # 'class', 'function', 'module', 'variable', 'concept'
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[List[float]] = None


@dataclass
class Relation:
    """关系"""
    source_id: str
    target_id: str
    type: str  # 'calls', 'inherits', 'imports', 'uses', 'depends_on', 'similar_to'
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeGraph:
    """知识图谱"""
    entities: Dict[str, Entity] = field(default_factory=dict)
    relations: List[Relation] = field(default_factory=list)

    def add_entity(self, entity: Entity):
        """添加实体"""
        self.entities[entity.id] = entity

    def add_relation(self, relation: Relation):
        """添加关系"""
        self.relations.append(relation)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(entity_id)

    def get_relations(self, entity_id: str, relation_type: Optional[str] = None) -> List[Relation]:
        """获取实体的关系"""
        result = []
        for rel in self.relations:
            if rel.source_id == entity_id or rel.target_id == entity_id:
                if relation_type is None or rel.type == relation_type:
                    result.append(rel)
        return result

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'entities': {k: vars(v) for k, v in self.entities.items()},
            'relations': [vars(r) for r in self.relations],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'KnowledgeGraph':
        """从字典加载"""
        kg = cls()
        for entity_id, entity_data in data['entities'].items():
            entity = Entity(**entity_data)
            kg.entities[entity_id] = entity

        for rel_data in data['relations']:
            rel = Relation(**rel_data)
            kg.relations.append(rel)

        return kg


class CodeParser:
    """代码解析器"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []

    def parse_repository(self) -> KnowledgeGraph:
        """解析整个仓库"""
        kg = KnowledgeGraph()

        # 1. 解析所有 Python 文件
        python_files = list(self.repo_path.rglob("*.py"))
        logger.info(f"发现 {len(python_files)} 个 Python 文件")

        for py_file in python_files:
            try:
                self._parse_file(py_file)
            except Exception as e:
                logger.error(f"解析文件失败 {py_file}: {e}")

        # 2. 添加到知识图谱
        for entity in self.entities.values():
            kg.add_entity(entity)

        for relation in self.relations:
            kg.add_relation(relation)

        # 3. 添加概念实体（从文档中提取）
        self._extract_concepts(kg)

        logger.info(f"知识图谱构建完成: {len(kg.entities)} 个实体, {len(kg.relations)} 个关系")
        return kg

    def _parse_file(self, file_path: Path):
        """解析单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            # 创建模块实体
            module_id = str(file_path.relative_to(self.repo_path))
            module_entity = Entity(
                id=module_id,
                type='module',
                name=file_path.stem,
                properties={
                    'path': str(file_path),
                    'size': len(content),
                    'lines': len(content.splitlines()),
                }
            )
            self.entities[module_id] = module_entity

            # 解析 AST
            self._parse_ast(tree, module_id, file_path)

        except SyntaxError as e:
            logger.warning(f"语法错误 {file_path}: {e}")
        except Exception as e:
            logger.error(f"解析错误 {file_path}: {e}")

    def _parse_ast(self, tree: ast.AST, module_id: str, file_path: Path):
        """解析 AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._parse_class(node, module_id)
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                self._parse_function(node, module_id)
            elif isinstance(node, ast.Import):
                self._parse_import(node, module_id)
            elif isinstance(node, ast.ImportFrom):
                self._parse_import_from(node, module_id)

    def _parse_class(self, node: ast.ClassDef, module_id: str):
        """解析类"""
        class_id = f"{module_id}::{node.name}"

        # 创建类实体
        class_entity = Entity(
            id=class_id,
            type='class',
            name=node.name,
            properties={
                'module': module_id,
                'lineno': node.lineno,
                'bases': [ast.dump(b) for b in node.bases],
            }
        )
        self.entities[class_id] = class_entity

        # 添加继承关系
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_id = f"{module_id}::{base.id}"
                if base_id in self.entities:
                    rel = Relation(
                        source_id=class_id,
                        target_id=base_id,
                        type='inherits',
                        weight=1.0
                    )
                    self.relations.append(rel)

        # 解析类中的方法
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._parse_method(item, module_id, class_id)

    def _parse_function(self, node: ast.FunctionDef, module_id: str):
        """解析函数"""
        func_id = f"{module_id}::{node.name}"

        # 创建函数实体
        func_entity = Entity(
            id=func_id,
            type='function',
            name=node.name,
            properties={
                'module': module_id,
                'lineno': node.lineno,
                'is_async': isinstance(node, ast.AsyncFunctionDef),
                'args': [a.arg for a in node.args.args],
            }
        )
        self.entities[func_id] = func_entity

        # 解析函数调用
        self._parse_function_calls(node, func_id)

    def _parse_method(self, node: ast.FunctionDef, module_id: str, class_id: str):
        """解析方法"""
        method_id = f"{class_id}::{node.name}"

        # 创建方法实体
        method_entity = Entity(
            id=method_id,
            type='function',
            name=node.name,
            properties={
                'module': module_id,
                'class': class_id,
                'lineno': node.lineno,
            }
        )
        self.entities[method_id] = method_entity

    def _parse_import(self, node: ast.Import, module_id: str):
        """解析 import 语句"""
        for alias in node.names:
            import_id = f"import::{alias.name}"

            # 创建导入实体（如果不存在）
            if import_id not in self.entities:
                import_entity = Entity(
                    id=import_id,
                    type='module',
                    name=alias.name,
                    properties={'is_external': True}
                )
                self.entities[import_id] = import_entity

            # 添加导入关系
            rel = Relation(
                source_id=module_id,
                target_id=import_id,
                type='imports',
                weight=1.0
            )
            self.relations.append(rel)

    def _parse_import_from(self, node: ast.ImportFrom, module_id: str):
        """解析 from ... import 语句"""
        if node.module:
            import_id = f"import::{node.module}"

            # 创建导入实体（如果不存在）
            if import_id not in self.entities:
                import_entity = Entity(
                    id=import_id,
                    type='module',
                    name=node.module,
                    properties={'is_external': node.module.startswith('.') is False}
                )
                self.entities[import_id] = import_entity

            # 添加导入关系
            rel = Relation(
                source_id=module_id,
                target_id=import_id,
                type='imports',
                weight=1.0
            )
            self.relations.append(rel)

    def _parse_function_calls(self, node: ast.AST, func_id: str):
        """解析函数调用"""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    # 直接调用：func()
                    callee_id = f"{func_id.split('::')[0]}::{child.func.id}"
                    if callee_id in self.entities:
                        rel = Relation(
                            source_id=func_id,
                            target_id=callee_id,
                            type='calls',
                            weight=1.0
                        )
                        self.relations.append(rel)
                elif isinstance(child.func, ast.Attribute):
                    # 方法调用：obj.method()
                    method_name = child.func.attr
                    obj_name = child.func.value.id if isinstance(child.func.value, ast.Name) else None

                    if obj_name:
                        callee_id = f"{func_id.split('::')[0]}::{obj_name}::{method_name}"
                        if callee_id in self.entities:
                            rel = Relation(
                                source_id=func_id,
                                target_id=callee_id,
                                type='calls',
                                weight=1.0
                            )
                            self.relations.append(rel)

    def _extract_concepts(self, kg: KnowledgeGraph):
        """提取概念（从文档和注释中）"""
        concept_patterns = [
            (r'(\w+)\s+(?:is a|is an)\s+(\w+)', 'is_a'),
            (r'(\w+)\s+(?:has a|has an)\s+(\w+)', 'has_a'),
            (r'(\w+)\s+(?:uses|used by)\s+(\w+)', 'uses'),
        ]

        for entity in kg.entities.values():
            if entity.type == 'module':
                file_path = entity.properties.get('path')
                if file_path:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # 提取文档字符串中的概念
                        docstring = self._extract_docstring(content)
                        if docstring:
                            for pattern, rel_type in concept_patterns:
                                matches = re.findall(pattern, docstring, re.IGNORECASE)
                                for match in matches:
                                    concept_id = f"concept::{match[1]}"
                                    if concept_id not in kg.entities:
                                        concept_entity = Entity(
                                            id=concept_id,
                                            type='concept',
                                            name=match[1],
                                            properties={'source': 'docstring'}
                                        )
                                        kg.add_entity(concept_entity)

                                    rel = Relation(
                                        source_id=entity.id,
                                        target_id=concept_id,
                                        type=rel_type,
                                        weight=0.5
                                    )
                                    kg.add_relation(rel)

                    except Exception as e:
                        logger.error(f"提取概念失败 {file_path}: {e}")

    def _extract_docstring(self, content: str) -> Optional[str]:
        """提取文档字符串"""
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                    docstring = ast.get_docstring(node)
                    if docstring:
                        return docstring
        except:
            pass
        return None


class KnowledgeGraphBuilder:
    """知识图谱构建器"""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.parser = CodeParser(repo_path)
        self.kg = None

    def build(self) -> KnowledgeGraph:
        """构建知识图谱"""
        logger.info(f"开始构建知识图谱: {self.repo_path}")
        self.kg = self.parser.parse_repository()
        return self.kg

    def save(self, path: str):
        """保存知识图谱"""
        if self.kg is None:
            raise ValueError("知识图谱尚未构建")

        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.kg.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"知识图谱已保存: {path}")

    def load(self, path: str):
        """加载知识图谱"""
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.kg = KnowledgeGraph.from_dict(data)
        logger.info(f"知识图谱已加载: {path}")
        return self.kg

    def visualize(self, output_path: str):
        """可视化知识图谱（生成 HTML）"""
        if self.kg is None:
            raise ValueError("知识图谱尚未构建")

        # 生成 D3.js 可视化
        html = self._generate_visualization_html()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"可视化已生成: {output_path}")

    def _generate_visualization_html(self) -> str:
        """生成可视化 HTML"""
        # 简化版：生成 D3.js 力导向图
        nodes = []
        edges = []

        for entity in self.kg.entities.values():
            nodes.append({
                'id': entity.id,
                'label': entity.name,
                'type': entity.type,
            })

        for rel in self.kg.relations:
            edges.append({
                'source': rel.source_id,
                'target': rel.target_id,
                'type': rel.type,
            })

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Knowledge Graph Visualization</title>
            <script src="https://d3js.org/d3.v7.min.js"></script>
            <style>
                .node {{ stroke: #fff; stroke-width: 1.5px; }}
                .link {{ stroke: #999; stroke-opacity: 0.6; }}
                .node-label {{ font-size: 12px; }}
            </style>
        </head>
        <body>
            <script>
                const nodes = {nodes};
                const edges = {edges};

                // D3.js 力导向图代码（简化）
                // ...
            </script>
        </body>
        </html>
        """

        return html
