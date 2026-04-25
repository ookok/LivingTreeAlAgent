# test_evaluator_standalone.py - Standalone test for evaluation framework
# Bypasses core/__init__.py to avoid import issues

"""
Standalone test for EvolutionEngine Evaluator modules.

This test uses exec() to load modules directly, bypassing the potentially
broken core/__init__.py import chain.
"""

import sys
import os
from pathlib import Path

# Setup paths
EVAL_DIR = Path(__file__).parent / "core" / "evolution_engine" / "evaluator"
PROJECT_ROOT = Path(__file__).parent

# CRITICAL: Add EVAL_DIR to sys.path so "from base_evaluator import" works
sys.path.insert(0, str(EVAL_DIR))


def load_module_source(module_name: str) -> dict:
    """Load module source and return its namespace."""
    filepath = EVAL_DIR / f"{module_name}.py"
    
    if not filepath.exists():
        return {"error": f"File not found: {filepath}"}
    
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    
    namespace = {
        '__name__': module_name,
        '__file__': str(filepath),
        '__path__': str(EVAL_DIR),
        '__package__': 'evaluator',
        '__doc__': None,
    }
    
    # Add pathlib for module use
    namespace['Path'] = Path
    
    try:
        exec(source, namespace)
        return {"namespace": namespace, "source": source}
    except Exception as e:
        return {"error": f"exec failed: {e}", "source": source}


def test_base_evaluator():
    """Test base_evaluator module."""
    print("\n" + "=" * 60)
    print("Testing base_evaluator...")
    print("=" * 60)
    
    result = load_module_source("base_evaluator")
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return False
    
    ns = result["namespace"]
    
    # Check key classes exist
    required = ["MetricType", "MetricScore", "EvaluationResult", 
                 "EvaluationSuite", "EvaluationConfig", "TestCase", "BaseEvaluator"]
    
    missing = [name for name in required if name not in ns]
    if missing:
        print(f"FAIL: Missing classes: {missing}")
        return False
    
    # Test MetricType enum
    assert hasattr(ns["MetricType"], "ACCURACY"), "MetricType.ACCURACY missing"
    assert hasattr(ns["MetricType"], "BPB"), "MetricType.BPB missing"
    
    # Test helper functions
    assert "calculate_accuracy" in ns
    assert "calculate_bpb" in ns
    assert ns["calculate_accuracy"](["a", "b"], ["a", "b"]) == 100.0
    assert ns["calculate_accuracy"](["a", "b"], ["a", "c"]) == 50.0
    
    print("PASS: base_evaluator loaded successfully")
    print(f"  - MetricType values: {[e.value for e in ns['MetricType']][:5]}...")
    print(f"  - Helper functions: calculate_accuracy, calculate_bpb, etc.")
    
    return True


def test_dclm_evaluator():
    """Test DCLM CORE evaluator."""
    print("\n" + "=" * 60)
    print("Testing DCLM CORE evaluator...")
    print("=" * 60)
    
    # Load base first
    base_result = load_module_source("base_evaluator")
    if "error" in base_result:
        print(f"FAIL: base_evaluator failed: {base_result['error']}")
        return False
    
    result = load_module_source("dclm_evaluator")
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return False
    
    ns = result["namespace"]
    
    # Check key classes
    required = ["DCLMEvaluator", "DCLMScore"]
    missing = [name for name in required if name not in ns]
    if missing:
        print(f"FAIL: Missing: {missing}")
        return False
    
    # Create evaluator
    evaluator = ns["DCLMEvaluator"](str(PROJECT_ROOT), {"enabled": True})
    assert evaluator.name == "dclm"
    
    # Run evaluation
    eval_result = evaluator.evaluate()
    
    # Check result structure
    assert eval_result.evaluator_name == "dclm"
    assert len(eval_result.metrics) > 0
    assert "dclm_overall" in eval_result.metrics
    
    dclm_data = eval_result.raw_data.get("dclm")
    assert dclm_data is not None
    assert hasattr(dclm_data, "overall_score")
    
    print("PASS: DCLM evaluator loaded and ran successfully")
    print(f"  - Overall Score: {dclm_data.overall_score:.2f}")
    print(f"  - Correctness: {dclm_data.correctness:.2f}%")
    print(f"  - Syntax Quality: {dclm_data.syntax_quality:.2f}")
    print(f"  - Semantic Quality: {dclm_data.semantic_quality:.2f}")
    print(f"  - Pass Rate: {dclm_data.passed_cases}/{dclm_data.total_cases}")
    
    return True


def test_bpb_evaluator():
    """Test BPB evaluator."""
    print("\n" + "=" * 60)
    print("Testing BPB (Bits Per Byte) evaluator...")
    print("=" * 60)
    
    result = load_module_source("bpb_evaluator")
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return False
    
    ns = result["namespace"]
    
    # Check key classes
    required = ["BPBEvaluator", "BPBScore"]
    missing = [name for name in required if name not in ns]
    if missing:
        print(f"FAIL: Missing: {missing}")
        return False
    
    # Create evaluator
    evaluator = ns["BPBEvaluator"](str(PROJECT_ROOT), {"enabled": True})
    assert evaluator.name == "bpb"
    
    # Run evaluation
    eval_result = evaluator.evaluate()
    
    # Check result structure
    assert eval_result.evaluator_name == "bpb"
    assert len(eval_result.metrics) > 0
    assert "bpb_score" in eval_result.metrics
    
    bpb_data = eval_result.raw_data.get("bpb")
    assert bpb_data is not None
    assert hasattr(bpb_data, "bpb")
    
    # Get reference baselines
    baselines = evaluator.get_reference_baselines()
    
    print("PASS: BPB evaluator loaded and ran successfully")
    print(f"  - BPB Score: {bpb_data.bpb:.4f}")
    print(f"  - Perplexity: {bpb_data.perplexity:.4f}")
    print(f"  - Compression Ratio: {bpb_data.reference_bpb / bpb_data.bpb:.2f}x" if bpb_data.bpb > 0 else "  - Compression Ratio: N/A")
    print(f"  - Reference Baselines: GPT-4={baselines['gpt4']}, Claude={baselines['claude']}")
    
    return True


def test_benchmark_evaluator():
    """Test Benchmark evaluator (ARC/GSM8K/MMLU/HumanEval/MBPP)."""
    print("\n" + "=" * 60)
    print("Testing Benchmark evaluator...")
    print("=" * 60)
    
    result = load_module_source("benchmark_evaluator")
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return False
    
    ns = result["namespace"]
    
    # Check key classes
    required = ["BenchmarkEvaluator", "BenchmarkScore", "BenchmarkTask"]
    missing = [name for name in required if name in ns]
    if missing:
        print(f"FAIL: Missing: {missing}")
        return False
    
    # Create evaluator
    evaluator = ns["BenchmarkEvaluator"](str(PROJECT_ROOT), {"enabled": True})
    assert evaluator.name == "benchmark"
    
    # Run evaluation
    eval_result = evaluator.evaluate()
    
    # Check result structure
    assert eval_result.evaluator_name == "benchmark"
    assert len(eval_result.metrics) > 0
    assert "benchmark_overall" in eval_result.metrics
    
    bench_data = eval_result.raw_data.get("benchmark")
    assert bench_data is not None
    
    # Get reference scores
    ref_scores = evaluator.get_reference_scores()
    
    print("PASS: Benchmark evaluator loaded and ran successfully")
    print(f"  - Overall Score: {bench_data.overall:.2f}%")
    print(f"  - ARC: {bench_data.arc or 0:.2f}%")
    print(f"  - GSM8K: {bench_data.gsm8k or 0:.2f}%")
    print(f"  - MMLU: {bench_data.mmlu or 0:.2f}%")
    print(f"  - HumanEval: {bench_data.humaneval or 0:.2f}%")
    print(f"  - MBPP: {bench_data.mbpp or 0:.2f}%")
    print(f"  - Reference: GPT-4={ref_scores['gpt4']['arc']:.1f}%, Claude3={ref_scores['claude3']['arc']:.1f}%")
    
    return True


def test_evolution_evaluator():
    """Test Evolution Evaluator (main controller)."""
    print("\n" + "=" * 60)
    print("Testing Evolution Evaluator (main controller)...")
    print("=" * 60)
    
    # Load all evaluators first
    load_module_source("base_evaluator")
    load_module_source("dclm_evaluator")
    load_module_source("bpb_evaluator")
    load_module_source("benchmark_evaluator")
    
    result = load_module_source("evolution_evaluator")
    if "error" in result:
        print(f"FAIL: {result['error']}")
        return False
    
    ns = result["namespace"]
    
    # Check key classes
    required = ["EvolutionEvaluator", "EvaluationMode", "CapabilityDimension", 
                 "CapabilityScore", "EvolutionMetrics"]
    missing = [name for name in required if name not in ns]
    if missing:
        print(f"FAIL: Missing: {missing}")
        return False
    
    # Create evaluator
    evaluator = ns["EvolutionEvaluator"](str(PROJECT_ROOT), {
        "dclm": {"enabled": True},
        "bpb": {"enabled": True},
        "benchmark": {"enabled": True}
    })
    
    # Run evaluation in QUICK mode
    eval_result = evaluator.evaluate(mode=ns["EvaluationMode"].QUICK)
    
    # Check result
    assert eval_result.evaluator_name == "evolution_evaluator"
    assert len(eval_result.metrics) > 0
    
    # Get capability report
    report = evaluator.get_capability_report()
    
    # Get stats
    stats = evaluator.get_stats()
    
    print("PASS: Evolution Evaluator loaded and ran successfully")
    print(f"  - Enabled Evaluators: {stats['enabled_evaluators']}")
    print(f"  - Total Evaluations: {stats['total_evaluations']}")
    print(f"  - Average Score: {stats['average_score']:.2f}")
    print(f"  - Capability Level: {report['capability_level']}")
    print(f"  - Overall Capability Score: {report['overall_score']:.2f}")
    print(f"  - Dimensions evaluated: {list(report['dimensions'].keys())}")
    
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("LivingTreeAI Evolution Engine - Evaluation Framework Tests")
    print("=" * 70)
    
    tests = [
        ("Base Evaluator", test_base_evaluator),
        ("DCLM CORE Evaluator", test_dclm_evaluator),
        ("BPB Evaluator", test_bpb_evaluator),
        ("Benchmark Evaluator", test_benchmark_evaluator),
        ("Evolution Evaluator", test_evolution_evaluator),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"FAIL: {name} - Exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
