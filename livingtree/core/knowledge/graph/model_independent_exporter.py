"""
ModelIndependentExporter - 模型无关导出器

实现模型无关性：
1. 知识库支持导出为模型无关格式（Markdown / JSON）
2. 支持从不同模型迁移知识
3. 支持多种格式之间的转换

参考 Rowboat 的"模型无关设计"。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import json
import os


class ExportFormat(Enum):
    """导出格式"""
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"


class KnowledgeType(Enum):
    """知识类型"""
    ENTITY = "entity"
    RELATION = "relation"
    MEMORY = "memory"
    DOCUMENT = "document"


@dataclass
class KnowledgeItem:
    """知识项"""
    id: str
    type: KnowledgeType
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class ModelIndependentExporter:
    """
    模型无关导出器
    
    核心功能：
    1. 支持多种格式导出（Markdown/JSON/YAML/CSV）
    2. 支持从不同模型迁移知识
    3. 支持格式转换
    4. 保持知识的语义完整性
    """

    def __init__(self):
        self._logger = logger.bind(component="ModelIndependentExporter")

    async def export_to_markdown(self, knowledge_data: Dict[str, Any], output_dir: str) -> str:
        """
        导出为 Markdown 格式
        
        Args:
            knowledge_data: 知识数据
            output_dir: 输出目录
            
        Returns:
            输出目录路径
        """
        os.makedirs(output_dir, exist_ok=True)

        # 导出实体
        entities = knowledge_data.get("entities", {})
        for entity_id, entity in entities.items():
            filepath = os.path.join(output_dir, f"{entity_id}.md")
            content = self._entity_to_markdown(entity_id, entity)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        # 导出关系
        relations = knowledge_data.get("relations", [])
        if relations:
            filepath = os.path.join(output_dir, "relations.md")
            content = self._relations_to_markdown(relations)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        self._logger.info(f"导出 Markdown 完成，共 {len(entities)} 个实体，{len(relations)} 个关系")
        return output_dir

    def _entity_to_markdown(self, entity_id: str, entity: Dict[str, Any]) -> str:
        """将实体转换为 Markdown"""
        title = entity.get("name", entity_id)
        content = entity.get("description", "")
        
        lines = []
        lines.append(f"# {title}")
        lines.append("")
        
        if content:
            lines.append(content)
            lines.append("")
        
        # 添加属性
        properties = entity.get("properties", {})
        if properties:
            lines.append("## 属性")
            for key, value in properties.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")
        
        # 添加关系
        relations = entity.get("relations", [])
        if relations:
            lines.append("## 关系")
            for rel in relations:
                target = rel.get("target_name", rel.get("target_id", ""))
                rel_type = rel.get("type", "")
                lines.append(f"- [[{target}]] ({rel_type})")
        
        return "\n".join(lines)

    def _relations_to_markdown(self, relations: List[Dict[str, Any]]) -> str:
        """将关系转换为 Markdown"""
        lines = ["# 关系列表", ""]
        
        for rel in relations:
            source = rel.get("source_name", rel.get("source_id", ""))
            target = rel.get("target_name", rel.get("target_id", ""))
            rel_type = rel.get("type", "")
            
            lines.append(f"## {source} → {target}")
            lines.append(f"- 类型: {rel_type}")
            
            if "description" in rel:
                lines.append(f"- 描述: {rel['description']}")
            lines.append("")
        
        return "\n".join(lines)

    async def export_to_json(self, knowledge_data: Dict[str, Any], output_path: str) -> str:
        """
        导出为 JSON 格式
        
        Args:
            knowledge_data: 知识数据
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        # 添加元数据
        export_data = {
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "format": "model-independent",
                "version": "1.0"
            },
            "data": knowledge_data
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        self._logger.info(f"导出 JSON 完成: {output_path}")
        return output_path

    async def export_to_yaml(self, knowledge_data: Dict[str, Any], output_path: str) -> str:
        """
        导出为 YAML 格式
        
        Args:
            knowledge_data: 知识数据
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("需要安装 PyYAML: pip install pyyaml")

        export_data = {
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "format": "model-independent",
                "version": "1.0"
            },
            "data": knowledge_data
        }

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(export_data, f, default_flow_style=False, allow_unicode=True)

        self._logger.info(f"导出 YAML 完成: {output_path}")
        return output_path

    async def export(self, knowledge_data: Dict[str, Any], output_path: str, 
                    format: ExportFormat = ExportFormat.JSON) -> str:
        """
        导出知识数据
        
        Args:
            knowledge_data: 知识数据
            output_path: 输出路径
            format: 导出格式
            
        Returns:
            输出路径
        """
        if format == ExportFormat.MARKDOWN:
            return await self.export_to_markdown(knowledge_data, output_path)
        elif format == ExportFormat.JSON:
            return await self.export_to_json(knowledge_data, output_path)
        elif format == ExportFormat.YAML:
            return await self.export_to_yaml(knowledge_data, output_path)
        else:
            raise ValueError(f"不支持的格式: {format}")

    async def import_from_json(self, input_path: str) -> Dict[str, Any]:
        """
        从 JSON 导入知识数据
        
        Args:
            input_path: 输入文件路径
            
        Returns:
            知识数据
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 提取实际数据
        if "data" in data:
            return data["data"]
        return data

    async def import_from_markdown(self, input_dir: str) -> Dict[str, Any]:
        """
        从 Markdown 目录导入知识数据
        
        Args:
            input_dir: 输入目录
            
        Returns:
            知识数据
        """
        entities = {}
        
        for filename in os.listdir(input_dir):
            if filename.endswith(".md") and filename != "relations.md":
                filepath = os.path.join(input_dir, filename)
                entity_id = filename[:-3]
                
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                entity = self._markdown_to_entity(entity_id, content)
                entities[entity_id] = entity

        return {"entities": entities, "relations": []}

    def _markdown_to_entity(self, entity_id: str, content: str) -> Dict[str, Any]:
        """将 Markdown 转换为实体"""
        lines = content.split("\n")
        entity = {
            "id": entity_id,
            "name": "",
            "description": "",
            "properties": {},
            "relations": []
        }

        current_section = None
        
        for line in lines:
            if line.startswith("# "):
                entity["name"] = line[2:]
            elif line.startswith("## 属性"):
                current_section = "properties"
            elif line.startswith("## 关系"):
                current_section = "relations"
            elif line.startswith("- **") and current_section == "properties":
                # 解析属性
                match = line[3:].split("**: ")
                if len(match) == 2:
                    key, value = match
                    entity["properties"][key] = value
            elif line.startswith("- [[") and current_section == "relations":
                # 解析关系
                end_bracket = line.find("]]")
                if end_bracket != -1:
                    target = line[4:end_bracket]
                    # 提取关系类型
                    rel_type = line[end_bracket+3:-1] if end_bracket+3 < len(line) else ""
                    entity["relations"].append({
                        "target_id": target,
                        "target_name": target,
                        "type": rel_type.strip("()")
                    })
            elif entity["name"] and not entity["description"] and not line.startswith("#"):
                entity["description"] = line.strip()

        return entity

    async def convert_format(self, input_path: str, output_path: str, 
                           input_format: ExportFormat, output_format: ExportFormat) -> str:
        """
        转换格式
        
        Args:
            input_path: 输入路径
            output_path: 输出路径
            input_format: 输入格式
            output_format: 输出格式
            
        Returns:
            输出路径
        """
        # 导入数据
        if input_format == ExportFormat.JSON:
            data = await self.import_from_json(input_path)
        elif input_format == ExportFormat.MARKDOWN:
            data = await self.import_from_markdown(input_path)
        else:
            raise ValueError(f"不支持的输入格式: {input_format}")

        # 导出数据
        return await self.export(data, output_path, output_format)