"""
Cookie 配置模块
负责 Cookie 配置的 UI 和逻辑
"""

import customtkinter as ctk
import threading

from ui.i18n_manager import t
from ui.fonts import heading_font, body_font
from core.cookie_manager import CookieManager
from core.logger import get_logger

logger = get_logger()


class CookieSectionMixin:
    """Cookie 配置 Mixin

    提供 Cookie 配置相关的方法和 UI
    """

    def _build_cookie_section(self, parent_frame):
        """构建 Cookie 配置区域

        Args:
            parent_frame: 父框架
        """
        # Cookie 配置区域
        cookie_frame = ctk.CTkFrame(parent_frame)
        cookie_frame.pack(fill="x", pady=(0, 24))
        cookie_frame.grid_columnconfigure(0, weight=1)

        cookie_label = ctk.CTkLabel(
            cookie_frame, text=t("cookie_label"), font=heading_font(weight="bold")
        )
        cookie_label.grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(16, 8)
        )

        # Cookie 输入框（多行文本框）
        self.cookie_textbox = ctk.CTkTextbox(cookie_frame, height=120, wrap="word")
        self.cookie_textbox.grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 8)
        )

        # Cookie 占位符文本
        self.cookie_placeholder = t("cookie_placeholder")

        # 绑定焦点事件以实现占位符功能
        self.cookie_textbox.bind("<FocusIn>", self._on_cookie_focus_in)
        self.cookie_textbox.bind("<FocusOut>", self._on_cookie_focus_out)
        self.cookie_textbox.bind("<KeyPress>", self._on_cookie_key_press)

        if self.cookie:
            self.cookie_textbox.insert("1.0", self.cookie)
        else:
            self._show_cookie_placeholder()

        # Cookie 按钮区域
        cookie_btn_frame = ctk.CTkFrame(cookie_frame, fg_color="transparent")
        cookie_btn_frame.grid(
            row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 8)
        )

        self.cookie_paste_btn = ctk.CTkButton(
            cookie_btn_frame,
            text=t("cookie_paste"),
            command=self._on_paste_cookie,
            width=120,
        )
        self.cookie_paste_btn.pack(side="left", padx=(0, 8))

        self.cookie_clear_btn = ctk.CTkButton(
            cookie_btn_frame,
            text=t("cookie_clear"),
            command=self._on_clear_cookie,
            width=120,
        )
        self.cookie_clear_btn.pack(side="left", padx=(0, 8))

        self.cookie_test_btn = ctk.CTkButton(
            cookie_btn_frame,
            text=t("cookie_test"),
            command=self._on_test_cookie,
            width=120,
        )
        self.cookie_test_btn.pack(side="left", padx=(0, 8))

        self.cookie_save_btn = ctk.CTkButton(
            cookie_btn_frame,
            text=t("cookie_save"),
            command=self._on_save_cookie,
            width=120,
        )
        self.cookie_save_btn.pack(side="left", padx=(0, 8))

        # 地区信息显示（如果有缓存的地区信息）
        self.region_label = ctk.CTkLabel(
            cookie_frame, text="", font=body_font(), text_color="gray"
        )
        self.region_label.grid(
            row=3, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 16)
        )
        self._update_region_display()

    def _on_paste_cookie(self):
        """从剪贴板粘贴 Cookie"""
        try:
            root = self.winfo_toplevel()
            cookie_text = root.clipboard_get()
            self.cookie_textbox.delete("1.0", "end")
            self.cookie_textbox.insert("1.0", cookie_text)
            self.cookie_is_placeholder = False
            if self.on_log_message:
                self.on_log_message("INFO", t("cookie_pasted"))
        except Exception as e:
            logger.error_i18n("log.cookie_paste_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("cookie_paste_failed_log", error=str(e)))

    def _on_clear_cookie(self):
        """清空 Cookie"""
        self.cookie_textbox.delete("1.0", "end")
        self._show_cookie_placeholder()
        if self.on_log_message:
            self.on_log_message("INFO", t("cookie_cleared"))

    def _show_cookie_placeholder(self):
        """显示 Cookie 占位符"""
        self.cookie_textbox.delete("1.0", "end")
        self.cookie_textbox.insert("1.0", self.cookie_placeholder)
        # 设置占位符文本颜色为灰色
        try:
            self.cookie_textbox.tag_add("placeholder", "1.0", "end")
            self.cookie_textbox.tag_config("placeholder", foreground="gray")
        except Exception:
            # 如果 tag_config 不支持 foreground，尝试其他方式
            pass
        self.cookie_is_placeholder = True

    def _on_cookie_focus_in(self, event):
        """Cookie 输入框获得焦点"""
        if hasattr(self, "cookie_is_placeholder") and self.cookie_is_placeholder:
            self.cookie_textbox.delete("1.0", "end")
            self.cookie_is_placeholder = False

    def _on_cookie_focus_out(self, event):
        """Cookie 输入框失去焦点"""
        content = self.cookie_textbox.get("1.0", "end-1c").strip()
        if not content:
            self._show_cookie_placeholder()

    def _on_cookie_key_press(self, event):
        """Cookie 输入框按键事件"""
        if hasattr(self, "cookie_is_placeholder") and self.cookie_is_placeholder:
            self.cookie_textbox.delete("1.0", "end")
            self.cookie_is_placeholder = False

    def _on_test_cookie(self):
        """测试 Cookie"""
        cookie_text = self.cookie_textbox.get("1.0", "end-1c").strip()

        # 如果是占位符文本，则视为空
        if hasattr(self, "cookie_is_placeholder") and self.cookie_is_placeholder:
            cookie_text = ""

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
                    region = result.get("region")
                    if region:
                        msg += t("region_label_prefix", region=region)
                        # 如果检测到地区信息，自动保存到配置并更新显示
                        if self.on_save_cookie:
                            # 保存 Cookie 和地区信息
                            def save_with_region():
                                try:
                                    self.on_save_cookie(cookie_text, region)
                                    self.network_region = region
                                    self._update_region_display()
                                    # 更新 Cookie 状态显示
                                    if self.on_update_cookie_status:
                                        self.on_update_cookie_status(
                                            cookie_text, region, "success"
                                        )
                                    if self.on_log_message:
                                        self.on_log_message(
                                            "INFO",
                                            t("cookie_region_saved", region=region),
                                        )
                                except Exception as e:
                                    logger.error_i18n(
                                        "cookie_region_save_failed", error=str(e)
                                    )

                            self.after(0, save_with_region)
                    else:
                        # 如果未检测到地区信息，提示用户并只保存 Cookie（保留现有地区信息）
                        msg += t("no_region_detected_hint")
                        if self.on_save_cookie:

                            def save_cookie_only():
                                try:
                                    self.on_save_cookie(
                                        cookie_text, self.network_region
                                    )
                                    # 更新 Cookie 状态显示
                                    if self.on_update_cookie_status:
                                        self.on_update_cookie_status(
                                            cookie_text, self.network_region, "success"
                                        )
                                except Exception as e:
                                    logger.error_i18n(
                                        "cookie_save_failed", error=str(e)
                                    )

                            self.after(0, save_cookie_only)
                        else:
                            # 即使不保存，也更新状态显示（测试成功）
                            if self.on_update_cookie_status:

                                def update_status():
                                    self.on_update_cookie_status(
                                        cookie_text, self.network_region, "success"
                                    )

                                self.after(0, update_status)

                    if self.on_log_message:
                        self.on_log_message("INFO", msg)
                else:
                    # 测试失败，更新状态显示
                    error_msg = result.get("error", t("status_error"))
                    if self.on_log_message:
                        self.on_log_message(
                            "ERROR", f"{t('cookie_test_failed')}: {error_msg}"
                        )
                    # 更新 Cookie 状态显示为测试失败
                    if self.on_update_cookie_status:

                        def update_status_failed():
                            # 测试失败，显示测试失败状态
                            self.on_update_cookie_status(cookie_text, None, "failed")

                        self.after(0, update_status_failed)

                cookie_manager.cleanup()
            except Exception as e:
                logger.error_i18n("log.cookie_test_error", error=str(e))
                if self.on_log_message:
                    self.on_log_message("ERROR", f"{t('cookie_test_failed')}: {e}")
            finally:
                # 恢复测试按钮
                def restore_button():
                    try:
                        if (
                            hasattr(self, "cookie_test_btn")
                            and self.cookie_test_btn.winfo_exists()
                        ):
                            self.cookie_test_btn.configure(
                                state="normal", text=t("cookie_test")
                            )
                    except Exception as e:
                        logger.debug_i18n(
                            "log.cookie_restore_button_failed", error=str(e)
                        )

                self.after(0, restore_button)

        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()

    def _update_region_display(self):
        """更新地区信息显示"""
        if self.network_region:
            self.region_label.configure(
                text=t("current_region_cached", region=self.network_region),
                text_color="gray",
            )
        else:
            self.region_label.configure(text="", text_color="gray")

    def _on_save_cookie(self):
        """保存 Cookie"""
        cookie_text = self.cookie_textbox.get("1.0", "end-1c").strip()

        # 如果是占位符文本，则不保存
        if hasattr(self, "cookie_is_placeholder") and self.cookie_is_placeholder:
            cookie_text = ""

        if self.on_save_cookie:
            try:
                # 保存时保留现有的地区信息（如果未在测试中更新）
                self.on_save_cookie(cookie_text, self.network_region)
                # 更新 Cookie 状态显示
                if self.on_update_cookie_status:
                    self.on_update_cookie_status(cookie_text, self.network_region)
            except Exception as e:
                logger.error_i18n("cookie_save_failed", error=str(e))
                if self.on_log_message:
                    self.on_log_message("ERROR", t("cookie_save_failed", error=str(e)))
        else:
            logger.warning_i18n("callback_not_set", callback="on_save_cookie")
