"""
智能创作与内容监控系统 - 规则引擎
零成本敏感词匹配与告警
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from .models import AlertLevel, AlertRecord, ContentItem, MonitoringRule, RuleType, SensitiveWord


class TrieNode:
    """敏感词Trie树节点"""
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.is_end: bool = False
        self.word: Optional[SensitiveWord] = None
        self.fail: Optional['TrieNode'] = None


class RuleEngine:
    """规则引擎 - 零成本内容监控核心"""
    
    def __init__(self):
        self.rules: Dict[str, MonitoringRule] = {}
        self.trie_root = TrieNode()
        self.regex_cache: Dict[str, re.Pattern] = {}
        self.match_stats: Dict[str, int] = defaultdict(int)
        self._sensitive_words_list: List[SensitiveWord] = []  # 敏感词列表
        self._init_builtin_words()
        self._build_ac_automaton()
    
    def _init_builtin_words(self):
        """初始化内置敏感词库"""
        builtin_words = [
            # 政治敏感词 (Level 4)
            ("敏感词1", "政治", AlertLevel.CRITICAL), ("敏感词2", "政治", AlertLevel.CRITICAL),
            # 暴力犯罪词 (Level 3)
            ("暴力词1", "暴力", AlertLevel.HIGH), ("暴力词2", "暴力", AlertLevel.HIGH),
            # 低俗色情词 (Level 2)
            ("低俗词1", "低俗", AlertLevel.MEDIUM), ("低俗词2", "低俗", AlertLevel.MEDIUM),
            # 违规广告词 (Level 1)
            ("广告词1", "广告", AlertLevel.LOW), ("广告词2", "广告", AlertLevel.LOW),
        ]
        for word, category, level in builtin_words:
            self.add_sensitive_word(word, category, level)
    
    def add_sensitive_word(self, word: str, category: str = "default",
                          alert_level: AlertLevel = AlertLevel.LOW):
        """添加敏感词到Trie树"""
        node = self.trie_root
        for char in word.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end = True
        node.word = SensitiveWord(word=word, category=category, alert_level=alert_level)
        # 同时添加到列表
        if word not in [w.word for w in self._sensitive_words_list]:
            self._sensitive_words_list.append(
                SensitiveWord(word=word, category=category, alert_level=alert_level)
            )

    def get_sensitive_words(self) -> List[SensitiveWord]:
        """获取所有敏感词列表"""
        return list(self._sensitive_words_list)
    
    def _build_ac_automaton(self):
        """构建AC自动机(用于高效多模式匹配)"""
        # 设置初始fail指针
        for child in self.trie_root.children.values():
            child.fail = self.trie_root
        
        # BFS构建fail指针
        queue = list(self.trie_root.children.values())
        while queue:
            current = queue.pop(0)
            for key, child in current.children.items():
                queue.append(child)
                fail = current.fail
                while fail and key not in fail.children:
                    fail = fail.fail
                child.fail = fail.children.get(key, self.trie_root) if fail else self.trie_root
    
    def add_rule(self, rule: MonitoringRule) -> bool:
        """添加监控规则"""
        if not rule.pattern:
            return False
        self.rules[rule.rule_id] = rule
        if rule.rule_type == RuleType.REGEX:
            try:
                self.regex_cache[rule.rule_id] = re.compile(rule.pattern)
            except re.error:
                return False
        return True
    
    def remove_rule(self, rule_id: str) -> bool:
        """移除规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self.regex_cache.pop(rule_id, None)
            return True
        return False
    
    def scan_text(self, text: str) -> List[Tuple[SensitiveWord, int]]:
        """扫描文本，返回匹配的敏感词及位置"""
        matches = []
        node = self.trie_root
        for i, char in enumerate(text.lower()):
            # 沿着fail指针回溯直到找到匹配或到达根节点
            while node and char not in node.children:
                node = node.fail
                if node is None:
                    node = self.trie_root
                    break
            
            if char in node.children:
                node = node.children[char]
            else:
                node = self.trie_root
            
            # 查找以当前位置结尾的所有匹配
            temp = node
            while temp != self.trie_root:
                if temp.is_end and temp.word:
                    matches.append((temp.word, i - len(temp.word.word) + 1))
                temp = temp.fail
                if temp is None:
                    break
        return matches
    
    def check_regex_rules(self, text: str) -> List[Tuple[MonitoringRule, re.Match]]:
        """检查正则规则"""
        matches = []
        for rule_id, pattern in self.regex_cache.items():
            rule = self.rules[rule_id]
            if rule.enabled:
                for match in pattern.finditer(text):
                    matches.append((rule, match))
        return matches
    
    def analyze_content(self, text: str) -> Tuple[AlertLevel, List[str], List[str]]:
        """
        分析内容，返回(告警级别, 匹配原因, 关键词列表)
        """
        alert_level = AlertLevel.NORMAL
        reasons = []
        keywords = []
        
        # Trie树匹配
        trie_matches = self.scan_text(text)
        for word, pos in trie_matches:
            if word.alert_level.value > alert_level.value:
                alert_level = word.alert_level
            reasons.append(f"[{word.category}] 匹配敏感词: {word.word}")
            keywords.append(word.word)
            self.match_stats[word.category] += 1
        
        # 正则规则匹配
        regex_matches = self.check_regex_rules(text)
        for rule, match in regex_matches:
            if rule.alert_level.value > alert_level.value:
                alert_level = rule.alert_level
            reasons.append(f"[{rule.category}] 匹配规则: {rule.name}")
            keywords.append(match.group())
            self.match_stats[rule.name] += 1
        
        return alert_level, reasons, keywords
    
    def get_stats(self) -> Dict[str, int]:
        """获取匹配统计"""
        return dict(self.match_stats)
    
    def export_rules(self) -> List[Dict]:
        """导出所有规则"""
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "type": r.rule_type.value,
                "pattern": r.pattern,
                "alert_level": r.alert_level.value,
                "enabled": r.enabled
            }
            for r in self.rules.values()
        ]
    
    def import_rules(self, rules_data: List[Dict]) -> int:
        """导入规则"""
        count = 0
        for data in rules_data:
            try:
                rule = MonitoringRule(
                    name=data.get("name", ""),
                    rule_type=RuleType(data.get("type", "keyword")),
                    pattern=data.get("pattern", ""),
                    alert_level=AlertLevel(data.get("alert_level", 0)),
                    enabled=data.get("enabled", True)
                )
                if self.add_rule(rule):
                    count += 1
            except Exception:
                continue
        return count
