"""
SkillConverter - 技能转换器

将外部技能格式转换为 LivingTreeAlAgent 兼容的格式。
支持多种技能格式：JSON、YAML、Markdown、Python 模块等。
"""

from typing import Dict, Any, Optional, List
from loguru import logger
import os
import json
import yaml
import ast
import inspect

from client.src.business.tools.base_tool import BaseTool


class SkillConverter:
    """技能转换器"""

    def __init__(self):
        self._logger = logger.bind(component="SkillConverter")

    def convert_from_json(self, json_content: str) -> Dict[str, Any]:
        """
        从 JSON 格式转换
        
        Args:
            json_content: JSON 内容
            
        Returns:
            转换后的技能配置
        """
        try:
            data = json.loads(json_content)
            return self._normalize_skill_data(data)
        except json.JSONDecodeError as e:
            self._logger.error(f"JSON 解析失败: {e}")
            return {}

    def convert_from_yaml(self, yaml_content: str) -> Dict[str, Any]:
        """
        从 YAML 格式转换
        
        Args:
            yaml_content: YAML 内容
            
        Returns:
            转换后的技能配置
        """
        try:
            data = yaml.safe_load(yaml_content)
            return self._normalize_skill_data(data)
        except yaml.YAMLError as e:
            self._logger.error(f"YAML 解析失败: {e}")
            return {}

    def convert_from_markdown(self, md_content: str) -> Dict[str, Any]:
        """
        从 Markdown 格式转换
        
        Args:
            md_content: Markdown 内容
            
        Returns:
            转换后的技能配置
        """
        data = {
            "name": "",
            "description": "",
            "category": "other",
            "parameters": [],
            "examples": [],
            "content": md_content
        }

        lines = md_content.split('\n')
        in_code_block = False
        code_content = []

        for line in lines:
            if line.startswith("# "):
                data["name"] = line[2:].strip()
            elif line.startswith("## "):
                section = line[3:].strip().lower()
                if section == "description":
                    continue
                elif section == "parameters":
                    continue
                elif section == "examples":
                    continue
            elif data["name"] and not data["description"] and not line.startswith("#"):
                data["description"] += line + " "
            elif line.startswith("```"):
                in_code_block = not in_code_block
                if not in_code_block:
                    data["content"] = "\n".join(code_content)
            elif in_code_block:
                code_content.append(line)

        data["description"] = data["description"].strip()
        return data

    def convert_from_python(self, py_content: str) -> Dict[str, Any]:
        """
        从 Python 代码转换
        
        Args:
            py_content: Python 代码内容
            
        Returns:
            转换后的技能配置
        """
        try:
            tree = ast.parse(py_content)
            data = {
                "name": "",
                "description": "",
                "category": "other",
                "parameters": [],
                "functions": [],
                "classes": []
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    data["classes"].append(node.name)
                    # 查找类的 docstring
                    docstring = ast.get_docstring(node)
                    if docstring and not data["description"]:
                        data["description"] = docstring
                    
                    # 查找 BaseTool 子类
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "BaseTool":
                            data["name"] = node.name.replace("Tool", "")
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "parameters": []
                    }
                    for arg in node.args.args:
                        func_info["parameters"].append(arg.arg)
                    data["functions"].append(func_info)

            return self._normalize_skill_data(data)

        except SyntaxError as e:
            self._logger.error(f"Python 代码解析失败: {e}")
            return {}

    def convert_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        从文件转换
        
        Args:
            file_path: 文件路径
            
        Returns:
            转换后的技能配置
        """
        _, ext = os.path.splitext(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if ext == '.json':
                return self.convert_from_json(content)
            elif ext in ['.yaml', '.yml']:
                return self.convert_from_yaml(content)
            elif ext == '.md':
                return self.convert_from_markdown(content)
            elif ext == '.py':
                return self.convert_from_python(content)
            else:
                self._logger.warning(f"不支持的文件格式: {ext}")
                return {"content": content}
                
        except Exception as e:
            self._logger.error(f"读取文件失败 {file_path}: {e}")
            return {}

    def _normalize_skill_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化技能数据格式
        
        Args:
            data: 原始数据
            
        Returns:
            标准化后的技能配置
        """
        normalized = {
            "name": data.get("name", "unnamed_skill"),
            "description": data.get("description", ""),
            "category": data.get("category", "other"),
            "version": data.get("version", "1.0"),
            "author": data.get("author", ""),
            "parameters": data.get("parameters", []),
            "examples": data.get("examples", []),
            "content": data.get("content", ""),
            "metadata": data.get("metadata", {})
        }

        # 标准化参数格式
        normalized["parameters"] = self._normalize_parameters(normalized["parameters"])
        
        return normalized

    def _normalize_parameters(self, parameters: List[Any]) -> List[Dict[str, Any]]:
        """
        标准化参数列表
        
        Args:
            parameters: 参数列表
            
        Returns:
            标准化后的参数列表
        """
        normalized = []
        
        for param in parameters:
            if isinstance(param, str):
                normalized.append({
                    "name": param,
                    "type": "string",
                    "description": "",
                    "required": False
                })
            elif isinstance(param, dict):
                normalized.append({
                    "name": param.get("name", ""),
                    "type": param.get("type", "string"),
                    "description": param.get("description", ""),
                    "required": param.get("required", False),
                    "default": param.get("default")
                })
        
        return normalized

    def create_tool_class(self, skill_data: Dict[str, Any]) -> type:
        """
        根据技能数据创建工具类
        
        Args:
            skill_data: 技能数据
            
        Returns:
            BaseTool 子类
        """
        class_name = f"{skill_data['name'].capitalize()}Tool"
        
        async def execute(self, **kwargs):
            return {
                "success": True,
                "message": f"{skill_data['name']} 执行成功",
                "data": {
                    "params": kwargs,
                    "content": skill_data.get("content", "")
                }
            }
        
        tool_class = type(
            class_name,
            (BaseTool,),
            {
                "name": property(lambda self: skill_data["name"]),
                "description": property(lambda self: skill_data["description"]),
                "category": property(lambda self: skill_data["category"]),
                "version": property(lambda self: skill_data.get("version", "1.0")),
                "execute": execute,
                "__doc__": skill_data.get("description", "")
            }
        )
        
        return tool_class

    def convert_and_register(self, file_path: str) -> Optional[BaseTool]:
        """
        转换技能并注册到系统
        
        Args:
            file_path: 技能文件路径
            
        Returns:
            注册的工具实例
        """
        skill_data = self.convert_from_file(file_path)
        
        if not skill_data.get("name"):
            self._logger.error("技能数据缺少名称")
            return None
        
        # 创建工具类
        tool_class = self.create_tool_class(skill_data)
        
        # 创建实例
        tool_instance = tool_class()
        
        # 注册到工具注册中心
        try:
            tool_instance.register()
            self._logger.info(f"已注册技能: {skill_data['name']}")
            return tool_instance
        except Exception as e:
            self._logger.error(f"注册技能失败 {skill_data['name']}: {e}")
            return None

    def batch_convert(self, directory: str) -> List[Dict[str, Any]]:
        """
        批量转换目录中的技能文件
        
        Args:
            directory: 目录路径
            
        Returns:
            转换结果列表
        """
        results = []
        
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                result = self.convert_from_file(filepath)
                result["filename"] = filename
                results.append(result)
        
        return results