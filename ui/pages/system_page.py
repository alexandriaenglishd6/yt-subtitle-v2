"""
系统工具页面
包含系统相关工具和设置
"""
import customtkinter as ctk
from ui.i18n_manager import t
from ui.fonts import title_font, heading_font


class SystemPage(ctk.CTkFrame):
    """系统工具页面"""
    
    def __init__(self, parent, on_log=None, **kwargs):
        # 从 kwargs 中移除 on_log，因为 CTkFrame 不支持这个参数
        # 如果将来需要使用，可以保存为实例变量
        self.on_log = on_log
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # 标题
        title = ctk.CTkLabel(
            self,
            text=t("system_tools"),
            font=title_font(weight="bold")
        )
        title.pack(pady=16)
        
        # 占位文本
        placeholder = ctk.CTkLabel(
            self,
            text=t("page_not_implemented", page="system"),
            font=heading_font()
        )
        placeholder.pack(expand=True)
    
    def refresh_language(self):
        """刷新语言相关文本"""
        pass

