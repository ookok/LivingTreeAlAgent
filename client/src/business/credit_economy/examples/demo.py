"""
积分经济模型示例
=================

演示如何使用积分经济模型进行智能调度。
"""

from client.src.business.credit_economy import (
    CreditRegistry, CreditRegistry as CR,
    TaskEstimator, TaskSpec,
    Scheduler, SchedulingStrategy, SchedulingDecision,
    CreditLearning,
    DAGOrchestrator, WorkflowSpec, ExecutionPlan,
    TransactionLedger, TransactionType,
    CreditEconomyManager, get_credit_economy_manager
)
from core.credit_economy.credit_registry import TaskType


def demo_basic_scheduling():
    """演示基础调度"""
    print("=" * 60)
    print("积分经济模型 - 基础调度演示")
    print("=" * 60)

    # 获取管理器
    manager = get_credit_economy_manager()

    # 创建用户（学生）
    student = manager.create_user(
        user_id="student_001",
        initial_credits=1000.0,
        time_value_per_hour=50.0,     # 学生时间价值低
        quality_preference=60
    )

    # 创建用户（工程师）
    engineer = manager.create_user(
        user_id="engineer_001",
        initial_credits=10000.0,
        time_value_per_hour=200.0,    # 工程师时间价值中等
        quality_preference=80
    )

    # 创建用户（高管）
    executive = manager.create_user(
        user_id="executive_001",
        initial_credits=100000.0,
        time_value_per_hour=1000.0,   # 高管时间价值极高
        quality_preference=90
    )

    # 翻译任务：2000字
    task = TaskSpec(
        task_id="trans_2000",
        task_type=TaskType.TRANSLATION,
        input_length=2000,
        min_quality=70,
        budget=500.0
    )

    print("\n【任务】翻译2000字中文技术博客")
    print(f"最低质量要求: {task.min_quality}")
    print(f"预算: {task.budget}积分")
    print()

    # 不同用户的调度决策
    for user in [student, engineer, executive]:
        manager.set_current_user(user.user_id)
        decision = manager.schedule_task(
            task_type=TaskType.TRANSLATION,
            input_length=2000,
            task_id=f"trans_{user.user_id}",
        )

        print(f"用户类型: {user.user_id}")
        print(f"  时间价值: {user.time_value_per_hour}积分/小时")
        print(f"  选择插件: {decision.selected_plugin_name}")
        print(f"  预估耗时: {decision.estimation.estimated_time_sec:.1f}秒")
        print(f"  质量评分: {decision.estimation.quality_score}分")
        print(f"  积分消耗: {decision.estimation.total_credits:.1f}积分")
        print(f"  决策理由: {decision.reasoning}")
        if decision.warning:
            print(f"  警告: {decision.warning}")
        print()


def demo_workflow_orchestration():
    """演示工作流编排"""
    print("=" * 60)
    print("积分经济模型 - 工作流编排演示")
    print("=" * 60)

    manager = get_credit_economy_manager()
    manager.set_current_user("engineer_001")

    # 创建视频翻译工作流
    workflow = manager.get_video_translation_workflow()

    print(f"\n工作流: {workflow.name}")
    print(f"描述: {workflow.description}")
    print(f"节点数: {len(workflow.nodes)}")
    print(f"边数: {len(workflow.edges)}")
    print()

    # 打印节点
    print("节点:")
    for node in workflow.nodes:
        print(f"  - {node.name} ({node.node_id})")
        print(f"    输入: {node.input_format.value} -> 输出: {node.output_format.value}")
    print()

    # 打印边
    print("依赖关系:")
    for edge in workflow.edges:
        from_node = workflow.get_node(edge.from_node)
        to_node = workflow.get_node(edge.to_node)
        print(f"  {from_node.name} -> {to_node.name}")
    print()

    # 生成执行计划
    input_data = {
        "video_frame_length": 10000,  # 视频抽帧输入
        "ocr_length": 5000,           # OCR输出
        "translation_length": 6000,    # 翻译输出
    }

    plan = manager.create_and_execute_workflow(workflow, input_data)

    print("执行计划:")
    print(f"  总预估时间: {plan.total_estimated_time_sec:.1f}秒")
    print(f"  总预估积分: {plan.total_estimated_credits:.1f}积分")
    print(f"  最低质量: {plan.min_quality}分")
    print(f"  可行性: {'是' if plan.is_feasible else '否'}")
    if plan.feasibility_issues:
        for issue in plan.feasibility_issues:
            print(f"    问题: {issue}")
    print()

    # 打印节点计划
    print("节点执行计划:")
    for node_plan in plan.node_plans:
        print(f"  {node_plan.node_id}:")
        print(f"    插件: {node_plan.plugin_name}")
        print(f"    耗时: {node_plan.estimated_time_sec:.1f}秒")
        print(f"    积分: {node_plan.estimated_credits:.1f}")
    print()


def demo_learning_feedback():
    """演示学习反馈"""
    print("=" * 60)
    print("积分经济模型 - 学习反馈演示")
    print("=" * 60)

    manager = get_credit_economy_manager()
    learning = CreditLearning.get_instance()

    # 模拟多条执行记录
    print("\n模拟任务执行记录...")

    # 模拟deepseek_api的实际表现
    for i in range(5):
        learning.record(
            plugin_id="deepseek_api",
            task_id=f"task_{i}",
            task_type="translation",
            predicted_time=4.0,
            actual_time=4.5 + (i * 0.2),  # 逐渐变慢
            predicted_credits=100.0,
            actual_credits=100.0,
            predicted_quality=85,
            actual_quality=85,
            user_satisfaction=4.0 + (i * 0.1),
        )

    # 获取学习指标
    metrics = learning.get_metrics("deepseek_api")
    print(f"\n插件: deepseek_api")
    print(f"  样本数: {metrics.sample_count}")
    print(f"  平均时间误差: {metrics.avg_time_error*100:.1f}%")
    print(f"  平均满意度: {metrics.avg_satisfaction:.2f}/5")
    print(f"  预测准确度: {metrics.prediction_accuracy*100:.1f}%")

    # 获取优化建议
    suggestions = learning.suggest_optimization("deepseek_api")
    print(f"\n优化建议:")
    for s in suggestions:
        print(f"  - {s}")


def demo_transaction_ledger():
    """演示积分账本"""
    print("=" * 60)
    print("积分经济模型 - 积分账本演示")
    print("=" * 60)

    ledger = TransactionLedger.get_instance()
    manager = get_credit_economy_manager()

    # 设置用户
    manager.set_current_user("engineer_001")

    # 充值
    print("\n积分充值...")
    tx = manager.recharge_credits(1000.0, "测试充值")
    print(f"  交易ID: {tx.tx_id}")
    print(f"  类型: {tx.tx_type.value}")
    print(f"  金额: {tx.amount}")
    print(f"  余额: {tx.balance_after}")

    # 模拟任务扣积分
    print("\n模拟任务执行扣积分...")
    decision = manager.schedule_task(
        task_type=TaskType.TRANSLATION,
        input_length=2000,
        task_id="trans_demo"
    )

    if decision.selected_plugin_id:
        result = manager.execute_scheduled_task(decision)
        print(f"  执行结果: {result['status']}")

    # 查询用户余额
    balance = manager.get_user_balance()
    print(f"\n当前余额: {balance}积分")

    # 获取用户摘要
    summary = ledger.get_user_summary("engineer_001")
    print(f"累计获得: {summary['total_earned']}积分")
    print(f"累计消耗: {summary['total_spent']}积分")
    print(f"交易笔数: {summary['transaction_count']}")


def demo_user_scenarios():
    """演示不同用户场景"""
    print("=" * 60)
    print("积分经济模型 - 用户场景演示")
    print("=" * 60)

    manager = get_credit_economy_manager()

    # 翻译2000字任务
    task = TaskSpec(
        task_id="trans_demo",
        task_type=TaskType.TRANSLATION,
        input_length=2000,
        min_quality=70,
        budget=500.0
    )

    print("\n【任务】翻译2000字中文 -> 英文")
    print()

    scenarios = [
        ("学生预算型", "student_budget", 50.0, 1000.0, 60),
        ("工程师均衡型", "engineer_balanced", 200.0, 5000.0, 80),
        ("高管质量型", "executive_quality", 1000.0, 50000.0, 95),
        ("政务合规型", "gov_compliance", 200.0, 1000.0, 70),
    ]

    for name, uid, time_value, budget, quality_pref in scenarios:
        # 创建/更新用户
        user = manager.create_user(
            user_id=uid,
            initial_credits=budget,
            time_value_per_hour=time_value,
            quality_preference=quality_pref
        )
        manager.set_current_user(uid)

        decision = manager.schedule_task(
            task_type=TaskType.TRANSLATION,
            input_length=2000,
            task_id=f"trans_{uid}",
            min_quality=quality_pref,
            budget=budget
        )

        print(f"场景: {name}")
        print(f"  用户时间价值: {time_value}积分/小时")
        print(f"  预算: {budget}积分")
        print(f"  质量偏好: {quality_pref}")
        print(f"  -> 选择: {decision.selected_plugin_name}")
        print(f"    积分消耗: {decision.estimation.total_credits:.1f}")
        print(f"    质量: {decision.estimation.quality_score}分")
        print(f"    耗时: {decision.estimation.estimated_time_sec:.1f}秒")
        print()


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "积分经济模型演示" + " " * 25 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    demo_basic_scheduling()
    demo_workflow_orchestration()
    demo_learning_feedback()
    demo_transaction_ledger()
    demo_user_scenarios()

    print("\n演示完成!")


if __name__ == "__main__":
    main()
