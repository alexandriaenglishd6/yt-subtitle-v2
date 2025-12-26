"""
Subprocess 工具函数
提供跨平台的 subprocess 调用，支持 Windows 下隐藏命令行窗口
"""

import subprocess
import sys
from typing import Any, Dict, Optional, List, Union


def get_subprocess_kwargs() -> Dict[str, Any]:
    """获取 subprocess.run 的平台相关参数
    
    Windows 下添加参数以隐藏命令行窗口
    
    Returns:
        字典，包含 startupinfo 和 creationflags 参数
    """
    kwargs: Dict[str, Any] = {}
    
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = startupinfo
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    
    return kwargs


def run_command(
    cmd: Union[List[str], str],
    capture_output: bool = True,
    text: bool = True,
    timeout: Optional[int] = None,
    **kwargs
) -> subprocess.CompletedProcess:
    """执行命令，Windows 下自动隐藏命令行窗口
    
    Args:
        cmd: 命令（列表或字符串）
        capture_output: 是否捕获输出
        text: 是否以文本模式处理输出
        timeout: 超时时间（秒）
        **kwargs: 其他传递给 subprocess.run 的参数
    
    Returns:
        subprocess.CompletedProcess 对象
    """
    # 合并平台相关参数
    platform_kwargs = get_subprocess_kwargs()
    platform_kwargs.update(kwargs)
    
    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        **platform_kwargs
    )
