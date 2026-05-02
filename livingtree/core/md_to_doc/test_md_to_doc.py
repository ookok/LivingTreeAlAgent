# -*- coding: utf-8 -*-
"""
Markdown转Word文档系统测试
===========================
"""

import sys
import os
import io

# 设置输出编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, 'd:/mhzyapp/hermes-desktop')

from livingtree.core.md_to_doc import (
    ConversionConfig, TargetFormat, ImageMode, LinkMode, CodeHighlight,
    Task, TaskStatus, DocumentNode, DocumentElement, ElementType,
    parse_markdown, get_builtin_templates, create_progress_info,
    StepStatus
)
from .converter import ConversionEngine, quick_convert, generate_docx
from .docx_generator import DOCXGenerator
from .markdown_parser import MarkdownParser


def test_markdown_parser():
    """测试Markdown解析器"""
    print("\n" + "="*60)
    print("测试1: Markdown解析器")
    print("="*60)

    markdown_text = """# 测试文档

这是一个测试文档，包含以下元素：

## 标题2

这是正文内容，包含**粗体**和*斜体*。

### 代码示例

```python
def hello():
    print("Hello, World!")
```

### 列表

- 无序列表项1
- 无序列表项2

1. 有序列表1
2. 有序列表2

### 表格

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| D   | E   | F   |

### 引用

> 这是一段引用文字

### 任务列表

- [x] 已完成任务
- [ ] 未完成任务

[链接示例](https://example.com)
"""

    parser = MarkdownParser()
    result = parse_markdown(markdown_text)

    if result.success:
        print("✅ Markdown解析成功!")
        print(f"   - 标题: {result.document.title}")
        print(f"   - 元素数量: {len(result.document.elements)}")

        # 统计信息
        stats = result.statistics
        print(f"   - 段落数: {stats.get('paragraph_count', 0)}")
        print(f"   - 标题数: {stats.get('heading_count', 0)}")
        print(f"   - 代码块数: {stats.get('code_block_count', 0)}")
        print(f"   - 表格数: {stats.get('table_count', 0)}")
        print(f"   - 列表数: {stats.get('list_count', 0)}")
        print(f"   - 引用数: {stats.get('blockquote_count', 0)}")
        print(f"   - 任务数: {stats.get('task_count', 0)}")
    else:
        print("❌ Markdown解析失败:")
        for error in result.errors:
            print(f"   - {error}")

    return result.success


def test_docx_generator():
    """测试DOCX生成器"""
    print("\n" + "="*60)
    print("测试2: DOCX生成器")
    print("="*60)

    markdown_text = """# 文档标题

这是正文内容。

## 二级标题

### 代码示例

```python
def hello():
    print("Hello!")
```

### 表格示例

| 姓名 | 年龄 | 城市 |
|------|------|------|
| 张三 | 25  | 北京 |
| 李四 | 30  | 上海 |

> 这是一段引用
"""

    try:
        # 生成DOCX
        output_path = os.path.join(os.path.expanduser("~"), "test_output.docx")
        success, result_path = generate_docx(markdown_text, output_path)

        if success:
            file_size = os.path.getsize(result_path)
            print(f"✅ DOCX生成成功!")
            print(f"   - 输出路径: {result_path}")
            print(f"   - 文件大小: {file_size} 字节 ({file_size/1024:.2f} KB)")

            # 清理测试文件
            # os.remove(result_path)
            return True
        else:
            print(f"❌ DOCX生成失败: {result_path}")
            return False

    except Exception as e:
        print(f"❌ DOCX生成异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_conversion_engine():
    """测试转换引擎"""
    print("\n" + "="*60)
    print("测试3: 转换引擎")
    print("="*60)

    engine = ConversionEngine()

    # 创建任务
    task = engine.create_task(
        source_files=["test_file.md"],
        target_format=TargetFormat.DOCX,
        task_name="测试任务"
    )

    print(f"✅ 任务创建成功!")
    print(f"   - 任务ID: {task.task_id}")
    print(f"   - 任务名称: {task.task_name}")
    print(f"   - 任务类型: {task.task_type.value}")
    print(f"   - 目标格式: {task.target_format.value}")
    print(f"   - 步骤数: {task.progress.total_steps}")

    # 打印步骤信息
    print("\n   转换步骤:")
    for step in task.progress.steps:
        print(f"   - {step.step_order}. {step.step_name}")

    # 验证任务获取
    retrieved_task = engine.get_task(task.task_id)
    if retrieved_task:
        print(f"\n✅ 任务获取成功!")
    else:
        print(f"\n❌ 任务获取失败!")
        return False

    # 验证任务列表
    all_tasks = engine.get_all_tasks()
    print(f"✅ 任务列表查询成功! 当前任务数: {len(all_tasks)}")

    return True


def test_config():
    """测试配置"""
    print("\n" + "="*60)
    print("测试4: 配置系统")
    print("="*60)

    config = ConversionConfig()
    config.target_format = TargetFormat.DOCX
    config.toc.generate_toc = True
    config.image.mode = ImageMode.EMBED
    config.code.highlight = CodeHighlight.COLORED
    config.page.page_size = "A4"

    print("✅ 配置创建成功!")
    print(f"   - 目标格式: {config.target_format.value}")
    print(f"   - 生成目录: {config.toc.generate_toc}")
    print(f"   - 图片模式: {config.image.mode.value}")
    print(f"   - 代码高亮: {config.code.highlight.value}")
    print(f"   - 纸张大小: {config.page.page_size}")

    # 转换为字典
    config_dict = config.to_dict()
    print(f"   - 配置JSON: {config_dict}")

    return True


def test_templates():
    """测试模板系统"""
    print("\n" + "="*60)
    print("测试5: 模板系统")
    print("="*60)

    templates = get_builtin_templates()

    print(f"✅ 内置模板加载成功! 共 {len(templates)} 个模板\n")

    for template in templates:
        print(f"📄 {template.template_name}")
        print(f"   - ID: {template.template_id}")
        print(f"   - 描述: {template.template_description}")
        print(f"   - 类别: {template.category.value}")
        print()

    return True


def test_progress():
    """测试进度系统"""
    print("\n" + "="*60)
    print("测试6: 进度系统")
    print("="*60)

    progress = create_progress_info("test-task-001")

    print("✅ 进度信息创建成功!")
    print(f"   - 任务ID: {progress.task_id}")
    print(f"   - 总步骤数: {progress.total_steps}")
    print(f"   - 开始时间: {progress.start_time}")

    # 更新步骤进度
    progress.steps[0].status = StepStatus.RUNNING
    progress.steps[0].progress = 0.5
    progress.calculate_overall_progress()
    print(f"   - 当前进度: {progress.overall_progress * 100:.1f}%")

    # 完成步骤
    progress.steps[0].status = StepStatus.COMPLETED
    progress.steps[0].progress = 1.0
    progress.calculate_overall_progress()
    print(f"   - 更新后进度: {progress.overall_progress * 100:.1f}%")

    # 转换为字典
    progress_dict = progress.to_dict()
    print(f"\n✅ 进度信息序列化成功!")

    return True


def test_knowledge_base():
    """测试知识库集成"""
    print("\n" + "="*60)
    print("测试7: 知识库集成")
    print("="*60)

    from .knowledge_base import (
        KnowledgeBaseManager, create_local_source,
        LocalFolderConnector
    )

    manager = KnowledgeBaseManager()
    print("✅ 知识库管理器创建成功!")

    # 创建本地知识源
    source = create_local_source(
        folder_path="d:/mhzyapp/hermes-desktop",
        recursive=False,
        include_patterns=["*.md"]
    )

    print(f"✅ 本地知识源创建成功!")
    print(f"   - 名称: {source.source_name}")
    print(f"   - 类型: {source.source_type.value}")
    print(f"   - 路径: {source.config.folder_path}")

    # 尝试连接
    connector = LocalFolderConnector(source)
    is_connected = connector.connect()
    print(f"   - 连接状态: {'已连接' if is_connected else '未连接'}")

    # 列出文档
    documents = connector.list_documents()
    print(f"   - 文档数量: {len(documents)}")

    return True


def test_quick_convert():
    """测试快速转换"""
    print("\n" + "="*60)
    print("测试8: 快速转换")
    print("="*60)

    # 测试文本
    test_markdown = """# 快速转换测试

这是一次快速转换测试。

## 功能特点

- 简单快捷
- 易于使用

## 代码示例

```python
print("Hello, World!")
```

| 功能 | 状态 |
|------|------|
| 转换 | ✅ |
| 预览 | ✅ |
"""

    # 直接生成
    try:
        # 使用DOCXGenerator直接生成
        generator = DOCXGenerator()
        docx_data = generator.generate_from_markdown(test_markdown)
        print(f"✅ 快速转换成功!")
        print(f"   - 数据大小: {len(docx_data)} 字节")

        # 保存测试
        test_path = os.path.join(os.path.expanduser("~"), "quick_test.docx")
        with open(test_path, 'wb') as f:
            f.write(docx_data)
        print(f"   - 测试文件: {test_path}")

        return True

    except Exception as e:
        print(f"❌ 快速转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🧪 Markdown转Word文档系统测试")
    print("="*60)

    tests = [
        ("Markdown解析器", test_markdown_parser),
        ("DOCX生成器", test_docx_generator),
        ("转换引擎", test_conversion_engine),
        ("配置系统", test_config),
        ("模板系统", test_templates),
        ("进度系统", test_progress),
        ("知识库集成", test_knowledge_base),
        ("快速转换", test_quick_convert),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # 打印总结
    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {status} - {name}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过!")
    else:
        print(f"\n⚠️  有 {total - passed} 项测试失败")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
