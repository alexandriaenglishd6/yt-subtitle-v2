"""
AI 摘要模块
调用大模型对字幕文本生成单语言摘要
"""
import os
from pathlib import Path
from typing import Optional, Dict

from core.models import VideoInfo
from core.language import LanguageConfig
from core.prompts import get_summary_prompt
from core.logger import get_logger
from core.llm_client import LLMClient, LLMException, LLMErrorType

logger = get_logger()


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
    
    def summarize(
        self,
        video_info: VideoInfo,
        language_config: LanguageConfig,
        translation_result: Dict[str, Optional[Path]],
        download_result: Dict[str, Optional[Path]],
        output_path: Path,
        force_regenerate: bool = False
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
        # 确保输出目录存在
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 确定摘要文件路径
        summary_lang = language_config.summary_language
        summary_path = output_path / f"summary.{summary_lang}.md"
        
        # 检查是否已存在摘要文件（避免重复调用 AI）
        if summary_path.exists() and not force_regenerate:
            logger.info(
                f"摘要文件已存在，跳过生成: {summary_path.name}",
                video_id=video_info.video_id
            )
            return summary_path
        
        # 选择摘要源文本（优先使用翻译后的字幕，其次原始字幕）
        source_subtitle_path = self._select_summary_source(
            summary_lang,
            translation_result,
            download_result
        )
        
        if not source_subtitle_path or not source_subtitle_path.exists():
            logger.warning(
                f"无法找到摘要源字幕文件，跳过摘要生成",
                video_id=video_info.video_id
            )
            return None
        
        # 读取字幕文本
        subtitle_text = self._read_srt_file(source_subtitle_path)
        if not subtitle_text:
            logger.error(
                f"无法读取源字幕文件: {source_subtitle_path}",
                video_id=video_info.video_id
            )
            return None
        
        # 提取纯文本（去除 SRT 格式的时间轴）
        plain_text = self._extract_text_from_srt(subtitle_text)
        if not plain_text:
            logger.warning(
                f"字幕文件为空，跳过摘要生成",
                video_id=video_info.video_id
            )
            return None
        
        # 生成摘要 Prompt
        prompt = get_summary_prompt(
            summary_language=summary_lang,
            subtitle_text=plain_text,
            video_title=video_info.title
        )
        
        # 调用 AI API 生成摘要
        try:
            summary_content = self._call_ai_api(prompt)
            if not summary_content:
                logger.error(
                    f"AI 摘要生成失败",
                    video_id=video_info.video_id
                )
                return None
            
            # 保存摘要文件
            summary_path.write_text(summary_content, encoding="utf-8")
            logger.info(
                f"摘要生成完成: {summary_path.name}",
                video_id=video_info.video_id
            )
            return summary_path
            
        except Exception as e:
            logger.error(
                f"摘要生成过程出错: {e}",
                video_id=video_info.video_id
            )
            return None
    
    def _select_summary_source(
        self,
        summary_language: str,
        translation_result: Dict[str, Optional[Path]],
        download_result: Dict[str, Optional[Path]]
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
            logger.info(f"使用翻译后的字幕作为摘要源: {translated_path.name}")
            return translated_path
        
        # 否则使用原始字幕
        original_path = download_result.get("original")
        if original_path and original_path.exists():
            logger.info(f"使用原始字幕作为摘要源: {original_path.name}")
            return original_path
        
        # 如果都没有，尝试使用任何可用的翻译字幕
        for lang, path in translation_result.items():
            if path and path.exists():
                logger.info(f"使用翻译字幕作为摘要源: {path.name} (语言: {lang})")
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
        except Exception as e:
            logger.error(f"读取 SRT 文件失败: {e}")
            return None
    
    def _extract_text_from_srt(self, srt_content: str) -> str:
        """从 SRT 格式中提取纯文本
        
        去除时间轴和序号，只保留字幕文本
        
        Args:
            srt_content: SRT 格式的字幕内容
        
        Returns:
            纯文本内容
        """
        import re
        
        # SRT 格式示例：
        # 1
        # 00:00:01,000 --> 00:00:03,000
        # Hello world
        # 
        # 2
        # 00:00:04,000 --> 00:00:06,000
        # This is a test
        
        # 移除序号行（纯数字行）
        lines = srt_content.split('\n')
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
                if i < len(lines) and '-->' in lines[i]:
                    i += 1
                continue
            
            # 跳过时间轴行（包含 -->）
            if '-->' in line:
                i += 1
                continue
            
            # 这是字幕文本行
            text_lines.append(line)
            i += 1
        
        # 合并文本行，用空格分隔
        return ' '.join(text_lines)
    
