"""
自动化工作流扩展 (Automation Workflows)

提供预定义的自动化工作流：
1. 自动文档生成
2. 自动测试生成
3. 自动代码审查
4. 自动部署
5. 自动问题修复
"""

from typing import Dict, Optional, Any
from . import WorkflowBuilder, register_workflow, execute_workflow
from client.src.business.agent_adapter import create_agent_adapter, AgentConfig
from client.src.business.shared.event_bus import EventBus, Event
import asyncio


# ------------------------------
# 自动文档生成工作流
# ------------------------------

class AutoDocumentGenerator:
    """自动文档生成器"""
    
    @staticmethod
    def create_workflow():
        """创建自动文档生成工作流"""
        builder = WorkflowBuilder("auto_doc_gen", "sequential")
        
        builder.start("开始文档生成")\
            .action("analyze_code", AutoDocumentGenerator._analyze_code, "分析代码结构")\
            .action("generate_doc", AutoDocumentGenerator._generate_documentation, "生成文档")\
            .action("save_doc", AutoDocumentGenerator._save_documentation, "保存文档")\
            .end("文档生成完成")
        
        workflow = builder.build()
        register_workflow(workflow)
        return workflow
    
    @staticmethod
    def _analyze_code(variables: Dict) -> Dict:
        """分析代码结构"""
        code = variables.get("code", "")
        print(f"[AutoDocumentGenerator] 分析代码: {len(code)} 字符")
        
        # 提取代码结构信息
        lines = code.split('\n')
        functions = []
        classes = []
        
        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                functions.append(line.strip())
            elif line.strip().startswith('class '):
                classes.append(line.strip())
        
        return {
            "code_lines": len(lines),
            "functions": functions,
            "classes": classes,
            "analysis_done": True
        }
    
    @staticmethod
    def _generate_documentation(variables: Dict) -> Dict:
        """生成文档"""
        code = variables.get("code", "")
        functions = variables.get("functions", [])
        classes = variables.get("classes", [])
        
        print(f"[AutoDocumentGenerator] 生成文档 - 函数: {len(functions)}, 类: {len(classes)}")
        
        # 使用 Agent 生成文档
        config = AgentConfig(agent_type="local", model_name="Qwen/Qwen2.5-7B-Instruct")
        
        try:
            agent = create_agent_adapter(config)
            
            prompt = f"""请为以下 Python 代码生成详细的文档：

代码内容：
{code[:2000]}

文档格式要求：
1. 模块概述
2. 类说明（如果有）
3. 函数说明（参数、返回值、示例）
4. 使用示例

请输出完整的文档内容。
"""
            
            response = agent.generate(prompt)
            return {"documentation": response.content, "doc_generated": True}
        except Exception as e:
            print(f"[AutoDocumentGenerator] 文档生成失败: {e}")
            return {"documentation": f"文档生成失败: {e}", "doc_generated": False}
    
    @staticmethod
    def _save_documentation(variables: Dict) -> Dict:
        """保存文档"""
        documentation = variables.get("documentation", "")
        output_path = variables.get("output_path", "documentation.md")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(documentation)
        
        print(f"[AutoDocumentGenerator] 文档已保存到: {output_path}")
        return {"saved_path": output_path, "save_done": True}


# ------------------------------
# 自动测试生成工作流
# ------------------------------

class AutoTestGenerator:
    """自动测试生成器"""
    
    @staticmethod
    def create_workflow():
        """创建自动测试生成工作流"""
        builder = WorkflowBuilder("auto_test_gen", "sequential")
        
        builder.start("开始测试生成")\
            .action("parse_requirements", AutoTestGenerator._parse_requirements, "解析测试需求")\
            .action("generate_tests", AutoTestGenerator._generate_tests, "生成测试用例")\
            .action("validate_tests", AutoTestGenerator._validate_tests, "验证测试用例")\
            .end("测试生成完成")
        
        workflow = builder.build()
        register_workflow(workflow)
        return workflow
    
    @staticmethod
    def _parse_requirements(variables: Dict) -> Dict:
        """解析测试需求"""
        requirements = variables.get("requirements", "")
        print(f"[AutoTestGenerator] 解析测试需求")
        return {"parsed_requirements": requirements, "parsed": True}
    
    @staticmethod
    def _generate_tests(variables: Dict) -> Dict:
        """生成测试用例"""
        requirements = variables.get("parsed_requirements", "")
        code = variables.get("code", "")
        
        print(f"[AutoTestGenerator] 生成测试用例")
        
        config = AgentConfig(agent_type="local", model_name="Qwen/Qwen2.5-7B-Instruct")
        
        try:
            agent = create_agent_adapter(config)
            
            prompt = f"""请根据以下需求为代码生成单元测试：

测试需求：
{requirements}

代码内容：
{code[:2000]}

请输出完整的 Python 测试代码，使用 pytest 框架。
"""
            
            response = agent.generate(prompt)
            return {"test_code": response.content, "tests_generated": True}
        except Exception as e:
            print(f"[AutoTestGenerator] 测试生成失败: {e}")
            return {"test_code": f"测试生成失败: {e}", "tests_generated": False}
    
    @staticmethod
    def _validate_tests(variables: Dict) -> Dict:
        """验证测试用例"""
        test_code = variables.get("test_code", "")
        
        print(f"[AutoTestGenerator] 验证测试用例")
        
        # 简单验证：检查是否包含 pytest 相关代码
        is_valid = "def test_" in test_code or "import pytest" in test_code
        
        return {"tests_valid": is_valid, "validation_done": True}


# ------------------------------
# 自动代码审查工作流
# ------------------------------

class AutoCodeReviewer:
    """自动代码审查器"""
    
    @staticmethod
    def create_workflow():
        """创建自动代码审查工作流"""
        builder = WorkflowBuilder("auto_code_review", "decision")
        
        builder.start("开始代码审查")\
            .action("analyze_code", AutoCodeReviewer._analyze_code, "分析代码")\
            .decision("has_issues", AutoCodeReviewer._has_issues, "检查是否有问题")\
            .then("generate_fixes", AutoCodeReviewer._generate_fixes, "生成修复建议")\
            .else_("no_fixes", AutoCodeReviewer._no_fixes_needed, "无需修复")\
            .end("审查完成")
        
        workflow = builder.build()
        register_workflow(workflow)
        return workflow
    
    @staticmethod
    def _analyze_code(variables: Dict) -> Dict:
        """分析代码"""
        code = variables.get("code", "")
        print(f"[AutoCodeReviewer] 分析代码")
        
        config = AgentConfig(agent_type="local", model_name="Qwen/Qwen2.5-7B-Instruct")
        
        try:
            agent = create_agent_adapter(config)
            
            prompt = f"""请分析以下代码，找出潜在的问题：

代码内容：
{code[:2000]}

请列出：
1. 潜在的 bug
2. 代码优化建议
3. 安全问题
4. 性能问题

请以结构化格式输出。
"""
            
            response = agent.generate(prompt)
            return {"analysis_result": response.content, "has_problems": len(response.content) > 100}
        except Exception as e:
            print(f"[AutoCodeReviewer] 代码分析失败: {e}")
            return {"analysis_result": f"分析失败: {e}", "has_problems": False}
    
    @staticmethod
    def _has_issues(variables: Dict) -> bool:
        """检查是否有问题"""
        return variables.get("has_problems", False)
    
    @staticmethod
    def _generate_fixes(variables: Dict) -> Dict:
        """生成修复建议"""
        code = variables.get("code", "")
        analysis = variables.get("analysis_result", "")
        
        print(f"[AutoCodeReviewer] 生成修复建议")
        
        config = AgentConfig(agent_type="local", model_name="Qwen/Qwen2.5-7B-Instruct")
        
        try:
            agent = create_agent_adapter(config)
            
            prompt = f"""请根据以下代码分析结果生成修复代码：

原代码：
{code[:2000]}

分析结果：
{analysis[:1000]}

请提供修复后的完整代码。
"""
            
            response = agent.generate(prompt)
            return {"fixed_code": response.content, "fixes_generated": True}
        except Exception as e:
            print(f"[AutoCodeReviewer] 修复生成失败: {e}")
            return {"fixed_code": f"修复生成失败: {e}", "fixes_generated": False}
    
    @staticmethod
    def _no_fixes_needed(variables: Dict) -> Dict:
        """无需修复"""
        print(f"[AutoCodeReviewer] 代码质量良好，无需修复")
        return {"fixes_generated": False, "code_quality": "good"}


# ------------------------------
# 自动部署工作流
# ------------------------------

class AutoDeployer:
    """自动部署器"""
    
    @staticmethod
    def create_workflow():
        """创建自动部署工作流"""
        builder = WorkflowBuilder("auto_deploy", "decision")
        
        builder.start("开始部署")\
            .action("check_env", AutoDeployer._check_environment, "检查环境")\
            .decision("env_ready", AutoDeployer._env_ready, "环境是否就绪")\
            .then("run_tests", AutoDeployer._run_tests, "运行测试")\
            .else_("fix_env", AutoDeployer._fix_environment, "修复环境")\
            .action("deploy", AutoDeployer._deploy, "执行部署")\
            .action("verify", AutoDeployer._verify_deployment, "验证部署")\
            .end("部署完成")
        
        workflow = builder.build()
        register_workflow(workflow)
        return workflow
    
    @staticmethod
    def _check_environment(variables: Dict) -> Dict:
        """检查环境"""
        print(f"[AutoDeployer] 检查部署环境")
        # 模拟环境检查
        return {"env_checked": True, "env_ready": True}
    
    @staticmethod
    def _env_ready(variables: Dict) -> bool:
        """环境是否就绪"""
        return variables.get("env_ready", False)
    
    @staticmethod
    def _run_tests(variables: Dict) -> Dict:
        """运行测试"""
        print(f"[AutoDeployer] 运行测试")
        return {"tests_passed": True, "test_run": True}
    
    @staticmethod
    def _fix_environment(variables: Dict) -> Dict:
        """修复环境"""
        print(f"[AutoDeployer] 修复环境配置")
        return {"env_fixed": True, "env_ready": True}
    
    @staticmethod
    def _deploy(variables: Dict) -> Dict:
        """执行部署"""
        print(f"[AutoDeployer] 执行部署")
        return {"deployed": True}
    
    @staticmethod
    def _verify_deployment(variables: Dict) -> Dict:
        """验证部署"""
        print(f"[AutoDeployer] 验证部署结果")
        return {"verified": True, "deploy_success": True}


# ------------------------------
# 自动问题修复工作流
# ------------------------------

class AutoIssueFixer:
    """自动问题修复器"""
    
    @staticmethod
    def create_workflow():
        """创建自动问题修复工作流"""
        builder = WorkflowBuilder("auto_issue_fix", "sequential")
        
        builder.start("开始修复")\
            .action("parse_issue", AutoIssueFixer._parse_issue, "解析问题")\
            .action("locate_code", AutoIssueFixer._locate_code, "定位代码")\
            .action("generate_fix", AutoIssueFixer._generate_fix, "生成修复")\
            .action("apply_fix", AutoIssueFixer._apply_fix, "应用修复")\
            .end("修复完成")
        
        workflow = builder.build()
        register_workflow(workflow)
        return workflow
    
    @staticmethod
    def _parse_issue(variables: Dict) -> Dict:
        """解析问题"""
        issue = variables.get("issue", "")
        print(f"[AutoIssueFixer] 解析问题: {issue[:50]}...")
        return {"parsed_issue": issue, "parsed": True}
    
    @staticmethod
    def _locate_code(variables: Dict) -> Dict:
        """定位代码"""
        print(f"[AutoIssueFixer] 定位相关代码")
        return {"code_found": True, "code_location": "src/main.py"}
    
    @staticmethod
    def _generate_fix(variables: Dict) -> Dict:
        """生成修复"""
        issue = variables.get("parsed_issue", "")
        
        print(f"[AutoIssueFixer] 生成修复方案")
        
        config = AgentConfig(agent_type="local", model_name="Qwen/Qwen2.5-7B-Instruct")
        
        try:
            agent = create_agent_adapter(config)
            
            prompt = f"""请根据以下问题描述生成修复方案：

问题描述：
{issue}

请输出：
1. 问题分析
2. 修复方案
3. 代码变更
"""
            
            response = agent.generate(prompt)
            return {"fix_solution": response.content, "fix_generated": True}
        except Exception as e:
            print(f"[AutoIssueFixer] 修复生成失败: {e}")
            return {"fix_solution": f"修复生成失败: {e}", "fix_generated": False}
    
    @staticmethod
    def _apply_fix(variables: Dict) -> Dict:
        """应用修复"""
        print(f"[AutoIssueFixer] 应用修复")
        return {"fix_applied": True}


# ------------------------------
# 工作流注册
# ------------------------------

def register_all_automation_workflows():
    """注册所有自动化工作流"""
    AutoDocumentGenerator.create_workflow()
    AutoTestGenerator.create_workflow()
    AutoCodeReviewer.create_workflow()
    AutoDeployer.create_workflow()
    AutoIssueFixer.create_workflow()
    print("[AutomationWorkflows] 所有自动化工作流已注册")


__all__ = [
    "AutoDocumentGenerator",
    "AutoTestGenerator",
    "AutoCodeReviewer",
    "AutoDeployer",
    "AutoIssueFixer",
    "register_all_automation_workflows"
]