"""
批量视频处理模块
支持 TaskRunner 模式和 StagedPipeline 模式
"""

from pathlib import Path
from typing import Optional, Dict, List, Callable
import time

from core.models import VideoInfo
from core.language import LanguageConfig
from core.logger import get_logger, set_log_context, clear_log_context
from core.output import OutputWriter
from core.incremental import IncrementalManager
from core.failure_logger import FailureLogger
from core.llm_client import LLMClient
from core.exceptions import ErrorType
from core.cancel_token import CancelToken
from core.batch_id import generate_run_id

from .single_video import process_single_video
from .utils import safe_log

logger = get_logger()


def process_video_list(
    videos: List[VideoInfo],
    language_config: LanguageConfig,
    translation_llm: Optional[LLMClient],
    summary_llm: Optional[LLMClient],
    output_writer: OutputWriter,
    failure_logger: FailureLogger,
    incremental_manager: IncrementalManager,
    archive_path: Optional[Path],
    force: bool = False,
    dry_run: bool = False,
    cancel_token: Optional[CancelToken] = None,
    concurrency: int = 10,
    ai_concurrency: int = 5,
    proxy_manager=None,
    cookie_manager=None,
    run_id: Optional[str] = None,
    on_stats: Optional[Callable[[dict], None]] = None,
    on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
    on_error: Optional[Callable[[ErrorType, str], None]] = None,
    translation_llm_init_error_type: Optional[ErrorType] = None,
    translation_llm_init_error: Optional[str] = None,
    use_staged_pipeline: bool = True,
    initial_url_count: int = 0,  # 初始 URL 数量（用于保持 total 不变）
    fetch_failed_count: int = 0,  # URL 获取阶段失败的数量
) -> Dict[str, int]:
    """处理视频列表（支持并发）

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
        dry_run: 是否为干跑模式
        cancel_token: 取消令牌
        concurrency: 并发数
        proxy_manager: 代理管理器
        cookie_manager: Cookie管理器
        run_id: 批次ID
        on_stats: 统计信息更新回调
        on_log: 日志回调
        translation_llm_init_error_type: 翻译 LLM 初始化错误类型
        translation_llm_init_error: 翻译 LLM 初始化错误信息
        use_staged_pipeline: 是否使用分阶段 Pipeline

    Returns:
        统计信息
    """
    # 生成 run_id（如果未提供）
    if run_id is None:
        run_id = generate_run_id()

    # 设置全局日志上下文
    set_log_context(run_id=run_id, task="pipeline")

    total = len(videos)

    if total == 0:
        logger.warning_i18n("task_video_list_empty")
        clear_log_context()
        return {"total": 0, "success": 0, "failed": 0}

    # 如果使用分阶段 Pipeline，调用新的实现
    if use_staged_pipeline:
        return _process_video_list_staged(
            videos=videos,
            language_config=language_config,
            translation_llm=translation_llm,
            summary_llm=summary_llm,
            output_writer=output_writer,
            failure_logger=failure_logger,
            incremental_manager=incremental_manager,
            archive_path=archive_path,
            force=force,
            dry_run=dry_run,
            cancel_token=cancel_token,
            concurrency=concurrency,
            ai_concurrency=ai_concurrency,
            proxy_manager=proxy_manager,
            cookie_manager=cookie_manager,
            run_id=run_id,
            on_stats=on_stats,
            on_log=on_log,
            translation_llm_init_error_type=translation_llm_init_error_type,
            translation_llm_init_error=translation_llm_init_error,
            initial_url_count=initial_url_count,
            fetch_failed_count=fetch_failed_count,
        )

    # 否则使用旧的实现（TaskRunner 方式）
    from core.task_runner import TaskRunner

    logger.info_i18n("task_start", total=total, concurrency=concurrency, run_id=run_id)

    # 创建任务列表
    tasks = []
    task_names = []

    for video in videos:

        def make_task(v: VideoInfo) -> Callable[[], bool]:
            """创建单个视频的处理任务"""

            def task():
                return process_single_video(
                    v,
                    language_config,
                    translation_llm,
                    summary_llm,
                    output_writer,
                    failure_logger,
                    incremental_manager,
                    archive_path,
                    force,
                    dry_run,
                    cancel_token,
                    proxy_manager,
                    cookie_manager,
                    run_id,
                    on_log,
                    translation_llm_init_error_type,
                    translation_llm_init_error,
                )

            return task

        tasks.append(make_task(video))
        task_names.append(f"{video.video_id} - {video.title[:30]}...")

    # 使用 TaskRunner 并发执行
    task_runner = TaskRunner(concurrency=concurrency)

    # ETA 计算相关变量
    start_time = time.time()
    last_eta_update = start_time
    min_samples_for_eta = 1
    eta_update_interval = 5.0

    def progress_callback(completed: int, total: int, running_tasks: List[str]):
        """进度回调"""
        nonlocal last_eta_update

        # 检查取消状态
        if cancel_token and cancel_token.is_cancelled():
            reason = cancel_token.get_reason() or "用户取消"
            msg = logger.info_i18n("task_cancelled", reason=reason, run_id=run_id)
            safe_log(on_log, "INFO", msg)
            return

        # 输出进度信息
        progress_interval = max(1, total // 10) if total >= 10 else 1
        if completed % progress_interval == 0 or completed == total:
            progress_msg = logger.info_i18n(
                "task_progress",
                current=completed,
                total=total,
                percent=completed * 100 // total,
            )
            safe_log(on_log, "INFO", progress_msg)

        # 计算 ETA
        eta_seconds = None
        current_time = time.time()

        if completed >= min_samples_for_eta and completed < total:
            elapsed = current_time - start_time
            if elapsed > 0 and completed > 0:
                avg_time_per_video = elapsed / completed
                remaining = total - completed
                eta_seconds = avg_time_per_video * remaining

                update_interval = eta_update_interval if total >= 10 else 2.0
                if (
                    current_time - last_eta_update >= update_interval
                    or completed == total
                ):
                    last_eta_update = current_time
                    if eta_seconds >= 60:
                        eta_minutes = int(eta_seconds / 60)
                        eta_msg = logger.info_i18n("eta_remaining", minutes=eta_minutes)
                    else:
                        eta_msg = logger.info_i18n(
                            "eta_remaining_seconds", seconds=int(eta_seconds)
                        )
                    safe_log(on_log, "INFO", eta_msg)

        # 显示正在处理的任务
        if running_tasks:
            running_interval = max(1, total // 5) if total >= 10 else 1
            if (
                completed == 0
                or completed % running_interval == 0
                or completed == total
            ):
                running_text = ", ".join(running_tasks[:3])
                if len(running_tasks) > 3:
                    from core.logger import translate_log

                    running_text += f" ... {translate_log('log.more_tasks_prefix')} {len(running_tasks) - 3} {translate_log('log.more_tasks_suffix')}"
                running_msg = logger.info_i18n("task_processing", tasks=running_text)
                safe_log(on_log, "INFO", running_msg)

        # 更新 UI 统计信息
        if on_stats:
            try:
                running_display = running_tasks[:3]
                if len(running_tasks) > 3:
                    running_display.append(f"... 还有 {len(running_tasks) - 3} 个")

                stats = {
                    "total": total,
                    "success": 0,
                    "failed": 0,
                    "current": completed,
                    "running": running_display,
                    "eta_seconds": eta_seconds,
                }
                on_stats(stats)
            except Exception as e:
                logger.warning_i18n("stats_update_failed", error=str(e))

    result = task_runner.run_tasks(
        tasks=tasks, task_names=task_names, progress_callback=progress_callback
    )

    # 统计成功和失败数量
    success_count = sum(1 for r in result["results"] if r is True)
    failed_count = result["failed"]

    logger.info_i18n(
        "task_complete",
        total=total,
        success=success_count,
        failed=failed_count,
        run_id=run_id,
    )

    # 清除日志上下文
    clear_log_context()

    return {
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "errors": result.get("errors", []),
    }


def _process_video_list_staged(
    videos: List[VideoInfo],
    language_config: LanguageConfig,
    translation_llm: Optional[LLMClient],
    summary_llm: Optional[LLMClient],
    output_writer: OutputWriter,
    failure_logger: FailureLogger,
    incremental_manager: IncrementalManager,
    archive_path: Optional[Path],
    force: bool = False,
    dry_run: bool = False,
    cancel_token: Optional[CancelToken] = None,
    concurrency: int = 10,
    ai_concurrency: int = 5,
    proxy_manager=None,
    cookie_manager=None,
    run_id: Optional[str] = None,
    on_stats: Optional[Callable[[dict], None]] = None,
    on_log: Optional[Callable[[str, str, Optional[str]], None]] = None,
    on_error: Optional[Callable[[ErrorType, str], None]] = None,
    translation_llm_init_error_type: Optional[ErrorType] = None,
    translation_llm_init_error: Optional[str] = None,
    initial_url_count: int = 0,  # 初始 URL 数量
    fetch_failed_count: int = 0,  # URL 获取阶段失败的数量
) -> Dict[str, int]:
    """使用分阶段队列化 Pipeline 处理视频列表

    Args:
        与 process_video_list 相同

    Returns:
        统计信息
    """
    from core.staged_pipeline import StagedPipeline
    from core.staged_pipeline.data_types import StageData

    # 使用初始 URL 数量作为 total（如果没有传入则使用视频数量）
    total = initial_url_count if initial_url_count > 0 else len(videos)
    videos_count = len(videos)  # 实际要处理的视频数量

    # 根据总并发数配置各阶段的并发数
    detect_concurrency = max(1, concurrency)
    download_concurrency = max(1, concurrency)
    translate_concurrency = max(1, ai_concurrency)
    summarize_concurrency = max(1, ai_concurrency)
    output_concurrency = max(1, concurrency)

    logger.info_i18n(
        "task_start_staged",
        total=total,
        detect=detect_concurrency,
        download=download_concurrency,
        translate=translate_concurrency,
        summarize=summarize_concurrency,
        output=output_concurrency,
        run_id=run_id,
    )

    # 创建 ManifestManager 用于断点续传状态管理
    from core.state.manifest import ManifestManager, VideoStage
    
    manifest_dir = output_writer.base_output_dir / ".state"
    manifest_manager = ManifestManager(manifest_dir)
    batch_manifest = manifest_manager.create_batch(
        batch_id=run_id,
        source=f"batch_{total}_videos",
    )
    
    # 添加所有视频到 BatchManifest
    for video in videos:
        batch_manifest.add_video(
            video_id=video.video_id,
            url=video.url,
            title=video.title,
        )
    
    # 保存初始 manifest
    manifest_manager.save_batch(batch_manifest)
    logger.debug(f"Created batch manifest: {run_id}", run_id=run_id)

    # 创建视频完成回调，更新 manifest 状态
    def on_video_complete(data):
        """视频处理完成时更新 manifest"""
        try:
            video_id = data.video_info.video_id if data.video_info else None
            if video_id:
                video_manifest = batch_manifest.get_video(video_id)
                if video_manifest:
                    video_manifest.update_stage(VideoStage.DONE)
                    manifest_manager.save_batch(batch_manifest)
                    logger.debug(f"Updated manifest: {video_id} -> DONE")
        except Exception as e:
            logger.warning(f"Failed to update manifest for video: {e}")

    # 创建分阶段 Pipeline
    pipeline = StagedPipeline(
        language_config=language_config,
        translation_llm=translation_llm,
        summary_llm=summary_llm,
        output_writer=output_writer,
        failure_logger=failure_logger,
        incremental_manager=incremental_manager,
        archive_path=archive_path,
        force=force,
        dry_run=dry_run,
        cancel_token=cancel_token,
        proxy_manager=proxy_manager,
        cookie_manager=cookie_manager,
        run_id=run_id,
        on_log=on_log,
        on_error=lambda data: on_error(data.error_type, str(data.error)) if on_error and data.error_type else None,
        on_video_complete=on_video_complete,  # 视频完成回调
        detect_concurrency=detect_concurrency,
        download_concurrency=download_concurrency,
        translate_concurrency=translate_concurrency,
        summarize_concurrency=summarize_concurrency,
        output_concurrency=output_concurrency,
        translation_llm_init_error_type=translation_llm_init_error_type,
        translation_llm_init_error=translation_llm_init_error,
    )

    # 处理视频
    try:
        # 如果需要实时统计更新，启动一个后台线程定期更新
        if on_stats:
            import threading

            stats_update_thread = None
            stop_stats_update = threading.Event()

            def stats_updater():
                """定期更新统计信息"""
                from core.progress.eta import ProgressTracker
                
                progress_tracker = ProgressTracker(total=total, task_name="video_processing")
                last_completed = 0
                last_update_time = time.time()
                
                # 发送初始 stats 确保 total 正确显示
                try:
                    initial_stats = {
                        "total": total,
                        "success": 0,
                        "failed": 0,
                        "current": 0,
                        "running": [],
                        "eta_seconds": None,
                        "eta_message": "",
                    }
                    logger.info(f"stats_updater sending initial stats: total={total}")
                    on_stats(initial_stats)
                except Exception as e:
                    logger.warning(f"stats_updater initial on_stats failed: {e}")
                
                while not stop_stats_update.is_set():
                    try:
                        # 获取各阶段统计
                        detect_stats = pipeline.detect_queue.get_stats()
                        download_stats = pipeline.download_queue.get_stats()
                        translate_stats = pipeline.translate_queue.get_stats()
                        summarize_stats = pipeline.summarize_queue.get_stats()
                        output_stats = pipeline.output_queue.get_stats()

                        # 计算成功数和失败数
                        success_count = output_stats["processed"]
                        # 失败数 = 总数 - 成功数 - 仍在队列中的数量
                        # 注意：不能简单用 total - success，因为可能还有视频在处理中
                        # 但为了避免重复计数，使用 (已完成数 - 成功数) 来计算失败数
                        # 已完成数 = 总入队数 - 各阶段仍在队列中的数
                        in_queue_count = (
                            detect_stats["pending"] + detect_stats["processing"]
                            + download_stats["pending"] + download_stats["processing"]
                            + translate_stats["pending"] + translate_stats["processing"]
                            + summarize_stats["pending"] + summarize_stats["processing"]
                            + output_stats["pending"] + output_stats["processing"]
                        )
                        completed_count = len(videos) - in_queue_count
                        failed_count = completed_count - success_count if completed_count > success_count else 0
                        
                        current_completed = success_count + failed_count
                        
                        # 记录新完成的视频到 ProgressTracker
                        if current_completed > last_completed:
                            current_time = time.time()
                            # 计算每个新完成视频的平均耗时
                            num_new = current_completed - last_completed
                            elapsed = current_time - last_update_time
                            avg_duration = elapsed / num_new if num_new > 0 else 0
                            
                            for i in range(num_new):
                                progress_tracker.record_completed(
                                    item_id=f"video_{last_completed + i + 1}",
                                    duration=avg_duration,
                                )
                            
                            last_completed = current_completed
                            last_update_time = current_time
                        
                        # 获取 ETA
                        progress_info = progress_tracker.eta_calculator.get_progress()
                        eta_seconds = progress_info.get("eta_seconds")

                        # 获取代理状态
                        proxy_healthy = 0
                        proxy_unhealthy = 0
                        if proxy_manager and hasattr(proxy_manager, 'get_healthy_count'):
                            proxy_healthy = proxy_manager.get_healthy_count()
                            proxy_unhealthy = proxy_manager.get_unhealthy_count()

                        stats = {
                            "total": total,
                            "success": success_count,
                            "failed": failed_count,
                            "current": current_completed,
                            "running": [],
                            "eta_seconds": eta_seconds,
                            "eta_message": progress_tracker.get_eta_message(),
                            "proxy_healthy": proxy_healthy,
                            "proxy_unhealthy": proxy_unhealthy,
                        }

                        try:
                            on_stats(stats)
                        except Exception as e:
                            logger.warning_i18n(
                                "stats_update_callback_failed", error=str(e)
                            )

                        # 每 0.5 秒更新一次
                        if stop_stats_update.wait(0.5):
                            break
                    except Exception as e:
                        logger.warning_i18n("stats_update_thread_error", error=str(e))
                        break

            stats_update_thread = threading.Thread(target=stats_updater, daemon=True)
            stats_update_thread.start()

        # 执行处理
        stats = pipeline.process_videos(videos)

        # 停止统计更新线程
        if on_stats and "stats_update_thread" in locals():
            stop_stats_update.set()
            stats_update_thread.join(timeout=1.0)

        # 更新 BatchManifest 的最终状态
        success_count = stats.get("success", 0)
        failed_count = stats.get("failed", 0)
        
        # 根据结果更新视频状态（简化：仅标记完成数量，不跟踪具体哪些视频）
        batch_manifest.updated_at = datetime.now().isoformat() if 'datetime' in dir() else None
        try:
            from datetime import datetime as dt
            batch_manifest.updated_at = dt.now().isoformat()
        except Exception:
            pass
        
        # 保存最终 manifest
        manifest_manager.save_batch(batch_manifest)
        logger.debug(
            f"Batch complete: {success_count}/{total} success, {failed_count} failed",
            run_id=run_id,
        )

        # 返回统计信息
        return {
            "total": stats.get("total", total),
            "success": success_count,
            "failed": failed_count,
            "errors": [],
            "manifest_path": str(manifest_manager._get_manifest_path(run_id)),
        }

    except Exception as e:
        logger.error_i18n("pipeline_staged_failed", error=str(e), run_id=run_id)
        import traceback

        logger.debug(traceback.format_exc(), run_id=run_id)
        if on_log:
            try:
                on_log("ERROR", logger.error_i18n("processing_failed", error=str(e)))
            except Exception:
                pass

        # 返回错误统计
        return {
            "total": total,
            "success": 0,
            "failed": total,
            "errors": [{"error": str(e), "error_type": "unknown"}],
        }

    finally:
        # 清理日志上下文
        clear_log_context()
