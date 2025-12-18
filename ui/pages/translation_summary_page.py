"""
翻译&摘要页面
包含翻译 AI 和摘要 AI 配置
"""

import customtkinter as ctk
from typing import Callable, Optional, Dict
from ui.i18n_manager import t
from ui.fonts import title_font, heading_font, body_font
from core.logger import get_logger

logger = get_logger()

# AI 供应商默认配置和可用模型列表
AI_PROVIDER_CONFIGS: Dict[str, Dict[str, any]] = {
    "openai": {
        "model": "gpt-5.2",
        "base_url": "https://api.openai.com/v1",  # 官方 API 地址
        "models": [
            "gpt-5.2",
            "gpt-5.2-instant",
            "gpt-5.2-thinking",
            "gpt-5.2-pro",
            "gpt-5.1",
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-4o-mini",
        ],
    },
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "gemini": {
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com",
        "models": [
            "gemini-3-pro-preview",
            "gemini-2.5-pro",
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
    },
    "anthropic": {
        "model": "claude-sonnet-4-5-20250929",
        "base_url": "https://api.anthropic.com",  # 官方 API 地址
        "models": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-5-20251101",
            "claude-opus-4-1-20250805",
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-20241022",
        ],
    },
    "siliconflow": {
        "model": "deepseek-ai/DeepSeek-V3",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-V2.5",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
            "Qwen/Qwen2.5-72B-Instruct",
            "THUDM/glm-4-9b-chat",
        ],
    },
    "openrouter": {
        "model": "google/gemini-flash-1.5",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "google/gemini-flash-1.5",
            "anthropic/claude-3.5-sonnet",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.1-70b-instruct",
        ],
    },
    "groq": {
        "model": "llama-3.1-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
    },
    "kimi": {
        "model": "kimi-k2-turbo-preview",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["kimi-k2-0905-preview", "kimi-k2-thinking", "kimi-k2-turbo-preview"],
    },
    "glm": {
        "model": "GLM-4.6",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "models": [
            "GLM-4.6",
            "GLM-4.6V-Flash",
            "GLM-4.5",
            "GLM-4.5-X",
            "GLM-4.5-Air",
            "GLM-4.5-AirX",
            "GLM-4.5-Flash",
            "GLM-4-Air-250414",
            "GLM-4-Long",
            "GLM-4-FlashX-250414",
        ],
    },
    "ollama": {
        "model": "qwen2.5",
        "base_url": "http://localhost:11434/v1",
        "models": ["qwen2.5", "llama3.1", "mistral", "gemma2"],
    },
    "lm_studio": {
        "model": "local-model",
        "base_url": "http://localhost:1234/v1",
        "models": ["local-model"],
    },
    "google_translate": {
        "model": "google_translate_free",
        "base_url": "",  # Google 翻译免费版不需要 API 地址
        "models": ["google_translate_free"],
        "requires_api_key": False,  # 标记不需要 API Key
    },
    "openai_compatible": {
        "model": "gpt-5.2",
        "base_url": "http://your-api-base-url/v1",
        "models": [
            "gpt-5.2",
            "gpt-5.1",
            "gpt-5",
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-sonnet",
        ],
    },
    "custom_openai": {
        "model": "gpt-5.2",
        "base_url": "http://your-api-base-url/v1",
        "models": [
            "gpt-5.2",
            "gpt-5.1",
            "gpt-5",
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-sonnet",
        ],
    },
    "gemini_openai": {
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": ["gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro"],
    },
}

# 供应商预填示例（用于快速配置）
AI_PREFILL_EXAMPLES = {
    "gemini_openai": {
        "name": "Gemini (OpenAI Compatible)",
        "provider": "gemini_openai",
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "tip": "ai_tip_gemini_openai",
    },
    "custom_openai": {
        "name": "Custom OpenAI Compatible",
        "provider": "custom_openai",
        "model": "gpt-5.2",
        "base_url": "https://your-proxy-api.com/v1",
        "tip": "ai_tip_openai_compatible",
    },
    "lm_studio": {
        "name": "LM Studio (Local)",
        "provider": "lm_studio",
        "model": "local-model",
        "base_url": "http://localhost:1234/v1",
        "tip": "ai_tip_lm_studio",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "provider": "ollama",
        "model": "qwen2.5",
        "base_url": "http://localhost:11434/v1",
        "tip": "ai_tip_ollama",
    },
}


class TranslationSummaryPage(ctk.CTkFrame):
    """翻译&摘要页面"""

    def __init__(
        self,
        parent,
        translation_ai_config: Optional[dict] = None,
        summary_ai_config: Optional[dict] = None,
        on_save_translation_ai: Optional[Callable[[dict], None]] = None,
        on_save_summary_ai: Optional[Callable[[dict], None]] = None,
        on_log_message: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.translation_ai_config = translation_ai_config or {}
        self.summary_ai_config = summary_ai_config or {}
        self.on_save_translation_ai = on_save_translation_ai
        self.on_save_summary_ai = on_save_summary_ai
        self.on_log_message = on_log_message
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        # 创建滚动框架
        scroll_frame = ctk.CTkScrollableFrame(self)
        scroll_frame.pack(fill="both", expand=True, padx=16, pady=16)
        scroll_frame.grid_columnconfigure(0, weight=1)

        # 标题
        title = ctk.CTkLabel(
            scroll_frame,
            text=t("translation_summary_group"),
            font=title_font(weight="bold"),
        )
        title.pack(pady=(0, 24))

        # 翻译 AI 配置区域
        translation_ai_frame = ctk.CTkFrame(scroll_frame)
        translation_ai_frame.pack(fill="x", pady=(0, 24))
        translation_ai_frame.grid_columnconfigure(1, weight=1)

        # 翻译 AI 标题
        translation_ai_label = ctk.CTkLabel(
            translation_ai_frame,
            text=t("translation_ai_config_label"),
            font=heading_font(weight="bold"),
        )
        translation_ai_label.grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8)
        )

        # 翻译 AI 配置字段
        last_row = self._build_ai_config_fields(
            translation_ai_frame, self.translation_ai_config, "translation", start_row=1
        )

        # 翻译 AI 保存和测试按钮
        translation_btn_frame = ctk.CTkFrame(
            translation_ai_frame, fg_color="transparent"
        )
        translation_btn_frame.grid(
            row=last_row + 1, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16)
        )

        self.translation_save_btn = ctk.CTkButton(
            translation_btn_frame,
            text=t("ai_save_translation"),
            command=self._on_save_translation_ai,
            width=120,
        )
        self.translation_save_btn.pack(side="left", padx=(0, 8))

        self.translation_test_btn = ctk.CTkButton(
            translation_btn_frame,
            text=t("ai_test_connection"),
            command=self._on_test_translation_ai,
            width=120,
            fg_color="gray50",
            hover_color="gray40",
        )
        self.translation_test_btn.pack(side="left", padx=(0, 8))

        # 摘要 AI 配置区域
        summary_ai_frame = ctk.CTkFrame(scroll_frame)
        summary_ai_frame.pack(fill="x", pady=(0, 24))
        summary_ai_frame.grid_columnconfigure(1, weight=1)

        # 摘要 AI 标题
        summary_ai_label = ctk.CTkLabel(
            summary_ai_frame,
            text=t("summary_ai_config_label"),
            font=heading_font(weight="bold"),
        )
        summary_ai_label.grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8)
        )

        # 摘要 AI 配置字段
        last_row = self._build_ai_config_fields(
            summary_ai_frame, self.summary_ai_config, "summary", start_row=1
        )

        # 摘要 AI 保存和测试按钮
        summary_btn_frame = ctk.CTkFrame(summary_ai_frame, fg_color="transparent")
        summary_btn_frame.grid(
            row=last_row + 1, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16)
        )

        self.summary_save_btn = ctk.CTkButton(
            summary_btn_frame,
            text=t("ai_save_summary"),
            command=self._on_save_summary_ai,
            width=120,
        )
        self.summary_save_btn.pack(side="left", padx=(0, 8))

        self.summary_test_btn = ctk.CTkButton(
            summary_btn_frame,
            text=t("ai_test_connection"),
            command=self._on_test_summary_ai,
            width=120,
            fg_color="gray50",
            hover_color="gray40",
        )
        self.summary_test_btn.pack(side="left", padx=(0, 8))

    def _build_ai_config_fields(
        self, parent_frame, ai_config: dict, prefix: str, start_row: int = 1
    ):
        """构建 AI 配置字段"""
        row = start_row

        # Provider (下拉框)
        provider_label = ctk.CTkLabel(parent_frame, text=t("ai_provider_label"))
        provider_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)

        provider_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        provider_frame.grid(row=row, column=1, sticky="w", padx=16, pady=8)

        provider_combo = ctk.CTkComboBox(
            provider_frame,
            values=list(AI_PROVIDER_CONFIGS.keys()),
            width=300,
            command=lambda value, p=prefix: self._on_provider_changed(p, value),
        )
        provider_combo.grid(row=0, column=0, sticky="w")

        # 快速预填按钮
        prefill_btn = ctk.CTkButton(
            provider_frame,
            text=t("ai_prefill_button"),
            width=80,
            command=lambda p=prefix: self._show_prefill_menu(p),
        )
        prefill_btn.grid(row=0, column=1, padx=(8, 0))

        setattr(self, f"{prefix}_ai_provider_combo", provider_combo)
        current_provider = ai_config.get("provider", "openai")
        setattr(self, f"{prefix}_last_provider", current_provider)
        if current_provider in AI_PROVIDER_CONFIGS:
            provider_combo.set(current_provider)
        else:
            provider_combo.set("openai")
            setattr(self, f"{prefix}_last_provider", "openai")

        row += 1

        # Provider Tip Label
        tip_label = ctk.CTkLabel(
            parent_frame,
            text="",
            font=body_font(),
            text_color=("gray50", "gray50"),
            justify="left",
            wraplength=600,
        )
        tip_label.grid(row=row, column=1, sticky="w", padx=16, pady=(0, 8))
        setattr(self, f"{prefix}_ai_provider_tip_label", tip_label)

        # 设置初始提示
        initial_tip_key = f"ai_tip_{current_provider}"
        initial_tip_text = t(initial_tip_key)
        if initial_tip_text != initial_tip_key:
            tip_label.configure(text=initial_tip_text)

        row += 1

        # Model (下拉框)
        model_label = ctk.CTkLabel(parent_frame, text=t("ai_model_label"))
        model_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        provider = current_provider if current_provider in AI_PROVIDER_CONFIGS else "openai"
        model_values = AI_PROVIDER_CONFIGS[provider]["models"]
        model_combo = ctk.CTkComboBox(parent_frame, values=model_values, width=300)
        model_combo.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_model_combo", model_combo)

        if ai_config.get("model"):
            model_combo.set(ai_config["model"])
        else:
            default_model = AI_PROVIDER_CONFIGS[provider]["model"]
            model_combo.set(default_model)

        row += 1

        # Model Tip Label
        model_tip_label = ctk.CTkLabel(
            parent_frame,
            text=t("ai_model_tip"),
            font=body_font(),
            text_color=("gray50", "gray50"),
            justify="left",
            wraplength=400,
        )
        model_tip_label.grid(row=row, column=1, sticky="w", padx=16, pady=(0, 8))
        setattr(self, f"{prefix}_ai_model_tip_label", model_tip_label)

        row += 1

        # API Key
        api_key_label = ctk.CTkLabel(parent_frame, text=t("ai_api_key_label"))
        api_key_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)

        api_key_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        api_key_frame.grid(row=row, column=1, sticky="w", padx=16, pady=8)

        api_key_entry = ctk.CTkEntry(api_key_frame, width=350)
        api_key_entry.grid(row=0, column=0, sticky="w")
        setattr(self, f"{prefix}_ai_api_key_entry", api_key_entry)

        # 绑定焦点事件实现自动遮罩
        api_key_entry.bind("<FocusIn>", lambda e, p=prefix: self._on_api_key_focus_in(p))
        api_key_entry.bind("<FocusOut>", lambda e, p=prefix: self._on_api_key_focus_out(p))

        # 初始化当前供应商的 Key (脱敏显示)
        current_key = ""
        if ai_config.get("api_keys"):
            current_key = ai_config["api_keys"].get(current_provider, "")
            if not current_key and len(ai_config["api_keys"]) == 1:
                current_key = list(ai_config["api_keys"].values())[0]
        
        # 记录真实的 key (未遮罩)
        setattr(self, f"{prefix}_real_key", current_key)
        
        if current_key:
            masked_key = self._mask_api_key(current_key)
            api_key_entry.insert(0, masked_key)

        row += 1

        # 管理所有 Key 和 清除所有 Key
        advanced_btn_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        advanced_btn_frame.grid(row=row, column=1, sticky="w", padx=16, pady=(0, 4))

        advanced_btn = ctk.CTkButton(
            advanced_btn_frame,
            text=t("ai_advanced_keys"),
            width=100,
            height=20,
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            hover_color=("gray90", "gray20"),
            command=lambda p=prefix: self._toggle_advanced_keys(p),
        )
        advanced_btn.pack(side="left")
        setattr(self, f"{prefix}_ai_advanced_btn", advanced_btn)

        clear_all_btn = ctk.CTkButton(
            advanced_btn_frame,
            text=t("ai_clear_keys"),
            width=100,
            height=20,
            fg_color="transparent",
            text_color="#ff4d4f",
            hover_color=("gray90", "gray20"),
            command=lambda p=prefix: self._on_clear_all_keys(p),
        )
        clear_all_btn.pack(side="left", padx=(8, 0))

        row += 1

        # 记录文本框应该出现的行号
        setattr(self, f"{prefix}_advanced_keys_row", row)

        api_keys_textbox = ctk.CTkTextbox(
            parent_frame,
            height=80,
            width=600,
            wrap="word",
            activate_scrollbars=True,
        )
        # 默认隐藏高级文本框
        setattr(self, f"{prefix}_ai_api_keys_textbox", api_keys_textbox)

        if ai_config.get("api_keys"):
            api_keys_text = "\n".join(
                [f"{k}={self._mask_api_key(v)}" for k, v in ai_config["api_keys"].items()]
            )
            api_keys_textbox.insert("1.0", api_keys_text)

        row += 1

        # Base URL
        base_url_label = ctk.CTkLabel(parent_frame, text=t("ai_base_url_label"))
        base_url_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        base_url_entry = ctk.CTkEntry(parent_frame, width=450)
        base_url_entry.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_base_url_entry", base_url_entry)
        base_url_value = ai_config.get("base_url") or ""
        
        is_valid_url = (
            base_url_value
            and (base_url_value.startswith("http://") or base_url_value.startswith("https://"))
        )

        if not base_url_value or not is_valid_url:
            provider = current_provider if current_provider in AI_PROVIDER_CONFIGS else "openai"
            base_url_value = AI_PROVIDER_CONFIGS[provider]["base_url"]

        base_url_entry.insert(0, base_url_value)

        row += 1

        # Timeout
        timeout_label = ctk.CTkLabel(parent_frame, text=t("ai_timeout_label"))
        timeout_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        timeout_entry = ctk.CTkEntry(parent_frame, width=150)
        timeout_entry.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_timeout_entry", timeout_entry)
        timeout_entry.insert(0, str(ai_config.get("timeout_seconds", 30)))

        row += 1

        # Max Retries
        retries_label = ctk.CTkLabel(parent_frame, text=t("ai_retries_label"))
        retries_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        retries_entry = ctk.CTkEntry(parent_frame, width=150)
        retries_entry.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_retries_entry", retries_entry)
        retries_entry.insert(0, str(ai_config.get("max_retries", 2)))

        row += 1
        return row + 1

    def _mask_api_key(self, key: str) -> str:
        """对 API Key 进行脱敏处理，保留前4位和后4位"""
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}****{key[-4:]}"

    def _on_api_key_focus_in(self, prefix: str):
        """进入输入框：显示完整 Key"""
        entry = getattr(self, f"{prefix}_ai_api_key_entry")
        real_key = getattr(self, f"{prefix}_real_key", "")
        entry.delete(0, "end")
        entry.insert(0, real_key)

    def _on_api_key_focus_out(self, prefix: str):
        """离开输入框：脱敏显示"""
        entry = getattr(self, f"{prefix}_ai_api_key_entry")
        new_key = entry.get().strip()
        
        # 获取该 provider 现有的真实 key
        real_key = getattr(self, f"{prefix}_real_key", "")
        
        # 如果用户输入的内容与原有的脱敏字符串一致，则不更新
        if new_key == self._mask_api_key(real_key):
            pass
        else:
            setattr(self, f"{prefix}_real_key", new_key)
            real_key = new_key
            
        entry.delete(0, "end")
        entry.insert(0, self._mask_api_key(real_key))

    def _on_clear_all_keys(self, prefix: str):
        """清除该类别下的所有 API Key"""
        from tkinter import messagebox
        if not messagebox.askyesno(t("confirm_title"), t("ai_clear_keys_confirm")):
            return

        # 1. 清除本地缓存
        ai_config = getattr(self, f"{prefix}_ai_config")
        ai_config["api_keys"] = {}
        setattr(self, f"{prefix}_real_key", "")

        # 2. 清除 UI 元素
        getattr(self, f"{prefix}_ai_api_key_entry").delete(0, "end")
        getattr(self, f"{prefix}_ai_api_keys_textbox").delete("1.0", "end")

        if self.on_log_message:
            self.on_log_message(
                "INFO",
                t(
                    "log.ai_keys_cleared",
                    category=t(prefix + "_ai_config_label")
                )
            )

    def _toggle_advanced_keys(self, prefix: str):
        """切换高级 API Keys 文本框的显示/隐藏"""
        textbox = getattr(self, f"{prefix}_ai_api_keys_textbox")
        if textbox.grid_info():
            textbox.grid_remove()
        else:
            # 使用预存的行号进行布局，避免按钮在子框架内导致获取 row 失败
            row = getattr(self, f"{prefix}_advanced_keys_row")
            textbox.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))

    def _get_base_url_value(self, prefix: str) -> str:
        base_url_entry = getattr(self, f"{prefix}_ai_base_url_entry", None)
        if not base_url_entry:
            return ""
        val = base_url_entry.get().strip()
        if val and (val.startswith("http://") or val.startswith("https://")):
            return val
        return ""

    def _show_prefill_menu(self, prefix: str):
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        for key, example in AI_PREFILL_EXAMPLES.items():
            menu.add_command(
                label=example["name"],
                command=lambda e=example, p=prefix: self._apply_prefill(p, e),
            )
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _apply_prefill(self, prefix: str, example: dict):
        provider_combo = getattr(self, f"{prefix}_ai_provider_combo", None)
        if provider_combo:
            provider_combo.set(example["provider"])
            self._on_provider_changed(prefix, example["provider"])

        model_combo = getattr(self, f"{prefix}_ai_model_combo", None)
        if model_combo:
            model_combo.set(example["model"])

        base_url_entry = getattr(self, f"{prefix}_ai_base_url_entry", None)
        if base_url_entry:
            base_url_entry.delete(0, "end")
            base_url_entry.insert(0, example["base_url"])

        tip_label = getattr(self, f"{prefix}_ai_provider_tip_label", None)
        if tip_label and "tip" in example:
            tip_text = t(example["tip"])
            if tip_text != example["tip"]:
                tip_label.configure(text=tip_text)

        if self.on_log_message:
            self.on_log_message("INFO", f"已应用 {example['name']} 预填示例")

    def _on_provider_changed(self, prefix: str, provider: str):
        """供应商选择改变时的回调"""
        self._sync_keys_to_config(prefix)

        if provider not in AI_PROVIDER_CONFIGS:
            return

        config = AI_PROVIDER_CONFIGS[provider]

        model_combo = getattr(self, f"{prefix}_ai_model_combo", None)
        if model_combo:
            model_values = config["models"]
            model_combo.configure(values=model_values)
            if config["model"] and config["model"] in model_values:
                model_combo.set(config["model"])
            elif model_values:
                model_combo.set(model_values[0])
            else:
                model_combo.set("")

        api_key_entry = getattr(self, f"{prefix}_ai_api_key_entry", None)
        if api_key_entry:
            ai_config = getattr(self, f"{prefix}_ai_config", {})
            api_keys = ai_config.get("api_keys", {})
            new_key = api_keys.get(provider, "")
            
            api_key_entry.delete(0, "end")
            if new_key:
                masked = self._mask_api_key(new_key)
                api_key_entry.insert(0, masked)
                setattr(self, f"{prefix}_real_key", new_key)
            else:
                setattr(self, f"{prefix}_real_key", "")

        tip_label = getattr(self, f"{prefix}_ai_provider_tip_label", None)
        if tip_label:
            tip_key = f"ai_tip_{provider}"
            tip_text = t(tip_key)
            tip_label.configure(text=tip_text if tip_text != tip_key else "")

        base_url_entry = getattr(self, f"{prefix}_ai_base_url_entry", None)
        if base_url_entry:
            base_url_entry.delete(0, "end")
            if config.get("base_url"):
                base_url_entry.insert(0, config["base_url"])

    def _sync_keys_to_config(self, prefix: str):
        """同步 UI 中的所有 Key 到本地配置字典中"""
        ai_config = getattr(self, f"{prefix}_ai_config")
        if "api_keys" not in ai_config:
            ai_config["api_keys"] = {}
            
        # 1. 从高级文本框同步
        textbox = getattr(self, f"{prefix}_ai_api_keys_textbox")
        text = textbox.get("1.0", "end-1c").strip()
        for line in text.split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                provider = k.strip()
                val = v.strip()
                
                # 如果输入的是脱敏后的格式，且与现有真实 Key 匹配，则跳过
                existing_real = ai_config["api_keys"].get(provider, "")
                if existing_real and val == self._mask_api_key(existing_real):
                    continue
                
                ai_config["api_keys"][provider] = val
        
        # 2. 从当前 Entry 同步
        prev_provider = getattr(self, f"{prefix}_last_provider", None)
        if prev_provider:
            entry_val = getattr(self, f"{prefix}_ai_api_key_entry").get().strip()
            # 如果输入的是脱敏后的格式，且与现有真实 Key 匹配，则不覆盖
            existing_real = ai_config["api_keys"].get(prev_provider, "")
            
            if entry_val and entry_val != self._mask_api_key(existing_real):
                # 用户输入了新内容（且不是脱敏占位符），更新真实 key
                ai_config["api_keys"][prev_provider] = entry_val
                setattr(self, f"{prefix}_real_key", entry_val)
            elif not entry_val:
                # 用户删空了，清除该 provider 的 key
                if prev_provider in ai_config["api_keys"]:
                    del ai_config["api_keys"][prev_provider]
                setattr(self, f"{prefix}_real_key", "")
        
        current_provider = getattr(self, f"{prefix}_ai_provider_combo").get()
        setattr(self, f"{prefix}_last_provider", current_provider)

    def _get_translation_ai_config(self) -> dict:
        try:
            self._sync_keys_to_config("translation")
            config = {
                "enabled": self.translation_ai_config.get("enabled", True),
                "provider": getattr(self, "translation_ai_provider_combo").get().strip(),
                "model": getattr(self, "translation_ai_model_combo").get().strip(),
                "base_url": self._get_base_url_value("translation"),
                "timeout_seconds": int(getattr(self, "translation_ai_timeout_entry").get().strip() or "30"),
                "max_retries": int(getattr(self, "translation_ai_retries_entry").get().strip() or "2"),
                "api_keys": self.translation_ai_config.get("api_keys", {}),
            }
            return config
        except ValueError as e:
            from core.logger import translate_exception
            raise ValueError(translate_exception("exception.translation_ai_config_format_error", error=str(e)))

    def _get_summary_ai_config(self) -> dict:
        try:
            self._sync_keys_to_config("summary")
            config = {
                "enabled": self.summary_ai_config.get("enabled", True),
                "provider": getattr(self, "summary_ai_provider_combo").get().strip(),
                "model": getattr(self, "summary_ai_model_combo").get().strip(),
                "base_url": self._get_base_url_value("summary"),
                "timeout_seconds": int(getattr(self, "summary_ai_timeout_entry").get().strip() or "30"),
                "max_retries": int(getattr(self, "summary_ai_retries_entry").get().strip() or "2"),
                "api_keys": self.summary_ai_config.get("api_keys", {}),
            }
            return config
        except ValueError as e:
            from core.logger import translate_exception
            raise ValueError(translate_exception("exception.summary_ai_config_format_error", error=str(e)))

    def _on_save_translation_ai(self):
        try:
            config = self._get_translation_ai_config()
            self.translation_ai_config = config
            if self.on_save_translation_ai:
                self.on_save_translation_ai(config)
            # 刷新脱敏显示
            self._on_provider_changed("translation", config["provider"])
        except Exception as e:
            logger.error_i18n("ai_save_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))

    def _on_save_summary_ai(self):
        try:
            config = self._get_summary_ai_config()
            self.summary_ai_config = config
            if self.on_save_summary_ai:
                self.on_save_summary_ai(config)
            # 刷新脱敏显示
            self._on_provider_changed("summary", config["provider"])
        except Exception as e:
            logger.error_i18n("ai_save_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))

    def _on_test_translation_ai(self):
        import threading
        from config.manager import AIConfig
        from core.ai_providers import create_llm_client

        self.translation_test_btn.configure(state="disabled", text=t("ai_testing"))

        def test_in_thread():
            try:
                config_dict = self._get_translation_ai_config()
                ai_config = AIConfig.from_dict(config_dict)
                client = create_llm_client(ai_config)
                test_prompt = "Hello" if ai_config.provider == "google_translate" else t("ai_test_prompt")
                client.generate(prompt=test_prompt, max_tokens=10)

                def on_success():
                    self.translation_test_btn.configure(state="normal", text=t("ai_test_connection"))
                    if self.on_log_message:
                        self.on_log_message("INFO", t("ai_test_success", provider=ai_config.provider, model=ai_config.model))
                self.after(0, on_success)
            except Exception as e:
                error_msg = str(e)
                def on_error():
                    self.translation_test_btn.configure(state="normal", text=t("ai_test_connection"))
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("ai_test_failed", error=error_msg))
                self.after(0, on_error)

        threading.Thread(target=test_in_thread, daemon=True).start()

    def _on_test_summary_ai(self):
        import threading
        from config.manager import AIConfig
        from core.ai_providers import create_llm_client

        self.summary_test_btn.configure(state="disabled", text=t("ai_testing"))

        def test_in_thread():
            try:
                config_dict = self._get_summary_ai_config()
                ai_config = AIConfig.from_dict(config_dict)
                client = create_llm_client(ai_config)
                test_prompt = "Hello" if ai_config.provider == "google_translate" else t("ai_test_prompt")
                client.generate(prompt=test_prompt, max_tokens=10)

                def on_success():
                    self.summary_test_btn.configure(state="normal", text=t("ai_test_connection"))
                    if self.on_log_message:
                        self.on_log_message("INFO", t("ai_test_success", provider=ai_config.provider, model=ai_config.model))
                self.after(0, on_success)
            except Exception as e:
                error_msg = str(e)
                def on_error():
                    self.summary_test_btn.configure(state="normal", text=t("ai_test_connection"))
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("ai_test_failed", error=error_msg))
                self.after(0, on_error)

        threading.Thread(target=test_in_thread, daemon=True).start()
