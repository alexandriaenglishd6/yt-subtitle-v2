"""
AI 供应商配置模块

从 translation_summary_page.py 提取，集中管理所有 AI 供应商的默认配置。
包含供应商默认 URL、模型列表、预填示例等。
"""

from typing import Dict, Any, List


# AI 供应商默认配置和可用模型列表
AI_PROVIDER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "model": "gpt-5.2",
        "base_url": "https://api.openai.com/v1",  # 官方 API 地址
        "models": [
            "gpt-5.2",
            "gpt-5.2-instant",
            "gpt-5.2-thinking",
            "gpt-5.2-pro",
            "gpt-5.1",
            "gpt-5",
            "gpt-5-mini",
            "gpt-5-nano",
            "gpt-4o-mini",
        ],
    },
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "gemini": {
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com",
        "models": [
            "gemini-3-pro-preview",
            "gemini-2.5-pro",
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
    },
    "anthropic": {
        "model": "claude-sonnet-4-5-20250929",
        "base_url": "https://api.anthropic.com",  # 官方 API 地址
        "models": [
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-5-20251101",
            "claude-opus-4-1-20250805",
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-20241022",
        ],
    },
    "siliconflow": {
        "model": "deepseek-ai/DeepSeek-V3",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-V2.5",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
            "Qwen/Qwen2.5-72B-Instruct",
            "THUDM/glm-4-9b-chat",
        ],
    },
    "openrouter": {
        "model": "google/gemini-flash-1.5",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "google/gemini-flash-1.5",
            "anthropic/claude-3.5-sonnet",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.1-70b-instruct",
        ],
    },
    "groq": {
        "model": "llama-3.1-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
    },
    "kimi": {
        "model": "kimi-k2-turbo-preview",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["kimi-k2-0905-preview", "kimi-k2-thinking", "kimi-k2-turbo-preview"],
    },
    "qwen": {
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "qwen3-max",
            "qwen-plus",
            "qwen-flash",
            "qwen-turbo",
            "qwq-plus",
            "qwen-long",
            "qwen-deep-research",
            "qwen2.5-14b",
        ],
    },
    "doubao": {
        "model": "Doubao-Seed-1.6",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": [
            "Doubao-Seed-1.6",
            "Doubao-Seed-1.6-flash",
            "Doubao-Seed-1.6-lite",
            "Doubao-Seed-Character",
            "Doubao-Seed-Translation",
        ],
    },
    "glm": {
        "model": "GLM-4.6",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "models": [
            "GLM-4.6",
            "GLM-4.6V-Flash",
            "GLM-4.5",
            "GLM-4.5-X",
            "GLM-4.5-Air",
            "GLM-4.5-AirX",
            "GLM-4.5-Flash",
            "GLM-4-Air-250414",
            "GLM-4-Long",
            "GLM-4-FlashX-250414",
        ],
    },
    "xai": {
        "model": "grok-4",
        "base_url": "https://api.x.ai/v1",
        "models": [
            "grok-4-1-fast-reasoning",
            "grok-4-1-fast-non-reasoning",
            "grok-4-fast-reasoning",
            "grok-4-fast-non-reasoning",
            "grok-4",
        ],
    },
    "ollama": {
        "model": "qwen2.5",
        "base_url": "http://localhost:11434/v1",
        "models": ["qwen2.5", "llama3.1", "mistral", "gemma2"],
    },
    "lm_studio": {
        "model": "local-model",
        "base_url": "http://localhost:1234/v1",
        "models": ["local-model"],
    },
    "google_translate": {
        "model": "google_translate_free",
        "base_url": "",  # Google 翻译免费版不需要 API 地址
        "models": ["google_translate_free"],
        "requires_api_key": False,  # 标记不需要 API Key
    },
    "openai_compatible": {
        "model": "gpt-5.2",
        "base_url": "http://your-api-base-url/v1",
        "models": [
            "gpt-5.2",
            "gpt-5.1",
            "gpt-5",
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-sonnet",
        ],
    },
    "custom_openai": {
        "model": "gpt-5.2",
        "base_url": "http://your-api-base-url/v1",
        "models": [
            "gpt-5.2",
            "gpt-5.1",
            "gpt-5",
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-sonnet",
        ],
    },
    "gemini_openai": {
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": ["gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro"],
    },
}


# 供应商预填示例（用于快速配置）
AI_PREFILL_EXAMPLES: Dict[str, Dict[str, str]] = {
    "gemini_openai": {
        "name": "Gemini (OpenAI Compatible)",
        "provider": "gemini_openai",
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "tip": "ai_tip_gemini_openai",
    },
    "custom_openai": {
        "name": "Custom OpenAI Compatible",
        "provider": "custom_openai",
        "model": "gpt-5.2",
        "base_url": "https://your-proxy-api.com/v1",
        "tip": "ai_tip_openai_compatible",
    },
    "lm_studio": {
        "name": "LM Studio (Local)",
        "provider": "lm_studio",
        "model": "local-model",
        "base_url": "http://localhost:1234/v1",
        "tip": "ai_tip_lm_studio",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "provider": "ollama",
        "model": "qwen2.5",
        "base_url": "http://localhost:11434/v1",
        "tip": "ai_tip_ollama",
    },
}


def get_provider_config(provider: str) -> Dict[str, Any]:
    """获取指定供应商的配置
    
    Args:
        provider: 供应商名称
        
    Returns:
        供应商配置字典，如果不存在则返回 openai 的配置
    """
    return AI_PROVIDER_CONFIGS.get(provider, AI_PROVIDER_CONFIGS["openai"])


def get_provider_names() -> List[str]:
    """获取所有可用的供应商名称列表"""
    return list(AI_PROVIDER_CONFIGS.keys())


def get_provider_models(provider: str) -> List[str]:
    """获取指定供应商的可用模型列表
    
    Args:
        provider: 供应商名称
        
    Returns:
        模型名称列表
    """
    config = get_provider_config(provider)
    return config.get("models", [])


def get_default_model(provider: str) -> str:
    """获取指定供应商的默认模型
    
    Args:
        provider: 供应商名称
        
    Returns:
        默认模型名称
    """
    config = get_provider_config(provider)
    return config.get("model", "")


def get_default_base_url(provider: str) -> str:
    """获取指定供应商的默认 Base URL
    
    Args:
        provider: 供应商名称
        
    Returns:
        Base URL 字符串
    """
    config = get_provider_config(provider)
    return config.get("base_url", "")


# 便于导入的别名
__all__ = [
    "AI_PROVIDER_CONFIGS",
    "AI_PREFILL_EXAMPLES",
    "get_provider_config",
    "get_provider_names",
    "get_provider_models",
    "get_default_model",
    "get_default_base_url",
]
