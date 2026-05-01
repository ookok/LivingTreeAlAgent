"""
代码分析器 - 理解代码结构和依赖关系
"""

import ast
import os
import hashlib
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path

@dataclass
class CodeEntity:
    """代码实体"""
    id: str
    type: str  # function, class, method, variable, import
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    parent_id: Optional[str] = None
    dependencies: List[str] = None
    decorators: List[str] = None

@dataclass
class CodeRelation:
    """代码关系"""
    source_id: str
    target_id: str
    relation_type: str  # calls, imports, inherits, uses
    line_number: int

@dataclass
class FileStructure:
    """文件结构"""
    file_path: str
    functions: List[CodeEntity]
    classes: List[CodeEntity]
    imports: List[CodeEntity]
    dependencies: List[str]

class CodeAnalyzer:
    """代码分析器"""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.entities: Dict[str, CodeEntity] = {}
        self.relations: List[CodeRelation] = []
        self.file_structures: Dict[str, FileStructure] = {}
        self.entity_by_name: Dict[str, List[CodeEntity]] = {}
    
    def analyze_project(self):
        """分析整个项目"""
        self.entities.clear()
        self.relations.clear()
        self.file_structures.clear()
        
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'venv']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    self.analyze_file(file_path)
        
        self._build_relations()
    
    def analyze_file(self, file_path: str):
        """分析单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            entities, imports = self._parse_ast(tree, file_path, content)
            
            for entity in entities:
                self.entities[entity.id] = entity
                self._index_by_name(entity)
            
            file_structure = FileStructure(
                file_path=file_path,
                functions=[e for e in entities if e.type == 'function'],
                classes=[e for e in entities if e.type == 'class'],
                imports=imports,
                dependencies=[imp.name for imp in imports]
            )
            self.file_structures[file_path] = file_structure
            
        except Exception as e:
            print(f"分析文件失败 {file_path}: {e}")
    
    def _parse_ast(self, tree, file_path: str, content: str) -> Tuple[List[CodeEntity], List[CodeEntity]]:
        """解析AST"""
        entities = []
        imports = []
        lines = content.split('\n')
        class_stack = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                parent_id = class_stack[-1].id if class_stack else None
                entity = CodeEntity(
                    id=self._generate_id(file_path, node.lineno),
                    type='function' if not class_stack else 'method',
                    name=node.name,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno,
                    docstring=ast.get_docstring(node),
                    parent_id=parent_id,
                    dependencies=self._extract_dependencies(node),
                    decorators=[d.id for d in node.decorator_list if isinstance(d, ast.Name)]
                )
                entities.append(entity)
            
            elif isinstance(node, ast.ClassDef):
                entity = CodeEntity(
                    id=self._generate_id(file_path, node.lineno),
                    type='class',
                    name=node.name,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno,
                    docstring=ast.get_docstring(node),
                    dependencies=self._extract_base_classes(node)
                )
                entities.append(entity)
                class_stack.append(entity)
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imp_entity = CodeEntity(
                        id=self._generate_id(file_path, node.lineno),
                        type='import',
                        name=alias.name,
                        file_path=file_path,
                        line_start=node.lineno,
                        line_end=node.lineno
                    )
                    imports.append(imp_entity)
            
            elif isinstance(node, ast.ClassDef):
                if class_stack and class_stack[-1].name == node.name:
                    class_stack.pop()
        
        return entities, imports
    
    def _generate_id(self, file_path: str, line: int) -> str:
        """生成唯一ID"""
        return hashlib.md5(f"{file_path}:{line}".encode()).hexdigest()
    
    def _extract_dependencies(self, node) -> List[str]:
        """提取依赖"""
        deps = []
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                deps.append(child.id)
            elif isinstance(child, ast.Attribute):
                deps.append(child.attr)
        return list(set(deps))
    
    def _extract_base_classes(self, node: ast.ClassDef) -> List[str]:
        """提取基类"""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        return bases
    
    def _index_by_name(self, entity: CodeEntity):
        """按名称索引"""
        if entity.name not in self.entity_by_name:
            self.entity_by_name[entity.name] = []
        self.entity_by_name[entity.name].append(entity)
    
    def _build_relations(self):
        """构建实体关系"""
        for entity in self.entities.values():
            if entity.dependencies:
                for dep_name in entity.dependencies:
                    if dep_name in self.entity_by_name:
                        for target_entity in self.entity_by_name[dep_name]:
                            if target_entity.file_path != entity.file_path:
                                self.relations.append(CodeRelation(
                                    source_id=entity.id,
                                    target_id=target_entity.id,
                                    relation_type='uses',
                                    line_number=entity.line_start
                                ))
    
    def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        """获取实体"""
        return self.entities.get(entity_id)
    
    def find_by_name(self, name: str) -> List[CodeEntity]:
        """按名称查找实体"""
        return self.entity_by_name.get(name, [])
    
    def get_file_structure(self, file_path: str) -> Optional[FileStructure]:
        """获取文件结构"""
        return self.file_structures.get(file_path)
    
    def get_related_entities(self, entity_id: str) -> List[CodeEntity]:
        """获取相关实体"""
        related_ids = set()
        
        for relation in self.relations:
            if relation.source_id == entity_id:
                related_ids.add(relation.target_id)
            elif relation.target_id == entity_id:
                related_ids.add(relation.source_id)
        
        return [self.entities[eid] for eid in related_ids if eid in self.entities]
    
    def get_dependency_graph(self, file_path: str) -> Dict[str, Any]:
        """获取依赖图"""
        structure = self.get_file_structure(file_path)
        if not structure:
            return {}
        
        graph = {
            'file': file_path,
            'imports': [imp.name for imp in structure.imports],
            'exports': [],
            'internal_deps': []
        }
        
        for func in structure.functions:
            graph['exports'].append(func.name)
            if func.dependencies:
                graph['internal_deps'].extend(func.dependencies)
        
        for cls in structure.classes:
            graph['exports'].append(cls.name)
            if cls.dependencies:
                graph['internal_deps'].extend(cls.dependencies)
        
        graph['internal_deps'] = list(set(graph['internal_deps']))
        return graph
    
    def get_project_overview(self) -> Dict[str, Any]:
        """获取项目概览"""
        stats = {
            'total_files': len(self.file_structures),
            'total_functions': 0,
            'total_classes': 0,
            'total_entities': len(self.entities),
            'total_relations': len(self.relations),
            'entity_types': {}
        }
        
        for entity in self.entities.values():
            stats['entity_types'][entity.type] = stats['entity_types'].get(entity.type, 0) + 1
            if entity.type in ('function', 'method'):
                stats['total_functions'] += 1
            elif entity.type == 'class':
                stats['total_classes'] += 1
        
        return stats