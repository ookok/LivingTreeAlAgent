"""
Markdown 技能加载器
=================

从 Markdown 文件加载 Agent Skills
"""

import re
import logging
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    Markdown 技能加载器
    
    解析 Markdown 格式的技能文件，提取元数据和内容
    """
    
    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or Path(__file__).parent / "skills"
        
    def load_skill_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        从 Markdown 文件加载技能
        
        支持 frontmatter 格式：
        ```
        ---
        id: spec-driven
        name: Spec-Driven Development
        description: Build features from specifications
        category: planning
        trigger_phrases: ["spec", "specification", "requirements"]
        ---
        
        # Skill Content
        ...
        ```
        """
        if not file_path.exists():
            logger.warning(f"[SkillLoader] 文件不存在: {file_path}")
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 frontmatter
            metadata = {}
            body = content
            
            frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
            if frontmatter_match:
                frontmatter = frontmatter_match.group(1)
                body = frontmatter_match.group(2)
                metadata = self._parse_frontmatter(frontmatter)
            
            return {
                "metadata": metadata,
                "content": body.strip(),
                "file_path": str(file_path),
            }
            
        except Exception as e:
            logger.error(f"[SkillLoader] 加载技能文件失败 {file_path}: {e}")
            return None
    
    def _parse_frontmatter(self, frontmatter: str) -> Dict[str, Any]:
        """解析 frontmatter YAML 格式"""
        metadata = {}
        for line in frontmatter.strip().split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                # 解析列表格式: ["item1", "item2"]
                if value.startswith('[') and value.endswith(']'):
                    items = value[1:-1].split(',')
                    metadata[key] = [item.strip().strip('"') for item in items]
                # 解析布尔值
                elif value.lower() in ('true', 'false'):
                    metadata[key] = value.lower() == 'true'
                # 解析数字
                elif value.isdigit():
                    metadata[key] = int(value)
                else:
                    metadata[key] = value
                    
        return metadata
    
    def load_all_skills(self) -> Dict[str, Dict[str, Any]]:
        """加载技能目录下的所有技能文件"""
        skills = {}
        
        if not self.skills_dir.exists():
            logger.warning(f"[SkillLoader] 技能目录不存在: {self.skills_dir}")
            return skills
        
        for md_file in self.skills_dir.glob("*.md"):
            skill_data = self.load_skill_file(md_file)
            if skill_data:
                skill_id = skill_data["metadata"].get("id", md_file.stem)
                skills[skill_id] = skill_data
                
        logger.info(f"[SkillLoader] 加载了 {len(skills)} 个技能")
        return skills
