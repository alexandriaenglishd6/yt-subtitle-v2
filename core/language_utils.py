"""
语言工具模块

提供语言代码匹配和处理的公共函数
消除 translator.py 和 downloader.py 中的重复代码
"""

from typing import List


def lang_matches(lang1: str, lang2: str) -> bool:
    """检查两个语言代码是否匹配（考虑主语言代码）

    特殊处理：
    - zh-CN 和 zh-TW 不互相匹配（需要精确匹配）
    - 其他语言使用主语言代码匹配（如 en-US 匹配 en）

    Args:
        lang1: 第一个语言代码（如 "en", "en-US", "zh-CN"）
        lang2: 第二个语言代码

    Returns:
        如果两个语言代码匹配则返回 True

    Examples:
        >>> lang_matches("en", "en-US")
        True
        >>> lang_matches("zh-CN", "zh-TW")
        False
        >>> lang_matches("ja", "ja-JP")
        True
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


def get_main_language_code(lang_code: str) -> str:
    """提取主语言代码

    Args:
        lang_code: 完整语言代码（如 "en-US", "zh-CN"）

    Returns:
        主语言代码（如 "en", "zh"）

    Examples:
        >>> get_main_language_code("en-US")
        'en'
        >>> get_main_language_code("zh-CN")
        'zh'
    """
    return lang_code.split("-")[0].split("_")[0].lower()


def find_matching_language(
    target_lang: str, available_languages: List[str]
) -> str | None:
    """在可用语言列表中查找匹配的语言

    Args:
        target_lang: 目标语言代码
        available_languages: 可用语言列表

    Returns:
        匹配的语言代码，如果没有找到则返回 None
    """
    for lang in available_languages:
        if lang_matches(lang, target_lang):
            return lang
    return None
