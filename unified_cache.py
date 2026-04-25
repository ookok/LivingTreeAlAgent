# -*- coding: utf-8 -*-
"""
统一缓存接入层 - UnifiedCache
=============================

为 L0-L4 深度搜索链路提供统一的缓存接入。

设计原则：
- L0 路由缓存：直接复用 L0Router 内置的 LRUCache（smolllm2/router.py）
- Search 缓存：接入 CacheManager（L1/L2/L3 三级）
- L4 生成缓存：使用 ExactCacheLayer（LRU+SimHash）+ WriteBackCache（异步回填）
- 统计聚合：各层命中率统一上报

缓存层级架构：
┌─────────────────────────────────────────────┐
│  L0 Route Cache (smolllm2/router.py)       │  ← query hash → route decision
│  ┌─────────────────────────────────────────┐│
│  │  Memory: LRUCache (100条/24h)           ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  Search Cache (tier_model/cache_manager.py)│  ← query → search results
│  ┌─────────────────────────────────────────┐│
│  │  L1 Memory: LRUCache+热度加权 (15min)  ││
│  ├─────────────────────────────────────────┤│
│  │  L2 Local: SQLite WAL (24h)            ││
│  ├─────────────────────────────────────────┤│
│  │  L3 Semantic: FAISS向量 (阈值0.85)      ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│  L4 Response Cache (fusion_rag/exact_cache)│  ← md5(query+context) → answer
│  ┌─────────────────────────────────────────┐│
│  │  ExactCacheLayer: LRU+SimHash+布隆(7天)││
│  ├─────────────────────────────────────────┤│
│  │  WriteBackCache: 异步回填 L1/L2/L3     ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
"""

import hashlib
import time
import re
import json
import threading
import requests
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict

# 统一配置导入
try:
    from client.src.business.config import get_config, get_timeout
except ImportError:
    get_config = get_timeout = None


def _get_cache_timeout(name: str = "ollama") -> int:
    """获取缓存超时配置"""
    if get_timeout:
        try:
            return get_timeout(name)
        except Exception:
            pass
    # 默认值
    defaults = {"ollama_quick": 3, "ollama_normal": 5, "ollama_slow": 10}
    return defaults.get(name, 5)
from collections import OrderedDict
from datetime import datetime, timedelta

# 日志系统
from core.logger import get_logger
logger = get_logger("core.unified_cache")

# ── L0 Router 缓存 ──────────────────────────────────────────────────────────
try:
    from client.src.business.smolllm2.router import L0Router, LRUCache as L0LRUCache
    _L0_AVAILABLE = True
except ImportError:
    _L0_AVAILABLE = False

# ── 三级缓存 ──────────────────────────────────────────────────────────────────
try:
    from client.src.business.tier_model.cache_manager import CacheManager
    _CACHE_MGR_AVAILABLE = True
except ImportError:
    _CACHE_MGR_AVAILABLE = False

# ── 精确缓存 + 回填 ───────────────────────────────────────────────────────────
try:
    from client.src.business.fusion_rag.exact_cache import ExactCacheLayer
    from client.src.business.fusion_rag.write_back_cache import WriteBackCache
    _EXACT_CACHE_AVAILABLE = True
except ImportError:
    _EXACT_CACHE_AVAILABLE = False


# ════════════════════════════════════════════════════════════════════════════
# 增强1: Query 标准化 + 关键词提取（超长 query 截断 + 语义压缩）
# ════════════════════════════════════════════════════════════════════════════

class QueryNormalizer:
    """
    Query 标准化模块

    功能：
    1. 截断超长 query（避免 key 过长、向量质量下降）
    2. 提取核心关键词（语义压缩）
    3. 归一化数字、标点（提升相似命中）
    4. 生成多种 cache key（原始 / 标准化 / 关键词集）

    示例：
        normalize("2024年五一杭州有什么好玩的地方推荐？")
        → 标准化: "2024年五一杭州有什么好玩的地方推荐"（去标点+截断200字）
        → 关键词: {"杭州", "五一", "好玩", "地方", "推荐"}
    """

    # 中文停用词（不做关键词）
    STOP_WORDS = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
        "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
        "会", "着", "没有", "看", "好", "这", "那", "什么", "怎么",
        "可以", "能", "能吗", "吗", "呢", "吧", "啊", "哦", "嗯",
        "请问", "帮忙", "一下", "一下", "有没有", "是不是", "能不能",
        "哪里", "哪个", "哪些", "什么", "怎么样", "多少", "多久",
        "please", "the", "a", "an", "is", "are", "was", "were", "to", "of",
        "and", "or", "but", "in", "on", "at", "for", "with", "by",
    }

    def __init__(self, max_length: int = 200):
        self.max_length = max_length

    # 核心语义词表（高权重关键词，用户问 travel/city/地点类问题的核心词）
    CORE_WORDS = {
        # 地点/城市
        "杭州", "北京", "上海", "深圳", "成都", "南京", "武汉", "西安", "苏州", "重庆",
        "西湖", "故宫", "长城", "天安门", "颐和园", "灵隐寺", "千岛湖", "黄山", "泰山",
        # 动作/意图
        "旅游", "游玩", "好玩", "景点", "推荐", "攻略", "美食", "住宿", "酒店",
        "餐厅", "小吃", "特产", "购物", "交通", "路线", "行程", "规划",
        # 时间词（保留，但降权）
        "五一", "十一", "春节", "清明", "端午", "中秋", "元旦", "周末",
        "假期", "旅游季", "春季", "夏季", "秋季", "冬季",
    }

    # 允许出现的单字实词（不在 STOP_WORDS 里的）
    ALLOWED_SINGLE = set("城市场馆景店行宿游吃玩")  # 高频实义单字

    def tokenize(self, text: str) -> List[str]:
        """
        提取核心语义词（兼顾2-4字词 + 高权重单字）

        策略：
        1. 英文词：直接提取
        2. 中文词：
           - 优先匹配 CORE_WORDS 表（高权重）
           - 其次提取 2-4 字组合，过滤碎片
           - 补充高权重单字
        """
        words = set()
        text_lower = text.lower()

        # 1. 英文词
        for w in re.findall(r'[a-zA-Z]{2,}', text_lower):
            words.add(w)

        # 2. 核心词优先匹配
        for core in self.CORE_WORDS:
            if core in text:
                words.add(core)

        # 3. 中文 n-gram（2-4字，智能过滤碎片）
        chinese = re.findall(r'[\u4e00-\u9fff]+', text)
        for chunk in chinese:
            for n in range(2, 5):
                for i in range(len(chunk) - n + 1):
                    word = chunk[i:i + n]
                    if self._is_meaningful_word(word):
                        words.add(word)
            # 4. 高权重单字补充（合并到循环内，避免 UnboundLocalError）
            for char in chunk:
                if char in self.ALLOWED_SINGLE:
                    words.add(char)

        return list(words)

    def _is_meaningful_word(self, word: str) -> bool:
        """判断是否是有意义的词"""
        # 太短或太长直接排除
        if len(word) < 2 or len(word) > 4:
            return False
        # 已经是核心词，通过
        if word in self.CORE_WORDS:
            return True
        # 纯数字/英文组合排除
        if re.match(r'^[a-zA-Z0-9]+$', word):
            return False
        # Fragment filter: reject if >50% stop-words
        if len(word) >= 2:
            char_set = set(word)
            stop_ratio = len(char_set & self.STOP_WORDS) / len(char_set)
            if stop_ratio > 0.5:
                return False
        return True

    def extract_keywords(self, query: str) -> frozenset:
        """提取关键词集合（用于语义相似度计算）"""
        tokens = self.tokenize(query)
        # _is_meaningful_word 已在 tokenize 中过滤碎片，直接收集
        # 去重 + 排除过短的
        keywords = {t for t in tokens if len(t) >= 2}
        return frozenset(keywords)

    def jaccard_similarity(self, keywords1: frozenset, keywords2: frozenset) -> float:
        """计算 Jaccard 相似度（保留方法，n-gram 词集合）"""
        if not keywords1 or not keywords2:
            return 0.0
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)
        return intersection / union if union > 0 else 0.0

    def chinese_similarity(self, query1: str, query2: str) -> float:
        """
        计算中文 query 的语义相似度（字符级加权覆盖）

        原理：
        - 中文中，每个汉字携带独立语义
        - 相似 query 应有大量共同汉字（尤其是实义词）
        - 用共同实义字符数 / query 平均实义字符数

        示例：
        "杭州五一有什么好玩的" vs "五一去杭州玩什么"
        → 共同实义词: 杭/州/五/一/玩/什/么 = 7字
        → query1实义词: 杭/州/五/一/好/玩/的 = 7字
        → query2实义词: 五/一/去/杭/州/玩/什/么 = 8字
        → 相似度: 7 / ((7+8)/2) = 7/7.5 = 0.93 ✅
        """
        # 实义字符（排除标点、停用字）
        def extract_chars(q: str) -> set:
            chars = set()
            for ch in q:
                if '\u4e00' <= ch <= '\u9fff':  # 中文
                    if ch not in self.STOP_WORDS and ch not in "的了是在和就都有":
                        chars.add(ch)
            return chars

        chars1 = extract_chars(query1)
        chars2 = extract_chars(query2)

        if not chars1 or not chars2:
            return 0.0

        # 共同字符
        common = chars1 & chars2
        # 加权分数：共同字符 / 平均字符数
        avg_len = (len(chars1) + len(chars2)) / 2
        if avg_len == 0:
            return 0.0
        return len(common) / avg_len

    def normalize(self, query: str, compressor: 'QueryCompressor' = None) -> Dict[str, Any]:
        """
        标准化 query，返回多种表示形式

        新增三级压缩策略（替代粗暴截断）：
        1. Keyword 快缩（≤500字符）：直接提取关键词，0 延迟
        2. LLM 语义压缩（300-500字符）：调用 LLM 将长 query 压缩为 50-100 字核心摘要
        3. QueryChunker 分块（>500字符）：按语义边界分块后合并

        Returns:
            {
                "original": str,        # 原始 query
                "cleaned": str,         # 语义压缩后的 query（替代粗暴截断）
                "keywords": frozenset,   # 关键词集合
                "hash_key": str,        # md5(cleaned) 用于精确 key
                "keyword_key": str,     # 关键词集哈希 用于相似 key
                "length": int,           # 原始长度
                "was_truncated": bool,  # 是否被压缩（包含压缩/分块）
                "compression_method": str, # "keyword" | "llm" | "llm_cached" | "chunking"
            }
        """
        original = query
        # 0. 去除标点
        cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', query)
        cleaned = re.sub(r'\s+', '', cleaned)

        original_len = len(cleaned)
        compression_method = "none"
        was_truncated = False

        # 1. 判断是否需要压缩
        if original_len > self.max_length:
            was_truncated = True
            if compressor is not None:
                # 使用语义压缩器（LLM/分块）
                compressed, method = compressor.compress(query, self)
                cleaned = re.sub(r'[^\w\u4e00-\u9fff]', '', compressed)
                cleaned = re.sub(r'\s+', '', cleaned)
                compression_method = method
            else:
                # 无压缩器，降级为分段提取
                keywords = self.extract_keywords(cleaned)
                if keywords:
                    sorted_kw = sorted(keywords, key=len, reverse=True)
                    cleaned = " ".join(sorted_kw[:10])
                    compression_method = "keyword_fallback"
                else:
                    cleaned = cleaned[:self.max_length]
                    compression_method = "direct_truncate"

        # 2. 最终截断（确保不超过 max_length，防止意外溢出）
        if len(cleaned) > self.max_length:
            cleaned = cleaned[:self.max_length]

        # 3. 关键词提取
        keywords = self.extract_keywords(cleaned)

        # 4. 生成 key
        hash_key = hashlib.md5(cleaned.encode()).hexdigest()
        keyword_key = hashlib.md5('|'.join(sorted(keywords)).encode()).hexdigest()[:16]

        return {
            "original": original,
            "cleaned": cleaned,
            "keywords": keywords,
            "hash_key": hash_key,
            "keyword_key": keyword_key,
            "length": original_len,
            "was_truncated": was_truncated,
            "compression_method": compression_method,
        }


# ════════════════════════════════════════════════════════════════════════════
# 增强1.5: 超长 Query 三级压缩策略（keyword快缩 → LLM语义压缩 → 分块）
# ════════════════════════════════════════════════════════════════════════════

class QueryCompressor:
    """
    Query 语义压缩器 - 替代粗暴截断

    三级压缩策略（按优先级递进）：
    1. Keyword 快缩（≤500字符）：直接用 QueryNormalizer 提取关键词，0 延迟
    2. LLM 语义压缩（300-500字符）：调用 LLM 将长 query 压缩为 50-100 字的
       核心语义摘要，保留意图 + 核心实体
    3. QueryChunker 分块（>500字符）：将超长 query 按语义句子/段落分块，
       每块独立标准化后再合并

    设计原则：
    - LLM 压缩只在"长但有价值"的 query 上使用（300-500字符）
    - 超长 query（>500）用分块，避免 LLM 调用膨胀
    - 分词相似度作为降级兜底（LLM 不可用时）

    使用 Ollama L4 模型（qwen3.5:4b）进行语义压缩，延迟 ~1-3s，
    仅在首次压缩时触发，后续命中本地压缩缓存。
    """

    # LLM 压缩触发阈值（字符数）
    LLM_COMPRESS_MIN = 300    # 超过此长度才考虑 LLM 压缩
    LLM_COMPRESS_MAX = 500    # 超过此长度直接分块，不 LLM 压缩
    TARGET_COMPRESSED = 80    # 压缩目标字数
    # LLM 压缩推荐模型（优先级：非思考模型优先）
    _COMPRESS_MODELS = ["qwen2.5:1.5b", "qwen2.5:0.5b", "qwen3.5:4b", "qwen3.5:2b"]

    def __init__(
        self,
        ollama_base: str = "http://localhost:11434",
        model: str = "qwen2.5:1.5b",
        timeout: float = 30.0,
        enable_llm: bool = True,
    ):
        self.ollama_base = ollama_base
        self.model = model
        self.timeout = timeout
        self.enable_llm = enable_llm

        # LLM 可用性检测（优先非思考模型）
        self._llm_available = self._check_llm()

        # 本地压缩缓存（避免重复调用 LLM）
        self._compress_cache: OrderedDict[str, str] = OrderedDict()
        self._compress_cache_max = 200

        # 统计
        self._stats = {"llm_compress": 0, "keyword_compress": 0, "chunk": 0}

        if self._llm_available:
            logger.info(f"LLM 语义压缩就绪（模型={self.model}），300-500字 query 将自动压缩")
        else:
            logger.warning(f"LLM 不可用，降级为 keyword 快缩 + 分块策略")

    def _check_llm(self) -> bool:
        """检测 LLM 是否可用，优先选择非思考模型"""
        if not self.enable_llm:
            return False
        try:
            r = requests.get(f"{self.ollama_base}/api/tags", timeout=_get_cache_timeout("ollama_quick"))
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                # 优先选择非思考模型（qwen2.5 系列）
                for preferred in self._COMPRESS_MODELS:
                    if preferred in models:
                        self.model = preferred
                        # 验证模型可用（非思考模型有 response 字段）
                        if self._test_model(self.model):
                            return True
                # 如果首选不可用，尝试任何可用的 qwen/llama 模型
                fallback = [m for m in models if "qwen" in m.lower() or "llama" in m.lower()]
                if fallback:
                    self.model = fallback[0]
                    return True
        except Exception:
            pass
        return False

    def _test_model(self, model: str) -> bool:
        """测试模型是否可用（非思考模型有 response 字段）"""
        try:
            resp = requests.post(
                f"{self.ollama_base}/api/generate",
                json={
                    "model": model,
                    "prompt": "测试",
                    "stream": False,
                    "options": {"num_predict": 10}
                },
                timeout=_get_cache_timeout("ollama_normal")
            )
            if resp.status_code == 200:
                data = resp.json()
                # 非思考模型：response 非空，thinking 为空
                response = data.get("response", "").strip()
                thinking = data.get("thinking", "")
                return bool(response) and not thinking
        except Exception:
            pass
        return False

    def compress(self, query: str, normalizer: QueryNormalizer) -> Tuple[str, str]:
        """
        对超长 query 进行语义压缩，返回 (compressed_text, method)

        Args:
            query: 原始 query
            normalizer: QueryNormalizer 实例（用于 keyword 快缩）

        Returns:
            (compressed_text, method): 压缩后文本 + 压缩方式标识
        """
        clean_len = len(re.sub(r'[^\w\u4e00-\u9fff]', '', query))

        # 策略1: keyword 快缩（≤500字符，或 LLM 不可用）
        if clean_len <= self.LLM_COMPRESS_MAX:
            if not self._llm_available or clean_len <= self.LLM_COMPRESS_MIN:
                result = self._keyword_compress(query, normalizer)
                self._stats["keyword_compress"] += 1
                return result, "keyword"

        # 策略2: LLM 语义压缩（300-500字符，LLM 可用）
        if self.LLM_COMPRESS_MIN < clean_len <= self.LLM_COMPRESS_MAX and self._llm_available:
            # 先检查本地缓存
            cache_key = f"{self.model}:{clean_len}:{query[:100]}"
            if cache_key in self._compress_cache:
                return self._compress_cache[cache_key], "llm_cached"
            result = self._llm_compress(query)
            if result:
                self._stats["llm_compress"] += 1
                # 写入本地缓存
                self._compress_cache[cache_key] = result
                if len(self._compress_cache) > self._compress_cache_max:
                    self._compress_cache.popitem(last=False)
                return result, "llm"

        # 策略3: 语义分块（>500字符，或 LLM 压缩失败）
        result = self._semantic_chunk(query, normalizer)
        self._stats["chunk"] += 1
        return result, "chunking"

    def _keyword_compress(self, query: str, normalizer: QueryNormalizer) -> str:
        """Keyword 快缩：提取核心关键词拼接"""
        keywords = normalizer.extract_keywords(query)
        if keywords:
            # 按字符长度降序排列（长词优先，语义更丰富）
            sorted_kw = sorted(keywords, key=len, reverse=True)
            # 取前 10 个关键词拼接
            return " ".join(sorted_kw[:10])
        # 兜底：取前 50 字符
        return query[:50]

    def _llm_compress(self, query: str) -> Optional[str]:
        """
        调用 LLM 将长 query 压缩为核心语义（保留意图 + 核心实体）

        提示词设计原则：
        - 明确输出字数限制（50-80字）
        - 强调保留：意图词 + 核心名词/实体 + 时间/地点限定词
        - 丢弃：语气词、重复描述、冗长修饰语

        兼容性处理：
        - qwen2.5:1.5b（推荐）：非思考模型，直接返回 response
        - qwen3.5:4b 等思考模型：答案在 thinking 字段，从最后一段提取
        """
        # 非思考模型用简短提示
        if self.model.startswith("qwen2.5") or self._test_model(self.model):
            prompt = (
                f"将以下问题压缩为 {self.TARGET_COMPRESSED} 字以内核心语义。"
                f"保留意图词+核心实体+限定词，删除语气词。问题：{query}。压缩结果（仅输出文本）："
            )
            num_predict = self.TARGET_COMPRESSED + 30
        else:
            # 思考模型用较长提示
            prompt = (
                f"将以下用户问题压缩为 {self.TARGET_COMPRESSED} 字以内的核心语义表述。\n"
                f"规则：保留【意图词+核心实体+限定词】，删除【语气词+重复+冗余修饰】。\n\n"
                f"原始问题：{query}\n\n"
                f"压缩结果（仅输出压缩后文本，不要解释）："
            )
            num_predict = 500  # 思考模型需要更多 token

        try:
            resp = requests.post(
                f"{self.ollama_base}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": num_predict,
                    }
                },
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                thinking = data.get("thinking", "")
                response = data.get("response", "").strip()

                if thinking:
                    # 思考模型：从 thinking 字段提取最终答案段落
                    result = self._extract_final_from_thinking(thinking)
                    if result and len(result) >= 10:
                        return result

                # 非思考模型：直接用 response
                if response and len(response) >= 10:
                    # 清理：去除引号、换行、前后空格
                    result = re.sub(r'^["""]|["""]$', '', response).strip()
                    # 清理思考标记词
                    result = re.sub(r'^Thinking\s*Process[：:]\s*', '', result, flags=re.IGNORECASE)
                    return result if len(result) >= 10 else None

        except Exception:
            pass
        return None

    def _extract_final_from_thinking(self, thinking: str) -> Optional[str]:
        """
        从思考模型的 thinking 字段提取最终答案段落

        思考模型的 thinking 字段包含：
        - 分析过程（"1. Analyze..."）
        - 中间推理
        - 最终答案（通常在最后几个段落，以完整句子结尾）

        提取策略：
        1. 按空行分段落
        2. 过滤掉分析步骤标记（"1.", "2.", "**"）
        3. 取最后一个非分析段落
        4. 清理后返回
        """
        paragraphs = thinking.split('\n\n')
        candidates = []
        for para in reversed(paragraphs):
            para = para.strip()
            if not para:
                continue
            # 过滤掉分析步骤标记
            if re.match(r'^\d+[\.\)]\s', para) or para.startswith('**'):
                continue
            # 过滤掉过短的段落
            if len(para) < 10:
                continue
            # 清理 markdown 标记
            clean = re.sub(r'\*+', '', para).strip()
            clean = re.sub(r'^[-•]\s*', '', clean).strip()
            if clean:
                candidates.append(clean)
            if candidates:
                break

        if candidates:
            return candidates[0]
        return None

    def _semantic_chunk(self, query: str, normalizer: QueryNormalizer) -> str:
        """
        语义分块：按句子/段落分块，每块独立标准化后合并

        策略：
        - 按句号/问号/逗号分句
        - 保留第一句（通常含核心意图）
        - 后面的句子提取关键词
        - 合并时用 " | " 分隔各块核心词
        """
        # 按中英文标点分句
        sentences = re.split(r'[。！？；\n]', query)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            # 无法分句，直接用 keyword 快缩兜底
            return self._keyword_compress(query, normalizer)

        chunks = []
        for i, sent in enumerate(sentences):
            if i == 0:
                # 第一句：通常包含核心意图，优先保留
                # 如果第一句过长，再压缩
                if len(sent) > 80:
                    kw = normalizer.extract_keywords(sent)
                    chunks.append(" ".join(sorted(kw, key=len, reverse=True)[:6]))
                else:
                    chunks.append(sent[:80])
            else:
                # 后续句子：提取关键词即可
                kw = normalizer.extract_keywords(sent)
                if kw:
                    chunks.append(" ".join(sorted(kw, key=len, reverse=True)[:4]))

        # 用 " | " 合并各块，"|" 是语义分隔符
        merged = " | ".join(chunks[:3])  # 最多合并3个块
        # 如果合并后仍超长，再截断
        if len(merged) > self.LLM_COMPRESS_MAX:
            merged = merged[:self.LLM_COMPRESS_MAX - 3] + "..."
        return merged

    def stats(self) -> Dict[str, int]:
        """返回压缩统计"""
        return self._stats.copy()


class QueryChunker:
    """
    Query 分块器 - 处理超长上下文/对话历史

    当 query 包含多轮对话历史、长文档描述时，直接压缩会丢失信息。
    分块器按语义边界切分，每块独立处理后再合并。

    切分策略：
    1. 对话模式：按 "User:" / "Assistant:" 轮次切分
    2. 文档模式：按段落/句子边界切分
    3. 重叠窗口：相邻块保留 1 句重叠，避免边界丢失
    """

    def __init__(
        self,
        chunk_size: int = 300,      # 每块目标字数
        overlap_sentences: int = 1, # 相邻块重叠句子数
        max_chunks: int = 5,        # 最多分块数
    ):
        self.chunk_size = chunk_size
        self.overlap_sentences = overlap_sentences
        self.max_chunks = max_chunks

    def chunk(self, query: str) -> List[Dict[str, str]]:
        """
        将超长 query 分块

        Args:
            query: 原始超长 query

        Returns:
            [{"text": str, "index": int, "keywords": frozenset}, ...]
        """
        # 检测是否为对话模式
        if self._is_conversation(query):
            chunks = self._chunk_by_turns(query)
        else:
            chunks = self._chunk_by_sentences(query)

        # 限制块数
        return chunks[:self.max_chunks]

    def _is_conversation(self, query: str) -> bool:
        """检测是否为多轮对话模式"""
        # 对话标记词
        patterns = [
            r'User[：:]\s*',
            r'用户[：:]\s*',
            r'上一[一轮句][：:：]?\s*',
            r'之前[说问讲][：:：]?\s*',
            r'之前提过',
            r'接着',
            r'另外',
            r'还有',
        ]
        matches = sum(1 for p in patterns if re.search(p, query))
        return matches >= 2

    def _chunk_by_turns(self, query: str) -> List[Dict[str, str]]:
        """按对话轮次分块"""
        # 分割轮次
        parts = re.split(r'(User[：:]|用户[：:]|Assistant[：:]|助手[：:])', query)
        turns = []
        current_role = ""
        current_content = []

        for part in parts:
            if re.match(r'User[：:]|用户[：:]', part):
                if current_content:
                    turns.append(("user", "".join(current_content)))
                current_role = "user"
                current_content = []
            elif re.match(r'Assistant[：:]|助手[：:]', part):
                if current_content:
                    turns.append((current_role, "".join(current_content)))
                current_role = "assistant"
                current_content = []
            else:
                current_content.append(part)

        if current_content:
            turns.append((current_role, "".join(current_content)))

        # 每轮作为一块（保留最后2轮，前面的轮次合并）
        chunks = []
        if len(turns) > 2:
            # 合并历史轮次
            history = "\n".join(f"{role}: {content}" for role, content in turns[:-2])
            chunks.append({"text": history, "index": 0, "role": "history"})
            # 当前轮次
            last_role, last_content = turns[-1]
            chunks.append({"text": last_content, "index": 1, "role": last_role})
        else:
            for i, (role, content) in enumerate(turns):
                chunks.append({"text": content, "index": i, "role": role})

        return chunks

    def _chunk_by_sentences(self, query: str) -> List[Dict[str, str]]:
        """按句子分块"""
        sentences = re.split(r'[。！？；\n]', query)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return [{"text": query[:self.chunk_size], "index": 0}]

        chunks = []
        current_chunk = []
        current_len = 0
        chunk_idx = 0

        for sent in sentences:
            sent_len = len(sent)
            if current_len + sent_len > self.chunk_size and current_chunk:
                # 保存当前块
                chunks.append({
                    "text": "".join(current_chunk),
                    "index": chunk_idx,
                })
                chunk_idx += 1
                # 重叠部分
                overlap_start = max(0, len(current_chunk) - self.overlap_sentences)
                current_chunk = current_chunk[overlap_start:]
                current_len = sum(len(s) for s in current_chunk)

            current_chunk.append(sent)
            current_len += sent_len

        # 最后一块
        if current_chunk:
            chunks.append({
                "text": "".join(current_chunk),
                "index": chunk_idx,
            })

        return chunks

    def merge_chunks(self, chunks: List[Dict[str, str]], normalizer: QueryNormalizer) -> str:
        """
        合并多块结果为核心 query

        策略：
        - 历史块：提取关键词（保留上下文线索）
        - 当前块：优先保留完整句子
        - 用 " || " 分隔不同来源
        """
        if len(chunks) == 1:
            return chunks[0]["text"]

        parts = []
        for chunk in chunks:
            text = chunk["text"]
            if chunk.get("role") == "history":
                # 历史块：提取关键词
                kw = normalizer.extract_keywords(text)
                kw_str = " ".join(sorted(kw, key=len, reverse=True)[:8])
                if kw_str:
                    parts.append(f"[历史]{kw_str}")
                else:
                    parts.append(text[:60])
            else:
                # 当前块：保留核心（截断到 100 字）
                if len(text) > 100:
                    parts.append(text[:100])
                else:
                    parts.append(text)

        return " || ".join(parts)


# ════════════════════════════════════════════════════════════════════════════
# 增强2: 语义相似缓存层（替代伪 md5 向量）
# ════════════════════════════════════════════════════════════════════════════

class SemanticSimilarityCache:
    """
    语义相似缓存层

    核心改进：
    1. 使用 QueryNormalizer 提取关键词 Jaccard 相似度（真正语义匹配）
    2. Ollama Embedding 增强（可选，需 nomic-embed-text 等模型）
    3. 三级降级：Ollama向量 → 关键词Jaccard → 精确匹配
    4. 批量存储支持，支持 top-k 相似查询

    相似问法示例（均可命中）：
        "杭州五一有什么好玩的"
        "五一去杭州玩什么"
        "杭州五一假期景点推荐"
        → 关键词集高度重叠，Jaccard > 0.5，命中缓存
    """

    # Ollama embedding 模型名
    EMBEDDING_MODEL = "nomic-embed-text"
    # LLM 压缩推荐模型（优先级：非思考模型优先）
    COMPRESS_MODELS = ["qwen2.5:1.5b", "qwen2.5:0.5b", "qwen3.5:4b", "qwen3.5:2b"]

    def __init__(
        self,
        similarity_threshold: float = 0.5,
        max_entries: int = 5000,
        ollama_base: str = "http://localhost:11434",
        enable_ollama: bool = True,
    ):
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.ollama_base = ollama_base
        self.enable_ollama = enable_ollama
        self.normalizer = QueryNormalizer()
        self._lock = threading.RLock()

        # Ollama 可用性检测
        self._ollama_available = self._check_ollama()

        # 存储结构
        self._entries: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        # 关键词索引: keyword_key → [(hash_key, entry), ...]
        self._keyword_index: Dict[str, List[Tuple[str, Dict]]] = {}
        # Ollama 向量索引: hash_key → List[float]
        self._vectors: Dict[str, List[float]] = {}

        self._hits = 0
        self._misses = 0
        self._l3_mode = "keyword"  # "ollama" | "keyword"

        if self._ollama_available and self.enable_ollama:
            self._l3_mode = "ollama"
            logger.info(f"Ollama embedding 可用（模型={self.EMBEDDING_MODEL}），使用真实向量语义匹配")
        else:
            logger.warning(f"Ollama embedding 不可用，使用关键词 Jaccard 语义匹配（阈值={similarity_threshold}）")

    def _check_ollama(self) -> bool:
        """检测 Ollama 是否可用"""
        try:
            r = requests.get(f"{self.ollama_base}/api/tags", timeout=_get_cache_timeout("ollama_quick"))
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                # 优先用专门的 embedding 模型
                emb_models = [m for m in models if "embed" in m.lower() or "nomic" in m.lower()]
                if emb_models:
                    self.EMBEDDING_MODEL = emb_models[0]
                return True
        except Exception:
            pass
        return False

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """调用 Ollama 生成 embedding 向量"""
        try:
            resp = requests.post(
                f"{self.ollama_base}/api/embed",
                json={"model": self.EMBEDDING_MODEL, "input": text},
                timeout=_get_cache_timeout("ollama_slow"),
            )
            if resp.status_code == 200:
                data = resp.json()
                embeddings = data.get("embeddings", [])
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]
        except Exception:
            pass
        return None

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        语义相似查询

        策略：
        1. 先精确匹配（md5 hash key）
        2. 再 Ollama 向量相似度（threshold > 0.85）
        3. 最后关键词 Jaccard 相似度（threshold > 0.5）
        """
        with self._lock:
            norm = self.normalizer.normalize(query)
            hash_key = norm["hash_key"]

            # 1. 精确匹配
            if hash_key in self._entries:
                entry = self._entries[hash_key]
                self._entries.move_to_end(hash_key)
                self._hits += 1
                return {
                    **entry,
                    "similarity": 1.0,
                    "match_type": "exact",
                }

            # 2. Ollama 向量相似度
            if self._l3_mode == "ollama" and self._ollama_available:
                query_vec = self._get_embedding(query)
                if query_vec:
                    best_sim = 0.0
                    best_entry = None
                    for stored_key, stored_vec in list(self._vectors.items()):
                        sim = self._cosine_similarity(query_vec, stored_vec)
                        if sim > best_sim and sim >= 0.85:
                            best_sim = sim
                            best_entry = self._entries.get(stored_key)
                    if best_entry:
                        self._entries.move_to_end(hash_key)
                        self._hits += 1
                        return {
                            **best_entry,
                            "similarity": best_sim,
                            "match_type": "ollama_vector",
                        }

            # 3. 字符级语义相似度（核心改进！）
            best_sim = 0.0
            best_entry = None
            best_key = None
            for stored_key, entry in list(self._entries.items()):
                stored_query = entry.get("query", "")
                sim = self.normalizer.chinese_similarity(query, stored_query)
                if sim > best_sim and sim >= self.similarity_threshold:
                    best_sim = sim
                    best_entry = entry
                    best_key = stored_key
            if best_entry and best_key:
                self._entries.move_to_end(best_key)
                self._hits += 1
                return {
                    **best_entry,
                    "similarity": best_sim,
                    "match_type": "char_similarity",
                }

            self._misses += 1
            return None

    def set(self, query: str, response: Any, model_id: str = None):
        """存储（自动注册关键词索引和向量索引）"""
        with self._lock:
            norm = self.normalizer.normalize(query)
            hash_key = norm["hash_key"]
            keywords = norm["keywords"]

            # LRU 淘汰
            if hash_key not in self._entries and len(self._entries) >= self.max_entries:
                evicted_key, _ = self._entries.popitem(last=False)
                # 清理向量
                self._vectors.pop(evicted_key, None)
                # 清理关键词索引
                for kw_key in list(self._keyword_index.keys()):
                    self._keyword_index[kw_key] = [
                        (hk, e) for hk, e in self._keyword_index[kw_key]
                        if hk != evicted_key
                    ]
                    if not self._keyword_index[kw_key]:
                        del self._keyword_index[kw_key]

            entry = {
                "query": query,
                "cleaned_query": norm["cleaned"],
                "_keywords": keywords,
                "response": response,
                "model_id": model_id,
                "created_at": time.time(),
                "access_count": 1,
            }
            self._entries[hash_key] = entry

            # 注册关键词索引
            if keywords:
                kw_key = norm["keyword_key"]
                if kw_key not in self._keyword_index:
                    self._keyword_index[kw_key] = []
                self._keyword_index[kw_key].append((hash_key, entry))

            # 注册 Ollama 向量
            if self._l3_mode == "ollama" and self._ollama_available:
                vec = self._get_embedding(query)
                if vec:
                    self._vectors[hash_key] = vec

    def search_similar(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """查找 top-k 最相似的缓存条目（字符级相似度）"""
        results = []

        with self._lock:
            for hk, entry in self._entries.items():
                stored_query = entry.get("query", "")
                sim = self.normalizer.chinese_similarity(query, stored_query)
                if sim > 0.3:  # 放宽阈值用于搜索
                    results.append({**entry, "similarity": sim, "match_type": "char_similarity"})
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "entries": len(self._entries),
            "max_entries": self.max_entries,
            "mode": self._l3_mode,
            "embedding_model": self.EMBEDDING_MODEL if self._l3_mode == "ollama" else "keyword_jaccard",
            "similarity_threshold": self.similarity_threshold,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / total:.2%}" if total else "0%",
            "keyword_index_size": len(self._keyword_index),
            "vector_index_size": len(self._vectors),
        }

    def clear(self):
        with self._lock:
            self._entries.clear()
            self._keyword_index.clear()
            self._vectors.clear()
            self._hits = 0
            self._misses = 0


# ════════════════════════════════════════════════════════════════════════════
# 增强3: 相似 query 检测 + 智能降级
# ════════════════════════════════════════════════════════════════════════════

class SimilarQueryDetector:
    """
    相似 query 检测器

    在 query 进入缓存之前，检测是否有相似的已缓存 query。
    支持三种模式，按优先级降序：
    1. Ollama 真实 embedding 向量（最准确）
    2. 关键词 Jaccard 相似度（离线可用）
    3. 字符级编辑距离（兜底）

    使用场景：
        # 新 query 进入时，先问有没有相似的
        similar = detector.find_similar("杭州五一有什么好玩的")
        if similar:
            logger.debug(f"已有相似答案，相似度 {similar['similarity']:.2f}")
            return similar["response"]

        # 没有相似的，执行搜索后存入
        detector.store("杭州五一有什么好玩的", answer)
    """

    def __init__(
        self,
        similarity_threshold: float = 0.5,
        keyword_threshold: float = 0.5,
        char_threshold: float = 0.85,
    ):
        self.keyword_threshold = keyword_threshold
        self.char_threshold = char_threshold
        self.normalizer = QueryNormalizer()
        self._similarity_cache = SemanticSimilarityCache(
            similarity_threshold=keyword_threshold
        )
        # 字符级索引: query 前缀 → [(query, response), ...]
        self._char_index: Dict[str, List[Tuple[str, Any]]] = {}

    def _prefix_key(self, query: str, n: int = 3) -> str:
        """取 query 前 n 个字符做前缀索引"""
        return query[:n]

    def _edit_distance(self, s1: str, s2: str) -> float:
        """计算两个字符串的编辑距离相似度（莱文斯坦比）"""
        if not s1 or not s2:
            return 0.0
        m, n = len(s1), len(s2)
        if m > 200 or n > 200:
            # 太长的字符串用截断版
            s1, s2 = s1[:200], s2[:200]
            m, n = 200, 200

        # 滚动数组优化
        prev = list(range(n + 1))
        curr = [0] * (n + 1)
        for i in range(1, m + 1):
            curr[0] = i
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    curr[j] = prev[j - 1]
                else:
                    curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
            prev, curr = curr, prev

        distance = prev[n]
        max_len = max(m, n)
        return 1.0 - distance / max_len

    def find_similar(self, query: str) -> Optional[Dict[str, Any]]:
        """
        查找最相似的已缓存 query

        Returns:
            相似条目（含 similarity 和 match_type）或 None
        """
        norm = self.normalizer.normalize(query)

        # 策略1: 语义相似缓存
        result = self._similarity_cache.get(query)
        if result and result.get("similarity", 0) >= self.keyword_threshold:
            result["match_type"] = "semantic"
            return result

        # 策略2: 字符级前缀索引 + 编辑距离
        prefix = self._prefix_key(query, 3)
        candidates = self._char_index.get(prefix, [])
        best = None
        best_sim = 0.0
        for cached_q, cached_r in candidates:
            sim = self._edit_distance(query, cached_q)
            if sim > best_sim and sim >= self.char_threshold:
                best_sim = sim
                best = cached_r
        if best:
            return {
                "query": cached_q,
                "response": best,
                "similarity": best_sim,
                "match_type": "char_edit_distance",
            }

        return None

    def store(self, query: str, response: Any, model_id: str = None):
        """存储 query-response 对"""
        norm = self.normalizer.normalize(query)
        self._similarity_cache.set(query, response, model_id)

        # 字符级索引
        for n in (2, 3, 4):
            prefix = query[:n]
            if prefix not in self._char_index:
                self._char_index[prefix] = []
            # 避免重复
            existing = [q for q, r in self._char_index[prefix] if q == query]
            if not existing:
                self._char_index[prefix].append((query, response))
                # 限制前缀列表长度
                if len(self._char_index[prefix]) > 50:
                    self._char_index[prefix] = self._char_index[prefix][-50:]

    def search_similar(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """查找 top-k 最相似的 query"""
        return self._similarity_cache.search_similar(query, top_k)

    def stats(self) -> Dict[str, Any]:
        return {
            **self._similarity_cache.get_stats(),
            "char_index_prefixes": len(self._char_index),
        }

    def clear(self):
        self._similarity_cache.clear()
        self._char_index.clear()


# ════════════════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class CacheStats:
    """缓存统计"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    l0_hits: int = 0
    l1_hits: int = 0
    l2_hits: int = 0
    l3_hits: int = 0
    l4_hits: int = 0
    total_latency_saved_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "l0_hits": self.l0_hits,
            "l1_hits": self.l1_hits,
            "l2_hits": self.l2_hits,
            "l3_hits": self.l3_hits,
            "l4_hits": self.l4_hits,
            "total_latency_saved_ms": self.total_latency_saved_ms,
        }


# ════════════════════════════════════════════════════════════════════════════
# 缓存命中结果
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class CacheHit:
    """缓存命中结果"""
    tier: str                    # "L0" / "L1" / "L2" / "L3" / "L4"
    data: Any                    # 缓存数据
    latency_ms: float = 0.0     # 命中层级的延迟
    similarity: float = 1.0     # 语义相似度（仅L3）
    source: str = ""            # 来源描述

    def is_hit(self) -> bool:
        return True

    def __str__(self) -> str:
        return f"[{self.tier}] {self.source} ({self.latency_ms:.1f}ms)"


class CacheMiss:
    """缓存未命中"""
    tier: str = "MISS"

    def is_hit(self) -> bool:
        return False


# ════════════════════════════════════════════════════════════════════════════
# L0 路由缓存
# ════════════════════════════════════════════════════════════════════════════

class L0RouteCache:
    """
    L0 路由缓存封装

    缓存 key = md5(normalized_query) → route decision JSON
    支持超长 query 截断和关键词标准化
    """

    def __init__(self, max_size: int = 100, ttl_hours: float = 24.0,
                 normalizer: QueryNormalizer = None):
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._normalizer = normalizer or QueryNormalizer()

    def _hash(self, query: str) -> str:
        norm = self._normalizer.normalize(query)
        return norm["hash_key"]

    def get(self, query: str) -> Optional[CacheHit]:
        """获取 L0 路由缓存"""
        key = self._hash(query)
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            # TTL 检查
            if datetime.now() - entry["ts"] > self.ttl:
                del self._cache[key]
                self._misses += 1
                return None

            # LRU 更新
            self._cache.move_to_end(key)
            self._hits += 1
            return CacheHit(
                tier="L0",
                data=entry["data"],
                latency_ms=0.0,
                source=f"路由缓存命中 (hit#{entry.get('hit_count', 1)})"
            )

    def set(self, query: str, route_decision: Dict[str, Any]):
        """缓存路由决策"""
        key = self._hash(query)
        with self._lock:
            # LRU 淘汰
            if key not in self._cache and len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            if key in self._cache:
                self._cache.move_to_end(key)
                entry = self._cache[key]
                entry["hit_count"] = entry.get("hit_count", 1) + 1
                entry["data"] = route_decision
                entry["ts"] = datetime.now()
            else:
                self._cache[key] = {
                    "data": route_decision,
                    "ts": datetime.now(),
                    "hit_count": 1,
                }

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "l0_cache_size": len(self._cache),
            "l0_hits": self._hits,
            "l0_misses": self._misses,
            "l0_hit_rate": f"{self._hits / total:.2%}" if total else "0%",
        }


# ════════════════════════════════════════════════════════════════════════════
# Search 缓存（封装 CacheManager 的三级缓存）
# ════════════════════════════════════════════════════════════════════════════

class SearchCache:
    """
    Search 缓存封装

    封装 tier_model/cache_manager.py 的 CacheManager，提供统一的 get/set 接口。
    支持精确匹配（L1/L2）和语义相似匹配（L3）。
    """

    def __init__(self):
        self._manager: Optional[CacheManager] = None
        self._hits = 0
        self._misses = 0
        self._tier_hits = {"L1": 0, "L2": 0, "L3": 0}

    def _ensure_init(self):
        if self._manager is None and _CACHE_MGR_AVAILABLE:
            try:
                self._manager = CacheManager()
                logger.info("CacheManager 初始化成功")
            except Exception as e:
                logger.error(f"CacheManager 初始化失败: {e}")

    def get(self, query: str, context: str = None) -> Optional[CacheHit]:
        """获取搜索缓存（逐级查询 L1 → L2 → L3）"""
        self._ensure_init()
        if self._manager is None:
            self._misses += 1
            return None

        try:
            result = self._manager.get(query, context)
            if result:
                tier = result.get("tier", "?")
                self._hits += 1
                self._tier_hits[tier] = self._tier_hits.get(tier, 0) + 1
                return CacheHit(
                    tier=tier,
                    data=result.get("response") or result.get("data"),
                    latency_ms=result.get("latency_ms", 0),
                    similarity=result.get("similarity", 1.0),
                    source=f"{tier}级搜索缓存命中"
                )
        except Exception as e:
            logger.error(f"get 异常: {e}")

        self._misses += 1
        return None

    def set(self, query: str, response: Any, context: str = None, model_id: str = None):
        """写入所有缓存层级"""
        self._ensure_init()
        if self._manager is None:
            return
        try:
            self._manager.set(query, response, context, model_id)
        except Exception as e:
            logger.error(f"set 异常: {e}")

    def clear(self):
        if self._manager:
            self._manager.clear_all()

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        mgr_stats = {}
        if self._manager:
            try:
                mgr_stats = self._manager.get_combined_stats()
            except Exception:
                pass
        return {
            "search_hits": self._hits,
            "search_misses": self._misses,
            "search_hit_rate": f"{self._hits / total:.2%}" if total else "0%",
            "tier_hits": self._tier_hits,
            "manager_stats": mgr_stats,
        }


# ════════════════════════════════════════════════════════════════════════════
# L4 响应缓存
# ════════════════════════════════════════════════════════════════════════════

class L4ResponseCache:
    """
    L4 响应缓存

    精确缓存层（LRU + SimHash）+ 异步回填机制
    支持超长 query 截断（通过 normalizer）
    """

    def __init__(
        self,
        memory_size: int = 1000,
        ttl_days: int = 7,
        batch_interval: float = 1.0,
        max_batch_size: int = 10,
        l1_cache=None,
        l2_cache=None,
        l3_cache=None,
        normalizer: QueryNormalizer = None,
    ):
        self._exact: Optional[ExactCacheLayer] = None
        self._write_back: Optional[WriteBackCache] = None
        self._hits = 0
        self._misses = 0
        self._normalizer = normalizer or QueryNormalizer()

        if _EXACT_CACHE_AVAILABLE:
            try:
                self._exact = ExactCacheLayer(
                    memory_size=memory_size,
                    ttl_seconds=ttl_days * 86400,
                )
                logger.info(f"ExactCacheLayer 初始化成功 (memory={memory_size}, ttl={ttl_days}d)")

                self._write_back = WriteBackCache(
                    l1_cache=l1_cache,
                    l2_cache=l2_cache,
                    l3_cache=l3_cache,
                    batch_interval=batch_interval,
                    max_batch_size=max_batch_size,
                )
                # WriteBackCache 启动（可能因无事件循环报 warning，后续 async 调用时会自动启动）
                try:
                    self._write_back.start()
                    logger.info("WriteBackCache 启动成功")
                except RuntimeError as e:
                    # 无运行中事件循环时，记录但不阻塞（后续 cache.set 触发时会重试）
                    logger.warning(f"WriteBackCache 延迟启动（无事件循环）: {e}")
                    self._write_back._running = True  # 标记为运行，异步回填在有loop时执行
            except Exception as e:
                logger.error(f"初始化失败: {e}")

    def _make_key(self, query: str, context: str = None) -> str:
        """生成缓存 key（使用标准化 query）"""
        norm = self._normalizer.normalize(query)
        raw = f"{norm['cleaned']}|{context or ''}"
        return f"l4:{hashlib.md5(raw.encode()).hexdigest()}"

    def get(self, query: str, context: str = None) -> Optional[CacheHit]:
        """获取 L4 响应缓存"""
        if self._exact is None:
            self._misses += 1
            return None

        key = self._make_key(query, context)
        try:
            result = self._exact.get(key)
            if result:
                self._hits += 1
                return CacheHit(
                    tier="L4",
                    data=result,
                    latency_ms=0.0,
                    source="L4响应精确缓存命中"
                )
        except Exception as e:
            logger.error(f"get 异常: {e}")

        self._misses += 1
        return None

    def set(self, query: str, response: str, context: str = None, metadata: Dict = None):
        """写入缓存 + 触发异步回填"""
        if self._exact is None:
            return

        key = self._make_key(query, context)
        try:
            # 同步写精确缓存
            self._exact.set(key, response, metadata)

            # 异步回填上层缓存
            if self._write_back:
                try:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    try:
                        loop.create_task(
                            self._write_back.write_back(
                                messages=[{"role": "user", "content": query}],
                                result={"choices": [{"message": {"content": response}}]},
                                ttl=(metadata or {}).get("ttl", 3600),
                            )
                        )
                    except RuntimeError:
                        # 没有运行中的事件循环，在新线程中启动
                        def _async_write_back():
                            asyncio.run(
                                self._write_back.write_back(
                                    messages=[{"role": "user", "content": query}],
                                    result={"choices": [{"message": {"content": response}}]},
                                    ttl=(metadata or {}).get("ttl", 3600),
                                )
                            )
                        import threading
                        threading.Thread(target=_async_write_back, daemon=True).start()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"set 异常: {e}")

    def exists(self, query: str, context: str = None) -> bool:
        if self._exact is None:
            return False
        return self._exact.exists(self._make_key(query, context))

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        exact_stats = {}
        wb_stats = {}
        if self._exact:
            exact_stats = self._exact.get_stats()
        if self._write_back:
            wb_stats = self._write_back.get_stats()
        return {
            "l4_hits": self._hits,
            "l4_misses": self._misses,
            "l4_hit_rate": f"{self._hits / total:.2%}" if total else "0%",
            "exact_cache": exact_stats,
            "write_back": wb_stats,
        }

    def clear(self):
        if self._exact:
            self._exact.clear()


# ════════════════════════════════════════════════════════════════════════════
# 统一缓存门面（对外唯一入口）
# ════════════════════════════════════════════════════════════════════════════

class UnifiedCache:
    """
    统一缓存门面（增强版）

    整合 L0 路由缓存、Search 缓存、L4 响应缓存，提供统一的接口。
    新增增强：
    - QueryNormalizer: 超长 query 语义压缩 + 关键词提取（替代粗暴截断）
    - QueryCompressor: 三级压缩（keyword → LLM语义 → 分块），仅 LLM 不可用时降级
    - SimilarQueryDetector: 相似问法语义匹配（Jaccard + Ollama embedding）
    - 全链路 query 标准化

    三级压缩策略说明：
    1. keyword 快缩（≤300字符）：直接提取关键词，0 延迟，缓存友好
    2. LLM 语义压缩（300-500字符）：调用 qwen3.5:4b 将 query 压缩为 50-80 字核心摘要
    3. QueryChunker 分块（>500字符）：按语义句子/轮次分块，每块独立标准化后合并

    使用示例：

        cache = UnifiedCache()

        # 相似 query 检测（新增！）
        similar = cache.find_similar("杭州五一有什么好玩的")
        if similar:
            logger.info(f"发现相似答案! 相似度={similar['similarity']:.2f} 匹配类型={similar['match_type']}")
            return similar["response"]

        # L0 路由
        hit = cache.get_l0_route("南京溧水养猪场环评报告")
        if hit:
            logger.debug(f"路由命中: {hit.data}")
        else:
            decision = await router.route(query)
            cache.set_l0_route(query, asdict(decision))

        # Search 缓存
        hit = cache.get_search("杭州五一旅游攻略")
        if hit:
            return hit.data
        results = await search(query)
        cache.set_search(query, results)

        # L4 响应缓存
        hit = cache.get_l4("杭州五一有什么好玩的", context=session_id)
        if hit:
            return hit.data
        answer = await llm.generate(query)
        cache.set_l4(query, answer, context=session_id)

        # 统计
        logger.info(cache.stats())
    """

    def __init__(
        self,
        l0_max_size: int = 100,
        l0_ttl_hours: float = 24.0,
        l4_memory_size: int = 1000,
        l4_ttl_days: int = 7,
        query_max_length: int = 200,
        similar_threshold: float = 0.5,
        compressor_model: str = "qwen2.5:1.5b",
        # 新增：容量管理配置
        max_memory_mb: int = 500,
        max_disk_mb: int = 5000,
        enable_smart_config: bool = True,
    ):
        self.normalizer = QueryNormalizer(max_length=query_max_length)
        self.compressor = QueryCompressor(model=compressor_model)
        self.similar = SimilarQueryDetector(similarity_threshold=similar_threshold)
        self.l0 = L0RouteCache(
            max_size=l0_max_size,
            ttl_hours=l0_ttl_hours,
            normalizer=self.normalizer,
        )
        self.search = SearchCache()
        self.l4 = L4ResponseCache(
            memory_size=l4_memory_size,
            ttl_days=l4_ttl_days,
            normalizer=self.normalizer,
        )
        self._stats = CacheStats()
        self._lock = threading.Lock()
        
        # 智能配置（TTL + 容量管理）
        if enable_smart_config:
            self._smart_config = SmartCacheConfig(
                max_memory_mb=max_memory_mb,
                max_disk_mb=max_disk_mb,
                enable_adaptive_ttl=True,
                enable_capacity_management=True,
            )
        else:
            self._smart_config = None

    # ── L0 路由缓存 ──────────────────────────────────────────────────────────

    def get_l0_route(self, query: str) -> Optional[CacheHit]:
        """获取 L0 路由缓存"""
        with self._lock:
            self._stats.total_requests += 1
            hit = self.l0.get(query)
            if hit:
                self._stats.cache_hits += 1
                self._stats.l0_hits += 1
                self._stats.total_latency_saved_ms += 50.0  # 假设节省50ms
            else:
                self._stats.cache_misses += 1
            return hit

    def set_l0_route(self, query: str, route_decision: Dict[str, Any]):
        """缓存路由决策"""
        self.l0.set(query, route_decision)

    # ── Search 缓存 ─────────────────────────────────────────────────────────

    def get_search(self, query: str, context: str = None) -> Optional[CacheHit]:
        """获取搜索缓存"""
        with self._lock:
            self._stats.total_requests += 1
            hit = self.search.get(query, context)
            if hit:
                self._stats.cache_hits += 1
                if hit.tier == "L1":
                    self._stats.l1_hits += 1
                elif hit.tier == "L2":
                    self._stats.l2_hits += 1
                elif hit.tier == "L3":
                    self._stats.l3_hits += 1
                self._stats.total_latency_saved_ms += 200.0  # 搜索节省200ms
            else:
                self._stats.cache_misses += 1
            return hit

    def set_search(self, query: str, response: Any, context: str = None, model_id: str = None):
        """缓存搜索结果"""
        self.search.set(query, response, context, model_id)

    # ── L4 响应缓存 ─────────────────────────────────────────────────────────

    def get_l4(self, query: str, context: str = None) -> Optional[CacheHit]:
        """获取 L4 响应缓存"""
        with self._lock:
            self._stats.total_requests += 1
            hit = self.l4.get(query, context)
            if hit:
                self._stats.cache_hits += 1
                self._stats.l4_hits += 1
                self._stats.total_latency_saved_ms += 5000.0  # LLM节省5s
            else:
                self._stats.cache_misses += 1
            return hit

    def set_l4(self, query: str, response: str, context: str = None, metadata: Dict = None):
        """缓存 L4 响应"""
        self.l4.set(query, response, context, metadata)

    def exists_l4(self, query: str, context: str = None) -> bool:
        """快速判断 L4 缓存是否存在"""
        return self.l4.exists(query, context)

    # ── 相似 query 检测（新增） ──────────────────────────────────────────────

    def find_similar(self, query: str) -> Optional[Dict[str, Any]]:
        """
        查找相似的已缓存 query（核心增强）

        支持三种匹配策略：
        1. Ollama 真实向量相似度（需 embedding 模型，阈值 0.85）
        2. 关键词 Jaccard 语义相似度（阈值 0.5）
        3. 字符编辑距离（阈值 0.85）

        Returns:
            {
                "query": str,          # 缓存中的原始 query
                "response": Any,       # 缓存的响应
                "similarity": float,   # 相似度分数
                "match_type": str,    # "semantic" | "keyword_jaccard" | "char_edit_distance"
            }
            或 None（无相似）
        """
        return self.similar.find_similar(query)

    def store_similar(self, query: str, response: Any, model_id: str = None):
        """存储 query-response 到相似缓存"""
        self.similar.store(query, response, model_id)

    def search_similar(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """查找 top-k 最相似的已缓存 query"""
        return self.similar.search_similar(query, top_k)

    # ── 全链路查询 ──────────────────────────────────────────────────────────

    def get_all(self, query: str, context: str = None) -> Dict[str, Optional[CacheHit]]:
        """查询所有层级的缓存（用于调试和分析）"""
        return {
            "l0": self.get_l0_route(query),
            "search": self.get_search(query, context),
            "l4": self.get_l4(query, context),
        }

    # ── 统计 ────────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """获取综合统计"""
        result = {
            "overall": self._stats.to_dict(),
            "l0": self.l0.stats(),
            "search": self.search.stats(),
            "l4": self.l4.stats(),
            "similar": self.similar.stats(),
        }
        
        # 添加智能配置状态
        if self._smart_config:
            result["smart_config"] = self._smart_config.get_status()
        
        return result

    def clear_all(self):
        """清空所有缓存"""
        self.l0.clear()
        self.search.clear()
        self.l4.clear()
        self.similar.clear()
        with self._lock:
            self._stats = CacheStats()

    def print_report(self):
        """打印缓存报告"""
        s = self.stats()
        logger.info("\n" + "=" * 60)
        logger.info("📊 统一缓存状态报告".center(52))
        logger.info("=" * 60)
        ov = s["overall"]
        logger.info(f"  总请求: {ov['total_requests']}  |  命中: {ov['cache_hits']}  |  未命中: {ov['cache_misses']}")
        logger.info(f"  综合命中率: {ov['hit_rate']}")
        logger.info("-" * 60)
        logger.info(f"  L0 路由缓存: {s['l0']['l0_hits']} hits / {s['l0']['l0_cache_size']} 条目")
        logger.info(f"  Search 缓存: {s['search']['search_hits']} hits | {s['search']['tier_hits']}")
        l4s = s["l4"]
        logger.info(f"  L4 响应缓存: {l4s['l4_hits']} hits | exact: {l4s['exact_cache'].get('hit_rate', 'N/A')}")
        sim = s.get("similar", {})
        logger.info(f"  相似缓存: {sim.get('hits', 0)} hits / {sim.get('entries', 0)} 条 | 模式: {sim.get('mode', 'N/A')}")
        logger.info(f"  总计节省延迟: {ov['total_latency_saved_ms']:.0f} ms")
        
        # 智能配置信息
        if "smart_config" in s:
            sc = s["smart_config"]
            cap = sc.get("capacity", {})
            logger.info("-" * 60)
            logger.info(f"  智能配置:")
            logger.info(f"    自适应 TTL: {sc.get('adaptive_ttl', False)}")
            logger.info(f"    容量管理: {sc.get('capacity_management', False)}")
            logger.info(f"    内存使用: {cap.get('memory_mb', 0):.0f}MB / {cap.get('memory_percent', 0):.1%}")
            logger.info(f"    磁盘使用: {cap.get('disk_mb', 0):.0f}MB / {cap.get('disk_percent', 0):.1%}")
        
        logger.info("=" * 60)
    
    # ── 智能 TTL 接口 ─────────────────────────────────────────────────────────
    
    def get_ttl_for_intent(self, intent: str, query: str = "") -> int:
        """
        根据意图类型获取 TTL
        
        Args:
            intent: 意图类型
            query: 原始查询（用于检测实时性）
            
        Returns:
            int: TTL 秒数
        """
        if self._smart_config:
            return self._smart_config.get_ttl(intent, query)
        return 604800  # 默认 7 天
    
    def record_intent_hit(self, intent: str):
        """记录意图缓存命中"""
        if self._smart_config:
            self._smart_config.record_hit(intent)
    
    def record_intent_miss(self, intent: str):
        """记录意图缓存未命中"""
        if self._smart_config:
            self._smart_config.record_miss(intent)
    
    def should_evict_entries(self) -> bool:
        """检查是否需要淘汰条目"""
        if self._smart_config:
            return self._smart_config.should_evict()
        return False


# ════════════════════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════════════════════

_cache_instance: Optional[UnifiedCache] = None
_cache_lock = threading.Lock()


def get_unified_cache(
    query_max_length: int = 200,
        similar_threshold: float = 0.5,
        l0_max_size: int = 100,
        l4_memory_size: int = 1000,
        compressor_model: str = "qwen2.5:1.5b",
) -> UnifiedCache:
    """获取全局统一缓存实例（线程安全单素）"""
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = UnifiedCache(
                    query_max_length=query_max_length,
                    similar_threshold=similar_threshold,
                    l0_max_size=l0_max_size,
                    l4_memory_size=l4_memory_size,
                    compressor_model=compressor_model,
                )
                logger.info("全局实例已创建")
    return _cache_instance


def reset_unified_cache():
    """重置全局缓存实例"""
    global _cache_instance
    with _cache_lock:
        if _cache_instance:
            _cache_instance.clear_all()
        _cache_instance = None


# ════════════════════════════════════════════════════════════════════════════
# 增强2: 智能 TTL 配置 + 按意图类型动态过期
# ════════════════════════════════════════════════════════════════════════════

class IntentBasedTTL:
    """
    基于意图类型的智能 TTL 配置
    
    不同类型的问题有不同的时效性：
    - 知识查询：长时间有效（7天）
    - 实时数据：短时间有效（1小时）
    - 代码生成：中等时间有效（3天）
    - 闲聊对话：短时间有效（1小时）
    
    使用示例：
        ttl_manager = IntentBasedTTL()
        ttl = ttl_manager.get_ttl("knowledge_query")  # → 604800 秒 (7天)
        ttl_manager.set_ttl("calculation", 3600)     # 设置为 1 小时
    """
    
    # 默认 TTL 配置（秒）
    DEFAULT_TTL = {
        # === 对话类 ===
        "greeting": 86400,          # 问候: 1天
        "chitchat": 3600,          # 闲聊: 1小时
        "question": 43200,          # 问答: 12小时
        
        # === 推理类 ===
        "reasoning": 604800,       # 逻辑推理: 7天
        "mathematics": 259200,     # 数学: 3天
        "analysis": 432000,        # 分析: 5天
        
        # === 任务类 ===
        "code_generation": 259200, # 代码生成: 3天
        "code_review": 172800,     # 代码审查: 2天
        "debugging": 86400,        # 调试: 1天
        "file_operation": 7200,    # 文件操作: 2小时
        "task_execution": 3600,    # 任务执行: 1小时
        
        # === 创作类 ===
        "writing": 432000,         # 写作: 5天
        "translation": 604800,     # 翻译: 7天
        "summarization": 432000,  # 摘要: 5天
        "creative": 259200,        # 创意: 3天
        
        # === 知识类 ===
        "knowledge_query": 604800, # 知识查询: 7天
        "search": 86400,          # 搜索: 1天
        
        # === 其他 ===
        "calculation": 172800,    # 计算: 2天
        "unknown": 43200,         # 未知: 12小时
        
        # === 实时性关键词 ===
        "realtime_news": 1800,     # 新闻: 30分钟
        "realtime_stock": 300,    # 股票: 5分钟
        "realtime_weather": 3600,  # 天气: 1小时
    }
    
    # 实时数据关键词（自动检测）
    REALTIME_KEYWORDS = [
        # 新闻
        "今天", "刚刚", "最新", "新闻", "资讯", "头条",
        # 股票
        "股价", "涨跌", "大盘", "指数", "股票", "基金净值",
        # 天气
        "天气", "气温", "下雨", "温度", "天气预报",
        # 时间敏感
        "现在", "当前", "此刻", "实时",
    ]
    
    def __init__(self, custom_ttl: Dict[str, int] = None):
        """
        Args:
            custom_ttl: 自定义 TTL 配置，会覆盖默认值
        """
        self._ttl_config = self.DEFAULT_TTL.copy()
        if custom_ttl:
            self._ttl_config.update(custom_ttl)
        
        # TTL 调整因子（根据命中率动态调整）
        self._hit_counts: Dict[str, int] = {}
        self._adjustment_factor: Dict[str, float] = {}
    
    def get_ttl(self, intent: str, query: str = "") -> int:
        """
        获取 TTL 秒数
        
        Args:
            intent: 意图类型
            query: 原始查询（用于检测实时性关键词）
            
        Returns:
            int: TTL 秒数
        """
        # 1. 检测实时性关键词
        if query and self._is_realtime_query(query):
            return self._ttl_config.get("realtime_news", 1800)
        
        # 2. 获取意图对应的 TTL
        base_ttl = self._ttl_config.get(intent, self._ttl_config["unknown"])
        
        # 3. 应用动态调整因子
        adjustment = self._adjustment_factor.get(intent, 1.0)
        adjusted_ttl = int(base_ttl * adjustment)
        
        return max(60, min(adjusted_ttl, 2592000))  # 限制在 1 分钟 ~ 30 天之间
    
    def _is_realtime_query(self, query: str) -> bool:
        """检测是否是实时性查询"""
        query_lower = query.lower()
        for keyword in self.REALTIME_KEYWORDS:
            if keyword in query_lower:
                return True
        return False
    
    def record_hit(self, intent: str):
        """记录缓存命中（用于动态调整 TTL）"""
        self._hit_counts[intent] = self._hit_counts.get(intent, 0) + 1
        
        # 高频命中的问题，延长 TTL
        if self._hit_counts[intent] >= 10:
            self._adjustment_factor[intent] = min(
                self._adjustment_factor.get(intent, 1.0) * 1.2,
                3.0  # 最多延长 3 倍
            )
    
    def record_miss(self, intent: str):
        """记录缓存未命中（用于动态调整 TTL）"""
        hits = self._hit_counts.get(intent, 0)
        if hits > 0:
            self._hit_counts[intent] = hits - 1
        
        # 持续未命中，降低 TTL
        if hits < 3:
            self._adjustment_factor[intent] = max(
                self._adjustment_factor.get(intent, 1.0) * 0.8,
                0.5  # 最低缩短到 50%
            )
    
    def set_ttl(self, intent: str, ttl_seconds: int):
        """设置某个意图的 TTL"""
        self._ttl_config[intent] = max(60, ttl_seconds)
    
    def get_ttl_config(self) -> Dict[str, int]:
        """获取当前 TTL 配置"""
        return self._ttl_config.copy()
    
    def reset_adjustments(self):
        """重置动态调整因子"""
        self._hit_counts.clear()
        self._adjustment_factor.clear()


class CacheCapacityManager:
    """
    缓存容量管理器
    
    功能：
    - 监控各层缓存大小
    - 设置容量限制
    - 自动淘汰低价值条目
    - 磁盘配额管理
    """
    
    def __init__(
        self,
        max_memory_mb: int = 500,
        max_disk_mb: int = 5000,
        eviction_threshold: float = 0.9,
    ):
        """
        Args:
            max_memory_mb: 内存缓存最大容量 (MB)
            max_disk_mb: 磁盘缓存最大容量 (MB)
            eviction_threshold: 淘汰阈值 (达到 90% 开始淘汰)
        """
        self.max_memory_mb = max_memory_mb
        self.max_disk_mb = max_disk_mb
        self.eviction_threshold = eviction_threshold
        
        self._current_memory_mb: float = 0.0
        self._current_disk_mb: float = 0.0
        self._lock = threading.Lock()
    
    def get_usage(self) -> Dict[str, float]:
        """获取当前使用情况"""
        return {
            "memory_mb": self._current_memory_mb,
            "memory_percent": self._current_memory_mb / self.max_memory_mb if self.max_memory_mb > 0 else 0,
            "disk_mb": self._current_disk_mb,
            "disk_percent": self._current_disk_mb / self.max_disk_mb if self.max_disk_mb > 0 else 0,
        }
    
    def update_usage(self, memory_mb: float, disk_mb: float = 0.0):
        """更新使用情况"""
        with self._lock:
            self._current_memory_mb = memory_mb
            self._current_disk_mb = disk_mb
    
    def should_evict(self) -> bool:
        """检查是否需要淘汰"""
        return self._current_memory_mb > self.max_memory_mb * self.eviction_threshold
    
    def get_eviction_count(self, cache_type: str = "memory") -> int:
        """计算需要淘汰的条目数"""
        max_mb = self.max_memory_mb if cache_type == "memory" else self.max_disk_mb
        current_mb = self._current_memory_mb if cache_type == "memory" else self._current_disk_mb
        
        if current_mb <= max_mb * self.eviction_threshold:
            return 0
        
        # 计算需要释放的空间（20%）
        target_mb = max_mb * 0.7
        excess_mb = current_mb - target_mb
        
        # 假设每个条目平均 1KB
        return int(excess_mb * 1024)
    
    def set_limits(self, max_memory_mb: int = None, max_disk_mb: int = None):
        """设置容量限制"""
        if max_memory_mb is not None:
            self.max_memory_mb = max_memory_mb
        if max_disk_mb is not None:
            self.max_disk_mb = max_disk_mb


class SmartCacheConfig:
    """
    智能缓存配置管理器
    
    整合 TTL 配置和容量管理，提供统一的配置接口
    """
    
    def __init__(
        self,
        # TTL 配置
        ttl_config: Dict[str, int] = None,
        
        # 容量配置
        max_memory_mb: int = 500,
        max_disk_mb: int = 5000,
        
        # 缓存行为配置
        enable_adaptive_ttl: bool = True,
        enable_capacity_management: bool = True,
        eviction_threshold: float = 0.9,
        
        # 预热配置
        enable_preload: bool = False,
        preload_intents: List[str] = None,
    ):
        self.intent_ttl = IntentBasedTTL(ttl_config)
        self.capacity = CacheCapacityManager(
            max_memory_mb=max_memory_mb,
            max_disk_mb=max_disk_mb,
            eviction_threshold=eviction_threshold,
        )
        self.enable_adaptive_ttl = enable_adaptive_ttl
        self.enable_capacity_management = enable_capacity_management
        self.enable_preload = enable_preload
        self.preload_intents = preload_intents or ["knowledge_query", "translation"]
    
    def get_ttl(self, intent: str, query: str = "") -> int:
        """获取 TTL"""
        return self.intent_ttl.get_ttl(intent, query)
    
    def record_hit(self, intent: str):
        """记录命中"""
        if self.enable_adaptive_ttl:
            self.intent_ttl.record_hit(intent)
    
    def record_miss(self, intent: str):
        """记录未命中"""
        if self.enable_adaptive_ttl:
            self.intent_ttl.record_miss(intent)
    
    def should_evict(self) -> bool:
        """检查是否需要淘汰"""
        if not self.enable_capacity_management:
            return False
        return self.capacity.should_evict()
    
    def get_eviction_count(self, cache_type: str = "memory") -> int:
        """获取需要淘汰的条目数"""
        if not self.enable_capacity_management:
            return 0
        return self.capacity.get_eviction_count(cache_type)
    
    def get_status(self) -> Dict[str, Any]:
        """获取配置状态"""
        return {
            "adaptive_ttl": self.enable_adaptive_ttl,
            "capacity_management": self.enable_capacity_management,
            "preload_enabled": self.enable_preload,
            "preload_intents": self.preload_intents,
            "capacity": self.capacity.get_usage(),
            "ttl_config_sample": {
                k: v for k, v in list(self.intent_ttl.get_ttl_config().items())[:5]
            },
        }


# ════════════════════════════════════════════════════════════════════════════
# 全局配置实例
# ════════════════════════════════════════════════════════════════════════════

_smart_config: Optional[SmartCacheConfig] = None
_config_lock = threading.Lock()


def get_smart_cache_config(
    max_memory_mb: int = 500,
    max_disk_mb: int = 5000,
    enable_adaptive_ttl: bool = True,
) -> SmartCacheConfig:
    """获取全局智能缓存配置"""
    global _smart_config
    if _smart_config is None:
        with _config_lock:
            if _smart_config is None:
                _smart_config = SmartCacheConfig(
                    max_memory_mb=max_memory_mb,
                    max_disk_mb=max_disk_mb,
                    enable_adaptive_ttl=enable_adaptive_ttl,
                )
    return _smart_config


def reset_smart_cache_config():
    """重置全局配置"""
    global _smart_config
    with _config_lock:
        _smart_config = None

