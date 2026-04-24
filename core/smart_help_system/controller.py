"""
Smart Help Controller - 智能求助控制器

协调整个求助流程：
1. 问题输入
2. 脱敏处理
3. 平台选择
4. 提问生成
5. 发布监控
6. 答案整合
7. 结果反馈
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

from .question_sanitizer import QuestionSanitizer, SanitizedQuestion
from .platform_selector import PlatformSelector, Platform, QuestionType, SelectionResult
from .question_generator import QuestionGenerator, GeneratedPost
from .answer_monitor import AnswerMonitor, MonitoredPost, MonitoringConfig, Answer
from .answer_aggregator import AnswerAggregator, AggregatedAnswer


class HelpStatus(Enum):
    """求助状态"""
    IDLE = "idle"                       # 空闲
    ANALYZING = "analyzing"             # 分析中
    SANITIZING = "sanitizing"           # 脱敏中
    SELECTING_PLATFORM = "selecting"    # 选择平台
    GENERATING = "generating"           # 生成提问
    PUBLISHING = "publishing"          # 发布中
    MONITORING = "monitoring"           # 监控中
    AGGREGATING = "aggregating"         # 整合中
    COMPLETED = "completed"             # 完成
    FAILED = "failed"                   # 失败


@dataclass
class HelpRequest:
    """求助请求"""
    request_id: str
    original_question: str
    context: Dict[str, Any]              # 额外上下文
    status: HelpStatus = HelpStatus.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 各阶段结果
    sanitized_question: Optional[SanitizedQuestion] = None
    platform_selection: Optional[SelectionResult] = None
    generated_post: Optional[GeneratedPost] = None
    monitored_posts: List[MonitoredPost] = field(default_factory=list)
    aggregated_answer: Optional[AggregatedAnswer] = None

    # 错误信息
    error_message: Optional[str] = None


class SmartHelpController:
    """
    智能求助控制器

    提供一键式求助体验：
    1. 用户输入问题
    2. 自动完成脱敏、平台选择、生成提问
    3. 发布到选定平台
    4. 监控回答
    5. 整合答案并反馈给用户
    """

    # 状态 -> 描述
    STATUS_DESCRIPTIONS = {
        HelpStatus.IDLE: "就绪",
        HelpStatus.ANALYZING: "正在分析问题...",
        HelpStatus.SANITIZING: "正在脱敏处理...",
        HelpStatus.SELECTING_PLATFORM: "正在选择最佳平台...",
        HelpStatus.GENERATING: "正在生成提问内容...",
        HelpStatus.PUBLISHING: "正在发布到平台...",
        HelpStatus.MONITORING: "正在监控回答...",
        HelpStatus.AGGREGATING: "正在整合答案...",
        HelpStatus.COMPLETED: "完成",
        HelpStatus.FAILED: "失败",
    }

    def __init__(self):
        # 初始化各组件
        self.sanitizer = QuestionSanitizer()
        self.platform_selector = PlatformSelector()
        self.question_generator = QuestionGenerator()
        self.answer_monitor = AnswerMonitor()
        self.answer_aggregator = AnswerAggregator()

        # 求助请求记录
        self._requests: Dict[str, HelpRequest] = {}

        # 回调函数
        self._status_callbacks: List[Callable] = []
        self._answer_callbacks: List[Callable] = []

        # 注册答案回调
        self.answer_monitor.register_callback(self._on_new_answer)

    def create_help_request(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> HelpRequest:
        """
        创建求助请求

        Args:
            question: 用户问题
            context: 额外上下文（错误信息、代码、环境等）

        Returns:
            HelpRequest: 求助请求
        """
        import hashlib
        request_id = hashlib.md5(
            f"{question}_{time.time()}".encode()
        ).hexdigest()[:12]

        request = HelpRequest(
            request_id=request_id,
            original_question=question,
            context=context or {}
        )

        self._requests[request_id] = request
        return request

    def execute_help_request(
        self,
        request: HelpRequest,
        auto_publish: bool = True,
        publish_platforms: Optional[List[Platform]] = None
    ) -> HelpRequest:
        """
        执行求助请求

        Args:
            request: 求助请求
            auto_publish: 是否自动发布到平台
            publish_platforms: 指定发布的平台（None表示使用自动选择的平台）

        Returns:
            HelpRequest: 更新后的请求
        """
        try:
            # 阶段1: 分析问题
            request.status = HelpStatus.ANALYZING
            self._notify_status_change(request)

            # 阶段2: 脱敏处理
            request.status = HelpStatus.SANITIZING
            self._notify_status_change(request)

            request.sanitized_question = self.sanitizer.sanitize(
                request.original_question
            )

            # 阶段3: 平台选择
            request.status = HelpStatus.SELECTING_PLATFORM
            self._notify_status_change(request)

            platforms = publish_platforms or []
            request.platform_selection = self.platform_selector.select(
                question=request.original_question,
                preferred_language=context.get('language', 'auto'),
                preferred_platforms=platforms if platforms else None
            )

            # 阶段4: 生成提问
            request.status = HelpStatus.GENERATING
            self._notify_status_change(request)

            context_for_generation = {
                'error_message': request.context.get('error_message', ''),
                'code': request.context.get('code', ''),
                'os': request.context.get('os', 'Windows 11'),
                'language': request.context.get('language', 'Python'),
                'framework': request.context.get('framework', ''),
            }

            request.generated_post = self.question_generator.generate(
                sanitized_question=request.sanitized_question,
                platform=request.platform_selection.primary_platform,
                question_type=request.platform_selection.question_type,
                context=context_for_generation
            )

            # 阶段5: 发布
            if auto_publish:
                request.status = HelpStatus.PUBLISHING
                self._notify_status_change(request)

                # 发布到主平台
                post = self.answer_monitor.publish_post(
                    platform=request.platform_selection.primary_platform,
                    title=request.generated_post.title,
                    body=request.generated_post.body,
                    tags=request.generated_post.tags,
                    github_repo=request.context.get('github_repo')
                )
                request.monitored_posts.append(post)

                # 可选：发布到备选平台
                for alt_platform in request.platform_selection.alternative_platforms[:2]:
                    alt_post = self.answer_monitor.publish_post(
                        platform=alt_platform,
                        title=request.generated_post.title,
                        body=request.generated_post.body,
                        tags=request.generated_post.tags
                    )
                    request.monitored_posts.append(alt_post)

            # 阶段6: 整合答案（如果已有回答）
            request.status = HelpStatus.AGGREGATING
            self._notify_status_change(request)

            if request.monitored_posts:
                request.aggregated_answer = self.answer_aggregator.aggregate(
                    posts=request.monitored_posts,
                    original_question=request.original_question
                )

            request.status = HelpStatus.COMPLETED

        except Exception as e:
            request.status = HelpStatus.FAILED
            request.error_message = str(e)

        request.updated_at = datetime.now()
        self._notify_status_change(request)

        return request

    def get_request_status(self, request_id: str) -> Optional[HelpRequest]:
        """获取请求状态"""
        return self._requests.get(request_id)

    def refresh_answers(self, request_id: str) -> Optional[AggregatedAnswer]:
        """
        刷新答案（重新整合）

        Args:
            request_id: 请求ID

        Returns:
            整合后的答案
        """
        request = self._requests.get(request_id)
        if not request:
            return None

        # 重新整合
        request.aggregated_answer = self.answer_aggregator.aggregate(
            posts=request.monitored_posts,
            original_question=request.original_question
        )

        return request.aggregated_answer

    def get_user_report(self, request_id: str) -> Optional[str]:
        """获取用户友好的报告"""
        request = self._requests.get(request_id)
        if not request or not request.aggregated_answer:
            return None

        return self.answer_aggregator.generate_user_friendly_report(
            aggregated=request.aggregated_answer,
            original_question=request.original_question
        )

    def stop_monitoring(self, request_id: str) -> bool:
        """停止监控"""
        request = self._requests.get(request_id)
        if not request:
            return False

        for post in request.monitored_posts:
            self.answer_monitor.stop_monitoring(post.post_id)

        return True

    def register_status_callback(
        self,
        callback: Callable[[HelpRequest], None]
    ):
        """注册状态变更回调"""
        self._status_callbacks.append(callback)

    def register_answer_callback(
        self,
        callback: Callable[[HelpRequest, Answer], None]
    ):
        """注册新回答回调"""
        self._answer_callbacks.append(callback)

    def _notify_status_change(self, request: HelpRequest):
        """通知状态变更"""
        for callback in self._status_callbacks:
            try:
                callback(request)
            except Exception as e:
                logger.info(f"Status callback error: {e}")

    def _on_new_answer(self, post: MonitoredPost, answer: Answer):
        """新回答回调"""
        # 找到对应的请求
        for request in self._requests.values():
            if post in request.monitored_posts:
                # 通知
                for callback in self._answer_callbacks:
                    try:
                        callback(request, answer)
                    except Exception as e:
                        logger.info(f"Answer callback error: {e}")
                break

    def get_all_requests(self) -> List[HelpRequest]:
        """获取所有请求"""
        return list(self._requests.values())

    def get_active_requests(self) -> List[HelpRequest]:
        """获取活跃请求"""
        return [
            r for r in self._requests.values()
            if r.status in {
                HelpStatus.ANALYZING,
                HelpStatus.SANITIZING,
                HelpStatus.SELECTING_PLATFORM,
                HelpStatus.GENERATING,
                HelpStatus.PUBLISHING,
                HelpStatus.MONITORING,
            }
        ]

    def get_completed_requests(self) -> List[HelpRequest]:
        """获取已完成的请求"""
        return [
            r for r in self._requests.values()
            if r.status == HelpStatus.COMPLETED
        ]

    def get_status_description(self, status: HelpStatus) -> str:
        """获取状态描述"""
        return self.STATUS_DESCRIPTIONS.get(status, "未知状态")

    # ========== 便捷方法 ==========

    def quick_help(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        快速求助（一站式）

        直接执行完整流程并返回结果报告

        Args:
            question: 问题
            context: 上下文

        Returns:
            结果报告
        """
        # 创建请求
        request = self.create_help_request(question, context)

        # 执行
        request = self.execute_help_request(request)

        # 如果已完成，返回报告
        if request.status == HelpStatus.COMPLETED and request.aggregated_answer:
            return self.answer_aggregator.generate_user_friendly_report(
                aggregated=request.aggregated_answer,
                original_question=question
            )
        elif request.error_message:
            return f"求助失败: {request.error_message}"
        else:
            return f"请求已提交，ID: {request.request_id}，状态: {request.status.value}"

    def preview_post(
        self,
        question: str,
        platform: Platform,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[GeneratedPost]:
        """
        预览生成的帖子

        Args:
            question: 问题
            platform: 平台
            context: 上下文

        Returns:
            生成的帖子（未发布）
        """
        # 脱敏
        sanitized = self.sanitizer.sanitize(question)

        # 选择平台
        selection = self.platform_selector.select(
            question=question,
            preferred_platforms=[platform]
        )

        # 生成
        return self.question_generator.generate(
            sanitized_question=sanitized,
            platform=platform,
            question_type=selection.question_type,
            context=context or {}
        )


# 辅助导入
import time
from core.logger import get_logger
logger = get_logger('smart_help_system.controller')

