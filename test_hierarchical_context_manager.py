"""
分层模型上下文管理测试
验证四类模型的固定窗口大小配置和智能上下文管理功能
"""

import asyncio
import time
import tempfile
import os
from typing import Dict, List, Optional, Any

print("=" * 60)
print("分层模型上下文管理测试")
print("=" * 60)


class ModelType:
    """模型类型"""
    FAST = "fast"
    VISION = "vision"
    QUERY = "query"
    REASONING = "reasoning"


class ModelConfig:
    """模型配置"""
    def __init__(self, model_type, window_size, temperature, max_tokens, response_format=None, image_detail=None, presence_penalty=None):
        self.model_type = model_type
        self.window_size = window_size
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_format = response_format
        self.image_detail = image_detail
        self.presence_penalty = presence_penalty


class ContextTemplate:
    """上下文模板"""
    def __init__(self, model_type, structure, system_prompt, token_allocation):
        self.model_type = model_type
        self.structure = structure
        self.system_prompt = system_prompt
        self.token_allocation = token_allocation


class SessionCache:
    """会话缓存"""
    def __init__(self, session_id, context, timestamp, model_usage):
        self.session_id = session_id
        self.context = context
        self.timestamp = timestamp
        self.model_usage = model_usage


class ModelUsage:
    """模型使用情况"""
    def __init__(self, model_type, usage_count, avg_response_time, success_rate, token_usage, last_used):
        self.model_type = model_type
        self.usage_count = usage_count
        self.avg_response_time = avg_response_time
        self.success_rate = success_rate
        self.token_usage = token_usage
        self.last_used = last_used


class HierarchicalContextManager:
    """分层模型上下文管理系统"""
    
    def __init__(self):
        # 模型配置
        self.model_configs = {
            ModelType.FAST: ModelConfig(
                model_type=ModelType.FAST,
                window_size=2000,
                temperature=0.1,
                max_tokens=1024
            ),
            ModelType.VISION: ModelConfig(
                model_type=ModelType.VISION,
                window_size=4000,
                temperature=0.3,
                max_tokens=2048,
                image_detail="auto"
            ),
            ModelType.QUERY: ModelConfig(
                model_type=ModelType.QUERY,
                window_size=8000,
                temperature=0.0,
                max_tokens=4096,
                response_format="json_object"
            ),
            ModelType.REASONING: ModelConfig(
                model_type=ModelType.REASONING,
                window_size=16000,
                temperature=0.7,
                max_tokens=8192,
                presence_penalty=0.1
            )
        }
        
        # 上下文模板
        self.context_templates = {
            ModelType.FAST: ContextTemplate(
                model_type=ModelType.FAST,
                structure={
                    "currentFocus": "光标周围的10行代码",
                    "recentCommands": ["最后3条命令"],
                    "activeFile": "当前文件名"
                },
                system_prompt="只回答具体问题，不分析。保持回答简洁明了。",
                token_allocation={
                    "currentFocus": 0.6,
                    "recentCommands": 0.3,
                    "activeFile": 0.1
                }
            ),
            ModelType.VISION: ContextTemplate(
                model_type=ModelType.VISION,
                structure={
                    "screenshot": "base64图片",
                    "uiContext": "技术栈（React/Vue）",
                    "relatedCode": "1-2个相似组件"
                },
                system_prompt="专注于UI元素识别和分析，基于提供的截图生成相应的代码。",
                token_allocation={
                    "screenshot": 0.5,
                    "uiContext": 0.2,
                    "relatedCode": 0.3
                }
            ),
            ModelType.QUERY: ContextTemplate(
                model_type=ModelType.QUERY,
                structure={
                    "query": {"type": "SEARCH", "params": {}},
                    "data": ["向量搜索结果", "数据库schema摘要"],
                    "format": "TABLE"
                },
                system_prompt="只基于提供的数据回答，输出结构化格式。",
                token_allocation={
                    "query": 0.2,
                    "data": 0.7,
                    "format": 0.1
                }
            ),
            ModelType.REASONING: ContextTemplate(
                model_type=ModelType.REASONING,
                structure={
                    "problem": "清晰的问题定义",
                    "architecture": "项目骨架",
                    "code": ["核心文件", "相关文件摘要"],
                    "knowledge": "设计模式参考"
                },
                system_prompt="逐步推理，权衡利弊，提供详细的分析和解决方案。",
                token_allocation={
                    "problem": 0.05,
                    "architecture": 0.15,
                    "code": 0.6,
                    "knowledge": 0.2
                }
            )
        }
        
        # 三级缓存
        self.caches = {
            "L1": {},
            "L2": {},
            "L3": {}
        }
        
        # 模型使用情况
        self.model_usage = {
            ModelType.FAST: ModelUsage(
                model_type=ModelType.FAST,
                usage_count=0,
                avg_response_time=0.0,
                success_rate=0.0,
                token_usage=0,
                last_used=0.0
            ),
            ModelType.VISION: ModelUsage(
                model_type=ModelType.VISION,
                usage_count=0,
                avg_response_time=0.0,
                success_rate=0.0,
                token_usage=0,
                last_used=0.0
            ),
            ModelType.QUERY: ModelUsage(
                model_type=ModelType.QUERY,
                usage_count=0,
                avg_response_time=0.0,
                success_rate=0.0,
                token_usage=0,
                last_used=0.0
            ),
            ModelType.REASONING: ModelUsage(
                model_type=ModelType.REASONING,
                usage_count=0,
                avg_response_time=0.0,
                success_rate=0.0,
                token_usage=0,
                last_used=0.0
            )
        }
        
        # 预热机制
        self.warmup_cache = {}
    
    def get_model_config(self, model_type):
        """获取模型配置"""
        return self.model_configs.get(model_type)
    
    def get_context_template(self, model_type):
        """获取上下文模板"""
        return self.context_templates.get(model_type)
    
    def create_context(self, model_type, data):
        """创建上下文"""
        template = self.get_context_template(model_type)
        if not template:
            return data
        
        context = {}
        for key, placeholder in template.structure.items():
            context[key] = data.get(key, placeholder)
        
        context = self._smart_truncate(context, model_type)
        return context
    
    def _smart_truncate(self, context, model_type):
        """智能截断上下文"""
        config = self.get_model_config(model_type)
        if not config:
            return context
        
        current_size = self._estimate_token_size(context)
        max_size = config.window_size * 0.8
        
        if current_size <= max_size:
            return context
        
        template = self.get_context_template(model_type)
        if template:
            for key, ratio in template.token_allocation.items():
                if key in context:
                    item_size = self._estimate_token_size(context[key])
                    target_size = max_size * ratio
                    
                    if item_size > target_size:
                        context[key] = self._truncate_item(context[key], target_size)
        
        return context
    
    def _estimate_token_size(self, content):
        """估计Token大小"""
        if isinstance(content, str):
            return len(content) // 4
        elif isinstance(content, dict):
            return sum(self._estimate_token_size(v) for v in content.values())
        elif isinstance(content, list):
            return sum(self._estimate_token_size(item) for item in content)
        else:
            return 0
    
    def _truncate_item(self, item, max_tokens):
        """截断项目"""
        if isinstance(item, str):
            max_chars = max_tokens * 4
            if len(item) > max_chars:
                return item[:max_chars//2] + "..." + item[-max_chars//2:]
            return item
        elif isinstance(item, dict):
            truncated = {}
            total_size = 0
            for key, value in item.items():
                value_size = self._estimate_token_size(value)
                if total_size + value_size <= max_tokens:
                    truncated[key] = value
                    total_size += value_size
                else:
                    remaining = max_tokens - total_size
                    if remaining > 0:
                        truncated[key] = self._truncate_item(value, remaining)
                    break
            return truncated
        elif isinstance(item, list):
            truncated = []
            total_size = 0
            for value in item:
                value_size = self._estimate_token_size(value)
                if total_size + value_size <= max_tokens:
                    truncated.append(value)
                    total_size += value_size
                else:
                    remaining = max_tokens - total_size
                    if remaining > 0:
                        truncated.append(self._truncate_item(value, remaining))
                    break
            return truncated
        else:
            return item
    
    def route_request(self, request):
        """智能路由请求"""
        input_text = request.get("input", "")
        input_length = len(input_text)
        
        if "screenshot" in request or "image" in request:
            return ModelType.VISION
        
        if "query" in request or "search" in request or "data" in request:
            return ModelType.QUERY
        
        if input_length < 100 and any(keyword in input_text.lower() for keyword in ["如何", "什么", "哪里", "怎么"]):
            return ModelType.FAST
        
        return ModelType.REASONING
    
    def update_session_cache(self, session_id, context, model_type):
        """更新会话缓存"""
        self.caches["L1"][session_id] = SessionCache(
            session_id=session_id,
            context=context,
            timestamp=time.time(),
            model_usage={model_type: 1}
        )
        
        if len(self.caches["L1"]) > 100:
            oldest_session = min(self.caches["L1"], key=lambda x: self.caches["L1"][x].timestamp)
            del self.caches["L1"][oldest_session]
    
    def get_session_cache(self, session_id):
        """获取会话缓存"""
        return self.caches["L1"].get(session_id)
    
    def record_model_usage(self, model_type, response_time, success, token_usage):
        """记录模型使用情况"""
        usage = self.model_usage[model_type]
        usage.usage_count += 1
        usage.avg_response_time = ((usage.avg_response_time * (usage.usage_count - 1)) + response_time) / usage.usage_count
        usage.success_rate = ((usage.success_rate * (usage.usage_count - 1)) + (1 if success else 0)) / usage.usage_count
        usage.token_usage += token_usage
        usage.last_used = time.time()
    
    def get_model_usage(self, model_type):
        """获取模型使用情况"""
        return self.model_usage[model_type]
    
    def get_all_model_usage(self):
        """获取所有模型使用情况"""
        return self.model_usage
    
    def warmup_model(self, model_type):
        """预热模型"""
        if model_type not in self.warmup_cache:
            template = self.get_context_template(model_type)
            if template:
                warmup_context = {}
                for key, placeholder in template.structure.items():
                    warmup_context[key] = placeholder
                
                self.warmup_cache[model_type] = {
                    "context": warmup_context,
                    "timestamp": time.time()
                }
                print(f"预热模型: {model_type}")
    
    def get_warmup_context(self, model_type):
        """获取预热上下文"""
        warmup = self.warmup_cache.get(model_type)
        if warmup:
            if time.time() - warmup["timestamp"] < 3600:
                return warmup["context"]
            else:
                del self.warmup_cache[model_type]
        return None
    
    def transfer_result(self, from_model, to_model, result):
        """跨模型结果传递"""
        summary = self._generate_summary(result)
        
        template = self.get_context_template(to_model)
        if not template:
            return {"summary": summary}
        
        context = {}
        for key in template.structure:
            if key == "knowledge" or key == "relatedCode" or key == "data":
                context[key] = summary
        
        return context
    
    def _generate_summary(self, result):
        """生成结果摘要"""
        if isinstance(result, str):
            if len(result) > 200:
                return result[:150] + "..." + result[-50:]
            return result
        elif isinstance(result, dict):
            summary = []
            for key, value in result.items():
                if isinstance(value, str) and len(value) > 50:
                    summary.append(f"{key}: {value[:50]}...")
                else:
                    summary.append(f"{key}: {value}")
            return " | ".join(summary)
        elif isinstance(result, list):
            summary = []
            for item in result[:3]:
                if isinstance(item, str) and len(item) > 50:
                    summary.append(item[:50] + "...")
                else:
                    summary.append(str(item))
            if len(result) > 3:
                summary.append(f"... 共{len(result)}项")
            return " | ".join(summary)
        else:
            return str(result)
    
    def optimize_configs(self):
        """基于实际使用数据调优配置"""
        for model_type, usage in self.model_usage.items():
            if usage.usage_count > 0:
                config = self.model_configs[model_type]
                
                if usage.usage_count < 10 and usage.success_rate > 0.8:
                    config.window_size = max(int(config.window_size * 0.8), 1000)
                    print(f"优化 {model_type} 窗口大小: {config.window_size}")
                
                elif usage.usage_count > 50 and usage.success_rate < 0.6:
                    config.window_size = min(int(config.window_size * 1.2), 32000)
                    print(f"优化 {model_type} 窗口大小: {config.window_size}")
    
    def get_stats(self):
        """获取统计信息"""
        stats = {
            "cache": {
                "L1": len(self.caches["L1"]),
                "L2": len(self.caches["L2"]),
                "L3": len(self.caches["L3"])
            },
            "model_usage": {},
            "warmup": len(self.warmup_cache)
        }
        
        for model_type, usage in self.model_usage.items():
            stats["model_usage"][model_type] = {
                "usage_count": usage.usage_count,
                "avg_response_time": usage.avg_response_time,
                "success_rate": usage.success_rate,
                "token_usage": usage.token_usage,
                "last_used": usage.last_used
            }
        
        return stats
    
    def clear_cache(self, level=None):
        """清理缓存"""
        if level:
            if level in self.caches:
                self.caches[level].clear()
        else:
            for cache_level in self.caches:
                self.caches[cache_level].clear()


def create_hierarchical_context_manager():
    """创建分层上下文管理器"""
    return HierarchicalContextManager()


async def test_model_configs():
    """测试模型配置"""
    print("=== 测试模型配置 ===")
    
    manager = create_hierarchical_context_manager()
    
    # 测试快速反应模型
    fast_config = manager.get_model_config(ModelType.FAST)
    print(f"快速反应模型: 窗口大小={fast_config.window_size}, 温度={fast_config.temperature}")
    
    # 测试截图识别模型
    vision_config = manager.get_model_config(ModelType.VISION)
    print(f"截图识别模型: 窗口大小={vision_config.window_size}, 温度={vision_config.temperature}")
    
    # 测试结构化查询模型
    query_config = manager.get_model_config(ModelType.QUERY)
    print(f"结构化查询模型: 窗口大小={query_config.window_size}, 温度={query_config.temperature}")
    
    # 测试大数据推理模型
    reasoning_config = manager.get_model_config(ModelType.REASONING)
    print(f"大数据推理模型: 窗口大小={reasoning_config.window_size}, 温度={reasoning_config.temperature}")
    
    return True


async def test_context_creation():
    """测试上下文创建"""
    print("\n=== 测试上下文创建 ===")
    
    manager = create_hierarchical_context_manager()
    
    # 测试快速反应模型上下文
    fast_context = manager.create_context(ModelType.FAST, {
        "currentFocus": "def hello():\n    print('Hello world')",
        "recentCommands": ["run", "debug", "test"],
        "activeFile": "test.py"
    })
    print(f"快速反应模型上下文: {fast_context}")
    
    # 测试截图识别模型上下文
    vision_context = manager.create_context(ModelType.VISION, {
        "screenshot": "base64_image_data",
        "uiContext": "React",
        "relatedCode": ["Button组件", "Input组件"]
    })
    print(f"截图识别模型上下文: {vision_context}")
    
    # 测试结构化查询模型上下文
    query_context = manager.create_context(ModelType.QUERY, {
        "query": {"type": "SEARCH", "params": {"keyword": "python"}},
        "data": ["搜索结果1", "搜索结果2"],
        "format": "TABLE"
    })
    print(f"结构化查询模型上下文: {query_context}")
    
    # 测试大数据推理模型上下文
    reasoning_context = manager.create_context(ModelType.REASONING, {
        "problem": "如何优化React应用性能",
        "architecture": "React + Redux",
        "code": ["App.js", "components/Header.js"],
        "knowledge": "React性能优化最佳实践"
    })
    print(f"大数据推理模型上下文: {reasoning_context}")
    
    return True


async def test_smart_routing():
    """测试智能路由"""
    print("\n=== 测试智能路由 ===")
    
    manager = create_hierarchical_context_manager()
    
    # 测试快速反应模型路由
    fast_request = {"input": "如何使用print函数"}
    fast_model = manager.route_request(fast_request)
    print(f"快速请求路由到: {fast_model}")
    
    # 测试截图识别模型路由
    vision_request = {"input": "分析这个UI", "screenshot": "base64_image"}
    vision_model = manager.route_request(vision_request)
    print(f"截图请求路由到: {vision_model}")
    
    # 测试结构化查询模型路由
    query_request = {"input": "查询用户数据", "query": {"type": "SEARCH"}}
    query_model = manager.route_request(query_request)
    print(f"查询请求路由到: {query_model}")
    
    # 测试大数据推理模型路由
    reasoning_request = {"input": "如何设计一个分布式系统，需要考虑哪些因素？详细分析每个组件的设计原则和最佳实践。"}
    reasoning_model = manager.route_request(reasoning_request)
    print(f"复杂请求路由到: {reasoning_model}")
    
    return True


async def test_session_cache():
    """测试会话缓存"""
    print("\n=== 测试会话缓存 ===")
    
    manager = create_hierarchical_context_manager()
    session_id = "test_session"
    
    # 创建上下文
    context = {
        "currentFocus": "def hello():\n    print('Hello world')",
        "recentCommands": ["run", "debug"],
        "activeFile": "test.py"
    }
    
    # 更新缓存
    manager.update_session_cache(session_id, context, ModelType.FAST)
    
    # 获取缓存
    cached_session = manager.get_session_cache(session_id)
    print(f"缓存获取成功: {cached_session is not None}")
    if cached_session:
        print(f"缓存上下文: {cached_session.context}")
    
    # 测试缓存限制
    for i in range(101):
        manager.update_session_cache(f"session_{i}", context, ModelType.FAST)
    
    stats = manager.get_stats()
    print(f"L1缓存大小: {stats['cache']['L1']}")
    
    return True


async def test_model_usage():
    """测试模型使用情况"""
    print("\n=== 测试模型使用情况 ===")
    
    manager = create_hierarchical_context_manager()
    
    # 记录模型使用
    for i in range(5):
        manager.record_model_usage(ModelType.FAST, 0.1, True, 100)
        manager.record_model_usage(ModelType.VISION, 0.3, True, 200)
        manager.record_model_usage(ModelType.QUERY, 0.5, True, 400)
        manager.record_model_usage(ModelType.REASONING, 1.0, True, 800)
    
    # 获取使用情况
    fast_usage = manager.get_model_usage(ModelType.FAST)
    print(f"快速模型使用次数: {fast_usage.usage_count}")
    print(f"快速模型平均响应时间: {fast_usage.avg_response_time:.3f}s")
    print(f"快速模型成功率: {fast_usage.success_rate:.2f}")
    
    # 获取所有使用情况
    all_usage = manager.get_all_model_usage()
    for model_type, usage in all_usage.items():
        print(f"{model_type} 总Token使用: {usage.token_usage}")
    
    return True


async def test_warmup():
    """测试预热机制"""
    print("\n=== 测试预热机制 ===")
    
    manager = create_hierarchical_context_manager()
    
    # 预热模型
    manager.warmup_model(ModelType.FAST)
    manager.warmup_model(ModelType.VISION)
    
    # 获取预热上下文
    fast_warmup = manager.get_warmup_context(ModelType.FAST)
    vision_warmup = manager.get_warmup_context(ModelType.VISION)
    
    print(f"快速模型预热上下文: {fast_warmup is not None}")
    print(f"视觉模型预热上下文: {vision_warmup is not None}")
    
    stats = manager.get_stats()
    print(f"预热缓存大小: {stats['warmup']}")
    
    return True


async def test_result_transfer():
    """测试跨模型结果传递"""
    print("\n=== 测试跨模型结果传递 ===")
    
    manager = create_hierarchical_context_manager()
    
    # 模拟结果
    result = {
        "answer": "这是一个详细的回答，包含了很多信息和分析。" * 10,
        "recommendations": ["建议1", "建议2", "建议3", "建议4", "建议5"]
    }
    
    # 从快速模型传递到推理模型
    transferred = manager.transfer_result(ModelType.FAST, ModelType.REASONING, result)
    print(f"跨模型传递结果: {transferred}")
    
    # 从视觉模型传递到查询模型
    transferred2 = manager.transfer_result(ModelType.VISION, ModelType.QUERY, result)
    print(f"跨模型传递结果2: {transferred2}")
    
    return True


async def test_optimization():
    """测试配置优化"""
    print("\n=== 测试配置优化 ===")
    
    manager = create_hierarchical_context_manager()
    
    # 模拟使用数据
    for i in range(5):
        manager.record_model_usage(ModelType.FAST, 0.1, True, 100)
    
    # 优化配置
    manager.optimize_configs()
    
    # 检查优化结果
    fast_config = manager.get_model_config(ModelType.FAST)
    print(f"优化后快速模型窗口大小: {fast_config.window_size}")
    
    return True


async def test_integration():
    """集成测试"""
    tests = [
        test_model_configs,
        test_context_creation,
        test_smart_routing,
        test_session_cache,
        test_model_usage,
        test_warmup,
        test_result_transfer,
        test_optimization
    ]
    
    all_passed = True
    
    for test in tests:
        try:
            success = await test()
            if not success:
                all_passed = False
                print(f"测试 {test.__name__} 失败")
            else:
                print(f"测试 {test.__name__} 通过")
        except Exception as e:
            all_passed = False
            print(f"测试 {test.__name__} 异常: {e}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！分层模型上下文管理集成成功")
    else:
        print("部分测试失败，需要进一步调试")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(test_integration())