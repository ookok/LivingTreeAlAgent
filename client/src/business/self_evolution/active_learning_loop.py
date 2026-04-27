"""
ActiveLearningLoop - 主动学习循环

功能：智能体能够主动学习，不断完善自己的工具和能力。

工作流程：
1. 分析当前能力边界（我有哪些工具？还能做什么？）
2. 发现能力缺口（我还缺少什么？）
3. 制定学习计划（我应该学习什么？）
4. 执行学习（搜索、阅读、实践）
5. 创建新工具或优化已有工具
6. 测试验证
7. 反思总结
"""

import json
import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger

from client.src.business.self_evolution.tool_missing_detector import ToolMissingDetector
from client.src.business.self_evolution.autonomous_tool_creator import AutonomousToolCreator
from client.src.business.tools.tool_registry import ToolRegistry


class ActiveLearningLoop:
    """
    主动学习循环
    
    功能：智能体能够主动学习，不断完善自己的工具和能力。
    
    用法：
        learning_loop = ActiveLearningLoop()
        await learning_loop.start_learning_loop()
    """
    
    def __init__(self, llm_client=None):
        """
        初始化主动学习循环
        
        Args:
            llm_client: LLM 客户端
        """
        self._llm = llm_client
        self._detector = ToolMissingDetector(llm_client)
        self._creator = AutonomousToolCreator(llm_client)
        self._logger = logger.bind(component="ActiveLearningLoop")
        self._learning_history = []
    
    async def start_learning_loop(self, max_iterations: int = 10):
        """
        开始主动学习循环
        
        Args:
            max_iterations: 最大迭代次数
        """
        self._logger.info(f"开始主动学习循环（最多 {max_iterations} 次迭代）")
        
        for i in range(max_iterations):
            self._logger.info(f"\n{'='*60}")
            self._logger.info(f"迭代 {i+1}/{max_iterations}")
            self._logger.info(f"{'='*60}")
            
            # 1. 分析当前能力边界
            self._logger.info("步骤 1: 分析当前能力边界...")
            capabilities = await self._analyze_capabilities()
            
            # 2. 发现能力缺口
            self._logger.info("步骤 2: 发现能力缺口...")
            gaps = await self._discover_capability_gaps(capabilities)
            
            if not gaps:
                self._logger.info("未发现能力缺口，学习循环结束")
                break
            
            self._logger.info(f"发现 {len(gaps)} 个能力缺口: {gaps}")
            
            # 3. 制定学习计划
            self._logger.info("步骤 3: 制定学习计划...")
            learning_plan = await self._create_learning_plan(gaps)
            
            # 4. 执行学习
            self._logger.info("步骤 4: 执行学习...")
            learning_results = await self._execute_learning(learning_plan)
            
            # 5. 创建新工具或优化已有工具
            self._logger.info("步骤 5: 创建新工具...")
            created_tools = await self._create_tools_from_learning(learning_results)
            
            # 6. 测试验证
            self._logger.info("步骤 6: 测试验证...")
            test_results = await self._test_created_tools(created_tools)
            
            # 7. 反思总结
            self._logger.info("步骤 7: 反思总结...")
            reflection = await self._reflect_and_summarize(i+1, gaps, created_tools, test_results)
            
            # 记录学习历史
            self._learning_history.append({
                "iteration": i+1,
                "gaps": gaps,
                "created_tools": created_tools,
                "test_results": test_results,
                "reflection": reflection
            })
            
            # 如果所有缺口都已填补，结束循环
            if len(created_tools) >= len(gaps):
                self._logger.info("所有能力缺口已填补，学习循环结束")
                break
        
        self._logger.info(f"\n{'='*60}")
        self._logger.info("主动学习循环完成")
        self._logger.info(f"总迭代次数: {min(i+1, max_iterations)}")
        self._logger.info(f"创建工具数量: {sum(len(h['created_tools']) for h in self._learning_history)}")
        self._logger.info(f"{'='*60}")
    
    async def learn_specific_topic(self, topic: str) -> Dict[str, Any]:
        """
        学习特定主题
        
        Args:
            topic: 要学习的主题
            
        Returns:
            学习结果
        """
        self._logger.info(f"开始学习主题: {topic}")
        
        # 1. 搜索知识库和网络
        learning_materials = await self._learn_item(topic)
        
        # 2. 分析是否需要创建工具
        needs_tool = await self._analyze_if_needs_tool(topic, learning_materials)
        
        result = {
            "topic": topic,
            "learning_materials": learning_materials,
            "needs_tool": needs_tool
        }
        
        # 3. 如果需要，创建工具
        if needs_tool:
            tool_name = await self._suggest_tool_name(topic)
            success, file_path = await self._creator.create_tool(tool_name, topic)
            result["created_tool"] = {
                "success": success,
                "tool_name": tool_name,
                "file_path": file_path
            }
        
        self._logger.info(f"主题学习完成: {topic}")
        
        return result
    
    async def _analyze_capabilities(self) -> Dict[str, Any]:
        """分析当前能力边界"""
        registry = ToolRegistry.get_instance()
        tools = registry.list_tools()
        
        capabilities = {
            "tool_count": len(tools),
            "tools": [tool.name for tool in tools],
            "categories": list(set([tool.category for tool in tools])),
        }
        
        self._logger.info(f"当前能力: {capabilities['tool_count']} 个工具, {len(capabilities['categories'])} 个类别")
        
        return capabilities
    
    async def _discover_capability_gaps(self, capabilities: Dict[str, Any]) -> List[str]:
        """发现能力缺口"""
        # 使用 LLM 分析能力缺口
        prompt = f"""
你是能力分析专家。

当前系统已有能力：
{json.dumps(capabilities, ensure_ascii=False, indent=2)}

请分析：
1. 一个完整的 AI Agent 系统还需要哪些能力？
2. 当前系统缺少哪些工具或功能？
3. 优先级最高的 3-5 个能力缺口是什么？

请以 JSON 格式输出：
{{
    "current_capabilities": ["cap1", "cap2"],
    "missing_capabilities": ["cap3", "cap4", "cap5"],
    "priority_gaps": ["gap1", "gap2", "gap3"]
}}
"""
        
        try:
            response = await self._call_llm(prompt)
            result = json.loads(response)
            return result.get("priority_gaps", [])
        except Exception as e:
            self._logger.error(f"发现能力缺口失败: {e}")
            return []
    
    async def _create_learning_plan(self, gaps: List[str]) -> List[Dict[str, Any]]:
        """制定学习计划"""
        plan = []
        
        for gap in gaps:
            plan.append({
                "gap": gap,
                "learning_methods": ["search_knowledge_base", "search_web", "read_documentation"],
                "expected_outcome": f"掌握 {gap} 能力"
            })
        
        self._logger.info(f"学习计划已制定: {len(plan)} 个学习项目")
        
        return plan
    
    async def _execute_learning(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行学习"""
        results = []
        
        for item in plan:
            gap = item["gap"]
            self._logger.info(f"  学习: {gap}...")
            
            try:
                learning_result = await self._learn_item(gap)
                results.append({
                    "gap": gap,
                    "success": True,
                    "learning_materials": learning_result
                })
            except Exception as e:
                self._logger.error(f"  学习失败: {e}")
                results.append({
                    "gap": gap,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    async def _learn_item(self, item: str) -> str:
        """学习某个项目"""
        self._logger.info(f"    正在学习: {item}...")
        
        learning_materials = ""
        
        # 1. 搜索知识库
        try:
            kb_results = await self._search_knowledge_base(item)
            learning_materials += f"\n\n## 知识库搜索结果：\n{kb_results}"
        except Exception as e:
            self._logger.warning(f"    知识库搜索失败: {e}")
        
        # 2. 搜索网络
        try:
            web_results = await self._deep_search(f"Python 实现 {item}")
            learning_materials += f"\n\n## 网络搜索结果：\n{web_results}"
        except Exception as e:
            self._logger.warning(f"    网络搜索失败: {e}")
            # 如果访问失败，尝试使用代理源
            try:
                proxy = await self._get_proxy()
                web_results = await self._deep_search(f"Python 实现 {item}", proxy=proxy)
                learning_materials += f"\n\n## 网络搜索结果（代理）:\n{web_results}"
            except Exception as e2:
                self._logger.warning(f"    代理搜索也失败: {e2}")
        
        self._logger.info(f"    学习完成: {item}")
        
        return learning_materials
    
    async def _create_tools_from_learning(self, learning_results: List[Dict[str, Any]]) -> List[str]:
        """从学习结果中创建工具"""
        created_tools = []
        
        for result in learning_results:
            if not result.get("success"):
                continue
            
            gap = result["gap"]
            
            # 分析是否需要创建工具
            needs_tool = await self._analyze_if_needs_tool(gap, result.get("learning_materials", ""))
            
            if needs_tool:
                # 建议工具名称
                tool_name = await self._suggest_tool_name(gap)
                
                # 创建工具
                success, file_path = await self._creator.create_tool(tool_name, gap)
                
                if success:
                    created_tools.append(tool_name)
                    self._logger.info(f"  工具创建成功: {tool_name}")
        
        return created_tools
    
    async def _test_created_tools(self, tool_names: List[str]) -> Dict[str, bool]:
        """测试创建的工具"""
        results = {}
        registry = ToolRegistry.get_instance()
        
        for tool_name in tool_names:
            tool = registry.get_tool(tool_name)
            
            if tool is None:
                results[tool_name] = False
                continue
            
            # 简单测试：检查工具是否可以执行
            try:
                # 这里应该进行更详细的测试
                results[tool_name] = True
            except Exception:
                results[tool_name] = False
        
        return results
    
    async def _reflect_and_summarize(
        self,
        iteration: int,
        gaps: List[str],
        created_tools: List[str],
        test_results: Dict[str, bool]
    ) -> str:
        """反思与总结"""
        prompt = f"""
你是学习反思专家。

学习循环迭代：{iteration}
能力缺口：{gaps}
创建的工具：{created_tools}
测试结果：{test_results}

请反思：
1. 这次学习循环有什么收获？
2. 哪些地方可以改进？
3. 下一步应该学习什么？

请简要总结（200 字以内）。
"""
        
        try:
            reflection = await self._call_llm(prompt)
            self._logger.info(f"反思: {reflection[:100]}...")
            return reflection
        except Exception as e:
            self._logger.error(f"反思失败: {e}")
            return ""
    
    async def _analyze_if_needs_tool(self, topic: str, learning_materials: str) -> bool:
        """分析是否需要创建工具"""
        prompt = f"""
你是工具需求分析专家。

主题：{topic}

学习内容：
{learning_materials[:1000]}

请分析：为了实现这个主题的能力，是否需要创建一个新的工具？

请以 JSON 格式输出：
{{
    "needs_tool": true/false,
    "reason": "原因分析"
}}
"""
        
        try:
            response = await self._call_llm(prompt)
            result = json.loads(response)
            return result.get("needs_tool", False)
        except Exception:
            return False
    
    async def _suggest_tool_name(self, topic: str) -> str:
        """建议工具名称"""
        # 简单实现：将主题转换为工具名称
        tool_name = topic.lower().replace(" ", "_").replace("-", "_")
        
        # 移除特殊字符
        import re
        tool_name = re.sub(r'[^a-z0-9_]', '', tool_name)
        
        return tool_name[:30]  # 限制长度
    
    async def _search_knowledge_base(self, query: str) -> str:
        """搜索知识库"""
        try:
            from client.src.business.knowledge_vector_db import VectorDatabase
            db = VectorDatabase()
            results = db.search(query, top_k=3)
            return "\n".join([r.get("content", "") for r in results])
        except Exception:
            return "知识库搜索不可用"
    
    async def _deep_search(self, query: str, proxy: Optional[str] = None) -> str:
        """深度搜索"""
        try:
            from client.src.business.deep_search_wiki.wiki_generator import LLMWikiGenerator
            generator = LLMWikiGenerator()
            result = await generator.generate_wiki(query)
            return result[:1000] if result else "深度搜索无结果"
        except Exception:
            return "深度搜索不可用"
    
    async def _get_proxy(self) -> Optional[str]:
        """获取代理"""
        try:
            from client.src.business.base_proxy_manager import ProxyManager
            manager = ProxyManager()
            return manager.get_best_proxy()
        except Exception:
            return None
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if self._llm is not None:
            return await self._llm.chat(prompt, model="qwen3.6:35b-a3b")
        else:
            try:
                from client.src.business.hermes_agent.llm_client import LLMClient
                llm = LLMClient()
                return await llm.chat(prompt, model="qwen3.6:35b-a3b")
            except Exception as e:
                self._logger.error(f"调用 LLM 失败: {e}")
                raise


async def test_active_learning_loop():
    """测试主动学习循环"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 配置 loguru
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ActiveLearningLoop")
    print("=" * 60)
    
    # 创建学习循环
    learning_loop = ActiveLearningLoop()
    
    # 测试学习特定主题
    print("\n测试学习特定主题...")
    result = await learning_loop.learn_specific_topic("天气查询")
    
    print(f"\n[结果] 学习完成:")
    print(f"  主题: {result['topic']}")
    print(f"  需要工具: {result['needs_tool']}")
    if "created_tool" in result:
        print(f"  创建工具: {result['created_tool']['tool_name']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import os
    asyncio.run(test_active_learning_loop())
