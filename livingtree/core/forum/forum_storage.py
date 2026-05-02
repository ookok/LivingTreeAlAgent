"""
去中心化论坛 - 存储层
SQLite 本地存储 + 虚拟云盘集成 + 全文检索

功能:
- 帖子/回复的本地存储
- 话题/订阅管理
- 全文检索
- 大帖附件云盘存储
"""

import sqlite3
import json
import time
import os
import logging
from typing import List, Optional, Dict, Any, Tuple, Callable
from pathlib import Path
from dataclasses import asdict
import threading
import asyncio

from .models import (
    ForumPost, ForumReply, Topic, Subscription, Vote,
    Author, PostContent, Attachment, SmartDraft,
    PostStatus, ReplyStatus, ContentType, VoteType,
    generate_post_id, generate_reply_id, generate_topic_id, compute_hash_chain
)

logger = logging.getLogger(__name__)


class ForumStorage:
    """
    论坛存储管理器

    存储策略:
    - 小内容 (文本): 直接 SQLite 存储
    - 大内容/附件: 加密上传到虚拟云盘
    - 全文检索: SQLite FTS5
    """

    def __init__(self, db_path: Optional[str] = None, node_id: str = ""):
        if db_path is None:
            # 默认路径: ~/.hermes-desktop/forum.db
            home = os.path.expanduser("~")
            data_dir = os.path.join(home, ".hermes-desktop")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "forum.db")

        self.db_path = db_path
        self.node_id = node_id
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

        # 云盘回调 (可选)
        self._cloud_storage_callback: Optional[Callable] = None

        # 初始化
        self._init_db()

    def set_cloud_storage_callback(self, callback: Callable):
        """设置云盘存储回调 (用于大文件存储)"""
        self._cloud_storage_callback = callback

    def _init_db(self):
        """初始化数据库"""
        with self._lock:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

            # 启用 WAL 模式 (提高并发)
            self._conn.execute("PRAGMA journal_mode=WAL")

            # 创建表
            self._create_tables()

    def _create_tables(self):
        """创建数据库表"""
        cursor = self._conn.cursor()

        # 话题表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                topic_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '📋',
                color TEXT DEFAULT '#4A90D9',
                post_count INTEGER DEFAULT 0,
                member_count INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0,
                is_nsfw INTEGER DEFAULT 0,
                created_at REAL,
                creator_id TEXT
            )
        """)

        # 帖子表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY,
                topic_id TEXT NOT NULL,
                author_json TEXT NOT NULL,
                title TEXT NOT NULL,
                content_json TEXT NOT NULL,
                status TEXT DEFAULT 'published',
                upvotes INTEGER DEFAULT 0,
                downvotes INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                hash_chain_json TEXT,
                created_at REAL,
                updated_at REAL,
                expires_at REAL,
                smart_draft_json TEXT,
                tags_json TEXT,
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
            )
        """)

        # 回复表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS replies (
                reply_id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                parent_reply_id TEXT,
                author_json TEXT NOT NULL,
                content_json TEXT NOT NULL,
                status TEXT DEFAULT 'normal',
                upvotes INTEGER DEFAULT 0,
                downvotes INTEGER DEFAULT 0,
                hash_chain_json TEXT,
                created_at REAL,
                updated_at REAL,
                FOREIGN KEY (post_id) REFERENCES posts(post_id),
                FOREIGN KEY (parent_reply_id) REFERENCES replies(reply_id)
            )
        """)

        # 订阅表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                subscriber_id TEXT NOT NULL,
                topic_id TEXT NOT NULL,
                subscribed_at REAL,
                notify_enabled INTEGER DEFAULT 1,
                PRIMARY KEY (subscriber_id, topic_id)
            )
        """)

        # 投票表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                voter_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                vote_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                timestamp REAL,
                PRIMARY KEY (voter_id, target_type, target_id)
            )
        """)

        # 帖子全文检索
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
                post_id,
                title,
                content_text,
                tags,
                content='posts',
                content_rowid='rowid'
            )
        """)

        # 回复全文检索
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS replies_fts USING fts5(
                reply_id,
                content_text,
                content='replies',
                content_rowid='rowid'
            )
        """)

        # 触发器: 帖子插入时更新 FTS
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
                INSERT INTO posts_fts(post_id, title, content_text, tags)
                VALUES (new.post_id, new.title, new.content_json, new.tags_json);
            END
        """)

        # 触发器: 回复插入时更新 FTS
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS replies_ai AFTER INSERT ON replies BEGIN
                INSERT INTO replies_fts(reply_id, content_text)
                VALUES (new.reply_id, new.content_json);
            END
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_topic ON posts(topic_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_json)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_replies_post ON replies(post_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_replies_parent ON replies(parent_reply_id)")

        self._conn.commit()

    # ==================== 话题操作 ====================

    def create_topic(self, name: str, description: str = "", icon: str = "📋",
                    color: str = "#4A90D9", creator_id: str = "") -> Topic:
        """创建话题"""
        topic_id = generate_topic_id(name)
        topic = Topic(
            topic_id=topic_id,
            name=name,
            description=description,
            icon=icon,
            color=color,
            created_at=time.time(),
            creator_id=creator_id or self.node_id
        )

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO topics
                (topic_id, name, description, icon, color, post_count, member_count,
                 is_private, is_nsfw, created_at, creator_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                topic.topic_id, topic.name, topic.description, topic.icon, topic.color,
                topic.post_count, topic.member_count,
                int(topic.is_private), int(topic.is_nsfw), topic.created_at, topic.creator_id
            ))
            self._conn.commit()

        return topic

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """获取话题"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM topics WHERE topic_id = ?", (topic_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_topic(row)
            return None

    def get_all_topics(self) -> List[Topic]:
        """获取所有话题"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM topics ORDER BY post_count DESC")
            return [self._row_to_topic(row) for row in cursor.fetchall()]

    def update_topic_stats(self, topic_id: str, post_count: int = None, member_count: int = None):
        """更新话题统计"""
        with self._lock:
            cursor = self._conn.cursor()
            if post_count is not None:
                cursor.execute("UPDATE topics SET post_count = ? WHERE topic_id = ?", (post_count, topic_id))
            if member_count is not None:
                cursor.execute("UPDATE topics SET member_count = ? WHERE topic_id = ?", (member_count, topic_id))
            self._conn.commit()

    def _row_to_topic(self, row: sqlite3.Row) -> Topic:
        """行转 Topic"""
        return Topic(
            topic_id=row["topic_id"],
            name=row["name"],
            description=row["description"] or "",
            icon=row["icon"] or "📋",
            color=row["color"] or "#4A90D9",
            post_count=row["post_count"] or 0,
            member_count=row["member_count"] or 0,
            is_private=bool(row["is_private"]),
            is_nsfw=bool(row["is_nsfw"]),
            created_at=row["created_at"] or time.time(),
            creator_id=row["creator_id"] or ""
        )

    # ==================== 帖子操作 ====================

    def create_post(self, topic_id: str, author: Author, title: str, content: PostContent,
                   tags: List[str] = None, status: PostStatus = PostStatus.PUBLISHED) -> ForumPost:
        """创建帖子"""
        post_id = generate_post_id()

        # 计算哈希链
        content_str = json.dumps(content.to_dict(), sort_keys=True)
        hash_chain = compute_hash_chain(content_str)

        post = ForumPost(
            post_id=post_id,
            topic_id=topic_id,
            author=author,
            title=title,
            content=content,
            status=status,
            hash_chain=hash_chain,
            created_at=time.time(),
            tags=tags or []
        )

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO posts
                (post_id, topic_id, author_json, title, content_json, status,
                 upvotes, downvotes, reply_count, view_count, hash_chain_json,
                 created_at, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post.post_id, post.topic_id, json.dumps(author.to_dict()), post.title,
                json.dumps(content.to_dict()), post.status.value,
                post.upvotes, post.downvotes, post.reply_count, post.view_count,
                json.dumps(hash_chain.__dict__),
                post.created_at, json.dumps(post.tags)
            ))

            # 更新话题帖子数
            cursor.execute("UPDATE topics SET post_count = post_count + 1 WHERE topic_id = ?", (topic_id,))
            self._conn.commit()

        return post

    def get_post(self, post_id: str) -> Optional[ForumPost]:
        """获取帖子"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_post(row)
            return None

    def get_posts_by_topic(self, topic_id: str, offset: int = 0, limit: int = 20,
                          sort_by: str = "created") -> List[ForumPost]:
        """获取话题下的帖子"""
        with self._lock:
            cursor = self._conn.cursor()
            if sort_by == "score":
                # 按评分排序
                cursor.execute("""
                    SELECT * FROM posts
                    WHERE topic_id = ? AND status = 'published'
                    ORDER BY (CAST(upvotes AS REAL) / (upvotes + downvotes + 1)) DESC
                    LIMIT ? OFFSET ?
                """, (topic_id, limit, offset))
            else:
                # 按时间排序
                cursor.execute("""
                    SELECT * FROM posts
                    WHERE topic_id = ? AND status = 'published'
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (topic_id, limit, offset))
            return [self._row_to_post(row) for row in cursor.fetchall()]

    def get_all_posts(self, offset: int = 0, limit: int = 20, sort_by: str = "created") -> List[ForumPost]:
        """获取所有帖子"""
        with self._lock:
            cursor = self._conn.cursor()
            if sort_by == "score":
                cursor.execute("""
                    SELECT * FROM posts
                    WHERE status = 'published'
                    ORDER BY (CAST(upvotes AS REAL) / (upvotes + downvotes + 1)) DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            else:
                cursor.execute("""
                    SELECT * FROM posts
                    WHERE status = 'published'
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            return [self._row_to_post(row) for row in cursor.fetchall()]

    def update_post(self, post_id: str, **kwargs):
        """更新帖子"""
        allowed = ["title", "content_json", "status", "upvotes", "downvotes",
                  "reply_count", "view_count", "updated_at", "tags_json"]
        updates = []
        values = []

        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)

        if not updates:
            return

        values.append(post_id)
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(f"UPDATE posts SET {', '.join(updates)} WHERE post_id = ?", values)
            self._conn.commit()

    def increment_post_views(self, post_id: str):
        """增加浏览数"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("UPDATE posts SET view_count = view_count + 1 WHERE post_id = ?", (post_id,))
            self._conn.commit()

    def delete_post(self, post_id: str):
        """删除帖子 (软删除)"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("UPDATE posts SET status = 'deleted' WHERE post_id = ?", (post_id,))
            self._conn.commit()

    def _row_to_post(self, row: sqlite3.Row) -> ForumPost:
        """行转 ForumPost"""
        import hashlib
        author_dict = json.loads(row["author_json"])
        content_dict = json.loads(row["content_json"])

        hash_chain = None
        if row["hash_chain_json"]:
            hash_chain_dict = json.loads(row["hash_chain_json"])
            from .models import ContentHash
            hash_chain = ContentHash(**hash_chain_dict)

        tags = []
        if row["tags_json"]:
            tags = json.loads(row["tags_json"])

        from .models import PostContent, Author, ContentType, PostStatus
        author = Author(**author_dict)
        content = PostContent(
            text=content_dict.get("text", ""),
            content_type=ContentType(content_dict.get("content_type", "text")),
            attachments=[],
            language=content_dict.get("language", "zh")
        )

        return ForumPost(
            post_id=row["post_id"],
            topic_id=row["topic_id"],
            author=author,
            title=row["title"],
            content=content,
            status=PostStatus(row["status"]),
            upvotes=row["upvotes"] or 0,
            downvotes=row["downvotes"] or 0,
            reply_count=row["reply_count"] or 0,
            view_count=row["view_count"] or 0,
            hash_chain=hash_chain,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            tags=tags
        )

    # ==================== 回复操作 ====================

    def create_reply(self, post_id: str, author: Author, content: PostContent,
                    parent_reply_id: str = None) -> ForumReply:
        """创建回复"""
        reply_id = generate_reply_id()

        # 计算哈希链
        content_str = json.dumps(content.to_dict(), sort_keys=True)
        hash_chain = compute_hash_chain(content_str)

        reply = ForumReply(
            reply_id=reply_id,
            post_id=post_id,
            parent_reply_id=parent_reply_id,
            author=author,
            content=content,
            hash_chain=hash_chain,
            created_at=time.time()
        )

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT INTO replies
                (reply_id, post_id, parent_reply_id, author_json, content_json,
                 status, upvotes, downvotes, hash_chain_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reply.reply_id, reply.post_id, reply.parent_reply_id,
                json.dumps(author.to_dict()), json.dumps(content.to_dict()),
                reply.status.value, reply.upvotes, reply.downvotes,
                json.dumps(hash_chain.__dict__), reply.created_at
            ))

            # 更新帖子回复数
            cursor.execute("UPDATE posts SET reply_count = reply_count + 1 WHERE post_id = ?", (post_id,))
            self._conn.commit()

        return reply

    def get_reply(self, reply_id: str) -> Optional[ForumReply]:
        """获取回复"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM replies WHERE reply_id = ?", (reply_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_reply(row)
            return None

    def get_replies_by_post(self, post_id: str, offset: int = 0, limit: int = 50) -> List[ForumReply]:
        """获取帖子的回复"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT * FROM replies
                WHERE post_id = ? AND status = 'normal'
                ORDER BY created_at ASC
                LIMIT ? OFFSET ?
            """, (post_id, limit, offset))
            return [self._row_to_reply(row) for row in cursor.fetchall()]

    def get_nested_replies(self, post_id: str) -> Dict[str, List[ForumReply]]:
        """获取嵌套回复结构"""
        replies = self.get_replies_by_post(post_id, limit=1000)

        # 按父回复分组
        nested: Dict[str, List[ForumReply]] = {}
        root_replies = []

        for reply in replies:
            if reply.parent_reply_id:
                if reply.parent_reply_id not in nested:
                    nested[reply.parent_reply_id] = []
                nested[reply.parent_reply_id].append(reply)
            else:
                root_replies.append(reply)

        # 添加嵌套的子回复
        def collect_children(parent_id: str) -> List[Tuple[int, ForumReply]]:
            result = []
            children = nested.get(parent_id, [])
            for reply in children:
                result.append((0, reply))
                result.extend([(level + 1, r) for level, r in collect_children(reply.reply_id)])
            return result

        result = []
        for reply in root_replies:
            result.append((0, reply))
            result.extend(collect_children(reply.reply_id))

        return {"root": root_replies, "nested": nested}

    def _row_to_reply(self, row: sqlite3.Row) -> ForumReply:
        """行转 ForumReply"""
        author_dict = json.loads(row["author_json"])
        content_dict = json.loads(row["content_json"])

        hash_chain = None
        if row["hash_chain_json"]:
            hash_chain_dict = json.loads(row["hash_chain_json"])
            from .models import ContentHash
            hash_chain = ContentHash(**hash_chain_dict)

        from .models import Author, PostContent, ContentType, ReplyStatus
        author = Author(**author_dict)
        content = PostContent(
            text=content_dict.get("text", ""),
            content_type=ContentType(content_dict.get("content_type", "text")),
            attachments=[],
            language=content_dict.get("language", "zh")
        )

        return ForumReply(
            reply_id=row["reply_id"],
            post_id=row["post_id"],
            parent_reply_id=row["parent_reply_id"],
            author=author,
            content=content,
            status=ReplyStatus(row["status"]),
            upvotes=row["upvotes"] or 0,
            downvotes=row["downvotes"] or 0,
            hash_chain=hash_chain,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    # ==================== 订阅操作 ====================

    def subscribe(self, subscriber_id: str, topic_id: str) -> Subscription:
        """订阅话题"""
        sub = Subscription(
            subscriber_id=subscriber_id,
            topic_id=topic_id,
            subscribed_at=time.time()
        )

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO subscriptions
                (subscriber_id, topic_id, subscribed_at, notify_enabled)
                VALUES (?, ?, ?, ?)
            """, (sub.subscriber_id, sub.topic_id, sub.subscribed_at, int(sub.notify_enabled)))

            # 更新话题成员数
            cursor.execute("UPDATE topics SET member_count = member_count + 1 WHERE topic_id = ?", (topic_id,))
            self._conn.commit()

        return sub

    def unsubscribe(self, subscriber_id: str, topic_id: str):
        """取消订阅"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                DELETE FROM subscriptions WHERE subscriber_id = ? AND topic_id = ?
            """, (subscriber_id, topic_id))
            cursor.execute("UPDATE topics SET member_count = MAX(0, member_count - 1) WHERE topic_id = ?", (topic_id,))
            self._conn.commit()

    def get_subscriptions(self, subscriber_id: str) -> List[str]:
        """获取用户的订阅列表"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT topic_id FROM subscriptions WHERE subscriber_id = ?", (subscriber_id,))
            return [row["topic_id"] for row in cursor.fetchall()]

    def is_subscribed(self, subscriber_id: str, topic_id: str) -> bool:
        """检查是否已订阅"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT 1 FROM subscriptions WHERE subscriber_id = ? AND topic_id = ?
            """, (subscriber_id, topic_id))
            return cursor.fetchone() is not None

    # ==================== 投票操作 ====================

    def vote(self, voter_id: str, target_type: str, target_id: str, vote_type: VoteType) -> bool:
        """投票"""
        with self._lock:
            cursor = self._conn.cursor()

            # 获取现有投票
            cursor.execute("""
                SELECT vote_type FROM votes
                WHERE voter_id = ? AND target_type = ? AND target_id = ?
            """, (voter_id, target_type, target_id))
            row = cursor.fetchone()

            old_vote_type = row["vote_type"] if row else None

            # 插入/更新投票
            cursor.execute("""
                INSERT OR REPLACE INTO votes
                (voter_id, target_type, target_id, vote_type, weight, timestamp)
                VALUES (?, ?, ?, ?, 1.0, ?)
            """, (voter_id, target_type, target_id, vote_type.value, time.time()))

            # 更新目标 upvotes/downvotes
            if target_type == "post":
                table = "posts"
                id_col = "post_id"
            else:
                table = "replies"
                id_col = "reply_id"

            # 扣除旧投票
            if old_vote_type == "up":
                cursor.execute(f"UPDATE {table} SET upvotes = MAX(0, upvotes - 1) WHERE {id_col} = ?", (target_id,))
            elif old_vote_type == "down":
                cursor.execute(f"UPDATE {table} SET downvotes = MAX(0, downvotes - 1) WHERE {id_col} = ?", (target_id,))

            # 添加新投票
            if vote_type == VoteType.UP:
                cursor.execute(f"UPDATE {table} SET upvotes = upvotes + 1 WHERE {id_col} = ?", (target_id,))
            elif vote_type == VoteType.DOWN:
                cursor.execute(f"UPDATE {table} SET downvotes = downvotes + 1 WHERE {id_col} = ?", (target_id,))

            self._conn.commit()

        return True

    def get_user_vote(self, voter_id: str, target_type: str, target_id: str) -> Optional[VoteType]:
        """获取用户对某内容的投票"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT vote_type FROM votes
                WHERE voter_id = ? AND target_type = ? AND target_id = ?
            """, (voter_id, target_type, target_id))
            row = cursor.fetchone()
            if row:
                return VoteType(row["vote_type"])
            return None

    # ==================== 搜索 ====================

    def search_posts(self, query: str, limit: int = 20) -> List[ForumPost]:
        """搜索帖子"""
        with self._lock:
            cursor = self._conn.cursor()
            # 使用 FTS5 搜索
            cursor.execute("""
                SELECT p.* FROM posts p
                JOIN posts_fts fts ON p.post_id = fts.post_id
                WHERE posts_fts MATCH ? AND p.status = 'published'
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            return [self._row_to_post(row) for row in cursor.fetchall()]

    def search_replies(self, query: str, limit: int = 20) -> List[ForumReply]:
        """搜索回复"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT r.* FROM replies r
                JOIN replies_fts fts ON r.reply_id = fts.reply_id
                WHERE replies_fts MATCH ? AND r.status = 'normal'
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            return [self._row_to_reply(row) for row in cursor.fetchall()]

    # ==================== 统计 ====================

    def get_user_stats(self, node_id: str) -> Dict[str, int]:
        """获取用户统计"""
        with self._lock:
            cursor = self._conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) as count FROM posts
                WHERE author_json LIKE ? AND status = 'published'
            """, (f'%"node_id": "{node_id}"%',))
            post_count = cursor.fetchone()["count"]

            cursor.execute("""
                SELECT COUNT(*) as count FROM replies
                WHERE author_json LIKE ? AND status = 'normal'
            """, (f'%"node_id": "{node_id}"%',))
            reply_count = cursor.fetchone()["count"]

            cursor.execute("""
                SELECT COALESCE(SUM(upvotes), 0) as total FROM posts
                WHERE author_json LIKE ? AND status = 'published'
            """, (f'%"node_id": "{node_id}"%',))
            total_upvotes = cursor.fetchone()["total"]

            return {
                "post_count": post_count,
                "reply_count": reply_count,
                "total_upvotes": total_upvotes
            }

    def close(self):
        """关闭数据库"""
        if self._conn:
            self._conn.close()
            self._conn = None
