# Hermes Desktop 架构文档

## 项目概览

基于 PyQt6 的 Windows 桌面 AI 助手，集成本地 GGUF 模型管理、Ollama 调用、文档转换、企业级监控。

```
hermes-desktop/
├── main.py                     # PyQt6 主窗口入口
├── run.bat                      # Windows 启动脚本
├── requirements.txt             # 依赖列表
│
├── app/                         # 企业级核心模块
│   ├── __init__.py
│   ├── main.py                  # CLI 主入口
│   ├── core/                    # 核心组件
│   │   ├── config.py           # YAML 配置管理
│   │   ├── security.py         # JWT/API密钥/限流
│   │   └── monitoring.py       # 指标收集/告警
│   ├── services/
│   │   └── model_manager.py    # 增强版模型管理器
│   └── api/
│       └── models.py           # REST API 路由
│
├── config/
│   └── config.yaml             # 企业配置文件
│
├── core/                        # 核心引擎
│   ├── agent.py                # AIAgent 对话循环
│   ├── ollama_client.py        # Ollama API 客户端
│   ├── llama_cpp_client.py     # llama-cpp-python 客户端
│   ├── unified_model_client.py # 统一模型客户端
│   ├── session_db.py           # SQLite 会话持久化
│   ├── memory_manager.py       # 记忆管理
│   └── tools_*.py              # 工具集
│
├── models/                      # 模型管理层
│   ├── model_pool.py          # 模型池
│   ├── downloader.py           # 断点续传下载
│   └── market.py              # ModelScope/HuggingFace 市场
│
├── writing/                     # 写作阅读层
│   ├── doc_manager.py         # 文档管理
│   ├── file_watcher.py        # 目录监控
│   ├── converter.py           # MarkItDown 转换器
│   └── event_handler.py       # 转换事件处理
│
└── ui/                          # PyQt6 界面
    ├── main_window.py         # 三栏主窗口
    ├── chat_panel.py          # 流式聊天
    ├── session_panel.py       # 会话列表
    ├── workspace_panel.py     # 文件树
    ├── writing_panel.py       # 写作编辑器
    ├── model_pool_panel.py    # 模型池面板
    ├── model_market.py        # 模型市场
    ├── settings_dialog.py     # 设置对话框
    └── theme.py              # 暗色主题
```

## 企业级功能

### 1. 配置管理 (`app/core/config.py`)

```yaml
# config/config.yaml
system:
  name: "Hermes Desktop"
  version: "2.0.0"

sources:
  modelscope:
    mirror: "https://mirror.modelScope.cn"
  huggingface:
    mirror: "https://hf-mirror.com"

inference:
  default_context_size: 4096
  temperature: 0.7

monitoring:
  enabled: true
  alert_rules:
    memory_usage_threshold: 85
```

### 2. 安全认证 (`app/core/security.py`)

- JWT 令牌认证
- API 密钥管理
- 速率限制
- 权限范围控制

### 3. 监控系统 (`app/core/monitoring.py`)

```
CPU: 35.7%  Memory: 30.4%  Disk: 71.1%
┌────────────────────────────────────────┐
│  Prometheus Metrics Export              │
│  system_cpu_usage_percent 35.7         │
│  system_memory_usage_percent 30.4      │
└────────────────────────────────────────┘
```

### 4. 模型管理器 (`app/services/model_manager.py`)

- 硬件自动检测 (CPU/RAM/GPU)
- 推荐分数算法
- 断点续传下载
- 智能加载配置

## 使用方式

### CLI 模式

```bash
# 交互模式
python app/main.py -i

# 列出模型
python app/main.py --list

# 显示硬件
python app/main.py --hardware

# 加载模型
python app/main.py --load qwen2.5-7b
```

### GUI 模式

```bash
python main.py
# 或双击 run.bat
```

## 依赖

```
PyQt6>=6.4.0          # 界面
httpx>=0.27.0         # HTTP
pydantic>=2.0         # 数据验证
pyyaml>=6.0           # 配置
modelscope>=1.20.0    # 模型下载
llama-cpp-python>=0.3 # 本地 GGUF
watchdog>=4.0.0       # 文件监控
markitdown>=0.1.0     # 文档转换
psutil>=6.0           # 系统监控
GPUtil>=1.4           # GPU 监控
```

## 快速开始

1. 安装依赖：`pip install -r requirements.txt`
2. 放入模型：`mkdir models && cp your-model.gguf models/`
3. 启动：`python main.py` 或 `run.bat`
