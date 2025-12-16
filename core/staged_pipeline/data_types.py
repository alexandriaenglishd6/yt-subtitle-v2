"""
阶段数据容器定义
"""
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.models import VideoInfo, DetectionResult
from core.exceptions import ErrorType


@dataclass
class StageData:
    """阶段数据容器
    
    用于在阶段之间传递视频处理数据
    """
    video_info: VideoInfo
    detection_result: Optional[DetectionResult] = None
    download_result: Optional[Dict[str, Any]] = None
    translation_result: Optional[Dict[str, Path]] = None
    summary_result: Optional[Path] = None  # 摘要文件路径
    temp_dir: Optional[Path] = None  # 临时目录（在 DOWNLOAD 阶段创建）
    temp_dir_created: bool = False  # 临时目录是否已创建
    error: Optional[Exception] = None  # 错误异常对象
    error_stage: Optional[str] = None  # 发生错误的阶段名称
    error_type: Optional[ErrorType] = None  # 错误类型（ErrorType 枚举）
    skip_reason: Optional[str] = None  # 跳过原因（如"无可用字幕"）
    is_processed: bool = False  # 是否已处理（用于增量管理）
    processing_failed: bool = False  # 处理是否失败（用于资源清理）
    run_id: Optional[str] = None  # 批次ID（run_id），用于日志和失败记录

