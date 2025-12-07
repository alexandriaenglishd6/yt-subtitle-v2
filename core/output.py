"""
输出模块
按 v2_final_plan.md 规定的结构创建目录和文件
"""
import json
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger

logger = get_logger()


class OutputWriter:
    """输出写入器
    
    负责按统一结构创建目录和文件，使用语言代码命名
    """
    
    def __init__(self, base_output_dir: Path):
        """初始化输出写入器
        
        Args:
            base_output_dir: 基础输出目录（通常是 "out"）
        """
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
    
    def get_video_output_dir(
        self,
        video_info: VideoInfo,
        channel_name: Optional[str] = None,
        channel_id: Optional[str] = None
    ) -> Path:
        """获取视频的输出目录路径
        
        根据模式确定目录结构：
        - 频道模式：out/频道名称 [UCxxxxxx]/视频ID 标题/
        - 单视频/URL列表模式：out/视频ID 标题/
        
        Args:
            video_info: 视频信息
            channel_name: 频道名称（频道模式时提供）
            channel_id: 频道 ID（频道模式时提供）
        
        Returns:
            视频输出目录路径
        """
        # 清理标题中的非法字符（Windows/Linux 文件系统不允许的字符）
        safe_title = self._sanitize_filename(video_info.title)
        video_dir_name = f"{video_info.video_id}  {safe_title}"
        
        if channel_name and channel_id:
            # 频道模式：out/频道名称 [UCxxxxxx]/视频ID 标题/
            channel_dir_name = f"{channel_name} [{channel_id}]"
            channel_dir = self.base_output_dir / channel_dir_name
            video_dir = channel_dir / video_dir_name
        else:
            # 单视频/URL列表模式：out/视频ID 标题/
            video_dir = self.base_output_dir / video_dir_name
        
        return video_dir
    
    def write_original_subtitle(
        self,
        video_dir: Path,
        subtitle_path: Path,
        source_language: str
    ) -> Path:
        """写入原始字幕文件
        
        Args:
            video_dir: 视频输出目录
            subtitle_path: 源字幕文件路径
            source_language: 源语言代码
        
        Returns:
            写入的文件路径
        """
        video_dir.mkdir(parents=True, exist_ok=True)
        target_path = video_dir / f"original.{source_language}.srt"
        
        try:
            import shutil
            shutil.copy2(subtitle_path, target_path)
            logger.debug(f"已写入原始字幕: {target_path.name}")
            return target_path
        except Exception as e:
            logger.error(f"写入原始字幕失败: {e}")
            raise
    
    def write_translated_subtitle(
        self,
        video_dir: Path,
        subtitle_path: Path,
        target_language: str
    ) -> Path:
        """写入翻译字幕文件
        
        Args:
            video_dir: 视频输出目录
            subtitle_path: 源字幕文件路径
            target_language: 目标语言代码
        
        Returns:
            写入的文件路径
        """
        video_dir.mkdir(parents=True, exist_ok=True)
        target_path = video_dir / f"translated.{target_language}.srt"
        
        try:
            import shutil
            shutil.copy2(subtitle_path, target_path)
            logger.debug(f"已写入翻译字幕: {target_path.name}")
            return target_path
        except Exception as e:
            logger.error(f"写入翻译字幕失败: {e}")
            raise
    
    def write_summary(
        self,
        video_dir: Path,
        summary_path: Path,
        summary_language: str
    ) -> Path:
        """写入摘要文件
        
        Args:
            video_dir: 视频输出目录
            summary_path: 源摘要文件路径
            summary_language: 摘要语言代码
        
        Returns:
            写入的文件路径
        """
        video_dir.mkdir(parents=True, exist_ok=True)
        target_path = video_dir / f"summary.{summary_language}.md"
        
        try:
            import shutil
            shutil.copy2(summary_path, target_path)
            logger.debug(f"已写入摘要: {target_path.name}")
            return target_path
        except Exception as e:
            logger.error(f"写入摘要失败: {e}")
            raise
    
    def write_metadata(
        self,
        video_dir: Path,
        video_info: VideoInfo,
        detection_result: DetectionResult,
        language_config: LanguageConfig,
        download_result: Dict[str, Optional[Path]],
        translation_result: Dict[str, Optional[Path]],
        summary_path: Optional[Path]
    ) -> Path:
        """写入元数据文件
        
        Args:
            video_dir: 视频输出目录
            video_info: 视频信息
            detection_result: 字幕检测结果
            language_config: 语言配置
            download_result: 下载结果
            translation_result: 翻译结果
            summary_path: 摘要文件路径（可选）
        
        Returns:
            写入的文件路径
        """
        video_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = video_dir / "metadata.json"
        
        try:
            # 构建元数据
            metadata = {
                "video_id": video_info.video_id,
                "url": video_info.url,
                "title": video_info.title,
                "channel_id": video_info.channel_id,
                "channel_name": video_info.channel_name,
                "duration": video_info.duration,
                "upload_date": video_info.upload_date,
                "description": video_info.description,
                "detection": {
                    "has_subtitles": detection_result.has_subtitles,
                    "manual_languages": detection_result.manual_languages,
                    "auto_languages": detection_result.auto_languages,
                },
                "language_config": {
                    "ui_language": language_config.ui_language,
                    "subtitle_target_languages": language_config.subtitle_target_languages,
                    "summary_language": language_config.summary_language,
                    "bilingual_mode": language_config.bilingual_mode,
                    "translation_strategy": language_config.translation_strategy,
                },
                "files": {
                    "original": str(download_result.get("original")) if download_result.get("original") else None,
                    "official_translations": {
                        lang: str(path) if path else None
                        for lang, path in download_result.get("official_translations", {}).items()
                    },
                    "translated": {
                        lang: str(path) if path else None
                        for lang, path in translation_result.items()
                    },
                    "summary": str(summary_path) if summary_path else None,
                },
                "generated_at": datetime.now().isoformat(),
            }
            
            # 写入 JSON 文件
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"已写入元数据: {metadata_path.name}")
            return metadata_path
            
        except Exception as e:
            logger.error(f"写入元数据失败: {e}")
            raise
    
    def write_all(
        self,
        video_info: VideoInfo,
        detection_result: DetectionResult,
        language_config: LanguageConfig,
        download_result: Dict[str, Optional[Path]],
        translation_result: Dict[str, Optional[Path]],
        summary_path: Optional[Path],
        channel_name: Optional[str] = None,
        channel_id: Optional[str] = None
    ) -> Path:
        """写入所有输出文件（便捷方法）
        
        自动创建目录并写入所有文件：
        - 原始字幕
        - 翻译字幕
        - 摘要
        - 元数据
        
        Args:
            video_info: 视频信息
            detection_result: 字幕检测结果
            language_config: 语言配置
            download_result: 下载结果
            translation_result: 翻译结果
            summary_path: 摘要文件路径（可选）
            channel_name: 频道名称（频道模式时提供）
            channel_id: 频道 ID（频道模式时提供）
        
        Returns:
            视频输出目录路径
        """
        # 获取视频输出目录
        video_dir = self.get_video_output_dir(video_info, channel_name, channel_id)
        
        # 写入原始字幕
        original_path = download_result.get("original")
        if original_path and original_path.exists():
            # 从文件名提取语言代码，如果失败则从 detection_result 获取
            source_lang = self._extract_language_from_filename(original_path.name)
            if not source_lang and detection_result.manual_languages:
                source_lang = detection_result.manual_languages[0]
            elif not source_lang and detection_result.auto_languages:
                source_lang = detection_result.auto_languages[0]
            
            if source_lang:
                self.write_original_subtitle(video_dir, original_path, source_lang)
        
        # 写入翻译字幕
        for target_lang, translated_path in translation_result.items():
            if translated_path and translated_path.exists():
                self.write_translated_subtitle(video_dir, translated_path, target_lang)
        
        # 写入摘要
        if summary_path and summary_path.exists():
            summary_lang = language_config.summary_language
            self.write_summary(video_dir, summary_path, summary_lang)
        
        # 写入元数据
        self.write_metadata(
            video_dir,
            video_info,
            detection_result,
            language_config,
            download_result,
            translation_result,
            summary_path
        )
        
        logger.info(f"所有输出文件已写入: {video_dir}", video_id=video_info.video_id)
        return video_dir
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符
        
        Args:
            filename: 原始文件名
        
        Returns:
            清理后的文件名
        """
        # Windows/Linux 文件系统不允许的字符
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        
        result = filename
        for char in illegal_chars:
            result = result.replace(char, '_')
        
        # 移除前后空格和点
        result = result.strip(' .')
        
        # 限制长度（Windows 路径限制）
        if len(result) > 200:
            result = result[:200]
        
        return result
    
    def _extract_language_from_filename(self, filename: str) -> Optional[str]:
        """从文件名中提取语言代码
        
        例如：original.en.srt -> en
              translated.zh-CN.srt -> zh-CN
        
        Args:
            filename: 文件名
        
        Returns:
            语言代码，如果无法提取则返回 None
        """
        import re
        # 匹配 pattern.<lang>.srt 或 pattern.<lang>.md
        match = re.search(r'\.([a-z]{2}(?:-[A-Z]{2})?)\.(?:srt|md)$', filename, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

