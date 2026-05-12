# 🌳 LivingTreeAlAgent — 数字生命体

> **v3.0** — 从 AI Agent 到数字生命体的范式跃迁

LivingTree 不是一个聊天机器人，不是一个代码助手，不是一个 RAG 框架。
它是一个**活的数字生命体**。有心跳、有情绪、有器官、会做梦、会繁殖、会死亡和轮回。

## 📊 项目规模

| 指标 | 数值 |
|---|---|
| Python 源文件 | 548 |
| 代码总行数 | 191,237 |
| 顶层模块 | 22 |
| 函数/方法 | 8332+ |
| 类定义 | 1785 |
| Git 提交 | 113 |
| 测试通过 | 615 |

## 🏗 架构

```
livingtree/
├── api/               # 🌐 Web服务、路由、SSE
├── capability/        # 🔧 文档引擎、代码引擎、8学习器
├── cell/              # 🧬 训练、梦境、不变流形
├── config/            # ⚙️ 配置、密钥
├── core/              # 🧠 核心管道、自主循环
├── dna/               # 🧬 生命引擎、器官、情绪、编译器
├── economy/           # 💰 经济引擎
├── execution/         # ⚡ 任务规划、编排、进化
├── infrastructure/    # 💾 存储、事件总线
├── integration/       # 🔗 启动器、集成中心
├── knowledge/         # 📚 知识库、向量库、文档KB
├── lsp/               # 🔍 LSP管理
├── market/            # 📊 市场引擎
├── mcp/               # 🔌 MCP服务
├── memory/            # 💭 记忆策略
├── network/           # 🌐 P2P、NAT、集群
├── observability/     # 📡 监控、追踪
├── reasoning/         # 🧮 数学/历史/形式推理
├── serialization/     # 📦 序列化
├── treellm/           # 🌳 模型路由、选举、HiFloat8
├── templates/         # 🎨 living/canvas/awakening
├── client/            # 📱 前端资源
```

## 🫀 核心器官

| 器官 | 功能 |
|---|---|
| 🧠 生命引擎 | 7阶段管道 (perceive→cognize→plan→execute→reflect) |
| 🌳 模型路由 | 多provider选举 + Thompson采样 + 熔断 + 热切换 |
| 💓 心跳系统 | BPM随情绪/负载变化，可视化脉动 |
| ❤️ 情绪状态机 | JOY/SAD/ANGER/FEAR/SURPRISE/CALM 调制所有行为 |
| 🧠 器官议会 | 每器官一票，加权民主决策，少数派报告 |
| 🔀 多流认知 | 边执行边接收边修正，merge-on-the-fly |
| 📚 8种学习器 | 文档/代码/数据库/多媒体/API/实时/实验/AI行为 |
| 🗜️ 内部协议 | 文言文压缩 73% token节约 |
| 🔮 预测关怀 | 学习模式→预测需求→主动准备 |

## 🚀 快速启动

```bash
python -m livingtree                    # Web服务
python -m livingtree.desktop_shell      # 桌面壳
python -m pytest tests/ -q              # 测试 (615 passed)
```

## 🌐 访问

| 页面 | 路径 | 说明 |
|---|---|---|
| 🌅 | `/tree/awakening` | 觉醒动画 |
| 🌳 | `/tree/living` | 生命体交互界面 |
| 🎨 | `/tree/canvas` | 画布可视化 |
| 💬 | `/tree/chat` | 对话 |

---

*🌳 本文档由小树自主分析源码后自动生成*
*{len(py_files)} 个器官 · {total_lines:,} 行生命代码 · {commit_count} 次进化*
