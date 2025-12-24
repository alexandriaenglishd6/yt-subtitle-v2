"""
AI 摘要模块
调用大模型对字幕文本生成单语言摘要
符合 error_handling.md 规范：将 LLMException 适配为 AppException
"""

from pathlib import Path
from typing import Optional, Dict, List

from core.models import VideoInfo
from core.language import LanguageConfig
from core.prompts import get_summary_prompt, get_chunk_summary_prompt, get_reduce_summary_prompt
from core.logger import get_logger
from core.llm_client import LLMClient, LLMException, LLMErrorType
from core.exceptions import AppException, ErrorType, map_llm_error_to_app_error

logger = get_logger()

# P1-1: 摘要文本最大字符数（约 10,000 tokens，足够大多数模型）
MAX_SUMMARY_TEXT_CHARS = 30000

# P1-2: Map-Reduce 分段摘要阈值和分块大小
MAP_REDUCE_THRESHOLD = 15000  # 超过此长度时使用分段摘要（约 5000 tokens）
CHUNK_SIZE_FOR_SUMMARY = 10000  # 每个分段的最大字符数（约 3300 tokens）

class Summarizer:
    """摘要生成器

    根据 LanguageConfig 生成单语言摘要
    """

    def __init__(self, llm: LLMClient, language_config: LanguageConfig):
        """初始化摘要生成器

        Args:
            llm: LLM 客户端实例（符合 ai_design.md 规范）
            language_config: 语言配置
        """
        self.llm = llm
        self.language_config = language_config
        # 保存摘要错误信息（用于 pipeline 记录失败时获取 error_type）
        self._last_summary_error: Optional[AppException] = None

    def get_summary_error(self) -> Optional[AppException]:
        """获取摘要错误信息

        Returns:
            摘要错误信息，如果没有错误则返回 None
        """
        return self._last_summary_error

    def summarize(
        self,
        video_info: VideoInfo,
        language_config: LanguageConfig,
        translation_result: Dict[str, Optional[Path]],
        download_result: Dict[str, Optional[Path]],
        output_path: Path,
        force_regenerate: bool = False,
    ) -> Optional[Path]:
        """生成视频摘要

        根据 LanguageConfig 生成单语言摘要

        Args:
            video_info: 视频信息
            language_config: 语言配置
            translation_result: 翻译结果（包含翻译后的字幕文件路径）
            download_result: 下载结果（包含原始字幕路径）
            output_path: 输出目录路径
            force_regenerate: 是否强制重新生成摘要（忽略已存在的摘要文件）

        Returns:
            摘要文件路径，如果失败则返回 None
        """
        # 清空之前的错误信息
        self._last_summary_error = None

        # 确保输出目录存在
        output_path.mkdir(parents=True, exist_ok=True)

        # 确定摘要文件路径
        summary_lang = language_config.summary_language
        summary_path = output_path / f"summary.{summary_lang}.md"

        # 检查是否已存在摘要文件（避免重复调用 AI）
        if summary_path.exists() and not force_regenerate:
            logger.info_i18n(
                "summary_file_exists_skip",
                file_name=summary_path.name,
                video_id=video_info.video_id,
            )
            return summary_path

        # 选择摘要源文本（优先使用翻译后的字幕，其次原始字幕）
        source_subtitle_path = self._select_summary_source(
            summary_lang, translation_result, download_result
        )

        if not source_subtitle_path or not source_subtitle_path.exists():
            logger.warning_i18n(
                "summary_source_not_found_skip", video_id=video_info.video_id
            )
            return None

        # 读取字幕文本
        subtitle_text = self._read_srt_file(source_subtitle_path)
        if not subtitle_text:
            logger.error_i18n(
                "summary_source_read_failed",
                path=str(source_subtitle_path),
                video_id=video_info.video_id,
            )
            return None

        # 提取纯文本（去除 SRT 格式的时间轴）
        plain_text = self._extract_text_from_srt(subtitle_text)
        if not plain_text:
            logger.warning_i18n(
                "summary_subtitle_empty_skip", video_id=video_info.video_id
            )
            return None

        # P1-2: 根据文本长度选择摘要策略
        original_length = len(plain_text)
        
        # 调用 AI API 生成摘要
        try:
            if original_length > MAP_REDUCE_THRESHOLD:
                # 使用 Map-Reduce 分段摘要
                logger.info_i18n(
                    "log.map_reduce_start",
                    text_length=original_length,
                    video_id=video_info.video_id,
                )
                duration_minutes = (video_info.duration // 60) if video_info.duration else 0
                summary_content = self._map_reduce_summarize(
                    plain_text=plain_text,
                    video_title=video_info.title,
                    summary_lang=summary_lang,
                    video_id=video_info.video_id,
                    duration_minutes=duration_minutes,
                    text_length=original_length,
                )
            else:
                # P1-1: 截断保护 - 超长时截断（作为后备）
                if original_length > MAX_SUMMARY_TEXT_CHARS:
                    plain_text = plain_text[:MAX_SUMMARY_TEXT_CHARS]
                    logger.warning_i18n(
                        "log.subtitle_truncated",
                        original_length=original_length,
                        truncated_length=MAX_SUMMARY_TEXT_CHARS,
                        video_id=video_info.video_id,
                    )
                
                # 生成摘要 Prompt（传入视频时长用于动态计算推荐字数）
                duration_minutes = (video_info.duration // 60) if video_info.duration else 0
                prompt = get_summary_prompt(
                    summary_language=summary_lang,
                    subtitle_text=plain_text,
                    video_title=video_info.title,
                    duration_minutes=duration_minutes,
                )
                summary_content = self._call_ai_api(prompt)
            
            if not summary_content:
                logger.error_i18n(
                    "summary_ai_generate_failed", video_id=video_info.video_id
                )
                return None

            # 保存摘要文件（使用原子写）
            from core.failure_logger import _atomic_write

            if not _atomic_write(summary_path, summary_content, mode="w"):
                logger.error_i18n(
                    "summary_save_failed",
                    video_id=video_info.video_id,
                    error_type=ErrorType.FILE_IO.value,
                )
                return None

            logger.info_i18n(
                "summary_generate_complete",
                file_name=summary_path.name,
                video_id=video_info.video_id,
            )
            return summary_path

        except LLMException as e:
            # 将 LLMException 适配为 AppException
            from core.logger import translate_exception

            error_msg = translate_exception("exception.summary_failed", reason=str(e))
            app_error = AppException(
                message=error_msg,
                error_type=map_llm_error_to_app_error(e.error_type.value),
                cause=e,
            )
            logger.error_i18n(
                "log.summary_generate_failed",
                error=str(app_error),
                video_id=video_info.video_id,
                error_type=app_error.error_type.value,
            )
            # 保存错误信息，供 pipeline 使用
            self._last_summary_error = app_error
            return None
        except (OSError, IOError, PermissionError) as e:
            # 文件IO错误
            from core.logger import translate_exception
            error_msg = translate_exception("exception.summary_generate_file_io_error", error=str(e))
            app_error = AppException(
                message=error_msg,
                error_type=ErrorType.FILE_IO,
                cause=e,
            )
            logger.error_i18n(
                "log.summary_generate_exception",
                error=str(app_error),
                video_id=video_info.video_id,
                error_type=app_error.error_type.value,
            )
            return None
        except Exception as e:
            # 未映射的异常，转换为 AppException
            from core.logger import translate_exception
            error_msg = translate_exception("exception.summary_generate_error", error=str(e))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.UNKNOWN, cause=e
            )
            logger.error_i18n(
                "log.summary_generate_exception",
                error=str(app_error),
                video_id=video_info.video_id,
                error_type=app_error.error_type.value,
            )
            # 保存错误信息，供 pipeline 使用
            self._last_summary_error = app_error
            return None

    def _select_summary_source(
        self,
        summary_language: str,
        translation_result: Dict[str, Optional[Path]],
        download_result: Dict[str, Optional[Path]],
    ) -> Optional[Path]:
        """选择摘要源文本

        优先使用 translated.<summary_language>.srt，否则使用原始字幕

        Args:
            summary_language: 摘要语言代码
            translation_result: 翻译结果
            download_result: 下载结果

        Returns:
            源字幕文件路径，如果不存在则返回 None
        """
        # 优先使用翻译后的字幕（如果存在）
        translated_path = translation_result.get(summary_language)
        if translated_path and translated_path.exists():
            logger.info_i18n(
                "summary_source_translated", file_name=translated_path.name
            )
            return translated_path

        # 否则使用原始字幕
        original_path = download_result.get("original")
        if original_path and original_path.exists():
            logger.info_i18n("summary_source_original", file_name=original_path.name)
            return original_path

        # 如果都没有，尝试使用任何可用的翻译字幕
        for lang, path in translation_result.items():
            if path and path.exists():
                logger.info_i18n(
                    "summary_source_translated_lang", file_name=path.name, lang=lang
                )
                return path

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
            error_msg = translate_exception("exception.summary_source_read_failed", path=str(srt_path))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.FILE_IO, cause=e
            )
            logger.error_i18n(
                "log.summary_source_read_failed", 
                path=str(srt_path),
                error_type=app_error.error_type.value
            )
            return None
        except Exception as e:
            # 未映射的异常
            from core.logger import translate_exception
            error_msg = translate_exception("exception.summary_source_read_failed", path=str(srt_path))
            app_error = AppException(
                message=error_msg, error_type=ErrorType.UNKNOWN, cause=e
            )
            logger.error_i18n(
                "log.summary_source_read_failed", 
                path=str(srt_path),
                error_type=app_error.error_type.value
            )
            return None

    def _extract_text_from_srt(self, srt_content: str) -> str:
        """从 SRT 格式中提取纯文本

        去除时间轴和序号，只保留字幕文本

        Args:
            srt_content: SRT 格式的字幕内容

        Returns:
            纯文本内容
        """

        # SRT 格式示例：
        # 1
        # 00:00:01,000 --> 00:00:03,000
        # Hello world
        #
        # 2
        # 00:00:04,000 --> 00:00:06,000
        # This is a test

        # 移除序号行（纯数字行）
        lines = srt_content.split("\n")
        text_lines = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 跳过空行
            if not line:
                i += 1
                continue

            # 跳过序号行（纯数字）
            if line.isdigit():
                i += 1
                # 跳过时间轴行（包含 -->）
                if i < len(lines) and "-->" in lines[i]:
                    i += 1
                continue

            # 跳过时间轴行（包含 -->）
            if "-->" in line:
                i += 1
                continue

            # 这是字幕文本行
            text_lines.append(line)
            i += 1

        # 合并文本行，用空格分隔
        return " ".join(text_lines)

    def _call_ai_api(self, prompt: str) -> Optional[str]:
        """调用 AI API 生成摘要

        Args:
            prompt: 摘要提示词

        Returns:
            摘要文本，如果失败则返回 None

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
            from core.logger import translate_exception

            error_msg = translate_exception("exception.ai_api_call_failed", error=str(e))
            raise LLMException(error_msg, LLMErrorType.UNKNOWN)

    def _map_reduce_summarize(
        self,
        plain_text: str,
        video_title: str,
        summary_lang: str,
        video_id: str,
        duration_minutes: int = 0,
        text_length: int = 0,
    ) -> Optional[str]:
        """Map-Reduce 分段摘要
        
        1. 分块
        2. Map: 每块生成子摘要
        3. Reduce: 合并子摘要生成最终摘要
        
        Args:
            plain_text: 完整的字幕纯文本
            video_title: 视频标题
            summary_lang: 摘要语言代码
            video_id: 视频 ID（用于日志）
            duration_minutes: 视频时长（分钟）
            text_length: 原始文本长度
            
        Returns:
            最终摘要文本，如果失败则返回 None
        """
        # 分块
        chunks = self._split_text_into_chunks(plain_text, CHUNK_SIZE_FOR_SUMMARY)
        total_chunks = len(chunks)
        
        logger.info_i18n(
            "log.map_reduce_chunked",
            total_chunks=total_chunks,
            video_id=video_id,
        )
        
        # 确定并发数：取 AI 并发数和 3 的较小值
        ai_concurrency = getattr(self.llm, 'max_concurrency', 5)
        map_workers = min(3, ai_concurrency, total_chunks)
        
        # Map: 并发生成子摘要
        sub_summaries = [None] * total_chunks  # 预分配保持顺序
        
        def summarize_chunk(chunk_index: int, chunk_text: str, max_retries: int = 2):
            """摘要单个 chunk 的工作函数（带重试）"""
            prompt = get_chunk_summary_prompt(
                summary_language=summary_lang,
                chunk_text=chunk_text,
                chunk_index=chunk_index + 1,
                total_chunks=total_chunks,
            )
            
            for attempt in range(max_retries + 1):
                result = self._call_ai_api(prompt)
                if result:
                    return chunk_index, result
                if attempt < max_retries:
                    logger.warning(f"Chunk {chunk_index + 1} summary failed, retrying ({attempt + 1}/{max_retries})")
            
            logger.warning(f"Chunk {chunk_index + 1} summary failed after {max_retries} retries")
            return chunk_index, None
        
        if map_workers > 1 and total_chunks > 1:
            # 多线程并发
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            logger.info_i18n(
                "log.map_parallel_start",
                video_id=video_id,
                workers=map_workers,
                chunks=total_chunks,
            )
            
            with ThreadPoolExecutor(max_workers=map_workers) as executor:
                futures = {
                    executor.submit(summarize_chunk, i, chunk): i
                    for i, chunk in enumerate(chunks)
                }
                
                for future in as_completed(futures):
                    try:
                        chunk_index, sub_summary = future.result()
                        if sub_summary:
                            sub_summaries[chunk_index] = sub_summary
                        logger.info_i18n(
                            "log.map_reduce_chunk_processing",
                            chunk_index=chunk_index + 1,
                            total_chunks=total_chunks,
                            video_id=video_id,
                        )
                    except Exception as e:
                        logger.error(f"Chunk summary error: {e}")
        else:
            # 串行模式（单个 chunk 或并发数为 1）
            for i, chunk in enumerate(chunks):
                logger.info_i18n(
                    "log.map_reduce_chunk_processing",
                    chunk_index=i + 1,
                    total_chunks=total_chunks,
                    video_id=video_id,
                )
                _, sub_summary = summarize_chunk(i, chunk)
                if sub_summary:
                    sub_summaries[i] = sub_summary
        
        # 过滤掉 None
        sub_summaries = [s for s in sub_summaries if s]
        
        if not sub_summaries:
            logger.warning_i18n(
                "log.map_reduce_no_sub_summaries",
                video_id=video_id,
            )
            return None
        
        # Reduce: 合并子摘要
        logger.info_i18n(
            "log.map_reduce_reducing",
            sub_summary_count=len(sub_summaries),
            video_id=video_id,
        )
        
        combined_text = "\n\n---\n\n".join(sub_summaries)
        reduce_prompt = get_reduce_summary_prompt(
            summary_language=summary_lang,
            sub_summaries=combined_text,
            video_title=video_title,
            total_chunks=total_chunks,
            duration_minutes=duration_minutes,  # 传入视频时长
            text_length=text_length,  # 传入原始文本长度
        )
        
        final_summary = self._call_ai_api(reduce_prompt)
        
        if final_summary:
            logger.info_i18n(
                "log.map_reduce_complete",
                total_chunks=total_chunks,
                video_id=video_id,
            )
        
        return final_summary

    def _split_text_into_chunks(self, text: str, chunk_size: int) -> List[str]:
        """将文本分割成多个块
        
        Args:
            text: 要分割的文本
            chunk_size: 每个块的最大字符数
            
        Returns:
            分割后的文本块列表
        """
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks

