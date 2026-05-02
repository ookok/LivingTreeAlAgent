"""
组件扫描器 - 自动发现UI组件和操作路径
"""

from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import re
import ast
from pathlib import Path


class ComponentType(Enum):
    """组件类型"""
    BUTTON = "button"
    INPUT = "input"
    PANEL = "panel"
    MENU = "menu"
    DIALOG = "dialog"
    LIST = "list"
    TABLE = "table"
    TREE = "tree"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class UIComponent:
    """UI组件"""
    component_id: str
    component_type: ComponentType
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    location: Optional[Dict[str, int]] = None


@dataclass
class ScanResult:
    """扫描结果"""
    components: Dict[str, UIComponent]
    actions: List[Dict[str, Any]]
    interactions: List[Dict[str, str]]
    timestamp: float
    
    @property
    def component_count(self) -> int:
        return len(self.components)
    
    def get_by_type(self, component_type: ComponentType) -> List[UIComponent]:
        return [c for c in self.components.values() 
                if c.component_type == component_type]


class ComponentScanner:
    """组件扫描器 - 扫描UI代码，识别组件和操作"""
    
    QT_COMPONENTS = {
        'QPushButton': ComponentType.BUTTON,
        'QTextEdit': ComponentType.TEXT,
        'QLineEdit': ComponentType.INPUT,
        'QComboBox': ComponentType.INPUT,
        'QListWidget': ComponentType.LIST,
        'QTableWidget': ComponentType.TABLE,
        'QTreeWidget': ComponentType.TREE,
        'QMenuBar': ComponentType.MENU,
        'QMenu': ComponentType.MENU,
        'QDialog': ComponentType.DIALOG,
        'QWidget': ComponentType.PANEL,
        'QMainWindow': ComponentType.PANEL,
        'QLabel': ComponentType.TEXT,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.result: Optional[ScanResult] = None
        
    def scan_directory(self, directory: str) -> ScanResult:
        """扫描目录"""
        components: Dict[str, UIComponent] = {}
        actions: List[Dict[str, Any]] = []
        
        for py_file in Path(directory).rglob("*.py"):
            if self._should_scan(py_file):
                file_components, file_actions = self._scan_file(py_file)
                components.update(file_components)
                actions.extend(file_actions)
                
        import time
        self.result = ScanResult(
            components=components,
            actions=actions,
            interactions=self._build_interaction_graph(components, actions),
            timestamp=time.time()
        )
        
        return self.result
    
    def _should_scan(self, file_path: Path) -> bool:
        exclude_patterns = ['test_', '__pycache__', '.pyc']
        for pattern in exclude_patterns:
            if pattern in str(file_path):
                return False
        return True
    
    def _scan_file(self, file_path: Path) -> tuple:
        components: Dict[str, UIComponent] = {}
        actions: List[Dict[str, Any]] = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            try:
                tree = ast.parse(content)
            except SyntaxError:
                return components, actions
                
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    component_type = self._get_component_type(node)
                    if component_type:
                        component_id = f"{file_path.name}:{node.name}"
                        component = UIComponent(
                            component_id=component_id,
                            component_type=component_type,
                            name=node.name,
                            properties=self._extract_properties(node),
                        )
                        components[component_id] = component
                        
        except Exception:
            pass
            
        return components, actions
    
    def _get_component_type(self, node: ast.ClassDef) -> Optional[ComponentType]:
        for base in node.bases:
            if isinstance(base, ast.Name):
                qt_type = self.QT_COMPONENTS.get(base.id)
                if qt_type:
                    return qt_type
        return None
    
    def _extract_properties(self, node: ast.ClassDef) -> Dict[str, Any]:
        properties = {}
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        properties[target.id] = f"value"
        return properties
    
    def _build_interaction_graph(self, 
                               components: Dict[str, UIComponent],
                               actions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        interactions = []
        
        for comp in components.values():
            if comp.component_type == ComponentType.BUTTON:
                for other_comp in components.values():
                    if other_comp.component_type in [ComponentType.DIALOG, ComponentType.PANEL]:
                        interactions.append({
                            'from': comp.component_id,
                            'to': other_comp.component_id,
                            'type': 'click'
                        })
                        
        return interactions
    
    def discover_actions(self) -> List[Dict[str, Any]]:
        """发现所有可执行操作"""
        if not self.result:
            return []
            
        discovered_actions = []
        
        for component in self.result.components.values():
            if component.component_type == ComponentType.BUTTON:
                discovered_actions.append({
                    'action': 'click',
                    'target': component.component_id,
                    'target_name': component.name,
                })
            elif component.component_type == ComponentType.INPUT:
                discovered_actions.append({
                    'action': 'type',
                    'target': component.component_id,
                    'target_name': component.name,
                })
            elif component.component_type == ComponentType.MENU:
                discovered_actions.append({
                    'action': 'select',
                    'target': component.component_id,
                    'target_name': component.name,
                })
                
        return discovered_actions
