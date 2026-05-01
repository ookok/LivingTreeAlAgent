"""
自我意识系统主控制器（性能优化版）
实现零干扰的后台自动升级和修复

核心能力：
1. 自我监控 - 零干扰后台监控
2. 自我诊断 - 自动检测问题
3. 自我修复 - 自动修复部署
4. 自我反思 - 元认知能力
5. 自我进化 - 自主学习优化

性能优化：
1. 增量文件扫描（只扫描变化的目录）
2. 文件哈希缓存
3. 并行处理（线程池）
4. 历史记录上限
5. 智能调度（避免频繁测试）
"""

from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import os
import sys
import time
import threading
import queue
import hashlib
import json
import re
import fnmatch
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools


class SystemState(Enum):
    """系统状态"""
    IDLE = "idle"                    # 空闲
    MONITORING = "monitoring"        # 监控中
    TESTING = "testing"              # 测试中
    DIAGNOSING = "diagnosing"        # 诊断中
    FIXING = "fixing"                # 修复中
    DEPLOYING = "deploying"          # 部署中
    ROLLING_BACK = "rolling_back"    # 回滚中
    ERROR = "error"                  # 错误


class SelfAwarenessSystem:
    """
    自我意识系统主控制器（性能优化版）
    
    核心能力：
    1. 自我监控 - 零干扰后台监控
    2. 自我诊断 - 自动检测问题
    3. 自我修复 - 自动修复部署
    4. 自我反思 - 元认知能力
    5. 自我进化 - 自主学习优化
    
    性能优化：
    1. 增量扫描 - 只扫描变化的目录
    2. 哈希缓存 - 避免重复计算
    3. 并行处理 - 使用线程池
    4. 历史限制 - 防止内存泄漏
    5. 智能调度 - 避免频繁测试
    """
    
    def __init__(self, project_root: str, config: Optional[Dict[str, Any]] = None):
        self.project_root = os.path.abspath(project_root)
        self.config = config or self._default_config()
        
        # 状态
        self.state = SystemState.IDLE
        self.state_lock = threading.Lock()
        
        # 系统状态变量
        self._system_state = {
            'health': 'good',
            'cognitive_load': 0.5,
            'learning_rate': 0.1,
            'last_reflection': 0
        }
        
        # 核心组件
        self.mirror_launcher = None  # 延迟初始化
        self.component_scanner = None
        self.problem_detector = None
        self.hotfix_engine = None
        self.auto_tester = None
        self.root_cause_tracer = None
        self.deployment_manager = None
        self.backup_manager = None
        
        # 自我意识组件
        self.self_reflection = None
        self.goal_manager = None
        self.autonomy_controller = None
        
        # 延迟初始化标志
        self._components_initialized = False
        
        # 监控
        self.file_hashes: Dict[str, str] = {}
        self.file_mtimes: Dict[str, float] = {}  # 修改时间缓存
        self.change_queue = queue.Queue()
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # 历史记录（限制大小）
        self.max_history = 100
        self.fix_history: List[Dict[str, Any]] = []
        self.test_history: List[Dict[str, Any]] = []
        
        # 智能调度
        self.last_test_time: float = 0
        self.test_cooldown: float = 10  # 测试冷却时间（秒）
        self.pending_changes: List[Dict[str, Any]] = []
        self.change_batch_delay: float = 2  # 批量处理延迟（秒）
        self.last_reflection_time: float = 0
        self.reflection_interval: float = 3600  # 反思间隔（秒）
        
        # 缓存
        self._hash_cache: Dict[str, Tuple[float, str]] = {}  # {path: (mtime, hash)}
        
        # 回调
        self.on_state_change: Optional[Callable] = None
        self.on_problem_detected: Optional[Callable] = None
        self.on_fix_applied: Optional[Callable] = None
        self.on_reflection: Optional[Callable] = None
        
    def _init_components(self):
        """延迟初始化组件（提高启动速度）"""
        if self._components_initialized:
            return
            
        from .mirror_launcher import MirrorLauncher, LaunchConfig
        from .component_scanner import ComponentScanner
        from .problem_detector import ProblemDetector
        from .hotfix_engine import HotFixEngine
        from .auto_tester import AutoTester
        from .root_cause_tracer import RootCauseTracer
        from .deployment_manager import DeploymentManager
        from .backup_manager import BackupManager
        from .self_reflection import SelfReflection
        from .goal_manager import GoalManager
        from .autonomy_controller import AutonomyController
        
        self.mirror_launcher = MirrorLauncher(
            LaunchConfig(mirror_dir=os.path.join(self.project_root, '.mirrors'))
        )
        self.component_scanner = ComponentScanner()
        self.problem_detector = ProblemDetector()
        self.hotfix_engine = HotFixEngine()
        self.auto_tester = AutoTester()
        self.root_cause_tracer = RootCauseTracer()
        self.deployment_manager = DeploymentManager(self.project_root)
        self.backup_manager = BackupManager(self.project_root)
        
        # 自我意识组件
        self.self_reflection = SelfReflection()
        self.goal_manager = GoalManager()
        self.autonomy_controller = AutonomyController()
        
        self._components_initialized = True
        
    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            'auto_fix': True,               # 自动修复
            'auto_deploy': True,             # 自动部署
            'backup_enabled': True,          # 启用备份
            'max_backups': 10,              # 最大备份数
            'test_timeout': 300,            # 测试超时（秒）
            'monitor_interval': 5,           # 监控间隔（秒）
            'exclude_patterns': [            # 排除模式
                '__pycache__',
                '*.pyc',
                '.git',
                'node_modules',
                '.mirrors',
                '.workbuddy',
                '*.log',
            ],
            'zero_interference': True,       # 零干扰模式
            'max_history': 100,             # 最大历史记录数
            'test_cooldown': 10,            # 测试冷却时间（秒）
            'change_batch_delay': 2,         # 批量处理延迟（秒）
            'parallel_workers': 2,           # 并行工作线程数
        }
        
    def start(self):
        """启动自我意识系统（非阻塞）"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
            
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,  # 守护线程，主程序退出时自动结束
            name="SelfAwarenessMonitor"
        )
        self.monitor_thread.start()
        
        self._set_state(SystemState.MONITORING)
        
    def stop(self):
        """停止监控系统"""
        self.stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        self._set_state(SystemState.IDLE)
        
    def _monitor_loop(self):
        """监控循环（后台线程）"""
        # 初始扫描
        self._scan_all_files_incremental()
        
        last_batch_time = 0
        
        while not self.stop_event.is_set():
            try:
                # 检测变化
                changes = self._detect_changes_incremental()
                
                if changes:
                    self.pending_changes.extend(changes)
                    
                # 批量处理（延迟一批，避免频繁测试）
                current_time = time.time()
                if self.pending_changes and (current_time - last_batch_time) >= self.config['change_batch_delay']:
                    batch = self.pending_changes[:]
                    self.pending_changes.clear()
                    last_batch_time = current_time
                    
                    # 智能调度：检查冷却时间
                    if (current_time - self.last_test_time) >= self.config['test_cooldown']:
                        self._process_changes(batch)
                        self.last_test_time = current_time
                    else:
                        # 延迟到冷却后处理
                        self.change_queue.put(batch)
                
                # 定期自我反思
                if (current_time - self.last_reflection_time) >= self.reflection_interval:
                    self._perform_reflection()
                    self.last_reflection_time = current_time
                
                # 更新认知负载
                self._update_cognitive_load()
                
                # 等待下次检查
                time.sleep(self.config['monitor_interval'])
                
            except Exception as e:
                self._log_error(f"监控循环错误: {e}")
    
    def _perform_reflection(self):
        """执行自我反思"""
        if not self._components_initialized:
            self._init_components()
        
        goals = self.goal_manager.get_active_goals()
        reflection = self.self_reflection.reflect(self._system_state, goals)
        
        # 更新系统状态
        self._system_state['last_reflection'] = time.time()
        
        # 应用改进建议
        for suggestion in reflection.improvement_suggestions:
            self._apply_improvement_suggestion(suggestion)
        
        # 发布反思完成事件
        self._publish_reflection_event(reflection)
        
        if self.on_reflection:
            self.on_reflection(reflection)
        
        self._log_info(f"自我反思完成，建议数: {len(reflection.improvement_suggestions)}")
    
    def _publish_reflection_event(self, reflection):
        """发布反思事件"""
        try:
            from client.src.business.integration_layer import EventType, publish
            
            event_data = {
                'suggestions': reflection.improvement_suggestions,
                'state_check': reflection.state_check,
                'goal_assessment': reflection.goal_assessment
            }
            
            publish(EventType.REFLECTION_COMPLETED, 'self_awareness', event_data)
        except ImportError:
            pass
    
    def _apply_improvement_suggestion(self, suggestion: str):
        """应用改进建议"""
        if "降低并发任务数量" in suggestion:
            # 可以在这里实现实际的优化逻辑
            self._log_info(f"应用改进: {suggestion}")
    
    def _update_cognitive_load(self):
        """更新认知负载"""
        pending_count = len(self.pending_changes)
        fix_count = len(self.fix_history)
        
        # 简单的认知负载计算
        load = min(1.0, 0.3 + pending_count * 0.1 + fix_count * 0.05)
        self._system_state['cognitive_load'] = load
                
    def _scan_all_files_incremental(self):
        """增量扫描所有文件（只扫描新增/修改的文件）"""
        new_hashes = {}
        
        for root, dirs, files in os.walk(self.project_root):
            # 过滤目录
            dirs[:] = [d for d in dirs 
                       if not self._should_exclude(d)]
            
            for file in files:
                if not self._should_exclude(file):
                    file_path = os.path.join(root, file)
                    
                    # 增量检查：如果文件未变化，使用缓存的哈希
                    if file_path in self.file_hashes:
                        try:
                            mtime = os.path.getmtime(file_path)
                            if file_path in self.file_mtimes and self.file_mtimes[file_path] == mtime:
                                # 文件未修改，使用缓存
                                new_hashes[file_path] = self.file_hashes[file_path]
                                continue
                        except OSError:
                            pass
                            
                    # 文件新增或修改，计算哈希
                    file_hash = self._file_hash_cached(file_path)
                    new_hashes[file_path] = file_hash
                    
        self.file_hashes = new_hashes
        
    def _detect_changes_incremental(self) -> List[Dict[str, Any]]:
        """增量检测文件变化（只检查可能变化的文件）"""
        changes = []
        current_hashes = {}
        
        # 只检查已知文件和新文件
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs 
                       if not self._should_exclude(d)]
            
            for file in files:
                if not self._should_exclude(file):
                    file_path = os.path.join(root, file)
                    current_hash = self._file_hash_cached(file_path)
                    current_hashes[file_path] = current_hash
                    
                    # 检查是否变化
                    if file_path in self.file_hashes:
                        if self.file_hashes[file_path] != current_hash:
                            changes.append({
                                'type': 'modified',
                                'path': file_path,
                                'hash': current_hash,
                            })
                    else:
                        # 新文件
                        changes.append({
                            'type': 'added',
                            'path': file_path,
                            'hash': current_hash,
                        })
        
        # 检查删除的文件
        for file_path in list(self.file_hashes.keys()):
            if file_path not in current_hashes:
                changes.append({
                    'type': 'deleted',
                    'path': file_path,
                })
                
        # 更新哈希
        self.file_hashes = current_hashes
        
        return changes
        
    def _process_changes(self, changes: List[Dict[str, Any]]):
        """处理文件变化（优化版）"""
        # 只处理Python文件的变化
        py_changes = [c for c in changes 
                      if c['path'].endswith('.py')]
        
        if not py_changes:
            return
            
        self._log_info(f"检测到 {len(py_changes)} 个Python文件变化，开始验证...")
        
        # 在镜像中测试
        self._set_state(SystemState.TESTING)
        
        try:
            # 使用线程池并行处理
            future = self.executor.submit(self._test_in_mirror, py_changes)
            test_result = future.result(timeout=self.config['test_timeout'])
            
            if test_result.get('failed', 0) > 0 or not test_result.get('success', True):
                # 检测到问题，诊断
                self._set_state(SystemState.DIAGNOSING)
                
                problems = self._diagnose_problems(test_result)
                
                if problems and self.config['auto_fix']:
                    # 自动修复
                    self._set_state(SystemState.FIXING)
                    
                    fix_result = self._auto_fix(problems)
                    
                    if fix_result and fix_result.success and self.config['auto_deploy']:
                        # 自动部署
                        self._set_state(SystemState.DEPLOYING)
                        
                        deploy_result = self._deploy_fix(fix_result)
                        
                        if deploy_result.get('success'):
                            self._log_info("自动修复部署成功！")
                        else:
                            self._log_error(f"部署失败: {deploy_result.get('error')}")
                            self._rollback(fix_result)
        
        except Exception as e:
            self._log_error(f"处理变化失败: {e}")
            self._set_state(SystemState.ERROR)
            return
            
        self._set_state(SystemState.MONITORING)
        
    def _test_in_mirror(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """在镜像中测试变化"""
        # 延迟初始化组件
        self._init_components()
        
        # 启动镜像
        mirror = self.mirror_launcher.launch(self.project_root, {
            'trigger': 'file_change',
            'changes': changes,
        })
        
        try:
            # 使用AutoTester运行测试
            test_result = self.auto_tester.run_tests(
                mirror_path=mirror.mirror_path,
                test_paths=['tests/']
            )
            
            # 限制历史记录大小
            self.test_history.append({
                'timestamp': time.time(),
                'mirror_id': mirror.instance_id,
                'result': test_result,
            })
            if len(self.test_history) > self.max_history:
                self.test_history = self.test_history[-self.max_history:]
            
            return test_result
            
        finally:
            # 停止镜像
            self.mirror_launcher.stop(mirror.instance_id)
            
    def _diagnose_problems(self, test_result: Dict[str, Any]) -> List[Any]:
        """诊断问题"""
        # 延迟初始化组件
        self._init_components()
        
        problems = []
        
        if test_result.get('failed', 0) > 0 or not test_result.get('success', True):
            # 测试失败，分析错误
            output = test_result.get('output', '')
            error = test_result.get('error')
            
            # 使用问题检测器分析
            if error or 'FAILED' in output or 'ERROR' in output:
                problem = self.problem_detector.detect_from_exception(
                    Exception(error or output),
                    context={'test_result': test_result}
                )
                
                # 使用根因追踪器深入分析
                if problem:
                    try:
                        root_cause = self.root_cause_tracer.trace(
                            Exception(error or output)
                        )
                        problem.metadata['root_cause'] = {
                            'type': root_cause.cause_type,
                            'description': root_cause.description,
                            'suggestion': root_cause.suggested_fix,
                        }
                    except:
                        pass
                        
                problems.append(problem)
            
        return problems
        
    def _auto_fix(self, problems: List[Any]) -> Optional[Any]:
        """自动修复"""
        # 延迟初始化组件
        self._init_components()
        
        for problem in problems:
            # 确定问题类型
            problem_type = problem.category.value if hasattr(problem.category, 'value') else str(problem.category)
            
            # 获取相关代码
            if problem.location and 'file' in problem.location:
                file_path = problem.location['file']
                
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    # 修复
                    fix_result = self.hotfix_engine.fix(
                        code,
                        problem_type,
                        strategy=FixStrategy.AUTO
                    )
                    
                    if fix_result.success:
                        # 应用修复
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(fix_result.fixed_code)
                            
                        self.fix_history.append({
                            'timestamp': time.time(),
                            'problem': problem.title,
                            'file': file_path,
                            'result': fix_result,
                        })
                        
                        # 限制历史记录大小
                        if len(self.fix_history) > self.max_history:
                            self.fix_history = self.fix_history[-self.max_history:]
                        
                        if self.on_fix_applied:
                            self.on_fix_applied(problem, fix_result)
                            
                        return fix_result
        
        return None
        
    def _deploy_fix(self, fix_result: Any) -> Dict[str, Any]:
        """部署修复"""
        # 延迟初始化组件
        self._init_components()
        
        try:
            # 验证修复
            validation = self.hotfix_engine._validate(fix_result.fixed_code)
            
            if not validation:
                return {'success': False, 'error': '修复验证失败'}
            
            # 使用DeploymentManager部署
            problem_info = {
                'title': 'Auto Fix',
                'category': 'auto',
            }
            
            deployment = self.deployment_manager.deploy(
                problem_info,
                fix_result
            )
            
            return {
                'success': deployment.status.value == 'success',
                'deployment_id': deployment.deployment_id,
                'status': deployment.status.value,
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _rollback(self, fix_result: Any):
        """回滚修复"""
        self._set_state(SystemState.ROLLING_BACK)
        
        # 简化实现：记录回滚事件
        self._log_info("执行回滚...")
        
        self._set_state(SystemState.MONITORING)
        
    def _file_hash_cached(self, file_path: str) -> str:
        """计算文件哈希（带缓存）"""
        try:
            mtime = os.path.getmtime(file_path)
            
            # 检查缓存
            if file_path in self._hash_cache:
                cached_mtime, cached_hash = self._hash_cache[file_path]
                if cached_mtime == mtime:
                    return cached_hash
            
            # 计算哈希
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            # 更新缓存
            self._hash_cache[file_path] = (mtime, file_hash)
            self.file_mtimes[file_path] = mtime
            
            return file_hash
            
        except OSError:
            return ''
            
    def _should_exclude(self, name: str) -> bool:
        """检查是否应该排除（优化：编译正则表达式）"""
        if not hasattr(self, '_exclude_regex'):
            # 编译正则表达式
            patterns = []
            for pattern in self.config['exclude_patterns']:
                if pattern.startswith('*'):
                    patterns.append(re.compile(fnmatch.translate(pattern)))
                else:
                    patterns.append(pattern)
            self._exclude_patterns = patterns
            
        for pattern in self._exclude_patterns:
            if isinstance(pattern, re.Pattern):
                if pattern.match(name):
                    return True
            else:
                if pattern in name:
                    return True
        return False
        
    def _set_state(self, new_state: SystemState):
        """设置状态"""
        with self.state_lock:
            old_state = self.state
            self.state = new_state
            
            if self.on_state_change:
                self.on_state_change(old_state, new_state)
                
    def _log_info(self, message: str):
        """记录信息日志"""
        print(f"[SelfAwareness] {message}")
        
    def _log_error(self, message: str):
        """记录错误日志"""
        print(f"[SelfAwareness ERROR] {message}")
        
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        with self.state_lock:
            status = {
                'state': self.state.value,
                'monitoring': self.monitor_thread is not None 
                           and self.monitor_thread.is_alive(),
                'fix_count': len(self.fix_history),
                'test_count': len(self.test_history),
                'last_fix': self.fix_history[-1] if self.fix_history else None,
                'pending_changes': len(self.pending_changes),
                'cache_size': len(self._hash_cache),
                
                # 自我意识状态
                'system_state': self._system_state,
                'autonomy': self._get_autonomy_status(),
                'goals': self._get_goal_status(),
            }
            return status
    
    def _get_autonomy_status(self) -> Dict:
        """获取自主控制状态"""
        if not self._components_initialized:
            return {'level': 3}
        
        return self.autonomy_controller.get_status()
    
    def _get_goal_status(self) -> Dict:
        """获取目标状态"""
        if not self._components_initialized:
            return {'count': 0}
        
        return self.goal_manager.get_stats()
    
    def set_goal(self, description: str, priority: float = 0.5) -> str:
        """设置目标"""
        if not self._components_initialized:
            self._init_components()
        
        return self.goal_manager.set_goal(description, priority)
    
    def update_goal_progress(self, goal_id: str, progress: float):
        """更新目标进度"""
        if self._components_initialized:
            self.goal_manager.update_goal_progress(goal_id, progress)
    
    def set_autonomy_level(self, level: int):
        """设置自主级别"""
        if not self._components_initialized:
            self._init_components()
        
        from .autonomy_controller import AutonomyLevel
        
        level_enum = AutonomyLevel(level)
        self.autonomy_controller.set_autonomy_level(level_enum)
    
    def reflect(self) -> Dict:
        """执行自我反思"""
        if not self._components_initialized:
            self._init_components()
        
        goals = self.goal_manager.get_active_goals()
        reflection = self.self_reflection.reflect(self._system_state, goals)
        
        return {
            'state_check': reflection.state_check,
            'goal_assessment': reflection.goal_assessment,
            'improvement_suggestions': reflection.improvement_suggestions
        }
    
    def get_reflection_history(self, limit: int = 10) -> List[Dict]:
        """获取反思历史"""
        if not self._components_initialized:
            self._init_components()
        
        history = self.self_reflection.get_reflection_history(limit)
        return [
            {
                'timestamp': h.timestamp,
                'suggestions': h.improvement_suggestions,
                'goals_assessed': len(h.goal_assessment)
            }
            for h in history
        ]
    
    def get_all_goals(self) -> List[Dict]:
        """获取所有目标"""
        if not self._components_initialized:
            self._init_components()
        
        return self.goal_manager.get_all_goals()
