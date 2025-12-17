"""
代理配置页面
"""
import customtkinter as ctk
from typing import Callable, Optional
from ui.i18n_manager import t
from ui.fonts import title_font, heading_font, body_font
from core.logger import get_logger

logger = get_logger()


class ProxyPage(ctk.CTkFrame):
    """代理配置页面"""
    
    def __init__(
        self,
        parent,
        proxies: list = None,
        on_save_proxies: Optional[Callable[[list], None]] = None,
        on_log_message: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.proxies = proxies or []
        self.on_save_proxies = on_save_proxies
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
            text=t("proxy_label"),
            font=title_font(weight="bold")
        )
        title.pack(pady=(0, 24))
        
        # 代理配置区域
        proxy_frame = ctk.CTkFrame(scroll_frame)
        proxy_frame.pack(fill="x", pady=(0, 16))
        proxy_frame.grid_columnconfigure(0, weight=1)
        
        # 代理输入框（多行文本框）
        self.proxy_textbox = ctk.CTkTextbox(
            proxy_frame,
            height=200,
            wrap="word"
        )
        self.proxy_textbox.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 8))
        if self.proxies:
            self.proxy_textbox.insert("1.0", "\n".join(self.proxies))
        
        # 代理按钮区域
        proxy_btn_frame = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        proxy_btn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        
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
        
        # 代理帮助文本
        proxy_help = ctk.CTkLabel(
            proxy_frame,
            text=t("proxy_placeholder"),
            font=body_font(),
            text_color=("gray50", "gray50"),
            justify="left"
        )
        proxy_help.grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 16))
    
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
    
    def _on_test_proxies(self):
        """测试代理连通性"""
        import threading
        
        # 获取代理列表
        proxy_text = self.proxy_textbox.get("1.0", "end-1c").strip()
        proxies = [line.strip() for line in proxy_text.split("\n") if line.strip()]
        
        if not proxies:
            if self.on_log_message:
                self.on_log_message("WARN", t("proxy_test_no_proxy"))
            return
        
        # 禁用测试按钮
        self.proxy_test_btn.configure(state="disabled", text=t("proxy_testing"))
        
        def test_in_thread():
            """在后台线程中测试代理"""
            try:
                import requests
                from urllib.parse import urlparse
                
                # 检查是否有 SOCKS 代理，并验证依赖
                has_socks = False
                for proxy in proxies:
                    if proxy:
                        parsed = urlparse(proxy)
                        if parsed.scheme and parsed.scheme.lower() in ["socks4", "socks5", "socks5h"]:
                            has_socks = True
                            break
                
                if has_socks:
                    # 检查是否安装了 PySocks
                    try:
                        import socks
                    except ImportError:
                        def on_missing_deps():
                            self.proxy_test_btn.configure(
                                state="normal",
                                text=t("proxy_test_connection")
                            )
                            if self.on_log_message:
                                self.on_log_message("ERROR", t("proxy_test_socks_required"))
                        self.after(0, on_missing_deps)
                        return
                
                test_url = "https://www.google.com"  # 测试URL
                timeout = 10  # 超时时间（秒）
                
                results = []
                total = len(proxies)
                
                for i, proxy in enumerate(proxies, 1):
                    if not proxy:
                        continue
                    
                    try:
                        # 验证代理格式
                        parsed = urlparse(proxy)
                        if not parsed.scheme or not parsed.hostname:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": "无效的代理格式"
                            })
                            continue
                        
                        # 构建代理字典（requests格式）
                        proxies_dict = {
                            "http": proxy,
                            "https": proxy
                        }
                        
                        # 发送测试请求
                        response = requests.get(
                            test_url,
                            proxies=proxies_dict,
                            timeout=timeout,
                            allow_redirects=True
                        )
                        
                        if response.status_code == 200:
                            results.append({
                                "proxy": proxy,
                                "success": True,
                                "error": None
                            })
                        else:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": f"HTTP {response.status_code}"
                            })
                    
                    except requests.exceptions.ProxyError as e:
                        error_msg = str(e)
                        # 检查是否是 SOCKS 依赖缺失的错误
                        if "Missing dependencies for SOCKS" in error_msg or "SOCKS support" in error_msg:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": t("proxy_test_socks_required_short")
                            })
                        elif "Max retries exceeded" in error_msg or "Connection refused" in error_msg:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": "代理服务器无响应或拒绝连接"
                            })
                        else:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": f"代理错误: {error_msg[:80]}"
                            })
                    except requests.exceptions.Timeout:
                        results.append({
                            "proxy": proxy,
                            "success": False,
                            "error": "连接超时（代理可能较慢或不可用）"
                        })
                    except requests.exceptions.ConnectionError as e:
                        error_msg = str(e)
                        # 分析连接错误类型
                        if "Max retries exceeded" in error_msg:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": "连接失败：代理服务器无响应（可能已失效或网络不通）"
                            })
                        elif "Connection refused" in error_msg:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": "连接失败：代理服务器拒绝连接"
                            })
                        elif "SOCKS" in error_msg:
                            # SOCKS 连接错误
                            if "authentication" in error_msg.lower() or "auth" in error_msg.lower():
                                results.append({
                                    "proxy": proxy,
                                    "success": False,
                                    "error": "连接失败：SOCKS 代理认证失败（请检查用户名和密码）"
                                })
                            else:
                                results.append({
                                    "proxy": proxy,
                                    "success": False,
                                    "error": "连接失败：SOCKS 代理连接失败（请检查代理地址和端口）"
                                })
                        else:
                            # 提取更简洁的错误信息
                            if "Caused by" in error_msg:
                                # 提取 "Caused by" 后面的部分
                                caused_by_part = error_msg.split("Caused by")[-1].strip()
                                if len(caused_by_part) > 60:
                                    caused_by_part = caused_by_part[:60] + "..."
                                results.append({
                                    "proxy": proxy,
                                    "success": False,
                                    "error": f"连接失败: {caused_by_part}"
                                })
                            else:
                                results.append({
                                    "proxy": proxy,
                                    "success": False,
                                    "error": f"连接失败: {error_msg[:80]}"
                                })
                    except Exception as e:
                        error_msg = str(e)
                        # 检查是否是 SOCKS 依赖缺失的错误
                        if "Missing dependencies for SOCKS" in error_msg or "SOCKS support" in error_msg:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": t("proxy_test_socks_required_short")
                            })
                        elif "Max retries exceeded" in error_msg:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": "连接失败：代理服务器无响应"
                            })
                        else:
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": f"未知错误: {error_msg[:80]}"
                            })
                
                # 统计结果
                success_count = sum(1 for r in results if r["success"])
                failed_count = len(results) - success_count
                
                # 更新UI
                def update_ui():
                    self.proxy_test_btn.configure(
                        state="normal",
                        text=t("proxy_test_connection")
                    )
                    
                    if self.on_log_message:
                        if success_count > 0:
                            self.on_log_message("INFO", t("proxy_test_success_count", success=success_count, total=total))
                        if failed_count > 0:
                            self.on_log_message("WARN", t("proxy_test_failed_count", failed=failed_count, total=total))
                        
                        # 显示每个代理的测试结果
                        for result in results:
                            if result["success"]:
                                self.on_log_message("INFO", t("proxy_test_proxy_success", proxy=result["proxy"]))
                            else:
                                self.on_log_message("ERROR", t("proxy_test_proxy_failed", proxy=result["proxy"], error=result["error"]))
                
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

