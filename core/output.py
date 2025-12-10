"""
输出模块
按 v2_final_plan.md 规定的结构创建目录和文件
符合 error_handling.md 规范：文件IO错误映射，使用原子写文件
"""
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger
from core.exceptions import AppException, ErrorType
from core.failure_logger import _atomic_write

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
            # 使用原子写机制
            content = subtitle_path.read_text(encoding="utf-8")
            if not _atomic_write(target_path, content, mode="w"):
                raise AppException(
                    message=f"原子写原始字幕文件失败: {target_path}",
                    error_type=ErrorType.FILE_IO
                )
            logger.debug(f"已写入原始字幕: {target_path.name}")
            return target_path
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"写入原始字幕失败: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"写入原始字幕失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"写入原始字幕失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"写入原始字幕失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
    
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
            # 使用原子写机制
            content = subtitle_path.read_text(encoding="utf-8")
            if not _atomic_write(target_path, content, mode="w"):
                raise AppException(
                    message=f"原子写翻译字幕文件失败: {target_path}",
                    error_type=ErrorType.FILE_IO
                )
            logger.debug(f"已写入翻译字幕: {target_path.name}")
            return target_path
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"写入翻译字幕失败: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"写入翻译字幕失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"写入翻译字幕失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"写入翻译字幕失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
    
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
            # 使用原子写机制
            content = summary_path.read_text(encoding="utf-8")
            if not _atomic_write(target_path, content, mode="w"):
                raise AppException(
                    message=f"原子写摘要文件失败: {target_path}",
                    error_type=ErrorType.FILE_IO
                )
            logger.debug(f"已写入摘要: {target_path.name}")
            return target_path
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"写入摘要失败: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"写入摘要失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"写入摘要失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"写入摘要失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
    
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
            
            # 写入 JSON 文件（使用原子写）
            json_content = json.dumps(metadata, ensure_ascii=False, indent=2)
            if not _atomic_write(metadata_path, json_content, mode="w"):
                raise AppException(
                    message=f"原子写元数据文件失败: {metadata_path}",
                    error_type=ErrorType.FILE_IO
                )
            
            logger.debug(f"已写入元数据: {metadata_path.name}")
            return metadata_path
            
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"写入元数据失败: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"写入元数据失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"写入元数据失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"写入元数据失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
    
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
        
        # 写入双语字幕（如果启用）
        if language_config.bilingual_mode == "source+target":
            original_path = download_result.get("original")
            if original_path and original_path.exists():
                # 确定源语言
                source_lang = self._extract_language_from_filename(original_path.name)
                if not source_lang:
                    # 从 detection_result 获取
                    if detection_result.manual_languages:
                        source_lang = detection_result.manual_languages[0]
                    elif detection_result.auto_languages:
                        source_lang = detection_result.auto_languages[0]
                
                if source_lang:
                    # 为每个目标语言生成双语字幕
                    for target_lang in language_config.subtitle_target_languages:
                        # 如果源语言和目标语言相同，仍然生成双语字幕（原文+原文）
                        # 这样用户可以明确看到这是双语模式，即使语言相同
                        if source_lang == target_lang or source_lang.split('-')[0] == target_lang.split('-')[0]:
                            logger.info(
                                f"源语言 {source_lang} 和目标语言 {target_lang} 相同，将生成原文+原文的双语字幕",
                                video_id=video_info.video_id
                            )
                            # 继续处理，使用原始字幕作为目标字幕
                            if not translated_path or not translated_path.exists():
                                translated_path = original_path
                                logger.info(
                                    f"使用原始字幕作为目标字幕（源语言和目标语言相同）",
                                    video_id=video_info.video_id
                                )
                        
                        # 优先使用翻译后的字幕
                        translated_path = translation_result.get(target_lang)
                        
                        # 如果没有翻译字幕，尝试使用官方翻译字幕
                        if not translated_path or not translated_path.exists():
                            official_path = download_result.get("official_translations", {}).get(target_lang)
                            if official_path and official_path.exists():
                                translated_path = official_path
                                logger.info(
                                    f"使用官方翻译字幕生成双语字幕: {target_lang}",
                                    video_id=video_info.video_id
                                )
                        
                        # 如果仍然没有目标语言字幕，记录详细信息并跳过
                        if not translated_path or not translated_path.exists():
                            logger.warning(
                                f"目标语言 {target_lang} 无可用字幕，跳过双语字幕生成。"
                                f"translation_result[{target_lang}]={translation_result.get(target_lang)}, "
                                f"official_translations[{target_lang}]={download_result.get('official_translations', {}).get(target_lang)}",
                                video_id=video_info.video_id
                            )
                            continue
                        
                        # 生成双语字幕
                        try:
                            logger.info(
                                f"开始生成双语字幕: 源语言={source_lang} (文件: {original_path}), "
                                f"目标语言={target_lang} (文件: {translated_path})",
                                video_id=video_info.video_id
                            )
                            
                            # 验证文件确实存在且不同
                            if not original_path.exists():
                                raise AppException(
                                    message=f"源语言字幕文件不存在: {original_path}",
                                    error_type=ErrorType.FILE_IO
                                )
                            if not translated_path.exists():
                                raise AppException(
                                    message=f"目标语言字幕文件不存在: {translated_path}",
                                    error_type=ErrorType.FILE_IO
                                )
                            if original_path == translated_path:
                                logger.warning(
                                    f"源语言和目标语言字幕文件相同: {original_path}，将生成原文+原文的双语字幕",
                                    video_id=video_info.video_id
                                )
                            
                            bilingual_path = self.write_bilingual_subtitle(
                                video_dir,
                                original_path,
                                translated_path,
                                source_lang,
                                target_lang
                            )
                            logger.info(
                                f"已生成双语字幕: {bilingual_path.name} (路径: {bilingual_path})",
                                video_id=video_info.video_id
                            )
                        except Exception as e:
                            import traceback
                            logger.error(
                                f"生成双语字幕失败 ({source_lang}-{target_lang}): {e}\n{traceback.format_exc()}",
                                video_id=video_info.video_id
                            )
        
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
    
    def _parse_srt(self, srt_content: str) -> List[Dict]:
        """解析 SRT 字幕文件内容
        
        Args:
            srt_content: SRT 文件内容
        
        Returns:
            字幕条目列表，每个条目包含：
            {
                "index": int,  # 序号
                "start": str,  # 开始时间
                "end": str,    # 结束时间
                "text": str    # 字幕文本
            }
        """
        import re
        entries = []
        
        # SRT 格式：序号\n时间码\n文本\n\n
        pattern = r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\d+\s*\n|\Z)'
        matches = re.finditer(pattern, srt_content, re.DOTALL | re.MULTILINE)
        
        for match in matches:
            index = int(match.group(1))
            start = match.group(2)
            end = match.group(3)
            text = match.group(4).strip()
            
            entries.append({
                "index": index,
                "start": start,
                "end": end,
                "text": text
            })
        
        return entries
    
    def _merge_srt_entries(
        self,
        source_entries: List[Dict],
        target_entries: List[Dict]
    ) -> str:
        """合并源语言和目标语言字幕条目
        
        根据时间轴对齐，生成双语字幕（格式：源语言 / 目标语言）
        
        Args:
            source_entries: 源语言字幕条目列表
            target_entries: 目标语言字幕条目列表
        
        Returns:
            合并后的 SRT 格式字符串
        """
        # 简单的对齐策略：按序号对齐（假设两个字幕文件的序号和时间轴一致）
        # 如果序号不一致，则按时间轴对齐
        merged_lines = []
        
        # 创建目标字幕的时间索引（用于时间对齐）
        target_by_time = {}
        for entry in target_entries:
            key = (entry["start"], entry["end"])
            target_by_time[key] = entry
        
        # 遍历源字幕条目，尝试匹配目标字幕
        for source_entry in source_entries:
            source_text = source_entry["text"]
            time_key = (source_entry["start"], source_entry["end"])
            
            # 尝试按时间轴匹配
            target_entry = target_by_time.get(time_key)
            
            if target_entry:
                # 找到匹配的目标字幕，合并
                target_text = target_entry["text"]
                merged_text = f"{source_text} / {target_text}"
            else:
                # 未找到匹配，只使用源语言
                merged_text = source_text
            
            # 生成 SRT 条目
            merged_lines.append(f"{source_entry['index']}")
            merged_lines.append(f"{source_entry['start']} --> {source_entry['end']}")
            merged_lines.append(merged_text)
            merged_lines.append("")  # 空行分隔
        
        logger.debug(f"字幕合并完成: 匹配 {matched_count} 条，未匹配 {unmatched_count} 条")
        return "\n".join(merged_lines)
    
    def write_bilingual_subtitle(
        self,
        video_dir: Path,
        source_subtitle_path: Path,
        target_subtitle_path: Path,
        source_language: str,
        target_language: str
    ) -> Path:
        """写入双语字幕文件
        
        合并源语言和目标语言字幕，生成格式：bilingual.<source>-<target>.srt
        
        Args:
            video_dir: 视频输出目录
            source_subtitle_path: 源语言字幕文件路径
            target_subtitle_path: 目标语言字幕文件路径
            source_language: 源语言代码
            target_language: 目标语言代码
        
        Returns:
            写入的文件路径
        """
        video_dir.mkdir(parents=True, exist_ok=True)
        target_path = video_dir / f"bilingual.{source_language}-{target_language}.srt"
        
        try:
            # 验证文件存在
            if not source_subtitle_path.exists():
                raise AppException(
                    message=f"源语言字幕文件不存在: {source_subtitle_path}",
                    error_type=ErrorType.FILE_IO
                )
            if not target_subtitle_path.exists():
                raise AppException(
                    message=f"目标语言字幕文件不存在: {target_subtitle_path}",
                    error_type=ErrorType.FILE_IO
                )
            
            # 读取源语言字幕
            source_content = source_subtitle_path.read_text(encoding="utf-8")
            source_entries = self._parse_srt(source_content)
            logger.debug(f"解析源语言字幕: {len(source_entries)} 条条目，文件: {source_subtitle_path.name}")
            
            # 读取目标语言字幕
            target_content = target_subtitle_path.read_text(encoding="utf-8")
            target_entries = self._parse_srt(target_content)
            logger.debug(f"解析目标语言字幕: {len(target_entries)} 条条目，文件: {target_subtitle_path.name}")
            
            if len(source_entries) == 0:
                raise AppException(
                    message=f"源语言字幕文件为空: {source_subtitle_path}",
                    error_type=ErrorType.CONTENT
                )
            if len(target_entries) == 0:
                raise AppException(
                    message=f"目标语言字幕文件为空: {target_subtitle_path}",
                    error_type=ErrorType.CONTENT
                )
            
            # 合并字幕
            merged_content = self._merge_srt_entries(source_entries, target_entries)
            logger.debug(f"合并后字幕长度: {len(merged_content)} 字符，前100字符: {merged_content[:100]}")
            
            # 使用原子写机制
            if not _atomic_write(target_path, merged_content, mode="w"):
                raise AppException(
                    message=f"原子写双语字幕文件失败: {target_path}",
                    error_type=ErrorType.FILE_IO
                )
            
            logger.debug(f"已写入双语字幕: {target_path.name}")
            return target_path
            
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"写入双语字幕失败: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"写入双语字幕失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error
        except AppException:
            # 重新抛出 AppException
            raise
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"写入双语字幕失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"写入双语字幕失败: {app_error}",
                error_type=app_error.error_type.value
            )
            raise app_error

