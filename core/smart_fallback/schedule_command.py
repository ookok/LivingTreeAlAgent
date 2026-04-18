"""
定时任务命令执行器
Schedule Command Executor

处理自然语言定时任务命令的执行
与 WorkBuddy automation_update 工具集成
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime

from .schedule_nlp import (
    NLPScheduleParser,
    ParsedSchedule,
    CommandType,
    ScheduleType
)


@dataclass
class TaskInfo:
    """任务信息"""
    id: str
    name: str
    prompt: str
    schedule_type: str
    rrule: Optional[str]
    scheduled_at: Optional[str]
    status: str
    last_run: Optional[str]
    next_run: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TaskInfo":
        return cls(
            id=row["id"],
            name=row["name"],
            prompt=row["prompt"],
            schedule_type=row["schedule_type"],
            rrule=row["rrule"],
            scheduled_at=row["scheduled_at"],
            status=row["status"],
            last_run=row["last_run"],
            next_run=row["next_run"],
            created_at=row["created_at"]
        )


class ScheduleCommandExecutor:
    """
    定时任务命令执行器

    负责：
    1. 执行自然语言解析后的定时任务命令
    2. 与 WorkBuddy automation 系统交互
    3. 提供任务查询和管理功能
    """

    # WorkBuddy 自动化数据库路径
    AUTOMATION_DB_PATTERN = str(Path.home() / ".workbuddy" / "automations.db")

    def __init__(self):
        self.parser = NLPScheduleParser()
        self._ensure_automation_db()

    def _ensure_automation_db(self):
        """确保自动化数据库存在"""
        db_path = Path(self.AUTOMATION_DB_PATTERN)
        if not db_path.exists():
            # 尝试创建基本结构
            db_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS automations (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        prompt TEXT,
                        cwds TEXT,
                        schedule_type TEXT DEFAULT 'recurring',
                        rrule TEXT,
                        scheduled_at TEXT,
                        status TEXT DEFAULT 'ACTIVE',
                        last_run TEXT,
                        next_run TEXT,
                        valid_from TEXT,
                        valid_until TEXT,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT DEFAULT (datetime('now'))
                    )
                """)
                conn.commit()
                conn.close()
            except Exception:
                pass

    def execute(self, text: str) -> Dict[str, Any]:
        """
        执行自然语言命令

        Args:
            text: 自然语言输入

        Returns:
            执行结果字典
        """
        # 1. 解析命令
        parsed = self.parser.parse(text)

        if parsed.command == CommandType.UNKNOWN:
            return {
                "success": False,
                "error": parsed.error_message or "无法理解您的意图",
                "parsed": parsed
            }

        # 2. 根据命令类型执行
        if parsed.command == CommandType.CREATE:
            return self._execute_create(parsed)
        elif parsed.command == CommandType.QUERY or parsed.command == CommandType.LIST:
            return self._execute_query(parsed)
        elif parsed.command == CommandType.DELETE:
            return self._execute_delete(parsed)
        else:
            return {
                "success": False,
                "error": "未知命令类型",
                "parsed": parsed
            }

    def _execute_create(self, parsed: ParsedSchedule) -> Dict[str, Any]:
        """执行创建命令"""
        try:
            # 构建自动化任务数据
            task_data = {
                "name": parsed.description or f"定时任务_{parsed.time_expr}",
                "prompt": parsed.description or "执行定时任务",
                "cwds": "d:/mhzyapp/hermes-desktop",
                "status": "ACTIVE"
            }

            if parsed.schedule_type == ScheduleType.ONCE:
                task_data["schedule_type"] = "once"
                task_data["scheduled_at"] = parsed.scheduled_at
            else:
                task_data["schedule_type"] = "recurring"
                task_data["rrule"] = parsed.rrule

            # 保存到数据库
            task_id = self._save_automation(task_data)

            # 构建成功消息
            msg_parts = [f"✅ 定时任务创建成功！"]
            msg_parts.append(f"📋 任务ID: `{task_id}`")

            if parsed.schedule_type == ScheduleType.ONCE:
                if parsed.scheduled_at:
                    dt = datetime.fromisoformat(parsed.scheduled_at)
                    msg_parts.append(f"⏰ 执行时间: {dt.strftime('%Y-%m-%d %H:%M')}")
            else:
                msg_parts.append(f"🔄 循环规则: {parsed.rrule}")

            if parsed.description:
                msg_parts.append(f"📝 描述: {parsed.description}")

            msg_parts.append("")
            msg_parts.append("💡 您可以对我说：")
            msg_parts.append("  - '查看我的定时任务' - 查看所有任务")
            msg_parts.append("  - '删除这个任务' - 删除指定任务")

            return {
                "success": True,
                "task_id": task_id,
                "message": "\n".join(msg_parts),
                "parsed": parsed
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"创建任务失败: {str(e)}",
                "parsed": parsed
            }

    def _execute_query(self, parsed: ParsedSchedule) -> Dict[str, Any]:
        """执行查询命令"""
        try:
            tasks = self._get_all_automations()

            if not tasks:
                return {
                    "success": True,
                    "message": "📭 暂无定时任务\n\n💡 您可以对我说：\n  - '每天早上9点提醒我开会' - 创建定时任务",
                    "tasks": []
                }

            # 应用过滤器
            filtered = self._apply_filters(tasks, parsed.filters or {})

            if not filtered:
                return {
                    "success": True,
                    "message": "🔍 没有找到符合条件的任务",
                    "tasks": []
                }

            # 构建消息
            msg_parts = [f"📋 共找到 {len(filtered)} 个定时任务：\n"]

            for i, task in enumerate(filtered, 1):
                status_icon = "🟢" if task.status == "ACTIVE" else "🔴"
                msg_parts.append(f"{i}. {status_icon} **{task.name}**")
                msg_parts.append(f"   ID: `{task.id}`")

                if task.schedule_type == "once" and task.scheduled_at:
                    try:
                        dt = datetime.fromisoformat(task.scheduled_at)
                        msg_parts.append(f"   ⏰ 执行时间: {dt.strftime('%Y-%m-%d %H:%M')}")
                    except:
                        msg_parts.append(f"   ⏰ 执行时间: {task.scheduled_at}")
                elif task.rrule:
                    rrule_desc = self._describe_rrule(task.rrule)
                    msg_parts.append(f"   🔄 {rrule_desc}")

                if task.last_run:
                    msg_parts.append(f"   📌 上次执行: {task.last_run}")

                msg_parts.append("")

            msg_parts.append("💡 您可以对我说：")
            msg_parts.append("  - '删除任务 [ID]' - 删除指定任务")
            msg_parts.append("  - '删除每天9点的任务' - 按描述删除")

            return {
                "success": True,
                "message": "\n".join(msg_parts),
                "tasks": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "schedule_type": t.schedule_type,
                        "status": t.status
                    }
                    for t in filtered
                ]
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"查询任务失败: {str(e)}"
            }

    def _execute_delete(self, parsed: ParsedSchedule) -> Dict[str, Any]:
        """执行删除命令"""
        try:
            if parsed.task_id:
                # 直接按ID删除
                success = self._delete_automation(parsed.task_id)
                if success:
                    return {
                        "success": True,
                        "message": f"🗑️ 已删除任务 `{parsed.task_id}`"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"未找到任务 `{parsed.task_id}`"
                    }
            elif parsed.filters:
                # 按条件删除
                tasks = self._get_all_automations()
                filtered = self._apply_filters(tasks, parsed.filters)

                if not filtered:
                    return {
                        "success": False,
                        "error": "没有找到要删除的任务"
                    }

                deleted_count = 0
                for task in filtered:
                    if self._delete_automation(task.id):
                        deleted_count += 1

                return {
                    "success": True,
                    "message": f"🗑️ 已删除 {deleted_count} 个任务"
                }
            else:
                return {
                    "success": False,
                    "error": "请指定要删除的任务ID或描述"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"删除任务失败: {str(e)}"
            }

    def _save_automation(self, data: Dict[str, Any]) -> str:
        """保存自动化任务到数据库"""
        import uuid
        task_id = str(uuid.uuid4())[:8]

        db_path = self.AUTOMATION_DB_PATTERN
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 计算下次执行时间
        next_run = self._calculate_next_run(
            data.get("rrule"),
            data.get("scheduled_at")
        )

        cursor.execute("""
            INSERT INTO automations
            (id, name, prompt, cwds, schedule_type, rrule, scheduled_at, status, next_run)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            data["name"],
            data.get("prompt", ""),
            data.get("cwds", ""),
            data.get("schedule_type", "recurring"),
            data.get("rrule"),
            data.get("scheduled_at"),
            data.get("status", "ACTIVE"),
            next_run
        ))

        conn.commit()
        conn.close()

        return task_id

    def _get_all_automations(self) -> List[TaskInfo]:
        """获取所有自动化任务"""
        db_path = self.AUTOMATION_DB_PATTERN
        if not Path(db_path).exists():
            return []

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT id, name, prompt, cwds, schedule_type, rrule, scheduled_at,
                   status, last_run, next_run, created_at
            FROM automations
            ORDER BY created_at DESC
        """)

        tasks = [TaskInfo.from_row(row) for row in cursor.fetchall()]
        conn.close()

        return tasks

    def _delete_automation(self, task_id: str) -> bool:
        """删除自动化任务"""
        db_path = self.AUTOMATION_DB_PATTERN
        if not Path(db_path).exists():
            return False

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("DELETE FROM automations WHERE id = ?", (task_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted

    def _apply_filters(self, tasks: List[TaskInfo], filters: Dict[str, Any]) -> List[TaskInfo]:
        """应用过滤器"""
        result = tasks

        for key, value in filters.items():
            if key == "status":
                result = [t for t in result if t.status == value]
            elif key == "rrule":
                result = [t for t in result if t.rrule and value in t.rrule]
            elif key == "hour":
                result = [t for t in result if self._task_runs_at_hour(t, value)]
            elif key == "description":
                result = [t for t in result if value.lower() in t.name.lower() or value.lower() in t.prompt.lower()]

        return result

    def _task_runs_at_hour(self, task: TaskInfo, hour: int) -> bool:
        """检查任务是否在指定小时执行"""
        if not task.rrule:
            return False

        hour_match = re.search(r'BYHOUR=(\d+)', task.rrule)
        if hour_match:
            return int(hour_match.group(1)) == hour

        # 对于日频任务，检查 scheduled_at
        if task.scheduled_at:
            try:
                dt = datetime.fromisoformat(task.scheduled_at)
                return dt.hour == hour
            except:
                pass

        return False

    def _calculate_next_run(self, rrule: Optional[str], scheduled_at: Optional[str]) -> Optional[str]:
        """计算下次执行时间"""
        from datetime import timedelta

        if scheduled_at:
            try:
                dt = datetime.fromisoformat(scheduled_at)
                return dt.isoformat()
            except:
                pass

        if rrule:
            # 简化处理：返回当前时间 + 1小时
            return (datetime.now() + timedelta(hours=1)).isoformat()

        return None

    def _describe_rrule(self, rrule: str) -> str:
        """将 RRule 转换为人类可读的描述"""
        desc_map = {
            "DAILY": "每天",
            "WEEKLY": "每周",
            "MONTHLY": "每月",
            "MINUTELY": "每分钟",
            "HOURLY": "每小时",
        }

        # 提取频率
        freq_match = re.search(r'FREQ=(\w+)', rrule)
        freq = freq_match.group(1) if freq_match else ""

        # 提取间隔
        interval_match = re.search(r'INTERVAL=(\d+)', rrule)
        interval = interval_match.group(1) if interval_match else "1"

        # 提取星期
        day_match = re.search(r'BYDAY=([A-Z,]+)', rrule)
        day_map = {"MO": "周一", "TU": "周二", "WE": "周三", "TH": "周四", "FR": "周五", "SA": "周六", "SU": "周日"}
        day = ""
        if day_match:
            days = day_match.group(1).split(",")
            day = "".join(day_map.get(d, d) for d in days)

        # 提取小时
        hour_match = re.search(r'BYHOUR=(\d+)', rrule)
        hour = ""
        if hour_match:
            h = int(hour_match.group(1))
            hour = f"{h}点"

        # 组合描述
        unit = desc_map.get(freq, freq)
        if interval != "1":
            return f"{unit}每隔{interval}次"
        elif day:
            return f"{day}{hour}" if hour else f"{day}"
        elif hour:
            return f"每天{hour}"
        else:
            return unit

    def get_task_by_id(self, task_id: str) -> Optional[TaskInfo]:
        """根据ID获取任务"""
        db_path = self.AUTOMATION_DB_PATTERN
        if not Path(db_path).exists():
            return None

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT id, name, prompt, cwds, schedule_type, rrule, scheduled_at,
                   status, last_run, next_run, created_at
            FROM automations
            WHERE id = ?
        """, (task_id,))

        row = cursor.fetchone()
        conn.close()

        return TaskInfo.from_row(row) if row else None


# 便捷函数
def execute_schedule_command(text: str) -> Dict[str, Any]:
    """
    执行自然语言定时任务命令

    Examples:
        >>> result = execute_schedule_command("每天早上9点提醒我开会")
        >>> print(result["success"])  # True
        >>> print(result["task_id"])  # "a1b2c3d4"

        >>> result = execute_schedule_command("查看我的定时任务")
        >>> print(result["tasks"])  # [TaskInfo, ...]
    """
    executor = ScheduleCommandExecutor()
    return executor.execute(text)


if __name__ == "__main__":
    # 测试用例
    import sys

    test_cases = [
        "每天早上9点提醒我开会",
        "明天下午3点做报告",
        "每周一早上9点部门周会",
        "查看我的定时任务",
        "删除所有定时任务",
    ]

    print("=" * 60)
    print("定时任务命令执行器测试")
    print("=" * 60)

    executor = ScheduleCommandExecutor()

    for text in test_cases:
        print(f"\n📝 输入: {text}")
        result = executor.execute(text)
        print(f"   成功: {result['success']}")
        if result.get('message'):
            print(f"   消息:\n{result['message']}")
        if result.get('error'):
            print(f"   错误: {result['error']}")
        if result.get('tasks') is not None:
            print(f"   任务数: {len(result['tasks'])}")
