"""
yt-dlp 错误映射模块

从 fetcher.py 提取，专注于将 yt-dlp 错误映射为 AppException。
遵循 error_handling.md 规范。
"""

from core.exceptions import AppException, ErrorType
from core.logger import translate_exception


def extract_error_message(stderr: str) -> str:
    """从 yt-dlp 的 stderr 中提取真正的错误消息，过滤掉警告

    Args:
        stderr: yt-dlp 的错误输出（可能包含 WARNING 和 ERROR）

    Returns:
        只包含 ERROR 消息的字符串
    """
    if not stderr:
        return ""

    lines = stderr.split("\n")
    error_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 跳过 WARNING 消息
        if line.startswith("WARNING:"):
            continue

        # 保留 ERROR 消息和其他非警告消息
        if line.startswith("ERROR:") or not line.startswith("WARNING"):
            error_lines.append(line)

    # 如果没有找到 ERROR 消息，返回原始 stderr（可能包含其他重要信息）
    if not error_lines:
        return stderr

    return "\n".join(error_lines)


def map_ytdlp_error_to_app_error(
    returncode: int, stderr: str, timeout: bool = False
) -> AppException:
    """将 yt-dlp 错误映射为 AppException

    符合 error_handling.md 规范：
    - 将 yt-dlp 退出码与常见 stderr 文案映射为 NETWORK / RATE_LIMIT / CONTENT / EXTERNAL_SERVICE

    Args:
        returncode: yt-dlp 退出码
        stderr: yt-dlp 错误输出（可能包含 WARNING 和 ERROR）
        timeout: 是否超时

    Returns:
        AppException 实例
    """
    # 提取真正的错误消息（过滤掉警告）
    error_message = extract_error_message(stderr)
    error_lower = (
        error_message.lower() if error_message else (stderr.lower() if stderr else "")
    )

    # 超时
    if timeout:
        return AppException(
            message=translate_exception("exception.ytdlp_timeout"),
            error_type=ErrorType.TIMEOUT,
        )

    # 网络错误
    # 包括直接的网络连接错误，以及因网络问题导致的下载失败
    network_keywords = [
        "network",
        "connection",
        "dns",
        "timeout",
        "unreachable",
        "refused",
        "reset",
        "failed to connect",
        "connection error",
        "connection refused",
        "connection timeout",
        "connection reset",
        "unable to connect",
        "cannot connect",
        "connect failed",
        # 下载失败相关（可能是网络问题导致）
        "failed to download",
        "unable to download",
        "download failed",
        "download error",
        "cannot download",
        "unable to fetch",
        # 网页下载失败导致的认证检查失败（通常是网络问题）
        "without a successful webpage download",
        "webpage download failed",
        "unable to download webpage",
        "failed to download webpage",
    ]
    if any(keyword in error_lower for keyword in network_keywords):
        # 使用提取的错误消息，如果没有则使用原始 stderr
        msg = (
            error_message[:200]
            if error_message
            else (
                stderr[:200]
                if stderr
                else translate_exception("exception.unknown_network_error")
            )
        )
        return AppException(
            message=translate_exception("exception.network_error_prefix", msg=msg),
            error_type=ErrorType.NETWORK,
        )

    # 认证检查失败，但可能是由网络问题导致的（需要检查是否涉及网页下载失败）
    # 如果错误信息包含 "authentication" 且涉及 "webpage download" 失败，归类为网络错误
    if "authentication" in error_lower and any(
        keyword in error_lower
        for keyword in [
            "webpage download",
            "download webpage",
            "webpage",
            "without a successful",
        ]
    ):
        # 使用提取的错误消息，如果没有则使用原始 stderr
        msg = (
            error_message[:200]
            if error_message
            else (
                stderr[:200]
                if stderr
                else translate_exception("exception.unknown_network_error")
            )
        )
        return AppException(
            message=translate_exception("exception.auth_check_failed_network", msg=msg),
            error_type=ErrorType.NETWORK,
        )

    # 限流（429）
    if (
        "429" in stderr
        or "rate limit" in error_lower
        or "too many requests" in error_lower
    ):
        msg = (
            error_message[:200]
            if error_message
            else (stderr[:200] if stderr else "429 Too Many Requests")
        )
        return AppException(
            message=translate_exception("exception.rate_limit_prefix", msg=msg),
            error_type=ErrorType.RATE_LIMIT,
        )

    # 认证错误（403, 401）
    # 包括 Cookie 认证失败（YouTube 要求登录）
    # 细分：Cookie 已失效/过期
    cookie_expired_keywords = [
        "sign in to confirm",
        "you're not a bot",
        "not a bot",
        "use --cookies",
        "cookies for the authentication",
        "login required",
    ]
    if any(keyword in error_lower for keyword in cookie_expired_keywords):
        msg = (
            error_message[:200]
            if error_message
            else (
                stderr[:200]
                if stderr
                else translate_exception("exception.auth_failed_cookie_required")
            )
        )
        return AppException(
            message=translate_exception("exception.cookie_expired", msg=msg),
            error_type=ErrorType.COOKIE_EXPIRED,
        )

    auth_keywords = [
        "403",
        "401",
        "unauthorized",
        "authentication required",
    ]
    if any(keyword in error_lower for keyword in auth_keywords):
        msg = (
            error_message[:200]
            if error_message
            else (
                stderr[:200]
                if stderr
                else translate_exception("exception.auth_failed")
            )
        )
        return AppException(
            message=translate_exception("exception.auth_failed_cookie_required", msg=msg),
            error_type=ErrorType.AUTH,
        )

    # 内容限制（404, 视频不可用等）
    if any(
        keyword in error_lower
        for keyword in [
            "404",
            "not found",
            "unavailable",
            "private",
            "deleted",
            "removed",
            "blocked",
            "region",
            "copyright",
        ]
    ):
        msg = (
            error_message[:200]
            if error_message
            else (
                stderr[:200]
                if stderr
                else translate_exception("exception.content_unavailable")
            )
        )
        return AppException(
            message=translate_exception("exception.content_unavailable_prefix", msg=msg),
            error_type=ErrorType.CONTENT,
        )

    # Cookie 文件格式错误（归类为认证错误）
    if (
        "does not look like a netscape format" in error_lower
        or "cookie" in error_lower
        and "format" in error_lower
    ):
        msg = (
            error_message[:200]
            if error_message
            else (
                stderr[:200]
                if stderr
                else translate_exception("exception.cookie_format_error")
            )
        )
        return AppException(
            message=translate_exception("exception.cookie_format_error_prefix", msg=msg),
            error_type=ErrorType.AUTH,
        )

    # 其他 yt-dlp 错误（视为外部服务错误）
    msg = (
        error_message[:200]
        if error_message
        else (
            stderr[:200]
            if stderr
            else translate_exception("exception.unknown_error_prefix", msg="")
        )
    )
    # 使用翻译键格式，日志系统会自动翻译
    translated_msg = translate_exception(
        "exception.ytdlp_execution_failed", returncode=returncode, error=msg
    )
    return AppException(message=translated_msg, error_type=ErrorType.EXTERNAL_SERVICE)


# 便于导入的别名（保持向后兼容）
__all__ = ["extract_error_message", "map_ytdlp_error_to_app_error"]
