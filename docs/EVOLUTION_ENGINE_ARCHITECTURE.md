# Evolution Engine - 智能IDE自我进化系统

> 让AI从"执行工具"进化为"设计伙伴"的关键跨越
> 
> 核心目标：构建"感知-诊断-规划-执行"的闭环自治系统

---

## 一、设计理念

### 1.1 传统IDE vs 进化型IDE

| 维度 | 传统 IDE | 进化型 IDE (Evolution Engine) |
|------|----------|-------------------------------|
| 问题发现 | 用户报告 | 系统自动感知 |
| 方案生成 | 用户手动规划 | AI推理+结构化提案 |
| 执行方式 | 用户手动修改 | 机器自动执行 + 用户确认 |
| 优化方向 | 用户设定目标 | AI自主发现 + 价值驱动 |
| 学习方式 | 人工积累 | 强化学习 + 进化日志 |

### 1.2 Evolution Engine 核心价值

```
用户输入："我想做一个社交App"
     ↓
Evolution Engine 自动感知：
  • 当前技术栈（Python/JS）
  • 代码库规模（小/中/大）
  • 性能瓶颈（API响应慢）
  • 架构风险（循环依赖）
  • 社区趋势（Flutter正在崛起）
     ↓
自动生成结构化进化提案：
  进化提案 REFACTOR-2026-001
  标题：从Flask迁移到FastAPI
  触发信号：性能监控显示平均响应时间 > 500ms
  预期收益：异步支持，预计降低60%延迟
  实施路径：分3步渐进迁移
  风险等级：LOW（AST分析验证兼容性）
     ↓
用户确认 / AI自动执行
```

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Evolution Engine                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │           进化传感器层 (Evolution Sensors)                │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │   │
│  │  │ 运行时    │  │ 代码质量  │  │ 生态监测  │  │ 用户行为  │ │   │
│  │  │ 性能感知  │  │ 静态分析  │  │ 外部情报  │  │ 埋点收集  │ │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │   │
│  └───────┼─────────────┼─────────────┼─────────────┼───────┘   │
│          └──────────────┴──────┬──────┴─────────────┘          │
│                                ↓                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              信号聚合器 (Signal Aggregator)               │   │
│  │  • 多源信号融合 (权重+RRF)                               │   │
│  │  • 信号去重与优先级排序                                    │   │
│  │  • 信号有效性验证                                         │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │             进化提案生成器 (Proposal Generator)           │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │   │
│  │  │ 诊断引擎  │  │ 推理引擎  │  │ 收益评估  │  │ 风险评估  │ │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │   │
│  │       └─────────────┴─────────────┴─────────────┘        │   │
│  │                         ↓                                  │   │
│  │              输出：结构化进化提案                           │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              自治执行引擎 (Autonomous Executor)           │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │   │
│  │  │ 安全沙箱  │  │ 原子操作  │  │ 验证关卡  │  │ 回滚熔断  │ │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │   │
│  └───────┼─────────────┼─────────────┼─────────────┼───────┘   │
│          └──────────────┴──────┬──────┴─────────────┘          │
│                                ↓                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              进化记忆层 (Evolution Memory)               │   │
│  │  • 进化日志 (成功/失败案例)                               │   │
│  │  • 强化学习反馈                                           │   │
│  │  • 知识图谱自动更新                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   安全围栏 (Safety Fence)                │   │
│  │  • 用户确认机制 (重大变更必须批准)                         │   │
│  │  • 伦理边界 (禁止删除核心代码)                            │   │
│  │  • 影响范围评估                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、进化传感器层

### 3.1 传感器类型

```python
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime

class SensorType(Enum):
    """传感器类型"""
    # 运行时性能
    PERFORMANCE = "performance"          # API响应、内存泄漏、CPU瓶颈
    ERROR_PATTERN = "error_pattern"      # 高频异常、日志分析
    RESOURCE_USAGE = "resource_usage"    # 内存/CPU/磁盘使用率
    
    # 代码质量
    ARCHITECTURE_SMELL = "arch_smell"   # 循环依赖、上帝类
    TECHNICAL_DEBT = "tech_debt"         # 过期API、冗余代码
    SECURITY_VULN = "security_vuln"      # 安全漏洞、SCA扫描
    
    # 生态情报
    COMPETITOR_TREND = "competitor"      # GitHub趋势、新框架
    COST_ANALYSIS = "cost_analysis"       # 云成本、资源浪费
    
    # 用户行为
    USER_WORKFLOW = "user_workflow"      # 绕路操作、重复求助
    SATISFACTION = "satisfaction"        # 用户满意度埋点

@dataclass
class EvolutionSignal:
    """进化信号"""
    signal_id: str
    sensor_type: SensorType
    timestamp: datetime
    source_module: str
    
    # 信号内容
    signal_type: str           # e.g., "high_latency", "circular_dependency"
    severity: str              # "critical" / "warning" / "info"
    evidence: List[str]        # 具体证据
    affected_files: List[str]  # 受影响文件
    metrics: Dict[str, float] # 量化指标
    
    # 置信度
    confidence: float          # 0.0 ~ 1.0
    false_positive_rate: float # 误报率
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "sensor_type": self.sensor_type.value,
            "timestamp": self.timestamp.isoformat(),
            "signal_type": self.signal_type,
            "severity": self.severity,
            "confidence": self.confidence,
            "affected_files": self.affected_files,
            "metrics": self.metrics,
        }
```

### 3.2 传感器实现矩阵

| 传感器 | 数据源 | 采集频率 | 触发阈值 |
|--------|--------|----------|----------|
| **PerformanceSensor** | ResourceMonitor + API日志 | 实时 | 响应时间 > P95 500ms |
| **ErrorPatternSensor** | StructuredLogger + ErrorLogger | 实时 | 错误率 > 5% |
| **ArchitectureSmellSensor** | CodeAnalyzer (增强) | 每日扫描 | 检测到循环依赖 |
| **TechDebtSensor** | AST分析 + 依赖扫描 | 每周扫描 | 检测到过时API |
| **SecurityVulnSensor** | SCA工具 + 代码扫描 | 每日扫描 | 发现CVE |
| **CompetitorSensor** | GitHubTrendingAPI | 每小时 | 检测到相关新框架 |
| **CostSensor** | 云账单API | 每日 | 成本增长 > 20% |
| **UserWorkflowSensor** | 埋点数据 + ExperienceOptimizer | 实时 | 反复求助 > 3次 |

### 3.3 传感器示例：PerformanceSensor

```python
# sensors/performance_sensor.py

from core.resource_monitor import ResourceMonitor, LoadLevel
from core.logger import get_logger
from typing import List, Dict, Any
import threading
import time

logger = get_logger('evolution.sensor.performance')

class PerformanceSensor:
    """
    运行时性能感知传感器
    
    监控内容：
    - API响应时间
    - 内存泄漏检测
    - CPU瓶颈识别
    - 吞吐量异常
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 阈值配置
        self.latency_threshold_p95 = self.config.get('latency_p95_ms', 500)
        self.memory_leak_threshold = self.config.get('memory_growth_mb', 100)
        self.cpu_threshold = self.config.get('cpu_percent', 85)
        
        # ResourceMonitor 集成
        self.resource_monitor = ResourceMonitor()
        
        # 指标缓存
        self._latency_history: List[float] = []
        self._memory_history: List[float] = []
        self._max_history_size = 1000
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 信号回调
        self.on_signal: callable = None
    
    def start(self):
        """启动监控"""
        logger.info("[PerformanceSensor] 启动性能监控...")
        self.resource_monitor.start()
    
    def stop(self):
        """停止监控"""
        logger.info("[PerformanceSensor] 停止性能监控...")
        self.resource_monitor.stop()
    
    def record_latency(self, endpoint: str, latency_ms: float):
        """记录API延迟"""
        with self._lock:
            self._latency_history.append({
                'endpoint': endpoint,
                'latency_ms': latency_ms,
                'timestamp': time.time()
            })
            
            # 保持历史大小
            if len(self._latency_history) > self._max_history_size:
                self._latency_history = self._latency_history[-self._max_history_size:]
        
        # 检测异常
        if latency_ms > self.latency_threshold_p95:
            self._emit_signal(
                signal_type="high_latency",
                severity="warning",
                evidence=[f"{endpoint} 响应时间 {latency_ms}ms > 阈值 {self.latency_threshold_p95}ms"],
                metrics={'latency_ms': latency_ms, 'threshold': self.latency_threshold_p95}
            )
    
    def record_memory(self, module: str, memory_mb: float):
        """记录内存使用"""
        with self._lock:
            self._memory_history.append({
                'module': module,
                'memory_mb': memory_mb,
                'timestamp': time.time()
            })
            
            if len(self._memory_history) > self._max_history_size:
                self._memory_history = self._memory_history[-self._max_history_size:]
        
        # 检测内存泄漏（持续增长）
        self._detect_memory_leak()
    
    def _detect_memory_leak(self):
        """检测内存泄漏"""
        if len(self._memory_history) < 100:
            return
        
        # 按模块分组分析
        modules = {}
        for record in self._memory_history:
            module = record['module']
            if module not in modules:
                modules[module] = []
            modules[module].append(record['memory_mb'])
        
        for module, memory_values in modules.items():
            if len(memory_values) < 50:
                continue
            
            # 计算增长趋势
            recent = memory_values[-20:]
            older = memory_values[-50:-20] if len(memory_values) >= 50 else memory_values[:20]
            
            avg_recent = sum(recent) / len(recent)
            avg_older = sum(older) / len(older) if older else avg_recent
            
            growth = avg_recent - avg_older
            
            if growth > self.memory_leak_threshold:
                self._emit_signal(
                    signal_type="memory_leak",
                    severity="critical",
                    evidence=[f"模块 {module} 内存增长 {growth:.1f}MB"],
                    metrics={'growth_mb': growth, 'recent_avg': avg_recent, 'older_avg': avg_older}
                )
    
    def _emit_signal(self, signal_type: str, severity: str, 
                     evidence: List[str], metrics: Dict[str, float]):
        """发射进化信号"""
        signal = EvolutionSignal(
            signal_id=f"perf_{signal_type}_{int(time.time())}",
            sensor_type=SensorType.PERFORMANCE,
            timestamp=datetime.now(),
            source_module="PerformanceSensor",
            signal_type=signal_type,
            severity=severity,
            evidence=evidence,
            affected_files=[],
            metrics=metrics,
            confidence=0.9,
            false_positive_rate=0.05
        )
        
        if self.on_signal:
            self.on_signal(signal)
        
        logger.info(f"[PerformanceSensor] 信号发射: {signal_type} ({severity})")
```

### 3.4 传感器示例：ArchitectureSmellSensor

```python
# sensors/architecture_smell_sensor.py

import ast
import os
from typing import List, Dict, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass
import hashlib

class ArchitectureSmellSensor:
    """
    架构异味传感器
    
    检测内容：
    - 循环依赖
    - 上帝类（God Class）
    - 过深继承
    - 特征 envy
    - 数据类滥用
    """
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._class_metrics: Dict[str, Dict] = {}
    
    def scan(self) -> List[EvolutionSignal]:
        """执行完整扫描"""
        signals = []
        
        # 1. 构建依赖图
        self._build_dependency_graph()
        
        # 2. 检测循环依赖
        signals.extend(self._detect_circular_dependencies())
        
        # 3. 检测上帝类
        signals.extend(self._detect_god_classes())
        
        # 4. 检测过深继承
        signals.extend(self._detect_deep_inheritance())
        
        return signals
    
    def _build_dependency_graph(self):
        """构建模块依赖图"""
        self._dependency_graph.clear()
        
        for root, dirs, files in os.walk(self.project_root):
            # 跳过非Python文件
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, self.project_root)
                module_name = rel_path.replace(os.sep, '.').replace('/', '.')[:-3]  # 去掉.py
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read(), filename=filepath)
                    
                    # 提取导入
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                self._dependency_graph[module_name].add(alias.name.split('.')[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                self._dependency_graph[module_name].add(node.module.split('.')[0])
                    
                    # 提取类信息
                    for item in tree.body:
                        if isinstance(item, ast.ClassDef):
                            self._analyze_class(item, module_name)
                            
                except Exception as e:
                    continue
    
    def _analyze_class(self, class_node: ast.ClassDef, module: str):
        """分析类复杂度"""
        methods = [n for n in class_node.body if isinstance(n, ast.FunctionDef)]
        
        # 计算圈复杂度
        complexity = 1
        for node in ast.walk(class_node):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        self._class_metrics[f"{module}.{class_node.name}"] = {
            'module': module,
            'name': class_node.name,
            'num_methods': len(methods),
            'num_lines': class_node.end_lineno - class_node.lineno if hasattr(class_node, 'end_lineno') else 0,
            'complexity': complexity,
            'num_attributes': len([n for n in class_node.body if isinstance(n, ast.AnnAssign)]),
        }
    
    def _detect_circular_dependencies(self) -> List[EvolutionSignal]:
        """检测循环依赖"""
        signals = []
        
        # DFS检测环
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
                    cycle_start = path.index(neighbor)
                    paths.append(path[cycle_start:] + [neighbor])
            
            rec_stack.remove(node)
            return paths
        
        for node in self._dependency_graph:
            if node not in visited:
                cycles = dfs(node, [node])
                
                for cycle in cycles:
                    affected = [n for n in cycle if '.' in n]
                    
                    signals.append(EvolutionSignal(
                        signal_id=f"arch_circular_{hashlib.md5(str(cycle).encode()).hexdigest()[:8]}",
                        sensor_type=SensorType.ARCHITECTURE_SMELL,
                        timestamp=datetime.now(),
                        source_module="ArchitectureSmellSensor",
                        signal_type="circular_dependency",
                        severity="critical",
                        evidence=[f"模块循环依赖: {' -> '.join(cycle)}"],
                        affected_files=affected,
                        metrics={'cycle_length': len(cycle), 'num_modules': len(set(affected))},
                        confidence=0.95,
                        false_positive_rate=0.01
                    ))
        
        return signals
    
    def _detect_god_classes(self) -> List[EvolutionSignal]:
        """检测上帝类"""
        signals = []
        
        GOD_CLASS_THRESHOLDS = {
            'num_methods': 20,      # 方法数过多
            'num_lines': 500,        # 代码行数过多
            'complexity': 50,        # 圈复杂度过高
        }
        
        for class_key, metrics in self._class_metrics.items():
            violations = []
            
            if metrics['num_methods'] > GOD_CLASS_THRESHOLDS['num_methods']:
                violations.append(f"方法数 {metrics['num_methods']} > {GOD_CLASS_THRESHOLDS['num_methods']}")
            
            if metrics['num_lines'] > GOD_CLASS_THRESHOLDS['num_lines']:
                violations.append(f"代码行数 {metrics['num_lines']} > {GOD_CLASS_THRESHOLDS['num_lines']}")
            
            if metrics['complexity'] > GOD_CLASS_THRESHOLDS['complexity']:
                violations.append(f"圈复杂度 {metrics['complexity']} > {GOD_CLASS_THRESHOLDS['complexity']}")
            
            if violations:
                signals.append(EvolutionSignal(
                    signal_id=f"arch_godclass_{hashlib.md5(class_key.encode()).hexdigest()[:8]}",
                    sensor_type=SensorType.ARCHITECTURE_SMELL,
                    timestamp=datetime.now(),
                    source_module="ArchitectureSmellSensor",
                    signal_type="god_class",
                    severity="warning",
                    evidence=violations,
                    affected_files=[f"{metrics['module']}/{metrics['name']}.py"],
                    metrics={
                        'num_methods': metrics['num_methods'],
                        'num_lines': metrics['num_lines'],
                        'complexity': metrics['complexity']
                    },
                    confidence=0.85,
                    false_positive_rate=0.1
                ))
        
        return signals
```

---

## 四、信号聚合器

### 4.1 信号融合算法

```python
# aggregator/signal_aggregator.py

from typing import List, Dict, Any, Tuple
from collections import defaultdict
import hashlib
from datetime import datetime, timedelta

class SignalAggregator:
    """
    信号聚合器
    
    功能：
    1. 多源信号融合（RRF + 加权平均）
    2. 信号去重与合并
    3. 信号优先级排序
    4. 信号有效性验证
    """
    
    # 信号类型权重配置
    SENSOR_WEIGHTS = {
        SensorType.PERFORMANCE: 0.3,
        SensorType.ERROR_PATTERN: 0.25,
        SensorType.SECURITY_VULN: 0.3,
        SensorType.ARCHITECTURE_SMELL: 0.2,
        SensorType.TECHNICAL_DEBT: 0.15,
        SensorType.COMPETITOR_TREND: 0.1,
        SensorType.COST_ANALYSIS: 0.15,
        SensorType.USER_WORKFLOW: 0.2,
    }
    
    # RRF参数
    RRF_K = 60  # RRF公式中的常数
    
    def __init__(self):
        self._signal_buffer: List[EvolutionSignal] = []
        self._last_aggregation = None
        self._aggregation_interval = timedelta(hours=1)
    
    def add_signal(self, signal: EvolutionSignal):
        """添加信号"""
        self._signal_buffer.append(signal)
    
    def aggregate(self, min_confidence: float = 0.5) -> List[Dict[str, Any]]:
        """
        执行信号聚合
        
        Returns:
            聚合后的信号组列表，每个包含融合后的信息
        """
        if not self._signal_buffer:
            return []
        
        # 1. 按信号类型分组
        signals_by_type = defaultdict(list)
        for signal in self._signal_buffer:
            if signal.confidence >= min_confidence:
                signals_by_type[signal.signal_type].append(signal)
        
        # 2. 对每组信号进行融合
        aggregated_groups = []
        
        for signal_type, signals in signals_by_type.items():
            group = self._fuse_signal_group(signals)
            aggregated_groups.append(group)
        
        # 3. 按严重程度和置信度排序
        aggregated_groups.sort(
            key=lambda x: (
                -self._severity_score(x['severity']),
                -x['avg_confidence'],
                -x['signal_count']
            )
        )
        
        # 4. 清理缓冲区
        self._signal_buffer.clear()
        self._last_aggregation = datetime.now()
        
        return aggregated_groups
    
    def _fuse_signal_group(self, signals: List[EvolutionSignal]) -> Dict[str, Any]:
        """融合一组同类信号"""
        # 收集所有证据
        all_evidence = []
        all_affected_files = set()
        all_metrics = defaultdict(list)
        
        for signal in signals:
            all_evidence.extend(signal.evidence)
            all_affected_files.update(signal.affected_files)
            
            for key, value in signal.metrics.items():
                all_metrics[key].append(value)
        
        # 聚合指标（均值）
        aggregated_metrics = {
            key: sum(values) / len(values) 
            for key, values in all_metrics.items()
        }
        
        # 计算平均置信度
        avg_confidence = sum(s.confidence for s in signals) / len(signals)
        
        # 确定最严重级别
        severity_order = {'critical': 3, 'warning': 2, 'info': 1}
        max_severity = max(signals, key=lambda s: severity_order.get(s.severity, 0)).severity
        
        return {
            'signal_type': signals[0].signal_type,
            'sensor_type': signals[0].sensor_type.value,
            'signal_count': len(signals),
            'severity': max_severity,
            'avg_confidence': avg_confidence,
            'evidence': list(set(all_evidence)),  # 去重
            'affected_files': list(all_affected_files),
            'metrics': aggregated_metrics,
            'sample_signals': [s.to_dict() for s in signals[:3]],  # 保留前3个样本
            'aggregated_id': hashlib.md5(
                f"{signals[0].signal_type}_{signals[0].sensor_type.value}".encode()
            ).hexdigest()[:12]
        }
    
    def _severity_score(self, severity: str) -> int:
        """严重程度分数"""
        scores = {'critical': 3, 'warning': 2, 'info': 1}
        return scores.get(severity, 0)
```

---

## 五、进化提案生成器

### 5.1 提案结构

```python
# proposal/evolution_proposal.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid

class ProposalType(Enum):
    """提案类型"""
    REFACTOR = "refactor"              # 重构提案
    OPTIMIZE = "optimize"             # 优化提案
    MIGRATE = "migrate"               # 迁移提案
    UPGRADE = "upgrade"               # 升级提案
    SECURITY = "security"             # 安全加固
    SCALE = "scale"                   # 扩展提案
    COST_REDUCE = "cost_reduce"       # 降本提案

class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"        # 低风险，AST验证兼容
    MEDIUM = "medium"  # 中风险，需用户确认
    HIGH = "high"     # 高风险，需详细评审
    CRITICAL = "critical"  # 极高风险，禁止自动执行

class ProposalStatus(Enum):
    """提案状态"""
    DRAFT = "draft"           # 草稿
    PROPOSED = "proposed"     # 已提出
    APPROVED = "approved"     # 已批准
    EXECUTING = "executing"   # 执行中
    COMPLETED = "completed"    # 已完成
    REJECTED = "rejected"     # 已拒绝
    ROLLED_BACK = "rolled_back"  # 已回滚

@dataclass
class TriggerSignal:
    """触发信号"""
    signal_type: str
    severity: str
    evidence: List[str]
    confidence: float
    metrics: Dict[str, float]

@dataclass
class Benefit:
    """预期收益"""
    category: str              # "性能"/"安全"/"成本"/"可维护性"
    metric_name: str           # e.g., "latency_reduction"
    current_value: float       # 当前值
    target_value: float        # 目标值
    improvement_pct: float     # 改善百分比
    confidence: float          # 预估置信度

@dataclass
class ExecutionStep:
    """执行步骤"""
    step_id: str
    title: str
    description: str
    affected_files: List[str]
    estimated_duration_minutes: int
    requires_approval: bool
    rollback_on_failure: bool
    verification_command: Optional[str] = None

@dataclass
class EvolutionProposal:
    """
    进化提案
    
    结构化提案，包含触发信号、预期收益、实施路径、风险评估
    """
    # 基本信息
    proposal_id: str = field(default_factory=lambda: f"REFACTOR-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}")
    title: str = ""
    proposal_type: ProposalType = ProposalType.REFACTOR
    
    # 状态
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 触发信号
    trigger_signals: List[TriggerSignal] = field(default_factory=list)
    
    # 预期收益
    benefits: List[Benefit] = field(default_factory=list)
    
    # 实施路径
    execution_steps: List[ExecutionStep] = field(default_factory=list)
    
    # 风险评估
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_factors: List[str] = field(default_factory=list)
    mitigation_plan: str = ""
    
    # 工时估算
    estimated_hours: float = 0.0
    auto_executable: bool = False  # 是否可自动执行
    
    # 元数据
    confidence: float = 0.0  # 提案整体置信度
    reviewer_notes: str = ""
    execution_result: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'proposal_id': self.proposal_id,
            'title': self.title,
            'proposal_type': self.proposal_type.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'trigger_signals': [s.__dict__ for s in self.trigger_signals],
            'benefits': [b.__dict__ for b in self.benefits],
            'execution_steps': [s.__dict__ for s in self.execution_steps],
            'risk_level': self.risk_level.value,
            'estimated_hours': self.estimated_hours,
            'auto_executable': self.auto_executable,
            'confidence': self.confidence,
        }
    
    def to_markdown(self) -> str:
        """生成Markdown格式提案"""
        lines = [
            f"# {self.proposal_id}",
            f"## {self.title}",
            f"",
            f"**类型**: {self.proposal_type.value} | **风险**: {self.risk_level.value} | **置信度**: {self.confidence:.0%}",
            f"",
            f"## 触发信号",
        ]
        
        for signal in self.trigger_signals:
            lines.append(f"- **{signal.signal_type}** ({signal.severity})")
            for evidence in signal.evidence[:3]:
                lines.append(f"  - {evidence}")
        
        lines.extend([
            f"",
            f"## 预期收益",
        ])
        
        for benefit in self.benefits:
            lines.append(
                f"- {benefit.category}: {benefit.metric_name} "
                f"{benefit.current_value:.1f} → {benefit.target_value:.1f} "
                f"(+{benefit.improvement_pct:.0f}%)"
            )
        
        lines.extend([
            f"",
            f"## 实施路径 ({len(self.execution_steps)} 步)",
        ])
        
        for i, step in enumerate(self.execution_steps, 1):
            lines.append(f"### 步骤 {i}: {step.title}")
            lines.append(f"{step.description}")
            if step.affected_files:
                lines.append(f"**影响文件**: {', '.join(step.affected_files[:5])}")
            lines.append("")
        
        if self.risk_factors:
            lines.extend([
                f"## 风险因素",
                *[f"- {risk}" for risk in self.risk_factors],
                f"",
            ])
        
        lines.extend([
            f"## 行动",
            f"- 预计工时: {self.estimated_hours:.1f} 小时",
            f"- 自动执行: {'✅ 是' if self.auto_executable else '❌ 否，需用户确认'}",
        ])
        
        return "\n".join(lines)
```

### 5.2 提案生成器

```python
# proposal/proposal_generator.py

from typing import List, Dict, Any, Optional
from core.fusion_rag.fusion_engine import FusionEngine
from core.knowledge_graph.knowledge_graph_manager import KnowledgeGraphManager
import re

class ProposalGenerator:
    """
    进化提案生成器
    
    输入：聚合后的信号组
    输出：结构化进化提案
    """
    
    # 提案模板规则
    PROPOSAL_RULES = {
        'high_latency': {
            'type': ProposalType.OPTIMIZE,
            'benefit_type': '性能',
            'metric': 'latency_reduction',
            'target_improvement': 0.4,  # 目标提升40%
            'risk': RiskLevel.MEDIUM,
        },
        'memory_leak': {
            'type': ProposalType.OPTIMIZE,
            'benefit_type': '稳定性',
            'metric': 'memory_stability',
            'target_improvement': 0.8,
            'risk': RiskLevel.LOW,
        },
        'circular_dependency': {
            'type': ProposalType.REFACTOR,
            'benefit_type': '可维护性',
            'metric': 'dependency_health',
            'target_improvement': 0.3,
            'risk': RiskLevel.HIGH,
        },
        'god_class': {
            'type': ProposalType.REFACTOR,
            'benefit_type': '可维护性',
            'metric': 'class_cohesion',
            'target_improvement': 0.5,
            'risk': RiskLevel.MEDIUM,
        },
        'outdated_api': {
            'type': ProposalType.UPGRADE,
            'benefit_type': '安全性',
            'metric': 'api_freshness',
            'target_improvement': 1.0,
            'risk': RiskLevel.MEDIUM,
        },
        'security_vuln': {
            'type': ProposalType.SECURITY,
            'benefit_type': '安全性',
            'metric': 'security_score',
            'target_improvement': 1.0,
            'risk': RiskLevel.LOW,
        },
    }
    
    def __init__(self, knowledge_graph: Optional[KnowledgeGraphManager] = None):
        self.kg = knowledge_graph
        self.fusion_engine = FusionEngine()
    
    def generate(self, aggregated_signals: List[Dict[str, Any]]) -> List[EvolutionProposal]:
        """生成进化提案列表"""
        proposals = []
        
        for signal_group in aggregated_signals:
            proposal = self._generate_proposal(signal_group)
            if proposal:
                proposals.append(proposal)
        
        # 按置信度排序
        proposals.sort(key=lambda p: -p.confidence)
        
        return proposals
    
    def _generate_proposal(self, signal_group: Dict[str, Any]) -> Optional[EvolutionProposal]:
        """为单个信号组生成提案"""
        signal_type = signal_group['signal_type']
        
        # 查找匹配规则
        rule = self.PROPOSAL_RULES.get(signal_type)
        if not rule:
            return None
        
        # 创建提案
        proposal = EvolutionProposal(
            title=self._generate_title(signal_type, signal_group),
            proposal_type=rule['type'],
            status=ProposalStatus.PROPOSED,
            confidence=signal_group['avg_confidence'],
            risk_level=rule['risk'],
        )
        
        # 添加触发信号
        for sample in signal_group.get('sample_signals', []):
            proposal.trigger_signals.append(TriggerSignal(
                signal_type=sample['signal_type'],
                severity=sample['severity'],
                evidence=sample.get('evidence', []),
                confidence=sample.get('confidence', 0.5),
                metrics=sample.get('metrics', {})
            ))
        
        # 计算收益
        proposal.benefits = self._calculate_benefits(signal_group, rule)
        
        # 生成执行步骤
        proposal.execution_steps = self._generate_steps(signal_group, rule)
        
        # 评估风险
        proposal.risk_factors = self._assess_risk_factors(signal_group)
        
        # 估算工时
        proposal.estimated_hours = self._estimate_hours(proposal)
        
        # 确定是否可自动执行
        proposal.auto_executable = self._can_auto_execute(proposal)
        
        return proposal
    
    def _generate_title(self, signal_type: str, signal_group: Dict) -> str:
        """生成提案标题"""
        titles = {
            'high_latency': f"性能优化：API响应时间过高（{signal_group.get('metrics', {}).get('latency_ms', 'N/A')}ms）",
            'memory_leak': "内存泄漏修复",
            'circular_dependency': "循环依赖重构",
            'god_class': f"上帝类拆分（{len(signal_group.get('affected_files', []))}处）",
            'outdated_api': "API版本升级",
            'security_vuln': "安全漏洞修复",
            'high_error_rate': "错误率降低",
        }
        return titles.get(signal_type, f"问题修复：{signal_type}")
    
    def _calculate_benefits(self, signal_group: Dict, rule: Dict) -> List[Benefit]:
        """计算预期收益"""
        metrics = signal_group.get('metrics', {})
        benefits = []
        
        benefit = Benefit(
            category=rule['benefit_type'],
            metric_name=rule['metric'],
            current_value=metrics.get(list(metrics.keys())[0], 100) if metrics else 100,
            target_value=0,  # 待计算
            improvement_pct=rule['target_improvement'] * 100,
            confidence=signal_group['avg_confidence'] * 0.8
        )
        
        # 计算目标值
        benefit.target_value = benefit.current_value * (1 - rule['target_improvement'])
        
        benefits.append(benefit)
        return benefits
    
    def _generate_steps(self, signal_group: Dict, rule: Dict) -> List[ExecutionStep]:
        """生成执行步骤"""
        steps = []
        affected_files = signal_group.get('affected_files', [])
        
        signal_type = signal_group['signal_type']
        
        if signal_type == 'high_latency':
            steps.extend([
                ExecutionStep(
                    step_id="step_1",
                    title="性能瓶颈定位",
                    description="使用profiler定位具体瓶颈点",
                    affected_files=affected_files[:3],
                    estimated_duration_minutes=30,
                    requires_approval=False,
                    rollback_on_failure=False,
                    verification_command="python -m cProfile -s cumulative target.py"
                ),
                ExecutionStep(
                    step_id="step_2",
                    title="应用性能优化",
                    description="添加缓存/异步处理/索引优化",
                    affected_files=affected_files,
                    estimated_duration_minutes=120,
                    requires_approval=True,
                    rollback_on_failure=True,
                    verification_command="pytest tests/performance/"
                ),
                ExecutionStep(
                    step_id="step_3",
                    title="性能验证",
                    description="运行性能测试套件验证改善效果",
                    affected_files=[],
                    estimated_duration_minutes=60,
                    requires_approval=False,
                    rollback_on_failure=False,
                    verification_command="python benchmarks/run.py"
                ),
            ])
        
        elif signal_type == 'circular_dependency':
            steps.extend([
                ExecutionStep(
                    step_id="step_1",
                    title="依赖分析",
                    description="生成依赖图，识别循环依赖路径",
                    affected_files=affected_files,
                    estimated_duration_minutes=20,
                    requires_approval=False,
                    rollback_on_failure=False
                ),
                ExecutionStep(
                    step_id="step_2",
                    title="接口抽象",
                    description="为循环依赖创建接口/抽象类打破循环",
                    affected_files=affected_files,
                    estimated_duration_minutes=60,
                    requires_approval=True,
                    rollback_on_failure=True
                ),
                ExecutionStep(
                    step_id="step_3",
                    title="验证测试",
                    description="运行测试确保重构不破坏功能",
                    affected_files=[],
                    estimated_duration_minutes=30,
                    requires_approval=False,
                    rollback_on_failure=True
                ),
            ])
        
        return steps
    
    def _assess_risk_factors(self, signal_group: Dict) -> List[str]:
        """评估风险因素"""
        factors = []
        
        if len(signal_group.get('affected_files', [])) > 10:
            factors.append("影响文件较多，需谨慎评估")
        
        if signal_group['severity'] == 'critical':
            factors.append("关键系统组件，失败影响大")
        
        return factors
    
    def _estimate_hours(self, proposal: EvolutionProposal) -> float:
        """估算工时"""
        base_hours = sum(step.estimated_duration_minutes for step in proposal.execution_steps) / 60
        
        # 风险系数
        risk_multiplier = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 1.2,
            RiskLevel.HIGH: 1.5,
            RiskLevel.CRITICAL: 2.0,
        }
        
        return base_hours * risk_multiplier.get(proposal.risk_level, 1.0)
    
    def _can_auto_execute(self, proposal: EvolutionProposal) -> bool:
        """判断是否可自动执行"""
        # 低风险且所有步骤都不需要审批
        if proposal.risk_level != RiskLevel.LOW:
            return False
        
        for step in proposal.execution_steps:
            if step.requires_approval:
                return False
        
        # 检查是否有关键文件
        critical_patterns = ['main.py', 'core/__init__.py', 'config/']
        for step in proposal.execution_steps:
            for file in step.affected_files:
                if any(pattern in file for pattern in critical_patterns):
                    return False
        
        return True
```

---

## 六、自治执行引擎

### 6.1 沙箱执行器

```python
# executor/sandbox_executor.py

import os
import subprocess
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import tempfile
import git
from datetime import datetime

class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

@dataclass
class ExecutionResult:
    """执行结果"""
    step_id: str
    status: ExecutionStatus
    output: str
    error: Optional[str]
    duration_seconds: float
    changes: List[str]  # 变更文件列表

class SandboxExecutor:
    """
    安全沙箱执行器
    
    特性：
    - Git分支隔离，不直接修改主分支
    - 变更预览（diff）
    - 自动回滚
    - 验证关卡
    """
    
    def __init__(self, project_root: str, sandbox_dir: Optional[str] = None):
        self.project_root = Path(project_root)
        self.sandbox_dir = Path(sandbox_dir) if sandbox_dir else self.project_root
        
        # 备份目录
        self.backup_dir = self.sandbox_dir / ".evolution_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 分支管理
        self.repo = git.Repo(self.project_root)
        
        # 回调
        self.on_step_complete: Optional[Callable] = None
        self.on_failure: Optional[Callable] = None
    
    def execute_proposal(self, proposal: EvolutionProposal) -> Dict[str, Any]:
        """
        执行进化提案
        
        Returns:
            执行结果摘要
        """
        results = []
        backup_id = self._create_backup(proposal.proposal_id)
        
        try:
            for step in proposal.execution_steps:
                result = self._execute_step(step, proposal)
                results.append(result)
                
                if result.status == ExecutionStatus.FAILED:
                    # 自动回滚
                    self._rollback(backup_id, proposal.proposal_id)
                    return {
                        'success': False,
                        'failed_step': step.step_id,
                        'results': results,
                        'backup_id': backup_id,
                    }
                
                # 触发回调
                if self.on_step_complete:
                    self.on_step_complete(step, result)
            
            return {
                'success': True,
                'results': results,
                'backup_id': backup_id,
            }
            
        except Exception as e:
            self._rollback(backup_id, proposal.proposal_id)
            return {
                'success': False,
                'error': str(e),
                'backup_id': backup_id,
            }
    
    def _execute_step(self, step: ExecutionStep, proposal: EvolutionProposal) -> ExecutionResult:
        """执行单个步骤"""
        import time
        start_time = time.time()
        
        # 1. 如果需要审批，跳过
        if step.requires_approval:
            return ExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.PENDING,
                output="等待用户审批",
                error=None,
                duration_seconds=0,
                changes=[]
            )
        
        # 2. 创建Git分支
        branch_name = f"evolution/{proposal.proposal_id}/{step.step_id}"
        self._create_branch(branch_name)
        
        # 3. 应用变更（这里调用代码生成器生成修改）
        changes = self._apply_changes(step, proposal)
        
        # 4. 运行验证
        if step.verification_command:
            verified, output = self._run_verification(step.verification_command)
            
            if not verified:
                return ExecutionResult(
                    step_id=step.step_id,
                    status=ExecutionStatus.FAILED,
                    output=output,
                    error="验证失败",
                    duration_seconds=time.time() - start_time,
                    changes=changes
                )
        
        # 5. 提交变更
        self._commit_changes(branch_name, step.title)
        
        return ExecutionResult(
            step_id=step.step_id,
            status=ExecutionStatus.PASSED,
            output="执行成功",
            error=None,
            duration_seconds=time.time() - start_time,
            changes=changes
        )
    
    def _create_backup(self, proposal_id: str) -> str:
        """创建备份"""
        backup_id = f"{proposal_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = self.backup_dir / backup_id
        
        # 复制项目到备份目录
        shutil.copytree(self.project_root, backup_path, 
                       ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', '.venv'))
        
        return backup_id
    
    def _rollback(self, backup_id: str, proposal_id: str):
        """回滚到备份"""
        backup_path = self.backup_dir / backup_id
        
        if not backup_path.exists():
            return
        
        # 清理当前项目（保留.git）
        for item in self.project_root.iterdir():
            if item.name == '.git':
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        
        # 恢复备份
        shutil.copytree(backup_path, self.project_root, 
                       ignore=shutil.ignore_patterns('.git', '__pycache__'))
        
        # 清理分支
        self._cleanup_branches(proposal_id)
    
    def _create_branch(self, branch_name: str):
        """创建分支"""
        try:
            # 切换到新分支
            self.repo.git.checkout('-b', branch_name)
        except git.GitCommandError:
            # 分支可能已存在，切换过去
            self.repo.git.checkout(branch_name)
    
    def _apply_changes(self, step: ExecutionStep, proposal: EvolutionProposal) -> List[str]:
        """应用变更"""
        # 这里应该集成代码生成器
        # 简化实现：只是读取文件并标记为已处理
        
        changed_files = []
        for file_path in step.affected_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                changed_files.append(file_path)
        
        return changed_files
    
    def _run_verification(self, command: str) -> tuple:
        """运行验证"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            return (result.returncode == 0, result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "验证超时")
        except Exception as e:
            return (False, str(e))
    
    def _commit_changes(self, branch_name: str, message: str):
        """提交变更"""
        self.repo.git.add('-A')
        
        if self.repo.is_dirty():
            self.repo.index.commit(f"{message}\n\nEvolution: {branch_name}")
        
        # 切回主分支
        self.repo.git.checkout('main' if 'main' in [h.name for h in self.repo.heads] else 'master')
    
    def _cleanup_branches(self, proposal_id: str):
        """清理相关分支"""
        prefix = f"evolution/{proposal_id}"
        
        for branch in self.repo.heads:
            if branch.name.startswith(prefix):
                self.repo.delete_head(branch, force=True)
    
    def preview_changes(self, proposal: EvolutionProposal) -> Dict[str, Any]:
        """预览变更"""
        changes = []
        
        for step in proposal.execution_steps:
            step_changes = {
                'step_id': step.step_id,
                'title': step.title,
                'affected_files': step.affected_files,
                'requires_approval': step.requires_approval,
            }
            
            # 生成diff预览
            diffs = []
            for file_path in step.affected_files[:10]:  # 限制数量
                full_path = self.project_root / file_path
                if full_path.exists():
                    diffs.append(f"# {file_path}\n# 变更预览...")
            
            step_changes['diffs'] = diffs
            changes.append(step_changes)
        
        return {
            'proposal_id': proposal.proposal_id,
            'total_steps': len(proposal.execution_steps),
            'total_affected_files': sum(len(s.affected_files) for s in proposal.execution_steps),
            'steps': changes,
        }
```

---

## 七、进化记忆层

### 7.1 进化日志

```python
# memory/evolution_log.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import sqlite3

@dataclass
class EvolutionRecord:
    """进化记录"""
    record_id: str
    proposal_id: str
    timestamp: datetime
    
    # 执行信息
    trigger_signals: List[str]
    proposal_type: str
    risk_level: str
    
    # 执行结果
    success: bool
    auto_executed: bool
    steps_completed: int
    total_steps: int
    duration_seconds: float
    
    # 反馈
    user_rating: Optional[float] = None  # 1-5星
    user_feedback: str = ""
    improvement_achieved: Dict[str, float] = field(default_factory=dict)
    
    # 学习
    lessons_learned: List[str] = field(default_factory=list)
    retry_recommended: bool = False

class EvolutionLog:
    """
    进化日志
    
    功能：
    - 记录每次进化结果
    - 分析成功率
    - 提取经验教训
    - 强化学习反馈
    """
    
    def __init__(self, log_dir: str = "~/.livingtree/evolution"):
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite存储
        self.db_path = self.log_dir / "evolution_log.db"
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evolution_records (
                record_id TEXT PRIMARY KEY,
                proposal_id TEXT,
                timestamp TEXT,
                trigger_signals TEXT,
                proposal_type TEXT,
                risk_level TEXT,
                success INTEGER,
                auto_executed INTEGER,
                steps_completed INTEGER,
                total_steps INTEGER,
                duration_seconds REAL,
                user_rating REAL,
                user_feedback TEXT,
                improvement_achieved TEXT,
                lessons_learned TEXT,
                retry_recommended INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    def log(self, record: EvolutionRecord):
        """记录进化结果"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO evolution_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.record_id,
            record.proposal_id,
            record.timestamp.isoformat(),
            json.dumps(record.trigger_signals),
            record.proposal_type,
            record.risk_level,
            int(record.success),
            int(record.auto_executed),
            record.steps_completed,
            record.total_steps,
            record.duration_seconds,
            record.user_rating,
            record.user_feedback,
            json.dumps(record.improvement_achieved),
            json.dumps(record.lessons_learned),
            int(record.retry_recommended),
        ))
        
        conn.commit()
        conn.close()
    
    def get_success_rate(self, proposal_type: Optional[str] = None) -> float:
        """获取成功率"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if proposal_type:
            cursor.execute(
                "SELECT COUNT(*) FROM evolution_records WHERE success=1 AND proposal_type=?",
                (proposal_type,)
            )
            success_count = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT COUNT(*) FROM evolution_records WHERE proposal_type=?",
                (proposal_type,)
            )
            total_count = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM evolution_records WHERE success=1")
            success_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM evolution_records")
            total_count = cursor.fetchone()[0]
        
        conn.close()
        
        return success_count / total_count if total_count > 0 else 0.0
    
    def get_lessons_learned(self) -> List[str]:
        """获取学到的经验"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT lessons_learned FROM evolution_records WHERE success=1")
        rows = cursor.fetchall()
        
        conn.close()
        
        lessons = []
        for row in rows:
            lessons.extend(json.loads(row[0]))
        
        return list(set(lessons))  # 去重
```

---

## 八、安全围栏

### 8.1 安全策略

```python
# safety/fence.py

from typing import List, Dict, Any
from enum import Enum

class SafetyLevel(Enum):
    """安全级别"""
    FULL_AUTO = "full_auto"      # 全自动（仅低风险）
    USER_CONFIRM = "user_confirm"  # 用户确认后执行
    MANUAL_ONLY = "manual_only"   # 仅手动执行
    BLOCKED = "blocked"          # 禁止执行

class SafetyFence:
    """
    安全围栏
    
    功能：
    - 评估变更影响范围
    - 确定执行权限
    - 伦理边界检查
    - 用户确认机制
    """
    
    # 禁止自动修改的模式
    FORBIDDEN_PATTERNS = [
        '**/core/__init__.py',
        '**/main.py',
        '**/config/secrets.yaml',
        '**/config/keys.json',
        '**/.env',
        '**/requirements.txt',  # 依赖变更需谨慎
        '**/package.json',       # npm包变更需谨慎
    ]
    
    # 需要用户确认的文件
    REQUIRES_CONFIRMATION = [
        '**/core/**/*.py',
        '**/server/**/*.py',
        '**/config/**/*.py',
        '**/config/*.yaml',
        '**/config/*.json',
    ]
    
    # 伦理边界规则
    ETHICAL_RULES = [
        "禁止删除用户代码（只能添加或修改）",
        "禁止修改核心业务逻辑",
        "禁止添加未经授权的第三方服务",
        "禁止修改安全相关的代码",
        "禁止添加后门或监控代码",
    ]
    
    def __init__(self):
        self._user_approvals: Dict[str, bool] = {}
    
    def assess(self, proposal: EvolutionProposal) -> Dict[str, Any]:
        """
        评估提案安全性
        
        Returns:
            安全评估结果
        """
        assessment = {
            'safety_level': SafetyLevel.USER_CONFIRM,
            'requires_approval': False,
            'blocked': False,
            'block_reason': None,
            'affected_critical_files': [],
            'warnings': [],
        }
        
        # 1. 检查是否涉及禁止文件
        forbidden_files = self._check_forbidden_files(proposal)
        if forbidden_files:
            assessment['safety_level'] = SafetyLevel.BLOCKED
            assessment['blocked'] = True
            assessment['block_reason'] = f"涉及禁止修改的文件: {forbidden_files}"
            return assessment
        
        # 2. 检查影响范围
        critical_files = self._check_critical_files(proposal)
        if critical_files:
            assessment['affected_critical_files'] = critical_files
            assessment['warnings'].append(f"涉及 {len(critical_files)} 个核心文件")
        
        # 3. 评估伦理合规
        ethical_violations = self._check_ethical_compliance(proposal)
        if ethical_violations:
            assessment['safety_level'] = SafetyLevel.BLOCKED
            assessment['blocked'] = True
            assessment['block_reason'] = f"违反伦理规则: {ethical_violations}"
            return assessment
        
        # 4. 确定安全级别
        if proposal.risk_level == RiskLevel.LOW and not critical_files:
            assessment['safety_level'] = SafetyLevel.FULL_AUTO
        elif proposal.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            assessment['safety_level'] = SafetyLevel.USER_CONFIRM
            assessment['requires_approval'] = True
        else:
            assessment['safety_level'] = SafetyLevel.MANUAL_ONLY
            assessment['requires_approval'] = True
        
        return assessment
    
    def _check_forbidden_files(self, proposal: EvolutionProposal) -> List[str]:
        """检查禁止文件"""
        import fnmatch
        
        forbidden = []
        
        for step in proposal.execution_steps:
            for file_path in step.affected_files:
                for pattern in self.FORBIDDEN_PATTERNS:
                    if fnmatch.fnmatch(file_path, pattern):
                        forbidden.append(file_path)
        
        return list(set(forbidden))
    
    def _check_critical_files(self, proposal: EvolutionProposal) -> List[str]:
        """检查核心文件"""
        import fnmatch
        
        critical = []
        
        for step in proposal.execution_steps:
            for file_path in step.affected_files:
                for pattern in self.REQUIRES_CONFIRMATION:
                    if fnmatch.fnmatch(file_path, pattern):
                        critical.append(file_path)
        
        return list(set(critical))
    
    def _check_ethical_compliance(self, proposal: EvolutionProposal) -> List[str]:
        """检查伦理合规"""
        # 这里应该实现更复杂的逻辑
        # 简化版本：检查提案标题/描述中是否包含敏感词
        
        sensitive_keywords = ['删除', '删除所有', '移除核心', '替换全部', 'drop table']
        
        violations = []
        full_text = proposal.title + ' ' + ' '.join(
            step.description for step in proposal.execution_steps
        )
        
        for keyword in sensitive_keywords:
            if keyword in full_text:
                violations.append(f"包含敏感词: {keyword}")
        
        return violations
```

---

## 九、Evolution Engine 主控制器

### 9.1 主控制器

```python
# evolution_engine.py

from typing import List, Dict, Any, Optional
from pathlib import Path
import threading
import time

class EvolutionEngine:
    """
    Evolution Engine 主控制器
    
    协调所有组件，实现"感知-诊断-规划-执行"闭环
    """
    
    def __init__(
        self,
        project_root: str,
        config: Optional[Dict[str, Any]] = None
    ):
        self.config = config or {}
        self.project_root = Path(project_root)
        
        # 初始化组件
        self._init_sensors()
        self._init_aggregator()
        self._init_proposal_generator()
        self._init_executor()
        self._init_memory()
        self._init_safety_fence()
        
        # 运行控制
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 提案队列
        self._proposal_queue: List[EvolutionProposal] = []
    
    def _init_sensors(self):
        """初始化传感器"""
        from sensors.performance_sensor import PerformanceSensor
        from sensors.architecture_smell_sensor import ArchitectureSmellSensor
        
        self.sensors = {
            'performance': PerformanceSensor(self.config.get('sensor', {})),
            'architecture': ArchitectureSmellSensor(str(self.project_root)),
        }
        
        # 连接信号输出
        for sensor in self.sensors.values():
            sensor.on_signal = self._on_sensor_signal
    
    def _init_aggregator(self):
        """初始化信号聚合器"""
        from aggregator.signal_aggregator import SignalAggregator
        self.aggregator = SignalAggregator()
    
    def _init_proposal_generator(self):
        """初始化提案生成器"""
        from proposal.proposal_generator import ProposalGenerator
        self.proposal_generator = ProposalGenerator()
    
    def _init_executor(self):
        """初始化执行器"""
        from executor.sandbox_executor import SandboxExecutor
        self.executor = SandboxExecutor(str(self.project_root))
    
    def _init_memory(self):
        """初始化记忆"""
        from memory.evolution_log import EvolutionLog
        self.evolution_log = EvolutionLog()
    
    def _init_safety_fence(self):
        """初始化安全围栏"""
        from safety.fence import SafetyFence
        self.safety_fence = SafetyFence()
    
    def start(self):
        """启动Evolution Engine"""
        if self._running:
            return
        
        self._running = True
        
        # 启动传感器
        if hasattr(self.sensors['performance'], 'start'):
            self.sensors['performance'].start()
        
        # 启动后台循环
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止Evolution Engine"""
        self._running = False
        
        if hasattr(self.sensors['performance'], 'stop'):
            self.sensors['performance'].stop()
        
        if self._thread:
            self._thread.join(timeout=5)
    
    def _run_loop(self):
        """主循环"""
        while self._running:
            try:
                # 1. 收集信号
                self._collect_signals()
                
                # 2. 聚合信号
                aggregated = self.aggregator.aggregate()
                
                # 3. 生成提案
                if aggregated:
                    proposals = self.proposal_generator.generate(aggregated)
                    self._proposal_queue.extend(proposals)
                
                # 4. 处理提案队列
                self._process_proposals()
                
                # 休眠
                time.sleep(3600)  # 每小时执行一次
                
            except Exception as e:
                print(f"[EvolutionEngine] 循环异常: {e}")
                time.sleep(60)  # 出错后1分钟重试
    
    def _collect_signals(self):
        """收集信号"""
        # 触发架构扫描
        if 'architecture' in self.sensors:
            signals = self.sensors['architecture'].scan()
            for signal in signals:
                self.aggregator.add_signal(signal)
    
    def _on_sensor_signal(self, signal):
        """处理传感器信号"""
        self.aggregator.add_signal(signal)
    
    def _process_proposals(self):
        """处理提案队列"""
        while self._proposal_queue:
            proposal = self._proposal_queue.pop(0)
            
            # 安全评估
            safety = self.safety_fence.assess(proposal)
            
            if safety['blocked']:
                print(f"[EvolutionEngine] 提案被阻止: {safety['block_reason']}")
                continue
            
            if safety['safety_level'] == SafetyLevel.USER_CONFIRM:
                # 添加到待确认队列
                self._notify_user(proposal, safety)
                continue
            
            if safety['safety_level'] == SafetyLevel.FULL_AUTO and proposal.auto_executable:
                # 自动执行
                self._execute_proposal(proposal)
    
    def _notify_user(self, proposal: EvolutionProposal, safety: Dict):
        """通知用户审批"""
        print(f"\n{'='*60}")
        print(f"📋 进化提案: {proposal.proposal_id}")
        print(f"{'='*60}")
        print(proposal.to_markdown())
        print(f"\n安全评估: {safety['safety_level'].value}")
        if safety.get('affected_critical_files'):
            print(f"影响核心文件: {len(safety['affected_critical_files'])} 个")
        print(f"{'='*60}\n")
    
    def _execute_proposal(self, proposal: EvolutionProposal):
        """执行提案"""
        print(f"[EvolutionEngine] 开始执行: {proposal.proposal_id}")
        
        # 预览变更
        preview = self.executor.preview_changes(proposal)
        print(f"[EvolutionEngine] 变更预览: {preview}")
        
        # 执行
        result = self.executor.execute_proposal(proposal)
        
        # 记录结果
        self._log_result(proposal, result)
    
    def _log_result(self, proposal: EvolutionProposal, result: Dict):
        """记录执行结果"""
        from memory.evolution_log import EvolutionRecord
        
        record = EvolutionRecord(
            record_id=f"log_{int(time.time())}",
            proposal_id=proposal.proposal_id,
            timestamp=datetime.now(),
            trigger_signals=[s.signal_type for s in proposal.trigger_signals],
            proposal_type=proposal.proposal_type.value,
            risk_level=proposal.risk_level.value,
            success=result.get('success', False),
            auto_executed=proposal.auto_executable,
            steps_completed=len([r for r in result.get('results', []) if r.status == ExecutionStatus.PASSED]),
            total_steps=len(proposal.execution_steps),
            duration_seconds=sum(r.duration_seconds for r in result.get('results', []))
        )
        
        self.evolution_log.log(record)
    
    def get_proposals(self) -> List[EvolutionProposal]:
        """获取当前提案列表"""
        return self._proposal_queue.copy()
    
    def approve_proposal(self, proposal_id: str):
        """用户批准提案"""
        for proposal in self._proposal_queue:
            if proposal.proposal_id == proposal_id:
                self._proposal_queue.remove(proposal)
                self._execute_proposal(proposal)
                return True
        return False
```

---

## 十、目录结构

```
core/evolution_engine/
├── __init__.py
├── evolution_engine.py          # 主控制器
│
├── sensors/
│   ├── __init__.py
│   ├── base.py                  # 传感器基类
│   ├── performance_sensor.py    # 性能监控
│   ├── error_sensor.py           # 错误模式
│   ├── architecture_smell_sensor.py  # 架构异味
│   ├── tech_debt_sensor.py       # 技术债
│   ├── security_sensor.py        # 安全扫描
│   ├── competitor_sensor.py      # 竞品监测
│   └── user_behavior_sensor.py   # 用户行为
│
├── aggregator/
│   ├── __init__.py
│   └── signal_aggregator.py      # 信号聚合器
│
├── proposal/
│   ├── __init__.py
│   ├── evolution_proposal.py     # 提案数据结构
│   └── proposal_generator.py     # 提案生成器
│
├── executor/
│   ├── __init__.py
│   ├── sandbox_executor.py       # 沙箱执行器
│   └── git_manager.py            # Git分支管理
│
├── memory/
│   ├── __init__.py
│   └── evolution_log.py          # 进化日志
│
└── safety/
    ├── __init__.py
    └── fence.py                  # 安全围栏
```

---

## 十一、集成方案

### 11.1 与现有模块集成

| 现有模块 | 集成方式 |
|----------|----------|
| **Intent Engine** | 作为"用户行为传感器"的数据源 |
| **CodeAnalyzer** | 增强为架构异味传感器 |
| **ResourceMonitor** | 作为性能传感器的数据源 |
| **StructuredLogger** | 作为错误模式传感器的数据源 |
| **GitHubTrendingAPI** | 作为竞品监测传感器的数据源 |
| **FusionRAG** | 提案生成时检索历史案例 |
| **SelfEvolution** | 共用进化记忆层 |
| **ExperienceOptimizer** | 用户行为传感器的数据来源 |
| **SmartIDE Panel** | 新增"Evolution"面板展示提案 |

### 11.2 UI集成

```python
# ui/evolution_panel.py (新增面板)

class EvolutionPanel(QWidget):
    """Evolution Engine 控制面板"""
    
    def __init__(self, engine: EvolutionEngine):
        self.engine = engine
        
        # 提案列表
        self.proposal_list = QListWidget()
        
        # 提案详情
        self.proposal_detail = QTextEdit()
        
        # 动作按钮
        self.approve_btn = QPushButton("批准执行")
        self.reject_btn = QPushButton("拒绝")
        self.preview_btn = QPushButton("预览变更")
        
        # 连接信号
        self.proposal_list.currentItemChanged.connect(self._show_detail)
        self.approve_btn.clicked.connect(self._on_approve)
        self.reject_btn.clicked.connect(self._on_reject)
        
        # 刷新定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(5000)
    
    def _refresh(self):
        """刷新提案列表"""
        proposals = self.engine.get_proposals()
        
        self.proposal_list.clear()
        for proposal in proposals:
            item = QListWidgetItem(f"📋 {proposal.proposal_id}: {proposal.title}")
            self.proposal_list.addItem(item)
    
    def _show_detail(self, item):
        """显示提案详情"""
        if not item:
            return
        
        idx = self.proposal_list.currentRow()
        proposals = self.engine.get_proposals()
        
        if 0 <= idx < len(proposals):
            self.proposal_detail.setMarkdown(proposals[idx].to_markdown())
    
    def _on_approve(self):
        """批准提案"""
        idx = self.proposal_list.currentRow()
        proposals = self.engine.get_proposals()
        
        if 0 <= idx < len(proposals):
            self.engine.approve_proposal(proposals[idx].proposal_id)
    
    def _on_reject(self):
        """拒绝提案"""
        idx = self.proposal_list.currentRow()
        proposals = self.engine.get_proposals()
        
        if 0 <= idx < len(proposals):
            self._proposal_queue.pop(idx)
```

---

## 十二、实施路线图

### Phase 1: 感知层（MVP，1周）

```
目标：建立基础感知能力
✅ PerformanceSensor - 集成ResourceMonitor
✅ ArchitectureSmellSensor - 增强现有CodeAnalyzer
✅ SignalAggregator - 多源信号融合
✅ 基础EvolutionPanel UI
```

### Phase 2: 提案生成（1周）

```
目标：实现结构化提案生成
✅ ProposalGenerator - 基于规则的提案模板
✅ Proposal结构定义 - 包含触发信号、收益、步骤
✅ 与FusionRAG集成 - 检索历史案例
✅ SafetyFence基础实现
```

### Phase 3: 自治执行（1周）

```
目标：实现安全的自动执行
✅ SandboxExecutor - Git分支隔离
✅ 执行步骤管理
✅ 验证关卡
✅ 回滚机制
✅ SafetyFence完善
```

### Phase 4: 进化记忆（1周）

```
目标：建立持续学习能力
✅ EvolutionLog - 记录每次进化
✅ 成功率分析
✅ 经验提取
✅ 强化学习反馈
```

### Phase 5: 生态集成（持续）

```
目标：扩展感知边界
🔄 CompetitorSensor - GitHub趋势监测
🔄 CostSensor - 云成本分析
🔄 SecuritySensor - SCA集成
🔄 UserBehaviorSensor - 埋点集成
```

---

## 十三、总结

Evolution Engine 是 LivingTreeAlAgent 从"执行工具"进化为"设计伙伴"的关键架构跨越。通过：

1. **多维度感知**：实时捕获性能、质量、生态情报
2. **智能提案**：将数据信号转化为结构化进化方案
3. **安全自治**：在围栏内实现自动执行与回滚
4. **持续学习**：通过进化日志实现自我优化

最终，用户只需定义业务目标（如"提升性能"、"降低成本"），IDE 会自动分析现状、提出路线图并执行重构。软件将具备**自我修复、自我优化**的生命特征。
