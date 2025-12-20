"""
Anthropic Claude 客户端实现
"""

import threading
import time
from typing import Optional, Sequence

from config.manager import AIConfig
from core.llm_client import LLMResult, LLMUsage, LLMException, LLMErrorType
from core.logger import get_logger, translate_exception
from core.llm_client import load_api_key

logger = get_logger()


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
        self.api_key = None
        key_choices = ["anthropic", "claude"]
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
            # 使用翻译键格式，日志系统会自动翻译
            raise LLMException(
                f"exception.ai_api_key_not_found:provider={self.provider_name.capitalize()},config={api_key_config}",
                LLMErrorType.AUTH,
            )

        # 检查依赖
        self._check_dependencies()

        # 初始化 4 个必需属性
        # Claude 3.5 Sonnet 和 Opus 支持视觉
        model_lower = ai_config.model.lower()
        self._supports_vision = (
            "opus" in model_lower or "sonnet" in model_lower or "haiku" in model_lower
        )

        # Token 限制（根据 Claude 模型能力）
        self._max_input_tokens = 200000  # Claude 3.5 支持 200K tokens
        self._max_output_tokens = 8192  # Claude 支持较大输出
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
            import anthropic  # noqa: F401
        except ImportError:
            raise LLMException(
                translate_exception("exception.ai_dependency_missing", library="anthropic"),
                LLMErrorType.UNKNOWN,
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
        from anthropic import (
            APIConnectionError,
            APIError,
            AuthenticationError,
            RateLimitError,
        )

        start_time = time.time()

        try:
            client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.ai_config.base_url,
                timeout=self.ai_config.timeout_seconds,
            )

            # 实现重试逻辑
            last_error = None
            for attempt in range(self.ai_config.max_retries + 1):
                try:
                    # 使用 Semaphore 进行并发限流
                    with self._sem:
                        response = client.messages.create(
                            model=self.ai_config.model,
                            max_tokens=min(
                                max_tokens or self.max_output_tokens,
                                self.max_output_tokens,
                            ),
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
                            total_tokens=response.usage.input_tokens
                            + response.usage.output_tokens,
                        )

                    elapsed = time.time() - start_time
                    logger.debug(
                        translate_exception(
                            "log.ai_call_success_detail",
                            provider="Anthropic",
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
                        translate_exception("exception.ai_rate_limit", provider="Anthropic", error=str(e)),
                        LLMErrorType.RATE_LIMIT,
                    )
                    if attempt < self.ai_config.max_retries:
                        wait_time = 2**attempt
                        logger.warning_i18n(
                            "log.ai_retry_rate_limit", wait_time=wait_time
                        )
                        time.sleep(wait_time)
                        continue
                    raise last_error

                except AuthenticationError as e:
                    raise LLMException(
                        translate_exception("exception.ai_auth_failed_prefix", provider="Anthropic", error=str(e)),
                        LLMErrorType.AUTH,
                    )

                except APIConnectionError as e:
                    last_error = LLMException(
                        translate_exception("exception.ai_network_failed_prefix", provider="Anthropic", error=str(e)),
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
                            translate_exception("exception.ai_content_filter", provider="Anthropic", error=str(e)),
                            LLMErrorType.CONTENT,
                        )
                    last_error = LLMException(
                        translate_exception("exception.ai_error_prefix", provider="Anthropic", error=str(e)),
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
                        translate_exception("exception.ai_unknown_error_prefix", provider="Anthropic", error=str(e)),
                        LLMErrorType.UNKNOWN,
                    )

            # 如果所有重试都失败
            if last_error:
                raise last_error

        except LLMException:
            raise
        except Exception as e:
            raise LLMException(
                translate_exception("exception.ai_client_init_failed_prefix", provider="Anthropic", error=str(e)),
                LLMErrorType.UNKNOWN,
            )
