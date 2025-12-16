"""
AI 供应商模块

提供统一的 LLM 客户端接口，支持多种 AI 供应商。

使用示例：
    from core.ai_providers import create_llm_client
    
    client = create_llm_client(config)
    result = client.generate("Hello")
"""

# 从 core.llm_client 导入基类接口（向后兼容）
from core.llm_client import (
    LLMClient, LLMResult, LLMUsage, LLMException, LLMErrorType
)

# 从 base 导入能力配置
from .base import (
    ProviderCapabilities,
    PROVIDER_CAPABILITIES,
    get_capabilities,
)

# 从 factory 导入工厂函数（向后兼容）
from .factory import create_llm_client

# 从 registry 导入注册相关函数
from .registry import (
    register_provider,
    get_provider,
    list_providers,
    is_provider_registered,
)

# 导入客户端类（向后兼容）
from .openai_compatible import OpenAICompatibleClient
from .local_model import LocalModelClient
from .gemini import GeminiClient
from .anthropic import AnthropicClient

# GoogleTranslateClient 需要延迟导入（因为文件很大，可能有循环依赖）
def _lazy_import_google_translate():
    """延迟导入 GoogleTranslateClient"""
    from .google_translate import GoogleTranslateClient
    return GoogleTranslateClient

# 使用 __getattr__ 实现延迟导入
def __getattr__(name):
    if name == "GoogleTranslateClient":
        return _lazy_import_google_translate()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # 基类接口（从 core.llm_client 导出，向后兼容）
    "LLMClient",
    "LLMResult",
    "LLMUsage",
    "LLMException",
    "LLMErrorType",
    # 能力配置
    "ProviderCapabilities",
    "PROVIDER_CAPABILITIES",
    "get_capabilities",
    # 工厂和注册
    "create_llm_client",
    "register_provider",
    "get_provider",
    "list_providers",
    "is_provider_registered",
    # 客户端类（向后兼容）
    "OpenAICompatibleClient",
    "LocalModelClient",
    "GeminiClient",
    "AnthropicClient",
    "GoogleTranslateClient",
]

__version__ = "3.1.0"

