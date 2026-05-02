# -*- coding: utf-8 -*-
"""
Markdown转Word文档系统 - 数据模型定义
=====================================

包含：
- 任务模型（Task, TaskStatus, TaskType等）
- 文档模型（DocumentNode, DocumentElement等）
- 样式模型（StyleTemplate, StyleConfig等）
- 进度模型（ProgressInfo, StepInfo等）
- 配置模型（ConversionConfig, ImageConfig等）
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
import uuid


# ============================================================================
# 枚举定义
# ============================================================================

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待中
    PREPARING = "preparing"       # 准备中
    CONVERTING = "converting"     # 转换中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 已失败
    CANCELLED = "cancelled"      # 已取消
    PAUSED = "paused"            # 已暂停


class TaskType(Enum):
    """任务类型枚举"""
    SINGLE_FILE = "single_file"      # 单文件转换
    BATCH = "batch"                  # 批量转换
    KNOWLEDGE_BASE = "knowledge_base"  # 知识库导出


class SourceType(Enum):
    """源文件类型枚举"""
    LOCAL_FILE = "local_file"        # 本地文件
    LOCAL_FOLDER = "local_folder"     # 本地文件夹
    URL = "url"                      # URL链接
    GIT_REPO = "git_repo"            # Git仓库
    CONFLUENCE = "confluence"        # Confluence
    NOTION = "notion"                # Notion
    YUQUE = "yuque"                   # 语雀
    CUSTOM_API = "custom_api"        # 自定义API


class TargetFormat(Enum):
    """目标格式枚举"""
    DOCX = "docx"                    # Word文档
    PDF = "pdf"                       # PDF文档
    HTML = "html"                    # HTML网页
    TXT = "txt"                      # 纯文本
    EPUB = "epub"                    # EPUB电子书


class ElementType(Enum):
    """文档元素类型枚举"""
    # 文本元素
    PARAGRAPH = "paragraph"          # 段落
    HEADING_1 = "heading_1"          # 一级标题
    HEADING_2 = "heading_2"          # 二级标题
    HEADING_3 = "heading_3"          # 三级标题
    HEADING_4 = "heading_4"          # 四级标题
    HEADING_5 = "heading_5"          # 五级标题
    HEADING_6 = "heading_6"          # 六级标题

    # 列表元素
    UNORDERED_LIST = "unordered_list"    # 无序列表
    ORDERED_LIST = "ordered_list"        # 有序列表
    LIST_ITEM = "list_item"              # 列表项
    TASK_LIST = "task_list"             # 任务列表
    TASK_ITEM = "task_item"             # 任务项

    # 容器元素
    BLOCKQUOTE = "blockquote"        # 引用块
    CODE_BLOCK = "code_block"       # 代码块
    TABLE = "table"                  # 表格
    HORIZONTAL_RULE = "horizontal_rule"  # 水平线

    # 行内元素
    TEXT = "text"                   # 文本
    BOLD = "bold"                   # 粗体
    ITALIC = "italic"               # 斜体
    STRIKETHROUGH = "strikethrough" # 删除线
    CODE = "code"                   # 行内代码
    LINK = "link"                   # 链接
    IMAGE = "image"                 # 图片
    MATH = "math"                  # 数学公式


class StyleType(Enum):
    """样式类型枚举"""
    # 文档样式
    DOCUMENT = "document"           # 文档整体样式
    PAGE = "page"                   # 页面样式

    # 段落样式
    NORMAL = "normal"               # 普通段落
    HEADING_1 = "heading_1"        # 一级标题样式
    HEADING_2 = "heading_2"        # 二级标题样式
    HEADING_3 = "heading_3"        # 三级标题样式
    HEADING_4 = "heading_4"        # 四级标题样式
    HEADING_5 = "heading_5"        # 五级标题样式
    HEADING_6 = "heading_6"        # 六级标题样式
    LIST = "list"                  # 列表样式
    QUOTE = "quote"                # 引用样式
    CODE_BLOCK = "code_block"      # 代码块样式

    # 字符样式
    CODE_INLINE = "code_inline"     # 行内代码样式
    LINK = "link"                  # 链接样式


class StepStatus(Enum):
    """步骤状态枚举"""
    PENDING = "pending"             # 等待中
    RUNNING = "running"            # 运行中
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"              # 已失败
    SKIPPED = "skipped"            # 已跳过


class TemplateCategory(Enum):
    """模板类别枚举"""
    BUSINESS = "business"          # 商务文档
    ACADEMIC = "academic"          # 学术论文
    TECHNICAL = "technical"        # 技术文档
    REPORT = "report"              # 报告文档
    MEMO = "memo"                  # 备忘录
    CUSTOM = "custom"              # 自定义


class LinkMode(Enum):
    """链接处理模式枚举"""
    KEEP = "keep"                  # 保持原样
    REMOVE = "remove"              # 移除
    TO_WEB = "to_web"              # 转为网页链接
    TO_FILE = "to_file"            # 转为文件路径


class ImageMode(Enum):
    """图片处理模式枚举"""
    EMBED = "embed"                 # 嵌入文档
    LINK = "link"                  # 链接引用
    DOWNLOAD = "download"         # 下载到本地
    BASE64 = "base64"              # 转Base64


class CodeHighlight(Enum):
    """代码高亮模式枚举"""
    NONE = "none"                  # 无高亮
    PLAIN = "plain"                # 纯文本
    COLORED = "colored"            # 彩色高亮


# ============================================================================
# 配置模型
# ============================================================================

@dataclass
class ImageConfig:
    """图片配置"""
    mode: ImageMode = ImageMode.EMBED           # 处理模式
    max_width: int = 600                        # 最大宽度(px)
    max_height: int = 800                       # 最大高度(px)
    preserve_aspect_ratio: bool = True         # 保持宽高比
    alt_text: str = ""                          # 默认alt文本
    download_timeout: int = 30                 # 下载超时(秒)


@dataclass
class LinkConfig:
    """链接配置"""
    mode: LinkMode = LinkMode.KEEP              # 处理模式
    open_in_new_tab: bool = True                # 新标签页打开
    preserve_formatting: bool = True            # 保持格式
    validate_urls: bool = True                  # 验证URL


@dataclass
class CodeConfig:
    """代码配置"""
    highlight: CodeHighlight = CodeHighlight.COLORED  # 高亮模式
    line_numbers: bool = True                   # 显示行号
    theme: str = "monokai"                     # 高亮主题
    font_family: str = "Consolas"              # 字体
    font_size: int = 10                         # 字号
    background_color: str = "#f5f5f5"           # 背景色


@dataclass
class TableConfig:
    """表格配置"""
    border_style: str = "single"               # 边框样式
    border_color: str = "#cccccc"              # 边框颜色
    header_background: str = "#e0e0e0"         # 表头背景色
    alternate_rows: bool = True                # 交替行颜色
    alternate_color: str = "#f9f9f9"           # 交替行颜色
    auto_fit: bool = True                       # 自动适应宽度


@dataclass
class MathConfig:
    """数学公式配置"""
    engine: str = "matplotlib"                 # 渲染引擎
    font_size: int = 12                         # 字号
    dpi: int = 150                              # DPI
    math_font: str = "Cambria Math"            # 数学字体


@dataclass
class PageConfig:
    """页面配置"""
    page_size: str = "A4"                       # 纸张大小
    orientation: str = "portrait"              # 方向
    margin_top: float = 2.54                    # 上边距(cm)
    margin_bottom: float = 2.54                # 下边距(cm)
    margin_left: float = 3.18                  # 左边距(cm)
    margin_right: float = 3.18                 # 右边距(cm)
    header_distance: float = 1.27              # 页眉距离(cm)
    footer_distance: float = 1.27              # 页脚距离(cm)


@dataclass
class HeaderFooterConfig:
    """页眉页脚配置"""
    show_header: bool = False                   # 显示页眉
    show_footer: bool = True                   # 显示页脚
    header_text: str = ""                       # 页眉文本
    footer_text: str = "第 {page} 页 / 共 {total} 页"  # 页脚文本
    header_font: str = "宋体"                  # 页眉字体
    footer_font: str = "宋体"                  # 页脚字体
    header_font_size: int = 10                 # 页眉字号
    footer_font_size: int = 10                 # 页脚字号


@dataclass
class TOCConfig:
    """目录配置"""
    generate_toc: bool = True                  # 生成目录
    toc_depth: int = 3                          # 目录深度
    toc_title: str = "目录"                     # 目录标题
    toc_style: str = "default"                  # 目录样式
    page_break_before: bool = True             # 目录前分页


@dataclass
class ConversionConfig:
    """转换配置"""
    target_format: TargetFormat = TargetFormat.DOCX  # 目标格式
    source_encoding: str = "utf-8"             # 源文件编码
    output_encoding: str = "utf-8"             # 输出编码
    markdown_flavor: str = "gfm"               # Markdown口味 (gfm/commonmark/原始)

    # 样式配置
    style_template: str = "default"            # 样式模板
    page: PageConfig = field(default_factory=PageConfig)
    header_footer: HeaderFooterConfig = field(default_factory=HeaderFooterConfig)
    toc: TOCConfig = field(default_factory=TOCConfig)

    # 内容处理配置
    image: ImageConfig = field(default_factory=ImageConfig)
    link: LinkConfig = field(default_factory=LinkConfig)
    code: CodeConfig = field(default_factory=CodeConfig)
    table: TableConfig = field(default_factory=TableConfig)
    math: MathConfig = field(default_factory=MathConfig)

    # 高级配置
    preserve_whitespace: bool = True           # 保留空白
    preserve_comments: bool = False            # 保留注释
    enable_table_of_contents: bool = True      # 启用目录
    enable_styles: bool = True                 # 启用样式
    clean_html: bool = True                    # 清理HTML标签

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'target_format': self.target_format.value,
            'source_encoding': self.source_encoding,
            'output_encoding': self.output_encoding,
            'markdown_flavor': self.markdown_flavor,
            'style_template': self.style_template,
            'page': {
                'page_size': self.page.page_size,
                'orientation': self.page.orientation,
                'margins': {
                    'top': self.page.margin_top,
                    'bottom': self.page.margin_bottom,
                    'left': self.page.margin_left,
                    'right': self.page.margin_right,
                }
            },
            'toc': {
                'generate': self.toc.generate_toc,
                'depth': self.toc.toc_depth,
                'title': self.toc.toc_title,
            },
            'image_mode': self.image.mode.value,
            'code_highlight': self.code.highlight.value,
        }


# ============================================================================
# 文档模型
# ============================================================================

@dataclass
class DocumentElement:
    """文档元素"""
    element_type: ElementType
    content: str = ""
    children: List['DocumentElement'] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    # 样式属性
    style_name: Optional[str] = None
    font_name: Optional[str] = None
    font_size: Optional[int] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    text_color: Optional[str] = None
    background_color: Optional[str] = None
    alignment: str = "left"

    # 元素属性
    level: int = 1                    # 层级（标题级别、列表缩进等）
    checked: bool = False            # 任务项是否完成
    language: str = ""                # 代码语言
    alt_text: str = ""               # 图片alt文本
    url: str = ""                    # 链接URL
    image_path: str = ""             # 图片路径
    row_count: int = 0               # 表格行数
    col_count: int = 0               # 表格列数

    def add_child(self, child: 'DocumentElement'):
        """添加子元素"""
        self.children.append(child)

    def get_text(self) -> str:
        """获取纯文本内容"""
        if self.content:
            return self.content
        return "".join(child.get_text() for child in self.children)


@dataclass
class DocumentNode:
    """文档节点树"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: str = "root"
    elements: List[DocumentElement] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 文档元信息
    title: str = ""
    author: str = ""
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    language: str = "zh-CN"
    subject: str = ""

    def add_element(self, element: DocumentElement):
        """添加元素"""
        self.elements.append(element)

    def get_all_elements(self) -> List[DocumentElement]:
        """获取所有元素（递归）"""
        result = []
        for elem in self.elements:
            result.append(elem)
            result.extend(elem.children)
        return result


# ============================================================================
# 样式模型
# ============================================================================

@dataclass
class StyleConfig:
    """样式配置"""
    # 字体配置
    font_name: str = "宋体"
    font_size: int = 12
    font_size_pt: float = 12.0

    # 颜色配置
    text_color: str = "#000000"
    background_color: Optional[str] = None

    # 段落配置
    alignment: str = "left"
    line_spacing: float = 1.5
    space_before: float = 0
    space_after: float = 0
    first_line_indent: float = 0
    left_indent: float = 0
    right_indent: float = 0

    # 边框配置
    border_top: bool = False
    border_bottom: bool = False
    border_left: bool = False
    border_right: bool = False
    border_color: str = "#000000"
    border_width: float = 0.5

    # 特效配置
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    shadow: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'font_name': self.font_name,
            'font_size': self.font_size,
            'text_color': self.text_color,
            'background_color': self.background_color,
            'alignment': self.alignment,
            'line_spacing': self.line_spacing,
            'bold': self.bold,
            'italic': self.italic,
            'underline': self.underline,
        }


@dataclass
class StyleTemplate:
    """样式模板"""
    template_id: str = ""
    template_name: str = ""
    description: str = ""
    category: TemplateCategory = TemplateCategory.CUSTOM
    is_builtin: bool = False
    is_default: bool = False

    # 样式配置
    base_style: StyleConfig = field(default_factory=StyleConfig)
    heading_styles: Dict[int, StyleConfig] = field(default_factory=dict)
    code_style: StyleConfig = field(default_factory=StyleConfig)
    quote_style: StyleConfig = field(default_factory=StyleConfig)
    table_style: TableConfig = field(default_factory=TableConfig)

    # 页面配置
    page_config: PageConfig = field(default_factory=PageConfig)
    header_footer: HeaderFooterConfig = field(default_factory=HeaderFooterConfig)

    # 预览信息
    preview_image: Optional[str] = None
    author: str = ""
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)


# ============================================================================
# 进度模型
# ============================================================================

@dataclass
class StepInfo:
    """步骤信息"""
    step_id: str
    step_name: str
    step_order: int
    status: StepStatus = StepStatus.PENDING
    progress: float = 0.0              # 0.0 - 1.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    message: str = ""
    error_info: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        """计算持续时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'step_id': self.step_id,
            'step_name': self.step_name,
            'step_order': self.step_order,
            'status': self.status.value,
            'progress': self.progress,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'message': self.message,
            'error_info': self.error_info,
            'duration': self.duration,
        }


@dataclass
class ProgressInfo:
    """进度信息"""
    task_id: str
    total_steps: int
    current_step: int = 0
    current_step_name: str = ""
    overall_progress: float = 0.0      # 0.0 - 1.0

    # 步骤详情
    steps: List[StepInfo] = field(default_factory=list)

    # 估算信息
    start_time: Optional[datetime] = None
    estimated_remaining: Optional[int] = None  # 预估剩余秒数

    # 状态信息
    is_running: bool = False
    is_paused: bool = False
    is_cancelled: bool = False
    error_message: Optional[str] = None

    def add_step(self, step: StepInfo):
        """添加步骤"""
        self.steps.append(step)

    def update_step_progress(self, step_index: int, progress: float, message: str = ""):
        """更新步骤进度"""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].progress = progress
            if message:
                self.steps[step_index].message = message

    def complete_step(self, step_index: int):
        """完成步骤"""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].status = StepStatus.COMPLETED
            self.steps[step_index].progress = 1.0
            self.steps[step_index].end_time = datetime.now()

    def fail_step(self, step_index: int, error: str):
        """步骤失败"""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].status = StepStatus.FAILED
            self.steps[step_index].error_info = error
            self.steps[step_index].end_time = datetime.now()

    def calculate_overall_progress(self) -> float:
        """计算整体进度"""
        if not self.steps:
            return 0.0

        total = 0.0
        for step in self.steps:
            if step.status == StepStatus.COMPLETED:
                total += 1.0
            elif step.status == StepStatus.RUNNING:
                total += step.progress

        self.overall_progress = total / self.total_steps
        return self.overall_progress

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'total_steps': self.total_steps,
            'current_step': self.current_step,
            'current_step_name': self.current_step_name,
            'overall_progress': self.overall_progress,
            'steps': [step.to_dict() for step in self.steps],
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'estimated_remaining': self.estimated_remaining,
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'is_cancelled': self.is_cancelled,
            'error_message': self.error_message,
        }


# ============================================================================
# 知识库模型
# ============================================================================

@dataclass
class SourceConfig:
    """知识源配置"""
    source_type: SourceType
    # 通用配置
    base_url: str = ""
    auth_token: str = ""
    timeout: int = 30

    # Git配置
    repo_url: str = ""
    branch: str = "main"
    auth_method: str = "token"        # token/ssh/key

    # 文件夹配置
    folder_path: str = ""
    recursive: bool = True
    file_patterns: List[str] = field(default_factory=lambda: ["*.md", "*.markdown"])

    # 过滤配置
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=lambda: [".git/**", "node_modules/**"])


@dataclass
class KnowledgeSource:
    """知识源"""
    source_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = ""
    source_type: SourceType = SourceType.LOCAL_FOLDER
    source_url: str = ""
    description: str = ""

    # 配置
    config: SourceConfig = field(default_factory=SourceConfig)

    # 状态
    is_connected: bool = False
    last_sync_time: Optional[datetime] = None
    document_count: int = 0

    # 认证信息（仅内存存储）
    credentials: Dict[str, str] = field(default_factory=dict)


# ============================================================================
# 模板模型
# ============================================================================

@dataclass
class TemplateInfo:
    """模板信息"""
    template_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    template_name: str = ""
    template_description: str = ""
    category: TemplateCategory = TemplateCategory.CUSTOM

    # 文件信息
    file_path: str = ""
    file_size: int = 0
    is_builtin: bool = False

    # 预览
    preview_image: Optional[str] = None
    preview_text: str = ""

    # 元信息
    author: str = ""
    version: str = "1.0.0"
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None

    # 使用统计
    use_count: int = 0
    rating: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'template_id': self.template_id,
            'template_name': self.template_name,
            'template_description': self.template_description,
            'category': self.category.value,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'is_builtin': self.is_builtin,
            'author': self.author,
            'version': self.version,
            'use_count': self.use_count,
            'rating': self.rating,
        }


# ============================================================================
# 任务模型
# ============================================================================

@dataclass
class Task:
    """转换任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_name: str = ""
    task_type: TaskType = TaskType.SINGLE_FILE
    status: TaskStatus = TaskStatus.PENDING

    # 源信息
    source_type: SourceType = SourceType.LOCAL_FILE
    source_files: List[str] = field(default_factory=list)  # 源文件路径列表
    source_url: str = ""                                   # 源URL（知识库）
    knowledge_source: Optional[KnowledgeSource] = None     # 知识源

    # 目标信息
    target_format: TargetFormat = TargetFormat.DOCX
    output_path: str = ""                                  # 输出目录
    output_filename: str = ""                             # 输出文件名模板

    # 配置
    config: ConversionConfig = field(default_factory=ConversionConfig)
    template: Optional[StyleTemplate] = None              # 样式模板

    # 进度
    progress: ProgressInfo = None

    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_time: Optional[int] = None                   # 预估耗时（秒）

    # 结果
    result_file: str = ""                                  # 结果文件路径
    result_size: int = 0                                   # 结果文件大小
    error_message: str = ""
    error_details: Dict[str, Any] = field(default_factory=dict)

    # 断点续传
    checkpoint_data: Dict[str, Any] = field(default_factory=dict)
    resume_from_checkpoint: bool = False

    # 元数据
    user_id: Optional[str] = None
    priority: int = 0                                      # 优先级（数字越大优先级越高）
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'task_name': self.task_name,
            'task_type': self.task_type.value,
            'status': self.status.value,
            'source_type': self.source_type.value,
            'source_files': self.source_files,
            'target_format': self.target_format.value,
            'output_path': self.output_path,
            'overall_progress': self.progress.overall_progress if self.progress else 0,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result_file': self.result_file,
            'result_size': self.result_size,
            'error_message': self.error_message,
        }


# ============================================================================
# 结果模型
# ============================================================================

@dataclass
class ConversionError:
    """转换错误"""
    error_code: str = ""
    error_type: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    recoverable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'error_code': self.error_code,
            'error_type': self.error_type,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'recoverable': self.recoverable,
        }


@dataclass
class ConversionResult:
    """转换结果"""
    success: bool = False
    task_id: str = ""

    # 文件信息
    input_file: str = ""
    output_file: str = ""
    output_size: int = 0                                   # 字节
    page_count: int = 0                                    # 页数

    # 内容信息
    word_count: int = 0                                    # 字数
    paragraph_count: int = 0                               # 段落数
    image_count: int = 0                                   # 图片数
    table_count: int = 0                                   # 表格数
    code_block_count: int = 0                              # 代码块数

    # 性能信息
    processing_time: float = 0.0                           # 处理时间（秒）
    peak_memory: int = 0                                   # 峰值内存（字节）

    # 错误信息
    error: Optional[ConversionError] = None

    # 警告信息
    warnings: List[str] = field(default_factory=list)

    # 输出格式
    format: TargetFormat = TargetFormat.DOCX

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'task_id': self.task_id,
            'input_file': self.input_file,
            'output_file': self.output_file,
            'output_size': self.output_size,
            'output_size_mb': round(self.output_size / 1024 / 1024, 2),
            'page_count': self.page_count,
            'word_count': self.word_count,
            'paragraph_count': self.paragraph_count,
            'image_count': self.image_count,
            'table_count': self.table_count,
            'code_block_count': self.code_block_count,
            'processing_time': round(self.processing_time, 2),
            'processing_time_formatted': f"{self.processing_time:.2f}秒",
            'peak_memory_mb': round(self.peak_memory / 1024 / 1024, 2),
            'error': self.error.to_dict() if self.error else None,
            'warnings': self.warnings,
            'format': self.format.value,
        }


# ============================================================================
# 默认样式模板
# ============================================================================

def get_default_template() -> StyleTemplate:
    """获取默认样式模板"""
    template = StyleTemplate(
        template_id="default",
        template_name="默认模板",
        description="适用于大多数场景的默认样式模板",
        category=TemplateCategory.CUSTOM,
        is_builtin=True,
        is_default=True,
    )

    # 基础样式
    template.base_style = StyleConfig(
        font_name="宋体",
        font_size=12,
        text_color="#000000",
        alignment="left",
        line_spacing=1.5,
    )

    # 标题样式
    for level in range(1, 7):
        size = 32 - (level - 1) * 4
        template.heading_styles[level] = StyleConfig(
            font_name="黑体",
            font_size=size,
            text_color="#000000",
            bold=True,
            space_before=12 if level > 1 else 24,
            space_after=6,
        )

    # 代码样式
    template.code_style = StyleConfig(
        font_name="Consolas",
        font_size=10,
        text_color="#333333",
        background_color="#f5f5f5",
    )

    # 引用样式
    template.quote_style = StyleConfig(
        font_name="宋体",
        font_size=12,
        text_color="#666666",
        italic=True,
        left_indent=2.0,
        border_left=True,
    )

    # 表格样式
    template.table_style = TableConfig(
        border_style="single",
        border_color="#cccccc",
        header_background="#e0e0e0",
        alternate_rows=True,
        alternate_color="#f9f9f9",
    )

    # 页面配置
    template.page_config = PageConfig(
        page_size="A4",
        orientation="portrait",
        margin_top=2.54,
        margin_bottom=2.54,
        margin_left=3.18,
        margin_right=3.18,
    )

    # 页眉页脚
    template.header_footer = HeaderFooterConfig(
        show_footer=True,
        footer_text="第 {page} 页 / 共 {total} 页",
    )

    return template


# ============================================================================
# 内置模板列表
# ============================================================================

def get_builtin_templates() -> List[TemplateInfo]:
    """获取内置模板列表"""
    return [
        TemplateInfo(
            template_id="default",
            template_name="默认模板",
            template_description="适用于大多数场景的默认样式",
            category=TemplateCategory.CUSTOM,
            is_builtin=True,
            preview_text="标准学术/商务文档格式",
        ),
        TemplateInfo(
            template_id="academic",
            template_name="学术论文模板",
            template_description="符合学术规范的论文格式，包含摘要、关键词、参考文献样式",
            category=TemplateCategory.ACADEMIC,
            is_builtin=True,
            preview_text="适合期刊论文、毕业论文",
        ),
        TemplateInfo(
            template_id="technical",
            template_name="技术文档模板",
            template_description="适合API文档、技术规范的格式，包含代码高亮和目录",
            category=TemplateCategory.TECHNICAL,
            is_builtin=True,
            preview_text="适合技术文档、API文档、README",
        ),
        TemplateInfo(
            template_id="business",
            template_name="商务报告模板",
            template_description="专业的商务报告格式，适合项目汇报、工作总结",
            category=TemplateCategory.BUSINESS,
            is_builtin=True,
            preview_text="适合商业报告、项目提案",
        ),
        TemplateInfo(
            template_id="memo",
            template_name="简洁备忘录模板",
            template_description="简洁的备忘录格式，无多余装饰",
            category=TemplateCategory.MEMO,
            is_builtin=True,
            preview_text="适合内部通知、会议纪要",
        ),
    ]


# ============================================================================
# 步骤定义
# ============================================================================

def get_default_steps() -> List[Dict[str, Any]]:
    """获取默认转换步骤定义"""
    return [
        {
            'step_id': 'parse',
            'step_name': '解析Markdown',
            'description': '读取并解析Markdown文件',
            'weight': 0.1,  # 在整体进度中的权重
        },
        {
            'step_id': 'extract',
            'step_name': '提取内容',
            'description': '提取文本、图片、表格、代码等内容',
            'weight': 0.2,
        },
        {
            'step_id': 'convert',
            'step_name': '格式转换',
            'description': '将Markdown AST转换为目标格式',
            'weight': 0.4,
        },
        {
            'step_id': 'style',
            'step_name': '应用样式',
            'description': '应用样式模板和格式设置',
            'weight': 0.15,
        },
        {
            'step_id': 'generate',
            'step_name': '生成文档',
            'description': '生成最终文档文件',
            'weight': 0.1,
        },
        {
            'step_id': 'verify',
            'step_name': '验证输出',
            'description': '验证文档完整性',
            'weight': 0.05,
        },
    ]


def create_progress_info(task_id: str) -> ProgressInfo:
    """创建进度信息对象"""
    steps_def = get_default_steps()
    progress = ProgressInfo(
        task_id=task_id,
        total_steps=len(steps_def),
        start_time=datetime.now(),
    )

    for i, step_def in enumerate(steps_def):
        step = StepInfo(
            step_id=step_def['step_id'],
            step_name=step_def['step_name'],
            step_order=i + 1,
        )
        progress.add_step(step)

    return progress
