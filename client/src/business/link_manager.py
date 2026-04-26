"""
link_manager - Module linkage service

Implements linkage between enterprise cockpit and other modules.
"""

from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class ModuleType(Enum):
    """Module types"""
    ENTERPRISE_COCKPIT = "enterprise_cockpit"
    KNOWLEDGE_BASE = "knowledge_base"
    IM = "im"
    SMART_WRITING = "smart_writing"
    SMART_IDE = "smart_ide"


class ActionType(Enum):
    """Action types"""
    OPEN = "open"
    CLOSE = "close"
    SEARCH_KNOWLEDGE = "search_knowledge"
    SEND_MESSAGE = "send_message"
    CREATE_DOCUMENT = "create_document"
    OPEN_PROJECT = "open_project"


@dataclass
class LinkAction:
    """Link action"""
    source_module: ModuleType
    target_module: ModuleType
    action_type: ActionType
    data: Dict[str, Any]
    timestamp: str
    callback: Optional[Callable] = None


class LinkManager:
    """
    Linkage Manager (Singleton)
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._link_registry: Dict[str, List[Callable]] = {}
        self._link_history: List[LinkAction] = []
        self._module_instances: Dict[ModuleType, Any] = {}
        logger.info("LinkManager initialized")

    def register_module(self, module_type: ModuleType, module_instance: Any):
        """Register module instance"""
        self._module_instances[module_type] = module_instance
        logger.info(f"Module registered: {module_type.value}")

    def trigger_link(self, action: LinkAction) -> Any:
        """Trigger linkage"""
        key = f"{action.source_module.value}->{action.target_module.value}"
        self._link_history.append(action)
        if len(self._link_history) > 100:
            self._link_history = self._link_history[-100:]
        logger.info(f"Triggering link: {key}")
        return None


def get_link_manager() -> LinkManager:
    """Get LinkManager instance"""
    return LinkManager()


def open_knowledge_from_cockpit(query: str = ""):
    """Open knowledge base from enterprise cockpit"""
    manager = get_link_manager()
    # TODO: Implement actual linkage
    logger.info(f"Opening knowledge base from cockpit, query={query}")
    return {"status": "opened"}


def open_im_from_cockpit(chat_id: str = ""):
    """Open IM from enterprise cockpit"""
    manager = get_link_manager()
    logger.info(f"Opening IM from cockpit, chat_id={chat_id}")
    return {"status": "opened"}


def open_writing_from_cockpit(document_id: str = ""):
    """Open smart writing from enterprise cockpit"""
    manager = get_link_manager()
    logger.info(f"Opening smart writing from cockpit, document_id={document_id}")
    return {"status": "opened"}


def open_ide_from_cockpit(project_id: str = ""):
    """Open smart IDE from enterprise cockpit"""
    manager = get_link_manager()
    logger.info(f"Opening smart IDE from cockpit, project_id={project_id}")
    return {"status": "opened"}
