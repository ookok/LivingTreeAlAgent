"""统一记忆层测试脚本"""
import sys
sys.path.insert(0, 'client/src')

from business.memory import (
    query_memory, store_memory,
    get_memory_router,
    get_session_memory,
    get_exact_memory,
    get_vector_memory,
    get_document_memory,
    get_knowledge_graph_memory,
    get_error_memory,
    get_evolution_memory
)

print('=' * 60)
print('统一记忆层完整测试')
print('=' * 60)

# 测试存储功能
print('\n[1] 测试存储功能')
store_memory('人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新的技术科学。', 'mid_term')
store_memory('机器学习是人工智能的一个分支。', 'mid_term')
store_memory('Python是一种高级编程语言。', 'mid_term')
print('✓ 文档存储成功')

session_mem = get_session_memory()
session_mem.store('你好！', session_id='test_session', user_id='user1', role='user')
session_mem.store('你好！有什么我可以帮助你的吗？', session_id='test_session', user_id='user1', role='assistant')
print('✓ 会话存储成功')

error_mem = get_error_memory()
error_mem.store('Connection timeout', error_type='network_error', recovery_steps=['检查网络', '重试连接'])
print('✓ 错误记忆存储成功')

evo_mem = get_evolution_memory()
evo_mem.store('模型升级', phase='model_upgrade', decision={'model': 'qwen3.6'})
print('✓ 进化记忆存储成功')

# 测试查询功能
print('\n[2] 测试查询功能')

router = get_memory_router()

# 测试文档查询
result = router.query('什么是人工智能？')
print(f'查询 "什么是人工智能？": 来源={result["memory_source"]}, 置信度={result["confidence"]:.2f}')

# 测试会话查询
result = router.query('你好！', {'session_id': 'test_session'})
print(f'查询 "你好！" (会话): 来源={result["memory_source"]}, 置信度={result["confidence"]:.2f}')

# 测试错误查询
result = router.query('network_error')
print(f'查询 "network_error": 来源={result["memory_source"]}, 置信度={result["confidence"]:.2f}')

# 测试意图分类
print('\n[3] 测试意图分类')
test_queries = [
    '如何修复网络错误？',
    '帮我写一个Python函数',
    '解释一下量子计算',
    '查找用户手册',
    '系统如何进化？'
]

for query in test_queries:
    routes = router.route(query, {})
    print(f'"{query}" -> 路由: {routes}')

print('\n' + '=' * 60)
print('测试完成！')
print('=' * 60)