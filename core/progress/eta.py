"""
ETA Calculator - 剩余时间估算模块

基于历史处理速度计算预计完成时间。
支持滑动窗口平滑和自适应权重。

设计原则：
- ETA 文案使用 t() 函数国际化
- 基于实际处理速度动态调整
- 支持视频/chunk 两种粒度
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import deque

from core.i18n import t


@dataclass
class ProcessingRecord:
    """单次处理记录

    Attributes:
        item_id: 处理项 ID（视频 ID 或 chunk 索引）
        start_time: 开始时间戳
        end_time: 结束时间戳
        duration: 处理耗时（秒）
        item_size: 项大小（字符数或视频时长秒数）
    """
    item_id: str
    start_time: float
    end_time: float
    duration: float
    item_size: Optional[int] = None


class ETACalculator:
    """剩余时间计算器

    使用滑动窗口平均处理速度来预测剩余时间。
    支持加权平均，最近的记录权重更高。
    """

    # 默认配置
    DEFAULT_WINDOW_SIZE = 10  # 滑动窗口大小
    DEFAULT_MIN_SAMPLES = 2  # 最少样本数（否则不估算）

    def __init__(
        self,
        window_size: int = DEFAULT_WINDOW_SIZE,
        min_samples: int = DEFAULT_MIN_SAMPLES,
    ):
        """初始化 ETA 计算器

        Args:
            window_size: 滑动窗口大小
            min_samples: 最少样本数
        """
        self.window_size = window_size
        self.min_samples = min_samples
        self.records: deque = deque(maxlen=window_size)
        self._total_items = 0
        self._completed_items = 0
        self._start_time: Optional[float] = None

    def set_total(self, total: int) -> None:
        """设置总任务数

        Args:
            total: 总任务数
        """
        self._total_items = total
        self._start_time = time.time()

    def add_record(self, record: ProcessingRecord) -> None:
        """添加处理记录

        Args:
            record: 处理记录
        """
        self.records.append(record)
        self._completed_items += 1

    def record_item(
        self, item_id: str, duration: float, item_size: Optional[int] = None
    ) -> None:
        """记录一个处理项

        Args:
            item_id: 项 ID
            duration: 耗时（秒）
            item_size: 项大小
        """
        now = time.time()
        record = ProcessingRecord(
            item_id=item_id,
            start_time=now - duration,
            end_time=now,
            duration=duration,
            item_size=item_size,
        )
        self.add_record(record)

    def get_average_duration(self) -> Optional[float]:
        """获取平均处理时间

        使用加权平均，最近的记录权重更高

        Returns:
            平均处理时间（秒），样本不足返回 None
        """
        if len(self.records) < self.min_samples:
            return None

        # 加权平均：最近的权重更高
        total_weight = 0
        weighted_sum = 0

        for i, record in enumerate(self.records):
            weight = i + 1  # 越新的权重越大
            weighted_sum += record.duration * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else None

    def get_eta_seconds(self) -> Optional[float]:
        """获取预计剩余时间（秒）

        Returns:
            剩余秒数，无法估算返回 None
        """
        avg_duration = self.get_average_duration()
        if avg_duration is None:
            return None

        remaining = self._total_items - self._completed_items
        if remaining <= 0:
            return 0

        return avg_duration * remaining

    def get_eta_datetime(self) -> Optional[datetime]:
        """获取预计完成时间点

        Returns:
            完成时间的 datetime 对象
        """
        eta_seconds = self.get_eta_seconds()
        if eta_seconds is None:
            return None

        return datetime.now() + timedelta(seconds=eta_seconds)

    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息

        Returns:
            包含进度信息的字典
        """
        elapsed = time.time() - self._start_time if self._start_time else 0
        eta_seconds = self.get_eta_seconds()

        return {
            "total": self._total_items,
            "completed": self._completed_items,
            "remaining": self._total_items - self._completed_items,
            "percent": (self._completed_items / self._total_items * 100)
            if self._total_items > 0
            else 0,
            "elapsed_seconds": elapsed,
            "eta_seconds": eta_seconds,
            "average_duration": self.get_average_duration(),
        }


class ProgressTracker:
    """进度追踪器

    整合 ETACalculator，提供易用的进度追踪接口
    """

    def __init__(self, total: int = 0, task_name: str = "processing"):
        """初始化进度追踪器

        Args:
            total: 总任务数
            task_name: 任务名称（用于日志）
        """
        self.task_name = task_name
        self.eta_calculator = ETACalculator()
        if total > 0:
            self.eta_calculator.set_total(total)

    def set_total(self, total: int) -> None:
        """设置总任务数"""
        self.eta_calculator.set_total(total)

    def record_completed(
        self, item_id: str, duration: float, item_size: Optional[int] = None
    ) -> None:
        """记录完成一个任务

        Args:
            item_id: 任务 ID
            duration: 耗时（秒）
            item_size: 任务大小
        """
        self.eta_calculator.record_item(item_id, duration, item_size)

    def get_status_message(self) -> str:
        """获取状态消息（国际化）

        Returns:
            格式化的状态消息
        """
        progress = self.eta_calculator.get_progress()

        # 基础进度信息
        completed = progress["completed"]
        total = progress["total"]
        percent = progress["percent"]

        # ETA 信息
        eta_seconds = progress["eta_seconds"]
        if eta_seconds is not None:
            eta_str = format_duration(eta_seconds)
            return t(
                "progress.status_with_eta",
                completed=completed,
                total=total,
                percent=f"{percent:.1f}",
                eta=eta_str,
            )
        else:
            return t(
                "progress.status_no_eta",
                completed=completed,
                total=total,
                percent=f"{percent:.1f}",
            )

    def get_eta_message(self) -> Optional[str]:
        """获取 ETA 消息（国际化）

        Returns:
            格式化的 ETA 消息，无法估算返回 None
        """
        eta_seconds = self.eta_calculator.get_eta_seconds()
        if eta_seconds is None:
            return None

        return format_eta(eta_seconds)


def format_duration(seconds: float) -> str:
    """格式化时长为可读字符串（国际化）

    Args:
        seconds: 秒数

    Returns:
        格式化的时长字符串
    """
    if seconds < 60:
        return t("time.seconds", count=int(seconds))
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if secs > 0:
            return t("time.minutes_seconds", minutes=minutes, seconds=secs)
        return t("time.minutes", count=minutes)
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if minutes > 0:
            return t("time.hours_minutes", hours=hours, minutes=minutes)
        return t("time.hours", count=hours)


def format_eta(seconds: float) -> str:
    """格式化 ETA 为可读字符串（国际化）

    Args:
        seconds: 剩余秒数

    Returns:
        格式化的 ETA 字符串
    """
    if seconds <= 0:
        return t("eta.complete_soon")

    duration_str = format_duration(seconds)
    return t("eta.remaining", duration=duration_str)
