"""
DETECT 阶段处理器
"""
from pathlib import Path
from typing import Optional, Callable

from core.logger import get_logger, set_log_context, clear_log_context, translate_log
from core.exceptions import ErrorType, AppException, TaskCancelledError
from core.cancel_token import CancelToken
from core.detector import SubtitleDetector
from ..data_types import StageData

logger = get_logger()

# 常量定义
MAX_TITLE_DISPLAY_LENGTH = 50


class DetectProcessor:
    """检测处理器
    
    负责检测视频是否有字幕
    """
    
    def __init__(
        self,
        cookie_manager,
        incremental_manager,
        archive_path: Optional[Path],
        force: bool,
        dry_run: bool,
        cancel_token: Optional[CancelToken],
        language_config=None,  # 语言配置（用于增量检查时考虑语言变化）
        on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
    ):
        """初始化检测处理器
        
        Args:
            cookie_manager: Cookie 管理器
            incremental_manager: 增量管理器
            archive_path: archive 文件路径
            force: 是否强制重跑
            dry_run: 是否 Dry Run 模式
            cancel_token: 取消令牌
            on_log: 日志回调
        """
        self.cookie_manager = cookie_manager
        self.incremental_manager = incremental_manager
        self.archive_path = archive_path
        self.force = force
        self.dry_run = dry_run
        self.cancel_token = cancel_token
        self.language_config = language_config
        self.on_log = on_log
    
    def process(self, data: StageData) -> StageData:
        """处理 DETECT 阶段
        
        1. 检查增量记录（如果 force=False，跳过已处理视频）
        2. 执行字幕检测
        3. 如果没有字幕，设置 skip_reason 并记录失败
        
        Args:
            data: 阶段数据
            
        Returns:
            处理后的阶段数据
        """
        vid = data.video_info.video_id
        title_preview = data.video_info.title[:MAX_TITLE_DISPLAY_LENGTH]
        
        try:
            # 设置日志上下文
            if data.run_id:
                set_log_context(run_id=data.run_id, task="detect", video_id=vid)
            
            logger.info_i18n("detect_subtitle_info", video_id=vid, title_preview=title_preview)
            
            # 检查取消状态
            if self.cancel_token and self.cancel_token.is_cancelled():
                reason = self.cancel_token.get_reason() or logger.translate_log("user_cancelled")
                raise TaskCancelledError(reason)
            
            # 检查增量记录（如果 force=False）
            if not self.force and self.archive_path:
                # 计算语言配置哈希值（如果提供了语言配置）
                from core.incremental import _get_language_config_hash
                lang_hash = _get_language_config_hash(self.language_config) if self.language_config else None
                
                if self.incremental_manager.is_processed(vid, self.archive_path, lang_hash):
                    data.is_processed = True
                    from ui.i18n_manager import t
                    data.skip_reason = t("log.video_already_processed_skip", video_id=vid)
                    skip_msg = logger.info_i18n("video_already_processed_skip", video_id=vid)
                    if self.on_log:
                        try:
                            self.on_log("INFO", skip_msg, vid)
                        except Exception:
                            pass
                    return data
            
            # 执行字幕检测
            detector = SubtitleDetector(cookie_manager=self.cookie_manager)
            detection_result = detector.detect(data.video_info)
            data.detection_result = detection_result
            
            # 检查是否有字幕
            if not detection_result.has_subtitles:
                error_msg = "视频无可用字幕，跳过处理"
                logger.warning(error_msg, video_id=vid)
                if self.on_log:
                    try:
                        self.on_log("WARN", error_msg, vid)
                    except Exception:
                        pass
                
                if not self.dry_run:
                    # 失败记录会在 StageQueue._log_failure 中处理
                    data.skip_reason = "无可用字幕"
                    data.error_type = ErrorType.CONTENT
                    data.processing_failed = True
                else:
                    data.skip_reason = translate_log("no_subtitles_dry_run")
                
                return data
            
            logger.info_i18n("detect_subtitle_found", video_id=vid)
            return data
            
        except TaskCancelledError as e:
            # 任务已取消
            reason = e.reason or translate_log("user_cancelled")
            logger.info_i18n("task_cancelled", video_id=vid, reason=reason)
            data.error = e
            data.error_type = ErrorType.CANCELLED
            data.error_stage = "detect"
            return data
        except AppException as e:
            # 应用异常
            data.error = e
            data.error_type = e.error_type
            data.error_stage = "detect"
            data.processing_failed = True
            logger.error_i18n("detect_subtitle_failed", video_id=vid, error=str(e))
            return data
        except Exception as e:
            # 未知异常
            app_error = AppException(
                message=translate_log("detect_subtitle_failed", video_id=vid, error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            data.error = app_error
            data.error_type = ErrorType.UNKNOWN
            data.error_stage = "detect"
            data.processing_failed = True
            logger.error_i18n("detect_subtitle_exception", video_id=vid, error=str(e))
            import traceback
            logger.debug(traceback.format_exc(), video_id=vid)
            return data
        finally:
            # 清理日志上下文
            clear_log_context()

