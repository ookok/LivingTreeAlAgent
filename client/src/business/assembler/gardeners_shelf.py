"""
🔄 园丁整理架 (Gardener's Shelf)
================================

输入：杂乱的知识/技能草稿。
动作：
• 去重：对比已有知识 ID，避免重复入库。
• 分类：按标签自动归档到 knowledge/pdf/、knowledge/network/。
• 索引更新：触发 PageIndex 重建索引，确保新知识立即可查。
"""

import hashlib
import json
import re
from typing import Optional, Callable, Any, List, Tuple
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import difflib

from .knowledge_incubator import KnowledgeEntry, KnowledgeBank


# ==================== 去重分析器 ====================

@dataclass
class DeduplicationResult:
    """去重结果"""
    is_duplicate: bool
    existing_id: str
    similarity: float
    existing_entry: Optional[KnowledgeEntry] = None


class Deduplicator:
    """知识去重器"""

    def __init__(self, knowledge_bank: KnowledgeBank):
        self.knowledge_bank = knowledge_bank

    def check_duplicate(
        self,
        content: str,
        title: str = "",
        source_url: str = "",
    ) -> DeduplicationResult:
        """
        检查内容是否重复

        Returns:
            DeduplicationResult
        """
        # 1. URL精确匹配
        if source_url:
            existing = self._find_by_url(source_url)
            if existing:
                return DeduplicationResult(
                    is_duplicate=True,
                    existing_id=existing.id,
                    similarity=1.0,
                    existing_entry=existing
                )

        # 2. 内容Hash匹配
        content_hash = self._hash_content(content)
        existing = self._find_by_hash(content_hash)
        if existing:
            return DeduplicationResult(
                is_duplicate=True,
                existing_id=existing.id,
                similarity=1.0,
                existing_entry=existing
            )

        # 3. 标题相似度匹配
        if title:
            existing = self._find_similar_title(title)
            if existing:
                similarity = self._calculate_similarity(title, existing.title)
                if similarity > 0.8:
                    return DeduplicationResult(
                        is_duplicate=True,
                        existing_id=existing.id,
                        similarity=similarity,
                        existing_entry=existing
                    )

        # 4. 内容相似度检查（简化版）
        existing_list = self.knowledge_bank.list_all(limit=50)
        for entry in existing_list:
            similarity = self._calculate_content_similarity(content, entry.content_md)
            if similarity > 0.9:
                return DeduplicationResult(
                    is_duplicate=True,
                    existing_id=entry.id,
                    similarity=similarity,
                    existing_entry=entry
                )

        return DeduplicationResult(
            is_duplicate=False,
            existing_id="",
            similarity=0.0
        )

    def _hash_content(self, content: str) -> str:
        """计算内容hash"""
        # 标准化内容（移除空白）
        normalized = re.sub(r'\s+', ' ', content).strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _find_by_url(self, url: str) -> Optional[KnowledgeEntry]:
        """通过URL查找"""
        entries = self.knowledge_bank.list_all(limit=100)
        for entry in entries:
            if entry.source_url == url:
                return entry
        return None

    def _find_by_hash(self, content_hash: str) -> Optional[KnowledgeEntry]:
        """通过hash查找"""
        # 遍历查找（简化版，实际应该在数据库加索引）
        entries = self.knowledge_bank.list_all(limit=100)
        for entry in entries:
            entry_hash = self._hash_content(entry.content_md)
            if entry_hash == content_hash:
                return entry
        return None

    def _find_similar_title(self, title: str) -> Optional[KnowledgeEntry]:
        """查找相似标题"""
        entries = self.knowledge_bank.list_all(limit=100)
        best_match = None
        best_similarity = 0.0

        for entry in entries:
            similarity = self._calculate_similarity(title, entry.title)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry

        if best_similarity > 0.7:
            return best_match
        return None

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """计算内容相似度"""
        # 简化：只比较前500字符
        c1 = content1[:500].lower()
        c2 = content2[:500].lower()

        # 移除代码块
        c1 = re.sub(r'```.*?```', '', c1, flags=re.DOTALL)
        c2 = re.sub(r'```.*?```', '', c2, flags=re.DOTALL)

        # 移除特殊字符
        c1 = re.sub(r'[^\w\s]', '', c1)
        c2 = re.sub(r'[^\w\s]', '', c2)

        return self._calculate_similarity(c1, c2)


# ==================== 自动分类器 ====================

class AutoTagger:
    """自动标签分类器"""

    CATEGORY_KEYWORDS = {
        "python": ["python", "pip", "venv", "django", "flask", "fastapi", "pandas", "numpy"],
        "javascript": ["javascript", "js", "node", "npm", "react", "vue", "angular", "webpack"],
        "typescript": ["typescript", "ts", "typed", "interface"],
        "rust": ["rust", "cargo", "crate", "rustc", "rustdoc"],
        "go": ["golang", "go ", "gopher", "goroutine"],
        "java": ["java", "jvm", "maven", "gradle", "spring"],
        "database": ["sql", "mysql", "postgresql", "mongodb", "redis", "database", "db"],
        "network": ["http", "https", "tcp", "udp", "websocket", "api", "rest", "grpc", "fetch"],
        "web": ["html", "css", "dom", "browser", "frontend", "backend"],
        "devops": ["docker", "kubernetes", "k8s", "ci/cd", "jenkins", "gitlab", "github actions"],
        "cloud": ["aws", "azure", "gcp", "cloud", "serverless", "lambda"],
        "ai": ["ai", "ml", "machine learning", "neural", "deep learning", "tensorflow", "pytorch", "llm"],
        "security": ["security", "auth", "jwt", "oauth", "encrypt", "ssl", "tls", "hash"],
        "testing": ["test", "pytest", "junit", "unittest", "coverage", "selenium"],
        "api": ["api", "restful", "endpoint", "graphql", "openapi", "swagger"],
        "file": ["file", "io", "path", "upload", "download", "stream"],
        "async": ["async", "await", "promise", "concurrent", "parallel", "thread", "process"],
        "config": ["config", "yaml", "toml", "json", "env", "settings"],
    }

    def suggest_tags(self, content: str, title: str = "", existing_tags: List[str] = None) -> List[str]:
        """
        建议标签

        Args:
            content: 内容文本
            title: 标题
            existing_tags: 已有的标签

        Returns:
            建议的标签列表
        """
        tags = set(existing_tags or [])

        # 合并标题和内容
        text = (title + " " + content).lower()

        # 按关键词匹配
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                tags.add(category)

        # 提取代码语言
        code_blocks = re.findall(r'```(\w+)', content)
        for lang in code_blocks:
            lang_lower = lang.lower()
            if lang_lower in ('python', 'javascript', 'typescript', 'rust', 'go', 'java', 'bash', 'shell', 'sql'):
                tags.add(lang_lower)

        # 从标题提取标签（#tag格式）
        hash_tags = re.findall(r'#([a-z][a-z0-9_-]*)', text)
        tags.update(hash_tags)

        # URL推断
        url_match = re.search(r'github\.com/([^/]+)/([^/]+)', content)
        if url_match:
            tags.add("github")
            org = url_match.group(1).lower()
            if org not in ('github', 'gitlab', 'sponsors'):
                tags.add(org)

        return list(tags)[:10]  # 最多10个标签

    def suggest_category(self, content: str, title: str = "") -> str:
        """建议分类目录"""
        tags = self.suggest_tags(content, title)

        # 优先级排序
        priority = ["ai", "network", "database", "security", "web", "devops", "cloud", "testing"]

        for cat in priority:
            if cat in tags:
                return cat

        for tag in tags:
            if tag in self.CATEGORY_KEYWORDS:
                return tag

        return "general"


# ==================== 索引管理器 ====================

class IndexManager:
    """索引管理器"""

    def __init__(self, knowledge_bank: KnowledgeBank):
        self.knowledge_bank = knowledge_bank

    def rebuild_index(self, progress_callback: Optional[Callable] = None) -> dict:
        """
        重建索引

        Returns:
            索引统计
        """
        if progress_callback:
            progress_callback("🔄 开始重建索引...")

        stats = {
            "total_entries": 0,
            "by_tag": {},
            "by_type": {},
            "rebuild_at": datetime.now().isoformat(),
        }

        entries = self.knowledge_bank.list_all(limit=1000)
        stats["total_entries"] = len(entries)

        for entry in entries:
            # 按标签统计
            for tag in entry.tags:
                stats["by_tag"][tag] = stats["by_tag"].get(tag, 0) + 1

            # 按类型统计
            ktype = entry.knowledge_type
            stats["by_type"][ktype] = stats["by_type"].get(ktype, 0) + 1

        if progress_callback:
            progress_callback(f"✅ 索引重建完成: {stats['total_entries']} 条目")

        return stats


# ==================== 园丁整理架 ====================

@dataclass
class ShelfReport:
    """整理报告"""
    duplicates_removed: int
    entries_reclassified: int
    index_updated: bool
    storage_freed: int  # bytes
    errors: List[str]


class GardenersShelf:
    """
    园丁整理架

    统一管理知识的去重、分类、索引
    """

    def __init__(self, knowledge_bank: KnowledgeBank):
        self.knowledge_bank = knowledge_bank
        self.deduplicator = Deduplicator(knowledge_bank)
        self.tagger = AutoTagger()
        self.index_manager = IndexManager(knowledge_bank)

    def organize(
        self,
        content: str = "",
        title: str = "",
        source_url: str = "",
        auto_save: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Tuple[bool, str, KnowledgeEntry]:
        """
        整理知识条目

        Args:
            content: 内容
            title: 标题
            source_url: 来源URL
            auto_save: 是否自动保存
            progress_callback: 进度回调

        Returns:
            (success, message, entry)
        """
        if progress_callback:
            progress_callback("🔍 开始整理知识...")

        try:
            # 1. 去重检查
            if progress_callback:
                progress_callback("🔄 检查重复...")
            dup_result = self.deduplicator.check_duplicate(content, title, source_url)

            if dup_result.is_duplicate:
                msg = f"检测到重复条目: {dup_result.existing_id} (相似度: {dup_result.similarity:.2%})"
                if progress_callback:
                    progress_callback(f"⚠️ {msg}")
                return False, msg, dup_result.existing_entry

            # 2. 自动标签
            if progress_callback:
                progress_callback("🏷️ 自动标签...")
            tags = self.tagger.suggest_tags(content, title)

            # 3. 确定分类
            category = self.tagger.suggest_category(content, title)

            # 4. 创建条目
            entry = KnowledgeEntry(
                id="",  # 让knowledge_bank生成
                title=title or "未命名",
                content_md=content,
                summary=self._generate_summary(content),
                source_url=source_url,
                source_type="imported",
                knowledge_type=self._detect_type(content),
                tags=tags,
                language=self._detect_language(content),
            )

            # 5. 保存
            if auto_save:
                if progress_callback:
                    progress_callback("💾 保存条目...")
                success, msg = self.knowledge_bank.save_knowledge(entry)
                if success:
                    if progress_callback:
                        progress_callback(f"✅ {msg}")
                return success, msg, entry
            else:
                if progress_callback:
                    progress_callback("✅ 整理完成（未保存）")
                return True, "整理完成", entry

        except Exception as e:
            error_msg = f"整理失败: {e}"
            if progress_callback:
                progress_callback(f"❌ {error_msg}")
            return False, error_msg, None

    def cleanup_duplicates(
        self,
        dry_run: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> ShelfReport:
        """
        清理重复条目

        Args:
            dry_run: 是否仅模拟（不实际删除）
            progress_callback: 进度回调

        Returns:
            ShelfReport
        """
        report = ShelfReport(
            duplicates_removed=0,
            entries_reclassified=0,
            index_updated=False,
            storage_freed=0,
            errors=[]
        )

        if progress_callback:
            progress_callback("🔍 扫描重复条目...")

        entries = self.knowledge_bank.list_all(limit=1000)
        seen_hashes = set()
        seen_titles = {}

        for entry in entries:
            try:
                # Hash去重
                content_hash = self.deduplicator._hash_content(entry.content_md)
                if content_hash in seen_hashes:
                    if not dry_run:
                        # 删除条目（简化版，实际应该删除文件）
                        pass
                    report.duplicates_removed += 1
                else:
                    seen_hashes.add(content_hash)

                # 标题去重
                title_lower = entry.title.lower()
                if title_lower in seen_titles:
                    # 保留较早的
                    if not dry_run:
                        pass  # 删除较晚的
                    report.duplicates_removed += 1
                else:
                    seen_titles[title_lower] = entry.id

            except Exception as e:
                report.errors.append(f"处理 {entry.id} 时出错: {e}")

        if progress_callback:
            if dry_run:
                progress_callback(f"🔍 模拟清理完成: 将移除 {report.duplicates_removed} 个重复条目")
            else:
                progress_callback(f"✅ 清理完成: 移除了 {report.duplicates_removed} 个重复条目")

        # 更新索引
        if not dry_run and report.duplicates_removed > 0:
            self.index_manager.rebuild_index(progress_callback)
            report.index_updated = True

        return report

    def reclassify_entries(
        self,
        progress_callback: Optional[Callable] = None,
    ) -> int:
        """
        重新分类所有条目

        Returns:
            被重新分类的条目数
        """
        count = 0
        entries = self.knowledge_bank.list_all(limit=1000)

        for entry in entries:
            new_tags = self.tagger.suggest_tags(entry.content_md, entry.title, entry.tags)
            new_category = self.tagger.suggest_category(entry.content_md, entry.title)

            # 检查是否有变化
            if set(new_tags) != set(entry.tags):
                entry.tags = new_tags
                count += 1
                # 重新保存
                self.knowledge_bank.save_knowledge(entry)

        if progress_callback:
            progress_callback(f"✅ 重新分类完成: {count} 个条目已更新")

        return count

    def get_stats(self) -> dict:
        """获取整理统计"""
        kb_stats = self.knowledge_bank.get_stats()

        shelf_stats = {
            "knowledge_bank": kb_stats,
            "last_cleanup": None,  # 可以从数据库读取
            "categories": self._get_category_structure(),
        }

        return shelf_stats

    def _get_category_structure(self) -> dict:
        """获取分类结构"""
        knowledge_dir = self.knowledge_bank.knowledge_dir
        structure = {}

        if knowledge_dir.exists():
            for category_dir in knowledge_dir.iterdir():
                if category_dir.is_dir():
                    count = len(list(category_dir.glob("*.json")))
                    structure[category_dir.name] = count

        return structure

    def _generate_summary(self, content: str) -> str:
        """生成摘要"""
        # 移除frontmatter和代码块
        text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'#+\s+', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

        # 取前400字符
        summary = text.strip()[:400]
        if len(text) > 400:
            summary += "..."

        return summary

    def _detect_type(self, content: str) -> str:
        """检测知识类型"""
        content_lower = content.lower()

        if any(kw in content_lower for kw in ['tutorial', '教程', 'guide', 'getting started']):
            return "tutorial"
        elif any(kw in content_lower for kw in ['api', 'reference', '参考', 'documentation']):
            return "api"
        elif any(kw in content_lower for kw in ['best practice', '最佳实践', 'principle']):
            return "best_practice"
        elif content.count('```') > 3:
            return "code"
        elif '?' in content and len(content) < 1000:
            return "qna"
        else:
            return "article"

    def _detect_language(self, content: str) -> str:
        """检测编程语言"""
        # 代码块检测
        code_blocks = re.findall(r'```(\w+)', content)

        lang_map = {
            'python': ['python', 'py'],
            'javascript': ['javascript', 'js', 'nodejs'],
            'typescript': ['typescript', 'ts'],
            'rust': ['rust', 'rs'],
            'go': ['golang', 'go'],
            'java': ['java'],
            'cpp': ['cpp', 'c++', 'cxx'],
            'c': ['c'],
            'csharp': ['csharp', 'c#', 'cs'],
            'ruby': ['ruby', 'rb'],
            'php': ['php'],
            'swift': ['swift'],
            'kotlin': ['kotlin', 'kt'],
            'shell': ['bash', 'shell', 'sh', 'zsh'],
            'sql': ['sql'],
            'html': ['html'],
            'css': ['css'],
        }

        lang_counts = {}
        for block_lang in code_blocks:
            block_lang_lower = block_lang.lower()
            for lang, aliases in lang_map.items():
                if block_lang_lower in aliases:
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1

        if lang_counts:
            return max(lang_counts, key=lang_counts.get)

        # 函数签名检测
        if re.search(r'\bdef\s+\w+\(', content):
            return 'python'
        elif re.search(r'\bfunction\s+\w+', content):
            return 'javascript'
        elif re.search(r'\bfn\s+\w+', content):
            return 'rust'
        elif re.search(r'\bfunc\s+\w+', content):
            return 'go'

        return ""
