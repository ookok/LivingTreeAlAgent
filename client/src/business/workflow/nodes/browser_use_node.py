"""
browser-use 工作流节点

将 browser-use 浏览器自动化功能集成到工作流系统中
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from ..workflow import WorkflowNode, StepStatus


@dataclass
class BrowserUseNode(WorkflowNode):
    """browser-use 浏览器自动化节点"""
    
    # 节点类型
    node_type: str = "browser_use"
    
    # browser-use 配置
    browser_config: Dict[str, Any] = field(default_factory=dict)
    
    # 任务配置
    task_type: str = "execute"  # execute/navigate/extract_content/fill_form/search/screenshot
    task_params: Dict[str, Any] = field(default_factory=dict)
    
    # 结果配置
    result_variable: str = "browser_result"
    
    def __post_init__(self):
        """初始化"""
        if not self.name:
            self.name = "浏览器自动化"
        if not self.description:
            self.description = "使用 browser-use 执行浏览器自动化任务"
        if not self.icon:
            self.icon = "🌐"
        if not self.color:
            self.color = "#3b82f6"
        
        # 设置可用动作
        self.available_actions = ["complete"]
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行浏览器自动化任务
        
        Args:
            context: 工作流上下文
            
        Returns:
            Dict: 执行结果
        """
        try:
            # 导入 browser-use 适配器
            from business.living_tree_ai.browser_gateway.browser_use_adapter import create_browser_use_adapter
            
            # 创建适配器
            adapter = create_browser_use_adapter()
            
            # 初始化
            initialized = await adapter.initialize(
                use_cloud=self.browser_config.get("use_cloud", False)
            )
            
            if not initialized:
                return {
                    "status": StepStatus.FAILED.value,
                    "error": "初始化 browser-use 失败"
                }
            
            # 执行任务
            result = await self._execute_task(adapter, context)
            
            # 关闭浏览器
            await adapter.close()
            
            # 存储结果
            if self.result_variable:
                context[self.result_variable] = result
            
            return {
                "status": StepStatus.COMPLETED.value,
                "result": result
            }
            
        except Exception as e:
            return {
                "status": StepStatus.FAILED.value,
                "error": str(e)
            }
    
    async def _execute_task(self, adapter, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行具体任务
        
        Args:
            adapter: browser-use 适配器
            context: 工作流上下文
            
        Returns:
            Dict: 执行结果
        """
        task_type = self.task_type
        task_params = self._resolve_params(self.task_params, context)
        
        if task_type == "execute":
            # 执行自定义任务
            task = task_params.get("task", "")
            return await adapter.execute_task(task)
        
        elif task_type == "navigate":
            # 导航到 URL
            url = task_params.get("url", "")
            return await adapter.navigate(url)
        
        elif task_type == "extract_content":
            # 提取页面内容
            url = task_params.get("url", "")
            selector = task_params.get("selector", None)
            return await adapter.extract_content(url, selector)
        
        elif task_type == "fill_form":
            # 填写表单
            url = task_params.get("url", "")
            form_data = task_params.get("form_data", {})
            return await adapter.fill_form(url, form_data)
        
        elif task_type == "search":
            # 搜索内容
            query = task_params.get("query", "")
            engine = task_params.get("engine", "google")
            return await adapter.search(query, engine)
        
        elif task_type == "screenshot":
            # 截图页面
            url = task_params.get("url", "")
            path = task_params.get("path", "screenshot.png")
            return await adapter.screenshot(url, path)
        
        else:
            raise ValueError(f"未知的任务类型: {task_type}")
    
    def _resolve_params(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析参数，支持上下文变量
        
        Args:
            params: 原始参数
            context: 工作流上下文
            
        Returns:
            Dict: 解析后的参数
        """
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # 解析上下文变量
                var_name = value[2:-1].strip()
                resolved[key] = context.get(var_name, value)
            else:
                resolved[key] = value
        return resolved
    
    def validate(self) -> Dict[str, Any]:
        """
        验证节点配置
        
        Returns:
            Dict: 验证结果
        """
        errors = []
        
        # 验证任务类型
        valid_task_types = ["execute", "navigate", "extract_content", "fill_form", "search", "screenshot"]
        if self.task_type not in valid_task_types:
            errors.append(f"无效的任务类型: {self.task_type}")
        
        # 验证任务参数
        if self.task_type == "execute":
            if not self.task_params.get("task"):
                errors.append("执行任务需要指定 task 参数")
        elif self.task_type in ["navigate", "extract_content", "fill_form", "screenshot"]:
            if not self.task_params.get("url"):
                errors.append(f"{self.task_type} 任务需要指定 url 参数")
        elif self.task_type == "search":
            if not self.task_params.get("query"):
                errors.append("搜索任务需要指定 query 参数")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


def create_browser_use_node(
    name: str = "浏览器自动化",
    task_type: str = "execute",
    task_params: Optional[Dict[str, Any]] = None,
    result_variable: str = "browser_result",
    browser_config: Optional[Dict[str, Any]] = None
) -> BrowserUseNode:
    """
    创建 browser-use 节点
    
    Args:
        name: 节点名称
        task_type: 任务类型
        task_params: 任务参数
        result_variable: 结果变量名
        browser_config: 浏览器配置
        
    Returns:
        BrowserUseNode: 节点实例
    """
    return BrowserUseNode(
        name=name,
        task_type=task_type,
        task_params=task_params or {},
        result_variable=result_variable,
        browser_config=browser_config or {}
    )
