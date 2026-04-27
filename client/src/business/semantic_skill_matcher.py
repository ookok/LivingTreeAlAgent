"""
SemanticSkillMatcher - 语义 Skill 匹配器（通用·Embedding 版）

功能：
1. 对输入文档计算 embedding
2. 与所有已注册 Skill 的 embedding 做余弦相似度计算
3. similarity > 阈值 → 自动触发对应 Skill
4. 无匹配 → 提示用户是否从当前文档提炼新 Skill

使用方法：
    from client.src.business.semantic_skill_matcher import SemanticSkillMatcher

    matcher = SemanticSkillMatcher()
    matched = matcher.match(document_text="通知内容…")
    if matched:
        print(f"自动触发 Skill: {matched['name']}")
        # 加载 SKILL.md 并执行检查
    else:
        print("未匹配到 Skill，是否创建新 Skill？")

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

import requests

from loguru import logger


# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #

OLLAMA_URL        = "http://localhost:11434"
EMBEDDING_MODEL  = "nomic-embed-text"
SIMILARITY_THRESHOLD = 0.75    # 触发阈值（可调整）
TOP_K               = 3        # 返回 top-k 个匹配结果


# --------------------------------------------------------------------------- #
# SemanticSkillMatcher
# --------------------------------------------------------------------------- #

class SemanticSkillMatcher:
    """
    语义 Skill 匹配器

    工作流程：
    1. 扫描 `.livingtree/skills/` 下所有子目录
    2. 加载每个 Skill 的 `embedding.json`（无则跳过或现场计算）
    3. 对输入文档计算 embedding
    4. 计算余弦相似度，返回 top-k 匹配结果
    """

    def __init__(
        self,
        skills_base_dir: str = ".livingtree/skills",
        ollama_url: str = OLLAMA_URL,
        embedding_model: str = EMBEDDING_MODEL,
        threshold: float = SIMILARITY_THRESHOLD,
    ):
        # 解析为绝对路径（相对于项目根目录）
        if os.path.isabs(skills_base_dir):
            self._skills_base = skills_base_dir
        else:
            # 项目根目录 = client/src/ 的上两级
            base = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )
            self._skills_base = os.path.join(base, skills_base_dir)

        self._ollama_url     = ollama_url.rstrip("/")
        self._embedding_model = embedding_model
        self._threshold        = threshold

        # 缓存：skill_dir → embedding vector
        self._cache: Dict[str, List[float]] = {}

        logger.info(f"[SemanticSkillMatcher] 初始化，skills 目录: {self._skills_base}")

    # ==================================================================== #
    # 公有接口
    # ==================================================================== #

    def match(
        self,
        document_text: str,
        top_k: int = TOP_K,
    ) -> List[Dict]:
        """
        对文档做语义匹配，返回最相似的 Skill 列表

        Args:
            document_text: 待检查文档文本
            top_k:         返回 top-k 个结果

        Returns:
            [
                {
                    "skill_dir":  "路径",
                    "name":       "Skill 名称",
                    "description": "触发描述",
                    "similarity":  0.87,
                    "skill_md":    "SKILL.md 全文",
                },
                ...
            ]
        """
        # 1. 计算输入文档的 embedding
        query_vec = self._get_embedding(document_text[:2000])
        if not query_vec:
            logger.warning("[SemanticSkillMatcher] 文档 embedding 计算失败")
            return []

        # 2. 加载所有 Skill embedding
        skill_embs = self._load_all_skill_embeddings()

        # 3. 计算相似度，排序
        results = []
        for skill_dir, emb_data in skill_embs.items():
            vec = emb_data.get("embedding", [])
            if not vec or len(vec) != len(query_vec):
                continue

            sim = self._cosine_similarity(query_vec, vec)
            if sim >= self._threshold:
                # 读取 SKILL.md
                skill_md_path = os.path.join(skill_dir, "SKILL.md")
                skill_md = ""
                if os.path.exists(skill_md_path):
                    with open(skill_md_path, "r", encoding="utf-8") as f:
                        skill_md = f.read()

                # 从 YAML frontmatter 提取 name / description
                name = self._extract_frontmatter_field(skill_md, "name")
                desc = self._extract_frontmatter_field(skill_md, "description")

                results.append({
                    "skill_dir":   skill_dir,
                    "name":         name or os.path.basename(skill_dir),
                    "description":  desc or "",
                    "similarity":   round(sim, 4),
                    "skill_md":      skill_md,
                })

        # 按相似度降序排列，取 top-k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def match_best(self, document_text: str) -> Optional[Dict]:
        """
        返回最匹配的 Skill（similarity 最高且 > threshold）

        Returns:
            Dict（同 match() 的单条记录）或 None
        """
        results = self.match(document_text, top_k=1)
        return results[0] if results else None

    def auto_trigger(
        self,
        document_text: str,
        treshold: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        自动触发：若匹配到 Skill，返回 Skill 的触发描述；否则提示创建新 Skill

        Returns:
            (triggered: bool, message: str)
        """
        t = treshold or self._treshold
        results = self.match(document_text, top_k=1)

        if results and results[0]["similarity"] >= t:
            best = results[0]
            msg = (
                f"✅ 自动匹配到 Skill：「{best['name']}」"
                f"（相似度：{best['similarity']}）\n"
                f"触发描述：{best['description']}\n\n"
                f"是否加载此 Skill 进行检查？"
            )
            return True, msg

        # 无匹配 → 提示创建
        msg = (
            "未匹配到合适的 Skill。"
            "是否为当前文档创建一个新 Skill？（系统将自动提炼检查规则）"
        )
        return False, msg

    def refresh_cache(self) -> None:
        """清空缓存，重新加载"""
        self._cache.clear()
        logger.info("[SemanticSkillMatcher] 缓存已清空")

    # ==================================================================== #
    # 内部方法：加载所有 Skill Embedding
    # ==================================================================== #

    def _load_all_skill_embeddings(self) -> Dict[str, Dict]:
        """
        扫描 skills_base 下所有子目录，加载 embedding.json

        Returns:
            {skill_dir: {"embedding": [...], "triggers": [...], ...}}
        """
        results = {}

        if not os.path.isdir(self._skills_base):
            logger.warning(f"[SemanticSkillMatcher] skills 目录不存在: {self._skills_base}")
            return results

        for entry in os.listdir(self._skills_base):
            skill_dir = os.path.join(self._skills_base, entry)
            if not os.path.isdir(skill_dir):
                continue

            embedding_path = os.path.join(skill_dir, "embedding.json")
            if not os.path.exists(embedding_path):
                logger.debug(f"[SemanticSkillMatcher] 跳过（无 embedding.json）: {entry}")
                continue

            # 检查缓存
            if skill_dir in self._cache:
                # 缓存只存 vector，需要重新构造返回结构
                results[skill_dir] = {
                    "embedding": self._cache[skill_dir],
                    "triggers":  [],
                }
                continue

            try:
                with open(embedding_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                vec = data.get("embedding", [])
                if vec:
                    self._cache[skill_dir] = vec
                    results[skill_dir] = data
                    logger.debug(f"[SemanticSkillMatcher] 已加载: {entry}（维度：{len(vec)}）")
            except Exception as e:
                logger.error(f"[SemanticSkillMatcher] 加载失败 {embedding_path}: {e}")

        logger.info(f"[SemanticSkillMatcher] 共加载 {len(results)} 个 Skill embedding")
        return results

    # ==================================================================== #
    # 内部方法：Embedding 计算（Ollama 本地）
    # ==================================================================== #

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        调用 Ollama Embedding API 计算文本向量

        API: POST http://localhost:11434/api/embeddings
        """
        try:
            resp = requests.post(
                f"{self._ollama_url}/api/embeddings",
                json={"model": self._embedding_model, "prompt": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding", [])
            if embedding:
                logger.debug(f"[SemanticSkillMatcher] embedding 计算成功（维度：{len(embedding)}）")
                return embedding
            else:
                logger.warning(f"[SemanticSkillMatcher] embedding 为空: {data}")
                return None
        except Exception as e:
            logger.error(f"[SemanticSkillMatcher] embedding 计算失败: {e}")
            return None

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """余弦相似度"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ==================================================================== #
    # 内部方法：解析 SKILL.md YAML frontmatter
    # ==================================================================== #

    def _extract_frontmatter_field(self, skill_md: str, field: str) -> str:
        """
        从 SKILL.md 的 YAML frontmatter 中提取字段值

        格式：
        ---
        name: XXX
        description: YYY
        ---
        """
        # 简单正则提取（不依赖 pyyaml，减少依赖）
        pattern = rf"^{field}\s*:\s*(.+)$"
        for line in skill_md.splitlines()[:20]:   # 只检查前 20 行
            match = re.search(pattern, line.strip())
            if match:
                return match.group(1).strip()
        return ""


# --------------------------------------------------------------------------- #
# 便捷函数
# --------------------------------------------------------------------------- #

def match_document_to_skill(document_text: str) -> List[Dict]:
    """
    便捷函数：文档 → 匹配 Skill 列表

    Args:
        document_text: 待检查文档

    Returns:
        匹配结果列表（同 SemanticSkillMatcher.match()）
    """
    matcher = SemanticSkillMatcher()
    return matcher.match(document_text)


def auto_trigger_skill(document_text: str) -> Tuple[bool, str]:
    """
    便捷函数：自动触发 Skill 匹配

    Returns:
        (是否触发, 消息)
    """
    matcher = SemanticSkillMatcher()
    return matcher.auto_trigger(document_text)
