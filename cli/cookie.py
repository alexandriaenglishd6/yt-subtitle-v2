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
    
    try:
        from config.manager import ConfigManager
        from core.cookie_manager import CookieManager
        
        config_manager = ConfigManager()
        config = config_manager.load()
        
        if not config.cookie:
            logger.warning("未配置 Cookie，请先在配置文件中添加 Cookie")
            return 1
        
        logger.info("开始测试 Cookie...")
        cookie_manager = CookieManager(cookie_string=config.cookie)
        result = cookie_manager.test_cookie()
        
        if result["available"]:
            logger.info("Cookie 测试成功：Cookie 可用")
            if result.get("region"):
                logger.info(f"检测到地区：{result['region']}")
            return 0
        else:
            error_msg = result.get("error", "未知错误")
            logger.error(f"Cookie 测试失败：{error_msg}")
            return 1
        
    except Exception as e:
        logger.error(f"测试 Cookie 时出错：{e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1

