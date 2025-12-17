"""
元数据输出格式处理
支持 JSON 格式
"""
import json
from pathlib import Path
from typing import Optional, Dict
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


def write_metadata(
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
        
        from core.logger import translate_log
        logger.debug(translate_log("metadata_written", file_name=metadata_path.name))
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

