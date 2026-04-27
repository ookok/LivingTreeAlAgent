# BookRAG 架构设计文档

> **灵感来源**: BookRAG 论文 - 处理长文档（书籍级）检索增强生成的模块化方法  
> **版本**: 2.1.0  
> **创建时间**: 2026-04-25  
> **模块位置**: `core/fusion_rag/`  
> **依赖模块**: FusionRAG 四层缓存架构、SemanticIndex 语义索引、EmbeddingEngine 向量嵌入

---

## 1. 概述

### 1.1 设计目标

BookRAG 模块旨在为 FusionRAG 系统引入**信息流类型（IFT - Information Flow Type）**驱动的模块化检索管道，实现：

- **自适应路由**: 根据查询复杂度自动选择最优检索策略
- **组合式管道**: 可插拔的检索操作符链
- **多跳推理**: 支持复杂的多步骤推理查询
- **全局聚合**: 高效处理需要跨越大量文档片段的聚合查询

### 1.2 核心价值

| 传统 RAG | BookRAG |
|----------|---------|
| 固定检索管道 | 动态组合检索操作符 |
| 单跳检索为主 | 支持多跳推理链 |
| 简单关键词匹配 | 信息气味（Information Scent）导向 |
| 难以处理复杂查询 | 智能路由到合适管道 |

### 1.3 模块架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         BookRAG 统一入口                         │
│                    BookRAG.retrieve(query, kb)                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      IFT 查询分类器                              │
│              IFTQueryClassifier.classify(query)                  │
│  ┌─────────────┬─────────────┬─────────────────────┐            │
│  │ SINGLE_HOP  │ MULTI_HOP   │ GLOBAL_AGGREGATION  │            │
│  │ 单跳查询     │ 多跳查询     │ 全局聚合查询         │            │
│  └─────────────┴─────────────┴─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      检索管道编排器                              │
│              RetrievalPipeline.run(query, chunks)                │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    │
│  │Selector │───▶│Reasoner │───▶│Aggregator│───▶│Synthesizer│   │
│  │ 选择器   │    │ 推理器   │    │ 聚合器   │    │ 合成器   │    │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         检索结果                                 │
│                    RetrievalResult                                │
│         answer + sources + confidence + pipeline_used            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 信息流类型（IFT）分类

### 2.1 三种查询类型

```python
class IFTQueryType(Enum):
    SINGLE_HOP = "single_hop"           # 单跳查询
    MULTI_HOP = "multi_hop"            # 多跳查询
    GLOBAL_AGGREGATION = "global_aggregation"  # 全局聚合
```

### 2.2 类型定义与特征

| 类型 | 特征 | 典型问题 | 推荐管道 |
|------|------|----------|----------|
| **SINGLE_HOP** | 单一事实查找 | "什么是机器学习？" | Selector → Synthesizer |
| | | "Python 的创始人是谁？" | |
| **MULTI_HOP** | 多步推理/比较 | "Python 和 Java 的区别是什么？" | Selector → Reasoner → Synthesizer |
| | | "为什么 Transformer 需要注意力机制？" | |
| **GLOBAL_AGGREGATION** | 跨文档统计/汇总 | "文档中一共提到了多少次 AI？" | Selector → Aggregator → Synthesizer |
| | | "列出所有提到的算法" | |

### 2.3 分类规则

#### 2.3.1 多跳关键词模式

```python
# 英文模式
r'\bvs\b', r'\bversus\b', r'\bcompare\b', r'\bdifference\b'
r'\bbecause\b', r'\btherefore\b', r'\bwhy\b', r'\bhow does.*work\b'

# 中文模式
r'和.*区别', r'与.*区别', r'比较', r'对比'
r'为什么', r'因为', r'所以', r'因此', r'如何工作'
```

#### 2.3.2 全局聚合关键词模式

```python
# 英文模式
r'\bhow many\b', r'\bhow much\b', r'\btotal\b', r'\bcount\b'
r'\blist all\b', r'\bsummarize\b', r'\bevery\b'

# 中文模式
r'多少', r'一共', r'总计', r'总数'
r'列出', r'列举', r'所有', r'全部'
r'总结', r'概括', r'汇总', r'统计'
```

#### 2.3.3 分类决策逻辑

```
score >= 0.5 → GLOBAL_AGGREGATION (聚合查询)
score >= 0.4 → MULTI_HOP (多跳查询)
score >= 0.3 且 multi_hop < 0.2 → SINGLE_HOP (单跳查询)
默认 → SINGLE_HOP
```

### 2.4 分类结果数据结构

```python
@dataclass
class IFTClassificationResult:
    query_type: IFTQueryType              # 查询类型
    confidence: float                     # 置信度 0.0 ~ 1.0
    reasoning: List[str]                   # 分类推理过程
    recommended_pipeline: List[str]        # 推荐的管道配置
    keywords_matched: List[str]           # 匹配的关键词
    metadata: Dict[str, Any]              # 额外元数据
```

---

## 3. 检索操作符架构

### 3.1 四种核心操作符

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Selector  │ ──▶ │   Reasoner  │ ──▶ │  Aggregator │ ──▶ │ Synthesizer │
│   (选择器)   │     │   (推理器)   │     │   (聚合器)   │     │   (合成器)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │                   │
   Top-k 切块         关系推理           全局统计            最终答案
   相关性打分         跨片段链接         分布式聚合            生成
```

### 3.2 Selector（选择器）

**职责**: 从大量块中选择最相关的 Top-k 块

**配置参数**:
```python
class Selector:
    def __init__(
        self,
        top_k: int = 10,                    # 返回 Top-k 块数
        min_score: float = 0.1,             # 最小相关分数
        use_hybrid: bool = True,            # 混合策略开关
        semantic_weight: float = 0.6,       # 语义权重
        keyword_weight: float = 0.3,        # 关键词权重
        bm25_weight: float = 0.1,           # BM25 权重
    )
```

**评分策略**:
1. **语义相似度**: 基于 embedding 的余弦相似度
2. **关键词密度**: 查询词在文档中的出现频率
3. **BM25 混合**: 结合文档长度归一化的相关性评分

### 3.3 Reasoner（推理器）

**职责**: 分析块之间的关系，构建推理链

**配置参数**:
```python
class Reasoner:
    def __init__(
        self,
        max_hops: int = 3,                  # 最大推理跳数
        relation_threshold: float = 0.3,    # 关系阈值
    )
```

**功能**:
1. **实体共现分析**: 识别同一文档中共同出现的实体
2. **引用关系检测**: 识别"如上所述"、"见第X节"等引用
3. **因果链路构建**: 建立实体间的关系图
4. **跨块排序**: 根据关系强度重新排序

### 3.4 Aggregator（聚合器）

**职责**: 处理全局聚合查询

**配置参数**:
```python
class Aggregator:
    def __init__(
        self,
        aggregation_type: str = "auto",     # 聚合类型
        top_n: int = 20,                    # 返回 Top-n 结果
    )
```

**聚合类型**:
| 类型 | 关键词 | 功能 |
|------|--------|------|
| `count` | 多少/how many/count | 计数统计 |
| `distinct` | 哪些/list/all | 去重查找 |
| `group` | 分类/group/类别 | 分组聚合 |
| `sort` | 默认 | 排序汇总 |

### 3.5 Synthesizer（合成器）

**职责**: 将检索结果合成为最终答案

**配置参数**:
```python
class Synthesizer:
    def __init__(
        self,
        max_context_length: int = 4000,     # 最大上下文长度
        include_citations: bool = True,    # 是否包含引用
        format_type: str = "auto",          # 输出格式
    )
```

**功能**:
1. **上下文压缩**: 截断至 max_context_length
2. **答案片段拼接**: 按相关性拼接答案片段
3. **引用标注**: 生成来源引用列表
4. **格式输出**: 支持段落/列表/编号格式

---

## 4. 管道组合策略

### 4.1 预定义管道模板

```python
PIPELINE_TEMPLATES = {
    "simple": ["selector", "synthesizer"],                              # 单跳
    "reasoning": ["selector", "reasoner", "synthesizer"],              # 多跳
    "aggregation": ["selector", "aggregator", "synthesizer"],          # 全局聚合
    "full": ["selector", "reasoner", "aggregator", "synthesizer"],    # 完整管道
}
```

### 4.2 动态管道选择

```
用户查询
    │
    ▼
┌─────────────────────────────────────────┐
│           IFT 分类器                     │
│  SINGLE_HOP / MULTI_HOP / GLOBAL_AGG   │
└─────────────────────────────────────────┘
    │
    ├── SINGLE_HOP ──────────────────────▶ simple pipeline
    │                                        [selector → synthesizer]
    │
    ├── MULTI_HOP ─────────────────────────▶ reasoning pipeline
    │                                        [selector → reasoner → synthesizer]
    │
    └── GLOBAL_AGGREGATION ───────────────▶ aggregation pipeline
                                            [selector → aggregator → synthesizer]
```

### 4.3 BookRAGConfig 配置

```python
@dataclass
class BookRAGConfig:
    # 选择器配置
    selector_top_k: int = 10
    selector_min_score: float = 0.1
    use_hybrid_similarity: bool = True
    
    # 推理器配置
    max_reasoning_hops: int = 3
    relation_threshold: float = 0.3
    
    # 聚合器配置
    aggregation_top_n: int = 20
    
    # 合成器配置
    max_context_length: int = 4000
    include_citations: bool = True
    
    # 管道映射
    default_pipeline: str = "auto"
    pipeline_mapping: Dict[str, List[str]] = {
        "single_hop": ["selector", "synthesizer"],
        "multi_hop": ["selector", "reasoner", "synthesizer"],
        "global_aggregation": ["selector", "aggregator", "synthesizer"],
    }
```

---

## 5. BookRAG 统一入口

### 5.1 核心接口

```python
class BookRAG:
    def __init__(
        self,
        config: Optional[BookRAGConfig] = None,
        knowledge_base: Optional[Any] = None,
    )
    
    def retrieve(
        self,
        query: str,
        chunks: Optional[List[Chunk]] = None,
        knowledge_base: Optional[Any] = None,
        return_classification: bool = False,
    ) -> Union[RetrievalResult, tuple]
    
    def classify(self, query: str) -> IFTClassificationResult
    
    def get_pipeline_for_query(self, query: str) -> List[str]
```

### 5.2 检索结果数据结构

```python
@dataclass
class RetrievalResult:
    answer: str                    # 最终答案
    sources: List[Chunk]          # 来源块列表
    confidence: float             # 置信度
    pipeline_used: List[str]      # 使用的管道
    reasoning: List[str]          # 推理过程
    metadata: Dict[str, Any]       # 额外元数据（含 IFT 分类）
```

### 5.3 使用示例

```python
from core.fusion_rag import (
    BookRAG,
    IFTQueryClassifier,
    RetrievalPipeline,
    Chunk,
)

# 方式 1: 直接使用 BookRAG
rag = BookRAG()
result = rag.retrieve(
    "Python 和 Java 有什么区别？",
    chunks=[Chunk(id="1", content="...")]
)
print(result.answer)

# 方式 2: 单独使用 IFT 分类器
classifier = IFTQueryClassifier()
classification = classifier.classify("文档中提到了哪些算法？")
print(f"类型: {classification.query_type}")
print(f"置信度: {classification.confidence}")

# 方式 3: 自定义管道
pipeline = RetrievalPipeline(default_pipeline="reasoning")
result = pipeline.run(query, chunks, pipeline=["selector", "reasoner", "synthesizer"])

# 方式 4: 快捷函数
from core.fusion_rag import bookrag_retrieve, bookrag_classify
result = bookrag_retrieve("Python 是什么？", chunks)
classification = bookrag_classify("比较两种语言")
```

---

## 6. 与现有模块集成

### 6.1 集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    BookRAG 模块边界                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ift_classifier│  │retrieval_   │  │  book_rag   │            │
│  │             │  │  operators  │  │             │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FusionRAG 核心模块                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Semantic   │  │ Embedding   │  │ Intelligent │            │
│  │   Index    │  │  Engine     │  │   Router    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 与 SemanticIndex 集成

```python
# SemanticIndex 提供语义块
from core.semantic_index import SemanticChunk, SemanticIndexer

# BookRAG 使用 SemanticChunk
chunks = [Chunk(id=c.chunk_id, content=c.content, metadata=c.metadata) 
          for c in semantic_chunks]
result = bookrag_retrieve(query, chunks)
```

### 6.3 与 KnowledgeBaseLayer 集成

```python
# KnowledgeBaseLayer 提供混合检索
from core.fusion_rag import KnowledgeBaseLayer

class KnowledgeBaseLayer:
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        # 混合向量 + BM25 检索
        ...

# BookRAG 可以直接使用
kb = KnowledgeBaseLayer()
rag = BookRAG(knowledge_base=kb)
result = rag.retrieve(query)
```

### 6.4 与 IntelligentRouter 集成

```python
# 在路由层添加 IFT 感知
class IFTAwareRouter(IntelligentRouter):
    def route(self, query: str) -> str:
        # 使用 IFT 分类结果指导路由
        classification = IFTQueryClassifier().classify(query)
        
        if classification.query_type == IFTQueryType.GLOBAL_AGGREGATION:
            return self.route_to_knowledge_base(query)
        elif classification.query_type == IFTQueryType.MULTI_HOP:
            return self.route_with_reasoning(query)
        else:
            return super().route(query)
```

---

## 7. 实现文件清单

| 文件 | 职责 | 行数 | 状态 |
|------|------|------|------|
| `ift_classifier.py` | IFT 查询类型分类器 | ~286 | ✅ 完整 |
| `retrieval_operators.py` | 四种检索操作符 + 管道编排 | ~1021 | ✅ 完整 |
| `book_rag.py` | BookRAG 统一入口 | ~311 | ✅ 完整 |
| `__init__.py` | 模块导出 | ~129 | ✅ 完整 |

---

## 8. 测试示例

```python
# test_bookrag.py
import pytest
from core.fusion_rag import (
    BookRAG,
    IFTQueryClassifier,
    Chunk,
    IFTQueryType,
)

def test_single_hop_classification():
    """测试单跳查询分类"""
    classifier = IFTQueryClassifier()
    result = classifier.classify("什么是 Python？")
    
    assert result.query_type == IFTQueryType.SINGLE_HOP
    assert result.confidence > 0.5

def test_multi_hop_classification():
    """测试多跳查询分类"""
    classifier = IFTQueryClassifier()
    result = classifier.classify("Python 和 Java 有什么区别？")
    
    assert result.query_type == IFTQueryType.MULTI_HOP

def test_aggregation_classification():
    """测试聚合查询分类"""
    classifier = IFTQueryClassifier()
    result = classifier.classify("文档中一共提到了多少次 AI？")
    
    assert result.query_type == IFTQueryType.GLOBAL_AGGREGATION

def test_bookrag_retrieval():
    """测试 BookRAG 检索"""
    rag = BookRAG()
    chunks = [
        Chunk(id="1", content="Python 是一种编程语言。"),
        Chunk(id="2", content="Java 也是一种编程语言。"),
    ]
    
    result = rag.retrieve("Python 是什么？", chunks)
    
    assert result.sources is not None
    assert len(result.sources) > 0
```

---

## 9. 性能考量

### 9.1 时间复杂度

| 操作 | 复杂度 | 说明 |
|------|--------|------|
| IFT 分类 | O(n) | 正则匹配，n 为模式数 |
| Selector | O(m log m) | m 为块数量，排序成本 |
| Reasoner | O(k²) | k 为实体数量 |
| Aggregator | O(m) | 线性扫描 |
| Synthesizer | O(m) | 上下文压缩 |

### 9.2 优化建议

1. **Selector 优化**: 使用向量索引加速 top-k 查询
2. **Reasoner 优化**: 限制最大实体数量
3. **Aggregator 优化**: 使用流式处理处理大文档
4. **缓存策略**: 缓存 IFT 分类结果

---

## 10. 未来扩展

- [ ] **LLM 驱动的分类器**: 用小模型替代关键词规则
- [ ] **自适应管道**: 根据中间结果动态调整管道
- [ ] **增量推理**: 支持思维链（Chain of Thought）追踪
- [ ] **多文档协调**: 跨知识库的联合检索
- [ ] **反馈学习**: 根据用户反馈优化管道选择
- [ ] **流式处理**: 支持大规模文档的流式检索
- [ ] **增量 Embedding**: 动态更新向量索引

---

## 11. 参考资料

- BookRAG Paper (arXiv)
- LangChain Retrieval QA
- HippoRAG Architecture
- Information Scent Theory (CHV)
- FusionRAG 四层缓存架构
- SemanticIndex 语义索引系统

---

*文档版本: 2.1.0 | 最后更新: 2026-04-25*
