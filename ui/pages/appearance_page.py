"""
外观设置页面
包含主题、语言等外观相关设置
"""

import customtkinter as ctk
from core.i18n import t
from ui.fonts import title_font, heading_font


class AppearancePage(ctk.CTkFrame):
    """外观设置页面"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        # 标题
        title = ctk.CTkLabel(
            self, text=t("appearance_lang"), font=title_font(weight="bold")
        )
        title.pack(pady=16)

        # 占位文本
        placeholder = ctk.CTkLabel(
            self, text=t("page_not_implemented", page="appearance"), font=heading_font()
        )
        placeholder.pack(expand=True)

    def refresh_language(self):
        """刷新语言相关文本"""
        pass
