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
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",  # 官方 API 地址
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]
    },
    "anthropic": {
        "model": "claude-3-5-sonnet-20241022",
        "base_url": "https://api.anthropic.com",  # 官方 API 地址
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]
    },
    "google_translate": {
        "model": "google_translate_free",
        "base_url": "",  # Google 翻译免费版不需要 API 地址
        "models": [
            "google_translate_free"
        ],
        "requires_api_key": False  # 标记不需要 API Key
    }
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
        **kwargs
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
            font=title_font(weight="bold")
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
            font=heading_font(weight="bold")
        )
        translation_ai_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        # 翻译 AI 配置字段
        last_row = self._build_ai_config_fields(translation_ai_frame, self.translation_ai_config, "translation", start_row=1)
        
        # 翻译 AI 保存和测试按钮
        translation_btn_frame = ctk.CTkFrame(translation_ai_frame, fg_color="transparent")
        translation_btn_frame.grid(row=last_row+1, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16))
        
        self.translation_save_btn = ctk.CTkButton(
            translation_btn_frame,
            text=t("ai_save_translation"),
            command=self._on_save_translation_ai,
            width=120
        )
        self.translation_save_btn.pack(side="left", padx=(0, 8))
        
        self.translation_test_btn = ctk.CTkButton(
            translation_btn_frame,
            text=t("ai_test_connection"),
            command=self._on_test_translation_ai,
            width=120,
            fg_color="gray50",
            hover_color="gray40"
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
            font=heading_font(weight="bold")
        )
        summary_ai_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))
        
        # 摘要 AI 配置字段
        last_row = self._build_ai_config_fields(summary_ai_frame, self.summary_ai_config, "summary", start_row=1)
        
        # 摘要 AI 保存和测试按钮
        summary_btn_frame = ctk.CTkFrame(summary_ai_frame, fg_color="transparent")
        summary_btn_frame.grid(row=last_row+1, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 16))
        
        self.summary_save_btn = ctk.CTkButton(
            summary_btn_frame,
            text=t("ai_save_summary"),
            command=self._on_save_summary_ai,
            width=120
        )
        self.summary_save_btn.pack(side="left", padx=(0, 8))
        
        self.summary_test_btn = ctk.CTkButton(
            summary_btn_frame,
            text=t("ai_test_connection"),
            command=self._on_test_summary_ai,
            width=120,
            fg_color="gray50",
            hover_color="gray40"
        )
        self.summary_test_btn.pack(side="left", padx=(0, 8))
    
    def _build_ai_config_fields(self, parent_frame, ai_config: dict, prefix: str, start_row: int = 1):
        """构建 AI 配置字段（辅助方法，用于翻译和摘要配置）
        
        Args:
            parent_frame: 父框架
            ai_config: AI 配置字典
            prefix: 字段前缀（"translation" 或 "summary"）
            start_row: 起始行号
        """
        row = start_row
        
        # Provider (下拉框)
        provider_label = ctk.CTkLabel(parent_frame, text=t("ai_provider_label"))
        provider_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        provider_combo = ctk.CTkComboBox(
            parent_frame,
            values=list(AI_PROVIDER_CONFIGS.keys()),
            width=200,
            command=lambda value, p=prefix: self._on_provider_changed(p, value)
        )
        provider_combo.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        # 绑定点击事件，使整个下拉框区域都可以点击打开下拉菜单
        def on_provider_click(event):
            try:
                provider_combo._open_dropdown_menu()
            except:
                pass  # 如果方法不存在，忽略错误
        provider_combo.bind("<Button-1>", on_provider_click)
        setattr(self, f"{prefix}_ai_provider_combo", provider_combo)
        current_provider = ai_config.get("provider", "openai")
        if current_provider in AI_PROVIDER_CONFIGS:
            provider_combo.set(current_provider)
        else:
            provider_combo.set("openai")  # 默认值
        
        row += 1
        
        # Model (下拉框)
        model_label = ctk.CTkLabel(parent_frame, text=t("ai_model_label"))
        model_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        # 获取当前供应商的模型列表
        provider = current_provider if current_provider in AI_PROVIDER_CONFIGS else "openai"
        model_values = AI_PROVIDER_CONFIGS[provider]["models"]
        model_combo = ctk.CTkComboBox(
            parent_frame,
            values=model_values,
            width=200
        )
        model_combo.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        # 绑定点击事件，使整个下拉框区域都可以点击打开下拉菜单
        def on_model_click(event):
            try:
                model_combo._open_dropdown_menu()
            except:
                pass  # 如果方法不存在，忽略错误
        model_combo.bind("<Button-1>", on_model_click)
        setattr(self, f"{prefix}_ai_model_combo", model_combo)
        if ai_config.get("model") and ai_config.get("model") in model_values:
            model_combo.set(ai_config["model"])
        else:
            # 如果没有配置或配置的模型不在列表中，使用当前供应商的默认模型
            default_model = AI_PROVIDER_CONFIGS[provider]["model"]
            model_combo.set(default_model)
        
        row += 1
        
        # Base URL
        base_url_label = ctk.CTkLabel(parent_frame, text=t("ai_base_url_label"))
        base_url_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        base_url_entry = ctk.CTkEntry(parent_frame, width=200)
        base_url_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_base_url_entry", base_url_entry)
        # 获取 base_url，如果为 None、空字符串或无效值，使用默认值
        base_url_value = ai_config.get("base_url")
        # 确保 base_url_value 是字符串类型
        if base_url_value is None:
            base_url_value = ""
        elif not isinstance(base_url_value, str):
            # 如果不是字符串（可能是数字或其他类型），视为无效值
            base_url_value = ""
        
        # 检查是否为有效 URL（简单检查：包含 http:// 或 https://）
        is_valid_url = base_url_value and isinstance(base_url_value, str) and (
            base_url_value.strip().startswith("http://") or 
            base_url_value.strip().startswith("https://")
        )
        
        # 如果为空字符串或无效值，使用当前供应商的默认 API 地址
        if not base_url_value or base_url_value.strip() == "" or not is_valid_url:
            provider = current_provider if current_provider in AI_PROVIDER_CONFIGS else "openai"
            base_url_value = AI_PROVIDER_CONFIGS[provider]["base_url"]
        
        # 确保 base_url_value 是有效的字符串后再插入
        if base_url_value and isinstance(base_url_value, str):
            base_url_entry.insert(0, base_url_value)
        
        row += 1
        
        # Timeout
        timeout_label = ctk.CTkLabel(parent_frame, text=t("ai_timeout_label"))
        timeout_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        timeout_entry = ctk.CTkEntry(parent_frame, width=200)
        timeout_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_timeout_entry", timeout_entry)
        if ai_config.get("timeout_seconds"):
            timeout_entry.insert(0, str(ai_config["timeout_seconds"]))
        else:
            timeout_entry.insert(0, "30")
        
        row += 1
        
        # Max Retries
        retries_label = ctk.CTkLabel(parent_frame, text=t("ai_retries_label"))
        retries_label.grid(row=row, column=0, sticky="w", padx=16, pady=8)
        retries_entry = ctk.CTkEntry(parent_frame, width=200)
        retries_entry.grid(row=row, column=1, sticky="ew", padx=16, pady=8)
        setattr(self, f"{prefix}_ai_retries_entry", retries_entry)
        if ai_config.get("max_retries"):
            retries_entry.insert(0, str(ai_config["max_retries"]))
        else:
            retries_entry.insert(0, "2")
        
        row += 1
        
        # API Keys
        api_keys_label = ctk.CTkLabel(parent_frame, text=t("ai_api_keys_label"))
        api_keys_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 4))
        api_keys_textbox = ctk.CTkTextbox(parent_frame, height=80, wrap="word")
        api_keys_textbox.grid(row=row+1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        setattr(self, f"{prefix}_ai_api_keys_textbox", api_keys_textbox)
        if ai_config.get("api_keys"):
            api_keys_text = "\n".join([f"{k}={v}" for k, v in ai_config["api_keys"].items()])
            api_keys_textbox.insert("1.0", api_keys_text)
        
        # 返回最后使用的行号
        return row + 1
    
    def _get_base_url_value(self, prefix: str) -> str:
        """获取有效的 base_url 值
        
        Args:
            prefix: 字段前缀（"translation" 或 "summary"）
        
        Returns:
            有效的 base_url 字符串，如果无效则返回空字符串
        """
        base_url_entry = getattr(self, f"{prefix}_ai_base_url_entry", None)
        if not base_url_entry:
            return ""
        
        base_url_value = base_url_entry.get().strip()
        
        # 检查是否为有效 URL（简单检查：包含 http:// 或 https://）
        if base_url_value and (
            base_url_value.startswith("http://") or 
            base_url_value.startswith("https://")
        ):
            return base_url_value
        
        # 如果无效，返回空字符串（表示使用官方 API）
        return ""
    
    def _on_provider_changed(self, prefix: str, provider: str):
        """供应商选择改变时的回调
        
        Args:
            prefix: 字段前缀（"translation" 或 "summary"）
            provider: 选择的供应商名称
        """
        if provider not in AI_PROVIDER_CONFIGS:
            return
        
        config = AI_PROVIDER_CONFIGS[provider]
        
        # 更新模型下拉框的选项和默认值
        model_combo = getattr(self, f"{prefix}_ai_model_combo", None)
        if model_combo:
            # 更新模型列表
            model_values = config["models"]
            model_combo.configure(values=model_values)
            # 设置默认模型
            if config["model"] and config["model"] in model_values:
                model_combo.set(config["model"])
            elif model_values:
                model_combo.set(model_values[0])
        
        # 更新 Base URL：清空并自动填充新供应商的官方 API 地址
        base_url_entry = getattr(self, f"{prefix}_ai_base_url_entry", None)
        if base_url_entry:
            base_url_entry.delete(0, "end")
            # 自动填充新供应商的官方 API 地址
            base_url_value = config.get("base_url", "")
            if base_url_value:
                base_url_entry.insert(0, base_url_value)
            # 用户仍然可以手动修改这个地址
    
    def _get_translation_ai_config(self) -> dict:
        """获取翻译 AI 配置"""
        try:
            translation_ai_config = {
                "enabled": self.translation_ai_config.get("enabled", True),  # 保持原有配置
                "provider": getattr(self, "translation_ai_provider_combo").get().strip(),
                "model": getattr(self, "translation_ai_model_combo").get().strip(),
                "base_url": self._get_base_url_value("translation"),
                "timeout_seconds": int(getattr(self, "translation_ai_timeout_entry").get().strip() or "30"),
                "max_retries": int(getattr(self, "translation_ai_retries_entry").get().strip() or "2"),
                "api_keys": {}
            }
            
            # 解析翻译 API Keys
            translation_api_keys_text = getattr(self, "translation_ai_api_keys_textbox").get("1.0", "end-1c").strip()
            for line in translation_api_keys_text.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    translation_ai_config["api_keys"][key.strip()] = value.strip()
            
            return translation_ai_config
        except ValueError as e:
            raise ValueError(f"翻译 AI 配置格式错误: {e}")
    
    def _get_summary_ai_config(self) -> dict:
        """获取摘要 AI 配置"""
        try:
            summary_ai_config = {
                "enabled": self.summary_ai_config.get("enabled", True),  # 保持原有配置
                "provider": getattr(self, "summary_ai_provider_combo").get().strip(),
                "model": getattr(self, "summary_ai_model_combo").get().strip(),
                "base_url": self._get_base_url_value("summary"),
                "timeout_seconds": int(getattr(self, "summary_ai_timeout_entry").get().strip() or "30"),
                "max_retries": int(getattr(self, "summary_ai_retries_entry").get().strip() or "2"),
                "api_keys": {}
            }
            
            # 解析摘要 API Keys
            summary_api_keys_text = getattr(self, "summary_ai_api_keys_textbox").get("1.0", "end-1c").strip()
            for line in summary_api_keys_text.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    summary_ai_config["api_keys"][key.strip()] = value.strip()
            
            return summary_ai_config
        except ValueError as e:
            raise ValueError(f"摘要 AI 配置格式错误: {e}")
    
    def _on_save_translation_ai(self):
        """保存翻译 AI 配置"""
        try:
            translation_ai_config = self._get_translation_ai_config()
            if self.on_save_translation_ai:
                self.on_save_translation_ai(translation_ai_config)
            if self.on_log_message:
                self.on_log_message("INFO", t("ai_save_translation_success"))
        except ValueError as e:
            logger.error(f"翻译 AI 配置格式错误: {e}")
            if self.on_log_message:
                self.on_log_message("ERROR", f"{t('ai_save_failed')}: {e}")
        except Exception as e:
            logger.error_i18n("ai_save_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))
    
    def _on_save_summary_ai(self):
        """保存摘要 AI 配置"""
        try:
            summary_ai_config = self._get_summary_ai_config()
            if self.on_save_summary_ai:
                self.on_save_summary_ai(summary_ai_config)
            if self.on_log_message:
                self.on_log_message("INFO", t("ai_save_summary_success"))
        except ValueError as e:
            logger.error_i18n("ai_config_format_error", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", f"{t('ai_save_failed')}: {e}")
        except Exception as e:
            logger.error_i18n("ai_save_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))
    
    def _on_test_translation_ai(self):
        """测试翻译 AI 连通性"""
        import threading
        from config.manager import AIConfig
        from core.ai_providers import create_llm_client
        from core.llm_client import LLMException
        
        # 禁用测试按钮
        self.translation_test_btn.configure(state="disabled", text=t("ai_testing"))
        
        def test_in_thread():
            try:
                # 获取当前配置
                translation_ai_config = self._get_translation_ai_config()
                ai_config = AIConfig.from_dict(translation_ai_config)
                
                # 创建客户端并测试
                client = create_llm_client(ai_config)
                
                # 发送一个简单的测试请求
                # 对于 Google 翻译，使用简单的英文文本更合适
                test_prompt = "测试" if ai_config.provider != "google_translate" else "Hello"
                result = client.generate(
                    prompt=test_prompt,
                    max_tokens=10
                )
                
                # 测试成功
                def on_success():
                    self.translation_test_btn.configure(
                        state="normal",
                        text=t("ai_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("INFO", t("ai_test_success", provider=ai_config.provider, model=ai_config.model))
                
                self.after(0, on_success)
                
            except LLMException as e:
                error_msg = str(e)
                def on_error():
                    self.translation_test_btn.configure(
                        state="normal",
                        text=t("ai_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("ai_test_failed", error=error_msg))
                
                self.after(0, on_error)
            except ValueError as e:
                error_msg = str(e)
                def on_error():
                    self.translation_test_btn.configure(
                        state="normal",
                        text=t("ai_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("ERROR", f"{t('ai_test_failed')}: {error_msg}")
                
                self.after(0, on_error)
            except Exception as e:
                error_msg = str(e)
                def on_error():
                    self.translation_test_btn.configure(
                        state="normal",
                        text=t("ai_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("ai_test_failed", error=error_msg))
                
                self.after(0, on_error)
        
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()
    
    def _on_test_summary_ai(self):
        """测试摘要 AI 连通性"""
        import threading
        from config.manager import AIConfig
        from core.ai_providers import create_llm_client
        from core.llm_client import LLMException
        
        # 禁用测试按钮
        self.summary_test_btn.configure(state="disabled", text=t("ai_testing"))
        
        def test_in_thread():
            try:
                # 获取当前配置
                summary_ai_config = self._get_summary_ai_config()
                ai_config = AIConfig.from_dict(summary_ai_config)
                
                # 创建客户端并测试
                client = create_llm_client(ai_config)
                
                # 发送一个简单的测试请求
                # 对于 Google 翻译，使用简单的英文文本更合适
                test_prompt = "测试" if ai_config.provider != "google_translate" else "Hello"
                result = client.generate(
                    prompt=test_prompt,
                    max_tokens=10
                )
                
                # 测试成功
                def on_success():
                    self.summary_test_btn.configure(
                        state="normal",
                        text=t("ai_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("INFO", t("ai_test_success", provider=ai_config.provider, model=ai_config.model))
                
                self.after(0, on_success)
                
            except LLMException as e:
                error_msg = str(e)
                def on_error():
                    self.summary_test_btn.configure(
                        state="normal",
                        text=t("ai_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("ai_test_failed", error=error_msg))
                
                self.after(0, on_error)
            except ValueError as e:
                error_msg = str(e)
                def on_error():
                    self.summary_test_btn.configure(
                        state="normal",
                        text=t("ai_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("ERROR", f"{t('ai_test_failed')}: {error_msg}")
                
                self.after(0, on_error)
            except Exception as e:
                error_msg = str(e)
                def on_error():
                    self.summary_test_btn.configure(
                        state="normal",
                        text=t("ai_test_connection")
                    )
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("ai_test_failed", error=error_msg))
                
                self.after(0, on_error)
        
        thread = threading.Thread(target=test_in_thread, daemon=True)
        thread.start()

