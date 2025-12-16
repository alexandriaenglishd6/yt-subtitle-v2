"""
core.pipeline 包的 __init__.py
用于导出公共接口，保持向后兼容
"""

# 导入并导出主要函数
from .single_video import process_single_video
from .batch import process_video_list

# 定义 __all__ 以明确包的公共接口
__all__ = [
    "process_single_video",
    "process_video_list",
]

