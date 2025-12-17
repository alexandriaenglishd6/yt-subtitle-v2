"""
字幕输出格式处理
支持 SRT、VTT、TXT 格式
"""
import re
from pathlib import Path
from typing import Optional, Dict, List

from core.logger import get_logger
from core.exceptions import AppException, ErrorType
from core.failure_logger import _atomic_write

logger = get_logger()


def parse_srt(srt_content: str) -> List[Dict]:
    """解析 SRT 或 VTT 字幕文件内容
    
    Args:
        srt_content: SRT 或 VTT 文件内容
    
    Returns:
        字幕条目列表，每个条目包含：
        {
            "index": int,  # 序号
            "start": str,  # 开始时间（SRT 格式：逗号分隔）
            "end": str,    # 结束时间（SRT 格式：逗号分隔）
            "text": str    # 字幕文本
        }
    """
    entries = []
    
    # 检查是否是 VTT 格式
    is_vtt = srt_content.strip().startswith("WEBVTT") or "WEBVTT" in srt_content[:100]
    
    if is_vtt:
        # 处理 VTT 格式
        lines = srt_content.split("\n")
        current_block = []
        subtitle_index = 1
        skip_header = True
        
        for line in lines:
            line_stripped = line.strip()
            
            # 跳过 VTT 头部
            if skip_header:
                if line_stripped.upper().startswith("WEBVTT"):
                    continue
                if line_stripped.startswith("Kind:") or line_stripped.startswith("Language:"):
                    continue
                if line_stripped.startswith("Translator:") or line_stripped.startswith("Reviewer:") or line_stripped.startswith("المترجم:") or line_stripped.startswith("المدقّق:"):
                    continue
                if not line_stripped and not current_block:
                    continue
                if "-->" in line:
                    skip_header = False
                elif line_stripped and not line_stripped.startswith("WEBVTT") and "-->" not in line:
                    continue
            
            # 空行：结束当前字幕块
            if not line_stripped:
                if current_block:
                    # 解析当前块
                    time_line = None
                    text_lines = []
                    for block_line in current_block:
                        if "-->" in block_line:
                            time_line = block_line
                        else:
                            text_lines.append(block_line)
                    
                    if time_line:
                        # 解析时间轴：00:00:00.000 --> 00:00:02.000
                        time_match = re.match(r'(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3})', time_line)
                        if time_match:
                            start = f"{time_match.group(1)},{time_match.group(2)}"
                            end = f"{time_match.group(3)},{time_match.group(4)}"
                            text = "\n".join(text_lines).strip()
                            
                            if text:  # 只添加有文本的条目
                                entries.append({
                                    "index": subtitle_index,
                                    "start": start,
                                    "end": end,
                                    "text": text
                                })
                                subtitle_index += 1
                    current_block = []
                continue
            
            # 判断是否是时间轴
            if "-->" in line:
                if current_block:
                    # 处理之前的块
                    time_line = None
                    text_lines = []
                    for block_line in current_block:
                        if "-->" in block_line:
                            time_line = block_line
                        else:
                            text_lines.append(block_line)
                    
                    if time_line:
                        time_match = re.match(r'(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3})', time_line)
                        if time_match:
                            start = f"{time_match.group(1)},{time_match.group(2)}"
                            end = f"{time_match.group(3)},{time_match.group(4)}"
                            text = "\n".join(text_lines).strip()
                            
                            if text:
                                entries.append({
                                    "index": subtitle_index,
                                    "start": start,
                                    "end": end,
                                    "text": text
                                })
                                subtitle_index += 1
                    current_block = []
                current_block = [line]
                continue
            
            # 其他行：字幕文本
            if current_block:
                current_block.append(line)
        
        # 处理最后一个块
        if current_block:
            time_line = None
            text_lines = []
            for block_line in current_block:
                if "-->" in block_line:
                    time_line = block_line
                else:
                    text_lines.append(block_line)
            
            if time_line:
                time_match = re.match(r'(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3})', time_line)
                if time_match:
                    start = f"{time_match.group(1)},{time_match.group(2)}"
                    end = f"{time_match.group(3)},{time_match.group(4)}"
                    text = "\n".join(text_lines).strip()
                    
                    if text:
                        entries.append({
                            "index": subtitle_index,
                            "start": start,
                            "end": end,
                            "text": text
                        })
    else:
        # 处理 SRT 格式：序号\n时间码\n文本\n\n
        pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\d+\s*\n|\Z)'
        matches = re.finditer(pattern, srt_content, re.DOTALL | re.MULTILINE)
        
        for match in matches:
            index = int(match.group(1))
            start = match.group(2)
            end = match.group(3)
            text = match.group(4).strip()
            
            entries.append({
                "index": index,
                "start": start,
                "end": end,
                "text": text
            })
    
    return entries


def merge_srt_entries(
    source_entries: List[Dict],
    target_entries: List[Dict]
) -> str:
    """合并源语言和目标语言字幕条目
    
    根据时间轴对齐，生成双语字幕（格式：源语言 / 目标语言）
    
    Args:
        source_entries: 源语言字幕条目列表
        target_entries: 目标语言字幕条目列表
    
    Returns:
        合并后的 SRT 格式字符串
    """
    # 简单的对齐策略：按序号对齐（假设两个字幕文件的序号和时间轴一致）
    # 如果序号不一致，则按时间轴对齐
    merged_lines = []
    matched_count = 0
    unmatched_count = 0
    
    # 创建目标字幕的时间索引（用于时间对齐）
    target_by_time = {}
    for entry in target_entries:
        key = (entry["start"], entry["end"])
        target_by_time[key] = entry
    
    # 遍历源字幕条目，尝试匹配目标字幕
    for source_entry in source_entries:
        source_text = source_entry["text"]
        time_key = (source_entry["start"], source_entry["end"])
        
        # 尝试按时间轴匹配
        target_entry = target_by_time.get(time_key)
        
        if target_entry:
            # 找到匹配的目标字幕，合并（上下放置）
            target_text = target_entry["text"]
            merged_text = f"{source_text}\n{target_text}"
            matched_count += 1
        else:
            # 未找到匹配，只使用源语言
            merged_text = source_text
            unmatched_count += 1
        
        # 生成 SRT 条目
        merged_lines.append(f"{source_entry['index']}")
        merged_lines.append(f"{source_entry['start']} --> {source_entry['end']}")
        merged_lines.append(merged_text)
        merged_lines.append("")  # 空行分隔
    
    logger.debug_i18n("log.subtitle_merge_complete", matched_count=matched_count, unmatched_count=unmatched_count)
    return "\n".join(merged_lines)


def merge_entries_to_txt(
    source_entries: List[Dict],
    target_entries: List[Dict]
) -> str:
    """合并源语言和目标语言字幕条目为 TXT 格式（去掉时间轴）
    
    保持字幕条目的空行分隔，双语字幕保持上下放置格式
    
    Args:
        source_entries: 源语言字幕条目列表
        target_entries: 目标语言字幕条目列表
    
    Returns:
        合并后的 TXT 格式字符串（每个条目之间有空行分隔）
    """
    # 创建目标字幕的时间索引（用于时间对齐）
    target_by_time = {}
    for entry in target_entries:
        key = (entry["start"], entry["end"])
        target_by_time[key] = entry
    
    lines = []
    matched_count = 0
    unmatched_count = 0
    
    # 遍历源字幕条目，尝试匹配目标字幕
    for source_entry in source_entries:
        source_text = source_entry["text"].strip()
        time_key = (source_entry["start"], source_entry["end"])
        
        # 尝试按时间轴匹配
        target_entry = target_by_time.get(time_key)
        
        if target_entry:
            # 找到匹配的目标字幕，合并（上下放置）
            target_text = target_entry["text"].strip()
            merged_text = f"{source_text}\n{target_text}"
            matched_count += 1
        else:
            # 未找到匹配，只使用源语言
            merged_text = source_text
            unmatched_count += 1
        
        # 添加到输出列表
        if merged_text:
            lines.append(merged_text)
            # 每个条目后添加空行分隔
            lines.append("")
    
    # 移除最后一个空行
    if lines and lines[-1] == "":
        lines.pop()
    
    from core.logger import translate_log
    logger.debug(translate_log("txt_subtitle_merge_complete", matched=matched_count, unmatched=unmatched_count))
    return "\n".join(lines)


def srt_to_txt(srt_content: str) -> str:
    """将 SRT 字幕转换为纯文本（去掉时间轴）
    
    保持字幕条目的空行分隔，对于双语字幕保持上下放置格式
    
    Args:
        srt_content: SRT 文件内容
    
    Returns:
        纯文本内容（每个字幕条目之间有空行分隔）
    """
    entries = parse_srt(srt_content)
    lines = []
    for entry in entries:
        text = entry.get("text", "").strip()
        if text:
            # 保持文本中的换行（双语字幕的上下放置格式）
            lines.append(text)
            # 每个条目后添加空行分隔
            lines.append("")
    
    # 移除最后一个空行
    if lines and lines[-1] == "":
        lines.pop()
    
    return "\n".join(lines)


def write_txt_subtitle(srt_path: Path, txt_path: Path) -> Optional[Path]:
    """将 SRT 字幕文件转换并写入为 TXT 格式
    
    Args:
        srt_path: SRT 文件路径
        txt_path: 输出 TXT 文件路径
    
    Returns:
        写入的文件路径，失败返回 None
    """
    try:
        srt_content = srt_path.read_text(encoding="utf-8")
        txt_content = srt_to_txt(srt_content)
        if not _atomic_write(txt_path, txt_content, mode="w"):
            logger.warning_i18n("log.txt_subtitle_write_failed", path=str(txt_path))
            return None
        from core.logger import translate_log
        logger.debug(translate_log("txt_subtitle_written", file_name=txt_path.name))
        return txt_path
    except Exception as e:
        logger.warning_i18n("log.srt_to_txt_conversion_failed", error=str(e))
        return None

