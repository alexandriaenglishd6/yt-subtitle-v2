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
        configs.append({
            "name": f"翻译 AI (Profile: {translation_profile.name})",
            "config": translation_profile.ai_config,
            "source": "profile",
            "task": "subtitle_translate"
        })
    elif app_config.translation_ai.enabled:
        configs.append({
            "name": "翻译 AI (默认配置)",
            "config": app_config.translation_ai,
            "source": "default",
            "task": "subtitle_translate"
        })
    else:
        configs.append({
            "name": "翻译 AI",
            "config": None,
            "source": "disabled",
            "task": "subtitle_translate"
        })
    
    # 收集摘要 AI 配置
    summary_profile = profile_manager.get_profile_for_task("subtitle_summarize")
    if summary_profile and summary_profile.enabled:
        configs.append({
            "name": f"摘要 AI (Profile: {summary_profile.name})",
            "config": summary_profile.ai_config,
            "source": "profile",
            "task": "subtitle_summarize"
        })
    elif app_config.summary_ai.enabled:
        configs.append({
            "name": "摘要 AI (默认配置)",
            "config": app_config.summary_ai,
            "source": "default",
            "task": "subtitle_summarize"
        })
    else:
        configs.append({
            "name": "摘要 AI",
            "config": None,
            "source": "disabled",
            "task": "subtitle_summarize"
        })
    
    # 收集所有 Profile 中的配置（如果未在任务映射中使用）
    all_profiles = profile_manager.list_profiles()
    task_mappings = profile_manager.list_task_mappings()
    used_profiles = set(task_mappings.values())
    
    for profile_name, profile in all_profiles.items():
        if profile_name not in used_profiles and profile.enabled:
            configs.append({
                "name": f"Profile: {profile_name}",
                "config": profile.ai_config,
                "source": "profile_unused",
                "task": None
            })
    
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
            model="N/A"
        )
    
    if not config.enabled:
        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.DISABLED,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url
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
            error=f"客户端创建失败: {e}",
            response_time=None
        )
    except Exception as e:
        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.UNHEALTHY,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            error=f"未知错误: {e}",
            response_time=None
        )
    
    # 尝试发送测试请求
    try:
        start_time = time.time()
        result = client.generate(
            prompt="Hi",  # 极简提示
            max_tokens=5,  # 最小输出
            temperature=0.0  # 最低温度
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
            test_response=result.text[:50] if result.text else None
        )
    except LLMException as e:
        error_type = e.error_type
        error_msg = str(e)
        
        # 根据错误类型提供更详细的错误信息
        if error_type == LLMErrorType.AUTH:
            error_msg = f"认证失败: {error_msg}（请检查 API Key）"
        elif error_type == LLMErrorType.RATE_LIMIT:
            error_msg = f"频率限制: {error_msg}"
        elif error_type == LLMErrorType.NETWORK:
            error_msg = f"网络错误: {error_msg}（请检查网络连接和代理设置）"
        elif error_type == LLMErrorType.TIMEOUT:
            error_msg = f"超时: {error_msg}（请检查服务是否可用）"
        
        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.UNHEALTHY,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            error=error_msg,
            response_time=None
        )
    except Exception as e:
        return AIHealthReport(
            name=name,
            config=config,
            status=HealthStatus.UNHEALTHY,
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            error=f"测试请求失败: {e}",
            response_time=None
        )


def format_health_report(reports: List[AIHealthReport]) -> str:
    """格式化健康报告
    
    Args:
        reports: 健康报告列表
    
    Returns:
        格式化的报告字符串
    """
    lines = []
    lines.append("=" * 80)
    lines.append("AI 供应商健康报告")
    lines.append("=" * 80)
    lines.append("")
    
    # 统计
    total = len(reports)
    healthy = sum(1 for r in reports if r.status == HealthStatus.HEALTHY)
    unhealthy = sum(1 for r in reports if r.status == HealthStatus.UNHEALTHY)
    disabled = sum(1 for r in reports if r.status == HealthStatus.DISABLED)
    not_configured = sum(1 for r in reports if r.status == HealthStatus.NOT_CONFIGURED)
    
    lines.append(f"总计: {total} 个配置")
    lines.append(f"  ✅ 健康: {healthy}")
    lines.append(f"  ❌ 不健康: {unhealthy}")
    lines.append(f"  ⚠️  已禁用: {disabled}")
    lines.append(f"  ⚪ 未配置: {not_configured}")
    lines.append("")
    lines.append("-" * 80)
    lines.append("")
    
    # 详细报告
    for report in reports:
        lines.append(f"【{report.name}】")
        lines.append(f"  提供商: {report.provider}")
        lines.append(f"  模型: {report.model}")
        if report.base_url:
            lines.append(f"  Base URL: {report.base_url}")
        
        if report.status == HealthStatus.HEALTHY:
            lines.append(f"  状态: ✅ 健康")
            if report.response_time:
                lines.append(f"  响应时间: {report.response_time:.2f} 秒")
            if report.test_response:
                lines.append(f"  测试响应: {report.test_response}")
        elif report.status == HealthStatus.UNHEALTHY:
            lines.append(f"  状态: ❌ 不健康")
            if report.error:
                lines.append(f"  错误: {report.error}")
        elif report.status == HealthStatus.DISABLED:
            lines.append(f"  状态: ⚠️  已禁用")
        elif report.status == HealthStatus.NOT_CONFIGURED:
            lines.append(f"  状态: ⚪ 未配置")
        
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
    
    try:
        logger.info("开始 AI 供应商健康自检...")
        
        # 加载配置
        config_manager = ConfigManager()
        
        # 收集所有 AI 配置
        ai_configs = collect_ai_configs(config_manager)
        
        if not ai_configs:
            logger.warning("未找到任何 AI 配置")
            return 0
        
        logger.info(f"找到 {len(ai_configs)} 个 AI 配置，开始测试...")
        
        # 测试每个配置
        reports = []
        for ai_config_info in ai_configs:
            name = ai_config_info["name"]
            config = ai_config_info["config"]
            
            logger.info(f"测试: {name}...")
            report = test_ai_config(name, config)
            reports.append(report)
            
            # 显示简要结果
            if report.status == HealthStatus.HEALTHY:
                logger.info(f"  ✅ {name}: 健康 (响应时间: {report.response_time:.2f}s)")
            elif report.status == HealthStatus.UNHEALTHY:
                logger.error(f"  ❌ {name}: 不健康 - {report.error}")
            elif report.status == HealthStatus.DISABLED:
                logger.warning(f"  ⚠️  {name}: 已禁用")
            elif report.status == HealthStatus.NOT_CONFIGURED:
                logger.info(f"  ⚪ {name}: 未配置")
        
        # 生成并输出报告
        report_text = format_health_report(reports)
        # 只通过 print 输出到控制台，避免日志重复
        print("\n" + report_text)
        
        # 判断退出码
        has_unhealthy = any(r.status == HealthStatus.UNHEALTHY for r in reports)
        if has_unhealthy:
            logger.warning("检测到不健康的配置，请检查 API Key、网络连接和代理设置")
            return 1
        else:
            logger.info("所有配置健康检查通过")
            return 0
        
    except Exception as e:
        logger.error(f"执行健康检查时出错：{e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1

