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
from core import __version__ as TOOL_VERSION
from core.prompts import PROMPT_VERSION
from core.llm_client import LLMClient

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
        summary_path: Optional[Path],
        run_id: Optional[str] = None,
        translation_llm: Optional[LLMClient] = None,
        summary_llm: Optional[LLMClient] = None
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
            run_id: 批次ID（run_id），可选
            translation_llm: 翻译 LLM 客户端（可选），用于获取 provider 和 model 信息
            summary_llm: 摘要 LLM 客户端（可选），用于获取 provider 和 model 信息
        
        Returns:
            写入的文件路径
        """
        video_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = video_dir / "metadata.json"
        
        try:
            # 获取翻译 AI 信息
            translation_ai_info = None
            if translation_llm:
                # 从 LLMClient 实例获取 provider 和 model
                provider = getattr(translation_llm, 'provider_name', None)
                if not provider:
                    # 尝试从 ai_config 获取
                    ai_config = getattr(translation_llm, 'ai_config', None)
                    if ai_config:
                        provider = getattr(ai_config, 'provider', None)
                
                model = None
                ai_config = getattr(translation_llm, 'ai_config', None)
                if ai_config:
                    model = getattr(ai_config, 'model', None)
                
                if provider or model:
                    translation_ai_info = {
                        "provider": provider,
                        "model": model,
                        "prompt_version": PROMPT_VERSION
                    }
            
            # 获取摘要 AI 信息
            summary_ai_info = None
            if summary_llm:
                # 从 LLMClient 实例获取 provider 和 model
                provider = getattr(summary_llm, 'provider_name', None)
                if not provider:
                    # 尝试从 ai_config 获取
                    ai_config = getattr(summary_llm, 'ai_config', None)
                    if ai_config:
                        provider = getattr(ai_config, 'provider', None)
                
                model = None
                ai_config = getattr(summary_llm, 'ai_config', None)
                if ai_config:
                    model = getattr(ai_config, 'model', None)
                
                if provider or model:
                    summary_ai_info = {
                        "provider": provider,
                        "model": model,
                        "prompt_version": PROMPT_VERSION
                    }
            
            # 构建元数据
            metadata = {
                "tool_version": TOOL_VERSION,
                "run_id": run_id,
                "generated_at": datetime.now().isoformat(),
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
                    "source_language": language_config.source_language,
                    "subtitle_format": language_config.subtitle_format,
                },
                "translation_ai": translation_ai_info,
                "summary_ai": summary_ai_info,
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
        channel_id: Optional[str] = None,
        run_id: Optional[str] = None,
        translation_llm: Optional[LLMClient] = None,
        summary_llm: Optional[LLMClient] = None
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
            run_id: 批次ID（run_id），可选
            translation_llm: 翻译 LLM 客户端（可选），用于元数据记录
            summary_llm: 摘要 LLM 客户端（可选），用于元数据记录
        
        Returns:
            视频输出目录路径
        """
        # 获取视频输出目录
        video_dir = self.get_video_output_dir(video_info, channel_name, channel_id)
        
        # 确定源语言（用于后续处理）
        original_path = download_result.get("original")
        source_lang = None
        if original_path and original_path.exists():
            # 从文件名提取语言代码，如果失败则从 detection_result 获取
            source_lang = self._extract_language_from_filename(original_path.name)
            if not source_lang and detection_result.manual_languages:
                source_lang = detection_result.manual_languages[0]
            elif not source_lang and detection_result.auto_languages:
                source_lang = detection_result.auto_languages[0]
        
        # 保存原始 SRT 路径（用于双语字幕生成）
        original_srt_path = original_path  # 临时目录中的原始 SRT 文件
        
        # 根据字幕格式决定是否写入 SRT 文件
        output_original_path = None  # 保存输出目录中的原始字幕路径（可能是 SRT 或 TXT）
        if original_path and original_path.exists() and source_lang:
            if language_config.subtitle_format == "txt":
                # 只输出 TXT，直接写入 TXT
                txt_path = video_dir / f"original.{source_lang}.txt"
                self._write_txt_subtitle(original_path, txt_path)
                output_original_path = txt_path
            else:
                # 输出 SRT（srt 或 both）
                output_original_path = self.write_original_subtitle(video_dir, original_path, source_lang)
        
        # 写入翻译字幕
        output_translated_paths = {}  # 保存输出目录中的翻译字幕路径（可能是 SRT 或 TXT）
        translated_srt_paths = {}  # 保存临时目录中的原始 SRT 路径（用于双语字幕生成）
        logger.info(
            f"OutputWriter.write_all: 准备写入翻译字幕，translation_result 包含: {list(translation_result.keys())}, "
            f"文件路径: {[str(p) if p else None for p in translation_result.values()]}",
            video_id=video_info.video_id
        )
        for target_lang, translated_path in translation_result.items():
            if translated_path and translated_path.exists():
                logger.debug(
                    f"写入翻译字幕: {target_lang} <- {translated_path}",
                    video_id=video_info.video_id
                )
                # 保存原始 SRT 路径（用于双语字幕生成）
                translated_srt_paths[target_lang] = translated_path
                
                if language_config.subtitle_format == "txt":
                    # 只输出 TXT，直接写入 TXT
                    txt_path = video_dir / f"translated.{target_lang}.txt"
                    self._write_txt_subtitle(translated_path, txt_path)
                    output_translated_paths[target_lang] = txt_path
                else:
                    # 输出 SRT（srt 或 both）
                    output_translated_path = self.write_translated_subtitle(video_dir, translated_path, target_lang)
                    output_translated_paths[target_lang] = output_translated_path
                logger.info(
                    f"已写入翻译字幕: {target_lang} -> {output_translated_paths[target_lang]}",
                    video_id=video_info.video_id
                )
            else:
                logger.warning(
                    f"跳过写入翻译字幕 {target_lang}，原因: translated_path={translated_path}, exists={translated_path.exists() if translated_path else False}",
                    video_id=video_info.video_id
                )
        
        # 写入双语字幕（如果启用）
        if language_config.bilingual_mode == "source+target":
            # 使用输出目录中的原始字幕路径
            if output_original_path and output_original_path.exists():
                # 确定源语言（优先使用配置的源语言，否则从文件名或检测结果获取）
                source_lang = None
                
                # 优先使用配置的源语言
                if language_config.source_language:
                    source_lang = language_config.source_language
                    logger.debug(
                        f"使用配置的源语言: {source_lang}",
                        video_id=video_info.video_id
                    )
                
                # 如果配置的源语言不存在或未配置，从文件名提取
                if not source_lang:
                    source_lang = self._extract_language_from_filename(original_path.name)
                
                # 如果文件名提取失败，从检测结果获取
                if not source_lang:
                    if detection_result.manual_languages:
                        source_lang = detection_result.manual_languages[0]
                    elif detection_result.auto_languages:
                        source_lang = detection_result.auto_languages[0]
                
                if source_lang:
                    # 为每个目标语言生成双语字幕
                    for target_lang in language_config.subtitle_target_languages:
                        # 优先使用输出目录中的翻译字幕路径
                        output_translated_path = output_translated_paths.get(target_lang)
                        
                        # 如果没有输出目录中的翻译字幕，尝试使用临时目录中的翻译字幕
                        if not output_translated_path or not output_translated_path.exists():
                            temp_translated_path = translation_result.get(target_lang)
                            if temp_translated_path and temp_translated_path.exists():
                                # 写入输出目录
                                output_translated_path = self.write_translated_subtitle(video_dir, temp_translated_path, target_lang)
                                output_translated_paths[target_lang] = output_translated_path
                        
                        # 如果没有翻译字幕，尝试使用官方翻译字幕
                        if not output_translated_path or not output_translated_path.exists():
                            official_path = download_result.get("official_translations", {}).get(target_lang)
                            if official_path and official_path.exists():
                                # 写入输出目录
                                output_translated_path = self.write_translated_subtitle(video_dir, official_path, target_lang)
                                output_translated_paths[target_lang] = output_translated_path
                                logger.info(
                                    f"使用官方翻译字幕生成双语字幕: {target_lang}",
                                    video_id=video_info.video_id
                                )
                        
                        # 如果源语言和目标语言相同，使用原始字幕作为目标字幕
                        if source_lang == target_lang or source_lang.split('-')[0] == target_lang.split('-')[0]:
                            if not output_translated_path or not output_translated_path.exists():
                                output_translated_path = output_original_path
                                logger.info(
                                    f"源语言 {source_lang} 和目标语言 {target_lang} 相同，使用原始字幕作为目标字幕",
                                    video_id=video_info.video_id
                                )
                        
                        # 如果仍然没有目标语言字幕，记录详细信息并跳过
                        if not output_translated_path or not output_translated_path.exists():
                            logger.warning(
                                f"目标语言 {target_lang} 无可用字幕，跳过双语字幕生成。"
                                f"translation_result[{target_lang}]={translation_result.get(target_lang)}, "
                                f"official_translations[{target_lang}]={download_result.get('official_translations', {}).get(target_lang)}",
                                video_id=video_info.video_id
                            )
                            continue
                        
                        # 生成双语字幕
                        try:
                            # 使用原始 SRT 文件路径（而不是输出目录中的文件）来生成双语字幕
                            # 这样可以确保无论输出格式是什么，都能正确解析和合并
                            source_srt_for_bilingual = original_srt_path
                            target_srt_for_bilingual = translated_srt_paths.get(target_lang)
                            
                            # 如果没有临时目录中的翻译字幕，使用输出目录中的
                            if not target_srt_for_bilingual or not target_srt_for_bilingual.exists():
                                target_srt_for_bilingual = output_translated_path
                            
                            logger.info(
                                f"开始生成双语字幕: 源语言={source_lang} (文件: {source_srt_for_bilingual}), "
                                f"目标语言={target_lang} (文件: {target_srt_for_bilingual})",
                                video_id=video_info.video_id
                            )
                            
                            # 根据字幕格式决定输出类型
                            if language_config.subtitle_format == "txt":
                                # 直接生成 TXT 格式双语字幕
                                bilingual_path = self.write_bilingual_subtitle(
                                    video_dir,
                                    source_srt_for_bilingual,
                                    target_srt_for_bilingual,
                                    source_lang,
                                    target_lang,
                                    output_format="txt"
                                )
                            else:
                                # 生成 SRT 格式双语字幕
                                bilingual_path = self.write_bilingual_subtitle(
                                    video_dir,
                                    source_srt_for_bilingual,
                                    target_srt_for_bilingual,
                                    source_lang,
                                    target_lang,
                                    output_format="srt"
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
        
        # 生成 TXT 格式字幕（如果配置为 both，需要从 SRT 转换）
        if language_config.subtitle_format == "both":
            # 转换原始字幕（从 SRT 到 TXT）
            if output_original_path and output_original_path.exists() and output_original_path.suffix == ".srt":
                txt_path = output_original_path.with_suffix(".txt")
                self._write_txt_subtitle(output_original_path, txt_path)
            
            # 转换翻译字幕（从 SRT 到 TXT）
            for target_lang, translated_path in output_translated_paths.items():
                if translated_path and translated_path.exists() and translated_path.suffix == ".srt":
                    txt_path = translated_path.with_suffix(".txt")
                    self._write_txt_subtitle(translated_path, txt_path)
            
            # 转换双语字幕（如果存在）
            for srt_file in video_dir.glob("bilingual.*.srt"):
                txt_path = srt_file.with_suffix(".txt")
                self._write_txt_subtitle(srt_file, txt_path)
            
            logger.debug(f"已生成 TXT 格式字幕", video_id=video_info.video_id)
        # 如果选择 "both"，需要将双语 SRT 转换为 TXT
        if language_config.subtitle_format == "both":
            for srt_file in video_dir.glob("bilingual.*.srt"):
                txt_path = srt_file.with_suffix(".txt")
                self._write_txt_subtitle(srt_file, txt_path)
        
        # 写入元数据
        self.write_metadata(
            video_dir,
            video_info,
            detection_result,
            language_config,
            download_result,
            translation_result,
            summary_path,
            run_id=run_id,
            translation_llm=translation_llm,
            summary_llm=summary_llm
        )
        
        logger.info(f"所有输出文件已写入: {video_dir}", video_id=video_info.video_id)
        return video_dir
    
    def _srt_to_txt(self, srt_content: str) -> str:
        """将 SRT 字幕转换为纯文本（去掉时间轴）
        
        保持字幕条目的空行分隔，对于双语字幕保持上下放置格式
        
        Args:
            srt_content: SRT 文件内容
        
        Returns:
            纯文本内容（每个字幕条目之间有空行分隔）
        """
        entries = self._parse_srt(srt_content)
        lines = []
        for entry in entries:
            text = entry.get("text", "").strip()
            if text:
                # 保持文本中的换行（双语字幕的上下放置格式）
                lines.append(text)
                # 每个条目后添加空行分隔
                lines.append("")
        
        # 移除最后一个空行
        if lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def _write_txt_subtitle(self, srt_path: Path, txt_path: Path) -> Optional[Path]:
        """将 SRT 字幕文件转换并写入为 TXT 格式
        
        Args:
            srt_path: SRT 文件路径
            txt_path: 输出 TXT 文件路径
        
        Returns:
            写入的文件路径，失败返回 None
        """
        try:
            srt_content = srt_path.read_text(encoding="utf-8")
            txt_content = self._srt_to_txt(srt_content)
            if not _atomic_write(txt_path, txt_content, mode="w"):
                logger.warning(f"写入 TXT 字幕失败: {txt_path}")
                return None
            logger.debug(f"已写入 TXT 字幕: {txt_path.name}")
            return txt_path
        except Exception as e:
            logger.warning(f"转换 SRT 到 TXT 失败: {e}")
            return None
    
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
        """解析 SRT 或 VTT 字幕文件内容
        
        Args:
            srt_content: SRT 或 VTT 文件内容
        
        Returns:
            字幕条目列表，每个条目包含：
            {
                "index": int,  # 序号
                "start": str,  # 开始时间（SRT 格式：逗号分隔）
                "end": str,    # 结束时间（SRT 格式：逗号分隔）
                "text": str    # 字幕文本
            }
        """
        import re
        entries = []
        
        # 检查是否是 VTT 格式
        is_vtt = srt_content.strip().startswith("WEBVTT") or "WEBVTT" in srt_content[:100]
        
        if is_vtt:
            # 处理 VTT 格式
            lines = srt_content.split("\n")
            current_block = []
            subtitle_index = 1
            skip_header = True
            
            for line in lines:
                line_stripped = line.strip()
                
                # 跳过 VTT 头部
                if skip_header:
                    if line_stripped.upper().startswith("WEBVTT"):
                        continue
                    if line_stripped.startswith("Kind:") or line_stripped.startswith("Language:"):
                        continue
                    if line_stripped.startswith("Translator:") or line_stripped.startswith("Reviewer:") or line_stripped.startswith("المترجم:") or line_stripped.startswith("المدقّق:"):
                        continue
                    if not line_stripped and not current_block:
                        continue
                    if "-->" in line:
                        skip_header = False
                    elif line_stripped and not line_stripped.startswith("WEBVTT") and "-->" not in line:
                        continue
                
                # 空行：结束当前字幕块
                if not line_stripped:
                    if current_block:
                        # 解析当前块
                        time_line = None
                        text_lines = []
                        for block_line in current_block:
                            if "-->" in block_line:
                                time_line = block_line
                            else:
                                text_lines.append(block_line)
                        
                        if time_line:
                            # 解析时间轴：00:00:00.000 --> 00:00:02.000
                            time_match = re.match(r'(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3})', time_line)
                            if time_match:
                                start = f"{time_match.group(1)},{time_match.group(2)}"
                                end = f"{time_match.group(3)},{time_match.group(4)}"
                                text = "\n".join(text_lines).strip()
                                
                                if text:  # 只添加有文本的条目
                                    entries.append({
                                        "index": subtitle_index,
                                        "start": start,
                                        "end": end,
                                        "text": text
                                    })
                                    subtitle_index += 1
                        current_block = []
                    continue
                
                # 判断是否是时间轴
                if "-->" in line:
                    if current_block:
                        # 处理之前的块
                        time_line = None
                        text_lines = []
                        for block_line in current_block:
                            if "-->" in block_line:
                                time_line = block_line
                            else:
                                text_lines.append(block_line)
                        
                        if time_line:
                            time_match = re.match(r'(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3})', time_line)
                            if time_match:
                                start = f"{time_match.group(1)},{time_match.group(2)}"
                                end = f"{time_match.group(3)},{time_match.group(4)}"
                                text = "\n".join(text_lines).strip()
                                
                                if text:
                                    entries.append({
                                        "index": subtitle_index,
                                        "start": start,
                                        "end": end,
                                        "text": text
                                    })
                                    subtitle_index += 1
                        current_block = []
                    current_block = [line]
                    continue
                
                # 其他行：字幕文本
                if current_block:
                    current_block.append(line)
            
            # 处理最后一个块
            if current_block:
                time_line = None
                text_lines = []
                for block_line in current_block:
                    if "-->" in block_line:
                        time_line = block_line
                    else:
                        text_lines.append(block_line)
                
                if time_line:
                    time_match = re.match(r'(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3})', time_line)
                    if time_match:
                        start = f"{time_match.group(1)},{time_match.group(2)}"
                        end = f"{time_match.group(3)},{time_match.group(4)}"
                        text = "\n".join(text_lines).strip()
                        
                        if text:
                            entries.append({
                                "index": subtitle_index,
                                "start": start,
                                "end": end,
                                "text": text
                            })
        else:
            # 处理 SRT 格式：序号\n时间码\n文本\n\n
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
        matched_count = 0
        unmatched_count = 0
        
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
                # 找到匹配的目标字幕，合并（上下放置）
                target_text = target_entry["text"]
                merged_text = f"{source_text}\n{target_text}"
                matched_count += 1
            else:
                # 未找到匹配，只使用源语言
                merged_text = source_text
                unmatched_count += 1
            
            # 生成 SRT 条目
            merged_lines.append(f"{source_entry['index']}")
            merged_lines.append(f"{source_entry['start']} --> {source_entry['end']}")
            merged_lines.append(merged_text)
            merged_lines.append("")  # 空行分隔
        
        logger.debug(f"字幕合并完成: 匹配 {matched_count} 条，未匹配 {unmatched_count} 条")
        return "\n".join(merged_lines)
    
    def _merge_entries_to_txt(
        self,
        source_entries: List[Dict],
        target_entries: List[Dict]
    ) -> str:
        """合并源语言和目标语言字幕条目为 TXT 格式（去掉时间轴）
        
        保持字幕条目的空行分隔，双语字幕保持上下放置格式
        
        Args:
            source_entries: 源语言字幕条目列表
            target_entries: 目标语言字幕条目列表
        
        Returns:
            合并后的 TXT 格式字符串（每个条目之间有空行分隔）
        """
        # 创建目标字幕的时间索引（用于时间对齐）
        target_by_time = {}
        for entry in target_entries:
            key = (entry["start"], entry["end"])
            target_by_time[key] = entry
        
        lines = []
        matched_count = 0
        unmatched_count = 0
        
        # 遍历源字幕条目，尝试匹配目标字幕
        for source_entry in source_entries:
            source_text = source_entry["text"].strip()
            time_key = (source_entry["start"], source_entry["end"])
            
            # 尝试按时间轴匹配
            target_entry = target_by_time.get(time_key)
            
            if target_entry:
                # 找到匹配的目标字幕，合并（上下放置）
                target_text = target_entry["text"].strip()
                merged_text = f"{source_text}\n{target_text}"
                matched_count += 1
            else:
                # 未找到匹配，只使用源语言
                merged_text = source_text
                unmatched_count += 1
            
            # 添加到输出列表
            if merged_text:
                lines.append(merged_text)
                # 每个条目后添加空行分隔
                lines.append("")
        
        # 移除最后一个空行
        if lines and lines[-1] == "":
            lines.pop()
        
        logger.debug(f"TXT 字幕合并完成: 匹配 {matched_count} 条，未匹配 {unmatched_count} 条")
        return "\n".join(lines)
    
    def write_bilingual_subtitle(
        self,
        video_dir: Path,
        source_subtitle_path: Path,
        target_subtitle_path: Path,
        source_language: str,
        target_language: str,
        output_format: str = "srt"
    ) -> Path:
        """写入双语字幕文件
        
        合并源语言和目标语言字幕，生成格式：bilingual.<source>-<target>.srt 或 .txt
        
        Args:
            video_dir: 视频输出目录
            source_subtitle_path: 源语言字幕文件路径
            target_subtitle_path: 目标语言字幕文件路径
            source_language: 源语言代码
            target_language: 目标语言代码
            output_format: 输出格式，"srt" 或 "txt"
        
        Returns:
            写入的文件路径
        """
        video_dir.mkdir(parents=True, exist_ok=True)
        extension = ".txt" if output_format == "txt" else ".srt"
        target_path = video_dir / f"bilingual.{source_language}-{target_language}{extension}"
        
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
            if not source_content or not source_content.strip():
                raise AppException(
                    message=f"源语言字幕文件内容为空: {source_subtitle_path}",
                    error_type=ErrorType.CONTENT
                )
            source_entries = self._parse_srt(source_content)
            logger.debug(f"解析源语言字幕: {len(source_entries)} 条条目，文件: {source_subtitle_path.name}，文件大小: {len(source_content)} 字符")
            
            # 读取目标语言字幕
            target_content = target_subtitle_path.read_text(encoding="utf-8")
            if not target_content or not target_content.strip():
                raise AppException(
                    message=f"目标语言字幕文件内容为空: {target_subtitle_path}",
                    error_type=ErrorType.CONTENT
                )
            target_entries = self._parse_srt(target_content)
            logger.debug(f"解析目标语言字幕: {len(target_entries)} 条条目，文件: {target_subtitle_path.name}，文件大小: {len(target_content)} 字符")
            
            if len(source_entries) == 0:
                # 记录文件内容的前200字符，方便调试
                content_preview = source_content[:200] if len(source_content) > 200 else source_content
                raise AppException(
                    message=f"源语言字幕文件解析后为空（无法解析为有效字幕条目）: {source_subtitle_path}。文件内容预览: {repr(content_preview)}",
                    error_type=ErrorType.CONTENT
                )
            if len(target_entries) == 0:
                # 记录文件内容的前200字符，方便调试
                content_preview = target_content[:200] if len(target_content) > 200 else target_content
                raise AppException(
                    message=f"目标语言字幕文件解析后为空（无法解析为有效字幕条目）: {target_subtitle_path}。文件内容预览: {repr(content_preview)}",
                    error_type=ErrorType.CONTENT
                )
            
            # 合并字幕
            if output_format == "txt":
                # 直接生成 TXT 格式（去掉时间轴，保持空行分隔和上下放置格式）
                merged_content = self._merge_entries_to_txt(source_entries, target_entries)
            else:
                # 生成 SRT 格式
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

