"""
主流水线模块
串联：检测 → 下载 → 翻译 → 摘要 → 输出 → 增量更新
符合 error_handling.md 和 logging_spec.md 规范
"""
from pathlib import Path
from typing import Optional, Dict, List, Callable
import time

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

# 常量定义
MAX_TITLE_DISPLAY_LENGTH = 50


def _safe_log(
    on_log: Optional[Callable[[str, str, Optional[str]], None]],
    level: str,
    message: str,
    video_id: Optional[str] = None
):
    """安全的日志回调执行
    
    Args:
        on_log: 日志回调函数（可能为 None）
        level: 日志级别
        message: 日志消息
        video_id: 视频 ID（可选）
    """
    if on_log:
        try:
            on_log(level, message, video_id)
        except Exception as e:
            logger.warning(f"日志回调执行失败: {e}")


def process_single_video(
    video_info: VideoInfo,
    language_config: LanguageConfig,
    translation_llm: Optional[LLMClient],
    summary_llm: Optional[LLMClient],
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
        vid = video_info.video_id
        title_preview = video_info.title[:MAX_TITLE_DISPLAY_LENGTH]
        
        # 步骤 1: 字幕检测
        set_log_context(run_id=run_id, task="detect", video_id=vid)
        logger.info(f"检测字幕: {vid} - {title_preview}...", video_id=vid)
        detector = SubtitleDetector(cookie_manager=cookie_manager)
        detection_result = detector.detect(video_info)
        
        if not detection_result.has_subtitles:
            error_msg = "视频无可用字幕，跳过处理"
            logger.warning(error_msg, video_id=vid)
            _safe_log(on_log, "WARN", error_msg, vid)
            failure_logger.log_failure(
                video_id=vid,
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
        set_log_context(run_id=run_id, task="download", video_id=vid)
        logger.info(f"下载字幕: {vid}", video_id=vid)
        downloader = SubtitleDownloader(proxy_manager=proxy_manager, cookie_manager=cookie_manager)
        temp_dir = Path("temp") / vid
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        download_result = downloader.download(
            video_info,
            detection_result,
            language_config,
            temp_dir
        )
        
        if not download_result.get("original"):
            error_msg = "下载原始字幕失败"
            logger.error(error_msg, video_id=vid)
            _safe_log(on_log, "ERROR", error_msg, vid)
            failure_logger.log_download_failure(
                video_id=vid,
                url=video_info.url,
                reason="下载原始字幕失败",
                error_type=ErrorType.NETWORK,
                batch_id=run_id,
                channel_id=video_info.channel_id,
                channel_name=video_info.channel_name
            )
            return False
        
        # 步骤 3: 字幕翻译
        set_log_context(run_id=run_id, task="translate", video_id=vid)
        logger.info(f"翻译字幕: {vid}", video_id=vid)
        if not translation_llm:
            logger.warning("翻译 LLM 客户端不可用，跳过翻译", video_id=vid)
            translation_result = {}
        else:
            translator = SubtitleTranslator(llm=translation_llm, language_config=language_config)
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
        missing_languages = [
            target_lang
            for target_lang in language_config.subtitle_target_languages
            if not translation_result.get(target_lang) or not translation_result[target_lang].exists()
        ]
        
        if missing_languages:
            missing_str = ', '.join(missing_languages)
            if language_config.translation_strategy == "OFFICIAL_ONLY":
                # 如果翻译策略是 OFFICIAL_ONLY 且没有可用翻译，应该停止任务
                error_msg = (
                    f"翻译策略为'只用官方多语言字幕'，但以下目标语言无可用官方字幕：{missing_str}。\n"
                    f"请修改翻译策略为'优先官方字幕/自动翻译，无则用 AI'，或确保视频有对应的官方字幕。"
                )
                logger.error(error_msg, video_id=vid)
                failure_logger.log_translation_failure(
                    video_id=vid,
                    url=video_info.url,
                    reason=error_msg,
                    error_type=ErrorType.CONTENT,
                    batch_id=run_id,
                    channel_id=video_info.channel_id,
                    channel_name=video_info.channel_name
                )
                _safe_log(on_log, "ERROR", error_msg, vid)
                raise AppException(message=error_msg, error_type=ErrorType.CONTENT)
            else:
                # 其他策略下，翻译失败不视为整体失败，继续处理
                logger.warning(f"以下目标语言翻译失败或无可用翻译：{missing_str}", video_id=vid)
                failure_logger.log_translation_failure(
                    video_id=vid,
                    url=video_info.url,
                    reason=f"翻译失败或无可用翻译：{missing_str}",
                    error_type=ErrorType.UNKNOWN,
                    batch_id=run_id,
                    channel_id=video_info.channel_id,
                    channel_name=video_info.channel_name
                )
        
        # 步骤 4: 生成摘要
        summary_path = None
        if (has_translation or download_result.get("original")) and summary_llm:
            set_log_context(run_id=run_id, task="summarize", video_id=vid)
            logger.info(f"生成摘要: {vid}", video_id=vid)
            summarizer = Summarizer(llm=summary_llm, language_config=language_config)
            summary_path = summarizer.summarize(
                video_info,
                language_config,
                translation_result,
                download_result,
                temp_dir,
                force_regenerate=force
            )
            
            if not summary_path:
                logger.warning("摘要生成失败", video_id=vid)
                failure_logger.log_summary_failure(
                    video_id=vid,
                    url=video_info.url,
                    reason="摘要生成失败",
                    error_type=ErrorType.UNKNOWN,
                    batch_id=run_id,
                    channel_id=video_info.channel_id,
                    channel_name=video_info.channel_name
                )
                # 摘要失败不视为整体失败
        
        # 步骤 5: 写入输出文件
        set_log_context(run_id=run_id, task="output", video_id=vid)
        logger.info(f"写入输出文件: {vid}", video_id=vid)
        output_writer.write_all(
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
            incremental_manager.mark_as_processed(vid, archive_path)
            logger.debug(f"已更新增量记录: {vid}", video_id=vid)
        
        # 清理临时文件
        _cleanup_temp_dir(temp_dir)
        
        logger.info(f"处理完成: {vid}", video_id=vid)
        return True
        
    except AppException as e:
        error_msg = f"处理视频失败: {e}"
        _handle_processing_error(
            error_msg, e.error_type, video_info, failure_logger,
            run_id, on_log, str(e)
        )
        return False
    except Exception as e:
        app_error = AppException(
            message=f"处理失败: {str(e)}",
            error_type=ErrorType.UNKNOWN,
            cause=e
        )
        error_msg = f"处理视频失败: {app_error}"
        _handle_processing_error(
            error_msg, app_error.error_type, video_info, failure_logger,
            run_id, on_log, str(app_error)
        )
        return False
    finally:
        clear_log_context()


def _cleanup_temp_dir(temp_dir: Path):
    """清理临时目录"""
    try:
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception as e:
        logger.warning(f"清理临时文件失败: {e}")


def _handle_processing_error(
    error_msg: str,
    error_type: ErrorType,
    video_info: VideoInfo,
    failure_logger: FailureLogger,
    run_id: Optional[str],
    on_log: Optional[Callable],
    reason: str
):
    """处理视频处理过程中的错误（统一错误处理）
    
    Args:
        error_msg: 错误消息
        error_type: 错误类型
        video_info: 视频信息
        failure_logger: 失败记录器
        run_id: 批次 ID
        on_log: 日志回调
        reason: 失败原因
    """
    import traceback
    
    # 生成清晰的错误消息（包含错误类型和原因）
    error_type_name = _get_error_type_display_name(error_type)
    detailed_msg = f"[{error_type_name}] {video_info.video_id} - {reason}"
    
    logger.error(detailed_msg, video_id=video_info.video_id, error_type=error_type.value)
    logger.debug(traceback.format_exc(), video_id=video_info.video_id)
    
    _safe_log(on_log, "ERROR", detailed_msg, video_info.video_id)
    
    failure_logger.log_failure(
        video_id=video_info.video_id,
        url=video_info.url,
        reason=reason,
        error_type=error_type,
        batch_id=run_id,
        channel_id=video_info.channel_id,
        channel_name=video_info.channel_name
    )


def _get_error_type_display_name(error_type: ErrorType) -> str:
    """获取错误类型的显示名称
    
    Args:
        error_type: 错误类型
    
    Returns:
        错误类型的显示名称
    """
    error_type_names = {
        ErrorType.NETWORK: "网络错误",
        ErrorType.TIMEOUT: "超时",
        ErrorType.RATE_LIMIT: "限流",
        ErrorType.AUTH: "认证失败",
        ErrorType.CONTENT: "内容不可用",
        ErrorType.FILE_IO: "文件IO错误",
        ErrorType.PARSE: "解析错误",
        ErrorType.INVALID_INPUT: "输入无效",
        ErrorType.CANCELLED: "已取消",
        ErrorType.EXTERNAL_SERVICE: "外部服务错误",
        ErrorType.UNKNOWN: "未知错误",
    }
    return error_type_names.get(error_type, "未知错误")


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
        translation_llm: 翻译 LLM 客户端（可选）
        summary_llm: 摘要 LLM 客户端（可选）
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
                    translation_llm,  # 翻译 LLM 客户端
                    summary_llm,  # 摘要 LLM 客户端
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
    
    # ETA 计算相关变量
    start_time = time.time()
    last_eta_update = start_time
    min_samples_for_eta = 1  # 至少完成 1 个样本就开始显示 ETA（降低阈值以支持少量视频）
    eta_update_interval = 5.0  # ETA 更新间隔（秒，降低到 5 秒以更频繁更新）
    
    def progress_callback(completed: int, total: int, running_tasks: List[str]):
        """进度回调
        
        Args:
            completed: 已完成数量
            total: 总数量
            running_tasks: 正在运行的任务列表
        """
        nonlocal last_eta_update
        
        # 输出进度信息到日志（控制台和文件）
        # 对于少量视频，每次完成都显示；对于大量视频，每 10% 显示一次
        progress_interval = max(1, total // 10) if total >= 10 else 1
        if completed % progress_interval == 0 or completed == total:
            progress_msg = f"处理进度: {completed}/{total} ({completed * 100 // total}%)"
            logger.info(progress_msg)
            # 也通过 on_log 回调输出到 GUI
            _safe_log(on_log, "INFO", progress_msg)
        
        # 计算 ETA
        eta_seconds = None
        current_time = time.time()
        
        if completed >= min_samples_for_eta and completed < total:
            # 计算平均耗时
            elapsed = current_time - start_time
            if elapsed > 0 and completed > 0:
                avg_time_per_video = elapsed / completed
                remaining = total - completed
                eta_seconds = avg_time_per_video * remaining
                
                # 限制更新频率（对于少量视频，更频繁更新）
                update_interval = eta_update_interval if total >= 10 else 2.0
                if current_time - last_eta_update >= update_interval or completed == total:
                    last_eta_update = current_time
                    if eta_seconds >= 60:
                        eta_minutes = int(eta_seconds / 60)
                        eta_msg = f"预计剩余时间: 约 {eta_minutes} 分钟（仅供参考）"
                    else:
                        eta_msg = f"预计剩余时间: 约 {int(eta_seconds)} 秒（仅供参考）"
                    logger.info(eta_msg)
                    # 也通过 on_log 回调输出到 GUI
                    _safe_log(on_log, "INFO", eta_msg)
        
        # 显示正在处理的任务（每次更新都显示，但限制频率）
        if running_tasks:
            # 对于少量视频，更频繁显示；对于大量视频，每 20% 显示一次
            running_interval = max(1, total // 5) if total >= 10 else 1
            if completed == 0 or completed % running_interval == 0 or completed == total:
                running_text = ", ".join(running_tasks[:3])
                if len(running_tasks) > 3:
                    running_text += f" ... 还有 {len(running_tasks) - 3} 个"
                running_msg = f"正在处理: {running_text}"
                logger.info(running_msg)
                # 也通过 on_log 回调输出到 GUI
                _safe_log(on_log, "INFO", running_msg)
        
        # 更新 UI 统计信息（如果提供了回调）
        if on_stats:
            try:
                # 格式化正在处理的任务列表（最多显示 3 个）
                running_display = running_tasks[:3]
                if len(running_tasks) > 3:
                    running_display.append(f"... 还有 {len(running_tasks) - 3} 个")
                
                stats = {
                    "total": total,
                    "success": 0,  # 暂时设为 0，等完成后更新
                    "failed": 0,   # 暂时设为 0，等完成后更新
                    "current": completed,
                    "running": running_display,  # 正在处理的任务列表
                    "eta_seconds": eta_seconds  # 预计剩余时间（秒）
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
    
    # 统计错误分类
    error_counts = {}
    if result.get("errors"):
        for error_info in result["errors"]:
            error_type = error_info.get('error_type', 'unknown')
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            task_name = error_info.get('task_name', 'unknown')
            error_msg = f"视频处理失败 [{task_name}]: {error_info.get('error', '未知错误')}"
            logger.error(error_msg, run_id=run_id)
            # 从 task_name 中提取 video_id（格式：video_id - title...）
            video_id = task_name.split(" - ")[0] if " - " in task_name else None
            _safe_log(on_log, "ERROR", error_msg, video_id)
    
    # 生成错误分类摘要
    error_summary = []
    if error_counts:
        for error_type, count in sorted(error_counts.items()):
            error_type_name = _get_error_type_display_name(ErrorType(error_type))
            error_summary.append(f"{error_type_name}: {count}")
    
    logger.info(
        f"处理完成: 总计 {total}，成功 {success_count}，失败 {failed_count}",
        run_id=run_id
    )
    
    if error_summary:
        summary_msg = f"错误分类: {', '.join(error_summary)}"
        logger.info(summary_msg, run_id=run_id)
        _safe_log(on_log, "INFO", summary_msg, None)
    
    # 清除日志上下文
    clear_log_context()
    
    return {
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "errors": result.get("errors", []),
        "error_counts": error_counts  # 错误分类统计
    }
