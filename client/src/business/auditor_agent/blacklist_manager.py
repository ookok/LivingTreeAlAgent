"""
黑名单管理器 - 记录陷阱模式

用于记录审计过程中发现的问题模式，避免重复犯错。
模拟人类"吃一堑长一智"的过程。
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BlacklistEntry:
    """黑名单条目"""
    id: str
    pattern: str
    description: str
    category: str
    severity: str  # high, medium, low
    occurrences: int = 0
    last_seen: str = ""
    fix_suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BlacklistManager:
    """
    黑名单管理器
    
    管理被审计发现的问题模式，用于：
    1. 在生成时避免重复出现相同问题
    2. 记录陷阱模式供未来规避
    3. 支持EvoSkill学习
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".livingtree" / "blacklist.json"
        self.blacklist: Dict[str, BlacklistEntry] = {}
        self._load_blacklist()
    
    def _load_blacklist(self):
        """加载黑名单"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for entry_id, entry_data in data.items():
                        self.blacklist[entry_id] = BlacklistEntry(**entry_data)
                logger.info(f"✅ 已加载 {len(self.blacklist)} 条黑名单记录")
            except Exception as e:
                logger.warning(f"⚠️ 加载黑名单失败: {e}")
    
    def _save_blacklist(self):
        """保存黑名单"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {entry.id: entry.__dict__ for entry in self.blacklist.values()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存黑名单失败: {e}")
    
    def add_pattern(self, pattern: str, description: str, category: str, severity: str = "medium", fix_suggestion: Optional[str] = None):
        """
        添加黑名单模式
        
        Args:
            pattern: 问题模式（可以是关键词、正则表达式等）
            description: 问题描述
            category: 问题类别
            severity: 严重程度
            fix_suggestion: 修复建议
        """
        # 检查是否已存在
        existing_entry = self.find_pattern(pattern)
        if existing_entry:
            existing_entry.occurrences += 1
            existing_entry.last_seen = datetime.now().isoformat()
            logger.debug(f"📝 更新黑名单模式: {pattern} (出现次数: {existing_entry.occurrences})")
        else:
            entry_id = f"blk_{hash(pattern) % 1000000:06d}"
            entry = BlacklistEntry(
                id=entry_id,
                pattern=pattern,
                description=description,
                category=category,
                severity=severity,
                occurrences=1,
                last_seen=datetime.now().isoformat(),
                fix_suggestion=fix_suggestion
            )
            self.blacklist[entry_id] = entry
            logger.info(f"➕ 添加黑名单模式: {entry_id} - {pattern}")
        
        self._save_blacklist()
    
    def find_pattern(self, pattern: str) -> Optional[BlacklistEntry]:
        """查找模式"""
        for entry in self.blacklist.values():
            if entry.pattern == pattern:
                return entry
            # 检查模式是否匹配（简单的包含匹配）
            if pattern in entry.pattern or entry.pattern in pattern:
                return entry
        return None
    
    def is_blocked(self, text: str) -> bool:
        """检查文本是否包含黑名单模式"""
        for entry in self.blacklist.values():
            if entry.pattern in text:
                return True
        return False
    
    def get_blocked_patterns(self, text: str) -> List[BlacklistEntry]:
        """获取文本中包含的所有黑名单模式"""
        blocked = []
        for entry in self.blacklist.values():
            if entry.pattern in text:
                blocked.append(entry)
        return blocked
    
    def remove_pattern(self, entry_id: str):
        """移除黑名单模式"""
        if entry_id in self.blacklist:
            del self.blacklist[entry_id]
            self._save_blacklist()
            logger.info(f"➖ 移除黑名单模式: {entry_id}")
    
    def get_by_category(self, category: str) -> List[BlacklistEntry]:
        """按类别获取黑名单"""
        return [entry for entry in self.blacklist.values() if entry.category == category]
    
    def get_by_severity(self, severity: str) -> List[BlacklistEntry]:
        """按严重程度获取黑名单"""
        return [entry for entry in self.blacklist.values() if entry.severity == severity]
    
    def get_top_offenders(self, limit: int = 10) -> List[BlacklistEntry]:
        """获取出现次数最多的模式"""
        return sorted(
            self.blacklist.values(),
            key=lambda x: x.occurrences,
            reverse=True
        )[:limit]
    
    def clear(self):
        """清空黑名单"""
        self.blacklist.clear()
        self._save_blacklist()
        logger.info("🗑️ 已清空黑名单")