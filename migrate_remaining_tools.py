"""
批量迁移剩余 14 个工具

使用 GenericToolAdapter 自动为现有模块生成 BaseTool 包装器。
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from loguru import logger

# 配置 loguru 移除彩色输出
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from client.src.business.tools.generic_adapter import BatchAdapter
from client.src.business.tools.tool_registry import ToolRegistry


# ============================================================
# 迁移清单（剩余 14 个工具）
# ============================================================

MIGRATION_LIST = [
    # (module_name, type, name_or_methods, tool_name_prefix)
    # type: "function", "class_method", "class_all"
    
    # 1. vector_database
    ("client.src.business.knowledge_vector_db", "class_method", "VectorDatabase", ["search", "add"]),
    
    # 2. tier_router
    ("client.src.business.search.tier_router", "class_method", "TierRouter", ["route"]),
    
    # 3. proxy_manager
    ("client.src.business.base_proxy_manager", "class_method", "ProxyManager", ["get_proxy", "test_proxy"]),
    
    # 4. content_extractor
    ("client.src.business.web_content_extractor.extractor", "class_method", "ContentExtractor", ["extract"]),
    
    # 5. document_parser
    ("client.src.business.bilingual_doc.document_parser", "class_method", "DocumentParser", ["parse"]),
    
    # 6. intelligent_ocr
    ("client.src.business.intelligent_ocr.ocr_engine", "class_method", "OCREngine", ["recognize"]),
    
    # 7. kb_auto_ingest
    ("client.src.business.knowledge_auto_ingest", "class_method", "KBAutoIngest", ["ingest"]),
    
    # 8. task_queue
    ("client.src.business.task_queue", "class_method", "TaskQueue", ["add", "get", "update_status"]),
    
    # 9. task_execution_engine
    ("client.src.business.task_execution_engine", "class_method", "TaskExecutionEngine", ["execute"]),
    
    # 10. agent_progress
    ("client.src.business.agent_progress", "class_method", "AgentProgress", ["report"]),
    
    # 11. expert_learning
    ("client.src.business.expert_learning.learning_system", "class_method", "ExpertLearningSystem", ["learn"]),
    
    # 12. skill_evolution
    ("client.src.business.skill_evolution.evolution_engine", "class_method", "SkillEvolutionEngine", ["evolve"]),
    
    # 13. experiment_loop
    ("client.src.business.experiment_loop.evolution_loop", "class_method", "ExperimentLoop", ["run"]),
    
    # 14. markitdown_converter (需新建，暂时跳过)
]


def migrate_all():
    """批量迁移所有工具"""
    print("=" * 60)
    print("批量迁移剩余工具")
    print("=" * 60)
    
    registry = ToolRegistry.get_instance()
    batch = BatchAdapter(registry=registry)
    
    migrated = []
    failed = []
    
    for item in MIGRATION_LIST:
        module_name, item_type, class_or_func_name, methods = item
        
        try:
            if item_type == "class_method":
                # 迁移类的指定方法
                for method_name in methods:
                    try:
                        adapter = GenericToolAdapter.from_class_method(
                            module_name=module_name,
                            class_name=class_or_func_name,
                            method_name=method_name,
                            tool_name=f"{class_or_func_name.lower()}_{method_name}"
                        )
                        
                        if adapter:
                            success = registry.register_tool(adapter)
                            if success:
                                migrated.append(adapter.name)
                                print(f"[PASS] 已迁移: {adapter.name}")
                            else:
                                failed.append(f"{module_name}.{class_or_func_name}.{method_name}")
                                print(f"[FAIL] 注册失败: {adapter.name}")
                    except Exception as e:
                        failed.append(f"{module_name}.{class_or_func_name}.{method_name}")
                        print(f"[FAIL] 迁移失败: {module_name}.{class_or_func_name}.{method_name} - {e}")
            
            elif item_type == "function":
                # 迁移函数
                adapter = GenericToolAdapter.from_function(
                    module_name=module_name,
                    func_name=class_or_func_name,  # 此时 class_or_func_name 是函数名
                    tool_name=methods[0] if methods else None  # methods[0] 作为 tool_name
                )
                
                if adapter:
                    success = registry.register_tool(adapter)
                    if success:
                        migrated.append(adapter.name)
                        print(f"[PASS] 已迁移: {adapter.name}")
                    else:
                        failed.append(f"{module_name}.{class_or_func_name}")
                        print(f"[FAIL] 注册失败: {adapter.name}")
        
        except Exception as e:
            failed.append(module_name)
            print(f"[FAIL] 迁移模块失败: {module_name} - {e}")
    
    # 输出统计
    print("\n" + "=" * 60)
    print(f"迁移完成: {len(migrated)} 成功, {len(failed)} 失败")
    print("=" * 60)
    
    if migrated:
        print("\n[PASS] 已迁移的工具:")
        for name in migrated:
            print(f"   - {name}")
    
    if failed:
        print("\n[FAIL] 迁移失败的工具:")
        for name in failed:
            print(f"   - {name}")
    
    # 注册中心统计
    stats = registry.stats()
    print(f"\n[INFO] 注册中心统计: {stats}")
    
    return migrated, failed, stats


if __name__ == "__main__":
    try:
        migrated, failed, stats = migrate_all()
    except Exception as e:
        print(f"\n[ERROR] 迁移过程出错: {e}")
        import traceback
        traceback.print_exc()
