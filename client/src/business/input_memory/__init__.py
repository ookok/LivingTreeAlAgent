# -*- coding: utf-8 -*-
"""
输入记忆系统 - 用户专属输入预测引擎
===================================

核心理念：输入即修炼，记忆即道行

三层记忆架构：
- L0 短期记忆：实时上下文缓存（瞬时加速）
- L1 中期记忆：用户习惯模型（习惯学习）
- L2 长期记忆：道境输入指纹（个性化进化）

与道境系统融合：
- 慧心道：采纳预测增加道行
- 匠心道：术语收录增加道行
- 道境专属词库差异化联想

Author: Hermes Desktop Team
"""

import os
import json
import hashlib
import sqlite3
import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from pathlib import Path
import pickle
import zlib

# =================================================================
# 核心数据模型
# =================================================================

@dataclass
class InputRecord:
    """单次输入记录"""
    id: str
    text: str
    context: Dict[str, str]  # app, page, field_type, etc.
    timestamp: float
    duration_ms: float  # 输入耗时
    corrected: bool = False  # 是否被纠正过
    prediction_source: str = None  # 来自哪个预测源

@dataclass
class PredictionCandidate:
    """预测候选词"""
    text: str
    confidence: float
    source: str  # 'short_term' | 'ngram' | 'fingerprint' | 'knowledge'
    priority: int  # 0=最高
    context_match: float = 1.0  # 上下文匹配度

@dataclass
class UserStats:
    """用户输入统计"""
    total_inputs: int = 0
    predictions_offered: int = 0
    predictions_accepted: int = 0
    avg_input_speed: float = 0.0  # 字符/秒
    active_hours: Dict[int, int] = field(default_factory=dict)  # 小时->次数

    @property
    def acceptance_rate(self) -> float:
        if self.predictions_offered == 0:
            return 0.0
        return self.predictions_accepted / self.predictions_offered

# =================================================================
# L0 短期记忆：实时上下文缓存
# =================================================================

class ShortTermMemory:
    """短期记忆 - 本次会话内的实时上下文缓存"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.memory = deque(maxlen=max_size)  # 最近N次输入
        self.context_map: Dict[str, List[str]] = defaultdict(list)  # 上下文->输入
        self.current_context: Dict[str, str] = {}

    def hash_context(self, context: Dict[str, str]) -> str:
        """将上下文字典哈希为字符串"""
        # 简化：只用app和page
        key_parts = [
            context.get('app', 'unknown'),
            context.get('page', 'unknown'),
            context.get('field_type', 'unknown')
        ]
        return '|'.join(key_parts)

    def record(self, input_text: str, context: Dict[str, str],
               duration_ms: float = 0, prediction_source: str = None) -> str:
        """记录一次输入"""
        record_id = hashlib.md5(
            f"{input_text}{time.time()}".encode()
        ).hexdigest()[:12]

        record = InputRecord(
            id=record_id,
            text=input_text,
            context=context.copy(),
            timestamp=time.time(),
            duration_ms=duration_ms,
            prediction_source=prediction_source
        )

        self.memory.append(record)

        # 更新上下文映射
        ctx_key = self.hash_context(context)
        if input_text not in self.context_map[ctx_key]:
            self.context_map[ctx_key].append(input_text)

        return record_id

    def confirm_adoption(self, text: str):
        """标记预测被采纳"""
        for record in reversed(self.memory):
            if record.text == text:
                record.corrected = True
                break

    def predict(self, partial_input: str,
                current_context: Dict[str, str]) -> List[PredictionCandidate]:
        """基于当前上下文预测补全"""
        candidates = []
        ctx_key = self.hash_context(current_context)

        # 1. 精确前缀匹配
        for text in self.context_map.get(ctx_key, []):
            if text.startswith(partial_input) and text != partial_input:
                candidates.append(PredictionCandidate(
                    text=text,
                    confidence=0.95,  # 短期记忆高置信度
                    source='short_term',
                    priority=0,
                    context_match=1.0
                ))

        # 2. 模糊匹配（包含partial）
        for record in reversed(self.memory):
            text = record.text
            if partial_input in text and text != partial_input:
                # 检查是否已添加
                if not any(c.text == text for c in candidates):
                    candidates.append(PredictionCandidate(
                        text=text,
                        confidence=0.7,
                        source='short_term',
                        priority=1,
                        context_match=0.8
                    ))

        # 去重并返回top 5
        return self._deduplicate_and_rank(candidates)[:5]

    def _deduplicate_and_rank(self, candidates: List[PredictionCandidate]) -> List[PredictionCandidate]:
        """去重并排序"""
        seen = set()
        result = []
        for c in candidates:
            if c.text not in seen:
                seen.add(c.text)
                result.append(c)
        return sorted(result, key=lambda x: (x.priority, -x.confidence))

    def get_recent_inputs(self, limit: int = 10) -> List[str]:
        """获取最近输入"""
        return [r.text for r in list(self.memory)[-limit:]]

    def clear(self):
        """清空短期记忆"""
        self.memory.clear()
        self.context_map.clear()

# =================================================================
# L1 中期记忆：用户习惯模型
# =================================================================

class UserHabitModel:
    """中期记忆 - 用户习惯模型(n-gram频率统计)"""

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.ngram_model: Dict[str, Dict[str, int]] = {}  # n -> {gram -> count}
        for n in [2, 3, 4]:
            self.ngram_model[n] = {}

        self.timing_stats: Dict[str, List[float]] = defaultdict(list)  # 输入时长统计
        self.app_preferences: Dict[str, int] = defaultdict(int)  # 应用使用频率
        self.hourly_stats: Dict[int, int] = defaultdict(int)  # 每小时输入次数
        self.field_type_stats: Dict[str, int] = defaultdict(int)  # 字段类型统计

        # 统计
        self.total_inputs = 0
        self.total_predictions = 0
        self.total_acceptances = 0

        # 加载已有模型
        self._load_model()

    def _model_path(self) -> Path:
        return self.storage_path / "habit_model.json"

    def _load_model(self):
        """加载模型"""
        path = self._model_path()
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for n in [2, 3, 4]:
                        self.ngram_model[n] = data.get('ngrams', {}).get(str(n), {})
                    self.app_preferences = defaultdict(int, data.get('apps', {}))
                    self.hourly_stats = defaultdict(int, data.get('hours', {}))
                    self.field_type_stats = defaultdict(int, data.get('fields', {}))
                    self.total_inputs = data.get('total_inputs', 0)
                    self.total_predictions = data.get('total_predictions', 0)
                    self.total_acceptances = data.get('total_acceptances', 0)
            except Exception as e:
                print(f"加载习惯模型失败: {e}")

    def _save_model(self):
        """保存模型"""
        path = self._model_path()
        data = {
            'ngrams': {str(n): gram for n, gram in self.ngram_model.items()},
            'apps': dict(self.app_preferences),
            'hours': dict(self.hourly_stats),
            'fields': dict(self.field_type_stats),
            'total_inputs': self.total_inputs,
            'total_predictions': self.total_predictions,
            'total_acceptances': self.total_acceptances,
            'updated_at': datetime.now().isoformat()
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存习惯模型失败: {e}")

    def learn_from_input(self, input_text: str, app_context: Dict[str, Any],
                        duration_ms: float = 0):
        """从输入中学习"""
        self.total_inputs += 1

        # 更新n-gram模型
        for n in [2, 3, 4]:
            for i in range(len(input_text) - n + 1):
                gram = input_text[i:i+n]
                self.ngram_model[n][gram] = self.ngram_model[n].get(gram, 0) + 1

        # 更新应用偏好
        app = app_context.get('app', 'unknown')
        self.app_preferences[app] += 1

        # 更新时段统计
        hour = datetime.now().hour
        self.hourly_stats[hour] += 1

        # 更新字段类型统计
        field_type = app_context.get('field_type', 'unknown')
        self.field_type_stats[field_type] += 1

        # 更新输入时长统计
        if duration_ms > 0:
            key = f"{app}:{field_type}"
            self.timing_stats[key].append(duration_ms)

        # 增量保存（每100次输入保存一次）
        if self.total_inputs % 100 == 0:
            self._save_model()

    def record_prediction_offered(self):
        """记录预测被提供"""
        self.total_predictions += 1

    def record_prediction_accepted(self):
        """记录预测被采纳"""
        self.total_acceptances += 1

    def predict_next_chars(self, prefix: str, app_context: Dict[str, Any] = None) -> List[Tuple[str, float]]:
        """基于n-gram预测下一个字符"""
        candidates = []

        # 基于最后2-4个字符预测
        prefix_len = min(len(prefix), 4)

        for n in [2, 3, 4]:
            if prefix_len < n:
                continue

            suffix = prefix[-n:]
            for gram, count in self.ngram_model[n].items():
                if gram.startswith(suffix):
                    next_char = gram[-1]
                    # 计算频率权重
                    weight = count / max(1, sum(self.ngram_model[n].values()))
                    candidates.append((next_char, weight * (n / 4)))  # 越长的n-gram权重越高

        # 合并同类
        char_weights: Dict[str, float] = {}
        for char, weight in candidates:
            char_weights[char] = char_weights.get(char, 0) + weight

        # 归一化并排序
        total = sum(char_weights.values())
        if total > 0:
            result = [(c, w/total) for c, w in char_weights.items()]
        else:
            result = []

        return sorted(result, key=lambda x: -x[1])[:5]

    def predict_word_completion(self, partial_word: str,
                                 app_context: Dict[str, Any] = None) -> List[PredictionCandidate]:
        """预测单词补全"""
        candidates = []

        # 从n-gram中查找以partial开头的词
        for n in [3, 4]:
            for gram, count in self.ngram_model[n].items():
                if gram.startswith(partial_word):
                    # 提取完整词（从上下文推断）
                    word = self._extract_word(gram, partial_word, n)
                    if word and len(word) > len(partial_word):
                        confidence = min(count / 10, 0.95)  # 封顶0.95
                        candidates.append(PredictionCandidate(
                            text=word,
                            confidence=confidence,
                            source='ngram',
                            priority=1
                        ))

        # 应用偏好加权
        if app_context:
            app = app_context.get('app', 'unknown')
            app_freq = self.app_preferences.get(app, 0)
            if app_freq > 100:  # 常用应用加权
                for c in candidates:
                    c.confidence *= 1.1

        # 去重并返回
        return self._deduplicate(candidates)[:5]

    def _extract_word(self, gram: str, partial: str, n: int) -> str:
        """从n-gram提取完整词"""
        # 简化版本：直接返回gram
        if len(gram) >= len(partial):
            return gram
        return None

    def _deduplicate(self, candidates: List[PredictionCandidate]) -> List[PredictionCandidate]:
        """去重"""
        seen = set()
        result = []
        for c in candidates:
            if c.text not in seen:
                seen.add(c.text)
                result.append(c)
        return sorted(result, key=lambda x: -x.confidence)

    def get_app_preference(self, app: str) -> float:
        """获取应用偏好权重"""
        total = sum(self.app_preferences.values())
        if total == 0:
            return 1.0
        freq = self.app_preferences.get(app, 0)
        # 归一化到0.5~1.5范围
        return 0.5 + (freq / max(total, 1)) * 1.0

    def get_stats(self) -> UserStats:
        """获取用户统计"""
        stats = UserStats(
            total_inputs=self.total_inputs,
            predictions_offered=self.total_predictions,
            predictions_accepted=self.total_acceptances
        )
        stats.active_hours = dict(self.hourly_stats)
        return stats

    def compress_model(self, max_size_kb: int = 5120):
        """压缩模型，保留最高频条目"""
        for n in [2, 3, 4]:
            grams = self.ngram_model[n]
            if not grams:
                continue

            # 按频率排序，保留前N个
            sorted_grams = sorted(grams.items(), key=lambda x: -x[1])
            max_items = max_size_kb * 10 // (n * 10)  # 粗略估算
            self.ngram_model[n] = dict(sorted_grams[:max_items])

        self._save_model()

# =================================================================
# L2 长期记忆：道境输入指纹
# =================================================================

class InputFingerprint:
    """长期记忆 - 道境输入指纹，与道境系统绑定进化"""

    def __init__(self, storage_path: str, dao_realm: str = "慧心道"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.dao_realm = dao_realm
        self.evolution_level = 1
        self.specialty_terms: Dict[str, int] = {}  # 专长术语库
        self.input_patterns: Dict[str, Any] = {}   # 输入模式
        self.cross_app_enabled = False
        self.semantic_enabled = False

        # 进化进度
        self.current_exp = 0
        self.exp_to_next_level = 100

        # 道境专属词库
        self.dao_glossary: Dict[str, List[str]] = {
            "自然道": ["生态系统", "生物多样性", "可持续发展", "碳排放", "生态平衡"],
            "匠心道": ["工艺流程", "精益求精", "工匠精神", "标准化", "质量控制"],
            "慧心道": ["逻辑推理", "归纳演绎", "批判性思维", "系统分析", "认知框架"],
            "商贾道": ["供需关系", "成本效益", "风险管理", "商业模式", "市场定位"],
            "和谐道": ["平衡协调", "共识达成", "冲突化解", "合作共赢", "社区治理"],
            "真言道": ["事实核查", "逻辑自洽", "证据链", "可信度", "真实性"],
            "逍遥道": ["自由创作", "灵感激发", "意境表达", "艺术审美", "诗意栖居"],
            "守护道": ["安全防护", "风险预警", "隐私保护", "系统稳定", "容灾备份"],
            "启明道": ["循序渐进", "因材施教", "知识传递", "认知发展", "学习曲线"],
            "慧心道": ["数据分析", "模式识别", "归纳推理", "洞察本质", "智慧决策"]
        }

        self._load_fingerprint()

    def _fingerprint_path(self) -> Path:
        return self.storage_path / "input_fingerprint.json"

    def _load_fingerprint(self):
        """加载指纹"""
        path = self._fingerprint_path()
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.dao_realm = data.get('dao_realm', '慧心道')
                    self.evolution_level = data.get('level', 1)
                    self.specialty_terms = data.get('terms', {})
                    self.input_patterns = data.get('patterns', {})
                    self.current_exp = data.get('exp', 0)
                    self.exp_to_next_level = data.get('exp_needed', 100)
                    self.cross_app_enabled = data.get('cross_app', False)
                    self.semantic_enabled = data.get('semantic', False)
            except Exception as e:
                print(f"加载输入指纹失败: {e}")

    def _save_fingerprint(self):
        """保存指纹"""
        path = self._fingerprint_path()
        data = {
            'dao_realm': self.dao_realm,
            'level': self.evolution_level,
            'terms': self.specialty_terms,
            'patterns': self.input_patterns,
            'exp': self.current_exp,
            'exp_needed': self.exp_to_next_level,
            'cross_app': self.cross_app_enabled,
            'semantic': self.semantic_enabled,
            'updated_at': datetime.now().isoformat()
        }
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存输入指纹失败: {e}")

    def add_exp(self, amount: int, reason: str = ""):
        """增加经验值"""
        self.current_exp += amount

        # 检查升级
        while self.current_exp >= self.exp_to_next_level:
            self.current_exp -= self.exp_to_next_level
            self.evolution_level += 1
            self.exp_to_next_level = int(self.exp_to_next_level * 1.5)
            self._on_level_up()

        self._save_fingerprint()

    def _on_level_up(self):
        """升级回调"""
        if self.evolution_level >= 3 and not self.cross_app_enabled:
            self.cross_app_enabled = True
            print(f"[输入指纹] 解锁跨应用预测能力！")

        if self.evolution_level >= 5 and not self.semantic_enabled:
            self.semantic_enabled = True
            print(f"[输入指纹] 解锁语义预测能力！")

    def learn_term(self, term: str, context: Dict[str, Any] = None):
        """学习新术语"""
        self.specialty_terms[term] = self.specialty_terms.get(term, 0) + 1

        # 术语被多次使用时增加经验
        if self.specialty_terms[term] >= 3:
            self.add_exp(5, f"术语'{term}'被复用")

        self._save_fingerprint()

    def confirm_term(self, term: str):
        """确认术语使用"""
        if term in self.specialty_terms:
            self.add_exp(2, f"术语'{term}'被确认")
        else:
            self.learn_term(term)

    def evolve(self, new_terms: List[str], confirmed_count: int):
        """进化：基于新术语和确认次数"""
        for term in new_terms:
            self.learn_term(term)

        # 准确率奖励
        if confirmed_count > 0:
            self.add_exp(confirmed_count, "预测被确认")

        self._save_fingerprint()

    def get_dao_glossary(self) -> List[str]:
        """获取当前道境的专属词库"""
        base_terms = self.dao_glossary.get(self.dao_realm, [])
        # 添加用户自定义术语
        user_terms = [t for t, c in self.specialty_terms.items() if c >= 2]
        return list(set(base_terms + user_terms))

    def predict_with_dao(self, partial: str) -> List[PredictionCandidate]:
        """基于道境词库预测"""
        candidates = []
        glossary = self.get_dao_glossary()

        for term in glossary:
            if term.startswith(partial):
                candidates.append(PredictionCandidate(
                    text=term,
                    confidence=0.85,
                    source='fingerprint',
                    priority=0,
                    context_match=1.0
                ))

        return sorted(candidates, key=lambda x: -x.confidence)[:5]

    def predict_cross_app(self, partial: str, current_app: str) -> List[PredictionCandidate]:
        """跨应用预测（需Lv3+）"""
        if not self.cross_app_enabled:
            return []

        candidates = []
        # 从其他应用的学习中预测
        # 简化：使用n-gram的跨应用统计
        return candidates  # 实际实现需要更多上下文

    def predict_semantic(self, partial: str, context: Dict[str, Any]) -> List[PredictionCandidate]:
        """语义预测（需Lv5+）"""
        if not self.semantic_enabled:
            return []

        # 简化实现：结合上下文语义
        candidates = []
        return candidates

    def get_evolution_info(self) -> Dict[str, Any]:
        """获取进化信息"""
        return {
            'level': self.evolution_level,
            'dao_realm': self.dao_realm,
            'current_exp': self.current_exp,
            'exp_needed': self.exp_to_next_level,
            'progress': self.current_exp / self.exp_to_next_level if self.exp_to_next_level > 0 else 0,
            'cross_app_enabled': self.cross_app_enabled,
            'semantic_enabled': self.semantic_enabled,
            'terms_count': len(self.specialty_terms)
        }

# =================================================================
# 预测引擎 - 三层记忆的统一调度
# =================================================================

class PredictionEngine:
    """预测引擎 - 整合三层记忆的预测调度"""

    def __init__(self, storage_path: str, dao_realm: str = "慧心道"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 三层记忆
        self.short_term = ShortTermMemory(max_size=100)
        self.habit = UserHabitModel(str(storage_path))
        self.fingerprint = InputFingerprint(str(storage_path), dao_realm)

        # 性能统计
        self.stats = {
            'predictions_offered': 0,
            'predictions_accepted': 0,
            'avg_latency_ms': 0,
            'last_prediction_time': 0
        }

        # 锁
        self._lock = threading.Lock()

    def record_input(self, input_text: str, context: Dict[str, Any],
                     duration_ms: float = 0):
        """记录用户输入并学习"""
        with self._lock:
            # L0: 记录到短期记忆
            self.short_term.record(input_text, context, duration_ms)

            # L1: 更新习惯模型
            self.habit.learn_from_input(input_text, context, duration_ms)

            # L2: 学习术语
            words = input_text.split()
            for word in words:
                if len(word) > 3:
                    self.fingerprint.learn_term(word, context)

    def predict(self, partial_input: str, context: Dict[str, Any] = None) -> List[PredictionCandidate]:
        """综合预测"""
        if context is None:
            context = {}

        start_time = time.time()
        all_candidates: List[PredictionCandidate] = []

        # 1. L0 短期记忆（最高优先级）
        if len(partial_input) >= 1:
            st_candidates = self.short_term.predict(partial_input, context)
            all_candidates.extend(st_candidates)

        # 2. L2 道境指纹（基于道境词库）
        if len(partial_input) >= 2:
            fp_candidates = self.fingerprint.predict_with_dao(partial_input)
            all_candidates.extend(fp_candidates)

        # 3. L1 n-gram预测
        if len(partial_input) >= 2:
            ngram_candidates = self.habit.predict_word_completion(partial_input, context)
            all_candidates.extend(ngram_candidates)

        # 4. 跨应用预测（需Lv3+）
        if self.fingerprint.cross_app_enabled:
            cross_candidates = self.fingerprint.predict_cross_app(
                partial_input, context.get('app', '')
            )
            all_candidates.extend(cross_candidates)

        # 去重并排序
        result = self._merge_and_rank(all_candidates, context)

        # 更新统计
        latency = (time.time() - start_time) * 1000
        self._update_stats(result, latency)

        return result[:10]  # 最多返回10个

    def _merge_and_rank(self, candidates: List[PredictionCandidate],
                       context: Dict[str, Any]) -> List[PredictionCandidate]:
        """合并并排序候选词"""
        # 按优先级和置信度排序
        priority_order = {'short_term': 0, 'fingerprint': 1, 'ngram': 2, 'knowledge': 3}

        seen = {}
        for c in candidates:
            if c.text in seen:
                # 保留更高置信度的
                if c.confidence > seen[c.text].confidence:
                    seen[c.text] = c
            else:
                seen[c.text] = c

        result = list(seen.values())

        # 加权排序
        for c in result:
            # 优先级权重
            priority_weight = 1.0 - (priority_order.get(c.source, 2) * 0.15)
            c.confidence *= priority_weight

            # 上下文匹配权重
            c.confidence *= (0.9 + c.context_match * 0.1)

        return sorted(result, key=lambda x: -x.confidence)

    def _update_stats(self, candidates: List[PredictionCandidate], latency_ms: float):
        """更新统计"""
        self.stats['predictions_offered'] += len(candidates)
        self.stats['last_prediction_time'] = latency_ms

        # 滑动平均延迟
        current_avg = self.stats['avg_latency_ms']
        if current_avg == 0:
            self.stats['avg_latency_ms'] = latency_ms
        else:
            self.stats['avg_latency_ms'] = current_avg * 0.9 + latency_ms * 0.1

    def record_adoption(self, text: str, prediction_source: str = None):
        """记录预测被采纳"""
        self.stats['predictions_accepted'] += 1

        # 通知各层
        self.short_term.confirm_adoption(text)
        self.habit.record_prediction_accepted()
        self.fingerprint.confirm_term(text)

        # 增加道行（慧心道）
        self.fingerprint.add_exp(1, f"采纳预测'{text}'")

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        acceptance_rate = 0
        if self.stats['predictions_offered'] > 0:
            acceptance_rate = self.stats['predictions_accepted'] / self.stats['predictions_offered']

        return {
            'acceptance_rate': acceptance_rate,
            'avg_latency_ms': round(self.stats['avg_latency_ms'], 2),
            'total_predictions_offered': self.stats['predictions_offered'],
            'total_predictions_accepted': self.stats['predictions_accepted'],
            'evolution_info': self.fingerprint.get_evolution_info(),
            'user_stats': asdict(self.habit.get_stats())
        }

    def warm_up(self, likely_contexts: List[Dict[str, Any]]):
        """预测预热"""
        # 预加载常用上下文的数据
        for context in likely_contexts:
            app = context.get('app', '')
            if app:
                # 触发模型加载
                self.habit.get_app_preference(app)

    def reset_daily(self):
        """每日重置（保留长期记忆）"""
        self.short_term.clear()
        self.habit._save_model()
        print("[预测引擎] 每日重置完成，保留长期记忆")

# =================================================================
# 统一入口
# =================================================================

_global_engine: Optional[PredictionEngine] = None
_engine_lock = threading.Lock()

def get_prediction_engine(storage_path: str = None,
                          dao_realm: str = "慧心道") -> PredictionEngine:
    """获取全局预测引擎"""
    global _global_engine

    if storage_path is None:
        storage_path = Path.home() / ".hermes-desktop" / "input_memory"

    with _engine_lock:
        if _global_engine is None:
            _global_engine = PredictionEngine(str(storage_path), dao_realm)
        return _global_engine

def create_input_memory(storage_path: str = None) -> PredictionEngine:
    """创建新的输入记忆引擎（独立实例）"""
    if storage_path is None:
        storage_path = Path.home() / ".hermes-desktop" / "input_memory"

    return PredictionEngine(str(storage_path))

__all__ = [
    'InputRecord',
    'PredictionCandidate',
    'UserStats',
    'ShortTermMemory',
    'UserHabitModel',
    'InputFingerprint',
    'PredictionEngine',
    'get_prediction_engine',
    'create_input_memory',
]