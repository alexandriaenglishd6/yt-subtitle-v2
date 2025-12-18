"""
任务处理模块
负责视频处理任务的回调和处理逻辑
"""

from typing import Optional, TYPE_CHECKING

from ui.i18n_manager import t
from core.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


class TaskHandlersMixin:
    """任务处理 Mixin

    提供任务处理相关的方法
    """

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
            if hasattr(self, "log_panel") and hasattr(self.log_panel, "update_stats"):
                current_stats = self.state_manager.get(
                    "stats", {"total": 0, "success": 0, "failed": 0}
                )
                self.after(
                    0, lambda: self.log_panel.update_stats(current_stats, status)
                )

        def safe_on_stats(stats: dict):
            """线程安全的统计信息更新回调"""
            self.after(0, lambda: self._on_stats(stats))

        def safe_on_complete():
            """线程安全的完成回调"""
            self.after(0, lambda: setattr(self, "is_processing", False))
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
            force=force,
        )

    def _on_start_processing(self, url: str, force: bool = False):
        """开始处理按钮点击（频道模式）"""
        if not self._check_can_start_task(url):
            return

        self.is_processing = True
        # 更新按钮状态（显示取消按钮，隐藏开始按钮）
        self._update_processing_buttons(True)

        safe_on_log, safe_on_status, safe_on_stats, safe_on_complete = (
            self._create_safe_callbacks()
        )

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
            force=force,
        )

        # 确认线程已启动
        if not (thread and thread.is_alive()):
            self.log_panel.append_log(
                "ERROR", t("processing_failed", error=t("thread_start_failed"))
            )
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
            force=force,
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

        safe_on_log, safe_on_status, safe_on_stats, safe_on_complete = (
            self._create_safe_callbacks()
        )

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
            force=force,
        )

        # 确认线程已启动
        if not (thread and thread.is_alive()):
            self.log_panel.append_log(
                "ERROR", t("processing_failed", error=t("thread_start_failed"))
            )
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
        if hasattr(self, "current_page") and self.current_page:
            if hasattr(self.current_page, "set_processing_state"):
                self.current_page.set_processing_state(is_processing)

    def _restore_processing_buttons(self):
        """恢复处理按钮状态（显示开始按钮，隐藏取消按钮）"""
        self._update_processing_buttons(False)

    def _fix_cancel_button_contrast(self):
        """修复取消按钮的对比度问题"""
        if hasattr(self, "current_page") and self.current_page:
            if hasattr(self.current_page, "cancel_processing_btn"):
                btn = self.current_page.cancel_processing_btn
                try:
                    current_state = btn.cget("state")
                    # 根据当前状态重新配置颜色
                    if current_state == "disabled":
                        btn.configure(
                            fg_color=("#4A9EFF", "#4A9EFF"),  # 禁用状态下使用淡蓝色背景
                            text_color=("white", "white"),  # 使用白色文字，确保高对比度
                        )
                    btn.update_idletasks()
                except Exception:
                    pass
