"""
AI 提供商实现
符合 ai_design.md 规范的 LLMClient 实现
"""
import time
from typing import Optional, Sequence
from config.manager import AIConfig
from core.llm_client import (
    LLMClient, LLMResult, LLMUsage, LLMException, LLMErrorType
)
from core.logger import get_logger
from core.llm_client import load_api_key

logger = get_logger()


class OpenAIClient:
    """OpenAI LLM 客户端实现"""
    
    def __init__(self, ai_config: AIConfig):
        """初始化 OpenAI 客户端
        
        Args:
            ai_config: AI 配置
        """
        self.ai_config = ai_config
        self.provider_name = "openai"
        
        # 加载 API Key
        api_key_config = ai_config.api_keys.get("openai", "")
        self.api_key = load_api_key(api_key_config)
        
        if not self.api_key:
            raise LLMException(
                f"未找到 OpenAI API Key（配置: {api_key_config}）",
                LLMErrorType.AUTH
            )
        
        # 检查依赖
        self._check_dependencies()
    
    def _check_dependencies(self) -> None:
        """检查依赖库是否已安装"""
        try:
            import openai
        except ImportError:
            raise LLMException(
                "未安装 openai 库，请运行: pip install openai",
                LLMErrorType.UNKNOWN
            )
    
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResult:
        """调用 OpenAI API"""
        import openai
        from openai import OpenAIError, APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        start_time = time.time()
        
        try:
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.ai_config.base_url,
                timeout=self.ai_config.timeout_seconds
            )
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            # 实现重试逻辑
            last_error = None
            for attempt in range(self.ai_config.max_retries + 1):
                try:
                    response = client.chat.completions.create(
                        model=self.ai_config.model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature or 0.3,
                        stop=stop,
                    )
                    
                    # 提取结果
                    text = response.choices[0].message.content or ""
                    
                    # 提取使用统计
                    usage = None
                    if response.usage:
                        usage = LLMUsage(
                            prompt_tokens=response.usage.prompt_tokens,
                            completion_tokens=response.usage.completion_tokens,
                            total_tokens=response.usage.total_tokens,
                        )
                    
                    elapsed = time.time() - start_time
                    logger.debug(
                        f"OpenAI API 调用成功: model={self.ai_config.model}, "
                        f"耗时={elapsed:.2f}s, tokens={usage.total_tokens if usage else 'N/A'}"
                    )
                    
                    return LLMResult(
                        text=text,
                        usage=usage,
                        provider=self.provider_name,
                        model=self.ai_config.model
                    )
                    
                except RateLimitError as e:
                    last_error = LLMException(
                        f"OpenAI API 频率限制: {e}",
                        LLMErrorType.RATE_LIMIT
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2 ** attempt  # 指数退避
                        logger.warning(f"遇到频率限制，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    raise last_error
                    
                except AuthenticationError as e:
                    raise LLMException(
                        f"OpenAI API 认证失败: {e}",
                        LLMErrorType.AUTH
                    )
                    
                except APIConnectionError as e:
                    last_error = LLMException(
                        f"OpenAI API 连接失败: {e}",
                        LLMErrorType.NETWORK
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2 ** attempt
                        logger.warning(f"连接失败，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    raise last_error
                    
                except APIError as e:
                    # 检查是否是内容过滤错误
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ["content", "safety", "policy", "violation"]):
                        raise LLMException(
                            f"OpenAI API 内容过滤: {e}",
                            LLMErrorType.CONTENT
                        )
                    last_error = LLMException(
                        f"OpenAI API 错误: {e}",
                        LLMErrorType.UNKNOWN
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2 ** attempt
                        logger.warning(f"API 错误，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    raise last_error
                    
                except Exception as e:
                    raise LLMException(
                        f"OpenAI API 未知错误: {e}",
                        LLMErrorType.UNKNOWN
                    )
            
            # 如果所有重试都失败
            if last_error:
                raise last_error
                
        except LLMException:
            raise
        except Exception as e:
            raise LLMException(
                f"OpenAI 客户端初始化失败: {e}",
                LLMErrorType.UNKNOWN
            )


class AnthropicClient:
    """Anthropic LLM 客户端实现"""
    
    def __init__(self, ai_config: AIConfig):
        """初始化 Anthropic 客户端
        
        Args:
            ai_config: AI 配置
        """
        self.ai_config = ai_config
        self.provider_name = "anthropic"
        
        # 加载 API Key
        api_key_config = ai_config.api_keys.get("anthropic", "")
        self.api_key = load_api_key(api_key_config)
        
        if not self.api_key:
            raise LLMException(
                f"未找到 Anthropic API Key（配置: {api_key_config}）",
                LLMErrorType.AUTH
            )
        
        # 检查依赖
        self._check_dependencies()
    
    def _check_dependencies(self) -> None:
        """检查依赖库是否已安装"""
        try:
            import anthropic
        except ImportError:
            raise LLMException(
                "未安装 anthropic 库，请运行: pip install anthropic",
                LLMErrorType.UNKNOWN
            )
    
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResult:
        """调用 Anthropic API"""
        import anthropic
        from anthropic import AnthropicError, APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        start_time = time.time()
        
        try:
            client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.ai_config.base_url,
                timeout=self.ai_config.timeout_seconds
            )
            
            # 实现重试逻辑
            last_error = None
            for attempt in range(self.ai_config.max_retries + 1):
                try:
                    response = client.messages.create(
                        model=self.ai_config.model,
                        max_tokens=max_tokens or 4096,
                        system=system,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature or 0.3,
                    )
                    
                    # 提取结果
                    text = response.content[0].text if response.content else ""
                    
                    # 提取使用统计
                    usage = None
                    if response.usage:
                        usage = LLMUsage(
                            prompt_tokens=response.usage.input_tokens,
                            completion_tokens=response.usage.output_tokens,
                            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                        )
                    
                    elapsed = time.time() - start_time
                    logger.debug(
                        f"Anthropic API 调用成功: model={self.ai_config.model}, "
                        f"耗时={elapsed:.2f}s, tokens={usage.total_tokens if usage else 'N/A'}"
                    )
                    
                    return LLMResult(
                        text=text,
                        usage=usage,
                        provider=self.provider_name,
                        model=self.ai_config.model
                    )
                    
                except RateLimitError as e:
                    last_error = LLMException(
                        f"Anthropic API 频率限制: {e}",
                        LLMErrorType.RATE_LIMIT
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2 ** attempt
                        logger.warning(f"遇到频率限制，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    raise last_error
                    
                except AuthenticationError as e:
                    raise LLMException(
                        f"Anthropic API 认证失败: {e}",
                        LLMErrorType.AUTH
                    )
                    
                except APIConnectionError as e:
                    last_error = LLMException(
                        f"Anthropic API 连接失败: {e}",
                        LLMErrorType.NETWORK
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2 ** attempt
                        logger.warning(f"连接失败，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    raise last_error
                    
                except APIError as e:
                    # 检查是否是内容过滤错误
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ["content", "safety", "policy", "violation"]):
                        raise LLMException(
                            f"Anthropic API 内容过滤: {e}",
                            LLMErrorType.CONTENT
                        )
                    last_error = LLMException(
                        f"Anthropic API 错误: {e}",
                        LLMErrorType.UNKNOWN
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2 ** attempt
                        logger.warning(f"API 错误，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                        continue
                    raise last_error
                    
                except Exception as e:
                    raise LLMException(
                        f"Anthropic API 未知错误: {e}",
                        LLMErrorType.UNKNOWN
                    )
            
            # 如果所有重试都失败
            if last_error:
                raise last_error
                
        except LLMException:
            raise
        except Exception as e:
            raise LLMException(
                f"Anthropic 客户端初始化失败: {e}",
                LLMErrorType.UNKNOWN
            )


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
    provider = ai_config.provider.lower()
    
    if provider == "openai":
        return OpenAIClient(ai_config)
    elif provider == "anthropic":
        return AnthropicClient(ai_config)
    else:
        raise LLMException(
            f"不支持的 AI 提供商: {provider}。支持的提供商: openai, anthropic",
            LLMErrorType.UNKNOWN
        )
