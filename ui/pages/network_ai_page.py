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
from ui.components.collapsible_frame import CollapsibleFrame

logger = get_logger()


class NetworkAIPage(ctk.CTkFrame):
    """网络和 AI 设置页面"""
    
    def __init__(
        self,
        parent,
        cookie: str = "",
        proxies: list = None,
        translation_ai_config: Optional[dict] = None,
        summary_ai_config: Optional[dict] = None,
        on_save_cookie: Optional[Callable[[str], None]] = None,
        on_save_proxies: Optional[Callable[[list], None]] = None,
        on_save_ai_config: Optional[Callable[[dict, dict], None]] = None,  # 现在接收两个配置
        on_log_message: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.cookie = cookie
        self.proxies = proxies or []
        self.translation_ai_config = translation_ai_config or {}
        self.summary_ai_config = summary_ai_config or {}
        self.on_save_cookie = on_save_cookie
        self.on_save_proxies = on_save_proxies
        self.on_save_ai_config = on_save_ai_config
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
        
        # ========== 网络设置分组（可折叠） ==========
        network_collapsible = CollapsibleFrame(
            scroll_frame,
            title=t("network_settings_group"),
            expanded=True
        )
        network_collapsible.pack(fill="x", pady=(0, 16))
        
        # Cookie 配置区域
        cookie_frame = ctk.CTkFrame(network_collapsible.content_frame)
        cookie_frame.pack(fill="x", padx=0, pady=(0, 16))
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
        proxy_frame = ctk.CTkFrame(network_collapsible.content_frame)
        proxy_frame.pack(fill="x", padx=0, pady=(0, 16))
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
        
        # ========== 翻译&摘要分组（可折叠） ==========
        translation_summary_collapsible = CollapsibleFrame(
            scroll_frame,
            title=t("translation_summary_group"),
            expanded=True
        )
        translation_summary_collapsible.pack(fill="x", pady=(0, 16))
        
        # AI Profile 状态提示
        self._build_ai_profile_status(translation_summary_collapsible.content_frame)
        
        # 翻译 AI 配置区域
        translation_ai_frame = ctk.CTkFrame(translation_summary_collapsible.content_frame)
        translation_ai_frame.pack(fill="x", padx=0, pady=(0, 16))
        translation_ai_frame.grid_columnconfigure(1, weight=1)
        
        translation_ai_label = ctk.CTkLabel(
            translation_ai_frame,
            text=t("translation_ai_config_label"),
            font=heading_font(weight="bold")
        )
        translation_ai_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        # 翻译 AI 配置字段
        self._build_ai_config_fields(translation_ai_frame, self.translation_ai_config, "translation", start_row=1)
        
        # 摘要 AI 配置区域
        summary_ai_frame = ctk.CTkFrame(translation_summary_collapsible.content_frame)
        summary_ai_frame.pack(fill="x", padx=0, pady=(0, 16))
        summary_ai_frame.grid_columnconfigure(1, weight=1)
        
        summary_ai_label = ctk.CTkLabel(
            summary_ai_frame,
            text=t("summary_ai_config_label"),
            font=heading_font(weight="bold")
        )
        summary_ai_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        # 摘要 AI 配置字段
        self._build_ai_config_fields(summary_ai_frame, self.summary_ai_config, "summary", start_row=1)
        
        # AI 保存按钮（统一保存两个配置）
        ai_btn_frame = ctk.CTkFrame(translation_summary_collapsible.content_frame, fg_color="transparent")
        ai_btn_frame.pack(fill="x", padx=0, pady=(0, 16))
        self.ai_save_btn = ctk.CTkButton(
            ai_btn_frame,
            text=t("ai_save_all"),
            command=self._on_save_ai_config,
            width=120
        )
        self.ai_save_btn.pack(side="left", padx=16, pady=8)
        
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
            logger.error_i18n("log.cookie_paste_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", f"粘贴 Cookie 失败: {e}")
    
    def _on_clear_cookie(self):
        """清空 Cookie"""
        self.cookie_textbox.delete("1.0", "end")
        if self.on_log_message:
            self.on_log_message("INFO", t("cookie_cleared"))
    
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
                logger.error_i18n("log.cookie_test_error", error=str(e))
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
                        logger.debug_i18n("log.cookie_restore_button_failed", error=str(e))
                
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
                logger.error_i18n("cookie_save_failed", error=str(e))
                if self.on_log_message:
                    self.on_log_message("ERROR", t("cookie_save_failed", error=str(e)))
        else:
            logger.warning_i18n("callback_not_set", callback="on_save_cookie")
    
    def _on_clear_proxies(self):
        """清空代理列表"""
        self.proxy_textbox.delete("1.0", "end")
        if self.on_log_message:
            self.on_log_message("INFO", t("proxy_list_cleared"))
    
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
                logger.error_i18n("proxy_save_failed", error=str(e))
                if self.on_log_message:
                    self.on_log_message("ERROR", t("proxy_save_failed", error=str(e)))
        else:
            logger.warning_i18n("callback_not_set", callback="on_save_proxies")
    
    def _build_ai_profile_status(self, parent_frame):
        """构建 AI Profile 状态显示
        
        Args:
            parent_frame: 父框架
        """
        from core.ai_profile_manager import get_profile_manager
        
        profile_frame = ctk.CTkFrame(parent_frame)
        profile_frame.pack(fill="x", padx=0, pady=(0, 16))
        profile_frame.grid_columnconfigure(0, weight=1)
        
        try:
            profile_manager = get_profile_manager()
            profile_manager.load()
            
            # 检查是否有 Profile 配置
            translation_profile = profile_manager.get_profile_for_task("subtitle_translate")
            summary_profile = profile_manager.get_profile_for_task("subtitle_summarize")
            
            if translation_profile or summary_profile:
                # 有 Profile 配置
                status_text = t("ai_profile_status_using")
                status_color = ("green", "lightgreen")
                
                profile_info_lines = []
                if translation_profile:
                    profile_info_lines.append(
                        f"翻译: {translation_profile.name} ({translation_profile.ai_config.provider}/{translation_profile.ai_config.model})"
                    )
                if summary_profile:
                    profile_info_lines.append(
                        f"摘要: {summary_profile.name} ({summary_profile.ai_config.provider}/{summary_profile.ai_config.model})"
                    )
                
                profile_info = "\n".join(profile_info_lines)
            else:
                # 使用默认配置
                status_text = t("ai_profile_status_default")
                status_color = ("gray50", "gray50")
                profile_info = t("ai_profile_info_not_configured")
            
            status_label = ctk.CTkLabel(
                profile_frame,
                text=status_text,
                font=heading_font(weight="bold"),
                text_color=status_color
            )
            status_label.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
            
            info_label = ctk.CTkLabel(
                profile_frame,
                text=profile_info,
                font=body_font(),
                text_color=("gray50", "gray50"),
                justify="left"
            )
            info_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
            
            help_text = (
                "提示：AI Profile 允许你通过 ai_profiles.json 配置文件定义多个 AI 配置组合，"
                "并根据任务类型选择不同的配置。详情请查看 docs/ai_profile_usage.md"
            )
            help_label = ctk.CTkLabel(
                profile_frame,
                text=help_text,
                font=body_font(size=11),
                text_color=("gray50", "gray50"),
                justify="left",
                wraplength=600
            )
            help_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 16))
            
        except Exception as e:
            logger.debug_i18n("log.ai_profile_status_fetch_failed", error=str(e))
            # 如果获取失败，不显示状态信息（静默失败）
    
    def _build_ai_config_fields(self, parent_frame, ai_config: dict, prefix: str, start_row: int = 1):
        """构建 AI 配置字段（辅助方法，用于翻译和摘要配置）
        
        Args:
            parent_frame: 父框架
            ai_config: AI 配置字典
            prefix: 字段前缀（"translation" 或 "summary"）
            start_row: 起始行号
        """
        row = start_row
        
        # Provider
        provider_label = ctk.CTkLabel(parent_frame, text=t("ai_provider_label"))
        provider_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        provider_entry = ctk.CTkEntry(parent_frame, width=200)
        provider_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_provider_entry", provider_entry)
        if ai_config.get("provider"):
            provider_entry.insert(0, ai_config["provider"])
        
        row += 1
        
        # Model
        model_label = ctk.CTkLabel(parent_frame, text=t("ai_model_label"))
        model_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        model_entry = ctk.CTkEntry(parent_frame, width=200)
        model_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_model_entry", model_entry)
        if ai_config.get("model"):
            model_entry.insert(0, ai_config["model"])
        
        row += 1
        
        # Base URL
        base_url_label = ctk.CTkLabel(parent_frame, text=t("ai_base_url_label"))
        base_url_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        base_url_entry = ctk.CTkEntry(parent_frame, width=200)
        base_url_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_base_url_entry", base_url_entry)
        if ai_config.get("base_url"):
            base_url_entry.insert(0, ai_config["base_url"])
        
        row += 1
        
        # Timeout
        timeout_label = ctk.CTkLabel(parent_frame, text=t("ai_timeout_label"))
        timeout_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        timeout_entry = ctk.CTkEntry(parent_frame, width=200)
        timeout_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_timeout_entry", timeout_entry)
        if ai_config.get("timeout_seconds"):
            timeout_entry.insert(0, str(ai_config["timeout_seconds"]))
        else:
            timeout_entry.insert(0, "30")
        
        row += 1
        
        # Max Retries
        retries_label = ctk.CTkLabel(parent_frame, text=t("ai_retries_label"))
        retries_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        retries_entry = ctk.CTkEntry(parent_frame, width=200)
        retries_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_retries_entry", retries_entry)
        if ai_config.get("max_retries"):
            retries_entry.insert(0, str(ai_config["max_retries"]))
        else:
            retries_entry.insert(0, "2")
        
        row += 1
        
        # API Keys
        api_keys_label = ctk.CTkLabel(parent_frame, text=t("ai_api_keys_label"))
        api_keys_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 4))
        api_keys_textbox = ctk.CTkTextbox(parent_frame, height=80, wrap="word")
        api_keys_textbox.grid(row=row+1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        setattr(self, f"{prefix}_ai_api_keys_textbox", api_keys_textbox)
        if ai_config.get("api_keys"):
            api_keys_text = "\n".join([f"{k}={v}" for k, v in ai_config["api_keys"].items()])
            api_keys_textbox.insert("1.0", api_keys_text)
    
    def _on_save_ai_config(self):
        """保存 AI 配置（翻译和摘要）"""
        try:
            # 构建翻译 AI 配置
            translation_ai_config = {
                "provider": getattr(self, "translation_ai_provider_entry").get().strip(),
                "model": getattr(self, "translation_ai_model_entry").get().strip(),
                "base_url": getattr(self, "translation_ai_base_url_entry").get().strip() or None,
                "timeout_seconds": int(getattr(self, "translation_ai_timeout_entry").get().strip() or "30"),
                "max_retries": int(getattr(self, "translation_ai_retries_entry").get().strip() or "2"),
                "api_keys": {}
            }
            
            # 解析翻译 API Keys
            translation_api_keys_text = getattr(self, "translation_ai_api_keys_textbox").get("1.0", "end-1c").strip()
            for line in translation_api_keys_text.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    translation_ai_config["api_keys"][key.strip()] = value.strip()
            
            # 构建摘要 AI 配置
            summary_ai_config = {
                "provider": getattr(self, "summary_ai_provider_entry").get().strip(),
                "model": getattr(self, "summary_ai_model_entry").get().strip(),
                "base_url": getattr(self, "summary_ai_base_url_entry").get().strip() or None,
                "timeout_seconds": int(getattr(self, "summary_ai_timeout_entry").get().strip() or "30"),
                "max_retries": int(getattr(self, "summary_ai_retries_entry").get().strip() or "2"),
                "api_keys": {}
            }
            
            # 解析摘要 API Keys
            summary_api_keys_text = getattr(self, "summary_ai_api_keys_textbox").get("1.0", "end-1c").strip()
            for line in summary_api_keys_text.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    summary_ai_config["api_keys"][key.strip()] = value.strip()
            
            if self.on_save_ai_config:
                self.on_save_ai_config(translation_ai_config, summary_ai_config)
                if self.on_log_message:
                    self.on_log_message("INFO", t("ai_save_success"))
        except ValueError as e:
            logger.error_i18n("log.ai_config_format_error", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", f"{t('ai_save_failed')}: {e}")
        except Exception as e:
            logger.error_i18n("log.ai_config_save_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))
    
    def refresh_language(self):
        """刷新语言相关文本"""
        # 标题已在 _build_ui 中设置，这里可以更新其他文本
        pass

