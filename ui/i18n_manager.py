"""
国际化管理器
支持中英文切换，从 JSON 文件加载翻译
"""

import json
from pathlib import Path
from typing import Dict, Optional

# 支持的语言代码
SUPPORTED_LANGUAGES = ["zh-CN", "en-US"]
DEFAULT_LANGUAGE = "zh-CN"

# 全局语言状态
_current_language: str = DEFAULT_LANGUAGE
_translations: Dict[str, Dict[str, str]] = {}


def load_translations(language: str = None) -> Dict[str, str]:
    """加载指定语言的翻译文件

    Args:
        language: 语言代码（zh-CN / en-US），如果为 None 则使用当前语言

    Returns:
        翻译字典
    """
    if language is None:
        language = _current_language

    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    # 如果已加载且不为空，直接返回（避免重复加载）
    if language in _translations and _translations[language]:
        return _translations[language]

    # 加载翻译文件
    # 使用多种方式查找文件
    translation_file = None

    # 将语言代码转换为文件名格式（zh-CN -> zh_CN.json, en-US -> en_US.json）
    file_name = language.replace("-", "_") + ".json"

    # 方法1：使用 __file__ 相对路径（最可靠）
    try:
        i18n_dir = Path(__file__).parent / "i18n"
        test_file = i18n_dir / file_name
        if test_file.exists():
            translation_file = test_file.resolve()
    except Exception:
        pass

    # 方法2：从项目根目录查找
    if translation_file is None or not translation_file.exists():
        try:
            project_root = Path.cwd()
            alt_path = project_root / "ui" / "i18n" / file_name
            if alt_path.exists():
                translation_file = alt_path.resolve()
        except Exception:
            pass

    if translation_file is None or not translation_file.exists():
        # 只在调试模式下输出错误
        import os

        if os.getenv("DEBUG_I18N", "0") == "1":
            file_name = language.replace("-", "_") + ".json"
            print(f"错误：找不到翻译文件，语言: {language}")
            print(f"  尝试路径1: {Path(__file__).parent / 'i18n' / file_name}")
            print(f"  尝试路径2: {Path.cwd() / 'ui' / 'i18n' / file_name}")
        return {}

    try:
        with open(translation_file, "r", encoding="utf-8") as f:
            translations = json.load(f)
            if translations:  # 确保不是空字典
                _translations[language] = translations
                # 只在调试模式下输出成功信息
                import os

                if os.getenv("DEBUG_I18N", "0") == "1":
                    print(
                        f"成功加载翻译文件: {translation_file}，共 {len(translations)} 个键"
                    )
                return translations
            else:
                import os

                if os.getenv("DEBUG_I18N", "0") == "1":
                    print(f"警告：翻译文件为空: {translation_file}")
                return {}
    except FileNotFoundError:
        import os

        if os.getenv("DEBUG_I18N", "0") == "1":
            print(f"错误：文件不存在: {translation_file}")
        return {}
    except json.JSONDecodeError as e:
        # JSON 解析错误（总是输出，因为这是严重错误）
        print(f"错误：JSON 解析错误 ({translation_file}): {e}")
        return {}
    except Exception as e:
        # 其他错误（总是输出，因为这是严重错误）
        print(f"错误：加载翻译文件失败 ({translation_file}): {e}")
        import traceback

        traceback.print_exc()
        return {}


def set_language(language: str):
    """设置当前语言

    Args:
        language: 语言代码（zh-CN / en-US）
    """
    global _current_language
    if language in SUPPORTED_LANGUAGES:
        # 如果语言发生变化，清除旧语言的缓存，强制重新加载
        if _current_language != language:
            # 清除当前语言的缓存（如果存在）
            if language in _translations:
                del _translations[language]
        _current_language = language
        # 预加载翻译（强制重新加载）
        load_translations(language)


def get_language() -> str:
    """获取当前语言代码"""
    return _current_language


def t(key: str, default: Optional[str] = None, **kwargs) -> str:
    """翻译函数

    Args:
        key: 翻译键
        default: 如果找不到翻译时的默认值（如果为 None，则返回 key）
        **kwargs: 格式化参数（用于 {placeholder} 替换）

    Returns:
        翻译后的文本
    """
    translations = load_translations()

    # 调试：如果翻译为空，打印警告（只在调试模式下）
    import os

    if not translations and os.getenv("DEBUG_I18N", "0") == "1":
        print(f"警告：翻译字典为空，当前语言: {_current_language}")

    text = translations.get(key, default if default is not None else key)

    # 如果返回的是 key 本身，说明翻译未找到（只在调试模式下输出）
    if text == key and default is None and os.getenv("DEBUG_I18N", "0") == "1":
        print(f"警告：未找到翻译键 '{key}'，当前语言: {_current_language}")

    # 支持格式化参数
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            # 格式化失败，返回原文本
            pass

    return text


def reload_translations():
    """重新加载所有翻译文件（用于开发时刷新）"""
    global _translations
    _translations.clear()
    load_translations(_current_language)
