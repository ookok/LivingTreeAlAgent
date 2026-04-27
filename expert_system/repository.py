"""
专家库和技能包仓库
支持导入导出功能（Markdown、ZIP）
"""

import json
import os
import re
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from urllib.parse import urlparse

from .persona_dispatcher import Persona, PersonaLibrary, BUILTIN_PERSONAS


# ── 技能包定义 ──────────────────────────────────────────────────────

@dataclass
class Skill:
    """技能包定义"""
    id: str
    name: str                           # 技能名称
    description: str = ""                # 技能描述
    category: str = "general"             # 分类
    
    # 触发条件
    trigger_keywords: List[str] = field(default_factory=list)
    trigger_domains: List[str] = field(default_factory=list)
    
    # 技能内容
    instructions: str = ""               # 技能指令
    prompts: List[str] = field(default_factory=list)  # 示例提示词
    
    # 工具引用
    tool_names: List[str] = field(default_factory=list)
    
    # 元数据
    version: str = "1.0"
    author: str = "system"
    source_url: str = ""
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    
    # 状态
    is_builtin: bool = False
    is_active: bool = True
    usage_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Skill":
        return cls(**data)


# ── 内置技能包 ───────────────────────────────────────────────────────

BUILTIN_SKILLS = {
    "cost_analysis": Skill(
        id="cost_analysis",
        name="成本分析技能",
        description="用于进行项目成本和投资回报分析",
        category="business",
        trigger_keywords=["成本", "预算", "费用", "投资", "ROI", "回报", "价格"],
        trigger_domains=["business", "investment"],
        instructions="""你具备专业的成本分析能力。分析时请：
1. 列出所有相关成本项（固定成本、变动成本）
2. 计算预期的投资回报
3. 提供盈亏平衡分析
4. 给出风险调整后的收益预期""",
        prompts=[
            "分析这个项目的成本结构",
            "计算投资回报率",
            "预算方案对比"
        ],
        tool_names=["calculator"],
        is_builtin=True,
    ),
    
    "regulation_lookup": Skill(
        id="regulation_lookup",
        name="法规查询技能",
        description="用于查询和引用相关法规标准",
        category="legal",
        trigger_keywords=["法规", "标准", "规范", "合规", "审批", "许可", "要求", "第X条"],
        trigger_domains=["legal", "compliance"],
        instructions="""你具备专业的法规查询能力。回答时请：
1. 明确引用相关法律法规的条文
2. 指出具体的标准编号和版本
3. 说明适用范围和条件
4. 提供完整的合规清单""",
        prompts=[
            "根据XX法规，应该如何做？",
            "这个标准有哪些要求？",
            "需要满足哪些合规条件？"
        ],
        tool_names=[],
        is_builtin=True,
    ),
    
    "technical_analysis": Skill(
        id="technical_analysis",
        name="技术分析技能",
        description="用于深入的技术方案分析和对比",
        category="engineering",
        trigger_keywords=["技术", "参数", "方案", "配置", "性能", "优化"],
        trigger_domains=["engineering", "technology"],
        instructions="""你具备专业的技术分析能力。分析时请：
1. 深入技术细节和实现原理
2. 对比不同技术方案的优缺点
3. 引用相关技术标准和最佳实践
4. 提供可操作的技术建议""",
        prompts=[
            "这个技术方案有哪些优缺点？",
            "如何优化这个配置？",
            "技术选型建议是什么？"
        ],
        tool_names=["code_generator"],
        is_builtin=True,
    ),
    
    "citation_manager": Skill(
        id="citation_manager",
        name="文献引用技能",
        description="用于学术文献管理和引用格式处理",
        category="academic",
        trigger_keywords=["论文", "引用", "参考文献", "文献", "学术", "研究"],
        trigger_domains=["academic"],
        instructions="""你具备专业的文献管理能力。请：
1. 使用规范的引用格式（IEEE/APA/GB7714）
2. 验证引用的完整性
3. 建议相关领域的重要文献
4. 帮助构建文献综述框架""",
        prompts=[
            "帮我整理参考文献格式",
            "这个领域有哪些重要文献？",
            "如何正确引用这篇论文？"
        ],
        tool_names=["citation_formatter"],
        is_builtin=True,
    ),
    
    "concept_explainer": Skill(
        id="concept_explainer",
        name="概念解释技能",
        description="用于用通俗语言解释复杂概念",
        category="education",
        trigger_keywords=["什么是", "解释", "概念", "入门", "基础"],
        trigger_domains=["education"],
        instructions="""你具备出色的科普解释能力。请：
1. 从基础概念开始
2. 使用生活化的类比
3. 分步骤讲解
4. 提供延伸学习建议""",
        prompts=[
            "什么是XX？",
            "能解释一下这个概念吗？",
            "用简单的话说明"
        ],
        tool_names=[],
        is_builtin=True,
    ),
    
    "environmental_impact": Skill(
        id="environmental_impact",
        name="环境影响分析技能",
        description="用于环境影响评估和分析",
        category="environment",
        trigger_keywords=["环境", "污染", "排放", "影响", "评估", "环保"],
        trigger_domains=["environment"],
        instructions="""你具备专业的环境影响分析能力。请：
1. 量化分析环境影响
2. 引用相关环保标准
3. 评估风险等级
4. 提出缓解措施""",
        prompts=[
            "这个项目对环境有什么影响？",
            "如何减少污染排放？",
            "环境影响评估怎么做？"
        ],
        tool_names=["emission_calculator"],
        is_builtin=True,
    ),
}


# ── 技能包仓库 ───────────────────────────────────────────────────────

class SkillRepository:
    """技能包仓库管理器"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or self._get_default_storage_path()
        self._skills: Dict[str, Skill] = {}
        self._load()
    
    def _get_default_storage_path(self) -> Path:
        from client.src.business.config import get_config_dir
        return get_config_dir() / "skill_repository.json"
    
    def _load(self):
        """加载技能包"""
        self._skills = {k: v for k, v in BUILTIN_SKILLS.items()}
        
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for sdata in data.get("skills", []):
                        skill = Skill.from_dict(sdata)
                        if not skill.is_builtin:
                            self._skills[skill.id] = skill
            except Exception:
                pass
    
    def _save(self):
        """保存技能包"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        custom_skills = [s.to_dict() for s in self._skills.values() if not s.is_builtin]
        
        data = {
            "version": "1.0",
            "skills": custom_skills,
            "updated_at": datetime.now().timestamp(),
        }
        
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get(self, skill_id: str) -> Optional[Skill]:
        """获取技能包"""
        return self._skills.get(skill_id)
    
    def get_all(self) -> List[Skill]:
        """获取所有技能包"""
        return list(self._skills.values())
    
    def get_active(self) -> List[Skill]:
        """获取所有激活的技能包"""
        return [s for s in self._skills.values() if s.is_active]
    
    def find_by_keyword(self, keyword: str) -> List[Skill]:
        """通过关键词查找技能包"""
        keyword_lower = keyword.lower()
        results = []
        for skill in self._skills.values():
            if skill.is_active:
                if keyword_lower in skill.name.lower() or \
                   keyword_lower in skill.description.lower() or \
                   any(keyword_lower in kw.lower() for kw in skill.trigger_keywords):
                    results.append(skill)
        return results
    
    def find_by_domain(self, domain: str) -> List[Skill]:
        """通过领域查找技能包"""
        results = []
        for skill in self._skills.values():
            if skill.is_active and domain in skill.trigger_domains:
                results.append(skill)
        return results
    
    def add(self, skill: Skill) -> bool:
        """添加技能包"""
        if skill.id in self._skills and not skill.is_builtin:
            return False
        skill.updated_at = datetime.now().timestamp()
        self._skills[skill.id] = skill
        self._save()
        return True
    
    def update(self, skill: Skill) -> bool:
        """更新技能包"""
        if skill.id not in self._skills:
            return False
        if self._skills[skill.id].is_builtin:
            skill.is_builtin = False
        skill.updated_at = datetime.now().timestamp()
        self._skills[skill.id] = skill
        self._save()
        return True
    
    def delete(self, skill_id: str) -> bool:
        """删除技能包"""
        if skill_id not in self._skills:
            return False
        if self._skills[skill_id].is_builtin:
            return False
        del self._skills[skill_id]
        self._save()
        return True
    
    def toggle_active(self, skill_id: str) -> bool:
        """切换激活状态"""
        skill = self._skills.get(skill_id)
        if skill and not skill.is_builtin:
            skill.is_active = not skill.is_active
            self._save()
            return True
        return False


# ── 专家库仓库 ───────────────────────────────────────────────────────

class ExpertRepository:
    """专家库仓库（人格库包装器）"""
    
    def __init__(self, persona_library: Optional[PersonaLibrary] = None):
        self.persona_library = persona_library or PersonaLibrary()
        self.skill_repository = SkillRepository()
    
    # 人格操作
    def get_persona(self, persona_id: str) -> Optional[Persona]:
        return self.persona_library.get(persona_id)
    
    def get_all_personas(self) -> List[Persona]:
        return self.persona_library.get_all()
    
    def get_active_personas(self) -> List[Persona]:
        return self.persona_library.get_active()
    
    def add_persona(self, persona: Persona) -> bool:
        return self.persona_library.add(persona)
    
    def update_persona(self, persona: Persona) -> bool:
        return self.persona_library.update(persona)
    
    def delete_persona(self, persona_id: str) -> bool:
        return self.persona_library.delete(persona_id)
    
    # 技能包操作
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return self.skill_repository.get(skill_id)
    
    def get_all_skills(self) -> List[Skill]:
        return self.skill_repository.get_all()
    
    def add_skill(self, skill: Skill) -> bool:
        return self.skill_repository.add(skill)
    
    def delete_skill(self, skill_id: str) -> bool:
        return self.skill_repository.delete(skill_id)


# ── 导入导出管理器 ──────────────────────────────────────────────────

class ExportManager:
    """
    导入导出管理器
    
    支持：
    - 单条导出（Markdown/JSON）
    - 批量导出（ZIP）
    - 从网络导入（URL）
    - 从本地导入（文件）
    """
    
    def __init__(self, expert_repository: Optional[ExpertRepository] = None):
        self.expert_repository = expert_repository or ExpertRepository()
    
    # ── 导出 ──────────────────────────────────────────────────────────
    
    def export_persona_markdown(self, persona_id: str) -> Optional[str]:
        """导出人格为 Markdown 格式"""
        persona = self.expert_repository.get_persona(persona_id)
        if not persona:
            return None
        
        lines = [
            f"# {persona.name}",
            "",
            f"**ID**: `{persona.id}`",
            f"**领域**: {persona.domain}",
            f"**版本**: {persona.version}",
            "",
            f"## 描述",
            "",
            persona.description or "无描述",
            "",
            f"## 系统提示词",
            "",
            "```system",
            persona.system_prompt or "(空)",
            "```",
            "",
            f"## 触发条件",
            "",
        ]
        
        if persona.trigger_conditions:
            for cond in persona.trigger_conditions:
                cond_type = cond.get("type", "")
                value = cond.get("value", "")
                weight = cond.get("weight", 1.0)
                threshold = cond.get("threshold", "")
                lines.append(f"- **{cond_type}**: `{value}` (权重: {weight})")
                if threshold:
                    lines.append(f"  - 阈值: {threshold}")
        else:
            lines.append("无特定触发条件")
        
        lines.extend([
            "",
            f"## 人格特征",
            "",
        ])
        
        if persona.traits:
            for key, value in persona.traits.items():
                lines.append(f"- **{key}**: {value}")
        else:
            lines.append("无特殊特征")
        
        lines.extend([
            "",
            f"## 关联技能",
            "",
        ])
        
        if persona.skill_ids:
            for skill_id in persona.skill_ids:
                skill = self.expert_repository.get_skill(skill_id)
                name = skill.name if skill else skill_id
                lines.append(f"- `{skill_id}`: {name}")
        else:
            lines.append("无关联技能")
        
        lines.extend([
            "",
            f"## 元数据",
            "",
            f"- 创建时间: {datetime.fromtimestamp(persona.created_at).strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 更新时间: {datetime.fromtimestamp(persona.updated_at).strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 作者: {persona.author}",
            f"- 内置: {'是' if persona.is_builtin else '否'}",
            f"- 激活: {'是' if persona.is_active else '否'}",
        ])
        
        return "\n".join(lines)
    
    def export_persona_json(self, persona_id: str) -> Optional[str]:
        """导出人格为 JSON 格式"""
        data = self.expert_repository.persona_library.export_persona(persona_id)
        return json.dumps(data, ensure_ascii=False, indent=2) if data else None
    
    def export_skill_markdown(self, skill_id: str) -> Optional[str]:
        """导出技能包为 Markdown 格式"""
        skill = self.expert_repository.get_skill(skill_id)
        if not skill:
            return None
        
        lines = [
            f"# {skill.name}",
            "",
            f"**ID**: `{skill.id}`",
            f"**分类**: {skill.category}",
            f"**版本**: {skill.version}",
            "",
            f"## 描述",
            "",
            skill.description or "无描述",
            "",
            f"## 触发关键词",
            "",
        ]
        
        if skill.trigger_keywords:
            lines.append(", ".join(f"`{kw}`" for kw in skill.trigger_keywords))
        else:
            lines.append("无")
        
        lines.extend([
            "",
            f"## 触发领域",
            "",
        ])
        
        if skill.trigger_domains:
            lines.append(", ".join(f"`{d}`" for d in skill.trigger_domains))
        else:
            lines.append("无")
        
        lines.extend([
            "",
            f"## 技能指令",
            "",
            "```system",
            skill.instructions or "(空)",
            "```",
        ])
        
        if skill.prompts:
            lines.extend([
                "",
                f"## 示例提示词",
                "",
            ])
            for i, prompt in enumerate(skill.prompts, 1):
                lines.append(f"{i}. {prompt}")
        
        if skill.tool_names:
            lines.extend([
                "",
                f"## 关联工具",
                "",
            ])
            for tool in skill.tool_names:
                lines.append(f"- `{tool}`")
        
        lines.extend([
            "",
            f"## 元数据",
            "",
            f"- 来源: {skill.source_url or '本地'}",
            f"- 作者: {skill.author}",
            f"- 内置: {'是' if skill.is_builtin else '否'}",
            f"- 激活: {'是' if skill.is_active else '否'}",
            f"- 使用次数: {skill.usage_count}",
        ])
        
        return "\n".join(lines)
    
    def export_skill_json(self, skill_id: str) -> Optional[str]:
        """导出技能包为 JSON 格式"""
        skill = self.expert_repository.get_skill(skill_id)
        return json.dumps(skill.to_dict(), ensure_ascii=False, indent=2) if skill else None
    
    def export_all_markdown(self, output_dir: str) -> Dict[str, str]:
        """
        导出所有人格和技能包为 Markdown
        
        Returns:
            {"personas": {"id": "path"}, "skills": {"id": "path"}}
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        results = {"personas": {}, "skills": {}}
        
        # 导出人格
        personas_dir = output_path / "personas"
        personas_dir.mkdir(exist_ok=True)
        
        for persona in self.expert_repository.get_all_personas():
            content = self.export_persona_markdown(persona.id)
            if content:
                filename = f"{persona.id}.md"
                filepath = personas_dir / filename
                filepath.write_text(content, encoding="utf-8")
                results["personas"][persona.id] = str(filepath)
        
        # 导出技能包
        skills_dir = output_path / "skills"
        skills_dir.mkdir(exist_ok=True)
        
        for skill in self.expert_repository.get_all_skills():
            content = self.export_skill_markdown(skill.id)
            if content:
                filename = f"{skill.id}.md"
                filepath = skills_dir / filename
                filepath.write_text(content, encoding="utf-8")
                results["skills"][skill.id] = str(filepath)
        
        return results
    
    def export_to_zip(self, output_path: str, include_builtin: bool = True) -> bool:
        """
        导出所有内容为 ZIP 压缩包
        
        Args:
            output_path: 输出文件路径
            include_builtin: 是否包含内置人格/技能包
            
        Returns:
            是否成功
        """
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 添加人格
                personas_dir = tempfile.mkdtemp()
                personas_path = Path(personas_dir)
                
                for persona in self.expert_repository.get_all_personas():
                    if not include_builtin and persona.is_builtin:
                        continue
                    
                    content = self.export_persona_markdown(persona.id)
                    if content:
                        filepath = personas_path / f"{persona.id}.md"
                        filepath.write_text(content, encoding="utf-8")
                        zf.write(filepath, f"personas/{persona.id}.md")
                    
                    # 添加 JSON
                    json_content = self.export_persona_json(persona.id)
                    if json_content:
                        filepath = personas_path / f"{persona.id}.json"
                        filepath.write_text(json_content, encoding="utf-8")
                        zf.write(filepath, f"personas/{persona.id}.json")
                
                # 添加技能包
                skills_dir = tempfile.mkdtemp()
                skills_path = Path(skills_dir)
                
                for skill in self.expert_repository.get_all_skills():
                    if not include_builtin and skill.is_builtin:
                        continue
                    
                    content = self.export_skill_markdown(skill.id)
                    if content:
                        filepath = skills_path / f"{skill.id}.md"
                        filepath.write_text(content, encoding="utf-8")
                        zf.write(filepath, f"skills/{skill.id}.md")
                
                # 添加索引文件
                index = {
                    "exported_at": datetime.now().isoformat(),
                    "version": "1.0",
                    "personas": [p.id for p in self.expert_repository.get_all_personas() 
                                if include_builtin or not p.is_builtin],
                    "skills": [s.id for s in self.expert_repository.get_all_skills()
                              if include_builtin or not s.is_builtin],
                }
                zf.writestr("index.json", json.dumps(index, ensure_ascii=False, indent=2))
                
                # 添加 README
                readme = f"""# Expert System Export

导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 内容

- 人格: {len(index['personas'])} 个
- 技能包: {len(index['skills'])} 个

## 目录结构

```
/
├── personas/
│   ├── xxx.md      # Markdown 格式
│   └── xxx.json    # JSON 格式
├── skills/
│   └── xxx.md      # Markdown 格式
└── index.json      # 索引文件
```

## 导入说明

1. 导入单个人格/技能包：直接导入对应的 Markdown 文件
2. 批量导入：导入整个 ZIP 包
"""
                zf.writestr("README.md", readme)
            
            return True
        except Exception as e:
            print(f"Export failed: {e}")
            return False
    
    # ── 导入 ──────────────────────────────────────────────────────────
    
    def import_persona_from_markdown(self, content: str) -> Optional[Persona]:
        """从 Markdown 导入人格"""
        try:
            # 解析 Markdown
            persona_data = self._parse_persona_markdown(content)
            if persona_data:
                persona = Persona.from_dict(persona_data)
                persona.id = persona_data.get("id", f"imported_{int(datetime.now().timestamp())}")
                persona.is_builtin = False
                return persona
        except Exception as e:
            print(f"Import failed: {e}")
        return None
    
    def import_persona_from_json(self, content: str) -> Optional[Persona]:
        """从 JSON 导入人格"""
        try:
            data = json.loads(content)
            persona = Persona.from_dict(data)
            persona.is_builtin = False
            return persona
        except Exception:
            return None
    
    def import_skill_from_markdown(self, content: str) -> Optional[Skill]:
        """从 Markdown 导入技能包"""
        try:
            skill_data = self._parse_skill_markdown(content)
            if skill_data:
                skill = Skill.from_dict(skill_data)
                skill.id = skill_data.get("id", f"imported_{int(datetime.now().timestamp())}")
                skill.is_builtin = False
                return skill
        except Exception as e:
            print(f"Import failed: {e}")
        return None
    
    def import_from_url(self, url: str) -> Dict[str, Any]:
        """
        从网络 URL 导入人格或技能包
        
        Returns:
            {"type": "persona|skill", "success": bool, "message": str}
        """
        try:
            import requests
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            content = response.text
            
            # 判断类型
            if "## 系统提示词" in content or "trigger_conditions" in content:
                result = self.import_persona_from_markdown(content)
                obj_type = "persona"
            else:
                result = self.import_skill_from_markdown(content)
                obj_type = "skill"
            
            if result:
                if isinstance(result, Persona):
                    self.expert_repository.add_persona(result)
                else:
                    self.expert_repository.add_skill(result)
                
                return {
                    "type": obj_type,
                    "success": True,
                    "id": result.id,
                    "name": result.name,
                    "message": f"成功导入{obj_type}: {result.name}"
                }
            else:
                return {
                    "type": obj_type,
                    "success": False,
                    "message": "解析失败"
                }
        except Exception as e:
            return {
                "type": "unknown",
                "success": False,
                "message": f"导入失败: {str(e)}"
            }
    
    def import_from_file(self, filepath: str) -> Dict[str, Any]:
        """
        从本地文件导入人格或技能包
        
        Returns:
            {"type": "persona|skill", "success": bool, "message": str}
        """
        path = Path(filepath)
        
        if not path.exists():
            return {"success": False, "message": "文件不存在"}
        
        try:
            content = path.read_text(encoding="utf-8")
            
            if path.suffix == ".json":
                if "trigger_conditions" in content or "system_prompt" in content:
                    result = self.import_persona_from_json(content)
                    obj_type = "persona"
                else:
                    return {"success": False, "message": "JSON 格式不正确"}
            elif path.suffix in [".md", ".txt"]:
                if "## 系统提示词" in content:
                    result = self.import_persona_from_markdown(content)
                    obj_type = "persona"
                else:
                    result = self.import_skill_from_markdown(content)
                    obj_type = "skill"
            else:
                return {"success": False, "message": "不支持的文件格式"}
            
            if result:
                if isinstance(result, Persona):
                    success = self.expert_repository.add_persona(result)
                else:
                    success = self.expert_repository.add_skill(result)
                
                return {
                    "type": obj_type,
                    "success": success,
                    "id": result.id,
                    "name": result.name,
                    "message": f"成功导入{obj_type}: {result.name}" if success else "导入失败，可能已存在"
                }
            else:
                return {"success": False, "message": "解析失败"}
        except Exception as e:
            return {"success": False, "message": f"导入失败: {str(e)}"}
    
    def import_from_zip(self, zip_path: str) -> Dict[str, Any]:
        """
        从 ZIP 压缩包批量导入
        
        Returns:
            {"success": bool, "personas": count, "skills": count, "message": str}
        """
        try:
            imported_personas = 0
            imported_skills = 0
            errors = []
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for filename in zf.namelist():
                    if filename.endswith('/') or filename.startswith('_'):
                        continue
                    
                    try:
                        content = zf.read(filename).decode('utf-8')
                        
                        if '/personas/' in filename or filename.startswith('personas/'):
                            if filename.endswith('.md'):
                                result = self.import_persona_from_markdown(content)
                            else:
                                continue
                            
                            if result and self.expert_repository.add_persona(result):
                                imported_personas += 1
                            
                        elif '/skills/' in filename or filename.startswith('skills/'):
                            if filename.endswith('.md'):
                                result = self.import_skill_from_markdown(content)
                            else:
                                continue
                            
                            if result and self.expert_repository.add_skill(result):
                                imported_skills += 1
                    except Exception as e:
                        errors.append(f"{filename}: {str(e)}")
            
            message = f"导入完成：人格 {imported_personas} 个，技能包 {imported_skills} 个"
            if errors:
                message += f"\n错误: {len(errors)}"
            
            return {
                "success": True,
                "personas": imported_personas,
                "skills": imported_skills,
                "errors": errors,
                "message": message
            }
        except Exception as e:
            return {"success": False, "message": f"导入失败: {str(e)}"}
    
    # ── 辅助方法 ───────────────────────────────────────────────────────
    
    def _parse_persona_markdown(self, content: str) -> Optional[Dict]:
        """解析 Markdown 为人格数据"""
        data = {
            "id": "",
            "name": "",
            "description": "",
            "domain": "general",
            "trigger_conditions": [],
            "system_prompt": "",
            "traits": {},
            "skill_ids": [],
            "is_builtin": False,
            "is_active": True,
        }
        
        lines = content.split('\n')
        current_section = None
        in_system_prompt = False
        system_prompt_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # 标题
            if stripped.startswith('# '):
                data['name'] = stripped[2:].strip()
                continue
            
            # 元数据
            if stripped.startswith('**ID**:'):
                match = re.search(r'`([^`]+)`', stripped)
                if match:
                    data['id'] = match.group(1)
                continue
            
            if stripped.startswith('**领域**:'):
                data['domain'] = stripped.split('**领域**:')[1].strip()
                continue
            
            if stripped.startswith('**版本**:'):
                data['version'] = stripped.split('**版本**:')[1].strip()
                continue
            
            # 章节检测
            if stripped.startswith('## '):
                current_section = stripped[3:].strip()
                in_system_prompt = False
                
                if current_section == '描述':
                    current_section = 'description'
                elif current_section == '系统提示词':
                    in_system_prompt = True
                    current_section = 'system_prompt'
                elif current_section == '触发条件':
                    current_section = 'trigger_conditions'
                elif current_section == '人格特征':
                    current_section = 'traits'
                elif current_section == '关联技能':
                    current_section = 'skill_ids'
                continue
            
            # 内容处理
            if current_section == 'description':
                if data['description']:
                    data['description'] += '\n' + stripped
                else:
                    data['description'] = stripped
            
            elif current_section == 'system_prompt':
                if in_system_prompt and stripped == '```':
                    in_system_prompt = False
                    data['system_prompt'] = '\n'.join(system_prompt_lines).strip()
                elif in_system_prompt:
                    system_prompt_lines.append(stripped)
            
            elif current_section == 'trigger_conditions':
                if stripped.startswith('- **'):
                    # 解析触发条件
                    match = re.search(r'\*\*(\w+)\*\*: `([^`]+)`', stripped)
                    if match:
                        cond_type = match.group(1)
                        value = match.group(2)
                        cond = {"type": cond_type, "value": value, "weight": 1.0}
                        
                        # 检查阈值
                        threshold_match = re.search(r'阈值[:：]\s*(\d+\.?\d*)', stripped)
                        if threshold_match:
                            cond["threshold"] = float(threshold_match.group(1))
                        
                        data["trigger_conditions"].append(cond)
            
            elif current_section == 'traits':
                if stripped.startswith('- **'):
                    match = re.search(r'\*\*(\w+)\*\*:\s*(.+)', stripped)
                    if match:
                        data["traits"][match.group(1)] = match.group(2).strip()
            
            elif current_section == 'skill_ids':
                if stripped.startswith('- `'):
                    match = re.search(r'`([^`]+)`', stripped)
                    if match:
                        data["skill_ids"].append(match.group(1))
        
        # 生成默认 ID
        if not data.get('id') and data.get('name'):
            data['id'] = data['name'].lower().replace(' ', '_')
        
        return data if data.get('name') else None
    
    def _parse_skill_markdown(self, content: str) -> Optional[Dict]:
        """解析 Markdown 为技能包数据"""
        data = {
            "id": "",
            "name": "",
            "description": "",
            "category": "general",
            "trigger_keywords": [],
            "trigger_domains": [],
            "instructions": "",
            "prompts": [],
            "tool_names": [],
            "is_builtin": False,
            "is_active": True,
        }
        
        lines = content.split('\n')
        current_section = None
        in_instructions = False
        instruction_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('# '):
                data['name'] = stripped[2:].strip()
                continue
            
            if stripped.startswith('**ID**:'):
                match = re.search(r'`([^`]+)`', stripped)
                if match:
                    data['id'] = match.group(1)
                continue
            
            if stripped.startswith('**分类**:'):
                data['category'] = stripped.split('**分类**:')[1].strip()
                continue
            
            if stripped.startswith('## '):
                section = stripped[3:].strip()
                current_section = section
                in_instructions = False
                
                if section == '描述':
                    current_section = 'description'
                elif section == '触发关键词':
                    current_section = 'trigger_keywords'
                elif section == '触发领域':
                    current_section = 'trigger_domains'
                elif section == '技能指令':
                    in_instructions = True
                    current_section = 'instructions'
                elif section == '示例提示词':
                    current_section = 'prompts'
                elif section == '关联工具':
                    current_section = 'tool_names'
                continue
            
            if current_section == 'description':
                if data['description']:
                    data['description'] += '\n' + stripped
                else:
                    data['description'] = stripped
            
            elif current_section == 'trigger_keywords':
                # 解析关键词列表
                keywords = re.findall(r'`([^`]+)`', stripped)
                data['trigger_keywords'].extend(keywords)
            
            elif current_section == 'trigger_domains':
                domains = re.findall(r'`([^`]+)`', stripped)
                data['trigger_domains'].extend(domains)
            
            elif current_section == 'instructions':
                if in_instructions and stripped == '```':
                    in_instructions = False
                    data['instructions'] = '\n'.join(instruction_lines).strip()
                elif in_instructions:
                    instruction_lines.append(stripped)
            
            elif current_section == 'prompts':
                if stripped and not stripped.startswith('#'):
                    # 移除序号
                    match = re.search(r'^\d+\.\s*(.+)', stripped)
                    if match:
                        data['prompts'].append(match.group(1))
            
            elif current_section == 'tool_names':
                if stripped.startswith('- `'):
                    match = re.search(r'`([^`]+)`', stripped)
                    if match:
                        data['tool_names'].append(match.group(1))
        
        if not data.get('id') and data.get('name'):
            data['id'] = data['name'].lower().replace(' ', '_')
        
        return data if data.get('name') else None
