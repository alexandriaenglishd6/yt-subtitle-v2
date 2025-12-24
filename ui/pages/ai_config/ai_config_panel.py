"""
AI 配置面板组件
可复用的 AI 供应商配置 UI 组件，支持翻译 AI 和摘要 AI
"""

import customtkinter as ctk
from typing import Callable, Optional, Dict
from core.i18n import t
from ui.fonts import body_font
from ui.ai_provider_config import AI_PROVIDER_CONFIGS, AI_PREFILL_EXAMPLES
from core.logger import get_logger

logger = get_logger()


class AIConfigPanel(ctk.CTkFrame):
    """AI 配置面板 - 可复用的 AI 供应商配置组件
    
    包含：Provider 下拉框、Model 下拉框、API Key 输入、Base URL、Timeout、Retries
    """
    
    def __init__(
        self,
        parent,
        config: dict,
        panel_id: str,
        on_config_changed: Optional[Callable[[dict], None]] = None,
        on_log_message: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ):
        """
        Args:
            parent: 父容器
            config: 初始配置字典
            panel_id: 面板标识符（用于区分多个面板）
            on_config_changed: 配置变更回调
            on_log_message: 日志回调
        """
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.config = config.copy() if config else {}
        self.panel_id = panel_id
        self.on_config_changed = on_config_changed
        self.on_log_message = on_log_message
        
        # 初始化 api_keys
        if "api_keys" not in self.config:
            self.config["api_keys"] = {}
        
        # 记录真实 Key（未脱敏）
        self._real_key = ""
        self._last_provider = None
        
        self._build_ui()
    
    # =========================================================================
    # UI 构建
    # =========================================================================
    
    def _build_ui(self):
        """构建 UI"""
        row = 0
        
        # Provider 下拉框
        row = self._build_provider_row(row)
        
        # Model 下拉框
        row = self._build_model_row(row)
        
        # API Key 输入
        row = self._build_api_key_row(row)
        
        # Base URL
        row = self._build_base_url_row(row)
        
        # Timeout
        row = self._build_timeout_row(row)
        
        # Max Retries
        row = self._build_retries_row(row)
    
    def _build_provider_row(self, row: int) -> int:
        """构建 Provider 行"""
        label = ctk.CTkLabel(self, text=t("ai_provider_label"), font=body_font())
        label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        
        self.provider_combo = ctk.CTkComboBox(
            frame,
            values=list(AI_PROVIDER_CONFIGS.keys()),
            width=300,
            font=body_font(),
            dropdown_font=body_font(),
            command=self._on_provider_changed,
        )
        self.provider_combo.grid(row=0, column=0, sticky="w")
        
        # 快速预填按钮
        prefill_btn = ctk.CTkButton(
            frame,
            text=t("ai_prefill_button"),
            width=80,
            font=body_font(),
            command=self._show_prefill_menu,
        )
        prefill_btn.grid(row=0, column=1, padx=(8, 0))
        
        # 设置初始值
        current_provider = self.config.get("provider", "openai")
        self._last_provider = current_provider
        if current_provider in AI_PROVIDER_CONFIGS:
            self.provider_combo.set(current_provider)
        else:
            self.provider_combo.set("openai")
            self._last_provider = "openai"
        
        row += 1
        
        # Provider 提示标签
        self.provider_tip_label = ctk.CTkLabel(
            self,
            text="",
            font=body_font(),
            text_color=("gray50", "gray50"),
            justify="left",
            wraplength=600,
        )
        self.provider_tip_label.grid(row=row, column=1, sticky="w", padx=16, pady=(0, 8))
        
        # 设置初始提示
        tip_key = f"ai_tip_{current_provider}"
        tip_text = t(tip_key)
        if tip_text != tip_key:
            self.provider_tip_label.configure(text=tip_text)
        
        return row + 1
    
    def _build_model_row(self, row: int) -> int:
        """构建 Model 行"""
        label = ctk.CTkLabel(self, text=t("ai_model_label"), font=body_font())
        label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        
        provider = self.config.get("provider", "openai")
        if provider not in AI_PROVIDER_CONFIGS:
            provider = "openai"
        model_values = AI_PROVIDER_CONFIGS[provider]["models"]
        
        self.model_combo = ctk.CTkComboBox(self, values=model_values, width=300, font=body_font(), dropdown_font=body_font())
        self.model_combo.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        
        if self.config.get("model"):
            self.model_combo.set(self.config["model"])
        else:
            default_model = AI_PROVIDER_CONFIGS[provider]["model"]
            self.model_combo.set(default_model)
        
        row += 1
        
        # Model 提示
        self.model_tip_label = ctk.CTkLabel(
            self,
            text=t("ai_model_tip"),
            font=body_font(),
            text_color=("gray50", "gray50"),
            justify="left",
            wraplength=400,
        )
        self.model_tip_label.grid(row=row, column=1, sticky="w", padx=16, pady=(0, 8))
        
        return row + 1
    
    def _build_api_key_row(self, row: int) -> int:
        """构建 API Key 行"""
        label = ctk.CTkLabel(self, text=t("ai_api_key_label"), font=body_font())
        label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        
        self.api_key_entry = ctk.CTkEntry(frame, width=350, font=body_font())
        self.api_key_entry.grid(row=0, column=0, sticky="w")
        
        # 绑定焦点事件
        self.api_key_entry.bind("<FocusIn>", lambda e: self._on_api_key_focus_in())
        self.api_key_entry.bind("<FocusOut>", lambda e: self._on_api_key_focus_out())
        
        # 初始化 Key
        current_provider = self.config.get("provider", "openai")
        current_key = ""
        if self.config.get("api_keys"):
            current_key = self.config["api_keys"].get(current_provider, "")
            if not current_key and len(self.config["api_keys"]) == 1:
                current_key = list(self.config["api_keys"].values())[0]
        
        self._real_key = current_key
        if current_key:
            self.api_key_entry.insert(0, self._mask_api_key(current_key))
        
        row += 1
        
        # 管理按钮行
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=row, column=1, sticky="w", padx=16, pady=(0, 4))
        
        self.advanced_btn = ctk.CTkButton(
            btn_frame,
            text=t("ai_advanced_keys"),
            width=100,
            height=20,
            font=body_font(),
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            hover_color=("gray90", "gray20"),
            command=self._toggle_advanced_keys,
        )
        self.advanced_btn.pack(side="left")
        
        clear_btn = ctk.CTkButton(
            btn_frame,
            text=t("ai_clear_keys"),
            width=100,
            height=20,
            font=body_font(),
            fg_color="transparent",
            text_color="#ff4d4f",
            hover_color=("gray90", "gray20"),
            command=self._on_clear_all_keys,
        )
        clear_btn.pack(side="left", padx=(8, 0))
        
        row += 1
        self._advanced_keys_row = row
        
        # 高级 API Keys 文本框（默认隐藏）
        self.api_keys_textbox = ctk.CTkTextbox(
            self,
            height=100,
            width=600,
            wrap="word",
            font=body_font(),
            activate_scrollbars=True,
        )
        
        # 添加格式提示
        placeholder_lines = [
            f"# {t('ai_advanced_keys_placeholder')}",
            f"# {t('ai_advanced_keys_example')}",
        ]
        if self.config.get("api_keys"):
            keys_text = "\n".join(
                [f"{k}={self._mask_api_key(v)}" for k, v in self.config["api_keys"].items()]
            )
            self.api_keys_textbox.insert("1.0", "\n".join(placeholder_lines) + "\n" + keys_text)
        else:
            self.api_keys_textbox.insert("1.0", "\n".join(placeholder_lines) + "\nopenai=sk-xxx\nkimi=sk-xxx")
        
        return row + 1
    
    def _build_base_url_row(self, row: int) -> int:
        """构建 Base URL 行"""
        label = ctk.CTkLabel(self, text=t("ai_base_url_label"), font=body_font())
        label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        
        self.base_url_entry = ctk.CTkEntry(self, width=450, font=body_font())
        self.base_url_entry.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        
        base_url = self.config.get("base_url") or ""
        is_valid = base_url and (base_url.startswith("http://") or base_url.startswith("https://"))
        
        if not base_url or not is_valid:
            provider = self.config.get("provider", "openai")
            if provider in AI_PROVIDER_CONFIGS:
                base_url = AI_PROVIDER_CONFIGS[provider]["base_url"]
        
        self.base_url_entry.insert(0, base_url)
        return row + 1
    
    def _build_timeout_row(self, row: int) -> int:
        """构建 Timeout 行"""
        label = ctk.CTkLabel(self, text=t("ai_timeout_label"), font=body_font())
        label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        
        self.timeout_entry = ctk.CTkEntry(self, width=150, font=body_font())
        self.timeout_entry.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        self.timeout_entry.insert(0, str(self.config.get("timeout_seconds", 30)))
        return row + 1
    
    def _build_retries_row(self, row: int) -> int:
        """构建 Retries 行"""
        label = ctk.CTkLabel(self, text=t("ai_retries_label"), font=body_font())
        label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        
        self.retries_entry = ctk.CTkEntry(self, width=150, font=body_font())
        self.retries_entry.grid(row=row, column=1, sticky="w", padx=16, pady=8)
        self.retries_entry.insert(0, str(self.config.get("max_retries", 2)))
        return row + 1
    
    # =========================================================================
    # API Key 管理
    # =========================================================================
    
    def _mask_api_key(self, key: str) -> str:
        """脱敏 API Key"""
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}****{key[-4:]}"
    
    def _on_api_key_focus_in(self):
        """进入输入框：保持脱敏显示，不显示完整 Key"""
        # 始终保持脱敏显示，不暴露完整 Key
        pass
    
    def _on_api_key_focus_out(self):
        """离开输入框：检测是否输入了新 Key"""
        new_key = self.api_key_entry.get().strip()
        
        # 如果输入的是脱敏格式（没有改动），则保持原样
        if new_key == self._mask_api_key(self._real_key):
            return
        
        # 如果输入了新的 Key（不是脱敏格式），更新 real_key
        if new_key and "****" not in new_key:
            self._real_key = new_key
            # 重新显示为脱敏格式
            self.api_key_entry.delete(0, "end")
            self.api_key_entry.insert(0, self._mask_api_key(self._real_key))
    
    def _toggle_advanced_keys(self):
        """切换高级 Keys 文本框"""
        if self.api_keys_textbox.grid_info():
            self._sync_keys_to_config()
            self._refresh_api_key_entry()
            self.api_keys_textbox.grid_remove()
        else:
            self.api_keys_textbox.grid(
                row=self._advanced_keys_row, column=0, columnspan=2,
                sticky="w", padx=16, pady=(0, 8)
            )
    
    def _on_clear_all_keys(self):
        """清除所有 Key"""
        from tkinter import messagebox
        if messagebox.askyesno(t("ai_clear_keys"), t("ai_clear_keys_confirm")):
            self.config["api_keys"] = {}
            self._real_key = ""
            self.api_key_entry.delete(0, "end")
            self.api_keys_textbox.delete("1.0", "end")
            
            placeholder_lines = [
                f"# {t('ai_advanced_keys_placeholder')}",
                f"# {t('ai_advanced_keys_example')}",
            ]
            self.api_keys_textbox.insert("1.0", "\n".join(placeholder_lines) + "\nopenai=sk-xxx\nkimi=sk-xxx")
    
    def _refresh_api_key_entry(self):
        """刷新 API Key Entry"""
        provider = self.provider_combo.get()
        current_key = self.config["api_keys"].get(provider, "")
        self._real_key = current_key
        
        self.api_key_entry.delete(0, "end")
        if current_key:
            self.api_key_entry.insert(0, self._mask_api_key(current_key))
    
    def _refresh_advanced_keys_textbox(self):
        """刷新高级 Keys 文本框"""
        self.api_keys_textbox.delete("1.0", "end")
        
        placeholder_lines = [
            f"# {t('ai_advanced_keys_placeholder')}",
            f"# {t('ai_advanced_keys_example')}",
        ]
        if self.config.get("api_keys"):
            keys_text = "\n".join(
                [f"{k}={self._mask_api_key(v)}" for k, v in self.config["api_keys"].items()]
            )
            self.api_keys_textbox.insert("1.0", "\n".join(placeholder_lines) + "\n" + keys_text)
        else:
            self.api_keys_textbox.insert("1.0", "\n".join(placeholder_lines) + "\nopenai=sk-xxx\nkimi=sk-xxx")
    
    def _sync_keys_to_config(self):
        """同步 UI 中的 Key 到配置"""
        if "api_keys" not in self.config:
            self.config["api_keys"] = {}
        
        current_provider = self.provider_combo.get()
        
        # 从高级文本框同步
        text = self.api_keys_textbox.get("1.0", "end-1c").strip()
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                k, v = line.split("=", 1)
                provider = k.strip()
                val = v.strip()
            else:
                provider = current_provider
                val = line
            
            if not val:
                continue
            
            existing = self.config["api_keys"].get(provider, "")
            if existing and val == self._mask_api_key(existing):
                continue
            
            self.config["api_keys"][provider] = val
        
        # 从 Entry 同步
        if self._last_provider:
            entry_val = self.api_key_entry.get().strip()
            
            if not entry_val:
                if self._last_provider in self.config["api_keys"]:
                    del self.config["api_keys"][self._last_provider]
                self._real_key = ""
            elif self._real_key:
                if entry_val != self._mask_api_key(self._real_key):
                    self.config["api_keys"][self._last_provider] = entry_val
                    self._real_key = entry_val
        
        self._last_provider = current_provider
    
    # =========================================================================
    # Provider 切换
    # =========================================================================
    
    def _on_provider_changed(self, provider: str):
        """Provider 切换回调"""
        self._sync_keys_to_config()
        
        if provider not in AI_PROVIDER_CONFIGS:
            return
        
        config = AI_PROVIDER_CONFIGS[provider]
        
        # 更新模型列表
        self.model_combo.configure(values=config["models"])
        self.model_combo.set(config["model"])
        
        # 更新 Base URL
        self.base_url_entry.delete(0, "end")
        self.base_url_entry.insert(0, config["base_url"])
        
        # 更新提示
        tip_key = f"ai_tip_{provider}"
        tip_text = t(tip_key)
        if tip_text != tip_key:
            self.provider_tip_label.configure(text=tip_text)
        else:
            self.provider_tip_label.configure(text="")
        
        # 更新 API Key
        self._refresh_api_key_entry()
        self._last_provider = provider
    
    def _show_prefill_menu(self):
        """显示预填菜单"""
        menu = ctk.CTkToplevel(self)
        menu.title(t("ai_prefill_button"))
        menu.geometry("300x200")
        menu.transient(self)
        menu.grab_set()
        
        for example in AI_PREFILL_EXAMPLES.values():
            btn = ctk.CTkButton(
                menu,
                text=example["name"],
                font=body_font(),
                command=lambda e=example, m=menu: self._apply_prefill(e, m),
            )
            btn.pack(pady=5, padx=10, fill="x")
    
    def _apply_prefill(self, example: dict, menu):
        """应用预填配置"""
        menu.destroy()
        
        if "provider" in example:
            self.provider_combo.set(example["provider"])
            self._on_provider_changed(example["provider"])
        
        if "model" in example:
            self.model_combo.set(example["model"])
        
        if "base_url" in example:
            self.base_url_entry.delete(0, "end")
            self.base_url_entry.insert(0, example["base_url"])
        
        if self.on_log_message:
            self.on_log_message("INFO", t("ai_example_applied", name=example["name"]))
    
    # =========================================================================
    # 配置获取
    # =========================================================================
    
    def get_config(self) -> dict:
        """获取当前配置"""
        self._sync_keys_to_config()
        
        base_url = self.base_url_entry.get().strip()
        if base_url == "":
            base_url = None
        
        return {
            "enabled": self.config.get("enabled", True),
            "provider": self.provider_combo.get().strip(),
            "model": self.model_combo.get().strip(),
            "base_url": base_url,
            "timeout_seconds": int(self.timeout_entry.get().strip() or "30"),
            "max_retries": int(self.retries_entry.get().strip() or "2"),
            "api_keys": self.config.get("api_keys", {}),
        }
    
    def refresh_display(self):
        """刷新显示（保存后调用）"""
        self._refresh_advanced_keys_textbox()
        self._refresh_api_key_entry()
