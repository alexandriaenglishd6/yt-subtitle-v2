"""
视频获取模块
解析频道 / 播放列表 / 单视频 / URL 列表，调用 yt-dlp 获取视频信息
"""
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse, parse_qs

from core.models import VideoInfo
from core.logger import get_logger

# 初始化 logger
logger = get_logger()


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
    
    def __init__(self, yt_dlp_path: Optional[str] = None):
        """初始化视频获取器
        
        Args:
            yt_dlp_path: yt-dlp 可执行文件路径，如果为 None 则使用系统 PATH 中的 yt-dlp
        """
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
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
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}", video_id=self.extract_video_id(url))
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
            return videos
        except Exception as e:
            logger.error(f"获取频道视频列表失败: {e}")
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
        except Exception as e:
            logger.error(f"获取播放列表视频失败: {e}")
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
        except Exception as e:
            logger.error(f"从文件读取 URL 列表失败: {e}")
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
        
        try:
            # 使用 yt-dlp 获取视频信息（JSON 格式）
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-warnings",
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"yt-dlp 执行失败: {result.stderr}")
                return None
            
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
            logger.error(f"获取视频信息超时: {url}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"解析 yt-dlp 输出失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取视频信息时出错: {e}")
            return None
    
    def _get_channel_videos_ytdlp(self, channel_url: str) -> List[VideoInfo]:
        """使用 yt-dlp 获取频道所有视频
        
        Args:
            channel_url: 频道 URL
        
        Returns:
            VideoInfo 列表
        """
        import subprocess
        import json
        
        try:
            # 使用 yt-dlp 获取频道视频列表（JSON 格式）
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-warnings",
                "--flat-playlist",
                "--playlist-end", "1000",  # 限制最多 1000 个视频（可根据需要调整）
                channel_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"yt-dlp 执行失败: {result.stderr}")
                return []
            
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
            logger.error(f"获取频道视频列表超时: {channel_url}")
            return []
        except Exception as e:
            logger.error(f"获取频道视频列表时出错: {e}")
            return []
    
    def _get_playlist_videos_ytdlp(self, playlist_url: str) -> List[VideoInfo]:
        """使用 yt-dlp 获取播放列表所有视频
        
        Args:
            playlist_url: 播放列表 URL
        
        Returns:
            VideoInfo 列表
        """
        import subprocess
        import json
        
        try:
            # 使用 yt-dlp 获取播放列表视频（JSON 格式）
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-warnings",
                "--flat-playlist",
                playlist_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.error(f"yt-dlp 执行失败: {result.stderr}")
                return []
            
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
            logger.error(f"获取播放列表视频超时: {playlist_url}")
            return []
        except Exception as e:
            logger.error(f"获取播放列表视频时出错: {e}")
            return []

