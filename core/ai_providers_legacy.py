"""
AI 提供商实现
符合 AI_PROVIDER_EXTENSION.md v2.1 规范的 LLMClient 实现
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
    """OpenAI 兼容客户端实现
    
    支持所有 OpenAI Chat Completions 兼容服务：
    - OpenAI 官方
    - DeepSeek
    - Kimi/Moonshot
    - 通义千问 Qwen
    - 智谱 GLM
    - 本地 Ollama / vLLM 等
    """
    
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
        
        # 检测是否是本地模型，如果是则进行预热
        self._is_local_model = self._is_local_base_url(ai_config.base_url)
        if self._is_local_model:
            self._warmup_in_background()
    
    def _is_local_base_url(self, base_url: Optional[str]) -> bool:
        """检测是否是本地模型（通过 base_url 判断）
        
        Args:
            base_url: API 基础 URL
        
        Returns:
            如果是本地模型则返回 True
        """
        if not base_url:
            return False
        
        base_url_lower = base_url.lower()
        # 检测常见的本地地址模式
        local_indicators = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",  # IPv6 localhost
        ]
        
        return any(indicator in base_url_lower for indicator in local_indicators)
    
    def _warmup_in_background(self) -> None:
        """在后台线程中执行预热（不阻塞初始化）
        
        预热会发送一个轻量级的请求来"唤醒"本地模型，避免首次调用时的冷启动延迟。
        预热失败不会影响客户端的使用，只会在日志中记录警告。
        """
        def warmup_thread():
            try:
                logger.info(f"检测到本地模型 ({self.ai_config.base_url})，开始预热...")
                self._warmup()
                logger.info(f"本地模型预热完成: {self.ai_config.model}")
            except Exception as e:
                # 预热失败不应该影响客户端使用，只记录警告
                logger.warning(f"本地模型预热失败（不影响使用）: {e}")
        
        # 在后台线程中执行预热
        thread = threading.Thread(target=warmup_thread, daemon=True, name="LLM-Warmup")
        thread.start()
    
    def _warmup(self) -> None:
        """执行预热：发送一个轻量级的请求
        
        使用 Semaphore 确保预热请求也受到并发控制。
        预热请求使用最小的 token 数量，只发送一个简单的提示。
        """
        import openai
        from openai import APIConnectionError, APIError
        
        try:
            # 确定 base_url
            base_url = self.ai_config.base_url or "https://api.openai.com/v1"
            
            client = openai.OpenAI(
                api_key=self.api_key,
                base_url=base_url,
                timeout=min(self.ai_config.timeout_seconds, 30)  # 预热使用较短的超时时间
            )
            
            # 使用 Semaphore 进行并发限流（预热也受并发控制）
            with self._sem:
                # 发送一个极轻量的请求（只包含一个单词）
                response = client.chat.completions.create(
                    model=self.ai_config.model,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=5,  # 最小输出 token
                    temperature=0.0,  # 最低温度，减少计算
                )
                
                # 验证响应
                if response.choices and response.choices[0].message.content:
                    logger.debug(f"预热请求成功: {response.choices[0].message.content[:20]}")
                else:
                    logger.debug("预热请求完成（无内容返回）")
                    
        except APIConnectionError as e:
            # 连接错误可能是本地服务未启动，这是可以接受的
            logger.debug(f"预热连接失败（可能服务未启动）: {e}")
            raise
        except APIError as e:
            # API 错误可能是配置问题，记录但不影响使用
            logger.debug(f"预热 API 错误: {e}")
            raise
        except Exception as e:
            # 其他错误也记录但不影响使用
            logger.debug(f"预热过程中出现错误: {e}")
            raise
    
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
        api_key_config = ai_config.api_keys.get("gemini", "")
        self.api_key = load_api_key(api_key_config)
        
        if not self.api_key:
            raise LLMException(
                f"未找到 Gemini API Key（配置: {api_key_config}）",
                LLMErrorType.AUTH
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
            import google.generativeai as genai
        except ImportError:
            raise LLMException(
                "未安装 google-generativeai 库，请运行: pip install google-generativeai",
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
                                "max_output_tokens": min(max_tokens or self.max_output_tokens, self.max_output_tokens),
                                "temperature": temperature or 0.3,
                                "stop_sequences": stop if stop else None,
                            }
                        )
                    
                    # 提取结果
                    text = response.text if hasattr(response, 'text') else ""
                    
                    # Gemini API 不直接提供 token 使用统计，设为 None
                    usage = None
                    
                    elapsed = time.time() - start_time
                    logger.debug(
                        f"Gemini API 调用成功: model={self.ai_config.model}, "
                        f"耗时={elapsed:.2f}s"
                    )
                    
                    return LLMResult(
                        text=text,
                        usage=usage,
                        provider=self.provider_name,
                        model=self.ai_config.model
                    )
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    # 判断错误类型
                    if "rate limit" in error_msg or "quota" in error_msg:
                        last_error = LLMException(
                            f"Gemini API 频率限制: {e}",
                            LLMErrorType.RATE_LIMIT
                        )
                    elif "auth" in error_msg or "api key" in error_msg or "permission" in error_msg:
                        raise LLMException(
                            f"Gemini API 认证失败: {e}",
                            LLMErrorType.AUTH
                        )
                    elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                        last_error = LLMException(
                            f"Gemini API 连接失败: {e}",
                            LLMErrorType.NETWORK
                        )
                    elif "safety" in error_msg or "content" in error_msg or "blocked" in error_msg:
                        raise LLMException(
                            f"Gemini API 内容过滤: {e}",
                            LLMErrorType.CONTENT
                        )
                    else:
                        last_error = LLMException(
                            f"Gemini API 错误: {e}",
                            LLMErrorType.UNKNOWN
                        )
                    
                    if attempt < self.ai_config.max_retries and last_error.error_type in (LLMErrorType.RATE_LIMIT, LLMErrorType.NETWORK):
                        wait_time = 2 ** attempt
                        logger.warning(f"遇到错误，{wait_time}秒后重试...")
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
                f"Gemini 客户端初始化失败: {e}",
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
        
        # 初始化 4 个必需属性
        # Claude 3.5 Sonnet 和 Opus 支持视觉
        model_lower = ai_config.model.lower()
        self._supports_vision = "opus" in model_lower or "sonnet" in model_lower or "haiku" in model_lower
        
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
        from anthropic import APIConnectionError, APIError, AuthenticationError, RateLimitError
        
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
                    # 使用 Semaphore 进行并发限流
                    with self._sem:
                        response = client.messages.create(
                            model=self.ai_config.model,
                            max_tokens=min(max_tokens or self.max_output_tokens, self.max_output_tokens),
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


class GoogleTranslateClient:
    """Google 翻译客户端（免费版）
    
    使用 deep-translator 库调用 Google 翻译的免费接口
    注意：这不是 LLM，但实现 LLMClient 接口以便统一使用
    """
    
    def __init__(self, ai_config: AIConfig):
        """初始化 Google 翻译客户端
        
        Args:
            ai_config: AI 配置（虽然不需要 API Key，但保持接口一致）
        """
        self.ai_config = ai_config
        self.provider_name = "google_translate"
        
        # 检查依赖
        try:
            from deep_translator import GoogleTranslator
            self._translator_class = GoogleTranslator
        except ImportError:
            raise LLMException(
                "未安装 deep-translator 库，请运行: pip install deep-translator",
                LLMErrorType.UNKNOWN
            )
        
        # 必需属性（Google 翻译不是 LLM，设置合理的默认值）
        self.supports_vision = False
        self.max_input_tokens = 50000  # Google 翻译单次可翻译约 5000 字符，这里设置较大值
        self.max_output_tokens = 50000
        self.max_concurrency = ai_config.max_concurrency  # 使用配置的并发限制
        
        # 创建 Semaphore 用于并发限流
        self._sem = threading.Semaphore(self.max_concurrency)
        
        # 取消令牌（用于支持取消操作，由 SubtitleTranslator 在调用前设置）
        self._cancel_token = None
    
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResult:
        """使用 Google 翻译进行翻译
        
        注意：prompt 应该包含字幕文本，格式由 get_translation_prompt 生成
        我们需要从 prompt 中提取字幕文本，翻译后重新组装
        
        Args:
            prompt: 翻译提示词（包含字幕文本）
            system: 系统提示词（忽略，Google 翻译不需要）
            max_tokens: 最大 token 数（忽略）
            temperature: 温度参数（忽略）
            stop: 停止序列（忽略）
        
        Returns:
            LLMResult 对象，包含翻译后的文本
        
        Raises:
            LLMException: 当翻译失败时抛出
        """
        try:
            # 从 prompt 中提取字幕文本
            # prompt 格式：请将以下字幕从 X 翻译成 Y...\n\n字幕内容：\n{字幕文本}\n\n请直接返回...
            subtitle_text = self._extract_subtitle_from_prompt(prompt)
            
            # 提取源语言和目标语言
            source_lang, target_lang = self._extract_languages_from_prompt(prompt)
            
            # 调试日志：记录提取的语言信息
            from core.logger import get_logger
            logger = get_logger()
            logger.debug(f"GoogleTranslateClient: 提取到源语言={source_lang}, 目标语言={target_lang}, 字幕文本长度={len(subtitle_text) if subtitle_text else 0}")
            
            # 如果无法从 prompt 中提取字幕格式，尝试其他方法
            if not subtitle_text or not source_lang or not target_lang:
                # 尝试从 prompt 中提取目标语言名称（即使字幕提取失败）
                import re
                # 尝试提取目标语言名称
                target_match = re.search(r"翻译成\s+(\S+)", prompt)
                if target_match:
                    target_lang_name = target_match.group(1).rstrip('。')
                    target_lang = self._language_name_to_code(target_lang_name)
                    # 使用自动检测源语言
                    source_lang_short = "auto"
                    target_lang_short = self._normalize_lang_code(target_lang)
                else:
                    # 完全无法提取，使用默认值（但这是不应该发生的情况）
                    logger.warning("无法从 prompt 中提取语言信息，使用默认值（auto -> zh-CN）")
                    source_lang_short = "auto"
                    target_lang_short = "zh-CN"
                
                # 如果没有字幕文本，尝试从 prompt 中提取（简单文本模式）
                if not subtitle_text:
                    subtitle_text = prompt.strip()
                
                # 如果还是没有字幕文本，直接翻译整个 prompt（用于测试）
                if subtitle_text:
                    # 直接翻译文本（不解析 SRT 格式）
                    # 使用 Semaphore 进行并发限流
                    from deep_translator import GoogleTranslator
                    with self._sem:
                        translator = GoogleTranslator(source=source_lang_short, target=target_lang_short)
                        translated_text = translator.translate(subtitle_text)
                else:
                    raise LLMException("无法从 prompt 中提取字幕文本", LLMErrorType.UNKNOWN)
            else:
                # 正常模式：提取到了字幕格式
                # 转换语言代码格式（Google 翻译使用短格式，如 "zh", "en"）
                source_lang_short = self._normalize_lang_code(source_lang)
                target_lang_short = self._normalize_lang_code(target_lang)
                
                # 调试日志：记录标准化后的语言代码
                logger.debug(f"GoogleTranslateClient: 标准化后源语言={source_lang_short}, 目标语言={target_lang_short}")
                
                # 翻译字幕（保持 SRT 格式）
                # 使用 Semaphore 进行并发限流
                # 从实例属性获取 cancel_token（由 SubtitleTranslator 在调用前设置）
                with self._sem:
                    translated_text = self._translate_srt(
                        subtitle_text,
                        source_lang_short,
                        target_lang_short,
                        cancel_token=self._cancel_token
                    )
            
            return LLMResult(
                text=translated_text,
                usage=LLMUsage(),  # Google 翻译不提供 token 统计
                provider="google_translate",
                model="google_translate_free"
            )
            
        except LLMException:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                raise LLMException(
                    f"Google 翻译连接失败: {e}",
                    LLMErrorType.NETWORK
                )
            elif "quota" in error_msg or "limit" in error_msg:
                raise LLMException(
                    f"Google 翻译频率限制: {e}",
                    LLMErrorType.RATE_LIMIT
                )
            else:
                raise LLMException(
                    f"Google 翻译失败: {e}",
                    LLMErrorType.UNKNOWN
                )
    
    def _extract_subtitle_from_prompt(self, prompt: str) -> Optional[str]:
        """从 prompt 中提取字幕文本
        
        Args:
            prompt: 翻译提示词
        
        Returns:
            字幕文本，如果无法提取则返回 None
        """
        # prompt 格式：...\n\n字幕内容：\n{字幕文本}\n\n请直接返回...
        markers = ["字幕内容：", "字幕内容:", "Subtitle content:", "Subtitle content："]
        for marker in markers:
            if marker in prompt:
                parts = prompt.split(marker, 1)
                if len(parts) > 1:
                    subtitle_part = parts[1]
                    # 移除最后的提示文本（"请直接返回..."）
                    if "请直接返回" in subtitle_part:
                        subtitle_part = subtitle_part.split("请直接返回")[0]
                    elif "Please return" in subtitle_part:
                        subtitle_part = subtitle_part.split("Please return")[0]
                    return subtitle_part.strip()
        return None
    
    def _extract_languages_from_prompt(self, prompt: str) -> tuple[Optional[str], Optional[str]]:
        """从 prompt 中提取源语言和目标语言
        
        Args:
            prompt: 翻译提示词
        
        Returns:
            (源语言代码, 目标语言代码)，如果无法提取则返回 (None, None)
        """
        # prompt 格式：请将以下字幕从 {源语言名称} 翻译成 {目标语言名称}
        # 注意：prompt 中使用的是语言名称（如"中文"、"English"），需要转换为语言代码
        import re
        patterns = [
            r"从\s+(\S+)\s+翻译成\s+(\S+)",
            r"from\s+(\S+)\s+to\s+(\S+)",
            r"从\s+(\S+)\s+翻\s+(\S+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                source_lang_name = match.group(1).rstrip('。')  # 移除可能的句号
                target_lang_name = match.group(2).rstrip('。')
                # 将语言名称转换为语言代码
                source_code = self._language_name_to_code(source_lang_name)
                target_code = self._language_name_to_code(target_lang_name)
                return source_code, target_code
        return None, None
    
    def _language_name_to_code(self, lang_name: str) -> str:
        """将语言名称转换为语言代码
        
        Args:
            lang_name: 语言名称（如 "中文", "English", "日本語"）或语言代码（如 "ar", "zh-CN"）
        
        Returns:
            语言代码（如 "zh-CN", "en-US", "ja-JP", "ar"），如果无法识别则返回原值
        """
        # 语言名称到语言代码的映射（与 core/language.py 中的 get_language_name 对应）
        name_to_code = {
            "中文": "zh-CN",
            "简体中文": "zh-CN",  # 简体中文别名
            "繁體中文": "zh-TW",
            "繁体中文": "zh-TW",  # 繁体中文别名
            "English": "en-US",
            "英语": "en",  # 英语中文名
            "英文": "en",  # 英文中文名
            "日本語": "ja-JP",
            "日语": "ja",  # 日语中文名
            "日文": "ja",  # 日文中文名
            "한국어": "ko-KR",
            "韩语": "ko",  # 韩语中文名
            "韩文": "ko",  # 韩文中文名
            "Español": "es-ES",
            "西班牙语": "es",  # 西班牙语中文名
            "Français": "fr-FR",
            "法语": "fr",  # 法语中文名
            "Deutsch": "de-DE",
            "德语": "de",  # 德语中文名
            "Русский": "ru-RU",
            "俄语": "ru",  # 俄语中文名
            "Português": "pt-PT",
            "葡萄牙语": "pt",  # 葡萄牙语中文名
            "Italiano": "it-IT",
            "意大利语": "it",  # 意大利语中文名
            "العربية": "ar",  # 阿拉伯语
            "阿拉伯语": "ar",  # 阿拉伯语中文名
            "ar": "ar",  # 直接支持语言代码
            "हिन्दी": "hi-IN",  # 印地语
            "印地语": "hi",  # 印地语中文名
        }
        # 如果输入已经是语言代码（短代码或标准代码），直接返回
        # 常见的语言代码格式：2-3 字母（如 "ar", "zh", "en"）或带地区后缀（如 "ar-SA", "zh-CN"）
        if len(lang_name) <= 5 and ('-' in lang_name or lang_name.isalpha()):
            # 可能是语言代码，先尝试映射，如果没有则直接返回
            return name_to_code.get(lang_name, lang_name)
        # 否则作为语言名称查找
        return name_to_code.get(lang_name, lang_name)
    
    def _normalize_lang_code(self, lang_code: str) -> str:
        """标准化语言代码（转换为 Google 翻译支持的格式）
        
        注意：deep-translator 库的 GoogleTranslator 需要特定的语言代码格式：
        - 简体中文需要使用 "zh-CN"（大写）
        - 繁体中文需要使用 "zh-TW"（大写）
        - 其他语言使用 2 字母 ISO 639-1 代码（小写）
        
        Args:
            lang_code: 语言代码（如 "zh-CN", "en-US", "ar"）
        
        Returns:
            标准化后的语言代码（如 "zh-CN", "zh-TW", "en", "ar"）
        """
        # 提取主语言代码和地区代码
        lang_code_lower = lang_code.lower()
        parts = lang_code.split("-")
        main_code = parts[0].lower()
        region_code = parts[1].upper() if len(parts) > 1 else None
        
        # 特殊处理：中文需要区分简体和繁体
        if main_code == "zh":
            if lang_code_lower in ["zh-tw", "zh_tw", "zh-hant"]:
                normalized = "zh-TW"
            else:
                # zh, zh-cn, zh_cn, zh-hans 等都视为简体中文
                normalized = "zh-CN"
            if normalized != lang_code:
                logger.debug(f"GoogleTranslateClient: 中文语言代码标准化 {lang_code} -> {normalized}")
            return normalized
        
        # 其他语言：使用小写的主语言代码
        lang_map = {
            "en": "en",
            "ja": "ja",
            "ko": "ko",
            "es": "es",
            "fr": "fr",
            "de": "de",
            "ru": "ru",
            "pt": "pt",
            "it": "it",
            "ar": "ar",
            "hi": "hi",
        }
        
        normalized = lang_map.get(main_code, main_code)
        
        # 调试日志：记录语言代码转换
        if normalized != lang_code:
            logger.debug(f"GoogleTranslateClient: 语言代码标准化 {lang_code} -> {normalized}")
        
        return normalized
    
    def _translate_srt(
        self,
        srt_text: str,
        source_lang: str,
        target_lang: str,
        cancel_token=None
    ) -> str:
        """翻译 SRT 或 VTT 字幕文件（保持时间轴格式）
        
        支持两种格式：
        1. SRT 格式：序号、时间轴（-->）、文本、空行
        2. VTT 格式：WEBVTT 头部、时间轴（-->）、文本、空行
        
        Args:
            srt_text: SRT 或 VTT 字幕文本
            source_lang: 源语言代码
            target_lang: 目标语言代码
            cancel_token: 取消令牌（可选）
        
        Returns:
            翻译后的 SRT 字幕文本（统一转换为 SRT 格式）
        
        Raises:
            LLMException: 当翻译失败时抛出
            TaskCancelledError: 当取消令牌被触发时抛出
        """
        from deep_translator import GoogleTranslator
        
        try:
            # 检查是否是 VTT 格式
            is_vtt = srt_text.strip().startswith("WEBVTT") or "WEBVTT" in srt_text[:100]
            
            if is_vtt:
                # 处理 VTT 格式
                return self._translate_vtt_to_srt(srt_text, source_lang, target_lang, cancel_token=cancel_token)
            else:
                # 处理 SRT 格式
                return self._translate_srt_format(srt_text, source_lang, target_lang, cancel_token=cancel_token)
            
        except TaskCancelledError:
            # 取消操作，直接重新抛出（不要包装成 LLMException）
            from core.exceptions import TaskCancelledError
            raise
        except Exception as e:
            raise LLMException(
                f"翻译字幕失败: {e}",
                LLMErrorType.UNKNOWN
            )
    
    def _translate_srt_format(
        self,
        srt_text: str,
        source_lang: str,
        target_lang: str,
        cancel_token=None
    ) -> str:
        """翻译 SRT 格式字幕（保持时间轴格式）
        
        Args:
            srt_text: SRT 字幕文本
            source_lang: 源语言代码
            target_lang: 目标语言代码
            cancel_token: 取消令牌（可选）
        
        Returns:
            翻译后的 SRT 字幕文本
        
        Raises:
            TaskCancelledError: 如果取消令牌被触发
        """
        from core.exceptions import TaskCancelledError
        
        # 解析 SRT 格式：序号、时间轴、文本、空行
        lines = srt_text.split("\n")
        translated_lines = []
        current_block = []
        
        for line in lines:
            # 检查取消状态（在处理每个字幕块前）
            if cancel_token and cancel_token.is_cancelled():
                reason = cancel_token.get_reason() or "用户取消"
                raise TaskCancelledError(reason)
            line_stripped = line.strip()
            
            # 空行：结束当前字幕块
            if not line_stripped:
                if current_block:
                    translated_block = self._translate_subtitle_block(
                        current_block,
                        source_lang,
                        target_lang,
                        cancel_token=cancel_token
                    )
                    translated_lines.extend(translated_block)
                    translated_lines.append("")
                    current_block = []
                else:
                    translated_lines.append("")
                continue
            
            # 判断是否是序号（纯数字）
            if line_stripped.isdigit() and not current_block:
                # 新字幕块开始
                current_block = [line]
                continue
            
            # 判断是否是时间轴（包含 -->）
            if "-->" in line:
                if current_block:  # 确保有序号
                    current_block.append(line)
                continue
            
            # 其他行：字幕文本（添加到当前块）
            if current_block:
                current_block.append(line)
            else:
                # 没有序号，可能是格式问题，直接添加
                translated_lines.append(line)
        
        # 处理最后一个块
        if current_block:
            if cancel_token and cancel_token.is_cancelled():
                reason = cancel_token.get_reason() or "用户取消"
                raise TaskCancelledError(reason)
            translated_block = self._translate_subtitle_block(
                current_block,
                source_lang,
                target_lang,
                cancel_token=cancel_token
            )
            translated_lines.extend(translated_block)
        
        return "\n".join(translated_lines)
    
    def _translate_vtt_to_srt(
        self,
        vtt_text: str,
        source_lang: str,
        target_lang: str,
        cancel_token=None
    ) -> str:
        """将 VTT 格式转换为 SRT 格式并翻译
        
        Args:
            vtt_text: VTT 字幕文本
            source_lang: 源语言代码
            target_lang: 目标语言代码
        
        Returns:
            翻译后的 SRT 字幕文本
        """
        lines = vtt_text.split("\n")
        translated_lines = []
        current_block = []
        subtitle_index = 1  # SRT 格式需要序号
        skip_header = True
        
        for line in lines:
            line_stripped = line.strip()
            
            # 跳过 VTT 头部（WEBVTT 及其元数据）
            if skip_header:
                if line_stripped.upper().startswith("WEBVTT"):
                    continue
                if line_stripped.startswith("Kind:") or line_stripped.startswith("Language:"):
                    continue
                if line_stripped.startswith("Translator:") or line_stripped.startswith("Reviewer:"):
                    continue
                # 如果遇到空行且还没开始字幕块，继续跳过
                if not line_stripped and not current_block:
                    continue
                # 遇到时间轴，开始处理字幕
                if "-->" in line:
                    skip_header = False
                elif line_stripped and not line_stripped.startswith("WEBVTT") and not "-->" in line:
                    # 可能是注释或其他元数据，继续跳过
                    continue
            
            # 空行：结束当前字幕块
            if not line_stripped:
                if current_block:
                    # 添加序号到块的开头（如果是 VTT，可能没有序号）
                    if not current_block[0].strip().isdigit():
                        current_block.insert(0, str(subtitle_index))
                    
                    translated_block = self._translate_subtitle_block(
                        current_block,
                        source_lang,
                        target_lang,
                        cancel_token=cancel_token
                    )
                    translated_lines.extend(translated_block)
                    translated_lines.append("")
                    current_block = []
                    subtitle_index += 1
                else:
                    translated_lines.append("")
                continue
            
            # 判断是否是时间轴（包含 -->）
            if "-->" in line:
                # VTT 时间轴格式：00:00:00.000 --> 00:00:02.000
                # 转换为 SRT 时间轴格式：00:00:00,000 --> 00:00:02,000 (点改为逗号)
                srt_time_line = line.replace(".", ",")
                if not current_block:
                    # 新字幕块，添加序号
                    current_block = [str(subtitle_index)]
                current_block.append(srt_time_line)
                continue
            
            # 其他行：字幕文本（添加到当前块）
            if current_block:
                current_block.append(line)
            elif not skip_header:
                # 不在头部，且没有时间轴，可能是格式问题，直接添加
                translated_lines.append(line)
        
        # 处理最后一个块
        if current_block:
            if not current_block[0].strip().isdigit():
                current_block.insert(0, str(subtitle_index))
            translated_block = self._translate_subtitle_block(
                current_block,
                source_lang,
                target_lang,
                cancel_token=cancel_token
            )
            translated_lines.extend(translated_block)
        
        return "\n".join(translated_lines)
    
    def _translate_subtitle_block(
        self,
        block: list[str],
        source_lang: str,
        target_lang: str,
        cancel_token=None
    ) -> list[str]:
        """翻译单个字幕块
        
        Args:
            block: 字幕块（序号、时间轴、文本行）
            source_lang: 源语言代码
            target_lang: 目标语言代码
            cancel_token: 取消令牌（可选）
        
        Returns:
            翻译后的字幕块
        
        Raises:
            TaskCancelledError: 如果取消令牌被触发
        """
        from deep_translator import GoogleTranslator
        from core.exceptions import TaskCancelledError
        
        # 检查取消状态（在每个字幕块翻译开始时）
        if cancel_token and cancel_token.is_cancelled():
            reason = cancel_token.get_reason() or "用户取消"
            raise TaskCancelledError(reason)
        
        if len(block) < 3:
            return block  # 格式不正确，返回原样
        
        # 序号和时间轴保持不变
        result = [block[0], block[1]]
        
        # 收集所有文本行（跳过序号和时间轴）
        text_lines = []
        for line in block[2:]:
            if line.strip():  # 非空行
                text_lines.append(line)
        
        if not text_lines:
            return block  # 没有文本，返回原样
        
        # 合并文本行进行翻译（Google 翻译可以处理多行）
        text_to_translate = "\n".join(text_lines)
        
        # 再次检查取消状态（在调用阻塞的 translate 之前）
        if cancel_token and cancel_token.is_cancelled():
            reason = cancel_token.get_reason() or "用户取消"
            raise TaskCancelledError(reason)
        
        try:
            # 调试日志：记录翻译参数
            logger.debug(f"GoogleTranslateClient._translate_subtitle_block: source={source_lang}, target={target_lang}, text_length={len(text_to_translate)}")
            logger.debug(f"GoogleTranslateClient._translate_subtitle_block: 原文前50字符: {text_to_translate[:50] if len(text_to_translate) > 50 else text_to_translate}")
            
            # 标准化源语言代码（处理语言名称如"简体中文"、"英语"等）
            actual_source_lang = self._normalize_lang_code(self._language_name_to_code(source_lang))
            
            # 标准化目标语言代码
            # deep-translator 库的 GoogleTranslator 需要使用 zh-CN（大写）来获得简体中文
            actual_target_lang = self._language_name_to_code(target_lang)
            # 确保中文使用正确的格式（zh-CN 或 zh-TW，大写）
            if actual_target_lang.lower() in ["zh-cn", "zh_cn", "zh", "chinese"]:
                actual_target_lang = "zh-CN"
            elif actual_target_lang.lower() in ["zh-tw", "zh_tw"]:
                actual_target_lang = "zh-TW"
            else:
                # 其他语言使用小写的短格式
                actual_target_lang = self._normalize_lang_code(actual_target_lang)
            
            logger.debug(f"GoogleTranslateClient: 实际使用源语言={actual_source_lang}, 目标语言={actual_target_lang}")
            
            translator = GoogleTranslator(source=actual_source_lang, target=actual_target_lang)
            # 注意：translator.translate() 是阻塞调用，无法在调用期间中断
            # 只能在调用前检查取消状态，因此取消响应可能有延迟（直到当前字幕块翻译完成）
            translated_text = translator.translate(text_to_translate)
            
            # 调试日志：记录翻译结果
            logger.debug(f"GoogleTranslateClient._translate_subtitle_block: 翻译结果前50字符: {translated_text[:50] if len(translated_text) > 50 else translated_text}")
            
            # 检查翻译结果是否与原文相同（可能是翻译失败但没有抛出异常）
            if translated_text == text_to_translate:
                logger.warning(
                    f"Google 翻译返回的文本与原文相同，可能翻译失败。源语言={source_lang}, 目标语言={target_lang}。"
                    f"原文前100字符: {text_to_translate[:100]}"
                )
                # 即使翻译失败（返回原文），也继续使用翻译结果（可能是同语言翻译或其他原因）
            
            # 将翻译结果按行分割（如果原文本是多行）
            if "\n" in translated_text:
                translated_lines = translated_text.split("\n")
            else:
                # 单行翻译结果，尝试保持原行数结构（如果原文是多行）
                # 使用原始文本（去除说明后的）来判断
                if "\n" in text_to_translate:
                    # 原文是多行，但翻译结果是单行，保持原行数
                    original_lines = text_to_translate.split("\n")
                    translated_lines = [translated_text if i == 0 else "" for i in range(len(original_lines))]
                else:
                    # 原文是单行，翻译结果也是单行
                    translated_lines = [translated_text]
            
            # 添加翻译后的文本行
            # 如果翻译结果的行数与原文不一致，尽量保持原行数结构
            if len(translated_lines) != len(text_lines):
                logger.debug(
                    f"翻译结果行数与原文不一致：原文 {len(text_lines)} 行，翻译结果 {len(translated_lines)} 行"
                )
                # 如果翻译结果是单行但原文是多行，将单行结果作为所有行的内容
                if len(translated_lines) == 1 and len(text_lines) > 1:
                    # 将单行翻译结果分配给所有行
                    for i, orig_line in enumerate(text_lines):
                        if i == 0:
                            result.append(translated_lines[0])
                        else:
                            result.append("")  # 其他行保持空行
                else:
                    # 其他情况，直接使用翻译结果（可能行数不一致）
                    result.extend(translated_lines)
            else:
                # 行数一致，直接添加
                result.extend(translated_lines)
            
        except TaskCancelledError:
            # 取消操作，直接重新抛出
            raise
        except Exception as e:
            # 翻译失败，返回原文（但保留序号和时间轴）
            logger.error(
                f"Google 翻译失败，使用原文: {e}。源语言={source_lang}, 目标语言={target_lang}, "
                f"文本长度={len(text_to_translate)}"
            )
            # 保留序号和时间轴，使用原文文本
            result.extend(text_lines)
        
        return result


# 注册表：provider 名称 -> 实现类
_LLM_REGISTRY: dict[str, type] = {
    "openai": OpenAICompatibleClient,  # 兼容所有 OpenAI 风格服务
    "openai_compatible": OpenAICompatibleClient,  # 别名，指向同一个实现
    "gemini": GeminiClient,
    "anthropic": AnthropicClient,
    "google_translate": GoogleTranslateClient,  # Google 翻译（免费版）
    "google": GoogleTranslateClient,  # 别名
}


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
    
    # 从注册表获取实现类
    client_class = _LLM_REGISTRY.get(provider)
    
    if client_class is None:
        raise LLMException(
            f"不支持的 AI 提供商: {provider}。支持的提供商: {', '.join(_LLM_REGISTRY.keys())}",
            LLMErrorType.UNKNOWN
        )
    
    # 创建实例
    return client_class(ai_config)
