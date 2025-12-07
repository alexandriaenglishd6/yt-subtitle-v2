"""
增量管理模块
使用 yt-dlp --download-archive 格式记录已成功处理的视频
"""
import re
from pathlib import Path
from typing import Set, Optional
from datetime import datetime

from config.manager import ConfigManager
from core.logger import get_logger

logger = get_logger()


class IncrementalManager:
    """增量管理器
    
    负责管理已成功处理的视频记录，使用 yt-dlp --download-archive 格式
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """初始化增量管理器
        
        Args:
            config_manager: ConfigManager 实例，如果为 None 则创建新实例
        """
        if config_manager is None:
            config_manager = ConfigManager()
        self.config_manager = config_manager
        self.archives_dir = config_manager.get_archives_dir()
        self.archives_dir.mkdir(parents=True, exist_ok=True)
    
    def get_channel_archive_path(self, channel_id: str) -> Path:
        """获取频道 archive 文件路径
        
        Args:
            channel_id: 频道 ID（如 "UCxxxxxx"）
        
        Returns:
            archive 文件路径
        """
        return self.archives_dir / f"{channel_id}.txt"
    
    def get_batch_archive_path(self, batch_id: Optional[str] = None) -> Path:
        """获取 URL 列表批次的 archive 文件路径
        
        Args:
            batch_id: 批次 ID，如果为 None 则自动生成（格式：batch_YYYYMMDD_HHMMSS）
        
        Returns:
            archive 文件路径
        """
        if batch_id is None:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return self.archives_dir / f"{batch_id}.txt"
    
    def is_processed(self, video_id: str, archive_path: Path) -> bool:
        """判断视频是否已处理过
        
        Args:
            video_id: 视频 ID
            archive_path: archive 文件路径
        
        Returns:
            如果视频已处理过则返回 True，否则返回 False
        """
        if not archive_path.exists():
            return False
        
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                content = f.read()
                # yt-dlp archive 格式：youtube <video_id> 或 youtube <video_id> <ext>
                # 检查是否包含该 video_id
                pattern = rf"youtube\s+{re.escape(video_id)}(\s|$)"
                return bool(re.search(pattern, content))
        except Exception as e:
            logger.warning(f"读取 archive 文件失败: {e}")
            return False
    
    def mark_as_processed(self, video_id: str, archive_path: Path) -> None:
        """标记视频为已处理
        
        Args:
            video_id: 视频 ID
            archive_path: archive 文件路径
        """
        try:
            # yt-dlp archive 格式：youtube <video_id>
            # 使用追加模式写入
            with open(archive_path, "a", encoding="utf-8") as f:
                f.write(f"youtube {video_id}\n")
        except Exception as e:
            logger.error(f"写入 archive 文件失败: {e}")
    
    def get_processed_video_ids(self, archive_path: Path) -> Set[str]:
        """获取已处理的视频 ID 集合
        
        Args:
            archive_path: archive 文件路径
        
        Returns:
            已处理的视频 ID 集合
        """
        processed = set()
        
        if not archive_path.exists():
            return processed
        
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # 解析 yt-dlp archive 格式：youtube <video_id> 或 youtube <video_id> <ext>
                    match = re.match(r"youtube\s+(\S+)", line)
                    if match:
                        video_id = match.group(1)
                        processed.add(video_id)
        except Exception as e:
            logger.warning(f"读取 archive 文件失败: {e}")
        
        return processed
    
    def filter_unprocessed(
        self,
        video_ids: list[str],
        archive_path: Path,
        force: bool = False
    ) -> list[str]:
        """过滤出未处理的视频 ID 列表
        
        Args:
            video_ids: 视频 ID 列表
            archive_path: archive 文件路径
            force: 如果为 True，则忽略增量，返回所有视频 ID
        
        Returns:
            未处理的视频 ID 列表
        """
        if force:
            logger.info("强制重跑模式：忽略增量记录，处理所有视频")
            return video_ids
        
        if not archive_path.exists():
            logger.info(f"Archive 文件不存在，将处理所有 {len(video_ids)} 个视频")
            return video_ids
        
        processed = self.get_processed_video_ids(archive_path)
        unprocessed = [vid for vid in video_ids if vid not in processed]
        
        skipped_count = len(video_ids) - len(unprocessed)
        if skipped_count > 0:
            logger.info(f"增量处理：跳过 {skipped_count} 个已处理视频，剩余 {len(unprocessed)} 个待处理")
        
        return unprocessed
    
    def clear_archive(self, archive_path: Path) -> bool:
        """清空 archive 文件（用于强制重跑）
        
        Args:
            archive_path: archive 文件路径
        
        Returns:
            如果成功清空则返回 True
        """
        try:
            if archive_path.exists():
                archive_path.unlink()
                logger.info(f"已清空 archive 文件: {archive_path}")
            return True
        except Exception as e:
            logger.error(f"清空 archive 文件失败: {e}")
            return False
    
    def get_or_create_channel_archive(self, channel_id: Optional[str]) -> Optional[Path]:
        """获取或创建频道 archive 文件路径
        
        Args:
            channel_id: 频道 ID，如果为 None 则返回 None
        
        Returns:
            archive 文件路径，如果 channel_id 为 None 则返回 None
        """
        if not channel_id:
            return None
        archive_path = self.get_channel_archive_path(channel_id)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        return archive_path

