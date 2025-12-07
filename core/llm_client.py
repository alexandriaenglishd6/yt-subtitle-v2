"""
LLM 客户端抽象接口
符合 ai_design.md 规范的统一 AI 调用层
"""
import os
from typing import Protocol, Optional, Sequence
from dataclasses import dataclass
from enum import Enum


class LLMErrorType(str, Enum):
    """LLM 错误类型枚举"""
    NETWORK = "network"  # 超时 / 连接失败 / DNS 等
    AUTH = "auth"  # API key 无效、权限不足等
    RATE_LIMIT = "rate_limit"  # 频率限制、配额耗尽等
    CONTENT = "content"  # 内容安全过滤、提示违规等
    UNKNOWN = "unknown"  # 未归类的其他错误


class LLMException(Exception):
    """LLM 统一异常类型
    
    所有供应商的异常都应该映射为这个类型
    """
    def __init__(self, msg: str, error_type: LLMErrorType):
        super().__init__(msg)
        self.error_type = error_type


@dataclass
class LLMUsage:
    """LLM 使用统计信息"""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None


@dataclass
class LLMResult:
    """LLM 调用结果"""
    text: str
    usage: Optional[LLMUsage] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class LLMClient(Protocol):
    """LLM 客户端抽象接口
    
    所有 AI 提供商都必须实现这个接口
    """
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResult:
        """生成文本结果
        
        Args:
            prompt: 用户提示词
            system: 系统提示词（可选）
            max_tokens: 最大 token 数（可选）
            temperature: 温度参数（可选）
            stop: 停止序列（可选）
        
        Returns:
            LLMResult 对象，包含生成的文本和使用统计
        
        Raises:
            LLMException: 当调用失败时抛出，包含错误类型
        """
        ...


def load_api_key(config_value: str) -> Optional[str]:
    """从配置值加载 API Key
    
    支持格式：
    - "env:OPENAI_API_KEY" - 从环境变量读取
    - 直接字符串 - 作为 API Key 使用（不推荐，仅用于测试）
    
    Args:
        config_value: 配置值，如 "env:OPENAI_API_KEY" 或直接是 API Key
    
    Returns:
        API Key 字符串，如果无法加载则返回 None
    """
    if not config_value:
        return None
    
    # 支持 "env:XXX" 格式
    if config_value.startswith("env:"):
        env_name = config_value[4:]  # 去掉 "env:" 前缀
        return os.getenv(env_name)
    
    # 直接作为 API Key（不推荐，但允许用于测试）
    return config_value
