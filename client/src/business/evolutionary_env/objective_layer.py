"""
目标层（Objective Layer）：定义"好报告"的奖励函数

核心功能：
1. 合规性奖励（Compliance Reward）：检查法规强制章节
2. 用户认可奖励（Adoption Reward）：用户采纳建议
3. 效率奖励（Efficiency Reward）：完成时间缩短
"""

import time
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class RewardSignal:
    reward_type: str  # compliance, adoption, efficiency
    score: float
    description: str
    timestamp: float

@dataclass
class EvaluationResult:
    total_score: float
    compliance_score: float
    adoption_score: float
    efficiency_score: float
    feedback: List[str]

class ObjectiveLayer:
    def __init__(self):
        self.reward_history: List[RewardSignal] = []
        self.compliance_rules = self._load_compliance_rules()
        self.session_start_time = None
        self.session_end_time = None
    
    def _load_compliance_rules(self) -> List[Dict[str, Any]]:
        """
        加载环评合规规则
        
        这些规则定义了"好报告"的标准
        """
        return [
            {
                'id': 'rule_1',
                'name': '三线一单分析',
                'pattern': ['三线一单', '生态保护红线', '环境质量底线', '资源利用上线'],
                'required': True,
                'weight': 20
            },
            {
                'id': 'rule_2',
                'name': '环境现状调查',
                'pattern': ['现状调查', '环境质量现状', '监测数据'],
                'required': True,
                'weight': 15
            },
            {
                'id': 'rule_3',
                'name': '影响预测',
                'pattern': ['影响预测', '预测结果', '预测分析'],
                'required': True,
                'weight': 15
            },
            {
                'id': 'rule_4',
                'name': '环境保护措施',
                'pattern': ['保护措施', '环保措施', '治理措施'],
                'required': True,
                'weight': 15
            },
            {
                'id': 'rule_5',
                'name': '公众参与',
                'pattern': ['公众参与', '意见征集', '公示'],
                'required': False,
                'weight': 10
            },
            {
                'id': 'rule_6',
                'name': '环境风险评价',
                'pattern': ['风险评价', '应急预案', '事故防范'],
                'required': False,
                'weight': 10
            },
            {
                'id': 'rule_7',
                'name': '清洁生产',
                'pattern': ['清洁生产', '节能减排', '循环经济'],
                'required': False,
                'weight': 10
            },
            {
                'id': 'rule_8',
                'name': '总量控制',
                'pattern': ['总量控制', '排放总量', '总量指标'],
                'required': False,
                'weight': 5
            }
        ]
    
    def start_session(self):
        """开始新的工作会话"""
        self.session_start_time = time.time()
    
    def end_session(self):
        """结束工作会话"""
        self.session_end_time = time.time()
    
    def evaluate_compliance(self, report_content: str) -> float:
        """
        合规性奖励：检查报告是否包含法规强制章节
        
        Args:
            report_content: 报告内容
        
        Returns:
            合规性得分（0-100）
        """
        score = 0
        total_weight = 0
        feedback = []
        
        for rule in self.compliance_rules:
            total_weight += rule['weight']
            
            # 检查是否包含规则模式
            matched = any(pattern in report_content for pattern in rule['pattern'])
            
            if matched:
                score += rule['weight']
                feedback.append(f"✓ 已包含: {rule['name']}")
            elif rule['required']:
                feedback.append(f"✗ 缺失强制章节: {rule['name']}")
            else:
                feedback.append(f"○ 建议添加: {rule['name']}")
        
        # 归一化得分
        normalized_score = (score / total_weight) * 100
        
        # 记录奖励信号
        self._add_reward('compliance', normalized_score, 
                        f"合规性评估: {len([r for r in self.compliance_rules if any(p in report_content for p in r['pattern'])])}/{len(self.compliance_rules)} 规则命中")
        
        return normalized_score, feedback
    
    def evaluate_adoption(self, suggestion_count: int, adoption_count: int) -> float:
        """
        用户认可奖励：用户采纳了AI的建议
        
        Args:
            suggestion_count: AI提出的建议总数
            adoption_count: 用户采纳的建议数
        
        Returns:
            采纳率得分（0-100）
        """
        if suggestion_count == 0:
            return 0
        
        adoption_rate = (adoption_count / suggestion_count) * 100
        
        self._add_reward('adoption', adoption_rate,
                        f"采纳率: {adoption_count}/{suggestion_count}")
        
        return adoption_rate
    
    def evaluate_efficiency(self, baseline_time: float = 3600) -> float:
        """
        效率奖励：用户完成报告的时间缩短
        
        Args:
            baseline_time: 基准时间（默认1小时）
        
        Returns:
            效率得分（0-100）
        """
        if self.session_start_time is None or self.session_end_time is None:
            return 0
        
        actual_time = self.session_end_time - self.session_start_time
        
        # 如果用时少于基准时间，给予奖励
        if actual_time < baseline_time:
            efficiency_score = min(100, ((baseline_time - actual_time) / baseline_time) * 100)
        else:
            efficiency_score = max(0, 100 - ((actual_time - baseline_time) / baseline_time) * 50)
        
        self._add_reward('efficiency', efficiency_score,
                        f"完成时间: {actual_time/60:.1f}分钟")
        
        return efficiency_score
    
    def _add_reward(self, reward_type: str, score: float, description: str):
        """添加奖励信号"""
        reward = RewardSignal(
            reward_type=reward_type,
            score=score,
            description=description,
            timestamp=time.time()
        )
        self.reward_history.append(reward)
    
    def evaluate_report(self, report_content: str, suggestion_count: int, adoption_count: int) -> EvaluationResult:
        """
        综合评估报告质量
        
        Args:
            report_content: 报告内容
            suggestion_count: AI提出的建议数
            adoption_count: 用户采纳的建议数
        
        Returns:
            综合评估结果
        """
        compliance_score, feedback = self.evaluate_compliance(report_content)
        adoption_score = self.evaluate_adoption(suggestion_count, adoption_count)
        efficiency_score = self.evaluate_efficiency()
        
        # 综合得分（加权）
        total_score = (compliance_score * 0.5 + adoption_score * 0.3 + efficiency_score * 0.2)
        
        return EvaluationResult(
            total_score=total_score,
            compliance_score=compliance_score,
            adoption_score=adoption_score,
            efficiency_score=efficiency_score,
            feedback=feedback
        )
    
    def get_reward_summary(self) -> Dict[str, Any]:
        """获取奖励信号摘要"""
        summary = {
            'total_rewards': len(self.reward_history),
            'compliance_rewards': [],
            'adoption_rewards': [],
            'efficiency_rewards': []
        }
        
        for reward in self.reward_history:
            category = f"{reward.reward_type}_rewards"
            summary[category].append({
                'score': reward.score,
                'description': reward.description,
                'timestamp': reward.timestamp
            })
        
        return summary
    
    def clear_history(self):
        """清除历史记录"""
        self.reward_history = []
        self.session_start_time = None
        self.session_end_time = None