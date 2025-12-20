"""
YouTube 视频章节模块

提取和输出 YouTube 视频章节信息
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class VideoChapter:
    """视频章节

    Attributes:
        title: 章节标题
        start_time: 开始时间（秒）
        end_time: 结束时间（秒，可选）
    """
    title: str
    start_time: float
    end_time: Optional[float] = None

    def format_timestamp(self, seconds: float) -> str:
        """格式化时间戳为 HH:MM:SS 或 MM:SS 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @property
    def start_formatted(self) -> str:
        """格式化的开始时间"""
        return self.format_timestamp(self.start_time)

    @property
    def end_formatted(self) -> Optional[str]:
        """格式化的结束时间"""
        if self.end_time is not None:
            return self.format_timestamp(self.end_time)
        return None

    @property
    def duration_seconds(self) -> Optional[float]:
        """章节时长（秒）"""
        if self.end_time is not None:
            return self.end_time - self.start_time
        return None


@dataclass
class ChapterList:
    """章节列表

    Attributes:
        video_id: 视频 ID
        video_title: 视频标题
        chapters: 章节列表
    """
    video_id: str
    video_title: str
    chapters: List[VideoChapter] = field(default_factory=list)

    @property
    def has_chapters(self) -> bool:
        """是否有章节"""
        return len(self.chapters) > 0

    @property
    def chapter_count(self) -> int:
        """章节数量"""
        return len(self.chapters)

    def to_markdown(self, include_header: bool = True) -> str:
        """转换为 Markdown 格式

        Args:
            include_header: 是否包含标题头

        Returns:
            Markdown 格式的章节列表
        """
        lines = []

        if include_header:
            lines.append(f"# {self.video_title}")
            lines.append("")
            lines.append("## 章节 / Chapters")
            lines.append("")

        if not self.chapters:
            lines.append("*No chapters available / 无章节信息*")
            return "\n".join(lines)

        # 生成章节列表
        for i, chapter in enumerate(self.chapters, 1):
            timestamp = chapter.start_formatted
            # 格式：序号. [时间戳] 标题
            lines.append(f"{i}. **[{timestamp}]** {chapter.title}")

        return "\n".join(lines)

    def to_markdown_table(self) -> str:
        """转换为 Markdown 表格格式

        Returns:
            Markdown 表格格式的章节列表
        """
        lines = [
            "| # | Start | End | Title |",
            "|---|-------|-----|-------|",
        ]

        for i, chapter in enumerate(self.chapters, 1):
            start = chapter.start_formatted
            end = chapter.end_formatted or "-"
            title = chapter.title.replace("|", "\\|")  # 转义管道符
            lines.append(f"| {i} | {start} | {end} | {title} |")

        return "\n".join(lines)


def extract_chapters_from_ytdlp(info_dict: Dict[str, Any]) -> ChapterList:
    """从 yt-dlp 的 info_dict 中提取章节信息

    Args:
        info_dict: yt-dlp --dump-json 的输出

    Returns:
        ChapterList 对象
    """
    video_id = info_dict.get("id", "unknown")
    video_title = info_dict.get("title", "Unknown Title")

    chapters_data = info_dict.get("chapters", [])

    chapters = []
    for ch in chapters_data:
        chapter = VideoChapter(
            title=ch.get("title", "Untitled"),
            start_time=ch.get("start_time", 0),
            end_time=ch.get("end_time"),
        )
        chapters.append(chapter)

    result = ChapterList(
        video_id=video_id,
        video_title=video_title,
        chapters=chapters,
    )

    if result.has_chapters:
        logger.info(f"Extracted {result.chapter_count} chapters for {video_id}")
    else:
        logger.debug(f"No chapters found for {video_id}")

    return result


def write_chapters_markdown(
    chapter_list: ChapterList,
    output_dir: Path,
    filename: str = "chapters.md",
) -> Optional[Path]:
    """将章节信息写入 Markdown 文件

    Args:
        chapter_list: 章节列表
        output_dir: 输出目录
        filename: 文件名

    Returns:
        写入的文件路径，如果无章节则返回 None
    """
    if not chapter_list.has_chapters:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    content = chapter_list.to_markdown()

    try:
        # 原子写入
        tmp_path = output_path.with_suffix(".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        import os
        os.replace(tmp_path, output_path)
        logger.info(f"Chapters written to {output_path}")
        return output_path
    except (OSError, IOError) as e:
        logger.error(f"Failed to write chapters: {e}")
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None
