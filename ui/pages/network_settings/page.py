"""
网络设置页面
包含 Cookie 和代理配置
"""

import customtkinter as ctk
from typing import Callable, Optional

from core.i18n import t
from ui.fonts import title_font
from core.logger import get_logger

# 导入 mixin 模块
from .cookie_section import CookieSectionMixin
from .proxy_section import ProxySectionMixin

logger = get_logger()


class NetworkSettingsPage(CookieSectionMixin, ProxySectionMixin, ctk.CTkFrame):
    """网络设置页面"""

    def __init__(
        self,
        parent,
        cookie: str = "",
        proxies: list = None,
        network_region: Optional[str] = None,
        on_save_cookie: Optional[Callable[[str, Optional[str]], None]] = None,
        on_save_proxies: Optional[Callable[[list], None]] = None,
        on_log_message: Optional[Callable[[str, str], None]] = None,
        on_update_cookie_status: Optional[
            Callable[[str, Optional[str], Optional[str]], None]
        ] = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.cookie = cookie
        self.proxies = proxies or []
        self.network_region = network_region
        self.on_save_cookie = on_save_cookie
        self.on_save_proxies = on_save_proxies
        self.on_log_message = on_log_message
        self.on_update_cookie_status = on_update_cookie_status
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        # 创建滚动框架
        scroll_frame = ctk.CTkScrollableFrame(self)
        scroll_frame.pack(fill="both", expand=True, padx=16, pady=16)
        scroll_frame.grid_columnconfigure(0, weight=1)

        # 标题（居中显示）
        self._title_label = ctk.CTkLabel(
            scroll_frame,
            text=t("network_settings_group"),
            font=title_font(weight="bold"),
            text_color=("black", "white"),  # 强制设置为黑/白
            anchor="center",
        )
        self._title_label.pack(fill="x", pady=(0, 24))

        # Cookie 配置区域
        self._build_cookie_section(scroll_frame)

        # 代理配置区域
        self._build_proxy_section(scroll_frame)
