"""
office_preview/pdf_renderer.py - PDF 预览渲染器

支持 PDF 文档预览、页面导航、缩放控制、文本选择
"""

import os
from typing import Optional, Tuple
from .models import RenderResult


class PDFRenderer:
    """PDF 渲染器 - 多种后端支持"""

    def __init__(self):
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """检测可用的 PDF 渲染后端"""
        try:
            import pypdf
            return 'pypdf'
        except ImportError:
            pass

        try:
            import fitz  # PyMuPDF
            return 'pymupdf'
        except ImportError:
            pass

        try:
            import pdfplumber
            return 'pdfplumber'
        except ImportError:
            pass

        return 'none'

    def render(self, file_path: str, page: int = 1, zoom: float = 1.0) -> RenderResult:
        """渲染 PDF 指定页面"""
        if not os.path.exists(file_path):
            return RenderResult.error(f"文件不存在: {file_path}")

        if self._backend == 'none':
            return self._render_info_only(file_path)

        try:
            if self._backend == 'pymupdf':
                return self._render_pymupdf(file_path, page, zoom)
            elif self._backend == 'pypdf':
                return self._render_pypdf(file_path, page, zoom)
            elif self._backend == 'pdfplumber':
                return self._render_pdfplumber(file_path, page, zoom)
        except Exception as e:
            pass

        return self._render_info_only(file_path)

    def _render_pymupdf(self, file_path: str, page: int, zoom: float) -> RenderResult:
        """使用 PyMuPDF 渲染"""
        import fitz

        doc = fitz.open(file_path)
        total_pages = len(doc)

        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        # 渲染页面为图像
        pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_data = pix.tobytes('png')

        # 提取文本
        text = doc[page - 1].get_text('text')[:2000]

        # Base64 编码图像
        import base64
        img_base64 = base64.b64encode(img_data).decode('utf-8')

        html = self._build_pdf_html(
            img_src=f'data:image/png;base64,{img_base64}',
            page=page,
            total_pages=total_pages,
            zoom=zoom,
            text=text,
            width=pix.width,
            height=pix.height
        )

        doc.close()
        return RenderResult.ok(html, {
            'page': page, 'total_pages': total_pages,
            'zoom': zoom, 'backend': 'PyMuPDF'
        })

    def _render_pypdf(self, file_path: str, page: int, zoom: float) -> RenderResult:
        """使用 pypdf 渲染（需要转换为图像）"""
        import pypdf

        with open(file_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            total_pages = len(reader.pages)

        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        # pypdf 不支持直接渲染为图像，使用信息展示
        return self._render_info_only(file_path, extra_info={
            'page': page,
            'total_pages': total_pages,
            'backend': 'pypdf (仅文本)'
        })

    def _render_pdfplumber(self, file_path: str, page: int, zoom: float) -> RenderResult:
        """使用 pdfplumber 渲染"""
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        # pdfplumber 也不直接支持图像渲染
        return self._render_info_only(file_path, extra_info={
            'page': page,
            'total_pages': total_pages,
            'backend': 'pdfplumber (仅文本)'
        })

    def _build_pdf_html(self, img_src: str, page: int, total_pages: int,
                         zoom: float, text: str, width: int, height: int) -> str:
        """构建 PDF HTML"""
        return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
:root {{ --bg: #1a1a1a; --toolbar-bg: #252525; --accent: #2563eb;
         --text: #d4d4d4; --border: #333; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', -apple-system, sans-serif; background: var(--bg);
        color: var(--text); height: 100vh; display: flex; flex-direction: column; }}
.pdf-toolbar {{ background: var(--toolbar-bg); border-bottom: 1px solid var(--border);
                padding: 10px 16px; display: flex; align-items: center; gap: 12px; }}
.pdf-toolbar button {{ background: #333; color: var(--text); border: 1px solid var(--border);
                       padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }}
.pdf-toolbar button:hover {{ background: #444; }}
.pdf-toolbar button:disabled {{ opacity: 0.4; cursor: not-allowed; }}
.page-info {{ font-size: 13px; color: #888; min-width: 120px; text-align: center; }}
.zoom-controls {{ display: flex; align-items: center; gap: 8px; }}
.zoom-label {{ font-size: 13px; color: #888; }}
.page-input {{ background: #333; color: var(--text); border: 1px solid var(--border);
              width: 50px; text-align: center; padding: 6px; border-radius: 4px; font-size: 13px; }}
.pdf-viewer {{ flex: 1; overflow: auto; display: flex; justify-content: center;
               padding: 24px; background: var(--bg); }}
.page-container {{ position: relative; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
.page-container img {{ display: block; max-width: 100%; height: auto; }}
.pdf-text {{ background: #2a2a2a; border-top: 1px solid var(--border); padding: 12px 16px;
             font-size: 13px; color: #888; max-height: 150px; overflow-y: auto;
             white-space: pre-wrap; line-height: 1.6; }}
</style>
</head><body>
<div class="pdf-toolbar">
    <button id="prev-btn" onclick="changePage(-1)">◀ 上一页</button>
    <span class="page-info">第 <input type="number" class="page-input" id="page-input"
           value="{page}" min="1" max="{total_pages}" onchange="gotoPage(this.value)">
           / {total_pages} 页</span>
    <button id="next-btn" onclick="changePage(1)">下一页 ▶</button>
    <div class="zoom-controls">
        <button onclick="changeZoom(-0.25)">➖</button>
        <span class="zoom-label" id="zoom-label">{int(zoom * 100)}%</span>
        <button onclick="changeZoom(0.25)">➕</button>
        <button onclick="resetZoom()">🔄 适应窗口</button>
    </div>
</div>
<div class="pdf-viewer">
    <div class="page-container" id="page-container">
        <img src="{img_src}" alt="PDF Page {page}" id="pdf-image"
             style="width:{int(width)}px;height:{int(height)}px;" />
    </div>
</div>
<div class="pdf-text" id="pdf-text">{text or "（无可用文本）"}</div>
<script>
let currentPage = {page};
let totalPages = {total_pages};
let currentZoom = {zoom};

function changePage(delta) {{
    const newPage = currentPage + delta;
    if (newPage >= 1 && newPage <= totalPages) {{
        window.pdfNavigate && window.pdfNavigate(newPage, currentZoom);
    }}
}}

function gotoPage(p) {{
    const page = parseInt(p);
    if (page >= 1 && page <= totalPages) {{
        window.pdfNavigate && window.pdfNavigate(page, currentZoom);
    }}
}}

function changeZoom(delta) {{
    const newZoom = Math.max(0.25, Math.min(4, currentZoom + delta));
    if (newZoom !== currentZoom) {{
        currentZoom = newZoom;
        window.pdfNavigate && window.pdfNavigate(currentPage, currentZoom);
    }}
}}

function resetZoom() {{
    currentZoom = 1.0;
    document.getElementById('zoom-label').textContent = '100%';
    window.pdfNavigate && window.pdfNavigate(currentPage, 1.0);
}}

// 键盘快捷键
document.addEventListener('keydown', e => {{
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') changePage(-1);
    if (e.key === 'ArrowRight' || e.key === 'PageDown') changePage(1);
    if (e.key === '+' || e.key === '=') changeZoom(0.25);
    if (e.key === '-') changeZoom(-0.25);
}});
</script>
</body></html>'''

    def _render_info_only(self, file_path: str, extra_info: dict = None) -> RenderResult:
        """仅展示 PDF 信息（无渲染后端时）"""
        import os
        size = os.path.getsize(file_path)

        info = {
            'file': os.path.basename(file_path),
            'size': f"{size / 1024 / 1024:.2f} MB",
            'path': file_path,
        }
        if extra_info:
            info.update(extra_info)

        info_html = '<br/>'.join(f'<b>{k}:</b> {v}' for k, v in info.items())

        return RenderResult.ok(
            f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: #d4d4d4;
       display: flex; align-items: center; justify-content: center; height: 100vh; text-align: center; }}
.info-panel {{ background: #252525; border-radius: 12px; padding: 40px; max-width: 500px;
              border: 1px solid #333; }}
.info-panel h2 {{ color: #fff; margin-bottom: 20px; font-size: 1.4em; }}
.info-panel p {{ font-size: 14px; color: #888; margin: 8px 0; text-align: left; }}
.info-panel b {{ color: #569cd6; }}
</style>
</head><body>
<div class="info-panel">
    <h2>📄 PDF 预览</h2>
    {info_html}
    <p style="margin-top:20px;color:#666;">提示: 安装以下库可实现完整预览:</p>
    <p style="color:#569cd6;">pip install PyMuPDF</p>
</div>
</body></html>''',
            {'backend': 'none', 'info': info}
        )

    def get_page_count(self, file_path: str) -> int:
        """获取 PDF 页数"""
        if not os.path.exists(file_path):
            return 0

        try:
            import fitz
            return len(fitz.open(file_path))
        except Exception:
            pass

        try:
            import pypdf
            with open(file_path, 'rb') as f:
                return len(pypdf.PdfReader(f).pages)
        except Exception:
            return 0
