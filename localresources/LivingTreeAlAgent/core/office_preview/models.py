"""
office_preview/models.py - 预览系统数据模型

借鉴 AionUi Preview Panel 设计，支持多格式文件的预览与编辑
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import os


class PreviewFileType(Enum):
    """支持预览的文件类型"""
    # 文档格式
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    WORD = "word"       # .docx, .doc
    EXCEL = "excel"     # .xlsx, .xls, .csv
    POWERPOINT = "powerpoint"  # .pptx, .ppt

    # 代码格式
    CODE = "code"

    # 图片格式
    IMAGE = "image"

    # 文本格式
    TEXT = "text"

    # 未知
    UNKNOWN = "unknown"


class EditorMode(Enum):
    """编辑器模式"""
    PREVIEW_ONLY = "preview_only"       # 仅预览
    EDIT_PREVIEW = "edit_preview"       # 编辑+预览（分屏）
    EDIT_ONLY = "edit_only"             # 仅编辑
    WYSIWYG = "wysiwyg"                # 所见即所得


class TabState(Enum):
    """标签页状态"""
    CLEAN = "clean"         # 干净（未修改）
    MODIFIED = "modified"    # 已修改
    SYNCING = "syncing"      # 同步中
    ERROR = "error"          # 错误


# ============ 文件类型检测 ============

MARKDOWN_EXTENSIONS = {'.md', '.markdown', '.mdown', '.mkdn', '.mkd', '.mdwn', '.mdtxt', '.mdtext'}
HTML_EXTENSIONS = {'.html', '.htm', '.xhtml', '.vue', '.jsx', '.tsx'}
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.c', '.cpp', '.h',
    '.hpp', '.cs', '.rb', '.php', '.swift', '.kt', '.scala', '.r', '.lua', '.sh',
    '.bash', '.zsh', '.ps1', '.bat', '.sql', '.json', '.xml', '.yaml', '.yml',
    '.toml', '.ini', '.cfg', '.conf', '.properties', '.env', '.dockerfile',
    '.css', '.scss', '.sass', '.less', '.vue', '.jsx', '.tsx', '.html',
    '.gradle', '.maven', '.cmake', '.make', '.ninja', '.dockerfile',
    '.gitignore', '.gitattributes', '.editorconfig', '.prettierrc',
    '.pylintrc', '.eslintrc', '.babelrc', '.webpack', '.lock', '.txt'
}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.ico', '.tiff', '.avif', '.heic'}
WORD_EXTENSIONS = {'.docx', '.doc', '.odt'}
EXCEL_EXTENSIONS = {'.xlsx', '.xls', '.xlsm', '.csv', '.ods'}
POWERPOINT_EXTENSIONS = {'.pptx', '.ppt', '.odp'}
PDF_EXTENSIONS = {'.pdf'}


def get_file_type(file_path: str) -> PreviewFileType:
    """根据文件扩展名判断文件类型"""
    ext = os.path.splitext(file_path)[1].lower()

    if ext in MARKDOWN_EXTENSIONS:
        return PreviewFileType.MARKDOWN
    elif ext in HTML_EXTENSIONS:
        return PreviewFileType.HTML
    elif ext in CODE_EXTENSIONS:
        return PreviewFileType.CODE
    elif ext in IMAGE_EXTENSIONS:
        return PreviewFileType.IMAGE
    elif ext in WORD_EXTENSIONS:
        return PreviewFileType.WORD
    elif ext in EXCEL_EXTENSIONS:
        return PreviewFileType.EXCEL
    elif ext in POWERPOINT_EXTENSIONS:
        return PreviewFileType.POWERPOINT
    elif ext in PDF_EXTENSIONS:
        return PreviewFileType.PDF
    elif ext in {'.txt', '.log', '.ini', '.cfg', '.conf'}:
        return PreviewFileType.TEXT
    else:
        return PreviewFileType.UNKNOWN


def is_previewable(file_path: str) -> bool:
    """判断文件是否可预览"""
    file_type = get_file_type(file_path)
    return file_type != PreviewFileType.UNKNOWN


# ============ 数据模型 ============

@dataclass
class FileInfo:
    """文件信息"""
    path: str
    name: str
    size: int
    modified_time: float
    file_type: PreviewFileType
    encoding: str = 'utf-8'
    line_count: int = 0
    language: str = ''  # 代码语言

    @classmethod
    def from_path(cls, file_path: str) -> 'FileInfo':
        """从路径创建文件信息"""
        stat = os.stat(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        name = os.path.basename(file_path)

        # 推断语言
        language_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.jsx': 'javascript', '.tsx': 'typescript', '.java': 'java',
            '.go': 'go', '.rs': 'rust', '.c': 'c', '.cpp': 'cpp',
            '.cs': 'csharp', '.rb': 'ruby', '.php': 'php', '.swift': 'swift',
            '.kt': 'kotlin', '.scala': 'scala', '.lua': 'lua', '.sh': 'bash',
            '.sql': 'sql', '.json': 'json', '.xml': 'xml', '.html': 'html',
            '.css': 'css', '.md': 'markdown', '.yaml': 'yaml', '.yml': 'yaml',
            '.dockerfile': 'dockerfile', '.txt': 'plaintext'
        }
        language = language_map.get(ext, 'plaintext')

        # 尝试读取行数
        line_count = 0
        encoding = 'utf-8'
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
        except UnicodeDecodeError:
            try:
                encoding = 'gbk'
                with open(file_path, 'r', encoding='gbk') as f:
                    line_count = sum(1 for _ in f)
            except Exception:
                pass

        return cls(
            path=file_path,
            name=name,
            size=stat.st_size,
            modified_time=stat.st_mtime,
            file_type=get_file_type(file_path),
            encoding=encoding,
            line_count=line_count,
            language=language
        )


@dataclass
class PreviewTab:
    """预览标签页"""
    tab_id: str                          # 唯一标识
    file_path: str                        # 文件路径
    file_info: FileInfo                   # 文件信息
    content: str = ''                     # 当前内容
    original_content: str = ''             # 原始内容（用于比较）
    editor_mode: EditorMode = EditorMode.PREVIEW_ONLY
    state: TabState = TabState.CLEAN
    cursor_position: int = 0              # 光标位置
    scroll_position: float = 0.0          # 滚动位置 0.0-1.0
    zoom_level: float = 1.0               # 缩放级别
    is_favorite: bool = False             # 是否收藏
    version_count: int = 0                # 版本数量
    error_message: str = ''               # 错误信息

    @property
    def is_modified(self) -> bool:
        return self.content != self.original_content

    @property
    def display_name(self) -> str:
        prefix = '●' if self.is_modified else ''
        return f"{prefix}{self.file_info.name}"

    @property
    def short_path(self) -> str:
        """缩短的路径显示"""
        if len(self.file_path) > 50:
            parts = self.file_path.split(os.sep)
            if len(parts) > 3:
                return f"{parts[0]}{os.sep}...{os.sep}{parts[-2]}{os.sep}{parts[-1]}"
        return self.file_path


@dataclass
class PreviewConfig:
    """预览配置"""
    # 显示配置
    show_line_numbers: bool = True
    show_minimap: bool = True              # 代码小地图
    word_wrap: bool = False
    font_size: int = 14
    tab_size: int = 4
    theme: str = 'vs-dark'

    # Markdown 配置
    markdown_math: bool = True             # 数学公式支持
    markdown_uml: bool = True               # UML图表支持
    markdown_emoji: bool = True             #  emoji支持
    markdown_html: bool = True              # HTML标签支持

    # 预览配置
    auto_refresh: bool = True              # 自动刷新
    refresh_delay: float = 0.5             # 刷新延迟（秒）
    max_file_size: int = 10 * 1024 * 1024  # 最大预览文件 10MB

    # PDF 配置
    pdf_page: int = 1                      # 当前页
    pdf_zoom: float = 1.0                  # PDF缩放

    # 图片配置
    image_zoom: float = 1.0                # 图片缩放
    image_fit_window: bool = True           # 自动适应窗口


@dataclass
class RenderResult:
    """渲染结果"""
    success: bool
    html: str = ''
    error: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, html: str, metadata: Dict[str, Any] = None) -> 'RenderResult':
        return cls(success=True, html=html, metadata=metadata or {})

    @classmethod
    def error(cls, error: str) -> 'RenderResult':
        return cls(success=False, error=error)


@dataclass
class PreviewHistory:
    """预览历史"""
    id: str
    file_path: str
    preview_count: int = 1
    last_preview_time: float = 0.0
    favorite: bool = False
    tags: List[str] = field(default_factory=list)

    @classmethod
    def new(cls, file_path: str) -> 'PreviewHistory':
        import time
        import uuid
        return cls(
            id=str(uuid.uuid4()),
            file_path=file_path,
            preview_count=1,
            last_preview_time=time.time()
        )


# ============ Office 文档结构 ============

@dataclass
class WordPage:
    """Word 文档页面"""
    page_number: int
    heading: str            # 标题
    content_preview: str    # 内容预览（前100字）
    word_count: int         # 字数
    has_images: bool = False
    has_tables: bool = False


@dataclass
class ExcelSheet:
    """Excel 工作表"""
    name: str
    row_count: int
    column_count: int
    used_range: str         # 如 "A1:J100"
    has_formulas: bool = False
    preview_data: List[List[str]] = None  # 预览数据

    def __post_init__(self):
        if self.preview_data is None:
            self.preview_data = []


@dataclass
class PowerPointSlide:
    """PowerPoint 幻灯片"""
    slide_number: int
    title: str
    content_preview: str     # 文本内容预览
    image_count: int = 0
    layout: str = ''         # 布局名称


# ============ 辅助函数 ============

def format_file_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def format_timestamp(ts: float) -> str:
    """格式化时间戳"""
    dt = datetime.fromtimestamp(ts)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


# 支持高亮的语言列表
SUPPORTED_CODE_LANGUAGES = [
    'python', 'javascript', 'typescript', 'java', 'go', 'rust', 'c', 'cpp',
    'csharp', 'ruby', 'php', 'swift', 'kotlin', 'scala', 'lua', 'bash',
    'sql', 'json', 'xml', 'html', 'css', 'markdown', 'yaml', 'dockerfile',
    'plaintext', 'ini', 'toml', 'makefile', 'cmake', 'gradle'
]
