"""
分阶段 Pipeline 调度器
"""

import threading
import time
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from concurrent.futures import ThreadPoolExecutor

from core.models import VideoInfo
from core.logger import get_logger
from core.exceptions import ErrorType
from core.cancel_token import CancelToken
from core.failure_logger import FailureLogger
from core.i18n import t

from .data_types import StageData
from .queue import StageQueue
from .processors.detect import DetectProcessor
from .processors.download import DownloadProcessor
from .processors.translate import TranslateProcessor
from .processors.summarize import SummarizeProcessor
from .processors.output import OutputProcessor

logger = get_logger()


class StagedPipeline:
    """分阶段 Pipeline 编排器

    将视频处理流程拆分为多个阶段，每个阶段有独立的队列和执行器
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
        on_video_complete: Optional[Callable[[StageData], None]] = None,  # 视频完成回调
        # 阶段并发配置
        detect_concurrency: int = 10,
        download_concurrency: int = 10,
        translate_concurrency: int = 5,
        summarize_concurrency: int = 5,
        output_concurrency: int = 10,
        translation_llm_init_error_type: Optional[ErrorType] = None,
        translation_llm_init_error: Optional[str] = None,
    ):
        """初始化分阶段 Pipeline

        Args:
            language_config: 语言配置
            translation_llm: 翻译 LLM 客户端（可选）
            summary_llm: 摘要 LLM 客户端（可选）
            output_writer: 输出写入器
            failure_logger: 失败记录器
            incremental_manager: 增量管理器
            archive_path: archive 文件路径
            force: 是否强制重跑
            dry_run: 是否 Dry Run 模式
            cancel_token: 取消令牌
            proxy_manager: 代理管理器
            cookie_manager: Cookie 管理器
            run_id: 批次ID（run_id）
            on_log: 日志回调
            detect_concurrency: DETECT 阶段并发数
            download_concurrency: DOWNLOAD 阶段并发数
            translate_concurrency: TRANSLATE 阶段并发数
            summarize_concurrency: SUMMARIZE 阶段并发数
            output_concurrency: OUTPUT 阶段并发数
            translation_llm_init_error_type: 翻译 LLM 初始化错误类型
            translation_llm_init_error: 翻译 LLM 初始化错误信息
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
        self.run_id = run_id
        self.on_log = on_log
        self.on_video_complete = on_video_complete
        self.translation_llm_init_error_type = translation_llm_init_error_type
        self.translation_llm_init_error = translation_llm_init_error

        # 创建各阶段的执行器
        self.detect_executor = ThreadPoolExecutor(
            max_workers=detect_concurrency, thread_name_prefix="detect"
        )
        self.download_executor = ThreadPoolExecutor(
            max_workers=download_concurrency, thread_name_prefix="download"
        )
        self.translate_executor = ThreadPoolExecutor(
            max_workers=translate_concurrency, thread_name_prefix="translate"
        )
        self.summarize_executor = ThreadPoolExecutor(
            max_workers=summarize_concurrency, thread_name_prefix="summarize"
        )
        self.output_executor = ThreadPoolExecutor(
            max_workers=output_concurrency, thread_name_prefix="output"
        )

        # 创建各阶段的处理器（显式参数注入）
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

        # 创建各阶段的队列（从后往前创建，以便设置 next_stage_queue）
        # OUTPUT 阶段（最后一个阶段）
        self.output_queue = StageQueue(
            stage_name="output",
            executor=self.output_executor,
            processor=self.output_processor.process,
            next_stage_queue=None,  # 最后一个阶段
            failure_logger=failure_logger,
            cancel_token=cancel_token,
            on_error=on_error,
            on_complete=self.on_video_complete,  # 视频完成回调
        )

        # SUMMARIZE 阶段
        self.summarize_queue = StageQueue(
            stage_name="summarize",
            executor=self.summarize_executor,
            processor=self.summarize_processor.process,
            next_stage_queue=self.output_queue,
            failure_logger=failure_logger,
            cancel_token=cancel_token,
            on_error=on_error,
        )

        # TRANSLATE 阶段
        self.translate_queue = StageQueue(
            stage_name="translate",
            executor=self.translate_executor,
            processor=self.translate_processor.process,
            next_stage_queue=self.summarize_queue,
            failure_logger=failure_logger,
            cancel_token=cancel_token,
            on_error=on_error,
        )

        # DOWNLOAD 阶段
        self.download_queue = StageQueue(
            stage_name="download",
            executor=self.download_executor,
            processor=self.download_processor.process,
            next_stage_queue=self.translate_queue,
            failure_logger=failure_logger,
            cancel_token=cancel_token,
            on_error=on_error,
        )

        # DETECT 阶段（第一个阶段）
        self.detect_queue = StageQueue(
            stage_name="detect",
            executor=self.detect_executor,
            processor=self.detect_processor.process,
            next_stage_queue=self.download_queue,
            failure_logger=failure_logger,
            cancel_token=cancel_token,
            on_error=on_error,
        )

        # 统计信息
        self._lock = threading.Lock()
        self._total_count = 0
        self._success_count = 0
        self._failed_count = 0

    def _stop_all_queues(self, timeout: float = 5.0):
        """停止所有阶段的队列
        
        Args:
            timeout: 每个队列的超时时间（秒）
        """
        logger.debug("Stopping all stage queues...")
        # 按反向顺序停止队列（从输出到检测）
        for queue in [
            self.output_queue,
            self.summarize_queue,
            self.translate_queue,
            self.download_queue,
            self.detect_queue,
        ]:
            try:
                queue.stop(timeout=timeout)
            except Exception as e:
                logger.warning(f"Error stopping queue {queue.stage_name}: {e}")

    def process_videos(self, videos: List[VideoInfo]) -> Dict[str, int]:
        """处理视频列表

        Args:
            videos: 视频列表

        Returns:
            统计信息：{"total": 总数, "success": 成功数, "failed": 失败数}
        """
        if not videos:
            logger.warning_i18n("log.task_video_list_empty")
            return {"total": 0, "success": 0, "failed": 0}

        self._total_count = len(videos)
        self._success_count = 0
        self._failed_count = 0

        logger.info_i18n(
            "processing_start_staged", count=self._total_count, run_id=self.run_id
        )

        try:
            # 1. 启动所有阶段
            self.detect_queue.start()
            self.download_queue.start()
            self.translate_queue.start()
            self.summarize_queue.start()
            self.output_queue.start()

            # 2. 将视频加入 DETECT 阶段（第一个阶段）
            for video in videos:
                data = StageData(
                    video_info=video,
                    run_id=self.run_id,  # 添加 run_id 到 data（用于失败记录）
                )
                self.detect_queue.enqueue(data)

            # 3. 等待所有阶段完成
            # 等待所有队列为空且所有任务完成
            while True:
                if self.cancel_token and self.cancel_token.is_cancelled():
                    logger.info_i18n("log.cancel_signal_detected")
                    # 立即停止所有阶段的 worker 线程
                    self._stop_all_queues()
                    break

                # 检查所有阶段是否完成
                if (
                    self.detect_queue.is_empty()
                    and self.download_queue.is_empty()
                    and self.translate_queue.is_empty()
                    and self.summarize_queue.is_empty()
                    and self.output_queue.is_empty()
                ):
                    break

                time.sleep(0.5)  # 等待 0.5 秒后再次检查

            # 4. 汇总统计信息
            detect_stats = self.detect_queue.get_stats()
            download_stats = self.download_queue.get_stats()
            translate_stats = self.translate_queue.get_stats()
            summarize_stats = self.summarize_queue.get_stats()
            output_stats = self.output_queue.get_stats()

            # 成功数：OUTPUT 阶段成功处理的数量
            self._success_count = output_stats["processed"]
            # 失败数：所有阶段的失败数之和
            self._failed_count = (
                detect_stats["failed"]
                + download_stats["failed"]
                + translate_stats["failed"]
                + summarize_stats["failed"]
                + output_stats["failed"]
            )

            logger.info(
                t(
                    "log.task_complete",
                    total=self._total_count,
                    success=self._success_count,
                    failed=self._failed_count,
                ),
                run_id=self.run_id,
            )

            return {
                "total": self._total_count,
                "success": self._success_count,
                "failed": self._failed_count,
            }

        finally:
            # 5. 停止所有阶段
            self.output_queue.stop()
            self.summarize_queue.stop()
            self.translate_queue.stop()
            self.download_queue.stop()
            self.detect_queue.stop()

            # 关闭所有执行器
            self.output_executor.shutdown(wait=True)
            self.summarize_executor.shutdown(wait=True)
            self.translate_executor.shutdown(wait=True)
            self.download_executor.shutdown(wait=True)
            self.detect_executor.shutdown(wait=True)

    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            if hasattr(self, "output_executor"):
                self.output_executor.shutdown(wait=False)
            if hasattr(self, "summarize_executor"):
                self.summarize_executor.shutdown(wait=False)
            if hasattr(self, "translate_executor"):
                self.translate_executor.shutdown(wait=False)
            if hasattr(self, "download_executor"):
                self.download_executor.shutdown(wait=False)
            if hasattr(self, "detect_executor"):
                self.detect_executor.shutdown(wait=False)
        except Exception:
            pass
