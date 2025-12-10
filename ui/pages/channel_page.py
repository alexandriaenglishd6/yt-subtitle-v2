"""
频道模式页面
包含频道 URL 输入、检测按钮、开始处理按钮、统计信息显示
"""
import customtkinter as ctk
from typing import Callable, Optional, Dict
from ui.i18n_manager import t
from ui.fonts import title_font, body_font


class ChannelPage(ctk.CTkFrame):
    """频道模式页面"""
    
    def __init__(
        self,
        parent,
        on_check_new: Optional[Callable[[str], None]] = None,
        on_start_processing: Optional[Callable[[str], None]] = None,
        stats: Optional[Dict[str, int]] = None,
        running_status: str = "",
        language_config: Optional[dict] = None,
        on_save_language_config: Optional[Callable[[dict], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.on_check_new = on_check_new
        self.on_start_processing = on_start_processing
        self.stats = stats or {"total": 0, "success": 0, "failed": 0, "current": 0}
        self.running_status = running_status
        self.language_config = language_config or {}
        self.on_save_language_config = on_save_language_config
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # 标题
        self._title_label = ctk.CTkLabel(
            self,
            text=t("channel_mode"),
            font=title_font(weight="bold")
        )
        self._title_label.pack(pady=16)
        
        # 频道 URL 输入框
        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.pack(fill="x", padx=32, pady=8)
        
        self._url_label = ctk.CTkLabel(url_frame, text=t("channel_url_label"))
        self._url_label.pack(side="left", padx=8)
        
        self.channel_url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text=t("channel_url_placeholder"),
            width=500
        )
        self.channel_url_entry.pack(side="left", fill="x", expand=True, padx=8)
        
        # 按钮区域
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=32, pady=8)
        
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
        
        # 语言配置区域
        config_frame = ctk.CTkFrame(self)
        config_frame.pack(fill="x", padx=32, pady=16)
        config_frame.grid_columnconfigure(1, weight=1)
        
        self._config_label = ctk.CTkLabel(
            config_frame,
            text=t("language_config_label"),
            font=body_font(weight="bold")
        )
        self._config_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        # 字幕目标语言
        subtitle_target_label = ctk.CTkLabel(config_frame, text=t("subtitle_target_languages_label"))
        subtitle_target_label.grid(row=1, column=0, sticky="w", padx=16, pady=8)
        self.subtitle_target_textbox = ctk.CTkTextbox(config_frame, height=60, wrap="word")
        self.subtitle_target_textbox.grid(row=1, column=1, sticky="ew", padx=16, pady=8)
        if self.language_config.get("subtitle_target_languages"):
            self.subtitle_target_textbox.insert("1.0", "\n".join(self.language_config["subtitle_target_languages"]))
        subtitle_target_hint = ctk.CTkLabel(
            config_frame,
            text=t("subtitle_target_languages_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        subtitle_target_hint.grid(row=2, column=1, sticky="w", padx=16, pady=(0, 8))
        
        # 摘要语言
        summary_lang_label = ctk.CTkLabel(config_frame, text=t("summary_language_label"))
        summary_lang_label.grid(row=3, column=0, sticky="w", padx=16, pady=8)
        self.summary_language_entry = ctk.CTkEntry(config_frame, width=200)
        self.summary_language_entry.grid(row=3, column=1, sticky="w", padx=16, pady=8)
        if self.language_config.get("summary_language"):
            self.summary_language_entry.insert(0, self.language_config["summary_language"])
        
        # 双语模式
        bilingual_mode_label = ctk.CTkLabel(config_frame, text=t("bilingual_mode_label"))
        bilingual_mode_label.grid(row=4, column=0, sticky="w", padx=16, pady=8)
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
        
        # 翻译策略
        translation_strategy_label = ctk.CTkLabel(config_frame, text=t("translation_strategy_label"))
        translation_strategy_label.grid(row=5, column=0, sticky="w", padx=16, pady=8)
        self.translation_strategy_combo = ctk.CTkComboBox(
            config_frame,
            values=[
                t("translation_strategy_ai_only"),
                t("translation_strategy_official_auto_then_ai"),
                t("translation_strategy_official_only")
            ],
            width=200
        )
        self.translation_strategy_combo.grid(row=5, column=1, sticky="w", padx=16, pady=8)
        strategy = self.language_config.get("translation_strategy", "OFFICIAL_AUTO_THEN_AI")
        if strategy == "AI_ONLY":
            self.translation_strategy_combo.set(t("translation_strategy_ai_only"))
        elif strategy == "OFFICIAL_ONLY":
            self.translation_strategy_combo.set(t("translation_strategy_official_only"))
        else:
            self.translation_strategy_combo.set(t("translation_strategy_official_auto_then_ai"))
        
        # 保存按钮
        language_config_btn_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        language_config_btn_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16))
        self.language_config_save_btn = ctk.CTkButton(
            language_config_btn_frame,
            text=t("language_config_save"),
            command=self._on_save_language_config,
            width=120
        )
        self.language_config_save_btn.pack(side="left", padx=(0, 8))
        
        # 统计信息区域
        stats_frame = ctk.CTkFrame(self)
        stats_frame.pack(fill="x", padx=32, pady=16)
        
        self._stats_label = ctk.CTkLabel(
            stats_frame,
            text=t("stats_info"),
            font=body_font(weight="bold")
        )
        self._stats_label.pack(pady=8)
        
        self.stats_text = ctk.CTkLabel(
            stats_frame,
            text=t("stats_template", total=0, success=0, failed=0, status=t("status_idle")),
            font=body_font(),
            justify="left"
        )
        self.stats_text.pack(pady=8)
    
    def _on_check_new(self):
        """检测新视频按钮点击"""
        url = self.channel_url_entry.get().strip()
        if self.on_check_new:
            self.on_check_new(url)
    
    def _on_start_processing(self):
        """开始处理按钮点击"""
        url = self.channel_url_entry.get().strip()
        if self.on_start_processing:
            self.on_start_processing(url)
    
    def update_stats(self, stats: Dict[str, int], status: str = ""):
        """更新统计信息"""
        self.stats = stats
        if status:
            self.running_status = status
        if hasattr(self, 'stats_text'):
            self.stats_text.configure(
                text=t("stats_template",
                      total=stats.get("total", 0),
                      success=stats.get("success", 0),
                      failed=stats.get("failed", 0),
                      status=status or self.running_status or t("status_idle"))
            )
    
    def _on_save_language_config(self):
        """保存语言配置"""
        try:
            # 获取字幕目标语言
            subtitle_target_text = self.subtitle_target_textbox.get("1.0", "end-1c").strip()
            subtitle_target_languages = [lang.strip() for lang in subtitle_target_text.split("\n") if lang.strip()]
            if not subtitle_target_languages:
                subtitle_target_languages = ["zh-CN"]  # 默认值
            
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
            
            language_config = {
                "subtitle_target_languages": subtitle_target_languages,
                "summary_language": summary_language,
                "bilingual_mode": bilingual_mode,
                "translation_strategy": translation_strategy
            }
            
            if self.on_save_language_config:
                self.on_save_language_config(language_config)
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger()
            logger.error(f"保存语言配置失败: {e}")
    
    def refresh_language(self):
        """刷新语言相关文本"""
        # 更新标题
        if hasattr(self, '_title_label'):
            self._title_label.configure(text=t("channel_mode"))
        
        # 更新按钮和标签文本
        if hasattr(self, 'check_new_btn'):
            self.check_new_btn.configure(text=t("check_new_videos"))
        if hasattr(self, 'start_processing_btn'):
            self.start_processing_btn.configure(text=t("start_processing"))
        
        # 更新 URL 标签
        if hasattr(self, '_url_label'):
            self._url_label.configure(text=t("channel_url_label"))
        
        # 更新 URL 输入框占位符
        if hasattr(self, 'channel_url_entry'):
            self.channel_url_entry.configure(placeholder_text=t("channel_url_placeholder"))
        
        # 更新配置区域标签
        if hasattr(self, '_config_label'):
            self._config_label.configure(text=t("language_config_label"))
        
        # 更新统计信息标签
        if hasattr(self, '_stats_label'):
            self._stats_label.configure(text=t("stats_info"))
        
        # 更新统计信息显示
        if hasattr(self, 'stats_text'):
            self.update_stats(self.stats, self.running_status)

