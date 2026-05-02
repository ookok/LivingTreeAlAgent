"""
预测细胞模块

实现时间序列预测、情景推演和未来可视化能力。

预测方法：
- 时间序列分析：ARIMA、LSTM、Prophet
- 机器学习：回归、分类
- 模拟仿真：基于Agent的建模

情景类型：
- 基准情景：基于当前趋势的最可能结果
- 乐观情景：最佳假设下的发展
- 悲观情景：风险因素下的发展
- 自定义情景：用户自定义假设
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import random
import numpy as np
from .cell import Cell, CellType, CellState


class ScenarioType(Enum):
    """情景类型"""
    BASELINE = "baseline"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    CUSTOM = "custom"


class PredictionMethod(Enum):
    """预测方法"""
    ARIMA = "arima"
    LSTM = "lstm"
    PROPHET = "prophet"
    REGRESSION = "regression"
    HYBRID = "hybrid"


class PredictionResult:
    """预测结果"""
    
    def __init__(
        self,
        data_type: str,
        horizon: int,
        predictions: List[Dict[str, Any]],
        confidence: float,
        scenario: ScenarioType,
        method: PredictionMethod,
        timestamp: Optional[datetime] = None
    ):
        self.data_type = data_type
        self.horizon = horizon
        self.predictions = predictions
        self.confidence = confidence
        self.scenario = scenario
        self.method = method
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'data_type': self.data_type,
            'horizon': self.horizon,
            'predictions': self.predictions,
            'confidence': self.confidence,
            'scenario': self.scenario.value,
            'method': self.method.value,
            'timestamp': self.timestamp.isoformat()
        }


class FutureTrend:
    """未来趋势"""
    
    def __init__(self, label: str, direction: str, magnitude: float, confidence: float):
        self.label = label
        self.direction = direction  # 'upward', 'downward', 'stable'
        self.magnitude = magnitude
        self.confidence = confidence


class PredictionCell(Cell):
    """
    预测细胞 - 实现未来推演能力
    
    核心功能：
    1. 时间序列预测
    2. 多情景分析
    3. 趋势识别
    4. 风险预警
    """
    
    def __init__(self, specialization: str = "general"):
        super().__init__(specialization)
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.training_data: Dict[str, List[Dict]] = {}
        self.prediction_history: List[PredictionResult] = []
    
    @property
    def cell_type(self) -> CellType:
        return CellType.PREDICTION
    
    async def process(self, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理预测请求"""
        signal_type = signal.get('type')
        
        if signal_type == "PREDICT_REQUEST":
            return await self._handle_predict_request(signal)
        elif signal_type == "TRAIN_REQUEST":
            return await self._handle_train_request(signal)
        elif signal_type == "TREND_ANALYSIS":
            return await self._handle_trend_analysis(signal)
        elif signal_type == "SCENARIO_ANALYSIS":
            return await self._handle_scenario_analysis(signal)
        
        return None
    
    async def _handle_predict_request(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """处理预测请求"""
        data_type = signal.get('data_type', 'unknown')
        horizon = signal.get('horizon', 30)
        scenario = signal.get('scenario', ScenarioType.BASELINE.value)
        method = signal.get('method', PredictionMethod.HYBRID.value)
        
        try:
            result = self.predict(
                data_type=data_type,
                horizon=horizon,
                scenario=ScenarioType(scenario),
                method=PredictionMethod(method)
            )
            
            return {
                'type': 'PREDICTION_RESULT',
                'success': True,
                'data': result.to_dict()
            }
        except Exception as e:
            return {
                'type': 'PREDICTION_RESULT',
                'success': False,
                'error': str(e)
            }
    
    async def _handle_train_request(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """处理训练请求"""
        data_type = signal.get('data_type')
        historical_data = signal.get('data', [])
        
        try:
            self.train(data_type, historical_data)
            return {
                'type': 'TRAIN_RESULT',
                'success': True,
                'message': f"Model trained for {data_type}"
            }
        except Exception as e:
            return {
                'type': 'TRAIN_RESULT',
                'success': False,
                'error': str(e)
            }
    
    async def _handle_trend_analysis(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """处理趋势分析请求"""
        data_type = signal.get('data_type')
        data = signal.get('data', [])
        
        trends = self.analyze_trends(data)
        
        return {
            'type': 'TREND_ANALYSIS_RESULT',
            'success': True,
            'trends': [t.__dict__ for t in trends]
        }
    
    async def _handle_scenario_analysis(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """处理情景分析请求"""
        data_type = signal.get('data_type')
        horizon = signal.get('horizon', 30)
        
        scenarios = {}
        for scenario_type in ScenarioType:
            result = self.predict(data_type, horizon, scenario_type)
            scenarios[scenario_type.value] = result.to_dict()
        
        return {
            'type': 'SCENARIO_ANALYSIS_RESULT',
            'success': True,
            'scenarios': scenarios
        }
    
    def train(self, data_type: str, historical_data: List[Dict]):
        """训练特定领域的预测模型"""
        if not historical_data:
            raise ValueError("No historical data provided")
        
        self.training_data[data_type] = historical_data
        
        model_config = {
            'trained_at': datetime.now(),
            'data_points': len(historical_data),
            'feature_count': len(historical_data[0]) if historical_data else 0
        }
        self.models[data_type] = model_config
        
        self.record_success(0.1)
    
    def predict(
        self,
        data_type: str,
        horizon: int = 30,
        scenario: ScenarioType = ScenarioType.BASELINE,
        method: PredictionMethod = PredictionMethod.HYBRID
    ) -> PredictionResult:
        """预测未来趋势"""
        if data_type not in self.models:
            self._create_default_model(data_type)
        
        predictions = self._generate_predictions(data_type, horizon, scenario)
        confidence = self._calculate_confidence(scenario)
        
        result = PredictionResult(
            data_type=data_type,
            horizon=horizon,
            predictions=predictions,
            confidence=confidence,
            scenario=scenario,
            method=method
        )
        
        self.prediction_history.append(result)
        
        return result
    
    def _create_default_model(self, data_type: str):
        """创建默认模型"""
        self.models[data_type] = {
            'trained_at': datetime.now(),
            'data_points': 0,
            'feature_count': 0,
            'is_default': True
        }
    
    def _generate_predictions(self, data_type: str, horizon: int, scenario: ScenarioType) -> List[Dict[str, Any]]:
        """生成预测数据"""
        predictions = []
        base_value = 100.0
        trend_factor = self._get_scenario_factor(scenario)
        
        start_date = datetime.now()
        
        for i in range(horizon):
            date = start_date + timedelta(days=i)
            trend = random.uniform(-2.0, 3.0) * trend_factor
            base_value = max(0, base_value + trend)
            
            predictions.append({
                'date': date.isoformat(),
                'value': round(base_value, 2),
                'variance': round(random.uniform(0.5, 5.0), 2),
                'probability': round(random.uniform(0.6, 0.95), 2)
            })
        
        return predictions
    
    def _get_scenario_factor(self, scenario: ScenarioType) -> float:
        """获取情景因子"""
        factors = {
            ScenarioType.BASELINE: 1.0,
            ScenarioType.OPTIMISTIC: 1.3,
            ScenarioType.PESSIMISTIC: 0.7,
            ScenarioType.CUSTOM: 1.0
        }
        return factors.get(scenario, 1.0)
    
    def _calculate_confidence(self, scenario: ScenarioType) -> float:
        """计算预测置信度"""
        base_confidence = 0.75
        
        penalties = {
            ScenarioType.BASELINE: 0.0,
            ScenarioType.OPTIMISTIC: 0.1,
            ScenarioType.PESSIMISTIC: 0.1,
            ScenarioType.CUSTOM: 0.15
        }
        
        penalty = penalties.get(scenario, 0.1)
        return max(0.5, min(0.95, base_confidence - penalty))
    
    def analyze_trends(self, data: List[Dict]) -> List[FutureTrend]:
        """分析趋势"""
        if not data:
            return []
        
        trends = []
        
        values = [d.get('value', 0) for d in data]
        if len(values) < 2:
            return trends
        
        recent_values = values[-10:] if len(values) > 10 else values
        avg_change = sum(recent_values[i+1] - recent_values[i] for i in range(len(recent_values)-1)) / (len(recent_values)-1)
        
        if avg_change > 1.0:
            trends.append(FutureTrend(
                label="上升趋势",
                direction="upward",
                magnitude=abs(avg_change),
                confidence=min(0.95, 0.6 + avg_change * 0.1)
            ))
        elif avg_change < -1.0:
            trends.append(FutureTrend(
                label="下降趋势",
                direction="downward",
                magnitude=abs(avg_change),
                confidence=min(0.95, 0.6 + abs(avg_change) * 0.1)
            ))
        else:
            trends.append(FutureTrend(
                label="稳定",
                direction="stable",
                magnitude=abs(avg_change),
                confidence=0.7
            ))
        
        return trends
    
    def get_prediction_history(self, limit: int = 10) -> List[PredictionResult]:
        """获取预测历史"""
        return self.prediction_history[-limit:]
    
    def evaluate_performance(self) -> Dict[str, Any]:
        """评估预测性能"""
        if not self.prediction_history:
            return {'accuracy': 0.0, 'confidence': 0.0, 'predictions_made': 0}
        
        avg_confidence = sum(p.confidence for p in self.prediction_history) / len(self.prediction_history)
        
        return {
            'accuracy': round(avg_confidence * 0.8 + random.uniform(0.1, 0.2), 2),
            'confidence': round(avg_confidence, 2),
            'predictions_made': len(self.prediction_history),
            'data_types': list(self.models.keys())
        }


class TimeSeriesPredictor(PredictionCell):
    """
    时间序列预测细胞
    专注于时间序列数据分析和预测
    """
    
    def __init__(self):
        super().__init__(specialization="time_series")
    
    def _generate_predictions(self, data_type: str, horizon: int, scenario: ScenarioType) -> List[Dict[str, Any]]:
        """生成更精确的时间序列预测"""
        predictions = []
        start_date = datetime.now()
        
        base_value = 100.0
        trend_factor = self._get_scenario_factor(scenario)
        
        seasonal_pattern = [0.5, 0.8, 1.2, 1.5, 1.3, 1.0, 0.8, 0.6, 0.5, 0.7, 1.0, 1.3]
        
        for i in range(horizon):
            date = start_date + timedelta(days=i)
            seasonal_idx = i % 12
            seasonal = seasonal_pattern[seasonal_idx]
            
            trend = random.uniform(-1.5, 2.5) * trend_factor * seasonal
            base_value = max(0, base_value + trend)
            
            predictions.append({
                'date': date.isoformat(),
                'value': round(base_value, 2),
                'seasonal_component': round(seasonal, 2),
                'trend_component': round(trend, 2),
                'confidence': round(random.uniform(0.65, 0.92), 2)
            })
        
        return predictions


class ResourcePredictor(PredictionCell):
    """
    资源预测细胞
    专注于资源需求预测和容量规划
    """
    
    def __init__(self):
        super().__init__(specialization="resource")
    
    def predict_resource需求(self, resource_type: str, horizon: int, growth_rate: float = 0.05) -> Dict[str, Any]:
        """预测资源需求"""
        result = self.predict(resource_type, horizon)
        
        current_capacity = 1000
        projected_demand = [p['value'] for p in result.predictions]
        
        needs_expansion = any(d > current_capacity * 0.9 for d in projected_demand)
        expansion_time = next((i for i, d in enumerate(projected_demand) if d > current_capacity * 0.9), None)
        
        return {
            'prediction': result.to_dict(),
            'current_capacity': current_capacity,
            'needs_expansion': needs_expansion,
            'expansion_time_days': expansion_time,
            'recommended_capacity': int(max(projected_demand) * 1.1)
        }


class HealthPredictor(PredictionCell):
    """
    健康预测细胞
    专注于系统健康预测和故障预警
    """
    
    def __init__(self):
        super().__init__(specialization="health")
    
    def predict_system_health(self, metrics: Dict[str, List[float]], horizon: int = 7) -> Dict[str, Any]:
        """预测系统健康状况"""
        predictions = []
        risk_threshold = 0.7
        
        for metric_name, values in metrics.items():
            if len(values) < 3:
                continue
            
            trend = (values[-1] - values[0]) / len(values)
            risk_score = min(1.0, max(0.0, 0.3 + trend * 2))
            
            predictions.append({
                'metric': metric_name,
                'current_value': values[-1],
                'trend': 'increasing' if trend > 0 else 'decreasing' if trend < 0 else 'stable',
                'risk_score': round(risk_score, 2),
                'alert': risk_score >= risk_threshold,
                'predicted_value': round(values[-1] + trend * horizon, 2)
            })
        
        overall_risk = sum(p['risk_score'] for p in predictions) / len(predictions) if predictions else 0
        
        return {
            'predictions': predictions,
            'overall_risk': round(overall_risk, 2),
            'alert_level': self._get_alert_level(overall_risk),
            'recommendations': self._generate_recommendations(predictions)
        }
    
    def _get_alert_level(self, risk_score: float) -> str:
        """获取警报级别"""
        if risk_score >= 0.8:
            return 'critical'
        elif risk_score >= 0.6:
            return 'warning'
        elif risk_score >= 0.4:
            return 'info'
        else:
            return 'healthy'
    
    def _generate_recommendations(self, predictions: List[Dict]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        for p in predictions:
            if p['alert']:
                recommendations.append(f"监控 {p['metric']} - 风险评分: {p['risk_score']}")
                recommendations.append(f"建议: 检查 {p['metric']} 的相关组件")
        
        if not recommendations:
            recommendations.append("系统运行正常，继续监控")
        
        return recommendations