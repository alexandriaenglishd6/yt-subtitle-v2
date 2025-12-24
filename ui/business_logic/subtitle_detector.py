"""
字幕检测模块
负责检测视频字幕并保存检测结果
"""

from typing import List, Tuple, Optional, Callable
from pathlib import Path
from datetime import datetime

from core.models import VideoInfo
from core.detector import SubtitleDetector
from core.logger import get_logger
from core.failure_logger import _append_line_safe
from core.i18n import t

logger = get_logger()

# 常量定义
MAX_TITLE_DISPLAY_LENGTH = 50


class SubtitleDetectorMixin:
    """字幕检测 Mixin

    提供字幕检测相关的方法
    """

    def _detect_subtitles(
        self,
        videos: List[VideoInfo],
        on_log: Callable[[str, str, Optional[str]], None],
        source_url: Optional[str] = None,
        channel_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        dry_run: bool = False,
        on_stats: Optional[Callable[[dict, str], None]] = None,
        initial_total: Optional[int] = None,
        initial_failed: int = 0,
    ) -> Tuple[int, int]:
        """检测视频字幕（Dry Run 核心逻辑）

        Args:
            videos: 视频列表
            on_log: 日志回调
            source_url: 来源 URL（可选）
            channel_name: 频道名称（可选）
            channel_id: 频道 ID（可选）
            dry_run: 是否为 Dry Run 模式（Dry Run 模式下不写入文件）
            on_stats: 状态更新回调（可选）
            initial_total: 初始计划数量（可选，用于保持计划数不变）
            initial_failed: 初始失败数量（获取视频信息失败的数量）

        Returns:
            (有字幕数, 无字幕数)
        """
        detector = SubtitleDetector(cookie_manager=self.cookie_manager)
        has_subtitle_count = 0
        no_subtitle_count = initial_failed  # 从初始失败数开始计数
        # 使用初始计划数量，如果未提供则使用视频数量
        total_count = initial_total if initial_total is not None else len(videos)

        # 用于分类保存的列表
        videos_with_subtitle = []
        videos_without_subtitle = []

        try:
            on_log("INFO", t("detection_starting", count=len(videos)))
            # 初始化状态栏（使用 initial_failed 保持之前的失败计数）
            if on_stats:
                on_stats({"total": total_count, "success": 0, "failed": no_subtitle_count})
        except Exception as log_err:
            logger.error(f"on_log callback failed: {log_err}")

        for i, video in enumerate(videos, 1):
            # 检查取消状态
            if hasattr(self, 'cancel_token') and self.cancel_token and self.cancel_token.is_cancelled():
                on_log("INFO", t("log.cancel_signal_detected"))
                break
            
            try:
                result = detector.detect(video)
                progress_prefix = f"[{i}/{len(videos)}]"

                if result.has_subtitles:
                    has_subtitle_count += 1
                    videos_with_subtitle.append(video)
                    # 更新状态栏
                    if on_stats:
                        try:
                            on_stats({"total": total_count, "success": has_subtitle_count, "failed": no_subtitle_count})
                        except Exception:
                            pass

                    # 详细输出字幕信息 - 使用 try-except 保护 on_log 调用
                    try:
                        on_log(
                            "INFO",
                            f"{progress_prefix} ✓ {video.video_id} - {video.title[:MAX_TITLE_DISPLAY_LENGTH]}",
                            video_id=video.video_id,
                        )

                        # 显示手动字幕详情
                        if result.manual_languages:
                            manual_list = ", ".join(result.manual_languages)
                            on_log(
                                "INFO",
                                f"    {t('manual_subtitles')} ({len(result.manual_languages)}): {manual_list}",
                                video_id=video.video_id,
                            )

                        # 显示自动字幕详情
                        if result.auto_languages:
                            auto_list = ", ".join(result.auto_languages)
                            on_log(
                                "INFO",
                                f"    {t('auto_subtitles')} ({len(result.auto_languages)}): {auto_list}",
                                video_id=video.video_id,
                            )
                    except Exception as log_err:
                        logger.error(
                            f"on_log callback failed for video {video.video_id}: {log_err}"
                        )
                else:
                    no_subtitle_count += 1
                    videos_without_subtitle.append(video)
                    # 更新状态栏
                    if on_stats:
                        try:
                            on_stats({"total": total_count, "success": has_subtitle_count, "failed": no_subtitle_count})
                        except Exception:
                            pass
                    try:
                        on_log(
                            "WARN",
                            f"{progress_prefix} ✗ {video.video_id} - {video.title[:MAX_TITLE_DISPLAY_LENGTH]} - {t('no_subtitle_available')}",
                            video_id=video.video_id,
                        )
                    except Exception as log_err:
                        logger.error(
                            f"on_log callback failed for video {video.video_id}: {log_err}"
                        )
            except Exception as e:
                no_subtitle_count += 1
                videos_without_subtitle.append(video)
                # 更新状态栏
                if on_stats:
                    try:
                        on_stats({"total": total_count, "success": has_subtitle_count, "failed": no_subtitle_count})
                    except Exception:
                        pass
                try:
                    on_log(
                        "ERROR",
                        f"[{i}/{len(videos)}] ✗ {video.video_id} - {t('subtitle_detect_failed_short', error=str(e))}",
                        video_id=video.video_id,
                    )
                except Exception as log_err:
                    logger.error(f"on_log callback failed: {log_err}")

        # 保存分类结果到文件（使用传入的参数，Dry Run 模式下跳过）
        self._save_detection_results(
            videos_with_subtitle,
            videos_without_subtitle,
            on_log,
            source_url=source_url,
            channel_name=channel_name,
            channel_id=channel_id,
            dry_run=dry_run,
        )

        # 显示统计结果
        try:
            on_log("INFO", "=" * 50)
            on_log(
                "INFO",
                t(
                    "detection_complete",
                    has_count=has_subtitle_count,
                    no_count=no_subtitle_count,
                ),
            )
            on_log("INFO", "=" * 50)
        except Exception as log_err:
            logger.error(f"on_log callback failed for summary: {log_err}")

        return has_subtitle_count, no_subtitle_count

    def _save_detection_results(
        self,
        videos_with_subtitle: List[VideoInfo],
        videos_without_subtitle: List[VideoInfo],
        on_log: Callable[[str, str, Optional[str]], None],
        source_url: Optional[str] = None,
        channel_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        dry_run: bool = False,
    ):
        """保存检测结果到文件（追加模式，带分隔符）

        Args:
            videos_with_subtitle: 有字幕的视频列表
            videos_without_subtitle: 无字幕的视频列表
            on_log: 日志回调
            source_url: 来源 URL（可选）
            channel_name: 频道名称（可选）
            channel_id: 频道 ID（可选）
            dry_run: 是否为 Dry Run 模式（仅用于日志标记，不影响文件保存）

        说明：
        - Dry Run 模式下也会保存检测结果（with_subtitle.txt / without_subtitle.txt）
        - 这些文件是检测结果的记录，不属于"报告文件"，保存有助于用户了解检测情况
        - Dry Run 模式下仍然不会：下载字幕、翻译、摘要、更新 Archive
        """
        output_dir = Path(self.app_config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 固定文件名（追加模式）
        with_subtitle_file = output_dir / "with_subtitle.txt"
        without_subtitle_file = output_dir / "without_subtitle.txt"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建分隔符信息
        separator_parts = [f"# {timestamp}"]
        if dry_run:
            separator_parts.append("[Dry Run]")
        if channel_name and channel_id:
            separator_parts.append(f"{t('report_channel')}: {channel_name} [{channel_id}]")
        elif channel_id:
            separator_parts.append(f"{t('report_channel_id')}: {channel_id}")
        elif source_url:
            separator_parts.append(f"{t('report_source')}: {source_url}")
        separator_parts.append(
            f"{t('report_video_count')}: {len(videos_with_subtitle) + len(videos_without_subtitle)}"
        )
        separator = " | ".join(separator_parts)

        # 保存有字幕的视频链接（追加模式）
        if videos_with_subtitle:
            try:
                # 先写入分隔符和标题
                _append_line_safe(with_subtitle_file, "\n")
                _append_line_safe(with_subtitle_file, separator + "\n")
                _append_line_safe(
                    with_subtitle_file,
                    f"# {t('videos_with_subtitle')} ({len(videos_with_subtitle)} {t('count_unit')})\n",
                )
                _append_line_safe(with_subtitle_file, "\n")

                # 逐行写入视频 URL（使用线程安全的追加写入）
                for video in videos_with_subtitle:
                    _append_line_safe(with_subtitle_file, video.url + "\n")

                # 写入结束分隔符
                _append_line_safe(with_subtitle_file, "# " + "=" * 80 + "\n")
                _append_line_safe(with_subtitle_file, "\n")

                on_log(
                    "INFO",
                    t(
                        "saved_with_subtitle_file",
                        count=len(videos_with_subtitle),
                        filename=with_subtitle_file.name,
                    ),
                )
            except Exception as e:
                on_log(
                    "WARN",
                    t(
                        "save_file_failed",
                        filename=with_subtitle_file.name,
                        error=str(e),
                    ),
                )

        # 保存无字幕的视频链接（追加模式）
        if videos_without_subtitle:
            try:
                # 先写入分隔符和标题
                _append_line_safe(without_subtitle_file, "\n")
                _append_line_safe(without_subtitle_file, separator + "\n")
                _append_line_safe(
                    without_subtitle_file,
                    f"# {t('videos_without_subtitle')} ({len(videos_without_subtitle)} {t('count_unit')})\n",
                )
                _append_line_safe(without_subtitle_file, "\n")

                # 逐行写入视频 URL（使用线程安全的追加写入）
                for video in videos_without_subtitle:
                    _append_line_safe(without_subtitle_file, video.url + "\n")

                # 写入结束分隔符
                _append_line_safe(without_subtitle_file, "# " + "=" * 80 + "\n")
                _append_line_safe(without_subtitle_file, "\n")

                on_log(
                    "INFO",
                    t(
                        "saved_without_subtitle_file",
                        count=len(videos_without_subtitle),
                        filename=without_subtitle_file.name,
                    ),
                )
            except Exception as e:
                on_log(
                    "WARN",
                    t(
                        "save_file_failed",
                        filename=without_subtitle_file.name,
                        error=str(e),
                    ),
                )

    def _format_subtitle_info(self, result) -> str:
        """格式化字幕信息显示

        Args:
            result: 检测结果

        Returns:
            格式化的字幕信息字符串
        """
        subtitle_info_parts = []
        if result.manual_languages:
            manual_langs = ", ".join(result.manual_languages)
            subtitle_info_parts.append(f"{t('manual_subtitles')}：{manual_langs}")
        if result.auto_languages:
            auto_langs = ", ".join(result.auto_languages)
            subtitle_info_parts.append(f"{t('auto_subtitles')}：{auto_langs}")
        return " | ".join(subtitle_info_parts)
