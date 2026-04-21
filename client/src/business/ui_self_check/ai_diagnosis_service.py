"""
AI诊断服务 - AIDiagnosisService
核心理念：通过AI能力进行深度根因分析和修复建议

功能：
1. 错误根因分析
2. 修复建议生成
3. 代码差分（Diff）生成
4. 文档链接推荐
5. 知识图谱关联
"""

import threading
import logging
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

from .context_collector import ErrorContext
from .reactive_error_analyzer import DiagnosisResult, ErrorSeverity

logger = logging.getLogger(__name__)


@dataclass
class AIDiagnosisResult:
    """AI诊断结果"""
    root_cause: str
    likely_causes: List[str]
    fix_suggestions: List[str]
    code_diff: Optional[str] = None
    doc_links: List[str] = None
    confidence: float = 0.0
    analysis_time_ms: float = 0.0


class AIDiagnosisService:
    """
    AI诊断服务

    提供智能诊断能力：
    1. 解析错误栈，定位源码
    2. 结合上下文分析根因
    3. 生成修复建议和代码
    4. 关联官方文档和社区方案
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._llm_callback: Optional[Callable] = None
        self._knowledge_base: Dict[str, List[str]] = {}  # 错误类型 -> 文档链接
        self._enabled = True
        self._diagnosis_count = 0
        self._avg_analysis_time = 0

    def set_llm_callback(self, callback: Callable):
        """
        设置LLM回调

        callback 接收 (ErrorContext) -> AIDiagnosisResult
        """
        self._llm_callback = callback

    def set_knowledge_base(self, kb: Dict[str, List[str]]):
        """设置知识库（错误类型 -> 文档链接）"""
        self._knowledge_base = kb

    def add_knowledge(self, error_type: str, doc_link: str):
        """添加知识条目"""
        if error_type not in self._knowledge_base:
            self._knowledge_base[error_type] = []
        if doc_link not in self._knowledge_base[error_type]:
            self._knowledge_base[error_type].append(doc_link)

    def diagnose(self, context: ErrorContext) -> AIDiagnosisResult:
        """
        执行AI诊断

        Args:
            context: 错误上下文

        Returns:
            AIDiagnosisResult
        """
        if not self._enabled:
            return None

        start_time = datetime.now()

        # 1. 调用LLM进行诊断
        if self._llm_callback:
            try:
                result = self._llm_callback(context)
                if result:
                    self._diagnosis_count += 1
                    return result
            except Exception as e:
                logger.error(f"LLM diagnosis failed: {e}")

        # 2. 使用本地知识库诊断
        result = self._local_diagnosis(context)

        # 计算分析时间
        analysis_time = (datetime.now() - start_time).total_seconds() * 1000
        result.analysis_time_ms = analysis_time

        # 更新平均时间
        self._avg_analysis_time = (
            (self._avg_analysis_time * (self._diagnosis_count - 1) + analysis_time)
            / self._diagnosis_count
        ) if self._diagnosis_count > 0 else analysis_time

        self._diagnosis_count += 1

        return result

    def _local_diagnosis(self, context: ErrorContext) -> AIDiagnosisResult:
        """本地诊断（基于规则和知识库）"""

        # 获取相关文档链接
        doc_links = self._knowledge_base.get(context.error_type, [])

        # 基础分析
        root_cause = self._analyze_root_cause(context)
        likely_causes = self._generate_likely_causes(context)
        fix_suggestions = self._generate_fix_suggestions(context)

        # 生成代码差分（简单场景）
        code_diff = self._generate_simple_diff(context)

        return AIDiagnosisResult(
            root_cause=root_cause,
            likely_causes=likely_causes,
            fix_suggestions=fix_suggestions,
            code_diff=code_diff,
            doc_links=doc_links,
            confidence=0.7  # 本地诊断置信度较低
        )

    def _analyze_root_cause(self, context: ErrorContext) -> str:
        """分析根因"""
        # 基于错误类型和消息进行简单分析
        msg = context.error_message.lower()

        if "connection" in msg:
            return "网络连接失败，可能是服务器未启动或网络被阻断"
        elif "timeout" in msg:
            return "请求超时，可能是网络延迟或服务端处理时间过长"
        elif "permission" in msg:
            return "权限不足，当前用户没有执行此操作的权限"
        elif "not found" in msg:
            return "资源不存在，请求的目标可能已被删除或移动"
        elif "memory" in msg:
            return "内存不足，可能存在内存泄漏或数据量过大"
        elif "disk" in msg:
            return "磁盘空间不足，无法写入更多数据"
        else:
            return f"{context.error_type}错误: {context.error_message[:50]}"

    def _generate_likely_causes(self, context: ErrorContext) -> List[str]:
        """生成可能原因"""
        causes = []
        error_type = context.error_type

        # 基于错误类型的常见原因
        cause_map = {
            "ConnectionError": [
                "服务端未启动或已关闭",
                "防火墙阻止了连接",
                "服务地址或端口配置错误",
                "网络代理设置不正确"
            ],
            "TimeoutError": [
                "网络连接不稳定",
                "服务端负载过高",
                "请求的数据量过大",
                "网络带宽不足"
            ],
            "PermissionError": [
                "当前用户权限不足",
                "文件或目录权限设置过于严格",
                "操作被安全策略阻止"
            ],
            "NotFoundError": [
                "请求的资源已被删除",
                "URL路径或资源ID错误",
                "资源已被移动到其他位置"
            ],
            "ValueError": [
                "传入的参数值不合法",
                "数据格式与预期不符",
                "缺少必需的参数"
            ],
            "TypeError": [
                "数据类型不匹配",
                "对非预期类型的对象进行了操作",
                "函数参数类型错误"
            ]
        }

        causes = cause_map.get(error_type, [
            "代码逻辑存在缺陷",
            "外部依赖服务异常",
            "配置参数错误"
        ])

        return causes[:3]  # 返回最多3个

    def _generate_fix_suggestions(self, context: ErrorContext) -> List[str]:
        """生成修复建议"""
        suggestions = []
        error_type = context.error_type

        if context.file_path:
            suggestions.append(f"检查源文件: {context.file_path}")
        if context.line_number:
            suggestions.append(f"查看第 {context.line_number} 行代码")

        # 基于错误类型的建议
        suggestion_map = {
            "ConnectionError": [
                "1. 确认服务端服务已启动",
                "2. 检查网络连接是否正常",
                "3. 验证防火墙设置"
            ],
            "TimeoutError": [
                "1. 增加请求超时时间",
                "2. 检查网络质量",
                "3. 优化服务端响应速度"
            ],
            "PermissionError": [
                "1. 使用管理员权限运行",
                "2. 修改文件/目录权限",
                "3. 联系管理员获取授权"
            ]
        }

        if error_type in suggestion_map:
            suggestions.extend(suggestion_map[error_type])
        else:
            suggestions.extend([
                "1. 查看详细错误日志",
                "2. 检查相关配置",
                "3. 尝试重启应用"
            ])

        return suggestions[:5]  # 最多5条

    def _generate_simple_diff(self, context: ErrorContext) -> Optional[str]:
        """生成代码差分（基于实际文件内容）"""
        import os

        if not context.file_path or not context.line_number:
            return None

        # 检查文件是否存在
        if not os.path.exists(context.file_path):
            return None

        try:
            # 读取源文件
            with open(context.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines or context.line_number > len(lines):
                return None

            # 获取错误行及上下文
            line_idx = context.line_number - 1
            start_idx = max(0, line_idx - 3)
            end_idx = min(len(lines), line_idx + 4)

            # 构建原始代码片段
            original_lines = []
            for i in range(start_idx, end_idx):
                marker = ">>> " if i == line_idx else "    "
                original_lines.append(f"{marker}{i+1:4d}: {lines[i].rstrip()}")

            original_code = "\n".join(original_lines)

            # 根据错误类型生成修复建议
            msg = context.error_message.lower()
            fix_suggestion = self._get_fix_for_error_type(msg, context)

            # 生成 unified diff 格式
            diff = f"""# 文件: {os.path.basename(context.file_path)}
# 错误位置: 第 {context.line_number} 行

--- a/{context.file_path}
+++ b/{context.file_path}
@@ -{start_idx+1},{end_idx-start_idx} +{start_idx+1},{end_idx-start_idx} @@

错误上下文:
{original_code}

{fix_suggestion}
"""
            return diff

        except Exception as e:
            logger.error(f"Failed to generate diff for {context.file_path}: {e}")
            return None

    def _get_fix_for_error_type(self, msg: str, context: ErrorContext) -> str:
        """根据错误类型获取修复建议"""
        # 提取错误信息中的具体内容
        error_detail = context.error_message

        if "indentationerror" in msg or " indent" in msg:
            return f"""修复建议:
- 检查缩进是否一致（使用空格而非Tab，或统一使用Tab）
- 建议使用4个空格作为标准缩进
- 在IDE中开启"显示空白字符"功能检查"""

        if "syntaxerror" in msg:
            return f"""修复建议:
- 检查语法错误: {error_detail[:100]}
- 确保括号、引号成对出现
- 检查是否有遗漏的逗号、冒号等符号"""

        if "nameerror" in msg:
            return f"""修复建议:
- 检查变量/函数名是否正确拼写
- 确保在使用前已导入所需的模块
- 检查是否存在作用域问题"""

        if "typeerror" in msg:
            return f"""修复建议:
- 检查数据类型是否匹配
- 确保操作符两边类型一致
- 使用 type() 检查实际类型"""

        if "attributeerror" in msg:
            return f"""修复建议:
- 检查对象是否有该属性/方法
- 确保已正确导入模块
- 检查是否对 None 调用了方法"""

        if "importerror" in msg or "modulenotfounderror" in msg:
            return f"""修复建议:
- 确认模块已正确安装 (pip install xxx)
- 检查模块名称拼写是否正确
- 检查 __init__.py 是否存在"""

        return f"""修复建议:
- 查看错误信息: {error_detail[:100]}
- 检查相关代码逻辑"""

    def enable(self):
        """启用"""
        self._enabled = True

    def disable(self):
        """禁用"""
        self._enabled = False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "diagnosis_count": self._diagnosis_count,
            "avg_analysis_time_ms": round(self._avg_analysis_time, 2),
            "knowledge_base_size": len(self._knowledge_base),
            "enabled": self._enabled
        }


# 全局单例
ai_diagnosis_service = AIDiagnosisService()
