# =================================================================
# 表单智能解析器 - Form Parser
# =================================================================
# 功能：
# 1. 基础解析：提取 input/select/textarea 字段
# 2. 语义增强：从标签、占位符、附近文本推测语义类型
# 3. 结构分析：识别字段组、依赖关系、必填项
# =================================================================

import re
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from bs4 import BeautifulSoup


class FieldType(Enum):
    """字段 HTML 类型"""
    INPUT_TEXT = "text"
    INPUT_PASSWORD = "password"
    INPUT_EMAIL = "email"
    INPUT_NUMBER = "number"
    INPUT_TEL = "tel"
    INPUT_URL = "url"
    INPUT_SEARCH = "search"
    INPUT_DATE = "date"
    INPUT_TIME = "time"
    INPUT_DATETIME = "datetime-local"
    INPUT_FILE = "file"
    INPUT_CHECKBOX = "checkbox"
    INPUT_RADIO = "radio"
    INPUT_RANGE = "range"
    INPUT_HIDDEN = "hidden"
    SELECT = "select"
    SELECT_MULTIPLE = "select-multiple"
    TEXTAREA = "textarea"
    BUTTON = "button"
    UNKNOWN = "unknown"


class FieldSemanticType(Enum):
    """字段语义类型"""
    # 个人信息
    NAME = "name"                  # 姓名
    NAME_FAMILY = "name_family"   # 姓
    NAME_GIVEN = "name_given"      # 名
    EMAIL = "email"                # 邮箱
    PHONE = "phone"               # 电话
    PHONE_MOBILE = "phone_mobile" # 手机
    ADDRESS = "address"            # 地址
    ADDRESS_PROVINCE = "addr_province"
    ADDRESS_CITY = "addr_city"
    ADDRESS_DISTRICT = "addr_district"
    ADDRESS_STREET = "addr_street"

    # 身份证件
    ID_CARD = "id_card"           # 身份证
    PASSPORT = "passport"          # 护照
    LICENSE_PLATE = "license_plate"

    # 企业信息
    COMPANY_NAME = "company_name"
    COMPANY_CODE = "company_code"  # 统一社会信用代码
    TAX_ID = "tax_id"             # 税号

    # 金融
    BANK_ACCOUNT = "bank_account"
    BANK_NAME = "bank_name"
    AMOUNT = "amount"
    PRICE = "price"

    # 日期时间
    DATE = "date"
    DATE_START = "date_start"
    DATE_END = "date_end"
    TIME = "time"

    # 文本
    DESCRIPTION = "description"    # 描述
    REMARK = "remark"              # 备注
    COMMENT = "comment"            # 评价
    INTRODUCTION = "introduction"  # 简介

    # 选项类
    GENDER = "gender"
    EDUCATION = "education"
    OCCUPATION = "occupation"
    INDUSTRY = "industry"
    COUNTRY = "country"
    LANGUAGE = "language"

    # 布尔
    AGREEMENT = "agreement"        # 同意协议
    SUBSCRIBE = "subscribe"       # 订阅

    # 数值
    QUANTITY = "quantity"
    PERCENTAGE = "percentage"
    AGE = "age"

    # 文件
    FILE_UPLOAD = "file_upload"
    IMAGE_UPLOAD = "image_upload"
    AVATAR_UPLOAD = "avatar_upload"

    # 其他
    USERNAME = "username"
    PASSWORD = "password"
    PASSWORD_CONFIRM = "password_confirm"
    CAPTCHA = "captcha"
    VERIFY_CODE = "verify_code"
    URL = "url"
    TITLE = "title"               # 标题
    KEYWORD = "keyword"            # 关键词
    TAG = "tag"                   # 标签
    SEARCH = "search"             # 搜索
    UNKNOWN = "unknown"


class FieldSource(Enum):
    """字段数据来源"""
    KNOWLEDGE_BASE = "knowledge_base"  # 本地知识库
    BROWSER_AUTOFILL = "browser_autofill"
    CONTEXT = "context"              # 上下文推测
    TEMPLATE = "template"            # 模板库
    AI_GENERATED = "ai_generated"    # AI生成
    HISTORY = "history"              # 历史记录


@dataclass
class FormField:
    """表单字段"""
    # 基础信息
    name: str                       # HTML name 属性
    field_id: str                   # HTML id 属性
    field_type: FieldType           # HTML 字段类型
    semantic_type: FieldSemanticType # 语义类型

    # 位置信息
    element_xpath: str = ""         # 元素 XPath
    rect: Dict[str, int] = field(default_factory=dict)  # 位置 {x, y, width, height}

    # 内容
    label: str = ""                 # 字段标签（如"企业名称"）
    placeholder: str = ""           # 占位符
    value: str = ""                 # 当前值
    default_value: str = ""         # 默认值

    # 约束
    required: bool = False          # 是否必填
    readonly: bool = False          # 是否只读
    disabled: bool = False          # 是否禁用
    max_length: int = 0             # 最大长度
    min_length: int = 0             # 最小长度
    max_value: float = 0            # 最大值
    min_value: float = 0            # 最小值

    # 选项（用于 select/radio/checkbox）
    options: List[Dict[str, str]] = field(default_factory=list)
    # [{value: "1", text: "男"}, {value: "2", text: "女"}]

    # 语义分析结果
    confidence: float = 0.0         # 类型识别置信度 0-1
    related_fields: List[str] = field(default_factory=list)  # 关联字段名
    group_id: str = ""              # 字段组 ID

    # 状态
    is_filled: bool = False         # 是否已填充
    suggested_values: List[Any] = field(default_factory=list)  # 建议值列表

    # 原始元素引用（用于注入）
    element_selector: str = ""      # CSS 选择器


@dataclass
class FormStructure:
    """表单结构"""
    form_id: str
    url: str
    domain: str
    fields: List[FormField] = field(default_factory=list)
    field_count: int = 0
    filled_count: int = 0
    required_count: int = 0
    filled_required_count: int = 0

    # 字段分组
    groups: Dict[str, List[FormField]] = field(default_factory=dict)
    # {"基本信息": [field1, field2], "企业信息": [field3, field4]}

    # 依赖关系
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    # {"has_spouse": ["spouse_name", "spouse_id"]}

    # 表单类型推测
    form_type: str = ""             # "login", "register", "profile", "application"等
    form_name: str = ""             # 表单名称

    # 解析元数据
    parsed_at: float = 0            # 解析时间戳
    parser_version: str = "1.0"


class FormParser:
    """
    表单智能解析器

    功能：
    1. HTML -> 表单字段列表
    2. 字段语义类型推断
    3. 字段分组和依赖关系识别
    4. 表单类型推测
    """

    # 语义类型识别规则
    SEMANTIC_PATTERNS = {
        # 姓名类
        FieldSemanticType.NAME: [
            r"姓名", r"name", r"真实姓名", r"your\s*name", r"full\s*name",
            r"用户名", r"nickname", r"nick\s*name",  # 注意：username有时是账号
        ],
        FieldSemanticType.NAME_FAMILY: [
            r"姓", r"last\s*name", r"family\s*name", r"姓氏",
        ],
        FieldSemanticType.NAME_GIVEN: [
            r"名", r"first\s*name", r"given\s*name",
        ],

        # 联系方式
        FieldSemanticType.EMAIL: [
            r"邮箱", r"email", r"e-mail", r"邮件", r"mail",
        ],
        FieldSemanticType.PHONE: [
            r"电话", r"phone", r"tel", r"固话", r"座机",
        ],
        FieldSemanticType.PHONE_MOBILE: [
            r"手机", r"mobile", r"cell", r"电话号码", r"手機",
        ],

        # 地址
        FieldSemanticType.ADDRESS: [
            r"地址", r"address", r"住址", r"所在地",
        ],
        FieldSemanticType.ADDRESS_PROVINCE: [
            r"省", r"province", r"省份",
        ],
        FieldSemanticType.ADDRESS_CITY: [
            r"市", r"city",
        ],
        FieldSemanticType.ADDRESS_DISTRICT: [
            r"区", r"县", r"district", r"county",
        ],

        # 证件
        FieldSemanticType.ID_CARD: [
            r"身份证", r"id\s*card", r"证件号", r"certificatenum",
            r"证件号码", r"公民身份号码",
        ],
        FieldSemanticType.PASSPORT: [
            r"护照", r"passport",
        ],

        # 企业
        FieldSemanticType.COMPANY_NAME: [
            r"企业名称", r"公司名称", r"company\s*name", r"单位名称",
            r"机构名称", r"组织名称", r"名称",
        ],
        FieldSemanticType.COMPANY_CODE: [
            r"统一社会信用代码", r"信用代码", r"组织机构代码",
            r"company\s*code", r"org\s*code", r"社会信用代码",
        ],

        # 金融
        FieldSemanticType.AMOUNT: [
            r"金额", r"amount", r"sum", r"总额", r"总计",
        ],
        FieldSemanticType.PRICE: [
            r"价格", r"price", r"报价", r"单价", r"费用",
        ],

        # 日期
        FieldSemanticType.DATE: [
            r"日期", r"date", r"时间", r"日程",
        ],
        FieldSemanticType.DATE_START: [
            r"开始日期", r"start\s*date", r"有效期起",
        ],
        FieldSemanticType.DATE_END: [
            r"结束日期", r"end\s*date", r"截止日期", r"有效期至",
        ],

        # 文本
        FieldSemanticType.DESCRIPTION: [
            r"描述", r"description", r"详情", r"说明", r"具体内容",
        ],
        FieldSemanticType.INTRODUCTION: [
            r"简介", r"introduction", r"概述", r"概要",
        ],

        # 性别
        FieldSemanticType.GENDER: [
            r"性别", r"gender", r"sex",
        ],

        # 文件上传
        FieldSemanticType.FILE_UPLOAD: [
            r"上传文件", r"upload", r"附件", r"文件上传",
        ],
        FieldSemanticType.IMAGE_UPLOAD: [
            r"上传图片", r"上传照片", r"image\s*upload",
        ],
        FieldSemanticType.AVATAR_UPLOAD: [
            r"头像", r"avatar", r"照片",
        ],

        # 账号密码
        FieldSemanticType.USERNAME: [
            r"账号", r"username", r"account", r"user\s*name",
        ],
        FieldSemanticType.PASSWORD: [
            r"密码", r"password", r"pwd",
        ],
        FieldSemanticType.PASSWORD_CONFIRM: [
            r"确认密码", r"confirm\s*password", r"再次输入密码",
        ],

        # 验证码
        FieldSemanticType.CAPTCHA: [
            r"验证码", r"captcha", r"图形验证码",
        ],
        FieldSemanticType.VERIFY_CODE: [
            r"短信验证码", r"手机验证码", r"verify\s*code", r"code",
        ],

        # 选项类
        FieldSemanticType.EDUCATION: [
            r"学历", r"education", r"受教育程度",
        ],
        FieldSemanticType.OCCUPATION: [
            r"职业", r"occupation", r"job", r"工作",
        ],

        # 协议
        FieldSemanticType.AGREEMENT: [
            r"同意", r"协议", r"条款", r"须知", r"agreement",
            r"terms", r"policy", r"privacy",
        ],

        # 标题/关键词
        FieldSemanticType.TITLE: [
            r"标题", r"title", r"主题",
        ],
        FieldSemanticType.KEYWORD: [
            r"关键词", r"keyword", r"tags", r"标签",
        ],
        FieldSemanticType.SEARCH: [
            r"搜索", r"search", r"查询",
        ],
    }

    # HTML type -> FieldType 映射
    HTML_TYPE_MAP = {
        "text": FieldType.INPUT_TEXT,
        "password": FieldType.INPUT_PASSWORD,
        "email": FieldType.INPUT_EMAIL,
        "number": FieldType.INPUT_NUMBER,
        "tel": FieldType.INPUT_TEL,
        "url": FieldType.INPUT_URL,
        "search": FieldType.INPUT_SEARCH,
        "date": FieldType.INPUT_DATE,
        "time": FieldType.INPUT_TIME,
        "datetime-local": FieldType.INPUT_DATETIME,
        "file": FieldType.INPUT_FILE,
        "checkbox": FieldType.INPUT_CHECKBOX,
        "radio": FieldType.INPUT_RADIO,
        "range": FieldType.INPUT_RANGE,
        "hidden": FieldType.INPUT_HIDDEN,
        "submit": FieldType.BUTTON,
        "button": FieldType.BUTTON,
        "reset": FieldType.BUTTON,
        "image": FieldType.BUTTON,
    }

    def __init__(self):
        self._soup: Optional[BeautifulSoup] = None
        self._html: str = ""

    def parse(self, html: str, url: str = "") -> FormStructure:
        """
        解析 HTML 中的表单

        Args:
            html: HTML 内容
            url: 页面 URL（用于域名和表单类型判断）

        Returns:
            FormStructure: 表单结构
        """
        self._html = html
        self._soup = BeautifulSoup(html, "html.parser")

        # 提取域名
        domain = self._extract_domain(url)

        # 创建表单结构
        form = FormStructure(
            form_id=self._generate_form_id(url),
            url=url,
            domain=domain,
            parsed_at=self._current_timestamp(),
        )

        # 查找所有表单
        form_elements = self._soup.find_all("form")
        if not form_elements:
            # 如果没有 form 标签，查找独立的输入元素
            form_elements = [None]

        for form_elem in form_elements:
            fields = self._extract_fields(form_elem)
            form.fields.extend(fields)

        # 分析表单结构
        self._analyze_structure(form)

        # 推测表单类型
        form.form_type = self._infer_form_type(form, url)

        # 统计
        form.field_count = len(form.fields)
        form.filled_count = sum(1 for f in form.fields if f.is_filled)
        form.required_count = sum(1 for f in form.fields if f.required)
        form.filled_required_count = sum(
            1 for f in form.fields if f.required and f.is_filled
        )

        return form

    def _extract_fields(self, form_elem) -> List[FormField]:
        """提取表单字段"""
        fields = []

        # 查找所有输入元素
        selectors = [
            "input", "select", "textarea", "button[type='submit']"
        ]

        for selector in selectors:
            elements = form_elem.find_all(selector) if form_elem else self._soup.find_all(selector)

            for elem in elements:
                field = self._parse_field_element(elem)
                if field:
                    fields.append(field)

        # 提取字段组
        self._extract_field_groups(fields)

        return fields

    def _parse_field_element(self, elem) -> Optional[FormField]:
        """解析单个字段元素"""
        tag_name = elem.name.lower()

        # 获取基础属性
        name = elem.get("name", "")
        field_id = elem.get("id", "")
        field_type_str = elem.get("type", "text" if tag_name == "input" else "text")
        placeholder = elem.get("placeholder", "")
        required = elem.get("required", False) or elem.get("aria-required", False)
        readonly = elem.get("readonly", False) or elem.get("aria-readonly", False)
        disabled = elem.get("disabled", False)
        max_length = int(elem.get("maxlength", 0))
        min_length = int(elem.get("minlength", 0))
        value = elem.get("value", "")

        # 跳过隐藏字段（但保留重要的）
        if field_type_str == "hidden" and not self._is_important_hidden(name, field_id):
            return None

        # 映射 HTML type
        if tag_name == "input":
            field_type = self.HTML_TYPE_MAP.get(field_type_str, FieldType.INPUT_TEXT)
        elif tag_name == "select":
            field_type = FieldType.SELECT_MULTIPLE if elem.get("multiple") else FieldType.SELECT
        elif tag_name == "textarea":
            field_type = FieldType.TEXTAREA
        elif tag_name == "button":
            field_type = FieldType.BUTTON
        else:
            field_type = FieldType.UNKNOWN

        # 提取标签
        label = self._extract_label(elem)

        # 提取选项（用于 select/radio/checkbox）
        options = self._extract_options(elem, field_type)

        # 推断语义类型
        semantic_type, confidence = self._infer_semantic_type(
            name, field_id, label, placeholder, field_type, options
        )

        # 提取 xpath
        xpath = self._get_xpath(elem)

        # CSS 选择器
        selector = self._get_css_selector(elem)

        field = FormField(
            name=name,
            field_id=field_id,
            field_type=field_type,
            semantic_type=semantic_type,
            label=label,
            placeholder=placeholder,
            value=value,
            default_value=value,
            required=required,
            readonly=readonly,
            disabled=disabled,
            max_length=max_length or 0,
            min_length=min_length or 0,
            options=options,
            confidence=confidence,
            element_xpath=xpath,
            element_selector=selector,
        )

        return field

    def _extract_label(self, elem) -> str:
        """提取字段标签"""
        # 1. 查找 label 标签
        parent = elem.parent
        if parent and parent.name == "label":
            label_text = parent.get_text(strip=True)
            if label_text:
                return label_text

        # 2. 查找 id 对应的 label
        field_id = elem.get("id")
        if field_id:
            label_elem = self._soup.find("label", {"for": field_id})
            if label_elem:
                return label_elem.get_text(strip=True)

        # 3. 查找前面的文本节点
        label_text = self._get_preceding_text(elem)
        if label_text:
            return label_text

        # 4. 查找 aria-label
        aria_label = elem.get("aria-label", "")
        if aria_label:
            return aria_label

        # 5. 查找 title
        title = elem.get("title", "")
        if title:
            return title

        return ""

    def _get_preceding_text(self, elem, max_length: int = 100) -> str:
        """获取元素前面的文本"""
        text_parts = []
        for sibling in elem.previous_siblings:
            if hasattr(sibling, 'name'):
                if sibling.name == "label":
                    text_parts.append(sibling.get_text(strip=True))
                    break
                elif sibling.name in ["script", "style", "noscript"]:
                    continue
                elif sibling.name and sibling.name.startswith("h"):
                    # 标题元素通常是分组标签
                    text_parts.append(sibling.get_text(strip=True))
                    break
            else:
                # 文本节点
                text = str(sibling).strip()
                if text:
                    text_parts.append(text)

        result = " ".join(reversed(text_parts))
        return result[:max_length] if result else ""

    def def _extract_options(self, elem, field_type: FieldType) -> List[Dict[str, str]]:
        """提取选项（用于 select/radio/checkbox）"""
        options = []

        if field_type in [FieldType.SELECT, FieldType.SELECT_MULTIPLE]:
            for option in elem.find_all("option"):
                options.append({
                    "value": option.get("value", option.get_text(strip=True)),
                    "text": option.get_text(strip=True),
                    "selected": bool(option.get("selected")),
                })

        elif field_type == FieldType.INPUT_RADIO:
            name = elem.get("name", "")
            for radio in self._soup.find_all("input", {"type": "radio", "name": name}):
                label = self._soup.find("label", {"for": radio.get("id")})
                label_text = label.get_text(strip=True) if label else radio.get("value", "")
                options.append({
                    "value": radio.get("value", ""),
                    "text": label_text,
                    "checked": bool(radio.get("checked")),
                })

        elif field_type == FieldType.INPUT_CHECKBOX:
            label = self._soup.find("label", {"for": elem.get("id")})
            options.append({
                "value": elem.get("value", "on"),
                "text": label.get_text(strip=True) if label else "",
                "checked": bool(elem.get("checked")),
            })

        return options

    def _infer_semantic_type(
        self,
        name: str,
        field_id: str,
        label: str,
        placeholder: str,
        field_type: FieldType,
        options: List[Dict]
    ) -> Tuple[FieldSemanticType, float]:
        """
        推断字段语义类型

        Returns:
            (语义类型, 置信度)
        """
        name_lower = name.lower()
        id_lower = field_id.lower()
        label_lower = label.lower()
        placeholder_lower = placeholder.lower()

        # 组合文本用于匹配
        combined = f"{name_lower} {id_lower} {label_lower} {placeholder_lower}"

        best_match = FieldSemanticType.UNKNOWN
        best_confidence = 0.0

        for semantic_type, patterns in self.SEMANTIC_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    # 计算置信度
                    confidence = 0.5  # 基础置信度

                    # 标签中匹配（高权重）
                    if re.search(pattern, label_lower, re.IGNORECASE):
                        confidence = max(confidence, 0.85)

                    # name/id 中匹配（中等权重）
                    if re.search(pattern, name_lower, re.IGNORECASE):
                        confidence = max(confidence, 0.75)

                    # placeholder 中匹配（较低权重）
                    if re.search(pattern, placeholder_lower, re.IGNORECASE):
                        confidence = max(confidence, 0.6)

                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = semantic_type

        # 特殊处理：根据字段类型辅助判断
        if best_match == FieldSemanticType.UNKNOWN:
            best_match, best_confidence = self._infer_by_html_type(
                name, field_id, label, field_type, options
            )

        return best_match, best_confidence

    def _infer_by_html_type(
        self,
        name: str,
        field_id: str,
        label: str,
        field_type: FieldType,
        options: List[Dict]
    ) -> Tuple[FieldSemanticType, float]:
        """根据 HTML 类型辅助判断"""
        name_id = f"{name.lower()} {field_id.lower()}"

        # email 类型
        if field_type == FieldType.INPUT_EMAIL:
            return FieldSemanticType.EMAIL, 0.9

        # tel 类型
        if field_type == FieldType.INPUT_TEL:
            return FieldSemanticType.PHONE_MOBILE, 0.9

        # date 类型
        if field_type == FieldType.INPUT_DATE:
            if "start" in name_id or "begin" in name_id:
                return FieldSemanticType.DATE_START, 0.8
            elif "end" in name_id or "deadline" in name_id:
                return FieldSemanticType.DATE_END, 0.8
            return FieldSemanticType.DATE, 0.8

        # file 类型
        if field_type == FieldType.INPUT_FILE:
            if "avatar" in name_id or "photo" in name_id:
                return FieldSemanticType.AVATAR_UPLOAD, 0.8
            elif "image" in name_id or "img" in name_id:
                return FieldSemanticType.IMAGE_UPLOAD, 0.8
            return FieldSemanticType.FILE_UPLOAD, 0.7

        # password 类型
        if field_type == FieldType.INPUT_PASSWORD:
            if "confirm" in name_id or "again" in name_id:
                return FieldSemanticType.PASSWORD_CONFIRM, 0.9
            elif "new" in name_id:
                return FieldSemanticType.PASSWORD, 0.7
            return FieldSemanticType.PASSWORD, 0.85

        # select 选项分析
        if field_type in [FieldType.SELECT, FieldType.INPUT_RADIO] and options:
            first_option = options[0].get("text", "").lower() if options else ""

            if any(g in first_option for g in ["男", "女", "male", "female"]):
                return FieldSemanticType.GENDER, 0.8

            if any(e in first_option for e in ["小学", "初中", "高中", "本科", "硕士", "博士", "博士"]):
                return FieldSemanticType.EDUCATION, 0.8

        return FieldSemanticType.UNKNOWN, 0.3

    def _extract_field_groups(self, fields: List[FormField]):
        """提取字段分组"""
        # 字段组标识：legend、fieldset、h1-h6、相邻标题
        groups: Dict[str, List[FormField]] = {}
        current_group = "默认分组"
        group_counter = 0

        for field in fields:
            # 简单实现：按字段数量自动分组
            # 实际应用中需要分析 DOM 结构
            if len(groups.get(current_group, [])) >= 5:
                group_counter += 1
                current_group = f"分组 {group_counter}"

            if current_group not in groups:
                groups[current_group] = []
            groups[current_group].append(field)
            field.group_id = current_group

        return groups

    def _analyze_structure(self, form: FormStructure):
        """分析表单结构"""
        # 识别依赖关系
        # 例如：选择"否"时隐藏"配偶信息"字段组
        for field in form.fields:
            name_lower = field.name.lower()
            if "has_" in name_lower or "is_" in name_lower or "agree" in name_lower:
                # 这可能是一个控制字段
                dependent_fields = self._find_dependent_fields(field)
                if dependent_fields:
                    form.dependencies[field.name] = dependent_fields

    def _find_dependent_fields(self, control_field: FormField) -> List[str]:
        """查找被控制的字段"""
        # 简化实现：查找包含 control_field.name 模式的字段
        dependents = []
        control_name = control_field.name.lower()

        # 实际应用中需要分析 DOM 结构确定依赖关系
        return dependents

    def _infer_form_type(self, form: FormStructure, url: str) -> str:
        """推测表单类型"""
        url_lower = url.lower()

        # URL 模式匹配
        if any(x in url_lower for x in ["/login", "/signin", "/logon"]):
            return "login"
        elif any(x in url_lower for x in ["/register", "/signup", "/join", "/create"]):
            return "register"
        elif any(x in url_lower for x in ["/profile", "/account", "/settings"]):
            return "profile"
        elif any(x in url_lower for x in ["/checkout", "/order", "/cart"]):
            return "checkout"
        elif any(x in url_lower for x in ["/search", "/query"]):
            return "search"
        elif any(x in url_lower for x in ["/apply", "/submit", "/register"]):
            return "application"
        elif any(x in url_lower for x in ["/contact", "/feedback"]):
            return "contact"

        # 字段模式匹配
        field_names = [f.name.lower() for f in form.fields]
        field_labels = [f.label.lower() for f in form.fields]
        combined = " ".join(field_names + field_labels)

        if "password" in combined and "username" in combined:
            return "login"
        elif "confirm" in combined and "password" in combined:
            return "register"
        elif "company" in combined or "企业" in combined:
            return "enterprise"

        return "general"

    def _is_important_hidden(self, name: str, field_id: str) -> bool:
        """判断隐藏字段是否重要"""
        important_names = ["csrf", "token", "authenticity", "_csrf", "xsrf"]
        important_ids = important_names

        return (
            name.lower() in important_names or
            field_id.lower() in important_ids
        )

    def _extract_domain(self, url: str) -> str:
        """提取域名"""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return ""

    def _generate_form_id(self, url: str) -> str:
        """生成表单 ID"""
        import hashlib
        domain = self._extract_domain(url)
        return f"form_{hashlib.md5(f'{domain}_{self._current_timestamp()}'.encode()).hexdigest()[:8]}"

    def _get_xpath(self, elem) -> str:
        """获取元素 XPath"""
        components = []
        child = elem

        while child and child.name:
            parent = child.parent
            if parent is None:
                break

            siblings = parent.find_all(child.name, recursive=False)
            if len(siblings) == 1:
                index = ""
            else:
                index = f"[{siblings.index(child) + 1}]"

            components.append(f"{child.name}{index}")
            child = parent

        return "/" + "/".join(reversed(components))

    def _get_css_selector(self, elem) -> str:
        """获取 CSS 选择器"""
        if elem.get("id"):
            return f"#{elem.get('id')}"
        if elem.get("class"):
            classes = " ".join(elem.get("class"))
            return f"{elem.name}.{classes.replace(' ', '.')}"
        return elem.name

    def _current_timestamp(self) -> float:
        """获取当前时间戳"""
        import time
        return time.time()

    def serialize_form(self, form: FormStructure) -> Dict[str, Any]:
        """序列化表单为 JSON"""
        return {
            "form_id": form.form_id,
            "url": form.url,
            "domain": form.domain,
            "form_type": form.form_type,
            "field_count": form.field_count,
            "filled_count": form.filled_count,
            "required_count": form.required_count,
            "fields": [
                {
                    "name": f.name,
                    "field_id": f.field_id,
                    "field_type": f.field_type.value,
                    "semantic_type": f.semantic_type.value,
                    "label": f.label,
                    "required": f.required,
                    "filled": f.is_filled,
                    "confidence": f.confidence,
                }
                for f in form.fields
            ],
            "parsed_at": form.parsed_at,
        }
