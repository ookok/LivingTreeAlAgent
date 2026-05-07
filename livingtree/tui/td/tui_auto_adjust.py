"""TUIAutoAdjust — Non-destructive Toad layout micro-adjustment engine.

Reads TUIInspector diagnostics and proposes/suggests CSS micro-adjustments
that fix layout issues without changing the visual design intent.

Rules (what we NEVER change):
  - Dock position (dock: left/right/bottom)
  - Layout mode (layout: vertical/horizontal/grid)
  - Layer assignment (layer: prompt/base)
  - Colors, borders, opacity, tint

Rules (what we CAN micro-adjust):
  - Width/height (only when overflowing)
  - Min/max dimensions
  - Overflow mode (hidden→auto→scroll)
  - Padding (when content is clipped)
  - Margin (when docked widgets collide)

Usage:
    adjuster = TUIAutoAdjust(inspector)
    suggestions = adjuster.analyze()
    # → list of AdjustmentSuggestion with original→proposed values
    adjuster.apply(suggestions, app)  # apply suggested changes to live widgets
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class AdjustmentSuggestion:
    widget_name: str
    widget_type: str
    issue_type: str
    css_property: str
    original_value: str
    proposed_value: str
    reason: str
    severity: str = "warning"
    css_selector: str = ""

    @property
    def is_safe(self) -> bool:
        return self.severity in ("info", "warning")

    @property
    def tcss_rule(self) -> str:
        return f"{self.css_property}: {self.proposed_value};"

    @property
    def full_suggestion(self) -> str:
        return f"{self.issue_type}: {self.css_property} {self.original_value} → {self.proposed_value} ({self.reason})"


@dataclass
class AdjustReport:
    total_issues: int
    suggestions: list[AdjustmentSuggestion]
    applied: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class TUIAutoAdjust:
    """Non-destructive layout micro-adjuster for Toad TUI.

    Analyzes inspector diagnostics and proposes minimal CSS changes
    to fix layout issues. Changes are previewable and reversible.
    """

    MAX_WIDTH_PROPORTIONAL = "1fr"
    MIN_SAFE_MIN_WIDTH = 8
    MIN_SAFE_MIN_HEIGHT = 2

    def __init__(self, inspector):
        self._inspector = inspector
        self._app = inspector._app

    def analyze(self) -> list[AdjustmentSuggestion]:
        issues = self._inspector.diagnose()
        suggestions = []

        for issue in issues:
            if issue["type"] == "overflow":
                suggestions.extend(self._suggest_overflow_fix(issue))
            elif issue["type"] == "empty":
                suggestions.extend(self._suggest_empty_fix(issue))
            elif issue["type"] == "narrow":
                suggestions.extend(self._suggest_narrow_fix(issue))
            elif issue["type"] == "hidden":
                suggestions.append(self._suggest_hidden_check(issue))
            elif issue["type"] == "deep_nesting":
                suggestions.append(self._suggest_nesting_check(issue))

        return suggestions

    def apply(self, suggestions: list[AdjustmentSuggestion],
              dry_run: bool = True) -> AdjustReport:
        applied = 0
        skipped = 0
        errors: list[str] = []

        for s in suggestions:
            if not s.is_safe:
                logger.info(f"Skipping unsafe adjustment: {s.full_suggestion}")
                skipped += 1
                continue

            if dry_run:
                logger.info(f"[DRY RUN] Would apply: {s.full_suggestion}")
                continue

            try:
                widget = self._find_widget_by_name(s.widget_name, s.widget_type)
                if widget and hasattr(widget, 'styles'):
                    self._apply_style_change(widget, s.css_property,
                                              s.proposed_value)
                    logger.info(f"Applied: {s.full_suggestion}")
                    applied += 1
                else:
                    logger.info(f"Widget not found: {s.widget_name} ({s.widget_type})")
                    skipped += 1
            except Exception as e:
                errors.append(f"{s.widget_name}: {e}")
                skipped += 1

        return AdjustReport(
            total_issues=len(suggestions), suggestions=suggestions,
            applied=applied, skipped=skipped, errors=errors,
        )

    def preview(self) -> str:
        suggestions = self.analyze()
        if not suggestions:
            return "[OK] No layout adjustments needed."

        lines = ["═══ 布局微调预览 ═══", f"建议调整: {len(suggestions)} 项\n"]
        for s in suggestions:
            lines.append(
                f"[{s.severity.upper()}] {s.widget_name}({s.widget_type}) - "
                f"{s.issue_type}")
            lines.append(f"  {s.css_property}: {s.original_value} → {s.proposed_value}")
            lines.append(f"  原因: {s.reason}")
            lines.append("")

        grouped = {}
        for s in suggestions:
            grouped[s.issue_type] = grouped.get(s.issue_type, 0) + 1
        lines.append("--- 按类型统计 ---")
        for issue_type, count in grouped.items():
            lines.append(f"  {issue_type}: {count}")
        return "\n".join(lines)

    # ── Suggestion generators ──

    def _suggest_overflow_fix(self, issue: dict) -> list[AdjustmentSuggestion]:
        suggestions = []
        vs = issue.get("virtual", (0, 0))
        cs = issue.get("container", (0, 0))
        ratio = issue.get("ratio", 1.0)
        name = issue["widget"]
        wtype = issue["widget_type"]

        width_exceeded = vs[0] > cs[0] if vs and cs else False
        height_exceeded = vs[1] > cs[1] if vs and cs else False

        if width_exceeded and cs[0] > 0:
            suggestions.append(AdjustmentSuggestion(
                widget_name=name, widget_type=wtype,
                issue_type="overflow", css_property="overflow-x",
                original_value="auto", proposed_value="auto",
                reason=f"virtual_w={vs[0]} > container_w={cs[0]} ({ratio:.1f}x); 滚动已启用",
                severity="info",
            ))

        if height_exceeded and cs[1] > 0:
            suggestions.append(AdjustmentSuggestion(
                widget_name=name, widget_type=wtype,
                issue_type="overflow", css_property="overflow-y",
                original_value="auto", proposed_value="auto",
                reason=f"virtual_h={vs[1]} > container_h={cs[1]} ({ratio:.1f}x); 滚动已启用",
                severity="info",
            ))

        if ratio > 3.0 and cs[0] > 0:
            suggestions.append(AdjustmentSuggestion(
                widget_name=name, widget_type=wtype,
                issue_type="overflow_severe", css_property="max-height",
                original_value="auto",
                proposed_value=f"{max(cs[1], 20)}vh" if cs[1] > 0 else "50vh",
                reason=f"严重溢出({ratio:.1f}x); 建议限制最大高度",
                severity="warning",
            ))

        return suggestions

    def _suggest_empty_fix(self, issue: dict) -> list[AdjustmentSuggestion]:
        name = issue["widget"]
        wtype = issue["widget_type"]
        return [
            AdjustmentSuggestion(
                widget_name=name, widget_type=wtype,
                issue_type="empty_container", css_property="min-height",
                original_value="auto",
                proposed_value=str(self.MIN_SAFE_MIN_HEIGHT),
                reason="空容器(0,0); 设置最小高度避免布局塌陷",
                severity="warning",
            ),
            AdjustmentSuggestion(
                widget_name=name, widget_type=wtype,
                issue_type="empty_container", css_property="min-width",
                original_value="auto",
                proposed_value=str(self.MIN_SAFE_MIN_WIDTH),
                reason="空容器(0,0); 设置最小宽度避免布局塌陷",
                severity="warning",
            ),
        ]

    def _suggest_narrow_fix(self, issue: dict) -> list[AdjustmentSuggestion]:
        name = issue["widget"]
        wtype = issue["widget_type"]
        current_w = issue.get("width", 3)

        suggestions = []
        if current_w < self.MIN_SAFE_MIN_WIDTH:
            suggestions.append(AdjustmentSuggestion(
                widget_name=name, widget_type=wtype,
                issue_type="narrow_widget", css_property="min-width",
                original_value=str(current_w),
                proposed_value=str(self.MIN_SAFE_MIN_WIDTH),
                reason=f"组件过窄(width={current_w}); 保证最小阅读宽度",
                severity="info",
            ))
        return suggestions

    def _suggest_hidden_check(self, issue: dict) -> AdjustmentSuggestion:
        return AdjustmentSuggestion(
            widget_name=issue["widget"], widget_type=issue["widget_type"],
            issue_type="hidden_widget", css_property="display",
            original_value="none", proposed_value="none",
            reason="组件display=none — 检查是否故意隐藏",
            severity="info",
        )

    def _suggest_nesting_check(self, issue: dict) -> AdjustmentSuggestion:
        return AdjustmentSuggestion(
            widget_name=issue["widget"], widget_type="",
            issue_type="deep_nesting", css_property="(结构)",
            original_value=f"depth={issue.get('depth', 0)}",
            proposed_value="考虑扁平化",
            reason="嵌套过深影响布局性能和可维护性",
            severity="info",
        )

    # ── Widget style manipulation ──

    def _find_widget_by_name(self, name: str, widget_type: str = ""):
        if not self._app or not hasattr(self._app, 'screen'):
            return None
        return self._walk_find(self._app.screen, name, widget_type)

    def _walk_find(self, root, name: str, widget_type: str = ""):
        if type(root).__name__ == widget_type if widget_type else False:
            w_name = getattr(root, 'name', '') or type(root).__name__
            if w_name == name:
                return root
        if type(root).__name__ == name:
            return root
        if hasattr(root, 'children'):
            for child in root.children:
                found = self._walk_find(child, name, widget_type)
                if found:
                    return found
        return None

    @staticmethod
    def _apply_style_change(widget, property_name: str, value: str):
        """Apply a CSS property change to a widget's inline styles.

        Only touches the given property — all other styles preserved.
        """
        styles = widget.styles

        prop_map = {
            "width": "width", "height": "height",
            "min-width": "min_width", "max-width": "max_width",
            "min-height": "min_height", "max-height": "max_height",
            "overflow-x": "overflow_x", "overflow-y": "overflow_y",
            "display": "display", "margin": "margin", "padding": "padding",
        }

        attr = prop_map.get(property_name)
        if not attr:
            logger.debug(f"Unknown CSS property for micro-adjust: {property_name}")
            return

        setattr(styles, attr, value)

    # ── CSS string generation ──

    def generate_tcss_patch(self, suggestions: list[AdjustmentSuggestion]) -> str:
        """Generate a TCSS patch file from adjustment suggestions.

        The patch can be reviewed before manual integration into the
        project's .tcss stylesheet. Handles selector generation.
        """
        lines = ["/* Auto-generated layout micro-adjustment patch */",
                 "/* Review before merging into main.tcss */", ""]

        by_widget: dict[str, list[AdjustmentSuggestion]] = {}
        for s in suggestions:
            key = f"{s.widget_type}"
            if s.widget_type not in by_widget:
                by_widget[key] = []
            by_widget[key].append(s)

        for wtype, sug_list in by_widget.items():
            lines.append(f"/* {wtype} — {len(sug_list)} adjustments */")
            lines.append(f"{wtype} {{")
            for s in sug_list:
                if s.css_property == "(结构)":
                    lines.append(f"    /* {s.reason} */")
                else:
                    lines.append(f"    {s.tcss_rule}  /* {s.reason} */")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)
