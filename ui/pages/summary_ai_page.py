"""
摘要 AI 配置页面
"""
import customtkinter as ctk
from typing import Callable, Optional
from ui.i18n_manager import t
from ui.fonts import title_font, heading_font, body_font
from core.logger import get_logger

logger = get_logger()


class SummaryAIPage(ctk.CTkFrame):
    """摘要 AI 配置页面"""
    
    def __init__(
        self,
        parent,
        summary_ai_config: Optional[dict] = None,
        on_save_ai_config: Optional[Callable[[dict], None]] = None,
        on_log_message: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.summary_ai_config = summary_ai_config or {}
        self.on_save_ai_config = on_save_ai_config
        self.on_log_message = on_log_message
        self.grid_columnconfigure(0, weight=1)
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
            text=t("summary_ai_config_label"),
            font=title_font(weight="bold")
        )
        title.pack(pady=(0, 24))
        
        # AI 配置区域
        ai_frame = ctk.CTkFrame(scroll_frame)
        ai_frame.pack(fill="x", pady=(0, 16))
        ai_frame.grid_columnconfigure(1, weight=1)
        
        # 构建 AI 配置字段
        self._build_ai_config_fields(ai_frame, self.summary_ai_config)
        
        # 保存按钮
        btn_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=0, pady=(0, 16))
        
        self.save_btn = ctk.CTkButton(
            btn_frame,
            text=t("ai_save"),
            command=self._on_save,
            width=120
        )
        self.save_btn.pack(side="left", padx=16, pady=8)
    
    def _build_ai_config_fields(self, parent_frame, ai_config: dict):
        """构建 AI 配置字段"""
        row = 0
        
        # Provider
        provider_label = ctk.CTkLabel(parent_frame, text=t("ai_provider_label"))
        provider_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.provider_entry = ctk.CTkEntry(parent_frame, width=200)
        self.provider_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        if ai_config.get("provider"):
            self.provider_entry.insert(0, ai_config["provider"])
        
        row += 1
        
        # Model
        model_label = ctk.CTkLabel(parent_frame, text=t("ai_model_label"))
        model_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.model_entry = ctk.CTkEntry(parent_frame, width=200)
        self.model_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        if ai_config.get("model"):
            self.model_entry.insert(0, ai_config["model"])
        
        row += 1
        
        # Base URL
        base_url_label = ctk.CTkLabel(parent_frame, text=t("ai_base_url_label"))
        base_url_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.base_url_entry = ctk.CTkEntry(parent_frame, width=200)
        self.base_url_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        if ai_config.get("base_url"):
            self.base_url_entry.insert(0, ai_config["base_url"])
        
        row += 1
        
        # Timeout
        timeout_label = ctk.CTkLabel(parent_frame, text=t("ai_timeout_label"))
        timeout_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.timeout_entry = ctk.CTkEntry(parent_frame, width=200)
        self.timeout_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        if ai_config.get("timeout_seconds"):
            self.timeout_entry.insert(0, str(ai_config["timeout_seconds"]))
        else:
            self.timeout_entry.insert(0, "30")
        
        row += 1
        
        # Max Retries
        retries_label = ctk.CTkLabel(parent_frame, text=t("ai_retries_label"))
        retries_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        self.retries_entry = ctk.CTkEntry(parent_frame, width=200)
        self.retries_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        if ai_config.get("max_retries"):
            self.retries_entry.insert(0, str(ai_config["max_retries"]))
        else:
            self.retries_entry.insert(0, "2")
        
        row += 1
        
        # API Keys
        api_keys_label = ctk.CTkLabel(parent_frame, text=t("ai_api_keys_label"))
        api_keys_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 4))
        self.api_keys_textbox = ctk.CTkTextbox(parent_frame, height=80, wrap="word")
        self.api_keys_textbox.grid(row=row+1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        if ai_config.get("api_keys"):
            api_keys_text = "\n".join([f"{k}={v}" for k, v in ai_config["api_keys"].items()])
            self.api_keys_textbox.insert("1.0", api_keys_text)
    
    def _on_save(self):
        """保存 AI 配置"""
        try:
            ai_config = {
                "provider": self.provider_entry.get().strip(),
                "model": self.model_entry.get().strip(),
                "base_url": self.base_url_entry.get().strip() or None,
                "timeout_seconds": int(self.timeout_entry.get().strip() or "30"),
                "max_retries": int(self.retries_entry.get().strip() or "2"),
                "api_keys": {}
            }
            
            # 解析 API Keys
            api_keys_text = self.api_keys_textbox.get("1.0", "end-1c").strip()
            for line in api_keys_text.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    ai_config["api_keys"][key.strip()] = value.strip()
            
            if self.on_save_ai_config:
                self.on_save_ai_config(ai_config)
                if self.on_log_message:
                    self.on_log_message("INFO", t("ai_save_success"))
        except ValueError as e:
            logger.error_i18n("ai_config_format_error", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", f"{t('ai_save_failed')}: {e}")
        except Exception as e:
            logger.error_i18n("ai_save_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))

