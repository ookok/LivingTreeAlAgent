from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import os
import re
from collections import defaultdict

class PolicyType(Enum):
    TASK_PLANNING = "task_planning"
    SKILL_SELECTION = "skill_selection"
    PROMPT_OPTIMIZATION = "prompt_optimization"
    FEEDBACK_HANDLING = "feedback_handling"
    LEARNING_STRATEGY = "learning_strategy"

class PolicyAction(Enum):
    USE_SKILL = "use_skill"
    SKIP_SKILL = "skip_skill"
    MODIFY_PARAMS = "modify_params"
    RETRY_TASK = "retry_task"
    ASK_CLARIFICATION = "ask_clarification"
    CALL_HUMAN = "call_human"

@dataclass
class PolicyRule:
    condition: str
    action: PolicyAction
    action_params: Dict[str, Any]
    confidence: float = 0.8
    usage_count: int = 0
    success_count: int = 0

@dataclass
class Policy:
    name: str
    policy_type: PolicyType
    rules: List[PolicyRule]
    description: str = ""
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    enabled: bool = True

@dataclass
class PolicyInsight:
    insight_id: str
    policy_name: str
    insight_type: str
    description: str
    evidence: List[str]
    recommended_action: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)

class PolicyEngine:
    def __init__(self, storage_path: str = "./data/policies"):
        self.storage_path = storage_path
        self.policies: Dict[str, Policy] = {}
        self.insights: List[PolicyInsight] = []
        os.makedirs(storage_path, exist_ok=True)
        self._load_policies()
        self._load_insights()
    
    def _load_policies(self):
        for filename in os.listdir(self.storage_path):
            if filename.endswith(".json") and not filename.startswith("insights_"):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        policy = self._policy_from_dict(data)
                        self.policies[policy.name] = policy
                except Exception as e:
                    print(f"Error loading policy {filename}: {e}")
    
    def _load_insights(self):
        insights_file = os.path.join(self.storage_path, "insights.json")
        if os.path.exists(insights_file):
            try:
                with open(insights_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.insights = [self._insight_from_dict(d) for d in data]
            except Exception as e:
                print(f"Error loading insights: {e}")
    
    def _save_policy(self, policy: Policy):
        filepath = os.path.join(self.storage_path, f"{policy.name}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._policy_to_dict(policy), f, indent=2, default=str)
    
    def _save_insights(self):
        insights_file = os.path.join(self.storage_path, "insights.json")
        with open(insights_file, 'w', encoding='utf-8') as f:
            json.dump([self._insight_to_dict(i) for i in self.insights], f, indent=2, default=str)
    
    def _policy_to_dict(self, policy: Policy) -> Dict[str, Any]:
        return {
            "name": policy.name,
            "policy_type": policy.policy_type.value,
            "rules": [
                {
                    "condition": rule.condition,
                    "action": rule.action.value,
                    "action_params": rule.action_params,
                    "confidence": rule.confidence,
                    "usage_count": rule.usage_count,
                    "success_count": rule.success_count
                } for rule in policy.rules
            ],
            "description": policy.description,
            "version": policy.version,
            "created_at": policy.created_at.isoformat(),
            "updated_at": policy.updated_at.isoformat(),
            "enabled": policy.enabled
        }
    
    def _policy_from_dict(self, data: Dict[str, Any]) -> Policy:
        return Policy(
            name=data["name"],
            policy_type=PolicyType(data["policy_type"]),
            rules=[
                PolicyRule(
                    condition=rule["condition"],
                    action=PolicyAction(rule["action"]),
                    action_params=rule["action_params"],
                    confidence=rule["confidence"],
                    usage_count=rule["usage_count"],
                    success_count=rule["success_count"]
                ) for rule in data["rules"]
            ],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            enabled=data.get("enabled", True)
        )
    
    def _insight_to_dict(self, insight: PolicyInsight) -> Dict[str, Any]:
        return {
            "insight_id": insight.insight_id,
            "policy_name": insight.policy_name,
            "insight_type": insight.insight_type,
            "description": insight.description,
            "evidence": insight.evidence,
            "recommended_action": insight.recommended_action,
            "confidence": insight.confidence,
            "timestamp": insight.timestamp.isoformat()
        }
    
    def _insight_from_dict(self, data: Dict[str, Any]) -> PolicyInsight:
        return PolicyInsight(
            insight_id=data["insight_id"],
            policy_name=data["policy_name"],
            insight_type=data["insight_type"],
            description=data["description"],
            evidence=data["evidence"],
            recommended_action=data["recommended_action"],
            confidence=data["confidence"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )
    
    def register_policy(self, policy: Policy):
        self.policies[policy.name] = policy
        self._save_policy(policy)
    
    def get_policy(self, policy_name: str) -> Optional[Policy]:
        return self.policies.get(policy_name)
    
    def get_policies_by_type(self, policy_type: PolicyType) -> List[Policy]:
        return [p for p in self.policies.values() if p.policy_type == policy_type and p.enabled]
    
    def evaluate_policy(self, policy_name: str, context: Dict[str, Any]) -> Optional[PolicyRule]:
        policy = self.policies.get(policy_name)
        if not policy or not policy.enabled:
            return None
        
        for rule in policy.rules:
            if self._evaluate_condition(rule.condition, context):
                rule.usage_count += 1
                self._save_policy(policy)
                return rule
        
        return None
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        try:
            condition = condition.replace("AND", "and").replace("OR", "or").replace("NOT", "not")
            local_vars = context.copy()
            return eval(condition, {}, local_vars)
        except Exception:
            return False
    
    def record_rule_result(self, policy_name: str, condition: str, success: bool):
        policy = self.policies.get(policy_name)
        if not policy:
            return
        
        for rule in policy.rules:
            if rule.condition == condition:
                rule.success_count += 1 if success else 0
                self._save_policy(policy)
                break
    
    def analyze_experience(self, experience_data: Dict[str, Any]) -> List[PolicyInsight]:
        insights = []
        
        task_type = experience_data.get("task_type")
        success = experience_data.get("success", False)
        skills_used = experience_data.get("skills_used", [])
        feedback = experience_data.get("human_feedback")
        
        if not success:
            insight = self._analyze_failure(experience_data)
            if insight:
                insights.append(insight)
        
        for skill_usage in skills_used:
            skill_insight = self._analyze_skill_usage(skill_usage, experience_data)
            if skill_insight:
                insights.append(skill_insight)
        
        if feedback:
            feedback_insight = self._analyze_feedback(feedback, experience_data)
            if feedback_insight:
                insights.append(feedback_insight)
        
        self.insights.extend(insights)
        self._save_insights()
        return insights
    
    def _analyze_failure(self, experience_data: Dict[str, Any]) -> Optional[PolicyInsight]:
        task_type = experience_data.get("task_type")
        skills_used = experience_data.get("skills_used", [])
        error_message = experience_data.get("error_message", "")
        
        if len(skills_used) == 0:
            return PolicyInsight(
                insight_id=f"insight_{int(datetime.now().timestamp())}",
                policy_name="task_planning",
                insight_type="missing_skills",
                description=f"任务类型 {task_type} 未使用任何Skill导致失败",
                evidence=[f"任务描述: {experience_data.get('task_description', '')}"],
                recommended_action="建议为该任务类型添加合适的Skill",
                confidence=0.85
            )
        
        failed_skills = [su for su in skills_used if not su.get("success", True)]
        if failed_skills:
            return PolicyInsight(
                insight_id=f"insight_{int(datetime.now().timestamp())}",
                policy_name="skill_selection",
                insight_type="skill_failure",
                description=f"Skill {failed_skills[0].get('skill_name')} 执行失败",
                evidence=[f"错误信息: {error_message}"],
                recommended_action="考虑禁用该Skill或寻找替代方案",
                confidence=0.9
            )
        
        return None
    
    def _analyze_skill_usage(self, skill_usage: Dict[str, Any], experience_data: Dict[str, Any]) -> Optional[PolicyInsight]:
        skill_name = skill_usage.get("skill_name")
        execution_time = skill_usage.get("execution_time", 0)
        success = skill_usage.get("success", True)
        
        if execution_time > 30:
            return PolicyInsight(
                insight_id=f"insight_{int(datetime.now().timestamp())}",
                policy_name="skill_selection",
                insight_type="performance_issue",
                description=f"Skill {skill_name} 执行时间过长 ({execution_time}s)",
                evidence=[f"任务类型: {experience_data.get('task_type')}"],
                recommended_action="考虑优化该Skill或寻找更快的替代方案",
                confidence=0.75
            )
        
        if not success:
            return PolicyInsight(
                insight_id=f"insight_{int(datetime.now().timestamp())}",
                policy_name="skill_selection",
                insight_type="skill_failure_pattern",
                description=f"Skill {skill_name} 执行失败",
                evidence=[f"输入参数: {json.dumps(skill_usage.get('input_params', {}))}"],
                recommended_action="分析输入参数是否符合预期",
                confidence=0.8
            )
        
        return None
    
    def _analyze_feedback(self, feedback: Dict[str, Any], experience_data: Dict[str, Any]) -> Optional[PolicyInsight]:
        feedback_type = feedback.get("feedback_type")
        rating = feedback.get("rating")
        comments = feedback.get("comments", "")
        
        if feedback_type == "thumbs_down" or (rating and rating < 3):
            return PolicyInsight(
                insight_id=f"insight_{int(datetime.now().timestamp())}",
                policy_name="feedback_handling",
                insight_type="negative_feedback",
                description=f"收到负面反馈，评分: {rating}",
                evidence=[f"用户评论: {comments}", f"任务描述: {experience_data.get('task_description', '')}"],
                recommended_action="分析失败原因，调整相关策略",
                confidence=0.95
            )
        
        if feedback_type == "detailed" and comments:
            if "慢" in comments or "耗时" in comments:
                return PolicyInsight(
                    insight_id=f"insight_{int(datetime.now().timestamp())}",
                    policy_name="performance",
                    insight_type="performance_feedback",
                    description="用户反馈执行速度慢",
                    evidence=[f"用户评论: {comments}"],
                    recommended_action="优化执行流程，考虑缓存或并行处理",
                    confidence=0.85
                )
        
        return None
    
    def update_policy(self, insights: List[PolicyInsight]):
        for insight in insights:
            policy = self.policies.get(insight.policy_name)
            if not policy:
                policy = Policy(
                    name=insight.policy_name,
                    policy_type=self._infer_policy_type(insight.insight_type),
                    rules=[],
                    description=f"自动生成的{insight.insight_type}策略"
                )
                self.policies[insight.policy_name] = policy
            
            new_rule = self._generate_rule_from_insight(insight)
            if new_rule:
                existing_rule = next((r for r in policy.rules if r.condition == new_rule.condition), None)
                if existing_rule:
                    existing_rule.confidence = min(1.0, existing_rule.confidence + 0.1)
                else:
                    policy.rules.append(new_rule)
                
                policy.updated_at = datetime.now()
                self._save_policy(policy)
    
    def _infer_policy_type(self, insight_type: str) -> PolicyType:
        if "skill" in insight_type.lower():
            return PolicyType.SKILL_SELECTION
        elif "feedback" in insight_type.lower():
            return PolicyType.FEEDBACK_HANDLING
        elif "planning" in insight_type.lower():
            return PolicyType.TASK_PLANNING
        else:
            return PolicyType.LEARNING_STRATEGY
    
    def _generate_rule_from_insight(self, insight: PolicyInsight) -> Optional[PolicyRule]:
        if insight.insight_type == "skill_failure":
            return PolicyRule(
                condition=f"task_type == '{insight.policy_name}'",
                action=PolicyAction.SKIP_SKILL,
                action_params={"skill_name": insight.description.split()[1]},
                confidence=insight.confidence
            )
        
        if insight.insight_type == "missing_skills":
            return PolicyRule(
                condition=f"len(skills_used) == 0",
                action=PolicyAction.ASK_CLARIFICATION,
                action_params={"message": "需要更多信息来选择合适的工具"},
                confidence=insight.confidence
            )
        
        if insight.insight_type == "negative_feedback":
            return PolicyRule(
                condition=f"human_feedback.get('rating', 5) < 3",
                action=PolicyAction.RETRY_TASK,
                action_params={"retry_count": 1},
                confidence=insight.confidence
            )
        
        return None
    
    def get_recent_insights(self, limit: int = 10) -> List[PolicyInsight]:
        return sorted(self.insights, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_insights_by_type(self, insight_type: str) -> List[PolicyInsight]:
        return [i for i in self.insights if i.insight_type == insight_type]
    
    def suggest_policy_changes(self) -> List[Dict[str, Any]]:
        suggestions = []
        
        for policy_name, policy in self.policies.items():
            for rule in policy.rules:
                if rule.usage_count > 0:
                    success_rate = rule.success_count / rule.usage_count
                    if success_rate < 0.6:
                        suggestions.append({
                            "policy_name": policy_name,
                            "rule_condition": rule.condition,
                            "issue": f"规则成功率低 ({success_rate:.2f})",
                            "suggestion": "考虑修改规则条件或禁用此规则",
                            "confidence": success_rate
                        })
        
        for insight in self.insights[-20:]:
            if insight.confidence > 0.8 and not self._insight_applied(insight):
                suggestions.append({
                    "policy_name": insight.policy_name,
                    "rule_condition": "",
                    "issue": insight.description,
                    "suggestion": insight.recommended_action,
                    "confidence": insight.confidence
                })
        
        return sorted(suggestions, key=lambda x: -x["confidence"])[:10]
    
    def _insight_applied(self, insight: PolicyInsight) -> bool:
        policy = self.policies.get(insight.policy_name)
        if not policy:
            return False
        
        action_keywords = ["禁用", "跳过", "重试", "询问"]
        for rule in policy.rules:
            if any(keyword in rule.action_params.get("message", "") or 
                   keyword in str(rule.action_params) for keyword in action_keywords):
                return True
        
        return False
