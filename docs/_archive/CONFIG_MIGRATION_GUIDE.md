# 配置系统迁移指南

本文档指导如何将现有配置模块迁移到统一配置系统 (UnifiedConfig)。

## 📋 迁移概览

| 原模块 | 迁移到 | 状态 |
|--------|--------|------|
| `commission/config_manager.py` | `commission.section` | ✅ 已支持 |
| `decentralized_knowledge/config_manager.py` | `decentralized.section` | ✅ 已支持 |
| `provider/config_manager.py` | `provider.section` | ✅ 已支持 |
| `email_notification/config_manager.py` | `email.section` | ✅ 已支持 |
| `smart_config.py` | `smart_config.profile` | ✅ 已支持 |

---

## 🚀 快速迁移

### 方式一：直接替换（推荐）

**Before:**
```python
from core.commission.config_manager import CommissionConfigManager
config_manager = CommissionConfigManager()
rate = config_manager.get_commission_rate("deep_search")
```

**After:**
```python
from core.config.unified_config import get_config
config = get_config()
rate = config.get("commission.modules.deep_search.rate", 0.3)
```

### 方式二：使用专用API

```python
from core.config.unified_config import get_commission_config
config = get_commission_config("deep_search")
rate = config.get("rate", 0.3)
```

### 方式三：保持向后兼容

创建一个兼容层：

```python
# core/commission/config_manager.py (兼容层)

from core.config.unified_config import get_config

class CommissionConfigManager:
    """佣金配置管理器 - 兼容层"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_commission_rate(self, module: str) -> float:
        """获取佣金费率"""
        config = get_config()
        return config.get(f"commission.modules.{module}.rate", 0.2)
    
    def is_module_enabled(self, module: str) -> bool:
        """检查模块是否启用"""
        config = get_config()
        return config.get(f"commission.modules.{module}.enabled", True)
```

---

## 📖 各模块迁移详解

### 1. Commission 配置迁移

```python
# 迁移前
from core.commission.config_manager import CommissionConfigManager
manager = CommissionConfigManager.get_instance()

# 迁移后
from core.config.unified_config import get_commission_config

# 获取完整配置
config = get_commission_config()
# {'enabled': True, 'modules': {...}, 'payment': {...}, ...}

# 获取指定模块
deep_search_config = get_commission_config("deep_search")
# {'enabled': True, 'rate': 0.3}

# 直接访问
from core.config.unified_config import get_config
rate = get_config().get("commission.modules.deep_search.rate")
```

### 2. Decentralized 配置迁移

```python
# 迁移前
from core.decentralized_knowledge.config_manager import DecentralizedConfig
config = DecentralizedConfig()

# 迁移后
from core.config.unified_config import get_decentralized_config

config = get_decentralized_config()
# {
#     'enabled': True,
#     'p2p': {'port': 9001, 'max_peers': 50, ...},
#     'relay': {'servers': [...], ...},
#     ...
# }
```

### 3. Provider 配置迁移

```python
# 迁移前
from core.provider.config_manager import ProviderConfigManager
manager = ProviderConfigManager()

# 迁移后
from core.config.unified_config import get_provider_config, get_config

# 获取所有槽位
all_slots = get_provider_config()
# {'enabled': True, 'slots': {...}, 'strategy': {...}, ...}

# 获取指定槽位
slot_1 = get_provider_config("slot_1")
# {'name': 'primary', 'provider': 'openai', 'model': 'gpt-4', ...}

# 根据优先级获取
config = get_config()
slot = config.get_provider_slot_by_priority(1)
```

### 4. Email 配置迁移

```python
# 迁移前
from core.email_notification.config_manager import EmailConfig
config = EmailConfig()

# 迁移后
from core.config.unified_config import get_email_config

config = get_email_config()
# {
#     'enabled': False,
#     'smtp': {'host': 'smtp.gmail.com', ...},
#     'notification': {...}
# }

# 检查是否启用
if config.get('enabled'):
    smtp = config.get('smtp', {})
    ...
```

### 5. Browser Gateway 配置迁移

```python
# 迁移前
from core.living_tree_ai.browser_gateway.config.config_manager import BrowserGatewayConfig
config = BrowserGatewayConfig()

# 迁移后
from core.config.unified_config import get_browser_gateway_config

config = get_browser_gateway_config()
# {
#     'enabled': True,
#     'browser': {'type': 'chrome', ...},
#     'proxy': {...},
#     ...
# }
```

---

## 🔧 配置文件格式

在 `~/.livingtree/unified.yaml` 中配置：

```yaml
# 佣金配置
commission:
  enabled: true
  modules:
    deep_search:
      enabled: true
      rate: 0.3
    creation:
      enabled: true
      rate: 0.2

# 去中心化配置
decentralized:
  enabled: true
  p2p:
    port: 9001
    max_peers: 50
  relay:
    servers:
      - "139.199.124.242:8888"

# Provider槽位配置
provider:
  enabled: true
  slots:
    slot_1:
      name: "primary"
      provider: "openai"
      model: "gpt-4"

# 邮件配置
email:
  enabled: false
  smtp:
    host: "smtp.gmail.com"
    port: 587
```

---

## 📝 配置访问速查表

| 配置项 | 访问方式 |
|--------|----------|
| 佣金模块费率 | `get_config().get("commission.modules.{module}.rate")` |
| 去中心化P2P端口 | `get_config().get("decentralized.p2p.port")` |
| Provider槽位策略 | `get_config().get_provider_config("slot_1")` |
| 邮件SMTP配置 | `get_config().get_email_config()["smtp"]` |
| 浏览器类型 | `get_config().get("browser_gateway.browser.type")` |

---

## ⚠️ 注意事项

1. **环境变量**: 配置中的 `${VAR_NAME}` 会自动替换为环境变量
2. **默认值**: 使用 `get_config().get("key", default)` 提供合理的默认值
3. **热更新**: 运行时修改配置可通过 `set()` 方法，但不持久化
4. **持久化**: 需要持久化的配置应写入 `~/.livingtree/unified.yaml`

---

## 🧪 测试配置

```python
from core.config.unified_config import UnifiedConfig, get_config

# 初始化
config = UnifiedConfig.get_instance()

# 测试访问
assert config.get("commission.modules.deep_search.rate") == 0.3
assert config.get_decentralized_config()["p2p"]["port"] == 9001

# 测试便捷函数
from get_commission_config, get_decentralized_config
assert get_commission_config("deep_search")["enabled"] == True
```
