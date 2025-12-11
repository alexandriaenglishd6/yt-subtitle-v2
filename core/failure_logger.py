"""
失败记录模块
符合 error_handling.md 规范的失败记录系统
记录所有下载/翻译/摘要失败的视频，写入 out/failed_detail.log 和 out/failed_urls.txt
"""
from pathlib import Path
from typing import Optional
from datetime import datetime
import os

from core.logger import get_logger
from core.exceptions import ErrorType

logger = get_logger()


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
                logger.warning(f"读取原文件失败，将创建新文件: {e}")
        
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
        logger.error(f"原子写文件失败 ({file_path}): {e}")
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
            # 原子写详细日志
            _atomic_write(self.detail_log_path, detail_line, mode="a")
            
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
                # 原子写 URL 列表
                _atomic_write(self.urls_file_path, url + "\n", mode="a")
            
            # 静默记录（不阻塞主流程，不弹窗）
            logger.warning(
                f"失败记录已写入: {video_id} - {reason}",
                video_id=video_id,
                error_type=error_type.value
            )
            
        except Exception as e:
            # 失败记录写入失败不应该影响主流程
            logger.error(f"写入失败记录失败: {e}", video_id=video_id)
    
    def log_download_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        batch_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None
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
            stage="download"
        )
    
    def log_translation_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        batch_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None
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
            stage="translate"
        )
    
    def log_summary_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        batch_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None
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
            stage="summarize"
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
            logger.info("失败记录已清空")
        except Exception as e:
            logger.error(f"清空失败记录失败: {e}")
