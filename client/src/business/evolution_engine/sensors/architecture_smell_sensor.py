# sensors/architecture_smell_sensor.py - 架构异味传感器

"""
ArchitectureSmellSensor - 架构异味检测传感器

检测内容：
- 循环依赖
- 上帝类（God Class）
- 过深继承
- 特征 envy
- 数据类滥用
"""

import os
import ast
import hashlib
from typing import List, Dict, Set, Any, Optional
from collections import defaultdict
from pathlib import Path
import logging

from .base import BaseSensor, SensorType, EvolutionSignal

logger = logging.getLogger('evolution.sensor.architecture')


class ArchitectureSmellSensor(BaseSensor):
    """
    架构异味传感器
    
    通过 AST 分析检测代码库中的架构问题
    """
    
    # 上帝类阈值配置
    GOD_CLASS_THRESHOLDS = {
        'num_methods': 20,      # 方法数过多
        'num_lines': 500,        # 代码行数过多
        'complexity': 50,        # 圈复杂度过高
        'num_attributes': 10,    # 属性数过多
    }
    
    def __init__(self, project_root: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="ArchitectureSmellSensor",
            sensor_type=SensorType.ARCHITECTURE_SMELL,
            config=config
        )
        
        self.project_root = Path(project_root)
        
        # 自定义阈值（可选）
        self.god_class_thresholds = self.config.get(
            'god_class_thresholds', 
            self.GOD_CLASS_THRESHOLDS
        )
        
        # 扫描配置
        self.exclude_dirs = set(self.config.get(
            'exclude_dirs',
            ['.git', '__pycache__', '.venv', 'venv', 'node_modules', 'tests', 'test']
        ))
        self.max_file_size = self.config.get('max_file_size', 10000)  # 最大文件行数
        
        # 缓存
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._class_metrics: Dict[str, Dict] = {}
        
        logger.info(f"[ArchitectureSmellSensor] 扫描目录: {self.project_root}")
    
    def scan(self) -> List[EvolutionSignal]:
        """
        执行架构扫描
        
        Returns:
            检测到的架构异味信号列表
        """
        signals = []
        
        # 1. 构建依赖图
        self._build_dependency_graph()
        
        # 2. 检测循环依赖
        signals.extend(self._detect_circular_dependencies())
        
        # 3. 检测上帝类
        signals.extend(self._detect_god_classes())
        
        # 4. 检测过深继承
        signals.extend(self._detect_deep_inheritance())
        
        logger.info(f"[ArchitectureSmellSensor] 扫描完成，检测到 {len(signals)} 个信号")
        return signals
    
    def _build_dependency_graph(self):
        """构建模块依赖图"""
        self._dependency_graph.clear()
        self._class_metrics.clear()
        
        if not self.project_root.exists():
            logger.warning(f"[ArchitectureSmellSensor] 目录不存在: {self.project_root}")
            return
        
        for root, dirs, files in os.walk(self.project_root):
            # 过滤目录
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs and not d.startswith('.')]
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                filepath = os.path.join(root, file)
                
                # 检查文件大小
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if len(lines) > self.max_file_size:
                            logger.debug(f"跳过过大文件: {filepath}")
                            continue
                except Exception:
                    continue
                
                rel_path = os.path.relpath(filepath, self.project_root)
                module_name = self._path_to_module(rel_path)
                
                # 解析文件
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        tree = ast.parse(content, filename=filepath)
                    
                    # 提取导入
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                dep = alias.name.split('.')[0]
                                if dep not in ['__future__', 'builtins']:
                                    self._dependency_graph[module_name].add(dep)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                dep = node.module.split('.')[0]
                                if dep not in ['__future__', 'builtins']:
                                    self._dependency_graph[module_name].add(dep)
                    
                    # 提取类信息
                    for item in tree.body:
                        if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                            if isinstance(item, ast.ClassDef):
                                self._analyze_class(item, module_name, filepath)
                            
                except SyntaxError as e:
                    logger.debug(f"语法错误 {filepath}: {e}")
                except Exception as e:
                    logger.debug(f"解析异常 {filepath}: {e}")
    
    def _path_to_module(self, rel_path: str) -> str:
        """将路径转换为模块名"""
        module = rel_path.replace(os.sep, '.').replace('/', '.')
        if module.endswith('.py'):
            module = module[:-3]
        if module.startswith('.'):
            module = module[1:]
        return module or 'root'
    
    def _analyze_class(self, class_node: ast.ClassDef, module: str, filepath: str):
        """分析类复杂度"""
        # 统计方法
        methods = [n for n in class_node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        
        # 计算圈复杂度
        complexity = 1
        for node in ast.walk(class_node):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        # 统计属性（类级别赋值）
        attributes = [
            n for n in class_node.body 
            if isinstance(n, ast.AnnAssign) or 
               (isinstance(n, ast.Assign) and not isinstance(n.value, ast.Call))
        ]
        
        # 行数
        start_line = class_node.lineno
        end_line = class_node.end_lineno if hasattr(class_node, 'end_lineno') else start_line
        
        self._class_metrics[f"{module}.{class_node.name}"] = {
            'module': module,
            'name': class_node.name,
            'filepath': filepath,
            'num_methods': len(methods),
            'num_lines': end_line - start_line,
            'complexity': complexity,
            'num_attributes': len(attributes),
            'methods': [m.name for m in methods],
        }
    
    def _detect_circular_dependencies(self) -> List[EvolutionSignal]:
        """检测循环依赖"""
        signals = []
        
        # 使用DFS检测环
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> List[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            paths = []
            
            for neighbor in self._dependency_graph.get(node, set()):
                if neighbor not in visited:
                    paths.extend(dfs(neighbor, path + [neighbor]))
                elif neighbor in rec_stack:
                    # 发现环
                    if neighbor in path:
                        cycle_start = path.index(neighbor)
                        paths.append(path[cycle_start:] + [neighbor])
            
            rec_stack.remove(node)
            return paths
        
        for node in self._dependency_graph:
            if node not in visited:
                cycles = dfs(node, [node])
                
                for cycle in cycles:
                    # 过滤外部依赖
                    affected = [n for n in cycle if '.' in n or n.startswith('core') or n.startswith('client')]
                    
                    if affected:
                        signal = self._create_signal(
                            signal_type="circular_dependency",
                            severity="critical",
                            evidence=[f"模块循环依赖: {' -> '.join(cycle)}"],
                            affected_files=affected,
                            metrics={
                                'cycle_length': len(cycle),
                                'num_modules': len(set(affected))
                            },
                            confidence=0.95,
                            false_positive_rate=0.01
                        )
                        signals.append(signal)
        
        return signals
    
    def _detect_god_classes(self) -> List[EvolutionSignal]:
        """检测上帝类"""
        signals = []
        
        thresholds = self.god_class_thresholds
        
        for class_key, metrics in self._class_metrics.items():
            violations = []
            
            if metrics['num_methods'] > thresholds['num_methods']:
                violations.append(
                    f"方法数 {metrics['num_methods']} > {thresholds['num_methods']}"
                )
            
            if metrics['num_lines'] > thresholds['num_lines']:
                violations.append(
                    f"代码行数 {metrics['num_lines']} > {thresholds['num_lines']}"
                )
            
            if metrics['complexity'] > thresholds['complexity']:
                violations.append(
                    f"圈复杂度 {metrics['complexity']} > {thresholds['complexity']}"
                )
            
            if metrics['num_attributes'] > thresholds['num_attributes']:
                violations.append(
                    f"属性数 {metrics['num_attributes']} > {thresholds['num_attributes']}"
                )
            
            if violations:
                signal = self._create_signal(
                    signal_type="god_class",
                    severity="warning",
                    evidence=violations,
                    affected_files=[metrics.get('filepath', class_key)],
                    metrics={
                        'num_methods': metrics['num_methods'],
                        'num_lines': metrics['num_lines'],
                        'complexity': metrics['complexity'],
                        'num_attributes': metrics['num_attributes']
                    },
                    confidence=0.85,
                    false_positive_rate=0.1
                )
                signals.append(signal)
        
        return signals
    
    def _detect_deep_inheritance(self) -> List[EvolutionSignal]:
        """检测过深继承"""
        signals = []
        
        # 构建继承关系图
        inheritance: Dict[str, List[str]] = {}
        for class_key, metrics in self._class_metrics.items():
            try:
                with open(metrics['filepath'], 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read(), filename=metrics['filepath'])
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        bases = [
                            b.attr if isinstance(b, ast.Attribute) else b.id
                            for b in node.bases
                            if isinstance(b, (ast.Attribute, ast.Name))
                        ]
                        inheritance[f"{metrics['module']}.{node.name}"] = bases
                        
            except Exception:
                continue
        
        # DFS检测继承深度
        def get_depth(class_name: str, visited: Set[str] = None) -> int:
            if visited is None:
                visited = set()
            
            if class_name in visited:
                return 0  # 避免循环
            
            if class_name not in inheritance or not inheritance[class_name]:
                return 0
            
            visited.add(class_name)
            max_child_depth = 0
            
            for base in inheritance[class_name]:
                depth = get_depth(base, visited.copy())
                max_child_depth = max(max_child_depth, depth)
            
            return max_child_depth + 1
        
        for class_name in inheritance:
            depth = get_depth(class_name)
            if depth > 4:  # 超过4层认为是过深
                metrics = self._class_metrics.get(class_name, {})
                signal = self._create_signal(
                    signal_type="deep_inheritance",
                    severity="info",
                    evidence=[f"类 {class_name} 继承深度 {depth} > 4"],
                    affected_files=[metrics.get('filepath', class_name)],
                    metrics={'inheritance_depth': depth},
                    confidence=0.7,
                    false_positive_rate=0.15
                )
                signals.append(signal)
        
        return signals
    
    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """获取依赖图"""
        return self._dependency_graph.copy()
    
    def get_class_metrics(self) -> Dict[str, Dict]:
        """获取类指标"""
        return self._class_metrics.copy()
