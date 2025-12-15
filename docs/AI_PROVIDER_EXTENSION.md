# AI Provider 扩展规范（v2.1 草案版）

> 本文档定义本项目中 **AI 调用层（LLM 层）** 的统一抽象、扩展方式与行为约定。  
> 目标是：
> - 让上层（pipeline / translator / summarizer / GUI）只依赖 **一个抽象接口：`LLMClient`**；
> - 通过少量实现类 + 注册表/工厂，支持 OpenAI 官方、各类 OpenAI 兼容服务（DeepSeek/Kimi/Qwen/智谱/Ollama 等）、Gemini、Anthropic 等；
> - 未来新增/替换模型时，只改实现与配置，不动业务代码。

> ⚠️ **与其他文档的关系**  
> 本文档只约束"AI 层（LLM 抽象与实现）"的设计与扩展方式。  
> 当本文件与以下更高优先级文档在行为细节上存在冲突时，应以高优先级文档为准，并在后续更新本文件以重新对齐：  
> 1. `docs/v2_final_plan.md` – 行为规范（Dry Run / 增量 / 输出结构等）  
> 2. `docs/project_blueprint.md` – 项目蓝图  
> 3. `docs/acceptance_criteria.md` – 验收标准  
> 4. `docs/ide_修复任务表_AI层与流水线.md` – 当前版本的具体修复任务与落地顺序

---

## 1. 总体设计目标

1. **统一抽象：LLMClient Protocol**

   - 所有 AI 调用都通过 `LLMClient` 这个协议接口进行（形如 `generate()`），上层代码不感知具体厂商。
   - 任何新模型接入，都必须实现 `LLMClient`，并通过注册表 + 工厂产生实例。

2. **极简实现族：三大实现类**

   - 所有具体实现统一收敛为三类：
     - `OpenAICompatibleClient`：  
       使用 OpenAI Chat Completions 协议调用所有兼容服务：
       - OpenAI 官方
       - DeepSeek
       - Kimi/Moonshot
       - 通义千问 Qwen（OpenAI 兼容端点）
       - 智谱 GLM（OpenAI 兼容端点）
       - 本地 Ollama / vLLM / 其它 OpenAI-Compatible HTTP 服务
     - `GeminiClient`：  
       调用 Google Gemini 原生或其 OpenAI 兼容端点。
     - `AnthropicClient`：  
       调用 Claude/Anthropic，基于官方 SDK 适配为 LLMClient。

   - 原来那种「每个厂商一个 Client」（例如 `DeepSeekClient/KimiClient/QwenClient`）的模式全部废止或迁移到 `OpenAICompatibleClient` + 配置。

3. **对业务层：开闭分离**

   - 对上层业务（pipeline / translator / summarizer / GUI）：  
     - 只依赖 `LLMClient` 接口 + `create_llm_client()` 工厂；
     - 不允许直接 import 某个厂商 SDK 或具体 Client 类。
   - 对下层实现：  
     - 可以自由更换 SDK、base_url、模型名等，只要保证接口/异常约定不变。

---

## 2. LLMClient Protocol 抽象

### 2.1 接口定义（示意）

> 说明：这里用的是"Protocol 风格"伪代码，实际项目中可以根据需要用 `Protocol`、抽象基类或普通基类 + 文档约定。

```python
class AIProviderError(Exception):
    """LLMClient 实现层统一异常（可选内部工具）。

    说明：
    - LLMClient 实现内部可以使用 AIProviderError 作为统一包装第三方 SDK 异常的**内部类型**。
    - 对调用方而言，约定是 generate() 直接抛出 LLMException，不需要感知底层 SDK 细节。
    - 是否在实现内部先 wrap 为 AIProviderError，再转成 LLMException，由实现决定，不做强制要求。
    """
    pass


class LLMClient(Protocol):
    """统一的 LLM 抽象接口。

    上层代码只依赖此接口，不关心具体 Provider 或 SDK。
    """

    # ---- 能力属性：所有实现必须提供（字段或 @property 均可） ----
    supports_vision: bool
    max_input_tokens: int
    max_output_tokens: int
    max_concurrency: int

    # ---- 核心调用接口 ----
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResult:
        """调用 LLM 完成一次文本生成。

        要求：
        - 正常时返回 LLMResult（包含 content 和 usage 统计）。
        - 失败时抛出 LLMException（见错误处理章节），不得返回 None。
        """
```

> **关键点**：
>
> * `supports_vision`/`max_input_tokens`/`max_output_tokens`/`max_concurrency` 是 **LLMClient 协议的必需成员**，所有实现必须提供。
> * 值可以不同，例如：
>
>   * `supports_vision=False` 代表纯文本模型；
>   * `max_input_tokens` 和 `max_output_tokens` 可为保守估计值。

---

## 3. 内置三大实现类

本项目中，所有实际的 LLM 调用都应通过以下三个实现之一完成：

* `OpenAICompatibleClient`
* `GeminiClient`
* `AnthropicClient`

### 3.1 OpenAICompatibleClient

**用途**：适配所有 OpenAI Chat Completions 兼容服务，包括：

* OpenAI 官方服务（默认 base_url = `https://api.openai.com/v1`）
* DeepSeek
* 各类国内外 OpenAI 兼容服务（通过 base_url 区分）
* 本地服务（如 Ollama 监听的 `/v1` 接口）

**配置约定：**

```jsonc
{
  "ai": {
    "provider": "openai",          // 向后兼容，内部映射为 OpenAICompatibleClient
    "model": "gpt-4o-mini",
    "api_key_env": "OPENAI_API_KEY",
    "base_url": "https://api.openai.com/v1",
    "timeout_seconds": 120,
    "max_input_tokens": 128000,
    "max_output_tokens": 4096,
    "max_concurrency": 5,
    "temperature": 0.3
  }
}
```

> 说明：
>
> * 配置中的 `"provider": "openai"` 实际对应的是 `OpenAICompatibleClient`。
> * 若 `base_url` 为空或为官方地址，则调用 OpenAI 官方；否则视为 OpenAI 兼容第三方服务。
> * 内部注册表同样可以支持 `"openai_compatible"` 映射到同一个实现类，便于以后在文档中区分"官方"与"兼容"。

**示意实现（简化）：**

```python
class OpenAICompatibleClient(LLMClient):
    def __init__(self, ai_config: AIConfig):
        self.config = ai_config
        self._supports_vision = getattr(ai_config, "supports_vision", False)
        self._max_input_tokens = getattr(ai_config, "max_input_tokens", 128000)
        self._max_output_tokens = getattr(ai_config, "max_output_tokens", 4096)
        self._max_concurrency = getattr(ai_config, "max_concurrency", 5)

        self._sem = threading.Semaphore(self._max_concurrency)

    # ---- 能力属性 ----

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

    # ---- 依赖检查 ----

    def check_dependencies(self) -> bool:
        try:
            import openai  # 新版 OpenAI SDK
            return True
        except ImportError:
            logger.error("未安装 openai SDK，请执行: pip install 'openai>=1.0.0'")
            return False

    # ---- 核心调用 ----

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResult:
        if not self.check_dependencies():
            raise LLMException(
                "openai SDK 未安装",
                error_type=LLMErrorType.RUNTIME,
            )

        from openai import OpenAI

        base_url = self.config.base_url or "https://api.openai.com/v1"
        timeout = self.config.timeout_seconds
        temperature = getattr(self.config, "temperature", 0.3)

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=base_url,
            timeout=timeout,
        )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            with self._sem:
                completion = client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temperature or getattr(self.config, "temperature", 0.3),
                    max_tokens=min(
                        max_tokens or self.max_output_tokens,
                        self.max_output_tokens,
                    ),
                    stop=stop,
                )
            
            content = completion.choices[0].message.content or ""
            usage = completion.usage
            
            return LLMResult(
                content=content,
                usage=LLMUsage(
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                ),
            )
        except Exception as e:
            # 此处捕获所有底层异常，统一转换为 LLMException
            # 可以根据异常类型映射为不同的 LLMErrorType
            raise LLMException(
                f"OpenAICompatibleClient 调用失败: {e}",
                error_type=LLMErrorType.UNKNOWN,
            )
```

---

### 3.2 GeminiClient

**用途**：适配 Google Gemini 系列模型，支持：

* 原生 `google-generativeai` 调用；
* （可选）通过 OpenAI 兼容端点调用。

**配置示例（原生模式）：**

```jsonc
{
  "ai": {
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "api_key_env": "GEMINI_API_KEY",
    "max_input_tokens": 128000,
    "max_output_tokens": 4096,
    "max_concurrency": 3,
    "temperature": 0.3
  }
}
```

**配置示例（OpenAI 兼容模式，通过 OpenAICompatibleClient）：**

```jsonc
{
  "ai": {
    "provider": "openai",
    "model": "gemini-1.5-flash",
    "api_key_env": "GEMINI_API_KEY",
    "base_url": "https://generativelanguage.googleapis.com/v1beta",
    "max_input_tokens": 128000,
    "max_output_tokens": 4096,
    "max_concurrency": 3
  }
}
```

> 是否使用独立 `GeminiClient`，还是完全走 `OpenAICompatibleClient`，由实际实现决定。  
> 本文档只要求：任一方式都必须实现 LLMClient 协议，且遵守统一异常与能力属性约定。

---

### 3.3 AnthropicClient

**用途**：适配 Claude / Anthropic 系列模型。

* 必须实现 LLMClient 协议；
* 内部使用 Anthropic 官方 SDK；
* 将所有 SDK 异常转换为 `LLMException`；
* 能力属性 `supports_vision` 等按模型能力设置。

（具体代码略，本节只定义规范，不强行约束 SDK 使用细节。）

---

## 4. 注册表与工厂

### 4.1 注册表

```python
_LLM_REGISTRY: dict[str, type[LLMClient]] = {
    "openai": OpenAICompatibleClient,           # 兼容所有 OpenAI 风格服务
    "openai_compatible": OpenAICompatibleClient,
    "gemini": GeminiClient,
    "anthropic": AnthropicClient,
}
```

> 说明：
>
> * `"openai"` 与 `"openai_compatible"` 两个 provider 名称都映射到 `OpenAICompatibleClient`，用于兼容旧配置并兼顾新语义。
> * 新增 Provider 时，必须：
>
>   1. 实现 LLMClient；
>   2. 注册到 `_LLM_REGISTRY` 中；
>   3. 更新文档示例与推荐配置。

### 4.2 工厂函数

```python
def get_llm_client(ai_config: AIConfig) -> LLMClient:
    provider_name = ai_config.provider  # 例如 "openai" / "gemini" / "anthropic"
    cls = _LLM_REGISTRY.get(provider_name)

    if cls is None:
        raise AppException(
            f"未知的 LLM Provider: {provider_name}",
            error_type=ErrorType.CONFIG,
        )

    client = cls(ai_config)

    if not client.check_dependencies():
        raise AppException(
            f"LLM Provider 依赖缺失: {provider_name}",
            error_type=ErrorType.RUNTIME,
        )

    return client
```

> 上层代码（pipeline / translator / summarizer）不得直接 `new OpenAICompatibleClient(...)`，而必须通过此工厂构造 LLM 实例。

---

## 5. 错误处理约定

### 5.1 LLMClient 实现层

* LLMClient 实现内部可以使用 `AIProviderError` 作为统一包装第三方 SDK 异常的**内部类型**（可选）；
* 对调用方而言，约定是：
  * `LLMClient.generate(...)` 正常返回 `LLMResult`；
  * 调用失败时抛出 `LLMException`（包含 `LLMErrorType` 等信息），上层逻辑不需要感知底层 SDK 细节；
* 是否在实现内部先 wrap 为 `AIProviderError`，再转成 `LLMException`，由实现决定，不做强制要求。

### 5.2 LLM 层对上暴露（现有机制）

* 在调用 LLMClient 的地方，统一捕获 `LLMException`，转换为：
  * `AppException` 并交给 `failure_logger`。

> **重要**：
>
> * `LLMException` 这个名字 **继续保留**（向后兼容），不重命名；
> * `AIProviderError` 是 **LLMClient 内部实现层** 的可选统一异常类型，用于封装第三方 SDK 异常，但不强制要求使用。

---

## 6. 配置与 UI 建议

1. **Provider 下拉框建议值：**

   * OpenAI（包括所有 OpenAI 兼容服务）
   * Gemini
   * Anthropic (Claude)

2. **当选择 "OpenAI" 时：**

   * 默认 base_url = `https://api.openai.com/v1`；
   * 若用户选择"DeepSeek / 本地 Ollama"等预设：
     * UI 自动填入对应 base_url（用户可以手动修改）；
     * 仍使用 provider = "openai" + `OpenAICompatibleClient` 实现。

3. **当选择 "Gemini" 时：**

   * 原生模式：不暴露 base_url，只让用户填 API Key + model；
   * 兼容模式（可选）：由高级配置启用，通过 `OpenAICompatibleClient` 调用。

4. **本地模型（Ollama 等）特别说明：**

   * 建议：
     * `base_url = "http://localhost:11434/v1"`
     * `timeout_seconds` 调大（例如 600 秒）；
     * `max_concurrency` 适当调低（例如 2~3），防止 CPU 模型被打爆。

---

## 7. 扩展规则（为未来新 Provider 预留）

1. 如需支持新的协议/厂商（假设为 `FooLLM`）：

   * 必须实现一个新的 `FooLLMClient(LLMClient)`；
   * 必须在 `_LLM_REGISTRY` 中注册新的 provider 名称；
   * 必须更新本文件中：
     * 支持 Provider 列表；
     * 推荐配置示例。

2. 不允许的扩展方式：

   * 在业务层直接 import FooLLM 的 SDK；
   * 直接在 pipeline 内 new FooLLM 原生 client；
   * 绕过 LLMClient 接口直接调用 HTTP。

---

## 8. 状态说明

> 版本：**v2.1 草案版**  
> 说明：
>
> * 本版是为配合"R0/R1 修复任务 + LLM 架构重构"而快速同步的版本；
> * 实现落地后，可在此基础上补充：
>
>   * 实际使用中的推荐配置表（不同场景：便宜/高质/本地）；
>   * 更详细的错误码映射规范；
>   * 多模型路由策略（不同任务走不同 LLM）；
> * 任何修改必须保障：
>
>   * LLMClient 抽象和三大实现族不被破坏；
>   * 注册表 + 工厂模式保留；
>   * LLMException 的错误路径保持一致。
