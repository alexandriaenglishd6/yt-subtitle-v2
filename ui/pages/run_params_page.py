"""
运行参数页面
包含并发数设置等运行参数配置
"""
import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Optional
from pathlib import Path
from ui.i18n_manager import t
from ui.fonts import title_font, body_font


class RunParamsPage(ctk.CTkFrame):
    """运行参数页面"""
    
    def __init__(
        self,
        parent,
        concurrency: int = 10,
        retry_count: int = 2,
        output_dir: str = "out",
        on_save: Optional[Callable[[int, int, str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.concurrency = concurrency
        self.retry_count = retry_count
        self.output_dir = output_dir
        self.on_save = on_save
        self.grid_columnconfigure(0, weight=1)
        self._build_ui()
    
    def _build_ui(self):
        """构建 UI"""
        # 标题
        title = ctk.CTkLabel(
            self,
            text=t("run_params"),
            font=title_font(weight="bold")
        )
        title.pack(pady=16)
        
        # 并发数量设置
        concurrency_frame = ctk.CTkFrame(self)
        concurrency_frame.pack(fill="x", padx=32, pady=16)
        concurrency_frame.grid_columnconfigure(1, weight=1)
        
        # 左侧：标签
        concurrency_label = ctk.CTkLabel(
            concurrency_frame,
            text=t("concurrency_label"),
            font=body_font()
        )
        concurrency_label.grid(row=0, column=0, padx=8, pady=8, sticky="w")
        
        # 中间：滑块和输入框
        concurrency_control_frame = ctk.CTkFrame(concurrency_frame, fg_color="transparent")
        concurrency_control_frame.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        concurrency_control_frame.grid_columnconfigure(0, weight=1)
        
        # 滑块
        self.concurrency_slider = ctk.CTkSlider(
            concurrency_control_frame,
            from_=1,
            to=50,
            number_of_steps=49,
            command=self._on_concurrency_slider_changed
        )
        self.concurrency_slider.set(self.concurrency)
        self.concurrency_slider.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        
        # 输入框
        self.concurrency_entry = ctk.CTkEntry(
            concurrency_control_frame,
            width=60
        )
        self.concurrency_entry.insert(0, str(self.concurrency))
        self.concurrency_entry.grid(row=0, column=1, padx=(0, 8))
        self.concurrency_entry.bind("<KeyRelease>", self._on_concurrency_entry_changed)
        
        # 范围提示
        range_label = ctk.CTkLabel(
            concurrency_control_frame,
            text="(1-50)",
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        range_label.grid(row=0, column=2, padx=(0, 8))
        
        # 警告提示（第二行）
        self.concurrency_warning = ctk.CTkLabel(
            concurrency_frame,
            text="",
            font=body_font(),
            text_color=("orange", "orange")
        )
        self.concurrency_warning.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="w")
        
        # 更新警告提示
        self._update_concurrency_warning(self.concurrency)
        
        # 重试次数设置
        retry_frame = ctk.CTkFrame(self)
        retry_frame.pack(fill="x", padx=32, pady=16)
        
        retry_label = ctk.CTkLabel(
            retry_frame,
            text=t("retry_count_label"),
            font=body_font()
        )
        retry_label.pack(side="left", padx=8, pady=8)
        
        self.retry_count_entry = ctk.CTkEntry(
            retry_frame,
            width=100,
            placeholder_text="2"
        )
        self.retry_count_entry.pack(side="left", padx=8, pady=8)
        self.retry_count_entry.insert(0, str(self.retry_count))
        
        retry_hint = ctk.CTkLabel(
            retry_frame,
            text=t("retry_count_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        retry_hint.pack(side="left", padx=8, pady=8)
        
        # 输出目录设置
        output_dir_frame = ctk.CTkFrame(self)
        output_dir_frame.pack(fill="x", padx=32, pady=16)
        
        output_dir_label = ctk.CTkLabel(
            output_dir_frame,
            text=t("output_dir_label"),
            font=body_font()
        )
        output_dir_label.pack(side="left", padx=8, pady=8)
        
        self.output_dir_entry = ctk.CTkEntry(
            output_dir_frame,
            width=200,
            placeholder_text="out"
        )
        self.output_dir_entry.pack(side="left", padx=8, pady=8)
        self.output_dir_entry.insert(0, str(self.output_dir))
        
        # 选择文件夹按钮
        select_folder_btn = ctk.CTkButton(
            output_dir_frame,
            text=t("select_folder"),
            width=100,
            command=self._on_select_folder
        )
        select_folder_btn.pack(side="left", padx=8, pady=8)
        
        output_dir_hint = ctk.CTkLabel(
            output_dir_frame,
            text=t("output_dir_placeholder"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        output_dir_hint.pack(side="left", padx=8, pady=8)
        
        # 保存按钮和提示信息（同一行）
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=32, pady=16)
        
        save_btn = ctk.CTkButton(
            button_frame,
            text=t("save_settings"),
            command=self._on_save,
            width=120
        )
        save_btn.pack(side="left", padx=8)
        
        # 提示信息（与保存按钮同一行）
        hint_label = ctk.CTkLabel(
            button_frame,
            text=t("save_settings_hint"),
            font=body_font(),
            text_color=("gray50", "gray50")
        )
        hint_label.pack(side="left", padx=8, pady=8)
    
    def _on_concurrency_slider_changed(self, value):
        """滑块值改变回调"""
        concurrency = int(value)
        # 更新输入框（不触发输入框回调）
        current_text = self.concurrency_entry.get().strip()
        if current_text != str(concurrency):
            self.concurrency_entry.delete(0, "end")
            self.concurrency_entry.insert(0, str(concurrency))
        # 更新警告提示
        self._update_concurrency_warning(concurrency)
    
    def _on_concurrency_entry_changed(self, event=None):
        """输入框值改变回调"""
        try:
            concurrency_str = self.concurrency_entry.get().strip()
            if not concurrency_str:
                return
            concurrency = int(concurrency_str)
            # 限制范围
            if concurrency < 1:
                concurrency = 1
                self.concurrency_entry.delete(0, "end")
                self.concurrency_entry.insert(0, "1")
            elif concurrency > 50:
                concurrency = 50
                self.concurrency_entry.delete(0, "end")
                self.concurrency_entry.insert(0, "50")
            # 更新滑块
            if self.concurrency_slider.get() != concurrency:
                self.concurrency_slider.set(concurrency)
            # 更新警告提示
            self._update_concurrency_warning(concurrency)
        except ValueError:
            # 输入无效，忽略
            pass
    
    def _update_concurrency_warning(self, concurrency: int):
        """更新并发数警告提示"""
        if concurrency > 30:
            self.concurrency_warning.configure(
                text="⚠️ 警告：并发数过高可能导致 IP 封锁、429 错误或本地模型压力过大，建议降低并发数",
                text_color=("red", "red")
            )
        elif concurrency > 20:
            self.concurrency_warning.configure(
                text="⚠️ 提示：高并发可能导致限流，建议监控网络请求频率",
                text_color=("orange", "orange")
            )
        elif concurrency > 10:
            self.concurrency_warning.configure(
                text="💡 提示：并发数较高，建议监控网络请求，避免触发限流",
                text_color=("gray50", "gray50")
            )
        else:
            self.concurrency_warning.configure(text="")
    
    def _on_save(self):
        """保存运行参数"""
        if self.on_save:
            try:
                concurrency_str = self.concurrency_entry.get().strip()
                if not concurrency_str:
                    return
                concurrency = int(concurrency_str)
                # 验证范围
                if concurrency < 1:
                    concurrency = 1
                    self.concurrency_entry.delete(0, "end")
                    self.concurrency_entry.insert(0, "1")
                elif concurrency > 50:
                    concurrency = 50
                    self.concurrency_entry.delete(0, "end")
                    self.concurrency_entry.insert(0, "50")
                
                retry_count_str = self.retry_count_entry.get().strip()
                retry_count = 2  # 默认值
                if retry_count_str:
                    retry_count = int(retry_count_str)
                    if retry_count < 0:
                        retry_count = 0
                    elif retry_count > 10:
                        retry_count = 10
                        self.retry_count_entry.delete(0, "end")
                        self.retry_count_entry.insert(0, "10")
                
                output_dir = self.output_dir_entry.get().strip()
                if not output_dir:
                    output_dir = "out"
                
                self.on_save(concurrency, retry_count, output_dir)
            except ValueError:
                pass
    
    def _on_select_folder(self):
        """选择输出文件夹"""
        current_dir = self.output_dir_entry.get().strip()
        if not current_dir:
            current_dir = "out"
        
        # 尝试解析为绝对路径
        try:
            initial_dir = Path(current_dir).absolute()
            if not initial_dir.exists():
                initial_dir = Path.cwd()
        except Exception:
            initial_dir = Path.cwd()
        
        # 打开文件夹选择对话框
        folder_path = filedialog.askdirectory(
            title=t("select_output_folder"),
            initialdir=str(initial_dir)
        )
        
        if folder_path:
            # 将选择的路径转换为相对路径（如果可能）
            try:
                rel_path = Path(folder_path).relative_to(Path.cwd())
                # 如果相对路径更短，使用相对路径
                if len(str(rel_path)) < len(str(folder_path)):
                    folder_path = str(rel_path)
            except (ValueError, RuntimeError):
                # 如果无法转换为相对路径，保持绝对路径
                pass
            
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, folder_path)
    
    def refresh_language(self):
        """刷新语言相关文本"""
        # 更新按钮和标签文本
        if hasattr(self, 'concurrency_entry'):
            # 语言切换时不需要更新输入框内容
            pass

