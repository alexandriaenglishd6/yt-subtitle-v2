"""
翻译&摘要页面
包含翻译 AI 和摘要 AI 配置
"""

import customtkinter as ctk
from typing import Callable, Optional
import threading
from core.i18n import t
from ui.fonts import title_font, heading_font, body_font
from ui.pages.ai_config import AIConfigPanel
from core.logger import get_logger

logger = get_logger()


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

        self.translation_ai_config = translation_ai_config or {}
        self.summary_ai_config = summary_ai_config or {}
        self.on_save_translation_ai = on_save_translation_ai
        self.on_save_summary_ai = on_save_summary_ai
        self.on_log_message = on_log_message

        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        # 主滚动容器
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # 页面标题（居中显示）
        title_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=t("translation_summary_page_title"),
            font=title_font(),
            anchor="center",
        )
        title_label.pack(fill="x", padx=16, pady=(16, 8))

        # =========================================================================
        # 翻译 AI 配置区域
        # =========================================================================
        translation_frame = ctk.CTkFrame(self.scrollable_frame)
        translation_frame.pack(fill="x", padx=16, pady=8)

        translation_title = ctk.CTkLabel(
            translation_frame,
            text=t("translation_ai_config_label"),
            font=heading_font(),
        )
        translation_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))

        # 使用 AIConfigPanel 组件
        self.translation_panel = AIConfigPanel(
            translation_frame,
            config=self.translation_ai_config,
            panel_id="translation",
            on_log_message=self.on_log_message,
        )
        self.translation_panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

        # 翻译 AI 按钮
        translation_btn_frame = ctk.CTkFrame(translation_frame, fg_color="transparent")
        translation_btn_frame.grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 16))

        save_translation_btn = ctk.CTkButton(
            translation_btn_frame,
            text=t("ai_save_translation"),
            font=body_font(),
            command=self._on_save_translation_ai,
        )
        save_translation_btn.pack(side="left", padx=(0, 8))

        test_translation_btn = ctk.CTkButton(
            translation_btn_frame,
            text=t("ai_test_connection"),
            font=body_font(),
            command=self._on_test_translation_ai,
        )
        test_translation_btn.pack(side="left")

        # =========================================================================
        # 摘要 AI 配置区域
        # =========================================================================
        summary_frame = ctk.CTkFrame(self.scrollable_frame)
        summary_frame.pack(fill="x", padx=16, pady=8)

        summary_title = ctk.CTkLabel(
            summary_frame,
            text=t("summary_ai_config_label"),
            font=heading_font(),
        )
        summary_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8))

        # 使用 AIConfigPanel 组件
        self.summary_panel = AIConfigPanel(
            summary_frame,
            config=self.summary_ai_config,
            panel_id="summary",
            on_log_message=self.on_log_message,
        )
        self.summary_panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=4)

        # 摘要 AI 按钮
        summary_btn_frame = ctk.CTkFrame(summary_frame, fg_color="transparent")
        summary_btn_frame.grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 16))

        save_summary_btn = ctk.CTkButton(
            summary_btn_frame,
            text=t("ai_save_summary"),
            font=body_font(),
            command=self._on_save_summary_ai,
        )
        save_summary_btn.pack(side="left", padx=(0, 8))

        test_summary_btn = ctk.CTkButton(
            summary_btn_frame,
            text=t("ai_test_connection"),
            font=body_font(),
            command=self._on_test_summary_ai,
        )
        test_summary_btn.pack(side="left")

    # =========================================================================
    # 保存回调
    # =========================================================================

    def _on_save_translation_ai(self):
        """保存翻译 AI 配置"""
        try:
            config = self.translation_panel.get_config()
            self.translation_ai_config = config
            if self.on_save_translation_ai:
                self.on_save_translation_ai(config)
            self.translation_panel.refresh_display()
        except Exception as e:
            logger.error_i18n("ai_save_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))

    def _on_save_summary_ai(self):
        """保存摘要 AI 配置"""
        try:
            config = self.summary_panel.get_config()
            self.summary_ai_config = config
            if self.on_save_summary_ai:
                self.on_save_summary_ai(config)
            self.summary_panel.refresh_display()
        except Exception as e:
            logger.error_i18n("ai_save_failed", error=str(e))
            if self.on_log_message:
                self.on_log_message("ERROR", t("ai_save_failed", error=str(e)))

    # =========================================================================
    # 测试连接
    # =========================================================================

    def _on_test_translation_ai(self):
        """测试翻译 AI 连接"""
        if self.on_log_message:
            self.on_log_message("INFO", t("ai_testing"))

        config = self.translation_panel.get_config()
        provider = config.get("provider", "unknown")

        def test_in_thread():
            try:
                from core.ai_providers import create_ai_client

                client = create_ai_client(config)
                result = client.generate("Hello, please respond with 'OK'.")
                
                # LLMResult 对象需要访问 .text 属性
                response_text = result.text if hasattr(result, 'text') else str(result)
                
                # 获取 provider 和 model 信息
                result_provider = getattr(result, 'provider', provider)
                result_model = getattr(result, 'model', config.get('model', 'unknown'))

                def on_success():
                    if self.on_log_message:
                        # 谷歌翻译已经显示了专门的测试消息，跳过通用成功消息
                        if result_provider == "google_translate":
                            pass  # 不显示重复消息
                        else:
                            self.on_log_message("INFO", t("ai_test_success", response=f"{result_provider}/{result_model}: {response_text[:50]}"))

                self.after(0, on_success)
            except Exception as e:
                error_msg = str(e)  # 在异常处理块中立即捕获
                def on_error(msg=error_msg):
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("ai_test_failed", error=msg))

                self.after(0, on_error)

        threading.Thread(target=test_in_thread, daemon=True).start()

    def _on_test_summary_ai(self):
        """测试摘要 AI 连接"""
        if self.on_log_message:
            self.on_log_message("INFO", t("ai_testing"))

        config = self.summary_panel.get_config()
        provider = config.get("provider", "unknown")

        def test_in_thread():
            try:
                from core.ai_providers import create_ai_client

                client = create_ai_client(config)
                result = client.generate("Hello, please respond with 'OK'.")
                
                # LLMResult 对象需要访问 .text 属性
                response_text = result.text if hasattr(result, 'text') else str(result)
                
                # 获取 provider 和 model 信息
                result_provider = getattr(result, 'provider', provider)
                result_model = getattr(result, 'model', config.get('model', 'unknown'))

                def on_success():
                    if self.on_log_message:
                        # 谷歌翻译已经显示了专门的测试消息，跳过通用成功消息
                        if result_provider == "google_translate":
                            pass  # 不显示重复消息
                        else:
                            self.on_log_message("INFO", t("ai_test_success", response=f"{result_provider}/{result_model}: {response_text[:50]}"))

                self.after(0, on_success)
            except Exception as e:
                error_msg = str(e)  # 在异常处理块中立即捕获
                def on_error(msg=error_msg):
                    if self.on_log_message:
                        self.on_log_message("ERROR", t("ai_test_failed", error=msg))

                self.after(0, on_error)

        threading.Thread(target=test_in_thread, daemon=True).start()
