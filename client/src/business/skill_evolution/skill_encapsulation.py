"""
SkillEncapsulation - 技能封装流程

参考 Multica 的技能系统设计，实现从"解决方案"自动封装为技能。

功能：
1. 从对话历史提取解决方案
2. 自动生成技能代码
3. 测试和验证技能
4. 注册到技能库

遵循自我进化原则：
- 自动学习用户需求
- 自动封装为可复用技能
- 支持技能版本控制
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import asyncio


class SkillStatus(Enum):
    """技能状态"""
    DRAFT = "draft"
    TESTING = "testing"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass
class Skill:
    """技能定义"""
    skill_id: str
    name: str
    description: str
    code: str
    parameters: Dict[str, str] = field(default_factory=dict)
    returns: str = "ToolResult"
    category: str = "general"
    status: SkillStatus = SkillStatus.DRAFT
    version: str = "1.0"
    author: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    rating: float = 0.0


@dataclass
class SkillTemplate:
    """技能模板"""
    template_id: str
    name: str
    description: str
    code_pattern: str
    parameters: List[str] = field(default_factory=list)


class SkillEncapsulationEngine:
    """
    技能封装引擎
    
    核心功能：
    1. 从对话历史提取解决方案
    2. 自动生成技能代码
    3. 测试和验证技能
    4. 注册到技能库
    """
    
    def __init__(self):
        self._logger = logger.bind(component="SkillEncapsulationEngine")
        self._skills: Dict[str, Skill] = {}
        self._templates: Dict[str, SkillTemplate] = {}
        self._load_templates()
    
    def _load_templates(self):
        """加载技能模板"""
        templates = [
            SkillTemplate(
                template_id="web_search",
                name="网页搜索",
                description="使用深度搜索获取信息",
                code_pattern="""async def execute(query: str):
    results = await deep_search(query)
    return results""",
                parameters=["query"]
            ),
            SkillTemplate(
                template_id="file_process",
                name="文件处理",
                description="处理文档文件",
                code_pattern="""async def execute(file_path: str):
    content = await document_parser.parse(file_path)
    return content""",
                parameters=["file_path"]
            ),
            SkillTemplate(
                template_id="calculation",
                name="计算",
                description="执行数学计算",
                code_pattern="""async def execute(expression: str):
    result = eval(expression)
    return result""",
                parameters=["expression"]
            )
        ]
        
        for template in templates:
            self._templates[template.template_id] = template
    
    async def encapsulate_from_dialog(self, dialog_history: List[Dict[str, str]]) -> Optional[Skill]:
        """
        从对话历史封装技能
        
        Args:
            dialog_history: 对话历史列表
            
        Returns:
            封装的技能
        """
        self._logger.info("开始从对话历史封装技能")
        
        # 1. 分析对话，提取解决方案
        solution = await self._extract_solution(dialog_history)
        if not solution:
            self._logger.info("未找到可封装的解决方案")
            return None
        
        # 2. 选择合适的模板
        template = await self._select_template(solution)
        
        # 3. 生成技能代码
        skill_code = await self._generate_skill_code(solution, template)
        
        # 4. 创建技能对象
        skill = Skill(
            skill_id=f"skill_{len(self._skills) + 1}",
            name=solution.get("name", "未命名技能"),
            description=solution.get("description", ""),
            code=skill_code,
            parameters=solution.get("parameters", {}),
            category=solution.get("category", "general")
        )
        
        # 5. 测试技能
        test_result = await self._test_skill(skill)
        
        if test_result:
            skill.status = SkillStatus.ACTIVE
            self._skills[skill.skill_id] = skill
            self._logger.info(f"技能封装成功: {skill.name}")
            return skill
        else:
            skill.status = SkillStatus.TESTING
            self._skills[skill.skill_id] = skill
            self._logger.warning(f"技能测试失败，保留为测试状态: {skill.name}")
            return skill
    
    async def _extract_solution(self, dialog_history: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """提取解决方案"""
        # 简单实现：查找包含"步骤"、"方法"、"流程"等关键词的消息
        solution = {}
        steps = []
        
        for msg in dialog_history:
            content = msg.get("content", "")
            
            if "步骤" in content or "方法" in content or "流程" in content:
                solution["name"] = self._extract_name(content)
                solution["description"] = content
                steps.extend(self._extract_steps(content))
        
        if steps:
            solution["steps"] = steps
            solution["parameters"] = self._extract_parameters(steps)
        
        return solution if solution else None
    
    def _extract_name(self, content: str) -> str:
        """提取技能名称"""
        import re
        # 尝试从内容中提取名称
        patterns = [
            r"(?:为|实现|创建|开发)\s*(.+?)(?:功能|工具|技能|方法)",
            r"(?:步骤|流程)\s*(?:是)?\s*[:：]\s*(.+?)(?:\n|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        
        return "未命名技能"
    
    def _extract_steps(self, content: str) -> List[str]:
        """提取步骤"""
        import re
        # 匹配数字序号或"- "开头的列表项
        steps = re.findall(r"(?:\d+\.\s*|- )(.+?)(?=\n|$)", content)
        return [s.strip() for s in steps]
    
    def _extract_parameters(self, steps: List[str]) -> Dict[str, str]:
        """提取参数"""
        parameters = {}
        for step in steps:
            # 简单提取变量（用花括号包裹的内容）
            import re
            vars_found = re.findall(r"\{(\w+)\}", step)
            for var in vars_found:
                parameters[var] = "str"
        
        return parameters
    
    async def _select_template(self, solution: Dict[str, Any]) -> SkillTemplate:
        """选择合适的模板"""
        # 简单实现：根据内容匹配模板
        description = solution.get("description", "")
        
        if "搜索" in description or "查询" in description:
            return self._templates["web_search"]
        elif "文件" in description or "文档" in description:
            return self._templates["file_process"]
        elif "计算" in description or "数学" in description:
            return self._templates["calculation"]
        else:
            # 默认返回第一个模板
            return list(self._templates.values())[0]
    
    async def _generate_skill_code(self, solution: Dict[str, Any], template: SkillTemplate) -> str:
        """生成技能代码"""
        code = template.code_pattern
        
        # 替换参数占位符
        params = solution.get("parameters", {})
        for param_name, param_type in params.items():
            code = code.replace(f"{{{param_name}}}", param_name)
        
        # 添加步骤注释
        if "steps" in solution:
            steps_comment = "\n    # 步骤:\n"
            for i, step in enumerate(solution["steps"], 1):
                steps_comment += f"    # {i}. {step}\n"
            code = code.replace("async def", steps_comment + "async def")
        
        return code
    
    async def _test_skill(self, skill: Skill) -> bool:
        """测试技能"""
        try:
            # 简单测试：编译代码检查语法错误
            compile(skill.code, "<string>", "exec")
            self._logger.debug(f"技能 {skill.name} 语法检查通过")
            return True
        except SyntaxError as e:
            self._logger.error(f"技能 {skill.name} 语法错误: {e}")
            return False
    
    def register_skill(self, skill: Skill):
        """注册技能"""
        self._skills[skill.skill_id] = skill
        self._logger.info(f"技能已注册: {skill.name}")
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(skill_id)
    
    def list_skills(self, category: Optional[str] = None) -> List[Skill]:
        """列出技能"""
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return skills
    
    def update_skill(self, skill_id: str, updates: Dict[str, Any]):
        """更新技能"""
        skill = self._skills.get(skill_id)
        if skill:
            for key, value in updates.items():
                if hasattr(skill, key):
                    setattr(skill, key, value)
            skill.updated_at = datetime.now()
            self._logger.info(f"技能已更新: {skill.name}")
    
    def delete_skill(self, skill_id: str):
        """删除技能"""
        if skill_id in self._skills:
            del self._skills[skill_id]
            self._logger.info(f"技能已删除: {skill_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        status_counts = {}
        category_counts = {}
        
        for skill in self._skills.values():
            status_counts[skill.status.value] = status_counts.get(skill.status.value, 0) + 1
            category_counts[skill.category] = category_counts.get(skill.category, 0) + 1
        
        return {
            "total_skills": len(self._skills),
            "status_counts": status_counts,
            "category_counts": category_counts
        }