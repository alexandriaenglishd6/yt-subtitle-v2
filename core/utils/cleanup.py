"""
清理工具模块
提供临时文件清理等功能
"""

from pathlib import Path
from typing import List
from core.logger import get_logger

logger = get_logger()


def cleanup_tmp_files(directory: Path, recursive: bool = True) -> int:
    """清理目录中的残留 .tmp 文件
    
    Args:
        directory: 要清理的目录路径
        recursive: 是否递归清理子目录（默认 True）
        
    Returns:
        清理的文件数量
    """
    if not directory.exists() or not directory.is_dir():
        return 0
    
    cleaned_count = 0
    pattern = "**/*.tmp" if recursive else "*.tmp"
    
    try:
        for tmp_file in directory.glob(pattern):
            try:
                if tmp_file.is_file():
                    tmp_file.unlink()
                    cleaned_count += 1
                    logger.debug(f"Cleaned tmp file: {tmp_file}")
            except (OSError, PermissionError) as e:
                logger.warning(f"Failed to delete tmp file {tmp_file}: {e}")
    except Exception as e:
        logger.warning(f"Error during tmp files cleanup: {e}")
    
    if cleaned_count > 0:
        logger.info_i18n(
            "log.cleanup_tmp_files",
            count=cleaned_count,
            directory=str(directory),
        )
    
    return cleaned_count


def cleanup_video_tmp_files(video_output_dir: Path) -> int:
    """清理视频输出目录中的临时文件
    
    专门用于清理视频处理过程中产生的临时文件，包括：
    - .tmp 文件
    - .part 文件（下载未完成）
    - .progress.json.tmp 文件
    
    Args:
        video_output_dir: 视频输出目录路径
        
    Returns:
        清理的文件数量
    """
    if not video_output_dir.exists() or not video_output_dir.is_dir():
        return 0
    
    cleaned_count = 0
    patterns = ["**/*.tmp", "**/*.part", "**/*.progress.json.tmp"]
    
    for pattern in patterns:
        try:
            for tmp_file in video_output_dir.glob(pattern):
                try:
                    if tmp_file.is_file():
                        tmp_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"Cleaned tmp file: {tmp_file}")
                except (OSError, PermissionError) as e:
                    logger.warning(f"Failed to delete tmp file {tmp_file}: {e}")
        except Exception as e:
            logger.warning(f"Error during cleanup with pattern {pattern}: {e}")
    
    if cleaned_count > 0:
        logger.info_i18n(
            "log.cleanup_tmp_files",
            count=cleaned_count,
            directory=str(video_output_dir),
        )
    
    return cleaned_count
