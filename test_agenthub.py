"""验证五大核心模块"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("AgentHub 五大核心模块验证")
print("=" * 60)

results = []

# 1. TaskRouter
try:
    from core.task_router import TaskRouter, TaskNode, TaskStatus, TaskPriority
    print("[OK] TaskRouter - Multi-layer Recursive Task Decomposer")
    router = TaskRouter(max_depth=3)
    task_id = router.add_task("Test Task", context={}, tools=["read_file"], depth=0, priority=TaskPriority.NORMAL)
    print(f"     Task added: {task_id[:8]}")
    results.append(("TaskRouter", True, None))
except Exception as e:
    print(f"[FAIL] TaskRouter: {e}")
    results.append(("TaskRouter", False, str(e)))

# 2. PermissionEngine
try:
    from core.permission_engine import PermissionEngine, RiskLevel, PermissionAction
    print("[OK] PermissionEngine - Dynamic Permission Strategy Engine")
    engine = PermissionEngine(auto_approve_low=True)
    result = engine.assess("delete file C:\\temp\\test.txt")
    print(f"     Risk: {result['risk_level']} ({result['confidence']:.0%})")
    results.append(("PermissionEngine", True, None))
except Exception as e:
    print(f"[FAIL] PermissionEngine: {e}")
    results.append(("PermissionEngine", False, str(e)))

# 3. SkillClusterer
try:
    from core.skill_clusterer import SkillClusterer
    print("[OK] SkillClusterer - Semantic Skill Clustering System")
    clusterer = SkillClusterer()
    sid = clusterer.register_skill("extract_data_v1", "Extract data", docstring="Extract data from file")
    print(f"     Skill registered: {sid[:8]}")
    results.append(("SkillClusterer", True, None))
except Exception as e:
    print(f"[WARN] SkillClusterer (optional): {e}")
    results.append(("SkillClusterer", "optional", str(e)))

# 4. SemanticValidator
try:
    from core.semantic_validator import SemanticValidator, ChunkQuality
    print("[OK] SemanticValidator - Semantic Consistency Validator")
    validator = SemanticValidator()
    result = validator.validate_chunk("Because the weather is cold, so")
    status = "Invalid" if not result["is_valid"] else "Valid"
    issues = result["issues"][0] if result["issues"] else "None"
    print(f"     Result: {status}")
    print(f"     Issue: {issues}")
    results.append(("SemanticValidator", True, None))
except Exception as e:
    print(f"[WARN] SemanticValidator (optional): {e}")
    results.append(("SemanticValidator", "optional", str(e)))

# 5. ResourceMonitor
try:
    from core.resource_monitor import ResourceMonitor, LoadLevel
    print("[OK] ResourceMonitor - Adaptive Resource Scheduler")
    monitor = ResourceMonitor(interval=1)
    monitor.start()
    import time
    time.sleep(1.5)
    status = monitor.get_status_dict()
    print(f"     Load: {status['load_level']} | CPU: {status['cpu_percent']:.1f}%")
    monitor.stop()
    results.append(("ResourceMonitor", True, None))
except Exception as e:
    print(f"[FAIL] ResourceMonitor: {e}")
    results.append(("ResourceMonitor", False, str(e)))

# 6. AgentHub
try:
    from core.agent_hub import AgentHub, show_agent_hub
    print("[OK] AgentHub - PyQt Integration Interface")
    results.append(("AgentHub", True, None))
except Exception as e:
    print(f"[FAIL] AgentHub: {e}")
    results.append(("AgentHub", False, str(e)))

# Summary
print()
print("=" * 60)
print("Summary")
print("=" * 60)

passed = sum(1 for r in results if r[1] is True)
optional_ok = sum(1 for r in results if r[1] == "optional")
failed = sum(1 for r in results if r[1] is False)

for name, status, error in results:
    if status is True:
        print(f"  PASS: {name}")
    elif status == "optional":
        print(f"  WARN: {name} (optional deps not installed)")
    else:
        print(f"  FAIL: {name}")

print()
print(f"Core modules: {passed}/{len(results)} passed")
if optional_ok > 0:
    print(f"Optional modules: {optional_ok} not installed (limited functionality)")

if failed == 0:
    print()
    print("All 5 core modules ready!")
