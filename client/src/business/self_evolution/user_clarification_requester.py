"""
UserClarificationRequester - 用户交互澄清器

功能：当智能体不确定时，能够主动询问用户。

使用场景：
1. 创建工具时，不确定具体需求
2. 学习过程中，遇到模糊的概念
3. 升级模型时，需要用户确认
"""

import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger

from client.src.business.agent_progress import AgentProgress, ProgressPhase


class UserClarificationRequester:
    """
    用户澄清请求器
    
    功能：当智能体不确定时，能够主动询问用户。
    
    用法：
        requester = UserClarificationRequester()
        response = await requester.request_clarification("需要更多信息", ["选项1", "选项2"])
    """
    
    def __init__(self, timeout: int = 300):
        """
        初始化用户澄清请求器
        
        Args:
            timeout: 等待用户回复的超时时间（秒），默认 5 分钟
        """
        self._timeout = timeout
        self._logger = logger.bind(component="UserClarificationRequester")
        self._pending_requests = {}  # 存储待处理的请求
        self._responses = {}  # 存储用户回复
    
    async def request_clarification(
        self,
        question: str,
        options: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        请求用户澄清
        
        Args:
            question: 要向用户提出的问题
            options: 可选的选项列表
            context: 上下文信息
            
        Returns:
            用户的回复
        """
        self._logger.info(f"请求用户澄清: {question[:50]}...")
        
        # 1. 通过 AgentProgress 向用户显示问题
        progress = AgentProgress(
            phase=ProgressPhase.USER_CLARIFICATION,
            message=question,
            options=options,
            await_user_response=True,
            context=context
        )
        
        self.emit_progress(progress)
        
        # 2. 等待用户回复
        request_id = progress.request_id
        self._pending_requests[request_id] = progress
        
        self._logger.info(f"  等待用户回复（请求 ID: {request_id}）...")
        
        try:
            user_response = await self._wait_for_user_response(request_id, timeout=self._timeout)
            
            self._logger.info(f"  收到用户回复: {user_response[:100]}...")
            
            # 3. 返回用户回复
            return user_response
            
        except asyncio.TimeoutError:
            self._logger.warning(f"  等待用户回复超时（{self._timeout} 秒）")
            return ""  # 返回空字符串表示超时
        
        finally:
            # 清理
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]
    
    async def request_confirmation(
        self,
        message: str,
        options: List[str] = None
    ) -> bool:
        """
        请求用户确认（是/否 问题）
        
        Args:
            message: 要确认的消息
            options: 选项列表（默认：["是", "否"]）
            
        Returns:
            用户是否确认
        """
        if options is None:
            options = ["是", "否"]
        
        response = await self.request_clarification(message, options)
        
        # 判断用户回复
        if response == "是" or response.lower() in ["yes", "y", "ok", "确认"]:
            return True
        else:
            return False
    
    async def request_tool_requirements(self, tool_name: str) -> Dict[str, Any]:
        """
        请求用户提供工具需求
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具需求字典
        """
        questions = [
            f"请描述 {tool_name} 工具应该实现什么功能？",
            "这个工具需要哪些输入参数？",
            "你期望这个工具返回什么结果？",
            "有没有类似的工具可以作为参考？"
        ]
        
        answers = {}
        
        for i, question in enumerate(questions, 1):
            self._logger.info(f"  问题 {i}/{len(questions)}: {question}")
            
            response = await self.request_clarification(question)
            answers[f"question_{i}"] = {
                "question": question,
                "answer": response
            }
        
        return answers
    
    async def request_learning_preferences(self) -> Dict[str, Any]:
        """
        请求用户的学习偏好
        
        Returns:
            学习偏好字典
        """
        questions = [
            "你希望我重点学习哪些领域的知识？",
            "当我遇到不确定的情况时，应该如何处理？",
            "你对我未来的进化有什么期望？"
        ]
        
        preferences = {}
        
        for i, question in enumerate(questions, 1):
            self._logger.info(f"  问题 {i}/{len(questions)}: {question}")
            
            response = await self.request_clarification(question)
            preferences[f"preference_{i}"] = {
                "question": question,
                "answer": response
            }
        
        return preferences
    
    def emit_progress(self, progress: AgentProgress):
        """
        发送进度更新（需要通过信号或事件总线实现）
        
        Args:
            progress: 进度对象
        """
        # TODO: 实现实际的进度发送逻辑
        # 例如：通过 PyQt 信号、WebSocket、或消息队列
        
        self._logger.info(f"  发送进度更新: {progress.phase} - {progress.message[:50]}...")
        
        # 示例：打印到控制台（实际应该通过 UI 显示给用户）
        print(f"\n[用户交互] {progress.message}")
        if progress.options:
            print(f"选项: {', '.join(progress.options)}")
    
    async def _wait_for_user_response(self, request_id: str, timeout: int) -> str:
        """
        等待用户回复
        
        Args:
            request_id: 请求 ID
            timeout: 超时时间（秒）
            
        Returns:
            用户的回复
        """
        # TODO: 实现实际的等待逻辑
        # 例如：通过 asyncio.Queue、WebSocket 接收、或轮询数据库
        
        # 这里使用简单的轮询模拟
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查是否有回复
            if request_id in self._responses:
                response = self._responses[request_id]
                del self._responses[request_id]  # 清理
                return response
            
            # 等待一段时间再检查
            await asyncio.sleep(1)
        
        # 超时
        raise asyncio.TimeoutError(f"等待用户回复超时（{timeout} 秒）")
    
    def provide_response(self, request_id: str, response: str):
        """
        提供用户回复（由外部调用，例如从 UI 或 API）
        
        Args:
            request_id: 请求 ID
            response: 用户回复
        """
        self._responses[request_id] = response
        self._logger.info(f"收到用户回复（请求 ID: {request_id}）: {response[:50]}...")
    
    async def interactive_tool_creation(self, tool_name: str, tool_description: str) -> Dict[str, Any]:
        """
        交互式工具创建（在创建工具过程中与用户交互）
        
        Args:
            tool_name: 工具名称
            tool_description: 工具描述
            
        Returns:
            包含用户需求和确认的字典
        """
        self._logger.info(f"开始交互式工具创建: {tool_name}")
        
        # 1. 请求工具需求
        self._logger.info("  步骤 1: 获取工具需求...")
        requirements = await self.request_tool_requirements(tool_name)
        
        # 2. 确认是否继续
        self._logger.info("  步骤 2: 确认是否继续...")
        confirmed = await self.request_confirmation(
            f"我将根据以下需求创建 {tool_name} 工具：\n\n{requirements}\n\n是否继续？"
        )
        
        if not confirmed:
            self._logger.info("  用户取消工具创建")
            return {"cancelled": True}
        
        # 3. 创建完成后，请求用户测试
        self._logger.info("  步骤 3: 等待工具创建完成...")
        # （这里应该调用 AutonomousToolCreator.create_tool()）
        
        # 4. 请求用户确认测试结果
        test_passed = await self.request_confirmation(
            f"{tool_name} 工具已创建完成，是否通过测试？"
        )
        
        return {
            "cancelled": False,
            "requirements": requirements,
            "test_passed": test_passed
        }


async def test_user_clarification_requester():
    """测试用户澄清请求器"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 配置 loguru
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 UserClarificationRequester")
    print("=" * 60)
    
    # 创建请求器
    requester = UserClarificationRequester()
    
    # 测试请求澄清
    print("\n测试请求澄清...")
    print("（注意：这个测试会等待用户输入，超时时间 10 秒）")
    
    try:
        response = await requester.request_clarification(
            "这是一个测试问题，请输入任意回复（或等待超时）：",
            options=["选项1", "选项2", "选项3"],
            timeout=10  # 缩短超时时间用于测试
        )
        print(f"\n[结果] 收到回复: {response}")
    except asyncio.TimeoutError:
        print("\n[结果] 等待用户回复超时")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_user_clarification_requester())
