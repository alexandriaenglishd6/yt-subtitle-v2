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

        # 迁移旧位置的 archive.txt 文件
        self._migrate_old_archive()

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

    def get_playlist_archive_path(self, playlist_id: str) -> Path:
        """获取播放列表 archive 文件路径

        Args:
            playlist_id: 播放列表 ID

        Returns:
            archive 文件路径
        """
        return self.archives_dir / f"playlist_{playlist_id}.txt"

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
            logger.warning_i18n("archive_read_failed", error=str(e))
            return False

    def mark_as_processed(self, video_id: str, archive_path: Path) -> None:
        """标记视频为已处理

        Args:
            video_id: 视频 ID
            archive_path: archive 文件路径
        """
        from core.failure_logger import _append_line_safe

        try:
            # yt-dlp archive 格式：youtube <video_id>
            # 使用线程安全的追加写入
            if not _append_line_safe(archive_path, f"youtube {video_id}\n"):
                from core.exceptions import AppException, ErrorType
                from core.logger import translate_exception

                raise AppException(
                    message=translate_exception("exception.append_write_failed"),
                    error_type=ErrorType.FILE_IO,
                )
        except Exception as e:
            logger.error_i18n("archive_write_failed", error=str(e))

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
            logger.warning_i18n("archive_read_failed", error=str(e))

        return processed

    def filter_unprocessed(
        self, video_ids: list[str], archive_path: Path, force: bool = False
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
            logger.info_i18n("force_rerun_mode")
            return video_ids

        if not archive_path.exists():
            logger.info_i18n("archive_not_exists", count=len(video_ids))
            return video_ids

        processed = self.get_processed_video_ids(archive_path)
        unprocessed = [vid for vid in video_ids if vid not in processed]

        skipped_count = len(video_ids) - len(unprocessed)
        if skipped_count > 0:
            logger.info_i18n(
                "incremental_skip_processed",
                skipped=skipped_count,
                remaining=len(unprocessed),
            )

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
                logger.info_i18n("archive_cleared", path=str(archive_path))
            return True
        except Exception as e:
            logger.error_i18n("archive_clear_failed", error=str(e))
            return False

    def get_or_create_channel_archive(
        self, channel_id: Optional[str]
    ) -> Optional[Path]:
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

    def _migrate_old_archive(self) -> None:
        """迁移旧位置的 archive.txt 文件到新位置

        检查以下旧位置：
        1. out/archive.txt（项目根目录下的 out 文件夹）
        2. 其他可能的旧位置

        如果发现旧文件，将其内容合并到通用的迁移文件中，并备份旧文件。
        """
        import shutil

        # 可能的旧位置列表
        old_locations = [
            Path("out") / "archive.txt",  # 项目根目录下的 out/archive.txt
            Path("archive.txt"),  # 项目根目录下的 archive.txt
        ]

        migrated_file = self.archives_dir / "migrated_archive.txt"
        migrated = False

        for old_path in old_locations:
            if old_path.exists() and old_path.is_file():
                try:
                    logger.info_i18n("archive_old_found", path=str(old_path))

                    # 读取旧文件内容
                    with open(old_path, "r", encoding="utf-8") as f:
                        old_content = f.read()

                    if old_content.strip():
                        # 如果迁移文件已存在，合并内容（去重）
                        if migrated_file.exists():
                            with open(migrated_file, "r", encoding="utf-8") as f:
                                existing_content = f.read()

                            # 合并内容，去重
                            existing_lines = set(existing_content.strip().split("\n"))
                            new_lines = set(old_content.strip().split("\n"))
                            merged_lines = sorted(existing_lines | new_lines)

                            with open(migrated_file, "w", encoding="utf-8") as f:
                                f.write("\n".join(merged_lines) + "\n")
                        else:
                            # 直接写入迁移文件
                            with open(migrated_file, "w", encoding="utf-8") as f:
                                f.write(old_content)

                        # 备份旧文件（重命名为 .bak）
                        backup_path = old_path.with_suffix(".txt.bak")
                        shutil.copy2(old_path, backup_path)
                        logger.info_i18n("archive_backed_up", path=str(backup_path))

                        # 删除旧文件
                        old_path.unlink()
                        logger.info_i18n("archive_old_deleted", path=str(old_path))

                        migrated = True
                    else:
                        # 空文件，直接删除
                        old_path.unlink()
                        logger.info_i18n("archive_empty_deleted", path=str(old_path))

                except Exception as e:
                    logger.warning_i18n(
                        "archive_migration_failed", path=str(old_path), error=str(e)
                    )

        if migrated:
            logger.info(
                f"旧 archive 文件已迁移到: {migrated_file}\n"
                f"注意：此文件包含所有历史记录，新的频道/批次 archive 文件将按来源隔离。"
            )
