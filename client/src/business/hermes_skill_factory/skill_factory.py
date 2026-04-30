"""
SkillFactory - 技能工厂主类

提供完整的技能创建、生成、注册流程。
"""

from typing import Dict, Any, Optional, List
from loguru import logger
import os

from .skill_config import SkillConfig, ToolConfig, ParameterConfig
from .skill_generator import SkillGenerator
from .registry_integrator import SkillRegistryIntegrator
from .skill_template_engine import SkillTemplateEngine


class SkillFactory:
    """技能工厂主类"""

    def __init__(self):
        self._logger = logger.bind(component="SkillFactory")
        self._generator = SkillGenerator()
        self._integrator = SkillRegistryIntegrator()
        self._template_engine = SkillTemplateEngine()
        self._config_dir = self._get_config_dir()

    def _get_config_dir(self) -> str:
        """获取配置目录"""
        config_dir = os.path.join(
            os.path.dirname(__file__),
            "configs"
        )
        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def create_tool_config(self, name: str, description: str,
                          category: str = "general", node_type: str = "deterministic",
                          parameters: Optional[List[Dict[str, Any]]] = None,
                          examples: Optional[List[Dict[str, Any]]] = None) -> ToolConfig:
        """
        创建工具配置
        
        Args:
            name: 工具名称
            description: 工具描述
            category: 工具类别
            node_type: 节点类型 (deterministic/ai)
            parameters: 参数列表
            examples: 示例列表
            
        Returns:
            ToolConfig 对象
        """
        param_configs = []
        if parameters:
            for param_data in parameters:
                param_configs.append(ParameterConfig.from_dict(param_data))
        
        return ToolConfig(
            name=name,
            description=description,
            category=category,
            node_type=node_type,
            parameters=param_configs,
            examples=examples or []
        )

    def create_skill_config(self, tools: Optional[List[ToolConfig]] = None) -> SkillConfig:
        """
        创建技能配置
        
        Args:
            tools: 工具配置列表
            
        Returns:
            SkillConfig 对象
        """
        return SkillConfig(tools=tools or [])

    def generate_tool(self, tool_config: ToolConfig, output_path: Optional[str] = None) -> str:
        """
        生成工具代码并保存到文件
        
        Args:
            tool_config: 工具配置
            output_path: 输出路径
            
        Returns:
            输出文件路径
        """
        filepath = self._generator.write_tool_file(tool_config, output_path)
        self._logger.info(f"生成工具: {filepath}")
        return filepath

    def generate_skill_module(self, config: SkillConfig, module_name: str,
                             output_path: Optional[str] = None) -> str:
        """
        生成技能模块
        
        Args:
            config: 技能配置
            module_name: 模块名称
            output_path: 输出路径
            
        Returns:
            输出文件路径
        """
        filepath = self._generator.write_skill_module(config, module_name, output_path)
        self._logger.info(f"生成技能模块: {filepath}")
        return filepath

    def generate_from_config(self, config: SkillConfig, output_dir: Optional[str] = None) -> List[str]:
        """
        从配置生成所有技能
        
        Args:
            config: 技能配置
            output_dir: 输出目录
            
        Returns:
            生成的文件路径列表
        """
        generated_files = []
        
        for tool in config.tools:
            filepath = self.generate_tool(tool)
            generated_files.append(filepath)
        
        return generated_files

    def generate_from_config_file(self, config_file: str, output_dir: Optional[str] = None) -> List[str]:
        """
        从配置文件生成技能
        
        Args:
            config_file: 配置文件路径
            output_dir: 输出目录
            
        Returns:
            生成的文件路径列表
        """
        return self._generator.generate_from_config_file(config_file, output_dir)

    def register_tool(self, tool_instance) -> bool:
        """
        注册工具到注册中心
        
        Args:
            tool_instance: BaseTool 实例
            
        Returns:
            是否成功
        """
        return self._integrator.register_tool(tool_instance)

    def register_from_file(self, file_path: str) -> List[str]:
        """
        从文件注册工具
        
        Args:
            file_path: 工具文件路径
            
        Returns:
            成功注册的工具名称列表
        """
        return self._integrator.register_from_module(file_path)

    def register_from_directory(self, directory: str) -> List[str]:
        """
        从目录注册所有工具
        
        Args:
            directory: 目录路径
            
        Returns:
            成功注册的工具名称列表
        """
        return self._integrator.register_from_directory(directory)

    def publish_skill(self, skill_id: str, user_id: str = "system") -> bool:
        """
        发布技能
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            
        Returns:
            是否成功
        """
        return self._integrator.publish_skill(skill_id, user_id)

    def create_and_register(self, name: str, description: str,
                           category: str = "general", node_type: str = "deterministic",
                           parameters: Optional[List[Dict[str, Any]]] = None,
                           examples: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        创建工具并注册到系统
        
        Args:
            name: 工具名称
            description: 工具描述
            category: 工具类别
            node_type: 节点类型
            parameters: 参数列表
            examples: 示例列表
            
        Returns:
            是否成功
        """
        try:
            # 创建配置
            tool_config = self.create_tool_config(
                name=name,
                description=description,
                category=category,
                node_type=node_type,
                parameters=parameters,
                examples=examples
            )
            
            # 生成代码
            filepath = self.generate_tool(tool_config)
            
            # 注册到系统
            registered = self.register_from_file(filepath)
            
            if registered:
                self._logger.info(f"成功创建并注册工具: {name}")
                return True
            else:
                return False
                
        except Exception as e:
            self._logger.error(f"创建并注册工具失败 {name}: {e}")
            return False

    def batch_create_from_config(self, config_file: str, register: bool = True) -> Dict[str, Any]:
        """
        批量从配置文件创建并注册技能
        
        Args:
            config_file: 配置文件路径
            register: 是否注册到系统
            
        Returns:
            结果统计
        """
        try:
            # 生成技能文件
            generated_files = self.generate_from_config_file(config_file)
            
            result = {
                "success": True,
                "generated_files": generated_files,
                "generated_count": len(generated_files),
                "registered_count": 0,
                "registered_names": []
            }
            
            # 如果需要注册
            if register:
                for filepath in generated_files:
                    registered = self.register_from_file(filepath)
                    result["registered_count"] += len(registered)
                    result["registered_names"].extend(registered)
            
            self._logger.info(f"批量创建完成: {result}")
            return result
            
        except Exception as e:
            self._logger.error(f"批量创建失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "generated_files": [],
                "generated_count": 0,
                "registered_count": 0,
                "registered_names": []
            }

    def get_stats(self) -> Dict[str, Any]:
        """获取技能工厂统计信息"""
        return {
            "generated_skills": self._generator.list_generated_skills(),
            "registry_stats": self._integrator.get_stats(),
            "available_templates": self._template_engine.get_template_names()
        }

    def save_config(self, config: SkillConfig, filename: str):
        """
        保存配置到文件
        
        Args:
            config: 技能配置
            filename: 文件名（不含扩展名）
        """
        yaml_path = os.path.join(self._config_dir, f"{filename}.yaml")
        config.save_to_yaml(yaml_path)
        self._logger.info(f"配置已保存: {yaml_path}")

    def load_config(self, filename: str) -> SkillConfig:
        """
        从文件加载配置
        
        Args:
            filename: 文件名（不含扩展名）
            
        Returns:
            SkillConfig 对象
        """
        yaml_path = os.path.join(self._config_dir, f"{filename}.yaml")
        return SkillConfig.from_yaml_file(yaml_path)

    def add_template(self, template_name: str, template_content: str):
        """
        添加自定义模板
        
        Args:
            template_name: 模板名称
            template_content: 模板内容
        """
        self._template_engine.add_template(template_name, template_content)

    def list_templates(self) -> List[str]:
        """列出可用模板"""
        return self._template_engine.get_template_names()

    def validate_tool_config(self, tool_config: ToolConfig) -> bool:
        """
        验证工具配置
        
        Args:
            tool_config: 工具配置
            
        Returns:
            是否有效
        """
        if not tool_config.name:
            self._logger.error("工具名称不能为空")
            return False
            
        if not tool_config.description:
            self._logger.error("工具描述不能为空")
            return False
            
        # 验证参数名称唯一性
        param_names = [p.name for p in tool_config.parameters]
        if len(param_names) != len(set(param_names)):
            self._logger.error("参数名称重复")
            return False
            
        return True