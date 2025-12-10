"""
顶部工具栏组件
包含应用标题、运行状态、语言/主题切换、功能按钮
"""
import customtkinter as ctk
from typing import Callable, Optional
from ui.i18n_manager import t, get_language
from ui.themes import ThemeName
from ui.fonts import heading_font, body_font


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
        **kwargs
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
        
        # 左侧：应用标题 + 当前模式
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=16, pady=8, sticky="w")
        
        self.title_label = ctk.CTkLabel(
            title_frame,
            text=f"{t('app_name')} – {self.current_mode}",
            font=heading_font(weight="bold")
        )
        self.title_label.pack(side="left", padx=8)
        
        # 中间：运行状态
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=0, column=1, padx=16, pady=8, sticky="ew")
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text=f"{t('status')}：{self.running_status}",
            font=body_font()
        )
        self.status_label.pack(side="left", padx=8)
        
        # 右侧：功能按钮区域
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=0, column=2, padx=16, pady=8, sticky="e")
        
        # UI 语言切换
        # 使用固定文本，避免翻译问题
        lang_values = ["中文", "English"]
        self.lang_combo = ctk.CTkComboBox(
            button_frame,
            values=lang_values,
            width=100,
            command=self._on_language_changed
        )
        current_lang = get_language()
        if current_lang == "zh-CN":
            self.lang_combo.set("中文")
        else:
            self.lang_combo.set("English")
        self.lang_combo.pack(side="left", padx=4)
        
        # 主题切换
        theme_values = [
            t("theme_light"),
            t("theme_light_gray"),
            t("theme_dark_gray"),
            t("theme_claude_warm")
        ]
        self.theme_combo = ctk.CTkComboBox(
            button_frame,
            values=theme_values,
            width=120,
            command=self._on_theme_changed
        )
        current_theme_display = t(f"theme_{self.current_theme}")
        self.theme_combo.set(current_theme_display)
        self.theme_combo.pack(side="left", padx=4)
        
        # 打开输出文件夹按钮
        self.open_output_btn = ctk.CTkButton(
            button_frame,
            text=t("open_output_folder"),
            width=120,
            command=self._on_open_output_folder
        )
        self.open_output_btn.pack(side="left", padx=4)
        
        # 打开配置文件夹按钮
        self.open_config_btn = ctk.CTkButton(
            button_frame,
            text=t("open_config_folder"),
            width=120,
            command=self._on_open_config_folder
        )
        self.open_config_btn.pack(side="left", padx=4)
    
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
    
    def _on_open_config_folder(self):
        """打开配置文件夹"""
        if self.on_open_config:
            self.on_open_config()
    
    def update_title(self, mode: str):
        """更新标题"""
        self.current_mode = mode
        if hasattr(self, 'title_label'):
            self.title_label.configure(text=f"{t('app_name')} – {mode}")
    
    def update_status(self, status: str):
        """更新运行状态"""
        self.running_status = status
        if hasattr(self, 'status_label'):
            # status 可能是中文或英文，需要确保显示正确
            # 如果 status 是翻译键（如 "status_idle"），则翻译它
            if status.startswith("status_"):
                status_display = t(status)
            else:
                status_display = status
            self.status_label.configure(text=f"{t('status')}：{status_display}")
    
    def refresh_language(self):
        """刷新语言相关文本"""
        # 更新语言下拉框
        if hasattr(self, 'lang_combo'):
            # 使用固定文本，避免翻译问题
            lang_values = ["中文", "English"]
            original_command = self.lang_combo.cget("command")
            self.lang_combo.configure(command=None)
            self.lang_combo.configure(values=lang_values)
            current_lang = get_language()
            # 使用固定文本设置值，避免翻译问题
            if current_lang == "zh-CN":
                self.lang_combo.set("中文")  # 固定文本
            else:
                self.lang_combo.set("English")  # 固定文本
            self.lang_combo.configure(command=original_command)
        
        # 更新按钮文本
        if hasattr(self, 'open_output_btn'):
            self.open_output_btn.configure(text=t("open_output_folder"))
        if hasattr(self, 'open_config_btn'):
            self.open_config_btn.configure(text=t("open_config_folder"))
        
        # 更新标题和状态
        if hasattr(self, 'title_label'):
            self.title_label.configure(text=f"{t('app_name')} – {self.current_mode}")
        if hasattr(self, 'status_label'):
            self.status_label.configure(text=f"{t('status')}：{self.running_status}")
    
    def update_theme(self, theme_name: ThemeName):
        """更新当前主题并刷新下拉框显示"""
        self.current_theme = theme_name
        self.refresh_theme_combo()
    
    def refresh_theme_combo(self):
        """刷新主题下拉框（语言切换后或主题切换后调用）"""
        if not hasattr(self, 'theme_combo'):
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
                t("theme_claude_warm")
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
                        if hasattr(self, 'theme_combo'):
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
        except Exception as e:
            self._refreshing_theme_combo = False
            # 如果出错，至少恢复命令回调
            try:
                if hasattr(self, 'theme_combo'):
                    original_command = self.theme_combo.cget("command")
                    if original_command is None:
                        # 尝试恢复之前的命令
                        self.theme_combo.configure(command=self._on_theme_changed)
            except Exception:
                pass

