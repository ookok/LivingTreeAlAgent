# landing_page.py — 永久静态页生成器

import json
from pathlib import Path
from typing import Optional, Dict, Any

from .models import LandingPageConfig


class LandingPageGenerator:
    """
    静态落地页生成器

    功能：
    1. 生成纯静态 HTML 页面（GitHub Pages / Cloudflare Pages / Vercel 兼容）
    2. 三大卖点区块
    3. 多端下载按钮
    4. 二维码占位
    5. 归因参数透传
    """

    def __init__(
        self,
        config: LandingPageConfig = None,
        output_dir: Path = None,
    ):
        """
        初始化落地页生成器

        Args:
            config: 落地页配置
            output_dir: 输出目录
        """
        self._config = config or LandingPageConfig()
        self._output_dir = output_dir or self._default_output_dir()
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _default_output_dir(self) -> Path:
        """默认输出目录"""
        return Path.home() / ".hermes-desktop" / "promotion" / "landing_pages"

    def generate(
        self,
        attribution_id: Optional[str] = None,
        output_file: str = "index.html",
    ) -> str:
        """
        生成静态落地页

        Args:
            attribution_id: 归因ID（用于追踪）
            output_file: 输出文件名

        Returns:
            str: 生成的文件路径
        """
        html = self._build_html(attribution_id)
        output_path = self._output_dir / output_file
        output_path.write_text(html, encoding="utf-8")
        return str(output_path)

    def _build_html(self, attribution_id: Optional[str]) -> str:
        """构建完整HTML"""
        config = self._config

        # 构建URL
        base_download = config.download_links.get("windows", "")
        if attribution_id:
            base_download = f"{base_download}?ref={attribution_id}"

        # 卖点区块HTML
        selling_points_html = self._build_selling_points()

        # 下载按钮HTML
        download_buttons_html = self._build_download_buttons(base_download)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config.product_name} — {config.tagline}</title>
    <meta name="description" content="{config.description}">

    <!-- Open Graph -->
    <meta property="og:title" content="{config.product_name}">
    <meta property="og:description" content="{config.description}">
    <meta property="og:type" content="website">

    <!-- Theme Color -->
    <meta name="theme-color" content="{config.theme_color}">

    <style>
        /* CSS Reset & Base */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --theme: {config.theme_color};
            --accent: {config.accent_color};
            --text: #1a1a1a;
            --text-secondary: #666;
            --bg: #f8faf8;
            --card-bg: #ffffff;
            --radius: 16px;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* Container */
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 0 20px;
        }}

        /* Header */
        .header {{
            text-align: center;
            padding: 80px 0 60px;
        }}

        .logo {{
            font-size: 64px;
            margin-bottom: 20px;
        }}

        .header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--theme);
            margin-bottom: 12px;
        }}

        .header .tagline {{
            font-size: 1.25rem;
            color: var(--text-secondary);
            margin-bottom: 24px;
        }}

        .header .description {{
            max-width: 600px;
            margin: 0 auto 32px;
            color: var(--text-secondary);
        }}

        /* Download Buttons */
        .download-buttons {{
            display: flex;
            gap: 16px;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 24px;
        }}

        .download-btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 14px 28px;
            border-radius: 50px;
            font-size: 1rem;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
        }}

        .download-btn.primary {{
            background: var(--theme);
            color: white;
        }}

        .download-btn.primary:hover {{
            background: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(46, 125, 50, 0.3);
        }}

        .download-btn.secondary {{
            background: var(--card-bg);
            color: var(--text);
            border: 2px solid #e0e0e0;
        }}

        .download-btn.secondary:hover {{
            border-color: var(--theme);
            color: var(--theme);
        }}

        .download-btn .icon {{
            font-size: 1.2em;
        }}

        /* QR Code Placeholder */
        .qr-section {{
            text-align: center;
            margin-top: 40px;
        }}

        .qr-placeholder {{
            display: inline-block;
            width: 120px;
            height: 120px;
            background: #f0f0f0;
            border-radius: 12px;
            line-height: 120px;
            color: #999;
            font-size: 12px;
        }}

        .qr-section p {{
            margin-top: 12px;
            color: var(--text-secondary);
            font-size: 14px;
        }}

        /* Divider */
        .divider {{
            height: 1px;
            background: linear-gradient(to right, transparent, #e0e0e0, transparent);
            margin: 60px 0;
        }}

        /* Selling Points */
        .selling-points {{
            padding: 40px 0 80px;
        }}

        .selling-points h2 {{
            text-align: center;
            font-size: 2rem;
            margin-bottom: 48px;
            color: var(--text);
        }}

        .points-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 24px;
        }}

        .point-card {{
            background: var(--card-bg);
            border-radius: var(--radius);
            padding: 32px 24px;
            text-align: center;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .point-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}

        .point-icon {{
            font-size: 48px;
            margin-bottom: 16px;
        }}

        .point-card h3 {{
            font-size: 1.25rem;
            color: var(--theme);
            margin-bottom: 12px;
        }}

        .point-card p {{
            color: var(--text-secondary);
            margin-bottom: 16px;
        }}

        .point-highlight {{
            display: inline-block;
            padding: 4px 12px;
            background: rgba(46, 125, 50, 0.1);
            color: var(--theme);
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 40px 0;
            color: var(--text-secondary);
            font-size: 14px;
            border-top: 1px solid #e0e0e0;
        }}

        .footer a {{
            color: var(--theme);
            text-decoration: none;
        }}

        /* Animations */
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .header {{ animation: fadeInUp 0.6s ease-out; }}
        .download-buttons {{ animation: fadeInUp 0.6s ease-out 0.1s both; }}
        .qr-section {{ animation: fadeInUp 0.6s ease-out 0.2s both; }}
        .point-card:nth-child(1) {{ animation: fadeInUp 0.5s ease-out 0.1s both; }}
        .point-card:nth-child(2) {{ animation: fadeInUp 0.5s ease-out 0.2s both; }}
        .point-card:nth-child(3) {{ animation: fadeInUp 0.5s ease-out 0.3s both; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="logo">🌿</div>
            <h1>{config.product_name}</h1>
            <p class="tagline">{config.tagline}</p>
            <p class="description">{config.description}</p>

            <!-- Download Buttons -->
            <div class="download-buttons">
                <a href="{config.download_links.get('windows', '#')}" class="download-btn primary">
                    <span class="icon">🪟</span> Windows
                </a>
                <a href="{config.download_links.get('macos', '#')}" class="download-btn secondary">
                    <span class="icon">🍎</span> macOS
                </a>
                <a href="{config.download_links.get('linux', '#')}" class="download-btn secondary">
                    <span class="icon">🐧</span> Linux
                </a>
            </div>

            <!-- QR Code -->
            <div class="qr-section">
                <div class="qr-placeholder">QR Code</div>
                <p>扫码手机访问 · 轻量化体验</p>
            </div>
        </header>

        <div class="divider"></div>

        <!-- Selling Points -->
        <section class="selling-points">
            <h2>为什么选择 Living Tree？</h2>
            <div class="points-grid">
                {selling_points_html}
            </div>
        </section>

        <!-- Footer -->
        <footer class="footer">
            <p>
                <a href="https://github.com/LivingTreeAI/hermes-desktop" target="_blank">GitHub</a>
                · <a href="https://dl.living-tree.ai/docs" target="_blank">文档</a>
                · <a href="https://dl.living-tree.ai/privacy" target="_blank">隐私政策</a>
            </p>
            <p style="margin-top: 8px;">
                © 2024 Living Tree AI · 开源免费 · 尊重隐私
            </p>
        </footer>
    </div>
</body>
</html>"""

        return html

    def _build_selling_points(self) -> str:
        """构建卖点区块HTML"""
        points_html = []
        for point in self._config.selling_points:
            html = f"""
                <div class="point-card">
                    <div class="point-icon">{point['icon']}</div>
                    <h3>{point['title']}</h3>
                    <p>{point['description']}</p>
                    <span class="point-highlight">{point['highlight']}</span>
                </div>"""
            points_html.append(html)
        return "".join(points_html)

    def _build_download_buttons(self, base_url: str) -> str:
        """构建下载按钮HTML"""
        buttons = []
        platforms = [
            ("windows", "🪟", "Windows"),
            ("macos", "🍎", "macOS"),
            ("linux", "🐧", "Linux"),
        ]
        for key, icon, name in platforms:
            url = self._config.download_links.get(key, base_url)
            buttons.append(
                f'<a href="{url}" class="download-btn secondary">'
                f'<span class="icon">{icon}</span> {name}</a>'
            )
        return "".join(buttons)

    def generate_and_save(
        self,
        attribution_id: Optional[str] = None,
        filename: str = None,
    ) -> str:
        """
        生成并保存到文件

        Args:
            attribution_id: 归因ID
            filename: 文件名，None则自动生成

        Returns:
            str: 文件路径
        """
        if filename is None:
            if attribution_id:
                filename = f"{attribution_id}.html"
            else:
                filename = "index.html"

        return self.generate(attribution_id, filename)

    def get_page_url(self, attribution_id: Optional[str] = None) -> str:
        """
        获取落地页URL

        Args:
            attribution_id: 归因ID

        Returns:
            str: 落地页完整URL
        """
        base = f"https://{self._config.base_domain}/index.html"
        if attribution_id:
            return f"{base}?ref={attribution_id}"
        return base


# 全局单例
_generator_instance: Optional[LandingPageGenerator] = None


def get_landing_page_generator() -> LandingPageGenerator:
    """获取落地页生成器全局实例"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = LandingPageGenerator()
    return _generator_instance
