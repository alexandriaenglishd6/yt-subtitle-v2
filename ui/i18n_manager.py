"""
国际化管理器（UI 层薄封装）

.. deprecated:: v3.2
    此模块已弃用，请直接使用 core.i18n 模块。
    将在未来版本中删除。

    迁移指南：
    - 将 `from ui.i18n_manager import t, set_language`
    - 改为 `from core.i18n import t, set_language`
"""

import warnings
from typing import Optional, Any

# 导入 core.i18n 作为唯一来源
from core.i18n import (
    t as _t,
    tn as _tn,
    set_language as _set_language,
    get_language as _get_language,
    reload_translations as _reload_translations,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
)

# 发出弃用警告（只在首次导入时）
warnings.warn(
    "ui.i18n_manager 已弃用，请直接使用 core.i18n 模块。"
    "此模块将在未来版本中删除。",
    DeprecationWarning,
    stacklevel=2,
)


def load_translations(language: str = None):
    """加载指定语言的翻译文件

    .. deprecated:: v3.2
        此函数已弃用，语言切换请使用 set_language()
    """
    if language is not None:
        _set_language(language)
    return {}  # 返回空字典保持兼容，实际翻译由 core.i18n 管理


def set_language(language: str) -> None:
    """设置当前语言

    Args:
        language: 语言代码（zh-CN / en-US）
    """
    _set_language(language)


def get_language() -> str:
    """获取当前语言代码"""
    return _get_language()


def t(key: str, default: Optional[str] = None, **kwargs: Any) -> str:
    """翻译函数

    Args:
        key: 翻译键
        default: 如果找不到翻译时的默认值（如果为 None，则返回 key）
        **kwargs: 格式化参数（用于 {placeholder} 替换）

    Returns:
        翻译后的文本
    """
    return _t(key, default, **kwargs)


def tn(singular: str, plural: str, n: int, **kwargs: Any) -> str:
    """复数翻译函数

    Args:
        singular: 单数形式的翻译键
        plural: 复数形式的翻译键
        n: 数量
        **kwargs: 格式化参数

    Returns:
        翻译后的文本
    """
    return _tn(singular, plural, n, **kwargs)


def reload_translations() -> None:
    """重新加载所有翻译文件（用于开发时刷新）"""
    _reload_translations()

