"""
测试 CrewAI 集成

测试内容：
1. CrewAIAgentAdapter - CrewAI Agent 适配为 BaseTool
2. TaskDecomposer 增强 - 三种 Process 模式
3. ChainOfThoughtExecutor 增强 - 支持三种执行流程
"""

import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_crewai_adapter():
    """测试 CrewAIAgentAdapter"""
    print("\n=== 测试 CrewAIAgentAdapter ===\n")
    
    try:
        from client.src.business.multi_agent.crewai_adapter import (
            CrewAIAgentAdapter,
            convert_crewai_agent_to_tool
        )
        
        # 检查 CrewAI 是否安装
        try:
            import crewai
            print(f"✓ CrewAI version: {crewai.__version__}")
        except ImportError:
            print("✗ CrewAI not installed. Please install with: pip install crewai")
            return False
        except AttributeError:
            print(f"✓ CrewAI installed")
        
        # 测试1: 创建 CrewAIAgentAdapter
        print("\n[测试1] 创建 CrewAIAgentAdapter...")
        try:
            adapter = CrewAIAgentAdapter(
                name="test_researcher",
                role="Research Analyst",
                goal="Research and analyze information",
                backstory="Expert at finding and analyzing data",
                verbose=True
            )
            
            print(f"✓ Adapter created: {adapter.name}")
            print(f"  Role: {adapter.role}")
            print(f"  Goal: {adapter.goal}")
        except Exception as e:
            print(f"✗ Failed to create adapter: {e}")
            return False
        
        # 测试2: 从配置创建
        print("\n[测试2] 从配置创建 Adapter...")
        try:
            config = {
                "name": "test_writer",
                "role": "Technical Writer",
                "goal": "Write clear documentation",
                "backstory": "Experienced technical writer"
            }
            
            adapter2 = CrewAIAgentAdapter.create_from_config(config)
            
            print(f"✓ Adapter created from config: {adapter2.name}")
        except Exception as e:
            print(f"✗ Failed to create from config: {e}")
            return False
        
        # 测试3: 快速转换函数
        print("\n[测试3] 快速转换函数...")
        try:
            quick_adapter = convert_crewai_agent_to_tool(
                role="Data Scientist",
                goal="Analyze data and build models",
                backstory="PhD in Machine Learning"
            )
            
            print(f"✓ Quick adapter created: {quick_adapter.name}")
        except Exception as e:
            print(f"✗ Failed to create quick adapter: {e}")
            return False
        
        print("\n✓ CrewAIAgentAdapter 基础测试通过\n")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crewai_crew_adapter():
    """测试 CrewAICrewAdapter"""
    print("\n=== 测试 CrewAICrewAdapter ===\n")
    
    try:
        from client.src.business.multi_agent.crewai_adapter import (
            CrewAIAgentAdapter,
            CrewAICrewAdapter
        )
        
        # 测试1: 创建 Sequential Crew
        print("[测试1] 创建 Sequential Crew...")
        try:
            # 创建 Agent
            researcher = CrewAIAgentAdapter(
                name="researcher",
                role="Researcher",
                goal="Research information",
                backstory="Expert researcher"
            )
            
            writer = CrewAIAgentAdapter(
                name="writer",
                role="Writer",
                goal="Write reports",
                backstory="Experienced writer"
            )
            
            # 任务配置
            tasks_config = [
                {
                    "description": "Research the latest AI trends",
                    "expected_output": "List of AI trends",
                    "agent_index": 0
                },
                {
                    "description": "Write a report based on research",
                    "expected_output": "Comprehensive report",
                    "agent_index": 1
                }
            ]
            
            # 创建 Crew
            crew = CrewAICrewAdapter.create_sequential_crew(
                name="research_crew",
                agents_config=[
                    {"name": "researcher", "role": "Researcher", "goal": "Research", "backstory": "Expert"},
                    {"name": "writer", "role": "Writer", "goal": "Write", "backstory": "Experienced"}
                ],
                tasks_config=tasks_config,
                verbose=True
            )
            
            print(f"✓ Sequential Crew created: {crew.name}")
            print(f"  Process: {crew.process}")
            print(f"  Agents: {len(crew.agents)}")
        except Exception as e:
            print(f"✗ Failed to create Sequential Crew: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n✓ CrewAICrewAdapter 基础测试通过\n")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_decomposer_enhanced():
    """测试增强的 TaskDecomposer（三种 Process 模式）"""
    print("\n=== 测试增强的 TaskDecomposer（三种 Process 模式）===\n")
    
    try:
        from client.src.business.task_decomposer import (
            TaskDecomposer,
            ChainOfThoughtExecutor,
            ProcessType,
            create_sequential_task,
            create_hierarchical_task,
            create_parallel_task
        )
        
        # 模拟 LLM 调用
        def mock_llm(prompt: str) -> str:
            time.sleep(0.1)  # 模拟延迟
            return f"[Mock LLM Response to: {prompt[:50]}...]"
        
        # 测试1: Sequential Process
        print("[测试1] Sequential Process...")
        try:
            task1 = create_sequential_task(
                question="分析人工智能对教育的影响",
                task_type="analysis"
            )
            
            print(f"✓ Sequential task created")
            print(f"  Task ID: {task1.task_id}")
            print(f"  Process Type: {task1.process_type.value}")
            print(f"  Steps: {task1.total_steps}")
            
            # 执行
            executor = ChainOfThoughtExecutor(
                llm_callable=mock_llm,
                process_type=ProcessType.SEQUENTIAL
            )
            
            result = executor.execute(task1)
            
            print(f"  Completed: {result.completed_steps}/{result.total_steps}")
        except Exception as e:
            print(f"✗ Sequential Process failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 测试2: Hierarchical Process
        print("\n[测试2] Hierarchical Process...")
        try:
            task2 = create_hierarchical_task(
                question="选择最适合的机器学习算法",
                task_type="decision"
            )
            
            print(f"✓ Hierarchical task created")
            print(f"  Task ID: {task2.task_id}")
            print(f"  Process Type: {task2.process_type.value}")
            print(f"  Steps: {task2.total_steps}")
            
            # 执行（需要 Manager LLM）
            def mock_manager_llm(prompt: str) -> str:
                import json
                # 模拟 Manager 返回执行计划
                plan = {
                    "execution_order": [s.step_id for s in task2.steps],
                    "instructions": {},
                    "validate_results": False
                }
                return json.dumps(plan)
            
            executor = ChainOfThoughtExecutor(
                llm_callable=mock_llm,
                process_type=ProcessType.HIERARCHICAL,
                manager_llm=mock_manager_llm
            )
            
            result = executor.execute(task2)
            
            print(f"  Completed: {result.completed_steps}/{result.total_steps}")
        except Exception as e:
            print(f"✗ Hierarchical Process failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 测试3: Parallel Process
        print("\n[测试3] Parallel Process...")
        try:
            task3 = create_parallel_task(
                question="设计高可用系统架构",
                task_type="design"
            )
            
            print(f"✓ Parallel task created")
            print(f"  Task ID: {task3.task_id}")
            print(f"  Process Type: {task3.process_type.value}")
            print(f"  Steps: {task3.total_steps}")
            
            # 标记一些步骤为异步
            for step in task3.steps:
                if step.step_id in ["research", "detail"]:
                    step.async_execution = True
            
            # 执行
            executor = ChainOfThoughtExecutor(
                llm_callable=mock_llm,
                process_type=ProcessType.PARALLEL
            )
            
            result = executor.execute(task3)
            
            print(f"  Completed: {result.completed_steps}/{result.total_steps}")
        except Exception as e:
            print(f"✗ Parallel Process failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n✓ TaskDecomposer 增强测试通过（三种 Process 模式）\n")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_process_type_detection():
    """测试 Process 类型自动检测"""
    print("\n=== 测试 Process 类型自动检测 ===\n")
    
    try:
        from client.src.business.task_decomposer import TaskDecomposer, ProcessType
        
        decomposer = TaskDecomposer()
        
        # 测试不同任务类型的默认 Process
        test_cases = [
            ("分析人工智能发展趋势", "analysis", ProcessType.SEQUENTIAL),
            ("设计一个推荐系统架构", "design", ProcessType.HIERARCHICAL),
            ("写一份项目总结报告", "writing", ProcessType.SEQUENTIAL),
            ("选择最适合的部署方案", "decision", ProcessType.HIERARCHICAL),
            ("解释什么是区块链", "general", ProcessType.SEQUENTIAL)
        ]
        
        for question, expected_type, expected_process in test_cases:
            task = decomposer.decompose(question)
            
            print(f"问题: {question}")
            print(f"  任务类型: {task.metadata.get('task_type')}")
            print(f"  Process 类型: {task.process_type.value}")
            
            if task.process_type == expected_process:
                print(f"  ✓ 符合预期")
            else:
                print(f"  ✗ 不符合预期（期望: {expected_process.value}）")
        
        print("\n✓ Process 类型自动检测测试完成\n")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("="*60)
    print("CrewAI 集成测试")
    print("="*60)
    
    results = []
    
    # 运行测试
    results.append(("CrewAIAgentAdapter", test_crewai_adapter()))
    results.append(("CrewAICrewAdapter", test_crewai_crew_adapter()))
    results.append(("TaskDecomposer 增强（三种 Process）", test_task_decomposer_enhanced()))
    results.append(("Process 类型自动检测", test_process_type_detection()))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "-"*60)
    print(f"总计: {passed + failed} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print("-"*60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
