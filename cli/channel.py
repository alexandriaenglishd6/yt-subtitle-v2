"""
频道模式命令
处理 YouTube 频道/播放列表/单视频
"""
from pathlib import Path

from core.logger import get_logger
from cli.utils import get_archive_path, create_managers, create_llm_client, print_summary


def channel_command(args):
    """处理频道命令
    
    Args:
        args: argparse 解析的参数
    
    Returns:
        退出码（0 表示成功）
    """
    logger = get_logger()
    
    if not args.url:
        logger.error("必须提供频道 URL（使用 --url 参数）")
        return 1
    
    logger.info(f"频道模式：URL = {args.url}")
    
    if args.dry_run:
        return run_dry_run(args.url, logger, force=args.force)
    
    if args.run:
        return run_full_pipeline(args.url, logger, force=args.force)
    
    logger.warning("请指定 --dry-run（仅检测）或 --run（开始处理）")
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
    logger.info("=" * 60)
    logger.info("Dry Run 模式：仅检测字幕，不下载/不翻译/不摘要/不更新增量")
    if force:
        logger.info("强制重跑模式：忽略历史记录，检测所有视频")
    logger.info("=" * 60)
    
    try:
        from core.fetcher import VideoFetcher
        from core.detector import SubtitleDetector
        from core.incremental import IncrementalManager
        
        # 步骤 1: 获取视频列表
        logger.info(f"开始获取视频列表: {url}")
        fetcher = VideoFetcher()
        all_videos = fetcher.fetch_from_url(url)
        
        if not all_videos:
            logger.warning("未能获取到任何视频，请检查 URL 是否正确")
            return 1
        
        total_videos = len(all_videos)
        logger.info(f"共获取到 {total_videos} 个视频")
        
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
                logger.info(f"增量过滤：跳过 {skipped_count} 个已处理视频，剩余 {len(videos)} 个待检测")
            else:
                logger.info("所有视频都是新视频，将全部检测")
        else:
            videos = all_videos
            if force:
                logger.info("强制重跑模式：将检测所有视频（忽略增量记录）")
        
        if not videos:
            logger.info("所有视频都已处理过，无需检测（使用 --force 可强制重跑）")
            return 0
        
        logger.info(f"开始检测 {len(videos)} 个视频的字幕...")
        
        # 步骤 2: 批量检测字幕
        detector = SubtitleDetector()
        
        has_subtitles_count = 0
        no_subtitles_count = 0
        
        for i, video in enumerate(videos, 1):
            logger.info(f"[{i}/{len(videos)}] 检测视频: {video.video_id} - {video.title[:50]}...")
            
            try:
                result = detector.detect(video)
                
                if result.has_subtitles:
                    has_subtitles_count += 1
                    manual_str = ", ".join(result.manual_languages) if result.manual_languages else "无"
                    auto_str = ", ".join(result.auto_languages) if result.auto_languages else "无"
                    logger.info(
                        f"  ✓ 有字幕 - 人工字幕: {manual_str}, 自动字幕: {auto_str}",
                        video_id=video.video_id
                    )
                else:
                    no_subtitles_count += 1
                    logger.warning(f"  ✗ 无可用字幕", video_id=video.video_id)
                    
            except Exception as e:
                logger.error(f"  ✗ 检测失败: {e}", video_id=video.video_id)
        
        # 步骤 3: 输出汇总统计
        logger.info("=" * 60)
        logger.info("Dry Run 检测完成")
        logger.info("=" * 60)
        logger.info(f"本次共检测 {len(videos)} 个视频：可处理 {has_subtitles_count} 个，无字幕 {no_subtitles_count} 个")
        if total_videos > len(videos):
            logger.info(f"（总视频数: {total_videos}，已跳过: {total_videos - len(videos)} 个已处理视频）")
        logger.info("=" * 60)
        logger.info("注意：Dry Run 模式下不下载、不翻译、不摘要、不写报告、不更新增量")
        
        return 0
        
    except Exception as e:
        logger.error(f"Dry Run 执行失败: {e}")
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
    logger.info("=" * 60)
    logger.info("开始执行完整流水线")
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
        logger.info(f"获取视频列表: {url}")
        fetcher = VideoFetcher(proxy_manager=proxy_manager, cookie_manager=cookie_manager)
        all_videos = fetcher.fetch_from_url(url)
        
        if not all_videos:
            logger.warning("未能获取到任何视频，请检查 URL 是否正确")
            return 1
        
        total_videos = len(all_videos)
        logger.info(f"共获取到 {total_videos} 个视频")
        
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
                logger.info(f"增量过滤：跳过 {skipped_count} 个已处理视频，剩余 {len(videos)} 个待处理")
            else:
                logger.info("所有视频都是新视频，将全部处理")
        else:
            videos = all_videos
            if force:
                logger.info("强制重跑模式：将处理所有视频（忽略增量记录）")
        
        if not videos:
            logger.info("所有视频都已处理过，无需处理（使用 --force 可强制重跑）")
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
                logger.info(f"进度: {current}/{total} ({percent}%)")
            
            # 显示正在处理的视频
            if running:
                running_text = ", ".join(running[:3])
                if len(running) > 3:
                    running_text += f" ... 还有 {len(running) - 3} 个"
                logger.info(f"正在处理: {running_text}")
            
            # 显示 ETA
            if eta_seconds is not None and eta_seconds > 0:
                eta_minutes = int(eta_seconds / 60)
                if eta_minutes > 0:
                    logger.info(f"预计剩余时间: 约 {eta_minutes} 分钟（仅供参考）")
                else:
                    logger.info(f"预计剩余时间: 约 {int(eta_seconds)} 秒（仅供参考）")
        
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
            concurrency=config.concurrency,
            proxy_manager=proxy_manager,
            cookie_manager=cookie_manager,
            on_stats=on_stats_callback
        )
        
        # 输出汇总
        print_summary(logger, stats)
        
        return 0 if stats['failed'] == 0 else 1
        
    except Exception as e:
        logger.error(f"执行完整流水线失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1

