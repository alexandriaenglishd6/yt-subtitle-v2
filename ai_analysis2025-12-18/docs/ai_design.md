# AI 调用设计规范（ai_design.md）

> 面向对象：所有 AI / IDE / 开发者  
> 目的：为字幕翻译 & 文本摘要提供一个**可扩展、多供应商、安全可控**的统一 AI 调用层，避免将来接入新模型时对业务代码大改。

本规范与以下文档配套使用：

- `docs/project_blueprint.md` – 项目蓝图（整体目标和场景）
- `docs/v2_final_plan.md` – 行为规范（Dry Run / 增量 / 输出结构 / LanguageConfig 等）
- `docs/ide_任务表.md` – 任务拆分与执行顺序
- `docs/ui_plan.md` – UI 布局与交互
- `docs/acceptance_criteria.md` – 验收标准
- `docs/ide_integration.md` – IDE 行为约束

当本文件与上面任何文档冲突时：

- 行为语义仍以 `v2_final_plan.md` 为准；
- 任务优先级与顺序以 `ide_任务表.md` 为准；
- 本文件主要约束 **AI 调用层的架构与边界**。

---

## 1. 设计目标与非目标

### 1.1 设计目标

1. **统一接口，多供应商**  
   - 字幕翻译 / 摘要模块只依赖一个抽象的 AI 客户端接口（LLMClient），不直接依赖某家 SDK。  
   - 将来接入新的 AI 供应商时，只需新增实现，不需要修改业务层。

2. **配置驱动，易于切换**  
   - 当前使用的 provider / model 等来自 `config.json` 中的 `ai` 配置，而不是写死在代码。  
   - 用户（或你自己）可以通过配置切换供应商和模型，而不修改代码。

3. **错误与重试行为统一**  
   - 不同供应商的不同异常（网络错误 / 授权失败 / 限流 / 内容违规等）在 AI 层统一分类；  
   - 上层只需要看到“这次调用成功/失败 + 某几类统一错误类型”。

4. **便于扩展的策略层**  
   - 支持现在的简单场景（单一 provider）；  
   - 为未来的高级策略留出接口（例如按语言选择不同 provider、主备切换、用量控制）。

5. **安全与隐私控制**  
   - 不在日志中泄露 API key；  
   - 不强制长期持久化完整字幕内容或完整 prompt。

### 1.2 非目标（当前阶段不做）

- 不实现复杂的多供应商“自动降级 / 负载均衡策略”（P2 以后再考虑）；  
- 不实现精确的计费系统，仅预留 usage 信息字段；  
- 不实现复杂的 JSON 结构化输出协议（当前以纯文本翻译和摘要为主，结构化摘要属于 P2）。

---

## 2. 总体架构概览

AI 调用层主要包含 4 个角色：

1. **配置层（AIConfig）** – 从 `config.json` 读取当前 AI 相关配置；
2. **抽象接口（LLMClient）** – 对上游（翻译/摘要模块）提供统一调用方式；
3. **具体实现（各供应商 Client）** – 封装 OpenAI / Anthropic / Gemini / Groq 等 SDK 或 HTTP 调用；
4. **策略层（AIStrategy / AIManager）** – 根据配置和简单策略选择具体 client 实例。

结构示意：

```text
SubtitleTranslator / Summarizer
        │
        ▼
     LLMClient (抽象接口)
        │
        ▼
   AIManager / AIStrategy
  ┌────────┴───────────┐
  ▼                    ▼
OpenAIClient      ClaudeClient
  ▼                    ▼
 OpenAI SDK       Anthropic SDK / HTTP
约束：

SubtitleTranslator / Summarizer 只能依赖 LLMClient 抽象，不得直接 import 某个供应商 SDK；

供应商相关实现（OpenAI、Claude、Gemini 等）集中放在一个模块（例如 core/ai_providers.py），避免散落业务层。

3. 配置设计（config.ai）
3.1 配置结构建议
在 config.json 中，ai 字段建议采用类似结构：

json
复制代码
{
  "ai": {
    "provider": "openai",                // "anthropic" / "gemini" / "groq" / "local" 等
    "model": "gpt-4.1-mini",
    "base_url": null,                    // 可选，自定义 API 网关或代理，不需要时为 null
    "timeout_seconds": 30,
    "max_retries": 2,
    "api_keys": {
      "openai": "env:OPENAI_API_KEY",
      "anthropic": "env:ANTHROPIC_API_KEY",
      "gemini": "env:GEMINI_API_KEY"
    },
    "usage_limits": {
      "daily_budget_usd": 3.0,           // 预留字段，P0 不必实现逻辑
      "max_tokens_per_call": 4096
    }
  }
}
要求：

API key 不直接写明文，而是用约定形式标记“从哪个环境变量读取”，例如 "env:OPENAI_API_KEY"；

provider 必须为一个枚举值（如 "openai" | "anthropic" | "gemini" | "groq" | "local"）；

未配置的 provider 不允许选用。

3.2 与 LanguageConfig 的关系
LanguageConfig 决定“翻译成什么语言 / 摘要使用什么语言”；

AIConfig 决定“用哪家模型来完成翻译/摘要”；

两者互相独立，业务逻辑不应该把“provider”写死在 LanguageConfig 中。

4. 抽象接口：LLMClient
4.1 接口定义（示意）
python
复制代码
from typing import Protocol, Literal, Sequence, Optional
from dataclasses import dataclass
from enum import Enum

class LLMErrorType(str, Enum):
    NETWORK = "network"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    CONTENT = "content"
    UNKNOWN = "unknown"

@dataclass
class LLMUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

@dataclass
class LLMResult:
    text: str
    usage: Optional[LLMUsage] = None
    provider: Optional[str] = None
    model: Optional[str] = None

class LLMClient(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[Sequence[str]] = None,
    ) -> LLMResult:
        """生成文本结果，抛出统一封装的 LLMException。"""
        ...
4.2 错误封装
定义统一异常类型：

python
复制代码
class LLMException(Exception):
    def __init__(self, msg: str, error_type: LLMErrorType):
        super().__init__(msg)
        self.error_type = error_type
要求：

具体供应商实现必须捕获供应商 SDK/HTTP 的异常，并映射为统一的 LLMException(error_type=...)；

错误类型分类：

NETWORK：超时 / 连接失败 / DNS 等；

AUTH：API key 无效、权限不足等；

RATE_LIMIT：频率限制、配额耗尽等；

CONTENT：内容安全过滤、提示违规等；

UNKNOWN：未归类的其他错误。

上层翻译 / 摘要模块只需要根据 error_type 决定是否重试、是否记为失败。

5. 提供者实现：AI Providers
5.1 统一入口
建议在 core/ai_providers.py 中集中放置 provider 实现：

python
复制代码
class OpenAIClient(LLMClient): ...
class AnthropicClient(LLMClient): ...
class GeminiClient(LLMClient): ...
class LocalLLMClient(LLMClient): ...
5.2 Provider 选择工厂
实现一个工厂函数，基于 AIConfig 创建对应 client：

python
复制代码
@dataclass
class AIConfig:
    provider: str
    model: str
    base_url: str | None
    timeout_seconds: int
    max_retries: int
    api_keys: dict[str, str]  # env var names or actual tokens（按统一约定）
    usage_limits: dict[str, object] | None = None

def load_api_key(config_value: str) -> str | None:
    """
    支持形如 'env:OPENAI_API_KEY' 的约定，从环境变量中读取。
    """
    ...

def create_llm_client(ai_config: AIConfig) -> LLMClient:
    # 根据 provider 创建对应 Client 实例
    ...
要求：

不在业务层出现大段 if provider == "openai": ... 逻辑；

新增 provider 时，只需增加一个 XXXClient 实现，以及在工厂函数中多一个分支。

6. 策略层：AIStrategy / AIManager
6.1 P0 简化策略
P0 阶段策略可以非常简单：

总是使用 AIConfig.provider 指定的主 provider；

暂不实现复杂自动切换/备份逻辑。

可以定义一个简单的策略类，方便将来扩展：

python
复制代码
@dataclass
class AIStrategy:
    primary_provider: str
    fallback_providers: list[str]

    def choose_for_translation(self, lang_pair: tuple[str, str]) -> str:
        return self.primary_provider

    def choose_for_summary(self, lang: str) -> str:
        return self.primary_provider
P1/P2 可在不修改翻译/摘要模块的前提下扩展逻辑：

某些语言对使用特定 provider；

主 provider 失败时自动切 fallback provider。

6.2 与并发、代理的关系
AI 调用的并发控制可复用 TaskRunner 的整体并发管理，不需要单独实现多线程池；

HTTP 代理配置可以通过环境变量或专门的 AI 代理配置注入到 LLMClient 中，不强制与 YouTube 下载的代理完全共用。

7. 在业务模块中的使用方式
7.1 SubtitleTranslator
示意：

python
复制代码
class SubtitleTranslator:
    def __init__(self, llm: LLMClient, lang_config: LanguageConfig):
        self._llm = llm
        self._lang_config = lang_config

    def translate(self, subtitle_text: str, source_lang: str, target_lang: str) -> str:
        prompt = build_translation_prompt(
            subtitle_text=subtitle_text,
            source_lang=source_lang,
            target_lang=target_lang,
            lang_config=self._lang_config,
        )
        result = self._llm.generate(prompt=prompt, max_tokens=None)
        return result.text
要求：

只通过 LLMClient 调用，传入 prompt 字符串和必要参数；

Prompt 模板集中在 core/prompts.py，语言信息由 LanguageConfig 注入；

不在此处硬编码“翻译成中文”等自然语言。

7.2 Summarizer
类似：

python
复制代码
class Summarizer:
    def __init__(self, llm: LLMClient, lang_config: LanguageConfig):
        self._llm = llm
        self._lang_config = lang_config

    def summarize(self, subtitle_text: str, lang: str | None = None) -> str:
        summary_lang = lang or self._lang_config.summary_language
        prompt = build_summary_prompt(
            subtitle_text=subtitle_text,
            summary_language=summary_lang,
        )
        result = self._llm.generate(prompt=prompt, max_tokens=None)
        return result.text
8. 错误处理与重试
8.1 在 LLMClient 内部处理的内容
每个具体 Provider 的 client（例如 OpenAIClient）内部必须处理：

网络异常（超时/连接失败）；

SDK 抛出的各类异常；

限流 / 配额错误；

授权错误（API key 错误 / 无权限）；

内容违规 / 安全过滤错误。

并根据错误类型：

在本地做有限次数重试（max_retries）；

将最终错误包装为 LLMException(error_type=...) 抛给上层。

8.2 上层业务的行为
翻译/摘要模块在遇到 LLMException 时：

根据 error_type 决定是否直接失败或等待；

无论如何，不得让整个程序崩溃退出，而是：

在日志输出错误（包含 provider/model/错误类型/简要原因）；

将当前视频记为失败，写入 failed_detail.log 和 failed_urls.txt。

9. 日志与简单统计
9.1 日志要求
每次 AI 调用，建议在 debug 级别日志中记录：

provider / model 名称；

调用耗时（ms 或 s）；

prompt 长度（字符数或估算 tokens 数）；

返回文本长度（同上）。

禁止：

在日志中打印完整 API key；

在日志中长期保存完整、敏感的字幕内容（可截断）。

9.2 usage 统计（可选）
LLMResult.usage 中可存储 tokens 统计信息（若 provider 返回）；

P0 不要求做完整“账单/预算”系统，但可在将来利用这些信息做“粗略用量估算”。

10. UI 集成规范
10.1 设置页面
AI 相关设置建议在「运行设置 → 网络 & AI」页面中展示：

AI 供应商下拉框（OpenAI / Anthropic / Gemini / Groq / Local 等）；

模型下拉框（根据 provider 动态改变候选列表）；

超时时间 / 最大重试次数（简单输入框）；

API key 配置说明（文本提示），不要求在 UI 中直接输入 key，可以提示用户通过环境变量配置。

UI 行为要求：

UI 只能修改配置（AIConfig），不得在 UI 内部直接调用 SDK；

点击“保存配置”时写回 config.json；

切换 provider/model 后，新的任务才会使用新配置。

10.2 “测试 AI 设置”按钮
建议在 AI 设置页面提供一个：

[测试 AI 设置] 按钮：

使用当前配置创建 LLMClient；

发送一个非常简单的测试请求（例如“请用一句话回复 OK”）；

将结果（成功/失败及原因）写入日志和/或在 UI 的状态区域显示。

要求：

测试失败时，不崩溃；

至少能提示用户“API key 有问题 / 网络不可用 / 限流”等大类问题。

11. 安全与隐私约束
不在仓库中提交任何真实 API key；

不在日志打印 API key / 完整 Authorization header；

对于字幕内容和 prompt，只在必要时打印简短片段（截断）；

如未来加入本地模型（LocalLLM），同样遵守上述规范。

12. P0 / P1 实现要求（对 IDE 的明确约束）
12.1 P0 阶段（必须完成）
实现：

AIConfig 结构（含 provider、model、base_url、timeout、max_retries、api_keys 等）；

LLMClient 抽象接口；

至少一个具体 provider（例如 OpenAIClient 或 AnthropicClient）；

Provider 工厂函数 create_llm_client(ai_config)；

将 SubtitleTranslator / Summarizer 改造为只依赖 LLMClient，不再直接调用某家 SDK。

不要求：

真正支持多个 provider 之间的自动切换（fallback）；

UI 中暴露全部高级参数（可以先只暴露 provider/model）。

12.2 P1 及以后（增强）
增加更多 provider 实现（如第二家第三家供应商）；

实现简单的策略层（如“按语言选择 provider”，“主 provider 不可用时自动尝试备选 provider”）；

在 UI 中完整呈现更多 AI 配置项；

在必要时实现粗略的 usage / 费用估算。