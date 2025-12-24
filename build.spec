# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件
用于将 YouTube 字幕工具打包为便携版
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# 项目根目录
project_root = os.path.dirname(os.path.abspath(SPEC))

# 收集数据文件
datas = [
    # i18n 语言文件
    (os.path.join(project_root, 'core', 'i18n', 'locales'), os.path.join('core', 'i18n', 'locales')),
    # 配置目录（如果存在）
    (os.path.join(project_root, 'config'), 'config'),
]

# 收集隐式导入的模块
hiddenimports = [
    # customtkinter 相关
    'customtkinter',
    'PIL',
    'PIL._tkinter_finder',
    # deep-translator 相关
    'deep_translator',
    'deep_translator.google',
    # 请求相关
    'requests',
    'urllib3',
    'certifi',
    # 其他核心模块
    'json',
    'threading',
    'concurrent.futures',
    # tkinter
    'tkinter',
    'tkinter.messagebox',
    'tkinter.filedialog',
]

# 收集 customtkinter 数据文件
try:
    datas += collect_data_files('customtkinter')
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'notebook',
        'jupyter',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='YT-Subtitle-Tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标：icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YT-Subtitle-Tool',
)
