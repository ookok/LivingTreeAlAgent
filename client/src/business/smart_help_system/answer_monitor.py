"""
Answer Monitor - 答案监控器

监控已发布问题的回复情况：
1. 定时轮询检查新回复
2. 记录回答者信息
3. 追踪回答质量
4. 推送通知给用户
"""

import time
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import hashlib

from .platform_selector import Platform


class MonitorStatus(Enum):
    """监控状态"""
    PENDING = "pending"           # 待发布
    MONITORING = "monitoring"     # 监控中
    ANSWERED = "answered"         # 已有回复
    SOLVED = "solved"             # 已解决
    EXPIRED = "expired"           # 已过期
    FAILED = "failed"            # 监控失败


@dataclass
class Answer:
    """回答"""
    answer_id: str
    author: str
    author_reputation: int       # 回答者声誉
    content: str
    upvotes: int
    is_accepted: bool            # 是否被提问者采纳
    posted_at: datetime
    quality_score: float = 0.0   # 质量评分


@dataclass
class MonitoredPost:
    """监控的帖子"""
    post_id: str
    platform: Platform
    post_url: str
    title: str
    status: MonitorStatus
    posted_at: datetime
    last_checked_at: datetime
    answers: List[Answer] = field(default_factory=list)
    total_views: int = 0
    total_answers: int = 0
    notification_count: int = 0

    @property
    def has_new_answers(self) -> bool:
        """是否有新回复"""
        return len(self.answers) > 0

    @property
    def best_answer(self) -> Optional[Answer]:
        """最佳回答（优先采纳，其次点赞最多）"""
        if not self.answers:
            return None
        accepted = [a for a in self.answers if a.is_accepted]
        if accepted:
            return accepted[0]
        return max(self.answers, key=lambda x: x.upvotes)


@dataclass
class MonitoringConfig:
    """监控配置"""
    check_interval_seconds: int = 300  # 默认5分钟检查一次
    max_monitor_hours: int = 72        # 最多监控72小时
    min_answers_for_quality: int = 3   # 计算质量所需的最低回答数
    auto_solve_threshold: float = 0.8  # 自动标记已解决的置信度阈值


class AnswerMonitor:
    """
    答案监控器

    功能：
    1. 多平台帖子监控（模拟实现，实际需要API）
    2. 新回答检测
    3. 回答质量评估
    4. 自动通知
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self._monitored_posts: Dict[str, MonitoredPost] = {}
        self._monitor_threads: Dict[str, threading.Thread] = {}
        self._callbacks: List[Callable] = []
        self._running = False

    def start_monitoring(self, post: MonitoredPost) -> str:
        """
        开始监控一个帖子

        Args:
            post: 要监控的帖子

        Returns:
            监控ID
        """
        monitor_id = self._generate_monitor_id(post)
        post.post_id = monitor_id
        post.status = MonitorStatus.MONITORING
        self._monitored_posts[monitor_id] = post

        # 启动监控线程
        thread = threading.Thread(
            target=self._monitor_loop,
            args=(monitor_id,),
            daemon=True
        )
        self._monitor_threads[monitor_id] = thread
        thread.start()

        return monitor_id

    def stop_monitoring(self, monitor_id: str) -> bool:
        """停止监控"""
        if monitor_id in self._monitor_threads:
            # 标记为不再运行（通过状态检查）
            if monitor_id in self._monitored_posts:
                self._monitored_posts[monitor_id].status = MonitorStatus.EXPIRED
            del self._monitor_threads[monitor_id]
            return True
        return False

    def stop_all(self):
        """停止所有监控"""
        self._running = False
        for monitor_id in list(self._monitor_threads.keys()):
            self.stop_monitoring(monitor_id)

    def get_post_status(self, monitor_id: str) -> Optional[MonitoredPost]:
        """获取帖子监控状态"""
        return self._monitored_posts.get(monitor_id)

    def get_all_monitored_posts(self) -> List[MonitoredPost]:
        """获取所有监控中的帖子"""
        return [
            post for post in self._monitored_posts.values()
            if post.status == MonitorStatus.MONITORING
        ]

    def register_callback(self, callback: Callable[[MonitoredPost, Answer], None]):
        """注册新回答回调"""
        self._callbacks.append(callback)

    def _generate_monitor_id(self, post: MonitoredPost) -> str:
        """生成监控ID"""
        content = f"{post.platform.value}_{post.post_url}_{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _monitor_loop(self, monitor_id: str):
        """监控循环"""
        post = self._monitored_posts.get(monitor_id)
        if not post:
            return

        self._running = True
        start_time = datetime.now()
        max_duration = timedelta(hours=self.config.max_monitor_hours)

        while self._running and post.status == MonitorStatus.MONITORING:
            try:
                # 检查是否超时
                if datetime.now() - start_time > max_duration:
                    post.status = MonitorStatus.EXPIRED
                    break

                # 检查新回答
                new_answers = self._fetch_new_answers(post)

                for answer in new_answers:
                    if answer.answer_id not in [a.answer_id for a in post.answers]:
                        post.answers.append(answer)
                        post.total_answers += 1
                        post.status = MonitorStatus.ANSWERED

                        # 触发回调
                        self._notify_callbacks(post, answer)

                        # 检查是否可以标记为解决
                        if self._should_mark_solved(post):
                            post.status = MonitorStatus.SOLVED

                # 更新最后检查时间
                post.last_checked_at = datetime.now()

            except Exception as e:
                print(f"Monitor error for {monitor_id}: {e}")

            # 等待下次检查
            time.sleep(self.config.check_interval_seconds)

    def _fetch_new_answers(self, post: MonitoredPost) -> List[Answer]:
        """
        获取新回答（模拟实现）

        实际实现需要调用各平台的API
        """
        # 模拟：每次检查随机返回0-2个回答
        import random
        new_count = random.randint(0, 2)

        answers = []
        for i in range(new_count):
            answer = Answer(
                answer_id=f"{post.post_id}_ans_{len(post.answers) + i}_{int(time.time())}",
                author=f"user_{random.randint(1000, 9999)}",
                author_reputation=random.randint(10, 10000),
                content=self._generate_simulated_answer_content(post, i),
                upvotes=random.randint(0, 100),
                is_accepted=False,
                posted_at=datetime.now() - timedelta(minutes=random.randint(1, 60)),
                quality_score=random.uniform(0.5, 1.0)
            )
            answers.append(answer)

        return answers

    def _generate_simulated_answer_content(
        self,
        post: MonitoredPost,
        index: int
    ) -> str:
        """生成模拟回答内容"""
        templates = [
            "根据我的经验，这个问题可以通过以下方式解决...",
            "建议您尝试使用XX方法，这是最常用的解决方案。",
            "这个问题我之前也遇到过，我是这样处理的...",
            "查看官方文档后发现，需要注意以下几点...",
            "可以尝试这个库，它可能有您需要的功能。",
        ]
        return templates[index % len(templates)]

    def _should_mark_solved(self, post: MonitoredPost) -> bool:
        """判断是否应该标记为已解决"""
        if not post.answers:
            return False

        # 检查是否有被采纳的回答
        if any(a.is_accepted for a in post.answers):
            return True

        # 检查是否有高质量回答
        high_quality_count = sum(
            1 for a in post.answers
            if a.quality_score >= self.config.auto_solve_threshold
        )

        if high_quality_count >= 2:
            return True

        return False

    def _notify_callbacks(self, post: MonitoredPost, answer: Answer):
        """通知回调"""
        post.notification_count += 1
        for callback in self._callbacks:
            try:
                callback(post, answer)
            except Exception as e:
                print(f"Callback error: {e}")

    def get_answer_summary(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        """获取回答摘要"""
        post = self._monitored_posts.get(monitor_id)
        if not post:
            return None

        return {
            "post_id": monitor_id,
            "title": post.title,
            "platform": post.platform.value,
            "total_answers": post.total_answers,
            "best_answer": {
                "author": post.best_answer.author,
                "upvotes": post.best_answer.upvotes,
                "content_preview": post.best_answer.content[:100],
            } if post.best_answer else None,
            "status": post.status.value,
            "monitoring_duration": str(datetime.now() - post.posted_at),
        }

    def export_answers(self, monitor_id: str) -> Optional[str]:
        """导出回答为文本"""
        post = self._monitored_posts.get(monitor_id)
        if not post or not post.answers:
            return None

        lines = [
            f"问题：{post.title}",
            f"平台：{post.platform.value}",
            f"链接：{post.post_url}",
            f"状态：{post.status.value}",
            "",
            "=" * 60,
            "回答列表：",
            "=" * 60,
            "",
        ]

        for i, answer in enumerate(post.answers, 1):
            lines.append(f"--- 回答 #{i} ---")
            lines.append(f"作者：{answer.author} (声誉: {answer.author_reputation})")
            lines.append(f"点赞：{answer.upvotes}")
            lines.append(f"时间：{answer.posted_at.strftime('%Y-%m-%d %H:%M')}")
            lines.append(f"采纳：{'是' if answer.is_accepted else '否'}")
            lines.append(f"内容：{answer.content}")
            lines.append("")

        return "\n".join(lines)

    # ========== 模拟的API调用 ==========

    def simulate_publish_to_stackoverflow(
        self,
        title: str,
        body: str,
        tags: List[str]
    ) -> str:
        """
        模拟发布到StackOverflow

        实际实现需要OAuth2 + StackExchange API
        """
        post_id = f"so_{int(time.time())}"
        return f"https://stackoverflow.com/questions/{post_id}"

    def simulate_publish_to_zhihu(
        self,
        title: str,
        body: str
    ) -> str:
        """
        模拟发布到知乎

        实际实现需要知乎OAuth
        """
        post_id = f"zh_{int(time.time())}"
        return f"https://www.zhihu.com/question/{post_id}"

    def simulate_publish_to_github(
        self,
        repo: str,
        title: str,
        body: str,
        labels: List[str]
    ) -> str:
        """
        模拟发布到GitHub Issue

        实际实现需要GitHub Token + REST API
        """
        post_id = f"gh_{int(time.time())}"
        return f"https://github.com/{repo}/issues/{post_id}"

    def publish_post(
        self,
        platform: Platform,
        title: str,
        body: str,
        tags: Optional[List[str]] = None,
        github_repo: Optional[str] = None
    ) -> MonitoredPost:
        """
        发布帖子并开始监控

        Args:
            platform: 目标平台
            title: 标题
            body: 正文
            tags: 标签（用于GitHub）
            github_repo: GitHub仓库（用于GitHub平台）

        Returns:
            MonitoredPost: 监控中的帖子
        """
        tags = tags or []

        # 根据平台发布
        if platform == Platform.STACKOVERFLOW:
            url = self.simulate_publish_to_stackoverflow(title, body, tags)
        elif platform == Platform.ZHIHU:
            url = self.simulate_publish_to_zhihu(title, body)
        elif platform == Platform.GITHUB:
            url = self.simulate_publish_to_github(github_repo or "user/repo", title, body, tags)
        else:
            url = f"https://{platform.value}.com/post/{int(time.time())}"

        # 创建监控帖子
        post = MonitoredPost(
            post_id="",
            platform=platform,
            post_url=url,
            title=title,
            status=MonitorStatus.PENDING,
            posted_at=datetime.now(),
            last_checked_at=datetime.now()
        )

        # 开始监控
        monitor_id = self.start_monitoring(post)

        return self._monitored_posts[monitor_id]
