# AI Profile 配置设计文档

## 概述

AI Profile 系统允许用户通过配置文件定义多个 AI 配置组合（profiles），然后根据任务类型（翻译、摘要等）选择不同的 profile。这样可以在不改代码的前提下灵活调整模型策略。

## 设计目标

1. **配置化**：通过 `ai_profiles.json` 文件定义多个 AI 配置组合
2. **任务类型映射**：将任务类型（如 `subtitle_translate`, `subtitle_summarize`）映射到对应的 profile
3. **向后兼容**：如果没有 profile 配置，使用现有的 `translation_ai` / `summary_ai` 配置
4. **灵活性**：支持为不同任务类型配置不同的模型/供应商组合

## 配置文件结构

### ai_profiles.json

```json
{
  "profiles": {
    "subtitle_translate_default": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "base_url": null,
      "timeout_seconds": 30,
      "max_retries": 2,
      "max_concurrency": 5,
      "api_keys": {
        "openai": "env:OPENAI_API_KEY"
      },
      "enabled": true
    },
    "subtitle_translate_fast": {
      "provider": "google_translate",
      "model": "google_translate_free",
      "timeout_seconds": 10,
      "max_retries": 1,
      "max_concurrency": 10,
      "api_keys": {},
      "enabled": true
    },
    "subtitle_summarize_default": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "base_url": null,
      "timeout_seconds": 60,
      "max_retries": 2,
      "max_concurrency": 3,
      "api_keys": {
        "openai": "env:OPENAI_API_KEY"
      },
      "enabled": true
    },
    "subtitle_summarize_quality": {
      "provider": "openai",
      "model": "gpt-4o",
      "base_url": null,
      "timeout_seconds": 120,
      "max_retries": 3,
      "max_concurrency": 2,
      "api_keys": {
        "openai": "env:OPENAI_API_KEY"
      },
      "enabled": true
    }
  },
  "task_mapping": {
    "subtitle_translate": "subtitle_translate_default",
    "subtitle_summarize": "subtitle_summarize_default"
  }
}
```

## 任务类型

- `subtitle_translate`: 字幕翻译任务
- `subtitle_summarize`: 字幕摘要任务

## 使用方式

### 1. 配置文件位置

`ai_profiles.json` 位于用户数据目录（与 `config.json` 同级）：
- Windows: `%APPDATA%/yt-subtitle-v2/ai_profiles.json`
- Linux: `~/.config/yt-subtitle-v2/ai_profiles.json`
- macOS: `~/Library/Application Support/yt-subtitle-v2/ai_profiles.json`

### 2. Profile 选择逻辑

1. **优先使用 Profile**：
   - 如果 `ai_profiles.json` 存在且配置了对应的 task_mapping
   - 使用 profile 中定义的配置创建 LLM 客户端

2. **回退到现有配置**：
   - 如果 profile 不存在或未配置
   - 使用 `AppConfig.translation_ai` 或 `AppConfig.summary_ai`

3. **禁用 Profile**：
   - 如果 profile 的 `enabled` 为 `false`
   - 回退到现有配置

## 实现细节

### AIProfileManager

负责：
- 加载和解析 `ai_profiles.json`
- 根据任务类型查找对应的 profile
- 将 profile 转换为 `AIConfig` 对象
- 提供默认 profile 配置

### 集成点

1. **`cli/utils.py` 中的 `create_llm_clients`**：
   - 修改为支持从 profile 创建 LLM 客户端

2. **`ui/business_logic.py` 中的 `_init_components`**：
   - 修改为支持从 profile 创建 LLM 客户端

3. **`core/ai_providers.py` 中的 `create_llm_client`**：
   - 保持不变，仍然接受 `AIConfig` 对象

## 向后兼容性

- 如果 `ai_profiles.json` 不存在，行为与之前完全相同
- 如果 profile 未配置或禁用，回退到现有配置
- 现有的 `translation_ai` 和 `summary_ai` 配置仍然有效

## 示例场景

### 场景 1: 快速翻译 + 高质量摘要

```json
{
  "task_mapping": {
    "subtitle_translate": "subtitle_translate_fast",
    "subtitle_summarize": "subtitle_summarize_quality"
  }
}
```

### 场景 2: 使用不同供应商

```json
{
  "profiles": {
    "subtitle_translate_default": {
      "provider": "google_translate",
      "model": "google_translate_free"
    },
    "subtitle_summarize_default": {
      "provider": "openai",
      "model": "gpt-4o-mini"
    }
  }
}
```

### 场景 3: 本地模型 + 云端模型

```json
{
  "profiles": {
    "subtitle_translate_default": {
      "provider": "openai",
      "model": "qwen2.5:7b",
      "base_url": "http://localhost:11434/v1"
    },
    "subtitle_summarize_default": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "base_url": null
    }
  }
}
```

