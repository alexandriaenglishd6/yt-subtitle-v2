"""
字幕翻译模块
根据翻译策略调用 AI 翻译或使用官方字幕
符合 error_handling.md 规范：将 LLMException 适配为 AppException
"""
import os
import re
from pathlib import Path
from typing import Optional, Dict, List

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.prompts import get_translation_prompt
from core.logger import get_logger
from core.llm_client import LLMClient, LLMException, LLMErrorType
from core.exceptions import AppException, ErrorType, map_llm_error_to_app_error
from config.manager import AIConfig

logger = get_logger()


class SubtitleTranslator:
    """字幕翻译器
    
    根据翻译策略决定是否调用 AI 翻译，或使用官方字幕
    """
    
    def __init__(self, llm: LLMClient, language_config: LanguageConfig):
        """初始化字幕翻译器
        
        Args:
            llm: LLM 客户端实例（符合 ai_design.md 规范）
            language_config: 语言配置
        """
        self.llm = llm
        self.language_config = language_config
    
    def translate(
        self,
        video_info: VideoInfo,
        detection_result: DetectionResult,
        language_config: LanguageConfig,
        download_result: Dict[str, Optional[Path]],
        output_path: Path,
        force_retranslate: bool = False
    ) -> Dict[str, Optional[Path]]:
        """翻译字幕
        
        根据翻译策略和检测结果，决定是否调用 AI 翻译
        
        Args:
            video_info: 视频信息
            detection_result: 字幕检测结果
            language_config: 语言配置
            download_result: 下载结果（包含原始字幕和官方翻译字幕路径）
            output_path: 输出目录路径
            force_retranslate: 是否强制重译（忽略已存在的翻译文件）
        
        Returns:
            字典，包含翻译后的字幕文件路径（按目标语言）：
            {
                "zh-CN": Path,
                ...
            }
        """
        result = {}
        
        if not detection_result.has_subtitles:
            logger.warning(f"视频无可用字幕，跳过翻译: {video_info.video_id}")
            return result
        
        # 确保输出目录存在
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 对每个目标语言进行翻译
        for target_lang in language_config.subtitle_target_languages:
            translated_path = output_path / f"translated.{target_lang}.srt"
            
            # 检查是否已存在翻译文件（避免重复调用 AI）
            if translated_path.exists() and not force_retranslate:
                logger.info(
                    f"翻译文件已存在，跳过翻译: {translated_path.name}",
                    video_id=video_info.video_id
                )
                result[target_lang] = translated_path
                continue
            
            # 检查是否有官方翻译字幕
            official_path = download_result.get("official_translations", {}).get(target_lang)
            
            if official_path and official_path.exists():
                # 有官方翻译字幕，直接使用（不调用 AI）
                logger.info(
                    f"使用官方翻译字幕: {official_path.name}",
                    video_id=video_info.video_id
                )
                # 复制或链接到 translated.<lang>.srt
                self._copy_to_translated(official_path, translated_path)
                result[target_lang] = translated_path
                continue
            
            # 根据翻译策略决定是否调用 AI
            if language_config.translation_strategy == "OFFICIAL_ONLY":
                # 只用官方字幕，不调用 AI
                logger.warning(
                    f"目标语言 {target_lang} 无可用官方字幕，且策略为 OFFICIAL_ONLY，跳过翻译",
                    video_id=video_info.video_id
                )
                result[target_lang] = None
                continue
            
            # 需要调用 AI 翻译
            # 选择源字幕（优先人工字幕，其次自动字幕）
            source_subtitle_path = self._select_source_subtitle(
                download_result,
                detection_result
            )
            
            if not source_subtitle_path or not source_subtitle_path.exists():
                logger.warning(
                    f"无法找到源字幕文件，跳过 AI 翻译",
                    video_id=video_info.video_id
                )
                result[target_lang] = None
                continue
            
            # 调用 AI 翻译
            try:
                translated_path = self._translate_with_ai(
                    source_subtitle_path,
                    target_lang,
                    translated_path,
                    detection_result
                )
                if translated_path:
                    result[target_lang] = translated_path
                    logger.info(
                        f"AI 翻译完成: {translated_path.name}",
                        video_id=video_info.video_id
                    )
                else:
                    result[target_lang] = None
            except LLMException as e:
                # 将 LLMException 适配为 AppException
                app_error = AppException(
                    message=f"AI 翻译失败: {e}",
                    error_type=map_llm_error_to_app_error(e.error_type.value),
                    cause=e
                )
                logger.error(
                    f"AI 翻译失败: {app_error}",
                    video_id=video_info.video_id,
                    error_type=app_error.error_type.value
                )
                result[target_lang] = None
                # 不抛出异常，继续处理其他语言
            except Exception as e:
                # 未映射的异常，转换为 AppException
                app_error = AppException(
                    message=f"AI 翻译失败: {e}",
                    error_type=ErrorType.UNKNOWN,
                    cause=e
                )
                logger.error(
                    f"AI 翻译失败: {app_error}",
                    video_id=video_info.video_id,
                    error_type=app_error.error_type.value
                )
                result[target_lang] = None
        
        return result
    
    def _select_source_subtitle(
        self,
        download_result: Dict[str, Optional[Path]],
        detection_result: DetectionResult
    ) -> Optional[Path]:
        """选择源字幕文件（用于 AI 翻译）
        
        优先使用人工字幕，其次自动字幕
        
        Args:
            download_result: 下载结果
            detection_result: 检测结果
        
        Returns:
            源字幕文件路径，如果不存在则返回 None
        """
        # 优先使用原始字幕（人工字幕）
        original_path = download_result.get("original")
        if original_path and original_path.exists():
            return original_path
        
        # 如果没有原始字幕，尝试使用第一个可用的人工字幕
        if detection_result.manual_languages:
            for lang in detection_result.manual_languages:
                official_path = download_result.get("official_translations", {}).get(lang)
                if official_path and official_path.exists():
                    return official_path
        
        # 最后尝试使用自动字幕
        if detection_result.auto_languages:
            for lang in detection_result.auto_languages:
                official_path = download_result.get("official_translations", {}).get(lang)
                if official_path and official_path.exists():
                    return official_path
        
        return None
    
    def _copy_to_translated(self, source_path: Path, target_path: Path) -> None:
        """将官方翻译字幕复制到 translated.<lang>.srt
        
        Args:
            source_path: 源文件路径
            target_path: 目标文件路径
        """
        try:
            import shutil
            shutil.copy2(source_path, target_path)
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"复制文件失败: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"复制文件失败: {app_error}",
                error_type=app_error.error_type.value
            )
            # 不抛出异常，由调用方决定如何处理
        except Exception as e:
            # 未映射的异常
            app_error = AppException(
                message=f"复制文件失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"复制文件失败: {app_error}",
                error_type=app_error.error_type.value
            )
    
    def _translate_with_ai(
        self,
        source_subtitle_path: Path,
        target_language: str,
        output_path: Path,
        detection_result: DetectionResult
    ) -> Optional[Path]:
        """使用 AI 翻译字幕文件
        
        Args:
            source_subtitle_path: 源字幕文件路径
            target_language: 目标语言代码
            output_path: 输出文件路径
            detection_result: 检测结果（用于确定源语言）
        
        Returns:
            翻译后的字幕文件路径，如果失败则返回 None
        """
        try:
            # 读取源字幕文件
            subtitle_text = self._read_srt_file(source_subtitle_path)
            if not subtitle_text:
                logger.error(f"无法读取源字幕文件: {source_subtitle_path}")
                return None
            
            # 确定源语言
            source_language = self._determine_source_language(detection_result)
            if not source_language:
                logger.error("无法确定源语言")
                return None
            
            # 生成翻译 Prompt
            prompt = get_translation_prompt(
                source_language,
                target_language,
                subtitle_text
            )
            
            # 调用 AI API
            translated_text = self._call_ai_api(prompt)
            if not translated_text:
                logger.error("AI API 调用失败")
                return None
            
            # 保存翻译后的字幕文件（使用原子写）
            from core.failure_logger import _atomic_write
            if not _atomic_write(output_path, translated_text, mode="w"):
                logger.error(
                    "保存翻译文件失败",
                    error_type=ErrorType.FILE_IO.value
                )
                return None
            
            return output_path
            
        except LLMException as e:
            # 将 LLMException 适配为 AppException
            app_error = AppException(
                message=f"AI 翻译过程出错: {e}",
                error_type=map_llm_error_to_app_error(e.error_type.value),
                cause=e
            )
            logger.error(
                f"AI 翻译过程出错: {app_error}",
                error_type=app_error.error_type.value
            )
            return None
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"AI 翻译过程文件IO错误: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"AI 翻译过程文件IO错误: {app_error}",
                error_type=app_error.error_type.value
            )
            return None
        except Exception as e:
            # 未映射的异常，转换为 AppException
            app_error = AppException(
                message=f"AI 翻译过程出错: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"AI 翻译过程出错: {app_error}",
                error_type=app_error.error_type.value
            )
            return None
    
    def _determine_source_language(self, detection_result: DetectionResult) -> Optional[str]:
        """确定源语言代码
        
        Args:
            detection_result: 检测结果
        
        Returns:
            源语言代码，如果无法确定则返回 None
        """
        if detection_result.manual_languages:
            return detection_result.manual_languages[0]
        elif detection_result.auto_languages:
            return detection_result.auto_languages[0]
        else:
            return None
    
    def _read_srt_file(self, srt_path: Path) -> Optional[str]:
        """读取 SRT 字幕文件
        
        Args:
            srt_path: SRT 文件路径
        
        Returns:
            字幕文本内容，如果失败则返回 None
        """
        try:
            return srt_path.read_text(encoding="utf-8")
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            app_error = AppException(
                message=f"读取 SRT 文件失败: {e}",
                error_type=ErrorType.FILE_IO,
                cause=e
            )
            logger.error(
                f"读取 SRT 文件失败: {app_error}",
                error_type=app_error.error_type.value
            )
            return None
        except Exception as e:
            # 未映射的异常
            app_error = AppException(
                message=f"读取 SRT 文件失败: {e}",
                error_type=ErrorType.UNKNOWN,
                cause=e
            )
            logger.error(
                f"读取 SRT 文件失败: {app_error}",
                error_type=app_error.error_type.value
            )
            return None
    
    def _call_ai_api(self, prompt: str) -> Optional[str]:
        """调用 AI API 进行翻译
        
        Args:
            prompt: 翻译提示词
        
        Returns:
            翻译后的文本，如果失败则返回 None
        
        Raises:
            LLMException: 当 LLM 调用失败时抛出
        """
        try:
            result = self.llm.generate(prompt)
            return result.text
        except LLMException:
            # 重新抛出 LLMException，由调用方处理
            raise
        except Exception as e:
            # 未映射的异常，转换为 LLMException
            raise LLMException(
                f"AI API 调用失败: {e}",
                LLMErrorType.UNKNOWN
            )
