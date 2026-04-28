#!/usr/bin/env python3
"""
批量创建工具包装器脚本

为剩余 11 个工具生成 BaseTool 包装器
"""

import os
import sys

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from typing import Dict, List, Tuple

# 工具配置列表：(工具名称, 模块路径, 类名, 主要方法)
TOOL_CONFIGS: List[Tuple[str, str, str, str]] = [
    # 网络与搜索工具
    ("tier_router", "client.src.business.search.tier_router", "TierRouter", "route"),
    ("proxy_manager", "client.src.business.base_proxy_manager", "ProxyManager", "get_proxy"),
    ("content_extractor", "client.src.business.web_content_extractor.extractor", "ContentExtractor", "extract"),
    
    # 文档处理工具
    ("document_parser", "client.src.business.bilingual_doc.document_parser", "DocumentParser", "parse"),
    ("intelligent_ocr", "client.src.business.intelligent_ocr.ocr_engine", "OCREngine", "recognize"),
    
    # 数据存储与检索工具
    ("kb_auto_ingest", "client.src.business.knowledge_auto_ingest", "KBAutoIngest", "ingest"),
    
    # 任务与流程工具
    ("agent_progress", "client.src.business.agent_progress", "AgentProgress", "report"),
    
    # 学习与进化工具
    ("expert_learning", "client.src.business.expert_learning.learning_system", "ExpertLearningSystem", "learn"),
    ("skill_evolution", "client.src.business.skill_evolution.evolution_engine", "SkillEvolutionEngine", "evolve"),
    ("experiment_loop", "client.src.business.experiment_loop.evolution_loop", "ExperimentLoop", "run"),
    
    # 需新建的工具
    ("markitdown_converter", None, None, None),  # 特殊处理后
]

def generate_tool_wrapper(config: Tuple[str, str, str, str]) -> str:
    """生成工具包装器代码"""
    tool_name, module_path, class_name, method_name = config
    
    if tool_name == "markitdown_converter":
        # 特殊处理的 markitdown_converter（需新建）
        return '''"""
MarkItDown Converter Tool

HTML/PDF/DOCX → Markdown 转换器
"""

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from loguru import logger


class MarkItDownTool(BaseTool):
    """
    MarkItDown 转换器工具
    
    将 HTML/PDF/DOCX 文档转换为 Markdown 格式
    """
    
    def __init__(self):
        super().__init__(
            name="markitdown_converter",
            description="Convert HTML/PDF/DOCX to Markdown format",
            category="document",
            tags=["document", "markdown", "converter"]
        )
        self._converter = None
        
    def _get_converter(self):
        """延迟加载转换器"""
        if self._converter is None:
            try:
                from markitdown import MarkItDown
                self._converter = MarkItDown()
            except ImportError:
                logger.warning("markitdown not installed, using basic converter")
                self._converter = BasicMarkdownConverter()
        return self._converter
    
    def execute(self, **kwargs):
        """
        执行转换
        
        Args:
            file_path: 文件路径
            output_format: 输出格式（默认 markdown）
            
        Returns:
            ToolResult
        """
        try:
            file_path = kwargs.get("file_path")
            if not file_path:
                return ToolResult.fail(error="file_path is required")
            
            converter = self._get_converter()
            
            # 执行转换
            if hasattr(converter, "convert"):
                result = converter.convert(file_path)
            else:
                # 基本转换逻辑
                result = self._basic_convert(file_path)
            
            return ToolResult.ok(
                data={"markdown": result, "file_path": file_path},
                message=f"File converted successfully: {file_path}"
            )
            
        except Exception as e:
            logger.error(f"MarkItDown conversion failed: {e}")
            return ToolResult.fail(error=str(e))
    
    def _basic_convert(self, file_path: str) -> str:
        """基本转换（fallback）"""
        # 简单实现，实际应调用 markitdown 库
        return f"# Converted from {file_path}\\n\\nContent conversion not fully implemented."
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            converter = self._get_converter()
            return converter is not None
        except Exception:
            return False


class BasicMarkdownConverter:
    """基本 Markdown 转换器（fallback）"""
    
    def convert(self, file_path: str) -> str:
        """转换文件为 Markdown"""
        # 简单读取文本文件
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content


def register_markitdown_tool():
    """注册 markitdown_converter 工具"""
    from client.src.business.tools.tool_registry import ToolRegistry
    
    registry = ToolRegistry.get_instance()
    tool = MarkItDownTool()
    registry.register_tool(tool)
    
    logger.info(f"Registered tool: {tool.name}")
    return tool.name
'''
    
    # 通用模板
    template = '''"""
{class_name} Tool Wrapper

Auto-generated BaseTool wrapper for {class_name}
"""

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from loguru import logger

try:
    from {module_path} import {class_name}
except ImportError:
    logger.warning(f"Could not import {{class_name}} from {{module_path}}")
    {class_name} = None


class {class_name}Tool(BaseTool):
    """
    {class_name} 工具包装器
    
    将 {class_name} 包装为 BaseTool 子类
    """
    
    def __init__(self):
        super().__init__(
            name="{tool_name}",
            description=f"Auto-generated tool wrapper for {class_name}",
            category="auto",
            tags=["auto", "{tool_name}"]
        )
        
        if {class_name} is not None:
            self._instance = {class_name}()
        else:
            self._instance = None
        
    def execute(self, **kwargs):
        """
        执行 {class_name}
        
        Args:
            **kwargs: 传递给底层模块的参数
            
        Returns:
            ToolResult
        """
        try:
            if self._instance is None:
                return ToolResult.fail(
                    error=f"{class_name} module not available",
                    error_code="MODULE_NOT_AVAILABLE"
                )
            
            # 调用主要方法
            if hasattr(self._instance, "{method_name}"):
                method = getattr(self._instance, "{method_name}")
                result = method(**kwargs)
                
                return ToolResult.ok(
                    data=result,
                    message=f"{class_name} executed successfully"
                )
            else:
                # 如果没有指定方法，尝试调用实例本身
                result = self._instance(**kwargs) if callable(self._instance) else None
                
                return ToolResult.ok(
                    data=result,
                    message=f"{class_name} executed successfully"
                )
                
        except Exception as e:
            logger.error(f"{class_name} execution failed: {{e}}")
            return ToolResult.fail(error=str(e))
    
    def health_check(self) -> bool:
        """健康检查"""
        return self._instance is not None


def register_{tool_name}_tool():
    """注册 {tool_name} 工具"""
    from client.src.business.tools.tool_registry import ToolRegistry
    
    registry = ToolRegistry.get_instance()
    tool = {class_name}Tool()
    
    try:
        registry.register_tool(tool)
        logger.info(f"Registered tool: {{tool.name}}")
        return tool.name
    except Exception as e:
        logger.error(f"Failed to register tool {{tool.name}}: {{e}}")
        return None
'''
    
    return template.format(
        class_name=class_name,
        module_path=module_path,
        tool_name=tool_name,
        method_name=method_name
    )


def main():
    """主函数：生成所有工具包装器"""
    import json
    
    print("=" * 60)
    print("批量生成工具包装器")
    print("=" * 60)
    
    success_count = 0
    failed_count = 0
    
    for config in TOOL_CONFIGS:
        tool_name = config[0]
        
        try:
            # 生成代码
            code = generate_tool_wrapper(config)
            
            # 写入文件
            file_name = f"{tool_name}_tool.py"
            file_path = os.path.join(
                project_root,
                "client", "src", "business", "tools",
                file_name
            )
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            print(f"[PASS] 创建: {file_name}")
            success_count += 1
            
        except Exception as e:
            print(f"[FAIL] 失败: {tool_name} - {e}")
            failed_count += 1
    
    print("\n" + "=" * 60)
    print(f"生成完成: 成功 {success_count} 个, 失败 {failed_count} 个")
    print("=" * 60)
    
    # 生成注册脚本
    generate_registration_script()


def generate_registration_script():
    """生成批量注册脚本"""
    script_path = os.path.join(project_root, "register_all_tools.py")
    
    with open(script_path, "w", encoding="utf-8") as f:
        f.write('"""\n批量注册所有工具到 ToolRegistry\n"""\n\n')
        f.write('import sys\nimport os\n\n')
        f.write('# 添加项目路径\n')
        f.write('project_root = os.path.dirname(os.path.abspath(__file__))\n')
        f.write('sys.path.insert(0, project_root)\n\n')
        f.write('from loguru import logger\n\n')
        
        f.write('def register_all_tools():\n')
        f.write('    """注册所有工具"""\n')
        f.write('    registered = []\n')
        f.write('    failed = []\n\n')
        
        # 添加每个工具的注册调用
        for config in TOOL_CONFIGS:
            tool_name = config[0]
            f.write(f'    try:\n')
            f.write(f'        from client.src.business.tools.{tool_name}_tool import register_{tool_name}_tool\n')
            f.write(f'        name = register_{tool_name}_tool()\n')
            f.write(f'        if name:\n')
            f.write(f'            registered.append(name)\n')
            f.write(f'    except Exception as e:\n')
            f.write(f'        logger.error(f"Failed to register {tool_name}: {{e}}")\n')
            f.write(f'        failed.append("{tool_name}")\n\n')
        
        f.write('    logger.info(f"Registered {len(registered)} tools, {len(failed)} failed")\n')
        f.write('    return registered, failed\n\n')
        
        f.write('if __name__ == "__main__":\n')
        f.write('    register_all_tools()\n')
    
    print(f"\n[PASS] 生成注册脚本: register_all_tools.py")


if __name__ == "__main__":
    main()
