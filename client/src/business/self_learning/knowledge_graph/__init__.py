"""
代码知识图谱 (Code Knowledge Graph)
=====================================

轻量级内存知识图谱，不依赖外部数据库。

支持:
1. 代码结构解析 (AST)
2. 实体关系建模
3. 影响范围分析
4. 相似代码查询
"""

import ast
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """知识图谱实体"""
    id: str
    type: str  # "File", "Class", "Function", "Method", "Variable"
    name: str
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "attributes": self.attributes,
        }


@dataclass
class Relation:
    """知识图谱关系"""
    type: str  # "CONTAINS", "CALLS", "INHERITS_FROM", "IMPORTS", "USES"
    source_id: str
    target_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "source": self.source_id,
            "target": self.target_id,
            "attributes": self.attributes,
        }


class CodeKnowledgeGraph:
    """
    代码知识图谱（内存版本）
    
    存储代码结构、依赖关系，支持推理和查询。
    """
    
    def __init__(self, name: str = "default"):
        """
        初始化知识图谱
        
        Args:
            name: 图谱名称
        """
        self.name = name
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []
        self._entity_index: Dict[str, List[str]] = defaultdict(list)  # type -> [entity_ids]
        self._adjacency: Dict[str, Dict[str, List[Relation]]] = defaultdict(lambda: defaultdict(list))
        
        logger.info(f"[CodeKnowledgeGraph] 初始化完成: {name}")
    
    def add_entity(self, entity: Entity) -> str:
        """
        添加实体
        
        Returns:
            实体ID
        """
        if entity.id in self.entities:
            logger.warning(f"[CodeKnowledgeGraph] 实体已存在: {entity.id}")
            return entity.id
        
        self.entities[entity.id] = entity
        self._entity_index[entity.type].append(entity.id)
        
        return entity.id
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self.entities.get(entity_id)
    
    def find_entities(self, type: str = None, name: str = None) -> List[Entity]:
        """
        查找实体
        
        Args:
            type: 实体类型过滤
            name: 实体名称过滤（部分匹配）
            
        Returns:
            实体列表
        """
        results = []
        
        for entity in self.entities.values():
            if type and entity.type != type:
                continue
            if name and name.lower() not in entity.name.lower():
                continue
            results.append(entity)
        
        return results
    
    def add_relation(self, relation: Relation):
        """添加关系"""
        self.relations.append(relation)
        
        # 更新邻接表
        self._adjacency[relation.source_id][relation.type].append(relation)
        
        logger.debug(f"[CodeKnowledgeGraph] 添加关系: {relation.source_id} -[{relation.type}]-> {relation.target_id}")
    
    def get_relations(self, entity_id: str, relation_type: str = None) -> List[Relation]:
        """
        获取实体的所有关系
        
        Args:
            entity_id: 实体ID
            relation_type: 关系类型过滤
            
        Returns:
            关系列表
        """
        if relation_type:
            return self._adjacency.get(entity_id, {}).get(relation_type, [])
        else:
            relations = []
            for rels in self._adjacency.get(entity_id, {}).values():
                relations.extend(rels)
            return relations
    
    def add_file(self, file_path: str, language: str = "python", size: int = 0) -> str:
        """
        添加文件实体
        
        Returns:
            文件实体ID
        """
        entity_id = f"file:{file_path}"
        entity = Entity(
            id=entity_id,
            type="File",
            name=os.path.basename(file_path),
            file_path=file_path,
            attributes={
                "language": language,
                "size": size,
                "last_modified": os.path.getmtime(file_path) if os.path.exists(file_path) else 0,
            }
        )
        return self.add_entity(entity)
    
    def add_class(self, class_name: str, file_path: str, start_line: int, end_line: int) -> str:
        """
        添加类实体
        
        Returns:
            类实体ID
        """
        entity_id = f"class:{class_name}@{file_path}"
        entity = Entity(
            id=entity_id,
            type="Class",
            name=class_name,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
        )
        return self.add_entity(entity)
    
    def add_function(self, func_name: str, file_path: str, start_line: int, end_line: int, return_type: str = None) -> str:
        """
        添加函数实体
        
        Returns:
            函数实体ID
        """
        entity_id = f"func:{func_name}@{file_path}:{start_line}"
        entity = Entity(
            id=entity_id,
            type="Function",
            name=func_name,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            attributes={"return_type": return_type},
        )
        return self.add_entity(entity)
    
    def add_call_relation(self, caller_id: str, callee_id: str):
        """添加函数调用关系"""
        relation = Relation(
            type="CALLS",
            source_id=caller_id,
            target_id=callee_id,
        )
        self.add_relation(relation)
    
    def add_inheritance_relation(self, child_id: str, parent_id: str):
        """添加继承关系"""
        relation = Relation(
            type="INHERITS_FROM",
            source_id=child_id,
            target_id=parent_id,
        )
        self.add_relation(relation)
    
    def add_import_relation(self, source_file_id: str, target_module: str):
        """添加导入关系"""
        relation = Relation(
            type="IMPORTS",
            source_id=source_file_id,
            target_id=f"module:{target_module}",
            attributes={"module": target_module},
        )
        self.add_relation(relation)
    
    def analyze_impact(self, modified_entity_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """
        影响范围分析（查找所有调用链）
        
        Args:
            modified_entity_id: 被修改的实体ID
            max_depth: 最大搜索深度
            
        Returns:
            受影响实体列表
        """
        visited = set()
        affected = []
        
        def dfs(entity_id: str, depth: int, path: List[str]):
            if depth > max_depth or entity_id in visited:
                return
            
            visited.add(entity_id)
            entity = self.get_entity(entity_id)
            if entity:
                affected.append({
                    "entity_id": entity_id,
                    "name": entity.name,
                    "type": entity.type,
                    "file_path": entity.file_path,
                    "depth": depth,
                    "path": path.copy(),
                })
            
            # 查找调用者（反向查找）
            for relation in self.relations:
                if relation.target_id == entity_id and relation.type == "CALLS":
                    dfs(relation.source_id, depth + 1, path + [entity_id])
        
        dfs(modified_entity_id, 0, [])
        return affected
    
    def find_similar_code(self, code_snippet: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        查找相似代码（基于结构相似度）
        
        简化版：基于函数名和调用关系
        """
        # 解析代码片段
        try:
            tree = ast.parse(code_snippet)
        except SyntaxError:
            return []
        
        # 提取函数名和调用
        snippet_funcs = set()
        snippet_calls = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                snippet_funcs.add(node.name)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    snippet_calls.add(node.func.id)
        
        # 比较图谱中的函数
        results = []
        for entity in self.entities.values():
            if entity.type != "Function":
                continue
            
            # 简单相似度：名称重叠
            score = 0.0
            if entity.name in snippet_funcs:
                score += 1.0
            
            # 查看调用关系相似度
            calls = set(r.target_id for r in self.get_relations(entity.id, "CALLS"))
            if calls & snippet_calls:
                score += 0.5
            
            if score > 0:
                results.append({
                    "entity_id": entity.id,
                    "name": entity.name,
                    "file_path": entity.file_path,
                    "similarity": score,
                })
        
        # 排序并返回 top-k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "entities": [e.to_dict() for e in self.entities.values()],
            "relations": [r.to_dict() for r in self.relations],
        }
    
    def save(self, path: str):
        """保存到文件"""
        data = self.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"[CodeKnowledgeGraph] 保存到: {path}")
    
    def load(self, path: str):
        """从文件加载"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.name = data.get("name", "default")
        
        # 加载实体
        for e_data in data.get("entities", []):
            entity = Entity(**e_data)
            self.entities[entity.id] = entity
            self._entity_index[entity.type].append(entity.id)
        
        # 加载关系
        for r_data in data.get("relations", []):
            relation = Relation(**r_data)
            self.relations.append(relation)
            self._adjacency[relation.source_id][relation.type].append(relation)
        
        logger.info(f"[CodeKnowledgeGraph] 从 {path} 加载完成，实体数: {len(self.entities)}")


class ASTParser:
    """
    AST 解析器（自动构建知识图谱）
    
    遍历 Python 代码文件，自动提取代码结构并构建知识图谱。
    """
    
    def __init__(self, kg: CodeKnowledgeGraph):
        """
        初始化解析器
        
        Args:
            kg: 知识图谱实例
        """
        self.kg = kg
        self.current_file_id = None
        logger.info("[ASTParser] 初始化完成")
    
    def parse_file(self, file_path: str) -> bool:
        """
        解析单个文件
        
        Returns:
            是否成功
        """
        self.current_file_id = None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            logger.error(f"[ASTParser] 无法读取文件 {file_path}: {e}")
            return False
        
        # 添加文件节点
        self.current_file_id = self.kg.add_file(
            file_path=file_path,
            language="python",
            size=len(code),
        )
        
        # 解析AST
        try:
            tree = ast.parse(code)
            self._visit(tree)
            logger.debug(f"[ASTParser] 解析文件完成: {file_path}")
            return True
        except SyntaxError as e:
            logger.error(f"[ASTParser] 语法错误 {file_path}: {e}")
            return False
    
    def parse_directory(self, dir_path: str, extensions: List[str] = None):
        """
        解析整个目录
        
        Args:
            dir_path: 目录路径
            extensions: 文件扩展名过滤（如 [".py"]）
        """
        if extensions is None:
            extensions = [".py"]
        
        count = 0
        for root, dirs, files in os.walk(dir_path):
            # 跳过隐藏目录和特殊目录
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    if self.parse_file(file_path):
                        count += 1
        
        logger.info(f"[ASTParser] 解析目录完成: {dir_path}, 文件数: {count}")
        return count
    
    def _visit(self, node):
        """遍历 AST"""
        if isinstance(node, ast.ClassDef):
            self._process_class(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._process_function(node)
        
        for child in ast.iter_child_nodes(node):
            self._visit(child)
    
    def _process_class(self, node: ast.ClassDef):
        """处理类定义"""
        class_id = self.kg.add_class(
            class_name=node.name,
            file_path=self.kg.get_entity(self.current_file_id).name if self.current_file_id else "",
            start_line=node.lineno,
            end_line=node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
        )
        
        # 处理继承
        for base in node.bases:
            if isinstance(base, ast.Name):
                # 简化：假设父类在同一文件
                parent_id = f"class:{base.id}@" + (
                    self.kg.get_entity(self.current_file_id).name if self.current_file_id else ""
                )
                self.kg.add_inheritance_relation(class_id, parent_id)
    
    def _process_function(self, node):
        """处理函数定义"""
        func_id = self.kg.add_function(
            func_name=node.name,
            file_path=self.kg.get_entity(self.current_file_id).name if self.current_file_id else "",
            start_line=node.lineno,
            end_line=node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
        )
        
        # 处理函数调用
        self._extract_function_calls(node, func_id)
    
    def _extract_function_calls(self, node, caller_id: str):
        """提取函数调用关系"""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    # 简单函数调用: func()
                    callee_name = child.func.id
                    # 简化：假设被调用函数也在某个地方定义
                    # 实际应该建立全局函数索引
                    callee_id = f"func:{callee_name}"  # 简化为仅函数名
                    self.kg.add_call_relation(caller_id, callee_id)
                elif isinstance(child.func, ast.Attribute):
                    # 方法调用: obj.method()
                    method_name = child.func.attr
                    callee_id = f"method:{method_name}"
                    self.kg.add_call_relation(caller_id, callee_id)


class ImpactAnalyzer:
    """
    影响范围分析器
    
    基于知识图谱，分析代码修改的影响范围。
    """
    
    def __init__(self, kg: CodeKnowledgeGraph):
        """
        初始化分析器
        
        Args:
            kg: 知识图谱实例
        """
        self.kg = kg
        logger.info("[ImpactAnalyzer] 初始化完成")
    
    def analyze_function_modification(self, function_name: str, file_path: str = None, max_depth: int = 5) -> Dict[str, Any]:
        """
        分析函数修改的影响范围
        
        Args:
            function_name: 函数名
            file_path: 文件路径（可选，用于精确匹配）
            max_depth: 最大影响深度
            
        Returns:
            分析结果
        """
        # 查找目标函数
        target_entities = self.kg.find_entities(type="Function", name=function_name)
        
        if not target_entities:
            return {
                "error": f"未找到函数: {function_name}",
                "affected_entities": [],
            }
        
        # 分析每个匹配的函数
        all_affected = []
        for entity in target_entities:
            if file_path and entity.file_path != file_path:
                continue
            
            affected = self.kg.analyze_impact(entity.id, max_depth=max_depth)
            all_affected.extend(affected)
        
        # 去重
        seen = set()
        unique_affected = []
        for item in all_affected:
            if item["entity_id"] not in seen:
                seen.add(item["entity_id"])
                unique_affected.append(item)
        
        return {
            "target_function": function_name,
            "affected_count": len(unique_affected),
            "affected_entities": unique_affected,
        }
    
    def analyze_class_modification(self, class_name: str, file_path: str = None) -> Dict[str, Any]:
        """
        分析类修改的影响范围
        
        Args:
            class_name: 类名
            file_path: 文件路径（可选）
            
        Returns:
            分析结果
        """
        target_entities = self.kg.find_entities(type="Class", name=class_name)
        
        if not target_entities:
            return {
                "error": f"未找到类: {class_name}",
                "affected_entities": [],
            }
        
        all_affected = []
        for entity in target_entities:
            if file_path and entity.file_path != file_path:
                continue
            
            affected = self.kg.analyze_impact(entity.id, max_depth=5)
            all_affected.extend(affected)
        
        # 去重
        seen = set()
        unique_affected = []
        for item in all_affected:
            if item["entity_id"] not in seen:
                seen.add(item["entity_id"])
                unique_affected.append(item)
        
        return {
            "target_class": class_name,
            "affected_count": len(unique_affected),
            "affected_entities": unique_affected,
        }


def build_knowledge_graph(project_root: str, output_path: str = None) -> CodeKnowledgeGraph:
    """
    构建知识图谱（便捷函数）
    
    Args:
        project_root: 项目根目录
        output_path: 输出路径（可选）
        
    Returns:
        构建好的知识图谱
    """
    kg = CodeKnowledgeGraph(name=os.path.basename(project_root))
    parser = ASTParser(kg)
    
    logger.info(f"[build_knowledge_graph] 开始构建，项目: {project_root}")
    count = parser.parse_directory(project_root, extensions=[".py"])
    
    logger.info(f"[build_knowledge_graph] 构建完成，解析文件数: {count}, 实体数: {len(kg.entities)}")
    
    if output_path:
        kg.save(output_path)
    
    return kg


if __name__ == "__main__":
    # 简单测试
    kg = CodeKnowledgeGraph("test")
    parser = ASTParser(kg)
    
    # 解析当前目录的 Python 文件
    current_dir = os.path.dirname(os.path.abspath(__file__))
    count = parser.parse_directory(current_dir, extensions=[".py"])
    
    print(f"解析文件数: {count}")
    print(f"实体数: {len(kg.entities)}")
    print(f"关系数: {len(kg.relations)}")
    
    # 影响分析
    analyzer = ImpactAnalyzer(kg)
    if kg.entities:
        first_entity = list(kg.entities.values())[0]
        result = analyzer.analyze_function_modification(first_entity.name)
        print(f"\n影响分析 ({first_entity.name}):")
        print(f"受影响实体数: {result['affected_count']}")
