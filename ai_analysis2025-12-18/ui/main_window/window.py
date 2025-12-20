"""
主窗口 & 控件布局（重构版）
实现四区结构：顶部工具栏 + 左侧侧边栏 + 中间主区 + 底部日志框
使用组件化架构，main_window 仅负责布局和事件接线
"""

import customtkinter as ctk
from typing import Optional

from core.logger import Logger, get_logger
from ui.themes import ThemeTokens, get_theme, ThemeName, apply_theme_to_window
from ui.i18n_manager import t, set_language, get_language
from ui.app_events import get_event_bus, EventType
from ui.state import get_state_manager
from ui.components.toolbar import Toolbar
from ui.components.sidebar import Sidebar
from ui.components.log_panel import LogPanel
from ui.business_logic import VideoProcessor
from config.manager import ConfigManager

# 导入 mixin 模块
from .page_manager import PageManagerMixin
from .task_handlers import TaskHandlersMixin
from .event_handlers import EventHandlersMixin


class MainWindow(PageManagerMixin, TaskHandlersMixin, EventHandlersMixin, ctk.CTk):
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
        self.title(t("app_name"))
        self.geometry("1600x1000")
        self.minsize(1000, 700)
        
        # 初始化配置管理器
        self.config_manager = ConfigManager()
        self.app_config = self.config_manager.load()
        
        # 初始化 i18n（从配置读取语言设置）
        self._init_i18n()
        
        # 更新窗口标题（i18n 初始化后）
        self.title(t("app_name"))
        
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
        self.video_processor = VideoProcessor(
            self.config_manager, self.app_config, event_bus=self.event_bus, quiet=True
        )
        
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
            if hasattr(self.app_config, "ui_language") and self.app_config.ui_language:
                set_language(self.app_config.ui_language)
            else:
                set_language("zh-CN")
        except Exception:
            set_language("zh-CN")
    
    def _load_theme_from_config(self) -> ThemeName:
        """从配置加载主题设置"""
        try:
            if hasattr(self.app_config, "theme") and self.app_config.theme:
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
            on_open_config=self._on_open_failed_links,
        )
        self.toolbar._is_secondary = True  # 标记为次要区域（背景稍深）
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")

        # 2. 左侧侧边栏
        self.sidebar = Sidebar(self, on_page_changed=self._switch_page)
        self.sidebar._is_secondary = True  # 标记为次要区域
        self.sidebar.grid(row=1, column=0, sticky="nsew")

        # 3. 中间主内容区
        self.main_content = ctk.CTkFrame(self)
        self.main_content._is_primary = True  # 标记为主内容区（背景最浅）
        self.main_content.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(0, weight=1)

        # 页面容器
        self.page_container = ctk.CTkFrame(self.main_content)
        self.page_container.pack(fill="both", expand=True)

        # 4. 底部日志框
        self.log_panel = LogPanel(self, height=450)
        self.log_panel._is_secondary = True  # 标记为次要区域
        self.log_panel.grid(row=2, column=0, columnspan=2, sticky="ew")

        # 5. 默认显示频道页面
        self._switch_page("channel")
    
    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.STATUS_CHANGED, self._on_status_changed)
        self.event_bus.subscribe(EventType.STATS_UPDATED, self._on_stats_updated)
        self.event_bus.subscribe(
            EventType.COOKIE_STATUS_CHANGED, self._on_cookie_status_changed
        )
