"""
Phase 5: 企业级应用场景集成测试
================================

测试内容:
1. IndustryTemplateLibrary - 行业模板库
2. EnterpriseScenarioAdapter - 企业场景适配器
3. WorkflowOrchestrator - 工作流编排器
4. BusinessMetricsMonitor - 业务指标监控
5. EnterpriseIntegrationHub - 企业集成中心
"""

import sys
import os
import importlib.util

# 直接加载模块，绕过 core/__init__.py
module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'core', 'enterprise_integration.py'
)

spec = importlib.util.spec_from_file_location('enterprise_integration', module_path)
enterprise_integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enterprise_integration)

# 导出需要的内容
Industry = enterprise_integration.Industry
ScenarioType = enterprise_integration.ScenarioType
ScenarioConfig = enterprise_integration.ScenarioConfig
WorkflowDefinition = enterprise_integration.WorkflowDefinition
WorkflowExecution = enterprise_integration.WorkflowExecution
BusinessMetric = enterprise_integration.BusinessMetric
IndustryTemplateLibrary = enterprise_integration.IndustryTemplateLibrary
EnterpriseScenarioAdapter = enterprise_integration.EnterpriseScenarioAdapter
WorkflowOrchestrator = enterprise_integration.WorkflowOrchestrator
BusinessMetricsMonitor = enterprise_integration.BusinessMetricsMonitor
EnterpriseIntegrationHub = enterprise_integration.EnterpriseIntegrationHub
create_enterprise_adapter = enterprise_integration.create_enterprise_adapter
create_metrics_monitor = enterprise_integration.create_metrics_monitor


def test_template_library():
    """测试行业模板库"""
    print("\n[Test 1] IndustryTemplateLibrary")
    print("-" * 40)

    library = IndustryTemplateLibrary()

    # 列出行业
    industries = library.list_industries()
    print(f"  Available Industries: {len(industries)}")
    print(f"    {', '.join(industries)}")

    # 获取科技行业模板
    tech_template = library.get_industry_template("technology")
    print(f"\n  Technology Template:")
    print(f"    Scenarios: {len(tech_template['scenarios'])}")
    print(f"    Integrations: {', '.join(tech_template['integrations'][:3])}...")
    print(f"    Compliance: {', '.join(tech_template['compliance'])}")

    # 获取金融行业场景
    finance_scenarios = library.list_scenarios("finance")
    print(f"\n  Finance Scenarios: {len(finance_scenarios)}")
    for scenario in finance_scenarios[:3]:
        print(f"    - {scenario['name']}: {scenario['description']}")

    # 获取客服场景模板
    customer_service = library.get_scenario_template("technology", "customer_service")
    print(f"\n  Customer Service Template:")
    print(f"    Name: {customer_service['name']}")
    print(f"    Workflows: {', '.join(customer_service['workflows'])}")

    # 从模板创建配置
    config = library.create_scenario_from_template(
        "retail", "sales",
        custom_settings={"region": "cn-north"}
    )
    print(f"\n  Created Scenario Config:")
    print(f"    Name: {config.name}")
    print(f"    Industry: {config.industry}")
    print(f"    Integrations: {len(config.integrations)}")

    print("  [OK] Template Library Test Passed")


def test_scenario_adapter():
    """测试企业场景适配器"""
    print("\n[Test 2] EnterpriseScenarioAdapter")
    print("-" * 40)

    adapter = EnterpriseScenarioAdapter("enterprise_001")

    # 创建科技客服场景
    tech_cs = adapter.create_scenario("technology", "customer_service")
    print(f"  Created Scenario: {tech_cs.name}")
    print(f"    Industry: {tech_cs.industry}")
    print(f"    Type: {tech_cs.scenario_type}")
    print(f"    Modules: {len(tech_cs.enabled_modules)}")

    # 创建零售销售场景
    retail_sales = adapter.create_scenario("retail", "sales", name="零售销售助手")
    print(f"\n  Created Scenario: {retail_sales.name}")

    # 切换场景
    adapter.switch_scenario(retail_sales.scenario_id)
    active = adapter.get_active_scenario()
    print(f"\n  Active Scenario: {active.name}")

    # 处理请求
    result = adapter.process_enterprise_request(
        "我想查一下订单状态",
        context={"user_id": "user_123"}
    )
    print(f"\n  Request: 我想查一下订单状态")
    print(f"  Intent: {result['intent']['type']}")
    print(f"  Workflow: {result['workflow']}")

    # 处理IT支持请求
    result2 = adapter.process_enterprise_request(
        "系统报错了，显示500错误",
        context={"system": "web_server"}
    )
    print(f"\n  Request: 系统报错了，显示500错误")
    print(f"  Intent: {result2['intent']['type']}")
    print(f"  Suggestions: {', '.join(result2['suggestions'][:2])}")

    print("  [OK] Scenario Adapter Test Passed")


def test_workflow_orchestrator():
    """测试工作流编排器"""
    print("\n[Test 3] WorkflowOrchestrator")
    print("-" * 40)

    orchestrator = WorkflowOrchestrator()

    # 注册处理器
    def trigger_handler(ctx, opts):
        print(f"    [Trigger] Initializing workflow")
        return {"initialized": True, "timestamp": "now"}

    def process_handler(ctx, opts):
        print(f"    [Process] Processing request")
        return {"processed": True, "result": "data_processed"}

    def output_handler(ctx, opts):
        print(f"    [Output] Generating response")
        return {"response": "Here's your result", "confidence": 0.95}

    orchestrator.register_handler("trigger", trigger_handler)
    orchestrator.register_handler("process", process_handler)
    orchestrator.register_handler("output", output_handler)

    # 定义工作流
    workflow = WorkflowDefinition(
        name="test_workflow",
        stages=[
            {"name": "trigger", "order": 1},
            {"name": "process", "order": 2},
            {"name": "output", "order": 3}
        ],
        timeout_seconds=60
    )
    orchestrator.register_workflow(workflow)

    # 执行工作流
    result = orchestrator.execute_workflow(
        workflow,
        context={"request": "test data"},
        options={"verbose": True}
    )

    print(f"\n  Execution Status: {result['status']}")
    print(f"  Execution ID: {result['execution_id']}")
    print(f"  Stages Completed: {len(result['results'])}")

    # 获取执行状态
    status = orchestrator.get_execution_status(result["execution_id"])
    print(f"  Final Stage: {status['current_stage']}")

    print("  [OK] Workflow Orchestrator Test Passed")


def test_metrics_monitor():
    """测试业务指标监控"""
    print("\n[Test 4] BusinessMetricsMonitor")
    print("-" * 40)

    monitor = BusinessMetricsMonitor()

    # 创建指标
    monitor.create_metric(
        "daily_orders",
        category="business",
        unit="count",
        target=1000,
        thresholds={"warning": 800, "critical": 950}
    )

    monitor.create_metric(
        "response_time_ms",
        category="performance",
        unit="ms",
        target=200,
        thresholds={"warning": 300, "critical": 500}
    )

    monitor.create_metric(
        "customer_satisfaction",
        category="quality",
        unit="score",
        target=4.5
    )

    # 记录数据
    for i in range(5):
        monitor.record_metric("daily_orders", 100 + i * 10)

    monitor.record_metric("response_time_ms", 150)
    monitor.record_metric("customer_satisfaction", 4.7)

    # 获取指标
    orders = monitor.get_metric("daily_orders")
    print(f"  Daily Orders: {orders.value} ({orders.trend})")
    print(f"    Target: {orders.target}, History: {len(orders.history)}")

    response = monitor.get_metric("response_time_ms")
    print(f"  Response Time: {response.value}ms (target: {response.target}ms)")

    satisfaction = monitor.get_metric("customer_satisfaction")
    print(f"  Satisfaction: {satisfaction.value}/5 (target: {satisfaction.target})")

    # 获取仪表盘摘要
    summary = monitor.get_dashboard_summary()
    print(f"\n  Dashboard Summary:")
    print(f"    Total Metrics: {summary['total_metrics']}")
    print(f"    By Category: {dict(summary['by_category'])}")
    print(f"    Alerts: {len(summary['alerts'])}")
    print(f"    Top Metrics: {[m['name'] for m in summary['top_metrics']]}")

    print("  [OK] Metrics Monitor Test Passed")


def test_integration_hub():
    """测试企业集成中心"""
    print("\n[Test 5] EnterpriseIntegrationHub")
    print("-" * 40)

    hub = EnterpriseIntegrationHub("enterprise_001")

    # 注册集成
    hub.register_integration(
        name="slack",
        integration_type="messaging",
        config={"webhook_url": "https://hooks.slack.com/..."}
    )

    hub.register_integration(
        name="salesforce",
        integration_type="crm",
        config={"instance_url": "https://company.salesforce.com"}
    )

    hub.register_integration(
        name="jira",
        integration_type="project_management",
        config={"base_url": "https://company.atlassian.net"}
    )

    print(f"  Registered Integrations: {len(hub.integrations)}")

    # 连接集成
    hub.connect("slack")
    hub.connect("salesforce")

    status = hub.get_integration_status()
    print(f"\n  Integration Status:")
    for name, st in status.items():
        print(f"    {name}: {st}")

    # 调用集成
    result = hub.call_integration("slack", "send_message", {"text": "Hello"})
    print(f"\n  Slack Call Result: {result['status']}")

    # 断开集成
    hub.disconnect("salesforce")
    print(f"  Salesforce After Disconnect: {hub.get_integration_status()['salesforce']}")

    print("  [OK] Integration Hub Test Passed")


def test_cross_scenario_workflow():
    """测试跨场景工作流"""
    print("\n[Test 6] Cross-Scenario Workflow")
    print("-" * 40)

    # 创建多场景适配器
    adapter = EnterpriseScenarioAdapter("enterprise_cross")

    # 创建多个场景
    adapter.create_scenario("technology", "customer_service", name="技术支持客服")
    adapter.create_scenario("technology", "it_support", name="IT支持助手")
    adapter.create_scenario("finance", "compliance", name="合规审查")

    print(f"  Created Scenarios: {len(adapter.scenarios)}")

    # 模拟一个跨部门的工作流请求
    requests = [
        ("technology", "it_support", "服务器响应很慢，需要检查"),
        ("finance", "compliance", "这笔交易需要风控审核"),
        ("technology", "customer_service", "客户投诉系统经常崩溃")
    ]

    for industry, scenario_type, request in requests:
        # 切换到对应场景
        for config in adapter.scenarios.values():
            if config.industry == industry and config.scenario_type == scenario_type:
                adapter.switch_scenario(config.scenario_id)
                break

        result = adapter.process_enterprise_request(request)
        print(f"\n  [{scenario_type}] {request[:20]}...")
        print(f"    Intent: {result['intent']['type']} (conf: {result['intent']['confidence']:.2f})")
        print(f"    Workflow: {result['workflow']}")

    print("  [OK] Cross-Scenario Workflow Test Passed")


def test_industry_comparison():
    """测试行业对比"""
    print("\n[Test 7] Industry Comparison")
    print("-" * 40)

    industries = ["technology", "finance", "healthcare", "retail"]
    library = IndustryTemplateLibrary()

    print("  Industry Feature Comparison:")
    print("-" * 50)
    print(f"{'Industry':<15} {'Scenarios':<10} {'Integrations':<15} {'Compliance'}")
    print("-" * 50)

    for industry in industries:
        template = library.get_industry_template(industry)
        scenarios = len(template["scenarios"])
        integrations = len(template["integrations"])
        compliance = ", ".join(template["compliance"][:2])

        print(f"{industry:<15} {scenarios:<10} {integrations:<15} {compliance}")

    print("  [OK] Industry Comparison Test Passed")


def test_quick_start():
    """测试快速启动"""
    print("\n[Test 8] Quick Start")
    print("-" * 40)

    # 快速创建适配器
    adapter = create_enterprise_adapter("quick_start", "technology")

    print(f"  Enterprise ID: {adapter.enterprise_id}")
    print(f"  Active Scenario: {adapter.get_active_scenario().name}")
    print(f"  Scenario Modules: {len(adapter.get_active_scenario().enabled_modules)}")

    # 快速处理请求
    result = adapter.process_enterprise_request(
        "帮我查一下工单状态",
        context={"ticket_id": "TICKET-001"}
    )
    print(f"\n  Quick Request Result:")
    print(f"    Intent: {result['intent']['type']}")
    result_data = result.get('result', {})
    response = result_data.get('response', 'N/A')
    print(f"    Response: {response[:50]}...")

    # 快速获取指标
    monitor = create_metrics_monitor()
    monitor.record_metric("test_metric", 100)
    metric = monitor.get_metric("test_metric")
    print(f"\n  Quick Metric: {metric.name} = {metric.value}")

    print("  [OK] Quick Start Test Passed")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("  Phase 5: 企业级应用场景集成测试")
    print("=" * 60)

    test_template_library()
    test_scenario_adapter()
    test_workflow_orchestrator()
    test_metrics_monitor()
    test_integration_hub()
    test_cross_scenario_workflow()
    test_industry_comparison()
    test_quick_start()

    print("\n" + "=" * 60)
    print("  All Phase 5 Tests Passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
