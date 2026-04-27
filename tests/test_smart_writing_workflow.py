# -*- coding: utf-8 -*-
"""
SmartWritingWorkflow 测试
"""

import sys
import time

# 添加项目根目录
sys.path.insert(0, "f:/mhzyapp/LivingTreeAlAgent")

from core.smart_writing.unified_workflow import (
    SmartWritingWorkflow,
    WritingConfig,
    WritingStage,
)


def test_workflow():
    """测试智能写作工作流"""
    print("=" * 60)
    print("SmartWritingWorkflow 测试")
    print("=" * 60)
    
    # 创建工作流
    config = WritingConfig(
        enable_knowledge_retrieval=True,
        enable_deep_search=False,  # 跳过深度搜索加速测试
        enable_ai_review=True,
        enable_debate=False,  # 跳过辩论加速测试
        enable_virtual_meeting=False,
        use_knowledge_base=False,
        use_deep_search=False,
    )
    
    workflow = SmartWritingWorkflow(config)
    
    # 测试需求
    test_cases = [
        {
            "requirement": "写一份关于智慧工厂项目的可行性研究报告",
            "document_type": "feasibility_report",
            "project_name": "智慧工厂项目",
        },
        {
            "requirement": "分析Python异步编程",
            "document_type": "general",
            "project_name": "Python异步编程分析",
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{'─' * 60}")
        print(f"测试用例 {i}: {case['requirement'][:30]}...")
        print(f"{'─' * 60}")
        
        start_time = time.time()
        
        try:
            result = workflow.execute(
                requirement=case["requirement"],
                document_type=case["document_type"],
                project_name=case["project_name"],
            )
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ 执行成功！耗时: {elapsed:.2f}s")
            print(f"  阶段: {result.current_stage.value}")
            print(f"  审核评分: {result.review_score:.1f}")
            print(f"  审核结论: {result.review_conclusion}")
            print(f"  置信度: {result.confidence:.2f}")
            
            if result.final_content:
                print(f"  内容键: {list(result.final_content.keys())[:5]}")
            
            if result.review_issues:
                print(f"  问题数: {len(result.review_issues)}")
            
        except Exception as e:
            print(f"\n❌ 执行失败: {e}")
            import traceback
            traceback.print_exc()


def test_stream():
    """测试流式执行"""
    print("\n" + "=" * 60)
    print("流式执行测试")
    print("=" * 60)
    
    workflow = SmartWritingWorkflow()
    
    requirement = "人工智能在医疗领域的应用前景分析"
    
    print(f"\n需求: {requirement}")
    print("-" * 40)
    
    for i, stage_result in enumerate(workflow.execute_stream(requirement)):
        stage = stage_result.get("stage", "")
        progress = stage_result.get("progress", 0)
        content = stage_result.get("content", "")[:100]
        
        print(f"[{progress:3d}%] {stage}: {content}...")
        
        if stage == "completed":
            break


def test_config():
    """测试配置"""
    print("\n" + "=" * 60)
    print("配置测试")
    print("=" * 60)
    
    # 默认配置
    config = WritingConfig()
    print("\n默认配置:")
    print(f"  enable_clarification: {config.enable_clarification}")
    print(f"  enable_ai_review: {config.enable_ai_review}")
    print(f"  enable_debate: {config.enable_debate}")
    print(f"  debate_rounds: {config.debate_rounds}")
    print(f"  output_formats: {config.output_formats}")
    
    # 自定义配置
    custom_config = WritingConfig(
        enable_ai_review=True,
        enable_debate=True,
        debate_rounds=5,
        output_formats=["docx", "pdf", "markdown"],
    )
    print("\n自定义配置:")
    print(f"  debate_rounds: {custom_config.debate_rounds}")
    print(f"  output_formats: {custom_config.output_formats}")


if __name__ == "__main__":
    try:
        test_config()
        test_workflow()
        test_stream()
        print("\n" + "=" * 60)
        print("所有测试完成！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
