"""
JSON I18n Provider

JSON 翻译文件加载器实现（短期方案）
实现 I18nProvider 协议
"""

import json
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class JsonI18nProvider:
    """JSON 翻译文件加载器

    从 core/i18n/locales/ 目录加载 JSON 翻译文件
    支持 fallback 到英文

    Attributes:
        translations: 当前语言的翻译字典
        language: 当前语言代码
    """

    def __init__(self, locale_dir: Path, lang_code: str = "en-US"):
        """初始化 JSON Provider

        Args:
            locale_dir: 翻译文件目录（如 core/i18n/locales/）
            lang_code: 语言代码（如 "zh-CN", "en-US"）
        """
        self.locale_dir = locale_dir
        self.language = lang_code
        self.translations: Dict[str, str] = {}
        self._load(lang_code)

    def _lang_to_filename(self, lang_code: str) -> str:
        """将语言代码转换为文件名

        Args:
            lang_code: 语言代码（zh-CN, en-US）

        Returns:
            文件名（zh_CN.json, en_US.json）
        """
        return lang_code.replace("-", "_") + ".json"

    def _load(self, lang_code: str) -> None:
        """加载翻译文件

        先加载英文作为 fallback，再用目标语言覆盖

        Args:
            lang_code: 目标语言代码
        """
        self.translations.clear()

        # 先加载英文作为 fallback
        en_path = self.locale_dir / self._lang_to_filename("en-US")
        if en_path.exists():
            try:
                self.translations = json.loads(en_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load fallback translations from {en_path}: {e}")

        # 再加载目标语言覆盖
        if lang_code != "en-US":
            target_path = self.locale_dir / self._lang_to_filename(lang_code)
            if target_path.exists():
                try:
                    target_trans = json.loads(target_path.read_text(encoding="utf-8"))
                    self.translations.update(target_trans)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to load translations from {target_path}: {e}")

        self.language = lang_code

    def reload(self, lang_code: Optional[str] = None) -> None:
        """重新加载翻译文件

        Args:
            lang_code: 新的语言代码，如果为 None 则使用当前语言
        """
        self._load(lang_code or self.language)

    def get(self, key: str, default: Optional[str] = None) -> str:
        """获取翻译文本

        如果 key 不存在，返回 key 本身（符合规范要求）

        Args:
            key: 翻译键
            default: 未找到时的默认值（如果为 None，返回 key）

        Returns:
            翻译后的文本
        """
        return self.translations.get(key, default if default is not None else key)

    def nget(self, singular: str, plural: str, n: int) -> str:
        """获取复数形式的翻译

        简单实现：根据 n 选择 key
        未来可升级为 gettext 的复杂复数规则

        Args:
            singular: 单数形式的翻译键
            plural: 复数形式的翻译键
            n: 数量

        Returns:
            对应形式的翻译文本
        """
        key = singular if n == 1 else plural
        return self.translations.get(key, key)

    def get_language(self) -> str:
        """获取当前语言代码

        Returns:
            当前语言代码
        """
        return self.language
