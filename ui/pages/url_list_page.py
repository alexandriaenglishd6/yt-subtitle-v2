"""
URL 列表模式页面
包含多行 URL 输入、检测按钮、开始处理按钮
"""

import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Optional, Dict, Any
from core.i18n import t
from ui.fonts import title_font, body_font, small_font
from ui.components.language_config import LanguageConfigPanel
from core.utils.url_validation import validate_url_list


class UrlListPage(ctk.CTkFrame):
    """URL 列表模式页面"""

    def __init__(
        self,
        parent,
        on_check_new: Optional[Callable[[str, bool], None]] = None,
        on_start_processing: Optional[Callable[[str, bool], None]] = None,
        on_cancel_processing: Optional[Callable[[], None]] = None,
        on_resume_processing: Optional[Callable[[], None]] = None,  # 恢复任务回调
        stats: Optional[Dict[str, int]] = None,
        running_status: str = "",
        language_config: Optional[dict] = None,
        on_save_language_config: Optional[Callable[[dict], None]] = None,
        translation_ai_config: Optional[dict] = None,
        summary_ai_config: Optional[dict] = None,
        on_save_translation_ai: Optional[Callable[[dict], None]] = None,
        on_save_summary_ai: Optional[Callable[[dict], None]] = None,
        initial_url_list_text: str = "",
        initial_force_rerun: bool = False,
        on_save_force_rerun: Optional[Callable[[bool], None]] = None,
        **kwargs,
    ):
        # 从 kwargs 中移除自定义参数，避免传递给父类
        kwargs.pop("on_save_force_rerun", None)
        kwargs.pop("initial_force_rerun", None)
        super().__init__(parent, **kwargs)
        self.on_check_new = on_check_new
        self.on_start_processing = on_start_processing
        self.on_cancel_processing = on_cancel_processing
        self.on_resume_processing = on_resume_processing
        self.stats = stats or {"total": 0, "success": 0, "failed": 0, "current": 0}
        self.running_status = running_status
        self.language_config = language_config or {}
        self.on_save_language_config = on_save_language_config
        self.translation_ai_config = translation_ai_config or {}
        self.summary_ai_config = summary_ai_config or {}
        self.on_save_translation_ai = on_save_translation_ai
        self.on_save_summary_ai = on_save_summary_ai
        self.initial_url_list_text = initial_url_list_text or ""
        self.initial_force_rerun = initial_force_rerun
        self.on_save_force_rerun = on_save_force_rerun
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        # 创建可滚动的容器
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        # 标题（改为"开始任务"）
        self._title_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=t("start_task"),
            font=title_font(weight="bold"),
            text_color=("black", "white"),  # 强制设置为黑/白
        )
        self._title_label.pack(pady=16)

        # 提示信息已整合到输入框的占位符中
        # URL 列表多行输入框（固定高度）
        url_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        url_frame.pack(fill="x", padx=32, pady=8)
        url_frame.grid_columnconfigure(0, weight=1)

        self.url_list_textbox = ctk.CTkTextbox(
            url_frame,
            wrap="word",
            font=body_font(),
            height=150,  # 固定高度，避免占用过多空间
        )
        self.url_list_textbox.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        # 恢复保存的URL列表或使用占位符
        if self.initial_url_list_text:
            self.url_list_textbox.insert("1.0", self.initial_url_list_text)
        else:
            self.url_list_textbox.insert("1.0", t("url_list_placeholder"))

        # 错误提示标签
        self.url_error_label = ctk.CTkLabel(
            url_frame,
            text="",
            text_color="red",
            font=small_font(),
            height=20
        )
        self.url_error_label.grid(row=1, column=0, sticky="w", padx=8)

        # 绑定事件进行校验
        self.url_list_textbox.bind("<KeyRelease>", self._on_text_changed)
        # 初始校验一次
        self.after(100, self._on_text_changed)

        # 按钮区域
        button_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=32, pady=8)

        # 导入文件按钮
        self.import_file_btn = ctk.CTkButton(
            button_frame,
            text=t("import_url_file"),
            command=self._on_import_file,
            width=120,
            font=body_font(),
            fg_color="gray50",
            hover_color="gray40",
        )
        self.import_file_btn.pack(side="left", padx=8)

        # 去重按钮
        self.deduplicate_btn = ctk.CTkButton(
            button_frame,
            text=t("deduplicate_urls"),
            command=self._on_deduplicate_urls,
            width=100,
            font=body_font(),
            fg_color="gray50",
            hover_color="gray40",
        )
        self.deduplicate_btn.pack(side="left", padx=8)

        # 清空按钮
        self.clear_btn = ctk.CTkButton(
            button_frame,
            text=t("clear_url_list"),
            command=self._on_clear_urls,
            width=80,
            font=body_font(),
            fg_color="gray50",
            hover_color="gray40",
        )
        self.clear_btn.pack(side="left", padx=8)

        # 分隔
        spacer = ctk.CTkLabel(button_frame, text="", width=20)
        spacer.pack(side="left", padx=8)

        self.check_new_btn = ctk.CTkButton(
            button_frame,
            text=t("check_new_videos"),
            command=self._on_check_new,
            width=150,
            font=body_font(),
        )
        self.check_new_btn.pack(side="left", padx=8)

        self.start_processing_btn = ctk.CTkButton(
            button_frame,
            text=t("start_processing"),
            command=self._on_start_processing,
            width=150,
            font=body_font(),
        )
        self.start_processing_btn.pack(side="left", padx=8)

        # 取消任务按钮（始终显示，初始状态禁用）
        # 禁用状态：灰色文字（亮色主题用深灰，暗色主题用浅灰）；启用状态：蓝色背景 + 白色文字
        self.cancel_processing_btn = ctk.CTkButton(
            button_frame,
            text=t("cancel_processing"),
            command=self._on_cancel_processing,
            width=150,
            font=body_font(),
            fg_color=("#3B82F6", "#3B82F6"),  # 启用时蓝色背景
            hover_color=("#2563EB", "#2563EB"),  # 悬停时深蓝色
            text_color=("white", "white"),  # 启用时白色文字
            text_color_disabled=("#6B7280", "#D1D5DB"),  # 禁用时灰色文字（亮/暗主题适配）
            state="disabled",  # 初始状态禁用
        )
        self.cancel_processing_btn._preserve_colors = True  # 防止主题覆盖颜色
        self.cancel_processing_btn.pack(side="left", padx=8)

        # 恢复任务按钮（初始状态禁用，有可恢复任务时启用）
        # 禁用状态：灰色文字；启用状态：绿色背景 + 白色文字
        self.resume_processing_btn = ctk.CTkButton(
            button_frame,
            text=t("resume_processing"),
            command=self._on_resume_processing,
            width=120,
            font=body_font(),
            fg_color=("#10B981", "#10B981"),  # 启用时绿色背景
            hover_color=("#059669", "#059669"),  # 悬停时深绿色
            text_color=("white", "white"),  # 启用时白色文字
            text_color_disabled=("#6B7280", "#D1D5DB"),  # 禁用时灰色文字（亮/暗主题适配）
            state="disabled",  # 初始状态禁用
        )
        self.resume_processing_btn._preserve_colors = True  # 防止主题覆盖颜色
        self.resume_processing_btn.pack(side="left", padx=8)

        # 强制重跑选项
        self.force_rerun_checkbox = ctk.CTkCheckBox(
            button_frame,
            text=t("force_rerun_label"),
            font=body_font(),
            command=self._on_force_rerun_changed,
        )
        # 从配置中恢复状态
        if self.initial_force_rerun:
            self.force_rerun_checkbox.select()
        self.force_rerun_checkbox.pack(side="left", padx=16, pady=8)

        # 语言配置区域（使用可复用组件）
        self.language_config_panel = LanguageConfigPanel(
            self.scrollable_frame,
            language_config=self.language_config,
            translation_ai_config=self.translation_ai_config,
            summary_ai_config=self.summary_ai_config,
            on_save=self._on_language_config_save,
            on_translation_enabled_changed=self._on_translation_enabled_changed,
            on_summary_enabled_changed=self._on_summary_enabled_changed,
        )
        self.language_config_panel.pack(fill="x", padx=32, pady=16)

        # 统计信息已移至日志面板，此处不再显示

    def _on_import_file(self):
        """导入文件按钮点击"""
        file_path = filedialog.askopenfilename(
            title=t("import_url_file_title"),
            filetypes=[(t("text_files"), "*.txt"), (t("all_files"), "*.*")],
        )

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 解析文件中的 URL（支持多种格式）
                urls = self._extract_urls_from_text(content)

                if urls:
                    # 追加到现有内容
                    current_text = self.url_list_textbox.get("1.0", "end-1c").strip()
                    placeholder = t("url_list_placeholder")

                    # 如果当前是占位符文本，则清空
                    if current_text == placeholder:
                        self.url_list_textbox.delete("1.0", "end")
                        self.url_list_textbox.insert("1.0", "\n".join(urls))
                    else:
                        # 追加到现有内容
                        if current_text:
                            self.url_list_textbox.insert("end", "\n")
                        self.url_list_textbox.insert("end", "\n".join(urls))

                    from core.logger import get_logger

                    logger = get_logger()
                    logger.info(t("import_urls_success", count=len(urls)))
                else:
                    from core.logger import get_logger

                    logger = get_logger()
                    logger.warning(t("no_urls_in_file"))
            except Exception as e:
                from core.logger import get_logger

                logger = get_logger()
                logger.error(t("import_urls_failed", error=str(e)))

    def _extract_urls_from_text(self, text: str) -> list:
        """从文本中提取 YouTube URL

        支持格式：
        - 每行一个 URL
        - 混合有其他文本的行（提取其中的 URL）
        """
        import re

        urls = []

        # YouTube URL 正则
        youtube_pattern = re.compile(
            r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<>"\']+', re.IGNORECASE
        )

        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 尝试直接匹配整行
            if "youtube.com" in line or "youtu.be" in line:
                # 提取行中的 URL
                matches = youtube_pattern.findall(line)
                for url in matches:
                    # 清理 URL（去除尾部的标点等）
                    url = url.rstrip(".,;:!?")
                    if url not in urls:
                        urls.append(url)

        return urls

    def _on_clear_urls(self):
        """清空 URL 列表"""
        from core.logger import get_logger

        logger = get_logger()

        # 检查是否有内容需要清空
        text = self._get_cleaned_urls_text()
        if text:
            logger.info(t("url_list_cleared"))
        else:
            logger.info(t("url_list_already_empty"))

        self.url_list_textbox.delete("1.0", "end")
        self.url_list_textbox.insert("1.0", t("url_list_placeholder"))

    def _on_deduplicate_urls(self):
        """去重 URL 列表（基于视频 ID）"""
        text = self._get_cleaned_urls_text()
        if not text:
            return

        # 直接提取所有 URL（不过滤重复，保留所有）
        import re

        youtube_pattern = re.compile(
            r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<>"\']+', re.IGNORECASE
        )

        urls = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 尝试直接匹配整行
            if "youtube.com" in line or "youtu.be" in line:
                # 提取行中的 URL
                matches = youtube_pattern.findall(line)
                for url in matches:
                    # 清理 URL（去除尾部的标点等）
                    url = url.rstrip(".,;:!?")
                    urls.append(url)  # 不在这里去重，保留所有

        if not urls:
            return

        # 使用 VideoFetcher 提取视频 ID
        from core.fetcher import VideoFetcher

        fetcher = VideoFetcher()

        # 去重：基于视频 ID（对于视频 URL）或完整 URL（对于非视频 URL）
        seen_video_ids = set()
        seen_urls = set()
        unique_urls = []
        removed_count = 0

        for url in urls:
            # 尝试提取视频 ID
            video_id = fetcher.extract_video_id(url)

            if video_id:
                # 这是视频 URL，基于视频 ID 去重
                if video_id not in seen_video_ids:
                    seen_video_ids.add(video_id)
                    unique_urls.append(url)
                else:
                    removed_count += 1
            else:
                # 非视频 URL（频道、播放列表等），基于完整 URL 去重
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_urls.append(url)
                else:
                    removed_count += 1

        # 更新文本框并记录日志
        from core.logger import get_logger

        logger = get_logger()

        if removed_count > 0:
            # 更新文本框内容
            self.url_list_textbox.delete("1.0", "end")
            if unique_urls:
                self.url_list_textbox.insert("1.0", "\n".join(unique_urls))
            else:
                self.url_list_textbox.insert("1.0", t("url_list_placeholder"))

            # 在日志中显示去重结果
            logger.info(
                t(
                    "deduplicate_complete_message",
                    removed=removed_count,
                    remaining=len(unique_urls),
                )
            )
        else:
            # 没有重复项
            logger.info(t("no_duplicates_found"))

    def _on_check_new(self):
        """检测新视频按钮点击"""
        urls_text = self._get_cleaned_urls_text()
        force = (
            self.force_rerun_checkbox.get() == 1
            if hasattr(self, "force_rerun_checkbox")
            else False
        )
        if self.on_check_new:
            self.on_check_new(urls_text, force)

    def _on_start_processing(self):
        """开始处理按钮点击"""
        urls_text = self._get_cleaned_urls_text()
        force = (
            self.force_rerun_checkbox.get() == 1
            if hasattr(self, "force_rerun_checkbox")
            else False
        )
        if self.on_start_processing:
            self.on_start_processing(urls_text, force)

    def _on_cancel_processing(self):
        """取消处理按钮点击"""
        if self.on_cancel_processing:
            self.on_cancel_processing()

    def _on_resume_processing(self):
        """恢复处理按钮点击"""
        if self.on_resume_processing:
            self.on_resume_processing()

    def _on_text_changed(self, event=None):
        """文本内容变化时的实时校验"""
        text = self._get_cleaned_urls_text()
        if not text:
            self.url_list_textbox.configure(border_color=["#979DA2", "#565B5E"]) # 恢复默认
            self.url_error_label.configure(text="")
            return

        is_valid, error_lines = validate_url_list(text)
        if not is_valid:
            self.url_list_textbox.configure(border_color="red")
            # 格式化错误提示：第 X, Y 行格式不正确
            lines_str = ", ".join(map(str, error_lines))
            error_msg = t("log.invalid_url_lines", lines=lines_str)
            self.url_error_label.configure(text=f"⚠️ {error_msg}")
        else:
            self.url_list_textbox.configure(border_color=["#979DA2", "#565B5E"]) # 恢复默认
            self.url_error_label.configure(text="")

    def _on_translation_enabled_changed(self, enabled: bool):
        """翻译启用状态变化（由 LanguageConfigPanel 回调）"""
        if self.on_save_translation_ai:
            # 更新配置并保存
            updated_config = self.translation_ai_config.copy()
            updated_config["enabled"] = enabled
            self.on_save_translation_ai(updated_config)

    def _on_summary_enabled_changed(self, enabled: bool):
        """摘要启用状态变化（由 LanguageConfigPanel 回调）"""
        if self.on_save_summary_ai:
            # 更新配置并保存
            updated_config = self.summary_ai_config.copy()
            updated_config["enabled"] = enabled
            self.on_save_summary_ai(updated_config)

    def set_processing_state(self, is_processing: bool):
        """设置处理状态（启用/禁用相应按钮）

        Args:
            is_processing: 是否正在处理
        """
        if hasattr(self, "start_processing_btn") and hasattr(
            self, "cancel_processing_btn"
        ):
            if is_processing:
                # 处理中：禁用开始按钮，启用取消按钮
                self.start_processing_btn.configure(state="disabled")
                # 重新配置取消按钮，确保字体正确渲染
                self.cancel_processing_btn.configure(
                    state="normal",
                    font=body_font(),  # 重新设置字体
                    text=t("cancel_processing"),  # 重新设置文本
                    fg_color=("#0078D4", "#0078D4"),  # 启用状态下使用正常蓝色背景
                    hover_color=("#005A9E", "#005A9E"),  # 悬停时使用深蓝色
                    text_color=("white", "white"),  # 使用白色文字，确保高对比度
                )
                self.cancel_processing_btn.update_idletasks()  # 强制刷新
            else:
                # 空闲：启用开始按钮，禁用取消按钮
                self.start_processing_btn.configure(state="normal")
                # 重新配置取消按钮，确保字体正确渲染
                self.cancel_processing_btn.configure(
                    state="disabled",
                    font=body_font(),  # 重新设置字体
                    text=t("cancel_processing"),  # 重新设置文本
                    fg_color=("#4A9EFF", "#4A9EFF"),  # 禁用状态下使用淡蓝色背景
                    hover_color=("#6BB5FF", "#6BB5FF"),  # 悬停时使用稍亮的蓝色
                    text_color=("white", "white"),  # 使用白色文字，确保高对比度
                )
                self.cancel_processing_btn.update_idletasks()  # 强制刷新

    def set_stopping_state(self):
        """设置正在停止状态（P0-2）
        
        取消按钮点击后调用，禁用按钮并显示"正在停止"
        """
        if hasattr(self, "cancel_processing_btn"):
            self.cancel_processing_btn.configure(
                state="disabled",
                text=t("status_stopping"),
                fg_color=("#FF9800", "#FF9800"),  # 橙色表示正在停止
                text_color=("white", "white"),
            )
            self.cancel_processing_btn.update_idletasks()

    def set_resumable_state(self, has_resumable: bool, resumable_count: int = 0):
        """设置是否有可恢复任务
        
        Args:
            has_resumable: 是否有可恢复任务
            resumable_count: 可恢复的视频数量
        """
        if hasattr(self, "resume_processing_btn"):
            if has_resumable and resumable_count > 0:
                # 有可恢复任务：启用按钮，显示数量
                self.resume_processing_btn.configure(
                    state="normal",
                    text=f"{t('resume_processing')} ({resumable_count})",
                    fg_color=("#2E7D32", "#2E7D32"),  # 绿色背景
                    hover_color=("#1B5E20", "#1B5E20"),  # 深绿色悬停
                )
            else:
                # 没有可恢复任务：禁用按钮
                self.resume_processing_btn.configure(
                    state="disabled",
                    text=t("resume_processing"),
                    fg_color=("#81C784", "#81C784"),  # 淡绿色（禁用状态）
                    hover_color=("#A5D6A7", "#A5D6A7"),
                )

    def _get_cleaned_urls_text(self) -> str:
        """获取清理后的 URL 文本（排除占位符）"""
        text = self.url_list_textbox.get("1.0", "end-1c").strip()
        
        # 检查是否是占位符文本（通过检查第一行是否包含占位符特征）
        first_line = text.split('\n')[0].strip() if text else ""
        is_zh_placeholder = "支持输入" in first_line or "视频链接" in first_line
        is_en_placeholder = "Supports:" in first_line or "Video URL" in first_line
        
        if is_zh_placeholder or is_en_placeholder or not text:
            return ""
        return text

    def set_url_text(self, urls_text: str):
        """设置 URL 输入框的文本内容（用于恢复任务时回填）
        
        Args:
            urls_text: 要设置的 URL 文本（多个 URL 以换行分隔）
        """
        # 清空现有内容
        self.url_list_textbox.delete("1.0", "end")
        # 设置新文本
        self.url_list_textbox.insert("1.0", urls_text)
        # 触发校验
        self._on_text_changed()

    def update_stats(self, stats: Dict[str, Any], status: str = ""):
        """更新统计信息（已移至日志面板，此方法保留以保持兼容性）"""
        self.stats = stats
        if status:
            self.running_status = status
        # 统计信息现在显示在日志面板中，不再更新页面内的显示

    def _on_language_config_save(self, config: dict):
        """保存语言配置（由 LanguageConfigPanel 回调）"""
        try:
            if self.on_save_language_config:
                self.on_save_language_config(config)
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger()
            logger.error(t("save_language_config_failed", error=str(e)))

    def _on_force_rerun_changed(self):
        """强制重跑选项改变时的回调"""
        if hasattr(self, "on_save_force_rerun") and self.on_save_force_rerun:
            force_rerun = self.force_rerun_checkbox.get() == 1
            self.on_save_force_rerun(force_rerun)

    def refresh_language(self):
        """刷新语言相关文本"""
        # 更新标题
        if hasattr(self, "_title_label"):
            self._title_label.configure(text=t("start_task"))

        # 更新提示
        if hasattr(self, "_hint_label"):
            self._hint_label.configure(text=t("url_list_hint"))

        # 更新按钮文本
        if hasattr(self, "import_file_btn"):
            self.import_file_btn.configure(text=t("import_url_file"))
        if hasattr(self, "deduplicate_btn"):
            self.deduplicate_btn.configure(text=t("deduplicate_urls"))
        if hasattr(self, "clear_btn"):
            self.clear_btn.configure(text=t("clear_url_list"))
        if hasattr(self, "check_new_btn"):
            self.check_new_btn.configure(text=t("check_new_videos"))
        if hasattr(self, "start_processing_btn"):
            self.start_processing_btn.configure(text=t("start_processing"))
        if hasattr(self, "cancel_processing_btn"):
            self.cancel_processing_btn.configure(text=t("cancel_processing"))
        if hasattr(self, "resume_processing_btn"):
            self.resume_processing_btn.configure(text=t("resume_processing"))
        if hasattr(self, "force_rerun_checkbox"):
            self.force_rerun_checkbox.configure(text=t("force_rerun_label"))

        # 更新语言配置面板
        if hasattr(self, "language_config_panel"):
            self.language_config_panel.refresh_language()

        # 更新 URL 文本框占位符（如果当前是占位符文本）
        if hasattr(self, "url_list_textbox"):
            text = self.url_list_textbox.get("1.0", "end-1c").strip()
            # 检查是否是占位符文本（通过检查第一行是否包含占位符特征）
            # 中文占位符第一行: "支持输入：视频链接..."
            # 英文占位符第一行: "Supports: Video URL..."
            first_line = text.split('\n')[0].strip() if text else ""
            is_zh_placeholder = "支持输入" in first_line or "视频链接" in first_line
            is_en_placeholder = "Supports:" in first_line or "Video URL" in first_line
            
            if is_zh_placeholder or is_en_placeholder or not text:
                # 是占位符或空，更新为当前语言的占位符
                self.url_list_textbox.delete("1.0", "end")
                self.url_list_textbox.insert("1.0", t("url_list_placeholder"))
                # 清除错误提示
                if hasattr(self, "url_error_label"):
                    self.url_error_label.configure(text="")
                    self.url_list_textbox.configure(border_color=["#979DA2", "#565B5E"])

        # 统计信息已移至日志面板，不再需要更新

