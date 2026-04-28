"""
知识库完整任务链测试
==================

测试流程：
1. 初始化知识库（扫描 C:\bak 文件夹）
2. 搜索："系统架构设计"
3. 推理："帮我生成ollama的部署文档"
"""

import sys
import os
import time
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
from client.src.business.md_to_doc.knowledge_base import (
    KnowledgeBaseManager,
    create_local_source,
    SourceType,
    SourceConfig,
    KnowledgeSource,
)
from client.src.business.smart_incremental_indexer import SmartIncrementalIndexer
from core.ollama_client import OllamaClient


def print_header(title: str):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_step(step: int, title: str):
    """打印步骤"""
    print(f"\n>>> 步骤 {step}: {title}")
    print("-" * 50)


def scan_folder(folder_path: str) -> list:
    """
    扫描文件夹中的文件，返回文档列表
    """
    documents = []
    supported_extensions = {'.md', '.txt', '.py', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg'}

    if not os.path.exists(folder_path):
        print(f"  [警告] 文件夹不存在: {folder_path}")
        return documents

    print(f"  [扫描] 开始扫描文件夹: {folder_path}")

    for root, dirs, files in os.walk(folder_path):
        # 跳过隐藏目录和特定目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv']]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in supported_extensions:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    rel_path = os.path.relpath(file_path, folder_path)
                    doc = {
                        "id": file_path,
                        "title": os.path.splitext(file)[0],
                        "content": content,
                        "type": ext[1:],  # 去掉点号
                        "path": rel_path,
                        "metadata": {
                            "file_path": file_path,
                            "extension": ext,
                            "size": len(content),
                        }
                    }
                    documents.append(doc)
                    print(f"    [+] {rel_path} ({len(content)} 字符)")
                except Exception as e:
                    print(f"    [!] 读取失败 {file}: {e}")

    print(f"  [完成] 共扫描到 {len(documents)} 个文档")
    return documents


def init_knowledge_base(folder_path: str) -> tuple:
    """
    初始化知识库

    Returns:
        tuple: (kb_layer, documents)
    """
    print_step(1, "初始化知识库")

    # 创建知识库层
    print("  [1] 创建 KnowledgeBaseLayer (混合检索引擎)")
    kb_layer = KnowledgeBaseLayer(
        embedding_model="BAAI/bge-small-zh",
        top_k=10,
        chunk_size=512,
        chunk_overlap=64
    )
    print(f"      - 嵌入模型: {kb_layer.embedding_model}")
    print(f"      - 分块大小: {kb_layer.chunk_size}")
    print(f"      - 重叠大小: {kb_layer.chunk_overlap}")

    # 扫描文件夹
    print("\n  [2] 扫描源文件夹")
    documents = scan_folder(folder_path)

    if not documents:
        print("  [警告] 没有找到文档，添加测试数据...")

        # 添加测试文档
        test_docs = [
            {
                "id": "test_001",
                "title": "系统架构设计指南",
                "content": """
                系统架构设计是软件工程的核心环节。一个好的架构需要满足以下原则：

                1. 模块化：将系统拆分为独立的模块，降低耦合度
                2. 可扩展性：设计应支持功能的扩展
                3. 高可用：确保系统的稳定性和容错能力
                4. 性能优化：考虑响应时间和资源利用率

                常见架构模式：
                - MVC (Model-View-Controller)
                - 微服务架构
                - 事件驱动架构
                - 分层架构
                """,
                "type": "md",
                "metadata": {"source": "test"}
            },
            {
                "id": "test_002",
                "title": "Ollama 部署文档",
                "content": """
                # Ollama 部署指南

                ## 安装

                ### macOS
                ```bash
                brew install ollama
                ```

                ### Linux
                ```bash
                curl -fsSL https://ollama.com/install.sh | sh
                ```

                ### Windows
                从官网下载安装包进行安装

                ## 使用

                ### 运行模型
                ```bash
                ollama run llama2
                ```

                ### 查看可用模型
                ```bash
                ollama list
                ```

                ### 自定义模型
                Modelfile 支持自定义模型配置

                ## API 调用
                ```python
                import ollama
                response = ollama.chat(model='llama2', messages=[
                    {'role': 'user', 'content': 'Hello!'}
                ])
                ```
                """,
                "type": "md",
                "metadata": {"source": "test"}
            }
        ]
        for doc in test_docs:
            kb_layer.add_document(doc)
        print(f"  [完成] 添加了 {len(test_docs)} 个测试文档")
        return kb_layer, test_docs

    # 添加文档到知识库
    print("\n  [3] 将文档添加到知识库")
    total_chunks = 0
    for doc in documents:
        chunks = kb_layer.add_document(doc)
        total_chunks += chunks
        print(f"      {doc['title']}: {chunks} 个分块")

    print(f"\n  [完成] 知识库初始化完成!")
    print(f"      - 文档数: {len(documents)}")
    print(f"      - 分块数: {total_chunks}")

    # 打印统计信息
    stats = kb_layer.get_stats()
    print(f"\n  [统计]")
    for key, value in stats.items():
        print(f"      - {key}: {value}")

    return kb_layer, documents


def search_knowledge(kb_layer: KnowledgeBaseLayer, query: str) -> list:
    """
    搜索知识

    Args:
        kb_layer: 知识库层
        query: 查询文本

    Returns:
        list: 搜索结果
    """
    print_step(2, f"搜索: '{query}'")

    start_time = time.time()
    results = kb_layer.search(query, top_k=5, alpha=0.6)
    elapsed = time.time() - start_time

    print(f"\n  [搜索完成] 耗时: {elapsed:.3f}s")
    print(f"  [结果] 找到 {len(results)} 个匹配结果")

    if not results:
        print("  [提示] 没有找到匹配结果，尝试其他关键词")
        return []

    print("\n  [匹配详情]")
    for i, result in enumerate(results, 1):
        print(f"\n  --- 结果 {i} ---")
        print(f"  标题: {result.get('title', 'N/A')}")
        print(f"  类型: {result.get('type', 'N/A')}")
        print(f"  综合分数: {result.get('score', 0):.4f}")
        print(f"    - 向量分数: {result.get('vector_score', 0):.4f}")
        print(f"    - BM25分数: {result.get('bm25_score', 0):.4f}")

        content = result.get('content', '')[:200]
        print(f"  内容预览: {content}...")

    return results


async def reasoning_with_knowledge(
    kb_layer: KnowledgeBaseLayer,
    documents: list,
    query: str
) -> dict:
    """
    基于知识库进行推理生成

    Args:
        kb_layer: 知识库层
        documents: 文档列表
        query: 推理任务

    Returns:
        dict: 推理结果
    """
    print_step(3, f"推理任务: '{query}'")

    # 1. 检索相关知识
    print("\n  [1] 检索相关知识...")

    # 从查询中提取关键词进行检索
    keywords = ["ollama", "部署", "安装", "deploy"]
    all_results = []

    for kw in keywords:
        results = kb_layer.search(kw, top_k=3, alpha=0.6)
        all_results.extend(results)

    # 去重
    seen = set()
    unique_results = []
    for r in all_results:
        if r['id'] not in seen:
            seen.add(r['id'])
            unique_results.append(r)

    print(f"      找到 {len(unique_results)} 条相关知识")

    # 2. 构建上下文
    print("\n  [2] 构建上下文...")

    context_parts = []
    for i, result in enumerate(unique_results[:3], 1):
        context_parts.append(f"[文档 {i}] {result['title']}\n{result['content'][:300]}...")

    context = "\n\n".join(context_parts)

    print(f"      上下文长度: {len(context)} 字符")

    # 3. 调用 Ollama 生成
    print("\n  [3] 调用 Ollama 进行推理...")

    ollama_client = OllamaClient()

    # 检查 Ollama 连接
    if not ollama_client.is_available():
        print("      [警告] Ollama 服务未运行，使用模拟响应")

        # 生成模拟的部署文档
        simulated_result = {
            "query": query,
            "context_docs": len(unique_results),
            "generation": generate_deployment_doc(query, unique_results),
            "model": "simulation",
            "elapsed": 0.0
        }
        return simulated_result

    # 构建提示
    prompt = f"""基于以下上下文信息，生成 Ollama 部署文档。

上下文信息:
{context}

用户请求: {query}

请生成一份完整的部署文档，包括：
1. 环境要求
2. 安装步骤
3. 配置说明
4. 使用示例
5. 常见问题

请用中文回答，格式清晰。
"""

    try:
        start_time = time.time()
        response = await ollama_client.async_generate(
            model="qwen2.5:1.5b",
            prompt=prompt,
            timeout=60
        )
        elapsed = time.time() - start_time

        result = {
            "query": query,
            "context_docs": len(unique_results),
            "generation": response.get('response', '无响应'),
            "model": "qwen2.5:1.5b",
            "elapsed": elapsed
        }

        print(f"      [完成] 生成完成，耗时: {elapsed:.2f}s")

    except Exception as e:
        print(f"      [错误] Ollama 调用失败: {e}")
        result = {
            "query": query,
            "context_docs": len(unique_results),
            "generation": generate_deployment_doc(query, unique_results),
            "model": "simulation",
            "error": str(e),
            "elapsed": 0.0
        }

    return result


def generate_deployment_doc(query: str, relevant_docs: list) -> str:
    """
    生成模拟的部署文档
    """
    doc = f"""# Ollama 部署文档

## 基于知识库检索生成

**查询**: {query}
**参考文档数**: {len(relevant_docs)}

---

## 1. 环境要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Linux/macOS/Windows |
| 内存 | >= 8GB (推荐 16GB) |
| 磁盘 | >= 10GB 可用空间 |
| GPU | NVIDIA GPU (可选，用于加速) |

---

## 2. 安装步骤

### 2.1 Linux/macOS

```bash
# 使用安装脚本
curl -fsSL https://ollama.com/install.sh | sh

# 验证安装
ollama --version
```

### 2.2 Windows

1. 访问 https://ollama.com/download
2. 下载 Windows 安装包 (.exe)
3. 运行安装程序
4. 在命令行验证: `ollama --version`

### 2.3 Docker 部署

```bash
# 拉取镜像
docker pull ollama/ollama

# 运行容器
docker run -d -v ollama-data:/root/.ollama \\
  -p 11434:11434 \\
  --name ollama \\
  ollama/ollama
```

---

## 3. 配置说明

### 3.1 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| OLLAMA_HOST | 服务监听地址 | 127.0.0.1 |
| OLLAMA_PORT | 服务端口 | 11434 |
| OLLAMA_MODELS | 模型存储路径 | ~/.ollama/models |

### 3.2 GPU 配置

对于 NVIDIA GPU，确保安装 CUDA 驱动后，Ollama 会自动识别。

---

## 4. 使用示例

### 4.1 拉取模型

```bash
ollama pull llama2
ollama pull mistral
ollama pull codellama
```

### 4.2 运行模型

```bash
# 交互式对话
ollama run llama2

# 单次请求
ollama run llama2 "Hello, how are you?"
```

### 4.3 API 调用

```python
import requests

response = requests.post("http://localhost:11434/api/generate", json={
    "model": "llama2",
    "prompt": "What is machine learning?",
    "stream": False
})

print(response.json()["response"])
```

---

## 5. 常见问题

### Q1: 启动失败

**症状**: `Error: listen tcp 127.0.0.1:11434: bind: address already in use`

**解决**:
```bash
# 检查是否有其他进程占用
lsof -i :11434

# 杀死占用进程或更改端口
export OLLAMA_PORT=11435
```

### Q2: 模型下载慢

**解决**: 使用镜像或手动下载模型文件

### Q3: GPU 未被使用

**解决**: 
1. 确认 NVIDIA 驱动已安装: `nvidia-smi`
2. 确认 CUDA 已安装
3. 检查 Ollama 日志: `journalctl -u ollama`

---

## 6. 参考资料

以下是与 Ollama 部署相关的知识库文档:

"""

    for i, doc in enumerate(relevant_docs[:3], 1):
        doc_title = doc.get('title', 'Unknown')
        doc_id = doc.get('id', 'N/A')
        doc_type = doc.get('type', 'unknown')
        doc_preview = doc.get('content', '')[:100]

        doc_entry = f"""
### {i}. {doc_title}

- **文档ID**: {doc_id}
- **类型**: {doc_type}
- **内容预览**: {doc_preview}...

"""
        doc += doc_entry

    doc += """

---

*本文档由知识库系统基于检索结果自动生成*
"""

    return doc


def print_result(result: dict):
    """打印推理结果"""
    print("\n" + "="*60)
    print("  推理结果")
    print("="*60)

    print(f"\n  [元信息]")
    print(f"    查询: {result.get('query', 'N/A')}")
    print(f"    参考文档数: {result.get('context_docs', 0)}")
    print(f"    使用模型: {result.get('model', 'N/A')}")
    print(f"    耗时: {result.get('elapsed', 0):.2f}s")

    if 'error' in result:
        print(f"    错误: {result['error']}")

    print(f"\n  [生成的文档]")
    print("-"*60)
    print(result.get('generation', '无内容'))
    print("-"*60)


async def main():
    """主函数"""
    print_header("知识库完整任务链测试")

    # 配置
    folder_path = r"C:\bak"

    # 步骤 1: 初始化知识库
    kb_layer, documents = init_knowledge_base(folder_path)

    # 步骤 2: 搜索
    search_query = "系统架构设计"
    results = search_knowledge(kb_layer, search_query)

    # 步骤 3: 推理
    reasoning_query = "帮我生成ollama的部署文档"
    result = await reasoning_with_knowledge(kb_layer, documents, reasoning_query)

    # 打印推理结果
    print_result(result)

    # 最终统计
    print_header("测试完成 - 统计信息")
    stats = kb_layer.get_stats()
    for key, value in stats.items():
        print(f"  - {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
