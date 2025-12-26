"""
版本检查模块
启动时检查 GitHub 最新版本，提示用户更新
"""

import threading
import webbrowser
from typing import Optional, Callable
import urllib.request
import json

from core.logger import get_logger

logger = get_logger()

# 当前版本
CURRENT_VERSION = "1.0.1"

# GitHub API 地址
GITHUB_API_URL = "https://api.github.com/repos/alexandriaenglishd6/yt-subtitle-v2/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/alexandriaenglishd6/yt-subtitle-v2/releases"


def parse_version(version_str: str) -> tuple:
    """解析版本号为元组，用于比较"""
    # 移除 'v' 前缀
    version_str = version_str.lstrip("v")
    try:
        parts = version_str.split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def is_newer_version(latest: str, current: str) -> bool:
    """判断是否有新版本"""
    return parse_version(latest) > parse_version(current)


def check_for_updates(
    on_update_available: Optional[Callable[[str, str], None]] = None,
    on_no_update: Optional[Callable[[], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
):
    """
    异步检查更新
    
    Args:
        on_update_available: 有新版本时的回调 (latest_version, release_notes)
        on_no_update: 已是最新版本时的回调
        on_error: 检查失败时的回调 (error_message)
    """
    def _check():
        try:
            # 创建请求
            request = urllib.request.Request(
                GITHUB_API_URL,
                headers={
                    "User-Agent": "YT-Subtitle-Tool",
                    "Accept": "application/vnd.github.v3+json",
                }
            )
            
            # 发送请求（超时 5 秒）
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            latest_version = data.get("tag_name", "").lstrip("v")
            release_notes = data.get("body", "")
            
            if is_newer_version(latest_version, CURRENT_VERSION):
                logger.info(f"发现新版本: v{latest_version}")
                if on_update_available:
                    on_update_available(latest_version, release_notes)
            else:
                logger.debug(f"当前已是最新版本: v{CURRENT_VERSION}")
                if on_no_update:
                    on_no_update()
                    
        except Exception as e:
            error_msg = str(e)
            logger.debug(f"版本检查失败: {error_msg}")
            if on_error:
                on_error(error_msg)
    
    # 在后台线程执行，不阻塞 UI
    thread = threading.Thread(target=_check, daemon=True)
    thread.start()


def open_releases_page():
    """打开 GitHub Releases 页面"""
    webbrowser.open(GITHUB_RELEASES_URL)


def get_current_version() -> str:
    """获取当前版本号"""
    return CURRENT_VERSION
