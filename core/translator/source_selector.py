"""
源字幕选择器模块
根据检测结果和下载结果选择最佳源字幕用于 AI 翻译
"""

from pathlib import Path
from typing import Optional, Dict

from core.models import DetectionResult
from core.language_utils import lang_matches
from core.logger import get_logger

logger = get_logger()

# 常见语言列表（按优先级排序，用于在检测结果中优先选择）
# 优先级考虑：翻译质量 + 世界使用人数
COMMON_LANGUAGES = [
    "en",       # 英语 - 使用最广泛，翻译资源最丰富
    "en-US",
    "zh-CN",    # 简体中文 - 使用人数第二
    "zh-TW",    # 繁体中文 - 港澳台用户
    "es",       # 西班牙语 - 世界第三大语言
    "es-ES",
    "de",       # 德语 - 技术内容丰富
    "de-DE",
    "ja",       # 日语
    "ja-JP",
    "fr",       # 法语
    "fr-FR",
    "pt",       # 葡萄牙语
    "pt-PT",
    "ru",       # 俄语
    "ru-RU",
    "ko",       # 韩语
    "ko-KR",
]


class SourceSubtitleSelector:
    """源字幕选择器
    
    基于检测结果选择最佳源语言用于 AI 翻译。
    优先级：常见语言官方字幕 > 原始字幕 > 其他人工字幕 > 自动字幕
    """
    
    def select(
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
        official_translations = download_result.get("official_translations", {})
        video_id = (
            detection_result.video_id if hasattr(detection_result, "video_id") else None
        )

        # 优先级1：基于检测结果，优先选择常见语言的官方字幕
        source = self._select_common_language_subtitle(
            detection_result, official_translations, target_language, video_id
        )
        if source:
            return source

        # 优先级2：使用原始字幕
        source = self._select_original_subtitle(
            download_result, target_language, video_id
        )
        if source:
            return source

        # 优先级3：使用检测结果中的其他人工字幕（非常见语言）
        source = self._select_manual_subtitle(
            detection_result, official_translations, target_language, video_id
        )
        if source:
            return source

        # 优先级4：使用检测结果中的自动字幕（非常见语言）
        source = self._select_auto_subtitle(
            detection_result, official_translations, target_language, video_id
        )
        if source:
            return source

        logger.warning_i18n(
            "log.no_source_subtitle_for_translation",
            target_lang=target_language,
            video_id=video_id,
        )
        return None

    def _find_matching_lang_in_detection(
        self, detection_result: DetectionResult, common_lang: str
    ) -> Optional[str]:
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

    def _select_common_language_subtitle(
        self,
        detection_result: DetectionResult,
        official_translations: Dict[str, Path],
        target_language: Optional[str],
        video_id: Optional[str],
    ) -> Optional[Path]:
        """选择常见语言的官方字幕"""
        for common_lang in COMMON_LANGUAGES:
            matched_lang = self._find_matching_lang_in_detection(detection_result, common_lang)
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
        return None

    def _select_original_subtitle(
        self,
        download_result: Dict[str, Optional[Path]],
        target_language: Optional[str],
        video_id: Optional[str],
    ) -> Optional[Path]:
        """选择原始字幕"""
        original_path = download_result.get("original")
        if original_path and original_path.exists():
            logger.info_i18n(
                "selecting_original_as_source",
                target_language=target_language,
                video_id=video_id,
            )
            return original_path
        return None

    def _select_manual_subtitle(
        self,
        detection_result: DetectionResult,
        official_translations: Dict[str, Path],
        target_language: Optional[str],
        video_id: Optional[str],
    ) -> Optional[Path]:
        """选择人工字幕（非常见语言）"""
        if not detection_result.manual_languages:
            return None
            
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
        return None

    def _select_auto_subtitle(
        self,
        detection_result: DetectionResult,
        official_translations: Dict[str, Path],
        target_language: Optional[str],
        video_id: Optional[str],
    ) -> Optional[Path]:
        """选择自动字幕（非常见语言）"""
        if not detection_result.auto_languages:
            return None
            
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
        return None


# 便捷函数
def select_source_subtitle(
    download_result: Dict[str, Optional[Path]],
    detection_result: DetectionResult,
    target_language: Optional[str] = None,
) -> Optional[Path]:
    """选择源字幕文件的便捷函数"""
    selector = SourceSubtitleSelector()
    return selector.select(download_result, detection_result, target_language)
