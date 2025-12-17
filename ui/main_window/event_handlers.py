"""
事件处理模块
负责配置保存、语言/主题切换、日志/状态处理等事件
"""
from typing import Optional, TYPE_CHECKING
from pathlib import Path
import subprocess
import platform

from ui.i18n_manager import t, set_language, get_language, load_translations
from ui.themes import get_theme, apply_theme_to_window
from ui.app_events import EventType
from ui.pages.channel_page import ChannelPage
from ui.pages.url_list_page import UrlListPage
from core.logger import get_logger
from ui.business_logic import VideoProcessor

if TYPE_CHECKING:
    from .window import MainWindow

logger = get_logger()


class EventHandlersMixin:
    """事件处理 Mixin
    
    提供配置保存、语言/主题切换、日志/状态处理等方法
    """
    
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
            self.log_panel.update_cookie_status(cookie_status, cookie=cookie, region=region, test_result=test_result)
    
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
    
    def _on_save_force_rerun(self, force_rerun: bool):
        """保存强制重跑选项
        
        Args:
            force_rerun: 是否强制重跑
        """
        def update_config(cfg):
            cfg.force_rerun = force_rerun
        
        self._save_config(
            update_fn=update_config,
            success_msg="",  # 静默保存，不显示消息
            error_msg_prefix="",
            reinit_processor=False
        )
    
    def _on_language_changed(self, value: str):
        """语言切换回调"""
        # 直接比较显示文本，因为翻译文件中 language_zh 和 language_en 的值是固定的
        # zh_CN.json: "language_zh": "中文", "language_en": "English"
        # en_US.json: "language_zh": "中文", "language_en": "English"
        logger = get_logger()
        
        if value == "中文":
            new_lang = "zh-CN"
        elif value == "English":
            new_lang = "en-US"
        else:
            logger.warning_i18n("language_unknown", value=value)
            return
        
        current_lang = get_language()
        
        if current_lang == new_lang:
            logger.info_i18n("language_no_change")
            return
        
        # 先切换语言，这样后续的日志都会使用新语言
        set_language(new_lang)
        
        # 现在使用新语言记录日志
        logger.info_i18n("language_change_callback", value=value)
        logger.info_i18n("language_current_new", current=current_lang, new=new_lang)
        logger.info_i18n("language_set", lang=new_lang, test=t('app_name'))
        
        # 保存到配置
        try:
            if hasattr(self.app_config, 'ui_language'):
                self.app_config.ui_language = new_lang
                self.config_manager.save(self.app_config)
                logger.info_i18n("language_saved")
        except Exception as e:
            logger.error_i18n("language_save_failed", error=str(e))
        
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
        
        # 重新更新 Cookie 状态（确保使用新语言）
        self._update_cookie_status()
        
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
        
        self.log_panel.append_log("INFO", t("output_folder_opened", path=str(output_dir.absolute())))
    
    def _on_open_failed_links(self):
        """打开失败链接文件"""
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

