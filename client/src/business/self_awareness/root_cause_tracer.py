"""
根因追踪器
分析问题产生的根本原因
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import re
import ast
import traceback
from pathlib import Path


@dataclass
class RootCause:
    """根因分析"""
    cause_type: str  # 'syntax' | 'import' | 'logic' | 'performance' | 'config'
    description: str
    confidence: float  # 0.0 - 1.0
    evidence: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    related_files: List[str] = field(default_factory=list)
    

class RootCauseTracer:
    """
    根因追踪器
    
    功能：
    1. 分析错误堆栈
    2. 追踪问题根源
    3. 生成修复建议
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
    def trace(self, error: Exception, 
              code_context: Optional[Dict[str, Any]] = None) -> RootCause:
        """
        追踪根因
        
        Args:
            error: 异常对象
            code_context: 代码上下文
            
        Returns:
            RootCause: 根因分析
        """
        error_type = type(error).__name__
        
        # 根据异常类型分析
        if isinstance(error, SyntaxError):
            return self._trace_syntax_error(error)
        elif isinstance(error, ImportError):
            return self._trace_import_error(error)
        elif isinstance(error, (NameError, AttributeError)):
            return self._trace_name_error(error)
        elif isinstance(error, (TypeError, ValueError)):
            return self._trace_type_error(error)
        elif isinstance(error, (IndexError, KeyError)):
            return self._trace_index_error(error)
        else:
            return self._trace_generic_error(error)
            
    def _trace_syntax_error(self, error: SyntaxError) -> RootCause:
        """追踪语法错误"""
        evidence = []
        suggested_fix = None
        
        if error.text:
            evidence.append(f"错误行: {error.text}")
            
        # 分析常见语法问题
        if error.msg:
            if 'invalid syntax' in error.msg.lower():
                suggested_fix = "检查语法是否正确，确保括号、引号配对"
            elif 'unexpected EOF' in error.msg.lower():
                suggested_fix = "代码未完整，可能缺少闭合括号或引号"
                
        return RootCause(
            cause_type='syntax',
            description=f"语法错误: {error.msg}",
            confidence=0.9,
            evidence=evidence,
            suggested_fix=suggested_fix or "检查并修复语法错误"
        )
        
    def _trace_import_error(self, error: ImportError) -> RootCause:
        """追踪导入错误"""
        evidence = [f"缺失模块: {error.name}"]
        suggested_fix = f"安装缺失模块: pip install {error.name}"
        
        # 检查是否是自定义模块
        if error.name and not error.name.startswith('_'):
            # 检查项目中是否存在该模块
            project_root = self.config.get('project_root', '.')
            module_path = Path(project_root) / f"{error.name.replace('.', '/')}.py"
            
            if module_path.exists():
                evidence.append(f"模块存在但可能路径不对: {module_path}")
                suggested_fix = f"检查 sys.path 或相对导入"
                
        return RootCause(
            cause_type='import',
            description=f"导入错误: {error.msg}",
            confidence=0.85,
            evidence=evidence,
            suggested_fix=suggested_fix,
        )
        
    def _trace_name_error(self, error: Exception) -> RootCause:
        """追踪名称错误"""
        error_msg = str(error)
        evidence = [f"错误详情: {error_msg}"]
        
        # 提取未定义的名称
        name_match = re.search(r"name '(\w+)' is not defined", error_msg)
        if name_match:
            undefined_name = name_match.group(1)
            evidence.append(f"未定义名称: {undefined_name}")
            suggested_fix = f"定义变量 '{undefined_name}' 或检查拼写"
        else:
            suggested_fix = "检查变量名拼写和作用域"
            
        return RootCause(
            cause_type='logic',
            description=f"名称错误: {error_msg}",
            confidence=0.8,
            evidence=evidence,
            suggested_fix=suggested_fix,
        )
        
    def _trace_type_error(self, error: Exception) -> RootCause:
        """追踪类型错误"""
        error_msg = str(error)
        
        return RootCause(
            cause_type='logic',
            description=f"类型错误: {error_msg}",
            confidence=0.7,
            evidence=[f"错误详情: {error_msg}"],
            suggested_fix="检查函数参数类型和返回值类型"
        )
        
    def _trace_index_error(self, error: Exception) -> RootCause:
        """追踪索引错误"""
        return RootCause(
            cause_type='logic',
            description=f"索引/键错误: {str(error)}",
            confidence=0.8,
            evidence=[str(error)],
            suggested_fix="添加边界检查或使用 .get() 方法"
        )
        
    def _trace_generic_error(self, error: Exception) -> RootCause:
        """追踪通用错误"""
        return RootCause(
            cause_type='unknown',
            description=f"未知错误: {type(error).__name__}: {str(error)}",
            confidence=0.5,
            evidence=[traceback.format_exc()],
            suggested_fix="查看详细堆栈信息以定位问题"
        )
        
    def analyze_code(self, code: str, 
                   problem_type: str) -> Optional[RootCause]:
        """
        分析代码找出问题根因
        
        Args:
            code: 代码字符串
            problem_type: 问题类型
            
        Returns:
            RootCause or None
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None
            
        if 'null' in problem_type.lower() or 'none' in problem_type.lower():
            # 查找可能的空指针问题
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # 检查函数调用是否可能返回None
                    if isinstance(node.func, ast.Name):
                        if 'get' in node.func.id.lower():
                            return RootCause(
                                cause_type='logic',
                                description="可能未处理None返回值",
                                confidence=0.6,
                                evidence=[f"函数调用: {node.func.id}"],
                                suggested_fix="添加None检查"
                            )
                            
        return None
        
    def generate_fix_suggestion(self, root_cause: RootCause) -> str:
        """生成修复建议"""
        if root_cause.suggested_fix:
            return root_cause.suggested_fix
            
        # 根据根因类型生成建议
        suggestions = {
            'syntax': "检查并修复语法错误，确保括号、引号配对正确",
            'import': "安装缺失的模块或检查导入路径",
            'logic': "检查代码逻辑，添加必要的条件判断和错误处理",
            'performance': "优化算法复杂度，减少不必要的计算",
            'config': "检查配置文件格式和内容是否正确",
        }
        
        return suggestions.get(root_cause.cause_type, "查看详细错误信息")
