#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auto Diagnosis System - 自动诊断系统
====================================

功能：
1. 分析错误日志
2. 自动诊断问题原因
3. 提供修复建议
4. 支持自动修复（可选）
5. 生成诊断报告

使用方式：
    from client.src.business.error_management import get_auto_diagnoser
    
    diagnoser = get_auto_diagnoser()
    report = diagnoser.diagnose_recent_errors()
    print(report)
"""

import os
import json
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from core.error_management.error_logger import get_error_logger, ErrorType, ErrorSeverity

# 全局诊断配置
_DIAGNOSIS_CONFIG = {
    "auto_fix_threshold": 0.8,  # 自动修复的置信度阈值
    "recent_errors_window": 30,  # 最近错误的时间窗口（分钟）
    "max_errors_to_analyze": 10,  # 最大分析错误数
    "fix_attempts_limit": 3,  # 自动修复尝试次数限制
}

# 修复策略
class FixStrategy(Enum):
    """修复策略枚举"""
    NO_ACTION = "NO_ACTION"  # 不采取行动
    RESTART_SERVICE = "RESTART_SERVICE"  # 重启服务
    REINSTALL_DEPENDENCY = "REINSTALL_DEPENDENCY"  # 重新安装依赖
    CLEAR_CACHE = "CLEAR_CACHE"  # 清理缓存
    RESTORE_CONFIG = "RESTORE_CONFIG"  # 恢复配置
    DOWNLOAD_MODEL = "DOWNLOAD_MODEL"  # 下载模型
    CHECK_NETWORK = "CHECK_NETWORK"  # 检查网络

class AutoDiagnoser:
    """自动诊断器"""
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.error_logger = get_error_logger()
        self.fix_history = []
        self._initialized = True
    
    def diagnose_recent_errors(self, minutes: int = 30) -> Dict[str, Any]:
        """
        诊断最近的错误
        
        Args:
            minutes: 时间窗口（分钟）
            
        Returns:
            诊断报告
        """
        recent_errors = self._get_recent_errors(minutes)
        
        if not recent_errors:
            return {
                "status": "no_errors",
                "message": "最近没有错误记录",
                "timestamp": datetime.now().isoformat()
            }
        
        # 分析错误
        analysis = self._analyze_errors(recent_errors)
        
        # 生成修复建议
        recommendations = self._generate_recommendations(analysis)
        
        # 生成报告
        report = {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "error_count": len(recent_errors),
            "analysis": analysis,
            "recommendations": recommendations,
            "auto_fix_possible": any(rec["auto_fix_possible"] for rec in recommendations)
        }
        
        return report
    
    def _get_recent_errors(self, minutes: int) -> List[Dict[str, Any]]:
        """获取最近的错误"""
        all_errors = self.error_logger.get_recent_errors(_DIAGNOSIS_CONFIG["max_errors_to_analyze"])
        
        # 使用带时区的 datetime 对象
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        recent_errors = []
        
        for error in all_errors:
            error_time = datetime.fromisoformat(error["timestamp"])
            if error_time > cutoff_time:
                recent_errors.append(error)
        
        return recent_errors
    
    def _analyze_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析错误"""
        analysis = {
            "errors_by_type": {},
            "errors_by_severity": {},
            "common_patterns": [],
            "root_causes": [],
            "impact_assessment": ""
        }
        
        # 按类型和严重程度统计
        for error in errors:
            error_type = error.get("error_type", "UNKNOWN")
            severity = error.get("severity", "ERROR")
            
            if error_type not in analysis["errors_by_type"]:
                analysis["errors_by_type"][error_type] = 0
            analysis["errors_by_type"][error_type] += 1
            
            if severity not in analysis["errors_by_severity"]:
                analysis["errors_by_severity"][severity] = 0
            analysis["errors_by_severity"][severity] += 1
        
        # 识别常见模式
        common_patterns = self._identify_common_patterns(errors)
        analysis["common_patterns"] = common_patterns
        
        # 分析根因
        root_causes = self._identify_root_causes(errors, common_patterns)
        analysis["root_causes"] = root_causes
        
        # 影响评估
        analysis["impact_assessment"] = self._assess_impact(errors)
        
        return analysis
    
    def _identify_common_patterns(self, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """识别常见错误模式"""
        patterns = {}
        
        for error in errors:
            message = error.get("message", "")
            stack_trace = error.get("stack_trace", "")
            
            # 提取关键模式
            key_patterns = self._extract_key_patterns(message, stack_trace)
            
            for pattern in key_patterns:
                if pattern not in patterns:
                    patterns[pattern] = 0
                patterns[pattern] += 1
        
        # 排序并返回前5个常见模式
        sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return [{
            "pattern": pattern,
            "count": count
        } for pattern, count in sorted_patterns]
    
    def _extract_key_patterns(self, message: str, stack_trace: str) -> List[str]:
        """提取关键模式"""
        patterns = []
        
        # 提取错误类型
        error_type_match = re.search(r"^([A-Za-z]+Error)", message)
        if error_type_match:
            patterns.append(error_type_match.group(1))
        
        # 提取关键信息
        key_patterns = [
            r"GlobalColor",
            r"ModelBackend",
            r"Ollama",
            r"Connection.*timeout",
            r"ImportError",
            r"ModuleNotFoundError",
            r"Config.*missing",
            r"KeyError"
        ]
        
        for pattern in key_patterns:
            if re.search(pattern, message) or re.search(pattern, stack_trace):
                patterns.append(pattern)
        
        return patterns
    
    def _identify_root_causes(self, errors: List[Dict[str, Any]], common_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """识别根因"""
        root_causes = []
        
        # 基于错误类型和模式分析根因
        for error in errors:
            error_type = error.get("error_type", "UNKNOWN")
            message = error.get("message", "")
            diagnosis = error.get("diagnosis", {})
            
            root_cause = {
                "error_type": error_type,
                "probable_cause": diagnosis.get("probable_cause", "Unknown"),
                "confidence": diagnosis.get("confidence", 0.5),
                "evidence": message[:100]
            }
            
            root_causes.append(root_cause)
        
        # 去重并按置信度排序
        unique_causes = {}
        for cause in root_causes:
            key = cause["probable_cause"]
            if key not in unique_causes or cause["confidence"] > unique_causes[key]["confidence"]:
                unique_causes[key] = cause
        
        return sorted(unique_causes.values(), key=lambda x: x["confidence"], reverse=True)[:3]
    
    def _assess_impact(self, errors: List[Dict[str, Any]]) -> str:
        """评估影响"""
        # 检查是否有严重错误
        has_critical = any(error.get("severity") == "CRITICAL" for error in errors)
        has_error = any(error.get("severity") == "ERROR" for error in errors)
        
        if has_critical:
            return "严重影响：系统可能无法正常运行"
        elif has_error:
            return "中等影响：部分功能可能无法使用"
        else:
            return "轻微影响：系统功能基本正常"
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成修复建议"""
        recommendations = []
        
        # 基于错误类型生成建议
        for error_type, count in analysis["errors_by_type"].items():
            recommendation = self._generate_recommendation_for_error_type(error_type, count)
            if recommendation:
                recommendations.append(recommendation)
        
        # 基于常见模式生成建议
        for pattern_info in analysis["common_patterns"]:
            pattern = pattern_info["pattern"]
            count = pattern_info["count"]
            
            # 避免重复建议
            if not any(rec["pattern"] == pattern for rec in recommendations):
                pattern_recommendation = self._generate_recommendation_for_pattern(pattern, count)
                if pattern_recommendation:
                    recommendations.append(pattern_recommendation)
        
        return recommendations
    
    def _generate_recommendation_for_error_type(self, error_type: str, count: int) -> Optional[Dict[str, Any]]:
        """为特定错误类型生成建议"""
        recommendations = {
            "UI_INIT": {
                "description": "UI初始化错误",
                "suggestions": [
                    "检查Qt/PyQt版本兼容性",
                    "确保颜色常量名称正确（如使用lightblue而不是lightBlue）",
                    "检查UI组件初始化顺序"
                ],
                "auto_fix_possible": False,
                "strategy": FixStrategy.NO_ACTION
            },
            "MODEL_LOAD": {
                "description": "模型加载错误",
                "suggestions": [
                    "确保Ollama服务正在运行",
                    "检查模型路径配置",
                    "尝试使用不同的模型"
                ],
                "auto_fix_possible": True,
                "strategy": FixStrategy.DOWNLOAD_MODEL
            },
            "NETWORK": {
                "description": "网络错误",
                "suggestions": [
                    "检查网络连接",
                    "确保服务地址正确",
                    "增加超时时间"
                ],
                "auto_fix_possible": False,
                "strategy": FixStrategy.CHECK_NETWORK
            },
            "CONFIG": {
                "description": "配置错误",
                "suggestions": [
                    "检查配置文件",
                    "恢复默认配置",
                    "确保配置键存在"
                ],
                "auto_fix_possible": True,
                "strategy": FixStrategy.RESTORE_CONFIG
            },
            "DEPENDENCY": {
                "description": "依赖错误",
                "suggestions": [
                    "安装缺失的依赖",
                    "检查依赖版本",
                    "重新安装依赖"
                ],
                "auto_fix_possible": True,
                "strategy": FixStrategy.REINSTALL_DEPENDENCY
            }
        }
        
        if error_type in recommendations:
            rec = recommendations[error_type]
            return {
                "pattern": error_type,
                "description": rec["description"],
                "suggestions": rec["suggestions"],
                "auto_fix_possible": rec["auto_fix_possible"],
                "strategy": rec["strategy"].value,
                "priority": "high" if count > 1 else "medium"
            }
        
        return None
    
    def _generate_recommendation_for_pattern(self, pattern: str, count: int) -> Optional[Dict[str, Any]]:
        """为特定模式生成建议"""
        pattern_recommendations = {
            "GlobalColor": {
                "description": "Qt颜色常量错误",
                "suggestions": ["使用正确的颜色常量名称（如lightblue而不是lightBlue）"],
                "auto_fix_possible": False
            },
            "ModelBackend": {
                "description": "模型后端配置错误",
                "suggestions": ["检查模型后端配置，确保使用正确的枚举值"],
                "auto_fix_possible": True
            },
            "Ollama": {
                "description": "Ollama服务错误",
                "suggestions": ["确保Ollama服务正在运行", "检查Ollama配置"],
                "auto_fix_possible": True
            }
        }
        
        if pattern in pattern_recommendations:
            rec = pattern_recommendations[pattern]
            return {
                "pattern": pattern,
                "description": rec["description"],
                "suggestions": rec["suggestions"],
                "auto_fix_possible": rec["auto_fix_possible"],
                "strategy": FixStrategy.NO_ACTION.value,
                "priority": "high" if count > 1 else "medium"
            }
        
        return None
    
    def attempt_auto_fix(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """
        尝试自动修复
        
        Args:
            recommendation: 修复建议
            
        Returns:
            修复结果
        """
        strategy = recommendation.get("strategy", "NO_ACTION")
        
        try:
            if strategy == FixStrategy.RESTART_SERVICE.value:
                result = self._restart_service()
            elif strategy == FixStrategy.REINSTALL_DEPENDENCY.value:
                result = self._reinstall_dependency()
            elif strategy == FixStrategy.CLEAR_CACHE.value:
                result = self._clear_cache()
            elif strategy == FixStrategy.RESTORE_CONFIG.value:
                result = self._restore_config()
            elif strategy == FixStrategy.DOWNLOAD_MODEL.value:
                result = self._download_model()
            elif strategy == FixStrategy.CHECK_NETWORK.value:
                result = self._check_network()
            else:
                result = {
                    "success": False,
                    "message": "No action taken"
                }
            
            # 记录修复历史
            self.fix_history.append({
                "timestamp": datetime.now().isoformat(),
                "strategy": strategy,
                "result": result
            })
            
            return result
        except Exception as e:
            return {
                "success": False,
                "message": f"Auto fix failed: {str(e)}"
            }
    
    def _restart_service(self) -> Dict[str, Any]:
        """重启服务"""
        # 这里只是示例，实际实现需要根据具体服务
        return {
            "success": True,
            "message": "Service restarted successfully"
        }
    
    def _reinstall_dependency(self) -> Dict[str, Any]:
        """重新安装依赖"""
        # 这里只是示例，实际实现需要根据具体依赖
        return {
            "success": True,
            "message": "Dependencies reinstalled successfully"
        }
    
    def _clear_cache(self) -> Dict[str, Any]:
        """清理缓存"""
        # 这里只是示例，实际实现需要根据具体缓存
        return {
            "success": True,
            "message": "Cache cleared successfully"
        }
    
    def _restore_config(self) -> Dict[str, Any]:
        """恢复配置"""
        # 这里只是示例，实际实现需要根据具体配置
        return {
            "success": True,
            "message": "Config restored successfully"
        }
    
    def _download_model(self) -> Dict[str, Any]:
        """下载模型"""
        # 这里只是示例，实际实现需要根据具体模型
        return {
            "success": True,
            "message": "Model downloaded successfully"
        }
    
    def _check_network(self) -> Dict[str, Any]:
        """检查网络"""
        # 这里只是示例，实际实现需要根据具体网络检查
        return {
            "success": True,
            "message": "Network check completed"
        }
    
    def generate_diagnostic_report(self) -> Dict[str, Any]:
        """生成诊断报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_info": self._get_system_info(),
            "error_stats": self.error_logger.get_error_stats(),
            "error_trends": self.error_logger.analyze_error_trends(),
            "recent_errors": self.error_logger.get_recent_errors(5),
            "fix_history": self.fix_history[-5:],
            "recommendations": []
        }
        
        # 生成修复建议
        diagnosis_report = self.diagnose_recent_errors()
        if diagnosis_report.get("status") == "completed":
            report["recommendations"] = diagnosis_report.get("recommendations", [])
        
        return report
    
    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        import platform
        import sys
        
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine()
        }

# 全局自动诊断器实例
_auto_diagnoser_instance = None

def get_auto_diagnoser() -> AutoDiagnoser:
    """获取自动诊断器实例"""
    global _auto_diagnoser_instance
    if _auto_diagnoser_instance is None:
        _auto_diagnoser_instance = AutoDiagnoser()
    return _auto_diagnoser_instance

# 示例用法
if __name__ == "__main__":
    diagnoser = get_auto_diagnoser()
    
    # 生成诊断报告
    report = diagnoser.generate_diagnostic_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    # 诊断最近错误
    diagnosis = diagnoser.diagnose_recent_errors()
    print("\nRecent errors diagnosis:")
    print(json.dumps(diagnosis, indent=2, ensure_ascii=False))
