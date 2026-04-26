#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IDE Agent - 智能IDE智能体
============================

架构层级：
- UI层 (panel.py) → 调用 Agent
- Agent层 (IDEAgent) → 调用 Service
- Service层 (IDEService) → 实现业务逻辑

智能体职责：
1. 接收UI层的请求
2. 协调 IDEService 完成具体工作
3. 返回处理结果给UI层
4. 提供异步接口（compatible with QThread）

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime


# ── IDE Agent ─────────────────────────────────────────────────────

class IDEAgent:
    """
    智能IDE智能体
    
    架构：UI → Agent → Service
    
    Usage:
        from client.src.business.ide_agent import get_ide_agent
        
        agent = get_ide_agent()
        
        # 同步方法（推荐，QThread 中直接调用）
        result = agent.execute_code("print('Hello')", "python")
        
        # 异步方法（如果需要）
        result = await agent.execute_code_async("print('Hello')", "python")
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化智能IDE智能体"""
        self.config = config or {}
        self._service = None
        self._init_service()
    
    def _init_service(self):
        """初始化服务层"""
        from client.src.business.ide_service import IDEService
        self._service = IDEService(self.config)
    
    def _ensure_service(self) -> "IDEService":
        """确保服务层已初始化"""
        if self._service is None:
            self._init_service()
        return self._service
    
    # ── 代码执行 ─────────────────────────────────────────────────
    
    def execute_code(self, code: str, language: str = "python") -> Dict:
        """
        执行代码（同步接口，推荐）
        
        Args:
            code: 代码字符串
            language: 编程语言
            
        Returns:
            Dict: 执行结果
        """
        service = self._ensure_service()
        result = service.execute_code(code, language)
        
        return {
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "exit_code": result.exit_code,
            "execution_time_ms": result.execution_time_ms,
            "memory_usage_mb": result.memory_usage_mb,
        }
    
    async def execute_code_async(self, code: str, language: str = "python") -> Dict:
        """执行代码（异步接口）"""
        # 目前是同步操作，包装成异步
        return await asyncio.to_thread(
            self.execute_code, code, language
        )
    
    # ── 代码生成 ─────────────────────────────────────────────────
    
    def generate_code(
        self,
        intent: str,
        language: str = "python",
        context: str = "",
        framework: str = "",
    ) -> Dict:
        """
        生成代码（意图驱动）
        
        Args:
            intent: 用户意图描述
            language: 目标语言
            context: 上下文（现有代码）
            framework: 框架
            
        Returns:
            Dict: 生成结果
        """
        service = self._ensure_service()
        result = service.generate_code(intent, language, context, framework)
        
        return {
            "success": result.success,
            "code": result.code,
            "language": result.language,
            "file_path": result.file_path,
            "description": result.description,
            "confidence": result.confidence,
            "warnings": result.warnings,
            "suggestions": result.suggestions,
            "error": result.error,
        }
    
    async def generate_code_async(
        self,
        intent: str,
        language: str = "python",
        context: str = "",
        framework: str = "",
    ) -> Dict:
        """生成代码（异步接口）"""
        return await asyncio.to_thread(
            self.generate_code, intent, language, context, framework
        )
    
    # ── 代码解释 ─────────────────────────────────────────────────
    
    def explain_code(self, code: str, language: str = "python") -> str:
        """
        解释代码
        
        Args:
            code: 代码字符串
            language: 编程语言
            
        Returns:
            str: 代码解释
        """
        service = self._ensure_service()
        return service.explain_code(code, language)
    
    async def explain_code_async(self, code: str, language: str = "python") -> str:
        """解释代码（异步接口）"""
        return await asyncio.to_thread(
            self.explain_code, code, language
        )
    
    # ── 代码调试 ─────────────────────────────────────────────────
    
    def debug_code(
        self,
        code: str,
        language: str = "python",
        error_message: str = "",
    ) -> str:
        """
        调试代码（错误分析）
        
        Args:
            code: 代码字符串
            language: 编程语言
            error_message: 错误信息（如果有）
            
        Returns:
            str: 调试建议
        """
        service = self._ensure_service()
        return service.debug_code(code, language, error_message)
    
    async def debug_code_async(
        self,
        code: str,
        language: str = "python",
        error_message: str = "",
    ) -> str:
        """调试代码（异步接口）"""
        return await asyncio.to_thread(
            self.debug_code, code, language, error_message
        )
    
    # ── 代码优化 ─────────────────────────────────────────────────
    
    def optimize_code(self, code: str, language: str = "python") -> str:
        """
        优化代码（性能/可读性）
        
        Args:
            code: 代码字符串
            language: 编程语言
            
        Returns:
            str: 优化建议
        """
        service = self._ensure_service()
        return service.optimize_code(code, language)
    
    async def optimize_code_async(self, code: str, language: str = "python") -> str:
        """优化代码（异步接口）"""
        return await asyncio.to_thread(
            self.optimize_code, code, language
        )
    
    # ── 语法检查 ─────────────────────────────────────────────────
    
    def analyze_code(self, code: str, language: str = "python") -> Dict:
        """
        分析代码（语法检查等）
        
        Args:
            code: 代码字符串
            language: 编程语言
            
        Returns:
            Dict: 分析结果
        """
        service = self._ensure_service()
        result = service.analyze_code(code, language)
        
        return {
            "syntax_valid": result.syntax_valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "suggestions": result.suggestions,
            "complexity": result.complexity,
            "line_count": result.line_count,
        }
    
    async def analyze_code_async(self, code: str, language: str = "python") -> Dict:
        """分析代码（异步接口）"""
        return await asyncio.to_thread(
            self.analyze_code, code, language
        )
    
    # ── 统计信息 ─────────────────────────────────────────────────
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        service = self._ensure_service()
        return service.get_stats()
    
    # ── 聊天消息处理（流式输出支持）─────────────────────────────────
    
    def process_chat_message(
        self,
        message: str,
        context: Optional[Dict] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
    ) -> Dict:
        """
        处理聊天消息（意图驱动）
        
        Args:
            message: 用户消息
            context: 上下文（项目路径、当前文件等）
            callbacks: 回调函数字典
                - on_stream_delta: 流式输出回调
                - on_thinking: 思考过程回调
                - on_tool_start: 工具开始回调
                - on_tool_result: 工具结果回调
            
        Returns:
            Dict: 处理结果
        """
        # 分析用户意图
        intent = self._analyze_intent(message)
        
        # 根据意图调用不同的方法
        if intent['type'] == 'generate_code':
            return self._handle_generate_code(message, intent, callbacks)
        elif intent['type'] == 'modify_code':
            return self._handle_modify_code(message, intent, context, callbacks)
        elif intent['type'] == 'explain_code':
            return self._handle_explain_code(message, intent, callbacks)
        elif intent['type'] == 'debug_code':
            return self._handle_debug_code(message, intent, callbacks)
        elif intent['type'] == 'optimize_code':
            return self._handle_optimize_code(message, intent, callbacks)
        else:
            return self._handle_general_chat(message, callbacks)
    
    def _analyze_intent(self, message: str) -> Dict:
        """
        分析用户意图
        
        Args:
            message: 用户消息
            
        Returns:
            Dict: 意图信息
        """
        message_lower = message.lower()
        
        # 生成代码
        generate_keywords = ['创建', '生成', '新建', '写', '开发', '实现', 'create', 'generate', 'new']
        if any(kw in message_lower for kw in generate_keywords):
            # 提取语言和框架
            language = self._extract_language(message)
            framework = self._extract_framework(message)
            return {
                'type': 'generate_code',
                'language': language,
                'framework': framework,
                'description': message,
            }
        
        # 修改代码
        modify_keywords = ['修改', '更新', '优化', '改进', '修复', '添加', '删除', 'modify', 'update', 'fix', 'add', 'remove']
        if any(kw in message_lower for kw in modify_keywords):
            return {
                'type': 'modify_code',
                'description': message,
            }
        
        # 解释代码
        explain_keywords = ['解释', '说明', '讲解', '什么意思', 'explain', 'what', 'how']
        if any(kw in message_lower for kw in explain_keywords):
            return {
                'type': 'explain_code',
                'description': message,
            }
        
        # 调试代码
        debug_keywords = ['调试', '错误', '报错', 'bug', 'debug', 'error', 'fix']
        if any(kw in message_lower for kw in debug_keywords):
            return {
                'type': 'debug_code',
                'description': message,
            }
        
        # 优化代码
        optimize_keywords = ['优化', '性能', '速度', '更快', 'optimize', 'performance', 'faster']
        if any(kw in message_lower for kw in optimize_keywords):
            return {
                'type': 'optimize_code',
                'description': message,
            }
        
        # 通用聊天
        return {
            'type': 'general_chat',
            'description': message,
        }
    
    def _extract_language(self, message: str) -> str:
        """提取编程语言"""
        message_lower = message.lower()
        
        if 'python' in message_lower or 'py' in message_lower:
            return 'python'
        elif 'javascript' in message_lower or 'js' in message_lower:
            return 'javascript'
        elif 'typescript' in message_lower or 'ts' in message_lower:
            return 'typescript'
        elif 'html' in message_lower:
            return 'html'
        elif 'css' in message_lower:
            return 'css'
        else:
            return 'python'  # 默认 Python
    
    def _extract_framework(self, message: str) -> str:
        """提取框架"""
        message_lower = message.lower()
        
        if 'pyqt' in message_lower or 'qt' in message_lower:
            return 'pyqt'
        elif 'flask' in message_lower:
            return 'flask'
        elif 'django' in message_lower:
            return 'django'
        elif 'react' in message_lower:
            return 'react'
        elif 'vue' in message_lower:
            return 'vue'
        else:
            return ''
    
    def _handle_generate_code(
        self,
        message: str,
        intent: Dict,
        callbacks: Optional[Dict[str, Callable]],
    ) -> Dict:
        """处理代码生成"""
        # 调用生成代码服务
        result = self.generate_code(
            intent=intent['description'],
            language=intent['language'],
            framework=intent['framework'],
        )
        
        if result['success']:
            # 流式输出生成的代码
            if callbacks and 'on_stream_delta' in callbacks:
                code = result['code']
                # 分块输出（模拟流式）
                chunk_size = 50
                for i in range(0, len(code), chunk_size):
                    chunk = code[i:i+chunk_size]
                    callbacks['on_stream_delta'](chunk)
                    import time
                    time.sleep(0.01)  # 模拟延迟
            
            return {
                'type': 'code_generation',
                'message': f"已生成{intent['language']}代码：\n\n{result['description']}",
                'file_path': result['file_path'],
                'code': result['code'],
                'language': result['language'],
            }
        else:
            return {
                'type': 'error',
                'message': f"代码生成失败：{result['error']}",
                'error': result['error'],
            }
    
    def _handle_modify_code(
        self,
        message: str,
        intent: Dict,
        context: Optional[Dict],
        callbacks: Optional[Dict[str, Callable]],
    ) -> Dict:
        """处理代码修改"""
        # TODO: 实现代码修改逻辑
        # 1. 从 context 获取当前文件
        # 2. 读取文件内容
        # 3. 调用 AI 修改代码
        # 4. 返回修改后的代码
        
        return {
            'type': 'general_chat',
            'message': '代码修改功能正在开发中...',
        }
    
    def _handle_explain_code(
        self,
        message: str,
        intent: Dict,
        callbacks: Optional[Dict[str, Callable]],
    ) -> Dict:
        """处理代码解释"""
        # TODO: 从消息中提取代码
        # 这里简化，假设消息中包含代码
        code = self._extract_code_from_message(message)
        
        if not code:
            return {
                'type': 'general_chat',
                'message': '请在消息中包含要解释的代码。',
            }
        
        explanation = self.explain_code(code)
        
        return {
            'type': 'explanation',
            'message': explanation,
        }
    
    def _handle_debug_code(
        self,
        message: str,
        intent: Dict,
        callbacks: Optional[Dict[str, Callable]],
    ) -> Dict:
        """处理代码调试"""
        code = self._extract_code_from_message(message)
        
        if not code:
            return {
                'type': 'general_chat',
                'message': '请在消息中包含要调试的代码。',
            }
        
        debug_info = self.debug_code(code)
        
        return {
            'type': 'debug_info',
            'message': debug_info,
        }
    
    def _handle_optimize_code(
        self,
        message: str,
        intent: Dict,
        callbacks: Optional[Dict[str, Callable]],
    ) -> Dict:
        """处理代码优化"""
        code = self._extract_code_from_message(message)
        
        if not code:
            return {
                'type': 'general_chat',
                'message': '请在消息中包含要优化的代码。',
            }
        
        optimization = self.optimize_code(code)
        
        return {
            'type': 'optimization',
            'message': optimization,
        }
    
    def _handle_general_chat(
        self,
        message: str,
        callbacks: Optional[Dict[str, Callable]],
    ) -> Dict:
        """处理通用聊天"""
        # TODO: 调用通用对话模型
        return {
            'type': 'general_chat',
            'message': f"收到你的消息：{message}\n\n我是你的 AI 编程助手，可以帮你生成代码、修改代码、解释代码等。",
        }
    
    def _extract_code_from_message(self, message: str) -> str:
        """从消息中提取代码"""
        # 匹配代码块 ```code```
        match = re.search(r'```(?:\w*)\n(.*?)```', message, re.DOTALL)
        if match:
            return match.group(1)
        
        # 如果没有代码块，返回空
        return ''
    
    # ── A2A 协议支持 ────────────────────────────────────────────
    
    def handle_a2a_message(self, message: Dict) -> Dict:
        """
        处理 A2A 协议消息
        
        Args:
            message: A2A 消息
            
        Returns:
            Dict: 响应消息
        """
        message_type = message.get("type", "")
        
        if message_type == "execute_code":
            code = message.get("code", "")
            language = message.get("language", "python")
            result = self.execute_code(code, language)
            return {"status": "success", "result": result}
        
        elif message_type == "generate_code":
            intent = message.get("intent", "")
            language = message.get("language", "python")
            result = self.generate_code(intent, language)
            return {"status": "success", "result": result}
        
        elif message_type == "explain_code":
            code = message.get("code", "")
            language = message.get("language", "python")
            explanation = self.explain_code(code, language)
            return {"status": "success", "result": {"explanation": explanation}}
        
        elif message_type == "debug_code":
            code = message.get("code", "")
            language = message.get("language", "python")
            error_message = message.get("error_message", "")
            debug_info = self.debug_code(code, language, error_message)
            return {"status": "success", "result": {"debug_info": debug_info}}
        
        elif message_type == "optimize_code":
            code = message.get("code", "")
            language = message.get("language", "python")
            optimization = self.optimize_code(code, language)
            return {"status": "success", "result": {"optimization": optimization}}
        
        elif message_type == "analyze_code":
            code = message.get("code", "")
            language = message.get("language", "python")
            analysis = self.analyze_code(code, language)
            return {"status": "success", "result": analysis}
        
        else:
            return {
                "status": "error",
                "error": f"未知的消息类型: {message_type}",
            }


# ── 单例模式 ─────────────────────────────────────────────────────

def get_ide_agent(config: Optional[Dict] = None) -> IDEAgent:
    """
    获取智能IDE智能体实例（单例模式）
    
    Args:
        config: 可选的配置参数
        
    Returns:
        IDEAgent: 智能IDE智能体实例
    """
    if not hasattr(get_ide_agent, "_instance"):
        get_ide_agent._instance = IDEAgent(config)
    return get_ide_agent._instance


# ── 测试 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 测试智能IDE智能体
    agent = get_ide_agent()
    
    print("=" * 60)
    print("测试1: 执行代码")
    print("=" * 60)
    
    code = """
print("Hello, World!")
for i in range(3):
    print(f"Count: {i}")
"""
    
    result = agent.execute_code(code, "python")
    print(f"状态: {result['status']}")
    print(f"输出:\n{result['output']}")
    if result['error']:
        print(f"错误:\n{result['error']}")
    print(f"执行时间: {result['execution_time_ms']:.2f} ms")
    
    print("\n" + "=" * 60)
    print("测试2: 生成代码")
    print("=" * 60)
    
    result = agent.generate_code("写一个登录函数", "python")
    if result['success']:
        print(f"生成成功！")
        print(f"代码:\n{result['code']}")
    else:
        print(f"生成失败: {result['error']}")
    
    print("\n" + "=" * 60)
    print("测试3: 解释代码")
    print("=" * 60)
    
    code = """
def add(a, b):
    return a + b
"""
    
    explanation = agent.explain_code(code, "python")
    print(explanation)
    
    print("\n" + "=" * 60)
    print("测试4: 分析代码")
    print("=" * 60)
    
    analysis = agent.analyze_code(code, "python")
    print(f"语法有效: {analysis['syntax_valid']}")
    print(f"行数: {analysis['line_count']}")
    if analysis['errors']:
        print(f"错误: {analysis['errors']}")
    
    print("\n" + "=" * 60)
    print("统计信息")
    print("=" * 60)
    
    stats = agent.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
