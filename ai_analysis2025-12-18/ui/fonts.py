"""
字体配置模块
统一管理 UI 字体大小规格
"""

import customtkinter as ctk
from typing import Literal

# 字体大小规格定义
FONT_SIZE_TITLE = 22  # 页面主标题
FONT_SIZE_HEADING = 18  # 工具栏标题、分组标签、占位符文本
FONT_SIZE_BODY = (
    14  # 侧边栏分组、统计标签、普通标签、状态文本、提示文本、日志内容、小号提示文本
)


def get_font(
    size: int, weight: Literal["normal", "bold"] = "normal", family: str = None
) -> ctk.CTkFont:
    """获取字体对象

    Args:
        size: 字体大小（22, 18, 14）
        weight: 字体粗细（"normal" 或 "bold"）
        family: 字体族（如 "Consolas"），可选

    Returns:
        CTkFont 对象
    """
    font_kwargs = {"size": size}
    if weight == "bold":
        font_kwargs["weight"] = "bold"
    if family:
        font_kwargs["family"] = family

    return ctk.CTkFont(**font_kwargs)


# 便捷函数
def title_font(weight: Literal["normal", "bold"] = "bold") -> ctk.CTkFont:
    """页面主标题字体（22px）"""
    return get_font(FONT_SIZE_TITLE, weight)


def heading_font(weight: Literal["normal", "bold"] = "bold") -> ctk.CTkFont:
    """工具栏标题、分组标签字体（18px）"""
    return get_font(FONT_SIZE_HEADING, weight)


def body_font(
    weight: Literal["normal", "bold"] = "normal", family: str = None
) -> ctk.CTkFont:
    """正文字体（14px）"""
    return get_font(FONT_SIZE_BODY, weight, family)


def small_font(
    weight: Literal["normal", "bold"] = "normal", family: str = None
) -> ctk.CTkFont:
    """小号字体（14px），已按要求从 11px 上调"""
    return get_font(FONT_SIZE_BODY, weight, family)
