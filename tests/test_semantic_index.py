# -*- coding: utf-8 -*-
"""
语义索引测试
"""

import sys
import time

# Direct execution
exec(open('core/semantic_index.py', encoding='utf-8').read())

print("=" * 60)
print("[TEST] Semantic Index - Virtual File System")
print("=" * 60)

# ============================================================================
# Test 1: Basic Indexing
# ============================================================================
print("\n[Test 1] Basic Indexing")
print("-" * 40)

test_context = """
# 用户管理系统

这是一个用户管理系统的文档。

## 功能模块

- 用户注册
- 用户登录
- 权限管理

## 代码实现

```python
class UserManager:
    def __init__(self, db):
        self.db = db
    
    def register(self, username: str, email: str) -> User:
        pass
    
    def login(self, username: str, password: str) -> Optional[User]:
        pass
```

## 配置

需要配置数据库连接和缓存策略。
"""

intent_sig = {
    "type": "create",
    "action": "create",
    "target": "user_manager",
    "constraints": ["performance"],
    "code_signatures": ["UserManager", "register", "login"]
}

indexer = SemanticIndexer()
vfs = indexer.index(test_context, intent_sig)

print(f"  Chunks created: {vfs.total_chunks}")
print(f"  Total chars: {vfs.total_chars}")
print(f"  Index time: {vfs.index_time_ms:.1f}ms")
print(f"  Paths: {list(vfs.paths.keys())[:5]}")

# ============================================================================
# Test 2: Content Type Detection
# ============================================================================
print("\n[Test 2] Content Type Detection")
print("-" * 40)

code_context = "```python\ndef test():\n    pass\n```" * 10
md_context = "# Heading\n" * 10
mixed_context = "# Docs\n```js\ncode\n```\ntext\n"

test_types = [
    (code_context, "code"),
    (md_context, "markdown"),
    (mixed_context, "mixed"),
]

for ctx, expected in test_types:
    detected = indexer._detect_content_type(ctx)
    status = "[OK]" if detected == expected else "[X]"
    print(f"  {status} {expected}: detected as {detected}")

# ============================================================================
# Test 3: Search Functionality
# ============================================================================
print("\n[Test 3] Search Functionality")
print("-" * 40)

results = vfs.search("用户登录")
print(f"  Search '用户登录': {len(results)} results")
for r in results[:3]:
    print(f"    - Score: {r.relevance_score:.2f} | {r.chunk.path}")
    print(f"      Preview: {r.context_preview[:50]}...")

results = vfs.search("UserManager")
print(f"\n  Search 'UserManager': {len(results)} results")
for r in results[:3]:
    print(f"    - Score: {r.relevance_score:.2f} | {r.chunk.path}")

# ============================================================================
# Test 4: Tag-based Search
# ============================================================================
print("\n[Test 4] Tag-based Search")
print("-" * 40)

tag_results = vfs.search_by_tag("python")
print(f"  Tag 'python': {len(tag_results)} chunks")
for chunk in tag_results[:3]:
    print(f"    - {chunk.path}: {len(chunk.content)} chars")

tag_results = vfs.search_by_tag("documentation")
print(f"\n  Tag 'documentation': {len(tag_results)} chunks")

# ============================================================================
# Test 5: Keyword Extraction
# ============================================================================
print("\n[Test 5] Keyword Extraction")
print("-" * 40)

keywords = indexer._extract_keywords("用户管理系统包含注册登录功能，使用Python开发，性能高效")
print(f"  Keywords: {keywords}")

signatures = indexer._extract_signatures("""
class UserService:
    def __init__(self):
        pass
    def get_user(self, user_id: int) -> User:
        pass
    async def create_user(self, name: str) -> User:
        pass
""", "python")
print(f"  Python signatures: {signatures}")

# ============================================================================
# Test 6: VFS Stats
# ============================================================================
print("\n[Test 6] VFS Statistics")
print("-" * 40)

stats = vfs.get_stats()
for key, value in stats.items():
    print(f"  {key}: {value}")

# ============================================================================
# Test 7: Lazy Loading
# ============================================================================
print("\n[Test 7] Lazy Loading")
print("-" * 40)

loader = LazySemanticLoader(vfs)
chunks = loader.load_related("code_block_1", depth=1)
print(f"  Loaded {len(chunks)} chunks (including related)")
print(f"  Loaded chunk IDs: {list(loader.loaded_chunks)[:5]}")

# ============================================================================
# Test 8: Complex Mixed Content
# ============================================================================
print("\n[Test 8] Complex Mixed Content")
print("-" * 40)

complex_context = """
# 项目概述

这是一个电商平台项目。

## 用户模块

实现用户注册、登录、个人资料管理。

```python
class UserService:
    async def register(self, username: str, email: str) -> User:
        '''注册新用户'''
        pass
    
    async def login(self, username: str, password: str) -> Token:
        '''用户登录'''
        pass
    
    def get_profile(self, user_id: int) -> Profile:
        '''获取用户资料'''
        pass
```

## 商品模块

管理商品信息和库存。

```python
class ProductService:
    def list_products(self, category: str) -> List[Product]:
        pass
    
    def get_product(self, product_id: int) -> Product:
        pass
```

## 订单模块

处理订单流程。

```javascript
class OrderService {
    async createOrder(userId, items) {
        // 创建订单逻辑
    }
    
    async cancelOrder(orderId) {
        // 取消订单逻辑
    }
}
```

## 数据库配置

```json
{
    "database": "postgres://localhost/shop",
    "cache": "redis://localhost"
}
```
"""

vfs2 = indexer.index(complex_context, {"type": "create", "action": "create", "target": "ecommerce"})

print(f"  Chunks: {vfs2.total_chunks}")
print(f"  Paths:")
for path in list(vfs2.paths.keys())[:8]:
    print(f"    - {path}")

# Search for specific content
results = vfs2.search("订单创建")
print(f"\n  Search '订单创建': {len(results)} results")
for r in results[:2]:
    print(f"    - {r.relevance_score:.2f}: {r.chunk.path}")

results = vfs2.search("UserService")
print(f"\n  Search 'UserService': {len(results)} results")

# ============================================================================
# Test 9: Convenience Functions
# ============================================================================
print("\n[Test 9] Convenience Functions")
print("-" * 40)

# Create semantic index
vfs3 = create_semantic_index("Some context with code:\n```python\ndef test(): pass\n```", intent_sig)
print(f"  create_semantic_index: {vfs3.total_chunks} chunks")

# Quick search
results = quick_search(vfs3, "test")
print(f"  quick_search: {len(results)} results")

# ============================================================================
# Test 10: Performance
# ============================================================================
print("\n[Test 10] Performance")
print("-" * 40)

# Large context test
large_context = """
# 大型文档

""" + """
## Section {i}

这是第 {i} 个章节的内容。
包含一些代码示例：

```python
def function_{i}(param):
    '''函数说明'''
    return param * {i}
```

更多内容...
""" * 50

start = time.time()
vfs_large = indexer.index(large_context, intent_sig)
index_time = (time.time() - start) * 1000

print(f"  Large context indexing:")
print(f"    Chars: {len(large_context)}")
print(f"    Chunks: {vfs_large.total_chunks}")
print(f"    Time: {index_time:.1f}ms")

start = time.time()
search_results = vfs_large.search("function_25")
search_time = (time.time() - start) * 1000

print(f"  Search performance:")
print(f"    Query: 'function_25'")
print(f"    Results: {len(search_results)}")
print(f"    Time: {search_time:.3f}ms")

print("\n" + "=" * 60)
print("[OK] All tests completed!")
print("=" * 60)
