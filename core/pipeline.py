"""
主流水线模块
串联：检测 → 下载 → 翻译 → 摘要 → 输出 → 增量更新
符合 error_handling.md 和 logging_spec.md 规范
"""
from pathlib import Path
from typing import Optional, Dict, List, Callable

from core.models import VideoInfo, DetectionResult
from core.language import LanguageConfig
from core.logger import get_logger, set_log_context, clear_log_context
from core.detector import SubtitleDetector
from core.downloader import SubtitleDownloader
from core.translator import SubtitleTranslator
from core.summarizer import Summarizer
from core.output import OutputWriter
from core.incremental import IncrementalManager
from core.failure_logger import FailureLogger
from core.llm_client import LLMClient
from core.exceptions import AppException, ErrorType, map_llm_error_to_app_error
from core.batch_id import generate_run_id
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
    force: bool = False,
    proxy_manager=None,
    cookie_manager=None,
    run_id: Optional[str] = None,
    on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
) -> bool:
    """处理单个视频的完整流程
    
    符合 error_handling.md 规范：
    - 使用统一的错误处理
    - 仅在最终失败时写入失败记录
    - 使用日志上下文（run_id, task, video_id）
    
    Args:
        video_info: 视频信息
        language_config: 语言配置
        llm: LLM 客户端
        output_writer: 输出写入器
        failure_logger: 失败记录器
        incremental_manager: 增量管理器
        archive_path: archive 文件路径（用于增量更新）
        force: 是否强制重跑（忽略增量）
        proxy_manager: 代理管理器
        cookie_manager: Cookie管理器
        run_id: 批次ID（run_id），如果为 None 则不设置上下文
    
    Returns:
        处理是否成功
    """
    # 设置日志上下文
    if run_id:
        set_log_context(run_id=run_id, task="process", video_id=video_info.video_id)
    
    try:
        # 步骤 1: 字幕检测
        set_log_context(run_id=run_id, task="detect", video_id=video_info.video_id)
        logger.info(f"检测字幕: {video_info.video_id} - {video_info.title[:50]}...", video_id=video_info.video_id)
        detector = SubtitleDetector(cookie_manager=cookie_manager)
        detection_result = detector.detect(video_info)
        
        if not detection_result.has_subtitles:
            error_msg = f"视频无可用字幕，跳过处理"
            logger.warning(error_msg, video_id=video_info.video_id)
            
            # 实时传递错误信息到 UI（如果提供了回调）
            if on_log:
                try:
                    on_log("WARN", error_msg, video_id=video_info.video_id)
                except Exception as log_error:
                    logger.warning(f"日志回调执行失败: {log_error}")
            
            failure_logger.log_failure(
                video_id=video_info.video_id,
                url=video_info.url,
                reason="无可用字幕",
                error_type=ErrorType.CONTENT,
                batch_id=run_id,
                channel_id=video_info.channel_id,
                channel_name=video_info.channel_name,
                stage="detect"
            )
            return False
        
        # 步骤 2: 字幕下载
        set_log_context(run_id=run_id, task="download", video_id=video_info.video_id)
        logger.info(f"下载字幕: {video_info.video_id}", video_id=video_info.video_id)
        downloader = SubtitleDownloader(proxy_manager=proxy_manager, cookie_manager=cookie_manager)
        temp_dir = Path("temp") / video_info.video_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        download_result = downloader.download(
            video_info,
            detection_result,
            language_config,
            temp_dir
        )
        
        if not download_result.get("original"):
            error_msg = f"下载原始字幕失败"
            logger.error(error_msg, video_id=video_info.video_id)
            
            # 实时传递错误信息到 UI（如果提供了回调）
            if on_log:
                try:
                    on_log("ERROR", error_msg, video_id=video_info.video_id)
                except Exception as log_error:
                    logger.warning(f"日志回调执行失败: {log_error}")
            
            failure_logger.log_download_failure(
                video_id=video_info.video_id,
                url=video_info.url,
                reason="下载原始字幕失败",
                error_type=ErrorType.NETWORK,  # 默认网络错误，实际应由 downloader 提供
                batch_id=run_id,
                channel_id=video_info.channel_id,
                channel_name=video_info.channel_name
            )
            return False
        
        # 步骤 3: 字幕翻译
        set_log_context(run_id=run_id, task="translate", video_id=video_info.video_id)
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
        
        # 检查是否所有目标语言都有翻译结果
        missing_languages = []
        for target_lang in language_config.subtitle_target_languages:
            translated_path = translation_result.get(target_lang)
            if not translated_path or not translated_path.exists():
                missing_languages.append(target_lang)
        
        if missing_languages:
            # 如果翻译策略是 OFFICIAL_ONLY 且没有可用翻译，应该停止任务
            if language_config.translation_strategy == "OFFICIAL_ONLY":
                error_msg = (
                    f"翻译策略为'只用官方多语言字幕'，但以下目标语言无可用官方字幕：{', '.join(missing_languages)}。\n"
                    f"请修改翻译策略为'优先官方字幕/自动翻译，无则用 AI'，或确保视频有对应的官方字幕。"
                )
                logger.error(error_msg, video_id=video_info.video_id)
                failure_logger.log_translation_failure(
                    video_id=video_info.video_id,
                    url=video_info.url,
                    reason=error_msg,
                    error_type=ErrorType.CONTENT,
                    batch_id=run_id,
                    channel_id=video_info.channel_id,
                    channel_name=video_info.channel_name
                )
                # 实时传递错误信息到 UI（如果提供了回调）
                if on_log:
                    try:
                        on_log("ERROR", error_msg, video_id=video_info.video_id)
                    except Exception as log_error:
                        logger.warning(f"日志回调执行失败: {log_error}")
                
                # 抛出异常，停止处理
                raise AppException(
                    message=error_msg,
                    error_type=ErrorType.CONTENT
                )
            else:
                # 其他策略下，翻译失败不视为整体失败，继续处理
                logger.warning(
                    f"以下目标语言翻译失败或无可用翻译：{', '.join(missing_languages)}",
                    video_id=video_info.video_id
                )
                failure_logger.log_translation_failure(
                    video_id=video_info.video_id,
                    url=video_info.url,
                    reason=f"翻译失败或无可用翻译：{', '.join(missing_languages)}",
                    error_type=ErrorType.UNKNOWN,
                    batch_id=run_id,
                    channel_id=video_info.channel_id,
                    channel_name=video_info.channel_name
                )
        
        # 步骤 4: 生成摘要
        summary_path = None
        if (has_translation or download_result.get("original")) and llm:
            set_log_context(run_id=run_id, task="summarize", video_id=video_info.video_id)
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
                    error_type=ErrorType.UNKNOWN,  # 默认未知错误，实际应由 summarizer 提供
                    batch_id=run_id,
                    channel_id=video_info.channel_id,
                    channel_name=video_info.channel_name
                )
                # 摘要失败不视为整体失败
        
        # 步骤 5: 写入输出文件
        set_log_context(run_id=run_id, task="output", video_id=video_info.video_id)
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
        
    except AppException as e:
        # 统一异常处理
        error_msg = f"处理视频失败: {e}"
        logger.error(
            error_msg,
            video_id=video_info.video_id,
            error_type=e.error_type.value
        )
        import traceback
        logger.debug(traceback.format_exc(), video_id=video_info.video_id)
        
        # 实时传递错误信息到 UI（如果提供了回调）
        if on_log:
            try:
                on_log("ERROR", error_msg, video_id=video_info.video_id)
            except Exception as log_error:
                logger.warning(f"日志回调执行失败: {log_error}")
        
        failure_logger.log_failure(
            video_id=video_info.video_id,
            url=video_info.url,
            reason=str(e),
            error_type=e.error_type,
            batch_id=run_id,
            channel_id=video_info.channel_id,
            channel_name=video_info.channel_name
        )
        return False
    except Exception as e:
        # 未映射的异常，转换为 AppException
        app_error = AppException(
            message=f"处理失败: {str(e)}",
            error_type=ErrorType.UNKNOWN,
            cause=e
        )
        error_msg = f"处理视频失败: {app_error}"
        logger.error(
            error_msg,
            video_id=video_info.video_id,
            error_type=app_error.error_type.value
        )
        import traceback
        logger.debug(traceback.format_exc(), video_id=video_info.video_id)
        
        # 实时传递错误信息到 UI（如果提供了回调）
        if on_log:
            try:
                on_log("ERROR", error_msg, video_id=video_info.video_id)
            except Exception as log_error:
                logger.warning(f"日志回调执行失败: {log_error}")
        
        failure_logger.log_failure(
            video_id=video_info.video_id,
            url=video_info.url,
            reason=str(app_error),
            error_type=app_error.error_type,
            batch_id=run_id,
            channel_id=video_info.channel_id,
            channel_name=video_info.channel_name
        )
        return False
    finally:
        # 清除日志上下文
        clear_log_context()


def process_video_list(
    videos: List[VideoInfo],
    language_config: LanguageConfig,
    llm: LLMClient,
    output_writer: OutputWriter,
    failure_logger: FailureLogger,
    incremental_manager: IncrementalManager,
    archive_path: Optional[Path],
    force: bool = False,
    concurrency: int = 3,
    proxy_manager=None,
    cookie_manager=None,
    run_id: Optional[str] = None,
    on_stats: Optional[Callable[[dict], None]] = None,
    on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
) -> Dict[str, int]:
    """处理视频列表（支持并发）
    
    符合 logging_spec.md 规范：
    - 生成 run_id（批次ID）并传递给所有子模块
    - 使用日志上下文（run_id, task, video_id）
    
    Args:
        videos: 视频列表
        language_config: 语言配置
        llm: LLM 客户端
        output_writer: 输出写入器
        failure_logger: 失败记录器
        incremental_manager: 增量管理器
        archive_path: archive 文件路径
        force: 是否强制重跑
        concurrency: 并发数，默认 3
        proxy_manager: 代理管理器
        cookie_manager: Cookie管理器
        run_id: 批次ID（run_id），如果为 None 则自动生成
        on_stats: 统计信息更新回调 (stats_dict)，可选
        on_log: 日志回调 (level, message, video_id)，可选
    
    Returns:
        统计信息：{"total": 总数, "success": 成功数, "failed": 失败数, "errors": 错误列表}
    """
    from core.task_runner import TaskRunner
    
    # 生成 run_id（如果未提供）
    if run_id is None:
        run_id = generate_run_id()
    
    # 设置全局日志上下文
    set_log_context(run_id=run_id, task="pipeline")
    
    total = len(videos)
    
    if total == 0:
        logger.warning("视频列表为空")
        clear_log_context()
        return {
            "total": 0,
            "success": 0,
            "failed": 0
        }
    
    logger.info(f"开始处理 {total} 个视频，并发数: {concurrency}", run_id=run_id)
    
    # 创建任务列表
    tasks = []
    task_names = []
    
    for video in videos:
        # 为每个视频创建一个任务函数
        # 使用 lambda 和默认参数来避免闭包变量捕获问题
        # 注意：lambda 的默认参数在定义时求值，确保每个任务捕获正确的 video
        def make_task(v: VideoInfo) -> Callable[[], bool]:
            """创建单个视频的处理任务（使用闭包捕获 video）"""
            def task():
                return process_single_video(
                    v,  # 这里 v 是闭包捕获的，每个任务都有独立的 v
                    language_config,
                    llm,
                    output_writer,
                    failure_logger,
                    incremental_manager,
                    archive_path,
                    force,
                    proxy_manager,
                    cookie_manager,
                    run_id,  # 传递 run_id
                    on_log,  # 传递日志回调，用于实时显示错误
                )
            return task
        
        tasks.append(make_task(video))
        task_names.append(f"{video.video_id} - {video.title[:30]}...")
    
    # 使用 TaskRunner 并发执行
    task_runner = TaskRunner(concurrency=concurrency)
    
    def progress_callback(completed: int, total: int):
        """进度回调"""
        if completed % max(1, total // 10) == 0 or completed == total:
            logger.info(f"处理进度: {completed}/{total} ({completed * 100 // total}%)")
        
        # 更新 UI 统计信息（如果提供了回调）
        if on_stats:
            try:
                # 统计当前成功和失败数量
                # 注意：这里只能统计已完成的，无法区分成功/失败
                # 实际的成功/失败数量需要等所有任务完成后才能准确统计
                stats = {
                    "total": total,
                    "success": 0,  # 暂时设为 0，等完成后更新
                    "failed": 0,   # 暂时设为 0，等完成后更新
                    "current": completed
                }
                on_stats(stats)
            except Exception as e:
                logger.warning(f"更新统计信息失败: {e}")
    
    result = task_runner.run_tasks(
        tasks=tasks,
        task_names=task_names,
        progress_callback=progress_callback
    )
    
    # 统计成功和失败数量
    success_count = sum(1 for r in result["results"] if r is True)
    failed_count = result["failed"]
    
    # 记录错误信息到日志和回调
    if result.get("errors"):
        for error_info in result["errors"]:
            error_msg = f"视频处理失败 [{error_info.get('task_name', 'unknown')}]: {error_info.get('error', '未知错误')}"
            logger.error(error_msg, run_id=run_id)
            if on_log:
                try:
                    # 从 task_name 中提取 video_id（格式：video_id - title...）
                    task_name = error_info.get("task_name", "")
                    video_id = None
                    if " - " in task_name:
                        video_id = task_name.split(" - ")[0]
                    on_log("ERROR", error_msg, video_id=video_id)
                except Exception as e:
                    logger.warning(f"日志回调执行失败: {e}")
    
    logger.info(
        f"处理完成: 总计 {total}，成功 {success_count}，失败 {failed_count}",
        run_id=run_id
    )
    
    # 清除日志上下文
    clear_log_context()
    
    return {
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "errors": result.get("errors", [])
    }
