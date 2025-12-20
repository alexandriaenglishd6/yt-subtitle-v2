"""
输出工具函数
"""

import re
from typing import Optional

from core.logger import get_logger

logger = get_logger()


def sanitize_filename(filename: str) -> str:
    """清理文件名中的非法字符

    Args:
        filename: 原始文件名

    Returns:
        清理后的文件名
    """
    # Windows/Linux 文件系统不允许的字符
    illegal_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]

    result = filename
    for char in illegal_chars:
        result = result.replace(char, "_")

    # 移除前后空格和点
    result = result.strip(" .")

    # 限制长度（Windows 路径限制）
    if len(result) > 200:
        result = result[:200]

    return result


def extract_language_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取语言代码

    例如：original.en.srt -> en
          translated.zh-CN.srt -> zh-CN

    Args:
        filename: 文件名

    Returns:
        语言代码，如果无法提取则返回 None
    """
    # 匹配 pattern.<lang>.srt 或 pattern.<lang>.md
    match = re.search(
        r"\.([a-z]{2}(?:-[A-Z]{2})?)\.(?:srt|md)$", filename, re.IGNORECASE
    )
    if match:
        return match.group(1)
    return None
