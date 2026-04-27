"""
BaseToolAgent - 工具层基类
============================

所有使用统一工具层的智能体的基类。
提供工具发现、工具执行、工具描述生成等核心能力。

架构定位：
    智能体层 (BaseToolAgent)
        | 调用 discover_tools() / execute_tool()
        v
    统一工具层 (ToolRegistry)
        | 路由
        v
    工具实现层 (BaseTool subclasses)

Author: LivingTreeAI Agent
Date: 2026-04-27
"""

import json
import time
import logging
from typing import Any, Optional, List, Dict, Callable
from dataclasses import dataclass, field

from client.src.business.unified_tool_registry import (
    ToolRegistry,
    ToolResult,
    search_tools,
    list_all_tools,
    execute_tool,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolCallResult:
    """工具调用结果"""
    name: str
    success: bool
    data: Any = None
    error: str = ""
    duration_ms: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class BaseToolAgent:
    """
    基于统一工具层的智能体基类。
    
    提供：
    - discover_tools() - 语义搜索发现所需工具
    - execute_tool() - 统一执行工具
    - get_available_tools() - 获取当前可用工具
    - build_tool_schema() - 构建 OpenAI tools schema
    - get_tool_descriptions() - 生成工具描述文本（供系统提示使用）
    """
    
    def __init__(self, enabled_toolsets: Optional[List[str]] = None):
        """
        Args:
            enabled_toolsets: 启用的工具集列表，如 ["core", "search", "geospatial"]
        """
        self._registry = ToolRegistry.get_instance()
        self._enabled_toolsets = enabled_toolsets or ["core"]
        
        # 工具调用统计
        self._tool_stats: Dict[str, int] = {}  # {tool_name: call_count}
        self._tool_errors: Dict[str, str] = {}  # {tool_name: last_error}
    
    # ── 核心方法 ───────────────────────────────────────────────────────
    
    def discover_tools(
        self,
        task_description: str,
        max_results: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        语义搜索发现适合任务的工具。
        
        使用统一的 ToolRegistry 做关键词 + 语义双重匹配。
        
        Args:
            task_description: 任务描述文本
            max_results: 最大返回数量
            category: 可选，按分类过滤
            
        Returns:
            工具定义列表，每个元素包含 {name, description, category, relevance_score}
        """
        # 1. 语义搜索
        semantic_results = search_tools(task_description)
        
        # 2. 如果有分类要求，过滤结果
        if category:
            semantic_results = [
                r for r in semantic_results
                if r.get("category") == category
            ]
        
        # 3. 限制数量
        results = semantic_results[:max_results]
        
        # 4. 补充完整信息
        enriched = []
        for r in results:
            tool_def = self._registry.get_tool(r.get("name", ""))
            if tool_def:
                enriched.append({
                    "name": tool_def.name,
                    "description": tool_def.definition.description,
                    "category": tool_def.definition.category,
                    "tags": tool_def.definition.tags,
                    "parameters": tool_def.definition.parameters,
                    "relevance_score": r.get("score", 0.0),
                })
        
        logger.info(f"[BaseToolAgent] 发现 {len(enriched)} 个工具用于任务: {task_description[:50]}")
        return enriched
    
    def execute_tool(
        self,
        tool_name: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ToolCallResult:
        """
        统一执行工具（同步版本）。
        
        Args:
            tool_name: 工具名称
            context: 可选的上下文信息（会被注入到 kwargs 中）
            **kwargs: 工具参数
            
        Returns:
            ToolCallResult 包含执行结果或错误信息
        """
        start_time = time.time()
        
        # 合并 context 到 kwargs
        merged_kwargs = kwargs.copy()
        if context:
            merged_kwargs.setdefault("context", context)
        
        try:
            # 通过统一注册中心执行
            result = execute_tool(tool_name, **merged_kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # 更新统计
            self._record_call(tool_name, success=True)
            
            if isinstance(result, ToolResult):
                return ToolCallResult(
                    name=tool_name,
                    success=result.success,
                    data=result.data,
                    error=result.error or "",
                    duration_ms=duration_ms,
                )
            else:
                # 兼容旧格式返回值
                return ToolCallResult(
                    name=tool_name,
                    success=result.get("success", True) if isinstance(result, dict) else True,
                    data=result,
                    error="",
                    duration_ms=duration_ms,
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._record_call(tool_name, success=False, error=error_msg)
            logger.error(f"[BaseToolAgent] 工具 {tool_name} 执行失败: {error_msg}")
            
            return ToolCallResult(
                name=tool_name,
                success=False,
                error=error_msg,
                duration_ms=duration_ms,
            )
    
    async def execute_tool_async(
        self,
        tool_name: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ToolCallResult:
        """
        异步执行工具。
        
        对于需要异步处理的工具（如 HTTP 请求、文件 I/O），使用此方法。
        """
        import asyncio
        
        def _sync_wrapper():
            return self.execute_tool(tool_name, context, **kwargs)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_wrapper)
    
    # ── 工具信息 ───────────────────────────────────────────────────────
    
    def get_available_tools(self, toolset: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取当前可用的工具列表。
        
        Args:
            toolset: 可选，按工具集过滤
            
        Returns:
            工具信息列表
        """
        if toolset:
            from client.src.business.unified_tool_registry import CompatibleToolRegistry
            tools = CompatibleToolRegistry.get_by_toolset(toolset)
            return [
                {"name": t.name, "description": t.description, "parameters": t.parameters}
                for t in tools if t
            ]
        
        all_tools = list_all_tools()
        return [
            {
                "name": t.name if hasattr(t, "name") else str(t),
                "description": getattr(t, "description", ""),
                "category": getattr(t, "category", "general"),
            }
            for t in all_tools
        ]
    
    def build_tool_schema(self) -> List[Dict[str, Any]]:
        """
        构建 OpenAI tools schema。
        
        用于 LLM 函数调用接口。
        
        Returns:
            OpenAI tools format 的 schema 列表
        """
        from client.src.business.unified_tool_registry import CompatibleToolRegistry
        
        # 获取启用的工具
        tools = []
        for ts in self._enabled_toolsets:
            ts_tools = CompatibleToolRegistry.get_by_toolset(ts)
            tools.extend([t for t in ts_tools if t])
        
        # 去重
        seen = set()
        unique_tools = []
        for t in tools:
            if t.name not in seen:
                seen.add(t.name)
                unique_tools.append(t)
        
        # 转换为 schema
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters or {"type": "object", "properties": {}},
                }
            }
            for t in unique_tools
        ]
    
    def get_tool_descriptions(self) -> str:
        """
        生成工具描述文本（供系统提示使用）。
        
        Returns:
            Markdown 格式的工具列表描述
        """
        from client.src.business.unified_tool_registry import CompatibleToolRegistry
        
        tools = []
        for ts in self._enabled_toolsets:
            ts_tools = CompatibleToolRegistry.get_by_toolset(ts)
            tools.extend([t for t in ts_tools if t])
        
        # 去重
        seen = set()
        lines = []
        for t in tools:
            if t.name not in seen:
                seen.add(t.name)
                params_str = ""
                if t.parameters and t.parameters.get("properties"):
                    props = list(t.parameters["properties"].keys())
                    params_str = f" (参数: {', '.join(props)})" if props else ""
                lines.append(f"- **{t.name}**: {t.description}{params_str}")
        
        return "\n".join(lines)
    
    def list_tool_categories(self) -> List[str]:
        """获取所有工具分类"""
        return list(self._registry._categories.keys())
    
    # ── 统计 ─────────────────────────────────────────────────────────
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """获取工具使用统计"""
        from client.src.business.unified_tool_registry import get_stats
        
        registry_stats = get_stats()
        
        return {
            "call_counts": dict(self._tool_stats),
            "errors": dict(self._tool_errors),
            "registry": registry_stats,
        }
    
    def _record_call(self, tool_name: str, success: bool, error: str = ""):
        """记录工具调用"""
        if tool_name not in self._tool_stats:
            self._tool_stats[tool_name] = 0
        self._tool_stats[tool_name] += 1
        
        if not success:
            self._tool_errors[tool_name] = error


# ── 便捷函数 ────────────────────────────────────────────────────────────

def create_base_agent(enabled_toolsets: Optional[List[str]] = None) -> BaseToolAgent:
    """
    创建 BaseToolAgent 实例的便捷工厂函数。
    
    自动初始化工具注册中心（如果尚未初始化）。
    """
    from client.src.business.tools.register_all_tools import register_all_tools
    
    # 确保所有工具已注册
    register_all_tools()
    
    return BaseToolAgent(enabled_toolsets=enabled_toolsets)
