# yt-subtitle-v3.1 重构方案

> | v3.1 | 2025-12-16 | 整合 Grok 最终审计反馈，完善 Gemini 配置、长内容优化等细节 |
> **生成日期**: 2025年12月16日  
> **讨论来源**: Claude + GPT + Grok + Gemini 四方三轮讨论整合  
> **状态**: ✅ 已定稿，可执行

---

## 目录

1. [项目现状与问题分析](#一项目现状与问题分析)
2. [改进目标](#二改进目标)
3. [大文件拆分方案](#三大文件拆分方案)
4. [日志国际化方案](#四日志国际化方案)
5. [AI 供应商适配方案](#五ai-供应商适配方案)
6. [执行计划](#六执行计划)
7. [风险控制](#七风险控制)
8. [范围外内容](#八范围外内容明确不做)
9. [附录：核心代码示例](#九附录核心代码示例)

---

## 一、项目现状与问题分析

### 1.1 项目概述

yt-subtitle-v2 是一个 YouTube 视频字幕下载、翻译、摘要工具，使用 CustomTkinter 构建 GUI 界面。

### 1.2 当前问题

| 问题类别 | 具体表现 | 影响 |
|---------|---------|------|
| **大文件问题** | 7个文件超过800行，最大1391行 | 难维护、难测试、难扩展 |
| **职责混杂** | ai_providers.py 里4种AI客户端挤在一起 | 改一个容易影响另一个 |
| **日志国际化缺失** | UI切英文后，日志/异常消息仍显示中文 | 用户体验不一致 |
| **新旧代码混杂** | pipeline.py 里新旧流程混在一起 | 容易出bug |
| **循环依赖风险** | logger 和 i18n_manager 互相调用 | 可能导致启动死锁 |
| **本地AI不稳定** | Ollama/LM Studio 缺少专门处理 | 连接失败时报错晦涩 |

### 1.3 超大文件清单

| 文件路径 | 行数 | 主要问题 | 拆分优先级 |
|---------|------|---------|-----------|
| core/ai_providers.py | 1391 | 4种客户端混杂 | P0 最高 |
| core/staged_pipeline.py | 1345 | 调度+处理器混杂 | P0 最高 |
| core/output.py | 1155 | 多种输出格式混杂 | P1 高 |
| core/pipeline.py | 1045 | 新旧流程混杂 | P1 高 |
| ui/main_window.py | 977 | GUI职责分散 | P2 中 |
| ui/pages/network_settings_page.py | 913 | 功能区域复杂 | P2 中 |
| ui/business_logic.py | 881 | 处理职责多 | P2 中 |

---

## 二、改进目标

| 目标 | 具体指标 |
|------|---------|
| **代码可维护性** | 单文件不超过 500 行，单一职责 |
| **国际化完整性** | UI、日志、异常消息全部支持中英文切换 |
| **AI扩展性** | 新增供应商只需添加文件，无需修改现有代码 |
| **本地AI稳定性** | 友好的错误提示，自动检测服务状态 |
| **测试可行性** | 各模块可独立单元测试 |

---

## 三、大文件拆分方案

### 3.1 拆分原则

1. **模块 Package 化**：将大文件转换为 Python Package（目录 + `__init__.py`）
2. **向后兼容**：通过 `__init__.py` 重新导出，保持原有导入路径可用
3. **单一职责**：每个文件只负责一个明确的功能
4. **显式依赖**：闭包改为参数传递，便于测试和维护
5. **渐进式执行**：每拆一个模块就运行测试，小步前进

### 3.2 拆分优先级和顺序

```
Week 1: ai_providers.py（P0 最高优先级）
   ↓
Week 2: staged_pipeline.py（P0 最高优先级）
   ↓
Week 3-4: output.py + pipeline.py（P1 高优先级）
   ↓
Week 5-6: UI 层文件（P2 中优先级）
```

### 3.3 ai_providers.py 拆分方案

#### 3.3.1 拆分前结构
```
core/
└── ai_providers.py  (1391行，包含所有AI客户端)
```

#### 3.3.2 拆分后结构
```
core/ai_providers/
├── __init__.py           # 重导出所有类，保持向后兼容
├── base.py               # LLMClient 基类 + PROVIDER_CAPABILITIES
├── factory.py            # create_llm_client() 工厂函数
├── registry.py           # _LLM_REGISTRY + _init_registry()
├── openai_compatible.py  # OpenAI 兼容客户端（~300行）
├── local_model.py        # 本地模型专用客户端（新增）
├── gemini.py             # Gemini 原生客户端（~165行）
├── anthropic.py          # Anthropic 客户端（~190行）
└── google_translate.py   # Google 翻译客户端（~680行）
```

#### 3.3.3 各文件职责说明

| 文件 | 职责 | 预估行数 |
|------|------|---------|
| `__init__.py` | 导出所有公开类和函数，保持 `from core.ai_providers import X` 可用 | ~30 |
| `base.py` | 定义 LLMClient 抽象基类、PROVIDER_CAPABILITIES 能力配置 | ~100 |
| `factory.py` | create_llm_client() 工厂函数，根据配置创建对应客户端 | ~50 |
| `registry.py` | 供应商注册表，支持动态注册新供应商 | ~40 |
| `openai_compatible.py` | OpenAI 兼容协议客户端，支持 DeepSeek/Kimi/Qwen 等 | ~300 |
| `local_model.py` | 本地模型专用，继承 OpenAI 兼容，添加心跳检测、预热、长超时 | ~150 |
| `gemini.py` | Google Gemini 原生客户端 | ~165 |
| `anthropic.py` | Anthropic Claude 客户端 | ~190 |
| `google_translate.py` | Google 翻译客户端（免费版） | ~400 |

#### 3.3.4 向后兼容处理

```python
# core/ai_providers/__init__.py

from .base import LLMClient, PROVIDER_CAPABILITIES, get_capabilities
from .factory import create_llm_client
from .registry import register_provider, get_provider, list_providers
from .openai_compatible import OpenAICompatibleClient
from .local_model import LocalModelClient
from .gemini import GeminiClient
from .anthropic import AnthropicClient
from .google_translate import GoogleTranslateClient

__all__ = [
    # 基类和工具
    "LLMClient",
    "PROVIDER_CAPABILITIES",
    "get_capabilities",
    "create_llm_client",
    "register_provider",
    "get_provider",
    "list_providers",
    # 客户端类
    "OpenAICompatibleClient",
    "LocalModelClient", 
    "GeminiClient",
    "AnthropicClient",
    "GoogleTranslateClient",
]

# 原有导入方式继续有效：
# from core.ai_providers import create_llm_client
# from core.ai_providers import OpenAICompatibleClient
```

#### 配置兼容映射

用户现有 `config.json` 中的 `provider` 字段需要兼容：
```python
# core/ai_providers/registry.py

# 旧名称 -> 新客户端类的映射
_LLM_REGISTRY = {
    # 标准名称
    "openai": OpenAICompatibleClient,
    "gemini": GeminiClient,
    "anthropic": AnthropicClient,
    "google_translate": GoogleTranslateClient,
    
    # 本地模型（自动路由到专用客户端）
    "ollama": LocalModelClient,
    "lm_studio": LocalModelClient,
    "local": LocalModelClient,
    
    # OpenAI 兼容供应商（别名）
    "deepseek": OpenAICompatibleClient,
    "kimi": OpenAICompatibleClient,
    "moonshot": OpenAICompatibleClient,
    "qwen": OpenAICompatibleClient,
    "glm": OpenAICompatibleClient,
    "groq": OpenAICompatibleClient,
}

```

### 3.4 staged_pipeline.py 拆分方案

#### 3.4.1 拆分前结构
```
core/
└── staged_pipeline.py  (1345行，包含调度器和所有处理器)
```

#### 3.4.2 拆分后结构
```
core/staged_pipeline/
├── __init__.py           # 重导出，保持向后兼容
├── scheduler.py          # 主调度器（原 StagedPipeline 类，只负责编排）
├── data_types.py         # StageData、StageResult 等数据类
├── queue.py              # StageQueue 队列管理
└── processors/           # 各阶段处理器
    ├── __init__.py
    ├── detect.py         # 检测处理器
    ├── download.py       # 下载处理器
    ├── translate.py      # 翻译处理器
    ├── summarize.py      # 摘要处理器
    └── output.py         # 输出处理器
```

#### 3.4.3 依赖注入改造

**改造前（闭包隐式依赖）**：
```python
class StagedPipeline:
    def _create_download_processor(self):
        def processor(data):
            # 隐式依赖 self.config, self.cookie_manager
            config = self.config
            cookie = self.cookie_manager
            # ... 处理逻辑
        return processor
```

**改造后（参数显式注入）**：
```python
# core/staged_pipeline/processors/download.py

class DownloadProcessor:
    """下载处理器"""
    
    def __init__(self, config, cookie_manager, logger):
        self.config = config
        self.cookie_manager = cookie_manager
        self.logger = logger
    
    def process(self, data: StageData) -> StageResult:
        """执行下载处理"""
        # ... 处理逻辑
        pass

# core/staged_pipeline/scheduler.py

class StagedPipeline:
    def __init__(self, config, cookie_manager, ...):
        self.config = config
        # 创建处理器时显式传入依赖
        self.download_processor = DownloadProcessor(
            config=config,
            cookie_manager=cookie_manager,
            logger=self.logger
        )
```

### 3.5 其他文件拆分方案（P1/P2）

#### 3.5.1 output.py 拆分
```
core/output/
├── __init__.py
├── writer.py             # OutputWriter 主类
└── formats/
    ├── __init__.py
    ├── subtitle.py       # 字幕输出（SRT、VTT、ASS）
    ├── summary.py        # 摘要输出（TXT、MD）
    ├── metadata.py       # 元数据输出（JSON）
    └── archive.py        # 打包输出（ZIP）
```

#### 3.5.2 pipeline.py 拆分
```
core/pipeline/
├── __init__.py
├── base.py               # 基础流水线类
├── single_video.py       # 单视频处理
├── batch.py              # 批量处理
├── legacy.py             # 旧版流程（兼容）
└── utils.py              # 工具函数
```

#### 3.5.3 UI 层拆分（参考）
```
ui/
├── main_window/
│   ├── __init__.py
│   ├── window.py         # 主窗口类
│   ├── page_manager.py   # 页面管理
│   └── event_handlers.py # 事件处理
├── business_logic/
│   ├── __init__.py
│   ├── processor.py      # 主处理器
│   └── handlers/
│       ├── detection.py
│       ├── download.py
│       └── translation.py
```

---

## 四、日志国际化方案

### 4.1 技术选型

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 翻译文件格式 | JSON | 复用现有 i18n_manager，不引入新体系 |
| 实现方式 | Logger 内部自动翻译 | 一劳永逸，业务代码改动小 |
| 循环依赖处理 | 延迟导入（lazy import） | 避免 logger ↔ i18n_manager 死锁 |
| 命名空间 | 分层结构（ui/log/exception） | 避免键名冲突 |

### 4.2 JSON 翻译文件结构

#### 4.2.1 中文版 (zh_CN.json)

```json
{
  "ui": {
    "start_btn": "开始",
    "stop_btn": "停止",
    "settings": "设置"
  },
  "log": {
    "video_detected": "检测到视频: {video_id}",
    "video_no_subtitle": "视频无字幕: {video_id}",
    "video_has_subtitle": "视频有字幕: {video_id} ({lang})",
    
    "download_start": "开始下载: {video_id}",
    "download_complete": "下载完成: {video_id}",
    "download_failed": "下载失败: {video_id} - {error}",
    
    "translation_start": "开始翻译: {video_id}",
    "translation_complete": "翻译完成: {video_id}",
    "translation_failed": "翻译失败: {video_id} - {error}",
    
    "summary_start": "开始生成摘要: {video_id}",
    "summary_complete": "摘要生成完成: {video_id}",
    
    "task_progress": "处理进度: {current}/{total} ({percent}%)",
    "task_success": "成功: {count} 个",
    "task_failed": "失败: {count} 个",
    "task_cancelled": "任务已取消",
    
    "cookie_configured": "Cookie 已配置",
    "cookie_not_configured": "Cookie 未配置",
    "proxy_configured": "代理已配置",
    "proxy_valid": "代理有效: {proxy}",
    "proxy_invalid": "代理无效: {proxy}",
    
    "api_call_success": "{provider} API 调用成功，耗时 {elapsed}s",
    "api_call_failed": "{provider} API 调用失败: {error}",
    
    "network_error": "网络错误: {error}",
    "auth_error": "认证失败: {error}",
    "rate_limit": "API 频率限制，{seconds}秒后重试",
    "timeout_error": "请求超时: {error}",
    
    "local_model_warmup": "本地模型预热中...",
    "local_model_ready": "本地模型就绪: {model}",
    "local_model_check_failed": "本地模型服务检测失败",
    
    "init_complete": "初始化完成",
    "config_loaded": "配置已加载"
  },
  "exception": {
    "download_failed": "下载失败: {reason}",
    "translation_failed": "翻译失败: {reason}",
    "summary_failed": "摘要生成失败: {reason}",
    "api_auth_failed": "API 认证失败，请检查 API Key",
    "network_failed": "网络连接失败，请检查网络设置",
    "local_model_not_running": "本地模型服务未启动，请先运行 Ollama 或 LM Studio",
    "file_not_found": "文件未找到: {path}",
    "invalid_config": "配置无效: {detail}"
  }
}
```

#### 4.2.2 英文版 (en_US.json)

```json
{
  "ui": {
    "start_btn": "Start",
    "stop_btn": "Stop",
    "settings": "Settings"
  },
  "log": {
    "video_detected": "Video detected: {video_id}",
    "video_no_subtitle": "No subtitle available: {video_id}",
    "video_has_subtitle": "Subtitle found: {video_id} ({lang})",
    
    "download_start": "Starting download: {video_id}",
    "download_complete": "Download complete: {video_id}",
    "download_failed": "Download failed: {video_id} - {error}",
    
    "translation_start": "Starting translation: {video_id}",
    "translation_complete": "Translation complete: {video_id}",
    "translation_failed": "Translation failed: {video_id} - {error}",
    
    "summary_start": "Generating summary: {video_id}",
    "summary_complete": "Summary complete: {video_id}",
    
    "task_progress": "Progress: {current}/{total} ({percent}%)",
    "task_success": "Succeeded: {count}",
    "task_failed": "Failed: {count}",
    "task_cancelled": "Task cancelled",
    
    "cookie_configured": "Cookie configured",
    "cookie_not_configured": "Cookie not configured",
    "proxy_configured": "Proxy configured",
    "proxy_valid": "Proxy valid: {proxy}",
    "proxy_invalid": "Proxy invalid: {proxy}",
    
    "api_call_success": "{provider} API call succeeded, took {elapsed}s",
    "api_call_failed": "{provider} API call failed: {error}",
    
    "network_error": "Network error: {error}",
    "auth_error": "Authentication failed: {error}",
    "rate_limit": "Rate limited, retry in {seconds}s",
    "timeout_error": "Request timeout: {error}",
    
    "local_model_warmup": "Warming up local model...",
    "local_model_ready": "Local model ready: {model}",
    "local_model_check_failed": "Local model service check failed",
    
    "init_complete": "Initialization complete",
    "config_loaded": "Configuration loaded"
  },
  "exception": {
    "download_failed": "Download failed: {reason}",
    "translation_failed": "Translation failed: {reason}",
    "summary_failed": "Summary generation failed: {reason}",
    "api_auth_failed": "API authentication failed, please check your API key",
    "network_failed": "Network connection failed, please check network settings",
    "local_model_not_running": "Local model service not running, please start Ollama or LM Studio first",
    "file_not_found": "File not found: {path}",
    "invalid_config": "Invalid configuration: {detail}"
  }
}
```

### 4.3 Logger 修改方案
class Logger:
    # ... 现有方法 ...
    
    def info_i18n(self, key: str, **kwargs) -> None:
        """显式国际化日志（推荐用于关键路径）
        
        与 info() 的区别：不做启发式判断，直接翻译 key
        """
        message = translate_log(key, **kwargs)
        self._log("INFO", message)
    
    def error_i18n(self, key: str, **kwargs) -> None:
        """显式国际化错误日志"""
        message = translate_log(key, **kwargs)
        self._log("ERROR", message)

> **使用建议**：
> - P0/P1 关键路径（用户直接看到的日志）：优先使用 `logger.info_i18n("key", ...)`
> - 其他日志：可继续使用 `logger.info("key", ...)`（启发式判断）

#### 4.3.1 核心代码

```python
# core/logger.py

"""
统一日志系统（支持国际化）
"""
import logging
import sys
import re
from pathlib import Path
from typing import Optional, Callable, List
from datetime import datetime
from threading import Lock
from logging.handlers import RotatingFileHandler

# ============ 国际化支持 ============

_i18n_module = None
_i18n_lock = Lock()


def _get_i18n():
    """延迟加载 i18n 模块，避免循环依赖"""
    global _i18n_module
    if _i18n_module is None:
        with _i18n_lock:
            if _i18n_module is None:
                try:
                    from ui import i18n_manager
                    _i18n_module = i18n_manager
                except ImportError:
                    _i18n_module = False  # 标记为不可用（CLI模式）
    return _i18n_module if _i18n_module else None


def translate_log(key: str, **kwargs) -> str:
    """翻译日志消息
    
    Args:
        key: 翻译键（不含 log. 前缀）
        **kwargs: 格式化参数
    
    Returns:
        翻译后的消息
    
    Example:
        >>> translate_log("video_detected", video_id="abc123")
        "检测到视频: abc123"  # 中文环境
        "Video detected: abc123"  # 英文环境
    """
    i18n = _get_i18n()
    
    if i18n is None:
        # i18n 不可用，返回原 key
        if kwargs:
            try:
                return f"{key}: {kwargs}"
            except:
                pass
        return key
    
    try:
        # 从 log 命名空间获取翻译
        full_key = f"log.{key}" if not key.startswith("log.") else key
        text = i18n.t(full_key, default=key)
        
        # 格式化参数
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text
    except Exception:
        return key


def translate_exception(key: str, **kwargs) -> str:
    """翻译异常消息"""
    i18n = _get_i18n()
    
    if i18n is None:
        return key
    
    try:
        full_key = f"exception.{key}" if not key.startswith("exception.") else key
        text = i18n.t(full_key, default=key)
        
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text
    except Exception:
        return key


class Logger:
    """统一日志管理器（支持国际化）"""
    
    # 日志翻译键的白名单参数
    FORMAT_PARAMS = {
        'video_id', 'error', 'path', 'count', 'total', 'percent',
        'model', 'provider', 'url', 'lang', 'source', 'target',
        'channel', 'playlist', 'success', 'elapsed', 'tokens',
        'proxy', 'current', 'seconds', 'reason', 'detail'
    }
    
    def __init__(self, name: str = "yt-subtitle-v2", ...):
        # ... 初始化代码 ...
        pass
    
    def _translate_if_key(self, message: str, **kwargs) -> str:
        """如果 message 是翻译键，则翻译"""
        # 判断是否为翻译键：全 ASCII、无空格开头、无中文
        if (message.isascii() and 
            not message.startswith(" ") and
            "_" in message and
            not any('\u4e00' <= c <= '\u9fff' for c in message)):
            
            # 分离格式化参数
            format_kwargs = {k: v for k, v in kwargs.items() if k in self.FORMAT_PARAMS}
            return translate_log(message, **format_kwargs)
        
        return message
    
    def info(self, message: str, **kwargs) -> None:
        """记录信息日志"""
        translated = self._translate_if_key(message, **kwargs)
        self._log("INFO", translated, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """记录警告日志"""
        translated = self._translate_if_key(message, **kwargs)
        self._log("WARNING", translated, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """记录错误日志"""
        translated = self._translate_if_key(message, **kwargs)
        self._log("ERROR", translated, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """记录调试日志（不翻译）"""
        self._log("DEBUG", message, **kwargs)
```

#### 4.3.2 日志脱敏与敏感字段保护（P1）

> 背景：日志会写入文件/控制台/GUI 面板，建议对 API Key、Cookie、Authorization、Proxy Credential 等进行统一脱敏，避免误打到日志中。  
> 实现方式：使用 Python 标准库 logging 的 Filter/Formatter 机制在输出前做替换/遮罩。

**建议规则：**
- 命中敏感字段（如 `api_key`、`authorization`、`cookie`、`set-cookie`、`proxy_password`）→ 统一替换为 `***`
- URL 若包含 query 参数里疑似 token → 只保留域名与 path，query 置空

（落地时建议：Filter 只做“替换”，不要直接丢弃整条日志，避免排障困难。）


### 4.4 异常国际化方案

```python
# core/exceptions.py

"""
可翻译的应用异常
"""
from core.logger import translate_exception


class AppException(Exception):
    """应用异常基类，支持国际化"""
    
    def __init__(self, key: str, **kwargs):
        """
        Args:
            key: 翻译键（不含 exception. 前缀）
            **kwargs: 格式化参数
        """
        self.key = key
        self.kwargs = kwargs
        super().__init__(key)
    
    def get_message(self) -> str:
        """获取翻译后的错误消息"""
        return translate_exception(self.key, **self.kwargs)
    
    def __str__(self) -> str:
        return self.get_message()


class DownloadError(AppException):
    """下载错误"""
    def __init__(self, reason: str):
        super().__init__("download_failed", reason=reason)


class TranslationError(AppException):
    """翻译错误"""
    def __init__(self, reason: str):
        super().__init__("translation_failed", reason=reason)


class LocalModelError(AppException):
    """本地模型错误"""
    def __init__(self):
        super().__init__("local_model_not_running")


class AuthError(AppException):
    """认证错误"""
    def __init__(self):
        super().__init__("api_auth_failed")


class NetworkError(AppException):
    """网络错误"""
    def __init__(self):
        super().__init__("network_failed")

```

#### UI 捕获异常时的修改

UI 代码中捕获异常时，需要使用翻译后的消息：
```python
# 修改前
except Exception as e:
    self.log_panel.append_log("ERROR", str(e))

# 修改后
except Exception as e:
    error_msg = e.get_message() if hasattr(e, 'get_message') else str(e)
    self.log_panel.append_log("ERROR", error_msg)
```

此修改应在 **Phase 4（Week 4）** 执行。


### 4.5 业务代码迁移示例

#### 迁移前
```python
logger.info(f"检测到视频: {video_id}")
logger.info(f"处理进度: {current}/{total}")
logger.error(f"下载失败: {video_id} - {str(e)}")

if not service_available:
    raise Exception("本地模型服务未启动，请先运行 Ollama")
```

#### 迁移后
```python
logger.info_i18n("video_detected", video_id=video_id)
logger.info_i18n("task_progress", current=current, total=total, percent=int(current / total * 100))
logger.error_i18n("download_failed", video_id=video_id, error=str(e))

if not service_available:
    raise LocalModelError()
```

### 4.6 日志迁移优先级

| 优先级 | 内容 | 数量 | 影响范围 |
|--------|------|------|----------|
| **P0** | GUI 日志区域显示的状态 | ~30条 | 用户直接看到（任务进度、成功/失败、Cookie/代理状态） |
| **P1** | 错误弹窗/异常消息 | ~20条 | 用户直接看到的错误提示 |
| **P2** | 控制台警告/系统状态 | ~30条 | 技术用户关注 |
| **P3** | 调试日志 | ~50条 | 可保持中文不翻译 |

#### 4.6 日志 Key 命名规范

| 规则 | 说明 | 示例 |
|------|------|------|
| 使用 snake_case | 必须包含下划线 | `download_start` ✅ / `downloadStart` ❌ |
| 全小写 ASCII | 不含中文和大写 | `video_detected` ✅ / `VIDEO_DETECTED` ❌ |
| 语义清晰 | 动作_对象 或 对象_状态 | `task_progress`、`proxy_invalid` |

**兜底策略**：如果 key 在翻译文件中找不到，返回原 key 并在调试模式下输出警告，便于发现遗漏。

### 4.7 迁移文件顺序

1. **core/staged_pipeline.py**（任务进度、成功/失败）
2. **ui/business_logic.py**（状态回调、GUI日志）
3. **core/ai_providers/*.py**（API调用状态）
4. **core/pipeline.py**（处理流程日志）
5. **core/translator.py**（翻译相关日志）
6. **core/summarizer.py**（摘要相关日志）

---

## 五、AI 供应商适配方案

### 5.1 当前支持状态

| 供应商 | 客户端类 | 状态 |
|--------|---------|------|
| OpenAI | OpenAICompatibleClient | ✅ 已支持 |
| DeepSeek | OpenAICompatibleClient + base_url | ✅ 已支持 |
| Kimi/Moonshot | OpenAICompatibleClient + base_url | ✅ 已支持 |
| 通义千问 | OpenAICompatibleClient + base_url | ✅ 已支持 |
| 智谱GLM | OpenAICompatibleClient + base_url | ✅ 已支持 |
| Groq | OpenAICompatibleClient + base_url | ✅ 已支持 |
| Gemini | GeminiClient | ✅ 已支持 |
| Anthropic | AnthropicClient | ✅ 已支持 |
| Google翻译 | GoogleTranslateClient | ✅ 已支持 |
| Ollama | LocalModelClient | ⚠️ 需增强 |
| LM Studio | LocalModelClient | ⚠️ 需增强 |

### 5.2 能力预定义（Capabilities）

```python
# core/ai_providers/base.py

"""
AI 供应商基类和能力配置
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ProviderCapabilities:
    """供应商能力配置"""
    supports_vision: bool = False       # 是否支持图片输入
    supports_streaming: bool = True     # 是否支持流式输出
    supports_tools: bool = False        # 是否支持工具调用
    supports_json_mode: bool = False    # 是否支持 JSON 模式
    default_timeout: int = 60           # 默认超时时间（秒）
    max_tokens: int = 4096              # 默认最大输出 token
    context_window: int = 8000          # 上下文窗口大小


# 各供应商能力配置
PROVIDER_CAPABILITIES: Dict[str, ProviderCapabilities] = {
    "openai": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=60,
        max_tokens=4096,
        context_window=128000,
    ),
    "gemini": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=60,
        max_tokens=8192,
        context_window=1000000,
    ),
    "anthropic": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=False,
        default_timeout=60,
        max_tokens=8192,
        context_window=200000,
    ),
    "deepseek": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=60,
        max_tokens=4096,
        context_window=64000,
    ),
    "kimi": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=60,
        max_tokens=4096,
        context_window=128000,
    ),
    "qwen": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=60,
        max_tokens=4096,
        context_window=32000,
    ),
    "glm": ProviderCapabilities(
        supports_vision=True,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=60,
        max_tokens=4096,
        context_window=128000,
    ),
    "groq": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=True,
        supports_json_mode=True,
        default_timeout=30,  # Groq 响应快
        max_tokens=4096,
        context_window=32000,
    ),
    "ollama": ProviderCapabilities(
        supports_vision=False,  # 取决于具体模型
        supports_streaming=True,
        supports_tools=False,   # 大部分本地模型不支持
        supports_json_mode=False,
        default_timeout=300,    # 本地模型需要更长时间
        max_tokens=4096,
        context_window=8000,
    ),
    "lm_studio": ProviderCapabilities(
        supports_vision=False,
        supports_streaming=True,
        supports_tools=False,
        supports_json_mode=False,
        default_timeout=300,
        max_tokens=4096,
        context_window=8000,
    ),
}


def get_capabilities(provider: str) -> ProviderCapabilities:
    """获取供应商能力配置
    
    Args:
        provider: 供应商名称
    
    Returns:
        能力配置，如果未知则返回保守的默认配置
    """
    return PROVIDER_CAPABILITIES.get(
        provider.lower(),
        ProviderCapabilities()  # 默认保守配置
    )

> **重要说明**：
> - PROVIDER_CAPABILITIES 提供的是**保守默认值**
> - 实际值以用户配置或模型配置为准（配置优先级：用户配置 > 模型配置 > 供应商默认值）
> - 同一供应商的不同模型能力可能不同（如 GPT-4o 支持 vision，GPT-3.5 不支持）

> **重要区分**：
> - **能力支持（Capabilities）**：描述供应商/模型的技术能力（"能不能"）
> - **功能启用（Feature Flag）**：本项目是否使用该能力（"用不用"）
> 
> 本期虽然多数供应商标记 `supports_streaming=True`，但项目流程仍按**非流式**实现。
> 未来如需启用流式，只需打开开关，无需重构协议层。

```

### 5.3 LocalModelClient 实现

> **设计依据**：LM Studio 与 Ollama 的 OpenAI 兼容服务都支持 `GET /v1/models` 作为可用性探测端点，因此心跳检测统一走该端点即可。  
> **注意**：base_url 规范化只在 LocalModelClient 内做（补齐 `/v1`），避免误伤 Gemini 等非 `/v1` 形态的兼容层（例如 `.../v1beta/openai/`）。

```python
# core/ai_providers/local_model.py

"""
本地模型专用客户端（Ollama、LM Studio）
- 继承 OpenAICompatibleClient
- 增强：长超时、心跳检测、预热、友好报错
"""

from __future__ import annotations

from typing import Optional
import requests

from .openai_compatible import OpenAICompatibleClient
from core.exceptions import LocalModelError
from core.logger import get_logger

logger = get_logger()


class LocalModelClient(OpenAICompatibleClient):
    """本地模型专用客户端"""

    MIN_TIMEOUT = 300
    WARMUP_TIMEOUT = 30
    HEALTH_CHECK_TIMEOUT = 5

    def __init__(self, config):
        # 强制使用更长的超时时间
        original_timeout = config.timeout_seconds
        config.timeout_seconds = max(config.timeout_seconds, self.MIN_TIMEOUT)
        if config.timeout_seconds != original_timeout:
            logger.debug(f"本地模型超时时间调整: {original_timeout}s -> {config.timeout_seconds}s")

        super().__init__(config)

        self._warmed_up = False
        self._service_checked = False

    def _normalize_base_url(self) -> str:
        """
        规范化 base_url 到 OpenAI 兼容的 /v1 根路径：
        - 允许用户填：http://localhost:11434 或 http://localhost:11434/v1 或 .../v1/
        - 最终统一为：.../v1（不带尾部 /）
        """
        base = (self.base_url or "").rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return base

    def _check_service_available(self) -> bool:
        """检查本地模型服务是否可用（心跳）"""
        check_url = f"{self._normalize_base_url()}/models"  # GET /v1/models

        try:
            response = requests.get(check_url, timeout=self.HEALTH_CHECK_TIMEOUT)
            return response.status_code == 200
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            logger.warning("local_model_check_failed")
            return False
        except Exception as e:
            logger.debug(f"服务检查异常: {e}")
            return False

    def _warmup(self) -> None:
        """预热本地模型：发送轻量级请求唤醒模型，避免首次正式请求超时"""
        logger.info("local_model_warmup")

        try:
            original_timeout = self.ai_config.timeout_seconds
            self.ai_config.timeout_seconds = self.WARMUP_TIMEOUT

            super().generate("Hi", max_tokens=5)

            self.ai_config.timeout_seconds = original_timeout
            logger.info("local_model_ready", model=self.ai_config.model)

        except Exception as e:
            logger.debug(f"预热失败（不影响使用）: {e}")

        self._warmed_up = True

    def generate(self, prompt: str, **kwargs):
        """生成文本：首次调用时进行服务检查和预热"""
        if not self._service_checked:
            if not self._check_service_available():
                raise LocalModelError()
            self._service_checked = True

        if not self._warmed_up:
            self._warmup()

        return super().generate(prompt, **kwargs)

```

### 5.4 供应商支持总结

| 供应商类型 | 实现方式 | 特殊处理 |
|-----------|----------|----------|
| **OpenAI 官方** | OpenAICompatibleClient | 无 |
| **OpenAI 兼容** | OpenAICompatibleClient + base_url | 预定义常用端点 |
| **Gemini** | GeminiClient（原生） | 保留多模态扩展能力 |
| **Anthropic** | AnthropicClient | 无 |
| **本地模型** | LocalModelClient | 长超时 + 心跳检测 + 预热 |
| **Google 翻译** | GoogleTranslateClient | 无 |

> **关于 Gemini 的两种接入方式**：
> - **默认方式**：使用 GeminiClient（原生 SDK），保留多模态扩展能力
> - **可选方式**：通过 "Custom OpenAI" 配置 Gemini 的 OpenAI 兼容端点（base_url: `https://generativelanguage.googleapis.com/v1beta/openai/`），适合希望统一协议栈的用户

> **Gemini OpenAI 兼容接入鉴权（可选）**：
> 适用于希望“统一走 OpenAI 协议栈”的场景；多模态/供应商独有能力（例如更复杂的视频理解能力）仍建议保留 `GeminiClient`（原生 SDK）作为备用实现。
>
> - **Base URL（必须填到“协议根路径”）**：`https://generativelanguage.googleapis.com/v1beta/openai/`
>   - ✅ 这是 *OpenAI 兼容层* 的根路径（不要填写到某个具体 REST 端点，例如 `.../models/...:generateContent`）
> - **API Key**：使用 **Gemini API Key**（不是 OpenAI Key）
> - **Model Name**：填写 Gemini 模型名（例如 `gemini-2.5-flash` / `gemini-1.5-pro`）
> - **注意**：该兼容层为 Beta，部分 OpenAI 参数/行为可能与原生接口存在差异；若遇到兼容性限制，可切回 `GeminiClient`。

### 5.5 业务代码使用能力配置

```python
# 示例：根据能力决定行为

from core.ai_providers.base import get_capabilities

def translate_with_ai(client, text, config):
    capabilities = get_capabilities(config.provider)
    
    # 根据能力选择策略
    if capabilities.supports_json_mode:
        # 使用 JSON 模式获得结构化输出
        result = client.generate(prompt, json_mode=True)
    else:
        # 使用纯文本约束输出
        result = client.generate(prompt + "\n请只输出翻译结果，不要其他内容。")
    
    # 根据上下文窗口分块
    if len(text) > capabilities.context_window * 0.8:
        # 需要分块处理
        chunks = split_text(text, capabilities.context_window // 2)
        # ...
```

---

## 六、执行计划

### 6.1 整体时间线

| 阶段 | 周次 | 任务 | 产出物 |
|------|------|------|--------|
| **准备** | Week 0 | 建立回归测试基线 | 测试样例 + 预期输出存档 |
| **Phase 1** | Week 1 | 拆分 ai_providers + LocalModelClient | 8个新文件，测试通过 |
| **Phase 2** | Week 2 | 拆分 staged_pipeline + 依赖注入 | 8个新文件，dry_run 通过 |
| **Phase 3** | Week 3 | 日志基础设施 + P0 日志迁移 | 修改后的 logger.py + ~30条日志迁移 |
| **Phase 4** | Week 4 | P1 异常/错误迁移 | exceptions.py + ~20条异常迁移 |
| **Phase 5** | Week 5-6 | 拆分 output.py + pipeline.py | 10+个新文件 |
| **Phase 6** | Week 7-8 | UI 层拆分 + P2 日志迁移 | UI 模块重组 + ~30条日志迁移 |

### 6.2 Phase 1 详细任务（Week 1）

| 天 | 任务 | 验证标准 |
|----|------|----------|
| Day 1 | 创建 ai_providers/ 目录结构 | 目录和空文件创建完成 |
| Day 2 | 迁移 base.py + registry.py + factory.py | 基础设施测试通过 |
| Day 3 | 迁移 openai_compatible.py | OpenAI/DeepSeek 测试通过 |
| Day 4 | 实现 local_model.py | Ollama 连接测试通过 |
| Day 5 | 迁移 gemini.py + anthropic.py | 各客户端测试通过 |
| Day 6 | 迁移 google_translate.py | 翻译功能测试通过 |
| Day 7 | 完善 __init__.py + 集成测试 | 所有原有功能正常 |

**UI 配置增强**（可在 Phase 1 或 Phase 5 实现）：
- 在设置页面增加 **"Custom OpenAI Compatible"** 选项（统一接入 OpenAI 兼容服务）
- 配置项：
  - **Base URL（必填）**：必须填到“兼容协议根路径”
    - **LM Studio**：`http://localhost:1234/v1`（支持 `GET /v1/models`）
    - **Ollama**：`http://localhost:11434/v1`（OpenAI compatibility）
    - **Gemini OpenAI compatibility**：`https://generativelanguage.googleapis.com/v1beta/openai/`（注意是 v1beta/openai 形态）
  - **API Key（必填）**：使用对应供应商的 Key（Gemini 用 Gemini API Key，不是 OpenAI Key）
  - **Model Name（必填）**：供应商侧的模型标识（如 `llama3` / `deepseek-chat` / `gemini-2.0-flash`）
- 用途：支持任意 OpenAI 兼容服务（DeepSeek、Kimi、本地模型等），也支持用同一协议栈接入 Gemini（可选）。


### 6.3 Phase 2 详细任务（Week 2）

| 天 | 任务 | 验证标准 |
|----|------|----------|
| Day 1 | 创建 staged_pipeline/ 目录结构 | 目录和空文件创建完成 |
| Day 2 | 迁移 data_types.py + queue.py | 数据结构测试通过 |
| Day 3 | 迁移 scheduler.py（主调度器） | 基本调度测试通过 |
| Day 4 | 迁移 processors/detect.py + download.py | 检测下载测试通过 |
| Day 5 | 迁移 processors/translate.py + summarize.py | 翻译摘要测试通过 |
| Day 6 | 迁移 processors/output.py | 输出功能测试通过 |
| Day 7 | 完善 __init__.py + dry_run 全流程 | 完整流程测试通过 |

### 6.4 Phase 3 详细任务（Week 3）

| 天 | 任务 | 验证标准 |
|----|------|----------|
| Day 1 | 修改 logger.py 添加翻译功能 | 翻译函数单测通过 |
| Day 2 | 更新 JSON 翻译文件结构 | 文件格式验证通过 |
| Day 3-4 | 迁移 P0 日志（staged_pipeline） | GUI 日志区域显示正确 |
| Day 5-6 | 迁移 P0 日志（business_logic） | 状态显示正确 |
| Day 7 | 中英文切换测试 | 切换后日志语言正确 |

### 6.5 验收标准

#### 功能验收
- [ ] 所有 AI 供应商调用正常
- [ ] 本地模型（Ollama）连接正常，错误提示友好
- [ ] 单视频处理流程正常
- [ ] 批量处理流程正常
- [ ] 各输出格式生成正常
- [ ] 中英文切换后 UI + 日志 + 错误提示语言一致

#### 代码质量验收
- [ ] 无文件超过 500 行
- [ ] 无循环依赖
- [ ] 原有导入路径全部可用
- [ ] 现有测试全部通过

---

## 七、风险控制

### 7.1 风险清单

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| 拆分后功能异常 | 中 | 高 | 每次拆分后运行回归测试 |
| 循环依赖导致启动失败 | 中 | 高 | logger 中延迟导入 i18n |
| 闭包改造遗漏依赖 | 中 | 中 | 改为显式参数，编译期即可发现 |
| 本地模型服务未启动 | 高 | 低 | 心跳检测 + 友好提示 |
| 遗漏硬编码中文 | 高 | 低 | 正则搜索 `[\u4e00-\u9fa5]+` |
| 测试覆盖不足 | 中 | 中 | 重构前固定测试样例 |
| 原有导入路径失效 | 低 | 高 | `__init__.py` 完整导出 |

### 7.2 回滚策略

1. **代码版本控制**：每个 Phase 完成后打 Tag
2. **分支策略**：在 feature 分支开发，测试通过后合并
3. **渐进发布**：先内部测试，再灰度发布
4. **快速回滚**：保留原文件备份，问题时可快速恢复

### 7.3 测试策略

#### 回归测试样例
```
1. 单视频处理
   - 输入：YouTube 视频 URL
   - 预期：字幕下载 + 翻译 + 摘要 + 输出文件

2. 批量处理
   - 输入：频道/播放列表 URL
   - 预期：批量处理 + 进度显示 + 汇总报告

3. AI 供应商切换
   - 输入：相同文本，不同供应商
   - 预期：各供应商正常返回

4. 本地模型
   - 输入：Ollama 配置
   - 预期：服务检测 + 正常翻译

5. 错误处理
   - 输入：无效 API Key
   - 预期：友好错误提示（中/英文）

6. 语言切换
   - 操作：切换界面语言
   - 预期：UI + 日志 + 错误提示同步切换
```

---

## 八、范围外内容（明确不做）

以下内容在本次重构中**明确不做**，避免范围蔓延：

| 内容 | 不做原因 |
|------|----------|
| OpenAI Responses API | 当前以 Chat Completions 为主（兼容面更广），先把协议层与模块拆分做稳 |
| 运行时能力探测 | 复杂度高，本期用“预定义能力 + 配置覆盖”即可 |
| CLI 国际化 | CLI 用户少，优先级低 |
| 流式输出 | 字幕批量处理场景暂不需要 |
| Qt 翻译体系（.ts/.qm） | 项目使用 CustomTkinter，继续沿用 JSON i18n 体系 |
| 翻译后端过度抽象化 | 本期聚焦结构与稳定性，避免过度设计 |
| UI 大改版 | 本次聚焦结构重构，不改 UI 设计 |

### 8.1 可选优化（不阻塞主流程，建议 Phase 5-6 再评估）

| 内容 | 价值 |
|------|------|
| 长字幕分块优化 | 翻译/摘要质量与稳定性收益高，但需要结合模型上下文与对齐策略单独验证 |

---

## 九、附录：核心代码示例

### A. __init__.py 模板

```python
# core/ai_providers/__init__.py

"""
AI 供应商模块

提供统一的 LLM 客户端接口，支持多种 AI 供应商。

使用示例：
    from core.ai_providers import create_llm_client
    
    client = create_llm_client(config)
    result = client.generate("Hello")
"""

from .base import (
    LLMClient,
    ProviderCapabilities,
    PROVIDER_CAPABILITIES,
    get_capabilities,
)
from .factory import create_llm_client
from .registry import (
    register_provider,
    get_provider,
    list_providers,
    is_provider_registered,
)
from .openai_compatible import OpenAICompatibleClient
from .local_model import LocalModelClient
from .gemini import GeminiClient
from .anthropic import AnthropicClient
from .google_translate import GoogleTranslateClient

__all__ = [
    # 基类和工具
    "LLMClient",
    "ProviderCapabilities",
    "PROVIDER_CAPABILITIES",
    "get_capabilities",
    # 工厂和注册
    "create_llm_client",
    "register_provider",
    "get_provider",
    "list_providers",
    "is_provider_registered",
    # 客户端类
    "OpenAICompatibleClient",
    "LocalModelClient",
    "GeminiClient",
    "AnthropicClient",
    "GoogleTranslateClient",
]

__version__ = "2.0.0"
```

### B. 处理器基类模板

```python
# core/staged_pipeline/processors/base.py

"""
处理器基类
"""
from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass


@dataclass
class ProcessorResult:
    """处理器结果"""
    success: bool
    data: Any = None
    error: str = None


class BaseProcessor(ABC):
    """处理器基类
    
    所有阶段处理器都应继承此类，实现 process 方法。
    依赖通过构造函数显式注入。
    """
    
    def __init__(self, config, logger):
        """初始化处理器
        
        Args:
            config: 应用配置
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger
    
    @abstractmethod
    def process(self, data: Any) -> ProcessorResult:
        """执行处理
        
        Args:
            data: 输入数据
        
        Returns:
            处理结果
        """
        pass
    
    def can_process(self, data: Any) -> bool:
        """检查是否可以处理该数据
        
        Args:
            data: 输入数据
        
        Returns:
            True 如果可以处理
        """
        return True
```

### C. 迁移检查清单

```markdown
## ai_providers.py 拆分检查清单

### 准备工作
- [ ] 备份原文件
- [ ] 创建新分支
- [ ] 确认测试可运行

### 文件创建
- [ ] 创建 core/ai_providers/ 目录
- [ ] 创建 __init__.py
- [ ] 创建 base.py
- [ ] 创建 factory.py
- [ ] 创建 registry.py
- [ ] 创建 openai_compatible.py
- [ ] 创建 local_model.py
- [ ] 创建 gemini.py
- [ ] 创建 anthropic.py
- [ ] 创建 google_translate.py

### 代码迁移
- [ ] 迁移 PROVIDER_CAPABILITIES
- [ ] 迁移 LLMClient 基类
- [ ] 迁移 _LLM_REGISTRY
- [ ] 迁移 create_llm_client
- [ ] 迁移 OpenAICompatibleClient
- [ ] 实现 LocalModelClient
- [ ] 迁移 GeminiClient
- [ ] 迁移 AnthropicClient
- [ ] 迁移 GoogleTranslateClient

### 导入更新
- [ ] 更新 __init__.py 导出
- [ ] 检查内部 import
- [ ] 检查外部 import（grep 搜索）

### 测试验证
- [ ] 单元测试通过
- [ ] OpenAI 调用测试
- [ ] Gemini 调用测试
- [ ] Ollama 调用测试
- [ ] 集成测试通过
- [ ] dry_run 全流程

### 清理工作
- [ ] 删除原 ai_providers.py
- [ ] 更新文档
- [ ] 提交代码
```

---

## 文档变更历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2025-12-15 | 初始分析报告 |
| v2.0 | 2025-12-16 | 四方方案整合，第一轮讨论 |
| v2.5 | 2025-12-16 | 第二轮讨论，解决分歧 |
| v3.0 | 2025-12-16 | **终版定稿**，四方三轮讨论完成 |

---

---

## 十、参考链接（便于核对）

```text
LM Studio OpenAI compatibility: https://lmstudio.ai/docs/developer/openai-compat
Ollama OpenAI compatibility: https://ollama.com/blog/openai-compatibility
Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai
Python logging filters (official docs): https://docs.python.org/3/library/logging.html
```

> **文档结束**
> 
> 本方案由 Claude、GPT、Grok、Gemini 四方三轮讨论整合而成，已达成一致，可直接执行。