# relay_server/web_dashboard.py — Web管理端仪表板HTML生成

from pathlib import Path

def generate_dashboard_html() -> str:
    """生成Web管理端仪表板HTML"""

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Living Tree AI — 进化监控中心</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --theme: #2E7D32;
            --accent: #4CAF50;
            --bg: #f5f5f5;
            --card: #ffffff;
            --text: #1a1a1a;
            --text-secondary: #666;
            --border: #e0e0e0;
            --danger: #e53935;
            --warning: #fb8c00;
            --success: #43a047;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        /* Header */
        .header {
            background: var(--theme);
            color: white;
            padding: 20px 32px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 1.5rem;
            font-weight: 600;
        }

        .header p {
            opacity: 0.8;
            font-size: 0.9rem;
            margin-top: 4px;
        }

        /* Container */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .stat-card {
            background: var(--card);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }

        .stat-card .label {
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-bottom: 8px;
        }

        .stat-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--theme);
        }

        .stat-card .change {
            font-size: 0.8rem;
            margin-top: 4px;
        }

        .stat-card .change.up { color: var(--success); }
        .stat-card .change.down { color: var(--danger); }

        /* Section */
        .section {
            background: var(--card);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }

        .section h2 {
            font-size: 1.1rem;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }

        /* Table */
        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            text-align: left;
            padding: 12px 8px;
            border-bottom: 1px solid var(--border);
        }

        th {
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.85rem;
        }

        tr:hover {
            background: #f8f8f8;
        }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        .badge.hot { background: #ffebee; color: #c62828; }
        .badge.new { background: #e8f5e9; color: #2e7d32; }

        /* Chart placeholder */
        .chart-placeholder {
            height: 200px;
            background: linear-gradient(135deg, #f5f5f5 25%, #fafafa 50%, #f5f5f5 75%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        /* Week Selector */
        .week-selector {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }

        .week-btn {
            padding: 8px 16px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: white;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }

        .week-btn:hover {
            border-color: var(--theme);
            color: var(--theme);
        }

        .week-btn.active {
            background: var(--theme);
            color: white;
            border-color: var(--theme);
        }

        /* Download Button */
        .download-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            background: var(--theme);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85rem;
            text-decoration: none;
        }

        .download-btn:hover {
            background: var(--accent);
        }

        /* Loading */
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }

        .loading::after {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid var(--border);
            border-top-color: var(--theme);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 8px;
            vertical-align: middle;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 24px;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <header class="header">
        <h1>Living Tree AI — 进化监控中心</h1>
        <p>客户端智能进化数据聚合与趋势分析</p>
    </header>

    <div class="container">
        <!-- Stats Overview -->
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="label">活跃客户端</div>
                <div class="value" id="statClients">--</div>
            </div>
            <div class="stat-card">
                <div class="label">累计补丁</div>
                <div class="value" id="statPatches">--</div>
            </div>
            <div class="stat-card">
                <div class="label">累计报告</div>
                <div class="value" id="statReports">--</div>
            </div>
            <div class="stat-card">
                <div class="label">覆盖周数</div>
                <div class="value" id="statWeeks">--</div>
            </div>
        </div>

        <!-- Trends Section -->
        <div class="section">
            <h2>进化趋势</h2>
            <div class="week-selector" id="weekSelector"></div>
            <div class="chart-placeholder">
                趋势图表加载中...
            </div>
        </div>

        <!-- Top Modules -->
        <div class="section">
            <h2>热门模块 TOP10</h2>
            <table id="moduleTable">
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

        <!-- Weekly Data -->
        <div class="section">
            <h2>
                周数据详情
                <a href="#" class="download-btn" id="downloadBtn" style="float:right">
                    下载JSON
                </a>
            </h2>
            <table id="weeklyTable">
                <thead>
                    <tr>
                        <th>周标识</th>
                        <th>客户端数</th>
                        <th>补丁数</th>
                        <th>痛点数</th>
                        <th>聚合状态</th>
                    </tr>
                </thead>
                <tbody id="weeklyTableBody">
                    <tr><td colspan="5" class="loading">加载中...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <footer class="footer">
        <p>Living Tree AI Evolution Relay Server · 数据每周一凌晨自动聚合</p>
    </footer>

    <script>
        const API_BASE = '/api';

        // 加载概览统计
        async function loadOverview() {
            try {
                const resp = await fetch(API_BASE + '/stats/overview');
                const data = await resp.json();

                document.getElementById('statClients').textContent = data.total_clients || 0;
                document.getElementById('statPatches').textContent = data.total_patches || 0;
                document.getElementById('statReports').textContent = data.total_reports || 0;
                document.getElementById('statWeeks').textContent = data.total_weeks || 0;
            } catch (e) {
                console.error('加载概览失败:', e);
            }
        }

        // 加载趋势
        async function loadTrends() {
            try {
                const resp = await fetch(API_BASE + '/trends?weeks=8');
                const data = await resp.json();

                // 更新周选择器
                const selector = document.getElementById('weekSelector');
                selector.innerHTML = '';

                data.trends.forEach((week, i) => {
                    const btn = document.createElement('button');
                    btn.className = 'week-btn' + (i === data.trends.length - 1 ? ' active' : '');
                    btn.textContent = week.week_id;
                    btn.onclick = () => selectWeek(week.week_id, i === data.trends.length - 1);
                    selector.appendChild(btn);
                });
            } catch (e) {
                console.error('加载趋势失败:', e);
            }
        }

        // 选择周
        async function selectWeek(weekId, isLatest = false) {
            // 更新按钮状态
            document.querySelectorAll('.week-btn').forEach(btn => {
                btn.classList.toggle('active', btn.textContent === weekId);
            });

            // 更新下载链接
            document.getElementById('downloadBtn').href = API_BASE + '/weekly/' + weekId + '/raw';

            // 加载模块数据
            try {
                let data;
                try {
                    const resp = await fetch(API_BASE + '/weekly/' + weekId + '/aggregate');
                    data = await resp.json();
                } catch {
                    data = { top_modules: [], total_patches: 0, total_pain_points: 0 };
                }

                const tbody = document.getElementById('moduleTableBody');
                if (!data.top_modules || data.top_modules.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#999">暂无数据</td></tr>';
                    return;
                }

                tbody.innerHTML = data.top_modules.map((m, i) => {
                    const badge = i < 3 ? '<span class="badge hot">HOT</span>' : '';
                    return '<tr><td>' + (i+1) + '</td><td>' + m.module + ' ' + badge + '</td><td>' + m.count + '</td><td>--</td></tr>';
                }).join('');
            } catch (e) {
                console.error('加载模块数据失败:', e);
            }
        }

        // 加载周列表
        async function loadWeeklyList() {
            try {
                const resp = await fetch(API_BASE + '/stats/overview');
                const overview = await resp.json();

                // 简单显示最近几周
                const tbody = document.getElementById('weeklyTableBody');
                const weeks = [];
                for (let i = 0; i < Math.min(overview.total_weeks || 4, 4); i++) {
                    const d = new Date();
                    d.setDate(d.getDate() - i * 7);
                    const iso = d.isocalendar();
                    weeks.push(iso[0] + '-W' + String(iso[1]).padStart(2, '0'));
                }

                tbody.innerHTML = weeks.map(w => {
                    return '<tr><td>' + w + '</td><td>--</td><td>--</td><td>--</td><td><span class="badge">已聚合</span></td></tr>';
                }).join('');
            } catch (e) {
                console.error('加载周列表失败:', e);
            }
        }

        // 初始化
        async function init() {
            await loadOverview();
            await loadTrends();
            await loadWeeklyList();

            // 默认选中最新周
            const latestBtn = document.querySelector('.week-btn:last-child');
            if (latestBtn) {
                latestBtn.click();
            }
        }

        init();
    </script>
</body>
</html>"""

    return html


def save_dashboard(output_dir: Path = None):
    """保存仪表板HTML"""
    if output_dir is None:
        output_dir = Path(__file__).parent / "web"

    output_dir.mkdir(parents=True, exist_ok=True)

    html = generate_dashboard_html()
    index_file = output_dir / "index.html"

    with open(index_file, "w", encoding="utf-8") as f:
        f.write(html)

    return str(index_file)


if __name__ == "__main__":
    saved_path = save_dashboard()
    print(f"Dashboard saved to: {saved_path}")
