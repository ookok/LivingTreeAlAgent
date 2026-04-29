# external_absorption.py — 外部营养吸收模块
# 从 Reddit/知乎/微博/GitHub 抓取热点争论，AI消化并标记差异

import json
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from .models import ExternalInsight, ExternalSource, SafetyLevel


class ExternalAbsorption:
    """
    外部营养吸收器

    功能：
    1. 从多个平台抓取热点内容
    2. AI 消化并提取关键观点
    3. 对比本地认知，标记差异
    4. 安全审查后入库
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / ".hermes-desktop" / "self_upgrade"
        self.insights_dir = self.data_dir / "external_insights"
        self.insights_dir.mkdir(parents=True, exist_ok=True)

        # 平台配置
        self._platforms = {
            "reddit": {
                "enabled": False,
                "subreddits": ["MachineLearning", "programming", "artificial"],
                "api_endpoint": "https://www.reddit.com/r/{subreddit}/hot.json",
            },
            "zhihu": {
                "enabled": False,
                "topics": ["人工智能", "机器学习", "编程"],
                "api_endpoint": "https://api.zhihu.com/topics",
            },
            "github": {
                "enabled": True,
                "repos": ["microsoft/vscode", "openai/gym"],
                "api_endpoint": "https://api.github.com/repos/{repo}/issues",
            },
        }

    # ============================================================
    # 抓取接口（最小化实现，支持扩展）
    # ============================================================

    async def fetch_reddit_trending(
        self, subreddit: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        抓取 Reddit 热门帖子

        注意：Reddit API 需要认证，实际使用需要：
        1. Reddit API 注册获取 client_id/client_secret
        2. 使用 PRAW 库 或 自行实现 OAuth
        这里提供骨架代码
        """
        # 骨架实现 - 实际需要 Reddit API 认证
        return []

    async def fetch_github_issues(
        self, repo: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        抓取 GitHub Issues

        可以使用: pip install PyGithub
        """
        try:
            from github import Github
            # 需要 GITHUB_TOKEN 环境变量
            import os
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                return []

            g = Github(token)
            repo_obj = g.get_repo(repo)
            issues = repo_obj.get_issues(state="open", sort="created")[:limit]

            result = []
            for issue in issues:
                result.append({
                    "title": issue.title,
                    "body": issue.body or "",
                    "url": issue.html_url,
                    "comments": issue.comments,
                    "labels": [l.name for l in issue.labels],
                    "created_at": issue.created_at.isoformat(),
                })
            return result
        except ImportError:
            print("[ExternalAbsorption] PyGithub not installed")
            return []
        except Exception as e:
            print(f"[ExternalAbsorption] GitHub fetch failed: {e}")
            return []

    async def fetch_zhihu_daily(self, topic: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        抓取知乎日报

        注意：知乎有反爬机制，实际使用需要：
        1. 登录态 Cookie
        2. 或使用 zhihu-oauth 库
        """
        return []

    # ============================================================
    # 核心：消化外部内容
    # ============================================================

    async def absorb(
        self,
        source: ExternalSource,
        content: Dict[str, Any],
        local_belief: str = "",
    ) -> ExternalInsight:
        """
        消化外部内容，生成洞察

        Args:
            source: 来源平台
            content: 抓取的内容
            local_belief: 本地原有认知

        Returns:
            ExternalInsight: 消化后的洞察
        """
        insight = ExternalInsight(
            id=str(uuid.uuid4()),
            source=source,
            source_url=content.get("url", ""),
            source_title=content.get("title", ""),
            content_summary=self._summarize(content),
            key_points=self._extract_key_points(content),
            local_belief=local_belief,
            difference_flagged="",
        )

        # 标记与本地认知的差异
        if local_belief:
            insight.difference_flagged = self._find_difference(
                insight.key_points, local_belief
            )

        # 安全审查
        from .safety_pipeline import check_safety
        safety_result = check_safety(
            insight.content_summary + " " + " ".join(insight.key_points)
        )
        insight.safety_level = safety_result.level

        # 保存
        self._save_insight(insight)

        return insight

    def _summarize(self, content: Dict[str, Any]) -> str:
        """提取摘要（简化版，实际可用 LLM）"""
        body = content.get("body", "") or content.get("text", "") or ""
        title = content.get("title", "")

        # 简单截断
        if len(body) > 300:
            return title + " — " + body[:300] + "..."
        return title + " — " + body

    def _extract_key_points(self, content: Dict[str, Any]) -> List[str]:
        """提取关键观点（简化版）"""
        points = []

        # 从标题提取
        title = content.get("title", "")
        if title:
            points.append(title)

        # 从标签提取
        labels = content.get("labels", []) or content.get("tags", [])
        if labels:
            points.extend([f"标签: {l}" for l in labels[:3]])

        # 从评论数推断热度
        comments = content.get("comments", 0)
        if comments and comments > 10:
            points.append(f"高热度讨论 ({comments} 评论)")

        return points[:5]  # 最多5个点

    def _find_difference(self, external_points: List[str], local_belief: str) -> str:
        """标记与本地认知的差异"""
        # 简化实现：检查关键词重叠度
        local_words = set(local_belief.lower().split())

        for point in external_points:
            point_words = set(point.lower().split())
            overlap = local_words & point_words
            if len(overlap) < 2:  # 重叠词少，可能是新观点
                return f"新观点: {point}"

        return "与本地认知一致"

    # ============================================================
    # 吸收历史
    # ============================================================

    def _insight_path(self, insight_id: str) -> Path:
        return self.insights_dir / f"{insight_id}.json"

    def _save_insight(self, insight: ExternalInsight):
        data = {
            "id": insight.id,
            "source": insight.source.value,
            "source_url": insight.source_url,
            "source_title": insight.source_title,
            "content_summary": insight.content_summary,
            "key_points": insight.key_points,
            "local_belief": insight.local_belief,
            "difference_flagged": insight.difference_flagged,
            "absorbed": insight.absorbed,
            "absorbed_at": insight.absorbed_at.isoformat() if insight.absorbed_at else None,
            "safety_level": insight.safety_level.value,
            "created_at": insight.created_at.isoformat(),
        }
        path = self._insight_path(insight.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_insight(self, insight_id: str) -> Optional[ExternalInsight]:
        path = self._insight_path(insight_id)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return ExternalInsight(
            id=data["id"],
            source=ExternalSource(data["source"]),
            source_url=data["source_url"],
            source_title=data["source_title"],
            content_summary=data["content_summary"],
            key_points=data["key_points"],
            local_belief=data["local_belief"],
            difference_flagged=data["difference_flagged"],
            absorbed=data["absorbed"],
            absorbed_at=datetime.fromisoformat(data["absorbed_at"]) if data["absorbed_at"] else None,
            safety_level=SafetyLevel(data["safety_level"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def list_insights(
        self,
        source: Optional[ExternalSource] = None,
        absorbed: Optional[bool] = None,
        limit: int = 50,
    ) -> List[ExternalInsight]:
        """列出洞察"""
        insights = []
        count = 0

        for f in sorted(self.insights_dir.glob("*.json"), reverse=True):
            if count >= limit:
                break

            insight = self.load_insight(f.stem)
            if not insight:
                continue

            if source and insight.source != source:
                continue
            if absorbed is not None and insight.absorbed != absorbed:
                continue

            insights.append(insight)
            count += 1

        return insights

    def mark_absorbed(self, insight_id: str) -> bool:
        """标记为已吸收"""
        insight = self.load_insight(insight_id)
        if not insight:
            return False

        insight.absorbed = True
        insight.absorbed_at = datetime.now()
        self._save_insight(insight)
        return True

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        insights = self.list_insights(limit=1000)
        return {
            "total": len(insights),
            "absorbed": sum(1 for i in insights if i.absorbed),
            "pending": sum(1 for i in insights if not i.absorbed),
            "by_source": {
                s.value: sum(1 for i in insights if i.source == s)
                for s in ExternalSource
            },
        }


# 全局单例
_external_absorption: Optional[ExternalAbsorption] = None


def get_external_absorption() -> ExternalAbsorption:
    global _external_absorption
    if _external_absorption is None:
        _external_absorption = ExternalAbsorption()
    return _external_absorption
