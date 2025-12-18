"""
失败记录模块
符合 error_handling.md 规范的失败记录系统
记录所有下载/翻译/摘要失败的视频，写入 out/failed_detail.log 和 out/failed_urls.txt
同时写入结构化 JSON 记录到 out/failed_records.json（R2-1 任务）
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import os
import threading
import json

from core.logger import get_logger
from core.exceptions import ErrorType

logger = get_logger()

# 全局锁字典：每个文件路径对应一个 Lock，用于线程安全的追加写入
_file_locks: dict[Path, threading.Lock] = {}
_locks_lock = threading.Lock()  # 保护 _file_locks 字典本身的锁


def _append_line_safe(file_path: Path, line: str) -> bool:
    """线程安全的追加写入单行文本

    使用每个文件路径对应的 Lock 确保并发安全。
    符合 R0-4 任务要求：所有追加写入统一调用此函数。

    Args:
        file_path: 目标文件路径
        line: 要追加的行（应包含换行符，如 "content\n"）

    Returns:
        是否成功
    """
    # 确保目录存在
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 获取或创建该文件对应的 Lock
    with _locks_lock:
        if file_path not in _file_locks:
            _file_locks[file_path] = threading.Lock()
        file_lock = _file_locks[file_path]

    # 使用文件锁进行线程安全的追加写入
    try:
        with file_lock:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())  # 强制刷新到磁盘
        return True
    except Exception as e:
        logger.error_i18n(
            "thread_safe_append_failed", file_path=str(file_path), error=str(e)
        )
        return False


def _atomic_write(file_path: Path, content: str, mode: str = "a") -> bool:
    """原子写文件（先写.tmp，成功后rename）

    符合 error_handling.md 的原子落盘要求：
    - 先写 .tmp 文件
    - 成功后 atomic rename
    - 失败清理 .tmp

    Args:
        file_path: 目标文件路径
        content: 要写入的内容
        mode: 写入模式（"a" 追加，"w" 覆盖）

    Returns:
        是否成功
    """
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")

    try:
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 如果是追加模式且原文件存在，先读取原文件内容
        existing_content = ""
        if mode == "a" and file_path.exists():
            try:
                existing_content = file_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning_i18n("read_original_file_failed", error=str(e))

        # 写入临时文件（追加模式下先写入原内容，再写入新内容）
        with open(tmp_path, "w", encoding="utf-8") as f:
            if mode == "a":
                f.write(existing_content)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # 强制刷新到磁盘

        # 原子重命名
        tmp_path.replace(file_path)
        return True
    except Exception as e:
        # 失败时清理临时文件
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        logger.error_i18n(
            "atomic_write_file_failed", file_path=str(file_path), error=str(e)
        )
        return False


class FailureLogger:
    """失败记录器

    符合 error_handling.md 规范：
    - 仅当"视频级任务最终失败"时写入
    - 格式：[时间戳] [batch:<batch_id>] [video:<video_id>] <url>  error=<error_type>  msg=<简要原因>
    - 使用原子写文件机制
    - 静默追加，不阻塞主流程
    """

    def __init__(self, base_output_dir: Path):
        """初始化失败记录器

        Args:
            base_output_dir: 基础输出目录（通常是 "out"）
        """
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

        self.detail_log_path = self.base_output_dir / "failed_detail.log"
        self.urls_file_path = self.base_output_dir / "failed_urls.txt"
        self.json_records_path = (
            self.base_output_dir / "failed_records.json"
        )  # R2-1: 结构化 JSON 记录

    def log_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        batch_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> None:
        """记录失败

        符合 error_handling.md 格式：
        [时间戳] [batch:<batch_id>] [video:<video_id>] <url>  error=<error_type>  msg=<简要原因>

        Args:
            video_id: 视频 ID
            url: 视频 URL
            reason: 失败原因（简要描述）
            error_type: 错误类型（ErrorType 枚举）
            batch_id: 批次ID（run_id，格式：YYYYMMDD_HHMMSS）
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
            stage: 失败阶段（如 "download", "translate", "summarize"）（可选）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建详细记录行（符合 error_handling.md 格式）
        detail_parts = [f"[{timestamp}]"]

        # batch_id（run_id）
        if batch_id:
            detail_parts.append(f"[batch:{batch_id}]")

        # video_id
        detail_parts.append(f"[video:{video_id}]")

        # URL
        detail_parts.append(url)

        # error_type
        detail_parts.append(f"error={error_type.value}")

        # 简要原因（msg）
        detail_parts.append(f"msg={reason}")

        # 可选：阶段信息（如果提供）
        if stage:
            detail_parts.append(f"stage={stage}")

        detail_line = " ".join(detail_parts) + "\n"

        try:
            # 使用线程安全的追加写入详细日志
            _append_line_safe(self.detail_log_path, detail_line)

            # 追加写入 URL 列表（如果 URL 不存在）
            # 检查是否已存在（避免重复）
            existing_urls = set()
            if self.urls_file_path.exists():
                try:
                    with open(self.urls_file_path, "r", encoding="utf-8") as f:
                        existing_urls = set(line.strip() for line in f if line.strip())
                except Exception:
                    pass  # 读取失败不影响主流程

            if url not in existing_urls:
                # 使用线程安全的追加写入
                _append_line_safe(self.urls_file_path, url + "\n")

            # R2-1: 写入结构化 JSON 记录
            self._write_json_record(
                video_id=video_id,
                url=url,
                stage=stage or "unknown",
                error_type=error_type.value,
                timestamp=timestamp,
                run_id=batch_id,
                reason=reason,
                channel_id=channel_id,
                channel_name=channel_name,
            )

            # 静默记录（不阻塞主流程，不弹窗）
            logger.warning_i18n(
                "failure_record_written",
                video_id=video_id,
                reason=reason,
                error_type=error_type.value,
            )

        except Exception as e:
            # 失败记录写入失败不应该影响主流程
            logger.error_i18n(
                "write_failure_record_failed", error=str(e), video_id=video_id
            )

    def log_download_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        batch_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
    ) -> None:
        """记录下载失败（便捷方法）

        Args:
            video_id: 视频 ID
            url: 视频 URL
            reason: 失败原因
            error_type: 错误类型
            batch_id: 批次ID
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
        """
        self.log_failure(
            video_id=video_id,
            url=url,
            reason=reason,
            error_type=error_type,
            batch_id=batch_id,
            channel_id=channel_id,
            channel_name=channel_name,
            stage="download",
        )

    def log_translation_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        batch_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
    ) -> None:
        """记录翻译失败（便捷方法）

        Args:
            video_id: 视频 ID
            url: 视频 URL
            reason: 失败原因
            error_type: 错误类型
            batch_id: 批次ID
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
        """
        self.log_failure(
            video_id=video_id,
            url=url,
            reason=reason,
            error_type=error_type,
            batch_id=batch_id,
            channel_id=channel_id,
            channel_name=channel_name,
            stage="translate",
        )

    def log_summary_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        batch_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
    ) -> None:
        """记录摘要失败（便捷方法）

        Args:
            video_id: 视频 ID
            url: 视频 URL
            reason: 失败原因
            error_type: 错误类型
            batch_id: 批次ID
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
        """
        self.log_failure(
            video_id=video_id,
            url=url,
            reason=reason,
            error_type=error_type,
            batch_id=batch_id,
            channel_id=channel_id,
            channel_name=channel_name,
            stage="summarize",
        )

    def _write_json_record(
        self,
        video_id: str,
        url: str,
        stage: str,
        error_type: str,
        timestamp: str,
        run_id: Optional[str],
        reason: str,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
    ) -> None:
        """写入结构化 JSON 记录（R2-1 任务）

        使用 JSONL 格式（每行一个 JSON 对象），便于追加写入和解析。

        Args:
            video_id: 视频 ID
            url: 视频 URL
            stage: 失败阶段（detect/download/translate/summarize/output）
            error_type: 错误类型（字符串）
            timestamp: 时间戳（格式：YYYY-MM-DD HH:MM:SS）
            run_id: 批次ID（run_id，格式：YYYYMMDD_HHMMSS）
            reason: 失败原因
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
        """
        try:
            # 构建 JSON 记录对象
            record: Dict[str, Any] = {
                "video_id": video_id,
                "url": url,
                "stage": stage,
                "error_type": error_type,
                "timestamp": timestamp,
            }

            # 可选字段
            if run_id:
                record["run_id"] = run_id
            if channel_id:
                record["channel_id"] = channel_id
            if channel_name:
                record["channel_name"] = channel_name
            if reason:
                record["reason"] = reason

            # 将 JSON 对象序列化为字符串（紧凑格式，无缩进）
            json_line = json.dumps(record, ensure_ascii=False) + "\n"

            # 使用线程安全的追加写入
            _append_line_safe(self.json_records_path, json_line)

        except Exception as e:
            # JSON 记录写入失败不应该影响主流程
            logger.debug_i18n(
                "write_json_record_failed", error=str(e), video_id=video_id
            )

    def clear_logs(self) -> None:
        """清空失败记录（谨慎使用）

        用于测试或用户手动清空
        """
        try:
            if self.detail_log_path.exists():
                self.detail_log_path.unlink()
            if self.urls_file_path.exists():
                self.urls_file_path.unlink()
            if self.json_records_path.exists():
                self.json_records_path.unlink()
            logger.info_i18n("failure_records_cleared")
        except Exception as e:
            logger.error_i18n("clear_failure_records_failed", error=str(e))
