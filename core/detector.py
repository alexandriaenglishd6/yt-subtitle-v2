"""
字幕检测模块
检测单个视频的字幕情况（人工/自动字幕语言列表）
"""

import json
import subprocess
from typing import Optional

from core.models import DetectionResult, VideoInfo
from core.logger import get_logger, translate_exception
from core.exceptions import AppException, ErrorType
from core.fetcher import _map_ytdlp_error_to_app_error

logger = get_logger()


class SubtitleDetector:
    """字幕检测器

    负责检测单个视频的字幕情况，区分人工字幕和自动字幕
    """

    def __init__(self, yt_dlp_path: Optional[str] = None, cookie_manager=None):
        """初始化字幕检测器

        Args:
            yt_dlp_path: yt-dlp 可执行文件路径，如果为 None 则使用系统 PATH 中的 yt-dlp
            cookie_manager: CookieManager 实例，如果为 None 则不使用 Cookie
        """
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        self.cookie_manager = cookie_manager

    def detect(self, video_info: VideoInfo) -> DetectionResult:
        """检测视频字幕情况

        Args:
            video_info: 视频信息对象

        Returns:
            DetectionResult 对象，包含字幕检测结果
        """
        try:
            logger.info_i18n("detect_subtitle_start", video_id=video_info.video_id)

            # 使用 yt-dlp 获取字幕信息
            subtitle_info = self._get_subtitle_info_ytdlp(video_info.url)

            if subtitle_info is None:
                logger.warning_i18n(
                    "log.detect_subtitle_info_failed", video_id=video_info.video_id
                )
                return DetectionResult(
                    video_id=video_info.video_id,
                    has_subtitles=False,
                    manual_languages=[],
                    auto_languages=[],
                )

            # 解析字幕信息
            manual_languages = []
            auto_languages = []

            # yt-dlp 返回的字幕信息格式：
            # subtitles: {lang_code: [{"ext": "vtt", "url": "...", ...}, ...]}
            # automatic_captions: {lang_code: [{"ext": "vtt", "url": "...", ...}, ...]}

            subtitles = subtitle_info.get("subtitles", {})
            automatic_captions = subtitle_info.get("automatic_captions", {})

            # 提取人工字幕语言（标准化语言代码）
            from core.language import normalize_language_code

            for lang_code in subtitles.keys():
                normalized_lang = normalize_language_code(lang_code)
                if normalized_lang not in manual_languages:
                    manual_languages.append(normalized_lang)

            # 提取自动字幕语言（标准化语言代码）
            for lang_code in automatic_captions.keys():
                normalized_lang = normalize_language_code(lang_code)
                if normalized_lang not in auto_languages:
                    auto_languages.append(normalized_lang)

            has_subtitles = len(manual_languages) > 0 or len(auto_languages) > 0

            # 提取章节信息
            chapters = subtitle_info.get("chapters", [])

            result = DetectionResult(
                video_id=video_info.video_id,
                has_subtitles=has_subtitles,
                manual_languages=manual_languages,
                auto_languages=auto_languages,
                chapters=chapters,
                subtitle_urls=subtitles,  # 保存原始字幕 URL 信息
                auto_subtitle_urls=automatic_captions,  # 保存原始自动字幕 URL 信息
            )

            if has_subtitles:
                logger.info_i18n(
                    "detect_subtitle_complete",
                    video_id=video_info.video_id,
                    manual_count=len(manual_languages),
                    auto_count=len(auto_languages),
                )
                # 输出详细语言列表
                if manual_languages:
                    logger.info_i18n(
                        "detect_manual_languages", languages=", ".join(manual_languages)
                    )
                if auto_languages:
                    logger.info_i18n(
                        "detect_auto_languages", languages=", ".join(auto_languages)
                    )
            else:
                logger.warning_i18n(
                    "log.video_no_subtitle", video_id=video_info.video_id
                )

            return result

        except AppException as e:
            # AppException 应该被重新抛出，让调用者处理
            logger.error(
                f"{translate_exception('exception.subtitle_detect_failed', error=str(e))}",
                extra={
                    "video_id": video_info.video_id,
                    "error_type": e.error_type.value,
                },
            )
            raise
        except Exception as e:
            # 其他异常转换为 AppException
            app_error = AppException(
                message=translate_exception("exception.subtitle_detect_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                f"{translate_exception('exception.subtitle_detect_failed', error=str(app_error))}",
                extra={
                    "video_id": video_info.video_id,
                    "error_type": app_error.error_type.value,
                },
            )
            raise app_error

    def _get_subtitle_info_ytdlp(self, url: str) -> Optional[dict]:
        """使用 yt-dlp 获取字幕信息

        Args:
            url: 视频 URL

        Returns:
            包含字幕信息的字典，如果失败则返回 None
        """
        try:
            # 使用 yt-dlp 获取视频信息（包含字幕列表）
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-warnings",
                "--skip-download",  # 不下载视频，只获取信息
            ]

            # 如果配置了 Cookie，添加 Cookie 参数
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
                    logger.info_i18n(
                        "cookie_file_detect_subtitle", cookie_file=cookie_file
                    )
                else:
                    logger.warning_i18n("log.cookie_file_path_unavailable_detect")
            else:
                logger.debug_i18n("log.cookie_manager_not_configured_detect")

            cmd.append(url)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                # 将 yt-dlp 错误映射为 AppException
                app_error = _map_ytdlp_error_to_app_error(
                    returncode=result.returncode,
                    stderr=result.stderr or "",
                    timeout=False,
                )
                logger.error(
                    f"{translate_exception('exception.ytdlp_execution_failed', returncode=result.returncode, error=str(app_error))}",
                    extra={"error_type": app_error.error_type.value},
                )
                # 抛出异常，而不是返回 None
                raise app_error

            # 解析 JSON
            data = json.loads(result.stdout)

            # 提取字幕信息和章节
            subtitle_info = {
                "subtitles": data.get("subtitles", {}),
                "automatic_captions": data.get("automatic_captions", {}),
                "chapters": data.get("chapters", []),  # 添加章节信息
            }

            return subtitle_info

        except subprocess.TimeoutExpired:
            app_error = AppException(
                message=translate_exception("exception.fetch_subtitle_info_timeout", url=url),
                error_type=ErrorType.TIMEOUT,
            )
            logger.error(
                f"{translate_exception('exception.fetch_subtitle_info_timeout', url=url)}",
                extra={"error_type": app_error.error_type.value},
            )
            raise app_error
        except json.JSONDecodeError as e:
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
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            app_error = AppException(
                message=translate_exception("exception.fetch_subtitle_info_error", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                f"{translate_exception('exception.fetch_subtitle_info_error', error=str(app_error))}",
                extra={"error_type": app_error.error_type.value},
            )
            raise app_error

    def detect_by_url(
        self, url: str, video_id: Optional[str] = None
    ) -> DetectionResult:
        """通过 URL 检测字幕（便捷方法）

        Args:
            url: 视频 URL
            video_id: 视频 ID，如果为 None 则从 URL 提取

        Returns:
            DetectionResult 对象
        """
        from core.fetcher import VideoFetcher

        if video_id is None:
            fetcher = VideoFetcher()
            video_id = fetcher.extract_video_id(url)
            if not video_id:
                logger.error_i18n("log.video_id_extract_failed", url=url)
                return DetectionResult(
                    video_id="unknown",
                    has_subtitles=False,
                    manual_languages=[],
                    auto_languages=[],
                )

        video_info = VideoInfo(
            video_id=video_id,
            url=url,
            title="",  # 标题不是必需的
        )

        return self.detect(video_info)
