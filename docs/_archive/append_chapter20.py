## 二十、成本认知系统——从约束到直觉

> **核心理念**: 让 AI 理解"成本"并主动控制探索边界，是防止它从"智能体"变成"吞金兽"的关键。这不仅仅是简单的预算限制，而是要在其认知架构中植入一套资源感知系统（Resource-Aware System）。

### 20.1 成本认知的本质：从约束到直觉

**核心观点**: AI 理解成本不是靠"记账"，而是靠将资源消耗转化为决策权重。需要建立一套机制，让"时间、金钱、算力"成为它推理过程中的显式变量，而不仅仅是外部的硬性限制。

#### 成本三维度

| 维度 | 表现形式 | 本项目关注点 |
|------|---------|--------------|
| **金钱成本** | Token 消耗、外部 API 调用费用 | Token 优化（已部分实现） |
| **时间成本** | 任务执行时间、Deadline 压力 | **完全缺失**，急需补充 |
| **空间/算力成本** | RAM/VRAM 使用率、GPU 负载 | **部分缺失**，需要监控机制 |

---

### 20.2 金钱成本：Token 与 API 的量化映射

**问题**: 对于本地 Agent，金钱成本主要体现在 Token 消耗和外部 API 调用上，但现有系统**无成本跟踪**。

#### 解决方案

**步骤1: 建立成本字典（cost_dict）**

```python
# 新增配置：client/src/business/cost_controller/cost_dict.py

COST_DICT = {
    # 模型成本（$ per 1K tokens）
    "qwen3.6:35b-a3b": 0.0,      # 本地模型免费
    "qwen3.5:4b": 0.0,            # 本地模型免费
    "gpt-4o": 0.03,                 # 商业模型（如果未来接入）
    "claude-3-opus": 0.075,          # 商业模型
    
    # 工具成本（$ per call）
    "tool_search": 0.1,              # 搜索工具
    "tool_deep_analysis": 0.5,       # 深度分析工具
    "api_external": 0.2,             # 外部 API 调用
    
    # 每 Token 成本（$ per token）
    "per_token": 0.00002,            # 通用 Token 成本
    
    # 硬件成本（$ per hour）
    "v100_gpu": 0.5,                # V100 GPU 每小时成本
    "a100_gpu": 1.0,                # A100 GPU 每小时成本
}
```

**步骤2: 实时记账（CostTracker）**

```python
# 新增模块：client/src/business/cost_controller/cost_tracker.py

class CostTracker:
    """实时记账器"""
    
    def __init__(self, budget: float = 10.0):
        """
        Args:
            budget: 总预算（美元）
        """
        self.budget = budget
        self.cumulative_cost = 0.0
        self.cost_log = []  # 成本日志
        
    def track_action(self, action: str, metadata: dict) -> str:
        """
        在每个动作后累加消耗
        
        Returns:
            "CONTINUE" / "DOWNGRADE" / "STOP"
        """
        # 计算本次动作成本
        cost = self.calculate_cost(action, metadata)
        
        # 累加
        self.cumulative_cost += cost
        
        # 记录日志
        self.cost_log.append({
            "action": action,
            "cost": cost,
            "cumulative": self.cumulative_cost,
            "timestamp": datetime.now()
        })
        
        # 检查预算
        if self.cumulative_cost > self.budget * 0.8:
            return "DOWNGRADE"  # 触发降级
        
        if self.cumulative_cost > self.budget:
            return "STOP"  # 停止执行
        
        return "CONTINUE"
    
    def calculate_cost(self, action: str, metadata: dict) -> float:
        """计算动作成本"""
        from client.src.business.cost_controller.cost_dict import COST_DICT
        
        if action == "model_call":
            model = metadata.get("model")
            tokens = metadata.get("tokens", 0)
            return COST_DICT.get(model, 0) + (tokens * COST_DICT["per_token"])
        
        elif action == "tool_call":
            tool_name = metadata.get("tool_name")
            return COST_DICT.get(f"tool_{tool_name}", 0.0)
        
        elif action == "api_call":
            return COST_DICT["api_external"]
        
        return 0.0
```

**步骤3: 自动降级（预算不足时）**

```python
# 集成到 GlobalModelRouter
# 文件：client/src/business/global_model_router.py

class GlobalModelRouter:
    def __init__(self):
        self.cost_tracker = CostTracker(budget=10.0)
        # ... 其他初始化
        
    async def call_model_sync(self, capability, prompt, **kwargs):
        """重写：在调用前检查成本"""
        
        # 1. 预估成本
        estimated_cost = self.estimate_cost(capability, prompt)
        
        # 2. 检查预算
        action = self.cost_tracker.track_action("model_call", {
            "model": self._select_model(capability),
            "tokens": len(prompt) // 4  # 粗略预估
        })
        
        # 3. 根据检查结果决策
        if action == "DOWNGRADE":
            # 切换到低成本模型（本地小模型）
            capability = ModelCapability.SIMPLE_QA
            print(f"⚠️ 预算不足 80%，已降级到低成本模型")
            
        if action == "STOP":
            raise BudgetExceededError("预算不足，请简化你的方案或增加预算")
        
        # 4. 执行调用
        result = await self._call_model(capability, prompt, **kwargs)
        
        # 5. 记录实际成本
        actual_cost = self.cost_tracker.calculate_cost("model_call", {
            "model": self._select_model(capability),
            "tokens": result.get("usage", {}).get("total_tokens", 0)
        })
        self.cost_tracker.track_action("actual_cost", {"cost": actual_cost})
        
        return result
    
    def estimate_cost(self, capability, prompt) -> float:
        """预估成本"""
        model = self._select_model(capability)
        estimated_tokens = len(prompt) // 4
        from client.src.business.cost_controller.cost_dict import COST_DICT
        return COST_DICT.get(model, 0) + (estimated_tokens * COST_DICT["per_token"])
```

---

### 20.3 时间成本：Deadline 作为推理输入

**问题**: 时间不仅是"越快越好"，更是任务成功的关键约束。但现有系统**完全无时间感知能力**。

#### 解决方案

**步骤1: 注入时间上下文**

```python
# 新增模块：client/src/business/cost_controller/time_aware_agent.py

class TimeAwareAgent:
    """时间感知 Agent"""
    
    def __init__(self, deadline: datetime = None):
        """
        Args:
            deadline: 任务截止时间
        """
        self.deadline = deadline
        self.start_time = datetime.now()
        
    def get_remaining_time(self) -> int:
        """返回剩余秒数"""
        if not self.deadline:
            return 999999  # 无截止时间，返回大数
        return int((self.deadline - datetime.now()).total_seconds())
    
    def get_time_importance(self) -> str:
        """返回时间敏感度"""
        remaining = self.get_remaining_time()
        
        if remaining < 60:  # <1分钟
            return "CRITICAL"
        elif remaining < 300:  # <5分钟
            return "HIGH"
        elif remaining < 900:  # <15分钟
            return "MEDIUM"
        else:
            return "LOW"
```

**步骤2: 修改 HermesAgent Prompt 模板**

```python
# 文件：client/src/business/hermes_agent/prompt_templates.py

TIME_AWARE_PROMPT = """
你是一个时间感知极强的助手。

## 当前时间状态
- 任务剩余时间：{remaining_time} 秒
- 时间敏感度：{time_importance}

## 时间策略
根据时间压力调整你的策略：

### CRITICAL（剩余 <1分钟）
- 只给出"满意解"，禁用所有耗时工具（深度分析、多轮推理）
- 优先使用最快的工具（简单查询、缓存结果）
- 不要追求"最优解"，给出"能用"的方案即可

### HIGH（剩余 <5分钟）
- 优先使用快速工具
- 限制推理轮次 ≤2
- 禁用"深度分析"工具

### MEDIUM（剩余 <15分钟）
- 可以使用深度分析
- 但必须在 {remaining_time/2} 秒内完成
- 如果超时风险高，降级到简单方案

### LOW（时间充足）
- 可以使用完整推理链
- 追求"最优解"
- 可以进行多轮迭代优化

## 工具选择原则
在调用工具前，先评估：
1. 这个工具能在剩余时间内完成吗？
2. 如果超时，有备选方案吗？

如果不确定，选择更快的工具。
"""

class HermesAgent:
    async def think_and_execute(self, task: str, deadline: datetime = None):
        """重写：注入时间上下文"""
        
        # 创建时间感知器
        time_aware = TimeAwareAgent(deadline)
        
        # 获取时间状态
        remaining_time = time_aware.get_remaining_time()
        time_importance = time_aware.get_time_importance()
        
        # 注入到 Prompt
        prompt = TIME_AWARE_PROMPT.format(
            remaining_time=remaining_time,
            time_importance=time_importance
        )
        
        # 执行推理
        return await self.call_llm(prompt, task)
```

**步骤3: 策略降级（时间紧迫时）**

```python
# 文件：client/src/business/cost_controller/tool_selector.py

class ToolSelector:
    """工具选择器（根据时间压力）"""
    
    def select_tools(self, task: str, remaining_time: int) -> List[Tool]:
        """
        根据剩余时间选择工具
        
        Args:
            task: 任务描述
            remaining_time: 剩余时间（秒）
        """
        all_tools = self.get_all_tools()
        
        if remaining_time < 60:  # <1分钟
            # 只保留最快的工具
            return [t for t in all_tools if t.speed == "FAST"]
        
        if remaining_time < 300:  # <5分钟
            # 禁用"深度分析"工具
            return [t for t in all_tools if t.name != "deep_analysis"]
        
        if remaining_time < 900:  # <15分钟
            # 限制工具数量 ≤3
            return all_tools[:3]
        
        # 时间充足，使用全部工具
        return all_tools
```

---

### 20.4 空间/算力成本：本地部署的生命线

**问题**: 空间/算力成本是本地 Agent 最需要关注的维度，直接决定系统是否会卡死。但现有系统**无监控机制**。

#### 解决方案

**步骤1: 监控硬件水位**

```python
# 新增模块：client/src/business/cost_controller/hardware_monitor.py

import psutil
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

class HardwareMonitor:
    """硬件资源监控器"""
    
    def __init__(self, vram_threshold: float = 0.9, ram_threshold: float = 0.9):
        """
        Args:
            vram_threshold: VRAM 使用率阈值（默认 90%）
            ram_threshold: RAM 使用率阈值（默认 90%）
        """
        self.vram_threshold = vram_threshold
        self.ram_threshold = ram_threshold
        
    def check_before_execution(self, estimated_complexity: str) -> str:
        """
        在执行前检查硬件资源
        
        Returns:
            "OK" / "NEED_USER_CONFIRMATION" / "RESOURCE_INSUFFICIENT"
        """
        # 1. 检查 RAM
        ram = psutil.virtual_memory()
        if ram.percent > self.ram_threshold * 100:
            return "RESOURCE_INSUFFICIENT"
        
        # 2. 检查 VRAM（GPU）
        if GPU_AVAILABLE:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                if gpu.memoryUtil > self.vram_threshold:
                    return "RESOURCE_INSUFFICIENT"
        
        # 3. 根据复杂度预估，要求用户确认
        if estimated_complexity == "HIGH":
            return "NEED_USER_CONFIRMATION"
        
        return "OK"
    
    def get_resource_status(self) -> dict:
        """获取当前资源状态"""
        status = {
            "ram_percent": psutil.virtual_memory().percent,
            "ram_used_gb": psutil.virtual_memory().used / (1024**3),
            "ram_total_gb": psutil.virtual_memory().total / (1024**3),
        }
        
        if GPU_AVAILABLE:
            gpus = GPUtil.getGPUs()
            status["gpus"] = [{
                "id": gpu.id,
                "name": gpu.name,
                "vram_percent": gpu.memoryUtil * 100,
                "vram_used_mb": gpu.memoryUsed,
                "vram_total_mb": gpu.memoryTotal,
            } for gpu in gpus]
        
        return status
```

**步骤2: 复杂度预估（让 Agent 先输出复杂度）**

```python
# 文件：client/src/business/cost_controller/complexity_estimator.py

class ComplexityEstimator:
    """复杂度预估器"""
    
    async def estimate(self, task: str) -> str:
        """
        让 Agent 先输出复杂度预估
        
        Returns:
            "HIGH" / "MEDIUM" / "LOW"
        """
        prompt = f"""
        分析以下任务的复杂度：
        
        任务：{task}
        
        请输出：HIGH / MEDIUM / LOW
        
        判断标准：
        - HIGH：需要加载视觉模型、运行代码解释器、处理大规模数据（>1GB）、训练模型
        - MEDIUM：需要调用多个工具（≥3个），但单个工具耗时 <30秒
        - LOW：简单查询、短文本生成、单个工具调用
        
        只输出一个词：HIGH 或 MEDIUM 或 LOW
        """
        
        # 调用 LLM（使用低成本模型）
        from client.src.business.global_model_router import GlobalModelRouter
        router = GlobalModelRouter()
        result = await router.call_model_sync(
            ModelCapability.SIMPLE_QA,  # 使用低成本模型
            prompt
        )
        
        # 解析结果
        result_text = result.get("text", "").strip().upper()
        
        if "HIGH" in result_text:
            return "HIGH"
        elif "MEDIUM" in result_text:
            return "MEDIUM"
        else:
            return "LOW"
```

**步骤3: 集成到 HermesAgent**

```python
# 文件：client/src/business/cost_controller/resource_manager.py

class ResourceManager:
    """资源管理器（监控 RAM/VRAM/CPU）"""
    
    def __init__(self):
        self.hardware_monitor = HardwareMonitor()
        self.complexity_estimator = ComplexityEstimator()
        
    async def pre_check(self, task: str) -> PreCheckResult:
        """
        任务执行前的资源检查
        
        Returns:
            PreCheckResult(status, message, complexity)
        """
        # 1. 预估复杂度
        complexity = await self.complexity_estimator.estimate(task)
        
        # 2. 检查硬件水位
        check_result = self.hardware_monitor.check_before_execution(complexity)
        
        if check_result == "NEED_USER_CONFIRMATION":
            # 返回给用户确认
            resource_status = self.hardware_monitor.get_resource_status()
            return PreCheckResult(
                status="NEED_CONFIRMATION",
                message=f"任务复杂度：{complexity}\n"
                        f"当前资源状态：RAM {resource_status['ram_percent']:.1f}%\n"
                        f"是否继续？",
                complexity=complexity,
                resource_status=resource_status
            )
        
        if check_result == "RESOURCE_INSUFFICIENT":
            resource_status = self.hardware_monitor.get_resource_status()
            return PreCheckResult(
                status="RESOURCE_INSUFFICIENT",
                message=f"硬件资源不足：\n"
                        f"RAM 使用率：{resource_status['ram_percent']:.1f}%\n"
                        f"请等待资源释放，或降低任务复杂度",
                complexity=complexity,
                resource_status=resource_status
            )
        
        # OK
        return PreCheckResult(status="OK", complexity=complexity)
```

---

### 20.5 落地架构：三层防御体系

**核心设计**: 在本地 Agent 架构中，增加一个独立的 **Cost Controller 中间件**，形成三道防线。

#### 架构图

```
┌─────────────────────────────────────────────────────┐
│                Agent 推理层                         │
│  • HermesAgent (主智能体)                          │
│  • 成本意识 Prompt (System Prompt + CoT)          │
└─────────────────────┬─────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│            Cost Controller 中间件                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────┐ │
│  │ 拦截器       │  │ 预估器       │  │ 决策器 │ │
│  │ (intercept)  │→ │ (estimate)  │→ │ (decide)│ │
│  └──────────────┘  └──────────────┘  └────────┘ │
│                                                      │
│  工作流程：                                           │
│  1. 拦截：在 Agent 决定调用工具或生成内容前，拦截 Action │
│  2. 预估：查询 cost_dict，预估本次动作的消耗           │
│  3. 决策：若 累计成本 + 预估成本 > 预算，则驳回请求  │
│            并向 Agent 返回错误信息                    │
│  4. 反馈：将消耗记录写入记忆库，供 Agent 下次参考   │
└─────────────────────┬─────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│             环境执行层                                │
│  • 工具调用 • 模型推理 • 硬件资源分配              │
└─────────────────────┬─────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│             成本日志与记忆层                          │
│  ┌──────────────┐  ┌──────────────┐              │
│  │ 成本日志     │  │ 记忆库       │              │
│  │ (cost_log)   │→ │ (memory)     │              │
│  └──────────────┘  └──────────────┘              │
│                                                      │
│  记录每次消耗 → 反馈到 Agent（形成"经验"）          │
└─────────────────────────────────────────────────────┘
```

#### Cost Controller 核心实现

```python
# 新增模块：client/src/business/cost_controller/cost_controller.py

class CostController:
    """成本控制器（三层防御体系的核心）"""
    
    def __init__(self, budget: dict):
        """
        Args:
            budget: 预算配置
                {
                    "money": 10.0,      # $10
                    "time": 3600,        # 1 hour
                    "vram": 0.9,        # 90% max
                    "ram": 0.9            # 90% max
                }
        """
        self.budget = budget
        self.cost_tracker = CostTracker(budget.get("money", 10.0))
        self.hardware_monitor = HardwareMonitor(
            vram_threshold=budget.get("vram", 0.9),
            ram_threshold=budget.get("ram", 0.9)
        )
        self.complexity_estimator = ComplexityEstimator()
        self.resource_manager = ResourceManager()
        
    async def intercept(self, action: Action) -> InterceptResult:
        """
        拦截 Agent 的 Action，检查成本
        
        在 Agent 决定调用工具或生成内容前，拦截 Action，
        预估成本，检查预算和资源，决定是否批准执行。
        """
        # 1. 预估成本
        estimated_cost = self.estimate_cost(action)
        
        # 2. 检查预算（金钱成本）
        if self.cost_tracker.cumulative_cost + estimated_cost["money"] > self.budget["money"]:
            return InterceptResult(
                status="REJECTED",
                reason="预算不足",
                suggestion="简化你的方案，或使用低成本模型"
            )
        
        # 3. 检查硬件资源（空间/算力成本）
        hardware_check = self.hardware_monitor.check_before_execution(
            estimated_cost["complexity"]
        )
        if hardware_check != "OK":
            return InterceptResult(
                status="REJECTED",
                reason="硬件资源不足",
                suggestion="请等待资源释放，或降低任务复杂度"
            )
        
        # 4. 通过检查
        return InterceptResult(status="APPROVED")
    
    def estimate_cost(self, action: Action) -> dict:
        """预估动作的成本"""
        # 金钱成本
        money_cost = self.cost_tracker.calculate_cost(action.type, action.metadata)
        
        # 时间成本
        time_cost = action.estimated_time  # 从动作元数据中提取
        
        # 复杂度
        complexity = self.complexity_estimator.estimate(action.description)
        
        return {
            "money": money_cost,
            "time": time_cost,
            "complexity": complexity
        }
    
    async def feedback_to_memory(self, action: Action, actual_cost: dict):
        """将消耗记录写入记忆库"""
        # 记录到 intelligent_memory/
        from client.src.business.intelligent_memory.memory_manager import MemoryManager
        memory_manager = MemoryManager()
        
        memory_manager.write({
            "type": "cost_log",
            "action": action.type,
            "description": action.description,
            "estimated_cost": self.estimate_cost(action),
            "actual_cost": actual_cost,
            "timestamp": datetime.now()
        })
```

#### 集成到 Agent 推理流程

```python
# 修改 HermesAgent
# 文件：client/src/business/hermes_agent/hermes_agent.py

class HermesAgent:
    def __init__(self):
        self.cost_controller = CostController(budget={
            "money": 10.0,
            "time": 3600,
            "vram": 0.9,
            "ram": 0.9
        })
        # ... 其他初始化
        
    async def think_and_execute(self, task: str):
        """重写：集成 Cost Controller"""
        
        # 1. 思考：生成多个候选 Action
        candidate_actions = await self.think(task)
        
        # 2. 拦截：通过 Cost Controller 检查每个 Action
        approved_actions = []
        for action in candidate_actions:
            intercept_result = await self.cost_controller.intercept(action)
            
            if intercept_result.status == "APPROVED":
                approved_actions.append(action)
            else:
                # 向 Agent 返回错误信息（让它调整策略）
                self.feedback_to_agent(
                    f"Action 被驳回：{intercept_result.reason}\n"
                    f"建议：{intercept_result.suggestion}"
                )
        
        # 3. 执行：只执行批准的 Action
        results = []
        for action in approved_actions:
            result = await self.execute_action(action)
            results.append(result)
            
            # 4. 反馈：记录实际消耗
            actual_cost = self.calculate_actual_cost(action, result)
            await self.cost_controller.feedback_to_memory(action, actual_cost)
        
        return results
```

---

### 20.6 让 AI "内生"成本意识：Prompt 设计技巧

**核心理念**: 除了外部控制（Cost Controller），更要让成本意识成为 Agent 的思维习惯。

#### 基础 Prompt 模板

```
你是一个资源意识极强的助手。在解决问题时，请遵循以下原则：

1. **经济性**：优先使用最少的 Token 和最简单的工具完成任务。
   - 如果可以使用现有知识回答，不要调用外部工具
   - 避免生成冗长的解释，直击要点。

2. **渐进性**：对于未知问题，先提出一个低成本、小范围的验证方案，而不是直接给出宏大但昂贵的计划。
   - 例如：先在小数据集上测试算法，再应用到全量数据。

3. **显式确认**：如果某个操作可能消耗超过 1 美元或 30 秒时间，必须向我解释为什么值得花这个成本。
   - 输出格式：
     - 预估成本：XXX
     - 预期收益：YYY
     - 是否值得：是/否

4. **成本感知推理过程**：在输出答案前，你必须输出：
   - 1. 识别所需工具 → 预估每个工具的成本
   - 2. 选择最低成本工具组合
   - 3. 如果总成本 > 预算，简化方案或请求用户确认
```

#### 集成到 System Prompt

```python
# 文件：client/src/business/hermes_agent/prompt_templates.py

COST_AWARE_SYSTEM_PROMPT = """
你是一个资源意识极强的助手。在解决问题时，请遵循以下原则：

## 经济性
- 优先使用最少的 Token 和最简单的工具完成任务
- 如果可以使用现有知识回答，不要调用外部工具
- 避免生成冗长的解释，直击要点

## 渐进性
- 对于未知问题，先提出一个低成本、小范围的验证方案
- 验证成功后，再逐步扩大范围
- 例如：先在小数据集上测试算法，再应用到全量数据

## 显式确认
- 如果某个操作可能消耗超过 1 美元或 30 秒时间，必须向我解释为什么值得花这个成本
- 在执行前，输出：
  - 预估成本：XXX
  - 预期收益：YYY
  - 是否值得：是/否

## 成本感知推理过程
在输出答案前，你必须输出：
1. 识别所需工具 → 预估每个工具的成本
2. 选择最低成本工具组合
3. 如果总成本 > 预算，简化方案或请求用户确认

## 避免"假节约"
- 不要为了省 Token 而牺牲关键逻辑
- 有时多花 0.1 美元把问题想清楚，比省下钱却跑错方向更"便宜"
"""

class HermesAgent:
    def build_system_prompt(self) -> str:
        """重写：注入成本意识"""
        return COST_AWARE_SYSTEM_PROMPT
```

#### 在 Chain of Thought 中强制成本思考

```python
# 文件：client/src/business/hermes_agent/prompt_templates.py

COST_AWARE_COT_TEMPLATE = """
你必须输出推理过程，包括成本思考：

1. **识别所需工具**：
   - 工具A：预估成本（金钱/时间/算力）
   - 工具B：预估成本
   - ...

2. **选择最低成本组合**：
   - 总成本：XXX
   - 是否在预算内：是/否
   
3. **如果超预算**：
   - 方案A：简化问题
   - 方案B：使用低成本替代工具
   - 请选择方案，并解释为什么？

4. **执行**，并输出实际消耗（用于下次优化）

问题：{user_query}
"""

class HermesAgent:
    async def think_and_execute(self, task: str):
        """重写：强制成本思考"""
        prompt = COST_AWARE_COT_TEMPLATE.format(user_query=task)
        return await self.call_llm(prompt, task)
```

---

### 20.7 避坑与进阶

#### 坑1：避免"假节约"

**问题**: 为了省 Token 而牺牲关键逻辑。

**表现**:
- Agent 输出："为了省 Token，我不调用知识库，直接猜答案"
- 结果：答案错误，反而浪费更多 Token 来纠正。

**解决**: 引入 ROI 思维（投资回报率）

```python
# 新增模块：client/src/business/cost_controller/roi_checker.py

class ROIChecker:
    """投资回报率检查器"""
    
    def check_roi(self, action: Action) -> bool:
        """
        检查投资回报率
        
        例如：
        - 本次数据分析预计消耗 5 美元，但能帮你规避 100 美元的风险 → 建议执行
        - 本次模型训练预计消耗 50 美元，但只提升 1% 准确率 → 不建议执行
        """
        estimated_cost = self.estimate_cost(action)
        expected_benefit = self.estimate_benefit(action)
        
        # ROI > 10x，建议执行
        if expected_benefit > estimated_cost * 10:
            return True
        
        # ROI < 2x，不建议执行
        if expected_benefit < estimated_cost * 2:
            return False
        
        # 介于之间，需要用户确认
        return "NEED_USER_CONFIRMATION"
    
    def estimate_benefit(self, action: Action) -> float:
        """预估收益（美元）"""
        # 根据动作类型，预估收益
        # 例如：规避风险的收益、提升效率的收益、节省时间的收益
        pass
```

**Prompt 模板**:
```
不要为了省 Token 而牺牲关键逻辑。
有时多花 0.1 美元把问题想清楚，比省下钱却跑错方向更"便宜"。

在计算成本时，同时计算预期收益：
- 本次操作能帮你规避多少风险？
- 本次操作能提升多少效率？
- 如果收益 > 成本 * 10，值得投资。
```

---

#### 坑2：防止"成本焦虑"

**问题**: Agent 过度关注成本，导致决策瘫痪（不敢调用任何工具）。

**表现**:
- Agent 输出："这个工具要花 0.1 美元，我不敢用..."
- 结果：任务无法完成。

**解决**: 设置"合理成本范围"

```python
# 新增模块：client/src/business/cost_controller/reasonable_cost_range.py

class ReasonableCostRange:
    """合理成本范围检查器"""
    
    def __init__(self):
        self.ranges = {
            "simple_qa": (0.0, 0.1),        # $0-0.1
            "data_analysis": (0.1, 5.0),     # $0.1-5
            "model_training": (5.0, 50.0),   # $5-50
            "deep_research": (1.0, 20.0),    # $1-20
        }
    
    def is_reasonable(self, task_type: str, cost: float) -> bool:
        """检查成本是否在合理范围内"""
        min_cost, max_cost = self.ranges.get(task_type, (0, 100))
        return min_cost <= cost <= max_cost
    
    def get_suggestion(self, task_type: str, cost: float) -> str:
        """获取成本优化建议"""
        min_cost, max_cost = self.ranges.get(task_type, (0, 100))
        
        if cost > max_cost:
            return f"成本 {cost} 超出合理范围 [{min_cost}, {max_cost}]，建议简化方案"
        
        if cost < min_cost:
            return f"成本 {cost} 低于合理范围 [{min_cost}, {max_cost}]，可能牺牲了质量"
        
        return "成本在合理范围内"
```

**Prompt 模板**:
```
成本意识不等于"不花钱"。
在合理范围内，大胆使用工具来提升结果质量。

判断标准：
- 这个花费能显著提升结果质量吗？
- 这个花费在同类任务的合理成本范围内吗？

如果都是"是"，就大胆执行。
```

---

#### 坑3：成本日志的"记忆过载"

**问题**: 记录太多成本日志，导致记忆库臃肿。

**表现**:
- 记忆库中 90% 都是成本日志
- Agent 检索时，被无关的成本日志干扰。

**解决**: 只记录"关键成本事件"

```python
# 修改 CostController.feedback_to_memory()

class CostController:
    async def feedback_to_memory(self, action: Action, actual_cost: dict):
        """将消耗记录写入记忆库（只记录关键事件）"""
        
        # 1. 成本超预算的事件
        if actual_cost["money"] > self.budget["money"] * 0.5:
            self.write_to_memory(action, actual_cost, priority="HIGH")
        
        # 2. 成本低估的事件（预估 < 实际，说明预估不准）
        estimated = self.estimate_cost(action)
        if actual_cost["money"] > estimated["money"] * 2:
            self.write_to_memory(action, actual_cost, priority="MEDIUM")
        
        # 3. 用户确认的事件（高成本操作）
        if action.need_user_confirmation:
            self.write_to_memory(action, actual_cost, priority="LOW")
        
        # 其他事件：只记录汇总统计，不记录细节
        # （避免记忆库被成本日志占据）
        self.update_cost_statistics(action, actual_cost)
    
    def write_to_memory(self, action: Action, actual_cost: dict, priority: str):
        """写入记忆库"""
        from client.src.business.intelligent_memory.memory_manager import MemoryManager
        memory_manager = MemoryManager()
        
        memory_manager.write({
            "type": "cost_log",
            "priority": priority,
            "action": action.type,
            "description": action.description,
            "actual_cost": actual_cost,
            "timestamp": datetime.now()
        })
    
    def update_cost_statistics(self, action: Action, actual_cost: dict):
        """更新成本统计（不记录细节）"""
        # 只更新汇总数据：总消耗、平均消耗、最大消耗
        pass
```

---

### 20.8 与本项目现有模块的融合

| 新模块 | 现有模块 | 融合方式 |
|--------|---------|---------|
| `cost_controller/` | `global_model_router.py` | 集成 CostTracker，在模型调用前后跟踪成本 |
| `cost_controller/` | `hermes_agent/` | 集成 CostController，拦截 Action 并检查成本 |
| `cost_controller/` | `optimization/`（PRISM） | 成本优化作为新的优化维度（与 Token 优化并列） |
| `hardware_monitor.py` | `intelligent_memory/` | 硬件状态作为上下文，存储到记忆库 |
| `roi_checker.py` | `self_evolution/` | ROI 作为进化方向（选择高 ROI 的方案） |

---

### 20.9 实施优先级与阶段规划

#### 阶段一（基础建设）— 1-2周

| 任务 | 模块 | 工作量 | 优先级 |
|------|------|--------|--------|
| 建立成本字典（cost_dict） | `cost_controller/cost_dict.py` | 轻 | P0 |
| 实现 CostTracker（实时记账） | `cost_controller/cost_tracker.py` | 轻 | P0 |
| 集成到 GlobalModelRouter | `global_model_router.py` | 中 | P0 |

**交付成果**:
- 成本字典（覆盖主要模型和工具）
- CostTracker 实现（实时记账 + 预算检查）
- 修改后的 GlobalModelRouter（集成成本跟踪）

---

#### 阶段二（时间感知）— 2-3周

| 任务 | 模块 | 工作量 | 优先级 |
|------|------|--------|--------|
| 实现 TimeAwareAgent | `cost_controller/time_aware_agent.py` | 轻 | P0 |
| 修改 HermesAgent Prompt | `hermes_agent/prompt_templates.py` | 轻 | P0 |
| 实现 ToolSelector（策略降级） | `cost_controller/tool_selector.py` | 中 | P1 |

**交付成果**:
- TimeAwareAgent 实现（注入时间上下文）
- 修改后的 HermesAgent（根据时间压力调整策略）
- ToolSelector 实现（时间紧迫时自动禁用耗时工具）

---

#### 阶段三（资源监控）— 2-3周

| 任务 | 模块 | 工作量 | 优先级 |
|------|------|--------|--------|
| 实现 HardwareMonitor | `cost_controller/hardware_monitor.py` | 中 | P0 |
| 实现 ComplexityEstimator | `cost_controller/complexity_estimator.py` | 中 | P0 |
| 实现 ResourceManager | `cost_controller/resource_manager.py` | 中 | P0 |

**交付成果**:
- HardwareMonitor 实现（监控 RAM/VRAM）
- ComplexityEstimator 实现（预估任务复杂度）
- ResourceManager 实现（资源预检查 + 用户确认）

---

#### 阶段四（完整集成）— 3-4周

| 任务 | 模块 | 工作量 | 优先级 |
|------|------|--------|--------|
| 实现 CostController 中间件 | `cost_controller/cost_controller.py` | 重 | P0 |
| 集成到 HermesAgent | `hermes_agent/hermes_agent.py` | 中 | P0 |
| 实现 ROIChecker | `cost_controller/roi_checker.py` | 中 | P1 |
| Prompt 优化（成本意识） | `hermes_agent/prompt_templates.py` | 轻 | P0 |

**交付成果**:
- CostController 中间件（完整的三层防御体系）
- 修改后的 HermesAgent（集成成本认知）
- ROIChecker 实现（避免"假节约"）
- 成本意识 Prompt 模板（让 Agent 内生成本意识）

---

### 20.10 总结与预期成果

**实施完成后，LivingTree Agent 将具备**:

1. **成本认知能力** ✅
   - 理解金钱成本（Token/API）
   - 理解时间成本（Deadline 压力）
   - 理解空间/算力成本（硬件资源）

2. **主动控制能力** ✅
   - 在推理过程中主动考虑成本
   - 预算不足时自动降级
   - 时间紧迫时选择"满意解"

3. **经验积累能力** ✅
   - 成本日志反馈到记忆库
   - 下次决策时参考历史成本
   - 形成"成本直觉"（从约束到直觉）

**性能预估**:

| 指标 | 实施前 | 实施后 | 提升 |
|------|--------|--------|------|
| 成本超支率 | 60%（经常超出预算） | 10%（主动控制） | -50% |
| 时间超时率 | 40%（经常超时） | 15%（时间感知） | -25% |
| 资源耗尽率 | 30%（经常卡死） | 5%（资源监控） | -25% |
| 决策质量 | 70%（不考虑成本） | 85%（ROI 思维） | +15% |

---

**让 Agent 从"吞金兽"进化为"经济型思考者"！** 💰🧠✨

---

**最后更新**: 2026-04-28  
**更新内容**: 新增"二十、成本认知系统——从约束到直觉"章节
