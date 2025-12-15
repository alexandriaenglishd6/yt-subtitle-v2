"""
LanguageConfig & 语言相关工具
语言配置模块
"""
from typing import Literal, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class LanguageConfig:
    """语言配置模型
    
    明确区分：
    - UI 语言（界面显示语言）
    - 字幕翻译目标语言（字幕要翻成什么）
    - 摘要语言（摘要用什么语言写）
    - 双语字幕模式
    - 翻译策略
    - 字幕输出格式
    """
    ui_language: str = "zh-CN"  # 界面语言，如 "zh-CN" / "en-US"
    subtitle_target_languages: list[str] = field(default_factory=lambda: ["zh-CN"])  # 字幕翻译目标语言列表
    summary_language: str = "zh-CN"  # 摘要使用的单一语言
    source_language: Optional[str] = None  # 源语言（None 表示自动，否则为指定语言代码）
    bilingual_mode: Literal["none", "source+target"] = "none"  # 双语字幕模式
    translation_strategy: Literal[
        "AI_ONLY",                 # 总是用 AI 翻译
        "OFFICIAL_AUTO_THEN_AI",   # 优先官方字幕/自动翻译，无则用 AI
        "OFFICIAL_ONLY"            # 只用官方多语言字幕，不调用 AI
    ] = "OFFICIAL_AUTO_THEN_AI"
    subtitle_format: Literal["srt", "txt", "both"] = "srt"  # 字幕输出格式：srt（带时间轴）、txt（纯文本）、both（两种都输出）
    
    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        result = {
            "ui_language": self.ui_language,
            "subtitle_target_languages": self.subtitle_target_languages,
            "summary_language": self.summary_language,
            "bilingual_mode": self.bilingual_mode,
            "translation_strategy": self.translation_strategy,
            "subtitle_format": self.subtitle_format,
        }
        # 只有当 source_language 不为 None 时才包含（避免保存 None 值）
        if self.source_language is not None:
            result["source_language"] = self.source_language
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "LanguageConfig":
        """从字典创建（用于 JSON 反序列化）
        
        自动处理：
        1. 转换旧字段名为新字段名（向后兼容）
        2. 标准化语言代码
        """
        # 步骤 1：转换旧字段名为新字段名（如果存在）
        if "target_languages" in data and "subtitle_target_languages" not in data:
            data["subtitle_target_languages"] = data.pop("target_languages")
            logger.debug("检测到旧字段名 'target_languages'，已转换为 'subtitle_target_languages'")
        
        # 步骤 2：标准化语言代码
        target_langs = data.get("subtitle_target_languages", ["zh-CN"])
        normalized_target_langs = [normalize_language_code(lang) for lang in target_langs]
        
        summary_lang = normalize_language_code(data.get("summary_language", "zh-CN"))
        ui_lang = normalize_language_code(data.get("ui_language", "zh-CN"))
        
        # 步骤 3：处理源语言字段（如果存在，标准化；如果缺失，保持 None）
        source_lang = data.get("source_language")
        if source_lang is not None:
            source_lang = normalize_language_code(source_lang)
        
        # 步骤 4：统一使用新字段名创建配置对象
        return cls(
            ui_language=ui_lang,
            subtitle_target_languages=normalized_target_langs,
            summary_language=summary_lang,
            source_language=source_lang,
            bilingual_mode=data.get("bilingual_mode", "none"),
            translation_strategy=data.get("translation_strategy", "OFFICIAL_AUTO_THEN_AI"),
            subtitle_format=data.get("subtitle_format", "srt"),
        )


def normalize_language_code(lang_code: str) -> str:
    """标准化语言代码
    
    规则：
    - zh-CN, zh-TW 保持不变（完整格式）
    - 其他语言转换为简短格式（如 en-US -> en）
    
    Args:
        lang_code: 语言代码（如 "en-US", "zh-CN", "en"）
    
    Returns:
        标准化后的语言代码（如 "en", "zh-CN"）
    """
    if not lang_code:
        return lang_code
    
    # 转换为小写以便比较
    lang_code_lower = lang_code.lower()
    
    # zh-CN 和 zh-TW 保持不变（完整格式）
    if lang_code_lower in ["zh-cn", "zh_cn"]:
        return "zh-CN"
    if lang_code_lower in ["zh-tw", "zh_tw"]:
        return "zh-TW"
    
    # 其他语言：提取主语言代码（简短格式）
    # 例如：en-US -> en, ja-JP -> ja, ar-SA -> ar
    main_code = lang_code.split("-")[0].split("_")[0].lower()
    
    # 如果已经是简短格式，直接返回（保持原大小写风格）
    if "-" not in lang_code and "_" not in lang_code:
        return lang_code
    
    # 返回简短格式
    return main_code


def get_language_name(lang_code: str) -> str:
    """根据语言代码获取语言名称（用于 Prompt 模板）
    
    Args:
        lang_code: 语言代码，如 "zh-CN", "en-US"
    
    Returns:
        语言名称，如 "中文", "English"
    """
    lang_map = {
        "zh-CN": "中文",
        "zh-TW": "繁體中文",
        "en-US": "English",
        "en-GB": "English",
        "ja-JP": "日本語",
        "ko-KR": "한국어",
        "es-ES": "Español",
        "fr-FR": "Français",
        "de-DE": "Deutsch",
        "ru-RU": "Русский",
        "ar": "العربية",  # 阿拉伯语
        "ar-SA": "العربية",
        "pt-PT": "Português",
        "pt-BR": "Português",
        "it-IT": "Italiano",
        "hi-IN": "हिन्दी",  # 印地语
    }
    # 尝试精确匹配
    if lang_code in lang_map:
        return lang_map[lang_code]
    # 尝试只匹配主语言代码（如 "zh"）
    main_lang = lang_code.split("-")[0] if "-" in lang_code else lang_code
    for code, name in lang_map.items():
        if code.startswith(main_lang):
            return name
    # 默认返回代码本身
    return lang_code
