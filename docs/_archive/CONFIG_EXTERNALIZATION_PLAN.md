# LivingTree AI Agent 配置外部化方案
> 版本: 1.0
> 日期: 2026-04-25
> 状态: 进行中

---

## 一、目标

将项目中硬编码的配置项外化到统一配置文件，支持：
- YAML/YAML 环境变量覆盖
- 环境变量自动注入
- 运行时热更新
- 分环境配置 (dev/staging/prod)

---

## 二、配置结构

### 2.1 统一配置模板

```yaml
# config/unified.yaml

# ===========================================
# 服务端点配置
# ===========================================
endpoints:
  ollama:
    url: "http://localhost:11434"
    timeout: 30
    max_retries: 3
    
  cloud_sync:
    url: "ws://localhost:8765/sync"
    timeout: 30
    retry_delay: 5
    
  tracker:
    url: "http://localhost:8765"
    
  relay:
    default: "139.199.124.242:8888"
    
  webrtc:
    signaling: "0.0.0.0:8080"
    
  market:
    tools: "https://market.hermes-ai.cn/tools/manifest.json"

# ===========================================
# 网络超时配置
# ===========================================
timeouts:
  default: 30
  long: 60
  browser: 15
  download: 120
  quick: 5
  search: 10

# ===========================================
# 重试配置
# ===========================================
retries:
  default: 3
  message: 5
  download: 3
  exponential_base: 2

# ===========================================
# 延迟配置 (秒)
# ===========================================
delays:
  # 轮询间隔
  polling_short: 0.1
  polling_medium: 0.5
  polling_long: 1.0
  
  # 周期任务
  periodic_check: 5
  heartbeat: 30
  long_task: 60
  
  # 长等待
  wait_short: 1
  wait_medium: 2
  wait_long: 5
  wait_extreme: 10

# ===========================================
# 批处理配置
# ===========================================
batch:
  default_size: 32
  large_size: 100
  small_size: 10
  page_size: 100

# ===========================================
# 资源限制
# ===========================================
limits:
  max_file_size: 52428800  # 50MB
  max_cache_size: 1073741824  # 1GB
  max_tokens: 2048
  max_context: 4096
  max_level: 4

# ===========================================
# API Keys (通过环境变量覆盖)
# ===========================================
api_keys:
  openai: "${OPENAI_API_KEY}"
  anthropic: "${ANTHROPIC_API_KEY}"
  deepseek: "${DEEPSEEK_API_KEY}"
  moonshot: "${MOONSHOT_API_KEY}"
  dashscope: "${DASHSCOPE_API_KEY}"
  modelscope: "${MODELSCOPE_TOKEN}"
  huggingface: "${HF_TOKEN}"

# ===========================================
# 路径配置
# ===========================================
paths:
  data: "./data"
  logs: "./logs"
  cache: "./cache"
  temp: "/tmp"
  
  # 特定数据目录
  distillation: "./data/distillation"
  templates: "./data/templates"
  vector_db: "./data/vector_db"
  regulations: "./data/regulations"

# ===========================================
# LLM 默认参数
# ===========================================
llm:
  temperature: 0.7
  top_p: 0.9
  top_k: 40
  repeat_penalty: 1.1
  max_tokens: 2048
```

---

## 三、实施计划

### 阶段一：创建统一配置模块 (P0)
- [ ] 创建 `core/config/unified_config.py`
- [ ] 实现 YAML 加载 + 环境变量覆盖
- [ ] 实现配置热更新
- [ ] 编写单元测试

### 阶段二：核心模块配置化 (P1)
- [ ] `core/config.py` → 迁移到统一配置
- [ ] Ollama 相关 → 统一 endpoint 配置
- [ ] 云同步相关 → 统一配置
- [ ] 浏览器自动化 → 统一 timeout 配置

### 阶段三：逐步迁移 (P2)
- [ ] Expert Learning 模块
- [ ] Fusion RAG 模块
- [ ] Expert Distillation 模块
- [ ] 其他核心模块

---

## 四、关键配置项映射

| 原硬编码 | 配置路径 | 说明 |
|---------|---------|------|
| `localhost:11434` | `endpoints.ollama.url` | Ollama 服务地址 |
| `timeout=30` | `timeouts.default` | 默认超时 |
| `max_retries=3` | `retries.default` | 默认重试 |
| `asyncio.sleep(0.5)` | `delays.polling_medium` | 中等轮询间隔 |
| `./data/` | `paths.data` | 数据根目录 |

---

## 五、使用示例

```python
from core.config.unified_config import UnifiedConfig

config = UnifiedConfig.get_instance()

# 获取配置
ollama_url = config.get("endpoints.ollama.url")
timeout = config.get("timeouts.default")

# 环境变量自动覆盖
# export OPENAI_API_KEY=sk-xxx
api_key = config.get("api_keys.openai")  # 自动读取环境变量

# 热更新
config.reload()
```

---

## 六、向后兼容性

- 保持现有默认值
- 渐进式迁移，不破坏现有代码
- 配置加载失败时使用硬编码兜底

---

**维护者**: LivingTree AI Team
**更新日期**: 2026-04-25
