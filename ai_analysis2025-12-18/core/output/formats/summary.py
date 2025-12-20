"""
摘要输出格式处理
支持 TXT、MD 格式
"""

from pathlib import Path

from core.logger import get_logger
from core.exceptions import AppException, ErrorType
from core.failure_logger import _atomic_write

logger = get_logger()


def write_summary(video_dir: Path, summary_path: Path, summary_language: str) -> Path:
    """写入摘要文件

    Args:
        video_dir: 视频输出目录
        summary_path: 源摘要文件路径
        summary_language: 摘要语言代码

    Returns:
        写入的文件路径
    """
    video_dir.mkdir(parents=True, exist_ok=True)
    target_path = video_dir / f"summary.{summary_language}.md"

    try:
        # 使用原子写机制
        content = summary_path.read_text(encoding="utf-8")
        from core.logger import translate_exception
        if not _atomic_write(target_path, content, mode="w"):
            raise AppException(
                message=translate_exception("exception.atomic_write_summary_failed", path=str(target_path)),
                error_type=ErrorType.FILE_IO,
            )
        from core.logger import translate_log

        logger.debug(translate_log("summary_written", file_name=target_path.name))
        return target_path
    except (OSError, IOError, PermissionError) as e:
        # 文件IO错误
        from core.logger import translate_exception
        app_error = AppException(
            message=translate_exception("exception.write_summary_failed", error=str(e)),
            error_type=ErrorType.FILE_IO,
            cause=e,
        )
        logger.error(
            translate_exception("exception.write_summary_failed", error=str(app_error)),
            extra={"error_type": app_error.error_type.value},
        )
        raise app_error
    except AppException:
        # 重新抛出 AppException
        raise
    except Exception as e:
        # 未映射的异常，转换为 AppException
        from core.logger import translate_exception
        app_error = AppException(
            message=translate_exception("exception.write_summary_failed", error=str(e)),
            error_type=ErrorType.UNKNOWN,
            cause=e,
        )
        logger.error(
            translate_exception("exception.write_summary_failed", error=str(app_error)),
            extra={"error_type": app_error.error_type.value},
        )
        raise app_error
