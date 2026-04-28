"""
AutonomousToolCreator - 自主工具创建器

功能：智能体能够自主编写代码，创建新工具。

工作流程：
1. 学习阶段：搜索知识库和网络，学习如何创建这个工具
2. 代码生成阶段：让 LLM 生成工具代码
3. 写入文件阶段：将代码写入到正确位置
4. 测试阶段：测试工具是否有效
5. 反思与改进阶段：如果测试失败，反思并改进代码
6. 注册阶段：注册到 ToolRegistry
"""

import os
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from client.src.business.tools.tool_registry import ToolRegistry


class AutonomousToolCreator:
    """
    自主工具创建器
    
    功能：智能体能够自主编写代码，创建新工具。
    
    用法：
        creator = AutonomousToolCreator()
        success = await creator.create_tool("weather_tool", "获取天气信息")
    """
    
    def __init__(self, llm_client=None, work_dir: str = None):
        """
        初始化自主工具创建器
        
        Args:
            llm_client: LLM 客户端
            work_dir: 工作目录（工具创建位置）
        """
        self._llm = llm_client
        self._work_dir = work_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "client", "src", "business", "tools"
        )
        self._logger = logger.bind(component="AutonomousToolCreator")
    
    async def create_tool(
        self,
        tool_name: str,
        tool_description: str,
        context: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        自主创建工具（完整闭环）
        
        Args:
            tool_name: 工具名称
            tool_description: 工具描述
            context: 上下文信息（可选）
            
        Returns:
            (是否成功, 工具文件路径)
        """
        self._logger.info(f"开始创建工具: {tool_name}")
        self._logger.info(f"工具描述: {tool_description}")
        
        try:
            # 1. 学习阶段
            self._logger.info("阶段 1: 学习如何创建工具...")
            learning_materials = await self._learn_how_to_create(tool_name, tool_description, context)
            
            # 2. 代码生成阶段
            self._logger.info("阶段 2: 生成工具代码...")
            code = await self._generate_tool_code(tool_name, tool_description, learning_materials)
            
            # 3. 写入文件阶段
            self._logger.info("阶段 3: 写入文件...")
            file_path = await self._write_code_to_file(tool_name, code)
            
            # 4. 测试阶段
            self._logger.info("阶段 4: 测试工具...")
            test_result = await self._test_tool(file_path)
            
            # 5. 反思与改进阶段（如果测试失败）
            if not test_result.success:
                self._logger.warning(f"测试失败，进入反思与改进阶段...")
                return await self._reflect_and_improve(
                    tool_name, code, test_result, file_path, max_retries=3
                )
            
            # 6. 注册阶段
            self._logger.info("阶段 5: 注册工具...")
            await self._register_tool(tool_name, file_path)
            
            self._logger.info(f"工具创建成功: {tool_name}")
            return True, file_path
            
        except Exception as e:
            self._logger.error(f"创建工具失败: {e}")
            import traceback
            self._logger.error(traceback.format_exc())
            return False, None
    
    async def _learn_how_to_create(
        self,
        tool_name: str,
        tool_description: str,
        context: Optional[str] = None
    ) -> str:
        """学习如何创建工具"""
        self._logger.info("  正在学习如何创建工具...")
        
        learning_materials = ""
        
        # 1. 搜索知识库
        try:
            self._logger.info("    - 搜索知识库...")
            kb_results = await self._search_knowledge_base(tool_name)
            learning_materials += f"\n\n## 知识库搜索结果：\n{kb_results}"
        except Exception as e:
            self._logger.warning(f"    - 知识库搜索失败: {e}")
        
        # 2. 搜索网络（使用 DeepSearch）
        try:
            self._logger.info("    - 搜索网络...")
            web_results = await self._deep_search(f"Python 实现 {tool_name} 工具")
            learning_materials += f"\n\n## 网络搜索结果：\n{web_results}"
        except Exception as e:
            self._logger.warning(f"    - 网络搜索失败: {e}")
            # 如果访问失败，尝试使用代理源
            try:
                self._logger.info("    - 尝试使用代理源...")
                proxy = await self._get_proxy()
                web_results = await self._deep_search(f"Python 实现 {tool_name} 工具", proxy=proxy)
                learning_materials += f"\n\n## 网络搜索结果（代理）:\n{web_results}"
            except Exception as e2:
                self._logger.warning(f"    - 代理搜索也失败: {e2}")
        
        # 3. 查看已有工具示例
        self._logger.info("    - 读取已有工具示例...")
        example_tools = await self._read_example_tools(["web_crawler_tool", "deep_search_tool"])
        learning_materials += f"\n\n## 已有工具示例：\n{example_tools}"
        
        # 4. 如果是 CLI 工具，获取帮助文档
        if "CLI" in tool_description or "cli" in tool_name.lower():
            self._logger.info("    - 获取 CLI 工具帮助文档...")
            cli_help = await self._get_cli_tool_help(tool_name)
            learning_materials += f"\n\n## CLI 工具帮助文档：\n{cli_help}"
        
        # 5. 整合学习材料
        if context:
            learning_materials += f"\n\n## 上下文信息：\n{context}"
        
        self._logger.info("  学习阶段完成")
        
        return learning_materials
    
    async def _generate_tool_code(
        self,
        tool_name: str,
        tool_description: str,
        learning_materials: str
    ) -> str:
        """生成工具代码"""
        self._logger.info("  正在生成工具代码...")
        
        prompt = f"""
你是 Python 工具开发专家。

请为以下工具生成完整的 Python 代码：

工具名称：{tool_name}
工具描述：{tool_description}

学习材料：
{learning_materials[:2000]}  # 限制长度

=== 简单优先原则（必须遵守）===
1. KEEP IT SIMPLE: 优先选择最简单的解决方案
2. NO OVER-ENGINEERING: 避免过度工程化，不使用不必要的抽象
3. MINIMAL DEPENDENCIES: 使用最少的依赖
4. STRAIGHTFORWARD: 代码应该直接、易于理解
5. AVOID PATTERNS: 除非绝对必要，否则不要使用设计模式
6. SINGLE RESPONSIBILITY: 工具只做一件事，并且做好

=== 代码要求 ===
1. 创建一个继承自 BaseTool 的工具类
2. 类名格式：{tool_name.title().replace('_', '')}Tool
3. 实现 __init__ 方法和 execute 方法
4. 添加完整的文档字符串
5. 处理所有可能的异常
6. 返回 ToolResult 对象
7. 保持代码简洁，避免不必要的复杂性
8. 不要创建不必要的辅助类或函数
9. 优先使用标准库，避免引入额外依赖

代码模板：
```python
from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from loguru import logger


class {tool_name.title().replace('_', '')}Tool(BaseTool):
    \"\"\"{tool_description}\"\"\"
    
    def __init__(self):
        super().__init__(
            name="{tool_name}",
            description="{tool_description}",
            category="auto",
            tags=["auto", "{tool_name}"]
        )
        # 初始化代码（保持简单）
        
    def execute(self, **kwargs):
        \"\"\"
        执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            ToolResult
        \"\"\"
        try:
            # 直接、简单的执行逻辑
            result = None  # 替换为实际逻辑
            
            return ToolResult.ok(
                data=result,
                message=f"{tool_name} executed successfully"
            )
        except Exception as e:
            logger.error(f"{tool_name} execution failed: {{e}}")
            return ToolResult.fail(error=str(e))
```

请只输出完整的 Python 代码，不要有任何其他输出。
"""
        
        try:
            response = await self._call_llm(prompt)
            
            # 提取代码块
            code = self._extract_code(response)
            
            # 检查代码复杂度（简单优先约束）
            complexity_result = self._check_simple_first(code)
            if not complexity_result["pass"]:
                self._logger.warning(f"  代码复杂度检查失败: {complexity_result['reason']}")
                # 重新生成代码
                self._logger.info("  重新生成代码以满足简单优先原则...")
                simple_prompt = f"""
以下代码不符合简单优先原则：

代码：
{code}

问题：{complexity_result['reason']}

请简化代码，遵循以下原则：
1. 移除不必要的抽象和类
2. 使用简单直接的实现
3. 减少不必要的依赖
4. 保持代码行数最少

请只输出简化后的完整 Python 代码。
"""
                response = await self._call_llm(simple_prompt)
                code = self._extract_code(response)
            
            self._logger.info("  代码生成完成")
            
            return code
            
        except Exception as e:
            self._logger.error(f"  代码生成失败: {e}")
            raise
    
    def _check_simple_first(self, code: str) -> Dict[str, Any]:
        """
        检查代码是否符合简单优先原则
        
        Args:
            code: 生成的代码
            
        Returns:
            {"pass": bool, "reason": str}
        """
        lines = code.strip().split('\n')
        line_count = len(lines)
        
        # 检查代码行数（不应超过 100 行）
        if line_count > 100:
            return {"pass": False, "reason": f"代码行数过多 ({line_count} 行)，应简化"}
        
        # 检查类数量（应该只有一个工具类）
        class_count = sum(1 for line in lines if line.strip().startswith('class '))
        if class_count > 1:
            return {"pass": False, "reason": f"类数量过多 ({class_count} 个)，应只保留一个工具类"}
        
        # 检查函数数量（应该只有必要的方法）
        func_count = sum(1 for line in lines if line.strip().startswith('def '))
        if func_count > 5:  # __init__, execute, 以及最多 3 个辅助方法
            return {"pass": False, "reason": f"函数数量过多 ({func_count} 个)，应简化"}
        
        # 检查导入数量（应最少）
        import_count = sum(1 for line in lines if line.strip().startswith(('import ', 'from ')))
        if import_count > 5:
            return {"pass": False, "reason": f"导入数量过多 ({import_count} 个)，应减少依赖"}
        
        # 检查嵌套层数（不应过深）
        max_indent = 0
        for line in lines:
            indent = len(line) - len(line.lstrip())
            if indent > max_indent:
                max_indent = indent
        if max_indent > 20:  # 超过 5 层嵌套（每层约 4 空格）
            return {"pass": False, "reason": f"代码嵌套过深 (缩进 {max_indent} 空格)，应简化"}
        
        # 检查是否有不必要的设计模式术语
        pattern_terms = ["Singleton", "Factory", "Builder", "Observer", "Strategy", "Decorator"]
        for term in pattern_terms:
            if term in code:
                return {"pass": False, "reason": f"使用了不必要的设计模式 ({term})"}
        
        return {"pass": True, "reason": "代码符合简单优先原则"}
    
    async def _write_code_to_file(self, tool_name: str, code: str) -> str:
        """将代码写入到文件"""
        self._logger.info("  正在写入文件...")
        
        # 确保目录存在
        os.makedirs(self._work_dir, exist_ok=True)
        
        # 构建文件路径
        file_name = f"{tool_name}_tool.py"
        file_path = os.path.join(self._work_dir, file_name)
        
        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        
        self._logger.info(f"  文件已写入: {file_path}")
        
        return file_path
    
    async def _test_tool(self, file_path: str) -> ToolResult:
        """测试工具是否有效"""
        self._logger.info("  正在测试工具...")
        
        try:
            # 导入模块
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_module", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找 Tool 类
            tool_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseTool) and attr != BaseTool:
                    tool_class = attr
                    break
            
            if tool_class is None:
                return ToolResult.fail(error="未找到 BaseTool 子类")
            
            # 实例化并测试
            tool_instance = tool_class()
            
            # 测试基本属性
            if not tool_instance.name:
                return ToolResult.fail(error="工具名称为空")
            
            self._logger.info("  测试通过")
            
            return ToolResult.ok(data={"tool_name": tool_instance.name}, message="测试通过")
            
        except Exception as e:
            self._logger.error(f"  测试失败: {e}")
            return ToolResult.fail(error=str(e))
    
    async def _reflect_and_improve(
        self,
        tool_name: str,
        code: str,
        test_result: ToolResult,
        file_path: str,
        max_retries: int = 3
    ) -> Tuple[bool, Optional[str]]:
        """反思与改进（如果测试失败）"""
        self._logger.info(f"  反思与改进（最多 {max_retries} 次）...")
        
        for i in range(max_retries):
            self._logger.info(f"  重试 {i+1}/{max_retries}...")
            
            # 让 LLM 分析错误并改进代码
            prompt = f"""
你是代码调试专家。

以下代码在测试时失败：

代码：
{code}

错误信息：
{test_result.error}

请分析错误原因，并给出修正后的完整代码。

要求：
1. 只输出完整的 Python 代码
2. 不要有任何其他输出
3. 确保代码可以正确导入和执行
"""
            
            try:
                response = await self._call_llm(prompt)
                improved_code = self._extract_code(response)
                
                # 写入改进后的代码
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(improved_code)
                
                # 重新测试
                test_result = await self._test_tool(file_path)
                
                if test_result.success:
                    self._logger.info(f"  改进成功（第 {i+1} 次尝试）")
                    return True, file_path
                
            except Exception as e:
                self._logger.error(f"  改进失败: {e}")
        
        self._logger.error(f"  改进失败（已达到最大重试次数 {max_retries}）")
        return False, file_path
    
    async def _register_tool(self, tool_name: str, file_path: str):
        """注册工具到 ToolRegistry"""
        self._logger.info(f"  正在注册工具: {tool_name}...")
        
        try:
            # 导入模块
            import importlib.util
            spec = importlib.util.spec_from_file_location("register_module", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找 Tool 类并实例化
            tool_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseTool) and attr != BaseTool:
                    tool_class = attr
                    break
            
            if tool_class is None:
                raise ValueError("未找到 BaseTool 子类")
            
            # 注册到 ToolRegistry
            registry = ToolRegistry.get_instance()
            tool_instance = tool_class()
            success = registry.register_tool(tool_instance)
            
            if success:
                self._logger.info(f"  工具已注册: {tool_instance.name}")
            else:
                self._logger.warning(f"  工具注册失败（可能已存在）: {tool_instance.name}")
            
        except Exception as e:
            self._logger.error(f"  注册失败: {e}")
            raise
    
    async def _search_knowledge_base(self, query: str) -> str:
        """搜索知识库"""
        try:
            # 尝试使用知识库搜索
            from client.src.business.knowledge_vector_db import VectorDatabase
            db = VectorDatabase()
            results = db.search(query, top_k=3)
            return "\n".join([r.get("content", "") for r in results])
        except Exception:
            return "知识库搜索不可用"
    
    async def _deep_search(self, query: str, proxy: Optional[str] = None) -> str:
        """深度搜索"""
        try:
            from client.src.business.deep_search_wiki.wiki_generator import LLMWikiGenerator
            generator = LLMWikiGenerator()
            result = await generator.generate_wiki(query)
            return result[:1000] if result else "深度搜索无结果"
        except Exception:
            return "深度搜索不可用"
    
    async def _get_proxy(self) -> Optional[str]:
        """获取代理"""
        try:
            from client.src.business.base_proxy_manager import ProxyManager
            manager = ProxyManager()
            return manager.get_best_proxy()
        except Exception:
            return None
    
    async def _read_example_tools(self, tool_names: List[str]) -> str:
        """读取已有工具示例"""
        examples = []
        
        for tool_name in tool_names:
            file_path = os.path.join(self._work_dir, f"{tool_name}.py")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    examples.append(f"### {tool_name}.py\n\n{content[:500]}...")
        
        return "\n\n".join(examples) if examples else "无可用示例"
    
    async def _get_cli_tool_help(self, tool_name: str) -> str:
        """获取 CLI 工具帮助文档"""
        try:
            import subprocess
            result = subprocess.run(
                [tool_name, "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout or result.stderr or "无帮助文档"
        except Exception:
            return "无法获取帮助文档"
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if self._llm is not None:
            return await self._llm.chat(prompt, model="qwen3.6:35b-a3b")
        else:
            try:
                from client.src.business.hermes_agent.llm_client import LLMClient
                llm = LLMClient()
                return await llm.chat(prompt, model="qwen3.6:35b-a3b")
            except Exception as e:
                self._logger.error(f"调用 LLM 失败: {e}")
                raise
    
    def _extract_code(self, response: str) -> str:
        """从 LLM 响应中提取代码"""
        # 尝试提取代码块
        import re
        code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            return code_match.group(1)
        
        # 如果没有代码块，假设整个响应都是代码
        return response.strip()


async def test_autonomous_tool_creator():
    """测试自主工具创建器"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 配置 loguru
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 AutonomousToolCreator")
    print("=" * 60)
    
    # 创建创建器
    creator = AutonomousToolCreator()
    
    # 测试创建工具
    test_tool_name = "hello_world"
    test_tool_description = "打印 Hello World 的测试工具"
    
    print(f"\n测试创建工具: {test_tool_name}")
    print(f"工具描述: {test_tool_description}")
    
    success, file_path = await creator.create_tool(test_tool_name, test_tool_description)
    
    if success:
        print(f"\n[PASS] 工具创建成功: {file_path}")
    else:
        print(f"\n[FAIL] 工具创建失败")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_autonomous_tool_creator())
