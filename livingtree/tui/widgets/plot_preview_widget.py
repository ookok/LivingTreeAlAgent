"""PlotPreviewWidget — renders charts/plots in the terminal.

Uses Unicode characters for bar charts, line plots, and scatter plots.
Falls back to JPEG/PNG → ASCII conversion when image files are provided.
"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static
from textual.reactive import reactive


class PlotPreviewWidget(Vertical):
    can_focus = False
    preview_content = reactive("")

    def __init__(self, name: str = "PlotPreview", classes: str = ""):
        super().__init__(name=name)
        self._classes = classes

    def compose(self):
        yield Static("📈 图表预览", classes="preview-title")
        yield Static("", id="plot-canvas", classes="plot-canvas")

    def render_bar_chart(self, data: dict[str, float], title: str = "", width: int = 50) -> None:
        if not data:
            self.preview_content = "[dim]无数据[/dim]"
            self.query_one("#plot-canvas", Static).update(self.preview_content)
            return

        max_val = max(abs(v) for v in data.values()) or 1
        max_label = max(len(k) for k in data.keys()) or 1
        bar_width = max(4, width - max_label - 5)
        chars = "█▉▊▋▌▍▎▏"

        lines = []
        if title:
            lines.append(f"[bold]{title}[/bold]")
        for label, value in data.items():
            bar_len = int(abs(value) / max_val * bar_width * 8)
            full = bar_len // 8
            partial = bar_len % 8
            bar = "█" * full
            if partial > 0:
                bar += chars[partial]
            pct = f"{value:.1f}"
            lines.append(f"{label:>{max_label}} │ {bar} {pct}")

        self.preview_content = "\n".join(lines)
        self.query_one("#plot-canvas", Static).update(self.preview_content)

    def render_line_plot(self, data: list[float], title: str = "", height: int = 15, width: int = 50) -> None:
        if not data:
            self.preview_content = "[dim]无数据[/dim]"
            self.query_one("#plot-canvas", Static).update(self.preview_content)
            return

        min_val, max_val = min(data), max(data)
        if min_val == max_val:
            min_val -= 1
            max_val += 1
        val_range = max_val - min_val
        chars = "▁▂▃▄▅▆▇█"

        step = max(1, len(data) // width)
        sampled = [data[i] for i in range(0, len(data), step)][:width]

        lines = []
        if title:
            lines.append(f"[bold]{title}[/bold]")
        for row in range(height - 1, -1, -1):
            threshold = min_val + (row / (height - 1)) * val_range
            line = ""
            for val in sampled:
                if val >= threshold:
                    idx = min(7, int((val - min_val) / val_range * 7))
                    line += chars[idx]
                else:
                    line += " "
            lines.append(line)

        lines.append(f"[dim]min: {min_val:.1f}  max: {max_val:.1f}  n: {len(data)}[/dim]")
        self.preview_content = "\n".join(lines)
        self.query_one("#plot-canvas", Static).update(self.preview_content)

    def render_scatter(self, points: list[tuple[float, float]], title: str = "", height: int = 15, width: int = 40) -> None:
        if not points:
            self.preview_content = "[dim]无数据[/dim]"
            self.query_one("#plot-canvas", Static).update(self.preview_content)
            return

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        x_range = (x_max - x_min) or 1
        y_range = (y_max - y_min) or 1

        grid = [[" " for _ in range(width)] for _ in range(height)]
        for x, y in points:
            col = int((x - x_min) / x_range * (width - 1))
            row = int((1 - (y - y_min) / y_range) * (height - 1))
            if 0 <= col < width and 0 <= row < height:
                grid[row][col] = "●"

        lines = []
        if title:
            lines.append(f"[bold]{title}[/bold]")
        for row in grid:
            lines.append("".join(row))
        lines.append(f"[dim]x: [{x_min:.1f}, {x_max:.1f}]  y: [{y_min:.1f}, {y_max:.1f}][/dim]")

        self.preview_content = "\n".join(lines)
        self.query_one("#plot-canvas", Static).update(self.preview_content)

    def clear(self) -> None:
        self.preview_content = ""
        self.query_one("#plot-canvas", Static).update("")
