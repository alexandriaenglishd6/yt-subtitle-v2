"""
YouTube URL 校验工具
用于实时校验输入框中的 URL 格式
"""

import re
from typing import List, Tuple, Optional

# YouTube 域名正则表达式
YOUTUBE_DOMAINS = [
    r"youtube\.com",
    r"youtu\.be",
    r"www\.youtube\.com"
]

# 具体的模式正则
PATTERNS = {
    "video": re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})"),
    "playlist": re.compile(r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)"),
    "channel": re.compile(r"youtube\.com/(?:c/|user/|channel/|@)([^/?]+)"),
}

def is_youtube_domain(url: str) -> bool:
    """检查是否属于 YouTube 域名"""
    url_lower = url.lower()
    return any(re.search(domain, url_lower) for domain in YOUTUBE_DOMAINS)

def validate_youtube_url(url: str) -> Tuple[bool, Optional[str]]:
    """校验单个 YouTube URL
    
    Returns:
        (是否合法, 错误类型键)
    """
    url = url.strip()
    if not url:
        return True, None # 为空不视为错误（不红框），由“开始”按钮校验
        
    if not is_youtube_domain(url):
        return False, "invalid_domain"
        
    # 检查是否匹配任何一个合法模式
    if any(p.search(url) for p in PATTERNS.values()):
        return True, None
        
    return False, "invalid_format"

def validate_url_list(text: str) -> Tuple[bool, List[int]]:
    """校验多行 URL 列表
    
    Returns:
        (是否整体合法, 错误行号列表)
    """
    lines = text.splitlines()
    error_lines = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        is_valid, _ = validate_youtube_url(line)
        if not is_valid:
            error_lines.append(i + 1)
            
    return len(error_lines) == 0, error_lines

