# 增强记忆系统使用指南

## 1. 系统概述

增强记忆系统（Enhanced Memory System）是基于Claude-Mem理念实现的智能记忆管理系统，旨在为LivingTree AI Agent提供跨会话的持久记忆能力。

### 核心功能

- **跨会话持久记忆**：记忆在会话间持久保存，避免重复解释
- **智能记忆压缩**：自动压缩记忆内容，减少存储和检索成本
- **语义搜索能力**：基于向量数据库的语义搜索，提高搜索准确性
- **渐进式记忆检索**：优化令牌使用效率，智能构建上下文

## 2. 快速开始

### 2.1 初始化系统

```python
from core.enhanced_memory import get_enhanced_memory_system

# 获取增强记忆系统实例
memory_system = get_enhanced_memory_system()
```

### 2.2 会话管理

```python
# 开始新会话
session_id = memory_system.start_session({
    "user": "用户名",
    "purpose": "会话目的"
})

# 结束会话
memory_system.end_session("会话摘要")
```

### 2.3 添加记忆

```python
# 添加记忆项
memory_id = memory_system.add_memory(
    "这是一条记忆内容",
    tags=["标签1", "标签2"]  # 可选标签
)
```

### 2.4 搜索记忆

```python
# 搜索记忆
results = memory_system.search_memory(
    "搜索关键词",
    limit=10,  # 结果数量限制
    use_semantic=True  # 是否使用语义搜索
)

# 遍历搜索结果
for item in results:
    print(f"摘要: {item.summary}")
    print(f"内容: {item.content}")
    print(f"标签: {item.tags}")
```

### 2.5 检索上下文

```python
# 检索上下文（用于构建提示词）
context = memory_system.retrieve_context(
    "查询内容",
    max_tokens=2000,  # 最大令牌数
    include_full_content=True  # 是否包含完整内容
)

# 使用上下文构建提示词
summaries = context.get("summaries", [])
detailed_items = context.get("detailed_items", [])
tokens_used = context.get("tokens_used", 0)
```

## 3. 系统架构

### 3.1 核心模块

| 模块 | 功能 | 文件位置 |
|------|------|----------|
| 核心系统 | 记忆管理和会话管理 | `core/enhanced_memory/core.py` |
| 嵌入生成 | 语义嵌入向量生成 | `core/enhanced_memory/embedding.py` |
| 令牌优化 | 令牌使用效率优化 | `core/enhanced_memory/token_optimizer.py` |

### 3.2 数据存储

- **SQLite数据库**：存储记忆项和会话信息
- **向量存储**：存储语义嵌入向量，支持语义搜索

## 4. 高级功能

### 4.1 记忆价值评估

系统会自动评估记忆的价值等级：
- **LOW** (0)：噪音信息
- **MEDIUM** (1)：一般信息
- **HIGH** (2)：重要事实
- **CRITICAL** (3)：核心知识

### 4.2 智能压缩

系统会自动压缩长文本，生成摘要，减少存储和检索成本。

### 4.3 渐进式检索

系统采用渐进式检索策略：
1. 先获取摘要级别的信息
2. 根据令牌预算，逐步获取详细内容
3. 优化令牌使用，确保在预算范围内获取最有价值的信息

### 4.4 语义搜索

系统支持基于向量的语义搜索，能够理解查询的语义意图，返回最相关的记忆项。

## 5. 配置选项

```python
# 系统配置
memory_system.config = {
    "auto_compress": True,        # 自动压缩
    "max_content_length": 5000,   # 最大内容长度
    "summary_length": 100,        # 摘要长度
    "embedding_dim": 128,         # 嵌入向量维度
}
```

## 6. 性能优化

### 6.1 令牌使用优化

- 使用 `max_tokens` 参数控制上下文大小
- 优先使用摘要级别的信息，仅在必要时获取详细内容
- 利用语义搜索提高搜索准确性，减少无关结果

### 6.2 存储优化

- 系统会自动压缩长文本
- 定期清理低价值记忆
- 优化数据库索引，提高查询速度

## 7. 示例代码

### 7.1 完整使用示例

```python
from core.enhanced_memory import get_enhanced_memory_system

# 初始化系统
memory_system = get_enhanced_memory_system()

# 开始会话
session_id = memory_system.start_session({"user": "开发者", "purpose": "项目开发"})

# 添加项目相关记忆
memory_system.add_memory(
    "项目使用Python 3.11开发，使用PyQt6构建界面",
    tags=["项目", "技术栈"]
)

memory_system.add_memory(
    "数据库使用SQLite，存储用户数据和配置信息",
    tags=["数据库", "配置"]
)

# 搜索相关记忆
results = memory_system.search_memory("技术栈")
print("技术栈相关记忆:")
for item in results:
    print(f"- {item.summary}")

# 检索上下文用于提示词
context = memory_system.retrieve_context("如何实现用户认证", max_tokens=1000)
print(f"\n检索到 {len(context['summaries'])} 条摘要")
print(f"使用令牌数: {context['tokens_used']}")

# 结束会话
memory_system.end_session("添加了项目技术栈和数据库相关记忆")

# 获取统计信息
stats = memory_system.get_stats()
print(f"\n系统统计:")
print(f"记忆项数量: {stats['memory_items']}")
print(f"会话数量: {stats['sessions']}")
```

### 7.2 语义搜索示例

```python
# 语义搜索示例
results = memory_system.search_memory("编程语言", use_semantic=True)
print("语义搜索结果:")
for i, item in enumerate(results, 1):
    print(f"{i}. {item.summary}")
    print(f"   标签: {item.tags}")
```

## 8. 故障排除

### 8.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 搜索结果不相关 | 关键词匹配不准确 | 使用语义搜索 `use_semantic=True` |
| 令牌使用过多 | 上下文过大 | 减少 `max_tokens` 参数 |
| 记忆项重复 | 重复添加相同内容 | 检查内容是否已存在 |

### 8.2 性能问题

- **搜索速度慢**：检查数据库索引，清理低价值记忆
- **内存使用高**：减少同时处理的记忆项数量
- **响应时间长**：优化嵌入向量生成，考虑使用更高效的嵌入模型

## 9. 未来规划

- 集成更先进的嵌入模型，提高语义搜索准确性
- 添加记忆分类和标签管理功能
- 实现记忆关联分析，发现记忆间的联系
- 支持多语言记忆管理
- 提供Web界面，方便用户管理和查看记忆

## 10. 结论

增强记忆系统为LivingTree AI Agent提供了强大的记忆管理能力，使AI能够在会话间保持连续性，减少重复解释，提高交互效率。通过智能压缩、语义搜索和渐进式检索等技术，系统在保证记忆质量的同时，优化了令牌使用效率，为AI代理的长期学习和知识积累提供了坚实的基础。