"""
社交互动子智能体

支持自动化社交互动任务：
- 批量点赞
- 智能评论
- 关注管理
- 数据监测
"""

import time
import asyncio
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from .platform_tools import (
    PlatformType,
    EngageAction,
    EngageResult,
    MultiPlatformManager,
)


# ============ 评论生成器 ============

class CommentGenerator:
    """
    评论生成器
    
    使用 LLM 生成智能评论
    """
    
    def __init__(self, llm_client: Optional[Callable] = None):
        self.llm_client = llm_client
    
    async def generate(
        self,
        content: str,
        style: str = "friendly",
        language: str = "zh"
    ) -> str:
        """
        生成评论
        
        Args:
            content: 内容
            style: 风格 (friendly, professional, humorous)
            language: 语言
            
        Returns:
            str: 生成的评论
        """
        if self.llm_client:
            # 使用 LLM 生成
            prompt = self._build_prompt(content, style, language)
            response = await self.llm_client(prompt)
            return response
        else:
            # 默认评论
            default_comments = {
                "friendly": ["很棒的内容！", "学到了，感谢分享！", "支持！"],
                "professional": ["分析到位", "观点很有见地", "值得深入研究"],
                "humorous": ["笑死我了", "哈哈太真实了", "这也太秀了"],
            }
            
            comments = default_comments.get(style, default_comments["friendly"])
            import random
            return random.choice(comments)
    
    def _build_prompt(self, content: str, style: str, language: str) -> str:
        """构建提示"""
        return f"生成一条关于以下内容的{style}风格的{language}语评论：\n{content[:200]}"


# ============ 互动分析器 ============

class EngageAnalyzer:
    """
    互动分析器
    
    分析高价值互动目标
    """
    
    def __init__(self):
        self.high_value_keywords = {
            "zh": ["求链接", "怎么买", "多少钱", "在哪", "教程", "方法"],
            "en": ["link", "buy", "price", "how to", "tutorial", "guide"],
        }
    
    def is_high_value(self, text: str, language: str = "zh") -> bool:
        """
        判断是否为高价值互动
        
        Args:
            text: 文本内容
            language: 语言
            
        Returns:
            bool: 是否高价值
        """
        keywords = self.high_value_keywords.get(language, self.high_value_keywords["en"])
        text_lower = text.lower()
        
        return any(keyword in text_lower for keyword in keywords)
    
    def get_engagement_score(self, stats: Dict[str, Any]) -> float:
        """
        计算互动得分
        
        Args:
            stats: 互动统计
            
        Returns:
            float: 得分 (0-1)
        """
        likes = stats.get("likes", 0)
        comments = stats.get("comments", 0)
        shares = stats.get("shares", 0)
        
        # 简单评分公式
        score = (likes * 0.3 + comments * 0.5 + shares * 0.2) / 1000
        return min(1.0, score)


# ============ 社交互动子智能体 ============

class SocialEngageSubAgent:
    """
    社交互动子智能体
    
    自动执行社交平台互动任务
    """
    
    def __init__(
        self,
        platform_manager: MultiPlatformManager,
        comment_generator: Optional[CommentGenerator] = None
    ):
        self.platform_manager = platform_manager
        self.comment_generator = comment_generator or CommentGenerator()
        self.analyzer = EngageAnalyzer()
        
        # 配置
        self.config = {
            "auto_comment": True,
            "auto_like": True,
            "high_value_only": False,
            "max_daily_actions": 100,
        }
        
        # 统计
        self.stats = {
            "total_likes": 0,
            "total_comments": 0,
            "total_follows": 0,
            "high_value_responses": 0,
        }
    
    async def like_post(self, platform: PlatformType, post_id: str) -> EngageResult:
        """
        点赞帖子
        
        Args:
            platform: 平台
            post_id: 帖子 ID
            
        Returns:
            EngageResult: 结果
        """
        result = await self.platform_manager.engage(
            platform,
            EngageAction.LIKE,
            post_id
        )
        
        if result.success:
            self.stats["total_likes"] += 1
        
        return result
    
    async def comment_post(
        self,
        platform: PlatformType,
        post_id: str,
        content: str = None,
        auto_generate: bool = True
    ) -> EngageResult:
        """
        评论帖子
        
        Args:
            platform: 平台
            post_id: 帖子 ID
            content: 评论内容（可选）
            auto_generate: 是否自动生成
            
        Returns:
            EngageResult: 结果
        """
        if auto_generate and not content:
            content = await self.comment_generator.generate(
                f"Post about: {post_id}",
                style="friendly",
                language="zh"
            )
        
        result = await self.platform_manager.engage(
            platform,
            EngageAction.COMMENT,
            post_id,
            content=content
        )
        
        if result.success:
            self.stats["total_comments"] += 1
        
        return result
    
    async def follow_user(self, platform: PlatformType, user_id: str) -> EngageResult:
        """
        关注用户
        
        Args:
            platform: 平台
            user_id: 用户 ID
            
        Returns:
            EngageResult: 结果
        """
        result = await self.platform_manager.engage(
            platform,
            EngageAction.FOLLOW,
            user_id
        )
        
        if result.success:
            self.stats["total_follows"] += 1
        
        return result
    
    async def batch_like(
        self,
        platform: PlatformType,
        post_ids: List[str]
    ) -> List[EngageResult]:
        """
        批量点赞
        
        Args:
            platform: 平台
            post_ids: 帖子 ID 列表
            
        Returns:
            List[EngageResult]: 结果列表
        """
        tasks = [self.like_post(platform, pid) for pid in post_ids]
        return await asyncio.gather(*tasks)
    
    async def process_high_value_comments(
        self,
        platform: PlatformType,
        comments: List[Dict[str, Any]]
    ) -> List[EngageResult]:
        """
        处理高价值评论
        
        Args:
            platform: 平台
            comments: 评论列表
            
        Returns:
            List[EngageResult]: 结果列表
        """
        results = []
        
        for comment in comments:
            text = comment.get("text", "")
            
            if self.analyzer.is_high_value(text):
                # 高价值评论，生成回复
                result = await self.comment_post(
                    platform,
                    comment.get("comment_id", ""),
                    content=f"感谢咨询！{comment.get('reply_hint', '请私信了解详情')}"
                )
                results.append(result)
                
                if result.success:
                    self.stats["high_value_responses"] += 1
            else:
                results.append(EngageResult(
                    platform=platform.value,
                    action=EngageAction.COMMENT,
                    success=False,
                    target_id=comment.get("comment_id", ""),
                    error="Not high value"
                ))
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return self.stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_likes": 0,
            "total_comments": 0,
            "total_follows": 0,
            "high_value_responses": 0,
        }


# ============ 社交监听器 ============

class SocialListener:
    """
    社交监听器
    
    监听社交平台动态
    """
    
    def __init__(self, platform_manager: MultiPlatformManager):
        self.platform_manager = platform_manager
        self.listeners: List[Callable] = []
        self.running = False
    
    def add_listener(self, callback: Callable[[Dict[str, Any]], None]):
        """添加监听器"""
        self.listeners.append(callback)
    
    def remove_listener(self, callback: Callable) -> bool:
        """移除监听器"""
        if callback in self.listeners:
            self.listeners.remove(callback)
            return True
        return False
    
    async def start_listening(self, platform: PlatformType, interval: int = 60):
        """
        开始监听
        
        Args:
            platform: 平台
            interval: 监听间隔（秒）
        """
        self.running = True
        
        while self.running:
            try:
                # 获取最新动态
                updates = await self._fetch_updates(platform)
                
                # 通知监听器
                for listener in self.listeners:
                    try:
                        listener(updates)
                    except Exception as e:
                        print(f"Listener error: {e}")
                
                # 等待下次监听
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"Listening error: {e}")
                await asyncio.sleep(interval)
    
    def stop_listening(self):
        """停止监听"""
        self.running = False
    
    async def _fetch_updates(self, platform: PlatformType) -> Dict[str, Any]:
        """获取最新动态"""
        # 模拟获取
        return {
            "platform": platform.value,
            "timestamp": time.time(),
            "mentions": [],
            "comments": [],
            "new_followers": [],
        }


# ============ 导出 ============

__all__ = [
    "CommentGenerator",
    "EngageAnalyzer",
    "SocialEngageSubAgent",
    "SocialListener",
]
