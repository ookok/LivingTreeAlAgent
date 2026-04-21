"""
CSS 重写引擎 (CSS Rewriter)
==========================

为任意网站编写"皮肤"，实现视觉主权

功能：
- 域名级别的样式覆盖
- 预设主题（深夜模式、极简版等）
- 实时预览
- 自动应用
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ThemeType(Enum):
    """主题类型"""
    DARK = "dark"             # 深夜模式
    LIGHT = "light"           # 浅色模式
    MINIMAL = "minimal"       # 极简版
    HIGH_CONTRAST = "high_contrast"  # 高对比度
    CUSTOM = "custom"         # 自定义


@dataclass
class CSSRule:
    """CSS 规则"""
    rule_id: str
    domain: str                # 目标域名 (如 "github.com")
    selector: str             # CSS 选择器
    styles: str               # CSS 属性
    theme: ThemeType = ThemeType.CUSTOM
    enabled: bool = True
    priority: int = 0         # 优先级
    created_at: datetime = = field(default_factory=datetime.now)


@dataclass
class Theme:
    """主题"""
    theme_id: str
    name: str
    theme_type: ThemeType
    rules: list[CSSRule]
    enabled: bool = True


class CSSRewriter:
    """
    CSS 重写引擎

    功能：
    1. 管理域名级别的 CSS 覆盖规则
    2. 预设主题（深夜模式等）
    3. 生成要注入的 CSS
    4. 实时预览和编辑
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "css_rewriter"
        self.db_path = self.data_dir / "styles.db"

        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # 预设主题
        self._builtin_themes = self._create_builtin_themes()

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # CSS 规则表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS css_rules (
                rule_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                selector TEXT NOT NULL,
                styles TEXT NOT NULL,
                theme TEXT DEFAULT 'custom',
                enabled INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # 主题表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS themes (
                theme_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                theme_type TEXT NOT NULL,
                enabled INTEGER DEFAULT 1
            )
        """)

        # 域名启用状态
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS domain_settings (
                domain TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                theme_id TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _create_builtin_themes(self) -> dict[ThemeType, Theme]:
        """创建预设主题"""
        themes = {}

        # 深夜模式
        dark_rules = [
            CSSRule(
                rule_id="dark_bg",
                domain="*",
                selector="body, html",
                styles="background-color: #1a1a1a !important; color: #e0e0e0 !important;",
                theme=ThemeType.DARK
            ),
            CSSRule(
                rule_id="dark_links",
                domain="*",
                selector="a",
                styles="color: #6eb5ff !important;",
                theme=ThemeType.DARK
            ),
            CSSRule(
                rule_id="dark_code",
                domain="*",
                selector="code, pre",
                styles="background-color: #2d2d2d !important; color: #f8f8f2 !important;",
                theme=ThemeType.DARK
            ),
        ]
        themes[ThemeType.DARK] = Theme(
            theme_id="builtin_dark",
            name="深夜模式",
            theme_type=ThemeType.DARK,
            rules=dark_rules
        )

        # 极简模式
        minimal_rules = [
            CSSRule(
                rule_id="minimal_hide_sidebar",
                domain="*",
                selector=".sidebar, .side-panel, [class*='sidebar']",
                styles="display: none !important;",
                theme=ThemeType.MINIMAL
            ),
            CSSRule(
                rule_id="minimal_hide_footer",
                domain="*",
                selector="footer, .footer",
                styles="display: none !important;",
                theme=ThemeType.MINIMAL
            ),
            CSSRule(
                rule_id="minimal_hide_ads",
                domain="*",
                selector="[class*='ad'], [id*='ad'], [class*='advert'], .ads",
                styles="display: none !important;",
                theme=ThemeType.MINIMAL
            ),
        ]
        themes[ThemeType.MINIMAL] = Theme(
            theme_id="builtin_minimal",
            name="极简模式",
            theme_type=ThemeType.MINIMAL,
            rules=minimal_rules
        )

        return themes

    def add_rule(
        self,
        domain: str,
        selector: str,
        styles: str,
        theme: ThemeType = ThemeType.CUSTOM,
        enabled: bool = True
    ) -> str:
        """添加 CSS 规则"""
        rule_id = str(uuid.uuid4())[:12]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO css_rules
            (rule_id, domain, selector, styles, theme, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            rule_id,
            domain,
            selector,
            styles,
            theme.value,
            1 if enabled else 0,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        return rule_id

    def get_rules_for_domain(self, domain: str) -> list[CSSRule]:
        """获取域名的 CSS 规则"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取通用规则和域名特定规则
        cursor.execute("""
            SELECT rule_id, domain, selector, styles, theme, enabled, priority, created_at
            FROM css_rules
            WHERE (domain = ? OR domain = '*') AND enabled = 1
            ORDER BY priority DESC, created_at ASC
        """, (domain,))

        rows = cursor.fetchall()
        conn.close()

        rules = []
        for row in rows:
            rules.append(CSSRule(
                rule_id=row[0],
                domain=row[1],
                selector=row[2],
                styles=row[3],
                theme=ThemeType(row[4]),
                enabled=bool(row[5]),
                priority=row[6],
                created_at=datetime.fromisoformat(row[7])
            ))

        return rules

    def generate_css_for_domain(self, domain: str) -> str:
        """
        为域名生成 CSS

        Returns:
            要注入的 CSS 代码
        """
        rules = self.get_rules_for_domain(domain)

        css_parts = []
        for rule in rules:
            # 包装在域名特定的选择器中
            if rule.domain == "*":
                css_parts.append(f"{rule.selector} {{ {rule.styles} }}")
            else:
                css_parts.append(f"{rule.selector} {{ {rule.styles} }}")

        if not css_parts:
            return ""

        return f"""
/* HyperOS CSS Rewriter - Domain: {domain} */
<style id="hyperos-css-rewriter">
{chr(10).join(css_parts)}
</style>
"""

    def apply_builtin_theme(
        self,
        domain: str,
        theme_type: ThemeType
    ) -> bool:
        """应用预设主题到域名"""
        if theme_type not in self._builtin_themes:
            return False

        theme = self._builtin_themes[theme_type]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for rule in theme.rules:
            # 使用通用域名（*）的规则
            # 复制规则到数据库
            rule_id = str(uuid.uuid4())[:12]
            cursor.execute("""
                INSERT INTO css_rules
                (rule_id, domain, selector, styles, theme, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (
                rule_id,
                "*",  # 通用规则
                rule.selector,
                rule.styles,
                theme_type.value,
                datetime.now().isoformat()
            ))

        conn.commit()
        conn.close()

        # 记录域名使用的主题
        self._set_domain_theme(domain, theme_type)

        return True

    def _set_domain_theme(self, domain: str, theme_type: ThemeType):
        """设置域名的默认主题"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 如果已有，使用 builtin_ 前缀
        theme_id = f"builtin_{theme_type.value}"

        cursor.execute("""
            INSERT OR REPLACE INTO domain_settings
            (domain, theme_id, enabled)
            VALUES (?, ?, 1)
        """, (domain, theme_id))

        conn.commit()
        conn.close()

    def get_injection_script(self, domain: str) -> str:
        """
        生成注入脚本

        Returns:
            要注入到网页的 JavaScript 代码
        """
        css = self.generate_css_for_domain(domain)

        if not css:
            return ""

        return f"""
(function() {{
    // HyperOS CSS Rewriter Injection
    const css = `{css}`;

    // 创建或更新样式元素
    let styleEl = document.getElementById("hyperos-css-rewriter");
    if (!styleEl) {{
        styleEl = document.createElement("div");
        styleEl.id = "hyperos-css-rewriter";
        document.head.appendChild(styleEl);
    }}

    // 直接注入 HTML（包含 style 标签）
    styleEl.innerHTML = css;

    console.log("[HyperOS] CSS Rewriter applied for:", "{domain}");
}})();
"""

    def list_rules(self, domain: Optional[str] = None) -> list[dict[str, Any]]:
        """列出 CSS 规则"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if domain:
            cursor.execute("""
                SELECT rule_id, domain, selector, styles, theme, enabled, priority, created_at
                FROM css_rules WHERE domain = ? OR domain = '*'
                ORDER BY domain, priority DESC
            """, (domain,))
        else:
            cursor.execute("""
                SELECT rule_id, domain, selector, styles, theme, enabled, priority, created_at
                FROM css_rules
                ORDER BY domain, priority DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "rule_id": row[0],
                "domain": row[1],
                "selector": row[2],
                "styles": row[3],
                "theme": row[4],
                "enabled": bool(row[5]),
                "priority": row[6],
                "created_at": row[7]
            }
            for row in rows
        ]


def create_css_rewriter(data_dir: Path) -> CSSRewriter:
    """创建 CSS 重写引擎"""
    return CSSRewriter(data_dir=data_dir)