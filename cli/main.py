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
from cli.ai_smoke_test import ai_smoke_test_command
from ui.i18n_manager import t


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器

    Returns:
        配置好的 ArgumentParser 实例
    """
    parser = argparse.ArgumentParser(
        description=t("cli_description"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=t("cli_epilog"),
    )

    # 创建子命令解析器
    subparsers = parser.add_subparsers(dest="command", help=t("cli_subparsers_help"))

    # channel 子命令
    _add_channel_parser(subparsers)

    # urls 子命令
    _add_urls_parser(subparsers)

    # test-cookie 子命令
    _add_test_cookie_parser(subparsers)

    # ai-smoke-test 子命令
    _add_ai_smoke_test_parser(subparsers)

    return parser


def _add_channel_parser(subparsers):
    """添加 channel 子命令解析器"""
    channel_parser = subparsers.add_parser(
        "channel", help=t("cli_channel_help")
    )
    channel_parser.add_argument(
        "--url", type=str, help=t("cli_channel_url_help")
    )
    channel_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=t("cli_dry_run_help"),
    )
    channel_parser.add_argument(
        "--run",
        action="store_true",
        help=t("cli_run_help"),
    )
    channel_parser.add_argument(
        "--force", action="store_true", help=t("cli_force_help")
    )
    channel_parser.set_defaults(func=channel_command)


def _add_urls_parser(subparsers):
    """添加 urls 子命令解析器"""
    urls_parser = subparsers.add_parser("urls", help=t("cli_urls_help"))
    urls_parser.add_argument(
        "--file", type=str, help=t("cli_urls_file_help")
    )
    urls_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=t("cli_dry_run_help"),
    )
    urls_parser.add_argument(
        "--run",
        action="store_true",
        help=t("cli_run_help"),
    )
    urls_parser.add_argument(
        "--force", action="store_true", help=t("cli_force_help")
    )
    urls_parser.set_defaults(func=urls_command)


def _add_test_cookie_parser(subparsers):
    """添加 test-cookie 子命令解析器"""
    test_cookie_parser = subparsers.add_parser(
        "test-cookie", help=t("cli_test_cookie_help")
    )
    test_cookie_parser.set_defaults(func=test_cookie_command)


def _add_ai_smoke_test_parser(subparsers):
    """添加 ai-smoke-test 子命令解析器"""
    ai_smoke_test_parser = subparsers.add_parser(
        "ai-smoke-test", help=t("cli_ai_smoke_test_help")
    )
    ai_smoke_test_parser.set_defaults(func=ai_smoke_test_command)


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
        from core.logger import translate_log
        logger.error(f"{translate_log('cli_execution_error')}: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
