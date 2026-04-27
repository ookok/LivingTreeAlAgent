"""
LivingTreeAI 配置面板 - 带参数解释的智能配置UI
================================================

每个配置项自动显示:
- 参数名称
- 中文解释
- 默认值/取值范围
- 官方文档链接
- 最佳实践提示
"""

from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class ConfigField:
    """配置字段定义"""
    key: str
    name: str
    description: str
    default: Any
    value: Any
    range_hint: Any  # list, tuple, or None for free-form
    options: list  # 下拉选项列表
    link: str
    tips: str
    category: str
    on_change: Optional[Callable] = None


class ConfigHelpMixin:
    """配置帮助混入类 - 为UI组件添加帮助能力"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._help_info = {}

    def set_help_info(self, name: str, description: str, link: str, tips: str):
        """设置帮助信息"""
        self._help_info = {
            "name": name,
            "description": description,
            "link": link,
            "tips": tips
        }

    def get_help_html(self) -> str:
        """生成帮助HTML"""
        info = self._help_info
        if not info:
            return ""

        html = f'''
        <div class="config-help">
            <div class="help-header">
                <span class="help-icon">ℹ️</span>
                <strong>{info.get("name", "")}</strong>
            </div>
            <div class="help-desc">{info.get("description", "")}</div>
            <div class="help-tips">💡 {info.get("tips", "")}</div>
            <div class="help-link">
                <a href="{info.get("link", "#")}" target="_blank">📖 查看文档</a>
            </div>
        </div>
        '''
        return html


# ============================================================
# 配置面板模板 (可用于 PyQt/Tkinter/Web)
# ============================================================

CONFIG_PANEL_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
<style>
.config-panel {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}}
.config-section {{
    margin-bottom: 30px;
    background: #f8f9fa;
    border-radius: 12px;
    padding: 20px;
}}
.section-title {{
    font-size: 18px;
    font-weight: 600;
    color: #1a73e8;
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.config-item {{
    background: white;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
.item-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}}
.item-name {{
    font-weight: 500;
    color: #333;
}}
.item-badge {{
    background: #e8f0fe;
    color: #1a73e8;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
}}
.item-description {{
    color: #666;
    font-size: 14px;
    margin-bottom: 10px;
}}
.item-tips {{
    background: #fff8e1;
    border-left: 3px solid #ffc107;
    padding: 8px 12px;
    font-size: 13px;
    color: #555;
    margin: 8px 0;
}}
.item-link {{
    font-size: 12px;
}}
.item-link a {{
    color: #1a73e8;
    text-decoration: none;
}}
.item-link a:hover {{
    text-decoration: underline;
}}
.item-control {{
    margin-top: 10px;
}}
input[type="text"], input[type="number"], select {{
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
}}
input[type="range"] {{
    width: 100%;
}}
input[type="checkbox"] {{
    width: 18px;
    height: 18px;
}}
.help-icon {{
    cursor: help;
    border-bottom: 1px dotted #1a73e8;
}}
</style>
</head>
<body>
<div class="config-panel">
    {sections_html}
</div>
</body>
</html>
'''


def generate_config_panel_html(config_values: Dict[str, Dict[str, Any]]) -> str:
    """
    生成带参数解释的配置面板HTML

    Args:
        config_values: 配置值字典，格式为 {section: {field: value}}

    Returns:
        HTML字符串
    """
    from .config_metadata import CONFIG_METADATA

    sections_html = []

    for section, section_data in CONFIG_METADATA.items():
        display_name = section_data.get("display_name", section)
        section_icon = {
            "network": "🌐",
            "node": "🖥️",
            "federation": "🧠",
            "knowledge": "📚",
            "task": "📋",
            "incentive": "🏆",
            "security": "🔒",
            "advanced": "⚙️"
        }.get(section, "📌")

        fields_html = []

        for field, field_data in section_data.get("fields", {}).items():
            current_value = config_values.get(section, {}).get(field, field_data.get("default"))

            # 根据类型生成控件
            field_type = "text"
            if isinstance(field_data.get("range"), list):
                if len(field_data["range"]) == 2 and isinstance(field_data["range"][0], (int, float)):
                    field_type = "range"
                else:
                    field_type = "select"

            control_html = _generate_control_html(field, current_value, field_data, field_type)

            field_html = f'''
            <div class="config-item">
                <div class="item-header">
                    <span class="item-name">{field_data.get("name", field)}</span>
                    <span class="item-badge">{field_data.get("category", "")}</span>
                </div>
                <div class="item-description">{field_data.get("description", "")}</div>
                <div class="item-tips">💡 {field_data.get("tips", "")}</div>
                <div class="item-link">
                    <a href="{field_data.get("link", "#")}" target="_blank">📖 查看完整文档</a>
                </div>
                <div class="item-control">
                    {control_html}
                </div>
            </div>
            '''
            fields_html.append(field_html)

        section_html = f'''
        <div class="config-section">
            <div class="section-title">{section_icon} {display_name}</div>
            {''.join(fields_html)}
        </div>
        '''
        sections_html.append(section_html)

    return CONFIG_PANEL_TEMPLATE.format(sections_html=''.join(sections_html))


def _generate_control_html(field: str, value: Any, field_data: Dict, field_type: str) -> str:
    """生成表单控件HTML"""
    if field_type == "range":
        range_list = field_data.get("range", [0, 100])
        min_val, max_val = range_list[0], range_list[1]
        return f'''
        <input type="range" name="{field}" min="{min_val}" max="{max_val}" value="{value}"
               oninput="this.nextElementSibling.textContent = this.value">
        <span>{value}</span>
        '''

    elif field_type == "select":
        options = field_data.get("range", [])
        options_html = ''.join(
            f'<option value="{opt}" {"selected" if opt == value else ""}>{opt}</option>'
            for opt in options
        )
        return f'<select name="{field}">{options_html}</select>'

    elif isinstance(field_data.get("range"), list) and len(field_data["range"]) == 2:
        # Boolean
        if field_data["range"] == [True, False]:
            checked = "checked" if value else ""
            return f'<input type="checkbox" name="{field}" {checked}>'

    # Default: text input
    return f'<input type="text" name="{field}" value="{value}">'
