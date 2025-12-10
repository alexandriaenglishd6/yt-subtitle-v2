"""
日志面板组件
负责显示实时日志输出
"""
import customtkinter as ctk
from typing import Optional
from ui.i18n_manager import t
from ui.fonts import body_font


class LogPanel(ctk.CTkFrame):
    """日志面板
    
    显示实时日志输出，支持自动滚动
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # 日志标题栏
        log_header = ctk.CTkFrame(self, height=30, corner_radius=0)
        log_header.grid(row=0, column=0, sticky="ew")
        log_header.grid_columnconfigure(0, weight=1)
        
        self.log_title = ctk.CTkLabel(
            log_header,
            text=t("log_output"),
            font=body_font(weight="bold")
        )
        self.log_title.pack(side="left", padx=8, pady=4)
        
        # 日志文本框（只读）
        self.log_text = ctk.CTkTextbox(
            self,
            height=170,
            state="disabled",
            font=body_font(family="Consolas")
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        
        # 初始日志消息
        self.append_log("INFO", t("gui_started"))
    
    def append_log(self, level: str, message: str, video_id: Optional[str] = None):
        """追加日志到日志框
        
        Args:
            level: 日志级别（INFO, WARN, ERROR 等）
            message: 日志消息
            video_id: 视频ID（可选）
        """
        self.log_text.configure(state="normal")
        
        # 格式化日志消息
        if video_id:
            log_line = f"[{level}] [{video_id}] {message}\n"
        else:
            log_line = f"[{level}] {message}\n"
        
        self.log_text.insert("end", log_line)
        self.log_text.see("end")  # 自动滚动到底部
        self.log_text.configure(state="disabled")
    
    def clear(self):
        """清空日志"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
    
    def refresh_language(self):
        """刷新语言相关文本"""
        if hasattr(self, 'log_title'):
            self.log_title.configure(text=t("log_output"))
        # 重新添加初始日志消息（使用新语言）
        self.clear()
        self.append_log("INFO", t("gui_started"))

