"""
Hermes AI算力工具集 (Hermes AI Capability Tools)
================================================

为Hermes Desktop提供AI算力相关的工具函数，供AI助手调用。

工具函数:
- get_local_ai_capability: 获取本地AI算力能力
- get_ai_capability_report: 获取格式化报告
- can_run_model: 检查模型兼容性
- publish_ai_service: 发布AI算力服务
- check_buyer_capability: 检查买家本地算力

作者: Hermes Desktop Team
"""

import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

# 导入核心模块
from business.ai_capability_detector import (
    AICapabilityRegistry,
    get_ai_capability_registry,
    get_local_capability,
    can_run_model as _can_run_model,
    HardwareSpec,
    CapabilityProfile,
    ModelSpec,
    ModelCompatibility,
)


# =============================================================================
# Hermes 工具函数
# =============================================================================

def get_local_ai_capability(override_specs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    获取本地AI算力能力

    Args:
        override_specs: 可选的硬件规格覆盖值

    Returns:
        {
            "status": "success" | "error",
            "profile_hash": str,
            "cpu": str,
            "ram": str,
            "gpu": str,
            "vram": str,
            "best_model": str,
            "best_speed": str,
            "model_count": int,
            "local_capable": int,
            "timestamp": str
        }
    """
    try:
        registry = get_ai_capability_registry()
        if override_specs:
            registry.detect(override_specs)
        else:
            registry.detect()

        summary = registry.get_capability_summary()

        return {
            "status": "success",
            **summary
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "suggestion": "请先运行硬件检测或在数据视图中手动输入配置"
        }


def get_ai_capability_report() -> Dict[str, Any]:
    """
    获取本地AI算力能力报告(格式化)

    Returns:
        包含报告文本和详细数据的字典
    """
    try:
        registry = get_ai_capability_registry()
        profile = registry._current_profile

        if profile is None:
            registry.detect()
            profile = registry._current_profile

        if profile is None:
            return {
                "status": "not_detected",
                "report": "尚未进行硬件检测,请先调用 get_local_ai_capability",
                "suggestion": "运行检测或使用 publish_ai_service 发布服务"
            }

        # 生成报告
        report_text = profile.generate_report()

        # 提取兼容模型列表
        compatible = [
            {
                "name": m.name,
                "provider": m.provider,
                "params": m.params,
                "compatibility": m.compatibility.value,
                "speed": m.estimated_speed,
                "vram": m.vram_required_gb,
                "recommended": m.recommended
            }
            for m in profile.compatible_models[:15]
        ]

        return {
            "status": "success",
            "report": report_text,
            "profile_hash": profile.profile_hash,
            "best_model": profile.best_model.name if profile.best_model else None,
            "best_speed": profile.best_model.estimated_speed if profile.best_model else 0,
            "hardware": profile.hardware.to_dict(),
            "compatible_models": compatible,
            "local_capable_count": len([m for m in profile.compatible_models
                                       if m.compatibility != ModelCompatibility.API_ONLY])
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def check_model_compatibility(model_name: str) -> Dict[str, Any]:
    """
    检查本地是否能运行指定模型

    Args:
        model_name: 模型名称 (如 "Llama-2-7B", "GPT-4")

    Returns:
        {
            "status": "success" | "error",
            "model_name": str,
            "can_run": bool,
            "compatibility": str,
            "estimated_speed": int,
            "suggestion": str
        }
    """
    try:
        registry = get_ai_capability_registry()
        can_run, compat, speed = registry.can_run_model(model_name)

        # 生成建议
        if can_run:
            if compat == ModelCompatibility.EXCELLENT:
                suggestion = "运行流畅,推荐使用!"
            elif compat == ModelCompatibility.GOOD:
                suggestion = "运行良好,可正常使用"
            elif compat == ModelCompatibility.MODERATE:
                suggestion = "运行较慢,建议降低批量大小"
            elif compat == ModelCompatibility.SLOW:
                suggestion = "速度较慢,仅适合小规模使用"
            else:
                suggestion = "可运行,但性能有限"
        else:
            if compat == ModelCompatibility.API_ONLY:
                suggestion = "该模型仅支持API调用,请配置API密钥"
            else:
                suggestion = "硬件不足,无法运行该模型"

        return {
            "status": "success",
            "model_name": model_name,
            "can_run": can_run,
            "compatibility": compat.value,
            "estimated_speed": speed,
            "suggestion": suggestion
        }

    except Exception as e:
        return {
            "status": "error",
            "model_name": model_name,
            "error": str(e)
        }


def list_supported_models(
    model_type: Optional[str] = None,
    local_only: bool = False
) -> Dict[str, Any]:
    """
    列出支持的AI模型

    Args:
        model_type: 模型类型过滤 (text_llm/embedding/vision/api_only)
        local_only: 仅返回可本地运行的模型

    Returns:
        模型列表
    """
    try:
        registry = get_ai_capability_registry()

        from business.ai_capability_detector import ModelType

        mtype = None
        if model_type:
            type_map = {
                "text_llm": ModelType.TEXT_LLM,
                "embedding": ModelType.EMBEDDING,
                "vision": ModelType.VISION,
                "multimodal": ModelType.MULTIMODAL,
                "api_only": ModelType.API_ONLY,
            }
            mtype = type_map.get(model_type.lower())

        models = registry._detector.list_models(model_type=mtype, has_local=local_only)

        return {
            "status": "success",
            "count": len(models),
            "models": [
                {
                    "name": m.name,
                    "provider": m.provider,
                    "params": m.params,
                    "vram_required": m.vram_required_gb,
                    "model_type": m.model_type.value,
                    "notes": m.notes
                }
                for m in models
            ]
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def publish_ai_service(
    service_name: str,
    service_type: str = "text_chat",
    price_per_hour: float = 1.0,
    model_name: Optional[str] = None,
    custom_description: Optional[str] = None
) -> Dict[str, Any]:
    """
    发布AI算力服务到DeCommerce市场

    Args:
        service_name: 服务名称
        service_type: 服务类型 (text_chat/code_completion/reasoning等)
        price_per_hour: 每小时价格(元)
        model_name: 指定模型(若不指定则使用最佳推荐)
        custom_description: 自定义描述

    Returns:
        发布结果
    """
    try:
        registry = get_ai_capability_registry()
        registry.detect()

        # 确定使用的模型
        if model_name:
            can_run, compat, speed = registry.can_run_model(model_name)
            if not can_run:
                return {
                    "status": "error",
                    "message": f"本地无法运行模型 {model_name}",
                    "compatibility": compat.value,
                    "suggestion": "请选择其他模型或升级硬件"
                }
            target_model = registry._detector.get_model_info(model_name)
        else:
            # 使用最佳推荐模型
            profile = registry.get_current_profile()
            if profile and profile.best_model:
                target_model = profile.best_model
            else:
                return {
                    "status": "error",
                    "message": "未检测到可用的AI模型",
                    "suggestion": "请确保已安装Ollama并运行模型"
                }

        # 生成服务描述
        summary = registry.get_capability_summary()
        hw = summary

        description_parts = [
            f"AI {service_type.replace('_', ' ')} 服务",
            "",
            "【硬件认证】",
            f"CPU: {hw['cpu']}",
            f"内存: {hw['ram']}",
            f"GPU: {hw['gpu']} ({hw['vram']})",
            "",
            "【模型信息】",
            f"模型: {target_model.name}",
            f"参数量: {target_model.params}",
            f"预估速度: {target_model.estimated_speed} tokens/sec",
            "",
            f"【服务价格】¥{price_per_hour}/小时",
        ]

        if custom_description:
            description_parts.insert(0, custom_description + "\n")
            description_parts.insert(0, "=" * 40)

        description = "\n".join(description_parts)

        # 构建服务列表
        from business.decommerce.ai_capability_registry import AICapability, CapabilityType

        capability_type_map = {
            "text_chat": CapabilityType.TEXT_CHAT,
            "code_completion": CapabilityType.CODE_COMPLETION,
            "code_review": CapabilityType.CODE_REVIEW,
            "reasoning": CapabilityType.REASONING,
            "summarization": CapabilityType.SUMMARIZATION,
            "translation": CapabilityType.TRANSLATION,
        }

        service_capability = AICapability(
            capability_type=capability_type_map.get(service_type, CapabilityType.TEXT_CHAT),
            model_name=target_model.name,
            model_backend="Ollama/Local",
            model_size=target_model.params,
            display_name=service_name,
            description=description,
            avg_latency_ms=1000 // max(1, target_model.estimated_speed // 10),
            max_tokens=4096,
            price_per_1k_tokens=int(price_per_hour * 10),  # 估算
            is_available=True,
        )

        # 注册服务
        svc_registry = registry  # 复用registry
        svc_registry._current_profile  # 确保有profile

        # 构建市场列表数据
        listing = {
            "id": f"ai_svc_{summary['profile_hash'][:8]}_{int(datetime.now().timestamp())}",
            "type": "ai_capability_service",
            "name": service_name,
            "service_type": service_type,
            "capability": service_capability.to_dict(),
            "hardware_certified": {
                "cpu": hw["cpu"],
                "ram": hw["ram"],
                "gpu": hw["gpu"],
                "vram": hw["vram"],
                "profile_hash": summary["profile_hash"],
            },
            "model": {
                "name": target_model.name,
                "params": target_model.params,
                "speed": target_model.estimated_speed,
            },
            "price_per_hour": price_per_hour,
            "timestamp": datetime.now().isoformat(),
        }

        return {
            "status": "success",
            "message": "服务发布成功",
            "listing": listing,
            "description": description,
            "profile_hash": summary["profile_hash"],
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"发布失败: {str(e)}",
            "error": str(e)
        }


def compare_with_seller(
    seller_profile_hash: str,
    comparison_model: Optional[str] = None
) -> Dict[str, Any]:
    """
    比较买家本地算力与卖家算力(用于买家决策)

    Args:
        seller_profile_hash: 卖家的硬件指纹
        comparison_model: 比较的模型名称

    Returns:
        比较结果
    """
    try:
        buyer_registry = get_ai_capability_registry()
        buyer_registry.detect()

        buyer_profile = buyer_registry.get_current_profile()
        if not buyer_profile:
            return {
                "status": "error",
                "message": "无法获取买家硬件配置"
            }

        # 尝试加载卖家profile
        seller_profile = None
        try:
            seller_profile = buyer_registry.load_profile(seller_profile_hash)
        except Exception:
            pass

        if not seller_profile:
            return {
                "status": "partial",
                "message": "无法获取卖家详细配置,仅显示买家能力",
                "buyer_capability": buyer_registry.get_capability_summary(),
                "suggestion": "卖家配置不可用,请直接联系卖家了解详情"
            }

        # 对比分析
        buyer_hw = buyer_profile.hardware
        seller_hw = seller_profile.hardware

        comparison = {
            "buyer": {
                "cpu": buyer_hw.cpu_model,
                "cpu_cores": buyer_hw.cpu_cores,
                "ram_gb": buyer_hw.ram_total_gb,
                "gpu": buyer_hw.gpu_renderer,
                "vram_gb": buyer_hw.gpu_vram_gb,
                "has_gpu": buyer_hw.has_gpu,
            },
            "seller": {
                "cpu": seller_hw.cpu_model,
                "cpu_cores": seller_hw.cpu_cores,
                "ram_gb": seller_hw.ram_total_gb,
                "gpu": seller_hw.gpu_renderer,
                "vram_gb": seller_hw.gpu_vram_gb,
                "has_gpu": seller_hw.has_gpu,
            },
            "recommendation": "",
            "savings": {},
        }

        # 计算节省成本(假设卖家价格)
        if buyer_hw.has_gpu and buyer_hw.gpu_vram_gb >= seller_hw.gpu_vram_gb:
            comparison["recommendation"] = "您本地运行更划算,建议自己跑"
            comparison["savings"] = {
                "can_run_locally": True,
                "local_speed": buyer_profile.best_model.estimated_speed if buyer_profile.best_model else 0,
                "local_vram": buyer_hw.gpu_vram_gb,
            }
        else:
            comparison["recommendation"] = "卖家硬件更强,购买服务更划算"
            comparison["savings"] = {
                "can_run_locally": buyer_hw.has_gpu,
                "local_speed": buyer_profile.best_model.estimated_speed if buyer_profile.best_model else 0,
                "local_vram": buyer_hw.gpu_vram_gb,
                "seller_speed": seller_profile.best_model.estimated_speed if seller_profile.best_model else 0,
                "seller_vram": seller_hw.gpu_vram_gb,
            }

        # 特定模型比较
        if comparison_model:
            buyer_can, buyer_compat, buyer_speed = buyer_registry.can_run_model(comparison_model)
            seller_can, seller_compat, seller_speed = buyer_registry.can_run_model(comparison_model)

            comparison["model_comparison"] = {
                "model_name": comparison_model,
                "buyer": {
                    "can_run": buyer_can,
                    "compatibility": buyer_compat.value,
                    "speed": buyer_speed,
                },
                "seller": {
                    "can_run": seller_can,
                    "compatibility": seller_compat.value,
                    "speed": seller_speed,
                }
            }

        return {
            "status": "success",
            **comparison
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def generate_service_description_for_listing(
    service_name: str,
    price_per_hour: float,
    include_hardware: bool = True
) -> str:
    """
    为商品列表生成AI服务描述

    Args:
        service_name: 服务名称
        price_per_hour: 每小时价格
        include_hardware: 是否包含硬件信息

    Returns:
        格式化描述文本
    """
    try:
        registry = get_ai_capability_registry()
        return registry.generate_service_description(service_name, price_per_hour)
    except Exception:
        return f"{service_name}\n价格: ¥{price_per_hour}/小时"


# =============================================================================
# 辅助函数
# =============================================================================

def run_hardware_detection(
    cpu_cores: Optional[int] = None,
    cpu_model: Optional[str] = None,
    ram_gb: Optional[float] = None,
    gpu_model: Optional[str] = None,
    gpu_vram_gb: Optional[float] = None,
    has_gpu: Optional[bool] = None
) -> Dict[str, Any]:
    """
    使用指定参数运行硬件检测

    所有参数都是可选的,不提供的参数将自动检测
    """
    overrides = {}
    if cpu_cores is not None:
        overrides["cpu_cores"] = cpu_cores
    if cpu_model is not None:
        overrides["cpu_model"] = cpu_model
    if ram_gb is not None:
        overrides["ram_total_gb"] = ram_gb
    if gpu_model is not None:
        overrides["gpu_renderer"] = gpu_model
    if gpu_vram_gb is not None:
        overrides["gpu_vram_gb"] = gpu_vram_gb
    if has_gpu is not None:
        overrides["has_gpu"] = has_gpu

    return get_local_ai_capability(overrides if overrides else None)


# =============================================================================
# 工具注册表 (供Hermes系统调用)
# =============================================================================

HERMES_TOOLS = {
    "get_local_ai_capability": {
        "name": "get_local_ai_capability",
        "description": "获取本地AI算力能力,包括CPU/RAM/GPU配置和推荐的AI模型",
        "parameters": {
            "type": "object",
            "properties": {
                "override_specs": {
                    "type": "object",
                    "description": "可选的硬件规格覆盖值",
                    "properties": {
                        "cpu_cores": {"type": "number"},
                        "ram_total_gb": {"type": "number"},
                        "gpu_vram_gb": {"type": "number"},
                        "has_gpu": {"type": "boolean"}
                    }
                }
            }
        },
        "returns": "本地AI算力能力摘要",
        "category": "ai_capability"
    },

    "get_ai_capability_report": {
        "name": "get_ai_capability_report",
        "description": "获取详细的AI算力能力报告,包含硬件信息和兼容模型列表",
        "parameters": {"type": "object", "properties": {}},
        "returns": "详细的能力报告",
        "category": "ai_capability"
    },

    "check_model_compatibility": {
        "name": "check_model_compatibility",
        "description": "检查本地硬件是否能运行指定的AI模型",
        "parameters": {
            "type": "object",
            "required": ["model_name"],
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": "模型名称,如 Llama-2-7B, GPT-4, Qwen-1.5-14B"
                }
            }
        },
        "returns": "兼容性检查结果",
        "category": "ai_capability"
    },

    "publish_ai_service": {
        "name": "publish_ai_service",
        "description": "将本地AI算力发布为DeCommerce去中心化电商服务",
        "parameters": {
            "type": "object",
            "required": ["service_name", "price_per_hour"],
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"},
                "service_type": {
                    "type": "string",
                    "enum": ["text_chat", "code_completion", "code_review", "reasoning"],
                    "description": "服务类型"
                },
                "price_per_hour": {"type": "number", "description": "每小时价格(元)"},
                "model_name": {"type": "string", "description": "指定使用的模型(可选)"}
            }
        },
        "returns": "发布结果和服务列表数据",
        "category": "decommerce"
    },

    "compare_with_seller": {
        "name": "compare_with_seller",
        "description": "比较买家本地算力与卖家硬件配置,辅助购买决策",
        "parameters": {
            "type": "object",
            "required": ["seller_profile_hash"],
            "properties": {
                "seller_profile_hash": {"type": "string", "description": "卖家的硬件指纹"},
                "comparison_model": {"type": "string", "description": "要比较的模型名称(可选)"}
            }
        },
        "returns": "算力对比结果和建议",
        "category": "decommerce"
    },
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """获取所有工具的schema定义"""
    return list(HERMES_TOOLS.values())


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    """根据名称获取工具定义"""
    return HERMES_TOOLS.get(name)


async def execute_tool(name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行指定的工具

    Args:
        name: 工具名称
        parameters: 工具参数

    Returns:
        工具执行结果
    """
    tool_map = {
        "get_local_ai_capability": lambda p: get_local_ai_capability(p.get("override_specs")),
        "get_ai_capability_report": lambda p: get_ai_capability_report(),
        "check_model_compatibility": lambda p: check_model_compatibility(p.get("model_name", "")),
        "publish_ai_service": lambda p: publish_ai_service(
            service_name=p.get("service_name", ""),
            service_type=p.get("service_type", "text_chat"),
            price_per_hour=p.get("price_per_hour", 1.0),
            model_name=p.get("model_name")
        ),
        "compare_with_seller": lambda p: compare_with_seller(
            seller_profile_hash=p.get("seller_profile_hash", ""),
            comparison_model=p.get("comparison_model")
        ),
    }

    tool = tool_map.get(name)
    if tool:
        return tool(parameters)

    return {
        "status": "error",
        "message": f"Unknown tool: {name}",
        "available_tools": list(HERMES_TOOLS.keys())
    }
