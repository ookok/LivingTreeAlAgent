# 用户手册

## 快速开始

### 安装

```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.sh | bash

# Windows
powershell -c "irm https://raw.githubusercontent.com/ookok/LivingTreeAlAgent/main/install.ps1 | iex"
```

### 启动

```bash
livingtree          # TUI 对话界面
livingtree relay    # 启动中继服务器 (端口 8888)
```

## 登录

首次启动后系统弹出登录界面。使用管理员分配的账户和密码登录。内部验证通过中继服务器 `www.mogoo.com.cn:8888`。

```
/login admin admin123
```

## 对话操作

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Enter | 发送消息 |
| Ctrl+T | 对话面板 |
| Ctrl+E | 代码面板 |
| Ctrl+D | 知识库 |
| Ctrl+K | 工具箱 |
| Ctrl+B | 切换侧栏 |
| Esc | 返回主页 |
| Ctrl+L | 中/英切换 |
| Ctrl+Q | 退出 |

### 鼠标操作

对话面板顶部工具栏可点击执行常用操作，无需键盘快捷键。

## 命令参考

### 搜索与获取

| 命令 | 说明 | 示例 |
|------|------|------|
| `/search <关键词>` | 多引擎搜索 | `/search 大气污染标准` |
| `/fetch <URL>` | 抓取网页内容 | `/fetch https://example.com` |
| `/recall <关键词>` | 搜索历史对话 | `/recall 环评报告` |

### 知识与技能

| 命令 | 说明 | 示例 |
|------|------|------|
| `/tools` | 列出所有工具 | `/tools` |
| `/route <查询>` | 查询路由推荐 | `/route 分析大气数据` |
| `/role [名称]` | 查看/列出角色 | `/role 环评专家` |
| `/graph [节点]` | 技能关系图谱 | `/graph gaussian_plume` |
| `/mine [目录]` | 自动挖掘知识 | `/mine ./docs` |

### 推理与验证

| 命令 | 说明 | 示例 |
|------|------|------|
| `/plan <任务>` | 任务分解规划 | `/plan 编写环评报告` |
| `/factcheck <陈述>` | 事实核查 | `/factcheck SO2标准500μg/m³` |
| `/gaps` | 知识缺口分析 | `/gaps` |
| `/compute <模型> <参数>` | 数值计算 | `/compute gaussian_plume Q=100 u=3.5` |
| `/compliance <标准> <文本>` | 合规检查 | `/compliance GB3095-2012 文本` |

### 文档生成

| 命令 | 说明 | 示例 |
|------|------|------|
| `/batch <CSV> <模板>` | 批量生成文档 | `/batch data.csv 环评报告` |
| `/template list\|save` | 模板管理 | `/template save 环评 内容` |
| `/optimize <提示词>` | 提示词优化 | `/optimize 生成报告` |

### 系统管理

| 命令 | 说明 | 示例 |
|------|------|------|
| `/status` | 系统状态 | `/status` |
| `/sysinfo` | 资源监控 | `/sysinfo` |
| `/cost` | Token 费用 | `/cost` |
| `/cron list\|add` | 定时任务 | `/cron add 每天8点汇总` |
| `/evolve` | 进化状态 | `/evolve` |
| `/login <用户> <密码>` | 登录/切换账户 | `/login admin pass` |

### P2P 网络

| 命令 | 说明 | 示例 |
|------|------|------|
| `/peers` | 发现网络节点 | `/peers` |
| `/connect <ID>` | 连接节点 | `/connect lt-DESKTOP-8d22` |

## 中继服务器

### 部署

```bash
deploy_relay.bat          # Windows
./deploy_relay.sh         # Linux
```

### 管理员后台

`http://www.mogoo.com.cn:8888/admin`

默认管理员: admin / admin123

### 后台功能

- **账户管理**: 添加/删除用户，重置密码
- **费用监控**: 按账户和 Provider 查看 Token 消耗和 RMB 费用
- **负载均衡**: 添加/移除 P2P 中继服务器地址
- **统计重置**: 一键清空节点统计

## Token 成本

费用按 Provider 的每百万 token 单价自动计算，客户端自动上报到中继服务器。

| Provider | 单价 (¥/M tokens) |
|----------|-------------------|
| 硅基流动 | 0.00 (免费) |
| 模力方舟 | 0.00 (免费) |
| 智谱/讯飞/LongCat | 0.00 (免费) |
| DeepSeek | 2.00 |
| 阿里云 | 4.00 |
| 小米 | 8.00 |

## 常见问题

**Q: 无法连接中继服务器？**
A: 检查网络是否能访问 `www.mogoo.com.cn:8888`。节点自动在 3 次失败后切换备用中继。

**Q: LLM 响应慢？**
A: 系统自动选举延迟最低的免费模型。查看 `/sysinfo` 确认资源状况。

**Q: 如何添加新用户？**
A: 管理员登录中继服务器后台 → 账户管理 → 添加账户。

**Q: 如何更新？**
A: `git pull origin main` 或启动时自动检测新版本。
