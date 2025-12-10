"""
业务逻辑模块
处理视频检测、下载、翻译、摘要等核心业务逻辑
"""
import threading
from typing import Optional, Callable
from pathlib import Path
from datetime import datetime

from core.logger import get_logger
from core.fetcher import VideoFetcher
from core.pipeline import process_video_list
from core.detector import SubtitleDetector
from core.output import OutputWriter
from core.incremental import IncrementalManager
from core.failure_logger import FailureLogger
from core.proxy_manager import ProxyManager
from core.cookie_manager import CookieManager
from core.ai_providers import create_llm_client
from core.llm_client import LLMException
from config.manager import ConfigManager
from ui.i18n_manager import t

logger = get_logger()


class VideoProcessor:
    """视频处理器
    
    封装视频检测、处理等业务逻辑
    """
    
    def __init__(self, config_manager: ConfigManager, app_config):
        self.config_manager = config_manager
        self.app_config = app_config
        self._init_components()
    
    def _init_components(self):
        """初始化核心组件"""
        # 初始化代理管理器
        if self.app_config.proxies:
            self.proxy_manager = ProxyManager(self.app_config.proxies)
            logger.info(f"已加载 {len(self.app_config.proxies)} 个代理")
        else:
            self.proxy_manager = None
            logger.info("未配置代理，将使用直连")
        
        # 初始化 Cookie 管理器
        if self.app_config.cookie:
            self.cookie_manager = CookieManager(self.app_config.cookie)
            logger.info("已加载 Cookie")
        else:
            self.cookie_manager = None
        
        # 初始化 VideoFetcher
        self.video_fetcher = VideoFetcher(
            proxy_manager=self.proxy_manager,
            cookie_manager=self.cookie_manager
        )
        
        # 初始化 OutputWriter
        output_dir = Path(self.app_config.output_dir)
        self.output_writer = OutputWriter(output_dir)
        
        # 初始化 IncrementalManager
        self.incremental_manager = IncrementalManager()
        
        # 初始化 FailureLogger
        self.failure_logger = FailureLogger(output_dir)
        
        # 初始化 LLMClient（可能失败，允许为 None）
        try:
            self.llm_client = create_llm_client(self.app_config.ai)
            logger.info(f"AI 客户端已初始化：{self.app_config.ai.provider}/{self.app_config.ai.model}")
        except LLMException as e:
            logger.warning(f"AI 客户端初始化失败，将跳过翻译和摘要：{e}")
            self.llm_client = None
    
    def dry_run(
        self,
        url: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_complete: Optional[Callable[[], None]] = None
    ):
        """执行 Dry Run（仅检测字幕）
        
        Args:
            url: 频道/播放列表 URL
            on_log: 日志回调 (level, message, video_id) - 必须在主线程中调用
            on_status: 状态更新回调 (status) - 必须在主线程中调用
            on_complete: 完成回调 - 必须在主线程中调用
        """
        def task():
            try:
                on_status(t("status_detecting"))
                on_log("INFO", t("dry_run_start", url=url))
                
                # 获取视频列表
                on_log("INFO", t("fetching_videos"))
                try:
                    videos = self.video_fetcher.fetch_from_url(url)
                except Exception as e:
                    error_detail = t("fetch_videos_failed", error=str(e))
                    on_log("ERROR", error_detail)
                    on_status(t("status_idle"))
                    return
                
                if not videos:
                    error_msg = t("no_videos_found")
                    on_log("WARN", error_msg)
                    on_status(t("status_idle"))
                    return
                
                # 保存视频列表到文件
                channel_name = videos[0].channel_name if videos else None
                channel_id = videos[0].channel_id if videos else None
                self._save_video_list(videos, url, channel_name, channel_id, on_log)
                
                on_log("INFO", t("videos_found", count=len(videos)))
                
                # 检测字幕（Dry Run：只检测，不下载，不处理）
                detector = SubtitleDetector(cookie_manager=self.cookie_manager)
                has_subtitle_count = 0
                no_subtitle_count = 0
                
                for video in videos:
                    try:
                        result = detector.detect(video)
                        if result.has_subtitles:
                            has_subtitle_count += 1
                            
                            # 分别格式化手动字幕和自动字幕
                            manual_langs = ", ".join(result.manual_languages) if result.manual_languages else t("no_subtitles_short")
                            auto_langs = ", ".join(result.auto_languages) if result.auto_languages else t("no_subtitles_short")
                            
                            # 构建显示消息
                            subtitle_info_parts = []
                            if result.manual_languages:
                                subtitle_info_parts.append(f"{t('manual_subtitles')}：{manual_langs}")
                            if result.auto_languages:
                                subtitle_info_parts.append(f"{t('auto_subtitles')}：{auto_langs}")
                            
                            subtitle_info = " | ".join(subtitle_info_parts)
                            on_log("INFO", 
                                t("subtitle_detected", video_id=video.video_id, title=video.title[:50], subtitle_info=subtitle_info),
                                video_id=video.video_id)
                        else:
                            no_subtitle_count += 1
                            on_log("WARN",
                                t("no_subtitle", video_id=video.video_id, title=video.title[:50]),
                                video_id=video.video_id)
                    except Exception as e:
                        on_log("ERROR",
                            t("subtitle_detect_failed", video_id=video.video_id, error=str(e)),
                            video_id=video.video_id)
                
                # 显示统计结果
                on_log("INFO", t("detection_complete", has_count=has_subtitle_count, no_count=no_subtitle_count))
                on_status(t("status_idle"))
                
                if on_complete:
                    on_complete()
            
            except Exception as e:
                import traceback
                logger.error(f"Dry Run 失败: {e}\n{traceback.format_exc()}")
                on_log("ERROR", f"Dry Run 失败：{e}")
                on_status(t("status_idle"))
        
        thread = threading.Thread(target=task, daemon=True)
        thread.start()
        return thread
    
    def process_videos(
        self,
        url: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_stats: Callable[[dict], None],
        on_complete: Optional[Callable[[], None]] = None
    ):
        """处理视频（下载、翻译、摘要）
        
        Args:
            url: 频道/播放列表 URL
            on_log: 日志回调 (level, message, video_id)
            on_status: 状态更新回调 (status)
            on_stats: 统计信息更新回调 (stats_dict)
            on_complete: 完成回调
        """
        def task():
            try:
                # 确保回调函数被调用
                logger.info(f"[GUI] 处理任务线程已启动，URL: {url}")
                on_status("处理中...")
                on_log("INFO", f"开始处理：{url}")
                
                # 获取视频列表
                on_log("INFO", "正在获取视频列表（可能需要一些时间）...")
                logger.info(f"[GUI] 开始获取视频列表：{url}")
                videos = self.video_fetcher.fetch_from_url(url)
                logger.info(f"[GUI] 获取到 {len(videos) if videos else 0} 个视频")
                
                if not videos:
                    error_msg = (
                        "未获取到任何视频。可能的原因：\n"
                        "1. 频道 URL 不正确或格式错误\n"
                        "2. 需要 Cookie 才能访问（请在配置中添加 Cookie）\n"
                        "3. 网络连接问题或超时\n"
                        "4. yt-dlp 执行失败（请查看日志文件获取详细错误信息）\n"
                        "提示：请检查日志文件中的错误信息，或尝试在配置中添加 Cookie"
                    )
                    on_log("ERROR", error_msg)
                    on_status(t("status_idle"))
                    if on_complete:
                        on_complete()
                    return
                
                # 保存视频列表到文件
                channel_name = videos[0].channel_name if videos else None
                channel_id = videos[0].channel_id if videos else None
                self._save_video_list(videos, url, channel_name, channel_id, on_log)
                
                # 获取 archive 路径（用于增量处理）
                archive_path = self.incremental_manager.get_or_create_channel_archive(channel_id)
                
                # 检查是否强制重跑（暂时从 UI 读取，P0-25 会完善）
                force = False  # TODO: 从 UI 读取强制重跑选项
                
                # 更新统计信息
                stats = {
                    "total": len(videos),
                    "success": 0,
                    "failed": 0,
                    "current": 0
                }
                on_stats(stats)
                
                on_log("INFO", f"共 {len(videos)} 个视频，开始处理...")
                
                # 调用核心流水线（传递 on_stats 和 on_log 回调以实时更新进度和错误）
                result = process_video_list(
                    videos=videos,
                    language_config=self.app_config.language,
                    llm=self.llm_client,
                    output_writer=self.output_writer,
                    failure_logger=self.failure_logger,
                    incremental_manager=self.incremental_manager,
                    archive_path=archive_path,
                    force=force,
                    concurrency=self.app_config.concurrency,
                    proxy_manager=self.proxy_manager,
                    cookie_manager=self.cookie_manager,
                    on_stats=on_stats,  # 传递统计信息回调
                    on_log=on_log  # 传递日志回调，用于显示错误信息
                )
                
                # 更新统计信息
                stats["success"] = result.get("success", 0)
                stats["failed"] = result.get("failed", 0)
                stats["current"] = stats["total"]
                on_stats(stats)
                
                # 显示完成消息
                if stats["failed"] > 0:
                    # 如果有失败，显示详细的错误信息
                    errors = result.get("errors", [])
                    if errors:
                        error_summary = f"处理完成：成功 {stats['success']} 个，失败 {stats['failed']} 个。失败详情请查看上方错误日志。"
                    else:
                        error_summary = f"处理完成：成功 {stats['success']} 个，失败 {stats['failed']} 个"
                    on_log("WARN", error_summary)
                else:
                    on_log("INFO", f"处理完成：成功 {stats['success']} 个，失败 {stats['failed']} 个")
                on_status(t("status_idle"))
                
                if on_complete:
                    on_complete()
                
            except Exception as e:
                import traceback
                error_msg = f"处理失败：{e}\n{traceback.format_exc()}"
                on_log("ERROR", error_msg)
                on_status(t("status_idle"))
                if on_complete:
                    on_complete()
        
        thread = threading.Thread(target=task, daemon=True)
        thread.start()
        return thread
    
    def _save_video_list(self, videos: list, source_url: str, channel_name: Optional[str] = None, 
                        channel_id: Optional[str] = None, on_log: Optional[Callable] = None):
        """保存视频列表到文件（追加模式）"""
        try:
            output_dir = Path(self.app_config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            video_list_file = output_dir / "video_list.txt"
            
            # 构建分隔符
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            separator_parts = [f"# {timestamp}"]
            
            if channel_name and channel_id:
                separator_parts.append(f"频道: {channel_name} [{channel_id}]")
            elif channel_id:
                separator_parts.append(f"频道 ID: {channel_id}")
            else:
                separator_parts.append(f"来源: {source_url}")
            
            separator_parts.append(f"视频数量: {len(videos)}")
            separator = " | ".join(separator_parts)
            
            # 追加模式写入
            with open(video_list_file, "a", encoding="utf-8") as f:
                f.write("\n")
                f.write(separator + "\n")
                for video in videos:
                    f.write(video.url + "\n")
                f.write("# " + "=" * 60 + "\n")  # 结束分隔符
            
            logger.info(f"已保存 {len(videos)} 个视频链接到: {video_list_file}")
            if on_log:
                on_log("INFO", f"已保存 {len(videos)} 个视频链接到: {video_list_file.name}")
        except Exception as e:
            logger.error(f"保存视频列表失败: {e}")
            if on_log:
                on_log("WARN", f"保存视频列表失败: {e}")

