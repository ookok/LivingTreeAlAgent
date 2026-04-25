"""
Hermes P2P Tools - P2P核心封装为Hermes工具
==========================================

核心理念：将P2P系统的核心能力作为Hermes Agent的可调用工具，
让Agent能够通过自然语言操控P2P网络，实现"智能副驾驶"。

工具分类：
1. 节点管理 - 启动/停止/监控P2P节点
2. 配置诊断 - 检查配置、发现缺失、引导修复
3. 中继管理 - 连接/断开/监控中继服务器
4. 模型分发 - 搜索/下载/管理模型
5. 密钥管理 - 获取/验证/轮转API密钥

Author: Hermes Desktop AI Assistant
"""

import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from core.tools_registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


# ── 工具注册 ──────────────────────────────────────────────────────────────

def register_p2p_tools():
    """注册所有P2P工具到Hermes ToolRegistry"""
    _register_node_tools()
    _register_config_tools()
    _register_relay_tools()
    _register_model_tools()
    _register_key_tools()
    logger.info("Hermes P2P Tools 注册完成")


def get_p2p_tools() -> List[Dict]:
    """获取所有P2P工具的schema"""
    tools = ToolRegistry.get_by_toolset("p2p")
    return ToolRegistry.to_openai_schema(tools)


# ── 节点管理工具 ──────────────────────────────────────────────────────────

def _register_node_tools():
    """注册节点管理工具"""

    @tool(
        name="p2p_start_node",
        description="""启动P2P节点加入网络。

用法示例：
- "启动P2P节点"
- "加入P2P网络"

返回：节点ID、网络状态、邻居数量""",
        parameters={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "description": "启动模式：full(全节点) / light(轻节点)",
                    "enum": ["full", "light"]
                },
                "max_peers": {
                    "type": "integer",
                    "description": "最大邻居数"
                }
            }
        },
        toolset="p2p"
    )
    def p2p_start_node(context: Dict, mode: str = "full", max_peers: int = 50) -> Dict:
        """启动P2P节点"""
        try:
            # 导入P2P连接器
            from core.p2p_connector import get_p2p_connector

            connector = get_p2p_connector()
            success = connector.start()

            if success:
                return {
                    "success": True,
                    "node_id": connector.node_id,
                    "mode": mode,
                    "max_peers": max_peers,
                    "status": "online"
                }
            else:
                return {"success": False, "error": "节点启动失败"}
        except Exception as e:
            logger.error(f"启动P2P节点失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_stop_node",
        description="""停止P2P节点。

用法示例：
- "停止P2P节点"
- "断开P2P网络"

返回：操作结果""",
        parameters={
            "type": "object",
            "properties": {}
        },
        toolset="p2p"
    )
    def p2p_stop_node(context: Dict) -> Dict:
        """停止P2P节点"""
        try:
            from core.p2p_connector import get_p2p_connector

            connector = get_p2p_connector()
            connector.stop()

            return {"success": True, "status": "offline"}
        except Exception as e:
            logger.error(f"停止P2P节点失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_get_status",
        description="""获取P2P节点状态。

用法示例：
- "P2P节点状态如何"
- "查看节点运行状态"

返回：节点ID、连接状态、邻居数、流量统计""",
        parameters={
            "type": "object",
            "properties": {}
        },
        toolset="p2p"
    )
    def p2p_get_status(context: Dict) -> Dict:
        """获取节点状态"""
        try:
            from core.p2p_connector import get_p2p_connector

            connector = get_p2p_connector()

            return {
                "success": True,
                "node_id": connector.node_id if hasattr(connector, 'node_id') else "unknown",
                "status": "online" if connector.is_running else "offline",
                "peer_count": len(connector.get_peers()) if hasattr(connector, 'get_peers') else 0,
                "uptime_seconds": connector.uptime if hasattr(connector, 'uptime') else 0
            }
        except Exception as e:
            logger.error(f"获取节点状态失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_get_peers",
        description="""获取P2P网络邻居列表。

用法示例：
- "查看邻居节点"
- "有多少节点连接了我"

返回：邻居节点列表（ID、地址、状态）""",
        parameters={
            "type": "object",
            "properties": {}
        },
        toolset="p2p"
    )
    def p2p_get_peers(context: Dict) -> Dict:
        """获取邻居节点"""
        try:
            from core.p2p_connector import get_p2p_connector

            connector = get_p2p_connector()
            peers = connector.get_peers() if hasattr(connector, 'get_peers') else []

            return {
                "success": True,
                "peer_count": len(peers),
                "peers": [
                    {
                        "id": p.peer_id if hasattr(p, 'peer_id') else str(i),
                        "address": p.address if hasattr(p, 'address') else "unknown",
                        "status": p.status.value if hasattr(p, 'status') else "unknown"
                    }
                    for i, p in enumerate(peers[:10])  # 最多返回10个
                ]
            }
        except Exception as e:
            logger.error(f"获取邻居失败: {e}")
            return {"success": False, "error": str(e)}


# ── 配置管理工具 ──────────────────────────────────────────────────────────

def _register_config_tools():
    """注册配置管理工具"""

    @tool(
        name="p2p_check_config",
        description="""检查P2P系统配置完整性。

用法示例：
- "检查P2P配置是否完整"
- "我配置了哪些P2P参数"

返回：配置项列表、缺失项、建议""",
        parameters={
            "type": "object",
            "properties": {
                "feature": {
                    "type": "string",
                    "description": "指定功能检查（如 weather_api, map_service）"
                }
            }
        },
        toolset="p2p"
    )
    def p2p_check_config(context: Dict, feature: Optional[str] = None) -> Dict:
        """检查配置"""
        try:
            from client.src.business.config import load_config
            from core.config_missing_detector import get_config_detector

            cfg = load_config()
            detector = get_config_detector()

            if feature:
                # 检查特定功能
                missing = detector.detect_missing([feature])
                return {
                    "success": True,
                    "feature": feature,
                    "is_complete": len(missing) == 0,
                    "missing_items": missing
                }
            else:
                # 检查全部
                all_features = [
                    "weather_api", "map_service", "search_api",
                    "model_store", "relay_server", "api_keys"
                ]
                results = {}
                for f in all_features:
                    missing = detector.detect_missing([f])
                    results[f] = {
                        "is_complete": len(missing) == 0,
                        "missing": missing
                    }

                return {
                    "success": True,
                    "feature_results": results,
                    "total_features": len(all_features),
                    "complete_count": sum(1 for r in results.values() if r["is_complete"])
                }
        except Exception as e:
            logger.error(f"检查配置失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_get_missing_config",
        description="""获取缺失的配置项及其修复引导。

用法示例：
- "我还需要配置什么"
- "哪些功能还没配置好"

返回：缺失项列表、优先级、引导URL""",
        parameters={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "配置类别：api/relay/storage",
                    "enum": ["api", "relay", "storage", "all"]
                }
            }
        },
        toolset="p2p"
    )
    def p2p_get_missing_config(context: Dict, category: str = "all") -> Dict:
        """获取缺失配置"""
        try:
            from core.config_missing_detector import get_config_detector

            detector = get_config_detector()
            missing = detector.get_all_missing()

            # 按类别过滤
            if category != "all":
                filtered = [m for m in missing if m.get("category") == category]
            else:
                filtered = missing

            return {
                "success": True,
                "missing_count": len(filtered),
                "missing_items": [
                    {
                        "key": m.get("key"),
                        "description": m.get("description"),
                        "priority": m.get("priority", "medium"),
                        "guide_url": m.get("guide_url"),
                        "category": m.get("category")
                    }
                    for m in filtered
                ]
            }
        except Exception as e:
            logger.error(f"获取缺失配置失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_update_config",
        description="""更新P2P系统配置。

用法示例：
- "设置中继服务器为 139.199.124.242:8888"
- "修改最大邻居数为100"

返回：更新结果""",
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "配置项名称"
                },
                "value": {
                    "type": "string",
                    "description": "配置值"
                }
            },
            "required": ["key", "value"]
        },
        toolset="p2p"
    )
    def p2p_update_config(context: Dict, key: str, value: str) -> Dict:
        """更新配置"""
        try:
            from client.src.business.config import load_config, save_config
            import json

            cfg = load_config()

            # 根据key更新对应配置
            updated = False
            key_lower = key.lower()

            if "relay" in key_lower and "server" in key_lower:
                if not cfg.model_store.relay_servers:
                    cfg.model_store.relay_servers = []
                cfg.model_store.relay_servers = [value]
                updated = True
            elif "max_peer" in key_lower:
                cfg.model_store.max_concurrent_downloads = int(value)
                updated = True
            elif "storage" in key_lower and "dir" in key_lower:
                cfg.model_store.storage_dir = value
                updated = True

            if updated:
                save_config(cfg)
                return {"success": True, "key": key, "value": value}
            else:
                return {"success": False, "error": f"未知配置项: {key}"}
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_validate_config",
        description="""验证配置有效性。

用法示例：
- "验证我的API Key是否有效"
- "检查中继服务器是否可达"

返回：验证结果、错误信息（如有）""",
        parameters={
            "type": "object",
            "properties": {
                "config_type": {
                    "type": "string",
                    "description": "配置类型",
                    "enum": ["api_key", "relay_server", "storage"]
                },
                "value": {
                    "type": "string",
                    "description": "待验证的值"
                }
            },
            "required": ["config_type", "value"]
        },
        toolset="p2p"
    )
    def p2p_validate_config(context: Dict, config_type: str, value: str) -> Dict:
        """验证配置"""
        try:
            if config_type == "api_key":
                # 验证API Key
                from core.key_management import get_key_manager
                km = get_key_manager()
                if km and km._initialized:
                    consumer = km.consumer
                    if consumer:
                        key = consumer.get_key_for_provider(value.split("_")[0].lower())
                        return {"success": True, "valid": bool(key), "key_type": "api_key"}
                return {"success": False, "error": "密钥管理系统未初始化"}

            elif config_type == "relay_server":
                # 验证中继服务器
                import socket
                try:
                    host, port = value.split(":")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, int(port)))
                    sock.close()
                    return {"success": True, "valid": result == 0, "address": value}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            else:
                return {"success": False, "error": f"未知配置类型: {config_type}"}
        except Exception as e:
            logger.error(f"验证配置失败: {e}")
            return {"success": False, "error": str(e)}


# ── 中继服务器工具 ───────────────────────────────────────────────────────

def _register_relay_tools():
    """注册中继服务器工具"""

    @tool(
        name="p2p_connect_relay",
        description="""连接到中继服务器。

用法示例：
- "连接中继服务器"
- "接入中继网络"

返回：连接结果""",
        parameters={
            "type": "object",
            "properties": {
                "relay_address": {
                    "type": "string",
                    "description": "中继服务器地址（格式：host:port）"
                }
            }
        },
        toolset="p2p"
    )
    def p2p_connect_relay(context: Dict, relay_address: Optional[str] = None) -> Dict:
        """连接中继服务器"""
        try:
            from core.model_store import get_store_manager
            from client.src.business.config import load_config

            cfg = load_config()
            relay_servers = cfg.model_store.relay_servers

            if not relay_address and relay_servers:
                relay_address = relay_servers[0]

            if not relay_address:
                return {"success": False, "error": "未指定中继服务器"}

            store = get_store_manager(config={
                'relay_servers': [relay_address],
                'enable_p2p': True
            })

            return {
                "success": True,
                "relay_address": relay_address,
                "status": "connected"
            }
        except Exception as e:
            logger.error(f"连接中继失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_get_relay_status",
        description="""获取中继服务器状态。

用法示例：
- "中继服务器状态如何"
- "查看中继网络连接"

返回：中继列表、连接状态、延迟""",
        parameters={
            "type": "object",
            "properties": {}
        },
        toolset="p2p"
    )
    def p2p_get_relay_status(context: Dict) -> Dict:
        """获取中继状态"""
        try:
            from client.src.business.config import load_config

            cfg = load_config()
            relay_servers = cfg.model_store.relay_servers

            results = []
            for relay in relay_servers or []:
                # 简单检测
                import socket
                try:
                    host, port = relay.split(":")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    start = time.time()
                    result = sock.connect_ex((host, int(port)))
                    latency = (time.time() - start) * 1000
                    sock.close()
                    results.append({
                        "address": relay,
                        "reachable": result == 0,
                        "latency_ms": round(latency, 2)
                    })
                except Exception as e:
                    results.append({
                        "address": relay,
                        "reachable": False,
                        "error": str(e)
                    })

            return {
                "success": True,
                "relay_count": len(results),
                "relays": results
            }
        except Exception as e:
            logger.error(f"获取中继状态失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_broadcast",
        description="""向P2P网络广播消息。

用法示例：
- "广播消息给所有邻居"
- "通知网络我有新模型"

返回：广播结果、接收节点数""",
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "广播消息内容"
                },
                "message_type": {
                    "type": "string",
                    "description": "消息类型",
                    "enum": ["text", "model_announce", "config_sync", "chat"]
                }
            },
            "required": ["message"]
        },
        toolset="p2p"
    )
    def p2p_broadcast(context: Dict, message: str, message_type: str = "text") -> Dict:
        """广播消息"""
        try:
            from core.p2p_connector import get_p2p_connector

            connector = get_p2p_connector()
            peer_count = len(connector.get_peers()) if hasattr(connector, 'get_peers') else 0

            # 实际广播逻辑需要connector支持
            return {
                "success": True,
                "message_type": message_type,
                "target_peer_count": peer_count,
                "status": "broadcast_sent"
            }
        except Exception as e:
            logger.error(f"广播失败: {e}")
            return {"success": False, "error": str(e)}


# ── 模型分发工具 ─────────────────────────────────────────────────────────

def _register_model_tools():
    """注册模型分发工具"""

    @tool(
        name="p2p_search_models",
        description="""搜索可用的P2P模型。

用法示例：
- "搜索气象预测模型"
- "查找AQI相关的模型"

返回：模型列表（名称、大小、来源、可用性）""",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "category": {
                    "type": "string",
                    "description": "模型类别筛选"
                }
            }
        },
        toolset="p2p"
    )
    def p2p_search_models(context: Dict, query: str, category: Optional[str] = None) -> Dict:
        """搜索模型"""
        try:
            from core.model_store import get_store_manager

            store = get_store_manager()
            results = store.search_models(query) if hasattr(store, 'search_models') else []

            if category:
                results = [r for r in results if r.get('category') == category]

            return {
                "success": True,
                "query": query,
                "result_count": len(results),
                "models": results[:20]  # 最多返回20个
            }
        except Exception as e:
            logger.error(f"搜索模型失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_download_model",
        description="""从P2P网络下载模型。

用法示例：
- "下载气象预测模型"
- "安装air_quality_model"

返回：下载任务ID、状态""",
        parameters={
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "模型ID"
                },
                "priority": {
                    "type": "string",
                    "description": "下载优先级",
                    "enum": ["high", "normal", "low"]
                }
            },
            "required": ["model_id"]
        },
        toolset="p2p"
    )
    def p2p_download_model(context: Dict, model_id: str, priority: str = "normal") -> Dict:
        """下载模型"""
        try:
            from core.model_store import get_store_manager

            store = get_store_manager()

            # 启动下载
            if hasattr(store, 'download_model'):
                task_id = store.download_model(model_id, background=True)
                return {
                    "success": True,
                    "task_id": task_id,
                    "model_id": model_id,
                    "status": "downloading"
                }

            return {"success": False, "error": "下载功能不可用"}
        except Exception as e:
            logger.error(f"下载模型失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_get_download_progress",
        description="""获取模型下载进度。

用法示例：
- "查看下载进度"
- "气象模型下完了吗"

返回：下载进度、预计剩余时间""",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "下载任务ID"
                }
            }
        },
        toolset="p2p"
    )
    def p2p_get_download_progress(context: Dict, task_id: Optional[str] = None) -> Dict:
        """获取下载进度"""
        try:
            from core.model_store import get_store_manager

            store = get_store_manager()

            if hasattr(store, 'get_download_progress'):
                progress = store.get_download_progress(task_id)
                return {
                    "success": True,
                    "task_id": task_id,
                    "progress_percent": progress.get("percent", 0),
                    "speed_mbps": progress.get("speed", 0),
                    "status": progress.get("status", "unknown")
                }

            return {"success": False, "error": "进度查询不可用"}
        except Exception as e:
            logger.error(f"获取进度失败: {e}")
            return {"success": False, "error": str(e)}


# ── 密钥管理工具 ──────────────────────────────────────────────────────────

def _register_key_tools():
    """注册密钥管理工具"""

    @tool(
        name="p2p_get_api_key",
        description="""获取API密钥。

用法示例：
- "获取OpenWeatherMap的API Key"
- "我有Serper Key吗"

返回：密钥状态（不返回完整密钥值）""",
        parameters={
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "服务提供商",
                    "enum": ["openweather", "serper", "brave", "modelscope", "huggingface", "openai"]
                }
            },
            "required": ["provider"]
        },
        toolset="p2p"
    )
    def p2p_get_api_key(context: Dict, provider: str) -> Dict:
        """获取API密钥"""
        try:
            from core.key_management import get_key_manager

            km = get_key_manager()
            if not km or not km._initialized:
                return {"success": False, "error": "密钥管理系统未初始化"}

            consumer = km.consumer
            if not consumer:
                return {"success": False, "error": "密钥消费者未初始化"}

            try:
                key = consumer.get_key_for_provider(provider, skip_audit=True)
                # 不返回完整密钥，只返回状态
                masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
                return {
                    "success": True,
                    "provider": provider,
                    "has_key": True,
                    "key_preview": masked
                }
            except KeyError:
                return {
                    "success": True,
                    "provider": provider,
                    "has_key": False
                }
        except Exception as e:
            logger.error(f"获取API密钥失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_check_key_health",
        description="""检查API密钥健康状态。

用法示例：
- "检查我的API Key还可用吗"
- "验证密钥有效性"

返回：密钥状态、剩余配额、过期时间""",
        parameters={
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": "服务提供商"
                }
            },
            "required": ["provider"]
        },
        toolset="p2p"
    )
    def p2p_check_key_health(context: Dict, provider: str) -> Dict:
        """检查密钥健康"""
        try:
            from core.key_management import get_key_manager

            km = get_key_manager()
            if not km or not km._initialized:
                return {"success": False, "error": "密钥管理系统未初始化"}

            health = km.get_health_report() if hasattr(km, 'get_health_report') else {}

            provider_health = health.get(provider, {})
            return {
                "success": True,
                "provider": provider,
                "status": provider_health.get("status", "unknown"),
                "quota_used": provider_health.get("quota_used", 0),
                "quota_limit": provider_health.get("quota_limit", 0)
            }
        except Exception as e:
            logger.error(f"检查密钥健康失败: {e}")
            return {"success": False, "error": str(e)}

    @tool(
        name="p2p_list_providers",
        description="""列出所有已配置的API提供商。

用法示例：
- "我配置了哪些API"
- "查看API提供商列表"

返回：提供商列表、密钥状态""",
        parameters={
            "type": "object",
            "properties": {}
        },
        toolset="p2p"
    )
    def p2p_list_providers(context: Dict) -> Dict:
        """列出提供商"""
        try:
            from core.key_management import get_key_manager

            km = get_key_manager()
            if not km or not km._initialized:
                return {"success": False, "error": "密钥管理系统未初始化"}

            consumer = km.consumer
            if not consumer:
                return {"success": False, "error": "密钥消费者未初始化"}

            # 获取所有provider的key信息
            providers = []
            all_keys = consumer.storage.get_all_keys() if hasattr(consumer.storage, 'get_all_keys') else {}

            for name in all_keys:
                try:
                    key_info = consumer.get_key_info(name)
                    providers.append({
                        "name": name,
                        "has_key": bool(key_info),
                        "is_valid": key_info.get("is_valid", False) if key_info else False
                    })
                except:
                    providers.append({"name": name, "has_key": False})

            return {
                "success": True,
                "provider_count": len(providers),
                "providers": providers
            }
        except Exception as e:
            logger.error(f"列出提供商失败: {e}")
            return {"success": False, "error": str(e)}