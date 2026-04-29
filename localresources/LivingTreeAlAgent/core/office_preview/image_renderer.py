"""
office_preview/image_renderer.py - 图片预览渲染器

支持 PNG/JPG/GIF/SVG/WebP/BMP/ICO/TIFF/AVIF 等格式
"""

import os
import base64
from typing import Optional, Tuple, Dict, Any
from .models import RenderResult


class ImageRenderer:
    """图片渲染器"""

    # 支持的格式
    SUPPORTED_FORMATS = {
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
        '.bmp', '.ico', '.tiff', '.tif', '.avif', '.heic'
    }

    # MIME 类型
    MIME_TYPES = {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.svg': 'image/svg+xml', '.webp': 'image/webp',
        '.bmp': 'image/bmp', '.ico': 'image/x-icon', '.tiff': 'image/tiff',
        '.tif': 'image/tiff', '.avif': 'image/avif', '.heic': 'image/heic'
    }

    def __init__(self):
        self._pillow_available = self._check_pillow()
        self._avif_available = self._check_avif()

    def _check_pillow(self) -> bool:
        try:
            from PIL import Image
            return True
        except ImportError:
            return False

    def _check_avif(self) -> bool:
        try:
            import pillow_avif
            return True
        except ImportError:
            return False

    def render(self, file_path: str, zoom: float = 1.0) -> RenderResult:
        """渲染图片"""
        if not os.path.exists(file_path):
            return RenderResult.error(f"文件不存在: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext not in self.SUPPORTED_FORMATS:
            return RenderResult.error(f"不支持的图片格式: {ext}")

        try:
            return self._render_image(file_path, zoom, ext)
        except Exception as e:
            return RenderResult.error(f"图片渲染失败: {str(e)}")

    def _render_image(self, file_path: str, zoom: float, ext: str) -> RenderResult:
        """渲染图片"""
        # 获取图片信息
        width, height = self._get_image_size(file_path)
        file_size = os.path.getsize(file_path)
        mime_type = self.MIME_TYPES.get(ext, 'image/png')

        # SVG 直接使用
        if ext == '.svg':
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                svg_content = f.read()
            return RenderResult.ok(
                self._build_svg_html(svg_content, width, height),
                {'width': width, 'height': height, 'format': 'svg',
                 'file_size': file_size, 'zoom': zoom}
            )

        # 其他格式转换为 base64
        with open(file_path, 'rb') as f:
            img_data = f.read()

        img_base64 = base64.b64encode(img_data).decode('utf-8')

        html = self._build_image_html(
            img_src=f'data:{mime_type};base64,{img_base64}',
            width=int(width * zoom),
            height=int(height * zoom),
            original_width=width,
            original_height=height,
            file_size=file_size,
            format=ext[1:].upper(),
            file_name=os.path.basename(file_path),
            zoom=zoom
        )

        return RenderResult.ok(html, {
            'width': width, 'height': height,
            'file_size': file_size, 'format': ext[1:].upper(),
            'zoom': zoom
        })

    def _get_image_size(self, file_path: str) -> Tuple[int, int]:
        """获取图片尺寸"""
        try:
            if self._pillow_available:
                from PIL import Image
                with Image.open(file_path) as img:
                    return img.size  # (width, height)
        except Exception:
            pass
        return (800, 600)  # 默认尺寸

    def _build_image_html(self, img_src: str, width: int, height: int,
                           original_width: int, original_height: int,
                           file_size: float, format: str, file_name: str,
                           zoom: float) -> str:
        """构建图片 HTML"""
        size_str = self._format_size(file_size)

        return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
:root {{ --bg: #1a1a1a; --toolbar-bg: #252525; --accent: #2563eb;
         --text: #d4d4d4; --border: #333; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', -apple-system, sans-serif; background: var(--bg);
        color: var(--text); height: 100vh; display: flex; flex-direction: column; }}
.img-toolbar {{ background: var(--toolbar-bg); border-bottom: 1px solid var(--border);
                padding: 10px 16px; display: flex; align-items: center; gap: 12px;
                justify-content: space-between; }}
.toolbar-left {{ display: flex; align-items: center; gap: 12px; }}
.toolbar-right {{ display: flex; align-items: center; gap: 8px; }}
.img-info {{ font-size: 13px; color: #888; }}
.img-info b {{ color: var(--text); }}
button {{ background: #333; color: var(--text); border: 1px solid var(--border);
          padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }}
button:hover {{ background: #444; }}
.zoom-controls {{ display: flex; align-items: center; gap: 6px; }}
.zoom-label {{ font-size: 12px; color: #888; min-width: 45px; text-align: center; }}
.img-viewer {{ flex: 1; overflow: auto; display: flex; align-items: center;
               justify-content: center; padding: 24px; background: #111; }}
.img-container {{ position: relative; }}
.img-container img {{ display: block; max-width: 100%; height: auto;
                      border: 1px solid var(--border); cursor: zoom-in;
                      transition: transform 0.2s; }}
.img-container img:hover {{ transform: scale(1.02); }}
.img-actions {{ position: absolute; top: 8px; right: 8px; display: flex; gap: 6px;
                opacity: 0; transition: opacity 0.2s; }}
.img-container:hover .img-actions {{ opacity: 1; }}
.img-actions button {{ padding: 4px 8px; font-size: 11px; background: rgba(0,0,0,0.7); }}
</style>
</head><body>
<div class="img-toolbar">
    <div class="toolbar-left">
        <span class="img-info">
            <b>{file_name}</b> · {format} · {original_width}×{original_height}px · {size_str}
        </span>
    </div>
    <div class="toolbar-right">
        <div class="zoom-controls">
            <button onclick="changeZoom(-0.25)">➖</button>
            <span class="zoom-label" id="zoom-label">{int(zoom * 100)}%</span>
            <button onclick="changeZoom(0.25)">➕</button>
            <button onclick="zoomFit()">🔲 适应</button>
            <button onclick="zoomActual()">100%</button>
            <button onclick="zoomFull()">⛶ 全屏</button>
        </div>
    </div>
</div>
<div class="img-viewer" id="img-viewer">
    <div class="img-container">
        <img src="{img_src}" alt="{file_name}" id="main-img"
             style="width:{width}px;height:{height}px;" />
        <div class="img-actions">
            <button onclick="copyPath()">📋 复制路径</button>
            <button onclick="openFolder()">📁 打开文件夹</button>
        </div>
    </div>
</div>
<script>
let currentZoom = {zoom};
const originalW = {original_width};
const originalH = {original_height};

function changeZoom(delta) {{
    const newZoom = Math.max(0.1, Math.min(5, currentZoom + delta));
    if (newZoom !== currentZoom) {{
        currentZoom = newZoom;
        applyZoom();
    }}
}}

function applyZoom() {{
    const img = document.getElementById('main-img');
    img.style.width = (originalW * currentZoom) + 'px';
    img.style.height = (originalH * currentZoom) + 'px';
    document.getElementById('zoom-label').textContent = Math.round(currentZoom * 100) + '%';
    if (window.onZoomChange) window.onZoomChange(currentZoom);
}}

function zoomFit() {{
    const viewer = document.getElementById('img-viewer');
    const vw = viewer.clientWidth - 48;
    const vh = viewer.clientHeight - 48;
    currentZoom = Math.min(vw / originalW, vh / originalH, 1);
    applyZoom();
}}

function zoomActual() {{
    currentZoom = 1;
    applyZoom();
}}

function zoomFull() {{
    document.getElementById('main-img').requestFullscreen && document.getElementById('main-img').requestFullscreen();
}};

function copyPath() {{
    navigator.clipboard.writeText(decodeURIComponent("{img_src}".split(',')[1] ? location.href : "{file_path}"));
}};

function openFolder() {{
    window.openFolder && window.openFolder();
}};

// 鼠标滚轮缩放
document.getElementById('main-img').addEventListener('wheel', e => {{
    e.preventDefault();
    changeZoom(e.deltaY > 0 ? -0.1 : 0.1);
}});

// 双击适应窗口
document.getElementById('main-img').addEventListener('dblclick', zoomFit);

// 键盘快捷键
document.addEventListener('keydown', e => {{
    if (e.key === '+' || e.key === '=') changeZoom(0.25);
    if (e.key === '-') changeZoom(-0.25);
    if (e.key === '0') zoomFit();
    if (e.key === '1') zoomActual();
    if (e.key === 'f' || e.key === 'F11') zoomFull();
}});
</script>
</body></html>'''

    def _build_svg_html(self, svg_content: str, width: int, height: int) -> str:
        """构建 SVG HTML"""
        return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a1a; height: 100vh;
        display: flex; align-items: center; justify-content: center; padding: 24px; }}
.svg-container {{ width: 100%; height: 100%; display: flex; align-items: center;
                  justify-content: center; }}
.svg-container svg {{ max-width: 100%; max-height: 100%; width: {width}px; height: {height}px; }}
</style>
</head><body>
<div class="svg-container">
{svg_content}
</div>
</body></html>'''

    def _format_size(self, size: float) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"
