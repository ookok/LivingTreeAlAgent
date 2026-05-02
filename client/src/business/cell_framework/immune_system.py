"""
免疫系统模块 - ImmuneSystem

实现异常检测、自我修复和有害隔离能力。

免疫系统层次：
┌─────────────────────────────────────────────────────────┐
│  免疫监控层                                            │
│  • 持续监控系统状态                                     │
│  • 检测异常行为                                         │
│  • 识别入侵和攻击                                       │
├─────────────────────────────────────────────────────────┤
│  防御响应层                                            │
│  • 激活防御机制                                         │
│  • 隔离有害细胞                                         │
│  • 清除恶意影响                                         │
├─────────────────────────────────────────────────────────┤
│  自我修复层                                            │
│  • 修复受损组件                                         │
│  • 恢复系统功能                                         │
│  • 重建连接网络                                         │
├─────────────────────────────────────────────────────────┤
│  记忆层                                                │
│  • 记住之前的威胁                                       │
│  • 快速识别已知威胁                                     │
│  • 生成抗体（应对策略）                                 │
└─────────────────────────────────────────────────────────┘

威胁类型：
- 内部威胁：故障、错误、性能下降
- 外部威胁：恶意输入、攻击、异常请求
- 环境威胁：资源耗尽、系统过载
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable
from collections import defaultdict


class ThreatLevel(Enum):
    """威胁级别"""
    NONE = "none"           # 无威胁
    LOW = "low"             # 低威胁
    MEDIUM = "medium"       # 中等威胁
    HIGH = "high"           # 高威胁
    CRITICAL = "critical"   # 严重威胁


class ThreatType(Enum):
    """威胁类型"""
    INTERNAL = "internal"           # 内部威胁
    EXTERNAL = "external"           # 外部威胁
    ENVIRONMENTAL = "environmental" # 环境威胁


class DefenseStatus(Enum):
    """防御状态"""
    NORMAL = "normal"           # 正常
    MONITORING = "monitoring"   # 监控中
    ACTIVE = "active"           # 主动防御
    QUARANTINE = "quarantine"   # 隔离中


class Threat:
    """威胁实体"""
    
    def __init__(
        self,
        threat_id: str,
        threat_type: ThreatType,
        level: ThreatLevel,
        description: str,
        source: str,
        timestamp: Optional[datetime] = None
    ):
        self.id = threat_id
        self.type = threat_type
        self.level = level
        self.description = description
        self.source = source
        self.timestamp = timestamp or datetime.now()
        self.resolved = False
        self.resolution_time: Optional[datetime] = None
        self.response_actions: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type.value,
            'level': self.level.value,
            'description': self.description,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved,
            'resolution_time': self.resolution_time.isoformat() if self.resolution_time else None,
            'response_actions': self.response_actions
        }


class Antibody:
    """抗体 - 应对威胁的策略"""
    
    def __init__(self, threat_pattern: str, response: Callable, effectiveness: float):
        self.threat_pattern = threat_pattern
        self.response = response
        self.effectiveness = effectiveness
        self.usage_count = 0
    
    def apply(self, threat: Threat) -> bool:
        """应用抗体"""
        result = self.response(threat)
        self.usage_count += 1
        
        # 根据效果调整有效性
        if result:
            self.effectiveness = min(1.0, self.effectiveness + 0.05)
        else:
            self.effectiveness = max(0.1, self.effectiveness - 0.1)
        
        return result


class ImmuneSystem:
    """
    免疫系统
    
    负责：
    1. 持续监控系统健康状态
    2. 检测异常和威胁
    3. 激活防御机制
    4. 隔离和清除威胁
    5. 自我修复
    6. 学习和记忆威胁模式
    """
    
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.status = DefenseStatus.NORMAL
        self.threats: List[Threat] = []
        self.antibodies: Dict[str, Antibody] = {}  # 威胁模式 -> 抗体
        self.quarantine_list: Set[str] = set()      # 隔离列表
        self.vaccinations: Dict[str, datetime] = {} # 免疫记录
        
        # 监控指标
        self.monitors: Dict[str, Any] = {
            'performance': {'threshold': 0.3, 'current': 1.0},
            'error_rate': {'threshold': 0.1, 'current': 0.0},
            'response_time': {'threshold': 5.0, 'current': 0.1},
            'memory_usage': {'threshold': 0.9, 'current': 0.3},
            'cpu_usage': {'threshold': 0.95, 'current': 0.2}
        }
        
        # 免疫记忆
        self.immune_memory: Dict[str, Any] = {}
    
    async def monitor(self) -> Dict[str, Any]:
        """
        监控系统状态
        
        Returns:
            监控报告
        """
        report = {
            'timestamp': datetime.now(),
            'status': self.status.value,
            'active_threats': len(self._get_active_threats()),
            'quarantined_items': len(self.quarantine_list),
            'metrics': self._get_metrics_summary(),
            'recent_threats': [t.to_dict() for t in self.threats[-5:]]
        }
        
        return report
    
    def _get_active_threats(self) -> List[Threat]:
        """获取活跃威胁"""
        return [t for t in self.threats if not t.resolved]
    
    def _get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        summary = {}
        for name, metric in self.monitors.items():
            status = 'normal'
            if metric['current'] > metric['threshold'] * 0.8:
                status = 'warning'
            if metric['current'] > metric['threshold']:
                status = 'critical'
            
            summary[name] = {
                'current': metric['current'],
                'threshold': metric['threshold'],
                'status': status
            }
        
        return summary
    
    async def detect_threat(self, data: Dict[str, Any]) -> Optional[Threat]:
        """
        检测威胁
        
        Args:
            data: 待检测的数据
        
        Returns:
            检测到的威胁，如果没有威胁则返回None
        """
        threat = await self._analyze_for_threats(data)
        
        if threat:
            self.threats.append(threat)
            await self._activate_defense(threat)
        
        return threat
    
    async def _analyze_for_threats(self, data: Dict[str, Any]) -> Optional[Threat]:
        """分析数据寻找威胁"""
        threat_id = str(uuid.uuid4())[:8]
        threat_type = ThreatType.INTERNAL
        level = ThreatLevel.NONE
        description = ""
        source = data.get('source', 'unknown')
        
        # 检查性能指标
        if self.monitors['performance']['current'] < 0.3:
            level = ThreatLevel.HIGH
            description = "系统性能严重下降"
            threat_type = ThreatType.ENVIRONMENTAL
        
        # 检查错误率
        if self.monitors['error_rate']['current'] > 0.1:
            if level.value < ThreatLevel.MEDIUM.value:
                level = ThreatLevel.MEDIUM
            description += "，错误率过高"
        
        # 检查资源使用
        if self.monitors['memory_usage']['current'] > 0.9:
            if level.value < ThreatLevel.HIGH.value:
                level = ThreatLevel.HIGH
            description += "，内存资源耗尽"
        
        # 检查外部输入
        if 'input' in data:
            input_data = data['input']
            if await self._detect_malicious_input(input_data):
                level = ThreatLevel.HIGH
                description = "检测到恶意输入"
                threat_type = ThreatType.EXTERNAL
        
        # 检查异常行为模式
        if await self._detect_anomalous_pattern(data):
            level = ThreatLevel.MEDIUM
            description = "检测到异常行为模式"
        
        if level == ThreatLevel.NONE:
            return None
        
        return Threat(
            threat_id=threat_id,
            threat_type=threat_type,
            level=level,
            description=description.strip('，'),
            source=source
        )
    
    async def _detect_malicious_input(self, input_data: Any) -> bool:
        """检测恶意输入"""
        # 简化的恶意输入检测
        if isinstance(input_data, str):
            # 检查常见攻击模式
            patterns = ['<script>', 'DROP TABLE', 'UNION SELECT', '../']
            for pattern in patterns:
                if pattern.lower() in input_data.lower():
                    return True
        
        # 检查异常大小
        if isinstance(input_data, (str, list, dict)):
            if len(str(input_data)) > 100000:
                return True
        
        return False
    
    async def _detect_anomalous_pattern(self, data: Dict) -> bool:
        """检测异常模式"""
        # 检查请求频率
        request_count = data.get('request_count', 0)
        if request_count > 1000:
            return True
        
        # 检查响应时间波动
        response_time_std = data.get('response_time_std', 0)
        if response_time_std > 2.0:
            return True
        
        return False
    
    async def _activate_defense(self, threat: Threat):
        """激活防御机制"""
        # 更新防御状态
        if threat.level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            self.status = DefenseStatus.ACTIVE
        elif threat.level == ThreatLevel.MEDIUM:
            if self.status == DefenseStatus.NORMAL:
                self.status = DefenseStatus.MONITORING
        
        # 尝试使用抗体
        antibody = self._find_antibody(threat)
        if antibody:
            success = antibody.apply(threat)
            if success:
                await self._resolve_threat(threat, "抗体成功清除威胁")
                return
        
        # 根据威胁类型采取行动
        actions = await self._determine_response(threat)
        threat.response_actions = actions
        
        # 执行响应
        await self._execute_response(threat, actions)
    
    def _find_antibody(self, threat: Threat) -> Optional[Antibody]:
        """寻找针对威胁的抗体"""
        for pattern, antibody in self.antibodies.items():
            if pattern.lower() in threat.description.lower():
                return antibody
        return None
    
    async def _determine_response(self, threat: Threat) -> List[str]:
        """确定响应行动"""
        actions = []
        
        if threat.type == ThreatType.EXTERNAL:
            actions.append("block_source")
            actions.append("log_threat")
        
        if threat.type == ThreatType.INTERNAL:
            actions.append("quarantine_component")
            actions.append("initiate_repair")
        
        if threat.type == ThreatType.ENVIRONMENTAL:
            actions.append("resource_throttling")
            actions.append("alert_admin")
        
        if threat.level == ThreatLevel.CRITICAL:
            actions.append("emergency_shutdown")
        
        return actions
    
    async def _execute_response(self, threat: Threat, actions: List[str]):
        """执行响应行动"""
        for action in actions:
            if action == "block_source":
                await self._block_source(threat.source)
            elif action == "quarantine_component":
                await self._quarantine_component(threat.source)
            elif action == "initiate_repair":
                await self._initiate_repair()
            elif action == "resource_throttling":
                await self._resource_throttling()
            elif action == "alert_admin":
                await self._alert_admin(threat)
            elif action == "emergency_shutdown":
                await self._emergency_shutdown()
            elif action == "log_threat":
                await self._log_threat(threat)
    
    async def _block_source(self, source: str):
        """阻止来源"""
        self.quarantine_list.add(source)
    
    async def _quarantine_component(self, component_id: str):
        """隔离组件"""
        self.quarantine_list.add(component_id)
    
    async def _initiate_repair(self):
        """启动修复"""
        # 简化的修复逻辑
        self.monitors['performance']['current'] = min(1.0, self.monitors['performance']['current'] + 0.1)
    
    async def _resource_throttling(self):
        """资源节流"""
        # 降低资源消耗
        self.monitors['cpu_usage']['current'] = max(0.0, self.monitors['cpu_usage']['current'] - 0.2)
        self.monitors['memory_usage']['current'] = max(0.0, self.monitors['memory_usage']['current'] - 0.2)
    
    async def _alert_admin(self, threat: Threat):
        """警告管理员"""
        pass  # 在实际系统中发送通知
    
    async def _emergency_shutdown(self):
        """紧急关闭"""
        self.status = DefenseStatus.QUARANTINE
    
    async def _log_threat(self, threat: Threat):
        """记录威胁"""
        self.immune_memory[threat.id] = threat.to_dict()
    
    async def _resolve_threat(self, threat: Threat, reason: str):
        """解决威胁"""
        threat.resolved = True
        threat.resolution_time = datetime.now()
        threat.response_actions.append(f"resolved: {reason}")
        
        # 学习应对策略
        await self._learn_from_threat(threat)
        
        # 如果没有活跃威胁，恢复正常状态
        if not self._get_active_threats():
            self.status = DefenseStatus.NORMAL
    
    async def _learn_from_threat(self, threat: Threat):
        """从威胁中学习"""
        # 创建新抗体
        pattern = threat.description[:30]
        if pattern not in self.antibodies:
            self.antibodies[pattern] = Antibody(
                threat_pattern=pattern,
                response=lambda t: True,  # 简化响应
                effectiveness=0.7
            )
        
        # 更新免疫记录
        self.vaccinations[pattern] = datetime.now()
    
    def add_antibody(self, threat_pattern: str, response: Callable):
        """添加抗体"""
        self.antibodies[threat_pattern] = Antibody(
            threat_pattern=threat_pattern,
            response=response,
            effectiveness=0.7
        )
    
    def update_monitor(self, metric_name: str, value: float):
        """更新监控指标"""
        if metric_name in self.monitors:
            self.monitors[metric_name]['current'] = value
    
    def get_immune_status(self) -> Dict[str, Any]:
        """获取免疫系统状态"""
        return {
            'id': self.id,
            'status': self.status.value,
            'active_threats': len(self._get_active_threats()),
            'total_threats_resolved': len([t for t in self.threats if t.resolved]),
            'antibodies_count': len(self.antibodies),
            'quarantined_items': len(self.quarantine_list),
            'metrics': self._get_metrics_summary()
        }
    
    async def heal(self):
        """执行自我修复"""
        # 修复所有受损指标
        for metric_name, metric in self.monitors.items():
            if metric['current'] < 0.5:
                metric['current'] = min(1.0, metric['current'] + 0.1)
        
        # 清理已解决的威胁记录
        self.threats = [t for t in self.threats if not t.resolved or (datetime.now() - t.timestamp).days < 7]
        
        return {
            'message': '自我修复完成',
            'metrics_restored': len([m for m in self.monitors.values() if m['current'] >= 0.5])
        }