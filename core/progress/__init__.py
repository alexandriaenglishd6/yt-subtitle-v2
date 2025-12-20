"""
Progress & ETA Module - 进度和时间估算

提供处理进度跟踪和剩余时间估算功能。
ETA 文案使用 core.i18n 的 t() 函数实现国际化。
"""

from .eta import (
    ETACalculator,
    ProgressTracker,
    format_duration,
    format_eta,
)

__all__ = [
    "ETACalculator",
    "ProgressTracker",
    "format_duration",
    "format_eta",
]
