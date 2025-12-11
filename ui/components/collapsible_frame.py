"""
可折叠框架组件
用于创建可展开/折叠的分组
"""
import customtkinter as ctk
from ui.fonts import heading_font, body_font


class CollapsibleFrame(ctk.CTkFrame):
    """可折叠框架
    
    点击标题可以展开/折叠内容
    """
    
    def __init__(self, parent, title: str, expanded: bool = True, use_body_font: bool = False, **kwargs):
        super().__init__(parent, **kwargs)
        self.expanded = expanded
        self.title_text = title
        self.use_body_font = use_body_font
        
        # 内容框架（用于放置可折叠的内容）
        self.content_frame = None
        
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # 标题按钮（可点击展开/折叠）
        font = body_font(weight="bold") if self.use_body_font else heading_font(weight="bold")
        self.title_btn = ctk.CTkButton(
            self,
            text=self._get_title_text(),
            command=self._toggle,
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            font=font
        )
        self.title_btn.pack(fill="x", padx=0, pady=0)
        
        # 内容框架（初始状态根据 expanded 决定）
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        if self.expanded:
            self.content_frame.pack(fill="both", expand=True, padx=0, pady=(8, 0))
        else:
            self.content_frame.pack_forget()
    
    def _get_title_text(self) -> str:
        """获取标题文本（包含展开/折叠图标）"""
        icon = "▼ " if self.expanded else "▶ "
        return f"{icon}{self.title_text}"
    
    def _toggle(self):
        """切换展开/折叠状态"""
        self.expanded = not self.expanded
        
        if self.expanded:
            self.content_frame.pack(fill="both", expand=True, padx=0, pady=(8, 0))
        else:
            self.content_frame.pack_forget()
        
        # 更新标题按钮文本
        self.title_btn.configure(text=self._get_title_text())
    
    def set_expanded(self, expanded: bool):
        """设置展开/折叠状态"""
        if self.expanded != expanded:
            self._toggle()

