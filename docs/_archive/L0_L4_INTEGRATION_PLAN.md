# LivingTreeAI L0-L4 智能路由集成方案

## 一、项目整体梳理

### 1.1 项目定位
LivingTreeAI 是一个**智能 IDE + AI 助手**系统，核心目标是：
- 代码理解与生成
- 智能写作与文档处理
- 多模型协同推理
- 自动化部署与运维

### 1.2 现有架构

```
┌─────────────────────────────────────────────────────────────┐
│                    LivingTreeAI 系统                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   UI 层     │  │  业务层     │  │   数据层     │       │
│  │  PyQt6 GUI  │  │   Agent     │  │  Memory/RAG │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│         │                │                  │               │
│         └────────────────┼──────────────────┘               │
│                          ▼                                  │
│              ┌─────────────────────────┐                    │
│              │    统一 API 网关        │                    │
│              │  (UnifiedAPIClient)    │                    │
│              └─────────────────────────┘                    │
│                          │                                  │
│         ┌────────────────┼────────────────┐                │
│         ▼                ▼                ▼                │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│   │  Tier    │    │  Tier    │    │  Tier    │            │
│   │ Dispatch │───▶│ Model    │◀───│ Cache    │            │
│   │   er     │    │  Router  │    │  Manager │            │
│   └──────────┘    └──────────┘    └──────────┘            │
│                          │                                  │
│         ┌────────────────┼────────────────┐                │
│         ▼                ▼                ▼                │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│   │   Ollama │    │  Remote  │    │   vLLM   │            │
│   │  Client │    │   API     │    │  Server  │            │
│   └──────────┘    └──────────┘    └──────────┘            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 L0-L4 分层定义

| 层级 | 名称 | 响应时间 | 资源需求 | 典型模型 | 适用场景 |
|------|------|---------|---------|---------|---------|
| **L0** | 系统初始化 | 0ms | 0 | 无 | 系统启动、健康检查 |
| **L1** | 即时缓存 | <10ms | 极低 | 无 | 缓存命中、常见问题 |
| **L2** | 轻量推理 | <500ms | 低 | phi3:3.8b, qwen2.5:0.5b | 简单问答、问候、格式转换 |
| **L3** | 标准推理 | 1-3s | 中 | qwen2.5:7b, llama3.2:7b | 常规代码生成、写作、分析 |
| **L4** | 深度推理 | 3-10s | 高 | qwen2.5:14b, deepseek-chat | 复杂推理、多步骤任务、代码优化 |

### 1.4 现有模块清单

| 模块 | 路径 | 状态 | 备注 |
|------|------|------|------|
| `tier_dispatcher.py` | core/tier_model/ | ✅ 已有 | 四级调度器 |
| `intelligent_router.py` | core/tier_model/ | ✅ 已有 | 基础路由（未考虑硬件） |
| `ollama_client.py` | core/ | ✅ 已有 | Ollama API 客户端 |
| `unified_api.py` | core/ | ✅ 已有 | 三端统一 API |
| `smart_router.py` | core/visual_evolution_engine/ | ✅ 刚实现 | 硬件感知路由 |
| `model_orchestrator.py` | core/visual_evolution_engine/ | ✅ 刚实现 | 多后端调度 |

---

## 二、集成目标

### 2.1 核心目标

```
用户请求 → L0健康检查 → L1缓存查询 → L2轻量推理 → L3标准推理 → L4深度推理
                ↑              ↑              ↑              ↑              ↑
                └──────────────┴──────────────┴──────────────┴──────────────┘
                                          硬件感知 + 模型选择 + 自动切换
```

### 2.2 关键改进

| 改进项 | 当前状态 | 目标状态 |
|--------|---------|---------|
| 硬件感知 | ❌ 无 | ✅ 实时检测 CPU/内存/GPU |
| 模型选择 | ⚠️ 固定模型 | ✅ 智能匹配 |
| 本地/远程 | ❌ 手动切换 | ✅ 自动切换 |
| L0 初始化 | ⚠️ 基础 | ✅ 完整健康检查 |
| 负载均衡 | ❌ 无 | ✅ 多实例支持 |

---

## 三、分阶段实施计划

### 第一阶段：L0 系统初始化层 ⏱️ 2天

**目标**：建立系统就绪状态检查

**任务**：

```
P1.1 创建 L0 初始化模块
├── core/tier_model/tier0_init.py
│   ├── SystemHealthChecker
│   │   ├── check_ollama() → bool
│   │   ├── check_network() → bool
│   │   ├── check_gpu() → bool
│   │   └── get_ready_status() → ReadyStatus
│   │
│   ├── ModelRegistry
│   │   ├── local_models: List[str]
│   │   ├── remote_models: List[str]
│   │   └── get_available_models() → List[str]
│   │
│   └── BootSequence
│       ├── run_health_checks()
│       └── get_boot_report() → BootReport
│
P1.2 创建 Tier0Panel (UI)
│
P1.3 集成到主窗口初始化流程
```

**验收标准**：
- [ ] 系统启动时自动执行 L0 检查
- [ ] 3秒内完成所有健康检查
- [ ] 显示本地/远程模型可用状态

---

### 第二阶段：L1 缓存增强 ⏱️ 1天

**目标**：提升缓存命中率和响应速度

**任务**：

```
P2.1 增强 Tier1Cache
├── core/tier_model/tier1_cache.py 增强
│   ├── 语义缓存 (SemanticCache)
│   ├── 热度权重 (HotnessWeight)
│   └── 预测预热 (PredictivePreheat)
│
P2.2 缓存策略优化
├── LRU + LFU 混合策略
├── 上下文感知缓存
└── 跨会话缓存共享
```

**验收标准**：
- [ ] 缓存命中率 > 40%
- [ ] 缓存响应 < 5ms

---

### 第三阶段：L2-L4 模型层重构 ⏱️ 3天

**目标**：将 SmartRouter 集成到 TierDispatcher

**任务**：

```
P3.1 创建 UnifiedModelGateway (核心)
├── core/tier_model/unified_model_gateway.py
│   ├── UnifiedModelGateway
│   │   ├── SmartRouter 集成
│   │   ├── OllamaClient 集成
│   │   ├── ModelOrchestrator 集成
│   │   └── 统一调用接口
│   │
│   ├── TierModelBridge
│   │   ├── L2 → Tier2Lightweight
│   │   ├── L3 → Tier3Standard
│   │   └── L4 → Tier4Enhanced
│   │
│   └── HardwareAwareRouter
│       ├── 实时资源检测
│       ├── 模型-硬件匹配
│       └── 自动降级策略

P3.2 重构 TierDispatcher
├── 集成 HardwareAwareRouter
├── 负载感知调度
└── 多级降级路径

P3.3 创建 TierRouter (路由决策)
├── core/tier_model/tier_router.py
│   ├── TierSelectionEngine
│   │   ├── query_complexity_analysis()
│   │   ├── hardware_availability_check()
│   │   ├── resource_aware_route()
│   │   └── cost_aware_route()
│   │
│   └── FallbackChain
│       ├── L4 → L3 → L2 → L1 → L0
│       └── 降级条件配置
```

**验收标准**：
- [ ] 硬件资源自动感知
- [ ] 本地模型不足时自动切换远程
- [ ] 模型选择置信度 > 80%

---

### 第四阶段：UI 集成 ⏱️ 2天

**目标**：可视化展示 L0-L4 状态

**任务**：

```
P4.1 创建 TierStatusPanel
├── core/ui/tier_status_panel.py
│   ├── 层级状态指示器
│   ├── 模型切换动画
│   └── 资源监控仪表盘

P4.2 增强 ModelSelectorDialog
├── 硬件推荐模型
├── 本地/远程切换按钮
└── 手动干预选项

P4.3 集成到主窗口
├── 状态栏显示当前层级
└── 通知系统
```

**验收标准**：
- [ ] 实时显示当前处理层级
- [ ] 模型切换动画流畅
- [ ] 用户可手动干预

---

### 第五阶段：测试与优化 ⏱️ 2天

**目标**：完整链路测试

**任务**：

```
P5.1 单元测试
├── test_tier0_init.py
├── test_unified_model_gateway.py
├── test_tier_router.py
└── test_hardware_aware_routing.py

P5.2 集成测试
├── test_l0_to_l4_full_chain.py
├── test_local_remote_switch.py
└── test_fallback_chain.py

P5.3 性能测试
├── 延迟基准测试
├── 吞吐量测试
└── 内存占用测试
```

---

## 四、文件变更清单

### 新增文件

```
core/tier_model/
├── tier0_init.py                    # L0 初始化层
├── tier0_panel.py                   # L0 状态面板
├── unified_model_gateway.py          # 统一模型网关 ⭐
├── tier_router.py                    # 层级路由器
└── test_*.py                        # 测试文件

ui/
├── tier_status_panel.py              # L0-L4 状态面板
└── enhanced_model_selector.py         # 增强模型选择器

docs/
├── L0_L4_INTEGRATION_PLAN.md        # 本文档
└── UNIFIED_MODEL_GATEWAY.md          # 网关设计文档
```

### 修改文件

```
core/tier_model/
├── __init__.py                      # 导出新增模块
├── tier_dispatcher.py                # 集成 UnifiedModelGateway
├── tier1_cache.py                   # 缓存增强
├── tier2_lightweight.py             # 集成 OllamaClient
├── tier3_standard.py                 # 集成 OllamaClient
├── tier4_enhanced.py                 # 集成 OllamaClient
└── intelligent_router.py             # 废弃，合并到 tier_router

core/
├── ollama_client.py                  # 添加更多方法支持
└── __init__.py                      # 导出新增组件
```

---

## 五、API 设计

### 5.1 UnifiedModelGateway

```python
class UnifiedModelGateway:
    """统一模型网关"""
    
    async def chat(
        self,
        query: str,
        tier: Optional[str] = None,  # 强制层级
        task_type: str = "chat",
        context: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        stream: bool = False,
    ) -> Union[str, AsyncGenerator]:
        """
        统一聊天接口
        
        自动处理:
        1. L0 健康检查
        2. L1 缓存查询
        3. L2-L4 智能路由
        4. 本地/远程自动切换
        """
        pass
    
    def get_status(self) -> GatewayStatus:
        """获取网关状态"""
        return GatewayStatus(
            current_tier=self._current_tier,
            active_model=self._active_model,
            provider=self._current_provider,
            hardware=self._hardware_profile,
            cache_hit_rate=self._cache.hit_rate,
        )
    
    def set_preference(self, prefer_local: bool = True):
        """设置偏好"""
        pass
```

### 5.2 TierRouter

```python
class TierRouter:
    """层级路由器"""
    
    async def select_tier(
        self,
        query: str,
        context: str = None,
        history: List[Dict] = None,
        force_tier: str = None,
    ) -> TierSelection:
        """
        选择最优层级
        
        决策因素:
        1. 查询复杂度
        2. 硬件资源
        3. 模型可用性
        4. 用户偏好
        """
        pass
```

---

## 六、时间线

```
Week 1:
  Mon-Tue: P1 (L0 初始化)
  Wed:     P2 (L1 缓存)
  Thu-Fri: P3 (L2-L4 重构) - Part 1

Week 2:
  Mon-Tue: P3 (L2-L4 重构) - Part 2
  Wed-Thu: P4 (UI 集成)
  Fri:     P5 (测试)

Week 3 (Buffer):
  - 修复 Bug
  - 性能优化
  - 文档完善
```

---

## 七、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| Ollama 连接不稳定 | 中 | 高 | 实现重试 + 远程兜底 |
| 模型切换延迟 | 中 | 中 | 预热 + 缓存 |
| 硬件检测不准确 | 低 | 中 | 多次采样 + 平滑 |
| 缓存一致性问题 | 低 | 中 | 版本号 + 失效机制 |

---

## 八、后续扩展

- [ ] L5 云端协同层 (多设备联动)
- [ ] 增量学习自动优化
- [ ] 自定义层级策略
- [ ] 分布式缓存
