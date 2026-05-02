"""
SICA (Self-Improving Coding Agent) 核心引擎

实现代码生成、优化和自我改进能力。
"""
import ast
import json
import logging
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from ..global_model_router import GlobalModelRouter

logger = logging.getLogger(__name__)


@dataclass
class CodeGenerationResult:
    """代码生成结果"""
    success: bool
    code: str = ""
    test_code: str = ""
    explanation: str = ""
    confidence: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    """测试结果"""
    success: bool
    passed_tests: int = 0
    failed_tests: int = 0
    errors: List[str] = field(default_factory=list)
    output: str = ""


class SICACodeGenerator:
    """
    SICA代码生成器
    
    核心能力：
    1. 根据需求描述生成Python代码
    2. 自动生成单元测试
    3. 执行代码并收集反馈
    4. 基于失败进行自我改进
    """
    
    def __init__(self):
        self.model_router = GlobalModelRouter.get_instance()
        self.max_iterations = 5
        self.test_timeout = 30
    
    async def generate_code(
        self,
        task_description: str,
        requirements: Optional[Dict[str, Any]] = None,
        existing_code: Optional[str] = None,
    ) -> CodeGenerationResult:
        """
        生成代码的主入口
        
        Args:
            task_description: 任务描述
            requirements: 额外需求（如输入输出格式、性能要求等）
            existing_code: 现有代码（用于改进）
        
        Returns:
            CodeGenerationResult
        """
        logger.info(f"Generating code for task: {task_description[:50]}...")
        
        # 构建提示词
        prompt = self._build_code_prompt(task_description, requirements, existing_code)
        
        # 调用模型生成代码
        try:
            response = await self.model_router.generate(
                prompt=prompt,
                model_type="code",
                max_tokens=4000,
            )
            
            if not response or not response.content:
                return CodeGenerationResult(
                    success=False,
                    errors=["模型生成失败"]
                )
            
            # 解析生成的代码
            code, test_code = self._parse_generated_code(response.content)
            
            # 验证代码语法
            syntax_errors = self._validate_syntax(code)
            if syntax_errors:
                return CodeGenerationResult(
                    success=False,
                    code=code,
                    test_code=test_code,
                    errors=syntax_errors
                )
            
            # 如果有测试代码，执行测试
            if test_code:
                test_result = self._run_tests(code, test_code)
                if not test_result.success:
                    # 尝试自我修复
                    return await self._self_improve(
                        task_description,
                        code,
                        test_code,
                        test_result.errors
                    )
            
            return CodeGenerationResult(
                success=True,
                code=code,
                test_code=test_code,
                explanation=response.content if "解释" in response.content else "",
                confidence=0.9
            )
        
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return CodeGenerationResult(
                success=False,
                errors=[str(e)]
            )
    
    def _build_code_prompt(self, task_description: str, requirements: Optional[Dict], existing_code: Optional[str]) -> str:
        """构建代码生成提示词"""
        prompt_parts = [
            "你是一个专业的Python代码生成器。请根据以下要求生成高质量的Python代码。\n",
            "要求：\n",
            "1. 代码必须符合PEP8规范\n",
            "2. 必须包含详细的类型注解\n",
            "3. 必须包含单元测试（使用pytest）\n",
            "4. 代码结构清晰，有适当的注释\n",
            "5. 如果涉及计算逻辑，请提供数学公式说明\n",
            "\n任务描述：\n",
            f"{task_description}\n",
        ]
        
        if requirements:
            prompt_parts.append("\n额外需求：\n")
            for key, value in requirements.items():
                prompt_parts.append(f"- {key}: {value}\n")
        
        if existing_code:
            prompt_parts.append("\n现有代码（请改进）：\n")
            prompt_parts.append(f"```python\n{existing_code}\n```\n")
        
        prompt_parts.append("\n输出格式：\n")
        prompt_parts.append("```python\n")
        prompt_parts.append("# 主要代码\n")
        prompt_parts.append("```\n")
        prompt_parts.append("\n```python\n")
        prompt_parts.append("# 单元测试\n")
        prompt_parts.append("```\n")
        
        return "".join(prompt_parts)
    
    def _parse_generated_code(self, content: str) -> Tuple[str, str]:
        """解析生成的代码，分离主代码和测试代码"""
        code = ""
        test_code = ""
        
        # 查找代码块
        import re
        code_blocks = re.findall(r"```(python)?\s*(.*?)\s*```", content, re.DOTALL)
        
        for lang, block in code_blocks:
            if "# 单元测试" in block or "def test_" in block or "class Test" in block:
                test_code = block.strip()
            else:
                code = block.strip()
        
        # 如果没有找到代码块，尝试直接提取
        if not code:
            code = content.strip()
        
        return code, test_code
    
    def _validate_syntax(self, code: str) -> List[str]:
        """验证Python代码语法"""
        errors = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"语法错误: {e.msg} 在第 {e.lineno} 行")
        except Exception as e:
            errors.append(f"代码验证失败: {str(e)}")
        return errors
    
    def _run_tests(self, code: str, test_code: str) -> TestResult:
        """运行单元测试"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 写入主代码文件
            code_path = Path(tmp_dir) / "main.py"
            with open(code_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            # 写入测试文件
            test_path = Path(tmp_dir) / "test_main.py"
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_code)
            
            # 运行测试
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", str(test_path), "-v"],
                    capture_output=True,
                    text=True,
                    timeout=self.test_timeout,
                    cwd=tmp_dir
                )
                
                # 解析测试结果
                passed = 0
                failed = 0
                errors = []
                
                for line in result.stdout.split("\n"):
                    if "PASSED" in line:
                        passed += 1
                    elif "FAILED" in line:
                        failed += 1
                        errors.append(line.strip())
                
                if result.returncode != 0 or failed > 0:
                    return TestResult(
                        success=False,
                        passed_tests=passed,
                        failed_tests=failed,
                        errors=errors,
                        output=result.stdout + result.stderr
                    )
                
                return TestResult(
                    success=True,
                    passed_tests=passed,
                    failed_tests=failed,
                    output=result.stdout
                )
            
            except subprocess.TimeoutExpired:
                return TestResult(
                    success=False,
                    errors=["测试超时"],
                    output="测试执行超时"
                )
            except Exception as e:
                return TestResult(
                    success=False,
                    errors=[str(e)],
                    output=str(e)
                )
    
    async def _self_improve(
        self,
        task_description: str,
        code: str,
        test_code: str,
        errors: List[str],
        iteration: int = 1
    ) -> CodeGenerationResult:
        """
        自我改进循环
        
        根据测试失败反馈，自动修复代码。
        """
        if iteration > self.max_iterations:
            return CodeGenerationResult(
                success=False,
                code=code,
                test_code=test_code,
                errors=errors,
                warnings=["达到最大迭代次数"]
            )
        
        logger.info(f"Self-improvement iteration {iteration}/{self.max_iterations}")
        
        # 构建改进提示词
        prompt = self._build_improvement_prompt(task_description, code, test_code, errors)
        
        try:
            response = await self.model_router.generate(
                prompt=prompt,
                model_type="code",
                max_tokens=4000,
            )
            
            if not response or not response.content:
                return CodeGenerationResult(
                    success=False,
                    code=code,
                    test_code=test_code,
                    errors=errors + ["改进生成失败"]
                )
            
            # 解析改进后的代码
            new_code, new_test_code = self._parse_generated_code(response.content)
            
            # 验证语法
            syntax_errors = self._validate_syntax(new_code)
            if syntax_errors:
                return await self._self_improve(
                    task_description,
                    new_code,
                    new_test_code or test_code,
                    syntax_errors,
                    iteration + 1
                )
            
            # 运行测试
            test_result = self._run_tests(new_code, new_test_code or test_code)
            
            if test_result.success:
                return CodeGenerationResult(
                    success=True,
                    code=new_code,
                    test_code=new_test_code or test_code,
                    explanation=f"经过 {iteration} 次自我改进后成功",
                    confidence=0.85 + (iteration * 0.03)
                )
            
            # 继续改进
            return await self._self_improve(
                task_description,
                new_code,
                new_test_code or test_code,
                test_result.errors,
                iteration + 1
            )
        
        except Exception as e:
            logger.error(f"Self-improvement failed: {e}")
            return CodeGenerationResult(
                success=False,
                code=code,
                test_code=test_code,
                errors=errors + [str(e)]
            )
    
    def _build_improvement_prompt(self, task_description: str, code: str, test_code: str, errors: List[str]) -> str:
        """构建代码改进提示词"""
        return f"""
你是一个专业的代码修复工程师。请根据测试失败信息修复以下Python代码。

任务描述：
{task_description}

现有代码：
```python
{code}
```

单元测试：
```python
{test_code}
```

测试失败信息：
{chr(10).join(errors)}

请分析失败原因并提供修复后的完整代码。

输出格式：
```python
# 修复后的代码
```

```python
# 更新后的单元测试（如果需要）
```
"""
    
    async def generate_financial_model(self, model_type: str, parameters: Dict[str, Any]) -> CodeGenerationResult:
        """
        生成金融模型代码
        
        Args:
            model_type: 模型类型（npv, irr, sensitivity, monte_carlo等）
            parameters: 模型参数
        
        Returns:
            CodeGenerationResult
        """
        descriptions = {
            "npv": "生成净现值(NPV)计算函数，支持折现率、现金流输入",
            "irr": "生成内部收益率(IRR)计算函数",
            "sensitivity": "生成敏感性分析函数，分析关键变量变化对结果的影响",
            "monte_carlo": "生成蒙特卡洛模拟函数，进行风险分析",
        }
        
        description = descriptions.get(model_type, f"生成{model_type}金融模型")
        return await self.generate_code(description, parameters)
    
    async def generate_eia_calculator(self, pollutant_type: str, formula: str) -> CodeGenerationResult:
        """
        生成环评计算代码
        
        Args:
            pollutant_type: 污染物类型
            formula: 计算公式描述
        
        Returns:
            CodeGenerationResult
        """
        description = f"""
生成一个{pollutant_type}排放量计算工具。

计算公式要求：
{formula}

要求：
1. 包含详细的类型注解
2. 包含输入验证
3. 生成单元测试
4. 提供计算结果的不确定性分析
"""
        return await self.generate_code(description)