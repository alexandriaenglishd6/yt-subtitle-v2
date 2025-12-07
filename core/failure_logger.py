"""
失败记录模块
记录所有下载/翻译/摘要失败的视频，写入 out/failed_detail.log 和 out/failed_urls.txt
"""
from pathlib import Path
from typing import Optional
from datetime import datetime

from core.logger import get_logger

logger = get_logger()


class FailureLogger:
    """失败记录器
    
    负责记录所有失败的视频，写入两个文件：
    - failed_detail.log：详细失败记录（时间戳、频道ID、视频ID、URL、原因）
    - failed_urls.txt：仅包含失败 URL，一行一个（方便用户复制重跑）
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
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None,
        stage: Optional[str] = None
    ) -> None:
        """记录失败
        
        Args:
            video_id: 视频 ID
            url: 视频 URL
            reason: 失败原因
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
            stage: 失败阶段（如 "download", "translate", "summarize"）（可选）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建详细记录行
        detail_parts = [f"[{timestamp}]"]
        
        if channel_id:
            detail_parts.append(f"[频道:{channel_id}]")
        elif channel_name:
            detail_parts.append(f"[频道:{channel_name}]")
        
        detail_parts.append(f"[视频:{video_id}]")
        
        if stage:
            detail_parts.append(f"[阶段:{stage}]")
        
        detail_parts.append(url)
        detail_parts.append(f"- 原因：{reason}")
        
        detail_line = " ".join(detail_parts)
        
        try:
            # 追加写入详细日志
            with open(self.detail_log_path, "a", encoding="utf-8") as f:
                f.write(detail_line + "\n")
            
            # 追加写入 URL 列表（如果 URL 不存在）
            # 检查是否已存在（避免重复）
            existing_urls = set()
            if self.urls_file_path.exists():
                with open(self.urls_file_path, "r", encoding="utf-8") as f:
                    existing_urls = set(line.strip() for line in f if line.strip())
            
            if url not in existing_urls:
                with open(self.urls_file_path, "a", encoding="utf-8") as f:
                    f.write(url + "\n")
            
            logger.warning(
                f"失败记录已写入: {video_id} - {reason}",
                video_id=video_id
            )
            
        except Exception as e:
            logger.error(f"写入失败记录失败: {e}")
    
    def log_download_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None
    ) -> None:
        """记录下载失败（便捷方法）
        
        Args:
            video_id: 视频 ID
            url: 视频 URL
            reason: 失败原因
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
        """
        self.log_failure(
            video_id=video_id,
            url=url,
            reason=reason,
            channel_id=channel_id,
            channel_name=channel_name,
            stage="download"
        )
    
    def log_translation_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None
    ) -> None:
        """记录翻译失败（便捷方法）
        
        Args:
            video_id: 视频 ID
            url: 视频 URL
            reason: 失败原因
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
        """
        self.log_failure(
            video_id=video_id,
            url=url,
            reason=reason,
            channel_id=channel_id,
            channel_name=channel_name,
            stage="translate"
        )
    
    def log_summary_failure(
        self,
        video_id: str,
        url: str,
        reason: str,
        channel_id: Optional[str] = None,
        channel_name: Optional[str] = None
    ) -> None:
        """记录摘要失败（便捷方法）
        
        Args:
            video_id: 视频 ID
            url: 视频 URL
            reason: 失败原因
            channel_id: 频道 ID（可选）
            channel_name: 频道名称（可选）
        """
        self.log_failure(
            video_id=video_id,
            url=url,
            reason=reason,
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

