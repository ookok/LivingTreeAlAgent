"""
智能字段渲染器

根据字段配置渲染智能输入组件，支持多种字段类型和AI辅助功能。
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from .universal_template_engine import FieldType, SectionField


# ==================== 渲染配置 ====================

@dataclass
class FieldRenderConfig:
    """字段渲染配置"""
    field_id: str
    label: str
    field_type: FieldType
    value: Any = None
    required: bool = False
    placeholder: str = ""
    help_text: str = ""
    options: List[Any] = field(default_factory=list)
    unit: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    columns: List[Dict] = field(default_factory=list)
    ai_enabled: bool = False
    cross_ref_enabled: bool = False
    validation_message: str = ""
    is_valid: bool = True
    confidence: float = 0.0
    ai_suggestion: Any = None


# ==================== CSS样式 ====================

DEFAULT_FIELD_CSS = """
/* 智能字段样式 */
.smart-field {
    margin-bottom: 20px;
    position: relative;
}

.smart-field label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    color: #2d3748;
    margin-bottom: 6px;
}

.smart-field label .required {
    color: #e53e3e;
    margin-left: 3px;
}

.smart-field label .unit {
    font-weight: normal;
    color: #718096;
    font-size: 12px;
    margin-left: 4px;
}

/* 基础输入框 */
.smart-field input[type="text"],
.smart-field input[type="number"],
.smart-field input[type="email"],
.smart-field input[type="tel"],
.smart-field input[type="url"],
.smart-field input[type="date"],
.smart-field textarea,
.smart-field select {
    width: 100%;
    padding: 10px 14px;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 14px;
    transition: all 0.2s;
    box-sizing: border-box;
    background: white;
}

.smart-field input:focus,
.smart-field textarea:focus,
.smart-field select:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.smart-field input.modified,
.smart-field textarea.modified,
.smart-field select.modified {
    border-color: #f6ad55;
    background: #fffaf0;
}

.smart-field input.error,
.smart-field textarea.error {
    border-color: #fc8181;
    background: #fff5f5;
}

.smart-field input.success,
.smart-field textarea.success {
    border-color: #68d391;
}

/* 帮助文本 */
.smart-field .help-text {
    font-size: 12px;
    color: #718096;
    margin-top: 4px;
}

/* AI辅助按钮 */
.ai-assistant {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    gap: 4px;
    opacity: 0.6;
    transition: opacity 0.2s;
}

.smart-field:hover .ai-assistant {
    opacity: 1;
}

.ai-assistant button {
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    background: #edf2f7;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.ai-assistant button:hover {
    background: #667eea;
    color: white;
}

/* AI建议面板 */
.ai-suggestions-panel {
    background: #f7fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
}

.ai-suggestions-panel .suggestion-header {
    font-size: 12px;
    color: #718096;
    margin-bottom: 8px;
}

.ai-suggestions-panel .suggestion-item {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.ai-suggestions-panel .suggestion-item:hover {
    border-color: #667eea;
    background: #f7fafc;
}

.ai-suggestions-panel .suggestion-item .text {
    font-size: 13px;
    color: #2d3748;
}

.ai-suggestions-panel .suggestion-item .source {
    font-size: 11px;
    color: #a0aec0;
    margin-top: 2px;
}

/* 表格字段 */
.table-field {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}

.table-field table {
    width: 100%;
    border-collapse: collapse;
}

.table-field th {
    background: #f7fafc;
    padding: 10px 12px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
    color: #4a5568;
    border-bottom: 1px solid #e2e8f0;
}

.table-field td {
    padding: 8px 12px;
    border-bottom: 1px solid #e2e8f0;
}

.table-field tr:last-child td {
    border-bottom: none;
}

.table-field input {
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 6px 8px;
    width: 100%;
    box-sizing: border-box;
}

.table-field .add-row {
    background: #f7fafc;
    padding: 8px;
    text-align: center;
}

.table-field .add-row button {
    color: #667eea;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 13px;
}

/* 文件上传字段 */
.file-field {
    border: 2px dashed #e2e8f0;
    border-radius: 8px;
    padding: 24px;
    text-align: center;
    background: #fafbfc;
    transition: all 0.2s;
}

.file-field:hover {
    border-color: #667eea;
    background: #f7fafc;
}

.file-field .file-icon {
    font-size: 32px;
    margin-bottom: 8px;
}

.file-field .file-hint {
    font-size: 13px;
    color: #718096;
}

.file-field .file-list {
    margin-top: 12px;
    text-align: left;
}

.file-field .file-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    margin-bottom: 4px;
}

.file-field .file-item .name {
    flex: 1;
    font-size: 13px;
}

.file-field .file-item .remove {
    color: #e53e3e;
    cursor: pointer;
}

/* 富文本字段 */
.rich-text-field {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}

.rich-text-field .toolbar {
    background: #f7fafc;
    padding: 8px 12px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    gap: 4px;
}

.rich-text-field .toolbar button {
    width: 32px;
    height: 32px;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    font-size: 14px;
}

.rich-text-field .toolbar button:hover {
    background: #edf2f7;
}

.rich-text-field .editor {
    min-height: 200px;
    padding: 12px;
}

/* 签名字段 */
.signature-field {
    border: 2px dashed #e2e8f0;
    border-radius: 8px;
    padding: 24px;
    text-align: center;
    background: #fafbfc;
}

.signature-field canvas {
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    background: white;
    cursor: crosshair;
}

.signature-field .signature-actions {
    margin-top: 12px;
}

/* 验证反馈 */
.field-validation {
    font-size: 12px;
    margin-top: 4px;
    padding: 4px 8px;
    border-radius: 4px;
}

.field-validation.error {
    background: #fed7d7;
    color: #c53030;
}

.field-validation.success {
    background: #c6f6d5;
    color: #276749;
}

.field-validation.warning {
    background: #feebc8;
    color: #c05621;
}
"""


# ==================== 字段渲染器 ====================

class SmartFieldRenderer:
    """
    智能字段渲染器

    根据字段配置渲染智能输入组件。
    """

    def __init__(self):
        self._renderers = {
            FieldType.TEXT: self._render_text,
            FieldType.TEXTAREA: self._render_textarea,
            FieldType.NUMBER: self._render_number,
            FieldType.SELECT: self._render_select,
            FieldType.MULTI_SELECT: self._render_multi_select,
            FieldType.ADDRESS: self._render_address,
            FieldType.DATE: self._render_date,
            FieldType.DATE_RANGE: self._render_date_range,
            FieldType.TABLE: self._render_table,
            FieldType.FILE: self._render_file,
            FieldType.RICH_TEXT: self._render_rich_text,
            FieldType.SIGNATURE: self._render_signature,
            FieldType.CURRENCY: self._render_currency,
            FieldType.PERCENTAGE: self._render_percentage,
            FieldType.PHONE: self._render_phone,
            FieldType.EMAIL: self._render_email,
            FieldType.URL: self._render_url,
        }

    def render_field(
        self,
        config: FieldRenderConfig,
        section_id: str = ""
    ) -> str:
        """
        根据字段配置渲染智能输入组件

        Args:
            config: 字段渲染配置
            section_id: 所属章节ID

        Returns:
            str: HTML字符串
        """
        renderer = self._renderers.get(
            config.field_type,
            self._render_text
        )
        return renderer(config, section_id)

    def _render_base_wrapper(
        self,
        config: FieldRenderConfig,
        section_id: str,
        field_html: str
    ) -> str:
        """渲染字段包装器"""
        field_full_id = f"{section_id}_{config.field_id}" if section_id else config.field_id

        html = [f'<div class="smart-field" data-field-id="{config.field_id}" data-section="{section_id}">']

        # 标签
        label_parts = [config.label]
        if config.required:
            label_parts.append('<span class="required">*</span>')
        if config.unit:
            label_parts.append(f'<span class="unit">({config.unit})</span>')

        html.append(f'<label>{"".join(label_parts)}</label>')

        # 字段HTML
        html.append(field_html)

        # 帮助文本
        if config.help_text:
            html.append(f'<div class="help-text">{config.help_text}</div>')

        # 验证反馈
        if config.validation_message:
            validation_class = "error" if not config.is_valid else "success"
            html.append(f'<div class="field-validation {validation_class}">{config.validation_message}</div>')

        # AI辅助按钮
        if config.ai_enabled:
            html.append(self._render_ai_assistant(config.field_id))

        html.append('</div>')

        return '\n'.join(html)

    def _render_text(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染文本输入框"""
        value = config.value or ""
        field_html = f'''<input type="text"
            id="{config.field_id}"
            name="{config.field_id}"
            value="{value}"
            placeholder="{config.placeholder}"
            {'required' if config.required else ''}
            {'class="modified"' if value else ''}
        >'''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_textarea(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染文本域"""
        value = config.value or ""
        field_html = f'''<textarea
            id="{config.field_id}"
            name="{config.field_id}"
            rows="4"
            placeholder="{config.placeholder}"
            {'required' if config.required else ''}
        >{value}</textarea>'''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_number(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染数字输入框"""
        value = config.value if config.value is not None else ""
        attrs = []
        if config.min_value is not None:
            attrs.append(f'min="{config.min_value}"')
        if config.max_value is not None:
            attrs.append(f'max="{config.max_value}"')

        field_html = f'''<input type="number"
            id="{config.field_id}"
            name="{config.field_id}"
            value="{value}"
            {" ".join(attrs)}
            {'required' if config.required else ''}
        >'''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_select(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染下拉选择框"""
        options_html = ['<option value="">-- 请选择 --</option>']
        for opt in config.options:
            opt_value = opt if isinstance(opt, str) else opt.get("value", "")
            opt_label = opt if isinstance(opt, str) else opt.get("label", opt_value)
            selected = ' selected' if config.value == opt_value else ''
            options_html.append(f'<option value="{opt_value}"{selected}>{opt_label}</option>')

        field_html = f'''<select
            id="{config.field_id}"
            name="{config.field_id}"
            {'required' if config.required else ''}
        >
            {"".join(options_html)}
        </select>'''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_multi_select(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染多选框"""
        values = config.value if isinstance(config.value, list) else []

        options_html = []
        for opt in config.options:
            opt_value = opt if isinstance(opt, str) else opt.get("value", "")
            opt_label = opt if isinstance(opt, str) else opt.get("label", opt_value)
            checked = ' checked' if opt_value in values else ''
            options_html.append(f'''
            <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                <input type="checkbox" name="{config.field_id}" value="{opt_value}"{checked}>
                {opt_label}
            </label>
            ''')

        field_html = f'<div class="multi-select-options">{"".join(options_html)}</div>'
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_address(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染地址字段（带地图选择）"""
        value = config.value or ""
        field_html = f'''
        <div class="address-field">
            <input type="text"
                id="{config.field_id}"
                name="{config.field_id}"
                value="{value}"
                placeholder="{config.placeholder or '请输入地址'}"
                {'required' if config.required else ''}
            >
            <button type="button" class="map-picker" onclick="pickAddress('{config.field_id}')">📍 地图</button>
        </div>
        '''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_date(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染日期字段"""
        value = config.value or ""
        field_html = f'''<input type="date"
            id="{config.field_id}"
            name="{config.field_id}"
            value="{value}"
            {'required' if config.required else ''}
        >'''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_date_range(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染日期范围字段"""
        value = config.value or {}
        start_value = value.get("start", "") if isinstance(value, dict) else ""
        end_value = value.get("end", "") if isinstance(value, dict) else ""

        field_html = f'''
        <div class="date-range" style="display: flex; gap: 8px;">
            <input type="date" name="{config.field_id}_start" value="{start_value}" placeholder="开始日期">
            <span style="line-height: 38px;">至</span>
            <input type="date" name="{config.field_id}_end" value="{end_value}" placeholder="结束日期">
        </div>
        '''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_table(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染表格字段"""
        rows = config.value if isinstance(config.value, list) else []
        columns = config.columns or []

        # 表头
        header_html = ''.join([
            f'<th>{col.get("label", col.get("id", ""))}</th>'
            for col in columns
        ])

        # 数据行
        body_html = ''
        for row_idx, row in enumerate(rows):
            row_cells = []
            for col in columns:
                col_id = col.get("id", "")
                cell_value = row.get(col_id, "") if isinstance(row, dict) else ""
                row_cells.append(f'<td><input type="text" name="{config.field_id}_{col_id}_{row_idx}" value="{cell_value}"></td>')
            body_html += f'<tr>{"".join(row_cells)}</tr>'

        # 空行模板
        empty_row_cells = [
            f'<td><input type="text" name="{config.field_id}_{col.get("id", "")}_INDEX" placeholder=""></td>'
            for col in columns
        ]
        empty_row = f'<tr class="empty-row-template" style="display: none;">{"".join(empty_row_cells)}</tr>'

        field_html = f'''
        <div class="table-field">
            <table>
                <thead><tr>{header_html}<th>操作</th></tr></thead>
                <tbody>
                    {body_html}
                    {empty_row}
                </tbody>
            </table>
            <div class="add-row">
                <button type="button" onclick="addTableRow('{config.field_id}')">+ 添加行</button>
            </div>
        </div>
        '''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_file(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染文件上传字段"""
        files = config.value if isinstance(config.value, list) else []

        file_list_html = ''
        for f in files:
            file_name = f if isinstance(f, str) else f.get("name", "未知文件")
            file_list_html += f'''
            <div class="file-item">
                <span class="name">📄 {file_name}</span>
                <span class="remove" onclick="removeFile('{config.field_id}', this)">✕</span>
            </div>
            '''

        field_html = f'''
        <div class="file-field" id="file-{config.field_id}">
            <div class="file-icon">📁</div>
            <div class="file-hint">拖拽文件到此处，或 <label style="color: #667eea; cursor: pointer;">点击上传<input type="file" style="display: none;" onchange="handleFileUpload('{config.field_id}', this)"></label></div>
            <div class="file-list">{file_list_html}</div>
        </div>
        '''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_rich_text(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染富文本编辑器"""
        value = config.value or ""

        field_html = f'''
        <div class="rich-text-field">
            <div class="toolbar">
                <button type="button" onclick="execCmd('bold')" title="加粗">B</button>
                <button type="button" onclick="execCmd('italic')" title="斜体">I</button>
                <button type="button" onclick="execCmd('underline')" title="下划线">U</button>
                <button type="button" onclick="execCmd('insertUnorderedList')" title="列表">☰</button>
            </div>
            <div class="editor" contenteditable="true" id="{config.field_id}">{value}</div>
        </div>
        <input type="hidden" name="{config.field_id}" id="{config.field_id}_hidden" value="{value}">
        '''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_signature(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染电子签名字段"""
        field_html = f'''
        <div class="signature-field">
            <canvas id="{config.field_id}_canvas" width="400" height="150"></canvas>
            <div class="signature-actions">
                <button type="button" onclick="clearSignature('{config.field_id}')">清除</button>
                <button type="button" onclick="saveSignature('{config.field_id}')">确认签名</button>
            </div>
            <input type="hidden" name="{config.field_id}" id="{config.field_id}_hidden">
        </div>
        '''
        return self._render_base_wrapper(config, section_id, field_html)

    def _render_currency(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染货币字段"""
        return self._render_number(config, section_id)

    def _render_percentage(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染百分比字段"""
        return self._render_number(config, section_id)

    def _render_phone(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染电话字段"""
        return self._render_text(config, section_id)

    def _render_email(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染邮箱字段"""
        return self._render_text(config, section_id)

    def _render_url(self, config: FieldRenderConfig, section_id: str) -> str:
        """渲染URL字段"""
        return self._render_text(config, section_id)

    def _render_ai_assistant(self, field_id: str) -> str:
        """渲染AI辅助按钮"""
        return f'''
        <div class="ai-assistant" data-for-field="{field_id}">
            <button type="button" class="ai-suggest" title="AI建议" onclick="requestAISuggestion('{field_id}')">💡</button>
            <button type="button" class="ai-example" title="查看示例" onclick="showAIExample('{field_id}')">📋</button>
            <button type="button" class="ai-validate" title="校验数据" onclick="validateField('{field_id}')">✓</button>
        </div>
        '''

    def get_css(self) -> str:
        """获取字段CSS"""
        return DEFAULT_FIELD_CSS


# ==================== 便捷函数 ====================

_renderer_instance: Optional[SmartFieldRenderer] = None


def get_field_renderer() -> SmartFieldRenderer:
    """获取字段渲染器单例"""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = SmartFieldRenderer()
    return _renderer_instance


def render_field_async(
    field: SectionField,
    value: Any = None,
    section_id: str = ""
) -> str:
    """渲染单个字段的便捷函数"""
    renderer = get_field_renderer()

    config = FieldRenderConfig(
        field_id=field.id,
        label=field.label,
        field_type=field.field_type,
        value=value or field.default_value,
        required=field.required,
        placeholder=field.placeholder,
        help_text=field.help_text,
        options=field.options,
        unit=field.unit,
        min_value=field.min_value,
        max_value=field.max_value,
        columns=field.columns,
        ai_enabled=field.ai_enabled,
    )

    return renderer.render_field(config, section_id)


def render_form_async(
    fields: List[SectionField],
    values: Dict[str, Any],
    section_id: str = ""
) -> str:
    """渲染表单的便捷函数"""
    renderer = get_field_renderer()
    html_parts = []

    for field in fields:
        config = FieldRenderConfig(
            field_id=field.id,
            label=field.label,
            field_type=field.field_type,
            value=values.get(field.id),
            required=field.required,
            placeholder=field.placeholder,
            help_text=field.help_text,
            options=field.options,
            unit=field.unit,
            min_value=field.min_value,
            max_value=field.max_value,
            columns=field.columns,
            ai_enabled=field.ai_enabled,
        )

        html_parts.append(renderer.render_field(config, section_id))

    return '\n'.join(html_parts)
