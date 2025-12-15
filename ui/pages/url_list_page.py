"""
URL 列表模式页面
包含多行 URL 输入、检测按钮、开始处理按钮
"""
import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Optional, Dict, Any
from pathlib import Path
from ui.i18n_manager import t
from ui.fonts import title_font, body_font, small_font


class UrlListPage(ctk.CTkFrame):
    """URL 列表模式页面"""
    
    def __init__(
        self,
        parent,
        on_check_new: Optional[Callable[[str, bool], None]] = None,
        on_start_processing: Optional[Callable[[str, bool], None]] = None,
        on_cancel_processing: Optional[Callable[[], None]] = None,
        stats: Optional[Dict[str, int]] = None,
        running_status: str = "",
        language_config: Optional[dict] = None,
        on_save_language_config: Optional[Callable[[dict], None]] = None,
        translation_ai_config: Optional[dict] = None,
        summary_ai_config: Optional[dict] = None,
        on_save_translation_ai: Optional[Callable[[dict], None]] = None,
        on_save_summary_ai: Optional[Callable[[dict], None]] = None,
        initial_url_list_text: str = "",
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.on_check_new = on_check_new
        self.on_start_processing = on_start_processing
        self.on_cancel_processing = on_cancel_processing
        self.stats = stats or {"total": 0, "success": 0, "failed": 0, "current": 0}
        self.running_status = running_status
        self.language_config = language_config or {}
        self.on_save_language_config = on_save_language_config
        self.translation_ai_config = translation_ai_config or {}
        self.summary_ai_config = summary_ai_config or {}
        self.on_save_translation_ai = on_save_translation_ai
        self.on_save_summary_ai = on_save_summary_ai
        self.initial_url_list_text = initial_url_list_text or ""
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # 创建可滚动的容器
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, padx=0, pady=0)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # 标题
        self._title_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=t("url_list_mode"),
            font=title_font(weight="bold")
        )
        self._title_label.pack(pady=16)
        
        # URL 列表输入提示
        self._hint_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=t("url_list_hint"),
            font=body_font(),
            text_color=("gray50", "gray50"),
            justify="left"
        )
        self._hint_label.pack(pady=(0, 8), padx=32)
        
        # URL 列表多行输入框（固定高度）
        url_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        url_frame.pack(fill="x", padx=32, pady=8)
        url_frame.grid_columnconfigure(0, weight=1)
        
        self.url_list_textbox = ctk.CTkTextbox(
            url_frame,
            wrap="word",
            font=body_font(),
            height=150  # 固定高度，避免占用过多空间
        )
        self.url_list_textbox.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        # 恢复保存的URL列表或使用占位符
        if self.initial_url_list_text:
            self.url_list_textbox.insert("1.0", self.initial_url_list_text)
        else:
            self.url_list_textbox.insert("1.0", t("url_list_placeholder"))
        
        # 按钮区域
        button_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=32, pady=8)
        
        # 导入文件按钮
        self.import_file_btn = ctk.CTkButton(
            button_frame,
            text=t("import_url_file"),
            command=self._on_import_file,
            width=120,
            fg_color="gray50",
            hover_color="gray40"
        )
        self.import_file_btn.pack(side="left", padx=8)
        
        # 去重按钮
        self.deduplicate_btn = ctk.CTkButton(
            button_frame,
            text=t("deduplicate_urls"),
            command=self._on_deduplicate_urls,
            width=100,
            fg_color="gray50",
            hover_color="gray40"
        )
        self.deduplicate_btn.pack(side="left", padx=8)
        
        # 清空按钮
        self.clear_btn = ctk.CTkButton(
            button_frame,
            text=t("clear_url_list"),
            command=self._on_clear_urls,
            width=80,
            fg_color="gray50",
            hover_color="gray40"
        )
        self.clear_btn.pack(side="left", padx=8)
        
        # 分隔
        spacer = ctk.CTkLabel(button_frame, text="", width=20)
        spacer.pack(side="left", padx=8)
        
        self.check_new_btn = ctk.CTkButton(
            button_frame,
            text=t("check_new_videos"),
            command=self._on_check_new,
            width=150
        )
        self.check_new_btn.pack(side="left", padx=8)
        
        self.start_processing_btn = ctk.CTkButton(
            button_frame,
            text=t("start_processing"),
            command=self._on_start_processing,
            width=150
        )
        self.start_processing_btn.pack(side="left", padx=8)
        
        # 取消任务按钮（始终显示，初始状态禁用）
        # 使用蓝色背景和白色文字，提高对比度
        self.cancel_processing_btn = ctk.CTkButton(
            button_frame,
            text=t("cancel_processing"),
            command=self._on_cancel_processing,
            width=150,
            font=body_font(),  # 明确指定字体，避免页面切换后文字模糊
            fg_color=("#4A9EFF", "#4A9EFF"),  # 禁用状态下使用淡蓝色背景
            hover_color=("#6BB5FF", "#6BB5FF"),  # 悬停时使用稍亮的蓝色
            text_color=("white", "white"),  # 使用白色文字，确保高对比度
            state="disabled"  # 初始状态禁用
        )
        self.cancel_processing_btn.pack(side="left", padx=8)
        # 强制刷新按钮，确保字体正确渲染
        self.after(10, lambda: self.cancel_processing_btn.update_idletasks())
        
        # 强制重跑选项
        self.force_rerun_checkbox = ctk.CTkCheckBox(
            button_frame,
            text=t("force_rerun_label"),
            font=body_font()
        )
        self.force_rerun_checkbox.pack(side="left", padx=16, pady=8)
        
        # 语言配置区域（与频道模式保持一致）
        config_frame = ctk.CTkFrame(self.scrollable_frame)
        config_frame.pack(fill="x", padx=32, pady=16)
        config_frame.grid_columnconfigure(1, weight=1)
        
        self._config_label = ctk.CTkLabel(
            config_frame,
            text=t("language_config_label"),
            font=body_font(weight="bold")
        )
        self._config_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        # 源语言（输入框 + 自动勾选框）- 放在上方
        self._source_lang_label = ctk.CTkLabel(config_frame, text=t("source_language_label"))
        self._source_lang_label.grid(row=1, column=0, sticky="w", padx=16, pady=8)
        
        # 源语言输入区域（输入框 + 自动勾选框 + 提示）
        source_lang_input_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        source_lang_input_frame.grid(row=1, column=1, sticky="w", padx=16, pady=8)
        
        # 源语言输入框
        self.source_language_entry = ctk.CTkEntry(source_lang_input_frame, width=120, placeholder_text=t("source_language_placeholder"))
        self.source_language_entry.pack(side="left", padx=(0, 12))
        
        # 自动选择勾选框
        self.source_language_auto_checkbox = ctk.CTkCheckBox(
            source_lang_input_frame,
            text=t("auto_select"),
            font=body_font(),
            command=self._on_source_language_auto_toggle
        )
        self.source_language_auto_checkbox.pack(side="left", padx=(0, 12))
        
        # 提示信息（与输入框同行）
        source_lang_hint = ctk.CTkLabel(
            source_lang_input_frame,
            text=t("source_language_auto_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        source_lang_hint.pack(side="left")
        
        # 设置默认值
        source_language = self.language_config.get("source_language")
        if source_language:
            # 有指定源语言，取消勾选自动，填入语言代码
            self.source_language_entry.insert(0, source_language)
            self.source_language_auto_checkbox.deselect()
        else:
            # 自动模式，勾选自动，禁用输入框
            self.source_language_auto_checkbox.select()
            self.source_language_entry.configure(state="disabled")
        
        # 目标语言（输入框）- 放在下方
        self._subtitle_target_label = ctk.CTkLabel(config_frame, text=t("target_language_label"))
        self._subtitle_target_label.grid(row=2, column=0, sticky="w", padx=16, pady=8)
        
        # 目标语言输入区域
        subtitle_target_input_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        subtitle_target_input_frame.grid(row=2, column=1, sticky="w", padx=16, pady=8)
        
        # 目标语言输入框
        self.subtitle_target_entry = ctk.CTkEntry(subtitle_target_input_frame, width=120, placeholder_text=t("target_language_placeholder"))
        self.subtitle_target_entry.pack(side="left", padx=(0, 12))
        
        # 提示信息（与输入框同行）
        self._subtitle_target_hint = ctk.CTkLabel(
            subtitle_target_input_frame,
            text=t("target_language_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        self._subtitle_target_hint.pack(side="left")
        
        # 设置默认值
        if self.language_config.get("subtitle_target_languages"):
            first_lang = self.language_config["subtitle_target_languages"][0]
            self.subtitle_target_entry.insert(0, first_lang)
        else:
            self.subtitle_target_entry.insert(0, "zh-CN")
        
        # 摘要语言（带启用勾选框）
        self._summary_lang_label = ctk.CTkLabel(config_frame, text=t("summary_language_label"))
        self._summary_lang_label.grid(row=3, column=0, sticky="w", padx=16, pady=8)
        summary_lang_entry_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        summary_lang_entry_frame.grid(row=3, column=1, sticky="w", padx=16, pady=8)
        self.summary_language_entry = ctk.CTkEntry(summary_lang_entry_frame, width=200)
        self.summary_language_entry.pack(side="left", padx=(0, 8))
        self._summary_lang_hint = ctk.CTkLabel(
            summary_lang_entry_frame,
            text=t("summary_language_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        self._summary_lang_hint.pack(side="left", padx=(0, 12))
        self.summary_enabled_checkbox = ctk.CTkCheckBox(
            summary_lang_entry_frame,
            text=t("enable_summary"),
            font=body_font(),
            command=self._on_summary_enabled_changed
        )
        self.summary_enabled_checkbox.pack(side="left")
        if self.summary_ai_config.get("enabled", True):
            self.summary_enabled_checkbox.select()
        if self.language_config.get("summary_language"):
            self.summary_language_entry.insert(0, self.language_config["summary_language"])
        
        # 双语模式
        self._bilingual_mode_label = ctk.CTkLabel(config_frame, text=t("bilingual_mode_label"))
        self._bilingual_mode_label.grid(row=4, column=0, sticky="w", padx=16, pady=8)
        self.bilingual_mode_combo = ctk.CTkComboBox(
            config_frame,
            values=[t("bilingual_mode_none"), t("bilingual_mode_source_target")],
            width=200
        )
        self.bilingual_mode_combo.grid(row=4, column=1, sticky="w", padx=16, pady=8)
        bilingual_mode = self.language_config.get("bilingual_mode", "none")
        if bilingual_mode == "none":
            self.bilingual_mode_combo.set(t("bilingual_mode_none"))
        else:
            self.bilingual_mode_combo.set(t("bilingual_mode_source_target"))
        
        # 翻译策略（带启用勾选框）
        self._translation_strategy_label = ctk.CTkLabel(config_frame, text=t("translation_strategy_label"))
        self._translation_strategy_label.grid(row=5, column=0, sticky="w", padx=16, pady=8)
        translation_strategy_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        translation_strategy_frame.grid(row=5, column=1, sticky="w", padx=16, pady=8)
        self.translation_strategy_combo = ctk.CTkComboBox(
            translation_strategy_frame,
            values=[
                t("translation_strategy_ai_only"),
                t("translation_strategy_official_auto_then_ai"),
                t("translation_strategy_official_only")
            ],
            width=200
        )
        self.translation_strategy_combo.pack(side="left", padx=(0, 8))
        self._translation_strategy_hint = ctk.CTkLabel(
            translation_strategy_frame,
            text=t("translation_strategy_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        self._translation_strategy_hint.pack(side="left", padx=(0, 12))
        self.translation_enabled_checkbox = ctk.CTkCheckBox(
            translation_strategy_frame,
            text=t("enable_translation"),
            font=body_font(),
            command=self._on_translation_enabled_changed
        )
        self.translation_enabled_checkbox.pack(side="left")
        if self.translation_ai_config.get("enabled", True):
            self.translation_enabled_checkbox.select()
        strategy = self.language_config.get("translation_strategy", "OFFICIAL_AUTO_THEN_AI")
        if strategy == "AI_ONLY":
            self.translation_strategy_combo.set(t("translation_strategy_ai_only"))
        elif strategy == "OFFICIAL_ONLY":
            self.translation_strategy_combo.set(t("translation_strategy_official_only"))
        else:
            self.translation_strategy_combo.set(t("translation_strategy_official_auto_then_ai"))
        
        # 字幕格式
        subtitle_format_label = ctk.CTkLabel(config_frame, text=t("subtitle_format_label"))
        subtitle_format_label.grid(row=6, column=0, sticky="w", padx=16, pady=8)
        self.subtitle_format_combo = ctk.CTkComboBox(
            config_frame,
            values=[
                t("subtitle_format_srt"),
                t("subtitle_format_txt"),
                t("subtitle_format_both")
            ],
            width=200
        )
        self.subtitle_format_combo.grid(row=6, column=1, sticky="w", padx=16, pady=8)
        subtitle_format = self.language_config.get("subtitle_format", "srt")
        if subtitle_format == "txt":
            self.subtitle_format_combo.set(t("subtitle_format_txt"))
        elif subtitle_format == "both":
            self.subtitle_format_combo.set(t("subtitle_format_both"))
        else:
            self.subtitle_format_combo.set(t("subtitle_format_srt"))
        
        # 保存按钮
        language_config_btn_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        language_config_btn_frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16))
        self.language_config_save_btn = ctk.CTkButton(
            language_config_btn_frame,
            text=t("language_config_save"),
            command=self._on_save_language_config,
            width=120
        )
        self.language_config_save_btn.pack(side="left", padx=(0, 8))
        
        # 统计信息已移至日志面板，此处不再显示
    
    def _on_import_file(self):
        """导入文件按钮点击"""
        file_path = filedialog.askopenfilename(
            title=t("import_url_file_title"),
            filetypes=[
                (t("text_files"), "*.txt"),
                (t("all_files"), "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
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
            r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<>"\']+',
            re.IGNORECASE
        )
        
        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 尝试直接匹配整行
            if 'youtube.com' in line or 'youtu.be' in line:
                # 提取行中的 URL
                matches = youtube_pattern.findall(line)
                for url in matches:
                    # 清理 URL（去除尾部的标点等）
                    url = url.rstrip('.,;:!?')
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
            r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<>"\']+',
            re.IGNORECASE
        )
        
        urls = []
        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 尝试直接匹配整行
            if 'youtube.com' in line or 'youtu.be' in line:
                # 提取行中的 URL
                matches = youtube_pattern.findall(line)
                for url in matches:
                    # 清理 URL（去除尾部的标点等）
                    url = url.rstrip('.,;:!?')
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
            logger.info(t("deduplicate_complete_message", removed=removed_count, remaining=len(unique_urls)))
        else:
            # 没有重复项
            logger.info(t("no_duplicates_found"))
    
    def _on_check_new(self):
        """检测新视频按钮点击"""
        urls_text = self._get_cleaned_urls_text()
        force = self.force_rerun_checkbox.get() == 1 if hasattr(self, 'force_rerun_checkbox') else False
        if self.on_check_new:
            self.on_check_new(urls_text, force)
    
    def _on_start_processing(self):
        """开始处理按钮点击"""
        urls_text = self._get_cleaned_urls_text()
        force = self.force_rerun_checkbox.get() == 1 if hasattr(self, 'force_rerun_checkbox') else False
        if self.on_start_processing:
            self.on_start_processing(urls_text, force)
    
    def _on_cancel_processing(self):
        """取消处理按钮点击"""
        if self.on_cancel_processing:
            self.on_cancel_processing()
    
    def _on_source_language_auto_toggle(self):
        """源语言自动选择勾选框状态变化"""
        if self.source_language_auto_checkbox.get() == 1:
            # 勾选了自动，禁用输入框
            self.source_language_entry.configure(state="disabled")
        else:
            # 取消勾选，启用输入框
            self.source_language_entry.configure(state="normal")
    
    def _on_translation_enabled_changed(self):
        """翻译启用勾选框状态变化"""
        enabled = self.translation_enabled_checkbox.get() == 1
        if self.on_save_translation_ai:
            # 更新配置并保存
            updated_config = self.translation_ai_config.copy()
            updated_config["enabled"] = enabled
            self.on_save_translation_ai(updated_config)
    
    def _on_summary_enabled_changed(self):
        """摘要启用勾选框状态变化"""
        enabled = self.summary_enabled_checkbox.get() == 1
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
        if hasattr(self, 'start_processing_btn') and hasattr(self, 'cancel_processing_btn'):
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
                    text_color=("white", "white")  # 使用白色文字，确保高对比度
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
                    text_color=("white", "white")  # 使用白色文字，确保高对比度
                )
                self.cancel_processing_btn.update_idletasks()  # 强制刷新
    
    def _get_cleaned_urls_text(self) -> str:
        """获取清理后的 URL 文本（排除占位符）"""
        text = self.url_list_textbox.get("1.0", "end-1c").strip()
        placeholder = t("url_list_placeholder")
        if text == placeholder:
            return ""
        return text
    
    def update_stats(self, stats: Dict[str, Any], status: str = ""):
        """更新统计信息（已移至日志面板，此方法保留以保持兼容性）"""
        self.stats = stats
        if status:
            self.running_status = status
        # 统计信息现在显示在日志面板中，不再更新页面内的显示
    
    def _on_save_language_config(self):
        """保存语言配置"""
        try:
            # 获取字幕目标语言（输入框）
            subtitle_target_lang = self.subtitle_target_entry.get().strip()
            if not subtitle_target_lang:
                subtitle_target_lang = "zh-CN"  # 默认值
            subtitle_target_languages = [subtitle_target_lang]
            
            # 获取源语言
            if self.source_language_auto_checkbox.get() == 1:
                # 自动模式
                source_language = None
            else:
                # 手动指定
                source_language = self.source_language_entry.get().strip() or None
            
            # 获取摘要语言
            summary_language = self.summary_language_entry.get().strip()
            if not summary_language:
                summary_language = "zh-CN"  # 默认值
            
            # 获取双语模式
            bilingual_mode_text = self.bilingual_mode_combo.get()
            if bilingual_mode_text == t("bilingual_mode_source_target"):
                bilingual_mode = "source+target"
            else:
                bilingual_mode = "none"
            
            # 获取翻译策略
            strategy_text = self.translation_strategy_combo.get()
            if strategy_text == t("translation_strategy_ai_only"):
                translation_strategy = "AI_ONLY"
            elif strategy_text == t("translation_strategy_official_only"):
                translation_strategy = "OFFICIAL_ONLY"
            else:
                translation_strategy = "OFFICIAL_AUTO_THEN_AI"
            
            # 获取字幕格式
            format_text = self.subtitle_format_combo.get()
            if format_text == t("subtitle_format_txt"):
                subtitle_format = "txt"
            elif format_text == t("subtitle_format_both"):
                subtitle_format = "both"
            else:
                subtitle_format = "srt"
            
            language_config = {
                "subtitle_target_languages": subtitle_target_languages,
                "summary_language": summary_language,
                "source_language": source_language,
                "bilingual_mode": bilingual_mode,
                "translation_strategy": translation_strategy,
                "subtitle_format": subtitle_format
            }
            
            if self.on_save_language_config:
                self.on_save_language_config(language_config)
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger()
            logger.error(t("save_language_config_failed", error=str(e)))
    
    def refresh_language(self):
        """刷新语言相关文本"""
        # 更新标题
        if hasattr(self, '_title_label'):
            self._title_label.configure(text=t("url_list_mode"))
        
        # 更新提示
        if hasattr(self, '_hint_label'):
            self._hint_label.configure(text=t("url_list_hint"))
        
        # 更新按钮和标签文本
        if hasattr(self, 'import_file_btn'):
            self.import_file_btn.configure(text=t("import_url_file"))
        if hasattr(self, 'clear_btn'):
            self.clear_btn.configure(text=t("clear_url_list"))
        if hasattr(self, 'check_new_btn'):
            self.check_new_btn.configure(text=t("check_new_videos"))
        if hasattr(self, 'start_processing_btn'):
            self.start_processing_btn.configure(text=t("start_processing"))
        
        # 更新配置区域标签
        if hasattr(self, '_config_label'):
            self._config_label.configure(text=t("language_config_label"))
        if hasattr(self, '_subtitle_target_label'):
            self._subtitle_target_label.configure(text=t("subtitle_target_languages_label"))
        if hasattr(self, '_subtitle_target_hint'):
            self._subtitle_target_hint.configure(text=t("subtitle_target_languages_hint"))
        if hasattr(self, '_summary_lang_label'):
            self._summary_lang_label.configure(text=t("summary_language_label"))
        if hasattr(self, '_bilingual_mode_label'):
            self._bilingual_mode_label.configure(text=t("bilingual_mode_label"))
        if hasattr(self, '_translation_strategy_label'):
            self._translation_strategy_label.configure(text=t("translation_strategy_label"))
        if hasattr(self, 'language_config_save_btn'):
            self.language_config_save_btn.configure(text=t("language_config_save"))
        
        # 统计信息已移至日志面板，不再需要更新

