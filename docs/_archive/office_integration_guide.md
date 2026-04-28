# AI OS Office 集成指南

## 🚀 快速开始

### 1. 启动集成服务

```bash
# 启动所有服务
python -m core.external_integration

# 仅 API 服务
python -m core.external_integration --api-only

# 指定端口
python -m core.external_integration --port 8899
```

### 2. 服务状态

```
✅ REST API:  http://127.0.0.1:8898/api/v1/
✅ 剪贴板监控: 已启用
✅ 快捷键:     Ctrl+Shift+S/P/T/C/Q
```

---

## 📋 集成方案对比

| 方案 | 入侵性 | 难度 | 效果 | 推荐场景 |
|------|--------|------|------|----------|
| **REST API** | ⭐ 无 | ⭐ | 所有应用可用 | 程序员首选 |
| **剪贴板桥接** | ⭐ 无 | ⭐ | 无感知调用 | 日常办公 |
| **Python for Office** | ⭐ 极低 | ⭐⭐ | 深度集成 | 自动化办公 |
| **Office Add-in** | ⭐⭐ 低 | ⭐⭐⭐ | 原生体验 | 正式部署 |

---

## 🔌 方案一：REST API（最简单）

### cURL 调用

```bash
# 知识库查询
curl -X POST http://127.0.0.1:8898/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "公司章程查询", "context": "word"}'

# 文档摘要
curl -X POST http://127.0.0.1:8898/api/v1/summarize \
  -H "Content-Type: application/json" \
  -d '{"text": "要摘要的长文本..."}'

# 文本润色
curl -X POST http://127.0.0.1:8898/api/v1/polish \
  -H "Content-Type: application/json" \
  -d '{"text": "需要润色的文本"}'

# 翻译
curl -X POST http://127.0.0.1:8898/api/v1/translate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello", "options": {"target_lang": "zh"}}'

# 错别字纠正
curl -X POST http://127.0.0.1:8898/api/v1/correct \
  -H "Content-Type: application/json" \
  -d '{"text": "今天天气很好"}'
```

### Python 客户端

```python
from core.external_integration.api_server import APIClient

# 创建客户端
client = APIClient(base_url="http://127.0.0.1:8898")

# 查询知识库
result = client.query("公司章程关于分红的规定")
print(result['answer'])

# 摘要
result = client.summarize("长文档内容...")
print(result['summary'])

# 润色
result = client.polish("请帮我写一份报告")
print(result['polished'])
```

---

## 📋 方案二：剪贴板桥接（无感知）

### 工作原理

```
用户复制文字 → 剪贴板监控 → AI OS 分析 → 快捷键触发 → 结果覆盖剪贴板
```

### 使用方式

1. **复制文字**：在 Word/WPS 中复制一段文字
2. **自动检测**：服务自动分析内容类型
3. **快捷键操作**：
   - `Ctrl+Shift+S` - 生成摘要
   - `Ctrl+Shift+P` - 润色
   - `Ctrl+Shift+T` - 翻译
   - `Ctrl+Shift+C` - 纠正错别字
4. **粘贴结果**：处理后的内容已复制到剪贴板

### 代码示例

```python
from core.external_integration import start_clipboard_monitoring

# 启动监控
bridge = start_clipboard_monitoring()

# 查看历史
for entry in bridge.get_history():
    print(f"[{entry.char_count}字] {entry.suggestions}")

# 手动触发处理
result = bridge.process_action(SuggestionType.SUMMARIZE)
print(result)
```

---

## 🐍 方案三：Python for Office（深度集成）

### 3.1 Word/VBA 宏

```vba
Sub CallAIOSSummarize()
    Dim selectedText As String
    selectedText = Selection.Text

    Dim http As Object
    Set http = CreateObject("MSXML2.ServerXMLHTTP")
    http.Open "POST", "http://127.0.0.1:8898/api/v1/summarize", False
    http.setRequestHeader "Content-Type", "application/json"
    http.Send "{""text"": """ & selectedText & """}"

    Selection.Text = http.ResponseText
End Sub
```

### 3.2 WPS Python 宏

```python
# 文件: wps_script.py (放在 WPS 宏目录)

import requests
import json

API_URL = "http://127.0.0.1:8898/api/v1"

def summarize_selection():
    """摘要选中内容"""
    # 获取选中文本
    selection = wps.Selection()
    text = selection.Text

    if not text:
        print("请先选中文字")
        return

    # 调用 AI OS
    response = requests.post(
        f"{API_URL}/summarize",
        json={"text": text}
    )

    result = response.json()
    if result['success']:
        # 替换选中文本
        selection.Text = result['data']['summary']
        print("摘要完成!")
    else:
        print(f"错误: {result['error']}")

def polish_selection():
    """润色选中内容"""
    selection = wps.Selection()
    text = selection.Text

    if not text:
        return

    response = requests.post(
        f"{API_URL}/polish",
        json={"text": text}
    )

    result = response.json()
    if result['success']:
        selection.Text = result['data']['polished']
        print("润色完成!")

# 注册快捷键
# 在 WPS 中: 工具 -> 宏 -> 编辑
```

### 3.3 Excel Python 宏 (WPS)

```python
# wps_et_macro.py

import requests
import json

API_URL = "http://127.0.0.1:8898/api/v1"

def analyze_selected_cells():
    """分析选中的单元格"""
    sheet = et.Sheets("Sheet1")
    selection = sheet.Selection

    # 获取单元格内容
    cells_text = []
    for cell in selection:
        if cell.Value:
            cells_text.append(str(cell.Value))

    combined_text = "\\n".join(cells_text)

    # 调用 AI OS 分析
    response = requests.post(
        f"{API_URL}/analyze",
        json={"text": combined_text}
    )

    result = response.json()
    if result['success']:
        # 在右侧单元格输出结果
        result_cell = sheet.Cells(selection.Row, selection.Column + selection.Columns.Count + 1)
        result_cell.Value = result['data']['analysis']
        print("分析完成!")
```

### 3.4 Python-docx 集成

```python
# ai_os_word.py

import requests
from docx import Document
from docx.shared import Pt, RGBColor

API_URL = "http://127.0.0.1:8898/api/v1"

class AIOSWordPlugin:
    """AI OS Word 插件"""

    def __init__(self):
        self.doc = None
        self.api_url = API_URL

    def open_document(self, filepath: str):
        """打开文档"""
        self.doc = Document(filepath)

    def summarize_paragraph(self, para_index: int):
        """摘要指定段落"""
        para = self.doc.paragraphs[para_index]
        text = para.text

        response = requests.post(
            f"{self.api_url}/summarize",
            json={"text": text}
        )

        result = response.json()
        if result['success']:
            para.text = result['data']['summary']
            return True
        return False

    def polish_headings(self):
        """润色所有标题"""
        for para in self.doc.paragraphs:
            if para.style.name.startswith('Heading'):
                response = requests.post(
                    f"{self.api_url}/polish",
                    json={"text": para.text}
                )
                result = response.json()
                if result['success']:
                    para.text = result['data']['polished']

    def batch_summarize(self, output_file: str):
        """批量摘要文档"""
        summaries = []

        for para in self.doc.paragraphs:
            if len(para.text) > 100:
                response = requests.post(
                    f"{self.api_url}/summarize",
                    json={"text": para.text}
                )
                result = response.json()
                if result['success']:
                    summaries.append(result['data']['summary'])

        # 创建摘要文档
        summary_doc = Document()
        summary_doc.add_heading('文档摘要', 0)

        for i, summary in enumerate(summaries, 1):
            summary_doc.add_paragraph(f"段落 {i}: {summary}")

        summary_doc.save(output_file)
        return len(summaries)


# 使用示例
if __name__ == "__main__":
    plugin = AIOSWordPlugin()
    plugin.open_document("报告.docx")

    # 润色标题
    plugin.polish_headings()

    # 导出摘要
    count = plugin.batch_summarize("报告摘要.docx")
    print(f"已处理 {count} 个段落")
```

---

## 🌐 方案四：Office Add-in（原生体验）

### 安装步骤

1. **生成 Add-in 文件**：

```python
from core.external_integration.office_addin import create_wordaddin_package

create_wordaddin_package("output/ai-os-addin")
```

2. **部署到 Web 服务器**：

```bash
# 使用 Python 内置服务器测试
cd output/ai-os-addin
python -m http.server 8080
```

3. **在 Word 中加载**：

- Word -> 文件 -> 选项 -> 加载项
- 选择 "Word 加载项"
- 浏览并选择 `manifest.xml`

4. **使用**：

- 选中文字 -> 点击 "AI OS 智能助手" 任务面板
- 或使用快捷键：`Ctrl+Shift+S` 摘要

---

## 📡 API 参考

### 端点列表

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/query` | 知识库查询 |
| POST | `/api/v1/summarize` | 文档摘要 |
| POST | `/api/v1/polish` | 文本润色 |
| POST | `/api/v1/translate` | 翻译 |
| POST | `/api/v1/correct` | 错别字纠正 |
| POST | `/api/v1/analyze` | 分析 |
| POST | `/api/v1/generate` | 内容生成 |
| POST | `/api/v1/batch` | 批量处理 |
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/capabilities` | 能力列表 |

### 请求格式

```json
{
  "text": "要处理的文本",
  "context": "应用上下文（可选）",
  "options": {
    "target_lang": "en",
    "style": "formal"
  }
}
```

### 响应格式

```json
{
  "success": true,
  "data": {
    "answer": "处理结果...",
    "confidence": 0.95
  },
  "request_id": "abc123",
  "elapsed_ms": 123
}
```

---

## ⚙️ 配置

### 环境变量

```bash
# 设置 API 密钥
export AIOS_API_KEY="your-secret-key"

# 设置端口
export AIOS_API_PORT=8899
```

### 认证

```python
from core.external_integration.api_server import ExternalAPIServer

# 创建带认证的服务器
server = ExternalAPIServer(
    api_keys={
        "word-key-123": "word",
        "wps-key-456": "wps",
    }
)
```

客户端调用：

```python
client = APIClient(
    base_url="http://127.0.0.1:8898",
    api_key="word-key-123"
)
```

---

## 🐛 故障排除

### 1. API 服务无法连接

```bash
# 检查服务是否运行
curl http://127.0.0.1:8898/api/v1/health

# 检查端口占用
netstat -an | grep 8898
```

### 2. 剪贴板监控无响应

- 确认 `pyperclip` 已安装：`pip install pyperclip`
- 检查是否有其他程序占用剪贴板

### 3. Word Add-in 无法加载

- 确认 `manifest.xml` 中的 URL 可访问
- 检查 Office 是否启用了加载项

---

## 🎯 下一步

1. **启动服务**：`python -m core.external_integration`
2. **测试 API**：使用 cURL 或 Python 客户端
3. **集成到 Word**：按上述指南配置 Add-in
4. **自动化办公**：编写 Python 脚本处理文档
