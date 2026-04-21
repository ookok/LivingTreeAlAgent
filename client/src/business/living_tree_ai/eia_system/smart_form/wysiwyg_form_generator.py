"""
智能表单 - 所见即所得表单生成器
生成可交互的预填表单，业主可以实时核对和修改AI提取的数据

核心理念：从"填表"到"核验"，业主从打字员变成核验员
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from .document_form_extractor import (
    ExtractionResult,
    ExtractedField,
    ValidationResult,
)


# ==================== 样式常量 ====================

DEFAULT_CSS = """
/* 智能表单样式 */
.smart-form {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    max-width: 900px;
    margin: 0 auto;
    padding: 24px;
    background: #fafbfc;
}

.smart-form-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 12px 12px 0 0;
    margin: -24px -24px 24px -24px;
}

.smart-form-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
}

.confidence-badge {
    background: rgba(255,255,255,0.2);
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 13px;
}

.form-section {
    background: white;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.section-title {
    font-size: 15px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0 0 16px 0;
    padding-bottom: 10px;
    border-bottom: 2px solid #667eea;
}

.form-field {
    margin-bottom: 20px;
}

.form-field label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: #4a5568;
    margin-bottom: 6px;
}

.form-field label .required {
    color: #e53e3e;
    margin-left: 2px;
}

.form-field input[type="text"],
.form-field input[type="number"],
.form-field input[type="email"],
.form-field input[type="tel"],
.form-field textarea,
.form-field select {
    width: 100%;
    padding: 10px 14px;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 14px;
    transition: all 0.2s;
    box-sizing: border-box;
}

.form-field input:focus,
.form-field textarea:focus,
.form-field select:focus {
    outline: none;
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-field input.modified,
.form-field textarea.modified,
.form-field select.modified {
    border-color: #f6ad55;
    background: #fffaf0;
}

/* AI提取对比框 */
.ai-comparison {
    background: #f7fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
}

.ai-comparison .ai-label {
    font-size: 11px;
    color: #718096;
    margin-bottom: 4px;
}

.ai-comparison .ai-value {
    font-size: 13px;
    color: #2d3748;
    padding: 6px 10px;
    background: #edf2f7;
    border-radius: 4px;
    margin-bottom: 8px;
}

.ai-comparison.mismatch {
    border-color: #f6ad55;
    background: #fffaf0;
}

.ai-comparison.mismatch .ai-value {
    background: #fed7aa;
}

.ai-suggestion {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
}

.ai-suggestion .suggestion-text {
    font-size: 12px;
    color: #4a5568;
}

.suggestion-actions {
    display: flex;
    gap: 6px;
}

.suggestion-actions button {
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
}

.btn-use-standard {
    background: #48bb78;
    color: white;
}

.btn-use-standard:hover {
    background: #38a169;
}

.btn-use-current {
    background: #718096;
    color: white;
}

.btn-use-current:hover {
    background: #4a5568;
}

/* 置信度指示器 */
.confidence-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    margin-top: 4px;
}

.confidence-bar {
    width: 60px;
    height: 4px;
    background: #e2e8f0;
    border-radius: 2px;
    overflow: hidden;
}

.confidence-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.3s;
}

.confidence-high .confidence-fill { background: #48bb78; }
.confidence-medium .confidence-fill { background: #f6ad55; }
.confidence-low .confidence-fill { background: #fc8181; }

.confidence-high { color: #276749; }
.confidence-medium { color: #c05621; }
.confidence-low { color: #c53030; }

/* 验证反馈 */
.validation-feedback {
    font-size: 12px;
    margin-top: 4px;
    padding: 4px 8px;
    border-radius: 4px;
}

.validation-success {
    background: #c6f6d5;
    color: #276749;
}

.validation-warning {
    background: #feebc8;
    color: #c05621;
}

.validation-error {
    background: #fed7d7;
    color: #c53030;
}

/* 底部操作栏 */
.form-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    background: white;
    border-radius: 0 0 12px 12px;
    box-shadow: 0 -2px 8px rgba(0,0,0,0.04);
    margin: 0 -24px -24px -24px;
}

.form-actions .left-actions {
    display: flex;
    gap: 12px;
}

.form-actions .right-actions {
    display: flex;
    gap: 12px;
}

.btn {
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
}

.btn-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
    background: #e2e8f0;
    color: #4a5568;
}

.btn-secondary:hover {
    background: #cbd5e0;
}

.btn-success {
    background: #48bb78;
    color: white;
}

.btn-success:hover {
    background: #38a169;
}

/* 进度指示 */
.extraction-progress {
    text-align: center;
    padding: 40px;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #e2e8f0;
    border-top-color: #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 16px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* 响应式 */
@media (max-width: 640px) {
    .smart-form {
        padding: 16px;
    }

    .form-actions {
        flex-direction: column;
        gap: 12px;
    }

    .form-actions .left-actions,
    .form-actions .right-actions {
        width: 100%;
        justify-content: center;
    }
}
"""

DEFAULT_JAVASCRIPT = """
// 智能表单前端脚本
class SmartFormController {
    constructor(containerId, config = {}) {
        this.container = document.getElementById(containerId);
        this.config = {
            websocketUrl: config.websocketUrl || 'ws://localhost:8765/form/assist',
            apiBaseUrl: config.apiBaseUrl || 'http://localhost:5000/api',
            ...config
        };
        this.formData = {};
        this.validationCache = {};
        this.ws = null;
        this.isConnected = false;

        this.init();
    }

    init() {
        this.setupWebSocket();
        this.setupEventListeners();
    }

    setupWebSocket() {
        try {
            this.ws = new WebSocket(this.config.websocketUrl);

            this.ws.onopen = () => {
                this.isConnected = true;
                console.log('SmartForm: WebSocket connected');
            };

            this.ws.onclose = () => {
                this.isConnected = false;
                console.log('SmartForm: WebSocket disconnected');
                // 尝试重连
                setTimeout(() => this.setupWebSocket(), 3000);
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleServerMessage(data);
            };
        } catch (e) {
            console.log('SmartForm: WebSocket not available, using REST API');
        }
    }

    setupEventListeners() {
        // 输入事件 - 实时验证
        this.container.addEventListener('input', async (e) => {
            if (e.target.matches('input, select, textarea')) {
                const fieldName = e.target.dataset.field;
                if (fieldName) {
                    e.target.classList.add('modified');
                    this.formData[fieldName] = e.target.value;
                    await this.validateField(fieldName, e.target.value);
                }
            }
        });

        // 采纳标准值按钮
        this.container.addEventListener('click', (e) => {
            if (e.target.matches('.btn-use-standard')) {
                const fieldName = e.target.dataset.field;
                const standardValue = e.target.dataset.standard;
                this.useStandardValue(fieldName, standardValue);
            }

            if (e.target.matches('.btn-use-current')) {
                const fieldName = e.target.dataset.field;
                this.useCurrentValue(fieldName);
            }
        });

        // 提交按钮
        this.container.addEventListener('click', (e) => {
            if (e.target.matches('.btn-submit')) {
                this.submitForm();
            }

            if (e.target.matches('.btn-save-draft')) {
                this.saveDraft();
            }

            if (e.target.matches('.btn-reset')) {
                this.resetForm();
            }
        });
    }

    handleServerMessage(data) {
        switch (data.type) {
            case 'validation_result':
                this.showValidationResult(data.field, data.result);
                break;
            case 'autofill':
                this.applyAutofill(data.fields);
                break;
            case 'correction_suggestion':
                this.showCorrectionSuggestion(data.field, data.suggestion);
                break;
        }
    }

    async validateField(fieldName, value) {
        if (!value || value.length < 1) return;

        // 优先使用WebSocket
        if (this.isConnected) {
            this.ws.send(JSON.stringify({
                type: 'validate_field',
                field: fieldName,
                value: value,
                formId: this.config.formId
            }));
        } else {
            // 回退到REST API
            try {
                const response = await fetch(`${this.config.apiBaseUrl}/validate`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        field: fieldName,
                        value: value,
                        formId: this.config.formId
                    })
                });
                const result = await response.json();
                this.showValidationResult(fieldName, result);
            } catch (e) {
                console.error('Validation failed:', e);
            }
        }
    }

    showValidationResult(fieldName, result) {
        const field = this.container.querySelector(`[data-field="${fieldName}"]`);
        if (!field) return;

        // 移除旧反馈
        const oldFeedback = field.parentNode.querySelector('.validation-feedback');
        if (oldFeedback) oldFeedback.remove();

        // 添加新反馈
        const feedback = document.createElement('div');
        feedback.className = `validation-feedback validation-${result.status}`;
        feedback.textContent = result.message;
        field.parentNode.appendChild(feedback);
    }

    useStandardValue(fieldName, standardValue) {
        const field = this.container.querySelector(`[data-field="${fieldName}"]`);
        if (field) {
            field.value = standardValue;
            field.classList.remove('modified');
            this.formData[fieldName] = standardValue;
            this.showValidationResult(fieldName, {status: 'success', message: '已采用标准值'});

            // 隐藏对比框
            const comparison = field.parentNode.querySelector('.ai-comparison');
            if (comparison) {
                comparison.style.display = 'none';
            }
        }
    }

    useCurrentValue(fieldName) {
        const field = this.container.querySelector(`[data-field="${fieldName}"]`);
        if (field) {
            // 标记为已修改
            field.classList.add('modified');
            // 隐藏建议
            const comparison = field.parentNode.querySelector('.ai-comparison');
            if (comparison) {
                comparison.style.display = 'none';
            }
        }
    }

    showCorrectionSuggestion(fieldName, suggestion) {
        // 可以显示更详细的修正建议
        console.log(`Correction for ${fieldName}:`, suggestion);
    }

    applyAutofill(fields) {
        fields.forEach(field => {
            const input = this.container.querySelector(`[data-field="${field.name}"]`);
            if (input && !input.value) {
                input.value = field.value;
                input.dataset.confidence = field.confidence || 1.0;
            }
        });
    }

    async submitForm() {
        // 收集所有数据
        const submitData = {
            formId: this.config.formId,
            timestamp: new Date().toISOString(),
            fields: {}
        };

        const inputs = this.container.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            const fieldName = input.dataset.field;
            if (fieldName) {
                submitData.fields[fieldName] = {
                    value: input.value,
                    modified: input.classList.contains('modified')
                };
            }
        });

        // 发送到服务器
        try {
            const response = await fetch(`${this.config.apiBaseUrl}/submit`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(submitData)
            });

            if (response.ok) {
                alert('表单提交成功！');
            } else {
                alert('提交失败，请重试');
            }
        } catch (e) {
            console.error('Submit failed:', e);
            alert('提交失败: ' + e.message);
        }
    }

    saveDraft() {
        localStorage.setItem(`form_draft_${this.config.formId}`, JSON.stringify({
            data: this.formData,
            timestamp: new Date().toISOString()
        }));
        alert('草稿已保存');
    }

    resetForm() {
        if (confirm('确定要重置表单吗？所有修改将丢失。')) {
            const inputs = this.container.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                input.value = input.dataset.original || '';
                input.classList.remove('modified');
            });
            this.formData = {};
        }
    }

    getFormData() {
        return {...this.formData};
    }
}

// 工厂函数
function createSmartForm(containerId, options = {}) {
    return new SmartFormController(containerId, options);
}
"""


# ==================== 字段HTML生成器 ====================

class FieldHTMLGenerator:
    """字段HTML生成器"""

    @staticmethod
    def generate_text_field(
        config: Dict,
        extracted: Optional[ExtractedField] = None,
        validation: Optional[ValidationResult] = None
    ) -> str:
        """生成文本字段HTML"""
        label = config.get("label", config["name"])
        required = config.get("required", False)
        placeholder = config.get("placeholder", "")

        value = extracted.value if extracted else ""
        confidence = extracted.confidence if extracted else 0.0

        html = []
        html.append(f'<div class="form-field field-text">')
        html.append(f'  <label>{label}')
        if required:
            html.append(' <span class="required">*</span>')
        html.append('</label>')

        # AI提取对比
        if extracted and value:
            html.append(FieldHTMLGenerator._generate_comparison_block(
                config, value, validation, confidence
            ))

        # 输入框
        html.append(f'  <input type="text" ')
        html.append(f'         data-field="{config["name"]}" ')
        html.append(f'         data-original="{value}" ')
        html.append(f'         value="{value}" ')
        if placeholder:
            html.append(f'         placeholder="{placeholder}" ')
        if required:
            html.append('         required ')
        html.append('  >')

        # 置信度指示器
        if extracted:
            html.append(FieldHTMLGenerator._generate_confidence_indicator(confidence))

        html.append('</div>')

        return "\n".join(html)

    @staticmethod
    def generate_number_field(
        config: Dict,
        extracted: Optional[ExtractedField] = None,
        validation: Optional[ValidationResult] = None
    ) -> str:
        """生成数字字段HTML"""
        label = config.get("label", config["name"])
        required = config.get("required", False)
        min_val = config.get("min")
        max_val = config.get("max")
        unit = config.get("unit", "")

        value = extracted.value if extracted else ""
        confidence = extracted.confidence if extracted else 0.0

        html = []
        html.append(f'<div class="form-field field-number">')
        html.append(f'  <label>{label}')
        if required:
            html.append(' <span class="required">*</span>')
        if unit:
            html.append(f' <span class="unit">({unit})</span>')
        html.append('</label>')

        # AI提取对比
        if extracted and value:
            html.append(FieldHTMLGenerator._generate_comparison_block(
                config, value, validation, confidence
            ))

        # 输入框
        html.append(f'  <input type="number" ')
        html.append(f'         data-field="{config["name"]}" ')
        html.append(f'         data-original="{value}" ')
        html.append(f'         value="{value}" ')
        if min_val is not None:
            html.append(f'         min="{min_val}" ')
        if max_val is not None:
            html.append(f'         max="{max_val}" ')
        if required:
            html.append('         required ')
        html.append('  >')

        # 置信度指示器
        if extracted:
            html.append(FieldHTMLGenerator._generate_confidence_indicator(confidence))

        html.append('</div>')

        return "\n".join(html)

    @staticmethod
    def generate_select_field(
        config: Dict,
        extracted: Optional[ExtractedField] = None,
        validation: Optional[ValidationResult] = None
    ) -> str:
        """生成下拉字段HTML"""
        label = config.get("label", config["name"])
        required = config.get("required", False)
        options = config.get("options", [])

        value = extracted.value if extracted else ""

        html = []
        html.append(f'<div class="form-field field-select">')
        html.append(f'  <label>{label}')
        if required:
            html.append(' <span class="required">*</span>')
        html.append('</label>')

        # AI提取对比
        if extracted and value:
            html.append(FieldHTMLGenerator._generate_comparison_block(
                config, value, validation, extracted.confidence
            ))

        # 下拉框
        html.append(f'  <select data-field="{config["name"]}" ')
        html.append(f'         data-original="{value}" ')
        if required:
            html.append('         required ')
        html.append('  >')

        # 空选项
        html.append(f'    <option value="">-- 请选择 --</option>')

        # 选项
        for opt in options:
            opt_value = opt if isinstance(opt, str) else opt.get("value", "")
            opt_label = opt if isinstance(opt, str) else opt.get("label", opt_value)
            selected = ' selected' if value == opt_value else ''
            html.append(f'    <option value="{opt_value}"{selected}>{opt_label}</option>')

        html.append('  </select>')

        # 置信度指示器
        if extracted:
            html.append(FieldHTMLGenerator._generate_confidence_indicator(extracted.confidence))

        html.append('</div>')

        return "\n".join(html)

    @staticmethod
    def generate_textarea_field(
        config: Dict,
        extracted: Optional[ExtractedField] = None,
        validation: Optional[ValidationResult] = None
    ) -> str:
        """生成文本域字段HTML"""
        label = config.get("label", config["name"])
        required = config.get("required", False)
        rows = config.get("rows", 4)

        value = extracted.value if extracted else ""
        confidence = extracted.confidence if extracted else 0.0

        html = []
        html.append(f'<div class="form-field field-textarea">')
        html.append(f'  <label>{label}')
        if required:
            html.append(' <span class="required">*</span>')
        html.append('</label>')

        # AI提取对比
        if extracted and value:
            html.append(FieldHTMLGenerator._generate_comparison_block(
                config, value, validation, confidence
            ))

        # 文本域
        html.append(f'  <textarea data-field="{config["name"]}" ')
        html.append(f'          data-original="{value}" ')
        html.append(f'          rows="{rows}" ')
        if required:
            html.append('          required ')
        html.append(f'  >{value}</textarea>')

        # 置信度指示器
        if extracted:
            html.append(FieldHTMLGenerator._generate_confidence_indicator(confidence))

        html.append('</div>')

        return "\n".join(html)

    @staticmethod
    def _generate_comparison_block(
        config: Dict,
        value: str,
        validation: Optional[ValidationResult],
        confidence: float
    ) -> str:
        """生成AI提取对比块"""
        html = []

        is_mismatch = (
            validation and
            not validation.match and
            validation.standard_value
        )

        html.append(f'<div class="ai-comparison')
        if is_mismatch:
            html.append(' mismatch')
        html.append('">')

        html.append('  <div class="ai-label">🤖 AI从文档中提取</div>')
        html.append(f'  <div class="ai-value">{value}</div>')

        # 不匹配时显示标准值
        if is_mismatch and validation.standard_value:
            html.append('  <div class="ai-suggestion">')
            html.append('    <span class="suggestion-text">📋 知识库标准值:</span>')
            html.append('  </div>')
            html.append(f'  <div class="ai-value standard">{validation.standard_value}</div>')
            html.append('  <div class="suggestion-actions">')
            html.append(f'    <button class="btn-use-standard" ')
            html.append(f'            data-field="{config["name"]}" ')
            html.append(f'            data-standard="{validation.standard_value}">')
            html.append('      采用标准值')
            html.append('    </button>')
            html.append('    <button class="btn-use-current" ')
            html.append(f'            data-field="{config["name"]}">')
            html.append('      保留当前值')
            html.append('    </button>')
            html.append('  </div>')

        html.append('</div>')

        return "\n".join(html)

    @staticmethod
    def _generate_confidence_indicator(confidence: float) -> str:
        """生成置信度指示器"""
        if confidence >= 0.9:
            level_class = "confidence-high"
            level_text = "高"
        elif confidence >= 0.6:
            level_class = "confidence-medium"
            level_text = "中"
        else:
            level_class = "confidence-low"
            level_text = "低"

        percentage = int(confidence * 100)

        html = []
        html.append(f'<div class="confidence-indicator {level_class}">')
        html.append(f'  <span>可信度: {level_text} ({percentage}%)</span>')
        html.append('  <div class="confidence-bar">')
        html.append(f'    <div class="confidence-fill" style="width: {percentage}%"></div>')
        html.append('  </div>')
        html.append('</div>')

        return "\n".join(html)


# ==================== 所见即所得表单生成器 ====================

class WYSIWYGFormGenerator:
    """
    所见即所得表单生成器

    核心理念：业主不再被动填写，而是核对和确认AI从文档中提取的数据
    """

    def __init__(self):
        self.field_generator = FieldHTMLGenerator()
        self._css = DEFAULT_CSS
        self._javascript = DEFAULT_JAVASCRIPT

    def generate_form(
        self,
        extraction_result,
        template: Dict,
        options: Dict = None
    ) -> str:
        """
        生成交互式表单HTML

        Args:
            extraction_result: 文档提取结果
            template: 表单模板
            options: 生成选项

        Returns:
            str: 表单HTML
        """
        options = options or {}
        form_id = options.get("form_id", "smart_form_" + hashlib.md5(
            str(datetime.now().timestamp()).encode()
        ).hexdigest()[:8])

        extracted = extraction_result.extracted_fields
        validations = extraction_result.validation_results

        # 构建字段映射
        fields_map = {f["name"]: f for f in template["fields"]}

        html = []

        # HTML头部
        html.append('<div class="smart-form">')

        # 头部
        confidence = int(extraction_result.overall_confidence * 100)
        html.append(f'''
        <div class="smart-form-header">
            <h2>📋 {template.get("label", "智能表单")}</h2>
            <div class="confidence-badge">🤖 AI提取可信度: {confidence}%</div>
        </div>
        ''')

        # 按分组生成字段
        sections = self._group_fields_by_section(template["fields"])

        for section_name, fields in sections.items():
            html.append(f'<div class="form-section">')
            html.append(f'  <h3 class="section-title">{section_name}</h3>')

            for field_config in fields:
                field_name = field_config["name"]
                field_extracted = extracted.get(field_name)
                field_validation = validations.get(field_name)

                field_html = self._generate_field_html(
                    field_config,
                    field_extracted,
                    field_validation
                )
                html.append(f'  {field_html}')

            html.append('</div>')

        # 底部操作栏
        html.append('''
        <div class="form-actions">
            <div class="left-actions">
                <button class="btn btn-save-draft">💾 保存草稿</button>
                <button class="btn btn-reset">🔄 重置</button>
            </div>
            <div class="right-actions">
                <button class="btn btn-primary btn-submit">✅ 提交表单</button>
            </div>
        </div>
        ''')

        html.append('</div>')

        # 包裹完整HTML
        full_html = self._wrap_html(
            "\n".join(html),
            form_id=form_id,
            options=options
        )

        return full_html

    def _generate_field_html(
        self,
        config: Dict,
        extracted: Optional[ExtractedField],
        validation: Optional[ValidationResult]
    ) -> str:
        """生成单个字段HTML"""
        field_type = config.get("type", "text")

        generators = {
            "text": self.field_generator.generate_text_field,
            "number": self.field_generator.generate_number_field,
            "select": self.field_generator.generate_select_field,
            "textarea": self.field_generator.generate_textarea_field,
            "email": self.field_generator.generate_text_field,
            "tel": self.field_generator.generate_text_field,
        }

        generator = generators.get(field_type, self.field_generator.generate_text_field)

        return generator(config, extracted, validation)

    def _group_fields_by_section(self, fields: List[Dict]) -> Dict[str, List[Dict]]:
        """将字段按分组"""
        sections = {}

        for field in fields:
            section = field.get("category", "基本信息")
            if section not in sections:
                sections[section] = []
            sections[section].append(field)

        # 翻译分组名称
        section_names = {
            "basic": "基本信息",
            "technical": "技术参数",
            "other": "其他信息"
        }

        translated = {}
        for section, fields_list in sections.items():
            name = section_names.get(section, section)
            translated[name] = fields_list

        return translated

    def _wrap_html(
        self,
        body_html: str,
        form_id: str,
        options: Dict
    ) -> str:
        """包装完整HTML"""
        title = options.get("title", "智能表单")

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
{self._css}
    </style>
</head>
<body>
    <div id="{form_id}">
{body_html}
    </div>

    <script>
    // 表单配置
    const FORM_CONFIG = {{
        formId: "{form_id}",
        websocketUrl: "{options.get("websocket_url", "ws://localhost:8765/form/assist")}",
        apiBaseUrl: "{options.get("api_base_url", "http://localhost:5000/api")}"
    }};

    // 初始化表单控制器
    document.addEventListener('DOMContentLoaded', function() {{
        window.smartForm = createSmartForm("{form_id}", FORM_CONFIG);
    }});
    </script>
    <script>
{self._javascript}
    </script>
</body>
</html>'''

        return html

    def generate_minimal_form(
        self,
        fields: List[Dict],
        extracted_data: Dict[str, Any]
    ) -> str:
        """
        生成简化版表单HTML（用于内嵌）

        Args:
            fields: 字段配置列表
            extracted_data: 提取的数据字典

        Returns:
            str: 简化表单HTML
        """
        html = ['<div class="smart-form-minimal">']

        for config in fields:
            field_name = config["name"]
            value = extracted_data.get(field_name, "")

            html.append(f'<div class="form-field">')
            html.append(f'  <label>{config.get("label", field_name)}</label>')

            field_type = config.get("type", "text")
            if field_type == "select":
                html.append(f'  <select data-field="{field_name}">')
                for opt in config.get("options", []):
                    html.append(f'    <option value="{opt}">{opt}</option>')
                html.append('  </select>')
            elif field_type == "textarea":
                html.append(f'  <textarea data-field="{field_name}">{value}</textarea>')
            else:
                html.append(f'  <input type="{field_type}" data-field="{field_name}" value="{value}">')

            html.append('</div>')

        html.append('</div>')

        return "\n".join(html)

    def get_css(self) -> str:
        """获取表单CSS"""
        return self._css

    def get_javascript(self) -> str:
        """获取表单JavaScript"""
        return self._javascript


# ==================== 导出函数 ====================

_generator_instance: Optional[WYSIWYGFormGenerator] = None


def get_generator() -> WYSIWYGFormGenerator:
    """获取表单生成器单例"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = WYSIWYGFormGenerator()
    return _generator_instance


def generate_form_html(
    extraction_result,
    template: Dict,
    options: Dict = None
) -> str:
    """
    生成表单HTML的便捷函数

    Args:
        extraction_result: 文档提取结果
        template: 表单模板
        options: 生成选项

    Returns:
        str: 完整HTML
    """
    generator = get_generator()
    return generator.generate_form(extraction_result, template, options)


def generate_minimal_form(fields: List[Dict], extracted_data: Dict) -> str:
    """生成简化表单"""
    generator = get_generator()
    return generator.generate_minimal_form(fields, extracted_data)
