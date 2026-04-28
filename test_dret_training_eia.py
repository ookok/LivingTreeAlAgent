"""
DRET 真实训练测试 - 环评报告编写
=====================================
意图: 环评报告编写
递归深度: 5 层
知识库搜索: 污染物

模型配置:
- L0: SmolLM2.gguf → fallback qwen3.5:2b/qwen2.5:1.5b (Ollama)
- L3: qwen3.5:4b (Ollama)
- L4: qwen3.5:9b (Ollama)
"""

import sys
import os
import time
import json
from typing import Dict, List, Any, Optional

# ════════════════════════════════════════════════════════════════════════════
# 模型配置
# ════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("[CONFIG] 模型配置初始化")
print("=" * 70)

class ModelConfig:
    """模型配置"""
    # L0: 快速路由/意图分类
    L0_MODEL = "smollm2-test:latest"  # SmolLM2.gguf fallback
    L0_FALLBACKS = ["qwen3.5:2b", "qwen2.5:1.5b"]
    L0_API_BASE = "http://localhost:11434"
    
    # L3: 推理/意图理解
    L3_MODEL = "qwen3.5:4b"
    L3_API_BASE = "http://localhost:11434"
    
    # L4: 深度生成
    L4_MODEL = "qwen3.5:9b"
    L4_API_BASE = "http://localhost:11434"

config = ModelConfig()
print(f"  [L0] 模型: {config.L0_MODEL} (fallback: {config.L0_FALLBACKS})")
print(f"  [L3] 模型: {config.L3_MODEL}")
print(f"  [L4] 模型: {config.L4_MODEL}")
print(f"  [API] 端点: {config.L0_API_BASE}")

# ════════════════════════════════════════════════════════════════════════════
# Ollama 客户端封装
# ════════════════════════════════════════════════════════════════════════════
def get_ollama_client(model: str, api_base: str = "http://localhost:11434"):
    """获取 Ollama 客户端"""
    try:
        import ollama
        client = ollama.Client(host=api_base)
        # 验证连接
        client.models()
        print(f"  [] Ollama 连接成功: {model}")
        return client
    except Exception as e:
        print(f"  [] Ollama 连接失败: {e}")
        return None

def chat_with_ollama(client, model: str, messages: List[Dict], **kwargs) -> str:
    """调用 Ollama chat API"""
    try:
        response = client.chat(
            model=model,
            messages=messages,
            **kwargs
        )
        return response['message']['content']
    except Exception as e:
        return f"[Error: {e}]"

# ════════════════════════════════════════════════════════════════════════════
# 初始化模型客户端
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(" 初始化模型客户端")
print("=" * 70)

# L0 客户端
l0_client = get_ollama_client(config.L0_MODEL, config.L0_API_BASE)
if not l0_client:
    for fallback in config.L0_FALLBACKS:
        print(f"  尝试 fallback: {fallback}")
        l0_client = get_ollama_client(fallback, config.L0_API_BASE)
        if l0_client:
            config.L0_MODEL = fallback
            break

# L3 客户端 (复用)
l3_client = l0_client  # 同一端点
l4_client = l0_client  # 同一端点

print(f"  [L0] 当前使用: {config.L0_MODEL}")
print(f"  [L3] 当前使用: {config.L3_MODEL}")
print(f"  [L4] 当前使用: {config.L4_MODEL}")

# ════════════════════════════════════════════════════════════════════════════
# 导入 DRET 组件
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(" 加载 DRET 组件")
print("=" * 70)

try:
    from core.skill_evolution.dret_l04_integration import (
        L04IntegratedDRETSystem,
        L04IntegratedGapDetector,
        L04IntegratedConflictFinder,
        L04IntegratedMultiDebater,
        L04IntegratedRecursiveLearner,
        ExpertRoleFinder,
        create_l04_dret_system,
        RecursionDepthConfig
    )
    print("  [] DRET 组件导入成功")
except ImportError as e:
    print(f"  [] DRET 导入失败: {e}")
    sys.exit(1)

try:
    from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
    print("  [] KnowledgeBaseLayer 导入成功")
except ImportError as e:
    print(f"  [] KnowledgeBaseLayer 导入失败: {e}")
    KnowledgeBaseLayer = None

# ════════════════════════════════════════════════════════════════════════════
# 初始化知识库
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(" 初始化知识库")
print("=" * 70)

kb = KnowledgeBaseLayer() if KnowledgeBaseLayer else None

# 添加环评相关文档到知识库
eia_documents = [
    {
        "id": "eia_001",
        "title": "大气污染物排放标准",
        "type": "regulation",
        "content": """
        环境空气质量标准规定了各项污染物的浓度限值。
        主要大气污染物包括：二氧化硫(SO2)、氮氧化物(NOx)、
        颗粒物(PM10、PM2.5)、一氧化碳(CO)、臭氧(O3)等。
        排放标准根据污染物的危害程度分为一级标准和二级标准。
        """
    },
    {
        "id": "eia_002",
        "title": "水污染物排放标准",
        "type": "regulation",
        "content": """
        水污染物是指导致水体质量下降的物质。
        主要水污染物包括：化学需氧量(COD)、生化需氧量(BOD5)、
        氨氮、总磷、总氮、重金属(汞、铅、镉、铬等)。
        工业废水必须经过处理达标后方可排放。
        """
    },
    {
        "id": "eia_003",
        "title": "固体废物处理处置",
        "type": "regulation",
        "content": """
        固体废物分为一般固废和危险废物。
        危险废物包括：废酸、废碱、重金属污泥、废有机溶剂、
        废矿物油、感染性废物等。
        必须按照危废管理要求进行收集、贮存、运输和处置。
        """
    },
    {
        "id": "eia_004",
        "title": "噪声污染防治",
        "type": "regulation",
        "content": """
        环境噪声污染防治法规定了各类区域的噪声限值。
        工业企业噪声源包括：机械设备噪声、空气动力性噪声、
        电磁噪声等。必须采取消声、隔声、减振等措施。
        """
    },
    {
        "id": "eia_005",
        "title": "环评报告编写规范",
        "type": "guide",
        "content": """
        环境影响评价报告书应当包括以下内容：
        1. 项目概况
        2. 建设项目周围环境现状
        3. 建设项目对环境可能造成影响的分析
        4. 环境保护措施及其经济技术论证
        5. 环境影响经济损益分析
        6. 环境影响评价结论
        """
    }
]

if kb:
    for doc in eia_documents:
        kb.add_document(doc)
    print(f"  [] 添加了 {len(eia_documents)} 篇环评文档到知识库")

# ════════════════════════════════════════════════════════════════════════════
# 初始化 DRET 系统
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(" 初始化 DRET 系统 (递归深度: 5)")
print("=" * 70)

# 创建 DRET 系统，递归深度 5
dret = create_l04_dret_system(
    max_recursion_depth=5,  # 用户指定 5 层
    enable_l04=True,
    enable_expert=True,
    llm_client=l4_client,
    l4_model=config.L4_MODEL
)

print(f"  [] DRET 系统初始化完成")
print(f"      递归深度: {dret.max_depth}")
print(f"      L4 启用: {dret.enable_l04}")

# ════════════════════════════════════════════════════════════════════════════
# 训练任务定义
# ════════════════════════════════════════════════════════════════════════════
INTENT = "环评报告编写"
SEARCH_QUERY = "污染物"
MAX_RECURSION = 5

print("\n" + "=" * 70)
print(f" 训练任务")
print("=" * 70)
print(f"  意图: {INTENT}")
print(f"  递归深度: {MAX_RECURSION}")
print(f"  搜索关键词: {SEARCH_QUERY}")

# ════════════════════════════════════════════════════════════════════════════
# 步骤 1: 意图分析 (L0 + L3)
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "-" * 70)
print(" 步骤 1: 意图分析 (L0 → L3)")
print("-" * 70)

# L0: 快速路由
l0_prompt = f"""分析以下意图，输出简短的分类标签：
意图: {INTENT}

输出格式: {{"domain": "领域", "task_type": "任务类型", "complexity": "复杂度(低/中/高)"}}"""

l0_result = chat_with_ollama(l0_client, config.L0_MODEL, [
    {"role": "user", "content": l0_prompt}
])

print(f"  [L0] 路由分析:")
print(f"        {l0_result[:200]}...")

# L3: 深度意图理解
l3_prompt = f"""深度分析以下意图，识别关键实体和关系：

意图: {INTENT}

请分析：
1. 核心任务是什么？
2. 需要哪些专业知识？
3. 涉及哪些利益相关方？
4. 有哪些潜在的知识空白？"""

l3_result = chat_with_ollama(l3_client, config.L3_MODEL, [
    {"role": "user", "content": l3_prompt}
])

print(f"\n  [L3] 深度理解:")
print(f"        {l3_result[:300]}...")

# ════════════════════════════════════════════════════════════════════════════
# 步骤 2: 专家角色匹配
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "-" * 70)
print(" 步骤 2: 专家角色匹配")
print("-" * 70)

expert_finder = ExpertRoleFinder(enable_expert=True)
best_expert = expert_finder.find_best_persona(INTENT, context="环评工程师需要编写报告")
expert_name = best_expert.get('persona_name', '通用专家')
expert_domain = best_expert.get('domain', 'general')
match_score = best_expert.get('match_score', 0)

print(f"  匹配专家: {expert_name}")
print(f"  领域: {expert_domain}")
print(f"  匹配度: {match_score:.2f}")

# ════════════════════════════════════════════════════════════════════════════
# 步骤 3: 知识库搜索 - 核心污染物
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "-" * 70)
print(f" 步骤 3: 知识库搜索 \"{SEARCH_QUERY}\"")
print("-" * 70)

# 搜索污染物相关内容
if kb:
    search_results = kb.search(SEARCH_QUERY, top_k=5)
    print(f"  找到 {len(search_results)} 条相关结果:\n")
    
    for i, result in enumerate(search_results, 1):
        print(f"  【结果 {i}】 {result.get('title', 'N/A')}")
        print(f"  类型: {result.get('type', 'N/A')} | 相关度: {result.get('score', 0):.3f}")
        content = result.get('content', '')
        print(f"  内容: {content[:150]}...")
        print()
else:
    print("  [跳过] 知识库未初始化")
    search_results = []

# ════════════════════════════════════════════════════════════════════════════
# 步骤 4: DRET 递归学习 (5 层)
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "-" * 70)
print(f" 步骤 4: DRET 递归学习 (深度 {MAX_RECURSION})")
print("-" * 70)

# 构建训练上下文
training_context = {
    "intent": INTENT,
    "l0_analysis": l0_result,
    "l3_analysis": l3_result,
    "expert_persona": expert_name,
    "knowledge_results": search_results
}

# 执行递归学习
print(f"\n  开始 {MAX_RECURSION} 层递归学习...\n")

recursion_log = []

for depth in range(1, MAX_RECURSION + 1):
    print(f"  ═══ 第 {depth}/{MAX_RECURSION} 层 ═══")
    
    layer_prompt = f"""【递归层级 {depth}/{MAX_RECURSION}】
    
你是 {expert_name}，专注于 {expert_domain} 领域。

当前任务: {INTENT}

已获取的知识:
{json.dumps(search_results, ensure_ascii=False, indent=2)[:500]}

请深度分析这一层级的问题:
1. 当前层面的核心问题是什么？
2. 需要进一步探究的子问题？
3. 与环评报告编写的关系？"""

    layer_result = chat_with_ollama(l4_client, config.L4_MODEL, [
        {"role": "user", "content": layer_prompt}
    ])
    
    print(f"  分析结果: {layer_result[:200]}...")
    print()
    
    recursion_log.append({
        "depth": depth,
        "analysis": layer_result,
        "expert": expert_name
    })

# ════════════════════════════════════════════════════════════════════════════
# 步骤 5: 综合知识库搜索
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "-" * 70)
print(" 步骤 5: 综合知识库扩展搜索")
print("-" * 70)

# 扩展搜索关键词
extended_queries = ["污染物", "排放标准", "环境影响", "环评报告", "污染防治"]

all_results = {}
for query in extended_queries:
    if kb:
        results = kb.search(query, top_k=3)
        all_results[query] = results
        print(f"  [{query}]: {len(results)} 条结果")

# ════════════════════════════════════════════════════════════════════════════
# 步骤 6: 生成报告摘要
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "-" * 70)
print(" 步骤 6: 生成训练报告")
print("-" * 70)

# 汇总所有发现
summary_prompt = f"""基于以下训练结果，生成环评报告编写指南摘要：

意图: {INTENT}
递归深度: {MAX_RECURSION}
专家角色: {expert_name}

知识库搜索结果:
{json.dumps(all_results, ensure_ascii=False, indent=2)[:1000]}

请生成:
1. 环评报告关键要素
2. 污染物识别要点
3. 后续行动建议"""

summary = chat_with_ollama(l4_client, config.L4_MODEL, [
    {"role": "user", "content": summary_prompt}
])

print(f"\n{summary}")

# ════════════════════════════════════════════════════════════════════════════
# 最终输出
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(" 训练完成 - 结果汇总")
print("=" * 70)

print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│  训练任务: {INTENT:<50} │
├─────────────────────────────────────────────────────────────────────┤
│  模型配置:                                                           │
│    L0: {config.L0_MODEL:<60} │
│    L3: {config.L3_MODEL:<60} │
│    L4: {config.L4_MODEL:<60} │
├─────────────────────────────────────────────────────────────────────┤
│  递归深度: {MAX_RECURSION:<60} │
│  专家角色: {expert_name:<57} │
├─────────────────────────────────────────────────────────────────────┤
│  知识库搜索 "{SEARCH_QUERY}":                                            │
│    找到 {len(search_results)} 条相关结果                                              │
└─────────────────────────────────────────────────────────────────────┘
""")

# ════════════════════════════════════════════════════════════════════════════
# 返回知识库搜索结果
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(" 知识库搜索结果 - \"污染物\"")
print("=" * 70)

for i, result in enumerate(search_results, 1):
    print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│  结果 {i}: {result.get('title', 'N/A'):<55} │
├─────────────────────────────────────────────────────────────────────┤
│  类型: {result.get('type', 'N/A'):<62} │
│  相关度: {result.get('score', 0):.3f:<60} │
├─────────────────────────────────────────────────────────────────────┤
│  内容:                                                               │
│  {result.get('content', '')[:70]:<68} │
│  {result.get('content', '')[70:140]:<68} │
└─────────────────────────────────────────────────────────────────────┘
""")

print("\n 训练完成！")
