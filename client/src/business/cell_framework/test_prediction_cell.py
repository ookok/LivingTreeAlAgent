"""
预测细胞测试套件

测试覆盖：
1. 预测细胞创建
2. 时间序列预测
3. 多情景分析
4. 趋势分析
5. 资源需求预测
6. 系统健康预测
"""

import asyncio
import sys
import os

# 添加模块路径
cell_framework_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if cell_framework_path not in sys.path:
    sys.path.append(cell_framework_path)

from cell_framework import (
    PredictionCell, TimeSeriesPredictor, ResourcePredictor, HealthPredictor,
    ScenarioType, PredictionMethod, create_cell
)


async def test_prediction_cell_creation():
    """测试预测细胞创建"""
    print("\n" + "="*60)
    print("[Test 1] 预测细胞创建测试")
    print("="*60)
    
    cells = [
        PredictionCell(),
        TimeSeriesPredictor(),
        ResourcePredictor(),
        HealthPredictor(),
    ]
    
    for cell in cells:
        print(f"✓ 创建 {cell.__class__.__name__}[{cell.id}]")
        print(f"  - 类型: {cell.cell_type.value}")
        print(f"  - 专业: {cell.specialization}")
        print(f"  - 状态: {cell.state.value}")
    
    # 使用工厂函数
    factory_cell = create_cell('prediction')
    print(f"✓ 使用工厂函数创建: {factory_cell.__class__.__name__}[{factory_cell.id}]")
    
    print("\n✓ 所有预测细胞创建成功！")


async def test_time_series_prediction():
    """测试时间序列预测"""
    print("\n" + "="*60)
    print("[Test 2] 时间序列预测测试")
    print("="*60)
    
    predictor = TimeSeriesPredictor()
    
    # 训练模型
    historical_data = [
        {'date': '2024-01-01', 'value': 100.0},
        {'date': '2024-01-02', 'value': 102.0},
        {'date': '2024-01-03', 'value': 105.0},
        {'date': '2024-01-04', 'value': 103.0},
        {'date': '2024-01-05', 'value': 108.0},
    ]
    predictor.train('sales', historical_data)
    print("✓ 训练销售预测模型")
    
    # 基准情景预测
    result = predictor.predict('sales', horizon=7, scenario=ScenarioType.BASELINE)
    print(f"✓ 基准情景预测: {len(result.predictions)} 个时间点")
    print(f"  - 置信度: {result.confidence:.2f}")
    print(f"  - 第一个预测值: {result.predictions[0]['value']}")
    
    # 乐观情景预测
    result_optimistic = predictor.predict('sales', horizon=7, scenario=ScenarioType.OPTIMISTIC)
    print(f"✓ 乐观情景预测: 置信度 {result_optimistic.confidence:.2f}")
    
    # 悲观情景预测
    result_pessimistic = predictor.predict('sales', horizon=7, scenario=ScenarioType.PESSIMISTIC)
    print(f"✓ 悲观情景预测: 置信度 {result_pessimistic.confidence:.2f}")
    
    print("\n✓ 时间序列预测测试完成！")


async def test_scenario_analysis():
    """测试情景分析"""
    print("\n" + "="*60)
    print("[Test 3] 情景分析测试")
    print("="*60)
    
    predictor = PredictionCell()
    
    # 处理情景分析请求
    signal = {
        'type': 'SCENARIO_ANALYSIS',
        'data_type': 'revenue',
        'horizon': 30
    }
    
    result = await predictor.process(signal)
    print(f"✓ 情景分析完成")
    print(f"  - 情景数量: {len(result['scenarios'])}")
    
    for scenario_name, scenario_data in result['scenarios'].items():
        avg_value = sum(p['value'] for p in scenario_data['predictions']) / len(scenario_data['predictions'])
        print(f"  - {scenario_name}: 平均预测值 {avg_value:.2f}, 置信度 {scenario_data['confidence']:.2f}")
    
    print("\n✓ 情景分析测试完成！")


async def test_trend_analysis():
    """测试趋势分析"""
    print("\n" + "="*60)
    print("[Test 4] 趋势分析测试")
    print("="*60)
    
    predictor = PredictionCell()
    
    # 上升趋势数据
    upward_data = [
        {'value': 100}, {'value': 102}, {'value': 105}, {'value': 108}, 
        {'value': 110}, {'value': 115}, {'value': 118}, {'value': 120}
    ]
    trends = predictor.analyze_trends(upward_data)
    print(f"✓ 上升趋势分析: {trends[0].label} (置信度: {trends[0].confidence:.2f})")
    
    # 下降趋势数据
    downward_data = [
        {'value': 120}, {'value': 118}, {'value': 115}, {'value': 110}, 
        {'value': 108}, {'value': 105}, {'value': 102}, {'value': 100}
    ]
    trends = predictor.analyze_trends(downward_data)
    print(f"✓ 下降趋势分析: {trends[0].label} (置信度: {trends[0].confidence:.2f})")
    
    # 稳定数据
    stable_data = [
        {'value': 100}, {'value': 101}, {'value': 99}, {'value': 100}, 
        {'value': 102}, {'value': 99}, {'value': 101}, {'value': 100}
    ]
    trends = predictor.analyze_trends(stable_data)
    print(f"✓ 稳定趋势分析: {trends[0].label} (置信度: {trends[0].confidence:.2f})")
    
    print("\n✓ 趋势分析测试完成！")


async def test_resource_prediction():
    """测试资源需求预测"""
    print("\n" + "="*60)
    print("[Test 5] 资源需求预测测试")
    print("="*60)
    
    predictor = ResourcePredictor()
    
    # 预测资源需求
    result = predictor.predict_resource需求('cpu', horizon=30, growth_rate=0.05)
    print(f"✓ 资源需求预测完成")
    print(f"  - 当前容量: {result['current_capacity']}")
    print(f"  - 需要扩容: {'是' if result['needs_expansion'] else '否'}")
    print(f"  - 扩容时间: {result['expansion_time_days']} 天" if result['expansion_time_days'] else "  - 短期内无需扩容")
    print(f"  - 建议容量: {result['recommended_capacity']}")
    
    print("\n✓ 资源需求预测测试完成！")


async def test_health_prediction():
    """测试系统健康预测"""
    print("\n" + "="*60)
    print("[Test 6] 系统健康预测测试")
    print("="*60)
    
    predictor = HealthPredictor()
    
    # 模拟系统指标
    metrics = {
        'cpu_usage': [45, 48, 52, 55, 58, 62, 65],
        'memory_usage': [60, 62, 64, 65, 68, 70, 72],
        'disk_io': [30, 32, 35, 38, 40, 42, 45],
    }
    
    result = predictor.predict_system_health(metrics, horizon=7)
    print(f"✓ 系统健康预测完成")
    print(f"  - 总体风险: {result['overall_risk']:.2f}")
    print(f"  - 警报级别: {result['alert_level']}")
    
    print("  - 指标预测:")
    for pred in result['predictions']:
        status = "⚠️" if pred['alert'] else "✅"
        print(f"    {status} {pred['metric']}: 当前={pred['current_value']}%, 风险={pred['risk_score']:.2f}")
    
    print("  - 建议:")
    for rec in result['recommendations']:
        print(f"    • {rec}")
    
    print("\n✓ 系统健康预测测试完成！")


async def test_prediction_cell_signal_processing():
    """测试预测细胞信号处理"""
    print("\n" + "="*60)
    print("[Test 7] 预测细胞信号处理测试")
    print("="*60)
    
    predictor = PredictionCell()
    
    # 训练请求
    train_signal = {
        'type': 'TRAIN_REQUEST',
        'data_type': 'user_activity',
        'data': [
            {'date': '2024-01-01', 'value': 1000},
            {'date': '2024-01-02', 'value': 1200},
            {'date': '2024-01-03', 'value': 1100},
        ]
    }
    result = await predictor.process(train_signal)
    print(f"✓ 训练请求处理: {result['success']}")
    
    # 预测请求
    predict_signal = {
        'type': 'PREDICT_REQUEST',
        'data_type': 'user_activity',
        'horizon': 7,
        'scenario': 'baseline',
        'method': 'hybrid'
    }
    result = await predictor.process(predict_signal)
    print(f"✓ 预测请求处理: {result['success']}")
    print(f"  - 预测数量: {len(result['data']['predictions'])}")
    
    # 性能评估
    performance = predictor.evaluate_performance()
    print(f"✓ 性能评估: 准确率={performance['accuracy']:.2f}, 置信度={performance['confidence']:.2f}")
    
    print("\n✓ 预测细胞信号处理测试完成！")


async def test_predictor_types():
    """测试不同预测器类型"""
    print("\n" + "="*60)
    print("[Test 8] 预测器类型测试")
    print("="*60)
    
    # 使用工厂函数创建不同类型的预测细胞
    predictors = [
        ('prediction', PredictionCell),
        ('timeseries', TimeSeriesPredictor),
        ('resource', ResourcePredictor),
        ('health', HealthPredictor),
    ]
    
    for cell_type, expected_class in predictors:
        cell = create_cell(cell_type)
        assert isinstance(cell, expected_class), f"Expected {expected_class.__name__}, got {cell.__class__.__name__}"
        print(f"✓ 创建 {cell_type} 细胞: {cell.__class__.__name__}[{cell.id}]")
    
    print("\n✓ 预测器类型测试完成！")


async def main():
    """运行所有测试"""
    print("="*60)
    print("预测细胞测试套件")
    print("="*60)
    
    await test_prediction_cell_creation()
    await test_time_series_prediction()
    await test_scenario_analysis()
    await test_trend_analysis()
    await test_resource_prediction()
    await test_health_prediction()
    await test_prediction_cell_signal_processing()
    await test_predictor_types()
    
    print("\n" + "="*60)
    print("所有预测细胞测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())