"""
频道模式命令
处理 YouTube 频道/播放列表/单视频
"""

from pathlib import Path

from core.logger import get_logger
from cli.utils import get_archive_path, create_managers, print_summary


def channel_command(args):
    """处理频道命令

    Args:
        args: argparse 解析的参数

    Returns:
        退出码（0 表示成功）
    """
    logger = get_logger()
    from core.i18n import t

    if not args.url:
        logger.error(t("enter_channel_url"))
        return 1

    logger.info(t("log.url_type_identified", url_type="channel", url=args.url))

    if args.dry_run:
        return run_dry_run(args.url, logger, force=args.force)

    if args.run:
        return run_full_pipeline(args.url, logger, force=args.force)

    logger.warning(t("cli_select_mode_warning"))
    return 1


def run_dry_run(url: str, logger, force: bool = False) -> int:
    """执行 Dry Run 模式

    严格遵守"只检测、不下载、不摘要、不写报告、不更新增量"的语义
    但可以使用增量记录来过滤视频（不更新增量）

    Args:
        url: 频道/播放列表/单视频 URL
        logger: Logger 实例
        force: 是否强制重跑（忽略增量记录）

    Returns:
        退出码（0 表示成功）
    """
    from core.i18n import t
    logger.info("=" * 60)
    logger.info(t("dry_run_start"))
    if force:
        logger.info(t("force_rerun_enabled"))
    logger.info("=" * 60)

    try:
        from core.fetcher import VideoFetcher
        from core.detector import SubtitleDetector
        from core.incremental import IncrementalManager

        # 步骤 1: 获取视频列表
        logger.info(t("fetching_videos", url=url))
        fetcher = VideoFetcher()
        all_videos = fetcher.fetch_from_url(url)

        if not all_videos:
            logger.warning(t("no_videos_found"))
            return 1

        total_videos = len(all_videos)
        logger.info(t("videos_found", count=total_videos))

        # 步骤 1.5: 增量过滤（Dry Run 不更新增量，但可以使用增量过滤）
        incremental_manager = IncrementalManager()
        archive_path = get_archive_path(url, all_videos, incremental_manager, logger)

        if archive_path and not force:
            video_ids = [v.video_id for v in all_videos]
            unprocessed_ids = incremental_manager.filter_unprocessed(
                video_ids, archive_path, force=False
            )
            videos = [v for v in all_videos if v.video_id in unprocessed_ids]
            skipped_count = total_videos - len(videos)

            if skipped_count > 0:
                logger.info(
                    t("log.incremental_skip_processed", skipped=skipped_count, remaining=len(videos))
                )
            else:
                logger.info(t("log.incremental_not_found"))
        else:
            videos = all_videos
            if force:
                logger.info(t("log.force_rerun_mode"))

        if not videos:
            logger.info(t("log.video_already_processed"))
            return 0

        logger.info(t("detection_starting", count=len(videos)))

        # 步骤 2: 批量检测字幕
        detector = SubtitleDetector()

        has_subtitles_count = 0
        no_subtitles_count = 0

        for i, video in enumerate(videos, 1):
            logger.info(
                t("log.detect_subtitle_info", video_id=video.video_id, title_preview=video.title[:50])
            )

            try:
                result = detector.detect(video)

                if result.has_subtitles:
                    has_subtitles_count += 1
                    logger.info(
                        t("log.detect_subtitle_complete", video_id=video.video_id, manual_count=len(result.manual_languages), auto_count=len(result.auto_languages)),
                        video_id=video.video_id,
                    )
                else:
                    no_subtitles_count += 1
                    logger.warning(t("log.detect_no_subtitle"), video_id=video.video_id)

            except Exception as e:
                logger.error(t("log.detect_subtitle_failed", video_id=video.video_id, error=str(e)), video_id=video.video_id)

        # 步骤 3: 输出汇总统计
        logger.info("=" * 60)
        logger.info(t("log.detect_complete"))
        logger.info("=" * 60)
        logger.info(
            t("detection_complete", has_count=has_subtitles_count, no_count=no_subtitles_count)
        )
        if total_videos > len(videos):
            logger.info(
                t("log.incremental_skip_processed", skipped=total_videos - len(videos), remaining=len(videos))
            )
        logger.info("=" * 60)
        logger.info(t("log.output_skipped"))

        return 0

    except Exception as e:
        logger.error(t("dry_run_failed", error=str(e)))
        import traceback

        logger.debug(traceback.format_exc())
        return 1


def run_full_pipeline(url: str, logger, force: bool = False) -> int:
    """执行完整流水线（频道/播放列表/单视频）

    Args:
        url: 频道/播放列表/单视频 URL
        logger: Logger 实例
        force: 是否强制重跑

    Returns:
        退出码（0 表示成功）
    """
    from core.i18n import t
    logger.info("=" * 60)
    logger.info(t("start_processing"))
    logger.info("=" * 60)

    try:
        from core.fetcher import VideoFetcher
        from core.pipeline import process_video_list
        from core.output import OutputWriter
        from core.failure_logger import FailureLogger
        from core.incremental import IncrementalManager
        from config.manager import ConfigManager

        # 加载配置
        config_manager = ConfigManager()
        config = config_manager.load()

        # 创建管理器
        proxy_manager, cookie_manager = create_managers(config, logger)

        # 获取视频列表
        logger.info(t("fetching_videos", url=url))
        fetcher = VideoFetcher(
            proxy_manager=proxy_manager, cookie_manager=cookie_manager
        )
        all_videos = fetcher.fetch_from_url(url)

        if not all_videos:
            logger.warning(t("no_videos_found"))
            return 1

        total_videos = len(all_videos)
        logger.info(t("videos_found", count=total_videos))

        # 增量过滤
        incremental_manager = IncrementalManager()
        archive_path = get_archive_path(url, all_videos, incremental_manager, logger)

        if archive_path and not force:
            video_ids = [v.video_id for v in all_videos]
            unprocessed_ids = incremental_manager.filter_unprocessed(
                video_ids, archive_path, force=False
            )
            videos = [v for v in all_videos if v.video_id in unprocessed_ids]
            skipped_count = total_videos - len(videos)

            if skipped_count > 0:
                logger.info(
                    t("log.incremental_skip_processed", skipped=skipped_count, remaining=len(videos))
                )
            else:
                logger.info(t("log.incremental_not_found"))
        else:
            videos = all_videos
            if force:
                logger.info(t("log.force_rerun_mode"))

        if not videos:
            logger.info(t("log.video_already_processed"))
            return 0

        # 创建 LLM 客户端（翻译和摘要）
        from cli.utils import create_llm_clients

        translation_llm, summary_llm = create_llm_clients(config, logger)

        # 创建输出写入器和失败记录器
        output_dir = Path(config.output_dir)
        output_writer = OutputWriter(output_dir)
        failure_logger = FailureLogger(output_dir)

        # 定义进度回调（用于 CLI 显示）
        def on_stats_callback(stats_dict):
            """CLI 进度显示回调"""
            total = stats_dict.get("total", 0)
            current = stats_dict.get("current", 0)
            running = stats_dict.get("running", [])
            eta_seconds = stats_dict.get("eta_seconds")

            # 显示进度
            if total > 0:
                percent = (current * 100) // total
                logger.info(t("log.task_progress", current=current, total=total, percent=percent))

            # 显示正在处理的视频
            if running:
                running_text = ", ".join(running[:3])
                if len(running) > 3:
                    running_text += f" ... {t('log.task_processing', tasks=len(running) - 3)}"
                logger.info(t("log.task_processing", tasks=running_text))

            # 显示 ETA
            if eta_seconds is not None and eta_seconds > 0:
                eta_minutes = int(eta_seconds / 60)
                if eta_minutes > 0:
                    logger.info(t("log.task_eta_minutes", minutes=eta_minutes))
                else:
                    logger.info(t("log.task_eta_seconds", seconds=int(eta_seconds)))

        # 处理视频列表
        stats = process_video_list(
            videos,
            config.language,
            translation_llm,
            summary_llm,
            output_writer,
            failure_logger,
            incremental_manager,
            archive_path,
            force,
            dry_run=False,  # CLI 正常处理模式，不是 Dry Run
            concurrency=config.concurrency,
            proxy_manager=proxy_manager,
            cookie_manager=cookie_manager,
            on_stats=on_stats_callback,
        )

        # 输出汇总
        print_summary(logger, stats)

        return 0 if stats["failed"] == 0 else 1

    except Exception as e:
        logger.error(t("processing_failed", error=str(e)))
        import traceback

        logger.debug(traceback.format_exc())
        return 1
