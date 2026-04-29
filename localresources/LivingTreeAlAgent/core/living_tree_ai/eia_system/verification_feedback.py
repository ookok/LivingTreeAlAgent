"""
验证反馈系统 - 实现"导出-验证-反馈"闭环
将工程师在外部工具中完成的验证结果反馈到系统，形成持续优化
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from difflib import SequenceMatcher


class FeedbackSource(Enum):
    """反馈来源"""
    ENGINEER = "engineer"           # 工程师手动反馈
    EXTERNAL_TOOL = "external_tool" # 外部工具（EIAProA/CadnaA）
    AUTOMATIC = "automatic"         # 系统自动检测
    EXPERT_REVIEW = "expert_review" # 专家评审


class DifferenceType(Enum):
    """差异类型"""
    PARAMETER_MISMATCH = "parameter_mismatch"     # 参数不一致
    MODEL_SETTING_DIFF = "model_setting_diff"     # 模型设置差异
    BOUNDARY_CONDITION = "boundary_condition"     # 边界条件差异
    DATA_ENTRY_ERROR = "data_entry_error"         # 数据录入错误
    VERSION_INCOMPATIBILITY = "version_incompat"  # 版本不兼容
    CALCULATION_METHOD = "calculation_method"     # 计算方法差异
    UNKNOWN = "unknown"                             # 未知原因


class DifferenceSeverity(Enum):
    """差异严重程度"""
    CRITICAL = "critical"   # 严重（影响结论）
    WARNING = "warning"      # 警告（需要关注）
    INFO = "info"           # 信息（仅供参考）
    NEGLIGIBLE = "negligible" # 可忽略


@dataclass
class DifferenceRecord:
    """差异记录"""
    diff_id: str
    project_id: str
    data_item: str              # 出问题的数据项
    original_value: Any         # 系统原始值
    external_value: Any         # 外部工具值
    difference_type: DifferenceType
    severity: DifferenceSeverity
    tolerance: float = 0.0     # 允许的容差
    relative_diff: float = 0.0  # 相对差异百分比
    
    # 来源信息
    feedback_source: FeedbackSource
    feedback_time: str
    feedback_by: str = ""      # 反馈者
    external_tool: str = ""     # 外部工具名称
    
    # 分析结果
    cause_analysis: str = ""   # 原因分析
    recommended_action: str = "" # 建议操作
    is_resolved: bool = False
    resolution: str = ""
    resolved_by: str = ""
    resolved_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "diff_id": self.diff_id,
            "project_id": self.project_id,
            "data_item": self.data_item,
            "original_value": self.original_value,
            "external_value": self.external_value,
            "difference_type": self.difference_type.value,
            "severity": self.severity.value,
            "tolerance": self.tolerance,
            "relative_diff": self.relative_diff,
            "feedback_source": self.feedback_source.value,
            "feedback_time": self.feedback_time,
            "feedback_by": self.feedback_by,
            "external_tool": self.external_tool,
            "cause_analysis": self.cause_analysis,
            "recommended_action": self.recommended_action,
            "is_resolved": self.is_resolved,
            "resolution": self.resolution,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at
        }


@dataclass
class VerificationFeedback:
    """验证反馈"""
    feedback_id: str
    project_id: str
    package_id: str            # 关联的导出包ID
    
    # 反馈基本信息
    source: FeedbackSource
    submitted_by: str
    submitted_at: str
    external_tool_name: str = ""
    
    # 差异列表
    differences: List[DifferenceRecord] = field(default_factory=list)
    
    # 整体评估
    overall_assessment: str = ""  # "一致" / "有小差异" / "有重大差异"
    confidence_level: float = 0.0  # 0-1
    
    # 附加文件
    attachments: List[Dict] = field(default_factory=list)  # [{"name": "", "path": "", "type": ""}]
    
    # 工程师意见
    engineer_comments: str = ""
    system_learning: bool = False  # 是否纳入系统学习
    
    def to_dict(self) -> Dict:
        return {
            "feedback_id": self.feedback_id,
            "project_id": self.project_id,
            "package_id": self.package_id,
            "source": self.source.value,
            "submitted_by": self.submitted_by,
            "submitted_at": self.submitted_at,
            "external_tool_name": self.external_tool_name,
            "differences": [d.to_dict() for d in self.differences],
            "overall_assessment": self.overall_assessment,
            "confidence_level": self.confidence_level,
            "attachments": self.attachments,
            "engineer_comments": self.engineer_comments,
            "system_learning": self.system_learning
        }


@dataclass
class LearningRecord:
    """系统学习记录"""
    record_id: str
    project_id: str
    feedback_id: str
    
    # 学习内容
    category: str              # "parameter" / "model_setting" / "boundary_condition" / "calculation_method"
    key: str                   # 关键标识
    old_value: Any             # 之前的值/行为
    new_value: Any             # 新的值/行为
    trigger_count: int = 1    # 触发次数
    confidence: float = 0.0    # 学习置信度
    
    # 元数据
    created_at: str
    last_updated: str
    source_projects: List[str] = field(default_factory=list)  # 来源项目列表
    
    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "project_id": self.project_id,
            "feedback_id": self.feedback_id,
            "category": self.category,
            "key": self.key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "trigger_count": self.trigger_count,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "source_projects": self.source_projects
        }


class VerificationFeedbackSystem:
    """
    验证反馈系统
    
    实现"导出-验证-反馈"闭环：
    1. 工程师导出数据到外部工具（如EIAProA）
    2. 运行验证，标记差异点
    3. 将差异报告反馈到系统
    4. 系统分析差异原因，自动学习并更新知识库
    """
    
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.home() / ".hermes-desktop" / "eia_feedback"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据存储
        self.feedbacks: List[VerificationFeedback] = []
        self.differences: List[DifferenceRecord] = []
        self.learning_records: List[LearningRecord] = []
        
        # 知识库
        self.knowledge_base = self._load_knowledge_base()
        
        # 容差配置
        self.tolerance_config = {
            "emission_rate": 0.01,        # 排放速率：1%
            "concentration": 0.05,         # 浓度：5%
            "distance": 0.1,               # 距离：10%
            "wind_speed": 0.1,             # 风速：10%
            "stability": 0.0,              # 稳定度：必须完全匹配
        }
        
        # 回调函数
        self.on_feedback_received: Optional[Callable] = None
        self.on_learning_triggered: Optional[Callable] = None
    
    def _load_knowledge_base(self) -> Dict:
        """加载知识库"""
        kb_path = self.workspace_dir / "knowledge_base.json"
        if kb_path.exists():
            with open(kb_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "parameter_adjustments": {},   # 参数调整记录
            "model_settings": {},           # 模型设置偏好
            "boundary_conditions": {},      # 边界条件默认值
            "calculation_hints": {},        # 计算提示
        }
    
    def _save_knowledge_base(self):
        """保存知识库"""
        kb_path = self.workspace_dir / "knowledge_base.json"
        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
    
    # ==================== 核心方法 ====================
    
    def submit_feedback(
        self,
        project_id: str,
        package_id: str,
        source: FeedbackSource,
        submitted_by: str,
        differences: List[Dict] = None,
        overall_assessment: str = "",
        engineer_comments: str = "",
        external_tool_name: str = ""
    ) -> VerificationFeedback:
        """
        提交验证反馈
        
        Args:
            project_id: 项目ID
            package_id: 关联的导出包ID
            source: 反馈来源
            submitted_by: 提交人
            differences: 差异列表
            overall_assessment: 整体评估
            engineer_comments: 工程师意见
            external_tool_name: 外部工具名称
        """
        feedback_id = self._generate_feedback_id(project_id)
        
        feedback = VerificationFeedback(
            feedback_id=feedback_id,
            project_id=project_id,
            package_id=package_id,
            source=source,
            submitted_by=submitted_by,
            submitted_at=datetime.now().isoformat(),
            external_tool_name=external_tool_name,
            overall_assessment=overall_assessment,
            engineer_comments=engineer_comments
        )
        
        # 处理差异记录
        if differences:
            for diff_data in differences:
                diff = self._create_difference_record(
                    project_id=project_id,
                    **diff_data
                )
                feedback.differences.append(diff)
                self.differences.append(diff)
        
        # 计算置信度
        feedback.confidence_level = self._calculate_confidence(feedback)
        
        # 保存反馈
        self.feedbacks.append(feedback)
        self._save_feedback(feedback)
        
        # 触发学习
        if feedback.differences:
            self._trigger_learning(feedback)
        
        # 调用回调
        if self.on_feedback_received:
            self.on_feedback_received(feedback)
        
        return feedback
    
    def upload_difference_report(
        self,
        project_id: str,
        package_id: str,
        report_file_path: str,
        submitted_by: str,
        external_tool_name: str = "EIAProA"
    ) -> VerificationFeedback:
        """
        上传差异报告文件
        
        支持的文件格式：.json, .xlsx, .csv, .pdf
        
        Args:
            project_id: 项目ID
            package_id: 关联的导出包ID
            report_file_path: 差异报告文件路径
            submitted_by: 提交人
            external_tool_name: 外部工具名称
        """
        # 解析差异报告
        differences = self._parse_difference_report(report_file_path)
        
        # 提交反馈
        return self.submit_feedback(
            project_id=project_id,
            package_id=package_id,
            source=FeedbackSource.EXTERNAL_TOOL,
            submitted_by=submitted_by,
            differences=differences,
            external_tool_name=external_tool_name
        )
    
    def auto_compare(
        self,
        project_id: str,
        system_results: Dict,
        external_results: Dict
    ) -> List[Dict]:
        """
        自动对比系统计算结果与外部结果
        
        Args:
            project_id: 项目ID
            system_results: 系统计算结果
            external_results: 外部工具计算结果
            
        Returns:
            差异列表
        """
        differences = []
        
        # 对比污染源参数
        system_sources = system_results.get("sources", [])
        external_sources = external_results.get("sources", [])
        
        for i, (sys_src, ext_src) in enumerate(zip(system_sources, external_sources)):
            # 对比排放速率
            sys_rate = sys_src.get("emission_rate", 0)
            ext_rate = ext_src.get("emission_rate", 0)
            
            if sys_rate != ext_rate:
                rel_diff = abs(sys_rate - ext_rate) / sys_rate if sys_rate else 0
                tolerance = self.tolerance_config.get("emission_rate", 0.01)
                
                diff = {
                    "data_item": f"sources[{i}].emission_rate",
                    "original_value": sys_rate,
                    "external_value": ext_rate,
                    "difference_type": DifferenceType.PARAMETER_MISMATCH.value if rel_diff > tolerance else DifferenceType.NEGLIGIBLE.value,
                    "severity": self._determine_severity(rel_diff, tolerance).value,
                    "tolerance": tolerance,
                    "relative_diff": rel_diff
                }
                differences.append(diff)
        
        # 对比计算结果
        sys_max = system_results.get("max_concentration", 0)
        ext_max = external_results.get("max_concentration", 0)
        
        if sys_max and ext_max:
            rel_diff = abs(sys_max - ext_max) / sys_max
            tolerance = self.tolerance_config.get("concentration", 0.05)
            
            diff = {
                "data_item": "max_concentration",
                "original_value": sys_max,
                "external_value": ext_max,
                "difference_type": DifferenceType.CALCULATION_METHOD.value if rel_diff > tolerance else DifferenceType.NEGLIGIBLE.value,
                "severity": self._determine_severity(rel_diff, tolerance).value,
                "tolerance": tolerance,
                "relative_diff": rel_diff
            }
            differences.append(diff)
        
        return differences
    
    def analyze_difference_cause(
        self,
        difference: DifferenceRecord,
        context: Dict = None
    ) -> str:
        """
        分析差异原因
        
        使用知识库和规则引擎分析差异的根本原因
        """
        causes = []
        
        # 检查参数不一致
        if difference.difference_type == DifferenceType.PARAMETER_MISMATCH:
            # 可能是数据录入错误
            if difference.relative_diff > 0.5:  # 差异超过50%
                causes.append("疑似数据录入错误，建议核查原始输入")
            
            # 检查知识库中是否有类似记录
            kb_record = self._check_knowledge_base(difference.data_item)
            if kb_record:
                causes.append(f"知识库提示：该参数通常应设置为{kb_record.get('suggested_value')}")
        
        # 检查模型设置差异
        elif difference.difference_type == DifferenceType.MODEL_SETTING_DIFF:
            causes.append("模型设置不一致，请检查是否使用了相同的参数配置")
            if context and context.get("model_version"):
                causes.append(f"版本差异可能影响：{context['model_version']}")
        
        # 检查边界条件
        elif difference.difference_type == DifferenceType.BOUNDARY_CONDITION:
            causes.append("边界条件差异可能导致计算结果不同")
            if context and context.get("terrain"):
                causes.append("地形条件：需确认是否考虑建筑物或地形影响")
        
        # 检查计算方法
        elif difference.difference_type == DifferenceType.CALCULATION_METHOD:
            causes.append("计算方法差异：不同软件可能使用不同的算法或近似方法")
            causes.append("建议：对比两种软件的计算文档，确认差异来源")
        
        return "；".join(causes) if causes else "原因不明，建议人工审核"
    
    def get_recommended_action(
        self,
        difference: DifferenceRecord
    ) -> str:
        """根据差异类型获取建议操作"""
        recommendations = {
            DifferenceType.PARAMETER_MISMATCH: "修正系统参数值，使用验证后的正确值",
            DifferenceType.MODEL_SETTING_DIFF: "统一模型设置，确保使用相同的配置",
            DifferenceType.BOUNDARY_CONDITION: "重新评估边界条件，确认适用性",
            DifferenceType.DATA_ENTRY_ERROR: "修正数据录入错误，更新知识库",
            DifferenceType.VERSION_INCOMPATIBILITY: "记录版本差异，在报告中说明",
            DifferenceType.CALCULATION_METHOD: "在报告中注明两种方法的差异及原因",
            DifferenceType.UNKNOWN: "建议工程师人工审核确认"
        }
        
        return recommendations.get(difference.difference_type, "建议人工审核")
    
    def resolve_difference(
        self,
        diff_id: str,
        resolution: str,
        resolved_by: str
    ) -> bool:
        """标记差异已解决"""
        for diff in self.differences:
            if diff.diff_id == diff_id:
                diff.is_resolved = True
                diff.resolution = resolution
                diff.resolved_by = resolved_by
                diff.resolved_at = datetime.now().isoformat()
                return True
        return False
    
    # ==================== 学习系统 ====================
    
    def _trigger_learning(self, feedback: VerificationFeedback):
        """触发系统学习"""
        for diff in feedback.differences:
            if diff.severity in [DifferenceSeverity.WARNING, DifferenceSeverity.CRITICAL]:
                # 分析原因
                diff.cause_analysis = self.analyze_difference_cause(diff)
                diff.recommended_action = self.get_recommended_action(diff)
                
                # 创建学习记录
                self._create_learning_record(feedback, diff)
                
                # 调用回调
                if self.on_learning_triggered:
                    self.on_learning_triggered(diff)
    
    def _create_learning_record(
        self,
        feedback: VerificationFeedback,
        difference: DifferenceRecord
    ) -> LearningRecord:
        """创建学习记录"""
        record_id = f"lr_{hashlib.md5((feedback.feedback_id + difference.diff_id).encode()).hexdigest()[:8]}"
        
        # 确定学习类别
        category = self._categorize_difference(difference)
        
        # 检查是否已有类似记录
        existing = self._find_existing_learning(category, difference.data_item)
        
        if existing:
            # 更新现有记录
            existing.trigger_count += 1
            existing.last_updated = datetime.now().isoformat()
            existing.source_projects.append(feedback.project_id)
            
            # 如果新值更优，更新知识库
            if self._is_better_value(difference):
                existing.new_value = difference.external_value
                existing.confidence = min(1.0, existing.confidence + 0.1)
            
            record = existing
        else:
            # 创建新记录
            record = LearningRecord(
                record_id=record_id,
                project_id=feedback.project_id,
                feedback_id=feedback.feedback_id,
                category=category,
                key=difference.data_item,
                old_value=difference.original_value,
                new_value=difference.external_value,
                trigger_count=1,
                confidence=0.3,
                created_at=datetime.now().isoformat(),
                last_updated=datetime.now().isoformat(),
                source_projects=[feedback.project_id]
            )
            self.learning_records.append(record)
        
        # 更新知识库
        self._update_knowledge_base(record)
        
        return record
    
    def _categorize_difference(self, difference: DifferenceRecord) -> str:
        """分类差异"""
        if "emission" in difference.data_item or "rate" in difference.data_item.lower():
            return "parameter"
        elif "model" in difference.data_item or "setting" in difference.data_item.lower():
            return "model_setting"
        elif "boundary" in difference.data_item or "terrain" in difference.data_item.lower():
            return "boundary_condition"
        elif "method" in difference.data_item or "algorithm" in difference.data_item.lower():
            return "calculation_method"
        else:
            return "other"
    
    def _find_existing_learning(self, category: str, key: str) -> Optional[LearningRecord]:
        """查找现有学习记录"""
        for record in self.learning_records:
            if record.category == category and record.key == key:
                return record
        return None
    
    def _is_better_value(self, difference: DifferenceRecord) -> bool:
        """判断新值是否更优"""
        # 这个逻辑需要根据具体场景定义
        # 例如：如果外部工具是经过验证的商业软件，其值可能更可靠
        return True  # 默认接受外部验证的值
    
    def _update_knowledge_base(self, record: LearningRecord):
        """更新知识库"""
        category = record.category
        
        if category == "parameter":
            if "parameter_adjustments" not in self.knowledge_base:
                self.knowledge_base["parameter_adjustments"] = {}
            self.knowledge_base["parameter_adjustments"][record.key] = {
                "suggested_value": record.new_value,
                "trigger_count": record.trigger_count,
                "confidence": record.confidence
            }
        
        elif category == "model_setting":
            if "model_settings" not in self.knowledge_base:
                self.knowledge_base["model_settings"] = {}
            self.knowledge_base["model_settings"][record.key] = {
                "recommended": record.new_value,
                "confidence": record.confidence
            }
        
        self._save_knowledge_base()
    
    def _check_knowledge_base(self, data_item: str) -> Optional[Dict]:
        """检查知识库中是否有相关提示"""
        adjustments = self.knowledge_base.get("parameter_adjustments", {})
        return adjustments.get(data_item)
    
    # ==================== 辅助方法 ====================
    
    def _generate_feedback_id(self, project_id: str) -> str:
        """生成反馈ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        raw = f"{project_id}_feedback_{timestamp}"
        short_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
        return f"fb_{short_hash}"
    
    def _create_difference_record(
        self,
        project_id: str,
        data_item: str,
        original_value: Any,
        external_value: Any,
        difference_type: str,
        severity: str = "warning",
        tolerance: float = 0.0,
        relative_diff: float = 0.0,
        feedback_source: str = "engineer",
        feedback_by: str = "",
        external_tool: str = ""
    ) -> DifferenceRecord:
        """创建差异记录"""
        diff_id = f"diff_{hashlib.md5((data_item + str(original_value)).encode()).hexdigest()[:8]}"
        
        return DifferenceRecord(
            diff_id=diff_id,
            project_id=project_id,
            data_item=data_item,
            original_value=original_value,
            external_value=external_value,
            difference_type=DifferenceType(difference_type),
            severity=DifferenceSeverity(severity),
            tolerance=tolerance,
            relative_diff=relative_diff,
            feedback_source=FeedbackSource(feedback_source),
            feedback_time=datetime.now().isoformat(),
            feedback_by=feedback_by,
            external_tool=external_tool
        )
    
    def _parse_difference_report(self, file_path: str) -> List[Dict]:
        """解析差异报告文件"""
        path = Path(file_path)
        
        if not path.exists():
            return []
        
        if path.suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("differences", [data])
        
        elif path.suffix in [".xlsx", ".csv"]:
            # 简化实现，实际需要pandas解析
            return []
        
        return []
    
    def _calculate_confidence(self, feedback: VerificationFeedback) -> float:
        """计算置信度"""
        if not feedback.differences:
            return 1.0  # 无差异，100%置信
        
        # 根据差异严重程度降低置信度
        critical_count = sum(1 for d in feedback.differences if d.severity == DifferenceSeverity.CRITICAL)
        warning_count = sum(1 for d in feedback.differences if d.severity == DifferenceSeverity.WARNING)
        
        confidence = 1.0
        confidence -= critical_count * 0.3
        confidence -= warning_count * 0.1
        
        return max(0.0, confidence)
    
    def _determine_severity(
        self,
        relative_diff: float,
        tolerance: float
    ) -> DifferenceSeverity:
        """判断严重程度"""
        if relative_diff > 0.5:
            return DifferenceSeverity.CRITICAL
        elif relative_diff > tolerance * 5:
            return DifferenceSeverity.WARNING
        elif relative_diff > tolerance:
            return DifferenceSeverity.INFO
        else:
            return DifferenceSeverity.NEGLIGIBLE
    
    def _save_feedback(self, feedback: VerificationFeedback):
        """保存反馈到文件"""
        feedback_dir = self.workspace_dir / "feedbacks"
        feedback_dir.mkdir(exist_ok=True)
        
        path = feedback_dir / f"{feedback.feedback_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(feedback.to_dict(), f, ensure_ascii=False, indent=2)
    
    # ==================== 查询方法 ====================
    
    def get_project_feedbacks(self, project_id: str) -> List[VerificationFeedback]:
        """获取项目的所有反馈"""
        return [f for f in self.feedbacks if f.project_id == project_id]
    
    def get_project_differences(self, project_id: str) -> List[DifferenceRecord]:
        """获取项目的所有差异"""
        return [d for d in self.differences if d.project_id == project_id]
    
    def get_unresolved_differences(self, project_id: str = None) -> List[DifferenceRecord]:
        """获取未解决的差异"""
        diffs = [d for d in self.differences if not d.is_resolved]
        if project_id:
            diffs = [d for d in diffs if d.project_id == project_id]
        return diffs
    
    def get_learning_records(
        self,
        category: str = None,
        min_confidence: float = 0.0
    ) -> List[LearningRecord]:
        """获取学习记录"""
        records = self.learning_records
        
        if category:
            records = [r for r in records if r.category == category]
        
        if min_confidence > 0:
            records = [r for r in records if r.confidence >= min_confidence]
        
        return records
    
    def get_knowledge_suggestions(self, data_item: str) -> List[Dict]:
        """获取知识库建议"""
        suggestions = []
        
        # 从参数调整中查找
        adjustments = self.knowledge_base.get("parameter_adjustments", {})
        if data_item in adjustments:
            suggestions.append({
                "type": "parameter",
                "value": adjustments[data_item]["suggested_value"],
                "confidence": adjustments[data_item]["confidence"]
            })
        
        # 从模型设置中查找
        settings = self.knowledge_base.get("model_settings", {})
        if data_item in settings:
            suggestions.append({
                "type": "model_setting",
                "value": settings[data_item]["recommended"],
                "confidence": settings[data_item]["confidence"]
            })
        
        return suggestions
    
    def generate_feedback_report(
        self,
        project_id: str,
        include_resolved: bool = False
    ) -> str:
        """生成反馈报告"""
        feedbacks = self.get_project_feedbacks(project_id)
        differences = self.get_project_differences(project_id)
        
        if not include_resolved:
            differences = [d for d in differences if not d.is_resolved]
        
        # 统计
        critical = sum(1 for d in differences if d.severity == DifferenceSeverity.CRITICAL)
        warning = sum(1 for d in differences if d.severity == DifferenceSeverity.WARNING)
        info = sum(1 for d in differences if d.severity == DifferenceSeverity.INFO)
        
        report = f"""
================================================================================
                        验证反馈报告
================================================================================

项目编号: {project_id}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

一、反馈统计
--------------------------------------------------------------------------------
总反馈数: {len(feedbacks)}
总差异数: {len(differences)}
  - 严重差异: {critical}
  - 警告差异: {warning}
  - 信息差异: {info}
未解决差异: {sum(1 for d in differences if not d.is_resolved)}

二、差异详情
--------------------------------------------------------------------------------
"""
        for i, diff in enumerate(differences, 1):
            status = "✓ 已解决" if diff.is_resolved else "✗ 未解决"
            report += f"""
[{i}] {diff.data_item}
    类型: {diff.difference_type.value}
    严重程度: {diff.severity.value}
    系统值: {diff.original_value}
    外部值: {diff.external_value}
    相对差异: {diff.relative_diff*100:.2f}%
    状态: {status}
"""
            if diff.cause_analysis:
                report += f"    原因分析: {diff.cause_analysis}\n"
            if diff.recommended_action:
                report += f"    建议操作: {diff.recommended_action}\n"
        
        report += """
三、知识库学习
--------------------------------------------------------------------------------
"""
        learning = self.get_learning_records(min_confidence=0.3)
        for record in learning:
            report += f"""
- {record.category}: {record.key}
  旧值: {record.old_value} → 新值: {record.new_value}
  置信度: {record.confidence*100:.0f}% | 触发次数: {record.trigger_count}
"""
        
        report += """
================================================================================
"""
        return report


# ==================== 工厂函数 ====================

def create_feedback_system(workspace_dir: str = None) -> VerificationFeedbackSystem:
    """创建验证反馈系统"""
    return VerificationFeedbackSystem(workspace_dir=workspace_dir)


# ==================== 便捷函数 ====================

def submit_engineer_feedback(
    project_id: str,
    package_id: str,
    submitted_by: str,
    differences: List[Dict] = None,
    engineer_comments: str = ""
) -> VerificationFeedback:
    """提交工程师反馈"""
    system = create_feedback_system()
    return system.submit_feedback(
        project_id=project_id,
        package_id=package_id,
        source=FeedbackSource.ENGINEER,
        submitted_by=submitted_by,
        differences=differences or [],
        engineer_comments=engineer_comments
    )


def upload_external_verification(
    project_id: str,
    package_id: str,
    report_file: str,
    submitted_by: str,
    tool_name: str = "EIAProA"
) -> VerificationFeedback:
    """上传外部工具验证结果"""
    system = create_feedback_system()
    return system.upload_difference_report(
        project_id=project_id,
        package_id=package_id,
        report_file_path=report_file,
        submitted_by=submitted_by,
        external_tool_name=tool_name
    )


def compare_and_learn(
    project_id: str,
    system_results: Dict,
    external_results: Dict
) -> VerificationFeedback:
    """自动对比并学习"""
    system = create_feedback_system()
    
    differences = system.auto_compare(project_id, system_results, external_results)
    
    if differences:
        feedback = system.submit_feedback(
            project_id=project_id,
            package_id="auto_compare",
            source=FeedbackSource.AUTOMATIC,
            submitted_by="system",
            differences=differences,
            overall_assessment="自动对比分析"
        )
        return feedback
    
    return None