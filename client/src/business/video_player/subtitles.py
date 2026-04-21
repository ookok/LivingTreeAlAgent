# -*- coding: utf-8 -*-
"""
字幕管理模块
支持 SRT、SSA/ASS、SUB 等格式的字幕加载和切换
"""

import os
import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import chardet

logger = logging.getLogger(__name__)


class SubtitleType(Enum):
    """字幕类型"""
    UNKNOWN = "unknown"
    SRT = "srt"
    SSA = "ssa"
    ASS = "ass"
    SUB = "sub"
    WEBVTT = "vtt"


@dataclass
class SubtitleCue:
    """
    字幕条目

    Attributes:
        index: 序号
        start_time: 开始时间（秒）
        end_time: 结束时间（秒）
        text: 字幕文本
        style: 样式（ASS/SSA 专用）
    """
    index: int
    start_time: float
    end_time: float
    text: str
    style: str = ""

    def get_time_range(self) -> str:
        """获取时间范围字符串"""
        return f"{self._format_time(self.start_time)} --> {self._format_time(self.end_time)}"

    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间为 SRT 格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


@dataclass
class SubtitleTrack:
    """
    字幕轨道

    Attributes:
        id: 轨道 ID
        name: 轨道名称
        language: 语言代码 (ISO 639-1)
        path: 字幕文件路径
        subtitle_type: 字幕类型
        encoding: 字符编码
        cues: 字幕条目列表
    """
    id: str
    name: str
    language: str = ""
    path: str = ""
    subtitle_type: SubtitleType = SubtitleType.UNKNOWN
    encoding: str = "UTF-8"
    cues: List[SubtitleCue] = field(default_factory=list)
    external: bool = False  # 是否为外部字幕


class SubtitleManager:
    """
    字幕管理器

    支持:
    - 自动检测字幕编码
    - 解析 SRT、SSA/ASS、SUB 格式
    - 字幕轨道切换
    - 字幕延迟调整
    - 字幕搜索
    """

    # 常用编码列表（按优先级）
    ENCODING_PRIORITY = ["UTF-8", "UTF-8-BOM", "UTF-16", "UTF-16LE", "UTF-16BE",
                         "GB2312", "GBK", "GB18030", "BIG5", "SHIFT-JIS",
                         "ISO-8859-1", "Windows-1252"]

    def __init__(self):
        self._tracks: List[SubtitleTrack] = []
        self._current_track: Optional[SubtitleTrack] = None
        self._delay_ms: float = 0.0  # 字幕延迟（毫秒）

    def detect_encoding(self, path: str) -> str:
        """
        自动检测文件编码

        Args:
            path: 文件路径

        Returns:
            编码名称
        """
        # 先尝试检测
        try:
            with open(path, "rb") as f:
                raw = f.read(8192)
                result = chardet.detect(raw)
                if result and result.get("encoding"):
                    encoding = result["encoding"]
                    # 规范化编码名称
                    encoding = self._normalize_encoding(encoding)
                    if encoding:
                        logger.debug(f"检测到编码: {encoding} (置信度: {result.get('confidence', 0):.2f})")
                        return encoding
        except Exception as e:
            logger.debug(f"编码检测失败: {e}")

        # 默认返回 UTF-8
        return "UTF-8"

    @staticmethod
    def _normalize_encoding(encoding: str) -> str:
        """规范化编码名称"""
        if not encoding:
            return ""

        encoding = encoding.upper().replace("-", "").replace("_", "")

        mapping = {
            "UTF8": "UTF-8",
            "UTF8BOM": "UTF-8-BOM",
            "UTF16": "UTF-16",
            "UTF16LE": "UTF-16LE",
            "UTF16BE": "UTF-16BE",
            "GB2312": "GB2312",
            "GBK": "GBK",
            "GB18030": "GB18030",
            "BIG5": "BIG5",
            "SHIFTJIS": "SHIFT-JIS",
            "ISO88591": "ISO-8859-1",
            "WINDOWS1252": "Windows-1252",
        }

        return mapping.get(encoding, encoding)

    def load_subtitle(self, path: str, name: str = "", language: str = "") -> Optional[SubtitleTrack]:
        """
        加载字幕文件

        Args:
            path: 字幕文件路径
            name: 自定义名称
            language: 语言代码

        Returns:
            SubtitleTrack 或 None
        """
        if not os.path.exists(path):
            logger.error(f"字幕文件不存在: {path}")
            return None

        # 检测编码
        encoding = self.detect_encoding(path)

        # 检测类型
        subtitle_type = self._detect_type(path)

        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                content = f.read()

            # 解析字幕
            if subtitle_type == SubtitleType.SRT:
                cues = self._parse_srt(content)
            elif subtitle_type in (SubtitleType.SSA, SubtitleType.ASS):
                cues = self._parse_ssa(content)
            elif subtitle_type == SubtitleType.SUB:
                cues = self._parse_sub(content)
            elif subtitle_type == SubtitleType.WEBVTT:
                cues = self._parse_vtt(content)
            else:
                cues = self._parse_srt(content)  # 尝试当作 SRT 解析

            # 创建轨道
            track = SubtitleTrack(
                id=os.path.basename(path),
                name=name or os.path.splitext(os.path.basename(path))[0],
                language=language,
                path=path,
                subtitle_type=subtitle_type,
                encoding=encoding,
                cues=cues,
                external=True
            )

            self._tracks.append(track)
            logger.info(f"字幕加载成功: {track.name} ({len(cues)} 条)")

            return track

        except Exception as e:
            logger.error(f"字幕加载失败: {e}")
            return None

    def _detect_type(self, path: str) -> SubtitleType:
        """根据扩展名检测字幕类型"""
        ext = os.path.splitext(path)[1].lower()
        mapping = {
            ".srt": SubtitleType.SRT,
            ".ssa": SubtitleType.SSA,
            ".ass": SubtitleType.ASS,
            ".sub": SubtitleType.SUB,
            ".vtt": SubtitleType.WEBVTT,
        }
        return mapping.get(ext, SubtitleType.UNKNOWN)

    def _parse_srt(self, content: str) -> List[SubtitleCue]:
        """解析 SRT 格式"""
        cues = []
        # 分割字幕块
        pattern = r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n([\s\S]*?)(?=\n\n\d+\s*\n|\Z)"
        matches = re.findall(pattern, content, re.UNICODE)

        for match in matches:
            index = int(match[0])
            start = self._parse_srt_time(match[1])
            end = self._parse_srt_time(match[2])
            text = match[3].strip()

            # 清理 HTML 标签
            text = re.sub(r"<[^>]+>", "", text)

            cues.append(SubtitleCue(index, start, end, text))

        return cues

    @staticmethod
    def _parse_srt_time(time_str: str) -> float:
        """解析 SRT 时间字符串"""
        match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", time_str)
        if match:
            h, m, s, ms = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        return 0.0

    def _parse_ssa(self, content: str) -> List[SubtitleCue]:
        """解析 SSA/ASS 格式"""
        cues = []
        lines = content.split("\n")
        in_events = False
        format_keys = []
        index = 0

        for line in lines:
            line = line.strip()

            if line.startswith("[Events]"):
                in_events = True
                continue

            if in_events:
                if line.startswith("Format:"):
                    # 解析格式行
                    format_keys = [k.strip().lower() for k in line[7:].split(",")]
                    continue

                if line.startswith("Dialogue:"):
                    # 解析对话行
                    values = line[9:].split(",", len(format_keys) - 1)
                    if len(values) >= len(format_keys):
                        data = dict(zip(format_keys, [v.strip() for v in values]))

                        start = self._parse_ass_time(data.get("start", "0:00:00."))
                        end = self._parse_ass_time(data.get("end", "0:00:00."))
                        text = data.get("text", "")

                        # 处理 ASS 样式
                        style = data.get("style", "")

                        # 清理 ASS 标签
                        text = re.sub(r"\{[^}]*\}", "", text)
                        text = text.replace("\\N", "\n").replace("\\n", "\n")

                        index += 1
                        cues.append(SubtitleCue(index, start, end, text, style))

        return cues

    @staticmethod
    def _parse_ass_time(time_str: str) -> float:
        """解析 ASS 时间字符串"""
        match = re.match(r"(\d+):(\d{2}):(\d{2})\.(\d{2})", time_str)
        if match:
            h, m, s, cs = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
        return 0.0

    def _parse_sub(self, content: str) -> List[SubtitleCue]:
        """解析 MicroDVD SUB 格式"""
        cues = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # SUB 格式: {frame_start}{frame_end}text
            match = re.match(r"\{(\d+)\}\{(\d+)\}(.+)", line)
            if match:
                start_frame = int(match.group(1))
                end_frame = int(match.group(2))
                text = match.group(3)

                # 假设 25 fps
                fps = 25.0
                start = start_frame / fps
                end = end_frame / fps

                cues.append(SubtitleCue(i + 1, start, end, text))

        return cues

    def _parse_vtt(self, content: str) -> List[SubtitleCue]:
        """解析 WebVTT 格式"""
        cues = []
        lines = content.split("\n")
        i = 0

        # 跳过 WEBVTT 头
        while i < len(lines) and "WEBVTT" not in lines[i]:
            i += 1

        i += 1  # 跳过 WEBVTT 行
        index = 0

        while i < len(lines):
            line = lines[i].strip()

            # 时间行
            if "-->" in line:
                time_match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})", line)
                if time_match:
                    start = self._parse_vtt_time(time_match.group(1))
                    end = self._parse_vtt_time(time_match.group(2))

                    # 收集文本行
                    i += 1
                    text_lines = []
                    while i < len(lines) and lines[i].strip() and not "-->" in lines[i]:
                        text_lines.append(lines[i].strip())
                        i += 1

                    text = " ".join(text_lines)
                    # 清理标签
                    text = re.sub(r"<[^>]+>", "", text)

                    index += 1
                    cues.append(SubtitleCue(index, start, end, text))
                    continue

            i += 1

        return cues

    @staticmethod
    def _parse_vtt_time(time_str: str) -> float:
        """解析 VTT 时间字符串"""
        match = re.match(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})", time_str)
        if match:
            h, m, s, ms = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        return 0.0

    # 字幕轨道管理

    def get_tracks(self) -> List[SubtitleTrack]:
        """获取所有字幕轨道"""
        return self._tracks.copy()

    def add_track(self, track: SubtitleTrack):
        """添加字幕轨道"""
        if track not in self._tracks:
            self._tracks.append(track)

    def remove_track(self, track_id: str) -> bool:
        """移除字幕轨道"""
        for i, track in enumerate(self._tracks):
            if track.id == track_id:
                self._tracks.pop(i)
                if self._current_track and self._current_track.id == track_id:
                    self._current_track = None
                return True
        return False

    def set_current_track(self, track: Optional[SubtitleTrack]):
        """设置当前字幕轨道"""
        self._current_track = track

    def get_current_track(self) -> Optional[SubtitleTrack]:
        """获取当前字幕轨道"""
        return self._current_track

    def get_track_by_language(self, language: str) -> Optional[SubtitleTrack]:
        """通过语言代码获取字幕轨道"""
        for track in self._tracks:
            if track.language.lower() == language.lower():
                return track
        return None

    # 延迟控制

    def set_delay(self, delay_ms: float):
        """设置字幕延迟（毫秒）"""
        self._delay_ms = delay_ms

    def get_delay(self) -> float:
        """获取字幕延迟（毫秒）"""
        return self._delay_ms

    def shift_delay(self, delta_ms: float):
        """调整字幕延迟"""
        self._delay_ms += delta_ms

    # 搜索

    def search(self, query: str, case_sensitive: bool = False) -> List[Tuple[SubtitleTrack, SubtitleCue]]:
        """
        搜索字幕内容

        Args:
            query: 搜索关键词
            case_sensitive: 是否区分大小写

        Returns:
            (轨道, 匹配的字幕条目) 列表
        """
        results = []
        q = query if case_sensitive else query.lower()

        for track in self._tracks:
            for cue in track.cues:
                text = cue.text if case_sensitive else cue.text.lower()
                if q in text:
                    results.append((track, cue))

        return results

    def get_cue_at_time(self, time: float) -> Optional[SubtitleCue]:
        """
        获取指定时间的字幕

        Args:
            time: 时间（秒）

        Returns:
            匹配的 SubtitleCue 或 None
        """
        if not self._current_track:
            return None

        adjusted_time = time + self._delay_ms / 1000.0

        for cue in self._current_track.cues:
            if cue.start_time <= adjusted_time <= cue.end_time:
                return cue

        return None

    # 导出

    def export_to_srt(self, track: SubtitleTrack, output_path: str) -> bool:
        """
        导出字幕为 SRT 格式

        Args:
            track: 字幕轨道
            output_path: 输出路径

        Returns:
            是否成功
        """
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for cue in track.cues:
                    f.write(f"{cue.index}\n")
                    f.write(f"{cue.get_time_range()}\n")
                    f.write(f"{cue.text}\n\n")
            return True
        except Exception as e:
            logger.error(f"导出字幕失败: {e}")
            return False

    def clear(self):
        """清空所有字幕轨道"""
        self._tracks.clear()
        self._current_track = None
