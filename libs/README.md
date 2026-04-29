# OpenCode 集成指南

## 📦 概述

本目录包含 OpenCode CLI 和 oh-my-opencode 插件的集成代码，用于在 LivingTree AI Agent 中使用 OpenCode 的强大功能。

## 📁 目录结构

```
libs/
├── opencode-core/              # OpenCode CLI 核心 (嵌入式)
│   ├── cmd/                    # CLI 命令
│   ├── internal/               # 内部实现
│   ├── scripts/                # 脚本
│   └── main.go                 # 入口
│
├── oh-my-opencode-plugin/      # oh-my-opencode 插件 (嵌入式)
│   ├── src/                    # 源代码
│   ├── dist/                   # 构建输出
│   └── README.md               # 官方文档
│
├── opencode_integration/       # 集成层代码
│   ├── opencode_manager.py     # 主管理器
│   └── __init__.py             # 包初始化
│
└── README.md                   # 本文档
```

## 🚀 安装步骤

### 方法一：自动设置（推荐）

```bash
# 进入项目目录
cd d:/mhzyapp/LivingTreeAlAgent

# 运行设置脚本
python libs/opencode_integration/opencode_manager.py setup
```

### 方法二：手动安装

#### 1. 克隆 OpenCode 核心仓库

```bash
cd libs/
git clone --depth 1 https://github.com/opencode-ai/opencode.git opencode-core
```

#### 2. 克隆 oh-my-opencode 插件

```bash
git clone https://github.com/code-yeongyu/oh-my-opencode.git oh-my-opencode-plugin
```

#### 3. 安装 OpenCode CLI

```bash
# Linux/macOS
cd opencode-core && ./install

# Windows
cd opencode-core && bash install
```

#### 4. 构建 oh-my-opencode

```bash
# 安装 Bun (如果未安装)
curl -fsSL https://bun.sh/install | bash

# 构建插件
cd oh-my-opencode-plugin
bun install
bun run build
```

#### 5. 配置

```bash
# 创建配置目录
mkdir -p ~/.config/opencode

# 添加插件配置
cat > ~/.config/opencode/opencode.json << 'EOF'
{
  "plugin": [
    "file:///path/to/oh-my-opencode-plugin/dist/index.js"
  ]
}
EOF
```

## 🔧 使用方法

### Python API

```python
from libs.opencode_integration import get_integration, OpenCodeConfig

# 获取集成实例
integration = get_integration()

# 检查前置条件
prereqs = integration.check_prerequisites()
print(prereqs)

# 初始化设置
integration.setup()

# 获取状态信息
info = integration.get_info()
print(info)

# 同步上游更新
integration.sync_upstream()
```

### 命令行

```bash
# 设置
python libs/opencode_integration/opencode_manager.py setup

# 同步上游
python libs/opencode_integration/opencode_manager.py sync

# 查看状态
python libs/opencode_integration/opencode_manager.py status

# 查看信息
python libs/opencode_integration/opencode_manager.py info
```

## 🔌 插件系统

### oh-my-opencode 插件功能

| 功能 | 描述 |
|------|------|
| 🤖 后台代理 | 多智能体协作支持 |
| 🛠️ 预构建工具 | LSP/AST/MCP 集成 |
| ⚙️ 代理配置 | 精选的代理配置 |
| 🔄 Claude 兼容 | 兼容 Claude Code |
| ⚡ Sysphus Agents | 开箱即用的赛博军团 |

### 安装额外插件

```python
integration.install_plugin("/path/to/plugin.js")
```

## 🔄 同步上游代码

### 同步所有仓库

```python
from libs.opencode_integration import get_integration
integration = get_integration()
results = integration.sync_upstream()
```

### 强制同步（覆盖本地修改）

```python
results = integration.sync_upstream(force=True)
```

## 📝 常见问题

### Q: git clone 失败怎么办？

A: 由于网络问题，可以尝试：
1. 使用代理
2. 设置 Git 镜像
3. 手动下载 zip 包

```bash
# 使用 Gitee 镜像 (中国用户)
git clone https://gitee.com/mirrors/opencode.git opencode-core

# 或手动下载
wget https://github.com/opencode-ai/opencode/archive/refs/heads/main.zip
```

### Q: bun 命令未找到？

A: 安装 Bun：
```bash
# Linux/macOS
curl -fsSL https://bun.sh/install | bash

# Windows (PowerShell)
powershell -c "irm bun.sh/install.ps1 | iex"
```

### Q: oh-my-opencode 构建失败？

A: 使用 npm 作为备选：
```bash
cd oh-my-opencode-plugin
npm install
npm run build
```

## 📚 参考资源

- [OpenCode 官网](https://opencode.ai/)
- [OpenCode GitHub](https://github.com/opencode-ai/opencode)
- [oh-my-opencode GitHub](https://github.com/code-yeongyu/oh-my-opencode)
- [OpenCode 插件文档](https://opencode.ai/docs/zh-cn/plugins/)

## 📄 许可证

本集成代码与上游项目保持相同许可证。
