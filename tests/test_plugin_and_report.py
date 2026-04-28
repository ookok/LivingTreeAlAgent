"""
测试插件化能力层和交互式报告生成器
"""

import sys
import os
import asyncio

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 测试插件管理器
print("测试插件化能力层...")

from business.plugin_manager import PluginManager, WorkMode

# 获取插件管理器实例
plugin_manager = PluginManager.get_instance()

# 测试工作模式列表
work_modes = plugin_manager.list_work_modes()
print(f"✓ 加载了 {len(work_modes)} 种工作模式")

# 检查默认工作模式
assert len(work_modes) >= 6, "至少应有6种工作模式"

# 测试获取工作模式
mode = plugin_manager.get_work_mode("report_generation")
assert mode is not None
assert mode.name == "报告生成"
print("✓ 获取工作模式成功")

# 测试激活工作模式
result = plugin_manager.activate_work_mode("report_generation")
assert result["success"] is True
assert result["mode_id"] == "report_generation"
print("✓ 激活工作模式成功")

# 测试创建自定义工作模式
custom_mode = plugin_manager.create_custom_work_mode(
    name="自定义模式",
    description="用户自定义的工作模式",
    tools=["tool1", "tool2"],
    icon="🌟",
    color="#ff0000"
)
assert custom_mode.id == "自定义模式".lower().replace(" ", "_")
assert custom_mode.icon == "🌟"
print("✓ 创建自定义工作模式成功")

# 测试报告生成器
print("\n测试交互式报告生成器...")

from business.report_generator import ReportGenerator, ContentBlockType

# 创建报告生成器
generator = ReportGenerator()

# 创建报告
report = generator.create_report("测试报告", "这是一份测试报告")
assert report.title == "测试报告"
print("✓ 创建报告成功")

# 添加章节
section = generator.add_section(report, "第一章 介绍", order=1)
assert section.title == "第一章 介绍"
print("✓ 添加章节成功")

# 添加内容块
generator.add_heading(section, "欢迎", level=2)
generator.add_paragraph(section, "这是一个段落")
generator.add_list(section, ["项目A", "项目B", "项目C"])
generator.add_table(section, ["名称", "值"], [["参数1", "100"], ["参数2", "200"]], title="参数表")
generator.add_code(section, "print('Hello')", "python")
print("✓ 添加内容块成功")

# 测试导出为 Markdown
md_content = generator.export_to_markdown(report)
assert "# 测试报告" in md_content
print("✓ 导出 Markdown 成功")

# 测试导出为 HTML
html_content = generator.export_to_html(report)
assert "<title>测试报告</title>" in html_content
print("✓ 导出 HTML 成功")

# 测试导出为 JSON
json_content = generator.export_to_json(report)
assert '"title": "测试报告"' in json_content
print("✓ 导出 JSON 成功")

# 测试环评报告生成
print("\n测试环评报告生成...")

async def test_eia_report():
    eia_report = await generator.generate_eia_report("工业园区建设项目")
    assert eia_report.title == "工业园区建设项目 - 环境影响评价报告"
    assert len(eia_report.sections) >= 4  # 至少4个章节
    print("✓ 环评报告生成成功")
    
    # 导出环评报告
    eia_md = generator.export_to_markdown(eia_report)
    assert "环境影响评价报告" in eia_md
    print("✓ 环评报告导出成功")

asyncio.run(test_eia_report())

print("\n🎉 所有测试通过!")