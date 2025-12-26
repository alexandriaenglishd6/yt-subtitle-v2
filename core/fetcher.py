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
from core.ytdlp_errors import extract_error_message as _extract_error_message
from core.ytdlp_errors import map_ytdlp_error_to_app_error as _map_ytdlp_error_to_app_error
from core.url_parser import (
    identify_url_type as _identify_url_type,
    extract_video_id as _extract_video_id,
    YOUTUBE_PATTERNS,
)
from core.subprocess_utils import run_command, get_subprocess_kwargs

# 初始化 logger
logger = get_logger()



class VideoFetcher:
    """视频获取器

    负责从各种 URL 类型（频道、播放列表、单视频、URL 列表）中提取视频信息
    """

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
            result = run_command(
                [self.yt_dlp_path, "--version"],
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
        """识别 URL 类型（委托给 url_parser 模块）"""
        return _identify_url_type(url)

    def extract_video_id(self, url: str) -> Optional[str]:
        """从 URL 中提取视频 ID（委托给 url_parser 模块）"""
        return _extract_video_id(url)

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

    def fetch_from_file(self, file_path: Path, fetch_concurrency: int = 5) -> List[VideoInfo]:
        """从文件读取 URL 列表并获取视频信息（并发）

        Args:
            file_path: 包含 URL 列表的文件路径（每行一个 URL）
            fetch_concurrency: 获取视频信息的并发数（默认 5）

        Returns:
            VideoInfo 列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                urls = [line.strip() for line in f if line.strip()]

            logger.info_i18n("urls_read_from_file", count=len(urls))

            all_videos = []
            
            # 使用线程池并发获取视频信息
            with ThreadPoolExecutor(max_workers=fetch_concurrency, thread_name_prefix="fetch") as executor:
                # 提交所有任务
                future_to_url = {executor.submit(self.fetch_from_url, url): url for url in urls}
                
                # 收集结果（按完成顺序）
                for future in as_completed(future_to_url):
                    # 检查取消状态
                    if hasattr(self, 'cancel_token') and self.cancel_token and self.cancel_token.is_cancelled():
                        logger.info_i18n("log.cancel_signal_detected")
                        # 取消所有未完成的任务
                        for f in future_to_url:
                            f.cancel()
                        break
                    
                    url = future_to_url[future]
                    try:
                        videos = future.result()
                        all_videos.extend(videos)
                    except Exception as e:
                        logger.warning(f"获取 URL 失败: {url} - {e}")

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

                # 注意：不再检查 tried_proxies，允许同一个代理重试多次
                # 只有当 get_next_proxy 返回 None（所有代理都不健康）时才使用直连
                if proxy:
                    if proxy in tried_proxies:
                        # 同一个代理重试，记录日志
                        logger.debug(f"重试代理: {proxy} (尝试 {attempt + 1}/{max_retries})")
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
                    # 只在第一次使用时记录 INFO 日志，避免重复输出
                    if attempt == 0:
                        logger.info_i18n("using_proxy", proxy=proxy)
                else:
                    if attempt == 0:
                        logger.info_i18n("using_direct_connection")

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

                result = run_command(cmd, timeout=60)

                if result.returncode != 0:
                    error_msg = result.stderr

                    # 映射为 AppException
                    app_error = _map_ytdlp_error_to_app_error(
                        result.returncode, error_msg
                    )

                    # 只在真正的代理/网络错误时标记代理失败
                    # Cookie 过期、视频不可用等不是代理问题，不应影响代理健康度
                    if proxy and self.proxy_manager:
                        error_lower = error_msg.lower() if error_msg else ""
                        is_proxy_error = any(keyword in error_lower for keyword in [
                            "unable to connect",
                            "connection refused",
                            "connection timeout",
                            "network is unreachable",
                            "proxy",
                            "socks",
                            "timed out",
                            "connect failed",
                        ])
                        if is_proxy_error:
                            self.proxy_manager.mark_failure(proxy, error_msg[:200])
                            logger.warning_i18n("proxy_failed_try_next", proxy=proxy)
                            # 添加详细错误信息
                            logger.debug(f"代理失败详情: {error_msg[:500]}")
                        else:
                            # 非代理错误，记录详情但不标记代理失败
                            logger.debug(f"yt-dlp 错误（非代理问题）: {error_msg[:200]}")

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

            result = run_command(cmd, timeout=120)

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

            result = run_command(cmd, timeout=120)

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
