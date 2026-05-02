"""
行动细胞模块

包含：
- ActionCell: 通用行动细胞
- CodeCell: 代码生成细胞
- ToolCell: 工具调用细胞
- GenerationCell: 内容生成细胞
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import asyncio
from .cell import Cell, CellType


class ActionType(Enum):
    """行动类型"""
    CODE_GENERATION = "code_generation"   # 代码生成
    TOOL_CALL = "tool_call"               # 工具调用
    TEXT_GENERATION = "text_generation"   # 文本生成
    FILE_OPERATION = "file_operation"     # 文件操作
    API_CALL = "api_call"                 # API调用
    UI_ACTION = "ui_action"               # UI操作


class ActionCell(Cell):
    """
    通用行动细胞
    
    负责输出执行和外部交互。
    """
    
    def __init__(self, specialization: str = "general"):
        super().__init__(specialization)
        self.supported_actions: List[ActionType] = [ActionType.TEXT_GENERATION]
    
    @property
    def cell_type(self) -> CellType:
        return CellType.ACTION
    
    async def _process_signal(self, message: dict) -> Any:
        """
        处理行动请求
        
        支持的消息类型：
        - 'execute': 执行行动
        - 'generate': 生成内容
        - 'call_tool': 调用工具
        """
        message_type = message.get('type', '')
        
        if message_type == 'execute':
            return await self._execute(
                action_type=message.get('action_type', 'text_generation'),
                params=message.get('params', {})
            )
        
        elif message_type == 'generate':
            return await self._generate(
                prompt=message.get('prompt', ''),
                format=message.get('format', 'text')
            )
        
        elif message_type == 'call_tool':
            return await self._call_tool(
                tool_name=message.get('tool_name', ''),
                args=message.get('args', {})
            )
        
        return {'error': f"Unknown message type: {message_type}"}
    
    async def _execute(self, action_type: str = "text_generation", 
                      params: dict = None) -> Dict[str, Any]:
        """
        执行行动
        
        Args:
            action_type: 行动类型
            params: 行动参数
        
        Returns:
            执行结果
        """
        params = params or {}
        
        try:
            action_enum = ActionType(action_type.lower())
        except ValueError:
            return {'success': False, 'error': f"Invalid action type: {action_type}"}
        
        if action_enum not in self.supported_actions:
            return {'success': False, 'error': f"Action type {action_type} not supported"}
        
        # 根据类型执行行动
        if action_enum == ActionType.TEXT_GENERATION:
            result = await self._generate_text(params.get('prompt', ''))
        elif action_enum == ActionType.CODE_GENERATION:
            result = await self._generate_code(params.get('prompt', ''), params.get('language', 'python'))
        elif action_enum == ActionType.FILE_OPERATION:
            result = await self._file_operation(params.get('operation', ''), params.get('path', ''))
        elif action_enum == ActionType.API_CALL:
            result = await self._api_call(params.get('url', ''), params.get('method', 'GET'), params.get('data', {}))
        else:
            result = {'output': 'Action executed'}
        
        return {'success': True, 'action_type': action_type, 'result': result}
    
    async def _generate(self, prompt: str, format: str = "text") -> Dict[str, Any]:
        """
        生成内容
        
        Args:
            prompt: 生成提示
            format: 输出格式
        
        Returns:
            生成结果
        """
        if format == 'json':
            result = await self._generate_json(prompt)
        elif format == 'code':
            result = await self._generate_code(prompt, 'python')
        elif format == 'markdown':
            result = await self._generate_markdown(prompt)
        else:
            result = await self._generate_text(prompt)
        
        return {'success': True, 'format': format, 'output': result}
    
    async def _call_tool(self, tool_name: str, args: dict = None) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            args: 工具参数
        
        Returns:
            调用结果
        """
        args = args or {}
        
        # 简单的工具调用模拟
        tools = {
            'search': lambda: {'results': ['result1', 'result2']},
            'calculator': lambda: {'result': args.get('expression', '0')},
            'file_reader': lambda: {'content': 'file content'},
            'web_scraper': lambda: {'content': 'scraped content'}
        }
        
        if tool_name in tools:
            result = tools[tool_name]()
            self.record_success()
            return {'success': True, 'tool_name': tool_name, 'result': result}
        
        return {'success': False, 'error': f"Tool {tool_name} not found"}
    
    async def _generate_text(self, prompt: str) -> str:
        """生成文本"""
        return f"Generated text based on prompt: {prompt[:50]}..."
    
    async def _generate_json(self, prompt: str) -> dict:
        """生成JSON"""
        return {
            'generated': True,
            'prompt_summary': prompt[:50],
            'data': {'key': 'value'}
        }
    
    async def _generate_markdown(self, prompt: str) -> str:
        """生成Markdown"""
        return f"# Generated Content\n\nBased on: {prompt[:50]}...\n\n## Section\n\nContent here."
    
    async def _generate_code(self, prompt: str, language: str = "python") -> str:
        """生成代码"""
        return f"# {language} code generated\n\nprint('Generated from: {prompt[:30]}')"
    
    async def _file_operation(self, operation: str, path: str) -> Dict[str, Any]:
        """文件操作"""
        return {
            'operation': operation,
            'path': path,
            'success': True
        }
    
    async def _api_call(self, url: str, method: str = "GET", data: dict = None) -> Dict[str, Any]:
        """API调用"""
        return {
            'url': url,
            'method': method,
            'status': 200,
            'data': data or {}
        }


class CodeCell(ActionCell):
    """
    代码生成细胞
    
    专门用于代码生成、代码审查和代码调试。
    """
    
    def __init__(self):
        super().__init__(specialization="code")
        self.supported_actions = [ActionType.CODE_GENERATION]
        self.supported_languages = ['python', 'javascript', 'typescript', 'java', 'go', 'rust']
        self.max_code_length = 10000
    
    async def _process_signal(self, message: dict) -> Any:
        """处理代码相关请求"""
        message_type = message.get('type', '')
        
        if message_type == 'generate_code':
            return await self._generate_code_with_context(
                prompt=message.get('prompt', ''),
                language=message.get('language', 'python'),
                context=message.get('context', '')
            )
        
        elif message_type == 'review_code':
            return await self._review_code(
                code=message.get('code', ''),
                language=message.get('language', 'python')
            )
        
        elif message_type == 'debug_code':
            return await self._debug_code(
                code=message.get('code', ''),
                error=message.get('error', '')
            )
        
        return await super()._process_signal(message)
    
    async def _generate_code_with_context(self, prompt: str, language: str = "python", 
                                         context: str = "") -> Dict[str, Any]:
        """
        生成代码（带上下文）
        
        Args:
            prompt: 代码生成提示
            language: 目标语言
            context: 上下文信息
        
        Returns:
            代码生成结果
        """
        if language not in self.supported_languages:
            return {'success': False, 'error': f"Language {language} not supported"}
        
        code = f"""# {language} code generated
# Prompt: {prompt[:50]}...
# Context provided: {'Yes' if context else 'No'}

"""
        
        # 根据语言生成不同的代码模板
        if language == 'python':
            code += """def solution():
    \"\"\"Generated solution\"\"\"
    # Implementation based on requirements
    result = process_input()
    return result
"""
        elif language == 'javascript':
            code += """function solution() {
    // Implementation based on requirements
    const result = processInput();
    return result;
}
"""
        
        self.record_success()
        return {
            'success': True,
            'language': language,
            'code': code,
            'code_length': len(code),
            'context_used': len(context) > 0
        }
    
    async def _review_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        代码审查
        
        Args:
            code: 待审查的代码
            language: 代码语言
        
        Returns:
            审查结果
        """
        issues = []
        
        # 简单的代码审查规则
        if len(code) > 5000:
            issues.append({'severity': 'warning', 'message': 'Code is too long', 'line': 0})
        
        if 'print(' in code and 'debug' in code.lower():
            issues.append({'severity': 'info', 'message': 'Debug print statement found', 'line': code.count('\n') + 1})
        
        if 'TODO' in code:
            issues.append({'severity': 'info', 'message': 'TODO comment found', 'line': code.count('\n') + 1})
        
        return {
            'success': True,
            'issues_found': len(issues),
            'issues': issues,
            'code_lines': code.count('\n') + 1
        }
    
    async def _debug_code(self, code: str, error: str = "") -> Dict[str, Any]:
        """
        代码调试
        
        Args:
            code: 待调试的代码
            error: 错误信息
        
        Returns:
            调试结果
        """
        suggestions = []
        
        if error:
            if 'SyntaxError' in error:
                suggestions.append("检查代码语法，可能存在括号不匹配或缺少冒号")
            if 'IndentationError' in error:
                suggestions.append("检查代码缩进，Python对缩进非常敏感")
            if 'NameError' in error:
                suggestions.append("检查变量是否已定义，可能存在拼写错误")
        
        # 添加通用建议
        suggestions.append("添加更多调试日志来追踪执行流程")
        suggestions.append("使用单元测试来验证各部分功能")
        
        return {
            'success': True,
            'error_analyzed': bool(error),
            'suggestions': suggestions,
            'debug_steps': ['分析错误信息', '定位问题代码', '修复并测试']
        }


class ToolCell(ActionCell):
    """
    工具调用细胞
    
    专门用于调用外部工具和API。
    """
    
    def __init__(self):
        super().__init__(specialization="tool")
        self.supported_actions = [ActionType.TOOL_CALL, ActionType.API_CALL]
        self.registered_tools = {}
    
    def register_tool(self, tool_name: str, tool_func: callable, description: str = ""):
        """
        注册工具
        
        Args:
            tool_name: 工具名称
            tool_func: 工具函数
            description: 工具描述
        """
        self.registered_tools[tool_name] = {
            'func': tool_func,
            'description': description,
            'call_count': 0
        }
    
    def unregister_tool(self, tool_name: str):
        """注销工具"""
        if tool_name in self.registered_tools:
            del self.registered_tools[tool_name]
    
    async def _call_tool(self, tool_name: str, args: dict = None) -> Dict[str, Any]:
        """
        调用工具（支持已注册的工具）
        
        Args:
            tool_name: 工具名称
            args: 工具参数
        
        Returns:
            调用结果
        """
        args = args or {}
        
        if tool_name in self.registered_tools:
            tool_info = self.registered_tools[tool_name]
            
            try:
                result = await tool_info['func'](**args) if asyncio.iscoroutinefunction(tool_info['func']) else tool_info['func'](**args)
                tool_info['call_count'] += 1
                
                self.record_success()
                return {
                    'success': True,
                    'tool_name': tool_name,
                    'result': result,
                    'call_count': tool_info['call_count']
                }
            except Exception as e:
                self.record_error()
                return {'success': False, 'tool_name': tool_name, 'error': str(e)}
        
        # 尝试通用工具调用
        return await super()._call_tool(tool_name, args)


class GenerationCell(ActionCell):
    """
    内容生成细胞
    
    专门用于高质量内容生成。
    """
    
    def __init__(self):
        super().__init__(specialization="generation")
        self.supported_actions = [ActionType.TEXT_GENERATION]
        self.supported_formats = ['text', 'json', 'markdown', 'html', 'latex']
    
    async def _generate(self, prompt: str, format: str = "text") -> Dict[str, Any]:
        """
        生成高质量内容
        
        Args:
            prompt: 生成提示
            format: 输出格式
        
        Returns:
            生成结果
        """
        if format not in self.supported_formats:
            return {'success': False, 'error': f"Format {format} not supported"}
        
        # 根据格式生成内容
        if format == 'html':
            output = await self._generate_html(prompt)
        elif format == 'latex':
            output = await self._generate_latex(prompt)
        else:
            output = await super()._generate(prompt, format)
        
        self.record_success()
        return {'success': True, 'format': format, 'output': output}
    
    async def _generate_html(self, prompt: str) -> str:
        """生成HTML内容"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Generated Content</title>
</head>
<body>
    <h1>Generated from: {prompt[:30]}...</h1>
    <p>Auto-generated HTML content.</p>
</body>
</html>"""
    
    async def _generate_latex(self, prompt: str) -> str:
        """生成LaTeX内容"""
        return f"""\\documentclass{{article}}
\\begin{{document}}

\\title{{Generated Document}}
\\author{{LivingTreeAI}}
\\date{{\\today}}

\\maketitle

\\section{{Introduction}}
Generated from prompt: {prompt[:50]}...

\\end{{document}}"""