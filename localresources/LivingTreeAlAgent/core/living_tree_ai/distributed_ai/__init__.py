"""
私有分布式 AI 计算网络 (Private Distributed AI Computing Network)

三层架构：
- 感知层 (Client): 采集用户意图（语音/文本/行为）
- 推理层 (Nodes): 边缘/海外节点，执行 AI 模型计算
- 控制层 (Brain): 中心调度节点，任务分解、路由、上下文管理

核心设计理念：
- 数据不动，计算动
- 感知、推理、执行三层分离
- 中心调度，全局编排
"""

__version__ = "1.0.0"
__all__ = [
    # 版本
    "__version__",
]

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import time
import asyncio
import hashlib
import json


# ============================================================================
# 核心角色与状态定义
# ============================================================================

class NodeRole(Enum):
    """节点角色"""
    CLIENT = "client"           # 感知层客户端
    EDGE = "edge"              # 边缘加速节点
    OVERSEAS = "overseas"      # 海外计算集群
    BRAIN = "brain"            # 中心调度节点


class NodeStatus(Enum):
    """节点状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    MAINTENANCE = "maintenance"


class TaskType(Enum):
    """任务类型"""
    CODE_COMPLETION = "code_completion"     # 代码补全
    SEMANTIC_SEARCH = "semantic_search"     # 语义搜索
    ACADEMIC_SEARCH = "academic_search"     # 学术搜索
    CREATIVE_WRITING = "creative_writing"   # 创意写作
    CODE_GENERATION = "code_generation"     # 代码生成
    IMAGE_PROCESS = "image_process"         # 图片处理
    DATA_ANALYSIS = "data_analysis"         # 数据分析
    GAME_AI = "game_ai"                      # 游戏AI
    BROWSER_AUTO = "browser_auto"            # 浏览器自动化
    GENERAL = "general"                     # 通用任务


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    ROUTING = "routing"
    EXECUTING = "executing"
    COMPOSING = "composing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RoutingStrategy(Enum):
    """路由策略"""
    LOWEST_LATENCY = "lowest_latency"       # 最低延迟
    LOWEST_COST = "lowest_cost"             # 最低成本
    BEST_QUALITY = "best_quality"          # 最高质量
    BALANCED = "balanced"                   # 均衡策略


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    role: NodeRole
    status: NodeStatus
    capabilities: List[str] = field(default_factory=list)
    load: float = 0.0                        # 负载 0.0-1.0
    latency_ms: float = 0.0                 # 延迟毫秒
    cost_factor: float = 1.0                # 成本系数
    bandwidth_mbps: float = 100.0            # 带宽 Mbps
    memory_gb: float = 8.0                  # 内存 GB
    gpu_count: int = 0                      # GPU数量
    region: str = "unknown"                  # 地区
    last_heartbeat: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRequest:
    """任务请求"""
    task_id: str
    task_type: TaskType
    user_id: str
    intent: str                              # 用户意图描述
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文
    routing: RoutingStrategy = RoutingStrategy.BALANCED
    priority: int = 5                        # 优先级 1-10
    timeout_ms: int = 30000                  # 超时毫秒
    budget: float = None                     # 预算限制
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: str = None
    node_id: str = None                      # 执行节点
    execution_time_ms: float = 0.0
    cost: float = 0.0
    completed_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextEntry:
    """上下文条目"""
    key: str
    value: Any
    source: str                              # 来源：browser/ide/voice
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: int = 3600                  # 过期时间
    importance: float = 1.0                  # 重要性 0.0-1.0


# ============================================================================
# 感知层 (Client) - 采集用户意图
# ============================================================================

class IntentCollector:
    """
    感知层：采集用户意图（语音/文本/行为）
    物理对应：手机/PC App
    """

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.intent_buffer = []
        self.context_history: List[ContextEntry] = []
        self.active_apps = {}                # 当前活跃应用
        self.user_state = {}                  # 用户状态

    async def capture_intent(self, raw_input: Any, input_type: str) -> TaskRequest:
        """
        捕获用户意图

        Args:
            raw_input: 原始输入（语音/文本/行为数据）
            input_type: 输入类型（voice/text/behavior）
        """
        # 1. 解析输入
        parsed = await self.parse_input(raw_input, input_type)

        # 2. 补充上下文
        context = await self.gather_context(parsed)

        # 3. 创建任务请求
        task = TaskRequest(
            task_id=self.generate_task_id(),
            task_type=self.classify_intent(parsed),
            user_id=self.client_id,
            intent=parsed.get("intent", ""),
            context=context,
            priority=parsed.get("priority", 5)
        )

        # 4. 记录历史
        self.context_history.append(ContextEntry(
            key=f"intent:{task.task_id}",
            value=parsed,
            source=input_type
        ))

        return task

    async def parse_input(self, raw_input: Any, input_type: str) -> Dict:
        """解析不同类型的输入"""
        if input_type == "voice":
            return await self.parse_voice(raw_input)
        elif input_type == "text":
            return await self.parse_text(raw_input)
        elif input_type == "behavior":
            return await self.parse_behavior(raw_input)
        return {"intent": str(raw_input), "raw": raw_input}

    async def parse_voice(self, audio_data: bytes) -> Dict:
        """解析语音输入"""
        # 模拟语音转文字 + 意图识别
        return {
            "intent": "语音指令",
            "text": "帮我搜索 Python 异步编程的最佳实践",
            "entities": {"topic": "Python异步", "type": "搜索"},
            "priority": 7
        }

    async def parse_text(self, text: str) -> Dict:
        """解析文本输入"""
        # 模拟意图识别
        intent_keywords = {
            "搜索": TaskType.SEMANTIC_SEARCH,
            "代码": TaskType.CODE_COMPLETION,
            "写": TaskType.CREATIVE_WRITING,
            "分析": TaskType.DATA_ANALYSIS,
        }

        task_type = TaskType.GENERAL
        for keyword, task_t in intent_keywords.items():
            if keyword in text:
                task_type = task_t
                break

        return {
            "intent": text,
            "text": text,
            "entities": {"keywords": text.split()},
            "task_type": task_type,
            "priority": 5
        }

    async def parse_behavior(self, behavior_data: Dict) -> Dict:
        """解析行为输入"""
        behavior_type = behavior_data.get("type", "unknown")
        return {
            "intent": f"行为: {behavior_type}",
            "behavior": behavior_data,
            "priority": behavior_data.get("priority", 3)
        }

    async def gather_context(self, parsed: Dict) -> Dict:
        """收集当前上下文"""
        context = {
            "client_id": self.client_id,
            "active_apps": list(self.active_apps.keys()),
            "user_state": self.user_state.copy(),
            "recent_intents": [c.value for c in self.context_history[-5:]],
            "location": self.user_state.get("location", "unknown"),
            "time_of_day": self.get_time_of_day()
        }

        # 补充应用特定上下文
        for app_id, app_data in self.active_apps.items():
            if app_id == "ide":
                context["ide_project"] = app_data.get("project", {})
            elif app_id == "browser":
                context["browser_tab"] = app_data.get("current_tab", {})

        return context

    def get_time_of_day(self) -> str:
        """获取时间段"""
        hour = time.localtime().tm_hour
        if 6 <= hour < 9:
            return "morning"
        elif 9 <= hour < 12:
            return "forenoon"
        elif 12 <= hour < 14:
            return "noon"
        elif 14 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        return "night"

    def classify_intent(self, parsed: Dict) -> TaskType:
        """分类意图为任务类型"""
        return parsed.get("task_type", TaskType.GENERAL)

    def generate_task_id(self) -> str:
        """生成任务ID"""
        timestamp = str(time.time_ns())
        return hashlib.sha256(f"{self.client_id}{timestamp}".encode()).hexdigest()[:16]


# ============================================================================
# 推理层 (Nodes) - 执行 AI 计算
# ============================================================================

class InferenceNode:
    """
    推理层：执行具体的 AI 模型计算
    物理对应：边缘/海外节点
    """

    def __init__(self, node_info: NodeInfo):
        self.info = node_info
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.current_tasks: Dict[str, TaskRequest] = {}
        self.model_cache: Dict[str, Any] = {}

    async def execute_task(self, task: TaskRequest) -> TaskResult:
        """执行任务"""
        start_time = time.time()

        try:
            # 1. 更新状态
            self.info.status = NodeStatus.BUSY
            self.current_tasks[task.task_id] = task

            # 2. 选择模型
            model = self.select_model(task.task_type)

            # 3. 执行推理
            result = await self.run_inference(task, model)

            # 4. 构建结果
            execution_time = (time.time() - start_time) * 1000
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                node_id=self.info.node_id,
                execution_time_ms=execution_time,
                cost=self.calculate_cost(execution_time)
            )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                node_id=self.info.node_id,
                execution_time_ms=(time.time() - start_time) * 1000
            )
        finally:
            self.info.status = NodeStatus.ONLINE
            self.current_tasks.pop(task.task_id, None)

    def select_model(self, task_type: TaskType) -> str:
        """根据任务类型选择模型"""
        model_mapping = {
            TaskType.CODE_COMPLETION: "codellama:7b",
            TaskType.SEMANTIC_SEARCH: "embedding-model",
            TaskType.ACADEMIC_SEARCH: "gpt4all:latest",
            TaskType.CREATIVE_WRITING: "llama3:8b",
            TaskType.CODE_GENERATION: "codellama:13b",
            TaskType.GAME_AI: "gpt4all:13b",
        }
        return model_mapping.get(task_type, "gpt4all:latest")

    async def run_inference(self, task: TaskRequest, model: str) -> Any:
        """运行推理"""
        # 模拟推理过程
        await asyncio.sleep(0.1)  # 模拟计算时间

        # 根据任务类型返回不同结果
        if task.task_type == TaskType.CODE_COMPLETION:
            return {
                "type": "completion",
                "suggestions": ["def async_await():", "async def fetch():", "await asyncio."],
                "confidence": 0.95
            }
        elif task.task_type == TaskType.SEMANTIC_SEARCH:
            return {
                "type": "search_results",
                "results": [
                    {"title": "Python异步编程指南", "url": "https://...", "snippet": "..."},
                    {"title": "asyncio最佳实践", "url": "https://...", "snippet": "..."}
                ]
            }
        elif task.task_type == TaskType.CREATIVE_WRITING:
            return {
                "type": "text",
                "content": "生成的创意内容...",
                "style": "technical"
            }
        return {"type": "generic", "content": "处理结果"}

    def calculate_cost(self, execution_time_ms: float) -> float:
        """计算成本"""
        base_cost_per_second = 0.001  # $0.001/秒
        gpu_cost = 0.005 if self.info.gpu_count > 0 else 0
        return (execution_time_ms / 1000) * (base_cost_per_second + gpu_cost)


class NodeRegistry:
    """节点注册表"""

    def __init__(self):
        self.nodes: Dict[str, InferenceNode] = {}
        self.nodes_by_role: Dict[NodeRole, List[str]] = {role: [] for role in NodeRole}

    def register_node(self, node: InferenceNode):
        """注册节点"""
        self.nodes[node.info.node_id] = node
        self.nodes_by_role[node.info.role].append(node.info.node_id)

    def unregister_node(self, node_id: str):
        """注销节点"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            self.nodes_by_role[node.info.role].remove(node_id)
            del self.nodes[node_id]

    def get_nodes_by_capability(self, capability: str) -> List[InferenceNode]:
        """根据能力获取节点"""
        return [n for n in self.nodes.values()
                if capability in n.info.capabilities and n.info.status == NodeStatus.ONLINE]

    def get_best_node(self, task_type: TaskType, strategy: RoutingStrategy) -> Optional[InferenceNode]:
        """根据策略获取最优节点"""
        # 找出支持该任务类型的节点
        capability_map = {
            TaskType.CODE_COMPLETION: "code",
            TaskType.SEMANTIC_SEARCH: "search",
            TaskType.ACADEMIC_SEARCH: "search",
            TaskType.CREATIVE_WRITING: "text",
            TaskType.CODE_GENERATION: "code",
            TaskType.GAME_AI: "game",
        }

        capability = capability_map.get(task_type, "general")
        candidates = self.get_nodes_by_capability(capability)

        if not candidates:
            return None

        # 根据策略排序
        if strategy == RoutingStrategy.LOWEST_LATENCY:
            candidates.sort(key=lambda n: n.info.latency_ms)
        elif strategy == RoutingStrategy.LOWEST_COST:
            candidates.sort(key=lambda n: n.info.cost_factor)
        elif strategy == RoutingStrategy.BEST_QUALITY:
            candidates.sort(key=lambda n: -n.info.load)  # 负载低的更好
        else:  # BALANCED
            # 综合评分
            for n in candidates:
                n._score = (
                    1.0 / (n.info.latency_ms + 1) * 0.4 +
                    1.0 / (n.info.cost_factor + 0.1) * 0.3 +
                    (1.0 - n.info.load) * 0.3
                )
            candidates.sort(key=lambda n: -n._score)

        return candidates[0]


# ============================================================================
# 控制层 (Brain) - 中心调度节点
# ============================================================================

class ContextEngine:
    """
    上下文引擎：维护用户跨设备、跨应用的状态
    """

    def __init__(self, brain_id: str):
        self.brain_id = brain_id
        self.user_contexts: Dict[str, Dict[str, ContextEntry]] = {}

    def get_context(self, user_id: str, key: str) -> Optional[Any]:
        """获取上下文"""
        if user_id not in self.user_contexts:
            return None
        entry = self.user_contexts[user_id].get(key)
        if entry and time.time() - entry.timestamp < entry.ttl_seconds:
            return entry.value
        return None

    def set_context(self, user_id: str, key: str, value: Any,
                   source: str = "unknown", ttl_seconds: int = 3600,
                   importance: float = 1.0):
        """设置上下文"""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = {}
        self.user_contexts[user_id][key] = ContextEntry(
            key=key,
            value=value,
            source=source,
            ttl_seconds=ttl_seconds,
            importance=importance
        )

    def get_user_context_graph(self, user_id: str) -> Dict[str, Any]:
        """获取用户上下文图谱"""
        if user_id not in self.user_contexts:
            return {}

        graph = {
            "user_id": user_id,
            "entries": [],
            "recent_apps": [],
            "active_projects": []
        }

        for key, entry in self.user_contexts[user_id].items():
            if time.time() - entry.timestamp < entry.ttl_seconds:
                graph["entries"].append({
                    "key": key,
                    "value": entry.value,
                    "source": entry.source,
                    "importance": entry.importance
                })
                if entry.source == "ide" and "project" in key:
                    graph["active_projects"].append(entry.value)

        return graph

    def enrich_context(self, task: TaskRequest) -> Dict[str, Any]:
        """为任务补充上下文"""
        context = task.context.copy()

        # 添加 IDE 项目信息
        if "ide_project" in context:
            project = self.get_context(task.user_id, "ide_project")
            if project:
                context["project_structure"] = project.get("structure", {})
                context["current_file"] = project.get("current_file", "")

        # 添加浏览器标签信息
        browser_tab = self.get_context(task.user_id, "browser_tab")
        if browser_tab:
            context["current_page"] = browser_tab.get("url", "")
            context["page_content"] = browser_tab.get("content", "")

        # 添加用户偏好
        preferences = self.get_context(task.user_id, "preferences")
        if preferences:
            context["user_preferences"] = preferences

        return context


class PolicyRouter:
    """
    策略路由：根据规则将任务路由到最优节点
    """

    def __init__(self, node_registry: NodeRegistry):
        self.registry = node_registry
        self.rules: List[Dict] = []

    def add_rule(self, condition: Dict, action: Dict):
        """添加路由规则"""
        self.rules.append({"condition": condition, "action": action})

    async def route_task(self, task: TaskRequest) -> InferenceNode:
        """路由任务到最优节点"""

        # 1. 检查规则引擎
        for rule in self.rules:
            if self.match_condition(task, rule["condition"]):
                target_role = rule["action"].get("role")
                if target_role:
                    return self.route_to_role(task, NodeRole(target_role))

        # 2. 根据任务类型路由
        if task.task_type in [TaskType.ACADEMIC_SEARCH, TaskType.CODE_GENERATION]:
            # 需要海外集群
            return self.route_to_role(task, NodeRole.OVERSEAS)
        elif task.task_type in [TaskType.CODE_COMPLETION, TaskType.SEMANTIC_SEARCH]:
            # 优先边缘节点
            edge = self.route_to_role(task, NodeRole.EDGE)
            if edge:
                return edge
            return self.route_to_role(task, NodeRole.OVERSEAS)
        else:
            # 默认路由
            return self.registry.get_best_node(task.task_type, task.routing)

    def route_to_role(self, task: TaskRequest, role: NodeRole) -> Optional[InferenceNode]:
        """路由到特定角色的节点"""
        nodes = [n for n in self.registry.nodes.values()
                if n.info.role == role and n.info.status == NodeStatus.ONLINE]
        if not nodes:
            return None
        return self.registry.get_best_node(task.task_type, task.routing)

    def match_condition(self, task: TaskRequest, condition: Dict) -> bool:
        """匹配条件"""
        if "task_type" in condition:
            if task.task_type.value != condition["task_type"]:
                return False
        if "intent_contains" in condition:
            if condition["intent_contains"] not in task.intent:
                return False
        if "priority_ge" in condition:
            if task.priority < condition["priority_ge"]:
                return False
        return True


class ComplianceGateway:
    """
    合规网关：对跨境数据进行审计与脱敏
    """

    def __init__(self):
        self.audit_log: List[Dict] = []
        self.blocked_keywords: set = set()
        self.sensitivity_rules: Dict[str, float] = {}

    async def audit_content(self, content: Any, source: str, user_id: str) -> Dict:
        """
        审计内容

        Returns:
            {"passed": bool, "filtered": Any, "violations": List[str]}
        """
        violations = []
        filtered = content

        # 1. 关键词过滤
        if isinstance(content, str):
            for keyword in self.blocked_keywords:
                if keyword in content:
                    violations.append(f"Blocked keyword: {keyword}")
                    filtered = filtered.replace(keyword, "*" * len(keyword))

        # 2. 版权检测
        copyright_result = await self.check_copyright(filtered)
        if not copyright_result["safe"]:
            violations.append(f"Copyright: {copyright_result['source']}")

        # 3. 记录审计日志
        self.audit_log.append({
            "user_id": user_id,
            "source": source,
            "timestamp": time.time(),
            "violations": violations,
            "passed": len(violations) == 0
        })

        return {
            "passed": len(violations) == 0,
            "filtered": filtered,
            "violations": violations
        }

    async def check_copyright(self, content: str) -> Dict:
        """检查版权"""
        # 模拟版权检测
        return {"safe": True, "source": None}

    def add_blocked_keyword(self, keyword: str):
        """添加屏蔽关键词"""
        self.blocked_keywords.add(keyword)


class TaskComposer:
    """
    任务合成器：将多个子任务结果合成为最终结果
    """

    def __init__(self):
        self.partial_results: Dict[str, Any] = {}

    async def compose_results(self, task_id: str, results: List[TaskResult]) -> Any:
        """合成多个结果"""

        # 检查是否所有子任务都完成
        failed = [r for r in results if r.status != TaskStatus.COMPLETED]
        if failed:
            return {
                "error": "部分任务失败",
                "failed_count": len(failed),
                "partial": [r.result for r in results if r.result]
            }

        # 根据任务类型选择合成策略
        if not results:
            return None

        first_result = results[0].result

        if isinstance(first_result, dict):
            # 合并字典结果
            composed = {}
            for r in results:
                if isinstance(r.result, dict):
                    composed.update(r.result)
            return composed
        elif isinstance(first_result, list):
            # 合并列表结果
            combined = []
            for r in results:
                if isinstance(r.result, list):
                    combined.extend(r.result)
            # 去重
            return self.deduplicate(combined)
        else:
            # 直接返回第一个结果
            return first_result

    def deduplicate(self, items: List[Any]) -> List[Any]:
        """去重"""
        seen = set()
        result = []
        for item in items:
            key = json.dumps(item, sort_keys=True)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result


class CentralBrain:
    """
    中心调度节点：全局大脑
    """

    def __init__(self, brain_id: str):
        self.brain_id = brain_id
        self.node_registry = NodeRegistry()
        self.context_engine = ContextEngine(brain_id)
        self.policy_router = PolicyRouter(self.node_registry)
        self.compliance_gateway = ComplianceGateway()
        self.task_composer = TaskComposer()
        self.active_tasks: Dict[str, TaskRequest] = {}
        self.task_results: Dict[str, TaskResult] = {}

    async def submit_task(self, task: TaskRequest) -> str:
        """提交任务"""
        # 1. 补充上下文
        task.context = self.context_engine.enrich_context(task)

        # 2. 路由任务
        node = await self.policy_router.route_task(task)
        if not node:
            return None

        # 3. 更新任务状态
        task.metadata["assigned_node"] = node.info.node_id
        self.active_tasks[task.task_id] = task

        # 4. 执行任务
        result = await node.execute_task(task)

        # 5. 合规检查（如果是海外集群返回）
        if node.info.role == NodeRole.OVERSEAS and result.result:
            audit = await self.compliance_gateway.audit_content(
                result.result,
                source="overseas",
                user_id=task.user_id
            )
            if not audit["passed"]:
                result.result = audit["filtered"]
                result.metadata["violations"] = audit["violations"]

        # 6. 记录结果
        self.task_results[task.task_id] = result
        self.active_tasks.pop(task.task_id, None)

        return result

    async def submit_task_async(self, task: TaskRequest) -> asyncio.Task:
        """异步提交任务"""
        return asyncio.create_task(self.submit_task(task))

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        return self.task_results.get(task_id)

    def register_node(self, node_info: NodeInfo):
        """注册节点"""
        node = InferenceNode(node_info)
        self.node_registry.register_node(node)

    def get_network_status(self) -> Dict:
        """获取网络状态"""
        return {
            "total_nodes": len(self.node_registry.nodes),
            "by_role": {
                role.value: len(nodes)
                for role, nodes in self.node_registry.nodes_by_role.items()
            },
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.task_results)
        }


# ============================================================================
# 海外计算集群
# ============================================================================

class OverseasCluster:
    """
    海外计算集群：外脑与风险隔离区
    """

    def __init__(self, cluster_id: str, region: str = "us-west"):
        self.cluster_id = cluster_id
        self.region = region
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.result_callbacks: Dict[str, Callable] = {}
        self.whitelist_ips: set = set()  # 合规白名单

    async def submit_heavy_task(self, task: TaskRequest,
                                 webhook_url: str = None) -> str:
        """
        提交重量级任务到海外集群

        Args:
            task: 任务请求
            webhook_url: 结果回调URL
        """
        # 1. 放入队列
        await self.task_queue.put(task)

        # 2. 设置回调
        if webhook_url:
            self.result_callbacks[task.task_id] = lambda r: self.call_webhook(webhook_url, r)

        # 3. 返回任务ID
        return task.task_id

    async def call_webhook(self, url: str, result: TaskResult):
        """回调 webhook"""
        # 模拟 HTTP POST
        pass

    async def process_queue(self):
        """处理队列"""
        while True:
            task = await self.task_queue.get()
            try:
                # 执行任务
                result = await self.execute_overseas_task(task)

                # 回调
                if task.task_id in self.result_callbacks:
                    self.result_callbacks[task.task_id](result)
                    del self.result_callbacks[task.task_id]

            except Exception as e:
                print(f"Overseas task failed: {e}")
            finally:
                self.task_queue.task_done()

    async def execute_overseas_task(self, task: TaskRequest) -> TaskResult:
        """执行海外任务"""
        # 模拟执行
        await asyncio.sleep(0.5)

        return TaskResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            result={"overseas_result": True, "region": self.region}
        )


# ============================================================================
# 边缘加速节点
# ============================================================================

class EdgeAccelerator:
    """
    边缘加速节点：毫秒级响应代理
    """

    def __init__(self, node_id: str, region: str = "unknown"):
        self.node_id = node_id
        self.region = region
        self.lsp_cache: Dict[str, Any] = {}      # 代码补全缓存
        self.search_cache: Dict[str, Any] = {}    # 搜索结果缓存
        self.resource_cache: Dict[str, Any] = {}  # 资源缓存
        self.predictor: "PredictiveCache" = None

    async def handle_code_completion(self, task: TaskRequest) -> Dict:
        """处理代码补全"""
        # 1. 检查缓存
        cache_key = self.get_cache_key(task)
        if cache_key in self.lsp_cache:
            return self.lsp_cache[cache_key]

        # 2. 预测性缓存
        if self.predictor:
            prediction = await self.predictor.predict_next_completion(task)
            if prediction:
                return prediction

        # 3. 返回占位（实际会路由到边缘节点）
        return {
            "cached": False,
            "completion": "await ",
            "confidence": 0.5
        }

    async def handle_search(self, task: TaskRequest) -> Dict:
        """处理搜索请求"""
        cache_key = self.get_cache_key(task)

        if cache_key in self.search_cache:
            result = self.search_cache[cache_key]
            result["cached"] = True
            return result

        return {
            "cached": False,
            "results": []
        }

    def get_cache_key(self, task: TaskRequest) -> str:
        """生成缓存键"""
        content = f"{task.task_type.value}:{task.intent}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def prefetch_resources(self, user_id: str, context: Dict):
        """预测性预取资源"""
        if not self.predictor:
            return

        # 预测用户可能需要的资源
        predictions = await self.predictor.predict_resources(user_id, context)

        for resource in predictions:
            # 预取到本地
            self.resource_cache[resource["key"]] = resource


class PredictiveCache:
    """
    预测性缓存：基于用户行为预测提前缓存
    """

    def __init__(self):
        self.behavior_patterns: Dict[str, List[str]] = {}  # 用户 -> 行为序列
        self.context_correlation: Dict[str, Dict] = {}     # 上下文 -> 资源映射

    async def predict_next_completion(self, task: TaskRequest) -> Optional[Dict]:
        """预测下一个代码补全"""
        return None  # 简化实现

    async def predict_resources(self, user_id: str, context: Dict) -> List[Dict]:
        """预测用户可能需要的资源"""
        return []  # 简化实现


# ============================================================================
# 工厂函数
# ============================================================================

def create_brain(brain_id: str = "central_brain") -> CentralBrain:
    """创建中心大脑"""
    return CentralBrain(brain_id)


def create_client_collector(client_id: str) -> IntentCollector:
    """创建客户端感知器"""
    return IntentCollector(client_id)


def create_overseas_cluster(cluster_id: str, region: str = "us-west") -> OverseasCluster:
    """创建海外集群"""
    return OverseasCluster(cluster_id, region)


def create_edge_node(node_id: str, region: str = "unknown") -> EdgeAccelerator:
    """创建边缘节点"""
    return EdgeAccelerator(node_id, region)
