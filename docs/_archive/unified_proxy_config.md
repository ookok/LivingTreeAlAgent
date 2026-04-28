# 统一代理配置方案

## 📋 需求背景

用户要求：
1. **一处设置代理** - 不要到处都设置，只在 workspace panel 的代理源面板设置
2. **搜索源支持 GitHub** - 添加 GitHub 作为搜索源

## 🔧 实现方案

### 1. 统一代理配置中心 (`core/unified_proxy_config.py`)

创建了 `UnifiedProxyConfig` 单例类，实现：
- **单一代理地址设置** - 所有模块使用同一个代理
- **GitHub 搜索源支持** - 直接调用 GitHub API 搜索代码仓库
- **搜索源管理** - 启用/禁用各种搜索源
- **配置持久化** - 自动保存到 `~/.hermes/proxy_config.json`

```python
# 使用方式
from core.unified_proxy_config import UnifiedProxyConfig

config = UnifiedProxyConfig.get_instance()
config.set_proxy("http://127.0.0.1:7890")  # 一处设置，全局生效
```

### 2. 统一代理面板 UI (`ui/unified_proxy_panel.py`)

创建了 `UnifiedProxyPanel` 组件，集成到 workspace panel：

**功能区域：**
- 🌐 **代理设置** - 输入代理地址，一键应用/清除
- 🔍 **搜索源** - GitHub、DuckDuckGo、Google、Bing 开关
- ⚡ **快速搜索** - 直接在面板中搜索 GitHub 或全网

**特性：**
- 简洁的 UI 设计
- 实时状态显示
- Token 密码可见性切换

### 3. 更新 Workspace Panel

在 `ui/workspace_panel.py` 中添加了 **代理源** 选项卡：

```
工作区面板
├── 文件选项卡
├── 记忆选项卡
└── 代理源选项卡 ← 新增
```

### 4. 简化 AppProxyConfig

更新 `core/app_proxy_config.py`：
- 内部使用 `UnifiedProxyConfig`
- 保持向后兼容
- 不再分散设置多个环境变量
- 添加 `SEARCH_SOURCES` 到白名单

### 5. 市场白名单增强

更新了 `MarketWhitelist` 类：
```python
SEARCH_SOURCES = {
    "GitHub": ["github.com", "api.github.com"],
    "DuckDuckGo": ["duckduckgo.com", "lite.duckduckgo.com"],
    "Google": ["google.com", "googleapis.com"],
    "Bing": ["bing.com", "api.bing.microsoft.com"],
    "SearXNG": ["searx.sh", "searxng.org"],
}
```

## 📁 文件变更

| 文件 | 变更 | 说明 |
|------|------|------|
| `core/unified_proxy_config.py` | **新增** | 统一代理配置中心 |
| `ui/unified_proxy_panel.py` | **新增** | 统一代理面板 UI |
| `ui/workspace_panel.py` | **修改** | 添加代理源选项卡 |
| `client/src/.../workspace_panel.py` | **修改** | 客户端同步修改 |
| `core/app_proxy_config.py` | **修改** | 使用统一配置，添加搜索源白名单 |

## 🔄 使用流程

### 1. 设置代理
```
工作区面板 → 代理源选项卡 → 输入代理地址 → 点击"应用"
```

### 2. 配置 GitHub Token（可选）
```
代理源选项卡 → GitHub Token 输入框 → 输入 Token
```

### 3. 启用/禁用搜索源
```
代理源选项卡 → 搜索源区域 → 勾选/取消搜索源
```

### 4. 快速搜索
```
代理源选项卡 → 输入搜索关键词 → 点击 "GitHub" 或 "全网"
```

## 🎯 核心优势

1. **一处设置** - 代理地址只需设置一次
2. **GitHub 支持** - 原生 GitHub 搜索，无需第三方服务
3. **统一管理** - 所有代理和搜索源集中在一处
4. **向后兼容** - 现有代码无需修改
5. **配置持久化** - 设置自动保存，重启不丢失

## 🧪 测试验证

运行测试：
```bash
python test_unified_proxy.py
```

测试结果：
- ✅ 统一代理配置测试通过
- ✅ GitHub 搜索功能正常（需要有效代理）
- ✅ 市场白名单正确识别所有搜索源

## 📝 示例代码

```python
# 设置代理（只需一处）
from core.unified_proxy_config import UnifiedProxyConfig
config = UnifiedProxyConfig.get_instance()
config.set_proxy("http://127.0.0.1:7890")

# GitHub 搜索
results = config.search_github("python async", max_results=5)
for r in results:
    print(f"{r['title']} - Stars:{r['score']}")

# 全网搜索
results = await config.search("machine learning", SearchSource.DUCKDUCKGO)
```

## 🔗 相关文档

- `core/unified_proxy_config.py` - API 文档
- `ui/unified_proxy_panel.py` - UI 组件说明
