"""
CLI 主入口
参数解析和命令分发
"""
import argparse
import sys

from config.manager import ConfigManager
from core.logger import get_logger

from cli.channel import channel_command
from cli.urls import urls_command
from cli.cookie import test_cookie_command


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器
    
    Returns:
        配置好的 ArgumentParser 实例
    """
    parser = argparse.ArgumentParser(
        description="YouTube 字幕工具 v2 - 命令行接口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 频道模式 - Dry Run（仅检测）
  python cli.py channel --url https://www.youtube.com/@channel --dry-run
  
  # 频道模式 - 开始处理
  python cli.py channel --url https://www.youtube.com/@channel --run
  
  # URL 列表模式 - Dry Run
  python cli.py urls --file urls.txt --dry-run
  
  # URL 列表模式 - 开始处理
  python cli.py urls --file urls.txt --run
  
  # 测试 Cookie
  python cli.py test-cookie
        """
    )
    
    # 创建子命令解析器
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # channel 子命令
    _add_channel_parser(subparsers)
    
    # urls 子命令
    _add_urls_parser(subparsers)
    
    # test-cookie 子命令
    _add_test_cookie_parser(subparsers)
    
    return parser


def _add_channel_parser(subparsers):
    """添加 channel 子命令解析器"""
    channel_parser = subparsers.add_parser(
        "channel",
        help="频道模式：处理整个 YouTube 频道"
    )
    channel_parser.add_argument(
        "--url",
        type=str,
        help="频道 URL（例如：https://www.youtube.com/@channel）"
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


def _add_urls_parser(subparsers):
    """添加 urls 子命令解析器"""
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
        "--dry-run",
        action="store_true",
        help="Dry Run 模式：仅检测字幕，不下载/不翻译/不摘要"
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


def _add_test_cookie_parser(subparsers):
    """添加 test-cookie 子命令解析器"""
    test_cookie_parser = subparsers.add_parser(
        "test-cookie",
        help="测试 Cookie：检查 Cookie 是否可用、所在地区"
    )
    test_cookie_parser.set_defaults(func=test_cookie_command)


def main() -> int:
    """CLI 主入口
    
    Returns:
        退出码（0 表示成功）
    """
    # 加载配置
    config_manager = ConfigManager()
    config_manager.load()
    
    # 初始化日志系统
    logger = get_logger(
        level="INFO",
        console_output=True,
        file_output=True,
    )
    
    # 创建解析器并解析参数
    parser = create_parser()
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

