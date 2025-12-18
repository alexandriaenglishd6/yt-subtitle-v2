"""
Cookie 测试命令
检查 Cookie 是否可用及所在地区
"""

from core.logger import get_logger


def test_cookie_command(args):
    """测试 Cookie 命令

    Args:
        args: argparse 解析的参数

    Returns:
        退出码（0 表示成功）
    """
    logger = get_logger()
    from ui.i18n_manager import t

    try:
        from config.manager import ConfigManager
        from core.cookie_manager import CookieManager

        config_manager = ConfigManager()
        config = config_manager.load()

        if not config.cookie:
            logger.warning(t("no_cookie"))
            return 1

        logger.info(t("cookie_test_start"))
        cookie_manager = CookieManager(cookie_string=config.cookie)
        result = cookie_manager.test_cookie()

        if result["available"]:
            logger.info(t("cookie_test_success"))
            if result.get("region"):
                logger.info(t("log.cookie_region_detected", region=result["region"]))
            return 0
        else:
            error_msg = result.get("error", t("status_error"))
            logger.error(f"{t('cookie_test_failed')}: {error_msg}")
            return 1

    except Exception as e:
        logger.error(f"{t('log.cookie_test_error', error=str(e))}")
        import traceback

        logger.debug(traceback.format_exc())
        return 1
