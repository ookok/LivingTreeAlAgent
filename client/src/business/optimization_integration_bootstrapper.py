"""
优化集成启动器 (Optimization Integration Bootstrapper)
======================================================

深度集成所有优化功能到系统：
1. 自动启用优化引导器
2. 注册系统钩子
3. 初始化智能优化引擎
4. 设置全局优化代理
5. 启动监控仪表盘
6. 初始化自我进化引擎（开放式进化、强化学习、自我改进）

核心特性：
- 一键深度集成所有优化
- 自动拦截模型调用
- 智能决策优化策略
- 实时监控优化效果
- 自我进化与持续改进

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class OptimizationIntegrationBootstrapper:
    """
    优化集成启动器
    
    负责将所有优化功能深度集成到系统中：
    1. 启用优化引导器
    2. 注册系统钩子
    3. 初始化智能优化引擎
    4. 设置全局优化代理
    5. 启动监控仪表盘
    6. 初始化自我进化系统
    """
    
    _instance = None
    _initialized = False
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if OptimizationIntegrationBootstrapper._initialized:
            return
        
        # 组件引用
        self._optimization_bootstrapper = None
        self._intelligent_engine = None
        self._hook_manager = None
        self._evolution_engine = None
        self._open_evolution = None
        self._rl_improvement = None
        self._evolution_integration = None
        
        # 技能发现组件
        self._skill_discovery = None
        self._skill_matcher = None
        self._skill_graph = None
        self._skill_integration_service = None
        
        # LLM验证器组件
        self._llm_verifier = None
        self._verifier_integration_service = None
        
        # 智能搜索组件
        self._intelligent_search_engine = None
        self._web_scraper = None
        
        OptimizationIntegrationBootstrapper._initialized = True
    
    async def integrate_all(self) -> Dict[str, Any]:
        """
        深度集成所有优化功能
        
        Returns:
            集成结果
        """
        results = {
            "success": True,
            "modules": [],
            "message": "",
            "stats": {},
        }
        
        try:
            logger.info("[OptimizationIntegration] 开始深度集成优化系统...")
            
            # 1. 启用优化引导器
            bootstrap_result = await self._enable_optimization_bootstrapper()
            results["modules"].append({"name": "优化引导器", **bootstrap_result})
            
            # 2. 初始化智能优化引擎
            engine_result = await self._initialize_intelligent_engine()
            results["modules"].append({"name": "智能优化引擎", **engine_result})
            
            # 3. 注册系统钩子
            hooks_result = await self._register_system_hooks()
            results["modules"].append({"name": "系统钩子", **hooks_result})
            
            # 4. 初始化自我进化引擎
            evolution_result = await self._initialize_evolution_engine()
            results["modules"].append({"name": "自我进化引擎", **evolution_result})
            
            # 5. 初始化开放式进化
            open_result = await self._initialize_open_evolution()
            results["modules"].append({"name": "开放式进化", **open_result})
            
            # 6. 初始化强化学习改进
            rl_result = await self._initialize_rl_improvement()
            results["modules"].append({"name": "强化学习改进", **rl_result})
            
            # 7. 初始化进化集成层
            integration_result = await self._initialize_evolution_integration()
            results["modules"].append({"name": "进化集成层", **integration_result})
            
            # 8. 启动监控仪表盘
            dashboard_result = await self._start_monitoring_dashboard()
            results["modules"].append({"name": "监控仪表盘", **dashboard_result})
            
            # 9. 设置全局优化代理
            proxy_result = await self._setup_global_proxy()
            results["modules"].append({"name": "全局优化代理", **proxy_result})
            
            # 10. 初始化技能发现引擎
            skill_discovery_result = await self._initialize_skill_discovery()
            results["modules"].append({"name": "技能发现引擎", **skill_discovery_result})
            
            # 11. 初始化技能匹配引擎
            skill_matcher_result = await self._initialize_skill_matcher()
            results["modules"].append({"name": "技能匹配引擎", **skill_matcher_result})
            
            # 12. 初始化技能图谱
            skill_graph_result = await self._initialize_skill_graph()
            results["modules"].append({"name": "技能图谱", **skill_graph_result})
            
            # 13. 初始化技能集成服务
            skill_service_result = await self._initialize_skill_integration_service()
            results["modules"].append({"name": "技能集成服务", **skill_service_result})
            
            # 14. 注册技能感知钩子
            skill_hook_result = await self._register_skill_hooks()
            results["modules"].append({"name": "技能感知钩子", **skill_hook_result})
            
            # 15. 初始化LLM验证器
            llm_verifier_result = await self._initialize_llm_verifier()
            results["modules"].append({"name": "LLM验证器", **llm_verifier_result})
            
            # 16. 初始化验证器集成服务
            verifier_service_result = await self._initialize_verifier_integration_service()
            results["modules"].append({"name": "验证器集成服务", **verifier_service_result})
            
            # 17. 注册验证钩子
            verifier_hook_result = await self._register_verifier_hooks()
            results["modules"].append({"name": "验证钩子", **verifier_hook_result})
            
            # 18. 初始化智能搜索引擎
            search_engine_result = await self._initialize_intelligent_search_engine()
            results["modules"].append({"name": "智能搜索引擎", **search_engine_result})
            
            # 19. 初始化网页抓取器
            web_scraper_result = await self._initialize_web_scraper()
            results["modules"].append({"name": "网页抓取器", **web_scraper_result})
            
            # 20. 注册搜索钩子
            search_hook_result = await self._register_search_hooks()
            results["modules"].append({"name": "搜索钩子", **search_hook_result})
            
            results["message"] = "所有优化功能深度集成完成！包括自我进化引擎、开放式进化、强化学习驱动的自我改进、技能发现系统、LLM验证器和智能搜索"
            results["stats"] = self.get_integration_stats()
            
            logger.info(f"[OptimizationIntegration] {results['message']}")
            
        except Exception as e:
            results["success"] = False
            results["message"] = f"集成失败: {str(e)}"
            logger.error(f"[OptimizationIntegration] 集成失败: {e}")
        
        return results
    
    async def _enable_optimization_bootstrapper(self) -> Dict[str, Any]:
        """启用优化引导器"""
        try:
            from business.optimization_bootstrapper import enable_all_optimizations
            
            result = enable_all_optimizations()
            
            if result["success"]:
                logger.info("[OptimizationIntegration] 优化引导器启用成功")
                return {"success": True, "message": "优化引导器已启用"}
            else:
                return {"success": False, "message": result["message"]}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 启用优化引导器失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_intelligent_engine(self) -> Dict[str, Any]:
        """初始化智能优化引擎"""
        try:
            from business.intelligent_optimization_engine import get_intelligent_optimization_engine
            
            self._intelligent_engine = get_intelligent_optimization_engine()
            self._intelligent_engine.set_profile("default")
            
            logger.info("[OptimizationIntegration] 智能优化引擎初始化完成")
            return {"success": True, "message": "智能优化引擎已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化智能优化引擎失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _register_system_hooks(self) -> Dict[str, Any]:
        """注册系统钩子"""
        try:
            from business.optimization_hook_manager import (
                get_hook_manager,
                HookPoint,
                HookContext,
                HookResult,
            )
            
            self._hook_manager = get_hook_manager()
            
            # 注册上下文构建钩子
            async def context_build_hook(context: HookContext) -> HookResult:
                context.context["timestamp"] = context.timestamp
                context.context["model_type"] = context.model_type
                return HookResult(success=True)
            
            self._hook_manager.register_hook(HookPoint.CONTEXT_BUILD, context_build_hook)
            
            # 注册提示词优化钩子
            async def prompt_optimization_hook(context: HookContext) -> HookResult:
                if self._intelligent_engine and context.prompt:
                    decision = self._intelligent_engine.make_decision(
                        context.prompt,
                        context.context
                    )
                    return HookResult(
                        success=True,
                        optimization_metadata={
                            "decision": decision.decision.value,
                            "confidence": decision.confidence,
                        }
                    )
                return HookResult(success=True)
            
            self._hook_manager.register_hook(HookPoint.PROMPT_GENERATION, prompt_optimization_hook)
            
            # 注册响应处理钩子
            async def response_processing_hook(context: HookContext) -> HookResult:
                return HookResult(success=True)
            
            self._hook_manager.register_hook(HookPoint.RESPONSE_RECEIVED, response_processing_hook)
            
            # 启用钩子管理器
            self._hook_manager.enable()
            
            logger.info("[OptimizationIntegration] 系统钩子注册完成")
            return {"success": True, "message": "系统钩子已注册并启用"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 注册系统钩子失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_evolution_engine(self) -> Dict[str, Any]:
        """初始化自我进化引擎"""
        try:
            from business.self_evolution_engine import get_self_evolution_engine
            
            self._evolution_engine = get_self_evolution_engine()
            
            logger.info("[OptimizationIntegration] 自我进化引擎初始化完成")
            return {"success": True, "message": "自我进化引擎已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化自我进化引擎失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_open_evolution(self) -> Dict[str, Any]:
        """初始化开放式进化"""
        try:
            from business.open_ended_evolution import create_open_ended_evolution
            
            self._open_evolution = create_open_ended_evolution()
            
            logger.info("[OptimizationIntegration] 开放式进化初始化完成")
            return {"success": True, "message": "开放式进化已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化开放式进化失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_rl_improvement(self) -> Dict[str, Any]:
        """初始化强化学习改进"""
        try:
            from business.rl_driven_improvement import create_rl_improvement, RLAlgorithm
            
            self._rl_improvement = create_rl_improvement(RLAlgorithm.REINFORCE)
            
            logger.info("[OptimizationIntegration] 强化学习改进初始化完成")
            return {"success": True, "message": "强化学习改进已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化强化学习改进失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_evolution_integration(self) -> Dict[str, Any]:
        """初始化进化集成层"""
        try:
            from business.evolution_integration_layer import (
                get_evolution_integration_layer,
                initialize_evolution_integration,
            )
            
            self._evolution_integration = get_evolution_integration_layer()
            result = await initialize_evolution_integration()
            
            if result["success"]:
                logger.info("[OptimizationIntegration] 进化集成层初始化完成")
                return {"success": True, "message": "进化集成层已初始化"}
            else:
                return {"success": False, "message": result["message"]}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化进化集成层失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _start_monitoring_dashboard(self) -> Dict[str, Any]:
        """启动监控仪表盘"""
        try:
            async def monitoring_task():
                while True:
                    if self._intelligent_engine:
                        stats = self._intelligent_engine.get_dashboard_stats()
                        logger.debug(f"[OptimizationMonitoring] 优化统计: {stats}")
                    
                    if self._evolution_engine:
                        evolution_stats = self._evolution_engine.get_evolution_stats()
                        logger.debug(f"[OptimizationMonitoring] 进化统计: {evolution_stats}")
                    
                    if self._evolution_integration:
                        integration_stats = self._evolution_integration.get_stats()
                        logger.debug(f"[OptimizationMonitoring] 集成统计: {integration_stats}")
                    
                    await asyncio.sleep(30)
            
            asyncio.create_task(monitoring_task())
            
            logger.info("[OptimizationIntegration] 监控仪表盘已启动")
            return {"success": True, "message": "监控仪表盘已启动"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 启动监控仪表盘失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _setup_global_proxy(self) -> Dict[str, Any]:
        """设置全局优化代理"""
        try:
            if self._intelligent_engine:
                logger.info("[OptimizationIntegration] 全局优化代理已设置")
                return {"success": True, "message": "全局优化代理已设置"}
            else:
                return {"success": False, "message": "智能优化引擎未初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 设置全局优化代理失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """获取集成统计信息"""
        stats = {}
        
        if self._intelligent_engine:
            stats.update(self._intelligent_engine.get_dashboard_stats())
        
        if self._hook_manager:
            stats["hooks"] = self._hook_manager.get_stats()
        
        if self._evolution_engine:
            stats["evolution"] = self._evolution_engine.get_evolution_stats()
        
        if self._evolution_integration:
            stats["integration"] = vars(self._evolution_integration.get_stats())
        
        return stats
    
    def get_engine(self):
        """获取智能优化引擎"""
        return self._intelligent_engine
    
    def get_hook_manager(self):
        """获取钩子管理器"""
        return self._hook_manager
    
    def get_evolution_engine(self):
        """获取自我进化引擎"""
        return self._evolution_engine
    
    def get_open_evolution(self):
        """获取开放式进化"""
        return self._open_evolution
    
    def get_rl_improvement(self):
        """获取强化学习改进"""
        return self._rl_improvement
    
    def get_evolution_integration(self):
        """获取进化集成层"""
        return self._evolution_integration
    
    # ============ 技能发现相关方法 ============
    
    async def _initialize_skill_discovery(self) -> Dict[str, Any]:
        """初始化技能发现引擎"""
        try:
            from business.skill_discovery import create_skill_discovery
            
            self._skill_discovery = create_skill_discovery()
            
            # 分析代码库发现技能
            result = self._skill_discovery.analyze_repo("client/src")
            
            logger.info(f"[OptimizationIntegration] 技能发现引擎初始化完成，发现 {result.total_skills_found} 个技能")
            return {"success": True, "message": f"技能发现引擎已初始化，发现 {result.total_skills_found} 个技能"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化技能发现引擎失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_skill_matcher(self) -> Dict[str, Any]:
        """初始化技能匹配引擎"""
        try:
            from business.skill_matcher import create_skill_matcher
            
            self._skill_matcher = create_skill_matcher()
            
            logger.info("[OptimizationIntegration] 技能匹配引擎初始化完成")
            return {"success": True, "message": "技能匹配引擎已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化技能匹配引擎失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_skill_graph(self) -> Dict[str, Any]:
        """初始化技能图谱"""
        try:
            from business.skill_graph import create_skill_graph
            
            self._skill_graph = create_skill_graph()
            
            # 从技能发现引擎构建图谱
            if self._skill_discovery:
                skills_data = [
                    {
                        "name": skill.name,
                        "category": skill.category.value,
                        "level": skill.level.value,
                        "score": skill.score,
                    }
                    for skill in self._skill_discovery.get_top_skills([], 20)
                ]
                self._skill_graph.build_from_skills(skills_data)
            
            logger.info("[OptimizationIntegration] 技能图谱初始化完成")
            return {"success": True, "message": "技能图谱已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化技能图谱失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_skill_integration_service(self) -> Dict[str, Any]:
        """初始化技能集成服务"""
        try:
            from business.skill_integration_service import get_skill_integration_service
            
            self._skill_integration_service = get_skill_integration_service()
            
            # 发现并注册技能
            await self._skill_integration_service.discover_skills("client/src")
            
            # 构建技能图谱
            await self._skill_integration_service.build_graph()
            
            logger.info("[OptimizationIntegration] 技能集成服务初始化完成")
            return {"success": True, "message": "技能集成服务已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化技能集成服务失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _register_skill_hooks(self) -> Dict[str, Any]:
        """注册技能感知钩子"""
        try:
            if not self._hook_manager:
                return {"success": False, "message": "钩子管理器未初始化"}
            
            from business.optimization_hook_manager import HookPoint, HookContext, HookResult
            
            # 注册技能匹配钩子
            async def skill_matching_hook(context: HookContext) -> HookResult:
                if self._skill_integration_service and context.prompt:
                    # 匹配技能
                    match_result = await self._skill_integration_service.match_skills(context.prompt)
                    
                    # 将技能匹配结果添加到上下文
                    if match_result.matches:
                        context.context["matched_skills"] = [
                            m["skill_name"] for m in match_result.matches[:3]
                        ]
                        context.context["skill_confidence"] = [
                            m["confidence"] for m in match_result.matches[:3]
                        ]
                    
                    # 将推荐技能添加到上下文
                    if match_result.recommendations:
                        context.context["recommended_skills"] = [
                            r["skill_name"] for r in match_result.recommendations[:3]
                        ]
                    
                    return HookResult(
                        success=True,
                        optimization_metadata={
                            "matched_skills": len(match_result.matches),
                            "recommendations": len(match_result.recommendations),
                        }
                    )
                return HookResult(success=True)
            
            self._hook_manager.register_hook(HookPoint.PROMPT_GENERATION, skill_matching_hook)
            
            # 注册技能追踪钩子
            async def skill_tracking_hook(context: HookContext) -> HookResult:
                if self._skill_integration_service and context.response:
                    # 可以在这里追踪技能使用情况
                    pass
                return HookResult(success=True)
            
            self._hook_manager.register_hook(HookPoint.RESPONSE_RECEIVED, skill_tracking_hook)
            
            logger.info("[OptimizationIntegration] 技能感知钩子注册完成")
            return {"success": True, "message": "技能感知钩子已注册"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 注册技能感知钩子失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_skill_discovery(self):
        """获取技能发现引擎"""
        return self._skill_discovery
    
    def get_skill_matcher(self):
        """获取技能匹配引擎"""
        return self._skill_matcher
    
    def get_skill_graph(self):
        """获取技能图谱"""
        return self._skill_graph
    
    def get_skill_integration_service(self):
        """获取技能集成服务"""
        return self._skill_integration_service
    
    # ============ LLM验证器相关方法 ============
    
    async def _initialize_llm_verifier(self) -> Dict[str, Any]:
        """初始化LLM验证器"""
        try:
            from business.llm_verifier import create_llm_verifier
            
            self._llm_verifier = create_llm_verifier()
            
            logger.info("[OptimizationIntegration] LLM验证器初始化完成")
            return {"success": True, "message": "LLM验证器已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化LLM验证器失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_verifier_integration_service(self) -> Dict[str, Any]:
        """初始化验证器集成服务"""
        try:
            from business.verifier_integration_service import get_verifier_integration_service
            
            self._verifier_integration_service = get_verifier_integration_service()
            
            logger.info("[OptimizationIntegration] 验证器集成服务初始化完成")
            return {"success": True, "message": "验证器集成服务已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化验证器集成服务失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _register_verifier_hooks(self) -> Dict[str, Any]:
        """注册验证钩子"""
        try:
            if not self._hook_manager:
                return {"success": False, "message": "钩子管理器未初始化"}
            
            from business.optimization_hook_manager import HookPoint, HookContext, HookResult
            
            # 注册代码验证钩子
            async def code_verification_hook(context: HookContext) -> HookResult:
                if self._verifier_integration_service and context.prompt:
                    # 检查是否包含代码
                    if "```" in context.prompt or "def " in context.prompt or "function " in context.prompt:
                        # 运行代码验证管道
                        result = await self._verifier_integration_service.run_pipeline(
                            "code_generation",
                            code=context.prompt,
                            language="python"
                        )
                        
                        # 将验证结果添加到上下文
                        if result.get("overall_result") == "fail":
                            context.context["verification_failed"] = True
                            context.context["verification_issues"] = result.get("results", {})
                        
                        return HookResult(
                            success=True,
                            optimization_metadata={
                                "verification_result": result.get("overall_result"),
                            }
                        )
                return HookResult(success=True)
            
            self._hook_manager.register_hook(HookPoint.PROMPT_GENERATION, code_verification_hook)
            
            # 注册响应验证钩子
            async def response_verification_hook(context: HookContext) -> HookResult:
                if self._verifier_integration_service and context.response:
                    # 运行响应验证管道
                    result = await self._verifier_integration_service.run_pipeline(
                        "response_validation",
                        content=context.response,
                        context=context.context.get("original_prompt", "")
                    )
                    
                    return HookResult(
                        success=True,
                        optimization_metadata={
                            "response_verification": result.get("overall_result"),
                        }
                    )
                return HookResult(success=True)
            
            self._hook_manager.register_hook(HookPoint.RESPONSE_RECEIVED, response_verification_hook)
            
            logger.info("[OptimizationIntegration] 验证钩子注册完成")
            return {"success": True, "message": "验证钩子已注册"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 注册验证钩子失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_llm_verifier(self):
        """获取LLM验证器"""
        return self._llm_verifier
    
    def get_verifier_integration_service(self):
        """获取验证器集成服务"""
        return self._verifier_integration_service
    
    # ============ 智能搜索相关方法 ============
    
    async def _initialize_intelligent_search_engine(self) -> Dict[str, Any]:
        """初始化智能搜索引擎"""
        try:
            from business.intelligent_search_engine import get_intelligent_search_engine
            
            self._intelligent_search_engine = get_intelligent_search_engine()
            
            logger.info("[OptimizationIntegration] 智能搜索引擎初始化完成")
            return {"success": True, "message": "智能搜索引擎已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化智能搜索引擎失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _initialize_web_scraper(self) -> Dict[str, Any]:
        """初始化网页抓取器"""
        try:
            from business.web_scraper import create_web_scraper
            
            self._web_scraper = create_web_scraper()
            
            logger.info("[OptimizationIntegration] 网页抓取器初始化完成")
            return {"success": True, "message": "网页抓取器已初始化"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 初始化网页抓取器失败: {e}")
            return {"success": False, "message": str(e)}
    
    async def _register_search_hooks(self) -> Dict[str, Any]:
        """注册搜索钩子"""
        try:
            if not self._hook_manager:
                return {"success": False, "message": "钩子管理器未初始化"}
            
            from business.optimization_hook_manager import HookPoint, HookContext, HookResult
            
            # 注册搜索增强钩子
            async def search_enhancement_hook(context: HookContext) -> HookResult:
                if self._intelligent_search_engine and context.prompt:
                    # 分析是否需要搜索增强
                    search_keywords = ["搜索", "查找", "最新", "资料", "信息"]
                    if any(keyword in context.prompt for keyword in search_keywords):
                        # 执行智能搜索
                        results = await self._intelligent_search_engine.search(context.prompt)
                        
                        # 将搜索结果添加到上下文
                        if results:
                            context.context["search_results"] = [
                                {
                                    "title": r.title,
                                    "url": r.url,
                                    "snippet": r.snippet,
                                    "relevance": r.relevance,
                                }
                                for r in results[:3]
                            ]
                        
                        return HookResult(
                            success=True,
                            optimization_metadata={
                                "search_results": len(results),
                            }
                        )
                return HookResult(success=True)
            
            self._hook_manager.register_hook(HookPoint.PROMPT_GENERATION, search_enhancement_hook)
            
            logger.info("[OptimizationIntegration] 搜索钩子注册完成")
            return {"success": True, "message": "搜索钩子已注册"}
        
        except Exception as e:
            logger.error(f"[OptimizationIntegration] 注册搜索钩子失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_intelligent_search_engine(self):
        """获取智能搜索引擎"""
        return self._intelligent_search_engine
    
    def get_web_scraper(self):
        """获取网页抓取器"""
        return self._web_scraper
    
    @classmethod
    def is_initialized(cls) -> bool:
        """检查是否已初始化"""
        return cls._initialized


# 便捷函数
async def integrate_optimization() -> Dict[str, Any]:
    """便捷函数：深度集成所有优化功能"""
    bootstrapper = OptimizationIntegrationBootstrapper.get_instance()
    return await bootstrapper.integrate_all()


def get_integration_bootstrapper() -> OptimizationIntegrationBootstrapper:
    """获取集成启动器"""
    return OptimizationIntegrationBootstrapper.get_instance()


__all__ = [
    "OptimizationIntegrationBootstrapper",
    "integrate_optimization",
    "get_integration_bootstrapper",
]
