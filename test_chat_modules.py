"""
聊天模块测试脚本
"""

import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent/client')

def test_business_modules():
    print("=== 测试业务模块 ===")
    
    from client.src.business.nanochat_config import config
    print(f"✓ 配置模块: Ollama URL = {config.ollama.url}")
    
    from client.src.business.vector_db_integration import get_tool_registry
    registry = get_tool_registry()
    print(f"✓ 向量数据库集成: 工具数={len(registry.get_all_tools())}")
    
    from client.src.business.function_knowledge import get_knowledge_base, FUNCTION_MODULES
    kb = get_knowledge_base()
    print(f"✓ 功能模块知识库: {len(FUNCTION_MODULES)} 个模块")
    
    # 测试推荐功能
    test_queries = [
        "帮我写一本小说",
        "我想搜索一些信息",
        "创建一个项目",
        "玩游戏"
    ]
    
    for query in test_queries:
        module = kb.recommend_module(query)
        if module:
            print(f"  推荐测试: '{query}' -> {module.name}")
    
    print()

def test_ui_components():
    print("=== 测试UI组件 ===")
    
    from client.src.presentation.components.ui_descriptor import UIComponent, UIResponse, ControlType
    print(f"✓ UI描述符: {ControlType.__members__.keys()}")
    
    from client.src.presentation.components.semantic_parser import SemanticParser
    parser = SemanticParser()
    print(f"✓ 语义解析器")
    
    from client.src.presentation.components.markdown_renderer import MarkdownRenderer
    print(f"✓ Markdown渲染器")
    
    from client.src.presentation.components.code_highlighter import CodeHighlighterWidget
    print(f"✓ 代码高亮组件")
    
    from client.src.presentation.components.command_palette import CommandPalette
    print(f"✓ 命令面板")
    
    from client.src.presentation.components.task_widget import Task, TaskItem, create_sample_tasks
    tasks = create_sample_tasks()
    print(f"✓ 任务组件: {len(tasks)} 个示例任务")
    
    print()

def test_chat_panel():
    print("=== 测试聊天面板 ===")
    
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    
    from client.src.presentation.modules.chat.panel import Panel
    panel = Panel()
    print(f"✓ 聊天面板创建成功")
    
    from client.src.presentation.modules.chat.ide_panel import IDEChatPanel
    ide_panel = IDEChatPanel()
    print(f"✓ IDE聊天面板创建成功")
    
    app.quit()
    print()

if __name__ == "__main__":
    try:
        test_business_modules()
        test_ui_components()
        test_chat_panel()
        print("=== 所有测试通过 ===")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()