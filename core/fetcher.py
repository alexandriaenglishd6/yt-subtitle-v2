"""
视频获取模块
解析频道 / 播放列表 / 单视频 / URL 列表，调用 yt-dlp 获取视频信息
符合 error_handling.md 规范：将 yt-dlp 错误映射为 AppException
"""
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse, parse_qs

from core.models import VideoInfo
from core.logger import get_logger
from core.exceptions import AppException, ErrorType

# 初始化 logger
logger = get_logger()


def _map_ytdlp_error_to_app_error(
    returncode: int,
    stderr: str,
    timeout: bool = False
) -> AppException:
    """将 yt-dlp 错误映射为 AppException
    
    符合 error_handling.md 规范：
    - 将 yt-dlp 退出码与常见 stderr 文案映射为 NETWORK / RATE_LIMIT / CONTENT / EXTERNAL_SERVICE
    
    Args:
        returncode: yt-dlp 退出码
        stderr: yt-dlp 错误输出
        timeout: 是否超时
    
    Returns:
        AppException 实例
    """
    error_lower = stderr.lower() if stderr else ""
    
    # 超时
    if timeout:
        return AppException(
            message=f"yt-dlp 执行超时",
            error_type=ErrorType.TIMEOUT
        )
    
    # 网络错误
    if any(keyword in error_lower for keyword in [
        "network", "connection", "dns", "timeout", "unreachable",
        "refused", "reset", "failed to connect"
    ]):
        return AppException(
            message=f"网络错误: {stderr[:200] if stderr else '未知网络错误'}",
            error_type=ErrorType.NETWORK
        )
    
    # 限流（429）
    if "429" in stderr or "rate limit" in error_lower or "too many requests" in error_lower:
        return AppException(
            message=f"请求频率限制: {stderr[:200] if stderr else '429 Too Many Requests'}",
            error_type=ErrorType.RATE_LIMIT
        )
    
    # 认证错误（403, 401）
    if "403" in stderr or "401" in stderr or "unauthorized" in error_lower:
        return AppException(
            message=f"认证失败: {stderr[:200] if stderr else '403/401 Unauthorized'}",
            error_type=ErrorType.AUTH
        )
    
    # 内容限制（404, 视频不可用等）
    if any(keyword in error_lower for keyword in [
        "404", "not found", "unavailable", "private", "deleted",
        "removed", "blocked", "region", "copyright"
    ]):
        return AppException(
            message=f"内容不可用: {stderr[:200] if stderr else '内容受限或不存在'}",
            error_type=ErrorType.CONTENT
        )
    
    # 其他 yt-dlp 错误（视为外部服务错误）
    return AppException(
        message=f"yt-dlp 执行失败 (退出码 {returncode}): {stderr[:200] if stderr else '未知错误'}",
        error_type=ErrorType.EXTERNAL_SERVICE
    )


class VideoFetcher:
    """视频获取器
    
    负责从各种 URL 类型（频道、播放列表、单视频、URL 列表）中提取视频信息
    """
    
    # YouTube URL 模式
    YOUTUBE_PATTERNS = {
        "video": re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"),
        "channel": re.compile(r"youtube\.com/(?:c/|user/|channel/|@)([^/?]+)"),
        "playlist": re.compile(r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)"),
    }
    
    def __init__(self, yt_dlp_path: Optional[str] = None, proxy_manager=None, cookie_manager=None):
        """初始化视频获取器
        
        Args:
            yt_dlp_path: yt-dlp 可执行文件路径，如果为 None 则使用系统 PATH 中的 yt-dlp
            proxy_manager: ProxyManager 实例，如果为 None 则不使用代理
            cookie_manager: CookieManager 实例，如果为 None 则不使用 Cookie
        """
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        self.proxy_manager = proxy_manager
        self.cookie_manager = cookie_manager
        self._check_yt_dlp()
    
    def _check_yt_dlp(self) -> None:
        """检查 yt-dlp 是否可用"""
        import subprocess
        try:
            result = subprocess.run(
                [self.yt_dlp_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"yt-dlp 可用，版本: {version}")
            else:
                logger.warning("yt-dlp 可能不可用，请确保已安装")
        except FileNotFoundError:
            logger.error(f"未找到 yt-dlp，请确保已安装并添加到 PATH，或使用 --yt-dlp-path 指定路径")
        except Exception as e:
            logger.warning(f"检查 yt-dlp 时出错: {e}")
    
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
        logger.info(f"识别 URL 类型: {url_type}, URL: {url}")
        
        if url_type == "video":
            return self.fetch_single_video(url)
        elif url_type == "channel":
            return self.fetch_channel(url)
        elif url_type == "playlist":
            return self.fetch_playlist(url)
        else:
            logger.error(f"无法识别的 URL 类型: {url}")
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
            logger.error(
                f"获取视频信息失败: {e}",
                video_id=self.extract_video_id(url),
                error_type=e.error_type.value
            )
            return []
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"获取视频信息失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"获取视频信息失败: {app_error}",
                video_id=self.extract_video_id(url),
                error_type=app_error.error_type.value
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
            logger.info(f"开始获取频道视频列表: {channel_url}")
            videos = self._get_channel_videos_ytdlp(channel_url)
            logger.info(f"频道共 {len(videos)} 个视频")
            if len(videos) == 0:
                logger.warning(f"频道视频列表为空，可能的原因：1. 频道无视频 2. 需要 Cookie 3. 网络问题 4. yt-dlp 执行失败")
            return videos
        except AppException as e:
            logger.error(
                f"获取频道视频列表失败: {e}",
                error_type=e.error_type.value
            )
            return []
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"获取频道视频列表失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            import traceback
            logger.error(
                f"获取频道视频列表失败: {app_error}\n{traceback.format_exc()}",
                error_type=app_error.error_type.value
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
            logger.info(f"开始获取播放列表视频: {playlist_url}")
            videos = self._get_playlist_videos_ytdlp(playlist_url)
            logger.info(f"播放列表共 {len(videos)} 个视频")
            return videos
        except AppException as e:
            logger.error(
                f"获取播放列表视频失败: {e}",
                error_type=e.error_type.value
            )
            return []
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"获取播放列表视频失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"获取播放列表视频失败: {app_error}",
                error_type=app_error.error_type.value
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
            
            logger.info(f"从文件读取到 {len(urls)} 个 URL")
            
            all_videos = []
            for url in urls:
                videos = self.fetch_from_url(url)
                all_videos.extend(videos)
            
            logger.info(f"总共获取到 {len(all_videos)} 个视频")
            return all_videos
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"从文件读取 URL 列表失败: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"从文件读取 URL 列表失败: {app_error}",
                error_type=app_error.error_type.value
            )
            return []
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"从文件读取 URL 列表失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"从文件读取 URL 列表失败: {app_error}",
                error_type=app_error.error_type.value
            )
            return []
    
    def _get_video_info_ytdlp(self, url: str) -> Optional[VideoInfo]:
        """使用 yt-dlp 获取单个视频信息
        
        Args:
            url: 视频 URL
        
        Returns:
            VideoInfo 对象，如果失败则返回 None
        """
        import subprocess
        import json
        
        proxy = None
        if self.proxy_manager:
            proxy = self.proxy_manager.get_next_proxy()
        
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
                logger.debug(f"使用代理: {proxy}")
            
            # 如果配置了 Cookie，添加 Cookie 参数
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
                    logger.info(f"使用 Cookie 文件: {cookie_file}")
                else:
                    logger.warning("Cookie 管理器存在，但无法获取 Cookie 文件路径")
            else:
                logger.debug("未配置 Cookie 管理器")
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = result.stderr
                
                # 映射为 AppException
                app_error = _map_ytdlp_error_to_app_error(
                    result.returncode,
                    error_msg
                )
                logger.error(
                    f"yt-dlp 执行失败: {app_error}",
                    error_type=app_error.error_type.value
                )
                
                # 如果使用了代理，标记代理失败
                if proxy and self.proxy_manager:
                    self.proxy_manager.mark_failure(proxy, error_msg[:200])
                
                # 抛出 AppException（由调用方处理）
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
                description=data.get("description")
            )
        except subprocess.TimeoutExpired:
            app_error = AppException(
                message=f"获取视频信息超时: {url}",
                error_type=ErrorType.TIMEOUT
            )
            logger.error(
                f"获取视频信息超时: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except json.JSONDecodeError as e:
            app_error = AppException(
                message=f"解析 yt-dlp 输出失败: {e}",
                error_type=ErrorType.PARSE,
                cause=e
            )
            logger.error(
                f"解析 yt-dlp 输出失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            app_error = AppException(
                message=f"获取视频信息时出错: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"获取视频信息时出错: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
    
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
                "--playlist-end", "1000",  # 限制最多 1000 个视频（可根据需要调整）
            ]
            
            # 如果配置了代理，添加代理参数
            if proxy:
                cmd.extend(["--proxy", proxy])
                logger.debug(f"使用代理: {proxy}")
            
            # 如果配置了 Cookie，添加 Cookie 参数
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
                    logger.debug("使用 Cookie")
            
            cmd.append(channel_url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                error_msg = result.stderr
                logger.error(f"yt-dlp 执行失败: {error_msg}")
                
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
                    channel_id = data.get("channel_id") or data.get("playlist_channel_id")
                    channel_name = data.get("channel") or data.get("playlist_uploader") or data.get("playlist_channel")
                    
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
                        description=None  # flat-playlist 模式下不包含描述
                    )
                    videos.append(video_info)
                except json.JSONDecodeError:
                    continue
            
            return videos
        except subprocess.TimeoutExpired:
            app_error = AppException(
                message=f"获取频道视频列表超时: {channel_url}",
                error_type=ErrorType.TIMEOUT
            )
            logger.error(
                f"获取频道视频列表超时: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            app_error = AppException(
                message=f"获取频道视频列表时出错: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"获取频道视频列表时出错: {app_error}",
                error_type=app_error.error_type.value
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
                logger.debug(f"使用代理: {proxy}")
            
            # 如果配置了 Cookie，添加 Cookie 参数
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
                    logger.debug("使用 Cookie")
            
            cmd.append(playlist_url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                error_msg = result.stderr
                logger.error(f"yt-dlp 执行失败: {error_msg}")
                
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
                        description=None  # flat-playlist 模式下不包含描述
                    )
                    videos.append(video_info)
                except json.JSONDecodeError:
                    continue
            
            return videos
        except subprocess.TimeoutExpired:
            app_error = AppException(
                message=f"获取播放列表视频超时: {playlist_url}",
                error_type=ErrorType.TIMEOUT
            )
            logger.error(
                f"获取播放列表视频超时: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            app_error = AppException(
                message=f"获取播放列表视频时出错: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"获取播放列表视频时出错: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error

