"""
网络设置页面
包含 Cookie 和代理配置
"""
import customtkinter as ctk
from typing import Callable, Optional
import threading
from ui.i18n_manager import t
from core.cookie_manager import CookieManager
from ui.fonts import title_font, heading_font, body_font
from core.logger import get_logger

logger = get_logger()


class NetworkSettingsPage(ctk.CTkFrame):
    """网络设置页面"""
    
    def __init__(
        self,
        parent,
        cookie: str = "",
        proxies: list = None,
        on_save_cookie: Optional[Callable[[str], None]] = None,
        on_save_proxies: Optional[Callable[[list], None]] = None,
        on_log_message: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.cookie = cookie
        self.proxies = proxies or []
        self.on_save_cookie = on_save_cookie
        self.on_save_proxies = on_save_proxies
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
            text=t("network_settings_group"),
            font=title_font(weight="bold")
        )
        title.pack(pady=(0, 24))
        
        # Cookie 配置区域
        cookie_frame = ctk.CTkFrame(scroll_frame)
        cookie_frame.pack(fill="x", pady=(0, 24))
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
        
        # 移除 Cookie 帮助文本（已移到输入框内作为占位符）
        
        # 代理配置区域
        proxy_frame = ctk.CTkFrame(scroll_frame)
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
        
        # 移除代理帮助文本（已移到输入框内作为占位符）
    
    def _on_paste_cookie(self):
        """从剪贴板粘贴 Cookie"""
        try:
            import tkinter as tk
            root = self.winfo_toplevel()
            cookie_text = root.clipboard_get()
            self.cookie_textbox.delete("1.0", "end")
            self.cookie_textbox.insert("1.0", cookie_text)
            self.cookie_is_placeholder = False
            if self.on_log_message:
                self.on_log_message("INFO", "已从剪贴板粘贴 Cookie")
        except Exception as e:
            logger.error(f"粘贴 Cookie 失败: {e}")
            if self.on_log_message:
                self.on_log_message("ERROR", f"粘贴 Cookie 失败: {e}")
    
    def _on_clear_cookie(self):
        """清空 Cookie"""
        self.cookie_textbox.delete("1.0", "end")
        self._show_cookie_placeholder()
        if self.on_log_message:
            self.on_log_message("INFO", "已清空 Cookie")
    
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
        if hasattr(self, 'cookie_is_placeholder') and self.cookie_is_placeholder:
            self.cookie_textbox.delete("1.0", "end")
            self.cookie_is_placeholder = False
    
    def _on_cookie_focus_out(self, event):
        """Cookie 输入框失去焦点"""
        content = self.cookie_textbox.get("1.0", "end-1c").strip()
        if not content:
            self._show_cookie_placeholder()
    
    def _on_cookie_key_press(self, event):
        """Cookie 输入框按键事件"""
        if hasattr(self, 'cookie_is_placeholder') and self.cookie_is_placeholder:
            self.cookie_textbox.delete("1.0", "end")
            self.cookie_is_placeholder = False
    
    def _on_test_cookie(self):
        """测试 Cookie"""
        cookie_text = self.cookie_textbox.get("1.0", "end-1c").strip()
        
        # 如果是占位符文本，则视为空
        if hasattr(self, 'cookie_is_placeholder') and self.cookie_is_placeholder:
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
        
        # 如果是占位符文本，则不保存
        if hasattr(self, 'cookie_is_placeholder') and self.cookie_is_placeholder:
            cookie_text = ""
        
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
        self._show_proxy_placeholder()
        if self.on_log_message:
            self.on_log_message("INFO", "已清空代理列表")
    
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
                logger.error(f"保存代理设置失败: {e}")
                if self.on_log_message:
                    self.on_log_message("ERROR", t("proxy_save_failed", error=str(e)))
        else:
            logger.warning("on_save_proxies 回调未设置")
    
    def _on_test_proxies(self):
        """测试代理连通性"""
        import threading
        
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
            self.on_log_message("INFO", f"开始测试 {len(proxies)} 个代理...")
        
        def test_in_thread():
            """在后台线程中测试代理"""
            try:
                import requests
                from urllib.parse import urlparse
                import subprocess
                import shutil
                
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
                
                # 使用多个测试URL，提高成功率
                test_urls = [
                    "https://www.google.com",
                    "https://www.baidu.com",
                    "https://httpbin.org/ip",
                    "https://api.ipify.org?format=json"
                ]
                timeout = 15  # 超时时间（秒）- 增加到15秒
                
                results = []
                total = len(proxies)
                
                def log_info(msg):
                    """在GUI线程中记录日志"""
                    if self.on_log_message:
                        def log():
                            self.on_log_message("INFO", msg)
                        self.after(0, log)
                
                def log_error(msg):
                    """在GUI线程中记录错误"""
                    if self.on_log_message:
                        def log():
                            self.on_log_message("ERROR", msg)
                        self.after(0, log)
                
                def log_debug(msg):
                    """在GUI线程中记录调试信息"""
                    if self.on_log_message:
                        def log():
                            self.on_log_message("DEBUG", msg)
                        self.after(0, log)
                
                for i, proxy in enumerate(proxies, 1):
                    if not proxy:
                        continue
                    
                    # 隐藏密码的代理URL（用于日志显示）
                    if parsed.username or parsed.password:
                        safe_proxy = f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}"
                    else:
                        safe_proxy = proxy
                    log_info(f"测试代理 {i}/{total}: {safe_proxy}")
                    
                    try:
                        # 验证代理格式
                        parsed = urlparse(proxy)
                        if not parsed.scheme or not parsed.hostname:
                            error_msg = "无效的代理格式"
                            log_error(f"代理 {i} 格式无效: {proxy}")
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": error_msg
                            })
                            continue
                        
                        # 记录代理类型和认证信息
                        proxy_type = parsed.scheme.upper()
                        has_auth = parsed.username is not None or parsed.password is not None
                        auth_info = ""
                        if has_auth:
                            # 只显示用户名，不显示密码（隐私保护）
                            auth_info = f", 用户名: {parsed.username or '(无)'}, 密码: {'已设置' if parsed.password else '未设置'}"
                        log_info(f"代理类型: {proxy_type}, 地址: {parsed.hostname}:{parsed.port or '默认'}{auth_info}")
                        
                        # 验证代理URL格式（包含认证信息）
                        if has_auth:
                            log_debug(f"代理包含认证信息: 用户名={parsed.username}, 密码={'已设置' if parsed.password else '未设置'}")
                            # 验证URL解析是否正确
                            if parsed.username and not parsed.password:
                                log_error(f"警告: 代理包含用户名但缺少密码，可能导致认证失败")
                        
                        # 对于SOCKS5代理，需要特殊处理认证信息
                        # requests库理论上支持从URL中提取认证信息，但在某些情况下可能不工作
                        # 这里直接使用完整的代理URL，让requests库尝试自动处理
                        test_proxy_url = proxy
                        
                        # 对于SOCKS代理，验证URL格式是否正确
                        if parsed.scheme.lower() in ["socks4", "socks5", "socks5h"]:
                            if has_auth:
                                log_debug(f"使用带认证的SOCKS代理: {parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}")
                                # 验证URL是否包含完整的认证信息
                                if not parsed.username or not parsed.password:
                                    log_error(f"警告: SOCKS代理认证信息不完整（用户名: {'有' if parsed.username else '无'}, 密码: {'有' if parsed.password else '无'}）")
                            else:
                                log_debug(f"使用无认证的SOCKS代理: {parsed.scheme}://{parsed.hostname}:{parsed.port}")
                            
                            # 验证代理URL是否包含 '@' 符号（表示有认证信息）
                            if has_auth and '@' not in test_proxy_url:
                                log_error(f"错误: 代理URL格式异常，应该包含认证信息但未找到 '@' 符号")
                        
                        # 使用 yt-dlp 测试代理（与实际使用场景一致）
                        # yt-dlp 能够正确处理包含认证信息的 SOCKS5 代理
                        # 这样测试结果更能反映实际使用情况
                        log_debug(f"使用 yt-dlp 测试代理（与实际使用场景一致）")
                        
                        # 查找 yt-dlp 可执行文件
                        yt_dlp_path = shutil.which("yt-dlp")
                        if not yt_dlp_path:
                            yt_dlp_path = shutil.which("yt-dlp.exe")
                        
                        if not yt_dlp_path:
                            # 如果没有找到 yt-dlp，回退到使用 requests 的方式
                            log_debug(f"未找到 yt-dlp，回退到使用 requests 测试")
                            proxies_dict = {
                                "http": test_proxy_url,
                                "https": test_proxy_url
                            }
                            test_success = False
                            last_error = None
                            last_exception = None
                            
                            for url_idx, test_url in enumerate(test_urls, 1):
                                try:
                                    log_debug(f"  尝试测试URL {url_idx}/{len(test_urls)}: {test_url}")
                                    response = requests.get(
                                        test_url,
                                        proxies=proxies_dict,
                                        timeout=timeout,
                                        allow_redirects=True
                                    )
                                    if response.status_code in [200, 301, 302, 303, 307, 308]:
                                        safe_proxy = f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}" if (parsed.username or parsed.password) else proxy
                                        log_info(f"代理 {i} 测试成功: {safe_proxy} (通过 {test_url}, 状态码: {response.status_code})")
                                        test_success = True
                                        last_error = None
                                        break
                                    else:
                                        last_error = f"HTTP {response.status_code}"
                                except Exception as e:
                                    last_error = str(e)
                                    last_exception = e
                                    log_debug(f"  URL {test_url} 错误: {str(e)[:100]}")
                        else:
                            # 使用 yt-dlp 测试代理
                            # 使用一个简单的公开视频来测试代理是否可用
                            test_video_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # 公开的测试视频
                            
                            try:
                                log_debug(f"  使用 yt-dlp 测试代理连接...")
                                
                                # 构建 yt-dlp 命令
                                cmd = [
                                    yt_dlp_path,
                                    "--proxy", test_proxy_url,
                                    "--dump-json",
                                    "--no-warnings",
                                    "--quiet",
                                    "--no-playlist",
                                    test_video_url
                                ]
                                
                                # 执行命令（设置较短的超时时间）
                                result = subprocess.run(
                                    cmd,
                                    capture_output=True,
                                    text=True,
                                    timeout=timeout,
                                    encoding="utf-8",
                                    errors="ignore"
                                )
                                
                                # 提取错误输出
                                error_output = result.stderr if result.stderr else result.stdout
                                error_lines = [line for line in error_output.split("\n") if line.strip() and not line.startswith("WARNING:")]
                                error_msg = "\n".join(error_lines[:3])[:200] if error_lines else ""
                                error_lower = error_msg.lower()
                                
                                if result.returncode == 0:
                                    # 成功获取视频信息，代理可用
                                    safe_proxy = f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}" if (parsed.username or parsed.password) else proxy
                                    log_info(f"代理 {i} 测试成功: {safe_proxy} (通过 yt-dlp 测试)")
                                    test_success = True
                                    last_error = None
                                    last_exception = None
                                elif any(keyword in error_lower for keyword in [
                                    "sign in to confirm", "you're not a bot", 
                                    "cookies", "authentication", "cookie"
                                ]):
                                    # 代理连接成功，但需要 Cookie 认证（这说明代理是工作的）
                                    safe_proxy = f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}" if (parsed.username or parsed.password) else proxy
                                    log_info(f"代理 {i} 测试成功: {safe_proxy} (代理连接正常，但测试视频需要 Cookie 认证)")
                                    log_debug(f"  注意: {error_msg[:150]}")
                                    test_success = True
                                    last_error = None
                                    last_exception = None
                                elif any(keyword in error_lower for keyword in [
                                    "unable to connect", "connection refused", "connection timeout",
                                    "network is unreachable", "name resolution failed", "failed to resolve",
                                    "proxy", "socks"
                                ]):
                                    # 真正的连接错误
                                    last_error = error_msg if error_msg else f"yt-dlp 返回错误码 {result.returncode}"
                                    last_exception = None
                                    log_debug(f"  yt-dlp 测试失败（连接错误）: {last_error}")
                                    test_success = False
                                else:
                                    # 其他错误（可能是视频不存在、需要 Cookie 等，但不一定是代理问题）
                                    # 如果错误信息中包含 "ERROR:"，说明至少连接到了服务器
                                    if "ERROR:" in error_output and "youtube" in error_lower:
                                        # 能够连接到 YouTube 服务器，说明代理是工作的
                                        safe_proxy = f"{parsed.scheme}://{parsed.username or ''}:***@{parsed.hostname}:{parsed.port or ''}" if (parsed.username or parsed.password) else proxy
                                        log_info(f"代理 {i} 测试成功: {safe_proxy} (代理连接正常，可访问 YouTube)")
                                        log_debug(f"  详细信息: {error_msg[:150]}")
                                        test_success = True
                                        last_error = None
                                        last_exception = None
                                    else:
                                        last_error = error_msg if error_msg else f"yt-dlp 返回错误码 {result.returncode}"
                                        last_exception = None
                                        log_debug(f"  yt-dlp 测试失败: {last_error}")
                                        test_success = False
                            except subprocess.TimeoutExpired:
                                last_error = f"连接超时（超过 {timeout} 秒）"
                                last_exception = None
                                test_success = False
                                log_debug(f"  yt-dlp 测试超时")
                            except Exception as e:
                                last_error = str(e)[:200]
                                last_exception = e
                                test_success = False
                                log_debug(f"  yt-dlp 测试异常: {last_error}")
                        
                        if test_success:
                            results.append({
                                "proxy": proxy,
                                "success": True,
                                "error": None
                            })
                        else:
                            # 如果所有URL都失败，需要根据最后一个异常类型给出更详细的错误信息
                            if last_exception and isinstance(last_exception, Exception):
                                # 重新抛出异常，让外层的异常处理逻辑处理
                                raise last_exception
                            elif last_error:
                                # 根据错误信息模拟抛出相应的异常
                                error_lower = last_error.lower()
                                if "max retries exceeded" in error_lower or "connection refused" in error_lower:
                                    raise requests.exceptions.ConnectionError(last_error)
                                elif "timeout" in error_lower or "timed out" in error_lower:
                                    raise requests.exceptions.Timeout(last_error)
                                elif "socks" in error_lower or "missing dependencies" in error_lower:
                                    raise requests.exceptions.ProxyError(last_error)
                                else:
                                    raise requests.exceptions.ConnectionError(last_error)
                            else:
                                results.append({
                                    "proxy": proxy,
                                    "success": False,
                                    "error": "所有测试URL均失败"
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
                        log_error(f"代理 {i} 连接错误: {error_msg[:200]}")
                        
                        # 分析连接错误类型
                        if "Max retries exceeded" in error_msg:
                            error_detail = "连接失败：代理服务器无响应（可能已失效或网络不通）"
                            # 如果是SOCKS代理，提供更详细的提示
                            if parsed.scheme.lower() in ["socks4", "socks5", "socks5h"]:
                                error_detail += "（SOCKS代理：请检查代理地址、端口、用户名和密码是否正确，以及防火墙设置）"
                            results.append({
                                "proxy": proxy,
                                "success": False,
                                "error": error_detail
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
                        # 显示测试总结
                        if success_count > 0:
                            self.on_log_message("INFO", f"测试完成: {success_count}/{total} 个代理可用")
                        if failed_count > 0:
                            self.on_log_message("WARN", f"测试完成: {failed_count}/{total} 个代理失败")
                        
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
                                self.on_log_message("ERROR", f"代理测试失败: {failed_proxy} - {result['error']}")
                
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

