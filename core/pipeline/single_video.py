"""
单视频处理模块
串联：检测 → 下载 → 翻译 → 摘要 → 输出 → 增量更新

重构说明：将原单一大函数拆分为多个阶段函数，提高可测试性和可维护性
"""

from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple
from dataclasses import dataclass

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger, set_log_context, clear_log_context, translate_log
from core.detector import SubtitleDetector
from core.downloader import SubtitleDownloader
from core.translator import SubtitleTranslator
from core.summarizer import Summarizer
from core.output import OutputWriter
from core.incremental import IncrementalManager
from core.failure_logger import FailureLogger
from core.llm_client import LLMClient
from core.exceptions import (
    AppException,
    ErrorType,
    map_llm_error_to_app_error,
    TaskCancelledError,
)
from core.cancel_token import CancelToken

from .utils import safe_log, cleanup_temp_dir

logger = get_logger()


@dataclass
class StageContext:
    """阶段处理上下文，封装公共参数"""
    video_info: VideoInfo
    language_config: LanguageConfig
    cancel_token: Optional[CancelToken]
    proxy_manager: Any
    cookie_manager: Any
    run_id: Optional[str]
    on_log: Optional[Callable[[str, str, Optional[str]], None]]
    failure_logger: FailureLogger
    incremental_manager: IncrementalManager


def _check_cancelled(ctx: StageContext) -> None:
    """检查取消状态，如果已取消则抛出异常"""
    if ctx.cancel_token and ctx.cancel_token.is_cancelled():
        reason = ctx.cancel_token.get_reason() or translate_log("user_cancelled")
        raise TaskCancelledError(reason)


def _check_incremental(ctx: StageContext, force: bool) -> bool:
    """
    检查增量状态
    
    Returns:
        True 如果视频已处理完成（应跳过），False 如果需要继续处理
    """
    if force:
        return False
    
    status = ctx.incremental_manager.get_status(ctx.video_info.video_id)
    if status == "success":
        msg = logger.info_i18n(
            "video_already_processed", video_id=ctx.video_info.video_id
        )
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
        return True
    return False


def _stage_detect(ctx: StageContext) -> Optional[DetectionResult]:
    """
    阶段1: 字幕检测
    
    Returns:
        DetectionResult 如果有字幕，None 如果无字幕
    """
    _check_cancelled(ctx)
    
    msg = logger.info_i18n("detect_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
    
    detector = SubtitleDetector(
        proxy_manager=ctx.proxy_manager, cookie_manager=ctx.cookie_manager
    )
    detection_result = detector.detect(ctx.video_info.url)
    
    if not detection_result.has_subtitles:
        msg = logger.info_i18n("video_no_subtitle", video_id=ctx.video_info.video_id)
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
        return None
    
    msg = logger.info_i18n(
        "detect_subtitle_found",
        has_auto=str(detection_result.has_auto_captions),
        has_manual=str(detection_result.has_manual_captions),
        video_id=ctx.video_info.video_id,
    )
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
    
    return detection_result


def _stage_download(
    ctx: StageContext,
    detection_result: DetectionResult,
    archive_path: Optional[Path],
) -> Tuple[Optional[Path], Dict[str, Any]]:
    """
    阶段2: 字幕下载
    
    Returns:
        (temp_dir, download_result) 元组
    """
    _check_cancelled(ctx)
    
    msg = logger.info_i18n("download_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
    
    downloader = SubtitleDownloader(
        proxy_manager=ctx.proxy_manager,
        cookie_manager=ctx.cookie_manager,
        archive_path=archive_path,
    )
    
    from core.temp_manager import TempManager
    temp_manager = TempManager()
    temp_dir = temp_manager.create_temp_dir(ctx.video_info.video_id)
    
    download_result = downloader.download(
        url=ctx.video_info.url,
        detection_result=detection_result,
        output_dir=temp_dir,
        source_language=ctx.language_config.source_language,
        target_languages=ctx.language_config.target_languages,
    )
    
    msg = logger.info_i18n(
        "download_complete",
        has_original=str(download_result.get("original") is not None),
        video_id=ctx.video_info.video_id,
    )
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
    
    return temp_dir, download_result


def _stage_translate(
    ctx: StageContext,
    translation_llm: Optional[LLMClient],
    download_result: Dict[str, Any],
    temp_dir: Path,
    translation_llm_init_error_type: Optional[ErrorType] = None,
    translation_llm_init_error: Optional[str] = None,
) -> Dict[str, Optional[Path]]:
    """
    阶段3: 字幕翻译
    
    Returns:
        翻译结果字典 {语言代码: 翻译文件路径}
    """
    translation_result: Dict[str, Optional[Path]] = {}
    
    if not ctx.language_config.target_languages:
        return translation_result
    
    if not translation_llm:
        # 如果配置了目标语言但没有 LLM，记录警告
        if translation_llm_init_error_type:
            error_msg = logger.warning_i18n(
                "translation_llm_init_failed",
                error=translation_llm_init_error,
                video_id=ctx.video_info.video_id,
            )
            safe_log(ctx.on_log, "WARNING", error_msg, ctx.video_info.video_id)
        return translation_result
    
    _check_cancelled(ctx)
    
    msg = logger.info_i18n("translation_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
    
    translator = SubtitleTranslator(
        llm_client=translation_llm,
        source_language=ctx.language_config.source_language,
        target_languages=ctx.language_config.target_languages,
    )
    
    try:
        translation_result = translator.translate(
            original_path=download_result["original"],
            output_dir=temp_dir,
            video_title=ctx.video_info.title,
            cancel_token=ctx.cancel_token,
        )
        msg = logger.info_i18n(
            "translation_complete",
            count=len(translation_result),
            video_id=ctx.video_info.video_id,
        )
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
    except AppException as e:
        if e.error_type == ErrorType.AI_QUOTA_EXCEEDED:
            _handle_stage_error(ctx, e.error_type, e.message, "translation_quota_exceeded")
            raise
        raise
    
    return translation_result


def _stage_summarize(
    ctx: StageContext,
    summary_llm: Optional[LLMClient],
    download_result: Dict[str, Any],
    temp_dir: Path,
) -> Optional[Path]:
    """
    阶段4: 生成摘要
    
    Returns:
        摘要文件路径，如果未启用或失败则返回 None
    """
    if not ctx.language_config.summary_enabled:
        return None
    
    if not summary_llm:
        return None
    
    if not download_result.get("original"):
        return None
    
    _check_cancelled(ctx)
    
    msg = logger.info_i18n("summary_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
    
    summarizer = Summarizer(
        llm_client=summary_llm,
        summary_language=ctx.language_config.summary_language,
    )
    
    try:
        summary_path = summarizer.summarize(
            subtitle_path=download_result["original"],
            video_title=ctx.video_info.title,
            output_dir=temp_dir,
            cancel_token=ctx.cancel_token,
        )
        msg = logger.info_i18n("summary_complete", video_id=ctx.video_info.video_id)
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
        return summary_path
    except AppException as e:
        if e.error_type == ErrorType.AI_QUOTA_EXCEEDED:
            _handle_stage_error(ctx, e.error_type, e.message, "summary_quota_exceeded")
            raise
        raise


def _stage_output(
    ctx: StageContext,
    output_writer: OutputWriter,
    detection_result: DetectionResult,
    download_result: Dict[str, Any],
    translation_result: Dict[str, Optional[Path]],
    summary_path: Optional[Path],
    translation_llm: Optional[LLMClient],
    summary_llm: Optional[LLMClient],
    dry_run: bool,
) -> None:
    """阶段5: 输出文件"""
    if dry_run:
        msg = logger.info_i18n("output_skipped", video_id=ctx.video_info.video_id)
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
        return
    
    _check_cancelled(ctx)
    
    msg = logger.info_i18n("output_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
    
    output_writer.write_all(
        video_info=ctx.video_info,
        detection_result=detection_result,
        language_config=ctx.language_config,
        download_result=download_result,
        translation_result=translation_result,
        summary_path=summary_path,
        run_id=ctx.run_id,
        translation_llm=translation_llm,
        summary_llm=summary_llm,
    )
    
    msg = logger.info_i18n("output_complete", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)


def _handle_stage_error(
    ctx: StageContext,
    error_type: ErrorType,
    error_message: str,
    log_key: Optional[str] = None,
) -> None:
    """统一处理阶段错误：记录失败日志和增量状态"""
    if log_key:
        error_msg = logger.error_i18n(
            log_key,
            error=error_message,
            video_id=ctx.video_info.video_id,
        )
    else:
        error_msg = error_message
    
    safe_log(ctx.on_log, "ERROR", error_msg, ctx.video_info.video_id)
    
    ctx.failure_logger.log_failure(
        video_id=ctx.video_info.video_id,
        video_info=ctx.video_info,
        error_type=error_type,
        reason=error_msg,
        run_id=ctx.run_id,
    )
    
    ctx.incremental_manager.mark_failed(ctx.video_info.video_id, error_msg)


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
    
    # 创建阶段上下文
    ctx = StageContext(
        video_info=video_info,
        language_config=language_config,
        cancel_token=cancel_token,
        proxy_manager=proxy_manager,
        cookie_manager=cookie_manager,
        run_id=run_id,
        on_log=on_log,
        failure_logger=failure_logger,
        incremental_manager=incremental_manager,
    )
    
    temp_dir: Optional[Path] = None
    
    try:
        # 增量检查
        if _check_incremental(ctx, force):
            return True
        
        # 检查取消状态
        _check_cancelled(ctx)
        
        msg = logger.info_i18n(
            "video_processing_start",
            title=video_info.title,
            video_id=video_info.video_id,
        )
        safe_log(on_log, "INFO", msg, video_info.video_id)
        
        # 阶段 1: 字幕检测
        detection_result = _stage_detect(ctx)
        if detection_result is None:
            # 无字幕的情况
            if translation_llm_init_error_type:
                # 如果翻译 LLM 初始化失败，且没有字幕，则跳过
                error_msg = f"视频无字幕且翻译 LLM 初始化失败: {translation_llm_init_error}"
                _handle_stage_error(ctx, translation_llm_init_error_type, error_msg)
                return False
            return True
        
        # 阶段 2: 字幕下载
        temp_dir, download_result = _stage_download(ctx, detection_result, archive_path)
        
        if not download_result.get("original"):
            error_msg = logger.error_i18n(
                "download_original_failed", video_id=video_info.video_id
            )
            _handle_stage_error(ctx, ErrorType.FILE_IO, error_msg)
            return False
        
        # 阶段 3: 字幕翻译
        translation_result = _stage_translate(
            ctx, translation_llm, download_result, temp_dir,
            translation_llm_init_error_type, translation_llm_init_error
        )
        
        # 阶段 4: 生成摘要
        summary_path = _stage_summarize(ctx, summary_llm, download_result, temp_dir)
        
        # 阶段 5: 输出文件
        _stage_output(
            ctx, output_writer, detection_result, download_result,
            translation_result, summary_path, translation_llm, summary_llm, dry_run
        )
        
        # 更新增量状态
        if not dry_run:
            incremental_manager.mark_success(video_info.video_id)
        
        msg = logger.info_i18n(
            "video_processing_complete", video_id=video_info.video_id
        )
        safe_log(on_log, "INFO", msg, video_info.video_id)
        
        return True
    
    except TaskCancelledError as e:
        msg = logger.info_i18n(
            "task_cancelled", reason=e.message, video_id=video_info.video_id
        )
        safe_log(on_log, "INFO", msg, video_info.video_id)
        return False
    
    except AppException as e:
        import traceback
        
        error_msg = logger.error_i18n(
            "exception.processing_failed", error=e.message, video_id=video_info.video_id
        )
        logger.debug(traceback.format_exc(), video_id=video_info.video_id)
        safe_log(on_log, "ERROR", error_msg, video_info.video_id)
        
        failure_logger.log_failure(
            video_id=video_info.video_id,
            video_info=video_info,
            error_type=e.error_type,
            reason=e.message,
            run_id=run_id,
        )
        
        incremental_manager.mark_failed(video_info.video_id, e.message)
        return False
    
    except Exception as e:
        import traceback
        
        error_type = ErrorType.UNKNOWN
        
        if "llm" in str(e).lower() or "api" in str(e).lower():
            error_type = map_llm_error_to_app_error(e)
        
        error_msg = logger.error_i18n(
            "exception.unknown_error", error=str(e), video_id=video_info.video_id
        )
        logger.debug(traceback.format_exc(), video_id=video_info.video_id)
        safe_log(on_log, "ERROR", error_msg, video_info.video_id)
        
        failure_logger.log_failure(
            video_id=video_info.video_id,
            video_info=video_info,
            error_type=error_type,
            reason=str(e),
            run_id=run_id,
        )
        
        incremental_manager.mark_failed(video_info.video_id, str(e))
        return False
    
    finally:
        # 清理临时目录
        if temp_dir is not None:
            cleanup_temp_dir(temp_dir)
        # 清理日志上下文
        clear_log_context()
