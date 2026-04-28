"""
llmfit 集成功能测试

测试硬件检测、模型评分和模型推荐功能
"""

import time


def test_hardware_detector():
    """测试硬件检测"""
    print("=== 测试硬件检测 ===")
    
    from client.src.business.llmfit import HardwareDetector, HardwareBackend
    
    detector = HardwareDetector()
    spec = detector.detect()
    
    print(f"硬件配置:")
    print(f"  CPU: {spec.cpu_model} ({spec.cpu_cores} 核心)")
    print(f"  RAM: {spec.ram_gb:.1f} GB ({spec.ram_available_gb:.1f} GB 可用)")
    print(f"  GPU: {spec.gpu_count} x {spec.gpu_name} ({spec.gpu_memory_gb:.1f} GB VRAM)")
    print(f"  后端: {spec.backend.value}")
    print(f"  OS: {spec.os_name} {spec.os_version}")
    print(f"  Python: {spec.python_version}")
    print(f"  Apple Silicon: {spec.is_apple_silicon}")
    
    # 测试估算模型要求
    req = detector.get_model_requirements("llama-3.1-8b", "fp16")
    print(f"\n模型要求估算 (llama-3.1-8b fp16):")
    print(f"  最小 RAM: {req.min_ram_gb:.1f} GB")
    print(f"  最小 VRAM: {req.min_vram_gb:.1f} GB")
    print(f"  最小 CPU 核心: {req.min_cpu_cores}")
    
    print("\n硬件检测测试完成!")


def test_model_scorer():
    """测试模型评分"""
    print("\n=== 测试模型评分 ===")
    
    from client.src.business.llmfit import (
        HardwareDetector,
        ModelScorer,
        ModelInfo,
    )
    
    # 检测硬件
    detector = HardwareDetector()
    hardware = detector.detect()
    
    # 创建评分器
    scorer = ModelScorer()
    scorer.set_hardware(hardware)
    
    # 测试评分
    models = [
        ModelInfo(
            name="llama-3.2-1b",
            provider="Meta",
            params=1.0,
            context_length=128000,
            quantization="bf16",
            base_score=0.75,
            use_cases=["general"],
        ),
        ModelInfo(
            name="llama-3.1-8b",
            provider="Meta",
            params=8.0,
            context_length=128000,
            quantization="fp16",
            base_score=0.85,
            use_cases=["general", "coding"],
        ),
        ModelInfo(
            name="qwen-2.5-7b",
            provider="Alibaba",
            params=7.0,
            context_length=32768,
            quantization="fp16",
            base_score=0.83,
            use_cases=["general", "coding"],
        ),
    ]
    
    print(f"评分 {len(models)} 个模型...\n")
    
    for model in models:
        score = scorer.score(model, hardware)
        print(f"模型: {model.name}")
        print(f"  参数量: {model.params}B")
        print(f"  量化: {model.quantization}")
        print(f"  质量评分: {score.quality:.3f}")
        print(f"  速度评分: {score.speed:.3f}")
        print(f"  适配度评分: {score.fit:.3f}")
        print(f"  上下文评分: {score.context:.3f}")
        print(f"  综合评分: {score.composite:.3f}")
        print()
    
    print("\n模型评分测试完成!")


def test_model_recommender():
    """测试模型推荐"""
    print("\n=== 测试模型推荐 ===")
    
    from client.src.business.llmfit import ModelRecommender, UseCase
    
    recommender = ModelRecommender()
    
    # 显示硬件摘要
    hardware = recommender.detect_hardware()
    print(recommender.get_hardware_summary(hardware))
    
    # 测试通用推荐
    print("\n--- 通用场景推荐 ---")
    result = recommender.recommend(
        hardware_spec=hardware,
        use_case=UseCase.GENERAL,
        top_k=5,
    )
    
    print(f"共评估 {result.total_models_scored} 个模型")
    print(f"推荐 {len(result.recommendations)} 个:\n")
    
    for i, rec in enumerate(result.recommendations, 1):
        print(f"{i}. {rec.model.name} ({rec.model.provider})")
        print(f"   参数量: {rec.model.params}B | 量化: {rec.recommended_quantization}")
        print(f"   适配级别: {rec.fit_level}")
        print(f"   综合评分: {rec.score.composite:.3f}")
        print(f"   估计速度: {rec.estimated_speed:.1f} tok/s")
        if rec.notes:
            print(f"   备注: {'; '.join(rec.notes)}")
        print()
    
    # 测试编程场景推荐
    print("\n--- 编程场景推荐 ---")
    coding_result = recommender.recommend(
        hardware_spec=hardware,
        use_case=UseCase.CODING,
        top_k=3,
    )
    
    print(f"推荐 {len(coding_result.recommendations)} 个:\n")
    
    for i, rec in enumerate(coding_result.recommendations, 1):
        print(f"{i}. {rec.model.name} ({rec.model.provider})")
        print(f"   参数量: {rec.model.params}B | 量化: {rec.recommended_quantization}")
        print(f"   综合评分: {rec.score.composite:.3f}")
        print()
    
    print("模型推荐测试完成!")


def test_model_database():
    """测试模型数据库"""
    print("\n=== 测试模型数据库 ===")
    
    from client.src.business.llmfit import ModelDatabase, UseCase, HardwareDetector
    
    db = ModelDatabase()
    print(f"模型数据库共有 {len(db.list_all())} 个模型\n")
    
    # 测试使用场景筛选
    coding_models = db.filter_by_use_case(UseCase.CODING)
    print(f"编程模型: {len(coding_models)} 个")
    for m in coding_models[:5]:
        print(f"  - {m.name} ({m.params}B)")
    
    # 测试硬件筛选
    detector = HardwareDetector()
    hardware = detector.detect()
    
    runnable_models = db.filter_runnable(hardware)
    print(f"\n当前硬件可运行模型: {len(runnable_models)} 个")
    for m in runnable_models[:5]:
        print(f"  - {m.name} ({m.params}B)")
    
    print("\n模型数据库测试完成!")


def test_recommendation_result():
    """测试推荐结果"""
    print("\n=== 测试推荐结果 ===")
    
    from client.src.business.llmfit import ModelRecommender, UseCase
    
    recommender = ModelRecommender()
    hardware = recommender.detect_hardware()
    
    result = recommender.recommend(
        hardware_spec=hardware,
        use_case=UseCase.GENERAL,
        top_k=3,
    )
    
    print(f"推荐结果:")
    print(f"  硬件: {result.hardware.cpu_model}")
    print(f"  场景: {result.use_case.value}")
    print(f"  评分模型数: {result.total_models_scored}")
    print(f"  推荐数量: {len(result.recommendations)}")
    print(f"  时间戳: {result.timestamp}")
    
    print("\n推荐详情:")
    for i, rec in enumerate(result.recommendations, 1):
        print(f"\n{i}. {rec.model.name}")
        print(f"   提供商: {rec.model.provider}")
        print(f"   参数量: {rec.model.params}B")
        print(f"   量化: {rec.recommended_quantization}")
        print(f"   适配级别: {rec.fit_level}")
        print(f"   综合评分: {rec.score.composite:.4f}")
        print(f"   质量: {rec.score.quality:.4f} | 速度: {rec.score.speed:.4f} | 适配: {rec.score.fit:.4f} | 上下文: {rec.score.context:.4f}")
        print(f"   估计速度: {rec.estimated_speed:.2f} tok/s")
        if rec.notes:
            print(f"   备注: {rec.notes}")
    
    print("\n推荐结果测试完成!")


if __name__ == "__main__":
    print("=" * 60)
    print("llmfit 集成功能测试")
    print("=" * 60)
    
    try:
        test_hardware_detector()
        test_model_scorer()
        test_model_recommender()
        test_model_database()
        test_recommendation_result()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成")
