"""
页面管理模块
负责页面切换逻辑
"""

import customtkinter as ctk
from typing import TYPE_CHECKING

from core.i18n import t
from ui.fonts import heading_font
from ui.pages.url_list_page import UrlListPage
from ui.pages.run_params_page import RunParamsPage
from ui.pages.appearance_page import AppearancePage
from ui.pages.system_page import SystemPage
from ui.pages.network_settings import NetworkSettingsPage
from ui.pages.translation_summary_page import TranslationSummaryPage
from core.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


from ui.themes import apply_theme_to_window, _apply_custom_colors


class PageManagerMixin:
    """页面管理 Mixin

    提供页面切换相关的方法
    """

    def _switch_page(self, page_name: str):
        """切换页面"""
        # 在销毁页面之前，保存当前页面的输入内容
        if hasattr(self, "current_page") and self.current_page is not None:
            try:
                if isinstance(self.current_page, UrlListPage):
                    # 保存URL列表（即使为空或占位符也要保存，以便区分）
                    try:
                        url_text = self.current_page.url_list_textbox.get(
                            "1.0", "end-1c"
                        ).strip()
                        # 检查是否是占位符文本（通过检查第一行是否包含占位符特征）
                        first_line = url_text.split('\n')[0].strip() if url_text else ""
                        is_zh_placeholder = "支持输入" in first_line or "视频链接" in first_line
                        is_en_placeholder = "Supports:" in first_line or "Video URL" in first_line
                        
                        # 如果文本是占位符，保存空字符串；否则保存实际内容
                        if is_zh_placeholder or is_en_placeholder or not url_text:
                            self.state_manager.set("url_list_text", "")
                        else:
                            self.state_manager.set("url_list_text", url_text)
                    except (AttributeError, Exception):
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
        if page_name == "url_list":
            # 恢复保存的URL列表
            saved_url_list_text = self.state_manager.get("url_list_text", "")
            # 调试日志（可移除）
            if saved_url_list_text:
                logger = get_logger()
                logger.debug_i18n("url_list_restored", length=len(saved_url_list_text))
            page = UrlListPage(
                self.page_container,
                on_check_new=self._on_check_new_urls,
                on_start_processing=self._on_start_processing_urls,
                on_cancel_processing=self._on_cancel_task,
                on_resume_processing=self._on_resume_processing_urls,  # 恢复任务回调
                stats=self.state_manager.get(
                    "stats", {"total": 0, "success": 0, "failed": 0, "current": 0}
                ),
                running_status=self.state_manager.get(
                    "running_status", t("status_idle")
                ),
                language_config=self.app_config.language.to_dict()
                if self.app_config.language
                else {},
                on_save_language_config=self._on_save_language_config,
                translation_ai_config=self.app_config.translation_ai.to_dict(),
                summary_ai_config=self.app_config.summary_ai.to_dict(),
                on_save_translation_ai=self._on_save_translation_ai,
                on_save_summary_ai=self._on_save_summary_ai,
                initial_url_list_text=saved_url_list_text,
                initial_force_rerun=self.app_config.force_rerun,
                on_save_force_rerun=self._on_save_force_rerun,
            )
            page.pack(fill="both", expand=True)
            self.current_page = page

            # 应用主题颜色到新页面
            if hasattr(self, "theme_tokens") and self.theme_tokens:
                _apply_custom_colors(self.current_page, self.theme_tokens)


            self.toolbar.update_title(t("start_task"))
            self.state_manager.set("current_mode", t("start_task"))
            # 立即更新按钮状态，确保正确渲染
            self.after(10, lambda: self._update_processing_buttons(self.is_processing))
            # 强制重新配置取消按钮的颜色，确保对比度正确
            self.after(50, self._fix_cancel_button_contrast)
            # 检测可恢复任务并更新恢复按钮状态
            self.after(100, self._check_resumable_tasks)

        elif page_name == "run_params":
            page = RunParamsPage(
                self.page_container,
                concurrency=self.app_config.concurrency,
                ai_concurrency=self.app_config.ai_concurrency,
                retry_count=self.app_config.retry_count,
                output_dir=self.app_config.output_dir,
                on_save=self._on_save_run_params,
            )
            page.pack(fill="both", expand=True)
            self.current_page = page

            # 应用主题颜色到新页面
            if hasattr(self, "theme_tokens") and self.theme_tokens:
                _apply_custom_colors(self.current_page, self.theme_tokens)

            self.toolbar.update_title(t("run_params"))
            self.state_manager.set("current_mode", t("run_params"))

        elif page_name == "appearance":
            page = AppearancePage(self.page_container)
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("appearance_lang"))

        elif page_name == "network_settings":
            page = NetworkSettingsPage(
                self.page_container,
                cookie=self.app_config.cookie,
                proxies=self.app_config.proxies,
                network_region=self.app_config.network_region,
                on_save_cookie=self._on_save_cookie,
                on_save_proxies=self._on_save_proxies,
                on_log_message=self._on_log,
                on_update_cookie_status=self._update_cookie_status,
            )
            page.pack(fill="both", expand=True)
            self.current_page = page

            # 应用主题颜色到新页面
            if hasattr(self, "theme_tokens") and self.theme_tokens:
                _apply_custom_colors(self.current_page, self.theme_tokens)

            self.toolbar.update_title(t("network_settings_group"))

        elif page_name == "translation_summary":
            page = TranslationSummaryPage(
                self.page_container,
                translation_ai_config=self.app_config.translation_ai.to_dict(),
                summary_ai_config=self.app_config.summary_ai.to_dict(),
                on_save_translation_ai=self._on_save_translation_ai,
                on_save_summary_ai=self._on_save_summary_ai,
                on_log_message=self._on_log,
            )
            page.pack(fill="both", expand=True)
            self.current_page = page

            # 应用主题颜色到新页面
            if hasattr(self, "theme_tokens") and self.theme_tokens:
                _apply_custom_colors(self.current_page, self.theme_tokens)

            self.toolbar.update_title(t("translation_summary_group"))

        elif page_name == "system":
            page = SystemPage(self.page_container, on_log=self._on_log)
            page.pack(fill="both", expand=True)
            self.current_page = page
            self.toolbar.update_title(t("system_tools"))

        else:
            # 占位页面
            placeholder = ctk.CTkLabel(
                self.page_container,
                text=t("page_not_implemented", page=page_name),
                font=heading_font(),
            )
            placeholder.pack(expand=True)
