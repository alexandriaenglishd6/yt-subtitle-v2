"""
增量管理模块
使用 yt-dlp --download-archive 格式记录已成功处理的视频
"""
import re
import hashlib
import json
from pathlib import Path
from typing import Set, Optional
from datetime import datetime

from config.manager import ConfigManager
from core.logger import get_logger

logger = get_logger()


def _get_language_config_hash(language_config) -> Optional[str]:
    """计算语言配置的哈希值
    
    Args:
        language_config: LanguageConfig 对象或字典
    
    Returns:
        语言配置的哈希值（16 位十六进制字符串），如果 language_config 为 None 则返回 None
    """
    if language_config is None:
        return None
    
    try:
        # 如果是 LanguageConfig 对象，转换为字典
        if hasattr(language_config, 'to_dict'):
            config_dict = language_config.to_dict()
        elif isinstance(language_config, dict):
            config_dict = language_config
        else:
            return None
        
        # 只考虑影响输出的配置项（忽略 UI 语言）
        relevant_config = {
            "subtitle_target_languages": sorted(config_dict.get("subtitle_target_languages", [])),
            "summary_language": config_dict.get("summary_language"),
            "source_language": config_dict.get("source_language"),
            "bilingual_mode": config_dict.get("bilingual_mode"),
            "translation_strategy": config_dict.get("translation_strategy"),
            "subtitle_format": config_dict.get("subtitle_format"),
        }
        
        # 计算哈希值
        config_json = json.dumps(relevant_config, sort_keys=True)
        hash_obj = hashlib.md5(config_json.encode('utf-8'))
        return hash_obj.hexdigest()[:16]  # 使用前 16 位，足够区分不同的配置
    except Exception as e:
        logger.warning(f"计算语言配置哈希值失败: {e}")
        return None


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
    
    def is_processed(self, video_id: str, archive_path: Path, language_config_hash: Optional[str] = None) -> bool:
        """判断视频是否已处理过
        
        Args:
            video_id: 视频 ID
            archive_path: archive 文件路径
            language_config_hash: 语言配置的哈希值（可选），如果提供则检查是否匹配
        
        Returns:
            如果视频已处理过且语言配置匹配（如果提供了哈希值）则返回 True，否则返回 False
        """
        if not archive_path.exists():
            return False
        
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                content = f.read()
                # yt-dlp archive 格式：youtube <video_id> 或 youtube <video_id> <ext>
                # 扩展格式（如果包含语言配置哈希）：youtube <video_id> # lang_hash=<hash>
                pattern = rf"youtube\s+{re.escape(video_id)}(\s|$)"
                if not re.search(pattern, content):
                    return False
                
                # 如果提供了语言配置哈希，检查是否匹配
                if language_config_hash:
                    # 查找该视频 ID 对应的语言配置哈希
                    lang_hash_pattern = rf"youtube\s+{re.escape(video_id)}\s+(?:[^\s]+\s+)?#\s*lang_hash=([a-f0-9]+)"
                    match = re.search(lang_hash_pattern, content)
                    if match:
                        stored_hash = match.group(1)
                        # 如果哈希值不匹配，说明语言配置已变化，需要重新处理
                        if stored_hash != language_config_hash:
                            return False
                    else:
                        # 如果 archive 中没有语言配置哈希，说明是旧格式，为了安全起见，重新处理
                        return False
                
                return True
        except Exception as e:
            logger.warning(f"读取 archive 文件失败: {e}")
            return False
    
    def mark_as_processed(self, video_id: str, archive_path: Path, language_config_hash: Optional[str] = None) -> None:
        """标记视频为已处理
        
        Args:
            video_id: 视频 ID
            archive_path: archive 文件路径
            language_config_hash: 语言配置的哈希值（可选），如果提供则记录到 archive 中
        """
        from core.failure_logger import _append_line_safe
        
        try:
            # yt-dlp archive 格式：youtube <video_id>
            # 扩展格式（如果提供了语言配置哈希）：youtube <video_id> # lang_hash=<hash>
            if language_config_hash:
                line = f"youtube {video_id} # lang_hash={language_config_hash}\n"
            else:
                line = f"youtube {video_id}\n"
            # 使用线程安全的追加写入
            if not _append_line_safe(archive_path, line):
                raise Exception("追加写入失败")
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
                    logger.info(f"发现旧 archive 文件: {old_path}，开始迁移...")
                    
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
                        logger.info(f"已备份旧文件到: {backup_path}")
                        
                        # 删除旧文件
                        old_path.unlink()
                        logger.info(f"已删除旧文件: {old_path}")
                        
                        migrated = True
                    else:
                        # 空文件，直接删除
                        old_path.unlink()
                        logger.info(f"删除空的旧文件: {old_path}")
                        
                except Exception as e:
                    logger.warning(f"迁移旧 archive 文件失败 ({old_path}): {e}")
        
        if migrated:
            logger.info(
                f"旧 archive 文件已迁移到: {migrated_file}\n"
                f"注意：此文件包含所有历史记录，新的频道/批次 archive 文件将按来源隔离。"
            )

