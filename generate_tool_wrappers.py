"""
Batch Tool Wrapper Generator

Automatically generates BaseTool wrappers for multiple modules.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from client.src.business.tools.tool_registry import ToolRegistry

# Tool configurations: (tool_name, module_path, class_name, method_name)
TOOL_CONFIGS = [
    ("tier_router", "client.src.business.search.tier_router", "TierRouter", "route"),
    ("proxy_manager", "client.src.business.base_proxy_manager", "ProxyManager", "get_proxy"),
    ("content_extractor", "client.src.business.web_content_extractor.extractor", "ContentExtractor", "extract"),
    ("document_parser", "client.src.business.bilingual_doc.document_parser", "DocumentParser", "parse"),
    ("intelligent_ocr", "client.src.business.intelligent_ocr.ocr_engine", "OCREngine", "recognize"),
    ("kb_auto_ingest", "client.src.business.knowledge_auto_ingest", "KBAutoIngest", "ingest"),
    ("agent_progress", "client.src.business.agent_progress", "AgentProgress", "report"),
    ("expert_learning", "client.src.business.expert_learning.learning_system", "ExpertLearningSystem", "learn"),
    ("skill_evolution", "client.src.business.skill_evolution.evolution_engine", "SkillEvolutionEngine", "evolve"),
    ("experiment_loop", "client.src.business.experiment_loop.evolution_loop", "ExperimentLoop", "run"),
]

def generate_tool_wrapper(tool_name, module_path, class_name, method_name):
    """Generate a BaseTool wrapper for a given module/class/method"""
    
    # Create the wrapper class dynamically
    wrapper_code = f'''"""
{tool_name}_tool - Auto-generated BaseTool wrapper
"""

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from {module_path} import {class_name}


class {class_name}Tool(BaseTool):
    """Auto-generated tool wrapper for {class_name}.{method_name}"""
    
    def __init__(self):
        super().__init__(
            name="{tool_name}",
            description="Auto-generated tool wrapper for {class_name}",
            category="auto",
            tags=["auto", "{tool_name}"]
        )
        self._instance = {class_name}()
    
    def execute(self, **kwargs):
        try:
            method = getattr(self._instance, "{method_name}")
            result = method(**kwargs)
            return ToolResult.ok(data=result, message=f"{{tool_name}} executed successfully")
        except Exception as e:
            return ToolResult.fail(error=str(e))


def register_{tool_name}_tool():
    """Register {tool_name} tool with ToolRegistry"""
    from client.src.business.tools.tool_registry import ToolRegistry
    registry = ToolRegistry.get_instance()
    tool = {class_name}Tool()
    registry.register_tool(tool)
    return tool.name
'''
    
    return wrapper_code


def generate_all_wrappers():
    """Generate all tool wrappers"""
    import importlib
    
    registry = ToolRegistry.get_instance()
    generated = []
    failed = []
    
    for tool_name, module_path, class_name, method_name in TOOL_CONFIGS:
        try:
            # Try to import the module
            module = importlib.import_module(module_path)
            
            # Generate wrapper code
            wrapper_code = generate_tool_wrapper(tool_name, module_path, class_name, method_name)
            
            # Write to file
            file_path = os.path.join(project_root, "client", "src", "business", "tools", f"{tool_name}_tool.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(wrapper_code)
            
            generated.append(tool_name)
            print(f"[PASS] Generated: {tool_name}_tool.py")
            
        except Exception as e:
            failed.append((tool_name, str(e)))
            print(f"[FAIL] Failed to generate {tool_name}: {e}")
    
    return generated, failed


if __name__ == "__main__":
    print("=" * 60)
    print("Batch Tool Wrapper Generator")
    print("=" * 60)
    
    generated, failed = generate_all_wrappers()
    
    print(f"\n[INFO] Generated {len(generated)} wrappers")
    print(f"[INFO] Failed: {len(failed)}")
    
    if generated:
        print("\n[PASS] Successfully generated:")
        for name in generated:
            print(f"   - {name}_tool.py")
    
    if failed:
        print("\n[FAIL] Failed to generate:")
        for name, error in failed:
            print(f"   - {name}: {error}")
