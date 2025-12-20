"""
I18n Provider Protocol

定义翻译提供者的接口协议，为未来 gettext 迁移预留
"""

from typing import Protocol, Optional


class I18nProvider(Protocol):
    """翻译提供者协议

    短期使用 JSON，未来可切换到 gettext
    子类实现此协议即可无缝替换
    """

    def get(self, key: str, default: Optional[str] = None) -> str:
        """获取翻译文本

        Args:
            key: 翻译键
            default: 未找到时的默认值

        Returns:
            翻译后的文本，如果未找到则返回 default 或 key
        """
        ...

    def nget(self, singular: str, plural: str, n: int) -> str:
        """获取复数形式的翻译

        为 10+ 语言准备，不同语言复数规则差异大：
        - 中文：无复数变化
        - 英文：1 个 vs 多个
        - 俄文：复杂的复数规则

        Args:
            singular: 单数形式的翻译键
            plural: 复数形式的翻译键
            n: 数量

        Returns:
            对应形式的翻译文本
        """
        ...

    def get_language(self) -> str:
        """获取当前语言代码

        Returns:
            当前语言代码，如 "zh-CN", "en-US"
        """
        ...
