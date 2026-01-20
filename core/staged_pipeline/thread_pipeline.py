"""
线程级 Pipeline 调度器

每个线程独立完成一个视频的全部处理流程，
使用信号量控制 AI API 并发数。
"""

import threading
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore, Lock

from core.models import VideoInfo
from core.logger import get_logger, set_log_context, clear_log_context
from core.exceptions import ErrorType, AppException, TaskCancelledError
from core.cancel_token import CancelToken
from core.failure_logger import FailureLogger

from .data_types import StageData
from .processors.detect import DetectProcessor
from .processors.download import DownloadProcessor
from .processors.translate import TranslateProcessor
from .processors.summarize import SummarizeProcessor
from .processors.output import OutputProcessor

logger = get_logger()


class ThreadPipeline:
    """线程级 Pipeline 编排器

    每个线程独立完成一个视频的全部处理流程（检测→下载→翻译→摘要→输出），
    使用信号量控制翻译和摘要的并发数以避免 AI API 限流。
    """

    def __init__(
        self,
        language_config,
        translation_llm: Optional[Any],
        summary_llm: Optional[Any],
        output_writer: Any,
        failure_logger: FailureLogger,
        incremental_manager: Any,
        archive_path: Optional[Path],
        force: bool = False,
        dry_run: bool = False,
        cancel_token: Optional[CancelToken] = None,
        proxy_manager=None,
        cookie_manager=None,
        run_id: Optional[str] = None,
        on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
        on_error: Optional[Callable[[StageData], None]] = None,
        on_video_complete: Optional[Callable[[StageData], None]] = None,
        on_stats: Optional[Callable[[Dict], None]] = None,
        # 并发配置
        concurrency: int = 5,  # 线程数（同时处理的视频数）
        ai_concurrency: int = 3,  # AI API 并发数（翻译+摘要共享）
        translation_llm_init_error_type: Optional[ErrorType] = None,
        translation_llm_init_error: Optional[str] = None,
    ):
        """初始化线程级 Pipeline

        Args:
            concurrency: 线程数（同时处理的视频数）
            ai_concurrency: AI API 并发数（翻译和摘要共享此限制）
            其他参数与 StagedPipeline 相同
        """
        self.language_config = language_config
        self.translation_llm = translation_llm
        self.summary_llm = summary_llm
        self.output_writer = output_writer
        self.failure_logger = failure_logger
        self.incremental_manager = incremental_manager
        self.archive_path = archive_path
        self.force = force
        self.dry_run = dry_run
        self.cancel_token = cancel_token
        self.proxy_manager = proxy_manager
        self.cookie_manager = cookie_manager
        self.run_id = run_id or f"{time.strftime('%Y%m%d_%H%M%S')}"
        self.on_log = on_log
        self.on_error = on_error
        self.on_video_complete = on_video_complete
        self.on_stats = on_stats
        self.translation_llm_init_error_type = translation_llm_init_error_type
        self.translation_llm_init_error = translation_llm_init_error

        # 并发控制
        self.concurrency = concurrency
        self.ai_semaphore = Semaphore(ai_concurrency)  # 限制 AI API 并发

        # 线程池
        self.executor = ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="video"
        )

        # 统计信息（线程安全）
        self._stats_lock = Lock()
        self._total = 0
        self._success = 0
        self._failed = 0
        self._skipped = 0
        self._running_videos: List[str] = []

        # 创建处理器（所有线程共享，处理器本身是无状态的）
        self._init_processors()

    def _init_processors(self):
        """初始化各阶段处理器"""
        self.detect_processor = DetectProcessor(
            cookie_manager=self.cookie_manager,
            incremental_manager=self.incremental_manager,
            archive_path=self.archive_path,
            force=self.force,
            dry_run=self.dry_run,
            cancel_token=self.cancel_token,
            on_log=self.on_log,
        )

        self.download_processor = DownloadProcessor(
            language_config=self.language_config,
            proxy_manager=self.proxy_manager,
            cookie_manager=self.cookie_manager,
            dry_run=self.dry_run,
            cancel_token=self.cancel_token,
            on_log=self.on_log,
        )

        self.translate_processor = TranslateProcessor(
            language_config=self.language_config,
            translation_llm=self.translation_llm,
            force=self.force,
            dry_run=self.dry_run,
            cancel_token=self.cancel_token,
            translation_llm_init_error_type=self.translation_llm_init_error_type,
            translation_llm_init_error=self.translation_llm_init_error,
            on_log=self.on_log,
        )

        self.summarize_processor = SummarizeProcessor(
            language_config=self.language_config,
            summary_llm=self.summary_llm,
            force=self.force,
            dry_run=self.dry_run,
            cancel_token=self.cancel_token,
        )

        self.output_processor = OutputProcessor(
            language_config=self.language_config,
            output_writer=self.output_writer,
            incremental_manager=self.incremental_manager,
            archive_path=self.archive_path,
            dry_run=self.dry_run,
            cancel_token=self.cancel_token,
            translation_llm=self.translation_llm,
            summary_llm=self.summary_llm,
        )

    def process_videos(self, videos: List[VideoInfo]) -> Dict[str, int]:
        """处理视频列表

        Args:
            videos: 视频信息列表

        Returns:
            统计结果：{"total": n, "success": n, "failed": n, "skipped": n}
        """
        self._total = len(videos)
        self._success = 0
        self._failed = 0
        self._skipped = 0
        self._running_videos = []

        logger.info_i18n(
            "log.thread_pipeline_start",
            total=self._total,
            concurrency=self.concurrency,
        )

        # 发送初始统计
        self._send_stats()

        # 提交所有视频到线程池
        futures = {}
        for video in videos:
            if self.cancel_token and self.cancel_token.is_cancelled():
                break
            future = self.executor.submit(self._process_single_video, video)
            futures[future] = video

        # 等待所有任务完成
        for future in as_completed(futures):
            video = futures[future]
            try:
                result = future.result()
                self._handle_result(result)
            except Exception as e:
                # 注意：不在这里计数，因为 _handle_result 内部已经处理过统计
                # 这里只记录日志，防止重复计数
                logger.error(f"处理结果时发生异常: {video.video_id} - {e}")

        # 关闭线程池
        self.executor.shutdown(wait=True)

        logger.info_i18n(
            "log.thread_pipeline_complete",
            total=self._total,
            success=self._success,
            failed=self._failed,
        )

        return {
            "total": self._total,
            "success": self._success,
            "failed": self._failed,
            "skipped": self._skipped,
        }

    def _process_single_video(self, video: VideoInfo) -> StageData:
        """处理单个视频的完整流程

        Args:
            video: 视频信息

        Returns:
            处理结果
        """
        vid = video.video_id
        data = StageData(video_info=video, run_id=self.run_id)

        # 更新运行中列表
        self._add_running(vid)

        try:
            # 设置日志上下文
            set_log_context(run_id=self.run_id, task="pipeline", video_id=vid)

            # 检查取消状态
            if self.cancel_token and self.cancel_token.is_cancelled():
                reason = self.cancel_token.get_reason() or "用户取消"
                data.error = TaskCancelledError(reason)
                data.error_type = ErrorType.CANCELLED
                return data

            # 阶段 1: 检测字幕
            data = self.detect_processor.process(data)
            if data.error or data.skip_reason:
                return data

            # 阶段 2: 下载字幕
            data = self.download_processor.process(data)
            if data.error or data.processing_failed:
                return data

            # 阶段 3: 翻译字幕（使用信号量限制并发）
            with self.ai_semaphore:
                if self.cancel_token and self.cancel_token.is_cancelled():
                    reason = self.cancel_token.get_reason() or "用户取消"
                    data.error = TaskCancelledError(reason)
                    data.error_type = ErrorType.CANCELLED
                    return data
                data = self.translate_processor.process(data)
            if data.error or data.processing_failed:
                return data

            # 阶段 4: 生成摘要（使用信号量限制并发）
            with self.ai_semaphore:
                if self.cancel_token and self.cancel_token.is_cancelled():
                    reason = self.cancel_token.get_reason() or "用户取消"
                    data.error = TaskCancelledError(reason)
                    data.error_type = ErrorType.CANCELLED
                    return data
                data = self.summarize_processor.process(data)
            if data.error or data.processing_failed:
                return data

            # 阶段 5: 输出文件
            data = self.output_processor.process(data)

            return data

        except TaskCancelledError as e:
            data.error = e
            data.error_type = ErrorType.CANCELLED
            data.error_stage = "pipeline"
            return data
        except AppException as e:
            data.error = e
            data.error_type = e.error_type
            data.error_stage = "pipeline"
            data.processing_failed = True
            logger.error(f"视频处理失败: {vid} - {e}")
            return data
        except Exception as e:
            data.error = AppException(
                message=str(e),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            data.error_type = ErrorType.UNKNOWN
            data.error_stage = "pipeline"
            data.processing_failed = True
            logger.error(f"视频处理异常: {vid} - {e}")
            return data
        finally:
            # 清理日志上下文
            clear_log_context()
            # 移除运行中列表
            self._remove_running(vid)

    def _handle_result(self, data: StageData):
        """处理视频处理结果

        Args:
            data: 处理结果
        """
        vid = data.video_info.video_id

        if data.error or data.processing_failed:
            # 处理失败
            self._update_stats(failed=1)
            
            # 记录失败
            if self.failure_logger:
                try:
                    error_type = data.error_type or ErrorType.UNKNOWN
                    if data.error:
                        error_msg = str(data.error)
                    elif data.processing_failed:
                        error_msg = "处理流程中断(Processing Failed)"
                    else:
                        error_msg = "未知错误"
                    self.failure_logger.log_failure(
                        video_id=vid,
                        url=data.video_info.url,
                        reason=error_msg,
                        error_type=error_type,
                        batch_id=self.run_id,
                        stage=data.error_stage or "unknown",
                    )
                except Exception as e:
                    logger.warning(f"记录失败日志时出错: {e}")
            
            # 错误回调
            if self.on_error:
                try:
                    self.on_error(data)
                except Exception as e:
                    logger.warning(f"on_error 回调失败: {e}")
                    
        elif data.skip_reason:
            # 跳过
            self._update_stats(skipped=1)
        else:
            # 成功
            self._update_stats(success=1)
            
            # 成功回调
            if self.on_video_complete:
                try:
                    self.on_video_complete(data)
                except Exception as e:
                    logger.warning(f"on_video_complete 回调失败: {e}")

    def _update_stats(self, success: int = 0, failed: int = 0, skipped: int = 0):
        """更新统计信息（线程安全）"""
        with self._stats_lock:
            self._success += success
            self._failed += failed
            self._skipped += skipped
        self._send_stats()

    def _add_running(self, vid: str):
        """添加到运行中列表"""
        with self._stats_lock:
            self._running_videos.append(vid)
        self._send_stats()

    def _remove_running(self, vid: str):
        """从运行中列表移除"""
        with self._stats_lock:
            if vid in self._running_videos:
                self._running_videos.remove(vid)
        self._send_stats()

    def _send_stats(self):
        """发送统计信息到回调"""
        if self.on_stats:
            try:
                with self._stats_lock:
                    stats = {
                        "total": self._total,
                        "success": self._success,
                        "failed": self._failed,
                        "skipped": self._skipped,
                        "running": list(self._running_videos),
                    }
                self.on_stats(stats)
            except Exception as e:
                logger.warning(f"on_stats 回调失败: {e}")

    def get_stats(self) -> Dict[str, int]:
        """获取当前统计信息"""
        with self._stats_lock:
            return {
                "total": self._total,
                "success": self._success,
                "failed": self._failed,
                "skipped": self._skipped,
            }
