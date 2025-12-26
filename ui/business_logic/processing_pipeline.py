"""
处理流程模块
负责执行完整的视频处理流程（下载、翻译、摘要）
"""

from typing import List, Optional, Callable

from core.logger import get_logger
from core.pipeline import process_video_list
from core.cancel_token import CancelToken
from core.models import VideoInfo
from core.exceptions import ErrorType
from core.i18n import t

logger = get_logger()


class ProcessingPipelineMixin:
    """处理流程 Mixin

    提供处理流程相关的方法
    """

    def _run_full_processing(
        self,
        videos: List[VideoInfo],
        channel_id: Optional[str],
        on_log: Callable[[str, str, Optional[str]], None],
        on_stats: Callable[[dict], None],
        force: bool = False,
    ):
        """执行完整处理流程（下载、翻译、摘要）

        Args:
            videos: 视频列表
            channel_id: 频道 ID
            on_log: 日志回调
            on_stats: 统计回调
        """
        # 重置取消令牌（开始新的处理任务）
        self.cancel_token = CancelToken()

        # 获取 archive 路径（用于增量处理）
        archive_path = self.incremental_manager.get_or_create_channel_archive(
            channel_id
        )

        # 初始化统计信息
        stats = {"total": len(videos), "success": 0, "failed": 0, "current": 0}
        on_stats(stats)

        on_log("INFO", t("videos_found", count=len(videos)))
        on_log(
            "INFO",
            t(
                "log.task_start",
                total=len(videos),
                concurrency=self.app_config.concurrency,
                ai_concurrency=self.app_config.ai_concurrency,
            ),
        )

        # 调用核心流水线
        result = process_video_list(
            videos=videos,
            language_config=self.app_config.language,
            translation_llm=self.translation_llm_client,
            summary_llm=self.summary_llm_client,
            output_writer=self.output_writer,
            failure_logger=self.failure_logger,
            incremental_manager=self.incremental_manager,
            archive_path=archive_path,
            force=force,
            dry_run=False,  # 正常处理模式，不是 Dry Run
            cancel_token=self.cancel_token,  # 传递取消令牌
            concurrency=self.app_config.concurrency,
            ai_concurrency=self.app_config.ai_concurrency,
            proxy_manager=self.proxy_manager,
            cookie_manager=self.cookie_manager,
            on_stats=on_stats,
            on_log=on_log,
            on_error=self._handle_pipeline_error,
            translation_llm_init_error_type=self.translation_llm_init_error_type,  # 传递初始化失败的错误类型
            translation_llm_init_error=self.translation_llm_init_error,  # 传递初始化失败的错误信息
        )

        # 更新最终统计信息（包含错误分类）
        stats["success"] = result.get("success", 0)
        stats["failed"] = result.get("failed", 0)
        stats["current"] = stats["total"]
        stats["error_counts"] = result.get("error_counts", {})  # 错误分类统计
        on_stats(stats)

        # 显示完成消息
        self._log_processing_complete(stats, result, on_log)

    def _run_full_processing_url_list(
        self,
        videos: List[VideoInfo],
        on_log: Callable[[str, str, Optional[str]], None],
        on_stats: Callable[[dict], None],
        force: bool = False,
        initial_url_count: int = 0,  # 初始 URL 数量
        fetch_failed_count: int = 0,  # URL 获取阶段失败的数量
    ):
        """执行完整处理流程（URL 列表模式，使用批次 archive）

        Args:
            videos: 视频列表
            on_log: 日志回调
            on_stats: 统计回调
            initial_url_count: 初始 URL 数量（用于保持 total 不变）
            fetch_failed_count: URL 获取阶段失败的数量
        """
        # cancel_token 已经在主线程的 process_url_list 中创建，这里不再重复创建

        # URL 列表模式使用批次 archive（不区分频道）
        archive_path = self.incremental_manager.get_batch_archive_path()

        # 使用实际视频数量作为 total（不再使用 URL 数量）
        actual_video_count = len(videos)
        
        # 初始化统计信息（使用实际视频数量）
        stats = {"total": actual_video_count, "success": 0, "failed": 0, "current": 0}
        on_stats(stats)

        on_log("INFO", t("videos_found", count=len(videos)))
        on_log(
            "INFO",
            t(
                "log.task_start",
                total=len(videos),
                concurrency=self.app_config.concurrency,
                ai_concurrency=self.app_config.ai_concurrency,
            ),
        )

        # 调用核心流水线
        result = process_video_list(
            videos=videos,
            language_config=self.app_config.language,
            translation_llm=self.translation_llm_client,
            summary_llm=self.summary_llm_client,
            output_writer=self.output_writer,
            failure_logger=self.failure_logger,
            incremental_manager=self.incremental_manager,
            archive_path=archive_path,
            force=force,
            dry_run=False,  # 正常处理模式，不是 Dry Run
            cancel_token=self.cancel_token,  # 传递取消令牌
            concurrency=self.app_config.concurrency,
            ai_concurrency=self.app_config.ai_concurrency,
            proxy_manager=self.proxy_manager,
            cookie_manager=self.cookie_manager,
            on_stats=on_stats,
            on_log=on_log,
            on_error=self._handle_pipeline_error,
            translation_llm_init_error_type=self.translation_llm_init_error_type,
            translation_llm_init_error=self.translation_llm_init_error,
            initial_url_count=initial_url_count,
            fetch_failed_count=fetch_failed_count,
        )

        # 更新最终统计信息（包含错误分类）
        stats["success"] = result.get("success", 0)
        stats["failed"] = result.get("failed", 0)
        stats["current"] = actual_video_count
        stats["error_counts"] = result.get("error_counts", {})  # 错误分类统计
        on_stats(stats)

        # 显示完成消息
        self._log_processing_complete(stats, result, on_log)

    def _on_stats(self, stats: dict):
        """处理统计信息更新"""
        self.state_manager.set("stats", stats)
        if isinstance(self.current_page, UrlListPage):
            self.current_page.update_stats(
                stats, self.state_manager.get("running_status", "")
            )
        # 更新日志面板的统计信息
        if hasattr(self, "log_panel") and hasattr(self.log_panel, "update_stats"):
            self.log_panel.update_stats(
                stats, self.state_manager.get("running_status", "")
            )
        self.event_bus.publish(EventType.STATS_UPDATED, stats)

    def _handle_pipeline_error(self, error_type: ErrorType, message: str):
        """处理流水线运行过程中的错误"""
        from core.exceptions import ErrorType
        if error_type == ErrorType.COOKIE_EXPIRED:
            # 发布 Cookie 失效事件
            if hasattr(self, "event_bus") and self.event_bus:
                self.event_bus.publish(EventType.COOKIE_STATUS_CHANGED, "expired")
            logger.warning(f"[Pipeline] Cookie expired detected: {message}")

    def _log_processing_complete(
        self,
        stats: dict,
        result: dict,
        on_log: Callable[[str, str, Optional[str]], None],
    ):
        """记录处理完成消息

        Args:
            stats: 统计信息
            result: 处理结果
            on_log: 日志回调
        """
        success_count = stats["success"]
        failed_count = stats["failed"]

        if failed_count > 0:
            errors = result.get("errors", [])
            if errors:
                msg = t(
                    "processing_complete_with_errors",
                    success=success_count,
                    failed=failed_count,
                )
            else:
                msg = t(
                    "processing_complete_simple",
                    success=success_count,
                    failed=failed_count,
                )
            on_log("WARN", msg)
        else:
            msg = t(
                "processing_complete_simple", success=success_count, failed=failed_count
            )
            on_log("INFO", msg)
