"""测试错误记忆集成"""
import sys
sys.path.insert(0, 'client/src')

from business.memory import get_error_memory

error_mem = get_error_memory()

print("测试错误记忆查询...")
result = error_mem.query("UnicodeDecodeError: utf-8 codec can't decode")
print(f"成功: {result['success']}")
print(f"置信度: {result['confidence']:.2f}")
print(f"来源: {result['source']}")
print(f"内容: {result.get('content', '')[:200]}...")