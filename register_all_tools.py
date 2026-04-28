"""
批量注册所有工具到 ToolRegistry
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from loguru import logger

def register_all_tools():
    """注册所有工具"""
    registered = []
    failed = []

    try:
        from client.src.business.tools.tier_router_tool import register_tier_router_tool
        name = register_tier_router_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register tier_router: {e}")
        failed.append("tier_router")

    try:
        from client.src.business.tools.proxy_manager_tool import register_proxy_manager_tool
        name = register_proxy_manager_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register proxy_manager: {e}")
        failed.append("proxy_manager")

    try:
        from client.src.business.tools.content_extractor_tool import register_content_extractor_tool
        name = register_content_extractor_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register content_extractor: {e}")
        failed.append("content_extractor")

    try:
        from client.src.business.tools.document_parser_tool import register_document_parser_tool
        name = register_document_parser_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register document_parser: {e}")
        failed.append("document_parser")

    try:
        from client.src.business.tools.intelligent_ocr_tool import register_intelligent_ocr_tool
        name = register_intelligent_ocr_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register intelligent_ocr: {e}")
        failed.append("intelligent_ocr")

    try:
        from client.src.business.tools.kb_auto_ingest_tool import register_kb_auto_ingest_tool
        name = register_kb_auto_ingest_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register kb_auto_ingest: {e}")
        failed.append("kb_auto_ingest")

    try:
        from client.src.business.tools.agent_progress_tool import register_agent_progress_tool
        name = register_agent_progress_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register agent_progress: {e}")
        failed.append("agent_progress")

    try:
        from client.src.business.tools.expert_learning_tool import register_expert_learning_tool
        name = register_expert_learning_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register expert_learning: {e}")
        failed.append("expert_learning")

    try:
        from client.src.business.tools.skill_evolution_tool import register_skill_evolution_tool
        name = register_skill_evolution_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register skill_evolution: {e}")
        failed.append("skill_evolution")

    try:
        from client.src.business.tools.experiment_loop_tool import register_experiment_loop_tool
        name = register_experiment_loop_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register experiment_loop: {e}")
        failed.append("experiment_loop")

    try:
        from client.src.business.tools.markitdown_converter_tool import register_markitdown_converter_tool
        name = register_markitdown_converter_tool()
        if name:
            registered.append(name)
    except Exception as e:
        logger.error(f"Failed to register markitdown_converter: {e}")
        failed.append("markitdown_converter")

    logger.info(f"Registered {len(registered)} tools, {len(failed)} failed")
    return registered, failed

if __name__ == "__main__":
    register_all_tools()
