import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"

@dataclass
class ServiceInfo:
    name: str
    status: ServiceStatus
    description: str
    startup_time: Optional[float] = None
    error_message: Optional[str] = None

class UnifiedServiceManager:
    """统一服务管理器"""
    
    def __init__(self):
        self.services: Dict[str, ServiceInfo] = {}
        self._dependencies: Dict[str, list] = {}
        
        self._initialize_services()
    
    def _initialize_services(self):
        """初始化服务注册"""
        self._register_service(
            "tool_manager",
            "工具调用管理器",
            ["observability"]
        )
        self._register_service(
            "dialogue_manager",
            "对话管理器",
            []
        )
        self._register_service(
            "plugin_manager",
            "插件管理器",
            ["observability"]
        )
        self._register_service(
            "observability",
            "可观测性服务",
            []
        )
        self._register_service(
            "memory_system",
            "记忆系统",
            ["observability"]
        )
        self._register_service(
            "learning_system",
            "持续学习系统",
            ["memory_system", "observability"]
        )
        self._register_service(
            "reasoning_system",
            "认知推理系统",
            ["memory_system", "observability"]
        )
        self._register_service(
            "self_awareness",
            "自我意识系统",
            ["learning_system", "reasoning_system"]
        )
    
    def _register_service(self, name: str, description: str, dependencies: list = None):
        """注册服务"""
        self.services[name] = ServiceInfo(
            name=name,
            status=ServiceStatus.STOPPED,
            description=description
        )
        self._dependencies[name] = dependencies or []
    
    async def start_all_services(self):
        """启动所有服务（按依赖顺序）"""
        startup_order = self._resolve_dependencies()
        
        for service_name in startup_order:
            await self.start_service(service_name)
    
    def _resolve_dependencies(self) -> list:
        """解析服务依赖顺序"""
        resolved = []
        visited = set()
        
        def dfs(node):
            if node in visited:
                return
            visited.add(node)
            
            for dep in self._dependencies.get(node, []):
                dfs(dep)
            
            if node not in resolved:
                resolved.append(node)
        
        for service in self.services:
            dfs(service)
        
        return resolved
    
    async def start_service(self, service_name: str):
        """启动单个服务"""
        if service_name not in self.services:
            return False
        
        service = self.services[service_name]
        if service.status == ServiceStatus.RUNNING:
            return True
        
        service.status = ServiceStatus.STARTING
        
        try:
            await self._start_service_impl(service_name)
            service.status = ServiceStatus.RUNNING
            service.startup_time = asyncio.get_event_loop().time()
            
            if "observability" in self.services:
                obs_service = self.services["observability"]
                if obs_service.status == ServiceStatus.RUNNING:
                    self._record_service_start(service_name)
            
            return True
        except Exception as e:
            service.status = ServiceStatus.ERROR
            service.error_message = str(e)
            return False
    
    async def _start_service_impl(self, service_name: str):
        """实际启动服务的实现"""
        await asyncio.sleep(0.1)
    
    async def stop_service(self, service_name: str):
        """停止单个服务"""
        if service_name not in self.services:
            return False
        
        service = self.services[service_name]
        if service.status != ServiceStatus.RUNNING:
            return True
        
        try:
            await asyncio.sleep(0.1)
            service.status = ServiceStatus.STOPPED
            service.startup_time = None
            return True
        except Exception as e:
            service.error_message = str(e)
            return False
    
    async def stop_all_services(self):
        """停止所有服务"""
        for service_name in reversed(self._resolve_dependencies()):
            await self.stop_service(service_name)
    
    def _record_service_start(self, service_name: str):
        """记录服务启动到可观测性系统"""
        pass
    
    def get_service_info(self, service_name: str) -> Optional[ServiceInfo]:
        """获取服务信息"""
        return self.services.get(service_name)
    
    def get_all_services(self) -> Dict[str, ServiceInfo]:
        """获取所有服务"""
        return self.services
    
    def get_service_status(self) -> Dict[str, str]:
        """获取服务状态摘要"""
        return {
            name: service.status.value
            for name, service in self.services.items()
        }
    
    def is_all_running(self) -> bool:
        """检查所有服务是否运行"""
        return all(s.status == ServiceStatus.RUNNING for s in self.services.values())

class ServiceIntegration:
    """服务集成层 - 将增强功能与AI助手深度融合"""
    
    def __init__(self):
        self.service_manager = UnifiedServiceManager()
        
        self.tool_manager = None
        self.dialogue_manager = None
        self.plugin_manager = None
        self.observability_manager = None
        
        self._integration_hooks = []
    
    async def initialize(self):
        """初始化所有服务"""
        await self.service_manager.start_all_services()
        
        self._lazy_import_services()
        self._setup_integration_hooks()
    
    def _lazy_import_services(self):
        """延迟导入服务模块"""
        try:
            from business.tool_enhancement import ToolManager, SmartToolSelector
            from business.dialogue_optimization import ContextWindowManager, DialogueCompressor
            from business.plugin_extension import PluginManager
            from business.observability_enhancement import ObservabilityManager
        except ImportError:
            return

        self.tool_manager = ToolManager()
        self.smart_selector = SmartToolSelector(self.tool_manager)

        self.dialogue_manager = ContextWindowManager()
        self.dialogue_compressor = DialogueCompressor()

        self.plugin_manager = PluginManager()

        self.observability_manager = ObservabilityManager()
        self.observability_manager.start_monitoring()
    
    def _setup_integration_hooks(self):
        """设置集成钩子"""
        self._register_hook("message_received", self._on_message_received)
        self._register_hook("tool_call", self._on_tool_call)
        self._register_hook("response_generated", self._on_response_generated)
        self._register_hook("dialogue_created", self._on_dialogue_created)
    
    def _register_hook(self, hook_name: str, callback):
        """注册钩子"""
        self._integration_hooks.append({"name": hook_name, "callback": callback})
    
    async def _on_message_received(self, message: str, dialogue_id: str = None):
        """收到消息时的处理"""
        if self.observability_manager:
            self.observability_manager.increment_counter("dialogues.messages")
        
        if not dialogue_id:
            dialogue = self.dialogue_manager.create_dialogue()
            dialogue_id = dialogue.id
        
        self.dialogue_manager.add_message(dialogue_id, "user", message)
        
        if self.smart_selector:
            self.smart_selector.update_context({"query": message})
        
        return dialogue_id
    
    async def _on_tool_call(self, tool_name: str, params: Dict[str, Any], dialogue_id: str):
        """工具调用时的处理"""
        if self.observability_manager:
            self.observability_manager.increment_counter("tools.calls.total")
        
        start_time = asyncio.get_event_loop().time()
        result = await self.tool_manager.call_tool(tool_name, **params)
        execution_time = asyncio.get_event_loop().time() - start_time
        
        if self.observability_manager:
            if result.success:
                self.observability_manager.increment_counter("tools.calls.success")
            self.observability_manager.update_metric("tools.latency.avg", execution_time)
        
        if dialogue_id and result.success:
            self.dialogue_manager.add_message(
                dialogue_id,
                "assistant",
                f"工具调用结果 ({tool_name}):\n{result.result}",
                {"tool_name": tool_name, "execution_time": execution_time}
            )
        
        return result
    
    async def _on_response_generated(self, response: str, dialogue_id: str):
        """响应生成后的处理"""
        if self.observability_manager:
            self.observability_manager.increment_counter("ai.requests.success")
        
        self.dialogue_manager.add_message(dialogue_id, "assistant", response)
        
        self.dialogue_manager.compress_dialogue(dialogue_id)
    
    def _on_dialogue_created(self, dialogue_id: str):
        """对话创建时的处理"""
        if self.observability_manager:
            self.observability_manager.update_metric("dialogues.active", 
                len(self.dialogue_manager.get_dialogue_list()))
    
    async def process_message(self, message: str, dialogue_id: str = None) -> Dict[str, Any]:
        """处理用户消息 - 完整的集成流程"""
        dialogue_id = await self._on_message_received(message, dialogue_id)
        
        tools = self.smart_selector.select_tools(message)
        
        if tools:
            tool_results = []
            for tool in tools[:2]:
                result = await self._on_tool_call(tool.name, {}, dialogue_id)
                tool_results.append(result)
            
            response = self._generate_response(message, tool_results)
        else:
            response = self._generate_response(message, [])
        
        await self._on_response_generated(response, dialogue_id)
        
        return {
            "dialogue_id": dialogue_id,
            "response": response,
            "tools_used": [t.name for t in tools]
        }
    
    def _generate_response(self, message: str, tool_results: list) -> str:
        """生成响应"""
        if tool_results:
            results_text = "\n\n".join(
                f"【{r.tool_name}】\n{r.result}" 
                for r in tool_results if r.success
            )
            return f"根据工具查询结果，我来帮您分析：\n\n{results_text}"
        else:
            return f"收到您的消息：{message}\n\n这是我的回复内容。"
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取综合仪表盘数据"""
        return {
            "services": self.service_manager.get_service_status(),
            "metrics": self.observability_manager.get_summary_stats() if self.observability_manager else {},
            "dialogues": self.dialogue_manager.get_dialogue_list() if self.dialogue_manager else [],
            "tools": self.tool_manager.get_tool_stats() if self.tool_manager else {},
            "plugins": self.plugin_manager.get_plugin_stats() if self.plugin_manager else {}
        }
    
    async def shutdown(self):
        """关闭所有服务"""
        if self.observability_manager:
            self.observability_manager.stop_monitoring()
        
        await self.service_manager.stop_all_services()