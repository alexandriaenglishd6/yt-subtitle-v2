"""
DETECT 阶段处理器
"""
from pathlib import Path
from typing import Optional, Callable

from core.logger import get_logger, set_log_context, clear_log_context
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
                reason = self.cancel_token.get_reason() or "用户取消"
                raise TaskCancelledError(reason)
            
            # 检查增量记录（如果 force=False）
            if not self.force and self.archive_path:
                if self.incremental_manager.is_processed(vid, self.archive_path):
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
                    data.skip_reason = "无可用字幕（Dry Run）"
                
                return data
            
            logger.info(f"检测到字幕: {vid}", video_id=vid)
            return data
            
        except TaskCancelledError as e:
            # 任务已取消
            reason = e.reason or "用户取消"
            logger.info(f"任务已取消: {vid} - {reason}", video_id=vid)
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
            logger.error(f"检测字幕失败: {vid} - {e}", video_id=vid)
            return data
        except Exception as e:
            # 未知异常
            app_error = AppException(
                message=f"检测字幕失败: {str(e)}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            data.error = app_error
            data.error_type = ErrorType.UNKNOWN
            data.error_stage = "detect"
            data.processing_failed = True
            logger.error(f"检测字幕异常: {vid} - {e}", video_id=vid)
            import traceback
            logger.debug(traceback.format_exc(), video_id=vid)
            return data
        finally:
            # 清理日志上下文
            clear_log_context()

