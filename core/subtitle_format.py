"""
字幕格式转换模块

提供 VTT, JSON3, SRV3 等格式到 SRT 格式的转换功能
从 downloader.py 提取，提高代码复用性
"""

import re
import json
from html import unescape
from typing import Optional


def ms_to_srt_time(ms: int) -> str:
    """将毫秒转换为 SRT 时间格式 (HH:MM:SS,mmm)
    
    Args:
        ms: 毫秒数
        
    Returns:
        SRT 格式时间字符串，如 "00:01:23,456"
    """
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def convert_vtt_to_srt(vtt_content: str) -> str:
    """将 VTT (WebVTT) 格式转换为 SRT 格式
    
    Args:
        vtt_content: VTT 格式字幕内容
        
    Returns:
        SRT 格式字幕内容
    """
    # 移除 VTT 头部
    lines = vtt_content.strip().split("\n")
    if lines and lines[0].startswith("WEBVTT"):
        lines = lines[1:]
    
    # 处理时间戳格式
    srt_lines = []
    counter = 1
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 跳过空行和注释
        if not line or line.startswith("NOTE"):
            i += 1
            continue
        # 检测时间戳行
        if " --> " in line:
            # 转换时间戳格式（VTT 用 . 分隔毫秒，SRT 用 ,）
            timestamp = re.sub(r"(\d{2}:\d{2}:\d{2})\.(\d{3})", r"\1,\2", line)
            # 移除 VTT 特有的位置信息
            timestamp = re.sub(r" (align|position|line|size):[^\s]+", "", timestamp)
            srt_lines.append(str(counter))
            srt_lines.append(timestamp)
            counter += 1
            i += 1
            # 收集字幕文本
            while i < len(lines) and lines[i].strip():
                srt_lines.append(lines[i].strip())
                i += 1
            srt_lines.append("")
        else:
            i += 1
    
    return "\n".join(srt_lines)


def convert_json3_to_srt(json_content: str) -> str:
    """将 YouTube JSON3 格式转换为 SRT 格式
    
    JSON3 是 YouTube 使用的一种 JSON 字幕格式，包含 events 数组
    
    Args:
        json_content: JSON3 格式字幕内容
        
    Returns:
        SRT 格式字幕内容，转换失败时返回原内容
    """
    try:
        data = json.loads(json_content)
        events = data.get("events", [])
        
        srt_lines = []
        counter = 1
        
        for event in events:
            if "segs" not in event:
                continue
            
            start_ms = event.get("tStartMs", 0)
            duration_ms = event.get("dDurationMs", 0)
            end_ms = start_ms + duration_ms
            
            text = "".join(seg.get("utf8", "") for seg in event.get("segs", []))
            text = text.strip()
            
            if text:
                srt_lines.append(str(counter))
                srt_lines.append(f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}")
                srt_lines.append(text)
                srt_lines.append("")
                counter += 1
        
        return "\n".join(srt_lines)
    except Exception:
        return json_content


def convert_srv3_to_srt(srv3_content: str) -> str:
    """将 YouTube SRV3 (XML) 格式转换为 SRT 格式
    
    SRV3 是 YouTube 使用的一种 XML 字幕格式
    
    Args:
        srv3_content: SRV3 格式字幕内容
        
    Returns:
        SRT 格式字幕内容，转换失败时返回原内容
    """
    try:
        srt_lines = []
        counter = 1
        
        # 简单的正则解析 <p t="start" d="duration">text</p>
        pattern = r'<p[^>]*t="(\d+)"[^>]*d="(\d+)"[^>]*>([^<]*)</p>'
        matches = re.findall(pattern, srv3_content)
        
        for start_ms_str, duration_ms_str, text in matches:
            start_ms = int(start_ms_str)
            duration_ms = int(duration_ms_str)
            end_ms = start_ms + duration_ms
            text = unescape(text).strip()
            
            if text:
                srt_lines.append(str(counter))
                srt_lines.append(f"{ms_to_srt_time(start_ms)} --> {ms_to_srt_time(end_ms)}")
                srt_lines.append(text)
                srt_lines.append("")
                counter += 1
        
        return "\n".join(srt_lines) if srt_lines else srv3_content
    except Exception:
        return srv3_content


def detect_format(content: str) -> Optional[str]:
    """检测字幕内容的格式
    
    Args:
        content: 字幕内容
        
    Returns:
        格式名称: "vtt", "json3", "srv3", "srt" 或 None（无法识别）
    """
    content = content.strip()
    
    if content.startswith("WEBVTT"):
        return "vtt"
    
    if content.startswith("{"):
        try:
            data = json.loads(content)
            if "events" in data:
                return "json3"
        except json.JSONDecodeError:
            pass
    
    if content.startswith("<?xml") or "<transcript>" in content or "<p t=" in content:
        return "srv3"
    
    # 简单检测 SRT 格式（以数字开头，后跟时间戳）
    lines = content.split("\n")
    if len(lines) >= 2:
        if lines[0].strip().isdigit() and " --> " in lines[1]:
            return "srt"
    
    return None


def convert_to_srt(content: str, source_format: Optional[str] = None) -> str:
    """自动检测格式并转换为 SRT
    
    Args:
        content: 字幕内容
        source_format: 源格式（可选，不指定时自动检测）
        
    Returns:
        SRT 格式字幕内容
    """
    if source_format is None:
        source_format = detect_format(content)
    
    if source_format == "vtt":
        return convert_vtt_to_srt(content)
    elif source_format == "json3":
        return convert_json3_to_srt(content)
    elif source_format == "srv3":
        return convert_srv3_to_srt(content)
    elif source_format == "srt":
        return content  # 已经是 SRT 格式
    else:
        # 未知格式，返回原内容
        return content
