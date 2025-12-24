"""
任务处理模块
负责视频处理任务的回调和处理逻辑
"""

from typing import Optional, TYPE_CHECKING

from core.i18n import t
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

        # 检查双语模式 + 翻译未启用的冲突
        if self._check_bilingual_translation_conflict():
            return False

        return True

    def _check_bilingual_translation_conflict(self) -> bool:
        """检查双语模式和翻译配置是否冲突
        
        Returns:
            True 表示有冲突，False 表示无冲突
        """
        try:
            # 获取语言配置
            language_config = None
            if hasattr(self, 'language_panel') and self.language_panel:
                language_config = self.language_panel.get_config()
            elif hasattr(self, 'app_config') and self.app_config:
                language_config = self.app_config.language.to_dict()
            
            if not language_config:
                return False
            
            bilingual_mode = language_config.get("bilingual_mode", "none")
            
            # 获取翻译启用状态
            translation_enabled = True
            if hasattr(self, 'app_config') and self.app_config:
                translation_enabled = self.app_config.translation_ai.enabled
            
            if bilingual_mode == "source+target" and not translation_enabled:
                self.log_panel.append_log("ERROR", t("bilingual_translation_conflict"))
                return True
        except Exception as e:
            # 调试日志
            import traceback
            self.log_panel.append_log("DEBUG", f"Bilingual check error: {e}")
        
        return False

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
        safe_on_log, safe_on_status, safe_on_stats, safe_on_complete = self._create_safe_callbacks()

        self.video_processor.dry_run_url_list(
            urls_text=urls_text,
            on_log=safe_on_log,
            on_status=safe_on_status,
            on_complete=safe_on_complete,
            force=force,
            on_stats=safe_on_stats,
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
        """取消任务按钮点击（P0-2 优化）
        
        点击后立即：
        1. 禁用取消按钮，防止重复点击
        2. 更新按钮文本为"正在停止"
        3. 更新状态栏
        4. 调用 stop_processing 触发取消
        """
        if not self.is_processing:
            return

        # P0-2: 立即禁用取消按钮，显示"正在停止"
        if hasattr(self, "current_page") and self.current_page:
            if hasattr(self.current_page, "set_stopping_state"):
                self.current_page.set_stopping_state()

        # 更新状态栏显示"正在停止"
        if hasattr(self, "log_panel") and hasattr(self.log_panel, "update_stats"):
            current_stats = self.state_manager.get(
                "stats", {"total": 0, "success": 0, "failed": 0}
            )
            self.log_panel.update_stats(current_stats, t("status_stopping"))

        # 调用 VideoProcessor 的停止方法
        self.video_processor.stop_processing()
        self.log_panel.append_log("INFO", t("task_cancelling"))

    def _on_resume_processing_urls(self):
        """恢复任务按钮点击（URL 列表模式）
        
        读取最近的 BatchManifest，获取未完成的视频并继续处理
        P1-3: 恢复前清理残留 .tmp 文件
        """
        from pathlib import Path
        from core.state.manifest import ManifestManager, VideoStage
        from core.utils.cleanup import cleanup_video_tmp_files
        
        try:
            # 获取 manifest 目录
            output_dir = Path(self.app_config.output_dir or "out")
            manifest_dir = output_dir / ".state"
            
            if not manifest_dir.exists():
                self.log_panel.append_log("WARN", "没有可恢复的任务（.state 目录不存在）")
                return
            
            # P1-3: 清理残留 .tmp 文件
            cleaned_count = cleanup_video_tmp_files(output_dir)
            if cleaned_count > 0:
                self.log_panel.append_log(
                    "INFO", 
                    t("log.cleanup_tmp_files", count=cleaned_count, directory=str(output_dir))
                )
            
            # 初始化 ManifestManager 并获取最近的批次
            manifest_manager = ManifestManager(manifest_dir)
            batch_ids = manifest_manager.list_batches()
            
            if not batch_ids:
                self.log_panel.append_log("WARN", "没有可恢复的任务")
                return
            
            # 获取最近的批次（按时间排序）
            latest_batch_id = sorted(batch_ids, reverse=True)[0]
            batch_manifest = manifest_manager.load_batch(latest_batch_id)
            
            if not batch_manifest:
                self.log_panel.append_log("ERROR", f"无法加载批次: {latest_batch_id}")
                return
            
            # 获取可恢复的视频
            resumable_videos = batch_manifest.get_resumable_videos()
            
            if not resumable_videos:
                self.log_panel.append_log("INFO", t("all_videos_completed"))
                return
            
            # 构建 URL 列表
            urls = [v.url for v in resumable_videos]
            urls_text = "\n".join(urls)
            
            self.log_panel.append_log(
                "INFO", 
                t("resume_task_found", count=len(resumable_videos), batch_id=latest_batch_id)
            )
            
            # 回填 URL 到输入框，让用户确认后再处理
            if hasattr(self, "current_page") and hasattr(self.current_page, "set_url_text"):
                self.current_page.set_url_text(urls_text)
                self.log_panel.append_log(
                    "INFO", 
                    t("resume_urls_loaded", count=len(resumable_videos))
                )
            else:
                # 回退：如果无法回填，则直接开始处理
                self._on_start_processing_urls(urls_text, force=False)
            
        except Exception as e:
            self.log_panel.append_log("ERROR", t("resume_task_failed", error=str(e)))
            import traceback
            traceback.print_exc()

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

    def _check_resumable_tasks(self):
        """检测可恢复任务并更新恢复按钮状态"""
        from pathlib import Path
        from ui.pages.url_list_page import UrlListPage
        
        try:
            # 只在 UrlListPage 页面检测
            if not isinstance(self.current_page, UrlListPage):
                return
            
            # 获取 manifest 目录
            output_dir = Path(self.app_config.output_dir or "out")
            manifest_dir = output_dir / ".state"
            
            if not manifest_dir.exists():
                self.current_page.set_resumable_state(False, 0)
                return
            
            # 初始化 ManifestManager 并获取最近的批次
            from core.state.manifest import ManifestManager
            manifest_manager = ManifestManager(manifest_dir)
            batch_ids = manifest_manager.list_batches()
            
            if not batch_ids:
                self.current_page.set_resumable_state(False, 0)
                return
            
            # 获取最近的批次
            latest_batch_id = sorted(batch_ids, reverse=True)[0]
            batch_manifest = manifest_manager.load_batch(latest_batch_id)
            
            if not batch_manifest:
                self.current_page.set_resumable_state(False, 0)
                return
            
            # 获取可恢复的视频数量
            resumable_videos = batch_manifest.get_resumable_videos()
            resumable_count = len(resumable_videos)
            
            # 更新按钮状态
            self.current_page.set_resumable_state(resumable_count > 0, resumable_count)
            
        except Exception as e:
            # 出错时禁用按钮
            if hasattr(self, "current_page") and self.current_page:
                if hasattr(self.current_page, "set_resumable_state"):
                    self.current_page.set_resumable_state(False, 0)
