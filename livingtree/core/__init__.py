"""Core layer — infrastructure, registries, and system orchestration for LivingTree."""
from .entity_registry import EntityRegistry, EntityEntry, ENTITY_REGISTRY, get_entity_registry
from .unified_registry import *
from .async_disk import *
from .file_resolver import *
from .task_guard import *
from .system_orchestrator import SystemOrchestrator, SystemStatus, get_orchestrator
from .adaptive_pipeline import AdaptivePipeline, PipelineContext, PipelineStep, RequestType, ProtocolMode
from .hardware_accelerator import HardwareAccelerator, HardwareInfo, get_accelerator
from .memory_optimizer import MemoryOptimizer, MemoryStats, get_memory_optimizer

__all__ = [
    "EntityRegistry", "EntityEntry", "ENTITY_REGISTRY", "get_entity_registry",
    "SystemOrchestrator", "SystemStatus", "get_orchestrator",
    "AdaptivePipeline", "PipelineContext", "PipelineStep", "RequestType", "ProtocolMode",
    "HardwareAccelerator", "HardwareInfo", "get_accelerator",
    "MemoryOptimizer", "MemoryStats", "get_memory_optimizer",
]
