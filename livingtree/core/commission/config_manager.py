# -*- coding: utf-8 -*-
"""
统一佣金系统 - 统一配置管理器
Unified Commission System - Unified Config Manager

负责加载、验证、管理所有配置，支持热重载
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
import yaml

from .models import (
    ModuleType,
    ModuleConfig,
    PaymentConfig,
    SettlementConfig,
    GlobalConfig,
    PaymentProvider,
    TestResult
)

logger = logging.getLogger(__name__)


class ConfigObserver:
    """配置变更观察者接口"""
    def on_config_changed(self, section: str, key: str, old_value: Any, new_value: Any):
        """配置变更回调"""
        pass


class UnifiedConfigManager:
    """
    统一配置管理器
    职责：加载、验证、管理所有佣金系统配置
    """
    
    _instance = None
    _config: Dict[str, Any] = {}
    _config_path: str = ""
    _observers: List[ConfigObserver] = []
    _validator: Optional['ConfigValidator'] = None
    
    def __new__(cls, config_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: str = None):
        if self._initialized:
            return
        
        self._config_path = config_path or self._get_default_config_path()
        self._validator = ConfigValidator(self)
        self._initialized = True
        self._observers = []
        
        # 初始化默认配置
        self._init_default_config()
    
    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        from pathlib import Path
        config_dir = Path.home() / ".hermes-desktop" / "commission"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "commission_config.yaml")
    
    def _init_default_config(self):
        """初始化默认配置"""
        self._config = {
            "version": "1.0.0",
            "last_modified": "",
            "environment": "production",
            "global": {
                "app_name": "智能创作平台",
                "app_version": "1.0.0",
                "base_currency": "CNY",
                "commission_rate": 0.0003,
                "min_commission": 0.01,
                "max_order_amount": 50000.0,
                "auto_refund_timeout": 1800,
                "enable_debug_log": False,
                "log_level": "INFO"
            },
            "modules": {
                "deep_search": {
                    "enabled": True,
                    "display_name": "深度搜索",
                    "min_amount": 1.0,
                    "max_amount": 1000.0,
                    "default_amounts": [5, 10, 20, 50, 100],
                    "commission_rate": 0.0003,
                    "description": "高级搜索功能，提供精准结果",
                    "features": ["语义搜索", "多源聚合", "智能排序", "历史记录"]
                },
                "creation": {
                    "enabled": True,
                    "display_name": "智能创作",
                    "min_amount": 1.0,
                    "max_amount": 5000.0,
                    "default_amounts": [10, 20, 50, 100, 200],
                    "commission_rate": 0.0003,
                    "description": "AI辅助创作，提升创作效率",
                    "features": ["内容生成", "风格模仿", "结构优化", "语法检查"]
                },
                "stock_futures": {
                    "enabled": True,
                    "display_name": "股票期货分析",
                    "min_amount": 1.0,
                    "max_amount": 10000.0,
                    "default_amounts": [20, 50, 100, 200, 500],
                    "commission_rate": 0.0003,
                    "require_verification": True,
                    "risk_warning": "投资有风险，入市需谨慎",
                    "features": ["实时行情", "技术分析", "策略回测", "风险预警"]
                },
                "game": {
                    "enabled": True,
                    "display_name": "游戏娱乐",
                    "min_amount": 1.0,
                    "max_amount": 2000.0,
                    "default_amounts": [1, 5, 10, 20, 50],
                    "commission_rate": 0.0003,
                    "game_categories": ["休闲游戏", "竞技游戏", "策略游戏"],
                    "features": ["游戏道具", "虚拟货币", "会员特权", "排行榜奖励"]
                },
                "ide": {
                    "enabled": True,
                    "display_name": "智能IDE",
                    "min_amount": 1.0,
                    "max_amount": 3000.0,
                    "default_amounts": [10, 20, 50, 100, 200],
                    "commission_rate": 0.0003,
                    "description": "代码开发工具，AI编程助手",
                    "features": ["代码补全", "智能调试", "代码重构", "项目管理"]
                }
            },
            "payment": {
                "enabled": True,
                "default_provider": "wechat",
                "wechat": {
                    "enabled": False,
                    "app_id": "",
                    "mch_id": "",
                    "api_key": "",
                    "sandbox": True,
                    "test_amount": 0.01
                },
                "alipay": {
                    "enabled": False,
                    "app_id": "",
                    "app_private_key": "",
                    "alipay_public_key": "",
                    "sandbox": True
                },
                "common": {
                    "order_prefix": "COMM",
                    "order_timeout": 1800,
                    "qr_code_size": 300,
                    "enable_auto_query": True,
                    "query_interval": 5,
                    "max_query_times": 60
                }
            },
            "settlement": {
                "developer": {
                    "account_id": "developer_001",
                    "account_name": "软件开发作者",
                    "commission_rate": 0.0003,
                    "auto_settlement": True,
                    "settlement_threshold": 100.0,
                    "settlement_cycle": "weekly",
                    "settlement_day": 1
                },
                "author": {
                    "auto_settlement": True,
                    "settlement_threshold": 10.0,
                    "settlement_cycle": "monthly",
                    "min_withdraw_amount": 1.0,
                    "max_withdraw_amount": 50000.0,
                    "withdraw_fee": 0.0,
                    "tax_rate": 0.0
                },
                "methods": [
                    {"id": "internal", "name": "内部账户", "enabled": True, "fee_rate": 0.0},
                    {"id": "bank", "name": "银行卡", "enabled": True, "fee_rate": 0.0},
                    {"id": "alipay", "name": "支付宝", "enabled": True, "fee_rate": 0.0},
                    {"id": "wechat", "name": "微信", "enabled": True, "fee_rate": 0.0}
                ]
            },
            "refund": {
                "auto_refund_timeout": 1800,
                "max_auto_refund_amount": 1000.0,
                "enable_partial_refund": True,
                "max_refund_times": 3,
                "reasons": [
                    {"code": "USER_CANCEL", "name": "用户取消", "auto_process": True},
                    {"code": "PAY_TIMEOUT", "name": "支付超时", "auto_process": True},
                    {"code": "SYSTEM_ERROR", "name": "系统错误", "auto_process": True},
                    {"code": "SERVICE_UNAVAILABLE", "name": "服务不可用", "auto_process": True},
                    {"code": "OTHER", "name": "其他原因", "auto_process": False}
                ]
            },
            "database": {
                "main": {
                    "type": "sqlite",
                    "name": "commission.db"
                }
            }
        }
    
    def load_config(self, config_path: str = None) -> bool:
        """
        加载配置文件
        支持格式：YAML、JSON
        """
        path = config_path or self._config_path
        
        try:
            if not os.path.exists(path):
                logger.info(f"配置文件不存在，使用默认配置: {path}")
                self.save_config(path)
                return True
            
            with open(path, 'r', encoding='utf-8') as f:
                if path.endswith('.json'):
                    self._config = json.load(f)
                else:
                    self._config = yaml.safe_load(f) or {}
            
            logger.info(f"成功加载配置文件: {path}")
            return True
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return False
    
    def save_config(self, config_path: str = None) -> bool:
        """保存配置到文件"""
        path = config_path or self._config_path
        
        try:
            # 确保目录存在
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            
            # 更新时间戳
            from datetime import datetime
            self._config["last_modified"] = datetime.now().isoformat()
            
            with open(path, 'w', encoding='utf-8') as f:
                if path.endswith('.json'):
                    json.dump(self._config, f, ensure_ascii=False, indent=2)
                else:
                    yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
            
            logger.info(f"配置已保存: {path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def get_module_config(self, module_name: str) -> ModuleConfig:
        """获取指定模块的配置"""
        module_type = ModuleType(module_name)
        module_data = self._config.get("modules", {}).get(module_name, {})
        return ModuleConfig.from_dict(module_type, module_data)
    
    def get_all_module_configs(self) -> Dict[str, ModuleConfig]:
        """获取所有模块配置"""
        configs = {}
        for module_type in ModuleType:
            configs[module_type.value] = self.get_module_config(module_type.value)
        return configs
    
    def get_payment_config(self, provider: str = None) -> Dict[str, Any]:
        """获取支付配置"""
        payment_config = self._config.get("payment", {})
        
        if provider:
            return payment_config.get(provider, {})
        
        return payment_config
    
    def get_settlement_config(self) -> SettlementConfig:
        """获取结算配置"""
        return SettlementConfig.from_dict(self._config.get("settlement", {}))
    
    def get_global_config(self) -> GlobalConfig:
        """获取全局配置"""
        return GlobalConfig.from_dict(self._config.get("global", {}))
    
    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """
        通过点分隔的路径获取配置值
        例如: "modules.deep_search.commission_rate"
        """
        keys = key_path.split(".")
        value = self._config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def update_config(self, section: str, key: str, value: Any) -> bool:
        """
        更新配置项
        """
        try:
            old_value = self.get_config_value(f"{section}.{key}")
            
            if section not in self._config:
                self._config[section] = {}
            
            self._config[section][key] = value
            
            # 通知观察者
            self._notify_observers(section, key, old_value, value)
            
            return True
            
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
    
    def set_section(self, section: str, data: Dict[str, Any]) -> bool:
        """
        设置整个配置区块
        """
        try:
            self._config[section] = data
            
            # 验证配置
            if self._validator:
                is_valid, errors = self._validator.validate_section(section)
                if not is_valid:
                    logger.warning(f"配置验证有误: {errors}")
            
            return True
            
        except Exception as e:
            logger.error(f"设置配置区块失败: {e}")
            return False
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """
        验证配置有效性
        返回：(是否有效, 错误列表)
        """
        return self._validator.validate_all()
    
    def reload_config(self) -> bool:
        """
        重新加载配置
        支持热重载
        """
        return self.load_config()
    
    def export_config(self, format: str = "yaml") -> str:
        """
        导出配置
        """
        try:
            if format == "json":
                return json.dumps(self._config, ensure_ascii=False, indent=2)
            else:
                return yaml.dump(self._config, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return ""
    
    def import_config(self, config_data: str, format: str = "yaml") -> bool:
        """
        导入配置
        """
        try:
            if format == "json":
                self._config = json.loads(config_data)
            else:
                self._config = yaml.safe_load(config_data) or {}
            
            # 验证配置
            is_valid, errors = self.validate_config()
            if not is_valid:
                logger.warning(f"导入的配置验证有误: {errors}")
            
            return True
            
        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False
    
    def register_observer(self, observer: ConfigObserver):
        """注册配置变更观察者"""
        if observer not in self._observers:
            self._observers.append(observer)
    
    def unregister_observer(self, observer: ConfigObserver):
        """取消注册观察者"""
        if observer in self._observers:
            self._observers.remove(observer)
    
    def _notify_observers(self, section: str, key: str, old_value: Any, new_value: Any):
        """通知观察者配置变更"""
        for observer in self._observers:
            try:
                observer.on_config_changed(section, key, old_value, new_value)
            except Exception as e:
                logger.error(f"通知观察者失败: {e}")
    
    def test_config(self, config_type: str) -> TestResult:
        """
        测试配置
        """
        result = TestResult(config_type)
        
        try:
            if config_type == "module":
                for module in ModuleType:
                    test_result = self._validator.test_module_config(module.value)
                    result.data[module.value] = test_result.to_dict()
                    if test_result.has_errors():
                        result.add_warning(f"{module.value}: {test_result.errors}")
                
                result.success = True
                
            elif config_type == "payment":
                payment_config = self._config.get("payment", {})
                
                # 检查支付是否启用
                if not payment_config.get("enabled", False):
                    result.add_warning("支付功能未启用")
                
                # 检查微信支付
                wechat_config = payment_config.get("wechat", {})
                if wechat_config.get("enabled", False):
                    if not wechat_config.get("app_id"):
                        result.add_error("微信支付未配置app_id")
                
                # 检查支付宝
                alipay_config = payment_config.get("alipay", {})
                if alipay_config.get("enabled", False):
                    if not alipay_config.get("app_id"):
                        result.add_error("支付宝未配置app_id")
                
                result.success = not result.has_errors()
                
            elif config_type == "settlement":
                settlement_config = self._config.get("settlement", {})
                
                developer = settlement_config.get("developer", {})
                if developer.get("commission_rate", 0) <= 0:
                    result.add_error("开发者佣金比例必须大于0")
                
                result.success = not result.has_errors()
                
            else:
                result.add_error(f"未知配置类型: {config_type}")
            
        except Exception as e:
            result.add_error(f"测试配置异常: {str(e)}")
        
        return result
    
    def reset_to_default(self) -> bool:
        """重置为默认配置"""
        self._init_default_config()
        return self.save_config()
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config.copy()
    
    def __repr__(self):
        return f"<UnifiedConfigManager: {self._config_path}>"


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self, config_manager: UnifiedConfigManager):
        self.config_manager = config_manager
    
    def validate_all(self) -> Tuple[bool, List[str]]:
        """验证所有配置"""
        errors = []
        
        # 验证全局配置
        global_valid, global_errors = self.validate_section("global")
        if not global_valid:
            errors.extend(global_errors)
        
        # 验证模块配置
        for module in ModuleType:
            module_valid, module_errors = self.validate_section(f"modules.{module.value}")
            if not module_valid:
                errors.extend(module_errors)
        
        # 验证支付配置
        payment_valid, payment_errors = self.validate_section("payment")
        if not payment_valid:
            errors.extend(payment_errors)
        
        # 验证结算配置
        settlement_valid, settlement_errors = self.validate_section("settlement")
        if not settlement_valid:
            errors.extend(settlement_errors)
        
        return len(errors) == 0, errors
    
    def validate_section(self, section: str) -> Tuple[bool, List[str]]:
        """验证指定配置区块"""
        errors = []
        
        if section.startswith("modules."):
            module_name = section.split(".")[1]
            return self.test_module_config(module_name).name, self.test_module_config(module_name).errors
        elif section == "payment":
            return self.test_payment_config()
        elif section == "settlement":
            return self.test_settlement_config()
        
        return True, []
    
    def test_module_config(self, module_name: str) -> TestResult:
        """测试模块配置"""
        result = TestResult(f"module.{module_name}")
        
        try:
            config = self.config_manager.get_module_config(module_name)
            
            # 验证必填字段
            if config.min_amount <= 0:
                result.add_error("最小金额必须大于0")
            
            if config.max_amount <= 0:
                result.add_error("最大金额必须大于0")
            
            if config.min_amount > config.max_amount:
                result.add_error("最小金额不能大于最大金额")
            
            if config.commission_rate <= 0 or config.commission_rate > 1:
                result.add_error(f"佣金比例必须在0-1之间: {config.commission_rate}")
            
            result.success = not result.has_errors()
            
        except Exception as e:
            result.add_error(f"测试异常: {str(e)}")
        
        return result
    
    def test_payment_config(self) -> Tuple[bool, List[str]]:
        """测试支付配置"""
        errors = []
        
        payment = self.config_manager.get_config_value("payment", {})
        
        if payment.get("enabled", False):
            wechat = payment.get("wechat", {})
            if wechat.get("enabled", False):
                if not wechat.get("app_id"):
                    errors.append("微信支付未配置app_id")
            
            alipay = payment.get("alipay", {})
            if alipay.get("enabled", False):
                if not alipay.get("app_id"):
                    errors.append("支付宝未配置app_id")
        
        return len(errors) == 0, errors
    
    def test_settlement_config(self) -> Tuple[bool, List[str]]:
        """测试结算配置"""
        errors = []
        
        settlement = self.config_manager.get_config_value("settlement", {})
        
        developer = settlement.get("developer", {})
        if developer.get("commission_rate", 0) <= 0:
            errors.append("开发者佣金比例必须大于0")
        
        return len(errors) == 0, errors


# 获取全局配置管理器实例
_config_manager_instance = None

def get_config_manager(config_path: str = None) -> UnifiedConfigManager:
    """获取配置管理器单例"""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = UnifiedConfigManager(config_path)
    return _config_manager_instance
