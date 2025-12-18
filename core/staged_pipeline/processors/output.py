"""
OUTPUT 阶段处理器
"""

import shutil
from pathlib import Path
from typing import Optional, Any

from core.logger import get_logger, set_log_context, clear_log_context, translate_log
from core.exceptions import ErrorType, AppException, TaskCancelledError
from core.cancel_token import CancelToken
from ..data_types import StageData

logger = get_logger()


class OutputProcessor:
    """输出处理器

    负责写入输出文件和清理临时目录
    """

    def __init__(
        self,
        language_config,
        output_writer: Any,
        incremental_manager: Any,
        archive_path: Optional[Path],
        dry_run: bool,
        cancel_token: Optional[CancelToken],
        translation_llm: Optional[Any] = None,
        summary_llm: Optional[Any] = None,
    ):
        """初始化输出处理器

        Args:
            language_config: 语言配置
            output_writer: 输出写入器
            incremental_manager: 增量管理器
            archive_path: archive 文件路径
            dry_run: 是否 Dry Run 模式
            cancel_token: 取消令牌
            translation_llm: 翻译 LLM 客户端（可选）
            summary_llm: 摘要 LLM 客户端（可选）
        """
        self.language_config = language_config
        self.output_writer = output_writer
        self.incremental_manager = incremental_manager
        self.archive_path = archive_path
        self.dry_run = dry_run
        self.cancel_token = cancel_token
        self.translation_llm = translation_llm
        self.summary_llm = summary_llm

    def process(self, data: StageData) -> StageData:
        """处理 OUTPUT 阶段

        1. 写入输出文件（Dry Run 模式下跳过）
        2. 更新增量记录（如果成功）
        3. 清理临时目录（无论成功/失败）

        Args:
            data: 阶段数据

        Returns:
            处理后的阶段数据
        """
        vid = data.video_info.video_id

        try:
            # 设置日志上下文
            if data.run_id:
                set_log_context(run_id=data.run_id, task="output", video_id=vid)

            # 检查取消状态
            if self.cancel_token and self.cancel_token.is_cancelled():
                reason = self.cancel_token.get_reason() or translate_log(
                    "log.user_cancelled"
                )
                raise TaskCancelledError(reason)

            # 检查是否有必要的输入数据
            if not data.detection_result:
                raise AppException(
                    message=translate_log("missing_detection_result"),
                    error_type=ErrorType.INVALID_INPUT,
                )
            if not data.download_result:
                raise AppException(
                    message=translate_log("missing_download_result"),
                    error_type=ErrorType.INVALID_INPUT,
                )

            # 步骤 1: 写入输出文件（Dry Run 模式下跳过）
            if not self.dry_run:
                logger.info_i18n("output_file_write", video_id=vid)

                # 确保 translation_result 中包含所有需要的语言（包括官方字幕）
                # 如果有官方字幕但没有在 translation_result 中，从 download_result 中补充
                translation_result = data.translation_result or {}
                official_translations = data.download_result.get(
                    "official_translations", {}
                )

                for target_lang in self.language_config.subtitle_target_languages:
                    if (
                        target_lang not in translation_result
                        and target_lang in official_translations
                    ):
                        official_path = official_translations[target_lang]
                        if official_path and official_path.exists():
                            translation_result[target_lang] = official_path
                            logger.debug(
                                f"补充官方字幕到翻译结果: {target_lang} <- {official_path}",
                                video_id=vid,
                            )

                # 写入所有输出文件
                self.output_writer.write_all(
                    data.video_info,
                    data.detection_result,
                    self.language_config,
                    data.download_result,
                    translation_result,
                    data.summary_result,  # summary_result 已经是 Path 类型
                    channel_name=data.video_info.channel_name,
                    channel_id=data.video_info.channel_id,
                    run_id=data.run_id,
                    translation_llm=self.translation_llm,
                    summary_llm=self.summary_llm,
                )

                logger.info_i18n("output_file_complete", video_id=vid)
            else:
                logger.debug(f"[Dry Run] 跳过写入输出文件: {vid}", video_id=vid)

            # 步骤 2: 更新增量记录（仅在成功时，Dry Run 模式下跳过）
            if self.archive_path and not self.dry_run:
                self.incremental_manager.mark_as_processed(vid, self.archive_path)
                logger.debug(
                    translate_log("incremental_record_updated", video_id=vid),
                    video_id=vid,
                )
            elif self.archive_path and self.dry_run:
                logger.debug(f"[Dry Run] 跳过更新增量记录: {vid}", video_id=vid)

            logger.info_i18n("processing_complete", video_id=vid)
            return data

        except TaskCancelledError as e:
            # 任务已取消
            reason = e.reason or translate_log("log.user_cancelled")
            logger.info_i18n("task_cancelled", video_id=vid, reason=reason)
            data.error = e
            data.error_type = ErrorType.CANCELLED
            data.error_stage = "output"
            # 取消不视为失败，但需要清理资源
            return data
        except AppException as e:
            # 应用异常
            data.error = e
            data.error_type = e.error_type
            data.error_stage = "output"
            data.processing_failed = True
            logger.error_i18n("output_file_failed", video_id=vid, error=str(e))
            return data
        except Exception as e:
            # 未知异常
            app_error = AppException(
                message=translate_log("log.output_file_failed", video_id=vid, error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            data.error = app_error
            data.error_type = ErrorType.UNKNOWN
            data.error_stage = "output"
            data.processing_failed = True
            logger.error_i18n("output_file_exception", video_id=vid, error=str(e))
            import traceback

            logger.debug(traceback.format_exc(), video_id=vid)
            return data
        finally:
            # 步骤 3: 清理临时目录（无论成功/失败/被取消都尝试清理）
            if data.temp_dir_created and data.temp_dir and data.temp_dir.exists():
                try:
                    shutil.rmtree(data.temp_dir)
                    logger.debug(
                        translate_log("log.temp_dir_cleaned", temp_dir=str(data.temp_dir)),
                        video_id=vid,
                    )
                except Exception as e:
                    logger.warning_i18n("log.cleanup_temp_failed", error=str(e))

            # 清理日志上下文
            clear_log_context()
