"""
测试 markitdown 集成和 Markdown 输出格式
"""

import sys
import os
import importlib.util

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 测试文档解析器集成 markitdown
print("测试 markitdown 集成...")

# 直接导入模块，避免 __init__.py 的依赖问题
doc_parser_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'business', 'bilingual_doc', 'document_parser.py'
)
spec = importlib.util.spec_from_file_location("document_parser", doc_parser_path)
doc_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doc_module)

DocumentParser = doc_module.DocumentParser
MarkItDownParser = doc_module.MarkItDownParser
MARKITDOWN_AVAILABLE = doc_module.MARKITDOWN_AVAILABLE

# 测试文档解析器初始化
parser = DocumentParser()
print(f"✓ 文档解析器初始化成功")
print(f"✓ MarkItDown 可用: {MARKITDOWN_AVAILABLE}")

# 测试支持的格式
formats = parser.supported_formats()
print(f"✓ 支持的格式: {len(formats)} 种")

# 测试 MarkItDownParser 类
md_parser = MarkItDownParser()
supported_extensions = md_parser.SUPPORTED_EXTENSIONS
print(f"✓ MarkItDown 支持: {len(supported_extensions)} 种格式")

# 测试 Markdown 输出格式
print("\n测试工具输出 Markdown 格式...")

# 导入工具模块
import importlib.util
tool_module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'business', 'tools', 'base_tool.py'
)
spec = importlib.util.spec_from_file_location("base_tool", tool_module_path)
tool_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool_module)

AgentCallResult = tool_module.AgentCallResult

# 测试成功结果的 Markdown 输出
result = AgentCallResult.success(
    data={
        "name": "测试工具",
        "result": "成功",
        "details": {"value": 100, "unit": "%"},
        "items": ["item1", "item2", "item3", "item4", "item5", "item6"]
    },
    message="执行成功",
    evidence={"timestamp": "2024-01-15"}
)

# 设置验证信息
result.set_verification(
    criteria=["数据完整性", "格式正确性"],
    checks=[
        {"name": "数据不为空", "passed": True, "value": True},
        {"name": "格式正确", "passed": True, "value": "json"}
    ],
    score=1.0,
    explanation="所有验证通过"
)

md_output = result.to_markdown()
print("✓ Markdown 输出生成成功")

# 验证输出内容
assert "## ✅ 执行成功" in md_output
assert "### 📊 结果数据" in md_output
assert "### ✔️ 验证结果" in md_output
assert "### 📝 证据" in md_output
print("✓ Markdown 输出格式正确")

# 测试失败结果的 Markdown 输出
error_result = AgentCallResult.error(error="测试错误", message="执行失败")
error_md = error_result.to_markdown()
assert "## ❌ 执行失败" in error_md
assert "### 错误信息" in error_md
print("✓ 错误结果 Markdown 输出正确")

# 测试长列表输出（确保有限制）
long_list = ["item" + str(i) for i in range(15)]
long_result = AgentCallResult.success(data=long_list, message="长列表测试")
long_md = long_result.to_markdown()
assert "查看详细列表" in long_md  # 使用折叠
assert "... (共 15 项)" in long_md
print("✓ 长列表输出正确处理")

print("\n🎉 所有测试通过!")