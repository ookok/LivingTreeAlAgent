#!/usr/bin/env python3
"""
生命系统与业务模块集成演示

展示生命系统如何增强现有业务模块能力。
"""

import asyncio
import sys
import os

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client', 'src', 'business'))


async def main():
    print("🌲 LivingTree AI - 生命系统集成演示")
    print("="*60)
    
    # 动态导入细胞框架模块
    try:
        from cell_framework import LifeEngine, CellRegistry, PredictionCell, ReasoningCell, LearningCell
        print("✓ 成功导入细胞框架模块")
    except Exception as e:
        print(f"✗ 导入细胞框架失败: {e}")
        return
    
    # 创建生命引擎
    life_engine = LifeEngine()
    print("✓ 创建生命引擎")
    
    # 创建细胞注册表
    registry = CellRegistry.get_instance()
    print("✓ 获取细胞注册表")
    
    # 演示增强RAG查询
    print("\n--- 演示1: 增强版RAG查询 ---")
    query = "什么是细胞AI？"
    
    # 1. 使用感知细胞解析意图
    print(f"📥 用户查询: '{query}'")
    
    # 2. 使用推理细胞分析
    reasoner = ReasoningCell()
    analysis = await reasoner.process({'type': 'analyze', 'query': query})
    print(f"🧠 推理分析: 正在分析查询意图")
    
    # 3. 使用预测细胞评估
    predictor = PredictionCell()
    confidence = predictor.predict('query_confidence', horizon=1)
    print(f"🔮 预测置信度: {confidence:.2f}")
    
    # 4. 使用学习细胞记录
    learner = LearningCell()
    await learner.process({'type': 'learn', 'data': {'query': query}})
    print(f"📚 学习记录: 查询已记录")
    
    # 演示用户画像增强
    print("\n--- 演示2: 增强版用户画像 ---")
    user_id = "demo_user"
    interaction = {"query": "帮我推荐学习资源", "type": "recommendation"}
    
    print(f"👤 用户ID: {user_id}")
    print(f"💬 交互记录: {interaction}")
    print(f"🎯 预测需求: 基于历史交互，用户可能需要学习资源推荐")
    
    # 演示综合查询接口
    print("\n--- 演示3: 综合查询接口 ---")
    queries = [
        {"query": "解释量子计算", "type": "knowledge"},
        {"query": "我的工作进度如何？", "type": "user"},
        {"query": "搜索文档", "type": "search"},
        {"query": "生成报告", "type": "task"}
    ]
    
    for q in queries:
        print(f"\n📋 查询类型: {q['type']}")
        print(f"   查询内容: {q['query']}")
        print(f"   处理路径: {_get_processing_path(q['type'])}")
    
    # 展示系统状态
    print("\n--- 系统状态 ---")
    status = life_engine.get_system_status()
    print(f"🔋 系统健康: {status['health']}")
    print(f"💡 意识水平: {status['awareness_level']:.2f}")
    print(f"🎯 当前目标: {status.get('current_goal', '无')}")
    print(f"⏱️  运行时间: {status.get('age', 0):.1f} 秒")
    
    print("\n" + "="*60)
    print("🎉 生命系统集成演示完成！")
    print("="*60)
    print("\n核心集成价值:")
    print("• 智能意图识别 → 理解用户真实需求")
    print("• 持续学习能力 → 越用越聪明")
    print("• 预测性优化 → 提前预判结果")
    print("• 动态细胞组装 → 最优处理路径")


def _get_processing_path(query_type):
    """获取查询处理路径"""
    paths = {
        'knowledge': "RAG引擎 → 知识图谱 → 推理细胞",
        'user': "用户画像 → 个性化推荐 → 学习细胞",
        'search': "搜索系统 → 结果融合 → 优化细胞",
        'task': "任务规划 → 模型选择 → 行动细胞"
    }
    return paths.get(query_type, "通用处理路径")


if __name__ == "__main__":
    asyncio.run(main())