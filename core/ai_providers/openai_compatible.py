"""
OpenAI 兼容客户端实现

支持所有 OpenAI Chat Completions 兼容服务：
- OpenAI 官方
- DeepSeek
- Kimi/Moonshot
- 通义千问 Qwen
- 智谱 GLM
- Groq
"""
import threading
import time
from typing import Optional, Sequence

from config.manager import AIConfig
from core.llm_client import (
    LLMClient, LLMResult, LLMUsage, LLMException, LLMErrorType
)
from core.logger import get_logger
from core.llm_client import load_api_key

logger = get_logger()


class OpenAICompatibleClient:
    """OpenAI 兼容客户端实现"""
    
    def __init__(self, ai_config: AIConfig):
        """初始化 OpenAI 兼容客户端
        
        Args:
            ai_config: AI 配置
        """
        self.ai_config = ai_config
        self.provider_name = "openai"
        
        # 加载 API Key（优先使用 openai，如果没有则尝试其他 key）
        api_key_config = ai_config.api_keys.get("openai") or ai_config.api_keys.get("openai_compatible") or ""
        self.api_key = load_api_key(api_key_config)
        
        if not self.api_key:
            raise LLMException(
                f"未找到 OpenAI API Key（配置: {api_key_config}）",
                LLMErrorType.AUTH
            )
        
        # 检查依赖
        self._check_dependencies()
        
        # 初始化 4 个必需属性
        # 根据模型判断是否支持视觉（简化处理，可根据实际模型调整）
        model_lower = ai_config.model.lower()
        self._supports_vision = "vision" in model_lower or "gpt-4o" in model_lower or "gpt-4-vision" in model_lower
        
        # Token 限制（保守估计，可根据实际模型调整）
        self._max_input_tokens = 128000  # 默认值，可通过配置覆盖
        self._max_output_tokens = 4096  # 默认值，可通过配置覆盖
        self._max_concurrency = ai_config.max_concurrency
        
        # 创建 Semaphore 用于并发限流
        self._sem = threading.Semaphore(self._max_concurrency)
    
    @property
    def supports_vision(self) -> bool:
        return self._supports_vision
    
    @property
    def max_input_tokens(self) -> int:
        return self._max_input_tokens
    
    @property
    def max_output_tokens(self) -> int:
        return self._max_output_tokens
    
    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency
    
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
        """调用 OpenAI 兼容 API"""
        import openai
        from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
        start_time = time.time()
        
        try:
            # 确定 base_url
            base_url = self.ai_config.base_url or "https://api.openai.com/v1"
            
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=base_url,
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
                    # 使用 Semaphore 进行并发限流
                    with self._sem:
                        response = client.chat.completions.create(
                            model=self.ai_config.model,
                            messages=messages,
                            max_tokens=min(max_tokens or self.max_output_tokens, self.max_output_tokens),
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
                        f"OpenAICompatible API 调用成功: model={self.ai_config.model}, "
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
                        f"OpenAI 兼容 API 频率限制: {e}",
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
                        f"OpenAI 兼容 API 认证失败: {e}",
                        LLMErrorType.AUTH
                    )
                    
                except APIConnectionError as e:
                    last_error = LLMException(
                        f"OpenAI 兼容 API 连接失败: {e}",
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
                            f"OpenAI 兼容 API 内容过滤: {e}",
                            LLMErrorType.CONTENT
                        )
                    last_error = LLMException(
                        f"OpenAI 兼容 API 错误: {e}",
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
                        f"OpenAI 兼容 API 未知错误: {e}",
                        LLMErrorType.UNKNOWN
                    )
            
            # 如果所有重试都失败
            if last_error:
                raise last_error
                
        except LLMException:
            raise
        except Exception as e:
            raise LLMException(
                f"OpenAICompatible 客户端初始化失败: {e}",
                LLMErrorType.UNKNOWN
            )

