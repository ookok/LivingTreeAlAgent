"""
SkillGenerator - 技能代码生成器

根据配置自动生成技能代码文件。
"""

from typing import Dict, Any, Optional, List
from loguru import logger
import os
import ast
import inspect

from .skill_config import ToolConfig, SkillConfig


class SkillGenerator:
    """技能代码生成器"""

    def __init__(self):
        self._logger = logger.bind(component="SkillGenerator")
        self._output_dir = self._get_output_dir()
        from .skill_template_engine import SkillTemplateEngine
        self._template_engine = SkillTemplateEngine()

    def _get_output_dir(self) -> str:
        """获取输出目录"""
        output_dir = os.path.join(
            os.path.dirname(__file__),
            "generated"
        )
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def generate_tool_code(self, tool_config: ToolConfig) -> str:
        """
        生成单个工具的代码
        
        Args:
            tool_config: 工具配置
            
        Returns:
            生成的 Python 代码
        """
        return self._template_engine.generate_tool_code(tool_config.to_dict())

    def generate_skill_module(self, config: SkillConfig, module_name: str) -> str:
        """
        生成技能模块代码
        
        Args:
            config: 技能配置
            module_name: 模块名称
            
        Returns:
            生成的 Python 模块代码
        """
        tools_dict = [tool.to_dict() for tool in config.tools]
        return self._template_engine.generate_skill_module(tools_dict, module_name)

    def write_tool_file(self, tool_config: ToolConfig, output_path: Optional[str] = None) -> str:
        """
        将工具代码写入文件
        
        Args:
            tool_config: 工具配置
            output_path: 输出路径（可选）
            
        Returns:
            实际输出路径
        """
        if not output_path:
            filename = f"{tool_config.name}_tool.py"
            output_path = os.path.join(self._output_dir, filename)
        
        code = self.generate_tool_code(tool_config)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        self._logger.info(f"生成工具文件: {output_path}")
        return output_path

    def write_skill_module(self, config: SkillConfig, module_name: str, 
                           output_path: Optional[str] = None) -> str:
        """
        将技能模块写入文件
        
        Args:
            config: 技能配置
            module_name: 模块名称
            output_path: 输出路径（可选）
            
        Returns:
            实际输出路径
        """
        if not output_path:
            filename = f"{module_name}.py"
            output_path = os.path.join(self._output_dir, filename)
        
        code = self.generate_skill_module(config, module_name)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        self._logger.info(f"生成技能模块: {output_path}")
        return output_path

    def generate_from_config_file(self, config_file: str, output_dir: Optional[str] = None) -> List[str]:
        """
        从配置文件生成技能代码
        
        Args:
            config_file: 配置文件路径（YAML 或 JSON）
            output_dir: 输出目录（可选）
            
        Returns:
            生成的文件路径列表
        """
        # 加载配置
        if config_file.endswith('.yaml') or config_file.endswith('.yml'):
            config = SkillConfig.from_yaml_file(config_file)
        elif config_file.endswith('.json'):
            config = SkillConfig.from_json_file(config_file)
        else:
            self._logger.error(f"不支持的配置文件格式: {config_file}")
            raise ValueError(f"不支持的配置文件格式")

        # 设置输出目录
        if output_dir:
            original_output_dir = self._output_dir
            self._output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)

        generated_files = []
        
        # 为每个工具生成单独的文件
        for tool in config.tools:
            filepath = self.write_tool_file(tool)
            generated_files.append(filepath)

        # 恢复原始输出目录
        if output_dir:
            self._output_dir = original_output_dir

        self._logger.info(f"从配置文件生成 {len(generated_files)} 个技能文件")
        return generated_files

    def validate_generated_code(self, code: str) -> bool:
        """
        验证生成的代码是否合法
        
        Args:
            code: 代码字符串
            
        Returns:
            是否合法
        """
        try:
            ast.parse(code)
            self._logger.debug("代码语法验证通过")
            return True
        except SyntaxError as e:
            self._logger.error(f"代码语法错误: {e}")
            return False

    def import_and_test(self, module_path: str, tool_name: str) -> bool:
        """
        导入生成的模块并测试
        
        Args:
            module_path: 模块路径
            tool_name: 工具名称
            
        Returns:
            是否成功
        """
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("generated_module", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 检查工具类是否存在
            tool_class_name = f"{tool_name.capitalize().replace('_', '')}Tool"
            if hasattr(module, tool_class_name):
                tool_class = getattr(module, tool_class_name)
                # 尝试创建实例
                tool_instance = tool_class()
                if hasattr(tool_instance, 'name') and hasattr(tool_instance, 'execute'):
                    self._logger.info(f"成功导入并测试工具: {tool_name}")
                    return True
            return False
        except Exception as e:
            self._logger.error(f"导入测试失败 {module_path}: {e}")
            return False

    def list_generated_skills(self) -> List[str]:
        """列出已生成的技能文件"""
        files = []
        for filename in os.listdir(self._output_dir):
            if filename.endswith(".py") and "_tool.py" in filename:
                files.append(filename)
        return files

    def get_generated_skill_path(self, skill_name: str) -> Optional[str]:
        """获取已生成技能的文件路径"""
        filename = f"{skill_name}_tool.py"
        filepath = os.path.join(self._output_dir, filename)
        return filepath if os.path.exists(filepath) else None

    def update_tool(self, tool_config: ToolConfig):
        """更新已存在的工具代码"""
        filepath = self.get_generated_skill_path(tool_config.name)
        if filepath:
            self.write_tool_file(tool_config, filepath)
            self._logger.info(f"更新工具文件: {filepath}")
        else:
            self.write_tool_file(tool_config)

    def generate_skill_docstring(self, tool_config: ToolConfig) -> str:
        """
        生成技能文档字符串
        
        Args:
            tool_config: 工具配置
            
        Returns:
            文档字符串
        """
        doc_lines = [
            f'"""{tool_config.name.replace("_", " ").title()}',
            f'',
            f'{tool_config.description}',
            f'',
            f'参数:',
        ]
        
        for param in tool_config.parameters:
            required_marker = "*" if param.required else ""
            doc_lines.append(f'    {required_marker}{param.name} ({param.type}): {param.description}')
            
        if tool_config.examples:
            doc_lines.append(f'',)
            doc_lines.append(f'示例:')
            for i, example in enumerate(tool_config.examples, 1):
                doc_lines.append(f'    {i}. {example.get("description", "")}')
        
        doc_lines.append(f'"""')
        
        return "\n".join(doc_lines)