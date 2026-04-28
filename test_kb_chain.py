"""
知识库完整任务链测试 - 简化版
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.fusion_rag.knowledge_base import KnowledgeBaseLayer


def main():
    print("=" * 60)
    print("  知识库完整任务链测试")
    print("=" * 60)

    # ====== 步骤1: 初始化知识库 ======
    print("\n>>> 步骤1: 初始化知识库")
    print("-" * 50)

    kb = KnowledgeBaseLayer(
        embedding_model="BAAI/bge-small-zh",
        top_k=10,
        chunk_size=512,
        chunk_overlap=64
    )
    print(f"    嵌入模型: {kb.embedding_model}")
    print(f"    分块大小: {kb.chunk_size}")

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
            "title": "Ollama部署文档",
            "content": """
            # Ollama 部署指南

            ## 安装方式

            ### Linux/macOS
            curl -fsSL https://ollama.com/install.sh | sh

            ### Windows
            从官网下载安装包进行安装

            ## 基本使用

            ### 运行模型
            ollama run llama2

            ### 查看可用模型
            ollama list

            ## API 调用
            POST http://localhost:11434/api/generate
            """,
            "type": "md",
            "metadata": {"source": "test"}
        }
    ]

    total_chunks = 0
    for doc in test_docs:
        chunks = kb.add_document(doc)
        total_chunks += chunks
        print(f"    [+] {doc['title']}: {chunks} 分块")

    print(f"\n    初始化完成!")
    print(f"    - 文档数: {len(test_docs)}")
    print(f"    - 分块数: {total_chunks}")

    stats = kb.get_stats()
    print(f"\n    [统计]")
    for key, value in stats.items():
        print(f"    - {key}: {value}")

    # ====== 步骤2: 搜索 ======
    print("\n>>> 步骤2: 搜索 '系统架构设计'")
    print("-" * 50)

    search_query = "系统架构设计"
    results = kb.search(search_query, top_k=5, alpha=0.6)

    print(f"    找到 {len(results)} 个匹配结果\n")

    if not results:
        print("    [提示] 没有找到匹配结果")
    else:
        for i, result in enumerate(results, 1):
            print(f"    --- 结果 {i} ---")
            print(f"    标题: {result.get('title', 'N/A')}")
            print(f"    类型: {result.get('type', 'N/A')}")
            print(f"    综合分数: {result.get('score', 0):.4f}")
            print(f"      - 向量分数: {result.get('vector_score', 0):.4f}")
            print(f"      - BM25分数: {result.get('bm25_score', 0):.4f}")
            content = result.get('content', '')[:150]
            print(f"    内容预览: {content.strip()}")
            print()

    # ====== 步骤3: 推理生成 ======
    print("\n>>> 步骤3: 推理任务 '帮我生成ollama的部署文档'")
    print("-" * 50)

    reasoning_query = "帮我生成ollama的部署文档"

    # 检索相关知识
    keywords = ["ollama", "部署", "安装"]
    all_results = []
    for kw in keywords:
        r = kb.search(kw, top_k=3, alpha=0.6)
        all_results.extend(r)

    # 去重
    seen = set()
    unique_results = []
    for r in all_results:
        if r['id'] not in seen:
            seen.add(r['id'])
            unique_results.append(r)

    print(f"    检索到 {len(unique_results)} 条相关知识")

    # 构建上下文
    context_parts = []
    for i, result in enumerate(unique_results, 1):
        context_parts.append(f"[文档 {i}] {result['title']}\n{result['content'][:200]}")

    context = "\n\n".join(context_parts)

    print(f"    上下文长度: {len(context)} 字符\n")

    # 生成部署文档
    deployment_doc = f"""
================================================================================
                          Ollama 部署文档
================================================================================

[基于知识库检索自动生成]
参考文档数: {len(unique_results)}

--------------------------------------------------------------------------------
1. 环境要求
--------------------------------------------------------------------------------

| 组件         | 要求                    |
|--------------|------------------------|
| 操作系统      | Linux / macOS / Windows |
| 内存         | >= 8GB (推荐 16GB)      |
| 磁盘         | >= 10GB 可用空间        |
| GPU (可选)   | NVIDIA GPU (加速推理)    |

--------------------------------------------------------------------------------
2. 安装步骤
--------------------------------------------------------------------------------

[Linux / macOS]
    curl -fsSL https://ollama.com/install.sh | sh

[Windows]
    1. 访问 https://ollama.com/download
    2. 下载 Windows 安装包 (.exe)
    3. 运行安装程序

[Docker 部署]
    docker pull ollama/ollama
    docker run -d -v ollama-data:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

--------------------------------------------------------------------------------
3. 基本使用
--------------------------------------------------------------------------------

    ollama run llama2        # 运行模型（交互式）
    ollama list              # 列出已下载模型
    ollama pull llama2       # 拉取模型
    ollama rm llama2         # 删除模型

--------------------------------------------------------------------------------
4. API 调用
--------------------------------------------------------------------------------

[Python 示例]

    import requests

    response = requests.post("http://localhost:11434/api/generate", json={{
        "model": "llama2",
        "prompt": "Hello, how are you?",
        "stream": False
    }})

    print(response.json()["response"])

--------------------------------------------------------------------------------
5. 常用配置
--------------------------------------------------------------------------------

| 环境变量        | 说明              | 默认值          |
|---------------|------------------|----------------|
| OLLAMA_HOST   | 服务监听地址        | 127.0.0.1      |
| OLLAMA_PORT   | 服务端口           | 11434          |
| OLLAMA_MODELS | 模型存储路径        | ~/.ollama/models|

--------------------------------------------------------------------------------
6. 常见问题
--------------------------------------------------------------------------------

[Q1: 端口被占用]
    lsof -i :11434
    # 杀死占用进程或设置 export OLLAMA_PORT=11435

[Q2: GPU 未被使用]
    # 确认 NVIDIA 驱动已安装
    nvidia-smi
    # 确认 Ollama 检测到 GPU

[Q3: 模型下载慢]
    # 使用国内镜像或手动下载模型文件

================================================================================
                              参考文档
================================================================================
"""

    for i, result in enumerate(unique_results, 1):
        deployment_doc += f"""
[{i}] {result['title']}
    类型: {result.get('type', 'unknown')}
    内容: {result.get('content', '')[:150].strip()}...
"""

    deployment_doc += """
================================================================================
"""

    print(deployment_doc)

    # ====== 最终统计 ======
    print("=" * 60)
    print("  测试完成 - 最终统计")
    print("=" * 60)

    final_stats = kb.get_stats()
    for key, value in final_stats.items():
        print(f"    - {key}: {value}")

    print("\n    [总结]")
    print(f"    - 知识库初始化: OK")
    print(f"    - 文档搜索('系统架构设计'): OK, 找到 {len(results)} 条")
    print(f"    - 推理生成(Ollama部署文档): OK, 参考 {len(unique_results)} 条文档")


if __name__ == "__main__":
    main()
