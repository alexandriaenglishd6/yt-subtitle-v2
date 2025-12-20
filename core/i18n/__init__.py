"""
Core I18n Module

统一的国际化入口，提供 t(), tn(), set_language() 函数
解除 Core 对 UI 的依赖

使用方法：
    from core.i18n import t, tn, set_language

    # 设置语言
    set_language("zh-CN")

    # 翻译
    text = t("log.download_started", video_id="abc123")

    # 复数翻译
    text = tn("video.single", "video.plural", 5, count=5)
"""

from pathlib import Path
from typing import Optional, Any

from .json_provider import JsonI18nProvider

# 支持的语言代码
SUPPORTED_LANGUAGES = ["zh-CN", "en-US", "ja-JP"]
DEFAULT_LANGUAGE = "en-US"

# 全局 Provider 实例
_provider: Optional[JsonI18nProvider] = None
_current_language: str = DEFAULT_LANGUAGE


def _get_locale_dir() -> Path:
    """获取 locales 目录路径"""
    return Path(__file__).parent / "locales"


def _ensure_provider() -> JsonI18nProvider:
    """确保 Provider 已初始化"""
    global _provider, _current_language
    if _provider is None:
        _provider = JsonI18nProvider(_get_locale_dir(), _current_language)
    return _provider


def set_language(lang_code: str) -> bool:
    """切换语言

    Args:
        lang_code: 语言代码（如 "zh-CN", "en-US", "ja-JP"）

    Returns:
        是否切换成功
    """
    global _provider, _current_language

    if lang_code not in SUPPORTED_LANGUAGES:
        return False

    _current_language = lang_code

    if _provider is None:
        _provider = JsonI18nProvider(_get_locale_dir(), lang_code)
    else:
        _provider.reload(lang_code)

    return True


def get_language() -> str:
    """获取当前语言代码

    Returns:
        当前语言代码
    """
    return _current_language


def t(key: str, default: Optional[str] = None, **kwargs: Any) -> str:
    """翻译函数（主入口）

    Args:
        key: 翻译键，支持点号分隔（如 "log.download_started"）
        default: 未找到翻译时的默认值，若为 None 则返回 key
        **kwargs: 格式化参数（使用命名占位符）

    Returns:
        翻译后的字符串

    Examples:
        >>> t("download.started", video_id="abc123")
        "开始下载: abc123"  # 中文环境
        "Download started: abc123"  # 英文环境
    """
    provider = _ensure_provider()
    text = provider.get(key, default)
    return _format_safe(text, **kwargs)


def tn(singular: str, plural: str, n: int, **kwargs: Any) -> str:
    """复数翻译函数

    为 10+ 语言准备，不同语言复数规则差异大：
    - 中文：无复数变化
    - 英文：1 个 vs 多个
    - 俄文：复杂的复数规则

    Args:
        singular: 单数形式的翻译键
        plural: 复数形式的翻译键
        n: 数量
        **kwargs: 格式化参数

    Returns:
        翻译后的字符串

    Examples:
        >>> tn("video.single", "video.plural", 5, count=5)
        "5 videos"  # 英文
        "5 个视频"  # 中文（无复数变化，singular 和 plural 可相同）
    """
    provider = _ensure_provider()
    text = provider.nget(singular, plural, n)
    return _format_safe(text, n=n, **kwargs)


def _format_safe(text: str, **kwargs: Any) -> str:
    """安全格式化，缺少参数时不崩溃

    Args:
        text: 待格式化的文本
        **kwargs: 格式化参数

    Returns:
        格式化后的文本，如果失败则返回原文本
    """
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError, IndexError):
        # 格式化失败，返回原文本
        return text


def reload_translations() -> None:
    """重新加载翻译文件（用于开发时刷新）"""
    global _provider
    if _provider is not None:
        _provider.reload()


# 便于导入的别名
__all__ = [
    "t",
    "tn",
    "set_language",
    "get_language",
    "reload_translations",
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
]
