"""
主窗口模块
拆分自 ui/main_window.py，保持向后兼容
"""
from .window import MainWindow

__all__ = ["MainWindow"]

# 保持向后兼容：允许 from ui.main_window import MainWindow
# 同时也支持 from ui.main_window.window import MainWindow

