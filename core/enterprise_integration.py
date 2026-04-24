"""
Phase 5: 企业级应用场景集成
============================

整合 Phase 1-4 的能力，为企业提供开箱即用的解决方案。

核心功能:
- EnterpriseScenarioAdapter - 企业场景适配器
- IndustryTemplateLibrary - 行业模板库
- WorkflowOrchestrator - 工作流编排器
- BusinessMetricsMonitor - 业务指标监控
- EnterpriseIntegrationHub - 企业集成中心
"""

from __future__ import annotations

import re
import uuid
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from collections import defaultdict
from enum import Enum


# ============================================================================
# 枚举定义
# ============================================================================

class Industry(Enum):
    """行业类型"""
    TECHNOLOGY = "technology"           # 科技/互联网
    FINANCE = "finance"                 # 金融
    HEALTHCARE = "healthcare"           # 医疗健康
    MANUFACTURING = "manufacturing"     # 制造业
    RETAIL = "retail"                   # 零售
    EDUCATION = "education"             # 教育
    GOVERNMENT = "government"           # 政府
    MEDIA = "media"                     # 媒体娱乐
    ENERGY = "energy"                   # 能源
    LOGISTICS = "logistics"             # 物流


class ScenarioType(Enum):
    """场景类型"""
    CUSTOMER_SERVICE = "customer_service"       # 客服
    SALES = "sales"                             # 销售
    MARKETING = "marketing"                     # 营销
    HR = "hr"                                   # 人力资源
    IT_SUPPORT = "it_support"                   # IT支持
    OPERATIONS = "operations"                   # 运营
    COMPLIANCE = "compliance"                    # 合规
    DATA_ANALYSIS = "data_analysis"              # 数据分析
    PROJECT_MANAGEMENT = "project_management"   # 项目管理
    KNOWLEDGE_MANAGEMENT = "knowledge_management"  # 知识管理


class WorkflowStage(Enum):
    """工作流阶段"""
    TRIGGER = "trigger"                 # 触发
    INPUT = "input"                      # 输入
    PROCESS = "process"                  # 处理
    VALIDATE = "validate"                 # 验证
    OUTPUT = "output"                     # 输出
    MONITOR = "monitor"                   # 监控
    NOTIFY = "notify"                    # 通知


class MetricCategory(Enum):
    """指标类别"""
    PERFORMANCE = "performance"         # 性能指标
    BUSINESS = "business"               # 业务指标
    QUALITY = "quality"                  # 质量指标
    ENGAGEMENT = "engagement"            # 参与度指标
    COST = "cost"                        # 成本指标


# ============================================================================
# 数据结构
# ============================================================================

class ScenarioConfig:
    """场景配置"""
    def __init__(
        self,
        scenario_id: str = None,
        name: str = "",
        industry: str = "technology",
        scenario_type: str = "general",
        description: str = "",
        enabled_modules: List[str] = None,
        custom_settings: Dict[str, Any] = None,
        workflows: List[Dict] = None,
        integrations: List[str] = None,
        metrics: Dict[str, Any] = None,
        compliance_rules: List[str] = None,
        is_active: bool = False
    ):
        self.scenario_id = scenario_id or str(uuid.uuid4())
        self.name = name
        self.industry = industry
        self.scenario_type = scenario_type
        self.description = description
        self.enabled_modules = enabled_modules or []
        self.custom_settings = custom_settings or {}
        self.workflows = workflows or []
        self.integrations = integrations or []
        self.metrics = metrics or {}
        self.compliance_rules = compliance_rules or []
        self.is_active = is_active
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()


class WorkflowDefinition:
    """工作流定义"""
    def __init__(
        self,
        workflow_id: str = None,
        name: str = "",
        description: str = "",
        industry: str = "general",
        scenario_type: str = "general",
        stages: List[Dict] = None,
        triggers: List[Dict] = None,
        conditions: List[Dict] = None,
        actions: List[Dict] = None,
        error_handling: Dict = None,
        timeout_seconds: int = 300,
        retry_count: int = 3,
        is_active: bool = True
    ):
        self.workflow_id = workflow_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.industry = industry
        self.scenario_type = scenario_type
        self.stages = stages or []
        self.triggers = triggers or []
        self.conditions = conditions or []
        self.actions = actions or []
        self.error_handling = error_handling or {}
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.is_active = is_active


class WorkflowExecution:
    """工作流执行"""
    def __init__(
        self,
        execution_id: str = None,
        workflow_id: str = "",
        status: str = "pending",  # pending, running, completed, failed, cancelled
        current_stage: str = "trigger",
        context: Dict = None,
        results: Dict = None,
        errors: List[Dict] = None,
        started_at: str = None,
        completed_at: str = None,
        metadata: Dict = None
    ):
        self.execution_id = execution_id or str(uuid.uuid4())
        self.workflow_id = workflow_id
        self.status = status
        self.current_stage = current_stage
        self.context = context or {}
        self.results = results or {}
        self.errors = errors or []
        self.started_at = started_at or datetime.now().isoformat()
        self.completed_at = completed_at
        self.metadata = metadata or {}


class BusinessMetric:
    """业务指标"""
    def __init__(
        self,
        metric_id: str = None,
        name: str = "",
        category: str = "business",
        description: str = "",
        value: float = 0.0,
        previous_value: float = 0.0,
        unit: str = "",
        trend: str = "stable",  # up, down, stable
        target: float = 0.0,
        thresholds: Dict[str, float] = None,  # warning, critical
        history: List[Dict] = None,
        tags: List[str] = None
    ):
        self.metric_id = metric_id or str(uuid.uuid4())
        self.name = name
        self.category = category
        self.description = description
        self.value = value
        self.previous_value = previous_value
        self.unit = unit
        self.trend = trend
        self.target = target
        self.thresholds = thresholds or {}
        self.history = history or []
        self.tags = tags or []
        self.last_updated = datetime.now().isoformat()


# ============================================================================
# 核心类
# ============================================================================

class IndustryTemplateLibrary:
    """行业模板库"""

    # 预定义行业模板
    TEMPLATES = {
        # 科技/互联网
        "technology": {
            "name": "科技/互联网行业",
            "scenarios": [
                {
                    "type": "customer_service",
                    "name": "智能客服",
                    "description": "处理客户咨询、投诉、建议",
                    "workflows": ["auto_response", "ticket_escalation", "sentiment_analysis"],
                    "metrics": ["response_time", "resolution_rate", "csat"]
                },
                {
                    "type": "it_support",
                    "name": "IT支持助手",
                    "description": "故障排查、知识库检索、工单处理",
                    "workflows": ["diagnosis", "solution_lookup", "escalation"],
                    "metrics": ["mtttr", "first_fix_rate", "ticket_volume"]
                },
                {
                    "type": "data_analysis",
                    "name": "数据分析助手",
                    "description": "数据查询、报表生成、趋势分析",
                    "workflows": ["query", "analysis", "visualization"],
                    "metrics": ["query_time", "accuracy", "insights_generated"]
                }
            ],
            "integrations": ["slack", "jira", "confluence", "datadog", "pagerduty"],
            "compliance": ["gdpr", "soc2"]
        },

        # 金融
        "finance": {
            "name": "金融行业",
            "scenarios": [
                {
                    "type": "customer_service",
                    "name": "金融客服",
                    "description": "账户查询、产品咨询、投诉处理",
                    "workflows": ["authentication", "query", "escalation"],
                    "metrics": ["call_volume", "hold_time", "resolution"]
                },
                {
                    "type": "compliance",
                    "name": "合规审查",
                    "description": "文档审查、风控检查、报告生成",
                    "workflows": ["document_check", "rule_match", "report"],
                    "metrics": ["documents_reviewed", "violations_found", "false_positives"]
                },
                {
                    "type": "data_analysis",
                    "name": "风险分析",
                    "description": "交易监控、异常检测、风险评估",
                    "workflows": ["monitor", "detect", "alert"],
                    "metrics": ["alerts_triggered", "detection_rate", "false_alarms"]
                }
            ],
            "integrations": ["salesforce", "tableau", "s3", "snowflake"],
            "compliance": ["sox", "basel_iii", "amla", "kyp"]
        },

        # 医疗健康
        "healthcare": {
            "name": "医疗健康行业",
            "scenarios": [
                {
                    "type": "customer_service",
                    "name": "患者服务",
                    "description": "预约咨询、报告解读、健康管理",
                    "workflows": ["intake", "routing", "follow_up"],
                    "metrics": ["wait_time", "satisfaction", "appointment_show_rate"]
                },
                {
                    "type": "operations",
                    "name": "医院运营",
                    "description": "床位管理、药品库存、人员排班",
                    "workflows": ["check", "optimize", "alert"],
                    "metrics": ["bed_occupancy", "inventory_turnover", "staff_utilization"]
                }
            ],
            "integrations": ["epic", "cerner", "meditech"],
            "compliance": ["hipaa", "hitrust"]
        },

        # 制造业
        "manufacturing": {
            "name": "制造业",
            "scenarios": [
                {
                    "type": "operations",
                    "name": "生产管理",
                    "description": "生产计划、质量控制、设备维护",
                    "workflows": ["planning", "monitoring", "maintenance"],
                    "metrics": ["oee", "defect_rate", "downtime"]
                },
                {
                    "type": "it_support",
                    "name": "工厂IT",
                    "description": "设备故障、网络支持、系统维护",
                    "workflows": ["incident", "resolution", "sla_tracking"],
                    "metrics": ["mtbf", "mttr", "uptime"]
                }
            ],
            "integrations": ["sap", "oracle", "siemens", "ge"],
            "compliance": ["iso_9001", "six_sigma"]
        },

        # 零售
        "retail": {
            "name": "零售行业",
            "scenarios": [
                {
                    "type": "customer_service",
                    "name": "零售客服",
                    "description": "订单查询、退换货、投诉处理",
                    "workflows": ["order_lookup", "return_process", "compensation"],
                    "metrics": ["order_issues", "return_rate", "nps"]
                },
                {
                    "type": "sales",
                    "name": "销售助手",
                    "description": "产品推荐、库存查询、价格报价",
                    "workflows": ["customer_profile", "recommendation", "upsell"],
                    "metrics": ["conversion_rate", "avg_order_value", "basket_size"]
                },
                {
                    "type": "marketing",
                    "name": "营销自动化",
                    "description": "客户分群、活动推广、效果分析",
                    "workflows": ["segment", "campaign", "analyze"],
                    "metrics": ["engagement_rate", "roi", "churn_rate"]
                }
            ],
            "integrations": ["shopify", "magento", "salesforce_commerce", "hubspot"],
            "compliance": ["pci_dss", "ccpa"]
        },

        # 教育
        "education": {
            "name": "教育行业",
            "scenarios": [
                {
                    "type": "customer_service",
                    "name": "学员服务",
                    "description": "课程咨询、报名指导、学习支持",
                    "workflows": ["intake", "course_match", "onboarding"],
                    "metrics": ["enrollment_rate", "completion_rate", "satisfaction"]
                },
                {
                    "type": "operations",
                    "name": "教务管理",
                    "description": "排课管理、师资调度、成绩管理",
                    "workflows": ["schedule", "allocate", "track"],
                    "metrics": ["class_utilization", "teacher_load", "pass_rate"]
                }
            ],
            "integrations": ["canvas", "blackboard", "moodle", "salesforce"],
            "compliance": ["ferpa", "gdpr"]
        },

        # 政府
        "government": {
            "name": "政府机构",
            "scenarios": [
                {
                    "type": "customer_service",
                    "name": "市民服务",
                    "description": "政策咨询、办事指南、进度查询",
                    "workflows": ["intake", "routing", "status_update"],
                    "metrics": ["response_time", "first_contact_resolution", "citizen_satisfaction"]
                },
                {
                    "type": "compliance",
                    "name": "合规审查",
                    "description": "文件审查、审批流程、合规报告",
                    "workflows": ["review", "approve", "archive"],
                    "metrics": ["processing_time", "approval_rate", "audit_score"]
                }
            ],
            "integrations": ["sharepoint", "salesforce_gov", "service_now"],
            "compliance": ["fedramp", "fisma", " Section 508"]
        }
    }

    def __init__(self):
        self.templates = self.TEMPLATES

    def get_industry_template(self, industry: str) -> Dict:
        """获取行业模板"""
        return self.templates.get(industry.lower(), self.templates["technology"])

    def get_scenario_template(
        self,
        industry: str,
        scenario_type: str
    ) -> Optional[Dict]:
        """获取场景模板"""
        template = self.get_industry_template(industry)
        for scenario in template.get("scenarios", []):
            if scenario["type"] == scenario_type:
                return scenario
        return None

    def list_industries(self) -> List[str]:
        """列出所有行业"""
        return list(self.templates.keys())

    def list_scenarios(self, industry: str) -> List[Dict]:
        """列出行业场景"""
        template = self.get_industry_template(industry)
        return template.get("scenarios", [])

    def create_scenario_from_template(
        self,
        industry: str,
        scenario_type: str,
        custom_settings: Dict = None
    ) -> ScenarioConfig:
        """从模板创建场景配置"""
        scenario_template = self.get_scenario_template(industry, scenario_type)
        if not scenario_template:
            raise ValueError(f"场景 {scenario_type} 在行业 {industry} 中不存在")

        industry_template = self.get_industry_template(industry)

        config = ScenarioConfig(
            name=scenario_template["name"],
            industry=industry,
            scenario_type=scenario_type,
            description=scenario_template["description"],
            enabled_modules=scenario_template.get("workflows", []),
            workflows=[{"name": w} for w in scenario_template.get("workflows", [])],
            integrations=industry_template.get("integrations", []),
            metrics=scenario_template.get("metrics", {}),
            compliance_rules=industry_template.get("compliance", []),
            is_active=True
        )

        # 应用自定义设置
        if custom_settings:
            config.custom_settings.update(custom_settings)

        return config


class EnterpriseScenarioAdapter:
    """企业场景适配器

    将 AI 原生 OS 的能力适配到特定企业场景
    """

    def __init__(self, enterprise_id: str = None):
        self.enterprise_id = enterprise_id or str(uuid.uuid4())
        self.scenarios: Dict[str, ScenarioConfig] = {}
        self.active_scenario: Optional[ScenarioConfig] = None
        self.template_library = IndustryTemplateLibrary()
        self.workflow_orchestrator = WorkflowOrchestrator()
        self.metrics_monitor = BusinessMetricsMonitor()
        self.context_cache: Dict[str, Any] = {}

    def create_scenario(
        self,
        industry: str,
        scenario_type: str,
        name: str = None,
        custom_settings: Dict = None
    ) -> ScenarioConfig:
        """创建企业场景"""
        # 从模板创建
        config = self.template_library.create_scenario_from_template(
            industry, scenario_type, custom_settings
        )

        # 覆盖名称
        if name:
            config.name = name

        # 注册场景
        self.scenarios[config.scenario_id] = config

        # 如果没有活跃场景，激活第一个
        if self.active_scenario is None:
            self.active_scenario = config

        return config

    def switch_scenario(self, scenario_id: str) -> bool:
        """切换场景"""
        if scenario_id in self.scenarios:
            self.active_scenario = self.scenarios[scenario_id]
            # 清空上下文缓存
            self.context_cache.clear()
            return True
        return False

    def get_active_scenario(self) -> Optional[ScenarioConfig]:
        """获取活跃场景"""
        return self.active_scenario

    def process_enterprise_request(
        self,
        request: str,
        context: Dict = None,
        options: Dict = None
    ) -> Dict[str, Any]:
        """处理企业请求"""
        if not self.active_scenario:
            return {"error": "No active scenario", "suggestions": []}

        scenario = self.active_scenario
        context = context or {}
        options = options or {}

        # 构建增强上下文
        enhanced_context = {
            **context,
            "enterprise_id": self.enterprise_id,
            "industry": scenario.industry,
            "scenario_type": scenario.scenario_type,
            "enabled_modules": scenario.enabled_modules,
            "custom_settings": scenario.custom_settings,
            "integrations": scenario.integrations,
            "compliance_rules": scenario.compliance_rules
        }

        # 意图识别
        intent = self._recognize_intent(request, scenario)

        # 工作流选择
        workflow = self._select_workflow(intent, scenario)

        # 执行工作流
        if workflow:
            result = self.workflow_orchestrator.execute_workflow(
                workflow,
                enhanced_context,
                options
            )
        else:
            result = self._direct_process(request, enhanced_context, options)

        # 记录指标
        self._record_metrics(scenario, intent, result)

        return {
            "intent": intent,
            "workflow": workflow.name if workflow else None,
            "result": result,
            "context": enhanced_context,
            "suggestions": self._generate_suggestions(intent, result)
        }

    def _recognize_intent(
        self,
        request: str,
        scenario: ScenarioConfig
    ) -> Dict[str, Any]:
        """识别意图"""
        request_lower = request.lower()

        # 基于场景类型的意图映射
        intent_patterns = {
            "customer_service": {
                "query": ["查询", "咨询", "怎么", "什么", "?", "how", "what", "where"],
                "complaint": ["投诉", "不满", "问题", "坏", "差", "wrong", "bad", "issue"],
                "request": ["请求", "需要", "帮忙", "help", "need", "want"],
                "feedback": ["反馈", "建议", "意见", "feedback", "suggest", "improve"]
            },
            "it_support": {
                "diagnose": ["故障", "报错", "不行", "不能用", "error", "fail", "broken"],
                "fix": ["修复", "解决", "处理", "fix", "resolve", "solve"],
                "setup": ["安装", "配置", "设置", "setup", "install", "configure"],
                "monitor": ["监控", "状态", "检查", "monitor", "status", "check"]
            },
            "sales": {
                "browse": ["看看", "浏览", "有什么", "browse", "show", "available"],
                "recommend": ["推荐", "建议", "适合", "recommend", "suggest", "suitable"],
                "quote": ["报价", "价格", "多少钱", "price", "cost", "quote"],
                "order": ["购买", "下单", "订购", "buy", "order", "purchase"]
            },
            "data_analysis": {
                "query": ["查询", "获取", "拉取", "query", "get", "fetch"],
                "analyze": ["分析", "分析一下", "analyze", "analyse", "insights"],
                "visualize": ["可视化", "图表", "dashboard", "chart", "graph"],
                "report": ["报告", "报表", "导出", "report", "export"]
            }
        }

        # 获取场景对应的意图模式
        patterns = intent_patterns.get(
            scenario.scenario_type,
            intent_patterns["customer_service"]
        )

        # 匹配意图
        matched_intent = "general"
        confidence = 0.5

        for intent_name, keywords in patterns.items():
            for keyword in keywords:
                if keyword in request_lower:
                    matched_intent = intent_name
                    confidence = 0.8
                    break

        return {
            "type": matched_intent,
            "confidence": confidence,
            "raw_request": request
        }

    def _select_workflow(
        self,
        intent: Dict[str, Any],
        scenario: ScenarioConfig
    ) -> Optional[WorkflowDefinition]:
        """选择工作流"""
        intent_type = intent.get("type", "general")

        # 从场景配置的工作流中匹配
        for workflow_config in scenario.workflows:
            workflow_name = workflow_config.get("name", "").lower()
            if intent_type in workflow_name or workflow_name in intent_type:
                return WorkflowDefinition(
                    name=workflow_name,
                    industry=scenario.industry,
                    scenario_type=scenario.scenario_type
                )

        # 返回默认工作流
        if scenario.workflows:
            return WorkflowDefinition(
                name=scenario.workflows[0].get("name", "default"),
                industry=scenario.industry,
                scenario_type=scenario.scenario_type
            )

        return None

    def _direct_process(
        self,
        request: str,
        context: Dict,
        options: Dict
    ) -> Dict[str, Any]:
        """直接处理请求"""
        # 根据场景类型构建处理逻辑
        scenario_type = context.get('scenario_type', '请求')
        return {
            "status": "processed",
            "response": f"已处理您的{scenario_type}: {request[:50]}...",
            "confidence": 0.85,
            "next_actions": []
        }

    def _record_metrics(
        self,
        scenario: ScenarioConfig,
        intent: Dict,
        result: Dict
    ):
        """记录指标"""
        # 记录请求量
        metric_key = f"{scenario.scenario_type}_requests"
        self.metrics_monitor.record_metric(metric_key, 1, category="business")

        # 记录成功率
        if result.get("status") == "processed":
            self.metrics_monitor.record_metric(
                f"{scenario.scenario_type}_success_rate",
                1,
                category="quality"
            )

    def _generate_suggestions(
        self,
        intent: Dict,
        result: Dict
    ) -> List[str]:
        """生成建议"""
        suggestions = []

        if result.get("next_actions"):
            suggestions.extend(result["next_actions"][:3])

        # 基于意图的通用建议
        intent_type = intent.get("type", "general")

        common_suggestions = {
            "query": ["查看详细信息", "导出结果", "订阅更新"],
            "complaint": ["提交工单", "联系人工客服", "查看FAQ"],
            "diagnose": ["查看日志", "重启服务", "联系支持"],
            "recommend": ["了解更多产品", "获取报价", "预约演示"],
            "analyze": ["生成图表", "导出报告", "设置定时任务"]
        }

        suggestions.extend(common_suggestions.get(intent_type, []))

        return list(set(suggestions))[:5]


class WorkflowOrchestrator:
    """工作流编排器"""

    def __init__(self):
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.handlers: Dict[str, Callable] = {}

    def register_workflow(self, workflow: WorkflowDefinition):
        """注册工作流"""
        self.workflows[workflow.workflow_id] = workflow

    def register_handler(self, stage: str, handler: Callable):
        """注册处理器"""
        self.handlers[stage] = handler

    def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        context: Dict,
        options: Dict = None
    ) -> Dict[str, Any]:
        """执行工作流"""
        execution = WorkflowExecution(
            workflow_id=workflow.workflow_id,
            context=context
        )

        self.executions[execution.execution_id] = execution

        try:
            # 执行各阶段
            for stage in workflow.stages:
                stage_name = stage.get("name", "unknown")
                execution.current_stage = stage_name

                # 调用处理器
                if stage_name in self.handlers:
                    result = self.handlers[stage_name](context, options or {})
                    execution.results[stage_name] = result
                    context.update(result)

            execution.status = "completed"
            execution.completed_at = datetime.now().isoformat()

            return {
                "status": "completed",
                "execution_id": execution.execution_id,
                "results": execution.results,
                "context": context
            }

        except Exception as e:
            execution.status = "failed"
            execution.errors.append({
                "stage": execution.current_stage,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

            # 错误处理
            if workflow.error_handling:
                return {
                    "status": "failed",
                    "error": str(e),
                    "handling": workflow.error_handling,
                    "execution_id": execution.execution_id
                }

            return {
                "status": "failed",
                "error": str(e),
                "execution_id": execution.execution_id
            }

    def get_execution_status(self, execution_id: str) -> Optional[Dict]:
        """获取执行状态"""
        execution = self.executions.get(execution_id)
        if not execution:
            return None

        return {
            "execution_id": execution.execution_id,
            "workflow_id": execution.workflow_id,
            "status": execution.status,
            "current_stage": execution.current_stage,
            "results": execution.results,
            "errors": execution.errors,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at
        }


class BusinessMetricsMonitor:
    """业务指标监控"""

    def __init__(self):
        self.metrics: Dict[str, BusinessMetric] = {}
        self.dashboard: Dict[str, Any] = {}

    def create_metric(
        self,
        name: str,
        category: str = "business",
        unit: str = "",
        target: float = 0.0,
        thresholds: Dict[str, float] = None
    ) -> BusinessMetric:
        """创建指标"""
        metric = BusinessMetric(
            name=name,
            category=category,
            unit=unit,
            target=target,
            thresholds=thresholds or {}
        )
        self.metrics[name] = metric
        return metric

    def record_metric(
        self,
        name: str,
        value: float,
        category: str = "business",
        increment: bool = True
    ):
        """记录指标值"""
        if name not in self.metrics:
            self.create_metric(name, category)

        metric = self.metrics[name]
        metric.previous_value = metric.value

        if increment:
            metric.value += value
        else:
            metric.value = value

        # 计算趋势
        if metric.value > metric.previous_value:
            metric.trend = "up"
        elif metric.value < metric.previous_value:
            metric.trend = "down"
        else:
            metric.trend = "stable"

        # 添加到历史
        metric.history.append({
            "value": metric.value,
            "timestamp": datetime.now().isoformat()
        })

        # 保持历史记录数量
        if len(metric.history) > 100:
            metric.history = metric.history[-100:]

        metric.last_updated = datetime.now().isoformat()

    def get_metric(self, name: str) -> Optional[BusinessMetric]:
        """获取指标"""
        return self.metrics.get(name)

    def get_all_metrics(self, category: str = None) -> List[Dict]:
        """获取所有指标"""
        if category:
            return [
                m.__dict__ for m in self.metrics.values()
                if m.category == category
            ]
        return [m.__dict__ for m in self.metrics.values()]

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """获取仪表盘摘要"""
        summary = {
            "total_metrics": len(self.metrics),
            "by_category": defaultdict(int),
            "by_trend": defaultdict(int),
            "alerts": [],
            "top_metrics": []
        }

        for metric in self.metrics.values():
            summary["by_category"][metric.category] += 1
            summary["by_trend"][metric.trend] += 1

            # 检查告警阈值
            if metric.thresholds:
                if metric.value >= metric.thresholds.get("critical", float("inf")):
                    summary["alerts"].append({
                        "metric": metric.name,
                        "level": "critical",
                        "value": metric.value,
                        "threshold": metric.thresholds["critical"]
                    })
                elif metric.value >= metric.thresholds.get("warning", float("inf")):
                    summary["alerts"].append({
                        "metric": metric.name,
                        "level": "warning",
                        "value": metric.value,
                        "threshold": metric.thresholds["warning"]
                    })

        # 按值排序获取前5
        sorted_metrics = sorted(
            self.metrics.values(),
            key=lambda m: m.value,
            reverse=True
        )
        summary["top_metrics"] = [
            {"name": m.name, "value": m.value, "trend": m.trend}
            for m in sorted_metrics[:5]
        ]

        return dict(summary)


class EnterpriseIntegrationHub:
    """企业集成中心"""

    def __init__(self, enterprise_id: str = None):
        self.enterprise_id = enterprise_id or str(uuid.uuid4())
        self.integrations: Dict[str, Dict] = {}
        self.adapters: Dict[str, Any] = {}
        self.connector_registry: Dict[str, Callable] = {}

    def register_integration(
        self,
        name: str,
        integration_type: str,
        config: Dict,
        connector: Callable = None
    ):
        """注册集成"""
        self.integrations[name] = {
            "type": integration_type,
            "config": config,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }

        if connector:
            self.connector_registry[name] = connector

    def connect(self, name: str, auth_data: Dict = None) -> bool:
        """连接集成"""
        if name not in self.integrations:
            return False

        integration = self.integrations[name]

        # 如果有连接器，执行连接
        if name in self.connector_registry:
            try:
                self.connector_registry[name](auth_data or {})
                integration["status"] = "connected"
                return True
            except Exception:
                integration["status"] = "error"
                return False

        integration["status"] = "connected"
        return True

    def disconnect(self, name: str) -> bool:
        """断开集成"""
        if name not in self.integrations:
            return False

        self.integrations[name]["status"] = "disconnected"
        return True

    def call_integration(
        self,
        name: str,
        method: str,
        params: Dict = None
    ) -> Dict[str, Any]:
        """调用集成接口"""
        if name not in self.integrations:
            return {"error": f"Integration {name} not found"}

        integration = self.integrations[name]

        if integration["status"] != "connected":
            return {"error": f"Integration {name} not connected"}

        # 这里应该调用实际的连接器
        # 简化实现
        return {
            "status": "success",
            "integration": name,
            "method": method,
            "result": f"Result of {method}"
        }

    def get_integration_status(self) -> Dict[str, str]:
        """获取集成状态"""
        return {
            name: info["status"]
            for name, info in self.integrations.items()
        }


# ============================================================================
# 便捷函数
# ============================================================================

def create_enterprise_adapter(
    enterprise_id: str = None,
    industry: str = "technology"
) -> EnterpriseScenarioAdapter:
    """创建企业适配器"""
    adapter = EnterpriseScenarioAdapter(enterprise_id)

    # 获取行业模板
    scenarios = IndustryTemplateLibrary().list_scenarios(industry)

    # 创建第一个场景作为默认
    if scenarios:
        adapter.create_scenario(industry, scenarios[0]["type"])

    return adapter


def create_workflow_orchestrator() -> WorkflowOrchestrator:
    """创建工作流编排器"""
    return WorkflowOrchestrator()


def create_metrics_monitor() -> BusinessMetricsMonitor:
    """创建指标监控器"""
    return BusinessMetricsMonitor()


def create_integration_hub(enterprise_id: str = None) -> EnterpriseIntegrationHub:
    """创建集成中心"""
    return EnterpriseIntegrationHub(enterprise_id)


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 枚举
    "Industry",
    "ScenarioType",
    "WorkflowStage",
    "MetricCategory",
    # 数据结构
    "ScenarioConfig",
    "WorkflowDefinition",
    "WorkflowExecution",
    "BusinessMetric",
    # 核心类
    "IndustryTemplateLibrary",
    "EnterpriseScenarioAdapter",
    "WorkflowOrchestrator",
    "BusinessMetricsMonitor",
    "EnterpriseIntegrationHub",
    # 便捷函数
    "create_enterprise_adapter",
    "create_workflow_orchestrator",
    "create_metrics_monitor",
    "create_integration_hub"
]
