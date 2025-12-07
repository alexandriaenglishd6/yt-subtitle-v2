"""
CLI 入口（支持频道/URL 模式）
命令行接口
"""
import argparse
import sys
from pathlib import Path

from config.manager import ConfigManager
from core.logger import get_logger


def channel_command(args):
    """处理频道命令
    
    Args:
        args: argparse 解析的参数
    """
    logger = get_logger()
    
    if not args.url:
        logger.error("必须提供频道 URL（使用 --url 参数）")
        return 1
    
    logger.info(f"频道模式：URL = {args.url}")
    
    if args.dry_run:
        return _run_dry_run(args.url, logger, force=args.force)
    
    if args.run:
        return _run_full_pipeline(args.url, logger, force=args.force)
    
    # 如果没有指定 --dry-run 或 --run，默认提示
    logger.warning("请指定 --dry-run（仅检测）或 --run（开始处理）")
    return 1


def _run_dry_run(url: str, logger, force: bool = False) -> int:
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
        archive_path = _get_archive_path(url, all_videos, incremental_manager, logger)
        
        if archive_path and not force:
            # 使用增量过滤未处理的视频
            video_ids = [v.video_id for v in all_videos]
            unprocessed_ids = incremental_manager.filter_unprocessed(
                video_ids, archive_path, force=False
            )
            
            # 只保留未处理的视频
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
        
        processed_count = 0
        has_subtitles_count = 0
        no_subtitles_count = 0
        
        for i, video in enumerate(videos, 1):
            logger.info(f"[{i}/{len(videos)}] 检测视频: {video.video_id} - {video.title[:50]}...")
            
            try:
                result = detector.detect(video)
                processed_count += 1
                
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
                    logger.warning(
                        f"  ✗ 无可用字幕",
                        video_id=video.video_id
                    )
                    
            except Exception as e:
                logger.error(f"  ✗ 检测失败: {e}", video_id=video.video_id)
                processed_count += 1
        
        # 步骤 3: 输出汇总统计（符合 v2_final_plan.md 要求）
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


def _get_archive_path(
    url: str,
    videos: list,
    incremental_manager,
    logger
):
    """根据 URL 类型和视频列表确定 archive 文件路径
    
    Args:
        url: 原始 URL
        videos: 视频列表
        incremental_manager: IncrementalManager 实例
        logger: Logger 实例
    
    Returns:
        archive 文件路径，如果无法确定则返回 None
    """
    from core.fetcher import VideoFetcher
    from urllib.parse import urlparse, parse_qs
    from typing import Optional
    
    try:
        fetcher = VideoFetcher()
        url_type = fetcher.identify_url_type(url)
        
        if url_type == "channel":
            # 频道模式：使用 channel_id
            if videos and videos[0].channel_id:
                channel_id = videos[0].channel_id
                archive_path = incremental_manager.get_channel_archive_path(channel_id)
                logger.info(f"频道模式：使用 archive 文件 {archive_path.name}")
                return archive_path
            else:
                logger.warning("无法获取频道 ID，将不使用增量过滤")
                return None
        
        elif url_type == "playlist":
            # 播放列表模式：从 URL 提取播放列表 ID
            # 播放列表 URL 格式：https://www.youtube.com/playlist?list=PLxxxxxx
            parsed = urlparse(url)
            playlist_id = parse_qs(parsed.query).get("list", [None])[0]
            if playlist_id:
                # 使用播放列表 ID 作为 archive 文件名
                archive_path = incremental_manager.archives_dir / f"playlist_{playlist_id}.txt"
                logger.info(f"播放列表模式：使用 archive 文件 {archive_path.name}")
                return archive_path
            else:
                logger.warning("无法提取播放列表 ID，将不使用增量过滤")
                return None
        
        elif url_type == "video":
            # 单视频模式：不使用增量（单视频通常不需要增量）
            return None
        
        else:
            # URL 列表模式：在 urls_command 中处理
            return None
            
    except Exception as e:
        logger.warning(f"确定 archive 路径时出错: {e}")
        return None


def _run_full_pipeline(url: str, logger, force: bool = False) -> int:
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
        from core.ai_providers import create_llm_client
        from core.output import OutputWriter
        from core.failure_logger import FailureLogger
        from core.incremental import IncrementalManager
        from config.manager import ConfigManager
        
        # 加载配置
        config_manager = ConfigManager()
        config = config_manager.load()
        
        # 获取视频列表
        logger.info(f"获取视频列表: {url}")
        fetcher = VideoFetcher()
        all_videos = fetcher.fetch_from_url(url)
        
        if not all_videos:
            logger.warning("未能获取到任何视频，请检查 URL 是否正确")
            return 1
        
        total_videos = len(all_videos)
        logger.info(f"共获取到 {total_videos} 个视频")
        
        # 增量过滤
        incremental_manager = IncrementalManager()
        archive_path = _get_archive_path(url, all_videos, incremental_manager, logger)
        
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
        
        # 创建 LLM 客户端
        try:
            llm = create_llm_client(config.ai)
        except Exception as e:
            logger.error(f"创建 LLM 客户端失败: {e}")
            logger.warning("AI 翻译和摘要功能将不可用，但会继续处理其他步骤")
            llm = None
        
        # 创建输出写入器和失败记录器
        output_dir = Path(config.output_dir)
        output_writer = OutputWriter(output_dir)
        failure_logger = FailureLogger(output_dir)
        
        # 处理视频列表
        stats = process_video_list(
            videos,
            config.language,
            llm,
            output_writer,
            failure_logger,
            incremental_manager,
            archive_path,
            force
        )
        
        # 输出汇总
        logger.info("=" * 60)
        logger.info("处理完成")
        logger.info("=" * 60)
        logger.info(f"总计: {stats['total']} 个视频")
        logger.info(f"成功: {stats['success']} 个")
        logger.info(f"失败: {stats['failed']} 个")
        logger.info("=" * 60)
        
        return 0 if stats['failed'] == 0 else 1
        
    except Exception as e:
        logger.error(f"执行完整流水线失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1


def _run_full_pipeline_for_urls(file_path: Path, logger, force: bool = False) -> int:
    """执行完整流水线（URL 列表模式）
    
    Args:
        file_path: URL 列表文件路径
        logger: Logger 实例
        force: 是否强制重跑
    
    Returns:
        退出码（0 表示成功）
    """
    logger.info("=" * 60)
    logger.info("开始执行完整流水线（URL 列表模式）")
    logger.info("=" * 60)
    
    try:
        from core.fetcher import VideoFetcher
        from core.pipeline import process_video_list
        from core.ai_providers import create_llm_client
        from core.output import OutputWriter
        from core.failure_logger import FailureLogger
        from core.incremental import IncrementalManager
        from config.manager import ConfigManager
        
        # 加载配置
        config_manager = ConfigManager()
        config = config_manager.load()
        
        # 获取视频列表
        logger.info(f"从文件读取 URL 列表: {file_path}")
        fetcher = VideoFetcher()
        all_videos = fetcher.fetch_from_file(file_path)
        
        if not all_videos:
            logger.warning("未能获取到任何视频，请检查 URL 列表文件内容")
            return 1
        
        total_videos = len(all_videos)
        logger.info(f"共获取到 {total_videos} 个视频")
        
        # 增量过滤（URL 列表模式使用批次 archive）
        incremental_manager = IncrementalManager()
        archive_path = incremental_manager.get_batch_archive_path()
        
        if not force:
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
            logger.info("强制重跑模式：将处理所有视频（忽略增量记录）")
        
        if not videos:
            logger.info("所有视频都已处理过，无需处理（使用 --force 可强制重跑）")
            return 0
        
        # 创建 LLM 客户端
        try:
            llm = create_llm_client(config.ai)
        except Exception as e:
            logger.error(f"创建 LLM 客户端失败: {e}")
            logger.warning("AI 翻译和摘要功能将不可用，但会继续处理其他步骤")
            llm = None
        
        # 创建输出写入器和失败记录器
        output_dir = Path(config.output_dir)
        output_writer = OutputWriter(output_dir)
        failure_logger = FailureLogger(output_dir)
        
        # 处理视频列表
        stats = process_video_list(
            videos,
            config.language,
            llm,
            output_writer,
            failure_logger,
            incremental_manager,
            archive_path,
            force
        )
        
        # 输出汇总
        logger.info("=" * 60)
        logger.info("处理完成")
        logger.info("=" * 60)
        logger.info(f"总计: {stats['total']} 个视频")
        logger.info(f"成功: {stats['success']} 个")
        logger.info(f"失败: {stats['failed']} 个")
        logger.info("=" * 60)
        
        return 0 if stats['failed'] == 0 else 1
        
    except Exception as e:
        logger.error(f"执行完整流水线失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1


def urls_command(args):
    """处理 URL 列表命令
    
    Args:
        args: argparse 解析的参数
    """
    logger = get_logger()
    
    if not args.file:
        logger.error("必须提供 URL 列表文件（使用 --file 参数）")
        return 1
    
    file_path = Path(args.file)
    if not file_path.exists():
        logger.error(f"文件不存在：{file_path}")
        return 1
    
    logger.info(f"URL 列表模式：文件 = {file_path}")
    
    # 实际调用 VideoFetcher 获取视频列表
    try:
        from core.fetcher import VideoFetcher
        
        fetcher = VideoFetcher()
        videos = fetcher.fetch_from_file(file_path)
        
        if not videos:
            logger.warning("未能获取到任何视频，请检查 URL 列表文件内容")
            return 1
        
        logger.info(f"成功获取 {len(videos)} 个视频")
        
        # 显示前几个视频的基本信息
        if videos:
            logger.info("前 5 个视频信息：")
            for i, video in enumerate(videos[:5], 1):
                title_preview = video.title[:50] + "..." if len(video.title) > 50 else video.title
                logger.info(f"  {i}. [{video.video_id}] {title_preview}")
            
            if len(videos) > 5:
                logger.info(f"  ... 还有 {len(videos) - 5} 个视频")
        
        # 执行完整流程
        if args.dry_run:
            logger.warning("URL 列表模式暂不支持 Dry Run，请使用 --run 执行完整流程")
            return 1
        
        if args.run:
            return _run_full_pipeline_for_urls(file_path, logger, force=args.force)
        
        logger.warning("请指定 --run 执行完整流程")
        return 1
        
    except Exception as e:
        logger.error(f"获取视频列表失败：{e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1


def main():
    """CLI 主入口"""
    # 加载配置
    config_manager = ConfigManager()
    config = config_manager.load()
    
    # 初始化日志系统（使用配置中的日志级别）
    logger = get_logger(
        level="INFO",  # 暂时固定为 INFO，后续可以从配置读取
        console_output=True,
        file_output=True,
    )
    
    # 创建主解析器
    parser = argparse.ArgumentParser(
        description="YouTube 字幕工具 v2 - 命令行接口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 频道模式 - Dry Run（仅检测）
  python cli.py channel --url https://www.youtube.com/@channel --dry-run
  
  # 频道模式 - 开始处理
  python cli.py channel --url https://www.youtube.com/@channel --run
  
  # URL 列表模式
  python cli.py urls --file urls.txt
        """
    )
    
    # 创建子命令解析器
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # channel 子命令
    channel_parser = subparsers.add_parser(
        "channel",
        help="频道模式：处理整个 YouTube 频道"
    )
    channel_parser.add_argument(
        "--url",
        type=str,
        help="频道 URL（例如：https://www.youtube.com/@channel 或 https://www.youtube.com/channel/UCxxxxxx）"
    )
    channel_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry Run 模式：仅检测字幕，不下载/不翻译/不摘要"
    )
    channel_parser.add_argument(
        "--run",
        action="store_true",
        help="开始处理：执行完整流水线（下载、翻译、摘要）"
    )
    channel_parser.add_argument(
        "--force",
        action="store_true",
        help="强制重跑：忽略历史记录，重新处理所有视频"
    )
    channel_parser.set_defaults(func=channel_command)
    
    # urls 子命令
    urls_parser = subparsers.add_parser(
        "urls",
        help="URL 列表模式：处理多个视频 URL"
    )
    urls_parser.add_argument(
        "--file",
        type=str,
        help="包含 URL 列表的文件路径（每行一个 URL）"
    )
    urls_parser.add_argument(
        "--run",
        action="store_true",
        help="开始处理：执行完整流水线（下载、翻译、摘要）"
    )
    urls_parser.add_argument(
        "--force",
        action="store_true",
        help="强制重跑：忽略历史记录，重新处理所有视频"
    )
    urls_parser.set_defaults(func=urls_command)
    
    # 解析参数
    args = parser.parse_args()
    
    # 如果没有提供命令，显示帮助
    if not args.command:
        parser.print_help()
        return 1
    
    # 执行对应命令
    try:
        return args.func(args)
    except Exception as e:
        logger.error(f"执行命令时出错：{e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
