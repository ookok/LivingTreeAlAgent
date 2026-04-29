"""
自然语言定时任务解析器
Natural Language Schedule Parser

支持自然语言创建、查询、删除定时任务
"""

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta


class ScheduleType(Enum):
    """调度类型"""
    ONCE = "once"           # 一次性任务
    RECURRING = "recurring" # 循环任务


class CommandType(Enum):
    """命令类型"""
    CREATE = "create"       # 创建任务
    QUERY = "query"        # 查询任务
    DELETE = "delete"       # 删除任务
    LIST = "list"          # 列出任务
    CANCEL = "cancel"      # 取消任务
    UNKNOWN = "unknown"    # 未知命令


@dataclass
class ParsedSchedule:
    """解析后的定时任务"""
    command: CommandType
    schedule_type: Optional[ScheduleType] = None

    # 创建任务专用
    time_expr: Optional[str] = None      # 原始时间表达式
    scheduled_at: Optional[str] = None   # ISO格式时间 (一次性)
    rrule: Optional[str] = None          # iCalendar规则 (循环)
    description: Optional[str] = None    # 任务描述

    # 查询/删除专用
    task_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

    # 原始输入
    original_text: str = ""

    # 解析状态
    confidence: float = 0.0
    error_message: Optional[str] = None

    def to_automation_dict(self) -> Dict[str, Any]:
        """转换为 automation_update 所需格式"""
        if self.command == CommandType.CREATE:
            result = {
                "name": self.description or f"定时任务_{self.time_expr}",
                "prompt": self.description or "执行定时任务",
                "cwds": "d:/mhzyapp/hermes-desktop",
                "status": "ACTIVE"
            }

            if self.schedule_type == ScheduleType.ONCE:
                result["scheduleType"] = "once"
                result["scheduledAt"] = self.scheduled_at
            else:
                result["scheduleType"] = "recurring"
                result["rrule"] = self.rrule

            return result

        elif self.command in [CommandType.QUERY, CommandType.LIST]:
            return {"filters": self.filters or {}}

        elif self.command == CommandType.DELETE:
            return {"task_id": self.task_id}

        return {}


class NLPScheduleParser:
    """
    自然语言定时任务解析器

    将自然语言转换为结构化的定时任务参数
    支持：
    - 创建："每天早上9点提醒我开会"、"明天下午3点做报告"
    - 查询："查看所有定时任务"、"我的定时任务有哪些"
    - 删除："删除下午3点的任务"、"删掉每天9点的提醒"
    """

    # 时间关键词映射
    TIME_KEYWORDS = {
        # 相对时间
        "今天": 0,
        "明天": 1,
        "后天": 2,
        "大后天": 3,

        # 早上/下午/晚上
        "早上": (0, 12),
        "上午": (0, 12),
        "中午": (11, 13),
        "下午": (12, 18),
        "晚上": (18, 24),
        "凌晨": (0, 6),

        # 星期
        "周一": "MO",
        "周二": "TU",
        "周三": "WE",
        "周四": "TH",
        "周五": "FR",
        "周六": "SA",
        "周日": "SU",
        "周末": ["SA", "SU"],
    }

    # 循环周期关键词
    RECURRENCE_KEYWORDS = {
        # 每日
        r"每?天": "DAILY",
        r"每天": "DAILY",
        r"每日": "DAILY",
        r"日复一日": "DAILY",

        # 每周
        r"每?周": "WEEKLY",
        r"每周": "WEEKLY",
        r"每周\d+次": "WEEKLY",  # 简化处理

        # 每月
        r"每?月": "MONTHLY",
        r"每月": "MONTHLY",
        r"每月初": "MONTHLY",
        r"每月末": "MONTHLY",

        # 工作日
        r"工作日": "WEEKLY;BYDAY=MO,TU,WE,TH,FR",

        # 间隔
        r"每隔?\d+分钟": "MINUTELY",
        r"每隔?\d+小时": "HOURLY",
        r"每隔?\d+天": "DAILY",
    }

    # 命令关键词
    CREATE_KEYWORDS = ["创建", "新建", "添加", "设置", "提醒", "安排", "定个"]
    QUERY_KEYWORDS = ["查看", "查询", "看看", "有哪些", "列出", "显示", "我的"]
    DELETE_KEYWORDS = ["删除", "删掉", "取消", "移除", "不要"]
    LIST_KEYWORDS = ["列表", "全部", "所有", "看看有哪些"]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """编译正则表达式"""
        # 时间模式: HH点MM分 或 HH点
        self.time_pattern = re.compile(r'(\d{1,2})\s*[点时]\s*(\d{1,2})?\s*[分]?')

        # 日期模式: YYYY年MM月DD日
        self.date_pattern = re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?')

        # 星期模式: 周一/周一到周五
        self.weekday_pattern = re.compile(r'周([一二三四五六日])')

        # 间隔模式: 每隔X分钟/小时/天
        self.interval_pattern = re.compile(r'每隔(\d+)\s*(分钟|分|小时|时|天|日)')

    def parse(self, text: str) -> ParsedSchedule:
        """
        解析自然语言输入

        Args:
            text: 用户输入的自然语言

        Returns:
            ParsedSchedule: 解析结果
        """
        text = text.strip()
        original = text

        # 1. 判断命令类型
        command = self._detect_command(text)
        parsed = ParsedSchedule(command=command, original_text=original)

        if command == CommandType.UNKNOWN:
            parsed.confidence = 0.0
            parsed.error_message = "无法理解您的意图，请尝试：'每天早上9点提醒我开会' 或 '查看我的定时任务'"
            return parsed

        # 2. 根据命令类型解析
        if command == CommandType.CREATE:
            self._parse_create_command(text, parsed)
        elif command == CommandType.QUERY or command == CommandType.LIST:
            self._parse_query_command(text, parsed)
        elif command == CommandType.DELETE:
            self._parse_delete_command(text, parsed)

        return parsed

    def _detect_command(self, text: str) -> CommandType:
        """检测命令类型"""
        # 删除优先检测
        if any(kw in text for kw in self.DELETE_KEYWORDS):
            # 检查是否同时有创建意图
            if any(kw in text for kw in ["新建", "创建", "添加"]):
                return CommandType.CREATE
            return CommandType.DELETE

        # 创建
        if any(kw in text for kw in self.CREATE_KEYWORDS):
            return CommandType.CREATE

        # 查询/列出
        if any(kw in text for kw in self.QUERY_KEYWORDS) or any(kw in text for kw in self.LIST_KEYWORDS):
            # 检查是否同时有删除意图
            if any(kw in text for kw in ["删除", "删掉", "取消"]):
                return CommandType.DELETE
            return CommandType.QUERY

        # 模糊检测 - 以时间开头可能是创建
        if self._looks_like_schedule(text):
            return CommandType.CREATE

        return CommandType.UNKNOWN

    def _looks_like_schedule(self, text: str) -> bool:
        """判断是否像定时任务描述"""
        schedule_indicators = [
            r'\d+点', r'\d+分',
            '每天', '每周', '每月',
            '早上', '上午', '下午', '晚上',
            '提醒', '通知', '开会', '报告'
        ]
        return any(re.search(p, text) for p in schedule_indicators)

    def _parse_create_command(self, text: str, parsed: ParsedSchedule):
        """解析创建命令"""
        # 1. 提取时间表达式
        time_expr, remaining = self._extract_time_expression(text)
        parsed.time_expr = time_expr

        # 2. 判断是循环还是一次性
        is_recurring, rrule = self._detect_recurrence(text)

        if is_recurring:
            parsed.schedule_type = ScheduleType.RECURRING
            parsed.rrule = rrule
            parsed.confidence = 0.95
        else:
            # 一次性任务
            scheduled_at = self._parse_scheduled_at(text, time_expr)
            if scheduled_at:
                parsed.schedule_type = ScheduleType.ONCE
                parsed.scheduled_at = scheduled_at
                parsed.confidence = 0.9
            else:
                parsed.confidence = 0.5
                parsed.error_message = "无法解析具体时间，请明确说明时间如'今天下午3点'"

        # 3. 提取任务描述
        parsed.description = self._extract_description(remaining or text)

    def _extract_time_expression(self, text: str) -> Tuple[Optional[str], str]:
        """提取时间表达式并返回剩余文本"""
        # 尝试匹配完整时间
        match = self.time_pattern.search(text)
        if match:
            hour = match.group(1)
            minute = match.group(2) or "00"
            time_str = f"{hour}:{minute.zfill(2)}"

            # 检查前面有时间修饰词
            before = text[:match.start()]

            # 查找今天/明天/早上/下午等
            day_offset = 0
            hour_modifier = None

            for kw, val in self.TIME_KEYWORDS.items():
                if kw in before:
                    if isinstance(val, int):
                        day_offset = val
                    elif isinstance(val, tuple):
                        hour_modifier = val
                    break

            # 构建时间表达式
            if day_offset > 0:
                time_expr = f"{'明天' if day_offset == 1 else f'{day_offset}天后'}{time_str}"
            elif hour_modifier:
                time_expr = f"今天{list(self.TIME_KEYWORDS.keys())[list(self.TIME_KEYWORDS.values()).index(hour_modifier)]}{time_str}"
            else:
                time_expr = f"今天{time_str}"

            # 返回剩余文本
            remaining = before + text[match.end():]
            return time_expr.strip(), remaining.strip()

        return None, text

    def _detect_recurrence(self, text: str) -> Tuple[bool, Optional[str]]:
        """检测循环类型"""
        now = datetime.now()

        # 检查循环关键词
        for pattern, freq in self.RECURRENCE_KEYWORDS.items():
            if re.search(pattern, text):
                # 构建完整 rrule
                if "INTERVAL" in freq:
                    interval = re.search(r'INTERVAL=(\d+)', freq)
                    if interval:
                        unit = freq.split(";")[0].replace("FREQ=", "")
                        count = interval.group(1)
                        return True, f"FREQ={unit};INTERVAL={count}"
                return True, f"FREQ={freq}"

        # 检查星期几
        weekday_match = self.weekday_pattern.search(text)
        if weekday_match:
            day_map = {"一": "MO", "二": "TU", "三": "WE", "四": "TH", "五": "FR", "六": "SA", "日": "SU"}
            day = day_map.get(weekday_match.group(1), "MO")
            return True, f"FREQ=WEEKLY;BYDAY={day}"

        # 检查是否包含"每天"
        if "每天" in text or "每日" in text:
            return True, "FREQ=DAILY"

        # 检查间隔
        interval_match = self.interval_pattern.search(text)
        if interval_match:
            count = interval_match.group(1)
            unit_map = {"分钟": "MINUTELY", "分": "MINUTELY", "小时": "HOURLY", "时": "HOURLY", "天": "DAILY", "日": "DAILY"}
            unit = unit_map.get(interval_match.group(2), "DAILY")
            return True, f"FREQ={unit};INTERVAL={count}"

        # 检查是否只说了"明天"、"今天"等，没有具体时间
        day_only = re.search(r'^(今天|明天|后天|大后天)\s*$', text)
        if day_only:
            return False, None

        return False, None

    def _parse_scheduled_at(self, text: str, time_expr: Optional[str]) -> Optional[str]:
        """解析一次性任务的执行时间"""
        now = datetime.now()

        # 今天/明天 + 时间
        today_tomorrow = re.search(r'(今天|明天|后天)\s*(\d{1,2})\s*[点时]\s*(\d{1,2})?\s*[分]?', text)
        if today_tomorrow:
            day_offset = {"今天": 0, "明天": 1, "后天": 2, "大后天": 3}[today_tomorrow.group(1)]
            hour = int(today_tomorrow.group(2))
            minute = int(today_tomorrow.group(3)) if today_tomorrow.group(3) else 0

            target = now + timedelta(days=day_offset)
            target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # 如果时间已过，移到明天
            if target <= now:
                target += timedelta(days=1)

            return target.isoformat()

        # 特定日期: YYYY年MM月DD日
        date_match = self.date_pattern.search(text)
        time_match = self.time_pattern.search(text)
        if date_match:
            year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            hour, minute = 9, 0
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0

            try:
                target = datetime(year, month, day, hour, minute)
                if target > now:
                    return target.isoformat()
            except ValueError:
                pass

        # 只有时间，没有日期 - 假设是今天或明天
        if time_expr and not any(kw in text for kw in ["今天", "明天", "后天"]):
            time_match = self.time_pattern.search(text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return target.isoformat()

        return None

    def _extract_description(self, text: str) -> str:
        """提取任务描述"""
        # 移除时间相关词汇
        patterns_to_remove = [
            r'每?\s*天', r'每?\s*周', r'每?\s*月',
            r'每?\s*分钟', r'每?\s*小时',
            r'每?\s*次',
            r'每?\s*个?\s*小时',
            r'今天', r'明天', r'后天', r'大后天',
            r'早上', r'上午', r'中午', r'下午', r'晚上', r'凌晨',
            r'\d{1,2}\s*[点时]\s*\d{0,2}\s*[分]?',
            r'\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?',
            r'周[一二三四五六日]',
            r'每隔?\d+\s*(分钟|分|小时|时|天|日)',
            r'创建', r'新建', r'添加', r'设置', r'提醒',
            r'定时', r'任务',
            r'^的?\s*', r'\s*$'
        ]

        result = text
        for pattern in patterns_to_remove:
            result = re.sub(pattern, '', result)

        # 移除多余空格
        result = re.sub(r'\s+', ' ', result).strip()

        return result or text

    def _parse_query_command(self, text: str, parsed: ParsedSchedule):
        """解析查询命令"""
        parsed.filters = {}

        # 按状态筛选
        if "进行中" in text or "激活" in text:
            parsed.filters["status"] = "ACTIVE"
        elif "已取消" in text or "停止" in text:
            parsed.filters["status"] = "PAUSED"
        elif "已完成" in text:
            parsed.filters["status"] = "COMPLETED"

        # 按类型筛选
        if "每天" in text or "每日" in text:
            parsed.filters["rrule"] = "FREQ=DAILY"
        elif "每周" in text:
            parsed.filters["rrule"] = "FREQ=WEEKLY"

        parsed.confidence = 0.9

    def _parse_delete_command(self, text: str, parsed: ParsedSchedule):
        """解析删除命令"""
        # 尝试提取任务ID
        id_match = re.search(r'[a-zA-Z0-9]{8,}', text)
        if id_match:
            parsed.task_id = id_match.group()
            parsed.confidence = 0.95
            return

        # 尝试通过描述匹配
        parsed.filters = {}
        if "每天" in text:
            parsed.filters["rrule"] = "FREQ=DAILY"
        elif "每周" in text:
            parsed.filters["rrule"] = "FREQ=WEEKLY"

        # 提取时间
        time_match = self.time_pattern.search(text)
        if time_match:
            parsed.filters["hour"] = int(time_match.group(1))
            if time_match.group(2):
                parsed.filters["minute"] = int(time_match.group(2))

        # 提取描述关键词
        desc = self._extract_description(text)
        if desc:
            parsed.filters["description"] = desc

        parsed.confidence = 0.7

    def generate_confirmation(self, parsed: ParsedSchedule) -> str:
        """生成确认信息"""
        if parsed.command == CommandType.CREATE:
            parts = ["确认创建定时任务："]

            if parsed.schedule_type == ScheduleType.ONCE:
                if parsed.scheduled_at:
                    dt = datetime.fromisoformat(parsed.scheduled_at)
                    parts.append(f"⏰ 执行时间：{dt.strftime('%Y-%m-%d %H:%M')}")
            else:
                parts.append(f"🔄 循环规则：{parsed.rrule}")

            if parsed.description:
                parts.append(f"📝 任务描述：{parsed.description}")

            return "\n".join(parts)

        elif parsed.command == CommandType.QUERY:
            return "🔍 正在查询定时任务..."

        elif parsed.command == CommandType.DELETE:
            if parsed.task_id:
                return f"🗑️ 确认删除任务 {parsed.task_id}？"
            else:
                return f"🗑️ 确认删除符合条件的所有任务？"

        return "❓ 无法理解您的意图"


def parse_schedule(text: str) -> ParsedSchedule:
    """
    便捷函数：解析自然语言定时任务

    Examples:
        >>> result = parse_schedule("每天早上9点提醒我开会")
        >>> print(result.schedule_type)  # RECURRING
        >>> print(result.rrule)  # FREQ=DAILY;BYHOUR=9

        >>> result = parse_schedule("明天下午3点做报告")
        >>> print(result.schedule_type)  # ONCE
        >>> print(result.scheduled_at)  # 2026-04-17T15:00:00
    """
    parser = NLPScheduleParser()
    return parser.parse(text)


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "每天早上9点提醒我开会",
        "明天下午3点做报告",
        "每周一早上9点部门周会",
        "每隔30分钟提醒我喝水",
        "查看我的定时任务",
        "删除每天9点的任务",
        "今天下午5点提醒我下班",
        "创建一个每天早上8点推送新闻的任务",
        "每周三下午2点Code Review",
        "删除所有定时任务",
    ]

    print("=" * 60)
    print("自然语言定时任务解析器测试")
    print("=" * 60)

    for text in test_cases:
        print(f"\n📝 输入: {text}")
        result = parse_schedule(text)
        print(f"   命令: {result.command.value}")
        print(f"   类型: {result.schedule_type.value if result.schedule_type else 'N/A'}")
        print(f"   置信度: {result.confidence:.2f}")
        if result.scheduled_at:
            print(f"   执行时间: {result.scheduled_at}")
        if result.rrule:
            print(f"   循环规则: {result.rrule}")
        if result.description:
            print(f"   描述: {result.description}")
        if result.error_message:
            print(f"   错误: {result.error_message}")
