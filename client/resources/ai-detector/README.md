# AI算力仪表盘 - Hardware Detection Tool

> 基于 WebGL 和 JavaScript 的本地硬件检测工具，100%本地运行，无数据上传。

## 文件结构

```
ai-detector/
├── index.html          # 主页面 (嵌入式 CSS/JS)
└── README.md           # 本文件
```

## 功能特性

- **CPU 检测**: 核心数、线程数、架构信息
- **RAM 检测**: 总内存、可用内存
- **GPU 检测**: WebGL渲染器、VRAM估算
- **AI模型匹配**: 21+主流开源AI模型兼容性
- **性能预估**: tokens/sec 估算
- **100%本地运行**: 无数据上传，零隐私风险

## 支持的AI模型

1. GPT-4 (假设兼容)
2. GPT-3.5-Turbo
3. Llama-2-7B
4. Llama-2-13B
5. Llama-2-70B
6. Mistral-7B
7. Mixtral-8x7B
8. Qwen-1.5-7B
9. Qwen-1.5-14B
10. Qwen-1.5-72B
11. ChatGLM2-6B
12. ChatGLM3-6B
13. Baichuan2-7B
14. Baichuan2-13B
15. Yi-6B
16. Yi-34B
17. DeepSeek-7B
18. DeepSeek-33B
19. Falcon-7B
20. Falcon-40B
21. MPT-7B
22. Vicuna-7B
23. Vicuna-13B

## 与PyQt6集成

```python
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl

# 加载本地HTML
webview = QWebEngineView()
detector_path = Path(__file__).parent / "index.html"
webview.setUrl(QUrl.fromLocalFile(str(detector_path)))

# 接收检测结果
webview.page().runJavaScript("window.getDetectionResult()", callback)
```

## 通信协议

检测完成后，结果通过以下方式传递给Python:

```javascript
// 方式1: window.aiDetectorComplete 回调
window.aiDetectorComplete({
    status: "success",
    hardware: {
        cpuCores: 8,
        cpuThreads: 16,
        ramTotalGB: 32,
        ramAvailableGB: 16,
        gpuRenderer: "NVIDIA GeForce RTX 3080",
        gpuVRAM: 10,
        hasWebGL: true
    },
    recommendedModels: [
        {
            modelName: "Llama-2-7B",
            compatibility: "excellent",
            speedEstimate: 45,
            vramRequired: 6,
            recommended: true
        }
    ],
    timestamp: "2026-04-16T14:00:00Z"
});
```
