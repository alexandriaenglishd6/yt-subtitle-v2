"""
任务运行模块
负责在后台线程中执行任务
"""

import threading
from typing import Optional, Callable

from core.logger import get_logger
from ui.i18n_manager import t

logger = get_logger()


class TaskRunnerMixin:
    """任务运行 Mixin

    提供任务运行相关的方法
    """

    def _run_task_in_thread(
        self,
        task_fn: Callable[[], None],
        on_status: Callable[[str], None],
        on_complete: Optional[Callable[[], None]] = None,
    ) -> threading.Thread:
        """在后台线程中执行任务

        Args:
            task_fn: 要执行的任务函数
            on_status: 状态回调
            on_complete: 完成回调

        Returns:
            启动的线程对象
        """

        def wrapper():
            try:
                task_fn()
            except Exception as e:
                import traceback

                logger.error(f"Task execution failed: {e}\n{traceback.format_exc()}")
                on_status(t("status_idle"))
            finally:
                if on_complete:
                    try:
                        on_complete()
                    except Exception as e:
                        logger.error(f"on_complete callback failed: {e}")
                on_status(t("status_idle"))

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return thread

    def dry_run(
        self,
        url: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_complete: Optional[Callable[[], None]] = None,
        force: bool = False,
    ):
        """执行 Dry Run（仅检测字幕）

        Args:
            url: 频道/播放列表 URL
            on_log: 日志回调 (level, message, video_id) - 必须在主线程中调用
            on_status: 状态更新回调 (status) - 必须在主线程中调用
            on_complete: 完成回调 - 必须在主线程中调用
        """

        def task():
            try:
                on_status(t("status_detecting"))
                on_log("INFO", t("dry_run_start", url=url))

                # 获取视频列表
                videos = self._fetch_videos(url, on_log, on_status)
                if not videos:
                    return

                # 保存视频列表到文件
                channel_name = videos[0].channel_name if videos else None
                channel_id = videos[0].channel_id if videos else None
                self._save_video_list(videos, url, channel_name, channel_id, on_log)

                on_log("INFO", t("videos_found", count=len(videos)))

                # 执行字幕检测（Dry Run 模式）
                channel_name = videos[0].channel_name if videos else None
                channel_id = videos[0].channel_id if videos else None
                self._detect_subtitles(
                    videos,
                    on_log,
                    source_url=url,
                    channel_name=channel_name,
                    channel_id=channel_id,
                    dry_run=True,
                )
            except Exception as e:
                import traceback

                error_msg = f"{t('dry_run_failed', error=str(e))}"
                logger.error(f"Dry Run failed: {e}\n{traceback.format_exc()}")
                on_log("ERROR", error_msg)

        return self._run_task_in_thread(task, on_status, on_complete)

    def process_videos(
        self,
        url: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_stats: Callable[[dict], None],
        on_complete: Optional[Callable[[], None]] = None,
        force: bool = False,
    ):
        """处理视频（下载、翻译、摘要）

        Args:
            url: 频道/播放列表 URL
            on_log: 日志回调 (level, message, video_id)
            on_status: 状态更新回调 (status)
            on_stats: 统计信息更新回调 (stats_dict)
            on_complete: 完成回调
        """

        def task():
            try:
                logger.info(f"[GUI] Processing task started, URL: {url}")
                on_status(t("status_processing"))
                on_log("INFO", t("processing_start", url=url))

                # 获取视频列表
                videos = self._fetch_videos(url, on_log, on_status)
                if not videos:
                    return

                logger.info(f"[GUI] Fetched {len(videos)} videos")

                # 保存视频列表到文件
                channel_name = videos[0].channel_name if videos else None
                channel_id = videos[0].channel_id if videos else None
                self._save_video_list(videos, url, channel_name, channel_id, on_log)

                on_log("INFO", t("videos_found", count=len(videos)))

                # 先执行字幕检测，显示详细列表
                self._detect_subtitles(
                    videos,
                    on_log,
                    source_url=url,
                    channel_name=channel_name,
                    channel_id=channel_id,
                )

                # 如果翻译 AI 初始化失败，提前提示
                if (
                    self.translation_llm_init_error
                    and self.app_config.translation_ai.enabled
                ):
                    error_msg = t(
                        "translation_ai_init_failed_skip",
                        error=self.translation_llm_init_error,
                    )
                    on_log("WARN", error_msg)

                # 执行完整处理流程
                on_log("INFO", t("processing_starting"))
                self._run_full_processing(videos, channel_id, on_log, on_stats, force)
            except Exception as e:
                import traceback

                error_msg = f"{t('processing_failed', error=str(e))}"
                logger.error(f"Processing failed: {e}\n{traceback.format_exc()}")
                on_log("ERROR", error_msg)

        return self._run_task_in_thread(task, on_status, on_complete)

    def stop_processing(self):
        """停止处理（由 GUI 的停止按钮调用）"""
        if self.cancel_token is not None:
            self.cancel_token.cancel(t("user_request_stop"))
            logger.info_i18n("user_request_stop")
        else:
            logger.warning_i18n("cancel_token_not_exists")

    def dry_run_url_list(
        self,
        urls_text: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_complete: Optional[Callable[[], None]] = None,
        force: bool = False,
    ):
        """执行 Dry Run（URL 列表模式）

        Args:
            urls_text: 多行 URL 文本（每行一个 URL）
            on_log: 日志回调
            on_status: 状态更新回调
            on_complete: 完成回调
        """

        def task():
            try:
                on_status(t("status_detecting"))
                on_log("INFO", t("dry_run_start_url_list"))

                # 获取视频列表
                videos = self._fetch_videos_from_url_list(urls_text, on_log, on_status)
                if not videos:
                    return

                # 保存视频列表到文件
                self._save_video_list(videos, t("url_list_source"), None, None, on_log)

                on_log("INFO", t("videos_found", count=len(videos)))

                # 执行字幕检测
                self._detect_subtitles(
                    videos,
                    on_log,
                    source_url=t("url_list_source"),
                    channel_name=None,
                    channel_id=None,
                    dry_run=True,
                )
            except Exception as e:
                import traceback

                error_msg = f"{t('dry_run_failed', error=str(e))}"
                logger.error(
                    f"Dry Run (URL list) failed: {e}\n{traceback.format_exc()}"
                )
                on_log("ERROR", error_msg)

        return self._run_task_in_thread(task, on_status, on_complete)

    def process_url_list(
        self,
        urls_text: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_stats: Callable[[dict], None],
        on_complete: Optional[Callable[[], None]] = None,
        force: bool = False,
    ):
        """处理视频列表（URL 列表模式）

        Args:
            urls_text: 多行 URL 文本（每行一个 URL）
            on_log: 日志回调
            on_status: 状态更新回调
            on_stats: 统计信息更新回调
            on_complete: 完成回调
        """

        def task():
            try:
                logger.info_i18n("gui_url_list_thread_started")
                on_status(t("status_processing"))
                on_log("INFO", t("processing_start_url_list"))

                # 获取视频列表
                videos = self._fetch_videos_from_url_list(urls_text, on_log, on_status)
                if not videos:
                    return

                logger.info_i18n("gui_videos_fetched", count=len(videos))

                # 保存视频列表到文件
                self._save_video_list(videos, t("url_list_source"), None, None, on_log)

                on_log("INFO", t("videos_found", count=len(videos)))

                # 先执行字幕检测，显示详细列表
                self._detect_subtitles(
                    videos,
                    on_log,
                    source_url=t("url_list_source"),
                    channel_name=None,
                    channel_id=None,
                    dry_run=True,
                )

                # 如果翻译 AI 初始化失败，提前提示
                if (
                    self.translation_llm_init_error
                    and self.app_config.translation_ai.enabled
                ):
                    error_msg = t(
                        "translation_ai_init_failed_skip",
                        error=self.translation_llm_init_error,
                    )
                    on_log("WARN", error_msg)

                # 执行完整处理流程（URL 列表模式使用批次 archive）
                on_log("INFO", t("processing_starting"))
                self._run_full_processing_url_list(videos, on_log, on_stats, force)
            except Exception as e:
                import traceback

                error_msg = f"{t('processing_failed', error=str(e))}"
                logger.error(
                    f"URL list processing failed: {e}\n{traceback.format_exc()}"
                )
                on_log("ERROR", error_msg)

        return self._run_task_in_thread(task, on_status, on_complete)
