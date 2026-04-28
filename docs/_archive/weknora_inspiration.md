# WeKnora 设计精华融入指南

> 来源：WeKnora (腾讯开源 RAG + ReAct Agent 知识框架)
> 目标：吸收其"双模响应 + 国产优先 + 模块化全链路"设计思路

---

## 1. 双模响应机制（已在你的架构中体现）

### Quick Q&A (RAG 路径)
```
用户问 → 切块 → 向量检索 → 生成 → 秒回
```
- 适用：简单事实查询（运费、多少、状态）
- 你的实现：FusionEngine L1/L2 缓存层

### Intelligent Reasoning (ReAct 路径)
```
用户问 → Thought → Action → Observation → ... → 最终答案
```
- 适用：复杂决策（性价比对比、风险分析、多步骤规划）
- 你的实现：L4 RelayExecutor + L3 蒸馏路由层

### 融合建议
```python
# 在 FusionEngine 中新增路由决策
def decide_mode(query: str, complexity_hint: float = 0.5) -> str:
    if complexity_hint > 0.7 or contains_reasoning_markers(query):
        return "react"  # 深思模式
    return "rag"  # 快答模式
```

---

## 2. 国产模型路由强化

### WeKnora 原生支持
- DeepSeek / Qwen / 智谱 / 混元
- Ollama 本地并列

### 你的 RelayFreeLLM 已有
- DeepSeek (priority 750)
- 通义 DashScope (priority 600)
- 智谱 GLM (priority 600)
- 火山方舟 (priority 550)

### 待补全
| 模型 | 优先级 | 用途 |
|------|--------|------|
| 腾讯混元 | 650 | 国产替代 |
| 百度文心 | 600 | 国产替代 |
| 讯飞星火 | 580 | 语音交互 |

---

## 3. 数据源解析增强（借鉴 WeKnora）

### WeKnora 支持
- Feishu/飞书文档
- PDF/Word/Excel/图片 (含 OCR)
- Markdown/Text

### 你的 PageIndex 已支持
- 代码片段
- 技术文档
- Markdown

### 差距与改进点
1. **Office 文档深度解析**：Excel 表格结构、Word 段落语义
2. **OCR 集成**：图片转文字（商品标签、发票）
3. **飞书同步**：卖家商品库 → 飞书知识库

---

## 4. ReAct 循环实现参考

```python
class ReActAgent:
    """借鉴 WeKnora 的 ReAct 循环"""

    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools  # MCP 工具注册表

    async def think_act_observe(self, query: str, max_turns=5):
        """单轮 Thought-Action-Observation"""
        context = {"query": query, "thoughts": [], "actions": []}

        for _ in range(max_turns):
            # 1. Thought: LLM 决定下一步行动
            thought = await self.llm.generate(
                prompt=f"分析: {context['query']}\n已执行: {context['actions']}\n决定:"
            )
            context["thoughts"].append(thought)

            # 2. Action: 解析并执行工具
            action = self.parse_action(thought)
            if not action:
                break  # 无需更多行动，直接回答

            result = await self.execute_tool(action)
            context["actions"].append({action: result})

            # 3. Observation: 结果注入上下文
            if self.is_final_answer(result):
                return self.format_answer(result)

        return self.format_answer(context)
```

---

## 5. MCP 工具编排（你的优势）

WeKnora 通过 MCP 注入外部工具。你的架构天然支持：

| 工具 | 对应能力 | 场景 |
|------|----------|------|
| WPS/OfficeCLI | 文档操作 | 合同生成、报表导出 |
| FFmpeg | 媒体处理 | 商品视频剪辑 |
| Agent-Reach | 联网搜索 | 竞品分析、价格核查 |
| PageIndex | 知识检索 | 技术文档查询 |

---

## 6. IM 交付集成

### WeKnora 支持
- 飞书
- 企业微信
- Slack

### 你的电商场景
```
买家群问"订单状态"
    ↓
Agent 查询订单系统
    ↓
结果直接回群（企业微信/飞书机器人）
```

### 实现路径
```python
# core/im_delivery.py
class IMDelivery:
    async def send_to_wechat(self, group_id: str, message: str):
        """发送至企业微信群"""

    async def send_to_feishu(self, group_id: str, message: str):
        """发送至飞书群"""
```

---

## 7. 融入你的现有架构

```
┌─────────────────────────────────────────────────────┐
│                    用户请求                          │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  FusionEngine (你的四级缓存金字塔)                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ L1 内存  │→│ L2 向量 │→│ L3 蒸馏 │→│ L4 Relay│   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
└─────────────────────┬───────────────────────────────┘
                      │ 未命中
                      ▼
┌─────────────────────────────────────────────────────┐
│  双模决策 (WeKnora 启发)                            │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ Quick Q&A (RAG)  │  │ Intelligent     │        │
│  │ 简单问题秒回      │  │ Reasoning (ReAct)│        │
│  └──────────────────┘  │ 复杂问题拆解     │        │
│                        └──────────────────┘        │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  RelayFreeLLM (你的异构模型池)                       │
│  本地 Ollama → 国产云 → 国际云 → 聚合平台            │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  IM 交付 (WeKnora 启发)                             │
│  企业微信 / 飞书 / Slack → 结果直达群聊              │
└─────────────────────────────────────────────────────┘
```

---

## 8. 下一步行动清单

- [ ] **L4 执行器增强**：集成 ReAct 循环
- [ ] **国产模型补全**：添加混元/文心/星火
- [ ] **IM 交付模块**：企业微信/飞书 集成
- [ ] **文档解析增强**：PDF/Excel/OCR 支持

---

*本文档为设计指南，不含 WeKnora 源代码，仅吸收其架构思路*
