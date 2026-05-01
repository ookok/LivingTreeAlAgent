import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

class ToolCategory(Enum):
    SEARCH = "search"
    CODE = "code"
    DATA = "data"
    FILE = "file"
    WEB = "web"
    SYSTEM = "system"

@dataclass
class Tool:
    name: str
    description: str
    category: ToolCategory
    func: Callable
    parameters: List[Dict[str, Any]]
    enabled: bool = True
    usage_count: int = 0
    success_rate: float = 1.0

@dataclass
class ToolCallResult:
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0

class ToolManager:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.call_history: List[dict] = []
        self.semaphore = asyncio.Semaphore(5)
    
    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
    
    def unregister_tool(self, tool_name: str):
        """取消注册工具"""
        if tool_name in self.tools:
            del self.tools[tool_name]
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """获取工具"""
        return self.tools.get(tool_name)
    
    def get_tools_by_category(self, category: ToolCategory) -> List[Tool]:
        """按类别获取工具"""
        return [t for t in self.tools.values() if t.category == category and t.enabled]
    
    def get_all_tools(self) -> List[Tool]:
        """获取所有可用工具"""
        return [t for t in self.tools.values() if t.enabled]
    
    async def call_tool(self, tool_name: str, **kwargs) -> ToolCallResult:
        """调用单个工具"""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolCallResult(tool_name=tool_name, success=False, result=None, error="工具不存在")
        
        start_time = asyncio.get_event_loop().time()
        try:
            async with self.semaphore:
                result = await asyncio.to_thread(tool.func, **kwargs)
                tool.usage_count += 1
                execution_time = asyncio.get_event_loop().time() - start_time
                
                self.call_history.append({
                    "tool_name": tool_name,
                    "success": True,
                    "execution_time": execution_time,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
                return ToolCallResult(
                    tool_name=tool_name,
                    success=True,
                    result=result,
                    execution_time=execution_time
                )
        except Exception as e:
            tool.success_rate = (tool.success_rate * tool.usage_count) / (tool.usage_count + 1)
            execution_time = asyncio.get_event_loop().time() - start_time
            
            self.call_history.append({
                "tool_name": tool_name,
                "success": False,
                "error": str(e),
                "execution_time": execution_time,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            return ToolCallResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time
            )
    
    async def call_tools_parallel(self, tool_calls: List[dict]) -> List[ToolCallResult]:
        """并行调用多个工具"""
        tasks = []
        for call in tool_calls:
            tool_name = call.get("tool_name")
            kwargs = call.get("parameters", {})
            tasks.append(self.call_tool(tool_name, **kwargs))
        
        results = await asyncio.gather(*tasks)
        return results
    
    def suggest_tools(self, query: str, top_n: int = 3) -> List[Tool]:
        """智能工具选择 - 根据查询推荐最相关的工具"""
        query_lower = query.lower()
        scores = []
        
        for tool in self.tools.values():
            if not tool.enabled:
                continue
            
            score = 0
            
            if tool.name.lower() in query_lower:
                score += 5
            if tool.description.lower() in query_lower:
                score += 3
            
            for param in tool.parameters:
                if param.get("name", "").lower() in query_lower:
                    score += 1
            
            score += tool.success_rate * 2
            score += min(tool.usage_count / 100, 3)
            
            if score > 0:
                scores.append((tool, score))
        
        scores.sort(key=lambda x: -x[1])
        return [t[0] for t in scores[:top_n]]
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """获取工具调用统计"""
        stats = {
            "total_tools": len(self.tools),
            "enabled_tools": sum(1 for t in self.tools.values() if t.enabled),
            "total_calls": sum(t.usage_count for t in self.tools.values()),
            "avg_success_rate": sum(t.success_rate for t in self.tools.values()) / len(self.tools) if self.tools else 0,
            "category_distribution": {}
        }
        
        for category in ToolCategory:
            count = sum(1 for t in self.tools.values() if t.category == category)
            stats["category_distribution"][category.value] = count
        
        return stats

class SmartToolSelector:
    """智能工具选择器"""
    
    def __init__(self, tool_manager: ToolManager):
        self.tool_manager = tool_manager
        self.context_history = []
    
    def update_context(self, context: dict):
        """更新上下文"""
        self.context_history.append(context)
        if len(self.context_history) > 10:
            self.context_history = self.context_history[-10:]
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """分析查询意图"""
        query_lower = query.lower()
        
        intents = {
            "search": ["搜索", "查找", "查询", "find", "search", "look up"],
            "code": ["代码", "编程", "python", "javascript", "写代码", "code"],
            "data": ["数据", "分析", "统计", "图表", "data", "analyze"],
            "file": ["文件", "保存", "读取", "上传", "下载", "file"],
            "web": ["网页", "网站", "url", "http", "浏览器"],
            "system": ["系统", "设置", "配置", "system", "config"]
        }
        
        detected_intent = None
        max_matches = 0
        
        for intent, keywords in intents.items():
            matches = sum(1 for kw in keywords if kw.lower() in query_lower)
            if matches > max_matches:
                max_matches = matches
                detected_intent = intent
        
        return {
            "intent": detected_intent,
            "confidence": min(max_matches / 3, 1.0) if detected_intent else 0,
            "keywords": [kw for kw in query_lower.split() if len(kw) > 2]
        }
    
    def select_tools(self, query: str) -> List[Tool]:
        """选择最合适的工具"""
        analysis = self.analyze_query(query)
        
        if analysis["confidence"] > 0.5:
            category = ToolCategory(analysis["intent"])
            category_tools = self.tool_manager.get_tools_by_category(category)
            if category_tools:
                return sorted(category_tools, key=lambda t: -t.success_rate)[:3]
        
        return self.tool_manager.suggest_tools(query)
    
    def plan_tool_calls(self, query: str) -> List[dict]:
        """规划工具调用序列"""
        tools = self.select_tools(query)
        plan = []
        
        for tool in tools[:2]:
            plan.append({
                "tool_name": tool.name,
                "parameters": self._extract_parameters(query, tool),
                "priority": tools.index(tool) + 1
            })
        
        return plan
    
    def _extract_parameters(self, query: str, tool: Tool) -> dict:
        """从查询中提取参数"""
        params = {}
        query_lower = query.lower()
        
        for param in tool.parameters:
            param_name = param["name"]
            if param.get("type") == "string":
                params[param_name] = query
            elif param.get("type") == "boolean":
                params[param_name] = True
        
        return params