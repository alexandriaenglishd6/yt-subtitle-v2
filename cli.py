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
        logger.info("Dry Run 模式：仅检测字幕，不下载/不摘要")
        logger.warning("功能尚未实现，将在后续任务中完成")
        return 0
    
    if args.run:
        logger.info("开始处理模式：执行完整流水线")
        logger.warning("功能尚未实现，将在后续任务中完成")
        return 0
    
    # 如果没有指定 --dry-run 或 --run，默认提示
    logger.warning("请指定 --dry-run（仅检测）或 --run（开始处理）")
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
    logger.warning("功能尚未实现，将在后续任务中完成")
    
    # 读取文件内容（暂时只显示行数）
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        logger.info(f"文件包含 {len(lines)} 个 URL")
    except Exception as e:
        logger.error(f"读取文件失败：{e}")
        return 1
    
    return 0


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
