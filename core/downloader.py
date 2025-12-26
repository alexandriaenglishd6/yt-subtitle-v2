"""
字幕下载模块
根据检测结果下载原始字幕和官方翻译字幕
符合 error_handling.md 规范：将 yt-dlp 错误映射为 AppException，使用原子写文件
"""

import subprocess
from pathlib import Path
from typing import Optional, Dict

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger, translate_log
from core.exceptions import AppException, ErrorType
from core.fetcher import _map_ytdlp_error_to_app_error
from core.failure_logger import _atomic_write
from core.language_utils import lang_matches
from core.chinese_detector import is_chinese_lang, normalize_chinese_lang_code
from core.subprocess_utils import run_command

logger = get_logger()


class SubtitleDownloader:
    """字幕下载器

    负责下载原始字幕和官方翻译字幕
    """

    def __init__(
        self,
        yt_dlp_path: Optional[str] = None,
        output_dir: Optional[Path] = None,
        proxy_manager=None,
        cookie_manager=None,
    ):
        """初始化字幕下载器

        Args:
            yt_dlp_path: yt-dlp 可执行文件路径，如果为 None 则使用系统 PATH 中的 yt-dlp
            output_dir: 输出目录，如果为 None 则使用当前目录
            proxy_manager: ProxyManager 实例，如果为 None 则不使用代理
            cookie_manager: CookieManager 实例，如果为 None 则不使用 Cookie
        """
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        self.output_dir = output_dir or Path(".")
        self.proxy_manager = proxy_manager
        self.cookie_manager = cookie_manager

    def download(
        self,
        video_info: VideoInfo,
        detection_result: DetectionResult,
        language_config: LanguageConfig,
        output_path: Path,
        cancel_token=None,
    ) -> Dict[str, Optional[Path]]:
        """下载字幕文件

        Args:
            video_info: 视频信息
            detection_result: 字幕检测结果
            language_config: 语言配置
            output_path: 输出目录路径（视频的输出目录）

        Returns:
            字典，包含下载的字幕文件路径：
            {
                "original": Path,  # 原始字幕文件路径（原语言）
                "original_lang": str,  # 原始字幕语言代码
                "official_translations": {  # 官方翻译字幕文件路径（按语言代码）
                    "zh-CN": Path,
                    ...
                }
            }
        """
        result = {"original": None, "original_lang": None, "official_translations": {}}

        if not detection_result.has_subtitles:
            logger.warning_i18n(
                "video_no_subtitle_skip_download", video_id=video_info.video_id
            )
            return result

        try:
            # 确保输出目录存在
            output_path.mkdir(parents=True, exist_ok=True)

            # 步骤 1: 确定原始字幕语言（支持自动模式 and 指定模式）
            source_lang = self._determine_source_language(
                detection_result, language_config
            )
            result["original_lang"] = source_lang

            # 检查取消状态（在下载原始字幕前）
            if cancel_token and cancel_token.is_cancelled():
                from core.exceptions import TaskCancelledError

                reason = cancel_token.get_reason() or translate_log("user_cancelled")
                raise TaskCancelledError(reason)

            if source_lang:
                # 下载原始字幕 - 优先尝试人工字幕，失败后尝试自动字幕
                original_path = self._download_subtitle(
                    video_info.url,
                    source_lang,
                    output_path,
                    f"original.{source_lang}.srt",
                    is_auto=False,  # 先尝试人工字幕
                    cancel_token=cancel_token,
                )
                
                # 如果人工字幕下载失败，尝试自动字幕
                if not original_path:
                    logger.info_i18n(
                        "log.trying_auto_subtitle",
                        lang=source_lang,
                        video_id=video_info.video_id,
                    )
                    original_path = self._download_subtitle(
                        video_info.url,
                        source_lang,
                        output_path,
                        f"original.{source_lang}.srt",
                        is_auto=True,  # 尝试自动字幕
                        cancel_token=cancel_token,
                    )
                
                # 如果 yt-dlp 下载完全失败，尝试直接从 URL 下载
                if not original_path and detection_result:
                    original_path = self._download_subtitle_from_url(
                        detection_result,
                        source_lang,
                        output_path,
                        f"original.{source_lang}.srt",
                    )
                
                result["original"] = original_path

                if original_path:
                    # 如果是中文字幕，检测简繁体并规范化语言代码
                    if is_chinese_lang(source_lang) and source_lang.lower() == "zh":
                        try:
                            content = original_path.read_text(encoding="utf-8", errors="ignore")
                            normalized_lang = normalize_chinese_lang_code(source_lang, content)
                            if normalized_lang != source_lang:
                                # 重命名文件以使用规范化的语言代码
                                new_filename = f"original.{normalized_lang}.srt"
                                new_path = output_path / new_filename
                                original_path.rename(new_path)
                                result["original"] = new_path
                                result["original_lang"] = normalized_lang
                                logger.info_i18n(
                                    "log.chinese_variant_detected",
                                    original_lang=source_lang,
                                    detected_lang=normalized_lang,
                                    video_id=video_info.video_id,
                                )
                                original_path = new_path
                        except Exception as e:
                            logger.debug_i18n("log.chinese_detection_failed", error=str(e))
                    
                    logger.info_i18n(
                        "original_subtitle_downloaded",
                        file_name=original_path.name,
                        video_id=video_info.video_id,
                    )

            # 步骤 2: 下载官方翻译字幕（针对每个目标语言）
            # 定义常见语言列表（按优先级排序，用于当目标语言没有官方字幕时的备用选择）
            COMMON_LANGUAGES = [
                "en",
                "en-US",
                "de",
                "de-DE",
                "ja",
                "ja-JP",
                "es",
                "es-ES",
                "fr",
                "fr-FR",
                "pt",
                "pt-PT",
                "ru",
                "ru-RU",
                "ko",
                "ko-KR",
            ]

            for target_lang in language_config.subtitle_target_languages:
                # 检查取消状态（在下载每个官方翻译字幕前）
                if cancel_token and cancel_token.is_cancelled():
                    from core.exceptions import TaskCancelledError

                    reason = cancel_token.get_reason() or translate_log("user_cancelled")
                    raise TaskCancelledError(reason)


                # lang_matches() 已从 core.language_utils 导入
                # 检查是否有官方字幕（人工或自动）匹配目标语言（支持 en vs en-US 匹配）
                matched_lang = None
                is_auto = False

                # 先检查人工字幕
                if detection_result.manual_languages:
                    for lang in detection_result.manual_languages:
                        if lang_matches(lang, target_lang):
                            matched_lang = lang
                            is_auto = False
                            break

                # 如果没找到，检查自动字幕
                if not matched_lang and detection_result.auto_languages:
                    for lang in detection_result.auto_languages:
                        if lang_matches(lang, target_lang):
                            matched_lang = lang
                            is_auto = True
                            break

                if matched_lang:
                    # 找到匹配的语言，下载官方字幕（使用检测到的实际语言代码）
                    official_path = self._download_subtitle(
                        video_info.url,
                        matched_lang,  # 使用检测到的实际语言代码（如 en），而不是目标语言（如 en-US）
                        output_path,
                        f"translated.{target_lang}.srt",  # 但文件名仍使用目标语言代码
                        is_auto=is_auto,
                        cancel_token=cancel_token,
                    )

                if official_path:
                    # 验证下载的字幕语言是否正确
                    actual_lang = self._verify_subtitle_language(
                        official_path, target_lang
                    )
                    if actual_lang and actual_lang != target_lang:
                        logger.warning_i18n(
                            "log.subtitle_lang_mismatch",
                            target_lang=target_lang,
                            actual_lang=actual_lang,
                            file_name=official_path.name,
                            video_id=video_info.video_id,
                        )
                        # 仍然保存，但记录警告
                    result["official_translations"][target_lang] = official_path
                    logger.info_i18n(
                        "official_translated_subtitle_downloaded",
                        lang=target_lang,
                        file_name=official_path.name,
                        video_id=video_info.video_id,
                    )
                else:
                    logger.warning_i18n(
                        "official_translation_download_failed",
                        lang=target_lang,
                        video_id=video_info.video_id,
                    )
            else:
                logger.info_i18n(
                    "log.no_official_subtitle",
                    target_lang=target_lang,
                    video_id=video_info.video_id,
                )
                # 尝试下载常见语言的官方字幕（作为翻译的备用源语言）
                # 基于检测结果，优先下载常见语言的字幕作为 AI 翻译的源语言
                common_subtitle_downloaded = False

                # 使用从 core.language_utils 导入的 lang_matches() 函数

                for common_lang in COMMON_LANGUAGES:
                    # 在检测结果中查找匹配的语言（支持 en vs en-US 的匹配）
                    matched_lang = None
                    is_auto = False

                    # 先检查人工字幕
                    if detection_result.manual_languages:
                        for lang in detection_result.manual_languages:
                            if lang_matches(lang, common_lang):
                                matched_lang = lang
                                is_auto = False
                                break

                    # 如果没找到，检查自动字幕
                    if not matched_lang and detection_result.auto_languages:
                        for lang in detection_result.auto_languages:
                            if lang_matches(lang, common_lang):
                                matched_lang = lang
                                is_auto = True
                                break

                    # 如果找到匹配的语言且未下载，下载它
                    if (
                        matched_lang
                        and matched_lang not in result["official_translations"]
                    ):
                        # 使用检测结果中的实际语言代码下载
                        common_path = self._download_subtitle(
                            video_info.url,
                            matched_lang,
                            output_path,
                            f"translated.{matched_lang}.srt",
                            is_auto=is_auto,
                            cancel_token=cancel_token,
                        )

                        if common_path:
                            # 使用检测结果中的实际语言代码作为 key
                            result["official_translations"][matched_lang] = common_path
                            logger.info_i18n(
                                "log.downloaded_common_official_subtitle",
                                matched_lang=matched_lang,
                                common_lang=common_lang,
                                file_name=common_path.name,
                                video_id=video_info.video_id,
                            )
                            common_subtitle_downloaded = True
                            break  # 找到第一个常见语言的字幕即可

                if not common_subtitle_downloaded:
                    logger.info_i18n(
                        "log.no_official_or_common_subtitle",
                        target_lang=target_lang,
                        video_id=video_info.video_id,
                    )

            return result

        except AppException as e:
            from core.logger import translate_log

            error_msg = translate_log("download_subtitle_failed", error=str(e))
            logger.error_i18n(
                "download_subtitle_failed",
                error=str(e),
                video_id=video_info.video_id,
                error_type=e.error_type.value,
            )
            return result
        except Exception as e:
            # 未映射的异常，转换为 AppException
            from core.logger import translate_log

            error_msg = translate_log("download_subtitle_failed", error=str(e))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.UNKNOWN, cause=e
            )
            logger.error_i18n(
                "download_subtitle_failed",
                error=str(app_error),
                video_id=video_info.video_id,
                error_type=app_error.error_type.value,
            )
            return result

    def _determine_source_language(
        self, detection_result: DetectionResult, language_config: LanguageConfig
    ) -> Optional[str]:
        """确定原始字幕语言

        支持两种模式：
        1. 自动模式（source_language 为 None）：按优先级列表匹配检测到的语言
        2. 指定模式（source_language 有值）：使用指定的语言，如果不存在则回退到自动模式

        Args:
            detection_result: 字幕检测结果
            language_config: 语言配置

        Returns:
            语言代码，如果没有字幕则返回 None
        """
        # 定义优先级列表（按使用人数排序）
        PRIORITY_LANGUAGES = [
            "en",
            "zh-CN",
            "ja",
            "de",
            "fr",
            "es",
            "ru",
            "pt",
            "ko",
            "it",
            "ar",
            "hi",
        ]

        # 如果指定了源语言
        if language_config.source_language:
            specified_lang = language_config.source_language
            # 检查是否存在（先检查人工字幕，再检查自动字幕）- 使用 lang_matches 支持 zh vs zh-CN 匹配
            for detected_lang in detection_result.manual_languages:
                if lang_matches(detected_lang, specified_lang):
                    logger.info_i18n(
                        "using_specified_source_lang_manual",
                        lang=detected_lang,
                        video_id=detection_result.video_id
                        if hasattr(detection_result, "video_id")
                        else None,
                    )
                    return detected_lang  # 返回实际检测到的语言代码
            for detected_lang in detection_result.auto_languages:
                if lang_matches(detected_lang, specified_lang):
                    logger.info_i18n(
                        "using_specified_source_lang_auto",
                        lang=detected_lang,
                        video_id=detection_result.video_id
                        if hasattr(detection_result, "video_id")
                        else None,
                    )
                    return detected_lang  # 返回实际检测到的语言代码
            # 指定的源语言不存在，回退到自动模式
            logger.warning_i18n(
                "log.specified_source_lang_not_found",
                lang=specified_lang,
                manual=detection_result.manual_languages,
                auto=detection_result.auto_languages,
                video_id=detection_result.video_id
                if hasattr(detection_result, "video_id")
                else None,
            )

        # 自动模式：按优先级匹配
        # 先检查人工字幕（使用 lang_matches 函数支持 zh vs zh-CN 匹配）
        for priority_lang in PRIORITY_LANGUAGES:
            for detected_lang in detection_result.manual_languages:
                if lang_matches(detected_lang, priority_lang):
                    logger.debug_i18n(
                        "log.auto_selecting_source_lang_priority_manual",
                        lang=detected_lang,
                        video_id=detection_result.video_id
                        if hasattr(detection_result, "video_id")
                        else None,
                    )
                    return detected_lang  # 返回实际检测到的语言代码

        # 再检查自动字幕
        for priority_lang in PRIORITY_LANGUAGES:
            for detected_lang in detection_result.auto_languages:
                if lang_matches(detected_lang, priority_lang):
                    logger.debug_i18n(
                        "log.auto_selecting_source_lang_priority_auto",
                        lang=detected_lang,
                        video_id=detection_result.video_id
                        if hasattr(detection_result, "video_id")
                        else None,
                    )
                    return detected_lang  # 返回实际检测到的语言代码

        # 如果优先级列表中没有，使用原来的逻辑（第一个人工/自动字幕）
        if detection_result.manual_languages:
            logger.debug_i18n(
                "log.auto_selecting_source_lang_first_manual",
                lang=detection_result.manual_languages[0],
                video_id=detection_result.video_id
                if hasattr(detection_result, "video_id")
                else None,
            )
            return detection_result.manual_languages[0]
        elif detection_result.auto_languages:
            logger.debug_i18n(
                "log.auto_selecting_source_lang_first_auto",
                lang=detection_result.auto_languages[0],
                video_id=detection_result.video_id
                if hasattr(detection_result, "video_id")
                else None,
            )
            return detection_result.auto_languages[0]

        return None

    def _download_subtitle_from_url(
        self,
        detection_result: DetectionResult,
        lang_code: str,
        output_dir: Path,
        output_filename: str,
    ) -> Optional[Path]:
        """直接从检测结果中的 URL 下载字幕（备用方案）
        
        当 yt-dlp 的 --write-subs 无法工作时，直接从字幕 URL 下载。
        
        Args:
            detection_result: 检测结果（包含字幕 URL）
            lang_code: 语言代码
            output_dir: 输出目录
            output_filename: 输出文件名
            
        Returns:
            下载的字幕文件路径，如果失败则返回 None
        """
        import requests
        from core.language_utils import lang_matches
        
        try:
            output_path = output_dir / output_filename
            subtitle_url = None
            subtitle_ext = None
            
            # 先查找人工字幕 URL
            for sub_lang, sub_list in detection_result.subtitle_urls.items():
                if lang_matches(sub_lang, lang_code) and sub_list:
                    # 优先选择 srt 或 vtt 格式
                    for sub_info in sub_list:
                        ext = sub_info.get("ext", "")
                        if ext in ["srt", "vtt", "srv3", "json3"]:
                            subtitle_url = sub_info.get("url")
                            subtitle_ext = ext
                            break
                    if not subtitle_url and sub_list:
                        # 使用第一个可用的
                        subtitle_url = sub_list[0].get("url")
                        subtitle_ext = sub_list[0].get("ext", "vtt")
                    if subtitle_url:
                        logger.info_i18n(
                            "log.download_from_url_manual",
                            lang=sub_lang,
                            video_id=detection_result.video_id,
                        )
                        break
            
            # 如果没有人工字幕，查找自动字幕 URL
            if not subtitle_url:
                for sub_lang, sub_list in detection_result.auto_subtitle_urls.items():
                    if lang_matches(sub_lang, lang_code) and sub_list:
                        for sub_info in sub_list:
                            ext = sub_info.get("ext", "")
                            if ext in ["srt", "vtt", "srv3", "json3"]:
                                subtitle_url = sub_info.get("url")
                                subtitle_ext = ext
                                break
                        if not subtitle_url and sub_list:
                            subtitle_url = sub_list[0].get("url")
                            subtitle_ext = sub_list[0].get("ext", "vtt")
                        if subtitle_url:
                            logger.info_i18n(
                                "log.download_from_url_auto",
                                lang=sub_lang,
                                video_id=detection_result.video_id,
                            )
                            break
            
            if not subtitle_url:
                logger.warning_i18n(
                    "log.no_subtitle_url_found",
                    lang=lang_code,
                    video_id=detection_result.video_id,
                )
                return None
            
            # 准备代理配置（使用现有的 proxy_manager）
            proxies = None
            if self.proxy_manager:
                proxy = self.proxy_manager.get_next_proxy()
                if proxy:
                    proxies = {"http": proxy, "https": proxy}
                    logger.debug(f"使用代理下载字幕: {proxy}")
            
            # 下载字幕
            response = requests.get(subtitle_url, timeout=30, proxies=proxies)
            response.raise_for_status()
            
            content = response.text
            
            # 如果是 JSON3 格式，转换为 SRT
            if subtitle_ext == "json3":
                content = self._convert_json3_to_srt(content)
            elif subtitle_ext == "srv3":
                content = self._convert_srv3_to_srt(content)
            elif subtitle_ext == "vtt":
                content = self._convert_vtt_to_srt(content)
            
            # 写入文件
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            logger.info_i18n(
                "log.subtitle_downloaded_from_url",
                file_name=output_filename,
                video_id=detection_result.video_id,
            )
            
            return output_path
            
        except Exception as e:
            logger.warning_i18n(
                "log.download_from_url_failed",
                error=str(e),
                video_id=detection_result.video_id,
            )
            return None
    
    def _convert_vtt_to_srt(self, vtt_content: str) -> str:
        """将 VTT 格式转换为 SRT 格式"""
        import re
        
        # 移除 VTT 头部
        lines = vtt_content.strip().split("\n")
        if lines and lines[0].startswith("WEBVTT"):
            lines = lines[1:]
        
        # 处理时间戳格式
        srt_lines = []
        counter = 1
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # 跳过空行和注释
            if not line or line.startswith("NOTE"):
                i += 1
                continue
            # 检测时间戳行
            if " --> " in line:
                # 转换时间戳格式（VTT 用 . 分隔毫秒，SRT 用 ,）
                timestamp = re.sub(r"(\d{2}:\d{2}:\d{2})\.(\d{3})", r"\1,\2", line)
                # 移除 VTT 特有的位置信息
                timestamp = re.sub(r" (align|position|line|size):[^\s]+", "", timestamp)
                srt_lines.append(str(counter))
                srt_lines.append(timestamp)
                counter += 1
                i += 1
                # 收集字幕文本
                while i < len(lines) and lines[i].strip():
                    srt_lines.append(lines[i].strip())
                    i += 1
                srt_lines.append("")
            else:
                i += 1
        
        return "\n".join(srt_lines)
    
    def _convert_json3_to_srt(self, json_content: str) -> str:
        """将 YouTube JSON3 格式转换为 SRT 格式"""
        import json
        
        try:
            data = json.loads(json_content)
            events = data.get("events", [])
            
            srt_lines = []
            counter = 1
            
            for event in events:
                if "segs" not in event:
                    continue
                
                start_ms = event.get("tStartMs", 0)
                duration_ms = event.get("dDurationMs", 0)
                end_ms = start_ms + duration_ms
                
                text = "".join(seg.get("utf8", "") for seg in event.get("segs", []))
                text = text.strip()
                
                if text:
                    srt_lines.append(str(counter))
                    srt_lines.append(f"{self._ms_to_srt_time(start_ms)} --> {self._ms_to_srt_time(end_ms)}")
                    srt_lines.append(text)
                    srt_lines.append("")
                    counter += 1
            
            return "\n".join(srt_lines)
        except Exception:
            return json_content
    
    def _convert_srv3_to_srt(self, srv3_content: str) -> str:
        """将 YouTube SRV3 (XML) 格式转换为 SRT 格式"""
        import re
        from html import unescape
        
        try:
            srt_lines = []
            counter = 1
            
            # 简单的正则解析 <p t="start" d="duration">text</p>
            pattern = r'<p[^>]*t="(\d+)"[^>]*d="(\d+)"[^>]*>([^<]*)</p>'
            matches = re.findall(pattern, srv3_content)
            
            for start_ms_str, duration_ms_str, text in matches:
                start_ms = int(start_ms_str)
                duration_ms = int(duration_ms_str)
                end_ms = start_ms + duration_ms
                text = unescape(text).strip()
                
                if text:
                    srt_lines.append(str(counter))
                    srt_lines.append(f"{self._ms_to_srt_time(start_ms)} --> {self._ms_to_srt_time(end_ms)}")
                    srt_lines.append(text)
                    srt_lines.append("")
                    counter += 1
            
            return "\n".join(srt_lines) if srt_lines else srv3_content
        except Exception:
            return srv3_content
    
    def _ms_to_srt_time(self, ms: int) -> str:
        """将毫秒转换为 SRT 时间格式 (HH:MM:SS,mmm)"""
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _download_subtitle(
        self,
        url: str,
        lang_code: str,
        output_dir: Path,
        output_filename: str,
        is_auto: bool = False,
        cancel_token=None,
    ) -> Optional[Path]:
        """使用 yt-dlp 下载字幕文件

        Args:
            url: 视频 URL
            lang_code: 语言代码（如 "en", "zh-CN"）
            output_dir: 输出目录
            output_filename: 输出文件名
            is_auto: 是否为自动字幕（True）或人工字幕（False）

        Returns:
            下载的字幕文件路径，如果失败则返回 None
        """
        # 在 try 块外初始化 proxy，以便在 except 块中访问
        proxy = None
        if self.proxy_manager:
            proxy = self.proxy_manager.get_next_proxy()

        try:
            output_path = output_dir / output_filename

            # 构建 yt-dlp 命令
            # --write-subs: 下载字幕（人工字幕）
            # --write-auto-subs: 下载自动字幕（如果需要）
            # --sub-langs: 指定语言代码
            # --skip-download: 不下载视频
            # --convert-subs: 转换为 srt 格式
            # --output: 输出文件路径模板

            # yt-dlp 输出格式：<output_template>.<lang>.srt
            # 我们使用临时文件名，然后重命名
            temp_output = output_dir / f"temp_{output_path.stem}"

            cmd = [
                self.yt_dlp_path,
                "--skip-download",
                "--convert-subs",
                "srt",
                "--no-warnings",
                "--output",
                str(temp_output),
                # 如果 ffmpeg 不可用，尝试不使用 ffmpeg 进行转换
                # 某些字幕格式可能不需要 ffmpeg
                "--no-check-formats",  # 跳过格式检查，避免需要 ffmpeg
            ]

            # 如果配置了代理，添加代理参数
            if proxy:
                cmd.extend(["--proxy", proxy])
                logger.debug_i18n("using_proxy_download_subtitle", proxy=proxy)

            # 如果配置了 Cookie，添加 Cookie 参数
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])
                    logger.info_i18n(
                        "using_cookie_download_subtitle", cookie_file=cookie_file
                    )
                else:
                    logger.warning_i18n("cookie_manager_no_path_download")
            else:
                logger.debug_i18n("cookie_manager_not_configured_download")

            cmd.append(url)

            # 在调用 subprocess 前检查取消状态
            if cancel_token and cancel_token.is_cancelled():
                from core.exceptions import TaskCancelledError

                reason = cancel_token.get_reason() or translate_log("user_cancelled")
                raise TaskCancelledError(reason)

            # 根据是否为自动字幕选择不同的参数
            if is_auto:
                # 下载自动字幕
                cmd.extend(["--write-auto-subs", "--sub-langs", lang_code])
            else:
                # 下载人工字幕
                # 如果指定语言失败，会在外层逻辑尝试自动字幕
                cmd.extend(["--write-subs", "--sub-langs", lang_code])
            
            # 添加备用：如果指定语言不可用，尝试下载所有字幕
            # 这可以处理 yt-dlp 语言代码匹配问题
            if not is_auto:
                cmd.extend(["--write-auto-subs"])  # 同时也尝试自动字幕

            result = run_command(cmd, timeout=60)
            
            # 调试日志：输出 yt-dlp 的执行结果（使用 DEBUG 级别避免刷屏）
            logger.debug(f"yt-dlp 命令: {' '.join(cmd)}")
            logger.debug(f"yt-dlp returncode: {result.returncode}")
            if result.stdout:
                logger.debug(f"yt-dlp stdout: {result.stdout[:500]}")
            if result.stderr:
                logger.debug(f"yt-dlp stderr: {result.stderr[:500]}")
            
            # 列出输出目录中的临时文件
            temp_files = list(output_dir.glob("temp_*"))
            if temp_files:
                logger.debug(f"输出目录临时文件: {[f.name for f in temp_files]}")
            else:
                logger.debug(f"输出目录 {output_dir} 中没有临时文件")

            if result.returncode != 0:
                error_msg = result.stderr

                # 检查是否是 ffmpeg 错误
                is_ffmpeg_error = (
                    "ffmpeg" in error_msg.lower()
                    or "ffmpeg-location" in error_msg.lower()
                )

                # 即使 yt-dlp 报错，也检查文件是否已经生成（某些情况下文件可能已经下载）
                # yt-dlp 生成的文件名格式：<temp_output>.<lang>.srt
                # 例如：temp_original.zh.zh.srt（如果 temp_output = "temp_original.zh", lang_code = "zh"）
                expected_temp_name = temp_output.name  # 例如 "temp_original.zh"
                actual_paths = list(
                    output_dir.glob(f"{expected_temp_name}.{lang_code}.srt")
                )
                if not actual_paths:
                    # 也检查其他可能的格式（如 .vtt, .ttml）
                    actual_paths = list(
                        output_dir.glob(f"{expected_temp_name}.{lang_code}.*")
                    )
                if not actual_paths:
                    # 更宽泛的搜索：temp_*.<lang>.srt
                    actual_paths = list(output_dir.glob(f"temp_*.{lang_code}.srt"))
                if not actual_paths:
                    # 最宽泛的搜索：temp_*.<lang>.*
                    actual_paths = list(output_dir.glob(f"temp_*.{lang_code}.*"))
                # 如果是中文语言代码，扩展搜索模式以支持变体
                if not actual_paths and is_chinese_lang(lang_code):
                    # 支持多种字幕格式：srt, vtt, ttml, txt, srv3, json3
                    chinese_langs = ["zh", "zh-Hans", "zh-Hant", "zh-CN", "zh-TW", "cmn"]
                    subtitle_formats = ["srt", "vtt", "ttml", "txt", "srv3", "json3"]
                    for zh_lang in chinese_langs:
                        for fmt in subtitle_formats:
                            actual_paths = list(output_dir.glob(f"temp_*.{zh_lang}.{fmt}"))
                            if actual_paths:
                                break
                        if actual_paths:
                            break

                if actual_paths:
                    # 文件已经生成，即使 yt-dlp 报错也继续处理
                    logger.warning_i18n(
                        "ytdlp_error_but_file_generated",
                        returncode=result.returncode,
                        file_name=actual_paths[0].name,
                        error_type=ErrorType.CONTENT.value if is_ffmpeg_error else None,
                    )
                    # 直接处理文件，不抛出异常
                    actual_path = actual_paths[0]
                    expected_path = output_path
                    # 处理文件（移动到目标位置）
                    try:
                        if actual_path != expected_path:
                            content = actual_path.read_text(encoding="utf-8")
                            if _atomic_write(expected_path, content, mode="w"):
                                try:
                                    actual_path.unlink()
                                except Exception:
                                    pass
                                return expected_path
                            else:
                                logger.warning_i18n(
                                    "atomic_write_subtitle_failed",
                                    path=str(actual_path),
                                )
                                return actual_path
                        else:
                            return expected_path
                    except (OSError, IOError, PermissionError) as e:
                        from core.logger import translate_exception

                        app_error = AppException(
                            message=translate_exception(
                                "exception.read_write_subtitle_failed", error=str(e)
                            ),
                            error_type=ErrorType.FILE_IO,
                            cause=e,
                        )
                        logger.error(
                            translate_exception(
                                "exception.read_write_subtitle_failed",
                                error=str(app_error),
                            ),
                            extra={"error_type": app_error.error_type.value},
                        )
                        raise app_error
                else:
                    # 文件未生成，检查是否是 ffmpeg 错误
                    if is_ffmpeg_error:
                        # ffmpeg 错误：尝试不使用转换，直接下载原始格式
                        logger.warning_i18n("ffmpeg_error_retry_no_convert")
                        # 重新调用，但不使用 --convert-subs
                        return self._download_subtitle_no_convert(
                            url, lang_code, output_dir, output_filename, is_auto, proxy
                        )

                    # 映射为 AppException
                    app_error = _map_ytdlp_error_to_app_error(
                        result.returncode, error_msg
                    )
                    from core.logger import translate_exception

                    logger.error(
                        translate_exception(
                            "log.ytdlp_download_subtitle_failed", error=str(app_error)
                        ),
                        extra={"error_type": app_error.error_type.value},
                    )

                    # 如果使用了代理，标记代理失败
                    if proxy and self.proxy_manager:
                        self.proxy_manager.mark_failure(proxy, error_msg[:200])

                    # 抛出 AppException（由调用方处理）
                    raise app_error

            # 如果使用了代理且成功，标记代理成功
            if proxy and self.proxy_manager:
                self.proxy_manager.mark_success(proxy)

            # yt-dlp 下载的字幕文件名格式：<temp_output>.<lang>.srt
            # 查找下载的文件
            expected_path = output_path
            actual_paths = list(output_dir.glob(f"temp_*.{lang_code}.srt"))
            
            # 如果是中文语言代码，扩展搜索模式以支持变体（zh-Hans, zh-Hant, zh-CN, zh-TW 等）
            if not actual_paths and is_chinese_lang(lang_code):
                # yt-dlp 可能返回 zh-Hans、zh-Hant 或其他变体
                # 支持多种字幕格式：srt, vtt, ttml, txt, srv3, json3
                chinese_langs = ["zh", "zh-Hans", "zh-Hant", "zh-CN", "zh-TW", "cmn"]
                subtitle_formats = ["srt", "vtt", "ttml", "txt", "srv3", "json3"]
                for zh_lang in chinese_langs:
                    for fmt in subtitle_formats:
                        actual_paths = list(output_dir.glob(f"temp_*.{zh_lang}.{fmt}"))
                        if actual_paths:
                            logger.debug_i18n("log.found_chinese_variant_file", 
                                             pattern=f"{zh_lang}.{fmt}", 
                                             file=actual_paths[0].name)
                            break
                    if actual_paths:
                        break

            if actual_paths:
                # 找到下载的文件，使用原子写机制移动到目标位置
                actual_path = actual_paths[0]
                if actual_path != expected_path:
                    # 读取文件内容
                    try:
                        content = actual_path.read_text(encoding="utf-8")
                        # 使用原子写写入目标文件
                        if _atomic_write(expected_path, content, mode="w"):
                            # 删除临时文件
                            try:
                                actual_path.unlink()
                            except Exception:
                                pass
                        else:
                            # 原子写失败，保留临时文件
                            logger.error_i18n(
                                "atomic_write_subtitle_failed", path=str(actual_path)
                            )
                            return actual_path
                    except (OSError, IOError, PermissionError) as e:
                        # 文件IO错误
                        from core.logger import translate_exception
                        app_error = AppException(
                            message=translate_exception("exception.read_write_subtitle_failed", error=str(e)),
                            error_type=ErrorType.FILE_IO,
                            cause=e,
                        )
                        logger.error(
                            translate_exception("exception.read_write_subtitle_failed", error=str(app_error)),
                            extra={"error_type": app_error.error_type.value},
                        )
                        raise app_error

                # 清理其他可能的临时文件
                for temp_file in output_dir.glob("temp_*"):
                    if temp_file != actual_path and temp_file != expected_path:
                        try:
                            temp_file.unlink()
                        except Exception:
                            pass
                return expected_path
            else:
                # 检查是否已经存在目标文件
                if expected_path.exists():
                    return expected_path
                logger.warning_i18n(
                    "subtitle_file_not_found", file_name=output_filename
                )
                return None

        except subprocess.TimeoutExpired:
            # 超时错误：标记代理失败
            if proxy and self.proxy_manager:
                from core.logger import translate_log
                self.proxy_manager.mark_failure(proxy, translate_log("log.timeout"))
                logger.warning_i18n("proxy_timeout_download", proxy=proxy)

            from core.logger import translate_log

            error_msg = translate_log("download_subtitle_timeout", lang_code=lang_code)
            app_error = AppException(message=error_msg, error_type=ErrorType.TIMEOUT)
            logger.error_i18n(
                "download_subtitle_timeout",
                lang_code=lang_code,
                error_type=app_error.error_type.value,
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            from core.logger import translate_log

            error_msg = translate_log("download_subtitle_file_io_error", error=str(e))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.FILE_IO, cause=e
            )
            logger.error_i18n(
                "download_subtitle_file_io_error",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            raise app_error
        except Exception as e:
            # 未映射的异常，转换为 AppException
            from core.logger import translate_log

            error_msg = translate_log("download_subtitle_error", error=str(e))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.UNKNOWN, cause=e
            )
            logger.error_i18n(
                "download_subtitle_error",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            raise app_error

    def _download_subtitle_no_convert(
        self,
        url: str,
        lang_code: str,
        output_dir: Path,
        output_filename: str,
        is_auto: bool = False,
        proxy: Optional[str] = None,
    ) -> Optional[Path]:
        """不使用格式转换下载字幕（用于 ffmpeg 不可用时）

        Args:
            url: 视频 URL
            lang_code: 语言代码
            output_dir: 输出目录
            output_filename: 输出文件名
            is_auto: 是否为自动字幕
            proxy: 代理地址（可选）

        Returns:
            下载的字幕文件路径，如果失败则返回 None
        """
        try:
            output_path = output_dir / output_filename
            temp_output = output_dir / f"temp_{output_path.stem}"

            cmd = [
                self.yt_dlp_path,
                "--skip-download",
                "--no-warnings",
                "--output",
                str(temp_output),
            ]

            if proxy:
                cmd.extend(["--proxy", proxy])

            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file_path()
                if cookie_file:
                    cmd.extend(["--cookies", cookie_file])

            cmd.append(url)

            if is_auto:
                cmd.extend(["--write-auto-subs", "--sub-langs", lang_code])
            else:
                cmd.extend(["--write-subs", "--sub-langs", lang_code])

            result = run_command(cmd, timeout=60)

            if result.returncode != 0:
                logger.error_i18n(
                    "ytdlp_download_failed_no_convert", error=result.stderr
                )
                return None

            # 查找下载的文件（可能是 .vtt, .ttml 等格式）
            expected_temp_name = temp_output.name
            actual_paths = list(output_dir.glob(f"{expected_temp_name}.{lang_code}.*"))

            if actual_paths:
                actual_path = actual_paths[0]
                # 如果是非 srt 格式，尝试转换为 srt（如果可能）
                if actual_path.suffix != ".srt":
                    logger.warning_i18n(
                        "subtitle_format_non_srt", format=actual_path.suffix
                    )
                    # 直接使用原始格式
                    if actual_path != output_path:
                        try:
                            content = actual_path.read_text(encoding="utf-8")
                            if _atomic_write(output_path, content, mode="w"):
                                try:
                                    actual_path.unlink()
                                except Exception:
                                    pass
                                return output_path
                        except Exception as e:
                            logger.error_i18n("copy_subtitle_file_failed", error=str(e))
                return actual_path

            return None

        except Exception as e:
            logger.error_i18n("download_subtitle_failed_no_convert", error=str(e))
            return None

    def _verify_subtitle_language(
        self, subtitle_path: Path, expected_lang: str
    ) -> Optional[str]:
        """验证字幕文件的语言

        通过检查字幕内容的前几行，尝试识别语言

        Args:
            subtitle_path: 字幕文件路径
            expected_lang: 期望的语言代码

        Returns:
            检测到的语言代码，如果无法检测则返回 None
        """
        try:
            # 读取前几行字幕内容
            content = subtitle_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            # 提取前10条字幕的文本
            text_samples = []
            for i, line in enumerate(lines):
                if i > 50:  # 只检查前50行
                    break
                # 跳过序号和时间码行
                if line.strip() and not line.strip().isdigit() and "-->" not in line:
                    text_samples.append(line.strip())

            if not text_samples:
                return None

            # 简单的语言检测：检查是否包含阿拉伯文字符
            sample_text = " ".join(text_samples[:5])
            if any("\u0600" <= char <= "\u06ff" for char in sample_text):
                return "ar"  # 阿拉伯语
            # 可以添加更多语言检测逻辑

            # 如果无法确定，返回 None
            return None
        except Exception as e:
            logger.debug_i18n("language_verification_failed", error=str(e))
            return None

    def download_by_lang(
        self, url: str, lang_code: str, output_path: Path, is_auto: bool = False
    ) -> Optional[Path]:
        """直接按语言代码下载字幕（便捷方法）

        Args:
            url: 视频 URL
            lang_code: 语言代码
            output_path: 输出文件路径（完整路径，包含文件名）
            is_auto: 是否为自动字幕

        Returns:
            下载的字幕文件路径，如果失败则返回 None
        """
        output_dir = output_path.parent
        output_filename = output_path.name
        return self._download_subtitle(
            url, lang_code, output_dir, output_filename, is_auto
        )
