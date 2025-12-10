"""
运行参数页面
包含并发数设置等运行参数配置
"""
import customtkinter as ctk
from typing import Callable, Optional
from ui.i18n_manager import t
from ui.fonts import title_font, body_font
from ui.fonts import title_font, body_font


class RunParamsPage(ctk.CTkFrame):
    """运行参数页面"""
    
    def __init__(
        self,
        parent,
        concurrency: int = 3,
        on_save: Optional[Callable[[int], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.concurrency = concurrency
        self.on_save = on_save
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # 标题
        title = ctk.CTkLabel(
            self,
            text=t("run_params"),
            font=title_font(weight="bold")
        )
        title.pack(pady=16)
        
        # 并发数量设置
        concurrency_frame = ctk.CTkFrame(self)
        concurrency_frame.pack(fill="x", padx=32, pady=16)
        
        concurrency_label = ctk.CTkLabel(
            concurrency_frame,
            text=t("concurrency_label"),
            font=body_font()
        )
        concurrency_label.pack(side="left", padx=8, pady=8)
        
        self.concurrency_entry = ctk.CTkEntry(
            concurrency_frame,
            width=100,
            placeholder_text="3"
        )
        self.concurrency_entry.pack(side="left", padx=8, pady=8)
        self.concurrency_entry.insert(0, str(self.concurrency))
        
        concurrency_hint = ctk.CTkLabel(
            concurrency_frame,
            text=t("concurrency_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        concurrency_hint.pack(side="left", padx=8, pady=8)
        
        # 保存按钮
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=32, pady=16)
        
        save_btn = ctk.CTkButton(
            button_frame,
            text=t("save_settings"),
            command=self._on_save,
            width=120
        )
        save_btn.pack(side="left", padx=8)
        
        # 提示信息
        hint_label = ctk.CTkLabel(
            self,
            text=t("save_settings_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        hint_label.pack(pady=8)
    
    def _on_save(self):
        """保存运行参数"""
        if self.on_save:
            try:
                concurrency_str = self.concurrency_entry.get().strip()
                if not concurrency_str:
                    return
                concurrency = int(concurrency_str)
                if concurrency <= 0:
                    concurrency = 1
                    self.concurrency_entry.delete(0, "end")
                    self.concurrency_entry.insert(0, "1")
                self.on_save(concurrency)
            except ValueError:
                pass
    
    def refresh_language(self):
        """刷新语言相关文本"""
        # 更新按钮和标签文本
        if hasattr(self, 'concurrency_entry'):
            # 语言切换时不需要更新输入框内容
            pass

