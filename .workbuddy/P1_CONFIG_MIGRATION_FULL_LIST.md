# P1 配置迁移 - 完整清单

> 生成时间: 2026-04-25
> 扫描范围: time.sleep(), timeout=, interval=, retry=/max_retries=

---

## 📊 统计概览

| 类型 | 匹配文件数 | 说明 |
|------|-----------|------|
| `time.sleep()` | 103 个文件 | 硬编码延迟 |
| `timeout = 数字` | 394+ 处 | 超时配置 |
| `interval = 数字` | 103+ 处 | 轮询间隔 |
| `retry = 数字` | 93+ 处 | 重试配置 |
| **总计** | **200+ 个文件** | 待迁移 |

---

## ✅ 已完成迁移 (2026-04-24 ~ 2026-04-25)

### 1. 重试配置
| 模块 | 配置键 | 状态 |
|------|--------|------|
| `core/task_execution_engine.py` | `retries.default` | ✅ |
| `core/unified_api.py` | `retries.http` | ✅ |
| `core/download_manager.py` | `retries.download` | ✅ |

### 2. 心跳/轮询配置
| 模块 | 配置键 | 状态 |
|------|--------|------|
| `core/cloud_sync/sync_client.py` | `sync.interval` | ✅ |
| `core/decommerce/services/base.py` | `heartbeat.service_*` | ✅ |
| `core/deployment_monitor.py` | `polling.check` | ✅ |
| `core/decommerce/datachannel_transport.py` | `heartbeat.datachannel_*` | ✅ |
| `core/relay_router/health_monitor.py` | `heartbeat.default_*` | ✅ |
| `core/smart_help_system/answer_monitor.py` | `polling.check_interval` | ✅ |

### 3. API Keys 配置
| 模块 | Provider | 状态 |
|------|----------|------|
| `core/living_tree_ai/knowledge/document_qa.py` | openai | ✅ |
| `core/living_tree_ai/knowledge/document_processor.py` | openai | ✅ |
| `core/meeting/meeting_manager.py` | groq, openrouter | ✅ |
| `core/living_tree_ai/browser_gateway/browser_use_adapter.py` | openai, google, anthropic | ✅ |

---

## 📋 待迁移清单

### 🔴 P1-A: 核心网络/同步模块 (最高优先级)

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 1 | `core/vheer_client.py` | sleep, timeout, interval | 5, 30, 60 |
| 2 | `core/relay_chain/node_manager.py` | sleep, retry | 3, 5, 10 |
| 3 | `core/relay_chain/monitor.py` | sleep, interval | 5, 10, 30 |
| 4 | `core/relay_router/connection_manager.py` | sleep, retry, timeout | 3, 5, 30 |
| 5 | `core/decentralized_mailbox/relay_sync.py` | interval, timeout | 30, 60 |
| 6 | `core/decentralized_mailbox/message_router.py` | check_interval | 10, 30 |
| 7 | `core/webrtc/turn_client.py` | timeout, retry | 10, 30 |
| 8 | `core/relay_client.py` | sleep, timeout | 3, 5, 30 |

### 🟡 P1-B: Agent/任务执行模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 9 | `core/agent.py` | sleep, timeout, max_retries | 5, 30, 3 |
| 10 | `core/agent_chat.py` | timeout, retry | 30, 60 |
| 11 | `core/task_execution_engine.py` | sleep (已部分迁移) | 5, 10 |
| 12 | `core/task_decomposer.py` | sleep | 2, 5 |
| 13 | `core/system_brain.py` | timeout, sleep | 30, 60 |
| 14 | `core/reasoning_client.py` | retry, timeout | 3, 30 |
| 15 | `core/remote_api_client.py` | timeout, retry | 10, 30 |

### 🟡 P1-C: 部署/沙箱模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 16 | `core/smart_deploy/sandbox_executor.py` | sleep, timeout | 5, 30 |
| 17 | `core/smart_deploy/deployment_engine.py` | sleep, timeout | 10, 60 |
| 18 | `core/smart_deploy/obstacle_resolver.py` | retry, timeout | 3, 30 |
| 19 | `core/performance_deployment.py` | sleep | 5, 10 |
| 20 | `core/deployment_monitor.py` | (已迁移) | - |

### 🟡 P1-D: Provider/云驱动模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 21 | `core/provider/cloud_driver.py` | timeout, retry | 30, 3 |
| 22 | `core/provider/cloud/openai_compatible_driver.py` | timeout, retry | 30, 3 |
| 23 | `core/cloud_sync/sync_client.py` | (已迁移) | - |

### 🟡 P1-E: 本地文件/同步模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 24 | `core/local_file_search/incremental_sync.py` | sleep, interval | 5, 10 |
| 25 | `core/local_file_search/usn_monitor.py` | sleep, interval | 5, 10 |
| 26 | `core/model_manager.py` | sleep, timeout | 10, 30 |
| 27 | `core/model_store/p2p_discovery.py` | sleep | 5 |

### 🟢 P1-F: 智能写作/AI模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 28 | `core/smart_writing/streaming_output.py` | sleep | 0.1, 0.5 |
| 29 | `core/smart_writing/error_recovery.py` | retry, sleep | 3, 5 |
| 30 | `core/smart_fallback/external_ai_client.py` | timeout | 30 |
| 31 | `core/smart_ai_router.py` | timeout | 30 |
| 32 | `core/ai_capability_detector.py` | timeout | 30 |

### 🟢 P1-G: 安全/加密模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 33 | `core/key_management/key_rotator.py` | retry | 3 |
| 34 | `core/key_management/key_health_monitor.py` | interval | 60 |

### 🟢 P1-H: UI/自动化模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 35 | `core/ui_automation.py` | sleep | 1, 2, 5 |
| 36 | `core/ui_self_check/async_task_queue.py` | sleep | 1, 2 |
| 37 | `core/self_upgrade/evolution_scheduler.py` | sleep, interval | 60, 300 |
| 38 | `core/ui_evolution/evolution_scheduler.py` | sleep, interval | 60, 300 |

### 🟢 P1-I: P2P网络/分布式模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 39 | `core/relay_chain/event_ext/p2p_network/zero_config.py` | sleep | 2, 5 |
| 40 | `core/relay_chain/event_ext/p2p_network/network/connection.py` | timeout, sleep | 10, 30 |
| 41 | `core/relay_chain/event_ext/p2p_network/distributed_node.py` | sleep | 5 |
| 42 | `core/relay_chain/event_ext/p2p_network/discovery/multicast.py` | sleep | 5 |
| 43 | `core/relay_chain/event_ext/p2p_network/discovery/election.py` | sleep | 2, 5 |
| 44 | `core/p2p_network_bootstrap/node_discovery.py` | sleep | 5 |
| 45 | `core/p2p_network_bootstrap/gossip_protocol.py` | interval | 30 |
| 46 | `core/lightweight_ui/relay_client.py` | retry, timeout | 3, 30 |
| 47 | `core/lightweight_ui/fast_recovery.py` | retry | 3, 5 |

### 🟢 P1-J: Decommence/商务模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 48 | `core/decommerce/services/ai_computing.py` | timeout | 30 |
| 49 | `core/decommerce/services/remote_assist.py` | timeout | 60 |
| 50 | `core/decommerce/services/live_view.py` | timeout | 30 |

### 🔵 P1-K: Server 服务端模块 (relay_server)

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 51 | `server/relay_server/services/ws_service.py` | timeout | 30, 60 |
| 52 | `server/relay_server/services/credit_sync_client.py` | interval, timeout | 30, 10 |
| 53 | `server/relay_server/services/user_auth_service.py` | timeout | 30 |
| 54 | `server/relay_server/services/payment_gateway.py` | timeout, retry | 30, 3 |
| 55 | `server/relay_server/email_sender.py` | retry | 3 |
| 56 | `server/relay_server/cluster/relay_cluster.py` | interval | 30 |

### 🔵 P1-L: Smart Writing 智能写作模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 57 | `core/smart_writing/data_collector.py` | timeout | 10, 30 |
| 58 | `core/smart_writing/cli_automation.py` | timeout, sleep | 30, 5 |
| 59 | `core/smart_writing/document_analyzer.py` | timeout | 30 |

### ⚪ P1-M: 工具集成模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 60 | `core/seamless_tool_integration/tool_executor.py` | timeout | 30 |
| 61 | `core/seamless_tool_integration/cloud_bridge.py` | retry, timeout | 3, 30 |
| 62 | `core/github_store/downloader.py` | retry | 3 |
| 63 | `core/unified_downloader/download_center.py` | timeout | 60 |

### ⚪ P1-N: 资源监控模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 64 | `core/resource_monitor.py` | interval | 5, 10 |
| 65 | `core/intelligent_diagnosis/task_monitor.py` | interval | 30 |
| 66 | `core/network_optimizer/monitor.py` | interval | 10 |
| 67 | `core/provider/monitor.py` | interval | 5, 10 |

### ⚪ P1-O: 生命周期/升级模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 68 | `core/self_evolution.py` | interval | 300 |
| 69 | `core/async_startup.py` | retry | 3 |
| 70 | `core/production_automation.py` | sleep | 5 |

### ⚪ P1-P: 其他模块

| # | 模块路径 | 硬编码类型 | 典型值 |
|---|----------|-----------|--------|
| 71 | `core/search_tool.py` | timeout | 30 |
| 72 | `core/meeting/recorder.py` | sleep | 5 |
| 73 | `core/meeting/meeting_manager.py` | timeout | 30 |
| 74 | `core/office_preview/file_watcher.py` | sleep | 5 |
| 75 | `core/skill_market.py` | timeout | 30 |
| 76 | `core/long_context/progressive_understanding_impl.py` | sleep | 5 |
| 77 | `core/wiki_compiler/compounding_engine.py` | timeout | 60 |
| 78 | `core/wiki_compiler/document_analyzer.py` | timeout | 30 |

---

## 📈 迁移进度估算

| 优先级 | 模块数 | 预估时间 |
|--------|--------|----------|
| 🔴 P1-A (核心网络) | 8 个 | 1-2 小时 |
| 🟡 P1-B~D (Agent/部署) | 13 个 | 2-3 小时 |
| 🟢 P1-E~J (功能模块) | 22 个 | 3-4 小时 |
| 🔵 P1-K~O (服务端/工具) | 20 个 | 3-4 小时 |
| ⚪ P1-P (其他) | 8 个 | 1-2 小时 |
| **总计** | **71 个核心模块** | **10-15 小时** |

---

## 🛠️ 迁移方法论

### 1. 配置分类

```yaml
# unified.yaml 结构
timeout:
  network: 30          # 网络请求超时
  api: 60              # API 调用超时
  deployment: 300      # 部署操作超时
  download: 60         # 下载超时

interval:
  health_check: 10     # 健康检查间隔
  sync: 30             # 同步间隔
  monitor: 5           # 监控间隔
  heartbeat: 10         # 心跳间隔

retry:
  default: 3           # 默认重试次数
  network: 5          # 网络重试
  critical: 1          # 关键操作不重试

sleep:
  short: 1             # 短等待
  medium: 5            # 中等等待
  long: 10             # 长等待
```

### 2. 迁移模式

```python
# Before (硬编码)
time.sleep(5)
timeout = 30
retry = 3

# After (配置化)
from core.unified_config import get_unified_config

config = get_unified_config()
time.sleep(config.get("sleep.medium", 5))
timeout = config.get("timeout.network", 30)
retry = config.get("retry.default", 3)
```

### 3. 快速迁移脚本

```python
# migrate_hardcoded_config.py
import re
from pathlib import Path

HARDCODE_PATTERNS = [
    (r'time\.sleep\((\d+)\)', 'sleep'),
    (r'timeout\s*=\s*(\d+)', 'timeout'),
    (r'interval\s*=\s*(\d+)', 'interval'),
    (r'max_retries\s*=\s*(\d+)', 'retry'),
]

def analyze_file(filepath):
    with open(filepath) as f:
        content = f.read()
    findings = []
    for pattern, kind in HARDCODE_PATTERNS:
        matches = re.finditer(pattern, content)
        for m in matches:
            findings.append({
                'line': content[:m.start()].count('\n') + 1,
                'kind': kind,
                'value': m.group(1),
                'pattern': m.group(0)
            })
    return findings
```

---

## 📝 下一步行动

1. **立即开始**: P1-A (core/vheer_client.py)
2. **批量处理**: 同一类型的模块一起迁移
3. **测试验证**: 每个模块迁移后运行测试
4. **文档更新**: 记录已迁移的配置键

---

*报告生成完毕*
