"""
AI Code Generator - AI代码生成器
==================================

使用AI生成功能脚本，支持从自然语言描述生成Python代码。

生成的代码会被送入沙箱执行，确保安全性。
"""

import json
import re
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class CodeGenerationContext:
    """代码生成上下文"""
    available_apis: dict = field(default_factory=dict)
    template_library: dict = field(default_factory=dict)
    security_rules: list = field(default_factory=list)
    user_preferences: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class GeneratedCode:
    """生成的代码"""
    code: str
    language: str = "python"
    description: str = ""
    function_name: str = ""
    parameters: list = field(default_factory=list)
    return_type: str = "Any"
    imports: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "language": self.language,
            "description": self.description,
            "function_name": self.function_name,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "imports": self.imports,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class CodeTemplate:
    """代码模板"""

    TEMPLATES = {
        "simple_action": '''def {function_name}({params}):
    """
    {description}

    Args:
{param_docs}
    Returns:
        Any: 执行结果
    """
    try:
        # TODO: 实现功能逻辑
        result = None
        return result
    except Exception as e:
        print(f"Error in {function_name}: {{e}}")
        return None
''',

        "async_action": '''async def {function_name}({params}):
    """
    {description}

    Args:
{param_docs}
    Returns:
        Any: 执行结果
    """
    import asyncio
    try:
        # TODO: 实现异步功能逻辑
        result = await asyncio.sleep(0.1)  # 模拟异步操作
        return result
    except Exception as e:
        print(f"Error in {function_name}: {{e}}")
        return None
''',

        "button_handler": '''def handle_{button_id}_click(event):
    """
    处理 {button_name} 按钮点击事件

    Args:
        event: 点击事件对象
    """
    print(f"{button_name} clicked")
    # 添加你的逻辑
''',

        "data_processor": '''def process_{data_type}_data(input_data):
    """
    处理 {data_type} 类型数据

    Args:
        input_data: 输入数据

    Returns:
        dict: 处理后的数据
    """
    result = {{
        "status": "success",
        "data": input_data,
        "processed_at": None,
    }}
    # TODO: 添加数据处理逻辑
    return result
''',

        "api_caller": '''async def call_{api_name}_api({params}):
    """
    调用 {api_name} API

{param_docs}
    Returns:
        dict: API响应
    """
    import httpx

    url = "{api_url}"
    headers = {{}}
    data = {{}}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        print(f"HTTP error: {{e}}")
        return {{"error": str(e)}}
    except Exception as e:
        print(f"Error: {{e}}")
        return {{"error": str(e)}}
''',
    }

    @classmethod
    def get_template(cls, template_name: str) -> Optional[str]:
        """获取模板"""
        return cls.TEMPLATES.get(template_name)


class AICodeGenerator:
    """AI代码生成器"""

    # 系统提示词
    SYSTEM_PROMPT = """你是一个专业的Python代码生成助手。根据用户的自然语言描述，生成安全、高效的Python函数代码。

要求：
1. 函数名清晰、符合Python命名规范
2. 包含完整的docstring文档
3. 有完善的错误处理
4. 返回明确的结果
5. 代码简洁、注释完整
6. 不生成危险操作（如exec、eval、subprocess等）

只返回函数代码，不要返回其他内容。
"""

    # 用户提示词模板
    USER_PROMPT_TEMPLATE = '''根据以下描述生成Python函数：

功能描述：{description}

可用API：{available_apis}

参数要求：{param_requirements}

约束条件：{constraints}

只返回函数代码，不要其他内容。
'''

    def __init__(self):
        self.context = CodeGenerationContext()
        self.templates = CodeTemplate()
        self._load_default_apis()

    def _load_default_apis(self):
        """加载默认API"""
        self.context.available_apis = {
            "print": {"description": "打印输出", "params": ["*args"]},
            "len": {"description": "获取长度", "params": ["obj"]},
            "str": {"description": "转换为字符串", "params": ["obj"]},
            "int": {"description": "转换为整数", "params": ["obj"]},
            "float": {"description": "转换为浮点数", "params": ["obj"]},
            "list": {"description": "创建列表", "params": ["iterable"]},
            "dict": {"description": "创建字典", "params": ["**kwargs"]},
            "range": {"description": "生成序列", "params": ["start", "stop", "step"]},
            "enumerate": {"description": "枚举", "params": ["iterable"]},
            "sorted": {"description": "排序", "params": ["iterable", "key", "reverse"]},
            "filter": {"description": "过滤", "params": ["function", "iterable"]},
            "map": {"description": "映射", "params": ["function", "iterable"]},
            "json.dumps": {"description": "JSON序列化", "params": ["obj"]},
            "json.loads": {"description": "JSON反序列化", "params": ["s"]},
            "time.sleep": {"description": "延时", "params": ["seconds"]},
            "datetime.now": {"description": "获取当前时间", "params": []},
        }

    def set_context(self, context: CodeGenerationContext):
        """设置生成上下文"""
        self.context = context

    async def generate_async(self, description: str, intent_type: str = "simple") -> GeneratedCode:
        """异步生成代码"""
        import asyncio
        return await asyncio.to_thread(self.generate, description, intent_type)

    def generate(self, description: str, intent_type: str = "simple") -> GeneratedCode:
        """
        根据描述生成代码

        Args:
            description: 功能描述
            intent_type: 意图类型 (simple, async, button_handler, data_processor, api_caller)

        Returns:
            GeneratedCode: 生成的代码对象
        """
        # 选择模板
        template_name = self._get_template_name(intent_type, description)
        template = self.templates.get_template(template_name)

        if not template:
            # 使用默认模板生成
            return self._generate_from_description(description)
        else:
            return self._generate_from_template(description, template)

    def _get_template_name(self, intent_type: str, description: str) -> str:
        """根据意图类型和描述选择模板"""
        description_lower = description.lower()

        if "异步" in description or "async" in description_lower or "等待" in description:
            return "async_action"
        elif "按钮" in description or "点击" in description or "button" in description_lower:
            return "button_handler"
        elif "处理" in description or "数据" in description or "process" in description_lower:
            return "data_processor"
        elif "API" in description or "调用" in description or "http" in description_lower:
            return "api_caller"
        else:
            return "simple_action"

    def _generate_from_template(self, description: str, template: str) -> GeneratedCode:
        """使用模板生成代码"""
        # 解析描述，提取关键信息
        info = self._parse_description(description)

        # 构建函数签名
        params = ", ".join([p["name"] for p in info["params"]])
        param_docs = "\n".join([f"        {p['name']} ({p['type']}): {p['description']}" for p in info["params"]])

        # 替换模板占位符
        code = template.format(
            function_name=info["function_name"],
            params=params,
            description=info["description"],
            param_docs=param_docs,
            button_id=info.get("button_id", "unknown"),
            button_name=info.get("button_name", "Unknown"),
            data_type=info.get("data_type", "unknown"),
            api_name=info.get("api_name", "unknown"),
            api_url=info.get("api_url", ""),
        )

        return GeneratedCode(
            code=code,
            language="python",
            description=info["description"],
            function_name=info["function_name"],
            parameters=info["params"],
            imports=self._extract_imports(code),
            warnings=self._check_code_warnings(code),
        )

    def _generate_from_description(self, description: str) -> GeneratedCode:
        """直接从描述生成代码"""
        info = self._parse_description(description)

        # 生成基本函数结构
        code = f'''def {info["function_name"]}():
    """
    {info["description"]}

    Returns:
        Any: 执行结果
    """
    # TODO: 实现功能逻辑
    pass
'''
        return GeneratedCode(
            code=code,
            language="python",
            description=info["description"],
            function_name=info["function_name"],
            parameters=[],
            warnings=["代码未完成，需要人工实现"],
        )

    def _parse_description(self, description: str) -> dict:
        """解析描述，提取关键信息"""
        info = {
            "description": description,
            "function_name": self._generate_function_name(description),
            "params": [],
            "button_id": "",
            "button_name": "",
            "data_type": "",
            "api_name": "",
            "api_url": "",
        }

        # 提取按钮信息
        if "按钮" in description:
            match = re.search(r"([\w]+)按钮", description)
            if match:
                info["button_name"] = match.group(1)
                info["button_id"] = self._to_snake_case(info["button_name"])

        # 提取数据类型
        if "数据" in description:
            match = re.search(r"([\w]+)数据", description)
            if match:
                info["data_type"] = match.group(1)

        # 提取API名称
        if "API" in description or "接口" in description:
            match = re.search(r"([\w]+)(?:API|接口)", description)
            if match:
                info["api_name"] = match.group(1)

        # 提取URL
        url_match = re.search(r"https?://[^\s]+", description)
        if url_match:
            info["api_url"] = url_match.group(0)

        # 提取参数
        param_matches = re.findall(r"(\w+)参数|参数(\w+)", description)
        for p in param_matches:
            param_name = p[0] or p[1]
            if param_name and param_name not in ["参数"]:
                info["params"].append({
                    "name": self._to_snake_case(param_name),
                    "type": "Any",
                    "description": f"{param_name}参数",
                })

        return info

    def _generate_function_name(self, description: str) -> str:
        """从描述生成函数名"""
        # 移除常见动词和描述词
        words = description.replace("实现", "").replace("功能", "").replace("一个", "")
        words = re.sub(r"[^\w]", "_", words)
        words = re.sub(r"_+", "_", words).strip("_")

        # 如果函数名为空或太短，使用默认名
        if len(words) < 2:
            words = "custom_function"

        # 确保是有效的Python函数名
        if not words[0].isalpha() and words[0] != "_":
            words = "f_" + words

        return words.lower()[:50]  # 限制长度

    def _to_snake_case(self, text: str) -> str:
        """转换为蛇形命名"""
        text = re.sub(r"([A-Z])", r"_\1", text)
        text = text.replace(" ", "_").replace("-", "_")
        return text.lower().strip("_")

    def _extract_imports(self, code: str) -> list:
        """提取代码中的导入语句"""
        imports = []
        for line in code.split("\n"):
            if line.strip().startswith("import ") or line.strip().startswith("from "):
                imports.append(line.strip())
        return imports

    def _check_code_warnings(self, code: str) -> list:
        """检查代码警告"""
        warnings = []

        # 检查危险操作
        dangerous_patterns = [
            (r"exec\s*\(", "使用exec()存在安全风险"),
            (r"eval\s*\(", "使用eval()存在安全风险"),
            (r"__import__\s*\(", "使用__import__()存在安全风险"),
            (r"subprocess\s*\.", "subprocess模块可能存在安全风险"),
            (r"os\.system\s*\(", "os.system()可能存在安全风险"),
            (r"open\s*\([^)]*['\"]w['\"]", "文件写入操作需要谨慎处理路径"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):
                warnings.append(message)

        # 检查TODO标记
        if "# TODO" in code or "# TODO:" in code:
            warnings.append("代码包含未完成的TODO")

        return warnings

    def format_code(self, code: str) -> str:
        """格式化代码（简单版本）"""
        lines = code.split("\n")
        formatted_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()

            # 减少缩进
            if stripped.startswith("return ") or stripped.startswith("break") or stripped.startswith("continue"):
                indent_level = max(0, indent_level - 1)

            formatted_lines.append("    " * indent_level + stripped)

            # 增加缩进
            if stripped.endswith(":") and not stripped.startswith("#"):
                indent_level += 1

        return "\n".join(formatted_lines)


# 全局单例
_code_generator: Optional[AICodeGenerator] = None


def get_code_generator() -> AICodeGenerator:
    """获取代码生成器单例"""
    global _code_generator
    if _code_generator is None:
        _code_generator = AICodeGenerator()
    return _code_generator