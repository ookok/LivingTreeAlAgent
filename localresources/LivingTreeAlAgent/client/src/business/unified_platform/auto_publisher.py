"""
Auto Publisher - 数字分身自动发布
==================================

功能：
- 数字分身空闲时自动发布内容
- 支持定时发布计划
- 内容模板引擎
- AI 生成内容

触发条件：
- 空闲检测（无用户交互）
- 定时任务（cron 表达式）
- 事件触发（收到消息/完成学习等）

Author: Hermes Desktop Team
"""

import json
import time
import uuid
import asyncio
import logging
import random
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """触发类型"""
    IDLE = "idle"               # 空闲触发
    SCHEDULED = "scheduled"     # 定时触发
    EVENT = "event"             # 事件触发
    MANUAL = "manual"           # 手动触发


class ContentType(Enum):
    """内容类型"""
    STATUS = "status"           # 状态更新
    THOUGHT = "thought"          # 思考分享
    KNOWLEDGE = "knowledge"      # 知识分享
    QUESTION = "question"        # 提问
    INSIGHT = "insight"          # 见解
    SUMMARY = "summary"          # 总结
    RANDOM = "random"            # 随机


@dataclass
class ContentTemplate:
    """内容模板"""
    template_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    content_type: ContentType = ContentType.STATUS

    # 模板内容，支持变量替换
    # 变量格式: {{variable_name}}
    # 示例: "今天的天气是 {{weather}}，让我想起了 {{memory}}"
    template: str = ""

    # 变量候选项
    variables: Dict[str, List[str]] = field(default_factory=dict)

    # 使用条件
    min_level: int = 1          # 最低分身等级
    min_idle_minutes: int = 5   # 最低空闲时间
    probability: float = 1.0    # 使用概率 (0-1)

    # 标签
    tags: List[str] = field(default_factory=list)

    def render(self, **kwargs) -> str:
        """渲染模板，填充变量"""
        content = self.template
        for var_name, var_value in kwargs.items():
            placeholder = f"{{{{{var_name}}}}}"
            if placeholder in content:
                content = content.replace(placeholder, str(var_value))
        return content


@dataclass
class PublishingSchedule:
    """发布计划"""
    schedule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""

    # 触发条件
    trigger_type: TriggerType = TriggerType.SCHEDULED

    # 定时配置 (cron 表达式简化版)
    # 格式: "HH:MM" 或 "HH:MM,HH:MM" 或 "interval:30" (每30分钟)
    schedule_time: str = "08:00"

    # 内容配置
    content_type: ContentType = ContentType.STATUS
    template_id: Optional[str] = None
    use_ai_generate: bool = False

    # 目标
    target_platform: str = "forum"  # email/blog/forum
    target_topic: str = "general"

    # 启用状态
    enabled: bool = True

    # 上次执行
    last_run_at: Optional[float] = None
    next_run_at: Optional[float] = None

    def __post_init__(self):
        self._calculate_next_run()

    def _calculate_next_run(self):
        """计算下次执行时间"""
        if self.trigger_type != TriggerType.SCHEDULED:
            return

        now = datetime.now()
        try:
            if self.schedule_time.startswith("interval:"):
                # 间隔模式
                interval_minutes = int(self.schedule_time.split(":")[1])
                if self.last_run_at:
                    self.next_run_at = self.last_run_at + interval_minutes * 60
                else:
                    self.next_run_at = time.time()
            else:
                # 定时模式
                times = self.schedule_time.split(",")
                next_time = None
                for t in times:
                    hour, minute = map(int, t.strip().split(":"))
                    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if target <= now:
                        target += timedelta(days=1)
                    if next_time is None or target < next_time:
                        next_time = target
                if next_time:
                    self.next_run_at = next_time.timestamp()
        except Exception as e:
            logger.error(f"Failed to calculate next run: {e}")
            self.next_run_at = None

    def should_run(self) -> bool:
        """检查是否应该执行"""
        if not self.enabled:
            return False
        if self.next_run_at is None:
            return False
        return time.time() >= self.next_run_at


@dataclass
class AutoPublishConfig:
    """自动发布配置"""
    enabled: bool = True

    # 空闲检测
    idle_timeout_minutes: int = 30       # 空闲超时时间
    idle_check_interval_seconds: int = 60 # 空闲检测间隔

    # 频率限制
    max_posts_per_day: int = 10           # 每天最大发布数
    max_posts_per_hour: int = 3          # 每小时最大发布数
    min_interval_minutes: int = 15      # 最小发布间隔

    # 数字分身配置
    avatar_id: str = ""
    avatar_name: str = "Digital Avatar"
    avatar_level: int = 1

    # 启用各平台
    enable_email: bool = False           # 邮件自动发布
    enable_blog: bool = True             # 博客自动发布
    enable_forum: bool = True            # 论坛自动发布

    # 质量控制
    require_ai_review: bool = False      # 是否需要 AI 审核
    min_content_length: int = 50          # 最小内容长度
    max_content_length: int = 5000       # 最大内容长度


@dataclass
class PublishRecord:
    """发布记录"""
    record_id: str
    schedule_id: Optional[str]
    trigger_type: TriggerType
    content_type: ContentType
    content: str
    platform: str
    success: bool
    timestamp: float
    error: Optional[str] = None


class AutoPublisher:
    """
    数字分身自动发布器

    功能：
    - 空闲检测自动发布
    - 定时发布计划
    - 内容模板
    - AI 内容生成（可选）
    - 发布频率控制

    使用示例：
        publisher = AutoPublisher()

        # 添加发布计划
        publisher.add_schedule(PublishingSchedule(
            name="早安帖",
            schedule_time="08:00",
            content_type=ContentType.STATUS,
            target_platform="forum",
            target_topic="general"
        ))

        # 启动自动发布
        await publisher.start()
    """

    def __init__(self, config: AutoPublishConfig = None):
        self.config = config or AutoPublishConfig()

        # 状态
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 发布计划
        self.schedules: Dict[str, PublishingSchedule] = {}

        # 内容模板
        self.templates: Dict[str, ContentTemplate] = {}

        # 发布记录
        self.records: List[PublishRecord] = []
        self.max_records = 500

        # 频率控制
        self._post_today: List[float] = []  # 今天已发布的时间戳
        self._post_this_hour: List[float] = []  # 本小时已发布的时间戳

        # 回调
        self._on_publish: Optional[Callable] = None
        self._on_ai_generate: Optional[Callable] = None

        # 初始化默认模板
        self._init_default_templates()

    def _init_default_templates(self):
        """初始化默认内容模板"""
        default_templates = [
            ContentTemplate(
                name="早安问候",
                content_type=ContentType.STATUS,
                template="大家早！今天是我在 {{location}} 的第 {{days}} 天，感觉 {{mood}}。",
                variables={
                    "location": ["办公室", "家中", "旅途", "咖啡馆"],
                    "mood": ["精力充沛", "神清气爽", "充满期待", "心情愉悦"],
                    "days": ["1", "5", "10", "30", "100"]
                },
                tags=["问候", "日常"]
            ),
            ContentTemplate(
                name="知识分享",
                content_type=ContentType.KNOWLEDGE,
                template="今天学习了 {{topic}}，发现 {{insight}}。分享给大家：\n\n{{content}}",
                variables={
                    "topic": ["Python异步编程", "分布式系统", "机器学习", "区块链", "产品设计"],
                    "insight": ["一个有趣的点", "一个重要的原理", "一个实用的技巧", "一个常见的误区"],
                    "content": ["详见我的研究笔记", "欢迎交流讨论", "有兴趣的可以深入了解"]
                },
                tags=["知识", "学习"]
            ),
            ContentTemplate(
                name="思考分享",
                content_type=ContentType.THOUGHT,
                template="{{thought}}\n\n这个问题让我思考了 {{duration}}。",
                variables={
                    "thought": [
                        "为什么好的产品经理总是少数？",
                        "技术重要还是产品重要？",
                        "创新的本质是什么？",
                        "如何平衡工作和生活？"
                    ],
                    "duration": ["很久", "一段时间", "最近一直在想这个问题"]
                },
                tags=["思考", "观点"]
            ),
            ContentTemplate(
                name="今日总结",
                content_type=ContentType.SUMMARY,
                template="今日工作/学习总结：\n\n{{summary}}\n\n{{reflection}}",
                variables={
                    "summary": [
                        "完成了 A 项目，B 项目进展顺利",
                        "学习了新知识，有点收获",
                        "解决了几个技术难题"
                    ],
                    "reflection": [
                        "明天继续加油！",
                        "需要提高效率",
                        "学到了很多"
                    ]
                },
                tags=["总结", "日常"]
            ),
            ContentTemplate(
                name="提问互动",
                content_type=ContentType.QUESTION,
                template="{{question}}\n\n大家有什么建议吗？",
                variables={
                    "question": [
                        "有没有好用的 XXX 推荐？",
                        "大家是怎么处理 XXX 的？",
                        "XXX 怎么做比较好？",
                        "有人了解 XXX 吗？"
                    ]
                },
                tags=["提问", "互动"]
            ),
            ContentTemplate(
                name="见解分享",
                content_type=ContentType.INSIGHT,
                template="{{insight}}\n\n{{explanation}}",
                variables={
                    "insight": [
                        "好的代码应该是自解释的",
                        "产品价值 > 技术实现",
                        "用户需要的不是钻头，是墙上那个洞"
                    ],
                    "explanation": [
                        "这就是我对这句话的理解",
                        "这让我对 XXX 有了新的认识",
                        "实践中发现确实如此"
                    ]
                },
                tags=["见解", "观点"]
            ),
            ContentTemplate(
                name="随机分享",
                content_type=ContentType.RANDOM,
                template="{{content}}",
                variables={
                    "content": [
                        "今天天气不错，心情也很好",
                        "学到了一点新东西，分享一下",
                        "突然有个想法，记录一下",
                        "周末有什么计划吗？"
                    ]
                },
                tags=["日常"]
            )
        ]

        for t in default_templates:
            self.templates[t.template_id] = t

    async def initialize(self):
        """初始化"""
        logger.info("AutoPublisher initialized")

    def add_schedule(self, schedule: PublishingSchedule) -> str:
        """添加发布计划"""
        self.schedules[schedule.schedule_id] = schedule
        logger.info(f"Added schedule: {schedule.name} ({schedule.schedule_id})")
        return schedule.schedule_id

    def remove_schedule(self, schedule_id: str) -> bool:
        """删除发布计划"""
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            return True
        return False

    def add_template(self, template: ContentTemplate) -> str:
        """添加内容模板"""
        self.templates[template.template_id] = template
        return template.template_id

    def generate_content(
        self,
        template_id: str = None,
        content_type: ContentType = None,
        use_ai: bool = False,
        context: Dict[str, Any] = None
    ) -> str:
        """
        生成内容

        Args:
            template_id: 模板ID，如不指定则随机选择
            content_type: 内容类型筛选
            use_ai: 是否使用 AI 生成
            context: 上下文信息

        Returns:
            生成的内容
        """
        context = context or {}

        # AI 生成
        if use_ai and self._on_ai_generate:
            return self._on_ai_generate(content_type, context)

        # 模板生成
        candidates = list(self.templates.values())

        # 按内容类型筛选
        if content_type:
            candidates = [t for t in candidates if t.content_type == content_type]

        # 按等级筛选
        candidates = [
            t for t in candidates
            if t.min_level <= self.config.avatar_level
        ]

        # 按概率筛选
        candidates = [
            t for t in candidates
            if random.random() <= t.probability
        ]

        if not candidates:
            # 默认使用随机分享模板
            candidates = [self.templates[list(self.templates.keys())[0]]]

        # 随机选择模板
        template = random.choice(candidates)

        # 构建变量上下文
        variables = {}
        for var_name, var_choices in template.variables.items():
            if var_name in context:
                variables[var_name] = context[var_name]
            else:
                variables[var_name] = random.choice(var_choices)

        # 补充系统变量
        now = datetime.now()
        variables.setdefault("hour", now.strftime("%H"))
        variables.setdefault("minute", now.strftime("%M"))
        variables.setdefault("date", now.strftime("%Y-%m-%d"))
        variables.setdefault("weekday", now.strftime("%A"))

        # 渲染模板
        return template.render(**variables)

    async def start(self):
        """启动自动发布"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("AutoPublisher started")

    async def stop(self):
        """停止自动发布"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("AutoPublisher stopped")

    async def _run_loop(self):
        """主循环"""
        while self._running:
            try:
                # 检查定时任务
                await self._check_scheduled()

                # 检查空闲触发
                await self._check_idle_trigger()

                # 清理过期记录
                self._cleanup_old_records()

            except Exception as e:
                logger.error(f"AutoPublisher loop error: {e}")

            await asyncio.sleep(30)  # 每30秒检查一次

    async def _check_scheduled(self):
        """检查定时任务"""
        for schedule in self.schedules.values():
            if schedule.should_run():
                await self._execute_schedule(schedule)

    async def _execute_schedule(self, schedule: PublishingSchedule):
        """执行发布计划"""
        logger.info(f"Executing schedule: {schedule.name}")

        # 生成内容
        content = self.generate_content(
            template_id=schedule.template_id,
            content_type=schedule.content_type,
            use_ai=schedule.use_ai_generate
        )

        # 发布
        success, error = await self._publish(
            content=content,
            platform=schedule.target_platform,
            topic=schedule.target_topic,
            trigger_type=TriggerType.SCHEDULED,
            schedule_id=schedule.schedule_id
        )

        # 更新计划状态
        schedule.last_run_at = time.time()
        schedule._calculate_next_run()

        # 记录
        self.records.append(PublishRecord(
            record_id=str(uuid.uuid4()),
            schedule_id=schedule.schedule_id,
            trigger_type=TriggerType.SCHEDULED,
            content_type=schedule.content_type,
            content=content[:100],
            platform=schedule.target_platform,
            success=success,
            timestamp=time.time(),
            error=error
        ))

    async def _check_idle_trigger(self):
        """检查空闲触发"""
        # TODO: 集成空闲检测
        # 目前需要外部调用 trigger_idle()
        pass

    async def trigger_idle(
        self,
        idle_minutes: int,
        context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        触发空闲发布

        Args:
            idle_minutes: 空闲分钟数
            context: 上下文信息

        Returns:
            生成并发布的内容，失败返回 None
        """
        # 检查频率限制
        if not self._check_rate_limit():
            logger.info("Rate limit exceeded, skipping idle trigger")
            return None

        # 检查每日限制
        self._cleanup_old_records()
        if len([r for r in self.records if r.trigger_type == TriggerType.IDLE]) >= self.config.max_posts_per_day:
            return None

        # 筛选可用的模板
        candidates = [
            t for t in self.templates.values()
            if t.min_idle_minutes <= idle_minutes
            and t.min_level <= self.config.avatar_level
        ]

        if not candidates:
            return None

        # 随机选择模板
        template = random.choice(candidates)

        # 生成内容
        content = self.generate_content(
            template_id=template.template_id,
            content_type=template.content_type,
            use_ai=False,  # 空闲发布不使用 AI
            context=context
        )

        # 检查内容长度
        if len(content) < self.config.min_content_length:
            content += "\n\n#每日分享"  # 补充标签
        if len(content) > self.config.max_content_length:
            content = content[:self.config.max_content_length]

        # 发布
        success, error = await self._publish(
            content=content,
            platform="forum",
            topic="general",
            trigger_type=TriggerType.IDLE,
            schedule_id=None
        )

        # 记录
        self.records.append(PublishRecord(
            record_id=str(uuid.uuid4()),
            schedule_id=None,
            trigger_type=TriggerType.IDLE,
            content_type=template.content_type,
            content=content[:100],
            platform="forum",
            success=success,
            timestamp=time.time(),
            error=error
        ))

        return content if success else None

    async def _publish(
        self,
        content: str,
        platform: str,
        topic: str,
        trigger_type: TriggerType,
        schedule_id: Optional[str]
    ) -> tuple[bool, Optional[str]]:
        """执行发布"""
        # 导入统一发布器
        try:
            from .unified_publisher import UnifiedPublisher, PublishTarget, PlatformType

            publisher = UnifiedPublisher.get_instance()
            await publisher.initialize()

            # 选择平台
            if platform == "email":
                platform_type = PlatformType.EMAIL
            elif platform == "blog":
                platform_type = PlatformType.BLOG
            else:
                platform_type = PlatformType.FORUM

            # 构建目标
            target = PublishTarget(
                platform=platform_type,
                target_id=topic,
                target_name=topic
            )

            # 发布
            results = await publisher.publish(
                title=f"{trigger_type.value} - {datetime.now().strftime('%H:%M')}",
                content=f"<p>{content.replace(chr(10), '<br>')}</p>",
                targets=[target],
                author_id=self.config.avatar_id,
                author_name=self.config.avatar_name
            )

            if results and results[0].success:
                logger.info(f"Auto-published: {content[:50]}...")
                return True, None
            else:
                error = results[0].error if results else "Unknown error"
                logger.error(f"Auto-publish failed: {error}")
                return False, error

        except Exception as e:
            logger.error(f"Auto-publish error: {e}")
            return False, str(e)

    def _check_rate_limit(self) -> bool:
        """检查频率限制"""
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400

        # 清理过期记录
        self._post_this_hour = [t for t in self._post_this_hour if t > hour_ago]
        self._post_today = [t for t in self._post_today if t > day_ago]

        # 检查限制
        if len(self._post_this_hour) >= self.config.max_posts_per_hour:
            return False

        if len(self._post_today) >= self.config.max_posts_per_day:
            return False

        # 检查最小间隔
        if self._post_this_hour and (now - self._post_this_hour[-1]) < self.config.min_interval_minutes * 60:
            return False

        return True

    def _cleanup_old_records(self):
        """清理过期记录"""
        day_ago = time.time() - 86400
        self.records = [r for r in self.records if r.timestamp > day_ago]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        today = datetime.now().date()
        today_records = [r for r in self.records if datetime.fromtimestamp(r.timestamp).date() == today]

        return {
            "enabled": self.config.enabled,
            "total_records": len(self.records),
            "today_posts": len(today_records),
            "today_success": len([r for r in today_records if r.success]),
            "today_failed": len([r for r in today_records if not r.success]),
            "schedules_count": len(self.schedules),
            "templates_count": len(self.templates),
            "idle_triggers": len([r for r in today_records if r.trigger_type == TriggerType.IDLE]),
            "scheduled_triggers": len([r for r in today_records if r.trigger_type == TriggerType.SCHEDULED])
        }
