"""
左侧侧边栏组件
包含导航菜单（任务、运行设置、外观 & 系统）
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
        
        # URL 列表模式（P1，暂时占位）
        self.url_list_mode_btn = ctk.CTkButton(
            sidebar_content,
            text=t("url_list_mode"),
            command=lambda: self._switch_page("url_list"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            state="disabled"  # P1 功能，暂时禁用
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
        
        self.network_ai_btn = ctk.CTkButton(
            sidebar_content,
            text=t("network_ai"),
            command=lambda: self._switch_page("network_ai"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30")
        )
        self.network_ai_btn.pack(fill="x", pady=2)
        
        # 外观 & 系统分组
        self.appearance_label = ctk.CTkLabel(
            sidebar_content,
            text=t("sidebar_appearance"),
            font=body_font(weight="bold")
        )
        self.appearance_label.pack(pady=(16, 4), anchor="w")
        
        self.appearance_lang_btn = ctk.CTkButton(
            sidebar_content,
            text=t("appearance_lang"),
            command=lambda: self._switch_page("appearance"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30")
        )
        self.appearance_lang_btn.pack(fill="x", pady=2)
        
        self.system_tools_btn = ctk.CTkButton(
            sidebar_content,
            text=t("system_tools"),
            command=lambda: self._switch_page("system"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30")
        )
        self.system_tools_btn.pack(fill="x", pady=2)
    
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
        if hasattr(self, 'appearance_label'):
            self.appearance_label.configure(text=t("sidebar_appearance"))
        
        # 刷新按钮文本
        if hasattr(self, 'channel_mode_btn'):
            self.channel_mode_btn.configure(text=t("channel_mode"))
        if hasattr(self, 'url_list_mode_btn'):
            self.url_list_mode_btn.configure(text=t("url_list_mode"))
        if hasattr(self, 'run_params_btn'):
            self.run_params_btn.configure(text=t("run_params"))
        if hasattr(self, 'network_ai_btn'):
            self.network_ai_btn.configure(text=t("network_ai"))
        if hasattr(self, 'appearance_lang_btn'):
            self.appearance_lang_btn.configure(text=t("appearance_lang"))
        if hasattr(self, 'system_tools_btn'):
            self.system_tools_btn.configure(text=t("system_tools"))

