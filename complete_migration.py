"""
Complete Tool Migration Script - Creates BaseTool wrappers for all 14 remaining tools
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from loguru import logger
from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from client.src.business.tools.tool_registry import ToolRegistry

# Remove loguru colors to avoid PowerShell encoding issues
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

registry = ToolRegistry.get_instance()

def create_simple_tool(tool_name, description, module_path, class_name, method_name):
    """Create a simple BaseTool wrapper for a class method"""
    try:
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        instance = cls()
        
        class WrapperTool(BaseTool):
            def __init__(self):
                super().__init__(
                    name=tool_name,
                    description=description,
                    category="migrated",
                    tags=["auto", "migrated"]
                )
                self._instance = instance
            
            def execute(self, **kwargs):
                try:
                    method = getattr(self._instance, method_name)
                    result = method(**kwargs)
                    return ToolResult.ok(data=result, message=f"{tool_name} executed successfully")
                except Exception as e:
                    return ToolResult.fail(error=str(e))
        
        tool = WrapperTool()
        registry.register_tool(tool)
        print(f"[PASS] Migrated: {tool_name}")
        return tool_name
    
    except Exception as e:
        print(f"[FAIL] Failed to migrate {tool_name}: {e}")
        return None

# ============================================================
# Migrate all 14 remaining tools
# ============================================================

migrated = []
failed = []

# 1. vector_database
result = create_simple_tool(
    "vector_database",
    "Vector database tool",
    "client.src.business.knowledge_vector_db",
    "VectorDatabase",
    "search"
)
if result: migrated.append(result)

# 2. tier_router
result = create_simple_tool(
    "tier_router",
    "Tier routing tool",
    "client.src.business.search.tier_router",
    "TierRouter",
    "route"
)
if result: migrated.append(result)

# 3. proxy_manager
result = create_simple_tool(
    "proxy_manager",
    "Proxy manager tool",
    "client.src.business.base_proxy_manager",
    "ProxyManager",
    "get_proxy"
)
if result: migrated.append(result)

# 4. content_extractor
result = create_simple_tool(
    "content_extractor",
    "Content extractor tool",
    "client.src.business.web_content_extractor.extractor",
    "ContentExtractor",
    "extract"
)
if result: migrated.append(result)

# 5. document_parser
result = create_simple_tool(
    "document_parser",
    "Document parser tool",
    "client.src.business.bilingual_doc.document_parser",
    "DocumentParser",
    "parse"
)
if result: migrated.append(result)

# 6. intelligent_ocr
result = create_simple_tool(
    "intelligent_ocr",
    "Intelligent OCR tool",
    "client.src.business.intelligent_ocr.ocr_engine",
    "OCREngine",
    "recognize"
)
if result: migrated.append(result)

# 7. kb_auto_ingest
result = create_simple_tool(
    "kb_auto_ingest",
    "Knowledge base auto ingest tool",
    "client.src.business.knowledge_auto_ingest",
    "KBAutoIngest",
    "ingest"
)
if result: migrated.append(result)

# 8. task_queue
result = create_simple_tool(
    "task_queue",
    "Task queue tool",
    "client.src.business.task_queue",
    "TaskQueue",
    "add"
)
if result: migrated.append(result)

# 9. task_execution_engine
result = create_simple_tool(
    "task_execution_engine",
    "Task execution engine tool",
    "client.src.business.task_execution_engine",
    "TaskExecutionEngine",
    "execute"
)
if result: migrated.append(result)

# 10. agent_progress
result = create_simple_tool(
    "agent_progress",
    "Agent progress tool",
    "client.src.business.agent_progress",
    "AgentProgress",
    "report"
)
if result: migrated.append(result)

# 11. expert_learning
result = create_simple_tool(
    "expert_learning",
    "Expert learning tool",
    "client.src.business.expert_learning.learning_system",
    "ExpertLearningSystem",
    "learn"
)
if result: migrated.append(result)

# 12. skill_evolution
result = create_simple_tool(
    "skill_evolution",
    "Skill evolution tool",
    "client.src.business.skill_evolution.evolution_engine",
    "SkillEvolutionEngine",
    "evolve"
)
if result: migrated.append(result)

# 13. experiment_loop
result = create_simple_tool(
    "experiment_loop",
    "Experiment loop tool",
    "client.src.business.experiment_loop.evolution_loop",
    "ExperimentLoop",
    "run"
)
if result: migrated.append(result)

# 14. markitdown_converter (needs to be created, skip for now)
print(f"\n[INFO] Skipping markitdown_converter (needs to be created)")

# ============================================================
# Print statistics
# ============================================================

print("\n" + "=" * 60)
print(f"Migration completed: {len(migrated)} success, {len(failed)} failed")
print("=" * 60)

if migrated:
    print(f"\n[PASS] Successfully migrated {len(migrated)} tools:")
    for name in migrated:
        print(f"   - {name}")

if failed:
    print(f"\n[FAIL] Failed to migrate {len(failed)} tools:")
    for name in failed:
        print(f"   - {name}")

# Print registry statistics
stats = registry.stats()
print(f"\n[INFO] Registry statistics: {stats}")
