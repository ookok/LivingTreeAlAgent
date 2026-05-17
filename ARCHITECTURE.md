# ARCHITECTURE.md — LivingTree 目标架构与迁移路线图

## 现状问题

### 1. 36 对循环依赖
- **capability ↔ treellm** (20↔12 文件) — `capability_bus.py` 是耦合中枢
- **core ↔ dna** (17↔10) — 启动顺序耦合
- **core ↔ treellm** (14↔16) — 共享基础设施过度交织

### 2. integration 超级扇出 (165 次出向引用)

### 3. 缺乏接口抽象层

---

## 目标架构 (依赖方向 ↓ only)

```
入口层:   api, integration
            ↓
编排层:   execution, dna, capability
            ↓
领域层:   knowledge, memory, economy
            ↓
基础层:   bridge ← treellm, core
            ↓
静态层:   config, observability, infra
```

规则: 上层依赖下层，禁止反向。bridge 提供接口抽象。

---

## 迁移路线图

### ✅ 阶段 1 — 完成
- Router/Classifier 合并
- htmx_web 模块化 (11 子模块)
- hub Mixin 提取
- bridge/ 抽象层创建

### 🔄 阶段 2 — 依赖反转
- treellm/capability_bus.py → bridge.ToolRegistry
- capability/ 模块注册到 registry

### ⏳ 阶段 3
- core/dna 插件化解耦
- integration 依赖面缩减
- api 穿透修复

### ⏳ 阶段 4
- 循环依赖归零

---

## 当前循环依赖状态

| 对 | 程度 | 计划 |
|----|:---:|------|
| capability↔treellm | 20↔12 | bridge迁移 |
| core↔dna | 17↔10 | 插件化 |
| core↔treellm | 14↔16 | 稳定基础 |
| api↔core | 53↔1 | 穿透修复 |
