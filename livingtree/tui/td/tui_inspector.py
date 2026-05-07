"""TUIInspector — Toad DOM tree introspection and diagnostics.

Walks Toad's widget tree at runtime, collects structured info about each
node (type, CSS, geometry, health), detects layout anomalies, and exports
a DOM tree dump for debugging and automated testing.

Non-invasive: reads only, never modifies styles or layout.
Usage:
    inspector = TUIInspector(app)
    dom = inspector.inspect()       # full DOM tree as dict
    issues = inspector.diagnose()   # list of layout issues found
    report = inspector.report()     # human-readable diagnostic report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WidgetSnapshot:
    """Snapshot of a single widget's state at inspection time."""
    name: str
    widget_type: str
    id: str
    classes: list[str]
    parent_type: str
    child_count: int

    has_focus: bool = False
    is_visible: bool = True
    is_mounted: bool = False

    layout: str = ""
    dock: str = ""
    layer: str = ""
    display: str = ""

    region: dict[str, int] = field(default_factory=dict)
    virtual_size: tuple[int, int] = (0, 0)
    container_size: tuple[int, int] = (0, 0)

    width: str = ""
    height: str = ""
    min_width: str = ""
    max_width: str = ""
    min_height: str = ""
    max_height: str = ""

    margin: tuple[int, int, int, int] = (0, 0, 0, 0)
    padding: tuple[int, int, int, int] = (0, 0, 0, 0)
    overflow: tuple[str, str] = ("auto", "auto")

    issues: list[str] = field(default_factory=list)
    children: list[WidgetSnapshot] = field(default_factory=list)

    @property
    def is_overflowing(self) -> bool:
        vs = self.virtual_size
        cs = self.container_size
        if not vs or not cs or cs == (0, 0):
            return False
        return vs[0] > cs[0] or vs[1] > cs[1]

    @property
    def overflow_ratio(self) -> float:
        vs = self.virtual_size
        cs = self.container_size
        if not vs or not cs or cs == (0, 0):
            return 0.0
        return max(vs[0] / max(cs[0], 1), vs[1] / max(cs[1], 1))


@dataclass
class InspectorReport:
    snapshot: WidgetSnapshot
    total_widgets: int
    visible_widgets: int
    issues_found: int
    overflow_widgets: list[str]
    hidden_widgets: list[str]
    empty_widgets: list[str]
    deep_nesting_widgets: list[str]


class TUIInspector:
    """Non-invasive Toad widget tree inspector.

    Scans the live DOM tree from the app root, collecting geometry,
    CSS properties, and health metrics. Detects layout anomalies:
    overflow, clipping, hidden widgets, excessive nesting.
    """

    OVERFLOW_THRESHOLD = 1.5
    DEEP_NESTING_LIMIT = 8
    SMALL_WIDGET_THRESHOLD = 3

    def __init__(self, app):
        self._app = app

    def inspect(self) -> WidgetSnapshot:
        root = self._app.screen
        return self._inspect_widget(root, parent_type="App")

    def diagnose(self) -> list[dict[str, Any]]:
        snapshot = self.inspect()
        issues: list[dict] = []
        self._collect_issues(snapshot, issues, depth=0)
        return issues

    def report(self) -> str:
        snapshot = self.inspect()
        issues = self.diagnose()
        lines = [
            "═══ Toad DOM Tree 诊断报告 ═══",
            f"总组件数: {self._count_widgets(snapshot)}",
            f"布局异常: {len(issues)}",
            "",
        ]

        overflow = [i for i in issues if i["type"] == "overflow"]
        hidden = [i for i in issues if i["type"] == "hidden"]
        empty = [i for i in issues if i["type"] == "empty"]
        deep = [i for i in issues if i["type"] == "deep_nesting"]

        if overflow:
            lines.append(f"--- 溢出 ({len(overflow)}) ---")
            for o in overflow:
                lines.append(
                    f"  {o['widget']} v={o['virtual']} c={o['container']} "
                    f"ratio={o['ratio']:.1f}x  [{o['layout']}]")

        if hidden:
            lines.append(f"--- 隐藏 ({len(hidden)}) ---")
            for h in hidden:
                lines.append(f"  {h['widget']} display={h.get('display','?')}")

        if empty:
            lines.append(f"--- 空组件 ({len(empty)}) ---")
            for e in empty:
                lines.append(f"  {e['widget']} (container_size=0,0)")

        if deep:
            lines.append(f"--- 深层嵌套 ({len(deep)}) ---")
            for d in deep:
                lines.append(f"  {d['widget']} depth={d.get('depth','?')}")

        if not issues:
            lines.append("[OK] 未检测到布局异常")

        return "\n".join(lines)

    def dom_to_dict(self) -> dict:
        snapshot = self.inspect()
        return self._snapshot_to_dict(snapshot)

    # ── Internal ──

    def _inspect_widget(self, widget, parent_type: str = "",
                         depth: int = 0) -> WidgetSnapshot:
        wtype = type(widget).__name__
        name = getattr(widget, 'name', '') or wtype
        wid = getattr(widget, 'id', '') or ''

        classes = []
        if hasattr(widget, 'classes'):
            try:
                classes = list(widget.classes)
            except Exception:
                pass

        children = []
        if hasattr(widget, 'children'):
            for child in widget.children:
                if child is not widget:
                    try:
                        children.append(
                            self._inspect_widget(child, wtype, depth + 1))
                    except Exception:
                        pass

        region = {}
        try:
            r = widget.region if hasattr(widget, 'region') else None
            if r:
                region = {"x": r.x, "y": r.y, "width": r.width, "height": r.height}
        except Exception:
            pass

        vs = (0, 0)
        try:
            vs = (widget.virtual_size.width, widget.virtual_size.height) \
                if hasattr(widget, 'virtual_size') and widget.virtual_size else (0, 0)
        except Exception:
            pass

        cs = (0, 0)
        try:
            cs = (widget.container_size.width, widget.container_size.height) \
                if hasattr(widget, 'container_size') and widget.container_size else (0, 0)
        except Exception:
            pass

        styles = {}
        try:
            s = widget.styles if hasattr(widget, 'styles') else None
            if s:
                styles = {
                    "layout": str(getattr(s, 'layout', '')),
                    "dock": str(getattr(s, 'dock', '')),
                    "layer": str(getattr(s, 'layer', '')),
                    "display": str(getattr(s, 'display', '')),
                    "width": str(getattr(s, 'width', '')),
                    "height": str(getattr(s, 'height', '')),
                    "min_width": str(getattr(s, 'min_width', '')),
                    "max_width": str(getattr(s, 'max_width', '')),
                    "min_height": str(getattr(s, 'min_height', '')),
                    "max_height": str(getattr(s, 'max_height', '')),
                    "overflow": (str(getattr(s, 'overflow_x', 'auto')),
                                 str(getattr(s, 'overflow_y', 'auto'))),
                }
                mg = getattr(s, 'margin', None)
                styles["margin"] = (mg.top, mg.right, mg.bottom, mg.left) if mg else (0, 0, 0, 0)
                pd = getattr(s, 'padding', None)
                styles["padding"] = (pd.top, pd.right, pd.bottom, pd.left) if pd else (0, 0, 0, 0)
        except Exception:
            pass

        issues = self._widget_issues(widget, wtype, vs, cs, styles, depth)

        return WidgetSnapshot(
            name=name, widget_type=wtype, id=wid, classes=classes,
            parent_type=parent_type, child_count=len(children),
            has_focus=hasattr(widget, 'has_focus') and widget.has_focus,
            is_visible=getattr(widget, 'visible', True),
            is_mounted=getattr(widget, '_is_mounted', False),
            layout=styles.get("layout", ""), dock=styles.get("dock", ""),
            layer=styles.get("layer", ""), display=styles.get("display", ""),
            region=region, virtual_size=vs, container_size=cs,
            width=styles.get("width", ""), height=styles.get("height", ""),
            min_width=styles.get("min_width", ""),
            max_width=styles.get("max_width", ""),
            min_height=styles.get("min_height", ""),
            max_height=styles.get("max_height", ""),
            margin=styles.get("margin", (0, 0, 0, 0)),
            padding=styles.get("padding", (0, 0, 0, 0)),
            overflow=styles.get("overflow", ("auto", "auto")),
            issues=issues, children=children,
        )

    def _widget_issues(self, widget, wtype: str,
                        vs: tuple, cs: tuple,
                        styles: dict, depth: int) -> list[str]:
        issues = []

        if cs != (0, 0) and vs != (0, 0):
            if vs[0] > cs[0] or vs[1] > cs[1]:
                ratio = max(vs[0] / max(cs[0], 1), vs[1] / max(cs[1], 1))
                if ratio > self.OVERFLOW_THRESHOLD:
                    issues.append(f"严重溢出: virtual={vs} container={cs} ({ratio:.1f}x)")

        if cs == (0, 0) and depth > 0 and styles.get("display", "") != "none":
            issues.append("空容器: container_size=(0,0)")

        if styles.get("display", "") == "none":
            issues.append("隐藏: display=none")

        if depth >= self.DEEP_NESTING_LIMIT:
            issues.append(f"深层嵌套: depth={depth}")

        region_w = styles.get("region", {}).get("width", 0)
        if 0 < region_w < self.SMALL_WIDGET_THRESHOLD:
            issues.append(f"组件过窄: width={region_w}")

        return issues

    def _collect_issues(self, snapshot: WidgetSnapshot,
                         issues: list, depth: int):
        for issue in snapshot.issues:
            if "严重溢出" in issue:
                issues.append({
                    "type": "overflow", "widget": snapshot.name,
                    "widget_type": snapshot.widget_type,
                    "virtual": snapshot.virtual_size,
                    "container": snapshot.container_size,
                    "ratio": snapshot.overflow_ratio,
                    "layout": snapshot.layout,
                })
            elif "空容器" in issue:
                issues.append({
                    "type": "empty", "widget": snapshot.name,
                    "widget_type": snapshot.widget_type,
                })
            elif "隐藏" in issue:
                issues.append({
                    "type": "hidden", "widget": snapshot.name,
                    "widget_type": snapshot.widget_type,
                    "display": snapshot.display,
                })
            elif "深层嵌套" in issue:
                issues.append({
                    "type": "deep_nesting",
                    "widget": f"{snapshot.name}({snapshot.widget_type})",
                    "depth": depth,
                })
            elif "组件过窄" in issue:
                issues.append({
                    "type": "narrow", "widget": snapshot.name,
                    "width": snapshot.region.get("width", 0),
                })

        for child in snapshot.children:
            self._collect_issues(child, issues, depth + 1)

    @staticmethod
    def _count_widgets(snapshot: WidgetSnapshot) -> int:
        return 1 + sum(TUIInspector._count_widgets(c) for c in snapshot.children)

    @staticmethod
    def _snapshot_to_dict(snapshot: WidgetSnapshot) -> dict:
        return {
            "name": snapshot.name, "type": snapshot.widget_type,
            "id": snapshot.id, "classes": snapshot.classes,
            "region": snapshot.region,
            "virtual_size": list(snapshot.virtual_size),
            "container_size": list(snapshot.container_size),
            "layout": snapshot.layout, "dock": snapshot.dock,
            "layer": snapshot.layer, "display": snapshot.display,
            "width": snapshot.width, "height": snapshot.height,
            "overflow": list(snapshot.overflow),
            "issues": snapshot.issues,
            "child_count": snapshot.child_count,
            "children": [TUIInspector._snapshot_to_dict(c)
                         for c in snapshot.children],
        }
