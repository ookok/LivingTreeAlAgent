"""
自动测试生成示例

展示如何使用自动测试生成功能：
1. 根据业务逻辑生成测试代码
2. 自动查找测试数据
3. 批量生成模块测试
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ui_automation import (
    # 资源定位
    ResourceLocator,
    get_resource_locator,
    find_test_resource,
    find_test_data_file,

    # 代码分析
    CodeAnalyzer,
    ClassInfo,

    # 测试生成
    TestCodeGenerator,
    TestSuiteGenerator,
    auto_generate_tests,
    generate_opencode_ide_tests,
)


def demo_resource_locator():
    """演示资源定位功能"""
    print("\n" + "="*60)
    print("1. 资源定位器演示")
    print("="*60)

    locator = get_resource_locator()

    # 扫描资源
    print("\n扫描 localresources...")
    files = locator.scan()
    print(f"找到 {len(files)} 个文件")

    # 根据关键词查找
    print("\n查找 'chat' 相关文件:")
    chat_files = locator.find_by_keywords(["chat"], limit=5)
    for f in chat_files:
        print(f"  - {f.path} ({f.category.value})")

    # 查找 Python 文件
    print("\n查找 OpenCode IDE 相关 Python 文件:")
    python_files = locator.find_python_files(["opencode", "ide", "panel"], limit=5)
    for f in python_files:
        print(f"  - {f.path}")

    # 查找测试数据
    print("\n查找测试数据:")
    test_files = locator.find_test_data(related_to="opencode_ide_panel.py", limit=5)
    for f in test_files:
        print(f"  - {f.path}")


def demo_code_analysis():
    """演示代码分析功能"""
    print("\n" + "="*60)
    print("2. 代码分析器演示")
    print("="*60)

    analyzer = CodeAnalyzer()

    # 分析 ChatHistoryManager 类
    from client.src.presentation.modules.ide.opencode_ide_panel import ChatHistoryManager

    class_info = analyzer.analyze_class(ChatHistoryManager)

    print(f"\n类名: {class_info.name}")
    print(f"模块: {class_info.module}")
    print(f"基类: {class_info.bases}")
    print(f"公开方法: {len(class_info.methods)}")

    for method in class_info.methods:
        print(f"  - {method.name}{method.signature}")

    return class_info


def demo_test_generation(class_info: ClassInfo):
    """演示测试代码生成"""
    print("\n" + "="*60)
    print("3. 测试代码生成演示")
    print("="*60)

    generator = TestCodeGenerator(template="pytest")

    # 查找测试数据
    locator = get_resource_locator()
    test_files = locator.find_test_data(related_to=class_info.name, limit=3)
    test_data_paths = [f.full_path for f in test_files]

    # 生成测试代码
    test_code = generator.generate_tests(
        class_info,
        test_data_files=test_data_paths
    )

    print("\n生成的测试代码片段:")
    print("-"*40)
    lines = test_code.split('\n')
    for i, line in enumerate(lines[:50]):  # 只显示前50行
        print(line)
    if len(lines) > 50:
        print(f"... ({len(lines) - 50} more lines)")


def demo_opencode_ide_test_generation():
    """演示为 OpenCode IDE 生成测试"""
    print("\n" + "="*60)
    print("4. OpenCode IDE 测试套件生成")
    print("="*60)

    # 生成测试
    tests = generate_opencode_ide_tests()

    print(f"\n生成了 {len(tests)} 个测试文件:")
    for name in tests:
        print(f"  - {name}")

    # 保存测试文件（可选）
    output_dir = os.path.join(os.path.dirname(__file__), "generated")
    os.makedirs(output_dir, exist_ok=True)

    for name, code in tests.items():
        output_path = os.path.join(output_dir, name)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"  已保存: {output_path}")


def demo_auto_import_test():
    """演示自动导入和测试"""
    print("\n" + "="*60)
    print("5. 自动导入测试演示")
    print("="*60)

    # 直接使用 auto_generate_tests 函数
    from client.src.presentation.modules.ide.opencode_ide_panel import (
        ActivityBar,
        MessageBubble,
        ChatHistoryManager,
    )

    for cls in [ActivityBar, MessageBubble, ChatHistoryManager]:
        print(f"\n分析类: {cls.__name__}")
        test_code = auto_generate_tests(cls, template="pytest")
        print(f"生成测试代码 {len(test_code)} 字符")


def main():
    """主函数"""
    print("="*60)
    print("PyQt6 UI 自动化测试框架 - 自动测试生成演示")
    print("="*60)

    # 1. 资源定位
    demo_resource_locator()

    # 2. 代码分析
    class_info = demo_code_analysis()

    # 3. 测试生成
    demo_test_generation(class_info)

    # 4. OpenCode IDE 测试生成
    try:
        demo_opencode_ide_test_generation()
    except Exception as e:
        print(f"\n注意: OpenCode IDE 测试生成跳过 ({e})")

    # 5. 自动导入测试
    demo_auto_import_test()

    print("\n" + "="*60)
    print("演示完成!")
    print("="*60)


if __name__ == "__main__":
    main()
