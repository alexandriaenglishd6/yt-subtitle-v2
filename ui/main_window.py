"""
主窗口 & 控件布局（重构版）
实现四区结构：顶部工具栏 + 左侧侧边栏 + 中间主区 + 底部日志框
使用组件化架构，main_window 仅负责布局和事件接线
"""
import customtkinter as ctk
from typing import Optional
from pathlib import Path
import subprocess
import platform

from core.logger import Logger, get_logger
from ui.themes import ThemeTokens, get_theme, ThemeName, apply_theme_to_window
from ui.i18n_manager import t, set_language, get_language
from ui.app_events import get_event_bus, EventType
from ui.state import get_state_manager
from ui.components.toolbar import Toolbar
from ui.components.sidebar import Sidebar
from ui.components.log_panel import LogPanel
from ui.fonts import heading_font
from ui.pages.channel_page import ChannelPage
from ui.pages.url_list_page import UrlListPage
from ui.pages.run_params_page import RunParamsPage
from ui.pages.appearance_page import AppearancePage
from ui.pages.network_ai_page import NetworkAIPage
from ui.pages.system_page import SystemPage
from ui.pages.network_settings_page import NetworkSettingsPage
from ui.pages.translation_summary_page import TranslationSummaryPage
from ui.business_logic import VideoProcessor
from config.manager import get_user_data_dir, ConfigManager


class MainWindow(ctk.CTk):
    """主窗口类（重构版）
    
    实现四区布局，使用组件化架构：
    - 顶部工具栏：应用标题、运行状态、功能按钮
    - 左侧侧边栏：导航菜单（任务、运行设置、外观 & 系统）
    - 中间主区：根据导航显示不同页面
    - 底部日志框：实时显示日志
    """
    
    def __init__(self):
        super().__init__()
        
        # 窗口基本设置（先设置默认标题，i18n 初始化后会更新）
        self.title("YouTube 字幕工具 v2")
        self.geometry("1600x1000")
        self.minsize(1000, 700)
        
        # 初始化配置管理器
        self.config_manager = ConfigManager()
        self.app_config = self.config_manager.load()
        
        # 初始化 i18n（从配置读取语言设置）
        self._init_i18n()
        
        # 更新窗口标题（i18n 初始化后）
        self.title(t("app_name"))
        
        # 确保语言设置正确应用（可选：记录日志，但此时 logger 还未初始化）
        # current_lang = get_language()
        # get_logger().info(f"当前语言: {current_lang}")  # 如果需要调试，可以取消注释
        
        # 当前主题（从配置加载或使用默认值）
        self.current_theme: ThemeName = self._load_theme_from_config()
        self.theme_tokens: ThemeTokens = get_theme(self.current_theme)
        
        # 初始化事件总线和状态管理器
        self.event_bus = get_event_bus()
        self.state_manager = get_state_manager()  # 重命名避免与 window.state() 冲突
        
        # 初始化 Logger（用于 GUI 日志输出）
        self.logger = Logger(name="gui", console_output=False, file_output=True)
        self.logger.add_callback(self._on_log_message)
        
        # 同时为全局 logger 注册回调，确保所有通过 get_logger() 的日志都能显示在 GUI 中
        global_logger = get_logger()
        global_logger.add_callback(self._on_log_message)
        
        # 初始化业务逻辑处理器
        self.video_processor = VideoProcessor(self.config_manager, self.app_config)
        
        # 当前页面
        self.current_page: Optional[ctk.CTkFrame] = None
        self.current_page_name = "channel"
        
        # 处理状态
        self.is_processing = False
        
        # 构建 UI
        self._build_ui()
        
        # 订阅事件
        self._subscribe_events()
        
        # 应用主题
        apply_theme_to_window(self, self.theme_tokens, self.current_theme)
        
        # 初始化状态
        self.state_manager.set("current_page", "channel")
        self.state_manager.set("current_theme", self.current_theme)
        self.state_manager.set("current_language", get_language())
        
        # 初始化 Cookie 状态显示
        self._update_cookie_status()
    
    def _init_i18n(self):
        """初始化 i18n，从配置读取语言设置"""
        try:
            if hasattr(self.app_config, 'ui_language') and self.app_config.ui_language:
                set_language(self.app_config.ui_language)
            else:
                set_language("zh-CN")
        except Exception:
            set_language("zh-CN")
    
    def _load_theme_from_config(self) -> ThemeName:
        """从配置加载主题设置"""
        try:
            if hasattr(self.app_config, 'theme') and self.app_config.theme:
                theme_name = self.app_config.theme
                if theme_name in ["light", "light_gray", "dark_gray", "claude_warm"]:
                    return theme_name
        except Exception:
            pass
        return "light"
    
    def _build_ui(self):
        """构建 UI 布局"""
        # 配置网格权重，使布局可伸缩
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # 1. 顶部工具栏
        self.toolbar = Toolbar(
            self,
            current_mode=t("channel_mode"),
            running_status=t("status_idle"),
            current_theme=self.current_theme,
            on_language_changed=self._on_language_changed,
            on_theme_changed=self._on_theme_changed,
            on_open_output=self._on_open_output_folder,
            on_open_config=self._on_open_failed_links
        )
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        # 2. 左侧侧边栏
        self.sidebar = Sidebar(
            self,
            on_page_changed=self._switch_page
        )
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        
        # 3. 中间主内容区
        self.main_content = ctk.CTkFrame(self)
        self.main_content.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(0, weight=1)
        
        # 页面容器
        self.page_container = ctk.CTkFrame(self.main_content)
        self.page_container.pack(fill="both", expand=True)
        
        # 4. 底部日志框
        self.log_panel = LogPanel(self, height=300)  # 200 * 1.5 = 300（增加 50%）
        self.log_panel.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        # 5. 默认显示频道页面
        self._switch_page("channel")
    
    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.STATUS_CHANGED, self._on_status_changed)
        self.event_bus.subscribe(EventType.STATS_UPDATED, self._on_stats_updated)
    
    def _switch_page(self, page_name: str):
        """切换页面"""
        # 在销毁页面之前，保存当前页面的输入内容
        if hasattr(self, 'current_page') and self.current_page is not None:
            try:
                if isinstance(self.current_page, ChannelPage):
                    # 保存频道URL（即使为空也要保存，以便区分空值和未设置）
                    try:
                        channel_url = self.current_page.channel_url_entry.get().strip()
                        self.state_manager.set("channel_url", channel_url)
                    except (AttributeError, Exception) as e:
                        # 如果获取失败，忽略（可能是控件已被销毁）
                        pass
                elif isinstance(self.current_page, UrlListPage):
                    # 保存URL列表（即使为空或占位符也要保存，以便区分）
                    try:
                        url_text = self.current_page.url_list_textbox.get("1.0", "end-1c").strip()
                        placeholder = t("url_list_placeholder")
                        # 如果文本是占位符，保存空字符串；否则保存实际内容
                        if url_text == placeholder:
                            self.state_manager.set("url_list_text", "")
                        else:
                            self.state_manager.set("url_list_text", url_text)
                    except (AttributeError, Exception) as e:
                        # 如果获取失败，忽略（可能是控件已被销毁）
                        pass
            except Exception as e:
                # 捕获所有异常，确保不会影响页面切换
                get_logger().debug(f"保存页面内容时出错: {e}")
        
        # 清除当前页面
        for widget in self.page_container.winfo_children():
            widget.destroy()
        
        self.current_page_name = page_name
        
        # 创建并显示目标页面
        if page_name == "channel":
            # 恢复保存的频道URL
            saved_channel_url = self.state_manager.get("channel_url", "")
            # 调试日志（可移除）
            if saved_channel_url:
                get_logger().debug(f"恢复频道URL: {saved_channel_url[:50]}...")
            page = ChannelPage(
                self.page_container,
                on_check_new=self._on_check_new_videos,
                on_start_processing=self._on_start_processing,
                on_cancel_processing=self._on_cancel_task,
                stats=self.state_manager.get("stats", {"total": 0, "success": 0, "failed": 0, "current": 0}),
                running_status=self.state_manager.get("running_status", t("status_idle")),
                language_config=self.app_config.language.to_dict() if self.app_config.language else {},
                on_save_language_config=self._on_save_language_config,
                translation_ai_config=self.app_config.translation_ai.to_dict(),
                summary_ai_config=self.app_config.summary_ai.to_dict(),
                on_save_translation_ai=self._on_save_translation_ai,
                on_save_summary_ai=self._on_save_summary_ai,
                initial_channel_url=saved_channel_url
            )
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("channel_mode"))
            self.state_manager.set("current_mode", t("channel_mode"))
            # 立即更新按钮状态，确保正确渲染
            self.after(10, lambda: self._update_processing_buttons(self.is_processing))
            # 强制重新配置取消按钮的颜色，确保对比度正确
            self.after(50, self._fix_cancel_button_contrast)
            
        elif page_name == "url_list":
            # 恢复保存的URL列表
            saved_url_list_text = self.state_manager.get("url_list_text", "")
            # 调试日志（可移除）
            if saved_url_list_text:
                get_logger().debug(f"恢复URL列表文本，长度: {len(saved_url_list_text)}")
            page = UrlListPage(
                self.page_container,
                on_check_new=self._on_check_new_urls,
                on_start_processing=self._on_start_processing_urls,
                on_cancel_processing=self._on_cancel_task,
                stats=self.state_manager.get("stats", {"total": 0, "success": 0, "failed": 0, "current": 0}),
                running_status=self.state_manager.get("running_status", t("status_idle")),
                language_config=self.app_config.language.to_dict() if self.app_config.language else {},
                on_save_language_config=self._on_save_language_config,
                translation_ai_config=self.app_config.translation_ai.to_dict(),
                summary_ai_config=self.app_config.summary_ai.to_dict(),
                on_save_translation_ai=self._on_save_translation_ai,
                on_save_summary_ai=self._on_save_summary_ai,
                initial_url_list_text=saved_url_list_text
            )
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("url_list_mode"))
            self.state_manager.set("current_mode", t("url_list_mode"))
            # 立即更新按钮状态，确保正确渲染
            self.after(10, lambda: self._update_processing_buttons(self.is_processing))
            # 强制重新配置取消按钮的颜色，确保对比度正确
            self.after(50, self._fix_cancel_button_contrast)
            
        elif page_name == "run_params":
            page = RunParamsPage(
                self.page_container,
                concurrency=self.app_config.concurrency,
                retry_count=self.app_config.retry_count,
                output_dir=self.app_config.output_dir,
                on_save=self._on_save_run_params
            )
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("run_params"))
            self.state_manager.set("current_mode", t("run_params"))
            
        elif page_name == "appearance":
            page = AppearancePage(self.page_container)
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("appearance_lang"))
            
        elif page_name == "network_ai":
            page = NetworkAIPage(
                self.page_container,
                cookie=self.app_config.cookie,
                proxies=self.app_config.proxies,
                translation_ai_config=self.app_config.translation_ai.to_dict(),
                summary_ai_config=self.app_config.summary_ai.to_dict(),
                on_save_cookie=self._on_save_cookie,
                on_save_proxies=self._on_save_proxies,
                on_save_ai_config=self._on_save_ai_config,
                on_log_message=self._on_log
            )
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("network_ai"))
            
        elif page_name == "network_settings":
            page = NetworkSettingsPage(
                self.page_container,
                cookie=self.app_config.cookie,
                proxies=self.app_config.proxies,
                network_region=self.app_config.network_region,
                on_save_cookie=self._on_save_cookie,
                on_save_proxies=self._on_save_proxies,
                on_log_message=self._on_log,
                on_update_cookie_status=self._update_cookie_status
            )
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("network_settings_group"))
            
        elif page_name == "translation_summary":
            page = TranslationSummaryPage(
                self.page_container,
                translation_ai_config=self.app_config.translation_ai.to_dict(),
                summary_ai_config=self.app_config.summary_ai.to_dict(),
                on_save_translation_ai=self._on_save_translation_ai,
                on_save_summary_ai=self._on_save_summary_ai,
                on_log_message=self._on_log
            )
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("translation_summary_group"))
            
        elif page_name == "system":
            page = SystemPage(
                self.page_container,
                on_log=self._on_log
            )
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("system_tools"))
            
        else:
            # 占位页面
            placeholder = ctk.CTkLabel(
                self.page_container,
                text=t("page_not_implemented", page=page_name),
                font=heading_font()
            )
            placeholder.pack(expand=True)
    
    def _create_safe_callbacks(self):
        """创建线程安全的回调函数集
        
        Returns:
            tuple: (safe_on_log, safe_on_status, safe_on_stats, safe_on_complete)
        """
        def safe_on_log(level: str, message: str, video_id: Optional[str] = None):
            """线程安全的日志回调"""
            self.after(0, lambda: self._on_log(level, message, video_id))
        
        def safe_on_status(status: str):
            """线程安全的状态更新回调"""
            self.after(0, lambda: self._on_status(status))
            # 同时更新日志面板的统计信息（包含状态）
            if hasattr(self, 'log_panel') and hasattr(self.log_panel, 'update_stats'):
                current_stats = self.state_manager.get("stats", {"total": 0, "success": 0, "failed": 0})
                self.after(0, lambda: self.log_panel.update_stats(current_stats, status))
        
        def safe_on_stats(stats: dict):
            """线程安全的统计信息更新回调"""
            self.after(0, lambda: self._on_stats(stats))
        
        def safe_on_complete():
            """线程安全的完成回调"""
            self.after(0, lambda: setattr(self, 'is_processing', False))
            # 恢复按钮状态（显示开始按钮，隐藏取消按钮）
            self.after(0, self._restore_processing_buttons)
        
        return safe_on_log, safe_on_status, safe_on_stats, safe_on_complete
    
    def _check_can_start_task(self, input_text: str) -> bool:
        """检查是否可以启动任务
        
        Args:
            input_text: 输入的 URL 或 URL 列表文本
        
        Returns:
            是否可以启动任务
        """
        if not input_text or not input_text.strip():
            # 根据当前页面类型显示不同的提示
            if self.current_page_name == "url_list":
                self.log_panel.append_log("WARN", t("url_list_empty"))
            else:
                self.log_panel.append_log("WARN", t("enter_channel_url"))
            return False
        
        if self.is_processing:
            self.log_panel.append_log("WARN", t("processing_in_progress"))
            return False
        
        return True
    
    def _on_check_new_videos(self, url: str, force: bool = False):
        """检查新视频按钮点击（Dry Run）"""
        if not self._check_can_start_task(url):
            return
        
        self.is_processing = True
        safe_on_log, safe_on_status, _, safe_on_complete = self._create_safe_callbacks()
        
        self.video_processor.dry_run(
            url=url,
            on_log=safe_on_log,
            on_status=safe_on_status,
            on_complete=safe_on_complete,
            force=force
        )
    
    def _on_start_processing(self, url: str, force: bool = False):
        """开始处理按钮点击（频道模式）"""
        if not self._check_can_start_task(url):
            return
        
        self.is_processing = True
        # 更新按钮状态（显示取消按钮，隐藏开始按钮）
        self._update_processing_buttons(True)
        
        safe_on_log, safe_on_status, safe_on_stats, safe_on_complete = self._create_safe_callbacks()
        
        # 添加初始日志
        self.log_panel.append_log("INFO", t("processing_start", url=url))
        if force:
            self.log_panel.append_log("INFO", t("force_rerun_enabled"))
        
        # 启动处理任务
        thread = self.video_processor.process_videos(
            url=url,
            on_log=safe_on_log,
            on_status=safe_on_status,
            on_stats=safe_on_stats,
            on_complete=safe_on_complete,
            force=force
        )
        
        # 确认线程已启动
        if not (thread and thread.is_alive()):
            self.log_panel.append_log("ERROR", t("processing_failed", error="线程启动失败"))
            self.is_processing = False
            self._restore_processing_buttons()
    
    def _on_check_new_urls(self, urls_text: str, force: bool = False):
        """检查新视频按钮点击（URL 列表模式）"""
        if not urls_text or not urls_text.strip():
            self.log_panel.append_log("WARN", t("url_list_empty"))
            return
        
        if not self._check_can_start_task(urls_text):
            return
        
        self.is_processing = True
        safe_on_log, safe_on_status, _, safe_on_complete = self._create_safe_callbacks()
        
        self.video_processor.dry_run_url_list(
            urls_text=urls_text,
            on_log=safe_on_log,
            on_status=safe_on_status,
            on_complete=safe_on_complete,
            force=force
        )
    
    def _on_start_processing_urls(self, urls_text: str, force: bool = False):
        """开始处理按钮点击（URL 列表模式）"""
        if not urls_text or not urls_text.strip():
            self.log_panel.append_log("WARN", t("url_list_empty"))
            return
        
        if not self._check_can_start_task(urls_text):
            return
        
        self.is_processing = True
        # 更新按钮状态（显示取消按钮，隐藏开始按钮）
        self._update_processing_buttons(True)
        
        safe_on_log, safe_on_status, safe_on_stats, safe_on_complete = self._create_safe_callbacks()
        
        # 添加初始日志
        self.log_panel.append_log("INFO", t("processing_start_url_list"))
        if force:
            self.log_panel.append_log("INFO", t("force_rerun_enabled"))
        
        # 启动处理任务
        thread = self.video_processor.process_url_list(
            urls_text=urls_text,
            on_log=safe_on_log,
            on_status=safe_on_status,
            on_stats=safe_on_stats,
            on_complete=safe_on_complete,
            force=force
        )
        
        # 确认线程已启动
        if not (thread and thread.is_alive()):
            self.log_panel.append_log("ERROR", t("processing_failed", error="线程启动失败"))
            self.is_processing = False
            self._restore_processing_buttons()
    
    def _on_cancel_task(self):
        """取消任务按钮点击"""
        if not self.is_processing:
            return
        
        # 调用 VideoProcessor 的停止方法
        self.video_processor.stop_processing()
        self.log_panel.append_log("INFO", t("task_cancelling"))
    
    def _update_processing_buttons(self, is_processing: bool):
        """更新处理按钮状态
        
        Args:
            is_processing: 是否正在处理
        """
        if hasattr(self, 'current_page') and self.current_page:
            if hasattr(self.current_page, 'set_processing_state'):
                self.current_page.set_processing_state(is_processing)
    
    def _restore_processing_buttons(self):
        """恢复处理按钮状态（显示开始按钮，隐藏取消按钮）"""
        self._update_processing_buttons(False)
    
    def _fix_cancel_button_contrast(self):
        """修复取消按钮的对比度问题"""
        if hasattr(self, 'current_page') and self.current_page:
            if hasattr(self.current_page, 'cancel_processing_btn'):
                btn = self.current_page.cancel_processing_btn
                try:
                    current_state = btn.cget("state")
                    # 根据当前状态重新配置颜色
                    if current_state == "disabled":
                        btn.configure(
                            fg_color=("#4A9EFF", "#4A9EFF"),  # 禁用状态下使用淡蓝色背景
                            text_color=("white", "white")  # 使用白色文字，确保高对比度
                        )
                    btn.update_idletasks()
                except Exception:
                    pass
    
    def _save_config(
        self,
        update_fn,
        success_msg: str,
        error_msg_prefix: str,
        reinit_processor: bool = False
    ):
        """通用配置保存方法
        
        Args:
            update_fn: 更新配置的函数，接收 app_config 并修改
            success_msg: 成功时的日志消息
            error_msg_prefix: 失败时的日志消息前缀
            reinit_processor: 是否需要重新初始化 video_processor
        """
        try:
            update_fn(self.app_config)
            self.config_manager.save(self.app_config)
            if reinit_processor:
                self.video_processor = VideoProcessor(self.config_manager, self.app_config)
            self.log_panel.append_log("INFO", success_msg)
        except Exception as e:
            logger = get_logger()
            logger.error(f"{error_msg_prefix}: {e}")
            self.log_panel.append_log("ERROR", f"{error_msg_prefix}: {e}")
    
    def _on_save_cookie(self, cookie: str, region: Optional[str] = None):
        """保存 Cookie
        
        Args:
            cookie: Cookie 字符串
            region: 地区代码（可选，如果提供则同时保存地区信息）
        """
        def update_config(cfg):
            cfg.cookie = cookie
            if region is not None:
                cfg.network_region = region
        
        self._save_config(
            update_fn=update_config,
            success_msg=t("cookie_save_success"),
            error_msg_prefix=t("cookie_save_failed", error="").rstrip(": "),
            reinit_processor=True
        )
        
        # 更新 Cookie 状态显示
        self._update_cookie_status(cookie, region)
    
    def _update_cookie_status(self, cookie: Optional[str] = None, region: Optional[str] = None, test_result: Optional[str] = None):
        """更新 Cookie 状态显示
        
        Args:
            cookie: Cookie 字符串（可选，如果为 None 则从配置读取）
            region: 地区代码（可选）
            test_result: 测试结果（可选，"success" 或 "failed"）
        """
        if cookie is None:
            cookie = self.app_config.cookie
        if region is None:
            region = self.app_config.network_region
        
        if cookie:
            if test_result == "failed":
                cookie_status = t("cookie_status_test_failed")
            elif test_result == "success":
                if region:
                    cookie_status = t("cookie_status_test_success_with_region", region=region)
                else:
                    cookie_status = t("cookie_status_test_success")
            else:
                # 未测试，只显示配置状态
                if region:
                    cookie_status = t("cookie_status_configured_with_region", region=region)
                else:
                    cookie_status = t("cookie_status_configured")
        else:
            cookie_status = t("cookie_status_not_configured")
        
        if hasattr(self, 'log_panel') and hasattr(self.log_panel, 'update_cookie_status'):
            self.log_panel.update_cookie_status(cookie_status)
    
    def _on_save_proxies(self, proxies: list):
        """保存代理列表"""
        self._save_config(
            update_fn=lambda cfg: setattr(cfg, 'proxies', proxies),
            success_msg=t("proxy_save_success"),
            error_msg_prefix=t("proxy_save_failed", error="").rstrip(": "),
            reinit_processor=True
        )
    
    def _on_save_translation_ai(self, translation_ai_config: dict):
        """保存翻译 AI 配置"""
        from config.manager import AIConfig
        def update_config(cfg):
            cfg.translation_ai = AIConfig.from_dict(translation_ai_config)
        self._save_config(
            update_fn=update_config,
            success_msg=t("ai_save_success"),
            error_msg_prefix=t("ai_save_failed", error="").rstrip(": "),
            reinit_processor=True
        )
    
    def _on_save_summary_ai(self, summary_ai_config: dict):
        """保存摘要 AI 配置"""
        from config.manager import AIConfig
        def update_config(cfg):
            cfg.summary_ai = AIConfig.from_dict(summary_ai_config)
        self._save_config(
            update_fn=update_config,
            success_msg=t("ai_save_success"),
            error_msg_prefix=t("ai_save_failed", error="").rstrip(": "),
            reinit_processor=True
        )
    
    def _on_save_ai_config(self, translation_ai_config: dict, summary_ai_config: dict):
        """保存 AI 配置（翻译和摘要）"""
        from config.manager import AIConfig
        self._save_config(
            update_fn=lambda cfg: (
                setattr(cfg, 'translation_ai', AIConfig.from_dict(translation_ai_config)),
                setattr(cfg, 'summary_ai', AIConfig.from_dict(summary_ai_config))
            ),
            success_msg=t("ai_save_success"),
            error_msg_prefix=t("ai_save_failed", error="").rstrip(": "),
            reinit_processor=True
        )
    
    def _on_save_output_dir(self, output_dir: str):
        """保存输出目录"""
        self._save_config(
            update_fn=lambda cfg: setattr(cfg, 'output_dir', output_dir),
            success_msg=t("output_dir_save_success"),
            error_msg_prefix=t("output_dir_save_failed", error="").rstrip(": "),
            reinit_processor=False
        )
    
    def _on_save_language_config(self, language_config: dict):
        """保存语言配置"""
        from core.language import LanguageConfig
        
        def update_language(cfg):
            current_ui_language = cfg.language.ui_language if cfg.language else "zh-CN"
            merged_config = {"ui_language": current_ui_language, **language_config}
            cfg.language = LanguageConfig.from_dict(merged_config)
        
        self._save_config(
            update_fn=update_language,
            success_msg=t("language_config_save_success"),
            error_msg_prefix=t("language_config_save_failed", error="").rstrip(": "),
            reinit_processor=True
        )
    
    def _on_save_run_params(self, concurrency: int, retry_count: int, output_dir: str):
        """保存运行参数
        
        Args:
            concurrency: 并发数
            retry_count: 重试次数
            output_dir: 输出目录
        """
        def update_config(cfg):
            cfg.concurrency = concurrency
            cfg.retry_count = retry_count
            cfg.output_dir = output_dir
        
        self._save_config(
            update_fn=update_config,
            success_msg=t("run_params_updated", concurrency=concurrency, retry_count=retry_count),
            error_msg_prefix=t("save_params_failed", error="").rstrip(": "),
            reinit_processor=True  # 重试次数和输出目录变化需要重新初始化处理器
        )
    
    def _on_language_changed(self, value: str):
        """语言切换回调"""
        # 直接比较显示文本，因为翻译文件中 language_zh 和 language_en 的值是固定的
        # zh_CN.json: "language_zh": "中文", "language_en": "English"
        # en_US.json: "language_zh": "中文", "language_en": "English"
        logger = get_logger()
        logger.info_i18n("language_change_callback", value=value)
        
        if value == "中文":
            new_lang = "zh-CN"
        elif value == "English":
            new_lang = "en-US"
        else:
            logger.warning_i18n("language_unknown", value=value)
            return
        
        current_lang = get_language()
        logger.info_i18n("language_current_new", current=current_lang, new=new_lang)
        
        if current_lang == new_lang:
            logger.info_i18n("language_no_change")
            return
        
        set_language(new_lang)
        logger.info_i18n("language_set", lang=new_lang, test=t('app_name'))
        
        # 保存到配置
        try:
            if hasattr(self.app_config, 'ui_language'):
                self.app_config.ui_language = new_lang
                self.config_manager.save(self.app_config)
                logger.info_i18n("language_saved")
        except Exception as e:
            logger.error(f"保存语言设置失败: {e}")
        
        # 刷新 UI 文本
        self._refresh_ui_texts()
        self.state_manager.set("current_language", new_lang)
        self.event_bus.publish(EventType.LANGUAGE_CHANGED, new_lang)
        logger.info_i18n("ui_text_refreshed")
    
    def _on_theme_changed(self, value: str):
        """主题切换回调"""
        # 直接通过翻译文本反向查找主题名
        # 需要同时支持中英文翻译
        theme_map = {}
        for theme_key in ["light", "light_gray", "dark_gray", "claude_warm"]:
            # 获取当前语言下的主题显示名称
            theme_display = t(f"theme_{theme_key}")
            theme_map[theme_display] = theme_key
            # 也支持英文翻译（以防万一）
            from ui.i18n_manager import load_translations
            en_translations = load_translations("en-US")
            if en_translations:
                en_display = en_translations.get(f"theme_{theme_key}", "")
                if en_display:
                    theme_map[en_display] = theme_key
        
        theme_name = theme_map.get(value, "light")
        
        # 调试日志
        logger = get_logger()
        logger.info_i18n("theme_changed", value=value, theme_name=theme_name, current_theme=self.current_theme)
        
        if theme_name != self.current_theme:
            self.current_theme = theme_name
            self.theme_tokens = get_theme(theme_name)
            
            # 同步更新 toolbar 的 current_theme，并刷新下拉框显示
            # 这会在下拉框中显示正确的主题名称
            self.toolbar.update_theme(theme_name)
            
            # 保存到配置
            try:
                if hasattr(self.app_config, 'theme'):
                    self.app_config.theme = theme_name
                    self.config_manager.save(self.app_config)
                    logger.info_i18n("theme_saved", theme_name=theme_name)
            except Exception as e:
                logger.error_i18n("theme_save_failed", error=str(e))
            
            # 应用主题
            apply_theme_to_window(self, self.theme_tokens, self.current_theme)
            
            # 强制刷新所有组件（确保主题立即生效）
            self.update_idletasks()
            self.update()
            
            self.state_manager.set("current_theme", theme_name)
            self.event_bus.publish(EventType.THEME_CHANGED, theme_name)
    
    def _refresh_ui_texts(self):
        """刷新 UI 中的所有文本（语言切换后调用）"""
        # 更新窗口标题（set_language 已经加载了翻译）
        self.title(t("app_name"))
        
        # 刷新组件文本
        self.toolbar.refresh_language()
        self.sidebar.refresh_language()
        self.log_panel.refresh_language()
        
        # 刷新状态显示（确保使用翻译键）
        current_status = self.state_manager.get("running_status", "status_idle")
        # 如果状态不是翻译键，尝试转换
        if not current_status.startswith("status_"):
            from ui.i18n_manager import get_language, load_translations
            current_lang = get_language()
            translations = load_translations(current_lang)
            status_key = None
            for key, value in translations.items():
                if key.startswith("status_") and value == current_status:
                    status_key = key
                    break
            if status_key:
                current_status = status_key
            else:
                current_status = "status_idle"
        # 不再更新工具栏状态（已删除）
        # 更新日志面板的统计信息
        if hasattr(self, 'log_panel') and hasattr(self.log_panel, 'update_stats'):
            current_stats = self.state_manager.get("stats", {"total": 0, "success": 0, "failed": 0})
            self.log_panel.update_stats(current_stats, current_status)
        
        # 重新构建当前页面（确保所有文本都更新）
        if self.current_page_name:
            # 保存当前页面的状态（如果有）
            saved_stats = None
            saved_status = None
            if isinstance(self.current_page, (ChannelPage, UrlListPage)):
                saved_stats = self.current_page.stats
                saved_status = self.current_page.running_status
            
            # 重新切换页面（会重新构建，使用新语言）
            self._switch_page(self.current_page_name)
            
        # 恢复状态（使用翻译键）
        if isinstance(self.current_page, (ChannelPage, UrlListPage)) and saved_stats:
            self.current_page.update_stats(saved_stats, current_status)
        # 更新日志面板的统计信息
        if hasattr(self, 'log_panel') and hasattr(self.log_panel, 'update_stats'):
            current_stats = self.state_manager.get("stats", {"total": 0, "success": 0, "failed": 0})
            self.log_panel.update_stats(current_stats, current_status)
        else:
            # 如果无法重新构建，至少刷新现有页面
            if self.current_page and hasattr(self.current_page, 'refresh_language'):
                self.current_page.refresh_language()
        
        # 重新应用主题（确保颜色正确）
        apply_theme_to_window(self, self.theme_tokens, self.current_theme)
        self.toolbar.refresh_theme_combo()
    
    def _on_open_output_folder(self):
        """打开输出文件夹"""
        output_dir = Path(self.app_config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(f'explorer "{output_dir.absolute()}"')
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", str(output_dir.absolute())])
        else:  # Linux
            subprocess.Popen(["xdg-open", str(output_dir.absolute())])
        
        from ui.i18n_manager import t
        self.log_panel.append_log("INFO", t("output_folder_opened", path=str(output_dir.absolute())))
    
    def _on_open_failed_links(self):
        """打开失败链接文件"""
        from pathlib import Path
        
        # 获取输出目录
        output_dir = Path(self.app_config.output_dir)
        failed_urls_file = output_dir / "failed_urls.txt"
        
        # 如果文件不存在，创建空文件
        if not failed_urls_file.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            failed_urls_file.touch()
            self.log_panel.append_log("INFO", f"失败链接文件不存在，已创建：{failed_urls_file.absolute()}")
        
        # 打开文件
        system = platform.system()
        try:
            if system == "Windows":
                # Windows: 使用 notepad 打开
                subprocess.Popen(['notepad', str(failed_urls_file.absolute())])
            elif system == "Darwin":  # macOS
                subprocess.Popen(["open", "-t", str(failed_urls_file.absolute())])
            else:  # Linux
                # Linux: 尝试使用默认文本编辑器
                subprocess.Popen(["xdg-open", str(failed_urls_file.absolute())])
            
            self.log_panel.append_log("INFO", f"已打开失败链接文件：{failed_urls_file.absolute()}")
        except Exception as e:
            self.log_panel.append_log("ERROR", f"打开失败链接文件失败：{e}")
    
    def _on_log_message(self, level: str, message: str, video_id: Optional[str] = None):
        """日志回调函数（从 Logger 接收日志）"""
        self.after(0, lambda: self._on_log(level, message, video_id))
    
    def _on_log(self, level: str, message: str, video_id: Optional[str] = None):
        """处理日志消息"""
        self.log_panel.append_log(level, message, video_id)
    
    def _on_status(self, status: str):
        """处理状态更新"""
        # 确保 status 是翻译键，如果不是则尝试转换
        if not status.startswith("status_"):
            # 尝试反向查找翻译键
            from ui.i18n_manager import get_language, load_translations
            current_lang = get_language()
            translations = load_translations(current_lang)
            # 查找匹配的翻译值
            status_key = None
            for key, value in translations.items():
                if key.startswith("status_") and value == status:
                    status_key = key
                    break
            if status_key:
                status = status_key
            else:
                # 如果找不到，使用默认的 status_idle
                status = "status_idle"
        
        # 不再更新工具栏状态（已删除）
        self.state_manager.set("running_status", status)
        # 更新日志面板的统计信息（包含状态）
        if hasattr(self, 'log_panel') and hasattr(self.log_panel, 'update_stats'):
            current_stats = self.state_manager.get("stats", {"total": 0, "success": 0, "failed": 0})
            self.log_panel.update_stats(current_stats, status)
        self.event_bus.publish(EventType.STATUS_CHANGED, status)
    
    def _on_stats(self, stats: dict):
        """处理统计信息更新"""
        self.state_manager.set("stats", stats)
        if isinstance(self.current_page, (ChannelPage, UrlListPage)):
            self.current_page.update_stats(stats, self.state_manager.get("running_status", ""))
        # 更新日志面板的统计信息
        if hasattr(self, 'log_panel') and hasattr(self.log_panel, 'update_stats'):
            self.log_panel.update_stats(stats, self.state_manager.get("running_status", ""))
        self.event_bus.publish(EventType.STATS_UPDATED, stats)
    
    def _on_status_changed(self, status: str):
        """状态变化事件处理"""
        # 不再更新工具栏状态（已删除）
        # 更新日志面板的统计信息（包含状态）
        if hasattr(self, 'log_panel') and hasattr(self.log_panel, 'update_stats'):
            current_stats = self.state_manager.get("stats", {"total": 0, "success": 0, "failed": 0})
            self.log_panel.update_stats(current_stats, status)
    
    def _on_stats_updated(self, stats: dict):
        """统计信息更新事件处理"""
        if isinstance(self.current_page, (ChannelPage, UrlListPage)):
            self.current_page.update_stats(stats, self.state_manager.get("running_status", ""))
        # 更新日志面板的统计信息
        if hasattr(self, 'log_panel') and hasattr(self.log_panel, 'update_stats'):
            self.log_panel.update_stats(stats, self.state_manager.get("running_status", ""))
