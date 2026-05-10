# LivingTree v5.0 — System Architecture

> 生命之树系统架构手册 · 77+模块 · 12器官 · 7层自进化

---

## 系统全景

```
┌──────────────────────────────────────────────────────────────┐
│                    入口层 (Entry Layer)                       │
│  Living Canvas (/tree/living) · Admin Console (/api/admin)    │
│  TUI (Textual) · CLI · API (60+ endpoints)                    │
├──────────────────────────────────────────────────────────────┤
│                    UI层: Living Canvas v5.0                   │
│  dynamic_page · kami_theme · living_presence · anime_persona  │
│  cognition_stream · interactive_tools · creative_viz          │
├──────────────────────────────────────────────────────────────┤
│                  Core Layer v5.0 (18 new modules)             │
│  shell_env · perf_accel · adaptive_folder · final_polish     │
│  behavior_control · dpo_prefs · collective_intel · agent_qa   │
│  resilience_brain · capability_scanner · universal_scanner    │
│  admin_manager · model_spec                                   │
├──────────────────────────────────────────────────────────────┤
│               Core Layer (existing 45+ modules)               │
│  dna/ · knowledge/ · execution/ · treellm/ · capability/      │
│  economy/ · cell/ · tui/ · observability/ · config/           │
├──────────────────────────────────────────────────────────────┤
│              Network Layer v5.0 (8 new modules)               │
│  nat_traverse · reach_gateway · swarm_coordinator             │
│  im_core · webrtc_remote · universal_pairing                 │
│  message_bus · discovery                                       │
├──────────────────────────────────────────────────────────────┤
│              Network Layer (existing)                         │
│  p2p_node · relay_server · scinet_* · proxy_fetcher          │
│  encrypted_channel · node · reputation · collective           │
├──────────────────────────────────────────────────────────────┤
│                External Infrastructure                        │
│  Relay Server (port 8899) · Docker · FRP · K8s                │
└──────────────────────────────────────────────────────────────┘
```

## 12 器官系统

| 器官 | 生物类比 | 工程模块 |
|------|---------|---------|
| 👁️ Eyes | 视觉感知 | OCR · 文档解析 · 天气API · 网页抓取 |
| 👂 Ears | 听觉/事件 | EventBus · MCP工具发现 · 资源树搜索 |
| 🧠 Brain | 意识 | 现象意识 · 哥德尔自指 · 涌现检测 |
| ❤️ Heart | 心脏/内驱力 | 自主生长守护进程 · LifeDaemon |
| 🫁 Lungs | 呼吸/缓存 | KV上下文缓存 · 懒文档索引 |
| 🫀 Liver | 肝脏/安全 | SafetyGuard · CoFEE · 自复制防护 |
| 🩸 Blood | 血液/经济 | 经济编排器 · ROI追踪 · 成本降级链 |
| 🤲 Hands | 手/工具 | 研究员团队 · 代码工匠 · 工具市场 |
| 🦵 Legs | 腿/执行 | 沙盒执行器 · SSH · Docker部署 |
| 🦴 Bones | 骨骼/编排 | GTSM统一规划器 · Pipeline |
| 🛡️ Immune | 免疫/策略 | 安全策略 · Guidelines · ARQ验证 |
| 🌱 Reproductive | 生殖/繁衍 | 细胞有丝分裂 · 蓝图导入 · 群体同步 |

## 7 层自进化 (零模型训练)

```
Layer 1: 记忆分层 (HOT/WARM/COLD)
  └─ 频率驱动 + 时间衰减, 自动升降级

Layer 2: 记忆→技能结晶
  └─ 验证3次 → 自动注册为可复用技能

Layer 3: DPO 偏好学习
  └─ 每次 ✓/✕ 更新评分, 无需RL

Layer 4: 宪法/行为控制
  └─ Model Spec + Guidelines 硬约束

Layer 5: 细胞繁殖
  └─ 成功模式分裂为子代理

Layer 6: 群体同步
  └─ 一个节点学会 → 全网受益

Layer 7: 上下文折叠
  └─ 边界压缩, 省token提质量
```

## 自适应触发流

```
页面加载 → dynamic_page + kami_theme + living_presence + anime_persona
用户输入 → cognition_stream + model_spec(宪法注入)
LLM回复 → behavior_control(ARQ验证) + adaptive_folder(折叠)
         → final_polish(预计算) + collective_intel(存储记忆)
用户 ✓/✕ → dpo_prefs(偏好更新)
3次验证  → 记忆→技能结晶化
服务上线 → capability_scanner(发现+注册)
网络波动 → resilience_brain(降级+预缓存)
节点发现 → nat_traverse(打洞) + swarm_coordinator(直连)
```

## 数据流

```
用户请求 → FastAPI (routes.py)
         → Hub (integration/hub.py)
         → LifeEngine (dna/life_engine.py)
            ├─ perceive: 意图识别
            ├─ cognize: 工具匹配 + 记忆召回
            ├─ plan: GTSM规划
            ├─ execute: 工具调用 + 沙盒执行
            ├─ reflect: 自我反思
            └─ evolve: 记忆存储 + 偏好更新
         → 响应优化: behavior_control → adaptive_folder
         → 返回: SSE流式 → HTMX渲染
```

## 通信协议

| 层 | 协议 | 用途 |
|----|------|------|
| 浏览器↔服务器 | HTTPS + SSE + WebSocket | UI + 实时推送 |
| P2P节点间 | Protobuf (message_bus) | 二进制消息(14x更小) |
| WebRTC | DTLS-SRTP | 音视频 + 远程运维 |
| 中继 | HTTP + WebSocket | 节点发现 + 消息路由 |
| LAN发现 | UDP广播 (port 9999) | 局域网节点感知 |
| Push | Web Push API | 浏览器通知 |

## 部署架构

```
单机:    python -m livingtree server (port 8100)
中继:    python relay_server.py --port 8899
Docker:  docker run -p 8899:8899 livingtree-relay
K8s:     deploy/k8s/deployment.yml (3 replicas, HPA 2-10)
EXE:     build_relay_exe.py → dist/relay_server.exe
```

## 17 业务面板

```
用户可见: 报告 · 任务 · 感官 · Shell · IM · 远控 · 配对 · 创意
管理员:   费用 · ROI · 群体 · 韧性 · 北极星 · QA · CI · 行为 · DPO
```

## 核心端点

```
/tree/living           Living Canvas
/tree/dynamic?message= LLM动态生成页面
/tree/sse/cognition    认知流 SSE
/ws/im                 IM WebSocket
/ws/rtc-signal         远程运维 WebRTC
/api/admin             管理员控制台
/api/admin/config/chat 对话式配置
```

## 设计原则

1. **AI 生成一切** — 页面结构、工具选择、布局全部由 LLM 动态决定
2. **零手动调用** — 所有新增模块自适应触发
3. **零模型训练** — 7层系统学习替代模型微调
4. **Kami 设计** — 所有 UI 遵循 Kami Token 系统
5. **二进制优先** — P2P 消息使用 Protobuf
6. **管理面板隐藏** — 终端用户不可见, ⚙ 入口
