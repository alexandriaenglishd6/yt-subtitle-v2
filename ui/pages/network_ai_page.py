"""
网络和 AI 设置页面
包含代理、Cookie、AI 配置等
"""
import customtkinter as ctk
from typing import Callable, Optional
from tkinter import messagebox
import threading
from ui.i18n_manager import t
from core.cookie_manager import CookieManager
from ui.fonts import title_font, heading_font, body_font
from core.logger import get_logger

logger = get_logger()


class NetworkAIPage(ctk.CTkFrame):
    """网络和 AI 设置页面"""
    
    def __init__(
        self,
        parent,
        cookie: str = "",
        proxies: list = None,
        ai_config: Optional[dict] = None,
        output_dir: str = "out",
        on_save_cookie: Optional[Callable[[str], None]] = None,
        on_save_proxies: Optional[Callable[[list], None]] = None,
        on_save_ai_config: Optional[Callable[[dict], None]] = None,
        on_save_output_dir: Optional[Callable[[str], None]] = None,
        on_log_message: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.cookie = cookie
        self.proxies = proxies or []
        self.ai_config = ai_config or {}
        self.output_dir = output_dir
        self.on_save_cookie = on_save_cookie
        self.on_save_proxies = on_save_proxies
        self.on_save_ai_config = on_save_ai_config
        self.on_save_output_dir = on_save_output_dir
        self.on_log_message = on_log_message
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
            text=t("network_ai"),
            font=title_font(weight="bold")
        )
        title.pack(pady=(0, 24))
        
        # Cookie 配置区域
        cookie_frame = ctk.CTkFrame(scroll_frame)
        cookie_frame.pack(fill="x", pady=(0, 16))
        cookie_frame.grid_columnconfigure(0, weight=1)
        
        cookie_label = ctk.CTkLabel(
            cookie_frame,
            text=t("cookie_label"),
            font=heading_font(weight="bold")
        )
        cookie_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8))
        
        # Cookie 输入框（多行文本框）
        self.cookie_textbox = ctk.CTkTextbox(
            cookie_frame,
            height=120,
            wrap="word"
        )
        self.cookie_textbox.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 8))
        if self.cookie:
            self.cookie_textbox.insert("1.0", self.cookie)
        
        # Cookie 按钮区域
        cookie_btn_frame = ctk.CTkFrame(cookie_frame, fg_color="transparent")
        cookie_btn_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 8))
        
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
        cookie_help.grid(row=3, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 16))
        
        # 代理配置区域
        proxy_frame = ctk.CTkFrame(scroll_frame)
        proxy_frame.pack(fill="x", pady=(0, 16))
        proxy_frame.grid_columnconfigure(0, weight=1)
        
        proxy_label = ctk.CTkLabel(
            proxy_frame,
            text=t("proxy_label"),
            font=heading_font(weight="bold")
        )
        proxy_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        # 代理输入框（多行文本框）
        self.proxy_textbox = ctk.CTkTextbox(
            proxy_frame,
            height=100,
            wrap="word"
        )
        self.proxy_textbox.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        if self.proxies:
            self.proxy_textbox.insert("1.0", "\n".join(self.proxies))
        
        # 代理按钮区域
        proxy_btn_frame = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        proxy_btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        
        self.proxy_clear_btn = ctk.CTkButton(
            proxy_btn_frame,
            text=t("proxy_clear"),
            command=self._on_clear_proxies,
            width=120
        )
        self.proxy_clear_btn.pack(side="left", padx=(0, 8))
        
        self.proxy_save_btn = ctk.CTkButton(
            proxy_btn_frame,
            text=t("proxy_save"),
            command=self._on_save_proxies,
            width=120
        )
        self.proxy_save_btn.pack(side="left", padx=(0, 8))
        
        # 代理帮助文本
        proxy_help = ctk.CTkLabel(
            proxy_frame,
            text=t("proxy_placeholder"),
            font=body_font(),
            text_color=("gray50", "gray50"),
            justify="left"
        )
        proxy_help.grid(row=3, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 16))
        
        # AI 配置区域
        ai_frame = ctk.CTkFrame(scroll_frame)
        ai_frame.pack(fill="x", pady=(0, 16))
        ai_frame.grid_columnconfigure(1, weight=1)
        
        ai_label = ctk.CTkLabel(
            ai_frame,
            text=t("ai_config_label"),
            font=heading_font(weight="bold")
        )
        ai_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        # AI Provider
        provider_label = ctk.CTkLabel(ai_frame, text=t("ai_provider_label"))
        provider_label.grid(row=1, column=0, sticky="w", padx=16, pady=8)
        self.ai_provider_entry = ctk.CTkEntry(ai_frame, width=200)
        self.ai_provider_entry.grid(row=1, column=1, sticky="ew", padx=16, pady=8)
        if self.ai_config.get("provider"):
            self.ai_provider_entry.insert(0, self.ai_config["provider"])
        
        # AI Model
        model_label = ctk.CTkLabel(ai_frame, text=t("ai_model_label"))
        model_label.grid(row=2, column=0, sticky="w", padx=16, pady=8)
        self.ai_model_entry = ctk.CTkEntry(ai_frame, width=200)
        self.ai_model_entry.grid(row=2, column=1, sticky="ew", padx=16, pady=8)
        if self.ai_config.get("model"):
            self.ai_model_entry.insert(0, self.ai_config["model"])
        
        # Base URL
        base_url_label = ctk.CTkLabel(ai_frame, text=t("ai_base_url_label"))
        base_url_label.grid(row=3, column=0, sticky="w", padx=16, pady=8)
        self.ai_base_url_entry = ctk.CTkEntry(ai_frame, width=200)
        self.ai_base_url_entry.grid(row=3, column=1, sticky="ew", padx=16, pady=8)
        if self.ai_config.get("base_url"):
            self.ai_base_url_entry.insert(0, self.ai_config["base_url"])
        
        # Timeout
        timeout_label = ctk.CTkLabel(ai_frame, text=t("ai_timeout_label"))
        timeout_label.grid(row=4, column=0, sticky="w", padx=16, pady=8)
        self.ai_timeout_entry = ctk.CTkEntry(ai_frame, width=200)
        self.ai_timeout_entry.grid(row=4, column=1, sticky="ew", padx=16, pady=8)
        if self.ai_config.get("timeout_seconds"):
            self.ai_timeout_entry.insert(0, str(self.ai_config["timeout_seconds"]))
        else:
            self.ai_timeout_entry.insert(0, "30")
        
        # Max Retries
        retries_label = ctk.CTkLabel(ai_frame, text=t("ai_retries_label"))
        retries_label.grid(row=5, column=0, sticky="w", padx=16, pady=8)
        self.ai_retries_entry = ctk.CTkEntry(ai_frame, width=200)
        self.ai_retries_entry.grid(row=5, column=1, sticky="ew", padx=16, pady=8)
        if self.ai_config.get("max_retries"):
            self.ai_retries_entry.insert(0, str(self.ai_config["max_retries"]))
        else:
            self.ai_retries_entry.insert(0, "2")
        
        # API Keys
        api_keys_label = ctk.CTkLabel(ai_frame, text=t("ai_api_keys_label"))
        api_keys_label.grid(row=6, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 4))
        self.ai_api_keys_textbox = ctk.CTkTextbox(ai_frame, height=80, wrap="word")
        self.ai_api_keys_textbox.grid(row=7, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        if self.ai_config.get("api_keys"):
            api_keys_text = "\n".join([f"{k}={v}" for k, v in self.ai_config["api_keys"].items()])
            self.ai_api_keys_textbox.insert("1.0", api_keys_text)
        
        # AI 保存按钮
        ai_btn_frame = ctk.CTkFrame(ai_frame, fg_color="transparent")
        ai_btn_frame.grid(row=8, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        self.ai_save_btn = ctk.CTkButton(
            ai_btn_frame,
            text=t("ai_save"),
            command=self._on_save_ai_config,
            width=120
        )
        self.ai_save_btn.pack(side="left", padx=(0, 8))
        
        # 输出目录配置区域
        output_frame = ctk.CTkFrame(scroll_frame)
        output_frame.pack(fill="x", pady=(0, 16))
        output_frame.grid_columnconfigure(1, weight=1)
        
        output_label = ctk.CTkLabel(
            output_frame,
            text=t("output_dir_label"),
            font=heading_font(weight="bold")
        )
        output_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        output_dir_input_label = ctk.CTkLabel(output_frame, text=t("output_dir_placeholder"))
        output_dir_input_label.grid(row=1, column=0, sticky="w", padx=16, pady=8)
        self.output_dir_entry = ctk.CTkEntry(output_frame, width=200)
        self.output_dir_entry.grid(row=1, column=1, sticky="ew", padx=16, pady=8)
        if self.output_dir:
            self.output_dir_entry.insert(0, self.output_dir)
        
        output_btn_frame = ctk.CTkFrame(output_frame, fg_color="transparent")
        output_btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        self.output_dir_save_btn = ctk.CTkButton(
            output_btn_frame,
            text=t("output_dir_save"),
            command=self._on_save_output_dir,
            width=120
        )
        self.output_dir_save_btn.pack(side="left", padx=(0, 8))
    
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
                # 恢复测试按钮（检查按钮是否还存在）
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
    
    def _on_clear_proxies(self):
        """清空代理列表"""
        self.proxy_textbox.delete("1.0", "end")
        if self.on_log_message:
            self.on_log_message("INFO", "已清空代理列表")
    
    def _on_save_proxies(self):
        """保存代理列表"""
        proxy_text = self.proxy_textbox.get("1.0", "end-1c").strip()
        proxies = [line.strip() for line in proxy_text.split("\n") if line.strip()]
        
        if self.on_save_proxies:
            try:
                self.on_save_proxies(proxies)
                if self.on_log_message:
                    self.on_log_message("INFO", t("proxy_save_success"))
            except Exception as e:
                logger.error(f"保存代理设置失败: {e}")
                if self.on_log_message:
                    self.on_log_message("ERROR", t("proxy_save_failed", error=str(e)))
        else:
            logger.warning("on_save_proxies 回调未设置")
    
    def _on_save_ai_config(self):
        """保存 AI 配置"""
        try:
            ai_config = {
                "provider": self.ai_provider_entry.get().strip(),
                "model": self.ai_model_entry.get().strip(),
                "base_url": self.ai_base_url_entry.get().strip() or None,
                "timeout_seconds": int(self.ai_timeout_entry.get().strip() or "30"),
                "max_retries": int(self.ai_retries_entry.get().strip() or "2"),
                "api_keys": {}
            }
            
            # 解析 API Keys
            api_keys_text = self.ai_api_keys_textbox.get("1.0", "end-1c").strip()
            for line in api_keys_text.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    ai_config["api_keys"][key.strip()] = value.strip()
            
            if self.on_save_ai_config:
                self.on_save_ai_config(ai_config)
                if self.on_log_message:
                    self.on_log_message("INFO", t("ai_save_success"))
        except ValueError as e:
            logger.error(f"AI 配置格式错误: {e}")
            if self.on_log_message:
                self.on_log_message("ERROR", f"{t('ai_save_failed')}: {e}")
        except Exception as e:
            logger.error(f"保存 AI 配置失败: {e}")
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))
    
    def _on_save_output_dir(self):
        """保存输出目录"""
        output_dir = self.output_dir_entry.get().strip()
        if not output_dir:
            output_dir = "out"
        
        if self.on_save_output_dir:
            try:
                self.on_save_output_dir(output_dir)
                if self.on_log_message:
                    self.on_log_message("INFO", t("output_dir_save_success"))
            except Exception as e:
                logger.error(f"保存输出目录失败: {e}")
                if self.on_log_message:
                    self.on_log_message("ERROR", t("output_dir_save_failed", error=str(e)))
        else:
            logger.warning("on_save_output_dir 回调未设置")
    
    def refresh_language(self):
        """刷新语言相关文本"""
        # 标题已在 _build_ui 中设置，这里可以更新其他文本
        pass

