# 系统架构手册

## 1. 总体架构

LivingTree 是一个工业级自主 AI Agent 平台，采用分层架构设计：

```
┌──────────────────────────────────────────────────────┐
│                   表示层 (TUI/API)                     │
│  Toad Textual · Relay Server · WeChat Gateway        │
├──────────────────────────────────────────────────────┤
│                   编排层 (Orchestration)               │
│  RealPipeline · PanelAgent · CronScheduler            │
├──────────────────────────────────────────────────────┤
│                   智能层 (Intelligence)                │
│  DualConsciousness · AutonomousLearner · PromptOpt    │
├──────────────────────────────────────────────────────┤
│                   知识层 (Knowledge)                   │
│  KnowledgeBase · DocumentKB · StructMem · Graph       │
├──────────────────────────────────────────────────────┤
│                   路由层 (Routing)                     │
│  TreeLLM · HolisticElection · SkillRouter             │
├──────────────────────────────────────────────────────┤
│                   基础层 (Infrastructure)              │
│  AsyncDisk · TaskGuard · SystemMonitor · Registry     │
└──────────────────────────────────────────────────────┘
```

## 2. 数据流

### 2.1 用户对话流程

```
用户输入 → NeonAgent.send_prompt()
  → PromptOptimizer: 提示词增强 + 动态工具选择
  → TreeLLM: 选举最优免费 provider (5 维评分)
  → CacheOptimizer: 前缀缓存优化 token
  → LLM 流式输出 → ToadOrchestrator: 结构化解析
  → Toad Widgets: AgentResponse/ToolCall/Plan 渲染
  → SessionSearch: FTS5 索引
  → SkillSelfLearn: 分析任务模式
  → CostDashboard: token 成本记录
```

### 2.2 批量文档生成流程

```
/batch data.csv 环评模板
  → BatchGenerator.enqueue_csv(): 解析参数表
  → generate_all(): 4 并发 LLM 调用
  → 进度回调 → 全部完成
  → export_docx(): 导出 DOCX
```

### 2.3 P2P 通信流程

```
Node A (内网)          Relay Server (公网)        Node B (内网)
    │  POST /peers/register    │                        │
    │─────────────────────────►│◄───────────────────────│
    │  {peer_id, location}     │  {peer_id, location}   │
    │                          │                        │
    │  GET /peers/discover     │                        │
    │◄─────────────────────────│                        │
    │  {peers, relay_pool}     │                        │
    │                          │                        │
    │  WS /ws/relay ──────────►│◄───────────────────────│
    │  {"to":"B","data":"hi"}  │  forward →             │
```

## 3. 模型选举

### 3.1 5 维评分体系

| 维度 | 权重 | 计算方式 |
|------|------|---------|
| 质量 | 30% | 最近 20 次调用的加权成功率 |
| 延迟 | 25% | 归一化响应时间 |
| 成本 | 20% | 免费=1.0, 付费=0.3 |
| 能力 | 15% | 查询关键词 vs provider 专长 |
| 新鲜度 | 10% | 24h 内使用过加分 |

### 3.2 选举流程

```
1. 构建候选列表: free_models + paid_models + oc-* + local-*
2. 排除 L4 锁定模型
3. 序列 ping 所有候选
4. 对存活候选 5 维评分
5. 最高分当选
6. 全灭 → 使用 L4
```

## 4. 知识检索架构

### 4.1 多路融合检索

```
用户查询 → expand_query()
  ├→ DocumentKB: FTS5 全文 + embedding cosine → RRF merge
  ├→ KnowledgeBase: bi-temporal cosine
  ├→ StructMem: 层次化记忆检索
  ├→ KnowledgeGraph: 实体链接 + 图遍历
  └→ 结果融合排序 → 返回 top_k
```

### 4.2 情感记忆 (StructMem)

```
每个对话轮次 → 双视角绑定 (FACT + RELATION)
  → 缓冲 ≥ 3 条 + 超过 300s → 跨事件合并
  → 语义检索 → 合成块
```

## 5. 关键设计决策

| 决策 | 原因 |
|------|------|
| 纯 Python，零本地模型加载 | 启动秒级，不依赖 torch |
| Toad 全源集成 | 复用成熟 UI 组件 |
| AsyncDisk 批量写 | 避免热路径磁盘阻塞 |
| UnifiedRegistry 单例 | 30 全局单例 → 1 个 |
| Token 前缀缓存 | DeepSeek 90% 节省 |
| 免费模型优先选举 | 零成本运行 |
| P2P 默认组件 | 节点自动互联 |
