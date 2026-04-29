# -*- coding: utf-8 -*-
"""
Semantic Parser - 语义解析器

将AI响应解析为结构化的UI描述符。
支持多种解析模式：
1. JSON模式 - 直接解析JSON格式的UI描述
2. Markdown模式 - 解析Markdown格式的UI定义
3. 关键词模式 - 基于关键词匹配推断UI结构
4. 混合模式 - 结合多种策略
"""

import re
import json
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

from .ui_descriptor import (
    UIDescriptor, FormDescriptor, WidgetDescriptor, 
    WidgetType, Option, ValidationRule,
    create_text_input, create_email_input, create_password_input,
    create_dropdown, create_checkbox, create_radio_group,
    create_button, create_submit_button, create_heading
)

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """解析结果"""
    success: bool
    descriptor: Optional[UIDescriptor] = None
    error: str = ""
    confidence: float = 0.0  # 解析置信度 0-1
    parse_mode: str = ""  # 使用的解析模式


class SemanticParser:
    """
    语义解析器
    
    将AI的自然语言或结构化输出转换为UI描述符。
    """
    
    def __init__(self):
        self._parse_strategies: List[Callable] = []
        self._keyword_mappings = self._build_keyword_mappings()
        self._pattern_mappings = self._build_pattern_mappings()
        
        # 注册默认策略
        self._register_default_strategies()
    
    def _build_keyword_mappings(self) -> Dict[str, Dict]:
        """构建关键词映射表"""
        return {
            # 控件类型关键词
            "text_input": {
                "keywords": ["输入", "文本框", "text", "input", "name", "姓名", "地址", "描述", "备注"],
                "type": "text_input",
                "default_label": "文本输入"
            },
            "email_input": {
                "keywords": ["邮箱", "email", "邮件", "e-mail"],
                "type": "email_input",
                "default_label": "邮箱地址"
            },
            "password_input": {
                "keywords": ["密码", "password", "pwd", "口令"],
                "type": "password_input",
                "default_label": "密码"
            },
            "number_input": {
                "keywords": ["数字", "number", "数量", "年龄", "金额", "电话", "手机"],
                "type": "number_input",
                "default_label": "数字输入"
            },
            "textarea": {
                "keywords": ["文本域", "textarea", "多行", "详细", "说明", "留言", "评论", "内容"],
                "type": "text_area",
                "default_label": "多行文本"
            },
            "dropdown": {
                "keywords": ["下拉", "select", "dropdown", "选择", "选项", "菜单"],
                "type": "dropdown",
                "default_label": "请选择"
            },
            "checkbox": {
                "keywords": ["复选", "checkbox", "多选", "同意", "接受", "订阅", "启用"],
                "type": "checkbox",
                "default_label": "选项"
            },
            "radio_group": {
                "keywords": ["单选", "radio", "性别", "选项"],
                "type": "radio_group",
                "default_label": "请选择"
            },
            "switch": {
                "keywords": ["开关", "switch", "toggle", "启用", "禁用"],
                "type": "switch",
                "default_label": "开关"
            },
            "date_picker": {
                "keywords": ["日期", "date", "出生", "预约", "开始日期", "结束日期"],
                "type": "date_picker",
                "default_label": "选择日期"
            },
            "file_upload": {
                "keywords": ["上传", "upload", "文件", "附件", "avatar", "头像"],
                "type": "file_upload",
                "default_label": "上传文件"
            },
            "button": {
                "keywords": ["按钮", "button", "提交", "注册", "登录", "保存", "发送", "确认", "取消"],
                "type": "button",
                "default_label": "按钮"
            },
            "submit": {
                "keywords": ["提交", "submit", "注册", "登录", "confirm", "确认"],
                "type": "submit_button",
                "default_label": "提交"
            }
        }
    
    def _build_pattern_mappings(self) -> List[Dict]:
        """构建正则表达式映射"""
        return [
            # JSON对象模式
            {
                "pattern": r'```(?:json)?\s*(\{[\s\S]*?\})\s*```',
                "type": "json_block",
                "priority": 100
            },
            # 简单JSON模式
            {
                "pattern": r'^\s*\{[\s\S]*\}\s*$',
                "type": "json_line",
                "priority": 90
            },
            # Markdown表格模式
            {
                "pattern": r'\|(.+)\|.+\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)',
                "type": "markdown_table",
                "priority": 80
            },
            # 标题模式
            {
                "pattern": r'^#{1,6}\s+(.+)$',
                "type": "heading",
                "priority": 50
            },
            # YAML风格模式
            {
                "pattern": r'^\s*-\s+\w+:\s*.+$',
                "type": "yaml_list",
                "priority": 70
            }
        ]
    
    def _register_default_strategies(self):
        """注册默认解析策略"""
        self._parse_strategies = [
            ("json", self._parse_json),
            ("yaml_like", self._parse_yaml_like),
            ("markdown_table", self._parse_markdown_table),
            ("keyword", self._parse_keyword_based),
            ("fallback", self._parse_fallback)
        ]
    
    def parse(self, text: str) -> ParseResult:
        """
        解析AI响应文本
        
        Args:
            text: AI响应文本
            
        Returns:
            ParseResult: 解析结果
        """
        if not text or not text.strip():
            return ParseResult(
                success=False,
                error="Empty input text",
                confidence=0.0,
                parse_mode="none"
            )
        
        text = text.strip()
        logger.info(f"Parsing AI response (length: {len(text)})")
        
        # 尝试各种解析策略
        for name, strategy in self._parse_strategies:
            result = strategy(text)
            if result.success:
                logger.info(f"Successfully parsed using '{name}' strategy (confidence: {result.confidence})")
                return result
        
        # 如果所有策略都失败，返回失败结果
        return ParseResult(
            success=False,
            error="Failed to parse UI description",
            confidence=0.0,
            parse_mode="none"
        )
    
    def _parse_json(self, text: str) -> ParseResult:
        """解析JSON格式"""
        # 尝试从代码块中提取JSON
        json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if json_match:
            json_str = json_match.group(1)
        elif text.strip().startswith('{'):
            json_str = text.strip()
        else:
            return ParseResult(success=False, parse_mode="json")
        
        try:
            data = json.loads(json_str)
            descriptor = self._parse_json_structure(data)
            return ParseResult(
                success=True,
                descriptor=descriptor,
                confidence=0.95,
                parse_mode="json"
            )
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {e}")
            return ParseResult(success=False, error=str(e), parse_mode="json")
    
    def _parse_json_structure(self, data: Dict) -> UIDescriptor:
        """解析JSON结构为UIDescriptor"""
        # 处理标准格式
        if "ui_type" in data or "type" in data:
            return UIDescriptor.from_dict(data)
        
        # 处理嵌套widgets格式
        if "widgets" in data or "fields" in data:
            widgets_data = data.get("widgets") or data.get("fields", [])
            widgets = []
            for w in widgets_data:
                if isinstance(w, dict):
                    widgets.append(WidgetDescriptor.from_dict(w))
                else:
                    widgets.append(w)
            
            return UIDescriptor(
                ui_type=data.get("type", "form"),
                title=data.get("title", ""),
                description=data.get("description", ""),
                widgets=widgets,
                layout_type=data.get("layout_type", "flow"),
                columns=data.get("columns", 3)
            )
        
        # 处理简单的key-value格式
        widgets = []
        for key, value in data.items():
            if isinstance(value, dict):
                widget = self._dict_to_widget(key, value)
            elif isinstance(value, str):
                widget = create_text_input(label=value, field=key)
            elif isinstance(value, list):
                options = [(str(v), str(v)) for v in value]
                widget = create_dropdown(label=key, field=key, options=options)
            else:
                widget = create_text_input(label=key, field=key)
            widgets.append(widget)
        
        return UIDescriptor(
            ui_type="form",
            widgets=widgets
        )
    
    def _dict_to_widget(self, key: str, value: Dict) -> WidgetDescriptor:
        """将字典转换为控件描述符"""
        widget_type = value.get("type", "text_input")
        label = value.get("label", key)
        
        widget = WidgetDescriptor(
            type=widget_type,
            id=value.get("id", key),
            label=label,
            placeholder=value.get("placeholder", ""),
            default_value=value.get("default"),
            required=value.get("required", False),
            disabled=value.get("disabled", False)
        )
        
        # 处理选项
        if "options" in value:
            options_data = value["options"]
            if isinstance(options_data, list):
                widget.options = [
                    Option(value=str(opt) if isinstance(opt, str) else opt.get("value", ""),
                           label=opt if isinstance(opt, str) else opt.get("label", str(opt)))
                    for opt in options_data
                ]
        
        # 处理验证规则
        if "validation" in value:
            validation = value["validation"]
            if isinstance(validation, str):
                widget.validations.append(ValidationRule(rule_type=validation))
            elif isinstance(validation, dict):
                widget.validations.append(ValidationRule(
                    rule_type=validation.get("type", "custom"),
                    value=validation.get("value"),
                    message=validation.get("message", "")
                ))
        
        return widget
    
    def _parse_yaml_like(self, text: str) -> ParseResult:
        """解析类YAML格式"""
        # 检测YAML列表格式
        yaml_pattern = r'^\s*-\s+(\w+):\s*(.+)$'
        lines = text.strip().split('\n')
        
        if not all(re.match(yaml_pattern, line) for line in lines if line.strip()):
            return ParseResult(success=False, parse_mode="yaml_like")
        
        widgets = []
        for line in lines:
            match = re.match(yaml_pattern, line.strip())
            if match:
                field, desc = match.groups()
                # 根据描述推断控件类型
                widget = self._infer_widget_from_description(field, desc)
                widgets.append(widget)
        
        if widgets:
            return ParseResult(
                success=True,
                descriptor=UIDescriptor(ui_type="form", widgets=widgets),
                confidence=0.7,
                parse_mode="yaml_like"
            )
        
        return ParseResult(success=False, parse_mode="yaml_like")
    
    def _parse_markdown_table(self, text: str) -> ParseResult:
        """解析Markdown表格格式"""
        # 查找表格
        table_pattern = r'\|(.+)\|.+\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)'
        match = re.search(table_pattern, text, re.MULTILINE)
        
        if not match:
            return ParseResult(success=False, parse_mode="markdown_table")
        
        header_line = match.group(1)
        data_lines = match.group(2).strip().split('\n')
        
        # 解析表头
        headers = [h.strip() for h in header_line.split('|') if h.strip()]
        
        # 跳过前两个headers (标签和类型)
        if len(headers) < 2:
            return ParseResult(success=False, parse_mode="markdown_table")
        
        widgets = []
        for line in data_lines:
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if len(cells) >= 2:
                label = cells[0]
                widget_type = cells[1].lower().replace(' ', '_')
                
                # 推断控件类型
                if 'input' in widget_type or 'text' in widget_type:
                    widget = create_text_input(label=label, field=label)
                elif 'select' in widget_type or 'dropdown' in widget_type:
                    options = [(c, c) for c in cells[2:]] if len(cells) > 2 else []
                    widget = create_dropdown(label=label, field=label, options=options)
                elif 'checkbox' in widget_type:
                    widget = create_checkbox(label=label, field=label)
                elif 'radio' in widget_type:
                    options = cells[2:] if len(cells) > 2 else []
                    widget = create_radio_group(label=label, field=label, options=options)
                else:
                    widget = create_text_input(label=label, field=label)
                
                widgets.append(widget)
        
        return ParseResult(
            success=True,
            descriptor=UIDescriptor(ui_type="form", widgets=widgets),
            confidence=0.8,
            parse_mode="markdown_table"
        )
    
    def _parse_keyword_based(self, text: str) -> ParseResult:
        """基于关键词解析"""
        # 尝试从文本中提取结构化信息
        widgets = []
        
        # 分割句子
        sentences = re.split(r'[。\n]', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 查找包含表单字段的句子
            widget = self._extract_widget_from_sentence(sentence)
            if widget:
                widgets.append(widget)
        
        if widgets:
            return ParseResult(
                success=True,
                descriptor=UIDescriptor(ui_type="form", widgets=widgets),
                confidence=0.5,
                parse_mode="keyword"
            )
        
        return ParseResult(success=False, parse_mode="keyword")
    
    def _extract_widget_from_sentence(self, sentence: str) -> Optional[WidgetDescriptor]:
        """从句子中提取控件"""
        sentence_lower = sentence.lower()
        
        # 检查是否包含表单相关词汇
        form_indicators = ['输入', '选择', '填写', '输入', '录入', '提供', '请', '需要']
        if not any(ind in sentence for ind in form_indicators):
            return None
        
        # 尝试匹配已知关键词
        for key, mapping in self._keyword_mappings.items():
            if any(kw.lower() in sentence_lower for kw in mapping["keywords"]):
                # 提取字段名
                field_match = re.search(r'([^，,。:\s]+)', sentence)
                field = field_match.group(1) if field_match else key
                
                # 创建控件
                if key == "dropdown":
                    # 尝试提取选项
                    options = re.findall(r'["""]([^""""]+)["""]', sentence)
                    if not options:
                        options = re.findall(r'[、，]([^，,。]+)', sentence)
                    
                    widget = create_dropdown(
                        label=sentence[:30],
                        field=field,
                        options=[(opt, opt) for opt in options[:10]] if options else []
                    )
                elif key == "radio_group":
                    options = re.findall(r'["""]([^""""]+)["""]', sentence)
                    if not options:
                        options = re.findall(r'[、，]([^，,。]+)', sentence)
                    
                    widget = create_radio_group(
                        label=sentence[:30],
                        field=field,
                        options=options[:10] if options else []
                    )
                elif key == "checkbox":
                    widget = create_checkbox(label=sentence[:30], field=field)
                elif key == "submit":
                    widget = create_submit_button(label=sentence[:20])
                else:
                    widget = create_text_input(
                        label=sentence[:30],
                        field=field,
                        placeholder=sentence[:50]
                    )
                
                return widget
        
        # 如果没有匹配到具体类型，创建一个文本输入
        if len(sentence) > 3:
            return create_text_input(label=sentence[:30], field=f"field_{len(sentence)}")
        
        return None
    
    def _parse_fallback(self, text: str) -> ParseResult:
        """兜底解析 - 尝试提取任何可能的结构"""
        # 尝试分割为多个部分
        parts = re.split(r'[,，;；\n]', text)
        
        widgets = []
        for i, part in enumerate(parts):
            part = part.strip()
            if len(part) > 2:
                widget = create_text_input(label=part[:30], field=f"field_{i}")
                widgets.append(widget)
        
        if widgets:
            return ParseResult(
                success=True,
                descriptor=UIDescriptor(
                    ui_type="form",
                    title="表单",
                    description="从文本自动生成的表单",
                    widgets=widgets
                ),
                confidence=0.3,
                parse_mode="fallback"
            )
        
        return ParseResult(success=False, parse_mode="fallback")
    
    def _infer_widget_from_description(self, field: str, description: str) -> WidgetDescriptor:
        """根据描述推断控件类型"""
        desc_lower = description.lower()
        
        # 邮箱
        if 'email' in desc_lower or '邮箱' in desc_lower:
            return create_email_input(label=field, field=field)
        
        # 密码
        if 'password' in desc_lower or '密码' in desc_lower:
            return create_password_input(label=field, field=field)
        
        # 电话
        if 'phone' in desc_lower or 'tel' in desc_lower or '电话' in desc_lower:
            return create_text_input(label=field, field=field, placeholder="请输入电话号码")
        
        # 多行文本
        if 'desc' in desc_lower or 'description' in desc_lower or '详情' in desc_lower:
            return WidgetDescriptor(
                type="text_area",
                id=field,
                label=field,
                placeholder=description
            )
        
        # 下拉选择
        if 'select' in desc_lower or 'option' in desc_lower:
            # 尝试提取选项
            options_match = re.search(r'\[([^\]]+)\]', description)
            if options_match:
                options_text = options_match.group(1)
                options = [o.strip() for o in re.split(r'[,，]', options_text)]
                return create_dropdown(label=field, field=field, options=[(o, o) for o in options])
        
        # 复选框
        if 'agree' in desc_lower or 'accept' in desc_lower or '同意' in desc_lower:
            return create_checkbox(label=field, field=field)
        
        # 按钮
        if 'button' in desc_lower or 'submit' in desc_lower:
            return create_submit_button(label=field)
        
        # 默认文本输入
        return create_text_input(label=field, field=field, placeholder=description)


class PromptGenerator:
    """
    提示词生成器
    
    生成用于指导AI生成UI描述的提示词。
    """
    
    # UI Schema 示例
    SCHEMA_EXAMPLE = '''
```json
{
  "ui_type": "form",
  "title": "用户注册表单",
  "description": "请填写以下信息完成注册",
  "layout_type": "flow",
  "columns": 2,
  "widgets": [
    {
      "type": "text_input",
      "id": "username",
      "label": "用户名",
      "placeholder": "请输入用户名",
      "required": true
    },
    {
      "type": "email_input",
      "id": "email",
      "label": "邮箱",
      "placeholder": "请输入邮箱地址",
      "required": true
    },
    {
      "type": "radio_group",
      "id": "gender",
      "label": "性别",
      "options": [
        {"value": "male", "label": "男"},
        {"value": "female", "label": "女"}
      ],
      "required": true
    },
    {
      "type": "dropdown",
      "id": "country",
      "label": "国家/地区",
      "options": [
        {"value": "cn", "label": "中国"},
        {"value": "us", "label": "美国"}
      ],
      "default_value": "cn"
    },
    {
      "type": "checkbox",
      "id": "agree_terms",
      "label": "我同意服务条款",
      "default_value": false
    },
    {
      "type": "submit_button",
      "label": "注册"
    }
  ]
}
```'''
    
    SYSTEM_PROMPT = '''你是一个专业的UI描述生成器。

根据用户需求，生成符合以下JSON Schema的UI描述符：

支持的控件类型：
- text_input: 文本输入框
- email_input: 邮箱输入框
- password_input: 密码输入框
- number_input: 数字输入框
- text_area: 多行文本域
- dropdown: 下拉选择框
- checkbox: 复选框
- radio_group: 单选按钮组
- switch: 开关
- date_picker: 日期选择器
- file_upload: 文件上传
- button/submit_button: 按钮

布局类型：
- vertical: 垂直布局
- horizontal: 水平布局
- flow: 流式布局（自动换行）
- grid: 网格布局

请直接输出JSON格式的UI描述，不要包含其他解释文字。'''
    
    @classmethod
    def generate_prompt(cls, user_request: str, context: Dict = None) -> str:
        """生成完整提示词"""
        prompt = f'''{cls.SYSTEM_PROMPT}

用户需求：
{user_request}

示例输出格式：
{cls.SCHEMA_EXAMPLE}

请根据用户需求生成对应的UI描述。'''
        
        if context:
            prompt += f'\n\n上下文信息：\n{json.dumps(context, ensure_ascii=False, indent=2)}'
        
        return prompt
    
    @classmethod
    def generate_validation_prompt(cls, form_data: Dict, validation_rules: List[Dict]) -> str:
        """生成验证提示词"""
        return f'''请验证以下表单数据：

表单数据：
{json.dumps(form_data, ensure_ascii=False, indent=2)}

验证规则：
{json.dumps(validation_rules, ensure_ascii=False, indent=2)}

请返回验证结果，格式：
{{
  "valid": true/false,
  "errors": {{"field_name": "错误信息"}}
}}'''
