# evolution_engine.py - Evolution Engine 主控制器

"""
Evolution Engine - 智能IDE自我进化系统

核心理念：从"执行工具"进化为"设计伙伴"
构建"感知-诊断-规划-执行"闭环自治系统

功能：
1. 多维度感知 - 实时捕获性能、质量、生态情报
2. 智能提案 - 将数据信号转化为结构化进化方案
3. 安全自治 - 在围栏内实现自动执行与回滚
4. 持续学习 - 通过进化日志实现自我优化
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import threading
import time
import logging
from datetime import datetime

from .proposal.structured_proposal import StructuredProposal, ProposalStatus
from .proposal.proposal_generator import ProposalGenerator
from .safety.safety_fence import SafetyFence

# Phase 3: 执行引擎
from .executor.git_sandbox import GitSandbox
from .executor.atomic_executor import AtomicExecutor
from .executor.rollback_manager import RollbackManager, RollbackType
from .executor.step_executor import StepExecutor, StepStatus

# Phase 4: 进化记忆
from .memory.evolution_log import get_evolution_log, EvolutionLog
from .memory.learning_engine import get_learning_engine, LearningEngine
from .memory.pattern_miner import get_pattern_miner, PatternMiner
from .memory.decision_tracker import (
    get_decision_tracker, DecisionTracker,
    DecisionType, DecisionContext, DecisionFactor
)

logger = logging.getLogger('evolution.engine')


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
        
        # 状态
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 传感器
        self._sensors: Dict[str, Any] = {}
        
        # 聚合器
        self._aggregator = None
        
        # 提案生成器（Phase 2）
        self._proposal_generator = ProposalGenerator(str(self.project_root))
        
        # 安全围栏（Phase 2）
        self._safety_fence = SafetyFence(str(self.project_root))
        
        # Phase 3: 执行引擎
        self._git_sandbox = GitSandbox(str(self.project_root))
        self._atomic_executor = AtomicExecutor(str(self.project_root))
        self._rollback_manager = RollbackManager(str(self.project_root))
        self._step_executor = StepExecutor(str(self.project_root))
        
        # Phase 4: 进化记忆层
        self._evolution_log = get_evolution_log()
        self._learning_engine = get_learning_engine(self._evolution_log)
        self._pattern_miner = get_pattern_miner(self._evolution_log)
        self._decision_tracker = get_decision_tracker(self._evolution_log)
        
        # 提案队列（使用 StructuredProposal）
        self._proposal_queue: List[StructuredProposal] = []
        
        # 执行中的提案
        self._executing_proposals: Dict[str, Dict[str, Any]] = {}
        
        # 统计
        self._stats = {
            'total_signals': 0,
            'total_proposals': 0,
            'proposals_approved': 0,
            'proposals_rejected': 0,
            'proposals_executed': 0,
            'proposals_failed': 0,
            'started_at': None,
            'last_scan_at': None,
        }
        
        logger.info(f"[EvolutionEngine] 初始化完成，项目目录: {self.project_root}")
    
    def start(self):
        """启动 Evolution Engine"""
        if self._running:
            logger.warning("[EvolutionEngine] 已在运行中")
            return
        
        self._running = True
        self._stats['started_at'] = datetime.now()
        
        # 初始化传感器
        self._init_sensors()
        
        # 初始化聚合器
        self._init_aggregator()
        
        # 启动后台循环
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info("[EvolutionEngine] 启动成功")
    
    def stop(self):
        """停止 Evolution Engine"""
        if not self._running:
            return
        
        self._running = False
        
        # 停止所有传感器
        for sensor in self._sensors.values():
            if hasattr(sensor, 'stop'):
                sensor.stop()
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("[EvolutionEngine] 已停止")
    
    def _init_sensors(self):
        """初始化传感器"""
        from .sensors.performance_sensor import PerformanceSensor
        from .sensors.architecture_smell_sensor import ArchitectureSmellSensor
        
        sensor_config = self.config.get('sensors', {})
        
        # 性能传感器
        perf_config = sensor_config.get('performance', {})
        self._sensors['performance'] = PerformanceSensor(perf_config)
        self._sensors['performance'].on_signal = self._on_sensor_signal
        
        # 架构异味传感器
        arch_config = sensor_config.get('architecture', {})
        self._sensors['architecture'] = ArchitectureSmellSensor(
            str(self.project_root),
            arch_config
        )
        self._sensors['architecture'].on_signal = self._on_sensor_signal
        
        # 启动传感器
        for sensor in self._sensors.values():
            sensor.start()
        
        logger.info(f"[EvolutionEngine] 已初始化 {len(self._sensors)} 个传感器")
    
    def _init_aggregator(self):
        """初始化信号聚合器"""
        from .aggregator.signal_aggregator import SignalAggregator
        
        aggregator_config = self.config.get('aggregator', {})
        self._aggregator = SignalAggregator(aggregator_config)
    
    def _run_loop(self):
        """主循环"""
        scan_interval = self.config.get('scan_interval', 3600)  # 默认1小时
        
        while self._running:
            try:
                # 1. 执行传感器扫描
                self._collect_signals()
                
                # 2. 聚合信号
                aggregated = self._aggregator.aggregate()
                
                # 3. 生成提案（简化版：直接输出信号）
                if aggregated:
                    self._generate_proposals(aggregated)
                
                # 4. 更新统计
                self._stats['last_scan_at'] = datetime.now()
                
                # 休眠
                logger.info(f"[EvolutionEngine] 扫描完成，等待 {scan_interval} 秒...")
                time.sleep(scan_interval)
                
            except Exception as e:
                logger.error(f"[EvolutionEngine] 循环异常: {e}")
                time.sleep(60)  # 出错后1分钟重试
    
    def _collect_signals(self):
        """收集信号"""
        for sensor_name, sensor in self._sensors.items():
            try:
                if hasattr(sensor, 'scan'):
                    signals = sensor.scan()
                    for signal in signals:
                        self._aggregator.add_signal(signal)
                    logger.debug(f"[EvolutionEngine] {sensor_name} 扫描到 {len(signals)} 个信号")
            except Exception as e:
                logger.error(f"[EvolutionEngine] {sensor_name} 扫描异常: {e}")
    
    def _on_sensor_signal(self, signal):
        """处理传感器信号"""
        self._aggregator.add_signal(signal)
        self._stats['total_signals'] += 1
        logger.debug(
            f"[EvolutionEngine] 信号接收: {signal.signal_type} "
            f"({signal.sensor_type.value})"
        )
    
    def _generate_proposals(self, aggregated_signals: List[Dict[str, Any]]):
        """
        生成进化提案
        
        使用 ProposalGenerator 从聚合信号生成结构化提案
        """
        # 使用提案生成器生成提案
        proposals = self._proposal_generator.generate_proposals(aggregated_signals)
        
        for proposal in proposals:
            # 安全检查
            if not self._safety_fence.validate_proposal(proposal):
                violations_report = self._safety_fence.get_violations_report()
                logger.warning(
                    f"[EvolutionEngine] 提案 {proposal.proposal_id} 未通过安全检查:\n"
                    f"{violations_report}"
                )
                continue
            
            self._proposal_queue.append(proposal)
            self._stats['total_proposals'] += 1
            logger.info(
                f"[EvolutionEngine] 提案生成: {proposal.proposal_id} - {proposal.title} "
                f"[{proposal.priority.value}]"
            )
    
    def scan_once(self) -> Dict[str, Any]:
        """
        执行一次完整扫描（同步）
        
        Returns:
            扫描结果
        """
        # 收集信号
        self._collect_signals()
        
        # 聚合
        aggregated = self._aggregator.aggregate()
        
        # 生成提案
        self._generate_proposals(aggregated)
        
        return {
            'signals_collected': self._stats['total_signals'],
            'aggregated_groups': len(aggregated),
            'proposals_generated': len(self._proposal_queue),
            'pending_proposals': len([p for p in self._proposal_queue 
                                     if p.status == ProposalStatus.PENDING]),
            'timestamp': datetime.now().isoformat(),
        }
    
    def get_proposals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取提案列表
        
        Args:
            status: 可选的状态过滤（pending, approved, rejected）
        
        Returns:
            提案列表
        """
        if status:
            try:
                status_enum = ProposalStatus(status)
                return [p.to_dict() for p in self._proposal_queue if p.status == status_enum]
            except ValueError:
                pass
        return [p.to_dict() for p in self._proposal_queue]
    
    def get_proposal_detail(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        获取提案详情
        
        Args:
            proposal_id: 提案ID
        
        Returns:
            提案详情或 None
        """
        for proposal in self._proposal_queue:
            if proposal.proposal_id == proposal_id:
                return proposal.to_dict()
        return None
    
    def approve_proposal(self, proposal_id: str, decision_maker: str = "user") -> bool:
        """
        批准提案
        
        Args:
            proposal_id: 提案ID
            decision_maker: 决策者 (user/system/auto)
        
        Returns:
            是否成功
        """
        for proposal in self._proposal_queue:
            if proposal.proposal_id == proposal_id:
                # 最终安全检查
                if not self._safety_fence.validate_proposal(proposal):
                    logger.warning(
                        f"[EvolutionEngine] 提案 {proposal_id} 安全检查未通过"
                    )
                    return False
                
                proposal.status = ProposalStatus.APPROVED
                proposal.approved_by = decision_maker
                proposal.updated_at = datetime.now()
                self._stats['proposals_approved'] += 1
                
                # Phase 4: 记录决策
                self._record_decision(
                    DecisionType.APPROVE,
                    proposal,
                    decision_maker
                )
                
                logger.info(f"[EvolutionEngine] 提案已批准: {proposal_id}")
                return True
        return False
    
    def reject_proposal(self, proposal_id: str) -> bool:
        """
        拒绝提案
        
        Args:
            proposal_id: 提案ID
        
        Returns:
            是否成功
        """
        for proposal in self._proposal_queue:
            if proposal.proposal_id == proposal_id:
                proposal.status = ProposalStatus.REJECTED
                proposal.updated_at = datetime.now()
                self._proposal_queue.remove(proposal)
                self._stats['proposals_rejected'] += 1
                
                logger.info(f"[EvolutionEngine] 提案已拒绝: {proposal_id}")
                return True
        return False
    
    def validate_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """
        验证提案安全性
        
        Args:
            proposal_id: 提案ID
        
        Returns:
            验证结果
        """
        for proposal in self._proposal_queue:
            if proposal.proposal_id == proposal_id:
                is_safe = self._safety_fence.validate_proposal(proposal)
                violations_report = self._safety_fence.get_violations_report()
                
                return {
                    'proposal_id': proposal_id,
                    'is_safe': is_safe,
                    'violations_report': violations_report,
                }
        
        return {
            'proposal_id': proposal_id,
            'is_safe': False,
            'violations_report': '提案不存在',
        }
    
    def get_safety_violations(self) -> str:
        """
        获取当前安全违规报告
        
        Returns:
            违规报告字符串
        """
        return self._safety_fence.get_violations_report()
    
    # ── Phase 4: 进化记忆 ──
    
    def _record_decision(
        self,
        decision_type: DecisionType,
        proposal: StructuredProposal,
        decision_maker: str
    ):
        """记录决策到追踪器"""
        try:
            # 创建决策链
            chain_id = self._decision_tracker.create_chain(proposal.proposal_id)
            
            # 构建决策上下文
            context = DecisionContext(
                signals=[s.to_dict() for s in proposal.trigger_signals],
                proposals=[proposal.to_dict()],
                proposals_considered=1,
                risk_tolerance=proposal.risk_level.value
            )
            
            # 构建决策因素
            factors = [
                DecisionFactor(
                    factor_type='priority',
                    value={'low': 0.25, 'medium': 0.5, 'high': 0.75, 'critical': 1.0}.get(
                        proposal.priority.value, 0.5
                    ),
                    weight=0.3,
                    description=f'优先级: {proposal.priority.value}'
                ),
                DecisionFactor(
                    factor_type='risk',
                    value={'low': 0.25, 'medium': 0.5, 'high': 0.75, 'critical': 1.0}.get(
                        proposal.risk_level.value, 0.5
                    ),
                    weight=0.3,
                    description=f'风险等级: {proposal.risk_level.value}'
                ),
                DecisionFactor(
                    factor_type='signal_strength',
                    value=len(proposal.trigger_signals) / 10,
                    weight=0.2,
                    description=f'触发信号数: {len(proposal.trigger_signals)}'
                ),
                DecisionFactor(
                    factor_type='steps_count',
                    value=len(proposal.steps) / 20,
                    weight=0.2,
                    description=f'执行步骤数: {len(proposal.steps)}'
                )
            ]
            
            # 记录决策
            self._decision_tracker.record_decision(
                chain_id=chain_id,
                decision_type=decision_type,
                context=context,
                factors=factors,
                reasoning=f"批准提案: {proposal.title}",
                decision_maker=decision_maker
            )
            
            # 添加事件到模式挖掘器
            self._pattern_miner.add_event({
                'type': 'decision',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'decision_type': decision_type.value,
                    'proposal_id': proposal.proposal_id,
                    'priority': proposal.priority.value
                }
            })
            
        except Exception as e:
            logger.error(f"[EvolutionEngine] 记录决策失败: {e}")
    
    def get_learning_insights(self) -> List[Dict[str, Any]]:
        """获取学习洞察"""
        try:
            return self._learning_engine.get_insights()
        except Exception as e:
            logger.error(f"[EvolutionEngine] 获取学习洞察失败: {e}")
            return []
    
    def get_patterns_summary(self) -> Dict[str, Any]:
        """获取模式挖掘摘要"""
        try:
            return self._pattern_miner.get_patterns_summary()
        except Exception as e:
            logger.error(f"[EvolutionEngine] 获取模式摘要失败: {e}")
            return {}
    
    def get_micro_patterns(self) -> Dict[str, Any]:
        """获取微模式"""
        return self._pattern_miner.mine_patterns()
    
    def get_decision_audit(self, proposal_id: str) -> Dict[str, Any]:
        """获取决策审计追踪"""
        chain = self._decision_tracker.get_chain_by_proposal(proposal_id)
        if not chain:
            return {'error': 'Chain not found'}
        return {
            'chain': chain.to_dict(),
            'audit_trail': self._decision_tracker.get_audit_trail(chain.chain_id)
        }
    
    def analyze_root_cause(self, proposal_id: str) -> Dict[str, Any]:
        """分析根因"""
        return self._decision_tracker.analyze_root_cause(proposal_id)
    
    def get_evolution_summary(self) -> Dict[str, Any]:
        """获取进化摘要（包含所有记忆层信息）"""
        return {
            'log_summary': self._evolution_log.get_summary(),
            'learning_stats': self._learning_engine.get_statistics(),
            'patterns_summary': self._pattern_miner.get_patterns_summary(),
            'decision_stats': self._decision_tracker.get_statistics()
        }
    
    def _learn_from_execution(
        self,
        proposal: StructuredProposal,
        step_results: List[Dict],
        success: bool
    ):
        """从执行结果中学习"""
        try:
            # 提取信号信息
            signals = [s.to_dict() for s in proposal.trigger_signals]
            
            # 计算执行结果
            execution_result = {
                'proposal_id': proposal.proposal_id,
                'status': 'success' if success else 'failed',
                'steps_completed': sum(1 for r in step_results if r.get('status') == 'completed'),
                'steps_total': len(step_results),
                'duration_ms': 0  # 简化
            }
            
            # 记录到学习引擎
            self._learning_engine.learn_from_execution(
                proposal_type=proposal.proposal_type.value,
                proposal_id=proposal.proposal_id,
                signals=signals,
                execution_result=execution_result
            )
            
            # 添加事件到模式挖掘器
            self._pattern_miner.add_event({
                'type': 'execution',
                'timestamp': datetime.now().isoformat(),
                'data': execution_result
            })
            
        except Exception as e:
            logger.error(f"[EvolutionEngine] 学习记录失败: {e}")
    
    def _log_execution_result(
        self,
        proposal: StructuredProposal,
        step_results: List[Dict],
        success: bool
    ):
        """记录执行结果到日志"""
        try:
            # 记录执行
            self._evolution_log.log_execution({
                'proposal_id': proposal.proposal_id,
                'status': 'success' if success else 'failed',
                'steps_completed': sum(1 for r in step_results if r.get('status') == 'completed'),
                'steps_total': len(step_results),
                'duration_ms': 0
            })
            
            # 更新提案状态
            self._evolution_log.update_proposal_status(
                proposal.proposal_id,
                'completed' if success else 'failed',
                actual_impact=proposal.estimated_impact
            )
            
            # 记录决策结果
            chain = self._decision_tracker.get_chain_by_proposal(proposal.proposal_id)
            if chain:
                from .memory.decision_tracker import DecisionOutcome
                self._decision_tracker.resolve_outcome(
                    chain.chain_id,
                    DecisionOutcome.SUCCESS if success else DecisionOutcome.FAILURE,
                    reason=f"执行{'成功' if success else '失败'}"
                )
            
        except Exception as e:
            logger.error(f"[EvolutionEngine] 日志记录失败: {e}")
    
    # ── Phase 3: 执行提案 ──
    
    def execute_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """
        执行提案
        
        Args:
            proposal_id: 提案ID
            
        Returns:
            执行结果
        """
        # 查找提案
        proposal = None
        for p in self._proposal_queue:
            if p.proposal_id == proposal_id:
                proposal = p
                break
        
        if not proposal:
            return {
                'success': False,
                'error': '提案不存在'
            }
        
        # 检查提案状态
        if proposal.status != ProposalStatus.APPROVED:
            return {
                'success': False,
                'error': f'提案状态不是已批准: {proposal.status.value}'
            }
        
        # 再次安全检查
        if not self._safety_fence.validate_proposal(proposal):
            return {
                'success': False,
                'error': '安全检查未通过',
                'violations': self._safety_fence.get_violations_report()
            }
        
        # 创建快照
        snapshot = self._git_sandbox.create_snapshot(
            f"执行提案: {proposal.title}"
        )
        
        # 创建回滚点
        changed_files = [s.location for s in proposal.signals if s.location]
        rollback_point = self._rollback_manager.create_rollback_point(
            proposal_id=proposal_id,
            snapshot_id=snapshot.snapshot_id,
            description=proposal.title,
            changed_files=changed_files
        )
        
        # 记录执行状态
        execution_state = {
            'proposal_id': proposal_id,
            'snapshot_id': snapshot.snapshot_id,
            'rollback_point_id': rollback_point.point_id,
            'started_at': datetime.now().isoformat(),
            'steps_completed': 0,
            'steps_total': len(proposal.steps),
            'status': 'running',
        }
        self._executing_proposals[proposal_id] = execution_state
        
        # 更新提案状态
        proposal.status = ProposalStatus.EXECUTING
        proposal.executed_at = datetime.now()
        
        # 执行步骤
        step_results = []
        all_success = True
        
        for step in proposal.steps:
            # 检查是否需要用户确认
            if step.requires_confirmation:
                # 简化处理：跳过需要确认的步骤
                logger.info(f"[EvolutionEngine] 跳过需确认步骤: {step.step_id}")
                step_results.append({
                    'step_id': step.step_id,
                    'status': 'skipped',
                    'reason': '需要用户确认'
                })
                continue
            
            # 执行步骤
            step_dict = step.to_dict()
            result = self._step_executor.execute_step(step_dict)
            
            step_results.append({
                'step_id': result.step_id,
                'status': result.status.value,
                'output': result.output,
                'error': result.error,
                'files_changed': result.files_changed
            })
            
            if result.status != StepStatus.COMPLETED:
                all_success = False
                break
            
            execution_state['steps_completed'] += 1
        
        # 更新执行状态
        execution_state['completed_at'] = datetime.now().isoformat()
        execution_state['status'] = 'completed' if all_success else 'failed'
        
        # 更新统计
        if all_success:
            self._stats['proposals_executed'] += 1
            proposal.status = ProposalStatus.COMPLETED
            
            # 提交回滚点
            self._rollback_manager.commit(rollback_point.point_id)
            
            logger.info(f"[EvolutionEngine] 提案执行成功: {proposal_id}")
        else:
            self._stats['proposals_failed'] += 1
            proposal.status = ProposalStatus.FAILED
            
            # 回滚
            self._rollback_manager.rollback(
                rollback_point.point_id,
                RollbackType.FULL
            )
            
            logger.warning(f"[EvolutionEngine] 提案执行失败: {proposal_id}")
        
        # Phase 4: 记录执行结果到学习引擎
        self._learn_from_execution(proposal, step_results, all_success)
        
        # Phase 4: 记录到进化日志
        self._log_execution_result(proposal, step_results, all_success)
        
        return {
            'success': all_success,
            'proposal_id': proposal_id,
            'steps_completed': execution_state['steps_completed'],
            'steps_total': execution_state['steps_total'],
            'step_results': step_results,
            'snapshot_id': snapshot.snapshot_id,
            'rollback_point_id': rollback_point.point_id,
        }
    
    def get_execution_status(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        获取提案执行状态
        
        Args:
            proposal_id: 提案ID
            
        Returns:
            执行状态或 None
        """
        return self._executing_proposals.get(proposal_id)
    
    def rollback_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """
        回滚提案
        
        Args:
            proposal_id: 提案ID
            
        Returns:
            回滚结果
        """
        # 查找提案
        proposal = None
        for p in self._proposal_queue:
            if p.proposal_id == proposal_id:
                proposal = p
                break
        
        if not proposal:
            return {
                'success': False,
                'error': '提案不存在'
            }
        
        # 查找执行状态
        execution = self._executing_proposals.get(proposal_id)
        if not execution:
            return {
                'success': False,
                'error': '提案未执行过'
            }
        
        # 执行回滚
        rollback_point_id = execution.get('rollback_point_id')
        result = self._rollback_manager.rollback(rollback_point_id, RollbackType.FULL)
        
        # 更新提案状态
        proposal.status = ProposalStatus.PENDING
        
        return {
            'success': result.success,
            'proposal_id': proposal_id,
            'files_restored': result.files_restored,
            'files_removed': result.files_removed,
            'error': result.error
        }
    
    def get_executor_status(self) -> Dict[str, Any]:
        """获取执行引擎状态"""
        return {
            'git_sandbox': {
                'current_branch': self._git_sandbox._current_branch,
                'snapshots_count': len(self._git_sandbox.snapshots),
            },
            'rollback_manager': {
                'active_point': self._rollback_manager._active_point,
                'points_count': len(self._rollback_manager._rollback_points),
            },
            'executing_proposals': len(self._executing_proposals),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pending_count = len([p for p in self._proposal_queue 
                           if p.status == ProposalStatus.PENDING])
        approved_count = len([p for p in self._proposal_queue 
                            if p.status == ProposalStatus.APPROVED])
        
        return {
            **self._stats,
            'sensors_count': len(self._sensors),
            'pending_proposals': pending_count,
            'approved_proposals': approved_count,
            'running': self._running,
            'project_root': str(self.project_root),
            'safety_enabled': self._safety_fence.enabled,
        }
    
    def get_sensor_status(self) -> Dict[str, Any]:
        """获取传感器状态"""
        status = {}
        for name, sensor in self._sensors.items():
            last_scan = sensor.get_last_scan_time()
            status[name] = {
                'running': sensor._running if hasattr(sensor, '_running') else False,
                'last_scan': last_scan.isoformat() if last_scan else None,
                'buffered_signals': len(sensor.get_buffered_signals()),
            }
        return status

    # ── Phase 5: 自我学习能力 ──

    def enable_self_learning(self, enable: bool = True):
        """
        启用/禁用自我学习能力
        
        Args:
            enable: 是否启用
        """
        if enable:
            # 初始化自我学习模块 (使用简化版实现)
            try:
                # 1. 强化学习
                from client.src.business.self_learning.reinforcement import (
                    CodeEvolutionEnv,
                    PPOAgent,
                    RLTrainer,
                    TrainingConfig,
                )
                
                self._rl_env = CodeEvolutionEnv(project_root=str(self.project_root))
                self._rl_agent = PPOAgent(state_dim=6, action_dim=5)
                training_config = TrainingConfig()
                self._rl_trainer = RLTrainer(self._rl_env, self._rl_agent, training_config)
                
                # 2. 知识图谱
                from client.src.business.self_learning.knowledge_graph import (
                    CodeKnowledgeGraph,
                    ASTParser,
                    ImpactAnalyzer,
                )
                
                self._kg = CodeKnowledgeGraph(name="evolution")
                self._kg_parser = ASTParser(self._kg)
                self._impact_analyzer = ImpactAnalyzer(self._kg)
                
                # 3. 迁移学习
                from client.src.business.self_learning.transfer import (
                    DomainAdapter,
                    TransferTrainer,
                    CodeBERTAdapter,
                )
                
                self._domain_adapter = DomainAdapter(input_dim=64, hidden_dim=32)
                self._transfer_trainer = TransferTrainer(
                    model=self._domain_adapter,
                    source_data=None,  # 需要用户提供
                    target_data=None,  # 需要用户提供
                )
                self._codebert_adapter = CodeBERTAdapter()
                
                self._self_learning_enabled = True
                logger.info("[EvolutionEngine] 自我学习能力已启用 (简化版)")
                
            except ImportError as e:
                logger.error(f"[EvolutionEngine] 导入自我学习模块失败: {e}")
                raise
                
        else:
            self._self_learning_enabled = False
            logger.info("[EvolutionEngine] 自我学习能力已禁用")

    def train_reinforcement_learning(self, total_timesteps: Optional[int] = None):
        """
        训练强化学习模型

        Args:
            total_timesteps: 总训练步数（None 使用配置值）

        Returns:
            训练结果
        """
        if not hasattr(self, '_self_learning_enabled') or not self._self_learning_enabled:
            raise ValueError("自我学习能力未启用，请先调用 enable_self_learning()")

        if total_timesteps:
            self._rl_trainer.config.total_timesteps = total_timesteps

        # 启动训练
        logger.info(f"[EvolutionEngine] 开始训练强化学习模型，总步数: {self._rl_trainer.config.total_timesteps}")
        self._rl_trainer.train_loop()

        return {
            'status': 'completed',
            'total_timesteps': self._rl_trainer.training_info['timesteps'],
            'best_reward': self._rl_trainer.training_info['best_reward'],
        }

    def build_knowledge_graph(self, force_rebuild: bool = False):
        """
        构建知识图谱

        Args:
            force_rebuild: 是否强制重建

        Returns:
            知识图谱统计
        """
        if not hasattr(self, '_self_learning_enabled') or not self._self_learning_enabled:
            raise ValueError("自我学习能力未启用，请先调用 enable_self_learning()")

        logger.info(f"[EvolutionEngine] 开始构建知识图谱，强制重建: {force_rebuild}")
        kg = self._kg_builder.build_or_update(force_rebuild=force_rebuild)

        return {
            'status': 'completed',
            'entities_count': len(kg.entities),
            'relations_count': len(kg.relations),
        }

    def transfer_knowledge(self, source_domain_name: str, target_domain_name: str, data: Any):
        """
        迁移知识

        Args:
            source_domain_name: 源领域名称
            target_domain_name: 目标领域名称
            data: 要迁移的数据

        Returns:
            迁移结果
        """
        if not hasattr(self, '_self_learning_enabled') or not self._self_learning_enabled:
            raise ValueError("自我学习能力未启用，请先调用 enable_self_learning()")

        logger.info(f"[EvolutionEngine] 开始迁移知识: {source_domain_name} -> {target_domain_name}")
        result = self._transfer_pipeline.transfer_knowledge(
            source_domain_name, target_domain_name, data
        )

        return {
            'status': 'completed',
            'result': result,
        }

    def get_self_learning_status(self) -> Dict[str, Any]:
        """
        获取自我学习状态

        Returns:
            自我学习状态字典
        """
        if not hasattr(self, '_self_learning_enabled'):
            return {'enabled': False}

        if not self._self_learning_enabled:
            return {'enabled': False}

        status = {'enabled': True}

        # 强化学习状态
        if hasattr(self, '_rl_trainer'):
            status['reinforcement_learning'] = {
                'timesteps': self._rl_trainer.training_info['timesteps'],
                'episodes': self._rl_trainer.training_info['episodes'],
                'best_reward': self._rl_trainer.training_info['best_reward'],
            }

        # 知识图谱状态
        if hasattr(self, '_kg_builder') and self._kg_builder.kg is not None:
            status['knowledge_graph'] = {
                'entities_count': len(self._kg_builder.kg.entities),
                'relations_count': len(self._kg_builder.kg.relations),
            }

        # 迁移学习状态
        if hasattr(self, '_transfer_pipeline'):
            status['transfer_learning'] = {
                'adapters_count': len(self._transfer_pipeline.adapters),
            }

        return status


# 便捷函数
def create_evolution_engine(
    project_root: str,
    enable_performance: bool = True,
    enable_architecture: bool = True,
    scan_interval: int = 3600
) -> EvolutionEngine:
    """
    创建 Evolution Engine 的便捷函数
    
    Args:
        project_root: 项目根目录
        enable_performance: 启用性能传感器
        enable_architecture: 启用架构传感器
        scan_interval: 扫描间隔（秒）
    
    Returns:
        EvolutionEngine 实例
    """
    config = {
        'scan_interval': scan_interval,
        'sensors': {},
    }
    
    if not enable_performance:
        config['sensors']['performance'] = {'enabled': False}
    
    if not enable_architecture:
        config['sensors']['architecture'] = {'enabled': False}
    
    return EvolutionEngine(project_root, config)
