"""
LanguageConfig & 语言相关工具
语言配置模块
"""
from typing import Literal
from dataclasses import dataclass, field


@dataclass
class LanguageConfig:
    """语言配置模型
    
    明确区分：
    - UI 语言（界面显示语言）
    - 字幕翻译目标语言（字幕要翻成什么）
    - 摘要语言（摘要用什么语言写）
    - 双语字幕模式
    - 翻译策略
    """
    ui_language: str = "zh-CN"  # 界面语言，如 "zh-CN" / "en-US"
    subtitle_target_languages: list[str] = field(default_factory=lambda: ["zh-CN"])  # 字幕翻译目标语言列表
    summary_language: str = "zh-CN"  # 摘要使用的单一语言
    bilingual_mode: Literal["none", "source+target"] = "none"  # 双语字幕模式
    translation_strategy: Literal[
        "AI_ONLY",                 # 总是用 AI 翻译
        "OFFICIAL_AUTO_THEN_AI",   # 优先官方字幕/自动翻译，无则用 AI
        "OFFICIAL_ONLY"            # 只用官方多语言字幕，不调用 AI
    ] = "OFFICIAL_AUTO_THEN_AI"
    
    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "ui_language": self.ui_language,
            "subtitle_target_languages": self.subtitle_target_languages,
            "summary_language": self.summary_language,
            "bilingual_mode": self.bilingual_mode,
            "translation_strategy": self.translation_strategy,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LanguageConfig":
        """从字典创建（用于 JSON 反序列化）"""
        return cls(
            ui_language=data.get("ui_language", "zh-CN"),
            subtitle_target_languages=data.get("subtitle_target_languages", ["zh-CN"]),
            summary_language=data.get("summary_language", "zh-CN"),
            bilingual_mode=data.get("bilingual_mode", "none"),
            translation_strategy=data.get("translation_strategy", "OFFICIAL_AUTO_THEN_AI"),
        )


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
