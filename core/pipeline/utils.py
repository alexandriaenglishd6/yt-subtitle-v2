"""
流水线工具函数
"""

from pathlib import Path
from typing import Optional, Callable

from core.models import VideoInfo
from core.logger import get_logger
from core.exceptions import ErrorType
from core.failure_logger import FailureLogger

logger = get_logger()


def safe_log(
    on_log: Optional[Callable[[str, str, Optional[str]], None]],
    level: str,
    message: str,
    video_id: Optional[str] = None,
):
    """安全的日志回调执行

    Args:
        on_log: 日志回调函数（可能为 None）
        level: 日志级别
        message: 日志消息
        video_id: 视频 ID（可选）
    """
    if on_log:
        try:
            on_log(level, message, video_id)
        except Exception as e:
            logger.warning_i18n("log_callback_failed", error=str(e))


def cleanup_temp_dir(temp_dir: Path):
    """清理临时目录"""
    try:
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception as e:
        logger.warning_i18n("cleanup_temp_failed", error=str(e))


def handle_processing_error(
    error_msg: str,
    error_type: ErrorType,
    video_info: VideoInfo,
    failure_logger: FailureLogger,
    run_id: Optional[str],
    on_log: Optional[Callable],
    reason: str,
    dry_run: bool = False,
):
    """处理视频处理过程中的错误（统一错误处理）

    Args:
        error_msg: 错误消息
        error_type: 错误类型
        video_info: 视频信息
        failure_logger: 失败记录器
        run_id: 批次 ID
        on_log: 日志回调
        reason: 失败原因
    """
    import traceback

    # 生成清晰的错误消息（包含错误类型和原因）
    error_type_name = get_error_type_display_name(error_type)
    detailed_msg = f"[{error_type_name}] {video_info.video_id} - {reason}"

    logger.error(
        detailed_msg, video_id=video_info.video_id, error_type=error_type.value
    )
    logger.debug(traceback.format_exc(), video_id=video_info.video_id)

    safe_log(on_log, "ERROR", detailed_msg, video_info.video_id)

    if not dry_run:
        failure_logger.log_failure(
            video_id=video_info.video_id,
            url=video_info.url,
            reason=reason,
            error_type=error_type,
            batch_id=run_id,
            channel_id=video_info.channel_id,
            channel_name=video_info.channel_name,
        )


def get_error_type_display_name(error_type: ErrorType) -> str:
    """获取错误类型的显示名称

    Args:
        error_type: 错误类型

    Returns:
        错误类型的显示名称
    """
    error_type_names = {
        ErrorType.NETWORK: "网络错误",
        ErrorType.TIMEOUT: "超时",
        ErrorType.RATE_LIMIT: "限流",
        ErrorType.AUTH: "认证失败",
        ErrorType.CONTENT: "内容不可用",
        ErrorType.FILE_IO: "文件IO错误",
        ErrorType.PARSE: "解析错误",
        ErrorType.INVALID_INPUT: "输入无效",
        ErrorType.CANCELLED: "已取消",
        ErrorType.EXTERNAL_SERVICE: "外部服务错误",
        ErrorType.UNKNOWN: "未知错误",
    }
    return error_type_names.get(error_type, "未知错误")
