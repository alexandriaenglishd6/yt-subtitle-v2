"""
Cookie 配置页面
"""
import customtkinter as ctk
from typing import Callable, Optional
import threading
from ui.i18n_manager import t
from core.cookie_manager import CookieManager
from ui.fonts import title_font, heading_font, body_font
from core.logger import get_logger

logger = get_logger()


class CookiePage(ctk.CTkFrame):
    """Cookie 配置页面"""
    
    def __init__(
        self,
        parent,
        cookie: str = "",
        on_save_cookie: Optional[Callable[[str], None]] = None,
        on_log_message: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.cookie = cookie
        self.on_save_cookie = on_save_cookie
        self.on_log_message = on_log_message
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # 创建滚动框架
        scroll_frame = ctk.CTkScrollableFrame(self)
        scroll_frame.pack(fill="both", expand=True, padx=16, pady=16)
        scroll_frame.grid_columnconfigure(0, weight=1)
        
        # 标题
        title = ctk.CTkLabel(
            scroll_frame,
            text=t("cookie_label"),
            font=title_font(weight="bold")
        )
        title.pack(pady=(0, 24))
        
        # Cookie 配置区域
        cookie_frame = ctk.CTkFrame(scroll_frame)
        cookie_frame.pack(fill="x", pady=(0, 16))
        cookie_frame.grid_columnconfigure(0, weight=1)
        
        # Cookie 输入框（多行文本框）
        self.cookie_textbox = ctk.CTkTextbox(
            cookie_frame,
            height=200,
            wrap="word"
        )
        self.cookie_textbox.grid(row=0, column=0, columnspan=3, sticky="ew", padx=16, pady=(16, 8))
        if self.cookie:
            self.cookie_textbox.insert("1.0", self.cookie)
        
        # Cookie 按钮区域
        cookie_btn_frame = ctk.CTkFrame(cookie_frame, fg_color="transparent")
        cookie_btn_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 8))
        
        self.cookie_paste_btn = ctk.CTkButton(
            cookie_btn_frame,
            text=t("cookie_paste"),
            command=self._on_paste_cookie,
            width=120
        )
        self.cookie_paste_btn.pack(side="left", padx=(0, 8))
        
        self.cookie_clear_btn = ctk.CTkButton(
            cookie_btn_frame,
            text=t("cookie_clear"),
            command=self._on_clear_cookie,
            width=120
        )
        self.cookie_clear_btn.pack(side="left", padx=(0, 8))
        
        self.cookie_test_btn = ctk.CTkButton(
            cookie_btn_frame,
            text=t("cookie_test"),
            command=self._on_test_cookie,
            width=120
        )
        self.cookie_test_btn.pack(side="left", padx=(0, 8))
        
        self.cookie_save_btn = ctk.CTkButton(
            cookie_btn_frame,
            text=t("cookie_save"),
            command=self._on_save_cookie,
            width=120
        )
        self.cookie_save_btn.pack(side="left", padx=(0, 8))
        
        # Cookie 帮助文本
        cookie_help = ctk.CTkLabel(
            cookie_frame,
            text=t("cookie_help"),
            font=body_font(),
            text_color=("gray50", "gray50"),
            justify="left"
        )
        cookie_help.grid(row=2, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 16))
    
    def _on_paste_cookie(self):
        """从剪贴板粘贴 Cookie"""
        try:
            import tkinter as tk
            root = self.winfo_toplevel()
            cookie_text = root.clipboard_get()
            self.cookie_textbox.delete("1.0", "end")
            self.cookie_textbox.insert("1.0", cookie_text)
            if self.on_log_message:
                self.on_log_message("INFO", "已从剪贴板粘贴 Cookie")
        except Exception as e:
            logger.error(f"粘贴 Cookie 失败: {e}")
            if self.on_log_message:
                self.on_log_message("ERROR", f"粘贴 Cookie 失败: {e}")
    
    def _on_clear_cookie(self):
        """清空 Cookie"""
        self.cookie_textbox.delete("1.0", "end")
        if self.on_log_message:
            self.on_log_message("INFO", "已清空 Cookie")
    
    def _on_test_cookie(self):
        """测试 Cookie"""
        cookie_text = self.cookie_textbox.get("1.0", "end-1c").strip()
        if not cookie_text:
            if self.on_log_message:
                self.on_log_message("WARN", t("cookie_empty"))
            return
        
        # 禁用测试按钮
        self.cookie_test_btn.configure(state="disabled", text=t("cookie_test_start"))
        
        def test_in_thread():
            try:
                cookie_manager = CookieManager(cookie_text)
                result = cookie_manager.test_cookie()
                
                if result["available"]:
                    msg = t("cookie_test_success")
                    if result.get("region"):
                        msg += f" (地区: {result['region']})"
                    if self.on_log_message:
                        self.on_log_message("INFO", msg)
                else:
                    error_msg = result.get("error", "未知错误")
                    if self.on_log_message:
                        self.on_log_message("ERROR", f"{t('cookie_test_failed')}: {error_msg}")
                
                cookie_manager.cleanup()
            except Exception as e:
                logger.error(f"测试 Cookie 时出错: {e}")
                if self.on_log_message:
                    self.on_log_message("ERROR", f"{t('cookie_test_failed')}: {e}")
            finally:
                # 恢复测试按钮
                def restore_button():
                    try:
                        if hasattr(self, 'cookie_test_btn') and self.cookie_test_btn.winfo_exists():
                            self.cookie_test_btn.configure(
                                state="normal",
                                text=t("cookie_test")
                            )
                    except Exception as e:
                        logger.debug(f"恢复按钮失败（可能已销毁）: {e}")
                
                self.after(0, restore_button)
        
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()
    
    def _on_save_cookie(self):
        """保存 Cookie"""
        cookie_text = self.cookie_textbox.get("1.0", "end-1c").strip()
        
        if self.on_save_cookie:
            try:
                self.on_save_cookie(cookie_text)
                if self.on_log_message:
                    self.on_log_message("INFO", t("cookie_save_success"))
            except Exception as e:
                logger.error(f"保存 Cookie 失败: {e}")
                if self.on_log_message:
                    self.on_log_message("ERROR", t("cookie_save_failed", error=str(e)))
        else:
            logger.warning("on_save_cookie 回调未设置")

