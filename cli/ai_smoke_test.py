"""
AI 供应商健康自检命令
遍历当前配置中启用的所有 LLMClient，分别发起一个极小请求，
以验证 API Key / 代理 / 网络是否可用，并输出"健康报告"。
"""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from core.logger import get_logger
from ui.i18n_manager import t
from config.manager import ConfigManager, AIConfig
from core.ai_providers import create_llm_client
from core.ai_profile_manager import get_profile_manager
from core.llm_client import LLMException, LLMErrorType


class HealthStatus(Enum):
    """健康状态"""

    HEALTHY = "healthy"  # 健康
    UNHEALTHY = "unhealthy"  # 不健康
    DISABLED = "disabled"  # 已禁用
    NOT_CONFIGURED = "not_configured"  # 未配置


@dataclass
class AIHealthReport:
    """AI 健康报告项"""

    name: str  # 配置名称（如 "翻译 AI"、"摘要 AI" 或 Profile 名称）
    config: AIConfig  # AI 配置
    status: HealthStatus  # 健康状态
    provider: str  # 提供商
    model: str  # 模型名称
    base_url: Optional[str] = None  # Base URL（如果是本地模型）
    error: Optional[str] = None  # 错误信息
    response_time: Optional[float] = None  # 响应时间（秒）
    test_response: Optional[str] = None  # 测试响应内容（前50字符）


def collect_ai_configs(config: ConfigManager) -> List[Dict[str, Any]]:
    """收集所有启用的 AI 配置

    Args:
        config: 配置管理器

    Returns:
        AI 配置列表，每个元素包含 name, config, source 等信息
    """
    configs = []
    app_config = config.load()
    profile_manager = get_profile_manager()
    profile_manager.load()

    # 收集翻译 AI 配置
    translation_profile = profile_manager.get_profile_for_task("subtitle_translate")
    if translation_profile and translation_profile.enabled:
        configs.append(
            {
                "name": t(
                    "cli_ai_translation_profile", profile=translation_profile.name
                ),
                "config": translation_profile.ai_config,
                "source": "profile",
                "task": "subtitle_translate",
            }
        )
    elif app_config.translation_ai.enabled:
        configs.append(
            {
                "name": t("cli_ai_translation_default"),
                "config": app_config.translation_ai,
                "source": "default",
                "task": "subtitle_translate",
            }
        )
    else:
        configs.append(
            {
                "name": t("cli_ai_translation"),
                "config": None,
                "source": "disabled",
                "task": "subtitle_translate",
            }
        )

    # 收集摘要 AI 配置
    summary_profile = profile_manager.get_profile_for_task("subtitle_summarize")
    if summary_profile and summary_profile.enabled:
        configs.append(
            {
                "name": t("cli_ai_summary_profile", profile=summary_profile.name),
                "config": summary_profile.ai_config,
                "source": "profile",
                "task": "subtitle_summarize",
            }
        )
    elif app_config.summary_ai.enabled:
        configs.append(
            {
                "name": t("cli_ai_summary_default"),
                "config": app_config.summary_ai,
                "source": "default",
                "task": "subtitle_summarize",
            }
        )
    else:
        configs.append(
            {
                "name": t("cli_ai_summary"),
                "config": None,
                "source": "disabled",
                "task": "subtitle_summarize",
            }
        )

    # 收集所有 Profile 中的配置（如果未在任务映射中使用）
    all_profiles = profile_manager.list_profiles()
    task_mappings = profile_manager.list_task_mappings()
    used_profiles = set(task_mappings.values())

    for profile_name, profile in all_profiles.items():
        if profile_name not in used_profiles and profile.enabled:
            configs.append(
                {
                    "name": f"Profile: {profile_name}",
                    "config": profile.ai_config,
                    "source": "profile_unused",
                    "task": None,
                }
            )

    return configs


def test_ai_config(name: str, config: Optional[AIConfig]) -> AIHealthReport:
    """测试单个 AI 配置

    Args:
        name: 配置名称
        config: AI 配置（如果为 None 表示未配置或已禁用）

    Returns:
        健康报告
    """
    if config is None:
        return AIHealthReport(
            name=name,
            config=None,
            status=HealthStatus.NOT_CONFIGURED,
            provider="N/A",
            model="N/A",
        )

    if not config.enabled:
        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.DISABLED,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
        )

    # 尝试创建客户端
    try:
        client = create_llm_client(config)
    except LLMException as e:
        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.UNHEALTHY,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            error=f"{t('exception.ai_client_init_failed')}: {e}",
            response_time=None,
        )
    except Exception as e:
        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.UNHEALTHY,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            error=f"{t('exception_generic_error')}: {e}",
            response_time=None,
        )

    # 尝试发送测试请求
    try:
        start_time = time.time()
        result = client.generate(
            prompt="Hi",  # 极简提示
            max_tokens=5,  # 最小输出
            temperature=0.0,  # 最低温度
        )
        response_time = time.time() - start_time

        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.HEALTHY,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            error=None,
            response_time=response_time,
            test_response=result.text[:50] if result.text else None,
        )
    except LLMException as e:
        error_type = e.error_type
        error_msg = str(e)

        # 根据错误类型提供更详细的错误信息
        if error_type == LLMErrorType.AUTH:
            error_msg = f"{t('exception.api_auth_failed')}: {error_msg}"
        elif error_type == LLMErrorType.RATE_LIMIT:
            error_msg = f"{t('error_type_rate_limit')}: {error_msg}"
        elif error_type == LLMErrorType.NETWORK:
            error_msg = f"{t('error_type_network')}: {error_msg}"
        elif error_type == LLMErrorType.TIMEOUT:
            error_msg = f"{t('error_type_timeout')}: {error_msg}"

        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.UNHEALTHY,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            error=error_msg,
            response_time=None,
        )
    except Exception as e:
        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.UNHEALTHY,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            error=f"{t('exception.ai_request_failed')}: {e}",
            response_time=None,
        )


def format_health_report(reports: List[AIHealthReport], t) -> str:
    """格式化健康报告

    Args:
        reports: 健康报告列表
        t: 翻译函数

    Returns:
        格式化的报告字符串
    """
    lines = []
    lines.append("=" * 80)
    lines.append(t("ai_smoke_test_report_title"))
    lines.append("=" * 80)
    lines.append("")

    # 统计
    total = len(reports)
    healthy = sum(1 for r in reports if r.status == HealthStatus.HEALTHY)
    unhealthy = sum(1 for r in reports if r.status == HealthStatus.UNHEALTHY)
    disabled = sum(1 for r in reports if r.status == HealthStatus.DISABLED)
    not_configured = sum(1 for r in reports if r.status == HealthStatus.NOT_CONFIGURED)

    lines.append(f"{t('ai_smoke_test_total')}: {total}")
    lines.append(f"  ✅ {t('ai_smoke_test_healthy')}: {healthy}")
    lines.append(f"  ❌ {t('ai_smoke_test_unhealthy')}: {unhealthy}")
    lines.append(f"  ⚠️  {t('ai_smoke_test_disabled')}: {disabled}")
    lines.append(f"  ⚪ {t('ai_smoke_test_not_configured')}: {not_configured}")
    lines.append("")
    lines.append("-" * 80)
    lines.append("")

    # 详细报告
    for report in reports:
        lines.append(f"【{report.name}】")
        lines.append(f"  {t('ai_provider_label')}: {report.provider}")
        lines.append(f"  {t('ai_model_label')}: {report.model}")
        if report.base_url:
            lines.append(f"  Base URL: {report.base_url}")

        if report.status == HealthStatus.HEALTHY:
            lines.append(f"  {t('ai_status_label')}: ✅ {t('ai_smoke_test_healthy')}")
            if report.response_time:
                lines.append(f"  {t('ai_smoke_test_response_time')}: {report.response_time:.2f} s")
            if report.test_response:
                lines.append(f"  {t('ai_smoke_test_response')}: {report.test_response}")
        elif report.status == HealthStatus.UNHEALTHY:
            lines.append(f"  {t('ai_status_label')}: ❌ {t('ai_smoke_test_unhealthy')}")
            if report.error:
                lines.append(f"  {t('exception_label')}: {report.error}")
        elif report.status == HealthStatus.DISABLED:
            lines.append(f"  {t('ai_status_label')}: ⚠️  {t('ai_smoke_test_disabled')}")
        elif report.status == HealthStatus.NOT_CONFIGURED:
            lines.append(f"  {t('ai_status_label')}: ⚪ {t('ai_smoke_test_not_configured')}")

        lines.append("")

    lines.append("=" * 80)

    return "\n".join(lines)


def ai_smoke_test_command(args) -> int:
    """AI 健康自检命令

    Args:
        args: argparse 解析的参数

    Returns:
        退出码（0 表示所有配置健康，1 表示有配置不健康）
    """
    logger = get_logger()
    from ui.i18n_manager import t

    try:
        logger.info(t("ai_testing"))

        # 加载配置
        config_manager = ConfigManager()

        # 收集所有 AI 配置
        ai_configs = collect_ai_configs(config_manager)

        if not ai_configs:
            logger.warning(t("ai_config_label") + t("no_subtitle"))
            return 0

        logger.info(t("log.total_videos_fetched", count=len(ai_configs)) + t("ai_config_label"))

        # 测试每个配置
        reports = []
        for ai_config_info in ai_configs:
            name = ai_config_info["name"]
            config = ai_config_info["config"]

            logger.info(f"{t('ai_testing')}: {name}...")
            report = test_ai_config(name, config)
            reports.append(report)

            # 显示简要结果
            if report.status == HealthStatus.HEALTHY:
                logger.info(
                    f"  ✅ {name}: {t('status_idle')} ({t('log.task_eta_seconds', seconds=report.response_time)})"
                )
            elif report.status == HealthStatus.UNHEALTHY:
                logger.error(f"  ❌ {name}: {t('status_failed')} - {report.error}")
            elif report.status == HealthStatus.DISABLED:
                logger.warning(f"  ⚠️  {name}: {t('status_paused')}")
            elif report.status == HealthStatus.NOT_CONFIGURED:
                logger.info(f"  ⚪ {name}: {t('cookie_status_not_configured')}")

        # 生成并输出报告
        report_text = format_health_report(reports, t)
        # 只通过 print 输出到控制台，避免日志重复
        print("\n" + report_text)

        # 判断退出码
        has_unhealthy = any(r.status == HealthStatus.UNHEALTHY for r in reports)
        if has_unhealthy:
            logger.warning(t("ai_test_failed", error=""))
            return 1
        else:
            logger.info(t("ai_test_success", provider="All", model="All"))
            return 0

    except Exception as e:
        logger.error(f"{t('log.ai_test_failed', error=str(e))}")
        import traceback

        logger.debug(traceback.format_exc())
        return 1
