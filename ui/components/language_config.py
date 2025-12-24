"""
语言配置面板 - 可复用的语言设置 UI 组件

提取自 channel_page.py 和 url_list_page.py 中的共用代码
"""

import customtkinter as ctk
from typing import Callable, Optional, Dict, Any
from core.i18n import t
from ui.fonts import body_font


class LanguageConfigPanel(ctk.CTkFrame):
    """语言配置面板

    可复用的语言设置 UI 组件，包含：
    - 源语言选择（自动/手动）
    - 目标语言输入
    - 摘要语言
    - 双语模式
    - 翻译策略
    - 字幕格式
    """

    def __init__(
        self,
        parent,
        language_config: Optional[Dict] = None,
        translation_ai_config: Optional[Dict] = None,
        summary_ai_config: Optional[Dict] = None,
        on_save: Optional[Callable[[Dict], None]] = None,
        on_translation_enabled_changed: Optional[Callable[[bool], None]] = None,
        on_summary_enabled_changed: Optional[Callable[[bool], None]] = None,
        **kwargs
    ):
        """初始化语言配置面板

        Args:
            parent: 父容器
            language_config: 语言配置字典
            translation_ai_config: 翻译 AI 配置
            summary_ai_config: 摘要 AI 配置
            on_save: 保存回调
            on_translation_enabled_changed: 翻译启用状态变化回调
            on_summary_enabled_changed: 摘要启用状态变化回调
        """
        super().__init__(parent, **kwargs)
        
        self.language_config = language_config or {}
        self.translation_ai_config = translation_ai_config or {}
        self.summary_ai_config = summary_ai_config or {}
        self.on_save = on_save
        self.on_translation_enabled_changed = on_translation_enabled_changed
        self.on_summary_enabled_changed = on_summary_enabled_changed
        
        self.grid_columnconfigure(1, weight=1)
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        # 标题
        self._config_label = ctk.CTkLabel(
            self, text=t("language_config_label"), font=body_font(weight="bold")
        )
        self._config_label.grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8)
        )

        # 源语言
        self._build_source_language_row()
        
        # 目标语言
        self._build_target_language_row()
        
        # 摘要语言
        self._build_summary_language_row()
        
        # 翻译策略（在双语模式之前构建，确保复选框存在）
        self._build_translation_strategy_row()
        
        # 双语模式
        self._build_bilingual_mode_row()
        
        # 字幕格式
        self._build_subtitle_format_row()
        
        # 保存按钮
        self._build_save_button()

    def _build_source_language_row(self):
        """构建源语言行"""
        self._source_language_label = ctk.CTkLabel(self, text=t("source_language_label"), font=body_font())
        self._source_language_label.grid(row=1, column=0, sticky="w", padx=16, pady=8)

        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=1, column=1, sticky="w", padx=16, pady=8)

        self.source_language_entry = ctk.CTkEntry(
            input_frame, width=120, placeholder_text=t("source_language_placeholder"), font=body_font()
        )
        self.source_language_entry.pack(side="left", padx=(0, 12))

        self.source_language_auto_checkbox = ctk.CTkCheckBox(
            input_frame,
            text=t("auto_select"),
            font=body_font(),
            command=self._on_source_language_auto_toggle,
        )
        self.source_language_auto_checkbox.pack(side="left", padx=(0, 12))

        self._source_language_hint = ctk.CTkLabel(
            input_frame,
            text=t("source_language_auto_hint"),
            font=body_font(),
            text_color=("gray50", "gray50"),
        )
        self._source_language_hint.pack(side="left")

        # 设置默认值
        source_language = self.language_config.get("source_language")
        if source_language:
            self.source_language_entry.insert(0, source_language)
            self.source_language_auto_checkbox.deselect()
        else:
            self.source_language_auto_checkbox.select()
            self.source_language_entry.configure(state="disabled")

    def _build_target_language_row(self):
        """构建目标语言行"""
        self._target_language_label = ctk.CTkLabel(self, text=t("target_language_label"), font=body_font())
        self._target_language_label.grid(row=2, column=0, sticky="w", padx=16, pady=8)

        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=2, column=1, sticky="w", padx=16, pady=8)

        self.subtitle_target_entry = ctk.CTkEntry(
            input_frame, width=120, placeholder_text=t("target_language_placeholder"), font=body_font()
        )
        self.subtitle_target_entry.pack(side="left", padx=(0, 12))

        self._target_language_hint = ctk.CTkLabel(
            input_frame,
            text=t("target_language_hint"),
            font=body_font(),
            text_color=("gray50", "gray50"),
        )
        self._target_language_hint.pack(side="left")

        # 设置默认值
        if self.language_config.get("subtitle_target_languages"):
            first_lang = self.language_config["subtitle_target_languages"][0]
            self.subtitle_target_entry.insert(0, first_lang)
        else:
            self.subtitle_target_entry.insert(0, "zh-CN")

    def _build_summary_language_row(self):
        """构建摘要语言行"""
        self._summary_language_label = ctk.CTkLabel(self, text=t("summary_language_label"), font=body_font())
        self._summary_language_label.grid(row=3, column=0, sticky="w", padx=16, pady=8)

        entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        entry_frame.grid(row=3, column=1, sticky="w", padx=16, pady=8)

        self.summary_language_entry = ctk.CTkEntry(entry_frame, width=200, font=body_font())
        self.summary_language_entry.pack(side="left", padx=(0, 8))

        self._summary_language_hint = ctk.CTkLabel(
            entry_frame,
            text=t("summary_language_hint"),
            font=body_font(),
            text_color=("gray50", "gray50"),
        )
        self._summary_language_hint.pack(side="left", padx=(0, 12))

        self.summary_enabled_checkbox = ctk.CTkCheckBox(
            entry_frame,
            text=t("enable_summary"),
            font=body_font(),
            command=self._on_summary_enabled_changed,
        )
        self.summary_enabled_checkbox.pack(side="left")

        if self.summary_ai_config.get("enabled", True):
            self.summary_enabled_checkbox.select()
        if self.language_config.get("summary_language"):
            self.summary_language_entry.insert(0, self.language_config["summary_language"])

    def _build_bilingual_mode_row(self):
        """构建双语模式行"""
        self._bilingual_mode_label = ctk.CTkLabel(self, text=t("bilingual_mode_label"), font=body_font())
        self._bilingual_mode_label.grid(row=5, column=0, sticky="w", padx=16, pady=8)

        bilingual_frame = ctk.CTkFrame(self, fg_color="transparent")
        bilingual_frame.grid(row=5, column=1, sticky="w", padx=16, pady=8)

        self.bilingual_mode_combo = ctk.CTkComboBox(
            bilingual_frame,
            values=[t("bilingual_mode_none"), t("bilingual_mode_source_target")],
            width=200,
            font=body_font(),
            dropdown_font=body_font(),
            command=self._on_bilingual_mode_changed,
        )
        self.bilingual_mode_combo.pack(side="left")

        # 静态提示（始终显示）
        self._bilingual_hint_label = ctk.CTkLabel(
            bilingual_frame,
            text=t("bilingual_requires_translation_hint"),
            font=body_font(),
            text_color=("gray50", "gray50"),
        )
        self._bilingual_hint_label.pack(side="left", padx=10)

        bilingual_mode = self.language_config.get("bilingual_mode", "none")
        if bilingual_mode == "none":
            self.bilingual_mode_combo.set(t("bilingual_mode_none"))
        else:
            self.bilingual_mode_combo.set(t("bilingual_mode_source_target"))

    def _on_bilingual_mode_changed(self, value):
        """双语模式变更回调：选择双语模式时自动勾选翻译"""
        is_bilingual = value == t("bilingual_mode_source_target")
        
        if is_bilingual and hasattr(self, 'translation_enabled_checkbox'):
            # 自动勾选翻译
            if self.translation_enabled_checkbox.get() != 1:
                self.translation_enabled_checkbox.select()
                # 触发翻译启用回调
                if self.on_translation_enabled_changed:
                    self.on_translation_enabled_changed(True)

    def _build_translation_strategy_row(self):
        """构建翻译策略行"""
        self._translation_strategy_label = ctk.CTkLabel(self, text=t("translation_strategy_label"), font=body_font())
        self._translation_strategy_label.grid(row=4, column=0, sticky="w", padx=16, pady=8)

        strategy_frame = ctk.CTkFrame(self, fg_color="transparent")
        strategy_frame.grid(row=4, column=1, sticky="w", padx=16, pady=8)

        self.translation_strategy_combo = ctk.CTkComboBox(
            strategy_frame,
            values=[
                t("translation_strategy_ai_only"),
                t("translation_strategy_official_auto_then_ai"),
                t("translation_strategy_official_only"),
            ],
            width=200,
            font=body_font(),
            dropdown_font=body_font(),
        )
        self.translation_strategy_combo.pack(side="left", padx=(0, 8))

        self._translation_strategy_hint = ctk.CTkLabel(
            strategy_frame,
            text=t("translation_strategy_hint"),
            font=body_font(),
            text_color=("gray50", "gray50"),
        )
        self._translation_strategy_hint.pack(side="left", padx=(0, 12))

        self.translation_enabled_checkbox = ctk.CTkCheckBox(
            strategy_frame,
            text=t("enable_translation"),
            font=body_font(),
            command=self._on_translation_enabled_changed,
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

    def _build_subtitle_format_row(self):
        """构建字幕格式行"""
        self._subtitle_format_label = ctk.CTkLabel(self, text=t("subtitle_format_label"), font=body_font())
        self._subtitle_format_label.grid(row=6, column=0, sticky="w", padx=16, pady=8)

        self.subtitle_format_combo = ctk.CTkComboBox(
            self,
            values=[
                t("subtitle_format_srt"),
                t("subtitle_format_txt"),
                t("subtitle_format_both"),
            ],
            width=200,
            font=body_font(),
            dropdown_font=body_font(),
        )
        self.subtitle_format_combo.grid(row=6, column=1, sticky="w", padx=16, pady=8)

        subtitle_format = self.language_config.get("subtitle_format", "srt")
        if subtitle_format == "txt":
            self.subtitle_format_combo.set(t("subtitle_format_txt"))
        elif subtitle_format == "both":
            self.subtitle_format_combo.set(t("subtitle_format_both"))
        else:
            self.subtitle_format_combo.set(t("subtitle_format_srt"))

    def _build_save_button(self):
        """构建保存按钮"""
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16))

        self.save_btn = ctk.CTkButton(
            btn_frame,
            text=t("language_config_save"),
            command=self._on_save,
            width=120,
            font=body_font(),
        )
        self.save_btn.pack(side="left", padx=(0, 8))

    def _on_source_language_auto_toggle(self):
        """源语言自动选择勾选框状态变化"""
        if self.source_language_auto_checkbox.get() == 1:
            self.source_language_entry.configure(state="disabled")
        else:
            self.source_language_entry.configure(state="normal")

    def _on_translation_enabled_changed(self):
        """翻译启用勾选框状态变化"""
        enabled = self.translation_enabled_checkbox.get() == 1
        if self.on_translation_enabled_changed:
            self.on_translation_enabled_changed(enabled)

    def _on_summary_enabled_changed(self):
        """摘要启用勾选框状态变化"""
        enabled = self.summary_enabled_checkbox.get() == 1
        if self.on_summary_enabled_changed:
            self.on_summary_enabled_changed(enabled)

    def _on_save(self):
        """保存语言配置"""
        config = self.get_config()
        if self.on_save:
            self.on_save(config)

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置

        Returns:
            语言配置字典
        """
        # 获取字幕目标语言
        subtitle_target_lang = self.subtitle_target_entry.get().strip()
        if not subtitle_target_lang:
            subtitle_target_lang = "zh-CN"
        subtitle_target_languages = [subtitle_target_lang]

        # 获取源语言
        if self.source_language_auto_checkbox.get() == 1:
            source_language = None
        else:
            source_language = self.source_language_entry.get().strip() or None

        # 获取摘要语言
        summary_language = self.summary_language_entry.get().strip()
        if not summary_language:
            summary_language = "zh-CN"

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

        return {
            "subtitle_target_languages": subtitle_target_languages,
            "summary_language": summary_language,
            "source_language": source_language,
            "bilingual_mode": bilingual_mode,
            "translation_strategy": translation_strategy,
            "subtitle_format": subtitle_format,
        }

    def refresh_language(self):
        """刷新语言相关文本"""
        # 更新配置标题
        if hasattr(self, "_config_label"):
            self._config_label.configure(text=t("language_config_label"))
        
        # 更新保存按钮
        if hasattr(self, "save_btn"):
            self.save_btn.configure(text=t("language_config_save"))
        
        # 更新所有行标签
        if hasattr(self, "_source_language_label"):
            self._source_language_label.configure(text=t("source_language_label"))
        if hasattr(self, "_target_language_label"):
            self._target_language_label.configure(text=t("target_language_label"))
        if hasattr(self, "_summary_language_label"):
            self._summary_language_label.configure(text=t("summary_language_label"))
        if hasattr(self, "_bilingual_mode_label"):
            self._bilingual_mode_label.configure(text=t("bilingual_mode_label"))
        if hasattr(self, "_translation_strategy_label"):
            self._translation_strategy_label.configure(text=t("translation_strategy_label"))
        if hasattr(self, "_subtitle_format_label"):
            self._subtitle_format_label.configure(text=t("subtitle_format_label"))
        
        # 更新提示文本
        if hasattr(self, "_source_language_hint"):
            self._source_language_hint.configure(text=t("source_language_auto_hint"))
        if hasattr(self, "_target_language_hint"):
            self._target_language_hint.configure(text=t("target_language_hint"))
        if hasattr(self, "_summary_language_hint"):
            self._summary_language_hint.configure(text=t("summary_language_hint"))
        if hasattr(self, "_translation_strategy_hint"):
            self._translation_strategy_hint.configure(text=t("translation_strategy_hint"))
        
        # 更新复选框文本
        if hasattr(self, "source_language_auto_checkbox"):
            self.source_language_auto_checkbox.configure(text=t("auto_select"))
        if hasattr(self, "summary_enabled_checkbox"):
            self.summary_enabled_checkbox.configure(text=t("enable_summary"))
        if hasattr(self, "translation_enabled_checkbox"):
            self.translation_enabled_checkbox.configure(text=t("enable_translation"))
        
        # 更新下拉框值（需要保存当前选择并重新设置）
        if hasattr(self, "bilingual_mode_combo"):
            current = self.bilingual_mode_combo.get()
            self.bilingual_mode_combo.configure(values=[
                t("bilingual_mode_none"), 
                t("bilingual_mode_source_target")
            ])
            # 保持选择状态
            if "source" in current.lower() or "target" in current.lower() or "原文" in current:
                self.bilingual_mode_combo.set(t("bilingual_mode_source_target"))
            else:
                self.bilingual_mode_combo.set(t("bilingual_mode_none"))
        
        if hasattr(self, "translation_strategy_combo"):
            current = self.translation_strategy_combo.get()
            self.translation_strategy_combo.configure(values=[
                t("translation_strategy_ai_only"),
                t("translation_strategy_official_auto_then_ai"),
                t("translation_strategy_official_only"),
            ])
            # 保持选择状态
            if "AI" in current.upper() and "OFFICIAL" not in current.upper():
                self.translation_strategy_combo.set(t("translation_strategy_ai_only"))
            elif "OFFICIAL" in current.upper() and "AI" not in current.upper():
                self.translation_strategy_combo.set(t("translation_strategy_official_only"))
            else:
                self.translation_strategy_combo.set(t("translation_strategy_official_auto_then_ai"))
        
        if hasattr(self, "subtitle_format_combo"):
            current = self.subtitle_format_combo.get()
            self.subtitle_format_combo.configure(values=[
                t("subtitle_format_srt"),
                t("subtitle_format_txt"),
                t("subtitle_format_both"),
            ])
            # 保持选择状态
            if "txt" in current.lower():
                self.subtitle_format_combo.set(t("subtitle_format_txt"))
            elif "both" in current.lower() or "两者" in current:
                self.subtitle_format_combo.set(t("subtitle_format_both"))
            else:
                self.subtitle_format_combo.set(t("subtitle_format_srt"))


