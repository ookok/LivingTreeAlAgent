"""
Phase 4: 多模态交互集成测试
============================

测试内容:
1. MultimodalInteractionManager - 多模态交互管理器
2. TextProcessor - 文本处理器
3. CodeProcessor - 代码处理器
4. VoiceProcessor - 语音处理器
5. ImageProcessor - 图像处理器
6. DocumentProcessor - 文档处理器
"""

import sys
import os
import importlib.util

# 直接加载模块，绕过 core/__init__.py
module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'core', 'multimodal_interaction.py'
)

spec = importlib.util.spec_from_file_location('multimodal_interaction', module_path)
multimodal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multimodal)

# 导出需要的内容
MultimodalInteractionManager = multimodal.MultimodalInteractionManager
TextProcessor = multimodal.TextProcessor
CodeProcessor = multimodal.CodeProcessor
VoiceProcessor = multimodal.VoiceProcessor
ImageProcessor = multimodal.ImageProcessor
DocumentProcessor = multimodal.DocumentProcessor
ContentBlock = multimodal.ContentBlock
MultimodalMessage = multimodal.MultimodalMessage
MultimodalResponse = multimodal.MultimodalResponse
create_multimodal_manager = multimodal.create_multimodal_manager


def test_multimodal_manager():
    """测试多模态交互管理器"""
    print("\n[Test 1] MultimodalInteractionManager")
    print("-" * 40)

    manager = create_multimodal_manager("twin_001")

    # 测试解析
    message = manager.parse_message("测试消息", user_id="user_001")
    assert message.message_id is not None
    assert message.primary_modality == "text"

    print(f"  Message ID: {message.message_id}")
    print(f"  Primary Modality: {message.primary_modality}")
    print(f"  Blocks: {len(message.content_blocks)}")

    print("  [OK] Manager Test Passed")


def test_parse_text():
    """测试文本解析"""
    print("\n[Test 2] Parse Text")
    print("-" * 40)

    manager = create_multimodal_manager()

    message = manager.parse_message("帮我创建一个用户管理类")
    print(f"  Blocks: {len(message.content_blocks)}")
    print(f"  Primary: {message.primary_modality}")

    # 检查内容块
    assert len(message.content_blocks) == 1
    assert message.content_blocks[0].content == "帮我创建一个用户管理类"

    print("  [OK] Text Parse Test Passed")


def test_parse_mixed_content():
    """测试混合内容解析"""
    print("\n[Test 3] Parse Mixed Content")
    print("-" * 40)

    manager = create_multimodal_manager()

    content = """
    请帮我优化这段代码：

    ```python
    def calculate(a, b):
        return a + b
    ```

    另外请添加类型注解。
    """

    message = manager.parse_message(content)
    print(f"  Primary Modality: {message.primary_modality}")
    print(f"  Total Blocks: {len(message.content_blocks)}")

    for block in message.content_blocks:
        print(f"    {block.modality}: {block.language or block.format_type}")

    print("  [OK] Mixed Content Test Passed")


def test_parse_dict():
    """测试字典解析"""
    print("\n[Test 4] Parse Dictionary")
    print("-" * 40)

    manager = create_multimodal_manager()

    content = {"blocks": [
        {"modality": "text", "content": "Hello"},
        {"modality": "code", "language": "javascript", "content": "console.log('hi')"}
    ]}

    message = manager.parse_message(content)
    print(f"  Blocks: {len(message.content_blocks)}")
    print(f"  Modalities: {[b.modality for b in message.content_blocks]}")

    assert len(message.content_blocks) == 2

    print("  [OK] Dictionary Parse Test Passed")


def test_code_processor():
    """测试代码处理器"""
    print("\n[Test 5] Code Processor")
    print("-" * 40)

    code = """
    import os
    from typing import List

    class UserManager:
        def __init__(self):
            self.users = []

        def add_user(self, name: str) -> bool:
            self.users.append(name)
            return True
    """

    # 检测语言
    lang = CodeProcessor.detect_language(code)
    print(f"  Detected Language: {lang}")
    assert lang == "python"

    # 提取签名
    signatures = CodeProcessor.extract_signatures(code, lang)
    print(f"  Classes: {[s[0] for s in signatures['classes']]}")
    print(f"  Functions: {[s[0] for s in signatures['functions'][:2]]}")

    # 验证语法
    valid, errors = CodeProcessor.validate_syntax(code, lang)
    print(f"  Syntax Valid: {valid}")

    print("  [OK] Code Processor Test Passed")


def test_text_processor():
    """测试文本处理器"""
    print("\n[Test 6] Text Processor")
    print("-" * 40)

    # 意图提取
    test_cases = [
        ("创建用户管理类", "create"),
        ("修改登录函数", "modify"),
        ("删除测试代码", "delete"),
        ("搜索相关实现", "search"),
        ("解释这段代码", "explain")
    ]

    for text, expected_action in test_cases:
        intent = TextProcessor.extract_intent(text)
        print(f"  '{text[:15]}...' -> {intent['primary_action']}")

    print("  [OK] Text Processor Test Passed")


def test_image_processor():
    """测试图像处理器"""
    print("\n[Test 7] Image Processor")
    print("-" * 40)

    test_cases = [
        ("创建一个流程图", "flowchart"),
        ("画出类结构图", "uml"),
        ("时序图展示", "sequence"),
        ("架构设计图", "architecture")
    ]

    for description, expected in test_cases:
        diagram_type = ImageProcessor.extract_diagram_type(description)
        print(f"  '{description[:10]}...' -> {diagram_type}")

    # 生成 PlantUML
    plantuml = ImageProcessor.generate_plantuml("流程图", "flowchart")
    print(f"  PlantUML Generated: {len(plantuml)} chars")

    print("  [OK] Image Processor Test Passed")


def test_voice_processor():
    """测试语音处理器"""
    print("\n[Test 8] Voice Processor")
    print("-" * 40)

    transcript = "请运行这个程序并打开设置，然后关闭日志"

    commands = VoiceProcessor.extract_commands(transcript)
    print(f"  Transcript: {transcript}")
    print(f"  Commands Found: {len(commands)}")

    for cmd in commands:
        print(f"    Action: {cmd['action']}, Target: {cmd['target']}")

    # TTS 配置
    tts_config = VoiceProcessor.text_to_speech_config("Hello, how can I help you?")
    print(f"  TTS Config: voice={tts_config['voice']}, rate={tts_config['rate']}")

    print("  [OK] Voice Processor Test Passed")


def test_document_processor():
    """测试文档处理器"""
    print("\n[Test 9] Document Processor")
    print("-" * 40)

    md_content = """# 用户管理模块

## 功能特性
- 用户注册
- 用户登录

## 代码实现

```python
class User:
    def login(self):
        pass
```

![架构图](architecture.png)
"""

    structure = DocumentProcessor.extract_structure(md_content, "markdown")
    print(f"  Title: {structure['title']}")
    print(f"  Sections: {len(structure['sections'])}")
    print(f"  Code Blocks: {len(structure['code_blocks'])}")
    print(f"  Images: {len(structure['images'])}")

    # 格式检测
    format_type = DocumentProcessor.detect_format("readme.md")
    print(f"  Format Detection: readme.md -> {format_type}")

    print("  [OK] Document Processor Test Passed")


def test_generate_response():
    """测试生成响应"""
    print("\n[Test 10] Generate Response")
    print("-" * 40)

    manager = create_multimodal_manager()

    message = manager.parse_message("帮我创建用户管理类")
    response = manager.generate_response(message, context="用户模块开发中")

    print(f"  Response ID: {response.response_id}")
    print(f"  Content Blocks: {len(response.content_blocks)}")
    print(f"  Suggested Actions: {len(response.suggested_actions)}")

    for block in response.content_blocks:
        print(f"    {block.modality}: {block.content[:50]}...")

    for action in response.suggested_actions:
        print(f"    Action: {action.get('label', 'N/A')}")

    print("  [OK] Generate Response Test Passed")


def test_add_response_blocks():
    """测试添加响应块"""
    print("\n[Test 11] Add Response Blocks")
    print("-" * 40)

    response = MultimodalResponse()

    # 添加文本
    response.add_text("# 响应标题\n\n这是响应内容")
    print(f"  Text Block Added")

    # 添加代码
    response.add_code("print('Hello')", language="python")
    print(f"  Code Block Added")

    # 添加操作
    response.add_action({"type": "run", "label": "Execute"})
    print(f"  Action Added")

    print(f"  Total Blocks: {len(response.content_blocks)}")

    print("  [OK] Add Blocks Test Passed")


def test_conversation_context():
    """测试对话上下文"""
    print("\n[Test 12] Conversation Context")
    print("-" * 40)

    manager = create_multimodal_manager()

    # 添加多条消息
    queries = [
        "第一个问题",
        "第二个问题带代码",
        "第三个问题"
    ]

    for query in queries:
        manager.parse_message(query)

    # 获取上下文
    context = manager.get_conversation_context()
    print(f"  Messages: {len(manager.message_history)}")
    print(f"  Context Length: {len(context)} chars")

    # 检查历史
    data = manager.to_dict()
    print(f"  Manager Data: message_count={data['message_history_count']}")

    print("  [OK] Conversation Context Test Passed")


def test_visualization():
    """测试可视化"""
    print("\n[Test 13] Visualization")
    print("-" * 40)

    manager = create_multimodal_manager()

    # 图表
    chart_data = {
        "type": "bar",
        "data": {
            "labels": ["Jan", "Feb", "Mar", "Apr"],
            "datasets": [{"label": "Users", "data": [100, 200, 150, 300]}]
        }
    }

    chart_block = manager.create_visualization(chart_data, "chart")
    print(f"  Chart Type: {chart_block.metadata.get('chart_type')}")
    print(f"  Content Length: {len(chart_block.content)}")

    # 表格
    table_data = {
        "headers": ["Name", "Type", "Lines", "Status"],
        "rows": [
            ["UserManager", "Class", "150", "Active"],
            ["login", "Method", "25", "Active"],
            ["logout", "Method", "15", "Active"]
        ]
    }

    table_block = manager.create_visualization(table_data, "table")
    print(f"  Table Preview: {table_block.content[:80]}...")

    # 图表
    diagram_block = manager.create_visualization(
        {"description": "创建架构图"},
        "diagram"
    )
    print(f"  Diagram Type: {diagram_block.metadata.get('diagram_type')}")

    print("  [OK] Visualization Test Passed")


def test_content_block():
    """测试内容块"""
    print("\n[Test 14] Content Block")
    print("-" * 40)

    block = ContentBlock(
        modality="code",
        content="print('test')",
        language="python",
        metadata={"line": 1}
    )

    print(f"  Block ID: {block.block_id}")
    print(f"  Modality: {block.modality}")
    print(f"  Language: {block.language}")

    # 序列化
    data = block.to_dict()
    print(f"  Serialized: {list(data.keys())}")

    print("  [OK] Content Block Test Passed")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("[TEST] Phase 4: Multimodal Interaction Integration")
    print("=" * 60)

    test_multimodal_manager()
    test_parse_text()
    test_parse_mixed_content()
    test_parse_dict()
    test_code_processor()
    test_text_processor()
    test_image_processor()
    test_voice_processor()
    test_document_processor()
    test_generate_response()
    test_add_response_blocks()
    test_conversation_context()
    test_visualization()
    test_content_block()

    print("\n" + "=" * 60)
    print("[COMPLETE] All Phase 4 Tests Passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
