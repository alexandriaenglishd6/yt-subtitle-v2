"""
SUMMARIZE 阶段处理器
"""
from pathlib import Path
from typing import Optional, Callable, Any

from core.logger import get_logger, set_log_context, clear_log_context
from core.exceptions import ErrorType, AppException, TaskCancelledError
from core.cancel_token import CancelToken
from core.summarizer import Summarizer
from ..data_types import StageData

logger = get_logger()


class SummarizeProcessor:
    """摘要处理器
    
    负责生成视频摘要
    """
    
    def __init__(
        self,
        language_config,
        summary_llm: Optional[Any],
        force: bool,
        dry_run: bool,
        cancel_token: Optional[CancelToken],
    ):
        """初始化摘要处理器
        
        Args:
            language_config: 语言配置
            summary_llm: 摘要 LLM 客户端（可选）
            force: 是否强制重跑
            dry_run: 是否 Dry Run 模式
            cancel_token: 取消令牌
        """
        self.language_config = language_config
        self.summary_llm = summary_llm
        self.force = force
        self.dry_run = dry_run
        self.cancel_token = cancel_token
    
    def process(self, data: StageData) -> StageData:
        """处理 SUMMARIZE 阶段
        
        1. 检查是否有翻译结果或原始字幕，以及是否有 summary_llm
        2. 如果有，调用摘要生成器
        3. 摘要失败不视为整体失败
        
        Args:
            data: 阶段数据
            
        Returns:
            处理后的阶段数据
        """
        vid = data.video_info.video_id
        
        try:
            # 设置日志上下文
            if data.run_id:
                set_log_context(run_id=data.run_id, task="summarize", video_id=vid)
            
            # 检查是否有必要的输入数据和 summary_llm
            if not self.summary_llm:
                logger.debug(f"摘要 LLM 不可用，跳过摘要生成: {vid}", video_id=vid)
                data.summary_result = None
                return data
            
            # 检查是否有翻译结果或原始字幕
            has_translation = False
            if data.translation_result:
                has_translation = any(
                    path and path.exists()
                    for path in data.translation_result.values()
                )
            
            has_original = False
            if data.download_result and data.download_result.get("original"):
                has_original = data.download_result["original"].exists()
            
            if not (has_translation or has_original):
                logger.debug(f"无可用字幕，跳过摘要生成: {vid}", video_id=vid)
                data.summary_result = None
                return data
            
            logger.info(f"生成摘要: {vid}", video_id=vid)
            
            # 检查取消状态
            if self.cancel_token and self.cancel_token.is_cancelled():
                reason = self.cancel_token.get_reason() or "用户取消"
                raise TaskCancelledError(reason)
            
            # 生成摘要
            summarizer = Summarizer(llm=self.summary_llm, language_config=self.language_config)
            summary_path = summarizer.summarize(
                data.video_info,
                self.language_config,
                data.translation_result or {},
                data.download_result or {},
                data.temp_dir,
                force_regenerate=self.force
            )
            
            if not summary_path:
                logger.warning("摘要生成失败", video_id=vid)
                if not self.dry_run:
                    # 尝试从 summarizer 获取错误类型
                    summary_error = summarizer.get_summary_error()
                    error_type = ErrorType.UNKNOWN
                    if summary_error:
                        error_type = summary_error.error_type
                    
                    # 失败记录会在 StageQueue._log_failure 中处理
                    # 但这里需要设置错误信息以便记录
                    data.error = AppException(
                        message="摘要生成失败",
                        error_type=error_type
                    )
                    data.error_type = error_type
                    # 注意：不设置 processing_failed = True，因为摘要失败不视为整体失败
                else:
                    logger.debug("[Dry Run] 摘要生成失败（Dry Run）", video_id=vid)
            else:
                # 保存摘要结果（已经是 Path 类型）
                data.summary_result = summary_path
                logger.info(f"摘要生成完成: {vid}", video_id=vid)
            
            return data
            
        except TaskCancelledError as e:
            # 任务已取消
            reason = e.reason or "用户取消"
            logger.info(f"任务已取消: {vid} - {reason}", video_id=vid)
            data.error = e
            data.error_type = ErrorType.CANCELLED
            data.error_stage = "summarize"
            # 取消不视为失败，但需要清理资源
            return data
        except AppException as e:
            # 应用异常
            data.error = e
            data.error_type = e.error_type
            data.error_stage = "summarize"
            # 摘要失败不视为整体失败
            logger.error(f"生成摘要失败: {vid} - {e}", video_id=vid)
            return data
        except Exception as e:
            # 未知异常
            app_error = AppException(
                message=f"生成摘要失败: {str(e)}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            data.error = app_error
            data.error_type = ErrorType.UNKNOWN
            data.error_stage = "summarize"
            # 摘要失败不视为整体失败
            logger.error(f"生成摘要异常: {vid} - {e}", video_id=vid)
            import traceback
            logger.debug(traceback.format_exc(), video_id=vid)
            return data
        finally:
            # 清理日志上下文
            clear_log_context()

