"""
自动知识图谱构建器
支持增量更新和自动发现新实体/关系
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
import json
import hashlib

from .kg_builder import KnowledgeGraphBuilder, KnowledgeGraph, Entity, Relation

logger = logging.getLogger(__name__)


class AutoKnowledgeGraphBuilder(KnowledgeGraphBuilder):
    """自动知识图谱构建器（支持增量更新）"""

    def __init__(self, repo_path: str, cache_path: str = ".kg_cache.json"):
        super().__init__(repo_path)
        self.cache_path = Path(cache_path)
        self.file_hashes: Dict[str, str] = {}  # 文件路径 -> 哈希值
        self.kg: Optional[KnowledgeGraph] = None

    def build_or_update(self, force_rebuild: bool = False) -> KnowledgeGraph:
        """构建或更新知识图谱"""

        # 1. 尝试加载缓存
        if not force_rebuild and self.cache_path.exists():
            logger.info("发现缓存，尝试增量更新...")
            self.load_cache()
            changed_files = self._detect_changes()

            if not changed_files:
                logger.info("没有文件变更，使用缓存的知识图谱")
                return self.kg

            logger.info(f"发现 {len(changed_files)} 个变更文件，执行增量更新...")
            self._incremental_update(changed_files)
        else:
            logger.info("强制重建知识图谱...")
            self.kg = self.build()
            self._save_cache()

        return self.kg

    def _detect_changes(self) -> Set[str]:
        """检测变更的文件"""
        changed_files = set()
        repo_path = Path(self.repo_path)

        # 扫描所有 Python 文件
        for py_file in repo_path.rglob("*.py"):
            file_str = str(py_file)
            relative_path = str(py_file.relative_to(repo_path))

            # 计算文件哈希
            current_hash = self._calculate_file_hash(py_file)

            # 检查是否变更
            if relative_path not in self.file_hashes:
                # 新文件
                changed_files.add(relative_path)
                self.file_hashes[relative_path] = current_hash
            elif self.file_hashes[relative_path] != current_hash:
                # 文件已修改
                changed_files.add(relative_path)
                self.file_hashes[relative_path] = current_hash

        # 检查删除的文件
        cached_files = set(self.file_hashes.keys())
        current_files = {str(p.relative_to(repo_path)) for p in repo_path.rglob("*.py")}
        deleted_files = cached_files - current_files

        for deleted_file in deleted_files:
            del self.file_hashes[deleted_file]
            changed_files.add(deleted_file)  # 标记为变更（需要从图谱中移除）

        return changed_files

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def _incremental_update(self, changed_files: Set[str]):
        """增量更新知识图谱"""
        if self.kg is None:
            logger.warning("知识图谱尚未加载，执行完整构建")
            self.kg = self.build()
            return

        logger.info(f"增量更新: {len(changed_files)} 个文件")

        # 1. 移除旧实体和关系
        for file_path in changed_files:
            module_id = file_path
            self._remove_module_from_kg(module_id)

        # 2. 重新解析变更的文件
        repo_path = Path(self.repo_path)
        for file_path in changed_files:
            full_path = repo_path / file_path
            if full_path.exists():
                try:
                    self.parser._parse_file(full_path)
                except Exception as e:
                    logger.error(f"解析文件失败 {full_path}: {e}")

        # 3. 更新知识图谱
        for entity in self.parser.entities.values():
            if entity.id not in self.kg.entities:
                self.kg.add_entity(entity)

        for relation in self.parser.relations:
            # 检查关系是否已存在
            if not self._relation_exists(relation):
                self.kg.add_relation(relation)

        # 4. 保存缓存
        self._save_cache()

        logger.info(f"增量更新完成: {len(self.kg.entities)} 个实体, {len(self.kg.relations)} 个关系")

    def _remove_module_from_kg(self, module_id: str):
        """从知识图谱中移除模块"""
        # 1. 移除模块实体
        if module_id in self.kg.entities:
            del self.kg.entities[module_id]

        # 2. 移除与模块相关的实体（类、函数等）
        entities_to_remove = []
        for entity_id, entity in self.kg.entities.items():
            if entity_id.startswith(module_id + "::"):
                entities_to_remove.append(entity_id)

        for entity_id in entities_to_remove:
            del self.kg.entities[entity_id]

        # 3. 移除相关关系
        self.kg.relations = [
            rel for rel in self.kg.relations
            if not (rel.source_id.startswith(module_id) or rel.target_id.startswith(module_id))
        ]

    def _relation_exists(self, relation: Relation) -> bool:
        """检查关系是否已存在"""
        for existing_rel in self.kg.relations:
            if (existing_rel.source_id == relation.source_id and
                existing_rel.target_id == relation.target_id and
                existing_rel.type == relation.type):
                return True
        return False

    def load_cache(self):
        """加载缓存"""
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)

            self.file_hashes = cache.get('file_hashes', {})

            kg_data = cache.get('knowledge_graph', None)
            if kg_data:
                self.kg = KnowledgeGraph.from_dict(kg_data)

            logger.info(f"缓存加载成功: {len(self.file_hashes)} 个文件, "
                       f"{len(self.kg.entities) if self.kg else 0} 个实体")

        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
            self.kg = None

    def _save_cache(self):
        """保存缓存"""
        try:
            cache = {
                'file_hashes': self.file_hashes,
                'knowledge_graph': self.kg.to_dict() if self.kg else None,
                'last_update': datetime.now().isoformat(),
            }

            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)

            logger.info(f"缓存已保存: {self.cache_path}")

        except Exception as e:
            logger.error(f"保存缓存失败: {e}")

    def add_concept_manually(self, concept_name: str, description: str, related_entities: List[str]):
        """手动添加概念"""
        if self.kg is None:
            raise ValueError("知识图谱尚未构建")

        # 创建概念实体
        concept_id = f"concept::{concept_name}"
        concept_entity = Entity(
            id=concept_id,
            type='concept',
            name=concept_name,
            properties={
                'description': description,
                'source': 'manual',
                'created_at': datetime.now().isoformat(),
            }
        )
        self.kg.add_entity(concept_entity)

        # 添加关系
        for entity_id in related_entities:
            if entity_id in self.kg.entities:
                rel = Relation(
                    source_id=concept_id,
                    target_id=entity_id,
                    type='related_to',
                    weight=1.0,
                    properties={'source': 'manual'}
                )
                self.kg.add_relation(rel)

        logger.info(f"手动添加概念: {concept_name}")
        self._save_cache()

    def find_similar_entities(self, entity_id: str, top_k: int = 5) -> List[Entity]:
        """查找相似实体（基于关系）"""
        if self.kg is None:
            raise ValueError("知识图谱尚未构建")

        if entity_id not in self.kg.entities:
            raise ValueError(f"实体不存在: {entity_id}")

        # 基于关系重叠度计算相似度
        entity_relations = set(self.kg.get_relations(entity_id))
        similarity_scores = {}

        for other_id, other_entity in self.kg.entities.items():
            if other_id == entity_id:
                continue

            other_relations = set(self.kg.get_relations(other_id))
            overlap = len(entity_relations & other_relations)
            union = len(entity_relations | other_relations)

            if union > 0:
                similarity = overlap / union
                similarity_scores[other_id] = similarity

        # 排序并返回 top-k
        sorted_entities = sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True)
        return [self.kg.entities[eid] for eid, score in sorted_entities[:top_k]]

    def recommend_related_code(self, query_entity_id: str) -> List[str]:
        """推荐相关代码"""
        if self.kg is None:
            raise ValueError("知识图谱尚未构建")

        recommendations = []

        # 1. 直接关联的代码
        direct_relations = self.kg.get_relations(query_entity_id)
        for rel in direct_relations:
            if rel.type in ['calls', 'imports', 'inherits']:
                target_id = rel.target_id
                if target_id in self.kg.entities:
                    entity = self.kg.entities[target_id]
                    if entity.type in ['class', 'function', 'module']:
                        recommendations.append(target_id)

        # 2. 相似实体
        similar_entities = self.find_similar_entities(query_entity_id, top_k=5)
        for entity in similar_entities:
            if entity.id not in recommendations:
                recommendations.append(entity.id)

        return recommendations

    def export_for_embedding(self, output_path: str):
        """导出用于 embedding 的数据"""
        if self.kg is None:
            raise ValueError("知识图谱尚未构建")

        embedding_data = []

        for entity_id, entity in self.kg.entities.items():
            # 构建文本描述
            text = f"{entity.type}: {entity.name}"

            if entity.properties:
                props = ', '.join([f"{k}={v}" for k, v in entity.properties.items()])
                text += f" ({props})"

            embedding_data.append({
                'id': entity_id,
                'text': text,
                'type': entity.type,
            })

        # 保存为 JSONL
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in embedding_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        logger.info(f"Embedding 数据已导出: {output_path}")
        return embedding_data
