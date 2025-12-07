"""
主流水线模块
串联：检测 → 下载 → 翻译 → 摘要 → 输出 → 增量更新
"""
from pathlib import Path
from typing import Optional, Dict, List

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger
from core.detector import SubtitleDetector
from core.downloader import SubtitleDownloader
from core.translator import SubtitleTranslator
from core.summarizer import Summarizer
from core.output import OutputWriter
from core.incremental import IncrementalManager
from core.failure_logger import FailureLogger
from core.llm_client import LLMClient
from config.manager import ConfigManager

logger = get_logger()


def process_single_video(
    video_info: VideoInfo,
    language_config: LanguageConfig,
    llm: LLMClient,
    output_writer: OutputWriter,
    failure_logger: FailureLogger,
    incremental_manager: IncrementalManager,
    archive_path: Optional[Path],
    force: bool = False
) -> bool:
    """处理单个视频的完整流程
    
    Args:
        video_info: 视频信息
        language_config: 语言配置
        llm: LLM 客户端
        output_writer: 输出写入器
        failure_logger: 失败记录器
        incremental_manager: 增量管理器
        archive_path: archive 文件路径（用于增量更新）
        force: 是否强制重跑（忽略增量）
    
    Returns:
        处理是否成功
    """
    try:
        # 步骤 1: 字幕检测
        logger.info(f"检测字幕: {video_info.video_id} - {video_info.title[:50]}...", video_id=video_info.video_id)
        detector = SubtitleDetector()
        detection_result = detector.detect(video_info)
        
        if not detection_result.has_subtitles:
            logger.warning(f"视频无可用字幕，跳过处理", video_id=video_info.video_id)
            failure_logger.log_failure(
                video_id=video_info.video_id,
                url=video_info.url,
                reason="无可用字幕",
                channel_id=video_info.channel_id,
                channel_name=video_info.channel_name,
                stage="detect"
            )
            return False
        
        # 步骤 2: 字幕下载
        logger.info(f"下载字幕: {video_info.video_id}", video_id=video_info.video_id)
        downloader = SubtitleDownloader()
        temp_dir = Path("temp") / video_info.video_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        download_result = downloader.download(
            video_info,
            detection_result,
            language_config,
            temp_dir
        )
        
        if not download_result.get("original"):
            logger.error(f"下载原始字幕失败", video_id=video_info.video_id)
            failure_logger.log_download_failure(
                video_id=video_info.video_id,
                url=video_info.url,
                reason="下载原始字幕失败",
                channel_id=video_info.channel_id,
                channel_name=video_info.channel_name
            )
            return False
        
        # 步骤 3: 字幕翻译
        logger.info(f"翻译字幕: {video_info.video_id}", video_id=video_info.video_id)
        if not llm:
            logger.warning(f"LLM 客户端不可用，跳过翻译", video_id=video_info.video_id)
            translation_result = {}
        else:
            translator = SubtitleTranslator(llm=llm, language_config=language_config)
            
            translation_result = translator.translate(
                video_info,
                detection_result,
                language_config,
                download_result,
                temp_dir,
                force_retranslate=force
            )
        
        # 检查是否有翻译结果
        has_translation = any(
            path and path.exists()
            for path in translation_result.values()
        )
        
        if not has_translation:
            logger.warning(f"翻译失败或无可用翻译", video_id=video_info.video_id)
            failure_logger.log_translation_failure(
                video_id=video_info.video_id,
                url=video_info.url,
                reason="翻译失败或无可用翻译",
                channel_id=video_info.channel_id,
                channel_name=video_info.channel_name
            )
            # 翻译失败不视为整体失败，继续处理
        
        # 步骤 4: 生成摘要
        summary_path = None
        if (has_translation or download_result.get("original")) and llm:
            logger.info(f"生成摘要: {video_info.video_id}", video_id=video_info.video_id)
            summarizer = Summarizer(llm=llm, language_config=language_config)
            
            summary_path = summarizer.summarize(
                video_info,
                language_config,
                translation_result,
                download_result,
                temp_dir,
                force_regenerate=force
            )
            
            if not summary_path:
                logger.warning(f"摘要生成失败", video_id=video_info.video_id)
                failure_logger.log_summary_failure(
                    video_id=video_info.video_id,
                    url=video_info.url,
                    reason="摘要生成失败",
                    channel_id=video_info.channel_id,
                    channel_name=video_info.channel_name
                )
                # 摘要失败不视为整体失败
        
        # 步骤 5: 写入输出文件
        logger.info(f"写入输出文件: {video_info.video_id}", video_id=video_info.video_id)
        video_output_dir = output_writer.write_all(
            video_info,
            detection_result,
            language_config,
            download_result,
            translation_result,
            summary_path,
            channel_name=video_info.channel_name,
            channel_id=video_info.channel_id
        )
        
        # 步骤 6: 更新增量记录（仅在成功时）
        if archive_path:
            incremental_manager.mark_as_processed(video_info.video_id, archive_path)
            logger.debug(f"已更新增量记录: {video_info.video_id}", video_id=video_info.video_id)
        
        # 清理临时文件
        try:
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
        
        logger.info(f"处理完成: {video_info.video_id}", video_id=video_info.video_id)
        return True
        
    except Exception as e:
        logger.error(f"处理视频失败: {e}", video_id=video_info.video_id)
        import traceback
        logger.debug(traceback.format_exc(), video_id=video_info.video_id)
        
        failure_logger.log_failure(
            video_id=video_info.video_id,
            url=video_info.url,
            reason=f"处理失败: {str(e)}",
            channel_id=video_info.channel_id,
            channel_name=video_info.channel_name
        )
        return False


def process_video_list(
    videos: List[VideoInfo],
    language_config: LanguageConfig,
    llm: LLMClient,
    output_writer: OutputWriter,
    failure_logger: FailureLogger,
    incremental_manager: IncrementalManager,
    archive_path: Optional[Path],
    force: bool = False
) -> Dict[str, int]:
    """处理视频列表
    
    Args:
        videos: 视频列表
        language_config: 语言配置
        llm: LLM 客户端
        output_writer: 输出写入器
        failure_logger: 失败记录器
        incremental_manager: 增量管理器
        archive_path: archive 文件路径
        force: 是否强制重跑
    
    Returns:
        统计信息：{"total": 总数, "success": 成功数, "failed": 失败数}
    """
    total = len(videos)
    success_count = 0
    failed_count = 0
    
    logger.info(f"开始处理 {total} 个视频...")
    
    for i, video in enumerate(videos, 1):
        logger.info(f"[{i}/{total}] 处理视频: {video.video_id}")
        
        success = process_single_video(
            video,
            language_config,
            llm,
            output_writer,
            failure_logger,
            incremental_manager,
            archive_path,
            force
        )
        
        if success:
            success_count += 1
        else:
            failed_count += 1
    
    return {
        "total": total,
        "success": success_count,
        "failed": failed_count
    }
