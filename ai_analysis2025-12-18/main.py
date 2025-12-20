"""
GUI 入口
图形界面入口
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import customtkinter as ctk
except ImportError:
    print("Error: customtkinter not installed")
    print("Please run: pip install customtkinter")
    sys.exit(1)

from ui.main_window import MainWindow


def main():
    """GUI 主入口"""
    # 设置 customtkinter 外观模式（默认亮色）
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    
    # 创建并启动主窗口
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
