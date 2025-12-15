"""
日志面板组件
负责显示实时日志输出
"""
import customtkinter as ctk
from typing import Optional, List, Tuple
from ui.i18n_manager import t
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
        # 存储所有日志条目（用于过滤）
        self.log_entries: List[Tuple[str, str, Optional[str]]] = []
        # 统计信息
        self.stats = {"total": 0, "success": 0, "failed": 0}
        self.running_status = ""
        self.cookie_status = ""  # Cookie 状态（如 "已配置"、"未配置"、"测试成功"、"测试失败" 等）
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
            log_header,
            text=t("log_output"),
            font=body_font(weight="bold")
        )
        self.log_title.grid(row=0, column=0, padx=8, pady=4, sticky="w")
        
        # 中间：统计信息
        stats_frame = ctk.CTkFrame(log_header, fg_color="transparent")
        stats_frame.grid(row=0, column=1, padx=8, pady=4, sticky="ew")
        
        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text=self._format_stats(),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        self.stats_label.pack(side="left", padx=8)
        
        # 右侧：过滤控件
        filter_frame = ctk.CTkFrame(log_header, fg_color="transparent")
        filter_frame.grid(row=0, column=2, padx=8, pady=4, sticky="e")
        
        # 日志级别过滤标签
        filter_label = ctk.CTkLabel(
            filter_frame,
            text=t("log_filter_label"),
            font=body_font()
        )
        filter_label.pack(side="left", padx=4)
        
        # 日志级别下拉框
        filter_values = [
            t("log_filter_all"),
            t("log_filter_debug"),
            t("log_filter_info"),
            t("log_filter_warn"),
            t("log_filter_error")
        ]
        self.filter_combo = ctk.CTkComboBox(
            filter_frame,
            values=filter_values,
            width=100,
            command=self._on_filter_changed
        )
        self.filter_combo.set(filter_values[0])  # 默认 ALL
        self.filter_combo.pack(side="left", padx=4)
        
        # 暂停自动滚动复选框
        self.auto_scroll_checkbox = ctk.CTkCheckBox(
            filter_frame,
            text=t("log_auto_scroll"),
            command=self._on_auto_scroll_toggle,
            font=body_font()
        )
        self.auto_scroll_checkbox.select()  # 默认选中（启用自动滚动）
        self.auto_scroll_checkbox.pack(side="left", padx=8)
        
        # 日志文本框（只读）
        self.log_text = ctk.CTkTextbox(
            self,
            height=255,  # 170 * 1.5 = 255（增加 50%）
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
        # 保存日志条目
        self.log_entries.append((level, message, video_id))
        
        # 根据过滤级别决定是否显示
        if not self._should_show_log(level):
            return
        
        self.log_text.configure(state="normal")
        
        # 格式化日志消息
        if video_id:
            log_line = f"[{level}] [{video_id}] {message}\n"
        else:
            log_line = f"[{level}] {message}\n"
        
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
        
        level_upper = level.upper()
        
        # 日志级别优先级：ERROR > WARN > INFO > DEBUG
        if self.filter_level == "DEBUG":
            # DEBUG级别显示所有日志
            return level_upper in ("DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL")
        elif self.filter_level == "INFO":
            # INFO级别显示INFO及以上
            return level_upper in ("INFO", "WARN", "WARNING", "ERROR", "CRITICAL")
        elif self.filter_level == "WARN":
            # WARN级别显示WARN及以上
            return level_upper in ("WARN", "WARNING", "ERROR", "CRITICAL")
        elif self.filter_level == "ERROR":
            # ERROR级别只显示ERROR
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
            t("log_filter_error"): "ERROR"
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
        for level, message, video_id in self.log_entries:
            if self._should_show_log(level):
                if video_id:
                    log_line = f"[{level}] [{video_id}] {message}\n"
                else:
                    log_line = f"[{level}] {message}\n"
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
        if hasattr(self, 'stats_label'):
            self.stats_label.configure(text=self._format_stats())
    
    def update_cookie_status(self, cookie_status: str):
        """更新 Cookie 状态
        
        Args:
            cookie_status: Cookie 状态文本（如 "已配置"、"未配置"、"测试成功"、"测试失败" 等）
        """
        self.cookie_status = cookie_status
        if hasattr(self, 'stats_label'):
            self.stats_label.configure(text=self._format_stats())
    
    def _format_stats(self) -> str:
        """格式化统计信息文本"""
        total = self.stats.get("total", 0)
        success = self.stats.get("success", 0)
        failed = self.stats.get("failed", 0)
        
        # 格式化状态
        if self.running_status:
            if self.running_status.startswith("status_"):
                status_display = t(self.running_status)
            else:
                status_display = self.running_status
        else:
            status_display = t("status_idle")
        
        # 格式化 Cookie 状态
        cookie_display = self.cookie_status if self.cookie_status else "未配置"
        
        # 使用更清晰的分隔符，增加间隔（至少3个空格）
        return f"计划：{total}   ••   已处理：成功 {success} / 失败 {failed}   ••   状态：{status_display}   ••   Cookie：{cookie_display}"
    
    def refresh_language(self):
        """刷新语言相关文本"""
        if hasattr(self, 'log_title'):
            self.log_title.configure(text=t("log_output"))
        if hasattr(self, 'stats_label'):
            self.stats_label.configure(text=self._format_stats())
        # 重新添加初始日志消息（使用新语言）
        self.clear()
        self.append_log("INFO", t("gui_started"))

