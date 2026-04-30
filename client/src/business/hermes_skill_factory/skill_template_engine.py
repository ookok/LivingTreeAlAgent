"""
SkillTemplateEngine - 技能模板引擎

提供技能代码生成的模板管理和渲染功能。
支持多种模板格式，可扩展自定义模板。
"""

from typing import Dict, Any, Optional, List
from jinja2 import Environment, FileSystemLoader, Template
from loguru import logger
import os


class SkillTemplateEngine:
    """技能模板引擎"""

    def __init__(self):
        self._logger = logger.bind(component="SkillTemplateEngine")
        self._templates_dir = self._get_templates_dir()
        self._env = self._create_jinja_env()
        self._templates = self._load_templates()

    def _get_templates_dir(self) -> str:
        """获取模板目录"""
        templates_dir = os.path.join(
            os.path.dirname(__file__),
            "templates"
        )
        os.makedirs(templates_dir, exist_ok=True)
        return templates_dir

    def _create_jinja_env(self) -> Environment:
        """创建 Jinja2 环境"""
        env = Environment(
            loader=FileSystemLoader(self._templates_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        return env

    def _load_templates(self) -> Dict[str, Template]:
        """加载所有模板"""
        templates = {}
        try:
            for filename in os.listdir(self._templates_dir):
                if filename.endswith(".j2"):
                    template_name = filename[:-3]  # 移除 .j2 后缀
                    templates[template_name] = self._env.get_template(filename)
                    self._logger.debug(f"加载模板: {template_name}")
        except Exception as e:
            self._logger.warning(f"加载模板失败: {e}")
        return templates

    def get_template_names(self) -> List[str]:
        """获取可用模板名称列表"""
        return list(self._templates.keys())

    def render_template(self, template_name: str, **context) -> str:
        """
        渲染模板
        
        Args:
            template_name: 模板名称
            **context: 渲染上下文
        
        Returns:
            渲染后的代码字符串
        """
        if template_name not in self._templates:
            self._logger.error(f"模板不存在: {template_name}")
            raise ValueError(f"模板不存在: {template_name}")

        template = self._templates[template_name]
        try:
            result = template.render(context)
            self._logger.debug(f"成功渲染模板: {template_name}")
            return result
        except Exception as e:
            self._logger.error(f"渲染模板失败 {template_name}: {e}")
            raise

    def add_template(self, template_name: str, template_content: str):
        """
        添加新模板
        
        Args:
            template_name: 模板名称
            template_content: 模板内容
        """
        template_path = os.path.join(self._templates_dir, f"{template_name}.j2")
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        # 重新加载模板
        self._templates = self._load_templates()
        self._logger.info(f"添加模板: {template_name}")

    def get_template(self, template_name: str) -> Optional[Template]:
        """获取模板对象"""
        return self._templates.get(template_name)

    def generate_tool_code(self, tool_config: Dict[str, Any], template_name: str = "base_tool") -> str:
        """
        生成工具代码
        
        Args:
            tool_config: 工具配置字典
            template_name: 模板名称
            
        Returns:
            生成的 Python 代码
        """
        return self.render_template(template_name, tool=tool_config)

    def generate_skill_module(self, tools_config: List[Dict[str, Any]], 
                              module_name: str = "generated_skills") -> str:
        """
        生成技能模块代码
        
        Args:
            tools_config: 工具配置列表
            module_name: 模块名称
            
        Returns:
            生成的 Python 模块代码
        """
        return self.render_template(
            "skill_module",
            tools=tools_config,
            module_name=module_name,
            timestamp=self._get_timestamp()
        )

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()