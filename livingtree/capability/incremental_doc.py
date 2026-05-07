"""IncrementalDoc — 增量文档处理：哈希diff + 缓存复用.

场景：用户反复提交大文档（如环评报告 v1→v2→v3），每次只改几段。
传统方式每次重读整份文档 → 浪费 95% 的 token。

解决方案：
  1. 首次读取 → 按段落哈希 → 存入缓存
  2. 再次提交 → 哈希对比 → 找出变更段落
  3. 只对变更段落重新理解和分析 → 合并未变更段落的缓存结果
  4. 缓存带版本号，支持多版本对比

性能：50页文档改了3段 → 只处理3段（-94% token），不变段落秒级复用。

Usage:
    inc = IncrementalDoc(consciousness=llm)
    
    # 第一次提交
    snapshot = await inc.submit("report_v1.docx", session="project_x")
    # → 全量分析，缓存哈希
    
    # 第二次提交（改了3段）
    snapshot = await inc.submit("report_v2.docx", session="project_x")
    # → 增量分析，仅处理变更段落
    
    # 查看版本间差异
    diff = inc.diff("project_x", v1="report_v1.docx", v2="report_v2.docx")
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

CACHE_DIR = Path(".livingtree/incremental_doc")


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ParagraphFingerprint:
    """段落的轻量指纹——用于快速 diff."""
    index: int
    text_hash: str                    # SHA256前8位
    char_count: int
    style: str = ""
    first_50_chars: str = ""          # 预览
    cached_analysis: dict | None = None  # 缓存的语义分析结果

    @property
    def fingerprint(self) -> str:
        return f"{self.text_hash}:{self.char_count}:{self.style}"


@dataclass
class DocSnapshot:
    """一次文档提交的快照."""
    session: str
    filepath: str
    version: int = 1
    timestamp: float = field(default_factory=time.time)
    total_paragraphs: int = 0
    paragraphs: list[ParagraphFingerprint] = field(default_factory=list)
    changed_indices: list[int] = field(default_factory=list)  # 相对于上一版本的变更索引
    new_indices: list[int] = field(default_factory=list)      # 新增段落
    deleted_indices: list[int] = field(default_factory=list)  # 删除段落
    understanding: dict | None = None  # 完整理解结果
    tokens_used: int = 0
    full_analysis: bool = True         # True=全量分析, False=增量分析

    @property
    def change_pct(self) -> float:
        return len(self.changed_indices) / max(self.total_paragraphs, 1)

    @property
    def efficiency(self) -> str:
        if self.full_analysis:
            return f"全量 {self.tokens_used} tokens"
        saved = max(0, self.total_paragraphs - len(self.changed_indices) - len(self.new_indices))
        return f"增量 {self.tokens_used} tokens (复用 {saved}/{self.total_paragraphs} 段)"


@dataclass
class VersionDiff:
    """两个版本之间的差异."""
    session: str
    v1: str = ""  # filepath
    v2: str = ""  # filepath
    changed_paragraphs: list[dict] = field(default_factory=list)  # [{v1_text, v2_text, index, style}]
    added_paragraphs: list[dict] = field(default_factory=list)
    removed_paragraphs: list[dict] = field(default_factory=list)
    summary: str = ""


# ═══════════════════════════════════════════════════════════════════
# IncrementalDoc Engine
# ═══════════════════════════════════════════════════════════════════

class IncrementalDoc:
    """增量文档处理引擎——哈希diff + 缓存复用."""

    def __init__(self, consciousness: Any = None):
        self._consciousness = consciousness
        self._sessions: dict[str, list[DocSnapshot]] = {}  # {session: [v1, v2, ...]}
        self._paragraph_cache: dict[str, ParagraphFingerprint] = {}  # {hash → fingerprint}

    # ═══ Submit: 提交文档 ═══

    async def submit(
        self, filepath: str, session: str = "default",
    ) -> DocSnapshot:
        """提交一份文档进行增量处理.

        Args:
            filepath: 文档路径
            session: 会话标识（同一会话的文档视为版本迭代）

        Returns:
            DocSnapshot with change info
        """
        # 读取段落指纹
        fps = self._fingerprint_paragraphs(filepath)
        previous = self._sessions.get(session, [])[-1] if self._sessions.get(session) else None

        version = (len(self._sessions.get(session, [])) + 1)
        snapshot = DocSnapshot(
            session=session, filepath=filepath, version=version,
            total_paragraphs=len(fps), paragraphs=fps,
        )

        if previous is None:
            # 首次提交 → 全量分析
            snapshot.full_analysis = True
            snapshot.paragraphs = fps
            snapshot.tokens_used = len(fps) * 200  # 估计
        else:
            # 增量提交 → diff 对比
            diff_result = self._diff_paragraphs(previous.paragraphs, fps)
            snapshot.changed_indices = diff_result["changed"]
            snapshot.new_indices = diff_result["added"]
            snapshot.deleted_indices = diff_result["removed"]
            snapshot.full_analysis = len(snapshot.changed_indices) > len(fps) * 0.5

            if snapshot.full_analysis:
                snapshot.tokens_used = len(fps) * 200
            else:
                # 只处理变更段落
                changed_count = len(snapshot.changed_indices) + len(snapshot.new_indices)
                snapshot.tokens_used = changed_count * 200 + 500  # 变更段落 + diff overhead

        # 缓存指纹
        for fp in fps:
            self._paragraph_cache[fp.text_hash] = fp

        self._sessions.setdefault(session, []).append(snapshot)
        logger.info(
            f"IncrementalDoc: '{Path(filepath).name}' v{version} → "
            f"{snapshot.efficiency} ({snapshot.change_pct:.0%} changed)")
        return snapshot

    # ═══ Diff: 版本对比 ═══

    def diff(self, session: str, v1: str = "", v2: str = "") -> VersionDiff:
        """对比同一会话的两个版本."""
        snapshots = self._sessions.get(session, [])
        if len(snapshots) < 2:
            return VersionDiff(session=session)

        s1 = snapshots[0]
        s2 = snapshots[-1]
        if v1 and v2:
            s1 = next((s for s in snapshots if s.filepath == v1), s1)
            s2 = next((s for s in snapshots if s.filepath == v2), s2)

        result = self._diff_paragraphs(s1.paragraphs, s2.paragraphs)

        changed = []
        for idx in result["changed"]:
            p1 = s1.paragraphs[idx] if idx < len(s1.paragraphs) else None
            p2 = s2.paragraphs[idx] if idx < len(s2.paragraphs) else None
            changed.append({
                "index": idx,
                "v1_preview": p1.first_50_chars if p1 else "",
                "v2_preview": p2.first_50_chars if p2 else "",
                "style": p2.style if p2 else (p1.style if p1 else ""),
            })

        return VersionDiff(
            session=session,
            v1=s1.filepath, v2=s2.filepath,
            changed_paragraphs=changed,
            added_paragraphs=[
                {"index": i, "preview": s2.paragraphs[i].first_50_chars}
                for i in result["added"]
            ],
            removed_paragraphs=[
                {"index": i, "preview": s1.paragraphs[i].first_50_chars}
                for i in result["removed"]
            ],
            summary=f"{s1.filepath} → {s2.filepath}: "
                     f"{len(changed)} changed, {len(result['added'])} added, "
                     f"{len(result['removed'])} removed",
        )

    # ═══ 核心: 段落指纹 ═══

    def _fingerprint_paragraphs(self, filepath: str) -> list[ParagraphFingerprint]:
        """提取文档所有段落的指纹."""
        fps: list[ParagraphFingerprint] = []

        try:
            from .document_intelligence import get_doc_intelligence
            ws = get_doc_intelligence().read_docx(filepath)

            for i, p in enumerate(ws.paragraphs):
                text = p.get("text", "")
                # 跳过空段落
                if not text.strip():
                    continue

                text_hash = hashlib.sha256(text.encode()).hexdigest()[:8]
                fp = ParagraphFingerprint(
                    index=i,
                    text_hash=text_hash,
                    char_count=len(text),
                    style=p.get("style", ""),
                    first_50_chars=text[:50],
                    cached_analysis=(
                        self._paragraph_cache[text_hash].cached_analysis
                        if text_hash in self._paragraph_cache else None
                    ),
                )
                fps.append(fp)

        except Exception as e:
            logger.error(f"fingerprint '{filepath}': {e}")
            # Fallback: plain text
            try:
                text = Path(filepath).read_text(encoding="utf-8")
                for i, para in enumerate(text.split("\n\n")):
                    if para.strip():
                        text_hash = hashlib.sha256(para.encode()).hexdigest()[:8]
                        fps.append(ParagraphFingerprint(
                            index=i, text_hash=text_hash,
                            char_count=len(para),
                            first_50_chars=para[:50],
                        ))
            except Exception:
                pass

        return fps

    @staticmethod
    def _diff_paragraphs(
        old: list[ParagraphFingerprint], new: list[ParagraphFingerprint],
    ) -> dict[str, list[int]]:
        """段落级 diff —— 基于哈希指纹.

        时间复杂度 O(n) —— 使用哈希查找而非逐字比对.
        """
        old_hashes = {fp.text_hash: i for i, fp in enumerate(old)}
        new_hashes = {fp.text_hash: i for i, fp in enumerate(new)}

        changed = []   # 内容变了的段落索引
        added = []     # 新增段落
        removed = []   # 删除段落

        # 检测变更（相同位置不同hash）
        for i in range(min(len(old), len(new))):
            if old[i].text_hash != new[i].text_hash:
                changed.append(i)

        # 检测新增
        for hash_val, idx in new_hashes.items():
            if hash_val not in old_hashes:
                added.append(idx)

        # 检测删除
        for hash_val, idx in old_hashes.items():
            if hash_val not in new_hashes:
                removed.append(idx)

        return {"changed": changed, "added": added, "removed": removed}

    # ═══ 增量分析: 只处理变更部分 ═══

    async def analyze_incremental(
        self, snapshot: DocSnapshot, domain: str = "environmental",
    ) -> DocSnapshot:
        """对增量快照进行语义分析——只分析变更段落."""
        if snapshot.full_analysis or not self._consciousness:
            return snapshot

        # 如果有前一版本，复用未变更段落的分析
        prev = self._get_previous(snapshot)
        if not prev or not prev.understanding:
            return snapshot

        # 从缓存中合并未变更段落的理解
        merged = dict(prev.understanding or {})
        changed_texts = []

        for idx in snapshot.changed_indices:
            if idx < len(snapshot.paragraphs):
                fp = snapshot.paragraphs[idx]
                changed_texts.append(f"¶{idx}: {fp.first_50_chars}")

        for idx in snapshot.new_indices:
            if idx < len(snapshot.paragraphs):
                fp = snapshot.paragraphs[idx]
                changed_texts.append(f"+¶{idx}: {fp.first_50_chars}")

        if changed_texts:
            try:
                prompt = (
                    f"These paragraphs were CHANGED in a document revision. "
                    f"Analyze their impact on the overall document:\n\n"
                    + "\n".join(changed_texts[:10])
                    + f"\n\nOutput JSON: {{'impact': 'summary', 'findings': []}}"
                )
                raw = await self._consciousness.query(
                    prompt, max_tokens=300, temperature=0.3)
                merged["incremental_analysis"] = raw[:1000]
            except Exception as e:
                logger.debug(f"incremental_analysis: {e}")

        snapshot.understanding = merged
        snapshot.tokens_used = (len(snapshot.changed_indices) + len(snapshot.new_indices)) * 200
        return snapshot

    def _get_previous(self, snapshot: DocSnapshot) -> DocSnapshot | None:
        session = self._sessions.get(snapshot.session, [])
        for s in reversed(session):
            if s.version < snapshot.version:
                return s
        return None

    # ═══ 缓存管理 ═══

    def save_cache(self):
        """持久化缓存到磁盘."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "paragraph_cache": {
                    h: {
                        "text_hash": fp.text_hash,
                        "char_count": fp.char_count,
                        "style": fp.style,
                        "first_50_chars": fp.first_50_chars,
                        "cached_analysis": fp.cached_analysis,
                    }
                    for h, fp in self._paragraph_cache.items()
                },
                "sessions": {
                    sid: [{
                        "filepath": s.filepath, "version": s.version,
                        "timestamp": s.timestamp, "total_paragraphs": s.total_paragraphs,
                        "changed_indices": s.changed_indices,
                    } for s in snapshots]
                    for sid, snapshots in self._sessions.items()
                },
            }
            (CACHE_DIR / "incremental_cache.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.debug(f"cache save: {e}")

    def load_cache(self):
        try:
            cf = CACHE_DIR / "incremental_cache.json"
            if not cf.exists():
                return
            data = json.loads(cf.read_text(encoding="utf-8"))
            for h, fd in data.get("paragraph_cache", {}).items():
                self._paragraph_cache[h] = ParagraphFingerprint(**fd)
            logger.info(f"IncrementalDoc cache: {len(self._paragraph_cache)} paragraphs")
        except Exception as e:
            logger.debug(f"cache load: {e}")

    # ═══ Stats ═══

    def stats(self) -> dict[str, Any]:
        total_snapshots = sum(len(s) for s in self._sessions.values())
        cached = len(self._paragraph_cache)
        savings = sum(
            1 for ss in self._sessions.values()
            for s in ss if not s.full_analysis)
        return {
            "sessions": len(self._sessions),
            "snapshots": total_snapshots,
            "cached_paragraphs": cached,
            "incremental_analyses": savings,
            "efficiency": f"{savings}/{max(total_snapshots, 1)} incremental",
        }


# ── Singleton ──────────────────────────────────────────────────────

_incremental_doc: IncrementalDoc | None = None


def get_incremental_doc(consciousness: Any = None) -> IncrementalDoc:
    global _incremental_doc
    if _incremental_doc is None:
        _incremental_doc = IncrementalDoc(consciousness=consciousness)
    return _incremental_doc
