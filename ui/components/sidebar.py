"""
左侧侧边栏组件
包含导航菜单（任务、运行设置）
"""
import customtkinter as ctk
from typing import Callable, Optional
from ui.i18n_manager import t
from ui.fonts import body_font


class Sidebar(ctk.CTkFrame):
    """左侧侧边栏"""
    
    def __init__(
        self,
        parent,
        on_page_changed: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, width=200, corner_radius=0, **kwargs)
        self.on_page_changed = on_page_changed
        self.grid_propagate(False)
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # 侧边栏内容
        sidebar_content = ctk.CTkScrollableFrame(self)
        sidebar_content.pack(fill="both", expand=True, padx=8, pady=8)
        
        # 主流程分组
        self.task_label = ctk.CTkLabel(
            sidebar_content,
            text=t("sidebar_task"),
            font=body_font(weight="bold")
        )
        self.task_label.pack(pady=(8, 4), anchor="w")
        
        self.channel_mode_btn = ctk.CTkButton(
            sidebar_content,
            text=t("channel_mode"),
            command=lambda: self._switch_page("channel"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30")
        )
        self.channel_mode_btn.pack(fill="x", pady=2)
        
        # URL 列表模式
        self.url_list_mode_btn = ctk.CTkButton(
            sidebar_content,
            text=t("url_list_mode"),
            command=lambda: self._switch_page("url_list"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30")
        )
        self.url_list_mode_btn.pack(fill="x", pady=2)
        
        # 运行设置分组
        self.settings_label = ctk.CTkLabel(
            sidebar_content,
            text=t("sidebar_settings"),
            font=body_font(weight="bold")
        )
        self.settings_label.pack(pady=(16, 4), anchor="w")
        
        self.run_params_btn = ctk.CTkButton(
            sidebar_content,
            text=t("run_params"),
            command=lambda: self._switch_page("run_params"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30")
        )
        self.run_params_btn.pack(fill="x", pady=2)
        
        # 网络设置按钮（点击后显示包含 Cookie 和代理的页面）
        self.network_settings_btn = ctk.CTkButton(
            sidebar_content,
            text=t("network_settings_group"),
            command=lambda: self._switch_page("network_settings"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30")
        )
        self.network_settings_btn.pack(fill="x", pady=2)
        
        # 翻译&摘要按钮（点击后显示包含翻译 AI 和摘要 AI 的页面）
        self.translation_summary_btn = ctk.CTkButton(
            sidebar_content,
            text=t("translation_summary_group"),
            command=lambda: self._switch_page("translation_summary"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30")
        )
        self.translation_summary_btn.pack(fill="x", pady=2)
        
        # 外观 & 系统分组已暂时删除
    
    def _switch_page(self, page_name: str):
        """切换页面"""
        if self.on_page_changed:
            self.on_page_changed(page_name)
    
    def refresh_language(self):
        """刷新语言相关文本"""
        # 刷新分组标签
        if hasattr(self, 'task_label'):
            self.task_label.configure(text=t("sidebar_task"))
        if hasattr(self, 'settings_label'):
            self.settings_label.configure(text=t("sidebar_settings"))
        # 外观与语言和系统工具已暂时删除
        
        # 刷新按钮文本
        if hasattr(self, 'channel_mode_btn'):
            self.channel_mode_btn.configure(text=t("channel_mode"))
        if hasattr(self, 'url_list_mode_btn'):
            self.url_list_mode_btn.configure(text=t("url_list_mode"))
        if hasattr(self, 'run_params_btn'):
            self.run_params_btn.configure(text=t("run_params"))
        if hasattr(self, 'network_settings_btn'):
            self.network_settings_btn.configure(text=t("network_settings_group"))
        if hasattr(self, 'translation_summary_btn'):
            self.translation_summary_btn.configure(text=t("translation_summary_group"))
        # 外观与语言和系统工具已暂时删除

