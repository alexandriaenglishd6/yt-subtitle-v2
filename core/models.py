"""
数据模型（VideoInfo、DetectionResult 等）
数据模型定义
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class VideoInfo:
    """视频信息模型

    标准化的视频信息结构，用于在整个流水线中传递
    """

    video_id: str  # 视频 ID（如 "dQw4w9WgXcQ"）
    url: str  # 完整 URL
    title: str  # 视频标题
    channel_id: Optional[str] = None  # 频道 ID（如 "UCxxxxxx"）
    channel_name: Optional[str] = None  # 频道名称
    duration: Optional[int] = None  # 视频时长（秒）
    upload_date: Optional[str] = None  # 上传日期（YYYYMMDD 格式）
    description: Optional[str] = None  # 视频描述（可选）

    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.video_id} - {self.title}"


@dataclass
class DetectionResult:
    """字幕检测结果模型

    用于记录单个视频的字幕检测结果
    """

    video_id: str  # 视频 ID
    has_subtitles: bool  # 是否有字幕
    manual_languages: List[str]  # 人工字幕语言列表（如 ["en", "zh-CN"]）
    auto_languages: List[str]  # 自动字幕语言列表（如 ["en", "ja"]）
    chapters: List[Dict[str, Any]] = field(default_factory=list)  # 视频章节列表
    # 原始字幕 URL 信息，格式：{lang_code: [{"ext": "vtt", "url": "..."}, ...]}
    subtitle_urls: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    auto_subtitle_urls: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def __str__(self) -> str:
        """字符串表示"""
        manual = ", ".join(self.manual_languages) if self.manual_languages else "无"
        auto = ", ".join(self.auto_languages) if self.auto_languages else "无"
        return f"视频 {self.video_id}: 人工字幕={manual}, 自动字幕={auto}"

