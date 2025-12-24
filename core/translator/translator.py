"""
字幕翻译模块
根据翻译策略调用 AI 翻译或使用官方字幕
符合 error_handling.md 规范：将 LLMException 适配为 AppException
"""

import re
from pathlib import Path
from typing import Optional, Dict, List

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.prompts import get_translation_prompt
from core.logger import get_logger, translate_log
from core.llm_client import LLMClient, LLMException, LLMErrorType
from core.exceptions import (
    AppException,
    ErrorType,
    map_llm_error_to_app_error,
    TaskCancelledError,
)
from .source_selector import select_source_subtitle

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
        # 保存翻译错误信息（用于 pipeline 记录失败时获取 error_type）
        self._last_translation_errors: Dict[str, AppException] = {}

    def get_translation_errors(self) -> Dict[str, AppException]:
        """获取翻译错误信息

        Returns:
            字典，包含每个目标语言的错误信息：{target_lang: AppException}
        """
        return self._last_translation_errors.copy()

    def translate(
        self,
        video_info: VideoInfo,
        detection_result: DetectionResult,
        language_config: LanguageConfig,
        download_result: Dict[str, Optional[Path]],
        output_path: Path,
        force_retranslate: bool = False,
        target_languages: Optional[list[str]] = None,
        cancel_token=None,
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
            target_languages: 需要翻译的目标语言列表（如果为 None，则翻译所有目标语言）
                            注意：此参数用于优化，只翻译没有官方字幕的语言

        Returns:
            字典，包含翻译后的字幕文件路径（按目标语言）：
            {
                "zh-CN": Path,
                ...
            }
        """
        result = {}
        # 清空之前的错误信息
        self._last_translation_errors.clear()

        logger.info_i18n(
            "translator_translate_start",
            target_languages=target_languages
            if target_languages
            else language_config.subtitle_target_languages,
            output_dir=str(output_path),
            official_subtitles=list(
                download_result.get("official_translations", {}).keys()
            ),
            video_id=video_info.video_id,
        )

        if not detection_result.has_subtitles:
            logger.warning_i18n(
                "video_no_subtitle_skip_translation", video_id=video_info.video_id
            )
            return result

        # 确定需要翻译的语言列表（如果未指定，则翻译所有目标语言）
        languages_to_translate = (
            target_languages
            if target_languages is not None
            else language_config.subtitle_target_languages
        )

        logger.info_i18n(
            "translation_languages_needed",
            languages=languages_to_translate,
            video_id=video_info.video_id,
        )

        # 确保输出目录存在
        output_path.mkdir(parents=True, exist_ok=True)

        # 对需要翻译的语言进行翻译
        for target_lang in languages_to_translate:
            # 检查取消状态
            if cancel_token and cancel_token.is_cancelled():
                reason = cancel_token.get_reason() or translate_log("user_cancelled")
                logger.info_i18n(
                    "translation_cancelled", reason=reason, video_id=video_info.video_id
                )
                raise TaskCancelledError(reason)

            logger.info_i18n(
                "translation_target_start",
                target_lang=target_lang,
                video_id=video_info.video_id,
            )
            translated_path = output_path / f"translated.{target_lang}.srt"

            # 检查是否已存在翻译文件（避免重复调用 AI）
            if translated_path.exists() and not force_retranslate:
                logger.info_i18n(
                    "translation_file_exists_skip",
                    file_name=translated_path.name,
                    video_id=video_info.video_id,
                )
                result[target_lang] = translated_path
                continue

            # 注意：如果 target_languages 参数被传入，说明这些语言在 pipeline 层面已经确认没有官方字幕
            # 但为了代码健壮性，这里仍然检查一次（防止 pipeline 和 translator 逻辑不一致）
            # 如果 pipeline 优化正确，这里的检查应该总是 False
            official_path = download_result.get("official_translations", {}).get(
                target_lang
            )

            if official_path and official_path.exists():
                # 有官方翻译字幕，直接使用（不调用 AI）
                # 注意：如果 target_languages 被传入，这种情况理论上不应该发生
                logger.warning_i18n(
                    "log.copy_official_subtitle",
                    target_lang=target_lang,
                    file_name=official_path.name,
                    video_id=video_info.video_id,
                )
                # 复制到 translated.<lang>.srt（确保路径一致）
                if official_path != translated_path:
                    self._copy_to_translated(official_path, translated_path)
                result[target_lang] = translated_path
                continue

            # 根据翻译策略决定是否调用 AI
            if language_config.translation_strategy == "OFFICIAL_ONLY":
                # 只用官方字幕，不调用 AI
                logger.warning_i18n(
                    "log.no_official_subtitle_skip_ai",
                    target_lang=target_lang,
                    video_id=video_info.video_id,
                )
                result[target_lang] = None
                continue

            # 需要调用 AI 翻译
            # 选择源字幕（优先常见语言的官方字幕，其次原始字幕）
            logger.debug_i18n(
                "selecting_source_subtitle_for_translation",
                target_lang=target_lang,
                video_id=video_info.video_id,
            )
            source_subtitle_path = select_source_subtitle(
                download_result, detection_result, target_language=target_lang
            )

            if not source_subtitle_path or not source_subtitle_path.exists():
                logger.warning_i18n(
                    "log.no_source_subtitle_for_ai",
                    target_lang=target_lang,
                    original=str(download_result.get("original")),
                    official=list(
                        download_result.get("official_translations", {}).keys()
                    ),
                    video_id=video_info.video_id,
                )
                result[target_lang] = None
                continue

            logger.info_i18n(
                "source_subtitle_selected",
                path=str(source_subtitle_path),
                target_lang=target_lang,
                video_id=video_info.video_id,
            )

            # 调用 AI 翻译
            try:
                logger.info_i18n(
                    "calling_ai_translation",
                    source_file=source_subtitle_path.name,
                    target_lang=target_lang,
                    video_id=video_info.video_id,
                )
                translated_path = self._translate_with_ai(
                    source_subtitle_path,
                    target_lang,
                    translated_path,
                    detection_result,
                    video_info=video_info,
                    cancel_token=cancel_token,
                )
                if translated_path:
                    result[target_lang] = translated_path
                    logger.info_i18n(
                        "ai_translation_complete",
                        file_name=translated_path.name,
                        path=str(translated_path),
                        exists=translated_path.exists(),
                        video_id=video_info.video_id,
                    )
                else:
                    logger.warning_i18n(
                        "ai_translation_returned_none",
                        target_lang=target_lang,
                        video_id=video_info.video_id,
                    )
                    result[target_lang] = None
            except TaskCancelledError:
                # 取消操作，直接重新抛出（不要包装成 AppException）
                raise
            except LLMException as e:
                # 将 LLMException 适配为 AppException
                error_msg = translate_log(
                    "ai_translation_failed", target_lang=target_lang, error=str(e)
                )
                app_error = AppException(
                    message=error_msg,
                    error_type=map_llm_error_to_app_error(e.error_type.value),
                    cause=e,
                )
                logger.error_i18n(
                    "ai_translation_failed",
                    target_lang=target_lang,
                    error=str(app_error),
                    video_id=video_info.video_id,
                    error_type=app_error.error_type.value,
                )
                # 保存错误信息，供 pipeline 使用
                self._last_translation_errors[target_lang] = app_error
                result[target_lang] = None
                # 不抛出异常，继续处理其他语言
            except Exception as e:
                # 未映射的异常，转换为 AppException
                error_msg = translate_log(
                    "ai_translation_failed", target_lang=target_lang, error=str(e)
                )
                app_error = AppException(
                    message=error_msg, error_type=ErrorType.UNKNOWN, cause=e
                )
                logger.error_i18n(
                    "ai_translation_failed",
                    target_lang=target_lang,
                    error=str(app_error),
                    video_id=video_info.video_id,
                    error_type=app_error.error_type.value,
                )
                # 保存错误信息，供 pipeline 使用
                self._last_translation_errors[target_lang] = app_error
                result[target_lang] = None


        return result

    def _copy_to_translated(self, source_path: Path, target_path: Path) -> None:
        """将官方翻译字幕复制到 translated.<lang>.srt

        Args:
            source_path: 源文件路径
            target_path: 目标文件路径
        """
        try:
            import shutil

            # 增加安全检查，防止同一文件复制导致 SameFileError
            if source_path.resolve() == target_path.resolve():
                logger.debug_i18n(
                    "log.copy_file_skipped_same_path",
                    source_path=str(source_path),
                    target_path=str(target_path),
                )
                return

            shutil.copy2(source_path, target_path)
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            from core.logger import translate_exception

            app_error = AppException(
                message=translate_exception("exception.copy_file_failed", error=str(e)),
                error_type=ErrorType.FILE_IO,
                cause=e,
            )
            logger.error(
                translate_exception("exception.copy_file_failed", error=str(app_error)),
                extra={"error_type": app_error.error_type.value},
            )
            # 不抛出异常，由调用方决定如何处理
        except Exception as e:
            # 未映射的异常
            from core.logger import translate_exception

            app_error = AppException(
                message=translate_exception("exception.copy_file_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                translate_exception("exception.copy_file_failed", error=str(app_error)),
                extra={"error_type": app_error.error_type.value},
            )

    def _translate_with_ai(
        self,
        source_subtitle_path: Path,
        target_language: str,
        output_path: Path,
        detection_result: DetectionResult,
        video_info: Optional[VideoInfo] = None,
        cancel_token=None,
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
                logger.error_i18n(
                    "source_subtitle_read_failed", path=str(source_subtitle_path)
                )
                return None

            # 获取 video_id 用于日志
            video_id = (
                video_info.video_id
                if video_info
                else (
                    detection_result.video_id
                    if hasattr(detection_result, "video_id")
                    else None
                )
            )

            # 确定源语言（优先从文件名提取，更准确）
            source_language = self._extract_language_from_filename(
                source_subtitle_path.name
            )
            if not source_language:
                # 如果无法从文件名提取，使用检测结果
                source_language = self._determine_source_language(detection_result)
                logger.warning_i18n(
                    "source_language_extract_failed",
                    source_lang=source_language,
                    file_name=source_subtitle_path.name,
                    video_id=video_id,
                )

            if not source_language:
                logger.error_i18n(
                    "source_language_undetermined",
                    file_name=source_subtitle_path.name,
                    video_id=video_id,
                )
                return None

            logger.info_i18n(
                "source_language_determined",
                source_lang=source_language,
                file_name=source_subtitle_path.name,
                video_id=video_id,
            )

            # 生成翻译 Prompt
            prompt = get_translation_prompt(
                source_language, target_language, subtitle_text
            )

            # 检查取消状态（在调用 AI 前）
            if cancel_token and cancel_token.is_cancelled():
                reason = cancel_token.get_reason() or translate_log("log.user_cancelled")
                logger.info_i18n(
                    "log.translation_cancelled", reason=reason, video_id=video_id
                )
                raise TaskCancelledError(reason)

            # 判断是否需要分块翻译（长字幕使用 ChunkTracker）
            # 阈值：>100 条字幕或 >8000 字符
            use_chunks = len(subtitle_text) > 8000 or subtitle_text.count('\n\n') > 100

            if use_chunks and video_id:
                # 使用 ChunkTracker 分块翻译
                translated_text = self._translate_with_chunks(
                    subtitle_text=subtitle_text,
                    source_language=source_language,
                    target_language=target_language,
                    video_id=video_id,
                    work_dir=output_path.parent,
                    cancel_token=cancel_token,
                )
                # 如果分块翻译失败，回退到直接翻译
                if not translated_text:
                    logger.warning_i18n("log.chunk_fallback_direct", video_id=video_id)
                    translated_text = self._call_ai_api(prompt, cancel_token)
            else:
                # 短字幕直接翻译
                translated_text = self._call_ai_api(prompt, cancel_token)

            if not translated_text:
                logger.error_i18n("log.ai_api_call_failed")
                return None

            # 保存翻译后的字幕文件（使用原子写）
            from core.failure_logger import _atomic_write

            if not _atomic_write(output_path, translated_text, mode="w"):
                logger.error_i18n(
                    "log.translation_save_failed", error_type=ErrorType.FILE_IO.value
                )
                return None

            return output_path

        except TaskCancelledError:
            # 取消操作，直接重新抛出（不要包装成 AppException）
            raise
        except LLMException as e:
            # 将 LLMException 适配为 AppException
            error_msg = translate_log("ai_translation_error", error=str(e))
            app_error = AppException(
                message=error_msg,
                error_type=map_llm_error_to_app_error(e.error_type.value),
                cause=e,
            )
            logger.error_i18n(
                "ai_translation_error",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            return None
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            error_msg = translate_log("ai_translation_error", error=str(e))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.FILE_IO, cause=e
            )
            logger.error_i18n(
                "ai_translation_error",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            return None
        except Exception as e:
            # 未映射的异常，转换为 AppException
            error_msg = translate_log("ai_translation_error", error=str(e))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.UNKNOWN, cause=e
            )
            logger.error_i18n(
                "ai_translation_error",
                error=str(app_error),
                error_type=app_error.error_type.value,
            )
            return None

    def _extract_language_from_filename(self, filename: str) -> Optional[str]:
        """从文件名中提取语言代码

        例如：original.en.srt -> en
              translated.zh-CN.srt -> zh-CN

        Args:
            filename: 文件名

        Returns:
            语言代码，如果无法提取则返回 None
        """
        # 匹配 pattern.<lang>.srt 或 pattern.<lang>.md
        match = re.search(
            r"\.([a-z]{2}(?:-[A-Z]{2})?)\.(?:srt|md)$", filename, re.IGNORECASE
        )
        if match:
            return match.group(1)
        return None

    def _translate_with_chunks(
        self,
        subtitle_text: str,
        source_language: str,
        target_language: str,
        video_id: str,
        work_dir: Path,
        cancel_token=None,
    ) -> Optional[str]:
        """使用 ChunkTracker 分块翻译长字幕

        支持中断后恢复：如果之前翻译中途失败，会从上次中断的位置继续。

        Args:
            subtitle_text: SRT 格式的字幕内容
            source_language: 源语言代码
            target_language: 目标语言代码
            video_id: 视频 ID
            work_dir: 工作目录
            cancel_token: 取消令牌

        Returns:
            翻译后的 SRT 内容，失败返回 None
        """
        from core.state.chunk_tracker import ChunkTracker
        from core.prompts import get_translation_prompt

        try:
            # 初始化 ChunkTracker
            tracker = ChunkTracker(
                video_id=video_id,
                target_language=target_language,
                work_dir=work_dir,
            )

            # 拆分字幕为 chunks
            chunks = tracker.split_subtitle(subtitle_text)
            if not chunks:
                logger.warning_i18n("log.chunk_split_failed", video_id=video_id)
                return None

            total_chunks = len(chunks)
            status = tracker.get_status()
            completed = status.get("completed", 0)

            logger.info_i18n(
                "log.chunk_translation_start",
                video_id=video_id,
                total=total_chunks,
                completed=completed,
            )

            # 获取待翻译的 chunks
            pending_chunks = tracker.get_pending_chunks()
            
            # 确定并发数：取 AI 并发数和 3 的较小值
            ai_concurrency = getattr(self.llm, 'max_concurrency', 5)
            chunk_workers = min(3, ai_concurrency, len(pending_chunks))
            
            if chunk_workers > 1 and len(pending_chunks) > 1:
                # 多线程并发翻译
                logger.info_i18n(
                    "log.chunk_parallel_start",
                    video_id=video_id,
                    workers=chunk_workers,
                    pending=len(pending_chunks),
                )
                
                from concurrent.futures import ThreadPoolExecutor, as_completed
                import threading
                
                # 线程安全的进度计数器
                completed_count = [0]
                count_lock = threading.Lock()
                
                def translate_single_chunk(chunk):
                    """翻译单个 chunk 的工作函数"""
                    # 检查取消状态
                    if cancel_token and cancel_token.is_cancelled():
                        return (chunk.index, None, "cancelled")
                    
                    translated = self._translate_chunk_with_retry(
                        chunk_content=chunk.content,
                        source_language=source_language,
                        target_language=target_language,
                        video_id=video_id,
                        cancel_token=cancel_token,
                        max_chars=tracker.max_chars,
                        min_chars=500,
                    )
                    
                    return (chunk.index, translated, None)
                
                with ThreadPoolExecutor(max_workers=chunk_workers) as executor:
                    # 提交所有任务
                    futures = {
                        executor.submit(translate_single_chunk, chunk): chunk
                        for chunk in pending_chunks
                    }
                    
                    # 进度汇总变量
                    last_progress_milestone = 0
                    
                    # 处理完成的任务
                    for future in as_completed(futures):
                        chunk = futures[future]
                        
                        # 检查取消状态
                        if cancel_token and cancel_token.is_cancelled():
                            reason = cancel_token.get_reason() or translate_log("log.user_cancelled")
                            raise TaskCancelledError(reason)
                        
                        try:
                            chunk_index, translated, error = future.result()
                            
                            if error == "cancelled":
                                continue
                            
                            with count_lock:
                                completed_count[0] += 1
                                current = completed_count[0]
                            
                            # 汇总进度日志（每 25% 输出一次）
                            progress = (current * 100) // total_chunks
                            if progress >= last_progress_milestone + 25:
                                logger.info_i18n(
                                    "log.chunk_progress_summary",
                                    video_id=video_id,
                                    completed=current,
                                    total=total_chunks,
                                    percent=progress,
                                )
                                last_progress_milestone = (progress // 25) * 25
                            
                            if translated:
                                tracker.mark_chunk_completed(chunk_index, translated)
                            else:
                                tracker.mark_chunk_failed(chunk_index, "translation failed")
                                logger.warning_i18n(
                                    "log.chunk_translation_failed",
                                    video_id=video_id,
                                    chunk_index=chunk_index,
                                )
                        except Exception as e:
                            logger.error(f"Chunk {chunk.index} translation error: {e}")
                            tracker.mark_chunk_failed(chunk.index, str(e))
            else:
                # 单个 chunk 或串行模式
                for chunk in pending_chunks:
                    # 检查取消状态
                    if cancel_token and cancel_token.is_cancelled():
                        reason = cancel_token.get_reason() or translate_log("log.user_cancelled")
                        logger.info_i18n(
                            "log.translation_cancelled", reason=reason, video_id=video_id
                        )
                        raise TaskCancelledError(reason)

                    logger.info_i18n(
                        "log.chunk_processing",
                        video_id=video_id,
                        chunk_index=chunk.index + 1,
                        total_chunks=total_chunks,
                    )

                    # 使用递归式重试翻译
                    translated = self._translate_chunk_with_retry(
                        chunk_content=chunk.content,
                        source_language=source_language,
                        target_language=target_language,
                        video_id=video_id,
                        cancel_token=cancel_token,
                        max_chars=tracker.max_chars,
                        min_chars=500,
                    )

                    if translated:
                        tracker.mark_chunk_completed(chunk.index, translated)
                    else:
                        tracker.mark_chunk_failed(chunk.index, "recursive retry failed")
                        logger.warning_i18n(
                            "log.chunk_translation_failed",
                            video_id=video_id,
                            chunk_index=chunk.index,
                        )

            # 合并翻译结果
            merged = tracker.merge_translated_chunks()

            if merged:
                # 翻译完整性检查
                self._check_translation_completeness(subtitle_text, merged, video_id)
                
                logger.info_i18n(
                    "log.chunk_translation_complete",
                    video_id=video_id,
                    total=total_chunks,
                )
                # 清理临时文件
                tracker.cleanup()
                return merged
            else:
                # 有 chunk 未完成
                failed_status = tracker.get_status()
                logger.warning_i18n(
                    "log.chunk_translation_incomplete",
                    video_id=video_id,
                    completed=failed_status.get("completed", 0),
                    total=failed_status.get("total", total_chunks),
                )
                return None

        except TaskCancelledError:
            raise
        except Exception as e:
            logger.error_i18n(
                "log.chunk_translation_error",
                video_id=video_id,
                error=str(e),
            )
            return None

    def _translate_chunk_with_retry(
        self,
        chunk_content: str,
        source_language: str,
        target_language: str,
        video_id: str,
        cancel_token=None,
        max_chars: int = 8000,
        min_chars: int = 500,
        depth: int = 0,
    ) -> Optional[str]:
        """递归式翻译 chunk，失败时减小大小重试
        
        Args:
            chunk_content: chunk 内容（SRT 格式）
            source_language: 源语言
            target_language: 目标语言
            video_id: 视频 ID
            cancel_token: 取消令牌
            max_chars: 当前最大字符数
            min_chars: 最小字符数（不再拆分的阈值）
            depth: 递归深度（用于日志）
            
        Returns:
            翻译后的内容，失败返回 None
        """
        from core.prompts import get_translation_prompt
        
        # 检查取消状态
        if cancel_token and cancel_token.is_cancelled():
            return None
        
        # 生成翻译 prompt
        chunk_prompt = get_translation_prompt(
            source_language, target_language, chunk_content
        )
        
        # 尝试翻译
        translated = self._call_ai_api(chunk_prompt, cancel_token)
        
        if translated:
            return translated
        
        # 翻译失败，检查是否可以继续拆分
        content_len = len(chunk_content)
        if content_len <= min_chars:
            # 已经是最小大小，无法继续拆分
            logger.warning(
                f"Chunk 翻译失败且无法继续拆分 (size={content_len}, min={min_chars})",
                extra={"video_id": video_id},
            )
            return None
        
        # 拆分成两个子块
        logger.info_i18n(
            "log.chunk_retry_split",
            video_id=video_id,
            original_size=content_len,
            depth=depth + 1,
        )
        
        sub_chunks = self._split_chunk_in_half(chunk_content)
        
        if len(sub_chunks) < 2:
            # 无法拆分
            logger.warning(
                f"Chunk 无法拆分 (只有 {len(sub_chunks)} 个子块)",
                extra={"video_id": video_id},
            )
            return None
        
        # 递归翻译子块
        translated_parts = []
        new_max_chars = max_chars // 2
        
        for i, sub_chunk in enumerate(sub_chunks):
            logger.debug(
                f"翻译子块 {i + 1}/{len(sub_chunks)} (depth={depth + 1}, size={len(sub_chunk)})",
                extra={"video_id": video_id},
            )
            
            sub_translated = self._translate_chunk_with_retry(
                chunk_content=sub_chunk,
                source_language=source_language,
                target_language=target_language,
                video_id=video_id,
                cancel_token=cancel_token,
                max_chars=new_max_chars,
                min_chars=min_chars,
                depth=depth + 1,
            )
            
            if sub_translated:
                translated_parts.append(sub_translated)
            else:
                # 子块翻译失败，整个 chunk 失败
                logger.warning(
                    f"子块 {i + 1} 翻译失败",
                    extra={"video_id": video_id},
                )
                return None
        
        # 合并子块翻译结果
        return "\n".join(translated_parts)
    
    def _split_chunk_in_half(self, srt_content: str) -> List[str]:
        """将 SRT 内容在句子边界处拆分成两半
        
        优先在句子结束标点（句号、问号、感叹号）附近的字幕条目边界处拆分，
        其次在逗号、分号等次要标点处拆分，最后才在中点分割。
        
        Args:
            srt_content: SRT 格式内容
            
        Returns:
            两个子块的列表
        """
        import re
        
        # 按字幕条目拆分
        entries = re.split(r'\n\n+', srt_content.strip())
        entries = [e.strip() for e in entries if e.strip()]
        
        if len(entries) < 2:
            return [srt_content]
        
        # 计算中点范围（允许在中点 ±25% 范围内寻找最佳分割点）
        total = len(entries)
        mid = total // 2
        min_idx = max(1, int(total * 0.25))  # 至少保留 25% 在第一部分
        max_idx = min(total - 1, int(total * 0.75))  # 至少保留 25% 在第二部分
        
        # 句子结束标点（高优先级）
        sentence_end_pattern = re.compile(r'[.!?。！？][\s"\'）\]\}]*$')
        # 次要标点（低优先级）
        clause_end_pattern = re.compile(r'[,;:，；：、][\s"\'）\]\}]*$')
        
        # 在中点附近寻找最佳分割点
        best_idx = mid
        best_score = 0
        
        for i in range(min_idx, max_idx + 1):
            # 获取当前条目的文本内容（最后几行是字幕文本）
            entry = entries[i - 1]
            lines = entry.split('\n')
            text = lines[-1] if lines else ""
            
            # 计算分数：距离中点越近且有句子结束标点的得分越高
            distance_score = 1.0 - abs(i - mid) / (max_idx - min_idx + 1)
            
            if sentence_end_pattern.search(text):
                # 句子结束标点：高分
                punctuation_score = 2.0
            elif clause_end_pattern.search(text):
                # 次要标点：中分
                punctuation_score = 1.0
            else:
                # 无标点：低分
                punctuation_score = 0.0
            
            score = distance_score + punctuation_score
            
            if score > best_score:
                best_score = score
                best_idx = i
        
        first_half = "\n\n".join(entries[:best_idx])
        second_half = "\n\n".join(entries[best_idx:])
        
        return [first_half, second_half]


    def _determine_source_language(
        self, detection_result: DetectionResult
    ) -> Optional[str]:
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
            from core.logger import translate_exception

            app_error = AppException(
                message=translate_exception("exception.read_srt_failed", error=str(e)),
                error_type=ErrorType.FILE_IO,
                cause=e,
            )
            logger.error(
                translate_exception("exception.read_srt_failed", error=str(app_error)),
                extra={"error_type": app_error.error_type.value},
            )
            return None
        except Exception as e:
            # 未映射的异常
            from core.logger import translate_exception

            app_error = AppException(
                message=translate_exception("exception.read_srt_failed", error=str(e)),
                error_type=ErrorType.UNKNOWN,
                cause=e,
            )
            logger.error(
                translate_exception("exception.read_srt_failed", error=str(app_error)),
                extra={"error_type": app_error.error_type.value},
            )
            return None

    def _call_ai_api(self, prompt: str, cancel_token=None) -> Optional[str]:
        """调用 AI API 进行翻译

        Args:
            prompt: 翻译提示词
            cancel_token: 取消令牌（可选）

        Returns:
            翻译后的文本，如果失败则返回 None

        Raises:
            LLMException: 当 LLM 调用失败时抛出
            TaskCancelledError: 当取消令牌被触发时抛出
        """
        # 检查取消状态（在调用 AI 前）
        if cancel_token and cancel_token.is_cancelled():
            reason = cancel_token.get_reason() or translate_log("user_cancelled")
            raise TaskCancelledError(reason)

        try:
            # 如果是 GoogleTranslateClient，设置 cancel_token 以便在翻译过程中检查
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = cancel_token

            # 注意：generate 调用是同步的，在调用期间无法检查取消状态
            # 取消检查需要在字幕块级别的循环中进行（在 GoogleTranslateClient 内部）
            result = self.llm.generate(prompt)

            # 清除 cancel_token（避免影响后续调用）
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = None

            return result.text
        except TaskCancelledError:
            # 清除 cancel_token（如果已设置）
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = None
            # 取消操作，直接重新抛出
            raise
        except LLMException:
            # 清除 cancel_token（如果已设置）
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = None
            # 重新抛出 LLMException，由调用方处理
            raise
        except Exception as e:
            # 清除 cancel_token（如果已设置）
            if hasattr(self.llm, "_cancel_token"):
                self.llm._cancel_token = None
            # 未映射的异常，转换为 LLMException
            raise LLMException(
                translate_log("log.ai_api_call_failed_detail", error=str(e)),
                LLMErrorType.UNKNOWN,
            )

    def _check_translation_completeness(
        self, original: str, translated: str, video_id: str
    ) -> bool:
        """检查翻译前后条目数是否一致
        
        Args:
            original: 原始字幕内容
            translated: 翻译后字幕内容
            video_id: 视频 ID
            
        Returns:
            是否完整
        """
        original_count = original.count('-->')
        translated_count = translated.count('-->')
        
        if original_count != translated_count:
            logger.warning(
                f"Translation count mismatch for {video_id}: "
                f"{original_count} -> {translated_count} entries"
            )
            return False
        
        return True
