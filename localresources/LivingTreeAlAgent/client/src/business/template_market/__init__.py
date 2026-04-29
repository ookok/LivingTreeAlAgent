"""
模板市场系统 - 核心模块 v2.0

功能：
1. UI窗口捕获与模板提取
2. 模板上传、下载、预览、编辑
3. 民主投票撤回机制（改进版）
4. 版本管理与更新确认
5. 窗口上下文调用
"""

import json
import uuid
import hashlib
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path
import threading
import asyncio


# ============ 枚举定义 ============

class VoteType(Enum):
    """投票类型"""
    DELETE = "delete"                    # 删除模板
    WITHDRAW_UPDATE = "withdraw_update"  # 撤回更新
    REPORT = "report"                    # 举报


class VoteStatus(Enum):
    """投票状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TemplateStatus(Enum):
    """模板状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    UPDATE_AVAILABLE = "update_available"
    WITHDRAWN = "withdrawn"
    DELETED = "deleted"


class VoteStrategy(Enum):
    """投票策略"""
    # 无应用的模板：10票即通过
    NO_APPLICATION = "no_application"  # threshold = 10
    # 有应用的模板：2/3多数
    WITH_APPLICATION = "with_application"  # threshold = 2/3


# ============ 数据模型 ============

@dataclass
class WindowCapture:
    """窗口捕获信息"""
    window_handle: int
    title: str
    class_name: str
    rect: dict  # {"x", "y", "width", "height"}
    process_id: int
    process_name: str
    screenshot_path: Optional[str] = None
    ui_tree: Optional[dict] = None  # UI元素树
    context_hints: Optional[dict] = None  # 窗口上下文提示


@dataclass
class UITemplate:
    """UI模板"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)

    # 作者信息
    author_id: str = ""
    author_name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 版本信息
    version: str = "1.0.0"
    parent_id: Optional[str] = None  # 原始模板ID（如果是fork）

    # 内容
    ui_tree: dict = field(default_factory=dict)
    styles: dict = field(default_factory=dict)
    layouts: dict = field(default_factory=dict)
    assets: List[str] = field(default_factory=list)

    # 状态
    status: str = TemplateStatus.PUBLISHED.value
    download_count: int = 0
    use_count: int = 0  # 使用次数（应用次数）
    rating: float = 0.0
    rating_count: int = 0

    # 窗口上下文（用于自动匹配）
    window_context: Optional[dict] = None  # {"class_name", "process_name", "title_pattern"}

    # 变更检测
    source_window: Optional[str] = None
    content_hash: str = ""

    # 元数据
    metadata: dict = field(default_factory=dict)

    def compute_hash(self) -> str:
        """计算内容哈希"""
        content = json.dumps({
            "ui_tree": self.ui_tree,
            "styles": self.styles,
            "layouts": self.layouts
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def has_applications(self) -> bool:
        """是否有应用（被使用/下载）"""
        return self.download_count > 0 or self.use_count > 0


@dataclass
class Vote:
    """投票记录"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vote_type: str = VoteType.DELETE.value
    target_id: str = ""

    # 投票策略
    strategy: str = VoteStrategy.NO_APPLICATION.value
    threshold: int = 10  # 动态阈值

    # 发起人
    initiator_id: str = ""
    initiator_name: str = ""

    # 投票内容
    reason: str = ""
    evidence: Optional[dict] = None

    # 投票状态
    status: str = VoteStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""
    processed_at: Optional[str] = None
    processed_by: Optional[str] = None

    # 票数统计
    upvotes: List[str] = field(default_factory=list)
    downvotes: List[str] = field(default_factory=list)
    abstain: List[str] = field(default_factory=list)

    # 结果
    result_reason: str = ""
    final_score: int = 0

    def get_vote_strategy(self) -> str:
        """获取投票策略"""
        if self.strategy:
            return self.strategy
        return VoteStrategy.NO_APPLICATION.value

    def get_threshold(self, template: UITemplate = None) -> int:
        """获取投票阈值"""
        if template:
            if not template.has_applications():
                return 10  # 无应用：10票
            else:
                return -1  # 有应用：2/3多数（-1表示百分比）
        return self.threshold

    def check_resolution(self) -> bool:
        """检查是否达成决议"""
        total_votes = len(self.upvotes) + len(self.downvotes)
        if total_votes == 0:
            return False

        upvotes = len(self.upvotes)
        downvotes = len(self.downvotes)

        if self.get_vote_strategy() == VoteStrategy.NO_APPLICATION.value:
            # 无应用：10票即通过
            if total_votes >= 10:
                return upvotes > downvotes
        else:
            # 有应用：2/3多数
            ratio = upvotes / total_votes if total_votes > 0 else 0
            if ratio >= 2/3 and upvotes > downvotes:
                return True
            # 或者总票数超过20时，简单多数也可通过
            if total_votes >= 20 and upvotes > downvotes:
                return True

        return False


@dataclass
class UpdateInfo:
    """系统更新信息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = ""
    title: str = ""
    description: str = ""

    # 更新内容
    new_features: List[str] = field(default_factory=list)
    bug_fixes: List[str] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)

    # 兼容性
    min_version: str = ""
    auto_migrate: bool = True

    # 发布时间
    released_at: str = field(default_factory=lambda: datetime.now().isoformat())
    rollout_percent: int = 0

    # 撤回投票
    withdraw_votes: List[str] = field(default_factory=list)
    withdraw_threshold: int = 10

    # 状态
    status: str = "available"


# ============ 窗口捕获器 ============

class WindowCapturer:
    """窗口捕获器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._captured_windows: Dict[int, WindowCapture] = {}
        self._capture_callbacks: List[Callable] = []
        self._context_matcher: Optional['WindowContextMatcher'] = None

    def set_context_matcher(self, matcher: 'WindowContextMatcher'):
        """设置上下文匹配器"""
        self._context_matcher = matcher

    def add_capture_callback(self, callback: Callable):
        """添加捕获回调"""
        self._capture_callbacks.append(callback)

    def capture_foreground_window(self) -> Optional[WindowCapture]:
        """捕获前台窗口"""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            # 获取窗口信息
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value

            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

            capture = WindowCapture(
                window_handle=hwnd,
                title=title,
                class_name=class_name.value,
                rect={
                    "x": rect.left,
                    "y": rect.top,
                    "width": rect.right - rect.left,
                    "height": rect.bottom - rect.top
                },
                process_id=process_id.value,
                process_name=self._get_process_name(process_id.value)
            )

            # 提取UI树
            capture.ui_tree = self._extract_ui_tree(hwnd)

            # 计算内容哈希
            capture.content_hash = self._compute_ui_hash(capture.ui_tree)

            # 提取上下文提示
            capture.context_hints = self._extract_context_hints(capture)

            self._captured_windows[hwnd] = capture

            for callback in self._capture_callbacks:
                try:
                    callback(capture)
                except Exception as e:
                    print(f"Capture callback error: {e}")

            return capture

        except Exception as e:
            print(f"Window capture error: {e}")
            return None

    def capture_by_handle(self, hwnd: int) -> Optional[WindowCapture]:
        """通过句柄捕获窗口"""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            if not user32.IsWindow(hwnd):
                return None

            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value

            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

            capture = WindowCapture(
                window_handle=hwnd,
                title=title,
                class_name=class_name.value,
                rect={
                    "x": rect.left,
                    "y": rect.top,
                    "width": rect.right - rect.left,
                    "height": rect.bottom - rect.top
                },
                process_id=process_id.value,
                process_name=self._get_process_name(process_id.value)
            )

            capture.ui_tree = self._extract_ui_tree(hwnd)
            capture.content_hash = self._compute_ui_hash(capture.ui_tree)
            capture.context_hints = self._extract_context_hints(capture)

            self._captured_windows[hwnd] = capture
            return capture

        except Exception as e:
            print(f"Capture by handle error: {e}")
            return None

    def _get_process_name(self, process_id: int) -> str:
        """获取进程名"""
        try:
            import psutil
            return psutil.Process(process_id).name()
        except:
            return "unknown"

    def _extract_ui_tree(self, hwnd: int) -> dict:
        """提取UI元素树"""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            def get_child_windows(parent_hwnd):
                children = []
                child = user32.GetWindow(parent_hwnd, 1)
                while child:
                    length = user32.GetWindowTextLengthW(child)
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(child, buff, length + 1)

                    class_name = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(child, class_name, 256)

                    rect = wintypes.RECT()
                    user32.GetWindowRect(child, ctypes.byref(rect))

                    ctrl_id = user32.GetDlgCtrlID(child)

                    children.append({
                        "handle": child,
                        "title": buff.value,
                        "class_name": class_name.value,
                        "rect": {
                            "x": rect.left,
                            "y": rect.top,
                            "width": rect.right - rect.left,
                            "height": rect.bottom - rect.top
                        },
                        "control_id": ctrl_id,
                        "children": get_child_windows(child)
                    })

                    child = user32.GetWindow(child, 2)

                return children

            return {
                "root": hwnd,
                "title": "",
                "children": get_child_windows(hwnd)
            }

        except Exception as e:
            return {"error": str(e)}

    def _compute_ui_hash(self, ui_tree: dict) -> str:
        """计算UI树哈希"""
        content = json.dumps(ui_tree, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _extract_context_hints(self, capture: WindowCapture) -> dict:
        """提取窗口上下文提示"""
        return {
            "class_name_pattern": self._generate_pattern(capture.class_name),
            "title_keywords": self._extract_keywords(capture.title),
            "process_name": capture.process_name,
            "window_rect": capture.rect
        }

    def _generate_pattern(self, class_name: str) -> str:
        """从类名生成匹配模式"""
        # 保留部分结构信息
        parts = class_name.split('.')
        if len(parts) > 1:
            return f"*.{parts[-1]}"
        return f"*{class_name[-8:]}*" if len(class_name) > 8 else class_name

    def _extract_keywords(self, title: str) -> List[str]:
        """从标题提取关键词"""
        # 移除常见无用词
        stop_words = {"的", "the", "-", "—", "|", ":", "::"}
        words = []

        current_word = ""
        for char in title:
            if char.isalnum() or char in ('_', '-'):
                current_word += char
            else:
                if current_word and current_word not in stop_words and len(current_word) > 1:
                    words.append(current_word.lower())
                current_word = ""

        if current_word and current_word not in stop_words and len(current_word) > 1:
            words.append(current_word.lower())

        return list(set(words))[:10]  # 最多10个关键词


class WindowContextMatcher:
    """窗口上下文匹配器"""

    def __init__(self, store: 'TemplateMarketStore'):
        self.store = store

    def find_matching_templates(self, capture: WindowCapture) -> List[UITemplate]:
        """查找匹配的模板"""
        if not capture.context_hints:
            return []

        matching_templates = []
        templates = self.store.list_templates(status=TemplateStatus.PUBLISHED.value)

        for template in templates:
            if not template.window_context:
                continue

            score = self._calculate_match_score(capture, template)
            if score > 0:
                template.metadata["match_score"] = score
                matching_templates.append(template)

        # 按匹配度排序
        matching_templates.sort(
            key=lambda t: t.metadata.get("match_score", 0),
            reverse=True
        )

        return matching_templates

    def _calculate_match_score(self, capture: WindowCapture, template: UITemplate) -> float:
        """计算匹配分数"""
        if not template.window_context or not capture.context_hints:
            return 0.0

        score = 0.0
        ctx = template.window_context
        hints = capture.context_hints

        # 类名匹配
        if ctx.get("class_name_pattern"):
            pattern = ctx["class_name_pattern"]
            if pattern in capture.class_name or capture.class_name in pattern:
                score += 40

        # 进程名匹配
        if ctx.get("process_name"):
            if ctx["process_name"].lower() in capture.process_name.lower():
                score += 30

        # 标题关键词匹配
        template_keywords = set(ctx.get("title_keywords", []))
        capture_keywords = set(hints.get("title_keywords", []))
        if template_keywords and capture_keywords:
            overlap = template_keywords & capture_keywords
            keyword_score = len(overlap) / max(len(template_keywords), 1) * 30
            score += keyword_score

        return score


# ============ 模板市场存储 ============

class TemplateMarketStore:
    """模板市场存储"""

    def __init__(self, store_path: str):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        self.templates_dir = self.store_path / "templates"
        self.votes_dir = self.store_path / "votes"
        self.uploads_dir = self.store_path / "uploads"
        self.pending_dir = self.store_path / "pending"

        for d in [self.templates_dir, self.votes_dir, self.uploads_dir, self.pending_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self._templates_index = self.store_path / "templates.json"
        self._votes_index = self.store_path / "votes.json"
        self._updates_index = self.store_path / "updates.json"

        self._load_indexes()

        # 初始化上下文匹配器
        self.context_matcher = WindowContextMatcher(self)

    def _load_indexes(self):
        """加载索引"""
        if self._templates_index.exists():
            with open(self._templates_index, "r", encoding="utf-8") as f:
                self._template_index: Dict[str, dict] = json.load(f)
        else:
            self._template_index = {}

        if self._votes_index.exists():
            with open(self._votes_index, "r", encoding="utf-8") as f:
                self._votes_index_data: List[dict] = json.load(f)
        else:
            self._votes_index_data = []

        if self._updates_index.exists():
            with open(self._updates_index, "r", encoding="utf-8") as f:
                self._updates: List[dict] = json.load(f)
        else:
            self._updates = []

    def _save_template_index(self):
        with open(self._templates_index, "w", encoding="utf-8") as f:
            json.dump(self._template_index, f, ensure_ascii=False, indent=2)

    def _save_votes_index(self):
        with open(self._votes_index, "w", encoding="utf-8") as f:
            json.dump(self._votes_index_data, f, ensure_ascii=False, indent=2)

    def _save_updates_index(self):
        with open(self._updates_index, "w", encoding="utf-8") as f:
            json.dump(self._updates, f, ensure_ascii=False, indent=2)

    # ============ 模板操作 ============

    def save_template(self, template: UITemplate) -> str:
        """保存模板"""
        template.content_hash = template.compute_hash()

        template_file = self.templates_dir / f"{template.id}.json"
        with open(template_file, "w", encoding="utf-8") as f:
            json.dump(asdict(template), f, ensure_ascii=False, indent=2)

        self._template_index[template.id] = {
            "name": template.name,
            "category": template.category,
            "author_id": template.author_id,
            "version": template.version,
            "status": template.status,
            "download_count": template.download_count,
            "use_count": template.use_count,
            "rating": template.rating
        }
        self._save_template_index()

        return template.id

    def get_template(self, template_id: str) -> Optional[UITemplate]:
        """获取模板"""
        template_file = self.templates_dir / f"{template_id}.json"
        if not template_file.exists():
            return None

        with open(template_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return UITemplate(**data)

    def delete_template(self, template_id: str, user_id: str) -> bool:
        """删除模板（仅上传者可删除）"""
        template = self.get_template(template_id)
        if not template:
            return False

        if template.author_id != user_id:
            return False

        template.status = TemplateStatus.DELETED.value
        self.save_template(template)

        if template_id in self._template_index:
            del self._template_index[template_id]
            self._save_template_index()

        return True

    def list_templates(
        self,
        category: str = None,
        author_id: str = None,
        status: str = TemplateStatus.PUBLISHED.value,
        search: str = None,
        sort_by: str = "download_count",
        limit: int = 50,
        visible_only: bool = True,
        exclude_user_id: str = None  # 排除某个用户的模板（用于投票可见性）
    ) -> List[UITemplate]:
        """列出模板"""
        templates = []

        for template_id, meta in self._template_index.items():
            if status and meta.get("status") != status:
                continue

            if category and meta.get("category") != category:
                continue

            if author_id and meta.get("author_id") != author_id:
                continue

            if search:
                if search.lower() not in meta.get("name", "").lower():
                    continue

            template = self.get_template(template_id)
            if template:
                templates.append(template)

        # 排序
        if sort_by == "download_count":
            templates.sort(key=lambda t: t.download_count, reverse=True)
        elif sort_by == "rating":
            templates.sort(key=lambda t: t.rating, reverse=True)
        elif sort_by == "created_at":
            templates.sort(key=lambda t: t.created_at, reverse=True)
        elif sort_by == "match_score":
            templates.sort(key=lambda t: t.metadata.get("match_score", 0), reverse=True)

        return templates[:limit]

    def increment_download(self, template_id: str):
        """增加下载计数"""
        template = self.get_template(template_id)
        if template:
            template.download_count += 1
            self.save_template(template)

    def increment_use(self, template_id: str):
        """增加使用计数"""
        template = self.get_template(template_id)
        if template:
            template.use_count += 1
            self.save_template(template)

    # ============ 投票操作 ============

    def create_vote(self, vote: Vote, template: UITemplate = None) -> str:
        """创建投票"""
        # 根据模板是否有应用确定投票策略
        if template:
            if not template.has_applications():
                vote.strategy = VoteStrategy.NO_APPLICATION.value
                vote.threshold = 10
            else:
                vote.strategy = VoteStrategy.WITH_APPLICATION.value
                vote.threshold = -1  # 2/3多数

        # 设置过期时间（7天）
        expires = datetime.now() + timedelta(days=7)
        vote.expires_at = expires.isoformat()

        vote_file = self.votes_dir / f"{vote.id}.json"
        with open(vote_file, "w", encoding="utf-8") as f:
            json.dump(asdict(vote), f, ensure_ascii=False, indent=2)

        self._votes_index_data.append({
            "id": vote.id,
            "vote_type": vote.vote_type,
            "target_id": vote.target_id,
            "status": vote.status,
            "expires_at": vote.expires_at,
            "strategy": vote.strategy
        })
        self._save_votes_index()

        return vote.id

    def get_vote(self, vote_id: str) -> Optional[Vote]:
        """获取投票"""
        vote_file = self.votes_dir / f"{vote_id}.json"
        if not vote_file.exists():
            return None

        with open(vote_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Vote(**data)

    def cast_vote(self, vote_id: str, user_id: str, decision: str) -> bool:
        """投票"""
        vote = self.get_vote(vote_id)
        if not vote:
            return False

        # 检查是否已投票
        if user_id in vote.upvotes or user_id in vote.downvotes or user_id in vote.abstain:
            return False

        # 记录投票
        if decision == "upvote":
            vote.upvotes.append(user_id)
        elif decision == "downvote":
            vote.downvotes.append(user_id)
        else:
            vote.abstain.append(user_id)

        # 保存投票
        vote_file = self.votes_dir / f"{vote_id}.json"
        with open(vote_file, "w", encoding="utf-8") as f:
            json.dump(asdict(vote), f, ensure_ascii=False, indent=2)

        # 检查决议
        self._check_vote_resolution(vote)

        return True

    def _check_vote_resolution(self, vote: Vote):
        """检查投票是否达成决议"""
        template = self.get_template(vote.target_id) if vote.vote_type == VoteType.DELETE.value else None

        if vote.check_resolution():
            vote.status = VoteStatus.APPROVED.value
            vote.processed_at = datetime.now().isoformat()

            # 计算最终分数
            vote.final_score = len(vote.upvotes) - len(vote.downvotes)

            # 执行结果
            self._execute_vote_result(vote)

            # 保存投票状态
            vote_file = self.votes_dir / f"{vote.id}.json"
            with open(vote_file, "w", encoding="utf-8") as f:
                json.dump(asdict(vote), f, ensure_ascii=False, indent=2)

            # 更新索引
            for idx, v in enumerate(self._votes_index_data):
                if v["id"] == vote.id:
                    v["status"] = vote.status
                    self._save_votes_index()
                    break

    def _execute_vote_result(self, vote: Vote):
        """执行投票结果"""
        if vote.vote_type == VoteType.DELETE.value:
            template = self.get_template(vote.target_id)
            if template:
                template.status = TemplateStatus.DELETED.value
                self.save_template(template)

        elif vote.vote_type == VoteType.WITHDRAW_UPDATE.value:
            for update in self._updates:
                if update["id"] == vote.target_id:
                    update["status"] = "withdrawn"
                    self._save_updates_index()
                    break

    def get_pending_votes_for_target(self, target_id: str, exclude_user_id: str = None) -> List[Vote]:
        """获取目标的所有待处理投票（可排除某用户）"""
        votes = []
        for vote_meta in self._votes_index_data:
            if vote_meta["target_id"] == target_id and vote_meta["status"] == VoteStatus.PENDING.value:
                vote = self.get_vote(vote_meta["id"])
                if vote:
                    # 排除指定用户（投票对自己不可见）
                    if exclude_user_id:
                        if (exclude_user_id in vote.upvotes or
                            exclude_user_id in vote.downvotes or
                            exclude_user_id in vote.abstain):
                            continue  # 跳过用户已参与的投票
                    votes.append(vote)
        return votes

    def get_user_pending_votes(self, user_id: str) -> List[Vote]:
        """获取用户参与的待处理投票"""
        votes = []
        for vote_meta in self._votes_index_data:
            if vote_meta["status"] == VoteStatus.PENDING.value:
                vote = self.get_vote(vote_meta["id"])
                if vote:
                    if (user_id in vote.upvotes or
                        user_id in vote.downvotes or
                        user_id in vote.abstain):
                        votes.append(vote)
        return votes

    # ============ 更新操作 ============

    def save_update(self, update: UpdateInfo):
        """保存更新信息"""
        for i, u in enumerate(self._updates):
            if u["version"] == update.version:
                self._updates[i] = asdict(update)
                break
        else:
            self._updates.append(asdict(update))

        self._save_updates_index()

    def get_latest_update(self) -> Optional[UpdateInfo]:
        """获取最新更新"""
        if not self._updates:
            return None

        updates = sorted(self._updates, key=lambda x: x["version"], reverse=True)

        for u in updates:
            if u.get("status") in ["available", "rolling_out"]:
                return UpdateInfo(**u)

        return None

    def get_update(self, update_id: str) -> Optional[UpdateInfo]:
        """获取更新"""
        for u in self._updates:
            if u["id"] == update_id:
                return UpdateInfo(**u)
        return None

    def vote_withdraw_update(self, update_id: str, user_id: str) -> bool:
        """投票撤回更新"""
        update = self.get_update(update_id)
        if not update:
            return False

        if user_id in update.withdraw_votes:
            return False

        update.withdraw_votes.append(user_id)
        self.save_update(update)

        if len(update.withdraw_votes) >= update.withdraw_threshold:
            update.status = "withdrawn"
            self.save_update(update)
            return True

        return False


# ============ 模板市场主类 ============

class TemplateMarket:
    """模板市场主类"""

    def __init__(self, store_path: str = None):
        if store_path is None:
            store_path = Path("~/.hermes/template_market").expanduser()

        self.store = TemplateMarketStore(str(store_path))
        self.capturer = WindowCapturer()
        self.capturer.set_context_matcher(self.store.context_matcher)

        self.current_user_id: str = ""
        self.current_user_name: str = ""

    def set_current_user(self, user_id: str, user_name: str):
        """设置当前用户"""
        self.current_user_id = user_id
        self.current_user_name = user_name

    # ============ 窗口捕获与上下文调用 ============

    def capture_window_as_template(
        self,
        name: str = None,
        description: str = "",
        window_context: dict = None
    ) -> Optional[UITemplate]:
        """捕获焦点窗口并创建模板"""
        capture = self.capturer.capture_foreground_window()
        if not capture:
            return None

        # 使用窗口上下文
        if window_context is None and capture.context_hints:
            window_context = {
                "class_name_pattern": capture.context_hints.get("class_name_pattern", ""),
                "title_keywords": capture.context_hints.get("title_keywords", []),
                "process_name": capture.process_name
            }

        template = UITemplate(
            name=name or f"窗口模板 {capture.title}",
            description=description,
            category="captured",
            author_id=self.current_user_id,
            author_name=self.current_user_name,
            ui_tree=capture.ui_tree,
            source_window=capture.title,
            content_hash=capture.content_hash,
            window_context=window_context
        )

        self.store.save_template(template)
        return template

    def capture_specific_window(self, hwnd: int, name: str = None) -> Optional[UITemplate]:
        """捕获指定窗口"""
        capture = self.capturer.capture_by_handle(hwnd)
        if not capture:
            return None

        window_context = {
            "class_name_pattern": capture.context_hints.get("class_name_pattern", ""),
            "title_keywords": capture.context_hints.get("title_keywords", []),
            "process_name": capture.process_name
        } if capture.context_hints else None

        template = UITemplate(
            name=name or f"窗口模板 {capture.title}",
            category="captured",
            author_id=self.current_user_id,
            author_name=self.current_user_name,
            ui_tree=capture.ui_tree,
            source_window=capture.title,
            content_hash=capture.content_hash,
            window_context=window_context
        )

        self.store.save_template(template)
        return template

    def find_templates_for_current_window(self) -> List[UITemplate]:
        """为当前窗口查找匹配的模板"""
        capture = self.capturer.capture_foreground_window()
        if not capture:
            return []

        return self.store.context_matcher.find_matching_templates(capture)

    def find_templates_for_window(self, hwnd: int) -> List[UITemplate]:
        """为指定窗口查找匹配的模板"""
        capture = self.capturer.capture_by_handle(hwnd)
        if not capture:
            return []

        return self.store.context_matcher.find_matching_templates(capture)

    def detect_window_changes(self) -> dict:
        """检测窗口是否有较大改变"""
        capture = self.capturer.capture_foreground_window()
        if not capture:
            return {"changed": False}

        return {
            "changed": True,
            "capture": capture,
            "hash": capture.content_hash
        }

    # ============ 模板管理 ============

    def upload_template(
        self,
        template: UITemplate,
        window_context: dict = None
    ) -> str:
        """上传模板"""
        template.author_id = self.current_user_id
        template.author_name = self.current_user_name
        template.status = TemplateStatus.PUBLISHED.value

        if window_context:
            template.window_context = window_context

        return self.store.save_template(template)

    def download_template(self, template_id: str) -> Optional[UITemplate]:
        """下载模板"""
        self.store.increment_download(template_id)
        return self.store.get_template(template_id)

    def apply_template(self, template_id: str) -> bool:
        """应用模板"""
        self.store.increment_use(template_id)
        return True

    def fork_template(self, template_id: str, new_name: str = None) -> Optional[UITemplate]:
        """Fork模板"""
        original = self.store.get_template(template_id)
        if not original:
            return None

        forked = UITemplate(
            name=new_name or f"{original.name} (Fork)",
            description=original.description,
            category=original.category,
            tags=original.tags.copy(),
            author_id=self.current_user_id,
            author_name=self.current_user_name,
            ui_tree=original.ui_tree.copy(),
            styles=original.styles.copy(),
            layouts=original.layouts.copy(),
            parent_id=original.id,
            version="1.0.0",
            window_context=original.window_context.copy() if original.window_context else None
        )

        self.store.save_template(forked)
        return forked

    # ============ 民主投票 ============

    def initiate_delete_vote(self, template_id: str, reason: str) -> Optional[str]:
        """发起删除投票"""
        template = self.store.get_template(template_id)
        if not template:
            return None

        if template.author_id == self.current_user_id:
            return None

        vote = Vote(
            vote_type=VoteType.DELETE.value,
            target_id=template_id,
            initiator_id=self.current_user_id,
            initiator_name=self.current_user_name,
            reason=reason
        )

        return self.store.create_vote(vote, template)

    def vote_on_delete(self, vote_id: str, approve: bool):
        """对删除投票投票"""
        decision = "upvote" if approve else "downvote"
        self.store.cast_vote(vote_id, self.current_user_id, decision)

    def get_visible_pending_votes(self) -> List[Vote]:
        """获取对当前用户可见的待处理投票（排除自己参与的）"""
        return self.store.get_pending_votes_for_target(
            target_id="",  # 空表示所有
            exclude_user_id=self.current_user_id
        )

    def get_template_votes(self, template_id: str) -> List[Vote]:
        """获取模板的投票（对自己不可见的已参与投票会被过滤）"""
        return self.store.get_pending_votes_for_target(
            template_id,
            exclude_user_id=self.current_user_id
        )

    # ============ 更新管理 ============

    def check_for_updates(self) -> Optional[UpdateInfo]:
        """检查更新"""
        return self.store.get_latest_update()

    def acknowledge_update(self, update_id: str) -> bool:
        """用户确认收到更新通知"""
        update = self.store.get_update(update_id)
        if not update:
            return False

        if "acknowledged_by" not in update.metadata:
            update.metadata["acknowledged_by"] = []
        update.metadata["acknowledged_by"].append(self.current_user_id)
        self.store.save_update(update)

        return True

    def vote_withdraw_update(self, update_id: str) -> bool:
        """投票撤回更新"""
        return self.store.vote_withdraw_update(update_id, self.current_user_id)

    def get_pending_update_notifications(self) -> List[UpdateInfo]:
        """获取待处理的更新通知"""
        latest = self.store.get_latest_update()
        if not latest:
            return []

        acknowledged = latest.metadata.get("acknowledged_by", [])
        if self.current_user_id in acknowledged:
            return []

        return [latest]


# ============ 全局实例 ============

_market_instance: Optional[TemplateMarket] = None


def get_template_market() -> TemplateMarket:
    """获取模板市场实例"""
    global _market_instance
    if _market_instance is None:
        _market_instance = TemplateMarket()
    return _market_instance