"""
Pipeline 阶段函数

将 single_video.py 的巨型函数拆分为独立的阶段函数，
每个阶段函数负责一个处理步骤，便于测试和维护。

阶段流程：
1. detect_stage - 字幕检测
2. download_stage - 字幕下载
3. translate_stage - 字幕翻译
4. summarize_stage - 生成摘要
5. output_stage - 输出文件
"""

from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger, translate_log
from core.detector import SubtitleDetector
from core.downloader import SubtitleDownloader
from core.translator import SubtitleTranslator
from core.summarizer import Summarizer
from core.output import OutputWriter
from core.llm_client import LLMClient
from core.exceptions import AppException, ErrorType, TaskCancelledError
from core.cancel_token import CancelToken

from .utils import safe_log

logger = get_logger()


@dataclass
class StageContext:
    """阶段上下文，用于在阶段间传递数据

    Attributes:
        video_info: 视频信息
        language_config: 语言配置
        run_id: 批次 ID
        on_log: 日志回调
        cancel_token: 取消令牌
        proxy_manager: 代理管理器
        cookie_manager: Cookie 管理器
    """
    video_info: VideoInfo
    language_config: LanguageConfig
    run_id: Optional[str] = None
    on_log: Optional[Callable[[str, str, Optional[str]], None]] = None
    cancel_token: Optional[CancelToken] = None
    proxy_manager: Any = None
    cookie_manager: Any = None

    # 阶段输出（由各阶段填充）
    detection_result: Optional[DetectionResult] = None
    temp_dir: Optional[Path] = None
    download_result: Dict[str, Any] = field(default_factory=dict)
    translation_result: Dict[str, Any] = field(default_factory=dict)
    summary_path: Optional[Path] = None

    def check_cancelled(self) -> None:
        """检查是否已取消，如果已取消则抛出异常"""
        if self.cancel_token and self.cancel_token.is_cancelled():
            reason = self.cancel_token.get_reason() or translate_log("user_cancelled")
            raise TaskCancelledError(reason)


@dataclass
class StageResult:
    """阶段执行结果

    Attributes:
        success: 是否成功
        should_continue: 是否继续下一阶段
        error: 错误信息（如果失败）
        error_type: 错误类型
    """
    success: bool = True
    should_continue: bool = True
    error: Optional[str] = None
    error_type: Optional[ErrorType] = None


def detect_stage(ctx: StageContext) -> StageResult:
    """阶段 1: 字幕检测

    检测视频是否有字幕（自动/人工），填充 ctx.detection_result

    Args:
        ctx: 阶段上下文

    Returns:
        StageResult 执行结果
    """
    ctx.check_cancelled()

    msg = logger.info_i18n("detect_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)

    detector = SubtitleDetector(
        proxy_manager=ctx.proxy_manager,
        cookie_manager=ctx.cookie_manager,
    )

    ctx.detection_result = detector.detect(ctx.video_info.url)

    if not ctx.detection_result.has_subtitles:
        msg = logger.info_i18n("video_no_subtitle", video_id=ctx.video_info.video_id)
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
        return StageResult(success=True, should_continue=False)

    msg = logger.info_i18n(
        "detect_subtitle_found",
        has_auto=str(ctx.detection_result.has_auto_captions),
        has_manual=str(ctx.detection_result.has_manual_captions),
        video_id=ctx.video_info.video_id,
    )
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)

    return StageResult(success=True, should_continue=True)


def download_stage(
    ctx: StageContext,
    archive_path: Optional[Path] = None,
) -> StageResult:
    """阶段 2: 字幕下载

    下载原始字幕和官方翻译字幕，填充 ctx.download_result

    Args:
        ctx: 阶段上下文
        archive_path: archive 文件路径

    Returns:
        StageResult 执行结果
    """
    ctx.check_cancelled()

    msg = logger.info_i18n("download_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)

    downloader = SubtitleDownloader(
        proxy_manager=ctx.proxy_manager,
        cookie_manager=ctx.cookie_manager,
        archive_path=archive_path,
    )

    # 创建临时目录
    from core.temp_manager import TempManager
    temp_manager = TempManager()
    ctx.temp_dir = temp_manager.create_temp_dir(ctx.video_info.video_id)

    ctx.download_result = downloader.download(
        url=ctx.video_info.url,
        detection_result=ctx.detection_result,
        output_dir=ctx.temp_dir,
        source_language=ctx.language_config.source_language,
        target_languages=ctx.language_config.target_languages,
    )

    # 检查下载结果
    if not ctx.download_result.get("original"):
        error_msg = logger.error_i18n(
            "download_original_failed", video_id=ctx.video_info.video_id
        )
        safe_log(ctx.on_log, "ERROR", error_msg, ctx.video_info.video_id)
        return StageResult(
            success=False,
            should_continue=False,
            error=error_msg,
            error_type=ErrorType.FILE_IO,
        )

    msg = logger.info_i18n(
        "download_complete",
        has_original=str(ctx.download_result.get("original") is not None),
        video_id=ctx.video_info.video_id,
    )
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)

    return StageResult(success=True, should_continue=True)


def translate_stage(
    ctx: StageContext,
    translation_llm: Optional[LLMClient],
) -> StageResult:
    """阶段 3: 字幕翻译

    调用 AI 翻译字幕，填充 ctx.translation_result

    Args:
        ctx: 阶段上下文
        translation_llm: 翻译 LLM 客户端

    Returns:
        StageResult 执行结果
    """
    if not ctx.language_config.target_languages or not translation_llm:
        # 无需翻译
        return StageResult(success=True, should_continue=True)

    ctx.check_cancelled()

    msg = logger.info_i18n("translation_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)

    translator = SubtitleTranslator(
        llm_client=translation_llm,
        source_language=ctx.language_config.source_language,
        target_languages=ctx.language_config.target_languages,
    )

    try:
        ctx.translation_result = translator.translate(
            original_path=ctx.download_result["original"],
            output_dir=ctx.temp_dir,
            video_title=ctx.video_info.title,
            cancel_token=ctx.cancel_token,
        )
        msg = logger.info_i18n(
            "translation_complete",
            count=len(ctx.translation_result),
            video_id=ctx.video_info.video_id,
        )
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
        return StageResult(success=True, should_continue=True)

    except AppException as e:
        if e.error_type == ErrorType.AI_QUOTA_EXCEEDED:
            error_msg = logger.error_i18n(
                "translation_quota_exceeded",
                error=e.message,
                video_id=ctx.video_info.video_id,
            )
            safe_log(ctx.on_log, "ERROR", error_msg, ctx.video_info.video_id)
            return StageResult(
                success=False,
                should_continue=False,
                error=error_msg,
                error_type=e.error_type,
            )
        raise


def summarize_stage(
    ctx: StageContext,
    summary_llm: Optional[LLMClient],
) -> StageResult:
    """阶段 4: 生成摘要

    调用 AI 生成视频摘要，填充 ctx.summary_path

    Args:
        ctx: 阶段上下文
        summary_llm: 摘要 LLM 客户端

    Returns:
        StageResult 执行结果
    """
    if not ctx.language_config.summary_enabled or not summary_llm:
        # 无需摘要
        return StageResult(success=True, should_continue=True)

    if not ctx.download_result.get("original"):
        # 无原始字幕，跳过摘要
        return StageResult(success=True, should_continue=True)

    ctx.check_cancelled()

    msg = logger.info_i18n("summary_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)

    summarizer = Summarizer(
        llm_client=summary_llm,
        summary_language=ctx.language_config.summary_language,
    )

    try:
        ctx.summary_path = summarizer.summarize(
            subtitle_path=ctx.download_result["original"],
            video_title=ctx.video_info.title,
            output_dir=ctx.temp_dir,
            cancel_token=ctx.cancel_token,
        )
        msg = logger.info_i18n("summary_complete", video_id=ctx.video_info.video_id)
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
        return StageResult(success=True, should_continue=True)

    except AppException as e:
        if e.error_type == ErrorType.AI_QUOTA_EXCEEDED:
            error_msg = logger.error_i18n(
                "summary_quota_exceeded",
                error=e.message,
                video_id=ctx.video_info.video_id,
            )
            safe_log(ctx.on_log, "ERROR", error_msg, ctx.video_info.video_id)
            return StageResult(
                success=False,
                should_continue=False,
                error=error_msg,
                error_type=e.error_type,
            )
        raise


def output_stage(
    ctx: StageContext,
    output_writer: OutputWriter,
    translation_llm: Optional[LLMClient],
    summary_llm: Optional[LLMClient],
    dry_run: bool = False,
) -> StageResult:
    """阶段 5: 输出文件

    将处理结果写入输出目录

    Args:
        ctx: 阶段上下文
        output_writer: 输出写入器
        translation_llm: 翻译 LLM 客户端（用于元数据）
        summary_llm: 摘要 LLM 客户端（用于元数据）
        dry_run: 是否为干跑模式

    Returns:
        StageResult 执行结果
    """
    if dry_run:
        msg = logger.info_i18n("output_skipped", video_id=ctx.video_info.video_id)
        safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)
        return StageResult(success=True, should_continue=True)

    ctx.check_cancelled()

    msg = logger.info_i18n("output_start", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)

    output_writer.write_all(
        video_info=ctx.video_info,
        detection_result=ctx.detection_result,
        language_config=ctx.language_config,
        download_result=ctx.download_result,
        translation_result=ctx.translation_result,
        summary_path=ctx.summary_path,
        run_id=ctx.run_id,
        translation_llm=translation_llm,
        summary_llm=summary_llm,
    )

    msg = logger.info_i18n("output_complete", video_id=ctx.video_info.video_id)
    safe_log(ctx.on_log, "INFO", msg, ctx.video_info.video_id)

    return StageResult(success=True, should_continue=True)
