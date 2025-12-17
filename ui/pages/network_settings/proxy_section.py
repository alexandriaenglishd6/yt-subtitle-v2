"""
代理配置模块
负责代理配置的 UI 和逻辑
"""
import customtkinter as ctk
import threading
from typing import Callable, Optional

from ui.i18n_manager import t
from ui.fonts import heading_font
from core.logger import get_logger

# 导入代理测试模块
from .proxy_tester import ProxyTesterMixin

logger = get_logger()


class ProxySectionMixin(ProxyTesterMixin):
    """代理配置 Mixin
    
    提供代理配置相关的方法和 UI
    """
    
    def _build_proxy_section(self, parent_frame):
        """构建代理配置区域
        
        Args:
            parent_frame: 父框架
        """
        # 代理配置区域
        proxy_frame = ctk.CTkFrame(parent_frame)
        proxy_frame.pack(fill="x", pady=(0, 24))
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
        
        # 代理占位符文本
        self.proxy_placeholder = t("proxy_placeholder")
        
        # 绑定焦点事件以实现占位符功能
        self.proxy_textbox.bind("<FocusIn>", self._on_proxy_focus_in)
        self.proxy_textbox.bind("<FocusOut>", self._on_proxy_focus_out)
        self.proxy_textbox.bind("<KeyPress>", self._on_proxy_key_press)
        
        if self.proxies:
            self.proxy_textbox.insert("1.0", "\n".join(self.proxies))
        else:
            self._show_proxy_placeholder()
        
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
        
        self.proxy_test_btn = ctk.CTkButton(
            proxy_btn_frame,
            text=t("proxy_test_connection"),
            command=self._on_test_proxies,
            width=120,
            fg_color="gray50",
            hover_color="gray40"
        )
        self.proxy_test_btn.pack(side="left", padx=(0, 8))
    
    def _on_clear_proxies(self):
        """清空代理列表"""
        self.proxy_textbox.delete("1.0", "end")
        self._show_proxy_placeholder()
        if self.on_log_message:
            self.on_log_message("INFO", t("proxy_list_cleared"))
    
    def _show_proxy_placeholder(self):
        """显示代理占位符"""
        self.proxy_textbox.delete("1.0", "end")
        self.proxy_textbox.insert("1.0", self.proxy_placeholder)
        # 设置占位符文本颜色为灰色
        try:
            self.proxy_textbox.tag_add("placeholder", "1.0", "end")
            self.proxy_textbox.tag_config("placeholder", foreground="gray")
        except Exception:
            # 如果 tag_config 不支持 foreground，尝试其他方式
            pass
        self.proxy_is_placeholder = True
    
    def _on_proxy_focus_in(self, event):
        """代理输入框获得焦点"""
        if hasattr(self, 'proxy_is_placeholder') and self.proxy_is_placeholder:
            self.proxy_textbox.delete("1.0", "end")
            self.proxy_is_placeholder = False
    
    def _on_proxy_focus_out(self, event):
        """代理输入框失去焦点"""
        content = self.proxy_textbox.get("1.0", "end-1c").strip()
        if not content:
            self._show_proxy_placeholder()
    
    def _on_proxy_key_press(self, event):
        """代理输入框按键事件"""
        if hasattr(self, 'proxy_is_placeholder') and self.proxy_is_placeholder:
            self.proxy_textbox.delete("1.0", "end")
            self.proxy_is_placeholder = False
    
    def _on_save_proxies(self):
        """保存代理列表"""
        proxy_text = self.proxy_textbox.get("1.0", "end-1c").strip()
        
        # 如果是占位符文本，则视为空
        if hasattr(self, 'proxy_is_placeholder') and self.proxy_is_placeholder:
            proxy_text = ""
        
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
    
    def _on_test_proxies(self):
        """测试代理连通性"""
        from urllib.parse import urlparse
        
        # 获取代理列表
        proxy_text = self.proxy_textbox.get("1.0", "end-1c").strip()
        
        # 如果是占位符文本，则视为空
        if hasattr(self, 'proxy_is_placeholder') and self.proxy_is_placeholder:
            proxy_text = ""
        
        proxies = [line.strip() for line in proxy_text.split("\n") if line.strip()]
        
        if not proxies:
            if self.on_log_message:
                self.on_log_message("WARN", t("proxy_test_no_proxy"))
            return
        
        # 禁用测试按钮
        self.proxy_test_btn.configure(state="disabled", text=t("proxy_testing"))
        
        # 添加测试开始日志
        if self.on_log_message:
            self.on_log_message("INFO", t("log.proxy_test_start", count=len(proxies)))
        
        def test_in_thread():
            """在后台线程中测试代理"""
            try:
                # 调用代理测试方法
                results = self._test_proxy_list(proxies, self.on_log_message)
                
                # 统计结果
                success_count = sum(1 for r in results if r["success"])
                failed_count = len(results) - success_count
                total = len(proxies)
                
                # 更新UI
                def update_ui():
                    self.proxy_test_btn.configure(
                        state="normal",
                        text=t("proxy_test_connection")
                    )
                    
                    if self.on_log_message:
                        # 显示测试总结
                        if success_count > 0:
                            self.on_log_message("INFO", t("log.proxy_test_success_summary", success=success_count, total=total))
                        if failed_count > 0:
                            self.on_log_message("WARN", t("log.proxy_test_complete", failed=failed_count, total=total))
                        
                        # 显示每个代理的测试结果（只显示失败的结果，成功的已在测试过程中显示）
                        for result in results:
                            if not result["success"]:
                                # 隐藏密码的代理URL（用于错误日志显示）
                                failed_proxy = result['proxy']
                                try:
                                    failed_parsed = urlparse(failed_proxy)
                                    if failed_parsed.username or failed_parsed.password:
                                        failed_proxy = f"{failed_parsed.scheme}://{failed_parsed.username or ''}:***@{failed_parsed.hostname}:{failed_parsed.port or ''}"
                                except Exception:
                                    pass  # 如果解析失败，使用原始URL
                                self.on_log_message("ERROR", t("log.proxy_test_failed_detail", proxy=failed_proxy, error=result['error']))
                
                self.after(0, update_ui)
                
            except ImportError:
                def on_error():
                    self.proxy_test_btn.configure(
                        state="normal",
                        text=t("proxy_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("proxy_test_requires_requests"))
                
                self.after(0, on_error)
            except Exception as e:
                def on_error():
                    self.proxy_test_btn.configure(
                        state="normal",
                        text=t("proxy_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("proxy_test_failed", error=str(e)))
                
                self.after(0, on_error)
        
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()

