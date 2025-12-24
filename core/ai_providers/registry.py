"""
AI 供应商注册表
支持动态注册新供应商
"""

from typing import Dict, Type, Optional

from core.llm_client import LLMClient


# 供应商注册表：provider 名称 -> 实现类
# 注意：这个字典会在 _init_registry() 中初始化，避免循环导入
_LLM_REGISTRY: Dict[str, Type[LLMClient]] = {}


def _init_registry() -> None:
    """初始化注册表（延迟导入避免循环依赖）"""
    global _LLM_REGISTRY

    if _LLM_REGISTRY:
        return  # 已经初始化过了

    # 延迟导入客户端类
    from .openai_compatible import OpenAICompatibleClient
    from .local_model import LocalModelClient
    from .gemini import GeminiClient
    from .anthropic import AnthropicClient
    from .google_translate import GoogleTranslateClient

    # 注册标准名称
    _LLM_REGISTRY.update(
        {
            "openai": OpenAICompatibleClient,
            "openai_compatible": OpenAICompatibleClient,
            "gemini": GeminiClient,
            "anthropic": AnthropicClient,
            "google_translate": GoogleTranslateClient,
            "google": GoogleTranslateClient,  # 别名
            # 本地模型（自动路由到专用客户端）
            "ollama": LocalModelClient,
            "lm_studio": LocalModelClient,
            "local": LocalModelClient,
            # OpenAI 兼容供应商（别名）
            "custom_openai": OpenAICompatibleClient,
            "gemini_openai": OpenAICompatibleClient,
            "deepseek": OpenAICompatibleClient,
            "kimi": OpenAICompatibleClient,
            "moonshot": OpenAICompatibleClient,
            "qwen": OpenAICompatibleClient,
            "glm": OpenAICompatibleClient,
            "groq": OpenAICompatibleClient,
            "xai": OpenAICompatibleClient,
            "doubao": OpenAICompatibleClient,  # 豆包/火山引擎
        }
    )


def register_provider(name: str, client_class: Type[LLMClient]) -> None:
    """注册新的供应商

    Args:
        name: 供应商名称（小写）
        client_class: 客户端实现类
    """
    _init_registry()
    _LLM_REGISTRY[name.lower()] = client_class


def get_provider(name: str) -> Optional[Type[LLMClient]]:
    """获取供应商实现类

    Args:
        name: 供应商名称

    Returns:
        实现类，如果不存在则返回 None
    """
    _init_registry()
    return _LLM_REGISTRY.get(name.lower())


def list_providers() -> list[str]:
    """列出所有已注册的供应商

    Returns:
        供应商名称列表
    """
    _init_registry()
    return list(_LLM_REGISTRY.keys())


def is_provider_registered(name: str) -> bool:
    """检查供应商是否已注册

    Args:
        name: 供应商名称

    Returns:
        如果已注册则返回 True
    """
    _init_registry()
    return name.lower() in _LLM_REGISTRY
