"""MapPreviewWidget — renders map/image preview in the terminal.

Converts geographic data or image files to ASCII art for terminal display.
Supports tile-based map rendering and image-to-ASCII conversion.
"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static
from textual.reactive import reactive
from pathlib import Path


class MapPreviewWidget(Vertical):
    can_focus = False
    preview_content = reactive("")

    def __init__(self, name: str = "MapPreview", classes: str = ""):
        super().__init__(name=name)
        self._classes = classes
        self._image_path: str = ""

    def compose(self):
        yield Static("🗺 地图预览", classes="preview-title")
        yield Static("", id="map-canvas", classes="map-canvas")

    def load_image(self, image_path: str) -> None:
        self._image_path = image_path
        try:
            from PIL import Image
            img = Image.open(image_path)
            img = img.convert("L").resize((60, 30))
            pixels = img.load()
            charset = " .:-=+*#%@"
            lines = []
            for y in range(img.height):
                line = ""
                for x in range(img.width):
                    gray = pixels[x, y]
                    idx = int(gray / 256 * len(charset))
                    line += charset[min(idx, len(charset) - 1)]
                lines.append(line)
            self.preview_content = "\n".join(lines)
            self.query_one("#map-canvas", Static).update(self.preview_content)
        except ImportError:
            self.preview_content = f"[预览] {image_path}"
            self.query_one("#map-canvas", Static).update(self.preview_content)
        except Exception as e:
            self.preview_content = f"[错误] {e}"
            self.query_one("#map-canvas", Static).update(f"[red]{e}[/red]")

    def load_coords(self, lat: float, lon: float, zoom: int = 12) -> None:
        label = f"📍 坐标: {lat:.4f}, {lon:.4f} (zoom {zoom})"
        grid = self._generate_coord_grid(lat, lon)
        self.preview_content = f"{label}\n{grid}"
        self.query_one("#map-canvas", Static).update(self.preview_content)

    def _generate_coord_grid(self, lat: float, lon: float, size: int = 20) -> str:
        lines = []
        for y in range(size):
            line = ""
            for x in range(size):
                dx = (x - size // 2) * 0.01
                dy = (y - size // 2) * 0.01
                if abs(dx) < 0.002 and abs(dy) < 0.002:
                    line += "★"
                elif abs(dx) < 0.01 or abs(dy) < 0.01:
                    line += "+"
                else:
                    line += "·"
            lines.append(line)
        return "\n".join(lines)

    def clear(self) -> None:
        self.preview_content = ""
        self.query_one("#map-canvas", Static).update("")
