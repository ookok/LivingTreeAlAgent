"""DocumentPreviewWidget — renders PDF/Word/text document preview in terminal.

Extracts text content from documents and displays with pagination.
Supports PDF, DOCX, and plain text files.
"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static
from textual.binding import Binding
from pathlib import Path


class DocumentPreviewWidget(Vertical):
    can_focus = True
    BINDINGS = [
        Binding("down", "next_page", "下一页"),
        Binding("up", "prev_page", "上一页"),
    ]

    def __init__(self, name: str = "DocumentPreview", classes: str = ""):
        super().__init__(name=name)
        self._classes = classes
        self._pages: list[str] = []
        self._current_page = 0
        self._lines_per_page = 20

    def compose(self):
        yield Static("📄 文档预览", classes="preview-title")
        yield Static("", id="doc-content", classes="doc-content")
        yield Static("", id="doc-pager", classes="doc-pager")

    def load_file(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            self.query_one("#doc-content", Static).update(f"[red]文件不存在: {file_path}[/red]")
            return

        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                text = self._extract_pdf(path)
            elif ext in (".docx", ".doc"):
                text = self._extract_docx(path)
            elif ext in (".txt", ".md", ".py", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env", ".log", ".csv"):
                text = path.read_text(encoding="utf-8", errors="replace")
            else:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    text = f"[不支持的文件类型: {ext}]"
        except Exception as e:
            self.query_one("#doc-content", Static).update(f"[red]读取失败: {e}[/red]")
            return

        self._split_pages(text)
        self._show_page()

    def _extract_pdf(self, path: Path) -> str:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            parts = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    parts.append(f"--- 第 {i+1} 页 ---\n{text}")
            return "\n\n".join(parts) if parts else "[无法提取文本内容]"
        except ImportError:
            return f"[需要 PyPDF2 库来读取 PDF: {path.name}]"
        except Exception as e:
            return f"[PDF 读取错误: {e}]"

    def _extract_docx(self, path: Path) -> str:
        try:
            from docx import Document
            doc = Document(str(path))
            parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text)
            return "\n".join(parts) if parts else "[无法提取文本内容]"
        except ImportError:
            return f"[需要 python-docx 库来读取: {path.name}]"
        except Exception as e:
            return f"[DOCX 读取错误: {e}]"

    def load_text(self, text: str, title: str = "") -> None:
        if title:
            self.query_one(".preview-title", Static).update(f"📄 {title}")
        self._split_pages(text)
        self._show_page()

    def _split_pages(self, text: str) -> None:
        lines = text.split("\n")
        self._pages = []
        for i in range(0, len(lines), self._lines_per_page):
            self._pages.append("\n".join(lines[i:i + self._lines_per_page]))
        self._current_page = 0

    def _show_page(self) -> None:
        if not self._pages:
            self.query_one("#doc-content", Static).update("[dim]无内容[/dim]")
            self.query_one("#doc-pager", Static).update("")
            return

        page = self._pages[self._current_page]
        self.query_one("#doc-content", Static).update(page)
        self.query_one("#doc-pager", Static).update(
            f"[dim]第 {self._current_page + 1}/{len(self._pages)} 页[/dim]"
        )

    def action_next_page(self) -> None:
        if self._current_page < len(self._pages) - 1:
            self._current_page += 1
            self._show_page()

    def action_prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._show_page()

    def clear(self) -> None:
        self._pages = []
        self._current_page = 0
        self.query_one("#doc-content", Static).update("")
        self.query_one("#doc-pager", Static).update("")
