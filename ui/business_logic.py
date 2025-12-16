"""
业务逻辑模块
处理视频检测、下载、翻译、摘要等核心业务逻辑
"""
import threading
from typing import Optional, Callable, List, Tuple
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
from core.cancel_token import CancelToken
from core.models import VideoInfo
from config.manager import ConfigManager
from ui.i18n_manager import t

logger = get_logger()

# 常量定义
MAX_TITLE_DISPLAY_LENGTH = 50


class VideoProcessor:
    """视频处理器
    
    封装视频检测、处理等业务逻辑
    """
    
    def __init__(self, config_manager: ConfigManager, app_config):
        self.config_manager = config_manager
        self.app_config = app_config
        # 初始化取消令牌（初始为 None，任务开始时创建）
        self.cancel_token: Optional[CancelToken] = None
        self._init_components()
    
    def _init_components(self):
        """初始化核心组件"""
        # 初始化代理管理器
        if self.app_config.proxies:
            self.proxy_manager = ProxyManager(self.app_config.proxies)
            logger.info(t("proxies_loaded", count=len(self.app_config.proxies)))
        else:
            self.proxy_manager = None
            logger.info(t("no_proxy"))
        
        # 初始化 Cookie 管理器
        if self.app_config.cookie:
            self.cookie_manager = CookieManager(self.app_config.cookie)
            logger.info(t("cookie_loaded"))
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
        
        # 初始化翻译 LLMClient（可能失败，允许为 None）
        # 优先使用 AI Profile 配置，如果未配置则使用原有的 translation_ai 配置
        from core.ai_profile_manager import get_profile_manager
        
        profile_manager = get_profile_manager()
        
        self.translation_llm_init_error = None  # 保存初始化失败的原因
        self.translation_llm_init_error_type = None  # 保存初始化失败的错误类型
        
        # 获取翻译 AI 配置（优先使用 Profile）
        translation_ai_config = profile_manager.get_ai_config_for_task(
            "subtitle_translate",
            fallback_config=self.app_config.translation_ai if self.app_config.translation_ai.enabled else None
        )
        
        if translation_ai_config and translation_ai_config.enabled:
            try:
                self.translation_llm_client = create_llm_client(translation_ai_config)
                profile_name = profile_manager.task_mapping.get("subtitle_translate", t("profile_default"))
                logger.info(t("translation_ai_client_init_success", 
                             provider=translation_ai_config.provider, 
                             model=translation_ai_config.model) + f" (Profile: {profile_name})")
            except LLMException as e:
                # 翻译异常消息
                error_msg = str(e)
                # 如果异常消息看起来像翻译键，尝试翻译
                if error_msg.startswith("exception."):
                    from core.logger import translate_exception
                    # 尝试解析翻译键和参数
                    if ":" in error_msg:
                        key_part = error_msg.split(":")[0]
                        # 简单解析参数（格式：key:param1=value1,param2=value2）
                        params = {}
                        if ":" in error_msg:
                            param_str = error_msg.split(":", 1)[1]
                            for param in param_str.split(","):
                                if "=" in param:
                                    k, v = param.split("=", 1)
                                    params[k.strip()] = v.strip()
                        error_msg = translate_exception(key_part, **params)
                    else:
                        error_msg = translate_exception(error_msg)
                logger.warning(t("translation_ai_client_init_failed", error=error_msg))
                self.translation_llm_client = None
                # 保存初始化失败的原因和错误类型（用于后续提示和错误分类）
                self.translation_llm_init_error = str(e)
                # 将 LLMErrorType 映射为 ErrorType
                from core.exceptions import ErrorType, map_llm_error_to_app_error
                self.translation_llm_init_error_type = map_llm_error_to_app_error(e.error_type.value)
        else:
            logger.info(t("translation_ai_disabled"))
            self.translation_llm_client = None
            self.translation_llm_init_error = "翻译 AI 未启用"
            self.translation_llm_init_error_type = None
        
        # 初始化摘要 LLMClient（可能失败，允许为 None）
        # 优先使用 AI Profile 配置，如果未配置则使用原有的 summary_ai 配置
        summary_ai_config = profile_manager.get_ai_config_for_task(
            "subtitle_summarize",
            fallback_config=self.app_config.summary_ai if self.app_config.summary_ai.enabled else None
        )
        
        if summary_ai_config and summary_ai_config.enabled:
            try:
                self.summary_llm_client = create_llm_client(summary_ai_config)
                profile_name = profile_manager.task_mapping.get("subtitle_summarize", t("profile_default"))
                logger.info(t("summary_ai_client_init_success", 
                             provider=summary_ai_config.provider, 
                             model=summary_ai_config.model) + f" (Profile: {profile_name})")
            except LLMException as e:
                # 翻译异常消息
                error_msg = str(e)
                # 如果异常消息看起来像翻译键，尝试翻译
                if error_msg.startswith("exception."):
                    from core.logger import translate_exception
                    # 尝试解析翻译键和参数
                    if ":" in error_msg:
                        key_part = error_msg.split(":")[0]
                        # 简单解析参数（格式：key:param1=value1,param2=value2）
                        params = {}
                        if ":" in error_msg:
                            param_str = error_msg.split(":", 1)[1]
                            for param in param_str.split(","):
                                if "=" in param:
                                    k, v = param.split("=", 1)
                                    params[k.strip()] = v.strip()
                        error_msg = translate_exception(key_part, **params)
                    else:
                        error_msg = translate_exception(error_msg)
                logger.warning(t("summary_ai_client_init_failed", error=error_msg))
                self.summary_llm_client = None
        else:
            logger.info(t("summary_ai_disabled"))
            self.summary_llm_client = None
        
        # 向后兼容：保留 llm_client 属性（指向 translation_llm_client）
        self.llm_client = self.translation_llm_client
    
    # ============================================================
    # 公共方法：视频获取和保存
    # ============================================================
    
    def _fetch_videos(
        self,
        url: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None]
    ) -> Optional[List[VideoInfo]]:
        """获取视频列表（公共方法）
        
        Args:
            url: 频道/播放列表 URL
            on_log: 日志回调
            on_status: 状态回调
        
        Returns:
            视频列表，如果失败则返回 None
        """
        on_log("INFO", t("fetching_videos"))
        try:
            videos = self.video_fetcher.fetch_from_url(url)
        except Exception as e:
            on_log("ERROR", t("fetch_videos_failed", error=str(e)))
            on_status(t("status_idle"))
            return None
        
        if not videos:
            on_log("WARN", t("no_videos_found"))
            on_status(t("status_idle"))
            return None
        
        return videos
    
    def _fetch_videos_from_url_list(
        self,
        urls_text: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None]
    ) -> Optional[List[VideoInfo]]:
        """从 URL 列表文本获取视频列表（公共方法）
        
        Args:
            urls_text: 多行 URL 文本（每行一个 URL）
            on_log: 日志回调
            on_status: 状态回调
        
        Returns:
            视频列表，如果失败则返回 None
        """
        on_log("INFO", t("fetching_videos"))
        
        # 将多行文本写入临时文件
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt') as f:
                # 解析多行文本，每行一个 URL
                urls = [line.strip() for line in urls_text.split('\n') if line.strip()]
                if not urls:
                    on_log("WARN", t("url_list_empty"))
                    on_status(t("status_idle"))
                    return None
                
                for url in urls:
                    f.write(url + '\n')
                temp_file_path = Path(f.name)
            
            try:
                videos = self.video_fetcher.fetch_from_file(temp_file_path)
            finally:
                # 清理临时文件
                try:
                    temp_file_path.unlink()
                except Exception:
                    pass
            
            if not videos:
                on_log("WARN", t("no_videos_found"))
                on_status(t("status_idle"))
                return None
            
            return videos
        except Exception as e:
            on_log("ERROR", t("fetch_videos_failed", error=str(e)))
            on_status(t("status_idle"))
            return None
    
    def _save_video_list(
        self,
        videos: List[VideoInfo],
        source_url: str,
        channel_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        on_log: Optional[Callable] = None
    ):
        """保存视频列表到文件（追加模式）"""
        try:
            output_dir = Path(self.app_config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            video_list_file = output_dir / "video_list.txt"
            
            # 构建分隔符
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            separator_parts = [f"# {timestamp}"]
            
            if channel_name and channel_id:
                separator_parts.append(f"Channel: {channel_name} [{channel_id}]")
            elif channel_id:
                separator_parts.append(f"Channel ID: {channel_id}")
            else:
                separator_parts.append(f"Source: {source_url}")
            
            separator_parts.append(f"Count: {len(videos)}")
            separator = " | ".join(separator_parts)
            
            # 追加模式写入
            with open(video_list_file, "a", encoding="utf-8") as f:
                f.write("\n")
                f.write(separator + "\n")
                for video in videos:
                    f.write(video.url + "\n")
                f.write("# " + "=" * 60 + "\n")
            
            logger.info(t("video_list_saved", count=len(videos), filename=video_list_file.name))
            if on_log:
                on_log("INFO", t("video_list_saved", count=len(videos), filename=video_list_file.name))
        except Exception as e:
            logger.error(t("save_video_list_failed", error=str(e)))
            if on_log:
                on_log("WARN", t("save_video_list_failed", error=str(e)))
    
    # ============================================================
    # 基础任务执行框架
    # ============================================================
    
    def _run_task_in_thread(
        self,
        task_fn: Callable[[], None],
        on_status: Callable[[str], None],
        on_complete: Optional[Callable[[], None]] = None
    ) -> threading.Thread:
        """在后台线程中执行任务
        
        Args:
            task_fn: 要执行的任务函数
            on_status: 状态回调
            on_complete: 完成回调
        
        Returns:
            启动的线程对象
        """
        def wrapper():
            try:
                task_fn()
            except Exception as e:
                import traceback
                logger.error(f"Task failed: {e}\n{traceback.format_exc()}")
            finally:
                on_status(t("status_idle"))
                if on_complete:
                    on_complete()
        
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return thread
    
    # ============================================================
    # Dry Run 模式
    # ============================================================
    
    def dry_run(
        self,
        url: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_complete: Optional[Callable[[], None]] = None,
        force: bool = False
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
                videos = self._fetch_videos(url, on_log, on_status)
                if not videos:
                    return
                
                # 保存视频列表到文件
                channel_name = videos[0].channel_name if videos else None
                channel_id = videos[0].channel_id if videos else None
                self._save_video_list(videos, url, channel_name, channel_id, on_log)
                
                on_log("INFO", t("videos_found", count=len(videos)))
                
                # 执行字幕检测（Dry Run 模式）
                channel_name = videos[0].channel_name if videos else None
                channel_id = videos[0].channel_id if videos else None
                self._detect_subtitles(videos, on_log, source_url=url, channel_name=channel_name, channel_id=channel_id, dry_run=True)
            except Exception as e:
                import traceback
                error_msg = f"{t('dry_run_failed', error=str(e))}"
                logger.error(f"Dry Run failed: {e}\n{traceback.format_exc()}")
                on_log("ERROR", error_msg)
        
        return self._run_task_in_thread(task, on_status, on_complete)
    
    def _detect_subtitles(
        self,
        videos: List[VideoInfo],
        on_log: Callable[[str, str, Optional[str]], None],
        source_url: Optional[str] = None,
        channel_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        dry_run: bool = False
    ) -> Tuple[int, int]:
        """检测视频字幕（Dry Run 核心逻辑）
        
        Args:
            videos: 视频列表
            on_log: 日志回调
            source_url: 来源 URL（可选）
            channel_name: 频道名称（可选）
            channel_id: 频道 ID（可选）
            dry_run: 是否为 Dry Run 模式（Dry Run 模式下不写入文件）
        
        Returns:
            (有字幕数, 无字幕数)
        """
        detector = SubtitleDetector(cookie_manager=self.cookie_manager)
        has_subtitle_count = 0
        no_subtitle_count = 0
        
        # 用于分类保存的列表
        videos_with_subtitle = []
        videos_without_subtitle = []
        
        try:
            on_log("INFO", t("detection_starting", count=len(videos)))
        except Exception as log_err:
            logger.error(f"on_log callback failed: {log_err}")
        
        for i, video in enumerate(videos, 1):
            try:
                result = detector.detect(video)
                progress_prefix = f"[{i}/{len(videos)}]"
                
                if result.has_subtitles:
                    has_subtitle_count += 1
                    videos_with_subtitle.append(video)
                    
                    # 详细输出字幕信息 - 使用 try-except 保护 on_log 调用
                    try:
                        on_log("INFO", 
                            f"{progress_prefix} ✓ {video.video_id} - {video.title[:MAX_TITLE_DISPLAY_LENGTH]}",
                            video_id=video.video_id)
                        
                        # 显示手动字幕详情
                        if result.manual_languages:
                            manual_list = ", ".join(result.manual_languages)
                            on_log("INFO", 
                                f"    {t('manual_subtitles')} ({len(result.manual_languages)}): {manual_list}",
                                video_id=video.video_id)
                        
                        # 显示自动字幕详情
                        if result.auto_languages:
                            auto_list = ", ".join(result.auto_languages)
                            on_log("INFO", 
                                f"    {t('auto_subtitles')} ({len(result.auto_languages)}): {auto_list}",
                                video_id=video.video_id)
                    except Exception as log_err:
                        logger.error(f"on_log callback failed for video {video.video_id}: {log_err}")
                else:
                    no_subtitle_count += 1
                    videos_without_subtitle.append(video)
                    try:
                        on_log("WARN",
                            f"{progress_prefix} ✗ {video.video_id} - {video.title[:MAX_TITLE_DISPLAY_LENGTH]} - {t('no_subtitle_available')}",
                            video_id=video.video_id)
                    except Exception as log_err:
                        logger.error(f"on_log callback failed for video {video.video_id}: {log_err}")
            except Exception as e:
                no_subtitle_count += 1
                videos_without_subtitle.append(video)
                try:
                    on_log("ERROR",
                        f"[{i}/{len(videos)}] ✗ {video.video_id} - {t('subtitle_detect_failed_short', error=str(e))}",
                        video_id=video.video_id)
                except Exception as log_err:
                    logger.error(f"on_log callback failed: {log_err}")
        
        # 保存分类结果到文件（使用传入的参数，Dry Run 模式下跳过）
        self._save_detection_results(
            videos_with_subtitle, 
            videos_without_subtitle, 
            on_log,
            source_url=source_url,
            channel_name=channel_name,
            channel_id=channel_id,
            dry_run=dry_run
        )
        
        # 显示统计结果
        try:
            on_log("INFO", "=" * 50)
            on_log("INFO", t("detection_complete", has_count=has_subtitle_count, no_count=no_subtitle_count))
            on_log("INFO", "=" * 50)
        except Exception as log_err:
            logger.error(f"on_log callback failed for summary: {log_err}")
        
        return has_subtitle_count, no_subtitle_count
    
    def _save_detection_results(
        self,
        videos_with_subtitle: List[VideoInfo],
        videos_without_subtitle: List[VideoInfo],
        on_log: Callable[[str, str, Optional[str]], None],
        source_url: Optional[str] = None,
        channel_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        dry_run: bool = False
    ):
        """保存检测结果到文件（追加模式，带分隔符）
        
        Args:
            videos_with_subtitle: 有字幕的视频列表
            videos_without_subtitle: 无字幕的视频列表
            on_log: 日志回调
            source_url: 来源 URL（可选）
            channel_name: 频道名称（可选）
            channel_id: 频道 ID（可选）
            dry_run: 是否为 Dry Run 模式（仅用于日志标记，不影响文件保存）
        
        说明：
        - Dry Run 模式下也会保存检测结果（with_subtitle.txt / without_subtitle.txt）
        - 这些文件是检测结果的记录，不属于"报告文件"，保存有助于用户了解检测情况
        - Dry Run 模式下仍然不会：下载字幕、翻译、摘要、更新 Archive
        """
        from datetime import datetime
        from pathlib import Path
        from ui.i18n_manager import t
        from core.failure_logger import _append_line_safe
        
        output_dir = Path(self.app_config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 固定文件名（追加模式）
        with_subtitle_file = output_dir / "with_subtitle.txt"
        without_subtitle_file = output_dir / "without_subtitle.txt"
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建分隔符信息
        separator_parts = [f"# {timestamp}"]
        if dry_run:
            separator_parts.append("[Dry Run]")
        if channel_name and channel_id:
            separator_parts.append(f"频道: {channel_name} [{channel_id}]")
        elif channel_id:
            separator_parts.append(f"频道 ID: {channel_id}")
        elif source_url:
            separator_parts.append(f"来源: {source_url}")
        separator_parts.append(f"视频数量: {len(videos_with_subtitle) + len(videos_without_subtitle)}")
        separator = " | ".join(separator_parts)
        
        # 保存有字幕的视频链接（追加模式）
        if videos_with_subtitle:
            try:
                # 先写入分隔符和标题
                _append_line_safe(with_subtitle_file, "\n")
                _append_line_safe(with_subtitle_file, separator + "\n")
                _append_line_safe(with_subtitle_file, f"# {t('videos_with_subtitle')} ({len(videos_with_subtitle)} {t('count_unit')})\n")
                _append_line_safe(with_subtitle_file, "\n")
                
                # 逐行写入视频 URL（使用线程安全的追加写入）
                for video in videos_with_subtitle:
                    _append_line_safe(with_subtitle_file, video.url + "\n")
                
                # 写入结束分隔符
                _append_line_safe(with_subtitle_file, "# " + "=" * 80 + "\n")
                _append_line_safe(with_subtitle_file, "\n")
                
                on_log("INFO", t("saved_with_subtitle_file", count=len(videos_with_subtitle), filename=with_subtitle_file.name))
            except Exception as e:
                on_log("WARN", t("save_file_failed", filename=with_subtitle_file.name, error=str(e)))
        
        # 保存无字幕的视频链接（追加模式）
        if videos_without_subtitle:
            try:
                # 先写入分隔符和标题
                _append_line_safe(without_subtitle_file, "\n")
                _append_line_safe(without_subtitle_file, separator + "\n")
                _append_line_safe(without_subtitle_file, f"# {t('videos_without_subtitle')} ({len(videos_without_subtitle)} {t('count_unit')})\n")
                _append_line_safe(without_subtitle_file, "\n")
                
                # 逐行写入视频 URL（使用线程安全的追加写入）
                for video in videos_without_subtitle:
                    _append_line_safe(without_subtitle_file, video.url + "\n")
                
                # 写入结束分隔符
                _append_line_safe(without_subtitle_file, "# " + "=" * 80 + "\n")
                _append_line_safe(without_subtitle_file, "\n")
                
                on_log("INFO", t("saved_without_subtitle_file", count=len(videos_without_subtitle), filename=without_subtitle_file.name))
            except Exception as e:
                on_log("WARN", t("save_file_failed", filename=without_subtitle_file.name, error=str(e)))
    
    def _format_subtitle_info(self, result) -> str:
        """格式化字幕信息显示
        
        Args:
            result: 检测结果
        
        Returns:
            格式化的字幕信息字符串
        """
        subtitle_info_parts = []
        if result.manual_languages:
            manual_langs = ", ".join(result.manual_languages)
            subtitle_info_parts.append(f"{t('manual_subtitles')}：{manual_langs}")
        if result.auto_languages:
            auto_langs = ", ".join(result.auto_languages)
            subtitle_info_parts.append(f"{t('auto_subtitles')}：{auto_langs}")
        return " | ".join(subtitle_info_parts)
    
    # ============================================================
    # 完整处理模式
    # ============================================================
    
    def process_videos(
        self,
        url: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_stats: Callable[[dict], None],
        on_complete: Optional[Callable[[], None]] = None,
        force: bool = False
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
                logger.info(f"[GUI] Processing task started, URL: {url}")
                on_status(t("status_processing"))
                on_log("INFO", t("processing_start", url=url))
                
                # 获取视频列表
                videos = self._fetch_videos(url, on_log, on_status)
                if not videos:
                    return
                
                logger.info(f"[GUI] Fetched {len(videos)} videos")
                
                # 保存视频列表到文件
                channel_name = videos[0].channel_name if videos else None
                channel_id = videos[0].channel_id if videos else None
                self._save_video_list(videos, url, channel_name, channel_id, on_log)
                
                on_log("INFO", t("videos_found", count=len(videos)))
                
                # 先执行字幕检测，显示详细列表
                self._detect_subtitles(videos, on_log, source_url=url, channel_name=channel_name, channel_id=channel_id)
                
                # 如果翻译 AI 初始化失败，提前提示
                if self.translation_llm_init_error and self.app_config.translation_ai.enabled:
                    error_msg = f"翻译 AI 初始化失败: {self.translation_llm_init_error}，将跳过 AI 翻译"
                    on_log("WARN", error_msg)
                
                # 执行完整处理流程
                on_log("INFO", t("processing_starting"))
                self._run_full_processing(videos, channel_id, on_log, on_stats, force)
            except Exception as e:
                import traceback
                error_msg = f"{t('processing_failed', error=str(e))}"
                logger.error(f"Processing failed: {e}\n{traceback.format_exc()}")
                on_log("ERROR", error_msg)
        
        return self._run_task_in_thread(task, on_status, on_complete)
    
    def stop_processing(self):
        """停止处理（由 GUI 的停止按钮调用）"""
        if self.cancel_token is not None:
            self.cancel_token.cancel("用户点击停止按钮")
            logger.info("用户请求停止处理")
        else:
            logger.warning("尝试取消任务，但 cancel_token 不存在（任务可能未开始或已结束）")
    
    def _run_full_processing(
        self,
        videos: List[VideoInfo],
        channel_id: Optional[str],
        on_log: Callable[[str, str, Optional[str]], None],
        on_stats: Callable[[dict], None],
        force: bool = False
    ):
        # 重置取消令牌（开始新的处理任务）
        self.cancel_token = CancelToken()
        """执行完整处理流程（下载、翻译、摘要）
        
        Args:
            videos: 视频列表
            channel_id: 频道 ID
            on_log: 日志回调
            on_stats: 统计回调
        """
        # 获取 archive 路径（用于增量处理）
        archive_path = self.incremental_manager.get_or_create_channel_archive(channel_id)
        
        # 初始化统计信息
        stats = {"total": len(videos), "success": 0, "failed": 0, "current": 0}
        on_stats(stats)
        
        on_log("INFO", t("videos_found", count=len(videos)))
        on_log("INFO", t("log.task_start", total=len(videos), concurrency=self.app_config.concurrency))
        
        # 调用核心流水线
        result = process_video_list(
            videos=videos,
            language_config=self.app_config.language,
            translation_llm=self.translation_llm_client,
            summary_llm=self.summary_llm_client,
            output_writer=self.output_writer,
            failure_logger=self.failure_logger,
            incremental_manager=self.incremental_manager,
            archive_path=archive_path,
            force=force,
            dry_run=False,  # 正常处理模式，不是 Dry Run
            cancel_token=self.cancel_token,  # 传递取消令牌
            concurrency=self.app_config.concurrency,
            proxy_manager=self.proxy_manager,
            cookie_manager=self.cookie_manager,
            on_stats=on_stats,
            on_log=on_log,
            translation_llm_init_error_type=self.translation_llm_init_error_type,  # 传递初始化失败的错误类型
            translation_llm_init_error=self.translation_llm_init_error,  # 传递初始化失败的错误信息
        )
        
        # 更新最终统计信息（包含错误分类）
        stats["success"] = result.get("success", 0)
        stats["failed"] = result.get("failed", 0)
        stats["current"] = stats["total"]
        stats["error_counts"] = result.get("error_counts", {})  # 错误分类统计
        on_stats(stats)
        
        # 显示完成消息
        self._log_processing_complete(stats, result, on_log)
    
    def _log_processing_complete(
        self,
        stats: dict,
        result: dict,
        on_log: Callable[[str, str, Optional[str]], None]
    ):
        """记录处理完成消息
        
        Args:
            stats: 统计信息
            result: 处理结果
            on_log: 日志回调
        """
        success_count = stats["success"]
        failed_count = stats["failed"]
        
        if failed_count > 0:
            errors = result.get("errors", [])
            if errors:
                msg = t("processing_complete_with_errors",
                       success=success_count, failed=failed_count)
            else:
                msg = t("processing_complete_simple",
                       success=success_count, failed=failed_count)
            on_log("WARN", msg)
        else:
            msg = t("processing_complete_simple", success=success_count, failed=failed_count)
            on_log("INFO", msg)
    
    # ============================================================
    # URL 列表模式
    # ============================================================
    
    def dry_run_url_list(
        self,
        urls_text: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_complete: Optional[Callable[[], None]] = None,
        force: bool = False
    ):
        """执行 Dry Run（URL 列表模式）
        
        Args:
            urls_text: 多行 URL 文本（每行一个 URL）
            on_log: 日志回调
            on_status: 状态更新回调
            on_complete: 完成回调
        """
        def task():
            try:
                on_status(t("status_detecting"))
                on_log("INFO", t("dry_run_start_url_list"))
                
                # 获取视频列表
                videos = self._fetch_videos_from_url_list(urls_text, on_log, on_status)
                if not videos:
                    return
                
                # 保存视频列表到文件
                self._save_video_list(videos, "URL列表", None, None, on_log)
                
                on_log("INFO", t("videos_found", count=len(videos)))
                
                # 执行字幕检测
                self._detect_subtitles(videos, on_log, source_url="URL列表", channel_name=None, channel_id=None, dry_run=True)
            except Exception as e:
                import traceback
                error_msg = f"{t('dry_run_failed', error=str(e))}"
                logger.error(f"Dry Run (URL list) failed: {e}\n{traceback.format_exc()}")
                on_log("ERROR", error_msg)
        
        return self._run_task_in_thread(task, on_status, on_complete)
    
    def process_url_list(
        self,
        urls_text: str,
        on_log: Callable[[str, str, Optional[str]], None],
        on_status: Callable[[str], None],
        on_stats: Callable[[dict], None],
        on_complete: Optional[Callable[[], None]] = None,
        force: bool = False
    ):
        """处理视频列表（URL 列表模式）
        
        Args:
            urls_text: 多行 URL 文本（每行一个 URL）
            on_log: 日志回调
            on_status: 状态更新回调
            on_stats: 统计信息更新回调
            on_complete: 完成回调
        """
        def task():
            try:
                logger.info(f"[GUI] URL列表处理任务线程已启动")
                on_status(t("status_processing"))
                on_log("INFO", t("processing_start_url_list"))
                
                # 获取视频列表
                videos = self._fetch_videos_from_url_list(urls_text, on_log, on_status)
                if not videos:
                    return
                
                logger.info(f"[GUI] 获取到 {len(videos)} 个视频")
                
                # 保存视频列表到文件
                self._save_video_list(videos, "URL列表", None, None, on_log)
                
                on_log("INFO", t("videos_found", count=len(videos)))
                
                # 先执行字幕检测，显示详细列表
                self._detect_subtitles(videos, on_log, source_url="URL列表", channel_name=None, channel_id=None, dry_run=True)
                
                # 如果翻译 AI 初始化失败，提前提示
                if self.translation_llm_init_error and self.app_config.translation_ai.enabled:
                    error_msg = f"翻译 AI 初始化失败: {self.translation_llm_init_error}，将跳过 AI 翻译"
                    on_log("WARN", error_msg)
                
                # 执行完整处理流程（URL 列表模式使用批次 archive）
                on_log("INFO", t("processing_starting"))
                self._run_full_processing_url_list(videos, on_log, on_stats, force)
            except Exception as e:
                import traceback
                error_msg = f"{t('processing_failed', error=str(e))}"
                logger.error(f"URL list processing failed: {e}\n{traceback.format_exc()}")
                on_log("ERROR", error_msg)
        
        return self._run_task_in_thread(task, on_status, on_complete)
    
    def _run_full_processing_url_list(
        self,
        videos: List[VideoInfo],
        on_log: Callable[[str, str, Optional[str]], None],
        on_stats: Callable[[dict], None],
        force: bool = False
    ):
        # 重置取消令牌（开始新的处理任务）
        self.cancel_token = CancelToken()
        """执行完整处理流程（URL 列表模式）
        
        Args:
            videos: 视频列表
            on_log: 日志回调
            on_stats: 统计回调
        """
        # URL 列表模式使用批次 archive
        archive_path = self.incremental_manager.get_batch_archive_path()
        
        # 初始化统计信息
        stats = {"total": len(videos), "success": 0, "failed": 0, "current": 0}
        on_stats(stats)
        
        on_log("INFO", t("videos_found", count=len(videos)))
        on_log("INFO", t("log.task_start", total=len(videos), concurrency=self.app_config.concurrency))
        
        # 调用核心流水线
        result = process_video_list(
            videos=videos,
            language_config=self.app_config.language,
            translation_llm=self.translation_llm_client,
            summary_llm=self.summary_llm_client,
            output_writer=self.output_writer,
            failure_logger=self.failure_logger,
            incremental_manager=self.incremental_manager,
            archive_path=archive_path,
            force=force,
            dry_run=False,  # 正常处理模式，不是 Dry Run
            cancel_token=self.cancel_token,  # 传递取消令牌
            concurrency=self.app_config.concurrency,
            proxy_manager=self.proxy_manager,
            cookie_manager=self.cookie_manager,
            on_stats=on_stats,
            on_log=on_log,
            translation_llm_init_error_type=self.translation_llm_init_error_type,  # 传递初始化失败的错误类型
            translation_llm_init_error=self.translation_llm_init_error,  # 传递初始化失败的错误信息
        )
        
        # 更新最终统计信息（包含错误分类）
        stats["success"] = result.get("success", 0)
        stats["failed"] = result.get("failed", 0)
        stats["current"] = stats["total"]
        stats["error_counts"] = result.get("error_counts", {})  # 错误分类统计
        on_stats(stats)
        
        # 显示完成消息
        self._log_processing_complete(stats, result, on_log)
