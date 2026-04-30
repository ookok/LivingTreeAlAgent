# optimal_config.py - 计算最优配置
# 基于 nanochat "compute-optimal-config" 理念：

"""
LivingTreeAI 极简配置系统
=========================

核心理念：单参数调优 - 只需传入任务复杂度(depth)，其他所有参数自动计算

使用示例:
    from business.optimal_config import compute_optimal_config, get_depth
    
    # 简单任务
    config = compute_optimal_config(depth=1)
    
    # 复杂任务
    config = compute_optimal_config(depth=8)
    
    # 自动检测
    config = compute_optimal_config(depth="auto")
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
import math
import os


# ── 基础常量 (Chinchilla 缩放法则推导) ────────────────────────────────

class BaseConfig:
    """基础配置常量"""
    # 时间基准 (秒)
    BASE_TIMEOUT = 30.0
    BASE_RETRY_DELAY = 1.0
    BASE_HEARTBEAT = 10.0
    BASE_POLLING = 5.0
    
    # 资源基准
    BASE_MAX_TOKENS = 2048
    BASE_MAX_CONTEXT = 4096
    BASE_BATCH_SIZE = 32
    
    # 计算基准
    BASE_WIDTH = 64
    BASE_HEADS = 4
    BASE_LR = 0.0003


@dataclass
class OptimalConfig:
    """计算最优配置"""
    # 任务参数
    depth: int
    
    # 网络超时 (秒)
    timeout: float
    long_timeout: float
    quick_timeout: float
    retry_delay: float
    
    # 重试配置
    max_retries: int
    exponential_base: float
    
    # 延迟配置 (秒)
    polling_short: float
    polling_medium: float
    polling_long: float
    wait_short: float
    wait_long: float
    
    # 资源限制
    max_tokens: int
    max_context: int
    max_workers: int
    batch_size: int
    
    # LLM 参数
    llm_temperature: float
    llm_top_p: float
    
    # Agent 参数
    agent_init_timeout: float
    agent_max_iterations: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'depth': self.depth,
            'timeout': self.timeout,
            'long_timeout': self.long_timeout,
            'quick_timeout': self.quick_timeout,
            'retry_delay': self.retry_delay,
            'max_retries': self.max_retries,
            'exponential_base': self.exponential_base,
            'polling_short': self.polling_short,
            'polling_medium': self.polling_medium,
            'polling_long': self.polling_long,
            'wait_short': self.wait_short,
            'wait_long': self.wait_long,
            'max_tokens': self.max_tokens,
            'max_context': self.max_context,
            'max_workers': self.max_workers,
            'batch_size': self.batch_size,
            'llm_temperature': self.llm_temperature,
            'llm_top_p': self.llm_top_p,
            'agent_init_timeout': self.agent_init_timeout,
            'agent_max_iterations': self.agent_max_iterations,
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """字典式访问"""
        return self.to_dict().get(key, default)


def compute_optimal_config(depth: int = 3) -> OptimalConfig:
    """
    根据任务复杂度自动计算最优配置
    
    Args:
        depth: 任务复杂度 (1-10)
            - 1-2: 简单任务 (查询、简单生成)
            - 3-4: 普通任务 (代码补全、中等分析)
            - 5-6: 复杂任务 (多步骤推理、深度搜索)
            - 7-8: 极复杂任务 (复杂规划、大规模重构)
            - 9-10: 极限任务 (全自动驾驶)
    
    Returns:
        OptimalConfig: 计算得到的最优配置
    
    数学推导:
        - timeout ∝ depth^0.7 (对数增长，避免无限膨胀)
        - max_retries ∝ log2(depth) (复杂度增加，重试更重要)
        - max_tokens ∝ depth^1.5 (指数增长支持复杂任务)
        - max_workers ∝ sqrt(depth) (资源有限，平方根增长)
    """
    # 边界处理
    depth = max(1, min(10, depth))
    
    # 计算缩放因子
    depth_factor = depth / 5.0  # 归一化到 [0.2, 2.0]
    log_depth = math.log2(max(2, depth))  # log2(depth)
    sqrt_depth = math.sqrt(depth)  # sqrt(depth)
    
    # ── 网络超时 ───────────────────────────────────────────
    timeout = BaseConfig.BASE_TIMEOUT * (1 + 0.3 * math.pow(depth_factor, 0.7))
    long_timeout = timeout * 2
    quick_timeout = timeout * 0.2
    retry_delay = BaseConfig.BASE_RETRY_DELAY * math.pow(depth_factor, 0.5)
    
    # ── 重试配置 ───────────────────────────────────────────
    max_retries = max(1, min(10, 2 + int(log_depth)))
    exponential_base = 1.5 + 0.1 * depth
    
    # ── 轮询延迟 ───────────────────────────────────────────
    polling_short = 0.05 * sqrt_depth  # 0.05 - 0.16
    polling_medium = 0.2 * sqrt_depth   # 0.2 - 0.63
    polling_long = 1.0 * depth_factor   # 0.2 - 2.0
    wait_short = 0.5 * sqrt_depth       # 0.5 - 1.58
    wait_long = 5.0 * depth_factor      # 1.0 - 10.0
    
    # ── 资源限制 ───────────────────────────────────────────
    max_tokens = int(BaseConfig.BASE_MAX_TOKENS * math.pow(depth_factor, 1.5))
    max_context = int(BaseConfig.BASE_MAX_CONTEXT * math.pow(depth_factor, 1.3))
    max_workers = max(1, min(8, int(2 * sqrt_depth)))
    batch_size = int(BaseConfig.BASE_BATCH_SIZE * sqrt_depth)
    
    # ── LLM 参数 ───────────────────────────────────────────
    # 复杂度越高，温度略增 (保持创造性但不过度随机)
    llm_temperature = min(1.0, 0.5 + 0.05 * depth)
    # Top-p 随复杂度降低 (更集中于高概率token)
    llm_top_p = max(0.7, 0.95 - 0.02 * depth)
    
    # ── Agent 参数 ───────────────────────────────────────────
    agent_init_timeout = 5.0 * sqrt_depth
    agent_max_iterations = max(10, 30 * depth)
    
    return OptimalConfig(
        depth=depth,
        timeout=round(timeout, 2),
        long_timeout=round(long_timeout, 2),
        quick_timeout=round(quick_timeout, 2),
        retry_delay=round(retry_delay, 2),
        max_retries=max_retries,
        exponential_base=round(exponential_base, 2),
        polling_short=round(polling_short, 3),
        polling_medium=round(polling_medium, 3),
        polling_long=round(polling_long, 2),
        wait_short=round(wait_short, 2),
        wait_long=round(wait_long, 2),
        max_tokens=max_tokens,
        max_context=max_context,
        max_workers=max_workers,
        batch_size=batch_size,
        llm_temperature=round(llm_temperature, 2),
        llm_top_p=round(llm_top_p, 2),
        agent_init_timeout=round(agent_init_timeout, 2),
        agent_max_iterations=agent_max_iterations,
    )


def get_depth_from_task(task_type: str) -> int:
    """
    根据任务类型自动推断复杂度
    
    Args:
        task_type: 任务类型描述
    
    Returns:
        int: 推荐 depth (1-10)
    """
    task_depth_map = {
        # 极简单 (1-2)
        'ping': 1, 'health_check': 1, 'status': 1,
        'list': 2, 'query': 2, 'search': 2,
        
        # 简单 (2-3)
        'read': 2, 'get': 2, 'find': 2,
        'simple_generate': 3, 'complete': 3,
        
        # 普通 (3-4)
        'write': 3, 'create': 3, 'update': 3,
        'analyze': 4, 'compare': 4,
        'code_complete': 3, 'code_fix': 3,
        
        # 中等 (4-5)
        'refactor': 5, 'optimize': 5,
        'deep_analyze': 5, 'review': 5,
        
        # 复杂 (6-7)
        'generate': 6, 'build': 6,
        'complex_refactor': 7, 'migrate': 7,
        'architect': 6, 'design': 6,
        
        # 极复杂 (8-9)
        'auto_complete': 8, 'auto_fix': 8,
        'evolve': 8, 'self_improve': 9,
        
        # 极限 (10)
        'autonomous': 10, 'full_auto': 10,
    }
    
    task_lower = task_type.lower()
    
    # 精确匹配
    if task_lower in task_depth_map:
        return task_depth_map[task_lower]
    
    # 模糊匹配
    for key, depth in task_depth_map.items():
        if key in task_lower or task_lower in key:
            return depth
    
    # 默认值
    return 3


def compute_optimal_config_for_task(task_type: str) -> OptimalConfig:
    """
    根据任务类型自动计算最优配置
    
    Args:
        task_type: 任务类型描述
    
    Returns:
        OptimalConfig: 计算得到的最优配置
    """
    depth = get_depth_from_task(task_type)
    return compute_optimal_config(depth)


# ── 预设配置 ────────────────────────────────────────────────────────

PRESETS = {
    'minimal': compute_optimal_config(1),
    'light': compute_optimal_config(2),
    'normal': compute_optimal_config(3),
    'medium': compute_optimal_config(5),
    'heavy': compute_optimal_config(7),
    'extreme': compute_optimal_config(10),
}


def get_preset(name: str) -> Optional[OptimalConfig]:
    """
    获取预设配置
    
    Args:
        name: 预设名称 (minimal/light/normal/medium/heavy/extreme)
    
    Returns:
        OptimalConfig 或 None
    """
    return PRESETS.get(name.lower())


# ── 便捷函数 ────────────────────────────────────────────────────────

def quick_config() -> OptimalConfig:
    """快速任务配置 (depth=1)"""
    return compute_optimal_config(1)


def normal_config() -> OptimalConfig:
    """普通任务配置 (depth=3)"""
    return compute_optimal_config(3)


def heavy_config() -> OptimalConfig:
    """重型任务配置 (depth=7)"""
    return compute_optimal_config(7)


# ── 与 unified_config 集成 ─────────────────────────────────────────

def sync_to_unified_config(depth: int = 3) -> None:
    """
    将计算最优配置同步到 UnifiedConfig
    
    Args:
        depth: 任务复杂度
    """
    try:
        from business.config import get_unified_config
        
        config = compute_optimal_config(depth)
        cfg = get_unified_config()
        
        # 同步超时
        cfg.set('timeouts.default', config.timeout)
        cfg.set('timeouts.long', config.long_timeout)
        cfg.set('timeouts.quick', config.quick_timeout)
        
        # 同步重试
        cfg.set('retries.default', config.max_retries)
        
        # 同步延迟
        cfg.set('delays.polling_short', config.polling_short)
        cfg.set('delays.polling_medium', config.polling_medium)
        cfg.set('delays.polling_long', config.polling_long)
        
        # 同步资源
        cfg.set('limits.max_tokens', config.max_tokens)
        cfg.set('limits.max_context', config.max_context)
        
        # 同步LLM
        cfg.set('llm.temperature', config.llm_temperature)
        cfg.set('llm.top_p', config.llm_top_p)
        
    except ImportError:
        pass  # UnifiedConfig 未安装


# ── 导出 ────────────────────────────────────────────────────────────

__all__ = [
    'OptimalConfig', 'compute_optimal_config', 'get_depth_from_task',
    'compute_optimal_config_for_task', 'get_preset',
    'quick_config', 'normal_config', 'heavy_config',
    'sync_to_unified_config', 'PRESETS',
]
