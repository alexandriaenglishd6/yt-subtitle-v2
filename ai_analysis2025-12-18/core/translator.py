"""
字幕翻译模块
根据翻译策略调用 AI 翻译或使用官方字幕
符合 error_handling.md 规范：将 LLMException 适配为 AppException
"""

import re
from pathlib import Path
from typing import Optional, Dict

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.prompts import get_translation_prompt
from core.logger import get_logger, translate_log
from core.llm_client import LLMClient, LLMException, LLMErrorType
from core.exceptions import (
    AppException,
    ErrorType,
    map_llm_error_to_app_error,
    TaskCancelledError,
)

logger = get_logger()


class SubtitleTranslator:
    """字幕翻译器

    根据翻译策略决定是否调用 AI 翻译，或使用官方字幕
    """

    def __init__(self, llm: LLMClient, language_config: LanguageConfig):
        """初始化字幕翻译器

        Args:
            llm: LLM 客户端实例（符合 ai_design.md 规范）
            language_config: 语言配置
        """
        self.llm = llm
        self.language_config = language_config
        # 保存翻译错误信息（用于 pipeline 记录失败时获取 error_type）
        self._last_translation_errors: Dict[str, AppException] = {}

    def get_translation_errors(self) -> Dict[str, AppException]:
        """获取翻译错误信息

        Returns:
            字典，包含每个目标语言的错误信息：{target_lang: AppException}
        """
        return self._last_translation_errors.copy()

    def translate(
        self,
        video_info: VideoInfo,
        detection_result: DetectionResult,
        language_config: LanguageConfig,
        download_result: Dict[str, Optional[Path]],
        output_path: Path,
        force_retranslate: bool = False,
        target_languages: Optional[list[str]] = None,
        cancel_token=None,
    ) -> Dict[str, Optional[Path]]:
        """翻译字幕

        根据翻译策略和检测结果，决定是否调用 AI 翻译

        Args:
            video_info: 视频信息
            detection_result: 字幕检测结果
            language_config: 语言配置
            download_result: 下载结果（包含原始字幕和官方翻译字幕路径）
            output_path: 输出目录路径
            force_retranslate: 是否强制重译（忽略已存在的翻译文件）
            target_languages: 需要翻译的目标语言列表（如果为 None，则翻译所有目标语言）
                            注意：此参数用于优化，只翻译没有官方字幕的语言

        Returns:
            字典，包含翻译后的字幕文件路径（按目标语言）：
            {
                "zh-CN": Path,
                ...
            }
        """
        result = {}
        # 清空之前的错误信息
        self._last_translation_errors.clear()

        logger.info_i18n(
            "translator_translate_start",
            target_languages=target_languages
            if target_languages
            else language_config.subtitle_target_languages,
            output_dir=str(output_path),
            official_subtitles=list(
                download_result.get("official_translations", {}).keys()
            ),
            video_id=video_info.video_id,
        )

        if not detection_result.has_subtitles:
            logger.warning_i18n(
                "video_no_subtitle_skip_translation", video_id=video_info.video_id
            )
            return result

        # 确定需要翻译的语言列表（如果未指定，则翻译所有目标语言）
        languages_to_translate = (
            target_languages
            if target_languages is not None
            else language_config.subtitle_target_languages
        )

        logger.info_i18n(
            "translation_languages_needed",
            languages=languages_to_translate,
            video_id=video_info.video_id,
        )

        # 确保输出目录存在
        output_path.mkdir(parents=True, exist_ok=True)

        # 对需要翻译的语言进行翻译
        for target_lang in languages_to_translate:
            # 检查取消状态
            if cancel_token and cancel_token.is_cancelled():
                reason = cancel_token.get_reason() or translate_log("user_cancelled")
                logger.info_i18n(
                    "translation_cancelled", reason=reason, video_id=video_info.video_id
                )
                raise TaskCancelledError(reason)

            logger.info_i18n(
                "translation_target_start",
                target_lang=target_lang,
                video_id=video_info.video_id,
            )
            translated_path = output_path / f"translated.{target_lang}.srt"

            # 检查是否已存在翻译文件（避免重复调用 AI）
            if translated_path.exists() and not force_retranslate:
                logger.info_i18n(
                    "translation_file_exists_skip",
                    file_name=translated_path.name,
                    video_id=video_info.video_id,
                )
                result[target_lang] = translated_path
                continue

            # 注意：如果 target_languages 参数被传入，说明这些语言在 pipeline 层面已经确认没有官方字幕
            # 但为了代码健壮性，这里仍然检查一次（防止 pipeline 和 translator 逻辑不一致）
            # 如果 pipeline 优化正确，这里的检查应该总是 False
            official_path = download_result.get("official_translations", {}).get(
                target_lang
            )

            if official_path and official_path.exists():
                # 有官方翻译字幕，直接使用（不调用 AI）
                # 注意：如果 target_languages 被传入，这种情况理论上不应该发生
                logger.warning_i18n(
                    "log.copy_official_subtitle",
                    target_lang=target_lang,
                    file_name=official_path.name,
                    video_id=video_info.video_id,
                )
                # 复制到 translated.<lang>.srt（确保路径一致）
                if official_path != translated_path:
                    self._copy_to_translated(official_path, translated_path)
                result[target_lang] = translated_path
                continue

            # 根据翻译策略决定是否调用 AI
            if language_config.translation_strategy == "OFFICIAL_ONLY":
                # 只用官方字幕，不调用 AI
                logger.warning_i18n(
                    "log.no_official_subtitle_skip_ai",
                    target_lang=target_lang,
                    video_id=video_info.video_id,
                )
                result[target_lang] = None
                continue

            # 需要调用 AI 翻译
            # 选择源字幕（优先常见语言的官方字幕，其次原始字幕）
            logger.debug_i18n(
                "selecting_source_subtitle_for_translation",
                target_lang=target_lang,
                video_id=video_info.video_id,
            )
            source_subtitle_path = self._select_source_subtitle(
                download_result, detection_result, target_language=target_lang
            )

            if not source_subtitle_path or not source_subtitle_path.exists():
                logger.warning_i18n(
                    "log.no_source_subtitle_for_ai",
                    target_lang=target_lang,
                    original=str(download_result.get("original")),
                    official=list(
                        download_result.get("official_translations", {}).keys()
                    ),
                    video_id=video_info.video_id,
                )
                result[target_lang] = None
                continue

            logger.info_i18n(
                "source_subtitle_selected",
                path=str(source_subtitle_path),
                target_lang=target_lang,
                video_id=video_info.video_id,
            )

            # 调用 AI 翻译
            try:
                logger.info_i18n(
                    "calling_ai_translation",
                    source_file=source_subtitle_path.name,
                    target_lang=target_lang,
                    video_id=video_info.video_id,
                )
                translated_path = self._translate_with_ai(
                    source_subtitle_path,
                    target_lang,
                    translated_path,
                    detection_result,
                    video_info=video_info,
                    cancel_token=cancel_token,
                )
                if translated_path:
                    result[target_lang] = translated_path
                    logger.info_i18n(
                        "ai_translation_complete",
                        file_name=translated_path.name,
                        path=str(translated_path),
                        exists=translated_path.exists(),
                        video_id=video_info.video_id,
                    )
                else:
                    logger.warning_i18n(
                        "ai_translation_returned_none",
                        target_lang=target_lang,
                        video_id=video_info.video_id,
                    )
                    result[target_lang] = None
            except TaskCancelledError:
                # 取消操作，直接重新抛出（不要包装成 AppException）
                raise
            except LLMException as e:
                # 将 LLMException 适配为 AppException
                error_msg = translate_log(
                    "ai_translation_failed", target_lang=target_lang, error=str(e)
                )
                app_error = AppException(
                    message=error_msg,
                    error_type=map_llm_error_to_app_error(e.error_type.value),
                    cause=e,
                )
                logger.error_i18n(
                    "ai_translation_failed",
                    target_lang=target_lang,
                    error=str(app_error),
                    video_id=video_info.video_id,
                    error_type=app_error.error_type.value,
                )
                # 保存错误信息，供 pipeline 使用
                self._last_translation_errors[target_lang] = app_error
                result[target_lang] = None
                # 不抛出异常，继续处理其他语言
            except Exception as e:
                # 未映射的异常，转换为 AppException
                error_msg = translate_log(
                    "ai_translation_failed", target_lang=target_lang, error=str(e)
                )
                app_error = AppException(
                    message=error_msg, error_type=ErrorType.UNKNOWN, cause=e
                )
                logger.error_i18n(
                    "ai_translation_failed",
                    target_lang=target_lang,
                    error=str(app_error),
                    video_id=video_info.video_id,
                    error_type=app_error.error_type.value,
                )
                # 保存错误信息，供 pipeline 使用
                self._last_translation_errors[target_lang] = app_error
                result[target_lang] = None

        return result

    def _select_source_subtitle(
        self,
        download_result: Dict[str, Optional[Path]],
        detection_result: DetectionResult,
        target_language: Optional[str] = None,
    ) -> Optional[Path]:
        """选择源字幕文件（用于 AI 翻译）

        基于检测结果选择源语言，优先级顺序：
        1. 在检测结果中，优先选择常见语言（en, de, ja 等）- 翻译质量更好
        2. 使用原始字幕（人工字幕）
        3. 检测结果中的其他人工字幕
        4. 检测结果中的自动字幕

        Args:
            download_result: 下载结果
            detection_result: 检测结果
            target_language: 目标语言（用于日志）

        Returns:
            源字幕文件路径，如果不存在则返回 None
        """
        # 定义常见语言列表（按优先级排序，用于在检测结果中优先选择）
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

        official_translations = download_result.get("official_translations", {})
        video_id = (
            detection_result.video_id if hasattr(detection_result, "video_id") else None
        )

        # 辅助函数：检查语言代码是否匹配（处理 en vs en-US 的情况）
        def lang_matches(lang1: str, lang2: str) -> bool:
            """检查两个语言代码是否匹配（考虑主语言代码）

            特殊处理：
            - zh-CN 和 zh-TW 不互相匹配（需要精确匹配）
            - 其他语言使用主语言代码匹配（如 en-US 匹配 en）
            """
            if lang1 == lang2:
                return True

            # 特殊处理：zh-CN 和 zh-TW 不互相匹配
            lang1_lower = lang1.lower()
            lang2_lower = lang2.lower()
            if (
                lang1_lower in ["zh-cn", "zh_cn"] and lang2_lower in ["zh-tw", "zh_tw"]
            ) or (
                lang1_lower in ["zh-tw", "zh_tw"] and lang2_lower in ["zh-cn", "zh_cn"]
            ):
                return False

            # 其他语言：提取主语言代码进行匹配
            main1 = lang1.split("-")[0].split("_")[0].lower()
            main2 = lang2.split("-")[0].split("_")[0].lower()
            return main1 == main2

        # 辅助函数：在检测结果中查找匹配的语言
        def find_matching_lang_in_detection(common_lang: str) -> Optional[str]:
            """在检测结果中查找与常见语言匹配的语言代码"""
            # 先检查人工字幕
            if detection_result.manual_languages:
                for lang in detection_result.manual_languages:
                    if lang_matches(lang, common_lang):
                        return lang
            # 再检查自动字幕
            if detection_result.auto_languages:
                for lang in detection_result.auto_languages:
                    if lang_matches(lang, common_lang):
                        return lang
            return None

        # 优先级1：基于检测结果，优先选择常见语言的官方字幕
        # 遍历常见语言列表，在检测结果中查找匹配的语言，然后检查是否已下载
        for common_lang in COMMON_LANGUAGES:
            matched_lang = find_matching_lang_in_detection(common_lang)
            if matched_lang:
                # 检查是否已下载（key 可能是 matched_lang 或 common_lang）
                official_path = official_translations.get(
                    matched_lang
                ) or official_translations.get(common_lang)
                if official_path and official_path.exists():
                    logger.info_i18n(
                        "log.selecting_common_official_as_source",
                        lang=matched_lang,
                        common_lang=common_lang,
                        target_lang=target_language,
                        video_id=video_id,
                    )
                    return official_path

        # 优先级2：使用原始字幕（通常是检测到的第一个人工字幕或自动字幕）
        original_path = download_result.get("original")
        if original_path and original_path.exists():
            logger.info_i18n(
                "selecting_original_as_source",
                target_language=target_language,
                video_id=video_id,
            )
            return original_path

        # 优先级3：使用检测结果中的其他人工字幕（非常见语言）
        if detection_result.manual_languages:
            for lang in detection_result.manual_languages:
                # 检查是否是常见语言（已检查过）
                is_common = any(
                    lang_matches(lang, common_lang) for common_lang in COMMON_LANGUAGES
                )
                if not is_common:
                    official_path = official_translations.get(lang)
                    if official_path and official_path.exists():
                        logger.info_i18n(
                            "log.selecting_manual_as_source",
                            lang=lang,
                            target_lang=target_language,
                            video_id=video_id,
                        )
                        return official_path

        # 优先级4：使用检测结果中的自动字幕（非常见语言）
        if detection_result.auto_languages:
            for lang in detection_result.auto_languages:
                # 检查是否是常见语言（已检查过）
                is_common = any(
                    lang_matches(lang, common_lang) for common_lang in COMMON_LANGUAGES
                )
                if not is_common:
                    official_path = official_translations.get(lang)
                    if official_path and official_path.exists():
                        logger.info_i18n(
                            "log.selecting_auto_as_source",
                            lang=lang,
                            target_lang=target_language,
                            video_id=video_id,
                        )
                        return official_path

        logger.warning_i18n(
            "log.no_source_subtitle_for_translation",
            target_lang=target_language,
            video_id=video_id,
        )
        return None

    def _copy_to_translated(self, source_path: Path, target_path: Path) -> None:
        """将官方翻译字幕复制到 translated.<lang>.srt

        Args:
            source_path: 源文件路径
            target_path: 目标文件路径
        """
        try:
            import shutil

            # 增加安全检查，防止同一文件复制导致 SameFileError
            if source_path.resolve() == target_path.resolve():
                logger.debug_i18n(
                    "log.copy_file_skipped_same_path",
                    source_path=str(source_path),
                    target_path=str(target_path),
                )
                return

            shutil.copy2(source_path, target_path)
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            from core.logger import translate_exception

            app_error = AppException(
                message=translate_exception("exception.copy_file_failed", error=str(e)),
                error_type=ErrorType.FILE_IO,
                cause=e,
            )
            logger.error(
                translate_exception("exception.copy_file_failed", error=str(app_error)),
                extra={"error_type": app_error.error_type.value},
            )
            # 不抛出异常，由调用方决定如何处理
        except Exception as e:
            # 未映射的异常
            from core.logger import translate_exception

            app_error = AppException(
                message=translate_exception("exception.copy_file_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                translate_exception("exception.copy_file_failed", error=str(app_error)),
                extra={"error_type": app_error.error_type.value},
            )

    def _translate_with_ai(
        self,
        source_subtitle_path: Path,
        target_language: str,
        output_path: Path,
        detection_result: DetectionResult,
        video_info: Optional[VideoInfo] = None,
        cancel_token=None,
    ) -> Optional[Path]:
        """使用 AI 翻译字幕文件

        Args:
            source_subtitle_path: 源字幕文件路径
            target_language: 目标语言代码
            output_path: 输出文件路径
            detection_result: 检测结果（用于确定源语言）

        Returns:
            翻译后的字幕文件路径，如果失败则返回 None
        """
        try:
            # 读取源字幕文件
            subtitle_text = self._read_srt_file(source_subtitle_path)
            if not subtitle_text:
                logger.error_i18n(
                    "source_subtitle_read_failed", path=str(source_subtitle_path)
                )
                return None

            # 获取 video_id 用于日志
            video_id = (
                video_info.video_id
                if video_info
                else (
                    detection_result.video_id
                    if hasattr(detection_result, "video_id")
                    else None
                )
            )

            # 确定源语言（优先从文件名提取，更准确）
            source_language = self._extract_language_from_filename(
                source_subtitle_path.name
            )
            if not source_language:
                # 如果无法从文件名提取，使用检测结果
                source_language = self._determine_source_language(detection_result)
                logger.warning_i18n(
                    "source_language_extract_failed",
                    source_lang=source_language,
                    file_name=source_subtitle_path.name,
                    video_id=video_id,
                )

            if not source_language:
                logger.error_i18n(
                    "source_language_undetermined",
                    file_name=source_subtitle_path.name,
                    video_id=video_id,
                )
                return None

            logger.info_i18n(
                "source_language_determined",
                source_lang=source_language,
                file_name=source_subtitle_path.name,
                video_id=video_id,
            )

            # 生成翻译 Prompt
            prompt = get_translation_prompt(
                source_language, target_language, subtitle_text
            )

            # 检查取消状态（在调用 AI 前）
            if cancel_token and cancel_token.is_cancelled():
                reason = cancel_token.get_reason() or translate_log("log.user_cancelled")
                logger.info_i18n(
                    "log.translation_cancelled", reason=reason, video_id=video_id
                )
                raise TaskCancelledError(reason)

            # 调用 AI API
            translated_text = self._call_ai_api(prompt, cancel_token)
            if not translated_text:
                logger.error_i18n("log.ai_api_call_failed")
                return None

            # 保存翻译后的字幕文件（使用原子写）
            from core.failure_logger import _atomic_write

            if not _atomic_write(output_path, translated_text, mode="w"):
                logger.error_i18n(
                    "log.translation_save_failed", error_type=ErrorType.FILE_IO.value
                )
                return None

            return output_path

        except TaskCancelledError:
            # 取消操作，直接重新抛出（不要包装成 AppException）
            raise
        except LLMException as e:
            # 将 LLMException 适配为 AppException
            error_msg = translate_log("ai_translation_error", error=str(e))
            app_error = AppException(
                message=error_msg,
                error_type=map_llm_error_to_app_error(e.error_type.value),
                cause=e,
            )
            logger.error_i18n(
                "ai_translation_error",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            return None
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            error_msg = translate_log("ai_translation_error", error=str(e))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.FILE_IO, cause=e
            )
            logger.error_i18n(
                "ai_translation_error",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            return None
        except Exception as e:
            # 未映射的异常，转换为 AppException
            error_msg = translate_log("ai_translation_error", error=str(e))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.UNKNOWN, cause=e
            )
            logger.error_i18n(
                "ai_translation_error",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            return None

    def _extract_language_from_filename(self, filename: str) -> Optional[str]:
        """从文件名中提取语言代码

        例如：original.en.srt -> en
              translated.zh-CN.srt -> zh-CN

        Args:
            filename: 文件名

        Returns:
            语言代码，如果无法提取则返回 None
        """
        # 匹配 pattern.<lang>.srt 或 pattern.<lang>.md
        match = re.search(
            r"\.([a-z]{2}(?:-[A-Z]{2})?)\.(?:srt|md)$", filename, re.IGNORECASE
        )
        if match:
            return match.group(1)
        return None

    def _determine_source_language(
        self, detection_result: DetectionResult
    ) -> Optional[str]:
        """确定源语言代码

        Args:
            detection_result: 检测结果

        Returns:
            源语言代码，如果无法确定则返回 None
        """
        if detection_result.manual_languages:
            return detection_result.manual_languages[0]
        elif detection_result.auto_languages:
            return detection_result.auto_languages[0]
        else:
            return None

    def _read_srt_file(self, srt_path: Path) -> Optional[str]:
        """读取 SRT 字幕文件

        Args:
            srt_path: SRT 文件路径

        Returns:
            字幕文本内容，如果失败则返回 None
        """
        try:
            return srt_path.read_text(encoding="utf-8")
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            from core.logger import translate_exception

            app_error = AppException(
                message=translate_exception("exception.read_srt_failed", error=str(e)),
                error_type=ErrorType.FILE_IO,
                cause=e,
            )
            logger.error(
                translate_exception("exception.read_srt_failed", error=str(app_error)),
                extra={"error_type": app_error.error_type.value},
            )
            return None
        except Exception as e:
            # 未映射的异常
            from core.logger import translate_exception

            app_error = AppException(
                message=translate_exception("exception.read_srt_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                translate_exception("exception.read_srt_failed", error=str(app_error)),
                extra={"error_type": app_error.error_type.value},
            )
            return None

    def _call_ai_api(self, prompt: str, cancel_token=None) -> Optional[str]:
        """调用 AI API 进行翻译

        Args:
            prompt: 翻译提示词
            cancel_token: 取消令牌（可选）

        Returns:
            翻译后的文本，如果失败则返回 None

        Raises:
            LLMException: 当 LLM 调用失败时抛出
            TaskCancelledError: 当取消令牌被触发时抛出
        """
        # 检查取消状态（在调用 AI 前）
        if cancel_token and cancel_token.is_cancelled():
            reason = cancel_token.get_reason() or translate_log("user_cancelled")
            raise TaskCancelledError(reason)

        try:
            # 如果是 GoogleTranslateClient，设置 cancel_token 以便在翻译过程中检查
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = cancel_token

            # 注意：generate 调用是同步的，在调用期间无法检查取消状态
            # 取消检查需要在字幕块级别的循环中进行（在 GoogleTranslateClient 内部）
            result = self.llm.generate(prompt)

            # 清除 cancel_token（避免影响后续调用）
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = None

            return result.text
        except TaskCancelledError:
            # 清除 cancel_token（如果已设置）
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = None
            # 取消操作，直接重新抛出
            raise
        except LLMException:
            # 清除 cancel_token（如果已设置）
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = None
            # 重新抛出 LLMException，由调用方处理
            raise
        except Exception as e:
            # 清除 cancel_token（如果已设置）
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = None
            # 未映射的异常，转换为 LLMException
            raise LLMException(
                translate_log("log.ai_api_call_failed_detail", error=str(e)),
                LLMErrorType.UNKNOWN,
            )
