"""
DOWNLOAD 阶段处理器
"""
from pathlib import Path
from typing import Optional, Callable

from core.logger import get_logger, set_log_context, clear_log_context, translate_log
from core.exceptions import ErrorType, AppException, TaskCancelledError
from core.cancel_token import CancelToken
from core.downloader import SubtitleDownloader
from ..data_types import StageData

logger = get_logger()

# 常量定义
MAX_TITLE_DISPLAY_LENGTH = 50


class DownloadProcessor:
    """下载处理器
    
    负责下载字幕文件
    """
    
    def __init__(
        self,
        language_config,
        proxy_manager,
        cookie_manager,
        dry_run: bool,
        cancel_token: Optional[CancelToken],
        on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
    ):
        """初始化下载处理器
        
        Args:
            language_config: 语言配置
            proxy_manager: 代理管理器
            cookie_manager: Cookie 管理器
            dry_run: 是否 Dry Run 模式
            cancel_token: 取消令牌
            on_log: 日志回调
        """
        self.language_config = language_config
        self.proxy_manager = proxy_manager
        self.cookie_manager = cookie_manager
        self.dry_run = dry_run
        self.cancel_token = cancel_token
        self.on_log = on_log
    
    def process(self, data: StageData) -> StageData:
        """处理 DOWNLOAD 阶段
        
        1. 创建临时目录
        2. 下载原始字幕和官方翻译字幕
        3. 检查下载结果，如果没有原始字幕则失败
        
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
                set_log_context(run_id=data.run_id, task="download", video_id=vid)
            
            logger.info_i18n("download_subtitle", video_id=vid, title_preview=title_preview)
            
            # 检查取消状态
            if self.cancel_token and self.cancel_token.is_cancelled():
                reason = self.cancel_token.get_reason() or translate_log("user_cancelled")
                raise TaskCancelledError(reason)
            
            # 检查是否有检测结果
            if not data.detection_result:
                raise AppException(
                    message=translate_log("missing_detection_result"),
                    error_type=ErrorType.INVALID_INPUT
                )
            
            # 创建临时目录
            data.temp_dir = Path("temp") / vid
            data.temp_dir.mkdir(parents=True, exist_ok=True)
            data.temp_dir_created = True
            
            # 下载字幕
            downloader = SubtitleDownloader(
                proxy_manager=self.proxy_manager,
                cookie_manager=self.cookie_manager
            )
            download_result = downloader.download(
                data.video_info,
                data.detection_result,
                self.language_config,
                data.temp_dir,
                cancel_token=self.cancel_token
            )
            
            # 检查下载结果
            if not download_result.get("original"):
                error_msg = translate_log("download_original_subtitle_failed")
                logger.error_i18n("download_original_subtitle_failed", video_id=vid)
                if self.on_log:
                    try:
                        self.on_log("ERROR", error_msg, vid)
                    except Exception:
                        pass
                
                if not self.dry_run:
                    # 失败记录会在 StageQueue._log_failure 中处理
                    data.error_type = ErrorType.NETWORK
                    data.processing_failed = True
                else:
                    data.skip_reason = translate_log("download_original_subtitle_failed_dry_run")
                
                return data
            
            # 保存下载结果
            data.download_result = download_result
            
            logger.info_i18n("download_subtitle_complete", video_id=vid)
            return data
            
        except TaskCancelledError as e:
            # 任务已取消
            reason = e.reason or translate_log("user_cancelled")
            logger.info_i18n("task_cancelled", video_id=vid, reason=reason)
            data.error = e
            data.error_type = ErrorType.CANCELLED
            data.error_stage = "download"
            return data
        except AppException as e:
            # 应用异常
            data.error = e
            data.error_type = e.error_type
            data.error_stage = "download"
            data.processing_failed = True
            logger.error_i18n("download_subtitle_failed", video_id=vid, error=str(e))
            return data
        except Exception as e:
            # 未知异常
            app_error = AppException(
                message=translate_log("download_subtitle_failed", video_id=vid, error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            data.error = app_error
            data.error_type = ErrorType.UNKNOWN
            data.error_stage = "download"
            data.processing_failed = True
            logger.error_i18n("download_subtitle_exception", video_id=vid, error=str(e))
            import traceback
            logger.debug(traceback.format_exc(), video_id=vid)
            return data
        finally:
            # 清理日志上下文
            clear_log_context()

