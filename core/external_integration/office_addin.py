"""
Office Add-in 集成 - WPS/Word 原生插件方案
===========================================

方案说明：
1. Web Add-in（推荐）- 使用 HTML/JS 开发，Word/WPS 都支持
2. COM 插件 - 仅 Windows，需要 C# 开发

Web Add-in 架构：
┌─────────────────────────────────────────┐
│           Office / WPS                   │
│  ┌─────────────────────────────────┐     │
│  │         Add-in 任务面板          │     │
│  │  ┌─────────────────────────┐    │     │
│  │  │    React/Vue 前端         │    │     │
│  │  │    - 选中内容显示          │    │     │
│  │  │    - 操作按钮              │    │     │
│  │  │    - 结果预览              │     │     │
│  │  └─────────────────────────┘    │     │
│  └─────────────────────────────────┘     │
│                    │                    │
│                    ▼                    │
│           Office.js API                  │
└────────────────────┼────────────────────┘
                     │ REST API
                     ▼
┌─────────────────────────────────────────┐
│           AI OS External API             │
│    http://127.0.0.1:8898/api/v1/          │
└─────────────────────────────────────────┘
"""

from core.logger import get_logger
logger = get_logger('external_integration.office_addin')

# ============== Web Add-in 资源 ==============

ADDIN_MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<OfficeApp xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
           xsi:type="TaskPaneApp">

  <Id>AIOS-AddIn-Guid</Id>
  <Version>1.0.0</Version>
  <ProviderName>AI OS</ProviderName>
  <DefaultLocale>zh-CN</DefaultLocale>

  <DisplayName DefaultValue="AI OS 智能助手"/>
  <Description DefaultValue="调用 AI OS 知识库，实现文档智能处理"/>

  <Hosts>
    <Host Name="Document"/>
    <Host Name="Workbook"/>
  </Hosts>

  <DefaultSettings>
    <SourceLocation DefaultValue="https://your-domain.com/ai-os-addin/index.html"/>
  </DefaultSettings>

  <Permissions>ReadWriteDocument</Permissions>
</OfficeApp>
"""

ADDIN_INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI OS 智能助手</title>
    <script src="https://appsforoffice.microsoft.com/lib/1/hosted/office.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            padding: 16px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 16px;
        }
        .header h1 { font-size: 18px; margin-bottom: 4px; }
        .header p { font-size: 12px; opacity: 0.8; }
        .section {
            background: white;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section h2 {
            font-size: 14px;
            color: #333;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }
        .selected-text {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            padding: 12px;
            font-size: 13px;
            max-height: 120px;
            overflow-y: auto;
            margin-bottom: 12px;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .btn-group {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }
        .btn {
            padding: 10px 12px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover { background: #5a6fd6; }
        .btn-success { background: #28a745; color: white; }
        .btn-success:hover { background: #218838; }
        .btn-info { background: #17a2b8; color: white; }
        .btn-info:hover { background: #138496; }
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        .btn-secondary:hover { background: #5a6268; }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .result {
            background: #f8f9fa;
            border-radius: 4px;
            padding: 12px;
            font-size: 13px;
            min-height: 80px;
            white-space: pre-wrap;
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid #e9ecef;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .status {
            font-size: 11px;
            color: #666;
            margin-top: 8px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #28a745;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI OS 智能助手</h1>
        <p>选中文字，快速调用 AI OS 能力</p>
    </div>

    <div class="section">
        <h2>📝 选中内容</h2>
        <div id="selectedText" class="selected-text">请在文档中选中文字...</div>
        <button id="refreshBtn" class="btn btn-secondary">🔄 刷新选中</button>
    </div>

    <div class="section">
        <h2>⚡ 快捷操作</h2>
        <div class="btn-group">
            <button id="summarizeBtn" class="btn btn-primary" disabled>
                📋 摘要
            </button>
            <button id="polishBtn" class="btn btn-success" disabled>
                ✨ 润色
            </button>
            <button id="translateBtn" class="btn btn-info" disabled>
                🌐 翻译
            </button>
            <button id="correctBtn" class="btn btn-secondary" disabled>
                ✅ 纠正
            </button>
        </div>
        <div class="status">
            <span class="status-dot"></span>
            <span>API: http://127.0.0.1:8898</span>
        </div>
    </div>

    <div class="section">
        <h2>📤 处理结果</h2>
        <div id="result" class="result">等待处理...</div>
    </div>

    <script>
        const API_BASE = 'http://127.0.0.1:8898/api/v1';
        let currentText = '';

        // 初始化 Office.js
        Office.onReady(() => {
            console.log('AI OS Add-in 已加载');
            refreshSelection();
        });

        // 刷新选中内容
        async function refreshSelection() {
            try {
                const selection = await Word.run(async (context) => {
                    const range = context.document.getSelection();
                    range.load('text');
                    await context.sync();
                    return range.text;
                });

                currentText = selection.trim();
                document.getElementById('selectedText').textContent =
                    currentText || '请在文档中选中文字...';

                // 启用/禁用按钮
                const hasText = currentText.length > 0;
                document.querySelectorAll('.btn-group .btn').forEach(btn => {
                    btn.disabled = !hasText;
                });

                if (hasText) {
                    document.getElementById('result').textContent = '准备就绪，点击操作按钮...';
                }
            } catch (error) {
                console.error('获取选中内容失败:', error);
            }
        }

        // 调用 AI OS API
        async function callAPI(endpoint, data) {
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div>处理中...</div>';

            try {
                const response = await fetch(`${API_BASE}/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: currentText, ...data })
                });

                const result = await response.json();

                if (result.success) {
                    resultDiv.textContent = result.data[Object.keys(result.data)[0]] || JSON.stringify(result.data, null, 2);
                } else {
                    resultDiv.textContent = '错误: ' + result.error;
                }
            } catch (error) {
                resultDiv.textContent = '请求失败: ' + error.message + '\\n\\n请确保 AI OS 服务已启动（python -m core.external_integration）';
            }
        }

        // 绑定按钮事件
        document.getElementById('refreshBtn').onclick = refreshSelection;
        document.getElementById('summarizeBtn').onclick = () => callAPI('summarize', {});
        document.getElementById('polishBtn').onclick = () => callAPI('polish', {});
        document.getElementById('translateBtn').onclick = () => callAPI('translate', { options: { target_lang: 'en' } });
        document.getElementById('correctBtn').onclick = () => callAPI('correct', {});

        // 全局快捷键
        document.addEventListener('keydown', async (e) => {
            if (e.ctrlKey && e.shiftKey) {
                if (e.key === 'S') { e.preventDefault(); callAPI('summarize', {}); }
                if (e.key === 'P') { e.preventDefault(); callAPI('polish', {}); }
                if (e.key === 'T') { e.preventDefault(); callAPI('translate', {}); }
            }
        });
    </script>
</body>
</html>
"""

ADDIN_INSTALL_SCRIPT = """# AI OS Add-in 安装脚本
# ==========================

# 方式一：本地部署 Add-in（开发用）
# 1. 将此文件夹部署到 Web 服务器
# 2. 修改 manifest.xml 中的 SourceLocation
# 3. 在 Word 中：文件 -> 获取加载项 -> 我的加载项 -> 上传加载项

# 方式二：使用 Office 365 CDN
# 1. 将前端文件上传到 Azure Blob/Static Web Apps
# 2. 获取公网 URL
# 3. 修改 manifest.xml

# 方式三：旁加载（Sideload，仅开发）
# PowerShell:
$manifest = "path/to/ai-os-addin-manifest.xml"
Copy-Item $manifest "$env:APPDATA\\Microsoft\\Templates\\Document Formatting\\"

Write-Host "Add-in 已添加，请重新打开 Word"
"""

# ============== 导出 ==============

__all__ = [
    'ADDIN_MANIFEST',
    'ADDIN_INDEX_HTML',
    'ADDIN_INSTALL_SCRIPT',
    'create_wordaddin_package',
]


def create_wordaddin_package(output_dir: str):
    """
    创建 Word Add-in 安装包

    Args:
        output_dir: 输出目录
    """
    import os


    os.makedirs(output_dir, exist_ok=True)

    # 写入文件
    files = {
        'manifest.xml': ADDIN_MANIFEST,
        'index.html': ADDIN_INDEX_HTML,
        'INSTALL.txt': ADDIN_INSTALL_SCRIPT,
    }

    for filename, content in files.items():
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    logger.info(f"[AI OS Add-in] 安装包已生成: {output_dir}")
    logger.info("  - manifest.xml: Office 加载项清单")
    logger.info("  - index.html: Add-in 界面")
    logger.info("  - INSTALL.txt: 安装说明")
