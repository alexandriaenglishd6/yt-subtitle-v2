"""
YouTube URL 解析器模块
识别 URL 类型（视频/频道/播放列表）并提取 video_id
"""

import re
from typing import Optional


# YouTube URL 正则模式
YOUTUBE_PATTERNS = {
    "video": re.compile(
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
    ),
    "channel": re.compile(r"youtube\.com/(?:c/|user/|channel/|@)([^/?]+)"),
    "playlist": re.compile(r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)"),
}


def identify_url_type(url: str) -> str:
    """识别 YouTube URL 类型

    Args:
        url: YouTube URL

    Returns:
        URL 类型：'video', 'channel', 'playlist', 'unknown'
    """
    url_lower = url.lower()

    if "watch?v=" in url_lower or "youtu.be/" in url_lower:
        return "video"
    elif "playlist?list=" in url_lower:
        return "playlist"
    elif any(x in url_lower for x in ["/c/", "/user/", "/channel/", "/@"]):
        return "channel"
    else:
        return "unknown"


def extract_video_id(url: str) -> Optional[str]:
    """从 URL 中提取视频 ID

    Args:
        url: YouTube 视频 URL

    Returns:
        视频 ID，如果无法提取则返回 None
    """
    match = YOUTUBE_PATTERNS["video"].search(url)
    if match:
        return match.group(1)
    return None


def extract_playlist_id(url: str) -> Optional[str]:
    """从 URL 中提取播放列表 ID

    Args:
        url: YouTube 播放列表 URL

    Returns:
        播放列表 ID，如果无法提取则返回 None
    """
    match = YOUTUBE_PATTERNS["playlist"].search(url)
    if match:
        return match.group(1)
    return None


def extract_channel_id(url: str) -> Optional[str]:
    """从 URL 中提取频道标识

    Args:
        url: YouTube 频道 URL

    Returns:
        频道标识，如果无法提取则返回 None
    """
    match = YOUTUBE_PATTERNS["channel"].search(url)
    if match:
        return match.group(1)
    return None


def is_valid_youtube_url(url: str) -> bool:
    """检查是否为有效的 YouTube URL

    Args:
        url: URL 字符串

    Returns:
        是否为有效的 YouTube URL
    """
    return identify_url_type(url) != "unknown"
