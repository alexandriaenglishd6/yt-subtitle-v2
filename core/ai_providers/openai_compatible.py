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
from core.llm_client import LLMResult, LLMUsage, LLMException, LLMErrorType
from core.logger import get_logger, translate_exception
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
        self.provider_name = ai_config.provider

        # 加载 API Key（优先使用供应商专用 key，如果没有则尝试通用 key）
        self.api_key = None
        key_choices = [
            ai_config.provider,  # 优先使用供应商名称作为 key
            "openai",  # 回退到通用 openai key
            "openai_compatible",  # 回退到通用兼容 key
        ]

        api_key_config = ""
        for key in key_choices:
            config_val = ai_config.api_keys.get(key)
            if config_val:
                key_config = config_val
                loaded_key = load_api_key(key_config)
                if loaded_key:
                    self.api_key = loaded_key
                    api_key_config = key_config
                    break

        if not self.api_key:
            # 这里的 provider 应该是实际供应商名称
            raise LLMException(
                f"exception.ai_api_key_not_found:provider={self.provider_name},config={api_key_config}",
                LLMErrorType.AUTH,
            )

        # 检查依赖
        self._check_dependencies()

        # 初始化 4 个必需属性
        # 根据模型判断是否支持视觉（简化处理，可根据实际模型调整）
        model_lower = ai_config.model.lower()
        self._supports_vision = (
            "vision" in model_lower
            or "gpt-4o" in model_lower
            or "gpt-4-vision" in model_lower
        )

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
            import openai  # noqa: F401
        except ImportError:
            raise LLMException(
                translate_exception("exception.ai_dependency_missing", library="openai"),
                LLMErrorType.UNKNOWN,
            )

    def _is_local_base_url(self, base_url: Optional[str]) -> bool:
        """检测是否为本地服务 URL

        用于判断是否需要预热本地模型（如 Ollama）

        Args:
            base_url: API base URL

        Returns:
            是否为本地服务
        """
        if not base_url:
            return False

        # 本地地址模式
        local_patterns = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "[::1]",
        ]

        base_url_lower = base_url.lower()
        return any(pattern in base_url_lower for pattern in local_patterns)

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
        from openai import (
            APIConnectionError,
            APIError,
            AuthenticationError,
            RateLimitError,
        )

        start_time = time.time()

        try:
            # 确定 base_url
            base_url = self.ai_config.base_url or "https://api.openai.com/v1"

            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=base_url,
                timeout=self.ai_config.timeout_seconds,
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
                            max_tokens=min(
                                max_tokens or self.max_output_tokens,
                                self.max_output_tokens,
                            ),
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
                        translate_exception(
                            "log.ai_call_success_detail",
                            provider=self.provider_name.capitalize(),
                            model=self.ai_config.model,
                            elapsed=f"{elapsed:.2f}",
                            tokens=usage.total_tokens if usage else "N/A",
                        )
                    )

                    return LLMResult(
                        text=text,
                        usage=usage,
                        provider=self.provider_name,
                        model=self.ai_config.model,
                    )

                except RateLimitError as e:
                    last_error = LLMException(
                        translate_exception(
                            "exception.ai_rate_limit",
                            provider=self.provider_name.capitalize(),
                            error=str(e),
                        ),
                        LLMErrorType.RATE_LIMIT,
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2**attempt  # 指数退避
                        logger.warning_i18n(
                            "log.ai_retry_rate_limit", wait_time=wait_time
                        )
                        time.sleep(wait_time)
                        continue
                    raise last_error

                except AuthenticationError as e:
                    raise LLMException(
                        translate_exception(
                            "exception.ai_auth_failed_prefix",
                            provider=self.provider_name.capitalize(),
                            error=str(e),
                        ),
                        LLMErrorType.AUTH,
                    )

                except APIConnectionError as e:
                    last_error = LLMException(
                        translate_exception(
                            "exception.ai_network_failed_prefix",
                            provider=self.provider_name.capitalize(),
                            error=str(e),
                        ),
                        LLMErrorType.NETWORK,
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2**attempt
                        logger.warning_i18n(
                            "log.ai_retry_connection_failed", wait_time=wait_time
                        )
                        time.sleep(wait_time)
                        continue
                    raise last_error

                except APIError as e:
                    # 检查是否是内容过滤错误
                    error_msg = str(e).lower()
                    if any(
                        keyword in error_msg
                        for keyword in ["content", "safety", "policy", "violation"]
                    ):
                        raise LLMException(
                            translate_exception(
                                "exception.ai_content_filter",
                                provider=self.provider_name.capitalize(),
                                error=str(e),
                            ),
                            LLMErrorType.CONTENT,
                        )
                    last_error = LLMException(
                        translate_exception(
                            "exception.ai_error_prefix",
                            provider=self.provider_name.capitalize(),
                            error=str(e),
                        ),
                        LLMErrorType.UNKNOWN,
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2**attempt
                        logger.warning_i18n(
                            "log.ai_retry_api_error", wait_time=wait_time
                        )
                        time.sleep(wait_time)
                        continue
                    raise last_error

                except Exception as e:
                    raise LLMException(
                        translate_exception(
                            "exception.ai_unknown_error_prefix",
                            provider=self.provider_name.capitalize(),
                            error=str(e),
                        ),
                        LLMErrorType.UNKNOWN,
                    )

            # 如果所有重试都失败
            if last_error:
                raise last_error

        except LLMException:
            raise
        except Exception as e:
            raise LLMException(
                translate_exception(
                    "exception.ai_client_init_failed_prefix",
                    provider=self.provider_name.capitalize(),
                    error=str(e),
                ),
                LLMErrorType.UNKNOWN,
            )
