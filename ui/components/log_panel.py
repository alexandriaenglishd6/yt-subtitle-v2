"""
日志面板组件
负责显示实时日志输出
"""

import customtkinter as ctk
from datetime import datetime
from typing import Optional, List, Tuple
from core.i18n import t, get_language
from ui.fonts import body_font


class LogPanel(ctk.CTkFrame):
    """日志面板

    显示实时日志输出，支持自动滚动和日志级别过滤
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # 日志级别过滤：ALL, DEBUG, INFO, WARN, ERROR
        self.filter_level = "ALL"
        # 是否自动滚动
        self.auto_scroll = True
        # 存储所有日志条目（用于过滤）：Tuple[timestamp, level, message, video_id]
        self.log_entries: List[Tuple[str, str, str, Optional[str]]] = []
        # 统计信息
        self.stats = {"total": 0, "success": 0, "failed": 0}
        self.running_status = ""
        self.cookie_status = ""  # Cookie 状态（已翻译的文本）
        self.proxy_manager = None  # 代理管理器引用（用于实时获取代理状态）
        # Cookie 状态的原始信息（用于语言切换时重新翻译）
        self._cookie_info = {"cookie": None, "region": None, "test_result": None}
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 日志标题栏（包含统计信息、过滤和滚动控制）
        log_header = ctk.CTkFrame(self, height=40, corner_radius=0)
        log_header.grid(row=0, column=0, sticky="ew")
        log_header.grid_columnconfigure(1, weight=1)  # 中间列（统计信息）可扩展

        # 左侧：标题
        self.log_title = ctk.CTkLabel(
            log_header, text=t("log_output"), font=body_font(weight="bold")
        )
        self.log_title.grid(row=0, column=0, padx=8, pady=4, sticky="w")

        # 中间：统计信息
        stats_frame = ctk.CTkFrame(log_header, fg_color="transparent")
        stats_frame.grid(row=0, column=1, padx=8, pady=4, sticky="ew")

        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="",
            font=body_font(),
            text_color=("gray50", "gray50"),
        )
        self.stats_label.pack(side="left", padx=(8, 0))

        # 增加独立 Cookie 状态标签以便变色（只包含 Cookie 状态，红色不会影响后面的内容）
        self.cookie_status_label = ctk.CTkLabel(
            stats_frame,
            text="",
            font=body_font(),
            text_color=("gray50", "gray50"),
        )
        self.cookie_status_label.pack(side="left", padx=(0, 0))

        # 独立的代理和预计时间标签（不受 Cookie 状态颜色影响）
        self.proxy_eta_label = ctk.CTkLabel(
            stats_frame,
            text="",
            font=body_font(),
            text_color=("gray50", "gray50"),
        )
        self.proxy_eta_label.pack(side="left", padx=(0, 8))

        # 右侧：过滤控件
        filter_frame = ctk.CTkFrame(log_header, fg_color="transparent")
        filter_frame.grid(row=0, column=2, padx=8, pady=4, sticky="e")

        # 日志级别过滤标签
        self.filter_label = ctk.CTkLabel(
            filter_frame, text=t("log_filter_label"), font=body_font()
        )
        self.filter_label.pack(side="left", padx=4)

        # 日志级别下拉框
        filter_values = [
            t("log_filter_all"),
            t("log_filter_debug"),
            t("log_filter_info"),
            t("log_filter_warn"),
            t("log_filter_error"),
        ]
        self.filter_combo = ctk.CTkComboBox(
            filter_frame,
            values=filter_values,
            width=100,
            command=self._on_filter_changed,
        )
        self.filter_combo.set(filter_values[0])  # 默认 ALL
        self.filter_combo.pack(side="left", padx=4)

        # 暂停自动滚动复选框
        self.auto_scroll_checkbox = ctk.CTkCheckBox(
            filter_frame,
            text=t("log_auto_scroll"),
            command=self._on_auto_scroll_toggle,
            font=body_font(),
        )
        self.auto_scroll_checkbox.select()  # 默认选中（启用自动滚动）
        self.auto_scroll_checkbox.pack(side="left", padx=8)

        # 清空日志按钮
        self.clear_log_btn = ctk.CTkButton(
            filter_frame,
            text=t("log_clear"),
            width=60,
            height=24,
            command=self.clear,
            font=body_font(),
        )
        self.clear_log_btn.pack(side="left", padx=4)

        # 日志文本框（只读）
        self.log_text = ctk.CTkTextbox(
            self,
            height=380,  # 255 * 1.5 ≈ 380 (再次增加 50%)
            state="disabled",
            font=body_font(family="Consolas"),
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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 保存日志条目
        self.log_entries.append((timestamp, level, message, video_id))

        # 根据过滤级别决定是否显示
        if not self._should_show_log(level):
            return

        self.log_text.configure(state="normal")

        # 格式化日志消息
        if video_id:
            log_line = f"[{timestamp}] [{level}] [{video_id}] {message}\n"
        else:
            log_line = f"[{timestamp}] [{level}] {message}\n"

        self.log_text.insert("end", log_line)

        # 如果启用自动滚动，滚动到底部
        if self.auto_scroll:
            self.log_text.see("end")

        self.log_text.configure(state="disabled")

    def _should_show_log(self, level: str) -> bool:
        """判断日志是否应该显示（根据过滤级别）

        Args:
            level: 日志级别

        Returns:
            是否应该显示
        """
        if self.filter_level == "ALL":
            return True

        level_upper = level.upper().strip()

        # 只显示指定级别的日志
        if self.filter_level == "DEBUG":
            return level_upper == "DEBUG"
        elif self.filter_level == "INFO":
            return level_upper == "INFO"
        elif self.filter_level == "WARN":
            return level_upper in ("WARN", "WARNING")
        elif self.filter_level == "ERROR":
            return level_upper in ("ERROR", "CRITICAL")

        return True

    def _on_filter_changed(self, value: str):
        """日志级别过滤改变回调

        Args:
            value: 选择的过滤级别显示文本
        """
        # 将显示文本映射到级别值
        filter_map = {
            t("log_filter_all"): "ALL",
            t("log_filter_debug"): "DEBUG",
            t("log_filter_info"): "INFO",
            t("log_filter_warn"): "WARN",
            t("log_filter_error"): "ERROR",
        }

        self.filter_level = filter_map.get(value, "ALL")

        # 重新渲染所有日志（应用过滤）
        self._refresh_log_display()

    def _on_auto_scroll_toggle(self):
        """自动滚动复选框切换回调"""
        self.auto_scroll = self.auto_scroll_checkbox.get() == 1

    def _refresh_log_display(self):
        """刷新日志显示（应用过滤）"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")

        # 重新插入所有应该显示的日志
        for timestamp, level, message, video_id in self.log_entries:
            if self._should_show_log(level):
                if video_id:
                    log_line = f"[{timestamp}] [{level}] [{video_id}] {message}\n"
                else:
                    log_line = f"[{timestamp}] [{level}] {message}\n"
                self.log_text.insert("end", log_line)

        # 如果启用自动滚动，滚动到底部
        if self.auto_scroll:
            self.log_text.see("end")

        self.log_text.configure(state="disabled")

    def clear(self):
        """清空日志"""
        self.log_entries.clear()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def update_stats(self, stats: dict, status: str = ""):
        """更新统计信息
        
        Args:
            stats: 统计信息字典，包含 total, success, failed 等
            status: 当前状态（可选）
        """
        self.stats = stats
        if status:
            self.running_status = status
        
        # 使用 after() 确保在主线程中更新 UI
        # 注意：使用闭包捕获当前的 stats 值
        captured_stats = dict(stats)  # 复制一份避免被后续调用覆盖
        
        def _do_update():
            # 确保使用捕获的 stats 值（避免被后续调用覆盖）
            self.stats = captured_stats
            stats_text, cookie_text, proxy_eta_text, is_error = self._format_stats_v2()
            if hasattr(self, "stats_label"):
                self.stats_label.configure(text=stats_text)
            if hasattr(self, "cookie_status_label"):
                self.cookie_status_label.configure(
                    text=cookie_text,
                    text_color="red" if is_error else ("gray50", "gray50")
                )
            if hasattr(self, "proxy_eta_label"):
                self.proxy_eta_label.configure(text=proxy_eta_text)
            # 强制刷新 UI
            try:
                self.update_idletasks()
            except Exception:
                pass
        
        try:
            self.after(0, _do_update)
        except Exception:
            # 如果 after() 失败（例如窗口已关闭），直接调用
            _do_update()

    def refresh_status_bar(self):
        """刷新状态栏显示（用于代理测试后等需要刷新的场景）"""
        self.update_stats(self.stats, self.running_status)

    def update_cookie_status(
        self,
        cookie_status: str,
        cookie: Optional[str] = None,
        region: Optional[str] = None,
        test_result: Optional[str] = None,
    ):
        """更新 Cookie 状态

        Args:
            cookie_status: Cookie 状态文本（已翻译的文本）
            cookie: Cookie 字符串（可选，用于语言切换时重新翻译）
            region: 地区代码（可选）
            test_result: 测试结果（可选，"success" 或 "failed"）
        """
        self.cookie_status = cookie_status
        # 保存原始信息，用于语言切换时重新翻译
        if cookie is not None:
            self._cookie_info["cookie"] = cookie
        if region is not None:
            self._cookie_info["region"] = region
        if test_result is not None:
            self._cookie_info["test_result"] = test_result
            
        stats_text, cookie_text, proxy_eta_text, is_error = self._format_stats_v2()
        if hasattr(self, "stats_label"):
            self.stats_label.configure(text=stats_text)
        if hasattr(self, "cookie_status_label"):
            self.cookie_status_label.configure(
                text=cookie_text,
                text_color="red" if is_error else ("gray50", "gray50")
            )
        if hasattr(self, "proxy_eta_label"):
            self.proxy_eta_label.configure(text=proxy_eta_text)

    def _format_stats_v2(self) -> Tuple[str, str, str, bool]:
        """格式化统计信息文本 (V2)
        
        Returns:
            Tuple[统计信息文本, Cookie状态文本, 代理和预计时间文本, 是否为错误状态]
        """
        total = self.stats.get("total", 0)
        success = self.stats.get("success", 0)
        failed = self.stats.get("failed", 0)

        # 格式化状态
        if self.running_status:
            if self.running_status.startswith("status_"):
                status_display = t(self.running_status)
            else:
                # Status might be already translated or a key; just use it as is
                status_display = self.running_status
        else:
            status_display = t("status_idle")

        # ETA（预计时间）- 始终显示占位符
        eta_seconds = self.stats.get("eta_seconds")
        if eta_seconds is not None and eta_seconds > 0:
            eta_minutes = int(eta_seconds / 60)
            eta_secs = int(eta_seconds % 60)
            eta_display = f"{eta_minutes}:{eta_secs:02d}"
        else:
            eta_display = "--:--"

        # 代理状态（优先从 proxy_manager 直接获取，确保实时更新）
        proxy_healthy = 0
        proxy_unhealthy = 0
        if self.proxy_manager and hasattr(self.proxy_manager, 'get_healthy_count'):
            proxy_healthy = self.proxy_manager.get_healthy_count()
            proxy_unhealthy = self.proxy_manager.get_unhealthy_count()
        else:
            # 回退到 stats 中的值
            proxy_healthy = self.stats.get("proxy_healthy", 0)
            proxy_unhealthy = self.stats.get("proxy_unhealthy", 0)
        
        proxy_total = proxy_healthy + proxy_unhealthy
        if proxy_total > 0:
            proxy_display = t("proxy_stats", healthy=proxy_healthy, unhealthy=proxy_unhealthy)
        else:
            proxy_display = t("proxy_not_configured")

        # Cookie 部分文本
        is_error = False
        if self._cookie_info["cookie"] is not None:
            cookie = self._cookie_info["cookie"]
            region = self._cookie_info["region"]
            test_result = self._cookie_info["test_result"]
            if cookie:
                if test_result == "failed":
                    cookie_display = t("cookie_status_test_failed")
                    is_error = True
                elif test_result == "expired":
                    cookie_display = t("cookie_status_expired")
                    is_error = True
                elif test_result == "success":
                    if region:
                        cookie_display = t("cookie_status_test_success_with_region", region=region)
                    else:
                        cookie_display = t("cookie_status_test_success")
                else:
                    if region:
                        cookie_display = t("cookie_status_configured_with_region", region=region)
                    else:
                        cookie_display = t("cookie_status_configured")
            else:
                cookie_display = t("cookie_status_not_configured")
        else:
            cookie_display = self.cookie_status if self.cookie_status else t("cookie_status_not_configured")
            if t("cookie_status_test_failed") in cookie_display or t("cookie_status_expired") in cookie_display:
                is_error = True

        # 统计部分文本（新格式：计划 - 已处理 - 状态）
        stats_text = f"{t('stats_planned')}：{total}   ••   {t('stats_processed')}：{t('stats_success')} {success} / {t('stats_failed')} {failed}   ••   {t('stats_status')}：{status_display}   ••   "

        # Cookie 状态（可能变红）
        cookie_text = f"{t('stats_cookie')}：{cookie_display}"
        
        # 代理和预计时间（不受 Cookie 颜色影响）
        proxy_eta_text = f"   ••   {t('stats_proxy')}：{proxy_display}   ••   {t('stats_eta')}：{eta_display}"
        
        return stats_text, cookie_text, proxy_eta_text, is_error

    def refresh_language(self):
        """刷新语言相关文本"""
        if hasattr(self, "log_title"):
            self.log_title.configure(text=t("log_output"))
        
        # 刷新状态栏
        stats_text, cookie_text, proxy_eta_text, is_error = self._format_stats_v2()
        if hasattr(self, "stats_label"):
            self.stats_label.configure(text=stats_text)
        if hasattr(self, "cookie_status_label"):
            self.cookie_status_label.configure(
                text=cookie_text,
                text_color="red" if is_error else ("gray50", "gray50")
            )
        if hasattr(self, "proxy_eta_label"):
            self.proxy_eta_label.configure(text=proxy_eta_text)
        # 刷新过滤控件
        if hasattr(self, "filter_combo"):
            filter_values = [
                t("log_filter_all"),
                t("log_filter_debug"),
                t("log_filter_info"),
                t("log_filter_warn"),
                t("log_filter_error"),
            ]
            # 保存当前选择的级别
            current_level = self.filter_level
            # 更新下拉框选项
            self.filter_combo.configure(values=filter_values)
            # 根据当前级别恢复选择
            level_to_text = {
                "ALL": t("log_filter_all"),
                "DEBUG": t("log_filter_debug"),
                "INFO": t("log_filter_info"),
                "WARN": t("log_filter_warn"),
                "ERROR": t("log_filter_error"),
            }
            if current_level in level_to_text:
                self.filter_combo.set(level_to_text[current_level])
            else:
                self.filter_combo.set(filter_values[0])
        # 刷新自动滚动复选框
        if hasattr(self, "auto_scroll_checkbox"):
            self.auto_scroll_checkbox.configure(text=t("log_auto_scroll"))
        # 刷新过滤标签
        if hasattr(self, "filter_label"):
            self.filter_label.configure(text=t("log_filter_label"))
        # 刷新清空按钮
        if hasattr(self, "clear_log_btn"):
            self.clear_log_btn.configure(text=t("log_clear"))
