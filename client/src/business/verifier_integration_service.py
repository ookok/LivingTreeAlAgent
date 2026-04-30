"""
验证器集成服务 (Verifier Integration Service)
=============================================

参考: llm-as-a-verifier.notion.site

将LLM验证器与系统深度集成：
1. 代码验证 - 验证生成的代码
2. 逻辑验证 - 验证推理过程
3. 内容验证 - 验证回答内容
4. 安全验证 - 检测安全问题
5. 输出验证 - 验证模型输出

核心特性：
- 自动验证管道
- 多维度验证
- 智能修复建议
- 置信度评估
- 实时验证监控

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = __import__('logging').getLogger(__name__)


@dataclass
class VerificationPipeline:
    """验证管道"""
    name: str
    verifications: List[str] = field(default_factory=list)
    enabled: bool = True


class VerifierIntegrationService:
    """
    验证器集成服务
    
    统一管理系统中的验证功能，提供：
    1. 多维度验证
    2. 验证管道管理
    3. 自动修复建议
    4. 验证监控
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 验证器实例（延迟加载）
        self._verifier = None
        
        # 验证管道
        self._pipelines: Dict[str, VerificationPipeline] = {
            "code_generation": VerificationPipeline(
                name="代码生成",
                verifications=["code", "security"],
            ),
            "response_validation": VerificationPipeline(
                name="响应验证",
                verifications=["content", "output"],
            ),
            "reasoning_validation": VerificationPipeline(
                name="推理验证",
                verifications=["logic", "content"],
            ),
            "security_scan": VerificationPipeline(
                name="安全扫描",
                verifications=["security"],
            ),
        }
        
        # 验证统计
        self._stats = {
            "total_verifications": 0,
            "passed": 0,
            "warnings": 0,
            "failed": 0,
            "avg_confidence": 0.0,
        }
        
        # 验证历史
        self._history: List[Dict[str, Any]] = []
        
        self._initialized = True
        logger.info("[VerifierIntegrationService] 验证器集成服务初始化完成")
    
    def _lazy_load_verifier(self):
        """延迟加载验证器"""
        if self._verifier is None:
            from client.src.business.llm_verifier import create_llm_verifier
            self._verifier = create_llm_verifier()
    
    async def verify_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        验证代码
        
        Args:
            code: 代码内容
            language: 编程语言
            
        Returns:
            验证结果
        """
        self._lazy_load_verifier()
        
        if self._verifier:
            report = self._verifier.verify_code(code, language)
            self._update_stats(report)
            self._add_to_history("code", report)
            
            return self._report_to_dict(report)
        
        return {"success": False, "message": "验证器未初始化"}
    
    async def verify_logic(self, reasoning: str, conclusion: str) -> Dict[str, Any]:
        """
        验证逻辑
        
        Args:
            reasoning: 推理过程
            conclusion: 结论
            
        Returns:
            验证结果
        """
        self._lazy_load_verifier()
        
        if self._verifier:
            report = self._verifier.verify_logic(reasoning, conclusion)
            self._update_stats(report)
            self._add_to_history("logic", report)
            
            return self._report_to_dict(report)
        
        return {"success": False, "message": "验证器未初始化"}
    
    async def verify_content(self, content: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        验证内容
        
        Args:
            content: 内容
            context: 上下文
            
        Returns:
            验证结果
        """
        self._lazy_load_verifier()
        
        if self._verifier:
            report = self._verifier.verify_content(content, context)
            self._update_stats(report)
            self._add_to_history("content", report)
            
            return self._report_to_dict(report)
        
        return {"success": False, "message": "验证器未初始化"}
    
    async def verify_security(self, content: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        安全验证
        
        Args:
            content: 待验证内容
            context: 上下文
            
        Returns:
            验证结果
        """
        self._lazy_load_verifier()
        
        if self._verifier:
            report = self._verifier.verify_security(content, context)
            self._update_stats(report)
            self._add_to_history("security", report)
            
            return self._report_to_dict(report)
        
        return {"success": False, "message": "验证器未初始化"}
    
    async def verify_output(self, output: str, expected: Optional[str] = None) -> Dict[str, Any]:
        """
        验证输出
        
        Args:
            output: 实际输出
            expected: 期望输出
            
        Returns:
            验证结果
        """
        self._lazy_load_verifier()
        
        if self._verifier:
            report = self._verifier.verify_output(output, expected)
            self._update_stats(report)
            self._add_to_history("output", report)
            
            return self._report_to_dict(report)
        
        return {"success": False, "message": "验证器未初始化"}
    
    async def run_pipeline(self, pipeline_name: str, **kwargs) -> Dict[str, Any]:
        """
        运行验证管道
        
        Args:
            pipeline_name: 管道名称
            kwargs: 验证参数
            
        Returns:
            验证结果
        """
        pipeline = self._pipelines.get(pipeline_name)
        
        if not pipeline or not pipeline.enabled:
            return {"success": False, "message": f"管道 {pipeline_name} 不存在或未启用"}
        
        results = {}
        overall_result = "pass"
        
        for verification_type in pipeline.verifications:
            if verification_type == "code":
                result = await self.verify_code(kwargs.get("code", ""), kwargs.get("language", "python"))
            elif verification_type == "logic":
                result = await self.verify_logic(kwargs.get("reasoning", ""), kwargs.get("conclusion", ""))
            elif verification_type == "content":
                result = await self.verify_content(kwargs.get("content", ""), kwargs.get("context"))
            elif verification_type == "security":
                result = await self.verify_security(kwargs.get("content", ""), kwargs.get("context"))
            elif verification_type == "output":
                result = await self.verify_output(kwargs.get("output", ""), kwargs.get("expected"))
            
            results[verification_type] = result
            
            # 更新总体结果
            if result.get("overall_result") in ["warning", "fail", "error"]:
                if overall_result == "pass":
                    overall_result = "warning"
                if result.get("overall_result") == "fail":
                    overall_result = "fail"
        
        return {
            "success": True,
            "pipeline": pipeline_name,
            "overall_result": overall_result,
            "results": results,
        }
    
    def enable_pipeline(self, pipeline_name: str):
        """启用验证管道"""
        if pipeline_name in self._pipelines:
            self._pipelines[pipeline_name].enabled = True
            logger.info(f"[VerifierIntegrationService] 启用验证管道: {pipeline_name}")
    
    def disable_pipeline(self, pipeline_name: str):
        """禁用验证管道"""
        if pipeline_name in self._pipelines:
            self._pipelines[pipeline_name].enabled = False
            logger.info(f"[VerifierIntegrationService] 禁用验证管道: {pipeline_name}")
    
    def get_pipelines(self) -> Dict[str, VerificationPipeline]:
        """获取所有验证管道"""
        return self._pipelines.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取验证统计"""
        return self._stats.copy()
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取验证历史"""
        return self._history[-limit:]
    
    def _update_stats(self, report):
        """更新统计信息"""
        self._stats["total_verifications"] += 1
        
        if report.overall_result.value == "pass":
            self._stats["passed"] += 1
        elif report.overall_result.value == "warning":
            self._stats["warnings"] += 1
        else:
            self._stats["failed"] += 1
        
        # 更新平均置信度
        self._stats["avg_confidence"] = (
            self._stats["avg_confidence"] * 0.9 + report.confidence * 0.1
        )
    
    def _add_to_history(self, verification_type: str, report):
        """添加到历史"""
        history_entry = {
            "type": verification_type,
            "result": report.overall_result.value,
            "confidence": report.confidence,
            "issues": len(report.issues),
            "timestamp": __import__('time').time(),
        }
        
        self._history.append(history_entry)
        
        # 限制历史长度
        if len(self._history) > 100:
            self._history = self._history[-100:]
    
    def _report_to_dict(self, report) -> Dict[str, Any]:
        """报告转字典"""
        # 生成报告文本
        report_text = self._generate_report_text(report)
        
        return {
            "success": True,
            "verification_type": report.verification_type.value,
            "overall_result": report.overall_result.value,
            "confidence": report.confidence,
            "issues": [
                {
                    "type": issue.type.value,
                    "result": issue.result.value,
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "location": issue.location,
                    "suggestion": issue.suggestion,
                    "confidence": issue.confidence,
                }
                for issue in report.issues
            ],
            "report": report_text,
        }
    
    def _generate_report_text(self, report) -> str:
        """生成报告文本"""
        lines = [f"验证报告 - {report.verification_type.value}"]
        lines.append("=" * 50)
        lines.append(f"总体结果: {report.overall_result.value}")
        lines.append(f"置信度: {report.confidence:.2f}")
        lines.append("")
        
        if report.issues:
            lines.append("问题列表:")
            for i, issue in enumerate(report.issues, 1):
                lines.append(f"{i}. [{issue.severity.value}] {issue.message}")
                if issue.location:
                    lines.append(f"     位置: {issue.location}")
                if issue.suggestion:
                    lines.append(f"     建议: {issue.suggestion}")
                lines.append("")
        
        return "\n".join(lines)


# 便捷函数
def get_verifier_integration_service() -> VerifierIntegrationService:
    """获取验证器集成服务单例"""
    return VerifierIntegrationService()


__all__ = [
    "VerificationPipeline",
    "VerifierIntegrationService",
    "get_verifier_integration_service",
]
