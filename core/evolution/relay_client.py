# relay_client.py — 中继服务器客户端

import json
import re
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import urllib.request
import urllib.error

from .models import (
    WeeklyReport, ClientConfig, ReportStatus,
)

# 导入统一配置
try:
    from core.config.unified_config import UnifiedConfig
    _config = UnifiedConfig.get_instance()
except ImportError:
    _config = None


def _get_max_retries(category: str = "http") -> int:
    """安全获取重试次数"""
    if _config:
        return _config.get_max_retries(category)
    return 3


class RelayClient:
    """
    中继服务器客户端

    功能：
    1. 上报周报数据
    2. 拉取安全规则
    3. 拉取进化趋势
    4. 心跳保活
    """

    DEFAULT_SERVER_URL = "http://localhost:8766"
    DEFAULT_TIMEOUT = 10  # 秒
    # MAX_RETRIES = 3  # 已迁移到统一配置 (使用 _get_max_retries())

    def __init__(
        self,
        server_url: str = None,
        config: ClientConfig = None,
    ):
        """
        初始化中继客户端

        Args:
            server_url: 服务器地址
            config: 客户端配置
        """
        self._server_url = server_url or self.DEFAULT_SERVER_URL
        self._config = config or ClientConfig()
        self._logger = logging.getLogger(__name__)

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Dict[str, Any] = None,
        timeout: int = None,
    ) -> Optional[Dict[str, Any]]:
        """
        发送HTTP请求

        Args:
            endpoint: API端点
            method: HTTP方法
            data: 请求数据
            timeout: 超时时间

        Returns:
            Dict: 响应数据
        """
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

        url = f"{self._server_url}{endpoint}"

        for retry in range(_get_max_retries("http")):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "LivingTree-Evolution/2.0",
                }

                if self._config.token:
                    headers["Authorization"] = f"Bearer {self._config.token}"

                if data is not None:
                    body = json.dumps(data).encode("utf-8")
                    req = urllib.request.Request(
                        url, data=body, headers=headers, method=method
                    )
                else:
                    req = urllib.request.Request(url, headers=headers, method=method)

                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    response_data = resp.read().decode("utf-8")
                    if response_data:
                        return json.loads(response_data)
                    return {"success": True}

            except urllib.error.URLError as e:
                self._logger.warning(f"请求失败 (retry {retry+1}): {e}")
                if retry < _get_max_retries("http") - 1:
                    time.sleep(1 * (retry + 1))  # 指数退避
                else:
                    return None

            except json.JSONDecodeError as e:
                self._logger.warning(f"JSON解析失败: {e}")
                return None

            except Exception as e:
                self._logger.error(f"未知错误: {e}")
                return None

        return None

    def upload_report(self, report: WeeklyReport) -> bool:
        """
        上报周报

        Args:
            report: 周报数据

        Returns:
            bool: 是否成功
        """
        endpoint = "/api/collect"

        payload = {
            "week_id": report.week_id,
            "client_id": report.client_id,
            "patches": [p.to_dict() for p in report.patches],
            "pain_points": [p.to_dict() for p in report.pain_points],
            "generated_at": report.generated_at,
            "client_version": report.client_version,
            "platform": report.platform,
        }

        result = self._make_request(endpoint, method="POST", data=payload)

        if result and result.get("success"):
            return True

        self._logger.warning(f"周报上传失败: {result}")
        return False

    def upload_reports_batch(self, reports: List[WeeklyReport]) -> Dict[str, bool]:
        """
        批量上传周报

        Args:
            reports: 周报列表

        Returns:
            Dict[str, bool]: week_id -> 是否成功
        """
        results = {}

        for report in reports:
            success = self.upload_report(report)
            results[report.week_id] = success

            # 上报间隔
            if success:
                time.sleep(0.5)

        return results

    def fetch_safety_rules(self) -> Optional[List[Dict[str, Any]]]:
        """
        拉取安全规则

        Returns:
            List[Dict]: 安全规则列表
        """
        endpoint = "/api/safety/rules"

        result = self._make_request(endpoint, method="GET")

        if result and "rules" in result:
            return result["rules"]

        return None

    def fetch_trends(self, weeks: int = 4) -> Optional[Dict[str, Any]]:
        """
        拉取进化趋势

        Args:
            weeks: 拉取周数

        Returns:
            Dict: 趋势数据
        """
        endpoint = f"/api/trends?weeks={weeks}"

        result = self._make_request(endpoint, method="GET")

        if result:
            return result

        return None

    def fetch_recommended_patches(self) -> Optional[List[Dict[str, Any]]]:
        """
        拉取推荐补丁

        Returns:
            List[Dict]: 推荐补丁列表
        """
        endpoint = "/api/patches/recommended"

        result = self._make_request(endpoint, method="GET")

        if result and "patches" in result:
            return result["patches"]

        return None

    def heartbeat(self) -> bool:
        """
        发送心跳

        Returns:
            bool: 是否成功
        """
        endpoint = "/api/heartbeat"

        payload = {
            "client_id": self._config.client_id,
            "timestamp": int(time.time()),
            "platform": "windows",
        }

        result = self._make_request(endpoint, method="POST", data=payload)

        return result is not None

    def check_server_health(self) -> bool:
        """
        检查服务器健康状态

        Returns:
            bool: 是否健康
        """
        endpoint = "/api/health"

        result = self._make_request(endpoint, method="GET")

        return result is not None

    def get_server_url(self) -> str:
        """获取服务器URL"""
        return self._server_url

    def set_server_url(self, url: str):
        """设置服务器URL"""
        self._server_url = url


# 全局单例
_relay_client_instance: Optional[RelayClient] = None


def get_relay_client(server_url: str = None) -> RelayClient:
    """获取中继客户端全局实例"""
    global _relay_client_instance
    if _relay_client_instance is None:
        _relay_client_instance = RelayClient(server_url=server_url)
    return _relay_client_instance


# ============ 终极版新增：Bot 发帖与回流 ============

from .models import (
    ForumPost, ExternalPlatform, ExternalPost, Reply回流,
    BotConfig,
)


class BotPostingService:
    """
    Bot 发帖服务

    功能：
    1. 拟人化内容生成
    2. Safety 检查
    3. 通过中继服务器发帖
    4. 频率限制
    """

    # 拟人化关键词替换
    HUMANIZE_PATTERNS = [
        # 语气词
        (r"\bAI\b", ""),
        (r"\b人工智能\b", ""),
        (r"\b模型\b", ""),
        (r"\bLLM\b", ""),
        # 开头语气
        (r"^作为一个AI，", ""),
        (r"^AI助手", "我"),
        (r"^根据我的了解，", ""),
        (r"^一般来说，", ""),
        # 结尾免责声明
        (r"\b如有需要请咨询专业人员\b", ""),
        (r"\b以上内容仅供参考\b", ""),
    ]

    # 真人常用开头
    HUMANIZE_STARTS = [
        "请教大家一个问题",
        "卡在这儿了，求助",
        "刚折腾完，分享一下经验",
        "新人报道，问个问题",
        "试了一圈，总结一下",
    ]

    def __init__(self, relay_client: RelayClient = None):
        self._relay = relay_client or get_relay_client()
        self._last_post_time: Dict[ExternalPlatform, int] = {}

    def humanize_content(self, content: str) -> str:
        """
        拟人化内容（去AI痕迹）

        Args:
            content: 原始内容

        Returns:
            str: 拟人化后的内容
        """
        result = content

        # 应用替换模式
        for pattern, replacement in self.HUMANIZE_PATTERNS:
            result = re.sub(pattern, replacement, result)

        # 清理多余空格
        result = re.sub(r"\s+", " ", result).strip()

        # 如果开头不像真人，随机加一个
        starts_with_human = any(result.startswith(s) for s in self.HUMANIZE_STARTS)
        if not starts_with_human and not result.startswith(("请问", "请教", "求助", "问个", "刚", "试了")):
            import random
            prefix = random.choice(self.HUMANIZE_STARTS) + "，"
            result = prefix + result

        return result

    def check_safety(self, content: str) -> tuple[bool, float]:
        """
        Safety 检查

        Args:
            content: 内容

        Returns:
            tuple: (是否通过, 安全评分 0-1)
        """
        # 敏感词检测
        sensitive_keywords = [
            "赌博", "色情", "暴力", "政治", "诈骗",
            "gambling", "porn", "violence", "fraud",
        ]

        score = 1.0
        for keyword in sensitive_keywords:
            if keyword in content.lower():
                score -= 0.5

        return score >= 0.5, score

    def post_to_external(
        self,
        post: ForumPost,
        platform: ExternalPlatform,
        attribution_id: str,
    ) -> Optional[ExternalPost]:
        """
        发帖到外部平台

        Args:
            post: 论坛帖子
            platform: 目标平台
            attribution_id: 归因ID

        Returns:
            ExternalPost: 发帖记录
        """
        # 频率限制检查
        if not self._check_rate_limit(platform):
            return None

        # 拟人化
        humanized = self.humanize_content(post.content)

        # Safety 检查
        passed, safety_score = self.check_safety(humanized)
        if not passed:
            external_post = ExternalPost(
                id=post.id,
                attribution_id=attribution_id,
                original_content=post.content,
                humanized_content=humanized,
                platform=platform,
                status="safety_rejected",
                safety_score=safety_score,
            )
            return external_post

        # 通过中继发帖
        payload = {
            "post_id": post.id,
            "attribution_id": attribution_id,
            "content": humanized,
            "platform": platform.value,
            "title": post.title,
        }

        result = self._relay._make_request(
            "/api/bot/post",
            method="POST",
            data=payload,
        )

        if result and result.get("success"):
            self._last_post_time[platform] = int(time.time())
            return ExternalPost(
                id=post.id,
                attribution_id=attribution_id,
                original_content=post.content,
                humanized_content=humanized,
                platform=platform,
                status="success",
                external_url=result.get("url"),
                posted_at=int(time.time()),
                safety_score=safety_score,
            )
        else:
            return ExternalPost(
                id=post.id,
                attribution_id=attribution_id,
                original_content=post.content,
                humanized_content=humanized,
                platform=platform,
                status="failed",
                error_message=result.get("error") if result else "Network error",
                safety_score=safety_score,
            )

    def _check_rate_limit(self, platform: ExternalPlatform) -> bool:
        """
        检查频率限制

        Args:
            platform: 平台

        Returns:
            bool: 是否允许发帖
        """
        # 每小时最多1帖
        MAX_PER_HOUR = 1

        last_time = self._last_post_time.get(platform, 0)
        elapsed = time.time() - last_time

        return elapsed >= 3600  # 至少1小时

    def fetch_external_replies(
        self,
        external_post_id: str,
    ) -> List[Reply回流]:
        """
        获取外部帖子回复

        Args:
            external_post_id: 外部帖子ID

        Returns:
            List[Reply回流]: 回复列表
        """
        result = self._relay._make_request(
            f"/api/bot/replies/{external_post_id}",
            method="GET",
        )

        if not result or "replies" not in result:
            return []

        replies = []
        for item in result["replies"]:
            reply = Reply回流(
                id=item["id"],
                external_post_id=external_post_id,
                platform=ExternalPlatform(item["platform"]),
                author=item["author"],
                content=item["content"],
                timestamp=item["timestamp"],
            )
            replies.append(reply)

        return replies


# 全局单例
_bot_posting_instance: Optional[BotPostingService] = None


def get_bot_posting_service() -> BotPostingService:
    """获取Bot发帖服务全局实例"""
    global _bot_posting_instance
    if _bot_posting_instance is None:
        _bot_posting_instance = BotPostingService()
    return _bot_posting_instance
