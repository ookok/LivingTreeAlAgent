# 智能部署中心

> L0-L4 模型层自动化部署方案

## 概述

智能部署中心提供统一的模型部署管理，支持：
- **本地自动部署**：Ollama 自动安装、下载、启动
- **远程 API 配置**：连接远程模型服务器
- **状态监控**：实时监控服务运行状态
- **一键操作**：减少用户输入，提升部署流畅度

## 架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          智能部署中心                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      UI 层 (deployment_center_panel.py)               │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                    │   │
│  │  │ 本地部署页   │ │ 远程配置页   │ │ 状态总览页   │                    │   │
│  │  │ TierCard    │ │ API Config  │ │ StatusTable │                    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                       │                                       │
│  ┌────────────────────────────────────┴────────────────────────────────────┐ │
│  │                        核心层                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │ │
│  │  │DeploymentEngine │  │DeploymentMonitor│  │ ModelLayerConfig│          │ │
│  │  │  部署引擎        │  │  状态监控器      │  │  模型层配置      │          │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                       │
│  ┌────────────────────────────────────┴────────────────────────────────────┐ │
│  │                        服务层                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │ │
│  │  │ Ollama Service │  │ Remote API      │  │ System Monitor  │          │ │
│  │  │ (本地模型)      │  │ (远程服务)       │  │ (资源监控)       │          │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 模型层级

| 层级 | 模型 | 用途 | 推荐内存 |
|------|------|------|----------|
| **L0** | SmolLM2 / Qwen2.5-0.5B / Qwen2.5-1.5B | 意图分类、快速路由 | 1-2.5GB |
| **L1** | Qwen2.5-3B | 轻量推理、搜索增强 | 4GB |
| **L2** | Qwen2.5-7B | 通用对话、文档处理 | 8GB |
| **L3** | Qwen3.5-4B / Qwen3.5-2B | 意图理解、复杂推理 | 4-6GB |
| **L4** | Qwen3.5-9B / DeepSeek-R1-70B | 深度生成、思考模式 | 12-64GB |

## 快速开始

### Python API

```python
from core.deployment_engine import DeploymentEngine, get_deployment_engine
from core.deployment_monitor import DeploymentMonitor, get_deployment_monitor
from core.model_layer_config import ModelTier

# 获取部署引擎
engine = get_deployment_engine()

# 健康检查
health = engine.health_check()
print(f"Ollama: {health['ollama_running']}")
print(f"本地模型: {health['local_models']}")

# 部署单个层级
result = engine.auto_deploy_tier(
    ModelTier.L0,
    progress_callback=lambda p, s: print(f"[{p:.0%}] {s}")
)
print(f"结果: {result.message}")

# 一键部署所有
results = engine.auto_deploy_all(
    progress_callback=lambda p, s, t: print(f"[{p:.0%}] {t.value}: {s}")
)
for tier, result in results.items():
    print(f"{tier.value}: {'成功' if result.success else '失败'}")

# 状态监控
monitor = get_deployment_monitor()
monitor.start_monitoring()

import time
time.sleep(10)  # 监控10秒

monitor.stop_monitoring()
```

### PyQt6 UI

```python
from ui.deployment_center_panel import DeploymentCenterPanel
from PyQt6.QtWidgets import QApplication

app = QApplication([])
panel = DeploymentCenterPanel()
panel.show()
app.exec()
```

## 部署模式

### 本地部署模式

1. 自动检测 Ollama 安装状态
2. 自动下载模型 (`ollama pull`)
3. 自动启动服务
4. 状态实时监控

```python
config = LayerDeploymentConfig()
config.mode = DeployMode.LOCAL
config.auto_deploy_all = True
config.download_on_start = True
```

### 远程配置模式

1. 用户配置 API 地址和 Key
2. 系统验证连接
3. 使用远程 API 代替本地 Ollama

```python
config = LayerDeploymentConfig()
config.mode = DeployMode.REMOTE
config.remote_base_url = "http://139.199.124.242:8899/v1"
config.remote_api_key = "your-api-key"
```

## 状态监控

### 状态类型

| 状态 | 说明 | 颜色 |
|------|------|------|
| `RUNNING` | 服务运行中 | 🟢 绿色 |
| `STOPPED` | 已停止 | ⚫ 灰色 |
| `STARTING` | 启动中 | 🟡 黄色 |
| `ERROR` | 错误 | 🔴 红色 |
| `DOWNLOADING` | 下载中 | 🔵 蓝色 |

### 监控回调

```python
def on_status_change(status: SystemStatus):
    print(f"Ollama: {status.ollama_running}")
    print(f"内存: {status.used_memory_gb:.1f}/{status.total_memory_gb:.1f}GB")
    for tier, tier_status in status.tier_status.items():
        print(f"  {tier}: {tier_status.status}")

monitor = get_deployment_monitor()
monitor.add_callback(on_status_change)
monitor.start_monitoring()
```

## 文件清单

```
core/
├── model_layer_config.py       # L0-L4 模型层配置
├── deployment_engine.py         # 自动化部署引擎
└── deployment_monitor.py        # 状态监控器

ui/
└── deployment_center_panel.py   # 统一部署面板

tests/
└── test_deployment_center.py    # 测试文件

docs/
└── DEPLOYMENT_CENTER.md         # 本文档
```

## API 参考

### DeploymentEngine

```python
class DeploymentEngine:
    def is_ollama_installed() -> bool
    def is_ollama_running() -> bool
    def start_ollama() -> bool
    def stop_ollama() -> bool
    def list_local_models() -> List[str]
    def is_model_installed(model_name: str) -> bool
    def download_model(model_name: str, progress_callback) -> DeploymentResult
    def load_model(model_name: str, keep_alive: str) -> DeploymentResult
    def auto_deploy_tier(tier: ModelTier, model, progress_callback) -> DeploymentResult
    def auto_deploy_all(models, progress_callback) -> Dict[ModelTier, DeploymentResult]
    def get_tier_status(tier: ModelTier) -> ServiceStatus
    def health_check() -> Dict[str, Any]
```

### DeploymentMonitor

```python
class DeploymentMonitor:
    def get_status() -> SystemStatus
    def get_tier_status(tier: ModelTier) -> TierStatus
    def get_all_tier_status() -> Dict[ModelTier, TierStatus]
    def start_service(tier: ModelTier) -> bool
    def stop_service(tier: ModelTier) -> bool
    def restart_service(tier: ModelTier) -> bool
    def start_all_services() -> Dict[ModelTier, bool]
    def stop_all_services() -> Dict[ModelTier, bool]
    def get_diagnostic_report() -> str
    def start_monitoring()
    def stop_monitoring()
```

## 常见问题

### Q: Ollama 未安装
**A**: 访问 https://ollama.com/download 下载安装

### Q: 模型下载失败
**A**: 检查网络连接，或手动执行 `ollama pull <model_name>` 调试

### Q: 内存不足
**A**: 选择更小的模型（如 L0 层使用 SmolLM2）

### Q: 远程连接失败
**A**: 检查 API 地址和 Key 是否正确，确认远程服务已启动

---

**最后更新**: 2026-04-24
