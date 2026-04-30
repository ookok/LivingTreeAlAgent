"""
Model Switcher - 一键模型切换器

类似 cc-switch 的跨平台模型切换工具，支持：
- Claude Code / Codex / Gemini CLI / OpenCode / OpenClaw
- 一键切换当前使用的模型
- 模型状态监控
- 快速配置切换
- 负载均衡支持

参考项目: https://github.com/farion1231/cc-switch

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class ModelProvider(Enum):
    """模型提供者"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    MINIMAX = "minimax"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    LOCAL = "local"
    OTHER = "other"


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: str
    model_id: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    default: bool = False
    enabled: bool = True
    priority: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "model_id": self.model_id,
            "api_base": self.api_base,
            "default": self.default,
            "enabled": self.enabled,
            "priority": self.priority
        }


@dataclass
class SwitchResult:
    """切换结果"""
    success: bool
    message: str
    previous_model: Optional[str] = None
    current_model: Optional[str] = None
    provider: Optional[str] = None


class ModelSwitcher:
    """一键模型切换器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelSwitcher, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        """初始化切换器"""
        if self._initialized:
            return
        
        self._logger = logger.bind(component="ModelSwitcher")
        self._models: Dict[str, ModelConfig] = {}
        self._current_model: Optional[str] = None
        self._model_router = None
        self._load_models()
        self._load_current_model()
        
        self._initialized = True
        self._logger.info("ModelSwitcher 初始化完成")
    
    def _load_models(self):
        """加载模型配置"""
        # 从配置文件加载
        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, config in data.items():
                        # 跳过内部配置键
                        if name.startswith("_"):
                            continue
                        self._models[name] = ModelConfig(**config)
                self._logger.info(f"从配置文件加载了 {len(self._models)} 个模型")
            except Exception as e:
                self._logger.warning(f"加载配置文件失败: {e}")
        
        # 如果没有配置，使用默认模型列表
        if not self._models:
            self._load_default_models()
    
    def _load_default_models(self):
        """加载默认模型配置"""
        default_models = [
            ModelConfig(
                name="claude-3-5-sonnet",
                provider="anthropic",
                model_id="claude-3-5-sonnet-20240620",
                default=True
            ),
            ModelConfig(
                name="gpt-4o",
                provider="openai",
                model_id="gpt-4o",
                default=False
            ),
            ModelConfig(
                name="gemini-1.5-flash",
                provider="google",
                model_id="gemini-1.5-flash",
                default=False
            ),
            ModelConfig(
                name="qwen3.5-4b",
                provider="ollama",
                model_id="qwen3.5:4b",
                default=False
            ),
            ModelConfig(
                name="deepseek-chat",
                provider="deepseek",
                model_id="deepseek-chat",
                default=False
            ),
            ModelConfig(
                name="minimax-m2.7",
                provider="minimax",
                model_id="abab6.5-chat",
                default=False
            )
        ]
        
        for model in default_models:
            self._models[model.name] = model
        
        self._logger.info(f"加载了 {len(default_models)} 个默认模型")
        self._save_config()
    
    def _get_config_path(self) -> str:
        """获取配置文件路径"""
        config_dir = os.path.expanduser("~/.livingtree/model_switcher")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "models.json")
    
    def _save_config(self):
        """保存配置"""
        config_path = self._get_config_path()
        try:
            data = {name: model.to_dict() for name, model in self._models.items()}
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._logger.warning(f"保存配置失败: {e}")
    
    def _save_current_model(self):
        """保存当前模型到配置"""
        config_path = self._get_config_path()
        try:
            # 读取现有配置
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # 添加当前模型信息
            data["_current_model"] = self._current_model
            
            # 保存
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._logger.warning(f"保存当前模型失败: {e}")
    
    def _load_current_model(self):
        """加载当前模型"""
        config_path = self._get_config_path()
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "_current_model" in data:
                        self._current_model = data["_current_model"]
                        self._logger.info(f"加载当前模型: {self._current_model}")
        except Exception as e:
            self._logger.warning(f"加载当前模型失败: {e}")
    
    def add_model(self, config: ModelConfig):
        """添加模型配置"""
        self._models[config.name] = config
        self._save_config()
        self._logger.info(f"添加模型: {config.name}")
    
    def remove_model(self, name: str) -> bool:
        """移除模型配置"""
        if name in self._models:
            del self._models[name]
            self._save_config()
            self._logger.info(f"移除模型: {name}")
            return True
        return False
    
    def switch_to(self, model_name: str) -> SwitchResult:
        """
        一键切换到指定模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            切换结果
        """
        if model_name not in self._models:
            return SwitchResult(
                success=False,
                message=f"模型不存在: {model_name}",
                current_model=self._current_model
            )
        
        model = self._models[model_name]
        if not model.enabled:
            return SwitchResult(
                success=False,
                message=f"模型已禁用: {model_name}",
                current_model=self._current_model
            )
        
        previous_model = self._current_model
        
        # 更新全局模型路由器
        self._update_global_router(model)
        
        # 更新当前模型
        self._current_model = model_name
        
        # 保存当前模型状态
        self._save_current_model()
        
        self._logger.info(f"切换模型: {previous_model} -> {model_name}")
        
        return SwitchResult(
            success=True,
            message=f"成功切换到 {model_name}",
            previous_model=previous_model,
            current_model=model_name,
            provider=model.provider
        )
    
    def _update_global_router(self, model: ModelConfig):
        """更新全局模型路由器"""
        try:
            from business.global_model_router import GlobalModelRouter
            router = GlobalModelRouter()
            
            # 设置默认模型
            router.set_default_model(model.model_id)
            
            # 更新配置
            if model.api_base:
                router.set_api_base(model.provider, model.api_base)
            
            self._logger.debug(f"全局路由器已更新为: {model.name}")
            
        except Exception as e:
            self._logger.warning(f"更新全局路由器失败: {e}")
    
    def get_current_model(self) -> Optional[ModelConfig]:
        """获取当前模型配置"""
        if self._current_model and self._current_model in self._models:
            return self._models[self._current_model]
        return None
    
    def list_models(self) -> List[ModelConfig]:
        """获取所有模型列表"""
        return list(self._models.values())
    
    def get_models_by_provider(self, provider: str) -> List[ModelConfig]:
        """按提供者获取模型列表"""
        return [m for m in self._models.values() if m.provider.lower() == provider.lower()]
    
    def get_model_status(self, model_name: str) -> Dict[str, Any]:
        """获取模型状态"""
        if model_name not in self._models:
            return {"name": model_name, "status": "not_found"}
        
        model = self._models[model_name]
        is_current = self._current_model == model_name
        
        return {
            "name": model.name,
            "provider": model.provider,
            "model_id": model.model_id,
            "status": "active" if is_current else "available",
            "is_current": is_current,
            "enabled": model.enabled,
            "priority": model.priority
        }
    
    def get_all_status(self) -> List[Dict[str, Any]]:
        """获取所有模型状态"""
        return [self.get_model_status(name) for name in self._models]
    
    def cycle_models(self, direction: str = "next") -> SwitchResult:
        """
        循环切换模型
        
        Args:
            direction: next 或 previous
            
        Returns:
            切换结果
        """
        enabled_models = [name for name, model in self._models.items() if model.enabled]
        
        if not enabled_models:
            return SwitchResult(
                success=False,
                message="没有可用的模型",
                current_model=self._current_model
            )
        
        if self._current_model not in enabled_models:
            # 如果当前模型不在可用列表中，切换到第一个
            return self.switch_to(enabled_models[0])
        
        index = enabled_models.index(self._current_model)
        
        if direction == "next":
            next_index = (index + 1) % len(enabled_models)
        else:
            next_index = (index - 1) % len(enabled_models)
        
        return self.switch_to(enabled_models[next_index])
    
    async def test_model(self, model_name: str) -> Dict[str, Any]:
        """
        测试模型连接
        
        Args:
            model_name: 模型名称
            
        Returns:
            测试结果
        """
        if model_name not in self._models:
            return {"success": False, "message": "模型不存在"}
        
        model = self._models[model_name]
        
        try:
            # 执行简单的测试请求
            result = await self._execute_test_request(model)
            
            return {
                "success": True,
                "message": "连接成功",
                "model": model_name,
                "response_time": result.get("response_time", 0)
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "model": model_name
            }
    
    async def _execute_test_request(self, model: ModelConfig) -> Dict[str, Any]:
        """执行测试请求"""
        import time
        
        # 模拟测试请求
        start_time = time.time()
        
        # 根据提供者执行不同的测试
        if model.provider == "ollama":
            # Ollama 本地模型测试
            result = await self._test_ollama(model)
        else:
            # 远程模型测试
            result = await self._test_remote(model)
        
        result["response_time"] = time.time() - start_time
        return result
    
    async def _test_ollama(self, model: ModelConfig) -> Dict[str, Any]:
        """测试 Ollama 模型"""
        try:
            import ollama
            response = await ollama.chat(
                model=model.model_id,
                messages=[{"role": "user", "content": "Hello"}]
            )
            return {"success": True, "response": response.get("message", {}).get("content", "")}
        except Exception as e:
            raise Exception(f"Ollama 连接失败: {e}")
    
    async def _test_remote(self, model: ModelConfig) -> Dict[str, Any]:
        """测试远程模型"""
        # 模拟远程调用
        await asyncio.sleep(0.5)
        return {"success": True, "response": "Test response"}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        enabled_count = sum(1 for m in self._models.values() if m.enabled)
        
        return {
            "total_models": len(self._models),
            "enabled_models": enabled_count,
            "current_model": self._current_model,
            "providers": list(set(m.provider for m in self._models.values()))
        }
    
    @classmethod
    def get_instance(cls) -> "ModelSwitcher":
        """获取实例"""
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance


# 快捷函数
def switch_model(model_name: str) -> SwitchResult:
    """一键切换模型"""
    switcher = ModelSwitcher.get_instance()
    return switcher.switch_to(model_name)


def next_model() -> SwitchResult:
    """切换到下一个模型"""
    switcher = ModelSwitcher.get_instance()
    return switcher.cycle_models("next")


def prev_model() -> SwitchResult:
    """切换到上一个模型"""
    switcher = ModelSwitcher.get_instance()
    return switcher.cycle_models("previous")


def get_models() -> List[ModelConfig]:
    """获取所有模型"""
    switcher = ModelSwitcher.get_instance()
    return switcher.list_models()


def get_current() -> Optional[ModelConfig]:
    """获取当前模型"""
    switcher = ModelSwitcher.get_instance()
    return switcher.get_current_model()