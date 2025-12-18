"""
CLI 工具函数
共用的辅助函数
"""

from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse, parse_qs

from core.models import VideoInfo
from ui.i18n_manager import t


def get_archive_path(
    url: str, videos: List[VideoInfo], incremental_manager, logger
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
                logger.info(t("cli_channel_mode_archive", filename=archive_path.name))
                return archive_path
            else:
                logger.warning(t("cli_unable_get_channel_id"))
                return None

        elif url_type == "playlist":
            # 播放列表模式：从 URL 提取播放列表 ID
            parsed = urlparse(url)
            playlist_id = parse_qs(parsed.query).get("list", [None])[0]
            if playlist_id:
                archive_path = incremental_manager.get_playlist_archive_path(
                    playlist_id
                )
                logger.info(t("cli_playlist_mode_archive", filename=archive_path.name))
                return archive_path
            else:
                logger.warning(t("cli_unable_extract_playlist_id"))
                return None

        elif url_type == "video":
            # 单视频模式：不使用增量
            return None

        else:
            # URL 列表模式：在 urls 命令中处理
            return None

    except Exception as e:
        logger.warning(t("cli_archive_path_error", error=str(e)))
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
        logger.info(t("cli_proxies_configured", count=len(config.proxies)))

    cookie_manager = None
    if config.cookie:
        cookie_manager = CookieManager(cookie_string=config.cookie)
        logger.info(t("cli_cookie_configured"))

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

    优先使用 AI Profile 配置，如果未配置则使用原有的 translation_ai / summary_ai 配置

    Args:
        config: 配置对象
        logger: Logger 实例

    Returns:
        tuple: (translation_llm, summary_llm)，如果创建失败则返回 (None, None)
    """
    from core.ai_providers import create_llm_client as _create_llm_client
    from core.ai_profile_manager import get_profile_manager

    translation_llm = None
    summary_llm = None

    # 获取 Profile 管理器
    profile_manager = get_profile_manager()

    # 获取翻译 AI 配置（优先使用 Profile）
    translation_ai_config = profile_manager.get_ai_config_for_task(
        "subtitle_translate",
        fallback_config=config.translation_ai
        if config.translation_ai.enabled
        else None,
    )

    # 创建翻译 LLM 客户端
    if translation_ai_config and translation_ai_config.enabled:
        try:
            translation_llm = _create_llm_client(translation_ai_config)
            profile_name = profile_manager.task_mapping.get(
                "subtitle_translate", t("profile_default_config")
            )
            logger.info(
                t(
                    "cli_translation_ai_created",
                    provider=translation_ai_config.provider,
                    model=translation_ai_config.model,
                    profile=profile_name,
                )
            )
        except Exception as e:
            logger.error(t("cli_translation_ai_create_failed", error=str(e)))
            logger.warning(t("cli_translation_ai_unavailable_warning"))
    else:
        logger.debug(t("cli_translation_ai_not_configured"))

    # 获取摘要 AI 配置（优先使用 Profile）
    summary_ai_config = profile_manager.get_ai_config_for_task(
        "subtitle_summarize",
        fallback_config=config.summary_ai if config.summary_ai.enabled else None,
    )

    # 创建摘要 LLM 客户端
    if summary_ai_config and summary_ai_config.enabled:
        try:
            summary_llm = _create_llm_client(summary_ai_config)
            profile_name = profile_manager.task_mapping.get(
                "subtitle_summarize", t("profile_default_config")
            )
            logger.info(
                t(
                    "cli_summary_ai_created",
                    provider=summary_ai_config.provider,
                    model=summary_ai_config.model,
                    profile=profile_name,
                )
            )
        except Exception as e:
            logger.error(t("cli_summary_ai_create_failed", error=str(e)))
            logger.warning(t("cli_summary_ai_unavailable_warning"))
    else:
        logger.debug(t("cli_summary_ai_not_configured"))

    return translation_llm, summary_llm


def print_summary(logger, stats: dict):
    """打印处理汇总"""
    logger.info("=" * 60)
    logger.info(t("cli_processing_complete"))
    logger.info("=" * 60)
    logger.info(t("cli_total_videos", count=stats["total"]))
    logger.info(t("cli_success_videos", count=stats["success"]))
    logger.info(t("cli_failed_videos", count=stats["failed"]))
    logger.info("=" * 60)
