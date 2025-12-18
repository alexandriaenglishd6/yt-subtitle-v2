"""
Google Gemini 原生客户端实现
"""

import threading
import time
from typing import Optional, Sequence

from config.manager import AIConfig
from core.llm_client import LLMResult, LLMException, LLMErrorType
from core.logger import get_logger, translate_exception
from core.llm_client import load_api_key

logger = get_logger()


class GeminiClient:
    """Google Gemini 客户端实现"""

    def __init__(self, ai_config: AIConfig):
        """初始化 Gemini 客户端

        Args:
            ai_config: AI 配置
        """
        self.ai_config = ai_config
        self.provider_name = "gemini"

        # 加载 API Key
        self.api_key = None
        key_choices = ["gemini", "google"]
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
        self._supports_vision = True  # Gemini 支持视觉
        self._max_input_tokens = 128000  # Gemini 2.0 Flash 支持 1M tokens，保守估计
        self._max_output_tokens = 8192  # Gemini 支持较大输出
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
            import google.generativeai as genai  # noqa: F401
        except ImportError:
            raise LLMException(
                translate_exception("exception.ai_dependency_missing", library="google-generativeai"),
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
        """调用 Gemini API"""
        import google.generativeai as genai

        start_time = time.time()

        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.ai_config.model)

            # 组合 system 和 prompt
            full_prompt = prompt
            if system:
                full_prompt = f"{system}\n\n{prompt}"

            # 实现重试逻辑
            last_error = None
            for attempt in range(self.ai_config.max_retries + 1):
                try:
                    # 使用 Semaphore 进行并发限流
                    with self._sem:
                        response = model.generate_content(
                            full_prompt,
                            generation_config={
                                "max_output_tokens": min(
                                    max_tokens or self.max_output_tokens,
                                    self.max_output_tokens,
                                ),
                                "temperature": temperature or 0.3,
                                "stop_sequences": stop if stop else None,
                            },
                        )

                    # 提取结果
                    text = response.text if hasattr(response, "text") else ""

                    # Gemini API 不直接提供 token 使用统计，设为 None
                    usage = None

                    elapsed = time.time() - start_time
                    logger.debug(
                        translate_exception(
                            "log.ai_call_success_detail",
                            provider="Gemini",
                            model=self.ai_config.model,
                            elapsed=f"{elapsed:.2f}",
                            tokens="N/A",
                        )
                    )

                    return LLMResult(
                        text=text,
                        usage=usage,
                        provider=self.provider_name,
                        model=self.ai_config.model,
                    )

                except Exception as e:
                    error_msg = str(e).lower()

                    # 判断错误类型
                    if "rate limit" in error_msg or "quota" in error_msg:
                        last_error = LLMException(
                            translate_exception("exception.ai_rate_limit", provider="Gemini", error=str(e)),
                            LLMErrorType.RATE_LIMIT,
                        )
                    elif (
                        "auth" in error_msg
                        or "api key" in error_msg
                        or "permission" in error_msg
                    ):
                        raise LLMException(
                            translate_exception("exception.ai_auth_failed_prefix", provider="Gemini", error=str(e)),
                            LLMErrorType.AUTH,
                        )
                    elif (
                        "network" in error_msg
                        or "connection" in error_msg
                        or "timeout" in error_msg
                    ):
                        last_error = LLMException(
                            translate_exception("exception.ai_network_failed_prefix", provider="Gemini", error=str(e)),
                            LLMErrorType.NETWORK,
                        )
                    elif (
                        "safety" in error_msg
                        or "content" in error_msg
                        or "blocked" in error_msg
                    ):
                        raise LLMException(
                            translate_exception("exception.ai_content_filter", provider="Gemini", error=str(e)),
                            LLMErrorType.CONTENT,
                        )
                    else:
                        last_error = LLMException(
                            translate_exception("exception.ai_error_prefix", provider="Gemini", error=str(e)),
                            LLMErrorType.UNKNOWN,
                        )

                    if (
                        attempt < self.ai_config.max_retries
                        and last_error.error_type
                        in (LLMErrorType.RATE_LIMIT, LLMErrorType.NETWORK)
                    ):
                        wait_time = 2**attempt
                        logger.warning_i18n("log.ai_retry_error", wait_time=wait_time)
                        time.sleep(wait_time)
                        continue
                    raise last_error

            # 如果所有重试都失败
            if last_error:
                raise last_error

        except LLMException:
            raise
        except Exception as e:
            raise LLMException(
                translate_exception("exception.ai_client_init_failed_prefix", provider="Gemini", error=str(e)),
                LLMErrorType.UNKNOWN,
            )
