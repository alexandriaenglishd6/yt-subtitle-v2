"""
顶部工具栏组件
包含应用标题、运行状态、语言/主题切换、功能按钮
"""

import customtkinter as ctk
from typing import Callable, Optional
from core.i18n import t, get_language
from ui.themes import ThemeName, get_theme
from ui.fonts import title_font, body_font


class Toolbar(ctk.CTkFrame):
    """顶部工具栏"""

    def __init__(
        self,
        parent,
        current_mode: str = "",
        running_status: str = "",
        current_theme: ThemeName = "light",
        on_language_changed: Optional[Callable[[str], None]] = None,
        on_theme_changed: Optional[Callable[[str], None]] = None,
        on_open_output: Optional[Callable[[], None]] = None,
        on_open_config: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(parent, height=50, corner_radius=0, **kwargs)
        self.current_mode = current_mode
        self.running_status = running_status
        self.current_theme = current_theme
        self.on_language_changed = on_language_changed
        self.on_theme_changed = on_theme_changed
        self.on_open_output = on_open_output
        self.on_open_config = on_open_config
        self._refreshing_theme_combo = False
        self._build_ui()

    def _build_ui(self):
        """构建 UI"""
        self.grid_columnconfigure(1, weight=1)

        # 左侧：应用标题（仅显示当前模式，蓝色）
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=16, pady=8, sticky="w")

        tokens = get_theme(self.current_theme)
        self.title_label = ctk.CTkLabel(
            title_frame,
            text=self.current_mode,
            font=title_font(weight="bold"),
            text_color=(tokens.accent, tokens.accent),
        )
        self.title_label._is_top_title = True  # 标记为顶部标题，防止被主题引擎覆盖为普通文本颜色
        self.title_label.pack(side="left", padx=8)

        # 右侧：功能按钮区域
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=0, column=1, padx=16, pady=8, sticky="e")

        # GitHub 开源地址 + 版本号（合并为一个按钮）
        self.github_btn = ctk.CTkButton(
            button_frame,
            text=f"{t('github_link_text')} | {t('version_text')}",
            width=180,
            font=body_font(),
            fg_color=("gray85", "gray25"),
            hover_color=("gray75", "gray35"),
            text_color=("#0066CC", "#66B3FF"),
            command=self._on_github_click,
        )
        self.github_btn.pack(side="left", padx=4)

        # UI 语言切换
        lang_values = [t("language_zh"), t("language_en")]
        self.lang_combo = ctk.CTkComboBox(
            button_frame,
            values=lang_values,
            width=100,
            font=body_font(),
            dropdown_font=body_font(),
            command=self._on_language_changed,
        )
        current_lang = get_language()
        if current_lang == "zh-CN":
            self.lang_combo.set(t("language_zh"))
        else:
            self.lang_combo.set(t("language_en"))
        self.lang_combo.pack(side="left", padx=4)

        # 主题切换
        theme_values = [
            t("theme_light"),
            t("theme_light_gray"),
            t("theme_dark_gray"),
            t("theme_claude_warm"),
        ]
        self.theme_combo = ctk.CTkComboBox(
            button_frame, values=theme_values, width=120, font=body_font(), dropdown_font=body_font(), command=self._on_theme_changed
        )
        current_theme_display = t(f"theme_{self.current_theme}")
        self.theme_combo.set(current_theme_display)
        self.theme_combo.pack(side="left", padx=4)

        # 打开输出文件夹按钮
        self.open_output_btn = ctk.CTkButton(
            button_frame,
            text=t("open_output_folder"),
            width=120,
            font=body_font(),
            command=self._on_open_output_folder,
        )
        self.open_output_btn.pack(side="left", padx=4)

        # 打开失败链接按钮
        self.open_failed_links_btn = ctk.CTkButton(
            button_frame,
            text=t("open_failed_links"),
            width=120,
            font=body_font(),
            command=self._on_open_failed_links,
        )
        self.open_failed_links_btn.pack(side="left", padx=4)

    def _on_github_click(self, event=None):
        """点击 GitHub 链接"""
        import webbrowser
        webbrowser.open("https://github.com/alexandriaenglishd6/yt-subtitle-v2")

    def _on_language_changed(self, value: str):
        """语言切换回调"""
        if self.on_language_changed:
            self.on_language_changed(value)

    def _on_theme_changed(self, value: str):
        """主题切换回调"""
        if self._refreshing_theme_combo:
            return
        if self.on_theme_changed:
            self.on_theme_changed(value)

    def _on_open_output_folder(self):
        """打开输出文件夹"""
        if self.on_open_output:
            self.on_open_output()

    def _on_open_failed_links(self):
        """打开失败链接"""
        if self.on_open_config:  # 复用回调参数名，但功能已改变
            self.on_open_config()

    def update_title(self, mode: str):
        """更新标题"""
        self.current_mode = mode
        if hasattr(self, "title_label"):
            tokens = get_theme(self.current_theme)
            self.title_label.configure(
                text=mode,
                text_color=(tokens.accent, tokens.accent),
                font=title_font(weight="bold"),
            )

    def update_status(self, status: str):
        """更新运行状态（已废弃，状态现在显示在日志面板）"""
        self.running_status = status
        # 状态现在显示在日志面板中，不再更新工具栏

    def refresh_language(self):
        """刷新语言相关文本"""
        # 更新语言下拉框
        if hasattr(self, "lang_combo"):
            lang_values = [t("language_zh"), t("language_en")]
            original_command = self.lang_combo.cget("command")
            self.lang_combo.configure(command=None)
            self.lang_combo.configure(values=lang_values)
            current_lang = get_language()
            # 使用固定文本设置值，避免翻译问题
            if current_lang == "zh-CN":
                self.lang_combo.set(t("language_zh"))
            else:
                self.lang_combo.set(t("language_en"))
            self.lang_combo.configure(command=original_command)

        # 更新按钮文本
        if hasattr(self, "open_output_btn"):
            self.open_output_btn.configure(text=t("open_output_folder"))
        if hasattr(self, "open_failed_links_btn"):
            self.open_failed_links_btn.configure(text=t("open_failed_links"))
        if hasattr(self, "github_btn"):
            self.github_btn.configure(text=f"{t('github_link_text')} | {t('version_text')}")

        # 更新标题
        if hasattr(self, "title_label"):
            tokens = get_theme(self.current_theme)
            self.title_label.configure(
                text=self.current_mode,
                text_color=(tokens.accent, tokens.accent),
                font=title_font(weight="bold"),
            )

    def update_theme(self, theme_name: ThemeName):
        """更新当前主题并刷新下拉框显示"""
        self.current_theme = theme_name
        # 更新标题颜色和字体
        if hasattr(self, "title_label"):
            tokens = get_theme(theme_name)
            self.title_label.configure(
                text_color=(tokens.accent, tokens.accent), font=title_font(weight="bold")
            )
        self.refresh_theme_combo()

    def refresh_theme_combo(self):
        """刷新主题下拉框（语言切换后或主题切换后调用）"""
        if not hasattr(self, "theme_combo"):
            return

        if self._refreshing_theme_combo:
            return

        self._refreshing_theme_combo = True
        try:
            saved_theme = self.current_theme
            original_command = self.theme_combo.cget("command")
            self.theme_combo.configure(command=None)

            # 更新下拉框选项（使用当前语言的翻译）
            theme_values = [
                t("theme_light"),
                t("theme_light_gray"),
                t("theme_dark_gray"),
                t("theme_claude_warm"),
            ]
            self.theme_combo.configure(values=theme_values)

            # 获取当前主题的显示名称
            current_theme_display = t(f"theme_{saved_theme}")

            # 立即设置下拉框的值
            try:
                self.theme_combo.set(current_theme_display)
            except Exception:
                # 如果设置失败，尝试延迟设置
                def set_value_safely():
                    try:
                        if hasattr(self, "theme_combo"):
                            self.theme_combo.set(current_theme_display)
                    except Exception:
                        pass
                    finally:
                        self._refreshing_theme_combo = False

                self.after(50, set_value_safely)
                return

            # 恢复命令回调
            self.theme_combo.configure(command=original_command)
            self._refreshing_theme_combo = False
        except Exception:
            self._refreshing_theme_combo = False
            # 如果出错，至少恢复命令回调
            try:
                if hasattr(self, "theme_combo"):
                    original_command = self.theme_combo.cget("command")
                    if original_command is None:
                        # 尝试恢复之前的命令
                        self.theme_combo.configure(command=self._on_theme_changed)
            except Exception:
                pass
