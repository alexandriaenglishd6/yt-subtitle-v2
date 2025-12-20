"""
主题系统
提供 4 套预设主题（白 / 浅灰 / 深灰 / Claude 暖色），基于统一的 token 定义
"""

from typing import Dict, Literal
from dataclasses import dataclass

ThemeName = Literal["light", "light_gray", "dark_gray", "claude_warm"]


@dataclass
class ThemeTokens:
    """主题 token 定义

    所有颜色、间距等视觉元素通过 token 统一管理，便于主题切换
    """

    # 背景色
    bg_primary: str  # 主背景色
    bg_secondary: str  # 次要背景色（如侧边栏）
    bg_tertiary: str  # 第三级背景色（如输入框）

    # 文本色
    text_primary: str  # 主文本色
    text_secondary: str  # 次要文本色
    text_disabled: str  # 禁用文本色

    # 强调色
    accent: str  # 强调色（按钮、链接等）
    accent_hover: str  # 强调色悬停状态

    # 边框色
    border: str  # 边框色
    border_focus: str  # 聚焦边框色

    # 状态色
    success: str  # 成功状态
    warning: str  # 警告状态
    error: str  # 错误状态
    info: str  # 信息状态

    # 间距（像素）
    spacing_small: int = 4
    spacing_medium: int = 8
    spacing_large: int = 16
    spacing_xlarge: int = 24


# 主题定义
THEMES: Dict[ThemeName, ThemeTokens] = {
    "light": ThemeTokens(
        bg_primary="#FFFFFF",
        bg_secondary="#F5F5F5",
        bg_tertiary="#EEEEEE",
        text_primary="#000000",
        text_secondary="#666666",
        text_disabled="#999999",
        accent="#0078D4",
        accent_hover="#005A9E",
        border="#CCCCCC",
        border_focus="#0078D4",
        success="#107C10",
        warning="#FFB900",
        error="#E81123",
        info="#0078D4",
    ),
    "light_gray": ThemeTokens(
        bg_primary="#6E6E6E",
        bg_secondary="#5E5E5E",
        bg_tertiary="#7E7E7E",
        text_primary="#E0E0E0",
        text_secondary="#C0C0C0",
        text_disabled="#A0A0A0",
        accent="#3391FF",
        accent_hover="#52A3FF",
        border="#999999",
        border_focus="#3391FF",
        success="#10B981",
        warning="#F59E0B",
        error="#EF4444",
        info="#3391FF",
    ),
    "dark_gray": ThemeTokens(
        bg_primary="#2D2D2D",
        bg_secondary="#1E1E1E",
        bg_tertiary="#3D3D3D",
        text_primary="#FFFFFF",
        text_secondary="#CCCCCC",
        text_disabled="#888888",
        accent="#4A9EFF",
        accent_hover="#6BB5FF",
        border="#555555",
        border_focus="#4A9EFF",
        success="#6FCF97",
        warning="#F2C94C",
        error="#EB5757",
        info="#4A9EFF",
    ),
    "claude_warm": ThemeTokens(
        bg_primary="#FFF8F0",
        bg_secondary="#F5E6D3",
        bg_tertiary="#E8D5C0",
        text_primary="#3D2817",
        text_secondary="#6B4E3D",
        text_disabled="#9B7D6B",
        accent="#D97757",
        accent_hover="#C46242",
        border="#D4B5A0",
        border_focus="#D97757",
        success="#8B7355",
        warning="#D4A574",
        error="#C46242",
        info="#8B6F5F",
    ),
}


def get_theme(name: ThemeName) -> ThemeTokens:
    """获取指定主题的 token

    Args:
        name: 主题名称

    Returns:
        ThemeTokens 对象
    """
    return THEMES.get(name, THEMES["light"])


def get_theme_names() -> list[str]:
    """获取所有可用主题名称列表"""
    return list(THEMES.keys())


def get_theme_display_name(name: ThemeName, language: str = "zh-CN") -> str:
    """获取主题的显示名称（用于 UI，支持 i18n）

    Args:
        name: 主题名称
        language: 语言代码（zh-CN / en-US）

    Returns:
        显示名称
    """
    # 尝试从 i18n 获取（如果可用）
    try:
        from ui.i18n_manager import t

        if language == "zh-CN":
            key_map = {
                "light": "theme_light",
                "light_gray": "theme_light_gray",
                "dark_gray": "theme_dark_gray",
                "claude_warm": "theme_claude_warm",
            }
            return t(key_map.get(name, name))
        else:
            key_map = {
                "light": "theme_light",
                "light_gray": "theme_light_gray",
                "dark_gray": "theme_dark_gray",
                "claude_warm": "theme_claude_warm",
            }
            return t(key_map.get(name, name))
    except Exception:
        # 如果 i18n 不可用，使用默认名称
        display_names = {
            "light": "亮色（白）",
            "light_gray": "浅灰",
            "dark_gray": "深灰",
            "claude_warm": "Claude 暖色",
        }
        return display_names.get(name, name)


def apply_theme_to_window(window, tokens: ThemeTokens, theme_name: ThemeName):
    """应用主题到窗口及其所有组件
    """
    import customtkinter as ctk

    # 设置 customtkinter 的外观模式（亮色/暗色）
    ctk_theme_map = {
        "light": "light",
        "light_gray": "dark",
        "dark_gray": "dark",
        "claude_warm": "light",
    }
    ctk.set_appearance_mode(ctk_theme_map.get(theme_name, "light"))

    # 设置主窗口背景色为次要背景色（深色），解决组件间隙“露底”问题
    window.configure(fg_color=(tokens.bg_secondary, tokens.bg_secondary))

    # 设置 customtkinter 的默认颜色主题
    ctk.set_default_color_theme("blue")

    # 应用自定义颜色
    _apply_custom_colors(window, tokens)

    # 强制更新窗口
    window.update_idletasks()


def _apply_custom_colors(parent, tokens: ThemeTokens):
    """递归应用自定义颜色到所有组件"""
    try:
        import customtkinter as ctk

        for widget in parent.winfo_children():
            # 根据组件类型应用不同的颜色
            if isinstance(widget, ctk.CTkFrame):
                try:
                    current_color = widget.cget("fg_color")
                    # 跳过透明框架
                    if current_color == "transparent" or current_color == (
                        "transparent",
                        "transparent",
                    ):
                        _apply_custom_colors(widget, tokens)
                        continue

                    # 识别组件用途
                    is_secondary = False
                    try:
                        from ui.components.sidebar import Sidebar
                        from ui.components.toolbar import Toolbar
                        from ui.components.log_panel import LogPanel

                        if isinstance(widget, (Sidebar, Toolbar, LogPanel)):
                            is_secondary = True
                        # 如果父组件是 secondary，子组件通常也应该是 secondary
                        elif hasattr(parent, "_is_secondary") and parent._is_secondary:
                            is_secondary = True
                            widget._is_secondary = True
                    except ImportError:
                        pass

                    # 显式标记判断
                    if hasattr(widget, "_is_primary") and widget._is_primary:
                        bg_color = tokens.bg_primary
                    elif is_secondary:
                        bg_color = tokens.bg_secondary
                        widget._is_secondary = True
                    else:
                        # 默认跟随父组件或使用主背景色
                        bg_color = tokens.bg_primary

                    widget.configure(fg_color=(bg_color, bg_color))
                except Exception:
                    pass
            elif isinstance(widget, ctk.CTkLabel):
                try:
                    # 如果是顶部标题栏标题，强制使用强调色（蓝色等）
                    if hasattr(widget, "_is_top_title") and widget._is_top_title:
                        widget.configure(
                            text_color=(tokens.accent, tokens.accent)
                        )
                    else:
                        widget.configure(
                            text_color=(tokens.text_primary, tokens.text_primary)
                        )
                except Exception:
                    pass
            elif isinstance(widget, ctk.CTkButton):
                try:
                    widget.configure(
                        fg_color=(tokens.accent, tokens.accent),
                        hover_color=(tokens.accent_hover, tokens.accent_hover),
                        text_color=(tokens.text_primary, tokens.text_primary),
                    )
                except Exception:
                    pass
            elif isinstance(widget, ctk.CTkEntry):
                try:
                    widget.configure(
                        fg_color=(tokens.bg_tertiary, tokens.bg_tertiary),
                        text_color=(tokens.text_primary, tokens.text_primary),
                        border_color=(tokens.border, tokens.border),
                    )
                except Exception:
                    pass
            elif isinstance(widget, ctk.CTkTextbox):
                try:
                    widget.configure(
                        fg_color=(tokens.bg_tertiary, tokens.bg_tertiary),
                        text_color=(tokens.text_primary, tokens.text_primary),
                    )
                except Exception:
                    pass
            elif isinstance(widget, ctk.CTkComboBox):
                try:
                    # 获取当前高度，如果已经设置过（如height=10），则保持原高度
                    current_height = (
                        widget.cget("height") if hasattr(widget, "cget") else None
                    )
                    widget.configure(
                        fg_color=(tokens.bg_tertiary, tokens.bg_tertiary),
                        text_color=(tokens.text_primary, tokens.text_primary),
                        button_color=(tokens.accent, tokens.accent),
                        button_hover_color=(tokens.accent_hover, tokens.accent_hover),
                    )
                    # 如果之前设置了自定义高度，恢复它（防止主题应用时覆盖）
                    if (
                        current_height and current_height < 20
                    ):  # 如果高度小于20，说明是自定义的小高度
                        try:
                            widget.configure(height=current_height)
                        except Exception:
                            pass
                    # 延迟再次设置高度，确保生效
                    if current_height and current_height < 20:

                        def restore_height():
                            try:
                                widget.configure(height=current_height)
                            except Exception:
                                pass

                        try:
                            widget.after(10, restore_height)
                        except Exception:
                            pass
                except Exception:
                    pass
            elif isinstance(widget, ctk.CTkScrollableFrame):
                try:
                    # 滚动框架跟随父组件或标记
                    if hasattr(parent, "_is_secondary") and parent._is_secondary:
                        bg_color = tokens.bg_secondary
                    else:
                        bg_color = tokens.bg_primary

                    widget.configure(fg_color=(bg_color, bg_color))
                except Exception:
                    pass

            # 递归处理子组件
            _apply_custom_colors(widget, tokens)
    except Exception:
        pass
