"""
LivingTreeAI 配置参数元数据注册表
==================================

预生成的参数解释、文档链接、最佳实践
每个配置项包含：key, name, description, default, range, link, tips
"""

CONFIG_METADATA = {
    # ========== 网络配置 ==========
    "network": {
        "display_name": "网络配置",
        "fields": {
            "listen_port": {
                "name": "监听端口",
                "description": "节点监听的UDP/TCP端口，用于接收其他节点的连接请求。",
                "default": 18765,
                "range": [1024, 65535],
                "link": "https://docs.livingtreeai.ai/network#listen_port",
                "tips": "建议使用5000-20000范围内的随机端口，避免与其他服务冲突。",
                "category": "network"
            },
            "udp_broadcast_port": {
                "name": "UDP广播端口",
                "description": "用于局域网内节点发现的UDP广播端口。",
                "default": 18766,
                "range": [1024, 65535],
                "link": "https://docs.livingtreeai.ai/network#udp_broadcast",
                "tips": "在同一局域网内的节点需使用相同端口才能发现彼此。",
                "category": "network"
            },
            "max_connections": {
                "name": "最大连接数",
                "description": "节点同时保持的最大P2P连接数。",
                "default": 50,
                "range": [10, 500],
                "link": "https://docs.livingtreeai.ai/network#max_connections",
                "tips": "数值越大占用资源越多，建议内网节点设为100+，移动设备设为20。",
                "category": "network"
            },
            "bandwidth_limit": {
                "name": "带宽限制 (KB/s)",
                "description": "单节点最大上传/下载带宽限制，0表示不限制。",
                "default": 0,
                "range": [0, 10000],
                "link": "https://docs.livingtreeai.ai/network#bandwidth",
                "tips": "低带宽环境建议设置100-500KB/s，无限制可能影响其他网络使用。",
                "category": "network"
            },
            "relay_enabled": {
                "name": "启用中继服务",
                "description": "是否启用作为中继节点，帮助NAT穿透失败的节点通信。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/network#relay",
                "tips": "启用会消耗额外带宽，但能提升网络整体连通率。",
                "category": "network"
            },
            "nat_traversal": {
                "name": "NAT穿透模式",
                "description": "NAT穿透策略：disabled关闭，enabled尝试穿透，force强制穿透。",
                "default": "enabled",
                "range": ["disabled", "enabled", "force"],
                "link": "https://docs.livingtreeai.ai/network#nat_traversal",
                "tips": "家庭网络建议用enabled，企业网络建议disabled。",
                "category": "network"
            },
        }
    },

    # ========== 节点配置 ==========
    "node": {
        "display_name": "节点配置",
        "fields": {
            "node_name": {
                "name": "节点名称",
                "description": "您在网络中的显示名称，用于其他节点识别。",
                "default": "",
                "range": None,  # 字符串
                "link": "https://docs.livingtreeai.ai/node#name",
                "tips": "建议使用易记的名称，如「北京-开发机」或「树莓派-客厅」。",
                "category": "basic"
            },
            "node_type": {
                "name": "节点类型",
                "description": "节点的专业化方向，影响任务分配权重和知识领域。",
                "default": "general",
                "range": ["general", "research", "storage", "compute", "coordinator"],
                "link": "https://docs.livingtreeai.ai/node#type",
                "tips": "general通用型接受所有任务；专业型在某领域权重更高。",
                "category": "basic"
            },
            "specialty": {
                "name": "专业领域",
                "description": "节点擅长的知识领域，用于智能任务分配。",
                "default": [],
                "range": None,  # 多选列表
                "link": "https://docs.livingtreeai.ai/node#specialty",
                "tips": "可多选，如同时选择「编程」和「数学」会让相关任务优先分配给您。",
                "category": "basic"
            },
            "auto_start": {
                "name": "开机自启",
                "description": "系统启动时自动运行节点。",
                "default": False,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/node#auto_start",
                "tips": "服务器/桌面设备建议开启，移动设备不建议以节省电量。",
                "category": "basic"
            },
            "max_offline_hours": {
                "name": "最大离线时间 (小时)",
                "description": "超过此时间未上线，节点将被标记为不活跃。",
                "default": 24,
                "range": [1, 168],
                "link": "https://docs.livingtreeai.ai/node#offline",
                "tips": "设置为0表示永不被标记离线，适合长期运行的服务器。",
                "category": "basic"
            },
        }
    },

    # ========== 联邦学习配置 ==========
    "federation": {
        "display_name": "联邦学习配置",
        "fields": {
            "fl_enabled": {
                "name": "启用联邦学习",
                "description": "是否参与联邦学习任务，贡献算力帮助训练共享模型。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/federation#enabled",
                "tips": "关闭后节点只进行知识共享，不参与模型训练。",
                "category": "fl"
            },
            "fl_algorithm": {
                "name": "聚合算法",
                "description": "联邦学习的模型聚合算法，影响收敛速度和最终模型质量。",
                "default": "fedavg",
                "range": ["fedavg", "fedprox", "scaffold"],
                "link": "https://docs.livingtreeai.ai/federation#algorithm",
                "tips": "fedavg适合数据分布相似；fedprox适合数据异构；scaffold加速收敛但需更多通信。",
                "category": "fl"
            },
            "local_epochs": {
                "name": "本地训练轮数",
                "description": "每轮联邦学习中，本地训练的epoch数。",
                "default": 1,
                "range": [1, 10],
                "link": "https://docs.livingtreeai.ai/federation#local_epochs",
                "tips": "数值越大本地训练越充分，但占用时间更长。",
                "category": "fl"
            },
            "batch_size": {
                "name": "批量大小",
                "description": "本地训练的批量大小，影响内存占用和训练稳定性。",
                "default": 8,
                "range": [1, 128],
                "link": "https://docs.livingtreeai.ai/federation#batch_size",
                "tips": "内存小的设备建议8-16，桌面/服务器可用32-64。",
                "category": "fl"
            },
            "learning_rate": {
                "name": "学习率",
                "description": "本地训练的学习率，影响模型收敛速度。",
                "default": 0.001,
                "range": [0.0001, 0.1],
                "link": "https://docs.livingtreeai.ai/federation#learning_rate",
                "tips": "通常不需要修改，使用默认的Adam优化器参数即可。",
                "category": "fl"
            },
            "model_size_limit": {
                "name": "模型大小限制 (MB)",
                "description": "愿意下载的模型最大体积，超过此大小的模型不会被分配。",
                "default": 2048,
                "range": [100, 10240],
                "link": "https://docs.livingtreeai.ai/federation#model_size",
                "tips": "树莓派建议限制500MB以内以节省存储和内存。",
                "category": "fl"
            },
            "min_contribution_score": {
                "name": "最低贡献门槛",
                "description": "参与联邦学习的最低信誉分数要求。",
                "default": 10,
                "range": [0, 100],
                "link": "https://docs.livingtreeai.ai/federation#min_score",
                "tips": "新节点为0，建议设为10以上以确保网络质量。",
                "category": "fl"
            },
        }
    },

    # ========== 知识共享配置 ==========
    "knowledge": {
        "display_name": "知识共享配置",
        "fields": {
            "knowledge_share_enabled": {
                "name": "启用知识共享",
                "description": "是否向网络贡献知识，获得积分奖励。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/knowledge#share_enabled",
                "tips": "关闭后仍可查询他人共享的知识，但不会获得分享奖励。",
                "category": "knowledge"
            },
            "auto_knowledge_extract": {
                "name": "自动知识提取",
                "description": "是否自动从对话/任务中提取知识加入知识库。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/knowledge#auto_extract",
                "tips": "开启后会自动分析您的提问和AI回答，提取有价值的信息。",
                "category": "knowledge"
            },
            "knowledge_quality_threshold": {
                "name": "知识质量阈值",
                "description": "只有评分高于此值的知识才会被共享出去。",
                "default": 0.7,
                "range": [0.0, 1.0],
                "link": "https://docs.livingtreeai.ai/knowledge#quality",
                "tips": "设置过高会减少分享量，过低会影响知识库整体质量。",
                "category": "knowledge"
            },
            "max_knowledge_storage": {
                "name": "本地知识库上限 (条)",
                "description": "本地缓存的最大知识条目数，超出后自动清理低评分内容。",
                "default": 10000,
                "range": [100, 100000],
                "link": "https://docs.livingtreeai.ai/knowledge#storage",
                "tips": "根据存储空间调整，1万条约需100MB存储。",
                "category": "knowledge"
            },
            "knowledge_sync_interval": {
                "name": "知识同步间隔 (分钟)",
                "description": "定期从网络同步最新知识的间隔时间。",
                "default": 30,
                "range": [5, 1440],
                "link": "https://docs.livingtreeai.ai/knowledge#sync",
                "tips": "间隔太短会增加网络流量，建议设置为15-60分钟。",
                "category": "knowledge"
            },
        }
    },

    # ========== 任务配置 ==========
    "task": {
        "display_name": "任务配置",
        "fields": {
            "accept_tasks": {
                "name": "接受任务分配",
                "description": "是否接受来自其他节点的任务分配。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/task#accept",
                "tips": "关闭后将不会收到新任务，但可以主动提交任务。",
                "category": "task"
            },
            "max_concurrent_tasks": {
                "name": "最大并发任务数",
                "description": "同时处理的最大任务数量。",
                "default": 2,
                "range": [1, 10],
                "link": "https://docs.livingtreeai.ai/task#concurrent",
                "tips": "移动设备建议1-2，桌面/服务器可根据CPU核心数设置。",
                "category": "task"
            },
            "task_categories": {
                "name": "任务类别偏好",
                "description": "愿意接受的任务类型，可多选。",
                "default": ["inference", "knowledge_query"],
                "range": ["inference", "knowledge_query", "data_processing", "model_training", "relay"],
                "link": "https://docs.livingtreeai.ai/task#categories",
                "tips": "选择您擅长的领域会获得更高权重和奖励。",
                "category": "task"
            },
            "task_timeout": {
                "name": "任务超时时间 (秒)",
                "description": "任务执行超过此时间将被标记为超时。",
                "default": 300,
                "range": [30, 3600],
                "link": "https://docs.livingtreeai.ai/task#timeout",
                "tips": "复杂推理任务可能需要更长时间，可根据需求调整。",
                "category": "task"
            },
        }
    },

    # ========== 激励配置 ==========
    "incentive": {
        "display_name": "激励配置",
        "fields": {
            "anonymous_mode": {
                "name": "匿名模式",
                "description": "启用后您的节点名称和贡献记录将被匿名化显示。",
                "default": False,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/incentive#anonymous",
                "tips": "如果您重视隐私可开启，但会影响某些排行榜显示。",
                "category": "incentive"
            },
            "public_profile": {
                "name": "公开个人主页",
                "description": "是否在网络上公开您的贡献档案和等级信息。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/incentive#profile",
                "tips": "关闭后仍可参与贡献，但不会显示在贡献排行榜上。",
                "category": "incentive"
            },
            "reward_notifications": {
                "name": "奖励通知",
                "description": "是否在获得积分/勋章时显示通知。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/incentive#notifications",
                "tips": "关闭可减少打扰，适合后台运行的服务器节点。",
                "category": "incentive"
            },
        }
    },

    # ========== 安全配置 ==========
    "security": {
        "display_name": "安全配置",
        "fields": {
            "encrypt_messages": {
                "name": "加密通信",
                "description": "是否对所有P2P消息进行端到端加密。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/security#encryption",
                "tips": "建议保持开启，只有在可信局域网内才可关闭以提升性能。",
                "category": "security"
            },
            "verify_node_identity": {
                "name": "节点身份验证",
                "description": "是否验证连接节点的身份签名，防止伪造攻击。",
                "default": True,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/security#identity",
                "tips": "建议开启，关闭后可能遭受女巫攻击。",
                "category": "security"
            },
            "max_trusted_nodes": {
                "name": "最大信任节点数",
                "description": "信任列表中的最大节点数，用于快速通道认证。",
                "default": 20,
                "range": [0, 100],
                "link": "https://docs.livingtreeai.ai/security#trust",
                "tips": "设为0表示不启用信任列表，所有连接都需完整验证。",
                "category": "security"
            },
        }
    },

    # ========== 高级配置 ==========
    "advanced": {
        "display_name": "高级配置",
        "fields": {
            "debug_mode": {
                "name": "调试模式",
                "description": "启用详细的调试日志，用于排查问题。",
                "default": False,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/advanced#debug",
                "tips": "正常使用时建议关闭，排查问题时开启。",
                "category": "advanced"
            },
            "log_level": {
                "name": "日志级别",
                "description": "日志记录的详细程度。",
                "default": "INFO",
                "range": ["DEBUG", "INFO", "WARNING", "ERROR"],
                "link": "https://docs.livingtreeai.ai/advanced#loglevel",
                "tips": "生产环境建议INFO，调试时用DEBUG，问题排查用ERROR。",
                "category": "advanced"
            },
            "profile_enabled": {
                "name": "性能分析",
                "description": "是否启用性能分析，统计CPU/内存/网络使用。",
                "default": False,
                "range": [True, False],
                "link": "https://docs.livingtreeai.ai/advanced#profile",
                "tips": "正常使用时建议关闭，需要优化时开启。",
                "category": "advanced"
            },
        }
    },
}


def get_metadata(section: str, field: str = None) -> dict:
    """获取指定配置项的元数据"""
    if field is None:
        return CONFIG_METADATA.get(section, {})
    return CONFIG_METADATA.get(section, {}).get("fields", {}).get(field, {})


def get_all_sections() -> list:
    """获取所有配置分组"""
    return list(CONFIG_METADATA.keys())


def get_section_fields(section: str) -> dict:
    """获取指定分组的所有字段元数据"""
    return CONFIG_METADATA.get(section, {}).get("fields", {})


def search_metadata(keyword: str) -> list:
    """搜索包含关键词的配置项"""
    results = []
    for section, section_data in CONFIG_METADATA.items():
        for field, field_data in section_data.get("fields", {}).items():
            if (keyword.lower() in field.lower() or
                keyword.lower() in field_data.get("name", "").lower() or
                keyword.lower() in field_data.get("description", "").lower()):
                results.append({
                    "section": section,
                    "field": field,
                    **field_data
                })
    return results
