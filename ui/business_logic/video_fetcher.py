"""
视频获取模块
负责从 URL 或 URL 列表获取视频信息
"""

from typing import Optional, List, Callable
from pathlib import Path
from datetime import datetime
import tempfile

from core.models import VideoInfo
from core.logger import get_logger
from core.i18n import t

logger = get_logger()

# 常量定义
MAX_TITLE_DISPLAY_LENGTH = 50


class VideoFetcherMixin:
    """视频获取 Mixin

    提供视频获取相关的方法
    """

    def _fetch_videos(
        self,
        url: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
    ) -> Optional[List[VideoInfo]]:
        """获取视频列表（公共方法）

        Args:
            url: 频道/播放列表 URL
            on_log: 日志回调
            on_status: 状态回调

        Returns:
            视频列表，如果失败则返回 None
        """
        on_log("INFO", t("fetching_videos"))
        try:
            videos = self.video_fetcher.fetch_from_url(url)
        except Exception as e:
            on_log("ERROR", t("fetch_videos_failed", error=str(e)))
            on_status(t("status_idle"))
            return None

        if not videos:
            on_log("WARN", t("no_videos_found"))
            on_status(t("status_idle"))
            return None

        return videos

    def _fetch_videos_from_url_list(
        self,
        urls_text: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
    ) -> Optional[List[VideoInfo]]:
        """从 URL 列表文本获取视频列表（公共方法）

        Args:
            urls_text: 多行 URL 文本（每行一个 URL）
            on_log: 日志回调
            on_status: 状态回调

        Returns:
            视频列表，如果失败则返回 None
        """
        on_log("INFO", t("fetching_videos"))

        # 将多行文本写入临时文件
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", delete=False, suffix=".txt"
            ) as f:
                # 解析多行文本，每行一个 URL
                urls = [line.strip() for line in urls_text.split("\n") if line.strip()]
                if not urls:
                    on_log("WARN", t("url_list_empty"))
                    on_status(t("status_idle"))
                    return None

                for url in urls:
                    f.write(url + "\n")
                temp_file_path = Path(f.name)

            try:
                # 将 cancel_token 传递给 video_fetcher（用于取消支持）
                if hasattr(self, 'cancel_token'):
                    self.video_fetcher.cancel_token = self.cancel_token
                videos = self.video_fetcher.fetch_from_file(temp_file_path)
            finally:
                # 清理临时文件
                try:
                    temp_file_path.unlink()
                except Exception:
                    pass

            if not videos:
                on_log("WARN", t("no_videos_found"))
                on_status(t("status_idle"))
                return None

            return videos
        except Exception as e:
            on_log("ERROR", t("fetch_videos_failed", error=str(e)))
            on_status(t("status_idle"))
            return None

    def _save_video_list(
        self,
        videos: List[VideoInfo],
        source_url: str,
        channel_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        on_log: Optional[Callable] = None,
    ):
        """保存视频列表到文件（追加模式）"""
        try:
            output_dir = Path(self.app_config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            video_list_file = output_dir / "video_list.txt"

            # 构建分隔符
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            separator_parts = [f"# {timestamp}"]

            if channel_name and channel_id:
                separator_parts.append(f"Channel: {channel_name} [{channel_id}]")
            elif channel_id:
                separator_parts.append(f"Channel ID: {channel_id}")
            else:
                separator_parts.append(f"Source: {source_url}")

            separator_parts.append(f"Count: {len(videos)}")
            separator = " | ".join(separator_parts)

            # 追加模式写入
            with open(video_list_file, "a", encoding="utf-8") as f:
                f.write("\n")
                f.write(separator + "\n")
                for video in videos:
                    f.write(video.url + "\n")
                f.write("# " + "=" * 60 + "\n")

            logger.info(
                t("video_list_saved", count=len(videos), filename=video_list_file.name)
            )
            if on_log:
                on_log(
                    "INFO",
                    t(
                        "video_list_saved",
                        count=len(videos),
                        filename=video_list_file.name,
                    ),
                )
        except Exception as e:
            logger.error(t("save_video_list_failed", error=str(e)))
            if on_log:
                on_log("WARN", t("save_video_list_failed", error=str(e)))
