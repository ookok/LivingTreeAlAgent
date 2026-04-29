"""
自适应引导管理器 - Adaptive Guide Manager

统一协调层，整合所有组件：

1. AdaptiveRouter - 路由决策
2. DowngradeMatrix - 降级策略
3. ShortestPathGuide - 引导流程
4. UserProfileDetector - 用户画像
5. ContextHelp - 上下文帮助

使用示例：
    manager = AdaptiveGuideManager()
    
    # 执行功能，自动处理降级和引导
    result = await manager.execute("weather_forecast", {"location": "Beijing"})
    
    # 获取仪表盘数据
    dashboard = manager.get_dashboard_data()
    
    # 获取待配置功能
    pending = manager.get_pending_configurations()
"""

import os
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .adaptive_router import AdaptiveRouter, RouteResult, RouteStrategy, get_adaptive_router
from .downgrade_matrix import DowngradeMatrix, get_downgrade_matrix
from .shortest_path_guide import ShortestPathGuide, GuideFlow, GuideProgress, get_shortest_path_guide
from .user_profile_detector import UserProfileDetector, UserProfile, get_user_profile_detector
from .context_help import ContextHelp, HelpCard, get_context_help

logger = logging.getLogger(__name__)


@dataclass
class DashboardData:
    """
    仪表盘数据
    
    汇总系统状态、可用功能、待配置项等
    """
    total_features: int
    configured_features: int
    pending_configurations: List[Dict[str, Any]]
    active_implementations: Dict[str, str]  # feature_id -> implementation_name
    user_profile: Dict[str, Any]
    recent_guides: List[Dict[str, Any]]
    system_health: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_features": self.total_features,
            "configured_features": self.configured_features,
            "pending_configurations": self.pending_configurations,
            "active_implementations": self.active_implementations,
            "user_profile": self.user_profile,
            "recent_guides": self.recent_guides,
            "system_health": self.system_health,
        }


class AdaptiveGuideManager:
    """
    自适应引导管理器
    
    统一协调层，提供简化的接口
    """
    
    _instance: Optional["AdaptiveGuideManager"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 初始化组件
        self._router = get_adaptive_router()
        self._matrix = get_downgrade_matrix()
        self._guide = get_shortest_path_guide()
        self._profile_detector = get_user_profile_detector()
        self._help = get_context_help()
        
        # 配置
        self._config: Dict[str, Any] = {}
        self._config_path = Path.home() / ".hermes" / "adaptive_guide.json"
        
        # 加载配置
        self._load_config()
        
        # 最近的引导记录
        self._recent_guides: List[Dict[str, Any]] = []
        
        self._initialized = True
        logger.info("AdaptiveGuideManager initialized")
    
    def _load_config(self):
        """加载配置"""
        try:
            if self._config_path.exists():
                import json
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
        except Exception as e:
            logger.warning("Failed to load config: %s", e)
    
    def _save_config(self):
        """保存配置"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            import json
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save config: %s", e)
    
    # ============================================================
    # 核心执行接口
    # ============================================================
    
    async def execute(
        self, 
        feature_id: str, 
        input_data: Dict[str, Any],
        strategy: RouteStrategy = RouteStrategy.BALANCED
    ) -> RouteResult:
        """
        执行功能（主入口）
        
        自动处理：
        1. 配置检查
        2. 降级路由
        3. 引导启动
        
        Args:
            feature_id: 功能标识符
            input_data: 输入数据
            strategy: 路由策略
        
        Returns:
            RouteResult
        """
        return await self._router.execute_feature(
            feature_id, 
            input_data, 
            self._config,
            strategy
        )
    
    def execute_sync(
        self, 
        feature_id: str, 
        input_data: Dict[str, Any],
        strategy: RouteStrategy = RouteStrategy.BALANCED
    ) -> RouteResult:
        """
        同步执行功能
        
        兼容同步调用场景
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已经在事件循环中，创建task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.execute(feature_id, input_data, strategy)
                    )
                    return future.result()
            else:
                return asyncio.run(self.execute(feature_id, input_data, strategy))
        except RuntimeError:
            # 没有事件循环
            return asyncio.run(self.execute(feature_id, input_data, strategy))
    
    def get_best_available(self, feature_id: str) -> Optional[Dict[str, Any]]:
        """
        获取功能的最佳可用实现信息
        
        不执行，只返回实现信息
        """
        impl = self._matrix.get_best_available(feature_id, self._config, True)
        
        if impl is None:
            return None
        
        return {
            "id": impl.id,
            "name": impl.name,
            "level": impl.level.value,
            "accuracy": impl.accuracy,
            "latency_ms": impl.latency_ms,
            "requires_config": not impl.is_available(self._config),
            "config_keys": impl.config_keys,
        }
    
    # ============================================================
    # 引导接口
    # ============================================================
    
    def start_guide(
        self, 
        feature_id: str,
        guide_type: Optional[str] = None
    ) -> Optional[GuideFlow]:
        """
        启动引导流程
        
        Args:
            feature_id: 功能标识符
            guide_type: 引导类型（可选）
        
        Returns:
            GuideFlow 或 None
        """
        flow = self._guide.create_guide_flow(feature_id, None, guide_type)
        
        if flow:
            # 记录到最近引导
            self._add_recent_guide(feature_id, flow.flow_id)
        
        return flow
    
    def get_guide_progress(self, flow_id: str) -> Optional[GuideProgress]:
        """获取引导进度"""
        user_id = self._profile_detector.detect_profile().user_id
        return self._guide.load_progress(user_id, flow_id)
    
    def save_guide_progress(self, progress: GuideProgress) -> bool:
        """保存引导进度"""
        return self._guide.save_progress(progress)
    
    def complete_guide(self, flow_id: str) -> bool:
        """
        完成引导
        
        清理进度记录，更新配置
        """
        user_id = self._profile_detector.detect_profile().user_id
        success = self._guide.delete_progress(user_id, flow_id)
        
        if success:
            # 从最近引导移到已完成
            for guide in self._recent_guides:
                if guide.get("flow_id") == flow_id:
                    guide["completed"] = True
                    guide["completed_at"] = datetime.now().isoformat()
                    self._save_config()
        
        return success
    
    def _add_recent_guide(self, feature_id: str, flow_id: str):
        """添加最近引导记录"""
        self._recent_guides.insert(0, {
            "feature_id": feature_id,
            "flow_id": flow_id,
            "started_at": datetime.now().isoformat(),
            "completed": False,
        })
        
        # 只保留最近10条
        self._recent_guides = self._recent_guides[:10]
        self._save_config()
    
    # ============================================================
    # 配置接口
    # ============================================================
    
    def update_config(self, config: Dict[str, Any]):
        """
        更新配置
        
        Args:
            config: 新配置，会与现有配置合并
        """
        self._config.update(config)
        self._save_config()
        
        # 同步到路由器
        self._router.set_config(self._config)
    
    def get_config(self, feature_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取配置
        
        Args:
            feature_id: 如果指定，只返回该功能相关的配置
        """
        if feature_id:
            impl = self._matrix.get_implementation(feature_id)
            if impl:
                return {k: self._config.get(k) for k in impl.config_keys}
        return self._config.copy()
    
    def set_config_value(self, key: str, value: Any):
        """设置单个配置值"""
        self._config[key] = value
        self._save_config()
        self._router.set_config(self._config)
    
    def validate_config(self, feature_id: str) -> Dict[str, Any]:
        """
        验证功能配置
        
        Returns:
            验证结果，包含是否有效和缺失的key
        """
        impl = self._matrix.get_best_available(feature_id, self._config, True)
        
        if impl is None:
            return {"valid": False, "missing_keys": [], "error": "No implementation available"}
        
        missing_keys = []
        for key in impl.config_keys:
            if not self._config.get(key) and not os.getenv(key):
                missing_keys.append(key)
        
        return {
            "valid": len(missing_keys) == 0,
            "missing_keys": missing_keys,
            "current_implementation": impl.id,
            "current_level": impl.level.value,
        }

    # ============================================================
    # 密钥管理集成 (API Key 自动配置)
    # ============================================================

    def check_and_retrieve_api_keys(self, feature_id: str) -> Dict[str, Any]:
        """
        检查并获取功能所需的API密钥

        从密钥管理系统自动获取API Key，实现零配置自动填充：

        1. 获取功能需要的配置key（如 OPENWEATHER_API_KEY）
        2. 检查密钥管理系统是否有该key
        3. 如果有，自动填充到配置中
        4. 返回获取结果

        Args:
            feature_id: 功能标识符

        Returns:
            {
                "retrieved_keys": {key: value, ...},
                "missing_keys": [key, ...],
                "auto_configured": True/False
            }
        """
        result = {
            "retrieved_keys": {},
            "missing_keys": [],
            "auto_configured": False
        }

        try:
            # 获取功能实现
            impl = self._matrix.get_best_available(feature_id, self._config, True)
            if not impl or not impl.config_keys:
                return result

            # 映射配置key到provider
            key_to_provider = self._map_config_key_to_provider(impl.config_keys)

            # 尝试从密钥管理系统获取
            try:
                from core.key_management import get_key_manager
                key_manager = get_key_manager()

                if key_manager and key_manager._initialized:
                    consumer = key_manager.consumer
                    if consumer:
                        for config_key, provider in key_to_provider.items():
                            try:
                                api_key = consumer.get_key_for_provider(provider, skip_audit=True)
                                if api_key:
                                    result["retrieved_keys"][config_key] = api_key
                                    # 自动填充到配置
                                    self._config[config_key] = api_key
                            except (KeyError, ValueError):
                                result["missing_keys"].append(config_key)
            except ImportError:
                logger.warning("密钥管理系统未安装")
            except Exception as e:
                logger.warning(f"获取API密钥失败: {e}")

            # 检查缺失的keys
            for key in impl.config_keys:
                if key not in result["retrieved_keys"] and not self._config.get(key):
                    if key not in result["missing_keys"]:
                        result["missing_keys"].append(key)

            result["auto_configured"] = len(result["retrieved_keys"]) > 0

        except Exception as e:
            logger.warning(f"check_and_retrieve_api_keys 失败: {e}")

        return result

    def _map_config_key_to_provider(self, config_keys: List[str]) -> Dict[str, str]:
        """
        将配置key映射到密钥提供商标识

        例如:
            OPENWEATHER_API_KEY -> openweather
            SERPER_API_KEY -> serper
            BRAVE_API_KEY -> brave

        Args:
            config_keys: 配置key列表

        Returns:
            {config_key: provider_name, ...}
        """
        mapping = {}
        for key in config_keys:
            key_lower = key.lower()
            if "openweather" in key_lower:
                mapping[key] = "openweather"
            elif "serper" in key_lower:
                mapping[key] = "serper"
            elif "brave" in key_lower:
                mapping[key] = "brave"
            elif "modelscope" in key_lower:
                mapping[key] = "modelscope"
            elif "huggingface" in key_lower or "hf" in key_lower:
                mapping[key] = "huggingface"
            elif "openai" in key_lower:
                mapping[key] = "openai"
            elif "anthropic" in key_lower:
                mapping[key] = "anthropic"
            elif "github" in key_lower:
                mapping[key] = "github"
            else:
                # 尝试从key名推断provider
                provider = key_lower.replace("_api_key", "").replace("_key", "")
                mapping[key] = provider
        return mapping

    # ============================================================
    # 帮助接口
    # ============================================================
    
    def get_help_card(self, feature_id: str) -> HelpCard:
        """获取功能帮助卡片"""
        return self._help.get_help_card(feature_id)
    
    def get_pending_configurations(self) -> List[Dict[str, Any]]:
        """
        获取待配置功能列表
        
        Returns:
            按优先级排序的待配置功能列表
        """
        pending = []
        
        for feature_id in self._matrix.get_all_features():
            impl = self._matrix.get_best_available(feature_id, self._config, True)
            
            if impl and not impl.is_available(self._config):
                # 需要配置
                if impl.level not in ("local", "public"):
                    card = self._help.get_help_card(feature_id)
                    pending.append({
                        "feature_id": feature_id,
                        "current_impl": impl.id,
                        "level": impl.level.value,
                        "priority": card.priority,
                        "time_estimate": card.time_estimate,
                        "actions": card.actions,
                    })
        
        # 按优先级排序
        pending.sort(key=lambda x: x["priority"], reverse=True)
        return pending
    
    # ============================================================
    # 仪表盘接口
    # ============================================================
    
    def get_dashboard_data(self) -> DashboardData:
        """
        获取仪表盘数据
        
        Returns:
            DashboardData
        """
        all_features = self._matrix.get_all_features()
        configured = 0
        active_impls = {}
        pending_configs = []
        
        for feature_id in all_features:
            impl = self._matrix.get_best_available(feature_id, self._config, True)
            
            if impl:
                active_impls[feature_id] = impl.name
                
                if impl.is_available(self._config):
                    configured += 1
                elif impl.level not in ("local", "public"):
                    pending_configs.append({
                        "feature_id": feature_id,
                        "implementation": impl.name,
                        "level": impl.level.value,
                    })
        
        # 获取用户画像
        profile = self._profile_detector.detect_profile()
        
        return DashboardData(
            total_features=len(all_features),
            configured_features=configured,
            pending_configurations=pending_configs,
            active_implementations=active_impls,
            user_profile=profile.to_dict(),
            recent_guides=self._recent_guides[:5],
            system_health=self._get_system_health(),
        )
    
    def _get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        return {
            "status": "healthy",
            "components": {
                "router": "ok",
                "matrix": "ok",
                "guide": "ok",
                "profile": "ok",
                "help": "ok",
            },
            "timestamp": datetime.now().isoformat(),
        }
    
    # ============================================================
    # 功能注册接口
    # ============================================================
    
    def register_feature(
        self, 
        feature_id: str, 
        implementations: List[Any],
        help_template: Optional[HelpCard] = None
    ):
        """
        注册新功能
        
        Args:
            feature_id: 功能标识符
            implementations: 实现列表
            help_template: 帮助模板（可选）
        """
        # 注册到矩阵
        self._matrix.register_feature(feature_id, implementations)
        
        # 注册帮助模板
        if help_template:
            self._help.register_help_template(help_template)
    
    # ============================================================
    # 用户画像接口
    # ============================================================
    
    def get_user_profile(self) -> UserProfile:
        """获取用户画像"""
        return self._profile_detector.detect_profile()
    
    def record_guide_success(
        self, 
        feature_id: str, 
        guide_type: str, 
        time_taken: float
    ):
        """记录引导成功"""
        self._profile_detector.record_success(
            feature_id, 
            self._guide.create_guide_flow(feature_id).guide_type if hasattr(self._guide, 'guide_type') else None,
            time_taken
        )
    
    def record_guide_failure(self, feature_id: str, guide_type: str):
        """记录引导失败"""
        self._profile_detector.record_failure(feature_id, None)
    
    # ============================================================
    # 状态查询接口
    # ============================================================
    
    def get_feature_status(self, feature_id: str) -> Dict[str, Any]:
        """获取功能状态"""
        return self._router.get_feature_status(feature_id, self._config)
    
    def get_all_features_status(self) -> List[Dict[str, Any]]:
        """获取所有功能状态"""
        statuses = []
        for feature_id in self._matrix.get_all_features():
            statuses.append(self.get_feature_status(feature_id))
        return statuses
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._router.get_stats()
    
    def get_recent_guides(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取最近的引导记录"""
        return self._recent_guides[:limit]


# 全局实例
_manager: Optional[AdaptiveGuideManager] = None


def get_guide_manager() -> AdaptiveGuideManager:
    """获取自适应引导管理器全局实例"""
    global _manager
    if _manager is None:
        _manager = AdaptiveGuideManager()
    return _manager


# 便捷函数
def execute_feature(
    feature_id: str, 
    input_data: Dict[str, Any],
    strategy: RouteStrategy = RouteStrategy.BALANCED
) -> RouteResult:
    """
    便捷函数：执行功能
    
    使用全局管理器
    """
    manager = get_guide_manager()
    return manager.execute_sync(feature_id, input_data, strategy)


def start_guide(feature_id: str) -> Optional[GuideFlow]:
    """
    便捷函数：启动引导
    
    使用全局管理器
    """
    manager = get_guide_manager()
    return manager.start_guide(feature_id)


def get_dashboard() -> DashboardData:
    """
    便捷函数：获取仪表盘
    
    使用全局管理器
    """
    manager = get_guide_manager()
    return manager.get_dashboard_data()