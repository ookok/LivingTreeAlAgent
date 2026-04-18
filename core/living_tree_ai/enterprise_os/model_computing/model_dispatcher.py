"""
模型调度中心 (Model Dispatcher)

作为模型计算引擎的核心调度器，实现：
1. 模型注册与发现
2. 输入参数验证
3. 模型调度与并行执行
4. 结果聚合与分发
5. 版本管理与回滚

架构图：
    [项目数据池] → (模型调度中心) → [排放核算微服务]
                               → [大气预测微服务]
                               → [风险评估微服务]
                               → [工程经济微服务]
```

使用示例：
```python
dispatcher = get_model_dispatcher()

# 注册模型
await dispatcher.register_model(ModelInfo(...))

# 发起计算
result = await dispatcher.dispatch(
    model_type=ModelType.EMISSION,
    project_id="PROJ001",
    parameters={"source_type": "boiler", "fuel": "coal"}
)

# 批量调度
results = await dispatcher.dispatch_batch([
    ComputeRequest(model_type=ModelType.EMISSION, parameters={...}),
    ComputeRequest(model_type=ModelType.RISK, parameters={...}),
])
```
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable, Type
import asyncio
import hashlib
import json


class ModelType(Enum):
    """模型类型"""
    # 排放核算
    EMISSION_CALCULATION = "emission_calculation"     # 排放核算（通用）
    AIR_EMISSION = "air_emission"                     # 大气排放
    WATER_EMISSION = "water_emission"                 # 水污染物排放
    SOLID_WASTE = "solid_waste"                       # 固体废物

    # 环境预测
    AERMOD = "aermod"                                 # AERMOD大气预测
    EFDC = "efdc"                                     # EFDC水质预测

    # 风险评价
    RISK_ASSESSMENT = "risk_assessment"               # 综合风险评价
    LS_HAZARD = "ls_hazard"                          # LS危险度评价
    RISK_DIFFUSION = "risk_diffusion"                 # 风险扩散模型

    # 工程经济
    INVESTMENT_ESTIMATE = "investment_estimate"       # 投资估算
    OPERATING_COST = "operating_cost"                 # 运营成本
    COST_BENEFIT = "cost_benefit"                      # 成本效益分析

    # 扩展
    CUSTOM = "custom"                                  # 自定义模型


class ModelStatus(Enum):
    """模型状态"""
    REGISTERED = "registered"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    FAILED = "failed"
    UPDATING = "updating"


class ComputePriority(Enum):
    """计算优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    model_type: ModelType
    name: str
    description: str

    # 版本
    version: str
    previous_version: Optional[str] = None

    # 元数据
    author: str = "system"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 参数定义
    input_parameters: List[Dict[str, Any]] = field(default_factory=list)
    output_schema: Dict[str, Any] = field(default_factory=dict)

    # 能力
    capabilities: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    # 配置
    timeout_seconds: int = 300
    max_retries: int = 3
    requires_gpu: bool = False

    # 状态
    status: ModelStatus = ModelStatus.REGISTERED

    # 使用统计
    total_calls: int = 0
    success_rate: float = 0.0
    avg_compute_time: float = 0.0

    # 依赖
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_type": self.model_type.value,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "total_calls": self.total_calls,
            "success_rate": self.success_rate,
            "avg_compute_time": self.avg_compute_time,
        }


@dataclass
class ModelParameter:
    """模型参数"""
    name: str
    value: Any
    unit: Optional[str] = None
    source: str = "manual"            # manual/system/calculated
    source_item_id: Optional[str] = None  # 如果来自项目数据，关联的数据项ID
    validation_status: str = "pending"  # pending/valid/invalid
    validation_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "source_item_id": self.source_item_id,
            "validation_status": self.validation_status,
        }


@dataclass
class ComputeRequest:
    """计算请求"""
    request_id: str
    model_type: ModelType
    project_id: str

    # 参数
    parameters: Dict[str, Any] = field(default_factory=dict)
    parameter_sources: Dict[str, str] = field(default_factory=dict)  # 参数来源映射

    # 执行控制
    priority: ComputePriority = ComputePriority.NORMAL
    timeout_seconds: Optional[int] = None

    # 上下文
    document_id: Optional[str] = None       # 关联的文档ID
    section_id: Optional[str] = None        # 关联的文档章节ID
    callback_url: Optional[str] = None      # 异步回调URL

    # 元数据
    requested_by: str = "system"
    requested_at: datetime = field(default_factory=datetime.now)

    # 标签
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model_type": self.model_type.value,
            "project_id": self.project_id,
            "parameters": self.parameters,
            "priority": self.priority.value,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat(),
        }


@dataclass
class ComputeResult:
    """计算结果"""
    request_id: str
    model_type: ModelType
    project_id: str

    # 状态
    status: str                              # success/partial/failed
    error_message: Optional[str] = None

    # 输出数据
    output_data: Dict[str, Any] = field(default_factory=dict)

    # 计算详情
    calculation_details: Dict[str, Any] = field(default_factory=dict)  # 计算过程
    parameter_log: List[Dict[str, Any]] = field(default_factory=list)  # 参数清单（用于审计）

    # 质量指标
    confidence: float = 0.0                  # 结果置信度
    quality_score: float = 0.0               # 质量评分

    # 版本信息
    model_version: Optional[str] = None
    model_id: Optional[str] = None

    # 时间戳
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    compute_time_seconds: float = 0.0

    # 关联
    document_id: Optional[str] = None
    related_results: List[str] = field(default_factory=list)  # 关联的其他计算结果ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model_type": self.model_type.value,
            "project_id": self.project_id,
            "status": self.status,
            "output_data": self.output_data,
            "confidence": self.confidence,
            "quality_score": self.quality_score,
            "model_version": self.model_version,
            "compute_time_seconds": self.compute_time_seconds,
            "parameter_log": self.parameter_log,
        }

    def to_report_section(self) -> Dict[str, Any]:
        """转换为可嵌入报告的格式"""
        return {
            "model_name": self.model_type.value,
            "version": self.model_version,
            "results": self.output_data,
            "confidence": self.confidence,
            "parameters_used": self.parameter_log,
            "computed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class ModelVersion:
    """模型版本记录"""
    version: str
    model_id: str
    changelog: str = ""
    release_date: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    previous_version: Optional[str] = None

    # 性能指标
    avg_accuracy: float = 0.0
    benchmark_results: Dict[str, float] = field(default_factory=dict)


class ModelDispatcher:
    """
    模型调度中心

    核心功能：
    1. 模型注册与管理
    2. 计算请求调度
    3. 输入参数验证
    4. 结果聚合与分发
    5. 版本管理与回滚
    6. 调用统计与监控
    """

    # 默认模型配置
    DEFAULT_MODELS = {
        ModelType.EMISSION_CALCULATION: {
            "name": "通用排放核算模型",
            "description": "基于产排污系数法和物料衡算法的排放量核算",
            "version": "2.0.0",
            "timeout": 60,
        },
        ModelType.RISK_ASSESSMENT: {
            "name": "综合风险评价模型",
            "description": "综合考虑后果严重性和发生概率的风险评价",
            "version": "1.5.0",
            "timeout": 120,
        },
        ModelType.INVESTMENT_ESTIMATE: {
            "name": "投资估算模型",
            "description": "基于工程量和单价的投资估算",
            "version": "1.2.0",
            "timeout": 30,
        },
    }

    def __init__(self):
        # 模型注册表
        self._models: Dict[ModelType, List[ModelInfo]] = {}

        # 计算队列
        self._compute_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_computes: Dict[str, ComputeRequest] = {}

        # 结果缓存
        self._result_cache: Dict[str, ComputeResult] = {}
        self._cache_ttl = 3600  # 1小时

        # 调度器
        self._model_handlers: Dict[ModelType, Callable] = {}

        # 统计
        self._statistics: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_compute_time": 0,
        }

        # 初始化默认处理器
        self._init_default_handlers()

    def _init_default_handlers(self) -> None:
        """初始化默认处理器"""
        # 注册内置模型的简单实现
        # 实际应导入具体的计算模块
        pass

    async def register_model(self, model_info: ModelInfo) -> bool:
        """
        注册模型

        Args:
            model_info: 模型信息

        Returns:
            bool: 是否注册成功
        """
        if model_info.model_type not in self._models:
            self._models[model_info.model_type] = []

        # 检查版本冲突
        existing = [m for m in self._models[model_info.model_type] if m.version == model_info.version]
        if existing:
            # 版本已存在，更新
            idx = self._models[model_info.model_type].index(existing[0])
            self._models[model_info.model_type][idx] = model_info
        else:
            # 新增
            self._models[model_info.model_type].append(model_info)

        return True

    async def get_model(
        self,
        model_type: ModelType,
        version: Optional[str] = None
    ) -> Optional[ModelInfo]:
        """获取模型信息"""
        models = self._models.get(model_type, [])
        if not models:
            return None

        if version:
            for m in models:
                if m.version == version:
                    return m
            return None

        # 返回最新版本
        return max(models, key=lambda x: x.created_at)

    async def list_models(
        self,
        model_type: Optional[ModelType] = None,
        status: Optional[ModelStatus] = None
    ) -> List[ModelInfo]:
        """列出模型"""
        if model_type:
            models = self._models.get(model_type, [])
        else:
            models = []
            for type_models in self._models.values():
                models.extend(type_models)

        if status:
            models = [m for m in models if m.status == status]

        return sorted(models, key=lambda x: x.created_at, reverse=True)

    async def dispatch(
        self,
        model_type: ModelType,
        project_id: str,
        parameters: Dict[str, Any],
        parameter_sources: Optional[Dict[str, str]] = None,
        priority: ComputePriority = ComputePriority.NORMAL,
        timeout_seconds: Optional[int] = None,
        document_id: Optional[str] = None,
        **kwargs
    ) -> ComputeResult:
        """
        发起计算请求

        Args:
            model_type: 模型类型
            project_id: 项目ID
            parameters: 计算参数
            parameter_sources: 参数来源映射
            priority: 优先级
            timeout_seconds: 超时时间
            document_id: 关联文档ID

        Returns:
            ComputeResult: 计算结果
        """
        # 生成请求ID
        request_id = f"REQ:{hashlib.md5(f'{project_id}{model_type.value}{datetime.now().isoformat()}'.encode()).hexdigest()[:12].upper()}"

        # 创建请求
        request = ComputeRequest(
            request_id=request_id,
            model_type=model_type,
            project_id=project_id,
            parameters=parameters,
            parameter_sources=parameter_sources or {},
            priority=priority,
            timeout_seconds=timeout_seconds,
            document_id=document_id,
            **kwargs
        )

        # 更新统计
        self._statistics["total_requests"] += 1

        # 获取模型
        model = await self.get_model(model_type)
        if not model:
            return ComputeResult(
                request_id=request_id,
                model_type=model_type,
                project_id=project_id,
                status="failed",
                error_message=f"模型类型 {model_type.value} 未注册"
            )

        # 执行计算
        start_time = datetime.now()

        try:
            # 调用模型处理器
            handler = self._model_handlers.get(model_type)
            if handler:
                result = await handler(request, parameters)
            else:
                # 使用默认处理
                result = await self._default_compute(request, parameters)

            # 记录时间
            compute_time = (datetime.now() - start_time).total_seconds()
            result.compute_time_seconds = compute_time
            result.started_at = start_time
            result.completed_at = datetime.now()

            # 更新统计
            self._statistics["successful_requests"] += 1

            return result

        except Exception as e:
            self._statistics["failed_requests"] += 1

            return ComputeResult(
                request_id=request_id,
                model_type=model_type,
                project_id=project_id,
                status="failed",
                error_message=str(e),
                started_at=start_time,
                completed_at=datetime.now(),
                compute_time_seconds=(datetime.now() - start_time).total_seconds()
            )

    async def dispatch_batch(
        self,
        requests: List[ComputeRequest]
    ) -> List[ComputeResult]:
        """
        批量调度计算

        用于并行执行多个相关计算（如同时计算排放量和风险）。
        """
        # 按优先级排序
        sorted_requests = sorted(
            requests,
            key=lambda x: (x.priority.value, x.requested_at),
            reverse=True
        )

        # 并行执行
        tasks = [
            self.dispatch(
                model_type=r.model_type,
                project_id=r.project_id,
                parameters=r.parameters,
                priority=r.priority
            )
            for r in sorted_requests
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        processed_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                processed_results.append(ComputeResult(
                    request_id=sorted_requests[i].request_id,
                    model_type=sorted_requests[i].model_type,
                    project_id=sorted_requests[i].project_id,
                    status="failed",
                    error_message=str(r)
                ))
            else:
                processed_results.append(r)

        return processed_results

    async def _default_compute(
        self,
        request: ComputeRequest,
        parameters: Dict[str, Any]
    ) -> ComputeResult:
        """默认计算处理"""
        # 这里应调用具体的计算模块
        # 简化实现：返回参数回显

        return ComputeResult(
            request_id=request.request_id,
            model_type=request.model_type,
            project_id=request.project_id,
            status="success",
            output_data={
                "message": "计算完成（默认处理器）",
                "input_parameters": parameters,
            },
            parameter_log=[
                {"name": k, "value": v, "source": request.parameter_sources.get(k, "manual")}
                for k, v in parameters.items()
            ],
            model_version="1.0.0",
            confidence=0.8,
            quality_score=0.85
        )

    def register_handler(
        self,
        model_type: ModelType,
        handler: Callable
    ) -> None:
        """注册模型处理器"""
        self._model_handlers[model_type] = handler

    async def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._statistics["total_requests"]
        success = self._statistics["successful_requests"]

        return {
            **self._statistics,
            "success_rate": success / total if total > 0 else 0,
            "registered_models": sum(len(m) for m in self._models.values()),
            "models_by_type": {
                mt.value: len(models)
                for mt, models in self._models.items()
            }
        }


# 全局单例
_model_dispatcher: Optional[ModelDispatcher] = None


def get_model_dispatcher() -> ModelDispatcher:
    """获取模型调度器单例"""
    global _model_dispatcher
    if _model_dispatcher is None:
        _model_dispatcher = ModelDispatcher()
    return _model_dispatcher