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
        
        # 提案队列（使用 StructuredProposal）
        self._proposal_queue: List[StructuredProposal] = []
        
        # 统计
        self._stats = {
            'total_signals': 0,
            'total_proposals': 0,
            'proposals_approved': 0,
            'proposals_rejected': 0,
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
    
    def approve_proposal(self, proposal_id: str) -> bool:
        """
        批准提案
        
        Args:
            proposal_id: 提案ID
        
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
                proposal.approved_by = "user"
                proposal.updated_at = datetime.now()
                self._stats['proposals_approved'] += 1
                
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
