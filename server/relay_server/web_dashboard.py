# relay_server/web_dashboard.py — 项目首页 + 管理控制台
# =================================================================
# 生成两个页面:
# 1. index.html - 项目首页（架构图、功能介绍、安装脚本）
# 2. admin.html - 管理控制台（数据监控、配置管理）
# =================================================================

from pathlib import Path
import json

# =================================================================
# 项目首页 HTML
# =================================================================

def generate_landing_html() -> str:
    """生成项目首页"""

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LivingTreeAI — 生命之树 AI 桌面应用</title>
    <style>
        :root {
            --primary: #1a5f2a;
            --primary-light: #2e8b3d;
            --primary-dark: #0d3d18;
            --bg: #f8faf9;
            --card: #ffffff;
            --text: #1a1a1a;
            --text-secondary: #555;
            --border: #e0e0e0;
            --accent: #f59e0b;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }

        /* Hero Section */
        .hero {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 50%, var(--primary-dark) 100%);
            color: white;
            padding: 60px 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .hero::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M30 5 L35 25 L55 30 L35 35 L30 55 L25 35 L5 30 L25 25 Z' fill='rgba(255,255,255,0.05)'/%3E%3C/svg%3E");
            opacity: 0.5;
        }

        .hero-content { position: relative; max-width: 900px; margin: 0 auto; }

        .hero h1 {
            font-size: 2.8rem;
            font-weight: 700;
            margin-bottom: 16px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }

        .hero .tree-icon { font-size: 4rem; margin-bottom: 20px; }

        .hero p {
            font-size: 1.2rem;
            opacity: 0.95;
            max-width: 600px;
            margin: 0 auto 30px;
        }

        .hero-badges {
            display: flex;
            gap: 16px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .badge {
            background: rgba(255,255,255,0.15);
            padding: 8px 20px;
            border-radius: 50px;
            font-size: 0.9rem;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }

        /* Container */
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        /* Architecture Section */
        .section {
            margin-bottom: 50px;
        }

        .section-title {
            font-size: 1.8rem;
            color: var(--primary);
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .section-title::before {
            content: '';
            width: 4px;
            height: 32px;
            background: var(--primary);
            border-radius: 2px;
        }

        /* Architecture Diagram */
        .arch-diagram {
            background: var(--card);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            overflow-x: auto;
        }

        .arch-svg {
            width: 100%;
            max-width: 900px;
            margin: 0 auto;
            display: block;
        }

        /* Feature Cards */
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }

        .feature-card {
            background: var(--card);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            border-left: 4px solid var(--primary);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .feature-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.1);
        }

        .feature-card h3 {
            color: var(--primary);
            margin-bottom: 12px;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .feature-card p {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        /* Download Section */
        .download-section {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 16px;
            padding: 40px;
            color: white;
        }

        .download-section h2 {
            font-size: 1.6rem;
            margin-bottom: 24px;
            text-align: center;
        }

        .download-buttons {
            display: flex;
            gap: 20px;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 30px;
        }

        .download-btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 14px 28px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.2s;
        }

        .download-btn.primary {
            background: var(--primary-light);
            color: white;
        }

        .download-btn.primary:hover { background: var(--primary); }

        .download-btn.secondary {
            background: rgba(255,255,255,0.1);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
        }

        .download-btn.secondary:hover { background: rgba(255,255,255,0.2); }

        /* Install Scripts */
        .install-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
            justify-content: center;
        }

        .install-tab {
            padding: 10px 24px;
            border: none;
            background: rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.7);
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }

        .install-tab.active {
            background: white;
            color: var(--primary);
        }

        .install-code {
            background: #0d0d0d;
            border-radius: 10px;
            padding: 20px;
            font-family: 'SF Mono', 'Fira Code', Consolas, monospace;
            font-size: 0.85rem;
            overflow-x: auto;
            white-space: pre;
            line-height: 1.8;
            max-height: 300px;
            overflow-y: auto;
        }

        .install-code .comment { color: #6a9955; }
        .install-code .command { color: #dcdcaa; }
        .install-code .string { color: #ce9178; }
        .install-code .keyword { color: #569cd6; }

        /* Footer */
        .footer {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-secondary);
            font-size: 0.85rem;
            border-top: 1px solid var(--border);
            margin-top: 40px;
        }

        .footer-links {
            display: flex;
            gap: 24px;
            justify-content: center;
            margin-bottom: 16px;
        }

        .footer-links a {
            color: var(--primary);
            text-decoration: none;
        }

        .footer-links a:hover { text-decoration: underline; }

        /* Admin Link */
        .admin-link {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--primary);
            color: white;
            padding: 12px 20px;
            border-radius: 50px;
            text-decoration: none;
            font-size: 0.9rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            transition: all 0.2s;
        }

        .admin-link:hover {
            background: var(--primary-light);
            transform: translateY(-2px);
        }

        /* Tech Stack */
        .tech-stack {
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 16px;
        }

        .tech-badge {
            background: #f0f0f0;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        /* Responsive */
        @media (max-width: 768px) {
            .hero h1 { font-size: 2rem; }
            .hero p { font-size: 1rem; }
            .section-title { font-size: 1.4rem; }
        }
    </style>
</head>
<body>
    <!-- Hero -->
    <section class="hero">
        <div class="hero-content">
            <div class="tree-icon">🌲</div>
            <h1>Hermes Desktop</h1>
            <p>智能进化桌面助手 — 基于本地大模型的编程伴侣，支持知识林地、装配园、技能市场，让 AI 成为真正的创作搭档</p>
            <div class="hero-badges">
                <span class="badge">🎓 知识管理</span>
                <span class="badge">🛠️ 技能市场</span>
                <span class="badge">🌐 中继服务</span>
                <span class="badge">📦 跨平台</span>
            </div>
        </div>
    </section>

    <div class="container">
        <!-- Architecture -->
        <section class="section">
            <h2 class="section-title">🏛️ 系统架构</h2>
            <div class="arch-diagram">
                <svg class="arch-svg" viewBox="0 0 900 400" xmlns="http://www.w3.org/2000/svg">
                    <!-- Background Grid -->
                    <defs>
                        <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#e8e8e8" stroke-width="0.5"/>
                        </pattern>
                        <linearGradient id="primaryGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#1a5f2a"/>
                            <stop offset="100%" style="stop-color:#2e8b3d"/>
                        </linearGradient>
                        <linearGradient id="clientGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#3b82f6"/>
                            <stop offset="100%" style="stop-color:#1d4ed8"/>
                        </linearGradient>
                        <linearGradient id="serverGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" style="stop-color:#f59e0b"/>
                            <stop offset="100%" style="stop-color:#d97706"/>
                        </linearGradient>
                    </defs>
                    <rect width="900" height="400" fill="url(#grid)"/>

                    <!-- Client Layer -->
                    <rect x="30" y="30" width="380" height="340" rx="12" fill="#eff6ff" stroke="#3b82f6" stroke-width="2"/>
                    <text x="220" y="55" text-anchor="middle" font-size="14" font-weight="600" fill="#1d4ed8">🦉 客户端 Client</text>

                    <!-- Client Components -->
                    <rect x="50" y="75" width="160" height="70" rx="8" fill="white" stroke="#3b82f6" stroke-width="1"/>
                    <text x="130" y="98" text-anchor="middle" font-size="11" fill="#1d4ed8">🖥️ PyQt6 界面层</text>
                    <text x="130" y="115" text-anchor="middle" font-size="9" fill="#666">桌面 UI / 面板管理</text>
                    <text x="130" y="130" text-anchor="middle" font-size="9" fill="#666">任务进度 / 系统托盘</text>

                    <rect x="230" y="75" width="160" height="70" rx="8" fill="white" stroke="#3b82f6" stroke-width="1"/>
                    <text x="310" y="98" text-anchor="middle" font-size="11" fill="#1d4ed8">🧠 系统大脑</text>
                    <text x="310" y="115" text-anchor="middle" font-size="9" fill="#666">本地 LLM / 推理引擎</text>
                    <text x="310" y="130" text-anchor="middle" font-size="9" fill="#666">Ollama / GPT4All</text>

                    <rect x="50" y="160" width="160" height="70" rx="8" fill="white" stroke="#3b82f6" stroke-width="1"/>
                    <text x="130" y="183" text-anchor="middle" font-size="11" fill="#1d4ed8">🌱 装配园</text>
                    <text x="130" y="200" text-anchor="middle" font-size="9" fill="#666">知识孵化 / 技能生成</text>
                    <text x="130" y="215" text-anchor="middle" font-size="9" fill="#666">Soil Sowing / Skill Grafting</text>

                    <rect x="230" y="160" width="160" height="70" rx="8" fill="white" stroke="#3b82f6" stroke-width="1"/>
                    <text x="310" y="183" text-anchor="middle" font-size="11" fill="#1d4ed8">🌲 知识林地</text>
                    <text x="310" y="200" text-anchor="middle" font-size="9" fill="#666">行业知识库 / Wiki 渲染</text>
                    <text x="310" y="215" text-anchor="middle" font-size="9" fill="#666">LTKG 导入导出</text>

                    <rect x="50" y="245" width="160" height="70" rx="8" fill="white" stroke="#3b82f6" stroke-width="1"/>
                    <text x="130" y="268" text-anchor="middle" font-size="11" fill="#1d4ed8">📦 Skill Market</text>
                    <text x="130" y="285" text-anchor="middle" font-size="9" fill="#666">技能市场 / 技能安装</text>
                    <text x="130" y="300" text-anchor="middle" font-size="9" fill="#666">SKILL.md Manifest</text>

                    <rect x="230" y="245" width="160" height="70" rx="8" fill="white" stroke="#3b82f6" stroke-width="1"/>
                    <text x="310" y="268" text-anchor="middle" font-size="11" fill="#1d4ed8">🔧 MCP Manager</text>
                    <text x="310" y="285" text-anchor="middle" font-size="9" fill="#666">MCP 服务器管理</text>
                    <text x="310" y="300" text-anchor="middle" font-size="9" fill="#666">订阅 / 发布架构</text>

                    <!-- Arrow -->
                    <path d="M 420 200 L 460 200" stroke="#1a5f2a" stroke-width="3" fill="none" marker-end="url(#arrowhead)"/>
                    <defs>
                        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill="#1a5f2a"/>
                        </marker>
                    </defs>

                    <!-- Relay Server -->
                    <rect x="490" y="100" width="380" height="200" rx="12" fill="#fffbeb" stroke="#f59e0b" stroke-width="2"/>
                    <text x="680" y="125" text-anchor="middle" font-size="14" font-weight="600" fill="#d97706">🌐 中继服务器 Relay Server</text>

                    <rect x="510" y="145" width="160" height="60" rx="8" fill="white" stroke="#f59e0b" stroke-width="1"/>
                    <text x="590" y="168" text-anchor="middle" font-size="11" fill="#d97706">📊 数据收集</text>
                    <text x="590" y="183" text-anchor="middle" font-size="9" fill="#666">周报聚合 / 趋势分析</text>
                    <text x="590" y="195" text-anchor="middle" font-size="9" fill="#666">模块热度统计</text>

                    <rect x="690" y="145" width="160" height="60" rx="8" fill="white" stroke="#f59e0b" stroke-width="1"/>
                    <text x="770" y="168" text-anchor="middle" font-size="11" fill="#d97706">⚙️ 参数分发</text>
                    <text x="770" y="183" text-anchor="middle" font-size="9" fill="#666">超时配置 / 重试策略</text>
                    <text x="770" y="195" text-anchor="middle" font-size="9" fill="#666">批处理参数</text>

                    <rect x="510" y="220" width="340" height="60" rx="8" fill="white" stroke="#f59e0b" stroke-width="1"/>
                    <text x="680" y="243" text-anchor="middle" font-size="11" fill="#d97706">🌐 Web 管理界面</text>
                    <text x="680" y="260" text-anchor="middle" font-size="9" fill="#666">纯静态 HTML / 无 PyQt 依赖 / 响应式布局</text>
                    <text x="680" y="272" text-anchor="middle" font-size="9" fill="#666">数据监控 / 配置管理 / 一键部署</text>

                    <!-- Bottom Labels -->
                    <text x="220" y="380" text-anchor="middle" font-size="11" fill="#666">离线独立运行 | 本地优先 | 无服务器依赖</text>
                    <text x="680" y="380" text-anchor="middle" font-size="11" fill="#666">可选组件 | 轻量中继 | 支持关机</text>
                </svg>
            </div>
        </section>

        <!-- Features -->
        <section class="section">
            <h2 class="section-title">✨ 核心功能</h2>
            <div class="feature-grid">
                <div class="feature-card">
                    <h3>🧠 本地大模型</h3>
                    <p>支持 Ollama、GPT4All、ModelScope 等本地模型，无需联网，数据完全私密。支持 Qwen、LLM-Research 等 GGUF 模型。</p>
                </div>
                <div class="feature-card">
                    <h3>🌱 装配园 Assembly Garden</h3>
                    <p>自动化知识与技能生成管线。从代码库、文档、博客中提取知识，自动生成可执行的 Skill，并沉淀到知识林地。</p>
                </div>
                <div class="feature-card">
                    <h3>🌲 知识林地 Knowledge Grove</h3>
                    <p>行业化知识管理，按电子/硬件/软件等12个行业分类。支持伪域名路由、Wiki渲染、LTKG包导入导出。</p>
                </div>
                <div class="feature-card">
                    <h3>📦 技能市场 Skill Market</h3>
                    <p>基于 SKILL.md Manifest 的技能分发系统。技能即插即用，支持版本管理、依赖解析、自动安装。</p>
                </div>
                <div class="feature-card">
                    <h3>🔧 MCP 管理器</h3>
                    <p>支持 Model Context Protocol 的订阅/发布架构。连接外部工具和服务，扩展 AI 能力边界。</p>
                </div>
                <div class="feature-card">
                    <h3>🌐 轻量中继</h3>
                    <p>可选的 Relay Server 用于数据聚合和参数分发。客户端完全解耦，服务器可随时关闭，不影响本地功能。</p>
                </div>
            </div>
        </section>

        <!-- Download -->
        <section class="section">
            <h2 class="section-title">📥 下载安装</h2>
            <div class="download-section">
                <h2>🚀 一键部署</h2>
                <div class="download-buttons">
                    <a href="https://github.com/your-repo/hermes-desktop" class="download-btn primary" target="_blank">
                        <span>🐙</span> GitHub 源码
                    </a>
                    <a href="#install" class="download-btn secondary">
                        <span>📜</span> 查看安装脚本
                    </a>
                </div>

                <div class="tech-stack">
                    <span class="tech-badge">Python 3.11+</span>
                    <span class="tech-badge">PyQt6</span>
                    <span class="tech-badge">FastAPI</span>
                    <span class="tech-badge">SQLite</span>
                    <span class="tech-badge">Ollama</span>
                    <span class="tech-badge">llama-cpp-python</span>
                </div>

                <!-- Install Scripts -->
                <div id="install" style="margin-top: 40px;">
                    <h3 style="text-align: center; margin-bottom: 20px; font-size: 1.2rem;">安装脚本</h3>

                    <div class="install-tabs">
                        <button class="install-tab active" onclick="showScript('linux')">🐧 Linux</button>
                        <button class="install-tab" onclick="showScript('windows')">🪟 Windows</button>
                    </div>

                    <div class="install-code" id="installScript">
<span class="comment"># Linux 一键部署 (Ubuntu/Debian)</span>
<span class="command">curl -fsSL https://raw.githubusercontent.com/your-repo/hermes-desktop/main/deploy.sh | bash</span>

<span class="comment"># 或下载后执行</span>
<span class="command">chmod +x deploy.sh</span>
<span class="command">./deploy.sh install</span>

<span class="comment"># 管理命令</span>
<span class="command">sudo systemctl start hermes-relay   </span>  <span class="comment"># 启动服务</span>
<span class="command">sudo systemctl enable hermes-relay  </span>  <span class="comment"># 开机自启</span>
<span class="command">sudo systemctl status hermes-relay  </span>  <span class="comment"># 查看状态</span>

<span class="comment"># 访问 Web 管理界面</span>
<span class="string">http://your-server:8766/web</span></div>
                </div>
            </div>
        </section>

        <!-- Architecture Description -->
        <section class="section">
            <h2 class="section-title">📖 系统说明</h2>
            <div class="feature-card" style="border-left-color: #3b82f6;">
                <h3>🎯 设计理念</h3>
                <p><strong>离线优先</strong> — 核心功能不依赖服务器，关闭服务器不影响本地使用。<br>
                <strong>轻量中继</strong> — Relay Server 只做数据聚合和参数分发，不承担业务逻辑。<br>
                <strong>知识可迁徙</strong> — 知识以 LTKG 包格式存储，可跨设备、跨节点分享。</p>
            </div>
            <div style="margin-top: 16px;" class="feature-card" style="border-left-color: #f59e0b;">
                <h3>🏗️ 分层架构</h3>
                <p><strong>客户端</strong>：PyQt6 界面层 + 本地 LLM 推理 + 知识管理 + 技能市场<br>
                <strong>中继层</strong>：FastAPI 服务 + 静态 Web + SQLite 存储<br>
                <strong>网络层</strong>：支持 TCP/WebSocket/HTTP 多协议，可 NAT 穿透</p>
            </div>
        </section>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <div class="footer-links">
            <a href="https://github.com/your-repo/hermes-desktop" target="_blank">🐙 GitHub</a>
            <a href="/web">📊 管理控制台</a>
            <a href="/api/health">🔧 API 状态</a>
        </div>
        <p>Hermes Desktop v2.0 · 智能进化桌面助手</p>
        <p style="margin-top: 8px; opacity: 0.7;">基于 PyQt6 + Ollama + FastAPI 构建</p>
    </footer>

    <!-- Admin Link -->
    <a href="/web" class="admin-link">📊 管理控制台 →</a>

    <script>
        function showScript(platform) {
            const tabs = document.querySelectorAll('.install-tab');
            const code = document.getElementById('installScript');

            tabs.forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');

            if (platform === 'linux') {
                code.innerHTML = `<span class="comment"># Linux 一键部署 (Ubuntu/Debian)</span>
<span class="command">curl -fsSL https://raw.githubusercontent.com/your-repo/hermes-desktop/main/deploy.sh | bash</span>

<span class="comment"># 或下载后执行</span>
<span class="command">chmod +x deploy.sh</span>
<span class="command">./deploy.sh install</span>

<span class="comment"># 管理命令</span>
<span class="command">sudo systemctl start hermes-relay   </span>  <span class="comment"># 启动服务</span>
<span class="command">sudo systemctl enable hermes-relay  </span>  <span class="comment"># 开机自启</span>
<span class="command">sudo systemctl status hermes-relay  </span>  <span class="comment"># 查看状态</span>

<span class="comment"># 访问 Web 管理界面</span>
<span class="string">http://your-server:8766/web</span>`;
            } else {
                code.innerHTML = `<span class="comment"># Windows 一键部署</span>
<span class="comment"># 1. 克隆或下载项目</span>
<span class="command">git clone https://github.com/your-repo/hermes-desktop.git</span>
<span class="command">cd hermes-desktop</span>

<span class="comment"># 2. 运行客户端</span>
<span class="command">run.bat</span>

<span class="comment"># 3. 安装中继服务 (需要管理员)</span>
<span class="command">run.bat install</span>

<span class="comment"># 4. 启动中继服务器</span>
<span class="command">run.bat relay</span>

<span class="comment"># 访问 Web 管理界面</span>
<span class="string">http://localhost:8766/web</span>`;
            }
        }
    </script>
</body>
</html>"""


# =================================================================
# 管理控制台 HTML
# =================================================================

def generate_admin_html() -> str:
    """生成管理控制台 HTML"""

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes Relay — 管理控制台</title>
    <style>
        :root {
            --theme: #1a5f2a;
            --accent: #2e8b3d;
            --bg: #f5f5f5;
            --card: #ffffff;
            --text: #1a1a1a;
            --text-secondary: #666;
            --border: #e0e0e0;
            --danger: #e53935;
            --success: #43a047;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .header {
            background: linear-gradient(135deg, var(--theme) 0%, var(--accent) 100%);
            color: white;
            padding: 20px 32px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.15);
        }

        .header h1 { font-size: 1.3rem; font-weight: 600; }
        .header p { opacity: 0.85; font-size: 0.8rem; margin-top: 4px; }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255,255,255,0.2);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            margin-top: 10px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4caf50;
        }

        .status-dot.offline { background: #e53935; }

        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 24px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }

        .stat-card {
            background: var(--card);
            border-radius: 10px;
            padding: 18px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border-left: 3px solid var(--theme);
        }

        .stat-card .label { color: var(--text-secondary); font-size: 0.75rem; margin-bottom: 6px; }
        .stat-card .value { font-size: 1.8rem; font-weight: 700; color: var(--theme); }
        .stat-card .sub { font-size: 0.7rem; color: var(--text-secondary); margin-top: 4px; }

        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 20px;
            background: var(--card);
            padding: 4px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }

        .tab {
            flex: 1;
            padding: 10px 16px;
            border: none;
            background: transparent;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            color: var(--text-secondary);
            transition: all 0.2s;
        }

        .tab:hover { background: rgba(46, 139, 61, 0.1); }
        .tab.active { background: var(--theme); color: white; }

        .panel {
            background: var(--card);
            border-radius: 12px;
            padding: 22px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            display: none;
        }

        .panel.active { display: block; }
        .panel h2 { font-size: 1rem; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }

        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 10px 6px; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
        th { color: var(--text-secondary); font-weight: 500; font-size: 0.75rem; }
        tr:hover { background: #f8f8f8; }

        .badge { display: inline-block; padding: 2px 7px; border-radius: 10px; font-size: 0.65rem; font-weight: 500; }
        .badge.hot { background: #ffebee; color: #c62828; }

        .week-selector { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }

        .week-btn {
            padding: 5px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: white;
            cursor: pointer;
            font-size: 0.75rem;
            transition: all 0.2s;
        }

        .week-btn:hover { border-color: var(--theme); color: var(--theme); }
        .week-btn.active { background: var(--theme); color: white; border-color: var(--theme); }

        .config-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }

        .config-item { background: #f9f9f9; padding: 14px; border-radius: 8px; }
        .config-item label { display: block; font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 5px; }
        .config-item input { width: 100%; padding: 7px 10px; border: 1px solid var(--border); border-radius: 5px; font-size: 0.85rem; }
        .config-item input:focus { outline: none; border-color: var(--theme); }

        .btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.8rem; transition: all 0.2s; }
        .btn-primary { background: var(--theme); color: white; }
        .btn-primary:hover { background: var(--accent); }
        .btn-danger { background: var(--danger); color: white; }

        .alert { padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; font-size: 0.8rem; }
        .alert-success { background: #e8f5e9; color: #2e7d32; }
        .alert-error { background: #ffebee; color: #c62828; }

        .loading { text-align: center; padding: 30px; color: var(--text-secondary); font-size: 0.85rem; }
        .loading::after { content: ''; display: inline-block; width: 14px; height: 14px; border: 2px solid var(--border); border-top-color: var(--theme); border-radius: 50%; animation: spin 1s linear infinite; margin-left: 8px; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .empty { text-align: center; padding: 30px; color: var(--text-secondary); font-size: 0.85rem; }

        .footer { text-align: center; padding: 20px; color: var(--text-secondary); font-size: 0.75rem; margin-top: 30px; }

        .back-link { display: inline-block; margin-bottom: 16px; color: var(--theme); text-decoration: none; font-size: 0.85rem; }
        .back-link:hover { text-decoration: underline; }

        .toggle { position: relative; width: 40px; height: 22px; }
        .toggle input { opacity: 0; width: 0; height: 0; }
        .toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: #ccc; border-radius: 22px; transition: 0.3s; }
        .toggle-slider::before { content: ''; position: absolute; height: 16px; width: 16px; left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: 0.3s; }
        .toggle input:checked + .toggle-slider { background: var(--theme); }
        .toggle input:checked + .toggle-slider::before { transform: translateX(18px); }
    </style>
</head>
<body>
    <header class="header">
        <h1>🌲 Hermes Relay — 管理控制台</h1>
        <p>轻量级中继服务器 · 数据聚合与参数分发</p>
        <div class="status-badge">
            <span class="status-dot" id="serverStatus"></span>
            <span id="serverStatusText">检查中...</span>
        </div>
    </header>

    <div class="container">
        <a href="/" class="back-link">← 返回首页</a>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">活跃客户端</div>
                <div class="value" id="statClients">--</div>
                <div class="sub">累计唯一设备</div>
            </div>
            <div class="stat-card">
                <div class="label">累计补丁</div>
                <div class="value" id="statPatches">--</div>
                <div class="sub">来自所有客户端</div>
            </div>
            <div class="stat-card">
                <div class="label">累计报告</div>
                <div class="value" id="statReports">--</div>
                <div class="sub">周报提交数</div>
            </div>
            <div class="stat-card">
                <div class="label">覆盖周数</div>
                <div class="value" id="statWeeks">--</div>
                <div class="sub">数据跨度</div>
            </div>
        </div>

        <!-- Tabs -->
        <div class="tabs">
            <button class="tab active" onclick="showPanel('overview')">📊 数据概览</button>
            <button class="tab" onclick="showPanel('trends')">📈 进化趋势</button>
            <button class="tab" onclick="showPanel('config')">⚙️ 中继配置</button>
            <button class="tab" onclick="showPanel('params')">📦 参数分发</button>
        </div>

        <!-- Overview Panel -->
        <div class="panel active" id="panel-overview">
            <h2>周数据详情</h2>
            <div class="week-selector" id="weekSelector"></div>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>周标识</th>
                        <th>活跃客户端</th>
                        <th>补丁数</th>
                        <th>痛点数</th>
                    </tr>
                </thead>
                <tbody id="weeklyTableBody">
                    <tr><td colspan="5" class="loading">加载中...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Trends Panel -->
        <div class="panel" id="panel-trends">
            <h2>模块热度 TOP10</h2>
            <div id="trendAlert"></div>
            <table>
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>模块</th>
                        <th>热度</th>
                        <th>趋势</th>
                    </tr>
                </thead>
                <tbody id="moduleTableBody">
                    <tr><td colspan="4" class="loading">加载中...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Config Panel -->
        <div class="panel" id="panel-config">
            <h2>服务器配置</h2>
            <div id="configAlert"></div>
            <div class="config-grid">
                <div class="config-item">
                    <label>服务器地址</label>
                    <input type="text" id="cfgHost" value="0.0.0.0">
                </div>
                <div class="config-item">
                    <label>端口</label>
                    <input type="number" id="cfgPort" value="8766">
                </div>
                <div class="config-item">
                    <label>最大客户端数</label>
                    <input type="number" id="cfgMaxClients" value="100">
                </div>
                <div class="config-item">
                    <label>中继功能</label>
                    <input type="checkbox" id="cfgRelayEnabled" checked style="width: auto;">
                </div>
            </div>
            <div style="margin-top: 16px;">
                <button class="btn btn-primary" onclick="saveConfig()">保存配置</button>
            </div>
        </div>

        <!-- Params Panel -->
        <div class="panel" id="panel-params">
            <h2>中继参数分发</h2>
            <div id="paramsAlert"></div>
            <div class="config-grid">
                <div class="config-item">
                    <label>重试超时 (秒)</label>
                    <input type="number" id="paramRetryTimeout" value="30">
                </div>
                <div class="config-item">
                    <label>最大重试次数</label>
                    <input type="number" id="paramMaxRetry" value="3">
                </div>
                <div class="config-item">
                    <label>心跳间隔 (秒)</label>
                    <input type="number" id="paramHeartbeatInterval" value="60">
                </div>
                <div class="config-item">
                    <label>批处理大小</label>
                    <input type="number" id="paramBatchSize" value="10">
                </div>
            </div>
            <div style="margin-top: 16px;">
                <button class="btn btn-primary" onclick="saveParams()">保存参数</button>
                <button class="btn" onclick="loadParams()" style="margin-left: 8px; background: #e0e0e0;">重置</button>
            </div>
        </div>
    </div>

    <footer class="footer">
        Hermes Relay Server v2.0 · <a href="/" style="color: var(--theme);">返回首页</a>
    </footer>

    <script>
        const API_BASE = window.location.origin + '/api';

        async function init() {
            await checkHealth();
            await loadOverview();
            await loadTrends();
            await loadConfig();
            await loadParams();
        }

        async function checkHealth() {
            try {
                const resp = await fetch(API_BASE + '/health');
                const data = await resp.json();
                document.getElementById('serverStatus').classList.remove('offline');
                document.getElementById('serverStatusText').textContent = '在线';
            } catch (e) {
                document.getElementById('serverStatus').classList.add('offline');
                document.getElementById('serverStatusText').textContent = '离线';
            }
        }

        async function loadOverview() {
            try {
                const resp = await fetch(API_BASE + '/stats/overview');
                const data = await resp.json();
                document.getElementById('statClients').textContent = data.total_clients || 0;
                document.getElementById('statPatches').textContent = data.total_patches || 0;
                document.getElementById('statReports').textContent = data.total_reports || 0;
                document.getElementById('statWeeks').textContent = data.total_weeks || 0;
            } catch (e) { console.error(e); }
        }

        async function loadTrends() {
            try {
                const resp = await fetch(API_BASE + '/stats/trends?weeks=8');
                const data = await resp.json();
                const selector = document.getElementById('weekSelector');
                selector.innerHTML = '';
                data.trends.forEach((week, i) => {
                    const btn = document.createElement('button');
                    btn.className = 'week-btn' + (i === data.trends.length - 1 ? ' active' : '');
                    btn.textContent = week.week_id;
                    btn.onclick = () => selectWeek(week, btn);
                    selector.appendChild(btn);
                });
                if (data.trends.length > 0) selectWeek(data.trends[data.trends.length - 1], selector.lastChild);
            } catch (e) { console.error(e); }
        }

        function selectWeek(week, btn) {
            document.querySelectorAll('.week-btn').forEach(b => b.classList.remove('active'));
            if (btn) btn.classList.add('active');
            const tbody = document.getElementById('weeklyTableBody');
            if (!week.total_patches && !week.total_pain_points) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty">暂无数据</td></tr>';
                return;
            }
            tbody.innerHTML = '<tr><td>1</td><td>' + week.week_id + '</td><td>' + week.active_clients + '</td><td>' + week.total_patches + '</td><td>' + week.total_pain_points + '</td></tr>';
            loadModuleTable(week.week_id);
        }

        async function loadModuleTable(weekId) {
            const tbody = document.getElementById('moduleTableBody');
            try {
                const resp = await fetch(API_BASE + '/weekly/' + weekId + '/aggregate');
                const data = await resp.json();
                if (!data.top_modules || !data.top_modules.length) {
                    tbody.innerHTML = '<tr><td colspan="4" class="empty">暂无模块数据</td></tr>';
                    return;
                }
                tbody.innerHTML = data.top_modules.map((m, i) => {
                    const badge = i < 3 ? '<span class="badge hot">HOT</span>' : '';
                    return '<tr><td>' + (i+1) + '</td><td>' + m.module + ' ' + badge + '</td><td>' + m.count + '</td><td>--</td></tr>';
                }).join('');
            } catch (e) { tbody.innerHTML = '<tr><td colspan="4" class="empty">加载失败</td></tr>'; }
        }

        async function loadConfig() {
            try {
                const resp = await fetch(API_BASE + '/relay/config');
                const data = await resp.json();
                document.getElementById('cfgMaxClients').value = data.max_clients || 100;
                document.getElementById('cfgRelayEnabled').checked = data.relay_enabled !== false;
            } catch (e) { console.error(e); }
        }

        async function saveConfig() {
            const alert = document.getElementById('configAlert');
            try {
                await fetch(API_BASE + '/admin/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        server: { max_clients: parseInt(document.getElementById('cfgMaxClients').value) },
                        relay: { relay_enabled: document.getElementById('cfgRelayEnabled').checked }
                    })
                });
                alert.innerHTML = '<div class="alert alert-success">配置已保存</div>';
                setTimeout(() => alert.innerHTML = '', 3000);
            } catch (e) {
                alert.innerHTML = '<div class="alert alert-error">保存失败</div>';
            }
        }

        async function loadParams() {
            try {
                const resp = await fetch(API_BASE + '/relay/params');
                const data = await resp.json();
                const p = data.params || {};
                document.getElementById('paramRetryTimeout').value = p.retry_timeout || 30;
                document.getElementById('paramMaxRetry').value = p.max_retry || 3;
                document.getElementById('paramHeartbeatInterval').value = p.heartbeat_interval || 60;
                document.getElementById('paramBatchSize').value = p.batch_size || 10;
            } catch (e) { console.error(e); }
        }

        async function saveParams() {
            const alert = document.getElementById('paramsAlert');
            try {
                await fetch(API_BASE + '/relay/params', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        params: {
                            retry_timeout: parseInt(document.getElementById('paramRetryTimeout').value),
                            max_retry: parseInt(document.getElementById('paramMaxRetry').value),
                            heartbeat_interval: parseInt(document.getElementById('paramHeartbeatInterval').value),
                            batch_size: parseInt(document.getElementById('paramBatchSize').value)
                        }
                    })
                });
                alert.innerHTML = '<div class="alert alert-success">参数已保存，客户端下次拉取时更新</div>';
                setTimeout(() => alert.innerHTML = '', 3000);
            } catch (e) {
                alert.innerHTML = '<div class="alert alert-error">保存失败</div>';
            }
        }

        function showPanel(name) {
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById('panel-' + name).classList.add('active');
            event.target.classList.add('active');
        }

        init();
    </script>
</body>
</html>"""


def save_dashboard(output_dir: Path = None) -> dict:
    """
    生成并保存所有 Web 页面

    Returns:
        dict: {'landing': path, 'admin': path}
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "web"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成首页
    landing_html = generate_landing_html()
    landing_file = output_dir / "index.html"
    with open(landing_file, "w", encoding="utf-8") as f:
        f.write(landing_html)

    # 生成管理控制台
    admin_html = generate_admin_html()
    admin_file = output_dir / "admin.html"
    with open(admin_file, "w", encoding="utf-8") as f:
        f.write(admin_html)

    print(f"[OK] 项目首页: {landing_file}")
    print(f"[OK] 管理控制台: {admin_file}")

    return {"landing": str(landing_file), "admin": str(admin_file)}


if __name__ == "__main__":
    save_dashboard()
