"""
MarkdownExporter - Markdown 导出器

将 KnowledgeGraph / IntelligentMemory 导出为 Obsidian 兼容格式。

功能：
1. 支持反向链接（backlinks）
2. 支持双括号引用 [[note]]
3. 用户可直接查看/编辑知识库，然后同步回数据库
4. 支持 YAML frontmatter

参考 Rowboat 的知识管理设计。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
import os


@dataclass
class ExportNode:
    """导出节点"""
    id: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    backlinks: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


class MarkdownExporter:
    """
    Markdown 导出器
    
    将知识库导出为 Obsidian 兼容格式。
    
    特性：
    - 支持反向链接
    - 支持双括号引用 [[note]]
    - 支持 YAML frontmatter
    - 支持标签
    """

    def __init__(self, export_dir: str = None):
        self._logger = logger.bind(component="MarkdownExporter")
        
        if export_dir is None:
            export_dir = os.path.expanduser("~/.livingtree/obsidian")
        
        self._export_dir = export_dir
        self._notes_dir = os.path.join(export_dir, "notes")
        self._backlinks_dir = os.path.join(export_dir, "backlinks")
        
        os.makedirs(self._notes_dir, exist_ok=True)
        os.makedirs(self._backlinks_dir, exist_ok=True)

    async def export_knowledge_graph(self, kg_data: Dict[str, Any]) -> str:
        """
        导出知识图谱为 Markdown
        
        Args:
            kg_data: 知识图谱数据
            
        Returns:
            导出目录路径
        """
        self._logger.info("开始导出知识图谱")

        nodes = await self._convert_to_nodes(kg_data)
        
        for node in nodes:
            await self._export_node(node)
        
        # 生成反向链接
        await self._generate_backlinks(nodes)

        self._logger.info(f"知识图谱导出完成，共 {len(nodes)} 个节点")
        return self._export_dir

    async def _convert_to_nodes(self, kg_data: Dict[str, Any]) -> List[ExportNode]:
        """将知识图谱数据转换为导出节点"""
        nodes = []
        
        for entity_id, entity_data in kg_data.items():
            title = entity_data.get("name", entity_id)
            content = entity_data.get("description", "")
            
            # 添加属性
            properties = entity_data.get("properties", {})
            if properties:
                content += "\n\n## 属性\n"
                for key, value in properties.items():
                    content += f"- {key}: {value}\n"
            
            # 添加关系
            relations = entity_data.get("relations", [])
            if relations:
                content += "\n\n## 关系\n"
                for rel in relations:
                    target_name = rel.get("target_name", rel.get("target_id", ""))
                    content += f"- [[{target_name}]] ({rel.get('type', '')})\n"

            node = ExportNode(
                id=entity_id,
                title=title,
                content=content,
                tags=entity_data.get("tags", []),
                backlinks=[]
            )
            nodes.append(node)
        
        return nodes

    async def _export_node(self, node: ExportNode):
        """导出单个节点"""
        # 生成文件名（去除特殊字符）
        filename = self._sanitize_filename(node.title) + ".md"
        filepath = os.path.join(self._notes_dir, filename)

        # 生成 YAML frontmatter
        frontmatter = self._generate_frontmatter(node)
        
        # 生成内容
        content = f"---\n{frontmatter}---\n\n{node.content}"

        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        self._logger.debug(f"导出节点: {node.title}")

    def _generate_frontmatter(self, node: ExportNode) -> str:
        """生成 YAML frontmatter"""
        lines = []
        lines.append(f"title: \"{node.title}\"")
        lines.append(f"created: {node.created_at.isoformat()}")
        
        if node.tags:
            tags_str = ", ".join(f'"{tag}"' for tag in node.tags)
            lines.append(f"tags: [{tags_str}]")
        
        return "\n".join(lines)

    async def _generate_backlinks(self, nodes: List[ExportNode]):
        """生成反向链接文件"""
        # 构建引用映射
        reference_map = {}
        for node in nodes:
            # 查找所有引用该节点的节点
            for other in nodes:
                if node.title != other.title and f"[[{node.title}]]" in other.content:
                    if node.title not in reference_map:
                        reference_map[node.title] = []
                    reference_map[node.title].append(other.title)

        # 更新节点的反向链接
        for node in nodes:
            node.backlinks = reference_map.get(node.title, [])

        # 为每个节点生成反向链接文件
        for node in nodes:
            if node.backlinks:
                backlink_content = f"# 反向链接\n\n"
                for backlink in node.backlinks:
                    backlink_content += f"- [[{backlink}]]\n"
                
                filename = self._sanitize_filename(node.title) + "_backlinks.md"
                filepath = os.path.join(self._backlinks_dir, filename)
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(backlink_content)

    async def export_intelligent_memory(self, memory_data: Dict[str, Any]) -> str:
        """
        导出智能记忆为 Markdown
        
        Args:
            memory_data: 智能记忆数据
            
        Returns:
            导出目录路径
        """
        self._logger.info("开始导出智能记忆")

        nodes = []
        
        for memory_id, memory in memory_data.items():
            title = memory.get("title", memory_id)
            content = memory.get("content", "")
            
            # 添加上下文
            context = memory.get("context", "")
            if context:
                content += f"\n\n## 上下文\n\n{context}"
            
            # 添加相关记忆引用
            related = memory.get("related", [])
            if related:
                content += "\n\n## 相关记忆\n"
                for rel in related:
                    content += f"- [[{rel}]]\n"

            node = ExportNode(
                id=memory_id,
                title=title,
                content=content,
                tags=memory.get("tags", []),
                backlinks=[]
            )
            nodes.append(node)

        # 导出所有节点
        for node in nodes:
            await self._export_node(node)

        # 生成反向链接
        await self._generate_backlinks(nodes)

        self._logger.info(f"智能记忆导出完成，共 {len(nodes)} 条记录")
        return self._export_dir

    async def import_from_markdown(self, import_dir: str = None) -> Dict[str, Any]:
        """
        从 Markdown 文件导入知识库
        
        Args:
            import_dir: 导入目录（默认使用导出目录）
            
        Returns:
            导入的数据
        """
        if import_dir is None:
            import_dir = self._notes_dir

        imported_data = {}
        
        for filename in os.listdir(import_dir):
            if filename.endswith(".md") and not filename.endswith("_backlinks.md"):
                filepath = os.path.join(import_dir, filename)
                
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 解析 YAML frontmatter
                data = self._parse_markdown(content)
                data["filename"] = filename
                
                # 提取标题（去掉 .md 扩展名）
                title = filename[:-3]
                data["title"] = title
                
                imported_data[title] = data

        self._logger.info(f"从 {import_dir} 导入 {len(imported_data)} 个文件")
        return imported_data

    def _parse_markdown(self, content: str) -> Dict[str, Any]:
        """解析 Markdown 文件"""
        data = {
            "content": "",
            "tags": [],
            "backlinks": []
        }

        # 检查是否有 frontmatter
        if content.startswith("---"):
            end_idx = content.find("---", 3)
            if end_idx != -1:
                frontmatter = content[3:end_idx].strip()
                content = content[end_idx + 3:].strip()
                
                # 简单解析 YAML
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        if key == "tags":
                            # 解析 tags 数组
                            import re
                            tags = re.findall(r'"([^"]+)"', value)
                            data["tags"] = tags
                        else:
                            data[key] = value

        data["content"] = content
        
        # 提取双括号引用
        import re
        backlinks = re.findall(r'\[\[([^\]]+)\]\]', content)
        data["backlinks"] = backlinks

        return data

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名（去除特殊字符）"""
        import re
        return re.sub(r'[\\/:*?"<>|]', '_', filename)

    def get_export_dir(self) -> str:
        """获取导出目录"""
        return self._export_dir