# YouTube 字幕工具 - 代码精简重构执行文档

> 本文档指导如何精简项目中的冗余代码，预计减少 **1,000-1,300 行**代码。

---

## 📋 重构概览

| 任务 | 精简量 | 优先级 | 风险 |
|------|-------|-------|------|
| 任务1: ai_providers 基类重构 | ~660行 | 🔴 高 | 低 |
| 任务2: language_config_section UI组件 | ~300-400行 | 🔴 高 | 低 |
| 任务3: language_strategy 统一 | ~200-300行 | 🟡 中 | 中 |
| **合计** | **~1,160-1,360行** | | |

---

## 任务1: ai_providers 基类重构

### 1.1 问题分析

当前 `core/ai_providers/` 下的每个 provider 文件都重复实现了以下逻辑：

| 重复代码块 | 行数 | 出现次数 |
|-----------|------|---------|
| API Key 加载逻辑 | ~15行 | 5次 |
| 4个标准属性定义 | ~20行 | 5次 |
| Semaphore 并发控制 | ~5行 | 5次 |
| 重试循环框架 | ~50行 | 5次 |
| 错误分类处理 | ~40行 | 5次 |
| 依赖检查方法 | ~8行 | 5次 |

### 1.2 目标架构

```
改造前:
├── base.py              → 130行 (只有配置数据)
├── anthropic.py         → 200行 (完整实现)
├── openai_compatible.py → 270行 (完整实现)
├── gemini.py            → 210行 (完整实现)
├── local_model.py       → ~200行 (完整实现)
├── google_translate.py  → ~150行 (完整实现)
总计: ~1,160行

改造后:
├── base.py              → 280行 (配置 + 基类)
├── anthropic.py         → 45行 (只有差异部分)
├── openai_compatible.py → 50行 (只有差异部分)
├── gemini.py            → 55行 (只有差异部分)
├── local_model.py       → 60行 (只有差异部分)
├── google_translate.py  → 50行 (只有差异部分)
总计: ~540行
```

### 1.3 新的 base.py 设计

```python
"""
AI 供应商基类和能力配置
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Optional, Sequence, List, Dict, Type
from dataclasses import dataclass

from config.manager import AIConfig
from core.llm_client import LLMResult, LLMUsage, LLMException, LLMErrorType, load_api_key
from core.logger import get_logger, translate_exception

logger = get_logger()


@dataclass
class ProviderCapabilities:
    """供应商能力配置"""
    supports_vision: bool = False
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_json_mode: bool = False
    default_timeout: int = 60
    max_tokens: int = 4096
    context_window: int = 8000


# 保留现有的 PROVIDER_CAPABILITIES 字典...
PROVIDER_CAPABILITIES: Dict[str, ProviderCapabilities] = {
    # ... 保持现有配置不变
}


def get_capabilities(provider: str) -> ProviderCapabilities:
    """获取供应商能力配置"""
    return PROVIDER_CAPABILITIES.get(provider.lower(), ProviderCapabilities())


class BaseLLMClient(ABC):
    """LLM 客户端基类
    
    子类只需实现:
    - provider_name: 供应商名称
    - key_aliases: API Key 的可能名称列表
    - required_package: 需要的 Python 包名
    - _do_request(): 实际的 API 调用
    - _map_exception(): 异常映射 (可选，有默认实现)
    """
    
    # ========== 子类必须定义的类属性 ==========
    provider_name: str = ""  # 例如 "anthropic", "openai"
    key_aliases: List[str] = []  # 例如 ["anthropic", "claude"]
    required_package: str = ""  # 例如 "anthropic"
    
    # ========== 子类可选覆盖的类属性 ==========
    default_max_input_tokens: int = 128000
    default_max_output_tokens: int = 4096
    
    def __init__(self, ai_config: AIConfig):
        """初始化客户端 (通用逻辑，子类不需要重写)"""
        self.ai_config = ai_config
        
        # 1. 加载 API Key (通用)
        self.api_key = self._load_api_key()
        
        # 2. 检查依赖 (通用)
        self._check_dependencies()
        
        # 3. 初始化能力属性 (通用)
        self._supports_vision = self._check_vision_support(ai_config.model)
        self._max_input_tokens = self.default_max_input_tokens
        self._max_output_tokens = self.default_max_output_tokens
        self._max_concurrency = ai_config.max_concurrency
        
        # 4. 创建并发控制 Semaphore (通用)
        self._sem = threading.Semaphore(self._max_concurrency)
    
    # ========== 通用属性 (子类不需要重写) ==========
    
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
    
    # ========== 通用方法 (子类不需要重写) ==========
    
    def _load_api_key(self) -> str:
        """加载 API Key (通用逻辑)"""
        api_key_config = ""
        for key in self.key_aliases:
            config_val = self.ai_config.api_keys.get(key)
            if config_val:
                api_key_config = config_val
                loaded_key = load_api_key(config_val)
                if loaded_key:
                    return loaded_key
        
        raise LLMException(
            f"exception.ai_api_key_not_found:provider={self.provider_name.capitalize()},config={api_key_config}",
            LLMErrorType.AUTH,
        )
    
    def _check_dependencies(self) -> None:
        """检查依赖库 (通用逻辑)"""
        if not self.required_package:
            return
        try:
            __import__(self.required_package)
        except ImportError:
            raise LLMException(
                translate_exception("exception.ai_dependency_missing", library=self.required_package),
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
        """生成响应 (通用重试逻辑)"""
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.ai_config.max_retries + 1):
            try:
                # 使用 Semaphore 进行并发限流
                with self._sem:
                    result = self._do_request(
                        prompt=prompt,
                        system=system,
                        max_tokens=min(
                            max_tokens or self.max_output_tokens,
                            self.max_output_tokens,
                        ),
                        temperature=temperature or 0.3,
                        stop=stop,
                    )
                
                # 记录成功日志
                elapsed = time.time() - start_time
                logger.debug(
                    translate_exception(
                        "log.ai_call_success_detail",
                        provider=self.provider_name.capitalize(),
                        model=self.ai_config.model,
                        elapsed=f"{elapsed:.2f}",
                        tokens=result.usage.total_tokens if result.usage else "N/A",
                    )
                )
                return result
                
            except Exception as e:
                # 映射异常
                error_type, should_retry = self._map_exception(e)
                last_error = LLMException(str(e), error_type)
                
                # 判断是否重试
                if should_retry and attempt < self.ai_config.max_retries:
                    wait_time = 2 ** attempt
                    logger.warning_i18n("log.ai_retry_error", wait_time=wait_time)
                    time.sleep(wait_time)
                    continue
                
                raise last_error
        
        if last_error:
            raise last_error
    
    # ========== 子类可选覆盖的方法 ==========
    
    def _check_vision_support(self, model: str) -> bool:
        """检查模型是否支持视觉 (子类可覆盖)"""
        return False
    
    def _map_exception(self, e: Exception) -> tuple[LLMErrorType, bool]:
        """映射异常类型 (子类可覆盖)
        
        Returns:
            (错误类型, 是否应该重试)
        """
        error_msg = str(e).lower()
        
        if "rate limit" in error_msg or "quota" in error_msg:
            return LLMErrorType.RATE_LIMIT, True
        elif "auth" in error_msg or "api key" in error_msg or "permission" in error_msg:
            return LLMErrorType.AUTH, False
        elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
            return LLMErrorType.NETWORK, True
        elif "safety" in error_msg or "content" in error_msg or "blocked" in error_msg:
            return LLMErrorType.CONTENT, False
        else:
            return LLMErrorType.UNKNOWN, False
    
    # ========== 子类必须实现的方法 ==========
    
    @abstractmethod
    def _do_request(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
        stop: Optional[Sequence[str]],
    ) -> LLMResult:
        """执行实际的 API 请求 (子类必须实现)
        
        注意: 不需要处理重试、并发控制、日志，这些由基类处理
        """
        pass
```

### 1.4 新的 anthropic.py 设计 (示例)

```python
"""
Anthropic Claude 客户端实现
"""

from typing import Optional, Sequence

from core.llm_client import LLMResult, LLMUsage, LLMErrorType
from .base import BaseLLMClient


class AnthropicClient(BaseLLMClient):
    """Anthropic LLM 客户端"""
    
    # 类属性定义
    provider_name = "anthropic"
    key_aliases = ["anthropic", "claude"]
    required_package = "anthropic"
    default_max_input_tokens = 200000
    default_max_output_tokens = 8192
    
    def _check_vision_support(self, model: str) -> bool:
        """Claude 3.x 系列支持视觉"""
        model_lower = model.lower()
        return any(x in model_lower for x in ["opus", "sonnet", "haiku"])
    
    def _do_request(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
        stop: Optional[Sequence[str]],
    ) -> LLMResult:
        """调用 Anthropic API"""
        import anthropic
        
        client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url=self.ai_config.base_url,
            timeout=self.ai_config.timeout_seconds,
        )
        
        response = client.messages.create(
            model=self.ai_config.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        
        # 解析响应
        text = response.content[0].text if response.content else ""
        usage = None
        if response.usage:
            usage = LLMUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )
        
        return LLMResult(
            text=text,
            usage=usage,
            provider=self.provider_name,
            model=self.ai_config.model,
        )
    
    def _map_exception(self, e: Exception) -> tuple[LLMErrorType, bool]:
        """映射 Anthropic 特定异常"""
        from anthropic import (
            RateLimitError,
            AuthenticationError,
            APIConnectionError,
            APIError,
        )
        
        if isinstance(e, RateLimitError):
            return LLMErrorType.RATE_LIMIT, True
        elif isinstance(e, AuthenticationError):
            return LLMErrorType.AUTH, False
        elif isinstance(e, APIConnectionError):
            return LLMErrorType.NETWORK, True
        elif isinstance(e, APIError):
            error_msg = str(e).lower()
            if any(kw in error_msg for kw in ["content", "safety", "policy"]):
                return LLMErrorType.CONTENT, False
            return LLMErrorType.UNKNOWN, True
        else:
            return super()._map_exception(e)
```

### 1.5 其他 provider 的改造模式

#### openai_compatible.py (~50行)

```python
class OpenAICompatibleClient(BaseLLMClient):
    provider_name = "openai"  # 会被 ai_config.provider 覆盖
    key_aliases = ["openai", "openai_compatible"]  # 子类构造时动态添加
    required_package = "openai"
    
    def __init__(self, ai_config: AIConfig):
        # 动态设置 provider_name 和 key_aliases
        self.provider_name = ai_config.provider
        self.key_aliases = [ai_config.provider, "openai", "openai_compatible"]
        super().__init__(ai_config)
    
    def _check_vision_support(self, model: str) -> bool:
        model_lower = model.lower()
        return "vision" in model_lower or "gpt-4o" in model_lower
    
    def _do_request(self, prompt, system, max_tokens, temperature, stop) -> LLMResult:
        import openai
        client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.ai_config.base_url or "https://api.openai.com/v1",
            timeout=self.ai_config.timeout_seconds,
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=self.ai_config.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop,
        )
        # ... 解析响应 (类似 anthropic)
```

#### gemini.py (~55行)

```python
class GeminiClient(BaseLLMClient):
    provider_name = "gemini"
    key_aliases = ["gemini", "google"]
    required_package = "google.generativeai"
    default_max_input_tokens = 128000
    default_max_output_tokens = 8192
    
    def _check_vision_support(self, model: str) -> bool:
        return True  # Gemini 全系列支持视觉
    
    def _do_request(self, prompt, system, max_tokens, temperature, stop) -> LLMResult:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.ai_config.model)
        
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = model.generate_content(
            full_prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                "stop_sequences": stop if stop else None,
            },
        )
        
        return LLMResult(
            text=response.text if hasattr(response, "text") else "",
            usage=None,  # Gemini 不直接提供 token 统计
            provider=self.provider_name,
            model=self.ai_config.model,
        )
```

### 1.6 执行步骤

1. **备份原文件**
   ```bash
   cp -r core/ai_providers core/ai_providers_backup
   ```

2. **修改 base.py**
   - 保留现有的 `ProviderCapabilities` 和 `PROVIDER_CAPABILITIES`
   - 添加 `BaseLLMClient` 抽象基类

3. **逐个改造 provider**（建议顺序）
   - `anthropic.py` (最简单，先改这个验证基类设计)
   - `openai_compatible.py`
   - `gemini.py`
   - `local_model.py`
   - `google_translate.py`

4. **每改一个，运行测试**
   ```bash
   python -c "from core.ai_providers import AnthropicClient; print('OK')"
   ```

5. **全部改完后，运行集成测试**

---

## 任务2: language_config_section UI 组件抽取

### 2.1 问题分析

`ui/pages/url_list_page.py` 和 `ui/pages/channel_page.py` 中有大量重复的语言配置 UI 代码：
- 源语言选择
- 目标语言选择
- 双语模式开关
- 翻译策略选择

### 2.2 目标架构

```
改造前:
├── url_list_page.py     → ~850行 (包含语言配置 UI)
├── channel_page.py      → ~700行 (包含语言配置 UI，重复!)
总计: ~1,550行

改造后:
├── components/
│   └── language_config_section.py → ~200行 (提取的公共组件)
├── url_list_page.py     → ~650行 (使用组件)
├── channel_page.py      → ~500行 (使用组件)
总计: ~1,350行
```

### 2.3 新组件设计

```python
# ui/components/language_config_section.py

"""
语言配置组件
可复用于 url_list_page 和 channel_page
"""

import customtkinter as ctk
from typing import Callable, Optional, List
from ui.i18n import get_text


class LanguageConfigSection(ctk.CTkFrame):
    """语言配置区域组件
    
    包含:
    - 源语言选择
    - 目标语言选择 (多选)
    - 摘要语言选择
    - 双语模式开关
    - 翻译策略选择
    """
    
    def __init__(
        self,
        parent,
        on_config_changed: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(parent, **kwargs)
        self.on_config_changed = on_config_changed
        self._create_widgets()
    
    def _create_widgets(self):
        """创建所有语言配置控件"""
        # 源语言
        self.source_lang_label = ctk.CTkLabel(
            self, text=get_text("source_language")
        )
        self.source_lang_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        self.source_lang_combo = ctk.CTkComboBox(
            self,
            values=self._get_language_options(),
            command=self._on_change
        )
        self.source_lang_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        # 目标语言 (多选)
        self.target_lang_label = ctk.CTkLabel(
            self, text=get_text("target_languages")
        )
        self.target_lang_label.grid(row=1, column=0, sticky="w", padx=5, pady=5)
        
        # ... 其他控件
        
        # 双语模式
        self.bilingual_var = ctk.BooleanVar(value=False)
        self.bilingual_switch = ctk.CTkSwitch(
            self,
            text=get_text("bilingual_mode"),
            variable=self.bilingual_var,
            command=self._on_change
        )
        self.bilingual_switch.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        
        # 翻译策略
        self.strategy_label = ctk.CTkLabel(
            self, text=get_text("translation_strategy")
        )
        self.strategy_label.grid(row=4, column=0, sticky="w", padx=5, pady=5)
        
        self.strategy_combo = ctk.CTkComboBox(
            self,
            values=[
                get_text("strategy_ai_first"),
                get_text("strategy_official_first"),
                get_text("strategy_official_only"),
            ],
            command=self._on_change
        )
        self.strategy_combo.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    
    def _get_language_options(self) -> List[str]:
        """获取语言选项列表"""
        return [
            "auto", "en", "zh-CN", "zh-TW", "ja", "ko",
            "de", "fr", "es", "pt", "ru", "it"
        ]
    
    def _on_change(self, *args):
        """配置变更回调"""
        if self.on_config_changed:
            self.on_config_changed(self.get_config())
    
    def get_config(self) -> dict:
        """获取当前配置"""
        return {
            "source_language": self.source_lang_combo.get(),
            "target_languages": self._get_selected_targets(),
            "summary_language": self.summary_lang_combo.get(),
            "bilingual_mode": self.bilingual_var.get(),
            "translation_strategy": self._get_strategy_value(),
        }
    
    def set_config(self, config: dict):
        """设置配置"""
        if "source_language" in config:
            self.source_lang_combo.set(config["source_language"])
        if "bilingual_mode" in config:
            self.bilingual_var.set(config["bilingual_mode"])
        # ... 其他设置
    
    def _get_selected_targets(self) -> List[str]:
        """获取选中的目标语言"""
        # 实现多选逻辑
        pass
    
    def _get_strategy_value(self) -> str:
        """获取翻译策略值"""
        text = self.strategy_combo.get()
        if text == get_text("strategy_ai_first"):
            return "AI_FIRST"
        elif text == get_text("strategy_official_first"):
            return "OFFICIAL_FIRST"
        else:
            return "OFFICIAL_ONLY"
```

### 2.4 页面使用示例

```python
# ui/pages/url_list_page.py (改造后)

from ui.components.language_config_section import LanguageConfigSection

class URLListPage(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._create_widgets()
    
    def _create_widgets(self):
        # URL 输入区域 (保持不变)
        self.url_input_section = self._create_url_input_section()
        
        # 语言配置区域 (使用公共组件)
        self.language_config = LanguageConfigSection(
            self,
            on_config_changed=self._on_language_config_changed
        )
        self.language_config.pack(fill="x", padx=10, pady=10)
        
        # 运行按钮区域 (保持不变)
        self.run_section = self._create_run_section()
    
    def _on_language_config_changed(self, config: dict):
        """语言配置变更处理"""
        # 更新内部状态
        self.current_language_config = config
    
    def get_full_config(self) -> dict:
        """获取完整配置"""
        return {
            "urls": self._get_urls(),
            **self.language_config.get_config(),
        }
```

### 2.5 执行步骤

1. **创建组件目录**
   ```bash
   mkdir -p ui/components
   touch ui/components/__init__.py
   ```

2. **创建 language_config_section.py**
   - 从 `url_list_page.py` 中提取语言配置相关代码
   - 封装为独立组件

3. **改造 url_list_page.py**
   - 删除重复的语言配置代码
   - 引入 `LanguageConfigSection` 组件

4. **改造 channel_page.py**
   - 同样引入 `LanguageConfigSection` 组件

5. **测试两个页面功能是否正常**

---

## 任务3: language_strategy 统一

### 3.1 问题分析

`core/downloader.py` 和 `core/translator.py` 中有重复的语言处理逻辑：

| 重复代码 | downloader.py | translator.py |
|---------|--------------|---------------|
| `lang_matches()` 函数 | 有 | 有 (完全相同) |
| `COMMON_LANGUAGES` 列表 | 有 | 有 (完全相同) |
| 源语言选择算法 | 有 | 有 (类似) |

### 3.2 目标架构

```
改造前:
├── downloader.py  → ~900行 (包含语言逻辑)
├── translator.py  → ~770行 (包含语言逻辑，重复!)
总计: ~1,670行

改造后:
├── language_strategy.py → ~150行 (公共语言逻辑)
├── downloader.py        → ~750行 (使用公共模块)
├── translator.py        → ~620行 (使用公共模块)
总计: ~1,520行
```

### 3.3 新模块设计

```python
# core/language_strategy.py

"""
语言策略模块
统一处理语言代码匹配、源语言选择等逻辑
"""

from typing import Optional, List, Dict
from pathlib import Path


# 常见语言列表（按翻译质量优先级排序）
COMMON_LANGUAGES = [
    "en", "en-US",
    "de", "de-DE",
    "ja", "ja-JP",
    "es", "es-ES",
    "fr", "fr-FR",
    "pt", "pt-PT",
    "ru", "ru-RU",
    "ko", "ko-KR",
]


def lang_matches(lang1: str, lang2: str) -> bool:
    """检查两个语言代码是否匹配
    
    特殊处理:
    - zh-CN 和 zh-TW 不互相匹配（需要精确匹配）
    - 其他语言使用主语言代码匹配（如 en-US 匹配 en）
    
    Args:
        lang1: 第一个语言代码
        lang2: 第二个语言代码
    
    Returns:
        是否匹配
    """
    if lang1 == lang2:
        return True
    
    # 特殊处理：zh-CN 和 zh-TW 不互相匹配
    lang1_lower = lang1.lower()
    lang2_lower = lang2.lower()
    zh_cn_variants = ["zh-cn", "zh_cn"]
    zh_tw_variants = ["zh-tw", "zh_tw"]
    
    if (lang1_lower in zh_cn_variants and lang2_lower in zh_tw_variants) or \
       (lang1_lower in zh_tw_variants and lang2_lower in zh_cn_variants):
        return False
    
    # 其他语言：提取主语言代码进行匹配
    main1 = lang1.split("-")[0].split("_")[0].lower()
    main2 = lang2.split("-")[0].split("_")[0].lower()
    return main1 == main2


def get_main_language_code(lang: str) -> str:
    """获取主语言代码
    
    Args:
        lang: 完整语言代码 (如 "en-US", "zh-CN")
    
    Returns:
        主语言代码 (如 "en", "zh")
    """
    return lang.split("-")[0].split("_")[0].lower()


def is_chinese_variant(lang: str) -> bool:
    """检查是否是中文变体"""
    return get_main_language_code(lang) == "zh"


def find_best_source_language(
    available_languages: List[str],
    manual_languages: Optional[List[str]] = None,
    auto_languages: Optional[List[str]] = None,
    exclude_language: Optional[str] = None,
) -> Optional[str]:
    """在可用语言中找到最佳源语言
    
    优先级:
    1. 常见语言中的人工字幕
    2. 常见语言中的自动字幕
    3. 其他人工字幕
    4. 其他自动字幕
    
    Args:
        available_languages: 可用的语言列表
        manual_languages: 人工字幕语言列表
        auto_languages: 自动字幕语言列表
        exclude_language: 要排除的语言（通常是目标语言）
    
    Returns:
        最佳源语言代码，如果没有则返回 None
    """
    manual_languages = manual_languages or []
    auto_languages = auto_languages or []
    
    def should_exclude(lang: str) -> bool:
        if not exclude_language:
            return False
        return lang_matches(lang, exclude_language)
    
    # 优先级1: 常见语言中的人工字幕
    for common_lang in COMMON_LANGUAGES:
        for lang in manual_languages:
            if lang_matches(lang, common_lang) and not should_exclude(lang):
                if lang in available_languages:
                    return lang
    
    # 优先级2: 常见语言中的自动字幕
    for common_lang in COMMON_LANGUAGES:
        for lang in auto_languages:
            if lang_matches(lang, common_lang) and not should_exclude(lang):
                if lang in available_languages:
                    return lang
    
    # 优先级3: 其他人工字幕
    for lang in manual_languages:
        if not should_exclude(lang) and lang in available_languages:
            is_common = any(lang_matches(lang, c) for c in COMMON_LANGUAGES)
            if not is_common:
                return lang
    
    # 优先级4: 其他自动字幕
    for lang in auto_languages:
        if not should_exclude(lang) and lang in available_languages:
            is_common = any(lang_matches(lang, c) for c in COMMON_LANGUAGES)
            if not is_common:
                return lang
    
    return None


class LanguageSelector:
    """语言选择器
    
    封装源语言选择的完整逻辑，可被 downloader 和 translator 复用
    """
    
    def __init__(
        self,
        manual_languages: Optional[List[str]] = None,
        auto_languages: Optional[List[str]] = None,
    ):
        self.manual_languages = manual_languages or []
        self.auto_languages = auto_languages or []
    
    def select_source_for_translation(
        self,
        official_translations: Dict[str, Path],
        original_path: Optional[Path],
        target_language: str,
    ) -> Optional[Path]:
        """选择用于翻译的源字幕文件
        
        Args:
            official_translations: 已下载的官方翻译字幕 {语言代码: 路径}
            original_path: 原始字幕路径
            target_language: 目标语言
        
        Returns:
            源字幕文件路径
        """
        available_languages = list(official_translations.keys())
        
        # 使用通用算法找最佳源语言
        best_lang = find_best_source_language(
            available_languages=available_languages,
            manual_languages=self.manual_languages,
            auto_languages=self.auto_languages,
            exclude_language=target_language,
        )
        
        if best_lang:
            path = official_translations.get(best_lang)
            if path and path.exists():
                return path
        
        # 回退到原始字幕
        if original_path and original_path.exists():
            return original_path
        
        return None
```

### 3.4 改造 translator.py

```python
# 改造前 (translator.py 中的重复代码):
# - COMMON_LANGUAGES 列表 (删除)
# - lang_matches() 函数 (删除)
# - _select_source_subtitle() 方法中的复杂逻辑 (简化)

# 改造后:
from core.language_strategy import (
    lang_matches,
    COMMON_LANGUAGES,
    LanguageSelector,
)

class SubtitleTranslator:
    def __init__(self, llm, language_config):
        self.llm = llm
        self.language_config = language_config
        self._language_selector = None  # 延迟初始化
    
    def _select_source_subtitle(
        self,
        download_result: Dict,
        detection_result,
        target_language: str,
    ) -> Optional[Path]:
        """选择源字幕（简化版，使用公共模块）"""
        # 初始化语言选择器
        if self._language_selector is None:
            self._language_selector = LanguageSelector(
                manual_languages=detection_result.manual_languages,
                auto_languages=detection_result.auto_languages,
            )
        
        return self._language_selector.select_source_for_translation(
            official_translations=download_result.get("official_translations", {}),
            original_path=download_result.get("original"),
            target_language=target_language,
        )
```

### 3.5 执行步骤

1. **创建 language_strategy.py**
   ```bash
   touch core/language_strategy.py
   ```

2. **从 translator.py 提取公共代码**
   - `COMMON_LANGUAGES`
   - `lang_matches()`
   - 源语言选择逻辑

3. **改造 translator.py**
   - 删除重复代码
   - 引入 `language_strategy` 模块

4. **改造 downloader.py**
   - 删除重复代码
   - 引入 `language_strategy` 模块

5. **测试翻译和下载功能**

---

## 📋 执行顺序建议

```
Week 1: 任务1 - ai_providers 重构
├── Day 1-2: 设计并实现 BaseLLMClient
├── Day 3: 改造 anthropic.py (验证设计)
├── Day 4: 改造 openai_compatible.py, gemini.py
├── Day 5: 改造 local_model.py, google_translate.py
└── Day 6-7: 测试和修复

Week 2: 任务2 + 任务3
├── Day 1-2: 任务2 - language_config_section UI 组件
├── Day 3-4: 任务3 - language_strategy 统一
└── Day 5-7: 集成测试和修复
```

---

## ⚠️ 注意事项

1. **每完成一个小改动就测试**
   - 不要一次改太多
   - 保持代码始终可运行

2. **保留备份**
   ```bash
   git commit -m "Before refactoring" 
   # 或手动备份文件夹
   ```

3. **保持接口兼容**
   - `factory.py` 和 `registry.py` 不需要改
   - 对外的类名和方法名保持不变

4. **测试重点**
   - AI 调用是否正常
   - 重试逻辑是否生效
   - 错误信息是否正确显示
   - UI 语言配置是否正常保存/读取

---

## 📊 预期成果

| 指标 | 改造前 | 改造后 | 变化 |
|------|-------|-------|-----|
| 总代码量 | ~12,500行 | ~11,200行 | -1,300行 (10%) |
| ai_providers | ~1,160行 | ~540行 | -620行 |
| UI pages | ~1,550行 | ~1,350行 | -200行 |
| downloader + translator | ~1,670行 | ~1,520行 | -150行 |
| 新增 language_strategy | 0 | ~150行 | +150行 |
| 新增 UI components | 0 | ~200行 | +200行 |

**净减少: ~1,100-1,300 行代码**
