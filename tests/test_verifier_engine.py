"""
VerifierEngine 单元测试

测试 OS 级通用验证引擎的核心功能：
1. 数据结构（ScoreTokenMapper, VerificationConfig, VerificationCriteria）
2. 验证引擎初始化
3. 评估标准注册中心
4. 预置评估标准
5. GlobalModelRouter 集成接口

注意：不测试需要 Ollama 运行的部分（_call_ollama_logprobs），
     那部分需要集成测试。
"""

import sys
import os
import unittest

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def run_test(name, fn):
    """运行单个测试并打印结果"""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    try:
        fn()
        print(f"  ✅ PASS")
        return True
    except AssertionError as e:
        print(f"  ❌ FAIL: {e}")
        return False
    except Exception as e:
        print(f"  ❌ ERROR: {type(e).__name__}: {e}")
        return False


# ── 测试 1: ScoreTokenMapper ─────────────────────────────────

def test_score_token_mapper():
    from client.src.business.verifier_engine import ScoreTokenMapper

    # 字母模式
    print("  [1.1] 字母映射 A→1, T→20")
    assert ScoreTokenMapper.token_to_score("A") == 1, "A should be 1"
    assert ScoreTokenMapper.token_to_score("T") == 20, "T should be 20"
    assert ScoreTokenMapper.token_to_score("J") == 10, "J should be 10"
    assert ScoreTokenMapper.token_to_score("a") == 1, "a should be 1"
    assert ScoreTokenMapper.token_to_score("t") == 20, "t should be 20"
    print("      ✅ 字母映射正确")

    # 数字模式
    print("  [1.2] 数字映射")
    assert ScoreTokenMapper.token_to_score("1") == 1, "1 should be 1"
    assert ScoreTokenMapper.token_to_score("20") == 20, "20 should be 20"
    assert ScoreTokenMapper.token_to_score("10") == 10, "10 should be 10"
    assert ScoreTokenMapper.token_to_score(" 5 ") == 5, "' 5 ' should be 5"
    print("      ✅ 数字映射正确")

    # 边界
    print("  [1.3] 边界值")
    assert ScoreTokenMapper.token_to_score("Z") == 1, "Z should fallback to 1"
    assert ScoreTokenMapper.token_to_score("xyz") == 1, "xyz should fallback to 1"
    assert ScoreTokenMapper.token_to_score("0") == 1, "0 should clamp to 1"
    assert ScoreTokenMapper.token_to_score("99") == 20, "99 should clamp to 20"
    print("      ✅ 边界值正确")

    # score_to_token
    print("  [1.4] 反向映射")
    assert ScoreTokenMapper.score_to_token(1, "letter") == "A"
    assert ScoreTokenMapper.score_to_token(20, "letter") == "T"
    assert ScoreTokenMapper.score_to_token(1, "number") == "1"
    assert ScoreTokenMapper.score_to_token(15, "number") == "15"
    print("      ✅ 反向映射正确")

    # 归一化
    print("  [1.5] 归一化")
    assert ScoreTokenMapper.normalize(1) == 0.0
    assert ScoreTokenMapper.normalize(20) == 1.0
    assert abs(ScoreTokenMapper.normalize(10) - 0.4737) < 0.01
    print("      ✅ 归一化正确")


# ── 测试 2: VerificationConfig + VerificationCriteria ────────

def test_data_structures():
    from client.src.business.verifier_engine import (
        VerificationConfig, VerificationCriteria,
        ScoringMode, SelectionStrategy,
    )

    print("  [2.1] VerificationCriteria 默认值")
    c = VerificationCriteria(name="测试", description="测试标准")
    assert c.name == "测试"
    assert c.weight == 1.0
    assert c.granularity == 20
    assert c.scoring_mode == ScoringMode.GRANULARITY
    assert c.threshold == 0.0
    print("      ✅ 默认值正确")

    print("  [2.2] VerificationCriteria prompt 文本生成")
    text = c.to_prompt_text()
    assert "测试" in text
    assert "20" in text  # 粒度
    print(f"      Prompt: {text[:80]}...")
    print("      ✅ Prompt 生成正确")

    print("  [2.3] VerificationConfig 默认值")
    cfg = VerificationConfig()
    assert cfg.granularity == 20
    assert cfg.n_verifications == 3
    assert cfg.model == ""  # 不硬编码，从系统配置读取
    assert cfg.temperature == 0.1
    assert cfg.num_predict == 5
    assert cfg.selection_strategy == SelectionStrategy.ROUND_ROBIN
    assert cfg.cache_enabled == True
    print("      ✅ 默认配置正确")

    print("  [2.4] VerificationConfig 自定义")
    cfg2 = VerificationConfig(
        granularity=10,
        n_verifications=2,
        model="qwen2.5:1.5b",
        threshold=8.0,
        selection_strategy=SelectionStrategy.BEST_OF_N,
    )
    assert cfg2.granularity == 10
    assert cfg2.n_verifications == 2
    assert cfg2.model == "qwen2.5:1.5b"
    assert cfg2.threshold == 8.0
    print("      ✅ 自定义配置正确")


# ── 测试 3: VerificationResult ───────────────────────────────

def test_verification_result():
    from client.src.business.verifier_engine import VerificationResult, BatchVerificationResult

    print("  [3.1] VerificationResult 默认值")
    r = VerificationResult(candidate_id="test_1", content="test content")
    assert r.total_reward == 0.0
    assert r.wins == 0
    assert r.passed == False
    assert r.criteria_rewards == {}
    print("      ✅ 默认值正确")

    print("  [3.2] BatchVerificationResult")
    batch = BatchVerificationResult(task_description="测试任务")
    batch.candidates.append(r)
    batch.best_candidate_id = "test_1"
    assert batch.total_candidates == 0  # 需手动设置
    assert len(batch.candidates) == 1
    print("      ✅ 批量结果正确")


# ── 测试 4: VerifierRegistry ─────────────────────────────────

def test_verifier_registry():
    from client.src.business.verifier_engine import (
        VerifierRegistry, VerificationCriteria, ScoringMode,
    )

    print("  [4.1] 注册模块")
    registry = VerifierRegistry()

    criteria = [
        VerificationCriteria(name="标准A", description="测试标准A", weight=1.5),
        VerificationCriteria(name="标准B", description="测试标准B", weight=1.0),
    ]
    registry.register("test_module", criteria, {"granularity": 10})

    assert len(registry.list_modules()) == 1
    assert "test_module" in registry.list_modules()
    print("      ✅ 注册成功")

    print("  [4.2] 获取标准")
    retrieved = registry.get_criteria("test_module")
    assert len(retrieved) == 2
    assert retrieved[0].name == "标准A"
    assert retrieved[0].weight == 1.5
    assert retrieved[1].weight == 1.0
    print("      ✅ 获取标准正确")

    print("  [4.3] 获取配置覆盖")
    override = registry.get_config_override("test_module")
    assert override == {"granularity": 10}
    print("      ✅ 配置覆盖正确")

    print("  [4.4] 注销模块")
    registry.unregister("test_module")
    assert len(registry.list_modules()) == 0
    assert registry.get_criteria("test_module") == []
    print("      ✅ 注销成功")


# ── 测试 5: 预置评估标准 ─────────────────────────────────────

def test_preset_criteria():
    from client.src.business.verifier_engine import (
        get_universal_criteria,
        get_ei_agent_criteria,
        get_fusion_rag_criteria,
        get_code_generation_criteria,
    )

    print("  [5.1] 通用标准 (universal)")
    criteria = get_universal_criteria()
    assert len(criteria) == 3
    names = [c.name for c in criteria]
    assert "准确性" in names
    assert "完整性" in names
    assert "相关性" in names
    # 准确性权重最高
    accuracy = next(c for c in criteria if c.name == "准确性")
    assert accuracy.weight == 1.5
    print(f"      ✅ 3 条标准: {names}")

    print("  [5.2] 环评标准 (ei_agent)")
    criteria = get_ei_agent_criteria()
    assert len(criteria) == 7
    names = [c.name for c in criteria]
    assert "法规符合性" in names
    assert "数据准确性" in names
    assert "风险识别" in names
    print(f"      ✅ 7 条标准: {names}")

    print("  [5.3] 检索增强标准 (fusion_rag)")
    criteria = get_fusion_rag_criteria()
    assert len(criteria) == 3
    names = [c.name for c in criteria]
    assert "检索相关性" in names
    print(f"      ✅ 3 条标准: {names}")

    print("  [5.4] 代码生成标准 (code_generation)")
    criteria = get_code_generation_criteria()
    assert len(criteria) == 3
    names = [c.name for c in criteria]
    assert "正确性" in names
    assert "安全性" in names
    # 正确性权重最高
    correctness = next(c for c in criteria if c.name == "正确性")
    assert correctness.weight == 2.0
    print(f"      ✅ 3 条标准: {names}")


# ── 测试 6: auto_register_default_modules ────────────────────

def test_auto_register():
    from client.src.business.verifier_engine import (
        VerifierRegistry, auto_register_default_modules,
    )

    print("  [6.1] 自动注册内置模块")
    # 使用新实例避免与其他测试冲突
    registry = auto_register_default_modules()

    modules = registry.list_modules()
    assert "universal" in modules
    assert "ei_agent" in modules
    assert "fusion_rag" in modules
    assert "code_generation" in modules
    print(f"      ✅ 已注册 {len(modules)} 个模块: {modules}")

    print("  [6.2] 环评模块配置覆盖")
    ei_override = registry.get_config_override("ei_agent")
    assert ei_override.get("n_verifications") == 4
    assert ei_override.get("threshold") == 12.0
    print(f"      ✅ 环评配置: {ei_override}")

    print("  [6.3] 各模块标准数量")
    for mod in modules:
        criteria = registry.get_criteria(mod)
        print(f"      {mod}: {len(criteria)} 条标准")
        assert len(criteria) > 0


# ── 测试 7: VerifierEngine 初始化 ─────────────────────────────

def test_engine_init():
    from client.src.business.verifier_engine import (
        VerifierEngine, VerificationConfig, get_verifier_engine,
    )

    print("  [7.1] 默认配置初始化")
    engine = VerifierEngine()
    assert engine.config.granularity == 20
    assert engine.config.n_verifications == 3
    assert len(engine._cache) == 0
    assert len(engine._usage_history) == 0
    print("      ✅ 默认初始化正确")

    print("  [7.2] 自定义配置初始化")
    cfg = VerificationConfig(
        granularity=10,
        n_verifications=2,
        model="qwen2.5:1.5b",
        cache_enabled=False,
    )
    engine2 = VerifierEngine(cfg)
    assert engine2.config.granularity == 10
    assert engine2.config.cache_enabled == False
    print("      ✅ 自定义初始化正确")

    print("  [7.3] 全局单例")
    # 清除旧单例
    import client.src.business.verifier_engine as ve_mod
    ve_mod._engine_instance = None
    engine3 = get_verifier_engine()
    engine4 = get_verifier_engine()
    assert engine3 is engine4, "应该是同一个实例"
    print("      ✅ 全局单例正确")


# ── 测试 8: 验证 Prompt 构造 ─────────────────────────────────

def test_prompt_construction():
    from client.src.business.verifier_engine import (
        VerifierEngine, VerificationConfig, VerificationCriteria, ScoringMode,
    )

    engine = VerifierEngine()

    print("  [8.1] GRANULARITY 模式 prompt")
    c1 = VerificationCriteria(
        name="准确性",
        description="回答是否正确",
        scoring_mode=ScoringMode.GRANULARITY,
        granularity=20,
    )
    prompt1 = engine._build_verification_prompt("解释量子力学", "量子力学是...", c1)
    assert "准确性" in prompt1
    assert "A-T" in prompt1
    assert "1-20" not in prompt1 or "20" in prompt1
    print(f"      Prompt 片段: ...{prompt1[-60:]}")
    print("      ✅ GRANULARITY prompt 正确")

    print("  [8.2] BINARY 模式 prompt")
    c2 = VerificationCriteria(
        name="合规性",
        description="是否符合法规",
        scoring_mode=ScoringMode.BINARY,
    )
    prompt2 = engine._build_verification_prompt("检查环评报告", "报告内容...", c2)
    assert "通过" in prompt2
    assert "不通过" in prompt2
    print("      ✅ BINARY prompt 正确")

    print("  [8.3] LIKERT 模式 prompt")
    c3 = VerificationCriteria(
        name="满意度",
        description="用户满意度评估",
        scoring_mode=ScoringMode.LIKERT,
        granularity=10,
    )
    prompt3 = engine._build_verification_prompt("评估体验", "体验描述...", c3)
    assert "1-10" in prompt3
    assert "李克特" in prompt3
    print("      ✅ LIKERT prompt 正确")

    print("  [8.4] 长文本截断")
    long_content = "x" * 5000
    prompt4 = engine._build_verification_prompt("任务", long_content, c1)
    assert "截取前2000字" in prompt4
    # 实际注入的内容应该被截断
    assert len(prompt4) < 6000  # 不会包含全部 5000 字
    print("      ✅ 长文本截断正确")


# ── 测试 9: 概率评分提取（mock） ──────────────────────────────

def test_score_extraction():
    from client.src.business.verifier_engine import VerifierEngine

    engine = VerifierEngine()

    print("  [9.1] 正常 logprobs 响应")
    mock_response = {
        "message": {"role": "assistant", "content": "M"},
        "logprobs": [
            {
                "token": "M",
                "logprob": -0.2,
                "top_logprobs": [
                    {"token": "M", "logprob": -0.2},
                    {"token": "L", "logprob": -1.5},
                    {"token": "N", "logprob": -2.0},
                    {"token": "K", "logprob": -2.5},
                ],
            }
        ],
    }
    score, probs = engine._extract_probabilistic_score(mock_response)
    assert 12 <= score <= 14, f"期望分约13(M)，实际{score}"  # M=13
    assert "M" in probs
    print(f"      期望分: {score:.2f}, 概率分布: {probs}")
    print("      ✅ 正常响应提取正确")

    print("  [9.2] 无 logprobs（fallback）")
    mock_no_logprobs = {
        "message": {"role": "assistant", "content": "H"},
    }
    score2, probs2 = engine._extract_probabilistic_score(mock_no_logprobs)
    assert score2 == 8.0, f"H=8, 实际{score2}"  # H=8
    print(f"      Fallback 分: {score2}")
    print("      ✅ Fallback 正确")

    print("  [9.3] 数字评分 fallback")
    mock_number = {
        "message": {"role": "assistant", "content": "15"},
    }
    score3, probs3 = engine._extract_probabilistic_score(mock_number)
    assert score3 == 15.0, f"15, 实际{score3}"
    print("      ✅ 数字评分正确")

    print("  [9.4] 空 top_logprobs（用实际 token）")
    mock_empty_top = {
        "message": {"role": "assistant", "content": "A"},
        "logprobs": [
            {"token": "A", "logprob": -0.1, "top_logprobs": []},
        ],
    }
    score4, probs4 = engine._extract_probabilistic_score(mock_empty_top)
    assert score4 == 1.0, f"A=1, 实际{score4}"
    print("      ✅ 空 top_logprobs 正确")


# ── 测试 10: 使用统计 ───────────────────────────────────────

def test_usage_stats():
    from client.src.business.verifier_engine import (
        VerifierEngine, VerificationConfig, VerificationResult,
        VerificationCriteria, SelectionStrategy,
        BatchVerificationResult,
    )

    print("  [10.1] 空统计")
    engine = VerifierEngine()
    stats = engine.get_usage_stats()
    assert stats["total_verifications"] == 0
    print("      ✅ 空统计正确")

    print("  [10.2] 模拟使用后统计")
    # 手动注入历史
    engine._usage_history = [
        {
            "timestamp": 1000.0,
            "task": "test task",
            "n_candidates": 3,
            "n_criteria": 3,
            "strategy": "round_robin",
            "best_id": "0",
            "best_reward": 15.0,
            "elapsed": 2.5,
        },
        {
            "timestamp": 2000.0,
            "task": "test task 2",
            "n_candidates": 2,
            "n_criteria": 2,
            "strategy": "best_of_n",
            "best_id": "1",
            "best_reward": 18.0,
            "elapsed": 1.8,
        },
    ]
    stats = engine.get_usage_stats()
    assert stats["total_verifications"] == 2
    assert stats["avg_best_reward"] == 16.5
    assert abs(stats["avg_elapsed_seconds"] - 2.15) < 0.01
    print(f"      ✅ 统计: {stats}")

    print("  [10.3] 缓存清除")
    engine._cache = {"key": "value"}
    engine.clear_cache()
    assert len(engine._cache) == 0
    print("      ✅ 缓存清除正确")


# ── 测试 11: GlobalModelRouter 集成接口 ──────────────────────

def test_router_integration():
    from client.src.business.verifier_engine import get_verifier_engine, VerifierRegistry

    print("  [11.1] VerifierEngine 可作为独立模块导入")
    engine = get_verifier_engine()
    assert engine is not None
    print("      ✅ 独立导入成功")

    print("  [11.2] VerifierRegistry 单例")
    r1 = VerifierRegistry.get_instance()
    r2 = VerifierRegistry.get_instance()
    assert r1 is r2
    print("      ✅ 单例正确")

    print("  [11.3] GlobalModelRouter 有 verify 参数")
    import inspect
    # 检查签名中是否包含 verify
    from client.src.business.global_model_router import GlobalModelRouter, call_model_sync
    sig = inspect.signature(GlobalModelRouter.call_model)
    params = list(sig.parameters.keys())
    assert "verify" in params, f"verify not in {params}"
    print(f"      ✅ call_model 参数: {params}")

    sig2 = inspect.signature(call_model_sync)
    params2 = list(sig2.parameters.keys())
    assert "verify" in params2, f"verify not in {params2}"
    print(f"      ✅ call_model_sync 参数: {params2}")

    print("  [11.4] verify 参数是 Optional[dict]")
    verify_param = sig.parameters["verify"]
    assert verify_param.default is None
    print("      ✅ verify 默认值为 None")


# ══════════════════════════════════════════════════════════════
# 运行所有测试
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  VerifierEngine 测试套件                                ║")
    print("║  OS 级通用验证基础设施 (LLM-as-a-Verifier)               ║")
    print("╚══════════════════════════════════════════════════════════╝")

    tests = [
        ("测试1: ScoreTokenMapper 分数映射", test_score_token_mapper),
        ("测试2: 数据结构", test_data_structures),
        ("测试3: VerificationResult", test_verification_result),
        ("测试4: VerifierRegistry 注册中心", test_verifier_registry),
        ("测试5: 预置评估标准", test_preset_criteria),
        ("测试6: 自动注册内置模块", test_auto_register),
        ("测试7: VerifierEngine 初始化", test_engine_init),
        ("测试8: 验证 Prompt 构造", test_prompt_construction),
        ("测试9: 概率评分提取 (mock)", test_score_extraction),
        ("测试10: 使用统计", test_usage_stats),
        ("测试11: GlobalModelRouter 集成", test_router_integration),
    ]

    results = []
    for name, fn in tests:
        results.append(run_test(name, fn))

    # 汇总
    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"\n{'='*60}")
    print(f"  测试结果: {passed}/{total} 通过", end="")
    if failed:
        print(f", {failed} 失败 ❌")
    else:
        print(f" ✅ 全部通过!")
    print(f"{'='*60}")
