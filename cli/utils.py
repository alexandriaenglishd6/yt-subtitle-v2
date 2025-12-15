"""
CLI 工具函数
共用的辅助函数
"""
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse, parse_qs

from core.models import VideoInfo


def get_archive_path(
    url: str,
    videos: List[VideoInfo],
    incremental_manager,
    logger
) -> Optional[Path]:
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
            parsed = urlparse(url)
            playlist_id = parse_qs(parsed.query).get("list", [None])[0]
            if playlist_id:
                archive_path = incremental_manager.get_playlist_archive_path(playlist_id)
                logger.info(f"播放列表模式：使用 archive 文件 {archive_path.name}")
                return archive_path
            else:
                logger.warning("无法提取播放列表 ID，将不使用增量过滤")
                return None
        
        elif url_type == "video":
            # 单视频模式：不使用增量
            return None
        
        else:
            # URL 列表模式：在 urls 命令中处理
            return None
            
    except Exception as e:
        logger.warning(f"确定 archive 路径时出错: {e}")
        return None


def create_managers(config, logger):
    """创建代理管理器和 Cookie 管理器
    
    Args:
        config: 配置对象
        logger: Logger 实例
    
    Returns:
        tuple: (proxy_manager, cookie_manager)
    """
    from core.proxy_manager import ProxyManager
    from core.cookie_manager import CookieManager
    
    proxy_manager = None
    if config.proxies:
        proxy_manager = ProxyManager(proxies=config.proxies)
        logger.info(f"已配置 {len(config.proxies)} 个代理")
    
    cookie_manager = None
    if config.cookie:
        cookie_manager = CookieManager(cookie_string=config.cookie)
        logger.info("已配置 Cookie")
    
    return proxy_manager, cookie_manager


def create_llm_client(config, logger):
    """创建 LLM 客户端（向后兼容函数）
    
    注意：此函数已废弃，请使用 create_llm_clients
    
    Args:
        config: 配置对象
        logger: Logger 实例
    
    Returns:
        LLM 客户端实例（翻译客户端），如果创建失败则返回 None
    """
    translation_llm, _ = create_llm_clients(config, logger)
    return translation_llm


def create_llm_clients(config, logger):
    """创建翻译和摘要 LLM 客户端
    
    Args:
        config: 配置对象
        logger: Logger 实例
    
    Returns:
        tuple: (translation_llm, summary_llm)，如果创建失败则返回 (None, None)
    """
    from core.ai_providers import create_llm_client as _create_llm_client
    
    translation_llm = None
    summary_llm = None
    
    # 创建翻译 LLM 客户端
    try:
        translation_llm = _create_llm_client(config.translation_ai)
        logger.info(f"翻译 AI 客户端已创建: {config.translation_ai.provider}/{config.translation_ai.model}")
    except Exception as e:
        logger.error(f"创建翻译 LLM 客户端失败: {e}")
        logger.warning("AI 翻译功能将不可用，但会继续处理其他步骤")
    
    # 创建摘要 LLM 客户端
    try:
        summary_llm = _create_llm_client(config.summary_ai)
        logger.info(f"摘要 AI 客户端已创建: {config.summary_ai.provider}/{config.summary_ai.model}")
    except Exception as e:
        logger.error(f"创建摘要 LLM 客户端失败: {e}")
        logger.warning("AI 摘要功能将不可用，但会继续处理其他步骤")
    
    return translation_llm, summary_llm


def print_summary(logger, stats: dict):
    """打印处理汇总
    
    Args:
        logger: Logger 实例
        stats: 统计信息字典
    """
    logger.info("=" * 60)
    logger.info("处理完成")
    logger.info("=" * 60)
    logger.info(f"总计: {stats['total']} 个视频")
    logger.info(f"成功: {stats['success']} 个")
    logger.info(f"失败: {stats['failed']} 个")
    logger.info("=" * 60)

