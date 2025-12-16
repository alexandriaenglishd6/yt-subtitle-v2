"""
AI 供应商工厂函数
根据配置创建对应的客户端实例
"""
from config.manager import AIConfig
from core.llm_client import LLMClient, LLMException, LLMErrorType

from .registry import get_provider, _init_registry


def create_llm_client(ai_config: AIConfig) -> LLMClient:
    """创建 LLM 客户端实例（工厂函数）
    
    根据 AIConfig 中的 provider 创建对应的客户端实例
    
    Args:
        ai_config: AI 配置
    
    Returns:
        LLMClient 实例
    
    Raises:
        LLMException: 如果 provider 不支持或初始化失败
    """
    _init_registry()
    
    provider = ai_config.provider.lower()
    
    # 从注册表获取实现类
    client_class = get_provider(provider)
    
    if client_class is None:
        from .registry import list_providers
        available = list_providers()
        raise LLMException(
            f"不支持的 AI 提供商: {provider}。支持的提供商: {', '.join(available)}",
            LLMErrorType.UNKNOWN
        )
    
    # 创建实例
    try:
        return client_class(ai_config)
    except Exception as e:
        raise LLMException(
            f"初始化 {provider} 客户端失败: {e}",
            LLMErrorType.UNKNOWN
        )

