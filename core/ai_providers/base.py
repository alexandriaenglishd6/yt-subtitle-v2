"""
AI 供应商基类和能力配置
"""

from typing import Dict
from dataclasses import dataclass


@dataclass
class ProviderCapabilities:
    """供应商能力配置"""

    supports_vision: bool = False  # 是否支持图片输入
    supports_streaming: bool = True  # 是否支持流式输出
    supports_tools: bool = False  # 是否支持工具调用
    supports_json_mode: bool = False  # 是否支持 JSON 模式
    default_timeout: int = 60  # 默认超时时间（秒）
    max_tokens: int = 4096  # 默认最大输出 token
    context_window: int = 8000  # 上下文窗口大小


# 各供应商能力配置
PROVIDER_CAPABILITIES: Dict[str, ProviderCapabilities] = {
    "openai": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=60,
        max_tokens=4096,
        context_window=128000,
    ),
    "gemini": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=60,
        max_tokens=8192,
        context_window=1000000,
    ),
    "anthropic": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=False,
        default_timeout=60,
        max_tokens=8192,
        context_window=200000,
    ),
    "deepseek": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=120,  # 长文本摘要需要更长时间
        max_tokens=4096,
        context_window=64000,
    ),
    "kimi": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=120,  # Kimi 处理长文本需要更长时间
        max_tokens=4096,
        context_window=128000,
    ),
    "qwen": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=120,  # 长文本摘要需要更长时间
        max_tokens=4096,
        context_window=32000,
    ),
    "glm": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=120,  # 长文本摘要需要更长时间
        max_tokens=4096,
        context_window=128000,
    ),
    "groq": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=30,  # Groq 响应快
        max_tokens=4096,
        context_window=32000,
    ),
    "ollama": ProviderCapabilities(
        supports_vision=False,  # 取决于具体模型
        supports_streaming=True,
        supports_tools=False,  # 大部分本地模型不支持
        supports_json_mode=False,
        default_timeout=300,  # 本地模型需要更长时间
        max_tokens=4096,
        context_window=8000,
    ),
    "lm_studio": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=False,
        supports_json_mode=False,
        default_timeout=300,
        max_tokens=4096,
        context_window=8000,
    ),
    "local": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=False,
        supports_json_mode=False,
        default_timeout=300,
        max_tokens=4096,
        context_window=8000,
    ),
    "google_translate": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=False,
        supports_tools=False,
        supports_json_mode=False,
        default_timeout=60,
        max_tokens=50000,  # Google 翻译单次可翻译约 5000 字符
        context_window=50000,
    ),
}


def get_capabilities(provider: str) -> ProviderCapabilities:
    """获取供应商能力配置

    Args:
        provider: 供应商名称

    Returns:
        能力配置，如果未知则返回保守的默认配置
    """
    return PROVIDER_CAPABILITIES.get(
        provider.lower(),
        ProviderCapabilities(),  # 默认保守配置
    )
