"""
优化引导器 (Optimization Bootstrapper)
======================================

一键启用所有优化功能：
1. RTK 集成 - 基于 Rust Token Killer 理念的上下文压缩
2. Code Review Graph - 代码审查图谱集成
3. Context Mode - 智能上下文管理模式

核心特性：
- 一键启用所有优化组件
- 智能检测并配置最优策略
- 统一的优化状态管理
- 性能监控和报告

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OptimizationState(Enum):
    """优化状态"""
    DISABLED = "disabled"
    ENABLED = "enabled"
    INITIALIZING = "initializing"
    ERROR = "error"


class OptimizationModule(Enum):
    """优化模块"""
    RTK_COMPRESSION = "rtk_compression"
    PROMPT_CACHING = "prompt_caching"
    TOKEN_OPTIMIZATION = "token_optimization"
    COST_MANAGEMENT = "cost_management"
    CODE_REVIEW_GRAPH = "code_review_graph"
    CONTEXT_MODE = "context_mode"


@dataclass
class ModuleStatus:
    """模块状态"""
    module: OptimizationModule
    state: OptimizationState
    message: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationSummary:
    """优化摘要"""
    enabled_modules: List[str]
    total_tokens_saved: int = 0
    total_cost_saved: float = 0.0
    cache_hit_rate: float = 0.0
    compression_ratio: float = 0.0


class OptimizationBootstrapper:
    """
    优化引导器
    
    提供一键启用所有优化功能的入口，包括：
    1. RTK 集成 - 上下文压缩优化
    2. Code Review Graph - 代码审查图谱
    3. Context Mode - 智能上下文管理
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 模块状态
        self._module_status: Dict[OptimizationModule, ModuleStatus] = {}
        
        # 优化组件（延迟加载）
        self._context_preprocessor = None
        self._model_optimization_proxy = None
        self._code_review_graph = None
        self._context_mode_manager = None
        
        # 是否已启用优化
        self._optimization_enabled = False
        
        self._initialized = True
        logger.info("[OptimizationBootstrapper] 优化引导器初始化完成")
    
    def enable_all_optimizations(self) -> Dict[str, Any]:
        """
        一键启用所有优化功能
        
        Returns:
            启用结果摘要
        """
        results = {
            "success": True,
            "modules": [],
            "message": "",
        }
        
        try:
            logger.info("[OptimizationBootstrapper] 开始启用所有优化...")
            
            # 1. 启用 RTK 压缩
            rtk_result = self._enable_rtk_compression()
            results["modules"].append({"name": "RTK Compression", **rtk_result})
            
            # 2. 启用模型优化代理
            proxy_result = self._enable_model_optimization()
            results["modules"].append({"name": "Model Optimization Proxy", **proxy_result})
            
            # 3. 启用代码审查图谱
            review_result = self._enable_code_review_graph()
            results["modules"].append({"name": "Code Review Graph", **review_result})
            
            # 4. 启用 Context Mode
            context_result = self._enable_context_mode()
            results["modules"].append({"name": "Context Mode", **context_result})
            
            self._optimization_enabled = True
            
            results["message"] = "所有优化功能已成功启用！"
            logger.info(f"[OptimizationBootstrapper] {results['message']}")
            
        except Exception as e:
            results["success"] = False
            results["message"] = f"启用优化失败: {str(e)}"
            logger.error(f"[OptimizationBootstrapper] 启用优化失败: {e}")
        
        return results
    
    def disable_all_optimizations(self) -> Dict[str, Any]:
        """
        一键禁用所有优化功能
        
        Returns:
            禁用结果摘要
        """
        try:
            # 重置所有模块状态
            for module in OptimizationModule:
                self._module_status[module] = ModuleStatus(
                    module=module,
                    state=OptimizationState.DISABLED,
                    message="已禁用"
                )
            
            self._optimization_enabled = False
            logger.info("[OptimizationBootstrapper] 所有优化功能已禁用")
            
            return {
                "success": True,
                "message": "所有优化功能已成功禁用"
            }
        except Exception as e:
            logger.error(f"[OptimizationBootstrapper] 禁用优化失败: {e}")
            return {
                "success": False,
                "message": f"禁用优化失败: {str(e)}"
            }
    
    def is_optimization_enabled(self) -> bool:
        """检查优化是否已启用"""
        return self._optimization_enabled
    
    def get_module_status(self, module: OptimizationModule) -> Optional[ModuleStatus]:
        """获取指定模块的状态"""
        return self._module_status.get(module)
    
    def get_all_status(self) -> Dict[str, ModuleStatus]:
        """获取所有模块状态"""
        return {m.value: status for m, status in self._module_status.items()}
    
    def get_optimization_summary(self) -> OptimizationSummary:
        """获取优化摘要"""
        enabled_modules = [
            m.value for m, status in self._module_status.items()
            if status.state == OptimizationState.ENABLED
        ]
        
        return OptimizationSummary(
            enabled_modules=enabled_modules,
            total_tokens_saved=self._get_total_tokens_saved(),
            total_cost_saved=self._get_total_cost_saved(),
            cache_hit_rate=self._get_cache_hit_rate(),
            compression_ratio=self._get_compression_ratio(),
        )
    
    # ─── RTK 集成 ───
    
    def _enable_rtk_compression(self) -> Dict[str, Any]:
        """启用 RTK 压缩优化"""
        try:
            from business.context_preprocessor import ContextPreprocessor
            
            self._context_preprocessor = ContextPreprocessor(
                max_context_tokens=8192,
                compression_ratio=0.3,
                enable_compression=True,
                enable_dedup=True,
                enable_extraction=True,
                importance_threshold=3.0,
            )
            
            self._module_status[OptimizationModule.RTK_COMPRESSION] = ModuleStatus(
                module=OptimizationModule.RTK_COMPRESSION,
                state=OptimizationState.ENABLED,
                message="RTK 压缩优化已启用",
                metrics={"compression_ratio": 0.3, "max_tokens": 8192}
            )
            
            logger.info("[OptimizationBootstrapper] RTK 压缩优化已启用")
            return {"success": True, "message": "RTK 压缩优化已启用"}
        
        except Exception as e:
            self._module_status[OptimizationModule.RTK_COMPRESSION] = ModuleStatus(
                module=OptimizationModule.RTK_COMPRESSION,
                state=OptimizationState.ERROR,
                message=f"启用失败: {str(e)}"
            )
            logger.error(f"[OptimizationBootstrapper] RTK 压缩启用失败: {e}")
            return {"success": False, "message": str(e)}
    
    def process_context(self, segments: List[Any]) -> List[Any]:
        """
        使用 RTK 处理上下文
        
        Args:
            segments: 上下文片段列表
            
        Returns:
            优化后的上下文片段
        """
        if not self._context_preprocessor:
            return segments
        
        return self._context_preprocessor.process_context(segments)
    
    def process_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        使用 RTK 处理消息列表
        
        Args:
            messages: 消息列表
            
        Returns:
            优化后的消息列表
        """
        if not self._context_preprocessor:
            return messages
        
        return self._context_preprocessor.process_messages(messages)
    
    # ─── 模型优化代理 ───
    
    def _enable_model_optimization(self) -> Dict[str, Any]:
        """启用模型优化代理"""
        try:
            from business.model_optimization_proxy import (
                get_model_optimization_proxy,
                OptimizationFeature
            )
            
            self._model_optimization_proxy = get_model_optimization_proxy()
            
            # 启用所有优化特性
            self._model_optimization_proxy.set_feature(OptimizationFeature.TOKEN_OPTIMIZATION, True)
            self._model_optimization_proxy.set_feature(OptimizationFeature.PROMPT_CACHING, True)
            self._model_optimization_proxy.set_feature(OptimizationFeature.TOKEN_COMPRESSION, True)
            self._model_optimization_proxy.set_feature(OptimizationFeature.COST_MANAGEMENT, True)
            
            self._module_status[OptimizationModule.TOKEN_OPTIMIZATION] = ModuleStatus(
                module=OptimizationModule.TOKEN_OPTIMIZATION,
                state=OptimizationState.ENABLED,
                message="Token 优化已启用",
                metrics={"features": ["token_optimization", "prompt_caching", "token_compression", "cost_management"]}
            )
            
            logger.info("[OptimizationBootstrapper] 模型优化代理已启用")
            return {"success": True, "message": "模型优化代理已启用"}
        
        except Exception as e:
            self._module_status[OptimizationModule.TOKEN_OPTIMIZATION] = ModuleStatus(
                module=OptimizationModule.TOKEN_OPTIMIZATION,
                state=OptimizationState.ERROR,
                message=f"启用失败: {str(e)}"
            )
            logger.error(f"[OptimizationBootstrapper] 模型优化代理启用失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def call_with_optimization(self, prompt: str, model_callable: Callable, **kwargs):
        """
        带优化的模型调用
        
        Args:
            prompt: 提示词
            model_callable: 模型调用函数
            **kwargs: 额外参数
            
        Returns:
            (响应, 元数据)
        """
        if not self._model_optimization_proxy:
            return await model_callable(prompt) if hasattr(model_callable, '__aiter__') else model_callable(prompt), {}
        
        return await self._model_optimization_proxy.call_with_optimization(prompt, model_callable, **kwargs)
    
    # ─── Code Review Graph 集成 ───
    
    def _enable_code_review_graph(self) -> Dict[str, Any]:
        """启用代码审查图谱"""
        try:
            from business.code_review_graph import CodeReviewGraph
            
            self._code_review_graph = CodeReviewGraph()
            
            self._module_status[OptimizationModule.CODE_REVIEW_GRAPH] = ModuleStatus(
                module=OptimizationModule.CODE_REVIEW_GRAPH,
                state=OptimizationState.ENABLED,
                message="代码审查图谱已启用",
                metrics={"analysis_types": ["complexity", "security", "style", "performance"]}
            )
            
            logger.info("[OptimizationBootstrapper] 代码审查图谱已启用")
            return {"success": True, "message": "代码审查图谱已启用"}
        
        except Exception as e:
            self._module_status[OptimizationModule.CODE_REVIEW_GRAPH] = ModuleStatus(
                module=OptimizationModule.CODE_REVIEW_GRAPH,
                state=OptimizationState.ERROR,
                message=f"启用失败: {str(e)}"
            )
            logger.error(f"[OptimizationBootstrapper] 代码审查图谱启用失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def analyze_code(self, code: str, file_path: str = "") -> Dict[str, Any]:
        """
        分析代码（使用代码审查图谱）
        
        Args:
            code: 代码内容
            file_path: 文件路径
            
        Returns:
            分析结果
        """
        if not self._code_review_graph:
            return {"error": "代码审查图谱未启用"}
        
        return await self._code_review_graph.analyze(code, file_path)
    
    # ─── Context Mode 集成 ───
    
    def _enable_context_mode(self) -> Dict[str, Any]:
        """启用 Context Mode"""
        try:
            from business.context_mode_manager import ContextModeManager
            
            self._context_mode_manager = ContextModeManager()
            
            self._module_status[OptimizationModule.CONTEXT_MODE] = ModuleStatus(
                module=OptimizationModule.CONTEXT_MODE,
                state=OptimizationState.ENABLED,
                message="Context Mode 已启用",
                metrics={"modes": ["automatic", "manual", "selective"]}
            )
            
            logger.info("[OptimizationBootstrapper] Context Mode 已启用")
            return {"success": True, "message": "Context Mode 已启用"}
        
        except Exception as e:
            self._module_status[OptimizationModule.CONTEXT_MODE] = ModuleStatus(
                module=OptimizationModule.CONTEXT_MODE,
                state=OptimizationState.ERROR,
                message=f"启用失败: {str(e)}"
            )
            logger.error(f"[OptimizationBootstrapper] Context Mode 启用失败: {e}")
            return {"success": False, "message": str(e)}
    
    def set_context_mode(self, mode: str):
        """
        设置上下文模式
        
        Args:
            mode: 模式名称（automatic/manual/selective）
        """
        if self._context_mode_manager:
            self._context_mode_manager.set_mode(mode)
    
    def get_context_suggestion(self, query: str) -> Dict[str, Any]:
        """
        获取上下文建议
        
        Args:
            query: 用户查询
            
        Returns:
            上下文建议
        """
        if not self._context_mode_manager:
            return {"error": "Context Mode 未启用"}
        
        return self._context_mode_manager.get_suggestion(query)
    
    # ─── 统计信息 ───
    
    def _get_total_tokens_saved(self) -> int:
        """获取总节省的 token 数"""
        if self._model_optimization_proxy:
            return self._model_optimization_proxy.get_stats().token_saved
        return 0
    
    def _get_total_cost_saved(self) -> float:
        """获取总节省的成本"""
        if self._model_optimization_proxy:
            return self._model_optimization_proxy.get_stats().cost_saved
        return 0.0
    
    def _get_cache_hit_rate(self) -> float:
        """获取缓存命中率"""
        if self._model_optimization_proxy:
            report = self._model_optimization_proxy.get_full_report()
            return report.get("cache_hit_rate", 0.0)
        return 0.0
    
    def _get_compression_ratio(self) -> float:
        """获取压缩率"""
        if self._context_preprocessor:
            return self._context_preprocessor.get_stats().compression_ratio
        return 0.0
    
    def get_full_report(self) -> Dict[str, Any]:
        """获取完整的优化报告"""
        summary = self.get_optimization_summary()
        
        return {
            "optimization_enabled": self._optimization_enabled,
            "modules": self.get_all_status(),
            "summary": {
                "enabled_modules": summary.enabled_modules,
                "total_tokens_saved": summary.total_tokens_saved,
                "total_cost_saved": f"${summary.total_cost_saved:.2f}",
                "cache_hit_rate": f"{summary.cache_hit_rate:.2%}",
                "compression_ratio": f"{summary.compression_ratio:.1f}%",
            },
        }


# 便捷函数
def get_optimization_bootstrapper() -> OptimizationBootstrapper:
    """获取优化引导器单例"""
    return OptimizationBootstrapper()


def enable_all_optimizations() -> Dict[str, Any]:
    """一键启用所有优化（便捷函数）"""
    bootstrapper = get_optimization_bootstrapper()
    return bootstrapper.enable_all_optimizations()


__all__ = [
    "OptimizationState",
    "OptimizationModule",
    "ModuleStatus",
    "OptimizationSummary",
    "OptimizationBootstrapper",
    "get_optimization_bootstrapper",
    "enable_all_optimizations",
]
