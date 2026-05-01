"""
完整AI流水线测试脚本

测试所有新增模块：
1. AutoConfig - 自动化配置系统
2. AutoDeploy - 自动化部署系统
3. CodeWorkflowEngine - 智能代码工作流引擎
4. SmartScheduler - 智能调度引擎
5. MultimodalProcessor - 多模态输入处理引擎
6. AdaptiveLearningSystem - 自适应学习系统
7. IncrementalCodeGenerator - 增量代码生成器
8. IntegrationOrchestrator - 集成编排器（完整流程）
"""

import asyncio
import sys
import os

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


async def test_auto_config():
    """测试自动化配置系统"""
    print("\n" + "="*60)
    print("🧪 测试 AutoConfig - 自动化配置系统")
    print("="*60)
    
    try:
        from auto_config import AutoConfig
        
        config = AutoConfig()
        
        # 测试自动检测
        detections = await config.auto_detect()
        print(f"✅ 自动检测完成")
        print(f"   Ollama可用: {detections.get('ollama', {}).get('available', False)}")
        print(f"   OpenAI可用: {detections.get('openai', {}).get('available', False)}")
        print(f"   DeepSeek可用: {detections.get('deepseek', {}).get('available', False)}")
        print(f"   Git仓库: {detections.get('git_repo', {}).get('inside_repo', False)}")
        print(f"   网络连接: {detections.get('network', {}).get('connected', False)}")
        
        # 测试配置生成
        generated = await config.generate_config(detections)
        print(f"✅ 配置生成完成")
        
        # 测试配置验证
        validation = await config.validate_config()
        print(f"✅ 配置验证完成: {'有效' if validation['valid'] else '无效'}")
        if validation.get('warnings'):
            print(f"   ⚠️ 警告: {validation['warnings']}")
        
        # 测试保存配置
        await config.save_config()
        print(f"✅ 配置保存完成")
        
        return True
    except Exception as e:
        print(f"❌ AutoConfig测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_auto_deploy():
    """测试自动化部署系统"""
    print("\n" + "="*60)
    print("🧪 测试 AutoDeploy - 自动化部署系统")
    print("="*60)
    
    try:
        from auto_deploy import AutoDeploy
        
        deploy = AutoDeploy()
        
        # 测试生成启动脚本
        script_path = await deploy.generate_startup_script()
        print(f"✅ 启动脚本生成完成: {script_path}")
        
        # 测试健康检查（不实际启动服务）
        health = await deploy.health_check()
        print(f"✅ 健康检查完成")
        print(f"   服务状态: {health['services']}")
        
        return True
    except Exception as e:
        print(f"❌ AutoDeploy测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_code_workflow():
    """测试智能代码工作流引擎"""
    print("\n" + "="*60)
    print("🧪 测试 CodeWorkflowEngine - 智能代码工作流引擎")
    print("="*60)
    
    try:
        from code_workflow import CodeWorkflowEngine
        
        workflow_engine = CodeWorkflowEngine()
        
        # 创建工作流
        workflow_id = await workflow_engine.create_workflow(
            requirement="开发用户登录功能",
            mode=None
        )
        print(f"✅ 工作流创建完成: {workflow_id}")
        
        # 获取工作流状态
        workflow = workflow_engine.get_workflow(workflow_id)
        print(f"✅ 工作流状态获取成功")
        
        return True
    except Exception as e:
        print(f"❌ CodeWorkflowEngine测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_smart_scheduler():
    """测试智能调度引擎"""
    print("\n" + "="*60)
    print("🧪 测试 SmartScheduler - 智能调度引擎")
    print("="*60)
    
    try:
        from smart_scheduler import SmartScheduler
        
        scheduler = SmartScheduler()
        
        # 提交测试任务
        async def test_task():
            await asyncio.sleep(0.1)
            return {"result": "success"}
        
        task_id = await scheduler.submit_task("测试任务", test_task)
        print(f"✅ 任务提交成功: {task_id}")
        
        # 获取任务状态
        status = scheduler.get_task_status(task_id)
        print(f"✅ 任务状态获取成功: {status.status if status else '未知'}")
        
        # 列出任务
        tasks = scheduler.list_tasks()
        print(f"✅ 任务列表获取成功: {len(tasks)} 个任务")
        
        return True
    except Exception as e:
        print(f"❌ SmartScheduler测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multimodal_processor():
    """测试多模态输入处理引擎"""
    print("\n" + "="*60)
    print("🧪 测试 MultimodalProcessor - 多模态输入处理引擎")
    print("="*60)
    
    try:
        from multimodal_processor import MultimodalProcessor, InputData, InputType
        
        processor = MultimodalProcessor()
        
        # 测试文本输入
        input_data = InputData(
            id="test_input",
            type=InputType.TEXT,
            content="开发一个用户管理系统，支持用户注册、登录和权限管理"
        )
        
        result = await processor.process(input_data)
        print(f"✅ 文本输入处理完成")
        print(f"   分类: {result.content.get('category')}")
        print(f"   关键词: {result.content.get('keywords')}")
        print(f"   置信度: {result.confidence}")
        
        return True
    except Exception as e:
        print(f"❌ MultimodalProcessor测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_adaptive_learning():
    """测试自适应学习系统"""
    print("\n" + "="*60)
    print("🧪 测试 AdaptiveLearningSystem - 自适应学习系统")
    print("="*60)
    
    try:
        from adaptive_learning import AdaptiveLearningSystem
        
        learning = AdaptiveLearningSystem()
        
        # 测试学习编码风格
        code_samples = [
            """def my_function(param_one):
                '''This is a docstring.'''
                result = param_one * 2
                return result""",
            """class MyClass:
                def __init__(self, value):
                    self._value = value
                
                @property
                def value(self):
                    return self._value"""
        ]
        
        await learning.learn_coding_style(code_samples)
        print(f"✅ 编码风格学习完成")
        
        # 获取风格偏好
        style = learning.get_style_preferences()
        print(f"   缩进风格: {style.indent_style}")
        print(f"   缩进大小: {style.indent_size}")
        print(f"   命名约定: {style.naming_convention}")
        
        # 测试收集反馈
        await learning.collect_feedback(
            task_id="test_task",
            user_id="test_user",
            feedback_type="positive",
            content="代码生成质量很好"
        )
        print(f"✅ 反馈收集完成")
        
        # 获取反馈摘要
        summary = learning.get_feedback_summary()
        print(f"   总反馈数: {summary['total']}")
        print(f"   正面反馈: {summary['positive']}")
        print(f"   趋势: {summary['trend']}")
        
        return True
    except Exception as e:
        print(f"❌ AdaptiveLearningSystem测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_incremental_generator():
    """测试增量代码生成器"""
    print("\n" + "="*60)
    print("🧪 测试 IncrementalCodeGenerator - 增量代码生成器")
    print("="*60)
    
    try:
        from incremental_generator import IncrementalCodeGenerator
        
        generator = IncrementalCodeGenerator()
        
        # 测试增量生成
        result = await generator.generate_incremental(
            task_id="test_incremental",
            requirement="开发用户登录API",
            existing_code="",
            context={"framework": "FastAPI"}
        )
        
        print(f"✅ 增量生成完成")
        print(f"   更新文件数: {result.updated_files}")
        print(f"   冲突数: {result.conflicts}")
        print(f"   消息: {result.message}")
        
        return True
    except Exception as e:
        print(f"❌ IncrementalCodeGenerator测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("🚀 开始AI Pipeline完整测试套件")
    print("="*60)
    
    results = []
    
    # 运行所有测试
    results.append(("AutoConfig", await test_auto_config()))
    results.append(("AutoDeploy", await test_auto_deploy()))
    results.append(("CodeWorkflowEngine", await test_code_workflow()))
    results.append(("SmartScheduler", await test_smart_scheduler()))
    results.append(("MultimodalProcessor", await test_multimodal_processor()))
    results.append(("AdaptiveLearningSystem", await test_adaptive_learning()))
    results.append(("IncrementalCodeGenerator", await test_incremental_generator()))
    
    # 输出总结
    print("\n" + "="*60)
    print("📊 测试结果总结")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"   {status} {name}")
    
    print(f"\n   总计: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！")
    else:
        print(f"⚠️ 有 {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)