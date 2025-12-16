"""
core.output 包的 __init__.py
用于导出公共接口，保持向后兼容
"""

# 导入并导出 OutputWriter
from .writer import OutputWriter

# 定义 __all__ 以明确包的公共接口
__all__ = [
    "OutputWriter",
]

