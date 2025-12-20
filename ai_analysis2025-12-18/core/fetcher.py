"""
视频获取模块
解析频道 / 播放列表 / 单视频 / URL 列表，调用 yt-dlp 获取视频信息
符合 error_handling.md 规范：将 yt-dlp 错误映射为 AppException
"""

import re
from pathlib import Path
from typing import List, Optional

from core.models import VideoInfo
from core.logger import get_logger, translate_exception
from core.exceptions import AppException, ErrorType

# 初始化 logger
logger = get_logger()


def _extract_error_message(stderr: str) -> str:
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


def _map_ytdlp_error_to_app_error(
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
    error_message = _extract_error_message(stderr)
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


class VideoFetcher:
    """视频获取器

    负责从各种 URL 类型（频道、播放列表、单视频、URL 列表）中提取视频信息
    """

    # YouTube URL 模式
    YOUTUBE_PATTERNS = {
        "video": re.compile(
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
        ),
        "channel": re.compile(r"youtube\.com/(?:c/|user/|channel/|@)([^/?]+)"),
        "playlist": re.compile(r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)"),
    }

    def __init__(
        self, yt_dlp_path: Optional[str] = None, proxy_manager=None, cookie_manager=None, quiet: bool = False
    ):
        """初始化视频获取器

        Args:
            yt_dlp_path: yt-dlp 可执行文件路径，如果为 None 则使用系统 PATH 中的 yt-dlp
            proxy_manager: ProxyManager 实例，如果为 None 则不使用代理
            cookie_manager: CookieManager 实例，如果为 None 则不使用 Cookie
            quiet: 是否进入静默模式，默认 False
        """
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        self.proxy_manager = proxy_manager
        self.cookie_manager = cookie_manager
        self.quiet = quiet
        self._check_yt_dlp()

    def _check_yt_dlp(self) -> None:
        """检查 yt-dlp 是否可用"""
        import subprocess

        try:
            result = subprocess.run(
                [self.yt_dlp_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                if not self.quiet:
                    version = result.stdout.strip()
                    logger.info_i18n("ytdlp_available", version=version)
            else:
                if not self.quiet:
                    logger.warning_i18n("ytdlp_maybe_unavailable")
        except FileNotFoundError:
            if not self.quiet:
                logger.error_i18n("ytdlp_not_found")
        except Exception as e:
            if not self.quiet:
                logger.warning_i18n("ytdlp_check_error", error=str(e))

    def identify_url_type(self, url: str) -> str:
        """识别 URL 类型

        Args:
            url: YouTube URL

        Returns:
            URL 类型：'video', 'channel', 'playlist', 'unknown'
        """
        url_lower = url.lower()

        if "watch?v=" in url_lower or "youtu.be/" in url_lower:
            return "video"
        elif "playlist?list=" in url_lower:
            return "playlist"
        elif any(x in url_lower for x in ["/c/", "/user/", "/channel/", "/@"]):
            return "channel"
        else:
            return "unknown"

    def extract_video_id(self, url: str) -> Optional[str]:
        """从 URL 中提取视频 ID

        Args:
            url: YouTube 视频 URL

        Returns:
            视频 ID，如果无法提取则返回 None
        """
        match = self.YOUTUBE_PATTERNS["video"].search(url)
        if match:
            return match.group(1)
        return None

    def fetch_from_url(self, url: str) -> List[VideoInfo]:
        """从单个 URL 获取视频信息

        自动识别 URL 类型（频道/播放列表/单视频）并获取对应的视频列表

        Args:
            url: YouTube URL（频道/播放列表/单视频）

        Returns:
            VideoInfo 列表
        """
        url_type = self.identify_url_type(url)
        logger.info_i18n("url_type_identified", url_type=url_type, url=url)

        if url_type == "video":
            return self.fetch_single_video(url)
        elif url_type == "channel":
            return self.fetch_channel(url)
        elif url_type == "playlist":
            return self.fetch_playlist(url)
        else:
            logger.error_i18n("url_type_unknown", url=url)
            return []

    def fetch_single_video(self, url: str) -> List[VideoInfo]:
        """获取单个视频信息

        Args:
            url: 视频 URL

        Returns:
            包含单个 VideoInfo 的列表
        """
        try:
            video_info = self._get_video_info_ytdlp(url)
            if video_info:
                return [video_info]
            return []
        except AppException as e:
            logger.error_i18n(
                "fetch_video_info_failed",
                error=str(e),
                video_id=self.extract_video_id(url),
            )
            return []
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=translate_exception("exception.fetch_video_info_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error_i18n(
                "fetch_video_info_failed",
                error=str(app_error),
                video_id=self.extract_video_id(url),
            )
            return []

    def fetch_channel(self, channel_url: str) -> List[VideoInfo]:
        """获取频道所有视频信息

        Args:
            channel_url: 频道 URL

        Returns:
            VideoInfo 列表
        """
        try:
            logger.info_i18n("fetching_channel_videos", url=channel_url)
            videos = self._get_channel_videos_ytdlp(channel_url)
            logger.info_i18n("channel_video_count", count=len(videos))
            if len(videos) == 0:
                logger.warning_i18n("channel_video_list_empty")
            return videos
        except AppException as e:
            logger.error_i18n(
                "fetch_channel_videos_failed",
                error=str(e),
                error_type=e.error_type.value,
            )
            return []
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=translate_exception("exception.fetch_channel_videos_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error_i18n(
                "fetch_channel_videos_failed",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            return []

    def fetch_playlist(self, playlist_url: str) -> List[VideoInfo]:
        """获取播放列表所有视频信息

        Args:
            playlist_url: 播放列表 URL

        Returns:
            VideoInfo 列表
        """
        try:
            logger.info_i18n("fetching_playlist_videos", url=playlist_url)
            videos = self._get_playlist_videos_ytdlp(playlist_url)
            logger.info_i18n("playlist_video_count", count=len(videos))
            return videos
        except AppException as e:
            logger.error_i18n(
                "fetch_playlist_videos_failed",
                error=str(e),
                error_type=e.error_type.value,
            )
            return []
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=translate_exception("exception.fetch_playlist_videos_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error_i18n(
                "fetch_playlist_videos_failed",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            return []

    def fetch_from_file(self, file_path: Path) -> List[VideoInfo]:
        """从文件读取 URL 列表并获取视频信息

        Args:
            file_path: 包含 URL 列表的文件路径（每行一个 URL）

        Returns:
            VideoInfo 列表
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip()]

            logger.info_i18n("urls_read_from_file", count=len(urls))

            all_videos = []
            for url in urls:
                videos = self.fetch_from_url(url)
                all_videos.extend(videos)

            logger.info_i18n("total_videos_fetched", count=len(all_videos))
            return all_videos
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=translate_exception("exception.read_url_file_failed", error=str(e)),
                error_type=ErrorType.FILE_IO,
                cause=e,
            )
            logger.error(
                f"{translate_exception('exception.read_url_file_failed', error=str(app_error))}",
                extra={"error_type": app_error.error_type.value},
            )
            return []
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=translate_exception("exception.read_url_file_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                f"{translate_exception('exception.read_url_file_failed', error=str(app_error))}",
                extra={"error_type": app_error.error_type.value},
            )
            return []

    def _get_video_info_ytdlp(self, url: str) -> Optional[VideoInfo]:
        """使用 yt-dlp 获取单个视频信息（带代理重试逻辑）

        Args:
            url: 视频 URL

        Returns:
            VideoInfo 对象，如果失败则返回 None
        """
        import subprocess
        import json

        max_retries = 3  # 最多尝试 3 次（包括初始尝试）
        tried_proxies = set()  # 记录已尝试的代理
        last_error = None

        for attempt in range(max_retries):
            proxy = None
            if self.proxy_manager:
                # 尝试获取下一个代理（自动跳过已标记为不健康的代理）
                proxy = self.proxy_manager.get_next_proxy(allow_direct=True)

                # 如果已经尝试过这个代理，跳过（避免重复尝试同一个不健康的代理）
                if proxy and proxy in tried_proxies:
                    # 如果所有代理都尝试过了，尝试直连
                    proxy = None
                    logger.info_i18n("all_proxies_tried_direct")

                if proxy:
                    tried_proxies.add(proxy)

            try:
                # 使用 yt-dlp 获取视频信息（JSON 格式）
                cmd = [
                    self.yt_dlp_path,
                    "--dump-json",
                    "--no-warnings",
                ]

                # 如果配置了代理，添加代理参数
                if proxy:
                    cmd.extend(["--proxy", proxy])
                    logger.debug_i18n("using_proxy", proxy=proxy)
                else:
                    logger.debug_i18n("using_direct_connection")

                # 如果配置了 Cookie，添加 Cookie 参数
                if self.cookie_manager:
                    cookie_file = self.cookie_manager.get_cookie_file_path()
                    if cookie_file:
                        cmd.extend(["--cookies", cookie_file])
                        if attempt == 0:  # 只在第一次尝试时记录 Cookie 使用
                            logger.info_i18n(
                                "using_cookie_file", cookie_file=cookie_file
                            )
                    else:
                        if attempt == 0:
                            logger.warning_i18n("cookie_manager_no_file")

                cmd.append(url)

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    error_msg = result.stderr

                    # 映射为 AppException
                    app_error = _map_ytdlp_error_to_app_error(
                        result.returncode, error_msg
                    )

                    # 如果使用了代理，标记代理失败
                    if proxy and self.proxy_manager:
                        self.proxy_manager.mark_failure(proxy, error_msg[:200])
                        logger.warning_i18n("proxy_failed_try_next", proxy=proxy)

                    last_error = app_error
                    # 如果不是最后一次尝试，继续重试
                    if attempt < max_retries - 1:
                        continue
                    else:
                        # 最后一次尝试失败，抛出异常
                        logger.error_i18n(
                            "ytdlp_execution_failed_retries",
                            retries=max_retries,
                            error=str(app_error),
                            error_type=app_error.error_type.value,
                        )
                        raise app_error

                # 如果使用了代理且成功，标记代理成功
                if proxy and self.proxy_manager:
                    self.proxy_manager.mark_success(proxy)

                # 解析 JSON
                data = json.loads(result.stdout)

                return VideoInfo(
                    video_id=data.get("id", ""),
                    url=data.get("webpage_url", url),
                    title=data.get("title", ""),
                    channel_id=data.get("channel_id"),
                    channel_name=data.get("channel"),
                    duration=data.get("duration"),
                    upload_date=data.get("upload_date"),
                    description=data.get("description"),
                )
            except subprocess.TimeoutExpired:
                # 超时错误：标记代理失败并重试
                if proxy and self.proxy_manager:
                    from core.logger import translate_log
                    self.proxy_manager.mark_failure(proxy, translate_log("timeout"))
                    logger.warning_i18n("proxy_timeout_try_next", proxy=proxy)

                last_error = AppException(
                    message=translate_exception("exception.fetch_video_info_timeout", url=url),
                    error_type=ErrorType.TIMEOUT,
                )

                # 如果不是最后一次尝试，继续重试
                if attempt < max_retries - 1:
                    continue
                else:
                    # 最后一次尝试失败，抛出异常
                    logger.error(
                        f"{translate_exception('exception.fetch_video_info_timeout', url=url)}",
                        extra={"error_type": last_error.error_type.value},
                    )
                    raise last_error
            except json.JSONDecodeError as e:
                # JSON 解析错误通常不是代理问题，直接抛出
                app_error = AppException(
                    message=translate_exception("exception.parse_ytdlp_failed", error=str(e)),
                    error_type=ErrorType.PARSE,
                    cause=e,
                )
                logger.error(
                    f"{translate_exception('exception.parse_ytdlp_failed', error=str(app_error))}",
                    extra={"error_type": app_error.error_type.value},
                )
                raise app_error
            except AppException as e:
                # 对于某些 AppException（如 CONTENT），不重试，直接抛出
                if e.error_type in [ErrorType.CONTENT, ErrorType.AUTH]:
                    raise
                # 其他错误：如果还有重试机会，继续重试
                if attempt < max_retries - 1:
                    last_error = e
                    continue
                else:
                    raise
            except Exception as e:
                app_error = AppException(
                    message=translate_exception("exception.fetch_video_info_failed", error=str(e)),
                    error_type=ErrorType.UNKNOWN,
                    cause=e,
                )
                logger.error(
                    f"{translate_exception('exception.fetch_video_info_failed', error=str(app_error))}",
                    extra={"error_type": app_error.error_type.value},
                )
                raise app_error

        # 如果所有重试都失败，抛出最后的错误
        if last_error:
            raise last_error

        # 理论上不应该到达这里
        raise AppException(
            message=translate_exception("exception.fetch_video_info_failed", error=url),
            error_type=ErrorType.UNKNOWN,
        )

    def _get_channel_videos_ytdlp(self, channel_url: str) -> List[VideoInfo]:
        """使用 yt-dlp 获取频道所有视频

        Args:
            channel_url: 频道 URL

        Returns:
            VideoInfo 列表
        """
        import subprocess
        import json

        proxy = None
        if self.proxy_manager:
            proxy = self.proxy_manager.get_next_proxy()

        try:
            # 使用 yt-dlp 获取频道视频列表（JSON 格式）
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-warnings",
                "--flat-playlist",
                "--playlist-end",
                "1000",  # 限制最多 1000 个视频（可根据需要调整）
            ]

            # 如果配置了代理，添加代理参数
            if proxy:
                cmd.extend(["--proxy", proxy])
                logger.debug_i18n("using_proxy", proxy=proxy)

            # 如果配置了 Cookie，添加 Cookie 参数
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
                    logger.debug_i18n("using_cookie")

            cmd.append(channel_url)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                error_msg = result.stderr

                # 映射为 AppException（使用改进的错误分类逻辑）
                app_error = _map_ytdlp_error_to_app_error(result.returncode, error_msg)
                logger.error_i18n(
                    "ytdlp_execution_failed",
                    error=str(app_error),
                    error_type=app_error.error_type.value,
                )

                # 如果使用了代理，标记代理失败
                if proxy and self.proxy_manager:
                    self.proxy_manager.mark_failure(proxy, error_msg[:200])

                return []

            # 如果使用了代理且成功，标记代理成功
            if proxy and self.proxy_manager:
                self.proxy_manager.mark_success(proxy)

            # 解析 JSON（每行一个视频）
            videos = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)

                    # 跳过非视频条目（如 playlist 元数据）
                    if data.get("_type") == "playlist" or not data.get("id"):
                        continue

                    # 在 flat-playlist 模式下，channel_id 和 channel 可能为 null
                    # 使用 playlist_channel_id 和 playlist_uploader 作为备选
                    channel_id = data.get("channel_id") or data.get(
                        "playlist_channel_id"
                    )
                    channel_name = (
                        data.get("channel")
                        or data.get("playlist_uploader")
                        or data.get("playlist_channel")
                    )

                    # 获取视频 URL（优先使用 webpage_url，否则使用 url，最后构造）
                    video_url = data.get("webpage_url") or data.get("url")
                    if not video_url and data.get("id"):
                        video_url = f"https://www.youtube.com/watch?v={data.get('id')}"

                    video_info = VideoInfo(
                        video_id=data.get("id", ""),
                        url=video_url or "",
                        title=data.get("title", ""),
                        channel_id=channel_id,
                        channel_name=channel_name,
                        duration=data.get("duration"),
                        upload_date=data.get("upload_date"),
                        description=None,  # flat-playlist 模式下不包含描述
                    )
                    videos.append(video_info)
                except json.JSONDecodeError:
                    continue

            return videos
        except subprocess.TimeoutExpired:
            # 超时错误：标记代理失败
            if proxy and self.proxy_manager:
                from core.logger import translate_log
                self.proxy_manager.mark_failure(proxy, translate_log("timeout"))
                logger.warning_i18n("proxy_timeout", proxy=proxy)

            app_error = AppException(
                message=translate_exception("exception.fetch_channel_videos_timeout", channel_url=channel_url),
                error_type=ErrorType.TIMEOUT,
            )
            logger.error(
                f"{translate_exception('exception.fetch_channel_videos_timeout', channel_url=channel_url)}",
                extra={"error_type": app_error.error_type.value},
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            app_error = AppException(
                message=translate_exception("exception.fetch_channel_videos_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                f"{translate_exception('exception.fetch_channel_videos_failed', error=str(app_error))}",
                extra={"error_type": app_error.error_type.value},
            )
            raise app_error

    def _get_playlist_videos_ytdlp(self, playlist_url: str) -> List[VideoInfo]:
        """使用 yt-dlp 获取播放列表所有视频

        Args:
            playlist_url: 播放列表 URL

        Returns:
            VideoInfo 列表
        """
        import subprocess
        import json

        proxy = None
        if self.proxy_manager:
            proxy = self.proxy_manager.get_next_proxy()

        try:
            # 使用 yt-dlp 获取播放列表视频（JSON 格式）
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-warnings",
                "--flat-playlist",
            ]

            # 如果配置了代理，添加代理参数
            if proxy:
                cmd.extend(["--proxy", proxy])
                logger.debug_i18n("using_proxy", proxy=proxy)

            # 如果配置了 Cookie，添加 Cookie 参数
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
                    logger.debug_i18n("using_cookie")

            cmd.append(playlist_url)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                error_msg = result.stderr

                # 映射为 AppException（使用改进的错误分类逻辑）
                app_error = _map_ytdlp_error_to_app_error(result.returncode, error_msg)
                logger.error_i18n(
                    "ytdlp_execution_failed",
                    error=str(app_error),
                    error_type=app_error.error_type.value,
                )

                # 如果使用了代理，标记代理失败
                if proxy and self.proxy_manager:
                    self.proxy_manager.mark_failure(proxy, error_msg[:200])

                return []

            # 如果使用了代理且成功，标记代理成功
            if proxy and self.proxy_manager:
                self.proxy_manager.mark_success(proxy)

            # 解析 JSON（每行一个视频）
            videos = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    video_info = VideoInfo(
                        video_id=data.get("id", ""),
                        url=data.get("url", ""),
                        title=data.get("title", ""),
                        channel_id=data.get("channel_id"),
                        channel_name=data.get("channel"),
                        duration=data.get("duration"),
                        upload_date=data.get("upload_date"),
                        description=None,  # flat-playlist 模式下不包含描述
                    )
                    videos.append(video_info)
                except json.JSONDecodeError:
                    continue

            return videos
        except subprocess.TimeoutExpired:
            # 超时错误：标记代理失败
            if proxy and self.proxy_manager:
                from core.logger import translate_log
                self.proxy_manager.mark_failure(proxy, translate_log("timeout"))
                logger.warning_i18n("proxy_timeout", proxy=proxy)

            app_error = AppException(
                message=translate_exception("exception.fetch_playlist_videos_timeout", playlist_url=playlist_url),
                error_type=ErrorType.TIMEOUT,
            )
            logger.error(
                f"{translate_exception('exception.fetch_playlist_videos_timeout', playlist_url=playlist_url)}",
                extra={"error_type": app_error.error_type.value},
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            app_error = AppException(
                message=translate_exception("exception.fetch_playlist_videos_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                f"{translate_exception('exception.fetch_playlist_videos_failed', error=str(app_error))}",
                extra={"error_type": app_error.error_type.value},
            )
            raise app_error
