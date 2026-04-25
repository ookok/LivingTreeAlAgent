"""
世界模型模拟器 - 结果预测器

预测动作执行结果和状态变化
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from .simulation_models import State


@dataclass
class Prediction:
    """预测结果"""
    success: bool                          # 是否成功
    confidence: float                       # 置信度 (0-1)
    predicted_state_changes: Dict[str, Any]  # 预测的状态变化
    predicted_outcome: Dict[str, Any]        # 预测的输出结果
    uncertainty: float = 0.0                 # 不确定性
    reasoning: str = ""                     # 推理过程
    warnings: List[str] = field(default_factory=list)  # 警告信息
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "confidence": self.confidence,
            "predicted_state_changes": self.predicted_state_changes,
            "predicted_outcome": self.predicted_outcome,
            "uncertainty": self.uncertainty,
            "reasoning": self.reasoning,
            "warnings": self.warnings
        }


class OutcomePredictor:
    """
    结果预测器
    
    基于世界模型预测动作执行结果
    """
    
    def __init__(self):
        # 预测函数: action -> Callable[[State, Dict], Prediction]
        self._predictors: Dict[str, Callable] = {}
        
        # 默认预测器
        self._default_predictor: Optional[Callable] = None
        
        # 预测历史
        self._prediction_history: List[Prediction] = []
    
    def register_predictor(
        self,
        action: str,
        predictor: Callable[[State, Dict[str, Any]], Prediction]
    ) -> None:
        """注册预测器"""
        self._predictors[action] = predictor
    
    def set_default_predictor(
        self,
        predictor: Callable[[State, Dict[str, Any]], Prediction]
    ) -> None:
        """设置默认预测器"""
        self._default_predictor = predictor
    
    def predict(
        self,
        action: str,
        state: State,
        params: Dict[str, Any] = None
    ) -> Prediction:
        """
        预测结果
        
        Args:
            action: 动作名称
            state: 当前状态
            params: 动作参数
            
        Returns:
            预测结果
        """
        params = params or {}
        
        # 查找预测器
        predictor = self._predictors.get(action, self._default_predictor)
        
        if predictor:
            prediction = predictor(action, state, params)
        else:
            # 使用简单预测
            prediction = self._simple_predict(action, state, params)
        
        # 记录历史
        self._prediction_history.append(prediction)
        
        return prediction
    
    def _simple_predict(
        self,
        action: str,
        state: State,
        params: Dict[str, Any]
    ) -> Prediction:
        """简单预测逻辑"""
        return Prediction(
            success=True,
            confidence=0.5,
            predicted_state_changes={},
            predicted_outcome={"action": action, "params": params},
            uncertainty=0.5,
            reasoning=f"No specific predictor for action '{action}', using default"
        )
    
    def get_history(self) -> List[Prediction]:
        """获取预测历史"""
        return self._prediction_history.copy()
    
    def clear_history(self) -> None:
        """清空历史"""
        self._prediction_history.clear()


class LLMPredictor:
    """
    LLM驱动的预测器
    
    使用大语言模型进行结果预测
    """
    
    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client
        
        # 提示模板
        self.prompt_template = """你是一个世界模型预测器。
给定当前状态和动作，预测执行结果。

当前状态:
{state_description}

动作: {action}
参数: {params}

请预测:
1. 执行是否成功
2. 状态如何变化
3. 执行结果的置信度 (0-1)
4. 任何警告或注意事项

以JSON格式输出:
{{
    "success": true/false,
    "confidence": 0.0-1.0,
    "state_changes": {{...}},
    "outcome": {{...}},
    "warnings": [...]
}}
"""
    
    def predict(
        self,
        action: str,
        state: State,
        params: Dict[str, Any] = None
    ) -> Prediction:
        """使用LLM预测"""
        if self.llm_client is None:
            return Prediction(
                success=True,
                confidence=0.5,
                predicted_state_changes={},
                predicted_outcome={},
                uncertainty=0.5,
                reasoning="No LLM client configured"
            )
        
        params = params or {}
        
        # 构建提示
        state_desc = self._describe_state(state)
        prompt = self.prompt_template.format(
            state_description=state_desc,
            action=action,
            params=params
        )
        
        # 调用LLM
        response = self._call_llm(prompt)
        
        # 解析响应
        return self._parse_response(response)
    
    def _describe_state(self, state: State) -> str:
        """描述状态"""
        lines = []
        
        # 实体状态
        if state.entity_states:
            lines.append("实体状态:")
            for entity_id, props in state.entity_states.items():
                lines.append(f"  - {entity_id}: {props}")
        
        # 全局状态
        if state.global_state:
            lines.append("全局状态:")
            for key, value in state.global_state.items():
                lines.append(f"  - {key}: {value}")
        
        return "\n".join(lines) if lines else "无"
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        # 简单实现，实际应该调用真实的LLM API
        return '{"success": true, "confidence": 0.8, "state_changes": {}, "outcome": {}, "warnings": []}'
    
    def _parse_response(self, response: str) -> Prediction:
        """解析LLM响应"""
        import json
        try:
            data = json.loads(response)
            return Prediction(
                success=data.get("success", True),
                confidence=data.get("confidence", 0.5),
                predicted_state_changes=data.get("state_changes", {}),
                predicted_outcome=data.get("outcome", {}),
                uncertainty=1.0 - data.get("confidence", 0.5),
                reasoning="Predicted by LLM"
            )
        except Exception:
            return Prediction(
                success=True,
                confidence=0.3,
                predicted_state_changes={},
                predicted_outcome={},
                uncertainty=0.7,
                reasoning=f"Failed to parse LLM response: {response[:100]}"
            )


class EnsemblePredictor:
    """
    集成预测器
    
    结合多个预测器的结果
    """
    
    def __init__(self, predictors: List[Any] = None):
        self.predictors = predictors or []
        
        # 权重
        self.weights: Dict[str, float] = {}
    
    def add_predictor(self, name: str, predictor: Any, weight: float = 1.0) -> None:
        """添加预测器"""
        self.predictors.append(predictor)
        self.weights[name] = weight
    
    def predict(
        self,
        action: str,
        state: State,
        params: Dict[str, Any] = None
    ) -> Prediction:
        """集成预测"""
        if not self.predictors:
            return Prediction(
                success=True,
                confidence=0.5,
                predicted_state_changes={},
                predicted_outcome={},
                uncertainty=0.5
            )
        
        predictions = []
        total_weight = 0.0
        
        for i, predictor in enumerate(self.predictors):
            try:
                pred = predictor.predict(action, state, params)
                weight = self.weights.get(f"predictor_{i}", 1.0)
                predictions.append((pred, weight))
                total_weight += weight
            except Exception:
                continue
        
        if not predictions:
            return Prediction(
                success=True,
                confidence=0.5,
                predicted_state_changes={},
                predicted_outcome={},
                uncertainty=0.5
            )
        
        # 加权平均
        weighted_success = sum(p.success * w for p, w in predictions) / total_weight
        weighted_confidence = sum(p.confidence * w for p, w in predictions) / total_weight
        weighted_uncertainty = sum(p.uncertainty * w for p, w in predictions) / total_weight
        
        # 合并状态变化
        merged_changes = {}
        for pred, _ in predictions:
            merged_changes.update(pred.predicted_state_changes)
        
        # 收集警告
        all_warnings = []
        for pred, _ in predictions:
            all_warnings.extend(pred.warnings)
        
        return Prediction(
            success=weighted_success >= 0.5,
            confidence=weighted_confidence,
            predicted_state_changes=merged_changes,
            predicted_outcome=predictions[0][0].predicted_outcome if predictions else {},
            uncertainty=weighted_uncertainty,
            reasoning=f"Ensemble of {len(predictions)} predictors",
            warnings=all_warnings
        )


class RuleBasedPredictor:
    """
    规则基础预测器
    
    基于预定义规则进行预测
    """
    
    def __init__(self):
        # 动作规则: action -> List[Rule]
        self._rules: Dict[str, List[Dict[str, Any]]] = {}
        
        # 默认规则
        self._load_default_rules()
    
    def _load_default_rules(self) -> None:
        """加载默认规则"""
        # 搜索动作
        self._rules["search"] = [
            {
                "condition": lambda state, params: True,
                "success_probability": 0.8,
                "state_changes": {},
                "outcome_template": {"results": [], "count": 0}
            }
        ]
        
        # 读取文件动作
        self._rules["read_file"] = [
            {
                "condition": lambda state, params: "file_path" in params,
                "success_probability": 0.9,
                "state_changes": {"last_file_read": "${file_path}"},
                "outcome_template": {"content": "", "success": True}
            }
        ]
        
        # 写入文件动作
        self._rules["write_file"] = [
            {
                "condition": lambda state, params: "file_path" in params and "content" in params,
                "success_probability": 0.85,
                "state_changes": {"last_file_written": "${file_path}"},
                "outcome_template": {"bytes_written": 0, "success": True}
            }
        ]
        
        # 执行命令动作
        self._rules["execute_command"] = [
            {
                "condition": lambda state, params: "command" in params,
                "success_probability": 0.75,
                "state_changes": {"commands_executed": "+1"},
                "outcome_template": {"stdout": "", "stderr": "", "return_code": 0}
            }
        ]
    
    def add_rule(self, action: str, rule: Dict[str, Any]) -> None:
        """添加规则"""
        if action not in self._rules:
            self._rules[action] = []
        self._rules[action].append(rule)
    
    def predict(
        self,
        action: str,
        state: Any,  # State 可以是 State 或 SimulationState
        params: Dict[str, Any] = None
    ) -> Prediction:
        """基于规则预测"""
        params = params or {}
        
        rules = self._rules.get(action, [])
        if not rules:
            return Prediction(
                success=True,
                confidence=0.3,
                predicted_state_changes={},
                predicted_outcome={},
                uncertainty=0.7,
                reasoning=f"No rules for action '{action}'"
            )
        
        # 找到匹配的规则
        for rule in rules:
            if rule["condition"](state, params):
                # 应用模板
                outcome = self._apply_template(rule["outcome_template"], params)
                state_changes = self._apply_template(rule["state_changes"], params)
                
                return Prediction(
                    success=True,
                    confidence=rule["success_probability"],
                    predicted_state_changes=state_changes,
                    predicted_outcome=outcome,
                    uncertainty=1.0 - rule["success_probability"],
                    reasoning=f"Matched rule for '{action}'"
                )
        
        # 无匹配规则
        return Prediction(
            success=True,
            confidence=0.2,
            predicted_state_changes={},
            predicted_outcome={},
            uncertainty=0.8,
            reasoning=f"No matching rule for '{action}'"
        )
    
    def _apply_template(self, template: Any, params: Dict[str, Any]) -> Any:
        """应用模板"""
        if isinstance(template, dict):
            return {k: self._apply_template(v, params) for k, v in template.items()}
        elif isinstance(template, str):
            # 简单的模板替换
            result = template
            for key, value in params.items():
                result = result.replace(f"${{{key}}}", str(value))
            return result
        elif isinstance(template, list):
            return [self._apply_template(item, params) for item in template]
        else:
            return template
