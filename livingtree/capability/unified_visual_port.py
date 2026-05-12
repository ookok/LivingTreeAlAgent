"""UnifiedVisualPort — 统一视觉输出管道 (inspired by Vision Banana, arXiv:2604.20329).

Vision Banana 核心启示: "所有视觉任务输出参数化为 RGB 图像 = 图像生成是视觉的统一接口"
LivingTree 映射:     所有视觉输出 → 一个 UnifiedVisualPort
                     ├── text 通道 (Terminal Unicode / LLM text context)
                     └── image 通道 (RGB PNG / LLM vision input)

6 个内置适配器覆盖 LivingTree 全部视觉输出场景:
  DocumentAdapter  — PDF/DOCX/TXT → 文本提取 + 排版 PNG
  MapAdapter       — 坐标/图片 → ASCII 地图 + Matplotlib 地图
  PlotAdapter      — 数据字典/列表 → Unicode 图表 + Matplotlib PNG
  DiagramAdapter   — Mermaid/Graphviz → 终端渲染 + 图形 PNG
  ImageAdapter     — 已有图片 → ASCII 转换 + 透传
  TableAdapter     — CSV/DataFrame → 格式化表格 + PNG 表格

用法:
    from livingtree.capability.unified_visual_port import get_visual_port
    port = get_visual_port()
    output = port.render(data)
    print(output.text)        # Terminal/LLM text channel
    output.image_bytes        # RGB PNG bytes for file save or vision input
"""

from __future__ import annotations

import base64
import io
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ═══ VisualOutput — 双通道输出容器 ═══

@dataclass
class VisualOutput:
    """统一视觉输出 — text + image 双通道。

    text 通道:  终端 Unicode 渲染 / LLM 文本上下文
    image 通道: RGB PNG bytes / LLM 多模态 vision 输入
    """
    text: str = ""
    image_bytes: bytes = b""
    image_format: str = "png"
    width: int = 0
    height: int = 0
    source_type: str = "unknown"
    metadata: dict = field(default_factory=dict)

    def has_text(self) -> bool:
        return bool(self.text)

    def has_image(self) -> bool:
        return len(self.image_bytes) > 0

    def image_base64(self) -> str:
        """返回 base64 编码的图像数据（data URI 格式）。"""
        if not self.image_bytes:
            return ""
        mime = f"image/{self.image_format}"
        b64 = base64.b64encode(self.image_bytes).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def image_data_uri(self) -> str:
        """完整 data URI，可直接用于 <img src='...'> 或 LLM vision API。"""
        return self.image_base64()

    def save_image(self, path: str) -> Path:
        """持久化图像到文件。"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.image_bytes)
        return p

    def to_dict(self) -> dict:
        return {
            "text": self.text[:2000],
            "has_image": self.has_image(),
            "image_format": self.image_format,
            "width": self.width,
            "height": self.height,
            "source_type": self.source_type,
            "metadata": self.metadata,
        }


# ═══ VisualAdapter ABC ═══

class VisualAdapter(ABC):
    """视觉适配器基类 — 一种输出格式 = 一个适配器。

    Vision Banana 风格: 仅通过 type_name 切换，无任务特定模块。
    """

    type_name: str = ""

    @abstractmethod
    def can_handle(self, data: Any) -> bool:
        """判断是否能处理此数据。"""
        ...

    def render_text(self, data: Any) -> str:
        """产出 text 通道输出（Terminal Unicode 或 LLM 文本）。"""
        return ""

    def render_image(self, data: Any) -> Optional[bytes]:
        """产出 image 通道输出（RGB PNG bytes）。"""
        return None

    def render(self, data: Any) -> VisualOutput:
        """双通道渲染。"""
        text = self.render_text(data)
        img = self.render_image(data)
        meta = self._extract_meta(data)
        w, h = 0, 0
        if img:
            w, h = self._image_dims(img)
        return VisualOutput(
            text=text,
            image_bytes=img or b"",
            image_format="png",
            width=w,
            height=h,
            source_type=self.type_name,
            metadata=meta,
        )

    def _extract_meta(self, data: Any) -> dict:
        return {}

    def _image_dims(self, img: bytes) -> tuple[int, int]:
        try:
            from PIL import Image
            with Image.open(io.BytesIO(img)) as im:
                return im.size
        except Exception as e:
            logger.warning(f"UnifiedVisual: {e}")
            return 0, 0


# ═══ 适配器实现 ═══

# ── 1. ImageAdapter ──

class ImageAdapter(VisualAdapter):
    """已有图片适配器 — ASCII 转换 + 透传 RGB。

    输入: image_path (str) 或 {"image_path": str, "ascii_width": 60}
    输出: ASCII art text + 原图 PNG bytes
    """

    type_name = "image"

    def can_handle(self, data: Any) -> bool:
        if isinstance(data, str) and os.path.isfile(data):
            ext = Path(data).suffix.lower()
            return ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}
        if isinstance(data, dict) and "image_path" in data:
            return os.path.isfile(str(data["image_path"]))
        return False

    def render_text(self, data: Any) -> str:
        path = data if isinstance(data, str) else str(data.get("image_path", ""))
        width = (data if isinstance(data, dict) else {}).get("ascii_width", 60)
        try:
            from PIL import Image
            img = Image.open(path).convert("L")
            aspect = img.height / max(img.width, 1)
            h = max(5, int(width * aspect * 0.5))
            img = img.resize((width, h))
            pixels = img.load()
            charset = " .:-=+*#%@"
            lines = [f"🖼 {Path(path).name} ({img.width}x{img.height})"]
            for y in range(h):
                line = "".join(
                    charset[min(int(pixels[x, y] / 256 * len(charset)), len(charset) - 1)]
                    for x in range(width)
                )
                lines.append(line)
            return "\n".join(lines)
        except ImportError:
            return f"[需要 PIL/Pillow] {path}"
        except Exception as e:
            return f"[图片错误] {path}: {e}"

    def render_image(self, data: Any) -> Optional[bytes]:
        path = data if isinstance(data, str) else str(data.get("image_path", ""))
        try:
            return Path(path).read_bytes()
        except Exception as e:
            logger.warning(f"UnifiedVisual: {e}")
            return None

    def _extract_meta(self, data: Any) -> dict:
        path = data if isinstance(data, str) else str(data.get("image_path", ""))
        try:
            from PIL import Image
            with Image.open(path) as im:
                return {"path": path, "format": im.format, "mode": im.mode, "size": im.size}
        except Exception as e:
            logger.warning(f"UnifiedVisual: {e}")
            return {"path": path}


# ── 2. PlotAdapter ──

class PlotAdapter(VisualAdapter):
    """图表适配器 — Unicode 终端图表 + Matplotlib PNG。

    输入格式:
      bar:   {"type": "bar", "data": {"A": 10, "B": 20}, "title": "..."}
      line:  {"type": "line", "data": [1,2,3,...], "title": "..."}
      scatter: {"type": "scatter", "data": [(x1,y1),...], "title": "..."}
    """

    type_name = "plot"

    def can_handle(self, data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        t = data.get("type", "")
        return t in {"bar", "line", "scatter", "pie", "histogram"}

    def render_text(self, data: Any) -> str:
        t = data.get("type", "")
        d = data.get("data", {})
        title = data.get("title", "")
        width = data.get("width", 50)
        height = data.get("height", 15)
        try:
            if t == "bar":
                return self._bar_text(d, title, width)
            elif t == "line":
                return self._line_text(d, title, height, width)
            elif t == "scatter":
                return self._scatter_text(d, title, height, 40)
            elif t == "pie":
                return self._pie_text(d, title, width)
            elif t == "histogram":
                return self._histogram_text(d, title, height, width)
        except Exception as e:
            return f"[图表渲染错误] {e}"
        return f"[未知图表类型: {t}]"

    def _bar_text(self, data: dict, title: str, width: int) -> str:
        if not data:
            return "[dim]无数据[/dim]"
        max_val = max(abs(v) for v in data.values()) or 1
        max_label = max(len(str(k)) for k in data.keys()) or 1
        bar_width = max(4, width - max_label - 5)
        chars = "█▉▊▋▌▍▎▏"
        lines = [f"[bold]{title}[/bold]"] if title else []
        for label, value in data.items():
            bar_len = int(abs(value) / max_val * bar_width * 8)
            full, partial = bar_len // 8, bar_len % 8
            bar = "█" * full + (chars[partial] if partial > 0 else "")
            lines.append(f"{str(label):>{max_label}} │ {bar} {value:.1f}")
        return "\n".join(lines)

    def _line_text(self, data: list, title: str, height: int, width: int) -> str:
        if not data:
            return "[dim]无数据[/dim]"
        min_v, max_v = min(data), max(data)
        if min_v == max_v:
            min_v -= 1; max_v += 1
        rng = max_v - min_v
        step = max(1, len(data) // width)
        sampled = data[::step][:width]
        chars = "▁▂▃▄▅▆▇█"
        lines = [f"[bold]{title}[/bold]"] if title else []
        for row in range(height - 1, -1, -1):
            thresh = min_v + (row / (height - 1)) * rng
            line = ""
            for val in sampled:
                idx = min(7, int((val - min_v) / rng * 7))
                line += chars[idx] if val >= thresh else " "
            lines.append(line)
        lines.append(f"[dim]min:{min_v:.1f} max:{max_v:.1f} n:{len(data)}[/dim]")
        return "\n".join(lines)

    def _scatter_text(self, points: list, title: str, height: int, width: int) -> str:
        if not points:
            return "[dim]无数据[/dim]"
        xs = [p[0] for p in points]; ys = [p[1] for p in points]
        x_min, x_max = min(xs), max(xs); y_min, y_max = min(ys), max(ys)
        x_rng = (x_max - x_min) or 1; y_rng = (y_max - y_min) or 1
        grid = [[" " for _ in range(width)] for _ in range(height)]
        for x, y in points:
            col = int((x - x_min) / x_rng * (width - 1))
            row = int((1 - (y - y_min) / y_rng) * (height - 1))
            if 0 <= col < width and 0 <= row < height:
                grid[row][col] = "●"
        lines = [f"[bold]{title}[/bold]"] if title else []
        lines.extend("".join(r) for r in grid)
        lines.append(f"[dim]x:[{x_min:.1f},{x_max:.1f}] y:[{y_min:.1f},{y_max:.1f}][/dim]")
        return "\n".join(lines)

    def _pie_text(self, data: dict, title: str, width: int) -> str:
        """Simple text-based pie chart using proportions."""
        if not data:
            return "[dim]无数据[/dim]"
        total = sum(data.values()) or 1
        lines = [f"[bold]{title}[/bold]"] if title else []
        for label, value in data.items():
            pct = value / total * 100
            bar_len = int(pct / 100 * 40)
            lines.append(f"  {label:>12} █{'█' * bar_len} {value} ({pct:.1f}%)")
        return "\n".join(lines)

    def _histogram_text(self, data: list, title: str, height: int, width: int) -> str:
        """Histogram from raw values."""
        if not data:
            return "[dim]无数据[/dim]"
        bins = min(20, max(5, len(data) // 10))
        min_v, max_v = min(data), max(data)
        if min_v == max_v:
            min_v -= 0.5; max_v += 0.5
        bin_w = (max_v - min_v) / bins
        counts = [0] * bins
        for v in data:
            idx = min(int((v - min_v) / bin_w), bins - 1)
            counts[idx] += 1
        max_c = max(counts) or 1
        lines = [f"[bold]{title}[/bold]"] if title else []
        for i, c in enumerate(counts):
            bar_len = int(c / max_c * (width - 15))
            lo = min_v + i * bin_w
            label = f"{lo:6.1f}"
            lines.append(f"{label} │ {'█' * bar_len} {c}")
        return "\n".join(lines)

    def render_image(self, data: Any) -> Optional[bytes]:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return None
        t = data.get("type", "")
        d = data.get("data", {})
        title = data.get("title", "")
        try:
            fig, ax = plt.subplots(figsize=(8, 5))
            if t == "bar":
                if isinstance(d, dict):
                    ax.bar(list(d.keys()), list(d.values()), color="#4CAF50")
            elif t == "line":
                ax.plot(d, color="#2196F3", linewidth=1.5)
            elif t == "scatter":
                xs, ys = [p[0] for p in d], [p[1] for p in d]
                ax.scatter(xs, ys, c="#FF5722", s=20)
            elif t == "pie":
                if isinstance(d, dict):
                    ax.pie(list(d.values()), labels=list(d.keys()), autopct="%1.1f%%")
            elif t == "histogram":
                ax.hist(d, bins=min(20, max(5, len(d) // 10)), color="#9C27B0", edgecolor="white")
            if title:
                ax.set_title(title)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            plt.close(fig)
            return buf.getvalue()
        except Exception as e:
            logger.debug(f"PlotAdapter image: {e}")
            return None


# ── 3. TableAdapter ──

class TableAdapter(VisualAdapter):
    """表格适配器 — 格式化文本表格 + Matplotlib PNG 表格。

    输入: {"type": "table", "headers": [...], "rows": [[...],...], "title": "..."}
          或 CSV 文件路径字符串
    """

    type_name = "table"

    def can_handle(self, data: Any) -> bool:
        if isinstance(data, dict) and data.get("type") == "table":
            return True
        if isinstance(data, dict) and "headers" in data and "rows" in data:
            return True
        if isinstance(data, str) and data.lower().endswith(".csv"):
            return True
        return False

    def _parse_csv(self, path: str) -> dict:
        try:
            import csv
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                rows = list(reader)
            return {"headers": headers, "rows": rows[:100], "title": Path(path).name}
        except Exception as e:
            logger.warning(f"UnifiedVisual: {e}")
            return {"headers": [], "rows": [], "title": path}

    def render_text(self, data: Any) -> str:
        if isinstance(data, str):
            data = self._parse_csv(data)
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        title = data.get("title", "")
        max_rows = data.get("max_rows", 50)
        rows = rows[:max_rows]
        if not headers and not rows:
            return "[dim]空表格[/dim]"
        all_rows = [headers] + rows if headers else rows
        col_widths = [0] * max(len(r) for r in all_rows)
        for row in all_rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        lines = [f"[bold]{title}[/bold]"] if title else []
        sep = "─" * (sum(col_widths) + 3 * len(col_widths) + 1)
        lines.append(f"┌{sep}┐")
        if headers:
            hdr = "│ " + " │ ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers)) + " │"
            lines.append(hdr)
            lines.append(f"├{sep}┤")
        for row in rows:
            r = "│ " + " │ ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(row)) + " │"
            lines.append(r)
        lines.append(f"└{sep}┘")
        if len(data.get("rows", [])) > max_rows:
            lines.append(f"[dim]... 共 {len(data['rows'])} 行，显示前 {max_rows} 行[/dim]")
        return "\n".join(lines)

    def render_image(self, data: Any) -> Optional[bytes]:
        if isinstance(data, str):
            data = self._parse_csv(data)
        headers = data.get("headers", [])
        rows = data.get("rows", [])[:30]
        title = data.get("title", "")
        if not headers and not rows:
            return None
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(max(8, len(headers) * 1.2), max(4, len(rows) * 0.4)))
            ax.axis("off")
            tbl = ax.table(cellText=rows, colLabels=headers, loc="center", cellLoc="center")
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(9)
            tbl.scale(1.0, 1.4)
            for (row, col), cell in tbl.get_celld().items():
                if row == 0:
                    cell.set_facecolor("#404040")
                    cell.set_text_props(color="white", weight="bold")
                else:
                    cell.set_facecolor("#F5F5F5" if row % 2 == 0 else "#FFFFFF")
            if title:
                ax.set_title(title, fontsize=12, weight="bold")
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
            plt.close(fig)
            return buf.getvalue()
        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"TableAdapter image: {e}")
            return None


# ── 4. DocumentAdapter ──

class DocumentAdapter(VisualAdapter):
    """文档适配器 — 文本提取 + 排版 PNG 预览。

    输入: file_path (str)
    支持: PDF, DOCX, TXT, MD, PY, JSON, YAML, TOML
    """

    type_name = "document"

    _text_extensions = {".txt", ".md", ".py", ".json", ".yaml", ".yml",
                        ".toml", ".cfg", ".ini", ".env", ".log", ".csv",
                        ".xml", ".html", ".css", ".js", ".ts", ".sh", ".bat"}

    def can_handle(self, data: Any) -> bool:
        if isinstance(data, str):
            p = Path(data)
            if p.suffix.lower() in self._text_extensions:
                return True
            if p.suffix.lower() in {".pdf", ".docx", ".doc"}:
                return True
        return False

    def render_text(self, data: Any) -> str:
        path = Path(data)
        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                return self._extract_pdf(path)
            elif ext in (".docx", ".doc"):
                return self._extract_docx(path)
            else:
                return path.read_text(encoding="utf-8", errors="replace")[:8000]
        except Exception as e:
            return f"[文档读取错误] {path}: {e}"

    def _extract_pdf(self, path: Path) -> str:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            parts = [f"📄 {path.name} ({len(reader.pages)} 页)"]
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    parts.append(f"--- 第 {i+1} 页 ---\n{text}")
            return "\n\n".join(parts)
        except ImportError:
            return f"[需要 PyPDF2: {path.name}]"
        except Exception as e:
            return f"[PDF 错误] {e}"

    def _extract_docx(self, path: Path) -> str:
        try:
            from docx import Document
            doc = Document(str(path))
            parts = [f"📄 {path.name}"]
            parts.extend(p.text for p in doc.paragraphs if p.text.strip())
            return "\n".join(parts) if len(parts) > 1 else "[无文本内容]"
        except ImportError:
            return f"[需要 python-docx: {path.name}]"
        except Exception as e:
            return f"[DOCX 错误] {e}"

    def render_image(self, data: Any) -> Optional[bytes]:
        """Layout document text as a styled PNG preview."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            text = self.render_text(data)[:3000]
            lines = text.split("\n")[:60]
            fig, ax = plt.subplots(figsize=(8, max(4, len(lines) * 0.3)))
            ax.axis("off")
            ax.text(0.02, 0.98, "\n".join(lines), transform=ax.transAxes,
                    fontsize=8, fontfamily="monospace", verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="#FAFAFA", alpha=0.9))
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            plt.close(fig)
            return buf.getvalue()
        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"DocumentAdapter image: {e}")
            return None

    def _extract_meta(self, data: Any) -> dict:
        path = Path(data)
        return {"path": str(path), "ext": path.suffix.lower()}


# ── 5. MapAdapter ──

class MapAdapter(VisualAdapter):
    """地图适配器 — ASCII 坐标网格 + Matplotlib 地图 PNG。

    输入: {"type": "map", "lat": ..., "lon": ..., "zoom": ..., "title": "..."}
          或 image_path (str) → 委托给 ImageAdapter
    """

    type_name = "map"

    def can_handle(self, data: Any) -> bool:
        if isinstance(data, dict) and data.get("type") == "map":
            return True
        if isinstance(data, dict) and "lat" in data and "lon" in data:
            return True
        return False

    def render_text(self, data: Any) -> str:
        lat = data.get("lat", 0.0)
        lon = data.get("lon", 0.0)
        zoom = data.get("zoom", 12)
        title = data.get("title", "")
        size = data.get("grid_size", 20)
        # 生成坐标网格
        lines = [f"📍 {title or f'({lat:.4f}, {lon:.4f})'}"] if title else [f"📍 ({lat:.4f}, {lon:.4f})"]
        lines.append(f"   zoom={zoom}")
        for y in range(size):
            line = ""
            for x in range(size):
                dx = (x - size // 2) * 0.01 / zoom * 12
                dy = (y - size // 2) * 0.01 / zoom * 12
                if abs(dx) < 0.002 and abs(dy) < 0.002:
                    line += "★"
                elif abs(dx) < 0.01 or abs(dy) < 0.01:
                    line += "+"
                else:
                    line += "·"
            lines.append(line)
        return "\n".join(lines)

    def render_image(self, data: Any) -> Optional[bytes]:
        """Draw a simple map with marker using matplotlib/basemap if available."""
        lat = data.get("lat", 0.0)
        lon = data.get("lon", 0.0)
        title = data.get("title", f"({lat:.4f}, {lon:.4f})")
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 6))
            # Simple scatter plot with context box
            margin = 0.1
            ax.set_xlim(lon - margin, lon + margin)
            ax.set_ylim(lat - margin, lat + margin)
            ax.scatter([lon], [lat], c="red", s=200, marker="*", edgecolors="darkred", linewidth=1.5, zorder=5)
            ax.set_xlabel("Longitude")
            ax.set_ylabel("Latitude")
            ax.set_title(title)
            ax.grid(True, alpha=0.3)
            # Annotate
            ax.annotate(f"{lat:.4f}, {lon:.4f}", (lon, lat),
                       textcoords="offset points", xytext=(0, 15),
                       ha="center", fontsize=9,
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            plt.close(fig)
            return buf.getvalue()
        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"MapAdapter image: {e}")
            return None

    def _extract_meta(self, data: Any) -> dict:
        return {"lat": data.get("lat"), "lon": data.get("lon"), "zoom": data.get("zoom")}


# ── 6. DiagramAdapter ──

class DiagramAdapter(VisualAdapter):
    """图表适配器 — Mermaid/Graphviz 文本源码 → 终端提示 + 渲染 PNG。

    输入: {"type": "diagram", "source": "graph TD\\nA-->B", "format": "mermaid"|"dot", "title": "..."}
    """

    type_name = "diagram"

    def can_handle(self, data: Any) -> bool:
        if isinstance(data, dict) and data.get("type") in ("diagram", "mermaid", "graphviz", "dot"):
            return True
        if isinstance(data, str) and ("graph " in data.lower() or "digraph " in data.lower() or
                                       "flowchart " in data.lower() or "sequenceDiagram" in data):
            return True
        return False

    def render_text(self, data: Any) -> str:
        if isinstance(data, str):
            source = data
            fmt = "auto"
            title = ""
        else:
            source = data.get("source", data.get("code", ""))
            fmt = data.get("format", "auto")
            title = data.get("title", "")

        # Auto-detect format
        if fmt == "auto":
            if "digraph" in source.lower() or "graph " in source.lower() or "node " in source.lower():
                fmt = "dot"
            elif any(kw in source for kw in ["flowchart", "sequenceDiagram", "classDiagram",
                                               "gantt", "pie", "graph TD", "graph LR"]):
                fmt = "mermaid"
            else:
                fmt = "mermaid"

        lines = []
        if title:
            lines.append(f"[bold]{title}[/bold]")
        lines.append(f"[dim]图表类型: {fmt}, {len(source)} 字符[/dim]")
        lines.append("```" + ("mermaid" if fmt == "mermaid" else "dot"))
        lines.append(source[:1500])
        lines.append("```")
        lines.append("[dim]提示: 使用 Mermaid Live Editor 或 Graphviz 查看渲染效果[/dim]")
        return "\n".join(lines)

    def render_image(self, data: Any) -> Optional[bytes]:
        """Try to render via graphviz or mermaid-cli if available."""
        if isinstance(data, str):
            source = data
            fmt = "auto"
        else:
            source = data.get("source", data.get("code", ""))
            fmt = data.get("format", "auto")
        if fmt == "auto":
            fmt = "dot" if "digraph" in source.lower() else "mermaid"
        if not source:
            return None

        try:
            if fmt == "dot":
                return self._render_dot(source)
            else:
                return self._render_mermaid(source)
        except Exception as e:
            logger.debug(f"DiagramAdapter image: {e}")
            return None

    def _render_dot(self, source: str) -> Optional[bytes]:
        try:
            import graphviz
            dot = graphviz.Source(source, format="png")
            return dot.pipe()
        except ImportError:
            return None
        except Exception as e:
            logger.warning(f"UnifiedVisual: {e}")
            return None

    def _render_mermaid(self, source: str) -> Optional[bytes]:
        """Render via mmdc CLI if available, else no image."""
        try:
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".mmd", mode="w", delete=False,
                                             encoding="utf-8") as f:
                f.write(source)
                tmp_in = f.name
            tmp_out = tmp_in.replace(".mmd", ".png")
            result = subprocess.run(
                ["mmdc", "-i", tmp_in, "-o", tmp_out, "-b", "transparent"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and os.path.exists(tmp_out):
                data = Path(tmp_out).read_bytes()
                Path(tmp_in).unlink(missing_ok=True)
                Path(tmp_out).unlink(missing_ok=True)
                return data
            Path(tmp_in).unlink(missing_ok=True)
            return None
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.debug(f"Mermaid render: {e}")
            return None

    def _extract_meta(self, data: Any) -> dict:
        src = data if isinstance(data, str) else data.get("source", "")
        return {"source_length": len(src)}


# ═══ UnifiedVisualPort — 主入口 ═══

class UnifiedVisualPort:
    """将所有视觉任务输出统一为 RGB 图像 + 文本标注双通道。

    Vision Banana 风格: 仅通过 type_name 切换，无任务特定模块。
    用法:
        port = get_visual_port()
        output = port.render(some_data)          # 自动检测类型
        output = port.render(data, "plot")       # 指定类型
        outputs = port.render_batch([d1, d2])    # 批量渲染
    """

    def __init__(self):
        self._adapters: list[VisualAdapter] = []
        self._register_defaults()

    def _register_defaults(self):
        """按优先级注册默认适配器 — 先匹配先服务。"""
        self.register(DocumentAdapter())
        self.register(MapAdapter())
        self.register(PlotAdapter())
        self.register(TableAdapter())
        self.register(ImageAdapter())
        self.register(DiagramAdapter())  # 最后 — 可能误匹配文本

    def register(self, adapter: VisualAdapter):
        """注册新适配器。可自定义扩展。"""
        self._adapters.append(adapter)
        logger.debug(f"VisualPort registered: {adapter.type_name}")

    def unregister(self, type_name: str):
        """移除指定类型的适配器。"""
        self._adapters = [a for a in self._adapters if a.type_name != type_name]

    def find_adapter(self, data: Any, type_hint: str = "auto") -> Optional[VisualAdapter]:
        """查找能处理此数据的适配器。"""
        if type_hint != "auto":
            for a in self._adapters:
                if a.type_name == type_hint:
                    return a
            return None
        for a in self._adapters:
            if a.can_handle(data):
                return a
        return None

    def render(self, data: Any, type_hint: str = "auto") -> VisualOutput:
        """渲染单个输出 — 自动检测类型或按提示。"""
        adapter = self.find_adapter(data, type_hint)
        if adapter is None:
            text = self._fallback_text(data)
            return VisualOutput(
                text=text,
                source_type="fallback",
                metadata={"original_type": str(type(data).__name__)},
            )
        try:
            return adapter.render(data)
        except Exception as e:
            logger.warning(f"VisualPort render [{adapter.type_name}]: {e}")
            return VisualOutput(
                text=f"[渲染错误: {adapter.type_name}] {e}",
                source_type=adapter.type_name,
            )

    def render_dual(self, data: Any, type_hint: str = "auto") -> tuple[str, bytes]:
        """便捷方法 — 直接返回 (text, image_bytes)。"""
        out = self.render(data, type_hint)
        return out.text, out.image_bytes

    def render_batch(self, items: list[Any], type_hint: str = "auto") -> list[VisualOutput]:
        """批量渲染 — 顺序执行（并行化留给调用方 asyncio.gather）。"""
        return [self.render(item, type_hint) for item in items]

    def render_batch_parallel(self, items: list[Any],
                              type_hint: str = "auto") -> list[VisualOutput]:
        """批量渲染 — asyncio 并行版。"""
        import asyncio
        async def _run():
            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(None, self.render, item, type_hint)
                     for item in items]
            return await asyncio.gather(*tasks)
        try:
            return asyncio.run(_run())
        except RuntimeError:
            return self.render_batch(items, type_hint)

    def list_adapters(self) -> list[str]:
        return [a.type_name for a in self._adapters]

    def _fallback_text(self, data: Any) -> str:
        """兜底: 将未知数据转为文本。"""
        if isinstance(data, (str, int, float, bool)):
            return str(data)
        try:
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)[:4000]
        except Exception as e:
            logger.warning(f"UnifiedVisual: {e}")
            return str(data)[:4000]


# ═══ 全局单例 ═══

_visual_port: Optional[UnifiedVisualPort] = None


def get_visual_port() -> UnifiedVisualPort:
    """获取全局 UnifiedVisualPort 单例。"""
    global _visual_port
    if _visual_port is None:
        _visual_port = UnifiedVisualPort()
    return _visual_port


# ═══ 便捷函数 ═══

def render_visual(data: Any, type_hint: str = "auto") -> VisualOutput:
    """快捷渲染 — 不缓存单例。"""
    return get_visual_port().render(data, type_hint)


def render_as_data_uri(data: Any, type_hint: str = "auto") -> str:
    """渲染并返回 image data URI (可用于 LLM vision API)。"""
    out = get_visual_port().render(data, type_hint)
    return out.image_data_uri() if out.has_image() else ""


def render_text_only(data: Any, type_hint: str = "auto") -> str:
    """仅渲染 text 通道。"""
    return get_visual_port().render(data, type_hint).text


__all__ = [
    "VisualOutput", "VisualAdapter", "UnifiedVisualPort",
    "DocumentAdapter", "MapAdapter", "PlotAdapter", "TableAdapter",
    "ImageAdapter", "DiagramAdapter",
    "get_visual_port", "render_visual", "render_as_data_uri", "render_text_only",
]
