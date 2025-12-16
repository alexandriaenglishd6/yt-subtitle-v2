"""
单视频处理模块
串联：检测 → 下载 → 翻译 → 摘要 → 输出 → 增量更新
"""
from pathlib import Path
from typing import Optional, Callable

from core.models import VideoInfo
from core.language import LanguageConfig
from core.logger import get_logger, set_log_context, clear_log_context
from core.detector import SubtitleDetector
from core.downloader import SubtitleDownloader
from core.translator import SubtitleTranslator
from core.summarizer import Summarizer
from core.output import OutputWriter
from core.incremental import IncrementalManager
from core.failure_logger import FailureLogger
from core.llm_client import LLMClient
from core.exceptions import AppException, ErrorType, map_llm_error_to_app_error, TaskCancelledError
from core.cancel_token import CancelToken

from .utils import safe_log, cleanup_temp_dir

logger = get_logger()


def process_single_video(
    video_info: VideoInfo,
    language_config: LanguageConfig,
    translation_llm: Optional[LLMClient],
    summary_llm: Optional[LLMClient],
    output_writer: OutputWriter,
    failure_logger: FailureLogger,
    incremental_manager: IncrementalManager,
    archive_path: Optional[Path],
    force: bool = False,
    dry_run: bool = False,
    cancel_token: Optional[CancelToken] = None,
    proxy_manager=None,
    cookie_manager=None,
    run_id: Optional[str] = None,
    on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
    translation_llm_init_error_type: Optional[ErrorType] = None,
    translation_llm_init_error: Optional[str] = None,
) -> bool:
    """处理单个视频
    
    符合 logging_spec.md 规范：
    - 使用日志上下文（run_id, task, video_id）
    
    Args:
        video_info: 视频信息
        language_config: 语言配置
        translation_llm: 翻译 LLM 客户端（可选）
        summary_llm: 摘要 LLM 客户端（可选）
        output_writer: 输出写入器
        failure_logger: 失败记录器
        incremental_manager: 增量管理器
        archive_path: archive 文件路径
        force: 是否强制重跑
        dry_run: 是否为干跑模式
        cancel_token: 取消令牌（可选）
        proxy_manager: 代理管理器
        cookie_manager: Cookie管理器
        run_id: 批次ID（run_id）
        on_log: 日志回调 (level, message, video_id)，可选
        translation_llm_init_error_type: 翻译 LLM 初始化错误类型
        translation_llm_init_error: 翻译 LLM 初始化错误信息
    
    Returns:
        是否成功处理
    """
    # 设置日志上下文
    set_log_context(run_id=run_id, task="pipeline", video_id=video_info.video_id)
    
    temp_dir = None
    temp_dir_created = False
    processing_failed = False
    
    try:
        # 检查增量状态
        if not force:
            status = incremental_manager.get_status(video_info.video_id)
            if status == "success":
                logger.info(f"视频 {video_info.video_id} 已成功处理，跳过", video_id=video_info.video_id)
                safe_log(on_log, "INFO", f"视频 {video_info.video_id} 已成功处理，跳过", video_info.video_id)
                return True
        
        # 检查取消状态
        if cancel_token and cancel_token.is_cancelled():
            reason = cancel_token.get_reason() or "用户取消"
            logger.info(f"任务已取消: {reason}", video_id=video_info.video_id)
            safe_log(on_log, "INFO", f"任务已取消: {reason}", video_info.video_id)
            raise TaskCancelledError(f"任务已取消: {reason}")
        
        logger.info(f"开始处理视频: {video_info.title} ({video_info.video_id})", video_id=video_info.video_id)
        safe_log(on_log, "INFO", f"开始处理视频: {video_info.title}", video_info.video_id)
        
        # 1. 字幕检测
        if cancel_token and cancel_token.is_cancelled():
            raise TaskCancelledError("任务已取消")
        
        logger.info("开始字幕检测...", video_id=video_info.video_id)
        safe_log(on_log, "INFO", "开始字幕检测...", video_info.video_id)
        
        detector = SubtitleDetector(proxy_manager=proxy_manager, cookie_manager=cookie_manager)
        detection_result = detector.detect(video_info.url)
        
        if not detection_result.has_subtitles:
            # 如果翻译 LLM 初始化失败，且没有字幕，则跳过
            if translation_llm_init_error_type:
                error_msg = f"视频无字幕且翻译 LLM 初始化失败: {translation_llm_init_error}"
                logger.warning(error_msg, video_id=video_info.video_id)
                safe_log(on_log, "WARNING", error_msg, video_info.video_id)
                failure_logger.log_failure(
                    video_id=video_info.video_id,
                    video_info=video_info,
                    error_type=translation_llm_init_error_type,
                    reason=error_msg,
                    run_id=run_id
                )
                incremental_manager.mark_failed(video_info.video_id, error_msg)
            return False
            
            logger.info(f"视频 {video_info.video_id} 无字幕，跳过", video_id=video_info.video_id)
            safe_log(on_log, "INFO", f"视频无字幕，跳过", video_info.video_id)
            return True
        
        logger.info(f"检测到字幕: 自动字幕={detection_result.has_auto_captions}, 手动字幕={detection_result.has_manual_captions}",
                   video_id=video_info.video_id)
        safe_log(on_log, "INFO", 
                f"检测到字幕: 自动字幕={detection_result.has_auto_captions}, 手动字幕={detection_result.has_manual_captions}",
                video_info.video_id)
        
        # 2. 字幕下载
        if cancel_token and cancel_token.is_cancelled():
            raise TaskCancelledError("任务已取消")
        
        logger.info("开始下载字幕...", video_id=video_info.video_id)
        safe_log(on_log, "INFO", "开始下载字幕...", video_info.video_id)
        
        downloader = SubtitleDownloader(
            proxy_manager=proxy_manager,
            cookie_manager=cookie_manager,
            archive_path=archive_path
        )
        
        from core.temp_manager import TempManager
        temp_manager = TempManager()
        temp_dir = temp_manager.create_temp_dir(video_info.video_id)
        temp_dir_created = True
        
        download_result = downloader.download(
            url=video_info.url,
            detection_result=detection_result,
            output_dir=temp_dir,
            source_language=language_config.source_language,
            target_languages=language_config.target_languages
        )
        
        # 检查下载结果
        if not download_result.get("original"):
            error_msg = "原始字幕下载失败"
            logger.error(error_msg, video_id=video_info.video_id)
            safe_log(on_log, "ERROR", error_msg, video_info.video_id)
            failure_logger.log_failure(
                video_id=video_info.video_id,
                video_info=video_info,
                error_type=ErrorType.FILE_IO,
                reason=error_msg,
                run_id=run_id
            )
            incremental_manager.mark_failed(video_info.video_id, error_msg)
            processing_failed = True
            return False
        
        logger.info(f"字幕下载完成: 原始字幕={download_result.get('original') is not None}", video_id=video_info.video_id)
        safe_log(on_log, "INFO", "字幕下载完成", video_info.video_id)
        
        # 3. 字幕翻译
        translation_result = {}
        
        if language_config.target_languages and translation_llm:
            if cancel_token and cancel_token.is_cancelled():
                raise TaskCancelledError("任务已取消")
            
            logger.info("开始翻译字幕...", video_id=video_info.video_id)
            safe_log(on_log, "INFO", "开始翻译字幕...", video_info.video_id)
            
            translator = SubtitleTranslator(
                llm_client=translation_llm,
                source_language=language_config.source_language,
                target_languages=language_config.target_languages
            )
            
            try:
                translation_result = translator.translate(
                    original_path=download_result["original"],
                    output_dir=temp_dir,
                    video_title=video_info.title,
                    cancel_token=cancel_token
                )
                logger.info(f"翻译完成: {len(translation_result)} 个目标语言", video_id=video_info.video_id)
                safe_log(on_log, "INFO", f"翻译完成: {len(translation_result)} 个目标语言", video_info.video_id)
            except AppException as e:
                if e.error_type == ErrorType.AI_QUOTA_EXCEEDED:
                    error_msg = f"AI 配额已用尽: {e.message}"
                    logger.error(error_msg, video_id=video_info.video_id)
                    safe_log(on_log, "ERROR", error_msg, video_info.video_id)
                    failure_logger.log_failure(
                        video_id=video_info.video_id,
                        video_info=video_info,
                        error_type=e.error_type,
                        reason=error_msg,
                        run_id=run_id
                    )
                    incremental_manager.mark_failed(video_info.video_id, error_msg)
                    processing_failed = True
                    return False
            else:
                    raise
        elif language_config.target_languages and not translation_llm:
            # 如果配置了目标语言但没有 LLM，记录警告
            if translation_llm_init_error_type:
                error_msg = f"翻译 LLM 初始化失败: {translation_llm_init_error}"
                logger.warning(error_msg, video_id=video_info.video_id)
                safe_log(on_log, "WARNING", error_msg, video_info.video_id)
                # 继续处理，只输出原始字幕
        
        # 4. 生成摘要
        summary_path = None
            
        if language_config.summary_enabled and summary_llm and download_result.get("original"):
            if cancel_token and cancel_token.is_cancelled():
                raise TaskCancelledError("任务已取消")
            
            logger.info("开始生成摘要...", video_id=video_info.video_id)
            safe_log(on_log, "INFO", "开始生成摘要...", video_info.video_id)
            
            summarizer = Summarizer(
                llm_client=summary_llm,
                summary_language=language_config.summary_language
            )
            
            try:
                summary_path = summarizer.summarize(
                    subtitle_path=download_result["original"],
                    video_title=video_info.title,
                    output_dir=temp_dir,
                    cancel_token=cancel_token
                )
                logger.info("摘要生成完成", video_id=video_info.video_id)
                safe_log(on_log, "INFO", "摘要生成完成", video_info.video_id)
            except AppException as e:
                if e.error_type == ErrorType.AI_QUOTA_EXCEEDED:
                    error_msg = f"AI 配额已用尽: {e.message}"
                    logger.error(error_msg, video_id=video_info.video_id)
                    safe_log(on_log, "ERROR", error_msg, video_info.video_id)
                    failure_logger.log_failure(
                        video_id=video_info.video_id,
                        video_info=video_info,
                        error_type=e.error_type,
                        reason=error_msg,
                        run_id=run_id
                    )
                    incremental_manager.mark_failed(video_info.video_id, error_msg)
                    processing_failed = True
                    return False
                else:
                    raise
        
        # 5. 输出文件
        if not dry_run:
            if cancel_token and cancel_token.is_cancelled():
                raise TaskCancelledError("任务已取消")
            
            logger.info("开始写入输出文件...", video_id=video_info.video_id)
            safe_log(on_log, "INFO", "开始写入输出文件...", video_info.video_id)
            
            output_writer.write_all(
                video_info=video_info,
                detection_result=detection_result,
                language_config=language_config,
                download_result=download_result,
                translation_result=translation_result,
                summary_path=summary_path,
                run_id=run_id,
                translation_llm=translation_llm,
                summary_llm=summary_llm
            )
            
            logger.info("输出文件写入完成", video_id=video_info.video_id)
            safe_log(on_log, "INFO", "输出文件写入完成", video_info.video_id)
        else:
            logger.info("干跑模式：跳过文件写入", video_id=video_info.video_id)
            safe_log(on_log, "INFO", "干跑模式：跳过文件写入", video_info.video_id)
        
        # 6. 更新增量状态
        if not dry_run:
            incremental_manager.mark_success(video_info.video_id)
        
        logger.info(f"视频 {video_info.video_id} 处理成功", video_id=video_info.video_id)
        safe_log(on_log, "INFO", "视频处理成功", video_info.video_id)
        
        return True
        
    except TaskCancelledError as e:
        logger.info(f"任务已取消: {e.message}", video_id=video_info.video_id)
        safe_log(on_log, "INFO", f"任务已取消: {e.message}", video_info.video_id)
        processing_failed = True
        return False
        
    except AppException as e:
        import traceback
        logger.error(f"处理失败 [{e.error_type.value}]: {e.message}", video_id=video_info.video_id)
        logger.debug(traceback.format_exc(), video_id=video_info.video_id)
        safe_log(on_log, "ERROR", f"处理失败: {e.message}", video_info.video_id)
        
        failure_logger.log_failure(
            video_id=video_info.video_id,
            video_info=video_info,
            error_type=e.error_type,
            reason=e.message,
            run_id=run_id
        )
        
        incremental_manager.mark_failed(video_info.video_id, e.message)
        processing_failed = True
        return False
        
    except Exception as e:
        import traceback
        error_type = ErrorType.UNKNOWN
        
        if "llm" in str(e).lower() or "api" in str(e).lower():
            error_type = map_llm_error_to_app_error(e)
        
        logger.error(f"未知错误: {e}", video_id=video_info.video_id)
        logger.debug(traceback.format_exc(), video_id=video_info.video_id)
        safe_log(on_log, "ERROR", f"未知错误: {e}", video_info.video_id)
        
        failure_logger.log_failure(
            video_id=video_info.video_id,
            video_info=video_info,
            error_type=error_type,
            reason=str(e),
            run_id=run_id
        )
        
        incremental_manager.mark_failed(video_info.video_id, str(e))
        processing_failed = True
        return False
        
    finally:
        # 清理临时目录（无论成功/失败/被取消都尝试清理）
        # 注意：如果需要保留失败现场，可通过 keep_temp_on_error 配置项控制
        if temp_dir_created and temp_dir is not None:
            # 默认情况下，无论成功或失败都清理临时目录
            # 如果需要保留失败现场，可以在这里添加配置检查
            # 例如：if not (processing_failed and keep_temp_on_error):
            cleanup_temp_dir(temp_dir)
        # 清理日志上下文
        clear_log_context()
