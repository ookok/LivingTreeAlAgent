"""TailwindUI — Python dataclass → Tailwind CSS HTML component library.

DesignGUI-inspired: define UI in Python objects, render to production Tailwind HTML.
No JS framework, no npm install — pure server-side rendering with HTMX for interactivity.

Components: Button, Card, Table, Form, Grid, Navbar, Modal, Tabs, Alert, Badge, Spinner

LLM integration: LLM outputs A2UI JSON → LivingRenderer detects "tailwind" type → TailwindHTML

Usage:
    ui = TailwindUI()
    card = ui.Card(title="系统状态", children=[
        ui.Badge("在线", color="green"),
        ui.Table(columns=["模块","状态"], rows=[["TreeLLM","✅"],["CodeGraph","✅"]])
    ])
    html = ui.render(card)  # → Tailwind-styled HTML string
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any, Optional


class TailwindUI:
    """Python → Tailwind CSS renderer. Zero JS dependency, HTMX-ready."""

    # ═══ Component Classes ═══════════════════════════════════════

    @staticmethod
    def Button(label: str, variant: str = "primary", size: str = "md",
               hx_get: str = "", hx_post: str = "", hx_target: str = "",
               disabled: bool = False, **attrs) -> str:
        variants = {
            "primary": "bg-blue-600 hover:bg-blue-700 text-white",
            "secondary": "bg-gray-200 hover:bg-gray-300 text-gray-800",
            "danger": "bg-red-600 hover:bg-red-700 text-white",
            "success": "bg-green-600 hover:bg-green-700 text-white",
            "ghost": "bg-transparent hover:bg-gray-100 text-gray-600",
        }
        sizes = {"sm": "px-2 py-1 text-xs", "md": "px-4 py-2 text-sm",
                 "lg": "px-6 py-3 text-base"}
        hx_attrs = ""
        if hx_get:
            hx_attrs += f' hx-get="{hx_get}"'
        if hx_post:
            hx_attrs += f' hx-post="{hx_post}"'
        if hx_target:
            hx_attrs += f' hx-target="{hx_target}"'
        disabled_attr = " disabled" if disabled else ""
        return (
            f'<button class="{variants.get(variant, variants["primary"])} '
            f'{sizes.get(size, sizes["md"])} rounded-lg font-medium '
            f'transition-colors duration-150{disabled_attr}"{hx_attrs}>'
            f'{escape(label)}</button>'
        )

    @staticmethod
    def Card(title: str = "", children: list[str] | str = "",
             footer: str = "", accent: str = "blue") -> str:
        accents = {"blue": "border-l-4 border-blue-500",
                   "green": "border-l-4 border-green-500",
                   "red": "border-l-4 border-red-500"}
        kids = "".join(children) if isinstance(children, list) else children
        html = (f'<div class="bg-white rounded-xl shadow-sm '
                f'{accents.get(accent, "")} p-5 mb-4">')
        if title:
            html += f'<h3 class="text-lg font-semibold text-gray-800 mb-3">{escape(title)}</h3>'
        html += f'<div class="text-gray-600">{kids}</div>'
        if footer:
            html += (f'<div class="mt-4 pt-3 border-t border-gray-100 '
                    f'text-sm text-gray-500">{footer}</div>')
        html += '</div>'
        return html

    @staticmethod
    def Table(columns: list[str], rows: list[list[Any]],
              striped: bool = True, hover: bool = True) -> str:
        html = '<div class="overflow-x-auto"><table class="w-full text-sm">'
        html += '<thead><tr class="bg-gray-50 border-b">'
        for col in columns:
            html += (f'<th class="px-4 py-2 text-left font-medium '
                    f'text-gray-600">{escape(str(col))}</th>')
        html += '</tr></thead><tbody>'
        for i, row in enumerate(rows):
            bg = "bg-gray-50" if striped and i % 2 == 0 else "bg-white"
            hover_cls = "hover:bg-blue-50 transition-colors" if hover else ""
            html += f'<tr class="border-b {bg} {hover_cls}">'
            for cell in row:
                html += f'<td class="px-4 py-2 text-gray-700">{escape(str(cell))}</td>'
            html += '</tr>'
        html += '</tbody></table></div>'
        return html

    @staticmethod
    def Badge(label: str, color: str = "gray") -> str:
        colors = {
            "gray": "bg-gray-100 text-gray-700",
            "green": "bg-green-100 text-green-700",
            "red": "bg-red-100 text-red-700",
            "blue": "bg-blue-100 text-blue-700",
            "yellow": "bg-yellow-100 text-yellow-700",
        }
        return (f'<span class="inline-flex items-center px-2.5 py-0.5 '
                f'rounded-full text-xs font-medium '
                f'{colors.get(color, colors["gray"])}">{escape(label)}</span>')

    @staticmethod
    def Alert(message: str, level: str = "info") -> str:
        levels = {
            "info": "bg-blue-50 border-blue-200 text-blue-800",
            "success": "bg-green-50 border-green-200 text-green-800",
            "warning": "bg-yellow-50 border-yellow-200 text-yellow-800",
            "error": "bg-red-50 border-red-200 text-red-800",
        }
        return (f'<div class="border rounded-lg p-4 mb-3 '
                f'{levels.get(level, levels["info"])}">{escape(message)}</div>')

    @staticmethod
    def Spinner(size: str = "md") -> str:
        sizes = {"sm": "w-4 h-4", "md": "w-8 h-8", "lg": "w-12 h-12"}
        return (f'<div class="{sizes.get(size, sizes["md"])} animate-spin '
                f'rounded-full border-2 border-gray-300 border-t-blue-600"></div>')

    @staticmethod
    def Modal(title: str, content: str, show: bool = False) -> str:
        display = "" if show else " hidden"
        return (
            f'<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center '
            f'justify-center z-50{display}" id="modal">'
            f'<div class="bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4">'
            f'<div class="flex justify-between items-center p-4 border-b">'
            f'<h3 class="text-lg font-semibold">{escape(title)}</h3>'
            f'<button class="text-gray-400 hover:text-gray-600" '
            f'onclick="document.getElementById(\'modal\').classList.add(\'hidden\')">✕</button>'
            f'</div>'
            f'<div class="p-4">{content}</div>'
            f'</div></div>'
        )

    @staticmethod
    def Tabs(tabs: dict[str, str], active: str = "") -> str:
        """tabs: {label: content_html}"""
        active = active or list(tabs.keys())[0]
        html = '<div class="border-b border-gray-200 mb-3">'
        html += '<nav class="flex space-x-4">'
        for label in tabs:
            is_active = label == active
            cls = ("text-blue-600 border-b-2 border-blue-600" if is_active
                   else "text-gray-500 hover:text-gray-700")
            html += (f'<button class="px-3 py-2 text-sm font-medium {cls} '
                    f'border-b-2 border-transparent hover:border-gray-300" '
                    f'onclick="this.parentElement.parentElement.nextElementSibling'
                    f'.querySelectorAll(\'.tab-content\').forEach(c=>c.classList.add(\'hidden\'));'
                    f'document.getElementById(\'tab-{escape(label)}\').classList.remove(\'hidden\');'
                    f'this.parentElement.querySelectorAll(\'button\').forEach(b=>b.classList.remove'
                    f'(\'text-blue-600\',\'border-blue-600\'));'
                    f'this.classList.add(\'text-blue-600\',\'border-blue-600\')">'
                    f'{escape(label)}</button>')
        html += '</nav></div>'
        for label, content in tabs.items():
            hidden = "" if label == active else " hidden"
            html += (f'<div id="tab-{escape(label)}" class="tab-content{hidden}">'
                    f'{content}</div>')
        return html

    @staticmethod
    def Navbar(title: str, links: list[tuple[str, str]] = None,
               user_info: str = "", accent: str = "indigo") -> str:
        links = links or []
        return (
            f'<nav class="bg-{accent}-600 text-white px-6 py-3 flex items-center '
            f'justify-between shadow-md">'
            f'<div class="flex items-center space-x-6">'
            f'<span class="text-xl font-bold tracking-tight">{escape(title)}</span>'
            + "".join(
                f'<a href="{url}" class="text-{accent}-100 hover:text-white '
                f'text-sm font-medium transition-colors">{escape(label)}</a>'
                for label, url in links
            ) +
            f'</div>'
            f'<div class="text-sm text-{accent}-200">{escape(user_info)}</div>'
            f'</nav>'
        )

    @staticmethod
    def Grid(columns: int = 3, children: list[str] = None,
             gap: str = "4") -> str:
        children = children or []
        cols = {1: "grid-cols-1", 2: "grid-cols-2", 3: "grid-cols-3",
                4: "grid-cols-4"}
        return (
            f'<div class="grid {cols.get(columns, "grid-cols-3")} '
            f'gap-{gap}">{"".join(children)}</div>'
        )

    @staticmethod
    def Form(fields: list[dict], submit_label: str = "提交",
             hx_post: str = "", hx_target: str = "") -> str:
        """fields: [{name, label, type, placeholder, required}]"""
        html = f'<form class="space-y-4"'
        if hx_post:
            html += f' hx-post="{hx_post}"'
        if hx_target:
            html += f' hx-target="{hx_target}"'
        html += '>'
        for f in fields:
            required = " required" if f.get("required") else ""
            html += (
                f'<div>'
                f'<label class="block text-sm font-medium text-gray-700 mb-1">'
                f'{escape(f.get("label", f.get("name", "")))}</label>'
                f'<input name="{escape(f.get("name", ""))}" '
                f'type="{f.get("type", "text")}" '
                f'placeholder="{escape(f.get("placeholder", ""))}" '
                f'class="w-full px-3 py-2 border border-gray-300 rounded-lg '
                f'focus:ring-2 focus:ring-blue-500 focus:border-blue-500 '
                f'text-sm"{required}>'
                f'</div>'
            )
        html += (
            f'<button type="submit" class="bg-blue-600 hover:bg-blue-700 '
            f'text-white px-6 py-2 rounded-lg text-sm font-medium '
            f'transition-colors">{escape(submit_label)}</button>'
        )
        html += '</form>'
        return html

    # ═══ Page Builder ════════════════════════════════════════════

    @staticmethod
    def Page(title: str, children: list[str] = None,
             navbar: str = "", sidebar: str = "") -> str:
        children = children or []
        body = (
            f'<div class="flex min-h-screen bg-gray-50">'
            f'{sidebar}'
            f'<main class="flex-1 p-6">'
            f'{"".join(children)}'
            f'</main>'
            f'</div>'
        )
        return (
            '<!DOCTYPE html><html lang="zh">'
            '<head><meta charset="UTF-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title>'
            '<script src="https://cdn.tailwindcss.com"></script>'
            '<script src="https://unpkg.com/htmx.org@1.9.10"></script>'
            '</head>'
            f'<body>{navbar}{body}</body></html>'
        )

    @staticmethod
    def Sidebar(items: list[tuple[str, str, str]], active: str = "",
                width: str = "w-64") -> str:
        """items: [(icon_emoji, label, url)]"""
        html = (f'<aside class="{width} bg-white border-r border-gray-200 '
                f'p-4 flex-shrink-0 hidden lg:block">')
        html += '<nav class="space-y-1">'
        for icon, label, url in items:
            is_active = label == active
            bg = "bg-blue-50 text-blue-700" if is_active else "text-gray-600 hover:bg-gray-50"
            html += (
                f'<a href="{url}" class="flex items-center space-x-2 px-3 py-2 '
                f'rounded-lg text-sm font-medium {bg} transition-colors">'
                f'<span>{icon}</span><span>{escape(label)}</span></a>'
            )
        html += '</nav></aside>'
        return html

    # ═══ Primitives ═══════════════════════════════════════════════

    @staticmethod
    def Box(children: str = "", padding: str = "4", bg: str = "white",
            rounded: str = "lg", shadow: str = "") -> str:
        sh = f"shadow-{shadow}" if shadow else ""
        return (f'<div class="bg-{bg} p-{padding} rounded-{rounded} {sh}">'
                f'{children}</div>')

    @staticmethod
    def Flex(children: list[str] = None, direction: str = "row",
             gap: str = "4", align: str = "center") -> str:
        children = children or []
        dirs = {"row": "flex-row", "col": "flex-col"}
        return (f'<div class="flex {dirs.get(direction, "flex-row")} '
                f'gap-{gap} items-{align}">{"".join(children)}</div>')

    @staticmethod
    def Stack(children: list[str] = None, gap: str = "3") -> str:
        children = children or []
        return f'<div class="flex flex-col gap-{gap}">{"".join(children)}</div>'

    @staticmethod
    def Container(children: str = "", max_w: str = "4xl") -> str:
        return f'<div class="max-w-{max_w} mx-auto px-4">{children}</div>'

    @staticmethod
    def Text(content: str, size: str = "base", weight: str = "normal",
             color: str = "gray-700") -> str:
        sizes = {"xs": "text-xs", "sm": "text-sm", "base": "text-base",
                 "lg": "text-lg", "xl": "text-xl", "2xl": "text-2xl"}
        weights = {"normal": "font-normal", "medium": "font-medium",
                   "semibold": "font-semibold", "bold": "font-bold"}
        return (f'<span class="{sizes.get(size,"text-base")} '
                f'{weights.get(weight,"font-normal")} text-{color}">'
                f'{escape(content)}</span>')

    @staticmethod
    def Divider() -> str:
        return '<hr class="border-t border-gray-200 my-4">'

    # ═══ Inputs ════════════════════════════════════════════════════

    @staticmethod
    def Input(name: str, label: str = "", type_: str = "text",
              placeholder: str = "", required: bool = False,
              value: str = "") -> str:
        req = " required" if required else ""
        html = ""
        if label:
            html += (f'<label class="block text-sm font-medium text-gray-700 mb-1">'
                    f'{escape(label)}</label>')
        html += (f'<input name="{escape(name)}" type="{type_}" '
                f'placeholder="{escape(placeholder)}" value="{escape(value)}"'
                f' class="w-full px-3 py-2 border border-gray-300 rounded-lg '
                f'focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"'
                f'{req}>')
        return f'<div>{html}</div>'

    @staticmethod
    def Textarea(name: str, label: str = "", placeholder: str = "",
                 rows: int = 4) -> str:
        html = ""
        if label:
            html += (f'<label class="block text-sm font-medium text-gray-700 mb-1">'
                    f'{escape(label)}</label>')
        html += (f'<textarea name="{escape(name)}" rows="{rows}" '
                f'placeholder="{escape(placeholder)}"'
                f' class="w-full px-3 py-2 border border-gray-300 rounded-lg '
                f'focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm">'
                f'</textarea>')
        return f'<div>{html}</div>'

    @staticmethod
    def Select(name: str, label: str = "", options: list[tuple[str, str]] = None) -> str:
        """options: [(value, label)]"""
        options = options or []
        html = ""
        if label:
            html += (f'<label class="block text-sm font-medium text-gray-700 mb-1">'
                    f'{escape(label)}</label>')
        opts = "".join(
            f'<option value="{escape(v)}">{escape(l)}</option>' for v, l in options
        )
        html += (f'<select name="{escape(name)}" class="w-full px-3 py-2 border '
                f'border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500">'
                f'{opts}</select>')
        return f'<div>{html}</div>'

    @staticmethod
    def Checkbox(name: str, label: str = "", checked: bool = False) -> str:
        chk = " checked" if checked else ""
        return (f'<label class="flex items-center space-x-2 text-sm text-gray-700">'
                f'<input type="checkbox" name="{escape(name)}"'
                f' class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"'
                f'{chk}>'
                f'<span>{escape(label)}</span></label>')

    @staticmethod
    def ToggleSwitch(name: str, label: str = "", checked: bool = False) -> str:
        chk = " checked" if checked else ""
        return (f'<label class="flex items-center space-x-2 cursor-pointer">'
                f'<input type="checkbox" name="{escape(name)}"'
                f' class="sr-only peer"{chk}>'
                f'<div class="w-9 h-5 bg-gray-300 peer-checked:bg-blue-600 '
                f'rounded-full relative after:content-[\'\'] after:absolute '
                f'after:top-0.5 after:left-0.5 after:bg-white after:rounded-full '
                f'after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-4">'
                f'</div>'
                f'<span class="text-sm text-gray-700">{escape(label)}</span></label>')

    # ═══ Display ═══════════════════════════════════════════════════

    @staticmethod
    def Image(src: str, alt: str = "", width: str = "full",
              rounded: str = "lg") -> str:
        return (f'<img src="{escape(src)}" alt="{escape(alt)}" '
                f'class="w-{width} rounded-{rounded} object-cover">')

    @staticmethod
    def Avatar(name: str, src: str = "", size: str = "md") -> str:
        sizes = {"sm": "w-8 h-8 text-xs", "md": "w-10 h-10 text-sm",
                 "lg": "w-12 h-12 text-base"}
        if src:
            return (f'<img src="{escape(src)}" alt="{escape(name)}" '
                    f'class="{sizes.get(size,sizes["md"])} rounded-full object-cover">')
        initials = "".join(w[0] for w in name.split()[:2]).upper()
        return (f'<span class="inline-flex items-center justify-center '
                f'{sizes.get(size,sizes["md"])} rounded-full bg-blue-100 '
                f'text-blue-700 font-medium">{initials}</span>')

    @staticmethod
    def Accordion(items: list[tuple[str, str]]) -> str:
        """items: [(title, content)]"""
        html = '<div class="divide-y divide-gray-200 border rounded-lg">'
        for title, content in items:
            html += (
                f'<details class="group"><summary class="px-4 py-3 text-sm '
                f'font-medium text-gray-700 cursor-pointer hover:bg-gray-50 '
                f'group-open:bg-gray-50">{escape(title)}</summary>'
                f'<div class="px-4 py-3 text-sm text-gray-600">{content}</div>'
                f'</details>'
            )
        html += '</div>'
        return html

    # ═══ Feedback ══════════════════════════════════════════════════

    @staticmethod
    def Toast(message: str, level: str = "info", duration: int = 3000) -> str:
        colors = {"info": "bg-blue-600", "success": "bg-green-600",
                  "warning": "bg-yellow-500", "error": "bg-red-600"}
        return (
            f'<div class="fixed bottom-4 right-4 z-50 {colors.get(level,colors["info"])} '
            f'text-white px-6 py-3 rounded-lg shadow-lg text-sm animate-slide-up '
            f'onload="setTimeout(()=>this.remove(),{duration})">'
            f'{escape(message)}</div>'
        )

    @staticmethod
    def Skeleton(lines: int = 3, width: str = "full") -> str:
        html = f'<div class="animate-pulse space-y-3 w-{width}">'
        for _ in range(lines):
            html += '<div class="h-4 bg-gray-200 rounded"></div>'
        html += '</div>'
        return html

    # ═══ Composites ════════════════════════════════════════════════

    @staticmethod
    def StatGrid(stats: list[dict]) -> str:
        """stats: [{label, value, change, trend}] trend: up|down|neutral"""
        items = []
        for s in stats:
            trend_icon = {"up": "↑", "down": "↓", "neutral": "→"}.get(s.get("trend",""), "")
            trend_color = {"up": "text-green-600", "down": "text-red-600",
                          "neutral": "text-gray-500"}.get(s.get("trend",""), "")
            items.append(
                f'<div class="bg-white rounded-xl shadow-sm p-4 text-center">'
                f'<div class="text-2xl font-bold text-gray-800">{escape(str(s.get("value","")))}</div>'
                f'<div class="text-xs text-gray-500">{escape(s.get("label",""))}</div>'
                f'{("<div class=\"text-sm mt-1 " + trend_color + "\">" + trend_icon + " " + escape(str(s.get("change",""))) + "</div>") if s.get("change") else ""}'
                f'</div>'
            )
        return f'<div class="grid grid-cols-2 lg:grid-cols-4 gap-4">{"".join(items)}</div>'

    @staticmethod
    def EmptyState(title: str, description: str = "",
                   action_label: str = "", action_url: str = "") -> str:
        html = (
            f'<div class="text-center py-12">'
            f'<div class="text-4xl mb-3">📭</div>'
            f'<h3 class="text-lg font-semibold text-gray-700">{escape(title)}</h3>'
        )
        if description:
            html += f'<p class="text-sm text-gray-500 mt-1">{escape(description)}</p>'
        if action_label and action_url:
            html += (
                f'<a href="{escape(action_url)}" class="inline-block mt-4 px-4 py-2 '
                f'bg-blue-600 text-white rounded-lg text-sm font-medium '
                f'hover:bg-blue-700 transition-colors">{escape(action_label)}</a>'
            )
        html += '</div>'
        return html

    @staticmethod
    def DataFeed(items: list[dict]) -> str:
        """items: [{title, description, time, badge}] — activity feed"""
        html = '<div class="space-y-3">'
        for item in items:
            badge_html = ""
            if item.get("badge"):
                badge_html = (f'<span class="inline-flex px-2 py-0.5 rounded-full '
                             f'text-xs font-medium bg-blue-100 text-blue-700">'
                             f'{escape(item["badge"])}</span>')
            html += (
                f'<div class="flex items-start space-x-3 p-3 bg-white rounded-lg '
                f'shadow-sm">'
                f'<div class="flex-1 min-w-0">'
                f'<p class="text-sm font-medium text-gray-800">{escape(item.get("title",""))}</p>'
                f'<p class="text-xs text-gray-500 mt-0.5">{escape(item.get("description","")[:120])}</p>'
                f'</div>'
                f'<div class="flex flex-col items-end space-y-1 flex-shrink-0">'
                f'<span class="text-xs text-gray-400">{escape(item.get("time",""))}</span>'
                f'{badge_html}'
                f'</div></div>'
            )
        html += '</div>'
        return html

    @staticmethod
    def Stepper(steps: list[str], current: int = 0) -> str:
        html = '<div class="flex items-center">'
        for i, step in enumerate(steps):
            if i > 0:
                color = "bg-blue-600" if i <= current else "bg-gray-300"
                html += f'<div class="flex-1 h-0.5 {color}"></div>'
            circle_color = ("bg-blue-600 text-white" if i <= current
                           else "bg-gray-200 text-gray-500")
            html += (
                f'<div class="flex flex-col items-center flex-shrink-0">'
                f'<div class="w-6 h-6 rounded-full {circle_color} flex items-center '
                f'justify-center text-xs font-medium">{i+1}</div>'
                f'<span class="text-xs mt-1 text-gray-500">{escape(step[:12])}</span>'
                f'</div>'
            )
        html += '</div>'
        return html


# ═══ Singleton ════════════════════════════════════════════════════

_tailwind_ui: Optional[TailwindUI] = None


def get_tailwind_ui() -> TailwindUI:
    global _tailwind_ui
    if _tailwind_ui is None:
        _tailwind_ui = TailwindUI()
    return _tailwind_ui


__all__ = ["TailwindUI", "get_tailwind_ui"]
