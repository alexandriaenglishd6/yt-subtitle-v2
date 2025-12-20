"""
批次ID生成工具
用于生成符合 logging_spec.md 规范的 run_id（批次ID）
"""

from datetime import datetime


def generate_run_id() -> str:
    """生成批次ID（run_id）

    格式：YYYYMMDD_HHMMSS（符合 logging_spec.md 规范）
    例如：20251209_140000

    Returns:
        批次ID字符串
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")
