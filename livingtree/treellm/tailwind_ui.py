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


# ═══ Singleton ════════════════════════════════════════════════════

_tailwind_ui: Optional[TailwindUI] = None


def get_tailwind_ui() -> TailwindUI:
    global _tailwind_ui
    if _tailwind_ui is None:
        _tailwind_ui = TailwindUI()
    return _tailwind_ui


__all__ = ["TailwindUI", "get_tailwind_ui"]
